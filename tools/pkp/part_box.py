# ПКП: коробки для ленты на 100 и на 200 патронов (Box100_*, Box200_*): штампованный корпус с тремя выштамповками на
# длинных стенках, крышка на рояльной петле у правого (−Y) торца, откидная заслонка выхода ленты на крышке, защёлка
# (откидная скоба + вертушок) у левого (+Y) торца, брезентовая ручка на правом торце, узел крепления на крышке
# (Т-образный ползун в загнутых направляющих кронштейна Box_Bracket + упор сзади + подпружиненный зуб спереди).
# Устройство — по снимкам владельца 08–16 (13/14 — бока, 16 — правый торец с ручкой), фото настоящей коробки
# (refs/web/C_boxes, B10_box_mount) и описанию NGIC (refs/web/dimensions.md, раздел 3). Размеров настоящих коробок
# в открытых источниках нет — габариты оценочные (см. константы).
# Рёбра в полях расстояний: длинная сторона коробки — вдоль Y (патроны в ленте лежат вдоль X, слои — по Z).
import math

import numpy as np

from dims import *
from sdf import *

# ---- общие размеры (мм модели) ----
XC = -100.0                       # середина коробки по X: наложение на снимок 13, силуэт 98 мм на плоскости снимка
BW = 95.8                         # толщина коробки вдоль ствола у гладких стенок (рёбра ещё +1,3 с каждой стороны): снимок 13
HW = BW / 2
YE = -55.0                        # плоскость правого (−Y) торца: снимки 08, 12 (торец под правым бортом коробки)
Z_RIM = -95.0                     # верхняя кромка корпуса = линия петли: снимок 13 (нижний ряд колен петли)
LID_TOP = -59.0                   # верх крышки: снимок 13 (над ним — только ползун крепления)
T = 1.2                           # лист корпуса и крышки (dims.BOX_SHEET = 1,0 — при шаге 0,15 мм тоньше нельзя)
R_PLAN = 6.0                      # скругление вертикальных рёбер корпуса
R_BOT = 5.0                       # скругление нижних рёбер
# шарнир крышки (вдоль X): центр оси и радиус колена
YH, ZH, RH = -58.5, -94.0, 3.4
# колена петли по X от середины: (0 — лишь у крышки, 1 — лишь у корпуса); в середине — просвет под ручку
HINGE = [(-47.9, -34.9, "lid"), (-34.5, -20.5, "body"), (20.5, 34.5, "body"), (34.9, 47.9, "lid")]
HINGE_GAP = 20.1                  # полуширина просвета под ремень
# шарнир заслонки выхода ленты (на верху крышки у правого торца)
YF, ZF, RF = -59.1, -63.2, 2.5
FLAP_SEG = [(-45.0, -27.6, "flap"), (-27.2, -9.4, "lid"), (-9.0, 9.0, "flap"), (9.4, 27.2, "lid"), (27.6, 45.0, "flap")]
# щель выхода ленты в крышке (X, Y)
SLOT_X0, SLOT_X1 = -140.0, -58.0
SLOT_Y0, SLOT_Y1 = -48.0, -28.0
# защёлка на левом торце: ось скобы над торцом, вертушок на корпусе
# защёлка — по левому боковому рендеру владельца 14: скоба висит на петле во всю ширину у нижней кромки крышки
# (колена крышки по краям, колена скобы между ними, посередине на оси пружина), ниже сужается в язык с прорезью
# под вертушок; вертушок — на 63 мм ниже оси
LATCH_DY, LATCH_Z = 5.4, -94.0
BTN_Z = -157.0
LATCH_LID_SEG = [(-46.4, -28.8), (30.0, 46.4)]       # колена на крышке (X от середины коробки)
LATCH_SEG = [(-28.4, -8.8), (11.0, 29.6)]            # колена скобы
LATCH_SPRING = (-8.2, 10.4)                           # пружина на оси между коленами скобы

