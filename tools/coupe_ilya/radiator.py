"""Купе Ильи: предмет заказа car_radiator — снятый радиатор с двумя патрубками на хомутах и биркой «ЮР / 8».

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/radiator.py -- <выход.blend>
    ... --python tools/coupe_ilya/radiator.py -- fit <машина.blend> <радиатор.blend> <проверка.blend>

Радиатор встаёт в рамку моторного отсека (engine_bay.radiator_frame): шипы снизу — в резиновые опоры
(±0,42; −2,02; низ 0,318–0,348), шипы кронштейнов сверху — в верхние держатели (низ 0,7255).
Горловины — там, где к машине подходят патрубки (engine_bay.hanging_hoses): верхняя — на левом
бачке (+X), нижняя — на правом (−X), обе назад, к двигателю. Патрубки 42 и 46 мм — короткие
отрезки, снятые вместе с радиатором: на горловине хомут, на свободном конце — второй.

Геометрия считается в осях машины (левый борт +X, перёд −Y) и сдвигается так, что начало
координат предмета — под нижними шипами по центру (CAR_POS — где он стоит в машине).
Режим fit кладёт предмет в копию машины (капот открыт) и ищет пересечения с отсеком.
Только numpy; бирка и надпись — разбиение mathutils и шрифт Blender, переведённый в сетку.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import parts as pt  # noqa: E402
from wheel import revolve  # noqa: E402

# --- Размеры (м, оси машины) ---------------------------------------------------------------------
Y_C = -2.020                  # средняя плоскость сердцевины = плоскость опор рамки
CORE_X = 0.400                # сердцевина между коллекторными пластинами
CORE_Z0, CORE_Z1 = 0.372, 0.703
CORE_D = 0.027                # толщина сердцевины (по ходу воздуха)
N_ROWS = 35                   # рядов ламелей; трубок на одну больше, шаг ~9,5 мм
TUBE_T = 0.0018               # плоская трубка 27 × 1,8 мм
FIN_HALF = 0.0017             # половина волны ламели (~15 рёбер на дюйм)
TANK_X0, TANK_X1 = 0.405, 0.478
TANK_YC, TANK_D = -2.020, 0.044    # задняя стенка −1,998: за ней вплотную корпус фильтра машины (−1,99)
TANK_Z0, TANK_Z1 = 0.358, 0.716
MOUNT_X = 0.42                # шипы — в опоры рамки (engine_bay: ±0,42)
NECK_UP = (0.4415, 0.540, 0.033)     # x, z, наружный диаметр горловины (= внутренний патрубка);
                                     # верхняя — под корпусом фильтра машины (низ 0,575)
NECK_LO = (-0.4415, 0.405, 0.037)
HOSE_UP_OD, HOSE_LO_OD, HOSE_WALL = 0.042, 0.046, 0.0045
CAR_POS = np.array([0.0, Y_C, 0.333])
TAG_W, TAG_H, TAG_T = 0.070, 0.120, 0.0006     # картонная бирка 70 × 120 мм
TAG_HOLE = 0.012              # от верхнего края до центра отверстия


# --- Общие построители ---------------------------------------------------------------------------

def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def basis(d) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Правая тройка (d, e1, e2): d — направление, e1, e2 — поперёк."""
    d = _unit(d)
    a = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0, 0])
    e1 = _unit(np.cross(a, d))
    return d, e1, np.cross(d, e1)


def revolve_on(profile, base, direction, seg: int = 48, closed: bool = False, phase: float = 0.0):
    """Тело вращения (профиль: расстояние вдоль оси, радиус) с осью direction от точки base."""
    V, F = revolve(profile, seg, closed, phase)
    d, e1, e2 = basis(direction)
    return np.asarray(base, float) + V[:, :1] * d + V[:, 1:2] * e1 + V[:, 2:3] * e2, F


def rbox(c, size, r_side: float, r_cap: float, axes=((1, 0, 0), (0, 1, 0), (0, 0, 1)), n_side: int = 4,
         n_cap: int = 3):
    """Скруглённый брусок: сечение size[0]×size[1] по осям axes[0], axes[1] (радиус углов r_side) вытянуто
    вдоль axes[2] на size[2]; рёбра торцов скруглены радиусом r_cap (сечение сужается по дуге наружу)."""
    u, v, w = (np.asarray(a, float) for a in axes)
    sx, sy, sz = size
    r_cap = min(r_cap, sx * 0.49, sy * 0.49, sz * 0.49)
    r_side = min(max(r_side, r_cap), sx * 0.4999, sy * 0.4999)
    zs, ins = [], []
    for k in range(n_cap + 1):                       # низ: от торца к полному сечению
        b = math.pi / 2 * k / n_cap
        zs.append(-sz / 2 + r_cap - r_cap * math.cos(b))
        ins.append(r_cap * (1 - math.sin(b)))
    for k in range(n_cap + 1):                       # верх: от полного сечения к торцу
        a = math.pi / 2 * k / n_cap
        zs.append(sz / 2 - r_cap + r_cap * math.sin(a))
        ins.append(r_cap * (1 - math.cos(a)))
    path = np.asarray(c, float) + np.outer(zs, w)

    def sec(i):
        d = ins[i]
        return pt.rounded_rect(sx - 2 * d, sy - 2 * d, max(r_side - d, 1e-5), n_side)
    return pt.loft(path, np.broadcast_to(u, path.shape), np.broadcast_to(v, path.shape), sec, cap=True)


