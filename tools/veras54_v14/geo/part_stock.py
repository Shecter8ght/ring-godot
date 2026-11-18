# ВЕРАС-54 v14: складной приклад — шарнир на левом борту у заднего торца коробки (колодка с неподвижными петлями,
# ось, защёлка на оси с пружиной), узел приклада (рамка-«воротник» за коробкой, подвижные петли, нижняя планка под
# трубой), труба с метками положений «1 2 3», скелетный приклад с окнами, рычагом регулировки длины, гнездом QD
# сбоку, стойкой-антабкой QD снизу и резиновым затыльником с рёбрами.
# Места сняты с плиток образца с сеткой в мм (trace/stock_me): бок — R_x-0.43_z0.24, R_x-0.31_z0.24 (и R01 со сдвигом
# X +2,2, Z +0,4 — его камера стоит не там, где плиток), шарнир — R_x-0.20 / L_x-0.20 (R_hinge, L_hinge, l_hinge2),
# сверху — T_x-0.43 / T_x-0.31 / T_x-0.20, снизу — U_x-0.43 / U_x-0.31, сзади — B_z0.22 (с поправкой на глубину).
import math

import numpy as np

from dims import *
from sdf import *

# ---------------- шарнир ----------------
HX, HY = 5.8, 18.8            # ось шарнира (X, Y): петли по образцу на X 2…9,6 (l_hinge2); ось ближе к борту, чем
                              # HINGE_Y 19,5, — колонка прижата к борту, наружу до Y ≈ 20,7 (B_z0.22: ≈ 21)
KN_R = 3.8                    # петли: ширина вдоль X 7,6 (l_hinge2)
KN_FLAT = 1.9                 # петли сплющены с боков: ±1,9 от оси по Y (симметрично — после складывания на 180°
                              # петля встаёт на то же место)
PIN_R = 1.6                   # ось
BORE = 1.72                   # отверстие петель под ось
WALL_Y = RECV_HW + 0.2        # внутренняя плоскость — по борту коробки (снаружи листа 16,5)
# петли по высоте вплотную (зазор 0,2; l_hinge2, L07, P10): K1, K3, K6 — на узле приклада, K2, K5 — на колодке
K1 = (-1.5, 4.0)
K2 = (-8.6, -1.7)
K3 = (-15.8, -8.8)
LATCH_Z = (-22.4, -16.0)      # колодка защёлки на оси с языком назад
SPRING_Z = (-25.55, -22.55)   # пружина под колодкой (на образце видна витками: l_hinge2 Z −22,5…−25,5)
K5 = (-31.4, -25.75)
K6 = (-37.6, -31.6)
KN_TOP, KN_BOT = K1[1], K6[0]
LEAF_Z = [K2, (K5[0], LATCH_Z[1])]   # полка колодки — у неподвижных петель, защёлки и пружины
LEAF_X = (9.95, 11.2)         # отогнутая полка колодки вдоль борта (l_hinge2: полоса X 9,8…10,8)
LATCH_DROP = 1.2              # ход защёлки вниз по оси до сжатия пружины (оценка)

# ---------------- узел приклада ----------------
COL_X = (-2.75, -0.4)         # рамка за коробкой (R_hinge: X −2,6…−0,3; L_hinge: 0…−2,5)
COL_Y = (-16.6, 15.2)         # T_hinge: правый край Y −16,5
COL_Z = (-36.6, 0.3)          # R_hinge: Z 0…−36,5
TUBE_Z = STOCK_AXIS_Z         # ось трубы (R_x-0.31: верх −5,4, низ −31,7)
TUBE_R = 13.2                 # по образцу (у dims оценка 13,5)
TUBE_X = (-130.0, -3.65)      # задний конец спрятан в приклад (ход регулировки 40)
BAR_Z = (-34.2, -31.85)       # нижняя планка под трубой (R_x-0.31: Z −31…−34)
BAR_HW = 14.0                 # U_x-0.31: Y −15…+13
BAR_X0 = -59.7
BAR_SLOT = (-57.0, -8.0, 7.3)   # прорезь планки: X от, до, полуширина (U_x-0.31)
BAR_TAB = (-17.5, -7.5, -35.4)  # упор под планкой (R_x-0.31: X −18…−8, до Z −35)

# ---------------- приклад ----------------
S_TOP = -3.6                  # верх корпуса (R_x-0.43: −3,5…−4)
S_X0, S_X1 = -212.6, -60.0    # задняя плоскость корпуса (стык с затыльником; R_x-0.43 в наложении) и передний торец
HOUS_BOT = -30.5              # низ круглого корпуса трубы (тень под ним на R_x-0.43 — Z −28…−31)
HOUS_HW = 16.6                # T_x-0.43, U_x-0.43, B: ширина 33–34 (у dims STOCK_HW = 20 — оценка, образец уже)
FRAME_HW = 15.6               # боковины скелета на 1 мм глубже корпуса (тень под корпусом)
S_BOT = -139.0                # низ скелета (B, R01); у затыльника его срезает овал PAD_OVAL
# контур затыльника сзади (B_z0.215 по сетке, trace/stock_me/B215_*): прямые боковины, концы — полуэллипсы во всю
# ширину: верх — от Z −10,5 у боковин до −3,5 посередине, низ — от −131,5 до −139,5
PAD_OVAL = (-10.5, 7.0, -131.5, 8.0)
PAD_X = (STOCK_X_BUTT - 1.6, S_X0 - 0.15)   # по образцу затыльник на 1,6 длиннее dims (наложение на R_x-0.43)
PAD_HW = 17.2                 # B_butt2: Y −16,4…+17,2; U: ±17,5
# наружный контур скелета (X, Z): передний торец, нижняя «лапа», нижняя кромка раскоса, низ, задняя стойка
# (низ — по R01 с сеткой, привязанной к нашему кадру той же камерой: trace/stock_me/g_r01_low.png)
FRAME = [(-59.0, -24.0), (-59.0, -47.0), (-61.6, -52.5), (-63.3, -58.6), (-66.1, -63.7), (-69.8, -67.9), (-74.5, -72.1),
         (-78.7, -74.9), (-81.6, -77.3), (-83.9, -81.1), (-86.7, -83.4), (-90.9, -84.3), (-96.6, -84.6), (-102.7, -87.2),
         (-116.7, -93.6), (-193.0, S_BOT), (-219.0, S_BOT), (-219.0, -24.0)]
