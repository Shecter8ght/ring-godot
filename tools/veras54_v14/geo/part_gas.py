# ВЕРАС-54 v14: ствол, газовая трубка с продольными долами, газовая камера с основанием мушки заодно (хомут на
# стволе, стойка с овальными выборками, «уши» намушника, петля-антабка, прилив снизу), штифты, мушка, кольцо
# с проушиной на стволе за газовой камерой.
# Места сняты с плиток образца с сеткой в мм (ref_tiles.py → trace/gas): правый бок — R_x0.245_z0.305_f0.8,
# R_x0.185_z0.305_f0.8, R_x0.22_z0.27_f1.0, R_x0.32_z0.285_f1.0; левый — L_x0.245_z0.305_f0.8; сверху — T_x0.245_f0.8,
# T_x0.185_f0.8; снизу — U_x0.245_f0.8; спереди — F_z0.305_f0.7; виды P13, P24, P25.
# Сдвиг узла относительно образца: ось мушки образца X 501,6 → 518 (+16,4); передний торец цевья образца 412 → 428
# (+16) — разница 0,4 мм, растягивать нечего. По высоте ось ствола образца на плитках Z −1,7 (→ 0, +1,7), ось газовой
# камеры 24,7 (→ GAS_AXIS_Z 27, +2,3): нижние места (хомут, прилив, кольцо) сдвинуты от ствола, верхние (камера,
# стойка, уши, петля) — от оси трубки.
import math

import numpy as np

from dims import *
from sdf import *

SX = 16.4                          # сдвиг X: образец → модель
ZB = 1.7                           # сдвиг Z мест у ствола
ZG = GAS_AXIS_Z - 24.7             # сдвиг Z мест у газовой камеры (+2,3)
GZ = GAS_AXIS_Z


def xs(x):
    return x + SX


# ---------- ствол ----------
BREECH_X = 222.0                   # казённый срез: ствол входит во вкладыш глубоко, как у АК (владелец — патрон заходит «по рельсам»)
BREECH_JOIN = 232.0                # стык казённой части (поле) с телом вращения — по плоскости, r 10
# паз под зуб выбрасывателя на срезе: константы part_bolt (EXT_PSI 165°, зуб X 240,85…241,4, r 4,1…8,25, ±1,7 поперёк),
# сдвинутые на −18 мм к новому срезу; зазор 0,3…0,4
EXT_PSI = 165.0
EXT_SLOT = (BREECH_X - 1.0, 223.8, 3.6, 8.7, 2.5)   # X0, X1, r0, r1, полуширина
MUZZLE_X = 606.0                   # передний торец ствола (внутри дульного устройства)
BORE_R = 2.8                       # канал
BUSH_X = (428.3, xs(419.0))        # поясок у переднего торца цевья: образец X 412…419, r 8,1 (R_x0.185)
BUSH_R = 8.1
FRONT_R = 7.45                     # ствол впереди цевья (образец: Z +5,5…−9,3 при оси −1,9 → r 7,4…7,5)
SEAT_X = 586.6                     # перед задним торцом дульного устройства (X 587,4) — уступ к посадочной шейке
SEAT_R = 7.1                       # шейка под дульное устройство (его гнездо r 7,15 на X 587,4…606,1; у образца так же)
PIN_X = (xs(482.5), xs(507.5))     # поперечные пазы ствола под вертикальные штифты газовой камеры (U_x0.245: X 482,5 и 507,5)
GROOVE_R = 6.25                    # дно паза: штифт r 1,35 на |Y| 7,75 проходит над ним с зазором 0,15
# патронник 5,45×39 от казённого среза: гильза 39,6, дно r 5,0, скат к шейке r 3,15, пульный вход к каналу
# заходный конус на срезе: от r 5,03 до r 7,2 на глубине 2,2 — по нему носик пули заходит в патронник
CHAMBER = [(42.2, BORE_R), (39.8, 3.18), (33.5, 3.18), (31.4, 4.66), (2.2, 5.03), (0.0, 7.2)]


def _chamber_r(d):
    """Радиус патронника на глубине d от среза (между точками CHAMBER — линейно)."""
    pts = sorted(CHAMBER)
    return float(np.interp(d, [a for a, _ in pts], [b for _, b in pts]))


