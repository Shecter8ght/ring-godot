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
    """Поверхность вокруг конечности: u — вдоль оси от сустава a к b, v — дуга по окружности (0 — по ref,
    у руки — верх; + — к side_hint, у руки — вперёд), радиус r(u) по одежде. Бедро: ref — перёд,
    side_hint — наружу."""

    def __init__(self, a: Vector, b: Vector, radius: Callable[[float], float], ref: Vector | None = None,
                 side_hint: Vector | None = None):
        self.a = a
        self.d = (b - a).normalized()
        up = Vector((0.0, 0.0, 1.0)) if ref is None else ref
        self.e_up = (up - self.d * up.dot(self.d)).normalized()
        self.e_side = self.d.cross(self.e_up).normalized()
        if self.e_side.dot(Vector((0.0, -1.0, 0.0)) if side_hint is None else side_hint) < 0:
            self.e_side = -self.e_side
        self.radius = radius

    def _dir(self, u: float, v: float) -> Vector:
        th = v / max(self.radius(u), 0.02)
        return (self.e_up * math.cos(th) + self.e_side * math.sin(th)).normalized()

    def normal(self, u: float, v: float) -> Vector:
        return self._dir(u, v)

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self.a + self.d * u + self._dir(u, v) * (self.radius(u) + off)


class ShellFrame:
    """Оболочка вокруг оси a→b по замерам лучами к оси: радиус r(u, θ) — внешняя из поверхностей под
    деталью (каждая со своим зазором, у мягкой одежды он может быть отрицательным — деталь её поджимает).
    u — вдоль оси, v — дуга по опорному радиусу r0 (θ = v / r0; 0 — по ref, + — к side_hint).
    Сетка сглажена; fill="valleys" — впадины вдоль оси заполнены (погон по плечу не провисает между
    накладкой лямки и наплечником), fill="taper" — ниже по оси не шире, чем выше (щиток бедра — конус)."""

    def __init__(self, a: Vector, b: Vector, layers: list[tuple[BVHTree, float]], u0: float, u1: float,
                 th0: float, th1: float, r0: float, ref: Vector | None = None, side_hint: Vector | None = None,
                 nu: int = 28, nth: int = 28, fill: str = "", smooth: int = 3, r_min: float = 0.03,
                 convex: bool = False):
        base = ArmFrame(a, b, lambda u: r0, ref, side_hint)
        self.a, self.d, self.e_up, self.e_side, self.r0 = base.a, base.d, base.e_up, base.e_side, r0
        self.u0, self.u1, self.th0, self.th1, self.nu, self.nth = u0, u1, th0, th1, nu, nth
        grid = []
        for i in range(nu + 1):
            u = u0 + (u1 - u0) * i / nu
            c = self.a + self.d * u
            row = []
            for j in range(nth + 1):
                dv = self._dir(th0 + (th1 - th0) * j / nth)
                r = r_min
                for bvh, clr in layers:
                    hit = bvh.ray_cast(c + dv * 0.45, -dv, 0.45)
                    if hit[0] is not None:
                        r = max(r, (hit[0] - c).dot(dv) + clr)
                row.append(r)
            grid.append(row)
        if fill:
            for j in range(nth + 1):
                col = [grid[i][j] for i in range(nu + 1)]
                for i in range(nu + 1):
                    if fill == "taper":
                        col[i] = max(col[i:])
                    elif 0 < i < nu:
                        col[i] = max(col[i], min(max(col[:i]), max(col[i + 1:])))
                for i in range(nu + 1):
                    grid[i][j] = col[i]
        if convex:
            # Поперёк — выпуклая оболочка сечения: жёсткая деталь перекрывает карман, складку, накладку
            # лямки мостиком, а не повторяет их.
            ths = [th0 + (th1 - th0) * j / nth for j in range(nth + 1)]
            for i in range(nu + 1):
                hull = gm._hull([(0.0, 0.0)] + [(r * math.cos(t), r * math.sin(t)) for t, r in zip(ths, grid[i])])
                row = []
                for t, r in zip(ths, grid[i]):
                    dx, dy = math.cos(t), math.sin(t)
                    best = r
                    for k in range(len(hull)):
                        (px, py), (qx, qy) = hull[k], hull[(k + 1) % len(hull)]
                        ex, ey = qx - px, qy - py
                        den = dx * ey - dy * ex
                        if abs(den) < 1e-12:
                            continue
                        s = (px * ey - py * ex) / den
                        w = (px * dy - py * dx) / den
                        if s > 0 and -1e-9 <= w <= 1 + 1e-9:
                            best = max(best, s)
                    row.append(best)
                grid[i] = row
        for _ in range(smooth):
            new = [row[:] for row in grid]
            for i in range(nu + 1):
                for j in range(nth + 1):
                    nb = [grid[i2][j2] for i2, j2 in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                          if 0 <= i2 <= nu and 0 <= j2 <= nth]
                    # сглаживание только наружу: деталь не должна уйти внутрь того, что под ней
                    new[i][j] = max(grid[i][j], 0.5 * grid[i][j] + 0.5 * sum(nb) / len(nb))
            grid = new
        self.grid = grid

    def _dir(self, th: float) -> Vector:
        return (self.e_up * math.cos(th) + self.e_side * math.sin(th)).normalized()

    def radius(self, u: float, th: float) -> float:
        fi = max(0.0, min(self.nu - 1e-6, (u - self.u0) / (self.u1 - self.u0) * self.nu))
        fj = max(0.0, min(self.nth - 1e-6, (th - self.th0) / (self.th1 - self.th0) * self.nth))
        i, j = int(fi), int(fj)
        ti, tj = fi - i, fj - j
        g = self.grid
        r0 = g[i][j] + (g[i][j + 1] - g[i][j]) * tj
        r1 = g[i + 1][j] + (g[i + 1][j + 1] - g[i + 1][j]) * tj
        return r0 + (r1 - r0) * ti

    def _raw(self, u: float, v: float) -> Vector:
        th = v / self.r0
        return self.a + self.d * u + self._dir(th) * self.radius(u, th)

    def normal(self, u: float, v: float) -> Vector:
        h = 0.004
        du = self._raw(u + h, v) - self._raw(u - h, v)
        dv = self._raw(u, v + h) - self._raw(u, v - h)
        n = du.cross(dv)
        if n.length < 1e-12:
            return self._dir(v / self.r0)
        n.normalize()
        return n if n.dot(self._dir(v / self.r0)) > 0 else -n

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self._raw(u, v) + self.normal(u, v) * off


