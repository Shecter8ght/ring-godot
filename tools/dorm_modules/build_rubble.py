"""Обломки разрушенных стен общежития — форма на просмотр владельцем: глыбы кладки со штукатуркой и краской, кирпичи
и половняк, обломок пустотной плиты перекрытия с проволокой, куски штукатурки, крошка.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_rubble.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Clutter/models/RING_Dorm_Rubble_v01.blend"

Размеры — настоящие (мм): кирпич 250 × 120 × 65, шов 10–12 (ряд 77), стена в кирпич 250 — цепная перевязка (ложковый
ряд — две ложки, тычковый — тычки), перегородка в полкирпича 120; штукатурка 18–22 с краской (зелёная панель)
или побелкой; плита ПК 220 с каналами Ø159 через 185, проволока Вр Ø5 внизу. Глыба ломается уступами по швам:
кирпич на краю либо цел, либо расколот (излом — сетка с шумом, булева разность), либо выпал; раствор в швах
у края выкрошен на миллиметры, на постелях и тычках по излому — пятна корки, штукатурка отваливается по своей линии. Кирпич — ручной формовки: рёбра чуть скруглены, грани
неровные, на углах сколы плоскими гранями. Корень — точка опоры на полу, Z вверх. Материалы — нейтральные
слоты; текстуры после принятия формы.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import build_found_lights as F  # noqa: E402
import mlib as L  # noqa: E402

V = Vector
TAU = 2 * math.pi
BL, BW, BH = 0.250, 0.120, 0.065  # кирпич
JOINT = 0.011
COURSE = BH + JOINT


def mats() -> dict:
    return {
        "brick": L.material("Кирпич_красный", (0.42, 0.18, 0.11), 0.85),
        "mortar": L.material("Раствор", (0.58, 0.56, 0.51), 0.95),
        "plaster": L.material("Штукатурка", (0.74, 0.72, 0.67), 0.92),
        "paint_green": L.material("Краска_панель_зелёная", (0.2, 0.36, 0.28), 0.55),
        "whitewash": L.material("Побелка", (0.86, 0.86, 0.83), 0.9),
        "concrete": L.material("Бетон_плита", (0.5, 0.49, 0.46), 0.9),
        "wire": L.material("Проволока_ржавая", (0.3, 0.17, 0.1), 0.75, 0.6),
    }


# ---------------------------------------------------------------- помощники

def obj(bm, name: str) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(target: bpy.types.Object, cutter: bpy.types.Object, op: str) -> None:
    """Булева операция точным решателем, результат — в сетку target; резак удаляется."""
    md = target.modifiers.new("b", "BOOLEAN")
    md.operation = op
    md.solver = "EXACT"
    md.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg), depsgraph=dg)
    target.modifiers.remove(md)
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter)


def rough_box(size, cell: float, amp: float, seed: int, round_r: float = 0.002) -> bmesh.types.BMesh:
    """Брусок с центром в нуле: сетка ~cell, рёбра скруглены на round_r, грани неровные (шум amp по нормали)."""
    bm = bmesh.new()
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    L.bm_box(bm, (-hx, -hy, -hz), (hx, hy, hz))
    cuts = max(1, int(max(size) / cell))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-7)
    off = V((seed * 1.7, seed * 2.3, seed * 0.9))
    for v in bm.verts:
        p = V(v.co)
        inner = V((max(-hx + round_r, min(hx - round_r, p.x)), max(-hy + round_r, min(hy - round_r, p.y)),
                   max(-hz + round_r, min(hz - round_r, p.z))))
        d = p - inner
        n = d.normalized() if d.length > 1e-9 else V((0, 0, 1))
        if d.length > 1e-9:
            p = inner + n * round_r
        g = noise.noise(p * 28 + off) * amp + noise.noise(p * 90 + off) * amp * 0.35
        v.co = p + n * g
    return bm


def chip(bm, corner: V, normal: V, depth: float) -> None:
    """Скол угла: всё, что за плоскостью (corner + normal · depth), прижимается к ней — плоская грань скола."""
    n = normal.normalized()
    plane = corner - n * depth
    for v in bm.verts:
        d = (v.co - plane).dot(n)
        if d > 0:
            v.co -= n * d


def fracture_cutter(point: V, normal: V, span: float, amp: float, seed: int, name: str = "излом") -> bpy.types.Object:
    """Резак излома: толстая плита по ту сторону плоскости (point, normal), её грань у плоскости — шумная сетка."""
    n = normal.normalized()
    t = n.orthogonal().normalized()
    b = n.cross(t)
    cells = max(4, int(span / 0.005))
    bm = bmesh.new()
    off = V((seed * 3.1, seed * 1.3, 0.0))
    grid = []
    for j in range(cells + 1):
        row = []
        for i in range(cells + 1):
            u, w = (i / cells - 0.5) * span, (j / cells - 0.5) * span
            h = noise.noise(V((u, w, 0)) * 40 + off) * amp + noise.noise(V((u, w, 0)) * 130 + off) * amp * 0.3
            row.append(bm.verts.new(point + t * u + b * w + n * h))
        grid.append(row)
    faces = []
    for j in range(cells):
        for i in range(cells):
            faces.append(bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])))
    # шумная грань + выдавливание на 0,6 м по нормали — замкнутое тело резака
    ret = bmesh.ops.extrude_face_region(bm, geom=faces)
    moved = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=moved, vec=n * 0.6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj(bm, name)


def shard(rnd, cx: float, cz: float, rx: float, rz: float, corners=(5, 8), jag: float = 0.006,
          step: float = 0.015) -> list:
    """Контур обломка в плоскости (x, z): камень, бетон и штукатурка ломаются почти прямыми линиями —
    4–8 изломов по эллипсу rx × rz, между ними отрезки с мелкой неровностью jag и редкими выщерблинами."""
    k = rnd.randint(*corners)
    main = []
    for i in range(k):
        a = TAU * (i + rnd.uniform(-0.3, 0.3)) / k
        rr = rnd.uniform(0.72, 1.0)
        main.append(V((cx + rx * rr * math.cos(a), cz + rz * rr * math.sin(a), 0)))
    pts = []
    for i in range(k):
        p, q = main[i], main[(i + 1) % k]
        d = q - p
        n_seg = max(2, int(d.length / step))
        side = V((d.y, -d.x, 0)).normalized()  # наружу (контур против часовой)
        notch = rnd.random() < 0.3
        n0 = rnd.randint(0, n_seg - 1)
        n_len = rnd.randint(1, 3)
        drift = 0.0
        for t in range(n_seg):
            drift = drift * 0.6 + rnd.uniform(-jag, jag)
            off = drift
            if notch and n0 <= t < n0 + n_len:
                off -= rnd.uniform(0.012, 0.03)
            c = p + d * (t / n_seg) + side * off
            pts.append((c.x, c.y))
    return pts


def inside(poly: list, x: float, z: float) -> bool:
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            c = not c
        j = i
    return c


def prism(poly: list, y0: float, y1: float, layers: int, jitter: float, seed: int, name: str) -> bpy.types.Object:
    """Тело по контуру poly (x, z) толщиной y0…y1 (ось Y) со слоями: контур сдвинут наружу-внутрь плавным шумом
    по месту и глубине (амплитуда jitter) — излом поперёк толщины неровный, но без «шторок». Для булева пересечения."""
    bm = bmesh.new()
    rings = []
    cx = sum(p[0] for p in poly) / len(poly)
    cz = sum(p[1] for p in poly) / len(poly)
    off = V((seed * 1.9, seed * 0.7, seed * 2.9))
    for k in range(layers + 1):
        y = y0 + (y1 - y0) * k / layers
        ring = []
        for x, z in poly:
            d = V((x - cx, 0, z - cz))
            dn = d.normalized() if d.length > 1e-9 else V((1, 0, 0))
            q = V((x, y, z))
            j = (noise.noise(q * 9 + off) + 0.35 * noise.noise(q * 30 + off)) * jitter if jitter else 0.0
            ring.append(bm.verts.new((x + dn.x * j, y, z + dn.z * j)))
        rings.append(ring)
    n = len(poly)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return obj(bm, name)


def clip_inside(poly: list, outer: list) -> list:
    """Точки контура poly, вылезшие за outer, — к центру, пока не окажутся внутри (штукатурка не висит за кладкой)."""
    cx = sum(p[0] for p in outer) / len(outer)
    cz = sum(p[1] for p in outer) / len(outer)
    out = []
    for x, z in poly:
        t = 1.0
        while t > 0.05 and not inside(outer, cx + (x - cx) * t, cz + (z - cz) * t):
            t -= 0.02
        t = max(0.05, t - 0.02)
        out.append((cx + (x - cx) * t, cz + (z - cz) * t) if t < 0.99 else (x, z))
    return out


def brick_bm(rnd, seed: int) -> bmesh.types.BMesh:
    """Кирпич ручной формовки: размер ±1,5 мм, неровные грани, 0–3 скола на углах и рёбрах."""
    size = (BL + rnd.uniform(-0.0015, 0.0015), BW + rnd.uniform(-0.0012, 0.0012), BH + rnd.uniform(-0.001, 0.001))
    bm = rough_box(size, 0.01, 0.0006, seed, 0.0015)
    for _ in range(rnd.choice((1, 1, 2, 3, 4))):
        c = V((rnd.choice((-1, 1)) * size[0] / 2, rnd.choice((-1, 1)) * size[1] / 2, rnd.choice((-1, 1)) * size[2] / 2))
        nrm = V((c.x / size[0] * rnd.uniform(0.3, 1.0), c.y / size[1] * rnd.uniform(0.3, 1.0), c.z / size[2] * rnd.uniform(0.3, 1.0)))
        chip(bm, c, nrm, rnd.uniform(0.006, 0.022))
    return bm


def merge(dst: bmesh.types.BMesh, src: bmesh.types.BMesh, m: Matrix) -> None:
    L.transform(src, src.verts, m)
    me = bpy.data.meshes.new("tmp")
    src.to_mesh(me)
    src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)


def merge_obj(dst: bmesh.types.BMesh, ob: bpy.types.Object) -> None:
    dst.from_mesh(ob.data)
    me = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)


# ---------------------------------------------------------------- глыба кладки

def masonry(coll, m, at, name, w: float, h: float, full: bool, seed: int, paint: str, both_sides: bool = False,
            face_up: bool = True) -> bpy.types.Object:
    """Глыба кладки w × h (в плоскости стены), в кирпич (full) или в полкирпича, со штукатуркой и краской с комнаты.
    Лежит на полу (лицом вверх или вниз), чуть наклонена."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    thick = 0.250 if full else 0.120
    poly = shard(rnd, w / 2, h / 2, w / 2, h / 2)
    bricks = bmesh.new()
    mortar = bmesh.new()
    joints = bmesh.new()
    broken = []
    z = 0.0
    course = 0
    while z < h + COURSE:
        header = full and course % 2 == 1
        rows = [(0.0, BW)] if not full else ([(0.0, BW), (BW + JOINT + 0.0, BW)] if not header else [(0.0, BL)])
        along = BW if header else BL
        shift = (course % 2) * (BL + JOINT) / 2 if not full else (0.0 if not header else (BW + JOINT) / 2)
        kept_x = []
        for y0, depth in rows:
            x = -shift
            while x < w + along:
                x0, x1 = x, x + along
                zc0, zc1 = z, z + BH
                corners = [inside(poly, xx, zz) for xx in (x0, x1) for zz in (zc0, zc1)]
                n_in = sum(corners)
                keep = n_in == 4 or (n_in > 0 and rnd.random() < 0.45)
                brk = 0 < n_in < 4 and not keep and rnd.random() < 0.55
                if keep or brk:
                    bb = brick_bm(rnd, seed * 100 + len(kept_x) + course * 17)
                    if header:
                        bb_m = Matrix.Translation(((x0 + x1) / 2, y0 + depth / 2, (zc0 + zc1) / 2)) @ Matrix.Rotation(math.pi / 2, 4, "Z")
                    else:
                        bb_m = Matrix.Translation(((x0 + x1) / 2, y0 + depth / 2, (zc0 + zc1) / 2))
                    if brk:  # расколот: оставляем часть внутри контура
                        tmp = bmesh.new()
                        merge(tmp, bb, bb_m)
                        ob = obj(tmp, "кирпич_излом")
                        left_in = corners[0] or corners[1]
                        xb = x0 + along * rnd.uniform(0.3, 0.7)
                        nrm = V((1.0 if left_in else -1.0, rnd.uniform(-0.35, 0.35), rnd.uniform(-0.3, 0.3)))
                        boolean(ob, fracture_cutter(V((xb, y0 + depth / 2, (zc0 + zc1) / 2)), nrm, 0.3, 0.004, seed + course * 7 + int(x * 100)), "DIFFERENCE")
                        broken.append(ob)
                        kept_x.append((x0, xb) if left_in else (xb, x1))
                        # у излома корка кончается на сантиметр раньше рваного торца
                        mx0, mx1 = (x0, xb - 0.01) if left_in else (xb + 0.01, x1)
                    else:
                        merge(bricks, bb, bb_m)
                        kept_x.append((x0, x1))
                        mx0, mx1 = x0, x1
                    # корка раствора на кирпиче: шов рвётся по раствору, на постели и тычке остаются пятна —
                    # оболочка на 1,5 мм под гранью кирпича с шумом ±4 мм: наружу выходит примерно треть
                    env = rough_box((mx1 - mx0 - 0.003, depth - 0.006, BH - 0.003), 0.012, 0.0045, seed + course * 31 + int(x * 300))
                    merge(mortar, env, Matrix.Translation(((mx0 + mx1) / 2, y0 + depth / 2, (zc0 + zc1) / 2)))
                x += along + JOINT
        # раствор ряда — постель и вертикальные швы одним бруском во весь ряд за кирпичами, утоплен на 2 мм от граней
        if kept_x:
            xa, xb2 = min(a for a, _ in kept_x), max(b for _, b in kept_x)
            bed = rough_box((xb2 - xa, thick - 0.004, COURSE), 0.02, 0.0008, seed + course)
            merge(joints, bed, Matrix.Translation(((xa + xb2) / 2, thick / 2, z + BH / 2 - JOINT / 2)))
        z += COURSE
        course += 1
    # швы у края выкрошены на несколько миллиметров глубже кирпича
    jt = obj(joints, "швы")
    shrink = [(w / 2 + (x - w / 2) * 0.99, h / 2 + (zz - h / 2) * 0.99) for x, zz in poly]
    boolean(jt, prism(shrink, -0.05, thick + 0.05, 12, 0.006, seed + 5, "контур_раствора"), "INTERSECT")
    merge_obj(mortar, jt)
    mort = obj(mortar, "раствор")
    br = obj(bricks, name + "_кирпич")
    for ob in broken:
        bm = bmesh.new()
        bm.from_mesh(br.data)
        merge_obj(bm, ob)
        bm.to_mesh(br.data)
        bm.free()
    # штукатурка с комнатной стороны (y < 0): своя линия облома, местами отвалилась глубже
    pl_sides = [(-0.02, 0.0)] + ([(thick, thick + 0.02)] if both_sides else [])
    plaster_parts = []
    for k, (y0, y1) in enumerate(pl_sides):
        ppoly = clip_inside(shard(rnd, w / 2, h / 2, w / 2 * rnd.uniform(0.82, 0.96), h / 2 * rnd.uniform(0.78, 0.94), (4, 7),
                                  0.004, 0.012), poly)
        pr = prism(ppoly, y0, y1, 1, 0.0, seed + 30 + k, "штукатурка")
        pbm = bmesh.new()
        pbm.from_mesh(pr.data)
        # слегка неровный лицевой слой: краска по штукатурке — грань наружу
        for f in pbm.faces:
            f.material_index = 1 if abs(f.normal.y) > 0.9 and ((f.normal.y < 0) == (k == 0)) else 0
        pbm.to_mesh(pr.data)
        pbm.free()
        plaster_parts.append(pr)
    # всё в корень: глыба лицом вверх или вниз, чуть наклонена, низом на пол
    lay = Matrix.Rotation(math.radians(-90 if face_up else 90), 4, "X")
    tilt = Matrix.Rotation(rnd.uniform(-0.08, 0.08), 4, "X") @ Matrix.Rotation(rnd.uniform(-0.1, 0.1), 4, "Y")
    pieces = [(br, m["brick"], None), (mort, m["mortar"], None)] + [(p, m["plaster"], m[paint]) for p in plaster_parts]
    full_m = tilt @ lay @ Matrix.Translation((-w / 2, -thick / 2, -h / 2))
    low = 1e9
    for ob, _, _ in pieces:
        ob.data.transform(full_m)
        low = min(low, min((v.co.z for v in ob.data.vertices), default=0.0))
    for ob, mat, mat2 in pieces:
        ob.data.transform(Matrix.Translation((0, 0, -low)))
        ob.data.materials.append(mat)
        if mat2 is not None:
            ob.data.materials.append(mat2)
        for p in ob.data.polygons:
            p.use_smooth = True
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(40))
        except AttributeError:
            pass
        bpy.context.scene.collection.objects.unlink(ob)
        coll.objects.link(ob)
        ob.parent = r
    br.name, mort.name = name + "_кирпич", name + "_раствор"
    for k, p in enumerate(plaster_parts):
        p.name = name + "_штукатурка" + ("" if k == 0 else "_обратная")
    return r


