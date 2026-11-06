# ПП по мотивам KRISS Vector: магазины .45 ACP — штатный Glock 21 на 13 (в игре mag_45_vector13) и на 30 с удлинителем
# типа KRISS MagEx2 (mag_45_vector30). v2 (владелец 2026-11-06: «магазины сделай как у настоящего вектора, а то это
# поделка какая-то»), по снимкам: Glock 21 Gen4/Gen5 сбоку (refs/web/glock21_*), комплект MagEx2 .45 и магазин на 30 в
# оружии (refs/web/kriss_usa, магазин снят — refs/05).
#   Glock 21: корпус — параллелограмм: ось наклонена (21°, part_receiver.mag_frame), а верх губок и донышко
#   горизонтальны, как у пистолета; вверху корпус сужается к губкам (подача в один ряд), губки — длинные сзади, спереди
#   ступенька под носик пули; окна защёлки на обоих бортах у передней грани и спереди; контрольные окна сзади в два ряда;
#   донышко выступает по контуру, спереди «носик».
#   На 30: тот же корпус Glock сверху, ниже шахты — рукав удлинителя (толще корпуса, верх по низу шахты горизонтален),
#   по передней грани поперечное рифление с заходом на борта, сзади окна 16–30, на бортах у дна — рамка с прорезью
#   защёлки, снизу донышко поперёк оси.
#   Патроны лежат горизонтально (параллельно стволу), стопка идёт вдоль наклонённой оси: верхний — посередине губок,
#   ниже — в два ряда шахматкой. Числа у окон и надписи — рисунком на текстурах, не геометрией.
import math
import bpy
import bmesh
from mathutils import Matrix, Vector
import lib
from lib import material, MM, MAG_W, MAG_D, MAG_ANGLE, lathe, boolean, fillet, finish_small, weighted, apply_all
from part_receiver import mag_frame, MAG_CENTER

A = math.radians(MAG_ANGLE)
CX, CZ = MAG_CENTER[0], MAG_CENTER[2]
D, W = MAG_D / 2, MAG_W / 2      # полуглубина и полуширина сечения поперёк оси
WALL = 1.7
Z_TOP = -11.5                   # верх губок сзади (под затвором; прежний задний угол верха — Z −11.4)
STEP = 5.0                      # спереди губки ниже на столько (под носик пули)
STEP_X = 3.0                    # где начинается ступенька, локальный x (от середины вперёд)
Z_BOT13 = -131.5                # низ корпуса Glock на 13 (донышко ниже)
PLATE_H = 5.5
Z_SLEEVE = -111.2               # верх рукава удлинителя спереди — сразу под низом шахты (Z −110 у передней кромки)
SLEEVE_SLOPE = 0.0925           # к заду верх рукава ниже — по низу корпуса за шахтой (Z −114.6 у X −86)
U_BOT30 = -139.6                # низ рукава вдоль оси (низ донышка — u −143.6, Z −244: снимок KRISS)
BASE_H = 4.0
SLV_T = 2.2                     # рукав толще корпуса на столько с каждой стороны
CASE_R = 6.0                    # .45 ACP: гильза Ø12.0, длина 22.8, патрон 32.4
CASE_LEN = 22.8
CART_LEN = 32.4
COL_OFF = 5.0                   # смещение рядов от середины (внутри 22.1 мм: ряды вплотную к стенкам)
PITCH_U = 7.15                  # шаг стопки вдоль оси между соседними патронами (разные ряды, касаются)
TOP_DROP = 5.6                  # середина верхнего патрона ниже верха губок: в горловине 10 мм он ниже губок
# верх стопки: верхний — посередине, два следующих — ближе к середине (корпус к губкам сужен), дальше шахматка
TOP_STEPS = (12.3, 10.1, 8.8)
TOP_Y = (0.0, 3.6, -3.8)


# ---------- оси магазина ----------

def frame_matrix():
    up, fwd = mag_frame()
    c = Vector(MAG_CENTER) * MM
    # локальные оси магазина: x — вперёд (fwd), y — Y, z — вдоль магазина вверх (up)
    return Matrix(((fwd.x, 0, up.x, c.x), (0, 1, 0, c.y), (fwd.z, 0, up.z, c.z), (0, 0, 0, 1)))


