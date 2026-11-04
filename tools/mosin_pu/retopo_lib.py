"""Ретопология и швы игровой сетки Мосина: снятие петель четырёхугольной сетки и разрез поверхности до «дисков».

Форма Мосина собрана процедурно (build_*.py): тела вращения, лофты сечений, протяжки по пути — это сетки-решётки
из четырёхугольников. Игровая сетка получается из той же сборки (game_retopo.py), но лишние петли снимаются целиком:
петля (цепочка рёбер через правильные вершины) растворяется, если каждая её вершина отходит от отрезка между соседями
поперёк петли меньше допуска (тот же «прогиб хорды», что у окружности из N граней). Так сетка остаётся
четырёхугольной, кольца и образующие — ровными (основа выпрямленной развёртки), а плотность сама следует за кривизной:
у шара и галтелей гуще, на плоском — редко. Петля может кончаться у полюса (веер треугольников тела вращения) или на
краю крышки-многоугольника; через треугольник или узел с другим числом рёбер она не идёт.

Швы (auto_seams): острые рёбра — уже швы; остальное поверхность режется так, чтобы каждый остров стал диском —
дерево граней по рёбрам, которые дорого резать (видимые, гладкие), разрез — остальные рёбра, «висячие» концы разреза
обрезаются. Дёшево резать — по низу (−Z) и по скрытым граням, по изломам.
"""
from __future__ import annotations

import heapq
import math

import bmesh
from mathutils import Vector


# ---------------------------------------------------------------------------------------------- снятие петель
def _next_edge(e, v):
    """Продолжение петли через вершину v (4 ребра, 4 грани вокруг) — ребро без общих граней с e. Годятся ли грани
    (четырёхугольники; у полюса — треугольники веера), проверяет _loop_ok."""
    if len(v.link_edges) != 4 or len(v.link_faces) != 4:
        return None
    fs = set(e.link_faces)
    for e2 in v.link_edges:
        if e2 is not e and not (set(e2.link_faces) & fs):
            return e2
    return None


def _quad_edge(e) -> bool:
    return len(e.link_faces) == 2 and all(len(f.verts) == 4 for f in e.link_faces)


def _pole_edge(e, v) -> bool:
    """Ребро к полюсу v: обе грани — треугольники веера вокруг v."""
    return len(e.link_faces) == 2 and all(len(f.verts) == 3 and v in f.verts for f in e.link_faces) \
        and len(v.link_edges) >= 5


def _walk(e0):
    """Петля через e0: (рёбра, замкнута ли). Концы — вершина края/крышки (3 ребра) или полюс."""
    edges = [e0]
    seen = {e0}
    closed = False
    ends = []
    for start in (e0.verts[1], e0.verts[0]):
        e, v = e0, start
        while True:
            n = _next_edge(e, v)
            if n is None:
                ends.append((e, v))
                break
            if n is e0:
                closed = True
                break
            if n in seen:
                ends.append((e, v))
                break
            seen.add(n)
            edges.append(n)
            v = n.other_vert(v)
            e = n
        if closed:
            break
    return edges, closed, ends


def _loop_ok(edges, closed, ends) -> bool:
    for e in edges:
        if not _quad_edge(e):
            # последнее ребро у полюса — между треугольниками веера
            if not any(e is ee and _pole_edge(e, v) for ee, v in ends):
                return False
    if closed:
        return True
    for e, v in ends:
        if _pole_edge(e, v):
            continue
        if len(v.link_edges) != 3:
            return False
    return True


def _perp(v, loop_set):
    other = [e for e in v.link_edges if e not in loop_set]
    return other if len(other) == 2 else None


def _seg_dist(p, a, b) -> float:
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-20 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def _loop_cost(edges, ends, tol_of, max_len: float):
    """Худшая доля допуска по вершинам петли (≥ 1 — нельзя) или None, если петля не годится."""
    loop_set = set(edges)
    verts = {v for e in edges for v in e.verts}
    poles = {v for e, v in ends if _pole_edge(e, v)}
    worst = 0.0
    for v in verts:
        if v in poles:
            continue
        pp = _perp(v, loop_set)
        if pp is None:
            return None
        a, b = pp[0].other_vert(v).co, pp[1].other_vert(v).co
        if (a - b).length > max_len:
            return None
        if pp[0].seam or pp[1].seam:
            return None
        worst = max(worst, _seg_dist(v.co, a, b) / max(tol_of(v.co), 1e-9))
        if worst >= 1.0:
            return None
    return worst


