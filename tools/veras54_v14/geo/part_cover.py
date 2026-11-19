# ВЕРАС-54 v14: крышка ствольной коробки — штамповка из листа 0,8 с выштамповкой над окном затворной рамы,
# планка Пикатинни с широкой центральной бороздкой и двумя винтами, обойма-затыльник крышки на заднем скосе (с осями
# и «ушами»), кнопка крышки и колодка-шарнир спереди с пружинами в пазах щёк.
# Места сняты с плиток образца с сеткой в мм (ref_tiles.py → trace/cover, trace/cover/my):
#   правый бок — r_rear.png, r_hi.png (R_x-0.19_z0.32), r_hand.png, r_port.png, r5_block.png (вид R05),
#   левый бок — l_mid.png, l_front.png; сверху — t_a.png, T_x-0.20_f1.0.png; сзади — b_top.png; ракурс Q02 — q02_z.png.
import math

import numpy as np

from dims import *
from sdf import *

TS = 0.8                          # лист крышки (dims: COVER_HW — «лист 0,8 поверх бортов»)
HW = COVER_HW
X0, X1 = COVER_X0, COVER_X1
BOT = COVER_BOT
TOP_Z = 38.2                      # верх крышки по образцу (r_hi, r5_rail: 38,2…38,5); dims.COVER_TOP = 36,5 — см. отчёт
CREASE_Z = 18.8                   # перегиб борта: ниже — отвесный борт, выше — выпуклое плечо к верху (l_mid: блик на Z 19,5)
# плечо борта — полуширина на высоте (B_z0.25_f1.9 с поправкой на перспективу ×1/1,039: 16,4 на Z 22,3; 14,9 на 30,5;
# 13,0 на 34,3; верх ~±10)
SHOULDER = [(16.7, 22.6), (15.0, 30.5), (13.2, 34.6), (10.6, TOP_Z)]
SLOPE_P, SLOPE_A = (30.5, 37.0), 46.5   # задний скос: точка и угол к горизонтали (r_rear: (−1,5; 3,5)…(30; 36), r_hi: 47°)
_SA, _CA = math.sin(math.radians(SLOPE_A)), math.cos(math.radians(SLOPE_A))


def slope_sd(X, Z):
    """Расстояние от плоскости заднего скоса (плюс — снаружи, назад-вверх)."""
    return (SLOPE_P[0] - X) * _SA + (Z - SLOPE_P[1]) * _CA


def slope_x(z):
    """X наружной плоскости скоса на высоте z."""
    return SLOPE_P[0] - (SLOPE_P[1] - z) * _CA / _SA

# окно затворной рамы справа (плитка R_x-0.052_z0.2945_f0.7 → trace/cover/my/r2_port.png): над рамой от X 157,5 до
# переднего торца, верхняя кромка листа Z 17,7 (под ней на плитке тёмная щель до верха рамы 15,6)
WIN_X0, WIN_TOP = 157.5, 17.7
# за окном — только щель хода рукоятки взведения (её верх Z 15,6, середина X 234,5; назад на CARRIER_TRAVEL —
# до X ≈ 130); дальше кромка опускается к низу крышки под рычагом переводчика (оценка: X 118…126)
SLOT_Z = 16.8
SLOT_X0, SLOT_X1 = 118.0, 126.0
# вогнутый желоб над окном (r2_port, t2_port, P20): чёткая кромка-козырёк Z ≈ 30 (сверху — на Y −14,7),
# под ней лист уходит внутрь и плавно выходит к кромке окна; задний верхний угол — дуга R 13 от (157,5; 18)
TR_X0, TR_X1 = 157.5, 238.0
TR_R, TR_RF = 13.5, 3.0           # радиусы заднего и переднего верхних углов желоба
TR_Y0, TR_K, TR_ZC = 13.6, 0.07, 25.0  # профиль дна желоба: |Y| = TR_Y0 + TR_K·(Z − TR_ZC)²
# «ступенька» по низу бортов (l_mid: слева от X 203 вперёд — полоса до Z 10,3, сзади — до Z 7,2; справа — до 7,2)
STEP_X = 203.0
STEP_Z_REAR, STEP_Z_FRONT = 7.2, 10.3
STEP_D = 0.55                     # глубина утопленной полосы (оценка)

# кнопка крышки (T_x-0.20: тёмный прямоугольник X 30,5…38,5, Y ±4; Q02 — скруглённая площадка у верха скоса)
BTN = (31.0, 38.0, 3.9)
BTN_TOP = 39.5                    # оценка: на 1,3 над верхом крышки

