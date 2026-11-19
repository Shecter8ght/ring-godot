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
BC_STEP_X0, BC_STEP_X1 = 196.1, 199.0   # ступенька полки правого бока: задний участок выступает, его передний конец
                                  # сходит на передний участок (R_x-0.052_z0.2945: светлая полоса X 195,5…198,3; P20)
FACE_F = -13.5                    # грань полки на переднем участке (оценка глубины ступеньки 1,1: P20)
STEM_X1 = 249.85                  # передний торец штока рамы: дальше — поршень v13 (X 250, r 5,6)
STEM_R = 5.75                     # шток: низ 21,25 над пружиной (верх 21,1), верх 32,75 под проходом колодки (33,4)

# ---------------- сечение рамы (Y, Z) ----------------
LIP_Z0, LIP_Z1 = -1.6, 0.9        # полозья под направляющими коробки (направляющие Z 1,3…3,1 со скруглением 0,3)
GROOVE_Z1 = 3.5
LIP_HW = 15.2                     # полуширина по полозьям (коробка изнутри ±15,5)
GROOVE_L, GROOVE_R = 12.6, -13.7  # дно пазов: левая направляющая до Y 12,9, правая до −14,1 — зазор 0,3…0,4
FACE_R = CARRIER_FACE_Y           # правая грань полки на заднем участке (видна в вырезе крышки)
FACE_L = 14.6
# правый бок Г-образный (R_x-0.052_z0.2945, P20): внизу выступающая полка Z 5…13,9, над ней утопленная верхняя часть
SHELF_Z = 13.9                    # верх полки (сзади 14,0, спереди 13,6)
UPPER_R = -12.0                   # грань верхней части над полкой (P20: полка сверху — светлая полоса ~2,5 мм)
UPPER_Z1 = 15.3                   # светлая полоса Z 13,9…15,3, выше — тёмный скос под кромкой крышки
BEVEL_Y, BEVEL_Z = 12.3, 17.4     # скос слева
HUMP_Z = 24.6                     # верх горба над каналом пружины (свод крышки свободен на ±15,5 до Z 24)
SPRING_Z = 15.5                   # ось возвратной пружины (v13)
CHAN_R = 5.95                     # канал пружины: пружина v13 r 5,6
# стойка штока: подъём горба к штоку
RISE_X, RISE_DEG = 191.2, 32.0    # оценка: подъём (образец раму не показывает); плоскость начинается под верхом горба —
RISE_Z = HUMP_Z - 3.0             # на горб она выходит у X ≈ 196 без складки галтели

# ---------------- затвор v13 (срезы trace/bolt/sect1.png) ----------------
TAIL_R = 6.6                      # гнездо хвостовика затвора (хвостовик r 2,9, стебель r 6,2)
TAIL_X0 = 156.5                   # торец гнезда: ударник затвора с X 157
HEAD_R, HEAD_X0 = 8.75, 211.9     # головка затвора r 8,3 с X 212,4
LUGS_R, LUGS_X0 = 11.6, 231.2     # боевые упоры r 11,2 с X 232
# ведущий выступ затвора: X 205…214,5, Y −6,6…−13,5, Z −0,9…5,2 (наклонён) — фигурный паз снизу справа
CAM_Z1 = 5.9
EXTR = (220.6, -9.7, -5.0, 2.9)   # паз выбрасывателя (выбрасыватель X 221,6…240,3, Y −9,05…−5,5, Z ±2,2)
HAMMER = (BC_X0 - 2.0, 156.6, 4.6, 2.6)   # вырез под курок снизу сзади: X0, X1, полуширина, верх Z
# отражатель на левой направляющей коробки (в коробке его нет): X 165…175, лезвие внутрь до Y 3,2 — внутрь радиуса
# закраины гильзы (4,6); затвор проходит мимо него пазом (EJ_SLOT_* в затворе) уже повёрнутым
EJ_X0, EJ_X1, EJ_Y0 = 165.0, 175.0, 3.2
EJ_Z0, EJ_Z1 = 1.4, 3.0
EJ_SLOT_X = 163.5

