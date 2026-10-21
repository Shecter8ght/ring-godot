"""Швейная машина для одежды NPC: лекала → сетка → обёртка вокруг тела → сшивание симуляцией ткани.

Как в Marvelous Designer, только скриптом. Деталь кроя — замкнутый контур из именованных отрезков
в плоских координатах лекала (метры). Отрезки двух деталей, которые сшиваются, получают одинаковое
число точек; пары точек соединяются «швейными» рёбрами, симуляция стягивает их до нуля.
Плоская выкройка — форма покоя ткани (ключ формы Pattern_Rest + «динамическая основа», см. simulate),
поэтому обёртка вокруг тела может быть грубой: длины рёбер ткань берёт из лекала, а не из расстановки.
Развёртка UV = координаты лекала, нить ткани идёт как в настоящем крое.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import bmesh
import bpy
import mathutils.geometry as mgeo
from mathutils import Vector
from mathutils.bvhtree import BVHTree

Vec2 = tuple[float, float]
Place = Callable[[float, float], Vector]


# ---------- кривые ----------

def catmull(points: list[Vec2], per_span: int = 24) -> list[Vec2]:
    """Гладкая кривая через опорные точки (Катмулл — Ром, концы — как у отрезка)."""
    if len(points) < 3:
        a, b = points[0], points[-1]
        return [(a[0] + (b[0] - a[0]) * t / per_span, a[1] + (b[1] - a[1]) * t / per_span) for t in range(per_span + 1)]
    pts = [points[0]] + list(points) + [points[-1]]
    out: list[Vec2] = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for k in range(per_span):
            t = k / per_span
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(points[-1])
    return out


def poly_length(pts: list[Vec2]) -> float:
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def resample(pts: list[Vec2], n: int) -> list[Vec2]:
    """n отрезков равной длины по ломаной (n+1 точка, концы сохраняются)."""
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    total = cum[-1]
    out = []
    j = 0
    for k in range(n + 1):
        d = total * k / n
        while j < len(cum) - 2 and cum[j + 1] < d:
            j += 1
        span = cum[j + 1] - cum[j]
        t = 0.0 if span <= 0 else (d - cum[j]) / span
        a, b = pts[j], pts[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out[0], out[-1] = pts[0], pts[-1]
    return out


# ---------- крой ----------

@dataclass
class Seg:
    name: str
    pts: list[Vec2]
    smooth: bool = True

    def dense(self) -> list[Vec2]:
        return catmull(self.pts) if self.smooth else _dense_poly(self.pts)


def _dense_poly(pts: list[Vec2]) -> list[Vec2]:
    out = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        for k in range(16):
            t = k / 16
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out.append(pts[-1])
    return out


@dataclass
class Piece:
    """Деталь кроя. segs — по часовой… нет: против часовой стрелки, конец отрезка = начало следующего."""
    name: str
    segs: list[Seg]
    place: Place
    mirror: bool = False            # правая деталь — зеркало левой: обратный обход граней
    material: str = "Fabric"
    groups: dict[str, Callable[[float, float], float]] = field(default_factory=dict)  # группы вершин по лекалу
    uv_offset: Vec2 = (0.0, 0.0)    # где деталь лежит на общей раскладке (метры)
    h: float | None = None          # свой шаг сетки (манжеты и резинки — мельче)

    def seg(self, name: str) -> Seg:
        return next(s for s in self.segs if s.name == name)


@dataclass
class Seam:
    a: str          # "деталь.отрезок"
    b: str
    reverse: bool = True   # сшиваемые края обычно идут навстречу друг другу


def mirror_piece(src: Piece, name: str, uv_offset: Vec2) -> Piece:
    """Правая половина: те же лекала (та же UV-форма), обёртка зеркальна по X."""
    def place(x: float, y: float, _p=src.place) -> Vector:
        v = _p(x, y)
        return Vector((-v.x, v.y, v.z))
    return Piece(name, src.segs, place, mirror=not src.mirror, material=src.material,
                 groups=dict(src.groups), uv_offset=uv_offset, h=src.h)


# ---------- сетка ----------

def _inside(pt: Vec2, poly: list[Vec2]) -> bool:
    x, y = pt
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def _dist_to_poly(pt: Vec2, poly: list[Vec2]) -> float:
    best = 1e9
    px, py = pt
    for i in range(len(poly)):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % len(poly)]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def _dist_to_polyline(pt: Vec2, poly: list[Vec2]) -> float:
    best = 1e9
    px, py = pt
    for i in range(len(poly) - 1):
        ax, ay = poly[i]
        bx, by = poly[i + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


@dataclass
class Meshed:
    piece: Piece
    verts2d: list[Vec2]
    tris: list[tuple[int, int, int]]
    seg_ids: dict[str, list[int]]      # индексы вершин вдоль отрезка, от начала к концу
    boundary: set[int]


def mesh_piece(piece: Piece, counts: dict[str, int], h: float) -> Meshed:
    loop: list[Vec2] = []
    seg_ids: dict[str, list[int]] = {}
    for s in piece.segs:
        n = counts[f"{piece.name}.{s.name}"]
        pts = resample(s.dense(), n)
        start = len(loop)
        loop.extend(pts[:-1])
        seg_ids[s.name] = list(range(start, start + n)) + [None]  # конец — начало следующего, заполним ниже
    nb = len(loop)
    names = [s.name for s in piece.segs]
    for i, nm in enumerate(names):
        nxt = names[(i + 1) % len(names)]
        seg_ids[nm][-1] = seg_ids[nxt][0]
    # Внутренние точки — треугольная решётка, отступ от края.
    xs, ys = [p[0] for p in loop], [p[1] for p in loop]
    pts = list(loop)
    row = h * math.sqrt(3) / 2
    j = 0
    y = min(ys) + row * 0.5
    while y < max(ys):
        x = min(xs) + (h * 0.5 if j % 2 else 0.0)
        while x < max(xs):
            if _inside((x, y), loop) and _dist_to_poly((x, y), loop) > 0.6 * h:
                pts.append((x, y))
            x += h
        y += row
        j += 1
    vin = [Vector(p) for p in pts]
    out = mgeo.delaunay_2d_cdt(vin, [], [list(range(nb))], 1, 1e-7, True)
    overts, _, ofaces, orig, _, _ = out
    remap = {}
    for k, o in enumerate(orig):
        if o:
            remap[k] = o[0]
    if len(remap) != len(overts):
        raise RuntimeError(f"{piece.name}: триангуляция добавила вершины")
    tris = []
    for f in ofaces:
        for t in range(1, len(f) - 1):
            tri = (remap[f[0]], remap[f[t]], remap[f[t + 1]])
            tris.append(tri)
    # Сглаживание внутренних вершин — ровные треугольники устойчивее в симуляции.
    nbr: dict[int, set[int]] = {}
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            nbr.setdefault(u, set()).add(v)
            nbr.setdefault(v, set()).add(u)
    for _ in range(4):
        new = list(pts)
        for i in range(nb, len(pts)):
            ns = nbr.get(i)
            if ns:
                new[i] = (sum(pts[k][0] for k in ns) / len(ns), sum(pts[k][1] for k in ns) / len(ns))
        pts = new
    return Meshed(piece, pts, tris, seg_ids, set(range(nb)))


def build_garment(name: str, pieces: list[Piece], seams: list[Seam], h: float,
                  collection: bpy.types.Collection) -> tuple[bpy.types.Object, list[tuple[int, int]]]:
    """Собрать все детали в один объект: базис — обёртка вокруг тела, ключ "Pattern_Rest" — плоский крой."""
    by_name = {p.name: p for p in pieces}
    lengths = {}
    for p in pieces:
        for s in p.segs:
            lengths[f"{p.name}.{s.name}"] = poly_length(s.dense())
    counts: dict[str, int] = {}
    for sm in seams:
        ha = by_name[sm.a.split(".")[0]].h or h
        hb = by_name[sm.b.split(".")[0]].h or h
        n = max(2, round(max(lengths[sm.a] / ha, lengths[sm.b] / hb)))
        for key in (sm.a, sm.b):
            if key in counts and counts[key] != n:
                n = max(n, counts[key])
        counts[sm.a] = counts[sm.b] = n
    for key, L in lengths.items():
        if key not in counts:
            ph = by_name[key.split(".")[0]].h or h
            counts[key] = max(2, round(L / ph))
    # Второй проход: отрезок в двух швах — общее число.
    for _ in range(3):
        for sm in seams:
            n = max(counts[sm.a], counts[sm.b])
            counts[sm.a] = counts[sm.b] = n

    meshed = [mesh_piece(p, counts, p.h or h) for p in pieces]
    verts3d: list[Vector] = []
    rest: list[Vector] = []
    uvs_v: list[Vec2] = []
    faces: list[tuple[int, int, int]] = []
    face_piece: list[int] = []
    base: dict[str, int] = {}
    for pi, m in enumerate(meshed):
        off = len(verts3d)
        base[m.piece.name] = off
        ox, oy = m.piece.uv_offset
        for (x, y) in m.verts2d:
            verts3d.append(m.piece.place(x, y))
            rest.append(Vector((x + ox, y + oy, 0.0)))
            uvs_v.append((x + ox, y + oy))
        for a, b, c in m.tris:
            faces.append((off + a, off + c, off + b) if m.piece.mirror else (off + a, off + b, off + c))
            face_piece.append(pi)
    sew: list[tuple[int, int]] = []
    labels: list[str] = []
    seg_lookup = {m.piece.name: m for m in meshed}
    for sm in seams:
        pa, sa = sm.a.split(".")
        pb, sb = sm.b.split(".")
        ia = [base[pa] + i for i in seg_lookup[pa].seg_ids[sa]]
        ib = [base[pb] + i for i in seg_lookup[pb].seg_ids[sb]]
        if sm.reverse:
            ib = ib[::-1]
        for u, v in zip(ia, ib):
            if u != v:
                sew.append((u, v))
                labels.append(f"{sm.a}~{sm.b}")
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in verts3d], sew, faces)
    mesh.update()
    uv = mesh.uv_layers.new(name="UV_Pattern")
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            uv.data[li].uv = uvs_v[mesh.loops[li].vertex_index]
    # Материалы по деталям.
    mats: list[str] = []
    for p in pieces:
        if p.material not in mats:
            mats.append(p.material)
    for mname in mats:
        mesh.materials.append(bpy.data.materials.get(mname) or bpy.data.materials.new(mname))
    for poly, pi in zip(mesh.polygons, face_piece):
        poly.material_index = mats.index(pieces[pi].material)
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    # Группы вершин по деталям и по лекалу (закрепление, усадка резинок и т. п.).
    for m in meshed:
        vg = obj.vertex_groups.get("piece_" + m.piece.name) or obj.vertex_groups.new(name="piece_" + m.piece.name)
        off = base[m.piece.name]
        vg.add([off + i for i in range(len(m.verts2d))], 1.0, "REPLACE")
        for gname, fn in m.piece.groups.items():
            g = obj.vertex_groups.get(gname) or obj.vertex_groups.new(name=gname)
            for i, (x, y) in enumerate(m.verts2d):
                w = fn(x, y)
                if w > 0:
                    g.add([off + i], min(1.0, w), "REPLACE")
    seam_vg = obj.vertex_groups.new(name="seam_edge")
    seam_vg.add(sorted({i for e in sew for i in e}), 1.0, "REPLACE")
    # Полоса 1,6 шага вдоль швов: сшиваемые края сходятся вплотную, самостолкновение их бы
    # расталкивало (гребень по шву) — треугольники полосы из самостолкновений исключаем.
    band = obj.vertex_groups.new(name="seam_band")
    for m in meshed:
        off = base[m.piece.name]
        seam_polys = []
        for sm in seams:
            for key in (sm.a, sm.b):
                pn, sn = key.split(".")
                if pn == m.piece.name:
                    seam_polys.append([m.verts2d[i] for i in m.seg_ids[sn]])
        hh = (m.piece.h or h) * 1.6
        ids = []
        for i, pt in enumerate(m.verts2d):
            for poly in seam_polys:
                if _dist_to_polyline(pt, poly) <= hh:
                    ids.append(off + i)
                    break
        if ids:
            band.add(ids, 1.0, "REPLACE")
    # Плоский крой — форма покоя ткани.
    obj.shape_key_add(name="Basis", from_mix=False)
    key = obj.shape_key_add(name="Pattern_Rest", from_mix=False)
    for i, co in enumerate(rest):
        key.data[i].co = co
    key.value = 0.0
    obj["sew_pairs"] = [list(p) for p in sew]
    obj["sew_labels"] = labels
    return obj, sew


# ---------- помощники обёртки ----------

class Span:
    """Ширина детали на высоте y лекала: крайние x контура. top(x) — высота отрезка top_seg над x."""

    def __init__(self, segs: list[Seg], top_seg: str | None = None):
        import bisect as _b
        self._bisect = _b
        poly = []
        for sg in segs:
            poly.extend(sg.dense()[:-1])
        self.poly = poly
        ys = [p[1] for p in poly]
        self.y0, self.y1 = min(ys), max(ys)
        self.table = []
        n = 400
        for k in range(n + 1):
            y = self.y0 + (self.y1 - self.y0) * k / n
            xs = []
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
                    t = (y - a[1]) / (b[1] - a[1])
                    xs.append(a[0] + (b[0] - a[0]) * t)
            self.table.append((y, min(xs) if xs else 0.0, max(xs) if xs else 0.0))
        self.keys = [t[0] for t in self.table]
        self.top_line = sorted(next(sg for sg in segs if sg.name == top_seg).dense()) if top_seg else None

    def at(self, y: float) -> tuple[float, float]:
        i = min(max(self._bisect.bisect_left(self.keys, y), 0), len(self.table) - 1)
        return self.table[i][1], self.table[i][2]

    def frac(self, x: float, y: float) -> float:
        """Доля ширины от левого края (0) до правого (1) на высоте y."""
        a, b = self.at(y)
        return 0.0 if b - a < 1e-6 else max(0.0, min(1.0, (x - a) / (b - a)))

    def top(self, x: float) -> float:
        w = self.top_line
        if x <= w[0][0]:
            return w[0][1]
        if x >= w[-1][0]:
            return w[-1][1]
        for a, b in zip(w, w[1:]):
            if a[0] <= x <= b[0]:
                return a[1] + (b[1] - a[1]) * (x - a[0]) / max(b[0] - a[0], 1e-9)
        return w[-1][1]


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp_table(table: list[tuple[float, tuple]], z: float) -> tuple:
    if z <= table[0][0]:
        return table[0][1]
    for (za, va), (zb, vb) in zip(table, table[1:]):
        if za <= z <= zb:
            t = (z - za) / (zb - za)
            return tuple(a + (b - a) * t for a, b in zip(va, vb))
    return table[-1][1]


# ---------- сечения тела для обёртки ----------

def _hull(pts: list[Vec2]) -> list[Vec2]:
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


class Ring:
    """Обхват тела на высоте z «рулеткой» (выпуклая оболочка), отодвинутый на margin, точки против часовой."""

    def __init__(self, pts: list[Vec2], margin: float, n: int = 360):
        hull = _hull(pts)
        cx = sum(p[0] for p in hull) / len(hull)
        cy = sum(p[1] for p in hull) / len(hull)
        self.c = (cx, cy)
        # Равномерно по углу из центра: луч → пересечение с оболочкой, затем отступ по нормали луча.
        out = []
        for k in range(n):
            a = 2 * math.pi * k / n
            d = (math.cos(a), math.sin(a))
            best = None
            for i in range(len(hull)):
                p, q = hull[i], hull[(i + 1) % len(hull)]
                ex, ey = q[0] - p[0], q[1] - p[1]
                den = d[0] * ey - d[1] * ex
                if abs(den) < 1e-12:
                    continue
                t = ((p[0] - cx) * ey - (p[1] - cy) * ex) / den
                u = ((p[0] - cx) * d[1] - (p[1] - cy) * d[0]) / den
                if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                    best = t if best is None else max(best, t)
            r = (best or 0.1) + margin
            out.append((cx + d[0] * r, cy + d[1] * r))
        self.pts = out
        self.n = n

    def point(self, angle_deg: float) -> Vec2:
        a = (angle_deg % 360.0) / 360.0 * self.n
        i = int(a) % self.n
        t = a - int(a)
        p, q = self.pts[i], self.pts[(i + 1) % self.n]
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    def arc(self, a0: float, a1: float, s: float) -> Vec2:
        """Точка на дуге от угла a0 до a1 (градусы, по кратчайшему направлению) на доле s длины дуги."""
        steps = 96
        pts = [self.point(a0 + (a1 - a0) * k / steps) for k in range(steps + 1)]
        cum = [0.0]
        for i in range(steps):
            cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
        d = cum[-1] * max(0.0, min(1.0, s))
        for i in range(steps):
            if cum[i + 1] >= d:
                t = 0.0 if cum[i + 1] == cum[i] else (d - cum[i]) / (cum[i + 1] - cum[i])
                return (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t)
        return pts[-1]


def body_section_points(obj: bpy.types.Object, z: float, keep: Callable[[float, float], bool]) -> list[Vec2]:
    mw = obj.matrix_world
    vs = obj.data.vertices
    pts = []
    for e in obj.data.edges:
        a, b = mw @ vs[e.vertices[0]].co, mw @ vs[e.vertices[1]].co
        if (a.z - z) * (b.z - z) < 0:
            p = a.lerp(b, (z - a.z) / (b.z - a.z))
            if keep(p.x, p.y):
                pts.append((p.x, p.y))
    return pts


class RingStack:
    """Кольца обхвата через 1 см по высоте; между ними — линейно."""

    def __init__(self, obj: bpy.types.Object, z0: float, z1: float, margin: Callable[[float], float],
                 keep: Callable[[float, float], bool], step: float = 0.01):
        self.z0, self.step = z0, step
        self.rings = []
        z = z0
        while z <= z1 + 1e-9:
            self.rings.append(Ring(body_section_points(obj, z, keep), margin(z)))
            z += step

    def arc(self, z: float, a0: float, a1: float, s: float) -> Vec2:
        f = (z - self.z0) / self.step
        i = max(0, min(len(self.rings) - 2, int(math.floor(f))))
        t = max(0.0, min(1.0, f - i))
        p = self.rings[i].arc(a0, a1, s)
        q = self.rings[i + 1].arc(a0, a1, s)
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


# ---------- симуляция ----------

@dataclass
class Fabric:
    mass: float = 0.3
    tension: float = 15.0
    compression: float = 15.0
    shear: float = 5.0
    bending: float = 0.5
    air: float = 1.0
    quality: int = 18
    damping: float = 5.0


FABRICS = {
    # Масса в Blender — на вершину: при шаге ~1 см вершин тысячи, массу берём малую, иначе вещь
    # «свинцовая», тянется и сползает. Ткань почти не тянется (растяжение жёстко), но легко
    # сминается (сжатие мягко) — отсюда складки, а не резина.
    "cotton": Fabric(0.05, 60, 10, 20, 0.6),
    "denim": Fabric(0.09, 90, 15, 40, 4.0),
    "twill": Fabric(0.07, 80, 15, 30, 8.0),
    "leather": Fabric(0.10, 120, 30, 60, 45.0, quality=15),
    "knit_rib": Fabric(0.04, 25, 8, 10, 0.8),
    "nylon": Fabric(0.03, 60, 8, 15, 0.25),
}


def make_collider(src: bpy.types.Object, name: str, collection: bpy.types.Collection,
                  offset: float = 0.0, thickness: float = 0.004, friction: float = 8.0,
                  cut: Callable[[Vector], bool] | None = None,
                  offset_fn: Callable[[Vector], float] | None = None) -> bpy.types.Object:
    """Копия объекта (в текущей позе, со всеми модификаторами) как твёрдое препятствие для ткани.
    cut(точка) → True: грань выбрасывается; offset_fn(точка) — свой отступ (минус — тело «тоньше»:
    там, где под одеждой тело не рисуется, а ткани нужна щель, например между бёдрами)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
    mesh.transform(src.matrix_world)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    if offset or offset_fn:
        for v in bm.verts:
            v.co += v.normal * (offset_fn(v.co) if offset_fn else offset)
    if cut:
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if cut(f.calc_center_median())], context="FACES")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.modifiers.new("Collision", "COLLISION")
    obj.collision.thickness_outer = thickness
    obj.collision.thickness_inner = 0.01
    obj.collision.cloth_friction = friction
    obj.collision.damping = 0.4
    obj.hide_render = True
    return obj


