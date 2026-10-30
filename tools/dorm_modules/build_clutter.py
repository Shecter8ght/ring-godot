"""Мусор общежития, партия 1 — форма для просмотра владельцем: банки из-под пива, бутылки, окурки и пачка, гильзы.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_clutter.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Clutter/models/RING_Dorm_Clutter_v01.blend"

Размеры — настоящих вещей (мм): банка 0,5 л — Ø66,2 × 168, крышка «202» Ø52 с язычком; бутылка водочная 0,5 л —
Ø74 × 268, винтовая алюминиевая пробка Ø31 × 20; пивная «евро» 0,5 л — Ø70 × 250, кроненпробка Ø32; разбитая — горлышко
с рваным краем и осколки 3 мм; окурок — фильтр Ø7,8 × 21 в ободке (четверть — белые без ободка), бумага 4–13 мм,
затушенный конец смят и сплющен, рваный нагар 2–3,5 мм, табак внутри; пачка мягкая 56 × 88 × 22 плашмя (мнёт
crush_sim.py); гильзы — 5,45×39 (39,4, фланец Ø10,0, дульце Ø6,3), 7,62×39 (38,7, Ø11,35, дульце Ø8,6), 9×18 (18,1, Ø9,9).
Окурки и гильзы рассыпаны случайно, но не друг в друге.
Стекло и банки — полые (стенка 0,1 мм у банки, 3 мм у стекла), гильзы — полые с донцем и капсюлем. Корень — точка
опоры на полу, Z вверх. Мятые, раздавленные и разбитые — геометрией. Материалы — нейтральные слоты; текстуры
после принятия формы.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_found_lights as F  # noqa: E402
import mlib as L  # noqa: E402

V = Vector
TAU = 2 * math.pi


def mats() -> dict:
    return {
        "can": L.material("Банка_алюминий", (0.75, 0.75, 0.76), 0.25, 1.0),
        "can_dark": L.material("Банка_отверстие", (0.02, 0.02, 0.02), 0.6),
        "glass_clear": L.material("Стекло_бутылка_прозрачное", (0.85, 0.9, 0.88), 0.03, 0.0, 0.25),
        "glass_brown": L.material("Стекло_бутылка_коричневое", (0.25, 0.12, 0.03), 0.03, 0.0, 0.5),
        "cap_alu": L.material("Пробка_алюминий", (0.7, 0.7, 0.72), 0.3, 1.0),
        "cap_crown": L.material("Пробка_кроненпробка", (0.55, 0.5, 0.4), 0.3, 1.0),
        "filter": L.material("Окурок_ободок", (0.8, 0.55, 0.3), 0.7),
        "paper": L.material("Окурок_бумага", (0.85, 0.83, 0.78), 0.8),
        "filter_face": L.material("Окурок_фильтр", (0.88, 0.86, 0.8), 0.9),
        "ash": L.material("Окурок_нагар", (0.06, 0.05, 0.045), 0.95),
        "tobacco": L.material("Окурок_табак", (0.16, 0.09, 0.04), 0.95),
        "pack": L.material("Пачка_бумага", (0.75, 0.7, 0.6), 0.75),
        "brass": L.material("Гильза_латунь", (0.78, 0.6, 0.3), 0.3, 1.0),
        "steel_lac": L.material("Гильза_сталь_лак", (0.35, 0.3, 0.18), 0.35, 1.0),
        "primer": L.material("Гильза_капсюль", (0.7, 0.55, 0.35), 0.3, 1.0),
    }


def part(bm, name, coll, mat, parent, smooth=40.0, bevel=0.0):
    return L.finish_bm(bm, name, coll, mat, parent, bevel=bevel, segs=1, angle=40, smooth_angle=smooth)


# ---------------------------------------------------------------- банка

CAN_PROF = [(0.0, 0.0095), (0.010, 0.0090), (0.018, 0.0065), (0.0245, 0.0018), (0.0262, 0.0), (0.0282, 0.0012),
            (0.0310, 0.0050), (0.0331, 0.0120), (0.0331, 0.1500), (0.0322, 0.1540), (0.0300, 0.1590), (0.0274, 0.1630),
            (0.0263, 0.1650), (0.0268, 0.1668), (0.0263, 0.1680), (0.0256, 0.1672), (0.0256, 0.1635), (0.0247, 0.1628),
            (0.0, 0.1628)]


def can_mesh(bm, crush: float = 0.0, seed: int = 1, segs: int = 48) -> None:
    """Банка 0,5 л; crush 0…1 — раздавлена ногой: ниже, крышка набок, складки по кругу и вмятины."""
    rnd = random.Random(seed)
    F.lathe(bm, CAN_PROF, segs)
    if crush <= 0:
        return
    lobes = rnd.choice((5, 6, 7))
    ph = rnd.uniform(0, TAU)
    tilt = rnd.uniform(0.25, 0.5) * crush
    dents = [(rnd.uniform(0, TAU), rnd.uniform(0.04, 0.13), rnd.uniform(0.004, 0.009)) for _ in range(4)]
    for v in bm.verts:
        x, y, z = v.co
        r = math.hypot(x, y)
        a = math.atan2(y, x)
        t = min(max(z / 0.168, 0.0), 1.0)
        body = math.sin(math.pi * min(max((z - 0.012) / 0.14, 0.0), 1.0))  # только стенка, не дно и не крышка
        # гармошка: стенка складывается внутрь лепестками, высота ужимается
        fold = math.sin(lobes * a + ph + 9.0 * t) * 0.5 + 0.5
        r2 = r * (1.0 - crush * body * (0.22 + 0.28 * fold))
        z2 = z * (1.0 - 0.62 * crush * (0.6 + 0.4 * t)) + crush * body * 0.006 * math.sin(14.0 * t + lobes * a)
        for da, dz, depth in dents:
            d = math.exp(-((math.atan2(math.sin(a - da), math.cos(a - da)) / 0.5) ** 2 + ((z - dz) / 0.02) ** 2))
            r2 -= crush * depth * d * (r / 0.033)
        if r > 1e-6:
            x, y = x * r2 / r, y * r2 / r
        # крышку уводит набок
        x += tilt * (z2 - 0.0) * 0.6
        v.co = V((x, y, z2))


def can(coll, m, at, name, crush=0.0, lying=False, seed=1) -> bpy.types.Object:
    r = L.root(name, coll, at)
    bm = bmesh.new()
    can_mesh(bm, crush, seed)
    # язычок отогнут вверх и отверстие — на крышке (у раздавленной не видно — остаются как есть, со смещением формы)
    top = 0.1628 * (1.0 - 0.62 * crush) if crush else 0.1628
    if not crush:
        tab = bmesh.new()
        ring = [(0.0, 0.0), (0.0085, 0.0), (0.0105, 0.004), (0.0105, 0.009), (0.0085, 0.0125), (0.0, 0.0125)]
        L.bm_prism(tab, [(p[0] - 0.005, p[1] - 0.009) for p in ring], (0, 0, top + 0.0006), (1, 0, 0), (0, 1, 0), (0, 0, 0.0005))
        L.transform(tab, tab.verts, Matrix.Translation((0, -0.004, top)) @ Matrix.Rotation(math.radians(28), 4, "X")
                    @ Matrix.Translation((0, 0.004, -top)))
        bm2 = bmesh.new()
        tmp = bpy.data.meshes.new("tmp")
        tab.to_mesh(tmp)
        tab.free()
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
        bm2.free()
    body = part(bm, name + "_банка", coll, m["can"], r, smooth=50)
    if not crush:
        bm = bmesh.new()
        hole = [(0.012 * math.cos(t) * 0.55, 0.012 + 0.009 * math.sin(t)) for t in [TAU * i / 20 for i in range(20)]]
        L.bm_prism(bm, hole, (0, 0, top + 0.0001), (1, 0, 0), (0, 1, 0), (0, 0, 0.0002))
        part(bm, name + "_отверстие", coll, m["can_dark"], r)
    if lying:
        r.rotation_euler = (math.radians(90), 0, math.radians(30))
        r.location.z += 0.0331
    return r


# ---------------------------------------------------------------- бутылки

def bottle_profile(kind: str) -> list:
    """Внешний профиль снизу вверх и внутренний сверху вниз (стенка 3 мм, дно с выпуклостью)."""
    if kind == "vodka":
        outer = [(0.0, 0.006), (0.028, 0.004), (0.0345, 0.0), (0.0370, 0.004), (0.0370, 0.180), (0.0350, 0.195),
                 (0.0280, 0.210), (0.0170, 0.225), (0.0150, 0.235), (0.0150, 0.268)]
    else:
        outer = [(0.0, 0.006), (0.026, 0.004), (0.0330, 0.0), (0.0350, 0.004), (0.0350, 0.150), (0.0330, 0.168),
                 (0.0240, 0.192), (0.0140, 0.215), (0.0130, 0.235), (0.0145, 0.240), (0.0145, 0.246), (0.0130, 0.250)]
    inner = []
    for r, z in reversed(outer[1:]):
        inner.append((max(r - 0.003, 0.0085 if z > 0.2 else 0.0), max(z, 0.010)))
    inner = [(0.0090, outer[-1][1])] + inner[1:]
    return outer + inner + [(0.0, 0.012)]


def bottle(coll, m, at, name, kind="vodka", lying=False) -> bpy.types.Object:
    r = L.root(name, coll, at)
    bm = bmesh.new()
    F.lathe(bm, bottle_profile(kind), 48)
    part(bm, name + "_стекло", coll, m["glass_clear" if kind == "vodka" else "glass_brown"], r, smooth=50)
    bm = bmesh.new()
    if kind == "vodka":
        # винтовая алюминиевая пробка с кольцом контроля вскрытия; рифление — текстурой
        F.lathe(bm, [(0.0, 0.2505), (0.0158, 0.2505), (0.0158, 0.2560), (0.0152, 0.2566), (0.0158, 0.2572),
                     (0.0158, 0.2700), (0.0150, 0.2715), (0.0, 0.2718)], 32)
        part(bm, name + "_пробка", coll, m["cap_alu"], r, bevel=0.0003)
    else:
        prof = [(0.0, 0.2445), (0.0160, 0.2445), (0.0165, 0.2470), (0.0, 0.2480)]
        F.lathe(bm, prof, 21)
        for v in bm.verts:  # 21 зубец кроненпробки
            a = math.atan2(v.co.y, v.co.x)
            rr = math.hypot(v.co.x, v.co.y)
            if rr > 0.015:
                k = 1.0 + 0.04 * math.cos(21 * a)
                v.co.x *= k
                v.co.y *= k
        part(bm, name + "_пробка", coll, m["cap_crown"], r)
    if lying:
        r.rotation_euler = (math.radians(90), 0, math.radians(-20))
        r.location.z += 0.037 if kind == "vodka" else 0.035
    return r


def broken_bottle(coll, m, at, name, seed=3) -> bpy.types.Object:
    """Разбитая пивная: горлышко с рваным краем лежит на боку, рядом осколки."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    prof = bottle_profile("beer")
    bm = bmesh.new()
    F.lathe(bm, prof, 48)
    # рвём по зубчатой линии: всё ниже cut(угол) удаляем
    cuts = [0.13 + 0.05 * rnd.random() for _ in range(9)]

    def cut(a):
        k = (a % TAU) / TAU * 9
        i = int(k)
        f = k - i
        return cuts[i % 9] * (1 - f) + cuts[(i + 1) % 9] * f
    gone = [v for v in bm.verts if v.co.z < cut(math.atan2(v.co.y, v.co.x))]
    bmesh.ops.delete(bm, geom=gone, context="VERTS")
    # рваный край — открытые петли стенки: закрываем мостиком наружной и внутренней кромки
    edges = [e for e in bm.edges if e.is_boundary]
    try:
        bmesh.ops.bridge_loops(bm, edges=edges)
    except Exception:  # noqa: BLE001
        pass
    L.transform(bm, bm.verts, Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Translation((0, 0, -0.13)))
    L.transform(bm, bm.verts, Matrix.Translation((0, 0, 0.0335)))
    part(bm, name + "_горлышко", coll, m["glass_brown"], r, smooth=50)
    bm = bmesh.new()
    for k in range(7):
        n = rnd.randint(5, 8)
        size = rnd.uniform(0.012, 0.035)
        pts = []
        for i in range(n):
            a = TAU * i / n + rnd.uniform(-0.25, 0.25)
            rr = size * rnd.uniform(0.55, 1.0)
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        cx, cy = rnd.uniform(-0.12, 0.12), rnd.uniform(-0.06, 0.12)
        fs = L.bm_prism(bm, pts, (cx, cy, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 0.003))
        vs = {v for f in fs for v in f.verts}
        ang = rnd.uniform(0, TAU)
        L.transform(bm, vs, Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(ang, 4, "Z") @ Matrix.Translation((-cx, -cy, 0)))
        # осколок изогнут по стенке бутылки
        for v in vs:
            v.co.z += ((v.co.x - cx) ** 2) * 4.0
    part(bm, name + "_осколки", coll, m["glass_brown"], r, smooth=30)
    return r