def barrel(h):
    """Ствол — тело вращения сеткой: казённая часть r 10 до цевья, поясок, тонкая передняя часть с пазами под штифты
    газовой камеры, посадочная шейка под дульное устройство; внутри — патронник и канал."""
    # казённая часть X 222…232 — отдельной деталью Barrel_Breech (паз выбрасывателя телом вращения не сделать)
    top = [(BREECH_JOIN, BARREL_R), (BUSH_X[0], BARREL_R), (BUSH_X[0] + 1.2, BUSH_R),
           (BUSH_X[1], BUSH_R), (BUSH_X[1] + 0.6, FRONT_R)]
    rad = [0.0, 0.5, 0.4, 0.3, 0.4]
    for px in PIN_X:
        top += [(px - 1.6, FRONT_R), (px - 1.45, GROOVE_R), (px + 1.45, GROOVE_R), (px + 1.6, FRONT_R)]
        rad += [0.12, 0.3, 0.3, 0.12]
    top += [(SEAT_X, FRONT_R), (SEAT_X + 0.45, SEAT_R), (MUZZLE_X - 0.4, SEAT_R), (MUZZLE_X, SEAT_R - 0.4),
            (MUZZLE_X, BORE_R + 0.6), (MUZZLE_X - 0.5, BORE_R)]
    rad += [0.2, 0.2, 0.15, 0.15, 0.25, 0.15]
    dj = BREECH_JOIN - BREECH_X
    bore = [(BREECH_X + d, r) for d, r in CHAMBER if d > dj] + [(BREECH_JOIN, _chamber_r(dj))]
    rad += [0.5, 0.4, 0.3, 0.6][:len(bore) - 1] + [0.0]
    return lathe_mesh(fillet_poly(top + bore, rad, seg=4), seg=96, closed=True)


def breech(h):
    """Казённая часть ствола X 222…232: срез с фаской, заходный конус патронника, паз под зуб выбрасывателя."""
    F = Field("Barrel_Breech", (BREECH_X - 1.0, -BARREL_R - 1.0, -BARREL_R - 1.0), (BREECH_JOIN + 1.0, BARREL_R + 1.0, BARREL_R + 1.0), h)
    out = Poly(fillet_poly([(BREECH_X, 0.0), (BREECH_X, 9.35), (BREECH_X + 0.65, BARREL_R), (BREECH_JOIN + 2.0, BARREL_R),
                            (BREECH_JOIN + 2.0, 0.0)], [0, 0.35, 0.35, 0, 0], seg=8))
    F.add(revolve(out, "X", (0.0, 0.0)))
    dj = BREECH_JOIN - BREECH_X
    # патронник с заходным конусом; изнутри без скругления у стыка (плоскость X 232)
    pts = [(BREECH_X - 2.0, 0.0), (BREECH_X - 2.0, 7.2)] + [p for p in sorted(
        [(BREECH_X + d, r) for d, r in CHAMBER if d <= dj + 3.0] + [(BREECH_X + dj + 3.0, _chamber_r(dj + 3.0))])] + [(BREECH_X + dj + 3.0, 0.0)]
    F.sub(revolve(Poly(fillet_poly(pts, [0, 0, 0.5, 0.8] + [0.6] * (len(pts) - 4), seg=8)), "X", (0.0, 0.0)), 0.3, bbox=bb(BREECH_X - 1, BREECH_JOIN + 1, -8.5, 8.5, -8.5, 8.5))
    # паз под зуб выбрасывателя (задан справа, ψ 180°, и повёрнут на место выбрасывателя)
    x0, x1, r0, r1, hw = EXT_SLOT
    F.sub(rot(box_e((x0, -r1, -hw), (x1, -r0, hw), rx=0.3, rz=0.6), "X", (0.0, 0.0, 0.0), EXT_PSI - 180.0), 0.3,
          bbox=bb(x0 - 1, x1 + 1, -BARREL_R - 1, 0, -6, 6))
    # стык с телом вращения — по плоскости
    F.apply(half("X", BREECH_JOIN, 1), "inter", 0.0, bbox=bb(BREECH_JOIN - 1, BREECH_JOIN + 1, -BARREL_R - 1, BARREL_R + 1, -BARREL_R - 1, BARREL_R + 1))
    return F


# ---------- газовая трубка ----------
TUBE_X0 = 261.0                    # задний конец у колодки
TUBE_R = 10.0                      # трубка (образец: Z 14,6…34,5 и сверху ±9,9)
TUBE_X1 = xs(467.0)                # передний торец толстой части (R_x0.185: 466,5…467)
NECK_R = 8.2                       # передняя шейка (R_x0.245: Z 16,6…32,9; сверху ±8,6 с хомутом)
NECK_X1 = xs(477.85)               # шейка входит в газовую камеру (задний торец хомута образца 478)
CHAN_R = 6.3                       # канал под шток v13 (r 5,6)
# долы: шесть, по бокам и наискосок (по 60°, перемычки сверху и снизу — силуэт сбоку полный, сверху уже на 1,2);
# кромки долов на плитках: сверху Y −1 и −8,2, сбоку Z +4 и −4 от оси → ширина дола 48°, перемычка 12°
FLUTE_ANG = [30.0, 90.0, 150.0, 210.0, 270.0, 330.0]     # от +Z к +Y
FLUTE_FLOOR = 8.75                 # дно дола (глубина 1,25: силуэт сверху ±8,6…8,9)
FLUTE_RC = 21.7                    # радиус фрезы — дно чуть вогнутое, кромки на ±24°
FLUTE_TIP = xs(450.5)              # конец языка-сбега (R_x0.185: закруглённый язык до X 450…451)
FLUTE_RUN = 6.3                    # длина сбега: язык сужается от X 445,5 образца (R_x0.185)
FLUTE_X0 = 428.6                   # долы начинаются у переднего торца цевья (в цевье трубка гладкая)
TPIN_X = xs(469.5)                 # два штифта шейки (R_x0.185, L_x0.245: X 469,5…471; сверху Y ±6,4)
TPIN_DZ = (5.0, -3.3)              # хорды: сбоку Z +5 и −3,3 от оси, сверху концы верхнего на Y ±6,5
TPIN_R = 1.3