SERIAL = "0547"                   # вымышленный номер

# ---------------- затвор (новый, вместо v13): запирание поворотом ----------------
# Строится в запертом положении. Отпирание — поворот вокруг оси канала (X) на UNLOCK_DEG: ведущий выступ уходит
# вверх по скосу фигурного паза рамы (как у АК — против часовой, если смотреть сзади). Рама проходит FREE мм
# свободно, на следующих (LAG − FREE) мм поворачивает затвор, дальше затвор идёт вместе с рамой: зеркало
# X = BOLT_FACE − max(0, ход − LAG).
UNLOCK_DEG = -35.0
FREE, LAG = 2.5, 8.0
BOLT_FACE = 239.35                # дно чашечки (зеркало): у v13 то же
CUP_R = 5.05                      # чашечка под дно гильзы (закраина r 4,6)
BOLT_X0 = 157.5                   # задний конец ударника
TAILB_X = (159.5, 177.5)          # хвостовик r 2,9 — проходит под лезвием отражателя (до Y 3,2) в любом повороте
TAILB_R = 2.9
STEM_B_X1, STEM_B_R = 212.4, 6.2  # стебель затвора (у v13 r 6,2)
HEAD_B_R = 8.3                    # головка (у v13 r 8,3), X STEM_B_X1…240
LUG_X = (232.0, 240.0)            # боевые упоры r 11,2: правый — вниз-вправо (до Y −11), левый — вверх-влево (как у v13)
LUG_R = 11.2
LUG_L_PSI, LUG_R_PSI = (2.0, 40.0), (182.0, 224.0)   # угловые места упоров (ψ = atan2(Z, Y), град)
CAM_X0, CAM_X1 = 204.8, 213.8     # ведущий выступ (у v13 X 205…214), радиально 5,5…12,5, ψ 168°
CAM_PSI, CAM_HW, CAM_R1 = 168.0, 2.6, 12.5
CAM_CLR = 0.35
# досылатель: в ОТПЕРТОМ положении — гребень строго вниз у зеркала (цепляет верх закраины верхнего патрона)
RAM_X = (228.0, 239.8)
RAM_HW, RAM_Z = 2.6, -12.6
# паз отражателя (в отпертом положении): лезвие отражателя Y ≥ 3,2, Z 1,4…3,0 — паз с зазором 0,3
EJ_SLOT_Y, EJ_SLOT_Z = 2.9, (1.1, 3.3)
# выбрасыватель: справа-сверху в отпертом положении (ψ 130°) → в запертом ψ 165°
EXT_PSI = 165.0
EXT_X = (222.5, 241.4)
EXT_PIN = (230.0, 7.0)            # ось выбрасывателя: X и расстояние от оси затвора; поперёк (касательно)
EXT_SPRING_X = 224.4


def unlock_angle(sv):
    """Угол поворота затвора при ходе рамы sv (мм)."""
    return UNLOCK_DEG * float(np.clip((sv - FREE) / (LAG - FREE), 0.0, 1.0))


def _cam_lug(X, Y, Z):
    """Ведущий выступ затвора в запертом положении (брус на ψ 180°, повёрнутый на CAM_PSI)."""
    b = box_e((CAM_X0, -CAM_R1, -CAM_HW), (CAM_X1, -5.0, CAM_HW), rx=1.0, ry=0.8, rz=0.8)
    return rot(b, "X", (0.0, 0.0, 0.0), CAM_PSI - 180.0)(X, Y, Z)


def _wedge(psi0, psi1):
    """Клин между полуплоскостями через ось X под углами psi0…psi1 (град)."""
    a0, a1 = math.radians(psi0), math.radians(psi1)

    def f(X, Y, Z):
        d0 = -(np.cos(a0) * Z - np.sin(a0) * Y)          # внутрь от луча psi0 (против часовой)
        d1 = (np.cos(a1) * Z - np.sin(a1) * Y)
        return np.maximum(d0, d1)
    return f