# обойма-затыльник (Q02, r_rear, b_top)
CLIP_IN, CLIP_OUT = 0.15, 1.15    # от наружной поверхности крышки: зазор и лист 1,0
CLIP_SIDE = (-6.0, 25.0, 5.0, 20.0)   # боковые накладки X0, X1, Z0, Z1 (r_rear: передний край X 25, верх Z 20, низ Z 5)
# по B_z0.25_f1.9 (сетка g_b.png, поправка перспективы ×1/1,039 к Z −29,5)
BAND_Z = (10.3, 21.2)             # поперечная лента по скосу: нижняя кромка (плитка B_z0.22: 6 мм над коробкой), верх у «ушей»
TONGUE = (7.8, 28.0, 5.5)         # язык ленты вверх по скосу: полуширина, верх Z, радиус углов (Q02 — почти арка)
HOLES = [16.3, 23.1]              # отверстия ленты и языка по Z, Y = 0 (B_z0.22 и шаг 6,8 мм с B_z0.25)
HOLE_R = 1.6                      # Q02: отверстия ~0,2 ширины языка
AXIS = (12.5, 12.5)               # ось обоймы на боковых накладках (r_rear)
DENT = (22.2, 17.0)
WING_Z, WING_DEG = 20.0, 32.0        # крыло обоймы: линия отгиба по верхней кромке накладки и угол отгиба наружу (оценка по Q02, B_z0.22)

# планка: профиль Пикатинни под зажим целика v13 (сечения сетки v13: зажим внутри Y 6,65 до Z 39,4, скос 45° до
# 10,7 на Z 43); пазы — против поперечных болтов целика X 63,2 и 83,2 (v13 42,2 и 62,2 + сдвиг 21)
RAIL_X0_OWN = 113.8               # планка начинается перед основанием целика образца (T_x-0.152_f0.7: торец X 112,7)
RAIL_X1_OWN = 239.8               # образец: зубья кончаются у колодки X 240 (t_a, r5_rail)
RAIL_BASE = TOP_Z + 0.1
NECK_HW = 6.2                     # шейка (v13 6,2)
DOVE_Z0, DOVE_Z1 = 39.3, 43.4     # подрез 45°: от шейки до кромки ласточкина хвоста
TOP_HW = 9.7                      # верхняя площадка до фаски 45°
SLOT_PHASE, PITCH, SLOT_W = 8.9, 10.0, 5.2   # середины пазов 8,9 + 10n (T_x-0.152: пазы 116,3…121,5, 126,3…131,5)
SLOT_BOT = 42.3                   # дно пазов по образцу: зубья 2,2 мм (R05 / r5_rail: зубья видны на Z 42,5…45)
SLOT_BOT_DEEP = 40.6              # под поперечными болтами целика (снизу 40,95) — пазы глубже, их закрывает корпус целика
SLOT_DEEP_X = ()                  # целик v13 убран — углублённых пазов нет
GROOVE_HW, GROOVE_BOT = 5.0, SLOT_BOT  # центральная бороздка ±5 вровень с дном пазов (t_a: Y −4,5…+5,3; P15, P03)
SCREWS = [214.6, 232.1]           # винты планки (t_a: центры головок)

# колодка-шарнир (r5_block, l_front, P03, t_a)
FB_X0, FB_X1 = COVER_X1 + 0.2, RECV_X1 - 0.2
FB_HW = 16.9
FB_TOP = 45.6                     # r5_block: верх 45,6…45,8
FB_IN_HW, FB_IN_TOP = 13.0, 33.4  # проход для ствола, штока поршня (Z до 32,6) и рамы
FB_PIN = (247.5, 11.4)            # ось-заклёпка шарнира (r5_block 11,3; l_front 11,0; задание 11,5)
FB_RIVET = (247.3, 41.2)          # верхняя заклёпка на щеке (r5_block)
FB_POCKET = (FB_X0 - 3.0, 251.0, 5.0)   # углубление сверху, открытое назад к планке (t_a: X 240…254, Y −4,5…+5,3; P03)
FB_CHAMF_X = 252.3                # передний верхний угол колодки срезан 45° вниз к цевью (P03; R05: скос к (258,4; 37,5))
# сварной шов на щеках между накладками (владелец: «пружинка» на образце — шов; R05 справа, l_front слева)
WELD_P0, WELD_P1 = (241.4, 24.6), (258.7, 18.2)
WELD_W, WELD_H = 1.45, 0.85       # полуширина и высота валика
WELD_PITCH = 1.35                 # шаг чешуек