def rmf(path: np.ndarray, n0=None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Рамки без закрутки вдоль кривой (двойное отражение): T, N, B — правая тройка."""
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    N = np.zeros_like(path)
    seed = np.array([0, 0, 1.0]) if n0 is None else np.asarray(n0, float)
    if abs(seed @ T[0]) > 0.95:
        seed = np.array([1.0, 0, 0])
    N[0] = _unit(seed - T[0] * (seed @ T[0]))
    for i in range(len(path) - 1):
        v1 = path[i + 1] - path[i]
        c1 = v1 @ v1
        if c1 < 1e-18:
            N[i + 1] = N[i]
            continue
        nL = N[i] - 2 / c1 * (v1 @ N[i]) * v1
        tL = T[i] - 2 / c1 * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        N[i + 1] = nL - (2 / c2 * (v2 @ nL) * v2 if c2 > 1e-18 else 0)
        N[i + 1] = _unit(N[i + 1] - T[i + 1] * (N[i + 1] @ T[i + 1]))
    return T, N, np.cross(T, N)


def sweep(path, radius: float, n_sec: int = 12, cap: bool = True, n0=None):
    """Проволока / стержень круглого сечения вдоль кривой."""
    path = np.asarray(path, float)
    _, N, B = rmf(path, n0)
    a = np.linspace(0, 2 * math.pi, n_sec, endpoint=False)
    return pt.loft(path, N, B, np.c_[np.cos(a), np.sin(a)] * radius, cap=cap)


def resample(P: np.ndarray, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Ломаная → точки через равный шаг; возвращает точки и длину дуги каждой."""
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(int(math.ceil(s[-1] / step)), 2)
    ss = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(ss, s, P[:, k]) for k in range(3)], 1), ss


def bent_path(p0, d0, l0: float, d1, R: float, l1: float, step: float = 0.002) -> np.ndarray:
    """Прямой участок l0 по d0, дуга радиуса R до направления d1, прямой участок l1 (формованный шланг)."""
    p0, d0, d1 = np.asarray(p0, float), _unit(d0), _unit(d1)
    n = _unit(d1 - d0 * (d0 @ d1))
    th = math.acos(np.clip(d0 @ d1, -1, 1))
    pts = [p0 + d0 * t for t in np.linspace(0, l0, 20)]
    p1 = pts[-1]
    for f in np.linspace(0, th, 40)[1:]:
        pts.append(p1 + R * math.sin(f) * d0 + R * (1 - math.cos(f)) * n)
    p2 = pts[-1]
    pts += [p2 + d1 * t for t in np.linspace(0, l1, 30)[1:]]
    return resample(np.array(pts), step)[0]


def smooth_closed(P: np.ndarray, it: int = 3, lam: float = 0.5) -> np.ndarray:
    for _ in range(it):
        P = P + lam * ((np.roll(P, 1, 0) + np.roll(P, -1, 0)) / 2 - P)
    return P


def fillet_poly(pts: np.ndarray, r: float, n: int = 4) -> np.ndarray:
    """Многоугольник со скруглёнными углами (радиус r)."""
    out = []
    k = len(pts)
    for i in range(k):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % k]
        d1, d2 = (a - b) / np.linalg.norm(a - b), (c - b) / np.linalg.norm(c - b)
        ang = math.acos(np.clip(d1 @ d2, -1, 1))
        cen = b + (d1 + d2) / np.linalg.norm(d1 + d2) * r / math.sin(ang / 2)
        t = r / math.tan(ang / 2)
        p1, p2 = b + d1 * t, b + d2 * t
        a1 = math.atan2(*(p1 - cen)[::-1])
        a2 = math.atan2(*(p2 - cen)[::-1])
        da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        for s in np.linspace(0, 1, n + 1):
            out.append(cen + r * np.array([math.cos(a1 + da * s), math.sin(a1 + da * s)]))
    return np.array(out)


def flat_plate(outer: np.ndarray, holes: list[np.ndarray], thick: float, origin, u, v, n):
    """Плоская пластина (бирка) с отверстиями: лицо и оборот — разбиение mathutils, кромки по контурам."""
    loops = [outer] + list(holes)
    fv, ff = pt.poly_mesh(outer, holes)
    inp = np.vstack(loops)
    # разбиение кладёт исходные точки первыми; если нет — найти их по положению
    if not np.allclose(fv[:len(inp)], inp, atol=1e-9):
        idx = [int(np.argmin(np.linalg.norm(fv - p, axis=1))) for p in inp]
    else:
        idx = list(range(len(inp)))
    m = len(fv)
    o, u, v, n = (np.asarray(a, float) for a in (origin, u, v, n))

    def place(p2, h):
        return o + p2[:, :1] * u + p2[:, 1:2] * v + h * n
    V = np.vstack([place(fv, thick / 2), place(fv, -thick / 2)])
    F = [tuple(t) for t in ff] + [tuple(m + i for i in t[::-1]) for t in ff]
    base = 0
    for L in loops:
        k = len(L)
        for j in range(k):
            a, b = idx[base + j], idx[base + (j + 1) % k]
            F.append((a, b, m + b, m + a))
        base += k
    return V, F