def _section():
    pts = [(-LIP_HW, LIP_Z0), (-LIP_HW, LIP_Z1), (GROOVE_R, LIP_Z1), (GROOVE_R, GROOVE_Z1), (FACE_R, GROOVE_Z1),
           (FACE_R, SHELF_Z), (UPPER_R, SHELF_Z), (UPPER_R, UPPER_Z1), (-10.3, 17.6), (-10.0, 21.6), (-3.8, HUMP_Z),
           (3.8, HUMP_Z), (10.8, 21.6), (BEVEL_Y, BEVEL_Z), (FACE_L, 15.0), (FACE_L, GROOVE_Z1), (GROOVE_L, GROOVE_Z1),
           (GROOVE_L, LIP_Z1), (LIP_HW, LIP_Z1), (LIP_HW, LIP_Z0)]
    rad = [0.5, 0.3, 0.25, 0.25, 0.3, 0.5, 0.4, 0.5, 0.8, 2.5, 4.5, 4.5, 3.0, 0.9, 0.7, 0.3, 0.25, 0.25, 0.3, 0.5]
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
    # 3. ступенька полки: передний участок утоплен, задний сходит на него пологим скосом
    step = Poly([(BC_STEP_X0, -25.0), (BC_STEP_X0, FACE_R - 0.05), (BC_STEP_X1, FACE_F), (BC_X1 + 3, FACE_F), (BC_X1 + 3, -25.0)])
    # низ выреза — посреди паза направляющей (в воздухе): иначе плоскость совпадает с верхом полоза
    F.sub(prism(step, "XY", 2.2, 22.0), 0.45, bbox=bb(BC_STEP_X0 - 1, BC_X1 + 1, FACE_R - 1, FACE_F + 1, 1.5, SHELF_Z + 1))
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
    # 6. фигурный паз ведущего выступа — след выступа затвора на первых LAG мм хода рамы (затвор стоит, рама идёт
    #    назад; после свободного хода выступ скользит по скосу паза и затвор поворачивается на UNLOCK_DEG)
    def cam_slot(X, Y, Z):
        d = None
        for sv in np.linspace(0.0, LAG, 33):
            g = move(rot(_cam_lug, "X", (0.0, 0.0, 0.0), unlock_angle(sv)), (sv, 0.0, 0.0))(X, Y, Z)
            d = g if d is None else np.minimum(d, g)
        return d - CAM_CLR
    F.sub(cam_slot, 0.4, bbox=bb(CAM_X0 - 1.5, CAM_X1 + LAG + 1.5, -14.0, 0.0, -3.5, 13.5))
    # 7. паз выбрасывателя
    ex0, ey0, ey1, ez = EXTR
    F.sub(box_e((ex0, ey0, -ez), (BC_X1 + 3, ey1, ez), rx=0.8, rz=0.6), 0.3, bbox=bb(ex0 - 1, BC_X1 + 2, ey0 - 1, ey1 + 1, -ez - 1, ez + 1))
    # 8. вырез под курок снизу сзади, паз отражателя слева снизу
    hx0, hx1, hhw, hz = HAMMER
    F.sub(box_e((hx0, -hhw, LIP_Z0 - 3), (hx1, hhw, hz), rx=1.2, rz=1.0), 0.4, bbox=bb(hx0, hx1 + 1, -hhw - 1, hhw + 1, LIP_Z0 - 1, hz + 1))
    # паз отражателя: левый паз направляющей углублён от X EJ_SLOT_X до переднего конца нижней части —
    # отражатель (Ejector) на левой направляющей коробки стоит в нём, рама скользит мимо
    F.sub(box_e((EJ_SLOT_X, EJ_Y0 - 0.35, LIP_Z1 - 0.1), (BC_LOW_X1 + 3, GROOVE_L + 0.5, GROOVE_Z1 + 0.1), rx=0.4, rz=0.6), 0.3,
          bbox=bb(EJ_SLOT_X - 1, BC_LOW_X1 + 1, EJ_Y0 - 1.5, GROOVE_L + 1, LIP_Z1 - 0.8, GROOVE_Z1 + 0.8))
    # 9. фрезерованная выборка на левом боку (облегчение, как у рам АК)
    lp = Poly(fillet_poly([(152.0, 6.0), (219.0, 6.0), (219.0, 12.6), (152.0, 12.6)], 2.0))
    F.sub(prism(lp, "XZ", FACE_L - 0.7, FACE_L + 2.0, rim=0.0), 0.4, bbox=bb(150, 221, FACE_L - 1.5, FACE_L + 1.5, 4.5, 14.5))
    # 10. номер на правой грани переднего участка
    f2, w = text2(SERIAL, font_path(True), 2.4, track=0.25)
    ox, oz = 206.0, 8.0
    engrave(F, f2, "XZ", (ox, oz), 1, FACE_F, -1, depth=0.18, wall=0.18, bbox=bb(ox - 1, ox + w + 1, FACE_F - 1, FACE_F + 1.2, oz - 1, oz + 3.4))
    return F