FRAME_R = [0.0, 3.0, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 3.0, 4.0, 0.0, 0.0]
# большое окно: задняя кромка, низ, раскос вверх к «лапе»; сверху до рычага (R43_lever, R31_lobe)
WIN_UP = [(-194.8, -81.0), (-175.0, -61.0), (-171.5, -55.5), (-140.0, -58.0), (-110.0, -61.5), (-102.8, -62.5),
          (-106.3, -70.0), (-158.3, -103.3), (-194.8, -103.3)]
WIN_UP_R = [3.0, 4.0, 1.5, 3.0, 2.0, 1.5, 2.0, 3.0, 3.5]
# узкая прорезь вдоль раскоса (правый конец — R31_lobe: X −102, Z −76…−81), внизу — широкая часть над перекладиной
WIN_LOW = [(-207.5, -119.6), (-180.0, -118.0), (-104.0, -75.8), (-101.8, -77.2), (-101.8, -79.8), (-104.0, -81.2),
           (-172.0, -119.8), (-192.0, -128.4), (-207.5, -128.4)]
WIN_LOW_R = [3.0, 2.0, 1.0, 0.8, 0.8, 1.0, 2.0, 3.0, 3.0]
WIN_TL = [(-207.0, -63.8), (-188.5, -63.8), (-188.5, -69.6), (-207.0, -69.6)]   # прорезь над окном (R43_lever)
WIN_TL_R = 2.8
QD = (-74.5, -55.9, 6.8)      # гнездо QD сбоку (R31_lobe)
HOLES = [(-134.6, -37.4, 2.5), (-106.5, -36.9, 2.5)]   # глухие отверстия в корпусе (торцы осей в глубине)
NUT = (-181.0, -58.6)         # шестигранная гайка в гнезде (R43_lever: гнездо r 3,4)
STUD = (-88.4, -89.8)         # стойка QD снизу: X оси и нижний торец (R31_lobe)
STUD_R = 8.6
# рычаг регулировки длины: П-образный — две щеки по бокам скелета и рифлёный хвост снизу; ось — винт спереди
LEVER_AX = (-90.4, -53.2)     # ось рычага — винт с шестигранной головкой (R31_lobe)
LEVER = [(-171.5, -56.0), (-168.0, -54.3), (-138.0, -47.3), (-124.0, -46.6), (-92.0, -46.6), (-86.0, -49.0),
         (-85.6, -54.0), (-88.0, -58.3), (-94.0, -58.5), (-123.0, -63.0), (-140.0, -70.8), (-160.0, -73.2), (-171.5, -72.2)]
LEVER_R = [1.5, 2.0, 6.0, 4.0, 2.5, 2.0, 2.0, 2.0, 3.0, 5.0, 4.0, 3.0, 2.5]
LOW_GROOVE = 2.6              # глубина канавки вдоль раскоса с каждого бока (раскос сплошной — Q04, P09)
PLUNGER = (-91.5, -59.4, -63.6, 1.4)   # прорезь фиксатора под осью: X, Z от, до, полуширина (R31_lobe)
LEVER_RIVET = (-129.3, -54.4)  # заклёпка на щеке (R43_lever: круглая головка r 2,6)
LEVER_RIBS = [-165.5, -161.3, -157.0, -152.6, -148.3]   # рифление хвоста (R43_lever)
LEV_IN = FRAME_HW - 0.7       # щека рычага: внутренняя плоскость (боковина под ней утоплена)
LEV_OUT = FRAME_HW + 0.5
LEVER_DEG = 2.0               # нажатие: хвост вверх до упора (оценка, как в part_rig)
STOCK_TRAVEL = 40.0           # ход регулировки назад, 3 положения через 20 мм (метки трубы — оценка)


def _poly(pts, r, seg=10):
    return Poly(fillet_poly(pts, r, seg=seg))


# ---------------- шарнир ----------------

def _barrel2():
    """Петля в плане (X, Y): круг вокруг оси, сплющенный с боков до ±KN_FLAT."""
    circ = circle2((HX, HY), KN_R)

    def f(U, V):
        return i_round(circ(U, V), np.abs(V - HY) - KN_FLAT, 0.6)
    return f


def _moving2():
    """Подвижная петля: сзади оси — как неподвижная, спереди — полукруг r KN_FLAT: при складывании влево
    (по часовой сверху) передняя половина проходит мимо борта, задняя уходит наружу."""
    bar = _barrel2()
    front = circle2((HX, HY), KN_FLAT)

    def f(U, V):
        rear = i_round(bar(U, V), U - HX, 0.0)
        return u_round(rear, front(U, V), 0.4)
    return f


