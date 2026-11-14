# ПКП: механизм подачи — основание приёмника (лоток) на оси крышки, рычаг подачи с пальцем подачи (на казённой части
# вкладыша справа, ходит от кулачкового паза штока затворной рамы), щиток рычага, ось крышки и лотка; на внутренней
# стороне крышки — направляющая с удерживающим пальцем ленты (ось, пружина), рычаг крышки со скобой и пружиной,
# упор патрона.
# Устройство ПК, а не «ползун в крышке»: наставление ПК (перевод NGIC 2005, forgottenweapons.com/wp-content/uploads/
# 2012/12/PK-Series-manual-English-2005.pdf) — рис. 1-19 (крышка: упор патрона в продольном пазу посередине, перед ним
# рычаг крышки на оси между двумя приливами с винтовой пружиной, впереди направляющие приливы и удерживающий палец
# с пружиной), 1-20 (основание приёмника: проушины оси спереди, передние и задние направляющие и упорные приливы,
# поперечное окно для пальца подачи, опора закраины, сзади рёбра с продольным пазом для извлекателя, скос досылания,
# вырезы под закраину), 1-21 (рычаг подачи: остов с роликом, палец подачи с осью и пружиной, щиток);
# снимки NGIC 70190/70191/70192 (крышка и лоток подняты, рёбра лотка), образец владельца 01 (крышка открыта, лента
# на лотке: внутри крышки — рычаг с пружиной в окне скобы, пластина с тремя заклёпками и пазом, палец ленты с
# пружиной у оси), фото настоящего — refs/web/B01_cover_feed/01 (лоток и лента сверху).
# Числа, которых нет на образцах, помечены «оценка».
import math

import numpy as np

from dims import *
from sdf import *
from part_bolt import (LEVER_P, LEVER_X, ROLLER_C, ROLLER_R, LEVER_SWING, INS_TOP, sector2, rivet_head)

HX, HZ = COVER_HINGE
TRAY_X0 = -207.5                 # задний конец лотка: перед носиком патрона, вынутого из ленты (оценка по ходу рамы)
SK_IN, SK_OUT = 20.95, 22.35     # боковины лотка (лежат на кромках бортов, внутри юбки крышки)
SK_Z0 = RECV_TOP + 0.25
FL_Z0, FL_Z1 = 19.0, 21.0        # пол задней части (над стойкой рамы 18,7)
DECK_Z1 = 23.0                   # верх площадки передней части
DECK_X1 = -59.2                  # передний край площадки — перед передней стенкой крышки (−58,5)
SLOT_HW = 4.7                    # продольный паз под шейку извлекателя
RIB_Y0, RIB_Y1, RIB_Z1 = 10.5, 13.8, 29.5   # рёбра задней части (между ними ходят захваты извлекателя)
CLAW_X1 = -131.2                 # вырез под захваты извлекателя в передней части
WIN_X0, WIN_X1 = -123.2, -97.6   # поперечное окно пальца подачи
GUIDE_R = (-131.5, -123.6, 25.6) # задние направляющие приливы: X, верх (под гильзой Ø12,37)
GUIDE_F = (-97.0, -91.0, 26.0)   # передние — под скатом гильзы
GUIDE_Y0 = -14.5                 # справа приливы короче: следующий патрон ленты (Y −21) лежит ниже края
STOP_Y = 6.8                     # упорные приливы слева: патрон останавливается на оси (гильза R 6,18)
LUG_Y0, LUG_Y1 = 4.6, 8.85       # проушины оси: между стойками вкладыша (Y ±9)
LEVER_RECESS = (-123.6, -93.6)   # вырез правой боковины под рычаг подачи
LOCK_RECESS = (-85.0, -67.0)     # и под головку замыкателя ствола
DEF_DEG = -16.0                  # рычаг подачи «рама впереди»: на 16° левее середины хода (оценка)
MID_ARM = (-14.5, 19.0)          # ось пальца подачи на рычаге в среднем положении (Y, Z)