BOX = {
    # низ коробки на 100 — по правому боковому рендеру владельца 13 (кромка низа на Z ≈ −218 с поправкой на глубину
    # торца): коробка высокая, 159 мм от верха крышки; длина 205 — по видимой ширине левого торца на рендере 14
    # (перспектива, ±20 мм); на 200 — оценка по объёму ленты (вдвое больше при той же толщине)
    "Box100": dict(L=205.0, zb=-218.0, coll="Коробка 100", hidden=False, rib_h=24.0, rib_pitch=36.0, rib_z0=25.5),
    "Box200": dict(L=305.0, zb=-270.0, coll="Коробка 200", hidden=True, rib_h=30.0, rib_pitch=46.0, rib_z0=40.0),
}

# ---- для соседа, делающего ленту (мм модели) ----
# точка выхода ленты: середина щели на верхней плоскости крышки, X — середина патрона (донце FEED_RIM_X + полдлины);
# направление ленты в плоскости YZ (dy, dz) — от щели к окну приёмника справа (по Z от −59 до оси патрона на лотке)
BOX100_BELT_EXIT = (FEED_RIM_X + CART_LEN / 2, (SLOT_Y0 + SLOT_Y1) / 2, LID_TOP)
BOX100_BELT_DIR = (0.14, 0.99)
BOX200_BELT_EXIT = BOX100_BELT_EXIT      # коробка на 200 висит на том же кронштейне, крышка и щель те же
BOX200_BELT_DIR = BOX100_BELT_DIR


def _y1(pre):
    return YE + BOX[pre]["L"]


# ================= корпус =================

