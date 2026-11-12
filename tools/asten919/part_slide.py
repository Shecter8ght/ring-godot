# АСТЕН-919: затвор и его мелкие детали (крышка затвора, выбрасыватель, крышка выреза под коллиматор с винтами,
# мушка, целик). Формы — по снимкам владельца (ref_11, ref_16, ref_22, ref_23), размеры — dims.py.
import math

import numpy as np

from dims import *
from sdf import *

HW, TOP, BOT = SLIDE_HW, SLIDE_TOP, SLIDE_BOT
CH_IN = SLIDE_HW - SKIRT_T            # полуширина канала между бортами


def bb(x0, x1, y0, y1, z0, z1):
    return ((min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))


def section():
    """Поперечное сечение затвора (Y, Z): борта, фаски верхних кромок."""
    return Poly(fillet_poly([(-HW, BOT), (HW, BOT), (HW, TOP - SLIDE_CH), (HW - SLIDE_CH, TOP), (-HW + SLIDE_CH, TOP),
                             (-HW, TOP - SLIDE_CH)], [0.35, 0.35, 0.8, 0.8, 0.8, 0.8]))


def cover_poly():
    """Контур задней крышки затвора (Y, Z): арочный верх, как на снимке владельца от 2026-11-12."""
    return Poly(fillet_poly([(-8.8, BOT - 0.01), (8.8, BOT - 0.01), (8.8, 6.0), (-8.8, 6.0)], [0.0, 0.0, 4.2, 4.2], seg=14))


def dovetail_poly(off=0.0):
    c = RSIGHT_X
    return Poly(fillet_poly([(c - 4.5 - off, TOP - 2.0 - off), (c + 4.5 + off, TOP - 2.0 - off), (c + 3.6 + off, TOP + 0.6),
                             (c - 3.6 - off, TOP + 0.6)], [0.35, 0.35, 0, 0]))


