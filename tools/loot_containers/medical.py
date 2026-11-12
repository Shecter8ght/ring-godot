"""Медицина: мягкая сумка-укладка (ткань симуляцией) и настенная металлическая аптечка."""
import math

import bmesh
import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

import lc
from lc import L, V, part, shell_part, cyl, plug, rot_box
from build_found_lights import torus

# ================================================================ аптечка настенная


def med_cabinet(coll, m, at, open_: bool):
    """Аптечка настенная металлическая 360 × 460 × 120: корпус из листа 1 мм, дверца (лист 1 мм, отбортовка 20 мм,
    штампованный бортик) на рояльной петле по левой кромке, замок-защёлка с кнопкой справа; внутри две полки с
    бортиками. Корень — на стене (плоскость задней стенки), центр по ширине и высоте; лицо к −Y."""
    r = L.root("АП_аптечка_настенная" + ("_открыта" if open_ else ""), coll, at)
    W, H, D = 0.36, 0.46, 0.12
    bd = 0.100
    hw = W / 2
    body = shell_part("АП_корпус", coll, [m["steel_a"]], r, (W - 0.004, bd, H), 0.004, (0, -bd / 2, 0), "-y", 0.001, seg=2, flat=(2, 0, 3))
    # проушины крепления: две планки сверху и снизу сзади с отверстиями (кольцо)
    eb = bmesh.new()
    for z in (H / 2 + 0.012, -H / 2 - 0.012):
        for x in (-0.1, 0.1):
            lc.rbox(eb, (0.034, 0.002, 0.024), 0.006, (x, -0.001, z), seg=2)
    lc.obj(eb, "АП_проушины", coll, [m["steel_a"]], r, bevel=0.0003, segs=1, smooth=45)
    # полки с бортиками (передний борт 20 мм) и боковые направляющие-упоры
    sb = bmesh.new()
    for z in (0.045, -0.115):
        lc.rbox(sb, (W - 0.012, bd - 0.014, 0.0012), 0.0005, (0, -(bd - 0.014) / 2 - 0.002, z), seg=1)
        L.bm_box(sb, (-hw + 0.008, -bd + 0.004, z), (hw - 0.008, -bd + 0.0052, z + 0.022))
        for s in (-1, 1):
            L.bm_box(sb, (s * (hw - 0.0022) - (0.004 if s > 0 else 0), -bd + 0.004, z - 0.014), (s * (hw - 0.0022) + (0 if s > 0 else 0.004), -0.016, z))
    lc.obj(sb, "АП_полки", coll, [m["steel_a"]], r, bevel=0.0003, segs=1, smooth=45)
    # дверца: лист с отбортовкой; рояльная петля — звенья на оси слева
    dx0, dx1, dz0, dz1 = -hw, hw - 0.004, -H / 2 + 0.002, H / 2 - 0.002
    yfd = -bd - 0.002
    pv = (-hw - 0.003, yfd + 0.003, 0.0)
    db = bmesh.new()
    lc.tray_door(db, dx0 + 0.004, dx1, dz0, dz1, yfd, 0.020, 0.001)
    # штампованный бортик на лице: рамка 10 мм, высота 1,5 мм
    for (a0, b0, a1, b1) in ((dx0 + 0.03, dz0 + 0.03, dx1 - 0.03, dz0 + 0.04), (dx0 + 0.03, dz1 - 0.04, dx1 - 0.03, dz1 - 0.03),
                              (dx0 + 0.03, dz0 + 0.03, dx0 + 0.04, dz1 - 0.03), (dx1 - 0.04, dz0 + 0.03, dx1 - 0.03, dz1 - 0.03)):
        L.bm_box(db, (a0, yfd - 0.0015, b0), (a1, yfd, b1))
    door = part(db, "АП_дверца", coll, [m["steel_a"]], r, (0, 0, 0), pv, bevel=0.0004, segs=1, smooth=45, mover=True)
    # звенья петли: нечётные — на двери, чётные — на корпусе
    hd = bmesh.new()
    hk = bmesh.new()
    n = 15
    seg = (H - 0.01) / n
    for i in range(n):
        z0 = -H / 2 + 0.005 + i * seg
        tgt = hd if i % 2 == 0 else hk
        cyl(tgt, (pv[0], pv[1], z0 + 0.0003), (pv[0], pv[1], z0 + seg - 0.0003), 0.0036, segs=12)
        if i % 2 == 0:
            L.bm_box(hd, (pv[0], yfd - 0.0015 + 0.0, z0 + 0.0003), (dx0 + 0.008, yfd + 0.0, z0 + seg - 0.0003))
        else:
            L.bm_box(hk, (-hw - 0.0, yfd + 0.0, z0 + 0.0003), (pv[0] + 0.0036, yfd + 0.0015 + 0.0, z0 + seg - 0.0003))
    cyl(hd, (pv[0], pv[1], -H / 2 + 0.005), (pv[0], pv[1], H / 2 - 0.005), 0.0014, segs=8)
    part(hd, "АП_петля_дверца", coll, [m["chrome"]], door, pv, pv, bevel=0.0003, segs=1, smooth=50)
    lc.obj(hk, "АП_петля_корпус", coll, [m["chrome"]], r, bevel=0.0003, segs=1, smooth=50)
    # защёлка: кнопка в накладке справа, ответная скоба на корпусе
    lkx, lkz = hw - 0.040, 0.0
    lb = bmesh.new()
    lc.rbox(lb, (0.030, 0.003, 0.056), 0.007, (lkx, yfd - 0.0045, lkz), seg=3)
    lc.lathe(lb, [(0.0, 0.0), (0.0105, 0.0), (0.0105, 0.004), (0.0085, 0.0058), (0.0, 0.0058)], segs=22, origin=(lkx, yfd - 0.006, lkz), axis=(0, -1, 0))
    L.bm_box(lb, (lkx - 0.0035, yfd - 0.0015, lkz - 0.026), (lkx + 0.0035, yfd + 0.016, lkz - 0.019))
    part(lb, "АП_защёлка", coll, [m["plastic_white"]], door, pv, pv, bevel=0.0003, smooth=50)
    sk = bmesh.new()
    L.bm_box(sk, (lkx - 0.0045, -bd + 0.0, lkz - 0.030), (lkx + 0.0045, -bd + 0.014, lkz - 0.029))
    L.bm_box(sk, (lkx - 0.0045, -bd + 0.0, lkz - 0.0305), (lkx + 0.0045, -bd + 0.0015, lkz - 0.016))
    lc.obj(sk, "АП_скоба_защёлки", coll, [m["steel_raw"]], r, bevel=0.0003, segs=1, smooth=45)
    if open_:
        door.rotation_euler = (0, 0, math.radians(-110))
    return r