# --- Сердцевина: плоские трубки, гофрированные ламели, боковые пластины, коллекторы -----------

def core_rows() -> tuple[list[float], float]:
    p = (CORE_Z1 - CORE_Z0) / N_ROWS
    return [CORE_Z0 + p * k for k in range(N_ROWS + 1)], p


def core_tubes():
    """Плоские трубки поперёк (радиатор с боковыми бачками): концы уходят в коллекторы."""
    zs, _ = core_rows()
    sec = pt.rounded_rect(CORE_D, TUBE_T, TUBE_T * 0.49, 3)
    out = []
    for z in zs:
        path = np.array([[-CORE_X - 0.002, Y_C, z], [CORE_X + 0.002, Y_C, z]])
        out.append(pt.loft(path, np.broadcast_to([0, 1.0, 0], (2, 3)), np.broadcast_to([0, 0, 1.0], (2, 3)), sec))
    return pt.merge(out)


def core_fins():
    """Ламели: гофрированная лента между соседними трубками, гребни скруглены и касаются трубок.
    Лента — тонкий лист (одна поверхность, как настоящая фольга 0,08 мм)."""
    zs, p = core_rows()
    n_half = int(round(2 * CORE_X / FIN_HALF))
    s = np.arange(n_half * 4 + 1) / 4.0
    x = -CORE_X + s * (2 * CORE_X / n_half)
    wave = np.clip(1.25 * np.cos(np.pi * s), -1, 1)
    amp = (p - TUBE_T) / 2 + 0.0001
    yf, yb = Y_C - CORE_D / 2 + 0.0004, Y_C + CORE_D / 2 - 0.0004
    m = len(x)
    F = [(i, i + 1, m + i + 1, m + i) for i in range(m - 1)]
    out = []
    for k in range(N_ROWS):
        z = (zs[k] + zs[k + 1]) / 2 + amp * wave
        out.append((np.vstack([np.c_[x, np.full(m, yf), z], np.c_[x, np.full(m, yb), z]]), F))
    return pt.merge(out)


def core_frame():
    """Боковые пластины сверху и снизу сердцевины (с выштамповкой) и коллекторные пластины с лапками обжима."""
    parts = []
    for sgn, z_edge in ((-1, CORE_Z0), (1, CORE_Z1)):
        zc = z_edge + sgn * 0.0050
        parts.append(rbox((0, Y_C, zc), (2 * CORE_X + 0.004, CORE_D + 0.002, 0.0078), 0.003, 0.0025))
        parts.append(rbox((0, Y_C, zc + sgn * 0.0040), (2 * CORE_X - 0.03, 0.008, 0.003), 0.0015, 0.0012))
    zc = (TANK_Z0 + TANK_Z1) / 2
    hy, hz = TANK_D + 0.008, TANK_Z1 - TANK_Z0 + 0.008
    YZX = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    for s in (1, -1):
        parts.append(rbox((s * (CORE_X + 0.0015), TANK_YC, zc), (hy, hz, 0.003), 0.010, 0.0012, axes=YZX))
        # лапки обжима: загнуты с коллектора на фланец бачка
        for z in np.arange(TANK_Z0 + 0.010, TANK_Z1 - 0.006, 0.012):
            for sy in (1, -1):
                parts.append(rbox((s * (CORE_X + 0.0045), TANK_YC + sy * (hy / 2 - 0.0012), z),
                                  (0.0025, 0.007, 0.007), 0.0011, 0.0009, axes=YZX, n_side=2, n_cap=2))
        for y in (-0.018, -0.006, 0.006, 0.018):
            for sz in (1, -1):
                parts.append(rbox((s * (CORE_X + 0.0045), TANK_YC + y, zc + sz * (hz / 2 - 0.0012)),
                                  (0.007, 0.0025, 0.007), 0.0011, 0.0009, axes=YZX, n_side=2, n_cap=2))
    return pt.merge(parts)


# --- Бачки: корпус, фланец, рёбра, опоры, горловины ----------------------------------------------

def neck(x: float, z: float, od: float):
    """Горловина патрубка назад (+Y): бобышка на бачке, трубка с буртиком, полая — видна стенка."""
    r = od / 2
    prof = [(0.0, 0.0), (0.0, r + 0.0045), (0.008, r + 0.0045), (0.0105, r + 0.0025), (0.013, r), (0.032, r),
            (0.0335, r + 0.0018), (0.0375, r + 0.0018), (0.0395, r), (0.046, r), (0.0475, r - 0.0012),
            (0.0475, r - 0.0032), (0.046, r - 0.0037), (0.012, r - 0.0037), (0.012, 0.0)]
    return revolve_on(prof, (x, TANK_YC + TANK_D / 2 - 0.004, z), (0, 1, 0), 48)


