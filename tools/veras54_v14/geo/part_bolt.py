# ВЕРАС-54 v14: затворная рама с рукояткой взведения и направляющая возвратной пружины.
# Рама — фрезерованная деталь АК: нижние полозья под направляющие коробки, правый бок со ступенькой и скосом к верху
# (видны в вырезе крышки), горб над каналом возвратной пружины, стойка вверх-вперёд к штоку поршня, снизу —
# гнездо хвостовика затвора, фигурный паз ведущего выступа, паз выбрасывателя, вырез под курок, паз отражателя.
# Места сняты с плиток образца с сеткой в мм (ref_tiles.py → trace/bolt): правый бок — r_mid.png, r_front.png,
# r_handle.png (R_x-0.09_z0.265, R_x0.02_z0.265); рукоятка сверху и снизу — t_handle.png, u_handle.png
# (T_x0.02, U_x0.02); объём — ракурсы P01, P02 (p01_zoom, p02_zoom). Упор направляющей — по фото АК-12 3-37.
# Затвор, выбрасыватель и шток с поршнем — из v13 (transfer.py); рама обходит их по срезам сетки v13 (trace/bolt/sect.py).
import math

import numpy as np

from dims import *
from sdf import *

# ---------------- рама: продольные места ----------------
BC_X0 = 140.0                     # задний торец рамы (v13: 140)
BC_X1 = 240.3                     # передний торец боковин: колодка крышки с X 240,7 (проход ±13 до Z 33,4)
BC_LOW_X1 = 227.7                 # нижняя часть (полозья, гнездо затвора) кончается перед вкладышем ствола (X 228)
BC_STEP_X = 198.0                 # ступенька правого бока (r_mid: светлая грань X 197…198,7)
BC_STEP_D = 1.1                   # передний участок выступает на 1 мм (P02: видна грань ступеньки сзади; оценка)
STEM_X1 = 249.85                  # передний торец штока рамы: дальше — поршень v13 (X 250, r 5,6)
STEM_R = 5.75                     # шток: низ 21,25 над пружиной (верх 21,1), верх 32,75 под проходом колодки (33,4)

# ---------------- сечение рамы (Y, Z) ----------------
LIP_Z0, LIP_Z1 = -1.6, 0.9        # полозья под направляющими коробки (направляющие Z 1,3…3,1 со скруглением 0,3)
GROOVE_Z1 = 3.5
LIP_HW = 15.2                     # полуширина по полозьям (коробка изнутри ±15,5)
GROOVE_L, GROOVE_R = 12.6, -13.7  # дно пазов: левая направляющая до Y 12,9, правая до −14,1 — зазор 0,3…0,4
FACE_R = CARRIER_FACE_Y           # правая грань переднего участка (видна в вырезе крышки)
FACE_L = 14.6
FACE_TOP = 15.0                   # верхняя кромка грани (r_mid: светлая линия на Z 14,6…15,3)
BEVEL_Y, BEVEL_Z = 12.3, 17.4     # скос к верху (P02: светлая полоса под кромкой выреза крышки; r_mid: тёмная Z 15,3…17,5)
HUMP_Z = 24.6                     # верх горба над каналом пружины (свод крышки свободен на ±15,5 до Z 24)
SPRING_Z = 15.5                   # ось возвратной пружины (v13)
CHAN_R = 5.95                     # канал пружины: пружина v13 r 5,6
# стойка штока: подъём горба к штоку
RISE_X, RISE_DEG = 191.2, 32.0    # оценка: подъём (образец раму не показывает); плоскость начинается под верхом горба —
RISE_Z = HUMP_Z - 3.0             # на горб она выходит у X ≈ 196 без складки галтели

# ---------------- затвор v13 (срезы trace/bolt/sect1.png) ----------------
TAIL_R = 6.6                      # хвостовик затвора r 6,2
TAIL_X0 = 156.5                   # торец гнезда: ударник затвора с X 157
HEAD_R, HEAD_X0 = 8.75, 212.4     # корпус затвора r 8,3 с X 213
LUGS_R, LUGS_X0 = 11.6, 231.2     # боевые упоры r 11,2 с X 232
# ведущий выступ затвора: X 205…214,5, Y −6,6…−13,5, Z −0,9…5,2 (наклонён) — фигурный паз снизу справа
CAM_Z1 = 5.9
EXTR = (220.6, -9.7, -5.0, 2.9)   # паз выбрасывателя (выбрасыватель X 221,6…240,3, Y −9,05…−5,5, Z ±2,2)
HAMMER = (BC_X0 - 2.0, 156.6, 4.6, 2.6)   # вырез под курок снизу сзади: X0, X1, полуширина, верх Z
EJECT = (163.0, 8.3, 10.7, 1.8)   # паз отражателя слева снизу: от X, Y0, Y1, верх Z (оценка, по АК)

