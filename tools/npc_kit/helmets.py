"""NPC: шлемы трёх уровней (решение владельца 2026-10-22, docs/design/gear_v2.md) — форма на мародёре v03.

- Простой — старая стальная каска (тип СШ-68): купол с наклоном вперёд, короткий отогнутый край по кругу (сзади
  длиннее), завальцованная кромка, заклёпки подтулейника, подтулейник из кожзама, подбородочный ремень с пряжкой.
  Креплений нет.
- Средний — современный армейский шлем полного покроя в чехле (тип 6Б47): гладкий купол, над ушами подрезан,
  чехол с резинкой по кромке, липучки по бокам и сзади, спереди площадка под ПНВ (гнездо, три винта),
  четырёхточечная подвеска с чашкой подбородка.
- Крутой — тяжёлый шлем высокого среза (high-cut): кромка в резиновом окантовочном профиле, по бокам планки
  (на правой — фонарь), спереди площадка ПНВ с резинками-растяжками к планкам, откидное баллистическое забрало
  на рычагах от передних концов планок, липучки сверху и сзади, регулятор подвески (колесо) сзади, подвеска.

Купол строится по замерам головы в балаклаве: лучи от центра головы, сечения выпуклые, сверху зазор под
подвеску больше; кромка у каждого своя (линия возвышения по азимуту). Развёртка «шапкой» (CapFrame): макушка —
центр, без особой точки. Марок нет. Каждый шлем — своя коллекция (06_Helmet_*), переключение в Outliner.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/helmets.py -- [render] [deliver=<папка>]
→ _asset_src/npc_kit/helmets/helmets.blend (читает мародёра kit_common.npc_file())
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "helmets"
R0 = 0.10                      # опорный радиус развёртки купола (м)


# ---------- купол ----------

EAR_AZ = 6.0                   # ухо: азимут центра на стороне +X (левой у персонажа, лицо в −Y); на правой — 180 − EAR_AZ
# Ухо на балаклаве мародёра v03 (замер по выпуклости трикотажа): центр по |x|, y, z и полуоси эллипса по y и z.
# Ремни подвески обходят его: передний — перед ухом, задний — за ухом и под мочкой, развилка ниже уха.
EAR_X, EAR_Y, EAR_Z = 0.088, -0.045, 1.670
EAR_HY, EAR_HZ = 0.019, 0.032


def smooth_rim(front: float, side: float, back: float, ear: float = 0.0, ear_w: float = 15.0):
    """Кромка шлема без изломов: возвышение (градусы) спереди / сбоку / сзади — два гармонических члена по азимуту,
    над ушами — подъём на ear градусов шириной ear_w (вырез над ухом, высокий срез)."""
    c1 = (front - back) / 2
    c0 = ((front + back) / 2 + side) / 2
    c2 = ((front + back) / 2 - side) / 2

    def f(az: float) -> float:
        t = math.radians(az + 90.0)
        v = c0 + c1 * math.cos(t) + c2 * math.cos(2 * t)
        if ear:
            for centre in (EAR_AZ, 180.0 - EAR_AZ):
                d = (az - centre + 180.0) % 360.0 - 180.0
                v += ear * math.exp(-(d / ear_w) ** 2)
        return v
    return f


class Head:
    """Голова в балаклаве: радиус по направлению от центра (лучи снаружи внутрь)."""

    def __init__(self, objs: list[bpy.types.Object], c: Vector):
        co, faces = [], []
        dg = bpy.context.evaluated_depsgraph_get()
        for o in objs:
            eo = o.evaluated_get(dg)
            me = eo.to_mesh()
            base = len(co)
            co += [o.matrix_world @ v.co for v in me.vertices]
            faces += [[base + i for i in p.vertices] for p in me.polygons]
            eo.to_mesh_clear()
        self.bvh = BVHTree.FromPolygons(co, faces)
        self.c = c

    def radius(self, d: Vector) -> float | None:
        hit = self.bvh.ray_cast(self.c + d * 0.4, -d, 0.4)
        return (hit[0] - self.c).dot(d) if hit[0] is not None else None


def direction(az: float, el: float) -> Vector:
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))


class CapFrame:
    """Купол «шапкой»: (x, y) — плоскость развёртки, ρ = (90° − возвышение)·R0, угол — азимут (0 — +X, −90 — перёд).
    Радиус r(az, el) — сетка замеров головы + зазор, сечения выпуклые, сглажено; flare(az, el) — отгиб края."""

    def __init__(self, head: Head, standoff, min_gap: float = 0.010, el_min: float = -45.0, flare=None):
        self.c = head.c
        self.daz, self.del_ = 3.0, 2.5
        self.el_min = el_min
        self.na = int(360 / self.daz)
        self.ne = int((90 - el_min) / self.del_) + 1
        raw = []
        for j in range(self.ne):
            el = el_min + j * self.del_
            row = []
            for i in range(self.na):
                az = i * self.daz
                r = head.radius(direction(az, el))
                row.append(r)
            raw.append(row)
        # пропуски (луч прошёл в прорезь балаклавы) — по азимуту между ближайшими замерами
        for j in range(self.ne):
            row = raw[j]
            known = [i for i, r in enumerate(row) if r is not None]
            if not known:
                raw[j] = raw[j - 1][:] if j else [0.09] * self.na
                continue
            out = []
            for i, r in enumerate(row):
                if r is not None:
                    out.append(r)
                    continue
                left = max((k for k in known if k < i), default=known[-1] - self.na)
                right = min((k for k in known if k > i), default=known[0] + self.na)
                t = (i - left) / max(right - left, 1)
                out.append(row[left % self.na] * (1 - t) + row[right % self.na] * t)
            raw[j] = out
        need = [[raw[j][i] + standoff(i * self.daz, el_min + j * self.del_) for i in range(self.na)] for j in range(self.ne)]
        # сечения выпуклые (по горизонтали)
        g = []
        for j in range(self.ne):
            el = el_min + j * self.del_
            ce = max(math.cos(math.radians(el)), 1e-3)
            pts = [(need[j][i] * ce * math.cos(math.radians(i * self.daz)), need[j][i] * ce * math.sin(math.radians(i * self.daz)))
                   for i in range(self.na)]
            hull = gm._hull(pts)
            g.append([max(need[j][i], hull_ray(hull, i * self.daz) / ce) for i in range(self.na)])
        # сгладить (по азимуту периодично, по возвышению), не глубже нужного
        for _ in range(16):
            new = [row[:] for row in g]
            for j in range(self.ne):
                for i in range(self.na):
                    nb = [g[j][(i - 1) % self.na], g[j][(i + 1) % self.na]]
                    if j > 0:
                        nb.append(g[j - 1][i])
                    if j < self.ne - 1:
                        nb.append(g[j + 1][i])
                    v = 0.5 * g[j][i] + 0.5 * sum(nb) / len(nb)
                    new[j][i] = max(v, raw[j][i] + min_gap)
            g = new
        self.g = g
        self.flare = flare

    def r(self, az: float, el: float) -> float:
        """Радиус купола: сетка — сплайном Катмулла — Рома (без изломов по линиям сетки), отгиб края — точно."""
        fi = (az % 360.0) / self.daz
        fj = max(0.0, min(self.ne - 1.0001, (el - self.el_min) / self.del_))
        i0, j0 = int(fi), int(fj)
        ti, tj = fi - i0, fj - j0
        g = self.g
        col = []
        for dj in (-1, 0, 1, 2):
            j = max(0, min(self.ne - 1, j0 + dj))
            row = g[j]
            col.append(catmull(row[(i0 - 1) % self.na], row[i0 % self.na], row[(i0 + 1) % self.na],
                               row[(i0 + 2) % self.na], ti))
        v = catmull(col[0], col[1], col[2], col[3], tj)
        return v + (self.flare(az, el) if self.flare is not None else 0.0)

    @staticmethod
    def ae(x: float, y: float) -> tuple[float, float]:
        rho = math.hypot(x, y)
        az = math.degrees(math.atan2(y, x))
        el = 90.0 - math.degrees(rho / R0)
        return az, el

    @staticmethod
    def xy(az: float, el: float) -> tuple[float, float]:
        rho = math.radians(90.0 - el) * R0
        return rho * math.cos(math.radians(az)), rho * math.sin(math.radians(az))

    def _raw(self, x: float, y: float) -> Vector:
        az, el = self.ae(x, y)
        return self.c + direction(az, el) * self.r(az, el)

    def normal(self, x: float, y: float) -> Vector:
        h = 0.002
        du = self._raw(x + h, y) - self._raw(x - h, y)
        dv = self._raw(x, y + h) - self._raw(x, y - h)
        n = du.cross(dv)
        az, el = self.ae(x, y)
        out = direction(az, el)
        if n.length < 1e-12:
            return out
        n.normalize()
        return n if n.dot(out) > 0 else -n

    def point(self, x: float, y: float, off: float = 0.0) -> Vector:
        return self._raw(x, y) + self.normal(x, y) * off


def catmull(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    return 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3)


def hull_ray(hull: list[tuple[float, float]], az: float) -> float:
    """Расстояние от центра до выпуклой оболочки (вершины против часовой) по лучу азимута az (градусы)."""
    dx, dy = math.cos(math.radians(az)), math.sin(math.radians(az))
    best = 0.0
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
    return best


def rim_outline(rim, n: int = 180) -> list[tuple[float, float]]:
    """Кромка шлема в плоскости развёртки: по азимуту — возвышение кромки rim(az) (градусы)."""
    return [CapFrame.xy(360.0 * k / n, rim(360.0 * k / n)) for k in range(n)]


def rim_curve(cap: CapFrame, rim, off: float, n: int = 240) -> list[Vector]:
    pts = []
    for k in range(n + 1):
        az = 360.0 * k / n
        x, y = CapFrame.xy(az, rim(az))
        pts.append(cap.point(x, y, off))
    return pts


def ring_tube(m: ak.Mesh, pts: list[Vector], radius: float, sides: int = 8, mat: int = 0) -> None:
    """Замкнутая трубка (кромка, окантовка): рамка переносится по кругу без закручивания, а набежавший за оборот
    поворот сечения раскладывается по длине — последнее кольцо совпадает с первым, шва нет."""
    if (pts[0] - pts[-1]).length < 1e-7:
        pts = pts[:-1]
    n = len(pts)
    tans = [(pts[(i + 1) % n] - pts[i - 1]).normalized() for i in range(n)]
    nrm = [tans[0].orthogonal().normalized()]
    for i in range(1, n + 1):
        t = tans[i % n]
        v = nrm[-1] - t * nrm[-1].dot(t)
        nrm.append(v.normalized())
    end, start = nrm[n], nrm[0]
    twist = math.atan2(tans[0].dot(end.cross(start)), end.dot(start))
    rows = []
    for i in range(n):
        t = tans[i]
        a = twist * i / n
        nn = nrm[i]
        b = t.cross(nn)
        nn, b = nn * math.cos(a) + b * math.sin(a), b * math.cos(a) - nn * math.sin(a)
        rows.append([m.v(pts[i] + (nn * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * radius)
                     for k in range(sides)])
    rows.append(rows[0])
    m.grid(rows, [[(i * 0.01, k / sides) for k in range(sides)] for i in range(len(rows))], mat, closed_u=True)


def patch(m: ak.Mesh, cap: CapFrame, az: float, el: float, w: float, h: float, r: float, off: float, thick: float,
          mat: int = 0) -> None:
    """Плоская накладка на купол (липучка, площадка): прямоугольник w×h (м) со скруглением r вокруг (az, el)."""
    x0, y0 = CapFrame.xy(az, el)
    # оси в плоскости развёртки: «вдоль» — по азимуту, «вверх» — к макушке
    rho = math.hypot(x0, y0)
    ux, uy = (-y0 / rho, x0 / rho) if rho > 1e-6 else (1.0, 0.0)
    vx, vy = (-x0 / rho, -y0 / rho) if rho > 1e-6 else (0.0, 1.0)
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        corners.append((x0 + ux * sx * w / 2 + vx * sy * h / 2, y0 + uy * sx * w / 2 + vy * sy * h / 2))
    if ak.poly_area(corners) < 0:
        corners = corners[::-1]
    ak.padded_panel(m, ak.OffsetFrame(cap, off + thick / 2), ak.rounded_poly(corners, [r] * 4), thick, mat=mat,
                    bulge=0.0005, binding=0.0, step=0.003)


def strap_on_head(m: ak.Mesh, head: Head, pts: list[Vector], width: float, thick: float = 0.0025, lift: float = 0.003) -> ak.RibbonFrame:
    """Ремень по поверхности балаклавы: путь сглажен и снова положен на голову (+ lift), нормали — с поверхности."""
    out = [surface(head, p)[0] for p in pts]
    for _ in range(10):
        out = [out[0]] + [(out[i - 1] + out[i] * 2 + out[i + 1]) / 4 for i in range(1, len(out) - 1)] + [out[-1]]
        out = [surface(head, p)[0] for p in out]
    nrm = [surface(head, p)[1] for p in out]
    out = [p + n * lift for p, n in zip(out, nrm)]
    rib = ak.RibbonFrame(out, nrm)
    ak.strap(m, rib, width, thick)
    return rib


def cyl(m: ak.Mesh, a: Vector, b: Vector, r: float, sides: int = 16, mat: int = 0) -> None:
    """Цилиндр с донцами (корпус фонаря, колесо регулятора)."""
    ak.tube(m, [a, b], r, mat=mat, sides=sides)
    ax = (b - a).normalized()
    t = ax.orthogonal().normalized()
    bb = ax.cross(t)
    for c, flip in ((a, True), (b, False)):
        ring = [m.v(c + (t * math.cos(2 * math.pi * k / sides) + bb * math.sin(2 * math.pi * k / sides)) * r)
                for k in range(sides)]
        ci = m.v(c)
        for k in range(sides):
            f = [ring[k], ring[(k + 1) % sides], ci]
            m.f(f[::-1] if flip else f, [(0, 0), (1, 0), (0.5, 1)], mat)


def on_cap(cap: "CapFrame", a: tuple[float, float], b: tuple[float, float], off: float, n: int = 24) -> list[Vector]:
    """Путь по куполу между (az, el) a и b — шнур или растяжка лежит на оболочке, а не режет её."""
    out = []
    for k in range(n + 1):
        t = k / n
        x, y = CapFrame.xy(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        out.append(cap.point(x, y, off))
    return out


def deg_along(cap_r: float, el: float, d: float) -> float:
    """Сколько градусов азимута на d метров по горизонтали на возвышении el."""
    return math.degrees(d / max(cap_r * math.cos(math.radians(el)), 1e-3))


def surface(head: Head, p: Vector) -> tuple[Vector, Vector]:
    """Ближайшая точка балаклавы и нормаль наружу."""
    loc, n, _, _ = head.bvh.find_nearest(p)
    if n.dot(loc - head.c) < 0:
        n = -n
    return loc, n


def lerp_path(pts: list[Vector], n: int = 10) -> list[Vector]:
    out = []
    for a, b in zip(pts, pts[1:]):
        out += [a.lerp(b, k / n) for k in range(n)]
    return out + [pts[-1]]


# ---------- материалы ----------

def materials() -> dict:
    glass = bpy.data.materials.new("Helmet_Visor_Glass")
    glass.use_nodes = True
    p = next(n for n in glass.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (0.85, 0.88, 0.86, 1.0)
    p.inputs["Roughness"].default_value = 0.04
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = 1.58
    return {
        "steel": kc.clay("Helmet_Steel_Paint", (0.10, 0.12, 0.08), 0.55),
        "cover": kc.clay("Helmet_Cover", (0.16, 0.16, 0.12), 0.88),
        "shell": kc.clay("Helmet_Shell", (0.13, 0.12, 0.10), 0.6),
        "rubber": kc.clay("Helmet_Rubber", (0.025, 0.025, 0.025), 0.75),
        "webbing": kc.clay("Helmet_Webbing", (0.10, 0.10, 0.08), 0.8),
        "velcro": kc.clay("Helmet_Velcro", (0.045, 0.045, 0.035), 0.95),
        "plastic": kc.clay("Helmet_Plastic", (0.04, 0.04, 0.04), 0.45),
        "metal": kc.clay("Helmet_Metal", (0.30, 0.30, 0.30), 0.35),
        "leather": kc.clay("Helmet_Leatherette", (0.06, 0.035, 0.02), 0.6),
        "glass": glass,
    }


# ---------- шлемы ----------

def chin_harness(m: ak.Mesh, head: Head, cap: CapFrame, rim, metal: ak.Mesh, plastic: ak.Mesh, four_point: bool,
                 width: float = 0.018) -> None:
    """Подвеска: от кромки у виска — перед ухом, у четырёхточечной ещё от кромки за ухом — за ухом и под мочкой;
    сходятся на развилке ниже и впереди уха, от неё — под подбородок. Сквозь ухо ремни не идут (EAR_*)."""
    chin, chin_n = surface(head, head.c + Vector((0.0, -0.075, -0.135)))
    for sgn in (1.0, -1.0):
        az_front, az_back = (-25.0, 30.0) if sgn > 0 else (205.0, 150.0)
        fork, fork_n = surface(head, Vector((sgn * (EAR_X - 0.004), EAR_Y - 0.032, EAR_Z - 0.058)))
        x, y = CapFrame.xy(az_front, rim(az_front) + 4.0)
        top_f = cap.point(x, y, -0.004)
        strap_on_head(m, head, lerp_path([top_f, fork], n=24), width)
        if four_point:
            x, y = CapFrame.xy(az_back, rim(az_back) + 4.0)
            top_b = cap.point(x, y, -0.004)
            behind = Vector((sgn * (EAR_X - 0.002), EAR_Y + EAR_HY + 0.012, EAR_Z - 0.050))   # за мочкой
            strap_on_head(m, head, lerp_path([top_b, behind, fork], n=16), width)
            ay = fork_n.cross(Vector((0, 1, 0))).normalized()
            ak.rbox(plastic, fork + fork_n * 0.007, ay.cross(fork_n).normalized(), ay, fork_n, (0.024, 0.016, 0.006), 0.004)
        # под подбородок
        mid = head.c + Vector((sgn * 0.055, -0.07, -0.125))
        strap_on_head(m, head, lerp_path([fork, mid, chin]), width)
    up = chin_n.cross(Vector((1, 0, 0))).normalized()
    ak.rbox(plastic, chin + chin_n * 0.008, up.cross(chin_n).normalized(), up, chin_n, (0.034, 0.024, 0.008), 0.008)


def check_straps(head: Head, col: bpy.types.Collection) -> tuple[float, int]:
    """Ремни подвески: наименьший зазор до балаклавы (м, меньше нуля — ремень ушёл внутрь) и сколько вершин
    ремней лежит на ухе (в эллипсе EAR_* на боку головы)."""
    gap, on_ear = 1.0, 0
    for o in col.objects:
        if not any(k in o.name for k in ("Harness", "Strap")):
            continue
        for v in o.data.vertices:
            p = o.matrix_world @ v.co
            loc, n = surface(head, p)
            gap = min(gap, (p - loc).dot(n))
            if abs(p.x) > EAR_X - 0.025 and ((p.y - EAR_Y) / EAR_HY) ** 2 + ((p.z - EAR_Z) / EAR_HZ) ** 2 < 1.0:
                on_ear += 1
    return gap, on_ear


def build_simple(col, mats, head: Head) -> None:
    """Старая стальная каска (тип СШ-68)."""
    rim = smooth_rim(15.0, -10.0, -24.0)

    def standoff(az: float, el: float) -> float:
        return 0.016 + 0.010 * max(0.0, math.sin(math.radians(el)))

    def flare(az: float, el: float) -> float:
        # край отогнут наружу на последних ~5° возвышения; сзади сильнее
        t = max(0.0, min(1.0, (rim(az) + 8.0 - el) / 8.0))
        back = max(0.0, math.sin(math.radians(az)))
        return 0.016 * (t * t) * (0.6 + 0.8 * back)
    cap = CapFrame(head, standoff, flare=flare)
    shell, metal, leather, web, plastic = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()
    t = 0.003
    ak.padded_panel(shell, ak.OffsetFrame(cap, t / 2), rim_outline(rim), t, bulge=0.0, binding=0.0, step=0.004)
    ring_tube(shell, rim_curve(cap, lambda a: rim(a) + 0.15, t / 2), 0.0024, sides=8)       # завальцованная кромка
    # заклёпки подтулейника
    for az, el in ((0.0, 8.0), (180.0, 8.0), (90.0, 4.0), (-50.0, 18.0), (230.0, 18.0)):
        x, y = CapFrame.xy(az, el)
        p = cap.point(x, y, t + 0.0012)
        n = cap.normal(x, y)
        ak.rbox(metal, p, n.orthogonal().normalized(), n.cross(n.orthogonal()).normalized(), n, (0.008, 0.008, 0.0024), 0.0038)
    # подтулейник: ремень из кожзама изнутри по кромке
    inner = [p for p in rim_curve(cap, lambda a: rim(a) + 11.0, -0.012, n=180)]
    nrm = [(p - head.c).normalized() for p in inner]
    ak.strap(leather, ak.RibbonFrame(inner, nrm), 0.022, 0.002)
    chin_harness(web, head, cap, rim, metal, plastic, four_point=False, width=0.016)
    shell.build("Helmet_Simple_Shell", col, [mats["steel"]])
    metal.build("Helmet_Simple_Rivets", col, [mats["metal"]])
    leather.build("Helmet_Simple_Liner", col, [mats["leather"]])
    web.build("Helmet_Simple_Strap", col, [mats["webbing"]])
    plastic.build("Helmet_Simple_Buckle", col, [mats["plastic"]])


def nvg_mount(cap: CapFrame, plate: ak.Mesh, metal: ak.Mesh, shell_t: float, el: float = 33.0) -> tuple[Vector, Vector]:
    """Площадка ПНВ спереди: пластина по куполу, гнездо внизу, три винта. Возвращает (гнездо, нормаль)."""
    patch(plate, cap, -90.0, el, 0.058, 0.042, 0.010, shell_t, 0.005)
    x, y = CapFrame.xy(-90.0, el - 3.0)
    n = cap.normal(x, y)
    p = cap.point(x, y, shell_t + 0.012)
    side = Vector((1.0, 0.0, 0.0))
    up = n.cross(side).normalized()
    ak.rbox(plate, p, side, up, n, (0.026, 0.020, 0.014), 0.004)
    # винты треугольником: верхний по центру, два нижних по бокам от гнезда
    for dx, dz in ((0.0, 1.0), (-0.022, -1.0), (0.022, -1.0)):
        xx, yy = CapFrame.xy(-90.0 + deg_along(0.13, el, dx), el + 6.0 * dz)
        q = cap.point(xx, yy, shell_t + 0.0055)
        nn = cap.normal(xx, yy)
        ak.torus(metal, q, nn, 0.0028, 0.0012, seg=12, sides=6)
    return p, n


def back_hardware(cap: CapFrame, head: Head, rim, web: ak.Mesh, plastic: ak.Mesh, shell_t: float) -> None:
    """Затылочный ремень подвески под кромкой сзади и колесо регулятора на нём."""
    pts = []
    for k in range(17):
        az = 35.0 + 110.0 * k / 16
        drop = 4.0 + 9.0 * math.sin(math.pi * k / 16)
        x, y = CapFrame.xy(az, rim(az) - drop)
        pts.append(cap.point(x, y, -0.010))
    strap_on_head(web, head, pts, 0.024, thick=0.004)
    x, y = CapFrame.xy(90.0, rim(90.0) - 13.0)
    loc, n = surface(head, cap.point(x, y, -0.010))
    cyl(plastic, loc + n * 0.004, loc + n * 0.015, 0.017, sides=24)


def build_mid(col, mats, head: Head) -> None:
    """Армейский шлем полного покроя в чехле (тип 6Б47), площадка ПНВ."""
    rim = smooth_rim(14.0, -12.0, -22.0, ear=16.0, ear_w=13.0)

    def standoff(az: float, el: float) -> float:
        return 0.018 + 0.010 * max(0.0, math.sin(math.radians(el)))
    cap = CapFrame(head, standoff)
    shell, hem, velc, plate, metal, web, plastic = (ak.Mesh() for _ in range(7))
    t = 0.010
    ak.padded_panel(shell, ak.OffsetFrame(cap, t / 2), rim_outline(rim), t, bulge=0.0, binding=0.0, step=0.006)
    ring_tube(hem, rim_curve(cap, rim, t / 2), t / 2 + 0.0025, sides=10)                     # чехол обжимает кромку
    for az, el, w, h in ((0.0, 22.0, 0.065, 0.045), (180.0, 22.0, 0.065, 0.045), (90.0, 20.0, 0.09, 0.05)):
        patch(velc, cap, az, el, w, h, 0.008, t + 0.001, 0.003)
    nvg_mount(cap, plate, metal, t)
    back_hardware(cap, head, rim, web, plastic, t)
    chin_harness(web, head, cap, rim, metal, plastic, four_point=True)
    shell.build("Helmet_Mid_Shell", col, [mats["cover"]])
    hem.build("Helmet_Mid_Cover_Hem", col, [mats["cover"]])
    velc.build("Helmet_Mid_Velcro", col, [mats["velcro"]])
    plate.build("Helmet_Mid_NVG_Mount", col, [mats["plastic"]])
    metal.build("Helmet_Mid_Screws", col, [mats["metal"]])
    web.build("Helmet_Mid_Harness", col, [mats["webbing"]])
    plastic.build("Helmet_Mid_Buckles", col, [mats["plastic"]])


def rail(m: ak.Mesh, cap: CapFrame, az0: float, az1: float, rim, shell_t: float) -> ak.RibbonFrame:
    """Планка на боку купола (над вырезом): лента 21 мм с пазами через 10 мм."""
    pts, nrm = [], []
    for k in range(25):
        az = az0 + (az1 - az0) * k / 24
        el = rim(az) + 9.0
        x, y = CapFrame.xy(az, el)
        pts.append(cap.point(x, y, shell_t + 0.004))
        nrm.append(cap.normal(x, y))
    rib = ak.RibbonFrame(pts, nrm)
    L = rib.length

    def slots(u: float, v: float) -> float:
        ph = (u / 0.010) % 1.0
        return -0.0016 if (0.35 < ph < 0.65 and abs(v) < 0.007) else 0.0
    ak.padded_panel(m, rib, ak.rounded_poly([(0.0, -0.0105), (L, -0.0105), (L, 0.0105), (0.0, 0.0105)], [0.004] * 4),
                    0.008, bulge=0.0, binding=0.0, relief=slots, step=0.0015)
    return rib


def build_top(col, mats, head: Head) -> None:
    """Тяжёлый шлем высокого среза: планки, фонарь, площадка ПНВ, баллистическое забрало."""
    rim = smooth_rim(14.0, -10.0, -18.0, ear=28.0, ear_w=40.0)

    def standoff(az: float, el: float) -> float:
        return 0.018 + 0.010 * max(0.0, math.sin(math.radians(el)))
    cap = CapFrame(head, standoff)
    shell, trim, rails, velc, plate, metal, web, plastic, light, glass = (ak.Mesh() for _ in range(10))
    t = 0.010
    ak.padded_panel(shell, ak.OffsetFrame(cap, t / 2), rim_outline(rim), t, bulge=0.0, binding=0.0, step=0.006)
    ring_tube(trim, rim_curve(cap, rim, t / 2), t / 2 + 0.0022, sides=10)                    # резиновый профиль кромки
    rl = rail(rails, cap, -45.0, 32.0, rim, t)
    rr = rail(rails, cap, 225.0, 148.0, rim, t)
    for az, el, w, h in ((-90.0, 62.0, 0.07, 0.11), (90.0, 30.0, 0.10, 0.05)):
        patch(velc, cap, az, el, w, h, 0.010, t + 0.001, 0.003)
    nvg_mount(cap, plate, metal, t, el=30.0)
    # резинки-растяжки от верха площадки ПНВ по куполу к задним концам планок
    for az_end in (32.0, 148.0):
        sgn = 1.0 if az_end < 90 else -1.0
        start = (-90.0 + sgn * deg_along(0.13, 33.0, 0.026), 33.0)
        end_az = az_end - sgn * 4.0
        end = (end_az, rim(end_az) + 14.0)                 # над верхним краем планки, к её заднему концу
        if end[0] - start[0] > 180.0:
            end = (end[0] - 360.0, end[1])
        elif start[0] - end[0] > 180.0:
            end = (end[0] + 360.0, end[1])
        ak.tube(web, on_cap(cap, start, end, t + 0.0035), 0.0016, sides=6)
    for rib in (rl, rr):
        back = rib.point(rib.length - 0.006, 0.0, 0.007)
        tan = (rib.point(rib.length, 0, 0) - rib.point(rib.length - 0.01, 0, 0)).normalized()
        nn = rib.normal(rib.length, 0)
        ak.rbox(plastic, back, tan, nn.cross(tan).normalized(), nn, (0.014, 0.012, 0.006), 0.003)
    # фонарь на правой планке (ближе к переду): крепление и корпус вдоль планки
    # правая планка идёт от переда назад: «вперёд» для фонаря — против её направления
    u = 0.035
    p0 = rr.point(u, 0.0, 0.010)
    fwd = (rr.point(u - 0.01, 0, 0) - rr.point(u, 0, 0)).normalized()
    nrm = rr.normal(u, 0)
    ak.rbox(plastic, p0, fwd, nrm.cross(fwd).normalized(), nrm, (0.03, 0.022, 0.012), 0.004)
    body_c = p0 + nrm * 0.026
    cyl(light, body_c - fwd * 0.040, body_c + fwd * 0.045, 0.0105)
    cyl(light, body_c + fwd * 0.045, body_c + fwd * 0.058, 0.0135)                     # голова фонаря
    cyl(glass, body_c + fwd * 0.0582, body_c + fwd * 0.0590, 0.0115)                   # стекло фонаря
    cyl(light, body_c - fwd * 0.046, body_c - fwd * 0.040, 0.0085)                     # торцевая кнопка
    back_hardware(cap, head, rim, web, plastic, t)
    chin_harness(web, head, cap, rim, metal, plastic, four_point=True)
    # баллистическое забрало: щиток от козырька до подбородка, по лицу эллипсом; верхние углы — у шарниров
    # на передних концах планок, верх идёт под кромкой и поднимается к шарнирам
    pivots = [rib.point(0.004, 0.0, 0.007) for rib in (rl, rr)]
    piv_x = sum(abs(q.x) for q in pivots) / 2
    piv_y = sum(q.y for q in pivots) / 2
    piv_z = sum(q.z for q in pivots) / 2
    phi_max = math.radians(62.0)
    cy = head.c.y - 0.045
    a_ax = (piv_x + 0.012) / math.sin(phi_max)
    b_ax = max(0.10, (cy - (piv_y - 0.010)) / math.cos(phi_max))
    x, y = CapFrame.xy(-90.0, rim(-90.0))
    z_front = cap.point(x, y, t).z - 0.008
    z_bot = head.c.z - 0.118
    U = 0.11                                   # метры развёртки на радиан

    class VisorFrame:
        def _raw(self, u: float, v: float) -> tuple[Vector, Vector]:
            phi = u / U
            k = (phi / phi_max) ** 2
            z_top = z_front + (piv_z - 0.010 - z_front) * min(k, 1.0)
            fl = 1.0 + 0.07 * max(0.0, v) / (z_front - z_bot)
            a, b = a_ax * fl, b_ax * fl
            p = Vector((a * math.sin(phi), cy - b * math.cos(phi), z_top - v))
            n = Vector((math.sin(phi) / a, -math.cos(phi) / b, 0.0)).normalized()
            return p, n

        def normal(self, u: float, v: float) -> Vector:
            return self._raw(u, v)[1]

        def point(self, u: float, v: float, off: float = 0.0) -> Vector:
            p, n = self._raw(u, v)
            return p + n * off
    vf = VisorFrame()
    um = phi_max * U
    H = z_front - z_bot
    outline = ak.rounded_poly([(-um, 0.0), (um, 0.0), (um * 0.78, H), (-um * 0.78, H)], [0.012, 0.012, 0.035, 0.035])
    ak.padded_panel(glass, vf, outline, 0.005, bulge=0.0, binding=0.0, step=0.006)
    edge = [vf.point(-um * 0.99 + 2 * um * 0.99 * k / 47, 0.002, 0.0) for k in range(48)]
    ak.tube(trim, edge, 0.0028, sides=8)                                                   # окантовка верха забрала
    for piv, sgn, rib in ((pivots[0], 1.0, rl), (pivots[1], -1.0, rr)):
        corner = vf.point(sgn * um * 0.97, 0.008, 0.004)
        ak.tube(plastic, lerp_path([piv, corner], n=4), 0.0045, sides=8)                  # кронштейн к шарниру
        ak.torus(metal, piv, rib.normal(0.004, 0), 0.0055, 0.0022, seg=14, sides=6)
    shell.build("Helmet_Top_Shell", col, [mats["shell"]])
    trim.build("Helmet_Top_Edge_Trim", col, [mats["rubber"]])
    rails.build("Helmet_Top_Rails", col, [mats["plastic"]])
    velc.build("Helmet_Top_Velcro", col, [mats["velcro"]])
    plate.build("Helmet_Top_NVG_Mount", col, [mats["plastic"]])
    metal.build("Helmet_Top_Screws", col, [mats["metal"]])
    web.build("Helmet_Top_Harness", col, [mats["webbing"]])
    plastic.build("Helmet_Top_Hardware", col, [mats["plastic"]])
    light.build("Helmet_Top_Flashlight", col, [mats["plastic"]])
    glass.build("Helmet_Top_Visor", col, [mats["glass"]])


TIERS = (("06_Helmet_Simple", build_simple, "простой"), ("06_Helmet_Mid", build_mid, "средний"),
         ("06_Helmet_Top", build_top, "крутой"))


def show_only(name: str) -> None:
    for col_name, _, _ in TIERS:
        lc = bpy.context.view_layer.layer_collection.children.get(col_name)
        if lc is not None:
            lc.hide_viewport = col_name != name
        c = bpy.data.collections.get(col_name)
        if c is not None:
            c.hide_render = col_name != name


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.npc_file()))
    objs = [bpy.data.objects[n] for n in ("Balaclava", "Balaclava_SlotRim")]
    c = Vector((0.0, -0.055, 1.705))
    head = Head(objs, c)
    mats = materials()
    for col_name, fn, label in TIERS:
        col = kc.collection(col_name)
        fn(col, mats, head)
        gap, on_ear = check_straps(head, col)
        kc.log(f"  шлем {label}: {sum(len(o.data.polygons) for o in col.objects)} граней; ремни: зазор до балаклавы "
               f"не меньше {gap * 1000:.1f} мм, вершин на ухе {on_ear}")
    show_only("06_Helmet_Mid")
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(OUT / "helmets.blend")
    if "render" in args:
        render()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        show_only("06_Helmet_Mid")
        am.deliver(Path(dest), "Шлемы_v01_форма.blend", (
            "Шлемы трёх уровней — ФОРМА v01 на согласование (нейтральный материал), на мародёре v03.\n"
            "Переключение — галочки (глаз) коллекций в Outliner: 06_Helmet_Simple — простой (стальная каска, без креплений),\n"
            "06_Helmet_Mid — средний (шлем в чехле, площадка ПНВ), 06_Helmet_Top — крутой (высокий срез, планки с фонарём,\n"
            "площадка ПНВ, баллистическое забрало). Включать по одному. Смотреть в Rendered (Cycles).\n"
            "Скрипт: tools/npc_kit/helmets.py.\n"), focus_z=1.66, near=0.45)


def render() -> None:
    import numpy as np
    kc.studio()
    kc.gpu_cycles(96)
    scene = bpy.context.scene
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    out = kc.WORK / "previews"
    views = {"34": ((0.55, -0.75, 1.80), (0.0, -0.05, 1.70)), "side": ((0.85, -0.05, 1.74), (0.0, -0.05, 1.70)),
             "back": ((-0.45, 0.75, 1.82), (0.0, -0.03, 1.70)),
             "ear": ((0.42, -0.10, 1.68), (EAR_X, EAR_Y, EAR_Z - 0.02))}
    strips = []
    for col_name, _, _ in TIERS:
        show_only(col_name)
        row = []
        for v, (pos, tgt) in views.items():
            p = out / f"helmet_{col_name[10:].lower()}_{v}.png"
            kc.render(kc.camera("C_h_" + v, pos, tgt, 60), p, (700, 700), 96)
            row.append(p)
        strips.append(row)
    imgs = [[bpy.data.images.load(str(p)) for p in row] for row in strips]
    w, h = imgs[0][0].size
    nv = len(views)
    grid = np.zeros((h * 3, w * nv, 4), np.float32)
    for r, row in enumerate(imgs):
        for cidx, im in enumerate(row):
            px = np.empty(w * h * 4, np.float32)
            im.pixels.foreach_get(px)
            grid[(2 - r) * h:(3 - r) * h, cidx * w:(cidx + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("helmets_grid", w * nv, h * 3, alpha=False)
    res.pixels.foreach_set(grid.ravel())
    s = bpy.context.scene.render.image_settings
    s.file_format = "JPEG"
    s.quality = 90
    s.color_mode = "RGB"
    res.save_render(str(out / "helmets_v01.jpg"))


if __name__ == "__main__":
    main()
