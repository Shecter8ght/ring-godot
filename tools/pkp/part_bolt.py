# ПКП: затворная группа — затворная рама (остов-шток со стойкой, кожух с фигурным пазом, зацеп рукоятки
# перезаряжания), газовый поршень на оси, затвор с двумя боевыми упорами и выбрасывателем, извлекатель патрона из
# ленты (захваты на стойке рамы), возвратная пружина с направляющим стержнем, отражатель; казённая часть вкладыша
# (гнездо затвора с пазами боевых упоров, канал рамы под стволом, гнездо рычага подачи) и замыкатель ствола.
# Устройство и названия — наставление ПК (перевод NGIC 2005, forgottenweapons.com/wp-content/uploads/2012/12/
# PK-Series-manual-English-2005.pdf): рис. 1-16 (коробка), 1-27 (рама с поршнем: стойка сзади, извлекатель сверху,
# «круглое отверстие для возвратной пружины» снизу стойки), 1-28 (затвор: боевые упоры, фигурный выступ сверху,
# выбрасыватель, паз отражателя), снимки NGIC 70193/70197/70198 (рама в заднем положении: стойка с вилкой
# извлекателя, затвор перед стойкой); образец владельца 01 (вилка извлекателя сразу за донцем первого патрона).
# Схема движения: рама уходит назад на STROKE; первые FREE мм затвор стоит, фигурный выступ идёт по винтовому пазу
# кожуха рамы и поворачивает затвор на −LOCK_DEG; дальше затвор идёт с рамой. Захваты извлекателя в переднем
# положении на 13,8 мм впереди зеркала — поэтому в заднем положении патрон, вынутый из ленты, оказывается перед
# зеркалом и опускается на линию досылания.
import math

import numpy as np

from dims import *
from sdf import *

# ---- общие числа узла (их же берёт part_feed.py) ----
XB = X_BREECH          # казённый срез ствола (dims), который нужен механизму (сейчас у ствола ≈ −197, см. отчёт)
STROKE = CH_TRAVEL     # ход рамы назад (риг part_rig.py): стойка подходит к плите направляющего стержня на 0,9 мм
FREE = 10.0            # свободный ход рамы до поворота затвора (оценка)
LOCK_DEG = -35.0       # поворот затвора при запирании вокруг +X (оценка, как у АК)
GZ = GAS_Z             # ось поршня, рамы и возвратной пружины
INNER_HW = RECV_HW - SHEET                     # внутренняя полуширина коробки (21)
FLOOR_Z = RECV_BOT + SHEET                     # дно коробки изнутри (−47,3)

# ---- затвор (в положении «заперт», числа X — в этом положении; форма строится незапертой и поворачивается) ----
BF = XB - 0.2          # зеркало затвора
CUP_R, CUP_D = 7.45, 2.6       # чашка под закраину: закраина Ø14,48 × 1,6 входит целиком, впереди — зацеп выбрасывателя
HEAD_R = 10.2          # головка (оценка: Ø20 против патронника)
HEAD_X1 = -166.0
LUG_X0, LUG_X1 = -153.0, -164.5   # передний и задний торцы боевых упоров
LUG_R, LUG_HALF = 14.3, 20.0      # упоры: наружный радиус и полуширина в градусах; вверху и внизу (незаперт)
BODY_R = 8.6
TAIL_X = -186.3
CAM_X0, CAM_X1 = -184.3, -179.0   # фигурный выступ на теле затвора (запертый затвор) — в винтовом пазу стойки
CAM_R = 12.8

# ---- рама ----
POST_X0, POST_X1 = -188.0, -170.0           # стойка (впереди — 2 мм до казённой части вкладыша)
POST_HW = 11.0
POST_Z0, POST_Z1 = -40.5, 18.7
WING_HW = INNER_HW - 0.6                     # направляющие выступы стойки (по бортам коробки)
SLOT_RI, SLOT_RO = 8.4, 13.4                 # винтовой паз фигурного выступа внутри стойки
ROD_R = 9.2                                  # остов-шток рамы под стволом
ROD_X1 = 50.0                                # передний торец штока (в корпусе газовой трубки): кулачковый паз на всём ходе
SPRING_BORE_R = 6.4
BORE_X1 = -110.0                             # дно канала возвратной пружины
CH_LUG = (-175.5, -170.6)                    # зацеп рукоятки перезаряжания справа на штоке
GRIP_PIN = (-181.5, 16.4)                    # ось извлекателя (X, Z)
PISTON_PIN_X = ROD_X1 - 5.0
GRIP_X1 = -176.5                             # передний край основания извлекателя в стойке

