"""Одежда «оболочкой»: оболочка вокруг тела → разрез по линиям швов → развёртка деталей в лекала.

Для курток, жилетов, бронежилетов: начальная форма ткани — гладкая оболочка вокруг тела на
заданном отступе, она не пересекает тело нигде, в том числе у подмышек. Детали получаются
разрезом оболочки (бок и низ рукава — плоскостью y, центр переда — x = 0, низ, горловина, край
рукава); каждая разворачивается с наименьшим растяжением (SLIM) — это и есть лекало, форма покоя
ткани (с припуском на свободу). Дальше — та же симуляция, что у кроя (garment.simulate).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import garment as gm


def evaluated_copy(src: bpy.types.Object, name: str, col: bpy.types.Collection) -> bpy.types.Object:
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    mesh.transform(src.matrix_world)
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    return obj


def seg_dist(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def voxel_remesh(obj: bpy.types.Object, size: float) -> None:
    obj.data.remesh_voxel_size = size
    obj.data.use_remesh_preserve_volume = False
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.voxel_remesh()


def smooth(obj: bpy.types.Object, iterations: int, factor: float, only: Callable[[Vector], bool] | None = None) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    verts = [v for v in bm.verts if only is None or only(v.co)]
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def offset_from(obj: bpy.types.Object, body: bpy.types.Object, margin: float, only: Callable[[Vector], bool] | None = None,
                reach: float = 0.06) -> None:
    """Каждая вершина не ближе margin к телу (по нормали ближайшей точки); дальше reach не трогаем —
    иначе у острой кромки (край пояса брюк) нормаль смотрит вбок и точку уносит к ней."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    for v in obj.data.vertices:
        if only and not only(v.co):
            continue
        loc, nrm, _, dist = bvh.find_nearest(v.co)
        if loc is None or dist > reach:
            continue
        d = (v.co - loc).dot(nrm)
        if d < margin:
            v.co = loc + nrm * margin
    obj.data.update()


def bisect(obj: bpy.types.Object, co: Vector, no: Vector, clear_outer: bool = False,
           region: Callable[[Vector], bool] | None = None) -> None:
    """Разрезать плоскостью (co, no); clear_outer — убрать то, что по нормали."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    faces = [f for f in bm.faces if region is None or region(f.calc_center_median())]
    geom = list({e for f in faces for e in f.edges}) + faces + list({v for f in faces for v in f.verts})
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=clear_outer, dist=1e-6)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


SNAP = 0.22      # доля ребра: ноль поля ближе к концу ребра — переносим вершину на линию, а не дробим


def level_cut(obj: bpy.types.Object, field: Callable[[Vector], float]) -> list[float]:
    """Разрезать сетку по нулю поля (шов любой формы — пройма, кокетка, край): на рёбрах со сменой
    знака новая вершина в точке нуля (линейно), грани делятся. Если ноль у самого конца ребра,
    существующая вершина переносится на линию: иначе остаются рёбра в доли миллиметра — в симуляции
    это сверхжёсткие пружины, ткань дрожит и мнётся «фольгой». Возвращает поле по вершинам после
    разреза (на линии — ровно 0): по нему потом делить грани на детали."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    val = {v: field(v.co) for v in bm.verts}
    # Перенос: для вершины — ближайший ноль на её рёбрах со сменой знака.
    snap: dict = {}
    for e in bm.edges:
        a, b = e.verts
        ga, gb = val[a], val[b]
        if ga * gb >= 0:
            continue
        t = ga / (ga - gb)
        if t < SNAP and (a not in snap or snap[a][0] > t):
            snap[a] = (t, a.co.lerp(b.co, t))
        elif t > 1 - SNAP and (b not in snap or snap[b][0] > 1 - t):
            snap[b] = (1 - t, a.co.lerp(b.co, t))
    for v, (_, co) in snap.items():
        v.co = co
        val[v] = 0.0
    cross = [e for e in bm.edges if val[e.verts[0]] * val[e.verts[1]] < 0]
    on_cut = {v for v, g in val.items() if g == 0.0}
    for e in cross:
        a, b = e.verts
        t = val[a] / (val[a] - val[b])
        _, nv = bmesh.utils.edge_split(e, a, t)
        val[nv] = 0.0
        on_cut.add(nv)
    for f in list({f for v in on_cut for f in v.link_faces}):
        vs = [v for v in f.verts if v in on_cut]
        if len(vs) != 2:
            continue
        if any(e.other_vert(vs[0]) is vs[1] for e in vs[0].link_edges):
            continue                    # линия идёт по ребру — делить нечего
        bmesh.ops.connect_verts(bm, verts=vs)
    bm.verts.index_update()
    out = [0.0] * len(bm.verts)
    for v in bm.verts:
        out[v.index] = val[v] if v in val else field(v.co)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return out