def body(pre):
    P = BOX[pre]; L = P["L"]; zb = P["zb"]

    def build(h):
        y0, y1, ym = YE, YE + L, YE + L / 2
        x0, x1 = XC - HW, XC + HW
        F = Field(pre + "_Body", (x0 - 3, y0 - 8.5, zb - 1.5), (x1 + 3, y1 + 9, Z_RIM + 6.5), h)

        def solid(X, Y, Z):
            d = i_round(np.abs(X - XC) - HW, np.abs(Y - ym) - L / 2, R_PLAN)
            d = i_round(d, zb - Z, R_BOT)
            return np.maximum(d, Z - (Z_RIM + 8.0))
        F.add(solid)
        # три выштамповки-«овала» на каждой длинной стенке (снимки 08, 09, фото 02)
        rh = P["rib_h"]
        shapes = [rect2(y0 + 20, y1 - 20, zb + P["rib_z0"] + i * P["rib_pitch"] - rh / 2,
                        zb + P["rib_z0"] + i * P["rib_pitch"] + rh / 2, rh / 2) for i in range(3)]

        def ribs(X, Y, Z):
            d2 = shapes[0](Y, Z)
            for s in shapes[1:]:
                d2 = np.minimum(d2, s(Y, Z))
            return 1.3 * smoothstep(-d2 / 1.5) * smoothstep((np.abs(X - XC) - (HW - 3.0)) / 1.5)
        F.displace(ribs, bbox=bb(x0 - 3, x1 + 3, y0 + 5, y1 - 5, zb + 2, Z_RIM), fine=False)
        # торцы: П-образная выштамповка на правом (снимок 16) и вертикальные канавки жёсткости на обоих
        ush = union2(rect2(XC - 24, XC - 12, zb + 22, zb + 50, 6.0), rect2(XC + 12, XC + 24, zb + 22, zb + 50, 6.0),
                     rect2(XC - 24, XC + 24, zb + 20, zb + 29, 4.0), r=1.5)

        def end_emboss(X, Y, Z):
            return 0.7 * smoothstep(-ush(X, Z) / 1.2) * smoothstep(((y0 + 3.0) - Y) / 1.5)
        F.displace(end_emboss, bbox=bb(XC - 29, XC + 29, y0 - 2, y0 + 4, zb + 15, zb + 55), fine=False)

        def grooves(X, Y, Z):
            g = np.maximum(smoothstep((1.7 - np.abs(X - (XC - 38.0))) / 0.9), smoothstep((1.7 - np.abs(X - (XC + 38.0))) / 0.9))
            zf = smoothstep((Z - (zb + 8.0)) / 3.0) * smoothstep(((Z_RIM - 4.0) - Z) / 3.0)
            near = smoothstep(((y0 + 2.5) - Y) / 1.2) + smoothstep((Y - (y1 - 2.5)) / 1.2)
            return -0.9 * g * zf * near
        F.displace(grooves, bbox=bb(x0, x1, y0 - 2, y1 + 2, zb, Z_RIM), fine=False)
        F.shell(T)
        # сверху открыт; кромка — линия разъёма с крышкой
        F.apply(half("Z", Z_RIM, 1), "inter", 0.35, bbox=bb(x0 - 3, x1 + 3, y0 - 9, y1 + 9, Z_RIM - 1.5, Z_RIM + 9.5))
        # отбортовка под крышку; у правого торца её нет (там петля)
        ring_out = rect2(x0 - 1.0, x1 + 1.0, y0, y1 + 1.0, R_PLAN + 1.0)
        ring_in = rect2(x0 + T, x1 - T, y0 + T, y1 - T, R_PLAN - T)
        F.add(prism2(minus2(ring_out, ring_in), "XY", Z_RIM - 2.6, Z_RIM, rim=0.35), 0.25,
              bbox=bb(x0 - 2, x1 + 2, y0 - 1, y1 + 2, Z_RIM - 3.5, Z_RIM + 0.5))
        # колена петли на корпусе и их полки к торцевой стенке
        for a, b, who in HINGE:
            if who != "body":
                continue
            xa, xb = XC + a, XC + b
            F.add(cyl("X", (YH, ZH), RH, xa, xb, rim=0.5), 0.0, bbox=bb(xa - 1, xb + 1, YH - 4, YH + 4, ZH - 4, ZH + 4))
            F.add(box((xa, YH, Z_RIM - 5.5), (xb, y0 + 0.6, Z_RIM - 0.2), 0.7), 0.4,
                  bbox=bb(xa - 1, xb + 1, YH - 1, y0 + 2, Z_RIM - 7, Z_RIM + 1))
        F.sub(cyl("X", (YH, ZH), 1.8, XC - 53, XC + 53), 0.3, bbox=bb(XC - 53, XC + 53, YH - 3.6, YH + 3.6, ZH - 3.6, ZH + 3.6))
        # скобы ремня на правом торце: пластина на двух ножках, под ней ремень идёт вплотную к стенке; заклёпка по центру
        for zt0, zt1 in ((Z_RIM - 21.0, Z_RIM - 9.0), (zb + 4.0, zb + 16.0)):
            F.add(prism2(rect2(XC - 22.5, XC + 22.5, zt0, zt1, 2.0), "XZ", y0 - 4.4, y0 - 3.2, rim=0.35), 0.0,
                  bbox=bb(XC - 25, XC + 25, y0 - 5, y0 - 2.5, zt0 - 1, zt1 + 1))
            for s in (-1, 1):
                xa, xb = sorted((XC + s * 19.5, XC + s * 22.5))
                F.add(box((xa, y0 - 4.4, zt0 + 1.5), (xb, y0 + 0.6, zt1 - 1.5), 0.5), 0.3,
                      bbox=bb(xa - 1, xb + 1, y0 - 5, y0 + 1.5, zt0, zt1))
            zm = (zt0 + zt1) / 2
            cap = inter(sphere((XC, y0 - 2.4, zm), 3.0), half("Y", y0 - 4.4, 1))
            F.add(cap, 0.2, bbox=bb(XC - 4, XC + 4, y0 - 6, y0 - 3.5, zm - 4, zm + 4))
        # втулка вертушка у левого торца
        F.add(cyl("Y", (XC, BTN_Z), 5.5, y1 - 0.3, y1 + 1.7, rim=0.4), 0.3, bbox=bb(XC - 6, XC + 6, y1 - 1, y1 + 2.5, BTN_Z - 6, BTN_Z + 6))
        F.sub(cyl("Y", (XC, BTN_Z), 2.75, y1 - 3, y1 + 3), 0.0, bbox=bb(XC - 4, XC + 4, y1 - 3.5, y1 + 2.5, BTN_Z - 4, BTN_Z + 4))
        return F
    return build