def _flute(phi):
    sy, cz = math.sin(math.radians(phi)), math.cos(math.radians(phi))
    d0 = FLUTE_FLOOR + FLUTE_RC
    xa = FLUTE_TIP - FLUTE_RUN + 1.3
    amp = 1.32

    def f(X, Y, Z):
        # фреза поднимается к концам параболой — язык-сбег с закруглённым концом
        # сбег спереди линейный — язык с острым закруглённым концом, как у образца; сзади (в цевье) — параболой
        t1 = np.clip((X - xa) / FLUTE_RUN, 0.0, None)
        t0 = np.clip((FLUTE_X0 + 3.0 - X) / 3.0, 0.0, None)
        D = d0 + amp * t1 + 1.38 * t0 * t0 + 25.0 * np.clip(t1 - 0.95, 0.0, None) ** 2   # за концом языка фреза уходит круто — без царапин скругления
        return np.hypot(Y - sy * D, Z - GZ - cz * D) - FLUTE_RC
    return f


def gas_tube(h):
    F = Field("Gas_Tube", (TUBE_X0 - 1.0, -TUBE_R - 1.0, GZ - TUBE_R - 1.0), (NECK_X1 + 1.0, TUBE_R + 1.0, GZ + TUBE_R + 1.0), h)
    prof = Poly(fillet_poly([(TUBE_X0, 0.0), (TUBE_X0, TUBE_R), (TUBE_X1, TUBE_R), (TUBE_X1, NECK_R), (NECK_X1, NECK_R),
                             (NECK_X1, 0.0)], [0, 0.6, 0.7, 0.35, 0.2, 0], seg=6))
    F.add(revolve(prof, "X", (0.0, GZ)))
    for phi in FLUTE_ANG:
        F.sub(_flute(phi), 0.4, bbox=bb(FLUTE_X0 - 4.0, FLUTE_TIP + 1.0, -TUBE_R - 1, TUBE_R + 1, GZ - TUBE_R - 1, GZ + TUBE_R + 1))
    # канал под шток с фасками
    ch = Poly(fillet_poly([(TUBE_X0 - 2.0, 0.0), (TUBE_X0 - 2.0, CHAN_R + 1.2), (TUBE_X0 + 1.0, CHAN_R), (NECK_X1 - 0.6, CHAN_R),
                           (NECK_X1 + 0.6, CHAN_R + 1.0), (NECK_X1 + 2.0, CHAN_R + 1.0), (NECK_X1 + 2.0, 0.0)],
                          [0, 0, 0.3, 0.2, 0, 0, 0], seg=4))
    F.sub(revolve(ch, "X", (0.0, GZ)), 0.0)
    # отверстия штифтов шейки
    for dz in TPIN_DZ:
        F.sub(cyl("Y", (TPIN_X, GZ + dz), TPIN_R + 0.06, -12.0, 12.0), 0.15,
              bbox=bb(TPIN_X - 2.5, TPIN_X + 2.5, -TUBE_R, TUBE_R, GZ + dz - 2.5, GZ + dz + 2.5))
    return F


def tube_pins(h):
    """Два штифта шейки трубки — по хордам поперёк, концы вровень с шейкой, чуть выпуклые."""
    F = Field("Gas_Tube_Pins", (TPIN_X - 2.0, -NECK_R - 1.0, GZ - 6.0), (TPIN_X + 2.0, NECK_R + 1.0, GZ + 7.5), h)
    for dz in TPIN_DZ:
        rod = cyl("Y", (TPIN_X, GZ + dz), TPIN_R, -12.0, 12.0)
        F.add(inter(rod, cyl("X", (0.0, GZ), NECK_R + 0.08, TPIN_X - 3, TPIN_X + 3), r=0.3),
              bbox=bb(TPIN_X - 2, TPIN_X + 2, -NECK_R - 1, NECK_R + 1, GZ + dz - 2, GZ + dz + 2))
    return F


