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
# защёлка крышки на заднем скосе
SLOPE_N = (-0.629, 0.777)                 # нормаль заднего скоса: через (−363, 15) и (−339, 34.5)
LATCH_C = (-352.0, 24.3)                  # середина клавиши (образец 13: выступ на скосе у X −360 … −352)
LATCH_AXIS = (-350.5, 13.0)               # ось защёлки — по бобышкам на бортах
KEY_HU, KEY_HY = 5.0, 5.5                 # полуразмеры клавиши вдоль скоса и поперёк
WIN_U = (-5.7, 8.4)                       # окно в скосе вдоль него от середины клавиши: впереди клавиши — её ход
WIN_HY = 6.2
CATCH = (-350.6, 3.4)                     # перекладина на ствольной коробке, за которую держится крюк
CATCH_R = 1.5
HOOK_X = -354.6                           # низ плеча с крюком: позади перекладины
# петли щитков (владелец 2026-11-14: щитки «висят в воздухе» — ось держалась только в коленах самого щитка):
# ось щитка, колена щитка у концов окна, между ними — колено крышки на перемычке к листу (справа — к скосу над
# окном, слева — к борту под окном); FLAP_KN — длина колена щитка, FLAP_GAP — зазор между коленами
FEED_AX = (-HWC - 2.4, FEED_Z1 + 1.6)
EXIT_AX = (HWC + 2.4, EXIT_Z0 - 1.2)
FEED_KN, EXIT_KN, FLAP_GAP = 12.0, 10.0, 0.4
FEED_FOOT = (-22.85, 39.37)              # перемычка: на скосе 45° над окном, на 0,2 мм в листе (не выходит внутрь)
EXIT_FOOT = (HWC - 0.1, EXIT_Z0 - 2.7)   # перемычка: на борту под окном (внутрь крышки не выходит — там лоток)


def _ramp(X, x0, x1, a, b):
    t = np.clip((X - x0) / (x1 - x0), 0.0, 1.0)
    return a + (b - a) * t


def _slope(X, Z):
    """Координаты заднего скоса у защёлки: вдоль скоса вперёд-вверх и от скоса наружу."""
    nx, nz = SLOPE_N
    return (X - LATCH_C[0]) * nz - (Z - LATCH_C[1]) * nx, (X - LATCH_C[0]) * nx + (Z - LATCH_C[1]) * nz


def latch_window(X, Y, Z):
    """Окно защёлки в заднем скосе: прямоугольник со скруглёнными углами, насквозь через лист."""
    u, v = _slope(X, Z)
    r = 1.0
    q1 = np.abs(u - (WIN_U[0] + WIN_U[1]) / 2) - ((WIN_U[1] - WIN_U[0]) / 2 - r)
    q2 = np.abs(Y) - (WIN_HY - r)
    d2 = np.hypot(np.maximum(q1, 0), np.maximum(q2, 0)) + np.minimum(np.maximum(q1, q2), 0) - r
    return np.maximum(d2, np.abs(v) - 4.0)


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
    F = Field("Top_Cover", (XR - 1.5, -HWC - 5.5, -2.5), (HX + 9.0, HWC + 5.5, TOP_F + 2.0), h)
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
    # окно защёлки: клавиша ходит в нём вперёд и утапливается под лист
    F.sub(latch_window, 0.3, bbox=bb(-361.5, -342.0, -7.6, 7.6, 15.5, 34.4))
    # колена петель щитков на крышке: между коленами щитка, перемычкой к листу, с отверстием под ось щитка
    for (yc, zc), (x0, x1), kn, foot in ((FEED_AX, (FEED_X0, FEED_X1), FEED_KN, FEED_FOOT),
                                         (EXIT_AX, (EXIT_X0, EXIT_X1), EXIT_KN, EXIT_FOOT)):
        xa, xb = x0 + 2.0 + kn + FLAP_GAP, x1 - 2.0 - kn - FLAP_GAP
        ylo, yhi = min(yc, foot[0]) - 3.0, max(yc, foot[0]) + 3.0
        zlo, zhi = min(zc, foot[1]) - 3.0, max(zc, foot[1]) + 3.0
        F.add(cyl("X", (yc, zc), 2.2, xa, xb, rim=0.4), 0.3, bbox=bb(xa - 1, xb + 1, yc - 3, yc + 3, zc - 3, zc + 3))
        F.add(prism2(seg2((yc, zc), foot, 1.3), "YZ", xa, xb, rim=0.4), 0.6, bbox=bb(xa - 1, xb + 1, ylo, yhi, zlo, zhi))
        F.sub(cyl("X", (yc, zc), 1.35, xa - 1.0, xb + 1.0), 0.15, bbox=bb(xa - 2, xb + 2, yc - 2, yc + 2, zc - 2, zc + 2))
    return F