def bvh_of(parts: list[tuple[list[Vector], list[list[int]]]]) -> BVHTree:
    """Одно дерево лучей из нескольких наборов (вершины в мире, грани)."""
    co, faces = [], []
    for verts, fs in parts:
        base = len(co)
        co += verts
        faces += [[base + i for i in f] for f in fs]
    return BVHTree.FromPolygons(co, faces)


def mesh_parts(obj: bpy.types.Object, skip_groups: tuple[str, ...] = ()) -> tuple[list[Vector], list[list[int]]]:
    """Вершины (в мире) и грани объекта без модификаторов; грани с вершинами групп skip_groups — не в счёт."""
    me = obj.data
    gi = {g.index for g in obj.vertex_groups if g.name.startswith(skip_groups)} if skip_groups else set()
    skip = {v.index for v in me.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)} if gi else set()
    return ([obj.matrix_world @ v.co for v in me.vertices],
            [list(p.vertices) for p in me.polygons if not any(i in skip for i in p.vertices)])


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


class MouthLidFrame:
    """Мягкий клапан кармана по горловине-подкове (верх пакета вместе с плечевыми вырезами): s — длина
    вдоль горловины (curve — контур пакета, отступленный внутрь на радиус борта, против часовой), t — от
    шарнира у задней стенки через край (дуга радиуса r) и вниз на лицевую сторону на over(u) (u — поперёк
    пакета в точке горловины: сверху клапан заходит дальше, на плечевых вырезах — узкой полосой).
    opened (0…1) — клапан откинут: каждое сечение повёрнуто вокруг своей оси шарнира на angle градусов
    (клапан мягкий — у подковы нет одной оси, состояние «Открыт» идёт ключом формы)."""

    def __init__(self, frame, curve: list[Vec2], r: float, over: Callable[[float], float], opened: float = 0.0,
                 angle: float = 150.0):
        self.frame, self.r, self.over = frame, r, over
        self.pts = [Vector(p) for p in curve]
        self.cum = [0.0]
        for i in range(1, len(self.pts)):
            self.cum.append(self.cum[-1] + (self.pts[i] - self.pts[i - 1]).length)
        self.length = self.cum[-1]
        self.arc = math.pi * r
        self.ang = math.radians(angle) * opened

    def at(self, s: float) -> tuple[Vector, Vector, Vector]:
        """Точка горловины (u, v), наружная нормаль и касательная в развёртке; за концами горловины —
        продолжение по касательной (клапан чуть длиннее горловины и закрывает её концы)."""
        if s < 0.0 or s > self.length:
            if s < 0.0:
                tan = (self.pts[1] - self.pts[0]).normalized()
                e = self.pts[0] + tan * s
            else:
                tan = (self.pts[-1] - self.pts[-2]).normalized()
                e = self.pts[-1] + tan * (s - self.length)
            return e, Vector((tan.y, -tan.x)), tan
        i = 0
        while i < len(self.cum) - 2 and self.cum[i + 1] < s:
            i += 1
        t = (s - self.cum[i]) / max(self.cum[i + 1] - self.cum[i], 1e-12)
        e = self.pts[i].lerp(self.pts[i + 1], t)
        tan = (self.pts[i + 1] - self.pts[i]).normalized()
        return e, Vector((tan.y, -tan.x)), tan

    def _base(self, s: float, t: float) -> tuple[Vector, Vector]:
        e, nn, tan = self.at(s)
        f = self.frame
        up = (f.point(e.x + nn.x * 0.001, e.y + nn.y * 0.001, 0.0) - f.point(e.x, e.y, 0.0)).normalized()
        if t <= self.arc:
            th = -math.pi / 2 + t / self.r
            q = e + nn * (self.r * math.cos(th))
            p = f.point(q.x, q.y, self.r * math.sin(th))
            n = (up * math.cos(th) + f.normal(e.x, e.y) * math.sin(th)).normalized()
        else:
            q = e - nn * (t - self.arc)
            p = f.point(q.x, q.y, self.r)
            n = f.normal(q.x, q.y)
        if self.ang:
            from mathutils import Matrix
            h = f.point(e.x, e.y, -self.r)
            # ось сгиба — касательная, усреднённая на ±5 см: у плечевых изгибов подковы соседние сечения
            # иначе поворачиваются вокруг слишком разных осей и ткань сминается в гармошку
            ts = [self.at(s + d)[2] for d in (-0.05, -0.025, 0.0, 0.025, 0.05)]
            tm = sum(ts, Vector((0.0, 0.0))).normalized()
            axis = (f.point(e.x + tm.x * 0.001, e.y + tm.y * 0.001, -self.r) - h).normalized()
            rot = Matrix.Rotation(self.ang, 3, axis)
            p = h + rot @ (p - h)
            n = rot @ n
        return p, n

    def hinge(self, s: float) -> Vector:
        return self._base(s, 0.0)[0]

    def far(self, s: float) -> float:
        """Длина клапана в сечении s: дуга через край и заход на лицевую сторону."""
        return self.arc + self.over(self.at(s)[0].x)

    def normal(self, s: float, t: float) -> Vector:
        return self._base(s, t)[1]

    def point(self, s: float, t: float, off: float = 0.0) -> Vector:
        p, n = self._base(s, t)
        return p + n * off