# ---------- газовая камера с основанием мушки ----------
BLK_X = (xs(478.0), xs(511.0))     # хомут на стволе (R_x0.22: 478…511; снизу U_x0.245: 478…511)
BLK_HW = 10.0                      # полуширина (снизу ±10)
BLK_BOT = -11.8 + ZB               # низ боковин (R_x0.22: −11,8 при оси −1,6)
BLK_TOP = GZ - 8.2 + 0.1           # верх хомута — касательная к камере (R_x0.245: прямая кромка под камерой)
CH_X = (NECK_X1 + 0.15, xs(507.6))  # камера: от торца шейки трубки до обоймы (R_x0.245, g_key)
CH_R = NECK_R
# клин к петле: перед камерой основание петли сходится по ширине от камеры до толщины петли (g_key: тёмные
# скошенные грани X 507,5…511,5, сверху кромка поднимается 31,4 → 32,8, снизу опускается 17,6 → 16,3; P24)
WEDGE = [(507.3, 31.4), (511.6, 32.8), (511.6, 16.3), (507.3, 17.6)]
WEDGE_X1 = xs(511.6)
CHAN_X1 = xs(491.0)                # глухой канал камеры
BORE = FRONT_R + 0.1               # отверстие хомута под ствол
SLOT = (BLK_X[0], xs(496.0), 5.0)  # паз снизу между боковинами (U_x0.245: X 478…496, Y ±5, тёмный)
SLOT_FLOOR = -8.6
NUT = (xs(492.8), 3.4)             # шестигранная головка фиксатора в пазу (U_x0.245: X 489,7…495,9, Y ±3,5…4), под ключ 6,8
LUG = (xs(498.6), xs(510.4), 4.3, -20.8 + 1.6)   # прилив снизу-спереди (R_x0.22: X 498,6…510,3, Z до −20,8 при оси −1,6; снизу Y ±4,3)
VPIN_Y = 7.75                      # вертикальные штифты по бокам ствола (снизу: Y ±7,7)
VPIN_R = 1.35
VPIN_TOP = 5.6
HPIN = (xs(483.5), 10.6)           # поперечный штифт над стволом (R_x0.22: (483,5; 9,3) при оси −1,6)
BAND = (xs(505.4), xs(507.5))      # обойма-чека поперёк камеры и хомута (g_key: полоса X 505,4…507,5 от Z 5 до 36)
BAND_WIN_LO = (10.5 + ZB, 12.5 + ZB)   # окна в обойме: внизу (g_key Z 10,5…12,5) и над камерой (32,5…35,5)
BAND_WIN_HI = (32.5 + ZG, 35.5 + ZG)
BAND_TOP = 36.2 + ZG
BAND_TAB = 7.3                     # язык обоймы над камерой — вровень с боками стойки (окно видно сбоку)
# стойка мушки (R_x0.245: X 493,3…511, до Z 50; сверху ±7,1 с фасками)
TW_X = (xs(493.3), xs(511.0))
TW_HW = 7.1
TW_TOP = 50.0 + ZG                 # линия «ушей» (тёмная черта на боку)
TW_REAR = 2.0                      # задняя стенка; спереди стойка открыта прорезью
NOTCH_BOT, NOTCH_W0, NOTCH_W1 = 40.0, 2.8, 5.1   # V-прорезь (спереди F_z0.305: сходится книзу)
POST_X = 518.0                     # ось мушки (задание)
POST_TIP = 59.4                    # вершина мушки — на линии прицеливания
POST_HOLE_R, POST_HOLE_BOT = 2.0, 34.6
# уши намушника: дуги к середине, сверху открыты (F_z0.305: снаружи ±7,4 на Z 55, концы ±4…3,6 на Z 61)
EAR_PATH = [(6.45, TW_TOP - 2.0), (6.6, 54.2 + ZG), (4.2, 58.5 + ZG)]
EAR_T = 1.4
EAR_CORNER = 2.6                   # скругление верхних углов (R_x0.245); контур выше ушей на 0,5 — без касания
# овальные выборки на боках стойки (R_x0.245: X 495,5…503,6, Z 34,3…49,6, сужаются к концам)
OVAL = [(497.9, 34.8), (501.5, 34.8), (502.8, 38.6), (502.8, 45.4), (501.9, 49.2), (497.4, 49.2), (496.5, 45.4), (496.5, 38.6)]
OVAL_D = 0.8
# скос передних граней стойки: ширина у переднего торца по высоте и уклон назад (оценка по F_z0.305 и R_x0.245)
TW_FRONT_Z0, TW_FRONT_W0, TW_FRONT_K = 38.0 + ZG, 2.4, 0.855
TW_FRONT_SLOPE = 2.5
# петля-антабка (g_key): шестигранная пластина за клином, сзади отверстие закрыто торцом клина
LOOP = [(511.0, 32.8), (513.0, 32.8), (519.9, 28.1), (519.9, 18.8), (518.2, 16.3), (511.0, 16.3)]
LOOP_HOLE = [(512.3, 27.3), (516.0, 27.3), (517.7, 26.0), (517.7, 18.1), (512.3, 18.1)]
LOOP_HW = 2.2                      # толщина (F_z0.305: ±2,2)


def _xz(pts, dz):
    return [(xs(x), z + dz) for x, z in pts]