SERIAL = "0547"                   # вымышленный номер


def _section():
    pts = [(-LIP_HW, LIP_Z0), (-LIP_HW, LIP_Z1), (GROOVE_R, LIP_Z1), (GROOVE_R, GROOVE_Z1), (FACE_R, GROOVE_Z1),
           (FACE_R, FACE_TOP), (-BEVEL_Y, BEVEL_Z), (-10.8, 21.6), (-3.8, HUMP_Z), (3.8, HUMP_Z), (10.8, 21.6),
           (BEVEL_Y, BEVEL_Z), (FACE_L, FACE_TOP), (FACE_L, GROOVE_Z1), (GROOVE_L, GROOVE_Z1), (GROOVE_L, LIP_Z1),
           (LIP_HW, LIP_Z1), (LIP_HW, LIP_Z0)]
    rad = [0.5, 0.3, 0.25, 0.25, 0.3, 0.7, 0.9, 3.0, 4.5, 4.5, 3.0, 0.9, 0.7, 0.3, 0.25, 0.25, 0.3, 0.5]
    return Poly(fillet_poly(pts, rad, seg=10))


def _side():
    """Профиль сбоку (X, Z): нижняя часть кончается перед вкладышем ствола, впереди — боковины над ним."""
    pts = [(BC_X0, LIP_Z0), (BC_LOW_X1, LIP_Z0), (BC_LOW_X1, 4.45), (BC_X1, 4.45), (BC_X1, 40.0), (BC_X0, 40.0)]
    rad = [0.0, 0.6, 0.7, 0.0, 0.0, 0.0]
    return Poly(fillet_poly(pts, rad, seg=8))


SEC = _section()
SIDE = _side()


def _post(X, Y, Z):
    """Стойка штока: сечение «замочная скважина» (шток r STEM_R над перемычкой), сзади срезана подъёмом."""
    d = np.hypot(Y, Z - GAS_AXIS_Z) - STEM_R
    d = np.minimum(d, np.maximum(np.abs(Y) - STEM_R, np.maximum(14.0 - Z, Z - GAS_AXIS_Z)))
    t = math.tan(math.radians(RISE_DEG))
    rise = ((Z - RISE_Z) - (X - RISE_X) * t) / math.hypot(1.0, t)
    d = i_round(d, rise, 3.5)
    return d