def cover_latch(h):
    """Защёлка крышки — двуплечий рычаг на оси у задних бобышек (у настоящего ПКП так же: фото B03/14, образец 13).
    Клавиша с рифлением выходит в окно заднего скоса, крюк внизу держится за перекладину на ствольной коробке
    (Cover_Catch). Клавишу толкают вперёд: она идёт по окну и утапливается, крюк отходит назад из-под перекладины
    (угол — part_rig.LATCH_DEG)."""
    ax, az = LATCH_AXIS
    nx, nz = SLOPE_N
    F = Field("Cover_Latch", (-361.5, -6.6, -0.8), (-343.0, 6.6, 30.8), h)
    F.add(cyl("Y", (ax, az), 3.3, -4.2, 4.2, rim=0.6))
    # плечо к клавише и сама клавиша
    kb = (LATCH_C[0] - 2.2 * nx, LATCH_C[1] - 2.2 * nz)
    F.add(prism2(seg2((ax, az), kb, 2.0), "XZ", -3.2, 3.2, rim=0.6), 0.8)

    def key(X, Y, Z):
        u, v = _slope(X, Z)
        q1 = np.abs(u) - KEY_HU; q2 = np.abs(Y) - KEY_HY
        base = i_round(i_round(q1, q2, 0.8), np.abs(v + 0.6) - 2.6, 0.5)
        return base - 0.35 * (np.cos(u * 2 * math.pi / 1.4) * 0.5 + 0.5) * smoothstep((v - 1.2) / 0.5)
    F.add(key, 0.6, bbox=bb(-359.5, -344.5, -6.6, 6.6, 17.0, 30.8))
    # плечо с крюком: зуб смотрит вперёд и заходит под перекладину
    F.add(prism2(seg2((ax, az), (HOOK_X, 2.2), 1.7), "XZ", -3.0, 3.0, rim=0.5), 0.8)
    F.add(box((HOOK_X - 1.0, -3.0, 0.2), (CATCH[0] + 0.6, 3.0, CATCH[1] - CATCH_R - 0.25), 0.5), 0.6,
          bbox=bb(HOOK_X - 2.5, CATCH[0] + 1.6, -4, 4, -0.5, 4.5))
    # отверстие под ось
    F.sub(cyl("Y", (ax, az), 1.55, -7, 7), 0.25, bbox=bb(ax - 2.5, ax + 2.5, -5, 5, az - 2.5, az + 2.5))
    return F


def latch_pin(h):
    """Ось защёлки: стержень между бортами крышки (снаружи на бортах — бобышки)."""
    ax, az = LATCH_AXIS
    yw = HWC - TS - 0.15
    F = Field("Cover_Latch_Pin", (ax - 2.5, -yw - 0.5, az - 2.5), (ax + 2.5, yw + 0.5, az + 2.5), h)
    F.add(cyl("Y", (ax, az), 1.45, -yw, yw, rim=0.3))
    return F


def cover_catch(h):
    """Перекладина защёлки на заднем блоке ствольной коробки: пруток в двух ушках, под него заходит зуб крюка."""
    cx, cz = CATCH
    F = Field("Cover_Catch", (cx - 4.2, -8.6, -2.2), (cx + 4.2, 8.6, cz + 3.6), h)
    ear = Poly(fillet_poly([(cx - 2.6, -1.6), (cx + 2.6, -1.6), (cx + 2.6, cz + 2.4), (cx - 2.6, cz + 2.4)], [0, 0, 2.2, 2.2]))
    for s in (-1, 1):
        y0, y1 = sorted((s * 4.6, s * 7.4))
        F.add(prism(ear, "XZ", y0, y1, rim=0.5), 0.0, bbox=bb(cx - 4, cx + 4, y0 - 1, y1 + 1, -2.2, cz + 3.4))
    F.add(cyl("Y", (cx, cz), CATCH_R, -7.9, 7.9, rim=0.35), 0.3)
    return F


