# «Осока» (ПЗРК по образцу 9К333 «Верба»): общие помощники построения (взяты из tools/smg03/lib.py — ИЗЛОМ-45, оттуда —
# из tools/ar15/lib.py) и перевод точек заводского снимка КБМ в мм модели. Все размеры в мм, в Blender — метры.
# Оси: +X — вперёд по трубе (к цели), +Z — вверх, −Y — правая сторона стрелка. Начало — на оси трубы у заднего торца
# трубы (без задней крышки). Масштаб и источники — asset-state.md и sources.md в папке модели.
import json
import math
import os
import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001
BORE_Z = 0.0
# надписи: таблички и литые слова — рельефом в геометрии (владелец 2026-11-05: «как у настоящего»), трафарет — на текстурах
MARKINGS_GEOMETRY = True
# скругление кромок (острых граней быть не должно): ширина фасок finish() × ROUND_K, профиль круглый
ROUND_K = 2.0
ROUND_PROFILE = 0.5

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- заводской снимок КБМ (левый бок, 2631 × 822, refs/web/kbm_ru/kbm_verba_left_IFF_2631x822.png) ----------
# длина с крышками 23…2601 пикс = 1710 мм (труба «Иглы» 9П39 — 1,71 м; у «Вербы» труба той же схемы) → 0.6633 мм/пикс
PX_FRONT = 23.0            # передний торец передней крышки
PX_REAR_CAP = 2601.0       # задний торец задней крышки
PX_TUBE_REAR = 2545.0      # задний торец трубы (под задней крышкой) — X = 0
LEN_TOTAL = 1710.0
S_PX = LEN_TOTAL / (PX_REAR_CAP - PX_FRONT)
# ось трубы на снимке чуть наклонена (задний конец выше на 0.25°): y = 414 − 0.0043·(x − 1700)
AXIS_Y0, AXIS_X0, AXIS_K = 414.0, 1700.0, 0.0043


def px_x(x):
    """Пиксель снимка по горизонтали → X модели, мм (снимок: перёд слева)."""
    return (PX_TUBE_REAR - x) * S_PX


def px_z(x, y):
    """Пиксель снимка → Z модели, мм (от оси трубы, вверх)."""
    return (AXIS_Y0 - AXIS_K * (x - AXIS_X0) - y) * S_PX


def px(x, y):
    return (px_x(x), px_z(x, y))


def px_len(n):
    return n * S_PX


def _area(pts):
    return 0.5 * sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))


def offset_poly(pts, d):
    """Сдвиг замкнутого контура внутрь на d мм (по биссектрисам с поправкой на угол). Углы контура заранее скруглены
    радиусом не меньше d (profiles.py, ROUND_MM) — сдвиг без самопересечений. d — число или список на каждую точку."""
    n = len(pts)
    ds = d if isinstance(d, (list, tuple)) else [d] * n
    ccw = _area(pts) > 0
    out = []
    for i in range(n):
        p0 = Vector((*pts[i - 1], 0)); p1 = Vector((*pts[i], 0)); p2 = Vector((*pts[(i + 1) % n], 0))
        a = (p1 - p0); b = (p2 - p1)
        if a.length < 1e-9 or b.length < 1e-9:
            out.append(pts[i]); continue
        a.normalize(); b.normalize()
        # внутренняя нормаль ребра: для обхода против часовой — влево
        na = Vector((-a.y, a.x, 0)) if ccw else Vector((a.y, -a.x, 0))
        nb = Vector((-b.y, b.x, 0)) if ccw else Vector((b.y, -b.x, 0))
        m = (na + nb)
        if m.length < 1e-6:
            m = na
        m.normalize()
        k = max(0.4, m.dot(na))
        q = p1 + m * (ds[i] / k)
        out.append((q.x, q.y))
    return out