def mouth_curve(outline: list[Vec2], inset_d: float, mouth: Callable[[float, float], bool], step: float = 0.006,
                smooth: int = 3) -> list[Vec2]:
    """Линия горловины: контур, отступленный внутрь на inset_d, участок, где mouth(u, v), — по порядку обхода
    (против часовой), сглаженный (у плечевых углов выкройки малые скругления)."""
    outline = resample_closed(outline, step)
    if poly_area(outline) < 0:
        outline = outline[::-1]
    ins, _ = inset(outline, inset_d)
    n = len(ins)
    flags = [mouth(u, v) for u, v in ins]
    s0 = next(i for i in range(n) if flags[i] and not flags[i - 1])
    run = []
    for k in range(n):
        i = (s0 + k) % n
        if not flags[i]:
            break
        run.append(Vector(ins[i]))
    # Скользящее среднее на ±2,4 см: у плечевых углов выкройки отступленный контур почти острый, и край
    # клапана, заходящий на лицевую сторону, на нём перехлёстывался заломами.
    for _ in range(2):
        run = [run[0]] + [sum(run[max(0, i - 4):i + 5], Vector((0.0, 0.0))) / len(run[max(0, i - 4):i + 5])
                          for i in range(1, len(run) - 1)] + [run[-1]]
    for _ in range(smooth):
        sm = [run[0]]
        for i in range(len(run) - 1):
            sm.append(run[i].lerp(run[i + 1], 0.25))
            sm.append(run[i].lerp(run[i + 1], 0.75))
        sm.append(run[-1])
        run = sm
    return [(p.x, p.y) for p in run]


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
                 push: Callable[[Vector, Vector], Vector] | None = None, rows: int = 18, samples: int = 140,
                 vsmooth: int = 0, press: float = 0.0):
        """vsmooth — сколько раз сгладить контур по высоте и вдоль: у подмышки выпуклые сечения торса
        меняются скачками, и толстый камербанд по ним шёл волнами. Внутрь — не глубже press (пояс
        поджимает мягкую куртку, как плита)."""
        self.z_bot, self.height = z_bot, height
        self.rows = []
        raw = []
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
            raw.append((pts, ring.c))
        grid = [[p.copy() for p in pts] for pts, _ in raw]
        for _ in range(vsmooth):
            new = [[p.copy() for p in row] for row in grid]
            for j in range(len(grid)):
                cx, cy = raw[j][1]
                for k in range(len(grid[j])):
                    last = len(grid[j]) - 1             # концы пояса вдоль не сглаживать — иначе он укоротится
                    near = ((j - 1, k), (j + 1, k)) if k in (0, last) else ((j - 1, k), (j + 1, k), (j, k - 1), (j, k + 1))
                    nb = [grid[j2][k2] for j2, k2 in near if 0 <= j2 < len(grid)]
                    q = grid[j][k] * 0.5 + sum(nb, Vector()) * (0.5 / len(nb))
                    q.z = grid[j][k].z
                    o = raw[j][0][k]
                    r_o = math.hypot(o.x - cx, o.y - cy)
                    r_q = math.hypot(q.x - cx, q.y - cy)
                    if r_q < r_o - press:               # не глубже press в одежду
                        q.x = cx + (q.x - cx) * (r_o - press) / max(r_q, 1e-9)
                        q.y = cy + (q.y - cy) * (r_o - press) / max(r_q, 1e-9)
                    new[j][k] = q
            grid = new
        for pts in grid:
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