# ---------------- рукоятка взведения ----------------
# Место — по образцу (решение владельца 2026-11-19: «над крючком затвора выреза нет» — рукоятка v13 стояла под самой
# кромкой окна). Средняя линия (Y, X) и толщина по X сняты сверху: T_x-0.052_f0.7 (trace/bolt/t7b.png) до Y −36,
# дальше — T_x0.02 (t_handle.png); высота и торец — сбоку R_x-0.052_z0.2945_f0.7 (r7_win.png): торец с насечкой
# X 232…236,8, Z 6,2…14,2, рукоятка во всю высоту Z 6,0…14,4; ракурс P20 — лопатка, отогнутая вбок и вниз-назад.
CH_ROOT_Y = FACE_F
CH_TIP_Y_S = -44.5                # конец рукоятки (образец; у v13 был −41)
CH_LINE = [(-13.5, 234.1), (-20.0, 234.1), (-24.0, 234.0), (-28.0, 234.1), (-32.0, 234.4), (-36.0, 234.8),
           (-40.0, 235.5), (-43.6, 236.2)]
# толщина лопатки по X (Y, мм): у корня раздаётся к раме, к концу тоньше, на конце — площадка под палец
CH_THICK = [(-13.5, 6.0), (-17.0, 4.6), (-20.0, 4.0), (-24.0, 3.2), (-28.0, 2.7), (-32.0, 2.4), (-38.0, 2.3),
            (-41.0, 3.0), (-43.0, 4.4), (-45.0, 4.6)]
CH_ZC_ROOT, CH_ZC_TIP = 10.2, 9.9          # середина по высоте (отгиб конца вниз)
CH_H_ROOT, CH_H_TIP = 8.4, 7.7             # высота у корня и у конца
CH_END_N = (0.22, -0.975)                  # торец смотрит наружу, чуть вперёд (сверху: передний угол короче)
KNURL_P = 0.75                             # шаг насечки торца (ромб)


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


CH_P = Path2(smooth_path([(CH_LINE[0][1], CH_ROOT_Y + 1.0)] + [(x, y) for y, x in CH_LINE]))
_TY = np.array([y for y, t in CH_THICK])[::-1]
_TT = np.array([t for y, t in CH_THICK])[::-1]


def _end_plane():
    x, y = CH_LINE[-1][1], CH_TIP_Y_S
    n = np.array(CH_END_N); n /= np.linalg.norm(n)
    return (x, y), n


