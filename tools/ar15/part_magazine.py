# AR-15: полимерный магазин STANAG на 30 (своя форма в манере листинга Fab: каркас рёбер, сквозные окна-индикаторы
# сзади, рифлёные панели хвата спереди, раструб-«плечо» под шахтой), съёмное донце с фиксатором, подаватель со
# ступенькой под затворную задержку, пружина-«змейка», 30 патронов в шахматном порядке (связанные копии одной сетки).
# Отдельно, в стороне от оружия, — целый патрон 5.56×45 и стреляная гильза.
# Магазин строится в собственной системе «вдоль хребта»: s — вниз по магазину от верха губок, u — вперёд, w = Y.
# Верх прямой (в шахте), ниже — дуга R вперёд: изгиб под конусность гильзы (головки сзади, пули спереди).
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, MAG_TOP_Z, MAG_X, MAG_HALF_W, MAG_CATCH_SLOT, v, fillet, prism_xz, prism_yz, lathe, boolean, finish,
                 join, auto_sharp, material, set_parent, set_origin, box)
from part_lower import BOLT_CATCH_PIVOT

Z0 = MAG_TOP_Z
CX = (MAG_X[0] + MAG_X[1]) / 2            # середина горловины по X
L2 = (MAG_X[1] - MAG_X[0]) / 2            # полудлина сечения (33.3)
S_STRAIGHT = 64.0                         # прямой участок в шахте
R_CURVE = 560.0                           # радиус изгиба (под конус гильзы 9.60 → 9.00 мм)
S_BOTTOM = 179.0                          # низ корпуса по хребту
WALL = 1.8
RF, RR = 4.0, 3.0                         # скругления передних и задних углов сечения
BODY_HW = 12.3                            # полуширина корпуса ниже шахты
TOP_HW = 10.0                             # полуширина верха (проходит между стенками верхнего ресивера)
U_HEAD = -L2 + WALL + 0.9                 # донце гильзы у задней стенки (зазор до скругления угла)
ROUND_D = 9.62
ROUND_STEP = 4.84                         # шаг рядов по донцам гильз
COL_W = 4.75                              # центры колонн от середины


# ---------- хребет ----------

def frame(s):
    """Точка хребта и оси сечения: P, T (вниз по магазину), U (вперёд)."""
    if s <= S_STRAIGHT:
        return Vector((CX, 0.0, Z0 - s)), Vector((0.0, 0.0, -1.0)), Vector((1.0, 0.0, 0.0))
    ph = (s - S_STRAIGHT) / R_CURVE
    c = Vector((CX + R_CURVE, 0.0, Z0 - S_STRAIGHT))
    p = c + Vector((-math.cos(ph), 0.0, -math.sin(ph))) * R_CURVE
    return p, Vector((math.sin(ph), 0.0, -math.cos(ph))), Vector((math.cos(ph), 0.0, math.sin(ph)))


def pt(s, u, w):
    p, t, uu = frame(s)
    return p + uu * u + Vector((0.0, w, 0.0))


def rigid(s0):
    """Жёсткая система в точке s0 (для мелких деталей у донца и подавателя): (s, u, w) → мм."""
    p, t, uu = frame(s0)
    return lambda s, u, w: p + t * (s - s0) + uu * u + Vector((0.0, w, 0.0))


def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def outer_hw(s):
    if s <= 15.0:
        return TOP_HW
    if s <= 19.0:
        return lerp(TOP_HW, MAG_HALF_W, (s - 15.0) / 4.0)
    if s <= 74.0:
        return MAG_HALF_W
    return lerp(MAG_HALF_W, BODY_HW, (s - 74.0) / 3.0)


def inner_hw(s):
    if s <= 15.0:
        return TOP_HW - WALL
    return lerp(TOP_HW - WALL, 9.8, (s - 15.0) / 10.0)


def section(hu0, hu1, hw, rf, rr, seg=4):
    """Скруглённый прямоугольник сечения (u, w): перед — u1, зад — u0."""
    return fillet([(hu0, -hw), (hu1, -hw), (hu1, hw), (hu0, hw)], [rr, rf, rf, rr], seg)


# ---------- построение сеток ----------

