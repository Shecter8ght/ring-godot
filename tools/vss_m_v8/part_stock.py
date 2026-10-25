# ВСС-М v8: деревянный скелетный приклад с пистолетной рукояткой — построен заново по контуру принятого
# приклада v7 (затыльник, гребень, окна), но с ровной посадкой под коробку v8, овальной рукояткой, переменной
# шириной и крупными скруглениями всех кромок. Резиновый затыльник v7 сохранён (вогнутый торец совпадает).
# Пластина строится кольцами (как rounded_slab у ракетницы): замкнута по построению, без модификатора «Фаска».
import json
import math
import os
import bmesh
import bpy
from mathutils import Vector
from lib import MM, boolean, collection, material, lathe, auto_sharp, apply_transform, fillet

HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, "stock_v7_section.json")      # контур v7 (разрез y=0), снят stock_section.py
HALF = 19.0


def resample(loop, step=1.2):
    out = []
    n = len(loop)
    for i in range(n):
        a = Vector(loop[i]); b = Vector(loop[(i + 1) % n])
        L = (b - a).length
        k = max(1, int(L / step))
        for j in range(k):
            out.append(tuple(a + (b - a) * (j / k)))
    return out


def smooth(loop, it=2):
    for _ in range(it):
        n = len(loop)
        loop = [tuple((Vector(loop[i - 1]) + 2 * Vector(loop[i]) + Vector(loop[(i + 1) % n])) / 4) for i in range(n)]
    return loop


def ring_slab(bm, loop, half, radius_fn, steps=7):
    """Пластина по контуру (x,z) толщиной ±half по Y со скруглёнными кромками радиуса radius_fn(x,z)."""
    n = len(loop)
    area = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n))
    if area < 0:
        loop = list(reversed(loop))
    nrm, radii, rhos = [], [], []
    for i in range(n):
        p0, p1, p2 = Vector(loop[i - 1]), Vector(loop[i]), Vector(loop[(i + 1) % n])
        t0, t1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        tan = (t0 + t1)
        tan = tan.normalized() if tan.length > 1e-9 else t1
        nrm.append(Vector((tan.y, -tan.x)))            # наружу (обход против часовой)
        turn = math.atan2(t0.x * t1.y - t0.y * t1.x, t0.dot(t1))
        rho = (p2 - p0).length / (2.0 * abs(math.sin(turn))) if abs(turn) > 1e-4 else 1e9
        rhos.append(rho)
        radii.append(radius_fn(p1.x, p1.y))
    # радиус не больше местной кривизны и меняется вдоль контура плавно
    radii = [max(0.3, min(radii[i], 0.85 * rhos[i])) for i in range(n)]
    seg = [(Vector(loop[(i + 1) % n]) - Vector(loop[i])).length for i in range(n)]
    for _ in range(3):
        for i in range(n):
            radii[i] = min(radii[i], radii[i - 1] + 0.35 * seg[i - 1])
        for i in range(n - 1, -1, -1):
            radii[i] = min(radii[i], radii[(i + 1) % n] + 0.35 * seg[i])
    for _ in range(10):
        radii = [min(radii[i], 0.25 * radii[i - 1] + 0.5 * radii[i] + 0.25 * radii[(i + 1) % n]) for i in range(n)]
    rings = {}
    for side in (1.0, -1.0):
        for k in range(steps + 1):
            th = (math.pi / 2.0) * k / steps
            ring = []
            for i in range(n):
                r = radii[i]
                off = r * (1.0 - math.cos(th))
                yy = half - r * (1.0 - math.sin(th))
                x = loop[i][0] - nrm[i].x * off
                z = loop[i][1] - nrm[i].y * off
                ring.append(bm.verts.new(Vector((x * MM, side * yy * MM, z * MM))))
            rings[(side, k)] = ring
    for side in (1.0, -1.0):
        for k in range(steps):
            r0, r1 = rings[(side, k)], rings[(side, k + 1)]
            for i in range(n):
                bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
        bm.faces.new(rings[(side, steps)])
    a, b = rings[(1.0, 0)], rings[(-1.0, 0)]
    for i in range(n):
        bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return loop, radii


