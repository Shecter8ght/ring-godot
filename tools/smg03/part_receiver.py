# ПП по мотивам KRISS Vector Gen II: коробка (верх с планками, передний блок со стволом, окно выброса справа, паз
# рукоятки заряжания слева), корпус шахты магазина (наклон 21°, рёбра переда, выемки боков) и спусковая коробка
# (рукоять, скоба, нижняя тяга). Контуры деталей сбоку — перенос со снимков KRISS (data/profiles.json), ширины —
# asset-state.md. Все вырезы делаются до общего скругления (finish в build.py), чтобы кромки вырезов тоже были круглыми.
import math
import bpy
from mathutils import Matrix, Vector
from lib import (PROFILES, rounded_prism, finish, finish_small, bevel_edges, MM, HALF_W, RAIL_TOP, RAIL_BASE, RAIL_HALF_W, SEAM_Z, SEAM_REAR_Z, FRONT_FACE_X, FRONT_LOW_Z, REAR_X,
                 FRONT_BLOCK_REAR_X, PANEL_LINE, MAG_ANGLE, MAG_W, MAG_D, BARREL_R, profile, fillet, pchip, smooth_poly, prism_xz, prism_yz,
                 prism_xy, box, cyl, lathe, boolean, boolean_safe, apply_transform, v)

RAIL_SLOT_W = 5.23
RAIL_SLOT_DEPTH = 2.9
TOP_RAIL_X = (-262.0, 104.0)
LOW_RAIL_X = (24.0, 102.5)
LOW_RAIL_TOP = -29.5             # низ зубьев нижней планки (снимок)
CH_SLOT_Z = (17.6, 23.4)         # паз рукоятки заряжания слева (снимок)
CH_SLOT_X = (-62.0, 74.0)        # паз закрыт с обоих концов (h1ggs: X −56…72; задний конец — под ход тяги затвора)
CH_SLOT_DEPTH = 7.5              # дно паза — в полости затвора: ползун рукоятки берёт тягу затвора
PORT_X = (-43.0, 4.0)            # окно выброса справа (снимок B)
PORT_Z = (13.0, 49.0)            # h1ggs: верх окна — почти у планки; под окном — полочка до шва (Z 15)            # низ окна — по шву (снимок B: 13; дно окна — верх корпуса шахты), сверху полка 2.2 мм
CAVITY = (-111.0, 40.0, -14.5, 14.5, -12.5, 33.0)  # полость затвора (x0, x1, y0, y1, z0, z1): над затвором 3 мм
PORT_DEPTH_Y = -1.0               # карман окна выброса — от правого борта до середины коробки
PORT_CHAMFER = 9.0                # скос задней стенки окна (h1ggs: гильза уходит вперёд-вправо)  # полость затвора внутри коробки (x0, x1, y0, y1, z0, z1)
TRIG_HALF_W = 20.0               # спусковая коробка: передняя тяга и нижняя тяга
GRIP_HALF_W = 15.5               # рукоять (оценка: обычная пистолетная ~31 мм)
GUARD_HALF_W = 6.5               # перекладина скобы
BAR_HALF_W = 14.0                # нижняя тяга петли — чуть уже рукояти (овал 15.2); толщина местами 6.7 мм — скругление R 2


def rail_profile(top, base, half=RAIL_HALF_W, sgn=1.0):
    """Сечение планки 1913 (y, z); sgn = −1 — планка смотрит вниз (нижняя)."""
    top_half = half - 2.8
    neck = half - 2.6
    zv = top - 2.8 * sgn
    zn = zv - (half - neck) * sgn
    pts = [(-neck, base), (-neck, zn), (-half, zv), (-top_half, top), (top_half, top), (half, zv), (neck, zn), (neck, base)]
    return pts if sgn > 0 else list(reversed(pts))


def rail_slots(target, x0, x1, top, sgn, first, coll):
    xs = []
    x = first
    while x - RAIL_SLOT_W / 2 > x0 + 2.0:
        xs.append(x)
        x -= 10.0
    for i, xc in enumerate(xs):
        # паз со скруглённым дном (полуцилиндр) — без острых углов на дне
        z_bot = top - RAIL_SLOT_DEPTH * sgn
        c = prism_xz(f"_slot{i}", fillet([(xc - RAIL_SLOT_W / 2, z_bot), (xc + RAIL_SLOT_W / 2, z_bot),
                                          (xc + RAIL_SLOT_W / 2, top + 6 * sgn), (xc - RAIL_SLOT_W / 2, top + 6 * sgn)],
                                         [0.9, 0.9, 0, 0], 4), -15, 15, coll)
        boolean(target, c)
    return xs


def rounded_rect_xz(x0, x1, z0, z1, r, seg=6):
    return fillet([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], r, seg)


def pill_xz(a, b, r, seg=12):
    """Контур «пилюли» в XZ между центрами a и b радиуса r."""
    ax, az = a; bx, bz = b
    ang = math.atan2(bz - az, bx - ax)
    pts = []
    for k in range(seg + 1):
        t = ang + math.pi / 2 + math.pi * k / seg
        pts.append((ax + r * math.cos(t), az + r * math.sin(t)))
    for k in range(seg + 1):
        t = ang - math.pi / 2 + math.pi * k / seg
        pts.append((bx + r * math.cos(t), bz + r * math.sin(t)))
    return pts


