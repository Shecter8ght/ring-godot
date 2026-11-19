# ВЕРАС-54 v14: целик по образцу — длинное низкое основание на заднем конце крышки (подошва, корпус с боковыми
# полками, задняя стойка с ложем барабана, наклонные щёки-«горки» и передние «уши» с осью планки), секторная
# планка-лестница (шкала «П 2 4 6 8» / «1 3 5 7» сверху, насечка по бокам, ось спереди), хомутик с двумя рифлёными
# кнопками-защёлками, задний поперечный барабан: обойма на конце планки, ползун с диоптром и шкалой рисок
# боковых поправок, винт с маховичком (накатка) справа и гайкой слева.
# Места (X, Z / X, Y / Y, Z) сняты с плиток образца с сеткой в мм (ref_tiles.py → trace/sights):
#   правый бок — r_rear.png, r_front.png (R_x-0.175_z0.332_f0.6), левый — l_rear.png, l_front.png (L_x-0.175…),
#   сверху — t_rear.png, t_front.png (T_x-0.175_f0.6), сзади — b2.png (B_z0.332_f0.5, поправка глубины 205 мм),
#   вид через диоптр — A01_aim_peep (масштаб 0,021 мм/пикс на расстоянии 129 мм от глаза).
import math

import numpy as np

from dims import *
from sdf import *

COVER_TOP_Z = 38.2               # верх крышки (part_cover.TOP_Z; dims.COVER_TOP = 36,5 — устарел)

# ---------------- основание ----------------
B_X0, B_X1 = 38.8, 113.6         # подошва: от заднего скоса (r_rear: тёмная полоса с X 38,7) до переднего торца (r_front)
PL_Z0, PL_HW = COVER_TOP_Z + 0.1, 8.6   # подошва — в тени под корпусом (тёмная полоса Z 38,3…41,5); полуширина — оценка
BODY_X0 = 41.5                   # задний торец корпуса (r_rear, l_rear)
BODY_Z0, BODY_Z1 = 41.2, 46.3    # корпус: низ (светлая полоса Z 41,5…42,6 — нижний скос), верх (ступень Z 46,0…46,3)
BODY_HW = 10.85                  # b2: шире всего ±10,85 у Z 42,6 (t_front: Y −10,0…+11,2, центр плитки сдвинут на 0,6)
BODY_SIDE_Z = 42.6               # отвесный бок Z 41,6…42,6 (светлая полоса r_rear), выше — скос к щекам (b2: «шеврон», t_front: полоса Y 7,3…10)
FOOT_Z = 43.6                    # задний скос корпуса: от (38,8; 41,6) к (41,5; 43,6) (r_rear)
CHEEK_HW, CH_IN = 7.6, 5.4       # щёки: наружная и внутренняя плоскость (t_front: верх ушей Y ±5,5…7,5; B: стойка ±7,8)
POST_X1, POST_TOP = 48.5, 51.9   # задняя стойка X 41,5…, верх Z 52 (r_rear, b2); спереди — ложе барабана
RAMP = [(68.5, 46.0), (93.5, 49.2)]     # «горка» щёк под хомутиком (r_rear, r_front)
EAR = [(97.4, 54.1), (103.4, 54.1), (112.9, 48.0), (113.6, 47.3)]   # трапеция ушей (r_front)
CH_X0, CH_X1 = 56.0, 104.6       # паз между щёк под планку; спереди — поперечная стенка ушей
EAR_SLOT = (105.6, 107.4, 3.5)   # прорезь в стенке ушей сверху (P22; t_front: рамка X 105,6…107,6, Y −3,6…+4,6)
CH_FLOOR = 46.6
AXLE = (101.1, 50.6)             # ось планки (r_front: головка оси в верхней части отверстия r 1,95)
AXLE_R, BORE_R = 1.3, 1.38
CBORE_R, CBORE_D = 1.95, 0.5     # зенковка отверстия на наружной стороне уха
KEY_TOP = 52.6                   # прорезь над осью (r_front: тёмный язычок до Z 53,3)
CBORE_Z = 49.95                  # зенковка ниже оси: ось прижата к верху отверстия (r_front)