def _section():
    right = [(HW, CREASE_Z)] + SHOULDER
    pts = [(-HW, BOT - 6.0), (HW, BOT - 6.0)] + right + [(-y, z) for y, z in reversed(right)]
    rad = [0, 0] + [2.0, 5.0, 10.0, 5.0, 2.6] + [2.6, 5.0, 10.0, 5.0, 2.0]
    return Poly(smooth_closed(fillet_poly(pts, rad, seg=12), 0.2, 0.4))


SEC = _section()


def outer(X, Y, Z):
    """Наружная форма крышки (сплошное тело): сечение по Y, Z, задний скос 45° и короткий отвесный торец под ним."""
    d = SEC.sd(Y, Z)
    d = i_round(d, slope_sd(X, Z), 4.5)
    d = i_round(d, (X0 - 0.4) - X, 0.8)
    return np.maximum(d, X - (X1 + 4.0))


TR_PANEL = Poly(fillet_poly([(TR_X0, 14.0), (TR_X1, 14.0), (TR_X1, 30.0), (TR_X0, 30.0)], [0, 0, TR_RF, TR_R], seg=16))


def trough(X, Y, Z):
    """Тело, которое вынимается из правого борта над окном: внутри контура панели всё, что снаружи вогнутого дна."""
    floor = TR_Y0 + TR_K * (Z - TR_ZC) ** 2
    return np.maximum(TR_PANEL.sd(X, Z), floor - (-Y))


def cover(h):
    F = Field("Dust_Cover", (X0 - 1.5, -HW - 2.5, BOT - 1.5), (X1 + 1.0, HW + 2.5, TOP_Z + 1.5), h)
    F.add(outer)
    # утопленная полоса по низу бортов: сзади ниже Z 7,2, слева от X 203 вперёд — ниже Z 10,3 (ступенька)
    band_l = Poly(fillet_poly([(X0 - 5, BOT - 5), (X1 + 5, BOT - 5), (X1 + 5, STEP_Z_FRONT), (STEP_X, STEP_Z_FRONT),
                               (STEP_X - 1.2, STEP_Z_REAR), (X0 - 5, STEP_Z_REAR)], [0, 0, 0, 1.8, 1.8, 0]))

    def recess(X, Y, Z):
        f2 = np.where(Y > 0, band_l.sd(X, Z), Z - STEP_Z_REAR)
        return -STEP_D * smoothstep(-f2 / 0.7) * smoothstep((np.abs(Y) - (HW - 2.0)) / 1.2)
    F.displace(recess, bbox=bb(X0 + 3, X1 + 1, -HW - 1, HW + 1, BOT - 1, STEP_Z_FRONT + 2), fine=False)
    F.shell(TS)
    # низ и передний торец открыты
    F.apply(half("Z", BOT, -1), "inter", 0.3)
    F.apply(half("X", X1, 1), "inter", 0.25, bbox=bb(X1 - 2, X1 + 1, -HW - 2, HW + 2, BOT - 1, TOP_Z + 1))
    # вырез справа: подъём кромки под ограждением переводчика, дальше окно затворной рамы до переднего торца
    # одно большое окно: внизу до переднего торца (кромка Z 17,7), выше — до кромки Z 30 по контуру выборки рамы,
    # что видна в окне (передний угол R 3, задний верхний — дуга R 13,5); за окном — щель хода рукоятки
    ax_, az_ = TR_X0 + TR_R, SLOT_Z
    rear_arc = [(ax_ + TR_R * math.cos(math.radians(a)), az_ + TR_R * math.sin(math.radians(a))) for a in range(90, 181, 5)]
    head_ = fillet_poly([(SLOT_X0 - 20, BOT - 5), (X1 + 5, BOT - 5), (X1 + 5, WIN_TOP), (TR_X1, WIN_TOP), (TR_X1, az_ + TR_R),
                         (ax_, az_ + TR_R)], [0, 0, 0, 1.0, TR_RF, 0])
    tail_ = fillet_poly([(TR_X0, SLOT_Z), (SLOT_X1, SLOT_Z), (SLOT_X0, BOT + 0.6), (SLOT_X0 - 20, BOT + 0.6)], [0, 4.0, 3.0, 0])
    win = Poly(head_ + rear_arc[1:-1] + tail_)
    F.sub(prism(win, "XZ", -HW - 4, -HW + 5.5), 0.35, bbox=bb(SLOT_X0 - 2, X1 + 1, -HW - 3, -HW + 5, BOT - 1, az_ + TR_R + 2))
    # отверстие под кнопку на верху
    bx0, bx1, bhw = BTN
    F.sub(prism2(rect2(bx0 - 0.25, bx1 + 0.25, -bhw - 0.25, bhw + 0.25, 1.4), "XY", TOP_Z - 4, TOP_Z + 2), 0.25,
          bbox=bb(bx0 - 2, bx1 + 2, -bhw - 2, bhw + 2, TOP_Z - 3, TOP_Z + 1))
    # отверстия под оси обоймы в бортах
    ax, az = AXIS
    F.sub(cyl("Y", (ax, az), 1.9, -HW - 2, HW + 2), 0.15, bbox=bb(ax - 3, ax + 3, -HW - 1.5, HW + 1.5, az - 3, az + 3))
    return F