# ---------------------------------------------------------------- кирпичи и половняк

def loose_bricks(coll, m, at, name, seed: int) -> bpy.types.Object:
    """Россыпь: целые кирпичи, половинки и куски с изломом, на части — корка раствора."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    whole = bmesh.new()
    crust = bmesh.new()
    broken = []
    spots = []
    for k in range(9):
        kind = ("whole", "whole", "whole", "half", "half", "half", "quarter", "quarter", "bit")[k]
        bb = brick_bm(rnd, seed * 10 + k)
        for _ in range(60):
            p = V((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.25, 0.25), 0))
            if all((p - q).length > 0.2 for q in spots):
                break
        spots.append(p)
        yaw = rnd.uniform(0, TAU)
        side = rnd.choice(("flat", "flat", "edge"))
        orient = Matrix.Rotation(math.pi / 2, 4, "X") if side == "edge" else Matrix.Identity(4)
        hz = (BW if side == "edge" else BH) / 2
        mtx = Matrix.Translation((p.x, p.y, hz)) @ Matrix.Rotation(yaw, 4, "Z") @ orient
        if kind == "whole" and rnd.random() < 0.6:  # корка раствора на постели
            cr = rough_box((BL * rnd.uniform(0.4, 0.9), BW * rnd.uniform(0.5, 0.95), 0.006), 0.015, 0.0015, seed + k)
            merge(crust, cr, mtx @ Matrix.Translation((rnd.uniform(-0.04, 0.04), 0, BH / 2 + 0.002)))
        if kind == "whole":
            merge(whole, bb, mtx)
            continue
        tmp = bmesh.new()
        merge(tmp, bb, mtx)
        ob = obj(tmp, "кусок")
        frac = {"half": 0.5, "quarter": 0.27, "bit": 0.18}[kind]
        axis = (mtx.to_3x3() @ V((1, 0, 0))).normalized()
        cut_at = mtx.to_translation() + axis * (BL * (frac - 0.5))
        nrm = axis + V((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3)))
        boolean(ob, fracture_cutter(cut_at, nrm, 0.3, 0.004, seed + k * 13), "DIFFERENCE")
        if kind == "bit":  # обломок — ещё и вдоль
            ax2 = (mtx.to_3x3() @ V((0, 1, 0))).normalized()
            boolean(ob, fracture_cutter(mtx.to_translation() + ax2 * rnd.uniform(-0.01, 0.02), ax2, 0.3, 0.004, seed + k * 29), "DIFFERENCE")
        broken.append(ob)
    br = obj(whole, name + "_кирпич")
    bm = bmesh.new()
    bm.from_mesh(br.data)
    for ob in broken:
        merge_obj(bm, ob)
    # куски после разреза могли повиснуть: каждую связную часть — низом на пол
    bm.to_mesh(br.data)
    bm.free()
    finish(br, m["brick"], r, coll)
    finish(obj(crust, name + "_раствор"), m["mortar"], r, coll)
    drop_islands(br)
    return r


def drop_islands(ob: bpy.types.Object) -> None:
    """Каждый отдельный кусок сетки опускается на пол своим низом."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        island = []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            island.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        low = min(x.co.z for x in island)
        for x in island:
            x.co.z -= low
    bm.to_mesh(ob.data)
    bm.free()


