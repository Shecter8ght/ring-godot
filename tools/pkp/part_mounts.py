# ПКП «Частокол»: места под кронштейны и сами кронштейны с планками (замечание владельца 2026-11-14).
# На пулемёте: две опоры «ласточкин хвост» с поперечным пазом на крышке (Cover_Base_F / R) и две втулки под
# поперечные болты в корпусе газовой трубки (part_barrel.gas_housing; места — dims.FOREND_BOLT_*).
# Съёмное (две коллекции «Кронштейн — …», выключены по умолчанию): планка на крышку под прицел (Rail_Cover — надевается на опоры сзади, стягивается
# двумя поперечными винтами через пазы опор) и цевьё с нижней и двумя боковыми планками под рукоятку, ЛЦУ и фонарь
# (Rail_Forend — надевается снизу на корпус газовой трубки, два сквозных болта, спереди ложемент под трубку).
# Планки — профиль MIL-STD-1913 (Picatinny): ширина 21,2, паз 5,23 × 3,0, шаг 10,0076; на них встаёт и Weaver.
# Расположение — как у серийных обвесов ПКМ / ПКП на фото владельца (19, 20); конструкция своя, чужих марок нет.
import math

import numpy as np

from dims import *
from sdf import *
from part_cover import TOP_F

# в игре пулемёт без обвеса: кронштейны докупаются отдельно — их коллекции в файле выключены (владелец, 2026-11-14)
K_COVER = "Кронштейн — планка на крышку"
K_FOREND = "Кронштейн — цевьё"

# ---------- планка Picatinny ----------
PIC_W, PIC_NECK_W = 21.2, 15.6
PIC_CH = 2.74                    # верхняя фаска 45°
PIC_FL = 2.8                     # нижний скос 45° до шейки
PIC_SLOT, PIC_PITCH, PIC_DEPTH = 5.23, 10.0076, 3.0
PIC_RIB = PIC_PITCH - PIC_SLOT   # зуб между пазами
PIC_NECK = 1.1                   # высота шейки над основанием
PIC_TOP = PIC_NECK + PIC_FL + PIC_CH


def pic_len(n):
    """Длина планки на n пазов с целыми зубьями по концам."""
    return 2 * PIC_RIB + PIC_SLOT + (n - 1) * PIC_PITCH


def pic_slots(x0, n):
    return [x0 + PIC_RIB + PIC_SLOT / 2 + i * PIC_PITCH for i in range(n)]


def pic_section(place):
    """Сечение планки. place(поперёк, высота над основанием) → точка в плоскости YZ."""
    hw, nw = PIC_W / 2, PIC_NECK_W / 2
    pts = [(-nw, -1.5), (-nw, PIC_NECK), (-hw, PIC_NECK + PIC_FL), (-(hw - PIC_CH), PIC_TOP), (hw - PIC_CH, PIC_TOP),
           (hw, PIC_NECK + PIC_FL), (nw, PIC_NECK), (nw, -1.5)]
    return Poly(fillet_poly([place(u, v) for u, v in pts], [0, 0.4, 0.25, 0.3, 0.3, 0.25, 0.4, 0]))


def hexagon(cu, cv, r):
    return [(cu + r * math.cos(math.radians(60 * i)), cv + r * math.sin(math.radians(60 * i))) for i in range(6)]


# ---------- опоры на крышке ----------
ZPAD = TOP_F + 1.0               # верх выштамповки-площадки крышки
BASE_F = (-104.0, -86.0)         # блок передней опоры: на площадке, перед названием
BASE_R = (-203.0, -190.0)        # блок задней опоры: на ровном верху за площадкой
BASE_FL = 1.5                    # отступ фланца от блока
BASE_FLANGE_HW = 9.5
BASE_HW_ROOT, BASE_HW_TOP = 4.7, 7.0     # «ласточкин хвост» 60°
BASE_Z0, BASE_Z1 = 46.7, 50.7            # основание и верх хвоста — общие для обеих опор
SLOPE = (BASE_HW_TOP - BASE_HW_ROOT) / (BASE_Z1 - BASE_Z0)
SCREW_Z = 50.2                   # ось стяжного винта: проходит в поперечном пазу опоры
SCREW_R = 2.0
NOTCH_HW = 2.25                  # полуширина поперечного паза опоры