def tank(s: int):
    """Пластиковый бачок одной стороны (s = +1 — левый, с верхней горловиной; −1 — правый, с нижней)."""
    zc = (TANK_Z0 + TANK_Z1) / 2
    xc = s * (TANK_X0 + TANK_X1) / 2
    YZX = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
    parts = [
        rbox((xc, TANK_YC, zc), (TANK_X1 - TANK_X0, TANK_D, TANK_Z1 - TANK_Z0), 0.015, 0.013),
        rbox((s * (CORE_X + 0.0065), TANK_YC, zc), (TANK_D + 0.004, TANK_Z1 - TANK_Z0 + 0.004, 0.007), 0.012, 0.0015,
             axes=YZX),
        # продольное ребро по наружной стенке
        rbox((s * (TANK_X1 + 0.0005), TANK_YC, zc), (0.006, 0.012, TANK_Z1 - TANK_Z0 - 0.05), 0.0029, 0.0028),
    ]
    neck_z = NECK_UP[1] if s > 0 else NECK_LO[1]
    busy = [neck_z] + ([] if s > 0 else [0.392, 0.693])
    for z in np.arange(0.400, 0.700, 0.058):
        if min(abs(z - b) for b in busy) > 0.036:
            parts.append(rbox((s * 0.447, TANK_YC, z), (0.070, TANK_D + 0.005, 0.004), 0.016, 0.0015))
    # шип снизу (в резиновую опору рамки) и кронштейн с шипом сверху (в верхний держатель)
    pin = [(0.0, 0.0), (0.0, 0.0085), (0.003, 0.0085), (0.0045, 0.0065), (0.019, 0.0065), (0.0215, 0.0050),
           (0.0228, 0.0025), (0.023, 0.0)]
    parts.append(rbox((s * 0.428, Y_C, TANK_Z0 + 0.003), (0.030, 0.028, 0.012), 0.006, 0.004))
    parts.append(revolve_on(pin, (s * MOUNT_X, Y_C, TANK_Z0 - 0.002), (0, 0, -1), 32))
    parts.append(rbox((s * 0.428, Y_C, TANK_Z1 - 0.001), (0.030, 0.026, 0.014), 0.006, 0.004))
    top_pin = [(0.0, 0.0), (0.0, 0.0075), (0.003, 0.0075), (0.0045, 0.0055), (0.016, 0.0055), (0.0185, 0.0042),
               (0.0198, 0.0020), (0.020, 0.0)]
    parts.append(revolve_on(top_pin, (s * MOUNT_X, Y_C, TANK_Z1 + 0.005), (0, 0, 1), 32))
    if s > 0:
        parts.append(neck(NECK_UP[0], NECK_UP[1], NECK_UP[2]))
    else:
        parts.append(neck(NECK_LO[0], NECK_LO[1], NECK_LO[2]))
        # штуцер отвода воздуха — назад, к расширительному бачку машины (он справа)
        vent = [(0.0, 0.0), (0.0, 0.006), (0.004, 0.006), (0.005, 0.0035), (0.014, 0.0035), (0.0155, 0.0045),
                (0.017, 0.0035), (0.019, 0.0030), (0.019, 0.0018), (0.006, 0.0018), (0.006, 0.0)]
        parts.append(revolve_on(vent, (-0.455, TANK_YC + TANK_D / 2 - 0.004, 0.693), (0, 1, 0), 24))
        # бобышка сливной пробки спереди внизу
        parts.append(revolve_on([(0.0, 0.0), (0.0, 0.011), (0.006, 0.011), (0.007, 0.0095), (0.007, 0.0)],
                                (-0.4415, TANK_YC - TANK_D / 2 + 0.003, 0.392), (0, -1, 0), 32))
    return pt.merge(parts)


def drain_plug():
    """Сливная пробка-барашек (отдельная деталь, выкручивается)."""
    y0 = TANK_YC - TANK_D / 2 + 0.003 - 0.007
    cap = revolve_on([(0.0, 0.0), (0.0, 0.009), (0.008, 0.009), (0.0095, 0.0075), (0.0095, 0.0)],
                     (-0.4415, y0, 0.392), (0, -1, 0), 32)
    wing = rbox((-0.4415, y0 - 0.012, 0.392), (0.004, 0.022, 0.009), 0.0018, 0.0015,
                axes=((1, 0, 0), (0, 0, 1), (0, -1, 0)))
    return pt.merge([cap, wing])


# --- Патрубки и хомуты -----------------------------------------------------------------------------

def hose_paths() -> dict[str, np.ndarray]:
    """Формованные отрезки: прямо по горловине назад, изгиб к двигателю (как подходят патрубки машины)."""
    y0 = TANK_YC + TANK_D / 2 - 0.004 + 0.014       # край патрубка на горловине
    return {
        "upper": bent_path((NECK_UP[0], y0, NECK_UP[1]), (0, 1, 0), 0.036, (-1, 0.55, 0.12), 0.050, 0.065),
        "lower": bent_path((NECK_LO[0], y0, NECK_LO[1]), (0, 1, 0), 0.040, (1, 0.5, 0.12), 0.065, 0.080),
    }


def hose_radius(s: np.ndarray, L: float, r0: float) -> np.ndarray:
    """Наружный радиус вдоль патрубка: вздутие на буртике горловины, обжато под хомутами."""
    r = np.full_like(s, r0)
    r += 0.0012 * np.exp(-((s - 0.0225) / 0.003) ** 2)
    for sc in (0.011, L - 0.013):
        r -= 0.0004 / (1 + np.exp((np.abs(s - sc) - 0.0047) / 0.0006))
    return r