def gas_block(h):
    x0, x1 = BLK_X
    F = Field("Gas_Block", (x0 - 1.5, -BLK_HW - 1.0, LUG[3] - 1.0), (xs(522.5), BLK_HW + 1.0, 60.2 + ZG + 2.0), h)
    # хомут: брус вокруг ствола, нижние продольные рёбра скруглены крупно (в скругление выходят штифты)
    F.add(box_e((x0, -BLK_HW, BLK_BOT), (x1, BLK_HW, BLK_TOP + 1.0), rx=2.4, ry=0.7, rz=0.7),
          bbox=bb(x0 - 1, x1 + 1, -BLK_HW - 1, BLK_HW + 1, BLK_BOT - 1, BLK_TOP + 2))
    # камера: цилиндр на оси трубки и конус к петле
    cham = Poly(fillet_poly([(CH_X[0], 0.0), (CH_X[0], CH_R), (CH_X[1], CH_R), (CH_X[1], 0.0)], [0, 0.2, 0.5, 0], seg=6))
    F.add(revolve(cham, "X", (0.0, GZ)), 1.0, bbox=bb(CH_X[0] - 1, CH_X[1] + 1, -CH_R - 1, CH_R + 1, GZ - CH_R - 2, GZ + CH_R + 1))
    # клин к петле: контур сбоку × ширина, сходящаяся от камеры к толщине петли
    wedge_side = Poly(fillet_poly(_xz(WEDGE, ZG), [0.6, 0, 0, 0.6], seg=6))
    wx0 = xs(WEDGE[0][0])

    def wedge(X, Y, Z):
        d = wedge_side.sd(X, Z)
        hw = LOOP_HW + (CH_R - 0.3 - LOOP_HW) * np.clip((WEDGE_X1 - X) / (WEDGE_X1 - wx0), 0, 1)
        d = i_round(d, (np.abs(Y) - hw) * 0.82, 0.5)
        return i_round(d, np.hypot(Y, Z - GZ) - (CH_R + 0.1), 0.4)
    F.add(wedge, 0.6, bbox=bb(wx0 - 1, WEDGE_X1 + 1, -CH_R - 1, CH_R + 1, GZ - CH_R - 2, GZ + CH_R + 1))
    # стойка мушки: передние грани стенок скошены к середине — спереди стойка «рогаткой», книзу сходится к обойме
    # (F_z0.305: снаружи ±7,4 у ушей, ±5,3 на Z 44, ±2,4 на Z 38; сбоку от этого передняя кромка уходит назад книзу)
    tw_box = box_e((TW_X[0], -TW_HW, GZ - 1), (TW_X[1], TW_HW, TW_TOP + 0.5), rx=0.6, ry=0.6, rz=0.9)

    def tower(X, Y, Z):
        wf = TW_FRONT_W0 + (Z - TW_FRONT_Z0) * TW_FRONT_K
        d = (np.abs(Y) - wf - (TW_X[1] - X) * TW_FRONT_SLOPE) / math.hypot(1.0, TW_FRONT_SLOPE)
        return i_round(tw_box(X, Y, Z), d, 0.7)
    F.add(tower, 1.8, bbox=bb(TW_X[0] - 3, TW_X[1] + 3, -TW_HW - 3, TW_HW + 3, GZ - 2, TW_TOP + 1))
    # уши намушника (чуть длиннее стойки вперёд — R_x0.245)
    ex1 = TW_X[1] + 0.8
    ear = strip(Path2(fillet_path(EAR_PATH, [5.0], seg=12)), "YZ", EAR_T, TW_X[0], ex1, rim=0.45)
    F.add(both(ear), 0.6, bbox=bb(TW_X[0] - 1, ex1 + 1, -TW_HW - 1, TW_HW + 1, TW_TOP - 3, 60.2 + ZG + 2))
    side = Poly(fillet_poly([(TW_X[0], GZ), (ex1, GZ), (ex1, 59.7 + ZG), (TW_X[0], 59.7 + ZG)], [0, 0, EAR_CORNER, EAR_CORNER]))
    F.apply(prism(side, "XZ", -12.0, 12.0), "inter", 0.0, bbox=bb(TW_X[0] - 1, ex1 + 1, -TW_HW - 1, TW_HW + 1, TW_TOP, 60.2 + ZG + 2))
    # петля-антабка
    loop = Poly(fillet_poly(_xz(LOOP, ZG), [0.5, 1.0, 1.2, 1.2, 1.0, 0.5], seg=6))
    F.add(prism(loop, "XZ", -LOOP_HW, LOOP_HW, rim=0.6), 0.5,
          bbox=bb(xs(510.0), xs(521.0), -LOOP_HW - 1, LOOP_HW + 1, 15.0 + ZG, 34.0 + ZG))
    # прилив снизу-спереди: задняя кромка внизу срезана
    lx0, lx1, lhw, lbot = LUG
    lug = Poly(fillet_poly([(lx0, BLK_BOT + 1.0), (lx1, BLK_BOT + 1.0), (lx1, lbot), (lx0 + 1.6, lbot), (lx0, lbot + 1.6)],
                           [0, 0, 0.8, 0.6, 0.6], seg=6))
    F.add(prism(lug, "XZ", -lhw, lhw, rim=0.6), 0.7, bbox=bb(lx0 - 1, lx1 + 1, -lhw - 1, lhw + 1, lbot - 1, BLK_BOT + 2))
    # обойма-чека: пояс чуть выше поверхности хомута, камеры и низа стойки
    bx0, bx1 = BAND

    def band_env(X, Y, Z):
        d = box_e((bx0 - 1, -BLK_HW - 0.2, BLK_BOT - 0.2), (bx1 + 1, BLK_HW + 0.2, BLK_TOP + 0.6), rx=2.5)(X, Y, Z)
        d = np.minimum(d, np.hypot(Y, Z - GZ) - (CH_R + 0.2))
        d = np.minimum(d, box_e((bx0 - 1, -BAND_TAB, GZ), (bx1 + 1, BAND_TAB, BAND_TOP), rx=0.6)(X, Y, Z))
        return i_round(d, np.abs(X - (bx0 + bx1) / 2) - (bx1 - bx0) / 2, 0.25)
    F.add(band_env, 0.0, bbox=bb(bx0 - 1, bx1 + 1, -BLK_HW - 1, BLK_HW + 1, BLK_BOT - 1, BAND_TOP + 1))
    # --- вырезы ---
    # V-прорезь стойки: открыта спереди и сверху, задняя стенка цела
    notch = Poly(fillet_poly([(-NOTCH_W0, NOTCH_BOT), (NOTCH_W0, NOTCH_BOT), (NOTCH_W1, TW_TOP + 0.3), (NOTCH_W1 + 0.2, TW_TOP + 1.0),
                              (-NOTCH_W1 - 0.2, TW_TOP + 1.0), (-NOTCH_W1, TW_TOP + 0.3)], [1.6, 1.6, 0.6, 0, 0, 0.6], seg=6))
    # (сверху прорезь не выше основания ушей — их дуги над ней не режутся)
    F.sub(prism(notch, "YZ", TW_X[0] + TW_REAR, TW_X[1] + 6.0), 0.45,
          bbox=bb(TW_X[0] + TW_REAR - 1, TW_X[1] + 2, -TW_HW, TW_HW, NOTCH_BOT - 1, TW_TOP + 1.0))
    # гнездо мушки (резьба)
    F.sub(cyl("Z", (POST_X, 0.0), POST_HOLE_R, POST_HOLE_BOT, NOTCH_BOT + 2.0), 0.25,
          bbox=bb(POST_X - 3.5, POST_X + 3.5, -3.5, 3.5, POST_HOLE_BOT - 1, NOTCH_BOT + 1))
    # черта под ушами на боках
    for s in (-1, 1):
        y0, y1 = sorted((s * (TW_HW - 0.25), s * (TW_HW + 2)))
        F.sub(box((TW_X[0] - 2, y0, TW_TOP - 0.3), (TW_X[1] + 2, y1, TW_TOP + 0.35), 0.3), 0.15,
              bbox=bb(TW_X[0] - 1, TW_X[1] + 1, min(y0, y1) - 0.5, max(y0, y1) + 0.5, TW_TOP - 1, TW_TOP + 1))
    # овальные выборки на боках стойки
    oval = Poly(fillet_poly(_xz(OVAL, ZG), [1.2, 1.2, 2.0, 2.0, 1.2, 1.2, 2.0, 2.0], seg=8))
    for s in (-1, 1):
        y0, y1 = sorted((s * (TW_HW - OVAL_D), s * (TW_HW + 2)))
        F.sub(prism(oval, "XZ", y0, y1), 0.45, bbox=bb(xs(494.5), xs(504.5), min(y0, y1) - 0.5, max(y0, y1) + 0.5, 33.0 + ZG, 51.0 + ZG))
    # отверстие петли
    hole = Poly(fillet_poly(_xz(LOOP_HOLE, ZG), [1.0, 0.8, 0.8, 1.0, 1.0], seg=6))
    F.sub(prism(hole, "XZ", -LOOP_HW - 2, LOOP_HW + 2), 0.45, bbox=bb(xs(511.5), xs(518.5), -LOOP_HW - 1, LOOP_HW + 1, 17.0 + ZG, 28.5 + ZG))
    # отверстие под ствол и глухой канал камеры с газоотводом
    F.sub(cyl("X", (0.0, 0.0), BORE, x0 - 3, x1 + 3), 0.35, bbox=bb(x0 - 2, x1 + 2, -BORE - 1, BORE + 1, -BORE - 1, BORE + 1))
    F.sub(cyl("X", (0.0, GZ), CHAN_R, CH_X[0] - 2, CHAN_X1, rim1=1.5), 0.25,
          bbox=bb(CH_X[0] - 1, CHAN_X1 + 1, -CHAN_R - 1, CHAN_R + 1, GZ - CHAN_R - 1, GZ + CHAN_R + 1))
    F.sub(cyl("Z", (CHAN_X1 - 3.0, 0.0), 1.0, 2.0, GZ - 3.0), 0.0, bbox=bb(CHAN_X1 - 5, CHAN_X1 - 1, -2, 2, 1, GZ - 2))
    # паз снизу и головка фиксатора в нём
    sx0, sx1, shw = SLOT
    F.sub(box_e((sx0 - 3, -shw, BLK_BOT - 3), (sx1, shw, SLOT_FLOOR), rz=0.6), 0.45,
          bbox=bb(sx0 - 1, sx1 + 1, -shw - 1, shw + 1, BLK_BOT - 1, SLOT_FLOOR + 1))
    nx, af = NUT

    def nut(X, Y, Z):
        u = X - nx; v = Y
        d = np.maximum(np.abs(v), np.abs(0.8660254 * u + 0.5 * v))
        d = np.maximum(d, np.abs(0.8660254 * u - 0.5 * v)) - af
        return i_round(d, np.abs(Z - (SLOT_FLOOR - 0.7)) - 0.7, 0.3)
    F.add(nut, 0.25, bbox=bb(nx - 4.5, nx + 4.5, -4.5, 4.5, SLOT_FLOOR - 2, SLOT_FLOOR + 0.5))
    F.sub(cyl("Z", (nx, 0.0), 1.1, SLOT_FLOOR - 2.0, SLOT_FLOOR - 0.9), 0.2, bbox=bb(nx - 2, nx + 2, -2, 2, SLOT_FLOOR - 2, SLOT_FLOOR))
    # отверстия штифтов
    for px in PIN_X:
        for s in (-1, 1):
            F.sub(cyl("Z", (px, s * VPIN_Y), VPIN_R + 0.07, BLK_BOT - 2, VPIN_TOP + 0.3), 0.2,
                  bbox=bb(px - 2.5, px + 2.5, s * VPIN_Y - 2.5, s * VPIN_Y + 2.5, BLK_BOT - 1, VPIN_TOP + 1))
    hx, hz = HPIN
    F.sub(cyl("Y", (hx, hz), VPIN_R + 0.07, -BLK_HW - 2, BLK_HW + 2), 0.2, bbox=bb(hx - 2.5, hx + 2.5, -BLK_HW - 1, BLK_HW + 1, hz - 2.5, hz + 2.5))
    # окна обоймы
    for (za, zb), dep in ((BAND_WIN_LO, 1.6), (BAND_WIN_HI, 1.2)):
        hw = BLK_HW + 0.2 if za < GZ else BAND_TAB
        F.sub(box((bx0 + 0.3, -hw - 2, za), (bx1 - 0.3, hw + 2, zb), 0.0), 0.15, bbox=bb(bx0, bx1, -hw - 1, hw + 1, za - 1, zb + 1))
        F.add(box((bx0 - 1, -(hw - dep), za - 1), (bx1 + 1, hw - dep, zb + 1), 0.0), 0.0, bbox=bb(bx0 - 1, bx1 + 1, -hw, hw, za - 1, zb + 1))
    return F