# ---- вкладыш (казённая часть) ----
INS_X0, INS_X1 = -168.0, -62.15
INS_TOP = 18.6
INS_HW = 19.85        # уже коробки: впереди борта выштампованы внутрь (part_receiver PILL)

# ---- рычаг подачи (его форма в part_feed.py; здесь — вырезы под него во вкладыше и кулачковый паз штока) ----
LEVER_P = (-17.0, -6.0)          # ось рычага (Y, Z), вдоль X
LEVER_X = -104.0                 # середина рычага по X
ROLLER_C = (-11.5, -24.0)        # ролик рычага в положении «рама впереди» (Y, Z)
ROLLER_R = 3.4
LEVER_SWING = 26.0               # поворот рычага за ход рамы, градусы (+ — вправо, к −Y вверху)

# ---- отражатель ----
EJ_X0, EJ_X1 = -264.0, -229.5


def sector2(r0, r1, a0, a1, seg=24):
    """Кольцевой сектор на плоскости YZ (углы от +Y к +Z, градусы) — контур для prism «YZ»."""
    pts = arc(0.0, 0.0, r1, a0, a1, seg)
    if r0 > 0:
        pts += arc(0.0, 0.0, r0, a1, a0, seg)
    else:
        pts += [(0.0, 0.0)]
    return Poly(pts)


def helix_slot(xa, aa, xb, ab, r_in, r_out, half_w):
    """Винтовой паз в трубе вокруг оси X: на развёртке (x, дуга) — отрезок от (xa, угол aa) до (xb, угол ab)."""
    rm = (r_in + r_out) / 2
    seg = seg2((xa, rm * math.radians(aa)), (xb, rm * math.radians(ab)), half_w)

    def f(X, Y, Z):
        a = np.arctan2(Z, Y)
        d1 = seg(X, rm * a)
        d2 = np.abs(np.hypot(Y, Z) - rm) - (r_out - r_in) / 2 - 0.5
        return np.maximum(d1, d2)
    return f


def lever_angle(d):
    """Поворот рычага подачи при отходе рамы на d мм (градусы): стоит, поворачивается, снова стоит."""
    return LEVER_SWING * smoothstep((d - 15.0) / 70.0)


def roller_center(theta):
    a = math.radians(theta) if np.isscalar(theta) else np.radians(theta)
    vy, vz = ROLLER_C[0] - LEVER_P[0], ROLLER_C[1] - LEVER_P[1]
    return (LEVER_P[0] + vy * np.cos(a) - vz * np.sin(a), LEVER_P[1] + vy * np.sin(a) + vz * np.cos(a))


def cam_groove():
    """Кулачковый паз штока: след ролика рычага подачи при ходе рамы (в координатах рамы «впереди»)."""
    def f(X, Y, Z):
        d = np.clip(X - LEVER_X, 0.0, STROKE)
        cy, cz = roller_center(lever_angle(d))
        return np.hypot(Y - cy, Z - cz) - (ROLLER_R + 0.3)
    return f


# ---------------- затворная рама ----------------

