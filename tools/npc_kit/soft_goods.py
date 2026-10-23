"""Мягкая ткань снаряжения: складки, бугры от содержимого, стропы, которые перетягивают ткань.

Владелец 2026-10-22 о рейдовом рюкзаке: «лямки через геометрию проходят… слишком примитивно, не хватает
реалистичности». У образца ткань не надута подушкой: складки сжатия и провисания, содержимое выпирает буграми,
стяжки врезаются в ткань, по бокам от них она собирается. Поэтому:
- гладкая форма (Bag, padded_panel) остаётся опорой, ткань смещается от неё по нормали полями (складки, бугры);
- стропа не повторяет форму, а натянута поверх уже смятой ткани (верхняя выпуклая оболочка профиля под ней),
  ткань под ней и у краёв продавливается до её нижней стороны — стропа нигде не уходит в ткань;
- check_inside — сколько вершин строп и фурнитуры оказалось внутри ткани (должно быть 0).
"""
from __future__ import annotations

import math
from typing import Callable

import bmesh
from mathutils import Vector, noise
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

import armor_kit as ak
import garment as gm

Field = Callable[[Vector, Vector], float]          # (точка, нормаль) → смещение по нормали, м


def merge(dst: ak.Mesh, src: ak.Mesh) -> None:
    o = len(dst.verts)
    dst.verts += src.verts
    dst.faces += [[i + o for i in f] for f in src.faces]
    dst.uvs += src.uvs
    dst.mats += src.mats


def bvh(*meshes: ak.Mesh) -> BVHTree:
    m = ak.Mesh()
    for s in meshes:
        merge(m, s)
    return BVHTree.FromPolygons(m.verts, m.faces)


def _welded(m: ak.Mesh) -> tuple[bmesh.types.BMesh, list[int]]:
    """bmesh с совпадающими вершинами, сведёнными в одну (у листов и бортов есть дубли на стыках: без сведения
    куски не связаны, их обход случаен, а дубли расходятся при смещении — ткань рвётся)."""
    bm = bmesh.new()
    key_of: dict[tuple[int, int, int], int] = {}
    remap = []
    for p in m.verts:
        k = (round(p.x * 1e5), round(p.y * 1e5), round(p.z * 1e5))
        if k not in key_of:
            key_of[k] = len(bm.verts)
            bm.verts.new(p)
        remap.append(key_of[k])
    bm.verts.ensure_lookup_table()
    for f in m.faces:
        idx = list(dict.fromkeys(remap[i] for i in f))
        if len(idx) < 3:
            continue
        try:
            bm.faces.new([bm.verts[i] for i in idx])
        except ValueError:
            pass
    return bm, remap


def normals(m: ak.Mesh, smooth: int = 3) -> list[Vector]:
    """Нормали вершин, согласованные наружу (сетки собраны из листов с разным обходом граней), сглаженные
    по соседям: у мелких и вырожденных граней (углы контура, веер донца) нормаль случайна — ткань у них
    выстреливала «звёздочками»."""
    bm, remap = _welded(m)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    nn = [Vector() for _ in bm.verts]
    for f in bm.faces:
        a = f.calc_area()
        for v in f.verts:
            nn[v.index] += f.normal * a
    for _ in range(smooth):
        nn = [sum((nn[e.other_vert(v).index] for e in v.link_edges), nn[v.index] * 2.0) for v in bm.verts]
    out = [nn[i].normalized() if nn[i].length > 1e-12 else bm.verts[i].normal.copy() for i in remap]
    bm.free()
    return out


def displace(m: ak.Mesh, field: Field, nrm: list[Vector] | None = None) -> None:
    nrm = nrm or normals(m)
    m.verts = [p + n * field(p, n) for p, n in zip(m.verts, nrm)]


def _seed(k: float) -> Vector:
    return Vector((k * 1.73 + 0.31, k * 3.11 + 0.57, k * 0.89 + 0.13))