def block_pins(h):
    """Штифты газовой камеры: четыре вертикальных по бокам ствола (в пазах ствола) и поперечный над стволом."""
    F = Field("Gas_Block_Pins", (PIN_X[0] - 2.0, -BLK_HW - 1.0, BLK_BOT - 1.0), (PIN_X[1] + 2.0, BLK_HW + 1.0, HPIN[1] + 2.0), h)
    for px in PIN_X:
        for s in (-1, 1):
            F.add(cyl("Z", (px, s * VPIN_Y), VPIN_R, BLK_BOT + 0.25, VPIN_TOP, rim=0.3),
                  bbox=bb(px - 2, px + 2, s * VPIN_Y - 2, s * VPIN_Y + 2, BLK_BOT - 0.5, VPIN_TOP + 0.5))
    hx, hz = HPIN
    F.add(cyl("Y", (hx, hz), VPIN_R, -BLK_HW + 0.15, BLK_HW - 0.15, rim=0.3), bbox=bb(hx - 2, hx + 2, -BLK_HW, BLK_HW, hz - 2, hz + 2))
    return F


def post(h):
    """Мушка: резьбовой стержень в гнезде стойки, буртик, тонкий конический стержень с плоской вершиной."""
    F = Field("Front_Sight_Post", (POST_X - 3.0, -3.0, POST_HOLE_BOT + 0.5), (POST_X + 3.0, 3.0, POST_TIP + 1.0), h)
    z0 = POST_HOLE_BOT + 1.7
    F.add(cyl("Z", (POST_X, 0.0), 1.85, z0, 42.0, rim=0.3), bbox=bb(POST_X - 3, POST_X + 3, -3, 3, z0 - 1, 43))

    def thread(X, Y, Z):
        # резьба кольцевыми гребнями (шаг 0,5)
        w = smoothstep((Z - z0 - 0.7) / 0.6) * smoothstep((41.3 - Z) / 0.6)     # гребни сходят на нет к концам
        return (-0.12 * np.cos((Z - z0) * (2 * math.pi / 0.5)) - 0.12) * w
    F.displace(thread, bbox=bb(POST_X - 2.5, POST_X + 2.5, -2.5, 2.5, z0 + 0.6, 41.4))
    F.add(cyl("Z", (POST_X, 0.0), 2.2, 41.8, 43.0, rim=0.35), 0.2, bbox=bb(POST_X - 3, POST_X + 3, -3, 3, 41, 44))

    def stem(X, Y, Z):
        r = 1.2 + (0.72 - 1.2) * np.clip((Z - 43.0) / (POST_TIP - 43.0), 0, 1)
        return np.hypot(X - POST_X, Y) - r
    F.add(inter(stem, slab("Z", 42.5, POST_TIP), r=0.2), 0.5, bbox=bb(POST_X - 2.5, POST_X + 2.5, -2.5, 2.5, 42.5, POST_TIP + 0.5))
    return F


