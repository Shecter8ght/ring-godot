# ПП по мотивам KRISS Vector: складные прицельные — целик и мушка на верхней планке (требование владельца: подвижные,
# складываемые). Своя форма в манере низкопрофильных складных: основание с губками по планке 1913 и поперечным
# болтом в пазу, стойка на поперечной оси. Владелец 05.11 (снимки 1–3): «посвободнее, окошко побольше, воздуха в
# кружочке больше» — у целика кольцо диоптра с окном Ø5 на перекладине между высокими ушами; у мушки между ушами
# рифлёный барабан высоты с маховичком справа, на нём тонкий столбик 1.1 мм на пластине с V-образными плечиками.
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
FRONT = {"x0": 82.0, "x1": 104.0, "hinge_x": 100.5, "slot_x": 87.6, "fold": -1, "drum_pocket": True}
BOLT_Z = 56.7                   # поперечный болт — в пазу планки (дно паза Z 50.1)
EAR_IN, EAR_OUT = 6.6, 9.8      # уши стойки: внутренняя и наружная кромки (между ушами — 13.2 воздуха)
RING_R, APERTURE_R = 4.3, 2.5   # кольцо диоптра и его окно Ø5 (было Ø2.2 — «окошко побольше»)
DRUM_Z, DRUM_R = HINGE_Z + 6.1, 2.0   # барабан высоты мушки поперёк стойки
POST_HW = 0.55                  # полуширина столбика мушки


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
    if d.get("drum_pocket"):
        # сложенная мушка ложится барабаном и маховичком (выступают из стойки вниз) в нишу; болт в пазу — дальше 1.6 мм
        xd = hx + (DRUM_Z - HINGE_Z) * d["fold"]
        c = prism_xz("_drp", fillet([(xd - 3.3, 58.6), (xd + 3.3, 58.6), (xd + 3.3, BASE_TOP + 2), (xd - 3.3, BASE_TOP + 2)],
                                    [0.8, 0.8, 0, 0], 3), -7.3, 7.3, C)
        boolean(b, c)
    finish_small(b, w=0.35, seg=3)
    # поперечный болт с головкой слева и гайкой справа — упор в паз планки
    bolt = cyl(f"{name}_bolt", -14.2, 14.2, 2.0, C, "Steel_black", seg=40, cy=d["slot_x"], cz=BOLT_Z, axis="Y")
    hl = lathe(f"{name}_bolt_head", [(13.0, 0.0), (13.0, 3.6), (14.2, 3.6), (15.4, 2.5), (15.4, 0.0)], C, "Steel_black",
               seg=48)
    hl.rotation_euler = (0, 0, math.pi / 2)
    hl.location = v(d["slot_x"], 0, BOLT_Z)
    from lib import apply_transform
    apply_transform(hl)
    hexn = prism_xz(f"{name}_nut", [(d["slot_x"] + 3.4 * math.cos(math.pi / 3 * k + math.pi / 6),
                                     BOLT_Z + 3.4 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)],
                    -15.4, -13.0, C, "Steel_black")
    for o, w in ((bolt, 0.3), (hl, 0.3), (hexn, 0.45)):
        finish_small(o, w=w, seg=3)
        o["owner"] = name + ",Receiver"
    pin = cyl(f"{name}_hinge_pin", -13.6, 13.6, 1.15, C, "Steel_bare", seg=32, cy=d["hinge_x"], cz=HINGE_Z, axis="Y")
    finish_small(pin, w=0.1, seg=2)
    pin["owner"] = name + "," + name.replace("_base", "_leaf")
    b["owner"] = "Receiver"
    return b


def leaf_section(rear):
    """Стойка в сечении YZ (от оси вверх): уши EAR_IN…EAR_OUT, между ними — перемычка на высоте 4.5 над осью; у целика
    уши выше кольца диоптра, у мушки — выше столбика."""
    hz = HINGE_Z
    top = SIGHT_Z + (5.0 if rear else 3.0) - hz
    yi, yo, web = EAR_IN, EAR_OUT, 4.5
    # низ стойки (±4.6, до −1.2) целиком уходит в колено R 2.6 длиной ±5.0: прежде низ стойки (−2.6) касался колена
    # по касательной, а торцы колена совпадали с боками стойки (±5.0) — после фаски иглы над шарниром (сверка v05 Н1–Н3)
    pts = [(-4.6, -1.2), (4.6, -1.2), (4.6, 2.4), (yo, 4.6), (yo, top - 3.0), (yo - 1.2, top), (yi + 0.4, top), (yi, web),
           (-yi, web), (-yi - 0.4, top), (-yo + 1.2, top), (-yo, top - 3.0), (-yo, 4.6), (-4.6, 2.4)]
    return [(y, z + hz) for y, z in fillet(pts, [0.6, 0.6, 1.0, 1.5, 1.5, 1.2, 0.8, 1.2, 1.2, 0.8, 1.2, 1.5, 1.5, 1.0], 4)]


def _knurl_collar(name, y0, y1, r, teeth, depth, x, z, C, mat):
    """Маховичок с прямым рифлением: звёздчатый контур (зубья — косинусом, без острых) выдавлен вдоль Y."""
    n = teeth * 8
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        rr = r - depth * (0.5 - 0.5 * math.cos(teeth * a))
        pts.append((x + rr * math.cos(a), z + rr * math.sin(a)))
    o = prism_xz(name, pts, y0, y1, C, mat, smooth=True)
    finish_small(o, w=0.25, seg=2, angle=40.0)
    return o


