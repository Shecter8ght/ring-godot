"""Детали брони NPC: пакеты под плиты, велкро-панели, стропа MOLLE, лямки, камербанд, фурнитура.

Всё строится по поверхностям в метрах (u — поперёк / вдоль, v — вверх / поперёк ленты) и сажается
на торс поверх одежды: сечения торса берутся выпуклыми (Hull), плиты жёсткие — кривая поверхность
одного радиуса с наклоном, подобранным так, чтобы плита лежала на груди и не входила в одежду.
Развёртка каждой детали — те же метры (UV), под фотоматериалы ткани.

Оси: X — ширина, −Y — перёд, Z — вверх.
"""
from __future__ import annotations

import math
from typing import Callable

import bmesh
import bpy
import mathutils.geometry as mgeo
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import garment as gm

Vec2 = tuple[float, float]


# ---------- торс ----------

class Hull:
    """Выпуклые сечения торса (с одеждой) через 1 см: перёд/зад по x, точки контура по углу."""

    def __init__(self, objs: list[bpy.types.Object], z0: float, z1: float, margin: float = 0.0,
                 x_max: float = 0.26, step: float = 0.01, skip_groups: tuple[str, ...] = ("piece_sleeve", "piece_cuff")):
        """Сетка без модификаторов (у одежды толщина внутрь — наружная поверхность та же); вершины групп
        skip_groups (рукава, манжеты) не в счёт — иначе контур раздувает к рукам."""
        pts_all = []
        for o in objs:
            m = o.data
            gi = {g.index for g in o.vertex_groups if g.name.startswith(skip_groups)}
            skip = {v.index for v in m.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)}
            pts_all.append(([o.matrix_world @ v.co for v in m.vertices],
                            [tuple(e.vertices) for e in m.edges if e.vertices[0] not in skip and e.vertices[1] not in skip]))
        self.z0, self.step = z0, step
        self.rings: list[gm.Ring] = []
        z = z0
        while z <= z1 + 1e-9:
            sec = []
            for co, edges in pts_all:
                for a, b in edges:
                    pa, pb = co[a], co[b]
                    if (pa.z - z) * (pb.z - z) < 0:
                        p = pa.lerp(pb, (z - pa.z) / (pb.z - pa.z))
                        if abs(p.x) < x_max:
                            sec.append((p.x, p.y))
            self.rings.append(gm.Ring(sec, margin, n=360))
            z += step

    def ring(self, z: float) -> gm.Ring:
        i = int(round((z - self.z0) / self.step))
        return self.rings[max(0, min(len(self.rings) - 1, i))]

    def y_at(self, x: float, z: float, front: bool) -> float:
        """Перёд (min y) или зад (max y) контура на вертикали x."""
        pts = self.ring(z).pts
        ys = []
        for i in range(len(pts)):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
            if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
                ys.append(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
        if not ys:
            c = self.ring(z).c
            return c[1]
        return min(ys) if front else max(ys)


# ---------- поверхности ----------

class PlateFrame:
    """Жёсткая плита (пакет под плиту): поверхность одного радиуса по ширине, с наклоном по высоте.
    u — поперёк (x), v — вверх от низа (z = z_bot + v). Нормаль — наружу (вперёд или назад).
    Поверхность — середина пакета (half — половина его толщины). press — насколько внутренняя сторона
    может вдавить одежду (куртка мягкая, плитоносец её поджимает): плита ложится с наклоном по груди /
    спине, а не стоит отвесно на самой выпуклой точке."""

    def __init__(self, hull: Hull, front: bool, z_bot: float, height: float, width: float,
                 radius: float, half: float, press: float = 0.012, x0: float = 0.0):
        self.front, self.z_bot, self.R, self.x0 = front, z_bot, radius, x0
        s = -1.0 if front else 1.0              # наружу: перёд — к −Y
        zs = [z_bot + height * iz / 16 for iz in range(17)]
        xs = [-width / 2 + width * ix / 8 for ix in range(9)]
        hy = {(iz, ix): hull.y_at(x0 + x, z, front) for iz, z in enumerate(zs) for ix, x in enumerate(xs)}
        best = None
        for k in [t * 0.02 for t in range(-10, 16)]:    # наклон: на сколько низ дальше от тела на метр высоты
            # a — положение верха середины пакета: внутренняя сторона вдавливает одежду не больше press
            lim = None
            for iz, z in enumerate(zs):
                v = z - z_bot
                for ix, x in enumerate(xs):
                    need = hy[(iz, ix)] + s * (half - press) - s * (k * (height - v)) + s * x * x / (2 * radius)
                    lim = need if lim is None else (min(lim, need) if front else max(lim, need))
            # чем ближе внутренняя сторона к одежде по всей высоте (и зазор, и вдавливание), тем лучше
            dev = 0.0
            for iz, z in enumerate(zs):
                v = z - z_bot
                for ix in (2, 4, 6):
                    y_in = lim + s * (k * (height - v)) - s * xs[ix] ** 2 / (2 * radius) - s * half
                    dev += abs(y_in - hy[(iz, ix)])
            if best is None or dev < best[0]:
                best = (dev, k, lim)
        _, self.k, self.a = best
        self.height = height
        self.s = s

    def _y(self, u: float, v: float) -> float:
        return self.a + self.s * self.k * (self.height - v) - self.s * u * u / (2 * self.R)

    def normal(self, u: float, v: float) -> Vector:
        # F = y − y(u, z): ∇F = (−dy/du, 1, −dy/dz); наружу — по знаку s
        dydu = -self.s * u / self.R
        dydz = -self.s * self.k
        n = Vector((-dydu, 1.0, -dydz)) * self.s
        return n.normalized()

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return Vector((self.x0 + u, self._y(u, v), self.z_bot + v)) + self.normal(u, v) * off


class RotFrame:
    """Поворот осей развёртки на угол вокруг точки (o_u, o_v) — косые стропы, повёрнутые детали."""

    def __init__(self, base, angle_deg: float, o_u: float, o_v: float):
        self.base, self.o_u, self.o_v = base, o_u, o_v
        a = math.radians(angle_deg)
        self.c, self.s = math.cos(a), math.sin(a)

    def _uv(self, u: float, v: float) -> tuple[float, float]:
        return self.o_u + u * self.c - v * self.s, self.o_v + u * self.s + v * self.c

    def normal(self, u: float, v: float) -> Vector:
        return self.base.normal(*self._uv(u, v))

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        uu, vv = self._uv(u, v)
        return self.base.point(uu, vv, off)


class ArmFrame:
    """Поверхность вокруг руки: u — вдоль оси от плечевого сустава, v — дуга по окружности (0 — верх
    руки, + — вперёд), радиус r(u) по рукаву одежды."""

    def __init__(self, a: Vector, b: Vector, radius: Callable[[float], float]):
        self.a = a
        self.d = (b - a).normalized()
        up = Vector((0.0, 0.0, 1.0))
        self.e_up = (up - self.d * up.dot(self.d)).normalized()
        self.e_side = self.d.cross(self.e_up).normalized()
        if self.e_side.y > 0:                  # «вперёд» — к −Y
            self.e_side = -self.e_side
        self.radius = radius

    def _dir(self, u: float, v: float) -> Vector:
        th = v / max(self.radius(u), 0.02)
        return (self.e_up * math.cos(th) + self.e_side * math.sin(th)).normalized()

    def normal(self, u: float, v: float) -> Vector:
        return self._dir(u, v)

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self.a + self.d * u + self._dir(u, v) * (self.radius(u) + off)


class NeckFrame:
    """Воротник: гладкий эллиптический цилиндр вокруг шеи по сечениям внизу и вверху (неровности
    трикотажного воротника и балаклавы не переносятся), чуть расширяется кверху на flare.
    u — длина по окружности от угла a0 к a1 (градусы, 0 — +X, −90 — перёд), v — вверх."""

    def __init__(self, hull: Hull, z_bot: float, height: float, a0: float, a1: float, offset: float,
                 flare: float = 0.012):
        def ell(ring: gm.Ring) -> tuple[float, float, float, float]:
            xs = [q[0] for q in ring.pts]
            ys = [q[1] for q in ring.pts]
            return (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
        self.e0 = ell(hull.ring(z_bot + 0.012))
        self.e1 = ell(hull.ring(z_bot + height - 0.012))
        self.z_bot, self.height, self.a0, self.a1 = z_bot, height, a0, a1
        self.offset, self.flare = offset, flare
        pts = [self._raw(k / 200, height / 2) for k in range(201)]
        self.length = sum((pts[i] - pts[i - 1]).length for i in range(1, len(pts)))

    def _ell(self, v: float) -> tuple[float, float, float, float]:
        t = max(0.0, min(1.0, v / self.height))
        cx, cy, rx, ry = (a + (b - a) * t for a, b in zip(self.e0, self.e1))
        return cx, cy, rx + self.offset + self.flare * t, ry + self.offset + self.flare * t

    def _raw(self, t: float, v: float) -> Vector:
        th = math.radians(self.a0 + (self.a1 - self.a0) * t)
        cx, cy, rx, ry = self._ell(v)
        return Vector((cx + rx * math.cos(th), cy + ry * math.sin(th), self.z_bot + v))

    def normal(self, u: float, v: float) -> Vector:
        th = math.radians(self.a0 + (self.a1 - self.a0) * u / self.length)
        _, _, rx, ry = self._ell(v)
        return Vector((math.cos(th) / rx, math.sin(th) / ry, 0.0)).normalized()

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self._raw(u / self.length, v) + self.normal(u, v) * off


class OffsetFrame:
    """Та же поверхность, сдвинутая наружу на off0 (клапан поверх пакета)."""

    def __init__(self, base, off0: float):
        self.base, self.off0 = base, off0

    def normal(self, u: float, v: float) -> Vector:
        return self.base.normal(u, v)

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self.base.point(u, v, self.off0 + off)


class RibbonFrame:
    """Лента по осевой линии: u — длина по оси (м), v — поперёк (от −w/2 до w/2), нормаль — заданная
    в точках оси (наружу от тела)."""

    def __init__(self, pts: list[Vector], normals: list[Vector]):
        self.pts = pts
        self.nrm = [n.normalized() for n in normals]
        self.cum = [0.0]
        for i in range(1, len(pts)):
            self.cum.append(self.cum[-1] + (pts[i] - pts[i - 1]).length)
        self.length = self.cum[-1]

    def _at(self, u: float) -> tuple[Vector, Vector, Vector]:
        u = max(0.0, min(self.length, u))
        i = 0
        while i < len(self.cum) - 2 and self.cum[i + 1] < u:
            i += 1
        t = (u - self.cum[i]) / max(self.cum[i + 1] - self.cum[i], 1e-9)
        p = self.pts[i].lerp(self.pts[i + 1], t)
        n = self.nrm[i].lerp(self.nrm[i + 1], t).normalized()
        tan = (self.pts[i + 1] - self.pts[i]).normalized()
        return p, tan, n

    def normal(self, u: float, v: float) -> Vector:
        return self._at(u)[2]

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        p, tan, n = self._at(u)
        side = n.cross(tan).normalized()
        return p + side * v + n * off


class BandFrame:
    """Пояс (камербанд) вокруг торса: на каждой высоте v — дуга контура от угла a0 до a1; u — длина дуги.
    push(p, n) → новая точка (обход пакетов: пояс проходит поверх / под ними)."""

    def __init__(self, hull: Hull, z_bot: float, height: float, a0: float, a1: float, offset: float,
                 push: Callable[[Vector, Vector], Vector] | None = None, rows: int = 18, samples: int = 140):
        self.z_bot, self.height = z_bot, height
        self.rows = []
        for j in range(rows + 1):
            v = height * j / rows
            ring = hull.ring(z_bot + v)
            pts = []
            for k in range(samples + 1):
                a = a0 + (a1 - a0) * k / samples
                x, y = ring.point(a)
                cx, cy = ring.c
                n = Vector((x - cx, y - cy, 0.0)).normalized()
                p = Vector((x, y, z_bot + v)) + n * offset
                if push:
                    p = push(p, n)
                pts.append(p)
            # выровнять по длине дуги
            cum = [0.0]
            for k in range(1, len(pts)):
                cum.append(cum[-1] + (pts[k] - pts[k - 1]).length)
            self.rows.append((pts, cum))
        self.length = min(r[1][-1] for r in self.rows)

    def _row_point(self, j: int, u: float) -> tuple[Vector, Vector]:
        pts, cum = self.rows[j]
        u = max(0.0, min(cum[-1], u * cum[-1] / self.length))
        i = 0
        while i < len(cum) - 2 and cum[i + 1] < u:
            i += 1
        t = (u - cum[i]) / max(cum[i + 1] - cum[i], 1e-9)
        return pts[i].lerp(pts[i + 1], t), (pts[i + 1] - pts[i]).normalized()

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        f = max(0.0, min(len(self.rows) - 1.0001, v / self.height * (len(self.rows) - 1)))
        j = int(f)
        t = f - j
        p0, t0 = self._row_point(j, u)
        p1, _ = self._row_point(j + 1, u)
        p = p0.lerp(p1, t)
        return p + self.normal(u, v) * off

    def normal(self, u: float, v: float) -> Vector:
        f = max(0.0, min(len(self.rows) - 1.0001, v / self.height * (len(self.rows) - 1)))
        j = int(f)
        p0, tan = self._row_point(j, u)
        p1, _ = self._row_point(j + 1, u)
        up = (p1 - p0).normalized()
        n = up.cross(tan)
        # наружу: от оси торса
        if n.dot(Vector((p0.x, p0.y + 0.0, 0.0))) < 0:
            n = -n
        return n.normalized()


# ---------- сетка ----------

class Mesh:
    """Набор вершин, граней, развёртки и материалов → объект."""

    def __init__(self):
        self.verts: list[Vector] = []
        self.faces: list[list[int]] = []
        self.uvs: list[list[Vec2]] = []
        self.mats: list[int] = []

    def v(self, p: Vector) -> int:
        self.verts.append(p.copy())
        return len(self.verts) - 1

    def f(self, idx: list[int], uv: list[Vec2], mat: int = 0) -> None:
        self.faces.append(idx)
        self.uvs.append(uv)
        self.mats.append(mat)

    def grid(self, rows: list[list[int]], uvrows: list[list[Vec2]], mat: int = 0, closed_u: bool = False,
             flip: bool = False) -> None:
        for j in range(len(rows) - 1):
            r0, r1 = rows[j], rows[j + 1]
            n = len(r0) if closed_u else len(r0) - 1
            for i in range(n):
                i1 = (i + 1) % len(r0)
                q = [r0[i], r0[i1], r1[i1], r1[i]]
                uq = [uvrows[j][i], uvrows[j][i1], uvrows[j + 1][i1], uvrows[j + 1][i]]
                if flip:
                    q, uq = q[::-1], uq[::-1]
                self.f(q, uq, mat)

    def build(self, name: str, col: bpy.types.Collection, materials: list[bpy.types.Material],
              smooth: bool = True) -> bpy.types.Object:
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.verts], [], self.faces)
        me.update()
        uvl = me.uv_layers.new(name="UV")
        for poly, uv in zip(me.polygons, self.uvs):
            for li, t in zip(poly.loop_indices, uv):
                uvl.data[li].uv = t
        for m in materials:
            me.materials.append(m)
        for poly, mi in zip(me.polygons, self.mats):
            poly.material_index = mi
            poly.use_smooth = smooth
        obj = bpy.data.objects.new(name, me)
        col.objects.link(obj)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        return obj