def folds(axis: Vector, lam: float, amp: float, seed: float, cover: float = 0.55, warp: float = 0.5,
          sharp: float = 0.7) -> Callable[[Vector], float]:
    """Складки: гребни поперёк axis с шагом ~lam — гребень скруглён, во впадине залом. Фаза искривлена шумом
    (складки не по линейке), амплитуда пятнами по ~2–3 шага (cover — доля площади со складками): складка
    короткая и сходит на нет, как у мятой ткани."""
    ax = axis.normalized()
    s = _seed(seed)

    def f(p: Vector) -> float:
        w = noise.noise(p * (0.8 / lam) + s) + 0.45 * noise.noise(p * (2.1 / lam) + s * 2.0)
        sn = abs(math.sin(math.pi * (p.dot(ax) / lam + warp * w)))
        a = 0.5 + 0.9 * noise.noise(p * (0.42 / lam) + s * 3.0)
        a = gm.smoothstep((a - (1.0 - cover)) / 0.35)
        return amp * a * (sn ** sharp - 0.6)
    return f


def creases(scale: float, amp: float, seed: float, width: float = 0.10, stretch: Vector | None = None
            ) -> Callable[[Vector], float]:
    """Заломы мятой ткани: узкие вмятины по кривым нулевого уровня шума (сеть ломаных линий, как у смятой
    и расправленной ткани), рядом — небольшой подъём. stretch — растяжение по осям (заломы вытянуты вдоль
    оси с меньшим множителем)."""
    s = _seed(seed + 13.0)
    k = stretch or Vector((1.0, 1.0, 1.0))

    def f(p: Vector) -> float:
        q = Vector((p.x * k.x, p.y * k.y, p.z * k.z)) * (1.0 / scale)
        v = noise.noise(q + s) + 0.35 * noise.noise(q * 2.2 + s * 1.9)
        a = 0.55 + 0.6 * noise.noise(q * 0.45 + s * 2.7)          # заломы местами, не сплошной сеткой
        return amp * gm.smoothstep(a / 0.6) * (0.35 * math.exp(-(v / (width * 2.5)) ** 2) - math.exp(-(v / width) ** 2))
    return f


def lumps(scale: float, amp: float, seed: float) -> Callable[[Vector], float]:
    """Бугры от содержимого: крупные и помельче поверх."""
    s = _seed(seed + 7.0)

    def f(p: Vector) -> float:
        return amp * (noise.noise(p * (1.0 / scale) + s) + 0.4 * noise.noise(p * (2.3 / scale) + s * 1.7))
    return f


class Path:
    """Натянутая стропа: точки нижней стороны, нормали ленты и оси для продавливания ткани под ней."""

    def __init__(self, pts: list[Vector], nrm: list[Vector], half: float, s: list[float] | None = None):
        self.pts, self.nrm, self.half = pts, nrm, half
        self.s = s or [0.0] * len(pts)                     # координата построения (planar_path) у каждой точки
        self.extra = [0.0] * len(pts)                      # шире продавить под пряжкой
        self.axis: Vector | None = None                    # направление «высоты» у плоской стропы
        self.tan = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
        self.acc = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.acc.append(self.acc[-1] + (b - a).length)
        self.kd = KDTree(len(pts))
        for i, p in enumerate(pts):
            self.kd.insert(p, i)
        self.kd.balance()

    def rib(self, lift: float = 0.0) -> ak.RibbonFrame:
        return ak.RibbonFrame([p + n * lift for p, n in zip(self.pts, self.nrm)], self.nrm)

    def length_at(self, s: float) -> float:
        """Длина по ленте до точки с координатой построения s (ближайшей)."""
        return self.acc[min(range(len(self.s)), key=lambda i: abs(self.s[i] - s))]

    def widen(self, at: float, half_len: float, extra: float) -> None:
        """Под пряжкой (она шире ленты) ткань продавлена шире: на длине ±half_len от at."""
        for i, a in enumerate(self.acc):
            if abs(a - at) < half_len:
                self.extra[i] = max(self.extra[i], extra)

    def local(self, p: Vector) -> tuple[float, float, float, int]:
        """(поперёк ленты, высота над её нижней стороной, вдоль за концом, индекс ближайшей точки)."""
        _, i, _ = self.kd.find(p)
        q, n, t = self.pts[i], self.nrm[i], self.tan[i]
        d = p - q
        along = d.dot(t)
        beyond = 0.0
        if (i == 0 and along < 0) or (i == len(self.pts) - 1 and along > 0):
            beyond = abs(along)
        w = n.cross(t).normalized()
        return d.dot(w), d.dot(n), beyond, i


