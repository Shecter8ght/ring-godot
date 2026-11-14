# ПКП: пистолетная рукоятка (пластик) и спусковой узел — коробка спускового механизма со скобой, спусковой крючок,
# флажок предохранителя (слева). Контуры — по правому боковому рендеру владельца 13 (trace/mm2/r_trig, сетка в мм
# модели на глубине 14 мм), флажок — по левому рендеру 14; ширины — оценка.
import math

import numpy as np

from dims import *
from sdf import *

HWG = GRIP_HW                      # полуширина рукоятки
HWC = GRIP_NECK_HW                 # полуширина верхней части рукоятки (у коробки)
HWT = 12.5                         # полуширина коробки спускового механизма (оценка)
TOPZ = RECV_BOT - 0.05             # всё висит под дном ствольной коробки
# рукоятка: контур ручки (X, Z) — передняя грань, носок, низ, пятка, задняя грань
HANDLE = [(-286.5, -74.0), (-312.8, -143.0), (-307.8, -146.6), (-307.6, -150.6), (-310.6, -155.6), (-350.4, -147.3),
          (-353.6, -142.4), (-331.0, -73.0), (-331.8, -58.0), (-287.0, -58.0)]
HANDLE_R = [2.5, 3.0, 2.6, 2.6, 5.0, 6.0, 5.0, 5.0, 0.0, 0.0]
COLLAR = (-336.2, -284.0, -76.5)   # верхняя часть рукоятки: X от и до, низ по Z
PAD = (-336.2, -293.9, -54.0)      # поясок у дна коробки
AXIS0 = (-308.7, -73.5)            # начало оси ручки (середина ширины у верхней части)
AXIS_DEG = 20.9                    # наклон ручки от вертикали
# коробка спускового механизма
TH = (-283.4, -208.5, -63.5)       # X от и до, низ по Z
LOBE = ((-275.4, -62.0), 8.3)      # прилив у оси предохранителя
PINS = [(-275.4, -62.0), (-264.6, -58.8), (-220.8, -54.7)]
TRIG_AXIS = (-264.6, -58.8)        # ось спускового крючка
TRIG_PATH = [(-265.8, -57.0), (-265.6, -66.0), (-263.6, -75.0), (-258.8, -82.2), (-251.2, -86.9)]
GUARD_PATH = [(-275.9, -64.0), (-275.8, -88.5), (-270.0, -95.2), (-257.6, -96.7), (-233.0, -91.6), (-224.2, -85.6),
              (-221.2, -74.0), (-220.8, -61.5)]
GUARD_R = [5.0, 7.0, 30.0, 12.0, 9.0, 4.0]
SPUR = [(-221.9, -73.2), (-213.5, -76.3), (-208.6, -78.0), (-209.3, -79.7), (-216.0, -79.5), (-221.9, -78.8)]
SAFETY_AXIS = (-275.0, -63.0)      # ось флажка предохранителя (X, Z), флажок слева
SAFETY_R = 9.0