# ---------------------------------------------------------------- окурки и пачка

def _noise_ring(rnd, segs: int, harm: int = 4) -> list:
    """Плавная случайная кривая по кругу (несколько гармоник) — рваный обгоревший край, неровное сжатие."""
    ks = [(rnd.uniform(0.3, 1.0) / (h + 1), rnd.uniform(0, TAU)) for h in range(harm)]
    vals = [sum(amp * math.sin((h + 1) * TAU * i / segs + ph) for h, (amp, ph) in enumerate(ks)) for i in range(segs)]
    m = max(abs(v) for v in vals) or 1.0
    return [v / m for v in vals]


def butt(bms: dict, seed: int, burnt: float, bend: float, squash: float, flat_end: float, white_filter: bool) -> None:
    """Окурок вдоль +X, мундштук в начале координат: фильтр 21 мм в ободке (или белый без ободка), бумага burnt мм.
    Затушен: последние 4 мм сжаты неровно, смяты и сплющены (flat_end — доля толщины), край обгорел рваной
    полосой 2–3,5 мм, табак внутри утоплен. bend — изгиб конца, рад (в плоскости пола), squash — раздавлен целиком (доля высоты).
    Куски — в bms по материалам."""
    rnd = random.Random(seed)
    segs = 24
    r0 = 0.0039
    length = 0.021 + burnt
    xs = [0.0, 0.0004]
    x = 0.0015
    while x < length - 0.004:
        xs.append(x)
        x += 0.0015
    xs += [length - 0.004 + 0.0005 * i for i in range(9)]
    ragged = _noise_ring(rnd, segs, 5)
    shrink = _noise_ring(rnd, segs, 3)
    char = rnd.uniform(0.002, 0.0035)
    rings = []
    for k, x in enumerate(xs):
        t = max(0.0, (x - (length - 0.004)) / 0.004)  # 0 … 1 на затушенном конце
        ring = []
        for i in range(segs):
            th = TAU * i / segs
            r = r0 * (0.86 if k == 0 else 1.0) * (1.0 - t * (0.18 + 0.12 * shrink[i]))
            r += t * rnd.uniform(-0.0005, 0.0003)  # бумага у затушенного конца смята
            y, z = r * math.cos(th), r * math.sin(th)
            y *= 1.0 + 0.35 * t * (1.0 - flat_end)  # придавлен о пол — расплющен вширь
            z *= 1.0 - t ** 1.5 * (1.0 - flat_end)
            xx = x - (0.002 * (0.5 + 0.5 * ragged[i]) if k == len(xs) - 1 else 0.0)
            ring.append(V((xx, y, z)))
        rings.append(ring)
    # центр торца мундштука чуть утоплен (волокна фильтра), в обгоревшем конце — табак
    mouth = V((0.0006, 0.0, 0.0))
    end = V((length - 0.0035, 0.0, 0.0))

    def deform(p: V) -> V:
        q = V(p)
        q.z *= squash
        q.y *= 1.0 + (1.0 - squash) * 0.6
        xb = length - 0.008  # изгиб: последние 8 мм — по дуге в плоскости пола
        if bend and q.x > xb:
            rc = 0.008 / bend
            s_ = q.x - xb
            q = V((xb + (rc - q.y) * math.sin(s_ / rc), rc - (rc - q.y) * math.cos(s_ / rc), q.z))
        return q

    def verts(bm, pts):
        return [bm.verts.new(deform(pt)) for pt in pts]

    def band(bm, ka, kb):
        prev = verts(bm, rings[ka])
        for kk in range(ka + 1, kb + 1):
            cur = verts(bm, rings[kk])
            for i in range(segs):
                j = (i + 1) % segs
                bm.faces.new((prev[i], prev[j], cur[j], cur[i]))
            prev = cur

    def fan(bm, ring_k, centre, flip):
        rv = verts(bm, rings[ring_k])
        c = bm.verts.new(deform(centre))
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((rv[j], rv[i], c) if not flip else (rv[i], rv[j], c))

    k_filter = max(k for k, x in enumerate(xs) if x <= 0.0211)
    k_char = max(min(k for k, x in enumerate(xs) if x >= length - char) - 1, k_filter + 1)
    wrap = bms["face" if white_filter else "filter"]
    band(wrap, 0, k_filter)
    band(bms["paper"], k_filter, k_char)
    band(bms["ash"], k_char, len(xs) - 1)
    fan(bms["face"], 0, mouth, False)
    fan(bms["tobacco"], len(xs) - 1, end, True)


