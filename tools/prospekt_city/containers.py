"""Морские контейнеры «Проспекта»: ISO 1C (20 футов) и 1AA… 1A (40 футов) — закрыт / двери распахнуты.

Наборы container20 / container40 (src/blockout/mall_filler.gd): 19 + 7 на карте, часть стоит вторым ярусом (2,62 м) —
угловые фитинги сходятся при штабелировании. Размеры по ISO 668: 20' — 6058 × 2438 × 2591 мм, 40' — 12192 × 2438 ×
2591; фитинги ISO 1161 — 178 × 162 × 118 мм, верхнее и нижнее отверстие 124 × 63,5, боковое 78 × 51 (овалы); дверной
проём 20' ≈ 2343 × 2280. Борта — трапециевидный гофр шагом 278 мм, глубина 36; торцевая стенка — гофр 45 мм; крыша —
поперечные выштамповки ~20 мм; днище — поперечины-швеллеры 122 мм через ~300 мм, фанерный пол 28 мм; у 20' —
карманы под вилы (360 × 115, между осями 2050), у 40' — туннель под гусак (≈ 3150 × 1029 × 120) с переднего торца.
Двери: две створки в рамке из труб с горизонтальным гофром, по две запорные штанги Ø 27 мм на створку (кулачки сверху
и снизу входят в упоры перемычки и порога), ручки с фиксаторами, по 4 петли, уплотнитель по контуру; правая
(по виду сзади) створка с нахлёстом — открывается первой.

Оси: длина — Blender Y, двери к −Y (игровое +Z, как тёмная плоскость серого набора); ширина — X; начало — земля, центр.
Створки — на пустышках-шарнирах Hinge_L / Hinge_R (поворот по Z открывает: правая +, левая −).
"""
from __future__ import annotations

import math

import bpy
import numpy as np

import clib as C

W, H = 2.438, 2.591
PAINT = "paint_brown"                # окраска текущего варианта (у 20' и 40' — разная, для различения)
FIT = (0.162, 0.178, 0.118)          # фитинг: по X, по Y, по Z
T_SHEET = 0.002                      # лист гофры (реально 1,6–2,0)
Z_RAIL_B = (0.012, 0.170)            # нижняя продольная балка-швеллер 158 мм (низ фитинга ниже на 12)
Z_FLOOR = (0.142, 0.170)             # фанера 28 мм на поперечинах
Z_TOP_RAIL = (H - 0.066, H - 0.006)  # верхняя продольная — труба 60 × 60
DOOR_Z = (0.170, 0.170 + 2.280)      # дверной проём по высоте
DOOR_HALF = 2.343 / 2