def slide(h):
    F = Field("Slide", (SLIDE_X0 - 1, -HW - 1, GUIDE_Z - NOSE_R - 1), (SLIDE_X1 + 1.2, HW + 1, TOP + 1), h)
    sec = section()
    F.add(prism(sec, "YZ", SLIDE_X0, SLIDE_X1, rim=0.6, rim1=1.3))
    # «нос» под направляющую возвратной пружины
    nose = union(cyl("X", (0, GUIDE_Z), NOSE_R, NOSE_X0, SLIDE_X1, rim=0.5, rim1=1.2),
                 box_e((NOSE_X0, -NOSE_R, GUIDE_Z), (SLIDE_X1, NOSE_R, BOT + 2), rx=0.0, ry=0.0, rz=1.2))
    F.add(nose, 0.9, bbox=bb(NOSE_X0 - 1, SLIDE_X1 + 1, -HW, HW, GUIDE_Z - NOSE_R - 1, BOT + 4))
    # галтель стыка вспучивает общий передний торец — подрезаем его обратно в плоскость
    F.apply(half("X", SLIDE_X1, 1), "inter", 0.0, bbox=bb(SLIDE_X1 - 1, SLIDE_X1 + 1.2, -HW, HW, GUIDE_Z - NOSE_R - 1, TOP))
    # канал ствола между бортами (открыт вниз), крыша со скруглёнными углами
    F.sub(box_e((0.0, -CH_IN, BOT - 3), (NOSE_X0, CH_IN, ROOF_Z), rx=1.6), 0.3, bbox=bb(-1, NOSE_X0 + 1, -HW, HW, BOT - 1, ROOF_Z + 1))
    F.sub(box_e((NOSE_X0 - 2, -CH_IN, -5.6), (107.0, CH_IN, ROOF_Z), rx=1.6, ry=1.0), 0.0, bbox=bb(98, 108, -HW, HW, -7, ROOF_Z + 1))
    # выборка в крыше над ходом казённика (при отпирании он опускается и уходит под крышу)
    F.sub(box_e((PORT_X1 - 2.0, -9.0, ROOF_Z - 2), (78.0, 9.0, 9.25), rx=1.0, ry=1.2), 0.3, bbox=bb(PORT_X1 - 1, 79, -10, 10, ROOF_Z - 1, 10))
    # отверстие под ствол и гнездо направляющей
    F.sub(cyl("X", (0, 0), 7.55, 99, 116), 0.45, bbox=bb(98, 115, -9, 9, -9, 9))
    F.sub(cyl("X", (0, GUIDE_Z), 5.7, NOSE_X0 - 2, 109.6, rim1=0.6), 0.3, bbox=bb(98, 111, -7, 7, GUIDE_Z - 7, GUIDE_Z + 7))
    F.sub(box((NOSE_X0 - 2, -4.6, GUIDE_Z), (109.6, 4.6, -2.0), 0.5), 0.3, bbox=bb(98, 111, -6, 6, GUIDE_Z - 1, 0))
    F.sub(cyl("X", (0, GUIDE_Z), 4.6, 108, 116), 0.3, bbox=bb(107, 115, -6, 6, GUIDE_Z - 6, GUIDE_Z + 6))
    # окно выброса: справа и сверху
    port = union(box_e((0.0, -HW - 2, ROOF_Z - 1.5), (PORT_X1, PORT_Y, TOP + 2), rz=1.6),
                 box_e((0.0, -HW - 2, PORT_Z), (PORT_X1, -CH_IN + 0.5, TOP + 2), ry=1.8))
    F.sub(port, 0.4, bbox=bb(-1, PORT_X1 + 1, -HW - 1, PORT_Y + 1, PORT_Z - 1, TOP + 1))
    # под зеркалом: каналы по бокам от досылателя (под задние направляющие рамки и отражатель)
    side = box_e((SLIDE_X0 - 2, 4.75, BOT - 2), (0.6, CH_IN, -4.2), rx=0.9)
    F.sub(both(side), 0.25, bbox=bb(SLIDE_X0 - 1, 1.5, -HW, HW, BOT - 1, -3))
    # пазы под направляющие рамки в бортах
    groove = box((SLIDE_X0 - 2, CH_IN - 0.3, -8.35), (NOSE_X0 + 0.5, CH_IN + 1.35, -6.95), 0.15)
    F.sub(both(groove), 0.15, bbox=bb(SLIDE_X0 - 1, NOSE_X0 + 1, -HW, HW, -9, -6))
    # канал ударника, отверстие бойка в зеркале, паз под зуб ударника снизу
    F.sub(cyl("X", (0, 0), 3.0, SLIDE_X0 + 1.6, -2.4), 0.0, bbox=bb(SLIDE_X0, -2, -4, 4, -4, 4))
    F.sub(box_e((-4, -0.95, -1.9), (1, 0.95, 1.9), rx=0.9), 0.15, bbox=bb(-4, 1, -2, 2, -3, 3))
    F.sub(box_e((-60, -1.7, BOT - 2), (-27, 1.7, 0.0), rz=1.6), 0.25, bbox=bb(-61, -26, -3, 3, BOT - 1, 1))
    # паз выбрасывателя справа (выходит в окно)
    F.sub(box((-21.3, -HW - 2, -1.75), (2.6, -CH_IN + 1.0, 1.75), 0.0), 0.12, bbox=bb(-22, 3, -HW - 1, -7, -3, 3))
    # гнездо задней крышки
    F.sub(prism(cover_poly(), "YZ", SLIDE_X0 - 2, SLIDE_X0 + 1.6, off=0.08), 0.28, bbox=bb(SLIDE_X0 - 1, SLIDE_X0 + 3, -10, 10, BOT - 1, 7))
    # паз целика («ласточкин хвост» поперёк затвора)
    F.sub(prism(dovetail_poly(0.05), "XZ", -HW - 2, HW + 2), 0.15, bbox=bb(RSIGHT_X - 6, RSIGHT_X + 6, -HW - 1, HW + 1, TOP - 3, TOP + 1))
    # вырез под коллиматор и резьбовые отверстия винтов крышки
    F.sub(box_e((MOS_X0, -HW - 2, MOS_Z), (MOS_X1, HW + 2, TOP + 2), ry=0.5), 0.2, bbox=bb(MOS_X0 - 1, MOS_X1 + 1, -HW - 1, HW + 1, MOS_Z - 1, TOP + 1))
    F.sub(both(cyl("Z", (MOS_SCREW_X, MOS_SCREW_Y), 1.25, 3.0, TOP)), 0.15, bbox=bb(MOS_SCREW_X - 2, MOS_SCREW_X + 2, -8, 8, 2.5, MOS_Z + 1))
    # гнездо мушки (овальное, сквозное в крыше)
    F.sub(box_e((FSIGHT_X - 2.2, -1.25, ROOF_Z - 1), (FSIGHT_X + 2.2, 1.25, TOP + 2), rz=1.24), 0.1, bbox=bb(FSIGHT_X - 3, FSIGHT_X + 3, -2, 2, ROOF_Z - 1, TOP + 1))
    # задние насечки: широкие мелкие пазы, сверху не доходят до фаски
    for k in range(SERR_N):
        x1 = SERR_X0 - k * (SERR_W + SERR_GAP)
        g = box_e((x1 - SERR_W, HW - SERR_DEPTH, BOT - 2), (x1, HW + 2, 8.0), ry=0.35)
        F.sub(both(g), 0.15, bbox=bb(x1 - SERR_W - 0.6, x1 + 0.6, -HW - 1, HW + 1, BOT - 1, 9))
    # вырез под зуб затворной задержки в левом борту
    a, b = STOP_NOTCH_X
    notch = Poly(fillet_poly([(a, BOT - 2), (a, STOP_NOTCH_TOP), (a + 5.0, STOP_NOTCH_TOP), (b + 6, BOT + 0.05), (b + 6, BOT - 2)], [0, 0.5, 2.0, 0, 0]))
    F.sub(prism(notch, "XZ", CH_IN - 1, HW + 2), 0.25, bbox=bb(a - 1, b + 7, CH_IN - 1, HW + 1, BOT - 1, STOP_NOTCH_TOP + 1))
    # маркировка — гравировкой (вымышленная марка, см. asset-state.md): слева знак, название и калибр, справа номер
    engrave(F, sign2(8.4, 0.55), "XZ", (100.3, 0.4), -1, HW, 1, wall=0.2, bbox=bb(94, 107, HW - 1, HW + 1, -5, 6))
    name, wn = text2(MARK_NAME, font_path(), 4.2, track=0.25)
    engrave(F, name, "XZ", (93.0, -1.7), -1, HW, 1, wall=0.2, bbox=bb(93.5 - wn - 2, 94, HW - 1, HW + 1, -4, 5))
    cal, wc = text2(MARK_CAL, font_path(), 2.6, track=0.15)
    engrave(F, cal, "XZ", (47.0, -0.9), -1, HW, 1, wall=0.18, bbox=bb(46 - wc - 1, 48, HW - 1, HW + 1, -3, 4))
    ser, ws = text2(MARK_SERIAL, font_path(True), 2.0, track=0.15)
    engrave(F, ser, "XZ", (5.0, -6.9), 1, -HW, -1, depth=0.16, wall=0.16, bbox=bb(4, 6 + ws + 1, -HW - 1, -HW + 1, -8.5, -3.5))
    return F


