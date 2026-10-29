# AR-15: верхний ресивер «из заготовки» (без досылателя — как у листинга Fab), планка MIL-STD-1913, окно выброса,
# отражатель гильз, проушины осей, пылезащитная крышка на оси с пружиной.
import math
import bpy
from lib import (MM, UPPER_FRONT, UPPER_REAR, RAIL_TOP, SPLIT_Z, UPPER_HALF_W, RAIL_HALF_W, PIVOT_PIN, TAKEDOWN_PIN,
                 PORT_X, PORT_Z, GAS_Z, fillet, prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish, join,
                 auto_sharp, bevel_edges, renormal, clean)

RAIL_BASE = 22.0              # низ планки (верх корпуса)
CARRIER_BORE_R = 12.55        # канал затворной рамы (рама Ø24.6)
CHANNEL_HALF_W = 7.2          # паз ключа рамы и рукоятки заряжания
CHANNEL_Z = (11.0, 26.8)      # паз по высоте: от рамы до потолка под планкой
LUG_HALF_W = 6.3              # проушины верхнего ресивера между «ушами» нижнего
PIN_R = 3.15                  # оси сборки и разборки (Ø6.3 — 0.250″)
FRONT_RING_R = 15.9           # резьбовое кольцо под гайку цевья (Ø1.25″)
FRONT_RING_LEN = 12.0
HINGE_Y = -15.6               # ось пылезащитной крышки (под окном выброса)
HINGE_Z = -0.4
STEP = 0.8                    # уступ боковин над осью крышки
STEP_Z = 1.0
RAIL_SLOT_W = 5.23
RAIL_SLOT_DEPTH = 2.9


def rail_profile(top=RAIL_TOP, base=RAIL_BASE, half=RAIL_HALF_W):
    """Поперечное сечение планки 1913 (y, z): плоский верх, «ласточкин хвост» под 45°, шейка до корпуса."""
    top_half = half - 2.8
    neck = half - 2.6
    zv = top - 2.8                      # самая широкая точка «V»
    zn = zv - (half - neck)             # низ нижнего скоса
    pts = [(-neck, base), (-neck, zn), (-half, zv), (-top_half, top), (top_half, top), (half, zv), (neck, zn), (neck, base)]
    return pts


def rail(name, x0, x1, coll, slot_from, mat="Alu_anodized", top=RAIL_TOP, base=RAIL_BASE):
    """Планка с поперечными пазами шагом 10 мм; slot_from — центр первого паза у x1 (идут назад)."""
    r = prism_yz(name, rail_profile(top, base), x0, x1, coll, mat)
    xs = []
    x = slot_from
    while x - RAIL_SLOT_W / 2 > x0 + 2.0:
        xs.append(x)
        x -= 10.0
    for i, xc in enumerate(xs):
        c = box(f"{name}_slot{i}", xc - RAIL_SLOT_W / 2, xc + RAIL_SLOT_W / 2, -20, 20, top - RAIL_SLOT_DEPTH, top + 5, coll)
        boolean(r, c)
    return r, xs