# ---------- кольцо с проушиной на стволе за газовой камерой ----------
RING_X = (xs(470.2), xs(476.8))    # R_x0.22: скос сзади 470,2…472, передний торец 476,8; r 9,0
RING_R = 9.0
EYE_X = (xs(473.4), xs(476.8))     # проушина вниз (R_x0.22: X 473,4…476,8, до Z −23,6 от оси; P13 — кольцо с отверстием вдоль X)
EYE_Z, EYE_R, EYE_HOLE = -19.0, 4.6, 2.5


def collar(h):
    F = Field("Barrel_Collar", (RING_X[0] - 1.0, -RING_R - 1.0, EYE_Z - EYE_R - 1.0), (RING_X[1] + 1.0, RING_R + 1.0, RING_R + 1.0), h)
    prof = Poly(fillet_poly([(RING_X[0], 0.0), (RING_X[0], FRONT_R + 0.6), (RING_X[0] + 1.6, RING_R), (RING_X[1], RING_R),
                             (RING_X[1], 0.0)], [0, 0.4, 0.6, 0.5, 0], seg=6))
    F.add(revolve(prof, "X", (0.0, 0.0)))
    ex0, ex1 = EYE_X
    web = Poly(fillet_poly([(-3.0, -5.0), (3.0, -5.0), (3.0, EYE_Z), (-3.0, EYE_Z)], [0, 0, 0, 0]))
    F.add(prism(web, "YZ", ex0, ex1, rim=0.5), 1.2, bbox=bb(ex0 - 1, ex1 + 1, -4.5, 4.5, EYE_Z - 1, -4))
    F.add(cyl("X", (0.0, EYE_Z), EYE_R, ex0, ex1, rim=0.6), 1.0, bbox=bb(ex0 - 1, ex1 + 1, -EYE_R - 1, EYE_R + 1, EYE_Z - EYE_R - 1, EYE_Z + EYE_R + 1))
    F.sub(cyl("X", (0.0, EYE_Z), EYE_HOLE, ex0 - 2, ex1 + 2), 0.5, bbox=bb(ex0 - 1, ex1 + 1, -EYE_HOLE - 1, EYE_HOLE + 1, EYE_Z - EYE_HOLE - 1, EYE_Z + EYE_HOLE + 1))
    F.sub(cyl("X", (0.0, 0.0), FRONT_R + 0.1, RING_X[0] - 2, RING_X[1] + 2), 0.3, bbox=bb(RING_X[0] - 1, RING_X[1] + 1, -8.5, 8.5, -8.5, 8.5))
    return F