def side_recess(target, pts, depth, coll, both=True, half=HALF_W, name="_rec"):
    """Выемка глубиной depth в боковинах (обе стороны или только +Y)."""
    for s in ((1, -1) if both else (1,)):
        y0, y1 = (half - depth, half + 5) if s > 0 else (-half - 5, -half + depth)
        c = prism_xz(name, pts, y0, y1, coll)
        boolean(target, c)


def mag_frame():
    """Оси магазина: u — вдоль магазина вверх (наклон низом назад), w — вперёд поперёк, начало — середина горловины."""
    a = math.radians(MAG_ANGLE)
    up = Vector((math.sin(a), 0.0, math.cos(a)))
    fwd = Vector((math.cos(a), 0.0, -math.sin(a)))
    return up, fwd


def mag_box(name, center, w_half, d_half, u0, u1, coll):
    """Прямоугольный брусок в осях магазина: по ширине Y ±w_half, по глубине ±d_half, вдоль оси u0..u1 от center (мм)."""
    up, fwd = mag_frame()
    o = box(name, -d_half, d_half, -w_half, w_half, u0, u1, coll)
    m = Matrix(((fwd.x, 0, up.x, 0), (0, 1, 0, 0), (fwd.z, 0, up.z, 0), (0, 0, 0, 1)))
    o.data.transform(m)
    o.data.transform(Matrix.Translation(v(*center)))
    return o


MAG_CENTER = (-55.5, 0.0, -110.0)   # середина горловины (снимок: перёд магазина X −36, зад X −83 на Z −120)


def side_line(target, path, width, depth, side, C):
    """Тонкая канавка по ломаной path (XZ) на борту side (±1): полоса шириной width, глубиной depth, без перекрытий."""
    left, right = [], []
    n = len(path)
    for i, (x, z) in enumerate(path):
        a = path[max(i - 1, 0)]; b = path[min(i + 1, n - 1)]
        tx, tz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, tz)
        nx, nz = -tz / L, tx / L
        left.append((x + nx * width / 2, z + nz * width / 2))
        right.append((x - nx * width / 2, z - nz * width / 2))
    poly = left + list(reversed(right))
    y0, y1 = (HALF_W - depth, HALF_W + 3) if side > 0 else (-HALF_W - 3, -HALF_W + depth)
    c = prism_xz("_line", poly, y0, y1, C)
    boolean(target, c)


def clean_front(pts):
    """Передний торец по снимку слегка «пляшет» (рукоятка заряжания выступает) — ровная вертикаль X = FRONT_FACE_X со
    скруглёнными в плоскости углами (R 2.6, как остальной контур)."""
    cut = FRONT_FACE_X - 6.0
    res = []
    for p in pts:
        if p[0] >= cut:
            if not res or res[-1] != "F":
                res.append("F")
        else:
            res.append(p)
    final = []
    for k, p in enumerate(res):
        if p == "F":
            prev = res[k - 1] if k > 0 else res[-1]
            nxt = res[(k + 1) % len(res)]
            zl, zh = FRONT_LOW_Z, RAIL_BASE
            corner = [(cut, zl), (FRONT_FACE_X, zl), (FRONT_FACE_X, zh), (cut, zh)]
            if prev[1] > nxt[1]:
                corner = list(reversed(corner))
            rounded = fillet(corner, [0.0, 2.6, 2.6, 0.0], 6)
            final += rounded
        else:
            final.append(p)
    return final