def weld_in_all_keys(bm: bmesh.types.BMesh, dist: float) -> None:
    """Сварка совпадающих вершин сетки с ключами формы — только там, где они совпадают во всех ключах: совпавшие
    в основе, но разные в ключе вершины после сварки тянули грани ключа через полподсумка (язычок под ПМ)."""
    from mathutils.kdtree import KDTree
    layers = list(bm.verts.layers.shape.values())
    bm.verts.ensure_lookup_table()
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    target: dict = {}
    for v in bm.verts:
        if v in target:
            continue
        for _, idx, _ in kd.find_range(v.co, dist):
            w = bm.verts[idx]
            if w is v or w in target or w in target.values():
                continue
            if all((v[lay] - w[lay]).length <= dist for lay in layers):
                target[w] = v
    if target:
        bmesh.ops.weld_verts(bm, targetmap=target)


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
              smooth: bool = True, origin: Vector | None = None,
              axes: tuple[Vector, Vector, Vector] | None = None,
              shape_keys: dict[str, "Mesh"] | None = None) -> bpy.types.Object:
        """origin — опорная точка объекта, axes — его оси (X, Y, Z, правая тройка): плита ходит вдоль своей Z.
        shape_keys — ключи формы из сеток той же топологии (клапан «Открыт»)."""
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
        if shape_keys:
            obj.shape_key_add(name="Basis", from_mix=False)
            for key_name, other in shape_keys.items():
                assert len(other.verts) == len(self.verts), f"{name}: ключ {key_name} — другая топология"
                kb = obj.shape_key_add(name=key_name, from_mix=False)
                kb.value = 0.0                  # новый ключ в Blender 5 включён (1) — клапан был откинут по умолчанию
                for i, p in enumerate(other.verts):
                    kb.data[i].co = p
        bm = bmesh.new()
        bm.from_mesh(me)
        if shape_keys:
            weld_in_all_keys(bm, 1e-6)
        else:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if origin is not None:
            # Опорная точка детали (шарнир клапана, центр плиты) — для будущей анимации.
            from mathutils import Matrix
            m = Matrix.Translation(origin)
            if axes is not None:
                m = m @ Matrix((axes[0], axes[1], axes[2])).transposed().to_4x4()
            me.transform(m.inverted(), shape_keys=True)
            obj.matrix_world = m
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
    return _cut_loops(out, nrm)


