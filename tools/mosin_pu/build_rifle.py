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

OUT = os.path.join(L.ASSET_DIR, "models", "01_Винтовка", "Mosin_9130PU_Rifle_v07.blend")
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
# Клейма (вымышленные — правило владельца: реальных заводов и брендов нет). Казённая часть ствола
# между коробкой и колодкой: строки поперёк ствола, верх букв к дулу; (текст, x середины строки).
STAMP_BARREL = (("ВЕРАСОВСКІЙ", 66.0), ("ОРУЖЕЙНЫЙ ЗАВОДЪ", 61.8), ("1891 г.", 57.6), ("№ 30417", 46.0))
STAMP_SERIAL = "30417"         # номер винтовки — тот же на стебле затвора
CROSS_SCREW = (5.0, -18.0, 5.4)  # поперечный ложевой винт в пазу под пальцы: x, z, радиус шляпки
CROSS_SEAT_GAP = 0.35            # зазор гнезда в дереве вокруг шляпки


def cross_screw_base() -> float:
    """|y| плоскости основания шляпки поперечного винта (дно гнезда в ложе)."""
    return L.smooth_interp(STOCK_W, CROSS_SCREW[0]) / 2 - 0.6 - 3.2


SLING_SLOTS = (((-329.0, -84.8), 21.0, 6.0, 21.0),   # приклад: центр, длина, высота, наклон (+ — передний конец выше)
               ((444.0, -13.0), 17.0, 5.5, 0.0))     # цевьё

# ------------------------------------------------------------------ затвор (v07)
# Устройство — по НСД-46 (рис. «Затвор»), разнесённому виду 7.62x54r.net и снимку RIA 265; что оценено — asset-state.md.
# Углы вокруг оси канала: α = atan2(z, y) — 0° влево, 90° вверх, 180° вправо, 270° вниз. Затвор закрыт:
# гребень стебля и верхний (с выбрасывателем) упор личинки справа, нижний упор слева; открывание — поворот −90°.
HANDLE_DX = 4.5               # рукоять ближе к дулу, чем в v06: так она стоит на гребне на снимках RIA 265 и владельца
RIB_X = (-102.2, -28.5)       # гребень стебля: задний торец — зуб перед кольцом коробки
RIB_Y = (-16.0, -5.0)         # наружная грань — тело стебля
RIB_Z = (-5.4, 6.5)
BODY_X = (-158.5, -42.4)      # трубка стебля: задний торец с кулачком взведения — передний торец
HEAD_X = (-37.0, -0.2)        # боевая личинка: хвост — чашечка под закраину
LUG_X = (-16.0, -2.4)         # боевые упоры личинки
LUG_R = 11.7                  # наружный радиус упоров — вровень с низом соединительной планки (НСД-46)
LUG_HALF = 26.0               # половина углового размера упора, град
COCK_TRAVEL = 9.5             # взведение при повороте рукояти вверх, мм (кулачок стебля; оценка по фото разборки)
EJECTOR_X = (-93.0, -89.0)    # отражательный выступ отсечки-отражателя
EJECTOR_IN = 2.8              # на сколько выступ уходит внутрь коробки, когда под ним личинка, мм
EJECTOR_FROM = 56.4           # ход затвора, после которого выступ целиком над личинкой и может войти в её паз, мм


def _sector(name, prof, a0, a1, mat=None, col=None, step=2.0):
    """Тело из контура (x, r) в мм, повёрнутого вокруг оси канала от угла a0 до a1 (град, α = atan2(z, y))."""
    n = max(2, math.ceil(abs(a1 - a0) / step))
    secs = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        p = prof(math.degrees(a)) if callable(prof) else prof
        secs.append([(x, r * math.cos(a), r * math.sin(a)) for x, r in p])
    return L.loft(name, secs, mat, col)


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
    dx = HANDLE_DX
    L.boolean(stock, L.extrude_profile("cut_handle_relief", L.fillet([(-102.0 + dx, -9.0), (-89.0 + dx, -9.0),
                                                                       (-89.0 + dx, 12.0), (-102.0 + dx, 12.0)],
                                                                      [4.5, 4.5, 0, 0], 6, closed=True),
                                       -32.0, -12.0, None, None, None))
    # справа вдоль окна коробки дерево ниже гребня стебля (на снимке RIA 265 под гребнем — щель, затем ложа)
    zr = RIB_Z[0] - 0.7
    L.boolean(stock, L.extrude_profile("cut_rib_relief", L.fillet([(-104.0, zr), (-26.5, zr), (-26.5, 20.0),
                                                                   (-104.0, 20.0)], [3.0, 1.5, 0, 0], 6, closed=True),
                                       -40.0, -8.5, None, None, None))
    # паз под обойму колодки прицела
    L.boolean(stock, L.lathe("cut_rs_base", [(87.0, 0), (87.0, 12.45), (164.0, 12.45), (164.0, 0)], 64))
    # магазин и спусковая скоба
    L.boolean(stock, _magazine_cutter())
    # пазы под пальцы с обеих сторон
    for side in (-1, 1):
        L.boolean(stock, _groove_cutter(side))
    # гнёзда под шляпки поперечного винта: дно паза под пальцы вогнутое, плоская шляпка без гнезда уходила
    # краями в дерево; на снимке RIA 265 головка сидит в круглом высверленном гнезде
    yb, (xs, zs, rs) = cross_screw_base(), CROSS_SCREW
    for y0, y1 in ((yb - 0.02, yb + 12.0), (-yb - 12.0, -yb + 0.02)):
        L.boolean(stock, L.lathe("cut_screw_seat", [(y0, 0), (y0, rs + CROSS_SEAT_GAP), (y1, rs + CROSS_SEAT_GAP),
                                                    (y1, 0)], 64, axis="Y", origin=(xs, 0.0, zs)))
    # прорези под ремень (антабки-«собачки»)
    for slot in SLING_SLOTS:
        L.boolean(stock, _slot_cutter(*slot))
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
    # выемка в казённом срезе под зацеп выбрасывателя: личинка с выбрасывателем поворачивается на 90° (справа → вверх)
    L.boolean(ob, _sector("cut_extractor_relief", [(-0.5, 7.15), (-0.5, 9.0), (1.0, 9.0), (1.0, 7.15)], 72.0, 198.0))

    def wrap(u: float, v: float, h: float):
        # строка вдоль окружности (читается слева направо, если смотреть сверху дулом от себя)
        rr = barrel_radius(v)
        phi = u / rr
        return (v, -(rr + h) * math.sin(phi), (rr + h) * math.cos(phi))
    parts = [L.text_polys(text, 2.2, 0.0, x) for text, x in STAMP_BARREL]
    L.boolean(ob, L.stamp_cutter("cut_stamp_barrel", parts, wrap, 0.15))
    return ob