def hinge_base(h):
    F = Field("Hinge_Base", (HX - KN_R - 1, WALL_Y - 1, KN_BOT - 1), (LEAF_X[1] + 1, HY + KN_FLAT + 1, KN_TOP + 1), h)
    plan = union2(_barrel2(), rect2(HX, LEAF_X[0] + 0.3, HY - KN_FLAT, HY + KN_FLAT, 0.5), r=0.6)
    for z0, z1 in (K2, K5):
        F.add(prism2(plan, "XY", z0, z1, rim=0.4), 0.0, bbox=bb(HX - KN_R - 1, LEAF_X[1] + 1, WALL_Y - 1, HY + KN_FLAT + 1, z0 - 1, z1 + 1))
    # полка вдоль борта, приварена к борту; на высотах подвижных петель её нет — там при складывании проходят
    # перемычки узла приклада
    for z0, z1 in LEAF_Z:
        F.add(box((LEAF_X[0], HY - KN_FLAT, z0), (LEAF_X[1], HY + KN_FLAT, z1), 0.4), 0.6,
              bbox=bb(LEAF_X[0] - 2, LEAF_X[1] + 1, WALL_Y - 1, HY + KN_FLAT + 1, z0 - 1, z1 + 1))
        # сварной шов полки и борта — валик вдоль угла
        F.add(cyl("Z", (LEAF_X[1] + 0.05, HY - KN_FLAT + 0.05), 0.55, z0 + 0.6, z1 - 0.6, rim=0.3), 0.2,
              bbox=bb(LEAF_X[1] - 1, LEAF_X[1] + 1, WALL_Y - 0.5, HY - KN_FLAT + 1.2, z0, z1))
    F.apply(half("Y", WALL_Y, -1), "inter", 0.0)
    F.sub(cyl("Z", (HX, HY), BORE, KN_BOT - 2, KN_TOP + 2), 0.15)
    return F


def hinge_pin(h):
    """Ось шарнира: стержень с плоскими головками-заклёпками сверху и снизу."""
    zb, zt = KN_BOT - 0.55, KN_TOP + 0.55
    hr = KN_FLAT - 0.05
    prof = [(zb, 0.0), (zb, hr - 0.4), (zb + 0.15, hr - 0.1), (zb + 0.4, hr), (KN_BOT - 0.06, hr), (KN_BOT - 0.06, PIN_R),
            (KN_TOP + 0.06, PIN_R), (KN_TOP + 0.06, hr), (zt - 0.4, hr), (zt - 0.15, hr - 0.1), (zt, hr - 0.4), (zt, 0.0)]
    return lathe_mesh(prof, seg=48, axis="Z", c=(HX, HY), closed=False)


def hinge_latch(h):
    """Защёлка: крупная колодка на оси с языком назад, крюк языка заходит за рамку узла приклада."""
    z0, z1 = LATCH_Z
    F = Field("Hinge_Latch", (-6.5, 12.8, z0 - 1), (HX + KN_R + 1, HY + KN_FLAT + 1.5, z1 + 1), h)
    plan = union2(_barrel2(), rect2(-5.6, HX, WALL_Y + 0.25, HY + KN_FLAT + 0.3, 0.7), r=0.8)
    F.add(prism2(plan, "XY", z0, z1, rim=0.5))
    # крюк за рамкой: внутрь до Y 13,9 (труба — до 13,2)
    F.add(box_e((-5.6, 13.9, z0 + 0.6), (-3.85, WALL_Y + 1.0, z1 - 0.6), rx=0.4, ry=0.4, rz=0.4), 0.4,
          bbox=bb(-6.5, -3, 13, WALL_Y + 2, z0, z1))
    # насечка нажима на наружной грани колодки
    for k in range(5):
        x = 3.3 + k * 1.2

        def rib(X, Y, Z, x=x):
            return 0.14 * smoothstep(1 - np.abs(X - x) / 0.35) * smoothstep((Y - (HY + KN_FLAT - 0.6)) / 0.4)
        F.displace(rib, bbox=bb(x - 1, x + 1, HY, HY + KN_FLAT + 1.5, z0, z1), fine=True)
    F.sub(cyl("Z", (HX, HY), BORE + 0.03, z0 - 2, z1 + 2), 0.15)
    F.apply(half("Y", WALL_Y, -1), "inter", 0.3, bbox=bb(-0.3, HX + KN_R + 1, WALL_Y - 2, WALL_Y + 1, z0 - 1, z1 + 1))
    return F


def hinge_spring(h):
    """Витая пружина вокруг оси между колодкой защёлки и петлёй K5, концы поджаты."""
    z0, z1 = SPRING_Z
    wr = 0.24; R = PIN_R + 0.12 + wr
    turns = 4.0
    pts = []
    n = int(turns * 48)
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        # поджатые концы: на первом и последнем витке шаг — толщина проволоки
        tt = t * turns
        live = turns - 2 * 0.75
        if tt < 0.75:
            z = z0 + wr + tt * 2 * wr
        elif tt > turns - 0.75:
            z = z1 - wr - (turns - tt) * 2 * wr
        else:
            z = z0 + wr + 0.75 * 2 * wr + (tt - 0.75) / live * (z1 - z0 - 2 * wr - 2 * 0.75 * 2 * wr)
        pts.append((HX + R * math.cos(a), HY + R * math.sin(a), z))
    return tube_mesh(np.array(pts), wr, 10)


# ---------------- узел приклада ----------------