def _seg_dist(p0: V, p1: V, q0: V, q1: V) -> float:
    """Расстояние между отрезками на полу (россыпь без пересечений)."""
    def pt_seg(pt, a, b):
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (pt - a).dot(ab) / ab.length_squared))
        return (a + ab * t - pt).length
    return min(pt_seg(p0, q0, q1), pt_seg(p1, q0, q1), pt_seg(q0, p0, p1), pt_seg(q1, p0, p1))


def butts(coll, m, at, name, count=9, seed=5) -> bpy.types.Object:
    """Россыпь окурков у пачки: случайная, но не друг в друге и не в пачке (проверка отрезками по полу)."""
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    keys = ("filter", "face", "paper", "ash", "tobacco")
    out = {k: bmesh.new() for k in keys}
    placed = [(V((0.21, 0.05, 0.0)), V((0.21, 0.05, 0.0)), 0.058)]  # пачка — круг вокруг её центра
    for k in range(count):
        one = {key: bmesh.new() for key in keys}
        burnt = rnd.uniform(0.004, 0.013)
        butt(one, seed * 31 + k, burnt, bend=rnd.choice((0.0, 0.0, 0.5, 0.9, 1.3)) * rnd.choice((1, -1)),
             squash=rnd.choice((1.0, 1.0, 1.0, 0.62)), flat_end=rnd.uniform(0.25, 0.55), white_filter=rnd.random() < 0.25)
        length = 0.021 + burnt
        for _ in range(400):
            a, rr = rnd.uniform(0, TAU), 0.16 * math.sqrt(rnd.random())
            p = V((rr * math.cos(a), rr * math.sin(a), 0.0))
            yaw = rnd.uniform(0, TAU)
            q = p + V((math.cos(yaw), math.sin(yaw), 0.0)) * length
            if all(_seg_dist(p, q, s0, s1) > rad + 0.0048 for s0, s1, rad in placed):
                break
        placed.append((p, q, 0.0048))
        low = min(v.co.z for bm in one.values() for v in bm.verts)  # окурок целиком низом на пол
        mtx = Matrix.Translation(p - V((0, 0, low))) @ Matrix.Rotation(yaw, 4, "Z")
        for key in keys:
            bm = one[key]
            L.transform(bm, bm.verts, mtx)
            tmp = bpy.data.meshes.new("tmp")
            bm.to_mesh(tmp)
            bm.free()
            out[key].from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
    part(out["filter"], name + "_фильтры", coll, m["filter"], r, smooth=70)
    part(out["face"], name + "_фильтр_белый", coll, m["filter_face"], r, smooth=70)
    part(out["paper"], name + "_бумага", coll, m["paper"], r, smooth=70)
    part(out["ash"], name + "_нагар", coll, m["ash"], r, smooth=70)
    part(out["tobacco"], name + "_табак", coll, m["tobacco"], r, smooth=70)
    bm = bmesh.new()
    soft_pack(bm, seed + 99)
    L.transform(bm, bm.verts, Matrix.Translation((0.21, 0.05, 0.0)) @ Matrix.Rotation(math.radians(20), 4, "Z"))
    part(bm, name + "_пачка", coll, m["pack"], r, smooth=50)
    return r