def build_receiver(col):
    """Круглая ствольная коробка: кольцо, окно с левой стенкой, задняя часть, хвостовик."""
    r_out, r_in = 15.65, 9.35
    ring = L.lathe("Receiver", [(-170, r_in), (-170, r_out), (24.0, r_out), (24.0, r_in)],
                   96, "Steel_Blued", col, closed=True)
    # окно: справа и сверху от левой стенки (стенка слева y > +7,4 — над ней проходит гребень открытого стебля), за кольцом
    L.boolean(ring, _box("cut_port", (-112.5, -28.0), (-30, 7.4), (1.0, 30)))
    # правая стенка окна ниже гребня стебля: в закрытом затворе гребень лежит на ней
    L.boolean(ring, _box("cut_rib", (-103.5, -28.0), (-30, -4.0), (RIB_Z[0] - 0.7, 30)))
    # ниша отсечки-отражателя в левой стенке окна: глубже на ход пружины (пластину отжимает стебель)
    L.boolean(ring, _box("cut_interrupter", (-104.0, -48.0), (8.9, 13.2), (-6.5, 3.5)))
    # кольцо коробки: пазы для упоров личинки (сверху и снизу — затвор открыт) и гнёзда, где упоры поворачиваются
    # на 90° и запирают затвор; нижний паз — и для соединительной планки
    race = [(-31.0, 8.5), (-31.0, LUG_R + 0.55), (LUG_X[0] + 0.0, LUG_R + 0.55), (LUG_X[0] + 0.0, 8.5)]
    for a in (90.0, 270.0):
        L.boolean(ring, _sector("cut_raceway", race, a - LUG_HALF - 2.5, a + LUG_HALF + 2.5, step=1.0))
    seat = [(LUG_X[0] - 0.4, 8.5), (LUG_X[0] - 0.4, LUG_R + 0.55), (-0.05, LUG_R + 0.55), (-0.05, 8.5)]
    for a0, a1 in ((90.0 - LUG_HALF - 2.0, 180.0 + LUG_HALF + 2.0), (-90.0 - LUG_HALF - 2.0, LUG_HALF + 2.0)):
        L.boolean(ring, _sector("cut_lug_seat", seat, a0, a1, step=1.0))
    # паз под соединительную планку по дну коробки (она не вращается и идёт под затвором)
    L.boolean(ring, _box("cut_bar_groove", (-181.0, -28.0), (-3.9, 3.9), (-12.1, -6.0)))
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
    # гнездо винта: потай по нормали к поверхности, фаска 0,7 мм вокруг головки
    sink = L.lathe("cut_screw_sink", [(-2.0, 0), (-2.0, 2.45), (-0.3, 4.2), (0.0, 4.9), (3.0, 4.9), (3.0, 0)], 48,
                   axis="X")
    sink.matrix_world = _tang_screw_frame()
    L.boolean(tang, sink)
    L.bevel_mod(tang, 1.2)
    ring.data.shade_smooth()
    ring.data.set_sharp_from_angle(angle=math.radians(35))
    L.bevel_mod(ring, 0.5, 2)
    return ring, tang


def build_receiver_extras(col):
    out = []
    # отсечка-отражатель на левой стенке окна: пластина с отражательным выступом. Пластина пружинит: пока под ней
    # стебель, она отжата наружу; когда подходит личинка, выступ входит в её паз и выбивает гильзу за закраину
    slide = L.empty("Interrupter_Slide", (0, 0, 0), col, 0.012)
    cut = L.extrude_profile("Receiver_Interrupter", L.fillet([(-104, -5.5), (-56, -5.5), (-48, -2.0), (-48, 2.5),
                                                               (-104, 2.5)], [0.5, 2, 1.5, 0.5, 0.5], 4,
                                                              closed=True), 9.05, 10.1, "Steel_Blued", col)
    lug = L.extrude_profile("ejector", L.fillet([(EJECTOR_X[0], -1.4), (EJECTOR_X[1], -1.4), (EJECTOR_X[1], 1.4),
                                                 (EJECTOR_X[0], 1.4)], 0.4, 3, closed=True),
                            9.05 - EJECTOR_IN - 0.0, 9.6, None, None)
    L.boolean(cut, lug, "UNION")
    L.bevel_mod(cut, 0.25, 2)
    cut.parent = slide
    out.append(slide)
    # винт хвостовика
    frame = _tang_screw_frame()
    s = L.lathe("Receiver_TangScrew", L.fillet([(-1.9, 0), (-1.9, 2.4), (-0.3, 4.15), (-0.05, 4.15), (0.3, 3.4),
                                                (0.5, 0)], [0, 0.2, 0.15, 0.15, 0.5, 0], 3), 48,
                "Steel_Blued", col, axis="X")
    slot = _box("cut_screw_slot", (0.0, 1.5), (-0.5, 0.5), (-5.0, 5.0))
    slot.data.transform(Matrix.Rotation(math.radians(35), 4, "X"))     # шлиц наискось, как на снимке
    L.boolean(s, slot)
    s.matrix_world = frame
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