def cover_base(front):
    x0, x1 = BASE_F if front else BASE_R
    xm = (x0 + x1) / 2
    zs = (ZPAD if front else TOP_F) + 0.04
    name = "Cover_Base_F" if front else "Cover_Base_R"

    def build(h):
        F = Field(name, (x0 - BASE_FL - 1, -BASE_FLANGE_HW - 1, zs - 0.6), (x1 + BASE_FL + 1, BASE_FLANGE_HW + 1, BASE_Z1 + 1), h)
        F.add(box((x0 - BASE_FL, -BASE_FLANGE_HW, zs), (x1 + BASE_FL, BASE_FLANGE_HW, BASE_Z0), 0.45))
        zr = BASE_Z0 - 0.6       # хвост начинается в теле фланца: стык не по общей плоскости
        dov = Poly(fillet_poly([(-(BASE_HW_ROOT - 0.6 * SLOPE), zr), (-BASE_HW_TOP, BASE_Z1), (BASE_HW_TOP, BASE_Z1),
                                (BASE_HW_ROOT - 0.6 * SLOPE, zr)], [0, 0.35, 0.35, 0]))
        F.add(prism(dov, "YZ", x0, x1, rim=0.4), 0.3)
        # поперечный паз: в нём лежит стяжной винт кронштейна — он же упор от отдачи
        F.sub(box((xm - NOTCH_HW, -9, SCREW_Z - SCREW_R - 0.25), (xm + NOTCH_HW, 9, BASE_Z1 + 2), 0.0), 0.25,
              bbox=bb(xm - 3.5, xm + 3.5, -8.5, 8.5, BASE_Z0 - 0.2, BASE_Z1 + 0.8))
        # потайные заклёпки фланца: по две с каждой стороны
        for s in (-1, 1):
            for xr in (xm - 4.2, xm + 4.2):
                def ring(X, Y, Z, xr=xr, s=s):
                    rr = np.hypot(X - xr, Y - s * 7.35)
                    return -0.12 * smoothstep((0.22 - np.abs(rr - 1.45)) / 0.15) * smoothstep((Z - (BASE_Z0 - 0.4)) / 0.3)
                ya, yb = sorted((s * 5.2, s * 9.4))
                F.displace(ring, bbox=bb(xr - 2.2, xr + 2.2, ya, yb, BASE_Z0 - 0.5, BASE_Z0 + 0.3))
        return F
    return build


# ---------- планка на крышку ----------
RC_N = 12
RC_X0 = -207.4
RC_X1 = RC_X0 + pic_len(RC_N)
RC_HW = 13.0
RC_Z0 = 46.95                    # низ юбок: над фланцами опор
RC_ROOF = BASE_Z1 + 0.2          # потолок паза под опоры
RC_DECK = 53.9                   # основание планки
RC_ZT = RC_DECK + PIC_TOP        # верх планки
LIPS = ((BASE_R[0] - 2.5, BASE_R[1] + 2.5), (BASE_F[0] - 1.0, BASE_F[1] + 1.0))   # упругие губки левой юбки над опорами
SCREW_X = ((BASE_R[0] + BASE_R[1]) / 2, (BASE_F[0] + BASE_F[1]) / 2)
HEAD_R, HEAD_H = 3.3, 2.6