def hose(path: np.ndarray, od: float, n_sec: int = 32):
    """Полый патрубок: наружная и внутренняя стенки, кольцевые торцы."""
    _, N, B = rmf(path, (0, 0, 1))
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    ro = hose_radius(s, s[-1], od / 2)
    ri = od / 2 - HOSE_WALL
    a = np.linspace(0, 2 * math.pi, n_sec, endpoint=False)
    circ = np.c_[np.cos(a), np.sin(a)]
    Vo, Fo = pt.loft(path, N, B, lambda i: circ * ro[i], cap=False)
    Vi, Fi = pt.loft(path, N, B, circ * ri, cap=False)
    m, n = len(Vo), len(path)
    F = list(Fo) + [tuple(m + i for i in f[::-1]) for f in Fi]
    for ring in (0, n - 1):
        b = ring * n_sec
        for j in range(n_sec):
            j2 = (j + 1) % n_sec
            F.append((b + j, b + j2, m + b + j2, m + b + j))
    return np.vstack([Vo, Vi]), F


def worm_clamp(P, T, R: float, rad_hint):
    """Червячный хомут: лента вокруг патрубка, хвост ленты внахлёст, корпус замка и винт с шестигранником."""
    P, T = np.asarray(P, float), _unit(T)
    rad = _unit(np.asarray(rad_hint, float) - T * (T @ np.asarray(rad_hint, float)))
    tan = np.cross(T, rad)
    band = [(a, R + 0.0002 + b) for a, b in pt.rounded_rect(0.009, 0.0008, 0.0003, 2)]
    parts = [revolve_on(band, P, T, 64, closed=True)]
    # хвост ленты: второй слой поверх, от замка назад по окружности
    e1 = rad
    e2 = np.cross(T, e1)
    ang = np.linspace(-0.15, -1.05, 18)
    tail = np.array([P + (R + 0.0013) * (math.cos(t) * e1 + math.sin(t) * e2) for t in ang])
    radial = np.array([math.cos(t) * e1 + math.sin(t) * e2 for t in ang])
    parts.append(pt.loft(tail, np.broadcast_to(T, tail.shape), radial, pt.rounded_rect(0.008, 0.0007, 0.0003, 2)))
    # корпус замка и винт
    hc = P + rad * (R + 0.0035)
    parts.append(rbox(hc, (0.0125, 0.0065, 0.015), 0.002, 0.0018, axes=(T, rad, tan)))
    head = [(0.0, 0.0), (0.0, 0.0042), (0.0008, 0.0042), (0.0010, 0.0036), (0.0012, 0.0038), (0.0045, 0.0038),
            (0.0050, 0.0028), (0.0052, 0.0)]
    parts.append(revolve_on(head, hc + rad * 0.0003 + tan * 0.0074, tan, 6, phase=math.pi / 6))
    parts.append(revolve_on([(0.0, 0.0), (0.0, 0.0024), (0.0045, 0.0024), (0.0052, 0.0016), (0.0054, 0.0)],
                            hc + rad * 0.0003 - tan * 0.0074, -tan, 16))
    return pt.merge(parts)


def hoses_and_clamps():
    """Оба патрубка и по два хомута на каждом (на горловине и на свободном конце)."""
    out = {}
    # замки хомутов — туда, где к винту подлезет отвёртка (вверху над верхним патрубком — фильтр)
    hints = {"upper": ((1, 0, -0.6), (0.4, 1, 0)), "lower": ((-1, 0, 0.5), (0, 0, 1))}
    for key, path in hose_paths().items():
        od = HOSE_UP_OD if key == "upper" else HOSE_LO_OD
        T, _, _ = rmf(path)
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
        clamps = []
        for sc, hint in zip((0.011, s[-1] - 0.013), hints[key]):
            i = int(np.argmin(np.abs(s - sc)))
            R = float(hose_radius(np.array([sc]), s[-1], od / 2)[0])
            clamps.append(worm_clamp(path[i], T[i], R, hint))
        out[key] = (hose(path, od), pt.merge(clamps))
    return out


# --- Бирка партии на проволоке ----------------------------------------------------------------

def tag_frame() -> dict[str, np.ndarray]:
    """Где висит бирка: проволока вокруг верхнего патрубка за горловиной, бирка повёрнута наискосок назад."""
    path = hose_paths()["upper"]
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    Pw = path[int(np.argmin(np.abs(s - 0.036)))]
    rho = HOSE_UP_OD / 2 + 0.0008
    up = _unit((0.05, 0.0, 1.0))
    n0 = _unit((0.45, 1.0, 0.0))
    n = _unit(n0 - up * (n0 @ up))
    u = np.cross(up, n)
    z_top = Pw[2] - rho - 0.002
    top = np.array([Pw[0], Pw[1], z_top - 0.022])       # низ скрутки = верх петли через отверстие
    rt = 0.0068
    hole = top - up * 2 * rt
    center = hole - up * (TAG_H / 2 - TAG_HOLE)
    return {"Pw": Pw, "rho": rho, "up": up, "n": n, "u": u, "z_top": z_top, "top": top, "rt": rt, "hole": hole,
            "center": center}