TANG_SCREW_X = -197.0


def _tang_top(x: float) -> float:
    """Верх хвостовика коробки (как в build_receiver): заподлицо с деревом шейки, не выше −11,9."""
    return min(L.smooth_interp(STOCK_TOP, x, 1.5), -12.2) + 0.3


def _tang_screw_frame() -> Matrix:
    """Матрица винта хвостовика: начало на верхней грани хвостовика, ось X — нормаль к ней."""
    x0, x1 = -206.0, -188.0                       # верхняя грань хвостовика между этими точками — плоскость
    z0, z1 = _tang_top(x0), _tang_top(x1)
    slope = (z1 - z0) / (x1 - x0)
    p = Vector((TANG_SCREW_X, 0.0, z0 + slope * (TANG_SCREW_X - x0)))
    n = Vector((-slope, 0.0, 1.0)).normalized()
    return Matrix.Translation(p * L.MM) @ _basis_from_x(n).to_4x4()


def _bolt_handle(col):
    """Изогнутая рукоять ПУ: выходит из наружной грани гребня стебля с галтелью вдоль гребня (поперёк гребня места
    нет — стебель рукояти почти во всю его высоту), плавный изгиб, галтель R3 к шару Ø18,7."""
    r0, rho, seg = 4.9, 3.0, 48
    dx = HANDLE_DX
    face, flare = RIB_Y[0] + 0.02, 3.6         # основание галтели — на грани гребня; длина галтели, мм
    hx, hz = 7.6, 4.95                         # полуоси основания галтели: вдоль гребня и поперёк

    def flare_r(d: float, a: float) -> float:
        """Радиус кольца на расстоянии d от грани гребня в направлении a (cos a — к +Z, sin a — к −X)."""
        p = 3.0
        base = (abs(math.cos(a) / hz) ** p + abs(math.sin(a) / hx) ** p) ** (-1.0 / p)
        if d <= 0.0:
            return base
        if d >= flare:
            return r0
        u = 1.0 - d / flare                    # 1 у грани, 0 в конце галтели: четверть окружности, касание с обеих сторон
        return r0 + (base - r0) * (1.0 - math.sqrt(max(0.0, 1.0 - u * u)))
    # корень — внутри гребня, затем сплайн Катмулла–Рома по опорным точкам (иначе дуга гранёная)
    path = [Vector((-95.5 + dx, y, 0.0)) for y in (-14.4, -14.9, -15.4)]
    rad = [None] * len(path)                    # у корня и в галтели радиус зависит от направления — считается ниже
    ctrl = [(Vector((-95.5 + dx, -13.5, 0.0)), r0), (Vector((-95.5 + dx, -15.8, 0.0)), r0),
            (Vector((-95.0 + dx, -22.5, -0.5)), 4.85), (Vector((-93.5 + dx, -27.0, -5.0)), 4.7),
            (Vector((-92.0 + dx, -28.6, -12.0)), 4.6), (Vector((-90.8 + dx, -29.3, -24.0)), 4.5),
            (Vector((-90.0 + dx, -29.6, -37.0)), 4.5)]
    for i in range(1, len(ctrl) - 2):
        p0, p1, p2, p3 = (ctrl[j][0] for j in (i - 1, i, i + 1, i + 2))
        steps = 48 if i == 1 else 8             # у галтели кольца гуще
        for k in range(1, steps + 1):
            t = k / steps
            path.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                               + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
            rad.append(ctrl[i][1] + (ctrl[i + 1][1] - ctrl[i][1]) * t)
    path.insert(3, ctrl[1][0].copy())
    rad.insert(3, None)
    # шейка у шара: галтель R3 касается шара
    c, Rb, rn = Vector((-89.5 + dx, -30.0, -48.0)), 9.35, 4.5
    u = (Vector((-90.0 + dx, -29.6, -37.0)) - c).normalized()
    tc = math.sqrt((Rb + rho) ** 2 - (rn + rho) ** 2)
    tt_, rt = tc * Rb / (Rb + rho), (rn + rho) * Rb / (Rb + rho)
    for t in (11.0, tc, 9.6, 9.35, 9.1, 8.8, 8.5, 8.2, 7.9, 7.65, tt_, 6.5):
        path.append(c + u * t)
        rad.append(rn if t >= tc else (rn + rho - math.sqrt(max(0.0, rho ** 2 - (t - tc) ** 2)) if t > tt_ else rt))
    # рамки — параллельный перенос (как в L.sweep_circle); точка кольца = нормаль·cos a + бинормаль·sin a,
    # у корня нормаль +Z, бинормаль −X — по ним и задано основание галтели
    n = len(path)
    tang = [(path[min(n - 1, i + 1)] - path[max(0, i - 1)]).normalized() for i in range(n)]
    normal = Vector((0, 0, 1))
    normal = (normal - tang[0] * normal.dot(tang[0])).normalized()
    verts, faces = [], []
    for i in range(n):
        if i > 0:
            axis = tang[i - 1].cross(tang[i])
            if axis.length > 1e-8:
                normal = Matrix.Rotation(tang[i - 1].angle(tang[i]), 3, axis.normalized()) @ normal
            normal = (normal - tang[i] * normal.dot(tang[i])).normalized()
        binormal = tang[i].cross(normal)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            d = face - path[i].y
            r = flare_r(d, a) if (rad[i] is None or d < flare) else rad[i]
            verts.append(tuple((path[i] + (normal * math.cos(a) + binormal * math.sin(a)) * r) * L.MM))
    for i in range(n - 1):
        a0, b0 = i * seg, (i + 1) * seg
        faces += [(a0 + k, a0 + (k + 1) % seg, b0 + (k + 1) % seg, b0 + k) for k in range(seg)]
    faces.append(tuple(reversed(range(seg))))
    faces.append(tuple(range((n - 1) * seg, n * seg)))
    handle = L.mesh_object("Bolt_Handle", verts, faces, "Steel_Bright", col, 40)
    L.fix_normals(handle)
    ball = L.lathe("Bolt_Handle_Ball", [(-Rb, 0)] + [(-Rb * math.cos(a), Rb * math.sin(a))
                                                    for a in [math.pi * k / 32 for k in range(1, 32)]]
                   + [(Rb, 0)], 64, "Steel_Bright", col, origin=(0, 0, 0), axis="Z")
    ball.location = c * L.MM
    return handle, ball