def _seg_cross(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> Vec2 | None:
    """Точка пересечения отрезков ab и cd (без касаний концами)."""
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-14:
        return None
    t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / den
    w = ((c[0] - a[0]) * ry - (c[1] - a[1]) * rx) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < w < 1 - 1e-9:
        return (a[0] + rx * t, a[1] + ry * t)
    return None


def _cut_loops(pts: list[Vec2], nrm: list[Vec2], window: int = 16) -> tuple[list[Vec2], list[Vec2]]:
    """Срезать петли («ласточкин хвост»), которые даёт отступ внутрь у острого угла с малым скруглением
    рядом с другим углом: из них по краю горловины кармана и по углам пакета торчали лепестки."""
    pts, nrm = list(pts), list(nrm)
    changed = True
    while changed and len(pts) > 8:
        changed = False
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            for k in range(2, min(window, n - 2)):
                j = (i + k) % n
                hit = _seg_cross(a, b, pts[j], pts[(j + 1) % n])
                if hit is None:
                    continue
                seq = [(j + 1 + t) % n for t in range(n - k)]       # от j+1 по кругу до i включительно
                na = Vector(nrm[i]) + Vector(nrm[(j + 1) % n])
                na = na.normalized() if na.length > 1e-9 else Vector(nrm[i])
                pts = [pts[s] for s in seq] + [hit]
                nrm = [nrm[s] for s in seq] + [(na.x, na.y)]
                changed = True
                break
            if changed:
                break
    return pts, nrm


def dist_to_poly(p: Vec2, poly: list[Vec2]) -> float:
    return gm._dist_to_poly(p, poly)


# ---------- детали ----------

def _sheet(m: Mesh, frame, ins: list[Vec2], boundary: list[int], off_fn: Callable[[float, float], float],
           step: float, mat: int, flip: bool) -> None:
    """Лист по контуру ins: вершины края — готовые (boundary[i]), внутри — сетка ~step и CDT."""
    n = len(ins)
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
    _, _, ofaces, orig, _, _ = mgeo.delaunay_2d_cdt(pts2, [], [list(range(n))], 1, 1e-9, True)
    remap = {k: o[0] for k, o in enumerate(orig) if o}
    ids = {}
    for k2, o in remap.items():
        if o < n:
            ids[k2] = boundary[o]
        else:
            u, v = interior[o - n]
            ids[k2] = m.v(frame.point(u, v, off_fn(u, v)))
    for f in ofaces:
        if not all(k2 in ids for k2 in f):
            continue
        idx = [ids[k2] for k2 in f]
        uv = [tuple(pts2[remap[k2]]) for k2 in f]
        if flip:
            idx, uv = idx[::-1], uv[::-1]
        m.f(idx, uv, mat)


def _face_off(ins: list[Vec2], half: float, bulge: float, binding: float,
              relief: Callable[[float, float], float] | None) -> Callable[[float, float, float], float]:
    def f(u: float, v: float, sign: float) -> float:
        d = dist_to_poly((u, v), ins)
        h = half
        if sign > 0:
            h += bulge * gm.smoothstep(d / 0.05)
            h += 0.0007 * gm.smoothstep((binding - d) / 0.002)
            if relief:
                h += relief(u, v)
        return sign * h
    return f


def _perimeter(ins: list[Vec2]) -> list[float]:
    per = [0.0]
    for i in range(1, len(ins) + 1):
        per.append(per[-1] + (Vector(ins[i % len(ins)]) - Vector(ins[i - 1])).length)
    return per


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
    face_off = _face_off(ins, r, bulge, binding, relief)
    # борт: кольца от внутренней стороны (−90°) к лицевой (+90°)
    K = 8
    rings, uvr = [], []
    per = _perimeter(ins)
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
    _sheet(m, frame, ins, rings[K], lambda u, v: face_off(u, v, 1.0), step, mat, False)
    if inner:
        _sheet(m, frame, ins, rings[0], lambda u, v: face_off(u, v, -1.0), step, mat, True)


def pocket_bag(m: Mesh, frame, outline: list[Vec2], cav: float, wall: float, mouth: Callable[[float, float], bool],
               mat: int = 0, step: float = 0.006, bulge: float = 0.003, binding: float = 0.011) -> None:
    """Пакет-карман под плиту: две стенки толщиной wall, между ними полость cav, по бокам и снизу —
    закруглённый борт, сверху (где mouth) — открытая горловина с закруглёнными губами стенок.
    Плиту можно вынуть вверх (под анимацию смены плит)."""
    outline = resample_closed(outline, step)
    if poly_area(outline) < 0:
        outline = outline[::-1]
    r = cav / 2 + wall
    ins, nrm = inset(outline, r)
    n = len(ins)
    is_m = [mouth(u, v) for u, v in ins]
    if not any(is_m) or all(is_m):
        padded_panel(m, frame, outline, 2 * r, mat, step, bulge, binding)
        return
    s0 = next(i for i in range(n) if not is_m[i] and is_m[i - 1])     # первый борт после горловины
    ins, nrm, is_m = ins[s0:] + ins[:s0], nrm[s0:] + nrm[:s0], is_m[s0:] + is_m[:s0]
    j0 = is_m.index(True)                                            # горловина — хвост списка
    face_off = _face_off(ins, r, bulge, binding, None)
    per = _perimeter(ins)
    fo = [m.v(frame.point(u, v, face_off(u, v, 1.0))) for u, v in ins]     # лицевая
    bo = [m.v(frame.point(u, v, face_off(u, v, -1.0))) for u, v in ins]    # к телу
    fc = [m.v(frame.point(u, v, cav / 2)) for u, v in ins]                 # полость, лицевая стенка
    bc = [m.v(frame.point(u, v, -cav / 2)) for u, v in ins]                # полость, задняя стенка
    K = 8

    def rim(radius: float, a: list[int], b: list[int], idx: list[int], kk: int, center: float = 0.0,
            scale: list[float] | None = None) -> list[list[int]]:
        rows = []
        for k in range(kk + 1):
            phi = -math.pi / 2 + math.pi * k / kk
            row = []
            for n_i, i in enumerate(idx):
                if k == 0:
                    row.append(a[i])
                elif k == kk:
                    row.append(b[i])
                else:
                    sc = scale[n_i] if scale else 1.0
                    u = ins[i][0] + nrm[i][0] * radius * math.cos(phi) * sc
                    v = ins[i][1] + nrm[i][1] * radius * math.cos(phi) * sc
                    row.append(m.v(frame.point(u, v, center + radius * math.sin(phi))))
            rows.append(row)
        return rows

    def uvs(rows: list[list[int]], idx: list[int], radius: float) -> list[list[Vec2]]:
        return [[(per[i], math.pi * radius * k / (len(rows) - 1)) for i in idx] for k in range(len(rows))]
    side = list(range(j0))
    outer = rim(r, bo, fo, side, K)
    m.grid(outer, uvs(outer, side, r), mat)
    inner = rim(cav / 2, bc, fc, side, K)
    m.grid(inner, uvs(inner, side, cav / 2), mat, flip=True)
    lip_idx = [j0 - 1] + list(range(j0, n)) + [0]
    # У концов горловины губа сходит в плоскость торца борта (нормаль контура там смотрит вбок, и полная
    # губа торчала лепестком сбоку от горловины).
    ramp = [0.0, 0.55, 0.85]
    lip_sc = [min(1.0, ramp[min(k, len(lip_idx) - 1 - k)] if min(k, len(lip_idx) - 1 - k) < len(ramp) else 1.0)
              for k in range(len(lip_idx))]
    back_lip = rim(wall / 2, bo, bc, lip_idx, 4, -(cav / 2 + wall / 2), lip_sc)
    m.grid(back_lip, uvs(back_lip, lip_idx, wall / 2), mat)
    front_lip = rim(wall / 2, fc, fo, lip_idx, 4, cav / 2 + wall / 2, lip_sc)
    m.grid(front_lip, uvs(front_lip, lip_idx, wall / 2), mat)
    for col_i in (len(side) - 1, 0):                                 # торцы борта у горловины
        oc = [outer[k][col_i] for k in range(K + 1)]
        ic = [inner[k][col_i] for k in range(K + 1)]
        m.grid([oc, ic], [[(0.0, k * 0.01) for k in range(K + 1)], [(0.004, k * 0.01) for k in range(K + 1)]], mat,
               flip=(col_i == 0))
    _sheet(m, frame, ins, fo, lambda u, v: face_off(u, v, 1.0), step, mat, False)
    _sheet(m, frame, ins, bo, lambda u, v: face_off(u, v, -1.0), step, mat, True)
    _sheet(m, frame, ins, fc, lambda u, v: cav / 2, step, mat, True)
    _sheet(m, frame, ins, bc, lambda u, v: -cav / 2, step, mat, False)


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
                ut.append((u - u0, v - vr))          # от начала ряда: тайл закрепок (шаг pitch) — на закрепках
                ub.append((u - u0, v - vr + 0.05))
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
          taper: float = 0.0, stations: list[float] | None = None, top_div: int = 0,
          relief: Callable[[float, float], float] | None = None) -> None:
    """Лента (стропа, лямка, накладка): сечение со скруглёнными боками. taper — длина, на которой
    концы сходят на нет (у мягкой накладки торцы скруглены, а не обрублены). stations — свои сечения по длине
    (вместо равного шага), top_div — точек поперёк плоских верха и низа (для продавленных строчек), relief(u, x) —
    сдвиг верхней грани по высоте (строчка продавливает стропу)."""
    u1 = frame.length if u1 is None else u1
    nu = max(2, int(round((u1 - u0) / step)))
    us = stations if stations is not None else [u0 + (u1 - u0) * i / nu for i in range(nu + 1)]
    K = 3 if round_edges else 1
    hw = width / 2
    # правая половина сечения: от верха через бок к низу; левая — зеркально
    half = []
    for k in range(2 * K + 1):
        a = math.pi / 2 - math.pi * k / (2 * K)
        half.append((hw - thick / 2 + thick / 2 * math.cos(a), thick / 2 + thick / 2 * math.sin(a)))
    full = half + [(-x, y) for x, y in half[::-1]]
    if top_div:
        xe = hw - thick / 2
        bottom = [(xe - 2 * xe * k / (top_div + 1), 0.0) for k in range(1, top_div + 1)]
        top = [(-xe + 2 * xe * k / (top_div + 1), thick) for k in range(1, top_div + 1)]
        full = half + bottom + [(-x, y) for x, y in half[::-1]] + top
    rows, uvrows = [], []
    for u in us:
        sc = 1.0
        if taper > 0:
            e = min(u - u0, u1 - u) / taper
            sc = 0.35 + 0.65 * math.sqrt(max(0.0, min(1.0, e)) * (2 - min(1.0, e)))
        row, urow = [], []
        acc = 0.0
        for k, (x, y) in enumerate(full):
            dy = relief(u, x) if relief is not None and y >= thick * 0.999 else 0.0
            row.append(m.v(frame.point(u, x * (0.6 + 0.4 * sc), base_off + y * sc + dy)))
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