def _rot_yz(p, c, deg):
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    y, z = p[0] - c[0], p[1] - c[1]
    return (c[0] + y * ca - z * sa, c[1] + y * sa + z * ca)


ARM_AXIS = _rot_yz(MID_ARM, LEVER_P, DEF_DEG)      # ось пальца подачи в положении по умолчанию


# ---------------- лоток (основание приёмника) ----------------

def tray(h):
    F = Field("Feed_Tray", (TRAY_X0 - 1.5, -SK_OUT - 1.0, SK_Z0 - 1.0), (HX + 6.5, SK_OUT + 1.0, 33.0), h)
    # боковины
    for s in (-1, 1):
        y0, y1 = sorted((s * SK_IN, s * SK_OUT))
        F.add(box_e((TRAY_X0, y0, SK_Z0), (-62.5, y1, DECK_Z1), rx=0.6, ry=1.0, rz=0.6), 0.0,
              bbox=bb(TRAY_X0 - 1, -61.5, y0 - 1, y1 + 1, SK_Z0 - 1, DECK_Z1 + 1))
    # пол задней части и площадка передней (между боковинами), передний край ниже стенки крышки — уступом
    F.add(box_e((TRAY_X0, -SK_IN - 0.3, FL_Z0), (-146.0, SK_IN + 0.3, FL_Z1), rx=0.8, ry=0.6, rz=0.6), 0.8,
          bbox=bb(TRAY_X0 - 1, -145, -SK_IN - 1, SK_IN + 1, FL_Z0 - 1, FL_Z1 + 1))
    F.add(box_e((-148.0, -SK_IN - 0.3, FL_Z0), (DECK_X1, SK_IN + 0.3, DECK_Z1), rx=1.0, ry=0.6, rz=0.6), 0.8,
          bbox=bb(-149, DECK_X1 + 1, -SK_IN - 1, SK_IN + 1, FL_Z0 - 1, DECK_Z1 + 1))
    F.add(box_e((-62.0, -14.4, FL_Z0), (HX - 5.0, 14.4, 21.8), rx=0.8, ry=0.6, rz=0.6), 0.6,
          bbox=bb(-63, HX - 4, -15.5, 15.5, FL_Z0 - 1, 22.8))
    # рёбра задней части с передними скосами (скос досылания: гильза уходит вниз на линию досылания)
    rib = Poly(fillet_poly([(TRAY_X0 + 0.5, FL_Z1 - 0.5), (-141.0, FL_Z1 - 0.5), (-141.0, 24.5), (-147.0, RIB_Z1),
                            (TRAY_X0 + 4.0, RIB_Z1), (TRAY_X0 + 0.5, 26.0)], [0, 0, 1.0, 2.0, 1.2, 1.0]))
    for s in (-1, 1):
        y0, y1 = sorted((s * RIB_Y0, s * RIB_Y1))
        F.add(prism(rib, "XZ", y0, y1, rim=0.6), 0.8, bbox=bb(TRAY_X0 - 1, -140, y0 - 1, y1 + 1, FL_Z1 - 1, RIB_Z1 + 1))
    # вырезы под закраину позади рёбер (закраина вынутого патрона проходит вниз)
    for s in (-1, 1):
        y0, y1 = sorted((s * (RIB_Y0 - 0.5), s * (RIB_Y1 + 0.5)))
        F.sub(box((TRAY_X0 + 6.0, y0, 26.5), (TRAY_X0 + 11.0, y1, RIB_Z1 + 2), 0.0), 0.5,
              bbox=bb(TRAY_X0 + 5, TRAY_X0 + 12, y0 - 1, y1 + 1, 25.5, RIB_Z1 + 1))
    # продольный паз под шейку извлекателя (сзади открыт) и вырез под его захваты спереди
    F.sub(box((TRAY_X0 - 3, -SLOT_HW, FL_Z0 - 2), (-145.5, SLOT_HW, DECK_Z1 + 2), 0.0), 0.5,
          bbox=bb(TRAY_X0 - 2, -144.5, -SLOT_HW - 1, SLOT_HW + 1, FL_Z0 - 1, DECK_Z1 + 1))
    F.sub(box((-150.0, -RIB_Y0 + 0.05, FL_Z1 - 0.2), (CLAW_X1, RIB_Y0 - 0.05, 31.0), 0.0), 0.5,
          bbox=bb(-151, CLAW_X1 + 1, -RIB_Y0, RIB_Y0, FL_Z1 - 1, 30))
    F.sub(box((-150.0, -SLOT_HW, FL_Z0 - 2), (CLAW_X1, SLOT_HW, DECK_Z1 + 2), 0.0), 0.5,
          bbox=bb(-151, CLAW_X1 + 1, -SLOT_HW - 1, SLOT_HW + 1, FL_Z0 - 1, DECK_Z1 + 1))
    # направляющие и упорные приливы
    for x0, x1, zt in (GUIDE_R, GUIDE_F):
        g = Poly(fillet_poly([(GUIDE_Y0, DECK_Z1 - 0.5), (STOP_Y + 0.1, DECK_Z1 - 0.5), (STOP_Y + 0.1, zt), (GUIDE_Y0 + 1.5, zt),
                              (GUIDE_Y0, zt - 1.2)], [0, 0, 0.6, 0.8, 0.6]))
        F.add(prism(g, "YZ", x0, x1, rim=0.6), 0.6, bbox=bb(x0 - 1, x1 + 1, GUIDE_Y0 - 1, STOP_Y + 1, DECK_Z1 - 1, zt + 1))
        top = 28.0 if x0 > -110 else 30.0      # спереди ниже: над ним шарнир наконечника ленты (Z ≥ 28,65)
        st = Poly(fillet_poly([(STOP_Y, DECK_Z1 - 0.5), (15.5, DECK_Z1 - 0.5), (15.5, top - 3.0), (12.5, top), (STOP_Y + 0.8, top),
                               (STOP_Y, top - 1.4)], [0, 0, 1.5, 1.0, 0.6, 0.4]))
        F.add(prism(st, "YZ", x0, x1, rim=0.6), 0.6, bbox=bb(x0 - 1, x1 + 1, STOP_Y - 1, 16.5, DECK_Z1 - 1, top + 1))
    # пазы под ноги удерживающего пальца в задних приливах
    F.sub(box((-130.4, -10.4, 24.3), (-126.1, -7.2, 27.0), 0.0), 0.3, bbox=bb(-131.5, -125, -11.5, -6, 23.5, 26.5))
    # окно пальца подачи (насквозь, справа открыто в вырез боковины) и карман под ушко рычага
    F.sub(box((WIN_X0, -SK_OUT - 2, FL_Z0 - 2), (WIN_X1, 12.0, DECK_Z1 + 2), 0.0), 0.6,
          bbox=bb(WIN_X0 - 1, WIN_X1 + 1, -SK_OUT - 1, 13, FL_Z0 - 1, DECK_Z1 + 1))
    F.sub(box((WIN_X1 - 1.0, -SK_OUT - 2, FL_Z0 - 2), (-94.8, -1.0, 21.0), 0.0), 0.4,
          bbox=bb(WIN_X1 - 2, -93.8, -SK_OUT - 1, 0, FL_Z0 - 1, 22))
    # вырезы правой боковины: рычаг подачи и головка замыкателя
    for x0, x1 in (LEVER_RECESS, LOCK_RECESS):
        F.sub(box((x0, -SK_OUT - 2, SK_Z0 - 2), (x1, -SK_IN + 0.3, DECK_Z1 - 0.8), 0.0), 0.5,
              bbox=bb(x0 - 1, x1 + 1, -SK_OUT - 1, -SK_IN + 1, SK_Z0 - 1, DECK_Z1))
    # скос выхода звеньев влево (под окном выхода ленты в крышке)
    def chute(X, Y, Z):
        d = np.maximum(np.abs(X + 103.0) - 23.0, 16.0 - Y)
        return np.maximum(d, ((23.6 - (Y - 16.0) * 0.47) - Z) * 0.905)
    F.sub(chute, 0.6, bbox=bb(-127, -79, 15, SK_OUT + 1, 18, DECK_Z1 + 1))
    # проушины оси
    lug2 = union2(circle2((HX, HZ), 5.4), rect2(-62.0, HX, FL_Z0, 21.8, 0.6), r=1.5)
    for s in (-1, 1):
        y0, y1 = sorted((s * LUG_Y0, s * LUG_Y1))
        F.add(prism2(lug2, "XZ", y0, y1, rim=0.5), 0.8, bbox=bb(-63, HX + 6.5, y0 - 1, y1 + 1, FL_Z0 - 1, HZ + 6.5))
    F.sub(cyl("Y", (HX, HZ), 2.55, -12, 12), 0.25, bbox=bb(HX - 4, HX + 4, -10, 10, HZ - 4, HZ + 4))
    # защёлка лотка — круглое гнездо спереди слева (наставление), заклёпки направляющих
    F.sub(cyl("Z", (-70.0, 17.0), 2.2, DECK_Z1 - 1.6, DECK_Z1 + 1), 0.3, bbox=bb(-73, -67, 14, 20, DECK_Z1 - 2, DECK_Z1 + 1))
    for x, y in ((-160.0, 17.0), (-160.0, -17.0), (-190.0, 17.0), (-190.0, -17.0)):
        F.add(cyl("Z", (x, y), 1.6, FL_Z1 - 0.2, FL_Z1 + 0.6, rim=0.4), 0.3, bbox=bb(x - 3, x + 3, y - 3, y + 3, FL_Z1 - 1, FL_Z1 + 1))
    return F