def upper_features(o, C):
    # планка сверху — одно тело с коробкой (у Vector она литая с верхом)
    r = prism_yz("_rail", rail_profile(RAIL_TOP, RAIL_BASE - 0.5), TOP_RAIL_X[0], TOP_RAIL_X[1], C)
    boolean(o, r, op="UNION")
    rail_slots(o, TOP_RAIL_X[0], TOP_RAIL_X[1], RAIL_TOP, 1.0, TOP_RAIL_X[1] - 6.4, C)
    # нижняя планка под передним блоком
    r = prism_yz("_lrail", rail_profile(LOW_RAIL_TOP, FRONT_LOW_Z + 0.5, sgn=-1.0), LOW_RAIL_X[0], LOW_RAIL_X[1], C)
    boolean(o, r, op="UNION")
    rail_slots(o, LOW_RAIL_X[0], LOW_RAIL_X[1], LOW_RAIL_TOP, -1.0, LOW_RAIL_X[1] - 6.0, C)
    # паз рукоятки заряжания слева (+Y): открыт в передний торец, сзади — полукруг
    z0, z1 = CH_SLOT_Z
    zr = (z1 - z0) / 2
    pts = pill_xz((CH_SLOT_X[0] + zr, (z0 + z1) / 2), (CH_SLOT_X[1] - zr, (z0 + z1) / 2), zr)
    c = prism_xz("_chslot", pts, HALF_W - CH_SLOT_DEPTH, HALF_W + 5, C)
    boolean(o, c)
    # полость затвора и окно выброса справа (−Y)
    x0, x1, y0, y1, zc0, zc1 = CAVITY
    c = prism_xz("_cav", rounded_rect_xz(x0, x1, zc0, zc1, 3.0), y0, y1, C)
    boolean(o, c)
    c = prism_xz("_port", rounded_rect_xz(PORT_X[0], PORT_X[1], PORT_Z[0], PORT_Z[1], 2.5), -HALF_W - 5, PORT_DEPTH_Y, C)
    boolean(o, c)
    # задняя стенка окна — скосом наружу (h1ggs), углы скоса скруглены
    ch = PORT_CHAMFER
    c = prism_xy("_portch", fillet([(PORT_X[0] + 0.6, -HALF_W - 1.0), (PORT_X[0] + 0.6, -HALF_W + ch), (PORT_X[0] - ch, -HALF_W - 1.0)],
                                   [0.0, 1.5, 1.5], 4), PORT_Z[0] + 1.2, PORT_Z[1] - 1.2, C)
    boolean(o, c)
    # справа на переднем блоке — линия уступа (снимки KRISS B, владельца 04): от торца на Z 22 назад до X 58, дугой вниз
    # к Z 13 и дальше назад до шва; канавка 1.3 × 0.5 (уже — фаска кромок 0.45 перехлёстывается)
    side_line(o, [(FRONT_FACE_X + 3.0, 22.0), (60.0, 22.0)] +
              [(60.0 - 9.0 * math.sin(math.pi / 2 * k / 8), 13.0 + 9.0 * math.cos(math.pi / 2 * k / 8)) for k in range(1, 9)] +
              [(FRONT_BLOCK_REAR_X - 3.0, 13.0)], 1.3, 0.5, -1, C)
    # прорезь под перо спуска в низу коробки над проёмом скобы (ход назад на 11°)
    c = prism_xz("_trigslot", rounded_rect_xz(-173.0, -136.0, 12.0, 30.0, 2.0), -3.9, 3.9, C)
    boolean(o, c)
    # канал ствола в переднем блоке
    c = cyl("_bore", 30.0, FRONT_FACE_X + 5, BARREL_R + 0.25, C, seg=64)
    boolean(o, c)


def magwell_features(o, C):
    pts, _h = profile("magwell")
    # шахта магазина в осях магазина: зазор 0.55 мм на сторону, снизу — раструб
    c = mag_box("_well", MAG_CENTER, MAG_W / 2 + 0.55, MAG_D / 2 + 0.55, -20.0, 112.0, C)
    boolean(o, c)
    c = mag_box("_flare", MAG_CENTER, MAG_W / 2 + 2.2, MAG_D / 2 + 2.2, -20.0, 2.0, C)
    boolean(o, c)
    # полость затвора продолжается вниз (затвор и подаватель — над шахтой)
    x0, x1, y0, y1, zc0, zc1 = CAVITY
    c = prism_xz("_cav2", rounded_rect_xz(x0, x1, zc0, SEAM_Z + 3, 3.0), y0, y1, C)
    boolean(o, c)
    # рёбра переда шахты (снимки A, B, владельца 04): шаг 3.6, канавка 1.6 × 1.0 — от переднего блока до низа
    # канавки заходят на скругление кромок R 9 и кончаются там, где оно уходит глубже канавки (снимок 04: рёбра
    # заворачивают на бока)
    ribs(o, pts, edge_run(pts, (21.0, -22.0), (-27.0, -104.0), (-2.0, -62.0)), 3.6, 1.6, 1.0, HALF_W - 6.6, C, "_mwribs")
    # гнёзда органов управления: кнопка задержки справа (X −38, Z −10) и лопатки защёлки магазина у переднего ребра
    c = prism_xz("_brp", rounded_rect_xz(-43.2, -32.8, -14.8, -5.2, 2.0), -HALF_W - 3, -HALF_W + 3.8, C)
    boolean(o, c)
    up_, fw_ = mag_frame()
    from part_controls import MAG_REL
    a_ = (MAG_REL[0] + up_.x * 6.0, MAG_REL[1] + up_.z * 6.0)
    b_ = (MAG_REL[0] - up_.x * 6.0, MAG_REL[1] - up_.z * 6.0)
    side_recess(o, pill_xz(a_, b_, 5.7), 2.4, C, both=False)
    c = prism_xz("_mrr", [(a_[0] + fw_.x * 3.8, a_[1] + fw_.z * 3.8), (b_[0] + fw_.x * 3.8, b_[1] + fw_.z * 3.8),
                          (b_[0] - fw_.x * 3.8, b_[1] - fw_.z * 3.8), (a_[0] - fw_.x * 3.8, a_[1] - fw_.z * 3.8)],
                 -HALF_W - 3, -HALF_W + 3.4, C)
    boolean(o, c)
    # длинные выемки-«пилюли» на боках (снимки A и B), глубина 1.2
    side_recess(o, pill_xz((-28.2, -24.0), (-51.4, -82.7), 8.0), 1.2, C)
    # тёмное окно позади эмблемы — глубокая выемка 3 мм
    side_recess(o, pill_xz((-113.5, -54.0), (-123.0, -90.5), 5.6), 3.0, C)