def rail_cover(h):
    F = Field("Rail_Cover", (RC_X0 - 1, -RC_HW - 1.2, RC_Z0 - 1), (RC_X1 + 1, RC_HW + 1.2, RC_ZT + 1), h)
    body = Poly(fillet_poly([(-RC_HW, RC_Z0), (RC_HW, RC_Z0), (RC_HW, RC_DECK - 1.5), (RC_HW - 1.5, RC_DECK),
                             (-(RC_HW - 1.5), RC_DECK), (-RC_HW, RC_DECK - 1.5)], [0.6, 0.6, 0.4, 0.4, 0.4, 0.4]))
    F.add(prism(body, "YZ", RC_X0, RC_X1, rim=0.5))
    F.add(prism(pic_section(lambda u, v: (u, RC_DECK + v)), "YZ", RC_X0, RC_X1, rim=0.35), 0.4)
    for xs in pic_slots(RC_X0, RC_N):
        F.sub(box((xs - PIC_SLOT / 2, -RC_HW, RC_ZT - PIC_DEPTH), (xs + PIC_SLOT / 2, RC_HW, RC_ZT + 2), 0.0), 0.3,
              bbox=bb(xs - 3.6, xs + 3.6, -11.5, 11.5, RC_ZT - PIC_DEPTH - 0.8, RC_ZT + 0.9))
    # паз под опоры по всей длине: кронштейн надевается сзади
    g0 = BASE_HW_ROOT + 0.15 - 0.7 * SLOPE
    g1 = BASE_HW_ROOT + 0.15 + (RC_ROOF - BASE_Z0) * SLOPE
    groove = Poly(fillet_poly([(-g0, BASE_Z0 - 0.7), (-g1, RC_ROOF), (g1, RC_ROOF), (g0, BASE_Z0 - 0.7)], [0, 0.3, 0.3, 0]))
    F.sub(prism(groove, "YZ", RC_X0 - 2, RC_X1 + 2), 0.3, bbox=bb(RC_X0 - 1, RC_X1 + 1, -9, 9, RC_Z0 - 1, RC_ROOF + 0.8))
    # между опорами юбки сняты — мостик: легче, и название на крышке не закрыто с боков
    F.sub(box((BASE_R[1] + 7.0, -RC_HW - 3, RC_Z0 - 3), (BASE_F[0] - 7.0, RC_HW + 3, RC_ROOF + 0.3), 2.5), 0.6,
          bbox=bb(BASE_R[1] + 5, BASE_F[0] - 5, -RC_HW - 1.2, RC_HW + 1.2, RC_Z0 - 1, RC_ROOF + 1.5))
    # зажим: левая юбка над каждой опорой — упругая губка между двумя пропилами, её стягивает поперечный винт
    for (xa, xb), xs in zip(LIPS, SCREW_X):
        for xc in (xa, xb):
            F.sub(box((xc - 0.3, 3.0, RC_Z0 - 2), (xc + 0.3, RC_HW + 3, RC_ROOF + 0.45), 0.0), 0.12,
                  bbox=bb(xc - 1.2, xc + 1.2, 2.0, RC_HW + 1.2, RC_Z0 - 1, RC_ROOF + 1.3))
        # отверстие под винт: сквозь губку и паз опоры, резьба в правой юбке
        F.sub(cyl("Y", (xs, SCREW_Z), SCREW_R + 0.12, -RC_HW + 1.6, RC_HW + 3), 0.15,
              bbox=bb(xs - 3.2, xs + 3.2, -RC_HW, RC_HW + 1.2, SCREW_Z - 3.2, SCREW_Z + 3.2))
    return F


def cover_screw(i):
    xs = SCREW_X[i]
    name = "Rail_Cover_Screw_%s" % "RF"[i]

    def build(h):
        y1 = RC_HW + HEAD_H
        F = Field(name, (xs - 4.6, -RC_HW + 1.2, SCREW_Z - 4.6), (xs + 4.6, y1 + 0.8, SCREW_Z + 4.6), h)
        F.add(cyl("Y", (xs, SCREW_Z), SCREW_R, -RC_HW + 1.9, RC_HW + 0.5, rim=0.3))
        F.add(cyl("Y", (xs, SCREW_Z), HEAD_R, RC_HW + 0.06, y1, rim=0.25, rim1=0.7), 0.0)
        F.sub(prism(Poly(fillet_poly(hexagon(xs, SCREW_Z, 1.75), 0.15)), "XZ", y1 - 1.7, y1 + 1), 0.15,
              bbox=bb(xs - 2.6, xs + 2.6, y1 - 2.2, y1 + 0.8, SCREW_Z - 2.6, SCREW_Z + 2.6))
        return F
    return build


# ---------- цевьё с планками ----------
HOUS_HW = 11.5 * TILE_K          # корпус газовой трубки (part_barrel.gas_housing, там единицы до поправки масштаба)
HOUS_BOT = -47.0 * TILE_K
LATCH = (42.0 * TILE_K, -35.0 * TILE_K)   # кольца защёлки трубки на бортах корпуса
FE_X0, FE_X1 = 3.0, 118.5
FE_YI = HOUS_HW + 0.45           # внутренняя грань щеки
FE_T = 3.2
FE_YO = FE_YI + FE_T
FE_ZB = HOUS_BOT - 0.3           # верх нижней полки: под корпусом трубки
FE_ZU = FE_ZB - 3.6              # низ нижней полки
FE_ZT = -19.9                    # верхняя кромка щёк: ниже верха корпуса трубки
SIDE_N = 5
SIDE_X0 = 62.5                   # боковые планки — впереди окна защёлки и переднего болта
SIDE_ZC = -31.0
BOT_N = 10
BOT_X0 = 8.0
CRADLE_X = (113.4, FE_X1)        # ложемент под газовую трубку у переднего торца