def clip(obj: bpy.types.Object, field: Callable[[Vector], float]) -> None:
    """Отрезать по нулю поля и убрать, где поле > 0 (край вещи: низ, конец рукава)."""
    vals = level_cut(obj, field)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    kill = [f for f in bm.faces if sum(vals[v.index] for v in f.verts) > 0]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def short_edges(obj: bpy.types.Object, limit: float = 0.002) -> int:
    me = obj.data
    return sum(1 for e in me.edges if (me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length < limit)


def delete_faces(obj: bpy.types.Object, kill: Callable[[Vector], bool]) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if kill(f.calc_center_median())], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def keep_largest(obj: bpy.types.Object) -> None:
    """После разрезов остаются обрезки (кольцо у шеи, крышки) — оставляем самый большой кусок."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    seen, parts = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, part = [f], []
        seen.add(f)
        while stack:
            g = stack.pop()
            part.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        parts.append(part)
    parts.sort(key=len, reverse=True)
    junk = [f for part in parts[1:] for f in part]
    bmesh.ops.delete(bm, geom=junk, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def fill_small_holes(obj: bpy.types.Object, max_sides: int = 30) -> None:
    """Мелкие дыры после пересборки и разрезов заделать (настоящие края — горловина, низ, рукава — больше)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=max_sides)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def smooth_boundary(obj: bpy.types.Object, iterations: int = 6, only: Callable[[Vector], bool] | None = None) -> None:
    """Сгладить зубчатый край выреза (горловина после удаления граней по клеткам)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for _ in range(iterations):
        new = {}
        for v in bm.verts:
            if not v.is_boundary or (only and not only(v.co)):
                continue
            ns = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(ns) == 2:
                new[v] = v.co * 0.5 + (ns[0].co + ns[1].co) * 0.25
        for v, c in new.items():
            v.co = c
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def boundary_loops(obj: bpy.types.Object) -> list[list[int]]:
    """Упорядоченные контуры края сетки (индексы вершин)."""
    me = obj.data
    nbr: dict[int, list[int]] = {}
    edge_faces: dict[tuple[int, int], int] = {}
    for poly in me.polygons:
        vs = list(poly.vertices)
        for i in range(len(vs)):
            k = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
            edge_faces[k] = edge_faces.get(k, 0) + 1
    for (a, b), n in edge_faces.items():
        if n == 1:
            nbr.setdefault(a, []).append(b)
            nbr.setdefault(b, []).append(a)
    loops, used = [], set()
    for start in nbr:
        if start in used:
            continue
        loop, prev, cur = [start], None, start
        used.add(start)
        while True:
            nxt = [n for n in nbr[cur] if n != prev]
            if not nxt or nxt[0] == start:
                break
            prev, cur = cur, nxt[0]
            if cur in used:
                break
            used.add(cur)
            loop.append(cur)
        loops.append(loop)
    return loops


@dataclass
class ShellPiece:
    name: str
    material: str
    faces: list[list[int]] = field(default_factory=list)   # индексы вершин оболочки
    flat: dict[int, tuple[float, float]] = field(default_factory=dict)  # вершина оболочки → лекало (м)


def split_pieces(shell: bpy.types.Object, classify: Callable[[Vector], str], materials: dict[str, str]) -> dict[str, ShellPiece]:
    pieces: dict[str, ShellPiece] = {}
    me = shell.data
    for poly in me.polygons:
        name = classify(Vector(poly.center))
        pc = pieces.setdefault(name, ShellPiece(name, materials.get(name, "Fabric")))
        pc.faces.append(list(poly.vertices))
    return pieces


def flatten(shell: bpy.types.Object, piece: ShellPiece, ease: tuple[float, float] = (1.0, 1.0),
            col: bpy.types.Collection | None = None) -> float:
    """Развернуть деталь с наименьшим растяжением и привести к метрам; ease — припуск (по ширине,
    по длине развёртки после поворота длинной стороной вверх). Возвращает искажение площади."""
    me = shell.data
    used = sorted({i for f in piece.faces for i in f})
    local = {g: k for k, g in enumerate(used)}
    verts = [me.vertices[g].co.copy() for g in used]
    mesh = bpy.data.meshes.new("Flat_" + piece.name)
    mesh.from_pydata([tuple(v) for v in verts], [], [[local[i] for i in f] for f in piece.faces])
    mesh.update()
    obj = bpy.data.objects.new("Flat_" + piece.name, mesh)
    (col or bpy.context.scene.collection).objects.link(obj)
    mesh.uv_layers.new(name="UV")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", margin=0.0, iterations=40)
    except TypeError:
        bpy.ops.uv.unwrap(method="CONFORMAL", margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = mesh.uv_layers["UV"].data
    per_vert: dict[int, Vector] = {}
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            per_vert[mesh.loops[li].vertex_index] = Vector(uv[li].uv)
    # Масштаб к метрам: по отношению площадей.
    a3 = sum(p.area for p in mesh.polygons)
    a2 = 0.0
    for poly in mesh.polygons:
        pts = [per_vert[i] for i in poly.vertices]
        a2 += abs(sum(pts[k].x * pts[(k + 1) % len(pts)].y - pts[(k + 1) % len(pts)].x * pts[k].y
                      for k in range(len(pts)))) / 2
    s = math.sqrt(a3 / max(a2, 1e-12))
    # Ориентация: главная ось развёртки — по вертикали тела (z) для удобной раскладки текстур.
    zs = [v.z for v in verts]
    zmin, zmax = min(zs), max(zs)
    lo = [per_vert[k] for k, v in enumerate(verts) if v.z < zmin + 0.05]
    hi = [per_vert[k] for k, v in enumerate(verts) if v.z > zmax - 0.05]
    up = (sum(hi, Vector((0, 0))) / max(len(hi), 1) - sum(lo, Vector((0, 0))) / max(len(lo), 1))
    ang = math.atan2(up.x, up.y)
    ca, sa = math.cos(ang), math.sin(ang)
    for k, g in enumerate(used):
        u = per_vert[k] * s
        x, y = u.x * ca - u.y * sa, u.x * sa + u.y * ca
        piece.flat[g] = (x * ease[0], y * ease[1])
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)
    return s


def assemble(name: str, shell: bpy.types.Object, pieces: list[ShellPiece], extra: list[dict],
             col: bpy.types.Collection, h: float,
             extra_sew: list[tuple[int, int]] | None = None) -> tuple[bpy.types.Object, list[tuple[int, int]]]:
    """Собрать объект ткани: вершины деталей раздельно (дубли по швам), швейные рёбра между дублями,
    ключ Pattern_Rest — лекала. extra — готовые полосы (пояс, манжеты): verts, rest, faces, sew_to."""
    me = shell.data
    verts: list[Vector] = []
    rest: list[Vector] = []
    faces: list[list[int]] = []
    face_mat: list[str] = []
    owners: dict[int, list[int]] = {}       # вершина оболочки → её копии в деталях
    groups: dict[str, list[int]] = {}
    labels: list[str] = []
    ox = 0.0
    for pc in pieces:
        used = sorted({i for f in pc.faces for i in f})
        xs = [pc.flat[g][0] for g in used]
        shift = ox - min(xs)
        local = {}
        for g in used:
            local[g] = len(verts)
            verts.append(me.vertices[g].co.copy())
            x, y = pc.flat[g]
            rest.append(Vector((x + shift, y, 0.0)))
            owners.setdefault(g, []).append(local[g])
        groups["piece_" + pc.name] = list(local.values())
        for f in pc.faces:
            faces.append([local[i] for i in f])
            face_mat.append(pc.material)
        ox += max(xs) - min(xs) + 0.10
    sew: list[tuple[int, int]] = []
    for g, copies in owners.items():
        for c in copies[1:]:
            sew.append((copies[0], c))
            labels.append("shell")
    # Швы между разными кусками оболочки (капюшон к горловине): пары вершин оболочки.
    for a, b in extra_sew or []:
        if a in owners and b in owners:
            sew.append((owners[a][0], owners[b][0]))
            labels.append("hood")
    for ex in extra:
        base = len(verts)
        verts.extend(ex["verts"])
        for (x, y) in ex["rest"]:
            rest.append(Vector((x + ox, y, 0.0)))
        ox += max(x for x, _ in ex["rest"]) - min(x for x, _ in ex["rest"]) + 0.10
        for f in ex["faces"]:
            faces.append([base + i for i in f])
            face_mat.append(ex["material"])
        groups["piece_" + ex["name"]] = list(range(base, base + len(ex["verts"])))
        for gname in ex.get("groups", []):
            groups.setdefault(gname, []).extend(range(base, base + len(ex["verts"])))
        for local_i, shell_v in ex["sew_to"]:
            if shell_v in owners:
                sew.append((base + local_i, owners[shell_v][0]))
                labels.append(ex["name"])
        for a, b in ex.get("close_pairs", []):
            sew.append((base + a, base + b))
            labels.append(ex["name"] + "_close")
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts], sew, faces)
    mesh.update()
    uvl = mesh.uv_layers.new(name="UV_Pattern")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            r = rest[mesh.loops[li].vertex_index]
            uvl.data[li].uv = (r.x, r.y)
    mats: list[str] = []
    for m in face_mat:
        if m not in mats:
            mats.append(m)
    for m in mats:
        mesh.materials.append(bpy.data.materials.get(m) or bpy.data.materials.new(m))
    for poly, m in zip(mesh.polygons, face_mat):
        poly.material_index = mats.index(m)
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    for gname, ids in groups.items():
        vg = obj.vertex_groups.new(name=gname)
        vg.add(ids, 1.0, "REPLACE")
    # Полоса у швов — без самостолкновений (сшиваемые края стоят вплотную).
    seam_ids = {i for e in sew for i in e}
    band = set(seam_ids)
    nbr: dict[int, set[int]] = {}
    for f in faces:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            nbr.setdefault(a, set()).add(b)
            nbr.setdefault(b, set()).add(a)
    for _ in range(1):
        band |= {n for i in list(band) for n in nbr.get(i, ())}
    obj.vertex_groups.new(name="seam_edge").add(sorted(seam_ids), 1.0, "REPLACE")
    obj.vertex_groups.new(name="seam_band").add(sorted(band), 1.0, "REPLACE")
    obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="Pattern_Rest", from_mix=False)
    for i, r in enumerate(rest):
        key.data[i].co = r
    key.value = 0.0
    obj["sew_labels"] = labels
    return obj, sew


def strip_along(loop_pts: list[Vector], loop_ids: list[int], down: Callable[[int, Vector], Vector],
                height: float, rows: int, closed: bool = True, outward: Callable[[Vector], Vector] | None = None) -> dict:
    """Полоса (резинка) вдоль контура: столбцы под каждой точкой контура, rows рядов на height.
    Возвращает заготовку для assemble: 3D-вершины, плоские координаты, грани, пары шва к контуру."""
    n = len(loop_pts)
    verts, rest, faces, sew_to = [], [], [], []
    cum = [0.0]
    for i in range(1, n + (1 if closed else 0)):
        cum.append(cum[-1] + (loop_pts[i % n] - loop_pts[i - 1]).length)
    cols = n + (1 if closed else 0)
    for c in range(cols):
        i = c % n
        p = loop_pts[i]
        d = down(i, p)
        o = outward(p) if outward else Vector()
        for r in range(rows + 1):
            t = r / rows
            verts.append(p + d * (height * t) + o * (0.003 + 0.002 * t))
            rest.append((cum[c], -height * t))
        if c < n or not closed:
            sew_to.append((c * (rows + 1), loop_ids[i]))
    for c in range(cols - 1):
        for r in range(rows):
            a = c * (rows + 1) + r
            b = (c + 1) * (rows + 1) + r
            faces.append([a, b, b + 1, a + 1])
    if closed:
        # Шов полосы: последний столбец — копия первого, сшиваем.
        pass
    return {"verts": verts, "rest": rest, "faces": faces, "sew_to": sew_to,
            "close_pairs": [((cols - 1) * (rows + 1) + r, r) for r in range(rows + 1)] if closed else []}