def handle(h):
    F = Field("Charging_Handle", (226.0, CH_TIP_Y_S - 2.0, 3.0), (243.0, CH_ROOT_Y + 0.5, 17.0), h)
    (ex, ey), (nx, ny) = _end_plane()

    def blade(X, Y, Z):
        u = np.clip((Y - CH_ROOT_Y) / (CH_TIP_Y_S - CH_ROOT_Y), 0.0, 1.0)
        th = np.interp(Y, _TY, _TT).astype(np.float32)
        zc = CH_ZC_ROOT + (CH_ZC_TIP - CH_ZC_ROOT) * smoothstep((u - 0.5) / 0.5)
        hz = 0.5 * (CH_H_ROOT + (CH_H_TIP - CH_H_ROOT) * smoothstep(u)) + 0.6 * (1.0 - smoothstep(u / 0.15)) ** 2
        dxy = CH_P.dist(X, Y) - th / 2
        dz = np.abs(Z - zc) - hz
        return i_round(dxy, dz, 0.7)
    F.add(blade)
    # корень прилегает к грани полки рамы
    F.apply(half("Y", CH_ROOT_Y - 0.02, 1), "inter", 0.0, bbox=bb(226, 243, CH_ROOT_Y - 1.5, CH_ROOT_Y + 0.5, 3, 17))
    # торец
    F.apply(plane((ex, ey, 0.0), (nx, ny, 0.0)), "inter", 0.55, bbox=bb(ex - 6, ex + 6, ey - 1.5, ey + 6, 3, 17))

    # насечка торца: ромбическая сетка канавок 45°, глубина 0,16, только на торце
    def knurl(X, Y, Z):
        dpl = (X - ex) * nx + (Y - ey) * ny                       # до плоскости торца (минус — внутри)
        tx, ty = -ny, nx                                          # вдоль торца в плане
        u = (X - ex) * tx + (Y - ey) * ty
        a = (u + Z) / (KNURL_P * 1.41421356); b = (u - Z) / (KNURL_P * 1.41421356)
        ga = np.abs(a - np.round(a)); gb = np.abs(b - np.round(b))
        groove = np.maximum(smoothstep((0.22 - ga) / 0.12), smoothstep((0.22 - gb) / 0.12))
        near = smoothstep((0.5 + dpl) / 0.35)
        return -0.16 * groove * near
    F.displace(knurl, bbox=bb(ex - 5, ex + 5, ey - 1, ey + 2.0, 4.5, 15.5))
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


# ---------------- отражатель ----------------
def ejector(h):
    """Отражатель на левой направляющей коробки: лезвие внутрь до Y 3,2 (за закраину гильзы), у корня — усиление;
    передняя грань (по ней бьёт дно гильзы) скошена, чтобы гильза уходила вправо."""
    F = Field("Ejector", (EJ_X0 - 1.5, EJ_Y0 - 1.5, 0.3), (EJ_X1 + 1.5, 14.0, 4.3), h)
    blade = Poly(fillet_poly([(EJ_X0, 12.95), (EJ_X0, 9.0), (EJ_X0 + 2.5, EJ_Y0), (EJ_X1 - 0.8, EJ_Y0),
                              (EJ_X1, EJ_Y0 + 1.4), (EJ_X1, 12.95)], [0.0, 1.5, 0.8, 0.5, 0.8, 0.0]))
    F.add(prism(blade, "XY", EJ_Z0, EJ_Z1, rim=0.3))
    # усиление у корня (утолщение по Z к направляющей)
    root = Poly(fillet_poly([(EJ_X0, 12.95), (EJ_X0, 10.6), (EJ_X1, 10.6), (EJ_X1, 12.95)], [0.0, 1.0, 1.0, 0.0]))
    F.add(prism(root, "XY", EJ_Z0 - 0.15, EJ_Z1 + 0.25, rim=0.3), 0.5, bbox=bb(EJ_X0 - 1, EJ_X1 + 1, 9.5, 13.5, 0.5, 4.0))
    return F


# ---------------- затвор ----------------
def _ext_frame(fn):
    """Тело, заданное на ψ 180° (справа, плоскость Z = 0), — на место выбрасывателя ψ EXT_PSI."""
    return rot(fn, "X", (0.0, 0.0, 0.0), EXT_PSI - 180.0)