def simulate(obj: bpy.types.Object, fabric: Fabric, frames: int = 90, sew_frames: int = 25,
             pin_group: str | None = None, shrink_group: str | None = None, shrink: float = 0.0,
             self_collision: bool = True, collision_distance: float = 0.004,
             stiff_group: str | None = None, stiff_bending: float = 0.0,
             collide_collection: bpy.types.Collection | None = None, log: Callable[[str], None] = print,
             debug: tuple[str, ...] = ()) -> None:
    """Сначала без тяжести — швы стягиваются; потом тяжесть — ткань садится на тело и складки ложатся."""
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frames
    mod = obj.modifiers.new("Cloth", "CLOTH")
    st = mod.settings
    st.quality = fabric.quality
    st.mass = fabric.mass
    st.air_damping = fabric.air
    st.tension_stiffness = fabric.tension
    st.compression_stiffness = fabric.compression
    st.shear_stiffness = fabric.shear
    st.bending_stiffness = fabric.bending
    st.tension_damping = fabric.damping
    st.compression_damping = fabric.damping
    st.shear_damping = fabric.damping
    st.bending_damping = 0.5
    st.bending_model = "ANGULAR"
    st.use_sewing_springs = "nosew" not in debug
    st.sewing_force_max = 0.0
    if "norest" not in debug:
        # rest_shape_key в Blender 5 не действует. Обход: «динамическая основа» — на 1-м кадре вход
        # модификатора = расстановка вокруг тела (отсюда начальные положения), со 2-го — плоское лекало
        # (отсюда длины рёбер и углы покоя), положения же продолжают симулироваться.
        st.use_dynamic_mesh = True
        key = obj.data.shape_keys.key_blocks["Pattern_Rest"]
        key.value = 0.0
        key.keyframe_insert("value", frame=1)
        key.value = 1.0
        key.keyframe_insert("value", frame=2)
    if pin_group:
        # Закреплённые вершины следуют за входом модификатора: ключ лекала на них не действует
        # (группа "free"), они остаются на расстановке. С телом закреплённое не сталкивается.
        st.vertex_group_mass = pin_group
        st.pin_stiffness = 1.0
        gi = obj.vertex_groups[pin_group].index
        free = obj.vertex_groups.get("free") or obj.vertex_groups.new(name="free")
        for v in obj.data.vertices:
            w = next((g.weight for g in v.groups if g.group == gi), 0.0)
            free.add([v.index], 1.0 - w, "REPLACE")
        obj.data.shape_keys.key_blocks["Pattern_Rest"].vertex_group = "free"
        mod.collision_settings.vertex_group_object_collisions = pin_group
    if stiff_group:
        # Пояс, планки, манжеты: в несколько слоёв с прокладкой — гнутся труднее основной ткани.
        st.vertex_group_bending = stiff_group
        st.bending_stiffness_max = stiff_bending
    if shrink_group:
        st.vertex_group_shrink = shrink_group
        st.shrink_min = 0.0
        st.shrink_max = shrink
    cs = mod.collision_settings
    cs.use_collision = "nocol" not in debug
    cs.distance_min = collision_distance
    cs.collision_quality = 6
    cs.friction = 5.0
    cs.impulse_clamp = 0.04      # без ограничения один толчок о тело раскачивает всю ткань
    cs.self_impulse_clamp = 0.04
    cs.use_self_collision = self_collision
    cs.self_distance_min = 0.003
    if "seam_band" in obj.vertex_groups:
        cs.vertex_group_self_collisions = "seam_band"
    cs.self_friction = 5.0
    if collide_collection:
        cs.collection = collide_collection
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames
    ew = st.effector_weights
    ew.gravity = 0.0
    ew.keyframe_insert("gravity", frame=1)
    ew.keyframe_insert("gravity", frame=sew_frames)
    ew.gravity = 1.0
    ew.keyframe_insert("gravity", frame=sew_frames + 15)
    import time
    t0 = time.time()
    start = [v.co.copy() for v in obj.data.vertices]
    snaps = {int(a[5:]) for a in debug if a.startswith("snap=")} | (
        {1, 2, 5, 10, 20, 35, 50, 65, 85} if "snaps" in debug else set())
    for f in range(1, frames + 1):
        scene.frame_set(f)
        if f in snaps:
            dg = bpy.context.evaluated_depsgraph_get()
            m = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)
            snap = bpy.data.objects.new(f"{obj.name}_snap_{f:03d}", m)
            snap_col = bpy.data.collections.get("97_Snapshots") or bpy.data.collections.new("97_Snapshots")
            if snap_col.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(snap_col)
            snap_col.objects.link(snap)
            snap.hide_render = True
        if f % 10 == 0 or f < 4:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = obj.evaluated_get(dg)
            m = ev.to_mesh()
            zs = [v.co.z for v in m.vertices]
            xs = [v.co.x for v in m.vertices]
            if "trace" in debug and f in (2, 3, 6):
                moves = sorted(((m.vertices[i].co - start[i]).length, i) for i in range(len(start)))[-6:]
                for d, i in moves:
                    groups = [obj.vertex_groups[g.group].name for g in obj.data.vertices[i].groups]
                    log(f"    сдвиг {d:.3f} v{i} из {tuple(round(c, 3) for c in start[i])} {groups}")
            ev.to_mesh_clear()
            log(f"  {obj.name}: кадр {f}/{frames}, {time.time() - t0:.0f} с, x {min(xs):.2f}..{max(xs):.2f} z {min(zs):.2f}..{max(zs):.2f}")