def soft_pack(bm, seed: int) -> None:
    """Пустая мягкая пачка 56 × 88 × 22 плашмя: края скруглены (бумага на фольге), примята до ~60 % толщины,
    крупные заломы по верху, лёгкое скручивание вдоль, у верхнего торца надорвана (рваный край, внутрь видно).
    Симуляция ткани плитой давала мелкий «гравий» по верху (пробы 2026-10-30) — заломы заданы явно."""
    rnd = random.Random(seed)
    hx, hy, hz = 0.028, 0.044, 0.011
    rad = 0.004
    L.bm_box(bm, (-hx, -hy, -hz), (hx, hy, hz))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=24, use_grid_fill=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    # заломы: (точка, направление, глубина, ширина, длина) — по верхней стороне
    creases = []
    for _ in range(3):
        a = rnd.uniform(0, math.pi)
        creases.append((V((rnd.uniform(-0.015, 0.015), rnd.uniform(-0.03, 0.03), 0)), V((math.cos(a), math.sin(a), 0)),
                        rnd.uniform(0.0025, 0.0045), rnd.uniform(0.003, 0.006), rnd.uniform(0.03, 0.06)))
    twist = rnd.uniform(0.08, 0.16) * rnd.choice((1, -1))
    for v in bm.verts:
        p = V(v.co)
        # скруглённые рёбра: точка ложится на поверхность бруска со скруглением rad
        inner = V((max(-hx + rad, min(hx - rad, p.x)), max(-hy + rad, min(hy - rad, p.y)), max(-hz + rad, min(hz - rad, p.z))))
        d = p - inner
        if d.length > 1e-9:
            p = inner + d.normalized() * rad
        # пустая — примята: середина тоньше краёв
        edge = min(hx - abs(p.x), hy - abs(p.y))
        p.z *= 0.5 + 0.25 * max(0.0, 1.0 - edge / 0.012)
        if p.z > 0:
            for c, dirv, depth, w, ln in creases:
                rel = p - c
                along = rel.dot(dirv)
                across = abs(rel.x * dirv.y - rel.y * dirv.x)
                fade = max(0.0, 1.0 - abs(along) / (ln / 2)) ** 0.5
                p.z -= depth * max(0.0, 1.0 - across / w) ** 1.6 * fade * (p.z / hz)
        # скручено вдоль длины
        ang = twist * p.y / hy
        p = V((p.x * math.cos(ang) - p.z * math.sin(ang), p.y, p.x * math.sin(ang) + p.z * math.cos(ang)))
        v.co = p
    # надрыв у верхнего торца: вырван угол верхней стороны и торца, край рваный
    torn = [f for f in bm.faces if f.calc_center_median().y > hy - 0.011 + 0.004 * math.sin(f.calc_center_median().x * 160)
            and f.calc_center_median().x < -0.004 and f.calc_center_median().z > -0.002]
    bmesh.ops.delete(bm, geom=torn, context="FACES")
    for v in bm.verts:
        if v.is_boundary:
            v.co.y += rnd.uniform(-0.0012, 0.0012)
            v.co.z += rnd.uniform(-0.0004, 0.0004)
    low = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= low