def _unlocked(fn):
    """Тело, заданное в отпертом положении затвора, — в запертое (затвор строится запертым)."""
    return rot(fn, "X", (0.0, 0.0, 0.0), -UNLOCK_DEG)


def bolt(h):
    F = Field("Bolt", (BOLT_X0 - 1.0, -13.0, -13.5), (EXT_X[1] + 1.0, 13.0, 13.0), h)
    xf = BOLT_FACE + 0.65                                         # передний торец головки (X 240)
    # ударник, хвостовик, стебель, головка
    F.add(cyl("X", (0.0, 0.0), 1.8, BOLT_X0, TAILB_X[0] + 0.5, rim=0.4))
    F.add(cyl("X", (0.0, 0.0), TAILB_R, TAILB_X[0], TAILB_X[1] + 1.0, rim=0.5), 0.4,
          bbox=bb(TAILB_X[0] - 1, TAILB_X[1] + 2, -4, 4, -4, 4))
    F.add(revolve(Poly([(TAILB_X[1], 0.0), (TAILB_X[1], TAILB_R + 0.3), (TAILB_X[1] + 2.2, STEM_B_R),
                        (STEM_B_X1 + 1.0, STEM_B_R), (STEM_B_X1 + 1.0, 0.0)]), "X"), 0.6,
          bbox=bb(TAILB_X[1] - 1, STEM_B_X1 + 2, -7, 7, -7, 7))
    F.add(cyl("X", (0.0, 0.0), HEAD_B_R, STEM_B_X1, xf, rim=0.6, rim1=0.5), 0.8,
          bbox=bb(STEM_B_X1 - 2, xf + 1, -9.5, 9.5, -9.5, 9.5))
    # боевые упоры: клинья по радиусу 11,2 со скруглёнными кромками
    for p0, p1 in (LUG_L_PSI, LUG_R_PSI):
        lug = inter(cyl("X", (0.0, 0.0), LUG_R, LUG_X[0], LUG_X[1], rim=0.6), _wedge(p0, p1), r=0.6)
        F.add(lug, 0.6, bbox=bb(LUG_X[0] - 1.5, LUG_X[1] + 1, -12.5, 12.5, -12.5, 12.5))
    # ведущий выступ
    F.add(_cam_lug, 0.8, bbox=bb(CAM_X0 - 1.5, CAM_X1 + 1.5, -13.5, -3.0, -5.0, 6.0))
    # досылатель (в отпертом положении — вниз): гребень у зеркала, задний конец скошен — скользит по патронам назад
    ram = Poly(fillet_poly([(RAM_X[0], -6.0), (RAM_X[1], -6.0), (RAM_X[1], RAM_Z + 0.4), (RAM_X[1] - 0.6, RAM_Z),
                            (RAM_X[0] + 4.0, RAM_Z), (RAM_X[0], RAM_Z + 4.0)], [0.0, 0.0, 0.3, 0.5, 2.0, 1.0]))
    F.add(_unlocked(prism(ram, "XZ", -RAM_HW, RAM_HW, rim=0.5)), 0.8,
          bbox=bb(RAM_X[0] - 1.5, RAM_X[1] + 0.5, -2.0, 11.0, -13.5, -3.0))
    # чашечка под дно гильзы и отверстие бойка
    F.sub(cyl("X", (0.0, 0.0), CUP_R, BOLT_FACE, xf + 3.0), 0.25, bbox=bb(BOLT_FACE - 1, xf + 1, -6, 6, -6, 6))
    F.sub(cyl("X", (0.0, 0.0), 0.75, BOLT_FACE - 6.0, BOLT_FACE + 1.0), 0.2, bbox=bb(BOLT_FACE - 7, BOLT_FACE + 1, -2, 2, -2, 2))
    # паз отражателя вдоль стебля и головки (совпадает с лезвием в отпертом положении)
    z0, z1 = EJ_SLOT_Z
    F.sub(_unlocked(box_e((TAILB_X[1] - 1.0, EJ_SLOT_Y, z0), (xf + 3.0, 14.0, z1), rx=0.3, rz=0.5)), 0.3,
          bbox=bb(TAILB_X[1] - 2, xf + 1.5, -6.0, 13.0, -1.0, 13.0))
    # паз выбрасывателя (сквозь стенку чашечки), отверстие оси, гнездо пружины
    F.sub(_ext_frame(box_e((EXT_X[0] - 0.4, -14.0, -1.95), (xf + 3.0, -5.6, 1.95), rx=0.3, rz=0.5)), 0.25,
          bbox=bb(EXT_X[0] - 1.5, xf + 1.5, -10.0, -2.0, -3.5, 5.0))
    px, pr = EXT_PIN
    F.sub(_ext_frame(cyl("Z", (px, -pr), 0.95, -4.5, 4.5)), 0.15, bbox=bb(px - 2, px + 2, -10, -3, -6, 6))
    F.sub(_ext_frame(cyl("Y", (EXT_SPRING_X, 0.0), 1.25, -6.0, -3.4, rim=0.3)), 0.2,
          bbox=bb(EXT_SPRING_X - 2, EXT_SPRING_X + 2, -8, -2, -3, 3))
    return F