def lever_guard(h):
    """Щиток рычага подачи: пластина снаружи над правым бортом, закрывает вырез боковины лотка; на двух лапках."""
    x0, x1 = LEVER_RECESS[0] - 1.0, LEVER_RECESS[1] + 1.0
    F = Field("Feed_Lever_Guard", (x0 - 3, -27.0, -1.5), (x1 + 3, -22.2, 11.5), h)
    F.add(box_e((x0, -25.6, -0.2), (x1, -24.4, 10.0), rx=0.5, ry=2.0, rz=0.5))
    # выштамповка жёсткости
    inner = rect2(x0 + 4.0, x1 - 4.0, 2.0, 8.0, 1.5)

    def rib(X, Y, Z):
        return 0.6 * smoothstep(-inner(X, Z) / 1.2) * smoothstep((-25.0 - Y) / 0.4)
    F.displace(rib, bbox=bb(x0, x1, -26.5, -24.0, 0, 10), fine=False)
    for xa, xb in ((x0 - 2.4, x0 + 0.2), (x1 - 0.2, x1 + 2.4)):
        F.add(box_e((xa, -25.0, 1.0), (xb, -22.42, 9.0), rx=0.4, ry=0.6, rz=0.6), 0.6, bbox=bb(xa - 1, xb + 1, -26, -22, 0, 10))
        F.add(rivet_head((xa + xb) / 2, 5.0, -25.6, 1.6, 0.8), 0.2, bbox=bb(xa - 2, xb + 2, -27, -25, 2, 8))
    return F