def _point_in(pts, x, z):
    inside = False
    n = len(pts)
    for i in range(n):
        x1, z1 = pts[i]; x2, z2 = pts[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            inside = not inside
    return inside


def edge_run(pts, a, b, hint):
    """Участок контура между ближайшими к a и b вершинами — тот из двух путей, что ближе к точке hint."""
    n = len(pts)
    ia = min(range(n), key=lambda i: (pts[i][0] - a[0]) ** 2 + (pts[i][1] - a[1]) ** 2)
    ib = min(range(n), key=lambda i: (pts[i][0] - b[0]) ** 2 + (pts[i][1] - b[1]) ** 2)
    p1 = [pts[(ia + k) % n] for k in range((ib - ia) % n + 1)]
    p2 = [pts[(ia - k) % n] for k in range((ia - ib) % n + 1)]

    def dist(p):
        return min((q[0] - hint[0]) ** 2 + (q[1] - hint[1]) ** 2 for q in p)
    return p1 if dist(p1) < dist(p2) else p2


def resample(run, step):
    """Точки через step мм по длине ломаной: (точка, касательная)."""
    seg = []
    total = 0.0
    for p, q in zip(run, run[1:]):
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        seg.append((p, q, L, total))
        total += L
    out = []
    s = step / 2
    while s < total - step / 2 + 1e-6:
        for p, q, L, t0 in seg:
            if t0 <= s <= t0 + L and L > 1e-9:
                t = (s - t0) / L
                out.append(((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t), ((q[0] - p[0]) / L, (q[1] - p[1]) / L)))
                break
        s += step
    return out, total


def ribs(target, prof, run, pitch, width, depth, half_y, C, name="_ribs", solid=True):
    """Поперечные рёбра по краю детали: канавки шириной width и глубиной depth через pitch вдоль участка run контура prof.
    Все резцы — одним телом, одно булево вычитание."""
    stations, _L = resample(run, pitch)
    import bmesh
    for gi, ((px, pz), (tx, tz)) in enumerate(stations):
        nx, nz = -tz, tx
        # нормаль — наружу из материала (prof — контур детали; solid=False — контур отверстия, материал снаружи)
        if _point_in(prof, px + nx * 0.6, pz + nz * 0.6) == solid:
            nx, nz = -nx, -nz
        # канавка со скруглённым дном: сечение — полукруг радиуса width/2, утоплен на depth
        r = width / 2
        ring = []
        for k in range(9):
            a = math.pi * k / 8
            u = math.cos(a) * r                      # вдоль края
            w = -depth + r - math.sin(a) * r       # по нормали (внутрь — отрицательно)
            ring.append((px + tx * u + nx * w, pz + tz * u + nz * w))
        # дуга идёт от u = +r к u = −r, дальше наружу и обратно — контур без самопересечений
        ring += [(px - tx * r + nx * 3.0, pz - tz * r + nz * 3.0), (px + tx * r + nx * 3.0, pz + tz * r + nz * 3.0)]
        c = prism_xz(f"{name}{gi}", ring, -half_y, half_y, C)
        boolean(target, c)
    print("RIBS", name, len(stations), "по", round(_L, 1), "мм")
    return len(stations)


def narrow(target, zone_xz, section_yz, x0, x1, C, name="_narrow"):
    """Срезать бока детали в области zone_xz (вид сбоку) по сечению section_yz (что убрать, вид спереди) —
    пересечение двух призм; сечение задаёт и наклонные переходы ширины (без ступенек)."""
    a = prism_xz(name + "_z", zone_xz, -60, 60, C)
    for s in (1, -1):
        b = prism_yz(name + "_s", [(y * s, z) for y, z in section_yz][::s], x0, x1, C)
        boolean(b, a, op="INTERSECT", remove=False)
        boolean(target, b)
    bpy.data.objects.remove(a, do_unlink=True)


def _bodies(name, prof_name, half, r, C, mat=None, tri_caps=False):
    """Все куски профиля prof_name — скруглённые призмы, объединённые в одно тело."""
    items = PROFILES["parts"][prof_name]
    objs = []
    for k, it in enumerate(items):
        objs.append(rounded_prism(name if k == 0 else f"_{name}{k}", [tuple(p) for p in it["outer"]], -half, half, r, C, mat,
                                  tri_caps=tri_caps))
    o = objs[0]
    for b in objs[1:]:
        boolean(o, b, op="UNION")
    return o



def _span_x(poly, z):
    xs = []
    n = len(poly)
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        if (z1 - z) * (z2 - z) <= 0 and z1 != z2:
            xs.append(x1 + (z - z1) * (x2 - x1) / (z2 - z1))
    return (min(xs), max(xs)) if len(xs) >= 2 else None


GRIP_B = 15.2          # полуширина рукояти (30.4 мм)
GRIP_TOP_Z = 15.1      # низ коробки над рукоятью
GRIP_TOP_B = HALF_W - 0.35   # у коробки — почти её ширина: остаётся тонкая линия стыка, без «воротника»
GRIP_N = (2.4, 6.0)    # показатель овала сечения: в рукояти — и у коробки (сечение к верху прямоугольнее)
GRIP_GROOVES = (-73.0, -19.0, 3.4, 1.5, 0.9)   # рифление переда: Z от, до, шаг, ширина, глубина
GRIP_PANEL_D = 0.7     # поле под ладонь утоплено (шагрень — на этапе текстур)
GRIP_SEG = 128


def _grip_contour():
    return [tuple(p) for p in max(PROFILES["parts"]["th_grip"], key=lambda it: len(it["outer"]))["outer"]]


def _arc_out(z, z0, z1):
    """Вогнутая четверть окружности R = z1 − z0: 0 ниже z0, R на z1 и выше."""
    if z <= z0:
        return 0.0
    r = z1 - z0
    d = min(z, z1) - z0
    return r - math.sqrt(max(0.0, r * r - d * d))


def _ss(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def grip_edges():
    """Передняя и задняя кромки рукояти по высоте — гладко (кубически по контуру со снимка) и с расширением вверху:
    вперёд дугой R 5 в верх окна спуска, назад дугой R 7 в «бобровый хвост»."""
    gp = _grip_contour()
    keys = [-89.6, -88.6, -87.0, -85.0, -82.0, -78.0, -74.0, -68.0, -60.0, -50.0, -40.0, -30.0, -20.0, -12.0, -6.0,
            0.0, 4.0, 7.0, 9.0, 11.0]
    sp = [_span_x(gp, z) for z in keys]
    f0 = pchip(list(zip(keys, [s[0] for s in sp])))
    f1 = pchip(list(zip(keys, [s[1] for s in sp])))

    def x0(z, flare=True):
        return f0(min(z, 11.0)) - (_arc_out(z, 5.0, 12.0) if flare else 0.0)

    def x1(z, flare=True):
        return f1(min(z, 11.0)) + (_arc_out(z, 10.0, 15.0) if flare else 0.0)
    return x0, x1


def grip_section(z, x0, x1):
    """(центр X, полудлина a, полуширина b, показатель n) сечения на высоте z."""
    kb = pchip([(-89.6, 0.42), (-88.6, 0.62), (-87.0, 0.76), (-85.0, 0.86), (-82.0, 0.94), (-78.0, 0.99),
                (-74.0, 1.0), (-70.0, 1.0)])(z) if z < -70.0 else 1.0
    rb = GRIP_TOP_B - GRIP_B
    b = GRIP_B * kb + _arc_out(z, GRIP_TOP_Z - rb, GRIP_TOP_Z)
    n = GRIP_N[0] + (GRIP_N[1] - GRIP_N[0]) * _ss((z - 4.0) / 11.0)
    a0, a1 = x0(z), x1(z)
    return (a0 + a1) / 2, (a1 - a0) / 2 - 0.2, b, n


def _panel_poly(x0, x1):
    """Поле под ладонь (XZ): от переднего края — 30 % длины сечения (там рифление), от заднего — 8 %, Z −2…−70."""
    zs = [-2.0, -12.0, -24.0, -36.0, -48.0, -60.0, -70.0]
    front = [(x1(z, False) - 0.30 * (x1(z, False) - x0(z, False)), z) for z in zs]
    back = [(x0(z, False) + 0.08 * (x1(z, False) - x0(z, False)), z) for z in zs]
    poly = front + list(reversed(back))
    radii = [5.0] + [0.0] * (len(zs) - 2) + [5.0, 5.0] + [0.0] * (len(zs) - 2) + [5.0]
    return fillet(poly, radii, 6)


def _sd_poly(poly, x, z):
    """Расстояние до контура: + внутри, − снаружи."""
    best = 1e9
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]; bx, bz = poly[(i + 1) % n]
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L2))
        px, pz = ax + dx * t - x, az + dz * t - z
        best = min(best, px * px + pz * pz)
    d = math.sqrt(best)
    return d if _point_in(poly, x, z) else -d