def stock_knuckle(h):
    F = Field("Stock_Knuckle", (BAR_X0 - 1, COL_Y[0] - 1, KN_BOT - 1), (HX + KN_R + 1, HY + KN_FLAT + 1, KN_TOP + 1), h)
    # рамка за коробкой
    F.add(prism2(rect2(COL_Y[0], COL_Y[1], COL_Z[0], COL_Z[1], 1.6), "YZ", COL_X[0], COL_X[1], rim=0.55))
    # подвижные петли K1, K3 и перемычки к рамке: огибают задний угол коробки (на виде сверху — скос)
    arm = Poly(fillet_poly([(COL_X[0], 10.5), (COL_X[0], 15.4), (0.6, HY + KN_FLAT), (HX - 0.5, HY + KN_FLAT),
                            (HX - 0.5, WALL_Y), (COL_X[1] + 0.05, WALL_Y), (COL_X[1] + 0.05, 10.5)], [0.0, 1.5, 1.5, 0.0, 0.0, 1.0, 0.0]))
    plan = union2(lambda U, V: arm.sd(U, V), _moving2(), r=0.8)
    for z0, z1 in (K1, K3, K6):
        F.add(prism2(plan, "XY", z0, z1, rim=0.4), 0.5, bbox=bb(COL_X[0] - 1, HX + KN_R + 1, 9.5, HY + KN_FLAT + 1, z0 - 1, z1 + 1))
    # петли не заходят в борт коробки
    F.sub(box((COL_X[1] + 0.05, WALL_Y - 6, KN_BOT - 2), (HX + KN_R + 2, WALL_Y, KN_TOP + 2), 0.0), 0.0,
          bbox=bb(COL_X[1] - 1, HX + KN_R + 2, WALL_Y - 7, WALL_Y + 0.5, KN_BOT - 2, KN_TOP + 2))
    F.sub(cyl("Z", (HX, HY), BORE, KN_BOT - 2, KN_TOP + 2), 0.15, bbox=bb(HX - 4, HX + 4, HY - 4, HY + 4, KN_BOT - 2, KN_TOP + 2))
    # задняя грань рамки: поле утоплено на 0,6 внутри бортика 2,2 мм (Q02: светлая рамка вокруг тёмного поля)
    F.sub(box((COL_X[0] - 1.0, COL_Y[0] + 2.2, COL_Z[0] + 2.2), (COL_X[0] + 0.6, COL_Y[1] - 2.2, COL_Z[1] - 2.2), 1.5), 0.4,
          bbox=bb(COL_X[0] - 1, COL_X[0] + 1.5, COL_Y[0], COL_Y[1], COL_Z[0], COL_Z[1]))
    # обварка трубы: невысокий поясок у рамки
    F.add(cyl("X", (0.0, TUBE_Z), TUBE_R + 0.9, TUBE_X[1] + 0.05, COL_X[0] + 0.7, rim=0.35, rim1=0.0), 0.5,
          bbox=bb(TUBE_X[1] - 1, COL_X[0] + 1, -TUBE_R - 3, TUBE_R + 3, TUBE_Z - TUBE_R - 3, TUBE_Z + TUBE_R + 3))
    F.sub(cyl("X", (0.0, TUBE_Z), TUBE_R + 0.06, TUBE_X[1] - 2, TUBE_X[1] + 0.06), 0.0,
          bbox=bb(TUBE_X[1] - 1, TUBE_X[1] + 0.5, -TUBE_R - 1, TUBE_R + 1, TUBE_Z - TUBE_R - 1, TUBE_Z + TUBE_R + 1))
    # нижняя планка под трубой: снизу — неглубокий желоб с двумя заклёпками к трубе (U_x-0.31, P14) и упор
    bx0, bx1, bhw = BAR_SLOT
    F.add(prism2(rect2(BAR_X0, COL_X[0] + 0.4, -BAR_HW, BAR_HW, 1.5), "XY", BAR_Z[0], BAR_Z[1], rim=0.5), 0.8,
          bbox=bb(BAR_X0 - 1, COL_X[0] + 1, -BAR_HW - 1, BAR_HW + 1, BAR_Z[0] - 1, BAR_Z[1] + 1))
    F.sub(box((bx0, -bhw, BAR_Z[0] - 2), (bx1, bhw, BAR_Z[0] + 0.6), 2.0), 0.3,
          bbox=bb(bx0 - 1, bx1 + 1, -bhw - 1, bhw + 1, BAR_Z[0] - 1, BAR_Z[0] + 1))
    for x in (-52.0,):
        rs = (4.2 ** 2 + 0.9 ** 2) / (2 * 0.9)

        def head(X, Y, Z, x=x, rs=rs):
            z0 = BAR_Z[0] + 0.6
            d = np.sqrt((X - x) ** 2 + Y ** 2 + (Z - (z0 - 0.9 + rs)) ** 2) - rs
            return np.maximum(d, Z - (z0 + 0.1))
        F.add(head, 0.25, bbox=bb(x - 5, x + 5, -5, 5, BAR_Z[0] - 1, BAR_Z[0] + 1))
    tx0, tx1, tz = BAR_TAB
    # упор — круглая шайба на заклёпке (сбоку — прямоугольник X −18…−8, снизу — круг)
    F.add(cyl("Z", ((tx0 + tx1) / 2, 0.0), (tx1 - tx0) / 2, tz, BAR_Z[0] + 0.7, rim=0.4, rim1=0.0), 0.4,
          bbox=bb(tx0 - 1, tx1 + 1, -7, 7, tz - 1, BAR_Z[0] + 1))
    F.sub(cyl("Z", ((tx0 + tx1) / 2, 0.0), 1.6, tz - 1, tz + 0.5), 0.3, bbox=bb(tx0, tx1, -3, 3, tz - 1, tz + 1))
    # заклёпки планки к рамке
    for y in (-10.5, 10.5):
        rs = (1.5 ** 2 + 0.7 ** 2) / (2 * 0.7)

        def riv(X, Y, Z, y=y, rs=rs):
            cz = BAR_Z[0] - 0.7 + rs
            d = np.sqrt((X + 6.5) ** 2 + (Y - y) ** 2 + (Z - cz) ** 2) - rs
            return np.maximum(d, Z - (BAR_Z[0] + 0.2))
        F.add(riv, 0.15, bbox=bb(-9, -4, y - 2.5, y + 2.5, BAR_Z[0] - 1.5, BAR_Z[0] + 0.5))
    return F