# ================================================================ сумка-укладка (ткань)

_SIM: dict = {}
BW, BD, BH = 0.50, 0.28, 0.30      # габарит сумки: ширина × глубина × высота
FOOT = 0.012


def _simulate() -> dict:
    """Закрытая сумка-коробка: скруглённая оболочка, ткань с внутренним давлением на полу и «вещами» внутри (как у
    спортивной сумки партии 3): складки на боках и оседание верха. Результат — вершины и грани, считается один раз."""
    if _SIM:
        return _SIM
    sc = bpy.context.scene
    bm = bmesh.new()
    lc.rbox(bm, (BW, BD, BH), 0.045, (0, 0, BH / 2 + 0.02), seg=4, flat=(14, 9, 9))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("МС_ткань")
    bm.to_mesh(me)
    bm.free()
    bag = bpy.data.objects.new("МС_ткань_сим", me)
    sc.collection.objects.link(bag)
    gb = bmesh.new()
    L.bm_box(gb, (-1, -1, -0.3), (1, 1, -0.012))
    gm = bpy.data.meshes.new("пол")
    gb.to_mesh(gm)
    ground = bpy.data.objects.new("пол_сим", gm)
    sc.collection.objects.link(ground)
    ground.modifiers.new("Столкновение", "COLLISION")
    ground.collision.thickness_outer = 0.006
    ground.collision.cloth_friction = 8.0
    sb = bmesh.new()
    lc.rbox(sb, (BW - 0.045, BD - 0.05, BH - 0.075), 0.05, (0, 0, BH / 2 + 0.002), seg=3)
    sm = bpy.data.meshes.new("вещи")
    sb.to_mesh(sm)
    stuff = bpy.data.objects.new("вещи_сим", sm)
    sc.collection.objects.link(stuff)
    stuff.modifiers.new("Столкновение", "COLLISION")
    stuff.collision.thickness_outer = 0.004
    stuff.collision.cloth_friction = 6.0
    cl = bag.modifiers.new("Ткань", "CLOTH")
    s = cl.settings
    s.quality = 8
    s.mass = 0.006
    s.tension_stiffness, s.compression_stiffness, s.shear_stiffness = 60.0, 60.0, 30.0
    s.bending_stiffness = 0.6
    s.air_damping = 2.0
    s.use_pressure = True
    s.uniform_pressure_force = 0.2
    s.pressure_factor = 1.0
    cl.collision_settings.use_collision = True
    cl.collision_settings.distance_min = 0.006
    cl.collision_settings.use_self_collision = False
    cl.collision_settings.collision_quality = 4
    sc.frame_start, sc.frame_end = 1, 70
    cl.point_cache.frame_start, cl.point_cache.frame_end = 1, 70
    for f in range(1, 71):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    done = bpy.data.meshes.new_from_object(bag.evaluated_get(dg), depsgraph=dg)
    verts = [tuple(v.co) for v in done.vertices]
    faces = [tuple(p.vertices) for p in done.polygons]
    for o in (bag, ground, stuff):
        bpy.data.objects.remove(o)
    bpy.data.meshes.remove(done)
    sc.frame_set(1)
    _SIM["verts"], _SIM["faces"] = verts, faces
    return _SIM