def carrier(h):
    F = Field("Bolt_Carrier", (BC_X0 - 1.5, -LIP_HW - 1.5, LIP_Z0 - 1.5), (STEM_X1 + 1.0, LIP_HW + 1.5, GAS_AXIS_Z + STEM_R + 1.5), h)
    # 1. тело: сечение вдоль X, срезанное профилем сбоку
    F.add(inter(prism(SEC, "YZ", BC_X0, BC_X1, rim=0.8), prism(SIDE, "XZ", -20.0, 20.0), r=0.5))
    # 2. стойка и шток к поршню (галтель к горбу)
    F.add(_post, 2.8, bbox=bb(RISE_X - 4, BC_X1 + 0.5, -9, 9, 14, GAS_AXIS_Z + STEM_R + 1))
    # передний торец — одной плоскостью после галтели (галтель двух тел с общим торцом вспучивает его)
    F.apply(half("X", BC_X1, 1), "inter", 0.6, bbox=bb(BC_X1 - 3, BC_X1 + 3, -LIP_HW - 1, LIP_HW + 1, 3.0, GAS_AXIS_Z + STEM_R + 1))
    F.add(cyl("X", (0.0, GAS_AXIS_Z), STEM_R, BC_X1 - 2.0, STEM_X1, rim=0.0, rim1=0.6), 0.8,
          bbox=bb(BC_X1 - 3, STEM_X1 + 1, -STEM_R - 1, STEM_R + 1, GAS_AXIS_Z - STEM_R - 1, GAS_AXIS_Z + STEM_R + 1))
    # 3. ступенька правого бока: задний участок утоплен, переход — скос 45°
    sx = BC_STEP_X
    yb = FACE_R + BC_STEP_D
    step = Poly([(BC_X0 - 5, yb), (sx - 0.5, yb), (sx + BC_STEP_D - 0.5, FACE_R - 0.6), (sx + BC_STEP_D - 0.5, -25.0), (BC_X0 - 5, -25.0)])
    # низ выреза — посреди паза направляющей (в воздухе): иначе плоскость совпадает с верхом полоза
    F.sub(prism(step, "XY", 2.2, 22.0), 0.35, bbox=bb(BC_X0 - 1, sx + 2.5, FACE_R - 1, yb + 1, 1.5, 19.0))
    # 4. канал возвратной пружины — насквозь: пружина стоит, рама проходит по ней весь ход
    F.sub(cyl("X", (0.0, SPRING_Z), CHAN_R, BC_X0 - 3, BC_X1 + 2.0), 0.6,
          bbox=bb(BC_X0 - 2, BC_X1 + 2, -CHAN_R - 1.5, CHAN_R + 1.5, SPRING_Z - CHAN_R - 1.5, SPRING_Z + CHAN_R + 1.5))
    # 5. гнездо затвора: хвостовик, корпус, боевые упоры; спереди гнездо сливается с каналом (рама открыта снизу)
    F.sub(cyl("X", (0.0, 0.0), TAIL_R, TAIL_X0, HEAD_X0 + 1.0, rim=0.5, rim1=0.0), 0.4,
          bbox=bb(TAIL_X0 - 1, HEAD_X0 + 1.5, -TAIL_R - 1, TAIL_R + 1, -TAIL_R - 1, TAIL_R + 1))
    F.sub(cyl("X", (0.0, 0.0), HEAD_R, HEAD_X0, BC_X1 + 3, rim=0.4, rim1=0.0), 0.4,
          bbox=bb(HEAD_X0 - 1, BC_X1 + 2, -HEAD_R - 1, HEAD_R + 1, -HEAD_R - 1, HEAD_R + 1))
    F.sub(cyl("X", (0.0, 0.0), LUGS_R, LUGS_X0, BC_X1 + 3, rim=0.5, rim1=0.0), 0.4,
          bbox=bb(LUGS_X0 - 1, BC_X1 + 2, -LUGS_R - 1, LUGS_R + 1, -LUGS_R - 1, LUGS_R + 1))
    F.sub(box((HEAD_X0, -6.0, -2.0), (BC_X1 + 3, 6.0, SPRING_Z)), 0.5,
          bbox=bb(HEAD_X0 - 1, BC_X1 + 2, -7, 7, -3, SPRING_Z + 1))
    # 6. фигурный паз ведущего выступа (снизу справа): прямой участок у выступа и наклонный назад-внутрь
    cam = Poly(fillet_poly([(215.0, -14.0), (215.0, -6.0), (209.0, -6.0), (199.0, -1.5), (195.5, -4.5), (204.3, -9.0),
                            (204.3, -14.0)], [0.8, 1.0, 2.0, 1.5, 1.5, 2.0, 0.8]))
    F.sub(prism(cam, "XY", LIP_Z0 - 3, CAM_Z1, rim=0.0, rim1=0.8), 0.35, bbox=bb(194, 216, -15, 0, LIP_Z0 - 1, CAM_Z1 + 1))
    # 7. паз выбрасывателя
    ex0, ey0, ey1, ez = EXTR
    F.sub(box_e((ex0, ey0, -ez), (BC_X1 + 3, ey1, ez), rx=0.8, rz=0.6), 0.3, bbox=bb(ex0 - 1, BC_X1 + 2, ey0 - 1, ey1 + 1, -ez - 1, ez + 1))
    # 8. вырез под курок снизу сзади, паз отражателя слева снизу
    hx0, hx1, hhw, hz = HAMMER
    F.sub(box_e((hx0, -hhw, LIP_Z0 - 3), (hx1, hhw, hz), rx=1.2, rz=1.0), 0.4, bbox=bb(hx0, hx1 + 1, -hhw - 1, hhw + 1, LIP_Z0 - 1, hz + 1))
    ejx, ejy0, ejy1, ejz = EJECT
    F.sub(box_e((ejx, ejy0, LIP_Z0 - 3), (BC_LOW_X1 + 3, ejy1, ejz), rx=0.8, rz=0.6), 0.35,
          bbox=bb(ejx - 1, BC_LOW_X1 + 1, ejy0 - 1, ejy1 + 1, LIP_Z0 - 1, ejz + 1))
    # 9. фрезерованная выборка на левом боку (облегчение, как у рам АК)
    lp = Poly(fillet_poly([(152.0, 6.0), (219.0, 6.0), (219.0, 12.6), (152.0, 12.6)], 2.0))
    F.sub(prism(lp, "XZ", FACE_L - 0.7, FACE_L + 2.0, rim=0.0), 0.4, bbox=bb(150, 221, FACE_L - 1.5, FACE_L + 1.5, 4.5, 14.5))
    # 10. номер на правой грани переднего участка
    f2, w = text2(SERIAL, font_path(True), 2.4, track=0.25)
    ox, oz = 206.0, 8.0
    engrave(F, f2, "XZ", (ox, oz), 1, FACE_R, -1, depth=0.18, wall=0.18, bbox=bb(ox - 1, ox + w + 1, FACE_R - 1, FACE_R + 1.2, oz - 1, oz + 3.4))
    return F