def stock_tube(h):
    F = Field("Stock_Tube", (TUBE_X[0] - 1, -TUBE_R - 1, TUBE_Z - TUBE_R - 1), (TUBE_X[1] + 1, TUBE_R + 1, TUBE_Z + TUBE_R + 1), h)
    F.add(cyl("X", (0.0, TUBE_Z), TUBE_R, TUBE_X[0], TUBE_X[1], rim=0.8, rim1=0.3))
    F.sub(cyl("X", (0.0, TUBE_Z), TUBE_R - 1.6, TUBE_X[0] - 2, TUBE_X[0] + 30), 0.4,
          bbox=bb(TUBE_X[0] - 1, TUBE_X[0] + 31, -TUBE_R, TUBE_R, TUBE_Z - TUBE_R, TUBE_Z + TUBE_R))
    top = TUBE_Z + TUBE_R
    # метки положений сверху: цифры читаются сзади (верх цифры — к дулу); у «1» — лунка
    for txt, xc in (("3", -55.2), ("2", -36.1), ("1", -16.7)):
        f2, w = text2(txt, font_path(True), 3.6, track=0.0)
        engrave(F, f2, "YX", (w / 2, xc - 1.8), -1, top, 1, depth=0.28, wall=0.2,
                bbox=bb(xc - 3.5, xc + 3.5, -w / 2 - 1.5, w / 2 + 1.5, top - 1.5, top + 0.5))
    F.sub(sphere((-20.6, 0.0, top + 1.2), 1.95), 0.15, bbox=bb(-23, -18, -3, 3, top - 2, top + 1))
    return F


# ---------------- приклад ----------------

_P = {}


def polys():
    if not _P:
        _P["frame"] = _poly(FRAME, FRAME_R, 12)
        _P["up"] = _poly(WIN_UP, WIN_UP_R, 10)
        _P["low"] = _poly(WIN_LOW, WIN_LOW_R, 10)
        _P["tl"] = _poly(WIN_TL, WIN_TL_R, 10)
        _P["hous"] = _poly([(-HOUS_HW, HOUS_BOT), (HOUS_HW, HOUS_BOT), (HOUS_HW, S_TOP), (-HOUS_HW, S_TOP)], [3.0, 3.0, 9.0, 9.0], 14)
        _P["pad"] = Poly(_oval_pts(PAD_HW))
        _P["lever"] = _poly(LEVER, LEVER_R, 10)
    return _P


def _oval_pts(hw, n=48):
    """Контур затыльника в плоскости (Y, Z): полуэллипсы сверху и снизу во всю ширину hw, боковины прямые."""
    zt, bt, zb, bb_ = PAD_OVAL
    pts = []
    for k in range(n + 1):                      # верх: от +hw к −hw
        a = math.pi * k / n
        pts.append((hw * math.cos(a), zt + bt * math.sin(a)))
    for k in range(n + 1):                      # низ: от −hw к +hw
        a = math.pi + math.pi * k / n
        pts.append((hw * math.cos(a), zb + bb_ * math.sin(a)))
    return pts


def _hex2(c, s):
    """Шестигранник «под ключ» s в плоскости (U, V)."""
    pts = [(c[0] + s / math.sqrt(3) * math.cos(math.radians(30 + 60 * k)), c[1] + s / math.sqrt(3) * math.sin(math.radians(30 + 60 * k)))
           for k in range(6)]
    return Poly(pts)


