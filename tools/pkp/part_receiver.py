# ПКП: ствольная коробка (штамповка из листа с вкладышем и затыльником), её накладки, заклёпки и навесные детали:
# накладка правого борта с прорезью рукоятки перезаряжания, рукоятка перезаряжания, щиток окна выброса (слева),
# боковая планка под прицел и антабка-скоба (слева), кронштейн коробки с лентой (снизу).
# Правый борт — по рендеру владельца 13 (числа сняты со старой сетки, перевод — dims.side_r), левый — по рендеру 14
# (он снят немного сверху: высоты левого борта выставлены по общим с правым деталям — заклёпкам и выштамповке).
import math

import numpy as np

from dims import *
from sdf import *

HW = RECV_HW
X0, X1 = RECV_X0, RECV_X1
BOT, TOP = RECV_BOT, RECV_TOP
T = SHEET


def R(x, z):
    return side_r(x, z)


# заклёпки бортов (X, Z): правый — по снимку 13, левый — по снимку 14
RIVETS_R = [R(-357, -6.5), R(-340, -6.5), R(-340, -38.5), R(-224.5, -6.5), R(-194, -6.5), R(-14, -6.5), R(-14, -37), R(-59, -38)]
RIVETS_L = [(-13.7, -7.0), (-13.7, -37.4), (-85.0, -7.0), (-104.0, -7.0), (-338.4, -38.9)]
PILL = (R(-67, -18), R(-25, -7))                 # выштамповка впереди на обоих бортах: углы (X, Z)
# накладка правого борта: полоса с «лепестками» вокруг заклёпок, спереди — отдельная площадка
PL_X0, PL_X1 = R(-333, 0)[0], R(-160, 0)[0]
PL_Z0, PL_Z1 = R(0, -34)[1], R(0, -14.5)[1]
LOBES_X = [R(x, 0)[0] for x in (-318.5, -269.0, -209.0)]
LOBE_R = 13.0
LOBE_ZT, LOBE_ZB = R(0, -19.5)[1], R(0, -29.0)[1]
DIMPLE_ZT, DIMPLE_ZB = R(0, -11.5)[1], R(0, -38.5)[1]
PAD = (R(-158, -41), R(-141, -7))
FRAME = (R(-325, -29), R(-166, -18.5))          # приподнятая рамка прорези
SLOT = (R(-324, -26), R(-168, -21))             # сама прорезь
# окно выброса гильз в левом борту и его щиток
PORT = ((-222.0, -41.5), (-130.0, -14.5))
HINGE_EARS_X = (COVER_HINGE[0] - 4.6, COVER_HINGE[0] + 6.0)   # стойки оси — перед передней стенкой крышки
TRUNNION_CYL_X0 = -55.5              # цилиндр вкладыша над бортами начинается перед крышкой


def rivet(x, z, side):
    """Головка заклёпки на борту: side = −1 — правый борт, +1 — левый."""
    y0 = side * (HW - 0.3)
    c = (x, y0 + side * (RIVET_H - RIVET_R * 1.15), z)

    def f(X, Y, Z):
        dome = np.sqrt((X - x) ** 2 + (Y - c[1]) ** 2 + (Z - z) ** 2) - RIVET_R * 1.15
        return np.maximum(dome, side * (y0 - Y))
    return f