def grip_loft(C, name="_griploft"):
    """Рукоять одним телом без булевых (владелец 04.11: «кусок кирпича», «как отдельный брусок»; сверка v04: рваные
    концы рифления и шов на спинке от резцов): плотные кольца-овалы (суперэллипс), кромки — по контуру со снимка;
    рифление переда и утопленное поле — смещением точек по нормали овала. Спинка гладкая (снимки KRISS, h1ggs)."""
    import bmesh
    x0, x1 = grip_edges()
    zs = [-89.6, -89.2, -88.8]
    z = -88.4
    while z < 18.0 - 1e-6:
        zs.append(round(z, 3))
        dense = (-76.5 <= z < -16.0) or (-4.5 <= z < 0.5) or (-72.5 <= z < -67.5)
        z += 0.34 if dense else 1.0
    zs.append(18.0)
    g0, g1, pitch, gw, gd = GRIP_GROOVES
    panel = _panel_poly(x0, x1)
    pz0, pz1 = min(p[1] for p in panel), max(p[1] for p in panel)
    seg = GRIP_SEG
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for z in zs:
        cx, a, b, n = grip_section(z, x0, x1)
        ring = []
        for k in range(seg):
            t = 2 * math.pi * k / seg
            c, s_ = math.cos(t), math.sin(t)
            u = a * math.copysign(abs(c) ** (2 / n), c)
            y = b * math.copysign(abs(s_) ** (2 / n), s_)
            # нормаль овала в плоскости сечения
            nx = math.copysign(abs(u / a) ** (n - 1), u) / a
            ny = math.copysign(abs(y / b) ** (n - 1), y) / b
            ln = math.hypot(nx, ny) or 1.0
            nx, ny = nx / ln, ny / ln
            d = 0.0
            # рифление переда: поперечные канавки, к бокам сходят на нет
            if g0 - gw <= z <= g1 + gw:
                dz = abs(((z - g1) + pitch / 2) % pitch - pitch / 2)
                p = _ss((gw / 2 - dz) / 0.3)
                if p > 0:
                    wf = _ss(((u / a) - 0.5) / 0.3)
                    wy = _ss((11.5 - abs(y)) / 2.5)
                    d = max(d, gd * p * wf * wy)
            # поле под ладонь — на боках
            if pz0 - 1 <= z <= pz1 + 1 and abs(y) > 0.3 * b:
                sd = _sd_poly(panel, cx + u, z)
                if sd > -0.5:
                    d = max(d, GRIP_PANEL_D * _ss(sd / 0.45))
            ring.append(bm.verts.new(v(cx + u - d * nx, y - d * ny, z)))
        rings.append(ring)
    zb = zs[0]
    cxb = grip_section(zb, x0, x1)[0]
    tip = bm.verts.new(v(cxb, 0.0, zb - 0.6))
    for k in range(seg):
        bm.faces.new((rings[0][(k + 1) % seg], rings[0][k], tip))
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for f in me.polygons:
        f.use_smooth = True
    o = bpy.data.objects.new(name, me)
    C.objects.link(o)
    return o