# ---------------------------------------------------------------- листы гофры
def corr_profile(a0: float, a1: float, pitch: float, f_out: float, f_in: float, depth: float) -> list:
    """Трапециевидный гофр по оси a от a0 до a1: (a, b), b = 0 — наружные полки, −depth — внутренние.
    Целые шаги по центру, по краям — наружная полка до конца."""
    slant = (pitch - f_out - f_in) / 2
    n = int((a1 - a0 - f_out) // pitch)
    start = a0 + (a1 - a0 - (n * pitch + f_out)) / 2
    pts = [(a0, 0.0)]
    a = start
    for _ in range(n):
        pts += [(a + f_out, 0.0), (a + f_out + slant, -depth), (a + f_out + slant + f_in, -depth),
                (a + pitch, 0.0)]
        a += pitch
    pts.append((a1, 0.0))
    # убрать совпадающие точки (если гофр начался у самого края)
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def sheet(mb: C.MB, pts, h0: float, h1: float, origin, ea, eb, eh, thick: float = T_SHEET, m: str | None = None) -> None:
    """Лист по профилю (a, b) в плоскости ea/eb, вытянутый по eh от h0 до h1; толщина — внутрь по −eb. Замкнут."""
    m = m or PAINT
    P = np.asarray(pts, float)
    n = len(P)
    o, ea, eb, eh = (np.asarray(v, float) for v in (origin, ea, eb, eh))

    def pt(a: float, b: float, h: float) -> np.ndarray:
        return o + ea * a + eb * b + eh * h
    V = []
    for b_off in (0.0, -thick):
        for h in (h0, h1):
            for a, b in P:
                V.append(pt(a, b + b_off, h))
    # индексы: [слой][высота][i]
    idx = lambda L, k, i: L * 2 * n + k * n + i  # noqa: E731
    F = []
    for i in range(n - 1):
        F.append((idx(0, 0, i), idx(0, 0, i + 1), idx(0, 1, i + 1), idx(0, 1, i)))       # лицо
        F.append((idx(1, 0, i), idx(1, 1, i), idx(1, 1, i + 1), idx(1, 0, i + 1)))       # тыл
        F.append((idx(0, 0, i), idx(1, 0, i), idx(1, 0, i + 1), idx(0, 0, i + 1)))       # низ
        F.append((idx(0, 1, i), idx(0, 1, i + 1), idx(1, 1, i + 1), idx(1, 1, i)))       # верх
    for i in (0, n - 1):
        F.append((idx(0, 0, i), idx(0, 1, i), idx(1, 1, i), idx(1, 0, i)))
    mb.add(np.array(V), F, m)


# ---------------------------------------------------------------- фитинг (шаблон булевыми операциями)
_CASTING = None


def stadium(w: float, h: float, n: int = 10) -> list:
    """Овал-«стадион» w × h (полукруги по коротким сторонам), против часовой."""
    r = min(w, h) / 2
    long_a = w >= h
    cx = (max(w, h) / 2 - r)
    pts = []
    for s, a0 in ((1, -90), (-1, 90)):
        for k in range(n + 1):
            a = math.radians(a0 + 180 * k / n)
            x, y = s * cx + r * math.cos(a), r * math.sin(a)
            pts.append((x, y) if long_a else (y, x))
    return pts


def casting_template() -> tuple:
    """Фитинг верхнего угла (+X, +Y, верх): литая коробка со стенкой 25 мм, овалы сверху, сбоку (+X) и с торца (+Y).
    Возвращает (V, F) в координатах, где наружный угол — (0, 0, 0), тело в −X, −Y, −Z."""
    global _CASTING
    if _CASTING is not None:
        return _CASTING
    fx, fy, fz = FIT
    col = bpy.context.scene.collection
    mb = C.MB()
    mb.extend(C.box((-fx / 2, -fy / 2, -fz / 2), (fx, fy, fz)), "steel")
    body = mb.build("_casting", col, None)
    cutters = []

    def cutter(V, F) -> None:
        m = C.MB()
        m.add(V, F)
        cutters.append(m.build("_cut", col, None))
    # полость
    cutter(*C.box((-fx / 2, -fy / 2, -fz / 2), (fx - 0.05, fy - 0.05, fz - 0.05)))
    # верх: 124 × 63,5, длинная ось вдоль Y
    cutter(*C.prism(stadium(0.0635, 0.124), -0.06, 0.02, origin=(-fx / 2, -fy / 2 + 0.005, 0.0), ex=(1, 0, 0),
                    ey=(0, 1, 0), ez=(0, 0, 1)))
    # бок (+X): 78 × 51, длинная ось вдоль Y
    cutter(*C.prism(stadium(0.078, 0.051), -0.06, 0.02, origin=(0.0, -fy / 2, -fz / 2), ex=(0, 1, 0), ey=(0, 0, 1),
                    ez=(1, 0, 0)))
    # торец (+Y): 51 × 64 по высоте (по ISO 1161 торцевое отверстие ≈ овал поперёк)
    cutter(*C.prism(stadium(0.051, 0.064), -0.06, 0.02, origin=(-fx / 2, 0.0, -fz / 2 - 0.005), ex=(1, 0, 0),
                    ey=(0, 0, 1), ez=(0, 1, 0)))
    for i, c in enumerate(cutters):
        m = body.modifiers.new(f"b{i}", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = c
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = body.evaluated_get(dg).to_mesh()
    V = np.array([v.co[:] for v in me.vertices])
    F = [tuple(p.vertices) for p in me.polygons]
    body.evaluated_get(dg).to_mesh_clear()
    for o in cutters + [body]:
        bpy.data.objects.remove(o, do_unlink=True)
    _CASTING = (V, F)
    return _CASTING


def castings_clean(mb: C.MB, L: float) -> None:
    """Восемь фитингов: шаблон верхнего, зеркально по X/Y и по высоте для нижних (отверстие снизу)."""
    V0, F = casting_template()
    for sx in (-1, 1):
        for sy in (-1, 1):
            for top in (True, False):
                V = V0.copy()
                V[:, 0] *= sx
                V[:, 1] *= sy
                V[:, 2] = (H + V[:, 2]) if top else -V[:, 2]
                V[:, 0] += sx * W / 2
                V[:, 1] += sy * L / 2
                mb.add(V, F, PAINT)


# ---------------------------------------------------------------- каркас
def frame(mb: C.MB, L: float, size20: bool) -> None:
    fx, fy, fz = FIT
    y0, y1 = -L / 2, L / 2
    # передние угловые стойки (глухой торец, +Y): уголок с внутренними отгибами, на 4 мм внутри фитингов
    prof = [(0, 0), (0.150, 0), (0.150, 0.040), (0.144, 0.040), (0.144, 0.006), (0.006, 0.006), (0.006, 0.144),
            (0.040, 0.144), (0.040, 0.150), (0, 0.150)]
    for sx in (-1, 1):
        V, F = C.prism(prof, fz, H - fz, origin=(sx * (W / 2 - 0.004), y1 - 0.004, 0), ex=(-sx, 0, 0), ey=(0, -1, 0),
                       ez=(0, 0, 1))
        mb.add(V, F, PAINT)
    # задние (дверные) стойки: тяжёлый гнутый профиль, лицо 45 мм у проёма на 80 мм за торцом фитингов (перед ним —
    # проушины петель), глубина до 178
    for sx in (-1, 1):
        outer = sx * (W / 2 - 0.003)
        inner = sx * DOOR_HALF
        poly = [(outer, y0 + 0.080), (inner, y0 + 0.080), (inner, y0 + 0.100), (inner + sx * 0.012, y0 + 0.100),
                (inner + sx * 0.012, y0 + fy - 0.012), (inner - sx * 0.030, y0 + fy - 0.012),
                (inner - sx * 0.030, y0 + fy), (outer, y0 + fy)]
        if sx < 0:
            poly = poly[::-1]
        V, F = C.prism(poly, fz, H - fz)
        mb.add(V, F, PAINT)
    # верхние продольные: труба 60 × 60
    for sx in (-1, 1):
        xo = sx * (W / 2 - 0.004)
        mb.extend(C.box2((xo - sx * 0.060, y0 + fy, Z_TOP_RAIL[0]), (xo, y1 - fy, Z_TOP_RAIL[1])), PAINT)
    # нижние продольные: швеллер 158 × 48 × 4,5, стенкой наружу (у 20' — разрывы под карманы)
    pockets = pocket_spans(L) if size20 else []
    for sx in (-1, 1):
        xo = sx * (W / 2 - 0.004)
        ch = [(0, Z_RAIL_B[0]), (0.048, Z_RAIL_B[0]), (0.048, Z_RAIL_B[0] + 0.0045), (0.0045, Z_RAIL_B[0] + 0.0045),
              (0.0045, Z_RAIL_B[1] - 0.0045), (0.048, Z_RAIL_B[1] - 0.0045), (0.048, Z_RAIL_B[1]), (0, Z_RAIL_B[1])]
        cuts = [y0 + fy] + [v for (a, b) in pockets for v in (a, b)] + [y1 - fy]
        for k in range(0, len(cuts), 2):
            V, F = C.prism(ch, cuts[k], cuts[k + 1], origin=(xo, 0, 0), ex=(-sx, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
            mb.add(V, F, PAINT)
    # передняя верхняя поперечная (труба 100 × 60) и нижняя (швеллер)
    mb.extend(C.box2((-W / 2 + fx, y1 - 0.064, H - 0.106), (W / 2 - fx, y1 - 0.004, H - 0.006)), PAINT)
    if size20:
        mb.extend(C.box2((-W / 2 + fx, y1 - 0.052, Z_RAIL_B[0]), (W / 2 - fx, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    else:                                       # у 40' нижняя передняя балка выгнута над входом в туннель под гусак
        tw = 1.029 / 2
        for a, b in ((-W / 2 + fx, -tw - 0.006), (tw + 0.006, W / 2 - fx)):
            mb.extend(C.box2((a, y1 - 0.052, Z_RAIL_B[0]), (b, y1 - 0.004, Z_RAIL_B[1])), PAINT)
        mb.extend(C.box2((-tw - 0.006, y1 - 0.052, 0.132), (tw + 0.006, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    mb.extend(C.box2((-W / 2 + fx, y1 - 0.160, Z_RAIL_B[1] - 0.006), (W / 2 - fx, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    # дверная перемычка (верх) и порог: лицо отступает от торца фитингов на 135 мм (створки с запорами — внутри габарита)
    yf = y0 + 0.135
    mb.extend(C.box2((-W / 2 + fx, yf, DOOR_Z[1]), (W / 2 - fx, y0 + fy + 0.02, H - 0.004)), PAINT)
    mb.extend(C.box2((-DOOR_HALF - 0.01, yf, DOOR_Z[1]), (DOOR_HALF + 0.01, yf + 0.08, H - fz)), PAINT)
    mb.extend(C.box2((-W / 2 + fx, yf, Z_RAIL_B[0]), (W / 2 - fx, y0 + fy + 0.02, DOOR_Z[0])), PAINT)
    mb.extend(C.box2((-DOOR_HALF - 0.01, yf, fz), (DOOR_HALF + 0.01, yf + 0.08, DOOR_Z[0])), PAINT)
    # отбойная полоса перемычки и порога (выступающий пояс по лицу)
    for zc in (DOOR_Z[1] + 0.035, DOOR_Z[0] - 0.035):
        mb.extend(C.box2((-W / 2 + fx + 0.01, yf - 0.012, zc - 0.03), (W / 2 - fx - 0.01, yf, zc + 0.03)), PAINT)


def pocket_spans(L: float) -> list:
    return [(-1.025 - 0.18, -1.025 + 0.18), (1.025 - 0.18, 1.025 + 0.18)]


def underside(mb: C.MB, L: float, size20: bool) -> None:
    """Поперечины днища (швеллер 122, полкой к земле), карманы под вилы (20') или туннель под гусак (40')."""
    y0, y1 = -L / 2 + FIT[1] + 0.05, L / 2 - 0.20
    xa, xb = -W / 2 + 0.05, W / 2 - 0.05
    pockets = pocket_spans(L) if size20 else []
    tunnel = (L / 2 - 3.15, L / 2 - 0.16) if not size20 else None
    tw = 1.029 / 2
    ys = np.arange(y0, y1, 0.30 if size20 else 0.33)
    ch = [(-0.0225, 0.020), (0.0225, 0.020), (0.0225, 0.024), (-0.0185, 0.024), (-0.0185, Z_FLOOR[0] - 0.004),
          (0.0225, Z_FLOOR[0] - 0.004), (0.0225, Z_FLOOR[0]), (-0.0225, Z_FLOOR[0])]
    for y in ys:
        if any(a - 0.04 < y < b + 0.04 for a, b in pockets):
            continue
        spans = [(xa, xb)]
        if tunnel and tunnel[0] < y < tunnel[1]:
            spans = [(xa, -tw - 0.006), (tw + 0.006, xb)]
        for a, b in spans:
            V, F = C.prism(ch, a, b, origin=(0, y, 0), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
            mb.add(V, F, "paint_black")
    for a, b in pockets:                       # карманы: труба 360 × 115 поперёк, ребро-рамка по борту
        z0, z1 = Z_RAIL_B[0], Z_RAIL_B[0] + 0.122
        for (p0, p1) in (((-W / 2 + 0.004, a, z0), (W / 2 - 0.004, b, z0 + 0.006)),
                         ((-W / 2 + 0.004, a, z1 - 0.006), (W / 2 - 0.004, b, z1)),
                         ((-W / 2 + 0.004, a, z0), (W / 2 - 0.004, a + 0.006, z1)),
                         ((-W / 2 + 0.004, b - 0.006, z0), (W / 2 - 0.004, b, z1))):
            mb.extend(C.box2(p0, p1), PAINT)
        for sx in (-1, 1):
            xo = sx * (W / 2 - 0.004)
            mb.extend(C.box2((xo - sx * 0.008, a - 0.03, z1), (xo, b + 0.03, Z_RAIL_B[1])), PAINT)
            mb.extend(C.box2((xo - sx * 0.008, a - 0.03, z0), (xo, a, z1)), PAINT)
            mb.extend(C.box2((xo - sx * 0.008, b, z0), (xo, b + 0.03, z1)), PAINT)
    if tunnel:                                 # туннель: две стенки-швеллера и потолок 120 мм над землёй
        a, b = tunnel
        for sx in (-1, 1):
            mb.extend(C.box2((sx * tw - 0.006, a, 0.012), (sx * tw + 0.006, b, Z_FLOOR[0])), "paint_black")
            mb.extend(C.box2((sx * tw - (0.05 if sx > 0 else -0.006), a, 0.012), (sx * tw + (0.006 if sx > 0 else 0.05),
                                                                                 b, 0.018)), "paint_black")
        mb.extend(C.box2((-tw, a, 0.126), (tw, b, 0.132)), "paint_black")
        mb.extend(C.box2((-tw, a - 0.006, 0.012), (tw, a, 0.132)), "paint_black")


# ---------------------------------------------------------------- стенки, крыша, пол
def walls(mb: C.MB, L: float) -> None:
    fy = FIT[1]
    y0, y1 = -L / 2 + fy, L / 2 - 0.150
    zb, zt = Z_RAIL_B[1] - 0.012, Z_TOP_RAIL[0] + 0.010
    prof = corr_profile(y0, y1, 0.278, 0.072, 0.068, 0.036)
    for sx in (-1, 1):                         # борта: гофр вертикальный, профиль вдоль Y, глубина внутрь
        xo = sx * (W / 2 - 0.006)
        sheet(mb, prof, zb, zt, origin=(xo, 0, 0), ea=(0, 1, 0), eb=(sx, 0, 0), eh=(0, 0, 1))
    # глухой торец: гофр 45 мм, профиль вдоль X
    prof = corr_profile(-W / 2 + 0.150, W / 2 - 0.150, 0.278, 0.072, 0.068, 0.045)
    sheet(mb, prof, Z_RAIL_B[1] - 0.010, H - 0.100, origin=(0, L / 2 - 0.012, 0), ea=(1, 0, 0), eb=(0, 1, 0), eh=(0, 0, 1))
    # крыша: поперечные выштамповки 20 мм через 460 мм, профиль вдоль Y, лист поперёк (по X)
    xs = (-W / 2 + 0.064, W / 2 - 0.064)
    pr = corr_profile(-L / 2 + fy - 0.03, L / 2 - 0.064, 0.46, 0.17, 0.17, 0.020)
    sheet(mb, pr, xs[0], xs[1], origin=(0, 0, H - 0.008), ea=(0, 1, 0), eb=(0, 0, 1), eh=(1, 0, 0), thick=0.002)


def floor(mb: C.MB, L: float) -> None:
    """Фанера 28 мм листами 1160 × 2400 вдоль длины, швы 3 мм; у дверей — стальной порожек."""
    xa, xb = -W / 2 + 0.050, W / 2 - 0.050
    ya, yb = -L / 2 + 0.135 + 0.08, L / 2 - 0.058
    half = (xb - xa) / 2
    for k in range(2):
        x0 = xa + k * half
        y = ya
        while y < yb - 1e-3:
            y2 = min(yb, y + 2.4)
            mb.extend(C.box2((x0 + 0.0015, y + 0.0015, Z_FLOOR[0]), (x0 + half - 0.0015, y2 - 0.0015, Z_FLOOR[1])),
                      "plywood")
            y = y2


def lashing(mb: C.MB, L: float) -> None:
    """Крепёжные проушины (D-кольца) по низу бортов у пола, через ~0,9 м."""
    n = max(2, int((L - 0.6) / 0.9))
    for sx in (-1, 1):
        x = sx * (W / 2 - 0.058)
        for k in range(n):
            y = -L / 2 + 0.4 + k * (L - 0.8) / (n - 1)
            pts = [(x - sx * 0.012 * math.sin(a), y + 0.028 * math.cos(a), Z_FLOOR[1] + 0.006 + 0.03 * math.sin(a))
                   for a in np.linspace(0, math.pi, 9)]
            mb.extend(C.tube(np.array(pts), 0.005, 6), "steel_dark")
            mb.extend(C.box2((x - 0.006, y - 0.035, Z_FLOOR[1]), (x + 0.006, y + 0.035, Z_FLOOR[1] + 0.012)), "steel_dark")


def vents(mb: C.MB, L: float) -> None:
    """Вентрешётки под верхней балкой у торцов: короб 160 × 80 с жалюзи."""
    for sx in (-1, 1):
        xo = sx * (W / 2 - 0.006)
        for y in (-L / 2 + 0.55, L / 2 - 0.50):
            z = Z_TOP_RAIL[0] - 0.07
            # короб утоплен в гофр, жалюзи — в плоскости бортов (ничего не выходит за фитинги)
            mb.extend(C.box2((xo - sx * 0.030, y - 0.08, z - 0.04), (xo + sx * 0.002, y + 0.08, z + 0.04)), PAINT)
            for k in range(4):
                zz = z - 0.03 + k * 0.02
                V, F = C.box((xo - sx * 0.006, y, zz), (0.005, 0.14, 0.012), C.rot("y", sx * 35))
                mb.add(V, F, PAINT)


# ---------------------------------------------------------------- двери


def door_leaf(mb: C.MB, L: float, side: int, panel_m: str | None = None) -> tuple:
    """Створка (side = +1 правая, −1 левая по виду сзади) в координатах контейнера; возвращает ось петель (x, y)."""
    panel_m = panel_m or PAINT
    y0 = -L / 2
    yf = y0 + 0.075                                   # лицо рамки створки
    yb = y0 + 0.125                                   # тыл
    xs, xh = side * 0.002, side * (DOOR_HALF - 0.003)  # у шва и у петель
    z0, z1 = DOOR_Z[0] - 0.035, DOOR_Z[1] + 0.025
    lo, hi = min(xs, xh), max(xs, xh)
    # рамка: стойки 80 мм, верх и низ 100 мм, глубина 50
    mb.extend(C.box2((lo, yf, z0), (lo + 0.08, yb, z1)), panel_m)
    mb.extend(C.box2((hi - 0.08, yf, z0), (hi, yb, z1)), panel_m)
    mb.extend(C.box2((lo + 0.08, yf, z1 - 0.10), (hi - 0.08, yb, z1)), panel_m)
    mb.extend(C.box2((lo + 0.08, yf, z0), (hi - 0.08, yb, z0 + 0.10)), panel_m)
    # полотно: горизонтальный гофр, профиль по Z, утоплено на 8 мм
    pr = corr_profile(z0 + 0.10, z1 - 0.10, 0.44, 0.15, 0.12, 0.030)
    sheet(mb, [(a, b) for a, b in pr], lo + 0.08, hi - 0.08, origin=(0, yf + 0.008, 0), ea=(0, 0, 1), eb=(0, -1, 0),
          eh=(1, 0, 0), m=panel_m)
    # уплотнитель по контуру с тыла
    g = 0.022
    for p0, p1 in (((lo + 0.01, yb, z0 + 0.01), (lo + 0.01 + g, yb + 0.012, z1 - 0.01)),
                   ((hi - 0.01 - g, yb, z0 + 0.01), (hi - 0.01, yb + 0.012, z1 - 0.01)),
                   ((lo + 0.01, yb, z1 - 0.01 - g), (hi - 0.01, yb + 0.012, z1 - 0.01)),
                   ((lo + 0.01, yb, z0 + 0.01), (hi - 0.01, yb + 0.012, z0 + 0.01 + g))):
        mb.extend(C.box2(p0, p1), "rubber")
    if side > 0:                                       # нахлёст правой створки на шов
        mb.extend(C.box2((xs - 0.035, yf - 0.006, z0 + 0.02), (xs + 0.05, yf, z1 - 0.02)), panel_m)
    # петли: лопасть на лице створки до оси
    hx = side * (W / 2 - 0.025)
    hy = y0 + 0.050
    for z in (z0 + 0.25, z0 + 0.85, z1 - 0.85, z1 - 0.25):
        a, b = sorted((hx, hx - side * 0.16))
        mb.extend(C.box2((a, yf - 0.012, z - 0.025), (b, yf, z + 0.025)), panel_m)
        mb.extend(C.cyl((hx, hy, z), 0.018, 0.05, 12), panel_m)
    return hx, hy


def locking_gear(mb: C.MB, L: float, side: int) -> None:
    """Две запорные штанги Ø 27 на створку: кулачки на концах, три скобы, ручка с фиксатором, табличка CSC слева."""
    y0 = -L / 2
    yf = y0 + 0.075
    yb_ = y0 + 0.045                                   # ось штанги
    zt, zb = DOOR_Z[1] + 0.075, DOOR_Z[0] - 0.080
    for k, xa in enumerate((0.26, 0.86)):
        x = side * xa
        mb.extend(C.tube(np.array([(x, yb_, zb), (x, yb_, zt)]), 0.0135, 12), "galv")
        for zc, s in ((zt, 1), (zb, -1)):              # кулачок: перо поперёк штанги
            V, F = C.box((x + side * 0.025, yb_ + 0.012, zc - s * 0.005), (0.06, 0.022, 0.05), C.rot("z", side * 20))
            mb.add(V, F, "galv")
            mb.extend(C.cyl((x, yb_, zc + s * 0.012), 0.016, 0.026, 12), "galv")
        for zg in (DOOR_Z[0] + 0.12, 1.30, DOOR_Z[1] - 0.12):   # скобы-направляющие
            mb.extend(C.box2((x - 0.03, yb_ - 0.0175, zg - 0.03), (x - 0.02, yf, zg + 0.03)), "galv")
            mb.extend(C.box2((x + 0.02, yb_ - 0.0175, zg - 0.03), (x + 0.03, yf, zg + 0.03)), "galv")
            mb.extend(C.box2((x - 0.03, yb_ - 0.0215, zg - 0.03), (x + 0.03, yb_ - 0.0175, zg + 0.03)), "galv")
        # ручка: ступица на штанге, полоса 330 мм к правому краю вида (+X), конец отогнут; фиксатор на створке
        zh = 1.05 if k == 0 else 1.18
        mb.extend(C.cyl((x, yb_, zh), 0.021, 0.07, 12), "galv")
        pts = np.array([(x, yb_ - 0.016, zh), (x + 0.12, yb_ - 0.020, zh), (x + 0.30, yb_ - 0.020, zh),
                        (x + 0.33, yb_ - 0.030, zh)])                 # конец отогнут, но в габарите фитингов
        mb.extend(C.sweep(C.rect_profile(0.012, 0.035, 0.003, 2), pts, up=(0, 0, 1)), "galv")
        hx = x + 0.30
        mb.extend(C.box2((hx - 0.03, yb_ - 0.01, zh - 0.05), (hx + 0.03, yf, zh - 0.03)), "galv")
        mb.extend(C.box2((hx - 0.03, yb_ - 0.04, zh - 0.05), (hx - 0.022, yb_ - 0.01, zh + 0.03)), "galv")
        mb.extend(C.box2((hx + 0.022, yb_ - 0.04, zh - 0.05), (hx + 0.03, yb_ - 0.01, zh + 0.03)), "galv")
    if side < 0:                                       # табличка CSC и таможенная пломба
        mb.extend(C.box2((-0.75, yf - 0.005, 1.55), (-0.53, yf, 1.68)), "galv")


def keepers(mb: C.MB, L: float) -> None:
    """Упоры кулачков на перемычке и пороге — у каждой штанги."""
    y0 = -L / 2
    yf = y0 + 0.135
    for side in (-1, 1):
        for xa in (0.26, 0.86):
            x = side * xa
            for zc, s in ((DOOR_Z[1] + 0.075, 1), (DOOR_Z[0] - 0.080, -1)):
                mb.extend(C.box2((x - 0.045, y0 + 0.022, zc - 0.035), (x + 0.045, yf, zc - 0.025)), PAINT)
                mb.extend(C.box2((x - 0.045, y0 + 0.022, zc + 0.025), (x + 0.045, yf, zc + 0.035)), PAINT)
                mb.extend(C.box2((x + side * 0.035, y0 + 0.022, zc - 0.035), (x + side * 0.045, yf, zc + 0.035)),
                          PAINT)


def post_lugs(mb: C.MB, L: float) -> None:
    """Проушины петель на задних стойках."""
    y0 = -L / 2
    for side in (-1, 1):
        hx = side * (W / 2 - 0.025)
        for z in (DOOR_Z[0] - 0.035 + 0.25, DOOR_Z[0] - 0.035 + 0.85, DOOR_Z[1] + 0.025 - 0.85, DOOR_Z[1] + 0.025 - 0.25):
            for dz in (-0.045, 0.045):
                a, b = sorted((hx - side * 0.02, W / 2 * side - side * 0.004))
                mb.extend(C.box2((a, y0 + 0.032, z + dz - 0.012), (b, y0 + 0.085, z + dz + 0.012)), PAINT)
            mb.extend(C.cyl((hx, y0 + 0.050, z), 0.010, 0.14, 10), "galv")


# ---------------------------------------------------------------- сборка варианта
def container(col, parent, L: float, size20: bool, opened: bool, paint: str) -> None:
    global PAINT
    PAINT = paint
    st = C.MB()
    castings_clean(st, L)
    st.build("CNT_Castings", col, parent, bevel=0.004, seg=2)
    fr = C.MB()
    frame(fr, L, size20)
    fr.build("CNT_Frame", col, parent, bevel=0.0018, seg=2)
    wl = C.MB()
    walls(wl, L)
    wl.build("CNT_Walls", col, parent, bevel=0.006, seg=2, bevel_angle=25)
    un = C.MB()
    underside(un, L, size20)
    un.build("CNT_Underside", col, parent, bevel=0.0012, seg=1)
    fl = C.MB()
    floor(fl, L)
    fl.build("CNT_Floor", col, parent, bevel=0.0015, seg=1)
    dt = C.MB()
    lashing(dt, L)
    vents(dt, L)
    keepers(dt, L)
    post_lugs(dt, L)
    dt.build("CNT_Details", col, parent, bevel=0.0015, seg=1)
    for side, nm in ((1, "R"), (-1, "L")):
        lf = C.MB()
        hx, hy = door_leaf(lf, L, side)
        gear = C.MB()
        locking_gear(gear, L, side)
        ang = 0.0
        if opened:
            ang = 255.0 if side > 0 else -108.0
        pv = C.pivot(f"Hinge_{nm}", col, parent, (hx, hy, 0.0), (0.0, 0.0, math.radians(ang)))
        for mb_, name, bev in ((lf, f"CNT_Door_{nm}", 0.003), (gear, f"CNT_DoorGear_{nm}", 0.0015)):
            mb_.V = [v - np.array([hx, hy, 0.0]) for v in mb_.V]
            mb_.build(name, col, pv, bevel=bev, seg=1)


VARIANTS = {"c20_closed": "20 футов · закрыт", "c20_open": "20 футов · открыт",
            "c40_closed": "40 футов · закрыт", "c40_open": "40 футов · открыт"}
STEP = 4.0
META = {
    "folder": "Контейнеры", "name": "Containers_ISO", "title": "Морские контейнеры 20 и 40 футов",
    "step": 4.0,
    "shots": [["3/4 с дверей", [3.6, -8.0, 2.6], [0.0, -2.0, 1.2], 30], ["3/4 с торца и борта", [-5.0, 7.6, 3.4], [0.0, 0.6, 1.2], 30],
              ["запоры и фитинг", [1.75, -4.45, 0.95], [0.85, -3.0, 0.65], 30]],
    "shots_by": {
        "c20_open": [["3/4 с дверей", [3.8, -8.4, 2.4], [0.0, -2.0, 1.1], 28], ["внутрь", [0.25, -5.3, 1.65], [0.0, 1.5, 1.0], 22],
                     ["шарнир и фитинг", [2.3, -3.9, 0.6], [1.25, -3.0, 0.4], 35]],
        "c40_closed": [["3/4 с дверей", [4.6, -13.6, 3.0], [0.0, -4.5, 1.2], 30],
                       ["3/4 с торца и борта", [-6.5, 12.5, 4.2], [0.0, 1.5, 1.2], 30],
                       ["туннель под гусак", [0.9, 8.6, 0.10], [0.0, 4.0, 0.07], 30]],
        "c40_open": [["3/4 с дверей", [4.6, -14.0, 2.8], [0.0, -4.5, 1.1], 28], ["внутрь", [0.25, -8.4, 1.65], [0.0, 2.0, 1.0], 22],
                     ["шарнир и фитинг", [2.3, -7.0, 0.6], [1.25, -6.1, 0.4], 35]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"CNT | {name}", col, (i * STEP, 0.0, 0.0))
        size20 = k.startswith("c20")
        container(col, r, 6.058 if size20 else 12.192, size20, k.endswith("open"),
                  "paint_brown" if size20 else "paint_blue")
        out[k] = name
    return out