# ---------- планка ----------

def _rail_profile():
    """Сечение планки по Y, Z: шейка, подрез 45° (под зажим целика), кромка, фаска к верху."""
    e = DOVE_Z1 - DOVE_Z0
    pts = [(-NECK_HW, RAIL_BASE), (NECK_HW, RAIL_BASE), (NECK_HW, DOVE_Z0), (NECK_HW + e, DOVE_Z1),
           (RAIL_HW, DOVE_Z1), (RAIL_HW, RAIL_TOP - (RAIL_HW - TOP_HW)), (TOP_HW, RAIL_TOP), (-TOP_HW, RAIL_TOP),
           (-RAIL_HW, RAIL_TOP - (RAIL_HW - TOP_HW)), (-RAIL_HW, DOVE_Z1), (-NECK_HW - e, DOVE_Z1), (-NECK_HW, DOVE_Z0)]
    rad = [0, 0, 0.5, 0.25, 0.2, 0.2, 0.35, 0.35, 0.2, 0.2, 0.25, 0.5]
    return Poly(fillet_poly(pts, rad, seg=6))


RAIL_SEC = _rail_profile()


def rail(h):
    xa, xb = RAIL_X0_OWN, RAIL_X1_OWN
    F = Field("Top_Rail", (xa - 1.0, -RAIL_HW - 1.0, RAIL_BASE - 1.0), (xb + 1.0, RAIL_HW + 1.0, RAIL_TOP + 1.0), h)

    def body(X, Y, Z):
        d = RAIL_SEC.sd(Y, Z)
        d = i_round(d, xa - X, 0.4)
        d = i_round(d, X - xb, 0.4)
        # торцы с фаской сверху
        d = np.maximum(d, ((xa + 1.2 - X) + (Z - RAIL_TOP)) * 0.70710678)
        return np.maximum(d, ((X - xb + 1.0) + (Z - RAIL_TOP)) * 0.70710678)
    F.add(body)
    # поперечные пазы шагом 10
    n0 = int(math.ceil((xa - SLOT_PHASE) / PITCH)); n1 = int(math.floor((xb - SLOT_PHASE) / PITCH))
    for n in range(n0, n1 + 1):
        c = SLOT_PHASE + PITCH * n
        s0, s1 = c - SLOT_W / 2, c + SLOT_W / 2
        if s0 < xa + 1.0 or s1 > xb - 1.0:
            continue
        zb = SLOT_BOT_DEEP if any(abs(c - x) < 0.5 for x in SLOT_DEEP_X) else SLOT_BOT
        F.sub(box_e((s0, -RAIL_HW - 2, zb), (s1, RAIL_HW + 2, RAIL_TOP + 3), ry=0.6), 0.3,
              bbox=bb(s0 - 1, s1 + 1, -RAIL_HW - 1, RAIL_HW + 1, zb - 1, RAIL_TOP + 1))
    # центральная бороздка вдоль всей планки (замечание владельца №9: широкая)
    F.sub(box_e((xa + 2.5, -GROOVE_HW, GROOVE_BOT), (xb - 2.5, GROOVE_HW, RAIL_TOP + 3), rx=0.9, rz=1.5), 0.3,
          bbox=bb(xa + 1, xb - 1, -GROOVE_HW - 1, GROOVE_HW + 1, GROOVE_BOT - 1, RAIL_TOP + 1))
    # винты крепления к крышке: головка под шестигранник в бороздке, вокруг — зенковка
    for sx in SCREWS:
        F.sub(cyl("Z", (sx, 0.0), 3.55, GROOVE_BOT - 0.6, GROOVE_BOT + 1.0), 0.2,
              bbox=bb(sx - 5, sx + 5, -5, 5, GROOVE_BOT - 1, GROOVE_BOT + 1))
        F.add(cyl("Z", (sx, 0.0), 3.15, GROOVE_BOT - 0.65, GROOVE_BOT + 0.8, rim=0.45), 0.0,
              bbox=bb(sx - 4, sx + 4, -4, 4, GROOVE_BOT - 1, GROOVE_BOT + 1.5))

        def hexsock(X, Y, Z, sx=sx):
            u = X - sx; v = Y
            d = np.maximum(np.abs(u), np.abs(0.5 * u + 0.8660254 * v))
            d = np.maximum(d, np.abs(-0.5 * u + 0.8660254 * v)) - 1.25
            return np.maximum(d, np.abs(Z - (GROOVE_BOT + 0.8)) - 1.0)
        F.sub(hexsock, 0.12, bbox=bb(sx - 2, sx + 2, -2, 2, GROOVE_BOT - 0.2, GROOVE_BOT + 1.5))
    return F