def receiver(h):
    F = Field("Receiver", (X0 - 0.5, -HW - 4.5, BOT - 1.0), (X1 + 0.5, HW + 4.5, 34.0), h)
    # 1. штамповка: брус со скруглёнными нижними углами
    F.add(box_e((X0, -HW, BOT), (X1, HW, TOP + 6.0), rx=RECV_R + T))
    # 2. выштамповки на обоих бортах (внутрь на 1 мм) — до превращения в лист: рельеф повторяется с изнанки
    (px0, pz0), (px1, pz1) = PILL
    pill = rect2(px0, px1, pz0, pz1, (pz1 - pz0) / 2 - 0.05)

    def stamp(X, Y, Z):
        d2 = pill(X, Z)
        return -1.0 * smoothstep(-d2 / 1.6) * smoothstep((np.abs(Y) - (HW - 6.0)) / 2.0)
    F.displace(stamp, bbox=bb(px0 - 3, px1 + 3, -HW - 1, HW + 1, pz0 - 3, pz1 + 3), fine=False)
    # маркировка на левом борту (вымышленная): калибр и номер — штампом, до превращения тела в лист
    cal, wc = text2(MARK_CAL, font_path(True), 3.6, track=0.3)
    engrave(F, cal, "XZ", (-74.0, -27.5), -1, HW, 1, depth=0.3, wall=0.22, bbox=bb(-76 - wc, -72, HW - 1.5, HW + 1, -29, -22.5))
    ser, ws = text2(MARK_SERIAL, font_path(True), 3.2, track=0.3)
    engrave(F, ser, "XZ", (-74.0, -34.5), -1, HW, 1, depth=0.3, wall=0.22, bbox=bb(-76 - ws, -72, HW - 1.5, HW + 1, -36, -30))
    # 3. лист
    F.shell(T)
    # 4. сверху коробка открыта (её закрывают лоток и крышка); кромки бортов — на высоте разъёма
    F.sub(box((X0 + 22.0, -HW + T, TOP - 3.0), (TRUNNION_X0, HW - T, TOP + 9.0)), 0.0,
          bbox=bb(X0 + 21, TRUNNION_X0 + 1, -HW, HW, TOP - 4, TOP + 9))
    F.apply(half("Z", TOP, 1), "inter", 0.35)
    # 5. окно выброса слева и прорезь рукоятки перезаряжания справа
    (qx0, qz0), (qx1, qz1) = PORT
    F.sub(box_e((qx0, HW - 4, qz0), (qx1, HW + 4, qz1), ry=3.0), 0.3, bbox=bb(qx0 - 1, qx1 + 1, HW - 3, HW + 3, qz0 - 1, qz1 + 1))
    (sx0, sz0), (sx1, sz1) = SLOT
    F.sub(box_e((sx0, -HW - 6, sz0), (sx1, -HW + 4, sz1), ry=1.0), 0.0, bbox=bb(sx0 - 1, sx1 + 1, -HW - 5, -HW + 3, sz0 - 1, sz1 + 1))
    # 6. затыльник (гнездо приклада) и вкладыш с гнездом ствола; над бортами вкладыш — цилиндр
    F.add(box((X0, -HW + T - 0.1, BOT + T - 0.1), (X0 + 24.0, HW - T + 0.1, TOP), 0.0), 0.0, bbox=bb(X0, X0 + 25, -HW, HW, BOT, TOP + 1))
    # вкладыш: под крышкой — не выше кромок бортов, перед крышкой — выше, с цилиндром гнезда ствола
    tr = union(box((TRUNNION_X0, -HW + T - 0.1, BOT + T - 0.1), (X1, HW - T + 0.1, TOP - 0.6), 0.0),
               box((TRUNNION_CYL_X0, -HW + T - 0.1, BOT + T - 0.1), (X1, HW - T + 0.1, 2.0), 0.0),
               cyl("X", (0, 0), TRUNNION_R, TRUNNION_CYL_X0, X1, rim=0.8), r=1.5)
    F.add(tr, 0.0, bbox=bb(TRUNNION_X0 - 1, X1 + 0.5, -HW, HW, BOT, TRUNNION_R + 1))
    # стойки оси крышки и лотка на вкладыше
    ear2 = union2(rect2(HINGE_EARS_X[0], HINGE_EARS_X[1], 4.0, COVER_HINGE[1], 0.5), circle2(COVER_HINGE, 5.4), r=0.0)
    for s in (-1, 1):
        y0, y1 = sorted((s * 9.0, s * 13.5))
        F.add(prism2(ear2, "XZ", y0, y1, rim=0.6), 1.0, bbox=bb(HINGE_EARS_X[0] - 2, HINGE_EARS_X[1] + 3, y0 - 2, y1 + 2, 3, COVER_HINGE[1] + 8))
    F.sub(cyl("Y", COVER_HINGE, 2.55, -16, 16), 0.2, bbox=bb(COVER_HINGE[0] - 4, COVER_HINGE[0] + 4, -15, 15, COVER_HINGE[1] - 4, COVER_HINGE[1] + 4))
    F.sub(cyl("X", (0, 0), 11.6, TRUNNION_X0 - 3, X1 + 2), 0.5, bbox=bb(TRUNNION_X0 - 2, X1 + 1, -13, 13, -13, 13))
    # канал под шток затворной рамы (ось газовой трубки)
    F.sub(cyl("X", (0, GAS_Z), 9.6, TRUNNION_X0 - 3, X1 + 2), 0.5, bbox=bb(TRUNNION_X0 - 2, X1 + 1, -11, 11, GAS_Z - 11, GAS_Z + 11))
    F.apply(half("X", X1, 1), "inter", 0.0, bbox=bb(X1 - 1.5, X1 + 0.5, -HW - 1, HW + 1, BOT - 1, 16))
    F.apply(half("X", X0, -1), "inter", 0.0, bbox=bb(X0 - 0.5, X0 + 1.5, -HW - 1, HW + 1, BOT - 1, 8))
    # 7. накладка правого борта с лепестками и рамкой прорези
    strip_ = rect2(PL_X0, PL_X1, PL_Z0, PL_Z1, 1.2)
    lobes = [circle2((x, LOBE_ZT), LOBE_R) for x in LOBES_X] + [circle2((x, LOBE_ZB), LOBE_R) for x in LOBES_X]
    (ax0, az0), (ax1, az1) = PAD
    plate2 = union2(strip_, *lobes, rect2(ax0, ax1, az0, az1, 4.0), r=2.2)
    yo = -HW - RPLATE_T
    # наружная кромка накладки скруглена (rim), к борту она прилегает без галтели
    F.add(prism2(plate2, "XZ", yo, -HW + 0.3, rim=0.45, rim1=0.0), 0.0, bbox=bb(PL_X0 - 2, ax1 + 2, yo - 0.5, -HW + 0.5, az0 - 2, az1 + 2))
    (fx0, fz0), (fx1, fz1) = FRAME
    frame2 = minus2(rect2(fx0, fx1, fz0, fz1, 1.0), rect2(SLOT[0][0], SLOT[1][0], SLOT[0][1], SLOT[1][1], 1.0), 0.3)
    F.add(prism2(frame2, "XZ", yo - 1.3, yo + 0.2, rim=0.0, rim1=0.35), 0.25, bbox=bb(fx0 - 1, fx1 + 1, yo - 2, yo + 0.6, fz0 - 1, fz1 + 1))
    F.sub(box_e((SLOT[0][0], -HW - 6, SLOT[0][1]), (SLOT[1][0], -HW + 4, SLOT[1][1]), ry=1.0), 0.0,
          bbox=bb(SLOT[0][0] - 1, SLOT[1][0] + 1, -HW - 5, -HW + 3, SLOT[0][1] - 1, SLOT[1][1] + 1))
    # ямки под заклёпки на лепестках и площадке
    dimples = [(x, DIMPLE_ZT) for x in LOBES_X] + [(x, DIMPLE_ZB) for x in LOBES_X] + [R(-149, -12)]
    for x, z in dimples:
        def dimple(X, Y, Z, x=x, z=z):
            rr = np.hypot(X - x, Z - z)
            return -(0.9 * smoothstep((2.6 - rr) / 1.6) - 0.5 * smoothstep((1.0 - rr) / 0.8)) * smoothstep((yo + 1.0 - Y) / 0.6)
        F.displace(dimple, bbox=bb(x - 3.5, x + 3.5, yo - 0.5, yo + 1.2, z - 3.5, z + 3.5), fine=False)
    # 8. заклёпки бортов
    for x, z in RIVETS_R:
        F.add(rivet(x, z, -1), 0.25, bbox=bb(x - 4, x + 4, -HW - 2.5, -HW + 0.5, z - 4, z + 4))
    for x, z in RIVETS_L:
        F.add(rivet(x, z, 1), 0.25, bbox=bb(x - 4, x + 4, HW - 0.5, HW + 2.5, z - 4, z + 4))
    return F