def smooth_poly(pts, step=0.7, k=3):
    """Равномерная перевыборка замкнутого контура через step мм и сглаживание скользящим средним (±k точек): убирает
    зубцы обводки мельче шага, иначе сдвиг внутрь на радиус скругления их перехлёстывает."""
    n = len(pts)
    seg = []
    tot = 0.0
    for i in range(n):
        a = pts[i]; b = pts[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        seg.append((a, b, L, tot)); tot += L
    m = max(8, int(tot / step))
    out = []
    j = 0
    for i in range(m):
        s_ = tot * i / m
        while j < len(seg) - 1 and seg[j][3] + seg[j][2] < s_:
            j += 1
        a, b, L, t0 = seg[j]
        t = 0.0 if L < 1e-9 else (s_ - t0) / L
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if k > 0:
        out = [(sum(out[(i + d) % m][0] for d in range(-k, k + 1)) / (2 * k + 1),
                sum(out[(i + d) % m][1] for d in range(-k, k + 1)) / (2 * k + 1)) for i in range(m)]
    return out


def rounded_prism(name, pts, y0, y1, r, coll, mat=None, seg=6, tri_caps=False, r_fn=None, smooth=(0.7, 3)):
    """Призма по контуру (XZ), выдавленная по Y, с круглыми кромками радиуса r по всему контуру с обеих сторон —
    своей сеткой из колец (сдвинутые контуры), без модификатора фаски: чистые четырёхугольники, булевы после неё
    работают (фаска без зажима на многоугольной боковине ломала EXACT). r_fn(x, z) — радиус кромки по месту контура
    (меняться должен плавно и не больше скругления угла контура в плоскости); без него — r везде."""
    import bmesh as _bm
    # smooth — (шаг перевыборки, полуокно скользящего среднего): обводку со снимка сглаживаем; контур с задуманным
    # рельефом (рёбра затыльника) — только перевыборка, k = 0
    pts = smooth_poly(pts, smooth[0], smooth[1])
    rs = [r_fn(x, z) for x, z in pts] if r_fn is not None else [r] * len(pts)
    rings = []
    angs = [math.pi / 2 * k / seg for k in range(seg + 1)]
    # от боковины −Y (сдвиг r) к середине и к боковине +Y; кольцо — (Y по точкам, сдвиг по точкам)
    # y0 + r·(1 − sin t), а не (y0 + r) − r·sin t: на боковине (t = 90°) ровно y0 у каждой точки — при разных r
    # ошибки округления делали крышку неплоской на 1e-15, и точное булево потом пропускало буквы гравировки
    for t in reversed(angs):
        k = 1.0 - math.sin(t) if t < math.pi / 2 else 0.0
        rings.append(([y0 + ri * k for ri in rs], [ri * (1 - math.cos(t)) for ri in rs]))
    for t in angs:
        if t == 0 and r_fn is None and abs((y1 - r) - (y0 + r)) < 1e-6:
            continue
        k = 1.0 - math.sin(t) if t < math.pi / 2 else 0.0
        rings.append(([y1 - ri * k for ri in rs], [ri * (1 - math.cos(t)) for ri in rs]))
    me = bpy.data.meshes.new(name)
    bm = _bm.new()
    vr = []
    for ys, ds in rings:
        q = offset_poly(pts, ds) if max(ds) > 1e-9 else pts
        vr.append([bm.verts.new(v(x, y, z)) for (x, z), y in zip(q, ys)])
    n = len(pts)
    for r0, r1 in zip(vr, vr[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    caps = [bm.faces.new(vr[0]), bm.faces.new(list(reversed(vr[-1])))]
    # вогнутые крышки — сразу на треугольники (ушами по плоскому контуру): после объединений многоугольник крышки
    # разбивался неверно и натягивал «плёнку» поперёк окна петли (проверка v02)
    if tri_caps:
        _bm.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = _obj(name, me, coll, mat)
    # боковины плоские — жёсткие кромки по ним не нужны: всё гладкое, плоскость боковины держит Weighted Normal
    return o


def _nonmanifold(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n


def finish_small(o, w=0.5, seg=2, angle=30.0, exclude=None):
    """Второе, мелкое скругление — кромки вырезов, пазов, рёбер (w — мм, без ROUND_K) без зажима фаски (зажим в
    Blender общий на деталь и сводит фаску к долям миллиметра). Если сетка после фаски незамкнута или разлетелась —
    повтор с меньшей шириной; в крайнем случае — с зажимом."""
    o["_fin"] = 1
    clean(o)
    keep = o.data.copy()
    before = _bbox(o)
    nm0 = _nonmanifold(o)
    for ww, clamp in ((w, False), (w * 0.6, False), (w * 0.35, False), (w, True)):
        old = o.data
        o.data = keep.copy()
        if old is not keep and old.users == 0:
            bpy.data.meshes.remove(old)
        bevel(o, ww, seg, angle, harden=False, clamp=clamp, exclude=exclude)
        weighted(o)
        apply_all(o)
        _drop_loose(o)
        after = _bbox(o)
        ok = before and after and (after[0] - before[0]).length < 0.0005 and (after[1] - before[1]).length < 0.0005
        if ok and _nonmanifold(o) <= nm0:
            if ww != w or clamp:
                print("SMALL_RETRY", o.name, round(ww, 2), "зажим" if clamp else "")
            bpy.data.meshes.remove(keep)
            grid_split(o)
            weighted(o)
            apply_all(o)
            return o
        print("SMALL_FAIL", o.name, round(ww, 2), "nm", _nonmanifold(o))
    old = o.data
    o.data = keep
    bpy.data.meshes.remove(old)
    print("SMALL_FALLBACK", o.name)
    return o


def v(x, y, z):
    return Vector((x * MM, y * MM, z * MM))


# ---------- коллекции и материалы ----------

def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


_MAT_COLORS = {
    "Alu_anodized": ((0.030, 0.030, 0.032), 0.45, 0.6),     # ресиверы, цевьё, рукоятка заряжания
    "Steel_black": ((0.035, 0.036, 0.038), 0.55, 0.85),      # ствол, оси, мелкие стальные детали
    "Steel_nitride": ((0.045, 0.045, 0.048), 0.40, 0.9),     # затворная группа
    "Steel_bare": ((0.30, 0.30, 0.31), 0.35, 1.0),           # трущиеся места, ударник
    "Polymer": ((0.035, 0.034, 0.033), 0.65, 0.0),           # приклад, рукоять, магазин
    "Rubber": ((0.02, 0.02, 0.02), 0.85, 0.0),
    "Spring_steel": ((0.12, 0.12, 0.13), 0.4, 1.0),
    "Brass": ((0.62, 0.42, 0.16), 0.3, 1.0),
    "Bullet_jacket": ((0.55, 0.30, 0.18), 0.3, 1.0),
    "Glass": ((0.8, 0.85, 0.9), 0.05, 0.0),
    # «Осока»: оливковая краска по стеклопластику трубы и литью пускового механизма, чёрная резина, латунь табличек
    "Paint_olive": ((0.13, 0.15, 0.06), 0.62, 0.0),
    "Paint_olive_cast": ((0.12, 0.14, 0.055), 0.55, 0.0),
    "Rubber_black": ((0.018, 0.018, 0.02), 0.8, 0.0),
    "Plastic_black": ((0.025, 0.025, 0.027), 0.5, 0.0),
    "Plate_alu": ((0.55, 0.55, 0.53), 0.35, 1.0),
    "Plastic_yellow": ((0.75, 0.55, 0.02), 0.45, 0.0),
    "Webbing_grey": ((0.32, 0.33, 0.33), 0.9, 0.0),
    "Lens": ((0.02, 0.03, 0.04), 0.05, 0.0),
    "Indicator_cream": ((0.75, 0.68, 0.55), 0.45, 0.0),
    "Missile_grey": ((0.42, 0.45, 0.40), 0.5, 0.0),
    "Missile_band": ((0.03, 0.03, 0.03), 0.6, 0.0),
    "Fin_steel": ((0.40, 0.40, 0.42), 0.4, 1.0),
}


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        col, rough, metal = _MAT_COLORS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0))
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*col, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*col, 1.0)
    return m


# ---------- 2D-профили ----------

def fillet(points, radii, seg=6):
    """Скругляет углы замкнутого многоугольника. radii — число или список на каждый угол (0 — острый)."""
    n = len(points)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p0 = Vector(points[i - 1]); p1 = Vector(points[i]); p2 = Vector(points[(i + 1) % n])
        r = radii[i]
        if r <= 0:
            out.append((p1.x, p1.y)); continue
        a = (p0 - p1); b = (p2 - p1)
        la, lb = a.length, b.length
        if la < 1e-9 or lb < 1e-9:
            out.append((p1.x, p1.y)); continue
        a.normalize(); b.normalize()
        ang = a.angle(b)
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            out.append((p1.x, p1.y)); continue
        t = r / math.tan(ang / 2)
        t = min(t, la * 0.49, lb * 0.49)
        r_eff = t * math.tan(ang / 2)
        s = p1 + a * t; e = p1 + b * t
        bis = (a + b).normalized()
        c = p1 + bis * (r_eff / math.sin(ang / 2))
        v0 = s - c; v1 = e - c
        a0 = math.atan2(v0.y, v0.x); a1 = math.atan2(v1.y, v1.x)
        da = a1 - a0
        while da > math.pi: da -= 2 * math.pi
        while da < -math.pi: da += 2 * math.pi
        for k in range(seg + 1):
            aa = a0 + da * k / seg
            out.append((c.x + math.cos(aa) * r_eff, c.y + math.sin(aa) * r_eff))
    return out


def arc_pts(cx, cy, r, a0, a1, seg):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg))) for k in range(seg + 1)]