# ---------- контуры ----------

def rounded_poly(corners: list[Vec2], radii: list[float], seg: int = 6) -> list[Vec2]:
    """Многоугольник со скруглёнными углами (против часовой)."""
    out = []
    n = len(corners)
    for i in range(n):
        p0 = Vector(corners[i - 1])
        p1 = Vector(corners[i])
        p2 = Vector(corners[(i + 1) % n])
        r = radii[i]
        if r <= 0:
            out.append((p1.x, p1.y))
            continue
        d0 = (p0 - p1).normalized()
        d2 = (p2 - p1).normalized()
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d2))))
        t = r / math.tan(ang / 2)
        a = p1 + d0 * t
        b = p1 + d2 * t
        bis = (d0 + d2).normalized()
        c = p1 + bis * (r / math.sin(ang / 2))
        a0 = math.atan2(a.y - c.y, a.x - c.x)
        a1 = math.atan2(b.y - c.y, b.x - c.x)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(seg + 1):
            t2 = a0 + da * k / seg
            out.append((c.x + r * math.cos(t2), c.y + r * math.sin(t2)))
    return out


def resample_closed(poly: list[Vec2], step: float) -> list[Vec2]:
    pts = [Vector(p) for p in poly]
    cum = [0.0]
    for i in range(1, len(pts) + 1):
        cum.append(cum[-1] + (pts[i % len(pts)] - pts[i - 1]).length)
    n = max(8, int(round(cum[-1] / step)))
    out = []
    j = 0
    for k in range(n):
        d = cum[-1] * k / n
        while cum[j + 1] < d:
            j += 1
        t = (d - cum[j]) / max(cum[j + 1] - cum[j], 1e-12)
        p = pts[j].lerp(pts[(j + 1) % len(pts)], t)
        out.append((p.x, p.y))
    return out


