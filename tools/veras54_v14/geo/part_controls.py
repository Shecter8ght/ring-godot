# ВЕРАС-54 v14: органы управления — переводчик огня (правый борт), накладка со спусковой скобой и стойкой защёлки,
# спусковой крючок, защёлка магазина с осью.
# Контуры сняты с плиток образца с сеткой в мм (trace/ctrl): переводчик — R_x-0.20_z0.265 (my_r_sel_full, r_sel_a,
# my_r_sel_front), полочка — T_x-0.20 и U_x-0.20 (t_sel_a, my_u_mid); скоба, крючок, стойка, защёлка —
# R_x-0.09_z0.265, R_x-0.20_z0.265, R_x-0.21_z0.17 (r_guard, my_r_grear*), L_x-0.10_z0.20 (l_guard), U_x-0.09
# (my_u_guard); объём — ракурсы Q03, P11, P04.
# У образца переводчик стоит на предохранителе: его контур снят в этом положении (SEL_*) и повёрнут вокруг оси
# SELECTOR_AXIS в положение «АВ» на SEL_AB_DEG — нижний передний угол встаёт над клеймом «АВ» коробки.
import math

import numpy as np

from dims import *
from sdf import *

# ---------------- переводчик ----------------
# Снят в положении «предохранитель», как у образца (плитки R/T/U_x-0.152_…_f0.7, 0,115 мм на пиксель: trace/ctrl/s3_*),
# в модели повёрнут вокруг SELECTOR_AXIS в «АВ» на SEL_AB_DEG.
# Два слоя: рычаг (наружный, штамповка с бортом-ребром вдоль верхней кромки, две заклёпки, ступица с головкой оси)
# и нижняя пластина у коробки — видна полосой под рычагом: охватывает ступицу сзади-снизу, несёт козырёк под палец,
# за козырьком уступ вниз, дальше прямой скос к носу; нос выходит из-под рычага вперёд и наружу.
import os
SAX, SAZ = SELECTOR_AXIS
SEL_AB_DEG = float(os.environ.get("VERAS_SEL_DEG", "9.0"))   # от предохранителя к «АВ»: передний конец вниз
SEL_Y_IN = -(RECV_HW + 1.2)       # внутренняя грань нижней пластины: зазор 0,4 мм до юбки крышки (COVER_HW 17,3)
SEL_Y_MID = SEL_Y_IN - 0.8        # нижняя пластина 0,8 (T_x-0.152: весь пакет до поля рычага −19,5)
SEL_Y_OUT = SEL_Y_MID - 1.0       # поле рычага −19,5
SEL_RIB_H = 0.55                  # борт-ребро над полем: верх −20,05 (T_x-0.152)
SEL_RIB_W = 2.2                   # ширина борта (s4_ref_riv: полоса Z 11,8…13,4 над заклёпками)
SEL_HUB_R = 9.0                   # ушко рычага вокруг оси (s4_ref_hub: верх 0,7 при оси −8,3)
SEL_LOBE_R = 10.6                 # охват ушка нижней пластиной сзади-снизу (s4_ref_hub: дуга Z −18,5)
SEL_COLLAR = (7.3, 1.2)           # буртик-шайба оси: радиус, высота над полем (s4_ref_hub, T_x-0.152)
SEL_HEAD = (4.1, 1.0)             # головка оси: радиус, высота над буртиком; плоский торец r 3,6 с фаской
# нижняя кромка рычага — прямая (s3_r, s3_rf2: (67; −14,6) … (161; 5,7))
SEL_D0, SEL_DK = (67.0, -14.6), 0.2155


def _sel_d(x):
    return SEL_D0[1] + SEL_DK * (x - SEL_D0[0])


# рычаг: верх у ступицы, излом вверх к заклёпкам, верх, скошенный передний торец, прямая нижняя кромка
SEL_LEVER = [(61.0, 0.8), (80.8, 0.8), (91.4, 12.7), (93.0, 13.5), (159.4, 13.7), (162.0, 6.2), (161.0, _sel_d(161.0)),
             (67.0, -14.6), (61.0, -15.5)]
SEL_LEVER_R = [0.0, 2.5, 2.5, 1.5, 1.2, 1.0, 0.8, 0.0, 0.0]
# средняя линия борта: дугой по ступице сверху-сзади, вдоль верхней кромки, до переднего торца
SEL_RIB = [(63.0, 0.8 - SEL_RIB_W / 2), (80.4, 0.8 - SEL_RIB_W / 2), (91.0, 13.5 - SEL_RIB_W / 2),
           (158.6, 13.7 - SEL_RIB_W / 2)]