def window_cutter(name, loop, half, r, coll):
    """Вырез окна со скруглёнными кромками: сечение — контур окна, у обеих поверхностей расходится наружу
    четвертью окружности радиуса r и выносится за поверхность."""
    n = len(loop)
    area = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n))
    if area < 0:
        loop = list(reversed(loop))
    nrm = []
    for i in range(n):
        p0, p1, p2 = Vector(loop[i - 1]), Vector(loop[i]), Vector(loop[(i + 1) % n])
        tan = ((p1 - p0).normalized() + (p2 - p1).normalized())
        tan = tan.normalized() if tan.length > 1e-9 else (p2 - p1).normalized()
        nrm.append(Vector((tan.y, -tan.x)))
    bm = bmesh.new()
    steps = 7
    profile = []                                     # (отступ наружу, y) от середины к поверхности и за неё
    profile.append((0.0, 0.0))
    for k in range(steps + 1):
        th = (math.pi / 2.0) * k / steps
        profile.append((r * (1.0 - math.cos(th)), half - r + r * math.sin(th) + 0.08))
    # дуга кончается чуть над поверхностью (не в её плоскости — иначе точный булев оставлял грань поверх окна)
    profile.append((r + 0.6, half + 0.9))
    profile.append((r + 1.2, half + 3.0))
    rings = []
    for off, yy in [(o, -y) for o, y in reversed(profile)] + profile[1:]:
        rings.append([bm.verts.new(Vector(((loop[i][0] + nrm[i].x * off) * MM, yy * MM, (loop[i][1] + nrm[i].y * off) * MM))) for i in range(n)])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    return o


