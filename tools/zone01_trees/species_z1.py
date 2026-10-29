"""Клёны и тополя зоны 1 («Пригород»): виды и экземпляры (форма, без PBR). Зона 1 — поздняя осень (берёза, газон, подлесок):
листва пожелтела и частью облетела. Генератор ветвления — общий с растениями «Проспекта» (tools/prospekt_plants/plib.py).

  maple    — клён остролистный (Acer platanoides): дворовое и лесное дерево средней полосы. Ветвление супротивное, ствол
             рано отдаёт толстые скелетные ветви — крона широкая, округлая; лист пальчато-лопастный, 5 лопастей с редкими
             длинными оттянутыми зубцами, на длинном черешке, лежит плоско «мозаикой»; гроздья крылаток (крылья почти в линию).
  negundo  — клён ясенелистный (Acer negundo): самосев у гаражей, оврагов, пустырей; 2–4 наклонных ствола из одного корня,
             ветви длинные, дугой; побеги сизо-зелёные; лист сложный из 3–5 листочков; у женских деревьев — висячие кисти
             крылаток (крылья под острым углом), держатся до зимы.
  poplar   — тополь берлинский (Populus × berolinensis), как на «Проспекте»: ветви круто вверх, лист яйцевидный с оттянутой
             вершиной, почки крупные, острые. Желтеет поздно и долго держит лист. В зоне 1 — без кронирования: ряд у дороги,
             у насыпи, в лесу.

Модуль веточки: локальная +X — ось побега от прикрепления, +Z — сторона, куда смотрят листья. Метры, 1:1.
Цвет вершин листа: r — оттенок, g — осенняя спелость (0 зелёный … 1 оранжевый / бурый); материал листа — по спелости.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "prospekt_plants"))
import plib  # noqa: E402
import species as PS  # noqa: E402
from plib import Z, Branch, Envelope, LeafShape, Level, Mesh, Twigs  # noqa: E402


def smooth(a: float, b: float, x: float) -> float:
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ лист клёна остролистного (пальчатый)

@dataclass
class Palmate:
    """Пальчатый лист в полярных координатах от места прикрепления черешка (0° — средняя жилка, + — вправо).
    lobes: (угол оси лопасти, град; длина, доли длины листа; полуширина, град; зубцы [(смещение, доли полуширины;
    высота над лопастью, доли её длины; полуширина зубца, град)]) — боковые лопасти зеркально."""
    lobes: list
    body: float = 0.78         # широкое «тело» лопасти (доля её длины), к концу — оттянутое остриё
    tip_w: float = 0.42        # ширина острия (доля полуширины лопасти)
    sinus: float = 0.38        # выемка между лопастями — округлая, на этой доле длины
    notch: float = 0.12        # сердцевидная выемка у черешка
    petiole: tuple = (0.7, 1.1)
    cup: float = 0.07          # края приподняты (лист «блюдцем»)
    droop: float = 0.05        # концы лопастей книзу


def _spike(d: float, w: float, k: float = 1.15) -> float:
    """Остриё: 1 на оси, почти прямыми краями сходит к 0 на w (оттянутый кончик без «иглы»)."""
    return max(0.0, 1.0 - (d / w) ** k) if d < w else 0.0


def palmate_radius(sh: Palmate, th: float) -> float:
    a = abs(th)
    r = sh.sinus * (1.0 - (1.0 - sh.notch / sh.sinus) * smooth(132.0, 180.0, a))
    for (ax, L, w, teeth) in sh.lobes:
        for sgn in ((1, -1) if ax else (1,)):
            d = abs(th - sgn * ax)
            if d < w:
                r = max(r, L * sh.body * (1.0 - (d / w) ** 2.6), L * _spike(d, w * sh.tip_w))
            for (off, h, tw_) in teeth:
                for s2 in (1, -1):
                    dd = abs(th - (sgn * ax + s2 * off * w))
                    if dd < tw_:
                        r = max(r, L * sh.body * (1.0 - off ** 2.6) + h * L * _spike(dd, tw_, 1.0))
    return r


def palmate_angles(sh: Palmate) -> list:
    """Углы контура: ровная сетка и точно — концы лопастей и зубцов (иначе острия срезаются)."""
    out = set(round(-179.0 + 3.0 * i, 3) for i in range(120))
    for (ax, L, w, teeth) in sh.lobes:
        for sgn in ((1, -1) if ax else (1,)):
            c = sgn * ax
            for k in (-1.5, -0.6, 0.0, 0.6, 1.5):
                out.add(round(c + k, 3))
            for (off, h, tw_) in teeth:
                for s2 in (1, -1):
                    t = c + s2 * off * w
                    for k in (-tw_ * 0.6, -tw_ * 0.25, 0.0, tw_ * 0.25, tw_ * 0.6):
                        out.add(round(t + k, 3))
    return sorted(a for a in out if -179.5 <= a <= 179.5)


# Режим листа клёна: "form" — сетка по контуру вида (форма на просмотр); "alpha" — для PBR и игры: сетка с запасом
# в рамке MAPLE_FRAME, край листа — альфа настоящего осеннего листа (tools/zone01_trees/leaf_textures.py, та же рамка).
LEAF_MODE = "form"
MAPLE_FRAME = (0.95, -0.42, 1.12)       # x ∈ [−0,95; 0,95], y ∈ [−0,42; 1,12] в долях длины листа


def alpha_radius(th: float) -> float:
    """Контур сетки под альфу: с запасом на все лопасти (выемки закрыты), обрезан рамкой."""
    a = abs(th)
    if a < 60.0:
        r = 1.15
    elif a < 100.0:
        r = 1.15 - 0.4 * (a - 60.0) / 40.0
    elif a < 125.0:
        r = 0.75 - 0.13 * (a - 100.0) / 25.0
    else:
        r = 0.62 - 0.32 * (a - 125.0) / 55.0
    xh, y0, y1 = MAPLE_FRAME
    t = math.radians(th)
    sx, cy = abs(math.sin(t)), math.cos(t)
    lim = min(xh * 0.985 / sx if sx > 1e-6 else 9.0, (y1 * 0.985 / cy) if cy > 1e-6 else (-y0 * 0.985 / -cy if cy < -1e-6 else 9.0))
    return min(r, lim)


def palmate_leaf(m: Mesh, rng: random.Random, attach: Vector, grow: Vector, normal: Vector, length: float, sh: Palmate,
                 mat: str, col: tuple, stalk_r: float = 0.0013) -> None:
    """Пальчатый лист на длинном черешке: веер от прикрепления, второе кольцо на полрадиуса (изгиб «блюдцем»)."""
    n = normal.normalized()
    y_ax = grow - n * grow.dot(n)
    if y_ax.length < 1e-6:
        y_ax = n.orthogonal()
    y_ax.normalize()
    x_ax = y_ax.cross(n).normalized()
    m.leaves += 1
    pet = length * rng.uniform(*sh.petiole)
    g = grow.normalized()
    mid = attach + g * pet * 0.55 + n * pet * 0.1
    base = attach + (g * 0.45 + y_ax * 0.55).normalized() * pet
    m.tube("twig", [attach, mid, base], [stalk_r, stalk_r * 0.85, stalk_r * 0.7], 3, cap=False, col=col)
    cup = sh.cup * rng.uniform(0.6, 1.4)
    droop = sh.droop * rng.uniform(0.5, 1.5)
    twist = rng.uniform(-0.06, 0.06)
    if LEAF_MODE == "alpha":
        angs = [-179.0 + 358.0 * i / 47 for i in range(48)]
        rad = [alpha_radius(a) for a in angs]
        span, y_lo, y_hi = MAPLE_FRAME
    else:
        angs = palmate_angles(sh)
        rad = [palmate_radius(sh, a) for a in angs]
        span = max(max(r * abs(math.sin(math.radians(a))) for a, r in zip(angs, rad)), 1e-3)
        y_lo = min(r * math.cos(math.radians(a)) for a, r in zip(angs, rad))
        y_hi = max(r * math.cos(math.radians(a)) for a, r in zip(angs, rad))
    cell = (m.leaves * 7 + 3) % 4
    cu, cv = 0.5 * (cell % 2), 0.5 * (cell // 2)

    def place(x: float, y: float) -> Vector:
        rr = math.hypot(x, y)
        z = cup * rr * rr - droop * max(0.0, y) ** 2 + twist * x * y
        return base + x_ax * (x * length) + y_ax * (y * length) + n * (z * length)

    def luv(x: float, y: float) -> tuple:
        return (cu + (0.5 + 0.5 * x / span) * 0.5, cv + ((y - y_lo) / max(y_hi - y_lo, 1e-3)) * 0.5)

    ring = []
    for a, r in zip(angs, rad):
        t = math.radians(a)
        ring.append((r * math.sin(t), r * math.cos(t)))
    inner = [(x * 0.5, y * 0.5) for x, y in ring]
    c0 = (0.0, 0.0)
    N = len(ring)
    # обход против часовой со стороны лица (+n): контур идёт по углу по часовой — вершины в обратном порядке
    for i in range(N - 1):
        j = i + 1
        m.poly(mat, [place(*c0), place(*inner[j]), place(*inner[i])], [luv(*c0), luv(*inner[j]), luv(*inner[i])], col)
        m.poly(mat, [place(*inner[i]), place(*inner[j]), place(*ring[j]), place(*ring[i])],
               [luv(*inner[i]), luv(*inner[j]), luv(*ring[j]), luv(*ring[i])], col)


PLATANOIDES = Palmate(lobes=[(0.0, 1.0, 34.0, [(0.62, 0.11, 7.5)]),
                             (54.0, 0.92, 31.0, [(0.6, 0.1, 7.5)]),
                             (113.0, 0.56, 28.0, [(0.62, 0.08, 8.0)])])


# ------------------------------------------------------------------ сложный лист клёна ясенелистного

# листочек: яйцевидный, оттянутый, с редкими крупными неровными зубцами (y растёт — полосы к жилке без перехлёста)
NEG_LEAFLET = LeafShape([(0.0, 0.0), (0.12, 0.04), (0.22, 0.12), (0.28, 0.22), (0.31, 0.31), (0.27, 0.35), (0.31, 0.43),
                         (0.26, 0.48), (0.27, 0.56), (0.21, 0.6), (0.2, 0.68), (0.14, 0.74), (0.11, 0.82), (0.05, 0.92),
                         (0.0, 1.0)], petiole=(0.05, 0.12), fold=0.05, curl=0.05)
# конечный листочек — чаще трёхлопастный
NEG_TERMINAL = LeafShape([(0.0, 0.0), (0.1, 0.03), (0.2, 0.1), (0.3, 0.2), (0.4, 0.3), (0.24, 0.38), (0.25, 0.46),
                          (0.21, 0.54), (0.22, 0.6), (0.15, 0.68), (0.12, 0.78), (0.06, 0.9), (0.0, 1.0)],
                         petiole=(0.12, 0.22), fold=0.05, curl=0.05)


def compound_leaf(m: Mesh, rng: random.Random, attach: Vector, grow: Vector, normal: Vector, size: float, mat: str,
                  col: tuple) -> None:
    """Непарноперистый лист: черешок-рахис, конечный листочек и 1–2 пары боковых в плоскости листа."""
    n = normal.normalized()
    g = grow - n * grow.dot(n) * 0.7
    g = g.normalized() if g.length > 1e-4 else n.orthogonal()
    side = g.cross(n).normalized()
    pairs = 2 if rng.random() < 0.55 else 1
    Lr = size * rng.uniform(0.38, 0.48)
    pts = [attach + g * (Lr * t) + n * (0.04 * Lr * math.sin(math.pi * t)) - n * (0.08 * Lr * t * t) for t in (0, 0.33, 0.66, 1.0)]
    m.tube("twig", pts, [0.0016, 0.0014, 0.0012, 0.001], 3, cap=False, col=col)
    tip, tan = pts[-1], (pts[-1] - pts[-2]).normalized()
    lt = size * rng.uniform(0.42, 0.5)
    plib.leaf(m, rng, tip, tan, n, lt, NEG_TERMINAL if rng.random() < 0.5 else NEG_LEAFLET, mat=mat, stalk_r=0.0009, col=col)
    m.leaves -= 1          # лист один, листочков несколько: счёт — по листьям
    for k in range(pairs):
        t = 0.97 if k == 0 else 0.45
        p, tg = plib.point_at(pts, t)
        for s in (1, -1):
            ang = math.radians(rng.uniform(48, 66))
            d = (tg * math.cos(ang) + side * s * math.sin(ang)).normalized()
            plib.leaf(m, rng, p, d, (n + plib.rand_unit(rng) * 0.12).normalized(), lt * rng.uniform(0.72, 0.86) * (1.0 if k == 0 else 0.9),
                      NEG_LEAFLET, mat=mat, stalk_r=0.0008, col=col)
            m.leaves -= 1
    m.leaves += 1


# ------------------------------------------------------------------ крылатки

WING = [(0.0, 0.0), (0.06, 0.42), (0.2, 0.55), (0.32, 0.45), (0.55, 0.6), (0.8, 0.68), (0.95, 0.52), (1.0, 0.26),
        (0.94, 0.02), (0.6, -0.06), (0.3, -0.14), (0.1, -0.22)]


def samara_wing(m: Mesh, at: Vector, wd: Vector, plane_n: Vector, length: float, width: float, col: tuple) -> None:
    """Крылатка: орешек у основания, крыло расширяется к концу; плоская, веером от середины."""
    across = plane_n.cross(wd).normalized()
    pts = [at + wd * (u * length) + across * (v * width) for u, v in WING]
    c = sum(pts, Vector()) / len(pts)
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        m.poly("seed", [c, pts[i], pts[j]], [(0.5, 0.5), (0.0, 0.0), (1.0, 0.0)], col)
    # орешек — вздутие у основания
    m.tube("seed", [at - wd * length * 0.02, at + wd * length * 0.22], [width * 0.32, width * 0.18], 4, col=col)


def samaras_platanoides(m: Mesh, rng: random.Random, at: Vector, tan: Vector, face: Vector) -> None:
    """Гроздь (щиток) 3–6 пар: крылья разведены почти в линию (150–180°), висит на ножке."""
    down = (-face * 0.85 + tan * 0.35 + plib.rand_unit(rng) * 0.2).normalized()
    L0 = rng.uniform(0.04, 0.07)
    hub = at + down * L0
    m.tube("twig", [at, at + down * L0 * 0.5 + tan * 0.006, hub], [0.0012, 0.001, 0.0009], 3, cap=False)
    col = (rng.random(), 1.0, 0.0, 1.0)
    for k in range(rng.randint(3, 6)):
        pd = (down + plib.rand_unit(rng) * 0.6).normalized()
        q = hub + pd * rng.uniform(0.02, 0.04)
        m.tube("twig", [hub, q], [0.0008, 0.0007], 3, cap=False)
        w = plib.rand_unit(rng)
        w = (w - pd * w.dot(pd)).normalized()
        half = math.radians(rng.uniform(75, 90))
        plane_n = pd.cross(w).normalized()
        for s in (1, -1):
            wd = (pd * math.cos(half) + w * s * math.sin(half)).normalized()
            samara_wing(m, q, wd, plane_n, rng.uniform(0.035, 0.05), rng.uniform(0.013, 0.017), col)


def samaras_negundo(m: Mesh, rng: random.Random, at: Vector, tan: Vector, face: Vector) -> None:
    """Висячая кисть 0,1–0,2 м: пары крылаток на ножках, крылья буквой V (50–70°) книзу."""
    d = (-face * 0.9 + tan * 0.25 + plib.rand_unit(rng) * 0.12).normalized()
    L = rng.uniform(0.1, 0.2)
    axis = [at + d * (L * t) + tan * (0.03 * L * math.sin(math.pi * t)) for t in (0, 0.25, 0.5, 0.75, 1.0)]
    m.tube("twig", axis, [0.0012, 0.0011, 0.001, 0.0009, 0.0008], 3, cap=False)
    col = (rng.random(), 1.0, 0.0, 1.0)
    s = 0.12
    k = 0
    while s < 1.0:
        p, tg = plib.point_at(axis, s)
        o = plib.rotate_about(tg.orthogonal(), tg, k * 2.4 + rng.uniform(-0.4, 0.4))
        pd = (tg * 0.6 + o * 0.8).normalized()
        q = p + pd * rng.uniform(0.012, 0.025)
        m.tube("twig", [p, q], [0.0007, 0.0006], 3, cap=False)
        down = (d * 0.85 + o * 0.3).normalized()
        w = o.cross(down).normalized()
        half = math.radians(rng.uniform(24, 36))
        plane_n = down.cross(w).normalized()
        for sg in (1, -1):
            wd = (down * math.cos(half) + w * sg * math.sin(half)).normalized()
            samara_wing(m, q, wd, plane_n, rng.uniform(0.026, 0.034), rng.uniform(0.008, 0.011), col)
        s += rng.uniform(0.06, 0.11)
        k += 1


def bud(m: Mesh, at: Vector, d: Vector, length: float, r: float) -> None:
    """Почка (на месте опавшего листа и на конце побега)."""
    m.tube("twig", [at, at + d * length * 0.55, at + d * length], [r, r * 0.95, r * 0.7], 4)


# ------------------------------------------------------------------ побег с листьями (модуль веточки), осень

LEAF_FN = {}


@dataclass
class Shoot:
    length: float
    leaf: str                         # maple | negundo | poplar
    leaf_len: tuple                   # длина листа (пальчатого — от черешка до конца средней лопасти; сложного — весь), м
    node: tuple = (0.05, 0.08)        # шаг узлов, м
    phyllo: str = "opp"               # opp — супротивно накрест, spiral — по спирали
    r0: float = 0.0035
    bend: float = 0.0
    curve_y: float = 0.0
    face_spread: float = 0.35
    face: Vector = field(default_factory=lambda: Z.copy())
    forward: float = 0.3
    flat_leaf: float = 0.0            # прижать направление листа к плоскости лица (мозаика клёна)
    side_shoots: int = 0
    side_angle: tuple = (40, 58)
    side_len: tuple = (0.35, 0.55)
    start: float = 0.1                # голый низ оси (старая древесина)
    leaf_grow: Callable = lambda t: 1.0
    terminal: int = 2
    retain: float = 1.0               # доля оставшихся листьев (осенью облетают)
    ripe: float = 0.5                 # средняя спелость листьев побега
    ripe_var: float = 0.25
    seeds: int = 0                    # гроздей / кистей крылаток на побеге
    seed_fn: str = ""
    bud: tuple = (0.006, 0.002)       # почка: длина, радиус


def leaf_mat(ripe: float) -> str:
    return "leaf_g" if ripe < 0.35 else "leaf_y" if ripe < 0.72 else "leaf_o"


def build_shoot(m: Mesh, rng: random.Random, sh: Shoot, origin: Vector = None, xdir: Vector = None, zdir: Vector = None,
                depth: int = 0) -> None:
    origin = origin if origin is not None else Vector((0, 0, 0))
    xdir = (xdir if xdir is not None else plib.X).normalized()
    zdir = zdir if zdir is not None else Z
    zdir = (zdir - xdir * zdir.dot(xdir)).normalized()
    ydir = zdir.cross(xdir).normalized()
    L = sh.length
    n = max(4, int(L / 0.03))
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(origin + xdir * (L * t) + ydir * (sh.curve_y * math.sin(math.pi * t)) + zdir * (-sh.bend * t * t))
    r_end = max(0.0009, sh.r0 * 0.35)
    m.tube("twig", pts, [sh.r0 + (r_end - sh.r0) * (i / n) for i in range(n + 1)], 4 if sh.r0 > 0.002 else 3)
    face = sh.face.normalized()
    face_w = (xdir * face.x + ydir * face.y + zdir * face.z).normalized()
    side_slots = sorted(rng.uniform(0.15, 0.65) for _ in range(sh.side_shoots))
    seed_slots = sorted(rng.uniform(0.45, 0.95) for _ in range(sh.seeds))
    s = sh.start * L + rng.uniform(0, sh.node[1])
    roll = rng.uniform(0, 6.28)
    side = 1

    def one_leaf(p: Vector, d: Vector, tan: Vector, size: float) -> None:
        # своя случайность на лист: облетел он или нет — побег от этого не меняется
        lr = random.Random(rng.getrandbits(32))
        dd = (d + tan * sh.forward + plib.rand_unit(lr) * 0.15)
        dd = dd - face_w * dd.dot(face_w) * sh.flat_leaf
        dd = dd.normalized() if dd.length > 0.2 else tan
        if lr.random() >= sh.retain:
            if sh.bud[0] > 0:
                bud(m, p + d * sh.r0 * 0.6, (d * 0.6 + tan * 0.8).normalized(), sh.bud[0], sh.bud[1])
            return
        rp = min(max(sh.ripe + lr.uniform(-sh.ripe_var, sh.ripe_var), 0.0), 1.0)
        nrm = (face_w + plib.rand_unit(lr) * sh.face_spread).normalized()
        LEAF_FN[sh.leaf](m, lr, p + d * sh.r0, dd, nrm, size, leaf_mat(rp), (lr.random(), rp, 0.0, 1.0))

    while s < L * 0.97:
        t = s / L
        p, tan = plib.point_at(pts, t)
        nrm_side = (zdir - tan * zdir.dot(tan)).normalized()
        lat = nrm_side.cross(tan).normalized()
        size = rng.uniform(*sh.leaf_len) * sh.leaf_grow(t)
        if side_slots and t >= side_slots[0]:
            side_slots.pop(0)
            ang = math.radians(rng.uniform(*sh.side_angle))
            sd = (tan * math.cos(ang) + lat * side * math.sin(ang)).normalized()
            sub = Shoot(**{**sh.__dict__, "length": L * (1 - t) * rng.uniform(*sh.side_len), "side_shoots": 0, "seeds": 0,
                           "r0": sh.r0 * 0.65, "start": 0.12})
            build_shoot(m, rng, sub, p, sd, zdir, depth + 1)
            side = -side
        if seed_slots and t >= seed_slots[0]:
            seed_slots.pop(0)
            SEED_FN[sh.seed_fn](m, rng, p, tan, face_w)
        if sh.phyllo == "opp":
            d0 = plib.rotate_about(lat, tan, roll)
            dirs = [d0, -d0]
            roll += math.pi / 2 + rng.uniform(-0.15, 0.15)
        else:
            dirs = [plib.rotate_about(lat, tan, roll)]
            roll += math.radians(144) + rng.uniform(-0.3, 0.3)
        for d in dirs:
            if size >= 0.005:
                one_leaf(p, d, tan, size)
        s += rng.uniform(*sh.node)
    tip, tan = pts[-1], (pts[-1] - pts[-2]).normalized()
    if sh.bud[0] > 0:
        bud(m, tip, tan, sh.bud[0] * 1.3, sh.bud[1] * 1.15)
    for k in range(sh.terminal if sh.leaf_len[1] > 0.005 else 0):
        d = (tan + plib.rand_unit(rng) * 0.5).normalized()
        one_leaf(tip, d, tan, rng.uniform(*sh.leaf_len) * sh.leaf_grow(1.0) * 0.85)


def module(fn: Callable[[Mesh, random.Random], None], seed: int) -> Mesh:
    m = Mesh()
    fn(m, random.Random(seed))
    return m


LEAF_FN.update({
    "maple": lambda m, r, p, d, n, s, mat, col: palmate_leaf(m, r, p, d, n, s, PLATANOIDES, mat, col),
    "negundo": compound_leaf,
    "poplar": lambda m, r, p, d, n, s, mat, col: plib.leaf(m, r, p, d, n, s, PS.LEAF["poplar"], mat=mat, col=col),
})
SEED_FN = {"platanoides": samaras_platanoides, "negundo": samaras_negundo}


# ------------------------------------------------------------------ модули по видам

def maple_modules() -> list:
    # ветка: голый низ старой древесины, по бокам короткие побеги; листья парами накрест, на длинных черешках, лицом вверх
    sp = dict(leaf="maple", leaf_len=(0.085, 0.125), node=(0.055, 0.085), phyllo="opp", r0=0.0045, bend=0.05,
              face_spread=0.3, forward=0.2, flat_leaf=0.75, start=0.42, terminal=2, side_angle=(42, 60),
              side_len=(0.4, 0.62), seed_fn="platanoides", bud=(0.006, 0.0024))
    return [
        ("01_ветка_густая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.5, side_shoots=3, retain=0.7, ripe=0.32, **sp)), 2011)),
        ("02_ветка_средняя", module(lambda m, r: build_shoot(m, r, Shoot(length=0.38, side_shoots=2, retain=0.5, ripe=0.58, **sp)), 2012)),
        ("03_ветка_с_крылатками", module(lambda m, r: build_shoot(m, r, Shoot(length=0.42, side_shoots=2, retain=0.42, ripe=0.7,
                                                                          seeds=2, **sp)), 2013)),
        ("04_ветка_редкая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.44, side_shoots=3, retain=0.2, ripe=0.86,
                                                                    seeds=1, **sp)), 2014)),
        ("05_ветка_голая", module(lambda m, r: build_shoot(m, r, Shoot(length=0.42, side_shoots=3, retain=0.0, ripe=0.9, **sp)), 2015)),
    ]


def negundo_modules() -> list:
    # побег сизо-зелёный, дугой книзу; сложные листья парами накрест
    sp = dict(leaf="negundo", leaf_len=(0.17, 0.24), node=(0.07, 0.11), phyllo="opp", r0=0.0045, bend=0.07,
              face_spread=0.4, forward=0.3, flat_leaf=0.6, start=0.22, terminal=1, side_angle=(35, 55),
              side_len=(0.35, 0.55), seed_fn="negundo", bud=(0.004, 0.002))
    return [
        ("01_побег_густой", module(lambda m, r: build_shoot(m, r, Shoot(length=0.55, side_shoots=2, retain=0.65, ripe=0.42, **sp)), 2311)),
        ("02_побег_редкий", module(lambda m, r: build_shoot(m, r, Shoot(length=0.46, side_shoots=2, retain=0.3, ripe=0.72, **sp)), 2312)),
        ("03_побег_с_кистями", module(lambda m, r: build_shoot(m, r, Shoot(length=0.38, side_shoots=1, retain=0.25, ripe=0.8,
                                                                       seeds=3, **sp)), 2313)),
        ("04_побег_голый_с_кистями", module(lambda m, r: build_shoot(m, r, Shoot(length=0.42, side_shoots=2, retain=0.0, ripe=0.9,
                                                                             seeds=2, **sp)), 2314)),
    ]


def poplar_modules() -> list:
    sp = dict(leaf="poplar", leaf_len=(0.07, 0.1), node=(0.05, 0.075), phyllo="spiral", r0=0.0035, bend=0.04,
              face_spread=0.6, forward=0.4, side_angle=(30, 45), side_len=(0.3, 0.5), terminal=1, bud=(0.016, 0.0032))
    return [
        ("01_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=0.6, side_shoots=2, retain=0.85, ripe=0.3, **sp)), 2411)),
        ("02_побег_короткий", module(lambda m, r: build_shoot(m, r, Shoot(length=0.32, retain=0.7, ripe=0.55, **sp)), 2412)),
        # пучок на укороченном побеге: листья с одной точки
        ("03_пучок", module(lambda m, r: build_shoot(m, r, Shoot(length=0.12, **{**sp, "node": (0.012, 0.02), "r0": 0.004,
                                                                             "face_spread": 0.7, "forward": 0.7, "start": 0.2,
                                                                             "terminal": 2, "leaf_len": (0.07, 0.095)},
                                                             retain=0.75, ripe=0.5)), 2413)),
        # жировой побег (волчок): прямой, листья крупные, зеленее — держатся дольше
        ("04_жировой_побег", module(lambda m, r: build_shoot(m, r, Shoot(length=1.1, **{**sp, "leaf_len": (0.1, 0.15),
                                                                                     "node": (0.06, 0.09), "r0": 0.006,
                                                                                     "bend": 0.03, "face_spread": 0.55,
                                                                                     "forward": 0.35, "start": 0.12,
                                                                                     "leaf_grow": lambda t: 0.75 + 0.35 * t},
                                                                     retain=0.85, ripe=0.18)), 2414)),
        ("05_побег_редкий", module(lambda m, r: build_shoot(m, r, Shoot(length=0.5, side_shoots=2, retain=0.35, ripe=0.82, **sp)), 2415)),
    ]


# ------------------------------------------------------------------ общее для экземпляров

def pick(rng: random.Random, score: float, table: list) -> int:
    """Модуль по месту в кроне: score 0 — внутри и внизу (гуще, зеленее), 1 — снаружи и наверху (облетело, спелее)."""
    w = [lo + (hi - lo) * score for _, lo, hi in table]
    x = rng.random() * sum(w)
    for (tid, _, _), wi in zip(table, w):
        x -= wi
        if x <= 0:
            return tid
    return table[-1][0]


def stubs(m: Mesh, rng: random.Random, tr: Branch, z0: float, z1: float, count: int, r_rng: tuple, H: float) -> None:
    """Сухие сучья и обломки на стволе ниже кроны (самоочищение): короткие, торец обломан."""
    for k in range(count):
        z = rng.uniform(z0, z1)
        s = (z + 0.35) / (H + 0.35)
        p, tan = plib.point_at(tr.pts, s)
        a = rng.uniform(0, 6.28)
        o = Vector((math.cos(a), math.sin(a), 0))
        rt = plib.radius_at(tr, s)
        d = (o + Z * rng.uniform(0.2, 0.9)).normalized()
        L = rng.uniform(0.12, 0.6)
        r = rng.uniform(*r_rng)
        start = p + o * rt * 0.7
        mid = start + d * L * 0.5 + plib.rand_unit(rng) * 0.02
        if plib.LOD is not None and r * 1.15 < plib.LOD.get("min_r", 0.0):
            continue
        m.tube("dead", [start, mid, start + d * L], [r * 1.15, r * 0.9, r * 0.75],
               plib.lod_sides(plib.sides_for(r) if r > 0.012 else 5), col_fn=plib.LOD.get("col") if plib.LOD else None)


def walk(root: Branch, dead: set) -> list:
    """Ветви с пометкой «сухая» (сама или родитель)."""
    out = []

    def rec(b: Branch, is_dead: bool) -> None:
        d = is_dead or id(b) in dead
        out.append((b, d))
        for c in b.children:
            rec(c, d)
    rec(root, False)
    return out


def emit_walk(m: Mesh, items: list, threshold: float, skip: Branch | None = None) -> None:
    for br, is_dead in items:
        if br is skip:
            continue
        r0 = br.radii[min(1, len(br.radii) - 1)]
        if plib.LOD is not None and r0 < plib.LOD.get("min_r", 0.0):
            continue
        pts, radii = plib.lod_path(br.pts, br.radii)
        u, v = plib.bark_uv(r0)
        mat = "dead" if is_dead else ("bark" if r0 > threshold else "branch")
        m.tube(mat, pts, radii, plib.lod_sides(plib.sides_for(r0)), v_scale=v, u_reps=u,
               col_fn=plib.LOD.get("col") if plib.LOD else None)


def mark_dead(rng: random.Random, branches: list, count: int, broken: bool) -> set:
    """Сухие ветви: без листвы, серые; broken — обломаны (укорочены, без мелочи)."""
    cand = [b for b in branches if b.level == 1 and len(b.pts) > 3]
    rng.shuffle(cand)
    out = set()
    for b in cand[:count]:
        out.add(id(b))
        if broken:
            orig = b.pts
            k = max(2, int(len(orig) * rng.uniform(0.35, 0.6)))
            b.pts, b.radii = orig[:k], b.radii[:k]
            b.length = plib.path_len(b.pts)
            near = lambda p: min(range(len(orig)), key=lambda i: (orig[i] - p).length)  # noqa: E731
            b.children = [c for c in b.children if near(c.pts[0]) < k - 1]
        for c in b.children:
            c.children = []
    return out


# ---------------------------------------------------------------- клён остролистный

MAPLE_TIDS = [(0, 0.7, 0.1), (1, 0.9, 0.5), (2, 0.4, 0.7), (3, 0.25, 0.9), (4, 0.08, 0.5)]


def build_maple(pl: "Plant") -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    env = Envelope(P["crown_base"] - 0.4, H + 0.3, P["rmax"],
                   PS.ovoid(P.get("env_tc", 0.48), P.get("env_floor", 0.62), P.get("env_top", 0.9), 0.85),
                   seed=pl.seed, lump=P.get("lump", 0.2), shift=Vector((P.get("shift", 0.0), 0, 0)))
    tr = PS.make_trunk(rng, P)
    PS.emit_trunk(m, rng, tr, P)
    Lsc = P["rmax"] * P.get("scaf_k", 1.3)
    top = P["scaf_top"]
    sub = [Level(spacing=0.42, s0=0.12, s1=0.97, angle=(35, 60), roll="opp",
                 length=lambda s, L, r: L * r.uniform(0.28, 0.48) * (1 - 0.45 * s), tropism=lambda t: 0.05 - 0.11 * t,
                 wiggle=0.1, seg=0.32, flat=0.15, radius_k=0.62, tip=0.3, keep=0.8, env_tol=1.06),
           Level(spacing=0.3, s0=0.2, s1=0.95, angle=(40, 62), roll="opp", length=lambda s, L, r: L * r.uniform(0.35, 0.55),
                 tropism=lambda t: 0.02, wiggle=0.12, seg=0.22, flat=0.3, radius_k=0.6, tip=0.35, keep=0.75, env_tol=1.08)]
    scaf = Level(spacing=P["scaf_step"], s0=P["crown_base"] / H, s1=top, angle=P.get("scaf_angle", (30, 52)), roll="opp",
                 length=lambda s, L, r: Lsc * r.uniform(0.6, 1.0), tropism=lambda t: 0.1 - 0.17 * t, wiggle=0.07, seg=0.5,
                 radius_k=0.85, tip=0.18, keep=0.8)
    upper = Level(spacing=P.get("upper_step", 0.55), s0=top, s1=0.96, angle=(35, 60), roll="opp",
                  length=lambda s, L, r: Lsc * r.uniform(0.35, 0.7) * (1 - 0.6 * max(0.0, s - top) / (1 - top)),
                  tropism=lambda t: 0.07 - 0.1 * t, wiggle=0.08, seg=0.45, radius_k=0.6, tip=0.22, keep=0.85)
    plib.branch_children(tr, [scaf] + sub, rng, env, 0)
    plib.branch_children(tr, [upper] + sub, rng, env, 0)
    items = walk(tr, mark_dead(rng, plib.all_branches(tr), P.get("dead", 0), True))
    emit_walk(m, items, 0.035, skip=tr)
    stubs(m, rng, tr, 1.2, P["crown_base"], P.get("stubs", 0), (0.012, 0.035), H)
    for br, is_dead in items[1:]:
        if is_dead or br.level < 2:
            continue
        s = 0.18
        while s < 1.0:
            p, tan = plib.point_at(br.pts, min(s, 0.995))
            fr = env.frac(p)
            if fr < 9 and rng.random() < smooth(0.3, 0.8, fr) * 0.9 + 0.1:
                rel = min(max((p.z - P["crown_base"]) / (H - P["crown_base"]), 0.0), 1.0)
                out = PS.outward(p, env.center(p.z))
                d = tan * 0.5 + out * 0.6 + plib.rand_unit(rng) * 0.35
                d = Vector((d.x, d.y, d.z * 0.5 - 0.1 * (1 - rel))).normalized()
                face = Z * (0.65 + 0.3 * rel) + out * (0.6 - 0.3 * rel) * min(1.0, fr) + plib.rand_unit(rng) * 0.3
                score = min(1.0, 0.45 * rel + 0.45 * min(fr, 1.0) + rng.uniform(-0.15, 0.25))
                tw.add(p, d, face, rng.uniform(0.85, 1.15), pick(rng, score, MAPLE_TIDS))
            s += P.get("twig_step", 0.15) / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
        p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
        tw.add(p, Vector((tan.x, tan.y, tan.z * 0.5)).normalized(), Z + PS.outward(p, env.center(p.z)) * 0.6,
               rng.uniform(0.9, 1.15), pick(rng, 0.8, MAPLE_TIDS))
    return m, tw, env


# ---------------------------------------------------------------- клён ясенелистный

NEGUNDO_TIDS = [(0, 1.0, 0.2), (1, 0.5, 0.9), (2, 0.25, 0.7), (3, 0.1, 0.6)]


def build_negundo(pl: "Plant") -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    env = Envelope(1.0, H + 0.3, P["rmax"], PS.ovoid(0.5, 0.5, 0.75, 0.7), seed=pl.seed, lump=0.3,
                   shift=Vector((P.get("shift", 0.0), 0, 0)), squash_y=P.get("squash", 1.0))
    # стволы от корня врозь и выгибаются к свету; неровные — самосев не формировали
    stem_lv = Level(spacing=1, s0=0, s1=1, angle=(0, 0), length=lambda s, L, r: 0.0, tropism=lambda t: 0.13 - 0.06 * t,
                    wiggle=0.11, seg=0.4)
    levels = [
        Level(spacing=0.7, s0=0.2, s1=0.95, angle=(35, 62), roll="opp",
              length=lambda s, L, r: r.uniform(1.8, 3.4) * (1 - 0.45 * s), tropism=lambda t: 0.09 - 0.22 * t, wiggle=0.09,
              seg=0.4, radius_k=0.65, tip=0.22, keep=0.72, env_tol=1.12),
        Level(spacing=0.36, s0=0.15, s1=0.96, angle=(35, 58), roll="opp",
              length=lambda s, L, r: L * r.uniform(0.3, 0.5) * (1 - 0.4 * s), tropism=lambda t: 0.02 - 0.12 * t, wiggle=0.12,
              seg=0.28, radius_k=0.6, tip=0.3, keep=0.75, env_tol=1.12),
        Level(spacing=0.28, s0=0.2, s1=0.95, angle=(40, 60), roll="opp", length=lambda s, L, r: L * r.uniform(0.35, 0.55),
              tropism=lambda t: -0.03, wiggle=0.14, seg=0.2, radius_k=0.6, tip=0.35, keep=0.7, env_tol=1.15),
    ]
    stems = []
    az0 = P.get("az0", rng.uniform(0, 6.28))
    for k, (L, rc, lean) in enumerate(P["stems"]):
        a = az0 + 2 * math.pi * k / len(P["stems"]) + rng.uniform(-0.35, 0.35)
        o = Vector((math.cos(a), math.sin(a), 0))
        lr = math.radians(lean)
        d = (Z * math.cos(lr) + o * math.sin(lr)).normalized()
        pts = plib.grow(Vector((0, 0, -0.3)) + o * 0.04, d, L, stem_lv, rng, None)
        n = len(pts)
        radii = [rc * (1.0 - 0.82 * max(0.0, p.z) / max(pts[-1].z, 1.0)) for p in pts]
        st = Branch(pts, radii, 0, plib.path_len(pts))
        PS.emit_trunk(m, rng, st, dict(P, flare=0.35, flare_h=0.5, lobes=4, roots=2 if k == 0 else 0, r1=rc))
        plib.branch_children(st, levels, rng, env, 0, floor=0.5)
        stems.append(st)
    # корневая шейка: общий низкий наплыв, из него расходятся стволы
    rc0 = max(s[1] for s in P["stems"]) * 1.7
    collar = Branch([Vector((0, 0, -0.3)), Vector((0, 0, 0.0)), Vector((0, 0, 0.25)), Vector((0, 0, 0.42))],
                    [rc0 * 1.1, rc0, rc0 * 0.7, rc0 * 0.35], 0, 0.72)
    PS.emit_trunk(m, rng, collar, dict(P, flare=0.5, flare_h=0.45, lobes=5, roots=0, r1=rc0))
    dead = set()
    for st in stems:
        dead |= mark_dead(rng, plib.all_branches(st), 1 if rng.random() < P.get("dead_p", 0.5) else 0, True)
    for st in stems:
        items = walk(st, dead)
        emit_walk(m, items, 0.03, skip=st)
        for br, is_dead in items[1:]:
            if is_dead or br.level < 2:
                continue
            s = 0.2
            while s < 1.0:
                p, tan = plib.point_at(br.pts, min(s, 0.995))
                fr = env.frac(p)
                if fr < 9 and rng.random() < smooth(0.25, 0.8, fr) * 0.85 + 0.15:
                    rel = min(max(p.z / H, 0.0), 1.0)
                    out = PS.outward(p, env.center(p.z))
                    d = tan * 0.6 + out * 0.4 + plib.rand_unit(rng) * 0.3
                    d = Vector((d.x, d.y, d.z * 0.6 - 0.15)).normalized()
                    face = Z * 0.6 + out * 0.6 + plib.rand_unit(rng) * 0.35
                    score = min(1.0, 0.4 * rel + 0.5 * min(fr, 1.0) + rng.uniform(-0.15, 0.25))
                    tw.add(p, d, face, rng.uniform(0.85, 1.15), pick(rng, score, NEGUNDO_TIDS))
                s += P.get("twig_step", 0.17) / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
            p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
            tw.add(p, Vector((tan.x, tan.y, tan.z * 0.4 - 0.2)).normalized(), Z + PS.outward(p) * 0.5,
                   rng.uniform(0.9, 1.15), pick(rng, 0.7, NEGUNDO_TIDS))
    # поросль у корня — свежие прямые побеги
    for k in range(P.get("suckers", 0)):
        a = rng.uniform(0, 6.28)
        o = Vector((math.cos(a), math.sin(a), 0))
        base = o * rng.uniform(0.15, 0.6) + Vector((0, 0, -0.05))
        tw.add(base, (Z * rng.uniform(1.5, 3.0) + o).normalized(), o, rng.uniform(0.9, 1.3), 0)
    return m, tw, env


# ---------------------------------------------------------------- тополь берлинский (зона 1, без кронирования)

POPLAR_TIDS = [(0, 1.0, 0.5), (1, 0.6, 0.8), (2, 0.6, 0.6), (4, 0.05, 0.5)]


def build_poplar(pl: "Plant") -> tuple:
    P = pl.params
    rng = random.Random(pl.seed)
    m = Mesh()
    tw = Twigs()
    H = P["H"]
    tr = PS.make_trunk(rng, P)
    PS.emit_trunk(m, rng, tr, P)
    prof = PS.pyramid(0.22, 0.6, 0.85) if P.get("shape", "narrow") == "narrow" else PS.ovoid(0.5, 0.62, 0.75, 0.8)
    env = Envelope(P["crown_base"] - 0.3, H + 0.4, P["rmax"], prof, seed=pl.seed, lump=P.get("lump", 0.18))
    Lmain = P["rmax"] * P.get("main_k", 2.6)
    sub = [Level(spacing=0.36, s0=0.15, s1=0.96, angle=(24, 42), roll="spiral",
                 length=lambda s, L, r: L * r.uniform(0.2, 0.38) * (1 - 0.4 * s), tropism=lambda t: 0.06, wiggle=0.09,
                 seg=0.32, radius_k=0.55, tip=0.3, env_tol=1.08),
           Level(spacing=0.3, s0=0.2, s1=0.95, angle=(28, 48), roll="spiral", length=lambda s, L, r: L * r.uniform(0.3, 0.5),
                 tropism=lambda t: 0.04, wiggle=0.12, seg=0.2, radius_k=0.6, tip=0.35, keep=0.85, env_tol=1.1)]
    main = Level(spacing=P["main_step"], s0=P["crown_base"] / H, s1=0.97, angle=P.get("main_angle", (20, 36)), roll="spiral",
                 length=lambda s, L, r: Lmain * r.uniform(0.55, 1.0) * (1 - P.get("main_fall", 0.0) * s), tropism=lambda t: 0.05,
                 wiggle=0.06, seg=0.6, radius_k=0.5, tip=0.22)
    if P.get("fork"):
        # старый тополь: на высоте fork ствол делится — 2–3 равных вершины круто вверх
        f0 = P["fork"] / H
        codom = Level(spacing=0.35, s0=f0, s1=f0 + 0.05, angle=(13, 24), roll="spiral",
                      length=lambda s, L, r: (H - P["fork"]) * r.uniform(0.82, 0.97), tropism=lambda t: 0.04, wiggle=0.05,
                      seg=0.6, radius_k=1.0, tip=0.12, keep=1.0, env_tol=1.12)
        cmain = Level(spacing=P["main_step"] * 1.1, s0=0.15, s1=0.97, angle=(24, 42), roll="spiral",
                      length=lambda s, L, r: Lmain * 0.8 * r.uniform(0.5, 1.0) * (1 - 0.5 * s), tropism=lambda t: 0.05,
                      wiggle=0.07, seg=0.55, radius_k=0.5, tip=0.22)
        plib.branch_children(tr, [codom, cmain] + sub, rng, env, 0)
        low = Level(spacing=P["main_step"], s0=P["crown_base"] / H, s1=f0, angle=(28, 46), roll="spiral",
                    length=lambda s, L, r: Lmain * 0.55 * r.uniform(0.5, 1.0), tropism=lambda t: 0.05, wiggle=0.07, seg=0.55,
                    radius_k=0.5, tip=0.22)
        up = Level(spacing=P["main_step"] * 1.3, s0=f0 + 0.08, s1=0.97, angle=(22, 38), roll="spiral",
                   length=lambda s, L, r: Lmain * 0.7 * r.uniform(0.5, 1.0) * (1 - 0.5 * s), tropism=lambda t: 0.05,
                   wiggle=0.06, seg=0.55, radius_k=0.5, tip=0.22)
        plib.branch_children(tr, [low] + sub, rng, env, 0)
        plib.branch_children(tr, [up] + sub, rng, env, 0)
    else:
        plib.branch_children(tr, [main] + sub, rng, env, 0)
    items = walk(tr, mark_dead(rng, plib.all_branches(tr), P.get("dead", 0), True))
    emit_walk(m, items, 0.04, skip=tr)
    stubs(m, rng, tr, 1.5, P["crown_base"] + 0.5, P.get("stubs", 0), (0.015, 0.05), H)
    for br, is_dead in items[1:]:
        if is_dead or br.level < 2:
            continue
        s = 0.2
        while s < 1.0:
            p, tan = plib.point_at(br.pts, min(s, 0.995))
            fr = env.frac(p)
            if fr < 9 and rng.random() < smooth(0.3, 0.8, fr) * 0.85 + 0.15:
                rel = min(max((p.z - P["crown_base"]) / (H - P["crown_base"]), 0.0), 1.0)
                out = PS.outward(p)
                d = (tan + Z * 0.4 + plib.rand_unit(rng) * 0.3).normalized()
                score = min(1.0, 0.5 * rel + 0.4 * min(fr, 1.0) + rng.uniform(-0.2, 0.2))
                tw.add(p, d, out + Z * 0.5 + plib.rand_unit(rng) * 0.4, rng.uniform(0.85, 1.15), pick(rng, score, POPLAR_TIDS))
            s += P.get("twig_step", 0.18) / max(br.length, 0.3) * rng.uniform(0.7, 1.25)
        p, tan = br.pts[-1], (br.pts[-1] - br.pts[-2]).normalized()
        tw.add(p, (tan + Z * 0.5).normalized(), PS.outward(p) + Z, rng.uniform(0.9, 1.15), pick(rng, 0.6, POPLAR_TIDS))
    # волчки (жировые побеги) по стволу — тополь ими обрастает
    for k in range(P.get("epicormic", 0)):
        z = rng.uniform(1.8, P["crown_base"] + 1.0)
        s = (z + 0.35) / (H + 0.35)
        p, tan = plib.point_at(tr.pts, s)
        a = rng.uniform(0, 6.28)
        o = Vector((math.cos(a), math.sin(a), 0))
        tw.add(p + o * plib.radius_at(tr, s) * 0.9, (Z * rng.uniform(1.2, 2.5) + o).normalized(), o, rng.uniform(0.7, 1.2), 3)
    return m, tw, env


# ------------------------------------------------------------------ экземпляр

@dataclass
class Plant:
    key: str           # имя в игре (ключ зоны 1)
    label: str         # по-русски
    kind: str          # maple | negundo | poplar
    height: float
    seed: int
    params: dict


BUILDERS = {"maple": build_maple, "negundo": build_negundo, "poplar": build_poplar}
MODULES = {"maple": maple_modules, "negundo": negundo_modules, "poplar": poplar_modules}

# цвета для осмотра формы (не PBR): кора по виду; листья — три тона осени (зелёный / жёлтый / оранжевый или бурый)
WOOD = {
    "maple": {"bark": (0.26, 0.24, 0.22), "branch": (0.3, 0.28, 0.25), "twig": (0.36, 0.27, 0.2), "seed": (0.58, 0.44, 0.25),
              "dead": (0.46, 0.44, 0.41)},
    "negundo": {"bark": (0.4, 0.38, 0.34), "branch": (0.41, 0.41, 0.35), "twig": (0.36, 0.44, 0.32), "seed": (0.52, 0.4, 0.24),
                "dead": (0.5, 0.48, 0.44)},
    "poplar": {"bark": (0.33, 0.33, 0.31), "branch": (0.4, 0.39, 0.34), "twig": (0.42, 0.4, 0.3), "seed": (0.5, 0.4, 0.25),
               "dead": (0.47, 0.46, 0.43)},
}
LEAF_RGB = {
    "maple": {"leaf_g": (0.2, 0.31, 0.06), "leaf_y": (0.7, 0.53, 0.05), "leaf_o": (0.68, 0.27, 0.04)},
    "negundo": {"leaf_g": (0.25, 0.33, 0.07), "leaf_y": (0.64, 0.56, 0.12), "leaf_o": (0.46, 0.34, 0.1)},
    "poplar": {"leaf_g": (0.17, 0.29, 0.07), "leaf_y": (0.56, 0.5, 0.1), "leaf_o": (0.43, 0.31, 0.1)},
}
LABEL = {"maple": "Клён_остролистный", "negundo": "Клён_ясенелистный", "poplar": "Тополь"}

# ---------------------------------------------------------------- экземпляры зоны 1 (ключи — как у прежних деревьев карты)

PLANTS = [
    Plant("tree_maple_0", "клён остролистный взрослый, дворовый, 16 м", "maple", 16.0, 2101,
          dict(H=16.0, r1=0.23, lean=2.5, lean_az=0.8, wobble=0.15, flare=0.65, flare_h=0.9, lobes=6, ovality=0.06, taper=1.4,
               roots=0, crown_base=2.6, rmax=6.0, scaf_step=0.95, scaf_top=0.5, twig_step=0.15, stubs=2, dead=1)),
    Plant("tree_maple_1", "клён остролистный лесной, 13 м", "maple", 13.0, 2203,
          dict(H=13.0, r1=0.13, lean=4.0, lean_az=2.4, wobble=0.12, flare=0.35, flare_h=0.5, lobes=4, ovality=0.05, taper=1.15,
               roots=0, crown_base=4.4, rmax=3.8, scaf_step=1.1, scaf_top=0.62, scaf_k=1.2, env_tc=0.55, env_floor=0.5,
               upper_step=0.5, twig_step=0.15, stubs=6, dead=1)),
    Plant("tree_maple_2", "клён ясенелистный, самосев, три ствола, 9 м", "negundo", 9.0, 2307,
          dict(H=9.0, stems=[(9.8, 0.13, 16.0), (8.4, 0.11, 27.0), (6.6, 0.08, 38.0)], rmax=4.8, squash=0.8, shift=0.8,
               az0=0.3, dead_p=0.6, suckers=7, twig_step=0.17, flare=0.35, flare_h=0.5, lobes=4, ovality=0.08)),
    Plant("tree_poplar_0", "тополь берлинский взрослый, 24 м", "poplar", 24.0, 2401,
          dict(H=24.0, r1=0.37, lean=1.5, lean_az=0.4, wobble=0.12, flare=0.6, flare_h=1.0, lobes=7, ovality=0.08, taper=0.9,
               crown_base=6.0, rmax=3.6, roots=8, main_step=0.4, stubs=9, dead=1)),
    Plant("tree_poplar_1", "тополь берлинский старый, раздвоенный, 21 м", "poplar", 21.0, 2503,
          dict(H=21.0, r1=0.45, lean=3.0, lean_az=2.0, wobble=0.14, flare=0.7, flare_h=1.1, lobes=8, ovality=0.1, taper=1.1,
               crown_base=5.0, fork=6.5, shape="broad", rmax=5.4, main_k=1.6, lump=0.25, roots=8, main_step=0.45, stubs=6,
               epicormic=12, dead=2)),
    Plant("tree_poplar_2", "тополь берлинский молодой, 14 м", "poplar", 14.0, 2607,
          dict(H=14.0, r1=0.16, lean=2.0, lean_az=4.1, wobble=0.08, flare=0.35, flare_h=0.5, lobes=5, ovality=0.05, taper=0.95,
               crown_base=3.2, rmax=2.3, roots=0, main_step=0.34, stubs=3)),
]