# нижняя пластина (видна ниже рычага): корень козырька — дуга вверх, уступ, скос к носу
SEL_SHELF_ROOT = [(84.3, -16.9), (86.5, -15.9), (90.0, -14.9), (95.0, -14.3), (100.0, -14.2), (104.0, -14.5), (106.4, -15.3)]
SEL_L2 = (108.0, -9.4, 0.258)     # скос к носу: точка и наклон (s3_r: (108; −9,4), s3_rf2: (158; 3,5))
SEL_PLATE = ([(61.0, -4.0), (161.0, _sel_d(161.0) + 1.0), (161.2, 4.6), (159.0, 3.6), (108.0, -9.4), (107.4, -12.5)]
             + SEL_SHELF_ROOT[::-1] + [(63.5, -17.9)])
SEL_PLATE_R = [0.0, 0.0, 1.2, 1.0, 1.0, 0.8, 0.6, 0, 0, 0, 0, 0, 0.8, 0.0]
SEL_NOSE_X = 137.5                # нос пластины наружу от X 136,5 (T_x-0.152: уступ до Y −21,8)
SEL_NOSE_Y = -21.8
SEL_SHELF_X = (84.0, 106.6)       # козырёк: длина 22,6 (T_x-0.152)
SEL_SHELF_OUT = -26.8             # вынос (T_x-0.152)
SEL_SHELF_T = 1.5
SEL_SHELF_DEG = 20.0              # отгиб вниз от горизонтали (оценка: кромка козырька на s3_r)
SEL_RIVETS = [(94.6, 7.0), (101.7, 7.0)]      # заклёпки-купола в поле ниже борта (s4_ref_riv: Ø 4,3)
SEL_POS = {"safe": -SEL_AB_DEG, "АВ": 0.0, "2": 3.6, "ОД": 7.3}   # углы вокруг Y от «АВ» (плюс — передний конец вниз)

# ---------------- накладка, скоба, стойка защёлки ----------------
PL_TOP = RECV_BOT - 0.1           # верх накладки: 0,1 мм под дном коробки
PL_REAR_X = 0.0                   # задний край — по торцу коробки: дальше назад стоит рамка узла приклада (part_stock)
PL_HW = 12.5                      # полуширина накладки под рукояткой и скобой (оценка: из-под коробки сбоку не видна)
PAD_X = (112.5, 143.6)            # передняя широкая часть накладки (U_x-0.09: скругления у X 113 и 142)
PAD_HW = 16.0
PL_CUT = (96.6, 106.4, -33.3)     # выемка нижней кромки накладки у крючка (r_guard: X 97…107 видно дно коробки)
TB_BOSS = (76.0, 96.2, -37.3, 6.0)          # прилив под пазом крючка: X от, до, низ, полуширина (my_r_grear2)
TB_SLOT = (77.8, 98.0, 3.6)                 # паз крючка: X от, до, полуширина
GUARD_HW = 6.0                    # полуширина ленты скобы (U_x-0.20: кромки Y −6,2 и +5,7)
GUARD_T = 1.5                     # толщина ленты (вид сбоку)
# средняя линия ленты (X, Z): задняя стойка у рукоятки, низ (слегка поднимается вперёд), передняя стойка у защёлки
GUARD_PATH = [(71.4, -34.6), (71.4, -76.05), (126.15, -75.25), (126.15, -36.4)]
GUARD_R = [8.0, 8.5]
STAND_X = (126.6, 143.6)          # стойка защёлки: щёки (r_guard, l_guard)
STAND_BOT = -65.6
STAND_FRONT_R = 9.5               # скругление переднего нижнего угла щёк
CHEEK_Y = (8.6, 10.1)             # щёки по |Y| (U_x-0.09: рамка ±10, внутри ±8,5)
STAND_BEAM = (126.6, -38.3, 10.6) # поперечина под накладкой: X от, низ, полуширина
STAND_FOOT = (128.5, 137.5, -67.4)          # «подошва» под щёками (r_guard: X 129…137, до Z −67,5)
PAD_RIVETS = [(129.5, 13.4), (139.5, 13.4), (129.5, -13.4), (139.5, -13.4)]   # заклёпки снизу накладки (U_x-0.09)