def stock_body(h):
    P = polys()
    F = Field("Stock_Body", (S_X0 - 1.5, -HOUS_HW - 2, S_BOT - 1.5), (S_X1 + 1.5, HOUS_HW + 2, S_TOP + 1.5), h)
    # 1. корпус трубы (круглый верх) и скелет — длиннее торцов, торцы срезаются ниже со скруглением
    F.add(prism(P["hous"], "YZ", S_X0 - 1.0, S_X1 + 1.0))
    F.add(prism(P["frame"], "XZ", -FRAME_HW, FRAME_HW, rim=1.4), 1.8,
          bbox=bb(S_X0 - 1.5, S_X1 + 1.5, -HOUS_HW - 1, HOUS_HW + 1, S_BOT - 1, HOUS_BOT + 4))
    # 2. окна насквозь
    F.sub(prism(P["up"], "XZ", -FRAME_HW - 3, FRAME_HW + 3), 1.2, bbox=bb(-197, -100, -HOUS_HW - 1, HOUS_HW + 1, -105, -53))
    # прорезь вдоль раскоса: сзади над нижней перекладиной — насквозь (Q04: видна светлая стенка), вдоль раскоса —
    # глубокая канавка с обоих боков, раскос между ними — сплошной брус
    lo_ = P["low"]
    F.sub(lambda X, Y, Z: np.maximum(lo_.sd(X, Z), X - (-176.0)), 0.9, bbox=bb(-209, -170, -HOUS_HW - 1, HOUS_HW + 1, -130, -110))
    F.sub(lambda X, Y, Z: np.maximum(lo_.sd(X, Z), (FRAME_HW - LOW_GROOVE) - np.abs(Y)), 0.7,
          bbox=bb(-209, -95, -HOUS_HW - 1, HOUS_HW + 1, -130, -69))
    F.sub(prism(P["tl"], "XZ", -FRAME_HW - 3, FRAME_HW + 3), 0.9, bbox=bb(-210, -182, -HOUS_HW - 1, HOUS_HW + 1, -72, -62))
    # 3. скелет: поле боковин внутри бортика 3 мм утоплено на 0,5 мм с мягким переходом
    fr, up, lo, tl = P["frame"], P["up"], P["low"], P["tl"]

    def pocket(X, Y, Z):
        inside = np.maximum(np.maximum(np.maximum(fr.sd(X, Z), -up.sd(X, Z)), -lo.sd(X, Z)), -tl.sd(X, Z)) + 3.0
        inside = np.maximum(inside, X - (-100.0))           # «лапа» спереди сплошная
        inside = np.maximum(inside, Z - (-66.0))            # только нижняя часть (раскос, стойка, низ)
        return np.maximum(inside, (FRAME_HW - 0.5) - np.abs(Y))
    F.sub(pocket, 1.2, bbox=bb(S_X0 - 1, -60, -HOUS_HW - 1, HOUS_HW + 1, S_BOT - 1, -64))
    # у затыльника корпус повторяет его овал (на 0,5 меньше); к X −186 ограничение плавно отпускает
    oval = Poly(_oval_pts(PAD_HW - 0.5))
    F.apply(lambda X, Y, Z: oval.sd(Y, Z) - 1.2 * np.maximum(X + 201.0, 0.0), "inter", 1.0,
            bbox=bb(S_X0 - 1.5, -186, -HOUS_HW - 2, HOUS_HW + 2, S_BOT - 1.5, S_TOP + 1.5))
    # 4. торцы
    F.apply(slab("X", S_X0, S_X1), "inter", 0.9)
    # 5. канал трубы с фаской на входе
    F.sub(cyl("X", (0.0, TUBE_Z), TUBE_R + 0.25, -206.0, S_X1 + 3), 0.7,
          bbox=bb(-207, S_X1 + 1, -TUBE_R - 2, TUBE_R + 2, TUBE_Z - TUBE_R - 2, TUBE_Z + TUBE_R + 2))
    # 6. гнёзда щёк рычага: боковины под ними утоплены (щека выступает на 0,5)
    lev = P["lever"]
    for sg in (-1, 1):
        y0, y1 = sorted((sg * (LEV_IN - 0.25), sg * (HOUS_HW + 2)))
        # гнездо — по положениям рычага от свободного до нажатого (хвост вверх на LEVER_DEG)
        seat = prism(lev, "XZ", y0, y1, off=0.25)
        for deg in (0.0, LEVER_DEG / 2, LEVER_DEG):
            F.sub(rot(seat, "Y", (LEVER_AX[0], 0.0, LEVER_AX[1]), deg), 0.3, bbox=bb(-176, -82, y0 - 1, y1 + 1, -76, -38))
    # 8. гнездо QD сбоку: ступенчатое отверстие насквозь
    qx, qz, qr = QD
    F.sub(cyl("Y", (qx, qz), qr - 1.3, -HOUS_HW - 3, HOUS_HW + 3), 0.4, bbox=bb(qx - 8, qx + 8, -HOUS_HW - 1, HOUS_HW + 1, qz - 8, qz + 8))
    for s in (-1, 1):
        y0, y1 = sorted((s * (FRAME_HW - 3.0), s * (HOUS_HW + 3)))
        F.sub(cyl("Y", (qx, qz), qr, y0, y1), 0.8, bbox=bb(qx - 9, qx + 9, y0 - 1, y1 + 1, qz - 9, qz + 9))
    # 9. глухие отверстия корпуса (торцы осей в глубине) и малые отверстия у лапы
    for x, z, r in HOLES + [(-91.5, -67.4, 1.5)]:
        for s in (-1, 1):
            yf = HOUS_HW if z > HOUS_BOT else FRAME_HW
            y0, y1 = sorted((s * (yf - 2.2), s * (yf + 2)))
            F.sub(cyl("Y", (x, z), r, y0, y1), 0.35, bbox=bb(x - r - 2, x + r + 2, y0 - 1, y1 + 1, z - r - 2, z + r + 2))
    # 10. отверстие под ось рычага и гнёзда гаек
    F.sub(cyl("Y", LEVER_AX, 1.68, -HOUS_HW - 3, HOUS_HW + 3), 0.0, bbox=bb(-94, -86, -HOUS_HW - 2, HOUS_HW + 2, -57, -48))
    for s in (-1, 1):
        y0, y1 = sorted((s * (FRAME_HW - 1.6), s * (FRAME_HW + 2)))
        F.sub(cyl("Y", NUT, 3.4, y0, y1), 0.35, bbox=bb(NUT[0] - 5, NUT[0] + 5, y0 - 1, y1 + 1, NUT[1] - 5, NUT[1] + 5))
    # прорезь фиксатора под осью рычага (в ней виден шток)
    px_, pz0, pz1, phw = PLUNGER
    for sg in (-1, 1):
        y0, y1 = sorted((sg * (FRAME_HW - 2.5), sg * (HOUS_HW + 2)))
        F.sub(box((px_ - phw, y0, pz1), (px_ + phw, y1, pz0), phw - 0.05), 0.3, bbox=bb(px_ - 3, px_ + 3, y0 - 1, y1 + 1, pz1 - 2, pz0 + 2))
    # 11. гнездо стойки QD снизу
    F.sub(cyl("Z", (STUD[0], 0.0), STUD_R + 0.15, STUD[1] - 3, -73.5), 0.5,
          bbox=bb(STUD[0] - 9, STUD[0] + 9, -9, 9, STUD[1] - 3, -72))
    return F


