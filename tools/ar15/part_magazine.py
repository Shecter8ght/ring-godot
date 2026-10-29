# AR-15: полимерный магазин STANAG на 30 (своя форма в манере листинга Fab: каркас рёбер, сквозные окна-индикаторы
# сзади, рифлёные панели хвата спереди, раструб-«плечо» под шахтой), съёмное донце с фиксатором, подаватель со
# ступенькой под затворную задержку, пружина-«змейка», 30 патронов в шахматном порядке (связанные копии одной сетки).
# Отдельно, в стороне от оружия, — целый патрон 5.56×45 и стреляная гильза.
# Маркировки вымышленные: «ГРАНЬ» и «5,56×45 · 30» на верхней части стенок, на донце; у окон — цифры остатка; на донце
# гильзы — клеймо «ГР 24». Владелец (2026-10-29): надписи делаются на этапе текстур — в геометрии они только при
# lib.MARKINGS_GEOMETRY = True (по умолчанию нет), места под них ровные. Сетки замкнутые.
# Магазин строится в собственной системе «вдоль хребта»: s — вниз по магазину от верха губок, u — вперёд, w = Y.
# Верх прямой (в шахте), ниже — дуга R вперёд на CURVE_DEG и снова прямой низ: так изогнут 30-зарядный STANAG
# (замер по фото PEO M4, 4.7 пикс/мм: задняя кромка уходит вперёд на ≈ 22 мм на 85 мм ниже шахты, низ — под ≈ 19–20°).
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import (MM, MAG_TOP_Z, MAG_X, MAG_HALF_W, MAG_CATCH_SLOT, v, fillet, prism_xz, prism_yz, lathe, boolean, finish,
                 join, auto_sharp, material, set_parent, set_origin, box, renormal)
from part_lower import BOLT_CATCH_PIVOT

Z0 = MAG_TOP_Z
CX = (MAG_X[0] + MAG_X[1]) / 2            # середина горловины по X
L2 = (MAG_X[1] - MAG_X[0]) / 2            # полудлина сечения (33.3)
S_STRAIGHT = 58.0                         # прямой участок: в шахте до её переднего среза и чуть ниже
R_CURVE = 250.0                           # радиус дуги изгиба (по хребту)
CURVE_DEG = 20.0                          # поворот нижней части вперёд
S_ARC_END = S_STRAIGHT + R_CURVE * math.radians(CURVE_DEG)   # ниже — прямой участок до донца
S_BOTTOM = 179.0                          # низ корпуса по хребту
WALL = 1.8
RF, RR = 4.0, 3.0                         # скругления передних и задних углов сечения
BODY_HW = 12.3                            # полуширина корпуса ниже шахты
TOP_HW = 10.0                             # полуширина верха (проходит между стенками верхнего ресивера)
LIP_END = MAG_X[0] + 32.0                 # губки — задние ≈32 мм верха (держат гильзу до плеча), дальше ступенька вниз
FRONT_TOP_Z = MAG_TOP_Z - 10.2            # верх стенок перед губками: открыт верхний патрон (пуля, плечо)
LIP_ROUND_Y, LIP_ROUND_Z, LIP_ROUND_R = 2.4, MAG_TOP_Z - 5.8, 4.8   # верхний патрон под левой губкой (ось, радиус гильзы)
LIP_GAP = 0.55                            # зазор низа губки до гильзы
U_HEAD = -L2 + WALL + 0.9                 # донце гильзы у задней стенки (зазор до скругления угла)
U_SHOULDER = U_HEAD + 36.53               # начало ската плеча гильзы (Ø 8.99) — ближе к центру изгиба
SHOULDER_D = 8.99
ROUND_D = 9.62
ROUND_STEP = 4.84                         # шаг рядов по донцам гильз
COL_W = 4.75                              # центры колонн от середины
MARK_NAME = "ГРАНЬ"
MARK_CAL = "5,56×45 · 30"
HEADSTAMP = ("ГР", "24")


# ---------- хребет ----------

def frame(s):
    """Точка хребта и оси сечения: P, T (вниз по магазину), U (вперёд)."""
    if s <= S_STRAIGHT:
        return Vector((CX, 0.0, Z0 - s)), Vector((0.0, 0.0, -1.0)), Vector((1.0, 0.0, 0.0))
    ph = (min(s, S_ARC_END) - S_STRAIGHT) / R_CURVE
    c = Vector((CX + R_CURVE, 0.0, Z0 - S_STRAIGHT))
    p = c + Vector((-math.cos(ph), 0.0, -math.sin(ph))) * R_CURVE
    t = Vector((math.sin(ph), 0.0, -math.cos(ph)))
    if s > S_ARC_END:                     # прямой низ по касательной к дуге
        p = p + t * (s - S_ARC_END)
    return p, t, Vector((math.cos(ph), 0.0, math.sin(ph)))


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


