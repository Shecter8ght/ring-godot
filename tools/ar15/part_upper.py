# AR-15: верхний ресивер «из заготовки»: корпус-«труба» вокруг рамы со стойкой под планку MIL-STD-1913, окно выброса
# с гнутой по корпусу пылезащитной крышкой, отражатель гильз, досылатель, проушины осей.
import math
import bpy
from mathutils import Matrix, Vector
from lib import (MM, UPPER_FRONT, UPPER_REAR, RAIL_TOP, SPLIT_Z, UPPER_HALF_W, RAIL_HALF_W, PIVOT_PIN, TAKEDOWN_PIN,
                 REAR_TOP_Z, STEP_X, STEP_R, FA_S, FA_D, FA_R, FA_LEN,
                 PORT_X, PORT_Z, GAS_Z, material, fillet, arc_pts, prism_xz, prism_yz, prism_xy, box, cyl, lathe, boolean, finish, join,
                 auto_sharp, bevel_edges, renormal, clean)

RAIL_BASE = 22.0              # низ планки (верх корпуса)
CARRIER_BORE_R = 12.55        # канал затворной рамы (рама Ø24.6)
CHANNEL_HALF_W = 7.2          # паз ключа рамы и рукоятки заряжания
CHANNEL_Z = (11.0, 26.8)      # паз по высоте: от рамы до потолка под планкой
LUG_HALF_W = 6.3              # проушины верхнего ресивера между «ушами» нижнего
PIN_R = 3.15                  # оси сборки и разборки (Ø6.3 — 0.250″)
FRONT_RING_R = 15.9           # резьбовое кольцо под гайку цевья (Ø1.25″)
FRONT_RING_LEN = 12.0
FA_ROD_END = 14.5             # конец стержня досылателя по его оси: и нажатый не касается рамы
FA_PAWL = 4.9                 # вылет собачки к оси канала: в покое 0.2 мм до рамы, нажатием — в насечку на ~0.7 мм
FA_HOUSING_REAR = -4.4        # задний торец корпуса по оси досылателя: кнопка (до −7.6) выступает на ~3 мм
LEFT_WINDOW_X = (-136.0, -70.0)   # окно слева над разъёмом (за задержкой, перед проушиной разборки)
LEFT_WINDOW_Z = (-6.4, 6.0)       # над поднятой линией разъёма (−8.6), рама видна на всю высоту боковины канала
HINGE_Y = -15.6               # ось пылезащитной крышки (под окном выброса)
HINGE_Z = -0.4
STEP = 0.8                    # прежний уступ боковин (для старых ссылок; корпус теперь «труба»)
STEP_Z = 1.0
TUBE_R = 15.4                 # «труба» корпуса вокруг рамы: выше оси боковины идут по этой окружности
RISER_HW = 11.5               # стойка под планкой (полуширина) — над трубой


def side_contour(z):
    """Полуширина корпуса на высоте z (мм) в зоне юбки над шахтой: плоская юбка ±15 у оси, выше — окружность трубы,
    ещё выше — стойка под планкой."""
    return min(UPPER_HALF_W, max(RISER_HW, math.sqrt(max(0.0, TUBE_R * TUBE_R - z * z))))


def contour_zs(z0, z1, n=16):
    """Высоты для обхода контура: густо по дуге трубы, на прямых (юбка, стойка) — только концы (без лишних вершин
    на плоскостях — иначе булевы рвутся на стыках с карманами)."""
    zk = math.sqrt(TUBE_R * TUBE_R - UPPER_HALF_W * UPPER_HALF_W)      # колено: дуга сходит в плоскую юбку
    zr = math.sqrt(TUBE_R * TUBE_R - RISER_HW * RISER_HW)              # дуга встречает стойку
    a, b = max(z0, zk), min(z1, zr)
    zs = {round(z0, 4), round(z1, 4)}
    if a < b:
        zs |= {round(a + (b - a) * k / n, 4) for k in range(n + 1)}
    return sorted(zs)