def _bag_bm(coll_dz: float = FOOT):
    sim = _simulate()
    bm = bmesh.new()
    vs = [bm.verts.new(V(p) + V((0, 0, coll_dz))) for p in sim["verts"]]
    for f in sim["faces"]:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _ordered_boundary(bm):
    """Граничные рёбра, собранные в замкнутую цепочку вершин."""
    bm.edges.ensure_lookup_table()
    be = [e for e in bm.edges if len(e.link_faces) == 1]
    nxt = {}
    for e in be:
        a, b = e.verts
        nxt.setdefault(a, []).append(b)
        nxt.setdefault(b, []).append(a)
    start = be[0].verts[0]
    chain = [start]
    prev, cur = None, start
    while True:
        cands = [v for v in nxt[cur] if v is not prev]
        if not cands:
            break
        n = cands[0]
        if n is start:
            break
        chain.append(n)
        prev, cur = cur, n
        if len(chain) > len(be) + 2:
            break
    return chain


def ribbon(bm, pts, nrm, profile, closed=False):
    """Лента по пути: в каждой точке рамка (касательная, нормаль наружу, бинормаль); профиль — (s вдоль нормали, v вдоль бинормали)."""
    n = len(pts)
    rings = []
    for i in range(n):
        if closed:
            t = (pts[(i + 1) % n] - pts[i - 1]).normalized()
        else:
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        nn = (nrm[i] - t * nrm[i].dot(t)).normalized()
        b = t.cross(nn).normalized()
        rings.append([bm.verts.new(pts[i] + nn * s + b * v) for s, v in profile])
    k = len(profile)
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for j in range(k):
            q = (j + 1) % k
            bm.faces.new((r0[j], r0[q], r1[q], r1[j]))
    if not closed:
        bm.faces.new(rings[0][::-1])
        bm.faces.new(rings[-1])