CH_LEN = 44.0              # вылет рукоятки от башмака: на ней помещаются указательный и средний пальцы
                           # (владелец, 2026-11-14; на цветном образце 03 она короче — 25 мм)
CH_BOW = 3.4               # прогиб назад посередине: передняя грань — седло под два пальца (фото владельца 18)
CH_HOOK = 2.4              # конец отогнут вперёд — пальцы не соскальзывают
CH_LEAF_HH = 3.0           # полувысота пластин рукоятки: на боковом рендере 13 рукоятка с торца — 10,5 × 6 мм


def charging_handle(h):
    """Рукоятка перезаряжания (справа): башмак скользит по рамке прорези, язычок сзади входит в прорезь и цепляет
    зацеп рамы; сама рукоятка — две пластины с мелкой насечкой снаружи, торчат горизонтально наружу от общего корня,
    между ними щель, открытая с торца (цветной образец владельца 03, с торца — боковой рендер 13).
    Пластины выгнуты назад дугой с отогнутым вперёд концом: тянут рукоятку двумя пальцами за переднюю грань.
    В переднем положении язычок стоит у переднего конца прорези."""
    cx, cz = R(-158, -23.5)
    cx -= 1.0                                       # середина рукоятки по торцу на рендере 13
    zw = cz - 1.4                                   # пластины чуть ниже середины прорези
    yf = -HW - RPLATE_T - 1.3                       # наружная плоскость рамки прорези
    tx0, tx1 = SLOT[1][0] - 5.6, SLOT[1][0] - 0.4   # язычок в прорези
    y0 = yf - 2.4                                   # корень рукоятки — наружная плоскость башмака
    F = Field("Charging_Handle", (min(tx0 - 2, cx - 10.5), y0 - CH_LEN - 1.5, cz - 6), (cx + 8.5, -18.4, cz + 6), h)
    F.add(box((tx0 - 1.0, yf - 2.6, cz - 4.2), (cx + 5.6, yf - 0.2, cz + 4.2), 0.7))
    F.add(box((tx0, yf - 1.0, SLOT[0][1] + 0.25), (tx1, -HW + 0.6, SLOT[1][1] - 0.25), 0.3), 0.0)
    F.add(box((tx1 - 2.9, -HW - 0.5, SLOT[0][1] + 0.25), (tx1, -19.4, SLOT[1][1] - 0.25), 0.3), 0.0)
    # заклёпка башмака
    F.add(cyl("Y", (tx0 + 3.0, cz), 2.1, yf - 3.3, yf - 2.4, rim=0.4), 0.2, bbox=bb(tx0, tx0 + 6, yf - 3.6, yf - 2, cz - 3, cz + 3))
    # пластины: наружные грани слегка сходятся к концу (4,2 → 3 мм: при вылете под два пальца тоньше — хлипко),
    # внутренние параллельны — щель 2 мм открыта с торца
    rear = Poly(fillet_poly([(cx - 5.2, y0 + 0.6), (cx - 1.0, y0 + 0.6), (cx - 1.0, y0 - CH_LEN), (cx - 4.0, y0 - CH_LEN)], [0, 0, 0.5, 0.9]))
    front = Poly(fillet_poly([(cx + 1.0, y0 + 0.6), (cx + 5.2, y0 + 0.6), (cx + 4.0, y0 - CH_LEN), (cx + 1.0, y0 - CH_LEN)], [0, 0, 0.9, 0.5]))
    root = box((cx - 5.2, y0 - 5.0, -CH_LEAF_HH), (cx + 5.2, y0 + 0.6, CH_LEAF_HH), 0.7)

    def leaves(X, Y, Z):
        zl = Z - zw
        t = np.clip((y0 - Y) / CH_LEN, 0.0, 1.0)
        # изгиб: ось рукоятки посередине уходит назад, у конца — вперёд; считаем в координатах прямой рукоятки
        Xs = X + CH_BOW * np.sin(math.pi * t) ** 2 - CH_HOOK * t ** 4
        hh = CH_LEAF_HH - 0.5 * t                                       # к концу пластины чуть ниже
        lim = np.abs(zl) - hh
        d = np.minimum(i_round(rear.sd(Xs, Y), lim, 0.6), i_round(front.sd(Xs, Y), lim, 0.6))
        d = u_round(d, root(Xs, Y, zl), 0.6)
        # мелкая насечка на наружных гранях пластин: риски поперёк рукоятки, как на образце 03
        if not PLAIN:
            out = smoothstep((np.abs(Xs - cx) - 2.6) / 0.6) * smoothstep(((y0 - 5.5) - Y) / 1.5)
            d = d + 0.18 * out * (0.5 + 0.5 * np.cos(Y * 2 * math.pi / 0.75))
        return d
    F.add(leaves, 0.5, bbox=bb(cx - 10.3, cx + 8.2, y0 - CH_LEN - 1.2, yf - 0.4, zw - 4, zw + 4))
    return F