# ---------------- спусковой крючок ----------------
TAX, TAZ = TRIGGER_AXIS
TRIG_HW = 3.2                     # полуширина (оценка: лицевая грань на Q03 / P11)
TRIG_POLY = [(86.5, -29.0), (97.0, -28.0), (95.5, -31.5), (91.2, -34.5), (90.6, -37.0), (90.6, -44.5), (91.4, -48.5),
             (92.3, -51.0), (93.8, -55.0), (95.6, -60.0), (97.4, -64.0), (99.0, -65.9), (99.3, -66.7), (98.5, -67.8),
             (97.4, -67.7), (80.6, -45.6), (79.6, -43.6), (79.9, -37.0), (82.5, -31.5)]
TRIG_R = [2.0, 1.5, 3.0, 2.0, 1.0, 6.0, 10.0, 10.0, 10.0, 8.0, 4.0, 1.2, 1.0, 1.0, 0.8, 1.0, 0.8, 2.0, 3.0]
TRIG_PULL_DEG = 11.0              # ход: задний конец паза накладки пропускает до 11°

# ---------------- защёлка магазина ----------------
MCX, MCZ = MAG_CATCH_AXIS
MC_HW = 7.6                       # полуширина рычага между щёк (зазор 1,0 до щеки)
MC_PADDLE_HW = 6.0                # полуширина лапки ниже стойки
# рычаг (X, Z): верх в стойке, передняя грань, зуб (держит задний выступ магазина), лапка, низ задней части
MC_POLY = [(132.0, -40.5), (142.6, -40.5), (142.6, -49.4), (144.5, -49.9), (144.5, -53.0), (142.6, -54.8),
           (142.6, -63.0), (141.7, -63.4), (141.7, -65.8), (131.8, -64.0), (131.8, -50.0)]
MC_POLY_R = [1.0, 1.0, 0.4, 0.5, 0.6, 0.5, 0.3, 0.3, 0.3, 1.5, 1.0]
MC_PADDLE = [(139.0, -63.0), (141.7, -63.0), (141.7, -80.2), (139.0, -80.9)]   # лапка: нижний конец Z −81 (образец)
MC_PADDLE_R = [0.0, 0.0, 1.2, 1.2]
MC_HOLE_R = 1.75                  # отверстие под ось (ось r 1,6)
MC_PRESS_DEG = -13.0              # отжатие: лапка вперёд, к магазину; зуб (выше оси) уходит назад на 1,6 мм


def _rot_pt(x, z, ox, oz, deg):
    """Точка (x, z) тела, повёрнутого rot(…, "Y", origin, deg): плюс — +X уходит вниз."""
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    bx, bz = x - ox, z - oz
    return ox + bz * sa + bx * ca, oz + bz * ca - bx * sa


def _sel(fn):
    """Тело переводчика, снятое в положении «предохранитель», — в положение «АВ»."""
    return rot(fn, "Y", (SAX, 0.0, SAZ), SEL_AB_DEG)


def _sel_bb(x0, x1, y0, y1, z0, z1):
    """Габарит местной операции переводчика: прямоугольник (X, Z) снятого положения после поворота в «АВ»."""
    pts = [_rot_pt(x, z, SAX, SAZ, SEL_AB_DEG) for x in (x0, x1) for z in (z0, z1)]
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    return bb(min(xs) - 0.5, max(xs) + 0.5, y0, y1, min(zs) - 0.5, max(zs) + 0.5)


