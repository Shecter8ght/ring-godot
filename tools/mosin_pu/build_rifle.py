"""Снайперская винтовка обр. 1891/30 под прицел ПУ — high-poly для просмотра формы (без кронштейна).

Источники формы: подложка trace/blueprint_right.png (RIA 5039/265, правая сторона, привязка: длина
1232 мм, ось канала через середину ствола у дула и конус ствола у коробки), снимки сверху Commons
(ширины ложи, калибровка по кольцу коробки Ø31,3), профиль ствола 7.62x54r.net (A 30,1 → B 27,8 на
50,8 мм → C 19,8 на 63,5 мм → D 14,76 у дула; ствол 704,9 мм от коробки), патронник — по чертежу
патрона. Подробности и допущения — asset-state.md.

Оси: дуло +X, верх +Z, правая сторона стрелка −Y. Начало — ось канала у казённого среза ствола.
Запуск: blender --background --factory-startup --python tools/mosin_pu/build_rifle.py
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

OUT = os.path.join(L.ASSET_DIR, "models", "01_Винтовка", "Mosin_9130PU_Rifle_v04.blend")
MUZZLE = 728.8
SEC = 120                     # точек в сечении ложи

# ------------------------------------------------------------------ контуры ложи (сняты с подложки, мм)
STOCK_TOP = [
    (-512, -60), (-503, -58), (-500, -52), (-495, -48.5), (-485, -45.9), (-470, -42.1), (-450, -37.9),
    (-430, -35.1), (-410, -32.4), (-390, -30.4), (-370, -29.4), (-350, -28.6), (-330, -28.4), (-312, -28.2),
    (-300, -28.6), (-290, -30.25), (-280, -33.1), (-270, -36.5), (-262, -38.1), (-255, -37.75), (-250, -36.5),
    (-240, -33.75), (-230, -29.75), (-225, -26.25), (-220, -23.75), (-210, -20.0), (-200, -15.6),
    (-190, -12.25), (-180, -7.5), (-172, -3.1), (-160, -0.8), (-150, -1.0), (-125, -2.5), (-100, -4.2),
    (-75, -3.6), (-50, -3.1), (-30, -1.5), (-22, 0.8), (165, 0.8), (172, 0.4), (623, 0.4),
]
STOCK_BOT = [
    (-512, -156), (-485, -154.6), (-475, -154.4), (-460, -151.4), (-440, -147.9), (-420, -143.1),
    (-400, -137.4), (-380, -131.1), (-360, -124.9), (-340, -118.4), (-320, -111.4), (-300, -104.1),
    (-280, -96.9), (-260, -89.6), (-250, -86.1), (-235, -81.4), (-215, -75.4), (-205, -72.4), (-190, -67.6),
    (-185, -65.9), (-175, -60.5), (-160, -57.3), (-130, -55.2), (-110, -53.1), (-60, -50.6), (0, -48.5),
    (50, -46.0), (100, -41.9), (150, -35.6), (190, -30.4), (196, -30.0), (199, -26.0), (203, -24.8),
    (300, -24.4), (475, -23.7), (600, -22.5), (623, -22.2),
]
STOCK_W = [   # полная ширина
    (-512, 41.5), (-480, 43.0), (-400, 43.0), (-320, 42.0), (-285, 39.5), (-262, 37.0), (-240, 35.0),
    (-210, 35.5), (-188, 38.5), (-170, 43.0), (-150, 45.5), (-100, 46.0), (-50, 45.0), (-25, 43.0),
    (0, 42.0), (50, 40.0), (100, 38.0), (150, 36.0), (196, 35.0), (199, 31.5), (210, 31.0), (400, 30.2),
    (530, 29.6), (623, 29.2),
]
HANDGUARD_TOP = [(165, 15.0), (200, 14.6), (300, 13.6), (475, 12.3), (620, 11.0)]
HANDGUARD_W = [(165, 30.0), (300, 29.0), (620, 26.5)]
BUTT_HEEL, BUTT_TOE = (-503.0, -57.0), (-487.5, -154.8)    # наружная плоскость затыльника
BUTTPLATE_T = 3.0

# ------------------------------------------------------------------ ствол (x, r) — 7.62x54r.net
BARREL_OUT = [(0.0, 12.4), (23.9, 12.4), (23.9, 15.05), (74.7, 13.9), (78.5, 13.6), (84.0, 10.4),
              (87.4, 9.9), (MUZZLE, 7.38)]


def barrel_radius(x: float) -> float:
    return L.smooth_interp(BARREL_OUT[2:], x)


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _section_params(x: float, h: float, hw: float) -> tuple[float, float, float]:
    """Скругление верха, низа и полуширина низа сечения; между зонами — плавный переход."""
    butt = (min(11.0, h * 0.3), 9.0, hw - 1.0)        # приклад: плоские щёки, скруглённые гребень и низ
    wrist = (hw * 0.85, hw * 0.92, hw)                 # шейка — почти овал
    rcv = (2.5, 15.0, hw - 1.5)                        # у коробки: сверху выборка, снизу толстое скругление
    fwd = (2.5, 14.0, hw - 1.5)
    if x >= 198:                                       # цевьё за кольцом: низ полукругом
        return (2.0, min(hw * 0.9, h * 0.6), hw - 0.5)
    zones = [(-290.0, -240.0, butt, wrist), (-192.0, -160.0, wrist, rcv), (15.0, 35.0, rcv, fwd)]
    if x <= zones[0][0]:
        return butt
    for i, (x0, x1, a, b) in enumerate(zones):
        if x < x0:
            return zones[i - 1][3]
        if x <= x1:
            t = _smoothstep((x - x0) / (x1 - x0))
            return tuple(p + (q - p) * t for p, q in zip(a, b))
    return fwd


def _wrist_groove(y: float) -> float:
    """Дно ложбины за коробкой (под грибок курка Ø22): плоское по хвостовику, стенки — четверть круга R6."""
    a = abs(y)
    if a <= 6.0:
        return -12.0
    if a < 12.0:
        return -6.0 - math.sqrt(36.0 - (a - 6.0) ** 2)
    return 1e9


def stock_section(x: float):
    zt = L.smooth_interp(STOCK_TOP, x, 1.5)
    zb = L.smooth_interp(STOCK_BOT, x, 1.5 if 190 < x < 210 else 3.0)
    hw = L.smooth_interp(STOCK_W, x, 2.0) / 2
    rt, rb, hwb = _section_params(x, zt - zb, hw)
    pts = L.rounded_rect_yz(zt, zb, hw, rt, rb, SEC, hwb)
    if -210.0 < x < -160.0:
        # ложбина в верху шейки: грибок проходит над деревом, когда затвор закрыт и при отводе
        pts = [(y, min(z, _wrist_groove(y))) for y, z in pts]
    return [(x, y, z) for y, z in pts]


def build_stock(col):
    xs = []
    x = -512.0
    while x < 623.0:
        xs.append(x)
        # гуще у магазина: иначе кромка выреза в дереве идёт «пилой» по шагу сечений
        x += 2.0 if (x < -150 or 185 < x < 215) else (1.5 if -125 < x < 15 else 4.0)
    xs.append(623.0)
    secs = [stock_section(x) for x in xs]
    # скругление переднего торца цевья: последние сечения сжимаются к центру
    for k, shrink in ((-1, 0.82), (-2, 0.93), (-3, 0.98)):
        cx = sum(p[1] for p in secs[k]) / SEC
        cz = sum(p[2] for p in secs[k]) / SEC
        secs[k] = [(p[0], cx + (p[1] - cx) * shrink, cz + (p[2] - cz) * shrink) for p in secs[k]]
    stock = L.loft("Stock", secs, "Wood_Stock", col, smooth_angle=50)

    # затылок: срез плоскостью затыльника (дерево кончается на толщине пластины)
    heel, toe = Vector((BUTT_HEEL[0], 0, BUTT_HEEL[1])), Vector((BUTT_TOE[0], 0, BUTT_TOE[1]))
    d = (toe - heel).normalized()
    n = Vector((-d.z, 0, d.x))
    if n.x < 0:
        n = -n
    cut = _plane_box(heel + n * BUTTPLATE_T, n, d, 400, "cut_butt")
    L.boolean(stock, cut)

    # канал под ствол, коробку и хвостовик
    prof = [(-200, 0), (-200, 7.0), (-170.5, 7.0), (-170.5, 16.0), (24.5, 16.0), (24.5, 15.4), (74.7, 14.3),
            (84.0, 10.8), (90.0, 10.4), (623 + 5, 8.2), (623 + 5, 0)]
    L.boolean(stock, L.lathe("cut_channel", prof, 64))
    # паз под хвостовик коробки (хвостовик лежит в нём заподлицо с дном ложбины)
    top = lambda x: L.smooth_interp(STOCK_TOP, x, 1.5)  # noqa: E731
    tt = lambda x: min(top(x), -12.2) + 0.3  # noqa: E731
    inlet = [(-207.5, tt(-207.5) + 2.5), (-188.0, tt(-188.0) + 2.5), (-172.0, tt(-172.0) + 2.5), (-163.0, -9.4),
             (-163.0, -15.7), (-172.0, tt(-172.0) - 4.2), (-207.5, tt(-207.5) - 4.2)]
    cut_tang = L.extrude_profile("cut_tang", L.fillet(inlet, [0, 0, 0, 0, 0, 0, 3.5], 6, closed=True),
                                 -9.5, 9.5, None, None, None)
    L.boolean(cut_tang, _tang_plan(0.15), "INTERSECT")
    L.boolean(stock, cut_tang)
    # выемка правой стенки под изогнутую рукоять (ПУ)
    L.boolean(stock, L.extrude_profile("cut_handle_relief", L.fillet([(-102.0, -9.0), (-89.0, -9.0), (-89.0, 12.0),
                                                                       (-102.0, 12.0)], [4.5, 4.5, 0, 0], 6,
                                                                      closed=True), -32.0, -12.0, None, None, None))
    # магазин и спусковая скоба
    L.boolean(stock, _magazine_cutter())
    # пазы под пальцы с обеих сторон
    for side in (-1, 1):
        L.boolean(stock, _groove_cutter(side))
    # прорези под ремень (антабки-«собачки»)
    L.boolean(stock, _slot_cutter((-328.0, -85.5), 21.0, 6.0, -20.0))
    L.boolean(stock, _slot_cutter((444.0, -13.0), 17.0, 5.5, 0.0))
    # канал шомпола
    L.boolean(stock, L.lathe("cut_rod", [(30, 0), (30, 3.2), (630, 3.2), (630, 0)], 24,
                             origin=(0, 0, -21.3)))
    stock.data.shade_smooth()
    stock.data.set_sharp_from_angle(angle=math.radians(50))
    return stock


def _plane_box(origin: Vector, normal: Vector, along: Vector, size: float, name: str):
    """Большой брусок по одну сторону плоскости (со стороны −normal)."""
    side = normal.cross(along).normalized()
    c = origin - normal * size / 2
    verts = []
    for a in (-1, 1):
        for b in (-1, 1):
            for e in (-1, 1):
                p = c + normal * a * size / 2 + along * b * size + side * e * size
                verts.append(tuple(v * L.MM for v in p))
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = L.mesh_object(name, verts, faces, None, None, None)
    L.fix_normals(ob)
    return ob


def _chaikin(pts, iterations: int = 3):
    """Сглаживание замкнутого контура срезанием углов (Чайкин): гладкая кривая по опорным точкам обводки."""
    for _ in range(iterations):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


def _tang_plan(grow: float):
    """Хвостовик коробки в плане: ширина 14 мм, задний конец полукруглый; grow — зазор паза в ложе."""
    hw, r = 7.0 + grow, 6.5 + grow
    outline = L.fillet([(-163.0, -hw), (-206.0 - grow, -hw), (-206.0 - grow, hw), (-163.0, hw)], [0, r, r, 0], 10,
                       closed=True)
    return L.extrude_profile("tang_plan", outline, -40.0, 0.0, None, None, None, plane="XY")


def _magazine_cutter():
    box = [(-116.6, -10.0), (-116.6, -81.0), (-20, -66), (8.6, -52), (8.6, -45.4), (-11.4, -45.4), (-11.4, -10.0)]
    cut = L.extrude_profile("cut_mag", box, -9.8, 9.8, None, None, None)
    bow = [(-207.0, -19.0), (-204.4, -67.6), (-185.0, -61.8), (-176.0, -59.6), (-175.4, -63.0), (-174.8, -70.0),
           (-114, -90), (-114, -49.6), (-196.0, -19.0)]
    L.boolean(cut, L.extrude_profile("cut_bow_tang", bow, -4.8, 4.8, None, None, None), "UNION")
    return cut


def _groove_cutter(side: int):
    """Удлинённый паз под пальцы: капсула 124×12 мм, глубина 3,2 мм — один замкнутый лофт эллипсов."""
    x0, x1, zc, rz = -16.0, 108.0, -17.0, 6.0
    ry = 3.3 * 1.6
    hw = L.smooth_interp(STOCK_W, 46.0) / 2
    yc = side * (hw + ry - 3.2)
    secs = []
    n = 48
    xs = [x0 + rz * (1 - math.cos(math.pi / 2 * i / 8)) for i in range(9)]
    xs += [x0 + rz + (x1 - x0 - 2 * rz) * i / 12 for i in range(1, 12)]
    xs += [x1 - rz * (1 - math.cos(math.pi / 2 * i / 8)) for i in range(8, -1, -1)]
    for x in xs:
        e = min(x - x0, x1 - x)
        k = math.sqrt(max(0.0, 1 - ((rz - min(e, rz)) / rz) ** 2)) if e < rz else 1.0
        k = max(k, 0.02)
        secs.append([(x, yc + ry * k * math.cos(2 * math.pi * j / n), zc + rz * k * math.sin(2 * math.pi * j / n))
                     for j in range(n)])
    return L.loft("cut_groove", secs, None, None, cap_center=True)


def _slot_cutter(center, length, height, angle_deg):
    r = height / 2
    pts = []
    for k in range(17):
        a = math.pi / 2 + math.pi * k / 16
        pts.append((-length / 2 + r + r * math.cos(a), r * math.sin(a)))
    for k in range(17):
        a = -math.pi / 2 + math.pi * k / 16
        pts.append((length / 2 - r + r * math.cos(a), r * math.sin(a)))
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    outline = [(center[0] + u * ca - v * sa, center[1] + u * sa + v * ca) for u, v in pts]
    return L.extrude_profile("cut_slot", outline, -40, 40, None, None, None)


# ------------------------------------------------------------------ металл

def build_barrel(col):
    outer = list(BARREL_OUT)
    crown = [(MUZZLE, 7.38), (MUZZLE, 5.2), (MUZZLE - 0.6, 3.81)]
    bore = [(56.0, 3.81), (54.2, 3.98), (53.9, 4.32), (44.3, 4.32), (39.7, 5.83), (1.6, 6.22),
            (1.6, 7.30), (0.0, 7.30)]
    prof = outer[:-1] + crown + bore
    radii = [0.0] * len(prof)
    radii[2] = 0.8      # кромка плеча у коробки
    radii[4] = 3.0      # уступ B → C
    radii[5] = 1.5
    radii[len(outer) - 1] = 0.6   # кромка дульного среза
    prof = L.fillet(prof, radii, seg=6, closed=False)
    ob = L.lathe("Barrel", prof, 96, "Steel_Blued", col, closed=True)
    return ob


def build_receiver(col):
    """Круглая ствольная коробка: кольцо, окно с левой стенкой, задняя часть, хвостовик."""
    r_out, r_in = 15.65, 9.35
    ring = L.lathe("Receiver", [(-170, r_in), (-170, r_out), (24.0, r_out), (24.0, r_in)],
                   96, "Steel_Blued", col, closed=True)
    # окно: справа и сверху от левой стенки (стенка слева y > +6), за кольцом
    L.boolean(ring, _box("cut_port", (-112.5, -28.0), (-30, 6.0), (1.0, 30)))
    # вырез правой стенки под рукоять затвора в закрытом положении
    L.boolean(ring, _box("cut_handle", (-101.5, -89.0), (-30, -4.0), (-6.0, 30)))
    # ниша отсекателя-отражателя в левой стенке окна
    L.boolean(ring, _box("cut_interrupter", (-104.0, -48.0), (8.9, 11.4), (-6.5, 3.5)))
    # задняя часть: стенки ниже — затвор и курок лежат сверху
    L.boolean(ring, _box("cut_rear", (-180, -104.5), (-30, 30), (0.0, 30)))
    # окно магазина снизу
    L.boolean(ring, _box("cut_magwin", (-108, -30), (-8.2, 8.2), (-30, -4.0)))
    # хвостовик по верху шейки ложи (заподлицо с деревом)
    top = lambda x: L.smooth_interp(STOCK_TOP, x, 1.5)  # noqa: E731
    tt = lambda x: min(top(x), -12.2) + 0.3  # noqa: E731
    tang_pts = [(-206.0, tt(-206.0)), (-188.0, tt(-188.0)), (-172.0, tt(-172.0)), (-165.0, -11.9),
                (-165.0, -15.5), (-172.0, tt(-172.0) - 4.0), (-206.0, tt(-206.0) - 4.0)]
    tang = L.extrude_profile("Receiver_Tang", L.fillet(tang_pts, [1.0, 0, 0, 1, 1, 0, 3], 6, closed=True),
                             -9.0, 9.0, "Steel_Blued", col)
    # в плане конец хвостовика полукруглый (ширина 14 мм)
    L.boolean(tang, _tang_plan(0.0), "INTERSECT")
    L.bevel_mod(tang, 1.2)
    ring.data.shade_smooth()
    ring.data.set_sharp_from_angle(angle=math.radians(35))
    L.bevel_mod(ring, 0.5, 2)
    return ring, tang


def build_receiver_extras(col):
    out = []
    # отсекатель-отражатель на левой стенке окна
    cut = L.extrude_profile("Receiver_Interrupter", L.fillet([(-104, -5.5), (-56, -5.5), (-48, -2.0), (-48, 2.5),
                                                               (-104, 2.5)], [0.5, 2, 1.5, 0.5, 0.5], 4,
                                                              closed=True), 9.05, 10.3, "Steel_Blued", col)
    L.bevel_mod(cut, 0.3, 2)
    out.append(cut)
    # винт хвостовика
    s = L.lathe("Receiver_TangScrew", L.fillet([(0, 0), (0, 4.2), (1.0, 4.2), (1.5, 0)], [0, 0, 0.7, 0], 3), 32,
                "Steel_Blued", col, axis="X")
    s.matrix_world = Matrix.Translation(Vector((-196.0, 0.0, L.smooth_interp(STOCK_TOP, -196.0, 1.5) + 0.2)) * L.MM) \
        @ _basis_from_x(Vector((0.35, 0, 1.0))).to_4x4()
    out.append(s)
    return out


def _box(name, xr, yr, zr):
    x0, x1 = xr
    y0, y1 = yr
    z0, z1 = zr
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    v = [tuple(c * L.MM for c in p) for p in v]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = L.mesh_object(name, v, faces, None, None, None)
    L.fix_normals(ob)
    return ob


def build_bolt(col):
    """Затвор закрыт. Стебель с изогнутой рукоятью (ПУ), личинка, курок с грибком."""
    root = L.empty("Bolt", (0, 0, 0), col, 0.02)
    body = L.lathe("Bolt_Body", L.fillet([(-104, 0), (-104, 8.9), (-20, 8.9), (-20, 0)], [0, 0.8, 0.5, 0], 4),
                   64, "Steel_Bright", col)
    head = L.lathe("Bolt_Head", L.fillet([(-20, 0), (-20, 8.9), (-0.2, 8.9), (-0.2, 7.5), (-1.8, 7.5),
                                          (-1.8, 0)], [0, 0.4, 0.6, 0.2, 0.2, 0], 4), 64, "Steel_Bright", col)
    # рукоять: от стебля вправо, затем вниз вдоль ложи; шар Ø18,7
    path = [(-95.5, -6.0, 0.5), (-95.5, -16.0, 0.5), (-95.0, -22.5, -0.5), (-93.5, -27.0, -5.0),
            (-92.0, -28.6, -12.0), (-90.8, -29.3, -24.0), (-90.0, -29.6, -37.0), (-89.6, -29.8, -42.5)]
    radii = [5.2, 5.0, 4.8, 4.6, 4.5, 4.4, 4.4, 4.6]
    handle = L.sweep_circle("Bolt_Handle", path, radii, 32, "Steel_Bright", col)
    ball = L.lathe("Bolt_Handle_Ball", [(-9.35, 0)] + [(-9.35 * math.cos(a), 9.35 * math.sin(a))
                                                         for a in [math.pi * k / 24 for k in range(1, 24)]]
                   + [(9.35, 0)], 48, "Steel_Bright", col, origin=(0, 0, 0), axis="Z")
    ball.location = Vector((-89.5, -30.0, -48.0)) * L.MM
    # курок: корпус с гребнем — лофт, сечение «D»: круглый низ по стеблю, скруглённый верх
    ramp = [(-168.0, 4.5), (-163.0, 6.5), (-157.0, 10.0), (-152.0, 12.8), (-146.0, 14.3), (-120.0, 14.5),
            (-104.5, 14.5)]
    secs = []
    x = -168.0
    while x <= -104.5 + 1e-6:
        zt = L.smooth_interp(ramp, x, 1.0)
        hw = 8.6
        # торцы: округление в плане
        e = min(x + 168.0, -104.5 - x)
        if e < 3.0:
            hw *= 0.75 + 0.25 * (e / 3.0) ** 0.5
        pts = L.rounded_rect_yz(zt, -8.4, hw, min(5.0, hw * 0.6), hw * 0.98, 64)
        secs.append([(x, y, z) for y, z in pts])
        x += 1.0 if (x < -150 or x > -108) else 3.0
    cocking = L.loft("Bolt_CockingPiece", secs, "Steel_Bright", col, smooth_angle=45)
    knob = L.lathe("Bolt_Knob", L.fillet([(-178.0, 0), (-178.0, 11.0), (-172.5, 11.0), (-172.5, 5.0),
                                          (-167.0, 5.0), (-167.0, 0)], [0, 0.8, 0.8, 1.5, 0, 0], 4),
                   64, "Steel_Bright", col)
    # иерархия движения: Bolt — ход вдоль X (весь затвор), Bolt_Rotor — поворот стебля с рукоятью вокруг оси
    # канала (у Мосина личинка и курок при открывании не вращаются)
    rotor = L.empty("Bolt_Rotor", (0, 0, 0), col, 0.015)
    rotor.parent = root
    for ob in (body, handle, ball):
        ob.parent = rotor
    for ob in (head, cocking, knob):
        ob.parent = root
    return root


def build_magazine(col):
    """Магазинная коробка (полая, с подавателем), спусковая скоба с хвостовиком, защёлка, спусковой крючок."""
    box_out = [(-116.0, -12.0), (-116.0, -80.5), (-110, -82.3), (-100, -81.7), (-75, -79.2), (-50, -72.9),
               (-25, -65.0), (-12, -58.0), (-4, -52.5), (8, -50.5), (8, -46.0), (-12.0, -46.0), (-12.0, -12.0)]
    radii = [0, 2, 1.5, 1, 4, 6, 6, 5, 4, 2, 0, 1, 0]
    box = L.extrude_profile("Magazine_Box", L.fillet(box_out, radii, 6, closed=True), -9.5, 9.5,
                            "Steel_Blued", col)
    # полость: открыта вверх в окно коробки
    cav = L.fillet([(-109.0, 0.0), (-109.0, -77.5), (-75, -76.3), (-50, -70.0), (-33.0, -64.0), (-31.0, -50.0),
                    (-31.0, 0.0)], [0, 3, 3, 5, 3, 1, 0], 6, closed=True)
    L.boolean(box, L.extrude_profile("cut_cav", cav, -7.6, 7.6, None, None, None))
    # переднее ушко: окно под винт
    L.boolean(box, L.lathe("cut_screw", [(-30, 0), (-30, 2.3), (30, 2.3), (30, 0)], 24, axis="Z",
                           origin=(0.0, 0.0, -48.0)))
    # швы крышки магазина на боках (узкие пропилы)
    for xs in (-98.0, -60.0):
        L.boolean(box, _box("cut_seam", (xs - 0.25, xs + 0.25), (-12, 12), (-90, -58.0)))
    L.bevel_mod(box, 0.8, 3)
    # подаватель: пустой магазин — поднят до затвора
    follower = L.extrude_profile("Magazine_Follower", L.fillet([(-107.5, -10.6), (-34.0, -11.6), (-34.0, -14.0),
                                                                 (-107.5, -13.0)], 0.8, 3, closed=True),
                                 -7.3, 7.3, "Steel_Blued", col)
    L.bevel_mod(follower, 0.4, 2)
    # спусковая скоба: дуга с хвостовиком, узкая (9 мм), скруглённая
    # спусковая скоба по снимку RIA 265: задняя дужка почти отвесная (выходит из дерева у x −175),
    # дно плоское; сверху — пластина по низу ложи с прорезью под спуск
    bow_out = [(-206.0, -26.0), (-204.0, -67.0), (-185.0, -61.0), (-175.2, -58.8), (-174.6, -63.0), (-174.0, -70.0),
               (-172.6, -77.0), (-169.5, -82.0), (-164.5, -86.2), (-157.0, -88.8), (-148.0, -89.5), (-132.0, -89.5),
               (-124.0, -88.6), (-119.5, -86.0), (-116.1, -82.6), (-116.1, -50.0), (-172.0, -52.0), (-196.0, -24.0)]
    bow = L.extrude_profile("TriggerGuard", L.fillet(bow_out, [0, 3, 3, 2, 3, 5, 5, 5, 5, 5, 3, 3, 4, 4, 2, 0, 2, 2],
                                                     14, closed=True), -4.5, 4.5, "Steel_Blued", col)
    hole = L.fillet([(-170.0, -57.5), (-170.0, -84.4), (-118.3, -84.4), (-118.3, -57.5)], [1.0, 9.0, 4.0, 1.0], 14,
                    closed=True)
    L.boolean(bow, L.extrude_profile("cut_bow", hole, -20, 20, None, None, None))
    L.boolean(bow, _box("cut_trigger_slot", (-158.8, -145.8), (-3.4, 3.4), (-60.0, -45.0)))
    L.bevel_mod(bow, 1.6, 4)
    latch = L.extrude_profile("Magazine_Latch", L.fillet([(-114, -81.5), (-96, -81.0), (-96, -84.3), (-112, -84.8)],
                                                         0.8, 3, closed=True), -5.0, 5.0, "Steel_Bright", col)
    L.bevel_mod(latch, 0.5, 2)
    # спусковой крючок: изогнутая пластина, вогнутая спереди; обводка по снимку RIA 265 (сетка 1 мм),
    # ширина 6 мм — оценка; верх уходит в паз ложи
    trig = [(-147.0, -50.0), (-147.5, -56.0), (-150.4, -60.0), (-152.9, -62.0), (-154.8, -64.0), (-156.0, -66.0),
            (-157.0, -69.0), (-157.5, -72.0), (-157.3, -75.0), (-156.6, -78.0), (-155.8, -80.0), (-157.2, -81.0),
            (-158.8, -80.2), (-160.3, -78.0), (-161.5, -75.0), (-161.9, -70.0), (-161.0, -65.0), (-160.0, -62.0),
            (-157.9, -60.0), (-156.5, -57.0), (-156.0, -50.0)]
    trigger = L.extrude_profile("Trigger", _chaikin(trig, 3), -3.0, 3.0, "Steel_Blued", col, smooth_angle=40)
    L.bevel_mod(trigger, 0.9, 3)
    L.set_origin_mm(trigger, (-152.0, 0.0, -52.0))       # ось спуска (оценка)
    screw = L.lathe("Magazine_FrontScrew", L.fillet([(0, 0), (0, 4.0), (-1.3, 4.0), (-2.0, 0)], [0, 0, 0.8, 0], 3),
                    32, "Steel_Blued", col, axis="Z", origin=(0.0, 0.0, -50.5))
    return box, follower, bow, latch, trigger, screw


def build_sights(col):
    # колодка прицела: обойма на стволе и две щеки с подъёмом вперёд
    sleeve = L.lathe("RearSight_Base", [(86.0, 9.8), (86.0, 12.2), (163.5, 12.2), (163.5, 9.8)], 64,
                     "Steel_Blued", col, closed=True)
    cheek = L.fillet([(86.0, 4.0), (86.0, 12.5), (100.0, 18.6), (150.0, 19.8), (163.5, 19.8), (163.5, 4.0)],
                     [0, 1.5, 6, 4, 1.0, 0], 6, closed=True)
    parts = [sleeve]
    for y0, y1 in ((8.8, 11.8), (-11.8, -8.8)):
        c = L.extrude_profile("RearSight_Cheek", cheek, y0, y1, "Steel_Blued", col)
        L.bevel_mod(c, 0.5, 2)
        parts.append(c)
    # прицельная планка (лежит), хомутик и целик сзади
    leaf_root = L.empty("RearSight_Leaf", (160.0, 0, 18.5), col, 0.01)
    leaf = L.extrude_profile("RearSight_Leaf_Mesh", L.fillet([(78.5, 19.0), (161.5, 19.0), (161.5, 22.0),
                                                               (85.0, 22.2), (82.5, 25.8), (78.5, 25.0)],
                                                              [0.5, 1.5, 1.0, 1.0, 1.2, 1.0], 4, closed=True),
                             -5.0, 5.0, "Steel_Blued", col)
    L.bevel_mod(leaf, 0.4, 2)
    slider = L.extrude_profile("RearSight_Slider", L.fillet([(92.0, 18.3), (105.5, 18.3), (105.5, 25.0),
                                                              (92.0, 25.0)], 1.0, 3, closed=True),
                               -7.5, 7.5, "Steel_Blued", col)
    L.bevel_mod(slider, 0.6, 2)
    L.parent_keep(leaf, leaf_root)
    L.parent_keep(slider, leaf_root)
    # мушка: основание на стволе, намушник (кольцо вдоль канала), пенёк
    fs_sleeve = L.lathe("FrontSight_Base", L.fillet([(689.5, 7.5), (689.5, 9.4), (702.5, 9.4), (702.5, 7.5)],
                                                     [0, 0.6, 0.6, 0], 3), 64, "Steel_Blued", col, closed=True)
    fs_block = L.extrude_profile("FrontSight_Block", L.fillet([(690.0, 6.0), (702.0, 6.0), (702.0, 14.2),
                                                                (690.0, 14.2)], 0.8, 3, closed=True),
                                 -5.2, 5.2, "Steel_Blued", col)
    L.bevel_mod(fs_block, 0.4, 2)
    hood = L.lathe("FrontSight_Hood", L.fillet([(690.5, 8.1), (690.5, 9.5), (701.5, 9.5), (701.5, 8.1)],
                                               [0, 0.5, 0.5, 0], 3), 64, "Steel_Blued", col, closed=True,
                   origin=(0, 0, 22.75))
    post = L.extrude_profile("FrontSight_Post", [(694.2, 13.0), (697.8, 13.0), (696.8, 23.0), (695.2, 23.0)],
                             -1.0, 1.0, "Steel_Blued", col)
    return parts + [leaf_root, fs_sleeve, fs_block, hood, post]


def section_at(x):
    zt = L.smooth_interp(HANDGUARD_TOP, x)
    zb = L.smooth_interp(STOCK_BOT, x, 1.5)
    hw = max(L.smooth_interp(HANDGUARD_W, x), L.smooth_interp(STOCK_W, x)) / 2
    return zt, zb, hw


def build_handguard(col):
    secs = []
    x = 165.0
    while x <= 621.0:
        zt = L.smooth_interp(HANDGUARD_TOP, x)
        hw = L.smooth_interp(HANDGUARD_W, x) / 2
        pts = L.rounded_rect_yz(zt, 0.4, hw, hw * 0.92, 1.2, SEC)
        secs.append([(x, y, z) for y, z in pts])
        x += 4.0
    hg = L.loft("Handguard", secs, "Wood_Stock", col, smooth_angle=50)
    L.boolean(hg, L.lathe("cut_hg", [(150, 0), (150, 11.2), (640, 9.0), (640, 0)], 64))
    hg.data.shade_smooth()
    hg.data.set_sharp_from_angle(angle=math.radians(50))
    # обоймицы накладки: сзади у колодки и спереди у ствола
    rear = L.ring_tube("Handguard_Ferrule_Rear",
                       *[_hg_loop(165.0, d) for d in (0.6, 0.0)], 165.0, 171.0, "Steel_Blued", col)
    front = L.ring_tube("Handguard_Ferrule_Front",
                        *[_hg_loop(613.0, d) for d in (0.6, 0.0)], 609.0, 621.5, "Steel_Blued", col)
    return hg, rear, front


def _hg_loop(x, grow):
    zt = L.smooth_interp(HANDGUARD_TOP, x) + grow
    hw = L.smooth_interp(HANDGUARD_W, x) / 2 + grow
    return L.rounded_rect_yz(zt, 0.4 - grow * 0.0, hw, hw * 0.92, 1.2, SEC)


def build_bands(col):
    out = []
    for name, x0, x1 in (("Band_Rear", 200.5, 207.5), ("Band_Front", 532.5, 539.8)):
        xm = (x0 + x1) / 2
        zt, zb, hw = section_at(xm)
        inner = L.rounded_rect_yz(zt + 0.1, zb - 0.1, hw + 0.1, hw * 0.92, min(hw * 0.9, 12), SEC)
        outer = L.rounded_rect_yz(zt + 1.6, zb - 1.6, hw + 1.6, hw * 0.92 + 1.6, min(hw * 0.9, 12) + 1.6, SEC)
        b = L.ring_tube(name, outer, inner, x0, x1, "Steel_Blued", col)
        L.bevel_mod(b, 0.4, 2)
        out.append(b)
    return out


def build_fittings(col):
    out = []
    # затыльник: пластина по контуру торца + верхний ус
    heel, toe = Vector((BUTT_HEEL[0], 0, BUTT_HEEL[1])), Vector((BUTT_TOE[0], 0, BUTT_TOE[1]))
    d = (toe - heel).normalized()
    n = Vector((-d.z, 0, d.x))
    if n.x < 0:
        n = -n
    # контур пластины в её плоскости: u — от пятки к носку, v — поперёк (ширина ложи), углы скруглены
    length = (toe - heel).length
    hw0 = L.smooth_interp(STOCK_W, -500) / 2 - 0.3
    outline2d = L.fillet([(0, -hw0), (length, -hw0 + 1.5), (length, hw0 - 1.5), (0, hw0)],
                         [9.0, 8.0, 8.0, 9.0], 8, closed=True)
    m = len(outline2d)
    verts = []
    for t in (0.0, BUTTPLATE_T):
        for u, v in outline2d:
            p = heel + d * u + n * t + Vector((0, v, 0))
            verts.append(tuple(c * L.MM for c in p))
    faces = [(k, (k + 1) % m, m + (k + 1) % m, m + k) for k in range(m)]
    faces += [tuple(reversed(range(m))), tuple(range(m, 2 * m))]
    bp = L.mesh_object("Buttplate", verts, faces, "Steel_Blued", col, 40)
    L.fix_normals(bp)
    L.bevel_mod(bp, 0.8, 3)
    out.append(bp)
    for u in (12.0, length - 14.0):
        p = heel + d * u
        s = L.lathe("Buttplate_Screw", L.fillet([(0, 0), (0, 4.0), (0.8, 4.0), (1.4, 0)], [0, 0, 0.6, 0], 3),
                    32, "Steel_Blued", col, axis="X")
        s.matrix_world = Matrix.Translation(p * L.MM) @ _basis_from_x(-n).to_4x4()
        out.append(s)
    # обоймицы прорезей под ремень с обеих сторон
    for center, length_s, h, ang in (((-328.0, -85.5), 21.0, 6.0, -20.0), ((444.0, -13.0), 17.0, 5.5, 0.0)):
        for side in (-1, 1):
            hw = L.smooth_interp(STOCK_W, center[0]) / 2
            out.append(_escutcheon(center, length_s, h, ang, side, hw, col))
    # ложевые пружины (правая сторона) и поперечный винт
    for x0, x1 in ((208.0, 241.0), (522.0, 582.0)):
        hw = L.smooth_interp(STOCK_W, (x0 + x1) / 2) / 2
        sp = L.extrude_profile("Band_Spring", L.fillet([(x0, -13.6), (x1, -13.4), (x1, -10.6), (x0, -10.4)],
                                                        1.2, 3, closed=True), -hw - 0.7, -hw + 1.0,
                               "Steel_Blued", col)
        L.bevel_mod(sp, 0.3, 2)
        out.append(sp)
    for side in (-1, 1):
        hw = L.smooth_interp(STOCK_W, 5.0) / 2
        s = L.lathe("Stock_CrossScrew", L.fillet([(0, 0), (0, 5.4), (1.2, 5.4), (2.0, 0)], [0, 0, 1.0, 0], 3),
                    40, "Steel_Blued", col, axis="X")
        s.matrix_world = Matrix.Translation(Vector((5.0, side * (hw - 0.6 - 3.2), -18.0)) * L.MM) @ \
            _basis_from_x(Vector((0, side, 0))).to_4x4()
        out.append(s)
    # наконечник ложи и шомпол
    cap = L.extrude_profile("Stock_NoseCap", L.fillet([(621.0, 0.2), (639.0, 0.2), (645.5, -6.0), (645.5, -13.0),
                                                        (639.0, -17.6), (621.0, -18.0)], [0.5, 5, 3, 3, 5, 0.5],
                                                       6, closed=True), -10.5, 10.5, "Steel_Blued", col)
    L.bevel_mod(cap, 1.0, 3)
    L.boolean(cap, L.lathe("cut_cap", [(600, 0), (600, 9.8), (660, 9.8), (660, 0)], 48), "DIFFERENCE")
    out.append(cap)
    rod = L.lathe("CleaningRod", L.fillet([(36.0, 0), (36.0, 2.6), (692.0, 2.6), (692.5, 3.6), (703.0, 3.6),
                                           (703.0, 0)], [0, 0.3, 0.2, 0.4, 0.8, 0], 3), 32, "Steel_Bright", col,
                  origin=(0, 0, -21.3))
    L.boolean(rod, L.lathe("cut_rodhole", [(-5, 0), (-5, 1.6), (5, 1.6), (5, 0)], 24, axis="Y",
                           origin=(698.5, 0, -21.3)))
    out.append(rod)
    return out


def _escutcheon(center, length, h, ang, side, hw, col):
    r = h / 2 + 2.2
    ri = h / 2
    def capsule(rr, ll):
        pts = []
        for k in range(17):
            a = math.pi / 2 + math.pi * k / 16
            pts.append((-ll / 2 + rr + rr * math.cos(a), rr * math.sin(a)))
        for k in range(17):
            a = -math.pi / 2 + math.pi * k / 16
            pts.append((ll / 2 - rr + rr * math.cos(a), rr * math.sin(a)))
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        return [(center[0] + u * ca - v * sa, center[1] + u * sa + v * ca) for u, v in pts]
    outer, inner = capsule(r, length + 4.4), capsule(ri, length)
    y0 = side * (hw - 0.7)
    y1 = side * (hw + 0.6)
    verts = []
    for y in (y0, y1):
        for x, z in outer:
            verts.append((x * L.MM, y * L.MM, z * L.MM))
        for x, z in inner:
            verts.append((x * L.MM, y * L.MM, z * L.MM))
    m = len(outer)
    faces = []
    o0, i0, o1, i1 = 0, m, 2 * m, 3 * m
    for k in range(m):
        k1 = (k + 1) % m
        faces += [(o0 + k, o0 + k1, o1 + k1, o1 + k), (i0 + k, i1 + k, i1 + k1, i0 + k1),
                  (o1 + k, o1 + k1, i1 + k1, i1 + k), (o0 + k, i0 + k, i0 + k1, o0 + k1)]
    ob = L.mesh_object("Sling_Escutcheon", verts, faces, "Steel_Blued", col, 40)
    L.fix_normals(ob)
    L.bevel_mod(ob, 0.3, 2)
    return ob


def _basis_from_x(xdir: Vector):
    x = xdir.normalized()
    up = Vector((0, 0, 1)) if abs(x.z) < 0.9 else Vector((0, 1, 0))
    y = up.cross(x).normalized()
    z = x.cross(y)
    return Matrix((x, y, z)).transposed()


def build():
    L.reset_scene()
    root = L.empty("Mosin_9130PU", col=L.collection("Mosin_9130PU_Rifle"), size=0.05)
    cw = L.collection("Rifle_Wood")
    cm = L.collection("Rifle_Metal")
    cb = L.collection("Rifle_Bolt")
    stock = build_stock(cw)
    hg, fr, ff = build_handguard(cw)
    barrel = build_barrel(cm)
    rcv, tang = build_receiver(cm)
    rcv_extra = build_receiver_extras(cm)
    bolt = build_bolt(cb)
    mag_parts = list(build_magazine(cm))
    sights = build_sights(cm)
    bands = build_bands(cm)
    fittings = build_fittings(cm)
    for ob in [stock, hg, fr, ff, barrel, rcv, tang, bolt] + mag_parts + rcv_extra + sights + bands + fittings:
        if ob.parent is None:
            L.parent_keep(ob, root)
    lo, hi = L.world_bbox_mm([o for o in bpy.context.scene.objects if o.type == "MESH"])
    print("RIFLE bbox mm", tuple(round(v, 1) for v in lo), tuple(round(v, 1) for v in hi),
          "size", tuple(round(h - l, 1) for l, h in zip(lo, hi)))
    L.save_blend(OUT)


if __name__ == "__main__":
    build()