def feed_flap(h):
    """Щиток окна приёмника (справа): пластина на оси вдоль верхней кромки окна; с лентой — поднят горизонтально."""
    F = Field("Feed_Flap", (FEED_X0 - 3, -HWC - 35, FEED_Z1 - 3), (FEED_X1 + 3, -HWC + 1, FEED_Z1 + 5), h)
    yc, zc = FEED_AX
    kn = FEED_KN
    F.add(box((FEED_X0 + 0.5, yc - 30.0, zc - 0.6), (FEED_X1 - 0.5, yc + 0.5, zc + 0.6), 0.4))
    # отбортовка свободной кромки
    F.add(box((FEED_X0 + 0.5, yc - 30.6, zc - 3.6), (FEED_X1 - 0.5, yc - 29.4, zc + 0.6), 0.4), 0.8)
    for xa, xb in ((FEED_X0 + 2, FEED_X0 + 2 + kn), (FEED_X1 - 2 - kn, FEED_X1 - 2)):
        F.add(cyl("X", (yc, zc), 2.2, xa, xb, rim=0.4), 0.5, bbox=bb(xa - 1, xb + 1, yc - 3, yc + 3, zc - 3, zc + 3))
    # вырез пластины у оси между коленами щитка — там колено крышки
    xa, xb = FEED_X0 + 2 + kn + 0.2, FEED_X1 - 2 - kn - 0.2
    F.sub(box((xa, yc - 2.95, zc - 1.5), (xb, yc + 1.5, zc + 1.5), 0.0), 0.3, bbox=bb(xa - 1, xb + 1, yc - 4, yc + 2.5, zc - 2.5, zc + 2.5))
    F.add(cyl("X", (yc, zc), 1.2, FEED_X0 - 2.0, FEED_X1 + 2.0, rim=0.4), 0.0)
    return F


def exit_flap(h):
    """Щиток окна выхода ленты (слева): на оси по нижней кромке окна; открыт — откинут вниз-наружу."""
    F = Field("Exit_Flap", (EXIT_X0 - 3, HWC - 1, EXIT_Z0 - 4), (EXIT_X1 + 3, HWC + 29, EXIT_Z0 + 4), h)
    yc, zc = EXIT_AX
    kn = EXIT_KN
    F.add(box((EXIT_X0 + 0.5, yc - 0.5, zc - 0.6), (EXIT_X1 - 0.5, yc + 24.5, zc + 0.6), 0.4))
    for xa, xb in ((EXIT_X0 + 2, EXIT_X0 + 2 + kn), (EXIT_X1 - 2 - kn, EXIT_X1 - 2)):
        F.add(cyl("X", (yc, zc), 2.2, xa, xb, rim=0.4), 0.5, bbox=bb(xa - 1, xb + 1, yc - 3, yc + 3, zc - 3, zc + 3))
    # вырез пластины у оси между коленами щитка — там колено крышки
    xa, xb = EXIT_X0 + 2 + kn + 0.2, EXIT_X1 - 2 - kn - 0.2
    F.sub(box((xa, yc - 1.5, zc - 1.5), (xb, yc + 2.95, zc + 1.5), 0.0), 0.3, bbox=bb(xa - 1, xb + 1, yc - 2.5, yc + 4, zc - 2.5, zc + 2.5))
    F.add(cyl("X", (yc, zc), 1.2, EXIT_X0 - 2.0, EXIT_X1 + 2.0, rim=0.4), 0.0)
    return F


def parts():
    return [
        dict(name="Top_Cover", build=cover, h=0.15, coll="Крышка", mat="Steel_blued", adapt=0.1, pivot=[HX, 0.0, HZ]),
        dict(name="Cover_Latch", build=cover_latch, h=0.08, coll="Крышка", mat="Steel_phosphate", parent="Top_Cover",
             pivot=[LATCH_AXIS[0], 0.0, LATCH_AXIS[1]]),      # качается на оси Y; нажата — part_rig.LATCH_DEG
        dict(name="Cover_Latch_Pin", build=latch_pin, h=0.08, coll="Крышка", mat="Steel_phosphate", parent="Top_Cover"),
        dict(name="Cover_Catch", build=cover_catch, h=0.08, coll="Ствольная коробка", mat="Steel_blued", parent="Receiver"),
        dict(name="Feed_Flap", build=feed_flap, h=0.1, coll="Крышка", mat="Steel_blued", parent="Top_Cover",
             pivot=[(FEED_X0 + FEED_X1) / 2, FEED_AX[0], FEED_AX[1]]),
        dict(name="Exit_Flap", build=exit_flap, h=0.1, coll="Крышка", mat="Steel_blued", parent="Top_Cover",
             pivot=[(EXIT_X0 + EXIT_X1) / 2, EXIT_AX[0], EXIT_AX[1]]),
    ]
