"""Растения «Проспекта»: общая часть генератора форм (bpy, Blender 5). Описания видов — species.py, запуск — build_forms.py.

Дерево = ствол и ветви сеткой (трубы с сбегом, наплывы у корня, воротники у развилок) + модули веточек с листьями
(своя сетка листа по контуру вида, черешок, перегиб по средней жилке), размноженные по кроне геометрическими узлами
(точки с поворотом, масштабом и номером модуля). Крона растёт до огибающей вида (бугристая, не шар): ветвь,
вышедшая за огибающую, перестаёт расти — силуэт задаётся огибающей, строение — ветвлением.
Всё детерминировано: тот же seed — тот же экземпляр (игровая версия строится из тех же данных).
Метры, Z вверх, начало координат — у земли под стволом.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

import bpy
from mathutils import Matrix, Quaternion, Vector

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


# ------------------------------------------------------------------ накопитель сетки

class Mesh:
    """Части по материалам: вершины, грани, UV по углам граней, цвет вершин."""

    def __init__(self) -> None:
        self.parts: dict[str, dict] = {}
        self.leaves = 0

    def part(self, mat: str) -> dict:
        if mat not in self.parts:
            self.parts[mat] = dict(v=[], f=[], uv=[], col=[])
        return self.parts[mat]

    def tris(self) -> int:
        return sum(len(f) - 2 for p in self.parts.values() for f in p["f"])

    def poly(self, mat: str, pts: list, uvs: list, col=(1, 1, 1, 1)) -> None:
        p = self.part(mat)
        i = len(p["v"])
        p["v"].extend(pts)
        p["f"].append(list(range(i, i + len(pts))))
        p["uv"].append(list(uvs))
        p["col"].extend([col] * len(pts))

    def tube(self, mat: str, pts: list, radii: list, sides: int, v_scale: float = 1.0, u_reps: float = 1.0,
             col=(1, 1, 1, 1), shape: Callable | None = None, cap: bool = True, col_fn: Callable | None = None) -> None:
        """Труба по ломаной с переносом рамки без закрутки. shape(i, a) — множитель радиуса (наплывы, неровность сечения).
        UV: u — по окружности (u_reps повторов), v — длина в метрах × v_scale. cap — закрыть конец конусом."""
        n = len(pts)
        if n < 2:
            return
        p = self.part(mat)
        base = len(p["v"])
        side = None
        frames = []
        for i in range(n):
            d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
            d = d.normalized() if d.length > 1e-9 else Z
            ref = side if side is not None else (Z if abs(d.z) < 0.9 else X)
            s = ref - d * ref.dot(d)
            if s.length < 1e-6:
                s = (X if abs(d.x) < 0.9 else Y) - d * d.dot(X if abs(d.x) < 0.9 else Y)
            side = s.normalized()
            frames.append((d, side, d.cross(side)))
        lengths = [0.0]
        for i in range(1, n):
            lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
        for i in range(n):
            d, s, b = frames[i]
            for k in range(sides + 1):
                a = 2 * math.pi * k / sides
                r = radii[i] * (shape(i, a) if shape else 1.0)
                v = pts[i] + (s * math.cos(a) + b * math.sin(a)) * r
                p["v"].append(v)
                p["col"].append(col_fn(v) if col_fn else col)
        ring = sides + 1
        for i in range(n - 1):
            for k in range(sides):
                a0 = base + i * ring + k
                p["f"].append([a0, a0 + 1, a0 + ring + 1, a0 + ring])
                u0, u1 = u_reps * k / sides, u_reps * (k + 1) / sides
                v0, v1 = lengths[i] * v_scale, lengths[i + 1] * v_scale
                p["uv"].append([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        if cap and radii[-1] > 0.0015:
            tip = len(p["v"])
            p["v"].append(pts[-1] + frames[-1][0] * radii[-1] * 0.8)
            p["col"].append(col_fn(p["v"][-1]) if col_fn else col)
            last = base + (n - 1) * ring
            for k in range(sides):
                p["f"].append([last + k, last + k + 1, tip])
                p["uv"].append([(u_reps * k / sides, lengths[-1] * v_scale), (u_reps * (k + 1) / sides, lengths[-1] * v_scale),
                                (u_reps * (k + 0.5) / sides, lengths[-1] * v_scale + 0.02)])

    def merge(self, other: "Mesh", mat_map: dict | None = None, xf: Matrix | None = None) -> None:
        for key, src in other.parts.items():
            p = self.part(mat_map.get(key, key) if mat_map else key)
            b = len(p["v"])
            p["v"].extend([(xf @ v) if xf is not None else v.copy() for v in src["v"]])
            p["f"].extend([[b + i for i in f] for f in src["f"]])
            p["uv"].extend(src["uv"])
            p["col"].extend(src["col"])
        self.leaves += other.leaves

    def build(self, name: str, materials: dict, collection=None, smooth: bool = True) -> bpy.types.Object:
        verts, faces, uvs, cols, mats = [], [], [], [], []
        order = sorted(self.parts)
        for mi, key in enumerate(order):
            p = self.parts[key]
            b = len(verts)
            verts.extend(p["v"])
            faces.extend([[b + i for i in f] for f in p["f"]])
            uvs.extend(p["uv"])
            cols.extend(p["col"])
            mats.extend([mi] * len(p["f"]))
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in verts], [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        for poly, puv in zip(me.polygons, uvs):
            for k in range(poly.loop_total):
                uvl.data[poly.loop_start + k].uv = puv[k]
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        for i, c in enumerate(cols):
            ca.data[i].color = c
        for key in order:
            me.materials.append(materials[key])
        for poly, mi in zip(me.polygons, mats):
            poly.material_index = mi
            poly.use_smooth = smooth
        me.validate()
        me.update()
        ob = bpy.data.objects.new(name, me)
        (collection or bpy.context.scene.collection).objects.link(ob)
        return ob


# ------------------------------------------------------------------ лист

@dataclass
class LeafShape:
    """Половина контура листа в долях длины: x — поперёк (вправо), y — от прикрепления черешка (0) к кончику (1).
    Сердцевидное основание — точки с y < 0 (лопасти ниже черешка). asym — правая половина уже левой (липа)."""
    half: list
    petiole: tuple = (0.2, 0.3)       # длина черешка в долях длины листа
    fold: float = 0.12                # подъём краёв от средней жилки (доля полуширины)
    curl: float = 0.06                # прогиб вдоль (доля длины): кончик книзу
    asym: float = 0.0


def leaf(m: Mesh, rng: random.Random, attach: Vector, grow: Vector, normal: Vector, length: float, shape: LeafShape,
         mat: str = "leaf", stalk_mat: str = "twig", stalk_r: float = 0.0012, col=(1, 1, 1, 1)) -> None:
    """Лист на черешке. attach — точка на побеге, grow — куда растёт черешок/лист, normal — куда смотрит лицо листа.
    UV — ячейка листа текстуры (2 × 2 разных листа, tools/prospekt_plants/textures.py): v — от низа лопастей (0) до
    кончика (1), x — в тех же долях от средней жилки. Ячейка — по счётчику листьев (без случайных чисел: форма та же)."""
    y_ax = (grow - normal * grow.dot(normal))
    if y_ax.length < 1e-6:
        y_ax = normal.orthogonal()
    y_ax.normalize()
    n = normal.normalized()
    x_ax = y_ax.cross(n).normalized()
    m.leaves += 1
    pet = length * rng.uniform(*shape.petiole)
    # черешок слегка дугой: выходит по grow, подходит к листу вдоль его оси
    g = grow.normalized()
    mid = attach + g * pet * 0.55 + n * pet * 0.08
    base = attach + (g * 0.45 + y_ax * 0.55).normalized() * pet
    m.tube(stalk_mat, [attach, mid, base], [stalk_r, stalk_r * 0.85, stalk_r * 0.7], 3, cap=False, col=col)
    twist = rng.uniform(-0.08, 0.08)
    fold = shape.fold * rng.uniform(0.6, 1.3)
    curl = shape.curl * rng.uniform(0.5, 1.5)
    asym = shape.asym * rng.choice([-1, 1])

    def place(x: float, y: float) -> Vector:
        w = abs(x)
        z = fold * w * 2.0 - curl * (y ** 2) + twist * x * y
        return base + x_ax * (x * length) + y_ax * (y * length) + n * (z * length)

    half = shape.half
    y_lo = min(0.0, min(y for _, y in half))
    span = 1.0 - y_lo
    cell = (m.leaves * 7 + 3) % 4
    cu, cv = 0.5 * (cell % 2), 0.5 * (cell // 2)

    def luv(x: float, y: float) -> tuple:
        return (cu + (0.5 + x / span) * 0.5, cv + ((y - y_lo) / span) * 0.5)

    rows = []
    for (hx, hy) in half:
        yr = min(max(hy, 0.0), 1.0)
        rows.append((hx, hy, yr))
    for sgn in (1, -1):
        k = (1 - asym * 0.5) if sgn > 0 else (1 + asym * 0.5)
        for i in range(len(rows) - 1):
            x0, y0, m0 = rows[i]
            x1, y1, m1 = rows[i + 1]
            pa, pb = place(sgn * x0 * k, y0), place(sgn * x1 * k, y1)
            ma, mb = place(0.0, m0), place(0.0, m1)
            ua, ub = luv(sgn * x0, y0), luv(sgn * x1, y1)
            uma, umb = luv(0.0, m0), luv(0.0, m1)
            if abs(m1 - m0) < 1e-6:
                tri = [ma, pa, pb] if sgn > 0 else [ma, pb, pa]
                tuv = [uma, ua, ub] if sgn > 0 else [uma, ub, ua]
                m.poly(mat, tri, tuv, col)
            elif sgn > 0:
                m.poly(mat, [ma, pa, pb, mb], [uma, ua, ub, umb], col)
            else:
                m.poly(mat, [ma, mb, pb, pa], [uma, umb, ub, ua], col)


def rand_unit(rng: random.Random) -> Vector:
    while True:
        v = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        if 0.05 < v.length <= 1.0:
            return v.normalized()


def rotate_about(v: Vector, axis: Vector, ang: float) -> Vector:
    return Matrix.Rotation(ang, 3, axis.normalized()) @ v


def frame_quat(x_dir: Vector, z_hint: Vector) -> Quaternion:
    """Поворот: локальная +X → x_dir, локальная +Z — как можно ближе к z_hint."""
    xd = x_dir.normalized()
    zh = z_hint - xd * z_hint.dot(xd)
    if zh.length < 1e-5:
        zh = xd.orthogonal()
    zd = zh.normalized()
    yd = zd.cross(xd).normalized()
    mat = Matrix((xd, yd, zd)).transposed()
    return mat.to_quaternion()


# ------------------------------------------------------------------ огибающая кроны

@dataclass
class Envelope:
    """Тело вращения с бугристостью: радиус на высоте z = rmax × profile(t) × бугры(азимут, t).
    profile(t), t = (z − z0)/(z1 − z0) ∈ [0, 1]. Центр может уходить вбок (наклон кроны)."""
    z0: float
    z1: float
    rmax: float
    profile: Callable[[float], float]
    seed: int = 1
    lump: float = 0.18
    shift: Vector = field(default_factory=lambda: Vector((0, 0, 0)))
    squash_y: float = 1.0

    def __post_init__(self) -> None:
        r = random.Random(self.seed)
        self.terms = [(r.randint(1, 4), r.uniform(0.5, 2.5), r.uniform(0, 6.28), r.uniform(0, 6.28), r.uniform(0.4, 1.0))
                      for _ in range(6)]

    def radius(self, z: float, az: float) -> float:
        t = (z - self.z0) / max(self.z1 - self.z0, 1e-3)
        if t < 0.0 or t > 1.0:
            return 0.0
        b = 0.0
        tot = 0.0
        for (k, f, ph, ph2, w) in self.terms:
            b += w * math.sin(k * az + ph) * math.cos(f * t * math.pi + ph2)
            tot += w
        return max(0.0, self.rmax * self.profile(t) * (1.0 + self.lump * b / tot * 2.0))

    def center(self, z: float) -> Vector:
        t = min(max((z - self.z0) / max(self.z1 - self.z0, 1e-3), 0.0), 1.0)
        return Vector((self.shift.x * t, self.shift.y * t, 0.0))

    def frac(self, p: Vector) -> float:
        """Доля радиуса огибающей (0 — ось, 1 — поверхность, > 1 — снаружи); вне по высоте — 9."""
        c = self.center(p.z)
        dx, dy = p.x - c.x, (p.y - c.y) / self.squash_y
        R = self.radius(p.z, math.atan2(dy, dx))
        if R <= 1e-4:
            return 9.0
        return math.hypot(dx, dy) / R

    def inside(self, p: Vector, tol: float = 1.0) -> bool:
        return self.frac(p) <= tol


# ------------------------------------------------------------------ ветвление

@dataclass
class Level:
    """Порядок ветвления. Дочерние ветви растут на родителе в [s0, s1] доли длины с шагом spacing (м).
    angle — угол от оси родителя (град), roll — 'spiral' (137,5°), 'alt' (в плоскость, по очереди),
    'opp' (парами, следующая пара повёрнута на 90°). length(s, L_parent, rng) — длина дочерней.
    tropism(t) — подъём направления на шаг (+ вверх, − вниз), wiggle — случайный излом, flat — прижать к горизонтали."""
    spacing: float
    s0: float
    s1: float
    angle: tuple
    length: Callable
    roll: str = "spiral"
    tropism: Callable = lambda t: 0.0
    wiggle: float = 0.08
    seg: float = 0.5
    flat: float = 0.0
    radius_k: float = 0.75
    tip: float = 0.3
    keep: float = 1.0          # вероятность вырасти (разреженность)
    env_tol: float = 1.05      # насколько ветвь может выйти за огибающую


@dataclass
class Branch:
    pts: list
    radii: list
    level: int
    length: float = 0.0
    children: list = field(default_factory=list)


def path_len(pts: list) -> float:
    return sum((b - a).length for a, b in zip(pts, pts[1:]))


def point_at(pts: list, s: float):
    """Точка и касательная на доле s длины ломаной."""
    total = path_len(pts)
    target = s * total
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = (b - a).length
        if acc + seg >= target or b is pts[-1]:
            t = (target - acc) / seg if seg > 1e-9 else 0.0
            return a.lerp(b, min(max(t, 0.0), 1.0)), (b - a).normalized() if seg > 1e-9 else Z
        acc += seg
    return pts[-1], (pts[-1] - pts[-2]).normalized()


def radius_at(br: Branch, s: float) -> float:
    seg = s * (len(br.radii) - 1)
    i = min(int(seg), len(br.radii) - 2)
    return br.radii[i] + (br.radii[i + 1] - br.radii[i]) * (seg - i)


def grow(start: Vector, d0: Vector, L: float, lv: Level, rng: random.Random, env: Envelope | None,
         stop_floor: float = -1.0) -> list:
    """Путь ветви: шаги lv.seg, направление тянется тропизмом и случайным изломом; вне огибающей — остановка."""
    n = max(2, int(math.ceil(L / lv.seg)))
    step = L / n
    pts = [start]
    d = d0.normalized()
    for i in range(n):
        t = (i + 0.5) / n
        d = (d + Z * lv.tropism(t) + rand_unit(rng) * lv.wiggle).normalized()
        if lv.flat:
            d = Vector((d.x, d.y, d.z * (1 - lv.flat))).normalized()
        p = pts[-1] + d * step
        if p.z < stop_floor:
            break
        if env is not None and i > 0 and not env.inside(p, lv.env_tol):
            break
        pts.append(p)
    return pts


def child_dir(tan: Vector, angle: float, roll: float) -> Vector:
    """Направление дочерней: ось родителя, отклонённая на angle в плоскости, повёрнутой на roll вокруг оси."""
    perp = Z - tan * tan.dot(Z)
    if perp.length < 1e-4:
        perp = X - tan * tan.dot(X)
    perp.normalize()
    perp = rotate_about(perp, tan, roll)
    return (tan * math.cos(angle) + perp * math.sin(angle)).normalized()


# Кора: плитка текстуры в метрах (u — по окружности, v — вдоль). Толстым — целое число повторов по окружности (без шва),
# тонким — доля плитки (узор не сжимается в нитку; шов на ветке толщиной в палец не виден).
BARK = {"tile_u": 1.0, "tile_v": 1.0}
# Упрощение для игры (None — форма как есть): min_r — тоньше не строить, side_div — делитель числа граней,
# seg — шаг точек вдоль ветви, м; col — цвет вершин по точке (ветер, затенение).
LOD: dict | None = None


def bark_uv(r: float) -> tuple:
    c = 2 * math.pi * r / BARK["tile_u"]
    return (max(1.0, round(c)) if c >= 1.5 else max(c, 0.05)), 1.0 / BARK["tile_v"]


def lod_sides(n: int) -> int:
    return n if LOD is None else max(3, int(round(n / LOD.get("side_div", 1.0))))


def lod_path(pts: list, radii: list) -> tuple:
    """Реже точки вдоль ветви: первую, последнюю и через шаг LOD["seg"]."""
    if LOD is None or len(pts) <= 2:
        return pts, radii
    seg = LOD.get("seg", 0.0)
    keep = [0]
    acc = 0.0
    for i in range(1, len(pts) - 1):
        acc += (pts[i] - pts[i - 1]).length
        if acc >= seg or i <= 1:
            keep.append(i)
            acc = 0.0
    keep.append(len(pts) - 1)
    return [pts[i] for i in keep], [radii[i] for i in keep]


def sides_for(r: float) -> int:
    return 16 if r > 0.14 else 12 if r > 0.07 else 8 if r > 0.03 else 6 if r > 0.012 else 4


def branch_children(parent: Branch, levels: list, rng: random.Random, env: Envelope | None, depth: int,
                    floor: float = 0.05) -> None:
    """Рекурсивно: дочерние ветви уровня depth на parent."""
    if depth >= len(levels):
        return
    lv = levels[depth]
    L = parent.length
    s = lv.s0 + rng.uniform(0, lv.spacing / max(L, 1e-3))
    roll = rng.uniform(0, 6.28)
    pair = 0
    while s < lv.s1:
        p, tan = point_at(parent.pts, s)
        rolls = [roll + math.pi * 0.0] if lv.roll != "opp" else [roll, roll + math.pi]
        for rr in rolls:
            if rng.random() > lv.keep:
                continue
            ang = math.radians(rng.uniform(*lv.angle))
            d = child_dir(tan, ang, rr)
            Lc = lv.length(s, L, rng)
            if Lc < 0.08:
                continue
            rp = radius_at(parent, s)
            rc = max(0.004, min(rp * 0.8, rp * lv.radius_k * (Lc / max(L * (1 - s) + 0.3, 0.3)) ** 0.6))
            start = p + d * rp * 0.6
            pts = grow(start, d, Lc, lv, rng, env, floor)
            if len(pts) < 2:
                continue
            pts = [p] + pts
            n = len(pts)
            radii = [rc * (1 - (1 - lv.tip) * (i / (n - 1))) for i in range(n)]
            radii[0] = rc * 1.05
            if n > 2:
                radii[1] = rc * 1.22       # воротник у развилки
            ch = Branch(pts, radii, depth + 1, path_len(pts))
            parent.children.append(ch)
            branch_children(ch, levels, rng, env, depth + 1, floor)
        if lv.roll == "spiral":
            roll += math.radians(137.5) + rng.uniform(-0.35, 0.35)
        elif lv.roll == "alt":
            roll += math.pi + rng.uniform(-0.5, 0.5)
        else:
            roll += math.pi / 2 + rng.uniform(-0.2, 0.2)
            pair += 1
        s += lv.spacing / max(L, 1e-3) * rng.uniform(0.7, 1.3)


def all_branches(root: Branch) -> list:
    out = [root]
    for c in root.children:
        out.extend(all_branches(c))
    return out


def emit_branches(m: Mesh, root: Branch, mat_of: Callable[[Branch], str], skip_root: bool = False) -> None:
    for br in all_branches(root):
        if skip_root and br is root:
            continue
        r0 = br.radii[min(1, len(br.radii) - 1)]
        if LOD is not None and r0 < LOD.get("min_r", 0.0):
            continue
        pts, radii = lod_path(br.pts, br.radii)
        u, v = bark_uv(r0)
        m.tube(mat_of(br), pts, radii, lod_sides(sides_for(r0)), v_scale=v, u_reps=u,
               col_fn=LOD.get("col") if LOD else None)


# ------------------------------------------------------------------ ствол

def trunk_path(rng: random.Random, base: Vector, H: float, lean_dir: Vector, lean_deg: float, wobble: float,
               step: float = 0.35, z_start: float = -0.35) -> list:
    """Ось ствола: наклон, плавные изгибы (две частоты), к вершине изгиб сильнее."""
    ph = [rng.uniform(0, 6.28) for _ in range(4)]
    tilt = math.tan(math.radians(lean_deg))
    pts = []
    z = z_start
    while z < H:
        k = min(1.0, max(z, 0.0) / 2.5 + 0.15)
        off = lean_dir * (tilt * max(z, 0.0) * (1 - 0.3 * max(z, 0.0) / H))
        wav = Vector((math.sin(z * 0.43 + ph[0]) + 0.4 * math.sin(z * 1.27 + ph[1]),
                      math.sin(z * 0.37 + ph[2]) + 0.4 * math.sin(z * 1.11 + ph[3]), 0.0)) * wobble * k
        pts.append(base + off + wav + Vector((0, 0, z)))
        z += step if z > 1.2 else 0.08
    pts.append(pts[-1] + (pts[-1] - pts[-2]).normalized() * (H - pts[-1].z))
    return pts


def trunk_radii(pts: list, r1: float, H: float, taper: float = 1.0, tip: float = 0.012) -> list:
    """Сбег: r1 — радиус на высоте 1,3 м; к вершине — tip."""
    out = []
    for p in pts:
        h = max(p.z, 0.0)
        k = max(1.0 - h / H, 0.0) ** taper / max(1.0 - 1.3 / H, 0.05) ** taper
        out.append(max(tip, r1 * k))
    return out


def trunk_shape(pts: list, rng: random.Random, flare: float, flare_h: float, lobes: int, ovality: float = 0.05):
    """Множитель радиуса ствола: корневые наплывы лопастями у земли и неровное сечение выше."""
    ph = [rng.uniform(0, 6.28) for _ in range(6)]
    lob = [rng.uniform(0.6, 1.2) for _ in range(lobes)]

    def f(i: int, a: float) -> float:
        z = pts[i].z
        # вогнутый наплыв: быстро сходит на нет к flare_h, ниже земли — полный
        fl = math.exp(-max(z, 0.0) / (flare_h * 0.38)) if flare_h > 0 else 0.0
        lobe = 0.0
        if lobes:
            k = (a / (2 * math.pi) * lobes) % lobes
            j = int(k)
            w = 0.5 + 0.5 * math.cos(2 * math.pi * (k - j - 0.5))
            lobe = w ** 3 * lob[j]
        sec = 1.0 + ovality * math.sin(2 * a + ph[0] + z * 0.3) + ovality * 0.5 * math.sin(3 * a + ph[1] + z * 0.5)
        return sec * (1.0 + flare * (0.4 * fl + 1.25 * fl * fl * lobe))
    return f


# ------------------------------------------------------------------ размещение модулей веточек

@dataclass
class Twigs:
    """Модули веточек на дереве: точки, повороты (локальная +X — ось модуля, +Z — лицо листьев), масштаб, номер модуля."""
    pts: list = field(default_factory=list)
    rots: list = field(default_factory=list)
    scales: list = field(default_factory=list)
    ids: list = field(default_factory=list)

    def add(self, p: Vector, x_dir: Vector, z_hint: Vector, scale: float, tid: int) -> None:
        self.pts.append(p.copy())
        self.rots.append(frame_quat(x_dir, z_hint))
        self.scales.append(scale)
        self.ids.append(tid)


def twig_points_object(name: str, tw: Twigs, coll) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in tw.pts], [], [])
    ra = me.attributes.new("rot", "QUATERNION", "POINT")
    sa = me.attributes.new("scale", "FLOAT", "POINT")
    ia = me.attributes.new("tid", "INT", "POINT")
    for i in range(len(tw.pts)):
        q = tw.rots[i]
        ra.data[i].value = (q.w, q.x, q.y, q.z)
        sa.data[i].value = tw.scales[i]
        ia.data[i].value = tw.ids[i]
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def instancer_group(name: str, modules_coll) -> bpy.types.NodeTree:
    """Узлы: точки → модули коллекции по номеру tid, поворот rot, масштаб scale."""
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    ci = ng.nodes.new("GeometryNodeCollectionInfo")
    ci.inputs["Collection"].default_value = modules_coll
    ci.inputs["Separate Children"].default_value = True
    ci.inputs["Reset Children"].default_value = True
    ip = ng.nodes.new("GeometryNodeInstanceOnPoints")
    ip.inputs["Pick Instance"].default_value = True
    na_r = ng.nodes.new("GeometryNodeInputNamedAttribute")
    na_r.data_type = "QUATERNION"
    na_r.inputs["Name"].default_value = "rot"
    na_s = ng.nodes.new("GeometryNodeInputNamedAttribute")
    na_s.data_type = "FLOAT"
    na_s.inputs["Name"].default_value = "scale"
    na_i = ng.nodes.new("GeometryNodeInputNamedAttribute")
    na_i.data_type = "INT"
    na_i.inputs["Name"].default_value = "tid"
    L = ng.links
    L.new(gi.outputs[0], ip.inputs["Points"])
    L.new(ci.outputs["Instances"], ip.inputs["Instance"])
    L.new(na_i.outputs["Attribute"], ip.inputs["Instance Index"])
    L.new(na_r.outputs["Attribute"], ip.inputs["Rotation"])
    L.new(na_s.outputs["Attribute"], ip.inputs["Scale"])
    L.new(ip.outputs["Instances"], go.inputs[0])
    for i, n in enumerate([gi, na_i, na_r, na_s, ci, ip, go]):
        n.location = (i * 200 - 600, 0)
    return ng


# ------------------------------------------------------------------ материалы для осмотра формы (диагностика)

def diag_material(name: str, rgb: tuple, rough: float = 0.8, two_sided_leaf: bool = False) -> bpy.types.Material:
    mt = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mt.use_nodes = True
    mt.diffuse_color = (*rgb, 1.0)          # цвет в режиме Solid → Material
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if two_sided_leaf:
        bsdf.inputs["Transmission Weight"].default_value = 0.0
        bsdf.inputs["Subsurface Weight"].default_value = 0.0
    return mt


def leaf_material(name: str, rgb: tuple, vary: float = 0.18) -> bpy.types.Material:
    """Лист для осмотра: ровный зелёный, оттенок чуть гуляет по цвету вершин (r) — видно отдельные листья."""
    mt = diag_material(name, rgb, 0.65)
    nt = mt.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(attr.outputs["Color"], sep.inputs[0])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    mix.inputs[6].default_value = (*rgb, 1.0)
    comb = nt.nodes.new("ShaderNodeCombineColor")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 1.0 - vary
    mr.inputs["To Max"].default_value = 1.0 + vary
    nt.links.new(sep.outputs[0], mr.inputs["Value"])
    for k in range(3):
        nt.links.new(mr.outputs[0], comb.inputs[k])
    nt.links.new(comb.outputs[0], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return mt


# ------------------------------------------------------------------ сцена осмотра

def new_collection(name: str, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in [x.name for x in (parent or bpy.context.scene.collection).children]:
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def scale_figure(coll, at: Vector) -> bpy.types.Object:
    """Мерка 1,75 м — силуэт человека из простых тел (только для сравнения размеров, не ассет)."""
    m = Mesh()
    seg = 10
    def cyl(c0: Vector, c1: Vector, r: float) -> None:
        m.tube("fig", [c0, c1], [r, r], seg)
    cyl(Vector((0.1, 0, 0)), Vector((0.1, 0, 0.86)), 0.07)
    cyl(Vector((-0.1, 0, 0)), Vector((-0.1, 0, 0.86)), 0.07)
    cyl(Vector((0, 0, 0.84)), Vector((0, 0, 1.45)), 0.19)
    cyl(Vector((0.27, 0, 1.42)), Vector((0.3, 0, 0.82)), 0.05)
    cyl(Vector((-0.27, 0, 1.42)), Vector((-0.3, 0, 0.82)), 0.05)
    cyl(Vector((0, 0, 1.45)), Vector((0, 0, 1.53)), 0.06)
    ring = 8
    head = []
    for i in range(ring + 1):
        t = i / ring
        head.append(Vector((0, 0, 1.53 + 0.22 * t)))
    m.tube("fig", head, [max(0.01, 0.1 * math.sin(math.pi * (0.08 + 0.84 * i / ring))) for i in range(ring + 1)], seg)
    ob = m.build("Мерка_1.75м", {"fig": diag_material("Мерка", (0.75, 0.32, 0.12))}, coll)
    ob.location = at
    return ob


def studio(coll, size: float = 80.0) -> None:
    """Пол, солнце, небо — нейтральный осмотр формы."""
    gm = Mesh()
    s = size
    gm.poly("ground", [Vector((-s, -s, 0)), Vector((s, -s, 0)), Vector((s, s, 0)), Vector((-s, s, 0))], [(0, 0), (1, 0), (1, 1), (0, 1)])
    gm.build("Пол", {"ground": diag_material("Пол", (0.32, 0.31, 0.29), 0.95)}, coll, smooth=False)
    sun = bpy.data.objects.new("Солнце", bpy.data.lights.new("Солнце", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(1.5)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-38))
    coll.objects.link(sun)
    w = bpy.data.worlds.new("Небо осмотра")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.55, 0.62, 0.72, 1)
    bg.inputs[1].default_value = 0.9
    bpy.context.scene.world = w


def set_viewports(clip_end: float = 1000.0) -> None:
    """Окна 3D файла: Solid с цветом материалов, дальняя граница видимости."""
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.shading.type = "SOLID"
                    sp.shading.color_type = "MATERIAL"
                    sp.shading.light = "STUDIO"
                    sp.shading.show_shadows = True
                    sp.clip_end = clip_end


def gpu() -> None:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    bpy.context.scene.cycles.device = "GPU"
                    return
            except TypeError:
                continue
    except Exception as e:  # noqa: BLE001
        print("PLANTS GPU нет:", e)


def evaluated_bounds(objs: list) -> tuple:
    """Полный габарит после узлов (с экземплярами модулей) в мировых координатах."""
    dg = bpy.context.evaluated_depsgraph_get()
    names = {o.name for o in objs}
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for inst in dg.object_instances:
        top = inst.parent.original.name if inst.is_instance and inst.parent else inst.object.original.name
        if top not in names:
            continue
        ob = inst.object
        if ob.type != "MESH":
            continue
        mw = inst.matrix_world
        for c in ob.bound_box:
            w = mw @ Vector(c)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi
