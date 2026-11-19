# ВЕРАС-54 v14: цевьё (полимер) — нижняя половина с объёмным рельефом боков (скос-«волна», продольная канавка,
# поднутрение к килю, расширенный передний упор под ладонь) и нижней планкой Пикатинни заодно; верхняя накладка
# с утопленной панелью, пятью щелями, длинным окном с перемычкой и верхней планкой заодно; защёлка справа в кармане;
# короткие боковые планки на двух винтах под шестигранник в карманах накладки.
# Места сняты с плиток образца с сеткой в мм (ref_tiles.py → trace/hg/g): правый бок — r1 (R_x0.02_z0.265),
# r2 (R_x0.11_z0.27); левый — l1, l2; сверху — t1, t2 (T_x0.02, T_x0.13); снизу — u1, u2 (U_x0.02, U_x0.13).
# Длина — как у v13 (HG_X0…HG_X1): места образца (X 259…412) растянуты от X 259 в S раз; шаг зубьев планок — 10 мм.
import math

import numpy as np
from scipy.ndimage import gaussian_filter1d

from dims import *
from sdf import *

S = (HG_X1 - HG_X0) / (412.0 - 259.0)   # растяжение мест образца по длине (задание: ×1,105)
X0 = HG_X0 + 0.2                  # задний торец — зазор 0,2 до переднего торца коробки
X1 = HG_X1                        # передний торец
PART_Z = 11.0                     # линия разъёма половин (r1, l1: Z 10,5…11)
GAP = 0.2                         # зазор по разъёму


def X_(xs):
    """X образца → X модели (растяжение от X 259)."""
    return HG_X0 + (xs - 259.0) * S


def xs_of(X):
    return 259.0 + (X - HG_X0) / S


# ---- нижняя половина: полуширина бока по высоте Z (Y, Z) ----
W_REAR = 15.3                     # шейка у коробки: силуэт сверху и снизу ±15,3 у X 262…270 (sil.py по T_x0.02, U_x0.02),
                                  # уже борта коробки; к X 300 расходится до ±19,4
# середина: снизу вверх — киль, поднутрение (тёмная скошенная вниз грань), полоса под канавкой, «волна»-скос
# наружу-вниз от разъёма (r1, r2, l1 по высотам кромок; полуширина — t1/u1/u2: наибольшая ~19,4, оценка по глубине)
PROF_MID = [(-27.0, 13.8), (-19.6, 13.8), (-18.2, 14.2), (-15.0, 15.2), (-11.0, 17.3), (-8.3, 19.1), (-6.8, 19.4),
            (0.0, 19.5), (7.5, 17.8), (12.0, 17.7)]
# передний упор (X образца 395…412): бок полный до Z −17, ниже — киль
PROF_FRONT = [(-27.0, 13.8), (-20.2, 13.8), (-18.4, 16.4), (-16.4, 18.7), (5.0, 18.8), (8.5, 18.2), (12.0, 18.0)]   # силуэт у X 388: ±18,6
ZBOT_REAR = -31.4                 # низ задней части — вровень с низом коробки (l1, наложение R_x0.02)
ZBOT_BODY = -25.4                 # низ корпуса над нижней планкой (r1, r2: светлая полоса киля до −24,7)
GROOVE_Z = -4.5                   # продольная канавка (r1: острый задний конец у X 290, r2: передний у 388)
GROOVE_XS = (290.0, 388.0)
GROOVE_D = 1.0                    # глубина (оценка)

# ---- верхняя накладка ----
W_UP_REAR, W_UP = 15.3, 15.3      # полуширина накладки: сверху (T_x0.136) её бок — |Y| 15,1…15,3, планки выступают на ~6 мм;
                                  # нижняя половина под ней шире (до ±19,4) — уступ по разъёму