def extractor(h):
    """Выбрасыватель: рычаг в пазу головки, зуб за проточку гильзы (зуб X 240,85…241,4 до r 4,1, над закраиной —
    r ≥ 4,75), ось поперёк у X 230, сзади — гнездо пружины."""
    F = Field("Bolt_Extractor", (EXT_X[0] - 1.0, -10.0, -6.0), (EXT_X[1] + 1.0, -1.0, 7.0), h)
    side = Poly(fillet_poly([(EXT_X[0], -5.9), (240.85, -5.9), (240.85, -4.1), (EXT_X[1], -4.1), (EXT_X[1], -5.0),
                             (EXT_X[1] - 0.2, -8.0), (238.0, -8.25), (EXT_X[0] + 1.5, -8.25), (EXT_X[0], -7.6)],
                            [0.6, 0.2, 0.2, 0.3, 0.4, 0.5, 2.0, 0.8, 0.6]))
    F.add(_ext_frame(prism(side, "XY", -1.7, 1.7, rim=0.35)))
    # ось (головки заподлицо с телом затвора)
    px, pr = EXT_PIN
    F.add(_ext_frame(cyl("Z", (px, -pr), 0.9, -3.4, 3.4, rim=0.25)), 0.0, bbox=bb(px - 2, px + 2, -10, -3, -6, 6))
    # гнездо пружины снизу рычага
    F.sub(_ext_frame(cyl("Y", (EXT_SPRING_X, 0.0), 1.15, -6.9, -5.0)), 0.2, bbox=bb(EXT_SPRING_X - 2, EXT_SPRING_X + 2, -8, -4, -3, 3))
    return F


def extractor_spring(h):
    """Пружина выбрасывателя: витая, радиально между дном гнезда в затворе и рычагом (сетка)."""
    V, Q = helix_mesh((0.0, 0.0), 0.85, 0.17, 3.45, 6.65, 0.55, seg_turn=24, seg_wire=8, dead=1.0)
    # спираль построена вдоль X: X → радиально наружу (−Y на ψ 180°), затем на ψ EXT_PSI
    x, y, z = V[:, 0].copy(), V[:, 1].copy(), V[:, 2].copy()
    Y0 = -x; X0 = EXT_SPRING_X + y; Z0 = z
    a = math.radians(EXT_PSI - 180.0)
    Y1 = Y0 * math.cos(a) - Z0 * math.sin(a); Z1 = Y0 * math.sin(a) + Z0 * math.cos(a)
    return np.stack([X0, Y1, Z1], 1).astype(np.float32), Q