FRONT_R = 14.0         # радиус кромок переда шахты (владелец 04.11: «круглее», снимок 04 — рёбра заворачивают на бока);
                       # больше нельзя: стенка шахты спереди 4–5 мм, при R 14 у угла гнезда магазина остаётся 3.4 мм
FRONT_LINE = ((5.4, -30.0), (-29.3, -100.0))   # передняя кромка шахты (контур корпуса со снимка)
WINDOW_LINE = ((-133.8, -34.8), (-149.9, -70.6))   # передняя кромка окна спуска (задняя грань шахты) — прямая


def _straighten(pts, line, zr, tol=3.0, blend=4.0):
    """Точки контура у прямой line (в пределах tol мм, Z в zr) — на прямую, у концов zr плавно."""
    (ax, az), (bx, bz) = line
    L = math.hypot(bx - ax, bz - az)
    tx, tz = (bx - ax) / L, (bz - az) / L
    nx, nz = -tz, tx
    z0, z1 = zr
    out = []
    for x, z in pts:
        d = (x - ax) * nx + (z - az) * nz
        if abs(d) < tol and z0 <= z <= z1:
            k = _ss((z - z0) / blend) * _ss((z1 - z) / blend)
            out.append((x - nx * d * k, z - nz * d * k))
        else:
            out.append((x, z))
    return out


def body_contour(pts):
    """Правки контура корпуса со снимка: прямые кромки там, где снимок волнится (перёд шахты — под скругление R 14,
    кромка окна спуска — сверка v04 Д7), ровный низ переднего блока на Z −21 (по снимку поднимался к дулу на 2 мм —
    под нижней планкой была клиновая щель, Д10) и «бобровый хвост» за рукоятью (между рукоятью и хвостом контур давал
    выемку вверх — Д1)."""
    pts = _straighten(pts, FRONT_LINE, (-100.0, -30.0))
    pts = _straighten(pts, WINDOW_LINE, (-70.0, -35.0), tol=2.5)
    zbt = pchip([(-214.0, 15.1), (-220.0, 14.6), (-226.0, 13.2), (-234.0, 11.9), (-244.0, 11.2), (-252.0, 11.0),
                 (-259.0, 11.7), (-264.0, 12.5)])
    out = []
    for x, z in pts:
        if 28.0 <= x <= 106.0 and -24.5 <= z <= -17.0:
            k = _ss((x - 28.0) / 5.0) * _ss((106.0 - x) / 3.0)
            z = z + (FRONT_LOW_Z - z) * k
        elif -264.0 <= x <= -214.0 and 9.0 <= z <= 17.5:
            z = zbt(x)
        out.append((x, z))
    return out


def body_r(x, z):
    """Радиус кромки корпуса по месту контура (сразу в сетке, без булевых — резец по касательной оставлял щепки, и дальше
    по корпусу пропадали буквы гравировки):
    - везде 2.4;
    - перёд шахты (рифлёная часть под цевьём, за неё берутся; владелец 04.11: «как брусок») — до 14: нарастает от
      Z −32 к −60 (выше — лопатки защёлки магазина), у нижнего угла (скругление контура меньше радиуса) спадает до 2.4;
    - низ коробки над рукоятью — 0.45: рукоять подходит почти во всю ширину, без «воротника» (сверка v04 Д1)."""
    r = 2.4
    (ax, az), (bx, bz) = FRONT_LINE
    if -106.0 <= z <= -18.0:
        L = math.hypot(bx - ax, bz - az)
        nx, nz = -(bz - az) / L, (bx - ax) / L
        dist = abs((x - ax) * nx + (z - az) * nz)
        # полоса веса широкая: контур гуляет около прямой — радиус не должен скакать от точки к точке
        w = _ss((8.0 - dist) / 5.0)
        rz = 2.4 + (FRONT_R - 2.4) * _ss((-z - 32.0) / 28.0)
        rz = rz - (rz - 2.4) * _ss((-z - 88.0) / 12.0)
        r = 2.4 + (rz - 2.4) * w
    if -232.0 <= x <= -158.0 and 9.0 <= z <= 17.5:
        w = _ss((x + 232.0) / 6.0) * _ss((-158.0 - x) / 6.0)
        r = r - (r - 0.45) * w
    return r