def grip(h):
    F = Field("Pistol_Grip", (-356, -HWG - 1, -158), (-282.5, HWG + 1, TOPZ + 0.6), h)
    side = Poly(fillet_poly(HANDLE, HANDLE_R, seg=12))
    F.add(prism(side, "XZ", -HWG, HWG, rim=6.0))
    # верхняя часть у коробки — у́же и с малыми радиусами; стык с ручкой — галтелью
    collar = Poly(fillet_poly([(COLLAR[0], TOPZ + 2.0), (COLLAR[1], TOPZ + 2.0), (COLLAR[1], COLLAR[2] + 1.0), (-288.0, COLLAR[2] - 1.5),
                               (-329.8, COLLAR[2] - 1.5), (-331.6, -62.0)], [0.0, 0.0, 2.0, 2.0, 2.0, 6.0]))
    F.add(prism(collar, "XZ", -HWC, HWC, rim=2.0), 3.0, bbox=bb(COLLAR[0] - 1, COLLAR[1] + 1, -HWG, HWG, COLLAR[2] - 7, TOPZ + 0.5))
    # поясок под дном коробки
    F.add(box_e((PAD[0], -HWC - 0.9, PAD[2]), (PAD[1], HWC + 0.9, TOPZ), rx=0.8, ry=0.8, rz=2.5), 0.5,
          bbox=bb(PAD[0] - 1, PAD[1] + 1, -HWG, HWG, PAD[2] - 2, TOPZ + 0.5))
    F.apply(half("Z", TOPZ, 1), "inter", 0.0, bbox=bb(-340, -280, -HWG - 1, HWG + 1, TOPZ - 1.5, TOPZ + 0.6))
    # насечка-«сетка» на боках ручки: пирамидки в площадке вдоль оси ручки
    a = math.radians(AXIS_DEG)
    ax = (-math.sin(a), -math.cos(a)); bx = (math.cos(a), -math.sin(a))
    panel = rect2(9.0, 63.0, -15.5, 15.5, 4.0)
    p = 1.7

    def checker(X, Y, Z):
        u = (X - AXIS0[0]) * ax[0] + (Z - AXIS0[1]) * ax[1]
        v = (X - AXIS0[0]) * bx[0] + (Z - AXIS0[1]) * bx[1]
        m = smoothstep(-panel(u, v) / 0.8) * smoothstep((np.abs(Y) - (HWG - 3.5)) / 1.5)
        s1 = np.abs(((u + v) / p) % 1.0 - 0.5) * 2.0
        s2 = np.abs(((u - v) / p) % 1.0 - 0.5) * 2.0
        return -0.45 * m * (1.0 - np.minimum(s1, s2))
    F.displace(checker, bbox=bb(-352, -288, -HWG - 1, HWG + 1, -146, -78), fine=True)
    # винт рукоятки снизу
    c = (-331.0, -151.4)
    F.sub(rot(cyl("Z", (c[0], 0.0), 5.2, c[1] - 6.0, c[1] + 3.0), "Y", (c[0], 0.0, c[1]), 11.9), 0.6,
          bbox=bb(c[0] - 8, c[0] + 8, -7, 7, c[1] - 8, c[1] + 5))
    return F


def trigger_housing(h):
    """Коробка спускового механизма со спусковой скобой (скоба приварена — одно тело)."""
    F = Field("Trigger_Housing", (TH[0] - 2.5, -HWT - 1.5, -99.5), (TH[1] + 1.5, HWT + 1.5, TOPZ + 0.6), h)
    body = union2(rect2(TH[0], TH[1], TH[2], TOPZ + 4.0, 1.0), circle2(*LOBE), r=2.0)
    notch = rect2(-210.3, TH[1] + 3.0, TH[2] - 3.0, -57.5, 0.6)
    F.add(prism2(minus2(body, notch, 0.8), "XZ", -HWT, HWT, rim=1.2))
    F.apply(half("Z", TOPZ, 1), "inter", 0.0)
    # надпись у флажка предохранителя (техническая): положение «огонь»
    fire, wf = text2("ОГОНЬ", font_path(True), 2.5, track=0.25)
    engrave(F, fire, "XZ", (-244.0, -55.4), -1, HWT, 1, depth=0.25, wall=0.2, bbox=bb(-246 - wf, -242, HWT - 1.3, HWT + 0.6, -57, -51.5))
    # прорезь спускового крючка
    F.sub(box((-270.5, -3.6, -75), (-256.5, 3.6, -55.0), 0.6), 0.4, bbox=bb(-272, -255, -5, 5, -72, -54))
    # скоба: гнутая полоса и шпора спереди
    guard = Path2(fillet_path(GUARD_PATH, GUARD_R, seg=10))
    F.add(strip(guard, "XZ", 1.7, -7.0, 7.0, rim=0.6), 0.9, bbox=bb(-280, -218, -8.5, 8.5, -99, -60))
    F.add(prism(Poly(fillet_poly(SPUR, [0.3, 0.3, 0.6, 0.6, 0.3, 0.3])), "XZ", -7.0, 7.0, rim=0.6), 0.6,
          bbox=bb(-223, -207, -8.5, 8.5, -81, -72))
    # головки осей на обоих бортах
    for x, z in PINS:
        for s in (-1, 1):
            y0, y1 = sorted((s * (HWT - 0.3), s * (HWT + 0.7)))
            F.add(cyl("Y", (x, z), 2.3, y0, y1, rim=0.45), 0.2, bbox=bb(x - 3.5, x + 3.5, y0 - 0.6, y1 + 0.6, z - 3.5, z + 3.5))
    return F


