# AR-15: складные прицелы на планках 1913 (своя форма в манере листинга Fab, без надписей).
# Целик — на планке ресивера: основание с губками по профилю планки, поперечный болт в пазу (упор отдачи),
# откидная стойка на оси вдоль Y (складывается вперёд), перекидной диоптр с двумя отверстиями (малое — прицельное,
# большое — для ближней стрельбы), барабан поправки по горизонтали справа, кнопка фиксатора слева.
# Мушка — на планке цевья: такое же основание, стойка складывается назад, мушка в защитных «ушах»,
# барабан высоты вокруг резьбового стебля мушки. Линия прицеливания — z = SIGHT_Z над осью канала.
import math
import bpy
from lib import (MM, RAIL_TOP, REAR_SIGHT_X, FRONT_SIGHT_X, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl,
                 lathe, boolean, finish, auto_sharp, apply_transform, set_parent, set_origin)

SIGHT_Z = 64.5                  # линия прицеливания над осью канала
BASE_TOP = 38.0                 # верх оснований
REAR_HINGE = (REAR_SIGHT_X - 15.0, 42.5)      # (x, z) оси стойки целика
REAR_BASE_X = (REAR_SIGHT_X - 21.0, REAR_SIGHT_X + 21.0)
REAR_BOLT_X = -146.0            # центр паза планки ресивера (14 + 10·k)
FRONT_HINGE = (FRONT_SIGHT_X + 11.0, 43.5)
FRONT_BASE_X = (FRONT_SIGHT_X - 16.0, FRONT_SIGHT_X + 16.0)
FRONT_BOLT_X = 264.0            # центр паза планки цевья
AP_AXIS_Z = 59.0                # ось перекидного диоптра
AP_OFFSET = SIGHT_Z - AP_AXIS_Z # отверстия диоптра — на этом расстоянии от оси
LUG_IN, LUG_OUT = 4.5, 9.8      # щёки шарнира по Y
KNUCKLE_HALF = 4.3              # кулак стойки по Y


def _base_section():
    """Сечение основания (y, z): губки обжимают «ласточкин хвост» планки, плоский верх."""
    pts = [(-13.5, 25.8), (-8.9, 25.8), (-11.1, 28.2), (-7.9, RAIL_TOP + 0.05), (7.9, RAIL_TOP + 0.05), (11.1, 28.2),
           (8.9, 25.8), (13.5, 25.8), (13.5, 35.5), (11.0, BASE_TOP), (-11.0, BASE_TOP), (-13.5, 35.5)]
    return fillet(pts, [0.8, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.8, 1.2, 1.6, 1.6, 1.2], 3)


def _knurl_xz(cx, cz, r_out, r_in, n):
    pts = []
    for k in range(n):
        a0 = 2 * math.pi * k / n
        da = 2 * math.pi / n
        for t, r in ((0.0, r_in), (0.2, r_out), (0.5, r_out), (0.7, r_in)):
            a = a0 + da * t
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return pts