def lever(h):
    """Рычаг подачи (остов): ось вдоль X на приливах вкладыша справа; вверх — стойка к оси пальца подачи (две
    проушины), вниз — плечо с роликом в кулачковом пазу штока рамы. Положение — «рама впереди»."""
    F = Field("Feed_Lever", (-124.0, -24.0, -29.0), (-94.0, -1.0, 23.0), h)
    up = [prism(Poly(fillet_poly([(-19.1, LEVER_P[1]), (-19.1, 12.5), (-16.5, 17.0), (-13.0, 17.0), (-15.6, 12.0), (-15.6, LEVER_P[1])],
                                  [0, 3.0, 1.0, 1.0, 2.0, 0])), "YZ", -111.5, -96.5, rim=0.6),
          box_e((-122.5, -18.8, 12.6), (-95.5, -14.4, 16.0), rx=1.0, ry=0.8, rz=0.8)]
    ear = union2(circle2(MID_ARM, 2.9), rect2(MID_ARM[0] - 2.9, MID_ARM[0] + 2.9, 14.0, MID_ARM[1], 0.0))
    for xa, xb in ((-122.5, -119.6), (-98.4, -95.5)):
        up.append(prism2(ear, "YZ", xa, xb, rim=0.4))

    def upper(X, Y, Z):
        d = up[0](X, Y, Z)
        for g in up[1:]:
            d = u_round(d, g(X, Y, Z), 0.8)
        return cut(d, cyl("X", MID_ARM, 1.05, -125, -93)(X, Y, Z), 0.15)
    F.add(rot(upper, "X", (0.0, LEVER_P[0], LEVER_P[1]), DEF_DEG), 0.0)
    # ось-втулка и нижнее плечо с роликом (ролик в положении «рама впереди»)
    F.add(cyl("X", LEVER_P, 3.4, -112.0, -96.0, rim=0.6), 1.0)
    F.add(strip(Path2([LEVER_P, ROLLER_C]), "YZ", 4.2, -109.5, -98.5, rim=0.6), 1.0)
    F.add(cyl("X", ROLLER_C, ROLLER_R, LEVER_X - 2.5, LEVER_X + 2.5, rim=0.6), 0.4)
    F.sub(cyl("X", LEVER_P, 1.65, -113, -95), 0.2)
    # ось ролика — торцы видны
    for x in (LEVER_X - 2.6, LEVER_X + 2.6):
        F.add(cyl("X", ROLLER_C, 1.3, x - 0.5, x + 0.5, rim=0.2), 0.0, bbox=bb(x - 1, x + 1, ROLLER_C[0] - 2, ROLLER_C[0] + 2, ROLLER_C[1] - 2, ROLLER_C[1] + 2))
    return F


