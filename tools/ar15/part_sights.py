# AR-15: складные прицелы на планках 1913 (своя форма по образцам владельца — целик сзади и пара «целик + мушка»
# в манере складных полимерных прицелов; без надписей и знаков).
# Целик — на планке ресивера: основание с губками по профилю планки и поперечным болтом в пазу (упор отдачи),
# сзади скошенная площадка с рифлением под палец, низкий шарнир с массивными щёками, впереди — ложе сложенной стойки.
# Стойка (складывается вперёд) — толстая, с двумя высокими «ушами»; внутренние грани ушей расходятся кверху.
# Между ушами на винте поправки по горизонтали стоит перекидной диоптр «Г» (малое отверстие вверх, большое лежит
# назад), его поджимают две витые пружины на том же винте; барабан винта — справа: рифлёный, с рисками и сквозным
# отверстием под фиксатор. Мушка — на планке цевья: стойка-«капюшон» с ушами вокруг квадратной мушки на рифлёном
# барабане высоты, складывается назад. Линия прицеливания — z = SIGHT_Z над осью канала.
import math
import bpy
from lib import (MM, RAIL_TOP, REAR_SIGHT_X, FRONT_SIGHT_X, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl,
                 lathe, boolean, finish, auto_sharp, apply_transform, set_parent, set_origin, join)

SIGHT_Z = 64.5                  # линия прицеливания над осью канала
BASE_TOP = 38.0                 # верх оснований
SEAT_TOP = 36.0                 # ложе сложенной стойки целика (впереди шарнира основание ниже)
REAR_BASE_X = (REAR_SIGHT_X - 21.0, REAR_SIGHT_X + 24.0)     # −171 … −126 (сзади — место крыльям рукоятки заряжания)
REAR_HINGE = (REAR_BASE_X[0] + 12.0, 40.0)                   # (x, z) оси стойки целика — низкий шарнир, кулак в пазу основания
REAR_BOLT_X = -146.0            # центр паза планки ресивера (14 + 10·k)
REAR_BUTTON_X = REAR_BASE_X[1] - 8.0
FRONT_HINGE = (FRONT_SIGHT_X + 11.0, 43.5)
FRONT_BASE_X = (FRONT_SIGHT_X - 16.0, FRONT_SIGHT_X + 16.0)
FRONT_BOLT_X = 264.0            # центр паза планки цевья
FRONT_BUTTON_X = FRONT_SIGHT_X - 12.0
BTN_Z = 33.0                    # кнопка фиксатора: ниже ложа целика (SEAT_TOP) с запасом стенки
AP_AXIS_Z = 59.0                # ось перекидного диоптра (= ось винта поправки)
AP_OFFSET = SIGHT_Z - AP_AXIS_Z # отверстия диоптра — на этом расстоянии от оси
LUG_IN, LUG_OUT = 4.5, 9.8      # щёки шарнира по Y
KNUCKLE_HALF = 4.3              # кулак стойки по Y
# стойка целика (по X — от оси шарнира; по Y — от середины)
LEAF_FRONT, LEAF_BACK = 3.2, 4.8       # передняя грань у оси: в сложенном виде ложится над ложем
REAR_TOP = SIGHT_Z + 7.5               # верх ушей
EAR_OUT = 12.0                         # уши снаружи
EAR_IN_LOW, EAR_IN_TOP = 5.4, 7.4      # внутренние грани ушей: у площадки и вверху
DECK_Z = 55.5                          # площадка между ушами (под ступицей диоптра)
AP_HALF = 2.4                          # стебли и ступица диоптра по Y (по бокам — пружины)
AP_RING = 4.4                          # кольца диоптров
DRUM_Y = (-12.15, -17.0)               # барабан поправки справа
DRUM_R = 4.8
# мушка
HOOD_FRONT, HOOD_BACK = 4.6, 4.2