# ================= крышка =================

def lid(pre):
    P = BOX[pre]; L = P["L"]

    def build(h):
        y0, y1, ym = YE, YE + L, YE + L / 2
        yl0, yl1 = y0 - 1.6, y1 + 1.6                      # крышка шире корпуса на 1,6 с каждой стороны
        zlb = Z_RIM + 0.15
        F = Field(pre + "_Lid", (XC - HW - 4, YH - 5.5, ZH - 5), (XC + HW + 4, y1 + 9.5, LID_TOP + 1.5), h)

        def solid(X, Y, Z):
            d = i_round(np.abs(X - XC) - (HW + 1.6), np.abs(Y - ym) - (L / 2 + 1.6), R_PLAN + 1.6)
            return i_round(d, Z - LID_TOP, 6.0)
        F.add(solid)
        F.shell(T)
        F.apply(half("Z", zlb, -1), "inter", 0.35, bbox=bb(XC - HW - 4, XC + HW + 4, yl0 - 6, yl1 + 10, zlb - 6, zlb + 1.5))
        # щель выхода ленты
        slot = prism2(rect2(SLOT_X0, SLOT_X1, SLOT_Y0, SLOT_Y1, 3.0), "XY", LID_TOP - 12, LID_TOP + 4)
        F.sub(slot, 0.6, bbox=bb(SLOT_X0 - 2, SLOT_X1 + 2, SLOT_Y0 - 2, SLOT_Y1 + 2, LID_TOP - 8, LID_TOP + 3))
        # вырезы юбки под колена корпуса и колена петли самой крышки
        for a, b, who in HINGE:
            xa, xb = XC + a, XC + b
            if who == "body":
                F.sub(box((xa - 0.3, YH - 4, zlb - 1), (xb + 0.3, y0 + 0.8, ZH + RH + 0.6), 0.3), 0.4,
                      bbox=bb(xa - 1, xb + 1, YH - 5, y0 + 1.5, zlb - 2, ZH + RH + 1.5))
            else:
                F.add(cyl("X", (YH, ZH), RH, xa, xb, rim=0.5), 0.0, bbox=bb(xa - 1, xb + 1, YH - 4, YH + 4, ZH - 4, ZH + 4))
                F.add(box((xa, YH, ZH), (xb, yl0 + 1.0, ZH + RH), 0.7), 0.4, bbox=bb(xa - 1, xb + 1, YH - 1, yl0 + 2, ZH - 1, ZH + RH + 1))
        F.sub(cyl("X", (YH, ZH), 1.8, XC - 53, XC + 53), 0.3, bbox=bb(XC - 53, XC + 53, YH - 3.6, YH + 3.6, ZH - 3.6, ZH + 3.6))
        # колена заслонки на скруглённом плече крышки у правого торца
        for a, b, who in FLAP_SEG:
            if who != "lid":
                continue
            xa, xb = XC + a, XC + b
            F.add(cyl("X", (YF, ZF), RF, xa, xb, rim=0.4), 0.0, bbox=bb(xa - 1, xb + 1, YF - 3, YF + 3, ZF - 3, ZF + 3))
            F.add(box((xa, YF, ZF - 2.6), (xb, yl0 + 1.2, ZF + 2.2), 0.6), 0.4,
                  bbox=bb(xa - 1, xb + 1, YF - 1, yl0 + 2, ZF - 3.5, ZF + 3))
        F.sub(cyl("X", (YF, ZF), 1.4, XC - 47, XC + 47), 0.2, bbox=bb(XC - 47, XC + 47, YF - 3, YF + 3, ZF - 3, ZF + 3))
        # колена петли защёлки на нижней кромке левого торца крышки
        yb = y1 + LATCH_DY
        ear = union2(rect2(y1 + 0.2, yb, LATCH_Z, LATCH_Z + 7.0, 0.8), circle2((yb, LATCH_Z), 3.3))
        for a0, a1 in LATCH_LID_SEG:
            xa, xb = XC + a0, XC + a1
            F.add(prism2(ear, "YZ", xa, xb, rim=0.4), 0.6, bbox=bb(xa - 1, xb + 1, y1 - 0.5, yb + 4, LATCH_Z - 4, LATCH_Z + 8))
        F.sub(cyl("X", (yb, LATCH_Z), 1.4, XC - 48, XC + 48), 0.2, bbox=bb(XC - 48, XC + 48, yb - 2, yb + 2, LATCH_Z - 2, LATCH_Z + 2))
        return F
    return build