def butt_pad(h):
    P = polys()
    x0, x1 = PAD_X
    F = Field("Butt_Pad", (x0 - 1, -PAD_HW - 1, PAD_OVAL[2] - PAD_OVAL[3] - 1.5), (x1 + 1, PAD_HW + 1, S_TOP + 1.5), h)
    F.add(prism(P["pad"], "YZ", x0, x1, rim=2.0, rim1=0.6))
    pad = P["pad"]
    # рёбра затыльника — «пила» с шагом 8,7 (Q04 крупно: 15 светлых уступов, B_z0.22: тёмные линии через 8,7):
    # сверху у каждого зуба горизонтальный уступ, грань ниже плавно уходит вглубь; посередине зуба — тонкая риска
    for k in range(16):
        zt = -8.2 - 8.7 * k
        if zt - 8.7 < S_BOT + 2:
            break
        wedge = Poly(fillet_poly([(x0 - 2.0, zt), (x0 + 2.2, zt), (x0 + 1.9, zt - 0.9), (x0 + 0.1, zt - 8.1), (x0 - 2.0, zt - 8.1)],
                                 [0.0, 0.5, 0.8, 1.5, 0.0], seg=8))
        F.sub(prism(wedge, "XZ", -PAD_HW - 2, PAD_HW + 2), 0.45, bbox=bb(x0 - 1, x0 + 3, -PAD_HW - 1, PAD_HW + 1, zt - 9.5, zt + 1.5))
        zm = zt - 4.6
        F.sub(cyl("Y", (x0 + 0.95, zm), 0.45, -PAD_HW - 2, PAD_HW + 2), 0.15, bbox=bb(x0 - 1, x0 + 2, -PAD_HW - 1, PAD_HW + 1, zm - 1.5, zm + 1.5))
    # окна-прорези на боках (R_x-0.43: X −231…−227,5, высота 7,6, шаг 13)
    for k in range(8):
        z = -24.0 - 13.0 * k
        for s in (-1, 1):
            y0, y1 = sorted((s * (PAD_HW - 6.0), s * (PAD_HW + 2)))
            F.sub(box((-228.4, y0, z - 3.8), (-224.6, y1, z + 3.8), 0.5), 0.35,
                  bbox=bb(-230, -223, y0 - 1, y1 + 1, z - 5, z + 5))
    # линия разъёма у переднего края (двойная линия на R_x-0.43, X −219,3)

    def seam(X, Y, Z):
        return np.maximum(np.abs(X + 216.8) - 0.3, -(pad.sd(Y, Z) + 0.5))
    F.sub(seam, 0.12, bbox=bb(-218.5, -215, -PAD_HW - 1, PAD_HW + 1, -140.5, S_TOP + 1))
    return F


def stock_latch(h):
    """Рычаг регулировки длины: щёки по бокам скелета (ось — винт спереди) и рифлёный хвост снизу между ними."""
    P = polys()
    lev = P["lever"]
    F = Field("Stock_Latch", (-173.5, -LEV_OUT - 1.8, -75.5), (-83.0, LEV_OUT + 1.8, -45.0), h)
    for sg in (-1, 1):
        y0, y1 = sorted((sg * LEV_IN, sg * LEV_OUT))
        F.add(prism(lev, "XZ", y0, y1, rim=0.35), 0.0, bbox=bb(-173, -83, y0 - 1, y1 + 1, -75, -45))
        # заклёпка на щеке
        rx, rz = LEVER_RIVET
        rs = (2.4 ** 2 + 0.7 ** 2) / (2 * 0.7)
        cy = sg * (LEV_OUT + 0.7 - rs)

        def riv(X, Y, Z, cy=cy, sg=sg):
            d = np.sqrt((X - rx) ** 2 + (Y - cy) ** 2 + (Z - rz) ** 2) - rs
            return np.maximum(d, sg * (sg * (LEV_OUT - 0.1) - Y))
        F.add(riv, 0.2, bbox=bb(rx - 3.5, rx + 3.5, sg * LEV_OUT - 2, sg * LEV_OUT + 2, rz - 3.5, rz + 3.5))
    # хвост: поперечина между щёк ниже боковин (в окне) с рифлением снизу и по бокам
    tail = Poly(fillet_poly([(-171.5, -64.6), (-145.0, -64.6), (-142.0, -71.6), (-160.0, -73.2), (-171.5, -72.2)], [1.0, 1.0, 4.0, 3.0, 2.5]))
    F.add(prism(tail, "XZ", -LEV_IN - 0.2, LEV_IN + 0.2, rim=0.6), 0.5, bbox=bb(-173, -140, -LEV_OUT, LEV_OUT, -75, -63))
    # язык хвоста вперёд снизу (U_x-0.43: «ключ» до X −128 шириной ±9,5)
    tongue = Poly(fillet_poly([(-150.0, -64.6), (-128.0, -64.6), (-128.0, -68.0), (-142.0, -71.6), (-150.0, -72.4)], [0.0, 3.0, 3.0, 4.0, 0.0]))
    F.add(prism(tongue, "XZ", -9.5, 9.5, rim=0.8), 0.8, bbox=bb(-151, -126, -11, 11, -74, -63))
    # рифление — по краям хвоста, на щеках и снизу у кромок
    for x in LEVER_RIBS:
        for sg in (-1, 1):
            y0, y1 = sorted((sg * (LEV_IN - 2.8), sg * (LEV_OUT + 1.0)))
            F.add(box_e((x - 0.75, y0, -73.9), (x + 0.75, y1, -64.8), rx=0.7, ry=0.7, rz=0.7), 0.5,
                  bbox=bb(x - 2.5, x + 2.5, y0 - 1, y1 + 1, -75.5, -63.5))
    F.apply(lambda X, Y, Z: lev.sd(X, Z) - 0.9, "inter", 0.4, bbox=bb(-173, -146, -LEV_OUT - 2, LEV_OUT + 2, -76, -63))
    # между щеками выше хвоста — пусто (там боковины скелета)
    F.sub(box((-180, -LEV_IN, -64.4), (-80, LEV_IN, -40), 0.0), 0.3, bbox=bb(-174, -82, -LEV_IN - 0.5, LEV_IN + 0.5, -65, -44))
    F.sub(cyl("Y", LEVER_AX, 1.75, -LEV_OUT - 2, LEV_OUT + 2), 0.2, bbox=bb(-94, -86, -LEV_OUT - 2, LEV_OUT + 2, -57, -49))
    return F