# ---------------- патрон в патроннике ----------------
# Размеры — как у патронов v13 в магазине (сетка «Magazine • loaded case 1 / projectile 1»: гильза 39,0, корпус
# r 4,62…4,42, скат к дульцу r 3,03, пуля r 2,73, общая длина 51,4). Дно — у зеркала затвора v13: дно чашечки X 239,35
# (чашечка r 5,05…5,6 до X 240).
CASE_X0 = 239.4
CASE_L = 38.98
CASE_PROFILE = [(0.0, 0.0), (0.0, 4.15), (0.3, 4.6), (1.05, 4.6), (1.3, 4.2), (1.5, 3.95), (2.1, 3.95), (2.55, 4.45),
                (2.9, 4.62), (28.8, 4.42), (31.6, 3.06), (CASE_L - 0.25, 3.03), (CASE_L, 2.85), (CASE_L, 0.0)]
BULLET_PROFILE = [(CASE_L, 0.0), (CASE_L, 2.73), (41.4, 2.73), (42.5, 2.54), (43.6, 2.35), (44.7, 2.13), (45.9, 1.91),
                  (47.0, 1.67), (48.1, 1.41), (49.2, 1.12), (50.3, 0.79), (51.1, 0.42), (51.4, 0.0)]


def _lathe(profile):
    pts = [(CASE_X0 + t, r) for t, r in profile]
    return lathe_mesh(pts, seg=96, axis="X", c=(0.0, 0.0), closed=False)


def chambered_case(h):
    return _lathe(CASE_PROFILE)


def chambered_bullet(h):
    return _lathe(BULLET_PROFILE)


def parts():
    return [
        dict(name="Bolt_Carrier", build=carrier, h=0.1, coll="Затворная группа", mat="Steel_bare", adapt=0.012,
             pivot=[BC_X0, 0.0, 0.0],
             motion=f"сдвиг назад (−X) на {CARRIER_TRAVEL} мм (на предохранителе 72,9); за рамой едут рукоятка, "
                    "затвор, выбрасыватель, шток с поршнем"),
        dict(name="Charging_Handle", build=handle, h=0.06, coll="Затворная группа", mat="Steel_bare",
             parent="Bolt_Carrier", adapt=0.05),
        dict(name="Recoil_Guide_Rod", build=guide_rod, h=0.08, coll="Затворная группа", mat="Steel_bare", adapt=0.05),
        dict(name="Ejector", build=ejector, h=0.06, coll="Затворная группа", mat="Steel_blued", adapt=0.04,
             note="неподвижен: на левой направляющей коробки"),
        dict(name="Bolt", build=bolt, h=0.07, coll="Затворная группа", mat="Steel_bare", adapt=0.02,
             parent="Bolt_Carrier", pivot=[BOLT_FACE, 0.0, 0.0],
             motion=f"поворот вокруг X на {UNLOCK_DEG}° (отпирание) при ходе рамы {FREE}…{LAG} мм; до {LAG} мм затвор "
                    f"стоит (рама уходит назад), дальше едет с рамой: зеркало X = {BOLT_FACE} − max(0, ход − {LAG})"),
        dict(name="Bolt_Extractor", build=extractor, h=0.05, coll="Затворная группа", mat="Steel_bare", adapt=0.03,
             parent="Bolt", pivot=[EXT_PIN[0], -EXT_PIN[1] * math.cos(math.radians(EXT_PSI - 180.0)),
                                  -EXT_PIN[1] * math.sin(math.radians(EXT_PSI - 180.0))],
             motion="оценка: качание на оси (поперёк затвора) на 3…4°, зуб наружу при заходе на закраину"),
        dict(name="Bolt_Extractor_Spring", build=extractor_spring, coll="Затворная группа", mat="Spring_steel",
             parent="Bolt"),
        dict(name="Chambered_Case", build=chambered_case, coll="Патроны", mat="Case_lacquer",
             pivot=[CASE_X0, 0.0, 0.0], motion="движение даёт риг: дно — центр (CASE_X0, 0, 0)"),
        dict(name="Chambered_Bullet", build=chambered_bullet, coll="Патроны", mat="Bullet_jacket",
             parent="Chambered_Case"),
    ]