SHOULDER_R = 3.2                  # плечо бок — верх (r2, l2: линия на Z 37)
# утопленная панель со щелями (P12, l1: задняя кромка — дуга от (302; 21) к (289; 38,5))
PANEL = [(302.0, 19.6), (363.0, 19.6), (363.0, 39.5), (288.0, 39.5), (291.5, 30.5)]
PANEL_D = 0.5
# щели: X образца 306,5…310 + 10,07·n (r1, r2), Z 22,3…34,7
SLOTS = [306.5 + 10.07 * n for n in range(5)]
SLOT_W, SLOT_Z = 3.5, (22.3, 34.7)
# окно: утопленная рамка X образца 297,9…358,3, Z 7,4…19,2; насквозь — две прорези по низу рамки (Z 7,4…11,6) по сторонам
# перемычки X 322,5…332,6 (r1, r2, l1: верх рамки — светлое дно, прорези — чёрные)
WIN = (297.9, 358.3, 7.4, 19.2)
BRIDGE = (322.5, 332.6)
WIN_THRU_Z = 12.3
WIN_FLOOR = 14.0                  # дно рамки по |Y| (полость накладки ±12,6)
# карманы защёлки (обе стороны, r1 / l1: X 274,5…284,5, Z 29,5…36,3)
LATCH_POCKET = (274.5, 284.5, 29.5, 36.3)
LATCH_DEPTH = 1.4                 # глубина кармана от бока (оценка)

# ---- планки ----
RAIL_SLOT_W = 5.2                 # шаг и паз — продолжение планки крышки (part_cover: середины пазов 3,2 + 10n, паз 5,2)
RAIL_SLOT0 = 276.3                # середины пазов 8,9 + 10n, как у планки крышки по образцу (278,9 − 2,6)
# сечение планки от её основания: шейка, подрез 45°, кромка, фаска к верху (высота 4,0 — до RAIL_TOP)
RAIL_STEPS = (0.6, 2.6, 3.1, 4.0)
NECK_HW, TOP_HW = 8.4, 9.7
BOT_RAIL_XS0 = 300.0              # нижняя планка начинается у X образца 300 (u1)
BOT_RAIL_SLOT_XS = 326.0          # первый паз нижней планки — не раньше X образца 326 (r1, u1)
# боковые планки (t2, r2, l2): длина 44,3, винты от заднего конца 5,1 и 39,7, пазы 9,7 / 19,9 / 29,9 шириной 5,2;
# середина по высоте Z 28, наружу до |Y| 20,8 (образец 21,0), основание в кармане на |Y| 16,1
# боковые планки — по крупным снимкам R_x0.136_z0.3075_f0.6 (сбоку), T_x0.136_f0.6 (сверху), P17 (3/4); X образца:
# концевые блоки 364,3…375,8 и 400,9…411,6 во всю высоту Z 17,3…38,2 (фаски 45° ~2,2 по кромкам, торцы со скосом ~1,8),
# между ними пониженная перемычка (наружу до |Y| 18,2), на ней четыре зуба X 380,7…385,6 и 390,8…395,7 у верхней
# и нижней кромок (|Z − середина| ≥ 5,5); наружная грань блоков и зубьев — |Y| 21,1; винты X 371,2 и 405,8, Z 27,4
SR_XS0, SR_XS1 = 364.3, 411.6
SR_LEN = SR_XS1 - SR_XS0
SR_X0 = X_((SR_XS0 + SR_XS1) / 2) - SR_LEN / 2   # середина — растянутая середина образца, длина — своя
SR_X1 = SR_X0 + SR_LEN
SR_ZC = 27.75
SR_BASE = W_UP + 0.1              # стоит прямо на боку накладки (зазор 0,1), без кармана
SR_TOP = 21.1                     # наружная грань блоков и зубьев
SR_MID = 18.2                     # наружная грань перемычки
SR_BLOCK = (375.8 - SR_XS0, SR_XS1 - 400.9)       # длины концевых блоков
SR_TEETH = [(380.7 - SR_XS0, 4.9), (390.8 - SR_XS0, 4.9)]
SR_TOOTH_U = 5.5                  # зуб — дальше этого от середины по Z
SR_SCREWS = [(371.2 - SR_XS0, 27.4), (405.8 - SR_XS0, 27.4)]
SR_END_CH = 1.8                   # скос наружных торцов блоков


def _table(points, z0=-34.0, z1=14.0, st=0.05, sigma=0.7):
    """Полуширина по высоте: ломаная, сглаженная по Гауссу — скругления на изломах профиля."""
    zg = np.arange(z0, z1 + st, st)
    zs = [p[0] for p in points]; ws = [p[1] for p in points]
    w = np.interp(zg, zs, ws)
    return zg, gaussian_filter1d(w, sigma / st, mode="nearest")