# ---------------- рукоятка взведения ----------------
# средняя линия (X, Y) — снята сверху и снизу (t_handle, u_handle), длина по Y сжата 0,883 до конца на CH_TIP_Y,
# по X сдвинута так, чтобы середина рукоятки стояла на CH_X (место хвата v13)
_SAMPLE = [(-14.6, 233.6), (-20.0, 233.6), (-25.0, 233.5), (-30.0, 233.6), (-35.0, 234.4), (-40.0, 235.6), (-44.0, 236.9)]
CH_DX = 4.1
CH_SY = (CH_TIP_Y + 1.1 - FACE_R) / (-44.0 - FACE_R)
CH_PATH = [(x - CH_DX, FACE_R + (y - FACE_R) * CH_SY) for y, x in _SAMPLE]
CH_T = 3.3                        # толщина лезвия по X (сверху 3,2, снизу 3,5)
CH_H_ROOT, CH_H_TIP = 9.0, 7.6    # высота по Z у корня и у конца (торец R: Z 6,8…14,5)


def _ch_path():
    pts = [(-CH_PATH[0][1] * 0 + CH_PATH[0][0], FACE_R + 1.0)] + CH_PATH
    return Path2(smooth_path(pts))


def smooth_path(pts, step=0.4, sigma=1.2):
    """Перевыборка и сглаживание незамкнутой ломаной (концы на месте)."""
    from scipy.ndimage import gaussian_filter1d
    p = np.array(pts, float)
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    t = np.linspace(0, s[-1], max(8, int(s[-1] / step)))
    q = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    q = gaussian_filter1d(q, sigma / step, axis=0, mode="nearest")
    q[0], q[-1] = p[0], p[-1]
    return [tuple(v) for v in q]


CH_P = _ch_path()


def handle(h):
    F = Field("Charging_Handle", (CH_X - 8.0, CH_TIP_Y - 2.0, CH_Z - 7.0), (CH_X + 12.0, FACE_R + 0.5, CH_Z + 7.0), h)
    ty0, ty1 = FACE_R, CH_TIP_Y

    def blade(X, Y, Z):
        u = np.clip((Y - ty0) / (ty1 - ty0), 0.0, 1.0)          # 0 у корня, 1 у конца
        # корень раздаётся вилкой к раме (u_handle: от 3,3 до ~8 мм на последних 6 мм)
        th = CH_T + 4.6 * (1.0 - smoothstep(u / 0.26)) ** 2 + 0.7 * smoothstep((u - 0.82) / 0.14)
        hz = 0.5 * (CH_H_ROOT + (CH_H_TIP - CH_H_ROOT) * smoothstep(u)) + 0.9 * (1.0 - smoothstep(u / 0.2)) ** 2
        dxy = CH_P.dist(X, Y) - th / 2
        dz = np.abs(Z - CH_Z) - hz
        return i_round(dxy, dz, 0.8)
    F.add(blade)
    # корень прилегает к грани рамы
    F.apply(half("Y", FACE_R - 0.02, 1), "inter", 0.0, bbox=bb(CH_X - 9, CH_X + 13, FACE_R - 1.5, FACE_R + 0.5, CH_Z - 8, CH_Z + 8))
    # конец: косой торец (сверху: задний угол дальше, торец смотрит наружу-вперёд)
    ex, ey = CH_PATH[-1]
    nx, ny = 0.55, -0.835
    F.apply(plane((ex + 0.3, CH_TIP_Y + 0.95, 0.0), (nx, ny, 0.0)), "inter", 0.6,
            bbox=bb(ex - 5, ex + 5, CH_TIP_Y - 1.5, CH_TIP_Y + 6, CH_Z - 7, CH_Z + 7))
    return F