def hinge_pin(pre):
    def build(h):
        x0, x1 = XC - 50.2, XC + 49.4
        prof = [(x0, 0.0), (x0, 2.4), (x0 + 1.4, 2.4), (x0 + 1.4, 1.55), (x1 - 0.5, 1.55), (x1, 1.05), (x1, 0.0)]
        return lathe_mesh(prof, seg=32, axis="X", c=(YH, ZH))
    return build


def flap_pin(pre):
    def build(h):
        x0, x1 = XC - 46.6, XC + 46.4
        prof = [(x0, 0.0), (x0, 1.7), (x0 + 1.0, 1.7), (x0 + 1.0, 1.15), (x1 - 0.4, 1.15), (x1, 0.8), (x1, 0.0)]
        return lathe_mesh(prof, seg=24, axis="X", c=(YF, ZF))
    return build


# ================= заслонка выхода ленты =================

def flap(pre):
    def build(h):
        F = Field(pre + "_Flap", (XC - 48, YF - 3.2, ZF - 3.6), (XC + 48, -23.5, -54.3), h)
        # плита следует скруглению плеча крышки (центр дуги (−50,6; −65), радиус 6) с зазором 0,4 и идёт по верху
        pts = [(-57.36, -63.19), (-56.66, -61.5), (-55.55, -60.05), (-54.1, -58.94), (-52.41, -58.24), (-50.6, -58.0), (-25.5, -58.0)]
        F.add(strip(Path2(pts), "YZ", 1.2, XC - 45.0, XC + 45.0, rim=0.4))
        # отбортовка свободной кромки
        F.add(box((XC - 44.6, -27.0, -58.6), (XC + 44.6, -25.4, -56.4), 0.5), 0.4,
              bbox=bb(XC - 45, XC + 45, -28, -24.5, -59, -55.5))
        # оттиск патрона — куда укладывать ленту (NGIC), остриём к дулу
        x0 = XC - 38.0; yc = (SLOT_Y0 + SLOT_Y1) / 2
        top = [(0, 6.2), (34, 6.2), (39, 4.3), (43, 4.0), (58, 3.9), (68, 2.2), (74, 0.0)]
        outline = [(x0 + a, yc + b) for a, b in top] + [(x0 + a, yc - b) for a, b in reversed(top[1:-1])] + [(x0, yc - 6.2)]
        radii = [1.5, 1.5, 1.0, 1.0, 1.0, 1.2, 0.5] + [1.2, 1.0, 1.0, 1.0, 1.5, 1.5]
        poly = Poly(fillet_poly(outline, radii))

        def cart(X, Y, Z):
            return 0.8 * smoothstep(-poly.sd(X, Y) / 0.9) * smoothstep((Z - (-58.2)) / 0.6)
        F.displace(cart, bbox=bb(x0 - 2, x0 + 76, yc - 8, yc + 8, -59, -56), fine=False)
        # колена на оси; у колен крышки в плите вырезы
        for a, b, who in FLAP_SEG:
            xa, xb = XC + a, XC + b
            if who == "flap":
                F.add(cyl("X", (YF, ZF), RF, xa, xb, rim=0.4), 0.0, bbox=bb(xa - 1, xb + 1, YF - 3, YF + 3, ZF - 3, ZF + 3))
            else:
                F.sub(box((xa - 0.4, YF - 3, ZF - 3.4), (xb + 0.4, -55.5, ZF + 3.4), 0.3), 0.3,
                      bbox=bb(xa - 1, xb + 1, YF - 4, -54.5, ZF - 4, ZF + 4))
        F.sub(cyl("X", (YF, ZF), 1.4, XC - 47, XC + 47), 0.2, bbox=bb(XC - 47, XC + 47, YF - 3, YF + 3, ZF - 3, ZF + 3))
        return F
    return build