def parts():
    C = "Ствол и газовый узел"
    return [
        dict(name="Barrel", build=barrel, coll=C, mat="Steel_blued", sharp=40),
        dict(name="Barrel_Breech", build=breech, h=0.05, coll=C, mat="Steel_blued", parent="Barrel", adapt=0.01),
        dict(name="Gas_Tube", build=gas_tube, h=0.1, coll=C, mat="Steel_blued", parent="Barrel", adapt=0.05),
        dict(name="Gas_Tube_Pins", build=tube_pins, h=0.05, coll=C, mat="Steel_bare", parent="Gas_Tube"),
        dict(name="Gas_Block", build=gas_block, h=0.09, coll=C, mat="Steel_blued", parent="Barrel", adapt=0.05),
        dict(name="Gas_Block_Pins", build=block_pins, h=0.06, coll=C, mat="Steel_bare", parent="Gas_Block"),
        dict(name="Front_Sight_Post", build=post, h=0.04, coll=C, mat="Steel_blued", parent="Gas_Block",
             pivot=[POST_X, 0.0, POST_TIP],
             motion="ход вдоль Z (вворачивается в стойку): ±1,5 мм от вершины Z 59,4 — пристрелка по высоте"),
        dict(name="Barrel_Collar", build=collar, h=0.07, coll=C, mat="Steel_blued", parent="Barrel"),
    ]