def flatness(t: Vector, ax: Vector) -> float:
    """1 — лента лежит на ткани, 0 — идёт круто вниз (с кармана на мешок) и висит над тканью по оболочке."""
    return gm.smoothstep((0.75 - abs(t.dot(ax))) / 0.3)


def taut(hits: Callable[[float, float], float | None], s0: float, s1: float, half: float,
         step: float = 0.002) -> list[tuple[float, float]]:
    """Профиль натянутой стропы: по длине s — наибольшая высота ткани под лентой (по середине и у краёв),
    верхняя выпуклая оболочка (стропа перекидывается через гребни и впадины). hits(s, поперёк) → высота
    ткани или None."""
    n = max(2, int(abs(s1 - s0) / step))
    prof = []
    for k in range(n + 1):
        s = s0 + (s1 - s0) * k / n
        hs = [h for h in (hits(s, half * c) for c in (-1.03, -0.7, -0.35, 0.0, 0.35, 0.7, 1.03)) if h is not None]
        if hs:
            prof.append((s, max(hs)))
    # верхняя выпуклая оболочка (Эндрю), профиль упорядочен по s
    pts = prof if s1 > s0 else prof[::-1]
    hull: list[tuple[float, float]] = []
    for p in pts:
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) >= 0:      # не правый поворот — точка внутри
                hull.pop()
            else:
                break
        hull.append(p)
    if s1 < s0:
        hull = hull[::-1]
    out = []
    for k in range(n + 1):
        s = s0 + (s1 - s0) * k / n
        for (xa, ya), (xb, yb) in zip(hull, hull[1:]):
            if min(xa, xb) - 1e-9 <= s <= max(xa, xb) + 1e-9:
                t = 0.0 if xb == xa else (s - xa) / (xb - xa)
                h = ya + (yb - ya) * t
                break
        else:
            h = hull[0][1] if abs(s - hull[0][0]) < abs(s - hull[-1][0]) else hull[-1][1]
        out.append((s, h))
    return out