def carrier(h):
    F = Field("Bolt_Carrier", (POST_X0 - 1.5, -WING_HW - 1.5, POST_Z0 - 1.5), (ROD_X1 + 1.5, WING_HW + 1.5, POST_Z1 + 1.5), h)
    # стойка: снизу шире, по бокам — направляющие выступы вдоль бортов коробки
    F.add(box_e((POST_X0, -POST_HW, POST_Z0), (POST_X1, POST_HW, POST_Z1), rx=2.5, ry=1.2, rz=1.2))
    F.add(box_e((POST_X0 + 0.5, -WING_HW, -24.5), (POST_X1 - 0.5, WING_HW, -20.0), rx=1.0, ry=0.8, rz=0.8), 1.2,
          bbox=bb(POST_X0, POST_X1, -WING_HW - 1, WING_HW + 1, -27, -17))
    # шток от стойки вперёд до поршня
    F.add(cyl("X", (0, GZ), ROD_R, POST_X1 - 2.0, ROD_X1, rim=1.0), 1.5, bbox=bb(POST_X1 - 3, ROD_X1 + 1, -11, 11, GZ - 11, GZ + 11))
    # зацеп рукоятки перезаряжания справа
    F.add(box((CH_LUG[0], -WING_HW, -27.0), (CH_LUG[1], -7.5, -21.5), 0.8), 1.0,
          bbox=bb(CH_LUG[0] - 2, CH_LUG[1] + 2, -WING_HW - 1, -6, -29, -19))
    # канал затвора в стойке (глухой), канал возвратной пружины (вход сзади стойки)
    F.sub(cyl("X", (0, 0), BODY_R + 0.15, POST_X0 + 1.2, POST_X1 + 2.0), 0.4, bbox=bb(POST_X0, POST_X1 + 1, -10, 10, -10, 10))
    # вход канала спереди — фаска
    F.sub(cone("X", (0, 0), POST_X1 + 0.01, BODY_R + 1.2, POST_X1 - 1.6, BODY_R + 0.1), 0.0, bbox=bb(POST_X1 - 2, POST_X1 + 0.5, -11, 11, -11, 11))
    F.sub(cyl("X", (0, GZ), SPRING_BORE_R, POST_X0 - 2.0, BORE_X1), 0.5, bbox=bb(POST_X0 - 2, BORE_X1 + 1, -8, 8, GZ - 8, GZ + 8))
    # паз отражателя справа по всей стойке
    F.sub(box((POST_X0 - 1, -POST_HW - 1, -4.8), (POST_X1 + 1, -8.4, 0.8), 0.0), 0.4,
          bbox=bb(POST_X0 - 1, POST_X1 + 1, -POST_HW - 1, -7.5, -6, 2))
    # винтовой паз фигурного выступа затвора: заперт — сзади под 55°, отперт — на FREE впереди под 90°
    cam_c = (CAM_X0 + CAM_X1) / 2
    lock_a = 90.0 + LOCK_DEG
    F.sub(helix_slot(cam_c, lock_a, cam_c + FREE, 90.0, SLOT_RI, SLOT_RO, 4.3), 0.4,
          bbox=bb(POST_X0 + 1, POST_X1 + 1, -12, 12, 2, 15))
    # гнездо извлекателя в верху стойки и отверстие его оси
    F.sub(box((POST_X0 + 1.0, -4.4, 13.8), (GRIP_X1 + 0.3, 4.4, POST_Z1 + 2), 0.0), 0.3,
          bbox=bb(POST_X0, GRIP_X1 + 1, -5.5, 5.5, 12.8, POST_Z1 + 1))
    F.sub(cyl("Y", GRIP_PIN, 1.65, -POST_HW - 2, POST_HW + 2), 0.2, bbox=bb(GRIP_PIN[0] - 3, GRIP_PIN[0] + 3, -12.5, 12.5, GRIP_PIN[1] - 3, GRIP_PIN[1] + 3))
    # уступ шептала снизу стойки
    F.sub(box((POST_X0 - 1, -6.0, POST_Z0 - 1), (POST_X0 + 5.0, 6.0, POST_Z0 + 2.2), 0.5), 0.5,
          bbox=bb(POST_X0 - 1, POST_X0 + 6, -7, 7, POST_Z0 - 1, POST_Z0 + 3))
    # вилка под хвостовик поршня и отверстие оси поршня
    F.sub(box((ROD_X1 - 10.0, -3.1, GZ - 11), (ROD_X1 + 2, 3.1, GZ + 11), 0.0), 0.3,
          bbox=bb(ROD_X1 - 11, ROD_X1 + 1, -4, 4, GZ - 10, GZ + 10))
    F.sub(cyl("Y", (PISTON_PIN_X, GZ), 1.65, -11, 11), 0.2, bbox=bb(PISTON_PIN_X - 3, PISTON_PIN_X + 3, -10, 10, GZ - 3, GZ + 3))
    # кулачковый паз ролика рычага подачи на правом верху штока
    F.sub(cam_groove(), 0.4, bbox=bb(LEVER_X - 4, ROD_X1 + 1, -18, 2, GZ - 4, GZ + 14))
    # продольные лыски на штоке (облегчение, за кожухом не видно снизу) и фаски
    F.sub(box((POST_X1 + 6, -ROD_R - 2, GZ - 2.6), (LEVER_X - 12, -ROD_R + 0.8, GZ + 2.6), 0.0), 0.5,
          bbox=bb(POST_X1 + 5, LEVER_X - 11, -ROD_R - 1, -ROD_R + 2, GZ - 4, GZ + 4))
    F.sub(box((POST_X1 + 6, ROD_R - 0.8, GZ - 2.6), (LEVER_X - 12, ROD_R + 2, GZ + 2.6), 0.0), 0.5,
          bbox=bb(POST_X1 + 5, LEVER_X - 11, ROD_R - 2, ROD_R + 1, GZ - 4, GZ + 4))
    return F