TAB_MID = _table(PROF_MID)
TAB_FRONT = _table(PROF_FRONT)


def _lookup(tab, Z):
    zg, w = tab
    return np.interp(np.asarray(Z, np.float64).ravel(), zg, w).reshape(np.shape(Z)).astype(F32)


def w_lower(X, Z):
    """Полуширина нижней половины в точке (X, Z)."""
    xs = xs_of(X)
    # шейка → рельеф: граница наискосок (сверху раньше — «волна» от (270; 5), снизу позже — поднутрение от (300; −18))
    # (R_x0.02: поднутрение начинается наискосок от (272; −22,8) к (294; −16,4), выше — от конца канавки X 290)
    # (наклоны 3,4 и −0,4 сведены гиперболой — без излома: излом границы давал складку на боку)
    a = Z + 16.4
    xb = 294.0 + 1.5 * a - 1.9 * (np.sqrt(a * a + 4.0) - 2.0)
    xb = 0.5 * (xb + 268.0 + np.sqrt((xb - 268.0) ** 2 + 4.0))
    t1 = smoothstep((xs - xb + 10.0) / 20.0)
    # рельеф → передний упор: граница «углом» назад (r2: верх (370; 1)…(395; 6), низ (388; −17))
    a = Z + 1.0
    xf = 372.0 + 1.4 * a + 2.4 * (np.sqrt(a * a + 4.0) - 2.0)
    t2 = smoothstep((xs - xf + 6.0) / 12.0)
    W = W_REAR * (1 - t1) + _lookup(TAB_MID, Z) * t1
    W = W * (1 - t2) + _lookup(TAB_FRONT, Z) * t2
    # канавка с острыми концами
    taper = np.clip(np.minimum((xs - GROOVE_XS[0]) / 22.0, (GROOVE_XS[1] - xs) / 12.0), 0.0, 1.0)
    # к концам сужается и мелеет вместе (без «ниток» на остриях)
    hw = 1.5 * taper
    g = smoothstep((hw + 0.3 - np.abs(Z - GROOVE_Z)) / 0.9) * smoothstep(taper * 1.5)
    return (W - GROOVE_D * g).astype(F32)


PANEL_POLY = Poly(fillet_poly([(X_(x), z) for x, z in PANEL], [3.0, 1.0, 0.0, 2.0, 9.0], seg=10))


def w_upper(X, Z):
    xs = xs_of(X)
    W = W_UP_REAR + (W_UP - W_UP_REAR) * smoothstep((xs - 270.0) / 30.0)
    return (W - PANEL_D * smoothstep(-PANEL_POLY.sd(X, Z) / 1.6 + 0.5)).astype(F32)


def side_field(wfn):
    """Расстояние до бока |Y| = W(X, Z), поделённое на длину градиента (поле остаётся почти точным)."""
    def f(X, Y, Z):
        e = 0.1
        W = wfn(X, Z)
        gx = (wfn(X + e, Z) - W) / e
        gz = (wfn(X, Z + e) - W) / e
        return ((np.abs(Y) - W) / np.sqrt(1.0 + gx * gx + gz * gz)).astype(F32)
    return f


def z_bottom(X, Y):
    """Низ нижней половины: сзади — вровень с коробкой, середина низа плавно сходит в нижнюю планку,
    бока поднимаются к килю."""
    xs = xs_of(X)
    # середина низа сходит в планку; дальше её начала — поднимается к основанию планки (без скачка: шов поля)
    zc = ZBOT_REAR + (-29.4 - ZBOT_REAR) * smoothstep((xs - 262.0) / 40.0)
    zc = zc + (ZBOT_BODY - zc) * smoothstep((xs - BOT_RAIL_XS0 - 1.0) / 4.0)
    zs = ZBOT_REAR + (ZBOT_BODY - ZBOT_REAR) * smoothstep((xs - 280.0) / 22.0)
    return zc + (zs - zc) * smoothstep((np.abs(Y) - 9.0) / 3.5)


