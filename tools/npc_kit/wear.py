"""Маски износа одежды NPC по месту — атрибуты вершин (0…1) для материалов и будущего запекания.

Износ у настоящей вещи не равномерный: кожа куртки светлеет и матовеет на краях, гребнях складок,
локтях и швах, темнеет от грязи во впадинах и у манжет; брюки выгорают на коленях и сиденье, грязь —
книзу. Всё это считается здесь из геометрии (а не рисуется рукой), поэтому годится для любой вещи
и любого цвета: материал только решает, что делать с маской.

Атрибуты (FLOAT, на вершинах):
- fold  — складка: > 0 гребень, < 0 впадина (смещение от сглаженной формы по нормали, ±1 ≈ 4 мм);
- cmp   — сжатие ткани против лекала (0 — как в лекале, 0,3 — сжата на 30 %): там сборка и заломы;
- edge  — близость к краю вещи (низ, манжеты, воротник, застёжка), 1 у края → 0 за 3 см;
- seam  — близость к шву кроя (края островов развёртки лекал), 1 на шве → 0 за 1,5 см;
- joint — локти / колени (по костям скелета);
- seat  — сиденье и низ спины (брюки);
- touch — где трогают руками: перед бёдер, низ полочек куртки у карманов;
- sun   — обращено вверх (плечи, верх рукавов) — выгорает и пылится.
"""
from __future__ import annotations

import heapq
import math
from typing import Callable, Iterable

import bpy
from mathutils import Vector


def adjacency(me: bpy.types.Mesh) -> list[list[tuple[int, float]]]:
    """Соседи вершины по рёбрам граней (швейные «висячие» рёбра не в счёт) с длинами."""
    nbr: list[dict[int, float]] = [dict() for _ in me.vertices]
    co = [v.co for v in me.vertices]
    for poly in me.polygons:
        vs = list(poly.vertices)
        for k in range(len(vs)):
            a, b = vs[k], vs[(k + 1) % len(vs)]
            d = (co[a] - co[b]).length
            nbr[a][b] = d
            nbr[b][a] = d
    return [list(n.items()) for n in nbr]


def vertex_normals(me: bpy.types.Mesh) -> list[Vector]:
    return [v.normal.copy() for v in me.vertices]


def smoothed(me: bpy.types.Mesh, adj: list[list[tuple[int, float]]], iterations: int, factor: float = 0.5) -> list[Vector]:
    pos = [v.co.copy() for v in me.vertices]
    for _ in range(iterations):
        new = []
        for i, p in enumerate(pos):
            n = adj[i]
            if not n:
                new.append(p)
                continue
            avg = sum((pos[j] for j, _ in n), Vector()) / len(n)
            new.append(p.lerp(avg, factor))
        pos = new
    return pos


def fold(me: bpy.types.Mesh, adj, iterations: int = 10, scale: float = 0.004) -> list[float]:
    """Гребни и впадины складок: насколько вершина выступает над сглаженной формой вдоль нормали."""
    sm = smoothed(me, adj, iterations)
    nrm = vertex_normals(me)
    return [max(-1.0, min(1.0, (v.co - sm[i]).dot(nrm[i]) / scale)) for i, v in enumerate(me.vertices)]


def dijkstra(adj, seeds: Iterable[int], limit: float) -> list[float]:
    dist = [math.inf] * len(adj)
    heap = []
    for s in seeds:
        dist[s] = 0.0
        heap.append((0.0, s))
    heapq.heapify(heap)
    while heap:
        d, i = heapq.heappop(heap)
        if d > dist[i] or d > limit:
            continue
        for j, w in adj[i]:
            nd = d + w
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(heap, (nd, j))
    return dist


def falloff(dist: list[float], radius: float) -> list[float]:
    """1 у источника → 0 на radius, мягко."""
    out = []
    for d in dist:
        t = max(0.0, 1.0 - d / radius)
        out.append(t * t * (3 - 2 * t))
    return out


def boundary_vertices(me: bpy.types.Mesh) -> set[int]:
    count: dict[tuple[int, int], int] = {}
    for poly in me.polygons:
        vs = list(poly.vertices)
        for k in range(len(vs)):
            e = tuple(sorted((vs[k], vs[(k + 1) % len(vs)])))
            count[e] = count.get(e, 0) + 1
    return {i for e, n in count.items() if n == 1 for i in e}