def tag_wire():
    """Мягкая проволока одной петлёй: через отверстие бирки, скрутка, виток вокруг патрубка, скрутка назад."""
    f = tag_frame()
    up, n, rt = f["up"], f["n"], f["rt"]
    ct = f["top"] - up * rt
    pts = []
    for a in np.linspace(math.pi, 0, 14):                 # петля через бирку — лицевая половина
        pts.append(ct + rt * (math.cos(a) * up + math.sin(a) * n))
    q_bot, q_top = f["top"], np.array([f["Pw"][0], f["Pw"][1], f["z_top"]])
    rh, turns = 0.0008, 4
    X, Y = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    for t in np.linspace(0, 1, 48)[1:]:                   # скрутка вверх
        ph = 2 * math.pi * turns * t
        pts.append(q_bot + (q_top - q_bot) * t + rh * (math.cos(ph) * X + math.sin(ph) * Y))
    Pw, rho = f["Pw"], f["rho"]
    for a in np.linspace(-math.pi / 2 + 0.2, 3 * math.pi / 2 - 0.2, 40):   # виток вокруг патрубка
        pts.append(Pw + rho * (math.cos(a) * X + math.sin(a) * np.array([0, 0, 1.0])))
    for t in np.linspace(1, 0, 48):                       # скрутка вниз (вторая жила)
        ph = 2 * math.pi * turns * t + math.pi
        pts.append(q_bot + (q_top - q_bot) * t + rh * (math.cos(ph) * X + math.sin(ph) * Y))
    for a in np.linspace(0, -math.pi, 14)[1:-1]:          # петля через бирку — оборотная половина
        pts.append(ct + rt * (math.cos(a) * up + math.sin(a) * n))
    P = smooth_closed(np.array(pts), 3, 0.5)
    P = np.vstack([P, P[:2]])                             # замкнуть внахлёст
    return sweep(P, 0.0006, 10, cap=True)


def tag_outline() -> tuple[np.ndarray, list[np.ndarray]]:
    w, h, c = TAG_W, TAG_H, 0.010
    pts = np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2 - c), (w / 2 - c, h / 2), (-w / 2 + c, h / 2),
                    (-w / 2, h / 2 - c)])
    outer = fillet_poly(pts, 0.002, 4)
    a = np.linspace(0, 2 * math.pi, 24, endpoint=False)
    hole = np.c_[0.0028 * np.cos(a), h / 2 - TAG_HOLE + 0.0028 * np.sin(a)][::-1]
    return outer, [hole]


def tag_card():
    f = tag_frame()
    outer, holes = tag_outline()
    return flat_plate(outer, holes, TAG_T, f["center"], f["u"], f["up"], f["n"])


def tag_rings():
    """Бумажные кольца-усилители отверстия с обеих сторон."""
    f = tag_frame()
    prof = [(a, b) for a, b in [(0.0, 0.0028), (0.0, 0.0068), (0.00025, 0.0068), (0.00025, 0.0028)]]
    out = []
    for side in (1, -1):
        base = f["hole"] + side * f["n"] * (TAG_T / 2 - 0.00002)
        out.append(revolve_on(prof, base, side * f["n"], 32, closed=True))
    return pt.merge(out)


# --- Сборка в Blender ------------------------------------------------------------------------------

MATERIALS = {
    # проверочные материалы: нейтральные серые разной светлоты (текстур нет до принятия формы)
    "rad_alu": ((0.62, 0.62, 0.62), 0.4, 1.0),
    "rad_plastic": ((0.16, 0.16, 0.16), 0.55, 0.0),
    "rad_hose": ((0.08, 0.08, 0.08), 0.8, 0.0),
    "rad_clamp": ((0.55, 0.55, 0.56), 0.3, 1.0),
    "rad_wire": ((0.42, 0.42, 0.42), 0.45, 1.0),
    "rad_tag": ((0.74, 0.72, 0.66), 0.9, 0.0),
    "rad_tag_ring": ((0.84, 0.84, 0.82), 0.8, 0.0),
    "rad_ink": ((0.03, 0.03, 0.035), 0.6, 0.0),
}


def _material(name: str):
    import bpy
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb, rough, metal = MATERIALS[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = rough
    m.metallic = 0.0          # окно и Workbench: без металла, иначе светлый алюминий выходит чёрным
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def text_mesh(body: str, height: float, offset: float = 0.0):
    """Надпись шрифтом Blender → плоская сетка; высота заглавных = height, центр в нуле."""
    import bpy
    cu = bpy.data.curves.new("_txt", "FONT")
    cu.body = body
    cu.size = 1.0
    cu.align_x = "CENTER"
    cu.offset = offset
    cu.resolution_u = 8
    ob = bpy.data.objects.new("_txt", cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    V = np.array([v.co[:] for v in me.vertices])
    F = [tuple(p.vertices) for p in me.polygons]
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    bpy.data.meshes.remove(me)
    if len(V) == 0:
        raise RuntimeError(f"шрифт не дал сетку для «{body}»")
    V[:, :2] -= (V[:, :2].min(0) + V[:, :2].max(0)) / 2
    V *= height / np.ptp(V[:, 1])
    return V, F


def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int = 40):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False) + math.pi / 2
    return np.c_[cx + rx * np.cos(a), cy + ry * np.sin(a)], True