def piston(h):
    """Газовый поршень: хвостовик в вилке штока на оси, стержень, головка с канавками (уплотнение) и ведущим пояском."""
    F = Field("Gas_Piston", (ROD_X1 - 11, -6.5, GZ - 6.5), (264.5, 6.5, GZ + 6.5), h)
    prof = [(ROD_X1 - 9.6, 0.0), (ROD_X1 - 9.6, 3.0), (ROD_X1 + 0.8, 3.0), (ROD_X1 + 2.0, 4.6), (230.0, 4.6), (231.5, 5.45),
            (237.0, 5.45), (237.0, 4.85), (239.4, 4.85), (239.4, 5.45), (244.0, 5.45), (244.0, 4.85), (246.4, 4.85),
            (246.4, 5.45), (251.0, 5.45), (251.0, 4.85), (253.4, 4.85), (253.4, 5.45), (262.6, 5.45), (263.0, 5.0),
            (263.0, 0.0)]
    rad = [0, 0.6, 0.4, 0.6, 1.2, 0.3, 0.2, 0.15, 0.15, 0.2, 0.2, 0.15, 0.15, 0.2, 0.2, 0.15, 0.15, 0.2, 0.3, 0.3, 0]
    F.add(revolve(Poly(fillet_poly(prof, rad, seg=4)), "X", (0, GZ)))
    # хвостовик плоский: щёки вилки по бокам
    for s in (-1, 1):
        y0, y1 = sorted((s * 2.95, s * 8.0))
        F.sub(box((ROD_X1 - 12, y0, GZ - 6), (ROD_X1 + 0.8, y1, GZ + 6), 0.0), 0.4,
              bbox=bb(ROD_X1 - 11, ROD_X1 + 2.5, y0 - 1, y1 + 1, GZ - 5, GZ + 5))
    F.sub(cyl("Y", (PISTON_PIN_X, GZ), 1.65, -5, 5), 0.2, bbox=bb(PISTON_PIN_X - 3, PISTON_PIN_X + 3, -4, 4, GZ - 3, GZ + 3))
    # торец головки чуть вогнут
    F.sub(sphere((268.5, 0, GZ), 6.2), 0.3, bbox=bb(261, 264.5, -5.5, 5.5, GZ - 5.5, GZ + 5.5))
    return F


def pin_y(x, z, r, y0, y1):
    """Ось поперёк (вдоль Y) — сетка вращения с фасками на концах."""
    c = min(0.3, r * 0.25)
    return lathe_mesh([(y0, 0.0), (y0, r - c), (y0 + c, r), (y1 - c, r), (y1, r - c), (y1, 0.0)], seg=32, axis="Y", c=(x, z), closed=False)


def piston_pin(h):
    return pin_y(PISTON_PIN_X, GZ, 1.6, -ROD_R + 0.25, ROD_R - 0.25)


def gripper_pin(h):
    return pin_y(GRIP_PIN[0], GRIP_PIN[1], 1.6, -POST_HW + 0.3, POST_HW - 0.3)