def poly_area(poly: list[Vec2]) -> float:
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def inset(poly: list[Vec2], d: float) -> tuple[list[Vec2], list[Vec2]]:
    """Сдвиг замкнутого контура внутрь на d; возвращает (точки, наружные нормали в них)."""
    if poly_area(poly) < 0:
        poly = poly[::-1]
    n = len(poly)
    out, nrm = [], []
    for i in range(n):
        p0, p1, p2 = Vector(poly[i - 1]), Vector(poly[i]), Vector(poly[(i + 1) % n])
        e0 = (p1 - p0).normalized()
        e1 = (p2 - p1).normalized()
        n0 = Vector((e0.y, -e0.x))               # наружу для обхода против часовой
        n1 = Vector((e1.y, -e1.x))
        m = (n0 + n1)
        m = m.normalized() if m.length > 1e-9 else n0
        c = max(0.35, m.dot(n0))
        q = p1 - m * (d / c)
        out.append((q.x, q.y))
        nrm.append((m.x, m.y))
    return out, nrm


def dist_to_poly(p: Vec2, poly: list[Vec2]) -> float:
    return gm._dist_to_poly(p, poly)


# ---------- детали ----------

def padded_panel(m: Mesh, frame, outline: list[Vec2], thick: float, mat: int = 0, step: float = 0.006,
                 bulge: float = 0.003, binding: float = 0.011, relief: Callable[[float, float], float] | None = None,
                 inner: bool = True) -> None:
    """Мягкий пакет по контуру: лицевая и внутренняя стороны, скруглённый борт радиусом thick/2,
    окантовка (кромка толще на 0,7 мм на ширину binding), лицевая сторона чуть выпукла (набивка)."""
    outline = resample_closed(outline, step)
    if poly_area(outline) < 0:
        outline = outline[::-1]
    r = thick / 2
    ins, nrm = inset(outline, r)
    n = len(ins)

    def face_off(u: float, v: float, sign: float) -> float:
        d = dist_to_poly((u, v), ins)
        h = r
        if sign > 0:
            h += bulge * gm.smoothstep(d / 0.05)
            h += 0.0007 * gm.smoothstep((binding - d) / 0.002)
            if relief:
                h += relief(u, v)
        return sign * h

    # борт: кольца от внутренней стороны (−90°) к лицевой (+90°)
    K = 8
    rings = []
    uvr = []
    per = [0.0]
    for i in range(1, n + 1):
        per.append(per[-1] + (Vector(ins[i % n]) - Vector(ins[i - 1])).length)
    for k in range(K + 1):
        phi = -math.pi / 2 + math.pi * k / K
        row, urow = [], []
        for i in range(n):
            u = ins[i][0] + nrm[i][0] * r * math.cos(phi)
            v = ins[i][1] + nrm[i][1] * r * math.cos(phi)
            off = r * math.sin(phi)
            if k == K:
                off = face_off(ins[i][0], ins[i][1], 1.0)
            if k == 0:
                off = face_off(ins[i][0], ins[i][1], -1.0)
            row.append(m.v(frame.point(u, v, off)))
            urow.append((per[i], -thick * 2 + math.pi * r * k / K))
        rings.append(row)
        uvr.append(urow)
    m.grid(rings, uvr, mat, closed_u=True)
    # грани сторон: CDT по контуру и внутренним точкам
    xs = [p[0] for p in ins]
    ys = [p[1] for p in ins]
    interior = []
    yy = min(ys) + step
    row_i = 0
    while yy < max(ys):
        xx = min(xs) + (step / 2 if row_i % 2 else 0.0)
        while xx < max(xs):
            if gm._inside((xx, yy), ins) and dist_to_poly((xx, yy), ins) > step * 0.6:
                interior.append((xx, yy))
            xx += step
        yy += step * 0.87
        row_i += 1
    pts2 = [Vector(p) for p in ins + interior]
    out = mgeo.delaunay_2d_cdt(pts2, [], [list(range(n))], 1, 1e-9, True)
    _, _, ofaces, orig, _, _ = out
    remap = {k: o[0] for k, o in enumerate(orig) if o}
    for sign, ring in ((1.0, rings[K]), (-1.0, rings[0])):
        if sign < 0 and not inner:
            continue
        ids = {}
        for k2, o in remap.items():
            if o < n:
                ids[k2] = ring[o]
            else:
                u, v = interior[o - n]
                ids[k2] = m.v(frame.point(u, v, face_off(u, v, sign)))
        for f in ofaces:
            if not all(k2 in ids for k2 in f):
                continue
            idx = [ids[k2] for k2 in f]
            uv = [tuple(pts2[remap[k2]]) for k2 in f]
            if sign > 0:
                m.f(idx, uv, mat)
            else:
                m.f(idx[::-1], uv[::-1], mat)