def uv_seam_vertices(me: bpy.types.Mesh, uv_name: str = "UV_Pattern") -> set[int]:
    """Вершины на швах кроя: у одной вершины разные координаты лекала в разных гранях."""
    uv = me.uv_layers.get(uv_name)
    if not uv:
        return set()
    seen: dict[int, tuple[float, float]] = {}
    out = set()
    for li, loop in enumerate(me.loops):
        u = uv.data[li].uv
        k = (round(u.x, 5), round(u.y, 5))
        v = loop.vertex_index
        if v in seen and seen[v] != k:
            out.add(v)
        seen.setdefault(v, k)
    return out


def compression(me: bpy.types.Mesh, uv_name: str = "UV_Pattern") -> list[float]:
    """Сжатие против лекала по граням: наименьшее растяжение s₂ отображения лекало → 3D (сингулярное
    число), сжатие = 1 − s₂; на вершину — среднее по граням."""
    uv = me.uv_layers.get(uv_name)
    acc = [0.0] * len(me.vertices)
    cnt = [0] * len(me.vertices)
    if not uv:
        return acc
    for poly in me.polygons:
        li = list(poly.loop_indices)
        vs = [me.loops[k].vertex_index for k in li]
        uvs = [uv.data[k].uv for k in li]
        vals = []
        for k in range(1, len(vs) - 1):
            p0, p1, p2 = (me.vertices[vs[i]].co for i in (0, k, k + 1))
            u0, u1, u2 = uvs[0], uvs[k], uvs[k + 1]
            e1, e2 = p1 - p0, p2 - p0
            a, b = u1 - u0, u2 - u0
            det = a.x * b.y - a.y * b.x
            if abs(det) < 1e-12:
                continue
            # F = [e1 e2] · [a b]⁻¹ — столбцы Fu, Fv.
            fu = (e1 * b.y - e2 * a.y) / det
            fv = (e2 * a.x - e1 * b.x) / det
            g11, g12, g22 = fu.dot(fu), fu.dot(fv), fv.dot(fv)
            tr, dt = g11 + g22, g11 * g22 - g12 * g12
            lam2 = max(0.0, tr / 2 - math.sqrt(max(0.0, tr * tr / 4 - dt)))
            vals.append(max(0.0, 1.0 - math.sqrt(lam2)))
        if not vals:
            continue
        c = sum(vals) / len(vals)
        for v in vs:
            acc[v] += c
            cnt[v] += 1
    return [a / n if n else 0.0 for a, n in zip(acc, cnt)]


def blur(adj, values: list[float], iterations: int = 2) -> list[float]:
    for _ in range(iterations):
        values = [(values[i] + sum(values[j] for j, _ in adj[i])) / (1 + len(adj[i])) for i in range(len(values))]
    return values


def near_points(me: bpy.types.Mesh, points: list[Vector], radius: float,
                side: Callable[[Vector, Vector], float] | None = None) -> list[float]:
    """Гауссова близость к точкам (суставы); side(точка, сустав) — множитель стороны (перед/зад)."""
    out = []
    for v in me.vertices:
        best = 0.0
        for c in points:
            d = (v.co - c).length
            w = math.exp(-(d / radius) ** 2)
            if side:
                w *= side(v.co, c)
            best = max(best, w)
        out.append(best)
    return out


def sun(me: bpy.types.Mesh) -> list[float]:
    return [max(0.0, min(1.0, (v.normal.z - 0.25) / 0.65)) for v in me.vertices]


def write(obj: bpy.types.Object, name: str, values: list[float]) -> None:
    me = obj.data
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    at = me.attributes.new(name, "FLOAT", "POINT")
    at.data.foreach_set("value", values)


def bones(rig: bpy.types.Object) -> dict[str, tuple[Vector, Vector]]:
    return {b.name: (rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local) for b in rig.data.bones}