def _base_section(top=BASE_TOP):
    """Сечение основания (y, z): губки обжимают «ласточкин хвост» планки, плоский верх."""
    pts = [(-13.5, 25.8), (-8.9, 25.8), (-11.1, 28.2), (-7.9, RAIL_TOP + 0.05), (7.9, RAIL_TOP + 0.05), (11.1, 28.2),
           (8.9, 25.8), (13.5, 25.8), (13.5, top - 2.5), (11.0, top), (-11.0, top), (-13.5, top - 2.5)]
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


def _groove_xz(name, p, u, half_len, depth, y0, y1, C):
    """Поперечная канавка рифления на наклонной грани: p — точка грани (x, z), u — направление вдоль грани."""
    nx, nz = -u[1], u[0]                   # нормаль наружу (вверх)
    if nz < 0:
        nx, nz = -nx, -nz
    a = (p[0] - u[0] * half_len - nx * depth, p[1] - u[1] * half_len - nz * depth)
    b = (p[0] + u[0] * half_len - nx * depth, p[1] + u[1] * half_len - nz * depth)
    c = (p[0] + u[0] * half_len + nx * 1.5, p[1] + u[1] * half_len + nz * 1.5)
    d = (p[0] - u[0] * half_len + nx * 1.5, p[1] - u[1] * half_len + nz * 1.5)
    return prism_xz(name, [a, b, c, d], y0, y1, C)


