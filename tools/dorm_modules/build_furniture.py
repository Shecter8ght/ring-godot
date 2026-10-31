"""Мебель общежития, партия 1 (комнаты) — форма для просмотра владельцем: казённая мебель и вещи жильцов.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_furniture.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture/models/RING_Dorm_Furniture_v01.blend" [preview <папка>]

Интервью владельца 2026-10-31: казённая мебель вперемешку с вещами жильцов, целая, но старая (просевшая сетка,
комковатый матрас, примятые подушки дивана — геометрией; краска, износ и грязь — на текстурах после принятия формы).
Размеры — настоящих вещей, мм:
  кровать двухъярусная — 900 × 2000 × 1780 (как серый габарит стенда), стойки — труба Ø32, ярусы по верху рамы 370 и 1320;
  кровать одноярусная — 900 × 2000, спинки 950 / 750, сетка на 440; рамы — уголок 40 × 40 × 4, панцирная сетка на пружинах;
  матрас ватный — 1900 × 800 × 100, стёганый, с кантом; тумбочка — 400 × 400 × 650, ДСП 16, ящик и дверца;
  шкаф двустворчатый с антресолью — 1000 × 550 × 2100; стол — 1000 × 600 × 750, ножки 45 × 45, царга с ящиком;
  стул на металлокаркасе — труба Ø20, гнутая фанера, сиденье на 450, высота 830; табурет — 320 × 320 × 450;
  полка навесная со стёклами-купе — 800 × 220 × 300; холодильник малый — 480 × 600 × 850, ручка-рычаг сбоку;
  диван-книжка — 1900 × 850 × 850; ковёр на стену — 1500 × 2000 на трёх гвоздях; телевизор кинескопный 51 см с
  комнатной антенной; плитка электрическая одноконфорочная с открытой спиралью — 250 × 250 × 75.
Корень каждого предмета — середина опоры на полу (ковёр — середина низа у стены, полка — середина верха у стены),
Z вверх, лицо — к −Y. Материалы — нейтральные слоты по будущим отделкам.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import mlib as L  # noqa: E402
from build_found_lights import circle, lathe  # noqa: E402

V = Vector
TAU = 2 * math.pi


# ---------------------------------------------------------------- материалы (нейтральные, для просмотра формы)

def mats() -> dict:
    return {
        "bed_paint": L.material("Кровать_эмаль", (0.17, 0.24, 0.25), 0.45),
        "mesh": L.material("Сетка_проволока", (0.5, 0.5, 0.5), 0.35, 1.0),
        "cap": L.material("Заглушка_пластик", (0.025, 0.025, 0.025), 0.6),
        "chip": L.material("ДСП_ламинат", (0.30, 0.17, 0.08), 0.35),
        "edge": L.material("ДСП_кромка", (0.27, 0.15, 0.07), 0.5),
        "hdf": L.material("ДВП_задняя_стенка", (0.42, 0.32, 0.22), 0.85),
        "handle": L.material("Ручка_металл", (0.62, 0.62, 0.6), 0.3, 1.0),
        "wood": L.material("Дерево_лак", (0.33, 0.19, 0.08), 0.4),
        "plywood": L.material("Фанера_лак", (0.46, 0.29, 0.13), 0.35),
        "chair_frame": L.material("Стул_каркас_эмаль", (0.05, 0.05, 0.05), 0.4),
        "rubber": L.material("Резина", (0.02, 0.02, 0.02), 0.85),
        "glass": L.material("Стекло", (0.85, 0.9, 0.88), 0.03, 0.0, 0.2),
        "ticking": L.material("Матрас_тик", (0.62, 0.62, 0.64), 0.85),
        "piping": L.material("Матрас_кант", (0.5, 0.5, 0.52), 0.85),
        "sofa_fabric": L.material("Диван_ткань", (0.26, 0.17, 0.12), 0.9),
        "sofa_wood": L.material("Диван_дерево", (0.27, 0.14, 0.07), 0.45),
        "enamel": L.material("Холодильник_эмаль", (0.8, 0.79, 0.74), 0.25),
        "chrome": L.material("Хром", (0.8, 0.8, 0.8), 0.15, 1.0),
        "gasket": L.material("Уплотнитель", (0.55, 0.55, 0.53), 0.7),
        "black": L.material("Чёрная_краска", (0.02, 0.02, 0.02), 0.55),
        "carpet": L.material("Ковёр_шерсть", (0.35, 0.08, 0.06), 0.95),
        "nail": L.material("Гвоздь_сталь", (0.35, 0.33, 0.3), 0.5, 1.0),
        "tv_case": L.material("Телевизор_корпус", (0.13, 0.08, 0.05), 0.4),
        "tv_panel": L.material("Телевизор_панель", (0.16, 0.16, 0.16), 0.4),
        "tv_screen": L.material("Кинескоп", (0.04, 0.05, 0.05), 0.08),
        "tv_back": L.material("Телевизор_задняя_крышка", (0.08, 0.07, 0.06), 0.7),
        "plastic": L.material("Пластик_чёрный", (0.03, 0.03, 0.03), 0.45),
        "hot_body": L.material("Плитка_корпус", (0.72, 0.7, 0.64), 0.4),
        "ceramic": L.material("Керамика_плитки", (0.76, 0.72, 0.66), 0.8),
        "coil": L.material("Спираль_нихром", (0.3, 0.28, 0.26), 0.45, 1.0),
        "cord": L.material("Шнур", (0.03, 0.03, 0.03), 0.6),
    }


# ---------------------------------------------------------------- построители

def obj(bm, name, coll, mlist, parent, bevel=0.0, segs=2, angle=40.0, smooth=40.0):
    """bmesh → объект; у граней уже стоят номера слотов mlist."""
    ob = L.finish_bm(bm, name, coll, mlist[0], parent, bevel=bevel, segs=segs, angle=angle, smooth_angle=smooth)
    for m in mlist[1:]:
        ob.data.materials.append(m)
    return ob


def board(bm, mn, mx, face=0, edge=1) -> list:
    """Плита ДСП: пласти (по тонкой оси) — ламинат face, торцы — кромка edge."""
    fs = L.bm_box(bm, mn, mx)
    d = [abs(mx[i] - mn[i]) for i in range(3)]
    thin = d.index(min(d))
    bm.normal_update()
    for f in fs:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        f.material_index = face if ax == thin else edge
    return fs


def set_mat(faces, idx) -> None:
    for f in faces:
        f.material_index = idx


def fillet(points, r: float, steps: int = 6) -> list:
    """Ломаная со скруглёнными углами (гнутая труба): дуга радиуса r в каждом изломе."""
    pts = [V(p) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        d0, d1 = (a - b).normalized(), (c - b).normalized()
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))
        if ang > math.pi - 1e-3:
            out.append(b)
            continue
        t = min(r / math.tan(ang / 2), (a - b).length * 0.49, (c - b).length * 0.49)
        p0, p1 = b + d0 * t, b + d1 * t
        for k in range(steps + 1):
            u = k / steps
            out.append(p0 * (1 - u) ** 2 + b * 2 * u * (1 - u) + p1 * u * u)
    out.append(pts[-1])
    return out


def pipe(bm, points, r: float, segs: int = 12, bend: float = 0.0, caps: bool = True, closed: bool = False) -> list:
    """Труба / проволока по пути: рамки переносом без скручивания, изгибы — fillet."""
    path = fillet(points, bend) if bend > 0 else [V(p) for p in points]
    clean = [path[0]]
    for p in path[1:]:
        if (p - clean[-1]).length > 1e-6:
            clean.append(p)
    if closed and (clean[0] - clean[-1]).length < 1e-6:
        clean.pop()
    path, n = clean, len(clean)
    tans = []
    for i in range(n):
        if closed:
            t = (path[(i + 1) % n] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        elif i == 0:
            t = path[1] - path[0]
        elif i == n - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        tans.append(t.normalized())
    ref = V((0, 0, 1)) if abs(tans[0].z) < 0.9 else V((1, 0, 0))
    nrm = (ref - tans[0] * ref.dot(tans[0])).normalized()
    rings = []
    for i in range(n):
        if i > 0:
            ax = tans[i - 1].cross(tans[i])
            if ax.length > 1e-9:
                nrm = Matrix.Rotation(math.atan2(ax.length, tans[i - 1].dot(tans[i])), 3, ax.normalized()) @ nrm
        t = tans[i]
        b = t.cross(nrm).normalized()
        nn = b.cross(t).normalized()
        rings.append([bm.verts.new(path[i] + (nn * math.cos(TAU * k / segs) + b * math.sin(TAU * k / segs)) * r)
                      for k in range(segs)])
    faces = []
    for i in range(n if closed else n - 1):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            j = (k + 1) % segs
            faces.append(bm.faces.new((r0[k], r0[j], r1[j], r1[k])))
    if caps and not closed:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    return faces


def angle_steel(bm, p0, p1, inward, a: float = 0.04, t: float = 0.004) -> list:
    """Уголок a × a × t от p0 до p1 (верх полки по линии): вертикальная полка снаружи вниз, горизонтальная —
    поверху внутрь (inward — горизонтальный вектор внутрь кровати)."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0).normalized()
    w = V(inward).normalized()
    up = V((0, 0, 1))
    prof = [(0, 0), (a, 0), (a, -t), (t, -t), (t, -a), (0, -a)]
    a0 = [bm.verts.new(p0 + w * s + up * v) for s, v in prof]
    a1 = [bm.verts.new(p1 + w * s + up * v) for s, v in prof]
    faces = [bm.faces.new(a0[::-1]), bm.faces.new(a1)]
    for i in range(len(prof)):
        j = (i + 1) % len(prof)
        faces.append(bm.faces.new((a0[i], a0[j], a1[j], a1[i])))
    del ax
    return faces