def finish(ob: bpy.types.Object, mat, parent, coll) -> None:
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(40))
    except AttributeError:
        pass
    bpy.context.scene.collection.objects.unlink(ob)
    coll.objects.link(ob)
    ob.parent = parent


# ---------------------------------------------------------------- плита перекрытия

def slab(coll, m, at, name, seed: int) -> bpy.types.Object:
    """Обломок пустотной плиты ПК 220: каналы Ø159 через 185 вдоль Y, излом по контуру с открытыми каналами,
    снизу торчит проволока Вр Ø5 — загнута как попало."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    W, D, T = 0.66, 0.52, 0.22
    bm = rough_box((W, D + 0.2, T), 0.015, 0.0012, seed, 0.004)
    con = obj(bm, name + "_бетон")
    con.data.transform(Matrix.Translation((0, 0, T / 2)))
    for k in range(-2, 3):
        x = k * 0.185 + 0.03
        cb = bmesh.new()
        L.bm_cyl(cb, (x, -0.6, T / 2), (x, 0.6, T / 2), 0.0795, 32)
        boolean(con, obj(cb, "канал"), "DIFFERENCE")
    # излом: контур в плоскости XY, слоями по толщине (ось Z): поворачиваем prism (он строит по X–Z, толщина по Y)
    poly = shard(rnd, 0.0, 0.0, W / 2 * 0.98, D / 2, (4, 6), 0.002, 0.012)
    pr = prism(poly, -0.02, T + 0.02, 16, 0.016, seed + 3, "контур_плиты")
    pr.data.transform(Matrix.Rotation(math.pi / 2, 4, "X"))  # (x, y, z) → (x, −z, y): толщина prism по Y → вверх по Z
    boolean(con, pr, "INTERSECT")
    con.data.transform(Matrix.Translation((0, 0, -min(v.co.z for v in con.data.vertices))))  # шум граней ушёл под пол
    finish(con, m["concrete"], r, coll)
    # проволока из рёбер между каналами, у низа: из излома наружу
    wires = bmesh.new()
    for k in range(-2, 2):
        x = k * 0.185 + 0.03 + 0.0925
        for end in (-1, 1):
            if rnd.random() < 0.35:
                continue
            y_edge = None
            for t in range(100):  # где ребро выходит из контура
                y = end * t * 0.005
                if not inside(poly, x, -y):  # контур повёрнут: его z стал −y
                    y_edge = y
                    break
            if y_edge is None:
                continue
            start = V((x, y_edge - end * 0.04, 0.03))
            length = rnd.uniform(0.08, 0.26)
            bend = V((rnd.uniform(-0.6, 0.6), 0, rnd.uniform(-0.2, 0.5)))
            path = []
            for i in range(14):
                t = i / 13
                d = V((0, end * 1.0, 0)) * (length * t) + bend * (length * t * t)
                path.append(start + d)
            for p in path:
                p.z = max(p.z, 0.003)
            prof = [(0.0025 * math.cos(TAU * i / 8), 0.0025 * math.sin(TAU * i / 8)) for i in range(8)]
            L.bm_sweep(wires, path, prof, up=(0, 0, 1))
    finish(obj(wires, name + "_проволока"), m["wire"], r, coll)
    return r


# ---------------------------------------------------------------- штукатурка и крошка

def plaster_flakes(coll, m, at, name, seed: int) -> bpy.types.Object:
    """Куски штукатурки 8–28 см, 14–22 мм, краской или побелкой с одной стороны, лежат как упали."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    spots = []
    for k in range(7):
        rx, rz = rnd.uniform(0.04, 0.14), rnd.uniform(0.03, 0.1)
        poly = shard(rnd, 0, 0, rx, rz, (4, 7), 0.003, 0.008)
        th = rnd.uniform(0.014, 0.022)
        pr = prism(poly, 0.0, th, 1, 0.0, seed + k, name + f"_кусок{k}")
        paint_up = rnd.random() < 0.6
        bm = bmesh.new()
        bm.from_mesh(pr.data)
        for f in bm.faces:
            f.material_index = 1 if (abs(f.normal.y) > 0.9 and f.normal.y > 0) else 0
        bm.to_mesh(pr.data)
        bm.free()
        for _ in range(60):
            p = V((rnd.uniform(-0.4, 0.4), rnd.uniform(-0.25, 0.25), 0))
            if all((p - q).length > 0.22 for q in spots):
                break
        spots.append(p)
        # плашмя: ось Y куска — вверх (краской вверх) или вниз; слегка выгнут
        lay = Matrix.Rotation(math.radians(90 if paint_up else -90), 4, "X")
        pr.data.transform(Matrix.Translation(p) @ Matrix.Rotation(rnd.uniform(0, TAU), 4, "Z") @ lay)
        for v in pr.data.vertices:
            v.co.z += ((v.co.x - p.x) ** 2 + (v.co.y - p.y) ** 2) * rnd.uniform(-0.3, 0.6)
        low = min(v.co.z for v in pr.data.vertices)
        pr.data.transform(Matrix.Translation((0, 0, -low)))
        finish(pr, m["plaster"], r, coll)
        pr.data.materials.append(m["paint_green"] if rnd.random() < 0.5 else m["whitewash"])
    return r