# ---------- сетки ----------

def pchip(points):
    """Монотонная кубическая интерполяция (Фрич — Карлсон) по точкам (z, значение)."""
    pts = sorted(points)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        if x <= xs[0]:
            return ys[0] + m[0] * (x - xs[0])
        if x >= xs[-1]:
            return ys[-1] + m[-1] * (x - xs[-1])
        for i in range(n - 1):
            if xs[i] <= x <= xs[i + 1]:
                t = (x - xs[i]) / h[i]
                t2, t3 = t * t, t * t * t
                return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1]
                        + (t3 - t2) * h[i] * m[i + 1])
    return f


def _obj(name, me, coll, mat):
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for mm in mat:
                o.data.materials.append(material(mm) if isinstance(mm, str) else mm)
        else:
            o.data.materials.append(material(mat) if isinstance(mat, str) else mat)
    return o


def prism_xz(name, pts, y0, y1, coll, mat=None, smooth=False):
    """Профиль в плоскости XZ (мм), выдавленный по Y от y0 до y1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x, y0, z)) for x, z in pts]
    b = [bm.verts.new(v(x, y1, z)) for x, z in pts]
    n = len(pts)
    bm.faces.new(list(reversed(a)) if y1 > y0 else a)
    bm.faces.new(b if y1 > y0 else list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def prism_xy(name, pts, z0, z1, coll, mat=None):
    """Профиль в плоскости XY (вид сверху), выдавленный по Z."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x, y, z0)) for x, y in pts]
    b = [bm.verts.new(v(x, y, z1)) for x, y in pts]
    n = len(pts)
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def prism_yz(name, pts, x0, x1, coll, mat=None):
    """Профиль в плоскости YZ (поперечное сечение), выдавленный по X."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    a = [bm.verts.new(v(x0, y, z)) for y, z in pts]
    b = [bm.verts.new(v(x1, y, z)) for y, z in pts]
    n = len(pts)
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def loft_yz(name, sections, coll, mat=None, cap=True, smooth=True):
    """Лофт по X: sections = [(x, [(y,z)...]), ...] — одинаковое число точек в каждом сечении."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, pts in sections:
        rings.append([bm.verts.new(v(x, y, z)) for y, z in pts])
    n = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if cap:
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def lathe(name, prof, coll, mat=None, seg=64, cy=0.0, cz=BORE_Z, smooth=True, closed=True):
    """Тело вращения вокруг оси, параллельной X, через (cy, cz). prof = [(x, r), ...] по контуру.
    closed=True — контур замкнут (последняя точка соединяется с первой)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, r in prof:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            ring.append(bm.verts.new(v(x, cy + r * math.cos(a), cz + r * math.sin(a))))
        rings.append(ring)
    m = len(rings)
    pairs = list(zip(range(m - 1), range(1, m)))
    # оба конца профиля на оси — замыкать по оси не нужно (грани нулевой площади, сверка v04 Д23)
    if closed and not (abs(prof[0][1]) < 1e-9 and abs(prof[-1][1]) < 1e-9):
        pairs.append((m - 1, 0))
    for i0, i1 in pairs:
        r0, r1 = rings[i0], rings[i1]
        for k in range(seg):
            j = (k + 1) % seg
            q = (r0[k], r0[j], r1[j], r1[k])
            if len(set(q)) == 4:
                try:
                    bm.faces.new(q)
                except ValueError:
                    pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    # точки профиля на оси дают грани нулевой площади и ребро вдоль оси (сверка v04 Д23) — убрать
    bmesh.ops.dissolve_degenerate(bm, dist=1e-8, edges=bm.edges)
    wire = [e for e in bm.edges if not e.link_faces]
    if wire:
        bmesh.ops.delete(bm, geom=wire, context="EDGES")
    loose = [vv for vv in bm.verts if not vv.link_edges]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return _obj(name, me, coll, mat)


def cyl(name, x0, x1, r, coll, mat=None, seg=32, cy=0.0, cz=BORE_Z, axis="X", ch=0.0):
    """Цилиндр с фасками ch на торцах. axis — X, Y или Z; для Y/Z x0..x1 — координаты по этой оси, (cy,cz) — центр в двух других."""
    prof = [(x0, 0.0), (x0, r - ch), (x0 + ch, r), (x1 - ch, r), (x1, r - ch), (x1, 0.0)] if ch > 0 else [(x0, 0.0), (x0, r), (x1, r), (x1, 0.0)]
    o = lathe(name, prof, coll, mat, seg, 0.0, 0.0, smooth=True, closed=True)
    if axis == "X":
        o.location = v(0, cy, cz)
    elif axis == "Y":
        o.rotation_euler = (0, 0, math.pi / 2)
        o.location = v(cy, 0, cz)
    elif axis == "Z":
        o.rotation_euler = (0, -math.pi / 2, 0)
        o.location = v(cy, cz, 0)
    apply_transform(o)
    auto_sharp(o, 35)
    return o


def box(name, x0, x1, y0, y1, z0, z1, coll, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vv in bm.verts:
        vv.co.x = (x0 if vv.co.x < 0 else x1) * MM
        vv.co.y = (y0 if vv.co.y < 0 else y1) * MM
        vv.co.z = (z0 if vv.co.z < 0 else z1) * MM
    bm.to_mesh(me); bm.free()
    return _obj(name, me, coll, mat)


def apply_transform(o):
    mw = o.matrix_world.copy() if o.parent is None else o.matrix_basis.copy()
    o.data.transform(o.matrix_basis)
    o.matrix_basis = Matrix.Identity(4)


def auto_sharp(o, deg=35):
    """Плавное затенение с острыми рёбрами по углу (без модификатора)."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0) < math.radians(deg)
        else:
            e.smooth = False
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me); bm.free()