# ---------------------------------------------------------------- гильзы

CASES = {
    # внешний профиль от донца до дульца (r, z), мм → м; внутренний — стенка 0,3 мм у дульца
    "545": [(0.0, 0.0), (0.0050, 0.0), (0.0050, 0.0014), (0.0041, 0.0019), (0.0041, 0.0027), (0.0050, 0.0035),
            (0.0049, 0.0280), (0.0045, 0.0322), (0.0032, 0.0335), (0.0032, 0.0394)],
    "762": [(0.0, 0.0), (0.0056, 0.0), (0.0056, 0.0015), (0.0046, 0.0021), (0.0046, 0.0030), (0.0056, 0.0038),
            (0.0053, 0.0305), (0.0049, 0.0322), (0.0043, 0.0330), (0.0043, 0.0387)],
    "918": [(0.0, 0.0), (0.0050, 0.0), (0.0050, 0.0012), (0.0043, 0.0016), (0.0043, 0.0023), (0.0050, 0.0030),
            (0.0049, 0.0181)],
}


def case_profile(kind: str) -> list:
    out = [(r, z) for r, z in CASES[kind]]
    top = out[-1]
    inner = [(top[0] - 0.0003, top[1])] + [(max(r - 0.0003, 0.0005), z) for r, z in reversed(out[3:-1]) if z > 0.004]
    return out + inner + [(0.0018, 0.0042), (0.0, 0.0042)]