def gripper(h):
    """Извлекатель патрона из ленты: основание в гнезде стойки на оси, перемычка, два захвата вперёд; зацепы
    захватов заходят за переднюю грань закраины патрона в ленте (донце — FEED_RIM_X)."""
    xr, xf = POST_X0 + 1.2, FEED_RIM_X + RIM_T + 0.1        # от стойки до зацепов перед закраиной
    F = Field("Cartridge_Gripper", (xr - 1, -11.5, 12.5), (xf + 2.5, 11.5, 33.5), h)
    F.add(box((xr, -4.3, 13.9), (GRIP_X1, 4.3, 22.0), 0.6))
    F.add(box_e((xr, -10.2, 21.5), (GRIP_X1 + 1.0, 10.2, 24.8), rx=1.0, ry=0.8, rz=0.8), 0.8)
    # захваты: профиль сбоку — нижняя грань над лотком, передний конец скошен под закраину
    side = Poly(fillet_poly([(xr, 21.5), (xf - 4.0, 21.5), (xf, 25.5), (xf, 32.3), (xr + 3.0, 32.3), (xr, 29.0)],
                            [0, 2.5, 1.0, 0.6, 1.5, 1.0]))
    for s in (-1, 1):
        y0, y1 = sorted((s * 7.6, s * 10.2))
        F.add(prism(side, "XZ", y0, y1, rim=0.5), 0.8, bbox=bb(xr - 1, xf + 1, y0 - 1.5, y1 + 1.5, 20, 33.5))
        # зацеп: губа внутрь перед закраиной, передняя грань скошена — закраина заскакивает при подходе рамы
        lip = Poly(fillet_poly([(xf - 0.05, 28.0), (xf + 0.6, 28.0), (xf + 1.7, 30.0), (xf + 1.7, 32.3), (xf - 0.05, 32.3)],
                               [0.0, 0.3, 0.4, 0.3, 0.0]))
        y0, y1 = sorted((s * 6.45, s * 8.2))
        F.add(prism(lip, "XZ", y0, y1, rim=0.3), 0.3, bbox=bb(xf - 3, xf + 2.5, y0 - 1, y1 + 1, 27, 33.5))
    F.sub(cyl("Y", GRIP_PIN, 1.65, -6, 6), 0.2, bbox=bb(GRIP_PIN[0] - 3, GRIP_PIN[0] + 3, -5.5, 5.5, GRIP_PIN[1] - 3, GRIP_PIN[1] + 3))
    # продольная риска-упор на перемычке (как на снимке NGIC 70193 — рифление сверху)
    for k in range(5):
        x = xr + 1.8 + k * 1.9
        F.sub(box((x - 0.35, -7.3, 24.2), (x + 0.35, 7.3, 26.6), 0.0), 0.15, bbox=bb(x - 1, x + 1, -8, 8, 23.5, 26.2))
    return F


# ---------------- затвор ----------------

def bolt_shape():
    """Затвор незапертым (упоры вверху и внизу), числа X — в запертом положении."""
    parts_ = []
    head = cyl("X", (0, 0), HEAD_R, HEAD_X1, BF, rim=0.5, rim1=0.7)
    body = cyl("X", (0, 0), BODY_R, TAIL_X, HEAD_X1 + 1.0, rim=0.8)
    lugs = [prism(sector2(HEAD_R - 1.0, LUG_R, a - LUG_HALF, a + LUG_HALF), "YZ", LUG_X1, LUG_X0, rim=0.6) for a in (90.0, 270.0)]
    cam = box((CAM_X0, -3.0, 7.0), (CAM_X1, 3.0, CAM_R), 1.0)

    def f(X, Y, Z):
        d = u_round(head(X, Y, Z), body(X, Y, Z), 1.2)
        for g in lugs:
            d = u_round(d, g(X, Y, Z), 0.6)
        d = u_round(d, cam(X, Y, Z), 1.0)
        # чашка под закраину, отверстие бойка, гнездо выбрасывателя (слева), паз отражателя (справа)
        d = cut(d, cyl("X", (0, 0), CUP_R, BF - CUP_D, BF + 2)(X, Y, Z), 0.25)
        d = cut(d, cyl("X", (0, 0), 1.05, BF - 8, BF + 1)(X, Y, Z), 0.15)
        d = cut(d, box((BF - 14.0, 6.0, -2.6), (BF + 2, 12, 2.6), 0.0)(X, Y, Z), 0.3)
        d = cut(d, box((TAIL_X - 2, -12, -3.6), (BF + 2, -8.45, 0.6), 0.0)(X, Y, Z), 0.4)
        # проточка у хвоста (под зуб бойка) и продольные риски на теле
        d = cut(d, torus("X", (TAIL_X + 6.0, 0, 0), BODY_R + 0.4, 1.0)(X, Y, Z), 0.2)
        return d
    return f


def bolt(h):
    F = Field("Bolt", (TAIL_X - 1.5, -LUG_R - 2, -LUG_R - 2), (BF + 1.0, LUG_R + 2, LUG_R + 2), h)
    F.add(rot(bolt_shape(), "X", (0, 0, 0), LOCK_DEG))
    return F