def port_cover(h):
    """Щиток окна выброса гильз (слева): штампованная крышка на оси вдоль верхней кромки, подпружинена."""
    (qx0, qz0), (qx1, qz1) = PORT
    x0, x1 = qx0 - 4.0, qx1 + 4.0
    zt = qz1 + 3.0                       # ось щитка
    F = Field("Port_Cover", (x0 - 7, HW - 0.5, qz0 - 4), (x1 + 7, HW + 6.0, zt + 3.5), h)
    plate = rect2(x0, x1, qz0 - 2.5, zt - 0.5, 2.0)
    F.add(prism2(plate, "XZ", HW + 0.25, HW + 1.45, rim=0.3))
    # приподнятая середина — жёсткость
    inner = rect2(x0 + 5.0, x1 - 5.0, qz0 + 1.5, zt - 6.0, 1.5)

    def rib(X, Y, Z):
        return 0.9 * smoothstep(-inner(X, Z) / 1.4) * smoothstep((Y - (HW + 0.9)) / 0.5)
    F.displace(rib, fine=False)
    # ось и петли
    F.add(cyl("X", (HW + 2.55, zt), 1.25, x0 - 5.0, x1 + 5.0, rim=0.4), 0.0)
    for xa, xb in ((x0 + 2.0, x0 + 16.0), (x1 - 16.0, x1 - 2.0), ((x0 + x1) / 2 - 6.0, (x0 + x1) / 2 + 6.0)):
        F.add(cyl("X", (HW + 2.55, zt), 2.25, xa, xb, rim=0.4), 0.6, bbox=bb(xa - 1, xb + 1, HW, HW + 5.5, zt - 4, zt + 3))
    return F