def med_bag(coll, m, at, open_: bool):
    """Сумка-укладка мягкая 500 × 300 × 280 (ш × в × г): ткань — симуляция на давлении с оседанием, клапан = верх и
    верхние полосы трёх сторон, на молнии по трём сторонам, задняя кромка — линия шарнира; боковые карманы на
    молнии, две ручки на клапане, D-кольца и плечевой ремень, светоотражающие ленты (нашивные, по поверхности),
    донные ножки. Закрыта / раскрыта (клапан откинут на 110°, внутри органайзер с резинками, три мягких подсумка
    и вкладыши)."""
    r = L.root("МС_сумка_укладка" + ("_раскрыта" if open_ else ""), coll, at)
    bm = _bag_bm()
    ztop = max(v.co.z for v in bm.verts)
    ymax = max(v.co.y for v in bm.verts)
    zc = FOOT + BH - 0.105              # линия молнии по бокам и спереди
    # разрез по линии молнии
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zc), plane_no=(0, 0, 1))
    bm.faces.ensure_lookup_table()
    yb_lim = ymax - 0.035

    def is_flap(f):
        c = f.calc_center_median()
        return c.z > zc + 1e-4 and (c.y < yb_lim or c.z > ztop - 0.045)
    flap_faces = [f for f in bm.faces if is_flap(f)]
    body_bm, flap_bm = bm.copy(), bm.copy()
    bm.free()
    bmesh.ops.delete(body_bm, geom=[f for f in body_bm.faces if is_flap(f)], context="FACES")
    bmesh.ops.delete(flap_bm, geom=[f for f in flap_bm.faces if not is_flap(f)], context="FACES")
    for b in (body_bm, flap_bm):
        bmesh.ops.recalc_face_normals(b, faces=b.faces)
        b.normal_update()
    # шарнир клапана — вдоль задней кромки верха
    hinge = V((0, ymax - 0.035, ztop - 0.03))
    # молнии: путь по краю разреза с нормалями
    zipp = {}
    for name, b in (("body", body_bm), ("flap", flap_bm)):
        chain = _ordered_boundary(b)
        pts = [v.co.copy() for v in chain]
        nrm = [v.normal.copy() for v in chain]
        zipp[name] = (pts, nrm)

    def zip_arc(pts, nrm):
        n = len(pts)
        # берём только точки линии молнии (z у линии разреза, не у задней шарнирной кромки)
        sel = [i for i in range(n) if abs(pts[i].z - zc) < 0.004 and pts[i].y < yb_lim]
        if not sel:
            return [], []
        # разрыв нумерации — ищем начало дуги
        s0 = next((i for i in sel if (i - 1) % n not in sel), sel[0])
        arc = []
        i = s0
        while i in sel and len(arc) <= n:
            arc.append(i)
            i = (i + 1) % n
        return [pts[i] for i in arc], [nrm[i] for i in arc]

    def tree_of(b):
        vs = [v.co.copy() for v in b.verts]
        b.verts.ensure_lookup_table()
        idx = {v: i for i, v in enumerate(b.verts)}
        return BVHTree.FromPolygons(vs, [tuple(idx[v] for v in f.verts) for f in b.faces])
    t_body, t_flap = tree_of(body_bm), tree_of(flap_bm)

    # ---- тело (нижняя часть + задняя стенка)
    body = lc.obj(body_bm, "МС_корпус", coll, [m["fabric"]], r, smooth=60)
    sol = body.modifiers.new("Ткань", "SOLIDIFY")
    sol.thickness = 0.003
    sol.offset = -1
    # ---- клапан
    flap_piv = hinge
    flap = lc.obj(flap_bm, "МС_клапан", coll, [m["fabric"]], r, smooth=60)
    flap.data.transform(Matrix.Translation(-flap_piv))
    flap.matrix_parent_inverse = Matrix.Identity(4)
    flap.location = flap_piv
    lc.MOVERS.setdefault(coll.name, []).append(flap)
    sol = flap.modifiers.new("Ткань", "SOLIDIFY")
    sol.thickness = 0.003
    sol.offset = -1
    # молния: ленты вдоль разреза на теле и на клапане, бегунок
    for name, par, ppv in (("body", r, V()), ("flap", flap, flap_piv)):
        pts, nrm = zip_arc(*zipp[name])
        if len(pts) < 4:
            continue
        pts = [p for p in pts]
        zb = bmesh.new()
        up = 1 if name == "flap" else -1
        # лента 14 мм поверх ткани, зубчатая дорожка 3 мм
        prof = [(0.0, 0.0), (0.0012, 0.0), (0.0012, 0.0 + up * 0.007), (0.0, up * 0.007)]
        if up > 0:
            prof = [(0.0, 0.0), (0.0012, 0.0), (0.0012, 0.0 + 0.007), (0.0, 0.007)]
        else:
            prof = [(0.0, -0.007), (0.0012, -0.007), (0.0012, 0.0), (0.0, 0.0)]
        ribbon(zb, pts, nrm, [(a + 0.0012, b) for a, b in prof])
        # зубчатая дорожка (рельеф) — узкий валик вдоль кромки
        track = [(0.0012, up * 0.0007 - 0.0016), (0.0030, up * 0.0007 - 0.0016), (0.0030, up * 0.0007 + 0.0016), (0.0012, up * 0.0007 + 0.0016)]
        ribbon(zb, pts, nrm, [(a + 0.0012, b) for a, b in track])
        o = lc.obj(zb, f"МС_молния_{'клапан' if name == 'flap' else 'корпус'}", coll, [m["zip"]], par, smooth=45)
        o.data.transform(Matrix.Translation(-ppv))
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.location = (0, 0, 0)
    # бегунок молнии на лице у левого угла
    arcp, arcn = zip_arc(*zipp["flap"])
    if arcp:
        k = len(arcp) // 5
        p = arcp[k]
        n_ = arcn[k]
        sb = bmesh.new()
        lc.rbox(sb, (0.020, 0.014, 0.014), 0.004, (0, 0, 0), seg=2)
        tabl = L.bm_box(sb, (-0.006, 0.006, -0.004), (0.006, 0.040, 0.0))
        for v in sb.verts:
            v.co += p + n_ * 0.0055 + V((0, 0, 0.007))
        o = lc.obj(sb, "МС_бегунок", coll, [m["chrome"]], flap, bevel=0.0005, smooth=45)
        o.data.transform(Matrix.Translation(-flap_piv))
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.location = (0, 0, 0)
    # ---- по поверхности: ray-cast по телу и клапану
    def cast(tree, origin, direction):
        hit = tree.ray_cast(V(origin), V(direction), 2.0)
        return hit if hit[0] is not None else None

    # светоотражающие ленты на лице: две вертикальные (на теле и клапане), 30 мм, + по верху клапана
    for x in (-0.15, 0.15):
        for tag, tree, z0, z1, par, ppv in (("корпус", t_body, FOOT + 0.045, zc - 0.014, r, V()), ("клапан", t_flap, zc + 0.014, ztop - 0.065, flap, flap_piv)):
            pts, nrm = [], []
            for i in range(14):
                z = z0 + (z1 - z0) * i / 13
                h = cast(tree, (x, -1.0, z), (0, 1, 0))
                if h:
                    pts.append(h[0]); nrm.append(h[1])
            if len(pts) < 3:
                continue
            rb = bmesh.new()
            ribbon(rb, pts, nrm, [(-0.0006, -0.015), (0.0010, -0.015), (0.0010, 0.015), (-0.0006, 0.015)])
            o = lc.obj(rb, f"МС_лента_светоотр_{tag}_{'л' if x < 0 else 'п'}", coll, [m["reflect"]], par, smooth=45)
            o.data.transform(Matrix.Translation(-ppv))
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.location = (0, 0, 0)
    # ручки на клапане: две петли строп поперёк верха, с прошивкой на концах
    hb = bmesh.new()
    for x in (-0.075, 0.075):
        h1 = cast(t_flap, (x, -0.075, ztop + 0.2), (0, 0, -1))
        h2 = cast(t_flap, (x, 0.075, ztop + 0.2), (0, 0, -1))
        if not h1 or not h2:
            continue
        a, b = h1[0], h2[0]
        path = lc.smooth_path([a + V((0, 0, -0.002)), a + V((0, -0.006, 0.020)), (a + b) / 2 + V((0, 0, 0.060)), b + V((0, 0.006, 0.020)), b + V((0, 0, -0.002))], 8)
        L.bm_sweep(hb, path, [(-0.0125, 0.0), (0.0125, 0.0), (0.0125, 0.0035), (-0.0125, 0.0035)], up=(0, 0, 1))
        for p in (a, b):
            L.bm_box(hb, (x - 0.0165, p.y - 0.011, p.z + 0.0005), (x + 0.0165, p.y + 0.011, p.z + 0.0032))
    o = lc.obj(hb, "МС_ручки", coll, [m["webbing"]], flap, smooth=40)
    o.data.transform(Matrix.Translation(-flap_piv))
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.location = (0, 0, 0)
    # боковые карманы на молнии: накладной рельеф на торцах
    pk = bmesh.new()
    zk = FOOT + 0.082
    for s in (-1, 1):
        h = cast(t_body, (s * 1.0, 0.0, zk), (-s, 0, 0))
        if h:
            x_out = h[0].x
            lc.rbox(pk, (0.018, 0.17, 0.095), 0.006, (x_out + s * 0.0045, 0.0, zk), seg=3)
            L.bm_box(pk, (x_out + s * 0.0125 - 0.0015, -0.085, zk + 0.0475 - 0.004), (x_out + s * 0.0125 + 0.0015, 0.085, zk + 0.0475 + 0.0))
    lc.obj(pk, "МС_карманы", coll, [m["fabric"]], r, smooth=45)
    # D-кольца на торцах и плечевой ремень
    rg = bmesh.new()
    ends = []
    for s in (-1, 1):
        h = cast(t_body, (s * 1.0, 0.0, FOOT + 0.160), (-s, 0, 0))
        if h:
            c = h[0] + V((s * 0.016, 0, 0.0))
            ends.append(c)
            torus(rg, c + V((s * 0.006, 0, 0)), (1, 0, 0), 0.016, 0.0028, segs=22, wsegs=8)
            L.bm_box(rg, (h[0].x + s * 0.001 - 0.002, -0.017, c.z + 0.012), (h[0].x + s * 0.001 + 0.002, 0.017, c.z + 0.02))
    lc.obj(rg, "МС_D_кольца", coll, [m["chrome"]], r, smooth=50)
    if len(ends) == 2:
        sb = bmesh.new()
        p0, p1 = ends[0], ends[1]
        path = [p0 + V((s0 * 0.01, 0, 0.0)) for s0 in (0,)] + [V((-0.31, -0.06, 0.07)), V((-0.34, -0.2, 0.003)), V((-0.1, -0.33, 0.003)),
                V((0.2, -0.3, 0.003)), V((0.33, -0.12, 0.012)), p1 + V((0.012, 0, 0))]
        flat = [V((q.x, q.y, max(q.z, 0.0015))) for q in lc.smooth_path(path, 8)]
        L.bm_sweep(sb, flat, [(-0.0125, 0.0), (0.0125, 0.0), (0.0125, 0.0025), (-0.0125, 0.0025)], up=(0, 0, 1))
        lc.rbox(sb, (0.075, 0.032, 0.012), 0.004, (0.0, -0.318, 0.007), seg=2)
        lc.obj(sb, "МС_ремень", coll, [m["webbing"]], r, smooth=40)
    # донные ножки
    ft = bmesh.new()
    for x in (-0.2, 0.2):
        for y in (-0.09, 0.09):
            cyl(ft, (x, y, 0.0), (x, y, FOOT + 0.002), 0.014, segs=16, r1=0.012)
    lc.obj(ft, "МС_ножки", coll, [m["rubber"]], r, smooth=50)
    if open_:
        _organizer(coll, m, r, zc)
        flap.rotation_euler = (math.radians(-110), 0, 0)
    return r


