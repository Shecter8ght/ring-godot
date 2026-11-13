"""«Проспект», дом 7 — форма (геометрия без текстур) пробного жилого дома по концепту 04_house_9f_brutalist_podium.

Запуск:
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_houses/house7.py \
      -- <выход.blend> [preview <папка>] [check]
Числа — копия из tools/prospekt_house7_plan.py (там matplotlib, в Blender его нет): сетки пролётов SOUTH / NORTH / END,
высоты, портал 14 × 2,4 м. Оси: метры, Z вверх, начало — центр пятна на земле, юг (двор) — −Y, проспект — +Y.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
from kit import B, inst, get_mat, HF, HG, D

# ---- числа из tools/prospekt_house7_plan.py
FLOORS_UP = 11
H_PARAPET = 0.45
H_ROOF = HG + HF * FLOORS_UP                  # 37,5 — верх плиты кровли
H_TOP = H_ROOF + H_PARAPET                    # 37,95
HX, HY = 18.0, 13.0                           # полупятно 36 × 26
SOUTH = [(0, 1.5, "P"), (1.5, 5.0, "W"), (5.0, 6.5, "P"), (6.5, 11.5, "LP"), (11.5, 12.0, "WD"), (12.0, 17.0, "LG"),
         (17.0, 19.0, "P"), (19.0, 24.0, "LP"), (24.0, 24.5, "WD"), (24.5, 29.5, "LG"), (29.5, 31.0, "P"),
         (31.0, 34.5, "W"), (34.5, 36.0, "P")]
NORTH = [(0, 1.4, "P"), (1.4, 4.8, "W"), (4.8, 6.3, "P"), (6.3, 10.6, "LP"), (10.6, 14.9, "LG"), (14.9, 16.3, "P"),
         (16.3, 19.7, "W"), (19.7, 21.1, "P"), (21.1, 25.4, "LP"), (25.4, 29.7, "LG"), (29.7, 31.2, "P"),
         (31.2, 34.6, "W"), (34.6, 36.0, "P")]
# торец: плановая сетка 26 м, но у обоих углов по 1,5 м занимает возврат угловой панели южного / северного фасада,
# поэтому торцевые пролёты отсчитываются от y = −11,5 (сетка плана минус 1,5 с каждой стороны)
END = [(0, 2.9, "P"), (2.9, 5.1, "WV"), (5.1, 10.4, "P"), (10.4, 12.6, "WV"), (12.6, 17.9, "P"), (17.9, 20.1, "WV"),
       (20.1, 23.0, "P")]
END_Y0 = -11.5
PORTAL = (-7.0, 7.0)
PORTAL_OUT = 2.4
LIB = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses"

# ---------------------------------------------------------------- сборка модулей
def build_kit():
    kit.mod_window(3.5); kit.mod_window(3.4)
    kit.mod_window(2.2, end=True)
    kit.mod_loggia_perf(5.0); kit.mod_loggia_perf(4.3)
    kit.mod_loggia_glass(5.0); kit.mod_loggia_glass(4.3)
    kit.mod_wood(0.5)
    kit.mod_panel(1.5)
    for c in ("L", "R"):
        kit.mod_panel(1.5, corner=c)
        kit.mod_ground(1.5, corner=c)
    kit.mod_ground(1.5)
    kit.mod_slabband(5.0); kit.mod_slabband(4.3)
    kit.mod_parapet(3.0); kit.mod_parapet(1.5)


def key_for(kind, w, corner=None):
    if kind == "P":
        return kit.mod_panel(w, corner=corner)
    if kind == "W":
        return kit.mod_window(w)
    if kind == "WV":
        return kit.mod_window(w, end=True)
    if kind == "LP":
        return kit.mod_loggia_perf(w)
    if kind == "LG":
        return kit.mod_loggia_glass(w)
    if kind == "WD":
        return kit.mod_wood(w)
    raise KeyError(kind)


FACES = {
    "S": (lambda s: (-HX + s, -HY), 0.0),
    "N": (lambda s: (HX - s, HY), math.pi),
    "E": (lambda s: (HX, END_Y0 + s), math.pi / 2),
    "W": (lambda s: (-HX, -END_Y0 - s), -math.pi / 2),
}


def upper_floors(col, face, bays):
    pos, rot = FACES[face]
    n = len(bays)
    for i, (a, b_, kind) in enumerate(bays):
        w = round(b_ - a, 4)
        corner = None
        if face in ("S", "N") and kind == "P" and i == 0:
            corner = "L"
        if face in ("S", "N") and kind == "P" and i == n - 1:
            corner = "R"
        m = key_for(kind, w, corner)
        for f in range(FLOORS_UP):
            z = HG + HF * f
            x, y = pos(a)
            inst(col, m, (x, y, z), rot, "%s_f%02d_%02d" % (face, f + 1, i), body=True)
            if kind in ("LP", "LG"):
                inst(col, kit.mod_slabband(w), (x, y, z + kit.LOG_H), rot, "%s_f%02d_%02d_band" % (face, f + 1, i), body=True)


def ground_floor(col):
    # юг: слева угол + 6 панелей, портал, справа 6 панелей + угол
    pw = 9.5 / 6
    s = 0.0
    seq = [("C", 1.5, "L")] + [("G", pw, None)] * 6
    pos, rot = FACES["S"]
    for k, (t, w, c) in enumerate(seq):
        m = kit.mod_ground(w, corner=c) if c else kit.mod_ground(w)
        x, y = pos(s)
        inst(col, m, (x, y, 0), rot, "S_g%02d" % k, body=True)
        s += w
    s = HX * 2 - 11.0 + 0.0
    s = 25.0
    seq = [("G", pw, None)] * 6 + [("C", 1.5, "R")]
    for k, (t, w, c) in enumerate(seq):
        m = kit.mod_ground(w, corner=c) if c else kit.mod_ground(w)
        x, y = pos(s)
        inst(col, m, (x, y, 0), rot, "S_g%02d" % (10 + k), body=True)
        s += w
    # юг у портала: простенки по сторонам витража
    inst(col, kit.mod_ground(3.0), (-7.0, -HY, 0), 0.0, "S_gp_L", body=True)
    inst(col, kit.mod_ground(5.0), (2.0, -HY, 0), 0.0, "S_gp_R", body=True)
    # север: угол, 9, 1, дверь 3, 1, 9, угол
    pos, rot = FACES["N"]
    s = 0.0
    seq = [("L", 1.5)] + [("G", 1.5)] * 9 + [("G", 1.5)] + [("D", 3.0)] + [("G", 1.5)] + [("G", 1.5)] * 9 + [("R", 1.5)]
    for k, (t, w) in enumerate(seq):
        if t == "D":
            m = "H7_ServiceDoor"
        elif t in ("L", "R"):
            m = kit.mod_ground(w, corner=t)
        else:
            m = kit.mod_ground(w)
        x, y = pos(s)
        inst(col, m, (x, y, 0), rot, "N_g%02d" % k, body=True)
        s += w
    # торцы: 15 панелей по 23 / 15
    w = 23.0 / 15
    for face in ("E", "W"):
        pos, rot = FACES[face]
        for k in range(15):
            x, y = pos(k * w)
            inst(col, kit.mod_ground(w), (x, y, 0), rot, "%s_g%02d" % (face, k), body=True)


def belts(col):
    z = HG
    m = kit.mod_belt(11.0)
    inst(col, m, (-HX, -HY, z), 0.0, "BeltS_L")
    inst(col, m, (7.0, -HY, z), 0.0, "BeltS_R")
    inst(col, kit.mod_belt(36.0), (HX, HY, z), math.pi, "BeltN")
    m = kit.mod_belt(25.88)
    inst(col, m, (HX, -HY + 0.06, z), math.pi / 2, "BeltE")
    inst(col, m, (-HX, HY - 0.06, z), -math.pi / 2, "BeltW")


def parapets(col):
    z = H_ROOF
    p3, p15 = kit.mod_parapet(3.0), kit.mod_parapet(1.5)
    for i in range(12):
        inst(col, p3, (-HX + 3 * i, -HY, z), 0.0, "PS%02d" % i, body=True)
        inst(col, p3, (HX - 3 * i, HY, z), math.pi, "PN%02d" % i, body=True)
    for i in range(8):
        inst(col, p3, (HX, -HY + 0.25 + 3 * i, z), math.pi / 2, "PE%02d" % i, body=True)
        inst(col, p3, (-HX, HY - 0.25 - 3 * i, z), -math.pi / 2, "PW%02d" % i, body=True)
    inst(col, p15, (HX, -HY + 0.25 + 24, z), math.pi / 2, "PE08", body=True)
    inst(col, p15, (-HX, HY - 0.25 - 24, z), -math.pi / 2, "PW08", body=True)


# ---------------------------------------------------------------- свои узлы дома 7
def mod_core():
    b = B("H7_Core")
    b.box(-HX + D, HX - D, -HY + D, HY - D, 0, H_ROOF, "concrete")
    kit.register("H7_Core", b)


def mod_portal():
    # --- козырёк: плита 450, рёбра-балки снизу до 3,7, лобовая балка 800
    b = B("H7_PortalCanopy")
    y_f = -HY - PORTAL_OUT
    b.box(PORTAL[0], PORTAL[1], y_f, -HY + 0.3, 4.20, HG, "concrete", bev=0.018, seg=2)
    b.box(PORTAL[0], PORTAL[1], y_f, y_f + 0.32, 3.70, 4.20, "concrete", bev=0.018, seg=2)
    for i in range(7):
        xc = -6.0 + 2.0 * i
        # косые рёбра: у стены сдвинуты на 1,1 м влево относительно переднего края (как на концепте)
        b.hull([(xc - 1.1 - 0.16, -HY, 3.70), (xc - 1.1 + 0.16, -HY, 3.70), (xc - 1.1 - 0.16, -HY, 4.20), (xc - 1.1 + 0.16, -HY, 4.20),
                (xc - 0.16, y_f + 0.32, 3.70), (xc + 0.16, y_f + 0.32, 3.70), (xc - 0.16, y_f + 0.32, 4.20), (xc + 0.16, y_f + 0.32, 4.20)],
               "concrete", bev=0.012, seg=2)
    # светильники под козырьком (между рёбрами)
    for xc in (-6.0, -4.0, -2.0, 0.0, 2.0, 4.0):
        b.cyl(xc + 1.0, -14.2, 4.14, 4.20, 0.11, "steel", seg=18)
        b.cyl(xc + 1.0, -14.2, 4.125, 4.14, 0.085, "lamp", seg=18)
    # отлив по верху козырька
    b.box(PORTAL[0] - 0.03, PORTAL[1] + 0.03, y_f - 0.03, y_f + 0.25, HG, HG + 0.04, "steel", bev=0.004)
    kit.register("H7_PortalCanopy", b)

    # --- пилоны: выпуклая оболочка с «переломом» на 1,8 м, косые грани
    for side, sgn in (("L", -1), ("R", 1)):
        b = B("H7_PortalPylon" + side)
        def X(x):
            return sgn * x
        top = [(X(6.9), -15.2, 3.7), (X(5.3), -15.2, 3.7), (X(5.3), -13.0, 3.7), (X(6.9), -13.0, 3.7)]
        base = [(X(6.9), -14.4, 0.0), (X(4.2), -14.4, 0.0), (X(4.2), -13.0, 0.0), (X(6.9), -13.0, 0.0)]
        knuckle = [(X(4.55), -15.0, 1.8)]
        b.hull(top + base + knuckle, "concrete", bev=0.022, seg=2)
        kit.register("H7_PortalPylon" + side, b)

    # --- простенки у витража: голова и порог
    b = B("H7_PortalCore")
    b.box(-4.0, 2.0, -HY, -HY + D, 3.45, HG, "concrete", bev=0.012, seg=2)
    b.box(-4.0, 2.0, -HY, -HY + D, 0.0, 0.15, "concrete", bev=0.012, seg=2)
    kit.register("H7_PortalCore", b)

    # --- витраж вестибюля 6,0 × 3,3 + двери 2 × 1,17 × 2,42
    b = B("H7_PortalGlazing")
    yf0, yf1 = -12.52, -12.40
    x0, x1, z0, z1 = -4.0, 2.0, 0.15, 3.45
    fr = 0.06
    b.box(x0, x0 + fr, yf0, yf1, z0, z1, "alu_frame", bev=0.003)
    b.box(x1 - fr, x1, yf0, yf1, z0, z1, "alu_frame", bev=0.003)
    b.box(x0 + fr, x1 - fr, yf0, yf1, z1 - fr, z1, "alu_frame", bev=0.003)
    b.box(x0 + fr, x1 - fr, yf0, yf1, z0, z0 + 0.12, "alu_frame", bev=0.003)
    dx0, dx1 = -2.17, 0.17
    for xm in (dx0, dx1):
        b.box(xm - 0.04, xm + 0.04, yf0 - 0.02, yf1 + 0.02, z0 + 0.12, z1 - fr, "alu_frame", bev=0.003)
    b.box(x0 + fr, x1 - fr, yf0 - 0.02, yf1 + 0.02, 2.55 - 0.05, 2.55 + 0.05, "alu_frame", bev=0.003)   # ригель над дверью
    ym = (yf0 + yf1) / 2
    # боковые части: ригель на 1,0 м низкий
    for (xa, xb) in ((x0 + fr, dx0 - 0.04), (dx1 + 0.04, x1 - fr)):
        b.box(xa, xb, yf0, yf1, 1.0 - 0.03, 1.0 + 0.03, "alu_frame", bev=0.002)
        b.box(xa, xb, ym - 0.004, ym + 0.004, z0 + 0.12, 0.97, "glass")
        b.box(xa, xb, ym - 0.004, ym + 0.004, 1.03, 2.50, "glass")
        b.box(xa, xb, ym - 0.004, ym + 0.004, 2.60, z1 - fr, "glass")
    b.box(dx0 + 0.04, dx1 - 0.04, ym - 0.004, ym + 0.004, 2.60, z1 - fr, "glass")
    # створки: 2 × 1,17, высота 2,42 от пола; рамка 100 мм, нижний ригель 200
    dz0, dz1 = z0 + 0.12, z0 + 0.12 + 2.42
    for (xa, xb) in ((dx0 + 0.04, -1.0 - 0.01), (-1.0 + 0.01, dx1 - 0.04)):
        yl0, yl1 = yf0 - 0.04, yf1 - 0.0
        b.box(xa, xa + 0.09, yl0, yl1, dz0, dz1, "alu_frame", bev=0.003)
        b.box(xb - 0.09, xb, yl0, yl1, dz0, dz1, "alu_frame", bev=0.003)
        b.box(xa + 0.09, xb - 0.09, yl0, yl1, dz1 - 0.09, dz1, "alu_frame", bev=0.003)
        b.box(xa + 0.09, xb - 0.09, yl0, yl1, dz0, dz0 + 0.20, "alu_frame", bev=0.003)
        b.box(xa + 0.09, xb - 0.09, ym - 0.004, ym + 0.004, dz0 + 0.20, dz1 - 0.09, "glass")
    for xh in (-1.0 - 0.12, -1.0 + 0.12):                              # ручки-скобы
        b.cyl(xh, yf0 - 0.10, 0.85, 1.55, 0.016, "steel", seg=12)
        for zz in (0.9, 1.5):
            b.box(xh - 0.012, xh + 0.012, yf0 - 0.10, yf0 - 0.04, zz - 0.012, zz + 0.012, "steel")
    # тёплый интерьер за стеклом и потолочные светильники
    b.box(x0 + fr, x1 - fr, -11.80, -11.78, z0 + 0.12, z1 - fr, "wood")
    b.box(x0 + fr, x1 - fr, -12.38, -11.80, 0.15, 0.17, "wood")
    for xc in (-3.0, -1.0, 1.0):
        b.box(xc - 0.6, xc + 0.6, -12.2, -12.0, 3.30, 3.33, "lamp")
    kit.register("H7_PortalGlazing", b)

    # --- крыльцо сбоку: 6 ступеней 0,15 × 0,30 к стене, 1,8 м шириной
    b = B("H7_PortalSteps")
    for k in range(6):
        h = 0.9 - 0.15 * k
        b.box(2.3, 3.9, -HY - 0.30 * (k + 1), -HY - 0.30 * k, 0.0, h, "concrete", bev=0.008, seg=2)
    b.box(2.3, 3.9, -HY, -HY + 0.01, 0.0, 0.9, "concrete")
    kit.register("H7_PortalSteps", b)


def mod_service_door():
    """Бетонная панель 3,0 × 4,5 с проёмом, стальная дверь 1,17 × 2,42 в коробке из уголка, козырёк-уголок."""
    b = B("H7_ServiceDoor")
    w, h = 3.0, HG
    ox0, ox1, oh = 0.875, 2.125, 2.5          # проём 1,25 × 2,5
    # тело
    b.box(0, ox0, 0.20, D, 0, h, "concrete")
    b.box(ox1, w, 0.20, D, 0, h, "concrete")
    b.box(ox0, ox1, 0.20, D, oh, h, "concrete")
    # лицо щитами
    for (xa, xb) in ((0.0, ox0), (ox1, w)):
        for i in range(3):
            za = 1.5 * i + 0.006 if i else 0.0
            b.box(xa, xb, 0.14, 0.20, za, 1.5 * (i + 1) - 0.006, "concrete", bev=0.010, seg=2)
    b.box(ox0, ox1, 0.14, 0.20, oh, 3.0 - 0.006, "concrete", bev=0.010, seg=2)
    b.box(ox0, ox1, 0.14, 0.20, 3.0 + 0.006, h - 0.006 * 0 - 0.006, "concrete", bev=0.010, seg=2)
    b.box(0.0, 0.30, 0.0, 0.14, 0.0, h, "concrete", bev=0.012, seg=2)
    b.box(ox1 - 0.0, ox1 + 0.30, 0.0, 0.14, 0.0, h, "concrete", bev=0.012, seg=2)
    b.box(0.0, w, 0.0, 0.14, 0.0, 0.15, "concrete", bev=0.008, seg=2)
    # коробка из уголка 50 и полотно
    fx0, fx1 = ox0 + 0.0, ox1
    b.box(fx0, fx0 + 0.04, 0.16, 0.30, 0.0, oh, "steel", bev=0.003)
    b.box(fx1 - 0.04, fx1, 0.16, 0.30, 0.0, oh, "steel", bev=0.003)
    b.box(fx0 + 0.04, fx1 - 0.04, 0.16, 0.30, oh - 0.04, oh, "steel", bev=0.003)
    lx0, lx1 = 1.5 - 0.585, 1.5 + 0.585          # полотно 1,17
    b.box(lx0, lx1, 0.21, 0.26, 0.04, 2.46, "dark_panel", bev=0.005, seg=2)
    for zz in (0.35, 1.2, 2.05):
        b.box(lx0 + 0.07, lx1 - 0.07, 0.195, 0.21, zz - 0.15, zz + 0.15, "dark_panel", bev=0.004)   # штамповка
    b.box(lx0 - 0.005, lx0 + 0.04, 0.18, 0.21, 0.2, 0.34, "steel", bev=0.002)                  # петли
    b.box(lx0 - 0.005, lx0 + 0.04, 0.18, 0.21, 1.15, 1.29, "steel", bev=0.002)
    b.box(lx0 - 0.005, lx0 + 0.04, 0.18, 0.21, 2.05, 2.19, "steel", bev=0.002)
    b.box(lx1 - 0.18, lx1 - 0.05, 0.17, 0.21, 1.0, 1.04, "steel", bev=0.003)                   # ручка-нажим
    b.box(lx1 - 0.14, lx1 - 0.06, 0.19, 0.21, 1.12, 1.24, "steel", bev=0.003)                  # замок
    # козырёк-уголок над дверью: наклонный лист 1,8 × 0,7 и боковые щёки
    cx0, cx1 = 0.6, 2.4
    b.hull([(cx0, 0.0, 2.95), (cx1, 0.0, 2.95), (cx0, -0.70, 2.78), (cx1, -0.70, 2.78),
            (cx0, 0.0, 2.955), (cx1, 0.0, 2.955), (cx0, -0.70, 2.785), (cx1, -0.70, 2.785)], "steel", bev=0.001)
    for xs in (cx0, cx1 - 0.006):
        b.hull([(xs, 0.0, 2.95), (xs + 0.006, 0.0, 2.95), (xs, -0.70, 2.78), (xs + 0.006, -0.70, 2.78),
                (xs, -0.70, 2.70), (xs + 0.006, -0.70, 2.70), (xs, 0.0, 2.70), (xs + 0.006, 0.0, 2.70)], "steel")
    kit.register("H7_ServiceDoor", b)


def mod_roof():
    z = H_ROOF
    b = B("H7_Roof")
    b.box(-HX + 0.25, HX - 0.25, -HY + 0.25, HY - 0.25, z - 0.20, z, "concrete")
    b.box(-HX + 0.50, HX - 0.50, -HY + 0.50, HY - 0.50, z, z + 0.04, "dark_panel", bev=0.01, seg=2)
    # швы кровельного покрытия: полосы 1,0 м
    for i in range(-17, 18, 1):
        pass
    # две машинные: 6,0 × 5,0 × 3,0, плита-козырёк, дверь и жалюзи
    for xc in (-7.5, 7.5):
        x0, x1, y0, y1 = xc - 3.0, xc + 3.0, 0.0, 5.0
        z0, z1 = z + 0.04, z + 0.04 + 3.0
        b.box(x0, x1, y0, y1, z0, z1, "dark_panel", bev=0.01, seg=2)
        b.box(x0 - 0.12, x1 + 0.12, y0 - 0.12, y1 + 0.12, z1, z1 + 0.14, "concrete", bev=0.012, seg=2)
        # дверь на южной стене
        b.box(xc - 0.64, xc + 0.64, y0 - 0.03, y0 + 0.06, z0, z0 + 2.46, "steel", bev=0.003)
        b.box(xc - 0.585, xc + 0.585, y0 - 0.015, y0 + 0.07, z0 + 0.04, z0 + 2.46, "dark_panel", bev=0.004)
        b.box(xc + 0.40, xc + 0.52, y0 - 0.05, y0 - 0.015, z0 + 1.0, z0 + 1.04, "steel", bev=0.003)
        # жалюзи на торцах
        for sx, nx in ((x0, -1), (x1, 1)):
            yc = 2.5
            fw, fh, fz = 2.0, 1.0, z0 + 1.5
            xo = sx + nx * 0.0
            for (ya, yb, za, zb) in ((yc - fw / 2, yc + fw / 2, fz, fz + 0.05), (yc - fw / 2, yc + fw / 2, fz + fh - 0.05, fz + fh),
                                     (yc - fw / 2, yc - fw / 2 + 0.05, fz, fz + fh), (yc + fw / 2 - 0.05, yc + fw / 2, fz, fz + fh)):
                b.box(min(xo, xo + nx * 0.04), max(xo, xo + nx * 0.04), ya, yb, za, zb, "steel", bev=0.003)
            for k in range(7):
                zz = fz + 0.12 + k * 0.125
                b.box(min(xo, xo + nx * 0.03), max(xo, xo + nx * 0.03) + 0.0, yc - fw / 2 + 0.05, yc + fw / 2 - 0.05,
                      zz - 0.045, zz + 0.045, "steel", rot=("Y", nx * math.radians(38)))
    # вентшахты
    for (vx, vy) in ((-14.0, 8.0), (14.0, 8.0), (-1.0, -7.0), (11.0, -7.0)):
        b.cyl(vx, vy, z + 0.04, z + 1.5, 0.35, "steel", seg=24)
        b.cyl(vx, vy, z + 1.5, z + 1.56, 0.50, "steel", seg=24, r2=0.50)
        b.cyl(vx, vy, z + 0.04, z + 0.20, 0.45, "concrete", seg=24)
    # антенна: мачта 6 м на плите с растяжками-распорками
    ax, ay = 0.0, 9.5
    b.box(ax - 0.4, ax + 0.4, ay - 0.4, ay + 0.4, z + 0.04, z + 0.19, "concrete", bev=0.008)
    b.cyl(ax, ay, z + 0.19, z + 6.2, 0.045, "steel", seg=14)
    for zz, L in ((z + 3.2, 0.8), (z + 4.4, 0.65), (z + 5.6, 0.5)):
        b.box(ax - L, ax + L, ay - 0.012, ay + 0.012, zz - 0.012, zz + 0.012, "steel")
    kit.register("H7_Roof", b)


# ---------------------------------------------------------------- сцена, набор частей, просмотр
def new_col(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


def build(out):
    sc = bpy.context.scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    root = sc.collection
    mods = new_col("Модули", root)
    kit.set_root(mods)
    asm = new_col("Дом7_сборка", root)
    kset = new_col("Набор_частей", root)
    prev = new_col("Просмотр", root)
    build_kit()
    mod_core(); mod_portal(); mod_service_door(); mod_roof()
    for k in ("H7_Core", "H7_PortalCanopy", "H7_PortalPylonL", "H7_PortalPylonR", "H7_PortalCore", "H7_PortalGlazing",
              "H7_PortalSteps", "H7_ServiceDoor", "H7_Roof"):
        pass
    inst(asm, "H7_Core", (0, 0, 0), 0, "Core", body=True)
    for k in ("H7_PortalCanopy", "H7_PortalPylonL", "H7_PortalPylonR", "H7_PortalCore", "H7_PortalGlazing", "H7_PortalSteps"):
        inst(asm, k, (0, 0, 0), 0, k)
    inst(asm, "H7_Roof", (0, 0, 0), 0, "Roof")
    ground_floor(asm)
    upper_floors(asm, "S", SOUTH)
    upper_floors(asm, "N", NORTH)
    upper_floors(asm, "E", END)
    upper_floors(asm, "W", END)
    parapets(asm)
    belts(asm)

    # набор частей: модули в ряд (y = 200 — вне кадров дома), подписи — пустышки с именем
    cur = 60.0
    for name in ("H_Window_3500", "H_WindowEnd_2200", "H_LoggiaPerf_5000", "H_LoggiaGlass_5000", "H_WoodInsert_500",
                 "H_SlabBand_5000", "H_Panel_1500", "H_PanelCornerL_1500", "H_PanelCornerR_1500", "H_Ground_1500",
                 "H_GroundCornerL_1500", "H_GroundCornerR_1500", "H_Parapet_3000", "H7_ServiceDoor"):
        w = {"H_Window_3500": 3.5, "H_WindowEnd_2200": 2.2, "H_LoggiaPerf_5000": 5.0, "H_LoggiaGlass_5000": 5.0,
             "H_WoodInsert_500": 0.5, "H_SlabBand_5000": 5.0, "H_Parapet_3000": 3.0, "H7_ServiceDoor": 3.0}.get(name, 1.5)
        inst(kset, name, (cur, 200, 0), 0, name)
        lab = bpy.data.objects.new("LABEL " + name, None)
        lab.empty_display_type = "PLAIN_AXES"
        lab.empty_display_size = 0.15
        lab.location = (cur + w / 2, 199.0, -0.2)
        lab.show_name = True
        kset.objects.link(lab)
        cur += w + 2.0
    inst(kset, "H7_PortalPylonL", (cur + 7, 200, 0), 0, "H7_PortalPylonL (на месте дома: x -6.8..-4.4)")
    setup_preview(prev, sc)
    mods_lc = bpy.context.view_layer.layer_collection.children["Модули"]
    mods_lc.exclude = True
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out)


def setup_preview(prev, sc):
    # земля, двухэтажный отдел полиции к северу (+7 м), мир, свет, камеры
    gm = bpy.data.materials.new("preview_ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.30, 0.31, 0.30, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    pm = bpy.data.materials.new("preview_police")
    pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.47, 0.50, 1)
    bm = B("preview_ground")
    bm.box(-400, 400, -400, 400, -0.5, -0.0, "concrete")
    ob = bm.build()
    ob.data.materials.clear(); ob.data.materials.append(gm)
    prev.objects.link(ob)
    bp = B("preview_police")
    bp.box(-20, 10, 21, 35, 0, 7, "concrete")
    ob2 = bp.build()
    ob2.data.materials.clear(); ob2.data.materials.append(pm)
    prev.objects.link(ob2)
    w = bpy.data.worlds.new("overcast")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.66, 0.70, 0.76, 1)
    bg.inputs["Strength"].default_value = 0.75
    sc.world = w
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 2.2
    sun.angle = math.radians(18)
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(52), math.radians(8), math.radians(-35))
    prev.objects.link(so)
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    cams = {
        "cam_court": ((-60, -64, 9), (0, -6, 16), 30, None),
        "cam_avenue": ((-6, 78, 1.7), (-6, 13, 1.7), 24, None),
        "cam_portal": ((-3.5, -26, 1.7), (-0.5, -13.5, 3.2), 24, None),
        "cam_loggia": ((-6.0, -27, 14.5), (-6.5, -13, 18.0), 45, None),
        "cam_end": ((78, -12, 3.0), (18, 0, 17), 30, None),
        "cam_corner_up": ((-30, -30, 33), (-18, -13, 33), 35, None),
    }
    for n, (loc, tgt, lens, _) in cams.items():
        cd = bpy.data.cameras.new(n)
        cd.lens = lens
        cd.clip_end = 600
        co = bpy.data.objects.new(n, cd)
        co.location = loc
        co.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        if n == "cam_avenue":
            cd.shift_y = 0.19
        prev.objects.link(co)
    orth = {"ortho_south": ((0, -150, 20.4), (math.pi / 2, 0, 0)),
            "ortho_north": ((0, 150, 20.4), (math.pi / 2, 0, math.pi)),
            "ortho_east": ((150, 0, 20.4), (math.pi / 2, 0, math.pi / 2))}
    for n, (loc, rot) in orth.items():
        cd = bpy.data.cameras.new(n)
        cd.type = "ORTHO"
        cd.ortho_scale = 51.0
        cd.clip_end = 600
        co = bpy.data.objects.new(n, cd)
        co.location = loc
        co.rotation_euler = rot
        prev.objects.link(co)
    # камеры набора частей
    for n, loc, scale in (("set_a", (66, 120, 2.2), 24.0), ("set_b", (90, 120, 2.2), 30.0), ("set_c", (118, 120, 2.2), 30.0)):
        pass


# ---------------------------------------------------------------- проверка и кадры
def signed_volume_components(me):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    parent = {v.index: v.index for v in bm.verts}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        a, b = find(e.verts[0].index), find(e.verts[1].index)
        if a != b:
            parent[a] = b
    vol = {}
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        r = find(f.verts[0].index)
        for i in range(1, len(vs) - 1):
            vol[r] = vol.get(r, 0.0) + vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    bnd = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    bm.free()
    return len(vol), sum(1 for v in vol.values() if v < 0), bnd, nonman


def check(out_txt):
    lines = []
    mods = bpy.data.collections["Модули"]
    tris = {}
    bad = 0
    lines.append("МОДУЛИ: имя | треугольники | оболочек | вывернутых | граничных рёбер | неманифолд")
    for c in sorted(mods.children, key=lambda c: c.name):
        ob = c.objects[0]
        me = ob.data
        t = sum(len(p.vertices) - 2 for p in me.polygons)
        tris[c.name] = t
        n, neg, bnd, nm = signed_volume_components(me)
        if neg or bnd or nm:
            bad += 1
        bb = [ob.matrix_world @ Vector(v) for v in ob.bound_box]
        lines.append("%-28s %7d %4d %3d %4d %4d   габарит %.2f x %.2f x %.2f" % (
            c.name, t, n, neg, bnd, nm,
            max(v.x for v in bb) - min(v.x for v in bb), max(v.y for v in bb) - min(v.y for v in bb),
            max(v.z for v in bb) - min(v.z for v in bb)))
    asm = bpy.data.collections["Дом7_сборка"]
    total = 0
    env_min = Vector((1e9, 1e9, 1e9)); env_max = Vector((-1e9, -1e9, -1e9))
    zs = set()
    for o in asm.objects:
        m = o.get("module")
        total += tris.get(m, 0)
        if o.get("body") and m and (m.startswith("H_Panel") or m.startswith("H_Ground") or m.startswith("H_Parapet")):
            mc = bpy.data.collections[m]
            for v in mc.objects[0].bound_box:
                p = o.matrix_world @ Vector(v)
                for i in range(3):
                    env_min[i] = min(env_min[i], p[i]); env_max[i] = max(env_max[i], p[i])
        if m and m.startswith("H_Window_"):
            zs.add(round(o.location.z, 3))
    lines.append("")
    lines.append("СБОРКА: %d экземпляров, %d треугольников (с экземплярами), плюс 'свои узлы' внутри" % (len(asm.objects), total))
    size = env_max - env_min
    lines.append("ОБОЛОЧКА здания (панели, ограждение кровли; без портала, отливов, надстроек): %.3f x %.3f x %.3f, x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f" % (
        size.x, size.y, size.z, env_min.x, env_max.x, env_min.y, env_max.y, env_min.z, env_max.z))
    ok_dim = abs(size.x - 36) < 0.02 and abs(size.y - 26) < 0.02 and abs(size.z - 37.95) < 0.02
    lines.append("габарит 36 x 26 x 37,95 (+-0,02): %s" % ("ДА" if ok_dim else "НЕТ"))
    exp = sorted(round(4.5 + 3.0 * i, 3) for i in range(11))
    lines.append("этажи (низ окон), м: %s — ожидалось %s: %s" % (sorted(zs), exp, "ДА" if sorted(zs) == exp else "НЕТ"))
    lines.append("модулей с открытыми / вывернутыми / неманифолдными оболочками: %d" % bad)
    # полный полигонаж с учётом портала и крыши
    lines.append("")
    lines.append("ВСЕГО на доме (сумма по экземплярам, треугольников): %d" % total)
    txt = "\n".join(lines)
    with open(out_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt + "\n")
    print(txt)
    return ok_dim and bad == 0


def render(prev_dir):
    sc = bpy.context.scene
    os.makedirs(prev_dir, exist_ok=True)
    kset = bpy.data.collections["Набор_частей"]
    asm = bpy.data.collections["Дом7_сборка"]
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except Exception:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    sc.eevee.taa_render_samples = 48
    try:
        sc.eevee.use_raytracing = True
    except Exception:
        pass

    def shot(cam_name, fname, res=(1600, 1000), hide_set=True, hide_house=False):
        cam = bpy.data.objects[cam_name]
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = res
        kset.hide_render = hide_set
        asm.hide_render = hide_house
        sc.render.filepath = os.path.join(prev_dir, fname)
        bpy.ops.render.render(write_still=True)

    for n in ("cam_court", "cam_avenue", "cam_portal", "cam_loggia", "cam_end", "cam_corner_up"):
        shot(n, n + ".png")
    for n, f in (("ortho_south", "ortho_south.png"), ("ortho_north", "ortho_north.png"), ("ortho_east", "ortho_east.png")):
        shot(n, f, res=(1100, 900))
    # набор частей: ортокамера с юга на ряд
    for i, (x, sx, nm) in enumerate(((60, 24.0, "set_a"), (84, 30.0, "set_b"), (112, 28.0, "set_c"))):
        cd = bpy.data.cameras.new(nm)
        cd.type = "ORTHO"; cd.ortho_scale = sx; cd.clip_end = 600
        co = bpy.data.objects.new(nm, cd)
        co.location = (x + sx / 2 - 1, 120, 2.4)
        co.rotation_euler = (math.pi / 2, 0, 0)
        bpy.context.scene.collection.objects.link(co)
        shot(nm, "set_%d.png" % (i + 1), res=(1600, 700), hide_set=False, hide_house=True)
    asm.hide_render = False
    kset.hide_render = True
    # крупные планы: портал, пилон, лоджия — под скользящим светом
    sun = bpy.data.objects["sun"]
    sun.rotation_euler = (math.radians(75), math.radians(0), math.radians(-70))
    for n, f in (("cam_portal", "portal_grazing.png"), ("cam_loggia", "loggia_grazing.png")):
        shot(n, f)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0]
    build(out)
    print("saved", out)
    do_check = "check" in argv
    prev_dir = argv[argv.index("preview") + 1] if "preview" in argv else None
    if do_check or prev_dir:
        bpy.ops.wm.open_mainfile(filepath=out)
    ok = True
    if do_check:
        ok = check(os.path.join(os.path.dirname(os.path.dirname(out)), "check.txt") if False else os.path.splitext(out)[0] + "_check.txt")
    if prev_dir:
        render(prev_dir)
    sys.exit(0 if ok else 1)


main()