def loop_features(o, C):
    """Рукоять с нижней тягой («петля», 31 мм) и перекладина скобы (13 мм) — заодно с корпусом."""
    # рукоять — одно тело (лофт по овалам, рифление и поле — в сетке); нижняя тяга и перекладина — скруглённые призмы
    g = grip_loft(C)
    bar_pts = [tuple(p) for p in max(PROFILES["parts"]["th_bar"], key=lambda it: len(it["outer"]))["outer"]]
    # низ тяги по снимку волнистый (сверка v02 Н1, v04 Д9) — сгладить сильнее обычного
    bar = rounded_prism("_bar", smooth_poly(bar_pts, 0.7, 10), -BAR_HALF_W, BAR_HALF_W, 2.0, C)
    # перекладина скобы: передний конец (по снимку — X −127) углублён в стойку на 9 мм, чтобы плоский торец не торчал
    # «лапкой» на внутренней стенке стойки (сверка v04 Д6)
    gpts = [tuple(p) for p in max(PROFILES["parts"]["th_guard"], key=lambda it: len(it["outer"]))["outer"]]
    gpts = [(x + 9.0 * _ss((x + 133.0) / 4.0), z) for x, z in gpts]
    b = rounded_prism("_guard", gpts, -GUARD_HALF_W, GUARD_HALF_W, 1.5, C)
    # объединения и вырезы петли — с проверкой и повтором (lib.boolean_safe)
    boolean_safe(o, g, op="UNION", name="рукоять")
    boolean_safe(o, bar, op="UNION", name="нижняя тяга")
    boolean_safe(o, b, op="UNION", name="скоба")
    # окно петли — вычесть по контуру отверстия со снимка, ужатому на 2.5 мм: убирает натянутую поперёк окна «плёнку»
    # (проверка v02), стенки окна не задевает
    for i, it in enumerate(PROFILES["parts"].get("hand_hole", [])):
        c = prism_xz(f"_hh{i}", [tuple(p) for p in it["outer"]], -40.0, 40.0, C)
        boolean_safe(o, c, name="окно петли")
    # прорезь под перо спуска — заново: верх рукояти (лофт до Z 18) заходит в низ коробки у прорези
    c = prism_xz("_trigslot2", rounded_rect_xz(-173.0, -136.0, 12.0, 30.0, 2.0), -3.9, 3.9, C)
    boolean_safe(o, c, name="прорезь спуска")


def _panel_to(zmin):
    """Линия шва шахта / спусковая коробка до высоты zmin (последняя точка — на пересечении диагонали с zmin)."""
    out = [p for p in PANEL_LINE if p[1] > zmin]
    a = out[-1]
    b = next(p for p in PANEL_LINE if p[1] <= zmin)
    t = (zmin - a[1]) / (b[1] - a[1])
    return out + [(a[0] + (b[0] - a[0]) * t, zmin)]


def seams(o, C):
    """Швы деталей прототипа — канавки 1.2 × 0.45 (корпус одним телом): низ коробки над шахтой (Z 15), задняя грань
    переднего блока (X 22), дуга и диагональ между шахтой и спусковой коробкой."""
    for s_ in (1, -1):
        side_line(o, [(FRONT_BLOCK_REAR_X, FRONT_LOW_Z + 1.0), (FRONT_BLOCK_REAR_X, SEAM_Z), (-60.0, SEAM_Z)] +
                  _panel_to(-104.0), 1.2, 0.45, s_, C)


def front_face(o, C):
    """Передний торец (снимок владельца 04): крышка со швом по контуру и знаком, ствол выходит из выемки."""
    c = cyl("_fr", FRONT_FACE_X - 2.5, FRONT_FACE_X + 3, 11.0, C, seg=96)
    boolean(o, c)
    pts = rounded_rect_xz(-15.5, 15.5, 13.0, RAIL_BASE - 4.0, 4.0)
    inner = rounded_rect_xz(-14.7, 14.7, 13.8, RAIL_BASE - 4.8, 3.2)
    ring = prism_yz("_capseam", [(y, z) for y, z in pts], FRONT_FACE_X - 0.45, FRONT_FACE_X + 2, C)
    inn = prism_yz("_capin", [(y, z) for y, z in inner], FRONT_FACE_X - 1, FRONT_FACE_X + 3, C)
    boolean(ring, inn)
    boolean(o, ring)


SIDE_RAIL_X = (26.0, 103.5)      # боковые планки 1913 на переднем блоке (h1ggs: X 25…102; снимок владельца 04 — справа)
SIDE_RAIL_Z = 1.5                # середина планки: верх (Z 12.1) — под линией уступа справа (Z 13)
SIDE_RAIL_H = 7.5                # высота над бортом
SIDE_RAIL_SCREWS = (40.0, 90.0)  # винты — в пазах, на месте осей переднего блока (у h1ggs винты там же)


def _side_to_world(me, side):
    """Планка построена «как верхняя» (вдоль X, верх — +Z от 0); переносим на борт: верх — наружу (±Y), середина — Z."""
    import bmesh as _bm
    for vv in me.vertices:
        x, yl, zl = vv.co.x / MM, vv.co.y / MM, vv.co.z / MM
        vv.co = v(x, side * (HALF_W + zl), SIDE_RAIL_Z - side * yl)
    bm = _bm.new(); bm.from_mesh(me)
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.update()