# ================= защёлка у левого торца: скоба и вертушок =================

def latch(pre):
    y1 = _y1(pre)

    def build(h):
        yb = y1 + LATCH_DY
        LZ = LATCH_Z
        F = Field(pre + "_Latch", (XC - 31, y1 + 1.8, LZ - 93.5), (XC + 31, y1 + 9.6, LZ + 4.5), h)
        # контур скобы (X, Z): широкий верх у петли и язык со скруглённым концом
        outline = union2(rect2(XC - 28.2, XC + 28.2, LZ - 25.0, LZ - 3.4, 3.0),
                         rect2(XC - 22.5, XC + 22.5, LZ - 68.0, LZ - 20.0, 2.0), circle2((XC, LZ - 68.0), 22.5), r=3.0)
        F.add(prism2(outline, "XZ", y1 + 2.8, y1 + 4.0, rim=0.35))
        # отбортовка по контуру (жёсткость): контур за вычетом самого себя, сдвинутого внутрь
        frame = minus2(outline, lambda U, V: outline(U, V) + 1.7, 0.3)
        F.add(prism2(frame, "XZ", y1 + 2.8, y1 + 5.8, rim=0.3), 0.3)
        # колена петли и перемычки к пластине
        for a0, a1 in LATCH_SEG:
            xa, xb = XC + a0, XC + a1
            F.add(cyl("X", (yb, LZ), 2.7, xa, xb, rim=0.4), 0.0, bbox=bb(xa - 1, xb + 1, yb - 3.5, yb + 3.5, LZ - 3.5, LZ + 3.5))
            F.add(box((xa, y1 + 2.8, LZ - 5.5), (xb, yb + 0.6, LZ - 0.5), 0.5), 0.5, bbox=bb(xa - 1, xb + 1, y1 + 2.2, yb + 3, LZ - 7, LZ + 1))
        F.sub(cyl("X", (yb, LZ), 1.45, XC - 31, XC + 31), 0.0, bbox=bb(XC - 31, XC + 31, yb - 2, yb + 2, LZ - 2, LZ + 2))
        # прорезь под вертушок: через неё проходит стержень и (вертикально) пластина
        F.sub(prism2(rect2(XC - 3.75, XC + 3.75, BTN_Z - 9.0, BTN_Z + 15.0, 3.75), "XZ", y1 + 1, y1 + 7), 0.4,
              bbox=bb(XC - 5, XC + 5, y1 + 2.0, y1 + 6.6, BTN_Z - 10, BTN_Z + 16))
        return F
    return build


def latch_pin(pre):
    y1 = _y1(pre)

    def build(h):
        x0, x1 = XC - 48.2, XC + 48.2
        prof = [(x0, 0.0), (x0, 1.9), (x0 + 1.0, 1.9), (x0 + 1.0, 1.2), (x1 - 0.8, 1.2), (x1 - 0.8, 1.9), (x1, 1.9), (x1, 0.0)]
        return lathe_mesh(prof, seg=24, axis="X", c=(y1 + LATCH_DY, LATCH_Z))
    return build