def to_frame(o):
    o.data.transform(frame_matrix())


def u_at(z, x):
    """Где горизонтальная плоскость Z = z (мм оружия) пересекает ось магазина при локальном x: u вдоль оси."""
    return (z - CZ + x * math.sin(A)) / math.cos(A)


def world(x, y, u):
    """Точка в осях магазина (мм) → мм оружия."""
    return Vector((CX + x * math.cos(A) + u * math.sin(A), y, CZ - x * math.sin(A) + u * math.cos(A)))


def section(d_half, w_half, rf, rr, seg=6):
    """Сечение поперёк оси (вид вдоль оси): x — вперёд, y — поперёк; передние углы rf, задние rr."""
    return fillet([(-d_half, -w_half), (d_half, -w_half), (d_half, w_half), (-d_half, w_half)], [rr, rf, rf, rr], seg)


# ---------- сетки ----------

def _solid(name, rings, C, mat=None):
    """Замкнутое тело из колец точек (мм) одинаковой длины: боковые грани и две крышки."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vr = [[bm.verts.new(Vector(p) * MM) for p in ring] for ring in rings]
    n = len(rings[0])
    for r0, r1 in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    caps = [bm.faces.new(list(reversed(vr[0]))), bm.faces.new(vr[-1])]
    # крышки — сразу на треугольники ушами: вогнутый многоугольник точное булево разбивает неверно
    bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    if mat:
        o.data.materials.append(material(mat))
    return o


def _multi(name, solids, C):
    """Один резак из нескольких непересекающихся тел (списки колец) — одно булево вместо десятков."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for rings in solids:
        vr = [[bm.verts.new(Vector(p) * MM) for p in ring] for ring in rings]
        n = len(rings[0])
        for r0, r1 in zip(vr, vr[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        caps = [bm.faces.new(list(reversed(vr[0]))), bm.faces.new(vr[-1])]
        bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    return o


def loft_local(name, sections, C, mat=None):
    """Тело вдоль оси магазина: [(u, сечение [(x, y)…])…] в осях магазина → в оси оружия."""
    o = _solid(name, [[(x, y, u) for x, y in sec] for u, sec in sections], C, mat)
    to_frame(o)
    return o


def prism_local_xu(pts, y0, y1):
    """Кольца призмы: контур в плоскости (x, u) магазина, выдавленный по y."""
    return [[(x, y0, u) for x, u in pts], [(x, y1, u) for x, u in pts]]


def prism_local_xy(pts, u0, u1):
    """Кольца призмы: контур поперёк оси (x, y), выдавленный вдоль оси u0…u1."""
    return [[(x, y, u0) for x, y in pts], [(x, y, u1) for x, y in pts]]


def gun_box(name, x0, x1, y0, y1, z0, z1, C):
    """Брусок в осях оружия (мм)."""
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return _solid(name, [[(x, y, z0) for x, y in pts], [(x, y, z1) for x, y in pts]], C)


def gun_prism_xz(name, pts, y0, y1, C):
    """Контур в плоскости XZ оружия (мм), выдавленный по Y."""
    return _solid(name, [[(x, y0, z) for x, z in pts], [(x, y1, z) for x, z in pts]], C)


def local_cut(o, name, solids, C, **kw):
    c = _multi(name, solids, C)
    to_frame(c)
    boolean(o, c, **kw)


# ---------- корпус Glock 21 ----------

def round_u(i, top_u):
    """Середина i-го патрона сверху вдоль оси: верхние — по шагам TOP_STEPS (переход к одному ряду), ниже — шахматкой
    с шагом PITCH_U."""
    u = top_u
    for k in range(min(i, len(TOP_STEPS))):
        u -= TOP_STEPS[k]
    return u - max(0, i - len(TOP_STEPS)) * PITCH_U


def round_y(i):
    return TOP_Y[i] if i < len(TOP_Y) else COL_OFF * (1 if i % 2 else -1)


def top_round_u():
    return u_at(Z_TOP - TOP_DROP, 0.5)


def glock_body(name, z_bottom, C, holes=(4, 13)):
    """Корпус Glock 21: сужение к губкам, горизонтальный верх со ступенькой спереди, горловина, окна защёлки,
    контрольные окна сзади (патроны holes[0]…holes[1])."""
    u_lo = u_at(z_bottom, -D) - 4.0
    u_hi = u_at(Z_TOP, D) + 4.0
    u_sh = u_at(Z_TOP, -D) - 16.0
    full = section(D, W, 7.0, 3.0)
    narrow = section(D, W - 1.0, 7.0, 3.0)
    o = loft_local(name, [(u_lo, full), (u_sh, full), (u_sh + 4.0, narrow), (u_hi, narrow)], C, "Polymer")
    # верх и низ — горизонтальные плоскости оружия
    boolean(o, gun_box("_top", -400, 400, -60, 60, Z_TOP, Z_TOP + 200, C))
    boolean(o, gun_box("_bot", -400, 400, -60, 60, z_bottom - 300, z_bottom, C))
    # ступенька губок спереди (носик пули): со скосом 3 мм
    xs = world(STEP_X, 0, u_at(Z_TOP, STEP_X)).x
    boolean(o, gun_prism_xz("_step", [(xs - 3.0, Z_TOP + 1.0), (xs, Z_TOP - STEP), (xs + 80, Z_TOP - STEP),
                                      (xs + 80, Z_TOP + 60), (xs - 3.0, Z_TOP + 60)], -60, 60, C))
    # полость: внутри стенок, сверху — под губками (толщина губки 1.8), снизу открыта (донышко отдельно)
    inner_full = section(D - WALL, W - WALL, 5.3, 1.3)
    inner_narrow = section(D - WALL, W - WALL - 1.0, 5.3, 1.3)
    cav = loft_local("_cav", [(u_lo - 6, inner_full), (u_sh, inner_full), (u_sh + 4.0, inner_narrow),
                              (u_hi + 6, inner_narrow)], C)
    boolean(cav, gun_box("_cavtop", -400, 400, -60, 60, Z_TOP - 1.8, Z_TOP + 200, C))
    boolean(o, cav)
    # горловина между губками: от задней стенки (донце гильзы под губками) — 10 мм, к переду шире (14 мм)
    xr = world(-D + WALL + 0.3, 0, u_at(Z_TOP, -D + WALL + 0.3)).x
    slot = fillet([(xr, -5.0), (xr + 60, -7.0), (xr + 60, 7.0), (xr, 5.0)], [1.5, 0, 0, 1.5], 4)
    boolean(o, _solid("_slot", [[(x, y, Z_TOP - 4.0) for x, y in slot], [(x, y, Z_TOP + 60) for x, y in slot]], C))
    # окна защёлки: на обоих бортах у передней грани (Gen4/5) и на передней грани (Gen3), ~36 мм ниже губок
    uc = u_at(Z_TOP - STEP, D - 5.0) - 34.0
    side = [(D - 8.5, uc - 3.6), (D - 2.6, uc - 3.6), (D - 2.6, uc + 3.6), (D - 8.5, uc + 3.6)]
    front = [(D - 2.6, -4.0), (D + 3.0, -4.0), (D + 3.0, 4.0), (D - 2.6, 4.0)]
    local_cut(o, "_catch", [prism_local_xu(side, -W - 3.0, W + 3.0), prism_local_xy(front, uc - 3.6, uc + 3.6)], C)
    # контрольные окна сзади (Ø3 мм, сквозные: в них видно латунь) — у патронов holes[0]…holes[1], два ряда
    # источник игровой сетки (SMG03_LP_SOURCE=1 build.py) — без контрольных окон: их даёт карта нормалей с high-poly
    tu = top_round_u()
    circle = [(1.5 * math.cos(2 * math.pi * k / 16), 1.5 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
    holes_s = [] if lib.MARKINGS_GEOMETRY else None
    for n in range(holes[0], holes[1] + 1):
        uu = round_u(n - 1, tu)
        yy = round_y(n - 1) * 0.85
        if holes_s is not None:
            holes_s.append([[(-D - 3.0, yy + cy, uu + cu) for cy, cu in circle], [(-D + WALL + 1.0, yy + cy, uu + cu)
                                                                                 for cy, cu in circle]])
    if holes_s:
        local_cut(o, "_witness", holes_s, C)
    finish_small(o, w=0.4, seg=3)
    return o


def floorplate13(name, C):
    """Донышко Glock 21: горизонтальная пластина по контуру низа корпуса, по бортам и сзади шире на 1.4 мм, спереди —
    «носик» на 3 мм."""
    sec = fillet([(-D - 1.4, -W - 1.4), (D + 3.0, -W - 1.4), (D + 3.0, W + 1.4), (-D - 1.4, W + 1.4)],
                 [4.5, 8.0, 8.0, 4.5], 6)
    # контур поперёк оси → горизонтальный срез корпуса на высоте низа (наклон оси вытягивает его по X)
    pts = []
    for x, y in sec:
        p = world(x, y, u_at(Z_BOT13, x))
        pts.append((p.x, p.y))
    o = _solid(name, [[(x, y, Z_BOT13 - PLATE_H) for x, y in pts], [(x, y, Z_BOT13) for x, y in pts]], C, "Polymer")
    finish_small(o, w=0.9, seg=3)
    return o


def follower(name, z_top, C):
    """Подаватель под нижним патроном: верх горизонтален (патроны лежат параллельно стволу, наискось к оси), высота 8."""
    sec = section(D - WALL - 0.3, W - WALL - 0.3, 4.5, 1.0)
    u0, u1 = u_at(z_top - 8.0, -D) - 1.0, u_at(z_top, D) + 1.0
    o = loft_local(name, [(u0, sec), (u1, sec)], C, "Polymer")
    boolean(o, gun_box("_ftop", -400, 400, -60, 60, z_top, z_top + 200, C))
    boolean(o, gun_box("_fbot", -400, 400, -60, 60, z_top - 300, z_top - 8.0, C))
    return o


# ---------- удлинитель на 30 ----------

def sleeve30(name, C):
    """Рукав удлинителя: толще корпуса на SLV_T, верх горизонтален под шахтой, внутри — по корпусу, дно 3 мм;
    рифление спереди, окна 16–30 сзади, рамки защёлки на бортах."""
    ds, ws = D + SLV_T, W + SLV_T
    outer = section(ds, ws, 8.5, 4.5)
    u_hi = u_at(Z_SLEEVE, ds) + 4.0
    o = loft_local(name, [(U_BOT30, outer), (u_hi, outer)], C, "Polymer")
    # верх рукава — по линии низа корпуса: спереди Z_SLEEVE у передней кромки шахты (X −33.5), к заду ниже
    zf = lambda xg: Z_SLEEVE + (xg + 33.5) * SLEEVE_SLOPE
    boolean(o, gun_prism_xz("_stop", [(-400, zf(-400)), (400, zf(400)), (400, 300), (-400, 300)], -60, 60, C))
    cav = loft_local("_scav", [(U_BOT30 + 3.0, section(D, W, 7.0, 3.0)), (u_hi + 6.0, section(D, W, 7.0, 3.0))], C)
    boolean(o, cav)
    # крупные кромки (верхний срез, устье) скругляются до мелочи: фаска по сотне канавок рифления не ложилась
    finish_small(o, w=0.6, seg=3)
    o["_fin"] = 0
    # рифление: поперёк оси, шаг 3.2, ширина 1.6, глубина 1 мм ровно по контуру передней грани вместе со скруглёнными
    # углами и с заходом на борта (на снимке KRISS зубцы видны и спереди, и на профиле); резак — «подкова» между
    # контуром рукава, сдвинутым внутрь на 1 мм, и контуром снаружи (прямой заход на борта резал скругление ломтиками)
    u_front = u_at(Z_SLEEVE, ds) - 5.0
    # канавки — со стенками под 45° (дно 0.4 мм, по поверхности 2 мм, глубина 0.8): отвесные стенки карта нормалей
    # не передаёт, и рифление на игровой сетке не читалось; путь — контур рукава по передней грани и скруглениям углов,
    # концы — в 0.6 мм за началом дуг (там линии перехода рукава и резака совпадали — точное булево оставляло дыры)
    x0 = ds - 8.5 + 0.6
    path = [q for q in section(ds, ws, 8.5, 4.5, seg=10) if q[0] > x0]
    dense = []
    for a, b in zip(path, path[1:]):
        n_seg = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 1.5))
        for k in range(n_seg):
            t = k / n_seg
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    dense.append(path[-1])
    cx_arc = ds - 8.5

    def outward(q):
        # наружу: на дугах — от центра дуги, на передней грани — вперёд
        if abs(q[1]) <= ws - 8.5 + 1e-6:
            return (1.0, 0.0)
        cy = math.copysign(ws - 8.5, q[1])
        dx, dy = q[0] - cx_arc, q[1] - cy
        r = math.hypot(dx, dy) or 1.0
        return (dx / r, dy / r)
    profile = ((-0.8, -0.2), (-0.8, 0.2), (0.4, 1.4), (0.4, -1.4))   # (глубина от поверхности, сдвиг вдоль оси)

    def groove_rings(uc):
        rings = []
        for q in dense:
            nx, ny = outward(q)
            rings.append([(q[0] + nx * d, q[1] + ny * d, uc + du) for d, du in profile])
        return rings
    length = u_front - U_BOT30
    gs = []
    k = 0
    while True:
        uc = u_front - k * 3.2
        if uc < u_front - 0.62 * length:
            break
        gs.append(groove_rings(uc))
        k += 1
    # с учётом самопересечений: без него на каждой канавке оставались открытые рёбра у края на дуге; у источника
    # игровой сетки рифления и окон нет — они в карте нормалей (канавки в упрощённой сетке рвали развёртку на сотни
    # островов, и запекание в них било изнанку)
    if lib.MARKINGS_GEOMETRY:
        local_cut(o, "_grooves", gs, C, self_x=True)
    # окна 16–30 сзади, сквозь стенку рукава
    tu = top_round_u()
    circle = [(1.6 * math.cos(2 * math.pi * k / 16), 1.6 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
    hs = []
    for n in range(16, 31):
        uu = round_u(n - 1, tu)
        if uu < U_BOT30 + 6.0:
            continue
        yy = round_y(n - 1) * 0.9
        hs.append([[(-ds - 3.0, yy + cy, uu + cu) for cy, cu in circle], [(-ds + SLV_T + 0.6, yy + cy, uu + cu)
                                                                          for cy, cu in circle]])
    if lib.MARKINGS_GEOMETRY:
        local_cut(o, "_witness", hs, C)
    # рамки защёлки у дна на обоих бортах: выступ 0.9 мм, в нём прорезь глубиной 1.5 (виден язычок трубки)
    ub = U_BOT30 + 13.0
    frame = fillet([(-14.0, ub - 5.0), (10.0, ub - 5.0), (10.0, ub + 5.0), (-14.0, ub + 5.0)], 3.0, 6)
    boss = _multi("_boss", [prism_local_xu(frame, ws - 0.3, ws + 0.9), prism_local_xu(frame, -ws - 0.9, -ws + 0.3)], C)
    to_frame(boss)
    boolean(o, boss, op="UNION")
    slot = fillet([(-9.5, ub - 1.8), (5.5, ub - 1.8), (5.5, ub + 1.8), (-9.5, ub + 1.8)], 1.7, 6)
    local_cut(o, "_lock", [prism_local_xu(slot, ws - 1.5, ws + 3.0), prism_local_xu(slot, -ws - 3.0, -ws + 1.5)], C)
    # мелочь — узкой фаской только по острым кромкам вырезов (крупные уже скруглены: угол между гранями там мал)
    finish_small(o, w=0.15, seg=2, angle=60.0)
    # если мелкая фаска не легла (рифление узкое), плоскости всё равно держит Weighted Normal — без него по бортам
    # шли косые пятна затенения от треугольников после булевых
    weighted(o)
    apply_all(o)
    return o


def base30(name, C):
    """Донышко трубки удлинителя — поперёк оси, по контуру рукава чуть шире."""
    sec = section(D + SLV_T + 0.4, W + SLV_T + 0.4, 8.8, 4.8)
    o = loft_local(name, [(U_BOT30 - BASE_H, sec), (U_BOT30, sec)], C, "Polymer")
    finish_small(o, w=0.8, seg=3)
    return o


# ---------- патроны ----------

def cartridge(name, C):
    """Патрон .45 ACP вдоль +x (пуля вперёд): гильза с проточкой и закраиной, оболочечная пуля с круглым носом."""
    prof = [(0.0, 0.0), (0.0, 6.0), (1.2, 6.0), (1.4, 5.4), (2.2, 5.4), (2.4, 5.95), (CASE_LEN, 6.0), (CASE_LEN, 5.73)]
    case = lathe(name + "_case", [(x - CART_LEN / 2, r) for x, r in prof] + [(CASE_LEN - CART_LEN / 2, 0.0)], C, "Brass",
                 seg=48, cz=0.0)
    nose = []
    for k in range(13):
        a = math.pi / 2 * k / 12
        nose.append((CASE_LEN - 2.0 + (CART_LEN - CASE_LEN + 2.0) * math.sin(a) - CART_LEN / 2, 5.73 * math.cos(a) + 0.0))
    bullet = lathe(name + "_bullet", [(CASE_LEN - 2.0 - CART_LEN / 2, 0.0)] + nose + [(CART_LEN / 2, 0.0)], C,
                   "Bullet_jacket", seg=48, cz=0.0)
    return case, bullet


def rounds(prefix, count, C):
    """count патронов горизонтально (пуля вперёд, параллельно стволу): верхний — посередине губок, ниже — шахматкой."""
    objs = []
    base_case, base_bullet = cartridge(prefix + "_proto", C)
    tu = top_round_u()
    for i in range(count):
        p = world(0.5, round_y(i), round_u(i, tu)) * MM
        for src, nm in ((base_case, "case"), (base_bullet, "bullet")):
            o = bpy.data.objects.new(f"{prefix}_{i:02d}_{nm}", src.data)
            C.objects.link(o)
            o.matrix_world = Matrix.Translation(p)
            objs.append(o)
    for o in (base_case, base_bullet):
        bpy.data.objects.remove(o, do_unlink=True)
    # низ нижнего патрона (Z): под ним подаватель
    return objs, world(0.5, 0, round_u(count - 1, tu)).z - CASE_R - 0.4


# ---------- сборка ----------

def magazine13(C):
    body = glock_body("Magazine13_body", Z_BOT13, C)
    plate = floorplate13("Magazine13_floorplate", C)
    rs, z_last = rounds("Magazine13_round", 13, C)
    fl = follower("Magazine13_follower", z_last, C)
    for x in (plate, fl):
        x["owner"] = body.name
    body["mag_capacity"] = 13
    return body, plate, fl, rs


def magazine30(C):
    # корпус Glock сверху; ниже шахты его закрывает рукав — внутри рукава корпус кончается (не виден)
    body = glock_body("Magazine30_body", Z_SLEEVE - 30.0, C)
    sl = sleeve30("Magazine30_sleeve", C)
    base = base30("Magazine30_floorplate", C)
    rs, z_last = rounds("Magazine30_round", 30, C)
    fl = follower("Magazine30_follower", z_last, C)
    for x in (sl, base, fl):
        x["owner"] = body.name
    body["mag_capacity"] = 30
    return body, base, fl, rs


def build(ctx):
    C = ctx["coll"]["Magazine"]
    m13 = magazine13(C)
    C30 = bpy.data.collections.get("Magazine_30") or bpy.data.collections.new("Magazine_30")
    if C30.name not in [c.name for c in ctx["coll"]["Magazine"].children]:
        ctx["coll"]["Magazine"].children.link(C30)
    m30 = magazine30(C30)
    return {"mag13": m13, "mag30": m30, "coll30": C30}