def sling_stud(h):
    """Стойка-антабка QD снизу передней части приклада: втулка с гнездом под быстросъёмную антабку."""
    x, zb = STUD
    F = Field("Sling_Stud", (x - STUD_R - 1, -STUD_R - 1, zb - 1), (x + STUD_R + 1, STUD_R + 1, -73.0), h)
    F.add(cyl("Z", (x, 0.0), STUD_R, zb, -74.0, rim=0.9, rim1=0.3))
    F.sub(cyl("Z", (x, 0.0), 4.7, zb - 2, zb + 7.0), 0.5)
    F.sub(torus("Z", (x, 0.0, zb + 4.2), 4.75, 0.55), 0.15)
    # насечка по пояску (лыски под ключ)
    for s in (-1, 1):
        y0, y1 = sorted((s * (STUD_R - 0.8), s * (STUD_R + 2)))
        F.sub(box((x - 9, y0, zb + 1.5), (x + 9, y1, zb + 5.5), 0.0), 0.4,
              bbox=bb(x - 9, x + 9, -STUD_R - 2, STUD_R + 2, zb, zb + 7))
    return F


def stock_screws(h):
    """Метиз приклада: ось рычага (винт с шестигранным гнездом и гайкой с другой стороны), гайки в гнёздах."""
    F = Field("Stock_Screws", (-186.0, -LEV_OUT - 2.2, -64.0), (-85.0, LEV_OUT + 2.2, -48.0), h)
    lx, lz = LEVER_AX
    F.add(cyl("Y", LEVER_AX, 1.6, -LEV_OUT, LEV_OUT), 0.0, bbox=bb(lx - 3, lx + 3, -LEV_OUT - 1, LEV_OUT + 1, lz - 3, lz + 3))
    for sg in (-1, 1):
        # головка: цилиндр с фаской и шестигранным гнездом (справа), слева — та же форма гайки-втулки
        y0, y1 = sorted((sg * (LEV_OUT + 0.05), sg * (LEV_OUT + 1.3)))
        F.add(cyl("Y", LEVER_AX, 2.7, y0, y1, rim=0.4), 0.0, bbox=bb(lx - 4, lx + 4, y0 - 1, y1 + 1, lz - 4, lz + 4))
        hx = _hex2(LEVER_AX, 2.0)
        ys0, ys1 = sorted((sg * (LEV_OUT + 0.3), sg * (LEV_OUT + 2.5)))
        F.sub(prism(hx, "XZ", ys0, ys1), 0.12, bbox=bb(lx - 2.5, lx + 2.5, ys0 - 0.5, ys1 + 0.5, lz - 2.5, lz + 2.5))
        # гайка в гнезде
        nx, nz = NUT
        hn = _hex2((nx, nz), 4.6)
        n0, n1 = sorted((sg * (FRAME_HW - 1.55), sg * (FRAME_HW - 0.45)))
        F.add(prism(hn, "XZ", n0, n1, rim=0.25), 0.0, bbox=bb(nx - 4, nx + 4, n0 - 1, n1 + 1, nz - 4, nz + 4))
        F.sub(cyl("Y", (nx, nz), 1.25, n0 - 1, n1 + 1), 0.2, bbox=bb(nx - 2, nx + 2, n0 - 1.5, n1 + 1.5, nz - 2, nz + 2))
    return F


def parts():
    fold = (f"поворот вокруг вертикальной оси шарнира (Z через pivot): складывание влево вдоль левого борта, "
            f"0…−180° (минус — по часовой при взгляде сверху)")
    return [
        dict(name="Hinge_Base", build=hinge_base, h=0.07, coll="Шарнир приклада", mat="Steel_blued", adapt=0.05),
        dict(name="Hinge_Pin", build=hinge_pin, h=0.07, coll="Шарнир приклада", mat="Steel_bare"),
        dict(name="Hinge_Latch", build=hinge_latch, h=0.07, coll="Шарнир приклада", mat="Steel_blued",
             pivot=[HX, HY, LATCH_Z[1]], motion=f"сдвиг вниз вдоль оси шарнира (−Z) 0…{LATCH_DROP} мм — отпускает рамку приклада"),
        dict(name="Hinge_Spring", build=hinge_spring, h=0.07, coll="Шарнир приклада", mat="Spring_steel",
             note="сжимается при ходе защёлки вниз"),
        dict(name="Stock_Knuckle", build=stock_knuckle, h=0.08, coll="Шарнир приклада", mat="Steel_blued",
             pivot=[HX, HY, TUBE_Z], motion=fold, adapt=0.06),
        dict(name="Stock_Tube", build=stock_tube, h=0.11, coll="Приклад", mat="Steel_blued", parent="Stock_Knuckle", adapt=0.06),
        dict(name="Stock_Body", build=stock_body, h=0.17, coll="Приклад", mat="Polymer", parent="Stock_Knuckle",
             pivot=[S_X1, 0.0, TUBE_Z], adapt=0.05,
             motion=f"сдвиг назад вдоль трубы (−X) 0…{STOCK_TRAVEL:.0f} мм, три положения через 20 мм (оценка)"),
        dict(name="Butt_Pad", build=butt_pad, h=0.12, coll="Приклад", mat="Rubber", parent="Stock_Body", adapt=0.05),
        dict(name="Stock_Latch", build=stock_latch, h=0.09, coll="Приклад", mat="Polymer", parent="Stock_Body",
             pivot=[LEVER_AX[0], 0.0, LEVER_AX[1]], motion=f"поворот вокруг Y через pivot: нажатие — хвост вверх, 0…+{LEVER_DEG:.0f}°"),
        dict(name="Stock_Screws", build=stock_screws, h=0.06, coll="Приклад", mat="Steel_phosphate", parent="Stock_Body"),
        dict(name="Sling_Stud", build=sling_stud, h=0.07, coll="Приклад", mat="Steel_phosphate", parent="Stock_Body"),
    ]