def extractor(h):
    """Выбрасыватель (зацеп гильзы) в гнезде головки слева; ось вдоль Z, пружина под ним — внутри."""
    F = Field("Bolt_Extractor", (BF - 15, -2, -13), (BF + 1, 13, 13), h)
    body = box((BF - 13.6, 6.15, -2.45), (BF - 0.05, 12.0, 2.45), 0.4)
    shell = cyl("X", (0, 0), HEAD_R - 0.1, BF - 20, BF + 2)
    hook = box((BF - CUP_D + 1.65, 6.55, -2.2), (BF - 0.1, 9.0, 2.2), 0.3)

    def f(X, Y, Z):
        d = i_round(body(X, Y, Z), shell(X, Y, Z), 0.4)
        d = u_round(d, i_round(hook(X, Y, Z), shell(X, Y, Z), 0.3), 0.3)
        # закраина в чашке: выбрасыватель её не задевает (только зацеп впереди)
        return cut(d, cyl("X", (0, 0), RIM_R + 0.1, BF - CUP_D - 0.1, BF - CUP_D + 1.6)(X, Y, Z), 0.0)
    F.add(rot(f, "X", (0, 0, 0), LOCK_DEG))
    return F


# ---------------- возвратный механизм ----------------

GUIDE_HEAD_X = RECV_X0 + 24.0                      # внутренняя грань затыльника (−340,5)
GUIDE_TIP = BORE_X1 - STROKE - 3.0                  # конец стержня: в заднем положении рамы — до дна канала


def guide(h):
    """Направляющий стержень: плита-упор в затыльник (хвостовика в отверстии затыльника нет — отверстия нет у коробки),
    опора пружины, стержень."""
    xh = GUIDE_HEAD_X + 0.1
    F = Field("Recoil_Guide", (xh - 1.5, -8.5, GZ - 8), (GUIDE_TIP + 1, 8.5, GZ + 8), h)
    F.add(box_e((xh, -7.5, GZ - 6.5), (xh + 2.5, 7.5, GZ + 6.5), rx=1.5, ry=0.6, rz=0.6))
    F.add(cyl("X", (0, GZ), 4.0, xh + 2.0, xh + 3.7, rim=0.5), 0.6)
    F.add(cyl("X", (0, GZ), 2.6, xh + 3.0, GUIDE_TIP, rim=1.2), 0.8)
    # кольцевая проточка под шайбу на хвостовике
    return F


def recoil_spring(h):
    x0 = GUIDE_HEAD_X + 3.9
    return helix_mesh((0.0, GZ), 5.0, 0.7, x0, BORE_X1 - 0.2, 5.5, seg_turn=28, seg_wire=10)


def ejector(h):
    """Отражатель: пластина на правом борту изнутри на двух заклёпках, зуб входит в пазы стойки и затвора."""
    F = Field("Ejector", (EJ_X0 - 1, -INNER_HW - 3.5, -9), (EJ_X1 + 1, -8.0, 1), h)
    F.add(box_e((EJ_X0, -INNER_HW + 0.05, -6.6), (EJ_X1 - 4.0, -18.7, -0.7), rx=1.2, ry=0.6, rz=1.6))
    tooth = Poly(fillet_poly([(EJ_X1 - 9.0, -18.9), (EJ_X1 - 2.5, -18.9), (EJ_X1, -9.6), (EJ_X1 - 3.5, -9.1)], [0, 1.0, 0.5, 0.5]))
    F.add(prism(tooth, "XY", -3.5, -0.9, rim=0.4), 1.0, bbox=bb(EJ_X1 - 11, EJ_X1 + 1, -20, -8.5, -5, 0))
    # заклёпки: потай изнутри, головки снаружи борта
    for x in (EJ_X0 + 6.0, EJ_X0 + 21.0):
        F.add(cyl("Y", (x, -3.6), 1.9, -INNER_HW - 0.2, -18.4, rim=0.4), 0.0, bbox=bb(x - 3, x + 3, -INNER_HW - 1, -18, -6, -1))
        F.add(rivet_head(x, -3.6, -RECV_HW - 0.05), 0.0, bbox=bb(x - 3.5, x + 3.5, -RECV_HW - 2, -RECV_HW + 0.2, -7, 0))
    return F


def rivet_head(x, z, y0, r=2.4, hgt=1.1):
    """Полукруглая головка заклёпки на плоскости Y = y0, наружу (к −Y)."""
    rs = (r * r + hgt * hgt) / (2 * hgt)
    c = (x, y0 - hgt + rs, z)

    def f(X, Y, Z):
        dome = np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2) - rs
        return np.maximum(dome, Y - y0)
    return f