# ---------------- барабан (поперечный, на заднем конце планки) ----------------
DC = (51.0, 51.8)                # ось барабана (X, Z): маховичок справа r 5,2 с центром (51,0; 51,8) (r_rear)
CRADLE_R = 5.6                   # ложе в задней стойке
YOKE_R = 4.8                     # обоймы барабана (b2: Z 47,4…57,2)
SLEEVE_R = (-15.95, -8.95)       # правая обойма (b2: Y −8,8…−16)
SLEEVE_L = (9.55, 10.8)          # левая обойма до гайки (b2: Y 9,6…10,8)
BRIDGE_Z = (46.6, 49.0)          # перемычка под ползуном (низ сегмента барабана)
WEB_X = (55.15, 56.6)            # стенка от перемычки к планке
CAR_R = 5.3                      # ползун: цилиндр с плоским верхом и скошенной задней гранью
CAR_Y = (-8.3, 8.9)              # b2: Y −8,8…+9,6; ход поправки — по 0,65 мм в обе стороны (оценка)
CAR_TOP, CAR_BOT, CAR_FRONT = 57.0, 49.15, 55.0
FACET = ((46.05, 53.7), (49.98, 57.0))  # задняя грань со шкалой (b2: риски Z 53,9…57; t_rear: X 47…48,3)
SCREW_R, SCREW_BORE = 1.5, 1.6
TICK_PITCH, TICK_N = 0.69, 11    # риски поправок (b2: 11 рисок через 0,69, длинные — крайние и средняя)
# диоптр (A01: кольцо снаружи 2,4, отверстие 1,7, ширина стойки у основания 6,4, площадка 13,4 × 0,7)
PEEP_Z = 59.4                    # центр кольца — линия прицеливания (задание; B_z0.332: 59,4…59,6)
PEEP_HOLE = 0.85
PEEP_OUT = 1.62                  # A01: верх арки на 1,6 выше центра кольца
PEEP_X = (49.95, 51.95)          # стойка: толщина 2 (r_rear: X 49,9…52,0, к верху тоньше 50,2…51,8)
PLATE = (49.55, 52.45, 6.7, 57.65)
# винт: маховичок справа, гайка слева (r_rear, l_rear, b2, t_rear)
KNOB_Y = (-19.35, -16.1)
KNOB_R = 5.5                     # по зубьям накатки (r_rear в наложении)
KNURL_N = 56                     # зубьев накатки (шаг 0,6 мм — оценка по r_rear)
CAP_Y = (10.95, 13.9)            # b2: гайка не дальше +14 (поправка глубины)
CAP_R = 5.0

# ---------------- планка ----------------
LEAF_HW = 5.1                    # t_leaf: кромки Y −4,3…+5,9 (центр плитки сдвинут на 0,8)
LEAF_Z = (49.3, 52.0)            # r_rear, r_front: бок планки Z 49,3…52,0
LEAF_X1 = 104.3                  # передний носик под стенкой ушей
LEAF_X0 = 56.4                   # задний конец — на стенке обоймы барабана
NOTCH_X0, NOTCH_PITCH, NOTCH_N = 66.2, 1.2, 21   # насечка по бокам (r_rear: X 66,1…; r_front: …90)
ROW = (1.25, 4.6)                # полосы рядов шкалы по |Y| (t_leaf)
BARS_UP = [67.9, 76.2, 80.4, 84.6, 88.8]       # риски верхнего ряда (+Y) — «П 2 4 6 8» (t_leaf)
BARS_LO = [74.2, 78.3, 82.5, 86.9]             # нижнего (−Y) — «1 3 5 7»
DIGIT_H = 2.0                    # высота цифры (вдоль X; t_leaf: «2» X 77,0…79,0)

# ---------------- хомутик ----------------
SL_C = (61.0, 51.0)             # ось кнопок (r_rear: круг X 56,9…64,6, Z 47,2…55,1)
SL_R = 4.1                       # с тёмной кромкой: X 56,9…65,1, Z 46,9…55,1
SL_HW = 10.4                     # торцы корпуса; кнопки — до ±12,6 (t_rear: Y −12,6…+13,4 с центром +0,6)
BTN_R, BTN_Y = 3.3, (10.0, 12.6)
SLIDER_TRAVEL = 24.2             # до риски «8»: передняя кромка хомутика 64,65 → 88,8 (оценка)
LEAF_DEG = 11.0                  # подъём планки на «8»: горка поднимает хомутик на 2,5 мм в 13 мм от оси (оценка)


def _poly(pts, r, seg=8):
    return Poly(fillet_poly(pts, r, seg=seg))


def _facet_sd(X, Z):
    """Расстояние от задней грани ползуна (плюс — снаружи, назад-вверх)."""
    (x0, z0), (x1, z1) = FACET
    nx, nz = -(z1 - z0), (x1 - x0)
    L = math.hypot(nx, nz)
    return ((X - x0) * nx + (Z - z0) * nz) / L


# ---------------- основание ----------------