def lever_pin(h):
    c = 0.3
    return lathe_mesh([(-117.0, 0.0), (-117.0, 1.6 - c), (-117.0 + c, 1.6), (-91.0 - c, 1.6), (-91.0, 1.6 - c), (-91.0, 0.0)],
                      seg=32, axis="X", c=LEVER_P, closed=False)


def pawl_shaft(h):
    c = 0.25
    return lathe_mesh([(-122.3, 0.0), (-122.3, 1.0 - c), (-122.3 + c, 1.0), (-95.7 - c, 1.0), (-95.7, 1.0 - c), (-95.7, 0.0)],
                      seg=24, axis="X", c=ARM_AXIS, closed=False)


def pawl_arm(h):
    """Палец подачи: втулка на оси в проушинах рычага и три зуба вверх (толкают гильзу первого патрона влево до
    упорных приливов; обратным ходом складываются под следующим патроном). Положение — «рама впереди»."""
    ay, az = ARM_AXIS
    F = Field("Feed_Pawl_Arm", (-120.5, ay - 4.5, az - 3.5), (-97.5, ay + 4.5, 29.5), h)
    F.add(cyl("X", ARM_AXIS, 2.3, -119.3, -98.7, rim=0.4))
    tooth = Poly(fillet_poly([(ay - 0.9, az), (ay + 1.9, az), (-5.2, 26.8), (-5.5, 28.2), (-7.6, 28.2), (-8.6, 24.0)],
                             [0, 0, 0.6, 0.4, 0.8, 1.0]))
    for xa, xb in ((-117.6, -115.2), (-110.4, -108.0), (-103.2, -100.8)):
        F.add(prism(tooth, "YZ", xa, xb, rim=0.4), 0.6, bbox=bb(xa - 1, xb + 1, ay - 4, ay + 4, az - 1, 29))
    F.sub(cyl("X", ARM_AXIS, 1.05, -121, -97), 0.15)
    return F


# ---------------- детали на внутренней стороне крышки ----------------

RET_Y, RET_Z = -8.8, 39.0                       # ось удерживающего пальца
RET_LEGS = ((-130.0, -126.4), (-89.7, -86.9))   # ноги пальца — вне шарниров ленты (X −113,5…−90)