def selector(h):
    F = Field("Selector_Lever", (45.0, SEL_SHELF_OUT - 2.5, -30.0), (165.0, -15.8, 17.0), h)
    hb = bb(SAX - 14, SAX + 14, SEL_Y_OUT - 4.0, -16.0, SAZ - 14, SAZ + 14)
    # 1. нижняя пластина с охватом ступицы
    plate = Poly(fillet_poly(SEL_PLATE, SEL_PLATE_R, seg=10))
    lobe = minus2(circle2((SAX, SAZ), SEL_LOBE_R), union2(rect2(SAX + 4.5, SAX + 30, SAZ - 30, SAZ + 30),
                                                           rect2(SAX - 30, SAX + 30, SAZ + 3.5, SAZ + 30)), r=2.5)
    low2 = union2(lambda U, V: plate.sd(U, V), lobe, circle2((SAX, SAZ), SEL_HUB_R), r=2.5)
    F.add(_sel(prism2(low2, "XZ", SEL_Y_MID + 0.05, SEL_Y_IN, rim=0.35)))
    # нос: часть пластины под рычагом впереди отогнута наружу (ступенька на виде сверху)
    nose = minus2(minus2(lambda U, V: plate.sd(U, V), lambda U, V: U - SEL_NOSE_X, r=1.5),
                  lambda U, V: (SEL_D0[1] + SEL_DK * (U - SEL_D0[0]) - 0.1) - V, r=0.0)
    F.add(_sel(prism2(nose, "XZ", SEL_NOSE_Y, SEL_Y_MID + 0.3, rim=0.45, rim1=0.0)), 0.6,
          bbox=_sel_bb(SEL_NOSE_X - 8, 164, SEL_NOSE_Y - 1, SEL_Y_MID + 0.5, -2.0, 8.0))
    # 2. рычаг: толстый лист со скруглёнными кромками
    lever = Poly(fillet_poly(SEL_LEVER, SEL_LEVER_R, seg=10))
    up2 = union2(lambda U, V: lever.sd(U, V), circle2((SAX, SAZ), SEL_HUB_R), r=3.0)
    F.add(_sel(prism2(up2, "XZ", SEL_Y_OUT, SEL_Y_MID + 0.15, rim=0.5, rim1=0.0)))
    # борт-ребро вдоль верхней кромки: коробчатое сечение (плоский верх, скругления), по ступице — дугой
    rib = Path2(fillet_path(SEL_RIB, [2.5, 2.5], seg=8))

    def rib_f(X, Y, Z):
        d2 = rib.dist(X, Z) - SEL_RIB_W / 2
        d2 = np.maximum(d2, up2(X, Z) + 0.15)                   # не выходит за кромку рычага
        return i_round(d2, np.abs(Y - (SEL_Y_OUT - SEL_RIB_H / 2 + 0.4)) - (SEL_RIB_H / 2 + 0.4), 0.45)
    F.add(_sel(rib_f), 0.5, bbox=_sel_bb(48.0, 162.0, SEL_Y_OUT - SEL_RIB_H - 0.6, SEL_Y_OUT + 0.6, -6.0, 15.0))
    # 3. козырёк под палец: от дуги корня вниз-наружу, толстый, концы скруглены; насечка «вафлей» на верхней грани
    rx = np.array([q[0] for q in SEL_SHELF_ROOT]); rz = np.array([q[1] for q in SEL_SHELF_ROOT])
    y0 = (SEL_Y_IN + SEL_Y_MID) / 2
    ca, sa = math.cos(math.radians(SEL_SHELF_DEG)), math.sin(math.radians(SEL_SHELF_DEG))
    L0 = (y0 - SEL_SHELF_OUT - SEL_SHELF_T / 2) / ca
    xm, xh = (SEL_SHELF_X[0] + SEL_SHELF_X[1]) / 2, (SEL_SHELF_X[1] - SEL_SHELF_X[0]) / 2

    def shelf(X, Y, Z):
        zr = np.interp(X, rx, rz)
        u = Y - y0; v = Z - zr
        t = np.clip((-u * ca - v * sa) / L0, 0.0, 1.0) * L0
        d2 = np.sqrt((u + t * ca) ** 2 + (v + t * sa) ** 2) - SEL_SHELF_T / 2
        d1 = np.sqrt(u ** 2 + (v - np.clip(v, 0.0, 1.6)) ** 2) - SEL_SHELF_T / 2
        d = u_round(d1, d2, 1.8)
        return i_round(d, np.abs(X - xm) - xh, 1.2)
    F.add(_sel(shelf), 0.6, bbox=_sel_bb(82.8, 107.8, SEL_SHELF_OUT - 1.5, SEL_Y_IN + 0.3, -22.0, -12.0))
    kp = 1.0

    def waffle(X, Y, Z):
        zr = np.interp(X, rx, rz)
        wc = (Y - y0) * sa / ca                                       # средняя линия козырька над корнем
        top = smoothstep((Z - zr - wc) / 0.3)
        m = top * smoothstep((-Y + SEL_Y_IN - 1.6) / 0.6) * smoothstep((SEL_SHELF_OUT + 0.9 - Y) * -1 / 0.5) \
            * smoothstep((X - SEL_SHELF_X[0] - 1.4) / 0.6) * smoothstep((SEL_SHELF_X[1] - 1.4 - X) / 0.6)
        s1 = np.abs(((X + Y) / kp) % 1.0 - 0.5) * 2.0
        s2 = np.abs(((X - Y) / kp) % 1.0 - 0.5) * 2.0
        return -0.18 * m * (1.0 - np.minimum(s1, s2))
    F.displace(_sel(waffle), bbox=_sel_bb(83.5, 107.0, SEL_SHELF_OUT - 1.2, SEL_Y_IN - 1.0, -21.0, -12.5), fine=True)
    # 4. ось: ушко рычага (r SEL_HUB_R, своя кромка), на нём буртик-шайба и низкая головка оси с плоским торцом
    #    и фаской; изнутри — опора на борт коробки
    cr, ch = SEL_COLLAR
    hr, hh = SEL_HEAD
    y_c = SEL_Y_OUT - ch
    F.add(cyl("Y", (SAX, SAZ), cr, y_c, SEL_Y_OUT + 0.3, rim=0.45, rim1=0.0), 0.4, bbox=hb)
    F.add(cyl("Y", (SAX, SAZ), hr, y_c - hh, y_c + 0.3, rim=0.5, rim1=0.0), 0.3, bbox=hb)
    F.add(cyl("Y", (SAX, SAZ), 5.5, -RECV_HW - 0.15, SEL_Y_IN + 0.3, rim=0.3), 0.3, bbox=hb)
    # 5. заклёпки-купола на поле рычага, под куполом — тонкая шайба
    rr, rh = 2.15, 1.0
    rs = (rr ** 2 + rh ** 2) / (2 * rh)
    for x, z in ([] if PLAIN else SEL_RIVETS):
        F.add(_sel(cyl("Y", (x, z), 2.55, SEL_Y_OUT - 0.18, SEL_Y_OUT + 0.2, rim=0.12, rim1=0.0)), 0.1,
              bbox=_sel_bb(x - 3.5, x + 3.5, SEL_Y_OUT - 0.6, SEL_Y_OUT + 0.4, z - 3.5, z + 3.5))
        y0 = SEL_Y_OUT - 0.18
        cy = y0 - rh + rs

        def riv(X, Y, Z, x=x, z=z, cy=cy, y0=y0):
            d = np.sqrt((X - x) ** 2 + (Y - cy) ** 2 + (Z - z) ** 2) - rs
            return np.maximum(d, Y - (y0 + 0.2))
        F.add(_sel(riv), 0.15, bbox=_sel_bb(x - 3, x + 3, SEL_Y_OUT - 1.6, SEL_Y_OUT + 0.4, z - 3, z + 3))
    return F