def crumbs(coll, m, at, name, seed: int, count: int = 160) -> bpy.types.Object:
    """Крошка 4–30 мм: кирпич, штукатурка, бетон — выпуклые обломки, кучнее к центру пятна."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    parts = {"brick": bmesh.new(), "plaster": bmesh.new(), "concrete": bmesh.new()}
    for k in range(count):
        kind = rnd.choice(("brick", "brick", "plaster", "plaster", "concrete"))
        size = rnd.uniform(0.004, 0.012) if rnd.random() < 0.7 else rnd.uniform(0.012, 0.03)
        bm = bmesh.new()
        for _ in range(rnd.randint(7, 12)):
            bm.verts.new(V((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 0.6))).normalized() * size * rnd.uniform(0.6, 1.0))
        bmesh.ops.convex_hull(bm, input=bm.verts[:])
        a, rr = rnd.uniform(0, TAU), 0.45 * abs(rnd.gauss(0, 0.45))
        low = min(v.co.z for v in bm.verts)
        merge(parts[kind], bm, Matrix.Translation((rr * math.cos(a) * 1.3, rr * math.sin(a), -low))
              @ Matrix.Rotation(rnd.uniform(0, TAU), 4, "Z"))
    for kind, bm in parts.items():
        finish(obj(bm, name + "_" + kind), m[kind], r, coll)
    return r


def build(out: str) -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Обломки_стен_v01")
    m = mats()
    masonry(top, m, (0.0, 0.0, 0.0), "CL_глыба_стена_в_кирпич", 0.95, 0.62, True, 11, "paint_green", face_up=True)
    masonry(top, m, (1.25, 0.0, 0.0), "CL_глыба_перегородка", 0.62, 0.5, False, 23, "whitewash", both_sides=True, face_up=False)
    loose_bricks(top, m, (2.3, 0.0, 0.0), "CL_кирпичи", 31)
    slab(top, m, (3.35, 0.0, 0.0), "CL_плита_обломок", 41)
    plaster_flakes(top, m, (4.35, 0.0, 0.0), "CL_штукатурка_куски", 53)
    crumbs(top, m, (5.25, 0.0, 0.0), "CL_крошка", 61)
    F.studio(L.collection("Студия"))
    floor = bpy.data.objects.get("студия_пол")
    if floor:
        floor.scale = (5.0, 2.2, 1.0)
        floor.location = (2.6, 0.1, 0)
    sc = bpy.context.scene
    cam = sc.camera
    cam.location = (2.6, -4.4, 2.0)
    cam.rotation_euler = (V((2.6, 0.0, 0.1)) - V(cam.location)).to_track_quat("-Z", "Y").to_euler()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build(argv[0])
