# ПКП: крышка ствольной коробки (штамповка) с защёлкой, щитками окон приёмника (справа) и выхода ленты (слева).
# Правая сторона — по рендеру владельца 13 (сетка в миллиметрах модели на глубине борта, trace/mm2), левая — по 14.
# Крышка поворачивается на оси у переднего торца коробки (dims.COVER_HINGE) вместе с лотком.
import math

import numpy as np

from dims import *
from sdf import *

HWC = COVER_HW
XR, XF = -363.0, -57.0                     # задний торец; передняя стенка — перед носиками пуль в ленте
TS = SHEET
HX, HZ = COVER_HINGE
# высота верха и «плеча» (нижней кромки скоса) вдоль крышки: задняя часть ниже, передняя — выше
TOP_R, TOP_F = 34.5, 44.5
SH_R, SH_F = 25.0, 38.5
STEP_X0, STEP_X1 = -229.0, -206.0
# окно приёмника (справа) и окно выхода ленты (слева)
FEED_X0, FEED_X1 = -141.0, XF - TS - 0.1    # окно приёмника доходит до передней стенки
FEED_Z1 = 38.5
EXIT_X0, EXIT_X1 = -126.0, -80.0
EXIT_Z0, EXIT_Z1 = 13.5, 37.0


def _ramp(X, x0, x1, a, b):
    t = np.clip((X - x0) / (x1 - x0), 0.0, 1.0)
    return a + (b - a) * t


def outer(X, Y, Z):
    """Наружная форма крышки (сплошное тело): борта, скосы к верху, ступень, задний скос."""
    zt = _ramp(X, STEP_X0, STEP_X1, TOP_R, TOP_F)
    zs = _ramp(X, STEP_X0 - 1.0, STEP_X1 + 2.0, SH_R, SH_F)
    side = np.abs(Y) - HWC
    d = i_round(side, Z - zt, 2.2)
    # скос 45° от плеча к верху
    d = i_round(d, (side + (Z - zs)) * 0.70710678, 2.5)
    # задний торец и задний скос
    d = i_round(d, XR - X, 1.6)
    nx, nz = -0.629, 0.777                 # нормаль заднего скоса: через (−363, 15) и (−339, 34.5)
    d = i_round(d, (X + 363.0) * nx + (Z - 15.0) * nz, 2.0)
    # передний скос верха и передний торец
    d = i_round(d, ((X + 75.0) * 0.287 + (Z - TOP_F) * 0.958), 1.5)
    d = i_round(d, X - XF, 1.2)
    # задние вертикальные углы срезаны
    d = i_round(d, ((XR + 5.0 - X) + (np.abs(Y) - HWC)) * 0.70710678, 1.5)
    return d