def _rail_poly(base, sign):
    """Сечение планки Пикатинни (Y, Z) от основания base: sign = +1 — зубья вверх, −1 — вниз."""
    a, b, c, d = RAIL_STEPS
    s = sign
    pts = [(-NECK_HW, base - s * 0.8), (NECK_HW, base - s * 0.8), (NECK_HW, base + s * a), (RAIL_HW, base + s * b),
           (RAIL_HW, base + s * c), (TOP_HW, base + s * d), (-TOP_HW, base + s * d), (-RAIL_HW, base + s * c),
           (-RAIL_HW, base + s * b), (-NECK_HW, base + s * a)]
    rad = [0, 0, 0.4, 0.25, 0.2, 0.25, 0.25, 0.2, 0.25, 0.4]
    if s < 0:
        pts = pts[::-1]; rad = rad[::-1]
    return Poly(fillet_poly(pts, rad, seg=6))


def _rail(F, base, sign, xa, xb, first=None):
    """Планка заодно с корпусом: тело по длине xa…xb и поперечные пазы шагом 10."""
    pol = _rail_poly(base, sign)
    tip = base + sign * RAIL_STEPS[3]

    def body(X, Y, Z):
        d = pol.sd(Y, Z)
        d = i_round(d, xa - X, 0.5)
        d = i_round(d, X - xb, 0.5)
        # фаски торцов по кромке зубьев
        d = np.maximum(d, ((xa + 1.0 - X) + sign * (Z - tip)) * 0.70710678)
        return np.maximum(d, ((X - xb + 1.0) + sign * (Z - tip)) * 0.70710678)
    z0, z1 = sorted((base - sign * 1.0, tip))
    F.add(body, 0.6, bbox=bb(xa - 1, xb + 1, -RAIL_HW - 1, RAIL_HW + 1, z0 - 1, z1 + 1))
    sbot = base + sign * 1.1                   # дно паза
    n0 = int(math.ceil((xa - RAIL_SLOT0) / 10.0)) - 1
    n1 = int(math.floor((xb - RAIL_SLOT0) / 10.0)) + 1
    for n in range(n0, n1 + 1):
        s0 = RAIL_SLOT0 + 10.0 * n; s1 = s0 + RAIL_SLOT_W
        if s0 < xa + 4.5 or s1 > xb - 5.0 or (first is not None and s0 < first):
            continue
        lo, hi = sorted((sbot, tip + sign * 3.0))
        F.sub(box_e((s0, -RAIL_HW - 2, lo), (s1, RAIL_HW + 2, hi), ry=0.5), 0.3,
              bbox=bb(s0 - 1, s1 + 1, -RAIL_HW - 1, RAIL_HW + 1, min(sbot, tip) - 1, max(sbot, tip) + 1))


def _window2():
    x0, x1, z0, z1 = WIN
    pts = [(X_(x0), z0 + 2.4), (X_(x0) + 2.4, z0), (X_(x1) - 3.0, z0), (X_(x1), z0 + 3.0), (X_(x1), z1 - 2.4),
           (X_(x1) - 2.4, z1), (X_(x0) + 2.4, z1), (X_(x0), z1 - 2.4)]
    return Poly(fillet_poly(pts, [0.8, 0.8, 1.5, 1.5, 0.8, 0.8, 0.8, 0.8], seg=6)).sd


def _window_thru():
    x0, x1, z0, z1 = WIN
    zt = WIN_THRU_Z
    return union2(rect2(X_(x0) + 0.7, X_(BRIDGE[0]), z0 + 0.25, zt, 2.0), rect2(X_(BRIDGE[1]), X_(x1) - 0.7, z0 + 0.25, zt, 2.0))


def _window(F, z0, z1):
    """Утопленная рамка окна (обе стороны) и сквозные прорези по её низу."""
    x0, x1, _, _ = WIN
    xa, xb = X_(x0), X_(x1)
    for s in (-1, 1):
        y0, y1 = sorted((s * WIN_FLOOR, s * 24.0))
        F.sub(prism2(_window2(), "XZ", y0, y1), 0.5, bbox=bb(xa - 1, xb + 1, min(y0, y1) - 1, max(y0, y1) + 1, z0 - 1, z1 + 1))
    _cut_through(F, _window_thru(), z0, min(z1, WIN_THRU_Z), xa, xb, 0.4)


def _cut_through(F, f2, z0, z1, x0, x1, r=0.5):
    F.sub(prism2(f2, "XZ", -25.0, 25.0), r, bbox=bb(x0 - 1, x1 + 1, -22, 22, z0 - 1, z1 + 1))


# ---------- нижняя половина ----------

