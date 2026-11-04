# ПП по мотивам KRISS Vector Gen II: коробка (верх с планками, передний блок со стволом, окно выброса справа, паз
# рукоятки заряжания слева), корпус шахты магазина (наклон 21°, рёбра переда, выемки боков) и спусковая коробка
# (рукоять, скоба, нижняя тяга). Контуры деталей сбоку — перенос со снимков KRISS (data/profiles.json), ширины —
# asset-state.md. Все вырезы делаются до общего скругления (finish в build.py), чтобы кромки вырезов тоже были круглыми.
import math
import bpy
from mathutils import Matrix, Vector
from lib import (PROFILES, rounded_prism, finish, finish_small, bevel_edges, MM, HALF_W, RAIL_TOP, RAIL_BASE, RAIL_HALF_W, SEAM_Z, SEAM_REAR_Z, FRONT_FACE_X, FRONT_LOW_Z, REAR_X,
                 FRONT_BLOCK_REAR_X, PANEL_LINE, MAG_ANGLE, MAG_W, MAG_D, BARREL_R, profile, fillet, prism_xz, prism_yz,
                 prism_xy, box, cyl, lathe, boolean, apply_transform, v)

RAIL_SLOT_W = 5.23
RAIL_SLOT_DEPTH = 2.9
TOP_RAIL_X = (-262.0, 104.0)
LOW_RAIL_X = (24.0, 102.5)
LOW_RAIL_TOP = -29.5             # низ зубьев нижней планки (снимок)
CH_SLOT_Z = (17.6, 23.4)         # паз рукоятки заряжания слева (снимок)
CH_SLOT_X = (-46.0, FRONT_FACE_X + 5)
CH_SLOT_DEPTH = 5.0
PORT_X = (-43.0, 4.0)            # окно выброса справа (снимок B)
PORT_Z = (15.0, 47.5)            # низ окна — по шву (снимок B: 13; дно окна — верх корпуса шахты), сверху полка 2.2 мм
CAVITY = (-111.0, 40.0, -14.5, 14.5, -12.5, 46.5)  # полость затвора внутри коробки (x0, x1, y0, y1, z0, z1)
TRIG_HALF_W = 20.0               # спусковая коробка: передняя тяга и нижняя тяга
GRIP_HALF_W = 15.5               # рукоять (оценка: обычная пистолетная ~31 мм)
GUARD_HALF_W = 6.5               # перекладина скобы


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
    pts = [(CH_SLOT_X[1], z0), (CH_SLOT_X[0] + zr, z0)] + \
          [(CH_SLOT_X[0] + zr - zr * math.sin(math.pi * k / 10), (z0 + z1) / 2 - zr * math.cos(math.pi * k / 10)) for k in range(1, 10)] + \
          [(CH_SLOT_X[0] + zr, z1), (CH_SLOT_X[1], z1)]
    c = prism_xz("_chslot", pts, HALF_W - CH_SLOT_DEPTH, HALF_W + 5, C)
    boolean(o, c)
    # полость затвора и окно выброса справа (−Y)
    x0, x1, y0, y1, zc0, zc1 = CAVITY
    c = prism_xz("_cav", rounded_rect_xz(x0, x1, zc0, zc1, 3.0), y0, y1, C)
    boolean(o, c)
    c = prism_xz("_port", rounded_rect_xz(PORT_X[0], PORT_X[1], PORT_Z[0], PORT_Z[1], 2.5), -HALF_W - 5, 0.0, C)
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
    # канавки — по плоской части передней грани (кончаются до скруглённых боковых кромок R 3: иначе фаска их концов
    # перехлёстывается)
    ribs(o, pts, edge_run(pts, (21.0, -22.0), (-27.0, -104.0), (-2.0, -62.0)), 3.6, 1.6, 1.0, HALF_W - 3.4, C, "_mwribs")
    # гнёзда органов управления: кнопка задержки справа (X −38, Z −10) и лопатки защёлки магазина у переднего ребра
    c = prism_xz("_brp", rounded_rect_xz(-43.2, -32.8, -14.8, -5.2, 2.0), -HALF_W - 3, -HALF_W + 3.8, C)
    boolean(o, c)
    up_, fw_ = mag_frame()
    a_ = (-7.0 + up_.x * 6.0, -38.0 + up_.z * 6.0)
    b_ = (-7.0 - up_.x * 6.0, -38.0 - up_.z * 6.0)
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


def _bodies(name, prof_name, half, r, C, mat=None):
    """Все куски профиля prof_name — скруглённые призмы, объединённые в одно тело."""
    items = PROFILES["parts"][prof_name]
    objs = []
    for k, it in enumerate(items):
        objs.append(rounded_prism(name if k == 0 else f"_{name}{k}", [tuple(p) for p in it["outer"]], -half, half, r, C, mat))
    o = objs[0]
    for b in objs[1:]:
        boolean(o, b, op="UNION")
    return o


def loop_features(o, C):
    """Рукоять с нижней тягой («петля», 31 мм) и перекладина скобы (13 мм) — заодно с корпусом."""
    g = _bodies("_loop", "th_loop", GRIP_HALF_W, 2.0, C)
    b = _bodies("_guard", "th_guard", GUARD_HALF_W, 1.5, C)
    boolean(o, g, op="UNION")
    boolean(o, b, op="UNION")
    gp = [tuple(p) for p in max(PROFILES["parts"]["th_grip"], key=lambda it: len(it["outer"]))["outer"]]
    ribs(o, gp, edge_run(gp, (-183.0, -18.0), (-203.0, -74.0), (-195.0, -50.0)), 3.4, 1.5, 0.9, GRIP_HALF_W - 2.6, C,
         "_gripfront")
    ribs(o, gp, edge_run(gp, (-235.0, -18.0), (-247.0, -70.0), (-241.0, -45.0)), 3.4, 1.5, 0.9, GRIP_HALF_W - 2.6, C,
         "_gripback")
    # поле под ладонь — утоплено на 0.6, от кромок на 4…8 мм (шагрень — на этапе текстур)
    panel = fillet([(-206.0, -10.0), (-229.0, -10.0), (-238.0, -62.0), (-217.0, -72.0)], [4.0, 4.0, 6.0, 6.0], 6)
    side_recess(o, panel, 0.6, C, half=GRIP_HALF_W)


def seams(o, C):
    """Швы деталей прототипа — канавки 1.2 × 0.45 (корпус одним телом): низ коробки над шахтой (Z 15), задняя грань
    переднего блока (X 22), дуга и диагональ между шахтой и спусковой коробкой."""
    for s_ in (1, -1):
        side_line(o, [(FRONT_BLOCK_REAR_X, FRONT_LOW_Z + 1.0), (FRONT_BLOCK_REAR_X, SEAM_Z), (-60.0, SEAM_Z)] +
                  [p for p in PANEL_LINE if p[1] > -104.0], 1.2, 0.45, s_, C)


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


def build(ctx):
    cc = ctx["coll"]
    C = cc["Receiver"]
    pts, _h = profile("body")
    o = rounded_prism("Receiver", clean_front(pts), -HALF_W, HALF_W, 2.4, C, "Alu_anodized")
    upper_features(o, C)
    magwell_features(o, C)
    loop_features(o, C)
    seams(o, C)
    front_face(o, C)
    finish_small(o, w=0.45, seg=3)
    return {"receiver": o, "upper": o, "magwell": o, "trigger_housing": o}
