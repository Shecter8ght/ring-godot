"""Растения «Проспекта»: виды и экземпляры (форма, без PBR). Набор средней полосы, городское озеленение, лето.

  birch   — берёза повислая (Betula pendula): белый ствол, ветви вверх и дугой вниз, с них висят пряди тонких веточек.
  linden  — липа мелколистная (Tilia cordata): самое массовое уличное дерево; крона яйцевидная, плотная, листья
            сердцевидные, лежат плоскими «веерами» (двурядно); у комля городских лип — поросль.
  poplar  — тополь берлинский (Populus × berolinensis): крона узкопирамидальная, ветви круто вверх; второй экземпляр —
            «кронированный» по-московски: ствол спилен на 9 м, из культей — метла прямых побегов.
  lilac   — сирень обыкновенная (Syringa vulgaris): многоствольный куст, листья супротивные, сердцевидные, цельные;
            летом — засохшие метёлки с коробочками; внутри куста голые серые стволики.
  hedge   — живая изгородь из кизильника блестящего (Cotoneaster lucidus): была стриженым «брусом», город брошен два года
            назад — два лета без стрижки: форма бруса читается, сверху и с боков торчат длинные побеги, низ оголился.

Модуль веточки: локальная +X — ось побега от прикрепления, +Z — сторона, куда смотрят листья. Размеры — метры, 1:1.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

from mathutils import Vector

import plib
from plib import X, Y, Z, Branch, Envelope, LeafShape, Level, Mesh, Twigs

# ------------------------------------------------------------------ контуры листьев (половина, доли длины)

LEAF = {
    # ромбически-треугольный, ширококлиновидное основание, оттянутый кончик
    "birch": LeafShape([(0.0, 0.0), (0.2, 0.02), (0.33, 0.12), (0.37, 0.25), (0.33, 0.42), (0.25, 0.6), (0.15, 0.77),
                        (0.06, 0.92), (0.0, 1.0)], petiole=(0.35, 0.5), fold=0.1, curl=0.05),
    # сердцевидный, несимметричный, короткий оттянутый кончик
    "linden": LeafShape([(0.0, 0.0), (0.1, -0.07), (0.27, -0.07), (0.41, 0.06), (0.46, 0.27), (0.42, 0.5), (0.31, 0.7),
                         (0.17, 0.86), (0.05, 0.96), (0.0, 1.0)], petiole=(0.38, 0.5), fold=0.07, curl=0.05, asym=0.12),
    # яйцевидный с длинной вершиной, клиновидное основание
    "poplar": LeafShape([(0.0, 0.0), (0.15, 0.03), (0.27, 0.13), (0.31, 0.3), (0.28, 0.48), (0.21, 0.66), (0.12, 0.82),
                         (0.04, 0.94), (0.0, 1.0)], petiole=(0.3, 0.45), fold=0.09, curl=0.07),
    # сердцевидно-яйцевидный, цельнокрайный, заострённый
    "lilac": LeafShape([(0.0, 0.0), (0.09, -0.05), (0.24, -0.03), (0.35, 0.1), (0.38, 0.28), (0.33, 0.48), (0.23, 0.67),
                        (0.12, 0.84), (0.04, 0.95), (0.0, 1.0)], petiole=(0.22, 0.32), fold=0.13, curl=0.06),
    # эллиптический, заострённый, мелкий
    "cotoneaster": LeafShape([(0.0, 0.0), (0.12, 0.05), (0.23, 0.2), (0.27, 0.4), (0.24, 0.6), (0.16, 0.78), (0.07, 0.92),
                              (0.0, 1.0)], petiole=(0.08, 0.14), fold=0.12, curl=0.05),
}


def shade(rng: random.Random) -> tuple:
    """Цвет вершин листа: r — оттенок (вариация в материале осмотра)."""
    return (rng.random(), 0.0, 0.0, 1.0)


# ------------------------------------------------------------------ побег с листьями (модуль веточки)

@dataclass
class Shoot:
    length: float
    leaf: str
    leaf_len: tuple                   # длина листа, м (мин, макс)
    node: tuple = (0.04, 0.06)        # шаг узлов, м
    phyllo: str = "dist"              # dist — двурядно, spiral — по спирали, opp — супротивно, spur — укороченные побеги по 2 листа
    r0: float = 0.003
    zigzag: float = 0.0               # излом оси в узлах (липа)
    bend: float = 0.0                 # прогиб оси к концу по −Z (м на всю длину)
    curve_y: float = 0.0
    face_spread: float = 0.35         # разброс нормалей листьев вокруг +Z
    face: Vector = field(default_factory=lambda: Z.copy())
    forward: float = 0.45             # насколько черешок наклонён вперёд по оси
    side_shoots: int = 0              # боковых веточек
    side_angle: tuple = (40, 60)
    side_len: tuple = (0.35, 0.6)
    start: float = 0.06               # голый низ оси
    leaf_grow: Callable = lambda t: 1.0   # размер листа вдоль побега (t — доля)
    terminal: int = 1                 # листьев на конце
    sub_strand: float = 0.0           # вероятность боковой пряди (берёза)


def build_shoot(m: Mesh, rng: random.Random, sh: Shoot, origin: Vector = None, xdir: Vector = None, zdir: Vector = None,
                depth: int = 0) -> None:
    origin = origin if origin is not None else Vector((0, 0, 0))
    xdir = (xdir if xdir is not None else X).normalized()
    zdir = zdir if zdir is not None else Z
    zdir = (zdir - xdir * zdir.dot(xdir)).normalized()
    ydir = zdir.cross(xdir).normalized()
    L = sh.length
    n = max(4, int(L / 0.03))
    pts = []
    zz = 0.0
    for i in range(n + 1):
        t = i / n
        y = sh.curve_y * math.sin(math.pi * t) + (sh.zigzag * (1 if (i % 2) else -1) if 0 < i < n else 0.0)
        z = -sh.bend * t * t
        pts.append(origin + xdir * (L * t) + ydir * y + zdir * z)
    r_end = max(0.0008, sh.r0 * 0.3)
    m.tube("twig", pts, [sh.r0 + (r_end - sh.r0) * (i / n) for i in range(n + 1)], 4 if sh.r0 > 0.002 else 3)
    face = sh.face.normalized()
    face_w = (xdir * face.x + ydir * face.y + zdir * face.z).normalized()
    # узлы
    s = sh.start * L + rng.uniform(0, sh.node[1])
    side = 1
    roll = rng.uniform(0, 6.28)
    side_left = sh.side_shoots
    side_slots = sorted(rng.uniform(0.15, 0.65) for _ in range(sh.side_shoots))
    while s < L * 0.97:
        t = s / L
        p, tan = plib.point_at(pts, t)
        nrm_side = (zdir - tan * zdir.dot(tan)).normalized()
        lat = nrm_side.cross(tan).normalized()
        size = rng.uniform(*sh.leaf_len) * sh.leaf_grow(t)
        if side_left and side_slots and t >= side_slots[0]:
            side_slots.pop(0)
            side_left -= 1
            ang = math.radians(rng.uniform(*sh.side_angle))
            sd = (tan * math.cos(ang) + lat * side * math.sin(ang)).normalized()
            sub = Shoot(**{**sh.__dict__, "length": L * (1 - t) * rng.uniform(*sh.side_len), "side_shoots": 0,
                           "r0": sh.r0 * 0.6, "start": 0.1})
            build_shoot(m, rng, sub, p, sd, zdir, depth + 1)
        dirs = []
        if sh.phyllo == "dist":
            dirs = [lat * side]
            side = -side
        elif sh.phyllo == "spiral":
            dirs = [plib.rotate_about(lat, tan, roll)]
            roll += math.radians(144) + rng.uniform(-0.3, 0.3)
        elif sh.phyllo == "opp":
            d0 = plib.rotate_about(lat, tan, roll)
            dirs = [d0, -d0]
            roll += math.pi / 2 + rng.uniform(-0.15, 0.15)
        elif sh.phyllo == "spur":
            d0 = plib.rotate_about(lat, tan, roll)
            roll += math.radians(144) + rng.uniform(-0.4, 0.4)
            q = p + d0 * rng.uniform(0.006, 0.016) + tan * 0.004
            m.tube("twig", [p, q], [sh.r0 * 0.5, sh.r0 * 0.4], 3, cap=False)
            for k in range(rng.choice([1, 2, 2, 2, 3]) if size > 0.005 else 0):
                dd = (d0 * 0.6 + tan * sh.forward + plib.rand_unit(rng) * 0.45).normalized()
                nrm = (face_w + plib.rand_unit(rng) * sh.face_spread).normalized()
                plib.leaf(m, rng, q, dd, nrm, size * rng.uniform(0.8, 1.05), LEAF[sh.leaf], col=shade(rng))
            if sh.sub_strand and depth == 0 and rng.random() < sh.sub_strand:
                sub = Shoot(**{**sh.__dict__, "length": (L - s) * rng.uniform(0.3, 0.6), "r0": sh.r0 * 0.55, "start": 0.05,
                               "sub_strand": 0.0})
                build_shoot(m, rng, sub, p, (tan * 0.8 + d0 * 0.5).normalized(), zdir, depth + 1)
            s += rng.uniform(*sh.node)
            continue
        for d in dirs:
            if size < 0.005:
                break
            dd = (d + tan * sh.forward + plib.rand_unit(rng) * 0.15).normalized()
            nrm = (face_w + plib.rand_unit(rng) * sh.face_spread).normalized()
            plib.leaf(m, rng, p + d * sh.r0, dd, nrm, size, LEAF[sh.leaf], col=shade(rng))
        s += rng.uniform(*sh.node)
    tip, tan = pts[-1], (pts[-1] - pts[-2]).normalized()
    for k in range(sh.terminal if sh.leaf_len[1] > 0.005 else 0):
        d = (tan + plib.rand_unit(rng) * 0.35).normalized()
        plib.leaf(m, rng, tip, d, (face_w + plib.rand_unit(rng) * sh.face_spread).normalized(),
                  rng.uniform(*sh.leaf_len) * sh.leaf_grow(1.0) * 0.85, LEAF[sh.leaf], col=shade(rng))


def module(fn: Callable[[Mesh, random.Random], None], seed: int) -> Mesh:
    m = Mesh()
    fn(m, random.Random(seed))
    return m


# ------------------------------------------------------------------ модули по видам

def birch_modules() -> list:
    # пряди: ось висит (в дереве +X смотрит вниз), листья лицом наружу (+Z) и немного вверх (−X)
    face = Vector((-0.45, 0, 1))
    strand = dict(leaf="birch", leaf_len=(0.042, 0.062), node=(0.032, 0.052), phyllo="spur", r0=0.0022, bend=0.0,
                  curve_y=0.03, face=face, face_spread=0.55, forward=0.55, start=0.08, sub_strand=0.22)
    return [
        ("01_прядь_длинная", module(lambda m, r: build_shoot(m, r, Shoot(length=1.15, **strand)), 11)),
        ("02_прядь_средняя", module(lambda m, r: build_shoot(m, r, Shoot(length=0.78, **strand)), 12)),
        ("03_прядь_короткая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.48, **{**strand, "sub_strand": 0.1})), 13)),
        ("04_побег_вверх", module(lambda m, r: build_shoot(m, r, Shoot(length=0.55, leaf="birch", leaf_len=(0.045, 0.065),
                                                                   node=(0.035, 0.05), phyllo="spiral", r0=0.0028, bend=0.06,
                                                                   face_spread=0.5, side_shoots=2, side_angle=(30, 45),
                                                                   side_len=(0.35, 0.55))), 14)),
        ("05_прядь_длинная_б", module(lambda m, r: build_shoot(m, r, Shoot(length=1.0, **strand)), 15)),
    ]


def linden_modules() -> list:
    # плоский «веер»: ось зигзагом, листья в две стороны, лицом вверх
    spray = dict(leaf="linden", leaf_len=(0.055, 0.078), node=(0.034, 0.05), phyllo="dist", r0=0.003, zigzag=0.008,
                 bend=0.06, face_spread=0.4, forward=0.35, side_angle=(40, 62), side_len=(0.4, 0.65),
                 leaf_grow=lambda t: 0.85 + 0.3 * math.sin(math.pi * min(1.0, t * 1.2)))
    return [
        ("01_веер_большой", module(lambda m, r: build_shoot(m, r, Shoot(length=0.75, side_shoots=4, **spray)), 21)),
        ("02_веер_средний", module(lambda m, r: build_shoot(m, r, Shoot(length=0.5, side_shoots=3, **spray)), 22)),
        ("03_веер_малый", module(lambda m, r: build_shoot(m, r, Shoot(length=0.3, side_shoots=2, **spray)), 23)),
        ("04_побег_вверх", module(lambda m, r: build_shoot(m, r, Shoot(length=0.45, leaf="linden", leaf_len=(0.05, 0.07),
                                                                   node=(0.045, 0.06), phyllo="spiral", r0=0.003, bend=0.04,
                                                                   face_spread=0.45, side_shoots=1)), 24)),
        # поросль у комля и на стволе: прямой побег, листья крупнее
        ("05_поросль", module(lambda m, r: build_shoot(m, r, Shoot(length=0.8, leaf="linden", leaf_len=(0.07, 0.1),
                                                               node=(0.06, 0.09), phyllo="dist", r0=0.004, zigzag=0.006,
                                                               bend=0.03, face_spread=0.4, forward=0.3, terminal=1)), 25)),
    ]


def poplar_modules() -> list:
    shoot = dict(leaf="poplar", leaf_len=(0.07, 0.1), node=(0.05, 0.075), phyllo="spiral", r0=0.0035, bend=0.04,
                 face_spread=0.6, forward=0.4, side_angle=(30, 45), side_len=(0.3, 0.5))
    return [
        ("01_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=0.6, side_shoots=2, **shoot)), 31)),
        ("02_побег_короткий", module(lambda m, r: build_shoot(m, r, Shoot(length=0.32, side_shoots=0, **shoot)), 32)),
        # пучок на укороченном побеге: 5–7 листьев с одной точки
        ("03_пучок", module(lambda m, r: build_shoot(m, r, Shoot(length=0.12, leaf="poplar", leaf_len=(0.07, 0.095),
                                                             node=(0.012, 0.02), phyllo="spiral", r0=0.004, face_spread=0.7,
                                                             forward=0.7, start=0.2, terminal=2)), 33)),
        # жировой побег культи: прямой, листья крупные (до 15 см)
        ("04_жировой_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=1.1, leaf="poplar", leaf_len=(0.1, 0.15),
                                                                     node=(0.06, 0.09), phyllo="spiral", r0=0.006, bend=0.03,
                                                                     face_spread=0.55, forward=0.35, start=0.12,
                                                                     leaf_grow=lambda t: 0.75 + 0.35 * t)), 34)),
    ]


def lilac_panicle(m: Mesh, rng: random.Random) -> None:
    """Побег с засохшей прошлогодней метёлкой: две пары листьев, на конце — бурые ветвистые кисти коробочек."""
    build_shoot(m, rng, Shoot(length=0.22, leaf="lilac", leaf_len=(0.07, 0.1), node=(0.06, 0.08), phyllo="opp", r0=0.004,
                              face_spread=0.35, forward=0.25, terminal=0, start=0.15))
    base = Vector((0.22, 0, 0))
    axis = [base + Vector((0.16 * i / 6, 0, 0.012 * math.sin(i))) for i in range(7)]
    m.tube("seed", axis, [0.0025 - 0.0015 * i / 6 for i in range(7)], 3)
    for i in range(1, 7):
        for sgn in (1, -1):
            if rng.random() < 0.8:
                p = axis[i]
                d = (Vector((0.5, sgn * 0.8, rng.uniform(-0.4, 0.4)))).normalized()
                ln = 0.05 * (1 - i / 8) + 0.015
                q = p + d * ln
                m.tube("seed", [p, q], [0.0012, 0.0008], 3, cap=False)
                for k in range(rng.randint(2, 4)):
                    c = q + plib.rand_unit(rng) * 0.008
                    # коробочка — вытянутое зёрнышко из двух створок
                    ax = (d + plib.rand_unit(rng) * 0.6).normalized()
                    m.tube("seed", [c, c + ax * 0.012], [0.0028, 0.0012], 4)


def lilac_modules() -> list:
    shoot = dict(leaf="lilac", leaf_len=(0.065, 0.11), node=(0.05, 0.08), phyllo="opp", r0=0.0035, bend=0.03,
                 face_spread=0.35, forward=0.3, start=0.1, terminal=2, leaf_grow=lambda t: 1.05 - 0.25 * t)
    return [
        ("01_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=0.38, **shoot)), 41)),
        ("02_побег_короткий", module(lambda m, r: build_shoot(m, r, Shoot(length=0.22, **shoot)), 42)),
        ("03_побег_с_метёлкой", module(lilac_panicle, 43)),
        ("04_побег_ветвистый", module(lambda m, r: build_shoot(m, r, Shoot(length=0.5, side_shoots=2, side_angle=(35, 50),
                                                                       side_len=(0.4, 0.6), **shoot)), 44)),
    ]


def hedge_modules() -> list:
    sprig = dict(leaf="cotoneaster", leaf_len=(0.024, 0.04), node=(0.013, 0.021), phyllo="dist", r0=0.002, zigzag=0.003,
                 bend=0.02, face_spread=0.45, forward=0.35, start=0.08, side_angle=(35, 60), side_len=(0.35, 0.6))
    return [
        ("01_веточка", module(lambda m, r: build_shoot(m, r, Shoot(length=0.24, side_shoots=3, **sprig)), 51)),
        ("02_веточка_малая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.15, side_shoots=1, **sprig)), 52)),
        # отросший за два лета побег: длинный, дугой
        ("03_длинный_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=0.6, side_shoots=3, curve_y=0.02,
                                                                     **{**sprig, "bend": 0.1, "r0": 0.003})), 53)),
        ("04_побег_средний", module(lambda m, r: build_shoot(m, r, Shoot(length=0.38, side_shoots=2, **{**sprig, "bend": 0.05})), 54)),
        # засохшая веточка (пролом изгороди): без листьев
        ("05_сухая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.3, side_shoots=3, **{**sprig, "leaf_len": (0.0, 0.0)})), 55)),
    ]


# ------------------------------------------------------------------ профили огибающих

def ovoid(tc: float, floor: float, top_pow: float = 1.0, bottom_pow: float = 1.0) -> Callable:
    """Яйцевидная крона: шире всего на tc, снизу обрезана до floor, верх — top_pow (> 1 — заострённый)."""
    def f(t: float) -> float:
        if t < tc:
            u = (tc - t) / tc
            return floor + (1 - floor) * max(0.0, 1 - u ** 2) ** (0.5 * bottom_pow)
        u = (t - tc) / (1 - tc)
        return max(0.0, 1 - u ** (2.0 / top_pow)) ** 0.5
    return f


def pyramid(tc: float, floor: float, pw: float) -> Callable:
    def f(t: float) -> float:
        if t < tc:
            return floor + (1 - floor) * (t / tc) ** 0.6
        return max(0.0, (1 - t) / (1 - tc)) ** pw
    return f


# ------------------------------------------------------------------ экземпляр

@dataclass
class Plant:
    key: str           # имя в игре
    label: str         # по-русски
    kind: str          # birch | linden | poplar | lilac | hedge
    height: float
    seed: int
    params: dict


def outward(p: Vector, center: Vector = None) -> Vector:
    c = center if center is not None else Vector((0, 0, 0))
    o = Vector((p.x - c.x, p.y - c.y, 0.0))
    return o.normalized() if o.length > 1e-4 else Vector((1, 0, 0))


def smooth(a: float, b: float, x: float) -> float:
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def wood_mat(threshold: float) -> Callable:
    return lambda br: "bark" if br.radii[min(1, len(br.radii) - 1)] > threshold else "branch"


def make_trunk(rng: random.Random, P: dict, base: Vector = None, lean_dir: Vector = None) -> Branch:
    base = base if base is not None else Vector((0, 0, 0))
    lean_dir = lean_dir if lean_dir is not None else Vector((math.cos(P["lean_az"]), math.sin(P["lean_az"]), 0))
    pts = plib.trunk_path(rng, base, P["H"], lean_dir, P["lean"], P["wobble"])
    radii = plib.trunk_radii(pts, P["r1"], P["H"], P.get("taper", 1.0))
    return Branch(pts, radii, 0, plib.path_len(pts))


def emit_trunk(m: Mesh, rng: random.Random, tr: Branch, P: dict, mat: str = "bark") -> None:
    shape = plib.trunk_shape(tr.pts, rng, P["flare"], P["flare_h"], P["lobes"], P.get("ovality", 0.05))
    r0 = tr.radii[min(3, len(tr.radii) - 1)]
    u, v = plib.bark_uv(r0)
    col_fn = plib.LOD.get("col") if plib.LOD else None
    if plib.LOD is None:
        m.tube(mat, tr.pts, tr.radii, plib.sides_for(r0) + (4 if r0 > 0.2 else 0), v_scale=v, u_reps=u, shape=shape)
    else:
        # в игре ствол реже по высоте выше комля (наплывы — как в форме)
        keep = [i for i, p in enumerate(tr.pts) if p.z < 1.2 or i % 2 == 0 or i == len(tr.pts) - 1]
        sub = [tr.pts[i] for i in keep]
        shape2 = lambda i, a: shape(keep[i], a)
        m.tube(mat, sub, [tr.radii[i] for i in keep], plib.lod_sides(plib.sides_for(r0) + (4 if r0 > 0.2 else 0)),
               v_scale=v, u_reps=u, shape=shape2, col_fn=col_fn)
    # корневые лапы: от наплывов наружу, уходят под землю
    base = tr.pts[0] + Vector((0, 0, -tr.pts[0].z))
    r = P["r1"]
    a0 = rng.uniform(0, 6.28)
    for k in range(P.get("roots", 0)):
        a = a0 + 2 * math.pi * (k + rng.uniform(-0.25, 0.25)) / P["roots"]
        o = Vector((math.cos(a), math.sin(a), 0))
        L = r * rng.uniform(1.4, 2.6)
        pts = [base + Vector((0, 0, 0.45)), base + o * r * 0.75 + Vector((0, 0, 0.12)), base + o * (r * 1.1 + L * 0.4) + Vector((0, 0, -0.02)),
               base + o * (r * 1.1 + L) + Vector((0, 0, -0.3))]
        if plib.LOD is not None and plib.LOD.get("no_roots"):
            continue
        u, v = plib.bark_uv(r * 0.45)
        m.tube(mat, pts, [r * 0.5, r * 0.45, r * 0.3, r * 0.14], plib.lod_sides(max(8, plib.sides_for(r * 0.4))), v_scale=v,
               u_reps=u, shape=lambda i, a: 1.0 - 0.3 * abs(math.sin(a)) * (i / 3), col_fn=col_fn)


# ---------------------------------------------------------------- берёза

def build_birch(pl: Plant) -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    env = Envelope(P["crown_base"], H + 0.4, P["rmax"], ovoid(0.38, 0.55, 1.6), seed=pl.seed, lump=0.2)
    trunks = []
    az0 = rng.uniform(0, 6.28)
    for si in range(P["stems"]):
        a = az0 + 2 * math.pi * si / P["stems"]
        d = Vector((math.cos(a), math.sin(a), 0))
        Ps = dict(P, H=H * (1.0 if si == 0 else rng.uniform(0.84, 0.93)), r1=P["r1"] * (1 if si == 0 else 0.82),
                  lean=P["lean"] * (1 if P["stems"] == 1 else rng.uniform(0.8, 1.2)), lean_az=a)
        tr = make_trunk(rng, Ps, d * (0.05 if P["stems"] > 1 else 0.0), d)
        emit_trunk(m, rng, tr, dict(Ps, flare=P["flare"] * (0.6 if P["stems"] > 1 else 1.0)))
        trunks.append((tr, Ps))
    Lmain = P["rmax"] * 1.6
    levels = [
        Level(spacing=P["main_step"], s0=P["crown_base"] / H, s1=0.97, angle=(28, 58), roll="spiral",
              length=lambda s, L, r: Lmain * r.uniform(0.45, 1.05) * (1 - 0.45 * max(0.0, s - 0.6) / 0.4),
              tropism=lambda t: 0.06 - 0.24 * t, wiggle=0.06, seg=0.45, radius_k=0.5, tip=0.25),
        Level(spacing=0.3, s0=0.15, s1=0.96, angle=(26, 54), roll="spiral",
              length=lambda s, L, r: L * r.uniform(0.25, 0.48) * (1 - 0.5 * s),
              tropism=lambda t: -0.08 - 0.15 * t, wiggle=0.1, seg=0.28, radius_k=0.55, tip=0.3, env_tol=1.1),
    ]
    for tr, Ps in trunks:
        plib.branch_children(tr, levels, rng, env, 0)
        plib.emit_branches(m, tr, wood_mat(0.035), skip_root=True)
        # пряди с ветвей второго порядка и внешней половины главных
        for br in plib.all_branches(tr)[1:]:
            s = 0.2 if br.level == 2 else 0.3
            while s < 1.0:
                p, tan = plib.point_at(br.pts, min(s, 0.995))
                fr = env.frac(p)
                if fr < 9 and rng.random() < smooth(0.25, 0.75, fr) * 0.95 + 0.05:
                    rel = min(max((p.z - P["crown_base"]) / (H - P["crown_base"]), 0.0), 1.0)
                    out = outward(p)
                    if rel > 0.8 and rng.random() < 0.6:
                        d = (tan + Z * 0.9 + out * 0.2).normalized()
                        tw.add(p, d, out + Z * 0.3, rng.uniform(0.7, 1.0), 3)
                    else:
                        d = (-Z + out * rng.uniform(0.15, 0.45) + plib.rand_unit(rng) * 0.15).normalized()
                        tid = rng.choice([0, 0, 4, 1, 1, 2]) if rel < 0.6 else rng.choice([1, 2, 2, 4])
                        tw.add(p, d, out, rng.uniform(0.8, 1.15) * (1.15 - 0.3 * rel), tid)
                s += 0.13 / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
        # вершина: вертикальные побеги
        top = tr.pts[-1]
        for k in range(4):
            a = k * 1.7 + rng.uniform(-0.3, 0.3)
            o = Vector((math.cos(a), math.sin(a), 0))
            tw.add(top - Z * rng.uniform(0.2, 1.0), (Z + o * 0.3).normalized(), o, rng.uniform(0.8, 1.1), 3)
    return m, tw, env


# ---------------------------------------------------------------- липа

def build_linden(pl: Plant) -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    env = Envelope(P["crown_base"] - 0.3, H + 0.3, P["rmax"], ovoid(0.42, 0.72, 0.85, 0.8), seed=pl.seed, lump=0.16,
                   shift=Vector((P.get("shift", 0.0), 0, 0)))
    tr = make_trunk(rng, P)
    emit_trunk(m, rng, tr, P)
    Lmain = P["rmax"] * 1.7
    levels = [
        Level(spacing=P["main_step"], s0=P["crown_base"] / H, s1=0.96, angle=(38, 66), roll="spiral",
              length=lambda s, L, r: Lmain * r.uniform(0.5, 1.0), tropism=lambda t: 0.07 - 0.03 * t, wiggle=0.07,
              seg=0.55, radius_k=0.58, tip=0.22),
        Level(spacing=0.38 * P.get("branch_k", 1.0), s0=0.12, s1=0.97, angle=(35, 60), roll="spiral",
              length=lambda s, L, r: L * r.uniform(0.3, 0.5) * (1 - 0.55 * s), tropism=lambda t: 0.03, wiggle=0.1,
              seg=0.32, flat=0.25, radius_k=0.6, tip=0.3, env_tol=1.06),
    ]
    if P.get("levels3", True):
        levels.append(Level(spacing=0.3 * P.get("branch_k", 1.0), s0=0.2, s1=0.95, angle=(40, 62), roll="alt",
                            length=lambda s, L, r: L * r.uniform(0.35, 0.55), tropism=lambda t: 0.01, wiggle=0.12,
                            seg=0.22, flat=0.45, radius_k=0.6, tip=0.35, keep=0.85, env_tol=1.08))
    plib.branch_children(tr, levels, rng, env, 0)
    plib.emit_branches(m, tr, wood_mat(0.035), skip_root=True)
    last = len(levels)
    for br in plib.all_branches(tr)[1:]:
        if br.level < last - 1:
            continue
        s = 0.2
        while s < 1.0:
            p, tan = plib.point_at(br.pts, min(s, 0.995))
            fr = env.frac(p)
            if fr < 9 and rng.random() < smooth(0.3, 0.8, fr) * 0.9 + 0.1:
                rel = min(max((p.z - P["crown_base"]) / (H - P["crown_base"]), 0.0), 1.0)
                out = outward(p, env.center(p.z))
                if rel > 0.85 and rng.random() < 0.5:
                    tw.add(p, (tan + Z * 0.8).normalized(), out + Z * 0.4, rng.uniform(0.8, 1.1), 3)
                else:
                    d = (tan * 0.5 + out * 0.6 + plib.rand_unit(rng) * 0.35)
                    d = Vector((d.x, d.y, d.z * 0.55 - 0.18 * (1 - rel))).normalized()
                    tid = rng.choice([0, 0, 1, 1, 2]) if br.level == last else rng.choice([1, 2, 2])
                    face = Z * (0.5 + 0.5 * rel) + out * (0.9 - 0.4 * rel) * min(1.0, fr) + plib.rand_unit(rng) * 0.35
                    tw.add(p, d, face, rng.uniform(0.85, 1.15), tid)
            s += P.get("twig_step", 0.16) / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
        p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
        tw.add(p, Vector((tan.x, tan.y, tan.z * 0.5)).normalized(), Z + outward(p, env.center(p.z)) * 0.6, rng.uniform(0.9, 1.15), 0)
    # поросль у комля и «волчки» на стволе — у городских лип
    for k in range(P.get("suckers", 0)):
        a = rng.uniform(0, 6.28)
        o = Vector((math.cos(a), math.sin(a), 0))
        if k < P["suckers"] * 0.7:
            z = rng.uniform(-0.05, 0.35)
            r = P["r1"] * (1.25 + 0.4 * max(0.0, 0.35 - z))
        else:
            z = rng.uniform(1.0, P["crown_base"] - 0.3)
            r = P["r1"] * 0.95
        base = plib.point_at(tr.pts, max(0.0, (z + 0.35) / (H + 0.35)))[0] + o * r * 0.9
        d = (Z * rng.uniform(1.2, 2.5) + o).normalized()
        tw.add(base, d, o, rng.uniform(0.6, 1.25), 4)
    return m, tw, env


# ---------------------------------------------------------------- тополь

def build_poplar(pl: Plant) -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    tr = make_trunk(rng, P)
    emit_trunk(m, rng, tr, P)
    if not P.get("pollard"):
        env = Envelope(P["crown_base"] - 0.3, H + 0.4, P["rmax"], pyramid(0.22, 0.6, 0.85), seed=pl.seed, lump=0.18)
        Lmain = P["rmax"] * 2.6
        levels = [
            Level(spacing=P["main_step"], s0=P["crown_base"] / H, s1=0.97, angle=(20, 36), roll="spiral",
                  length=lambda s, L, r: Lmain * r.uniform(0.55, 1.0), tropism=lambda t: 0.05, wiggle=0.06, seg=0.6,
                  radius_k=0.5, tip=0.22),
            Level(spacing=0.36, s0=0.15, s1=0.96, angle=(24, 42), roll="spiral",
                  length=lambda s, L, r: L * r.uniform(0.2, 0.38) * (1 - 0.4 * s), tropism=lambda t: 0.06, wiggle=0.09,
                  seg=0.32, radius_k=0.55, tip=0.3, env_tol=1.08),
            Level(spacing=0.3, s0=0.2, s1=0.95, angle=(28, 48), roll="spiral",
                  length=lambda s, L, r: L * r.uniform(0.3, 0.5), tropism=lambda t: 0.04, wiggle=0.12, seg=0.2,
                  radius_k=0.6, tip=0.35, keep=0.85, env_tol=1.1),
        ]
        plib.branch_children(tr, levels, rng, env, 0)
        plib.emit_branches(m, tr, wood_mat(0.04), skip_root=True)
        for br in plib.all_branches(tr)[1:]:
            if br.level < 2:
                continue
            s = 0.2
            while s < 1.0:
                p, tan = plib.point_at(br.pts, min(s, 0.995))
                fr = env.frac(p)
                if fr < 9 and rng.random() < smooth(0.3, 0.8, fr) * 0.85 + 0.15:
                    out = outward(p)
                    d = (tan + Z * 0.4 + plib.rand_unit(rng) * 0.3).normalized()
                    tid = rng.choice([0, 0, 1, 2, 2]) if br.level == 3 else rng.choice([0, 1, 2])
                    tw.add(p, d, out + Z * 0.5 + plib.rand_unit(rng) * 0.4, rng.uniform(0.85, 1.15), tid)
                s += 0.18 / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
            p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
            tw.add(p, (tan + Z * 0.5).normalized(), outward(p) + Z, rng.uniform(0.9, 1.15), 0)
        return m, tw, env
    # кронированный: культи скелетных ветвей с наплывами, из них — метла прямых побегов; волчки по стволу
    env = Envelope(P["crown_base"] - 1.0, P["H"] + P["regrow"] + 0.5, P["rmax"], ovoid(0.45, 0.6, 0.7), seed=pl.seed, lump=0.25)
    limbs = []
    for k in range(P["limbs"]):
        z = P["crown_base"] + (H - P["crown_base"]) * (k + rng.uniform(0.1, 0.9)) / P["limbs"]
        if k == P["limbs"] - 1:
            z = H - 0.15
        p, tan = plib.point_at(tr.pts, (z + 0.35) / (H + 0.35))
        a = rng.uniform(0, 6.28) if k == 0 else limbs[-1][1] + math.radians(137.5) + rng.uniform(-0.4, 0.4)
        o = Vector((math.cos(a), math.sin(a), 0))
        ang = math.radians(rng.uniform(18, 40)) if k < P["limbs"] - 1 else math.radians(rng.uniform(3, 10))
        d = (Z * math.cos(ang) + o * math.sin(ang)).normalized()
        L = rng.uniform(0.6, 1.7) if k < P["limbs"] - 1 else 0.25
        rp = plib.radius_at(tr, (z + 0.35) / (H + 0.35))
        rc = rp * rng.uniform(0.6, 0.8) if k < P["limbs"] - 1 else rp * 0.95
        n = 5
        pts = [p] + [p + d * (rp * 0.5 + L * i / n) + plib.rand_unit(rng) * 0.03 * i for i in range(1, n + 1)]
        radii = [rc * 1.05, rc * 1.2] + [rc * (1 - 0.15 * i / n) for i in range(2, n + 1)]
        radii[-1] *= 1.35        # наплыв на срезе (культя)
        br = Branch(pts, radii, 1, plib.path_len(pts))
        u, v = plib.bark_uv(rc)
        m.tube("bark", pts, radii, plib.lod_sides(plib.sides_for(rc)), v_scale=v, u_reps=u,
               col_fn=plib.LOD.get("col") if plib.LOD else None)
        limbs.append((br, a))
    shoot_lv = Level(spacing=0.1, s0=0.0, s1=1.0, angle=(4, 30), roll="spiral", length=lambda s, L, r: 0.0,
                     tropism=lambda t: 0.1, wiggle=0.05, seg=0.35, tip=0.35, env_tol=1.15)
    side_lv = Level(spacing=0.35, s0=0.25, s1=0.9, angle=(25, 45), roll="spiral",
                    length=lambda s, L, r: L * r.uniform(0.15, 0.35), tropism=lambda t: 0.08, wiggle=0.1, seg=0.2,
                    radius_k=0.6, tip=0.35, keep=0.6, env_tol=1.2)
    shoots = []
    for br, a in limbs:
        tip, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
        for k in range(rng.randint(*P["per_limb"])):
            o = plib.rand_unit(rng)
            start = tip + o * br.radii[-1] * 0.9
            d = (Z * rng.uniform(1.8, 3.5) + tan * 0.5 + Vector((o.x, o.y, 0)) * rng.uniform(0.4, 1.2)).normalized()
            L = P["regrow"] * rng.uniform(0.45, 1.05)
            pts = plib.grow(start, d, L, shoot_lv, rng, env)
            if len(pts) < 2:
                continue
            rc = rng.uniform(0.015, 0.045) * (1.0 if L > P["regrow"] * 0.6 else 0.7)
            radii = [rc * 1.3] + [rc * (1 - 0.65 * i / (len(pts) - 1)) for i in range(1, len(pts))]
            sh = Branch(pts, radii, 2, plib.path_len(pts))
            plib.branch_children(sh, [side_lv], rng, env, 0)
            plib.emit_branches(m, sh, wood_mat(0.04))
            shoots.append(sh)
    # волчки по стволу ниже культей
    for k in range(P.get("epicormic", 0)):
        z = rng.uniform(2.0, P["crown_base"])
        p, tan = plib.point_at(tr.pts, (z + 0.35) / (H + 0.35))
        o = Vector((math.cos(rng.uniform(0, 6.28)), math.sin(rng.uniform(0, 6.28)), 0)).normalized()
        start = p + o * plib.radius_at(tr, (z + 0.35) / (H + 0.35)) * 0.9
        d = (Z * rng.uniform(1.0, 2.5) + o).normalized()
        pts = plib.grow(start, d, rng.uniform(0.5, 1.6), shoot_lv, rng, None)
        rc = rng.uniform(0.006, 0.014)
        sh = Branch(pts, [rc * (1 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], 2, plib.path_len(pts))
        plib.emit_branches(m, sh, wood_mat(0.04))
        shoots.append(sh)
    for sh in shoots:
        for br in plib.all_branches(sh):
            s = 0.25 if br.level == 2 else 0.2
            while s < 1.0:
                p, tan = plib.point_at(br.pts, min(s, 0.995))
                out = outward(p)
                tid = rng.choice([3, 3, 0]) if br is sh else rng.choice([0, 1, 2])
                tw.add(p, (tan * 0.7 + out * 0.4 + plib.rand_unit(rng) * 0.25).normalized(), out + Z * 0.5,
                       rng.uniform(0.8, 1.1), tid)
                s += 0.28 / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
            p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
            tw.add(p, tan, outward(p) + Z * 0.3, rng.uniform(0.9, 1.1), 3 if br is sh else 0)
    return m, tw, env


# ---------------------------------------------------------------- сирень

def build_lilac(pl: Plant) -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H, W = P["H"], P["W"]
    env = Envelope(0.15, H - 0.1, W * 0.5, ovoid(0.42, 0.62, 0.9, 0.7), seed=pl.seed, lump=0.22,
                   squash_y=P.get("squash", 1.0))
    stem_lv = Level(spacing=1.0, s0=0, s1=1, angle=(0, 0), length=lambda s, L, r: 0.0, tropism=lambda t: 0.02 - 0.06 * t,
                    wiggle=0.07, seg=0.28, env_tol=1.05)
    levels = [
        Level(spacing=0.24, s0=0.22, s1=0.97, angle=(22, 46), roll="opp",
              length=lambda s, L, r: r.uniform(0.3, 0.8) * (1 - 0.5 * s) * P["side_k"], tropism=lambda t: 0.06, wiggle=0.1,
              seg=0.18, radius_k=0.6, tip=0.35, keep=0.8, env_tol=1.1),
        Level(spacing=0.17, s0=0.3, s1=0.95, angle=(28, 48), roll="opp",
              length=lambda s, L, r: r.uniform(0.14, 0.32), tropism=lambda t: 0.06, wiggle=0.12, seg=0.12,
              radius_k=0.6, tip=0.4, keep=0.75, env_tol=1.15),
    ]
    stems = []
    for k in range(P["stems"]):
        a = rng.uniform(0, 6.28)
        rr = P["clump"] * math.sqrt(rng.random())
        base = Vector((math.cos(a) * rr, math.sin(a) * rr * P.get("squash", 1.0), -0.12))
        o = Vector((math.cos(a), math.sin(a), 0))
        lean = math.radians(rng.uniform(3, 10) + 16 * rr / max(P["clump"], 0.01))
        d = (Z * math.cos(lean) + o * math.sin(lean)).normalized()
        L = H * rng.uniform(0.6, 0.92) / max(math.cos(lean), 0.5)
        pts = plib.grow(base, d, L, stem_lv, rng, env)
        rc = rng.uniform(*P["stem_r"])
        n = len(pts)
        radii = [rc * (1 - 0.7 * i / max(n - 1, 1)) for i in range(n)]
        radii[0] *= 1.25
        st = Branch(pts, radii, 0, plib.path_len(pts))
        plib.branch_children(st, levels, rng, env, 0, floor=0.3)
        plib.emit_branches(m, st, wood_mat(0.022))
        stems.append(st)
    # молодая поросль у основания
    for k in range(P.get("suckers", 0)):
        a = rng.uniform(0, 6.28)
        rr = P["clump"] * rng.uniform(0.8, 1.4)
        base = Vector((math.cos(a) * rr, math.sin(a) * rr, -0.05))
        d = (Z * 3 + Vector((math.cos(a), math.sin(a), 0))).normalized()
        pts = plib.grow(base, d, rng.uniform(0.6, 1.3), stem_lv, rng, None)
        st = Branch(pts, [0.008 * (1 - 0.6 * i / (len(pts) - 1)) for i in range(len(pts))], 1, plib.path_len(pts))
        plib.emit_branches(m, st, wood_mat(0.022))
        stems.append(st)
    for st in stems:
        for br in plib.all_branches(st):
            s = 0.3 if br.level == 0 else 0.25
            while s < 1.0:
                p, tan = plib.point_at(br.pts, min(s, 0.995))
                fr = env.frac(p)
                if fr < 9 and p.z > 0.25 and rng.random() < smooth(0.3, 0.8, fr) * 0.95 + 0.04:
                    out = outward(p)
                    d = (tan * 0.6 + out * 0.6 + Z * 0.2 + plib.rand_unit(rng) * 0.25).normalized()
                    tid = 2 if rng.random() < 0.07 and p.z > H * 0.55 else rng.choice([0, 0, 1, 1, 3])
                    tw.add(p, d, out * (0.4 + 0.8 * min(1.0, fr)) + Z * 0.7 + plib.rand_unit(rng) * 0.35, rng.uniform(0.85, 1.15), tid)
                s += 0.16 / max(br.length, 0.25) * rng.uniform(0.7, 1.25)
            p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
            tw.add(p, (tan + Z * 0.3).normalized(), outward(p) * 0.5 + Z, rng.uniform(0.9, 1.15),
                   2 if rng.random() < 0.12 and p.z > H * 0.6 else 0)
    return m, tw, env


# ---------------------------------------------------------------- живая изгородь

class HedgeEnv:
    """Брус стриженой изгороди: длина по X, ширина по Y, высота по Z; верх скруглён, торцы — по форме."""

    def __init__(self, L: float, W: float, Hh: float, round_ends: bool, sag: float, gap: tuple | None, seed: int) -> None:
        self.L, self.W, self.H = L, W, Hh
        self.round_ends, self.sag, self.gap = round_ends, sag, gap
        r = random.Random(seed)
        self.ph = [r.uniform(0, 6.28) for _ in range(4)]

    def top(self, x: float) -> float:
        # верх неровный: стригли не по шнуру, к одному концу просел
        return self.H * (1 - self.sag * (x / self.L + 0.5)) + 0.04 * math.sin(x * 1.7 + self.ph[0]) + 0.025 * math.sin(x * 4.1 + self.ph[1])

    def half_w(self, x: float, z: float) -> float:
        w = self.W * 0.5 * (1 + 0.05 * math.sin(x * 2.3 + self.ph[2]))
        # кверху брус чуть сужается (стригут трапецией), низ оголён
        w *= 1 - 0.12 * min(max(z / self.H, 0), 1)
        t = self.top(x)
        if z > t - 0.15:
            k = (z - (t - 0.15)) / 0.15
            w *= math.sqrt(max(0.0, 1 - k * k))
        return w

    def frac(self, p) -> float:
        hl = self.L * 0.5
        ex = abs(p.x) - hl
        if self.round_ends and ex > -self.W * 0.5:
            # скруглённый торец
            ex2 = ex + self.W * 0.5
            dy = math.hypot(ex2, p.y)
            w = self.half_w(math.copysign(hl - self.W * 0.5, p.x), p.z)
            fx = dy / max(w, 1e-3)
        else:
            fx = max(abs(p.x) / hl, abs(p.y) / max(self.half_w(p.x, p.z), 1e-3))
        t = self.top(p.x)
        fz = p.z / max(t, 1e-3) if p.z > 0 else 9.0
        if self.gap and self.gap[0] < p.x < self.gap[1]:
            fz = p.z / 0.45
        return max(fx, fz)

    def inside(self, p, tol: float = 1.0) -> bool:
        return self.frac(p) <= tol

    def normal(self, p) -> Vector:
        """Наружу от бруса в точке (для поворота веточек)."""
        t = self.top(p.x)
        hw = max(self.half_w(p.x, p.z), 1e-3)
        ny = p.y / hw
        nz = max(0.0, (p.z - (t - 0.25)) / 0.25)
        nx = 0.0
        hl = self.L * 0.5
        if abs(p.x) > hl - 0.3:
            nx = math.copysign((abs(p.x) - (hl - 0.3)) / 0.3, p.x)
        v = Vector((nx, ny, nz * 1.3))
        return v.normalized() if v.length > 1e-4 else Z.copy()


def build_hedge(pl: Plant) -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    L, W, Hh = P["L"], P["W"], P["Hh"]
    env = HedgeEnv(L, W, Hh, P.get("round_ends", False), P.get("sag", 0.0), P.get("gap"), pl.seed)
    stem_lv = Level(spacing=1, s0=0, s1=1, angle=(0, 0), length=lambda s, L_, r: 0.0, tropism=lambda t: 0.04, wiggle=0.08,
                    seg=0.12, env_tol=0.97)
    levels = [
        Level(spacing=0.07, s0=0.18, s1=0.98, angle=(30, 70), roll="spiral",
              length=lambda s, L_, r: r.uniform(0.15, 0.5), tropism=lambda t: 0.06, wiggle=0.15, seg=0.08,
              radius_k=0.7, tip=0.4, keep=0.85, env_tol=0.98),
        Level(spacing=0.07, s0=0.25, s1=0.95, angle=(35, 60), roll="spiral",
              length=lambda s, L_, r: r.uniform(0.05, 0.15), tropism=lambda t: 0.06, wiggle=0.15, seg=0.05,
              radius_k=0.7, tip=0.45, keep=0.7, env_tol=1.0),
    ]
    stems = []
    x = -L * 0.5 + 0.12
    row = 0
    while x < L * 0.5 - 0.1:
        gap = P.get("gap")
        if not (gap and gap[0] + 0.1 < x < gap[1] - 0.1):
            y = 0.12 * (1 if row % 2 else -1) * W / 0.85
            for k in range(rng.randint(2, 4)):
                o = plib.rand_unit(rng)
                base = Vector((x + rng.uniform(-0.05, 0.05), y + rng.uniform(-0.04, 0.04), -0.08))
                d = (Z * 2.5 + Vector((o.x, o.y * 1.6, 0))).normalized()
                pts = plib.grow(base, d, Hh * 1.2, stem_lv, rng, env)
                rc = rng.uniform(0.008, 0.016)
                n = len(pts)
                st = Branch(pts, [rc * (1 - 0.55 * i / max(n - 1, 1)) for i in range(n)], 0, plib.path_len(pts))
                plib.branch_children(st, levels, rng, env, 0, floor=0.15)
                plib.emit_branches(m, st, wood_mat(0.02))
                stems.append(st)
        elif rng.random() < 0.5:
            # пролом: сломанный сухой пенёк-куст
            base = Vector((x, rng.uniform(-0.1, 0.1), -0.05))
            pts = plib.grow(base, (Z * 2 + plib.rand_unit(rng)).normalized(), rng.uniform(0.25, 0.5), stem_lv, rng, None)
            if plib.LOD is None or plib.LOD.get("min_r", 0.0) <= 0.012:
                u, v = plib.bark_uv(0.012)
                m.tube("branch", pts, [0.012 * (1 - 0.5 * i / max(len(pts) - 1, 1)) for i in range(len(pts))],
                       plib.lod_sides(5), v_scale=v, u_reps=u, col_fn=plib.LOD.get("col") if plib.LOD else None)
            tw.add(pts[-1], (Z + plib.rand_unit(rng) * 0.6).normalized(), X, rng.uniform(0.8, 1.2), 4)
        x += rng.uniform(0.22, 0.32)
        row += 1
    # оболочка: точки у поверхности бруса (глубина до 0,2 м), веточки вдоль поверхности, листья лицом наружу;
    # стриженый куст ветвится у поверхности, внутри и внизу — голые стволики
    area = L * (2 * Hh + W)
    target = int(area * P.get("shell", 210))
    made = 0
    tries = 0
    gap = P.get("gap")
    while made < target and tries < target * 40:
        tries += 1
        p = Vector((rng.uniform(-L * 0.5, L * 0.5), rng.uniform(-W * 0.55, W * 0.55), rng.uniform(0.15, Hh + 0.05)))
        fr = env.frac(p)
        if not (0.8 < fr < 1.02):
            continue
        if p.z < 0.3 and rng.random() < 0.7:
            continue
        nrm = env.normal(p)
        tang = plib.rand_unit(rng)
        tang = (tang - nrm * tang.dot(nrm)).normalized()
        d = (tang + nrm * 0.4).normalized()
        dead = gap and gap[0] - 0.4 < p.x < gap[1] + 0.4 and rng.random() < 0.35
        tw.add(p, d, nrm + Z * 0.25, rng.uniform(0.8, 1.2), 4 if dead else rng.choice([0, 0, 1, 1, 3]))
        made += 1
    # отросшие побеги: сверху длинные, с боков короче
    per_m = P.get("overgrowth", 8)
    for k in range(int(per_m * L)):
        xx = rng.uniform(-L * 0.5 + 0.1, L * 0.5 - 0.1)
        if P.get("gap") and P["gap"][0] - 0.2 < xx < P["gap"][1] + 0.2:
            continue
        top = rng.random() < 0.65
        if top:
            yy = rng.uniform(-0.35, 0.35) * W
            p = Vector((xx, yy, env.top(xx) - 0.08))
            d = (Z * 1.4 + Vector((0, yy, 0)) * 2.5 + plib.rand_unit(rng) * 0.7).normalized()
            tw.add(p, d, Vector((0, yy, 0.3)) + plib.rand_unit(rng) * 0.4, rng.uniform(0.5, 0.95), 2)
        else:
            sgn = rng.choice([-1, 1])
            zz = rng.uniform(0.35, env.top(xx) - 0.15)
            p = Vector((xx, sgn * (env.half_w(xx, zz) - 0.05), zz))
            d = (Vector((0, sgn, 0)) * 1.5 + Z * 0.6 + plib.rand_unit(rng) * 0.4).normalized()
            tw.add(p, d, Vector((0, sgn * 0.6, 1)), rng.uniform(0.8, 1.15), 3)
    return m, tw, env


BUILDERS = {"birch": build_birch, "linden": build_linden, "poplar": build_poplar, "lilac": build_lilac, "hedge": build_hedge}
MODULES = {"birch": birch_modules, "linden": linden_modules, "poplar": poplar_modules, "lilac": lilac_modules,
           "hedge": hedge_modules}

# цвета для осмотра формы (не PBR): кора по породе — чтобы вид читался и в Solid
WOOD = {
    "birch": {"bark": (0.78, 0.77, 0.73), "branch": (0.22, 0.17, 0.15), "twig": (0.16, 0.12, 0.1)},
    "linden": {"bark": (0.24, 0.22, 0.2), "branch": (0.28, 0.24, 0.2), "twig": (0.3, 0.22, 0.15)},
    "poplar": {"bark": (0.33, 0.33, 0.31), "branch": (0.4, 0.39, 0.34), "twig": (0.42, 0.4, 0.3)},
    "lilac": {"bark": (0.36, 0.34, 0.31), "branch": (0.38, 0.35, 0.3), "twig": (0.35, 0.36, 0.25), "seed": (0.3, 0.22, 0.12)},
    "hedge": {"bark": (0.25, 0.2, 0.17), "branch": (0.27, 0.21, 0.17), "twig": (0.25, 0.2, 0.15)},
}
LEAF_RGB = {"birch": (0.2, 0.36, 0.08), "linden": (0.14, 0.3, 0.07), "poplar": (0.16, 0.3, 0.09),
            "lilac": (0.13, 0.27, 0.07), "hedge": (0.08, 0.2, 0.05)}
LABEL = {"birch": "Берёза", "linden": "Липа", "poplar": "Тополь", "lilac": "Сирень", "hedge": "Изгородь"}

# ---------------------------------------------------------------- экземпляры (по 2–3 на вид, разного роста и строения)

PLANTS = [
    Plant("birch_a", "берёза взрослая, 16 м", "birch", 16.0, 105,
          dict(H=16.0, r1=0.17, stems=1, lean=3.0, lean_az=0.6, wobble=0.1, flare=0.45, flare_h=0.7, lobes=5,
               crown_base=5.2, rmax=3.6, main_step=0.27)),
    Plant("birch_b", "берёза двуствольная, 14 м", "birch", 14.0, 209,
          dict(H=14.0, r1=0.13, stems=2, lean=9.0, lean_az=0.0, wobble=0.12, flare=0.4, flare_h=0.6, lobes=5,
               crown_base=4.2, rmax=3.4, main_step=0.38)),
    Plant("birch_c", "берёза молодая, 8 м", "birch", 8.0, 317,
          dict(H=8.0, r1=0.065, stems=1, lean=4.0, lean_az=2.0, wobble=0.07, flare=0.3, flare_h=0.35, lobes=4,
               crown_base=2.0, rmax=1.7, main_step=0.3)),
    Plant("linden_a", "липа взрослая, 15 м, поросль у комля", "linden", 15.0, 401,
          dict(H=15.0, r1=0.25, lean=2.0, lean_az=1.0, wobble=0.12, flare=0.55, flare_h=0.9, lobes=6, ovality=0.07,
               crown_base=3.3, rmax=4.7, roots=7, main_step=0.42, suckers=26, shift=0.4)),
    Plant("linden_b", "липа средняя, 11 м", "linden", 11.0, 503,
          dict(H=11.0, r1=0.16, lean=3.0, lean_az=3.0, wobble=0.1, flare=0.45, flare_h=0.7, lobes=5, ovality=0.06,
               crown_base=2.6, rmax=3.4, main_step=0.36, suckers=10, branch_k=0.8, twig_step=0.12)),
    Plant("linden_c", "липа молодая уличная, 6,5 м", "linden", 6.5, 607,
          dict(H=6.5, r1=0.075, lean=1.5, lean_az=4.0, wobble=0.05, flare=0.25, flare_h=0.3, lobes=4, ovality=0.04,
               crown_base=2.2, rmax=1.75, main_step=0.24, branch_k=0.6, twig_step=0.08)),
    Plant("poplar_a", "тополь берлинский взрослый, 21 м", "poplar", 21.0, 701,
          dict(H=21.0, r1=0.36, lean=2.0, lean_az=0.3, wobble=0.12, flare=0.6, flare_h=1.0, lobes=7, ovality=0.08,
               taper=0.9, crown_base=4.6, rmax=3.3, roots=8, main_step=0.4)),
    Plant("poplar_b", "тополь кронированный, 13 м", "poplar", 13.0, 809,
          dict(H=9.5, r1=0.38, lean=3.0, lean_az=2.2, wobble=0.14, flare=0.6, flare_h=1.0, lobes=7, ovality=0.09,
               taper=0.3, crown_base=7.0, rmax=3.2, roots=7, pollard=True, limbs=6, per_limb=(12, 18), regrow=4.4, epicormic=22)),
    Plant("lilac_a", "сирень старая, 3,2 м", "lilac", 3.2, 901,
          dict(H=3.2, W=3.6, stems=22, clump=0.36, stem_r=(0.018, 0.045), side_k=1.0, suckers=12)),
    Plant("lilac_b", "сирень средняя, 2,4 м", "lilac", 2.4, 1003,
          dict(H=2.5, W=2.7, stems=15, clump=0.26, stem_r=(0.015, 0.032), side_k=0.85, suckers=8, squash=0.85)),
    Plant("lilac_c", "сирень молодая, 1,7 м", "lilac", 1.7, 1105,
          dict(H=1.8, W=1.9, stems=10, clump=0.16, stem_r=(0.011, 0.022), side_k=0.65, suckers=5)),
    Plant("hedge_a", "изгородь 4,2 м, два лета без стрижки", "hedge", 1.05, 1201,
          dict(L=4.2, W=0.85, Hh=1.05, sag=0.05, overgrowth=8)),
    Plant("hedge_b", "изгородь 2,1 м, конец ряда, скруглённый торец", "hedge", 1.05, 1303,
          dict(L=2.1, W=0.85, Hh=1.0, round_ends=True, sag=0.0, overgrowth=11)),
    Plant("hedge_c", "изгородь 4,2 м с проломом", "hedge", 1.05, 1409,
          dict(L=4.2, W=0.85, Hh=1.05, sag=0.16, gap=(0.3, 1.2), overgrowth=7)),
]