def casings(coll, m, at, name, kinds=("545",) * 9 + ("762",) * 3 + ("918",) * 3, seed=7) -> bpy.types.Object:
    rnd = random.Random(seed)
    r = L.root(name, coll, at)
    bm_b, bm_s, bm_p = bmesh.new(), bmesh.new(), bmesh.new()
    placed = []
    for k, kind in enumerate(kinds):
        bm = bm_s if kind in ("545", "762") else bm_b
        before = set(bm.verts)
        F.lathe(bm, case_profile(kind), 24)
        new = [v for v in bm.verts if v not in before]
        before_p = set(bm_p.verts)
        F.lathe(bm_p, [(0.0, -0.0001), (0.0022 if kind != "918" else 0.0019, -0.0001), (0.0022 if kind != "918" else 0.0019, 0.0003), (0.0, 0.0003)], 16)
        new_p = [v for v in bm_p.verts if v not in before_p]
        rad = 0.0050 if kind != "762" else 0.0056
        length = CASES[kind][-1][1]
        for _ in range(400):  # не друг в друге: отрезки осей по полу дальше суммы радиусов
            a = rnd.uniform(0, TAU)
            rr = rnd.uniform(0.0, 0.45)
            yaw = rnd.uniform(0, TAU)
            c = V((rr * math.cos(a), rr * math.sin(a), 0.0))
            d = V((math.cos(yaw), math.sin(yaw), 0.0)) * (length / 2)
            if all(_seg_dist(c - d, c + d, p0, p1) > rad + pr + 0.001 for p0, p1, pr in placed):
                break
        placed.append((c - d, c + d, rad))
        mtx = (Matrix.Translation((c.x, c.y, rad)) @ Matrix.Rotation(yaw, 4, "Z")
               @ Matrix.Rotation(math.radians(90), 4, "Y") @ Matrix.Translation((0, 0, -length / 2)))
        L.transform(bm, new, mtx)
        L.transform(bm_p, new_p, mtx)
    part(bm_s, name + "_сталь", coll, m["steel_lac"], r, smooth=40)
    part(bm_b, name + "_латунь", coll, m["brass"], r, smooth=40)
    part(bm_p, name + "_капсюли", coll, m["primer"], r)
    return r