def side_rails(C):
    """Боковые планки MIL-STD-1913 слева и справа на переднем блоке: по 7 пазов, два винта с шестигранником в пазах
    (владелец 04.11: «не хватает планок Picatinny по бокам»). Основание заходит в борт на 0.3 (без совпадающих граней)."""
    out = []
    x0, x1 = SIDE_RAIL_X
    # только справа: у настоящего Gen II (снимки KRISS A, владельца 01, 02) и у h1ggs слева планки нет — на её месте
    # два винта (part_pins); левую можно вернуть, добавив (1, "L") в список
    for side, tag in ((-1, "R"),):
        r = prism_yz("Side_rail_" + tag, rail_profile(SIDE_RAIL_H, -0.3), x0, x1, C, "Steel_black")
        rail_slots(r, x0, x1, SIDE_RAIL_H, 1.0, 100.0, C)
        # торцы и кромки: скругление концов в плане
        for xe, sgn in ((x0, 1), (x1, -1)):
            c = prism_xy("_re", [(xe - 3 * sgn, -RAIL_HALF_W - 1), (xe + 2.2 * sgn, -RAIL_HALF_W - 1),
                                 (xe - 3 * sgn, -RAIL_HALF_W + 4.0)], -1.0, SIDE_RAIL_H + 1, C)
            boolean(r, c)
            c = prism_xy("_re", [(xe - 3 * sgn, RAIL_HALF_W + 1), (xe + 2.2 * sgn, RAIL_HALF_W + 1),
                                 (xe - 3 * sgn, RAIL_HALF_W - 4.0)], -1.0, SIDE_RAIL_H + 1, C)
            boolean(r, c)
        # гнёзда винтов: Ø9.2 до 1.5 над бортом
        for xs in SIDE_RAIL_SCREWS:
            boolean(r, cyl("_cb", 1.5, SIDE_RAIL_H + 1, 4.6, C, seg=48, cy=xs, cz=0.0, axis="Z"))
        finish_small(r, w=0.35, seg=3)
        _side_to_world(r.data, side)
        r["owner"] = "Receiver"
        out.append(r)
        for i, xs in enumerate(SIDE_RAIL_SCREWS):
            hd = lathe(f"Side_rail_screw_{tag}{i}", [(1.5, 0.0), (1.5, 4.25), (4.0, 4.25), (4.3, 3.95), (4.3, 0.0)], C,
                       "Steel_black", seg=48, cy=0.0, cz=0.0)
            # ось токарного профиля — X; поворачиваем к Z (вверх «как у верхней»)
            import mathutils
            hd.data.transform(mathutils.Matrix.Rotation(-math.pi / 2, 4, "Y"))
            hd.data.transform(mathutils.Matrix.Translation(v(xs, 0.0, 0.0)))
            hexp = [(xs + 2.0 * math.cos(math.pi / 3 * k), 2.0 * math.sin(math.pi / 3 * k)) for k in range(6)]
            boolean(hd, prism_xy("_hex", hexp, 2.6, 5.0, C))
            finish_small(hd, w=0.15, seg=2)
            _side_to_world(hd.data, side)
            hd["owner"] = "Side_rail_" + tag + ",Receiver"
            out.append(hd)
    return out


def build(ctx):
    cc = ctx["coll"]
    C = cc["Receiver"]
    pts, _h = profile("body")
    # гравировки — первыми, на простом корпусе: точное вычитание на готовом корпусе (сотни вырезов) пропускало буквы
    # и давало рёбра на четыре грани (04.11); дальнейшие вырезы места надписей не задевают, мелкая фаска их не трогает.
    # Точное булево Blender изредка сбоит от запуска к запуску — буква с неудачным вычитанием откатывается
    # (part_stamps.stamp), и тогда корпус строится заново и гравировка повторяется
    import part_stamps
    for attempt in range(5):
        o = rounded_prism("Receiver", body_contour(clean_front(pts)), -HALF_W, HALF_W, 2.4, C, "Alu_anodized",
                          r_fn=body_r)
        zones = part_stamps.apply(o, C)
        if not part_stamps.FAILED:
            break
        print("STAMPS_REBUILD", attempt, part_stamps.FAILED)
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(me)
    upper_features(o, C)
    magwell_features(o, C)
    loop_features(o, C)
    seams(o, C)
    front_face(o, C)
    # выемка под кулак приклада (шарнир на правом заднем углу), зазор 0.4
    from part_stock import HINGE_X, HINGE_Y, HINGE_Z
    c = cyl("_kclr", HINGE_Z[0] + 8.2, HINGE_Z[1] - 8.2, 6.9, C, seg=64, cy=HINGE_X, cz=HINGE_Y, axis="Z")
    boolean(o, c)

    def keep_engraving(center, normal):
        return any((center - Vector(z)).length < r for z, r in zones)
    finish_small(o, w=0.45, seg=3, exclude=keep_engraving if zones else None)
    rails = side_rails(C)
    return {"receiver": o, "upper": o, "magwell": o, "trigger_housing": o, "side_rails": rails}
