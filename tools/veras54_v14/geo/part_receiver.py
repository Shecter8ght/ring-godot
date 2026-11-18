# ВЕРАС-54 v14: ствольная коробка — штамповка из листа 1 мм с вкладышами, заклёпками, осями механизма
# (с проволочным фиксатором слева), выштамповками и клеймами; площадка защёлки сложенного приклада справа.
# Места (X, Z) сняты с плиток образца с сеткой в мм: правый борт — trace/r_recv_*.png, левый — trace/l_recv_*.png.
import math

import numpy as np

from dims import *
from sdf import *

HW = RECV_HW
X0, X1 = RECV_X0, RECV_X1
BOT, TOP = RECV_BOT, RECV_TOP
T = SHEET

# заклёпки с полукруглой головкой (X, Z)
DOME_R = [(16.0, -2.0), (201.0, -19.5), (231.0, -2.5), (248.0, -2.5)]
DOME_L = [(201.0, -19.5), (231.5, -2.0), (248.5, -2.0)]
# заклёпки и оси с плоской головкой: (X, Z, радиус)
FLAT_R = [(21.0, -29.0, 2.7), (46.5, -15.5, 2.5), (85.0, -28.0, 2.6), (123.5, -23.5, 2.6), (111.5, -7.5, 2.0),
          (132.5, -9.0, 2.3), (248.5, -20.5, 3.8)]
FLAT_L = [(16.5, -2.0, 2.7), (60.3, -8.5, 2.7), (47.0, -15.8, 2.7), (21.0, -29.0, 2.7), (109.0, -9.0, 2.6),
          (143.0, -9.0, 2.4), (132.5, -9.0, 2.4), (120.6, -9.0, 2.4), (141.1, -15.6, 2.7), (219.0, -3.0, 3.8),
          (248.5, -20.5, 3.7)]
# утопленные кольца — торцы осей в отверстиях борта: (X, Z, радиус)
RING_R = [(111.5, -20.5, 2.4), (140.0, -15.5, 2.7), (171.5, -5.0, 2.2), (184.0, -5.0, 2.2)]
RING_L = [(184.2, -5.0, 2.2), (172.0, -5.0, 2.2), (20.0, -16.5, 3.7)]
# оси УСМ слева с проволочным фиксатором: (X, Z, радиус головки, углы «ушек» фиксатора в градусах)
AXLES_L = [(85.0, -28.0, 3.6, (40, 140)), (138.7, -26.0, 3.6, (40, 140)), (123.6, -23.5, 3.6, (45, 135, 225, 315))]
PILL = ((164.0, -24.0), (187.0, -16.0))        # овальная выштамповка над шахтой (обе стороны): углы (X, Z)
DETENTS = [(150.5, -9.5), (147.5, -20.5)]      # лунки фиксатора переводчика (правый борт)
SLOT_R = (137.5, -25.5)                        # вертикальная прорезь с осью (правый борт)
# площадка кнопки-защёлки сложенного приклада (правый борт сзади)
PAD = ((4.0, -22.0), (25.0, -12.0))
PAD_BTN = (20.0, -17.0, 4.0)


def dome(x, z, side, r=RIVET_R, hgt=RIVET_H):
    """Полукруглая головка заклёпки на борту: side = −1 — правый борт, +1 — левый."""
    y0 = side * (HW - 0.3)
    rs = (r * r + hgt * hgt) / (2 * hgt)           # радиус сферы, от которой головка — сегмент высотой hgt
    cy = y0 + side * (hgt + 0.3 - rs)

    def f(X, Y, Z):
        d = np.sqrt((X - x) ** 2 + (Y - cy) ** 2 + (Z - z) ** 2) - rs
        return np.maximum(d, side * (y0 - Y))
    return f