def cover(h):
    F = Field("Top_Cover", (XR - 1.5, -HWC - 3.0, -2.5), (HX + 9.0, HWC + 3.0, TOP_F + 2.0), h)
    F.add(outer)
    # выштамповки-рёбра жёсткости на бортах: вдоль задней части и наклонно к передней
    rib = Path2(fillet_path([(-328.0, 12.0), (-230.0, 12.0), (-175.0, 28.5)], [10.0]))

    def bead(X, Y, Z):
        d2 = rib.dist(X, Z)
        return 1.1 * smoothstep((1.9 - d2) / 1.5) * smoothstep((np.abs(Y) - (HWC - 5.0)) / 2.0)
    F.displace(bead, bbox=bb(-332, -171, -HWC - 2, HWC + 2, 8, 32), fine=False)
    # выштамповка-площадка на верху передней части
    top_pad = rect2(-187.0, -78.0, -11.0, 11.0, 3.0)

    def pad(X, Y, Z):
        return 1.0 * smoothstep(-top_pad(X, Y) / 1.6) * smoothstep((Z - (TOP_F - 4.0)) / 2.0)
    F.displace(pad, bbox=bb(-190, -75, -13, 13, TOP_F - 3, TOP_F + 2), fine=False)
    # название (вымышленное) — штампом на площадке
    name, wn = text2(MARK_NAME, font_path(True), 5.2, track=0.55)
    engrave(F, name, "XY", (-171.0, -2.6), 1, TOP_F + 1.0, 1, depth=0.32, wall=0.28,
            bbox=bb(-173, -169 + wn, -5, 5, TOP_F - 0.4, TOP_F + 2.0))
    F.shell(TS)
    # низ открыт: кромка бортов — по линии разъёма, спереди справа и слева поднимается к окнам
    F.sub(box((XR + TS, -HWC + TS, -6.0), (XF - TS, HWC - TS, 4.0)), 0.0, bbox=bb(XR, XF, -HWC, HWC, -3, 5))
    F.apply(half("Z", RECV_TOP + 0.15, -1), "inter", 0.35)
    # правый борт: нижняя кромка уходит вверх к окну приёмника
    low_r = Poly(fillet_poly([(-222.0, -4.0), (-153.0, 24.0), (-150.0, 33.0), (FEED_X0, 33.0), (FEED_X0, FEED_Z1), (FEED_X1, FEED_Z1),
                              (FEED_X1 + 2.0, -4.0)], [0, 3.0, 1.5, 1.0, 1.5, 1.5, 0]))
    F.sub(prism(low_r, "XZ", -HWC - 3, -HWC + 6), 0.35, bbox=bb(-224, FEED_X1 + 3, -HWC - 2, -HWC + 5, -3, FEED_Z1 + 2))
    # левый борт: окно выхода ленты и подрезка кромки у оси
    F.sub(box_e((EXIT_X0, HWC - 6, EXIT_Z0), (EXIT_X1, HWC + 3, EXIT_Z1), ry=2.0), 0.35,
          bbox=bb(EXIT_X0 - 1, EXIT_X1 + 1, HWC - 5, HWC + 2, EXIT_Z0 - 1, EXIT_Z1 + 1))
    # щёки оси спереди: вниз к оси крышки
    # передняя стенка между щеками — только выше оси: иначе при открывании её низ пошёл бы назад, на носики пуль
    F.sub(box((XF - 4.0, -14.8, -5.0), (XF + 3.0, 14.8, HZ - 4.0), 0.0), 0.4, bbox=bb(XF - 3, XF + 1, -16, 16, -3, HZ - 2))
    F.sub(box((XF - TS - 0.25, -HWC - 3, -5.0), (XF + 3.0, HWC + 3, HZ - 7.4), 0.0), 0.3,
          bbox=bb(XF - 3, XF + 1, -HWC - 2, HWC + 2, -3, HZ - 6))
    cheek = union2(rect2(XF - 1.5, HX, HZ - 7.2, 39.5, 1.0), circle2((HX, HZ), 7.2), r=0.0)
    for s in (-1, 1):
        y0, y1 = sorted((s * 15.0, s * (HWC - 0.2)))
        F.add(prism2(cheek, "XZ", y0, y1, rim=0.5), 0.6, bbox=bb(XF - 3, HX + 8.5, y0 - 1, y1 + 1, HZ - 8, 41))
    F.sub(cyl("Y", (HX, HZ), 2.55, -HWC - 3, HWC + 3), 0.2, bbox=bb(HX - 4, HX + 4, -HWC - 2, HWC + 2, HZ - 4, HZ + 4))
    # бобышка оси защёлки на борту сзади
    for s in (-1, 1):
        F.add(cyl("Y", (-350.5, 13.0), 3.7, s * (HWC - 0.3), s * (HWC + 1.5), rim=0.6), 0.3,
              bbox=bb(-356, -345, s * HWC - 2.5, s * HWC + 2.5, 8, 18))
    return F