def latch_spring(pre):
    y1 = _y1(pre)

    def build(h):
        return helix_mesh((y1 + LATCH_DY, LATCH_Z), 2.0, 0.45, XC + LATCH_SPRING[0], XC + LATCH_SPRING[1], 1.25)
    return build


def turnbutton(pre):
    y1 = _y1(pre)

    def build(h):
        F = Field(pre + "_Turnbutton", (XC - 9, y1 - 3.2, BTN_Z - 9), (XC + 9, y1 + 7.4, BTN_Z + 9), h)
        F.add(cyl("Y", (XC, BTN_Z), 2.45, y1 - 2.8, y1 + 4.8, rim=0.3))
        F.add(cyl("Y", (XC, BTN_Z), 4.2, y1 - 2.8, y1 - 1.5, rim=0.3), 0.2)
        F.add(prism2(rect2(XC - 8, XC + 8, BTN_Z - 3.0, BTN_Z + 3.0, 3.0), "XZ", y1 + 4.5, y1 + 6.4, rim=0.5), 0.4)
        return F
    return build


# ================= ручка =================

def handle(pre):
    zb = BOX[pre]["zb"]

    def build(h):
        F = Field(pre + "_Handle", (XC - 20.5, -82.0, zb - 1.0), (XC + 20.5, -53.0, -89.0), h)
        pts = [(-58.5, -91.2), (-61.3, -91.2), (-61.3, -96.5), (-56.9, -101.0), (-56.9, -128.0), (-68.0, -132.0),
               (-76.0, -142.0), (-68.0, -152.0), (-56.9, -156.0), (-56.9, zb + 5.0)]
        radii = [1.8, 2.5, 3.0, 4.0, 8.0, 8.0, 8.0, 8.0, 4.0]
        F.add(strip(Path2(fillet_path(pts, radii)), "YZ", 2.0, XC - 18.5, XC + 18.5, rim=0.5))
        # ярлык, пришитый к ремню над петлёй
        F.add(box((XC - 13.0, -58.9, -127.0), (XC + 13.0, -57.7, -118.0), 0.4), 0.3, bbox=bb(XC - 14, XC + 14, -60, -57, -128, -117))
        return F
    return build


# ================= узел крепления на крышке =================

def mount(pre):
    def build(h):
        F = Field(pre + "_Mount", (-176, -27, -60.2), (-10, 27, -47.5), h)
        # основание на крышке (клёпаное), стойка-ползун и Т-образная головка в направляющих кронштейна:
        # полость кронштейна — зазор шеи |Y| < 9 и камера |Y| < 12,2 между BOT − 3,6 и BOT − 1,6 (part_receiver.box_bracket)
        F.add(prism2(rect2(XC - 42, XC + 42, -24, 24, 5.0), "XY", -58.8, -57.6, rim=0.35))
        F.add(box((-172.0, -8.6, -57.8), (-14.0, 8.6, -52.0), 0.6), 0.5, bbox=bb(-173, -13, -9.5, 9.5, -58.5, -51.5))
        F.add(box((-160.0, -11.8, -52.2), (-38.0, 11.8, -50.6), 0.5), 0.3, bbox=bb(-161, -37, -12.5, 12.5, -53, -50))
        # упор сзади (за задним торцом кронштейна)
        F.add(box((-172.0, -10.0, -57.8), (-166.8, 10.0, -49.0), 0.6), 0.4, bbox=bb(-173, -166, -11, 11, -58.5, -48.5))
        # гнездо зуба спереди и отверстия оси в щёчках
        F.sub(box((-33.5, -3.4, -58.5), (-8.0, 3.4, -52.0), 0.3), 0.3, bbox=bb(-34, -7, -4, 4, -59, -51.5))
        F.sub(cyl("Y", (-28.6, -55.2), 1.6, -10, 10), 0.2, bbox=bb(-31, -26, -10, 10, -58, -52))
        # заклёпки основания
        for sx in (-1, 1):
            for sy in (-1, 1):
                cap = inter(sphere((XC + sx * 34.0, sy * 16.0, -58.45), 2.2), half("Z", -57.6, -1))
                F.add(cap, 0.2, bbox=bb(XC + sx * 34 - 3, XC + sx * 34 + 3, sy * 16 - 3, sy * 16 + 3, -58, -55.5))
        return F
    return build