def receiver(h):
    F = Field("Receiver", (X0 - 0.5, -HW - 3.0, BOT - 0.8), (X1 + 0.5, HW + 3.0, TOP + 0.8), h)
    # 1. штамповка: брус со скруглёнными нижними гибами
    F.add(box_e((X0, -HW, BOT), (X1, HW, TOP + 8.0), rx=RECV_R))
    # 2. выштамповки — до превращения в лист (рельеф повторяется с изнанки): овал над шахтой на обоих бортах
    (px0, pz0), (px1, pz1) = PILL
    pill = rect2(px0, px1, pz0, pz1, (pz1 - pz0) / 2 - 0.05)

    def stamp(X, Y, Z):
        return -0.9 * smoothstep(-pill(X, Z) / 1.4) * smoothstep((np.abs(Y) - (HW - 5.0)) / 2.0)
    F.displace(stamp, bbox=bb(px0 - 3, px1 + 3, -HW - 1, HW + 1, pz0 - 3, pz1 + 3), fine=False)
    # лунки фиксатора переводчика (правый борт): короткие овалы
    for x, z in DETENTS:
        ov = rect2(x - 2.6, x + 2.6, z - 1.0, z + 1.0, 0.95)

        def det(X, Y, Z, ov=ov):
            return -0.6 * smoothstep(-ov(X, Z) / 0.7) * smoothstep((-Y - (HW - 4.0)) / 2.0)
        F.displace(det, bbox=bb(x - 4, x + 4, -HW - 1, -HW + 3, z - 3, z + 3), fine=False)
    # клейма (вымышленные): слева — название и калибр, справа — режимы огня у конца переводчика
    name, wn = text2(MARK_NAME, font_path(True), 3.4, track=0.3)
    engrave(F, name, "XZ", (208.5, -5.2), -1, HW, 1, depth=0.3, wall=0.22, bbox=bb(206.5 - wn, 210.5, HW - 1.5, HW + 1, -6.5, -0.5))
    cal, wc = text2(MARK_CAL, font_path(True), 2.3, track=0.25)
    engrave(F, cal, "XZ", (208.5, -9.4), -1, HW, 1, depth=0.25, wall=0.2, bbox=bb(206.5 - wc, 210.5, HW - 1.5, HW + 1, -10.6, -6.3))
    for txt, x, z in (("АВ", 153.0, -14.2), ("2", 154.2, -20.2), ("ОД", 152.4, -26.4)):
        f2, w = text2(txt, font_path(True), 2.6, track=0.2)
        engrave(F, f2, "XZ", (x, z), 1, -HW, -1, depth=0.25, wall=0.2, bbox=bb(x - 1, x + w + 1, -HW - 1, -HW + 1.5, z - 1, z + 3.6))
    # 3. лист
    F.shell(T)
    # 4. коробка открыта сверху; кромки бортов — на высоте разъёма с крышкой
    F.apply(half("Z", TOP, 1), "inter", 0.3)
    # паз спускового крючка в дне (крючок — part_controls, ход 11° укладывается в паз)
    F.sub(box((77.8, -3.7, BOT - 3), (98.0, 3.7, BOT + 4), 0.0), 0.3, bbox=bb(76.5, 99.5, -5, 5, BOT - 1, BOT + 3))
    # окно шахты магазина в дне
    F.sub(box((MAGWELL_X0, -MAGWELL_HW, BOT - 3), (MAGWELL_X1, MAGWELL_HW, BOT + 4), 0.0), 0.3,
          bbox=bb(MAGWELL_X0 - 1, MAGWELL_X1 + 1, -HW, HW, BOT - 1, BOT + 3))
    # 5. вкладыши: задний (гнездо шарнира приклада) и передний (гнездо ствола) — заподлицо с бортами изнутри
    F.add(box((X0, -HW + T - 0.1, BOT + T - 0.1), (REAR_BLOCK_X1, HW - T + 0.1, TOP - 0.4), 0.0), 0.0,
          bbox=bb(X0, REAR_BLOCK_X1 + 1, -HW, HW, BOT, TOP + 0.5))
    F.add(box((TRUNNION_X0, -HW + T - 0.1, BOT + T - 0.1), (X1, HW - T + 0.1, TOP - 0.4), 0.0), 0.0,
          bbox=bb(TRUNNION_X0 - 1, X1, -HW, HW, BOT, TOP + 0.5))
    F.sub(cyl("X", (0, 0), BARREL_R + 0.3, TRUNNION_X0 - 3, X1 + 2), 0.4, bbox=bb(TRUNNION_X0 - 2, X1 + 1, -12, 12, -12, 12))
    # гнездо боевых упоров: затвор v13 входит во вкладыш до казённого среза ствола (X 240), его упоры — до Y −13,5
    F.sub(cyl("X", (0, 0), 14.0, TRUNNION_X0 - 2, 240.3), 0.4, bbox=bb(TRUNNION_X0 - 3, 241.5, -15, 15, -15, TOP + 0.5))
    # направляющие затворной рамы — отгибы внутрь по верху бортов между вкладышами
    for s in (-1, 1):
        # правая уже: по ней проходит боевой упор затвора v13 (до Y −13,5)
        y0, y1 = sorted((s * (HW - T + 0.1), s * (HW - (2.4 if s < 0 else 3.6))))
        F.add(box((REAR_BLOCK_X1 - 1, y0, TOP - 3.2), (TRUNNION_X0 + 1, y1, TOP - 1.4), 0.3), 0.0,
              bbox=bb(REAR_BLOCK_X1 - 2, TRUNNION_X0 + 2, y0 - 0.5, y1 + 0.5, TOP - 4, TOP))
    F.apply(half("X", X1, 1), "inter", 0.0, bbox=bb(X1 - 1.5, X1 + 0.5, -HW - 1, HW + 1, BOT - 1, TOP + 1))
    F.apply(half("X", X0, -1), "inter", 0.0, bbox=bb(X0 - 0.5, X0 + 1.5, -HW - 1, HW + 1, BOT - 1, TOP + 1))
    # 6. площадка кнопки-защёлки сложенного приклада на правом борту
    (ax0, az0), (ax1, az1) = PAD
    pad2 = rect2(ax0, ax1, az0, az1, 1.2)
    F.add(prism2(pad2, "XZ", -HW - 1.0, -HW + 0.3, rim=0.35, rim1=0.0), 0.0, bbox=bb(ax0 - 1, ax1 + 1, -HW - 1.5, -HW + 0.5, az0 - 1, az1 + 1))
    bx, bz, br = PAD_BTN
    F.sub(cyl("Y", (bx, bz), br + 0.25, -HW - 2, -HW - 0.55), 0.15, bbox=bb(bx - 5, bx + 5, -HW - 1.6, -HW, bz - 5, bz + 5))
    F.add(cyl("Y", (bx, bz), br, -HW - 1.25, -HW - 0.4, rim=0.3), 0.0, bbox=bb(bx - 5, bx + 5, -HW - 1.8, -HW, bz - 5, bz + 5))
    # 7. заклёпки и торцы осей
    for x, z in DOME_R:
        F.add(dome(x, z, -1), 0.2, bbox=bb(x - 3.5, x + 3.5, -HW - 2, -HW + 0.5, z - 3.5, z + 3.5))
    for x, z in DOME_L:
        F.add(dome(x, z, 1), 0.2, bbox=bb(x - 3.5, x + 3.5, HW - 0.5, HW + 2, z - 3.5, z + 3.5))
    for lst, s in ((FLAT_R, -1), (FLAT_L, 1)):
        for x, z, r in lst:
            y0, y1 = sorted((s * (HW - 0.3), s * (HW + 0.45)))
            F.add(cyl("Y", (x, z), r, y0, y1, rim=0.3), 0.12, bbox=bb(x - r - 1, x + r + 1, y0 - 0.5, y1 + 0.5, z - r - 1, z + r + 1))
    for lst, s in ((RING_R, -1), (RING_L, 1)):
        for x, z, r in lst:
            # отверстие в борту с фаской и торец оси чуть ниже поверхности
            y0, y1 = sorted((s * (HW - 2.0), s * (HW + 1.0)))
            F.sub(cyl("Y", (x, z), r, y0, y1), 0.25, bbox=bb(x - r - 1, x + r + 1, y0, y1, z - r - 1, z + r + 1))
            p0, p1 = sorted((s * (HW - 2.0), s * (HW - 0.35)))
            F.add(cyl("Y", (x, z), r - 0.12, p0, p1, rim=0.2), 0.0, bbox=bb(x - r - 1, x + r + 1, p0 - 0.3, p1 + 0.3, z - r - 1, z + r + 1))
    # вертикальная прорезь с осью (правый борт)
    sx, sz = SLOT_R
    F.sub(prism2(rect2(sx - 1.9, sx + 1.9, sz - 3.4, sz + 2.6, 1.85), "XZ", -HW - 1, -HW + 2.0), 0.2,
          bbox=bb(sx - 3, sx + 3, -HW - 1, -HW + 2.2, sz - 4.5, sz + 3.5))
    F.add(cyl("Y", (sx, sz - 1.4), 1.75, -HW + 0.25, -HW + 2.0, rim=0.2), 0.0, bbox=bb(sx - 3, sx + 3, -HW, -HW + 2.3, sz - 4, sz + 1))
    # 8. оси УСМ слева: плоская головка и проволочный фиксатор — «ушки» проволоки вокруг головки
    for x, z, r, angs in AXLES_L:
        F.add(cyl("Y", (x, z), r, HW - 0.3, HW + 0.9, rim=0.35), 0.12, bbox=bb(x - r - 1, x + r + 1, HW - 0.5, HW + 1.4, z - r - 1, z + r + 1))
        for a in angs:
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            # ушко — петля проволоки 0,9 мм: капсула-кольцо, вытянутое от головки
            p0 = (x + ca * (r - 0.6), z + sa * (r - 0.6)); p1 = (x + ca * (r + 2.6), z + sa * (r + 2.6))
            loop = minus2(seg2(p0, p1, 1.35), seg2(p0, p1, 0.5))
            F.add(prism2(loop, "XZ", HW - 0.2, HW + 0.75, rim=0.3), 0.1, bbox=bb(min(p0[0], p1[0]) - 2, max(p0[0], p1[0]) + 2, HW - 0.4, HW + 1.2,
                                                                         min(p0[1], p1[1]) - 2, max(p0[1], p1[1]) + 2))
    return F


def parts():
    return [
        dict(name="Receiver", build=receiver, h=0.11, coll="Ствольная коробка", mat="Steel_blued", adapt=0.06),
    ]