def side_rail(h):
    """Боковая планка под прицел (слева, сзади): плита на заклёпках с продольными скосами."""
    x0, x1 = -357.0, -251.0
    z0, z1 = -5.6, 2.2
    F = Field("Side_Rail", (x0 - 1, HW - 0.5, z0 - 6.5), (x1 + 1, HW + 7.5, z1 + 1.5), h)
    prof = Poly(fillet_poly([(HW, z0 - 5.0), (HW + 3.2, z0 - 5.0), (HW + 6.4, z0 - 1.8), (HW + 6.4, z1 - 2.6), (HW + 3.8, z1), (HW, z1)],
                            [0, 0.4, 0.5, 0.5, 0.4, 0]))
    F.add(prism(prof, "YZ", x0, x1, rim=0.5))
    # верх планки у борта подрезан: там проходит юбка крышки ствольной коробки
    F.sub(box((x0 - 2, HW - 1, RECV_TOP - 1.1), (x1 + 2, COVER_HW + 0.35, z1 + 3), 0.0), 0.3)
    # вырез посередине и облегчения
    F.sub(box((-300.5, HW + 1.8, z0 - 7), (-289.5, HW + 9, z1 + 3), 0.4), 0.4, bbox=bb(-302, -288, HW + 1, HW + 8, z0 - 6, z1 + 2))
    for x in (-345.0, -332.0, -318.0, -270.0, -259.0):
        F.sub(cyl("Y", (x, -1.6), 1.7, HW + 2.5, HW + 9), 0.3, bbox=bb(x - 3, x + 3, HW + 2, HW + 8, -4.5, 1.5))
    return F