def loop_reduce(me, tol_of, max_len: float = 0.12, passes: int = 60) -> int:
    """Снять петли сетки me (метры) с отклонением меньше tol_of(точка) → м. Возврат — сколько петель снято."""
    bm = bmesh.new()
    bm.from_mesh(me)
    removed = 0
    for _ in range(passes):
        bm.edges.ensure_lookup_table()
        done = set()
        cands = []
        for e0 in bm.edges:
            if e0 in done or not (_quad_edge(e0) or len(e0.link_faces) == 2):
                continue
            edges, closed, ends = _walk(e0)
            done.update(edges)
            if not _loop_ok(edges, closed, ends) or any(e.seam for e in edges):
                continue
            cost = _loop_cost(edges, ends, tol_of, max_len)
            if cost is not None:
                cands.append((cost, edges))
        if not cands:
            break
        cands.sort(key=lambda c: c[0])
        used = set()
        chosen = []
        for cost, edges in cands:
            faces = {f for e in edges for f in e.link_faces}
            # соседние петли в одном проходе не снимаются: их прогиб считается заново после растворения
            near = faces | {g for f in faces for e in f.edges for g in e.link_faces}
            if near & used:
                continue
            used |= faces
            chosen.append(edges)
        if not chosen:
            break
        for edges in chosen:
            live = [e for e in edges if e.is_valid]
            if live:
                bmesh.ops.dissolve_edges(bm, edges=live, use_verts=True, use_face_split=False)
                removed += 1
    bm.to_mesh(me)
    bm.free()
    me.update()
    return removed


def weld(me, dist: float) -> int:
    """Слить вершины ближе dist (м) и растворить вырожденные грани; возврат — сколько вершин ушло."""
    bm = bmesh.new()
    bm.from_mesh(me)
    n0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=dist)
    n = n0 - len(bm.verts)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def non_manifold(me) -> int:
    """Рёбер не на двух гранях (открытый край или «бабочка») — после снятия петель у замкнутых тел их быть не должно."""
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    bm.free()
    return n


# ---------------------------------------------------------------------------------------------- швы до «дисков»
def auto_seams(me, cut_cost=None) -> int:
    """Дорезать швы так, чтобы каждый остров (связь граней через рёбра без шва) стал диском. Уже отмеченные швы и
    край — разрез; cut_cost(edge) — цена разреза ребра (больше — реже режется). Возврат — сколько рёбер помечено."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    def default_cost(e) -> float:
        f1, f2 = e.link_faces
        n = (f1.normal + f2.normal).normalized()
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        up = 0.5 + 0.5 * n.z                      # снизу (−Z) резать дешевле
        crease = min(1.0, e.calc_face_angle(0.0) / math.radians(45))
        return e.calc_length() * (0.15 + up) * (1.0 - 0.6 * crease) + 1e-6 * mid.length

    cost = cut_cost or default_cost
    # дерево граней наибольшей цены разреза (Прим): рёбра дерева не режутся
    in_tree = set()
    visited = set()
    for seed in bm.faces:
        if seed.index in visited:
            continue
        visited.add(seed.index)
        heap = []

        def push(f):
            for e in f.edges:
                if e.seam or len(e.link_faces) != 2:
                    continue
                g = e.link_faces[0] if e.link_faces[1] is f else e.link_faces[1]
                if g.index not in visited:
                    heapq.heappush(heap, (-cost(e), e.index, g.index))
        push(seed)
        while heap:
            _c, ei, gi = heapq.heappop(heap)
            if gi in visited:
                continue
            visited.add(gi)
            in_tree.add(ei)
            push(bm.faces[gi])
    # разрез — рёбра вне дерева; висячие концы (вершина с одним ребром разреза) обрезаются, кроме прежних швов и края
    cut = {e.index for e in bm.edges if e.index not in in_tree}
    fixed = {e.index for e in bm.edges if e.seam or len(e.link_faces) != 2}
    deg = {}
    for ei in cut:
        for v in bm.edges[ei].verts:
            deg[v.index] = deg.get(v.index, 0) + 1
    stack = [ei for ei in cut if ei not in fixed and any(deg[v.index] == 1 for v in bm.edges[ei].verts)]
    while stack:
        ei = stack.pop()
        if ei not in cut or ei in fixed:
            continue
        e = bm.edges[ei]
        if not any(deg[v.index] == 1 for v in e.verts):
            continue
        cut.discard(ei)
        for v in e.verts:
            deg[v.index] -= 1
            if deg[v.index] == 1:
                stack += [x.index for x in v.link_edges if x.index in cut and x.index not in fixed]
    added = 0
    for ei in cut:
        e = bm.edges[ei]
        if not e.seam and len(e.link_faces) == 2:
            e.seam = True
            added += 1
    bm.to_mesh(me)
    bm.free()
    me.update()
    return added