def base(h):
    F = Field("Rear_Sight_Base", (B_X0 - 1.0, -BODY_HW - 1.5, PL_Z0 - 1.0), (B_X1 + 1.0, BODY_HW + 1.5, EAR[0][1] + 1.0), h)
    # подошва: узкая, утоплена под корпусом (на образце — тёмная полоса под светлой полкой)
    F.add(box_e((B_X0, -PL_HW, PL_Z0), (B_X1, PL_HW, BODY_Z0 + 0.6), rx=0.35, ry=0.3, rz=0.5))
    # корпус: сечение с фасками по низу и верху, сзади — скос к подошве
    # сечение — шестигранник (b2: «шеврон» на заднем торце): скос снизу к подошве, узкий отвесный бок, скос сверху к щекам
    lo = BODY_SIDE_Z - 0.2
    sec = _poly([(-PL_HW - 0.6, BODY_Z0), (PL_HW + 0.6, BODY_Z0), (BODY_HW, lo), (BODY_HW, BODY_SIDE_Z),
                 (CHEEK_HW, BODY_Z1), (-CHEEK_HW, BODY_Z1), (-BODY_HW, BODY_SIDE_Z), (-BODY_HW, lo)],
                [0.2, 0.2, 0.15, 0.3, 0.6, 0.6, 0.3, 0.15])
    side = _poly([(B_X0 - 0.2, BODY_Z0 - 0.8), (B_X1, BODY_Z0 - 0.8), (B_X1, BODY_Z1 + 1.0), (BODY_X0, BODY_Z1 + 1.0),
                  (BODY_X0, FOOT_Z), (B_X0 - 0.2, BODY_Z0)], [0, 0, 0, 0, 0.6, 0.3])
    F.add(inter(prism(sec, "YZ", B_X0 - 1.0, B_X1 + 0.5), prism(side, "XZ", -BODY_HW - 1, BODY_HW + 1), r=0.3), 0.3)
    # задняя стойка поперёк, спереди — ложе барабана (поднявшись с планкой, барабан из него выходит)
    post = minus(box((BODY_X0, -CHEEK_HW, BODY_Z1 - 0.5), (POST_X1, CHEEK_HW, POST_TOP), 0.45),
                 cyl("Y", DC, CRADLE_R, -CHEEK_HW - 2, CHEEK_HW + 2), 0.35)
    F.add(post, 0.3, bbox=bb(BODY_X0 - 0.5, POST_X1 + 1, -CHEEK_HW - 1.5, CHEEK_HW + 1.5, BODY_Z1 - 1, POST_TOP + 1))
    # щёки: горка под хомутик и уши с осью планки; паз между ними
    # горка — клин: наружные грани скошены 45° вниз до скоса корпуса (P21, P22); уши — отвесные щёки
    # верх клина: горка, перед ушами спуск на полку Z 48 (r_front: линия Z 47,9 от X 96 до переднего торца);
    # наружная грань — плоскость от кромки щеки (±7,6 на высоте горки) к отвесному боку корпуса (±10,85 на Z 42,6):
    # там, где горка уходит в корпус, она совпадает со скосом корпуса
    path = np.array(fillet_path([(RAMP[0][0] - 3.0, BODY_Z1 - 0.4), RAMP[0], RAMP[1], (96.3, 48.0), (B_X1 + 2.0, 48.0)],
                                [3.0, 2.0, 2.0], seg=16))
    px, pz = path[:, 0], path[:, 1]
    slope = np.gradient(pz) / np.maximum(np.gradient(px), 1e-6)

    def wedge(X, Y, Z):
        top = np.interp(X, px, pz).astype(np.float32)
        sl = np.interp(X, px, slope).astype(np.float32)
        p = (Z - top) / np.sqrt(1.0 + sl * sl)
        k = (BODY_HW - CHEEK_HW) / np.maximum(top - BODY_SIDE_Z, 0.5)
        side = (np.abs(Y) - CHEEK_HW - k * (top - Z)) / np.sqrt(1.0 + k * k)
        d = i_round(p, side, 0.45)
        return np.maximum(d, BODY_SIDE_Z + 0.3 - Z)
    F.add(wedge, 0.3, bbox=bb(RAMP[0][0] - 4, B_X1 + 0.5, -BODY_HW - 0.5, BODY_HW + 0.5, BODY_SIDE_Z, RAMP[1][1] + 1.5))
    ear = _poly([(RAMP[1][0] - 0.5, BODY_Z1 - 0.7), RAMP[1]] + EAR + [(B_X1, BODY_Z1 - 0.7)],
                [0, 0.8, 0.8, 1.0, 1.2, 0.5, 0])
    F.add(prism(ear, "XZ", -CHEEK_HW, CHEEK_HW, rim=0.35), 0.4,
          bbox=bb(RAMP[1][0] - 2, B_X1 + 0.5, -CHEEK_HW - 1, CHEEK_HW + 1, BODY_Z1 - 1, EAR[0][1] + 1))
    F.apply(half("X", B_X1, 1), "inter", 0.3, bbox=bb(B_X1 - 1.0, B_X1 + 1.0, -BODY_HW - 1, BODY_HW + 1, PL_Z0 - 0.5, EAR[0][1] + 0.5))
    F.sub(box((CH_X0, -CH_IN, CH_FLOOR), (CH_X1, CH_IN, EAR[0][1] + 3), 0.6), 0.3,
          bbox=bb(CH_X0 - 1, CH_X1 + 1, -CH_IN - 1, CH_IN + 1, CH_FLOOR - 1, EAR[0][1] + 1))
    sx0, sx1, shw = EAR_SLOT
    F.sub(box((sx0, -shw, CH_FLOOR), (sx1, shw, EAR[0][1] + 3), 0.4), 0.3,
          bbox=bb(sx0 - 1, sx1 + 1, -shw - 1, shw + 1, CH_FLOOR - 1, EAR[0][1] + 1))
    # ось планки: отверстие, зенковка и прорезь над ней на наружных сторонах ушей
    ax, az = AXLE
    F.sub(cyl("Y", AXLE, BORE_R, -CHEEK_HW - 2, CHEEK_HW + 2), 0.12, bbox=bb(ax - 3, ax + 3, -CHEEK_HW - 1, CHEEK_HW + 1, az - 3, az + 3))
    key = union2(circle2((ax, CBORE_Z), CBORE_R), seg2(AXLE, (ax, KEY_TOP), 0.72), r=0.3)
    for s in (-1, 1):
        y0, y1 = sorted((s * (CHEEK_HW - CBORE_D), s * (CHEEK_HW + 2)))
        F.sub(prism2(key, "XZ", y0, y1), 0.15, bbox=bb(ax - 3, ax + 3, y0 - 0.5, y1 + 0.5, az - 3, KEY_TOP + 2))
    return F