def rounded_box(bm, size, r: float, cuts: int = 8, center=(0, 0, 0)) -> list:
    """Коробка со скруглением r по всем рёбрам: подразделённый куб, точки — на скруглённую оболочку."""
    sx, sy, sz = (s / 2 for s in size)
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    bmesh.ops.subdivide_edges(tmp, edges=tmp.edges[:], cuts=cuts, use_grid_fill=True)
    for v in tmp.verts:
        p = V((v.co.x * 2 * sx, v.co.y * 2 * sy, v.co.z * 2 * sz))
        inner = V((max(-sx + r, min(sx - r, p.x)), max(-sy + r, min(sy - r, p.y)), max(-sz + r, min(sz - r, p.z))))
        d = p - inner
        if d.length > 1e-9:
            p = inner + d.normalized() * r
        v.co = p + V(center)
    me = bpy.data.meshes.new("tmp_rounded_box")
    tmp.to_mesh(me)
    tmp.free()
    nv = len(bm.verts)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    return faces_of(nv, bm)


def faces_of(verts_before: int, bm) -> list:
    bm.verts.ensure_lookup_table()
    vs = bm.verts[verts_before:]
    return list({f for v in vs for f in v.link_faces})


def cut(target, coll, parent, name: str, bm) -> None:
    """Вырез булевой разностью (модификатор, не применён — форму можно поправить): резец скрыт."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.parent = parent
    ob.display_type = "WIRE"
    ob.hide_render = True
    md = target.modifiers.new(name, "BOOLEAN")
    md.object = ob
    md.solver = "EXACT"
    target.modifiers.move(len(target.modifiers) - 1, 0)
    ob.hide_set(True)


# ---------------------------------------------------------------- кровати

def spring(bm, p0, p1, coil_r: float = 0.0045, wire: float = 0.0008, turns: int = 9) -> None:
    """Пружина-растяжка с крючками на концах: от p0 (сетка) до p1 (рама)."""
    p0, p1 = V(p0), V(p1)
    ax = (p1 - p0)
    ln = ax.length
    ax.normalize()
    side = ax.cross(V((0, 0, 1))).normalized()
    up = side.cross(ax).normalized()
    hook = 0.008
    path = [p0, p0 + ax * hook * 0.6 + up * coil_r * 0.8]
    body = ln - 2 * hook
    n = turns * 14
    for i in range(n + 1):
        t = i / n
        a = TAU * turns * t
        path.append(p0 + ax * (hook + body * t) + (up * math.cos(a) + side * math.sin(a)) * coil_r)
    path += [p1 - ax * hook * 0.6 + up * coil_r * 0.8, p1]
    pipe(bm, path, wire, segs=5)


def bed_mesh(bm, x0, x1, y0, y1, z, sag: float, rng: random.Random, cell: float = 0.034, wire: float = 0.0009) -> None:
    """Панцирная сетка: ромбы из проволоки в два направления (одно над другим на толщину проволоки), просевшая
    к середине; по длинным краям — прут-окантовка, по торцам — прут, за который цепляются пружины."""
    w2, l2 = (x1 - x0) / 2, (y1 - y0) / 2
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bumps = [(rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(0.004, 0.009), rng.uniform(0.18, 0.35)) for _ in range(3)]

    def zf(x, y):
        u, v = (x - cx) / w2, (y - cy) / l2
        h = z - sag * max(1 - u * u, 0) ** 0.8 * max(1 - v * v, 0) ** 0.6
        for bx, by, d, rr in bumps:
            q = ((x - bx) ** 2 + (y - by) ** 2) / (rr * rr)
            h -= d * math.exp(-q)
        return h

    cs = cell * math.sqrt(2)
    step = cell * 0.5
    for fam in (1, -1):
        lo = (x0 - y1) if fam == 1 else (x0 + y0)
        hi = (x1 - y0) if fam == 1 else (x1 + y1)
        c = lo + cs * 0.5
        while c < hi:
            # x − y = c (fam 1) или x + y = c (fam −1)
            if fam == 1:
                xa, xb = max(x0, y0 + c), min(x1, y1 + c)
            else:
                xa, xb = max(x0, c - y1), min(x1, c - y0)
            if xb - xa > step:
                n = max(2, int((xb - xa) * math.sqrt(2) / step))
                pts = []
                for i in range(n + 1):
                    x = xa + (xb - xa) * i / n
                    y = x - c if fam == 1 else c - x
                    pts.append((x, y, zf(x, y) + (wire if fam == 1 else -wire) * 0.9))
                pipe(bm, pts, wire, segs=5)
            c += cs
    edge_r = 0.0013
    for x in (x0, x1):
        pipe(bm, [(x, y0 + (y1 - y0) * i / 40, zf(x, y0 + (y1 - y0) * i / 40)) for i in range(41)], edge_r, segs=6)
    for y in (y0, y1):
        pipe(bm, [(x0 + (x1 - x0) * i / 24, y, zf(x0 + (x1 - x0) * i / 24, y)) for i in range(25)], edge_r, segs=6)


def bed_level(bm_frame, bm_mesh, w: float, ln: float, z_top: float, rng: random.Random, sag: float) -> None:
    """Ярус: две боковины-уголка и две поперечины-уголка по верху z_top, сетка на пружинах между поперечинами."""
    hw, hl = w / 2, ln / 2
    xi = hw - 0.016  # ось стоек
    for s in (-1, 1):
        x = s * (xi - 0.016)
        set_mat(angle_steel(bm_frame, (x, -hl + 0.03, z_top), (x, hl - 0.03, z_top), (-s, 0, 0)), 0)
    for s in (-1, 1):
        y = s * (hl - 0.07)
        set_mat(angle_steel(bm_frame, (-xi + 0.035, y, z_top - 0.004), (xi - 0.035, y, z_top - 0.004), (0, -s, 0)), 0)
        # уши-накладки на стыке боковины со стойкой (клиновой замок)
        for sx in (-1, 1):
            set_mat(L.bm_box(bm_frame, (sx * xi - 0.022, s * (hl - 0.016) - 0.03, z_top - 0.07),
                             (sx * xi + 0.022, s * (hl - 0.016) + 0.03, z_top - 0.035)), 0)
    mx0, mx1 = -hw + 0.07, hw - 0.07
    my0, my1 = -hl + 0.16, hl - 0.16
    zm = z_top - 0.012
    bed_mesh(bm_mesh, mx0, mx1, my0, my1, zm, sag, rng)
    n = 12
    for i in range(n):
        x = mx0 + 0.01 + (mx1 - mx0 - 0.02) * i / (n - 1)
        for s in (-1, 1):
            ym = s * (hl - 0.16)
            spring(bm_mesh, (x, ym, zm), (x, s * (hl - 0.075), z_top - 0.006))


def bunk_bed(coll, m, at, rng) -> bpy.types.Object:
    """Двухъярусная: четыре стойки Ø32, торцевые рамы с перекладинами-лестницей, ярусы на 370 и 1320, ограждение."""
    r = L.root("КР_двухъярусная", coll, at)
    w, ln, h = 0.9, 2.0, 1.78
    xi, yi = w / 2 - 0.016, ln / 2 - 0.016
    fr = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            pipe(fr, [(sx * xi, sy * yi, 0.0), (sx * xi, sy * yi, h - 0.012)], 0.016, segs=16)
            L.bm_sphere(fr, (sx * xi, sy * yi, h - 0.012), 0.016, segs=16, rings=8)
    for sy in (-1, 1):
        y = sy * yi
        for zz in (0.16, 0.62, 0.98, 1.62):
            pipe(fr, [(-xi, y, zz), (xi, y, zz)], 0.011, segs=12)
        # верх торца — дугой из трубы, вставки — прутья в верхней раме
        pipe(fr, [(-xi, y, h - 0.06), (xi, y, h - 0.06)], 0.013, segs=12)
        for i in range(1, 6):
            x = -xi + 2 * xi * i / 6
            pipe(fr, [(x, y, 1.62), (x, y, h - 0.06)], 0.006, segs=8)
    # ограждение верхнего яруса вдоль одной боковины
    pipe(fr, [(-xi, -yi, 1.64), (-xi, yi, 1.64)], 0.013, segs=12)
    for i in range(1, 4):
        y = -yi + 2 * yi * i / 4
        pipe(fr, [(-xi, y, 1.33), (-xi, y, 1.64)], 0.007, segs=8)
    ms = bmesh.new()
    for z_top, sag in ((0.37, 0.03), (1.32, 0.022)):
        bed_level(fr, ms, w, ln, z_top, rng, sag)
    obj(fr, "КР2_рама", coll, [m["bed_paint"]], r, bevel=0.0015, segs=1, angle=50)
    obj(ms, "КР2_сетка", coll, [m["mesh"]], r)
    caps = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            lathe(caps, [(0, -0.002), (0.017, -0.002), (0.0175, 0.012), (0.016, 0.022), (0, 0.022)], segs=16,
                  origin=(sx * xi, sy * yi, 0.002))
    obj(caps, "КР2_подпятники", coll, [m["cap"]], r)
    return r


def single_bed(coll, m, at, rng) -> bpy.types.Object:
    """Одноярусная: изголовье 950 и изножье 750 — сварные рамы из трубы Ø32 с прутьями Ø12, сетка на 440."""
    r = L.root("КР_одноярусная", coll, at)
    w, ln = 0.9, 2.0
    xi, yi = w / 2 - 0.016, ln / 2 - 0.016
    fr = bmesh.new()
    for sy, top in ((1, 0.95), (-1, 0.75)):
        y = sy * yi
        pipe(fr, [(-xi, y, 0.0), (-xi, y, top), (xi, y, top), (xi, y, 0.0)], 0.016, segs=16, bend=0.07)
        pipe(fr, [(-xi, y, 0.5), (xi, y, 0.5)], 0.011, segs=12)
        n = 7
        for i in range(1, n):
            x = -xi + 2 * xi * i / n
            pipe(fr, [(x, y, 0.5), (x, y, top - (0.012 if abs(x) < xi - 0.07 else 0.03))], 0.006, segs=8)
    ms = bmesh.new()
    bed_level(fr, ms, w, ln, 0.44, rng, 0.04)
    obj(fr, "КР1_рама", coll, [m["bed_paint"]], r, bevel=0.0015, segs=1, angle=50)
    obj(ms, "КР1_сетка", coll, [m["mesh"]], r)
    caps = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            lathe(caps, [(0, -0.002), (0.017, -0.002), (0.0175, 0.012), (0.016, 0.022), (0, 0.022)], segs=16,
                  origin=(sx * xi, sy * yi, 0.002))
    obj(caps, "КР1_подпятники", coll, [m["cap"]], r)
    return r


def mattress(coll, m, at, rng) -> bpy.types.Object:
    """Ватный матрас: стёганый (ямки по сетке 250 мм), комковатый, кант по верхнему и нижнему шву."""
    r = L.root("МТ_матрас", coll, at)
    w, ln, t = 0.8, 1.9, 0.1
    bm = bmesh.new()
    # частая сетка, чтобы ямки стёжки и комки читались
    rounded_box(bm, (w, ln, t), 0.035, cuts=64, center=(0, 0, t / 2))
    tufts = [(x, y) for x in (-0.25, 0.0, 0.25) for y in (-0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75)]
    lumps = [(rng.uniform(-0.35, 0.35), rng.uniform(-0.9, 0.9), rng.uniform(0.004, 0.012), rng.uniform(0.08, 0.2))
             for _ in range(22)]
    for v in bm.verts:
        x, y, z = v.co
        top = (z - t / 2) / (t / 2)
        k = max(top, -top)  # 1 у пластей
        dz = 0.0
        for tx, ty in tufts:
            q = ((x - tx) ** 2 + (y - ty) ** 2) / 0.0016
            dz += 0.013 * math.exp(-q)
        lump = sum(d * math.exp(-((x - lx) ** 2 + (y - ly) ** 2) / (rr * rr)) for lx, ly, d, rr in lumps)
        sag = 0.012 * (1 - (2 * x / w) ** 2) * (1 - (2 * y / ln) ** 2)
        if k > 0.6:
            v.co.z += -dz * math.copysign(1, top) * k + lump * math.copysign(1, top) * k
        v.co.z -= sag
    set_mat(bm.faces, 0)
    pip = bmesh.new()
    for zz in (0.012, t - 0.012):
        pts = [(px, py, zz) for px, py in L.rrect(w - 0.012, ln - 0.012, 0.03, segs=6)]
        pts = [(x, y, z - 0.012 * (1 - (2 * x / w) ** 2) * (1 - (2 * y / ln) ** 2)) for x, y, z in pts]
        set_mat(pipe(pip, pts, 0.004, segs=8, closed=True), 0)
    obj(bm, "МТ_тик", coll, [m["ticking"]], r, smooth=80)
    obj(pip, "МТ_кант", coll, [m["piping"]], r, smooth=80)
    return r


# ---------------------------------------------------------------- ДСП: тумбочка, шкаф, полка

def bow_handle(bm, center, axis, length: float = 0.096, standoff: float = 0.028, rr: float = 0.0045) -> None:
    """Ручка-скоба: две ножки и перекладина (axis — вдоль ручки), лицо к −Y."""
    c, a = V(center), V(axis).normalized()
    out = V((0, -1, 0))
    p0, p1 = c - a * length / 2, c + a * length / 2
    pipe(bm, [p0, p0 + out * standoff, p1 + out * standoff, p1], rr, segs=10, bend=0.008)
    for p in (p0, p1):
        L.bm_cyl(bm, p + out * 0.001, p - out * 0.001 + out * 0.004, 0.007, segs=14)


def nightstand(coll, m, at, rng) -> bpy.types.Object:
    r = L.root("ТМ_тумбочка", coll, at)
    w, d, h, t = 0.4, 0.4, 0.65, 0.016
    hw, hd = w / 2, d / 2
    bm = bmesh.new()
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), -hd, 0), (s * hw + (0 if s > 0 else t), hd, h - t))
    board(bm, (-hw, -hd - 0.004, h - t), (hw, hd, h))
    board(bm, (-hw + t, -hd + 0.018, 0.06), (hw - t, hd - 0.004, 0.06 + t))
    board(bm, (-hw + t, -hd + 0.03, 0.0), (hw - t, -hd + 0.03 + t, 0.06))
    board(bm, (-hw + t, -hd + 0.018, 0.47), (hw - t, hd - 0.004, 0.47 + t))
    # накладные фасады: ящик и дверца (зазоры 2–3 мм, дверца на петлях слева чуть просела)
    board(bm, (-hw + 0.002, -hd - 0.016, 0.488), (hw - 0.002, -hd, h - t - 0.003))
    door = board(bm, (-hw + 0.002, -hd - 0.016, 0.064), (hw - 0.002, -hd, 0.484))
    L.transform(bm, {v for f in door for v in f.verts}, Matrix.Rotation(math.radians(-0.25), 4, "Y"))
    back = L.bm_box(bm, (-hw + 0.004, hd - 0.004, 0.06), (hw - 0.004, hd, h - t))
    set_mat(back, 2)
    obj(bm, "ТМ_корпус", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.0012, segs=1)
    hb = bmesh.new()
    bow_handle(hb, (0, -hd - 0.016, 0.57), (1, 0, 0))
    bow_handle(hb, (hw - 0.05, -hd - 0.016, 0.38), (0, 0, 1))
    obj(hb, "ТМ_ручки", coll, [m["handle"]], r)
    return r


def wardrobe(coll, m, at, rng) -> bpy.types.Object:
    r = L.root("ШК_шкаф", coll, at)
    w, d, h, t = 1.0, 0.55, 2.1, 0.016
    hw, hd = w / 2, d / 2
    bm = bmesh.new()
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), -hd, 0), (s * hw + (0 if s > 0 else t), hd, h - t))
    board(bm, (-hw, -hd - 0.004, h - t), (hw, hd, h))
    board(bm, (-hw + t, -hd + 0.018, 0.06), (hw - t, hd - 0.004, 0.06 + t))
    board(bm, (-hw + t, -hd + 0.03, 0.0), (hw - t, -hd + 0.03 + t, 0.06))
    board(bm, (-hw + t, -hd + 0.018, 1.70), (hw - t, hd - 0.004, 1.70 + t))
    gap = 0.003
    doors = []
    for s in (-1, 1):
        x0, x1 = (-hw + 0.002, -gap / 2) if s < 0 else (gap / 2, hw - 0.002)
        doors.append(board(bm, (x0, -hd - t, 0.064), (x1, -hd, 1.70 + t / 2 - gap / 2)))
        board(bm, (x0, -hd - t, 1.70 + t / 2 + gap / 2), (x1, -hd, h - t - 0.003))
    # правая створка чуть просела на петлях
    L.transform(bm, {v for f in doors[1] for v in f.verts},
                Matrix.Translation((hw, 0, 0.064)) @ Matrix.Rotation(math.radians(0.2), 4, "Y") @ Matrix.Translation((-hw, 0, -0.064)))
    back = L.bm_box(bm, (-hw + 0.004, hd - 0.004, 0.06), (hw - 0.004, hd, h - t))
    set_mat(back, 2)
    obj(bm, "ШК_корпус", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.0012, segs=1)
    hb = bmesh.new()
    for s in (-1, 1):
        bow_handle(hb, (s * 0.045, -hd - t, 1.02), (0, 0, 1), length=0.128)
        bow_handle(hb, (s * 0.07, -hd - t, 1.79), (1, 0, 0), length=0.064, standoff=0.022)
    # замочная скважина с накладкой на правой створке
    L.bm_cyl(hb, (0.045, -hd - t + 0.0005, 0.92), (0.045, -hd - t - 0.002, 0.92), 0.011, segs=18)
    obj(hb, "ШК_фурнитура", coll, [m["handle"]], r)
    return r


def wall_shelf(coll, m, at, rng) -> bpy.types.Object:
    """Навесная полка: корень — середина верха у стены (вешается на два ушка), стёкла-купе в пазах."""
    r = L.root("ПЛ_полка", coll, at)
    w, d, h, t = 0.8, 0.22, 0.30, 0.016
    hw = w / 2
    bm = bmesh.new()
    y0, y1 = -d, 0.0
    board(bm, (-hw, y0, -t), (hw, y1, 0.0))
    board(bm, (-hw, y0, -h), (hw, y1, -h + t))
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), y0, -h + t), (s * hw + (0 if s > 0 else t), y1 - 0.004, -t))
    board(bm, (-hw + t, y0 + 0.03, -h + t), (-hw + t + 0.3, y1 - 0.004, -h + t + 0.012))
    back = L.bm_box(bm, (-hw + 0.004, -0.004, -h + 0.004), (hw - 0.004, 0.0, -0.004))
    set_mat(back, 2)
    obj(bm, "ПЛ_корпус", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.001, segs=1)
    gl = bmesh.new()
    for i, (x0, x1) in enumerate(((-hw + t + 0.002, 0.012), (-0.012, hw - t - 0.002))):
        y = y0 + 0.012 + i * 0.007
        set_mat(L.bm_box(gl, (x0, y, -h + t + 0.002), (x1, y + 0.004, -t - 0.002)), 0)
    obj(gl, "ПЛ_стёкла", coll, [m["glass"]], r, smooth=10)
    hw2 = bmesh.new()
    for x0, x1 in ((-hw + t, hw - t),):
        for z0 in (-h + t, -t - 0.008):
            set_mat(L.bm_box(hw2, (x0, y0 + 0.006, z0), (x1, y0 + 0.026, z0 + 0.008)), 0)
    for s in (-1, 1):
        set_mat(L.bm_box(hw2, (s * (hw - 0.06) - 0.012, -0.004, -0.01), (s * (hw - 0.06) + 0.012, -0.0015, 0.018)), 0)
    obj(hw2, "ПЛ_пазы_и_ушки", coll, [m["handle"]], r, smooth=10)
    return r


# ---------------------------------------------------------------- стол, стул, табурет

def table(coll, m, at, rng) -> bpy.types.Object:
    r = L.root("СТ_стол", coll, at)
    w, d, h = 1.0, 0.6, 0.75
    hw, hd = w / 2, d / 2
    bm = bmesh.new()
    board(bm, (-hw, -hd, h - 0.022), (hw, hd, h))
    obj(bm, "СТ_столешница", coll, [m["chip"], m["edge"]], r, bevel=0.002, segs=2)
    wd = bmesh.new()
    li = 0.045
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = sx * (hw - 0.04 - li / 2), sy * (hd - 0.04 - li / 2)
            # ножка сужается книзу с внутренних сторон 45 → 35 мм
            fs = L.bm_box(wd, (cx - li / 2, cy - li / 2, 0.0), (cx + li / 2, cy + li / 2, h - 0.022))
            for v in {v for f in fs for v in f.verts}:
                if v.co.z < 0.01:
                    if (v.co.x - cx) * sx < 0:
                        v.co.x += sx * 0.01
                    if (v.co.y - cy) * sy < 0:
                        v.co.y += sy * 0.01
    za, zb = h - 0.022 - 0.08, h - 0.022
    xa, ya = hw - 0.04 - li + 0.002, hd - 0.04 - li + 0.002
    for sy in (-1, 1):
        y = sy * (hd - 0.04 - li / 2)
        if sy < 0:
            for x0, x1 in ((-xa, -0.2), (0.2, xa)):
                L.bm_box(wd, (x0, y - 0.01, za), (x1, y + 0.01, zb))
        else:
            L.bm_box(wd, (-xa, y - 0.01, za), (xa, y + 0.01, zb))
    for sx in (-1, 1):
        x = sx * (hw - 0.04 - li / 2)
        L.bm_box(wd, (x - 0.01, -ya, za), (x + 0.01, ya, zb))
    # ящик: фасад заподлицо с царгой, кнопка
    y = -(hd - 0.04 - li / 2)
    L.bm_box(wd, (-0.198, y - 0.01, za + 0.003), (0.198, y + 0.01, zb - 0.003))
    L.bm_box(wd, (-0.19, y + 0.01, za + 0.01), (-0.18, y + 0.42, zb - 0.01))
    L.bm_box(wd, (0.18, y + 0.01, za + 0.01), (0.19, y + 0.42, zb - 0.01))
    L.bm_box(wd, (-0.19, y + 0.01, za + 0.005), (0.19, y + 0.42, za + 0.012))
    obj(wd, "СТ_ножки_царга", coll, [m["wood"]], r, bevel=0.0015, segs=1)
    kn = bmesh.new()
    lathe(kn, [(0, 0), (0.007, 0), (0.0075, 0.006), (0.012, 0.012), (0.012, 0.02), (0.0, 0.021)], segs=20,
          origin=(0, y - 0.01, (za + zb) / 2), axis=(0, -1, 0))
    obj(kn, "СТ_кнопка", coll, [m["handle"]], r)
    return r


def chair(coll, m, at, rng) -> bpy.types.Object:
    """Стул на металлокаркасе: две боковые рамы из гнутой трубы Ø20 (передняя ножка — опора сиденья — задняя
    ножка), стойки спинки, царги; сиденье и спинка — гнутая фанера 10 мм на заклёпках."""
    r = L.root("СТУ_стул", coll, at)
    fr = bmesh.new()
    rr = 0.01
    zs = 0.425
    for s in (-1, 1):
        x = s * 0.2
        pipe(fr, [(x, -0.2, 0.0), (x, -0.19, zs), (x, 0.17, zs), (x, 0.23, 0.0)], rr, segs=12, bend=0.04)
        pipe(fr, [(x, 0.16, zs), (x, 0.19, 0.6), (x, 0.235, 0.83)], rr, segs=12, bend=0.12)
    for y in (-0.185, 0.165):
        pipe(fr, [(-0.2, y, zs), (0.2, y, zs)], 0.008, segs=10)
    pipe(fr, [(-0.2, -0.198, 0.14), (0.2, -0.198, 0.14)], 0.007, segs=10)
    # заклёпки сиденья (сверху, по выгибу листа) и спинки
    for sx in (-0.17, 0.17):
        for y in (-0.12, 0.1):
            L.bm_sphere(fr, (sx, y, zs + rr + 0.012 + sx * sx / 1.8 + 0.001), 0.004, segs=10, rings=5)
        L.bm_sphere(fr, (sx * 1.1, 0.226 - 0.187 ** 2 / 1.2 - 0.001, 0.72), 0.004, segs=10, rings=5)
    obj(fr, "СТУ_каркас", coll, [m["chair_frame"]], r)
    ply = bmesh.new()

    def panel(w, ln, thick, bend_r, origin, along, normal, front_roll=0.0, nu=24, nv=16):
        """Гнутая фанера: лист w × ln, изогнут вокруг оси along с радиусом bend_r, край by front_roll вниз."""
        o, a, n = V(origin), V(along).normalized(), V(normal).normalized()
        b = n.cross(a)
        rows = []
        for j in range(nv + 1):
            v = -ln / 2 + ln * j / nv
            row = []
            for i in range(nu + 1):
                u = -w / 2 + w * i / nu
                sag = (u * u) / (2 * bend_r) if bend_r > 0 else 0.0
                roll = front_roll * max(0.0, (-v - (ln / 2 - 0.06)) / 0.06) ** 2 if front_roll else 0.0
                p = o + a * u + b * v + n * (sag - roll)
                row.append(p)
            rows.append(row)
        top = [[ply.verts.new(p) for p in row] for row in rows]
        bot = [[ply.verts.new(p - n * thick) for p in row] for row in rows]
        for g in (top, bot):
            for j in range(nv):
                for i in range(nu):
                    q = (g[j][i], g[j][i + 1], g[j + 1][i + 1], g[j + 1][i])
                    ply.faces.new(q if g is top else q[::-1])
        ring = [(j, 0) for j in range(nv)] + [(nv, i) for i in range(nu)] + [(j, nu) for j in range(nv, 0, -1)] + \
               [(0, i) for i in range(nu, 0, -1)]
        for k in range(len(ring)):
            j0, i0 = ring[k]
            j1, i1 = ring[(k + 1) % len(ring)]
            ply.faces.new((top[j0][i0], bot[j0][i0], bot[j1][i1], top[j1][i1]))

    panel(0.40, 0.40, 0.010, 0.9, (0, -0.01, zs + rr + 0.012), (1, 0, 0), (0, 0, 1), front_roll=0.025)
    tilt = math.radians(14)
    # спинка: краями лежит на стойках спереди, середина выгнута назад (радиус 0,6 м)
    nb = len(ply.verts)
    panel(0.40, 0.17, 0.010, 0.0, (0, 0.226, 0.72), (1, 0, 0), (0, -math.cos(tilt), math.sin(tilt)), nu=24, nv=8)
    ply.verts.ensure_lookup_table()
    for v in ply.verts[nb:]:
        v.co.y -= (v.co.x ** 2) / 1.2
    obj(ply, "СТУ_фанера", coll, [m["plywood"]], r, bevel=0.0015, segs=2, angle=60, smooth=50)
    ft = bmesh.new()
    for s in (-1, 1):
        for y in (-0.2, 0.23):
            lathe(ft, [(0, -0.001), (0.012, -0.001), (0.0125, 0.018), (0.0105, 0.022), (0, 0.022)], segs=14,
                  origin=(s * 0.2, y, 0.0))
    obj(ft, "СТУ_подпятники", coll, [m["rubber"]], r)
    return r


def stool(coll, m, at, rng) -> bpy.types.Object:
    r = L.root("ТБ_табурет", coll, at)
    s2, h = 0.16, 0.45
    bm = bmesh.new()
    # сиденье с прорезью-ручкой
    seat = bmesh.new()
    outer = L.rrect(0.32, 0.32, 0.012, segs=3)
    L.bm_prism(seat, outer, (0, 0, h - 0.026), V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 0.026)))
    seat_ob = obj(seat, "ТБ_сиденье", coll, [m["wood"]], r, bevel=0.0025, segs=2, angle=60)
    li = 0.038
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = (sx * (s2 - 0.03 - li / 2), sy * (s2 - 0.03 - li / 2))
            L.bm_box(bm, (c[0] - li / 2, c[1] - li / 2, 0), (c[0] + li / 2, c[1] + li / 2, h - 0.026))
    a = s2 - 0.03 - li / 2
    for sx in (-1, 1):
        L.bm_box(bm, (sx * a - 0.009, -a, h - 0.026 - 0.05), (sx * a + 0.009, a, h - 0.026))
        L.bm_box(bm, (sx * a - 0.01, -a, 0.12), (sx * a + 0.01, a, 0.145))
    for sy in (-1, 1):
        L.bm_box(bm, (-a, sy * a - 0.009, h - 0.026 - 0.05), (a, sy * a + 0.009, h - 0.026))
        L.bm_box(bm, (-a, sy * a - 0.01, 0.16), (a, sy * a + 0.01, 0.185))
    obj(bm, "ТБ_ножки", coll, [m["wood"]], r, bevel=0.002, segs=1)
    # прорезь-ручка в сиденье
    cb = bmesh.new()
    L.bm_prism(cb, L.rrect(0.11, 0.028, 0.013, segs=4), (0, 0, h - 0.04), V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 0.06)))
    cut(seat_ob, coll, r, "ТБ_прорезь", cb)
    return r


# ---------------------------------------------------------------- вещи жильцов

def fridge(coll, m, at, rng) -> bpy.types.Object:
    """Малый холодильник 480 × 600 × 850: скруглённый корпус, дверца с уплотнителем, ручка-рычаг справа,
    шильдик, сзади — змеевик конденсатора и компрессор, ножки."""
    r = L.root("ХЛ_холодильник", coll, at)
    w, d, h = 0.48, 0.6, 0.85
    z0 = 0.025
    bm = bmesh.new()
    set_mat(rounded_box(bm, (w, d - 0.045, h - z0), 0.028, cuts=10, center=(0, 0.0225, z0 + (h - z0) / 2)), 0)
    body = obj(bm, "ХЛ_корпус", coll, [m["enamel"]], r, smooth=60)
    # ниша компрессора внизу сзади
    cb = bmesh.new()
    L.bm_box(cb, (-0.17, d / 2 - 0.16, 0.0), (0.21, d / 2 + 0.05, 0.215))
    cut(body, coll, r, "ХЛ_ниша", cb)
    dr = bmesh.new()
    set_mat(rounded_box(dr, (w - 0.006, 0.042, h - z0 - 0.016), 0.02, cuts=10, center=(0, -d / 2 + 0.021 + 0.004, z0 + (h - z0) / 2)), 0)
    obj(dr, "ХЛ_дверца", coll, [m["enamel"]], r, smooth=60)
    gk = bmesh.new()
    pts = [(x, -d / 2 + 0.046, z) for x, z in L.rrect(w - 0.03, h - z0 - 0.04, 0.025, segs=6, cy=z0 + (h - z0) / 2)]
    set_mat(pipe(gk, pts, 0.005, segs=8, closed=True), 0)
    obj(gk, "ХЛ_уплотнитель", coll, [m["gasket"]], r, smooth=80)
    hd = bmesh.new()
    # ручка-рычаг на правом торце дверцы: основание и изогнутая скоба
    yb = -d / 2 + 0.012
    xb = w / 2 - 0.003
    L.bm_box(hd, (xb - 0.012, yb - 0.012, 0.62), (xb + 0.004, yb + 0.012, 0.74))
    pipe(hd, [(xb + 0.004, yb - 0.004, 0.64), (xb + 0.03, yb - 0.02, 0.655), (xb + 0.034, yb - 0.025, 0.72),
              (xb + 0.004, yb - 0.006, 0.735)], 0.007, segs=12, bend=0.015)
    # шильдик на дверце
    L.bm_prism(hd, L.rrect(0.12, 0.028, 0.008, segs=3), (-0.1, -d / 2 + 0.004 + 0.0005, 0.79), V((1, 0, 0)), V((0, 0, 1)),
               V((0, -0.0025, 0)))
    obj(hd, "ХЛ_ручка_шильдик", coll, [m["chrome"]], r, smooth=50)
    bk = bmesh.new()
    yb2 = d / 2 + 0.018
    zz, rows = 0.18, []
    while zz < h - 0.08:
        rows.append(zz)
        zz += 0.045
    path = []
    for i, z in enumerate(rows):
        xs = (-w / 2 + 0.06, w / 2 - 0.06) if i % 2 == 0 else (w / 2 - 0.06, -w / 2 + 0.06)
        path += [(xs[0], yb2, z), (xs[1], yb2, z)]
    pipe(bk, path, 0.003, segs=8, bend=0.02)
    for x in (-w / 2 + 0.08, -0.06, 0.06, w / 2 - 0.08):
        pipe(bk, [(x, yb2 + 0.004, rows[0] - 0.02), (x, yb2 + 0.004, rows[-1] + 0.02)], 0.0012, segs=6)
    for x in (-w / 2 + 0.05, w / 2 - 0.05):
        L.bm_box(bk, (x - 0.01, d / 2 - 0.0225, rows[-1] + 0.01), (x + 0.01, yb2 + 0.008, rows[-1] + 0.03))
    lathe(bk, [(0.0, 0.0), (0.075, 0.0), (0.08, 0.07), (0.07, 0.13), (0.04, 0.155), (0.0, 0.16)], segs=24,
          origin=(0.02, d / 2 - 0.075, z0 + 0.012))
    L.bm_box(bk, (-0.16, d / 2 - 0.155, z0), (0.2, d / 2 - 0.005, z0 + 0.012))
    pipe(bk, [(0.02, d / 2 - 0.075, z0 + 0.16), (0.02, d / 2 - 0.075, 0.2), (0.08, d / 2 + 0.0, 0.205), (0.15, yb2, rows[0])],
         0.003, segs=8, bend=0.02)
    obj(bk, "ХЛ_конденсатор", coll, [m["black"]], r, smooth=60)
    ft = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.bm_cyl(ft, (sx * (w / 2 - 0.04), sy * (d / 2 - 0.08), 0.0), (sx * (w / 2 - 0.04), sy * (d / 2 - 0.08), z0 + 0.004), 0.015, segs=16)
    obj(ft, "ХЛ_ножки", coll, [m["plastic"]], r)
    return r


def cushion(bm, size, center, r: float, rng: random.Random, tufts=(), tuft_depth: float = 0.012, lumpiness: float = 0.008,
            sit=None, cuts: int = 16) -> None:
    """Набивная подушка: скруглённая коробка, ямки стёжки, комки, примятость там, где сидят (sit: x, y, глубина, радиус)."""
    fs = rounded_box(bm, size, r, cuts=cuts, center=center)
    c = V(center)
    hz = size[2] / 2
    lumps = [(rng.uniform(-size[0] / 2, size[0] / 2), rng.uniform(-size[1] / 2, size[1] / 2), rng.uniform(-1, 1) * lumpiness,
              rng.uniform(0.1, 0.25)) for _ in range(int(size[0] * 8) + 4)]

    def top_dz(x, y):
        dz = 0.0
        for tx, ty in tufts:
            dz -= tuft_depth * math.exp(-((x - tx) ** 2 + (y - ty) ** 2) / 0.0012)
        dz += sum(d * math.exp(-((x - lx) ** 2 + (y - ly) ** 2) / (rr * rr)) for lx, ly, d, rr in lumps)
        for sx, sy, sd, sr in sit or ():
            dz -= sd * math.exp(-((x - sx) ** 2 + (y - sy) ** 2) / (sr * sr))
        return dz

    for v in {v for f in fs for v in f.verts}:
        p = v.co - c
        top = p.z / hz
        if top > 0.5:
            v.co.z += top_dz(p.x, p.y) * (top - 0.5) * 2
    return top_dz


def sofa(coll, m, at, rng) -> bpy.types.Object:
    """Диван-книжка: ящик для белья на ножках, сиденье и спинка — набивные, стёганые пуговицами, примятые."""
    r = L.root("ДВ_диван", coll, at)
    w = 1.9
    fab = bmesh.new()
    set_mat(L.bm_box(fab, (-w / 2, -0.32, 0.06), (w / 2, 0.30, 0.3)), 0)
    sit = [(-0.45, -0.05, 0.03, 0.22), (0.35, 0.0, 0.022, 0.25)]
    seat_tufts = [(x, y) for x in (-0.7, -0.35, 0.0, 0.35, 0.7) for y in (-0.15, 0.15)]
    back_tufts = [(x, y) for x in (-0.7, -0.35, 0.0, 0.35, 0.7) for y in (-0.1, 0.12)]
    seat_dz = cushion(fab, (w, 0.66, 0.17), (0, -0.01, 0.3 + 0.085), 0.045, rng, tufts=seat_tufts, sit=sit, cuts=48)
    bk = bmesh.new()
    back_dz = cushion(bk, (w, 0.46, 0.15), (0, 0, 0), 0.045, rng, tufts=back_tufts, sit=[(-0.45, -0.05, 0.02, 0.2)], cuts=48)
    # спинка: подушка встаёт на ребро лицом к сидящему и откидывается назад на 12°
    rot = Matrix.Translation((0, 0.22, 0.68)) @ Matrix.Rotation(math.radians(90 - 12), 4, "X")
    L.transform(bk, bk.verts, rot)
    nfab = len(fab.verts)
    bm_merge = bk
    me = bpy.data.meshes.new("tmp")
    bm_merge.to_mesh(me)
    bm_merge.free()
    fab.from_mesh(me)
    bpy.data.meshes.remove(me)
    set_mat(faces_of(nfab, fab), 0)
    obj(fab, "ДВ_обивка", coll, [m["sofa_fabric"]], r, smooth=70)
    wd = bmesh.new()
    for sx in (-1, 1):
        for y in (-0.27, 0.25):
            lathe(wd, [(0, 0), (0.017, 0), (0.024, 0.06), (0, 0.06)], segs=16, origin=(sx * (w / 2 - 0.07), y, 0.0))
    # боковые деревянные накладки ящика — снаружи торцов
    for sx in (-1, 1):
        set_mat(L.bm_box(wd, (sx * w / 2 + (0 if sx > 0 else -0.02), -0.325, 0.06), (sx * w / 2 + (0.02 if sx > 0 else 0), 0.305, 0.31)), 0)
    obj(wd, "ДВ_дерево", coll, [m["sofa_wood"]], r, bevel=0.002, segs=1)
    # пуговицы стёжки в ямках сиденья и спинки
    bt = bmesh.new()
    for x, y in seat_tufts:
        L.bm_sphere(bt, (x, -0.01 + y, 0.47 + seat_dz(x, y) + 0.003), 0.009, segs=12, rings=6)
    for x, y in back_tufts:
        L.bm_sphere(bt, rot @ V((x, y, 0.075 + back_dz(x, y) + 0.003)), 0.009, segs=12, rings=6)
    obj(bt, "ДВ_пуговицы", coll, [m["sofa_fabric"]], r)
    return r


def carpet(coll, m, at, rng) -> bpy.types.Object:
    """Ковёр на стену 1500 × 2000, толщина 6 мм: висит на трёх гвоздях по верху, между ними провисает, по полю —
    мягкие волны, низ чуть отходит от стены."""
    r = L.root("КВ_ковёр", coll, at)
    w, h, t = 1.5, 2.0, 0.006
    nx, nz = 60, 80
    nails = (-0.7, 0.0, 0.7)
    waves = [(rng.uniform(-0.7, 0.7), rng.uniform(0.2, 1.8), rng.uniform(0.002, 0.006), rng.uniform(0.25, 0.5)) for _ in range(7)]

    def pos(u, v):
        x, z = -w / 2 + w * u, h * v
        top_sag = 0.0
        if v > 0.9:
            dn = min(abs(x - n) for n in nails)
            top_sag = 0.012 * min(dn / 0.35, 1.0) ** 1.5 * ((v - 0.9) / 0.1)
        y = -t
        for wx, wz, a, rr in waves:
            y -= a * math.exp(-((x - wx) ** 2 + (z - wz) ** 2) / (rr * rr))
        y -= 0.006 * max(0.0, 0.25 - v) / 0.25
        y -= 0.004 * min(min(abs(x - n) for n in nails) / 0.35, 1.0) * max(0.0, v - 0.85) / 0.15
        return V((x, y, z - top_sag))

    bm = bmesh.new()
    front = [[bm.verts.new(pos(i / nx, j / nz)) for i in range(nx + 1)] for j in range(nz + 1)]
    back = [[bm.verts.new(front[j][i].co + V((0, t, 0))) for i in range(nx + 1)] for j in range(nz + 1)]
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((front[j][i], front[j + 1][i], front[j + 1][i + 1], front[j][i + 1]))
            bm.faces.new((back[j][i], back[j][i + 1], back[j + 1][i + 1], back[j + 1][i]))
    ring = [(j, 0) for j in range(nz)] + [(nz, i) for i in range(nx)] + [(j, nx) for j in range(nz, 0, -1)] + \
           [(0, i) for i in range(nx, 0, -1)]
    for k in range(len(ring)):
        j0, i0 = ring[k]
        j1, i1 = ring[(k + 1) % len(ring)]
        bm.faces.new((front[j0][i0], back[j0][i0], back[j1][i1], front[j1][i1]))
    obj(bm, "КВ_ковёр", coll, [m["carpet"]], r, smooth=60)
    nb = bmesh.new()
    for x in nails:
        z = h - 0.025
        L.bm_cyl(nb, (x, -t - 0.001, z), (x, -t - 0.004, z), 0.0045, segs=14)
        L.bm_cyl(nb, (x, -t, z), (x, 0.02, z), 0.0015, segs=8)
    obj(nb, "КВ_гвозди", coll, [m["nail"]], r)
    return r


def tv(coll, m, at, rng) -> bpy.types.Object:
    """Кинескопный телевизор 51 см: передняя часть корпуса 580 × 450, назад сужается задней крышкой, экран выпуклый,
    справа панель с ручками и решёткой динамика; сверху комнатная антенна-«рогатка»."""
    r = L.root("ТВ_телевизор", coll, at)
    w, h, df = 0.58, 0.45, 0.22
    bm = bmesh.new()
    set_mat(rounded_box(bm, (w, df, h), 0.014, cuts=8, center=(0, -0.22 + df / 2, h / 2)), 0)
    body = obj(bm, "ТВ_корпус", coll, [m["tv_case"]], r, smooth=60)
    # экран утоплен в лицевую панель на 12 мм
    cb = bmesh.new()
    L.bm_prism(cb, L.rrect(0.45, 0.36, 0.03, segs=6, cx=-0.06, cy=h / 2 + 0.005), (0, -0.24, 0), V((1, 0, 0)), V((0, 0, 1)),
               V((0, 0.032, 0)))
    cut(body, coll, r, "ТВ_ниша_экрана", cb)
    bk = bmesh.new()
    # задняя крышка: усечённая пирамида со скруглёнными углами 520 × 400 → 300 × 260
    prof0 = L.rrect(0.52, 0.40, 0.03, segs=4, cy=h / 2)
    prof1 = L.rrect(0.30, 0.26, 0.03, segs=4, cy=h / 2 - 0.02)
    ring0 = [bk.verts.new((x, -0.0, z)) for x, z in prof0]
    ring1 = [bk.verts.new((x, 0.22, z)) for x, z in prof1]
    n = len(prof0)
    for i in range(n):
        j = (i + 1) % n
        bk.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
    # замкнутое тело (иначе нормали развернутся внутрь); передняя грань упирается в корпус и не видна
    bk.faces.new(ring1[::-1])
    bk.faces.new(ring0)
    obj(bk, "ТВ_задняя_крышка", coll, [m["tv_back"]], r, smooth=40)
    sc = bmesh.new()
    sw, sh = 0.40, 0.31
    cx, cz = -0.06, h / 2 + 0.005
    nu, nv = 24, 18
    y_front = -0.22
    grid = []
    for j in range(nv + 1):
        row = []
        for i in range(nu + 1):
            u, v = -1 + 2 * i / nu, -1 + 2 * j / nv
            # скруглённый прямоугольник экрана: сжимаем углы
            x, z = u * sw / 2, v * sh / 2
            ku = 1 - 0.12 * (abs(u) ** 6) * (abs(v) ** 6)
            bulge = 0.012 * (1 - u * u * 0.6) * (1 - v * v * 0.6)
            row.append(sc.verts.new((cx + x * ku, y_front + 0.012 - 0.002 - bulge, cz + z * ku)))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            sc.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    obj(sc, "ТВ_экран", coll, [m["tv_screen"]], r, smooth=80)
    pn = bmesh.new()
    # дно ниши вокруг выпуклого стекла — чёрная маска кинескопа
    mo = L.rrect(0.448, 0.358, 0.03, segs=6, cx=cx, cy=cz)
    L.bm_prism(pn, mo, (0, y_front + 0.0115, 0), V((1, 0, 0)), V((0, 0, 1)), V((0, 0.002, 0)))
    # панель управления справа: ручки и решётка
    px = 0.215
    set_mat(L.bm_box(pn, (px - 0.055, y_front - 0.003, 0.03), (px + 0.055, y_front - 0.001, h - 0.03)), 0)
    for k, z in enumerate((0.37, 0.31, 0.25)):
        lathe(pn, [(0, 0), (0.017, 0), (0.017, 0.02), (0.014, 0.024), (0, 0.024)], segs=20, origin=(px, y_front - 0.003, z),
              axis=(0, -1, 0))
    for k in range(9):
        z = 0.06 + k * 0.014
        set_mat(L.bm_box(pn, (px - 0.045, y_front - 0.0045, z), (px + 0.045, y_front - 0.003, z + 0.006)), 0)
    obj(pn, "ТВ_панель", coll, [m["tv_panel"]], r, smooth=50)
    an = bmesh.new()
    lathe(an, [(0, 0), (0.05, 0), (0.05, 0.008), (0.035, 0.03), (0.012, 0.042), (0, 0.044)], segs=24, origin=(0.0, -0.02, h))
    for s in (-1, 1):
        base = V((s * 0.006, -0.02, h + 0.04))
        direc = V((s * math.sin(math.radians(32)), 0.12, math.cos(math.radians(32)))).normalized()
        p = base
        for seg_len, rr in ((0.2, 0.0035), (0.19, 0.0027), (0.18, 0.002)):
            q = p + direc * seg_len
            L.bm_cyl(an, p, q, rr, segs=10)
            p = q - direc * 0.012
        L.bm_sphere(an, p + direc * 0.012, 0.0035, segs=10, rings=5)
    pipe(an, [(0.0, 0.0, h + 0.01), (0.0, 0.05, h + 0.012), (0.0, 0.2, h - 0.02), (0.02, 0.24, h - 0.15)], 0.0018, segs=6, bend=0.03)
    obj(an, "ТВ_антенна", coll, [m["chrome"]], r, smooth=50)
    ft = bmesh.new()
    for sx in (-1, 1):
        for y in (-0.19, -0.03):
            set_mat(L.bm_box(ft, (sx * 0.25 - 0.02, y - 0.015, -0.0), (sx * 0.25 + 0.02, y + 0.015, 0.008)), 0)
    obj(ft, "ТВ_ножки", coll, [m["plastic"]], r)
    # корпус стоит на ножках
    for ob in coll.objects:
        if ob.parent == r and ob.type == "MESH":
            ob.location.z += 0.008 if ob.name != "ТВ_ножки" else 0.0
    return r


def hotplate(coll, m, at, rng) -> bpy.types.Object:
    """Плитка одноконфорочная: штампованный корпус, керамический диск с пазом и спиралью, ручка, шнур с вилкой."""
    r = L.root("ЭП_плитка", coll, at)
    s, h = 0.25, 0.075
    bm = bmesh.new()
    set_mat(rounded_box(bm, (s, s, h - 0.012), 0.012, cuts=8, center=(0, 0, 0.012 + (h - 0.012) / 2)), 0)
    obj(bm, "ЭП_корпус", coll, [m["hot_body"]], r, smooth=60)
    cr = bmesh.new()
    lathe(cr, [(0.0, h - 0.006), (0.085, h - 0.006), (0.094, h - 0.004), (0.095, h + 0.006), (0.0, h + 0.006)], segs=48)
    obj(cr, "ЭП_диск", coll, [m["ceramic"]], r, smooth=50)
    co = bmesh.new()
    pts = []
    turns, n = 6, 6 * 40
    for i in range(n + 1):
        t = i / n
        rr = 0.016 + (0.084 - 0.016) * t
        a = TAU * turns * t
        pts.append((rr * math.cos(a), rr * math.sin(a), h + 0.0075))
    pipe(co, pts, 0.0028, segs=8)
    obj(co, "ЭП_спираль", coll, [m["coil"]], r, smooth=80)
    kn = bmesh.new()
    lathe(kn, [(0, 0), (0.016, 0), (0.016, 0.016), (0.013, 0.02), (0, 0.02)], segs=20, origin=(0.07, -s / 2, 0.04), axis=(0, -1, 0))
    set_mat(L.bm_box(kn, (0.068, -s / 2 - 0.022, 0.035), (0.072, -s / 2 - 0.019, 0.058)), 0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.bm_cyl(kn, (sx * 0.1, sy * 0.1, 0.0), (sx * 0.1, sy * 0.1, 0.013), 0.009, segs=12)
    pipe(kn, [(0.0, s / 2, 0.03), (0.0, s / 2 + 0.03, 0.03), (0.04, s / 2 + 0.1, 0.006), (0.1, s / 2 + 0.25, 0.006),
              (0.02, s / 2 + 0.38, 0.006)], 0.0035, segs=8, bend=0.05)
    L.bm_box(kn, (0.0, s / 2 + 0.38, 0.0), (0.05, s / 2 + 0.41, 0.022))
    for dx in (0.015, 0.035):
        L.bm_cyl(kn, (dx, s / 2 + 0.41, 0.011), (dx, s / 2 + 0.43, 0.011), 0.002, segs=8)
    obj(kn, "ЭП_ручка_шнур", coll, [m["plastic"]], r, smooth=50)
    return r


# ---------------------------------------------------------------- сборка файла

ITEMS = [
    ("Кровать двухъярусная", bunk_bed, 0.9), ("Кровать одноярусная", single_bed, 0.9), ("Матрас ватный", mattress, 0.8),
    ("Тумбочка", nightstand, 0.4), ("Шкаф с антресолью", wardrobe, 1.0), ("Стол", table, 1.0), ("Стул", chair, 0.45),
    ("Табурет", stool, 0.32), ("Полка навесная", wall_shelf, 0.8), ("Холодильник", fridge, 0.48), ("Диван-книжка", sofa, 1.9),
    ("Ковёр на стену", carpet, 1.5), ("Телевизор", tv, 0.58), ("Плитка электрическая", hotplate, 0.25),
]


def studio(coll, span: float) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.get("Студия") or bpy.data.worlds.new("Студия")
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.32, 0.34, 0.37, 1.0)
    bg.inputs[1].default_value = 0.5
    sc.world = world
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, -3.0, -0.02), (span + 1.0, 2.5, 0.0))
    L.finish_bm(bm, "студия_пол", coll, L.material("Студия_пол", (0.22, 0.21, 0.2), 0.9))
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, 1.4, 0.0), (span + 1.0, 1.45, 2.8))
    L.finish_bm(bm, "студия_стена", coll, L.material("Студия_стена", (0.45, 0.45, 0.43), 0.9))
    for i, (x, e) in enumerate(((span * 0.25, 600), (span * 0.75, 600), (span * 0.5, 300))):
        ld = bpy.data.lights.new(f"Студия_свет_{i}", "AREA")
        ld.energy = e
        ld.size = 4.0
        lo = bpy.data.objects.new(f"Студия_свет_{i}", ld)
        lo.location = (x, -2.5 if i < 2 else 0.5, 3.0)
        lo.rotation_euler = (math.radians(40 if i < 2 else 0), 0, 0)
        coll.objects.link(lo)
    cd = bpy.data.cameras.new("Камера_обзор")
    cd.lens = 28
    co = bpy.data.objects.new("Камера_обзор", cd)
    co.location = (span / 2, -span * 0.55, 3.2)
    co.rotation_euler = (V((span / 2, 0.0, 0.6)) - V(co.location)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(co)
    sc.camera = co


def build(out: str) -> list:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Мебель_комнаты_v01")
    m = mats()
    rng = random.Random(31)
    x = 0.0
    placed = []
    for label, fn, width in ITEMS:
        c = L.collection(label, top)
        cx = x + width / 2
        at = (cx, 0.0, 0.0)
        if fn is wall_shelf:
            at = (cx, 1.4, 1.6)
        elif fn is carpet:
            at = (cx, 1.4, 0.45)
        root = fn(c, m, at, rng)
        placed.append((label, c, root))
        x += width + 0.45
    studio(L.collection("Студия"), x)
    # файл открывается сразу со светом студии
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)
    return placed


def preview(placed: list, folder: str, only: set | None = None, views=((-35, 22), (40, 38)), zoom: float = 1.35) -> None:
    """Кадры для самопроверки: каждый предмет 3/4 спереди слева и сверху справа (Eevee); стена студии — только
    у полки и ковра."""
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    sc.render.film_transparent = False
    cam = sc.camera
    wall = bpy.data.objects.get("студия_стена")
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (label, coll, root) in enumerate(placed):
        if only and i not in only:
            continue
        if wall:
            wall.hide_render = label not in ("Полка навесная", "Ковёр на стену")
        pts = []
        for ob in coll.objects:
            if ob.type == "MESH" and not ob.hide_render:
                ev = ob.evaluated_get(dg)
                pts += [ev.matrix_world @ V(c) for c in ev.bound_box]
        mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn + mx) / 2
        size = (mx - mn).length
        for k, (az, el) in enumerate(views):
            a, e = math.radians(az), math.radians(el)
            dist = size * zoom + 0.25
            cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = 40
            sc.render.filepath = os.path.join(folder, f"{i:02d}_{k}.png")
            bpy.ops.render.render(write_still=True)
            print("preview", label, k)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed = build(argv[0])
    if len(argv) >= 3 and argv[1] == "preview":
        # -- <файл> preview <папка> [номера через запятую] [ракурсы «аз:угол;…»] [приближение]
        only = {int(s) for s in argv[3].split(",")} if len(argv) >= 4 and argv[3] else None
        views = [tuple(float(x) for x in s.split(":")) for s in argv[4].split(";")] if len(argv) >= 5 else ((-35, 22), (40, 38))
        preview(placed, argv[2], only, views, float(argv[5]) if len(argv) >= 6 else 1.35)
        if wall := bpy.data.objects.get("студия_стена"):
            wall.hide_render = False