def webbing_rows(m: Mesh, frame, u0: float, u1: float, v_rows: list[float], base_off: float, mat: int = 0,
                 height: float = 0.025, thick: float = 0.0016, pitch: float = 0.038, step: float = 0.003) -> None:
    """Ряды стропы MOLLE: лента 25 мм пришита закрепками через 38 мм, между ними — петли чуть выпуклы.
    v_rows — низ каждой ленты."""
    nu = max(2, int(round((u1 - u0) / step)))
    nv = 4
    for vr in v_rows:
        top, bot, uvt, uvb = [], [], [], []
        for j in range(nv + 1):
            v = vr + height * j / nv
            rt, rb, ut, ub = [], [], [], []
            for i in range(nu + 1):
                u = u0 + (u1 - u0) * i / nu
                # закрепка — узкая вмятина до основы (4 мм), между закрепками петля почти плоская
                ph = ((u - u0) / pitch) % 1.0
                d_tack = min(ph, 1.0 - ph) * pitch
                loop = gm.smoothstep(d_tack / 0.004)
                edge = 1.0 - 0.3 * (abs(j - nv / 2) / (nv / 2)) ** 2
                lift = 0.0002 + 0.0013 * loop * edge
                rt.append(m.v(frame.point(u, v, base_off + thick + lift)))
                rb.append(m.v(frame.point(u, v, base_off + 0.0002)))
                ut.append((u, v))
                ub.append((u, v + 0.05))
            top.append(rt)
            bot.append(rb)
            uvt.append(ut)
            uvb.append(ub)
        m.grid(top, uvt, mat)
        # борта ленты (верх и низ) и торцы
        m.grid([bot[0], top[0]], [uvb[0], uvt[0]], mat, flip=True)
        m.grid([bot[-1], top[-1]], [uvb[-1], uvt[-1]], mat)
        for side in (0, -1):
            col_t = [top[j][side] for j in range(nv + 1)]
            col_b = [bot[j][side] for j in range(nv + 1)]
            cu = [(0.0, j * 0.01) for j in range(nv + 1)]
            m.grid([col_b, col_t], [cu, [(0.002, c[1]) for c in cu]], mat, flip=(side == 0))