def cover_guide(h):
    """Направляющая крышки: пластина под верхом передней части на трёх заклёпках, приливы с осью удерживающего
    пальца, поперечные рёбра — прижим следующих патронов ленты."""
    F = Field("Cover_Guide", (-141.5, -18.5, 36.0), (-81.0, 3.5, 43.0), h)
    F.add(box_e((-140.0, -17.3, 41.5), (-82.5, 2.0, 42.85), rx=0.4, ry=1.5, rz=1.5))
    lug = union2(rect2(-12.0, -5.0, 37.2, 42.0, 1.2), circle2((RET_Y, RET_Z), 2.6), r=0.8)
    for xa, xb in ((-133.0, -130.6), (-86.5, -84.0)):
        F.add(prism2(lug, "YZ", xa, xb, rim=0.4), 0.8, bbox=bb(xa - 1, xb + 1, -13, -4, 36, 43))
    F.sub(cyl("X", (RET_Y, RET_Z), 1.55, -135, -82), 0.15, bbox=bb(-135, -82, RET_Y - 3, RET_Y + 3, RET_Z - 3, RET_Z + 3))
    for x in (-122.0, -103.0):
        F.add(box_e((x - 1.0, -17.0, 40.3), (x + 1.0, -13.0, 41.6), rx=0.4, ry=0.4, rz=0.4), 0.4, bbox=bb(x - 2, x + 2, -18, -12, 39.5, 42))
    for x, y in ((-137.5, -4.5), (-112.0, -14.5), (-90.5, 0.0)):
        def head(X, Y, Z, x=x, y=y):
            rs = (2.2 ** 2 + 0.8 ** 2) / 1.6
            return np.maximum(np.sqrt((X - x) ** 2 + (Y - y) ** 2 + (Z - (41.5 - 0.8 + rs)) ** 2) - rs, Z - 41.5)
        F.add(head, 0.2, bbox=bb(x - 3, x + 3, y - 3, y + 3, 40, 42))
    return F


def retainer_shaft(h):
    c = 0.3
    return lathe_mesh([(-133.3, 0.0), (-133.3, 1.5 - c), (-133.3 + c, 1.5), (-83.7 - c, 1.5), (-83.7, 1.5 - c), (-83.7, 0.0)],
                      seg=24, axis="X", c=(RET_Y, RET_Z), closed=False)


def retainer_pawl(h):
    """Удерживающий палец ленты: две ноги между первым и вторым патроном не дают ленте уйти назад (вправо)."""
    F = Field("Retainer_Pawl", (-131.5, -11.5, 25.0), (-85.5, -6.0, 42.0), h)
    leg = Poly(fillet_poly([(-10.0, 37.0), (-10.0, 28.6), (-9.2, 26.6), (-7.6, 26.6), (-7.6, 37.0)], [0, 1.0, 0.5, 0.5, 0]))
    for xa, xb in RET_LEGS:
        F.add(cyl("X", (RET_Y, RET_Z), 2.3, xa, xb, rim=0.4), 0.0, bbox=bb(xa - 1, xb + 1, -12, -6, 36, 42))
        F.add(prism(leg, "YZ", xa, xb, rim=0.4), 1.0, bbox=bb(xa - 1, xb + 1, -11, -6.5, 25.5, 40))
    F.add(box_e((RET_LEGS[0][1] - 0.5, -10.0, 35.75), (RET_LEGS[1][0] + 0.5, -7.6, 36.45), rx=0.3, ry=0.3, rz=0.3), 0.6,
          bbox=bb(RET_LEGS[0][1] - 1, RET_LEGS[1][0] + 1, -11, -6.5, 35, 37.5))
    # зубцы на кромке перемычки (рифление, как на образце 01)
    for k in range(12):
        x = RET_LEGS[0][1] + 2.0 + k * 2.8
        F.add(sphere((x, -7.6, 36.1), 0.45), 0.1, bbox=bb(x - 1, x + 1, -8.5, -6.5, 35, 37))
    F.sub(cyl("X", (RET_Y, RET_Z), 1.55, -135, -82), 0.15, bbox=bb(-135, -82, RET_Y - 3, RET_Y + 3, RET_Z - 3, RET_Z + 3))
    return F