def rail_forend(h):
    ytop = FE_YO + PIC_TOP
    zlow = FE_ZU - PIC_TOP
    F = Field("Rail_Forend", (FE_X0 - 1, -ytop - 1, zlow - 1), (FE_X1 + 1, ytop + 1, FE_ZT + 1.2), h)
    shell_ = Poly(fillet_poly([(-FE_YO, FE_ZT), (-FE_YO, FE_ZU), (FE_YO, FE_ZU), (FE_YO, FE_ZT)], [0.8, 2.2, 2.2, 0.8]))
    F.add(prism(shell_, "YZ", FE_X0, FE_X1, rim=0.6))
    # ложемент: поперечная стенка у переднего торца, газовая трубка ложится в полукруглое гнездо
    F.sub(box((FE_X0 - 2, -FE_YI, FE_ZB), (CRADLE_X[0], FE_YI, FE_ZT + 5), 0.0), 0.5)
    F.sub(box((CRADLE_X[0] - 1, -FE_YI, GAS_Z - 1.2), (FE_X1 + 2, FE_YI, FE_ZT + 5), 0.0), 0.5,
          bbox=bb(CRADLE_X[0] - 2, FE_X1 + 1, -FE_YO, FE_YO, GAS_Z - 2.5, FE_ZT + 1.2))
    F.sub(cyl("X", (0.0, GAS_Z), GAS_R + 0.15, CRADLE_X[0] - 2, FE_X1 + 2), 0.4,
          bbox=bb(CRADLE_X[0] - 1.5, FE_X1 + 1, -9.5, 9.5, GAS_Z - 9.5, GAS_Z + 1.0))
    # передние верхние углы щёк срезаны
    cutf = Poly(fillet_poly([(FE_X1 + 2, FE_ZT + 2), (FE_X1 - 3.0, FE_ZT + 2), (FE_X1 + 2, FE_ZT - 3.0)], [0, 0, 0]))
    F.sub(prism(cutf, "XZ", -ytop - 2, ytop + 2), 0.8, bbox=bb(FE_X1 - 6, FE_X1 + 1, -FE_YO - 0.5, FE_YO + 0.5, FE_ZT - 6, FE_ZT + 1.2))
    # нижняя планка: вдоль всего цевья, под рукоятку
    xb1 = BOT_X0 + pic_len(BOT_N)
    F.add(prism(pic_section(lambda u, v: (u, FE_ZU - v)), "YZ", BOT_X0, xb1, rim=0.35), 0.4,
          bbox=bb(BOT_X0 - 1, xb1 + 1, -11.8, 11.8, zlow - 1, FE_ZU + 1.6))
    for xs in pic_slots(BOT_X0, BOT_N):
        F.sub(box((xs - PIC_SLOT / 2, -13, zlow - 2), (xs + PIC_SLOT / 2, 13, zlow + PIC_DEPTH), 0.0), 0.3,
              bbox=bb(xs - 3.6, xs + 3.6, -11.5, 11.5, zlow - 0.9, zlow + PIC_DEPTH + 0.8))
    # боковые планки: слева и справа, под ЛЦУ и фонарь
    xs1 = SIDE_X0 + pic_len(SIDE_N)
    for s in (-1, 1):
        ya, yb = sorted((s * (FE_YO - 1.6), s * (ytop + 1)))
        F.add(prism(pic_section(lambda u, v, s=s: (s * (FE_YO + v), SIDE_ZC + u)), "YZ", SIDE_X0, xs1, rim=0.35), 0.4,
              bbox=bb(SIDE_X0 - 1, xs1 + 1, ya, yb, SIDE_ZC - 11.8, SIDE_ZC + 11.8))
        for xs in pic_slots(SIDE_X0, SIDE_N):
            y0, y1 = sorted((s * (ytop - PIC_DEPTH), s * (ytop + 2)))
            F.sub(box((xs - PIC_SLOT / 2, y0, SIDE_ZC - 13), (xs + PIC_SLOT / 2, y1, SIDE_ZC + 13), 0.0), 0.3,
                  bbox=bb(xs - 3.6, xs + 3.6, min(s * (ytop - PIC_DEPTH - 0.8), s * (ytop + 0.9)),
                          max(s * (ytop - PIC_DEPTH - 0.8), s * (ytop + 0.9)), SIDE_ZC - 11.5, SIDE_ZC + 11.5))
    # окна под кольца защёлки газовой трубки
    F.sub(cyl("Y", LATCH, 8.7, -ytop - 2, ytop + 2), 0.5, bbox=bb(LATCH[0] - 10, LATCH[0] + 10, -FE_YO - 0.5, FE_YO + 0.5, LATCH[1] - 10, LATCH[1] + 10))
    # облегчения в щёках над задним болтом
    for x in (13.0, 22.5, 32.0):
        F.sub(cyl("Y", (x, -26.5), 2.6, -ytop - 2, ytop + 2), 0.4, bbox=bb(x - 4, x + 4, -FE_YO - 0.5, FE_YO + 0.5, -30.5, -22.5))
    # отверстия под сквозные болты; слева — зенковка под потайную головку
    for x in FOREND_BOLT_X:
        F.sub(cyl("Y", (x, FOREND_BOLT_Z), FOREND_BOLT_R + 0.15, -ytop - 2, ytop + 2), 0.15,
              bbox=bb(x - 3.2, x + 3.2, -FE_YO - 0.5, FE_YO + 0.5, FOREND_BOLT_Z - 3.2, FOREND_BOLT_Z + 3.2))
        csk = inter(cone("Y", (x, FOREND_BOLT_Z), FE_YO - 1.9, FOREND_BOLT_R + 0.15, FE_YO, FOREND_BOLT_R + 2.05), slab("Y", FE_YO - 1.9, FE_YO + 1))
        F.sub(csk, 0.15, bbox=bb(x - 5.2, x + 5.2, FE_YO - 2.4, FE_YO + 0.5, FOREND_BOLT_Z - 5.2, FOREND_BOLT_Z + 5.2))
    return F