def lower(h):
    F = Field("Handguard_Lower", (X0 - 1.0, -21.5, ZBOT_REAR - 1.5), (X1 + 1.0, 21.5, PART_Z + 1.0), h)
    side = side_field(w_lower)
    ztop = PART_Z - GAP / 2

    def shell(X, Y, Z):
        d = side(X, Y, Z)
        d = i_round(d, z_bottom(X, Y) - Z, 1.6)
        d = i_round(d, Z - ztop, 0.35)
        d = i_round(d, X0 - X, 0.8)
        return i_round(d, X - X1, 2.4)            # передний упор скруглён
    F.add(shell)
    _rail(F, ZBOT_BODY, -1, X_(BOT_RAIL_XS0), X1 - 2.2, X_(BOT_RAIL_SLOT_XS))
    # полость: ствол (r 10, зазор ≥ 0,5) и стенки ~3,5 мм; торцевые стенки с отверстием под ствол
    F.sub(union(box_e((X0 + 3.0, -12.6, -4.0), (X1 - 3.0, 12.6, PART_Z + 3), rx=2.5, ry=1.0, rz=1.0),
                cyl("X", (0.0, 0.0), 11.6, X0 + 3.0, X1 - 3.0, rim=1.0), r=1.5), 0.6,
          bbox=bb(X0 + 1, X1 - 1, -16, 16, -14, PART_Z + 1))
    F.sub(cyl("X", (0.0, 0.0), BARREL_R + 0.6, X0 - 3, X1 + 3), 0.5, bbox=bb(X0 - 1, X1 + 1, -12, 12, -12, 12))
    # окно (нижняя часть: две прорези по сторонам перемычки)
    _window(F, WIN[2], PART_Z)
    return F


# ---------- верхняя накладка ----------

def upper(h):
    F = Field("Handguard_Upper", (X0 - 1.0, -20.5, PART_Z - 1.0), (X1 + 1.0, 20.5, RAIL_TOP + 1.0), h)
    side = side_field(w_upper)
    zb = PART_Z + GAP / 2

    def shell(X, Y, Z):
        d = side(X, Y, Z)
        d = i_round(d, Z - HG_TOP, SHOULDER_R)
        d = i_round(d, zb - Z, 0.35)
        d = i_round(d, X0 - X, 0.8)
        d = i_round(d, X - X1, 0.6)
        # передние вертикальные кромки срезаны (t2, r2: фаска ~2,6)
        return i_round(d, ((X - X1) + (np.abs(Y) - W_UP) + 1.2) * 0.70710678, 0.4)
    F.add(shell)
    _rail(F, HG_TOP, 1, X0 + 0.4, X1 - 0.4)
    # полость под газовую трубку (Y ±10, Z 17…37; зазор ≥ 0,5) и торцевые стенки с отверстием под трубку
    F.sub(box_e((X0 + 3.0, -12.6, PART_Z - 3), (X1 - 3.0, 12.6, 38.0), rx=3.0, ry=1.0, rz=1.0), 0.6,
          bbox=bb(X0 + 1, X1 - 1, -15, 15, PART_Z - 1, 39.5))
    F.sub(cyl("X", (0.0, GAS_AXIS_Z), 10.6, X0 - 3, X1 + 3), 0.5, bbox=bb(X0 - 1, X1 + 1, -12, 12, 15, 39))
    # щели
    for xs in SLOTS:
        xa = X_(xs + SLOT_W / 2) - SLOT_W / 2
        _cut_through(F, rect2(xa, xa + SLOT_W, SLOT_Z[0], SLOT_Z[1], 0.7), SLOT_Z[0], SLOT_Z[1], xa, xa + SLOT_W, 0.5)
    # окно
    _window(F, PART_Z, WIN[3])
    # отверстия под винты боковых планок (бок под планкой гладкий)
    for s in (-1, 1):
        for dx, zc in SR_SCREWS:
            y0, y1 = sorted((s * 13.6, s * (W_UP + 1)))
            F.sub(cyl("Y", (SR_X0 + dx, zc), 1.65, y0, y1), 0.2,
                  bbox=bb(SR_X0 + dx - 3, SR_X0 + dx + 3, min(y0, y1) - 1, max(y0, y1) + 1, zc - 3, zc + 3))
    # карманы защёлки; слева в кармане — головка оси чеки (литая втулка заодно)
    lx0, lx1, lz0, lz1 = LATCH_POCKET
    LATCH_FLOOR = latch_floor()
    for s in (-1, 1):
        y0, y1 = sorted((s * LATCH_FLOOR, s * 24.0))
        F.sub(prism2(rect2(X_(lx0), X_(lx1), lz0, lz1, 1.2), "XZ", y0, y1), 0.35,
              bbox=bb(X_(lx0) - 2, X_(lx1) + 2, min(y0, y1) - 1, max(y0, y1) + 1, lz0 - 2, lz1 + 2))
    cx, cz = (X_(lx0) + X_(lx1)) / 2, (lz0 + lz1) / 2
    F.add(cyl("Y", (cx, cz), 2.6, LATCH_FLOOR - 0.2, LATCH_FLOOR + 0.9, rim=0.4), 0.3,
          bbox=bb(cx - 4, cx + 4, LATCH_FLOOR - 1, LATCH_FLOOR + 1.5, cz - 4, cz + 4))
    F.sub(prism2(rect2(cx - 1.8, cx + 1.8, cz - 0.45, cz + 0.45, 0.4), "XZ", LATCH_FLOOR + 0.5, LATCH_FLOOR + 2), 0.15,
          bbox=bb(cx - 3, cx + 3, LATCH_FLOOR, LATCH_FLOOR + 1.5, cz - 2, cz + 2))
    # гнездо оси защёлки справа (вертикальная ось у переднего конца кармана)
    F.sub(cyl("Z", _latch_pivot(), 0.75, lz0 - 2.0, lz1 + 2.0), 0.1,
          bbox=bb(X_(lx1) - 4, X_(lx1), -LATCH_FLOOR - 2, -LATCH_FLOOR + 1, lz0 - 3, lz1 + 3))
    return F