def _dome_down(x, y, z0, r=2.2, hgt=1.0):
    """Полукруглая головка заклёпки на нижней грани (Z = z0, головка вниз)."""
    rs = (r * r + hgt * hgt) / (2 * hgt)
    cz = z0 - hgt + rs

    def f(X, Y, Z):
        d = np.sqrt((X - x) ** 2 + (Y - y) ** 2 + (Z - cz) ** 2) - rs
        return np.maximum(d, Z - (z0 + 0.2))
    return f


def trigger_guard(h):
    F = Field("Trigger_Guard", (PL_REAR_X - 1.5, -PAD_HW - 1.5, -79.0), (PAD_X[1] + 1.5, PAD_HW + 1.5, PL_TOP + 1.0), h)
    # 1. накладка: узкая часть под рукояткой и скобой, широкая — у стойки защёлки
    plan = union2(rect2(PL_REAR_X, PAD_X[0] + 1.3, -PL_HW, PL_HW, 3.0), rect2(PAD_X[0], PAD_X[1], -PAD_HW, PAD_HW, 3.0), r=2.0)
    F.add(prism2(plan, "XY", PLATE_BOT, PL_TOP, rim=0.45, rim1=0.2))
    x0, x1, zc = PL_CUT
    F.sub(box((x0, -PAD_HW - 2, PLATE_BOT - 2), (x1, PAD_HW + 2, zc), 0.0), 0.6,
          bbox=bb(x0 - 1.5, x1 + 1.5, -PL_HW - 1, PL_HW + 1, PLATE_BOT - 1, zc + 1))
    # прилив под пазом крючка
    bx0, bx1, bz, bhw = TB_BOSS
    F.add(box_e((bx0, -bhw, bz), (bx1, bhw, PLATE_BOT + 0.5), rx=0.6, ry=0.6, rz=1.2), 0.8,
          bbox=bb(bx0 - 2, bx1 + 2, -bhw - 2, bhw + 2, bz - 1, PLATE_BOT + 1))
    # 2. скоба — гнутая лента; задняя стойка у рукоятки, передняя — у щёк стойки защёлки
    band = Path2(fillet_path(GUARD_PATH, GUARD_R, seg=12))
    F.add(strip(band, "XZ", GUARD_T, -GUARD_HW, GUARD_HW, rim=0.55), 0.9,
          bbox=bb(69.5, 128.5, -GUARD_HW - 1, GUARD_HW + 1, -78.0, PLATE_BOT + 0.5))
    # 3. стойка защёлки: поперечина, щёки со скруглённым передним углом, подошва
    sx0, sx1 = STAND_X
    F.add(box_e((sx0, -STAND_BEAM[2], STAND_BEAM[1]), (sx1, STAND_BEAM[2], PLATE_BOT + 0.4), rx=0.6, ry=0.6, rz=0.6), 0.5,
          bbox=bb(sx0 - 1, sx1 + 1, -STAND_BEAM[2] - 1, STAND_BEAM[2] + 1, STAND_BEAM[1] - 1, PLATE_BOT + 0.6))
    cheek = Poly(fillet_poly([(sx0, -36.0), (sx1, -36.0), (sx1, STAND_BOT), (sx0, STAND_BOT)], [0.0, 0.0, STAND_FRONT_R, 1.0]))
    for s in (-1, 1):
        y0, y1 = sorted((s * CHEEK_Y[0], s * CHEEK_Y[1]))
        F.add(prism(cheek, "XZ", y0, y1, rim=0.45), 0.5, bbox=bb(sx0 - 1, sx1 + 1, y0 - 1, y1 + 1, STAND_BOT - 1, STAND_BEAM[1] + 1))
    fx0, fx1, fz = STAND_FOOT
    F.add(box_e((fx0, -CHEEK_Y[1], fz), (fx1, CHEEK_Y[1], STAND_BOT + 0.2), rx=1.0, ry=1.0, rz=0.8), 0.5,
          bbox=bb(fx0 - 1.5, fx1 + 1.5, -CHEEK_Y[1] - 1, CHEEK_Y[1] + 1, fz - 1, STAND_BOT + 2))
    # отверстия щёк под ось защёлки
    F.sub(cyl("Y", (MCX, MCZ), MC_HOLE_R, -CHEEK_Y[1] - 2, CHEEK_Y[1] + 2), 0.2,
          bbox=bb(MCX - 3, MCX + 3, -CHEEK_Y[1] - 1, CHEEK_Y[1] + 1, MCZ - 3, MCZ + 3))
    # 4. паз крючка сквозь накладку и прилив
    tx0, tx1, thw = TB_SLOT
    F.sub(box((tx0, -thw, bz - 2), (tx1, thw, PL_TOP + 2), 0.6), 0.3,
          bbox=bb(tx0 - 1, tx1 + 1, -thw - 1, thw + 1, bz - 1, PL_TOP + 0.5))
    # 5. заклёпки снизу широкой части
    for x, y in ([] if PLAIN else PAD_RIVETS):
        F.add(_dome_down(x, y, PLATE_BOT), 0.2, bbox=bb(x - 3, x + 3, y - 3, y + 3, PLATE_BOT - 1.5, PLATE_BOT + 0.5))
    # 6. литьевая шероховатость ленты скобы (образец: «пупырчатая» лицевая сторона на P11)

    def stipple(X, Y, Z):
        n = np.sin(X * 5.1 + Y * 3.7) * np.sin(Y * 4.3 + Z * 5.9) * np.sin(Z * 4.7 + X * 3.1)
        return 0.02 * n
    F.displace(stipple, bbox=bb(69.5, 128.5, -GUARD_HW - 1, GUARD_HW + 1, -78.0, -37.5), fine=True)
    # верх — по дну коробки
    F.apply(half("Z", PL_TOP, 1), "inter", 0.0, bbox=bb(PL_REAR_X - 1, PAD_X[1] + 1, -PAD_HW - 1, PAD_HW + 1, PL_TOP - 0.8, PL_TOP + 1))
    return F


