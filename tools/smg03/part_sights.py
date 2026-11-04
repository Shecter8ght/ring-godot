# ПП по мотивам KRISS Vector: складные прицельные — целик и мушка на верхней планке (требование владельца: подвижные,
# складываемые). Своя форма в манере низкопрофильных складных: основание с губками по планке 1913 и поперечным
# болтом в пазу, стойка на поперечной оси; у целика — диоптр Ø2.2 в кольце между ушами, у мушки — столбик между ушами.
# Положения по снимку KRISS A (сложены): целик X −228…−206, мушка X 82…104. Целик складывается вперёд, мушка — назад.
import math
import bpy
from lib import (MM, RAIL_TOP, RAIL_HALF_W, fillet, prism_yz, prism_xz, cyl, lathe, boolean, rounded_prism,
                 finish_small, set_origin, v)

BASE_TOP = 63.0
HINGE_Z = 61.5
LEAF_T = 3.4                     # толщина стойки по X
SIGHT_Z = 76.0                   # линия прицеливания: центр диоптра = верх мушки
REAR = {"x0": -228.0, "x1": -206.0, "hinge_x": -224.5, "slot_x": -212.4, "fold": 1}
FRONT = {"x0": 82.0, "x1": 104.0, "hinge_x": 100.5, "slot_x": 87.6, "fold": -1}
BOLT_Z = 56.7                   # поперечный болт — в пазу планки (дно паза Z 50.1)


def base_section():
    """Сечение основания (y, z): губки обжимают «ласточкин хвост» планки (самое широкое место ±10.6 на Z 50.2)."""
    zv = RAIL_TOP - 2.8
    pts = [(-13.2, 48.4), (-9.4, 48.4), (-11.0, zv), (-7.9, RAIL_TOP + 0.05), (7.9, RAIL_TOP + 0.05), (11.0, zv),
           (9.4, 48.4), (13.2, 48.4), (13.2, BASE_TOP - 2.2), (11.0, BASE_TOP), (-11.0, BASE_TOP), (-13.2, BASE_TOP - 2.2)]
    return fillet(pts, [0.9, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.9, 1.4, 2.0, 2.0, 1.4], 4)


def base(name, d, C):
    from part_receiver import rail_profile
    blk = fillet([(-13.2, RAIL_TOP - 5.2), (13.2, RAIL_TOP - 5.2), (13.2, BASE_TOP), (-13.2, BASE_TOP)],
                 [1.2, 1.2, 2.0, 2.0], 5)
    b = prism_yz(name, blk, d["x0"], d["x1"], C, "Alu_anodized")
    # губки — точно по профилю планки 1913 с зазором 0.15, снизу вырез открыт
    rp = rail_profile(RAIL_TOP + 0.15, RAIL_TOP - 20.0, RAIL_HALF_W + 0.15)
    c = prism_yz("_railcut", rp, d["x0"] - 2, d["x1"] + 2, C)
    boolean(b, c)
    # проушины оси: вырез под кулак стойки посередине (±5.2), сама ось — сквозной канал Ø2.4
    hx = d["hinge_x"]
    c = prism_xz("_knk", fillet([(hx - 3.6, HINGE_Z - 3.0), (hx + 3.6, HINGE_Z - 3.0), (hx + 3.6, BASE_TOP + 2),
                                 (hx - 3.6, BASE_TOP + 2)], [1.2, 1.2, 0, 0], 4), -5.4, 5.4, C)
    boolean(b, c)
    h = cyl("_hp", -14, 14, 1.2, C, seg=32, cy=hx, cz=HINGE_Z, axis="Y")
    boolean(b, h)
    # ложе сложенной стойки: неглубокая выемка в верхе основания
    zb = HINGE_Z - LEAF_T / 2 - 0.35
    c = prism_xz("_bed", fillet([(min(d["x0"], d["x1"]) - 2, zb), (max(d["x0"], d["x1"]) + 2, zb),
                                 (max(d["x0"], d["x1"]) + 2, BASE_TOP + 2), (min(d["x0"], d["x1"]) - 2, BASE_TOP + 2)],
                                [0.8, 0.8, 0, 0], 3), -10.4, 10.4, C)
    boolean(b, c)
    finish_small(b, w=0.35, seg=3)
    # поперечный болт с головкой слева и гайкой справа — упор в паз планки
    bolt = cyl(f"{name}_bolt", -14.2, 14.2, 2.0, C, "Steel_black", seg=40, cy=d["slot_x"], cz=BOLT_Z, axis="Y")
    hl = lathe(f"{name}_bolt_head", [(13.0, 0.0), (13.0, 3.6), (14.6, 3.6), (15.4, 3.0), (15.4, 0.0)], C, "Steel_black",
               seg=48)
    hl.rotation_euler = (0, 0, math.pi / 2)
    hl.location = v(d["slot_x"], 0, BOLT_Z)
    from lib import apply_transform
    apply_transform(hl)
    hexn = prism_xz(f"{name}_nut", [(d["slot_x"] + 3.4 * math.cos(math.pi / 3 * k + math.pi / 6),
                                     BOLT_Z + 3.4 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)],
                    -15.4, -13.0, C, "Steel_black")
    for o in (bolt, hl, hexn):
        finish_small(o, w=0.15, seg=2)
        o["owner"] = name + ",Receiver"
    pin = cyl(f"{name}_hinge_pin", -13.6, 13.6, 1.15, C, "Steel_bare", seg=32, cy=d["hinge_x"], cz=HINGE_Z, axis="Y")
    finish_small(pin, w=0.1, seg=2)
    pin["owner"] = name + "," + name.replace("_base", "_leaf")
    b["owner"] = "Receiver"
    return b