# ---------------- планка ----------------

def leaf(h):
    F = Field("Rear_Sight_Leaf", (LEAF_X0 - 1.0, -LEAF_HW - 1.0, LEAF_Z[0] - 1.0), (LEAF_X1 + 1.0, LEAF_HW + 1.0, LEAF_Z[1] + 1.0), h)
    z0, z1 = LEAF_Z
    prof = _poly([(LEAF_X0, z0), (LEAF_X1, z0), (LEAF_X1, z1), (LEAF_X0, z1)], [0.3, 1.3, 1.3, 0.3])
    F.add(prism(prof, "XZ", -LEAF_HW, LEAF_HW, rim=0.25))
    # средний желобок сверху
    F.sub(box_e((63.0, -0.45, z1 - 0.35), (104.5, 0.45, z1 + 2), rx=0.2, rz=0.4), 0.12,
          bbox=bb(62, 105.5, -1.5, 1.5, z1 - 1, z1 + 0.5))
    # насечка по бокам — фиксация хомутика
    for k in range(NOTCH_N):
        x = NOTCH_X0 + NOTCH_PITCH * k
        for s in (-1, 1):
            y0, y1 = sorted((s * (LEAF_HW - 0.35), s * (LEAF_HW + 1.0)))
            F.sub(box_e((x - 0.22, y0, z0 + 0.35), (x + 0.22, y1, z1 - 0.35), ry=0.12), 0.08,
                  bbox=bb(x - 1, x + 1, y0 - 0.5, y1 + 0.5, z0, z1))
    # отверстие оси
    ax, az = AXLE
    F.sub(cyl("Y", AXLE, BORE_R, -LEAF_HW - 2, LEAF_HW + 2), 0.12, bbox=bb(ax - 3, ax + 3, -LEAF_HW - 1, LEAF_HW + 1, az - 3, az + 3))
    # шкала: риски поперёк и цифры дальности (читаются стрелком сзади: верх цифры — к дулу)
    for bars, s in ((BARS_UP, 1), (BARS_LO, -1)):
        y0, y1 = sorted((s * ROW[0], s * ROW[1]))
        for bx in bars:
            F.sub(box_e((bx - 0.2, y0, z1 - 0.15), (bx + 0.2, y1, z1 + 1), rz=0.1), 0.05,
                  bbox=bb(bx - 1, bx + 1, y0 - 0.5, y1 + 0.5, z1 - 0.5, z1 + 0.3))
    yc = (ROW[0] + ROW[1]) / 2
    for txt, bx, s in [(t, b, 1) for t, b in zip("П2468", BARS_UP)] + [(t, b, -1) for t, b in zip("1357", BARS_LO)]:
        f2, w = text2(txt, font_path(True), DIGIT_H, track=0.0)
        oy = s * yc + w / 2
        ox = bx + 0.55
        engrave(F, f2, "YX", (oy, ox), -1, z1, 1, depth=0.15, wall=0.12,
                bbox=bb(ox - 0.8, ox + DIGIT_H + 0.8, oy - w - 0.8, oy + 0.8, z1 - 0.8, z1 + 0.4))
    return F