# ---------- кнопка ----------

def button(h):
    bx0, bx1, bhw = BTN
    F = Field("Cover_Button", (bx0 - 1.8, -bhw - 2.0, TOP_Z - 3.0), (bx1 + 1.8, bhw + 2.0, BTN_TOP + 0.8), h)
    # площадка: задняя кромка скошена к скосу крышки
    cap = box((bx0, -bhw, TOP_Z - 2.4), (bx1, bhw, BTN_TOP), 1.1)
    F.add(cap)
    F.apply(plane((bx0 + 0.9, 0, BTN_TOP), (-0.6, 0, 0.8)), "inter", 0.8)
    # рифление поперёк — пять рёбер под палец (Q02: рифлёная площадка у верха скоса)
    for k in range(5):
        xr = bx0 + 1.9 + k * 1.15
        F.add(cyl("Y", (xr, BTN_TOP - 0.15), 0.32, -bhw + 0.9, bhw - 0.9, rim=0.3), 0.25,
              bbox=bb(xr - 1, xr + 1, -bhw, bhw, BTN_TOP - 1, BTN_TOP + 0.6))
    # фланец изнутри под листом: держит кнопку в отверстии
    # (сзади фланец короче: там изнутри уже наклонный лист скоса)
    F.add(box((bx0 + 2.5, -bhw - 1.0, TOP_Z - 2.9), (bx1 + 1.2, bhw + 1.0, TOP_Z - 1.85), 0.4), 0.5,
          bbox=bb(bx0 - 2, bx1 + 2, -bhw - 2, bhw + 2, TOP_Z - 3, TOP_Z - 0.4))
    return F


# ---------- обойма-затыльник ----------