def _base(name, x0, x1, hinge, bolt_x, button_x, lug_r, C, rear):
    """Основание прицела. rear — целик: шарнир низкий, кулак уходит в паз, впереди ложе (основание ниже),
    сзади скошенная площадка с рифлением; иначе мушка: ложе позади шарнира."""
    hx, hz = hinge
    b = prism_yz(name, _base_section(), x0, x1, C, "Alu_anodized")
    # скосы торцов сверху (у целика сзади вместо скоса — площадка под палец)
    ends = ((x1, 1),) if rear else ((x0, -1), (x1, 1))
    for xe, s in ends:
        c = prism_xz(f"cut_{name}_bevel{s}", [(xe - 3.0 * s, BASE_TOP + 1), (xe + 1.0 * s, BASE_TOP + 1), (xe + 1.0 * s, BASE_TOP - 3.5)],
                     -20, 20, C)
        boolean(b, c)
    if rear:
        r0, r1 = (x0, BASE_TOP - 3.5), (hx - lug_r - 0.1, BASE_TOP)
        k = (r1[1] - r0[1]) / (r1[0] - r0[0])
        boolean(b, prism_xz(f"cut_{name}_ramp", [(x0 - 1.0, r0[1] - k), r1, (r1[0], BASE_TOP + 3), (x0 - 1.0, BASE_TOP + 3)], -20, 20, C))
        ln = math.hypot(r1[0] - r0[0], r1[1] - r0[1])
        u = ((r1[0] - r0[0]) / ln, (r1[1] - r0[1]) / ln)
        for i, t in enumerate((0.22, 0.42, 0.62, 0.82)):
            p = (r0[0] + (r1[0] - r0[0]) * t, r0[1] + (r1[1] - r0[1]) * t)
            boolean(b, _groove_xz(f"cut_{name}_rib{i}", p, u, 0.35, 0.45, -9.0, 9.0, C))
    # щёки шарнира
    for s in (-1, 1):
        prof = [(hx - lug_r, BASE_TOP - 1.0), (hx + lug_r, BASE_TOP - 1.0)] + arc_pts(hx, hz, lug_r, 0, 180, 16)
        y0, y1 = (LUG_IN, LUG_OUT) if s > 0 else (-LUG_OUT, -LUG_IN)
        lug = prism_xz(f"{name}_lug{s}", prof, y0, y1, C, "Alu_anodized")
        boolean(b, lug, "UNION")
    boolean(b, cyl(f"cut_{name}_hinge", -20, 20, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    if rear:
        # паз под кулак стойки между щеками; впереди шарнира основание ниже — ложе сложенной стойки
        # (паз продлён вперёд до ложа: сложенная шейка стойки ложится в него)
        boolean(b, box(f"cut_{name}_knuckle", hx - 4.7, hx + 7.0, -4.45, 4.45, hz - 4.6, BASE_TOP + 2, C))
        boolean(b, box(f"cut_{name}_seat", hx + lug_r + 0.4, x1 + 1.0, -20, 20, SEAT_TOP, BASE_TOP + 2, C))
        # выборка справа под барабан поправки сложенной стойки
        fold_x = hx + (AP_AXIS_Z - hz)
        boolean(b, cyl(f"cut_{name}_drum_relief", -20.0, -11.6, DRUM_R + 0.6, C, seg=32, cy=fold_x, cz=hz, axis="Y"))
        bed = prism_xy(f"cut_{name}_bed", fillet([(hx + lug_r + 3.0, -8.0), (x1 - 5.0, -8.0), (x1 - 5.0, 8.0), (hx + lug_r + 3.0, 8.0)], 2.0, 4),
                       SEAT_TOP - 0.7, SEAT_TOP + 1, C)
        boolean(b, bed)
    else:
        bed = prism_xy(f"cut_{name}_bed", fillet([(x0 + 3.6, -10.0), (hx - lug_r - 0.7, -10.0), (hx - lug_r - 0.7, 10.0), (x0 + 3.6, 10.0)],
                                                 2.0, 4), BASE_TOP - 0.9, BASE_TOP + 2, C)
        boolean(b, bed)
    # продольные канавки по бокам (облегчение)
    gx0 = x0 + (9.0 if rear else 5.0)
    for s in (-1, 1):
        y0, y1 = (12.7, 20.0) if s > 0 else (-20.0, -12.7)
        g = prism_xz(f"cut_{name}_groove{s}", fillet([(gx0, 30.2), (x1 - 5.0, 30.2), (x1 - 5.0, 31.6), (gx0, 31.6)], 0.6, 3), y0, y1, C)
        boolean(b, g)
    # отверстие поперечного болта (через губки, болт проходит в пазу планки)
    boolean(b, cyl(f"cut_{name}_bolt", -20, 20, 1.85, C, seg=20, cy=bolt_x, cz=29.95, axis="Y"))
    # гнездо кнопки фиксатора слева
    boolean(b, cyl(f"cut_{name}_btn", 11.5, 20, 2.55, C, seg=24, cy=button_x, cz=BTN_Z, axis="Y"))
    finish(b, w=0.5, seg=2, angle=35)
    set_origin(b, ((x0 + x1) / 2, 0.0, RAIL_TOP))
    # болт: круглая головка со шлицем слева, шестигранная гайка справа
    bolt = cyl(f"{name}_bolt", -15.6, 15.6, 1.75, C, "Steel_black", seg=20, cy=bolt_x, cz=29.95, axis="Y", ch=0.3)
    head = cyl(f"{name}_bolt_head", 13.55, 15.9, 4.0, C, "Steel_black", seg=32, cy=bolt_x, cz=29.95, axis="Y", ch=0.6)
    boolean(head, box("cut_head_slot", bolt_x - 0.5, bolt_x + 0.5, 15.1, 17.0, 25.0, 35.0, C))
    boolean(bolt, head, "UNION")
    hexa = [(bolt_x + 3.0 * math.cos(math.radians(30 + 60 * k)), 29.95 + 3.0 * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    nut = prism_xz(f"{name}_bolt_nut", hexa, -15.8, -13.55, C, "Steel_black")
    boolean(bolt, nut, "UNION")
    finish(bolt, w=0.2, seg=2, angle=35)
    set_parent(bolt, b)
    # кнопка фиксатора стойки (рифлёный торец)
    btn = lathe(f"{name}_button", [(11.6, 0.0), (11.6, 2.4), (14.6, 2.4), (15.0, 2.0), (15.0, 0.0)], C, "Steel_black", seg=24)
    btn.rotation_euler = (0, 0, math.pi / 2)
    apply_transform(btn)
    btn.location = (button_x * MM, 0, BTN_Z * MM)
    apply_transform(btn)
    for k in range(3):
        zz = BTN_Z - 1.0 + k * 1.0
        boolean(btn, box(f"cut_btn_rib{k}", button_x - 2.6, button_x + 2.6, 14.65, 16, zz - 0.18, zz + 0.18, C))
    auto_sharp(btn, 35)
    set_origin(btn, (button_x, 13.0, BTN_Z))
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


def _rear_leaf_profile(hz):
    """Сечение стойки целика (y, z): узкий кулак между щеками, тело во всю ширину, два уха; внутренние грани ушей
    вогнуто расходятся кверху (как у образца сзади)."""
    top = REAR_TOP
    w0, w1 = hz + 6.5, hz + 9.5
    right = [(KNUCKLE_HALF, hz), (KNUCKLE_HALF, w0), (EAR_OUT, w1), (EAR_OUT, top - 1.6), (EAR_OUT - 1.6, top), (EAR_IN_TOP + 0.5, top)]
    rad = [0.0, 1.2, 1.6, 0.6, 0.6, 0.4]
    z_hi, z_lo = top - 0.5, DECK_Z + 2.0
    for k in range(8):
        t = k / 7
        right.append((EAR_IN_LOW + (EAR_IN_TOP - EAR_IN_LOW) * (1 - t) ** 2, z_hi - (z_hi - z_lo) * t))
        rad.append(0.0)
    right.append((EAR_IN_LOW, DECK_Z))
    rad.append(1.0)
    left = [(-y, z) for y, z in reversed(right)]
    return fillet(right + left, rad + list(reversed(rad)), 3)


def _coil_y(name, cx, cz, r, wire, y0, y1, turns, C):
    """Витая пружина сжатия на оси вдоль Y (проволока по винтовой линии)."""
    from part_lower import _wire
    pts = []
    n = int(turns * 24)
    for k in range(n + 1):
        t = k / n
        a = 2 * math.pi * turns * t
        pts.append((cx + r * math.cos(a), y0 + (y1 - y0) * t, cz + r * math.sin(a)))
    return _wire(name, pts, wire, C)


def rear_sight(C):
    o = {}
    hx, hz = REAR_HINGE
    base = _base("Rear_sight_base", REAR_BASE_X[0], REAR_BASE_X[1], REAR_HINGE, REAR_BOLT_X, REAR_BUTTON_X, 5.5, C, rear=True)
    o["rear_base"] = base
    # стойка (поднята): узкий кулак у оси, тело во всю ширину, уши вокруг диоптра
    leaf = prism_yz("Rear_sight_leaf", _rear_leaf_profile(hz), hx - LEAF_BACK, hx + LEAF_FRONT, C, "Alu_anodized")
    kn = cyl("rear_knuckle", -KNUCKLE_HALF, KNUCKLE_HALF, 4.0, C, "Alu_anodized", seg=32, cy=hx, cz=hz, axis="Y")
    boolean(leaf, kn, "UNION")
    boolean(leaf, cyl("cut_rear_knuckle", -10, 10, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    # отверстия винта поправки в ушах
    boolean(leaf, cyl("cut_rear_screw", -14, 14, 1.0, C, seg=16, cy=hx, cz=AP_AXIS_Z, axis="Y"))
    # рифление на верхних торцах ушей (палец откидывает стойку)
    for k in range(4):
        xx = hx - LEAF_BACK + 1.4 + k * 1.6
        boolean(leaf, box(f"cut_rear_ser{k}", xx - 0.3, xx + 0.3, -14, 14, REAR_TOP - 0.5, REAR_TOP + 1, C))
    # площадка под большой палец на задней грани тела — поперечные канавки
    for k in range(3):
        zz = hz + 10.6 + k * 1.6
        boolean(leaf, box(f"cut_rear_pad{k}", hx - LEAF_BACK - 1.0, hx - LEAF_BACK + 0.45, -9.5, 9.5, zz - 0.3, zz + 0.3, C))
    # облегчающие карманы на наружных гранях ушей — над винтом слева и над барабаном справа
    for s in (-1, 1):
        y0, y1 = (EAR_OUT - 0.6, EAR_OUT + 2) if s > 0 else (-EAR_OUT - 2, -EAR_OUT + 0.6)
        z0 = AP_AXIS_Z + 2.8 if s > 0 else AP_AXIS_Z + DRUM_R + 1.0
        pk = prism_xz(f"cut_rear_ear_pocket{s}", fillet([(hx - LEAF_BACK + 1.4, z0), (hx + LEAF_FRONT - 1.2, z0),
                                                         (hx + LEAF_FRONT - 1.2, REAR_TOP - 2.6), (hx - LEAF_BACK + 1.4, REAR_TOP - 2.6)], 1.0, 4),
                      y0, y1, C)
        boolean(leaf, pk)
    finish(leaf, w=0.35, seg=2, angle=35)
    set_origin(leaf, (hx, 0.0, hz))
    set_parent(leaf, base)
    o["rear_leaf"] = leaf
    # перекидной диоптр «Г»: вертикальное плечо — малое отверстие (прицельное), горизонтальное назад — большое
    ax, az = hx, AP_AXIS_Z
    ring_dz = math.sqrt(AP_RING ** 2 - AP_HALF ** 2)
    a_s = math.degrees(math.atan2(-ring_dz, AP_HALF))
    small = [(-AP_HALF, az), (AP_HALF, az)] + arc_pts(0.0, SIGHT_Z, AP_RING, a_s, 180.0 - a_s, 56)
    ap = prism_yz("Rear_sight_aperture", fillet(small, [0.0, 0.0, 0.8] + [0.0] * (len(small) - 4) + [0.8], 3), ax - 1.0, ax + 1.0, C,
                  "Alu_anodized")
    cx = ax - AP_OFFSET
    a_b = math.degrees(math.atan2(-AP_HALF, ring_dz))            # стык стебля с кольцом снизу (−Y)
    big = [(ax, -AP_HALF), (cx + ring_dz, -AP_HALF)] + arc_pts(cx, 0.0, AP_RING, a_b, a_b - (360.0 + 2 * a_b), 56)[1:-1] + \
          [(cx + ring_dz, AP_HALF), (ax, AP_HALF)]
    big_o = prism_xy("ap_big", fillet(big, [0.0, 0.8] + [0.0] * (len(big) - 4) + [0.8, 0.0], 3), az - 1.0, az + 1.0, C, "Alu_anodized")
    boolean(ap, big_o, "UNION")
    hub = cyl("ap_hub", -AP_HALF, AP_HALF, 2.3, C, "Alu_anodized", seg=32, cy=ax, cz=az, axis="Y")
    boolean(ap, hub, "UNION")
    boolean(ap, cyl("cut_ap_axis", -8, 8, 0.95, C, seg=16, cy=ax, cz=az, axis="Y"))
    # малое отверстие с зенковкой со стороны глаза; выемка-метка на верхушке кольца
    sm = lathe("cut_ap_small", [(ax - 3, 0.0), (ax - 3, 2.9), (ax - 1.6, 2.9), (ax - 0.5, 1.7), (ax + 3, 1.7), (ax + 3, 0.0)],
               C, None, seg=48, cy=0.0, cz=SIGHT_Z)
    boolean(ap, sm)
    boolean(ap, box("cut_ap_notch", ax - 3, ax + 3, -0.55, 0.55, SIGHT_Z + AP_RING - 0.9, SIGHT_Z + AP_RING + 1, C))
    # большое отверстие с фаской снизу (в рабочем положении — со стороны глаза)
    bg = lathe("cut_ap_big", [(az - 3, 0.0), (az - 3, 3.5), (az - 1.2, 3.5), (az - 0.5, 2.9), (az + 3, 2.9), (az + 3, 0.0)],
               C, None, seg=48, cy=0.0, cz=0.0)
    bg.rotation_euler = (0, -math.pi / 2, 0)
    apply_transform(bg)
    bg.location = (cx * MM, 0, 0)
    apply_transform(bg)
    boolean(ap, bg)
    finish(ap, w=0.2, seg=2, angle=35)
    set_origin(ap, (ax, 0.0, az))
    set_parent(ap, leaf)
    o["rear_aperture"] = ap
    # винт поправки — ось диоптра: шлицевая головка слева, справа уходит в барабан
    scr = cyl("Rear_sight_aperture_pin", DRUM_Y[0] - 2.0, EAR_OUT + 0.1, 0.9, C, "Steel_black", seg=16, cy=ax, cz=az, axis="Y", ch=0.1)
    shead = cyl("ap_screw_head", EAR_OUT + 0.05, EAR_OUT + 0.85, 1.9, C, "Steel_black", seg=24, cy=ax, cz=az, axis="Y", ch=0.25)
    boolean(shead, box("cut_screw_slot", ax - 0.3, ax + 0.3, EAR_OUT + 0.45, EAR_OUT + 1.2, az - 3, az + 3, C))
    boolean(scr, shead, "UNION")
    auto_sharp(scr, 35)
    set_parent(scr, leaf)
    # пружины диоптра на винте по обе стороны ступицы (поджимают диоптр, держат его в обоих положениях)
    wire = 0.28
    for s, nm in ((1, "Rear_sight_spring_L"), (-1, "Rear_sight_spring_R")):
        y_in, y_out = s * (AP_HALF + 0.12 + wire), s * (EAR_IN_LOW - 0.12 - wire)
        sp = _coil_y(nm, ax, az, 1.5, wire, y_in, y_out, 3.2, C)
        set_parent(sp, leaf)
        o[nm] = sp
    # барабан поправки справа (−Y): рифлёный, торец с утопленной серединой, шлицевой головкой, рисками; сквозное
    # радиальное отверстие под фиксатор
    drum = prism_xz("Rear_sight_drum", _knurl_xz(hx, az, DRUM_R, DRUM_R - 0.45, 26), DRUM_Y[1], DRUM_Y[0], C, "Steel_black")
    boolean(drum, cyl("cut_drum_bore", DRUM_Y[0] - 2.4, DRUM_Y[0] + 0.5, 0.95, C, seg=16, cy=hx, cz=az, axis="Y"))
    boolean(drum, cyl("cut_drum_face", DRUM_Y[1] - 1.0, DRUM_Y[1] + 0.6, 3.3, C, seg=32, cy=hx, cz=az, axis="Y"))
    boss = cyl("drum_boss", DRUM_Y[1] + 0.1, DRUM_Y[1] + 0.7, 1.7, C, "Steel_black", seg=24, cy=hx, cz=az, axis="Y")
    boolean(drum, boss, "UNION")
    boolean(drum, box("cut_drum_slot", hx - 0.3, hx + 0.3, DRUM_Y[1] - 1.0, DRUM_Y[1] + 0.4, az - 1.6, az + 1.6, C))
    ticks = []
    for k in range(12):
        t = box(f"cut_drum_tick{k}", -0.2, 0.2, DRUM_Y[1] - 1.0, DRUM_Y[1] + 0.35, DRUM_R - 1.25, DRUM_R - 0.55, C)
        t.rotation_euler = (0, 2 * math.pi * k / 12, 0)
        apply_transform(t)
        t.location = (hx * MM, 0, az * MM)
        apply_transform(t)
        ticks.append(t)
    boolean(drum, join(ticks, "cut_drum_ticks"))
    boolean(drum, cyl("cut_drum_cross", az - 6, az + 6, 0.55, C, seg=12, cy=hx, cz=(DRUM_Y[0] + DRUM_Y[1]) / 2, axis="Z"))
    finish(drum, w=0.15, seg=2, angle=35)
    set_origin(drum, (hx, (DRUM_Y[0] + DRUM_Y[1]) / 2, az))
    set_parent(drum, leaf)
    o["rear_drum"] = drum
    return o


def _hood_profile(hz, top, bridge):
    """Сечение стойки мушки (y, z): узкий кулак, широкое тело с уступом, U-проём со скруглённым дном между ушами;
    уши снаружи сужаются кверху."""
    right = [(KNUCKLE_HALF, hz), (KNUCKLE_HALF, hz + 6.5), (11.0, hz + 9.0), (11.0, bridge + 1.0), (9.8, bridge + 2.6), (9.0, top - 2.0),
             (8.0, top), (6.4, top), (5.7, top - 0.8), (5.7, bridge)]
    rad = [0.0, 1.2, 1.5, 0.8, 0.8, 1.5, 1.4, 0.4, 0.4, 2.0]
    left = [(-y, z) for y, z in reversed(right)]
    return fillet(right + left, rad + list(reversed(rad)), 3)


def front_sight(C):
    o = {}
    hx, hz = FRONT_HINGE
    base = _base("Front_sight_base", FRONT_BASE_X[0], FRONT_BASE_X[1], FRONT_HINGE, FRONT_BOLT_X, FRONT_BUTTON_X, 4.8, C, rear=False)
    o["front_base"] = base
    top = SIGHT_Z + 4.0
    bridge = hz + 9.5
    leaf = prism_yz("Front_sight_leaf", _hood_profile(hz, top, bridge), hx - HOOD_BACK, hx + HOOD_FRONT, C, "Alu_anodized")
    kn = cyl("front_knuckle", -KNUCKLE_HALF, KNUCKLE_HALF, 4.0, C, "Alu_anodized", seg=32, cy=hx, cz=hz, axis="Y")
    boolean(leaf, kn, "UNION")
    boolean(leaf, cyl("cut_front_knuckle", -10, 10, 1.25, C, seg=20, cy=hx, cz=hz, axis="Y"))
    # верх ушей скошен к глазу (перед выше — закрывает мушку от ударов)
    boolean(leaf, prism_xz("cut_hood_slope", [(hx - HOOD_BACK - 1, top - 2.4), (hx + HOOD_FRONT - 1.5, top), (hx + HOOD_FRONT + 1, top + 0.2),
                                              (hx + HOOD_FRONT + 1, top + 5), (hx - HOOD_BACK - 1, top + 5)], -14, 14, C))
    # отверстие под резьбовой стебель мушки в перемычке
    boolean(leaf, cyl("cut_post_stem", hz + 4.0, bridge + 1, 1.6, C, seg=20, cy=hx, cz=0.0, axis="Z"))
    # облегчающее окно между кулаком и перемычкой (сквозь него виден стебель мушки)
    boolean(leaf, prism_yz("cut_front_window", fillet([(-2.5, hz + 5.0), (2.5, hz + 5.0), (2.5, hz + 8.3), (-2.5, hz + 8.3)], 1.0, 4),
                           hx - 6.0, hx + 6.0, C))
    # рифление на передней грани ушей (в сложенном виде она сверху — под палец)
    for k in range(3):
        zz = bridge + 3.0 + k * 1.8
        for s in (-1, 1):
            y0, y1 = (6.4, 9.4) if s > 0 else (-9.4, -6.4)
            boolean(leaf, box(f"cut_front_ser{k}{s}", hx + HOOD_FRONT - 0.45, hx + HOOD_FRONT + 1, y0, y1, zz - 0.3, zz + 0.3, C))
    finish(leaf, w=0.35, seg=2, angle=35)
    set_origin(leaf, (hx, 0.0, hz))
    set_parent(leaf, base)
    o["front_leaf"] = leaf
    # барабан высоты (ось Z) — рифлёный диск на перемычке внутри проёма
    d0, d1 = bridge + 0.3, bridge + 3.5                # над скруглением дна проёма
    drum = prism_xy("Front_sight_drum", [(hx + x, y) for x, y in _knurl_xz(0.0, 0.0, 4.4, 3.9, 28)], d0, d1, C, "Steel_black")
    boolean(drum, cyl("cut_fdrum_bore", d0 - 1, d1 + 1, 1.55, C, seg=20, cy=hx, cz=0.0, axis="Z"))
    ticks = []
    for k in range(14):
        a = 2 * math.pi * k / 14
        t = box(f"cut_fdrum_tick{k}", 2.6, 3.4, -0.2, 0.2, d1 - 0.25, d1 + 1, C)
        t.rotation_euler = (0, 0, a)
        apply_transform(t)
        t.location = (hx * MM, 0, 0)
        apply_transform(t)
        ticks.append(t)
    boolean(drum, join(ticks, "cut_fdrum_ticks"))
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