# ---------- текст рельефом ----------

FONT_FILE = "DejaVuSansMono.woff2"       # шрифт Blender (лицензия DejaVu/Bitstream Vera — свободная), контуры без перекрытий


def _font():
    f = bpy.data.fonts.get("MagFont")
    if f is None:
        import os
        path = os.path.join(os.path.dirname(bpy.app.binary_path), f"{bpy.app.version[0]}.{bpy.app.version[1]}",
                            "datafiles", "fonts", FONT_FILE)
        try:
            f = bpy.data.fonts.load(path)
            f.name = "MagFont"
        except Exception:
            f = None
    return f


def text_obj(text, size, half_depth, coll):
    """Замкнутая сетка текста в плоскости XY, выдавленная на ±half_depth (мм): контуры шрифта → своя заливка
    с отверстиями → выдавливание (заливка самого Blender у букв с внутренними контурами даёт Т-стыки)."""
    cu = bpy.data.curves.new("_txt", "FONT")
    cu.body = text
    f = _font()
    if f is not None:
        cu.font = f
    cu.size = size * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.fill_mode = "NONE"
    cu.resolution_u = 3
    o = bpy.data.objects.new("_txt", cu)
    coll.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    for vv in bm.verts:
        vv.co.z = -half_depth * MM
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=bm.edges[:])
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    vs = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=vs, vec=Vector((0.0, 0.0, 2.0 * half_depth * MM)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("_txtm", me)
    coll.objects.link(ob)
    return ob


def place_text(ob, center, normal, up, lift):
    """Плоскость текста — поперёк normal (наружу), вверх — up; center — точка поверхности (мм)."""
    n = Vector(normal).normalized()
    u = (Vector(up) - n * Vector(up).dot(n)).normalized()
    r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = (Vector(center) + n * lift) * MM
    ob.data.transform(m)
    return ob


def markings_on():
    import lib
    return getattr(lib, "MARKINGS_GEOMETRY", False)


def engrave(target, text, size, depth, center, normal, up, coll):
    t = text_obj(text, size, depth, coll)
    place_text(t, center, normal, up, 0.0)
    boolean(target, t)


def emboss(target, text, size, height, center, normal, up, coll, embed=0.2):
    t = text_obj(text, size, (height + embed) / 2.0, coll)
    place_text(t, center, normal, up, (height - embed) / 2.0)
    boolean(target, t, "UNION")


# ---------- корпус ----------

def body(C):
    brk = (0.0, 15.0, 19.0, 25.0, 74.0, 77.0, S_STRAIGHT)
    rings = [[pt(s, u, w) for u, w in section(-L2, L2, outer_hw(s), RF, RR)] for s in stations(-8.0, S_BOTTOM, 2.5, brk)]
    b = loft("Magazine_body", rings, C, "Polymer")
    rings = [[pt(s, u, w) for u, w in section(-L2 + WALL, L2 - WALL, inner_hw(s), RF - WALL + 0.4, RR - WALL + 0.4)]
             for s in stations(-20.0, S_BOTTOM + 12.0, 2.5, brk)]
    boolean(b, loft("cut_mag_cavity", rings, C))
    # верх: губки сзади на уровне MAG_TOP_Z, спереди опущен под гайку/ресивер (пули поднимаются по рампе)
    top = prism_xz("cut_mag_top", fillet([(-90.0, Z0), (LIP_END, Z0), (LIP_END + 4.0, FRONT_TOP_Z), (40.0, FRONT_TOP_Z), (40.0, 30.0),
                                          (-90.0, 30.0)], [0, 4.0, 4.0, 0, 0, 0], 8), -30.0, 30.0, C)
    boolean(b, top)
    # губки — продолжение стенок, загнуты внутрь над верхним патроном
    for s in (1, -1):
        yo = TOP_HW - WALL + 0.3                       # корень губки — в стенке
        cy0, cz0, rr = LIP_ROUND_Y * s, LIP_ROUND_Z, LIP_ROUND_R + LIP_GAP
        under = []                                     # низ губки по окружности патрона (с зазором), от носа к стенке
        for k in range(9):
            yy = 5.0 + (7.4 - 5.0) * k / 8
            under.append((yy, cz0 + math.sqrt(max(rr * rr - (yy - abs(cy0)) ** 2, 0.0))))
        prof = [(yo, Z0), (5.9, Z0), (5.0, Z0 - 0.7)] + under[1:] + [(yo, under[-1][1] - 0.6)]
        rad = [0, 0.6, 0.4] + [0] * (len(under) - 1) + [0]
        prof = fillet(prof, rad, 3)
        prof = [(y * s, z) for y, z in prof]
        if s < 0:
            prof = list(reversed(prof))
        lip = prism_yz("mag_lip", prof, MAG_X[0] + WALL - 0.3, LIP_END - 3.4, C, "Polymer")
        finish(lip, w=0.4, seg=2, angle=40)
        boolean(b, lip, "UNION")
        y0, y1 = (TOP_HW - 0.35, TOP_HW + 0.3) if s > 0 else (-TOP_HW - 0.3, -TOP_HW + 0.35)
        bead = prism_yz("mag_lip_bead", fillet([(y0, Z0 - 3.4), (y1, Z0 - 3.4), (y1, Z0 - 0.9), (y0, Z0 - 0.9)], [0, 0.25, 0.25, 0], 2),
                        MAG_X[0] + 1.2, LIP_END - 4.0, C, "Polymer")
        finish(bead, w=0.2, seg=2, angle=40)
        boolean(b, bead, "UNION")
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
    # маркировка: вымышленное название и калибр — гравировка 0.25 мм на левой стенке (ниже окна защёлки)
    if markings_on():
        engrave(b, MARK_NAME, 4.2, 0.25, (CX - 1.0, MAG_HALF_W, Z0 - 34.0), (0, 1, 0), (0, 0, 1), C)
        engrave(b, MARK_CAL, 2.4, 0.22, (CX - 1.0, MAG_HALF_W, Z0 - 41.6), (0, 1, 0), (0, 0, 1), C)
    # справа — калибр и номер партии (вымышленный)
    if markings_on():
        engrave(b, MARK_CAL, 2.4, 0.22, (CX + 1.0, -MAG_HALF_W, Z0 - 34.0), (0, -1, 0), (0, 0, 1), C)
        engrave(b, "ЛОТ 24-07", 2.0, 0.2, (CX + 1.0, -MAG_HALF_W, Z0 - 40.0), (0, -1, 0), (0, 0, 1), C)
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
    # ребро на спинке ниже шахты
    rib = loft("mag_spine", [[pt(s_, u, w) for u, w in ((-L2 - 0.8, -1.7), (-L2 + 0.6, -1.7), (-L2 + 0.6, 1.7), (-L2 - 0.8, 1.7))]
                             for s_ in stations(85.5, 170.0, 3.0)], C, "Polymer")
    boolean(b, rib, "UNION")
    # цифры остатка у окон (литые, на полу задней панели): сколько патронов, если в этом окне видна латунь
    for i, (s0, s1) in enumerate(rows if markings_on() else []):
        sc = 0.5 * (s0 + s1)
        cnt = window_count(sc)
        for sg in (1, -1):
            c = pt(sc, -11.75, 0.0)
            c = Vector((c.x, (hw - 0.9) * sg, c.z))
            emboss(b, str(cnt), 2.0, 0.22, c, (0, sg, 0), -frame(sc)[1], C)
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
                    yb = (hw - 1.25) * sg
                    yt = (hw - 0.9 + h) * sg
                    ring0 = [pt(sc + ds, u + du, 0.0) for ds, du in ((-base, -base), (-base, base), (base, base), (base, -base))]
                    ring1 = [pt(sc + ds, u + du, 0.0) for ds, du in ((-topw, -topw), (-topw, topw), (topw, topw), (topw, -topw))]
                    vb = [studs.verts.new(Vector((p.x, yb, p.z)) * MM) for p in ring0]
                    vt = [studs.verts.new(Vector((p.x, yt, p.z)) * MM) for p in ring1]
                    studs.faces.new(vt if sg > 0 else list(reversed(vt)))
                    studs.faces.new(list(reversed(vb)) if sg > 0 else vb)
                    for k in range(4):
                        j = (k + 1) % 4
                        studs.faces.new((vb[k], vb[j], vt[j], vt[k]))
    bmesh.ops.recalc_face_normals(studs, faces=studs.faces)
    me = bpy.data.meshes.new("mag_studs")
    studs.to_mesh(me); studs.free()
    so = bpy.data.objects.new("mag_studs", me)
    C.objects.link(so)
    so.data.materials.append(material("Polymer"))
    boolean(b, so, "UNION")
    seal(b)
    renormal(b)
    b["_fin"] = 1
    return b


def seal(o, max_sides=8):
    """Заделка мелких дыр, которые EXACT-булево иногда оставляет на вырожденных местах (контуры до max_sides рёбер)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bnd = [e for e in bm.edges if len(e.link_faces) == 1]
    if bnd:
        bmesh.ops.holes_fill(bm, edges=bnd, sides=max_sides)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(o.data)
    bm.free()


def window_count(sc):
    """Сколько патронов в магазине, когда нижний патрон стоит у окна на хребте sc."""
    pos = round_positions()
    for k, (s_, w_) in enumerate(pos):
        if s_ >= sc - 1.5:
            return k + 1
    return len(pos)


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
          for k, u in enumerate([9.0 + 3.6 * i for i in range(6)])]
    boolean(fp, join(gr, "cut_fp_grooves"))
    boolean(fp, lbox("cut_fp_lock", f, S_BOTTOM + 2.6, S_BOTTOM + 7.0, -27.5, -15.5, -5.6, 5.6, C))
    finish(fp, w=0.3, seg=2, angle=35)
    # литые надписи на нижней грани донца
    pb, tb, ub = frame(sm)
    bottom = S_BOTTOM + 5.6
    if markings_on():
        emboss(fp, MARK_NAME, 3.6, 0.3, f(bottom, 1.6, 0.0), tb, ub, C)
        emboss(fp, MARK_CAL, 2.1, 0.25, f(bottom, -4.4, 0.0), tb, ub, C)
        renormal(fp)
    fp["_fin"] = 1
    lock = lbox("Magazine_floorplate_lock", f, S_BOTTOM + 1.0, S_BOTTOM + 4.4, -26.6, -16.4, -4.7, 4.7, C, "Polymer")
    # рифление кнопки фиксатора
    for k in range(4):
        uu = -25.0 + k * 2.4
        boolean(lock, lbox(f"cut_lock_g{k}", f, S_BOTTOM + 4.0, S_BOTTOM + 5.0, uu - 0.45, uu + 0.45, -5.0, 5.0, C))
    finish(lock, w=0.35, seg=2, angle=35)
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
    finish(o, w=0.08, seg=2, angle=40)
    headstamp(o, C)
    o["_fin"] = 1
    return o


def headstamp(o, C):
    """Клеймо на донце гильзы: сверху и снизу от капсюля, гравировка 0.07 мм (только при MARKINGS_GEOMETRY)."""
    if not markings_on():
        return
    engrave(o, HEADSTAMP[0], 1.05, 0.07, (0.0, 0.0, 3.5), (-1, 0, 0), (0, 0, 1), C)
    engrave(o, HEADSTAMP[1], 1.05, 0.07, (0.0, 0.0, -3.5), (-1, 0, 0), (0, 0, 1), C)
    # торец гильзы плоский: кастомные нормали фаски после вырезания букв интерполируются криво — сбросить их,
    # резкость по углу заново, грани торца — плоские
    clear_custom_normals(o)
    auto_sharp(o, 35)
    for poly in o.data.polygons:
        if poly.center.x < 0.15 * MM:
            poly.use_smooth = False


def clear_custom_normals(o):
    if not o.data.has_custom_normals:
        return
    vl = bpy.context.view_layer
    prev = vl.objects.active
    for ob in vl.objects:
        ob.select_set(False)
    o.select_set(True)
    vl.objects.active = o
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    o.select_set(False)
    vl.objects.active = prev


def spent_case(C):
    prof = CASE[:-1] + [(44.70, 2.92), (44.0, 2.92), (40.0, 3.0), (38.0, 4.1), (3.5, 4.35), (3.5, 0.0)]
    o = lathe("Case_556", prof, C, "Brass", seg=40, cy=0.0, cz=0.0)
    # вмятина бойка на капсюле
    dent = lathe("cut_dent", [(-0.5, 0.0), (-0.5, 0.75), (0.25, 0.55), (0.45, 0.0)], C, None, seg=20, cy=0.0, cz=0.0)
    boolean(o, dent)
    finish(o, w=0.08, seg=2, angle=40)
    headstamp(o, C)
    o["_fin"] = 1
    return o


def row_step(s):
    """Шаг рядов по хребту. На дуге донца идут по наружной (задней) линии, плечи гильз — ближе к центру изгиба:
    шаг такой, чтобы ни донца (9.68 мм в колонне), ни плечи (Ø 8.99) соседей одной колонны не пересекались."""
    if s <= S_STRAIGHT or s >= S_ARC_END:
        return ROUND_STEP
    head = ROUND_STEP * R_CURVE / (R_CURVE - U_HEAD)
    shoulder = (SHOULDER_D + 0.15) / 2.0 * R_CURVE / (R_CURVE - U_SHOULDER)
    return max(head, shoulder)


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
            st = row_step(s_prev)
            s = max(s_prev + st, out[k - 2][0] + 2.0 * st)
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
    base["_fin"] = 1
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
    o["_fin"] = 1
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