def yoke(h):
    """Обоймы барабана на заднем конце планки: правая (под маховичком), левая (под гайкой), перемычка под
    ползуном и стенка к планке."""
    cx, cz = DC
    F = Field("Rear_Sight_Yoke", (cx - YOKE_R - 1.0, SLEEVE_R[0] - 1.0, BRIDGE_Z[0] - 1.0),
              (WEB_X[1] + 1.0, SLEEVE_L[1] + 1.0, cz + YOKE_R + 1.0), h)
    F.add(cyl("Y", DC, YOKE_R, SLEEVE_R[0], SLEEVE_R[1], rim=0.35))
    F.add(cyl("Y", DC, YOKE_R, SLEEVE_L[0], SLEEVE_L[1], rim=0.35), 0.0)
    # перемычка: нижний сегмент барабана — под ним ложе стойки
    seg = inter(cyl("Y", DC, CRADLE_R - 0.15, SLEEVE_R[1] - 0.6, SLEEVE_L[0] + 0.6), half("Z", BRIDGE_Z[1], 1),
                half("Z", BRIDGE_Z[0], -1), half("X", cx - 4.2, -1), r=0.3)
    F.add(seg, 0.4, bbox=bb(cx - 6, cx + 6, SLEEVE_R[1] - 1.5, SLEEVE_L[0] + 1.5, BRIDGE_Z[0] - 1, BRIDGE_Z[1] + 1))
    web = box((WEB_X[0], -LEAF_HW, BRIDGE_Z[0]), (WEB_X[1], LEAF_HW, LEAF_Z[1]), 0.3)
    F.add(web, 0.5, bbox=bb(WEB_X[0] - 2, WEB_X[1] + 1, -LEAF_HW - 1, LEAF_HW + 1, BRIDGE_Z[0] - 1, LEAF_Z[1] + 1))
    # отверстие винта
    F.sub(cyl("Y", DC, SCREW_BORE, SLEEVE_R[0] - 2, SLEEVE_L[1] + 2), 0.15,
          bbox=bb(cx - 3, cx + 3, SLEEVE_R[0] - 1, SLEEVE_L[1] + 1, cz - 3, cz + 3))
    return F


# ---------------- ползун с диоптром ----------------