def strap(m: Mesh, frame: RibbonFrame, width: float, thick: float, base_off: float = 0.0, mat: int = 0,
          u0: float = 0.0, u1: float | None = None, step: float = 0.004, round_edges: bool = True,
          taper: float = 0.0) -> None:
    """Лента (стропа, лямка, накладка): сечение со скруглёнными боками. taper — длина, на которой
    концы сходят на нет (у мягкой накладки торцы скруглены, а не обрублены)."""
    u1 = frame.length if u1 is None else u1
    nu = max(2, int(round((u1 - u0) / step)))
    K = 3 if round_edges else 1
    hw = width / 2
    # правая половина сечения: от верха через бок к низу; левая — зеркально
    half = []
    for k in range(2 * K + 1):
        a = math.pi / 2 - math.pi * k / (2 * K)
        half.append((hw - thick / 2 + thick / 2 * math.cos(a), thick / 2 + thick / 2 * math.sin(a)))
    full = half + [(-x, y) for x, y in half[::-1]]
    rows, uvrows = [], []
    for i in range(nu + 1):
        u = u0 + (u1 - u0) * i / nu
        sc = 1.0
        if taper > 0:
            e = min(u - u0, u1 - u) / taper
            sc = 0.35 + 0.65 * math.sqrt(max(0.0, min(1.0, e)) * (2 - min(1.0, e)))
        row, urow = [], []
        acc = 0.0
        for k, (x, y) in enumerate(full):
            row.append(m.v(frame.point(u, x * (0.6 + 0.4 * sc), base_off + y * sc)))
            if k:
                acc += math.dist(full[k], full[k - 1])
            urow.append((u, acc))
        rows.append(row)
        uvrows.append(urow)
    m.grid(rows, uvrows, mat, closed_u=True)
    for end, flip in ((rows[0], True), (rows[-1], False)):
        c = m.v(sum((m.verts[i] for i in end), Vector()) / len(end))
        for k in range(len(end)):
            a2, b2 = end[k], end[(k + 1) % len(end)]
            m.f([a2, b2, c] if not flip else [b2, a2, c], [(0, 0), (0.01, 0), (0.005, 0.01)], mat)