def rear_block(h):
    F = Field("Cover_Rear_Block", (X0 - 4.0, -HW - 4.5, BOT - 0.5), (27.0, HW + 4.5, 31.0), h)
    sx0, sx1, sz0, sz1 = CLIP_SIDE
    side2 = rect2(sx0, sx1, sz0, sz1, 1.5)
    tw, tz, tr = TONGUE
    band2 = union2(rect2(-40, 40, BAND_Z[0], BAND_Z[1], 0.0), rect2(-tw, tw, BAND_Z[1] - 6, tz, tr), r=1.6)

    def clip(X, Y, Z):
        dc = outer(X, Y, Z)
        shell = np.maximum(dc - CLIP_OUT, CLIP_IN - dc)
        m_side = np.maximum(side2(X, Z), (HW - 1.3) - np.abs(Y))
        m_band = np.maximum(band2(Y, Z), -slope_sd(X, Z) - 2.2)
        return i_round(shell, np.minimum(m_side, m_band), 0.22)
    F.add(clip)
    # отбортовка нижней кромки ленты: кромка отогнута наружу валиком (Q02, P10)
    lip2 = rect2(-40, 40, BAND_Z[0], BAND_Z[0] + 1.3, 0.0)

    def lip(X, Y, Z):
        dc = outer(X, Y, Z)
        sh = np.maximum(dc - (CLIP_OUT + 0.55), CLIP_IN - dc)
        m = np.maximum(lip2(Y, Z), -slope_sd(X, Z) - 2.2)
        m = np.maximum(m, np.abs(Y) - (HW + 0.3))
        return i_round(sh, m, 0.3)
    F.add(lip, 0.3, bbox=bb(X0 - 2, 12, -HW - 3, HW + 3, BAND_Z[0] - 1.5, BAND_Z[0] + 2.5))
    # полоса под лентой на скосе: тот же лист ниже ленты через узкую щель-перегиб (B_z0.22: полоса Z 5,2…9,4)
    low2 = rect2(-40, 40, BOT + 0.5, BAND_Z[0] - 0.9, 0.0)

    def lowband(X, Y, Z):
        dc = outer(X, Y, Z)
        sh = np.maximum(dc - CLIP_OUT, CLIP_IN - dc)
        m = np.maximum(low2(Y, Z), -slope_sd(X, Z) - 2.2)
        return i_round(sh, m, 0.22)
    F.add(lowband, 0.0, bbox=bb(X0 - 3, 8, -HW - 3, HW + 3, BOT - 0.5, BAND_Z[0]))
    # V-надрез задней кромки боковой накладки у нижней кромки ленты (r_rear: «<» на Z ≈ 10)
    for s_ in (-1, 1):
        zc = BAND_Z[0] - 0.4
        xc = slope_x(zc)
        vn = Poly([(xc - 3.0, zc - 1.6), (xc - 3.0, zc + 1.6), (xc + 2.4, zc)])
        y0, y1 = sorted((s_ * (HW - 0.6), s_ * (HW + 3.0)))
        F.sub(prism(vn, "XZ", y0, y1), 0.2, bbox=bb(xc - 4, xc + 3.5, y0 - 0.5, y1 + 0.5, zc - 3, zc + 3))
    # «уши» — треугольные крылья заодно с обоймой (Q01, Q02, P10): основание — верхняя кромка боковой накладки
    # от скоса вперёд, лист отогнут наружу плавным радиусом, задняя кромка идёт вдоль скоса, вершина скруглена, на крыле лунка
    zb = WING_Z
    xs = slope_x(zb)
    wing2 = Poly(fillet_poly([(xs - 0.4, zb - 1.6), (xs + 8.2, zb - 1.6), (xs + 8.2, zb), (slope_x(27.4) + 0.4, 27.4), (xs - 0.4, zb)],
                             [0, 0, 1.2, 2.0, 0.6]))
    base2 = rect2(xs - 0.4, xs + 8.2, zb - 2.0, zb + 0.3, 0.0)
    for s in (-1, 1):
        y0, y1 = sorted((s * (HW + CLIP_IN), s * (HW + CLIP_OUT)))
        ym = s * (HW + (CLIP_IN + CLIP_OUT) / 2)
        wing = rot(prism(wing2, "XZ", y0, y1, rim=0.3), "X", (0, ym, zb), -s * WING_DEG)
        base = prism2(base2, "XZ", y0, y1)
        F.add(union(base, wing, r=0.9), 0.6, bbox=bb(xs - 3, xs + 11, s * HW - 6, s * HW + 6, zb - 3, 30))
        # лунка-выдавка на крыле
        ec = (xs + 4.4, zb + 3.0)
        F.sub(rot(sphere((ec[0], ym + s * (0.5 + 1.75 - 0.35), ec[1]), 1.75), "X", (0, ym, zb), -s * WING_DEG), 0.2,
              bbox=bb(ec[0] - 2.5, ec[0] + 2.5, s * HW - 6, s * HW + 6, ec[1] - 2.5, ec[1] + 2.5))
    # отверстия ленты и языка: ось по нормали скоса
    for zh in HOLES:
        xh = slope_x(zh) - (CLIP_IN + CLIP_OUT) / 2 * _SA
        F.sub(rot(cyl("X", (0.0, zh), HOLE_R, xh - 3, xh + 3), "Y", (xh, 0, zh), 45.0), 0.25,
              bbox=bb(xh - 3, xh + 3, -3, 3, zh - 3, zh + 3))
    ax, az = AXIS
    dx, dz = DENT
    for s in (-1, 1):
        yo = s * (HW + CLIP_OUT)
        # шайба-бобышка и полукруглая головка оси
        # (r_rear: кольца r 4,6 и 3,0, головка r 1,9)
        y0, y1 = sorted((yo - s * 0.1, yo + s * 0.45))
        F.add(cyl("Y", (ax, az), 4.6, y0, y1, rim=0.25), 0.2, bbox=bb(ax - 6, ax + 6, y0 - 1, y1 + 1, az - 6, az + 6))
        y0, y1 = sorted((yo + s * 0.3, yo + s * 0.95))
        F.add(cyl("Y", (ax, az), 3.0, y0, y1, rim=0.25), 0.15, bbox=bb(ax - 4, ax + 4, y0 - 1, y1 + 1, az - 4, az + 4))
        hgt, r = 0.8, 1.95
        rs = (r * r + hgt * hgt) / (2 * hgt)
        yb = yo + s * 0.95
        cy = yb + s * (hgt - rs)

        def head(X, Y, Z, cy=cy, yb=yb, s=s):
            d = np.sqrt((X - ax) ** 2 + (Y - cy) ** 2 + (Z - az) ** 2) - rs
            return np.maximum(d, s * (yb - 0.2 - Y))
        F.add(head, 0.2, bbox=bb(ax - 3, ax + 3, min(yb, yb + s * 2) - 1, max(yb, yb + s * 2) + 1, az - 3, az + 3))
        # ось насквозь через лист крышки (посадка в отверстии r 1,9), торец изнутри скруглён
        yi = s * (HW - TS - 0.15)
        y0, y1 = sorted((yi, yo))
        F.add(cyl("Y", (ax, az), 1.8, y0, y1, rim=0.3), 0.0, bbox=bb(ax - 3, ax + 3, y0 - 0.5, y1 + 0.5, az - 3, az + 3))
        # выдавленная лунка на накладке
        F.sub(sphere((dx, yo + s * 3.2, dz), 3.55), 0.3, bbox=bb(dx - 3, dx + 3, yo - 1.5, yo + 1.5, dz - 3, dz + 3))
    return F