def _p_bowl():
    a = np.linspace(math.pi / 2, -math.pi / 2, 16)
    arc = np.c_[0.30 + 0.25 * np.cos(a), 0.75 + 0.25 * np.sin(a)]
    return np.vstack([[(0.0, 1.0)], arc, [(0.0, 0.5)]]), False


# Буквы маркером: штрихи в долях высоты заглавной (ширина знака, [(точки, замкнут)]).
# «Ю» — своя: длинная перемычка, иначе издали буква читается как «IO».
MARKER = {
    "Ю": (0.96, [(np.array([(0.0, 0.0), (0.0, 1.0)]), False), (np.array([(0.0, 0.5), (0.31, 0.5)]), False),
                _ellipse(0.63, 0.5, 0.33, 0.5)]),
    "Р": (0.58, [(np.array([(0.0, 0.0), (0.0, 1.0)]), False), _p_bowl()]),
    "/": (0.40, [(np.array([(0.0, -0.04), (0.40, 1.04)]), False)]),
    "8": (0.58, [_ellipse(0.30, 0.76, 0.22, 0.24), _ellipse(0.30, 0.26, 0.28, 0.26)]),
    " ": (0.12, []),
}


def _disc(c: np.ndarray, r: float, n: int = 12):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = np.vstack([c, c + r * np.c_[np.cos(a), np.sin(a)]])
    return V, [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]


def stroke_ribbon(P: np.ndarray, closed: bool, w: float):
    """Плоский штрих маркера шириной w: лента по точкам, круглые концы и изломы — кружками."""
    n = len(P)
    if closed:
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    else:
        T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    Nn = np.c_[-T[:, 1], T[:, 0]]
    V = np.vstack([P + Nn * w / 2, P - Nn * w / 2])
    F = [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n if closed else n - 1)]   # лицом к +Z, как кружки
    parts = [(V, F)]
    for i in range(n):
        if closed:
            continue
        sharp = 0 < i < n - 1 and (P[i] - P[i - 1]) @ (P[i + 1] - P[i]) < 0.9 * np.linalg.norm(
            P[i] - P[i - 1]) * np.linalg.norm(P[i + 1] - P[i])
        if i in (0, n - 1) or sharp:
            parts.append(_disc(P[i], w / 2))
    return pt.merge([(np.c_[v, np.zeros(len(v))], f) for v, f in parts])


def marker_text(body: str, height: float, width: float, seed: int = 8):
    """Строка маркером: свои штрихи, лёгкий наклон и неровность почерка; центр в нуле."""
    rng = np.random.default_rng(seed)
    out, x = [], 0.0
    for ch in body:
        adv, strokes = MARKER[ch]
        dy, rot, k = rng.normal(0, 0.03), math.radians(rng.normal(0, 2.5)), 1 + rng.normal(0, 0.03)
        ca, sa = math.cos(rot), math.sin(rot)
        for P, closed in strokes:
            Q = (P - (adv / 2, 0.5)) * k @ np.array([[ca, sa], [-sa, ca]]) + (adv / 2, 0.5 + dy)
            Q[:, 0] += 0.12 * Q[:, 1] + x                    # наклон почерка
            out.append(stroke_ribbon(Q, closed, width / height))
        x += adv + 0.20
    V, F = pt.merge(out)
    V[:, :2] -= (V[:, :2].min(0) + V[:, :2].max(0)) / 2
    return V * height, F


def tag_text():
    """Надпись на обеих сторонах бирки: печатное «ПАРТИЯ», крупно маркером «ЮР / 8»."""
    f = tag_frame()
    V, F = text_mesh("ПАРТИЯ", 0.0058)
    V[:, 1] += 0.0290
    lines = [(V, F)]
    V, F = marker_text("ЮР / 8", 0.0150, 0.0021)
    V[:, :2] *= min(1.0, (TAG_W - 0.010) / np.ptp(V[:, 0]))      # не шире бирки
    V[:, 1] += 0.0030
    lines.append((V, F))
    out = []
    for side in (1, -1):
        for V, F in lines:
            x = V[:, :1] * side
            W = f["center"] + x * f["u"] + V[:, 1:2] * f["up"] + side * (TAG_T / 2 + 0.00006) * f["n"]
            out.append((W, F if side > 0 else [t[::-1] for t in F]))
    return pt.merge(out)


def item_parts() -> list[tuple[str, str, np.ndarray, list, bool]]:
    """Детали предмета: (имя, материал, вершины, грани, гладко) в осях машины."""
    hc = hoses_and_clamps()
    return [
        ("Radiator_Core_Tubes", "rad_alu", *core_tubes(), True),
        ("Radiator_Core_Fins", "rad_alu", *core_fins(), False),
        ("Radiator_Core_Frame", "rad_alu", *core_frame(), True),
        ("Radiator_Tank_L", "rad_plastic", *tank(1), True),
        ("Radiator_Tank_R", "rad_plastic", *tank(-1), True),
        ("Radiator_Drain_Plug", "rad_plastic", *drain_plug(), True),
        ("Hose_Upper", "rad_hose", *hc["upper"][0], True),
        ("Hose_Upper_Clamps", "rad_clamp", *hc["upper"][1], True),
        ("Hose_Lower", "rad_hose", *hc["lower"][0], True),
        ("Hose_Lower_Clamps", "rad_clamp", *hc["lower"][1], True),
        ("Tag_Wire", "rad_wire", *tag_wire(), True),
        ("Tag_Card", "rad_tag", *tag_card(), False),
        ("Tag_Rings", "rad_tag_ring", *tag_rings(), False),
    ]