def build(ctx):
    C = ctx["coll"]["Upper"]
    out = {}
    # --- корпус: боковой профиль, выдавленный на всю ширину ---
    tdx, tdz = TAKEDOWN_PIN
    side = fillet([
        (UPPER_REAR, SPLIT_Z), (UPPER_REAR, RAIL_BASE), (UPPER_FRONT, RAIL_BASE), (UPPER_FRONT, SPLIT_Z),
        (tdx + 9.0, SPLIT_Z), (tdx + 9.0, tdz - 7.5), (tdx - 9.0, tdz - 7.5), (tdx - 9.0, SPLIT_Z),
    ], [1.5, 2.0, 1.0, 1.0, 0.0, 3.0, 3.0, 0.0], seg=4)
    body = prism_xz("Upper_receiver", side, -UPPER_HALF_W, UPPER_HALF_W, C, "Alu_anodized")
    # кольцо под гайку цевья
    ring = cyl("Upper_ring", UPPER_FRONT - 2.0, UPPER_FRONT + FRONT_RING_LEN, FRONT_RING_R, C, "Alu_anodized", seg=64)
    boolean(body, ring, "UNION")
    # нижние кромки корпуса скруглены сильнее (как у фрезерованных ресиверов)
    bevel_edges(body, lambda n1, n2: n1.z < -0.9 and abs(n2.y) > 0.9, w=1.6, seg=4,
                where=lambda p: p.x < UPPER_FRONT - 1.0)
    # канал рамы, паз ключа и рукоятки заряжания (открыт назад), отверстие газовой трубки
    boolean(body, cyl("cut_bore", UPPER_REAR - 5, UPPER_FRONT + FRONT_RING_LEN + 5, CARRIER_BORE_R, C, seg=64))
    boolean(body, box("cut_channel", UPPER_REAR - 5, UPPER_FRONT - 6.0, -CHANNEL_HALF_W, CHANNEL_HALF_W, CHANNEL_Z[0], CHANNEL_Z[1], C))
    boolean(body, cyl("cut_gas", UPPER_FRONT - 8, UPPER_FRONT + FRONT_RING_LEN + 2, 2.6, C, seg=24, cz=GAS_Z))
    # дорожка кулачковой оси вдоль паза: повёрнутая головка оси идёт по ней при отходе рамы
    boolean(body, box("cut_cam_track", -125.0, -10.0, -8.6, 8.6, 9.4, 14.2, C))
    # снизу открыт над шахтой магазина и спусковым механизмом (курок достаёт до ударника)
    boolean(body, box("cut_bottom", -140.6, 8.0, -10.6, 10.6, SPLIT_Z - 5, 0.0, C))
    # проушины осей: «уши» нижнего ресивера заходят по бокам
    for nm, (px, pz) in (("pivot", PIVOT_PIN), ("takedown", TAKEDOWN_PIN)):
        for s in (-1, 1):
            y0, y1 = (LUG_HALF_W, UPPER_HALF_W + 3) if s > 0 else (-UPPER_HALF_W - 3, -LUG_HALF_W)
            boolean(body, box(f"cut_ear_{nm}{s}", px - 9.5, px + 9.5, y0, y1, pz - 10.0, pz + 7.6, C))
        boolean(body, cyl(f"cut_pin_{nm}", -20, 20, PIN_R, C, seg=32, cy=px, cz=pz, axis="Y"))
    pv = prism_xz("Upper_pivot_lug", fillet([
        (PIVOT_PIN[0] - 4.8, SPLIT_Z + 1.0), (PIVOT_PIN[0] + 9.0, SPLIT_Z + 1.0),
        (PIVOT_PIN[0] + 9.0, PIVOT_PIN[1] - 6.5), (PIVOT_PIN[0] - 4.8, PIVOT_PIN[1] - 6.5)], [0, 0, 5.0, 4.0], 5),
        -LUG_HALF_W + 0.2, LUG_HALF_W - 0.2, C, "Alu_anodized")
    boolean(pv, cyl("cut_pv_pin", -20, 20, PIN_R, C, seg=32, cy=PIVOT_PIN[0], cz=PIVOT_PIN[1], axis="Y"))
    boolean(body, pv, "UNION")
    # уступ по бокам: выше линии оси крышки корпус уже (характерная «ступень» фрезерованных ресиверов)
    for sgn in (-1, 1):
        y0, y1 = (UPPER_HALF_W - STEP, UPPER_HALF_W + 3) if sgn > 0 else (-UPPER_HALF_W - 3, -UPPER_HALF_W + STEP)
        boolean(body, box(f"cut_step{sgn}", UPPER_REAR - 2, UPPER_FRONT - 2.5, y0, y1, STEP_Z, RAIL_BASE + 1, C))
    # окно выброса (справа, −Y)
    port = prism_xz("cut_port", fillet([(PORT_X[0], PORT_Z[0]), (PORT_X[1], PORT_Z[0]), (PORT_X[1], PORT_Z[1]), (PORT_X[0], PORT_Z[1])],
                                       [1.5, 1.5, 1.5, 1.5], 4), -UPPER_HALF_W - 6, -2.0, C)
    boolean(body, port)
    # ниша под пылезащитную крышку (крышка лежит заподлицо) и прилив оси снизу окна
    rec = box("cut_cover_recess", PORT_X[0] - 1.0, PORT_X[1] + 1.0, -UPPER_HALF_W - 3, -UPPER_HALF_W + STEP + 0.9, HINGE_Z + 1.2, PORT_Z[1] + 1.4, C)
    boolean(body, rec)
    # канавка под шарнир крышки: проушины крышки вращаются на оси в канавке корпуса
    boolean(body, box("cut_hinge_groove", PORT_X[0] - 0.8, PORT_X[1] + 0.8, -UPPER_HALF_W - 3, -UPPER_HALF_W + 2.3,
                      HINGE_Z - 2.5, HINGE_Z + 2.4, C))
    # отражатель гильз за окном: сбоку — скошенный перед, в плане — клин (гильза уходит вперёд-вправо)
    defl = prism_xz("Upper_deflector", fillet([(-117.0, 5.0), (-98.5, 5.0), (-104.0, RAIL_BASE - 0.5), (-117.0, RAIL_BASE - 0.5)],
                                              [2.0, 1.5, 2.5, 1.5], 4), -UPPER_HALF_W + STEP + 0.5, -UPPER_HALF_W - 6.0, C, "Alu_anodized")
    wedge = prism_xy("cut_defl_wedge", [(-120.0, -UPPER_HALF_W - 7.0), (-109.0, -UPPER_HALF_W - 7.0), (-96.0, -UPPER_HALF_W - 1.2),
                                        (-96.0, -UPPER_HALF_W - 10.0), (-120.0, -UPPER_HALF_W - 10.0)], 0.0, 30.0, C)
    boolean(defl, wedge)
    boolean(body, defl, "UNION")
    # «облегчающие» карманы по бокам сзади — два ряда, как на листинге
    for s in (-1, 1):
        for z0, z1 in ((3.0, 8.4), (11.4, 16.8)):
            x0, x1 = -168.0, (-122.0 if s < 0 else -86.0)
            pk = prism_xz(f"cut_pocket{s}{z0}", fillet([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 2.6, 5),
                          (UPPER_HALF_W - STEP - 1.1) * s, (UPPER_HALF_W + 3) * s, C)
            boolean(body, pk)
    # выемка снизу сзади под головку фиксатора буфера
    boolean(body, box("cut_retainer_relief", UPPER_REAR - 2, UPPER_REAR + 5.0, -3.0, 3.0, SPLIT_Z - 2, -11.0, C))
    # выемка слева снизу под затворную задержку (её верхняя лопатка и зуб заходят выше разъёма)
    boolean(body, box("cut_bolt_catch", -66.5, -45.5, 7.0, UPPER_HALF_W + 3, SPLIT_Z - 2, -2.0, C))
    # вырез сзади сверху под защёлку рукоятки заряжания (обе стороны)
    for s in (-1, 1):
        boolean(body, box(f"cut_ch_latch{s}", UPPER_REAR - 2, UPPER_REAR + 9.0, 4.5 * s if s > 0 else -13.5, 13.5 if s > 0 else -4.5,
                          CHANNEL_Z[0] + 4.0, RAIL_BASE + 0.1, C))
    finish(body, w=0.45, seg=2, angle=35)
    # планка: пазы шагом 10 мм от переднего торца
    rl, slots = rail("Upper_rail", UPPER_REAR, UPPER_FRONT, C, slot_from=UPPER_FRONT - 6.0)
    boolean(rl, box("cut_rail_ch", UPPER_REAR - 2, UPPER_REAR + 9.0, -13.5, 13.5, RAIL_BASE - 1, RAIL_BASE + 3.2, C))
    finish(rl, w=0.35, seg=2, angle=35)
    out["body"] = body
    out["rail"] = rl
    out["rail_slots"] = slots
    out["cover"] = dust_cover(C)
    out["cover_rod"] = cyl("Dust_cover_rod", PORT_X[0] - 6.0, PORT_X[1] + 5.0, 1.0, C, "Steel_black", seg=16, cy=HINGE_Y, cz=HINGE_Z)
    spr = coil("Dust_cover_spring", PORT_X[0] + 18.0, PORT_X[0] + 34.0, 1.55, 0.35, 9, C, cy=HINGE_Y, cz=HINGE_Z)
    out["cover_spring"] = spr
    return out


def dust_cover(C):
    """Крышка окна: тонкая пластина с бортиком, шарнирные проушины снизу, защёлка-выступ внутри (за неё цепляется рама)."""
    t = 1.3
    x0, x1 = PORT_X[0] - 0.6, PORT_X[1] + 0.6
    z0, z1 = HINGE_Z + 1.6, PORT_Z[1] + 1.1
    y_out = -UPPER_HALF_W - 0.25
    plate = prism_xz("Dust_cover", fillet([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], [0.8, 0.8, 2.2, 2.2], 4), y_out, y_out + t, C, "Steel_black")
    # рёбра жёсткости — продольная выштамповка
    rib = prism_xz("cover_rib", fillet([(x0 + 8, z0 + 4.5), (x1 - 8, z0 + 4.5), (x1 - 8, z0 + 7.0), (x0 + 8, z0 + 7.0)], 1.2, 3),
                   y_out - 0.45, y_out + 0.2, C, "Steel_black")
    boolean(plate, rib, "UNION")
    # шарнирные проушины (три) вокруг оси
    for xa, xb in ((x0 + 0.5, x0 + 7.0), ((x0 + x1) / 2 - 4, (x0 + x1) / 2 + 4), (x1 - 7.0, x1 - 0.5)):
        k = lathe("cover_knuckle", [(xa, 0.0), (xa, 1.9), (xb, 1.9), (xb, 0.0)], C, "Steel_black", seg=24, cy=HINGE_Y, cz=HINGE_Z)
        boolean(plate, k, "UNION")
        brg = box("cover_web", xa, xb, HINGE_Y - 0.2, y_out + t, HINGE_Z, z0 + 0.5, C)
        boolean(plate, brg, "UNION")
    boolean(plate, cyl("cover_rod_hole", x0 - 5, x1 + 5, 1.1, C, seg=16, cy=HINGE_Y, cz=HINGE_Z))
    # выступ-защёлка изнутри у верхней кромки (входит в паз корпуса)
    latch = box("cover_latch", -40.0, -30.0, y_out + t - 0.1, y_out + t + 1.6, z1 - 3.2, z1 - 1.2, C, "Steel_black")
    boolean(plate, latch, "UNION")
    finish(plate, w=0.25, seg=2, angle=35)
    return plate


def coil(name, x0, x1, r, wire, turns, C, cy=0.0, cz=0.0, mat="Spring_steel", seg=10):
    """Винтовая пружина вдоль X (трубка по спирали)."""
    import bmesh
    from mathutils import Vector
    from lib import v
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    n = int(turns * 24)
    rings = []
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        x = x0 + (x1 - x0) * t
        c = Vector((x, cy + r * math.cos(a), cz + r * math.sin(a)))
        tang = Vector(((x1 - x0) / (2 * math.pi * turns), -r * math.sin(a), r * math.cos(a))).normalized()
        nrm = Vector((0, math.cos(a), math.sin(a)))
        bnr = tang.cross(nrm).normalized()
        ring = []
        for k in range(seg):
            b = 2 * math.pi * k / seg
            p = c + (nrm * math.cos(b) + bnr * math.sin(b)) * wire
            ring.append(bm.verts.new(v(p.x, p.y, p.z)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    from lib import material
    o.data.materials.append(material(mat))
    return o