# ---------- защёлка ----------

def latch_floor():
    """Дно кармана защёлки по |Y|: бок накладки в середине кармана минус глубина."""
    lx0, lx1, lz0, lz1 = LATCH_POCKET
    w = w_upper(np.array([[[X_((lx0 + lx1) / 2)]]], F32), np.array([[[(lz0 + lz1) / 2]]], F32))
    return float(w.ravel()[0]) - LATCH_DEPTH


def latch_side():
    lx0, lx1, lz0, lz1 = LATCH_POCKET
    w = w_upper(np.array([[[X_((lx0 + lx1) / 2)]]], F32), np.array([[[(lz0 + lz1) / 2]]], F32))
    return float(w.ravel()[0])


def _latch_pivot():
    lx0, lx1, lz0, lz1 = LATCH_POCKET
    return X_(lx1) - 1.6, -(latch_floor() + 0.7)


def latch(h):
    lx0, lx1, lz0, lz1 = LATCH_POCKET
    xa, xb = X_(lx0) + 0.25, X_(lx1) - 0.25
    za, zb = lz0 + 0.25, lz1 - 0.25
    px, py = _latch_pivot()
    y_in, y_out = -(latch_floor() + 0.12), -(latch_side() - 0.15)
    F = Field("Handguard_Latch", (xa - 1.5, y_out - 1.5, za - 2.5), (xb + 1.5, y_in + 1.0, zb + 2.5), h)
    # пластина-рычаг: задний конец — язычок под ноготь (утолщён наружу)
    plate = Poly(fillet_poly([(xa, za), (xb, za), (xb, zb), (xa, zb)], [1.0, 1.0, 1.0, 1.0]))
    F.add(prism(plate, "XZ", y_out, y_in, rim=0.35))
    F.add(box((xa + 0.2, y_out - 0.35, za + 0.6), (xa + 2.0, y_out + 0.5, zb - 0.6), 0.3), 0.3,
          bbox=bb(xa - 1, xa + 3, y_out - 1, y_out + 1, za, zb))
    # рифление — три поперечных ребра
    for k in range(0 if PLAIN else 3):
        xr = xa + 3.0 + k * 1.3
        F.add(cyl("Z", (xr, y_out + 0.1), 0.32, za + 1.0, zb - 1.0, rim=0.25), 0.2,
              bbox=bb(xr - 1, xr + 1, y_out - 1, y_out + 1, za, zb))
    # ось (в гнезде накладки) — заодно с рычагом, торцы скруглены
    F.add(cyl("Z", (px, py), 0.65, za - 1.6, zb + 1.6, rim=0.25), 0.0, bbox=bb(px - 1.5, px + 1.5, py - 1.5, py + 1.5, za - 2.5, zb + 2.5))
    return F