def zipper(tape: Mesh, teeth: Mesh, rib: RibbonFrame, base_off: float = 0.0, pull_at: float | None = None,
           tape_w: float = 0.020, pitch: float = 0.0042) -> None:
    """Молния: лента и звенья в шахматном порядке (сцеплены), pull_at — где бегунок с язычком."""
    strap(tape, rib, tape_w, 0.0012, base_off, step=0.006)
    n = max(2, int(rib.length / pitch))
    for i in range(n):
        p, tan, nn = rib._at((i + 0.5) * rib.length / n)
        side = nn.cross(tan).normalized()
        c = p + nn * (base_off + 0.0019) + side * (0.0011 if i % 2 else -0.0011)
        box(teeth, c, side, tan, nn, (0.0058, 0.0026, 0.0018))
    if pull_at is not None:
        p, tan, nn = rib._at(pull_at)
        side = nn.cross(tan).normalized()
        rbox(teeth, p + nn * (base_off + 0.0042), side, tan, nn, (0.0095, 0.016, 0.0045), 0.002)
        rbox(teeth, p + nn * (base_off + 0.0070) - tan * 0.017, side, tan, nn, (0.0075, 0.024, 0.0018), 0.0025)


def cord_lock(m: Mesh, center: Vector, ax: Vector, ay: Vector, az: Vector, mat: int = 0) -> None:
    """Фиксатор шнура: бочонок с кнопкой; ay — вдоль шнура."""
    rbox(m, center, ax, ay, az, (0.013, 0.020, 0.010), 0.0055, mat=mat)
    rbox(m, center - ay * 0.012, ax, ay, az, (0.008, 0.006, 0.007), 0.003, mat=mat)


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