# ---------------- казённая часть вкладыша и замыкатель ----------------

def insert(h):
    F = Field("Breech_Insert", (INS_X0 - 1.5, -INS_HW - 1, FLOOR_Z - 0.5), (INS_X1 + 0.5, INS_HW + 1, INS_TOP + 1), h)
    F.add(box_e((INS_X0, -INS_HW, FLOOR_Z + 0.15), (INS_X1, INS_HW, INS_TOP), rx=3.0, ry=0.8, rz=0.8))
    # гнездо ствола спереди и гнездо затвора сзади, с конусом-досылателем на входе
    bore = Poly(fillet_poly([(INS_X0 - 3, 0.0), (INS_X0 - 3, 13.4), (INS_X0, 13.0), (INS_X0 + 2.2, HEAD_R + 0.25), (XB + 0.05, HEAD_R + 0.25),
                             (XB + 0.05, 11.6), (INS_X1 + 2, 11.6), (INS_X1 + 2, 0.0)], [0, 0, 0.5, 0.6, 0, 0, 0, 0]))
    F.sub(revolve(bore, "X", (0, 0)), 0.3)
    # пазы боевых упоров: кольцевые выборки за срезом ствола (поворот упоров) и продольные проходы сзади
    up = 90.0 + LOCK_DEG
    for a_un in (90.0, 270.0):
        a_lk = a_un + LOCK_DEG
        rec = sector2(0.0, LUG_R + 0.35, min(a_lk, a_un) - LUG_HALF - 2.0, max(a_lk, a_un) + LUG_HALF + 2.0)
        F.sub(prism(rec, "YZ", LUG_X1 - 0.4, LUG_X0 + 0.2), 0.3, bbox=bb(LUG_X1 - 1, LUG_X0 + 1, -16, 16, -16, 16))
        pas = sector2(0.0, LUG_R + 0.35, a_un - LUG_HALF - 2.0, a_un + LUG_HALF + 2.0)
        F.sub(prism(pas, "YZ", INS_X0 - 2, LUG_X1), 0.5, bbox=bb(INS_X0 - 1, LUG_X1 + 1, -16, 16, -16, 16))
    # канал штока рамы под стволом
    F.sub(cyl("X", (0, GZ), ROD_R + 0.4, INS_X0 - 3, INS_X1 + 2), 0.6, bbox=bb(INS_X0 - 1, INS_X1 + 1, -11, 11, GZ - 11, GZ + 11))
    # гнездо рычага подачи справа: верх (пальцы и коромысло), стойка рычага, низ (ролик у штока)
    F.sub(box((-123.0, -INS_HW - 2, 9.0), (-95.5, -3.0, INS_TOP + 2), 0.0), 0.6, bbox=bb(-124, -94.5, -INS_HW - 1, -2, 8, INS_TOP + 1))
    F.sub(box((-112.5, -INS_HW - 2, -16.0), (-95.5, -11.0, INS_TOP + 2), 0.0), 0.6, bbox=bb(-113.5, -94.5, -INS_HW - 1, -10, -17, INS_TOP + 1))
    F.sub(box((-112.5, -INS_HW - 2, -31.0), (-95.5, 0.8, -12.0), 0.0), 0.6, bbox=bb(-113.5, -94.5, -INS_HW - 1, 2, -32, -11))
    F.sub(cyl("X", LEVER_P, 1.65, -117.5, -90.5), 0.2, bbox=bb(-118, -90, LEVER_P[0] - 3, LEVER_P[0] + 3, LEVER_P[1] - 3, LEVER_P[1] + 3))
    # поперечный паз замыкателя ствола
    F.sub(box((-82.1, -INS_HW - 2, 13.45), (-69.9, INS_HW + 2, INS_TOP + 2), 0.0), 0.3, bbox=bb(-83, -69, -INS_HW - 1, INS_HW + 1, 12.5, INS_TOP + 1))
    # продольные пазы под рёбра лотка сверху (наставление: «вырез для рёбер основания приёмника»)
    for s in (-1, 1):
        y0, y1 = sorted((s * 15.0, s * 17.6))
        F.sub(box((INS_X0 - 1, y0, INS_TOP - 1.2), (-124.0, y1, INS_TOP + 1), 0.0), 0.25, bbox=bb(INS_X0 - 1, -123, y0 - 1, y1 + 1, INS_TOP - 2, INS_TOP + 1))
    # заклёпки вкладыша на бортах — гнёзда (головки — у ствольной коробки, см. отчёт): фаски по бокам
    return F