def freeze(obj: bpy.types.Object, sew: list[tuple[int, int]], log: Callable[[str], None] = print) -> dict:
    """Забрать сетку с последнего кадра, сварить швы (пары → одна вершина), убрать швейные рёбра.
    Возвращает, насколько сошёлся каждый шов (наибольший зазор пары, мм) — шов, не сошедшийся
    в симуляции, после сварки даёт складку внутрь."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    co = [v.co.copy() for v in ev.to_mesh().vertices]
    ev.to_mesh_clear()
    gaps: dict[str, float] = {}
    labels = list(obj.get("sew_labels", []))
    for k, (a, b) in enumerate(sew):
        lab = labels[k] if k < len(labels) else "?"
        gaps[lab] = max(gaps.get(lab, 0.0), (co[a] - co[b]).length * 1000)
    for lab, g in sorted(gaps.items(), key=lambda t: -t[1]):
        log(f"  шов {lab}: зазор до {g:.1f} мм")
    for mod in list(obj.modifiers):
        obj.modifiers.remove(mod)
    if obj.data.shape_keys:
        rest = [k.co.copy() for k in obj.data.shape_keys.key_blocks["Pattern_Rest"].data]
        obj.shape_key_clear()
    else:
        rest = None
    for i, v in enumerate(obj.data.vertices):
        v.co = co[i]
    # Союзы сшитых вершин (угол может сходиться у трёх деталей).
    parent = list(range(len(co)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in sew:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for i in range(len(co)):
        groups.setdefault(find(i), []).append(i)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    targetmap = {}
    for root, members in groups.items():
        if len(members) < 2:
            continue
        avg = sum((co[i] for i in members), Vector()) / len(members)
        bm.verts[root].co = avg
        for i in members:
            if i != root:
                targetmap[bm.verts[i]] = bm.verts[root]
    # Швейные рёбра — без граней; после сварки они вырождаются, удалим заранее.
    loose = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="EDGES")
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    # Детали из лекал смотрят гранями в разные стороны (зеркальные и развёрнутые обёрткой):
    # после сварки выравниваем обход — иначе по швам тёмные полосы сглаживания.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for prop in ("sew_pairs", "sew_labels"):
        if prop in obj:
            del obj[prop]
    return gaps


def relax(obj: bpy.types.Object, fabric: Fabric, frames: int = 20, pin_group: str | None = None,
          collide_collection: bpy.types.Collection | None = None, log: Callable[[str], None] = print) -> None:
    """Короткая симуляция уже сваренной вещи: шов разглаживается, ткань досаживается под тяжестью."""
    scene = bpy.context.scene
    mod = obj.modifiers.new("Cloth_Relax", "CLOTH")
    st = mod.settings
    st.quality = fabric.quality
    st.mass = fabric.mass
    st.tension_stiffness = fabric.tension
    st.compression_stiffness = fabric.compression
    st.shear_stiffness = fabric.shear
    st.bending_stiffness = fabric.bending
    st.bending_model = "ANGULAR"
    if pin_group and pin_group in obj.vertex_groups:
        st.vertex_group_mass = pin_group
        mod.collision_settings.vertex_group_object_collisions = pin_group
    cs = mod.collision_settings
    cs.distance_min = 0.004
    cs.collision_quality = 4
    cs.use_self_collision = True
    cs.self_distance_min = 0.003
    cs.impulse_clamp = 0.04
    cs.self_impulse_clamp = 0.04
    if collide_collection:
        cs.collection = collide_collection
    mod.point_cache.frame_start = 1
    mod.point_cache.frame_end = frames
    for f in range(1, frames + 1):
        scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    co = [v.co.copy() for v in ev.to_mesh().vertices]
    ev.to_mesh_clear()
    obj.modifiers.remove(mod)
    for i, v in enumerate(obj.data.vertices):
        v.co = co[i]
    obj.data.update()
    log(f"  {obj.name}: досажено за {frames} кадров")


def smooth_noise(obj: bpy.types.Object, iterations: int = 4, factor: float = 0.5,
                 keep_boundary: bool = True) -> None:
    """Снять шум размером в треугольник (иголки от столкновений), не трогая складки крупнее 2–3 см."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    verts = [v for v in bm.verts if not (keep_boundary and v.is_boundary)]
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def penetrations(obj: bpy.types.Object, collider: bpy.types.Object, gap: float = 0.004) -> list[int]:
    """Вершины, которые при расстановке оказались внутри препятствия или ближе gap — от них ткань взрывается."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(collider, dg)
    bad = []
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        loc, nrm, _, dist = bvh.find_nearest(p)
        if loc is not None and dist < 0.05 and (p - loc).dot(nrm) < gap:
            bad.append(v.index)
    return bad


def set_coords(obj: bpy.types.Object, co: list[Vector]) -> None:
    for i, v in enumerate(obj.data.vertices):
        v.co = co[i]
    if obj.data.shape_keys:
        basis = obj.data.shape_keys.key_blocks[0]
        for i in range(len(co)):
            basis.data[i].co = co[i]
    obj.data.update()


def pattern_coords(obj: bpy.types.Object, piece: Piece) -> dict[int, Vec2]:
    """Координаты лекала (метры, без сдвига раскладки) вершин детали."""
    gi = obj.vertex_groups["piece_" + piece.name].index
    rest = obj.data.shape_keys.key_blocks["Pattern_Rest"].data
    ox, oy = piece.uv_offset
    out = {}
    for v in obj.data.vertices:
        if any(g.group == gi for g in v.groups):
            c = rest[v.index].co
            out[v.index] = (c.x - ox, c.y - oy)
    return out


def anchor(obj: bpy.types.Object, piece: Piece, targets: dict[int, Vector], radius: float) -> None:
    """Края детали — в заданные точки; внутренние вершины сдвигаются следом с плавным затуханием
    по расстоянию на лекале (radius, м)."""
    pat = pattern_coords(obj, piece)
    co = [v.co.copy() for v in obj.data.vertices]
    anchors = [(pat[i], targets[i] - co[i]) for i in targets if i in pat]
    for i, (x, y) in pat.items():
        if i in targets:
            co[i] = targets[i].copy()
            continue
        acc, wsum, dmin = Vector(), 0.0, 1e9
        for (ax, ay), d in anchors:
            r = math.hypot(x - ax, y - ay)
            dmin = min(dmin, r)
            if r < radius:
                w = (1.0 - r / radius) ** 2 / (r + 0.004)
                acc += d * w
                wsum += w
        if wsum > 0:
            co[i] = co[i] + (acc / wsum) * smoothstep(1.0 - dmin / radius)
    set_coords(obj, co)


def seg_vertices(obj: bpy.types.Object, piece: Piece, seg: str, h: float) -> list[tuple[int, float]]:
    """Вершины вдоль отрезка лекала и их доля длины от начала отрезка (0..1)."""
    pts = piece.seg(seg).dense()
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    out = []
    for i, (x, y) in pattern_coords(obj, piece).items():
        best, bt = 1e9, 0.0
        for k in range(len(pts) - 1):
            ax, ay = pts[k]
            bx, by = pts[k + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / L2))
            d = math.hypot(x - ax - t * dx, y - ay - t * dy)
            if d < best:
                best, bt = d, (cum[k] + t * math.sqrt(L2)) / cum[-1]
        if best < h * 0.25:
            out.append((i, bt))
    return out


def guide_seams(obj: bpy.types.Object, sew: list[tuple[int, int]], label_prefixes: tuple[str, ...],
                region: set[int], gap: float = 0.004, iterations: int = 300) -> int:
    """Поставить край детали прямо к его парам по шву (с зазором gap), а участок region между этим
    краем и остальной деталью — гладкой «мыльной плёнкой». Так окат рукава ложится к пройме без узлов."""
    labels = list(obj.get("sew_labels", []))
    co = [v.co.copy() for v in obj.data.vertices]
    moved = set()
    for (a, b), lab in zip(sew, labels):
        if lab.startswith(label_prefixes):
            co[a] = co[b] + (co[a] - co[b]).normalized() * gap if (co[a] - co[b]).length > 1e-6 else co[b].copy()
            moved.add(a)
    nbr: dict[int, set[int]] = {}
    for poly in obj.data.polygons:
        vs = list(poly.vertices)
        for i in range(len(vs)):
            u, w = vs[i], vs[(i + 1) % len(vs)]
            nbr.setdefault(u, set()).add(w)
            nbr.setdefault(w, set()).add(u)
    free = [i for i in region if i not in moved]
    for _ in range(iterations):
        for i in free:
            ns = nbr.get(i)
            if ns:
                acc = Vector()
                for n in ns:
                    acc += co[n]
                co[i] = acc / len(ns)
    set_coords(obj, co)
    return len(moved)


def push_along(obj: bpy.types.Object, collider: bpy.types.Object, direction: Callable[[int], Vector | None],
               margin: float = 0.012, step: float = 0.005, max_steps: int = 60) -> int:
    """Вывести вершины из тела, двигая каждую в заданном направлении (перед — вперёд, спинка — назад).
    В отличие от «ближайшей точки» соседние вершины не разлетаются на разные стороны тела."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(collider, dg)
    moved = 0
    for v in obj.data.vertices:
        d = direction(v.index)
        if d is None:
            continue
        p = v.co.copy()
        for k in range(max_steps):
            loc, nrm, _, dist = bvh.find_nearest(p)
            if loc is None or (p - loc).dot(nrm) >= margin:
                break
            p += d * step
        if p != v.co:
            v.co = p
            moved += 1
    obj.data.update()
    # Ключ формы "Basis" хранит те же координаты — обновим, иначе симуляция начнёт со старых.
    if obj.data.shape_keys:
        basis = obj.data.shape_keys.key_blocks[0]
        for v in obj.data.vertices:
            basis.data[v.index].co = v.co
    return moved


def push_out(obj: bpy.types.Object, collider: bpy.types.Object, gap: float = 0.003, reach: float = 0.05) -> int:
    """Вытолкнуть вершины, ушедшие под тело (сварка швов могла утянуть шов внутрь), по нормали
    ближайшей точки; reach — насколько глубоко внутри ещё ищем."""
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(collider, dg)
    moved = 0
    mw, mwi = obj.matrix_world, obj.matrix_world.inverted()
    for v in obj.data.vertices:
        p = mw @ v.co
        hit = bvh.find_nearest(p)
        if hit[0] is None:
            continue
        loc, nrm, _, dist = hit
        d = (p - loc).dot(nrm)
        if d < gap and dist < reach:
            v.co = mwi @ (loc + nrm * gap)
            moved += 1
    obj.data.update()
    if obj.data.shape_keys:
        basis = obj.data.shape_keys.key_blocks[0]
        for v in obj.data.vertices:
            basis.data[v.index].co = v.co
    return moved