def retainer_spring(h):
    return helix_mesh((RET_Y, RET_Z), 1.95, 0.35, -122.0, -106.0, 1.3, seg_turn=20, seg_wire=8)


LEV_P = (-172.0, 38.2)          # ось рычага крышки (X, Z)
LEV_TIP = (-212.0, 35.0)


def lever_bracket(h):
    """Скоба рычага крышки: пластина под верхом с двумя приливами (ось рычага) и передней стенкой — упор пружины."""
    F = Field("Cover_Lever_Bracket", (-195.5, -11, 34.5), (-158.5, 11, 43.0), h)
    F.add(box_e((-194.0, -9.5, 41.5), (-160.0, 9.5, 42.85), rx=0.4, ry=1.5, rz=1.5))
    ear = union2(rect2(-178.0, -166.0, 37.0, 42.0, 1.2), circle2(LEV_P, 2.6), r=0.8)
    for s in (-1, 1):
        y0, y1 = sorted((s * 5.6, s * 7.8))
        F.add(prism2(ear, "XZ", y0, y1, rim=0.4), 0.8, bbox=bb(-180, -164, y0 - 1, y1 + 1, 35, 43))
    F.add(box_e((-161.5, -3.2, 37.3), (-160.0, 3.2, 42.0), rx=0.4, ry=0.4, rz=0.4), 0.8)
    F.sub(cyl("Y", LEV_P, 1.55, -10, 10), 0.15, bbox=bb(LEV_P[0] - 3, LEV_P[0] + 3, -9, 9, LEV_P[1] - 3, LEV_P[1] + 3))
    for x, y in ((-189.0, -6.0), (-189.0, 6.0), (-163.5, -6.5), (-163.5, 6.5)):
        def head(X, Y, Z, x=x, y=y):
            rs = (1.8 ** 2 + 0.7 ** 2) / 1.4
            return np.maximum(np.sqrt((X - x) ** 2 + (Y - y) ** 2 + (Z - (41.5 - 0.7 + rs)) ** 2) - rs, Z - 41.5)
        F.add(head, 0.2, bbox=bb(x - 3, x + 3, y - 3, y + 3, 40, 42))
    return F


def cover_lever(h):
    """Рычаг крышки: на оси в скобе, назад — плечо с носиком; прижимает вынутый из ленты патрон вниз, на линию
    досылания. Над осью — лапка под пружину."""
    F = Field("Cover_Lever", (-215.5, -6.0, 31.5), (-167.0, 6.0, 42.0), h)
    F.add(cyl("Y", LEV_P, 2.9, -5.4, 5.4, rim=0.5))
    F.add(strip(Path2([LEV_P, LEV_TIP]), "XZ", 4.4, -4.8, 4.8, rim=0.8), 0.8)
    F.add(cyl("Y", LEV_TIP, 2.2, -4.8, 4.8, rim=0.6), 0.6)
    F.add(box_e((-170.2, -2.5, 38.0), (-168.0, 2.5, 41.2), rx=0.5, ry=0.5, rz=0.5), 0.6)
    F.sub(cyl("Y", LEV_P, 1.55, -7, 7), 0.15)
    # облегчающий паз в плече
    F.sub(box_e((-205.0, -1.6, 34.0), (-180.0, 1.6, 40.0), rx=1.5), 0.4, bbox=bb(-206, -179, -2.5, 2.5, 33, 41))
    return F


def lever_spring(h):
    return helix_mesh((0.0, 39.6), 1.5, 0.3, -167.9, -161.6, 1.25, seg_turn=20, seg_wire=8)


def lever_pin_cover(h):
    c = 0.25
    return lathe_mesh([(-7.6, 0.0), (-7.6, 1.5 - c), (-7.6 + c, 1.5), (7.6 - c, 1.5), (7.6, 1.5 - c), (7.6, 0.0)],
                      seg=24, axis="Y", c=LEV_P, closed=False)