# ---------- булевы и фаски ----------

def boolean(target, cutter, op="DIFFERENCE", remove=True, solver="EXACT", self_x=False, hole_tolerant=False):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.object = cutter
    m.solver = solver
    if solver == "EXACT" and self_x:
        m.use_self = True
    if solver == "EXACT" and hole_tolerant:
        m.use_hole_tolerant = True
    apply_all(target)
    _drop_empty_slots(target)
    clean(target, 0.002)
    if remove:
        me = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)


def _dupfaces(o):
    seen = set(); n = 0
    for f in o.data.polygons:
        k = tuple(sorted(f.vertices))
        if k in seen:
            n += 1
        seen.add(k)
    return n


def boolean_safe(target, cutter, op="DIFFERENCE", name=""):
    """Булево с проверкой: открытых / многогранных рёбер и дублей граней не прибавилось — иначе откат и повтор со сдвигом
    резца на сотые миллиметра, затем точное «с допуском к дырам», затем быстрое. Точное булево Blender на большом корпусе
    изредка сбоит от запуска к запуску (04.11: стык рукояти с коробкой — тысяча рёбер на три грани).
    Возвращает номер удавшейся попытки (−1 — ни одна)."""
    from mathutils import Matrix as _M, Vector as _V
    keep = target.data.copy()
    nm0, d0 = _nonmanifold(target), _dupfaces(target)
    tries = [((0, 0, 0), "EXACT", False), ((0.011, 0.007, 0.013), "EXACT", False), ((-0.013, 0.009, -0.007), "EXACT", False),
             ((0.017, -0.011, 0.005), "EXACT", False), ((0, 0, 0), "EXACT", True), ((0.009, 0.013, -0.011), "EXACT", True),
             ((0, 0, 0), "FLOAT", False)]
    best = None
    used = -1
    for k, (sh, solver, tol) in enumerate(tries):
        if k:
            old = target.data
            target.data = keep.copy()
            if old.users == 0:
                bpy.data.meshes.remove(old)
        c2 = cutter.copy(); c2.data = cutter.data.copy()
        for coll in cutter.users_collection:
            coll.objects.link(c2)
        c2.data.transform(_M.Translation(_V(sh) * MM))
        boolean(target, c2, op=op, solver=solver, hole_tolerant=tol)
        nm, d = _nonmanifold(target), _dupfaces(target)
        if nm <= nm0 and d <= d0:
            used = k
            break
        print("BOOL_RETRY", name or cutter.name, k, nm - nm0, d - d0)
        if best is None or nm + d < best[0]:
            if best is not None and best[1].users == 0:
                bpy.data.meshes.remove(best[1])
            best = (nm + d, target.data.copy())
    else:
        print("BOOL_FAIL", name or cutter.name)
        old = target.data
        target.data = best[1]
        if old.users == 0:
            bpy.data.meshes.remove(old)
        best = None
    if best is not None and best[1].users == 0:
        bpy.data.meshes.remove(best[1])
    if keep.users == 0:
        bpy.data.meshes.remove(keep)
    me = cutter.data
    bpy.data.objects.remove(cutter, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)
    # номер удавшейся попытки (0 — с первого раза, 6 — быстрым решателем), −1 — не удалось
    return used