def build(ctx):
    C = ctx["coll"]["Stock"]
    d = json.load(open(SEC, encoding="utf-8"))
    v7_loops = d["Wood_stock_with_integral_grip"]["0.0"]
    v7_loops.sort(key=lambda l: -len(l))
    outer_v7 = v7_loops[0]
    windows = v7_loops[1:3]
    # собрать наружный контур: дуга затыльника + низ v7 (x < 300) и верх v7 (x < 262), новый перед
    n = len(outer_v7)
    # обход v7 по часовой/против — найдём индексы по признакам
    def pick(cond):
        return [p for p in outer_v7 if cond(p)]
    top = sorted(pick(lambda p: p[1] > -22.5 and p[0] < 262.0 and p[0] > 21.0), key=lambda p: p[0])
    bottom = sorted(pick(lambda p: p[1] < -105.0 and p[0] < 300.0 and p[0] > 21.0), key=lambda p: -p[0])
    butt = sorted(pick(lambda p: p[0] <= 21.0), key=lambda p: p[1])
    front = [(262.0, 4.5), (266.5, 8.0), (271.0, 10.3), (276.0, 11.0), (281.6, 11.0),
             (281.6, -25.45), (345.6, -25.45), (345.6, -36.3),
             (344.6, -52.0), (343.2, -70.0), (341.6, -90.0), (340.0, -108.0), (338.6, -117.0), (335.0, -123.0),
             (327.0, -126.2), (314.0, -126.4), (303.0, -125.0)]
    # верх v7 у 262 уже поднимается; стыкуем: верх (по x вверх) → перед → низ (по x вниз) → затыльник (снизу вверх)
    loop = top + front + bottom + butt
    loop = resample(loop, 1.6)
    loop = smooth(loop, 1)
    # радиусы: крупно везде; затыльник и посадка под коробку — малые (стык)
    def rad(x, z):
        if x < 22.0:
            return 1.2
        if x > 279.0 and z > -27.0:
            return 1.0
        if x > 300.0 and z < -40.0:
            return 9.0           # рукоятка — почти овал
        return 7.0
    bm = bmesh.new()
    ring_slab(bm, loop, HALF, rad, steps=8)
    # большие вогнутые грани боков — треугольниками заранее: точный булев на таких n-угольниках ошибался
    caps = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="BEAUTY")
    me = bpy.data.meshes.new("Wood_stock_v8"); bm.to_mesh(me); bm.free()
    stock = bpy.data.objects.new("Wood_stock_v8", me)
    C.objects.link(stock)
    me.materials.append(material("Wood_stock"))
    def vol(o):
        b = bmesh.new(); b.from_mesh(o.data); v_ = b.calc_volume(); b.free(); return v_
    for i, w in enumerate(windows):
        wl = smooth(resample(w, 1.5), 2)
        cut = window_cutter(f"_win{i}", wl, HALF, 6.0, C)
        v0 = vol(stock)
        boolean(stock, cut)
        print("STOCK_WINDOW", i, "removed_cm3", round((v0 - vol(stock)) * 1e6, 1))
    # переменная ширина: затыльник 19.5, тело 18.0, у коробки 17.6, рукоятка к низу 15.5
    def sstep(a, b, t):
        u = min(1.0, max(0.0, (t - a) / (b - a)))
        return u * u * (3.0 - 2.0 * u)
    def width(x, z):
        # плавные переходы ширины: затыльник 19.6 → тело 18.0 → у коробки 17.6 → низ рукоятки 15.4
        w = 17.0 + (18.8 - 17.0) * (1.0 - sstep(17.0, 45.0, x))
        a = sstep(250.0, 278.0, x) * sstep(-44.0, -26.0, z)
        w = w + (18.2 - w) * a
        g = sstep(282.0, 305.0, x)
        wg = 18.2 - 2.4 * min(1.0, max(0.0, (-30.0 - z) / 85.0))
        w = w + (wg - w) * g
        return w
    # равномерная сетка перед сужением: длинные треугольники боковых граней после неравномерной ширины давали
    # косые полосы затенения; воксельная пересетка 0.5 мм, затем прореживание
    from lib import apply_all as _apply
    rm = stock.modifiers.new("remesh", "REMESH"); rm.mode = "VOXEL"; rm.voxel_size = 0.6 * MM; rm.adaptivity = 0.0
    _apply(stock)
    me = stock.data
    for vv in me.vertices:
        x, z = vv.co.x / MM, vv.co.z / MM
        vv.co.y *= width(x, z) / HALF
    for p in me.polygons:
        p.use_smooth = True
    dm = stock.modifiers.new("dec", "DECIMATE"); dm.decimate_type = "COLLAPSE"; dm.ratio = 0.18
    _apply(stock)
    for p in stock.data.polygons:
        p.use_smooth = True
    # крепёж: два винта крепления к коробке (по бокам у посадки), антабка слева у затыльника
    hw = []
    for s in (-1, 1):
        sc = lathe(f"Stock_screw_{'R' if s < 0 else 'L'}", [(0, 0), (0, 3.4), (0.5, 3.3), (1.1, 2.6), (1.3, 0)], C, "Steel_black", 32, 0, 0)
        sc.rotation_euler = (0, 0, math.pi / 2 * s)
        sc.location = (300.0 * MM, s * 18.05 * MM, -36.0 * MM)
        apply_transform(sc)
        from lib import box
        boolean(sc, box("_slot", 299.6, 300.4, -30, 30, -40.5, -31.5, C))
        auto_sharp(sc, 35)
        hw.append(sc)
    from lib import prism_xz, finish
    plate = prism_xz("Stock_sling_plate", fillet([(24.0, -106.0), (40.0, -106.0), (40.0, -92.0), (24.0, -92.0)], 3.0, 4),
                     17.8, 19.4, C, "Steel_black")
    finish(plate, 0.5, 2, 35)
    for i, (x, z) in enumerate(((27.5, -102.5), (36.5, -95.5))):
        r = lathe(f"Stock_sling_rivet_{i}", [(0, 0), (0, 1.4), (0.4, 1.3), (0.7, 0.8), (0.8, 0)], C, "Steel_black", 16, 0, 0)
        r.rotation_euler = (0, 0, math.pi / 2); r.location = (x * MM, 19.4 * MM, z * MM)
        apply_transform(r); auto_sharp(r, 40)
    import bpy as _b
    cu = _b.data.curves.new("Stock_sling_swivel", "CURVE"); cu.dimensions = "3D"
    loop_pts = fillet([(25.0, -122.0), (39.0, -122.0), (39.0, -104.0), (25.0, -104.0)], 5.0, 6)
    sp = cu.splines.new("POLY"); sp.points.add(len(loop_pts) - 1)
    for k, (x, z) in enumerate(loop_pts):
        sp.points[k].co = (x * MM, 21.2 * MM, z * MM, 1.0)
    sp.use_cyclic_u = True
    cu.bevel_depth = 1.3 * MM; cu.bevel_resolution = 3
    so = _b.data.objects.new("_sws", cu); C.objects.link(so)
    dg = _b.context.evaluated_depsgraph_get()
    me2 = _b.data.meshes.new_from_object(so.evaluated_get(dg), depsgraph=dg)
    _b.data.objects.remove(so, do_unlink=True); _b.data.curves.remove(cu)
    sw = _b.data.objects.new("Stock_sling_swivel", me2); C.objects.link(sw)
    me2.materials.append(material("Steel_black"))
    for p in me2.polygons:
        p.use_smooth = True
    # резиновый затыльник: контур v7 (вогнутый торец — по прикладу), скругление 3 мм, сквозные окна поперёк
    pad_loops = d["Ventilated_rubber_butt_pad"]["0.0"]
    pad_loops.sort(key=lambda l: -len(l))
    pl = smooth(resample(pad_loops[0], 1.0), 1)
    bm = bmesh.new()
    ring_slab(bm, pl, 18.9, lambda x, z: 1.0 if x > 24.5 else 3.2, steps=6)
    caps = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="BEAUTY")
    pme = bpy.data.meshes.new("Rubber_butt_pad"); bm.to_mesh(pme); bm.free()
    pad = bpy.data.objects.new("Rubber_butt_pad", pme); C.objects.link(pad)
    pme.materials.append(material("Rubber"))
    # окна: два ряда овалов вдоль затыльника, сквозь по Y
    from lib import join as _join, lathe as _lathe
    holes = []
    for k in range(10):
        z = -27.0 - k * 8.6
        for j, xc in enumerate((7.2, 13.6)):
            xs = xc + 3.2 * math.sin(math.radians(min(90.0, (k - 4.5) * 14.0))) * 0.0
            h = _lathe(f"_ph{k}_{j}", [(-30.0, 0.0), (-30.0, 1.9), (30.0, 1.9), (30.0, 0.0)], C, None, 20, 0, 0)
            h.data.transform(__import__("mathutils").Matrix.Rotation(math.pi / 2, 4, "Z"))
            h.data.transform(__import__("mathutils").Matrix.Diagonal((1.0, 1.0, 1.0, 1.0)))
            for vv in h.data.vertices:
                vv.co.z *= 1.0
            h.data.transform(__import__("mathutils").Matrix.Translation((xc * MM, 0, z * MM)))
            holes.append(h)
    boolean(pad, _join(holes, "_pholes"))
    for p in pad.data.polygons:
        p.use_smooth = True
    auto_sharp(pad, 40)
    btn = stock_release_button(C)
    return {"stock": stock, "swivel": sw, "pad": pad, "release": btn}