def trigger(h):
    F = Field("Trigger", (78.5, -TRIG_HW - 1.0, -69.5), (102.0, TRIG_HW + 1.0, -21.5), h)
    prof = Poly(fillet_poly(TRIG_POLY, TRIG_R, seg=10))
    shape = union2(lambda U, V: prof.sd(U, V), circle2((TAX, TAZ), 4.6), r=2.0)
    F.add(prism2(shape, "XZ", -TRIG_HW, TRIG_HW, rim=0.8))
    # отверстие под ось
    F.sub(cyl("Y", (TAX, TAZ), 1.6, -TRIG_HW - 2, TRIG_HW + 2), 0.2, bbox=bb(TAX - 3, TAX + 3, -TRIG_HW - 1, TRIG_HW + 1, TAZ - 3, TAZ + 3))
    return F


def mag_catch(h):
    F = Field("Mag_Catch", (130.0, -MC_HW - 1.0, -82.5), (146.5, MC_HW + 1.0, -39.0), h)
    body = Poly(fillet_poly(MC_POLY, MC_POLY_R, seg=8))
    b2 = union2(lambda U, V: body.sd(U, V), circle2((MCX, MCZ), 4.2), r=1.5)
    F.add(prism2(b2, "XZ", -MC_HW, MC_HW, rim=0.6))
    paddle = Poly(fillet_poly(MC_PADDLE, MC_PADDLE_R, seg=8))
    F.add(prism(paddle, "XZ", -MC_PADDLE_HW, MC_PADDLE_HW, rim=0.6), 0.8, bbox=bb(137.5, 143.5, -MC_HW - 1, MC_HW + 1, -82, -61))
    F.sub(cyl("Y", (MCX, MCZ), MC_HOLE_R, -MC_HW - 2, MC_HW + 2), 0.2, bbox=bb(MCX - 3, MCX + 3, -MC_HW - 1, MC_HW + 1, MCZ - 3, MCZ + 3))
    return F