def _drop_empty_slots(o):
    """Грани выреза приходят с пустым слотом материала (у резака его нет) — отдаём их материалу детали."""
    me = o.data
    mats = list(me.materials)
    if not any(m is None for m in mats):
        return
    keep = [i for i, m in enumerate(mats) if m is not None]
    if not keep:
        return
    remap = {old: new for new, old in enumerate(keep)}
    idx = [remap.get(p.material_index, 0) for p in me.polygons]
    new = [mats[i] for i in keep]
    me.materials.clear()
    for m in new:
        me.materials.append(m)
    for p, i in zip(me.polygons, idx):
        p.material_index = i


def apply_all(o):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
    old = o.data
    o.modifiers.clear()
    o.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _bevel_weights(o, angle, exclude):
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    sel = []
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0) < math.radians(angle):
            continue
        if any(exclude(f.calc_center_median() * (1.0 / MM), f.normal) for f in e.link_faces):
            continue
        sel.append(e.index)
    bm.free()
    attr = me.attributes.get("bevel_weight_edge") or me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for i in range(len(me.edges)):
        attr.data[i].value = 0.0
    for i in sel:
        attr.data[i].value = 1.0


def bevel(o, w=0.5, seg=2, angle=30.0, harden=True, profile=ROUND_PROFILE, clamp=True, miter="MITER_ARC", exclude=None):
    """Фаска по углу. w — мм. Не применяет: применить через apply_all или finish()."""
    m = o.modifiers.new("bevel", "BEVEL")
    m.width = w * MM
    m.segments = seg
    if exclude is None:
        m.limit_method = "ANGLE"
    else:
        _bevel_weights(o, angle, exclude)
        m.limit_method = "WEIGHT"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.harden_normals = harden
    m.use_clamp_overlap = clamp
    m.miter_outer = miter
    for p in o.data.polygons:
        p.use_smooth = True
    return m