# ---------- боковые планки ----------

def _sr_profile(top):
    """Сечение боковой планки (u — Z от середины, v — |Y|) до наружной грани top: подрез 45° у основания,
    грань во всю высоту, фаски 45° к наружной грани (профиль Пикатинни)."""
    b = SR_BASE
    hw, nk = RAIL_HW - 0.1, 8.4
    ch = min(2.2, top - b - 2.2)
    pts = [(-nk, b - 0.6), (nk, b - 0.6), (nk, b + 0.6), (hw, b + 0.6 + (hw - nk)), (hw, top - ch), (hw - ch, top),
           (-(hw - ch), top), (-hw, top - ch), (-hw, b + 0.6 + (hw - nk)), (-nk, b + 0.6)]
    return Poly(fillet_poly(pts, [0.3, 0.3, 0.35, 0.3, 0.3, 0.35, 0.35, 0.3, 0.3, 0.35], seg=6))


SR_FULL = _sr_profile(SR_TOP)
SR_LOW = _sr_profile(SR_MID)


def side_rail(side):
    """Боковая планка: два концевых блока с винтами, пониженная перемычка и четыре зуба у кромок."""
    def build(h):
        y0, y1 = sorted((side * (SR_BASE - 1.0), side * (SR_TOP + 0.6)))
        F = Field("Side_Rail_" + ("L" if side > 0 else "R"), (SR_X0 - 1.0, y0 - 0.5, SR_ZC - RAIL_HW - 1.2),
                  (SR_X1 + 1.0, y1 + 0.5, SR_ZC + RAIL_HW + 1.2), h)

        def span(prof, xa, xb, chamfer_a, chamfer_b, r=0.35):
            def f(X, Y, Z):
                v = side * Y
                d = prof.sd(Z - SR_ZC, v)
                d = i_round(d, xa - X, r)
                d = i_round(d, X - xb, r)
                # скос наружных торцов (вид сверху: торец уходит назад к наружной грани)
                if chamfer_a:
                    d = i_round(d, ((xa + chamfer_a - X) + (v - SR_TOP)) * 0.70710678, 0.3)
                if chamfer_b:
                    d = i_round(d, ((X - xb + chamfer_b) + (v - SR_TOP)) * 0.70710678, 0.3)
                return d
            return f
        bl0, bl1 = SR_BLOCK
        box_bb = bb(SR_X0 - 1, SR_X1 + 1, y0 - 0.5, y1 + 0.5, SR_ZC - 12, SR_ZC + 12)
        # перемычка по всей длине (концы скрыты блоками)
        F.add(span(SR_LOW, SR_X0 + 1.0, SR_X1 - 1.0, 0, 0), bbox=box_bb)
        # концевые блоки
        F.add(span(SR_FULL, SR_X0, SR_X0 + bl0, SR_END_CH, 0), 0.3, bbox=bb(SR_X0 - 1, SR_X0 + bl0 + 1, y0 - 0.5, y1 + 0.5, SR_ZC - 12, SR_ZC + 12))
        F.add(span(SR_FULL, SR_X1 - bl1, SR_X1, 0, SR_END_CH), 0.3, bbox=bb(SR_X1 - bl1 - 1, SR_X1 + 1, y0 - 0.5, y1 + 0.5, SR_ZC - 12, SR_ZC + 12))
        # зубья у верхней и нижней кромок
        for dx, w in SR_TEETH:
            xa = SR_X0 + dx
            for zs in (-1, 1):
                full = span(SR_FULL, xa, xa + w, 0, 0, 0.3)

                def tooth(X, Y, Z, full=full, zs=zs):
                    d = full(X, Y, Z)
                    return i_round(d, SR_TOOTH_U - zs * (Z - SR_ZC), 0.3)
                F.add(tooth, 0.25, bbox=bb(xa - 1, xa + w + 1, y0 - 0.5, y1 + 0.5, SR_ZC - 12, SR_ZC + 12))
        # винты: овальная выборка, цековка и отверстие под стержень
        for dx, zc in SR_SCREWS:
            sx = SR_X0 + dx
            ya, yb = sorted((side * (SR_TOP - 0.45), side * (SR_TOP + 1)))
            F.sub(prism2(rect2(sx - 3.75, sx + 3.75, zc - 4.15, zc + 4.15, 3.6), "XZ", ya, yb), 0.3,
                  bbox=bb(sx - 5, sx + 5, min(ya, yb) - 1, max(ya, yb) + 1, zc - 5.5, zc + 5.5))
            ya, yb = sorted((side * (SR_TOP - 1.7), side * (SR_TOP + 1)))
            F.sub(cyl("Y", (sx, zc), 3.35, ya, yb), 0.2, bbox=bb(sx - 5, sx + 5, min(ya, yb) - 1, max(ya, yb) + 1, zc - 5, zc + 5))
            ya, yb = sorted((side * (SR_BASE - 2), side * (SR_TOP - 1.5)))
            F.sub(cyl("Y", (sx, zc), 1.65, ya, yb), 0.15, bbox=bb(sx - 3, sx + 3, min(ya, yb) - 1, max(ya, yb) + 1, zc - 3, zc + 3))
        return F
    return build