COVER_IN = 0.25          # крышка утоплена относительно заднего торца затвора


def cover_plate(h):
    """Задняя крышка затвора (снимок владельца от 2026-11-12): гладкая арка сверху, пояс из пяти горизонтальных
    рисок, внизу окно с торцом втулки ударника (слева) и сквозным вырезом (справа)."""
    x0 = SLIDE_X0 + COVER_IN
    F = Field("Slide_Cover_Plate", (SLIDE_X0 - 0.4, -9.5, BOT - 0.6), (SLIDE_X0 + 2.2, 9.5, 6.8), h)
    F.add(prism(cover_poly(), "YZ", x0, SLIDE_X0 + 1.55, rim=0.3, rim1=0.1))
    F.apply(half("Z", BOT + 0.02, -1), "inter", 0.2)
    # пояс рисок
    for k in range(5):
        zc = -1.7 + k * 0.95
        F.sub(box((x0 - 1, -7.7, zc - 0.27), (x0 + 0.38, 7.7, zc + 0.27), 0.12), 0.1, bbox=bb(x0 - 0.5, x0 + 1, -8.5, 8.5, zc - 0.8, zc + 0.8))
    # нижнее окно (открыто вниз)
    F.sub(box((x0 - 1, -7.0, BOT - 2), (x0 + 0.85, 7.0, -2.9), 0.45), 0.25, bbox=bb(x0 - 0.5, x0 + 1.4, -8, 8, BOT - 0.6, -2.2))
    # торец втулки ударника в окне (левее середины) и сквозной вырез справа
    F.add(box((x0 + 0.3, 0.9, BOT + 0.9), (x0 + 1.2, 5.3, -3.6), 0.3), 0.15, bbox=bb(x0, x0 + 1.4, 0, 6.2, BOT, -2.9))
    F.sub(box((x0 - 1, -6.4, BOT - 2), (SLIDE_X0 + 3, -4.9, -3.7), 0.3), 0.2, bbox=bb(x0 - 0.5, SLIDE_X0 + 2.2, -7.2, -4.2, BOT - 0.6, -3))
    return F