def bevel_edges(o, pick, w=4.0, seg=6, profile=0.5, clamp=False, where=None):
    """Скругление выбранных рёбер радиусом ~w мм: pick(n1, n2) по нормалям двух граней ребра,
    where(середина ребра в мм) — дополнительный отбор по месту; применяется сразу."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.normal_update()
    sel = set()
    for e in bm.edges:
        if len(e.link_faces) == 2:
            n1, n2 = e.link_faces[0].normal, e.link_faces[1].normal
            if not (pick(n1, n2) or pick(n2, n1)):
                continue
            if where is not None and not where((e.verts[0].co + e.verts[1].co) * (0.5 / MM)):
                continue
            sel.add(e.index)
    bm.free()
    attr = me.attributes.get("bevel_weight_edge") or me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    for i in range(len(me.edges)):
        attr.data[i].value = 1.0 if i in sel else 0.0
    m = o.modifiers.new("bevel_w", "BEVEL")
    m.limit_method = "WEIGHT"
    m.width = w * MM
    m.segments = seg
    m.profile = profile
    m.use_clamp_overlap = clamp          # ограничение по соседним коротким рёбрам скруглений сводило ширину почти к нулю
    m.miter_outer = "MITER_ARC"
    m.harden_normals = False
    apply_all(o)
    a = o.data.attributes.get("bevel_weight_edge")
    if a is not None:
        o.data.attributes.remove(a)
    return len(sel)


def renormal(o):
    """Нормали заново по площадям граней — после булевых по уже готовой (с фаской) сетке: клейма, выштамповка.
    Рёбра круче 40° (буквы, стенки углублений) — жёсткие, полосы фасок остаются гладкими."""
    auto_sharp(o, 40)
    weighted(o)
    apply_all(o)


def grid_split(o, step=12.0, min_verts=12):
    """Многоугольники после булевых (боковины с вырезами-«дырками», соединёнными с краем разрезом) Blender при показе
    бьёт на треугольники с перехлёстом — вырез затягивается, на ровной грани чёрный клин или светлый конус (сверка v04
    Д4, Н1). Режем их невидимой сеткой плоскостей X, Y, Z (шаг — не больше пятой части детали): форма та же, куски
    мелкие. Новые рёбра — гладкие (иначе скругления выходили гранёными полосами — сверка v04b Н3)."""
    from mathutils import Vector as _V
    bm = bmesh.new(); bm.from_mesh(o.data)
    nm0 = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    big = [f for f in bm.faces if len(f.verts) > min_verts]
    if not big:
        bm.free()
        return
    orig = set(bm.edges)
    dims = [max(vv.co[k] for vv in bm.verts) - min(vv.co[k] for vv in bm.verts) for k in range(3)]
    st = min(step * MM, max(dims) / 5.0)
    planes = []
    for k in range(3):
        cs = [vv.co[k] for f in big for vv in f.verts]
        c = math.floor(min(cs) / st) * st + st / 2
        while c < max(cs):
            co = _V((0, 0, 0)); no = _V((0, 0, 0))
            co[k] = c; no[k] = 1.0
            planes.append((co, no))
            c += st
    for co, no in planes:
        faces = [f for f in bm.faces if len(f.verts) > min_verts]
        if not faces:
            break
        geom = list({e for f in faces for e in f.edges}) + faces
        # допуск 0.02 мм: плоскость Z −30.0 шла в 0.01 мм от вершины конца ломаной знака — щепка, после скругления
        # кромок знака тёмный «шип» (обе стороны шахты)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=0.02 * MM, plane_co=co, plane_no=no)
    # рёбра-нулёвки от допуска 0.02 мм (вершины ближе 1 мкм) — схлопнуть
    new = [e for e in bm.edges if e not in orig]
    bmesh.ops.dissolve_degenerate(bm, dist=0.002 * MM, edges=new)
    for e in bm.edges:
        if e not in orig:
            e.smooth = True
    nm1 = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    if nm1 <= nm0:
        bm.to_mesh(o.data)
    else:
        print("GRID_SPLIT_SKIP", o.name, nm0, nm1)
    bm.free()


def grid_split_local(o, center_mm, radius_mm, axes, step=1.2):
    """Мелкая нарезка невидимой сеткой только вокруг знака: кольцо с ломаной оставляло многоугольники с вырезами
    внутри (диск в кольце, борт вокруг кольца) — при показе треугольники с перехлёстом давали клин наружу кольца и
    «клюв» у конца ломаной (владелец 05.11, снимок 10). axes — оси в плоскости знака (поперёк нормали)."""
    from mathutils import Vector as _V
    bm = bmesh.new(); bm.from_mesh(o.data)
    nm0 = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    c = _V(center_mm) * MM
    rad = radius_mm * MM
    orig = set(bm.edges)

    def near(f):
        return len(f.verts) > 4 and any((vv.co - c).length < rad for vv in f.verts)
    st = step * MM
    for k in axes:
        t = c[k] - rad + st * 0.37
        while t < c[k] + rad:
            faces = [f for f in bm.faces if near(f)]
            if not faces:
                break
            co = _V((0, 0, 0)); no = _V((0, 0, 0))
            co[k] = t; no[k] = 1.0
            geom = list({e for f in faces for e in f.edges}) + faces
            # допуск 0.02 мм: плоскость на волосок от вершины фаски резала рядом — вывернутая щепка 0.003 мм²,
            # тёмный «шип» у конца ломаной знака
            bmesh.ops.bisect_plane(bm, geom=geom, dist=0.02 * MM, plane_co=co, plane_no=no)
            t += st
    new = [e for e in bm.edges if e not in orig]
    bmesh.ops.dissolve_degenerate(bm, dist=0.002 * MM, edges=new)
    for e in bm.edges:
        if e not in orig:
            e.smooth = True
    nm1 = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    big = sum(1 for f in bm.faces if len(f.verts) > 12 and any((vv.co - c).length < rad for vv in f.verts))
    if nm1 <= nm0:
        bm.to_mesh(o.data)
        print("LOCAL_SPLIT", o.name, [round(q, 1) for q in center_mm], "больших граней", big)
    else:
        print("LOCAL_SPLIT_SKIP", o.name, nm0, nm1)
    bm.free()


def hex_socket(name, r, depth, ch, coll, rot=0.0):
    """Резец гнезда под шестигранник в своих осях: ось +Z, поверхность головки — z = 0, гнездо вниз на depth, на входе
    фаска ch под 45° (шестигранник шире на ch). Общая мелкая фаска по краю гнезда, рассечённому веером граней головки,
    рвала край зубчиками (сверка v05 Н4) — край гнезда из фаски не скругляют, его даёт сам резец."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for z, rr in ((1.5, r + ch + 1.5), (0.0, r + ch), (-ch, r), (-depth, r)):
        rings.append([bm.verts.new(v(rr * math.cos(math.pi / 3 * k + rot), rr * math.sin(math.pi / 3 * k + rot), z))
                      for k in range(6)])
    for a, b in zip(rings, rings[1:]):
        for k in range(6):
            j = (k + 1) % 6
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def mark_sharp(o, angle_deg, where=None):
    """Острыми — рёбра с углом между гранями больше angle_deg (where(середина ребра, мм) — где): плоские грани у
    фаски остаются плоскими при любой нарезке. Иначе после мелкой нарезки нормали мелких плоских кусков у кромки тянулись
    к фаске — светлые и тёмные пятна-треугольники (кольцо целика, знак). Для мест с гравировкой без фаски не годится:
    стенки букв смотрят ребром и пропадают."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.normal_update()
    lim = math.radians(angle_deg)
    n = 0
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        if e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) <= lim:
            continue
        if where is not None and not where((e.verts[0].co + e.verts[1].co) * (0.5 / MM)):
            continue
        e.smooth = False
        n += 1
    bm.to_mesh(o.data); bm.free()
    return n


def weighted(o):
    m = o.modifiers.new("wn", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    m.weight = 50
    return m


def clean(o, dist=0.002):
    """Сварка совпавших вершин и растворение вырожденной геометрии после булевых (dist — мм)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist * MM)
    bmesh.ops.dissolve_degenerate(bm, dist=dist * MM, edges=bm.edges)
    bm.to_mesh(o.data); bm.free()