def sling_bar(h):
    """Антабка-скоба на левом борту: пруток на двух стойках с винтами."""
    xa, xb = -346.5, -253.5
    zc = -25.5
    F = Field("Sling_Bar", (xa - 12, HW - 0.5, zc - 17), (xb + 11, HW + 11, zc + 12), h)
    for xc in (xa, xb):
        foot = Poly(fillet_poly([(xc - 8.5, zc + 9.5), (xc + 8.5, zc + 9.5), (xc + 8.5, zc - 6.0), (xc + 4.5, zc - 15.5), (xc - 4.5, zc - 15.5),
                                 (xc - 8.5, zc - 6.0)], [1.5, 1.5, 3.0, 3.5, 3.5, 3.0]))
        F.add(prism(foot, "XZ", HW + 0.25, HW + 2.4, rim=0.5), 0.0, bbox=bb(xc - 10, xc + 10, HW, HW + 3, zc - 17, zc + 11))
        F.add(cyl("X", (HW + 5.4, zc), 4.6, xc - 6.5, xc + 6.5, rim=0.8), 1.2, bbox=bb(xc - 9, xc + 9, HW, HW + 11, zc - 7, zc + 7))
        # винт внизу стойки
        F.add(cyl("Y", (xc, zc - 11.0), 2.6, HW + 2.0, HW + 3.4, rim=0.4), 0.2, bbox=bb(xc - 4, xc + 4, HW + 1.5, HW + 4, zc - 15, zc - 7))
        F.sub(box((xc - 2.4, HW + 2.9, zc - 11.45), (xc + 2.4, HW + 5, zc - 10.55), 0.1), 0.12, bbox=bb(xc - 3, xc + 3, HW + 2.6, HW + 4, zc - 13, zc - 9))
    F.add(cyl("X", (HW + 5.4, zc), 2.5, xa, xb), 0.6)
    return F


def box_bracket(h):
    """Кронштейн коробки с лентой под ствольной коробкой: планка с загнутыми внутрь направляющими."""
    x0, x1 = -166.0, -32.0
    F = Field("Box_Bracket", (x0 - 1, -16, BOT - 6.5), (x1 + 1, 16, BOT + 0.6), h)
    prof = Poly(fillet_poly([(-14.0, BOT - 0.02), (14.0, BOT - 0.02), (14.0, BOT - 5.4), (9.0, BOT - 5.4), (9.0, BOT - 3.6), (12.2, BOT - 3.6),
                             (12.2, BOT - 1.6), (-12.2, BOT - 1.6), (-12.2, BOT - 3.6), (-9.0, BOT - 3.6), (-9.0, BOT - 5.4), (-14.0, BOT - 5.4)],
                            [0, 0, 1.2, 0.4, 0.3, 0.6, 0.6, 0.6, 0.6, 0.3, 0.4, 1.2]))
    F.add(prism(prof, "YZ", x0, x1, rim=0.6))
    return F


def hinge_pin(h):
    """Ось крышки и лотка: стержень сквозь стойки вкладыша и щёки крышки, справа головка, слева проточка под стопор."""
    yo = COVER_HW
    prof = [(-yo - 2.2, 0.0), (-yo - 2.2, 3.4), (-yo - 1.8, 4.0), (-yo - 0.7, 4.0), (-yo - 0.25, 3.6), (-yo - 0.25, 2.45),
            (yo + 0.5, 2.45), (yo + 0.5, 1.9), (yo + 1.2, 1.9), (yo + 1.2, 2.45), (yo + 2.2, 2.45), (yo + 2.6, 2.0), (yo + 2.6, 0.0)]
    return lathe_mesh(prof, seg=48, axis="Y", c=COVER_HINGE, closed=False)


def parts():
    return [
        dict(name="Cover_Hinge_Pin", build=hinge_pin, coll="Ствольная коробка", mat="Steel_phosphate", sharp=40, parent="Receiver"),
        dict(name="Receiver", build=receiver, h=0.15, coll="Ствольная коробка", mat="Steel_blued", adapt=0.1),
        dict(name="Charging_Handle", build=charging_handle, h=0.1, coll="Ствольная коробка", mat="Steel_phosphate",
             pivot=[R(-158, -23.5)[0], -HW, R(-158, -23.5)[1]], motion="вдоль X назад на dims.CH_TRAVEL"),
        dict(name="Port_Cover", build=port_cover, h=0.1, coll="Ствольная коробка", mat="Steel_blued",
             pivot=[(PORT[0][0] + PORT[1][0]) / 2, HW + 2.55, PORT[1][1] + 3.0]),
        dict(name="Side_Rail", build=side_rail, h=0.12, coll="Ствольная коробка", mat="Steel_blued", parent="Receiver"),
        dict(name="Sling_Bar", build=sling_bar, h=0.12, coll="Ствольная коробка", mat="Steel_blued", parent="Receiver"),
        dict(name="Box_Bracket", build=box_bracket, h=0.12, coll="Ствольная коробка", mat="Steel_blued", parent="Receiver"),
    ]
