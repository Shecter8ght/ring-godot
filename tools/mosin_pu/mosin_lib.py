"""Общие функции построения моделей комплекта «Мосин ПУ» в Blender (фоновый режим).

Единицы сцены — метры, все размеры в функциях задаются в миллиметрах (MM переводит).
Оси винтовки: ствол к дулу +X, верх +Z, правая сторона стрелка −Y.
"""
from __future__ import annotations

import math
import os
import sys
from typing import Iterable, Sequence

import bmesh
import bpy
from mathutils import Matrix, Vector

MM = 0.001
ASSET_DIR = r"E:\Models Blender\WEAPONS\Мосин — винтовка и узлы"


# ---------------------------------------------------------------- сцена и файлы

def reset_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"
    return sc


def script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def save_blend(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("SAVED", path)


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


# ---------------------------------------------------------------- материалы-заглушки для проверки формы

_MAT_COLORS = {
    "Steel_Blued": ((0.055, 0.058, 0.062, 1), 0.85, 0.42),
    "Steel_Bright": ((0.42, 0.42, 0.43, 1), 1.0, 0.30),
    "Wood_Stock": ((0.30, 0.13, 0.05, 1), 0.0, 0.50),
    "Case_Steel_Lacquer": ((0.42, 0.24, 0.12, 1), 0.9, 0.30),
    "Bullet_Jacket": ((0.55, 0.30, 0.17, 1), 1.0, 0.28),
    "Primer_Brass": ((0.60, 0.42, 0.20, 1), 1.0, 0.30),
    "Clip_Steel": ((0.52, 0.53, 0.54, 1), 1.0, 0.35),
    "Scope_Body": ((0.035, 0.037, 0.04, 1), 0.6, 0.45),
    "Glass_Lens": ((0.9, 0.95, 1.0, 1), 0.0, 0.02),
    "Brass_Ferrule": ((0.62, 0.45, 0.20, 1), 1.0, 0.35),
    "Reticle_Black": ((0.01, 0.01, 0.01, 1), 0.0, 0.6),
}


def material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    col, metal, rough = _MAT_COLORS.get(name, ((0.5, 0.5, 0.5, 1), 0.0, 0.5))
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Roughness"].default_value = rough
    if name.startswith("Glass"):
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.52
    mat.diffuse_color = col
    return mat


# ---------------------------------------------------------------- 2D-профили

def _arc(center: Vector, r: float, a0: float, a1: float, seg: int) -> list[Vector]:
    return [center + Vector((math.cos(a0 + (a1 - a0) * i / seg), math.sin(a0 + (a1 - a0) * i / seg))) * r
            for i in range(seg + 1)]


def fillet(points: Sequence[Sequence[float]], radii: Sequence[float] | float = 0.0,
           seg: int = 6, closed: bool = False) -> list[tuple[float, float]]:
    """Скругляет углы ломаной: radii[i] — радиус в i-й вершине (0 — острый угол).

    У открытой ломаной концы не скругляются. Радиус ужимается, если соседние отрезки короче.
    """
    pts = [Vector((p[0], p[1])) for p in points]
    n = len(pts)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out: list[Vector] = []
    for i in range(n):
        r = radii[i]
        if (not closed and (i == 0 or i == n - 1)) or r <= 0:
            out.append(pts[i])
            continue
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        v1, v2 = (a - b), (c - b)
        if v1.length < 1e-9 or v2.length < 1e-9:
            out.append(b)
            continue
        v1.normalize()
        v2.normalize()
        ang = math.acos(max(-1.0, min(1.0, v1.dot(v2))))
        if ang < 1e-3 or abs(ang - math.pi) < 0.05:     # почти прямой угол не скругляем — иначе микрограни
            out.append(b)
            continue
        t = r / math.tan(ang / 2)
        t = min(t, (a - b).length * 0.49, (c - b).length * 0.49)
        r_eff = t * math.tan(ang / 2)
        p1, p2 = b + v1 * t, b + v2 * t
        center = b + (v1 + v2).normalized() * (r_eff / math.sin(ang / 2))
        a0 = math.atan2(p1.y - center.y, p1.x - center.x)
        a1 = math.atan2(p2.y - center.y, p2.x - center.x)
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        k = max(2, int(seg * abs(da) / (math.pi / 2) + 0.5))
        out.extend(_arc(center, r_eff, a0, a0 + da, k))
    return [(p.x, p.y) for p in out]


def resample_closed(points: Sequence[Sequence[float]], count: int) -> list[tuple[float, float]]:
    """Равномерно по длине переставляет точки замкнутого контура (для лофта)."""
    pts = [Vector((p[0], p[1])) for p in points]
    seglen = [(pts[(i + 1) % len(pts)] - pts[i]).length for i in range(len(pts))]
    total = sum(seglen)
    out = []
    i, acc = 0, 0.0
    for k in range(count):
        target = total * k / count
        while acc + seglen[i] < target and i < len(pts) - 1:
            acc += seglen[i]
            i += 1
        t = (target - acc) / seglen[i] if seglen[i] > 0 else 0.0
        p = pts[i].lerp(pts[(i + 1) % len(pts)], t)
        out.append((p.x, p.y))
    return out


# ---------------------------------------------------------------- построение сеток

def mesh_object(name: str, verts: list, faces: list, mat: str | Sequence[str] | None = None,
                col: bpy.types.Collection | None = None, smooth_angle: float | None = 35.0,
                face_mats: Sequence[int] | None = None) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    if mat:
        for m in ([mat] if isinstance(mat, str) else mat):
            me.materials.append(material(m))
        if face_mats:
            for p, mi in zip(me.polygons, face_mats):
                p.material_index = mi
    if smooth_angle is not None:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    return ob


def lathe(name: str, profile: Sequence[Sequence[float]], seg: int = 96, mat: str | None = None,
          col=None, closed: bool = False, smooth_angle: float = 35.0,
          origin: Sequence[float] = (0, 0, 0), axis: str = "X", phase: float = 0.0) -> bpy.types.Object:
    """Тело вращения: profile — точки (осевая координата, радиус) в мм.

    Точки с радиусом 0 становятся полюсами. closed=True — профиль замкнут (кольцо, трубка).
    axis — ось вращения; для X сечение лежит в плоскости YZ.
    """
    verts: list[tuple[float, float, float]] = []
    rings: list[list[int]] = []
    ox, oy, oz = origin
    for (x, r) in profile:
        if r < 1e-6:
            rings.append([len(verts)])
            verts.append(_axis_point(axis, x, 0.0, 0.0, ox, oy, oz))
            continue
        ring = []
        for k in range(seg):
            a = phase + 2 * math.pi * k / seg
            ring.append(len(verts))
            verts.append(_axis_point(axis, x, r * math.cos(a), r * math.sin(a), ox, oy, oz))
        rings.append(ring)
    faces = []
    n = len(rings)
    for i in range(n if closed else n - 1):
        a, b = rings[i], rings[(i + 1) % n]
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            faces += [(a[0], b[k], b[(k + 1) % seg]) for k in range(seg)]
        elif len(b) == 1:
            faces += [(a[k], b[0], a[(k + 1) % seg]) for k in range(seg)]
        else:
            faces += [(a[k], b[k], b[(k + 1) % seg], a[(k + 1) % seg]) for k in range(seg)]
    ob = mesh_object(name, verts, faces, mat, col, smooth_angle)
    fix_normals(ob)          # наружу: иначе булевы операции с этим телом молча не работают
    return ob


def _axis_point(axis: str, x: float, u: float, v: float, ox: float, oy: float, oz: float):
    if axis == "X":
        return ((ox + x) * MM, (oy + u) * MM, (oz + v) * MM)
    if axis == "Y":
        return ((ox + v) * MM, (oy + x) * MM, (oz + u) * MM)
    return ((ox + u) * MM, (oy + v) * MM, (oz + x) * MM)


def loft(name: str, sections: Sequence[Sequence[Sequence[float]]], mat: str | None = None, col=None,
         cap_start: bool = True, cap_end: bool = True, smooth_angle: float = 35.0,
         cap_center: bool = False) -> bpy.types.Object:
    """Лофт по замкнутым сечениям одинаковой длины (точки в мм, 3D)."""
    m = len(sections[0])
    verts = [tuple(c * MM for c in p) for s in sections for p in s]
    faces = []
    for i in range(len(sections) - 1):
        a, b = i * m, (i + 1) * m
        faces += [(a + k, a + (k + 1) % m, b + (k + 1) % m, b + k) for k in range(m)]
    last = (len(sections) - 1) * m
    if cap_center:
        for idx, (cap, flip) in enumerate(((cap_start, True), (cap_end, False))):
            if not cap:
                continue
            base = 0 if idx == 0 else last
            c = Vector((0, 0, 0))
            for k in range(m):
                c += Vector(verts[base + k])
            c /= m
            ci = len(verts)
            verts.append(tuple(c))
            for k in range(m):
                f = (base + k, base + (k + 1) % m, ci)
                faces.append(tuple(reversed(f)) if flip else f)
    else:
        if cap_start:
            faces.append(tuple(reversed(range(m))))
        if cap_end:
            faces.append(tuple(range(last, last + m)))
    ob = mesh_object(name, verts, faces, mat, col, smooth_angle)
    fix_normals(ob)
    return ob


def extrude_profile(name: str, outline: Sequence[Sequence[float]], y0: float, y1: float,
                    mat: str | None = None, col=None, smooth_angle: float = 35.0,
                    plane: str = "XZ") -> bpy.types.Object:
    """Плоский контур (в плоскости XZ, мм) выдавливается по Y от y0 до y1 (мм)."""
    m = len(outline)
    verts = []
    for y in (y0, y1):
        for (x, z) in outline:
            if plane == "XZ":
                verts.append((x * MM, y * MM, z * MM))
            elif plane == "XY":
                verts.append((x * MM, z * MM, y * MM))
            else:  # YZ: x контура → Y, z → Z, выдавливание по X
                verts.append((y * MM, x * MM, z * MM))
    faces = [(k, (k + 1) % m, m + (k + 1) % m, m + k) for k in range(m)]
    faces.append(tuple(reversed(range(m))))
    faces.append(tuple(range(m, 2 * m)))
    ob = mesh_object(name, verts, faces, mat, col, smooth_angle)
    fix_normals(ob)
    return ob


def smooth_interp(pts: Sequence[Sequence[float]], x: float, win: float = 0.0) -> float:
    """Линейная интерполяция по точкам (x, v) с усреднением окном ±win (мм) — без выбросов."""
    def lin(xx: float) -> float:
        if xx <= pts[0][0]:
            return pts[0][1]
        if xx >= pts[-1][0]:
            return pts[-1][1]
        for (x0, v0), (x1, v1) in zip(pts[:-1], pts[1:]):
            if x0 <= xx <= x1:
                return v0 + (v1 - v0) * (xx - x0) / (x1 - x0) if x1 > x0 else v1
        return pts[-1][1]
    if win <= 0:
        return lin(x)
    n = 9
    return sum(lin(x - win + 2 * win * i / (n - 1)) for i in range(n)) / n


def rounded_rect_yz(zt: float, zb: float, hw: float, rt: float, rb: float, count: int,
                    hw_bot: float | None = None) -> list[tuple[float, float]]:
    """Замкнутое сечение (y, z): скруглённый прямоугольник, старт — середина верха, обход к +y."""
    hb = hw if hw_bot is None else hw_bot
    poly = [(0.0, zt), (hw, zt), (hb, zb), (-hb, zb), (-hw, zt)]
    pts = fillet(poly, [0.0, rt, rb, rb, rt], seg=10, closed=True)
    # fillet начинает с первой точки (0, zt) — порядок обхода сохраняется
    return resample_closed(pts, count)


def ring_tube(name: str, outer: Sequence[Sequence[float]], inner: Sequence[Sequence[float]],
              x0: float, x1: float, mat: str | None = None, col=None, smooth_angle: float = 35.0):
    """Кольцо-обойма: внешний и внутренний контуры (y, z) одной длины, выдавлено по X от x0 до x1."""
    m = len(outer)
    loops = [[(x0, y, z) for y, z in outer], [(x1, y, z) for y, z in outer],
             [(x1, y, z) for y, z in inner], [(x0, y, z) for y, z in inner]]
    verts = [tuple(c * MM for c in p) for lp in loops for p in lp]
    faces = []
    for i in range(4):
        a, b = i * m, ((i + 1) % 4) * m
        faces += [(a + k, a + (k + 1) % m, b + (k + 1) % m, b + k) for k in range(m)]
    ob = mesh_object(name, verts, faces, mat, col, smooth_angle)
    fix_normals(ob)
    return ob


def sweep_circle(name: str, path: Sequence[Sequence[float]], radii: Sequence[float] | float, seg: int = 24,
                 mat: str | None = None, col=None, cap: bool = True, smooth_angle: float = 40.0):
    """Трубка круглого сечения вдоль ломаной (мм), радиус по точкам; рамки — параллельный перенос."""
    P = [Vector(p) for p in path]
    n = len(P)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    tangents = []
    for i in range(n):
        a, b = P[max(0, i - 1)], P[min(n - 1, i + 1)]
        tangents.append((b - a).normalized())
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    normal = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    verts, faces = [], []
    for i in range(n):
        if i > 0:
            axis = tangents[i - 1].cross(tangents[i])
            if axis.length > 1e-8:
                ang = tangents[i - 1].angle(tangents[i])
                normal = (Matrix.Rotation(ang, 3, axis.normalized()) @ normal)
            normal = (normal - tangents[i] * normal.dot(tangents[i])).normalized()
        binormal = tangents[i].cross(normal)
        for k in range(seg):
            a = 2 * math.pi * k / seg
            p = P[i] + (normal * math.cos(a) + binormal * math.sin(a)) * radii[i]
            verts.append(tuple(c * MM for c in p))
    for i in range(n - 1):
        a, b = i * seg, (i + 1) * seg
        faces += [(a + k, a + (k + 1) % seg, b + (k + 1) % seg, b + k) for k in range(seg)]
    if cap:
        faces.append(tuple(reversed(range(seg))))
        faces.append(tuple(range((n - 1) * seg, n * seg)))
    ob = mesh_object(name, verts, faces, mat, col, smooth_angle)
    fix_normals(ob)
    return ob


def bevel_mod(ob: bpy.types.Object, width_mm: float, segments: int = 3, angle: float = 40.0):
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width_mm * MM
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = True      # плоские грани остаются плоскими, без пятен у фасок
    mod.use_clamp_overlap = True
    return mod


def fix_normals(ob: bpy.types.Object) -> None:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def empty(name: str, loc_mm: Sequence[float] = (0, 0, 0), col=None, size: float = 0.01) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = size
    ob.empty_display_type = "ARROWS"
    ob.location = Vector(loc_mm) * MM
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def parent_keep(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    """Привязать, сохранив мировое положение ребёнка."""
    bpy.context.view_layer.update()        # у только что созданных объектов matrix_world ещё не посчитана
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def set_origin_mm(ob: bpy.types.Object, point_mm: Sequence[float]) -> None:
    """Перенести origin объекта в мировую точку (мм) без сдвига геометрии."""
    p = Vector(point_mm) * MM
    local = ob.matrix_world.inverted() @ p
    ob.data.transform(Matrix.Translation(-local))
    ob.matrix_world = ob.matrix_world @ Matrix.Translation(local)


def boolean(target: bpy.types.Object, cutter: bpy.types.Object, op: str = "DIFFERENCE",
            solver: str = "EXACT", apply: bool = True, remove_cutter: bool = True) -> None:
    n_mats = len(target.data.materials)
    mod = target.modifiers.new("bool_" + cutter.name, "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = solver
    if apply:
        bpy.context.view_layer.objects.active = target
        with bpy.context.temp_override(object=target, active_object=target):
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if remove_cutter:
            bpy.data.objects.remove(cutter, do_unlink=True)
        # грани от резака получают пустой слот материала — вернуть материал детали
        me = target.data
        if n_mats <= 1 and len(me.materials) > max(n_mats, 1) - 0:
            for poly in me.polygons:
                poly.material_index = 0
            while len(me.materials) > max(n_mats, 1):
                me.materials.pop()


def join(objs: Sequence[bpy.types.Object], name: str) -> bpy.types.Object:
    target = objs[0]
    with bpy.context.temp_override(active_object=target, selected_editable_objects=list(objs),
                                   selected_objects=list(objs)):
        bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def world_bbox_mm(objs: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
        ev.to_mesh_clear()
    return lo / MM, hi / MM