def screws(h):
    """Винты боковых планок (4 шт.): головка под шестигранник в цековке, стержень в отверстие накладки."""
    F = Field("Side_Rail_Screws", (SR_X0 - 1.0, -SR_TOP - 1.0, SR_ZC - 5.0), (SR_X1 + 1.0, SR_TOP + 1.0, SR_ZC + 5.0), h)
    for side in (-1, 1):
        for dx, zc in SR_SCREWS:
            sx = SR_X0 + dx
            yh = side * (SR_TOP - 0.55)                      # верх головки — чуть ниже грани
            ya, yb = sorted((side * (SR_TOP - 1.6), yh))
            F.add(cyl("Y", (sx, zc), 3.15, ya, yb, rim=0.45), bbox=bb(sx - 4, sx + 4, min(ya, yb) - 0.5, max(ya, yb) + 0.5, zc - 4, zc + 4))
            ya, yb = sorted((side * 13.8, side * (SR_TOP - 1.5)))
            F.add(cyl("Y", (sx, zc), 1.45, ya, yb, rim=0.3), 0.15, bbox=bb(sx - 2.5, sx + 2.5, min(ya, yb) - 0.5, max(ya, yb) + 0.5, zc - 2.5, zc + 2.5))

            def hexsock(X, Y, Z, sx=sx, zc=zc, yh=yh):
                u = X - sx; v = Z - zc
                d = np.maximum(np.abs(u), np.abs(0.5 * u + 0.8660254 * v))
                d = np.maximum(d, np.abs(-0.5 * u + 0.8660254 * v)) - 1.5
                return np.maximum(d, np.abs(Y - yh) - 1.1)
            F.sub(hexsock, 0.12, bbox=bb(sx - 2.5, sx + 2.5, yh - 1.6, yh + 1.6, zc - 2.5, zc + 2.5))
    return F


def parts():
    px, py = _latch_pivot()
    return [
        dict(name="Handguard_Lower", build=lower, h=0.15, coll="Цевьё", mat="Polymer", adapt=0.05),
        dict(name="Handguard_Upper", build=upper, h=0.13, coll="Цевьё", mat="Polymer", adapt=0.05),
        dict(name="Handguard_Latch", build=latch, h=0.06, coll="Цевьё", mat="Steel_phosphate", parent="Handguard_Upper",
             pivot=[px, py, (LATCH_POCKET[2] + LATCH_POCKET[3]) / 2],
             motion="оценка: поворот вокруг Z (вертикальная ось у переднего конца кармана), задний конец наружу (−Y) до 25°"),
        dict(name="Side_Rail_R", build=side_rail(-1), h=0.07, coll="Цевьё", mat="Alu_anodized", parent="Handguard_Upper", adapt=0.04),
        dict(name="Side_Rail_L", build=side_rail(1), h=0.07, coll="Цевьё", mat="Alu_anodized", parent="Handguard_Upper", adapt=0.04),
        dict(name="Side_Rail_Screws", build=screws, h=0.06, coll="Цевьё", mat="Steel_phosphate", parent="Handguard_Upper"),
    ]
