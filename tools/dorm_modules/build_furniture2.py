"""Мебель общежития, партия 2 (кухня, умывальня, туалеты) — форма для просмотра владельцем.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_furniture2.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture/models/RING_Dorm_Furniture2_v01.blend" [preview <папка> [номера]]

Интервью владельца 2026-11-02: кухня — электроплиты, чугунная мойка и разделочные столы-тумбы, общий стол, табуреты
(табурет — из партии 1), навесные шкафчики и полки, посуда и баки; умывальня — отдельные фаянсовые раковины на
кронштейнах, у каждой свой кран; туалеты — унитазы с высоким чугунным бачком и цепочкой, кабинки; состояние —
вперемешку: в основном целое, кое-где отбитая раковина, сорванный бачок, распахнутая дверца духовки, выбитая дверца
кабинки (отдельные корни-варианты). Высоты — по СНиП 3.05.01-85: раковина 800 мм до борта, мойка 850, низ
высокорасположенного бачка 1800, борт унитаза 400. Размеры, мм: плита 500 × 600 × 850 (четыре конфорки Ø180 / Ø145,
духовка); мойка чугунная 800 × 600 на тумбе; стол-тумба 800 × 600 × 850; обеденный стол 1200 × 800 × 750;
шкафчик навесной 800 × 300 × 600; полка для посуды 800 × 250 × 500; раковина 550 × 450; зеркало 400 × 600;
унитаз 360 × 520, бачок 400 × 170 × 300; кабинка — перегородка 1200 × 1800 на ножках 150, дверца 700 × 1650.
Корень — середина опоры на полу, Z вверх, лицо к −Y; навесное (шкафчик, полка, зеркало) — середина верха у стены;
то, что крепится к стене (раковина, унитаз с бачком), — на полу у стены: стена — плоскость y = 0, предмет — в −Y.
Материалы — нейтральные слоты по будущим отделкам.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_furniture as B  # noqa: E402
import mlib as L  # noqa: E402
from build_found_lights import lathe  # noqa: E402

V = Vector
TAU = 2 * math.pi
board, pipe, rounded_box, cut, set_mat, obj, bow_handle = B.board, B.pipe, B.rounded_box, B.cut, B.set_mat, B.obj, B.bow_handle


def mats() -> dict:
    m = B.mats()
    m.update({
        "faience": L.material("Фаянс", (0.82, 0.82, 0.79), 0.12),
        "cast_iron": L.material("Чугун_окраска", (0.18, 0.18, 0.17), 0.55, 0.3),
        "sink_enamel": L.material("Мойка_эмаль", (0.85, 0.85, 0.82), 0.15),
        "stove_enamel": L.material("Плита_эмаль", (0.84, 0.83, 0.78), 0.2),
        "burner": L.material("Конфорка_чугун", (0.06, 0.06, 0.06), 0.6, 0.6),
        "steel_paint": L.material("Сталь_окраска", (0.2, 0.22, 0.22), 0.45),
        "top_laminate": L.material("Пластик_столешница", (0.62, 0.6, 0.55), 0.3),
        "aluminium": L.material("Алюминий", (0.72, 0.72, 0.7), 0.35, 1.0),
        "seat": L.material("Сиденье_пластик", (0.03, 0.03, 0.03), 0.4),
        "pot_enamel": L.material("Посуда_эмаль", (0.55, 0.62, 0.55), 0.2),
        "galvanized": L.material("Оцинковка", (0.6, 0.6, 0.58), 0.4, 1.0),
        "partition": L.material("Перегородка_краска", (0.42, 0.5, 0.45), 0.45),
        "mirror": L.material("Зеркало", (0.9, 0.9, 0.9), 0.02, 1.0),
        "pipe_paint": L.material("Труба_краска", (0.75, 0.75, 0.72), 0.4),
        "chain": L.material("Цепочка_сталь", (0.45, 0.43, 0.4), 0.4, 1.0),
        "oven": L.material("Духовка_эмаль", (0.05, 0.05, 0.055), 0.35),
    })
    return m


def subsurf(ob, levels: int = 2) -> None:
    """Литой фаянс и чугун — гладкой поверхностью подразделения (модификатор не применён)."""
    md = ob.modifiers.new("Гладкость", "SUBSURF")
    md.levels = 1
    md.render_levels = levels
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    for p in ob.data.polygons:
        p.use_smooth = True


# ---------------------------------------------------------------- лофт по сечениям (фаянс, мойка)

def superellipse(a: float, b: float, cx: float, cy: float, p: float, n: int, back: float | None = None) -> list:
    """Точки сечения: суперэллипс a × b (полуоси) с показателем p вокруг (cx, cy); back — срез по стене y ≤ back."""
    pts = []
    for i in range(n):
        t = TAU * i / n - math.pi / 2
        c, s = math.cos(t), math.sin(t)
        x = cx + a * math.copysign(abs(c) ** (2 / p), c)
        y = cy + b * math.copysign(abs(s) ** (2 / p), s)
        if back is not None:
            y = min(y, back)
        pts.append((x, y))
    return pts


def loft(bm, rings: list, cap_first: bool = False, cap_last: bool = False) -> list:
    """Кольца [(z, [(x, y)…])…] с одинаковым числом точек → поверхность по порядку колец."""
    vr = [[bm.verts.new((x, y, z)) for x, y in pts] for z, pts in rings]
    n = len(vr[0])
    faces = []
    for r0, r1 in zip(vr[:-1], vr[1:]):
        for k in range(n):
            j = (k + 1) % n
            faces.append(bm.faces.new((r0[k], r0[j], r1[j], r1[k])))
    if cap_first:
        faces.append(bm.faces.new(vr[0][::-1]))
    if cap_last:
        faces.append(bm.faces.new(vr[-1]))
    return faces


def jagged_cutter(center, size, rng: random.Random, n: int = 26) -> bmesh.types.BMesh:
    """Резец скола: выпуклая оболочка случайных точек вокруг center (рваный край отбитого фаянса)."""
    bm = bmesh.new()
    c = V(center)
    for _ in range(n):
        d = V((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if d.length > 1e-6:
            d.normalize()
        bm.verts.new(c + V((d.x * size[0], d.y * size[1], d.z * size[2])) * rng.uniform(0.75, 1.0))
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    return bm


# ---------------------------------------------------------------- умывальня

def washbasin(coll, m, at, rng, broken: bool = False) -> bpy.types.Object:
    """Раковина 550 × 450 на чугунных кронштейнах: борт на 800, задняя полка с краном, сток и сифон в стену."""
    r = L.root("РК_раковина_отбита" if broken else "РК_раковина", coll, at)
    n = 64
    top = 0.80
    out = [(0.615, 0.12, 0.10, -0.17, 2.4), (0.64, 0.19, 0.16, -0.19, 2.6), (0.70, 0.245, 0.215, -0.205, 2.8),
           (0.765, 0.272, 0.245, -0.21, 3.0), (top, 0.275, 0.25, -0.20, 3.0)]
    rings = [(z, superellipse(a, b, 0, cy, p, n, back=0.0)) for z, a, b, cy, p in out]
    # борт: от наружной кромки — плоский верх к чаше; задняя полка шире (кран), чаша смещена вперёд
    inn = [(top + 0.004, 0.24, 0.165, -0.265, 3.2), (top - 0.012, 0.228, 0.15, -0.268, 3.0), (0.75, 0.19, 0.12, -0.27, 2.6),
           (0.70, 0.11, 0.075, -0.27, 2.2), (0.682, 0.022, 0.022, -0.27, 2.0)]
    rings += [(z, superellipse(a, b, 0, cy, p, n)) for z, a, b, cy, p in inn]
    bm = bmesh.new()
    set_mat(loft(bm, rings, cap_first=True), 0)
    body = obj(bm, "РК_чаша", coll, [m["faience"]], r)
    subsurf(body)
    if broken:
        cut(body, coll, r, "РК_скол", jagged_cutter((-0.27, -0.42, 0.79), (0.13, 0.11, 0.09), rng))
    # кран-вентиль на задней полке: корпус, излив, маховик-крестовина
    tb = bmesh.new()
    y0 = -0.055
    lathe(tb, [(0, 0), (0.022, 0), (0.022, 0.006), (0.012, 0.012), (0.011, 0.07), (0.014, 0.085), (0.0, 0.09)], segs=24,
          origin=(0, y0, top + 0.004))
    pipe(tb, [(0, y0, top + 0.06), (0, y0 - 0.05, top + 0.065), (0, y0 - 0.11, top + 0.05), (0, y0 - 0.125, top + 0.025)],
         0.008, segs=14, bend=0.03)
    L.bm_cyl(tb, (0, y0, top + 0.09), (0, y0, top + 0.105), 0.006, segs=12)
    for k in range(4):
        a = TAU * k / 4 + math.pi / 4
        pipe(tb, [(0, y0, top + 0.105), (0.03 * math.cos(a), y0 + 0.03 * math.sin(a), top + 0.108)], 0.0045, segs=10)
        L.bm_sphere(tb, (0.032 * math.cos(a), y0 + 0.032 * math.sin(a), top + 0.108), 0.007, segs=12, rings=6)
    obj(tb, "РК_кран", coll, [m["chrome"]], r, smooth=60)
    # выпуск, сифон-бутылка, отвод в стену
    sb = bmesh.new()
    L.bm_cyl(sb, (0, -0.27, 0.69), (0, -0.27, 0.56), 0.016, segs=16)
    lathe(sb, [(0, 0), (0.028, 0), (0.03, 0.01), (0.03, 0.11), (0.024, 0.12), (0, 0.12)], segs=24, origin=(0, -0.27, 0.45))
    pipe(sb, [(0, -0.27, 0.53), (0, -0.2, 0.53), (0, -0.02, 0.53), (0, 0.0, 0.53)], 0.016, segs=16, bend=0.03)
    lathe(sb, [(0.0, 0.0), (0.03, 0.0), (0.03, 0.006), (0.0, 0.006)], segs=24, origin=(0, -0.006, 0.53), axis=(0, 1, 0))
    obj(sb, "РК_сифон", coll, [m["chrome"]], r, smooth=60)
    # кронштейны: литые угольники с косынкой, на двух шурупах в стену
    kb = bmesh.new()
    for sx in (-1, 1):
        x = sx * 0.17
        prof = [(0.0, 0.0), (-0.25, 0.0), (-0.25, -0.018), (-0.03, -0.17), (0.0, -0.17)]
        L.bm_prism(kb, [(y, z) for y, z in prof], (x - 0.006, 0, 0.64), V((0, 1, 0)), V((0, 0, 1)), V((0.012, 0, 0)))
        for z in (0.6, 0.52):
            L.bm_cyl(kb, (x, -0.001, z), (x, -0.008, z), 0.009, segs=12)
    obj(kb, "РК_кронштейны", coll, [m["cast_iron"]], r, bevel=0.002, segs=1)
    return r


def mirror(coll, m, at, rng) -> bpy.types.Object:
    """Зеркало 400 × 600 на четырёх держателях; корень — середина верха у стены."""
    r = L.root("ЗР_зеркало", coll, at)
    w, h = 0.40, 0.60
    bm = bmesh.new()
    set_mat(L.bm_box(bm, (-w / 2, -0.009, -h), (w / 2, -0.004, 0.0)), 0)
    obj(bm, "ЗР_стекло", coll, [m["mirror"]], r, bevel=0.0015, segs=1)
    cb = bmesh.new()
    for x, z in ((-w / 2, -0.03), (w / 2, -0.03), (-w / 2, -h + 0.03), (w / 2, -h + 0.03)):
        L.bm_cyl(cb, (x * 0.98, -0.0, z), (x * 0.98, -0.011, z), 0.012, segs=16)
    obj(cb, "ЗР_держатели", coll, [m["chrome"]], r, smooth=60)
    return r


# ---------------------------------------------------------------- туалеты

def toilet(coll, m, at, rng, torn: bool = False) -> bpy.types.Object:
    """Унитаз тарельчатый с высоким чугунным бачком: борт на 400, бачок низом на 1800, смывная труба по стене,
    рычаг с цепочкой и ручкой-грушей; сорванный — бачка нет, труба оборвана, кронштейны на стене, сиденья нет."""
    r = L.root("УН_унитаз_без_бачка" if torn else "УН_унитаз", coll, at)
    n = 56
    cy = -0.32
    out = [(0.0, 0.115, 0.175, cy + 0.01, 3.2), (0.02, 0.112, 0.17, cy + 0.01, 3.2), (0.07, 0.102, 0.158, cy + 0.01, 3.0),
           (0.2, 0.098, 0.15, cy, 2.6), (0.29, 0.13, 0.2, cy, 2.4), (0.355, 0.168, 0.248, cy - 0.005, 2.3),
           (0.395, 0.178, 0.262, cy - 0.005, 2.3)]
    rings = [(z, superellipse(a, b, 0, c, p, n)) for z, a, b, c, p in out]
    # закатанный борт и чаша: тарелка-полка спереди, выпуск сзади
    inn = [(0.405, 0.168, 0.25, cy - 0.005, 2.3), (0.398, 0.152, 0.232, cy - 0.005, 2.2), (0.37, 0.14, 0.215, cy, 2.2),
           (0.3, 0.1, 0.155, cy + 0.02, 2.1), (0.24, 0.06, 0.08, cy + 0.05, 2.0), (0.215, 0.035, 0.04, cy + 0.06, 2.0)]
    rings += [(z, superellipse(a, b, 0, c, p, n)) for z, a, b, c, p in inn]
    bm = bmesh.new()
    set_mat(loft(bm, rings, cap_first=True, cap_last=True), 0)
    # раструб для смывной трубы сзади вверху
    lathe(bm, [(0.0, 0.0), (0.028, 0.0), (0.03, 0.01), (0.03, 0.06), (0.024, 0.065), (0.018, 0.065), (0.018, 0.03), (0.0, 0.03)],
          segs=24, origin=(0, cy + 0.235, 0.36), axis=(0, 1, 0))
    body = obj(bm, "УН_чаша", coll, [m["faience"]], r)
    subsurf(body)
    if not torn:
        sb = bmesh.new()
        outer = superellipse(0.18, 0.225, 0, cy - 0.01, 2.2, 48)
        inner = superellipse(0.11, 0.15, 0, cy - 0.02, 2.0, 48)
        rs = [(0.407, inner), (0.407, outer), (0.43, outer), (0.43, inner)]
        set_mat(loft(sb, rs + [rs[0]]), 0)
        for sx in (-1, 1):
            L.bm_cyl(sb, (sx * 0.06, cy + 0.215, 0.418), (sx * 0.035, cy + 0.215, 0.418), 0.012, segs=12)
        seat = obj(sb, "УН_сиденье", coll, [m["seat"]], r)
        subsurf(seat, 1)
    # бачок: литой короб с рёбрами, крышка, кронштейны, рычаг, цепочка с грушей
    z0, w, d, h = 1.8, 0.40, 0.17, 0.30
    kb = bmesh.new()
    for sx in (-1, 1):
        x = sx * 0.13
        prof = [(0.0, 0.0), (-0.16, 0.0), (-0.16, -0.015), (-0.025, -0.13), (0.0, -0.13)]
        L.bm_prism(kb, prof, (x - 0.007, 0, z0), V((0, 1, 0)), V((0, 0, 1)), V((0.014, 0, 0)))
    obj(kb, "УН_кронштейны", coll, [m["cast_iron"]], r, bevel=0.002, segs=1)
    px = 0.08  # выпуск бачка — правее середины
    pp = bmesh.new()
    if not torn:
        tank = bmesh.new()
        set_mat(rounded_box(tank, (w, d, h), 0.018, cuts=6, center=(0, -0.012 - d / 2, z0 + h / 2)), 0)
        for k in range(3):
            z = z0 + 0.06 + k * 0.08
            set_mat(L.bm_box(tank, (-w / 2 - 0.004, -0.012 - d - 0.004, z), (w / 2 + 0.004, -0.012 - d + 0.02, z + 0.012)), 0)
        set_mat(rounded_box(tank, (w + 0.016, d + 0.016, 0.02), 0.008, cuts=4, center=(0, -0.012 - d / 2, z0 + h + 0.01)), 0)
        obj(tank, "УН_бачок", coll, [m["cast_iron"]], r, smooth=50)
        # рычаг поверх крышки вбок и вперёд, цепочка звеньями, груша
        lv = bmesh.new()
        pipe(lv, [(-0.12, -0.012 - d / 2, z0 + h + 0.03), (-0.2, -0.012 - d - 0.04, z0 + h + 0.03),
                  (-0.24, -0.012 - d - 0.06, z0 + h + 0.0)], 0.006, segs=10, bend=0.03)
        L.bm_cyl(lv, (-0.12, -0.012 - d / 2, z0 + h + 0.02), (-0.12, -0.012 - d / 2, z0 + h + 0.045), 0.012, segs=14)
        obj(lv, "УН_рычаг", coll, [m["cast_iron"]], r, smooth=50)
        ch = bmesh.new()
        top = V((-0.24, -0.012 - d - 0.06, z0 + h - 0.005))
        links = 34
        for k in range(links):
            c = top + V((0.0, 0.0, -0.018 * k - 0.009))
            pts = [c + V((0.0, 0.004 * math.cos(TAU * i / 10), 0.0085 * math.sin(TAU * i / 10))) for i in range(10)]
            if k % 2:
                pts = [c + V((0.004 * math.cos(TAU * i / 10), 0.0, 0.0085 * math.sin(TAU * i / 10))) for i in range(10)]
            pipe(ch, pts, 0.0012, segs=5, closed=True)
        hz = top.z - 0.018 * links - 0.015
        lathe(ch, [(0, 0), (0.014, 0.01), (0.02, 0.04), (0.017, 0.07), (0.008, 0.085), (0, 0.09)], segs=20,
              origin=(top.x, top.y, hz - 0.09))
        obj(ch, "УН_цепочка", coll, [m["chain"]], r, smooth=70)
        pipe(pp, [(px, -0.012 - d / 2, z0 + 0.01), (px, -0.012 - d / 2, z0 - 0.05), (px, -0.03, z0 - 0.2), (px, -0.03, 0.5),
                  (0, -0.03, 0.42), (0, cy + 0.27, 0.36)], 0.016, segs=14, bend=0.07)
    else:
        # оборванная труба: от раструба унитаза вверх, рваный конец на 0,9 м, чуть отогнута от стены
        pipe(pp, [(0, cy + 0.27, 0.36), (0, -0.03, 0.42), (px, -0.04, 0.55), (px + 0.02, -0.07, 0.92)], 0.016, segs=14,
             bend=0.07)
        # обломок выпуска у кронштейнов
        pipe(pp, [(px, -0.03, z0 - 0.05), (px, -0.03, z0 - 0.17)], 0.016, segs=14)
    obj(pp, "УН_смывная_труба", coll, [m["pipe_paint"]], r, smooth=60)
    return r


def stall(coll, m, at, rng, door: str = "closed") -> bpy.types.Object:
    """Кабинка: перегородка 1200 × 1800 на двух стальных ножках (низ на 150), стойка, верхняя тяга и дверца
    700 × 1650 на трёх петлях с щеколдой. Модуль ставится в ряд: правая перегородка — у соседнего, последней —
    КБ_перегородка. door: closed — прикрыта (на 4°), open — распахнута, none — выбита и лежит на полу."""
    names = {"closed": "КБ_кабинка", "open": "КБ_кабинка_открыта", "none": "КБ_кабинка_без_дверцы"}
    r = L.root(names[door], coll, at)
    W, D, H, z0, t = 1.1, 1.2, 1.8, 0.15, 0.025
    hw = W / 2
    pb = bmesh.new()
    board(pb, (-hw - t / 2, -D, z0), (-hw + t / 2, 0.0, z0 + H))
    obj(pb, "КБ_перегородка_лев", coll, [m["partition"], m["partition"]], r, bevel=0.003, segs=2)
    fb = bmesh.new()
    # ножка у фасада и уголки к стене
    L.bm_cyl(fb, (-hw, -D + 0.04, 0.0), (-hw, -D + 0.04, z0 + 0.1), 0.016, segs=14)
    L.bm_cyl(fb, (-hw, -D + 0.04, 0.0), (-hw, -D + 0.04, 0.012), 0.03, segs=16)
    for z in (z0 + 0.3, z0 + H - 0.3):
        L.bm_box(fb, (-hw - t / 2 - 0.003, -0.04, z), (-hw + t / 2 + 0.003, 0.0, z + 0.04))
    # стойка дверного проёма справа и верхняя тяга от стены до стены
    L.bm_box(fb, (hw - 0.03, -D - 0.03, 0.0), (hw + 0.0, -D, z0 + H))
    pipe(fb, [(-hw - 0.02, -D - 0.015, z0 + H + 0.02), (hw + 0.02, -D - 0.015, z0 + H + 0.02)], 0.012, segs=12)
    obj(fb, "КБ_фурнитура", coll, [m["steel_paint"]], r, bevel=0.0015, segs=1)
    # неподвижная панель фасада у стойки и дверца на петлях у левой перегородки
    pn = bmesh.new()
    board(pn, (hw - 0.03 - 0.2, -D - 0.018, z0), (hw - 0.03, -D, z0 + H))
    obj(pn, "КБ_панель_фасада", coll, [m["partition"], m["partition"]], r, bevel=0.003, segs=2)
    hinge_x = -hw + t / 2 + 0.004
    dw, dh, dz = (hw - 0.236) - hinge_x, 1.65, 0.2
    db = bmesh.new()
    board(db, (0.0, -0.018, 0.0), (dw, 0.0, dh))
    door_ob = None
    if door != "none":
        door_ob = obj(db, "КБ_дверца", coll, [m["partition"], m["partition"]], r, bevel=0.003, segs=2)
        ang = {"closed": 4.0, "open": 100.0}[door]
        door_ob.matrix_parent_inverse = Matrix.Identity(4)
        door_ob.location = (hinge_x, -D - 0.002, dz)
        door_ob.rotation_euler = (0, 0, math.radians(ang))
        hb = bmesh.new()
        for z in (0.12, dh / 2, dh - 0.12):
            L.bm_cyl(hb, (0.0, -0.009, z - 0.05), (0.0, -0.009, z + 0.05), 0.007, segs=12)
        L.bm_box(hb, (dw - 0.07, -0.03, dh / 2 - 0.01), (dw - 0.02, -0.018, dh / 2 + 0.01))
        L.bm_cyl(hb, (dw - 0.04, -0.03, dh / 2 + 0.03), (dw - 0.04, -0.06, dh / 2 + 0.03), 0.008, segs=12)
        hw_ob = obj(hb, "КБ_петли_щеколда", coll, [m["chrome"]], door_ob)
        hw_ob.matrix_parent_inverse = Matrix.Identity(4)
    else:
        # выбитая дверца лежит на полу внутри, одна петля вырвана с мясом
        door_ob = obj(db, "КБ_дверца_на_полу", coll, [m["partition"], m["partition"]], r, bevel=0.003, segs=2)
        door_ob.matrix_parent_inverse = Matrix.Identity(4)
        door_ob.location = (-hw + 0.12, -D + 0.25, 0.018)
        door_ob.rotation_euler = (math.radians(-90), 0, math.radians(8))
        hb = bmesh.new()
        for z in (0.12, dh - 0.12):
            L.bm_cyl(hb, (hinge_x, -D - 0.011, dz + z - 0.05), (hinge_x, -D - 0.011, dz + z + 0.05), 0.007, segs=12)
        obj(hb, "КБ_петли_остались", coll, [m["chrome"]], r)
    return r


def partition_end(coll, m, at, rng) -> bpy.types.Object:
    """Последняя перегородка ряда кабинок (правая у крайней)."""
    r = L.root("КБ_перегородка", coll, at)
    D, H, z0, t = 1.2, 1.8, 0.15, 0.025
    pb = bmesh.new()
    board(pb, (-t / 2, -D, z0), (t / 2, 0.0, z0 + H))
    obj(pb, "КБ_перегородка_прав", coll, [m["partition"], m["partition"]], r, bevel=0.003, segs=2)
    fb = bmesh.new()
    L.bm_cyl(fb, (0, -D + 0.04, 0.0), (0, -D + 0.04, z0 + 0.1), 0.016, segs=14)
    L.bm_cyl(fb, (0, -D + 0.04, 0.0), (0, -D + 0.04, 0.012), 0.03, segs=16)
    for z in (z0 + 0.3, z0 + H - 0.3):
        L.bm_box(fb, (-t / 2 - 0.003, -0.04, z), (t / 2 + 0.003, 0.0, z + 0.04))
    obj(fb, "КБ_ножка", coll, [m["steel_paint"]], r, bevel=0.0015, segs=1)
    return r


# ---------------------------------------------------------------- кухня

def stove(coll, m, at, rng, open_door: bool = False) -> bpy.types.Object:
    """Электроплита 500 × 600 × 850: эмалированный корпус, четыре чугунные конфорки на хромированных кольцах,
    задний борт, наклонная панель с пятью ручками, дверца духовки со стеклом и ручкой, ящик, цоколь, ножки."""
    r = L.root("ЭП_плита_дверца" if open_door else "ЭП_плита", coll, at)
    w, d, h = 0.5, 0.6, 0.85
    bm = bmesh.new()
    set_mat(rounded_box(bm, (w, d - 0.02, h - 0.07), 0.01, cuts=6, center=(0, 0.01, 0.07 + (h - 0.07) / 2)), 0)
    # цоколь утоплен, задний борт
    set_mat(L.bm_box(bm, (-w / 2 + 0.02, -d / 2 + 0.06, 0.012), (w / 2 - 0.02, d / 2 - 0.01, 0.07)), 0)
    set_mat(rounded_box(bm, (w, 0.03, 0.08), 0.008, cuts=4, center=(0, d / 2 - 0.015, h + 0.04)), 0)
    body = obj(bm, "ЭП_корпус", coll, [m["stove_enamel"]], r, smooth=50)
    yf = -d / 2 + 0.02          # лицевая плоскость корпуса
    # камера духовки за дверцей: вырез в корпусе и тёмная эмалированная камера (открыта спереди), направляющие
    # по бокам на трёх уровнях, решётка на среднем, ТЭН петлёй под потолком
    ox, oz0, oz1, od = 0.205, 0.215, 0.585, 0.46
    cb = bmesh.new()
    L.bm_box(cb, (-ox, yf - 0.02, oz0), (ox, yf + od, oz1))
    cut(body, coll, r, "ЭП_камера_вырез", cb)
    ch = bmesh.new()
    fs = L.bm_box(ch, (-ox + 0.0005, yf + 0.0005, oz0 + 0.0005), (ox - 0.0005, yf + od - 0.0005, oz1 - 0.0005))
    ch.normal_update()
    bmesh.ops.delete(ch, geom=[f for f in fs if f.normal.y < -0.9], context="FACES")
    bmesh.ops.reverse_faces(ch, faces=ch.faces[:])
    for sx in (-1, 1):
        for z in (0.31, 0.39, 0.47):
            L.bm_cyl(ch, (sx * (ox - 0.004), yf + 0.03, z), (sx * (ox - 0.004), yf + od - 0.03, z), 0.0045, segs=10)
    camera = L.finish_bm(ch, "ЭП_камера", coll, m["oven"], r, smooth_angle=35)
    camera.data.materials.clear()
    camera.data.materials.append(m["oven"])
    rk = bmesh.new()
    zr = 0.395
    pipe(rk, [(-ox + 0.012, yf + 0.03, zr), (ox - 0.012, yf + 0.03, zr), (ox - 0.012, yf + od - 0.03, zr),
              (-ox + 0.012, yf + od - 0.03, zr)], 0.003, segs=8, bend=0.012, closed=True)
    for k in range(11):
        x = -ox + 0.04 + k * (2 * ox - 0.08) / 10
        pipe(rk, [(x, yf + 0.03, zr + 0.004), (x, yf + od - 0.03, zr + 0.004)], 0.0018, segs=6)
    pipe(rk, [(-0.15, yf + od - 0.01, oz1 - 0.03), (-0.15, yf + 0.06, oz1 - 0.03), (-0.05, yf + 0.06, oz1 - 0.03),
              (-0.05, yf + od - 0.06, oz1 - 0.03), (0.05, yf + od - 0.06, oz1 - 0.03), (0.05, yf + 0.06, oz1 - 0.03),
              (0.15, yf + 0.06, oz1 - 0.03), (0.15, yf + od - 0.01, oz1 - 0.03)], 0.004, segs=8, bend=0.03)
    obj(rk, "ЭП_решётка_тэн", coll, [m["handle"]], r, smooth=60)
    # панель управления — наклонная полоса спереди сверху
    pb = bmesh.new()
    L.bm_prism(pb, [(-w / 2 + 0.005, 0.0), (w / 2 - 0.005, 0.0), (w / 2 - 0.005, 0.07), (-w / 2 + 0.005, 0.07)],
               (0, yf - 0.004, h - 0.08), V((1, 0, 0)), V((0, -0.25, 0.97)), V((0, 0.004, 0)))
    obj(pb, "ЭП_панель", coll, [m["stove_enamel"]], r)
    del body
    kb = bmesh.new()
    for k in range(5):
        x = -0.18 + k * 0.09
        o = V((x, yf - 0.013, h - 0.045))
        ax = V((0, -1, 0.25)).normalized()
        lathe(kb, [(0, 0), (0.019, 0), (0.019, 0.012), (0.015, 0.02), (0, 0.022)], segs=20, origin=o, axis=ax)
        f = o + ax * 0.0215     # риска-указатель на торце ручки
        L.bm_box(kb, (x - 0.0025, f.y - 0.002, f.z + 0.004), (x + 0.0025, f.y + 0.001, f.z + 0.014))
    obj(kb, "ЭП_ручки", coll, [m["plastic"]], r, smooth=50)
    # конфорки: чугунный диск с канавками на кольце-обечайке
    cb = bmesh.new()
    rings = bmesh.new()
    for (x, y), rad in (((-0.11, -0.1), 0.09), ((0.12, -0.12), 0.0725), ((-0.12, 0.14), 0.0725), ((0.11, 0.12), 0.09)):
        lathe(cb, [(0, h + 0.012), (rad - 0.004, h + 0.012), (rad, h + 0.008), (rad, h - 0.004), (0, h - 0.004)], segs=48,
              origin=(x, y, 0))
        for g in (0.3, 0.55, 0.8):
            lathe(cb, [(rad * g, h + 0.0125), (rad * g + 0.003, h + 0.0125), (rad * g + 0.003, h + 0.0135), (rad * g, h + 0.0135)],
                  segs=48, origin=(x, y, 0), closed=True)
        lathe(rings, [(rad + 0.001, h + 0.002), (rad + 0.016, h - 0.001), (rad + 0.02, h + 0.001), (rad + 0.004, h + 0.009),
                      (rad + 0.001, h + 0.009)], segs=48, origin=(x, y, 0), closed=True)
    obj(cb, "ЭП_конфорки", coll, [m["burner"]], r, smooth=40)
    obj(rings, "ЭП_кольца", coll, [m["chrome"]], r, smooth=60)
    # дверца духовки на петлях внизу: стекло, ручка на стойках
    dw, dh = 0.44, 0.40
    db = bmesh.new()
    set_mat(rounded_box(db, (dw, 0.035, dh), 0.008, cuts=4, center=(0, -0.0175, dh / 2)), 0)
    door = obj(db, "ЭП_дверца", coll, [m["stove_enamel"]], r, smooth=50)
    door.matrix_parent_inverse = Matrix.Identity(4)
    door.location = (0, yf, 0.2)
    door.rotation_euler = (math.radians(88 if open_door else 0), 0, 0)
    gb = bmesh.new()
    set_mat(L.bm_box(gb, (-0.13, -0.037, 0.13), (0.13, -0.033, 0.29)), 0)
    set_mat(L.bm_box(gb, (-0.15, -0.002, 0.11), (0.15, 0.001, 0.31)), 0)
    gl = obj(gb, "ЭП_стекло", coll, [m["glass"]], door)
    gl.matrix_parent_inverse = Matrix.Identity(4)
    hb = bmesh.new()
    for sx in (-1, 1):
        L.bm_cyl(hb, (sx * 0.17, -0.035, dh - 0.04), (sx * 0.17, -0.065, dh - 0.04), 0.007, segs=12)
    L.bm_cyl(hb, (-0.2, -0.068, dh - 0.04), (0.2, -0.068, dh - 0.04), 0.009, segs=16)
    hd = obj(hb, "ЭП_ручка_дверцы", coll, [m["chrome"]], door, smooth=60)
    hd.matrix_parent_inverse = Matrix.Identity(4)
    # ящик для противней под дверцей
    xb = bmesh.new()
    set_mat(rounded_box(xb, (dw, 0.025, 0.11), 0.006, cuts=4, center=(0, yf - 0.0125, 0.075 + 0.055)), 0)
    L.bm_box(xb, (-0.08, yf - 0.029, 0.165), (0.08, yf - 0.024, 0.172))
    obj(xb, "ЭП_ящик", coll, [m["stove_enamel"]], r, smooth=50)
    ft = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.bm_cyl(ft, (sx * (w / 2 - 0.04), sy * (d / 2 - 0.06), 0.0), (sx * (w / 2 - 0.04), sy * (d / 2 - 0.06), 0.014), 0.014, segs=14)
    obj(ft, "ЭП_ножки", coll, [m["plastic"]], r)
    return r


def edge_strips(bm, x0, x1, y0, y1, z0, z1, back: bool, t: float = 0.0025) -> None:
    """Алюминиевый кант по кромке столешницы: полосы по бокам и спереди (и сзади у отдельно стоящего стола)."""
    set_mat(L.bm_box(bm, (x0 - t, y0 - t, z0), (x1 + t, y0, z1)), 0)
    for x in (x0 - t, x1):
        set_mat(L.bm_box(bm, (x, y0, z0), (x + t, y1 + (t if back else 0.0), z1)), 0)
    if back:
        set_mat(L.bm_box(bm, (x0 - t, y1, z0), (x1 + t, y1 + t, z1)), 0)


def part_at(bm, name, coll, mlist, parent, pivot, **kw):
    """Деталь, которая потом открывается в игре (дверца, ящик): геометрия построена в осях предмета, начало узла —
    в шарнире / у лица ящика."""
    ob = obj(bm, name, coll, mlist, parent, **kw)
    ob.data.transform(Matrix.Translation(-V(pivot)))
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = V(pivot)
    return ob


def hinged_doors(coll, m, r, prefix, x_outer, y_face, z0, z1, handle_z, thick=0.016) -> None:
    """Две накладные дверцы на петлях по наружным краям (лицо — к −Y от y_face), ручки-скобы у притвора — дочерние
    узлы дверец: дверцы открываются в игре отдельно, корпус внутри пустой."""
    for s, side in ((-1, "лев"), (1, "прав")):
        x0, x1 = (-x_outer, -0.0015) if s < 0 else (0.0015, x_outer)
        db = bmesh.new()
        board(db, (x0, y_face - thick, z0), (x1, y_face, z1))
        pivot = (s * x_outer, y_face, z0)
        door = part_at(db, f"{prefix}_дверца_{side}", coll, [m["chip"], m["edge"]], r, pivot, bevel=0.0012, segs=1)
        hb = bmesh.new()
        bow_handle(hb, (s * 0.04, y_face - thick, handle_z), (0, 0, 1))
        hd = obj(hb, f"{prefix}_ручка_{side}", coll, [m["handle"]], door)
        hd.data.transform(Matrix.Translation(-V(pivot)))
        hd.matrix_parent_inverse = Matrix.Identity(4)


def drawer(coll, m, r, prefix, x_half, y_face, z0, z1, depth, thick=0.016) -> None:
    """Выдвижной ящик: накладное лицо и короб из ДСП 12 мм за ним (дно — ДВП), ручка-скоба; узел — у лица ящика."""
    bm = bmesh.new()
    board(bm, (-x_half, y_face - thick, z0), (x_half, y_face, z1))
    bx0, bx1 = -x_half + 0.03, x_half - 0.03
    bz0, bz1 = z0 + 0.012, z1 - 0.02
    for x in (bx0, bx1 - 0.012):
        board(bm, (x, y_face, bz0), (x + 0.012, y_face + depth, bz1))
    board(bm, (bx0, y_face + depth - 0.012, bz0), (bx1, y_face + depth, bz1))
    board(bm, (bx0 + 0.012, y_face, bz0 + 0.004), (bx1 - 0.012, y_face + 0.012, bz1))
    set_mat(L.bm_box(bm, (bx0, y_face, bz0 - 0.004), (bx1, y_face + depth, bz0)), 2)
    pivot = (0.0, y_face, z0)
    box = part_at(bm, f"{prefix}_ящик", coll, [m["chip"], m["edge"], m["hdf"]], r, pivot, bevel=0.0012, segs=1)
    hb = bmesh.new()
    bow_handle(hb, (0, y_face - thick, (z0 + z1) / 2), (1, 0, 0))
    hd = obj(hb, f"{prefix}_ручка_ящика", coll, [m["handle"]], box)
    hd.data.transform(Matrix.Translation(-V(pivot)))
    hd.matrix_parent_inverse = Matrix.Identity(4)


def cabinet_box(bm, w, d, h, t=0.016, plinth=0.08, top_over=0.0):
    """Корпус тумбы из ДСП: боковины, дно, цоколь, задняя ДВП (слот 2); верх — отдельно."""
    hw, hd = w / 2, d / 2
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), -hd + 0.02, 0), (s * hw + (0 if s > 0 else t), hd, h))
    board(bm, (-hw + t, -hd + 0.02, plinth), (hw - t, hd - 0.004, plinth + t))
    board(bm, (-hw + t, -hd + 0.04, 0.0), (hw - t, -hd + 0.04 + t, plinth))
    back = L.bm_box(bm, (-hw + 0.004, hd - 0.004, plinth), (hw - 0.004, hd, h))
    set_mat(back, 2)


def sink_cabinet(coll, m, at, rng) -> bpy.types.Object:
    """Мойка чугунная эмалированная 800 × 600 с крылом и задним бортом на тумбе с двумя дверцами; настенный смеситель
    с гусаком над бортом; под мойкой — выпуск и сифон."""
    r = L.root("МК_мойка", coll, at)
    w, d, h = 0.8, 0.6, 0.85
    bm = bmesh.new()
    cabinet_box(bm, w, d, h - 0.03)
    obj(bm, "МК_тумба", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.0012, segs=1)
    hinged_doors(coll, m, r, "МК", w / 2 - 0.002, -d / 2 + 0.02, 0.082, h - 0.035, h - 0.17)
    # чаша слева, крыло справа: верх — кольцо от контура мойки к краю чаши, чаша вниз до выпуска
    n = 64
    top = h
    cx, cyb = -0.15, -0.03
    outer = superellipse(w / 2, d / 2, 0, 0, 9.0, n)
    inset = superellipse(w / 2 - 0.008, d / 2 - 0.008, 0, 0, 9.0, n)
    rings = [(top - 0.04, outer), (top - 0.006, outer), (top, inset)]
    rim = superellipse(0.215, 0.18, cx, cyb, 7.0, n)
    rings += [(top, superellipse(0.25, 0.215, cx, cyb, 7.0, n)), (top + 0.004, superellipse(0.235, 0.2, cx, cyb, 7.0, n)),
              (top, rim)]
    for z, a, b, p in ((top - 0.04, 0.208, 0.172, 6.0), (top - 0.13, 0.19, 0.155, 5.0), (top - 0.16, 0.16, 0.125, 4.0),
                       (top - 0.165, 0.03, 0.03, 2.0)):
        rings.append((z, superellipse(a, b, cx, cyb, p, n)))
    sb = bmesh.new()
    set_mat(loft(sb, rings, cap_last=True), 0)
    # задний борт
    set_mat(rounded_box(sb, (w, 0.035, 0.13), 0.012, cuts=5, center=(0, d / 2 - 0.0175, top + 0.065)), 0)
    sink = obj(sb, "МК_мойка", coll, [m["sink_enamel"]], r)
    subsurf(sink, 1)
    # смеситель на стене над бортом: корпус, два вентиля, гусак
    mb = bmesh.new()
    zt = top + 0.21
    L.bm_cyl(mb, (-0.08, d / 2, zt), (0.08, d / 2, zt), 0.012, segs=14)
    L.bm_cyl(mb, (-0.08, d / 2 + 0.002, zt), (-0.08, d / 2 - 0.04, zt), 0.012, segs=14)
    L.bm_cyl(mb, (0.08, d / 2 + 0.002, zt), (0.08, d / 2 - 0.04, zt), 0.012, segs=14)
    for x in (-0.08, 0.08):
        L.bm_cyl(mb, (x, d / 2 - 0.0, zt), (x, d / 2 - 0.0, zt + 0.06), 0.011, segs=14)
        for k in range(4):
            a = TAU * k / 4
            pipe(mb, [(x, d / 2, zt + 0.06), (x + 0.028 * math.cos(a), d / 2 + 0.028 * math.sin(a), zt + 0.064)], 0.0045, segs=8)
    pipe(mb, [(0, d / 2, zt), (0, d / 2 - 0.02, zt + 0.02), (0, d / 2 - 0.08, zt + 0.12), (cx + 0.05, cyb + 0.09, zt + 0.13),
              (cx, cyb + 0.02, zt + 0.06)], 0.009, segs=14, bend=0.05)
    obj(mb, "МК_смеситель", coll, [m["chrome"]], r, smooth=60)
    pb = bmesh.new()
    pipe(pb, [(cx, cyb, top - 0.165), (cx, cyb, top - 0.3), (cx + 0.06, cyb + 0.1, top - 0.42), (cx + 0.06, d / 2 - 0.004, top - 0.42)],
         0.02, segs=14, bend=0.05)
    obj(pb, "МК_сифон", coll, [m["plastic"]], r, smooth=60)
    return r


def cutting_table(coll, m, at, rng) -> bpy.types.Object:
    """Стол-тумба кухонный 800 × 600 × 850: столешница с пластиком и алюминиевой окантовкой, ящик, две дверцы."""
    r = L.root("СР_стол_тумба", coll, at)
    w, d, h = 0.8, 0.6, 0.85
    bm = bmesh.new()
    cabinet_box(bm, w, d, h - 0.028)
    board(bm, (-w / 2 + 0.016, -d / 2 + 0.02, h - 0.195), (w / 2 - 0.016, d / 2 - 0.004, h - 0.18))
    obj(bm, "СР_корпус", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.0012, segs=1)
    drawer(coll, m, r, "СР", w / 2 - 0.002, -d / 2 + 0.02, h - 0.18, h - 0.032, 0.5)
    hinged_doors(coll, m, r, "СР", w / 2 - 0.002, -d / 2 + 0.02, 0.082, h - 0.185, h - 0.28)
    tb = bmesh.new()
    set_mat(L.bm_box(tb, (-w / 2 - 0.01, -d / 2 - 0.01, h - 0.028), (w / 2 + 0.01, d / 2, h)), 0)
    obj(tb, "СР_столешница", coll, [m["top_laminate"]], r, bevel=0.0015, segs=1)
    eb = bmesh.new()
    edge_strips(eb, -w / 2 - 0.01, w / 2 + 0.01, -d / 2 - 0.01, d / 2, h - 0.03, h + 0.002, back=False)
    obj(eb, "СР_окантовка", coll, [m["aluminium"]], r, bevel=0.0008, segs=1)
    return r


def dining_table(coll, m, at, rng) -> bpy.types.Object:
    """Обеденный стол 1200 × 800 × 750: каркас из профильной трубы 25 × 25, столешница ДСП с пластиком и
    алюминиевым кантом, пластиковые подпятники."""
    r = L.root("ОС_стол_обеденный", coll, at)
    w, d, h = 1.2, 0.8, 0.75
    tb = bmesh.new()
    set_mat(L.bm_box(tb, (-w / 2, -d / 2, h - 0.025), (w / 2, d / 2, h)), 0)
    obj(tb, "ОС_столешница", coll, [m["top_laminate"]], r, bevel=0.002, segs=2)
    eb = bmesh.new()
    edge_strips(eb, -w / 2, w / 2, -d / 2, d / 2, h - 0.027, h + 0.002, back=True)
    obj(eb, "ОС_кант", coll, [m["aluminium"]], r, bevel=0.0008, segs=1)
    fb = bmesh.new()
    s = 0.0125
    lx, ly = w / 2 - 0.06, d / 2 - 0.06
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.bm_box(fb, (sx * lx - s, sy * ly - s, 0.012), (sx * lx + s, sy * ly + s, h - 0.025))
    for sy in (-1, 1):
        L.bm_box(fb, (-lx, sy * ly - s, h - 0.025 - 0.05), (lx, sy * ly + s, h - 0.025 - 0.025))
    for sx in (-1, 1):
        L.bm_box(fb, (sx * lx - s, -ly, h - 0.025 - 0.05), (sx * lx + s, ly, h - 0.025 - 0.025))
        L.bm_box(fb, (sx * lx - s, -ly, 0.15), (sx * lx + s, ly, 0.175))
    obj(fb, "ОС_каркас", coll, [m["steel_paint"]], r, bevel=0.0015, segs=1)
    ft = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            L.bm_box(ft, (sx * lx - s - 0.001, sy * ly - s - 0.001, 0.0), (sx * lx + s + 0.001, sy * ly + s + 0.001, 0.014))
    obj(ft, "ОС_подпятники", coll, [m["plastic"]], r, bevel=0.002, segs=1)
    return r


def wall_cabinet(coll, m, at, rng) -> bpy.types.Object:
    """Шкафчик навесной 800 × 300 × 600, две дверцы на ручках-скобах, полка; корень — середина верха у стены."""
    r = L.root("ШН_шкафчик", coll, at)
    w, d, h, t = 0.8, 0.3, 0.6, 0.016
    hw = w / 2
    bm = bmesh.new()
    y0 = -d
    board(bm, (-hw, y0, -t), (hw, 0.0, 0.0))
    board(bm, (-hw, y0, -h), (hw, 0.0, -h + t))
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), y0 + 0.018, -h + t), (s * hw + (0 if s > 0 else t), -0.004, -t))
    board(bm, (-hw + t, y0 + 0.03, -h / 2 - t / 2), (hw - t, -0.004, -h / 2 + t / 2))
    back = L.bm_box(bm, (-hw + 0.004, -0.004, -h + 0.004), (hw - 0.004, 0.0, -0.004))
    set_mat(back, 2)
    obj(bm, "ШН_корпус", coll, [m["chip"], m["edge"], m["hdf"]], r, bevel=0.0012, segs=1)
    hinged_doors(coll, m, r, "ШН", hw - 0.002, y0 + 0.016, -h + 0.003, -0.003, -h + 0.1)
    return r


def dish_shelf(coll, m, at, rng) -> bpy.types.Object:
    """Полка для посуды 800 × 250 × 500: две полки, бортики-перекладины, решётка-сушилка для тарелок внизу;
    корень — середина верха у стены."""
    r = L.root("ПП_полка_посуда", coll, at)
    w, d, h, t = 0.8, 0.25, 0.5, 0.018
    hw = w / 2
    bm = bmesh.new()
    for s in (-1, 1):
        board(bm, (s * hw - (t if s > 0 else 0), -d, -h), (s * hw + (0 if s > 0 else t), 0.0, 0.0))
    for z in (-t, -h / 2, -h + 0.02):
        board(bm, (-hw + t, -d, z), (hw - t, 0.0, z + t))
    obj(bm, "ПП_корпус", coll, [m["wood"], m["wood"]], r, bevel=0.0015, segs=1)
    rb = bmesh.new()
    for z in (-h / 2 + 0.06, -t + 0.0):
        pipe(rb, [(-hw + t, -d + 0.012, z + 0.05), (hw - t, -d + 0.012, z + 0.05)], 0.005, segs=10)
    # сушилка: прутья вертикально под тарелки на нижней полке
    for k in range(18):
        x = -hw + t + 0.04 + k * 0.04
        pipe(rb, [(x, -d + 0.04, -h + 0.038), (x, -d + 0.04, -h + 0.16)], 0.0025, segs=8)
        pipe(rb, [(x, -0.04, -h + 0.038), (x, -0.04, -h + 0.2)], 0.0025, segs=8)
    for y in (-d + 0.04, -0.04):
        pipe(rb, [(-hw + t + 0.02, y, -h + 0.12 + (0.04 if y > -0.1 else 0.0)), (hw - t - 0.02, y, -h + 0.12 + (0.04 if y > -0.1 else 0.0))],
             0.0025, segs=8)
    obj(rb, "ПП_перекладины", coll, [m["handle"]], r, smooth=60)
    return r


# ---------------------------------------------------------------- посуда и баки

def pot(coll, m, at, rng) -> bpy.types.Object:
    """Кастрюля эмалированная 4 л: Ø220 × 140, закатанный край, две ручки-скобы, крышка с ручкой-кнопкой."""
    r = L.root("ПС_кастрюля", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.095, 0.0), (0.104, 0.008), (0.108, 0.04), (0.108, 0.135), (0.112, 0.14), (0.107, 0.142),
               (0.103, 0.136), (0.103, 0.01), (0.095, 0.005), (0.0, 0.005)], segs=48)
    obj(bm, "ПС_корпус", coll, [m["pot_enamel"]], r, smooth=50)
    lb = bmesh.new()
    lathe(lb, [(0.0, 0.152), (0.06, 0.15), (0.104, 0.142), (0.112, 0.138), (0.112, 0.134), (0.1, 0.137), (0.0, 0.146)], segs=48)
    lathe(lb, [(0, 0.15), (0.012, 0.15), (0.016, 0.165), (0.0, 0.172)], segs=16)
    obj(lb, "ПС_крышка", coll, [m["pot_enamel"]], r, smooth=50)
    hb = bmesh.new()
    for s in (-1, 1):
        pipe(hb, [(s * 0.105, -0.03, 0.115), (s * 0.135, -0.03, 0.12), (s * 0.14, 0.0, 0.12), (s * 0.135, 0.03, 0.12),
                  (s * 0.105, 0.03, 0.115)], 0.004, segs=8, bend=0.015)
    obj(hb, "ПС_ручки", coll, [m["pot_enamel"]], r, smooth=60)
    return r


def kettle(coll, m, at, rng) -> bpy.types.Object:
    """Чайник эмалированный 3 л: Ø190, носик, ручка-дуга на ушках, крышка с кнопкой."""
    r = L.root("ПС_чайник", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.085, 0.0), (0.095, 0.01), (0.098, 0.06), (0.09, 0.12), (0.06, 0.16), (0.045, 0.165),
               (0.045, 0.17), (0.041, 0.17), (0.041, 0.165), (0.0, 0.16)], segs=40)
    pipe(bm, [(0.08, 0.0, 0.05), (0.12, 0.0, 0.09), (0.15, 0.0, 0.14), (0.165, 0.0, 0.16)], 0.014, segs=14, bend=0.03)
    obj(bm, "ПС_чайник_корпус", coll, [m["pot_enamel"]], r, smooth=50)
    lb = bmesh.new()
    lathe(lb, [(0, 0.172), (0.044, 0.168), (0.046, 0.164), (0.0, 0.168)], segs=32)
    lathe(lb, [(0, 0.172), (0.01, 0.172), (0.012, 0.185), (0, 0.19)], segs=14)
    obj(lb, "ПС_чайник_крышка", coll, [m["pot_enamel"]], r, smooth=50)
    hb = bmesh.new()
    pipe(hb, [(-0.07, 0.0, 0.14), (-0.06, 0.0, 0.22), (0.0, 0.0, 0.255), (0.06, 0.0, 0.22), (0.07, 0.0, 0.14)], 0.006, segs=10, bend=0.05)
    obj(hb, "ПС_чайник_ручка", coll, [m["black"]], r, smooth=60)
    return r


def frying_pan(coll, m, at, rng) -> bpy.types.Object:
    """Сковорода чугунная Ø240 с литой ручкой."""
    r = L.root("ПС_сковорода", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.1, 0.0), (0.112, 0.01), (0.12, 0.045), (0.123, 0.048), (0.118, 0.048), (0.106, 0.014), (0.097, 0.006),
               (0.0, 0.006)], segs=48)
    pipe(bm, [(-0.115, 0.0, 0.035), (-0.16, 0.0, 0.045), (-0.29, 0.0, 0.06)], 0.012, segs=10, bend=0.03)
    obj(bm, "ПС_сковорода", coll, [m["burner"]], r, smooth=50)
    return r


def milk_can(coll, m, at, rng) -> bpy.types.Object:
    """Бидон алюминиевый 10 л: Ø230 × 400, горловина, крышка с зажимом, две ручки по бокам и дужка."""
    r = L.root("БД_бидон", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0.0, 0.0), (0.105, 0.0), (0.115, 0.012), (0.115, 0.03), (0.112, 0.033), (0.115, 0.036), (0.115, 0.24),
               (0.1, 0.29), (0.065, 0.32), (0.06, 0.34), (0.066, 0.345), (0.066, 0.352), (0.0, 0.352)], segs=48)
    obj(bm, "БД_корпус", coll, [m["aluminium"]], r, smooth=50)
    lb = bmesh.new()
    lathe(lb, [(0.0, 0.352), (0.07, 0.352), (0.072, 0.36), (0.07, 0.372), (0.0, 0.378)], segs=40)
    pipe(lb, [(-0.07, 0.0, 0.36), (-0.075, 0.0, 0.395), (0.0, 0.0, 0.41), (0.075, 0.0, 0.395), (0.07, 0.0, 0.36)], 0.004, segs=8, bend=0.03)
    obj(lb, "БД_крышка", coll, [m["aluminium"]], r, smooth=60)
    hb = bmesh.new()
    for s in (-1, 1):
        pipe(hb, [(s * 0.112, -0.04, 0.27), (s * 0.135, -0.04, 0.275), (s * 0.14, 0.0, 0.28), (s * 0.135, 0.04, 0.275),
                  (s * 0.112, 0.04, 0.27)], 0.005, segs=8, bend=0.02)
    obj(hb, "БД_ручки", coll, [m["aluminium"]], r, smooth=60)
    return r


def bucket(coll, m, at, rng) -> bpy.types.Object:
    """Бак для отходов — ведро оцинкованное 12 л с крышкой: Ø300 → Ø230, рёбра жёсткости, дужка на ушах."""
    r = L.root("БК_бак", coll, at)
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.115, 0.0), (0.118, 0.008), (0.12, 0.02)]
    for z, rr in ((0.09, 0.128), (0.092, 0.131), (0.096, 0.128), (0.2, 0.138), (0.202, 0.141), (0.206, 0.138), (0.29, 0.148)):
        prof.append((rr, z))
    prof += [(0.153, 0.296), (0.148, 0.3), (0.143, 0.292), (0.141, 0.2), (0.114, 0.012), (0.0, 0.006)]
    lathe(bm, prof, segs=48)
    obj(bm, "БК_ведро", coll, [m["galvanized"]], r, smooth=40)
    lb = bmesh.new()
    lathe(lb, [(0.0, 0.31), (0.12, 0.306), (0.155, 0.298), (0.158, 0.29), (0.153, 0.29), (0.0, 0.302)], segs=48)
    pipe(lb, [(-0.04, 0.0, 0.31), (-0.04, 0.0, 0.33), (0.04, 0.0, 0.33), (0.04, 0.0, 0.31)], 0.004, segs=8, bend=0.01)
    obj(lb, "БК_крышка", coll, [m["galvanized"]], r, smooth=40)
    hb = bmesh.new()
    for s in (-1, 1):
        L.bm_box(hb, (s * 0.148 - 0.005, -0.015, 0.25), (s * 0.148 + 0.005, 0.015, 0.29))
    pts = [(s * 0.152 * math.cos(a), 0.0, 0.27 + 0.0) for s, a in ((-1, 0), (1, 0))]
    arc = [(0.152 * math.cos(t), 0.0, 0.27 + 0.13 * math.sin(t)) for t in [math.pi * k / 16 for k in range(17)]]
    pipe(hb, arc, 0.003, segs=8)
    del pts
    obj(hb, "БК_дужка", coll, [m["galvanized"]], r, smooth=60)
    return r


# ---------------------------------------------------------------- сборка файла

ITEMS = [
    ("Электроплита", stove, 0.5), ("Электроплита — дверца распахнута", lambda c, m, a, g: stove(c, m, a, g, open_door=True), 0.5),
    ("Мойка на тумбе", sink_cabinet, 0.8), ("Стол-тумба", cutting_table, 0.8), ("Обеденный стол", dining_table, 1.2),
    ("Шкафчик навесной", wall_cabinet, 0.8), ("Полка для посуды", dish_shelf, 0.8),
    ("Кастрюля", pot, 0.3), ("Чайник", kettle, 0.3), ("Сковорода", frying_pan, 0.42), ("Бидон", milk_can, 0.3),
    ("Бак для отходов", bucket, 0.33),
    ("Раковина", washbasin, 0.55), ("Раковина — отбита", lambda c, m, a, g: washbasin(c, m, a, g, broken=True), 0.55),
    ("Зеркало", mirror, 0.4),
    ("Унитаз с бачком", toilet, 0.5), ("Унитаз — бачок сорван", lambda c, m, a, g: toilet(c, m, a, g, torn=True), 0.5),
    ("Кабинка", stall, 1.1), ("Кабинка — дверца распахнута", lambda c, m, a, g: stall(c, m, a, g, door="open"), 1.1),
    ("Кабинка — дверца выбита", lambda c, m, a, g: stall(c, m, a, g, door="none"), 1.1),
    ("Перегородка крайняя", partition_end, 0.1),
]
WALL = ("Шкафчик навесной", "Полка для посуды", "Зеркало")
AT_COUNTER = {"Электроплита": 0.3, "Электроплита — дверца распахнута": 0.3, "Мойка на тумбе": 0.3, "Стол-тумба": 0.3}
AT_WALL = ("Раковина", "Раковина — отбита", "Унитаз с бачком", "Унитаз — бачок сорван", "Кабинка",
           "Кабинка — дверца распахнута", "Кабинка — дверца выбита", "Перегородка крайняя")


def build(out: str) -> list:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Мебель_кухня_умывальня_туалеты_v01")
    m = mats()
    rng = random.Random(32)
    x = 0.0
    placed = []
    wall_y = 1.4
    for label, fn, width in ITEMS:
        c = L.collection(label, top)
        cx = x + width / 2
        at = (cx, 0.0, 0.0)
        if label in WALL:
            at = (cx, wall_y, 1.75 if label != "Зеркало" else 1.6)
        elif label in AT_WALL:
            at = (cx, wall_y, 0.0)
        elif label in AT_COUNTER:
            at = (cx, wall_y - AT_COUNTER[label], 0.0)
        elif label in ("Кастрюля", "Чайник", "Сковорода"):
            at = (cx, 0.0, 0.0)
        root = fn(c, m, at, rng)
        placed.append((label, c, root))
        x += width + 0.45
    B.studio(L.collection("Студия"), x)
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


def preview(placed: list, folder: str, only: set | None = None) -> None:
    """Кадры самопроверки: стена студии — у навесного и пристенного."""
    wall = bpy.data.objects.get("студия_стена")
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (label, coll, root) in enumerate(placed):
        if only and i not in only:
            continue
        if wall:
            wall.hide_render = label not in WALL + AT_WALL + tuple(AT_COUNTER)
        pts = []
        for ob in coll.all_objects:
            if ob.type == "MESH" and not ob.hide_render:
                ev = ob.evaluated_get(dg)
                pts += [ev.matrix_world @ V(c) for c in ev.bound_box]
        mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn + mx) / 2
        size = (mx - mn).length
        for k, (az, el) in enumerate(((-35, 22), (40, 38))):
            a, e = math.radians(az), math.radians(el)
            dist = size * 1.3 + 0.25
            cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = 40
            sc.render.filepath = os.path.join(folder, f"{i:02d}_{k}.png")
            bpy.ops.render.render(write_still=True)
        print("preview", label, flush=True)
    if wall:
        wall.hide_render = False


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed = build(argv[0])
    if len(argv) >= 3 and argv[1] == "preview":
        only = {int(s) for s in argv[3].split(",")} if len(argv) >= 4 and argv[3] else None
        preview(placed, argv[2], only)