def drum(name, hx, C):
    """Барабан высоты мушки: винт с кольцевыми витками между ушами и маховичок с прямым рифлением справа (снимок 3),
    на барабане — столбик. Отдельные детали стойки, двигаются вместе с ней (part_rig)."""
    import mathutils
    y_l, y_r = EAR_IN + 0.3, -(EAR_IN - 1.6)
    prof = [(y_r, 0.0), (y_r, DRUM_R - 0.35)]
    n = 120
    for i in range(n + 1):
        t = y_r + 0.35 + (y_l - 0.35 - (y_r + 0.35)) * i / n
        prof.append((t, DRUM_R - 0.22 * (0.5 - 0.5 * math.cos(2 * math.pi * (t - y_r) / 0.9))))
    prof += [(y_l, DRUM_R - 0.35), (y_l, 0.0)]
    o = lathe(name, prof, C, "Steel_black", seg=40, cy=0.0, cz=0.0)
    # ось профиля — X; кладём её поперёк (Y) и переносим на высоту барабана
    o.data.transform(mathutils.Matrix.Rotation(math.pi / 2, 4, "Z"))
    o.data.transform(mathutils.Matrix.Translation(v(hx, 0.0, DRUM_Z)))
    o.data.update()
    wheel = _knurl_collar(name + "_wheel", -(EAR_IN + 0.3), -(EAR_IN - 1.8), DRUM_R + 0.6, 24, 0.22, hx, DRUM_Z, C,
                          "Steel_black")
    # столбик на пластине: плечики V-образно сходятся к столбику, верх столбика — линия прицеливания
    zw, zv = SIGHT_Z - 2.6, SIGHT_Z - 4.0
    post = prism_yz(name.replace("_drum", "_post"),
                    fillet([(-2.6, DRUM_Z), (2.6, DRUM_Z), (2.6, zw), (POST_HW, zv), (POST_HW, SIGHT_Z),
                            (-POST_HW, SIGHT_Z), (-POST_HW, zv), (-2.6, zw)], [0, 0, 0.5, 0.35, 0.25, 0.25, 0.35, 0.5], 4),
                    hx - 0.8, hx + 0.8, C, "Steel_black")
    finish_small(post, w=0.2, seg=2)
    return [o, wheel, post]


def leaf(name, d, rear, C):
    hx = d["hinge_x"]
    x0, x1 = hx - LEAF_T / 2, hx + LEAF_T / 2
    o = prism_yz(name, leaf_section(rear), x0, x1, C, "Alu_anodized")
    # кулак на оси (между проушинами основания) — цилиндр вдоль Y
    k = cyl("_kn", -5.0, 5.0, 2.6, C, seg=40, cy=hx, cz=HINGE_Z, axis="Y")
    boolean(o, k, op="UNION")
    parts = []
    if rear:
        # кольцо диоптра на стебле и перекладина между ушами (снимок 2), окно Ø5 — «воздуха больше»
        stem = prism_yz("_stem", fillet([(-2.0, HINGE_Z + 4.0), (2.0, HINGE_Z + 4.0), (2.0, SIGHT_Z - 3.0),
                                         (-2.0, SIGHT_Z - 3.0)], [0.6, 0.6, 0, 0], 3), x0 - 0.15, x1 + 0.15, C)
        boolean(o, stem, op="UNION")
        zb = SIGHT_Z - RING_R + 0.5
        bar = prism_yz("_bar", [(-(EAR_IN + 0.35), zb - 2.0), (EAR_IN + 0.35, zb - 2.0), (EAR_IN + 0.35, zb),
                                (-(EAR_IN + 0.35), zb)], x0 + 0.3, x1 - 0.3, C)
        boolean(o, bar, op="UNION")
        ring = cyl("_ring", x0 - 0.3, x1 + 0.3, RING_R, C, seg=64, cy=0.0, cz=SIGHT_Z)
        boolean(o, ring, op="UNION")
        hole = cyl("_ap", x0 - 2, x1 + 2, APERTURE_R, C, seg=48, cy=0.0, cz=SIGHT_Z)
        boolean(o, hole)
    else:
        parts = drum(name.replace("_leaf", "_drum"), hx, C)
    hp = cyl("_hp", -14, 14, 1.2, C, seg=32, cy=hx, cz=HINGE_Z, axis="Y")
    boolean(o, hp)
    finish_small(o, w=0.3, seg=3)
    if rear:
        # грани целика вокруг кольца и перекладины — с вырезами: при показе косые линии от кольца к ушам — мелкой сеткой
        from lib import grid_split_local, weighted, apply_all
        # только кольцо, перекладина и уши — колено не трогать
        grid_split_local(o, (hx, 0.0, SIGHT_Z), 10.5, (1, 2), step=1.0)
        from lib import mark_sharp
        # 12°: первый сегмент фаски 0.3 отходит от плоскости меньше 25° — его тоже острым, иначе пятна на кольце
        mark_sharp(o, 12.0)
        weighted(o)
        apply_all(o)
    set_origin(o, (hx, 0, HINGE_Z))
    for p_ in parts:
        p_["owner"] = name + "," + ",".join(q.name for q in parts if q is not p_)
    return o, parts


def build(ctx):
    C = ctx["coll"]["Sights"]
    rb = base("Rear_sight_base", REAR, C)
    rl, _ = leaf("Rear_sight_leaf", REAR, True, C)
    fb = base("Front_sight_base", FRONT, C)
    fl, fparts = leaf("Front_sight_leaf", FRONT, False, C)
    return {"rear_leaf": rl, "front_leaf": fl, "front_parts": fparts}