def _organizer(coll, m, r, zc):
    """Вкладка в корпусе: дно-панель, три перегородки, задняя панель с резинками-держателями, три мягких подсумка на
    молнии и два вкладыша из пенки."""
    z0 = FOOT + 0.028
    ob = bmesh.new()
    lc.rbox(ob, (0.44, 0.22, 0.008), 0.003, (0, 0.0, z0), seg=2)
    for x in (-0.147, 0.0, 0.147):
        lc.rbox(ob, (0.006, 0.20, 0.13), 0.0025, (x, 0.0, z0 + 0.065), seg=2)
    lc.rbox(ob, (0.44, 0.006, 0.17), 0.0025, (0, 0.105, z0 + 0.085), seg=2)
    lc.obj(ob, "МС_органайзер", coll, [m["fabric_dark"]], r, smooth=45)
    eb = bmesh.new()
    for i in range(8):
        x = -0.18 + i * 0.052
        for zz in (0.045, 0.105):
            path = lc.smooth_path([(x - 0.014, 0.1, z0 + zz), (x - 0.013, 0.0975, z0 + zz + 0.012), (x, 0.0955, z0 + zz + 0.016),
                                   (x + 0.013, 0.0975, z0 + zz + 0.012), (x + 0.014, 0.1, z0 + zz)], 4)
            L.bm_sweep(eb, path, [(-0.0015, 0.0), (0.0015, 0.0), (0.0015, 0.0016), (-0.0015, 0.0016)], up=(0, 1, 0))
    lc.obj(eb, "МС_резинки", coll, [m["elastic"]], r, smooth=40)
    pb = bmesh.new()
    zb = bmesh.new()
    for i, (x, w, h, rot) in enumerate(((-0.205, 0.075, 0.115, 0.04), (-0.07, 0.090, 0.100, -0.03), (0.09, 0.105, 0.085, 0.02))):
        n0 = len(pb.verts)
        lc.rbox(pb, (w, 0.040, h), 0.012, (0, 0, 0), seg=3)
        pb.verts.ensure_lookup_table()
        for v in pb.verts[n0:]:
            v.co = Matrix.Rotation(rot, 3, "Y") @ v.co + V((x, -0.02, z0 + 0.004 + h / 2))
        # молния по верху подсумка
        L.bm_box(zb, (x - w / 2 + 0.012, -0.02 - 0.0205, z0 + 0.004 + h - 0.006), (x + w / 2 - 0.012, -0.02 + 0.0205, z0 + 0.004 + h + 0.002))
    lc.obj(pb, "МС_подсумки", coll, [m["fabric"]], r, smooth=50)
    lc.obj(zb, "МС_подсумки_молнии", coll, [m["zip"]], r, bevel=0.0006, smooth=45)
    fb = bmesh.new()
    lc.rbox(fb, (0.17, 0.10, 0.045), 0.008, (0.15, 0.04, z0 + 0.027), seg=2)
    lc.rbox(fb, (0.13, 0.085, 0.040), 0.008, (-0.05, 0.05, z0 + 0.025), seg=2)
    lc.obj(fb, "МС_вкладыши", coll, [m["foam"]], r, smooth=50)