def _rib_section(x: float):
    """Сечение гребня стебля (затвор закрыт — гребень справа): наружная грань плоская, её кромки скруглены;
    торцы скруглены в боковом виде (сзади R3, у зуба R1), как на снимке RIA 265."""
    zb, zt = RIB_Z
    for x_end, rr in ((RIB_X[0], 3.0), (RIB_X[1], 1.0)):
        e = abs(x - x_end)
        if e < rr:
            d = rr - math.sqrt(max(0.0, rr * rr - (rr - e) ** 2))
            zb, zt = zb + d, zt - d
    rc = min(0.8, (zt - zb) * 0.3)
    y_out, y_in = RIB_Y
    poly = [(y_in, zt), (y_out, zt), (y_out, zb), (y_in, zb)]
    pts = L.resample_closed(L.fillet(poly, [0.0, rc, rc, 0.0], seg=8, closed=True), 72)
    return [(x, y, z) for y, z in pts]


def _cam_profile(a: float):
    """Вырез кулачка взведения в заднем торце стебля (контур x, r при угле a): глубокое гнездо, где стоит выступ
    курка после выстрела, затем винтовой скос — при повороте стебля на 90° он отжимает курок назад на COCK_TRAVEL."""
    deep, end = BODY_X[0] + COCK_TRAVEL + 0.0, BODY_X[0] - 0.3
    if a <= 196.0:
        xf = deep
    else:
        xf = deep + (end - deep) * (a - 196.0) / 91.0
    return [(BODY_X[0] - 1.5, 2.6), (BODY_X[0] - 1.5, 9.6), (xf, 9.6), (xf, 2.6)]