# ---------------- направляющая возвратной пружины ----------------
GR_R = 1.8                        # стержень Ø3,6 (пружина v13 изнутри r 4,2)
GR_X1 = 150.0                     # передний конец: рама на месте начинается с X 140 — стержень входит в канал
SEAT_X = 17.15                    # опорная грань под пружину (пружина v13 с X 17,3)
BOSS_R = 3.85                     # бобышка внутри первого витка
GR_HW = 6.2                       # полуширина упора (оценка: ширина — по пружине, фото 3-37)
# профиль упора сбоку (X, Z): голова с опорной гранью, сзади — скос вдоль заднего скоса крышки, стойка, лапа на вкладыше
SLOPE_DEG = 46.5
GB_SLOPE_X0 = 32.3                # задний скос крышки изнутри + 0,5 мм: X = 32,3 − 0,949 · (37 − Z)


def _block_side():
    k = 1.0 / math.tan(math.radians(SLOPE_DEG))
    top_z = 37.0 - (GB_SLOPE_X0 - SEAT_X) / k - 0.15
    z9 = 37.0 - (GB_SLOPE_X0 - 9.0) / k - 0.15
    pts = [(9.0, 4.4), (21.0, 4.4), (21.0, 7.0), (12.9, 7.0), (12.9, 9.6), (SEAT_X, 9.6), (SEAT_X, top_z), (9.0, z9)]
    rad = [0.9, 0.9, 0.9, 1.0, 1.0, 0.9, 0.9, 1.2]
    return Poly(fillet_poly(pts, rad, seg=8))


GB_SIDE = _block_side()


def guide_rod(h):
    F = Field("Recoil_Guide_Rod", (7.5, -GR_HW - 1.5, 2.5), (GR_X1 + 1.0, GR_HW + 1.5, 23.5), h)
    F.add(prism(GB_SIDE, "XZ", -GR_HW, GR_HW, rim=0.45), 0.0, bbox=bb(8, 22, -GR_HW - 1, GR_HW + 1, 3.5, 23))
    # бобышка в первом витке и стержень с фаской
    F.add(cyl("X", (0.0, SPRING_Z), BOSS_R, SEAT_X - 0.5, SEAT_X + 2.4, rim=0.0, rim1=0.5), 0.4,
          bbox=bb(SEAT_X - 1, SEAT_X + 3, -BOSS_R - 1, BOSS_R + 1, SPRING_Z - BOSS_R - 1, SPRING_Z + BOSS_R + 1))
    F.add(cyl("X", (0.0, SPRING_Z), GR_R, SEAT_X + 1.0, GR_X1 - 3.0), 0.5,
          bbox=bb(SEAT_X, GR_X1 - 2, -GR_R - 1, GR_R + 1, SPRING_Z - GR_R - 1, SPRING_Z + GR_R + 1))
    # передний конец: поясок и скруглённый наконечник
    F.add(cyl("X", (0.0, SPRING_Z), GR_R + 0.6, GR_X1 - 3.0, GR_X1 - 1.2, rim=0.4), 0.3,
          bbox=bb(GR_X1 - 4, GR_X1, -GR_R - 1.6, GR_R + 1.6, SPRING_Z - GR_R - 1.6, SPRING_Z + GR_R + 1.6))
    F.add(cyl("X", (0.0, SPRING_Z), GR_R - 0.2, GR_X1 - 1.4, GR_X1, rim=0.0, rim1=0.7), 0.2,
          bbox=bb(GR_X1 - 2, GR_X1 + 0.5, -GR_R - 1, GR_R + 1, SPRING_Z - GR_R - 1, SPRING_Z + GR_R + 1))
    return F


def parts():
    return [
        dict(name="Bolt_Carrier", build=carrier, h=0.1, coll="Затворная группа", mat="Steel_bare", adapt=0.012,
             pivot=[BC_X0, 0.0, 0.0],
             motion=f"сдвиг назад (−X) на {CARRIER_TRAVEL} мм (на предохранителе 72,9); за рамой едут рукоятка, "
                    "затвор, выбрасыватель, шток с поршнем"),
        dict(name="Charging_Handle", build=handle, h=0.06, coll="Затворная группа", mat="Steel_bare",
             parent="Bolt_Carrier", adapt=0.05),
        dict(name="Recoil_Guide_Rod", build=guide_rod, h=0.08, coll="Затворная группа", mat="Steel_bare", adapt=0.05),
    ]