def box(m: Mesh, center: Vector, ax: Vector, ay: Vector, az: Vector, size: tuple[float, float, float],
        mat: int = 0, bevel: float = 0.0) -> None:
    """Брусок по осям ax, ay, az (единичные) с размерами size; bevel — скос рёбер (одна фаска)."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                corners.append(center + ax * (sx * hx) + ay * (sy * hy) + az * (sz * hz))
    idx = [m.v(c) for c in corners]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        m.f([idx[i] for i in f], [(0, 0), (1, 0), (1, 1), (0, 1)], mat)


def torus(m: Mesh, center: Vector, axis: Vector, R: float, r: float, mat: int = 0, seg: int = 20, sides: int = 8) -> None:
    axis = axis.normalized()
    t = axis.orthogonal().normalized()
    b = axis.cross(t)
    rows = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        c = center + (t * math.cos(a) + b * math.sin(a)) * R
        d = (c - center).normalized()
        row = []
        for k in range(sides):
            p = 2 * math.pi * k / sides
            row.append(m.v(c + d * (r * math.cos(p)) + axis * (r * math.sin(p))))
        rows.append(row)
    rows.append(rows[0])
    m.grid(rows, [[(i / seg, k / sides) for k in range(sides)] for i in range(seg + 1)], mat, closed_u=True)


def rbox(m: Mesh, center: Vector, ax: Vector, ay: Vector, az: Vector, size: tuple[float, float, float],
         r: float, bevel: float = 0.0006, mat: int = 0) -> None:
    """Брусок со скруглёнными углами в плоскости ax–ay и фаской сверху (пластиковая фурнитура)."""
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    r = min(r, hx * 0.95, hy * 0.95)
    prof = rounded_poly([(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)], [r] * 4, seg=4)
    rings = []
    for z, ins in ((-hz, 0.0), (hz - bevel, 0.0), (hz, bevel)):
        ring = []
        for x, y in prof:
            k = 1.0 - ins / max(min(hx, hy), 1e-6)
            ring.append(m.v(center + ax * (x * k) + ay * (y * k) + az * z))
        rings.append(ring)
    m.grid(rings, [[(i / len(prof), j * 0.1) for i in range(len(prof))] for j in range(3)], mat, closed_u=True)
    for ring, z, flip in ((rings[0], -hz, True), (rings[-1], hz, False)):
        c = m.v(center + az * z)
        for i in range(len(ring)):
            a2, b2 = ring[i], ring[(i + 1) % len(ring)]
            m.f([a2, b2, c] if not flip else [b2, a2, c], [(0, 0), (0.01, 0), (0.005, 0.01)], mat)


def ladder_lock(m: Mesh, center: Vector, ax: Vector, ay: Vector, az: Vector, width: float, mat: int = 0) -> None:
    """Пряжка-«лестница»: рамка и две перекладины (ширина под стропу width)."""
    w = width + 0.008
    h = 0.024
    t = 0.004
    for dy in (-h / 2 + 0.002, h / 2 - 0.002):
        rbox(m, center + ay * dy, ax, ay, az, (w, 0.004, t), 0.0015, mat=mat)
    for dx in (-w / 2 + 0.002, w / 2 - 0.002):
        rbox(m, center + ax * dx, ax, ay, az, (0.004, h, t), 0.0015, mat=mat)
    for dy in (-0.003, 0.004):
        rbox(m, center + ay * dy + az * 0.001, ax, ay, az, (w - 0.004, 0.003, t * 0.8), 0.0015, mat=mat)


def side_release(m: Mesh, center: Vector, ax: Vector, ay: Vector, az: Vector, width: float, mat: int = 0) -> None:
    """Фастекс: «мама» — корпус с окнами по бокам, «папа» — язык с двумя пружинными защёлками,
    видными в окнах, и рамкой под стропу; ay — вдоль стропы (к «маме»), ax — поперёк, az — от тела."""
    w = width + 0.010
    rbox(m, center + ay * 0.013, ax, ay, az, (w, 0.028, 0.009), 0.004, mat=mat)           # мама
    rbox(m, center + ay * 0.031, ax, ay, az, (w - 0.002, 0.008, 0.005), 0.002, mat=mat)   # рамка стропы мамы
    for sx in (-1, 1):
        rbox(m, center + ax * (sx * (w / 2 - 0.0015)) + ay * 0.004, ax, ay, az,
             (0.0045, 0.016, 0.0072), 0.0015, mat=mat)                                   # защёлки в окнах
    rbox(m, center - ay * 0.006, ax, ay, az, (w * 0.7, 0.014, 0.0062), 0.003, mat=mat)    # язык
    rbox(m, center - ay * 0.017, ax, ay, az, (w - 0.003, 0.008, 0.0052), 0.0025, mat=mat)  # рамка стропы папы


def tube(m: Mesh, pts: list[Vector], radius: float, mat: int = 0, sides: int = 8) -> None:
    """Трубка по ломаной (трос, шнур): кольца с переносом рамки без закручивания."""
    if len(pts) < 2:
        return
    t0 = (pts[1] - pts[0]).normalized()
    n = t0.orthogonal().normalized()
    rows = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = (n - t * n.dot(t)).normalized()
        b = t.cross(n)
        rows.append([m.v(p + (n * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * radius)
                     for k in range(sides)])
    m.grid(rows, [[(i * 0.01, k / sides) for k in range(sides)] for i in range(len(rows))], mat, closed_u=True)