def drum(h):
    cx, cz = DC
    F = Field("Rear_Sight_Drum", (cx - CAR_R - 1.0, CAR_Y[0] - 1.0, CAR_BOT - 1.0), (CAR_FRONT + 1.0, CAR_Y[1] + 1.0, PEEP_Z + PEEP_OUT + 1.0), h)
    circ = circle2(DC, CAR_R)

    def prof(U, V):
        d = i_round(circ(U, V), V - CAR_TOP, 0.25)
        d = i_round(d, _facet_sd(U, V), 0.3)
        d = i_round(d, U - CAR_FRONT, 0.3)
        return i_round(d, CAR_BOT - V, 0.3)
    F.add(prism2(prof, "XZ", CAR_Y[0], CAR_Y[1], rim=0.3))
    F.sub(cyl("Y", DC, SCREW_BORE, CAR_Y[0] - 2, CAR_Y[1] + 2), 0.15, bbox=bb(cx - 3, cx + 3, CAR_Y[0] - 1, CAR_Y[1] + 1, cz - 3, cz + 3))
    # площадка диоптра
    px0, px1, phw, pz1 = PLATE
    F.add(box((px0, -phw, CAR_TOP - 0.5), (px1, phw, pz1), 0.2), 0.25, bbox=bb(px0 - 1, px1 + 1, -phw - 1, phw + 1, CAR_TOP - 1.5, pz1 + 1))
    # стойка-арка с кольцом: тоньше к верху (r_rear), бока плавно расходятся к площадке (A01)
    foot = _poly([(-3.4, pz1 - 0.3), (3.4, pz1 - 0.3), (1.75, PEEP_Z + 0.3), (-1.75, PEEP_Z + 0.3)], [0.3, 0.3, 0, 0])
    arch2 = union2(lambda U, V: foot.sd(U, V), circle2((0.0, PEEP_Z), PEEP_OUT), r=0.6)
    ax0, ax1 = PEEP_X
    lean = 0.3 / (PEEP_Z + PEEP_OUT - pz1)
    arch = inter(prism2(arch2, "YZ", ax0 - 0.5, ax1 + 0.5),
                 plane((ax0, 0, pz1), (-1.0, 0, lean)), plane((ax1, 0, pz1), (1.0, 0, lean)), r=0.25)
    F.add(arch, 0.5, bbox=bb(ax0 - 1.5, ax1 + 1.5, -4.5, 4.5, pz1 - 1, PEEP_Z + PEEP_OUT + 0.5))
    # отверстие диоптра с зенковкой со стороны глаза
    F.sub(cyl("X", (0.0, PEEP_Z), PEEP_HOLE, ax0 - 2, ax1 + 2), 0.1, bbox=bb(ax0 - 1, ax1 + 1, -2, 2, PEEP_Z - 2, PEEP_Z + 2))
    F.sub(inter(cone("X", (0.0, PEEP_Z), ax0 - 0.05, 1.3, ax0 + 0.4, PEEP_HOLE - 0.02), slab("X", ax0 - 1, ax0 + 0.4)), 0.06,
          bbox=bb(ax0 - 1, ax0 + 0.8, -2, 2, PEEP_Z - 2, PEEP_Z + 2))
    F.sub(inter(cone("X", (0.0, PEEP_Z), ax1 + 0.1, 1.05, ax1 - 0.15, PEEP_HOLE - 0.02), slab("X", ax1 - 0.15, ax1 + 1)), 0.06,
          bbox=bb(ax1 - 0.6, ax1 + 1, -2, 2, PEEP_Z - 2, PEEP_Z + 2))
    # шкала боковых поправок на задней грани: 11 рисок, крайние и средняя длиннее
    (fx0, fz0), (fx1, fz1) = FACET
    for k in range(TICK_N):
        y = -TICK_PITCH * (TICK_N - 1) / 2 + TICK_PITCH * k
        zlow = 53.95 if k in (0, (TICK_N - 1) // 2, TICK_N - 1) else 55.3

        def tick(X, Y, Z, y=y, zlow=zlow):
            d = np.maximum(np.abs(Y - y) - 0.17, zlow - Z)
            return np.maximum(np.maximum(d, -(_facet_sd(X, Z) + 0.15)), Z - CAR_TOP)
        F.sub(tick, 0.04, bbox=bb(fx0 - 1, fx1 + 0.5, y - 0.6, y + 0.6, zlow - 0.6, fz1 + 0.3))
    # поперечная черта под короткими рисками (A01, b2)
    yt = TICK_PITCH * (TICK_N - 1) / 2

    def line(X, Y, Z):
        d = np.maximum(np.abs(Y) - yt, np.abs(Z - 55.3) - 0.15)
        return np.maximum(np.maximum(d, -(_facet_sd(X, Z) + 0.15)), Z - CAR_TOP)
    F.sub(line, 0.04, bbox=bb(fx0 - 1, fx1 + 0.5, -yt - 0.6, yt + 0.6, 54.6, 56.0))
    return F


# ---------------- винт: маховичок, гайка ----------------

def knob(h):
    cx, cz = DC
    F = Field("Rear_Sight_Knob", (cx - KNOB_R - 1.0, KNOB_Y[0] - 1.0, cz - KNOB_R - 1.0), (cx + KNOB_R + 1.0, CAP_Y[1] + 1.2, cz + KNOB_R + 1.0), h)
    # винт насквозь через обоймы и ползун
    F.add(cyl("Y", DC, SCREW_R, KNOB_Y[1] - 0.3, CAP_Y[0] + 0.3, rim=0.2))
    # маховичок: накатка по ободу, лицо утоплено
    F.add(cyl("Y", DC, KNOB_R, KNOB_Y[0], KNOB_Y[1], rim=0.5, rim1=0.35), 0.3,
          bbox=bb(cx - KNOB_R - 1, cx + KNOB_R + 1, KNOB_Y[0] - 1, KNOB_Y[1] + 1, cz - KNOB_R - 1, cz + KNOB_R + 1))

    def knurl(X, Y, Z):
        a = np.arctan2(Z - cz, X - cx)
        t = a * (KNURL_N / (2 * math.pi))
        g = -0.12 * (1.0 - np.cos(2 * math.pi * t))
        rr = np.hypot(X - cx, Z - cz)
        band = smoothstep((Y - (KNOB_Y[0] + 0.45)) / 0.35) * smoothstep(((KNOB_Y[1] - 0.35) - Y) / 0.35)
        return g * band * smoothstep((rr - (KNOB_R - 0.8)) / 0.4)
    F.displace(knurl, bbox=bb(cx - KNOB_R - 1, cx + KNOB_R + 1, KNOB_Y[0] - 0.5, KNOB_Y[1] + 0.5, cz - KNOB_R - 1, cz + KNOB_R + 1), fine=False)
    F.sub(cyl("Y", DC, 3.95, KNOB_Y[0] - 1, KNOB_Y[0] + 0.25), 0.25, bbox=bb(cx - 5, cx + 5, KNOB_Y[0] - 1, KNOB_Y[0] + 0.6, cz - 5, cz + 5))
    F.add(cyl("Y", DC, 1.9, KNOB_Y[0] + 0.1, KNOB_Y[0] + 0.5, rim=0.15), 0.2, bbox=bb(cx - 3, cx + 3, KNOB_Y[0] - 0.5, KNOB_Y[0] + 1, cz - 3, cz + 3))
    # гайка слева: канавка по лицу, выпуклый центр с плоским торцом, фиксатор-шарик сверху сзади
    F.add(cyl("Y", DC, CAP_R, CAP_Y[0], CAP_Y[1], rim=0.3, rim1=0.5), 0.3,
          bbox=bb(cx - CAP_R - 1, cx + CAP_R + 1, CAP_Y[0] - 1, CAP_Y[1] + 1, cz - CAP_R - 1, cz + CAP_R + 1))
    F.sub(torus("Y", (cx, CAP_Y[1], cz), 4.05, 0.2), 0.08, bbox=bb(cx - 5, cx + 5, CAP_Y[1] - 0.6, CAP_Y[1] + 0.6, cz - 5, cz + 5))
    F.add(cyl("Y", DC, 2.8, CAP_Y[1] - 0.3, CAP_Y[1] + 0.4, rim=0.25), 0.2, bbox=bb(cx - 4, cx + 4, CAP_Y[1] - 0.6, CAP_Y[1] + 1, cz - 4, cz + 4))
    F.sub(cyl("Y", DC, 2.1, CAP_Y[1] + 0.28, CAP_Y[1] + 1.5), 0.12, bbox=bb(cx - 3, cx + 3, CAP_Y[1], CAP_Y[1] + 1, cz - 3, cz + 3))
    da = math.radians(120.0)
    ux, uz = math.cos(da), math.sin(da)
    yb = (CAP_Y[0] + CAP_Y[1]) / 2 + 0.4
    p = (cx + ux * CAP_R, yb, cz + uz * CAP_R)
    F.sub(sphere(p, 0.85), 0.12, bbox=bb(p[0] - 1.5, p[0] + 1.5, yb - 1.5, yb + 1.5, p[2] - 1.5, p[2] + 1.5))
    q = (cx + ux * (CAP_R - 0.45), yb, cz + uz * (CAP_R - 0.45))
    F.add(sphere(q, 0.55), 0.0, bbox=bb(q[0] - 1, q[0] + 1, yb - 1, yb + 1, q[2] - 1, q[2] + 1))
    return F


# ---------------- хомутик и кнопки ----------------

def slider(h):
    sx, sz = SL_C
    F = Field("Rear_Sight_Slider", (sx - SL_R - 1.0, -SL_HW - 1.0, sz - SL_R - 1.0), (sx + SL_R + 1.0, SL_HW + 1.0, sz + SL_R + 1.0), h)
    F.add(cyl("Y", SL_C, SL_R, -SL_HW, SL_HW, rim=0.45))
    # проход планки
    F.sub(box((sx - SL_R - 2, -LEAF_HW - 0.12, LEAF_Z[0] - 0.12), (sx + SL_R + 2, LEAF_HW + 0.12, LEAF_Z[1] + 0.12), 0.1), 0.2,
          bbox=bb(sx - SL_R - 1, sx + SL_R + 1, -LEAF_HW - 1, LEAF_HW + 1, LEAF_Z[0] - 1, LEAF_Z[1] + 1))
    for s in (-1, 1):
        # гнёзда кнопок и поясок у торцов
        y0, y1 = sorted((s * (BTN_Y[0] - 0.1), s * (SL_HW + 1)))
        F.sub(cyl("Y", SL_C, BTN_R + 0.13, y0, y1), 0.15, bbox=bb(sx - 4, sx + 4, y0 - 0.5, y1 + 0.5, sz - 4, sz + 4))
        F.sub(torus("Y", (sx, s * (SL_HW - 1.1), sz), SL_R, 0.16), 0.06,
              bbox=bb(sx - 4.5, sx + 4.5, s * (SL_HW - 1.1) - 0.6, s * (SL_HW - 1.1) + 0.6, sz - 4.5, sz + 4.5))
    return F


def button(side):
    def build(h):
        sx, sz = SL_C
        y0, y1 = sorted((side * BTN_Y[0], side * BTN_Y[1]))
        F = Field("Rear_Sight_Button", (sx - BTN_R - 0.8, y0 - 0.8, sz - BTN_R - 0.8), (sx + BTN_R + 0.8, y1 + 0.8, sz + BTN_R + 0.8), h)
        if side > 0:
            F.add(cyl("Y", SL_C, BTN_R, y0, y1, rim=0.1, rim1=0.4))
        else:
            F.add(cyl("Y", SL_C, BTN_R, y0, y1, rim=0.4, rim1=0.1))
        yf = side * BTN_Y[1]

        # рифление лица: косые рёбра (справа — вдоль (1, 1) в плоскости X–Z, слева — зеркально, как у образца)
        def ribs(X, Y, Z):
            u = ((X - sx) + side * (Z - sz)) * 0.70710678
            g = 0.13 * (0.5 - 0.5 * np.cos(2 * math.pi * u / 0.7))
            rr = np.hypot(X - sx, Z - sz)
            return g * smoothstep((side * Y - (BTN_Y[1] - 0.3)) / 0.15) * smoothstep(((BTN_R - 0.6) - rr) / 0.5)
        F.displace(ribs, bbox=bb(sx - BTN_R, sx + BTN_R, yf - 0.6, yf + 0.6, sz - BTN_R, sz + BTN_R), fine=False)
        return F
    return build


def axle(h):
    ax, az = AXLE
    F = Field("Rear_Sight_Axle", (ax - AXLE_R - 0.8, -CHEEK_HW - 0.8, az - AXLE_R - 0.8), (ax + AXLE_R + 0.8, CHEEK_HW + 0.8, az + AXLE_R + 0.8), h)
    F.add(cyl("Y", AXLE, AXLE_R, -(CHEEK_HW - 0.2), CHEEK_HW - 0.2, rim=0.35))
    return F


def parts():
    ax, az = AXLE
    cx, cz = DC
    sx, sz = SL_C
    return [
        dict(name="Rear_Sight_Base", build=base, h=0.07, coll="Целик", mat="Steel_blued", adapt=0.05),
        dict(name="Rear_Sight_Axle", build=axle, h=0.04, coll="Целик", mat="Steel_bare"),
        dict(name="Rear_Sight_Leaf", build=leaf, h=0.04, coll="Целик", mat="Steel_blued", adapt=0.04,
             pivot=[ax, 0.0, az],
             motion=f"поворот вокруг Y через ось ушей: 0 — лежит («П»), до +{LEAF_DEG:.0f}° (правый винт, задний конец "
                    f"с барабаном вверх) — хомутик на «8» поднят горкой щёк (оценка)"),
        dict(name="Rear_Sight_Yoke", build=yoke, h=0.045, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Leaf", adapt=0.05),
        dict(name="Rear_Sight_Drum", build=drum, h=0.035, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Leaf", adapt=0.04,
             pivot=[cx, 0.0, cz],
             motion="боковая поправка: сдвиг вдоль Y ±0,65 мм (оценка), привод — винт Rear_Sight_Knob"),
        dict(name="Rear_Sight_Knob", build=knob, h=0.04, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Leaf", adapt=0.04,
             pivot=[cx, 0.0, cz],
             motion="вращение вокруг Y (ось барабана): оборот — сдвиг ползуна на шаг резьбы (оценка 0,5 мм), с гайкой слева"),
        dict(name="Rear_Sight_Slider", build=slider, h=0.045, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Leaf", adapt=0.04,
             pivot=[sx, 0.0, sz],
             motion=f"сдвиг вдоль планки (+X в её осях) 0…{SLIDER_TRAVEL:.1f} мм: 0 — «П», риски через 2,15 мм "
                    f"(«1» … «8», оценка)"),
        dict(name="Rear_Sight_Button_L", build=button(1), h=0.03, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Slider",
             pivot=[sx, BTN_Y[1], sz], motion="нажатие внутрь (−Y) на 0,6 мм — отпускает хомутик (оценка)"),
        dict(name="Rear_Sight_Button_R", build=button(-1), h=0.03, coll="Целик", mat="Steel_blued", parent="Rear_Sight_Slider",
             pivot=[sx, -BTN_Y[1], sz], motion="нажатие внутрь (+Y) на 0,6 мм — отпускает хомутик (оценка)"),
    ]