def cartridge_stop(h):
    """Упор патрона: пластина в продольном пазу задней части крышки, спереди — отогнутый упор."""
    F = Field("Cartridge_Stop", (-319.5, -6, 26.5), (-234.5, 6, 33.0), h)
    F.add(box_e((-318.0, -5.0, 30.4), (-236.0, 5.0, 32.85), rx=1.0, ry=1.5, rz=1.5))
    F.add(box_e((-240.0, -4.0, 27.5), (-236.0, 4.0, 32.0), rx=0.8, ry=0.8, rz=0.8), 1.0)
    for x in (-300.0, -262.0):
        def head(X, Y, Z, x=x):
            rs = (1.8 ** 2 + 0.7 ** 2) / 1.4
            return np.maximum(np.sqrt((X - x) ** 2 + Y ** 2 + (Z - (30.4 - rs + 0.7)) ** 2) - rs, 30.4 - Z)
        F.add(head, 0.2, bbox=bb(x - 3, x + 3, -3, 3, 29, 31))
    return F


def parts():
    G = "Лоток и подача"
    ap = [-109.0, ARM_AXIS[0], ARM_AXIS[1]]
    return [
        dict(name="Feed_Tray", build=tray, h=0.12, coll=G, mat="Steel_blued", adapt=0.1, pivot=[HX, 0.0, HZ],
             note="поворот вокруг +Y на оси крышки до 80°"),
        dict(name="Feed_Lever_Guard", build=lever_guard, h=0.08, coll=G, mat="Steel_blued", parent="Feed_Tray"),
        dict(name="Feed_Lever", build=lever, h=0.07, coll=G, mat="Steel_blued", pivot=[LEVER_X, LEVER_P[0], LEVER_P[1]],
             note=f"поворот вокруг +X от 0° (рама впереди) до +{LEVER_SWING:g}° (рама сзади, палец справа)"),
        dict(name="Feed_Lever_Pin", build=lever_pin, coll=G, mat="Steel_blued", sharp=40),
        dict(name="Feed_Pawl_Arm", build=pawl_arm, h=0.06, coll=G, mat="Steel_blued", parent="Feed_Lever", pivot=ap,
             note="складывается вокруг +X вправо (−Y) до −60° пружиной обратно"),
        dict(name="Feed_Pawl_Shaft", build=pawl_shaft, coll=G, mat="Steel_blued", parent="Feed_Lever", sharp=40),
        dict(name="Cover_Guide", build=cover_guide, h=0.08, coll=G, mat="Steel_blued", parent="Top_Cover"),
        dict(name="Retainer_Shaft", build=retainer_shaft, coll=G, mat="Steel_blued", parent="Top_Cover", sharp=40),
        dict(name="Retainer_Pawl", build=retainer_pawl, h=0.06, coll=G, mat="Steel_blued", parent="Top_Cover",
             pivot=[-108.0, RET_Y, RET_Z], note="качается вокруг +X, подпружинен вниз"),
        dict(name="Retainer_Spring", build=retainer_spring, coll=G, mat="Spring_steel", parent="Top_Cover", sharp=80),
        dict(name="Cover_Lever_Bracket", build=lever_bracket, h=0.08, coll=G, mat="Steel_blued", parent="Top_Cover"),
        dict(name="Cover_Lever", build=cover_lever, h=0.07, coll=G, mat="Steel_blued", parent="Top_Cover",
             pivot=[LEV_P[0], 0.0, LEV_P[1]], note="качается вокруг +Y, пружина прижимает носик вниз"),
        dict(name="Cover_Lever_Pin", build=lever_pin_cover, coll=G, mat="Steel_blued", parent="Top_Cover", sharp=40),
        dict(name="Cover_Lever_Spring", build=lever_spring, coll=G, mat="Spring_steel", parent="Top_Cover", sharp=80),
        dict(name="Cartridge_Stop", build=cartridge_stop, h=0.08, coll=G, mat="Steel_blued", parent="Top_Cover"),
    ]