# ---------- колодка-шарнир ----------

def _spring_dir():
    ux, uz = WELD_P1[0] - WELD_P0[0], WELD_P1[1] - WELD_P0[1]
    L = math.hypot(ux, uz)
    return ux / L, uz / L, L


def front_block(h):
    F = Field("Front_Block", (FB_X0 - 1.0, -FB_HW - 2.5, BOT - 1.0), (FB_X1 + 1.0, FB_HW + 2.5, FB_TOP + 1.0), h)
    F.add(box_e((FB_X0, -FB_HW, BOT), (FB_X1, FB_HW, FB_TOP), rx=1.4, ry=1.0, rz=1.2))
    # проход: ствол, шток поршня, рама — колодка стоит на щёках
    F.sub(box_e((FB_X0 - 3, -FB_IN_HW, BOT - 3), (FB_X1 + 3, FB_IN_HW, FB_IN_TOP), rx=2.0), 0.4,
          bbox=bb(FB_X0 - 1, FB_X1 + 1, -FB_IN_HW - 1, FB_IN_HW + 1, BOT - 1, FB_IN_TOP + 1))
    # углубление сверху
    px0, px1, phw = FB_POCKET
    F.sub(box((px0, -phw, FB_TOP - 2.6), (px1, phw, FB_TOP + 3), 2.0), 0.4, bbox=bb(px0 - 1, px1 + 1, -phw - 1, phw + 1, FB_TOP - 3.5, FB_TOP + 1))
    F.apply(plane((FB_CHAMF_X, 0.0, FB_TOP), (1.0, 0.0, 1.0)), "inter", 1.2,
            bbox=bb(FB_CHAMF_X - 3, FB_X1 + 1, -FB_HW - 2, FB_HW + 2, FB_TOP - (FB_X1 - FB_CHAMF_X) - 3, FB_TOP + 1))
    ux, uz, L = _spring_dir()
    # верхняя накладка — трапеция со скосом вниз-вперёд (R05: низ Z 37,3, скос от (250,2; 45,3) к (258,4; 37,3));
    # нижняя — под швом: верхняя кромка вдоль шва, дуга вокруг оси шарнира (l_front)
    up = Poly(fillet_poly([(242.3, 37.3), (FB_X1 - 0.5, 37.3), (FB_X1 - 0.5, FB_TOP - 0.9 - (FB_X1 - 0.5 - FB_CHAMF_X)), (FB_CHAMF_X - 0.5, FB_TOP - 0.4), (242.3, FB_TOP - 0.4)], [1.0, 0.6, 0.8, 1.5, 2.2]))
    ofs = WELD_W + 1.3
    k = uz / ux
    low = Poly(fillet_poly([(242.6, WELD_P0[1] - ofs + (242.6 - WELD_P0[0]) * k), (242.6, 7.6), (FB_X1 - 0.5, 7.6),
                            (FB_X1 - 0.5, WELD_P0[1] - ofs + (FB_X1 - 0.5 - WELD_P0[0]) * k)], [0.8, 4.8, 1.0, 1.0]))
    for s in (-1, 1):
        yo = s * FB_HW
        # накладки щёк: верхняя со скошенным передним углом и нижняя с дугой вокруг оси шарнира
        for pl in (up, low):
            y0, y1 = sorted((yo - s * 0.3, yo + s * 0.6))
            F.add(prism(pl, "XZ", y0, y1, rim=0.0, rim1=0.3) if s > 0 else prism(pl, "XZ", y0, y1, rim=0.3, rim1=0.0), 0.2,
                  bbox=bb(FB_X0, FB_X1, y0 - 0.5, y1 + 0.5, BOT, FB_TOP))
        # заклёпки: верхняя полукруглая, ось шарнира — плоская головка
        for (cx, cz), kind in (() if PLAIN else ((FB_RIVET, "dome"), (FB_PIN, "flat"))):
            yb = yo + s * 0.6
            if kind == "dome":
                hgt, r = 1.15, 2.5
                rs = (r * r + hgt * hgt) / (2 * hgt)
                cy = yb + s * (hgt - rs)

                def head(X, Y, Z, cy=cy, yb=yb, s=s, cx=cx, cz=cz, rs=rs):
                    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - rs
                    return np.maximum(d, s * (yb - 0.2 - Y))
                F.add(head, 0.2, bbox=bb(cx - 3.5, cx + 3.5, min(yb, yb + s * 2) - 1, max(yb, yb + s * 2) + 1, cz - 3.5, cz + 3.5))
            else:
                y0, y1 = sorted((yb - s * 0.3, yb + s * 0.55))
                F.add(cyl("Y", (cx, cz), 3.0, y0, y1, rim=0.3), 0.15, bbox=bb(cx - 4, cx + 4, y0 - 1, y1 + 1, cz - 4, cz + 4))
    # сварной шов: выпуклый валик смещением поверхности щеки, чешуйки внахлёст, кратеры на концах
    F.displace(weld, bbox=bb(WELD_P0[0] - 3, FB_X1 + 0.5, -FB_HW - 1.5, FB_HW + 1.5,
                             WELD_P1[1] - 4, WELD_P0[1] + 4), fine=True)
    return F