def leaf_section(rear):
    """Стойка в сечении YZ (от оси вверх): уши ±8…±10, между ними — кольцо диоптра (целик) или столбик (мушка)."""
    hz = HINGE_Z
    top = SIGHT_Z + 5.0 - hz
    pts = [(-5.0, -2.6), (5.0, -2.6), (5.0, 2.4), (9.8, 4.6), (9.8, top - 3.0), (8.6, top), (6.2, top), (5.4, 4.5),
           (-5.4, 4.5), (-6.2, top), (-8.6, top), (-9.8, top - 3.0), (-9.8, 4.6), (-5.0, 2.4)]
    return [(y, z + hz) for y, z in fillet(pts, [1.2, 1.2, 1.0, 1.5, 1.5, 1.2, 0.8, 1.2, 1.2, 0.8, 1.2, 1.5, 1.5, 1.0], 4)]


def leaf(name, d, rear, C):
    hx = d["hinge_x"]
    x0, x1 = hx - LEAF_T / 2, hx + LEAF_T / 2
    o = prism_yz(name, leaf_section(rear), x0, x1, C, "Alu_anodized")
    # кулак на оси (между проушинами основания) — цилиндр вдоль Y
    k = cyl("_kn", -5.0, 5.0, 2.6, C, seg=40, cy=hx, cz=HINGE_Z, axis="Y")
    boolean(o, k, op="UNION")
    if rear:
        # кольцо диоптра на стебле
        stem = prism_yz("_stem", fillet([(-1.6, HINGE_Z + 4.0), (1.6, HINGE_Z + 4.0), (1.6, SIGHT_Z), (-1.6, SIGHT_Z)],
                                        [0.6, 0.6, 0, 0], 3), x0, x1, C)
        boolean(o, stem, op="UNION")
        ring = cyl("_ring", x0, x1, 3.4, C, seg=48, cy=0.0, cz=SIGHT_Z)
        boolean(o, ring, op="UNION")
        hole = cyl("_ap", x0 - 2, x1 + 2, 1.1, C, seg=32, cy=0.0, cz=SIGHT_Z)
        boolean(o, hole)
    else:
        post = prism_yz("_post", fillet([(-1.0, HINGE_Z + 4.0), (1.0, HINGE_Z + 4.0), (0.9, SIGHT_Z), (-0.9, SIGHT_Z)],
                                        [0.4, 0.4, 0.3, 0.3], 3), x0, x1, C)
        boolean(o, post, op="UNION")
    hp = cyl("_hp", -14, 14, 1.2, C, seg=32, cy=hx, cz=HINGE_Z, axis="Y")
    boolean(o, hp)
    finish_small(o, w=0.3, seg=3)
    set_origin(o, (hx, 0, HINGE_Z))
    return o


def build(ctx):
    C = ctx["coll"]["Sights"]
    rb = base("Rear_sight_base", REAR, C)
    rl = leaf("Rear_sight_leaf", REAR, True, C)
    fb = base("Front_sight_base", FRONT, C)
    fl = leaf("Front_sight_leaf", FRONT, False, C)
    return {"rear_leaf": rl, "front_leaf": fl}