def forend_bolt(i):
    x, z = FOREND_BOLT_X[i], FOREND_BOLT_Z
    name = "Forend_Bolt_%s" % "AB"[i]

    def build(h):
        F = Field(name, (x - 4.8, -FE_YO - 0.6, z - 4.8), (x + 4.8, FE_YO + 0.6, z + 4.8), h)
        F.add(cyl("Y", (x, z), FOREND_BOLT_R, -FE_YO + 0.08, FE_YO - 1.0, rim=0.3))
        # потайная головка под шестигранник
        head = inter(cone("Y", (x, z), FE_YO - 1.9, FOREND_BOLT_R, FE_YO, FOREND_BOLT_R + 1.9), slab("Y", FE_YO - 1.95, FE_YO - 0.06), r=0.12)
        F.add(head, 0.0)
        F.sub(prism(Poly(fillet_poly(hexagon(x, z, 1.75), 0.15)), "XZ", FE_YO - 1.75, FE_YO + 1), 0.12,
              bbox=bb(x - 2.6, x + 2.6, FE_YO - 2.3, FE_YO + 0.5, z - 2.6, z + 2.6))
        return F
    return build


def parts():
    return [
        dict(name="Cover_Base_F", build=cover_base(True), h=0.08, coll="Крышка", mat="Steel_blued", parent="Top_Cover"),
        dict(name="Cover_Base_R", build=cover_base(False), h=0.08, coll="Крышка", mat="Steel_blued", parent="Top_Cover"),
        dict(name="Rail_Cover", build=rail_cover, h=0.1, coll=K_COVER, coll_hidden=True, mat="Alu_anodized", parent="Top_Cover", adapt=0.05),
        dict(name="Rail_Cover_Screw_R", build=cover_screw(0), h=0.06, coll=K_COVER, coll_hidden=True, mat="Steel_phosphate", parent="Rail_Cover"),
        dict(name="Rail_Cover_Screw_F", build=cover_screw(1), h=0.06, coll=K_COVER, coll_hidden=True, mat="Steel_phosphate", parent="Rail_Cover"),
        dict(name="Rail_Forend", build=rail_forend, h=0.12, coll=K_FOREND, coll_hidden=True, mat="Alu_anodized", parent="Barrel", adapt=0.05),
        dict(name="Forend_Bolt_A", build=forend_bolt(0), h=0.06, coll=K_FOREND, coll_hidden=True, mat="Steel_phosphate", parent="Rail_Forend"),
        dict(name="Forend_Bolt_B", build=forend_bolt(1), h=0.06, coll=K_FOREND, coll_hidden=True, mat="Steel_phosphate", parent="Rail_Forend"),
    ]