STOCK_BTN_TRAVEL = 2.5                   # ход кнопки снятия приклада вниз при нажатии


def stock_release_button(C):
    """Кнопка снятия приклада (образец владельца): на гребне приклада сразу за коробкой, плоский перед упирается
    в задний торец крышки, зад скруглён (в плане — «D»), сверху поперечное рифление; выходит из дерева, при нажатии
    утапливается вниз на STOCK_BTN_TRAVEL (риг: stock_release)."""
    import math as _m
    from lib import box, boolean, fillet, finish, join, prism_xy
    xf, xr, half = 276.4, 265.0, 7.4
    xc = xr + half
    pts = [(xf, -half), (xf, half), (xc, half)]
    for k in range(1, 12):
        t = _m.radians(90.0 + 180.0 * k / 12)
        pts.append((xc + half * _m.cos(t), half * _m.sin(t)))
    pts.append((xc, -half))
    from lib import cyl, renormal
    o = prism_xy("Stock_release_button", fillet(pts, [1.2, 1.2] + [0.0] * (len(pts) - 2), 3), 3.5, 16.0, C, "Steel_black")
    finish(o, 1.1, 4, 35)                    # грани скруглены (замечание владельца 25.10: «очень острые»)
    # поперечное рифление — скруглённые канавки
    grooves = [cyl(f"_sbg{k}", -half - 1, half + 1, 0.42, C, axis="Y", cy=x, cz=16.12, seg=12)
               for k, x in enumerate([267.4 + 1.25 * i for i in range(7)])]
    boolean(o, join(grooves, "_sbg"))
    renormal(o)
    return o