def _drop_loose(o):
    """Фаска иногда оставляет вершины без граней (в начале координат) — убираем, чтобы не ломать габарит."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.to_mesh(o.data)
    bm.free()


def _bbox(o):
    xs = [v.co for v in o.data.vertices]
    if not xs:
        return None
    return (Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs))),
            Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs))))


def _spots(o, lo, hi):
    """Где фаска разнесла сетку: вершины на месте у граней с улетевшими вершинами (мм, |y| > 15)."""
    bmd = bmesh.new(); bmd.from_mesh(o.data)
    spots = set()
    for vv in bmd.verts:
        if any(c < l - 0.002 or c > h + 0.002 for c, l, h in zip(vv.co, lo, hi)):
            for f in vv.link_faces:
                for q in f.verts:
                    if all(l - 1e-5 <= c <= h + 1e-5 for c, l, h in zip(q.co, lo, hi)):
                        spots.add(tuple(round(c / MM) for c in q.co))
    bmd.free()
    return sorted(spots)[:16]


def finish(o, w=0.5, seg=2, angle=30.0, apply=True, exclude=None, tri_first=False):
    """Общая фаска по углу; если на вырожденных рёбрах фаска разносит сетку — повтор с меньшей шириной,
    в крайнем случае сетка без фаски с жёсткими рёбрами по углу."""
    o["_fin"] = 1
    w = w * ROUND_K
    seg = max(seg, 4 if w >= 1.0 else 3)
    clean(o)
    before = _bbox(o)
    keep = o.data.copy()
    if not apply:
        bevel(o, w, seg, angle, exclude=exclude)
        weighted(o)
        bpy.data.meshes.remove(keep)
        return o
    tries = ((w, False, "MITER_ARC"), (w, False, "MITER_SHARP"), (w, True, "MITER_SHARP"),
             (w * 0.6, True, "MITER_SHARP"), (w * 0.35, True, "MITER_SHARP"))
    # tri_first — сразу с разбивкой больших многоугольников: широкая фаска вокруг отверстия в торце (рукоять) делала
    # большую грань неплоской — радиальные полосы в затенении
    for k, (ww, tri, mit) in enumerate(tries[2:] if tri_first else tries):
        if k:
            old = o.data
            o.data = keep.copy()
            bpy.data.meshes.remove(old)
        if tri:
            # большие многоугольники боковин после булевых фаска разносит — режем их на треугольники
            bm = bmesh.new(); bm.from_mesh(o.data)
            big = [f for f in bm.faces if len(f.verts) > 12]
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
            bm.to_mesh(o.data); bm.free()
            bevel(o, ww, seg, angle, miter=mit, exclude=exclude)
            apply_all(o)
            # после фаски плоские треугольники снова сливаем в многоугольники — иначе тонкие клинья портят затенение
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.05), verts=bm.verts, edges=bm.edges,
                                     delimit={"NORMAL"})
            bm.to_mesh(o.data); bm.free()
            for p in o.data.polygons:
                p.use_smooth = True
        else:
            bevel(o, ww, seg, angle, miter=mit, exclude=exclude)
        weighted(o)
        apply_all(o)
        _drop_loose(o)
        after = _bbox(o)
        if not (before and after and ((after[0] - before[0]).length > 0.002 or (after[1] - before[1]).length > 0.002)):
            if k:
                print("BEVEL_RETRY", o.name, round(ww, 2), "треугольники" if tri else "")
            bpy.data.meshes.remove(keep)
            return o
        print("BEVEL_FAIL", o.name, round(ww, 2), "места:", _spots(o, *before))
    old = o.data
    o.data = keep
    bpy.data.meshes.remove(old)
    for p in o.data.polygons:
        p.use_smooth = True
    auto_sharp(o, angle)
    print("BEVEL_FALLBACK", o.name)
    return o


def join(objs, name):
    base = objs[0]
    for o in objs[1:]:
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    base.data.transform(base.matrix_world); base.matrix_world = Matrix.Identity(4)
    bm = bmesh.new()
    mats = []
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material not in mats:
                mats.append(s.material)
    for o in objs:
        tmp = bmesh.new(); tmp.from_mesh(o.data)
        remap = {}
        for i, s in enumerate(o.material_slots):
            remap[i] = mats.index(s.material) if s.material in mats else 0
        for f in tmp.faces:
            f.material_index = remap.get(f.material_index, 0)
        me_tmp = bpy.data.meshes.new("tmp"); tmp.to_mesh(me_tmp); tmp.free()
        bm.from_mesh(me_tmp)
        bpy.data.meshes.remove(me_tmp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    coll = base.users_collection[0]
    for o in objs:
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    for m in mats:
        me.materials.append(m)
    return o


# ---------- иерархия ----------

def empty(name, loc_mm, coll, parent=None, size=0.01, kind="PLAIN_AXES"):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    coll.objects.link(e)
    e.location = v(*loc_mm)
    bpy.context.view_layer.update()
    if parent is not None:
        set_parent(e, parent)
    return e


def set_parent(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def set_origin(o, loc_mm):
    """Переносит начало координат объекта в точку (мм, мир) без смещения геометрии."""
    p = v(*loc_mm)
    mw = o.matrix_world.copy()
    local = mw.inverted() @ p
    o.data.transform(Matrix.Translation(-local))
    o.matrix_world = mw @ Matrix.Translation(local)


def tris(o):
    me = o.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def hug_tube(o):
    """Вычесть из детали объём трубы: канал под ракету R 38.6 до хомута ГСН, дальше — R 45 (внутри хомута). Детали,
    прилегающие к трубе снаружи, иначе проходили сквозь стенку в ракету."""
    import dims as D
    rr = D.TUBE_R + 0.12
    x_c = D.COLLAR[0] + 12.0
    prof = [(-60.0, 0.0), (-60.0, rr), (x_c, rr), (x_c, 45.1), (1700.0, 45.1), (1700.0, 0.0)]
    c = lathe("_hug", prof, o.users_collection[0], None, seg=160)
    return boolean_safe(o, c, name="hug_" + o.name)