def trigger(h):
    F = Field("Trigger", (-270.5, -4.6, -90), (-248.5, 4.6, -53), h)
    blade = Path2(fillet_path(TRIG_PATH, [8.0, 14.0, 14.0], seg=10))
    F.add(strip(blade, "XZ", 2.6, -3.2, 3.2, rim=1.1))
    # верх крючка в коробке — шире, с отверстием под ось
    F.add(cyl("Y", TRIG_AXIS, 4.2, -3.2, 3.2, rim=0.6), 1.5, bbox=bb(-270, -259, -4, 4, -64, -54))
    F.sub(cyl("Y", TRIG_AXIS, 1.45, -5, 5), 0.2, bbox=bb(-267, -262, -4.5, 4.5, -61.5, -56))
    return F


def safety(h):
    """Флажок предохранителя (слева): диск на оси и рычажок вперёд (положение «огонь»)."""
    x, z = SAFETY_AXIS
    y0 = HWT + 0.15
    F = Field("Safety_Lever", (x - 10.5, -HWT - 2.5, z - 10.5), (x + 25.0, y0 + 9.5, z + 10.5), h)
    F.add(cyl("Y", (x, z), SAFETY_R, y0, y0 + 2.6, rim=0.3, rim1=0.9))
    # рычажок с отогнутым наружу упором под палец
    flag = Path2(fillet_path([(x + 4.0, y0 + 1.3), (x + 17.5, y0 + 1.3), (x + 21.5, y0 + 7.4)], [3.0]))
    F.add(strip(flag, "XY", 2.2, z - 3.0, z + 3.0, rim=0.8), 0.8, bbox=bb(x + 2, x + 24, y0, y0 + 9.5, z - 4, z + 4))
    # ось сквозь коробку и её головка
    F.add(cyl("Y", (x, z), 2.6, -HWT - 0.9, y0 + 2.0, rim=0.4), 0.0)
    F.add(cyl("Y", (x, z), 3.4, y0 + 2.4, y0 + 3.6, rim=0.5), 0.3, bbox=bb(x - 4.5, x + 4.5, y0 + 2, y0 + 4.2, z - 4.5, z + 4.5))
    # насечка на упоре
    def ser(X, Y, Z):
        m = smoothstep((X - (x + 17.8)) / 0.6) * smoothstep((3.2 - np.abs(Z - z)) / 0.5)
        return -0.3 * m * (np.cos((Y - y0) * 2 * math.pi / 1.1) * 0.5 + 0.5)
    F.displace(ser, bbox=bb(x + 17, x + 24.5, y0 + 1, y0 + 9.5, z - 4, z + 4), fine=True)
    return F


def parts():
    return [
        dict(name="Pistol_Grip", build=grip, h=0.15, coll="Спуск и рукоятка", mat="Polymer", adapt=0.1),
        dict(name="Trigger_Housing", build=trigger_housing, h=0.12, coll="Спуск и рукоятка", mat="Steel_blued", adapt=0.1),
        dict(name="Trigger", build=trigger, h=0.08, coll="Спуск и рукоятка", mat="Steel_phosphate",
             pivot=[TRIG_AXIS[0], 0.0, TRIG_AXIS[1]]),
        dict(name="Safety_Lever", build=safety, h=0.08, coll="Спуск и рукоятка", mat="Steel_phosphate",
             pivot=[SAFETY_AXIS[0], HWT, SAFETY_AXIS[1]]),
    ]