def _add_mesh(name: str, mat: str, V, F, smooth: bool, collection, parent):
    import bmesh
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V - CAR_POS], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    if name != "Tag_Text":                      # плоская краска: лицом наружу с каждой стороны бирки, как построена
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    if smooth:
        try:
            me.set_sharp_from_angle(angle=math.radians(40))
        except AttributeError:
            pass
    me.materials.append(_material(mat))
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    ob.parent = parent
    if smooth:
        wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        wn.mode = "FACE_AREA"
        wn.keep_sharp = True
    return ob


def build(out: Path) -> None:
    import bpy
    from mathutils import Vector
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = bpy.data.collections.new("Radiator_Item")
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new("Radiator", None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.1
    root["item_id"] = "car_radiator"
    root["car_position"] = [float(v) for v in CAR_POS]
    col.objects.link(root)
    total = 0
    for name, mat, V, F, smooth in item_parts():
        _add_mesh(name, mat, V, F, smooth, col, root)
        total += len(F)
        print(f"  {name}: {len(V)} вершин, {len(F)} граней")
    V, F = tag_text()
    ob = _add_mesh("Tag_Text", "rad_ink", V, F, False, col, root)
    total += len(ob.data.polygons)
    f = tag_frame()
    print("бирка: центр (оси предмета)", np.round(f["center"] - CAR_POS, 4).tolist(),
          "нормаль", np.round(f["n"], 3).tolist())
    bpy.context.view_layer.update()
    lo = np.array([np.inf] * 3)
    hi = -lo
    for o in col.objects:
        if o.type == "MESH":
            for c in o.bound_box:
                w = np.array((o.matrix_world @ Vector(c))[:])
                lo, hi = np.minimum(lo, w), np.maximum(hi, w)
    print("габарит предмета, м:", np.round(hi - lo, 4).tolist(), "от", np.round(lo, 4).tolist(),
          "до", np.round(hi, 4).tolist())
    print("граней всего:", total)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("сохранено:", out)


def fit(car: Path, item: Path, out: Path) -> None:
    """Предмет в копии машины (капот открыт): пересечения с отсеком, зазоры до рамки."""
    import bpy
    from mathutils.bvhtree import BVHTree
    bpy.ops.wm.open_mainfile(filepath=str(car))
    with bpy.data.libraries.load(str(item), link=False) as (src, dst):
        dst.objects = list(src.objects)
    col = bpy.data.collections.new("Check_Radiator_Fit")
    bpy.context.scene.collection.children.link(col)
    root = None
    for ob in dst.objects:
        col.objects.link(ob)
        if ob.name.startswith("Radiator") and ob.type == "EMPTY":
            root = ob
    root.location = CAR_POS
    bpy.data.objects["Hood_Hinge"].rotation_euler[0] = -0.87
    bpy.context.view_layer.update()

    def tree(ob):
        M = ob.matrix_world
        vs = [M @ v.co for v in ob.data.vertices]
        return BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in ob.data.polygons])
    bay = [o for o in bpy.data.collections["EngineBay"].all_objects if o.type == "MESH"]
    bay += [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(("Bumper", "Grille", "Front"))
            and o not in bay]
    mine = [o for o in dst.objects if o.type == "MESH"]
    trees = {o.name: tree(o) for o in bay + mine}
    print("пересечения предмета с машиной (пар треугольников, где по высоте):")
    for a in mine:
        Ma = a.matrix_world
        for b in bay:
            pairs = trees[a.name].overlap(trees[b.name])
            if pairs:
                zs = [(Ma @ a.data.polygons[i].center).z for i, _ in pairs]
                xs = [(Ma @ a.data.polygons[i].center).x for i, _ in pairs]
                print(f"  {a.name} × {b.name}: {len(pairs)}  z {min(zs):.3f}…{max(zs):.3f}"
                      f"  x {min(xs):.3f}…{max(xs):.3f}")
    frame = bpy.data.objects["Bay_Radiator_Frame"]
    fv = np.array([(frame.matrix_world @ v.co)[:] for v in frame.data.vertices])
    for a in mine:
        av = np.array([(a.matrix_world @ v.co)[:] for v in a.data.vertices])
        lo, hi = av.min(0), av.max(0)
        print(f"  {a.name}: X {lo[0]:.3f}…{hi[0]:.3f}  Y {lo[1]:.3f}…{hi[1]:.3f}  Z {lo[2]:.3f}…{hi[2]:.3f}")
    print("рамка: X", np.round([fv[:, 0].min(), fv[:, 0].max()], 3).tolist())
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("проверка сохранена:", out)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv and argv[0] == "fit":
        fit(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    elif argv:
        build(Path(argv[0]))