def cover_latch(h):
    """Защёлка крышки: рифлёная клавиша на заднем скосе."""
    F = Field("Cover_Latch", (-362, -8, 15), (-342, 8, 32), h)
    nx, nz = -0.629, 0.777
    c = (-352.0, 24.3)

    def key(X, Y, Z):
        u = (X - c[0]) * nz - (Z - c[1]) * nx          # вдоль скоса
        v = (X - c[0]) * nx + (Z - c[1]) * nz          # от скоса наружу
        q1 = np.abs(u) - 5.0; q2 = np.abs(Y) - 5.5
        base = i_round(np.maximum(q1, q2), np.abs(v - 0.6) - 1.4, 0.5)
        return base - 0.35 * (np.cos(u * 2 * math.pi / 1.4) * 0.5 + 0.5) * smoothstep((v - 1.2) / 0.5)
    F.add(key)
    return F


def feed_flap(h):
    """Щиток окна приёмника (справа): пластина на оси вдоль верхней кромки окна; с лентой — поднят горизонтально."""
    F = Field("Feed_Flap", (FEED_X0 - 3, -HWC - 35, FEED_Z1 - 3), (FEED_X1 + 3, -HWC + 1, FEED_Z1 + 5), h)
    zc = FEED_Z1 + 1.6
    yc = -HWC - 2.4
    F.add(box((FEED_X0 + 0.5, yc - 30.0, zc - 0.6), (FEED_X1 - 0.5, yc + 0.5, zc + 0.6), 0.4))
    # отбортовка свободной кромки
    F.add(box((FEED_X0 + 0.5, yc - 30.6, zc - 3.6), (FEED_X1 - 0.5, yc - 29.4, zc + 0.6), 0.4), 0.8)
    F.add(cyl("X", (yc, zc), 1.2, FEED_X0 - 2.0, FEED_X1 + 2.0, rim=0.4), 0.0)
    for xa, xb in ((FEED_X0 + 2, FEED_X0 + 14), (FEED_X1 - 14, FEED_X1 - 2)):
        F.add(cyl("X", (yc, zc), 2.2, xa, xb, rim=0.4), 0.5, bbox=bb(xa - 1, xb + 1, yc - 3, yc + 3, zc - 3, zc + 3))
    return F


def exit_flap(h):
    """Щиток окна выхода ленты (слева): на оси по нижней кромке окна; открыт — откинут вниз-наружу."""
    F = Field("Exit_Flap", (EXIT_X0 - 3, HWC - 1, EXIT_Z0 - 4), (EXIT_X1 + 3, HWC + 29, EXIT_Z0 + 4), h)
    zc = EXIT_Z0 - 1.2
    yc = HWC + 2.4
    F.add(box((EXIT_X0 + 0.5, yc - 0.5, zc - 0.6), (EXIT_X1 - 0.5, yc + 24.5, zc + 0.6), 0.4))
    F.add(cyl("X", (yc, zc), 1.2, EXIT_X0 - 2.0, EXIT_X1 + 2.0, rim=0.4), 0.0)
    for xa, xb in ((EXIT_X0 + 2, EXIT_X0 + 12), (EXIT_X1 - 12, EXIT_X1 - 2)):
        F.add(cyl("X", (yc, zc), 2.2, xa, xb, rim=0.4), 0.5, bbox=bb(xa - 1, xb + 1, yc - 3, yc + 3, zc - 3, zc + 3))
    return F


def parts():
    return [
        dict(name="Top_Cover", build=cover, h=0.15, coll="Крышка", mat="Steel_blued", adapt=0.1, pivot=[HX, 0.0, HZ]),
        dict(name="Cover_Latch", build=cover_latch, h=0.08, coll="Крышка", mat="Steel_phosphate", parent="Top_Cover"),
        dict(name="Feed_Flap", build=feed_flap, h=0.1, coll="Крышка", mat="Steel_blued", parent="Top_Cover",
             pivot=[(FEED_X0 + FEED_X1) / 2, -HWC - 2.4, FEED_Z1 + 1.6]),
        dict(name="Exit_Flap", build=exit_flap, h=0.1, coll="Крышка", mat="Steel_blued", parent="Top_Cover",
             pivot=[(EXIT_X0 + EXIT_X1) / 2, HWC + 2.4, EXIT_Z0 - 1.2]),
    ]