def extractor(h):
    """Выбрасыватель: планка в пазу правого борта, спереди зацеп за закраину гильзы."""
    F = Field("Extractor", (-22, -HW - 0.6, -2.4), (3.4, -4.4, 2.4), h)
    bar = Poly(fillet_poly([(-21.2, -1.67), (2.5, -1.67), (2.5, 1.67), (-21.2, 1.67)], [1.2, 0.3, 0.3, 1.2]))
    F.add(prism(bar, "XZ", -HW + 0.03, -CH_IN + 0.9, rim=0.3))
    # зацеп
    F.add(box((0.5, -CH_IN + 0.6, -1.6), (2.5, -5.3, 1.6), 0.3), 0.3)
    # указатель патрона в патроннике: передняя часть планки отделена тонкой риской
    F.sub(box((-8.6, -HW - 1, -3), (-8.1, -HW + 0.3, 3), 0.1), 0.1)
    return F


def mos_plate(h):
    F = Field("MOS_Cover_Plate", (MOS_X0 - 0.5, -HW - 0.6, MOS_Z - 0.5), (MOS_X1 + 0.5, HW + 0.6, TOP + 0.6), h)
    body = inter(prism(section(), "YZ", MOS_X0 + 0.07, MOS_X1 - 0.07, rim=0.3), half("Z", MOS_Z + 0.04, -1), r=0.25)
    F.add(body)
    for s in (-1, 1):
        F.sub(cyl("Z", (MOS_SCREW_X, s * MOS_SCREW_Y), 2.95, TOP - 1.9, TOP + 2), 0.25,
              bbox=bb(MOS_SCREW_X - 4, MOS_SCREW_X + 4, s * MOS_SCREW_Y - 4, s * MOS_SCREW_Y + 4, TOP - 3, TOP + 1))
        F.sub(cyl("Z", (MOS_SCREW_X, s * MOS_SCREW_Y), 1.65, MOS_Z - 1, TOP), 0.0,
              bbox=bb(MOS_SCREW_X - 3, MOS_SCREW_X + 3, s * MOS_SCREW_Y - 3, s * MOS_SCREW_Y + 3, MOS_Z - 1, TOP))
    return F


def torx(c, r0, amp, z0, z1):
    """Шестилучевое гнездо (звёздочка) вдоль Z."""
    def f(X, Y, Z):
        dx = X - c[0]; dy = Y - c[1]
        rr = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        d = rr - (r0 + amp * np.cos(6 * th))
        return np.maximum(d * 0.8, np.maximum(z0 - Z, Z - z1))
    return f