def planar_path(bvh_: BVHTree, origin: Callable[[float], Vector], axis: Vector, along: Vector, s0: float, s1: float,
                half: float, sink: float = 0.0, reach: float = 0.6, end_ramp: float = 0.03) -> Path:
    """Стропа в плоскости: луч из origin(s) + axis·reach против axis, s — вдоль along; axis — «высота» над тканью.
    sink — насколько стяжка вдавлена в мягкий карман: только где лежит на ткани, к концам сходит на нет
    (на крутом участке опускать нельзя — там ткань не продавливается и лента ушла бы в борт)."""
    ax = axis.normalized()
    w = ax.cross(along).normalized()

    def hits(s: float, c: float) -> float | None:
        o = origin(s) + ax * reach + w * c
        loc, _, _, _ = bvh_.ray_cast(o, -ax, reach * 2)
        return None if loc is None else (loc - origin(s)).dot(ax)
    prof = taut(hits, s0, s1, half)
    pts = [origin(s) + ax * h for s, h in prof]
    if sink > 0:
        tans = [(pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized() for i in range(len(pts))]
        pts = [p - ax * sink * flatness(t, ax) * gm.smoothstep(min(abs(s - s0), abs(s1 - s)) / end_ramp)
               for p, t, (s, _) in zip(pts, tans, prof)]
    nrm = []
    for i in range(len(pts)):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        n = ax - t * ax.dot(t)
        nrm.append(n.normalized() if n.length > 1e-6 else ax)
    path = Path(pts, nrm, half, [s for s, _ in prof])
    path.axis = ax
    return path


def wrap_path(bvh_: BVHTree, c: Vector, e1: Vector, e2: Vector, a: Vector, b: Vector, half: float, ccw: bool,
              reach: float = 0.8, step: float = 0.002) -> Path:
    """Стропа в плоскости (c, e1, e2), огибающая вещь через ребро (с верха или дна на лицевую сторону): лучи
    снаружи к c по дуге от направления на a до направления на b (ccw — по часовой или против в базисе e1, e2),
    самая дальняя ткань под лентой по её ширине, выпуклая оболочка — лента натянута, перекидывается через гребни
    и мостом через впадины. Нормаль ленты — наружу от оболочки, «высота» над тканью меряется по ней."""
    e1, e2 = e1.normalized(), e2.normalized()
    w = e1.cross(e2).normalized()

    def ang(p: Vector) -> float:
        d = p - c
        return math.atan2(d.dot(e2), d.dot(e1))
    ta, tb = ang(a), ang(b)
    if ccw and tb < ta:
        tb += 2 * math.pi
    if not ccw and tb > ta:
        tb -= 2 * math.pi
    r_max = max((a - c).length, (b - c).length) + 0.1
    n = max(8, int(abs(tb - ta) * r_max / 0.002))
    prof = []
    for k in range(n + 1):
        t = ta + (tb - ta) * k / n
        d = e1 * math.cos(t) + e2 * math.sin(t)
        best = None
        for f in (-1.03, -0.7, -0.35, 0.0, 0.35, 0.7, 1.03):
            loc, _, _, _ = bvh_.ray_cast(c + d * reach + w * (half * f), -d, reach)
            if loc is not None:
                r = (loc - c - w * (half * f)).dot(d)
                best = r if best is None else max(best, r)
        if best is not None:
            prof.append((best * math.cos(t), best * math.sin(t)))
    pts2 = prof if ccw else prof[::-1]                     # обход против часовой: выпуклая цепь — только левые повороты
    hull: list[tuple[float, float]] = []
    for p in pts2:
        while len(hull) >= 2:
            (x1, y1), (x2, y2) = hull[-2], hull[-1]
            if (x2 - x1) * (p[1] - y1) - (y2 - y1) * (p[0] - x1) <= 0:
                hull.pop()
            else:
                break
        hull.append(p)
    if not ccw:
        hull = hull[::-1]
    # равномерно по длине
    dense = [Vector(hull[0])]
    for (x1, y1), (x2, y2) in zip(hull, hull[1:]):
        seg = math.hypot(x2 - x1, y2 - y1)
        for k in range(1, max(1, int(seg / step)) + 1):
            f = k / max(1, int(seg / step))
            dense.append(Vector((x1 + (x2 - x1) * f, y1 + (y2 - y1) * f)))
    pts = [c + e1 * q.x + e2 * q.y for q in dense]
    nrm = []
    for i in range(len(dense)):
        t2 = (dense[min(i + 1, len(dense) - 1)] - dense[max(i - 1, 0)]).normalized()
        o2 = Vector((t2.y, -t2.x)) if ccw else Vector((-t2.y, t2.x))   # наружу — справа по ходу против часовой
        nrm.append((e1 * o2.x + e2 * o2.y).normalized())
    path = Path(pts, nrm, half)
    path.s = list(path.acc)
    return path


class Line:
    """Линия на ткани (молния, шов): расстояние до неё и длина вдоль неё у ближайшей точки."""

    def __init__(self, pts: list[Vector], step: float = 0.002):
        dense = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            k = max(1, int((b - a).length / step))
            dense += [a.lerp(b, i / k) for i in range(1, k + 1)]
        self.pts = dense
        self.acc = [0.0]
        for a, b in zip(dense, dense[1:]):
            self.acc.append(self.acc[-1] + (b - a).length)
        self.kd = KDTree(len(dense))
        for i, p in enumerate(dense):
            self.kd.insert(p, i)
        self.kd.balance()

    def near(self, p: Vector) -> tuple[float, float]:
        q, i, d = self.kd.find(p)
        return d, self.acc[i]


def pucker(lines: list[Line], lam: float, amp: float, d0: float = 0.011, d1: float = 0.026
           ) -> tuple[Callable[[Vector], float], Callable[[Vector], float]]:
    """Ткань у молнии собирается мелкой волной поперёк неё (шов тянет): смещение у линии на d0…d1 (за краем ленты
    шириной 20 мм), под самой лентой — ноль. Второе — доля прочих складок у линии (под лентой ткань ровнее)."""
    def info(p: Vector) -> tuple[float, float]:
        return min((ln.near(p) for ln in lines), key=lambda t: t[0])

    def disp(p: Vector) -> float:
        d, s = info(p)
        if d > d1 + 0.01:
            return 0.0
        band = gm.smoothstep((d - d0) / 0.004) * gm.smoothstep((d1 + 0.01 - d) / 0.012)
        return amp * band * math.sin(2 * math.pi * s / lam + 1.7 * noise.noise(p * 40.0))

    def calm(p: Vector) -> float:
        return 0.25 + 0.75 * gm.smoothstep((info(p)[0] - d0) / 0.012)
    return disp, calm


def _layer_depth(m: ak.Mesh, thick: float, up: Callable[[int], Vector]) -> list[float]:
    """Тонкий пакет (клапан) давится слоем: у нижней стороны к высоте добавлена толщина, у борта — половина,
    иначе верх уходил под низ и пакет выворачивался."""
    if thick <= 0:
        return [0.0] * len(m.verts)
    return [thick * gm.smoothstep((0.2 - n.dot(up(i))) / 0.4) for i, n in enumerate(normals(m, smooth=1))]


def press(m: ak.Mesh, path: Path, rim: float = 0.010, gap: float = 0.0006, bulge: float = 0.0, depth: float = 0.04,
          thick: float = 0.0) -> int:
    """Ткань под стропой и у её краёв продавлена до нижней стороны стропы (плавно на ширину rim), за краем —
    чуть выдавлена (bulge); thick — толщина тонкого пакета, который давится целиком. Возвращает число сдвинутых
    вершин."""
    moved = 0
    out = []
    loc = [path.local(p) for p in m.verts]
    extra_h = _layer_depth(m, thick, lambda j: path.nrm[loc[j][3]])
    for p, (c, h, beyond, i), eh in zip(m.verts, loc, extra_h):
        h += eh
        d = max(abs(c) - path.half - path.extra[i], 0.0) + beyond * 3.0
        if h < -depth or d > rim * 2.5:
            out.append(p)
            continue
        n = path.nrm[i]
        # где лента идёт круто вниз (с кармана на мешок), она висит над тканью по оболочке — там не давим
        flat = flatness(path.tan[i], path.axis) if path.axis else 1.0
        k = gm.smoothstep((rim - d) / rim) * flat
        dh = -k * max(0.0, h + gap)
        if bulge > 0 and d > 0:
            dh += bulge * math.exp(-((d - rim * 1.3) / (rim * 0.7)) ** 2) * (1.0 - k)
        if dh != 0.0:
            moved += 1
        out.append(p + n * dh)
    m.verts = out
    return moved


def press_box(m: ak.Mesh, c: Vector, ax: Vector, ay: Vector, az: Vector, hx: float, hy: float, bottom: float,
              rim: float = 0.006, gap: float = 0.0006, depth: float = 0.03, thick: float = 0.0) -> None:
    """Ткань под жёсткой деталью (пряжкой) продавлена ниже её дна: прямоугольник hx × hy в осях детали,
    дно — на bottom по az от c, к краям плавно на ширину rim; thick — как у press."""
    target = bottom - gap
    out = []
    for p, eh in zip(m.verts, _layer_depth(m, thick, lambda j: az)):
        d = p - c
        h = d.dot(az) + eh
        e = math.hypot(max(abs(d.dot(ax)) - hx, 0.0), max(abs(d.dot(ay)) - hy, 0.0))
        if e > rim or h < -depth or h <= target:
            out.append(p)
            continue
        out.append(p - az * (gm.smoothstep((rim - e) / rim) * (h - target)))
    m.verts = out


def surface_point(bvh_: BVHTree, p: Vector, n: Vector, reach: float = 0.05) -> Vector:
    """Точка смятой ткани над точкой гладкой формы p (луч снаружи по её нормали)."""
    loc, _, _, _ = bvh_.ray_cast(p + n * reach, -n, reach * 2)
    if loc is None:
        loc, _, _, _ = bvh_.find_nearest(p)
    return loc


class SurfFrame:
    """Рамка детали на смятой ткани: точка — луч на смятую поверхность, нормаль — от гладкой формы
    (смещение толщины по нормали складок давало бы самопересечения во впадинах)."""

    def __init__(self, base, bvh_: BVHTree, reach: float = 0.05):
        self.base, self.bvh, self.reach = base, bvh_, reach

    def normal(self, u: float, v: float) -> Vector:
        return self.base.normal(u, v)

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        n = self.base.normal(u, v)
        return surface_point(self.bvh, self.base.point(u, v), n, self.reach) + n * off


def solid(*meshes: ak.Mesh) -> BVHTree:
    """BVH замкнутых деталей с нормалями граней наружу (для проверки «внутри»)."""
    m = ak.Mesh()
    for s in meshes:
        merge(m, s)
    bm, _ = _welded(m)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out = BVHTree.FromBMesh(bm)
    bm.free()
    return out


def check_inside(cloth: BVHTree, verts: list[Vector], tol: float = 0.0008) -> tuple[int, float, dict]:
    """Сколько вершин внутри ткани глубже tol (по ближайшей грани и её нормали), наибольшая глубина и где
    (клетки 5 см → число вершин)."""
    bad, worst, where = 0, 0.0, {}
    for p in verts:
        loc, nn, _, _ = cloth.find_nearest(p, 0.05)
        if loc is None:
            continue
        depth = -(p - loc).dot(nn)
        if depth > tol:
            bad += 1
            worst = max(worst, depth)
            key = tuple(round(c * 20) / 20 for c in p)
            where[key] = where.get(key, 0) + 1
    return bad, worst, where


def stitch_line(m: ak.Mesh, pts: list[Vector], nrm: list[Vector], count: int | None = None, pitch: float = 0.0042,
                dash: float = 0.0028, r: float = 0.00055, mat: int = 0) -> int:
    """Строчка по линии шва: стежки-«черточки» (утолщены к середине, наполовину утоплены в ткань) с шагом pitch.
    count — число стежков (для ключей формы — одинаковое во всех; положение — по доле длины линии)."""
    acc = [0.0]
    for a, b in zip(pts, pts[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1]
    if total < dash:
        return 0
    n_st = count if count is not None else max(1, int(total / pitch))
    step = total / n_st

    def at(s: float) -> tuple[Vector, Vector]:
        s = min(max(s, 0.0), total)
        i = max(0, min(len(acc) - 2, next((k for k in range(len(acc) - 1) if acc[k + 1] >= s), len(acc) - 2)))
        t = (s - acc[i]) / max(acc[i + 1] - acc[i], 1e-12)
        return pts[i].lerp(pts[i + 1], t), nrm[i].lerp(nrm[i + 1], t).normalized()
    for k in range(n_st):
        s0 = step * k + (step - dash) / 2
        ring = []
        for f, rad in ((0.0, 0.35), (0.5, 1.0), (1.0, 0.35)):
            p, n = at(s0 + dash * f)
            q, _ = at(s0 + dash * min(1.0, f + 0.1))
            t = (q - p).normalized() if (q - p).length > 1e-9 else n.orthogonal().normalized()
            if f == 1.0:
                q0, _ = at(s0 + dash * 0.9)
                t = (p - q0).normalized() if (p - q0).length > 1e-9 else t
            b = t.cross(n).normalized()
            c = p + n * (r * 0.35)
            ring.append([m.v(c + (n * math.cos(2 * math.pi * j / 4) + b * math.sin(2 * math.pi * j / 4)) * r * rad)
                         for j in range(4)])
        m.grid(ring, [[(k * 0.01 + i * 0.003, j / 4) for j in range(4)] for i in range(3)], mat, closed_u=True)
        for row, flip in ((ring[0], True), (ring[-1], False)):
            c = m.v(sum((m.verts[i] for i in row), Vector()) / 4)
            for j in range(4):
                f = [row[j], row[(j + 1) % 4], c]
                m.f(f[::-1] if flip else f, [(0, 0), (0.001, 0), (0.0005, 0.001)], mat)
    return n_st
