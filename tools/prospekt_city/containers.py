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
def frame(mb: C.MB, L: float, size20: bool, box=None) -> None:
    """Каркас; box(p0, p1) → (V, F) — чем строить прямоугольные брусья (по умолчанию C.box2; в игре — призмы _bar)."""
    _fb = C.box2 if box is None else box
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
        mb.extend(_fb((xo - sx * 0.060, y0 + fy, Z_TOP_RAIL[0]), (xo, y1 - fy, Z_TOP_RAIL[1])), PAINT)
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
    mb.extend(_fb((-W / 2 + fx, y1 - 0.064, H - 0.106), (W / 2 - fx, y1 - 0.004, H - 0.006)), PAINT)
    if size20:
        mb.extend(_fb((-W / 2 + fx, y1 - 0.052, Z_RAIL_B[0]), (W / 2 - fx, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    else:                                       # у 40' нижняя передняя балка выгнута над входом в туннель под гусак
        tw = 1.029 / 2
        for a, b in ((-W / 2 + fx, -tw - 0.006), (tw + 0.006, W / 2 - fx)):
            mb.extend(_fb((a, y1 - 0.052, Z_RAIL_B[0]), (b, y1 - 0.004, Z_RAIL_B[1])), PAINT)
        mb.extend(_fb((-tw - 0.006, y1 - 0.052, 0.132), (tw + 0.006, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    mb.extend(_fb((-W / 2 + fx, y1 - 0.160, Z_RAIL_B[1] - 0.006), (W / 2 - fx, y1 - 0.004, Z_RAIL_B[1])), PAINT)
    # дверная перемычка (верх) и порог: лицо отступает от торца фитингов на 135 мм (створки с запорами — внутри габарита)
    yf = y0 + 0.135
    mb.extend(_fb((-W / 2 + fx, yf, DOOR_Z[1]), (W / 2 - fx, y0 + fy + 0.02, H - 0.004)), PAINT)
    mb.extend(_fb((-DOOR_HALF - 0.01, yf, DOOR_Z[1]), (DOOR_HALF + 0.01, yf + 0.08, H - fz)), PAINT)
    mb.extend(_fb((-W / 2 + fx, yf, Z_RAIL_B[0]), (W / 2 - fx, y0 + fy + 0.02, DOOR_Z[0])), PAINT)
    mb.extend(_fb((-DOOR_HALF - 0.01, yf, fz), (DOOR_HALF + 0.01, yf + 0.08, DOOR_Z[0])), PAINT)
    # отбойная полоса перемычки и порога (выступающий пояс по лицу)
    for zc in (DOOR_Z[1] + 0.035, DOOR_Z[0] - 0.035):
        mb.extend(_fb((-W / 2 + fx + 0.01, yf - 0.012, zc - 0.03), (W / 2 - fx - 0.01, yf, zc + 0.03)), PAINT)


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
    # игровая версия (game_previews.py): варианты по порядку game.py — VARIANTS, затем цвета GAME["extra"]
    "game_shots": [["3/4 с дверей", [3.6, -8.0, 2.6], [0.0, -2.0, 1.2], 30],
                   ["3/4 с торца и борта", [-5.0, 7.6, 3.4], [0.0, 0.6, 1.2], 30],
                   ["двери с глаз", [1.3, -4.9, 1.65], [0.2, -3.0, 1.2], 32]],
    "game_shots_by": {
        "c20_open": [["3/4 с дверей", [3.8, -8.4, 2.4], [0.0, -2.0, 1.1], 28], ["внутрь", [0.25, -5.3, 1.65], [0.0, 1.5, 1.0], 22],
                     ["створки с глаз", [2.4, -4.6, 1.65], [0.6, -3.0, 1.2], 30]],
        "c40_closed": [["3/4 с дверей", [4.6, -13.6, 3.0], [0.0, -4.5, 1.2], 30],
                       ["3/4 с торца и борта", [-6.5, 12.5, 4.2], [0.0, 1.5, 1.2], 30],
                       ["двери с глаз", [1.3, -8.0, 1.65], [0.2, -6.1, 1.2], 32]],
        "c40_open": [["3/4 с дверей", [4.6, -14.0, 2.8], [0.0, -4.5, 1.1], 28], ["внутрь", [0.25, -8.4, 1.65], [0.0, 2.0, 1.0], 22],
                     ["створки с глаз", [2.4, -7.7, 1.65], [0.6, -6.1, 1.2], 30]],
        "c40_closed_blue": [["3/4 с дверей", [4.6, -13.6, 3.0], [0.0, -4.5, 1.2], 30],
                            ["3/4 с торца и борта", [-6.5, 12.5, 4.2], [0.0, 1.5, 1.2], 30],
                            ["двери с глаз", [1.3, -8.0, 1.65], [0.2, -6.1, 1.2], 32]],
        "c40_closed_green": [["3/4 с дверей", [4.6, -13.6, 3.0], [0.0, -4.5, 1.2], 30],
                             ["3/4 с торца и борта", [-6.5, 12.5, 4.2], [0.0, 1.5, 1.2], 30],
                             ["двери с глаз", [1.3, -8.0, 1.65], [0.2, -6.1, 1.2], 32]],
        "c40_closed_beige": [["3/4 с дверей", [4.6, -13.6, 3.0], [0.0, -4.5, 1.2], 30],
                             ["3/4 с торца и борта", [-6.5, 12.5, 4.2], [0.0, 1.5, 1.2], 30],
                             ["двери с глаз", [1.3, -8.0, 1.65], [0.2, -6.1, 1.2], 32]],
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


# ================================================================ игровая версия (LOD0)
# Наборы Painter: C20 / C40 — всё снаружи (гофра бортов, торца и крыши — односторонние поверхности по тому же профилю,
# что у формы; каркас — тот же, что у формы; фитинги — коробки, отверстия запекаются; двери и запоры — простыми объёмами;
# поперечины днища — копии одной), C20In / C40In — нутро открытых (изнанка гофры, фанерный пол). Борт −X — зеркальная
# копия +X, фитинги — копии одного, створки открытых — сетки закрытых, повёрнутые на петлях (общая развёртка).
# Проушины, вентрешётки, упоры кулачков, скобы штанг, уплотнитель, табличка — только в запекании.
# Цвета: основной — ржаво-красный; синий, зелёный, бежевый — те же сетки с другой картой цвета (containers_colors.py:
# выгрузка цвета из Painter и копии вариантов с материалами «<набор>_<цвет>»). Ящики коллизии открытых — борта, крыша,
# торец, пол и распахнутые створки (внутрь можно зайти); у закрытых — габарит. Оси Blender, [центр, размер].
_HW = 2.438 / 2
GAME = {
    "ids": {"c20_closed": "PC03_C20", "c20_open": "PC03_C20_OPEN", "c40_closed": "PC03_C40", "c40_open": "PC03_C40_OPEN",
            "c20_closed_blue": "PC03_C20_BLUE", "c20_closed_green": "PC03_C20_GREEN", "c20_closed_beige": "PC03_C20_BEIGE",
            "c40_closed_blue": "PC03_C40_BLUE", "c40_closed_green": "PC03_C40_GREEN", "c40_closed_beige": "PC03_C40_BEIGE"},
    "extra": {"c20_closed_blue": "20 футов · закрыт · синий", "c20_closed_green": "20 футов · закрыт · зелёный",
              "c20_closed_beige": "20 футов · закрыт · бежевый", "c40_closed_blue": "40 футов · закрыт · синий",
              "c40_closed_green": "40 футов · закрыт · зелёный", "c40_closed_beige": "40 футов · закрыт · бежевый"},
    "bake": ["c20_closed", "c20_open", "c40_closed", "c40_open"],
    "skip_high": [],
    "res": {"C20": 11, "C40": 11, "C20In": 11, "C40In": 11},
    "solids": {
        "c20_open": [[[1.169, 0.0, 1.2955], [0.10, 6.058, 2.591]], [[-1.169, 0.0, 1.2955], [0.10, 6.058, 2.591]],
                     [[0.0, 0.0, 2.541], [2.438, 6.058, 0.10]], [[0.0, 2.979, 1.2955], [2.438, 0.10, 2.591]],
                     [[0.0, 0.0, 0.085], [2.438, 6.058, 0.17]], [[1.34, -2.43, 1.3], [0.25, 1.15, 2.40]],
                     [[-1.38, -3.54, 1.3], [0.45, 1.12, 2.40]]],
        "c40_open": [[[1.169, 0.0, 1.2955], [0.10, 12.192, 2.591]], [[-1.169, 0.0, 1.2955], [0.10, 12.192, 2.591]],
                     [[0.0, 0.0, 2.541], [2.438, 12.192, 0.10]], [[0.0, 6.046, 1.2955], [2.438, 0.10, 2.591]],
                     [[0.0, 0.0, 0.085], [2.438, 12.192, 0.17]], [[1.34, -5.50, 1.3], [0.25, 1.15, 2.40]],
                     [[-1.38, -6.61, 1.3], [0.45, 1.12, 2.40]]],
    },
}
# цвет краски (sRGB) — стек Painter (sp/stack_containers.py) берёт тот же список
PAINTS = {"red": (0.44, 0.17, 0.11), "blue": (0.15, 0.27, 0.44), "green": (0.20, 0.35, 0.25), "beige": (0.62, 0.55, 0.42)}
CORR_SHARP = 15.0                    # гофра гнётся резко: грани профиля — не сглаживать между собой


def _surf(mb: C.MB, pts, h0: float, h1: float, origin, ea, eb, eh, b_off: float, normal, m: str) -> None:
    """Односторонняя поверхность по профилю (a, b) от h0 до h1 по eh; нормаль — в сторону normal."""
    P = np.asarray(pts, float)
    n = len(P)
    o, ea, eb, eh = (np.asarray(v, float) for v in (origin, ea, eb, eh))
    V = np.array([o + ea * a + eb * (b + b_off) + eh * h for h in (h0, h1) for a, b in P])
    F = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    v0, v1, v2 = V[F[0][0]], V[F[0][1]], V[F[0][2]]
    if np.cross(v1 - v0, v2 - v0) @ np.asarray(normal, float) < 0:
        F = [f[::-1] for f in F]
    mb.add(V, F, m)


def _gpart(mb: C.MB, name: str, ts: str, mat: str, col, parent, sharp: float = 30.0, recalc: bool = True):
    """Деталь LOD0 (как game_lib.part), но с выбором пересчёта нормалей: у односторонних листов направление задано."""
    import game_lib as G
    for i in range(len(mb.S)):
        mb.S[i] = True
    mb.M = ["concrete"] * len(mb.M)
    ob = mb.build(f"{ts}__{mat}__{name}", col, parent, bevel=0.0, sharp=sharp, weld=0.0, recalc=recalc)
    ob.data.materials.clear()
    ob.data.materials.append(G.set_material(ts))
    ob["tex_set"], ob["mat"], ob["part"] = ts, mat, name
    return ob


def _mat(R=None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def _hinge(hx: float, hy: float, deg: float) -> np.ndarray:
    """Поворот вокруг вертикальной оси петель (hx, hy)."""
    R = C.rot("z", deg)
    return _mat(R, np.array([hx, hy, 0.0]) - R @ np.array([hx, hy, 0.0]))


# развёртка по нормам навыка: лист гофры — одной выпрямленной полосой (U — по профилю в развёрнутую длину, V — по
# высоте), длинная — кусками по UV_PIECE м; крыша видна только сверху (×0,6), днище — малая доля (×0,35)
UV_PIECE = 3.2
ROOF_UV_RULES = '[["z", 1, 0.9, 0.6]]'


def _strip_uv(ob, surfs: int = 1, piece: float = UV_PIECE) -> None:
    """Лист из surfs поверхностей _surf подряд (у каждой два ряда по n точек) — полосой: game_lib.grid_uv + разрез."""
    import game_lib as G
    nv = len(ob.data.vertices)
    chunk = nv // surfs
    G.grid_uv(ob, [chunk] * surfs, [chunk // 2] * surfs)
    G.split_islands_uv(ob, piece)
    ob["uv_half"] = True                              # куски одного листа — половинный отступ (6 px)


def _bar(p0, p1) -> tuple:
    """Прямоугольный брус как призма вдоль длинной оси (развёртка — одной полосой и двумя торцами, не шестью
    островами коробки): тот же объём, что C.box2(p0, p1)."""
    lo, hi = np.minimum(p0, p1).astype(float), np.maximum(p0, p1).astype(float)
    d = hi - lo
    ax = int(np.argmax(d))
    a0, a1 = [i for i in range(3) if i != ax]
    ex, ey, ez = np.zeros(3), np.zeros(3), np.zeros(3)
    ex[a0], ey[a1], ez[ax] = 1.0, 1.0, 1.0
    poly = [(0.0, 0.0), (d[a0], 0.0), (d[a0], d[a1]), (0.0, d[a1])]
    return C.prism(poly, 0.0, d[ax], origin=lo, ex=ex, ey=ey, ez=ez)


def _rbox(c, sz, R) -> tuple:
    """Повёрнутая коробка (как C.box(c, sz, R)) — призмой вдоль третьей оси."""
    R = np.asarray(R, float)
    w, h, t = sz
    poly = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return C.prism(poly, -t / 2, t / 2, origin=c, ex=R[:, 0], ey=R[:, 1], ez=R[:, 2])


def _prism_uv(ob, mb: C.MB, piece: float = UV_PIECE) -> None:
    """Деталь из призм (брусья, трубки, цилиндры — по два кольца точек): каждая — полосой и торцами
    (game_lib.prism_strip_uv), длинные — разрезаны поперёк Y кусками по piece (12-метровая балка иначе ложится
    полосой на всю ширину атласа)."""
    import bmesh

    import game_lib as G
    G.prism_strip_uv(ob, [len(v) for v in mb.V])
    ob["uv_half"] = True                              # профили одной детали — половинный отступ
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uvl = bm.loops.layers.uv.active
    # торцы-четырёхугольники брусьев game_lib.prism_strip_uv принимает за боковые грани (у них V одинаковый —
    # развёртка вырождена): такие грани — плоской проекцией на свою плоскость, в метрах
    for f in bm.faces:
        vs = [lp[uvl].uv[1] for lp in f.loops]
        us = [lp[uvl].uv[0] for lp in f.loops]
        if max(vs) - min(vs) < 1e-9 or max(us) - min(us) < 1e-9:
            n = f.normal
            e1 = n.orthogonal().normalized()
            e2 = n.cross(e1)
            for lp in f.loops:
                lp[uvl].uv = (lp.vert.co.dot(e1), lp.vert.co.dot(e2))
    ys = [v.co.y for v in bm.verts]
    y0 = min(ys)
    y = math.floor(y0 / piece) * piece + piece
    while y < max(ys) - 1e-3:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0.0, y, 0.0),
                               plane_no=(0.0, 1.0, 0.0))
        y += piece
    uvl = bm.loops.layers.uv.active
    for f in bm.faces:
        k = int(math.floor((f.calc_center_median().y - y0) / piece))
        if k:
            for lp in f.loops:
                lp[uvl].uv = (lp[uvl].uv[0] + 1000.0 * k, lp[uvl].uv[1])
    bm.to_mesh(ob.data)
    bm.free()


def _box_pieces(ob, piece: float = UV_PIECE) -> None:
    """Коробки и балки (каркас, пол) — коробочной проекцией в метрах, длинные острова — кусками piece × piece
    (по середине грани): 12-метровая балка иначе ложится полосой на всю ширину атласа и ужимает остальное."""
    import bmesh

    import game_lib as G
    bm = bmesh.new()                                  # длинные грани (балка, пол — по одной грани) режутся поперёк
    bm.from_mesh(ob.data)
    ys = [v.co.y for v in bm.verts]
    y = math.floor(min(ys) / piece) * piece + piece
    while y < max(ys) - 1e-3:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0.0, y, 0.0), plane_no=(0.0, 1.0, 0.0))
        y += piece
    bm.to_mesh(ob.data)
    bm.free()
    G.box_unwrap(ob)
    ob["uv_half"] = True
    me = ob.data
    uv = me.uv_layers.active.data
    for p in me.polygons:
        cu = sum(uv[li].uv[0] for li in p.loop_indices) / p.loop_total
        cv = sum(uv[li].uv[1] for li in p.loop_indices) / p.loop_total
        k = int(math.floor(cu / piece)) * 101 + int(math.floor(cv / piece))
        if k:
            for li in p.loop_indices:
                uv[li].uv = (uv[li].uv[0], uv[li].uv[1] + 1000.0 * k)


def _piece(L: float) -> float:
    """Длина куска полосы: у 20' мельче — немного крупных островов иначе плохо складываются в атлас."""
    return 1.6 if L < 7.0 else UV_PIECE


def _walls_low(L: float, outer: bool, ts: str, col, parent, mat: str) -> list:
    """Борт +X (−X — зеркальная копия), глухой торец и крыша: лицо (outer) или изнанка листа. Развёртка — полосами."""
    fy = FIT[1]
    out = []
    y0, y1 = -L / 2 + fy, L / 2 - 0.150
    zb, zt = Z_RAIL_B[1] - 0.012, Z_TOP_RAIL[0] + 0.010
    b_off = 0.0 if outer else -T_SHEET
    sg = 1.0 if outer else -1.0
    mb = C.MB()
    _surf(mb, corr_profile(y0, y1, 0.278, 0.072, 0.068, 0.036), zb, zt, (_HW - 0.006, 0, 0), (0, 1, 0), (1, 0, 0),
          (0, 0, 1), b_off, (sg, 0, 0), "x")
    out.append(_gpart(mb, "wall", ts, mat, col, parent, CORR_SHARP, recalc=False))
    mb = C.MB()
    _surf(mb, corr_profile(-_HW + 0.150, _HW - 0.150, 0.278, 0.072, 0.068, 0.045), Z_RAIL_B[1] - 0.010, H - 0.100,
          (0, L / 2 - 0.012, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), b_off, (0, sg, 0), "x")
    out.append(_gpart(mb, "end", ts, mat, col, parent, CORR_SHARP, recalc=False))
    mb = C.MB()
    _surf(mb, corr_profile(-L / 2 + fy - 0.03, L / 2 - 0.064, 0.46, 0.17, 0.17, 0.020), -_HW + 0.064, _HW - 0.064,
          (0, 0, H - 0.008), (0, 1, 0), (0, 0, 1), (1, 0, 0), b_off if outer else -0.002, (0, 0, sg), "x")
    out.append(_gpart(mb, "roof", ts, mat, col, parent, CORR_SHARP, recalc=False))
    for o in out:
        _strip_uv(o, piece=_piece(L))
    out[2]["uv_rules"] = ROOF_UV_RULES
    return out


def _door_low(mb: C.MB, mp: C.MB, mg: C.MB, L: float, side: int) -> tuple:
    """Створка для игры: рамка, нахлёст, петли (mb); гофрированное полотно — лицо и изнанка (mp, односторонние);
    запоры (mg)."""
    y0 = -L / 2
    yf, yb = y0 + 0.075, y0 + 0.125
    xs, xh = side * 0.002, side * (DOOR_HALF - 0.003)
    z0, z1 = DOOR_Z[0] - 0.035, DOOR_Z[1] + 0.025
    lo, hi = min(xs, xh), max(xs, xh)
    mb.extend(_bar((lo, yf, z0), (lo + 0.08, yb, z1)), "x")
    mb.extend(_bar((hi - 0.08, yf, z0), (hi, yb, z1)), "x")
    mb.extend(_bar((lo + 0.08, yf, z1 - 0.10), (hi - 0.08, yb, z1)), "x")
    mb.extend(_bar((lo + 0.08, yf, z0), (hi - 0.08, yb, z0 + 0.10)), "x")
    pr = corr_profile(z0 + 0.10, z1 - 0.10, 0.44, 0.15, 0.12, 0.030)
    _surf(mp, pr, lo + 0.08, hi - 0.08, (0, yf + 0.008, 0), (0, 0, 1), (0, -1, 0), (1, 0, 0), 0.0, (0, -1, 0), "x")
    _surf(mp, pr, lo + 0.08, hi - 0.08, (0, yf + 0.008, 0), (0, 0, 1), (0, -1, 0), (1, 0, 0), -T_SHEET, (0, 1, 0), "x")
    if side > 0:
        mb.extend(_bar((xs - 0.035, yf - 0.006, z0 + 0.02), (xs + 0.05, yf, z1 - 0.02)), "x")
    hx, hy = side * (_HW - 0.025), y0 + 0.050
    for z in (z0 + 0.25, z0 + 0.85, z1 - 0.85, z1 - 0.25):
        a, b = sorted((hx, hx - side * 0.16))
        mb.extend(_bar((a, yf - 0.012, z - 0.025), (b, yf, z + 0.025)), "x")
        mb.extend(C.cyl((hx, hy, z), 0.018, 0.05, 6), "x")
    # запоры: штанга, кулачки, ступица и ручка с фиксатором
    yb_ = y0 + 0.045
    zt, zbb = DOOR_Z[1] + 0.075, DOOR_Z[0] - 0.080
    for k, xa in enumerate((0.26, 0.86)):
        x = side * xa
        mg.extend(C.tube(np.array([(x, yb_, zbb - 0.01), (x, yb_, zt + 0.01)]), 0.0135, 6), "x")
        for zc, s in ((zt, 1), (zbb, -1)):
            V, F = _rbox((x + side * 0.025, yb_ + 0.012, zc - s * 0.005), (0.06, 0.022, 0.05), C.rot("z", side * 20))
            mg.add(V, F, "x")
        zh = 1.05 if k == 0 else 1.18
        mg.extend(_bar((x - 0.021, yb_ - 0.021, zh - 0.035), (x + 0.021, yb_ + 0.021, zh + 0.035)), "x")
        mg.extend(_bar((x, yb_ - 0.026, zh - 0.0175), (x + 0.33, yb_ - 0.014, zh + 0.0175)), "x")
        hx2 = x + 0.30
        mg.extend(_bar((hx2 - 0.03, yb_ - 0.04, zh - 0.05), (hx2 + 0.03, yf, zh - 0.03)), "x")
    return hx, hy


def _castings_low(L: float, ts: str, col, parent) -> None:
    """Фитинг — коробка (отверстия в запекании); восемь мест — копии одного, зеркально по X, Y и высоте."""
    import game_lib as G
    fx, fy, fz = FIT
    mb = C.MB()
    mb.extend(_bar((_HW - fx, L / 2 - fy, H - fz), (_HW, L / 2, H)), "x")
    m = _gpart(mb, "casting", ts, "paint", col, parent, 30.0)
    _prism_uv(m, mb)
    for sx in (1, -1):
        for sy in (1, -1):
            for top in (True, False):
                if sx == 1 and sy == 1 and top:
                    continue
                G.instance(m, col, parent, _mat(np.diag([sx, sy, 1.0 if top else -1.0]), (0, 0, 0.0 if top else H)))


def _underside_low(L: float, size20: bool, ts: str, col, parent) -> None:
    """Поперечины — копии одной коробки по местам формы; карманы под вилы (20') и туннель (40') — коробками."""
    import game_lib as G
    y0, y1 = -L / 2 + FIT[1] + 0.05, L / 2 - 0.20
    xa, xb = -_HW + 0.05, _HW - 0.05
    pockets = pocket_spans(L) if size20 else []
    tw = 1.029 / 2
    tunnel = (L / 2 - 3.15, L / 2 - 0.16) if not size20 else None
    ys = np.arange(y0, y1, 0.30 if size20 else 0.33)
    full = short = None
    for y in ys:
        if any(a - 0.04 < y < b + 0.04 for a, b in pockets):
            continue
        if tunnel and tunnel[0] < y < tunnel[1]:
            if short is None:
                mb = C.MB()
                mb.extend(_bar((tw + 0.006, y - 0.0225, 0.020), (xb, y + 0.0225, Z_FLOOR[0])), "x")
                short = _gpart(mb, "cross_short", ts, "under", col, parent, 30.0)
                _prism_uv(short, mb)
                short["uv_scale"] = 0.35
                G.instance(short, col, parent, _mat(np.diag([-1.0, 1.0, 1.0])))
                y_short = y
            else:
                G.instance(short, col, parent, _mat(None, (0, y - y_short, 0)))
                G.instance(short, col, parent, _mat(np.diag([-1.0, 1.0, 1.0]), (0, y - y_short, 0)))
            continue
        if full is None:
            mb = C.MB()
            mb.extend(_bar((xa, y - 0.0225, 0.020), (xb, y + 0.0225, Z_FLOOR[0])), "x")
            full = _gpart(mb, "cross", ts, "under", col, parent, 30.0)
            _prism_uv(full, mb)
            full["uv_scale"] = 0.35
            y_full = y
        else:
            G.instance(full, col, parent, _mat(None, (0, y - y_full, 0)))
    mb = C.MB()
    for a, b in pockets:
        z0, z1 = Z_RAIL_B[0], Z_RAIL_B[0] + 0.122
        for (p0, p1) in (((-_HW + 0.004, a, z0), (_HW - 0.004, b, z0 + 0.006)),
                         ((-_HW + 0.004, a, z1 - 0.006), (_HW - 0.004, b, z1)),
                         ((-_HW + 0.004, a, z0), (_HW - 0.004, a + 0.006, z1)),
                         ((-_HW + 0.004, b - 0.006, z0), (_HW - 0.004, b, z1))):
            mb.extend(_bar(p0, p1), "x")
    if tunnel:
        a, b = tunnel
        for sx in (-1, 1):
            mb.extend(_bar((sx * tw - 0.006, a, 0.012), (sx * tw + 0.006, b, Z_FLOOR[0])), "x")
        mb.extend(_bar((-tw, a, 0.126), (tw, b, 0.132)), "x")
        mb.extend(_bar((-tw, a - 0.006, 0.012), (tw, a, 0.132)), "x")
    if not mb.empty():
        pk = _gpart(mb, "pockets", ts, "under", col, parent, 30.0)
        _prism_uv(pk, mb)
        pk["uv_scale"] = 0.5


def game(col, parent, key: str, ctx: dict) -> None:
    """Игровые детали варианта key (game.py): закрытые — источник сеток, открытые и цвета — их копии."""
    import game_lib as G
    if key in GAME["extra"]:                          # цвет: копии деталей закрытого (карты — containers_colors.py)
        base = key.rsplit("_", 1)[0]
        for o in ctx[base]:
            G.instance(o, col, parent)
        return
    size20 = key.startswith("c20")
    L = 6.058 if size20 else 12.192
    ts = "C20" if size20 else "C40"
    opened = key.endswith("open")
    if not opened:
        made = list(col.objects)
        _walls_low(L, True, ts, col, parent, "paint")
        G.instance([o for o in col.objects if o.get("part") == "wall"][0], col, parent, _mat(np.diag([-1.0, 1.0, 1.0])))
        mb = C.MB()
        frame(mb, L, size20, box=_bar)
        _prism_uv(_gpart(mb, "frame", ts, "paint", col, parent, 30.0), mb, _piece(L))
        _castings_low(L, ts, col, parent)
        _underside_low(L, size20, ts, col, parent)
        doors = {}
        for side, nm in ((1, "R"), (-1, "L")):
            md, mp, mg = C.MB(), C.MB(), C.MB()
            hx, hy = _door_low(md, mp, mg, L, side)
            panel = _gpart(mp, f"doorpanel_{nm}", ts, "paint", col, parent, CORR_SHARP, recalc=False)
            _strip_uv(panel, surfs=2)
            gear = _gpart(mg, f"gear_{nm}", ts, "galv", col, parent, 40.0)
            _prism_uv(gear, mg)                       # штанги, кулачки, ручки — полосами, не россыпью граней
            door = _gpart(md, f"door_{nm}", ts, "paint", col, parent, 30.0)
            _prism_uv(door, md)
            doors[nm] = ([door, panel, gear], hx, hy)
        ctx[key] = [o for o in col.objects if o.type == "MESH" and o not in made]
        ctx[key + "_doors"] = doors
        return
    base = ("c20" if size20 else "c40") + "_closed"
    doors = ctx[base + "_doors"]
    for o in ctx[base]:
        if o.get("part", "").startswith(("door_", "doorpanel_", "gear_")):
            continue
        G.instance(o, col, parent)
    for nm, ang in (("R", 255.0), ("L", -108.0)):
        objs, hx, hy = doors[nm]
        M = _hinge(hx, hy, ang)
        for o in objs:
            G.instance(o, col, parent, M)
    # нутро: изнанка гофры, пол
    tsi = ts + "In"
    ins = _walls_low(L, False, tsi, col, parent, "intpaint")
    G.instance(ins[0], col, parent, _mat(np.diag([-1.0, 1.0, 1.0])))
    mb = C.MB()
    xa, xb = -_HW + 0.050, _HW - 0.050
    ya, yb = -L / 2 + 0.135 + 0.08, L / 2 - 0.058
    zf = Z_FLOOR[1]
    mb.add([(xa, ya, zf), (xb, ya, zf), (xb, yb, zf), (xa, yb, zf)], [(0, 1, 2, 3)], "x")
    _box_pieces(_gpart(mb, "floor", tsi, "plywood", col, parent, 30.0, recalc=False), min(3.0, _piece(L)))