# ---------------------------------------------------------------- сборка

def build(out: str) -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Мусор_партия1_v01")
    m = mats()
    c = L.collection("банки", top)
    can(c, m, (0.0, 0.0, 0.0), "CL_банка_целая")
    can(c, m, (0.12, 0.05, 0.0), "CL_банка_лежит", lying=True)
    can(c, m, (0.26, 0.0, 0.0), "CL_банка_мятая", crush=0.7, seed=2)
    can(c, m, (0.38, 0.02, 0.0), "CL_банка_раздавлена", crush=1.0, seed=5)
    c = L.collection("бутылки", top)
    bottle(c, m, (0.62, 0.0, 0.0), "CL_бутылка_водка", "vodka")
    bottle(c, m, (0.76, 0.0, 0.0), "CL_бутылка_пиво", "beer")
    bottle(c, m, (0.95, 0.06, 0.0), "CL_бутылка_водка_лежит", "vodka", lying=True)
    broken_bottle(c, m, (1.30, 0.0, 0.0), "CL_бутылка_разбита")
    c = L.collection("окурки", top)
    butts(c, m, (1.75, 0.0, 0.0), "CL_окурки")
    c = L.collection("гильзы", top)
    casings(c, m, (2.35, 0.0, 0.0), "CL_гильзы")
    F.studio(L.collection("Студия"))
    sc = bpy.context.scene
    cam = sc.camera
    cam.location = (1.15, -2.1, 0.9)
    cam.rotation_euler = (V((1.15, 0.0, 0.05)) - V(cam.location)).to_track_quat("-Z", "Y").to_euler()
    floor = bpy.data.objects.get("студия_пол")
    if floor:
        floor.scale = (2.4, 1.0, 1.0)
        floor.location = (1.1, 0, 0)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build(argv[0])