def barrel_lock(h):
    """Замыкатель ствола: поперечный клин над стволом с головкой справа (винт регулировки зазора)."""
    F = Field("Barrel_Lock", (-86, -26.5, 1.0), (-66, INS_HW + 0.5, INS_TOP + 1.5), h)
    F.add(box_e((-81.85, -21.6, 13.6), (-70.15, INS_HW - 0.3, INS_TOP - 0.2), rx=0.6, ry=1.0, rz=1.0))
    F.sub(cyl("X", (0, 0), 13.6, -90, -60), 0.4, bbox=bb(-83, -69, -14, 14, 12, 17))
    # головка справа, над бортом коробки
    F.add(box_e((-84.0, -24.8, 3.0), (-68.0, -21.2, 19.2), rx=1.5, ry=1.5, rz=0.8), 0.8, bbox=bb(-85, -67, -26, -20, 2, 20))
    F.add(cyl("Y", (-76.0, 10.5), 3.6, -25.9, -24.4, rim=0.5), 0.3, bbox=bb(-80, -72, -26.5, -24, 6, 15))
    F.sub(box((-76.45, -27, 7.2), (-75.55, -25.2, 13.8), 0.0), 0.15, bbox=bb(-77.5, -74.5, -27, -25, 6.5, 14.5))
    # ступенчатый вырез сверху (по нему проходит палец подачи)
    F.sub(box((-83, -16.0, INS_TOP - 1.6), (-69, -4.0, INS_TOP + 2), 0.0), 0.4, bbox=bb(-83, -69, -17, -3, INS_TOP - 2.5, INS_TOP))
    return F


def parts():
    G = "Затворная группа"
    car_pivot = [POST_X0, 0.0, 0.0]
    mv = dict(axis="-X", travel=STROKE)
    return [
        dict(name="Bolt_Carrier", build=carrier, h=0.15, coll=G, mat="Steel_bare", pivot=car_pivot,
             note=f"ход назад вдоль −X {STROKE:g} мм; первые {FREE:g} мм затвор стоит"),
        dict(name="Gas_Piston", build=piston, h=0.08, coll=G, mat="Steel_bare", parent="Bolt_Carrier",
             pivot=[PISTON_PIN_X, 0.0, GZ], note="на оси вдоль Y, с рамой"),
        dict(name="Piston_Pin", build=piston_pin, coll=G, mat="Steel_bare", parent="Bolt_Carrier", sharp=40),
        dict(name="Cartridge_Gripper", build=gripper, h=0.07, coll=G, mat="Steel_bare", parent="Bolt_Carrier",
             pivot=[GRIP_PIN[0], 0.0, GRIP_PIN[1]], note="ось вдоль Y, подпружинен, качается на 2–3°"),
        dict(name="Gripper_Pin", build=gripper_pin, coll=G, mat="Steel_bare", parent="Bolt_Carrier", sharp=40),
        dict(name="Bolt", build=bolt, h=0.07, coll=G, mat="Steel_bare", pivot=[BF, 0.0, 0.0], parent="Bolt_Carrier",
             note=f"поворот вокруг +X от {LOCK_DEG:g}° (заперт) до 0° за первые {FREE:g} мм хода рамы, потом с рамой "
                  f"назад на {STROKE - FREE:g}"),
        dict(name="Bolt_Extractor", build=extractor, h=0.05, coll=G, mat="Steel_bare", parent="Bolt"),
        dict(name="Recoil_Guide", build=guide, h=0.08, coll=G, mat="Steel_blued"),
        dict(name="Recoil_Spring", build=recoil_spring, coll=G, mat="Spring_steel", sharp=80, pivot=[GUIDE_HEAD_X + 3.9, 0.0, GZ],
             note=f"сжимается вдоль X: передний конец с рамой на {STROKE:g} мм, задний у затыльника"),
        dict(name="Ejector", build=ejector, h=0.08, coll=G, mat="Steel_blued"),
        dict(name="Breech_Insert", build=insert, h=0.12, coll=G, mat="Steel_blued", adapt=0.1),
        dict(name="Barrel_Lock", build=barrel_lock, h=0.08, coll=G, mat="Steel_blued", pivot=[-76.0, -23.0, 10.5],
             note="поперечный клин, вдоль Y"),
    ]