def build_bolt(col):
    """Затвор закрыт, курок спущен (после выстрела). Детали и движение — как у винтовки обр. 1891/30:
    стебель с гребнем и рукоятью и боевая личинка с упорами и выбрасывателем поворачиваются вместе;
    соединительная планка и курок с ударником не вращаются; при повороте рукояти вверх кулачок стебля
    отжимает курок назад (взведение), затем весь затвор отводится назад."""
    root = L.empty("Bolt", (0, 0, 0), col, 0.02)
    # ---- стебель: трубка + гребень, на котором стоит рукоять
    body = L.lathe("Bolt_Body", L.fillet([(BODY_X[0], 3.0), (BODY_X[0], 8.9), (BODY_X[1], 8.9), (BODY_X[1], 3.0)],
                                         [0.0, 0.6, 0.5, 0.0], 4, closed=True), 256, "Steel_Bright", col, closed=True)
    xs, x = [], RIB_X[0]
    while x < RIB_X[1] - 1e-6:
        xs.append(x)
        x += 0.25 if (x < RIB_X[0] + 3.0 or x > RIB_X[1] - 1.25) else 2.0
    xs.append(RIB_X[1])
    rib = L.loft("rib", [_rib_section(x) for x in xs], "Steel_Bright", col)
    L.boolean(body, rib, "UNION")
    # гребень выходит вперёд за трубку и лежит над хвостом личинки: снизу полость по личинке, впереди зуб —
    # за него гребень поворачивает личинку (её задний выступ стоит в вырезе перед зубом)
    # (резаки повёрнуты на полшага относительно вершин трубки: совпадающие вершины рвут сетку при булевой)
    L.boolean(body, L.lathe("cut_rib_hook", [(-42.5, 0), (-42.5, 12.6), (-30.5, 12.6), (-30.5, 9.1), (-28.0, 9.1),
                                             (-28.0, 0)], 128, phase=math.pi / 128))
    # кулачок взведения: справа в заднем торце (там стоит выступ курка)
    L.boolean(body, _sector("cut_cam", _cam_profile, 163.3, 287.0, step=1.0))
    L.cleanup(body, 0.002)              # осколки после булевых — иначе фаска и клеймо дают незамкнутые рёбра
    mod = L.bevel_mod(body, 0.3, 2, 40)
    bpy.context.view_layer.objects.active = body
    with bpy.context.temp_override(object=body, active_object=body):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    L.triangulate(body)

    def wrap_rib(u: float, v: float, h: float):
        # номер на наружной грани гребня, как на снимке RIA 265: читается от дула к прикладу, верх цифр книзу
        return (-54.0 - u, RIB_Y[0] - h, 0.55 - v)
    L.boolean(body, L.stamp_cutter("cut_stamp_bolt", [L.text_polys(STAMP_SERIAL, 3.0, 0.0, 0.0)], wrap_rib, 0.12))
    handle, ball = _bolt_handle(col)

    # ---- боевая личинка: упоры (запирают затвор в кольце коробки), выбрасыватель, пазы отражателя и планки
    # промежуточные кольца по длине: на длинных гранях точная булева оставляет незамкнутые рёбра у пазов
    rings = [(x, 8.9) for x in (-34.0, -31.0, -28.0, -24.0, -20.0, -16.0, -12.0, -8.0, -4.0)]
    head = L.lathe("Bolt_Head", L.fillet([(HEAD_X[0], 1.8), (HEAD_X[0], 8.9)] + rings + [(HEAD_X[1], 8.9),
                                          (HEAD_X[1], 7.5), (-1.8, 7.5), (-1.8, 1.15), (-3.0, 1.15), (-3.0, 1.8)],
                                         [0, 0.4] + [0] * len(rings) + [0.6, 0.2, 0.2, 0, 0, 0], 4, closed=True),
                   128, "Steel_Bright", col, closed=True)
    lug_prof = L.fillet([(LUG_X[0], 8.5), (LUG_X[0], LUG_R), (-6.0, LUG_R), (LUG_X[1], 8.5)], [0, 0.5, 8.0, 0], 8,
                        closed=True)
    for a in (180.0, 0.0):          # затвор закрыт: верхний упор (с выбрасывателем) справа, нижний слева
        L.boolean(head, _sector("lug", lug_prof, a - LUG_HALF, a + LUG_HALF), "UNION")
    # задний выступ: стоит в вырезе гребня — через него стебель поворачивает личинку
    L.boolean(head, _sector("lug_drive", L.fillet([(-35.5, 8.5), (-35.5, 12.3), (-31.5, 12.3), (-31.5, 8.5)],
                                                  [0, 0.5, 0.5, 0], 3, closed=True), 163.4, 196.6), "UNION")
    # паз выбрасывателя справа: открытый вдоль личинки, под упором — туннель, впереди — прорезь в бортике чашечки
    L.boolean(head, _box("cut_extractor", (-31.2, 1.0), (-9.6, -7.55), (-2.05, 2.05)))
    # паз отражателя сверху (у открытого затвора — слева: по нему идёт выступ отсечки-отражателя до самой гильзы)
    L.boolean(head, _box("cut_ejector", (-38.0, 1.0), (-1.6, 1.6), (4.8, 13.0)))
    # кольцевой паз под зуб соединительной планки: личинка поворачивается, планка — нет
    L.boolean(head, _sector("cut_stud", [(-25.4, 6.0), (-25.4, 9.8), (-19.8, 9.8), (-19.8, 6.0)], -114.0, 24.0))
    L.bevel_mod(head, 0.3, 2)
    # выбрасыватель: пластина в пазу личинки, зацеп впереди заходит за закраину гильзы
    ext = L.extrude_profile("Bolt_Extractor", [(-30.8, -7.75), (-30.8, -8.6), (0.4, -8.6), (0.8, -8.2), (0.8, -6.95),
                                               (0.5, -6.6), (-0.2, -6.6), (-0.2, -7.3), (-2.6, -7.3), (-3.0, -7.75)],
                            -1.9, 1.9, "Steel_Bright", col, plane="XY")
    L.bevel_mod(ext, 0.2, 2)

    # ---- соединительная планка: под затвором, не вращается; зуб в кольцевом пазу личинки, стойка с отверстием
    # под ударник между стеблем и личинкой (сверху — лапка, видна в окне коробки), сзади — вилка под выступ курка
    bar = L.extrude_profile("Bolt_ConnectingBar", L.fillet([(-180.0, -LUG_R), (-16.4, -LUG_R), (-16.4, -9.15),
                                                            (-180.0, -9.15)], [0.6, 0.8, 0.8, 0.6], 3, closed=True),
                            -3.6, 3.6, "Steel_Blued", col)
    L.boolean(bar, _box("cut_fork", (-182.0, -152.0), (-1.9, 1.9), (-13.0, -8.0)))
    L.boolean(bar, _box("stud", (-25.2, -20.0), (-2.4, 2.4), (-9.6, -6.2)), "UNION")
    stand = L.lathe("stand", [(-42.2, 1.9), (-42.2, 8.6), (-37.3, 8.6), (-37.3, 1.9)], 96, closed=True)
    L.boolean(stand, _box("stand_tab", (-42.2, -37.3), (-3.0, 3.0), (7.5, 11.3)), "UNION")
    L.boolean(stand, _box("stand_web", (-42.2, -37.3), (-3.6, 3.6), (-9.6, -7.8)), "UNION")
    L.boolean(bar, stand, "UNION")
    L.bevel_mod(bar, 0.3, 2)

    # ---- курок: корпус за стеблем, сверху гребень по стеблю; спереди справа — выступ в кулачке стебля,
    # снизу — выступ боевого взвода в вилке планки
    ramp = [(-168.0, 4.5), (-163.0, 6.8), (-158.5, 10.1), (-155.0, 11.8), (-152.0, 12.8), (-146.0, 14.3),
            (-120.0, 14.5), (-104.5, 14.5)]
    x_front = BODY_X[0] - 0.4
    secs, x = [], -168.0
    while x <= x_front + 1e-6:
        hw = 8.6
        e = x + 168.0
        if e < 3.0:                                  # задний торец — округление в плане
            hw *= 0.75 + 0.25 * (e / 3.0) ** 0.5
        pts = L.rounded_rect_yz(L.smooth_interp(ramp, x, 1.0), -8.4, hw, min(5.0, hw * 0.6), hw * 0.98, 64)
        secs.append([(x, y, z) for y, z in pts])
        x = min(x + 1.0, x_front) if x < x_front - 1e-6 else x + 1.0
    cocking = L.loft("Bolt_CockingPiece", secs, "Steel_Bright", col, smooth_angle=45)
    zb_side = math.sqrt(9.05 ** 2 - 5.4 ** 2)
    arm, x = [], x_front - 0.6
    while x <= -104.5 + 1e-6:
        zt = L.smooth_interp(ramp, x, 1.0)
        hw = 5.4
        e = -104.5 - x
        if e < 2.5:                                  # передний торец — округление в плане
            hw *= 0.8 + 0.2 * (e / 2.5) ** 0.5
        zs = math.sqrt(9.05 ** 2 - hw ** 2)
        rc = max(0.2, min(2.0, (zt - zb_side) * 0.45))
        poly = [(0.0, zt), (hw, zt), (hw, zs)]
        poly += [(hw - 2 * hw * k / 12, math.sqrt(9.05 ** 2 - (hw - 2 * hw * k / 12) ** 2)) for k in range(1, 12)]
        poly += [(-hw, zs), (-hw, zt)]
        pts = L.resample_closed(L.fillet(poly, [0.0, rc] + [0.0] * 13 + [rc], seg=8, closed=True), 64)
        arm.append([(x, y, z) for y, z in pts])
        x += 1.0 if (x < -150 or x > -108) else 3.0
    L.boolean(cocking, L.loft("arm", arm), "UNION")
    L.boolean(cocking, _sector("follower", [(x_front - 0.6, 3.5), (x_front - 0.6, 8.6),
                                             (BODY_X[0] + COCK_TRAVEL - 0.4, 8.6), (BODY_X[0] + COCK_TRAVEL - 0.4, 3.5)],
                               166.0, 194.0), "UNION")
    L.boolean(cocking, _box("sear_lug", (-167.0, -160.5), (-1.6, 1.6), (-11.3, -7.5)), "UNION")
    L.bevel_mod(cocking, 0.3, 2)
    # грибок с гнездом под хвост ударника (кольцо торца — чистые квады, без булевой операции)
    knob = L.lathe("Bolt_Knob", L.fillet([(-174.0, 0), (-174.0, 3.45), (-178.0, 3.45), (-178.0, 3.9),
                                          (-178.0, 10.0), (-178.0, 11.0), (-172.5, 11.0), (-172.5, 5.0),
                                          (-167.0, 5.0), (-167.0, 0)], [0, 0, 0.3, 0, 0, 0.8, 0.8, 1.5, 0, 0], 4),
                   96, "Steel_Bright", col)
    # хвост ударника в центре грибка: выступает на 0,3 мм, шлиц поперёк
    pin_end = L.lathe("Bolt_FiringPin_End", L.fillet([(-178.3, 0), (-178.3, 3.3), (-174.5, 3.3), (-174.5, 0)],
                                                     [0, 0.35, 0, 0], 3), 48, "Steel_Bright", col)
    L.boolean(pin_end, _box("cut_pin_slot", (-179.0, -177.5), (-0.55, 0.55), (-4.0, 4.0)))
    # ударник: виден в зазоре между стеблем и взведённым курком; боёк после выстрела выходит из чашечки на 0,45 мм
    pin = L.lathe("Bolt_FiringPin", L.fillet([(x_front, 0), (x_front, 2.8), (-46.0, 2.8), (-45.0, 1.6), (-3.6, 1.6),
                                              (-3.3, 1.0), (0.1, 1.0), (0.25, 0)], [0, 0.3, 0.3, 0.2, 0.2, 0.2, 0.3, 0],
                                             3), 48, "Steel_Bright", col)

    # ---- иерархия движения: Bolt — ход назад по X; Bolt_Rotor — поворот стебля с личинкой вокруг оси канала;
    # Bolt_Cocking — ход курка с ударником (драйвер от поворота: кулачок; свойство cocked — удержание шепталом)
    root["cocked"] = 0.0
    root.id_properties_ui("cocked").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                           description="1 — курок на боевом взводе (затвор закрыт после перезарядки); "
                                                       "0 — после выстрела. При повороте рукояти вверх курок "
                                                       "взводится сам (кулачок стебля)")
    rotor = L.empty("Bolt_Rotor", (0, 0, 0), col, 0.015)
    rotor.parent = root
    cock = L.empty("Bolt_Cocking", (0, 0, 0), col, 0.012)
    cock.parent = root
    for ob in (body, handle, ball, head, ext):
        ob.parent = rotor
    for ob in (cocking, knob, pin_end, pin):
        ob.parent = cock
    bar.parent = root
    return root