def mag_catch_axle(h):
    """Ось защёлки: стержень r 1,6 сквозь щёки и рычаг, расклёпанные головки снаружи щёк."""
    y1 = CHEEK_Y[1] + 0.1
    prof = [(-y1 - 0.45, 0.0), (-y1 - 0.45, 2.0), (-y1 - 0.6, 2.3), (-y1 - 0.55, 2.65), (-y1 - 0.3, 2.85), (-y1, 2.85),
            (-y1, 1.6), (y1, 1.6), (y1, 2.85), (y1 + 0.3, 2.85), (y1 + 0.55, 2.65), (y1 + 0.6, 2.3), (y1 + 0.45, 2.0),
            (y1 + 0.45, 0.0)]
    return lathe_mesh(prof, seg=48, axis="Y", c=(MCX, MCZ), closed=False)


def parts():
    sel_motion = ("поворот вокруг оси Y через pivot (плюс — передний конец вниз), от «АВ»: предохранитель "
                  f"{SEL_POS['safe']:+.1f}°, «2» {SEL_POS['2']:+.1f}°, «ОД» {SEL_POS['ОД']:+.1f}°")
    return [
        dict(name="Selector_Lever", build=selector, h=0.08, coll="Органы управления", mat="Steel_blued",
             pivot=[SAX, SEL_Y_IN, SAZ], motion=sel_motion, adapt=0.06),
        dict(name="Trigger_Guard", build=trigger_guard, h=0.11, coll="Органы управления", mat="Steel_blued", adapt=0.08),
        dict(name="Trigger", build=trigger, h=0.07, coll="Органы управления", mat="Steel_phosphate",
             pivot=[TAX, 0.0, TAZ], motion=f"поворот вокруг Y через pivot: выжим — нижний конец назад, 0…+{TRIG_PULL_DEG:.0f}°"),
        dict(name="Mag_Catch", build=mag_catch, h=0.07, coll="Органы управления", mat="Steel_blued",
             pivot=[MCX, 0.0, MCZ], motion=f"поворот вокруг Y через pivot: отжатие — лапка вперёд, к магазину, 0…{MC_PRESS_DEG:+.0f}°"),
        dict(name="Mag_Catch_Axle", build=mag_catch_axle, h=0.07, coll="Органы управления", mat="Steel_bare"),
    ]