def jacket_masks(obj: bpy.types.Object, rig: bpy.types.Object, log=print) -> None:
    me = obj.data
    adj = adjacency(me)
    bn = bones(rig)
    write(obj, "fold", fold(me, adj))
    write(obj, "cmp", blur(adj, compression(me), 2))
    # Края: настоящие края вещи (низ пояса, манжет, верх воротника) и застёжка по центру переда.
    border = boundary_vertices(me)
    zip_line = {v.index for v in me.vertices if abs(v.co.x) < 0.012 and v.co.y < -0.04}
    write(obj, "edge", falloff(dijkstra(adj, border | zip_line, 0.04), 0.03))
    write(obj, "seam", falloff(dijkstra(adj, uv_seam_vertices(me), 0.02), 0.015))
    elbows = [bn[f"lowerarm_{s}"][0] for s in ("l", "r")]
    # Локоть — сзади и снаружи руки.
    write(obj, "joint", near_points(me, elbows, 0.07, lambda p, c: 0.35 + 0.65 * max(0.0, min(1.0, (p.y - c.y) / 0.03 + 0.5))))
    # Низ полочек у карманов и манжеты — руками.
    pockets = [Vector((s * 0.13, -0.17, 1.03)) for s in (1, -1)]
    write(obj, "touch", near_points(me, pockets, 0.09))
    write(obj, "sun", sun(me))
    log("  маски куртки: fold cmp edge seam joint touch sun")


def pants_masks(obj: bpy.types.Object, rig: bpy.types.Object, log=print) -> None:
    me = obj.data
    adj = adjacency(me)
    bn = bones(rig)
    write(obj, "fold", fold(me, adj))
    write(obj, "cmp", blur(adj, compression(me), 2))
    border = boundary_vertices(me)
    write(obj, "edge", falloff(dijkstra(adj, border, 0.04), 0.03))
    write(obj, "seam", falloff(dijkstra(adj, uv_seam_vertices(me), 0.02), 0.015))
    knees = [bn[f"calf_{s}"][0] for s in ("l", "r")]
    # Колено — спереди (лицо смотрит в −Y).
    write(obj, "joint", near_points(me, knees, 0.085, lambda p, c: max(0.0, min(1.0, (c.y - p.y) / 0.03 + 0.3))))
    pelvis = bn["pelvis"][0]
    seat_pts = [Vector((s * 0.085, pelvis.y + 0.10, pelvis.z - 0.10)) for s in (1, -1)]
    write(obj, "seat", near_points(me, seat_pts, 0.11, lambda p, c: max(0.0, min(1.0, (p.y - pelvis.y) / 0.04))))
    thighs = [Vector((s * 0.12, -0.10, 0.80)) for s in (1, -1)]
    write(obj, "touch", near_points(me, thighs, 0.10, lambda p, c: max(0.0, min(1.0, (c.y + 0.02 - p.y) / 0.04))))
    write(obj, "sun", sun(me))
    log("  маски брюк: fold cmp edge seam joint seat touch sun")


def boot_masks(obj: bpy.types.Object, log=print) -> None:
    """Берцы: сгиб союзки (за носком), носок — сбит, низ — грязь (это уже в материале по высоте)."""
    me = obj.data
    adj = adjacency(me)
    write(obj, "fold", fold(me, adj, iterations=6, scale=0.002))
    xs = [v.co.y for v in me.vertices]
    toe_y = min(xs)
    heel_y = max(xs)
    length = heel_y - toe_y
    toe, flex = [], []
    for v in me.vertices:
        f = (v.co.y - toe_y) / length          # 0 — носок, 1 — пятка
        toe.append(max(0.0, 1.0 - f / 0.16) * max(0.0, min(1.0, (0.09 - v.co.z) / 0.04)))
        # Сгиб — поперёк стопы на 22–34 % длины, на верхней стороне.
        flex.append(math.exp(-((f - 0.28) / 0.06) ** 2) * max(0.0, min(1.0, (v.co.z - 0.035) / 0.02)) *
                    max(0.0, min(1.0, (0.12 - v.co.z) / 0.03)))
    write(obj, "toe", toe)
    write(obj, "flex", flex)
    log("  маски берца", obj.name, f"длина {length:.3f}")


def knit_masks(obj: bpy.types.Object, mouth: Vector, log=print) -> None:
    """Балаклава: у рта — влажное пятно от дыхания."""
    me = obj.data
    adj = adjacency(me)
    write(obj, "fold", fold(me, adj, iterations=6, scale=0.002))
    write(obj, "breath", near_points(me, [mouth], 0.045))
    log("  маски балаклавы")