def _driver(ob, path: str, index: int, expr: str, variables) -> None:
    """Драйвер с простым выражением (работает без разрешения Python-скриптов в Blender)."""
    fc = ob.driver_add(path, index)
    d = fc.driver
    d.type = "SCRIPTED"
    for name, target, spec in variables:
        v = d.variables.new()
        v.name = name
        if spec.startswith("["):
            v.type = "SINGLE_PROP"
            v.targets[0].id_type = "OBJECT"
            v.targets[0].id = target
            v.targets[0].data_path = spec
        else:
            v.type = "TRANSFORMS"
            v.targets[0].id = target
            v.targets[0].transform_type = spec
            v.targets[0].transform_space = "LOCAL_SPACE"
    d.expression = expr


def rig_drivers() -> None:
    """Связи движения: курок отходит при повороте стебля (кулачок) или стоит на взводе; отсечка-отражатель
    отжата, пока под ней стебель, и входит выступом в паз личинки, когда та подходит при отводе затвора."""
    ob = bpy.data.objects
    _driver(ob["Bolt_Cocking"], "location", 0,
            f"-{COCK_TRAVEL * L.MM:.4f}*max(min(max(-r/1.5707963,0),1),h)",
            [("r", ob["Bolt_Rotor"], "ROT_X"), ("h", ob["Bolt"], '["cocked"]')])
    _driver(ob["Interrupter_Slide"], "location", 1,
            f"{EJECTOR_IN * L.MM:.4f}*(1-min(max((-{EJECTOR_FROM * L.MM:.4f}-x)/0.002,0),1))",
            [("x", ob["Bolt"], "LOC_X")])


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
    # подаватель: пустой магазин — поднят до соединительной планки, идущей под затвором
    follower = L.extrude_profile("Magazine_Follower", L.fillet([(-107.5, -12.2), (-34.0, -13.2), (-34.0, -15.6),
                                                                 (-107.5, -14.6)], 0.8, 3, closed=True),
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


RS_PIN = (157.5, 16.8)       # ось шарнира прицельной планки (снимок RIA 265)


def _leaf_top(x: float) -> float:
    """Верх прицельной планки в положении «1»: от оси (20,2) с подъёмом 1,8 мм к целику."""
    return 20.2 + (RS_PIN[0] - x) * (1.8 / 72.0)


def _pin_cutter(r: float):
    """Отверстие под ось шарнира планки (вдоль Y)."""
    return L.lathe("cut_pin", [(-20.0, 0), (-20.0, r), (20.0, r), (20.0, 0)], 32, axis="Y",
                   origin=(RS_PIN[0], 0.0, RS_PIN[1]))


def build_sights(col):
    # Прицел обр. 1891/30 в положении «1» (хомутик сзади). Сбоку — снимок RIA 265 (ось шарнира, высоты,
    # хомутик x 85,5…99,5), ширины — снимок планки сверху (длина хомутика 14 мм совпадает на обоих):
    # планка 19,5 мм, целик 21 мм с прорезью ≈2 мм, хомутик 29,5 мм, с кнопками 34 мм.
    px, pz = RS_PIN
    # обойма колодки — по стволу (он сужается к дулу), зазор 0,02 мм
    sleeve = L.lathe("RearSight_Base", [(87.6, barrel_radius(87.6) + 0.02), (87.6, 12.2), (163.5, 12.2),
                                        (163.5, barrel_radius(163.5) + 0.02)], 64, "Steel_Blued", col, closed=True)
    # щёки-секторы: верх — кривая, по которой хомутик поднимает планку; спереди ушки с осью
    sector = [(88.0, 1.5), (88.0, 14.6), (100.0, 15.4), (110.0, 16.5), (120.0, 17.7), (130.0, 18.9),
              (140.0, 19.9), (147.0, 20.6), (152.0, 21.5), (160.0, 21.5), (163.5, 18.0), (163.5, 1.5)]
    radii = [0, 1.0, 8, 10, 10, 10, 10, 6, 3, 3, 3, 0]
    parts = [sleeve]
    for y0, y1 in ((10.0, 12.0), (-12.0, -10.0)):
        c = L.extrude_profile("RearSight_Cheek", L.fillet(sector, radii, 6, closed=True), y0, y1,
                              "Steel_Blued", col)
        L.boolean(sleeve, c, "UNION")          # колодка со щеками — одна деталь
    L.boolean(sleeve, _pin_cutter(1.5))
    L.cleanup(sleeve, 0.02)
    L.bevel_mod(sleeve, 0.5, 2)
    pin = L.lathe("RearSight_Pin", L.fillet([(-12.7, 0), (-12.7, 2.1), (-12.05, 2.1), (-12.05, 1.45),
                                             (12.05, 1.45), (12.05, 2.1), (12.7, 2.1), (12.7, 0)],
                                            [0, 0.3, 0, 0, 0, 0, 0.3, 0], 3),
                  32, "Steel_Blued", col, axis="Y", origin=(px, 0.0, pz))
    parts.append(pin)

    # планка: шарнир на оси, тело 19,5 × 3,2 мм, снизу по бокам зубцы защёлки хомутика
    leaf_root = L.empty("RearSight_Leaf", (px, 0.0, pz), col, 0.01)
    top = lambda x: _leaf_top(x)  # noqa: E731
    body = L.extrude_profile("RearSight_Leaf_Mesh", [(84.5, top(84.5)), (px, top(px)), (px, top(px) - 3.2),
                                                      (84.5, top(84.5) - 3.2)], -9.75, 9.75, "Steel_Blued", col)
    knuckle = L.lathe("leaf_knuckle", L.fillet([(-9.7, 0), (-9.7, 3.4), (9.7, 3.4), (9.7, 0)], [0, 0.6, 0.6, 0], 3),
                      48, "Steel_Blued", col, axis="Y", origin=(px, 0.0, pz))
    L.boolean(body, knuckle, "UNION")
    # целик: брусок шире планки, сверху U-прорезь вдоль оси (ширина 2, глубина 1,5; верх 26,0 — по снимку)
    block = L.extrude_profile("leaf_notch_block", L.fillet([(85.5, top(85.5) - 3.0), (85.5, 24.5), (84.0, 26.0),
                                                            (78.0, 26.0), (77.2, 25.2), (77.2, 21.5),
                                                            (79.5, 19.2)], [0, 1.2, 0.6, 0.6, 0.6, 2.0, 1.0], 4,
                                                           closed=True), -10.5, 10.5, "Steel_Blued", col)
    L.boolean(body, block, "UNION")
    notch = L.extrude_profile("cut_notch", L.fillet([(-1.0, 31.0), (-1.0, 24.5), (1.0, 24.5), (1.0, 31.0)],
                                                    [0, 1.0, 1.0, 0], 8, closed=True), 70.0, 90.0,
                              None, None, None, plane="YZ")
    L.boolean(body, notch)
    teeth = []
    x = 100.0
    while x < 143.0:
        zb = top(x) - 3.2
        for y0, y1 in ((9.0, 10.5), (-10.5, -9.0)):
            teeth.append(_box("cut_tooth", (x, x + 1.4), (y0, y1), (zb - 0.5, zb + 2.0)))
        x += 3.5
    L.boolean(body, L.join(teeth, "cut_teeth"))
    L.boolean(body, _pin_cutter(1.5))
    # шкала сверху — последней операцией (если потом объединять, точная булева рвёт грань со шкалой):
    # продольная риска, поперечные риски
    # и цифры 1…20 (сотни метров), нечётные слева (+Y), чётные справа; «1» у переднего края хомутика,
    # цифры читаются из-за приклада (правка владельца)
    pitch = 2.45
    on_leaf = lambda u, v, h: (u, v, _leaf_top(u) + h)  # noqa: E731
    # два прохода: в одном резаке куски не должны пересекаться (иначе точная булева рвёт сетку)
    L.triangulate(body)
    L.boolean(body, L.stamp_cutter("cut_scale_axis", [L.box_polys(100.2, 150.8, -0.15, 0.15)], on_leaf, 0.15))
    scale = []
    for n in range(1, 21):
        xn = 100.8 + (n - 1) * pitch
        side = 1.0 if n % 2 else -1.0
        v0, v1 = sorted((side * 0.05, side * 8.6))   # заходит в продольную риску, уже вырезанную
        scale.append(L.box_polys(xn - 0.15, xn + 0.15, v0, v1))
        # цифра повёрнута на 90° по часовой (если смотреть сверху): стрелок читает её сзади, верх цифры к дулу
        tv, tf = L.text_polys(str(n), 2.4)
        scale.append(([(xn + pitch + v, side * 4.6 - u, w) for u, v, w in tv], tf))
    L.boolean(body, L.stamp_cutter("cut_scale", scale, on_leaf, 0.15))
    L.cleanup(body, 0.002)                 # мелкий порог: в контурах цифр шкалы точки бывают ближе 0,02 мм
    L.bevel_mod(body, 0.1, 2)              # мельче глубины клейм шкалы (0,15), иначе фаска их съедает
    leaf = body

    # хомутик: рамка вокруг планки, выступами снизу лежит на секторах; по бокам кнопки защёлки
    slider = L.extrude_profile("RearSight_Slider", L.fillet([(-14.5, 15.6), (14.5, 15.6), (14.5, 24.4),
                                                             (-14.5, 24.4)], [1.0, 1.0, 1.5, 1.5], 3, closed=True),
                               85.8, 99.8, "Steel_Blued", col, plane="YZ")
    L.boolean(slider, _box("cut_slider_window", (80.0, 105.0), (-9.9, 9.9), (16.1, 22.15)))
    oval = [(92.8 + 5.25 * math.cos(2 * math.pi * k / 40), 20.0 + 3.45 * math.sin(2 * math.pi * k / 40))
            for k in range(40)]
    for y0, y1 in ((14.0, 17.0), (-17.0, -14.0)):
        L.boolean(slider, L.extrude_profile("RearSight_Slider_Button", oval, y0, y1, "Steel_Blued", col), "UNION")
    L.bevel_mod(slider, 0.5, 2)
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
    for center, length_s, h, ang in SLING_SLOTS:
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
        xs, zs, rs = CROSS_SCREW
        s = L.lathe("Stock_CrossScrew", L.fillet([(0, 0), (0, rs), (1.2, rs), (2.0, 0)], [0, 0, 1.0, 0], 3),
                    40, "Steel_Blued", col, axis="X")
        s.matrix_world = Matrix.Translation(Vector((xs, side * cross_screw_base(), zs)) * L.MM) @ \
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
    rig_drivers()
    bpy.context.view_layer.update()
    lo, hi = L.world_bbox_mm([o for o in bpy.context.scene.objects if o.type == "MESH"])
    print("RIFLE bbox mm", tuple(round(v, 1) for v in lo), tuple(round(v, 1) for v in hi),
          "size", tuple(round(h - l, 1) for l, h in zip(lo, hi)))
    L.save_blend(OUT)


if __name__ == "__main__":
    build()
