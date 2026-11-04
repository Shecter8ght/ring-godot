# ПП по мотивам KRISS Vector Gen II: затвор (виден в окне выброса справа) и рукоятка заряжания слева (в пазу коробки,
# не ходит при стрельбе — тянет затвор только рукой). Затвор: зеркало с чашкой под донце .45 ACP, канал ударника,
# выбрасыватель справа, пазы направляющих по бокам. Рукоятка: ползун в пазу, плоский рычаг по борту, выступ под пальцы
# у переднего торца (снимок KRISS A, владельца 01/02/07: выступ ≈ 12 мм наружу).
import math
import bpy
from lib import (MM, HALF_W, FRONT_FACE_X, prism_xz, prism_xy, prism_yz, box, cyl, lathe, boolean, fillet, finish,
                 finish_small, v)
from part_receiver import CH_SLOT_Z, CAVITY, rounded_rect_xz

BOLT_X = (-64.3, -0.3)            # затвор в переднем положении: зеркало — на казённом срезе (X 0)
BOLT_HALF_W = 13.2
BOLT_Z = (-10.5, 30.0)
BOLT_TRAVEL = 45.0               # ход затвора назад (до задней стенки полости)
CH_X = (40.0, 104.0)             # рукоятка заряжания в переднем положении (снимок A)
CH_TRAVEL = BOLT_TRAVEL + 4.0    # рукоятка доходит до упора чуть дальше затвора
CH_KNOB_X = (83.0, 103.0)
CH_KNOB_OUT = 12.0               # выступ наружу от борта


def bolt(C):
    x0, x1 = BOLT_X
    z0, z1 = BOLT_Z
    b = prism_xz("Bolt", rounded_rect_xz(x0, x1, z0, z1, 3.0), -BOLT_HALF_W, BOLT_HALF_W, C, "Steel_nitride")
    # зеркало: чашка под донце гильзы (Ø12.4, глубина 1.3) и канал ударника Ø2.4
    cup = cyl("_cup", -1.3, 1.0, 6.2, C, seg=64)
    boolean(b, cup)
    fp = cyl("_fp", -20.0, 0.5, 1.2, C, seg=24)
    boolean(b, fp)
    # пазы под направляющие коробки по обоим бокам (Z 22–25, глубина 1.4)
    for s in (1, -1):
        y0, y1 = (BOLT_HALF_W - 1.4, BOLT_HALF_W + 2) if s > 0 else (-BOLT_HALF_W - 2, -BOLT_HALF_W + 1.4)
        g = prism_xz("_rail", rounded_rect_xz(x0 - 2, x1 + 2, 22.0, 25.0, 1.4), y0, y1, C)
        boolean(b, g)
    # окно под выбрасыватель справа (−Y) у зеркала
    w = box("_extw", -24.0, 1.0, -BOLT_HALF_W - 2, -BOLT_HALF_W + 1.6, -2.5, 5.5, C)
    boolean(b, w)
    # выемка снизу под верхний патрон магазина (затвор проходит над губками)
    u = prism_yz("_feed", fillet([(-7.5, -12.0), (7.5, -12.0), (5.5, -7.5), (-5.5, -7.5)], [0, 0, 2.0, 2.0], 4),
                 x0 + 8.0, x1 - 6.0, C)
    boolean(b, u)
    finish_small(b, w=0.8, seg=3)
    # выбрасыватель: пластина с когтем у зеркала, на штифте
    e = prism_xy("Extractor", fillet([(-23.0, -BOLT_HALF_W + 1.4), (0.4, -BOLT_HALF_W + 1.4), (0.4, -BOLT_HALF_W + 0.2),
                                      (-1.0, -BOLT_HALF_W - 0.2), (-23.0, -BOLT_HALF_W - 0.2)], [1.0, 0.2, 0.3, 0.3, 1.0], 3),
                 -2.3, 5.3, C, "Steel_bare")
    finish_small(e, w=0.25, seg=3)
    # штифт стоит вертикально в выбрасывателе: cyl(axis Z) — x0..x1 по Z, cy/cz — X и Y
    pin = cyl("Extractor_pin", -2.6, 5.6, 1.0, C, "Steel_bare", seg=24, cy=-17.0, cz=-BOLT_HALF_W + 0.6, axis="Z")
    finish_small(pin, w=0.15, seg=2)
    pin["owner"] = "Extractor,Bolt"
    e["owner"] = "Bolt"
    return b, e, pin


def charging_handle(C):
    z0, z1 = CH_SLOT_Z
    x0, x1 = CH_X
    # ползун в пазу (зазор 0.25 по высоте и до дна паза)
    sl = prism_xz("Charging_handle_slider", rounded_rect_xz(x0, x1 - 2.0, z0 + 0.4, z1 - 0.4, 1.6),
                  HALF_W - 4.75, HALF_W + 0.4, C, "Steel_black")
    finish_small(sl, w=0.35, seg=3)
    # рычаг вдоль борта: плоская полоса 3 мм, к переду утолщается в выступ под пальцы
    arm = prism_xz("Charging_handle", fillet([(x0 + 2.0, 20.0), (CH_KNOB_X[0], 20.0), (CH_KNOB_X[0] + 2.0, 21.5),
                                              (CH_KNOB_X[1], 22.0), (CH_KNOB_X[1], 30.6), (CH_KNOB_X[0] + 3.0, 30.8),
                                              (CH_KNOB_X[0], 27.8), (x0 + 2.0, 26.5)],
                                             [2.5, 3.0, 2.0, 2.5, 3.0, 3.0, 4.0, 2.5], 5),
                   HALF_W + 0.4, HALF_W + 3.4, C, "Steel_black")
    # выступ под пальцы: наружу на 12 мм, клином назад, с поперечными рёбрами
    knob_plan = fillet([(CH_KNOB_X[0] + 1.0, HALF_W + 3.0), (CH_KNOB_X[1], HALF_W + 3.0), (CH_KNOB_X[1], HALF_W + CH_KNOB_OUT),
                        (CH_KNOB_X[1] - 6.0, HALF_W + CH_KNOB_OUT)], [1.5, 2.0, 2.5, 4.0], 5)
    k = prism_xy("_knob", knob_plan, 22.5, 30.4, C)
    boolean(arm, k, op="UNION")
    for i in range(4):
        xg = CH_KNOB_X[1] - 3.5 - i * 3.2
        g = prism_xy("_kg", fillet([(xg - 0.8, HALF_W + 6.0), (xg + 0.8, HALF_W + 6.0), (xg + 0.8, HALF_W + 20.0),
                                     (xg - 0.8, HALF_W + 20.0)], [0.8, 0.8, 0, 0], 3), 29.6, 33.0, C)
        boolean(arm, g)
    finish_small(arm, w=0.6, seg=3)
    sl["owner"] = "Charging_handle"
    return sl, arm


def build(ctx):
    C = ctx["coll"]["Bolt_group"]
    b, e, pin = bolt(C)
    sl, arm = charging_handle(ctx["coll"]["Controls"])
    return {"bolt": b, "extractor": e, "ch": arm, "ch_slider": sl}