def mos_screw(side):
    def build(h):
        cy = side * MOS_SCREW_Y
        F = Field("MOS_Screw", (MOS_SCREW_X - 3.4, cy - 3.4, 3.2), (MOS_SCREW_X + 3.4, cy + 3.4, TOP + 0.4), h)
        F.add(cyl("Z", (MOS_SCREW_X, cy), 2.8, TOP - 1.85, TOP - 0.2, rim=0.15, rim1=0.45))
        F.add(cyl("Z", (MOS_SCREW_X, cy), 1.5, 3.6, TOP - 1.5, rim=0.2), 0.2)
        F.sub(torx((MOS_SCREW_X, cy), 1.02, 0.2, TOP - 1.25, TOP + 1), 0.12)
        return F
    return build


def front_sight(h):
    c = FSIGHT_X
    F = Field("Front_Sight", (c - 3.6, -2.6, ROOF_Z - 0.4), (c + 3.6, 2.6, TOP + 5.0), h)
    # клин: задняя (к стрелку) грань почти отвесная, передняя — пологая
    side = Poly(fillet_poly([(c - 2.9, TOP - 0.05), (c + 2.9, TOP - 0.05), (c + 0.2, TOP + 4.3), (c - 2.4, TOP + 4.3)], [0, 0, 0.5, 0.35]))
    F.add(prism(side, "XZ", -1.95, 1.95, rim=0.3))
    # бока сужаются кверху
    F.apply(plane((0, 1.95, TOP), (0, 1, 0.14)), "inter", 0.3)
    F.apply(plane((0, -1.95, TOP), (0, -1, 0.14)), "inter", 0.3)
    # хвостовик в гнезде затвора
    F.add(box_e((c - 2.1, -1.15, ROOF_Z), (c + 2.1, 1.15, TOP + 0.5), rz=1.14), 0.0)
    return F


def rear_sight(h):
    c = RSIGHT_X
    F = Field("Rear_Sight", (c - 5.2, -11.8, TOP - 2.4), (c + 5.2, 11.8, TOP + 4.9), h)
    side = Poly(fillet_poly([(c - 4.3, TOP + 0.02), (c + 4.3, TOP + 0.02), (c + 2.2, TOP + 4.3), (c - 3.6, TOP + 4.3)], [0.2, 0.2, 0.6, 0.4]))
    body = prism(side, "XZ", -11.2, 11.2, rim=0.5)
    F.add(body)
    # бока скошены кверху
    F.apply(plane((0, 11.2, TOP), (0, 1, 0.22)), "inter", 0.5)
    F.apply(plane((0, -11.2, TOP), (0, -1, 0.22)), "inter", 0.5)
    # основание в «ласточкином хвосте»
    F.add(prism(dovetail_poly(0.0), "XZ", -10.6, 10.6, rim=0.2), 0.0)
    F.apply(half("Z", TOP + 4.3, 1), "inter", 0.0)
    # прорезь
    F.sub(box_e((c - 8, -1.85, TOP + 1.55), (c + 8, 1.85, TOP + 8), rx=0.3), 0.2, bbox=bb(c - 5, c + 5, -3, 3, TOP + 1, TOP + 5))
    # задняя грань у прорези чуть утоплена (матовая площадка под белую обводку)
    return F


def parts():
    P = [
        dict(name="Slide", build=slide, h=0.1, coll="Slide", mat="Steel_nitride", weight=20, adapt=0.06),
        dict(name="Slide_Cover_Plate", build=cover_plate, h=0.06, coll="Slide", mat="Polymer", parent="Slide"),
        dict(name="Extractor", build=extractor, h=0.05, coll="Slide", mat="Steel_black", parent="Slide"),
        dict(name="MOS_Cover_Plate", build=mos_plate, h=0.08, coll="Slide", mat="Steel_nitride", parent="Slide", weight=3),
        dict(name="MOS_Screw_L", build=mos_screw(1), h=0.04, coll="Slide", mat="Steel_black", parent="MOS_Cover_Plate"),
        dict(name="MOS_Screw_R", build=mos_screw(-1), h=0.04, coll="Slide", mat="Steel_black", parent="MOS_Cover_Plate"),
        dict(name="Front_Sight", build=front_sight, h=0.05, coll="Slide", mat="Polymer", parent="Slide"),
        dict(name="Rear_Sight", build=rear_sight, h=0.06, coll="Slide", mat="Polymer", parent="Slide"),
    ]
    return P