def _base(name, x0, x1, hinge, bolt_x, button_x, C):
    hx, hz = hinge
    b = prism_yz(name, _base_section(), x0, x1, C, "Alu_anodized")
    # скос передней и задней кромки сверху
    for xe, s in ((x0, -1), (x1, 1)):
        c = prism_xz(f"cut_{name}_bevel{s}", [(xe - 3.0 * s, BASE_TOP + 1), (xe + 1.0 * s, BASE_TOP + 1), (xe + 1.0 * s, BASE_TOP - 3.5)],
                     -20, 20, C)
        boolean(b, c)
    # щёки шарнира
    for s in (-1, 1):
        prof = [(hx - 4.5, BASE_TOP - 1.0), (hx + 4.5, BASE_TOP - 1.0)] + arc_pts(hx, hz, 4.5, 0, 180, 12)
        y0, y1 = (LUG_IN, LUG_OUT) if s > 0 else (-LUG_OUT, -LUG_IN)
        lug = prism_xz(f"{name}_lug{s}", prof, y0, y1, C, "Alu_anodized")
        boolean(b, lug, "UNION")
    boolean(b, cyl(f"cut_{name}_hinge", -20, 20, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    # ложе под сложенную стойку сверху
    bx0, bx1 = (hx + 5.2, x1 - 3.6) if hx < (x0 + x1) / 2 else (x0 + 3.6, hx - 5.2)
    bed = prism_xy(f"cut_{name}_bed", fillet([(bx0, -10.0), (bx1, -10.0), (bx1, 10.0), (bx0, 10.0)], 2.0, 4), BASE_TOP - 0.9, BASE_TOP + 2, C)
    boolean(b, bed)
    # продольные канавки по бокам (облегчение)
    for s in (-1, 1):
        y0, y1 = (12.7, 20.0) if s > 0 else (-20.0, -12.7)
        g = prism_xz(f"cut_{name}_groove{s}", fillet([(x0 + 5.0, 31.6), (x1 - 5.0, 31.6), (x1 - 5.0, 33.6), (x0 + 5.0, 33.6)], 0.9, 3), y0, y1, C)
        boolean(b, g)
    # отверстие поперечного болта (через губки, болт проходит в пазу планки)
    boolean(b, cyl(f"cut_{name}_bolt", -20, 20, 1.85, C, seg=20, cy=bolt_x, cz=29.95, axis="Y"))
    # гнездо кнопки фиксатора слева
    boolean(b, cyl(f"cut_{name}_btn", 11.5, 20, 2.55, C, seg=24, cy=button_x, cz=34.0, axis="Y"))
    finish(b, w=0.3, seg=2, angle=35)
    set_origin(b, ((x0 + x1) / 2, 0.0, RAIL_TOP))
    # болт: шестигранная головка слева, гайка справа
    bolt = cyl(f"{name}_bolt", -15.6, 15.6, 1.75, C, "Steel_black", seg=20, cy=bolt_x, cz=29.95, axis="Y", ch=0.3)
    hexa = [(bolt_x + 3.0 * math.cos(math.radians(30 + 60 * k)), 29.95 + 3.0 * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    head = prism_xz(f"{name}_bolt_head", hexa, 13.4, 15.8, C, "Steel_black")
    boolean(head, cyl("cut_head_hex", 15.0, 17, 1.1, C, seg=6, cy=bolt_x, cz=29.95, axis="Y"))
    boolean(bolt, head, "UNION")
    nut = prism_xz(f"{name}_bolt_nut", hexa, -15.8, -13.4, C, "Steel_black")
    boolean(bolt, nut, "UNION")
    finish(bolt, w=0.2, seg=2, angle=35)
    set_parent(bolt, b)
    # кнопка фиксатора стойки
    btn = lathe(f"{name}_button", [(11.6, 0.0), (11.6, 2.4), (14.6, 2.4), (15.0, 2.0), (15.0, 0.0)], C, "Steel_black", seg=24)
    btn.rotation_euler = (0, 0, math.pi / 2)
    apply_transform(btn)
    btn.location = (button_x * MM, 0, 34.0 * MM)
    apply_transform(btn)
    boolean(btn, box("cut_btn_dimple", button_x - 1.2, button_x + 1.2, 14.6, 16, 33.5, 34.5, C))
    auto_sharp(btn, 35)
    set_origin(btn, (button_x, 13.0, 34.0))
    set_parent(btn, b)
    # ось шарнира
    pin = cyl(f"{name}_hinge_pin", -LUG_OUT - 0.2, LUG_OUT + 0.2, 1.2, C, "Steel_black", seg=16, cy=hx, cz=hz, axis="Y", ch=0.2)
    set_parent(pin, b)
    return b


def build(ctx):
    C = ctx["coll"]["Sights"]
    o = {}
    o.update(rear_sight(C))
    o.update(front_sight(C))
    return o


def rear_sight(C):
    o = {}
    hx, hz = REAR_HINGE
    base = _base("Rear_sight_base", REAR_BASE_X[0], REAR_BASE_X[1], REAR_HINGE, REAR_BOLT_X, hx + 9.0, C)
    o["rear_base"] = base
    # стойка (поднята): кулак у оси, тело с «ушами» вокруг диоптра
    top = SIGHT_Z + 7.5
    poly = [(-KNUCKLE_HALF, hz), (KNUCKLE_HALF, hz), (KNUCKLE_HALF, hz + 6.5), (9.8, hz + 10.5), (9.8, top - 2.0), (8.3, top),
            (6.4, top), (6.4, hz + 14.0), (-6.4, hz + 14.0), (-6.4, top), (-8.3, top), (-9.8, top - 2.0), (-9.8, hz + 10.5),
            (-KNUCKLE_HALF, hz + 6.5)]
    leaf = prism_yz("Rear_sight_leaf", fillet(poly, [0, 0, 1.0, 1.5, 0.6, 0.8, 0.5, 1.2, 1.2, 0.5, 0.8, 0.6, 1.5, 1.0], 3),
                    hx - 3.2, hx + 3.2, C, "Alu_anodized")
    kn = cyl("rear_knuckle", -KNUCKLE_HALF, KNUCKLE_HALF, 4.0, C, "Alu_anodized", seg=32, cy=hx, cz=hz, axis="Y")
    boolean(leaf, kn, "UNION")
    boolean(leaf, cyl("cut_rear_knuckle", -10, 10, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    boolean(leaf, cyl("cut_rear_ap_axis", -12, 12, 0.95, C, seg=16, cy=hx, cz=AP_AXIS_Z, axis="Y"))
    # рифление на верхних торцах «ушей» (палец откидывает стойку)
    for k in range(4):
        xx = hx - 2.4 + k * 1.6
        boolean(leaf, box(f"cut_rear_ser{k}", xx - 0.3, xx + 0.3, -12, 12, top - 0.5, top + 1, C))
    finish(leaf, w=0.25, seg=2, angle=35)
    set_origin(leaf, (hx, 0.0, hz))
    set_parent(leaf, base)
    o["rear_leaf"] = leaf
    # перекидной диоптр: Г-образный, ось вдоль Y; вертикальное плечо — малое отверстие, горизонтальное — большое
    ax, az = hx, AP_AXIS_Z
    ap_prof = fillet([(ax - 1.0, az - 0.6), (ax - AP_OFFSET - 4.8, az - 0.6), (ax - AP_OFFSET - 4.8, az + 1.4), (ax - 1.0, az + 1.4),
                      (ax - 1.0, az + AP_OFFSET + 4.6), (ax + 1.0, az + AP_OFFSET + 4.6), (ax + 1.0, az - 0.6)],
                     [0, 1.8, 0.8, 0.6, 1.4, 1.4, 0], 3)
    ap = prism_xz("Rear_sight_aperture", ap_prof, -6.0, 6.0, C, "Alu_anodized")
    hub = cyl("ap_hub", -6.0, 6.0, 2.0, C, "Alu_anodized", seg=24, cy=ax, cz=az, axis="Y")
    boolean(ap, hub, "UNION")
    boolean(ap, cyl("cut_ap_axis", -8, 8, 0.95, C, seg=16, cy=ax, cz=az, axis="Y"))
    small = lathe("cut_ap_small", [(ax - 3, 0.0), (ax - 3, 1.6), (ax - 1.3, 1.6), (ax - 0.6, 0.95), (ax + 3, 0.95), (ax + 3, 0.0)],
                  C, None, seg=24, cy=0.0, cz=SIGHT_Z)
    boolean(ap, small)
    big = cyl("cut_ap_big", az - 3, az + 4, 2.5, C, seg=32, cy=ax - AP_OFFSET, cz=0.0, axis="Z")
    boolean(ap, big)
    finish(ap, w=0.2, seg=2, angle=35)
    set_origin(ap, (ax, 0.0, az))
    set_parent(ap, leaf)
    o["rear_aperture"] = ap
    apin = cyl("Rear_sight_aperture_pin", -9.9, 9.9, 0.9, C, "Steel_black", seg=12, cy=ax, cz=az, axis="Y", ch=0.15)
    set_parent(apin, leaf)
    # барабан поправки по горизонтали справа (−Y): рифлёный, ось вдоль Y
    dz = hz + 9.5
    drum = prism_xz("Rear_sight_drum", _knurl_xz(hx, dz, 4.2, 3.7, 24), -13.6, -9.95, C, "Steel_black")
    boolean(drum, cyl("cut_drum_face", -14, -13.2, 2.6, C, seg=24, cy=hx, cz=dz, axis="Y"))
    boolean(drum, box("cut_drum_slot", hx - 0.35, hx + 0.35, -14, -13.0, dz - 2.2, dz + 2.2, C))
    finish(drum, w=0.15, seg=2, angle=35)
    set_origin(drum, (hx, -11.8, dz))
    set_parent(drum, leaf)
    o["rear_drum"] = drum
    return o


def front_sight(C):
    o = {}
    hx, hz = FRONT_HINGE
    base = _base("Front_sight_base", FRONT_BASE_X[0], FRONT_BASE_X[1], FRONT_HINGE, FRONT_BOLT_X, FRONT_SIGHT_X - 6.0, C)
    o["front_base"] = base
    top = SIGHT_Z + 4.0
    bridge = hz + 9.5
    poly = [(-KNUCKLE_HALF, hz), (KNUCKLE_HALF, hz), (KNUCKLE_HALF, hz + 4.5), (8.8, hz + 8.0), (8.8, top - 1.5), (7.6, top),
            (5.7, top), (5.7, bridge), (-5.7, bridge), (-5.7, top), (-7.6, top), (-8.8, top - 1.5), (-8.8, hz + 8.0),
            (-KNUCKLE_HALF, hz + 4.5)]
    leaf = prism_yz("Front_sight_leaf", fillet(poly, [0, 0, 1.0, 1.5, 0.6, 0.8, 0.5, 0.8, 0.8, 0.5, 0.8, 0.6, 1.5, 1.0], 3),
                    hx - 3.0, hx + 3.0, C, "Alu_anodized")
    kn = cyl("front_knuckle", -KNUCKLE_HALF, KNUCKLE_HALF, 4.0, C, "Alu_anodized", seg=32, cy=hx, cz=hz, axis="Y")
    boolean(leaf, kn, "UNION")
    boolean(leaf, cyl("cut_front_knuckle", -10, 10, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    # отверстие под резьбовой стебель мушки в перемычке
    boolean(leaf, cyl("cut_post_stem", hz + 4.0, bridge + 1, 1.6, C, seg=20, cy=hx, cz=0.0, axis="Z"))
    # окно облегчения в кулаке спереди
    for k in range(4):
        xx = hx - 2.4 + k * 1.6
        boolean(leaf, box(f"cut_front_ser{k}", xx - 0.3, xx + 0.3, -12, 12, top - 0.5, top + 1, C))
    finish(leaf, w=0.25, seg=2, angle=35)
    set_origin(leaf, (hx, 0.0, hz))
    set_parent(leaf, base)
    o["front_leaf"] = leaf
    # барабан высоты (ось Z) — рифлёный диск на перемычке, выступает из стойки вперёд и назад
    d0, d1 = bridge + 0.1, bridge + 3.3
    drum = prism_xy("Front_sight_drum", [(hx + x, y) for x, y in _knurl_xz(0.0, 0.0, 4.4, 3.9, 28)], d0, d1, C, "Steel_black")
    boolean(drum, cyl("cut_fdrum_bore", d0 - 1, d1 + 1, 1.55, C, seg=20, cy=hx, cz=0.0, axis="Z"))
    finish(drum, w=0.15, seg=2, angle=35)
    set_origin(drum, (hx, 0.0, (d0 + d1) / 2))
    set_parent(drum, leaf)
    o["front_drum"] = drum
    # мушка: резьбовой стебель сквозь барабан и перемычку, квадратная стойка с сужением к вершине
    stem = cyl("Front_sight_post", hz + 4.2, d1 + 1.6, 1.5, C, "Steel_black", seg=20, cy=hx, cz=0.0, axis="Z")
    for k in range(int((d1 + 1.0 - hz - 5.0) / 0.8)):
        zz = hz + 5.0 + k * 0.8
        boolean(stem, _ring_z_cut(hx, zz, C))
    post = prism_xz("front_post_blade", [(hx - 0.9, d1 + 1.2), (hx + 0.9, d1 + 1.2), (hx + 0.9, SIGHT_Z - 0.9), (hx + 0.25, SIGHT_Z),
                                         (hx - 0.25, SIGHT_Z), (hx - 0.9, SIGHT_Z - 0.9)], -0.9, 0.9, C, "Steel_black")
    boolean(stem, post, "UNION")
    auto_sharp(stem, 35)
    set_origin(stem, (hx, 0.0, d1))
    set_parent(stem, leaf)
    o["front_post"] = stem
    return o


def _ring_z_cut(cx, zz, C):
    """Кольцевая канавка резьбы на вертикальном стебле (резак)."""
    c = lathe("cut_stem_thr", [(zz - 0.25, 1.15), (zz, 1.65), (zz + 0.25, 1.15)], C, None, seg=20, cy=0.0, cz=0.0)
    c.rotation_euler = (0, -math.pi / 2, 0)
    apply_transform(c)
    c.location = (cx * MM, 0, 0)
    apply_transform(c)
    return c