def _contour_cut(sgn, z0, z1, n=16):
    """Профиль (y, z) резака снаружи контура трубы/стойки для стороны sgn на высотах z0…z1 (дуга без зажима к юбке —
    резак не ложится на плоскость боковины)."""
    zr = math.sqrt(TUBE_R * TUBE_R - RISER_HW * RISER_HW)
    b = min(z1, zr)
    zs = [z0 + (b - z0) * k / n for k in range(n + 1)]
    pts = [(math.sqrt(max(0.0, TUBE_R * TUBE_R - z * z)), z) for z in zs]
    if z1 > zr:
        pts.append((RISER_HW, z1))
    pts = [(30.0, z0)] + pts + [(30.0, z1)]
    pts = [(y * sgn, z) for y, z in pts]
    return pts if sgn > 0 else list(reversed(pts))
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
    # «труба» корпуса вокруг рамы (как у серийных верхних ресиверов): над осью боковины сходятся по окружности TUBE_R
    # к стойке под планкой; за юбкой над шахтой (x < STEP_X) труба видна и ниже оси — продолжает силуэт буферной трубки
    for sgn in (-1, 1):
        boolean(body, prism_yz(f"cut_shoulder{sgn}", _contour_cut(sgn, 0.0, RAIL_BASE + 1.0), UPPER_REAR - 2, UPPER_FRONT + 0.5, C))
        boolean(body, prism_yz(f"cut_tube_low{sgn}", _contour_cut(sgn, REAR_TOP_Z - 1.0, 3.2), UPPER_REAR - 2, STEP_X - STEP_R - 2.0, C))
    # кольцо под гайку цевья (от самого торца — не выпирает над стойкой)
    ring = cyl("Upper_ring", UPPER_FRONT - 0.4, UPPER_FRONT + FRONT_RING_LEN, FRONT_RING_R, C, "Alu_anodized", seg=64)
    boolean(body, ring, "UNION")
    # нижние кромки корпуса скруглены сильнее (как у фрезерованных ресиверов)
    bevel_edges(body, lambda n1, n2: n1.z < -0.9 and abs(n2.y) > 0.9, w=1.6, seg=4,
                where=lambda p: p.x < UPPER_FRONT - 1.0)
    # канал рамы, паз ключа и рукоятки заряжания (открыт назад), отверстие газовой трубки
    boolean(body, cyl("cut_bore", UPPER_REAR - 5, UPPER_FRONT + FRONT_RING_LEN + 5, CARRIER_BORE_R, C, seg=64))
    boolean(body, box("cut_channel", UPPER_REAR - 5, UPPER_FRONT - 6.0, -CHANNEL_HALF_W, CHANNEL_HALF_W, CHANNEL_Z[0], CHANNEL_Z[1], C))
    boolean(body, cyl("cut_gas", UPPER_FRONT - 8, UPPER_FRONT + 1.5, 2.6, C, seg=24, cz=GAS_Z))
    boolean(body, box("cut_gas_notch", UPPER_FRONT + 1.0, UPPER_FRONT + FRONT_RING_LEN + 2, -2.7, 2.7, GAS_Z - 2.7, RAIL_BASE - 3.0, C))
    # дорожка кулачковой оси вдоль паза: повёрнутая головка оси идёт по ней при отходе рамы
    boolean(body, box("cut_cam_track", -125.0, -10.0, -8.6, 8.6, 9.4, 14.2, C))
    # снизу открыт над шахтой магазина и спусковым механизмом (курок достаёт до ударника)
    boolean(body, box("cut_bottom", -140.6, 11.0, -10.6, 10.6, SPLIT_Z - 5, 0.0, C))
    pv = prism_xz("Upper_pivot_lug", fillet([
        (PIVOT_PIN[0] - 4.8, SPLIT_Z + 1.0), (PIVOT_PIN[0] + 5.0, SPLIT_Z + 1.0),
        (PIVOT_PIN[0] + 5.0, PIVOT_PIN[1] - 6.5), (PIVOT_PIN[0] - 4.8, PIVOT_PIN[1] - 6.5)], [0, 0, 4.0, 4.0], 5),
        -LUG_HALF_W + 0.2, LUG_HALF_W - 0.2, C, "Alu_anodized")
    boolean(body, pv, "UNION")
    # проушины осей: «уши» нижнего ресивера заходят по бокам
    for nm, (px, pz) in (("pivot", PIVOT_PIN), ("takedown", TAKEDOWN_PIN)):
        for s in (-1, 1):
            y0, y1 = (LUG_HALF_W, UPPER_HALF_W + 3) if s > 0 else (-UPPER_HALF_W - 3, -LUG_HALF_W)
            if nm == "pivot":       # ухо нижнего спереди круглое (R 6.3 вокруг оси) — выемка по нему, без пустых углов
                ear = prism_xz(f"cut_ear_{nm}{s}", [(px - 9.5, pz - 10.0), (px + 6.9, pz - 10.0)] +
                               arc_pts(px, pz, 6.9, 0, 90, 10) + [(px - 9.5, pz + 6.9)], y0, y1, C)
                boolean(body, ear)
            else:
                boolean(body, box(f"cut_ear_{nm}{s}", px - 9.5, px + 9.5, y0, y1, pz - 10.0, pz + 7.6, C))
        boolean(body, cyl(f"cut_pin_{nm}", -20, 20, PIN_R, C, seg=32, cy=px, cz=pz, axis="Y"))
    # окно выброса (справа, −Y)
    port = prism_xz("cut_port", fillet([(PORT_X[0], PORT_Z[0]), (PORT_X[1], PORT_Z[0]), (PORT_X[1], PORT_Z[1]), (PORT_X[0], PORT_Z[1])],
                                       [1.5, 1.5, 1.5, 1.5], 4), -UPPER_HALF_W - 6, -2.0, C)
    boolean(body, port)
    # ниша под пылезащитную крышку (крышка лежит заподлицо) и прилив оси снизу окна
    rz0, rz1 = HINGE_Z + 1.2, PORT_Z[1] + 1.4
    zs = contour_zs(rz0, rz1)
    rec = prism_yz("cut_cover_recess", [(-30.0, rz0)] + [(-(side_contour(z) - 1.55), z) for z in zs] + [(-30.0, rz1)],
                   PORT_X[0] - 1.0, PORT_X[1] + 1.0, C)
    boolean(body, rec)
    # канавка под шарнир крышки: проушины крышки вращаются на оси в канавке корпуса
    boolean(body, box("cut_hinge_groove", PORT_X[0] - 0.8, PORT_X[1] + 0.8, -UPPER_HALF_W - 3, -UPPER_HALF_W + 2.3,
                      HINGE_Z - 2.5, HINGE_Z + 2.4, C))
    # отражатель гильз за окном: сбоку — скошенный перед, в плане — клин (гильза уходит вперёд-вправо)
    dx0, dx1 = PORT_X[0] - 19.3, PORT_X[0] - 1.6
    defl = prism_xz("Upper_deflector", fillet([(dx0, 5.0), (dx1, 5.0), (dx1, 11.0), (dx1 - 6.2, RAIL_BASE - 0.5),
                                               (dx0 + 3.5, RAIL_BASE - 0.5)], [2.0, 1.0, 2.0, 2.5, 1.5], 4),
                    -RISER_HW + 0.5, -UPPER_HALF_W - 6.0, C, "Alu_anodized")
    wedge = prism_xy("cut_defl_wedge", [(dx0 - 3.0, -UPPER_HALF_W - 7.0), (dx0 + 8.0, -UPPER_HALF_W - 7.0), (dx1 + 3.3, -UPPER_HALF_W - 1.2),
                                        (dx1 + 3.3, -UPPER_HALF_W - 10.0), (dx0 - 3.0, -UPPER_HALF_W - 10.0)], 0.0, 30.0, C)
    boolean(defl, wedge)
    finish(defl, w=1.0, seg=3, angle=30)
    boolean(body, defl, "UNION")
    # передние верхние углы — фаской в линию верхних фасок цевья (y + z = 9.5 + RAIL_BASE), назад сходят на нет у окна
    import bmesh
    from lib import v as vmm
    from lib import HG_HALF_W
    for s in (-1, 1):
        me = bpy.data.meshes.new("cut_front_bevel")
        bm = bmesh.new()
        ends = []
        for xx, c in ((PORT_X[1] + 1.5, RISER_HW + RAIL_BASE + 0.3), (UPPER_FRONT + 1.0, 9.5 + RAIL_BASE)):
            tri = [(c - 26.0, 26.0), (19.0, c - 19.0), (19.0, 26.0)]
            ends.append([bm.verts.new(vmm(xx, y * s, z)) for y, z in tri])
        a, b = ends
        bm.faces.new(a); bm.faces.new(list(reversed(b)))
        for i in range(3):
            j = (i + 1) % 3
            bm.faces.new((a[i], b[i], b[j], a[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        cutter = bpy.data.objects.new("cut_front_bevel", me)
        C.objects.link(cutter)
        boolean(body, cutter)
    # за шахтой линия разъёма поднимается: снизу выбрано до REAR_TOP_Z (там боковины нижнего), проушина разборки остаётся
    boolean(body, box("cut_rear_low_a", UPPER_REAR - 3, tdx - 9.25, -20, 20, SPLIT_Z - 9, REAR_TOP_Z, C))
    boolean(body, prism_xz("cut_rear_low_b", fillet([(tdx + 9.25, SPLIT_Z - 9), (STEP_X, SPLIT_Z - 9), (STEP_X, REAR_TOP_Z),
                                                     (tdx + 9.25, REAR_TOP_Z)], [0, 0, STEP_R, 0], 8), -20, 20, C))
    # досылатель: корпус под углом к оси справа сзади, канал толкателя выходит к насечкам рамы
    m = fa_matrix()
    hs = fa_housing_mesh(C)
    hs.data.transform(m)
    # внутреннее корпуса досылателя вырезаем до объединения (повторный прорез канала совпал бы с его поверхностью)
    boolean(hs, cyl("cut_hs_bore", UPPER_REAR - 5, -60.0, CARRIER_BORE_R + 0.7, C, seg=64))
    boolean(hs, box("cut_hs_inner", UPPER_REAR - 5, -60.0, -11.0, 20.0, -20.0, 40.0, C))
    boolean(body, hs, "UNION")
    fb = lathe("cut_fa_bore", [(-12.0, 0.0), (-12.0, 7.15), (9.0, 7.15), (9.0, 4.25), (FA_LEN + 6.0, 4.25), (FA_LEN + 6.0, 0.0)],
               C, None, seg=48, cy=0.0, cz=0.0)
    fb.data.transform(m)
    boolean(body, fb)
    boolean(body, fa_pawl_box("cut_fa_pawl_slot", (-1.1, 0.4 + 4.5 + 0.6), (-1.6, FA_PAWL + 1.5), (-2.9, 2.9), C))
    # «облегчающий» карман сзади слева — один ряд над окном (как у образца Fab); справа его место занял досылатель
    for s in (1,):
        for z0, z1 in ((10.0, 16.8),):
            x0, x1 = -164.0, (-122.0 if s < 0 else -86.0)
            pk = prism_xz(f"cut_pocket{s}{z0}", fillet([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], 2.6, 5),
                          (RISER_HW - 1.1) * s, (UPPER_HALF_W + 3) * s, C)
            boolean(body, pk)
    # окно слева над разъёмом за затворной задержкой (образец Fab): сквозь него видна рама и её ход
    win = prism_xz("cut_left_window", fillet([(LEFT_WINDOW_X[0], LEFT_WINDOW_Z[0]), (LEFT_WINDOW_X[1], LEFT_WINDOW_Z[0]),
                                              (LEFT_WINDOW_X[1], LEFT_WINDOW_Z[1]), (LEFT_WINDOW_X[0], LEFT_WINDOW_Z[1])], 4.5, 6),
                   8.0, UPPER_HALF_W + 3, C)
    boolean(body, win)
    # квадратные выемки сеткой слева (образец Fab): 2 × 2 перед карманами и 2 × 2 у переднего края с круглой лункой
    for nm, xs, zs in (("mid", (-80.8, -77.2), (10.6, 14.2)), ("front", (-10.5, -6.9), (10.2, 13.8))):
        for i, xx in enumerate(xs):
            for j, zz in enumerate(zs):
                sq = prism_xz(f"cut_sq_{nm}{i}{j}", fillet([(xx - 1.2, zz - 1.2), (xx + 1.2, zz - 1.2), (xx + 1.2, zz + 1.2),
                                                             (xx - 1.2, zz + 1.2)], 0.4, 2), RISER_HW - 0.8, UPPER_HALF_W + 3, C)
                boolean(body, sq)
    boolean(body, cyl("cut_dimple", RISER_HW - 0.8, UPPER_HALF_W + 3, 2.1, C, seg=32, cy=-16.0, cz=12.0, axis="Y"))
    # выемка снизу сзади под головку фиксатора буфера
    boolean(body, box("cut_retainer_relief", UPPER_REAR - 2, UPPER_REAR + 5.0, -3.0, 3.0, SPLIT_Z - 2, -11.0, C))
    # выемка слева снизу под затворную задержку (её верхняя лопатка и зуб заходят выше разъёма)
    boolean(body, box("cut_bolt_catch", -59.4, -41.6, 7.0, UPPER_HALF_W + 3, SPLIT_Z - 2, -6.0, C))
    # вырез сзади сверху под защёлку рукоятки заряжания (обе стороны)
    for s in (-1, 1):
        boolean(body, box(f"cut_ch_latch{s}", UPPER_REAR - 2, UPPER_REAR + 9.0, 4.5 * s if s > 0 else -13.5, 13.5 if s > 0 else -4.5,
                          CHANNEL_Z[0] + 4.0, RAIL_BASE + 0.1, C))
    on_bore = lambda c, n: abs(math.hypot(c.y, c.z) - CARRIER_BORE_R) < 0.25 and c.x < UPPER_FRONT + FRONT_RING_LEN
    finish(body, w=0.6, seg=3, angle=35, exclude=on_bore)
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
    out["fa"] = forward_assist(C)
    return out


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def fa_housing_mesh(C):
    """Корпус досылателя кольцами вдоль его оси (локально X), «капля» по фото PEO: у кнопки цилиндр, дальше вылет
    наружной стороны над боковиной (локально −Y) плавно сходит на нет к ~64 мм (ось при этом уходит внутрь корпуса),
    высота убывает к острию — верхняя кромка опускается, нижняя идёт почти ровно. Внутренняя сторона уходит
    в корпус ресивера и срезается каналом рамы."""
    import bmesh
    from lib import v as vmm
    n = 64
    d = Vector(FA_D).normalized()
    side = -RISER_HW                                    # стойка над трубой
    p0 = side - (FA_S[1] - FA_R)                         # вылет у кнопки
    cy = (fa_matrix().to_3x3() @ Vector((0.0, 1.0, 0.0))).y   # локальная Y повёрнута вместе с осью
    L0 = FA_HOUSING_REAR
    stations = sorted(set([L0, L0 + 0.5, L0 + 1.2] + [-2.0 + 2.0 * k for k in range(38)] + [5.1, 5.4, 6.6, 6.9]))
    me = bpy.data.meshes.new("fa_housing")
    bm = bmesh.new()
    rings = []
    for L in stations:
        k = _smooth((L - 24.0) / 42.0)                      # цилиндр у кнопки, дальше сходит в боковину
        yc = FA_S[1] + d.y * L
        prot = p0 * (1.0 - k) - 0.8 * _smooth((L - 60.0) / 10.0)   # к концу уходит под боковину
        ry_out = (yc - (side - prot)) / cy
        if L < 14.0:
            ry_out = max(ry_out, FA_R)
        rz = FA_R - (FA_R - 5.0) * _smooth((L - 28.0) / 38.0)   # высота держится, к носу плавно убывает
        oz = 0.0                                            # ось горизонтальна: верх и низ сходятся к носу симметрично
        if 5.3 < L < 6.7:                                   # поясок за кнопкой
            ry_out -= 0.45; rz -= 0.45
        ry_in = FA_R
        if L < L0 + 1.2:                                  # фаска заднего торца
            dd = L0 + 1.2 - L
            ry_out -= dd; rz -= dd; ry_in -= dd
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ca, sa = math.cos(a), math.sin(a)
            ry = ry_in if ca > 0 else ry_out
            ring.append(bm.verts.new(vmm(L, ry * ca, rz * sa + oz)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for pl in me.polygons:
        pl.use_smooth = True
    o = bpy.data.objects.new("fa_housing", me)
    C.objects.link(o)
    o.data.materials.append(material("Alu_anodized"))
    return o


def fa_matrix():
    """Система досылателя: локальная X — его ось (от торца назад-наружу вперёд-внутрь), начало — задний торец корпуса."""
    d = Vector(FA_D).normalized()
    r = Vector((1.0, 0.0, 0.0)).rotation_difference(d).to_matrix().to_4x4()
    r.translation = Vector(FA_S) * MM
    return r


def fa_pawl_box(name, ra, rb, rc, C):
    """Брусок собачки досылателя от конца стержня: a — вдоль канала рамы (X), b — по радиусу к оси канала, c — по
    касательной (как насечки рамы: брусок и насечка соосны)."""
    import bmesh
    from lib import v as vmm
    dd = Vector(FA_D).normalized()
    e = Vector(FA_S) + dd * FA_ROD_END
    d = Vector((1.0, 0.0, 0.0))
    u = Vector((0.0, -e.y, -e.z)).normalized()
    w = d.cross(u)
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = {}
    for ia, a in enumerate(ra):
        for ib, b in enumerate(rb):
            for ic, c in enumerate(rc):
                p = e + d * a + u * b + w * c
                vs[(ia, ib, ic)] = bm.verts.new(vmm(p.x, p.y, p.z))
    for f in (((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)), ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)),
              ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)), ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)),
              ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)), ((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1))):
        bm.faces.new([vs[k] for k in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    return o


def forward_assist(C):
    """Толкатель досылателя: круглая кнопка с кольцевыми канавками и стержень с собачкой на конце (к насечкам рамы)."""
    # стержень кончается, где его поверхность в ~1 мм от рамы; к насечкам рамы тянется только собачка
    prof = [(-7.6, 0.0), (-7.6, 5.9), (-7.0, 6.75), (-1.0, 6.75), (-0.4, 3.9), (FA_ROD_END - 1.2, 3.9), (FA_ROD_END, 3.0),
            (FA_ROD_END, 0.0)]
    pl = lathe("Forward_assist", prof, C, "Steel_black", seg=48, cy=0.0, cz=0.0)
    for k, r0 in enumerate((1.4, 3.0, 4.6)):
        ring = lathe("cut_fa_ring", [(-8.2, r0), (-8.2, r0 + 0.55), (-7.1, r0 + 0.55), (-7.1, r0)], C, None, seg=48, cy=0.0, cz=0.0)
        boolean(pl, ring)
    finish(pl, w=0.25, seg=2, angle=35)
    pl.data.transform(fa_matrix())
    # собачка: брусок от конца стержня к оси канала (в мировых координатах)
    import bmesh
    from lib import v as vmm
    paw = fa_pawl_box("fa_pawl", (-0.6, 0.4), (-1.0, FA_PAWL), (-1.6, 1.6), C)
    paw.data.materials.append(material("Steel_black"))
    finish(paw, w=0.25, seg=2, angle=35)
    boolean(pl, paw, "UNION")
    pl["_fin"] = 1
    return pl


def dust_cover(C):
    """Крышка окна: тонкая пластина, гнутая по контуру корпуса (труба и стойка), продольная выштамповка, шарнирные
    проушины снизу, защёлка-выступ внутри у верхней кромки (за неё цепляется рама)."""
    t = 1.3
    x0, x1 = PORT_X[0] - 0.6, PORT_X[1] + 0.6
    z0, z1 = HINGE_Z + 1.6, PORT_Z[1] + 1.1
    zs = contour_zs(z0, z1)
    prof = [(-(side_contour(z) + 0.25), z) for z in zs] + [(-(side_contour(z) + 0.25 - t), z) for z in reversed(zs)]
    plate = prism_yz("Dust_cover", list(reversed(prof)), x0, x1, C, "Steel_black")
    # скругление торцов крышки (вид сбоку)
    for xa, za, sx, sz in ((x0, z1, 1, -1), (x1, z1, -1, -1)):
        r = 2.2
        corner = prism_xz("cut_cover_corner", [(xa - sx * 0.5, za + 0.5), (xa + sx * r, za + 0.5)] +
                          [(xa + sx * r - sx * r * math.sin(math.radians(a_)), za - r + r * math.cos(math.radians(a_))) for a_ in range(0, 91, 10)] +
                          [(xa - sx * 0.5, za - r)], -30, 0, C)
        boolean(plate, corner)
    # рёбра жёсткости — продольная выштамповка по контуру
    rz0, rz1 = z0 + 4.5, z0 + 7.0
    rzs = contour_zs(rz0, rz1, 8)
    rib = prism_yz("cover_rib", list(reversed([(-(side_contour(z) + 0.7), z) for z in rzs] +
                                              [(-(side_contour(z) + 0.05), z) for z in reversed(rzs)])), x0 + 8, x1 - 8, C, "Steel_black")
    boolean(plate, rib, "UNION")
    # шарнирные проушины (три) вокруг оси
    y_in0 = -(side_contour(z0) + 0.25 - t)
    for xa, xb in ((x0 + 0.5, x0 + 7.0), ((x0 + x1) / 2 - 4, (x0 + x1) / 2 + 4), (x1 - 7.0, x1 - 0.5)):
        k = lathe("cover_knuckle", [(xa, 0.0), (xa, 1.9), (xb, 1.9), (xb, 0.0)], C, "Steel_black", seg=24, cy=HINGE_Y, cz=HINGE_Z)
        boolean(plate, k, "UNION")
        brg = box("cover_web", xa, xb, HINGE_Y - 0.2, y_in0, HINGE_Z, z0 + 0.5, C)
        boolean(plate, brg, "UNION")
    boolean(plate, cyl("cover_rod_hole", x0 - 5, x1 + 5, 1.1, C, seg=16, cy=HINGE_Y, cz=HINGE_Z))
    # выступ-защёлка изнутри у верхней кромки (входит в паз корпуса)
    y_in1 = -(side_contour(z1 - 2.2) + 0.25 - t)
    latch = box("cover_latch", -40.0, -30.0, y_in1 - 0.1, y_in1 + 1.6, z1 - 3.2, z1 - 1.2, C, "Steel_black")
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