def mount_tooth(pre):
    def build(h):
        F = Field(pre + "_Mount_Tooth", (-33, -9.2, -59.2), (-10.5, 9.2, -48.0), h)
        prof = Poly(fillet_poly([(-31.2, -49.0), (-26.4, -49.0), (-26.4, -54.0), (-12.5, -55.0), (-12.5, -58.2), (-31.2, -58.2)],
                                [0.5, 0.5, 1.2, 0.8, 0.8, 0.8]))
        F.add(prism(prof, "XZ", -3.0, 3.0, rim=0.5))
        F.add(cyl("Y", (-28.6, -55.2), 1.35, -8.7, 8.7, rim=0.3), 0.2)
        return F
    return build


# ================= каталог =================

def parts():
    out = []
    for pre, P in BOX.items():
        c = P["coll"]; hid = P["hidden"]
        y1 = _y1(pre); yb = y1 + LATCH_DY
        common = dict(coll=c)
        if hid:
            common["coll_hidden"] = True
        out += [
            dict(name=pre + "_Body", build=body(pre), h=0.15, mat="Box_paint", adapt=0.1, parent="Box_Bracket", **common),
            dict(name=pre + "_Lid", build=lid(pre), h=0.15, mat="Box_paint", adapt=0.1, parent=pre + "_Body",
                 pivot=[XC, YH, ZH],
                 motion="ось X через (YH, ZH); открытие — поворот на +X до 110° (крышка встаёт вверх и наклоняется к −Y)", **common),
            dict(name=pre + "_Hinge_Pin", build=hinge_pin(pre), h=0.1, mat="Steel_phosphate", parent=pre + "_Body", **common),
            dict(name=pre + "_Flap", build=flap(pre), h=0.1, mat="Box_paint", adapt=0.08, parent=pre + "_Lid",
                 pivot=[XC, YF, ZF], motion="ось X; открытие — поворот на +X до 150°", **common),
            dict(name=pre + "_Flap_Pin", build=flap_pin(pre), h=0.1, mat="Steel_phosphate", parent=pre + "_Lid", **common),
            dict(name=pre + "_Latch", build=latch(pre), h=0.1, mat="Box_paint", adapt=0.08, parent=pre + "_Lid",
                 pivot=[XC, yb, LATCH_Z], motion="ось X; открытие — поворот на +X до 80° (скоба откидывается к +Y)", **common),
            dict(name=pre + "_Latch_Pin", build=latch_pin(pre), h=0.1, mat="Steel_phosphate", parent=pre + "_Lid", **common),
            dict(name=pre + "_Latch_Spring", build=latch_spring(pre), mat="Spring_steel", parent=pre + "_Lid", **common),
            dict(name=pre + "_Turnbutton", build=turnbutton(pre), h=0.08, mat="Steel_phosphate", parent=pre + "_Body",
                 pivot=[XC, y1, BTN_Z], motion="ось Y; замок закрыт — пластина поперёк прорези, открыт — поворот на 90°", **common),
            dict(name=pre + "_Handle", build=handle(pre), h=0.1, mat="Canvas", parent=pre + "_Body", **common),
            dict(name=pre + "_Mount", build=mount(pre), h=0.1, mat="Box_paint", adapt=0.08, parent=pre + "_Lid", **common),
            dict(name=pre + "_Mount_Tooth", build=mount_tooth(pre), h=0.08, mat="Steel_phosphate", parent=pre + "_Mount",
                 pivot=[-28.6, 0.0, -55.2], motion="ось Y; зуб убирается поворотом хвоста вверх (около 20°), пружина (в модели не показана) возвращает",
                 **common),
        ]
    return out
