"""Общие построители геометрии модулей общежития (Blender 5, bmesh).

Все размеры — метры. Ось X — вдоль стены, Y — поперёк, Z — вверх.
Детали собираются в bmesh по частям и превращаются в один объект на материал;
фаски — модификатором Bevel (по углу или по весам), чтобы владелец мог их менять.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

V = Vector


# ---------------------------------------------------------------- материалы и коллекции

def material(name: str, color: tuple, rough: float = 0.8, metal: float = 0.0, alpha: float = 1.0) -> bpy.types.Material:
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (color[0], color[1], color[2], alpha)
    m.roughness = rough
    m.metallic = metal
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    nodes = m.node_tree.nodes if m.node_tree else None
    if nodes is not None:
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
            bsdf.inputs["Roughness"].default_value = rough
            bsdf.inputs["Metallic"].default_value = metal
            if alpha < 1.0:
                bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            pass
    return m


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    host = parent or bpy.context.scene.collection
    if c.name not in host.children:
        host.children.link(c)
    return c


def root(name: str, coll: bpy.types.Collection, at: tuple = (0, 0, 0)) -> bpy.types.Object:
    """Пустышка-корень модуля: её положение — начало координат модуля."""
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.25
    e.location = at
    coll.objects.link(e)
    return e


# ---------------------------------------------------------------- bmesh-примитивы

def bm_box(bm: bmesh.types.BMesh, mn, mx) -> list:
    """Замкнутый брус от угла mn до угла mx. Возвращает его грани."""
    mn, mx = V(mn), V(mx)
    xs, ys, zs = (mn.x, mx.x), (mn.y, mx.y), (mn.z, mx.z)
    v = [bm.verts.new((xs[i], ys[j], zs[k])) for k in (0, 1) for j in (0, 1) for i in (0, 1)]
    idx = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [bm.faces.new([v[i] for i in f]) for f in idx]


def bm_prism(bm, poly2d, origin, u, w, depth_vec) -> list:
    """Призма: многоугольник в плоскости (origin, u, w), выдавленный на depth_vec."""
    o, u, w, d = V(origin), V(u), V(w), V(depth_vec)
    a = [bm.verts.new(o + u * p[0] + w * p[1]) for p in poly2d]
    b = [bm.verts.new(o + u * p[0] + w * p[1] + d) for p in poly2d]
    faces = [bm.faces.new(a[::-1]), bm.faces.new(b)]
    n = len(poly2d)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    return faces


def bm_cyl(bm, p0, p1, r: float, segs: int = 24, r1: float | None = None, cap: bool = True) -> list:
    """Цилиндр (или усечённый конус) по оси p0 → p1."""
    p0, p1 = V(p0), V(p1)
    axis = (p1 - p0).normalized()
    ref = V((0, 0, 1)) if abs(axis.z) < 0.9 else V((1, 0, 0))
    a = axis.cross(ref).normalized()
    b = axis.cross(a).normalized()
    r1 = r if r1 is None else r1
    ring0, ring1 = [], []
    for i in range(segs):
        t = 2 * math.pi * i / segs
        d = a * math.cos(t) + b * math.sin(t)
        ring0.append(bm.verts.new(p0 + d * r))
        ring1.append(bm.verts.new(p1 + d * r1))
    faces = []
    for i in range(segs):
        j = (i + 1) % segs
        faces.append(bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i])))
    if cap:
        faces.append(bm.faces.new(ring0[::-1]))
        faces.append(bm.faces.new(ring1))
    return faces


def bm_sphere(bm, center, r: float, segs: int = 16, rings: int = 8) -> None:
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r,
                              matrix=Matrix.Translation(V(center)))


def rrect(w: float, h: float, r: float, segs: int = 4, cx: float = 0.0, cy: float = 0.0) -> list:
    """Прямоугольник со скруглёнными углами (2D, против часовой стрелки)."""
    r = min(r, w / 2 - 1e-4, h / 2 - 1e-4)
    pts = []
    corners = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for x, y, a0 in corners:
        for i in range(segs + 1):
            t = math.radians(a0 + 90 * i / segs)
            pts.append((cx + x + r * math.cos(t), cy + y + r * math.sin(t)))
    return pts


def _closest(p1, d1, p2, d2):
    w = p1 - p2
    a, b, c = d1.dot(d1), d1.dot(d2), d2.dot(d2)
    d, e = d1.dot(w), d2.dot(w)
    den = a * c - b * b
    if abs(den) < 1e-10:
        return p1
    s = (b * e - c * d) / den
    t = (a * e - b * d) / den
    return ((p1 + d1 * s) + (p2 + d2 * t)) * 0.5


def bm_sweep(bm, path, profile, closed: bool = False, up=(0, 0, 1), caps: bool = True) -> list:
    """Протяжка замкнутого 2D-профиля (s, v) вдоль ломаной с запилом углов на ус.

    s — вбок: side = up × касательная; v — «вверх» профиля: касательная × side.
    """
    path = [V(p) for p in path]
    upv = V(up).normalized()
    n = len(path)
    nseg = n if closed else n - 1
    frames = []
    for i in range(nseg):
        t = (path[(i + 1) % n] - path[i]).normalized()
        side = upv.cross(t)
        if side.length < 1e-6:
            side = V((1, 0, 0)).cross(t)
        side.normalize()
        frames.append((t, side, t.cross(side).normalized()))
    rings = []
    for i in range(n):
        p = path[i]
        if not closed and i == 0:
            fr = [frames[0]]
        elif not closed and i == n - 1:
            fr = [frames[-1]]
        else:
            fr = [frames[(i - 1) % nseg], frames[i % nseg]]
        ring = []
        for s, v in profile:
            if len(fr) == 1:
                t, side, u = fr[0]
                ring.append(bm.verts.new(p + side * s + u * v))
            else:
                (t0, s0, u0), (t1, s1, u1) = fr
                ring.append(bm.verts.new(_closest(p + s0 * s + u0 * v, t0, p + s1 * s + u1 * v, t1)))
        rings.append(ring)
    faces = []
    m = len(profile)
    for i in range(nseg):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for j in range(m):
            k = (j + 1) % m
            faces.append(bm.faces.new((r0[j], r0[k], r1[k], r1[j])))
    if caps and not closed:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    return faces


def bm_wall_opening(bm, w: float, h: float, t: float, ox0: float, ox1: float, oz0: float, oz1: float,
                    weight_layer=None) -> None:
    """Стена w × h толщиной t (по Y, центр y=0) с прямоугольным проёмом [ox0, ox1] × [oz0, oz1].

    Одна замкнутая оболочка. Рёбра проёма получают вес фаски 1 — только они скругляются.
    """
    xs = [-w / 2, ox0, ox1, w / 2]
    zs = [0.0, oz1, h] if oz0 <= 1e-6 else [0.0, oz0, oz1, h]
    hole = (1, 0) if oz0 <= 1e-6 else (1, 1)
    front, back = {}, {}
    for i, x in enumerate(xs):
        for j, z in enumerate(zs):
            front[i, j] = bm.verts.new((x, t / 2, z))
            back[i, j] = bm.verts.new((x, -t / 2, z))
    quads = [(i, j) for i in range(3) for j in range(len(zs) - 1) if (i, j) != hole]
    edge_use = {}
    for i, j in quads:
        loop = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        bm.faces.new([front[c] for c in loop])
        bm.faces.new([back[c] for c in loop[::-1]])
        for a, b in zip(loop, loop[1:] + loop[:1]):
            key = tuple(sorted((a, b)))
            edge_use[key] = edge_use.get(key, 0) + 1
    hx = {hole[0], hole[0] + 1}
    hz = {hole[1], hole[1] + 1}
    for (a, b), cnt in edge_use.items():
        if cnt != 1:
            continue
        bm.faces.new((front[a], front[b], back[b], back[a]))
        on_hole = a[0] in hx and b[0] in hx and a[1] in hz and b[1] in hz
        # Нижняя кромка дверного проёма лежит на полу — её не скругляем.
        if on_hole and not (oz0 <= 1e-6 and a[1] == 0 and b[1] == 0) and weight_layer is not None:
            for side in (front, back):
                e = bm.edges.get((side[a], side[b]))
                if e is not None:
                    e[weight_layer] = 1.0
    if weight_layer is not None:
        # Рёбра откоса вдоль толщины стены у углов проёма тоже скругляются.
        for c in [(hole[0], hole[1]), (hole[0] + 1, hole[1]), (hole[0], hole[1] + 1), (hole[0] + 1, hole[1] + 1)]:
            if oz0 <= 1e-6 and c[1] == 0:
                continue
            e = bm.edges.get((front[c], back[c]))
            if e is not None:
                e[weight_layer] = 1.0


# ---------------------------------------------------------------- объекты

def weight_layer(bm):
    return bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")


def finish_bm(bm, name: str, coll, mat, parent=None, bevel: float = 0.0, segs: int = 2,
              angle: float = 35.0, by_weight: bool = False, smooth_angle: float = 35.0) -> bpy.types.Object:
    """bmesh → объект: нормали наружу, гладкое затенение по углу, фаска модификатором."""
    # Касающиеся бруски не склеиваем: общие вершины сделали бы рёбра неразделимыми (non-manifold).
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    except AttributeError:
        pass
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat is not None:
        me.materials.append(mat)
    if parent is not None:
        ob.parent = parent
    if bevel > 0:
        md = ob.modifiers.new("Фаска", "BEVEL")
        md.width = bevel
        md.segments = segs
        md.limit_method = "WEIGHT" if by_weight else "ANGLE"
        md.angle_limit = math.radians(angle)
        md.harden_normals = True
        md.use_clamp_overlap = True
    return ob


def text_mesh(bm, text: str, size: float, depth: float, at, basis: Matrix) -> None:
    """Объёмный текст (цифры номерка) в bmesh. basis — 3×3: куда идут оси текста x, y и лицевая z."""
    cu = bpy.data.curves.new("tmp_text", "FONT")
    cu.body = text
    cu.size = size
    cu.extrude = depth / 2
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new("tmp_text", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    me.transform(Matrix.Translation(V(at)) @ basis.to_4x4())
    before = len(bm.verts)
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    # Шрифт даёт двойные вершины по контуру букв — склеиваем только их.
    bmesh.ops.remove_doubles(bm, verts=bm.verts[before:], dist=1e-6)
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)


def transform(bm, verts, matrix) -> None:
    bmesh.ops.transform(bm, matrix=matrix, verts=list(verts))


def mirror_copy(bm, axis: str = "Y") -> None:
    """Добавить зеркальную копию всей геометрии bmesh относительно плоскости оси (через 0)."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    dup = bmesh.ops.duplicate(bm, geom=geom)
    verts = [e for e in dup["geom"] if isinstance(e, bmesh.types.BMVert)]
    s = {"X": (-1, 1, 1), "Y": (1, -1, 1), "Z": (1, 1, -1)}[axis]
    transform(bm, verts, Matrix.Diagonal((s[0], s[1], s[2], 1)))
    faces = [e for e in dup["geom"] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.reverse_faces(bm, faces=faces)