def weld(X, Y, Z):
    """Высота сварного валика над щекой: сечение — пологий купол со сходом на металл, вдоль шва — серповидные
    чешуйки (выпуклостью к началу шва) с неровным шагом и шириной, на концах — округлые кратеры."""
    ux, uz, L = _spring_dir()
    t = (X - WELD_P0[0]) * ux + (Z - WELD_P0[1]) * uz          # вдоль шва
    d = -(X - WELD_P0[0]) * uz + (Z - WELD_P0[1]) * ux         # поперёк (в плоскости щеки)
    # неровность: ширина и сдвиг оси медленно гуляют
    w = WELD_W * (1.0 + 0.08 * np.sin(t * 1.9 + 0.7) + 0.05 * np.sin(t * 4.3))
    d = d - 0.12 * np.sin(t * 0.9 + 1.3)
    q = np.clip(np.abs(d) / w, 0.0, 1.5)
    prof = np.where(q < 1.0, (1.0 - q * q) ** 1.6, 0.0)     # купол, плавно сходит на металл
    # чешуйки: фаза с изгибом по ширине — дуги выпуклостью назад вдоль шва
    ph = (t + 0.55 * w * (d / w) ** 2 + 0.18 * np.sin(t * 2.3)) / WELD_PITCH
    fr = ph - np.floor(ph)
    ripple = 0.86 + 0.14 * (0.5 - 0.5 * np.cos(2 * np.pi * fr ** 0.55))   # непрерывно, гребень смещён — чешуя внахлёст
    # концы: сход и округлый кратер
    end = smoothstep(t / 1.2) * smoothstep((L - t) / 1.2)
    crater = 1.0 - 0.35 * np.exp(-((L - 0.9 - t) ** 2 + d * d) / 0.8) - 0.25 * np.exp(-((t - 0.9) ** 2 + d * d) / 0.8)
    h = WELD_H * prof * ripple * end * crater
    face = smoothstep((np.abs(Y) - (FB_HW + 0.2 - 1.2)) / 0.6)    # только у наружной грани щеки
    return h * face


def parts():
    return [
        dict(name="Dust_Cover", build=cover, h=0.11, coll="Крышка и планка", mat="Steel_blued", adapt=0.06,
             pivot=[FB_PIN[0], 0.0, FB_PIN[1]],
             motion="оценка: поворот вокруг Y на оси колодки (247,5; 11,4), задний край вверх до ~60°"),
        dict(name="Top_Rail", build=rail, h=0.07, coll="Крышка и планка", mat="Steel_blued", parent="Dust_Cover", adapt=0.05),
        dict(name="Cover_Rear_Block", build=rear_block, h=0.07, coll="Крышка и планка", mat="Steel_blued", parent="Dust_Cover"),
        dict(name="Cover_Button", build=button, h=0.05, coll="Крышка и планка", mat="Steel_phosphate", parent="Dust_Cover",
             pivot=[(BTN[0] + BTN[1]) / 2, 0.0, TOP_Z], motion="оценка: нажатие вниз (−Z) на 1,2 мм"),
        dict(name="Front_Block", build=front_block, h=0.07, coll="Крышка и планка", mat="Steel_blued", adapt=0.05),
    ]