def loft(name, rings, coll, mat=None, cap0=True, cap1=True, smooth=True):
    """Лофт по кольцам точек (мм, Vector) с одинаковым числом точек."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vr = [[bm.verts.new(p * MM) for p in r] for r in rings]
    n = len(vr[0])
    for r0, r1 in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if cap0:
        bm.faces.new(list(reversed(vr[0])))
    if cap1:
        bm.faces.new(vr[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if mat:
        o.data.materials.append(material(mat))
    return o


def hexa(name, c, coll, mat=None):
    """Шестигранник по 8 углам: c[0..3] — нижнее кольцо, c[4..7] — верхнее (в том же порядке)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vv = [bm.verts.new(p * MM) for p in c]
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([vv[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if mat:
        o.data.materials.append(material(mat))
    return o


def lbox(name, f, s0, s1, u0, u1, w0, w1, coll, mat=None):
    c = [f(s0, u0, w0), f(s0, u1, w0), f(s0, u1, w1), f(s0, u0, w1), f(s1, u0, w0), f(s1, u1, w0), f(s1, u1, w1), f(s1, u0, w1)]
    return hexa(name, c, coll, mat)


def side_prism(name, su_pts, y0, y1, coll, mat=None):
    """Контур в координатах (s, u) на изогнутом хребте → профиль XZ, выдавленный по Y (боковины магазина плоские)."""
    pts = []
    for s, u in su_pts:
        p = pt(s, u, 0.0)
        pts.append((p.x, p.z))
    return prism_xz(name, pts, y0, y1, coll, mat)


def rr_su(s0, s1, u0, u1, r, seg=3):
    return fillet([(s0, u0), (s0, u1), (s1, u1), (s1, u0)], r, seg)


def stations(s0, s1, step, extra=()):
    ss = set(round(s0 + k * step, 3) for k in range(int((s1 - s0) / step) + 1))
    ss.update(e for e in extra if s0 <= e <= s1)
    ss.add(s1)
    return sorted(ss)


# ---------- корпус ----------

def body(C):
    brk = (0.0, 15.0, 19.0, 25.0, 74.0, 77.0, S_STRAIGHT)
    rings = [[pt(s, u, w) for u, w in section(-L2, L2, outer_hw(s), RF, RR)] for s in stations(-8.0, S_BOTTOM, 2.5, brk)]
    b = loft("Magazine_body", rings, C, "Polymer")
    rings = [[pt(s, u, w) for u, w in section(-L2 + WALL, L2 - WALL, inner_hw(s), RF - WALL + 0.4, RR - WALL + 0.4)]
             for s in stations(-20.0, S_BOTTOM + 12.0, 2.5, brk)]
    boolean(b, loft("cut_mag_cavity", rings, C))
    # верх: губки сзади на уровне MAG_TOP_Z, спереди опущен под гайку/ресивер (пули поднимаются по рампе)
    top = prism_xz("cut_mag_top", fillet([(-90.0, Z0), (-10.0, Z0), (-4.0, -17.6), (5.0, -17.6), (7.4, -23.2), (40.0, -23.2),
                                          (40.0, 30.0), (-90.0, 30.0)], [0, 3.0, 3.0, 1.5, 1.5, 0, 0, 0], 4), -30.0, 30.0, C)
    boolean(b, top)
    # губки — продолжение стенок, загнуты внутрь над верхним патроном
    for s in (1, -1):
        yi, yo = 5.0 * s, (TOP_HW - WALL + 0.3) * s
        prof = [(yo, Z0 - 1.5), (yi + 0.6 * s, Z0 - 1.5), (yi, Z0 - 1.0), (yi, Z0 - 0.5), (yi + 0.5 * s, Z0), (yo, Z0)]
        if s < 0:
            prof = list(reversed(prof))
        lip = prism_yz("mag_lip", prof, MAG_X[0] + WALL - 0.3, -10.5, C, "Polymer")
        boolean(b, lip, "UNION")
    # задняя стенка между губками ниже верха: над ней проходит хвост затвора, донце верхнего патрона открыто затвору
    boolean(b, box("cut_mag_rear_dip", MAG_X[0] - 3.0, MAG_X[0] + 4.5, -5.0, 5.0, Z0 - 1.4, Z0 + 5.0, C))
    # выемка сзади-слева под зуб затворной задержки
    bx, by, bz = BOLT_CATCH_PIVOT
    boolean(b, prism_xz("cut_bc_notch", fillet([(bx - 6.0, bz + 7.6), (bx + 5.5, bz + 7.6), (bx + 5.5, 6.0), (bx - 6.0, 6.0)],
                                               [0, 1.2, 0, 0], 3), 5.0, 20.0, C))
    # окно защёлки на левой стенке
    cx, cz = MAG_CATCH_SLOT
    boolean(b, prism_xz("cut_catch_slot", fillet([(cx - 4.2, cz - 4.0), (cx + 3.4, cz - 4.0), (cx + 3.4, cz + 4.0), (cx - 4.2, cz + 4.0)],
                                                 0.6, 2), 8.0, 20.0, C))
    # каркас ниже шахты: ряды панелей между рёбрами — сзади сквозные окна, спереди рифлёные панели
    rows = [(83.0, 95.5), (99.0, 111.5), (115.0, 127.5), (131.0, 143.5), (147.0, 159.5), (163.0, 172.5)]
    hw = BODY_HW
    cuts, wins = [], []
    for i, (s0, s1) in enumerate(rows):
        for sg in (1, -1):
            y0, y1 = (hw - 0.9, hw + 3.0) if sg > 0 else (-hw - 3.0, -hw + 0.9)
            cuts.append(side_prism(f"cut_pan_r{i}{sg}", rr_su(s0, s1, -L2 + 4.2, -9.5, 2.0), y0, y1, C))
            cuts.append(side_prism(f"cut_pan_f{i}{sg}", rr_su(s0, s1, -6.5, L2 - 3.8, 2.0), y0, y1, C))
            wy0, wy1 = (8.6, hw + 3.0) if sg > 0 else (-hw - 3.0, -8.6)
            wins.append(side_prism(f"cut_win{i}{sg}", rr_su(s0 + 2.2, s1 - 2.2, -24.5, -14.0, 1.6), wy0, wy1, C))
    boolean(b, join(cuts, "cut_panels"))
    boolean(b, join(wins, "cut_windows"))
    # передняя стенка: поперечные канавки хвата
    gr = []
    s = 82.0
    while s < 173.0:
        gr.append(side_prism(f"cut_fg{int(s)}", rr_su(s - 0.7, s + 0.7, L2 - 0.75, L2 + 6.0, 0.3, 2), -hw + 3.2, hw - 3.2, C))
        s += 3.6
    boolean(b, join(gr, "cut_front_grooves"))
    # «плечо» под шахтой: поясок вокруг корпуса
    band = []
    for sg in (1, -1):
        y0, y1 = (hw - 0.6, hw + 3.0) if sg > 0 else (-hw - 3.0, -hw + 0.6)
        band.append(side_prism(f"cut_band{sg}", rr_su(78.4, 79.6, -L2 - 2, L2 + 2, 0.0, 1), y0, y1, C))
    boolean(b, join(band, "cut_band"))
    finish(b, w=0.3, seg=2, angle=35)
    # пирамидки хвата на передних панелях
    studs = bmesh.new()
    for (s0, s1) in rows:
        nu, ns = 10, 3
        for sg in (1, -1):
            for iu in range(nu):
                for is_ in range(ns):
                    u = -3.5 + iu * 3.25
                    sc = s0 + 2.6 + is_ * ((s1 - s0 - 5.2) / (ns - 1))
                    base, topw, h = 1.15, 0.55, 0.65
                    yb = (hw - 0.9) * sg
                    yt = (hw - 0.9 + h) * sg
                    ring0 = [pt(sc + ds, u + du, 0.0) for ds, du in ((-base, -base), (-base, base), (base, base), (base, -base))]
                    ring1 = [pt(sc + ds, u + du, 0.0) for ds, du in ((-topw, -topw), (-topw, topw), (topw, topw), (topw, -topw))]
                    vb = [studs.verts.new(Vector((p.x, yb, p.z)) * MM) for p in ring0]
                    vt = [studs.verts.new(Vector((p.x, yt, p.z)) * MM) for p in ring1]
                    studs.faces.new(vt if sg > 0 else list(reversed(vt)))
                    for k in range(4):
                        j = (k + 1) % 4
                        studs.faces.new((vb[k], vb[j], vt[j], vt[k]))
    bmesh.ops.recalc_face_normals(studs, faces=studs.faces)
    me = bpy.data.meshes.new("mag_studs")
    studs.to_mesh(me); studs.free()
    so = bpy.data.objects.new("mag_studs", me)
    C.objects.link(so)
    so.data.materials.append(material("Polymer"))
    auto_sharp(so, 35)
    return join([b, so], "Magazine_body")


# ---------- донце ----------

def floorplate(C):
    sm = S_BOTTOM + 0.5
    f = rigid(sm)

    def ring(s, d):
        return [f(s, u, w) for u, w in section(-L2 - 1.4 + d, L2 + 4.3 - d, BODY_HW + 1.4 - d, 6.0 - d, 4.0 - d)]

    fp = loft("Magazine_floorplate", [ring(S_BOTTOM - 4.6, 0.5), ring(S_BOTTOM - 4.1, 0.0), ring(S_BOTTOM + 4.4, 0.0),
                                      ring(S_BOTTOM + 5.6, 1.1)], C, "Polymer")
    auto_sharp(fp, 35)
    # гнездо под низ корпуса (донце надвинуто на корпус)
    pocket = [[f(s, u, w) for u, w in section(-L2 - 0.12, L2 + 0.12, BODY_HW + 0.12, RF + 0.1, RR + 0.1)] for s in (S_BOTTOM - 8.0, S_BOTTOM + 1.0)]
    boolean(fp, loft("cut_fp_pocket", pocket, C))
    # снизу: поперечные рёбра хвата и фиксатор (кнопка в окне донца)
    gr = [lbox(f"cut_fp_g{k}", f, S_BOTTOM + 4.9, S_BOTTOM + 7.0, u - 0.7, u + 0.7, -BODY_HW + 1.0, BODY_HW - 1.0, C)
          for k, u in enumerate([-8.0 + 3.6 * i for i in range(11)])]
    boolean(fp, join(gr, "cut_fp_grooves"))
    boolean(fp, lbox("cut_fp_lock", f, S_BOTTOM + 2.6, S_BOTTOM + 7.0, -27.5, -15.5, -5.6, 5.6, C))
    finish(fp, w=0.3, seg=2, angle=35)
    lock = lbox("Magazine_floorplate_lock", f, S_BOTTOM + 1.0, S_BOTTOM + 4.4, -26.6, -16.4, -4.7, 4.7, C, "Polymer")
    finish(lock, w=0.5, seg=2, angle=35)
    return fp, lock


# ---------- патроны ----------

CASE = [(0.0, 0.0), (0.0, 2.23), (0.12, 2.23), (0.12, 2.48), (0.0, 2.48), (0.0, 4.50), (0.25, 4.80), (0.92, 4.80), (1.14, 4.55),
        (1.45, 4.215), (2.25, 4.215), (2.95, 4.775), (3.2, 4.785), (36.53, 4.495), (39.54, 3.215), (44.45, 3.215), (44.70, 3.10),
        (44.70, 2.85)]


def cartridge_mesh(C):
    case = lathe("c_case", CASE + [(44.70, 0.0)], C, "Brass", seg=40, cy=0.0, cz=0.0)
    # пуля: цилиндр у дульца, оживало, плоская вершина; кольцевой обжим у дульца
    prof = [(44.0, 0.0), (44.0, 2.85), (46.2, 2.85)]
    n = 14
    for k in range(1, n + 1):
        t = k / n
        x = 46.2 + (57.4 - 0.25 - 46.2) * t
        r = 2.85 * math.sqrt(max(0.0, 1.0 - t ** 1.9)) * (1.0 - 0.06 * t) + 0.42 * t
        prof.append((x, max(r, 0.42)))
    prof += [(57.4, 0.35), (57.4, 0.0)]
    bullet = lathe("c_bullet", prof, C, "Bullet_jacket", seg=40, cy=0.0, cz=0.0)
    o = join([case, bullet], "Cartridge_556")
    auto_sharp(o, 30)
    return o


def spent_case(C):
    prof = CASE[:-1] + [(44.70, 2.92), (44.0, 2.92), (40.0, 3.0), (38.0, 4.1), (3.5, 4.35), (3.5, 0.0)]
    o = lathe("Case_556", prof, C, "Brass", seg=40, cy=0.0, cz=0.0)
    # вмятина бойка на капсюле
    dent = lathe("cut_dent", [(-0.5, 0.0), (-0.5, 0.75), (0.25, 0.55), (0.45, 0.0)], C, None, seg=20, cy=0.0, cz=0.0)
    boolean(o, dent)
    auto_sharp(o, 30)
    return o


def round_positions():
    """Центры патронов по хребту (s, w): верхний под левой губкой, ниже — две колонны вплотную к стенкам;
    нижний (30-й) — в правой колонне, на низкой половине подавателя."""
    out = [(5.8, 2.4)]
    for k in range(1, 30):
        sg = -1.0 if k % 2 else 1.0
        s_prev, w_prev = out[-1]
        if k <= 3:
            s = s_prev + 5.0
            for _ in range(6):
                w = sg * min(COL_W, inner_hw(s - 4.5) - ROUND_D / 2 - 0.15)
                ds = math.sqrt(max(0.0, ROUND_D ** 2 - (abs(w) + abs(w_prev)) ** 2))
                s2 = s_prev + max(ds, 0.3)
                if k >= 2:
                    s2 = max(s2, out[k - 2][0] + ROUND_D)
                s = s2
            out.append((s, w))
        else:
            f = 1.0 if s_prev <= S_STRAIGHT else R_CURVE / (R_CURVE - U_HEAD)
            s = max(s_prev + ROUND_STEP * f, out[k - 2][0] + 2.0 * ROUND_STEP * f)
            out.append((s, sg * COL_W))
    return out


def place(o, s, u, w):
    p, t, uu = frame(s)
    yy = Vector((0.0, 1.0, 0.0))
    zz = uu.cross(yy)
    m = Matrix((uu, yy, zz)).transposed().to_4x4()
    pos = pt(s, u, w)
    m.translation = pos * MM
    o.matrix_world = m


# ---------- подаватель и пружина ----------

def follower(C, s_low, s_high, high_side):
    """Подаватель: половина high_side выше (под нижний патрон своей колонны), на ней сзади у стенки — невысокий
    выступ, который на пустом магазине поднимает затворную задержку (помещается под изгибом гильзы); спереди и
    сзади — ножки против перекоса."""
    f = rigid(s_low)
    hu0, hu1, hw = -L2 + WALL + 0.6, L2 - WALL - 0.6, 9.8 - 0.45
    base = loft("Magazine_follower", [[f(s, u, w) for u, w in section(hu0, hu1, hw, 2.2, 1.2)] for s in (s_low, s_low + 4.5)], C, "Polymer")
    w0, w1 = (0.7, hw - 0.4) if high_side > 0 else (-hw + 0.4, -0.7)
    hump = loft("fol_hump", [[f(s, u, w) for u, w in fillet([(hu0 + 0.6, w0), (hu1 - 1.0, w0), (hu1 - 1.0, w1), (hu0 + 0.6, w1)],
                                                             [1.0, 1.5, 1.5, 1.0], 3)] for s in (s_high, s_low + 0.5)], C, "Polymer")
    boolean(base, hump, "UNION")
    sw0, sw1 = (8.6, hw - 0.05) if high_side > 0 else (-hw + 0.05, -8.6)
    step = lbox("fol_step", f, s_high - 1.8, s_high + 0.5, hu0 + 0.4, hu0 + 6.0, sw0, sw1, C, "Polymer")
    boolean(base, step, "UNION")
    for u0, u1, d in ((25.6, hu1 - 0.6, 12.0), (hu0 + 0.6, -25.4, 9.0)):
        boolean(base, lbox("fol_leg", f, s_low + 4.0, s_low + 4.5 + d, u0, u1, -7.0, 7.0, C, "Polymer"), "UNION")
    finish(base, w=0.35, seg=2, angle=35)
    return base


def spring(C, s0, s1, turns=6, mat="Spring_steel"):
    """Пружина-«змейка»: плоская проволока по скруглённому прямоугольнику, виток к витку сжат подавателем."""
    rect = fillet([(-24.0, -7.2), (24.0, -7.2), (24.0, 7.2), (-24.0, 7.2)], 5.0, 6)
    seglens = [((Vector(rect[(i + 1) % len(rect)]) - Vector(rect[i])).length) for i in range(len(rect))]
    per = sum(seglens)
    npts = int(turns * 64)
    path = []
    for i in range(npts + 1):
        d = (i / 64.0 % 1.0) * per
        k = 0
        while d > seglens[k]:
            d -= seglens[k]
            k = (k + 1) % len(rect)
        a, b = Vector(rect[k]), Vector(rect[(k + 1) % len(rect)])
        q = a + (b - a) * (d / seglens[k])
        s = s0 + (s1 - s0) * i / npts
        path.append((s, q.x, q.y))
    bm = bmesh.new()
    rings = []
    for i, (s, u, w) in enumerate(path):
        pnow = pt(s, u, w)
        pa = pt(*path[max(0, i - 1)])
        pb = pt(*path[min(len(path) - 1, i + 1)])
        d = (pb - pa).normalized()
        tsp = frame(s)[1]
        n = tsp.cross(d).normalized()
        bnorm = d.cross(n).normalized()
        ring = [bm.verts.new((pnow + n * a + bnorm * b) * MM) for a, b in ((-0.3, -0.75), (0.3, -0.75), (0.3, 0.75), (-0.3, 0.75))]
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4):
            j = (k + 1) % 4
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Magazine_spring")
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new("Magazine_spring", me)
    C.objects.link(o)
    o.data.materials.append(material(mat))
    auto_sharp(o, 40)
    return o


# ---------- сборка ----------

def build(ctx):
    C = ctx["coll"]["Magazine"]
    o = {}
    b = body(C)
    fp, lock = floorplate(C)
    # патроны: одна сетка, связанные копии
    proto = cartridge_mesh(C)
    me = proto.data
    rounds_root = bpy.data.objects.new("Magazine_rounds", None)
    rounds_root.empty_display_type = "PLAIN_AXES"
    rounds_root.empty_display_size = 0.01
    C.objects.link(rounds_root)
    rounds = []
    pos = round_positions()
    for k, (s, w) in enumerate(pos):
        r = bpy.data.objects.new(f"Magazine_round_{k:02d}", me)
        C.objects.link(r)
        place(r, s, U_HEAD, w)
        rounds.append(r)
    # подаватель под последним патроном и пружина до донца
    s_last, w_last = pos[-1]
    s_prev, w_prev = pos[-2]
    s_low = s_last + ROUND_D / 2 + 0.45
    s_high = s_prev + ROUND_D / 2 + 0.45
    fol = follower(C, s_low, s_high, 1.0 if w_prev > 0 else -1.0)
    spr = spring(C, s_low + 4.5 + 0.85, S_BOTTOM + 1.0 - 0.85)
    # отдельный патрон и стреляная гильза — в стороне, для сцены
    proto.location = (40.0 * MM, 150.0 * MM, -260.0 * MM)     # отдельно от оружия, ниже и левее магазина
    case = spent_case(C)
    case.location = (40.0 * MM, 172.0 * MM, -260.0 * MM)
    # иерархия: всё — дети корпуса, начало корпуса — верх-перед горловины
    set_origin(b, (MAG_X[1], 0.0, MAG_TOP_Z))
    bpy.context.view_layer.update()
    for ch in (fp, fol, spr, rounds_root):
        set_parent(ch, b)
    set_parent(lock, fp)
    for r in rounds:
        set_parent(r, rounds_root)
    o.update({"body": b, "floorplate": fp, "floorplate_lock": lock, "follower": fol, "spring": spr, "rounds_root": rounds_root,
              "rounds": rounds, "cartridge": proto, "case": case, "round_positions": pos})
    return o
