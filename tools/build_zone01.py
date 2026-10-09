"""Зона 1 «Район ТЦ»: рельеф, маска поверхностей и блокаут по плану docs/design/contracts_and_map.md §6
и утверждённой концепт-карте (docs/design/zone01_map.md).

Использование: python tools/build_zone01.py
Пишет:
  data/terrain/zone01_heights.r32          карта высот (float32, 1 м), её читает DistrictTerrain
  assets/terrain/zone01_splat.png          маска поверхностей R грязь, G камень, B щебень, A листва
  assets/terrain/zone01_{albedo,normal,arm}.jpg  массивы слоёв рельефа (6 слоёв, полосой)
  data/sectors/zone01_mall.json            данные сектора (границы, точки, дороги, растительность)
  scenes/levels/zone01_mall.tscn           главная сцена уровня
  scenes/levels/zone01/zone01_world.tscn   рельеф, дороги, вода, железная дорога, периметр
  scenes/levels/zone01/zone01_blockout.tscn  серый блокаут зон 1–4, 6–14
  scenes/levels/zone01/zone01_yard05.tscn  двор с хрущёвками — ТОЛЬКО если файла ещё нет
                                           (детальную зону 5 собирает tools/build_zone01_yard.py)

Случайного размещения во время игры нет: план задан координатами здесь, шум — с фиксированным
зерном. Повторный запуск перезаписывает мир и блокаут (ручные правки этих двух сцен пропадут).
Оси: X — восток, Z — юг (север = -Z), 1 единица = 1 м. Центр ТЦ — (0, 0).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scenes/levels/zone01"
SECTOR = "res://data/sectors/zone01_mall.json"

# ------------------------------------------------------------------ сетка рельефа
# сетка шире игровой области: за границей — фон (панельки за насыпью и оврагом, лес)
X0, Z0, NX, NZ = -480.0, -300.0, 1011, 640
STEP = 1.0
xs = X0 + np.arange(NX) * STEP
zs = Z0 + np.arange(NZ) * STEP
GX, GZ = np.meshgrid(xs, zs)
RNG = np.random.default_rng(20261007)

# граница игровой области (по концепт-карте; масштаб подогнан под ТЦ Ø175)
BOUNDARY = [
    [-358, -197], [-14, -214], [380, -210], [410, -160], [425, -60], [440, 40], [436, 140],
    [442, 262], [300, 298], [0, 300], [-115, 292], [-240, 250], [-292, 207], [-362, 135],
    [-402, 12], [-392, -120],
]

# ж/д насыпь (13): ось, высота верха, полуширина верха, заложение откоса
RAIL = [(-430.0, -189.0), (470.0, -198.0)]
RAIL_TOP = 6.2
RAIL_HALF = 5.0
RAIL_SLOPE = 9.5
OVERPASS_X = 0.0
OVERPASS_HALF = 9.0

# овраг (12): ось русла с севера на юг, глубина 10 м
RAVINE = [(-305, -176), (-312, -140), (-318, -108), (-334, -70), (-345, -36), (-343, 4),
          (-340, 38), (-326, 66), (-310, 90), (-276, 112), (-240, 132), (-208, 158),
          (-190, 182), (-196, 214), (-214, 250), (-232, 280)]
RAVINE_DEPTH = 10.0
RAVINE_BOTTOM = 3.0
RAVINE_TOP = 22.0

HILL = (365.0, 190.0)
HILL_H = 16.0
HILL_R = 108.0
HILL_TOP_R = 18.0

MALL_R = 87.5
PODIUM_R = 92.5
PODIUM_H = 1.5
RING_R = 100.0

PIT = (-55.0, 112.0, 50.0, 168.0)    # погрузка (3): выемка −4 м
PIT_H = -4.0
PIT_RAMP = (-10.0, 168.0, 0.0, 198.0)  # пандус выезда на юг
TUNNEL = (-6.0, 86.0, 6.0, 112.0)      # тоннель-проезд под кольцевой дорогой к ТЦ

PONDS_PAD = (56.0, 172.0, 154.0, 208.0)
PONDS = [(62.0, 178.0, 102.0, 202.0), (108.0, 178.0, 148.0, 202.0)]
PONDS_H = 3.0

ROADS: list[dict] = []
ROAD_DEFS = [
    # имя, точки, ширина проезжей части, тротуар
    ("NorthRoad", [(-272, -164), (-100, -164), (0, -164), (200, -162), (377, -160)], 9.0, 2.5),
    ("Overpass", [(0, -110), (0, -164), (0, -224)], 9.0, 2.5),
    ("WestLink", [(-100, -164), (-100, -60), (-100, -14)], 8.0, 2.0),
    ("EastRoad", [(377, -160), (377, -60), (377, 26)], 8.0, 0.0),
    ("EastEntry", [(450, 26), (377, 26), (300, 32), (215, 52), (120, 50), (92, 40)], 9.0, 2.0),
    ("SiteRoad", [(70, 72), (130, 90), (200, 100)], 7.0, 0.0),
    ("LoadingExit", [(-5, 198), (-5, 214)], 8.0, 0.0),
]

# ------------------------------------------------------------------ помощники numpy


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def noise(cell: float, seed: int) -> np.ndarray:
    """Плавный шум 0..1 с размером пятна ~cell метров (бикубическое растяжение решётки)."""
    rng = np.random.default_rng(seed)
    w = int(math.ceil(NX * STEP / cell)) + 2
    h = int(math.ceil(NZ * STEP / cell)) + 2
    small = Image.fromarray(rng.random((h, w)).astype(np.float32), mode="F")
    big = small.resize((int(w * cell / STEP), int(h * cell / STEP)), Image.BICUBIC)
    arr = np.asarray(big, dtype=np.float32)[:NZ, :NX]
    return np.clip(arr, 0.0, 1.0)


def fbm(cell: float, seed: int) -> np.ndarray:
    return noise(cell, seed) * 0.55 + noise(cell / 2.1, seed + 1) * 0.3 + noise(cell / 4.6, seed + 2) * 0.15


def polyline_distance(points) -> tuple[np.ndarray, np.ndarray]:
    """Расстояние до ломаной и пройденная вдоль неё длина в ближайшей точке."""
    best = np.full(GX.shape, np.inf, dtype=np.float32)
    along = np.zeros(GX.shape, dtype=np.float32)
    total = 0.0
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        dx, dz = bx - ax, bz - az
        length = math.hypot(dx, dz)
        t = np.clip(((GX - ax) * dx + (GZ - az) * dz) / (length * length), 0.0, 1.0)
        d = np.hypot(GX - ax - dx * t, GZ - az - dz * t)
        mask = d < best
        best = np.where(mask, d, best)
        along = np.where(mask, total + t * length, along)
        total += length
    return best, along


def rect_distance(x0, z0, x1, z1) -> np.ndarray:
    dx = np.maximum(np.maximum(x0 - GX, GX - x1), 0.0)
    dz = np.maximum(np.maximum(z0 - GZ, GZ - z1), 0.0)
    return np.hypot(dx, dz)


def flatten(h, dist, height, fall, keep=0.0, keep_field=None):
    """Площадка: внутри — заданная высота (с долей исходного рельефа keep), к краю — плавно к рельефу."""
    t = smooth(dist / max(fall, 0.01))
    target = height if keep_field is None else height + keep * (keep_field - 0.5)
    return target * (1.0 - t) + h * t


def inside_polygon(poly) -> np.ndarray:
    inside = np.zeros(GX.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        cond = (z1 > GZ) != (z2 > GZ)
        xcross = (x2 - x1) * (GZ - z1) / ((z2 - z1) if z2 != z1 else 1e-9) + x1
        inside ^= cond & (GX < xcross)
    return inside


# ------------------------------------------------------------------ рельеф

def build_heights() -> np.ndarray:
    undulation = (fbm(140.0, 1) - 0.5) * 2.0 + (fbm(45.0, 2) - 0.5) * 0.7
    h = undulation.astype(np.float32)
    detail = fbm(18.0, 3)

    # восточный склон под гаражами (8): от x 255 вверх на 6 м к x 335, дальше полка
    rise = smooth((GX - 255.0) / 80.0) * 6.0
    band = 1.0 - smooth((np.maximum(GZ - 55.0, -175.0 - GZ)) / 40.0)
    h += rise * band

    # холм (10): купол с плоской вершиной, неровный край
    d_hill = np.hypot(GX - HILL[0], GZ - HILL[1])
    radius = HILL_R * (0.85 + 0.3 * noise(60.0, 4))
    t = np.clip((d_hill - HILL_TOP_R) / (radius - HILL_TOP_R), 0.0, 1.0)
    hill = HILL_H * (0.5 + 0.5 * np.cos(t * math.pi)) * (0.92 + 0.16 * detail)
    hill = np.where(d_hill < HILL_TOP_R + 4, HILL_H, hill)
    h = np.maximum(h, h * (1 - smooth(1 - t)) + hill)

    # площадки (что ниже приоритетом — раньше)
    pads = [
        ((-282, -160, -132, -44), 0.35, 10.0, 0.5),   # двор хрущёвок (5)
        ((-238, -58, -104, 112), 0.25, 8.0, 0.0),      # рынок (6)
        ((-82, -154, 92, -104), 0.2, 6.0, 0.0),        # площадь (4)
        ((118, -74, 202, 48), 0.05, 6.0, 0.0),         # паркинг (2): земля под плитой пола
        ((178, -146, 282, -104), 0.15, 6.0, 0.0),      # АЗС (7)
        ((200, 72, 280, 128), 0.2, 8.0, 0.3),          # недострой (9)
        ((60, 104, 156, 170), 0.3, 6.0, 0.0),          # подстанция (11)
        ((390, 10, 432, 44), None, 6.0, 0.0),          # блокпост (14) — на своей высоте
    ]
    for (x0, z0, x1, z1), height, fall, keep in pads:
        if height is None:
            height = float(h[int((z0 + z1) / 2 - Z0), int((x0 + x1) / 2 - X0)])
        h = flatten(h, rect_distance(x0, z0, x1, z1), height, fall, keep, detail)
    # фон за границей: ровные площадки под панельки
    for x0, z0, x1, z1 in PADS_BG:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        h = flatten(h, rect_distance(x0 - 3, z0 - 3, x1 + 3, z1 + 3), float(h[int(cz - Z0), int(cx - X0)]), 10.0)
    # частные дома у оврага (12)
    for hx, hz in [(-270, 3), (-297, 25), (-272, 50)]:
        h = flatten(h, rect_distance(hx - 10, hz - 9, hx + 10, hz + 9), float(h[int(hz - Z0), int(hx - X0)]), 6.0)
    # кольцевая дорога и подиум ТЦ
    d_c = np.hypot(GX, GZ)
    h = flatten(h, np.maximum(d_c - (RING_R + 9.0), 0.0), 0.2, 8.0)
    # отстойники (11): насыпь +3 м
    h = flatten(h, rect_distance(*PONDS_PAD), PONDS_H, 7.0)

    # вершина холма — ровная площадка ретранслятора
    h = flatten(h, np.maximum(d_hill - HILL_TOP_R, 0.0), HILL_H, 3.0, 0.4, detail)

    # насыпь (13): трапеция, верх ровный; путепровод — разрыв с вертикальными устоями
    d_rail, along_rail = polyline_distance(RAIL)
    emb = np.where(d_rail < RAIL_HALF, RAIL_TOP, RAIL_TOP * (1.0 - smooth((d_rail - RAIL_HALF) / RAIL_SLOPE * 1.0)))
    emb = np.where(d_rail < RAIL_HALF + RAIL_SLOPE, emb, 0.0)
    emb = np.where(np.abs(GX - OVERPASS_X) < OVERPASS_HALF, 0.0, emb)
    h = np.maximum(h, emb + np.minimum(h, 0.0) * 0.0)

    # овраг (12): чаша к руслу, неровные бровки; в начале мельче
    d_rav, along_rav = polyline_distance(RAVINE)
    top = RAVINE_TOP * (0.8 + 0.45 * noise(35.0, 5))
    depth = RAVINE_DEPTH * smooth(along_rav / 40.0) * 0.6 + RAVINE_DEPTH * 0.4
    s = np.clip((d_rav - RAVINE_BOTTOM) / (top - RAVINE_BOTTOM), 0.0, 1.0)
    cut = depth * (1.0 - s) ** 1.5
    cut += np.where(d_rav < RAVINE_BOTTOM, 0.0, (detail - 0.5) * 1.6 * (1.0 - s) * s * 4.0)
    h -= np.where(d_rav < top, cut, 0.0)

    # дороги — после рельефа: полотно по сглаженному профилю
    for name, points, width, sidewalk in ROAD_DEFS:
        h = carve_road(h, name, points, width, sidewalk)
    ring = [(RING_R * math.cos(a), RING_R * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 73)]
    h = carve_road(h, "RingRoad", ring, 10.0, 2.0, closed=True)

    # подиум ТЦ +1.5 (подпорная стенка — в блокауте)
    # плато чуть внутри стенки: на шаге меша 2 м откос не вылезает наружу; сверху — мощение
    h = flatten(h, np.maximum(d_c - (PODIUM_R - 1.5), 0.0), PODIUM_H, 1.2)
    # погрузка (3): выемка, тоннель, пандус выезда
    h = np.where(rect_distance(*PIT) < 0.01, PIT_H, h)
    h = np.where(rect_distance(*TUNNEL) < 0.01, PIT_H, h)
    rx0, rz0, rx1, rz1 = PIT_RAMP
    in_ramp = (GX >= rx0) & (GX <= rx1) & (GZ >= rz0) & (GZ <= rz1)
    ramp_t = np.clip((GZ - rz0) / (rz1 - rz0), 0.0, 1.0)
    h = np.where(in_ramp, PIT_H + (0.2 - PIT_H) * ramp_t, h)
    # чаши отстойников: дно на 0.8 м, бетонные стенки — в блокауте
    for rect in PONDS:
        h = np.where(rect_distance(*rect) < 0.01, 0.8, h)
    return h.astype(np.float32)


def sample(h: np.ndarray, x: float, z: float) -> float:
    fx = min(max((x - X0) / STEP, 0.0), NX - 1.001)
    fz = min(max((z - Z0) / STEP, 0.0), NZ - 1.001)
    ix, iz = int(fx), int(fz)
    tx, tz = fx - ix, fz - iz
    a, b = h[iz, ix], h[iz, ix + 1]
    c, d = h[iz + 1, ix], h[iz + 1, ix + 1]
    return float((a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz)


def carve_road(h, name, points, width, sidewalk, closed=False):
    """Полотно дороги: профиль по рельефу, сглаженный на ~40 м, земля под ним — вровень."""
    dense = []
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        n = max(1, int(math.dist((ax, az), (bx, bz)) / 2.0))
        for i in range(n):
            dense.append((ax + (bx - ax) * i / n, az + (bz - az) * i / n))
    dense.append(points[-1])
    ys = np.array([sample(h, x, z) for x, z in dense])
    k = 20
    padded = np.concatenate([ys[-k:], ys, ys[:k]]) if closed else np.pad(ys, k, mode="edge")
    ys = np.convolve(padded, np.ones(2 * k + 1) / (2 * k + 1), mode="same")[k:-k]
    if name == "Overpass":
        # проезд под насыпью — у земли, без «горба» от откосов
        ys = np.array([min(y, 0.3) if abs(z + 190) < 30 else y for y, (x, z) in zip(ys, dense)])
    half = width * 0.5 + sidewalk
    target = np.full(GX.shape, np.nan, dtype=np.float32)
    best = np.full(GX.shape, np.inf, dtype=np.float32)
    for i in range(len(dense) - 1):
        (ax, az), (bx, bz) = dense[i], dense[i + 1]
        dx, dz = bx - ax, bz - az
        length2 = dx * dx + dz * dz
        if length2 < 1e-6:
            continue
        x0, x1 = min(ax, bx) - half - 6, max(ax, bx) + half + 6
        z0, z1 = min(az, bz) - half - 6, max(az, bz) + half + 6
        i0, i1 = max(0, int(x0 - X0)), min(NX, int(x1 - X0) + 1)
        j0, j1 = max(0, int(z0 - Z0)), min(NZ, int(z1 - Z0) + 1)
        if i0 >= i1 or j0 >= j1:
            continue
        sx, sz = GX[j0:j1, i0:i1], GZ[j0:j1, i0:i1]
        t = np.clip(((sx - ax) * dx + (sz - az) * dz) / length2, 0.0, 1.0)
        d = np.hypot(sx - ax - dx * t, sz - az - dz * t)
        y = ys[i] + (ys[i + 1] - ys[i]) * t
        sub_best = best[j0:j1, i0:i1]
        m = d < sub_best
        sub_best[m] = d[m]
        target[j0:j1, i0:i1][m] = y[m]
    w = 1.0 - smooth((best - half) / 5.0)
    h = np.where(np.isnan(target), h, h * (1 - w) + (np.nan_to_num(target) - 0.06) * w)
    ROADS.append(dict(id=name, width=width, sidewalk=sidewalk,
                      points=[[round(x, 2), round(float(y), 3), round(z, 2)] for (x, z), y in list(zip(dense, ys))[::5]] +
                      ([] if (len(dense) - 1) % 5 == 0 else [[round(dense[-1][0], 2), round(float(ys[-1]), 3), round(dense[-1][1], 2)]])))
    return h


# ------------------------------------------------------------------ маска поверхностей

def build_splat(h: np.ndarray) -> np.ndarray:
    detail = fbm(12.0, 11)
    patches = fbm(30.0, 12)
    inside = inside_polygon(BOUNDARY)
    mud = np.zeros(GX.shape, np.float32)
    rock = np.zeros(GX.shape, np.float32)
    gravel = np.zeros(GX.shape, np.float32)
    leaves = np.zeros(GX.shape, np.float32)

    d_rail, _ = polyline_distance(RAIL)
    gravel = np.maximum(gravel, 1.0 - smooth((d_rail - RAIL_HALF - 1.0) / 3.0))
    gravel = np.maximum(gravel, (1.0 - smooth((d_rail - RAIL_HALF) / (RAIL_SLOPE + 2))) * smooth((detail - 0.35) / 0.3))

    d_rav, _ = polyline_distance(RAVINE)
    mud = np.maximum(mud, 1.0 - smooth((d_rav - RAVINE_BOTTOM - 1.5) / 3.0))
    rock = np.maximum(rock, (1.0 - smooth((d_rav - 14.0) / 6.0)) * smooth((d_rav - 3.5) / 2.0) * smooth((detail - 0.3) / 0.35))
    leaves = np.maximum(leaves, (1.0 - smooth((d_rav - 26.0) / 8.0)) * 0.75 * smooth((patches - 0.3) / 0.3))

    # лесополоса на юге и вокруг холма; листва под деревьями
    forest = forest_mask()
    leaves = np.maximum(leaves, forest * (0.65 + 0.35 * detail))
    d_hill = np.hypot(GX - HILL[0], GZ - HILL[1])
    leaves = np.maximum(leaves, (1.0 - smooth((d_hill - 40.0) / 30.0)) * smooth((patches - 0.45) / 0.3) * 0.7)
    rock = np.maximum(rock, (1.0 - smooth((d_hill - 30.0) / 25.0)) * smooth((d_hill - 12.0) / 8.0) * smooth((detail - 0.55) / 0.25))
    gravel = np.maximum(gravel, 1.0 - smooth((d_hill - HILL_TOP_R - 1.0) / 3.0))

    # грунтовки: серпантин на холм, лесная дорога, тропа к домам, проезды гаражей
    for path, width in [
        ([(300, 118), (336, 140), (318, 168), (346, 202), (372, 192), (366, 178)], 3.5),
        ([(-5, 212), (-4, 250), (2, 300)], 4.5),
        ([(-100, 40), (-160, 38), (-240, 30), (-272, 18), (-310, 34), (-385, 40)], 2.5),
        ([(-120, 110), (-200, 150), (-185, 200), (-150, 260), (-114, 292)], 2.0),
        ([(256, -100), (262, 16)], 4.0), ([(279, -100), (285, 16)], 4.0), ([(302, -100), (308, 16)], 4.0),
        ([(200, 100), (300, 118)], 4.0),
        # двор хрущёвок (5): вытоптанные тропинки поперёк газонов, к бакам, к гаражам
        ([(-204.0, -126.0), (-199.0, -104.0), (-197.0, -92.0)], 1.2),
        ([(-188.0, -126.0), (-180.0, -96.0), (-176.0, -70.0)], 1.0),
        ([(-164.0, -100.0), (-182.0, -95.0), (-197.0, -92.0)], 1.1),
        ([(-228.0, -85.0), (-212.0, -88.0), (-197.0, -92.0)], 1.0),
        ([(-228.0, -60.0), (-205.0, -57.0)], 1.0),
        ([(-240.0, -150.0), (-262.0, -150.0)], 1.5),
    ]:
        d, _ = polyline_distance(path)
        mud = np.maximum(mud, 1.0 - smooth((d - width * 0.5) / 2.5 + (detail - 0.5)))
    # детская площадка: вытоптанная земля с песком; полоса у гаражей
    d_play = np.hypot(GX + 197.0, GZ + 92.0)
    mud = np.maximum(mud, (1.0 - smooth((d_play - 9.0 - 4.0 * detail) / 4.0)) * 0.85)
    mud = np.maximum(mud, (1.0 - smooth(rect_distance(-275, -164, -258, -100) / 3.0)) * (0.5 + 0.5 * detail))
    leaves = np.maximum(leaves, (1.0 - smooth(rect_distance(-250, -158, -150, -48) / 2.0)) * smooth((patches - 0.35) / 0.35) * 0.55)
    # стройплощадка и подстанция — щебень с грязью
    gravel = np.maximum(gravel, (1.0 - smooth(rect_distance(198, 70, 282, 130) / 4.0)) * (0.55 + 0.45 * detail))
    mud = np.maximum(mud, (1.0 - smooth(rect_distance(198, 70, 282, 130) / 6.0)) * smooth((patches - 0.4) / 0.3))
    gravel = np.maximum(gravel, 1.0 - smooth(rect_distance(64, 108, 152, 166) / 2.0))
    # пятна вытоптанной земли и голой глины по всей карте
    mud = np.maximum(mud, smooth((patches - 0.72) / 0.15) * smooth((detail - 0.4) / 0.4) * 0.8)
    # вне границы — сплошная листва и подлесок (декорация)
    leaves = np.where(inside, leaves, np.maximum(leaves, 0.6))
    rgba = np.stack([mud, rock, gravel, leaves], axis=-1)
    return (np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ растительность всей карты

PADS_BG = [(x - 30, z - 12, x + 30, z + 12) if abs(yaw) < 45 else (x - 12, z - 30, x + 12, z + 30)
           for _, x, z, yaw in [("", -290, -262, 0), ("", -170, -270, 8), ("", 110, -268, -5), ("", 250, -262, 3), ("", -40, -250, 0),
                                ("", 360, -250, 0), ("", -450, -110, 90), ("", -452, -40, 92), ("", -450, 60, 88), ("", 500, -60, -90),
                                ("", 495, 60, -90)]]
PADS_PAVED = PADS_BG + [(-82, -154, 92, -104), (118, -74, 202, 48), (178, -146, 282, -104), (200, 72, 280, 128),
              (60, 104, 156, 170), (-238, -58, -104, 112), (-282, -160, -132, -44), PIT, PONDS_PAD, (390, 10, 432, 44)]


def build_vegetation(h: np.ndarray, splat: np.ndarray) -> None:
    """Деревья и сухая трава по всей карте (двор хрущёвок — свой генератор): точки в JSON для
    DistrictScatter. Лес — по маске лесополосы, склоны оврага, кольцо вокруг холма; трава — везде,
    где нет покрытия, площадок и голой грязи/щебня."""
    rng = np.random.default_rng(31)
    inside = inside_polygon(BOUNDARY)
    paved = np.zeros(GX.shape, bool)
    for rect in PADS_PAVED:
        paved |= rect_distance(*rect) < 2.0
    paved |= np.hypot(GX, GZ) < RING_R + 9.0
    for road in ROADS:
        pts = [(p[0], p[2]) for p in road["points"]]
        d, _ = polyline_distance(pts)
        paved |= d < road["width"] * 0.5 + road["sidewalk"] + 1.5
    d_rail, _ = polyline_distance(RAIL)
    paved |= d_rail < RAIL_HALF + 1.0
    d_rav, _ = polyline_distance(RAVINE)
    forest = forest_mask()
    mud, gravel = splat[..., 0] / 255.0, splat[..., 2] / 255.0
    trees: dict[str, list] = {f"tree_{k}_{v}": [] for k in ("birch", "poplar", "maple") for v in range(3)}
    trees.update({k: [] for k in SPRUCES + BIRCHES})

    def put(kind: str, x: float, z: float) -> None:
        # ель — своя (tools/build_spruce.py): в лесу высокие с сухими сучьями и подрост, на открытом —
        # одиночные с юбкой до земли; лиственные — свои
        if kind == "fir":
            key = rng.choice(["spruce_forest_a", "spruce_forest_a", "spruce_forest_b", "spruce_forest_b", "spruce_young_a", "spruce_young_b"])
        elif kind == "spruce_open":
            key = "spruce_open"
        elif kind == "birch":
            # берёза — своя (tools/build_birch.py): одиночные, двойные, кусты по три, почти голые, молодые
            key = rng.choice(["birch_a", "birch_a", "birch_b", "birch_c", "birch_bare", "birch_bare", "birch_young"])
        else:
            key = f"tree_{kind}_{int(rng.integers(0, 3))}"
        trees[key].append([round(x, 2), round(sample(h, x, z) - 0.1, 3), round(z, 2), round(float(rng.uniform(0, 360)), 1),
                           round(float(rng.uniform(0.8, 1.2)), 3)])

    def ok(ix: int, iz: int) -> bool:
        return 0 <= ix < NX and 0 <= iz < NZ and not paved[iz, ix]

    for gz in np.arange(Z0 + 4, Z0 + NZ - 4, 6.5):
        for gx in np.arange(X0 + 4, X0 + NX - 4, 6.5):
            x, z = gx + rng.uniform(-2.8, 2.8), gz + rng.uniform(-2.8, 2.8)
            ix, iz = int(x - X0), int(z - Z0)
            if not ok(ix, iz) or (-285 < x < -135 and -165 < z < -42):
                continue
            f = forest[iz, ix]
            r = d_rav[iz, ix]
            if f > 0.5 and rng.random() < 0.75 * f:
                put(rng.choice(["fir", "fir", "fir", "birch", "birch", "maple", "poplar"]), x, z)
            elif 4.0 < r < 30.0 and rng.random() < 0.38:
                put(rng.choice(["maple", "maple", "birch", "fir"]), x, z)
            elif not inside[iz, ix] and rng.random() < 0.3:
                # за границей — сплошной лес (декорация края карты)
                put(rng.choice(["fir", "fir", "birch", "maple", "poplar"]), x, z)
            elif inside[iz, ix] and rng.random() < 0.012:
                put(rng.choice(["birch", "maple", "spruce_open"]), x, z)
    # тополя вдоль подножия насыпи
    for x in np.arange(-260, 380, 11.0):
        if abs(x) > 20 and rng.random() < 0.7:
            z = -176.0 + rng.uniform(-1.5, 1.5)
            if ok(int(x - X0), int(z - Z0)):
                put("poplar", x + rng.uniform(-2, 2), z)
    add_pines(trees, h, forest, inside, d_rav)
    # подлесок: папоротник, валежник, пни, сухостой, корни — в лесу; камни со мхом — по склонам оврага
    under: dict[str, list] = {k: [] for k in ("forest_fern", "forest_dry_branches", "forest_stump_01", "forest_stump_02",
                                              "forest_dead_trunk", "forest_roots", "forest_rocks_01", "forest_rocks_02")}
    for gz in np.arange(Z0 + 3, Z0 + NZ - 3, 4.0):
        for gx in np.arange(X0 + 3, X0 + NX - 3, 4.0):
            x, z = gx + rng.uniform(-1.8, 1.8), gz + rng.uniform(-1.8, 1.8)
            ix, iz = int(x - X0), int(z - Z0)
            if not ok(ix, iz):
                continue
            f, r = forest[iz, ix], d_rav[iz, ix]
            roll = rng.random()
            key = None
            if f > 0.4:
                for name, pr in (("forest_fern", 0.16), ("forest_dry_branches", 0.05), ("forest_stump_01", 0.015),
                                 ("forest_stump_02", 0.015), ("forest_dead_trunk", 0.012), ("forest_roots", 0.012)):
                    if roll < pr:
                        key = name
                        break
                    roll -= pr
            elif 3.5 < r < 22.0:
                for name, pr in (("forest_rocks_01", 0.06), ("forest_rocks_02", 0.06), ("forest_fern", 0.06), ("forest_dry_branches", 0.03)):
                    if roll < pr:
                        key = name
                        break
                    roll -= pr
            if key:
                under[key].append([round(x, 2), round(sample(h, x, z) - 0.05, 3), round(z, 2), round(float(rng.uniform(0, 360)), 1),
                                   round(float(rng.uniform(0.8, 1.2)), 3)])
    patch = fbm(9.0, 41)
    clump = fbm(4.0, 43)
    near_edge = np.zeros(GX.shape, np.float32)
    # «края» — у дорог, площадок, насыпи: там бурьян гуще (не косят, не ходят)
    for rect in PADS_PAVED:
        d = rect_distance(*rect)
        near_edge = np.maximum(near_edge, (1.0 - smooth((d - 2.0) / 6.0)) * (d > 1.5))
    near_edge = np.maximum(near_edge, (1.0 - smooth((d_rail - RAIL_HALF - RAIL_SLOPE) / 6.0)))

    def accept(x: float, z: float) -> bool:
        ix, iz = int(x - X0), int(z - Z0)
        if not (0 <= ix < NX and 0 <= iz < NZ) or paved[iz, ix] or (-285 < x < -135 and -165 < z < -42):
            return False
        return mud[iz, ix] < 0.4 and gravel[iz, ix] < 0.45 and d_rav[iz, ix] > 2.5

    def kind_at(x: float, z: float, roll: float):
        ix, iz = int(x - X0), int(z - Z0)
        f, e, pc, cl = forest[iz, ix], near_edge[iz, ix], patch[iz, ix], clump[iz, ix]
        rav = 3.0 < d_rav[iz, ix] < 26.0
        bush_p = 0.05 * smooth((f - 0.15) / 0.3) + 0.012 * e + (0.014 if rav else 0.0)
        if roll < bush_p * (0.4 + 0.6 * smooth((cl - 0.35) / 0.3)):
            return "bush"
        roll -= bush_p
        sap_p = 0.012 * f + (0.004 if rav else 0.0)
        if roll < sap_p:
            return "sapling"
        roll -= sap_p
        dens = 0.08 + 0.55 * smooth((pc - 0.4) / 0.3) + 0.45 * e + (0.25 if rav else 0.0) - 0.4 * f
        if not inside[iz, ix]:
            dens *= 0.4
        if roll < max(0.0, dens) * smooth((cl - 0.25) / 0.35):
            return "grass" if roll > 0.06 else "weed"
        return None

    under.update(scatter_undergrowth(rng, X0 + 2, Z0 + 2, X0 + NX - 3, Z0 + NZ - 3, accept, kind_at))
    # карта плотности травы для DistrictGrass: R — трава, G — сорняки; 1 пиксель = 1 м
    import build_zone01_yard as yard
    dens = np.clip(0.18 + 0.55 * smooth((patch - 0.35) / 0.35) + 0.4 * near_edge, 0.0, 1.0) * smooth((clump - 0.15) / 0.4)
    dens = (dens * (1.0 - 0.6 * forest) + 0.12 * forest) * np.where(inside, 1.0, 0.35)
    dens = np.where((mud > 0.4) | (gravel > 0.45) | (d_rav < 2.5) | paved, 0.0, dens)
    dens = dens * (1.0 - smooth((mud - 0.15) / 0.25) * 0.8)
    weeds = np.clip(0.3 + 0.7 * near_edge, 0.0, 1.0) * (dens > 0.05)
    # двор: тротуары, проезды, дома, гаражи — без травы; у стен гуще; на площадке почти нет
    in_yard = (GX > -285) & (GX < -135) & (GZ > -165) & (GZ < -42)
    yard_dens = np.full(GX.shape, 0.55, np.float32)
    for _, pts, width, _, _ in yard.PAVING:
        dd, _ = polyline_distance(pts)
        yard_dens = np.where(dd < width * 0.5 + 0.35, 0.0, yard_dens)
    for x0, z0, x1, z1 in [(-240.8, -143.8, -183.2, -132.2), (-165.8, -136.8, -142.2, -79.2), (-244.0, -107.2, -232.0, -52.8)]:
        dd = rect_distance(x0, z0, x1, z1)
        yard_dens = np.where(dd < 0.5, 0.0, np.maximum(yard_dens, (1.0 - smooth((dd - 0.5) / 4.0)) * 0.95 * (yard_dens > 0)))
    yard_dens = np.where(rect_distance(-272.5, -162, -266.5, -104) < 0.3, 0.0, yard_dens)
    play = np.hypot(GX - yard.PLAYGROUND[0], GZ - yard.PLAYGROUND[1])
    yard_dens = yard_dens * (0.08 + 0.92 * smooth((play - 10.0) / 4.0)) * (0.6 + 0.6 * smooth((patch - 0.3) / 0.4))
    yard_dens = np.where(mud > 0.4, yard_dens * 0.2, yard_dens)
    dens = np.where(in_yard, np.clip(yard_dens, 0, 1), dens)
    img = np.stack([dens, weeds, np.zeros_like(dens)], -1)
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), mode="RGB").save(ROOT / "assets/terrain/zone01_grass.png")
    imp = ROOT / "assets/terrain/zone01_grass.png.import"
    if not imp.exists():
        imp.write_text(IMPORT_SPLAT.format(name="zone01_grass.png"), encoding="utf-8")
    grass = []
    for _ in range(0):
        x = float(rng.uniform(X0 + 2, X0 + NX - 3))
        z = float(rng.uniform(Z0 + 2, Z0 + NZ - 3))
        ix, iz = int(x - X0), int(z - Z0)
        if paved[iz, ix] or (-285 < x < -135 and -165 < z < -42):
            continue
        if mud[iz, ix] > 0.35 or gravel[iz, ix] > 0.4 or d_rav[iz, ix] < 3.5:
            continue
        if rng.random() > 0.25 + 0.75 * smooth((patch[iz, ix] - 0.35) / 0.3):
            continue
        grass.append([round(x, 2), round(sample(h, x, z) - 0.03, 3), round(z, 2), round(float(rng.uniform(0, 360)), 1),
                      round(float(rng.uniform(0.5, 1.15)), 2)])
        if len(grass) >= 90000:
            break
    data = dict(trees)
    data.update(under)
    data["grass"] = grass
    (ROOT / "data/zone01_vegetation.json").write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"zone01: деревьев {sum(len(v) for v in trees.values())}, подлеска {sum(len(v) for v in under.values())}")


SPRUCES = ["spruce_forest_a", "spruce_forest_b", "spruce_open", "spruce_young_a", "spruce_young_b"]
# сосна (tools/build_pine.py): тонкие высокие лесные, средние, толстые (укрытие), старая раскидистая, двойная, молодая
PINES = ["pine_young", "pine_slim_a", "pine_slim_b", "pine_forest", "pine_thick", "pine_old", "pine_twin", "pine_yard"]


def pine_radius(key: str) -> float:
    """Радиус ствола на высоте груди — из манифеста build_pine.py (коллизия ствола)."""
    path = ROOT / "assets/zone01/models/pine.json"
    if path.exists():
        return float(json.loads(path.read_text(encoding="utf-8")).get(key, {}).get("trunk_radius", 0.25))
    return 0.25


def add_pines(trees: dict, h: np.ndarray, forest: np.ndarray, inside: np.ndarray, d_rav: np.ndarray) -> None:
    """Сосны поверх готовой раскладки (свой генератор случайных чисел — остальные деревья не сдвигаются):
    в лесу — сосновые рощи пятнами (сухие места), там почти все деревья — сосны, тонкие и высокие с
    толстыми вперемешку; вне рощ — редкие сосны среди елей; на открытом и по бровке оврага —
    раскидистые старые и двойные."""
    rng = np.random.default_rng(97)
    grove = fbm(70.0, 97)
    for key in PINES:
        trees.setdefault(key, [])
    in_forest = ["pine_slim_a"] * 3 + ["pine_slim_b"] * 3 + ["pine_forest"] * 3 + ["pine_thick"] * 2 + ["pine_twin", "pine_young"]
    open_kind = ["pine_old", "pine_old", "pine_yard", "pine_yard", "pine_twin", "pine_thick"]
    for key in list(trees):
        # тополя у насыпи — ряд посадки, их не трогать
        if key in PINES or key.startswith("tree_poplar"):
            continue
        keep = []
        for p in trees[key]:
            x, z = p[0], p[2]
            ix, iz = min(max(int(x - X0), 0), NX - 1), min(max(int(z - Z0), 0), NZ - 1)
            f, g, r = forest[iz, ix], grove[iz, ix], d_rav[iz, ix]
            roll = rng.random()
            new = None
            if f > 0.5 and g > 0.56 and roll < 0.85:
                new = in_forest[int(rng.integers(0, len(in_forest)))]
            elif f > 0.5 and key.startswith("spruce_forest") and roll < 0.12:
                new = in_forest[int(rng.integers(0, len(in_forest)))]
            elif f <= 0.5 and inside[iz, ix] and 4.0 < r < 30.0 and roll < 0.2:
                new = open_kind[int(rng.integers(0, len(open_kind)))]
            elif f <= 0.5 and inside[iz, ix] and r >= 30.0 and roll < 0.35:
                new = open_kind[int(rng.integers(0, len(open_kind)))]
            elif f <= 0.5 and not inside[iz, ix] and g > 0.56 and roll < 0.6:
                new = in_forest[int(rng.integers(0, len(in_forest)))]
            if new:
                trees[new].append(p)
            else:
                keep.append(p)
        trees[key] = keep
    print("zone01: сосен", sum(len(trees[k]) for k in PINES))
BIRCHES = ["birch_a", "birch_b", "birch_c", "birch_bare", "birch_young"]

# подлесок из Poly Haven Nature (tools/build_zone01_undergrowth.py): ключ → (варианты, вид растения)
# лёгкие варианты — их у камеры десятки тысяч
UG_GRASS = ["ug_grass_tall_a", "ug_grass_tall_b", "ug_grass_tall_a", "ug_grass_small", "ug_grass_mid_b", "ug_grass2_c"]
UG_WEEDS = ["ug_weed_a", "ug_weed_b", "ug_dandelion_c", "ug_dandelion_e"]
UG_BUSH = ["ug_bush_a", "ug_bush_b", "ug_bush_c", "ug_bush_d"]
UG_SAPLING = ["ug_sapling_a", "ug_sapling_b", "ug_sapling_c"]
# ключ: (дальность, клетка, тень, оттенок, коллизия ствола)
UG_VIEW = {**{k: (260.0, 48.0, True, (0.82, 0.8, 0.62)) for k in UG_BUSH},
           **{k: (200.0, 48.0, True, (0.78, 0.82, 0.72)) for k in UG_SAPLING}}


def scatter_undergrowth(rng, x0: float, z0: float, x1: float, z1: float, accept, kind_at) -> dict:
    """Подлесок в прямоугольнике: шаг 0.9 м с дрожанием; accept(x, z) — можно ли здесь расти,
    kind_at(x, z, roll) — что растёт (ключ-группа или None). Возвращает ключ модели → точки."""
    out: dict[str, list] = {k: [] for k in UG_GRASS + UG_WEEDS + UG_BUSH + UG_SAPLING}
    groups = {"grass": UG_GRASS, "weed": UG_WEEDS, "bush": UG_BUSH, "sapling": UG_SAPLING}
    scale = {"grass": (1.2, 2.2), "weed": (1.4, 2.6), "bush": (0.8, 1.3), "sapling": (1.0, 2.4)}
    for gz in np.arange(z0, z1, 0.9):
        for gx in np.arange(x0, x1, 0.9):
            x, z = float(gx + rng.uniform(-0.45, 0.45)), float(gz + rng.uniform(-0.45, 0.45))
            if not accept(x, z):
                continue
            kind = kind_at(x, z, float(rng.random()))
            if kind is None or kind in ("grass", "weed"):
                continue
            key = groups[kind][int(rng.integers(0, len(groups[kind])))]
            lo, hi = scale[kind]
            out[key].append([round(x, 2), round(sample(H, x, z) - 0.04, 3), round(z, 2), round(float(rng.uniform(0, 360)), 1),
                             round(float(rng.uniform(lo, hi)), 2)])
    return out


def undergrowth_nodes(s: "Scene", parent: str, data_path: str) -> None:
    script = s.resource("res://src/world/district_scatter.gd", "Script")
    for key, (view, cell, shadow, tint) in UG_VIEW.items():
        s.node(key.title().replace("_", ""), parent, script=script, data_path=data_path, key=key,
               model=f"res://assets/zone01/models/{key}.glb", view_distance=view, cell=cell, shadows=shadow, foliage=True,
               foliage_tint=Raw(f"Color({tint[0]}, {tint[1]}, {tint[2]}, 1)"))


def vegetation_nodes(s: "Scene") -> None:
    script = s.resource("res://src/world/district_scatter.gd", "Script")
    s.node("Vegetation")
    keys = [f"tree_{k}_{v}" for k in ("poplar", "maple") for v in range(3)]
    for key in keys:
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_vegetation.json",
               key=key, model=f"res://assets/zone01/models/{key}.glb", view_distance=550.0, cell=96.0, trunk_radius=0.25)
    for key in SPRUCES + BIRCHES:
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_vegetation.json",
               key=key, model=f"res://assets/zone01/models/{key}.glb", far_model=f"res://assets/zone01/models/{key}_far.glb",
               near_distance=320.0, view_distance=900.0, cell=64.0, trunk_radius=(0.3 if "young" not in key else 0.08) * (0.7 if key.startswith("birch") else 1.0))
    for key in PINES:
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_vegetation.json",
               key=key, model=f"res://assets/zone01/models/{key}.glb", far_model=f"res://assets/zone01/models/{key}_far.glb",
               near_distance=320.0, view_distance=900.0, cell=64.0, trunk_radius=round(pine_radius(key), 3))
    for key, radius, height in (("forest_fern", 0.0, 0.0), ("forest_dry_branches", 0.0, 0.0), ("forest_stump_01", 0.3, 0.6),
                                ("forest_stump_02", 0.3, 0.6), ("forest_dead_trunk", 0.0, 0.0), ("forest_roots", 0.0, 0.0),
                                ("forest_rocks_01", 0.5, 0.8), ("forest_rocks_02", 0.5, 0.8)):
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_vegetation.json",
               key=key, model=f"res://assets/zone01/models/{key}.glb", view_distance=110.0, cell=48.0, trunk_radius=radius,
               trunk_height=height if height > 0 else 4.0)
    undergrowth_nodes(s, "Vegetation", "res://data/zone01_vegetation.json")
    s.node("Grass", "Vegetation", script=s.resource("res://src/world/district_grass.gd", "Script"),
           density_map="res://assets/terrain/zone01_grass.png", origin=v2(X0, Z0),
           models=Raw("PackedStringArray(" + ", ".join(f'"res://assets/zone01/models/{k}.glb"' for k in UG_GRASS) + ")"),
           weed_models=Raw("PackedStringArray(" + ", ".join(f'"res://assets/zone01/models/{k}.glb"' for k in UG_WEEDS) + ")"))


def forest_mask() -> np.ndarray:
    edge = 205.0 + (fbm(50.0, 21) - 0.5) * 30.0
    south = smooth((GZ - edge) / 10.0) * smooth((GX + 270.0) / 25.0) * (1.0 - smooth((GX - 300.0) / 40.0))
    d_hill = np.hypot(GX - HILL[0], GZ - HILL[1])
    hill_ring = smooth((d_hill - 55.0) / 15.0) * (1.0 - smooth((d_hill - 125.0) / 15.0)) * smooth((GZ - 100.0) / 30.0)
    road = 1.0 - (1.0 - smooth((np.abs(GX + 4.0) - 3.0) / 3.0)) * (GZ > 190)
    clear = smooth(rect_distance(52, 168, 158, 212) / 8.0)
    return np.clip(np.maximum(south, hill_ring) * road * clear, 0.0, 1.0)


# ------------------------------------------------------------------ текстуры рельефа

LAYERS = ["leafy_grass", "sparse_grass", "forest_floor", "mud_forest", "rocks_ground_02", "gravel_stones"]
LAYER_TILES = [3.0, 3.0, 2.5, 3.0, 4.0, 2.0]

IMPORT_ARRAY = """[remap]

importer="2d_array_texture"
type="CompressedTexture2DArray"

[deps]

source_file="res://assets/terrain/{name}"

[params]

compress/mode=2
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
slices/horizontal=1
slices/vertical={layers}
"""

IMPORT_SPLAT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/terrain/{name}"

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def build_noise_texture() -> None:
    """Бесшовный шум 1024² (FFT, спектр 1/f^β): 4 независимых канала для шейдера рельефа —
    крупные пятна, смешение выборок, рваные края слоёв, мелкая рябь."""
    n = 1024
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    rng = np.random.default_rng(77)
    chans = []
    for beta, cut in [(2.2, 0.02), (2.0, 0.05), (1.6, 0.2), (1.2, 0.5)]:
        spec = (rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))) / f ** (beta / 2)
        spec[f > cut] *= np.exp(-((f[f > cut] - cut) / cut) * 2)
        field = np.real(np.fft.ifft2(spec))
        field = (field - field.mean()) / (field.std() * 3.0) + 0.5
        chans.append(np.clip(field, 0, 1))
    img = (np.stack(chans, -1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(img, mode="RGBA").save(ROOT / "assets/terrain/zone01_noise.png")
    imp = ROOT / "assets/terrain/zone01_noise.png.import"
    if not imp.exists():
        imp.write_text(IMPORT_SPLAT.format(name="zone01_noise.png"), encoding="utf-8")


def build_layer_arrays() -> None:
    out = ROOT / "assets/terrain"
    out.mkdir(parents=True, exist_ok=True)
    for kind in ["albedo", "normal", "arm"]:
        name = f"zone01_{kind}.jpg"
        tiles = [Image.open(ROOT / "assets/textures" / layer / f"{kind}.jpg").convert("RGB").resize((2048, 2048), Image.LANCZOS)
                 for layer in LAYERS]
        strip = Image.new("RGB", (2048, 2048 * len(tiles)))
        for i, tile in enumerate(tiles):
            strip.paste(tile, (0, 2048 * i))
        strip.save(out / name, quality=93)
        imp = out / (name + ".import")
        if not imp.exists():
            imp.write_text(IMPORT_ARRAY.format(name=name, layers=len(tiles)), encoding="utf-8")


# ------------------------------------------------------------------ запись сцен

class Raw:
    def __init__(self, text: str):
        self.text = text


def gvalue(value) -> str:
    if isinstance(value, Raw):
        return value.text
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return "{" + ", ".join(gvalue(k) + ": " + gvalue(v) for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(gvalue(v) for v in value) + "]"
    if isinstance(value, (float, np.floating)):
        return str(round(float(value), 4))
    return str(value)


def v2(x, z):
    return Raw(f"Vector2({round(x, 4)}, {round(z, 4)})")


def v3(x, y, z):
    return Raw(f"Vector3({round(float(x), 4)}, {round(float(y), 4)}, {round(float(z), 4)})")


class Scene:
    def __init__(self, name: str, root_kind: str = "Node3D"):
        self.resources: dict[str, tuple[str, str]] = {}
        self.subs: list[str] = []
        self.nodes: list[str] = [f'[node name="{name}" type="{root_kind}"]']

    def resource(self, path: str, kind="PackedScene") -> Raw:
        if path not in self.resources:
            self.resources[path] = (str(len(self.resources) + 1), kind)
        return Raw(f'ExtResource("{self.resources[path][0]}")')

    def sub(self, kind: str, **attrs) -> Raw:
        sid = f"{kind}_{len(self.subs) + 1}"
        self.subs.append(f'[sub_resource type="{kind}" id="{sid}"]\n' + "\n".join(k + " = " + gvalue(v) for k, v in attrs.items()))
        return Raw(f'SubResource("{sid}")')

    def node(self, name: str, parent=".", scene=None, kind="Node3D", groups=None, **attrs):
        header = f'[node name="{name}" parent="{parent}"'
        header += f" instance={gvalue(self.resource(scene))}" if scene else f' type="{kind}"'
        if groups:
            header += " groups=" + gvalue(groups)
        header += "]"
        self.nodes.append(header + ("\n" + "\n".join(k + " = " + gvalue(v) for k, v in attrs.items()) if attrs else ""))
        return name if parent == "." else parent + "/" + name

    def save(self, path: Path):
        lines = [f"[gd_scene load_steps={len(self.resources) + len(self.subs) + 1} format=3]", ""]
        for res_path, (index, kind) in self.resources.items():
            lines.append(f'[ext_resource type="{kind}" path="{res_path}" id="{index}"]')
        if self.subs:
            lines += [""] + ["\n\n".join(self.subs)]
        lines += ["", "\n\n".join(self.nodes), ""]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")


H: np.ndarray = np.zeros((1, 1), np.float32)


def ground(x: float, z: float) -> float:
    return sample(H, x, z)


GREY = (0.58, 0.59, 0.6)
DARK = (0.36, 0.37, 0.38)
CONCRETE = (0.62, 0.61, 0.58)
METAL = (0.42, 0.45, 0.46)
RUST = (0.45, 0.33, 0.25)


def box(at, size, color=GREY, collision=True, **kwargs):
    return dict(at=[round(float(v), 3) for v in at], size=[round(float(v), 3) for v in size], color=list(color), collision=collision, **kwargs)


def props(scene: Scene, name, x, z, pieces, parent="Props", yaw=0.0, y=None, surface="concrete"):
    return scene.node(name, parent, "res://scenes/world/urban_props.tscn",
                      position=v3(x, ground(x, z) if y is None else y, z),
                      rotation_degrees=v3(0, yaw, 0), surface=surface,
                      pieces=Raw("Array[Dictionary](" + gvalue(pieces) + ")"))


def building(scene: Scene, name, x, z, w, d, h, parent, yaw=0.0, title="", floors=1, style="service",
             doors=((0.0, -1.0),), y=None, kind=0, **extra):
    base = (ground(x, z) + 0.1) if y is None else y
    path = scene.node(name, parent, "res://scenes/world/blockout_building.tscn",
                      position=v3(x, base, z), rotation_degrees=v3(0, yaw, 0), kind=kind,
                      size=v2(w, d), height=h, simple_collision=True, display_name=title, **extra)
    for i, (along, side) in enumerate(doors):
        scene.node(f"Door_{i}", path, "res://scenes/world/blockout_opening.tscn",
                   position=v3(along * w * 0.5, 0, side * d * 0.5), width=1.6)
    if kind == 0 and floors > 0:
        scene.node("Facade", path, script=scene.resource("res://src/world/urban_facade.gd", "Script"),
                   floors=floors, style=style, window_pitch=4.5)
    return path


SF_MANIFEST = "res://assets/zone01/models/sketchfab.json"


def sf_model(scene: "Scene", name: str, model: str, x: float, z: float, yaw: float = 0.0, parent: str = "Props",
             y: float | None = None, surface: str = "metal", rotation=None) -> str:
    """Модель Sketchfab (tools/import_sketchfab.py) узлом DistrictModel: материалы свои, коллизия из манифеста."""
    rot = rotation if rotation is not None else (0, yaw, 0)
    return scene.node(name, parent, kind="StaticBody3D", script=scene.resource("res://src/world/district_model.gd", "Script"),
                      position=v3(x, ground(x, z) if y is None else y, z), rotation_degrees=v3(*rot),
                      model=f"res://assets/zone01/models/{model}.glb", manifest=SF_MANIFEST, surface=surface, materials_dir="")


def car(scene, name, x, z, yaw=0.0, color=(.45, .51, .57), parent="Props"):
    """Брошенная машина: ВАЗ-2104 (скан), изредка — сгоревшая. Выбор по координатам — стабильный."""
    burned = (int(abs(x) * 7 + abs(z) * 13) % 5) == 0
    sf_model(scene, name, "sf_car_burned" if burned else "sf_vaz2104", x, z, yaw + 90.0, parent)


def truck(scene, name, x, z, yaw=0.0, parent="Props", trailer=True, y=None):
    pieces = [box((0, 1.6, -6.2), (2.5, 2.9, 2.4), (.55, .2, .18), surface="metal"),
              box((0, .7, -3.0), (2.4, .6, 4.0), DARK, surface="metal")]
    if trailer:
        pieces.append(box((0, 2.3, 2.2), (2.5, 2.9, 12.0), (.7, .71, .7), surface="metal"))
        pieces.append(box((0, .55, 2.2), (2.3, .5, 12.0), DARK, False))
    props(scene, name, x, z, pieces, parent, yaw, y=y, surface="metal")


def bus(scene, name, x, z, yaw=0.0, parent="Props"):
    props(scene, name, x, z, [box((0, 1.7, 0), (2.55, 2.9, 11.5), (.78, .62, .3), surface="metal"),
                              box((0, 2.2, 0), (2.6, 1.0, 10.6), (.2, .25, .28), False)], parent, yaw, surface="metal")


def container(scene, name, x, z, yaw=0.0, parent="Props", y=None, color=(.36, .45, .5)):
    props(scene, name, x, z, [box((0, 1.3, 0), (6.06, 2.6, 2.44), color, surface="metal")], parent, yaw, y=y, surface="metal")


def blocks(scene, name, a, b, parent="Props"):
    """Ряд бетонных блоков ФБС поперёк проезда."""
    length = math.dist(a, b)
    n = max(1, int(length / 2.6))
    yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    pieces = [box((-length / 2 + (i + .5) * length / n, .4, 0), (2.3, .8, .9), CONCRETE) for i in range(n)]
    props(scene, name, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, pieces, parent, yaw)


def fence(scene, name, a, b, height=2.2, parent="Props", solid=False, color=(.42, .44, .44)):
    x, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    length = math.dist(a, b)
    yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
    base = ground(x, z)
    pieces = []
    n = max(1, math.ceil(length / 12))
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        samples = [ground(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in (t0, (t0 + t1) / 2, t1)]
        low, high = min(samples) - .4, max(samples) + height
        at = -length / 2 + (i + .5) * length / n
        pieces.append(box((at, (low + high) / 2 - base, 0), (length / n + .03, high - low, .2 if solid else .08),
                          (.6, .6, .58) if solid else color, True, surface="concrete" if solid else "metal"))
    props(scene, name, x, z, pieces, parent, yaw)


# ------------------------------------------------------------------ мир: рельеф, дороги, вода, ж/д

def world_scene() -> None:
    s = Scene("World")
    s.node("Terrain", script=s.resource("res://src/world/district_terrain.gd", "Script"), data_path=SECTOR)
    s.node("Roads")
    for road in ROADS:
        raw = "PackedVector3Array(" + ", ".join(str(v) for p in road["points"] for v in p) + ")"
        s.node(road["id"], "Roads", "res://scenes/world/urban_road.tscn", points=Raw(raw),
               carriage_width=road["width"], sidewalk_width=road["sidewalk"], sidewalks=road["sidewalk"] > 0,
               markings=road["id"] not in ("SiteRoad", "LoadingExit"))
    s.node("Water")
    water = s.resource("res://src/world/district_water.gdshader", "Shader")
    mat = s.sub("ShaderMaterial", shader=water)
    s.subs[-1] += "\nshader_parameter/noise_tex = " + gvalue(s.resource("res://assets/terrain/zone01_noise.png", "Texture2D"))
    # ручей по дну оврага — полосы вдоль русла чуть выше дна
    for i, ((ax, az), (bx, bz)) in enumerate(zip(RAVINE, RAVINE[1:])):
        ya = min(ground(ax, az), ground((ax + bx) / 2, (az + bz) / 2)) + 0.35
        length = math.dist((ax, az), (bx, bz)) + 2.0
        mesh = s.sub("PlaneMesh", size=v2(3.2, length), material=mat)
        s.node(f"Stream_{i}", "Water", kind="MeshInstance3D", mesh=mesh,
               position=v3((ax + bx) / 2, ya, (az + bz) / 2),
               rotation_degrees=v3(0, math.degrees(math.atan2(bx - ax, bz - az)), 0), cast_shadow=0)
    for i, (x0, z0, x1, z1) in enumerate(PONDS):
        mesh = s.sub("PlaneMesh", size=v2(x1 - x0, z1 - z0), material=mat)
        s.node(f"Pond_{i}", "Water", kind="MeshInstance3D", mesh=mesh,
               position=v3((x0 + x1) / 2, 2.2, (z0 + z1) / 2), cast_shadow=0)
    railway(s)
    perimeter(s)
    vegetation_nodes(s)
    s.save(OUT / "zone01_world.tscn")


def railway(s: Scene) -> None:
    """Насыпь (13): два пути по верху, путепровод над проездом (устои, пролёт, ограждение)."""
    s.node("Railway")
    (ax, az), (bx, bz) = RAIL
    yaw = -math.degrees(math.atan2(bz - az, bx - ax))
    length = math.dist(RAIL[0], RAIL[1])
    seg = 40.0
    n = int(length / seg)
    for i in range(n):
        t = (i + .5) / n
        x, z = ax + (bx - ax) * t, az + (bz - az) * t
        if abs(x - OVERPASS_X) < OVERPASS_HALF + seg / 2:
            continue
        pieces = []
        for track in (-2.0, 2.0):
            pieces.append(box((0, .12, track), (seg, .24, 2.6), (.33, .3, .27), False))
            for rail in (-.76, .76):
                pieces.append(box((0, .32, track + rail), (seg, .15, .07), (.38, .33, .29), False, surface="metal"))
        props(s, f"Track_{i}", x, z, pieces, "Railway", yaw, y=RAIL_TOP)
    # пролёт путепровода над проездом
    span = OVERPASS_HALF * 2 + 4
    oz = az + (bz - az) * ((OVERPASS_X - ax) / (bx - ax))
    pieces = [box((0, RAIL_TOP - .6, 0), (span, 1.2, 12.0), CONCRETE),
              box((0, RAIL_TOP + .6, -5.9), (span, 1.2, .25), CONCRETE),
              box((0, RAIL_TOP + .6, 5.9), (span, 1.2, .25), CONCRETE)]
    for track in (-2.0, 2.0):
        for rail in (-.76, .76):
            pieces.append(box((0, RAIL_TOP + .32, track + rail), (span, .15, .07), (.38, .33, .29), False))
    for side in (-1, 1):
        # устои: стенки во весь откос насыпи, проезд между ними
        pieces.append(box((side * (OVERPASS_HALF + .6), RAIL_TOP / 2 - .6, 0), (1.2, RAIL_TOP + 1.2, 30.0), CONCRETE))
    props(s, "OverpassBridge", OVERPASS_X, oz, pieces, "Railway", yaw, y=0.0)


def perimeter(s: Scene) -> None:
    """Невидимая граница по контуру (высота 6 м над землёй); видимые преграды — насыпь, овраг, лес, блоки."""
    s.node("Perimeter")
    poly = BOUNDARY + BOUNDARY[:1]
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        x, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        length = math.dist(a, b)
        yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        low = min(ground(*a), ground(x, z), ground(*b)) - 12
        props(s, f"Wall_{i}", x, z, [box((0, (low + 8) / 2 - ground(x, z) + 4, 0), (length + 1, 20 + 8, .6), GREY, True, render=False)],
              "Perimeter", yaw)


# ------------------------------------------------------------------ блокаут зон

BACKGROUND = [("sf_panel12", -290, -262, 0), ("sf_panel12", -170, -270, 8), ("sf_panel12", 110, -268, -5),
              ("sf_panel12", 250, -262, 3), ("sf_panel5_brutal", -40, -250, 0), ("sf_panel5_brutal", 360, -250, 0),
              ("sf_panel5_brutal", -450, -110, 90), ("sf_panel5_brutal", -452, -40, 92), ("sf_panel12", -450, 60, 88),
              ("sf_panel12", 500, -60, -90), ("sf_panel5_brutal", 495, 60, -90)]


def background(s: "Scene") -> None:
    """Город за границей карты — декорация без входа (за насыпью, оврагом, блокпостом)."""
    s.node("Background")
    for i, (model, x, z, yaw) in enumerate(BACKGROUND):
        sf_model(s, f"Building_{i}", model, x, z, yaw, "Background", y=ground(x, z) - 0.3, surface="concrete")


def blockout_scene() -> None:
    s = Scene("Blockout")
    background(s)
    zone_mall(s)
    zone_parking(s)
    zone_loading(s)
    zone_plaza(s)
    zone_market(s)
    zone_fuel(s)
    zone_garages(s)
    zone_construction(s)
    zone_hill(s)
    zone_substation(s)
    zone_ravine(s)
    zone_checkpoint(s)
    s.save(OUT / "zone01_blockout.tscn")


def zone_root(s: Scene, name: str) -> str:
    s.node(name)
    s.node("Buildings", name)
    s.node("Props", name, groups=["urban_prop_batches"])
    return name


def zone_mall(s: Scene) -> None:
    """ТЦ (1): кольцо Ø175, 4 этажа, атриум под куполом, портал главного входа с севера.
    Владелец перестраивает ТЦ сам — здесь только масса здания и подпорная стенка подиума."""
    z = zone_root(s, "Z01_Mall")
    body = s.sub("CylinderMesh", top_radius=MALL_R, bottom_radius=MALL_R, height=22.5, radial_segments=96, rings=1)
    shape = s.sub("CylinderShape3D", radius=MALL_R, height=22.5)
    mall = s.node("MallMass", z, kind="StaticBody3D", position=v3(0, PODIUM_H + 11.25, 0))
    s.node("Mesh", mall, kind="MeshInstance3D", mesh=body)
    s.node("Shape", mall, kind="CollisionShape3D", shape=shape)
    dome = s.sub("SphereMesh", radius=30.0, height=16.0, radial_segments=64, rings=16, is_hemisphere=True)
    s.node("AtriumDome", z, kind="MeshInstance3D", mesh=dome, position=v3(0, PODIUM_H + 22.5, 0))
    # подпорная стенка подиума (+1.5) по кольцу, проёмы — к порталу и тоннелю
    pieces = []
    for i in range(72):
        a = (i + .5) / 72 * 2 * math.pi
        deg = math.degrees(a)
        if abs(((deg - 270) + 180) % 360 - 180) < 8 or abs(((deg - 90) + 180) % 360 - 180) < 4:
            continue
        x, zz = PODIUM_R * math.cos(a), PODIUM_R * math.sin(a)
        pieces.append(box((x, PODIUM_H / 2 - .2, zz), (PODIUM_R * 2 * math.pi / 72 + .1, PODIUM_H + .5, .4), CONCRETE,
                          rotation=[0, -deg + 90, 0]))
    # мощение подиума — поверх рельефа, кольцо от фасада до стенки
    for i in range(72):
        a = (i + .5) / 72 * 2 * math.pi
        r = (MALL_R + PODIUM_R) / 2
        pieces.append(box((r * math.cos(a), PODIUM_H - .1, r * math.sin(a)), (PODIUM_R * 2 * math.pi / 72 + .2, .2, PODIUM_R - MALL_R + .4),
                          (.5, .5, .48), rotation=[0, -math.degrees(a) + 90, 0], surface="concrete"))
    props(s, "PodiumWall", 0, 0, pieces, z + "/Props", y=0.0)
    # портал главного входа (север) со ступенями на площадь
    props(s, "NorthPortal", 0, -MALL_R - 4, [
        box((0, 4.5, 0), (24, 9.0, 10), (.55, .62, .66)),
        box((0, .4, -9.5), (24, .8, 9), CONCRETE),
    ], z + "/Props", y=PODIUM_H)
    # пожарная лестница на крышу (по документу — выходы на крышу по пожарным лестницам)
    for i, deg in enumerate([200, 340]):
        a = math.radians(deg)
        props(s, f"FireStair_{i}", (MALL_R + 2) * math.cos(a), (MALL_R + 2) * math.sin(a),
              [box((0, 12, 0), (3, 24, 6), METAL, surface="metal")], z + "/Props", -deg + 90, y=PODIUM_H)


def zone_parking(s: Scene) -> None:
    """Паркинг (2): 3 уровня, крыша +7.5 — вровень с 2F ТЦ; крытый мост на 2F."""
    z = zone_root(s, "Z02_Parking")
    building(s, "ParkingDeck", 160, -14, 70, 110, 7.5, z + "/Buildings", title="Паркинг", kind=1,
             doors=(), y=0.15, levels=3, level_height=3.75)
    y2 = PODIUM_H + 6.0
    length = 125 - (MALL_R - 1)
    cx = (125 + MALL_R - 1) / 2
    props(s, "SkyBridge", cx, -4, [
        box((0, y2 - .15, 0), (length, .3, 4.5), CONCRETE),
        box((0, y2 + 3.2, 0), (length, .25, 5.0), METAL, surface="metal"),
        box((0, y2 + .55, -2.2), (length, 1.1, .12), (.5, .6, .65), surface="glass"),
        box((0, y2 + .55, 2.2), (length, 1.1, .12), (.5, .6, .65), surface="glass"),
        box((-length / 2 + 6, y2 / 2, 0), (.8, y2, .8), CONCRETE),
        box((length / 2 - 6, y2 / 2, 0), (.8, y2, .8), CONCRETE),
    ], z + "/Props", y=0.0)
    for i, (x, zz, yaw) in enumerate([(140, -50, 0), (180, -40, 180), (150, 20, 90), (176, 30, 0), (138, 34, 180)]):
        car(s, f"Car_{i}", x, zz, yaw, parent=z + "/Props")


def zone_loading(s: Scene) -> None:
    """Погрузка (3): выемка −4 м, подпорные стены, платформы, фуры, тоннель к ТЦ под кольцевой."""
    z = zone_root(s, "Z03_Loading")
    x0, z0, x1, z1 = PIT
    wall = 4.6
    pieces = []
    for (ax, az, bx, bz) in [(x0, z0, -6, z0), (6, z0, x1, z0), (x1, z0, x1, z1), (x0, z0, x0, z1),
                             (x0, z1, PIT_RAMP[0], z1), (PIT_RAMP[2], z1, x1, z1)]:
        cx, cz = (ax + bx) / 2, (az + bz) / 2
        length = math.dist((ax, az), (bx, bz))
        yaw = 0 if az == bz else 90
        pieces.append(box((cx, PIT_H + wall / 2, cz), (length + .4, wall, .4), CONCRETE, rotation=[0, yaw, 0]))
    # бортики пандуса выезда
    for x in (PIT_RAMP[0] - .2, PIT_RAMP[2] + .2):
        pieces.append(box((x, PIT_H / 2 + .4, (PIT_RAMP[1] + PIT_RAMP[3]) / 2), (.4, -PIT_H + .8, PIT_RAMP[3] - PIT_RAMP[1]), CONCRETE))
    # стенки и перекрытие тоннеля (на нём кольцевая дорога и подиум)
    tx0, tz0, tx1, tz1 = TUNNEL
    for x in (tx0 - .2, tx1 + .2):
        pieces.append(box((x, PIT_H / 2, (tz0 + tz1) / 2), (.4, -PIT_H + .2, tz1 - tz0), CONCRETE))
    pieces.append(box(((tx0 + tx1) / 2, .05, (tz0 + tz1) / 2), (tx1 - tx0 + 1.2, .5, tz1 - tz0 - 2), CONCRETE))
    pieces.append(box(((tx0 + tx1) / 2, PIT_H + 2.6, tz0 + .3), (tx1 - tx0, 5.2, .3), METAL, surface="metal"))
    # пол выемки — бетон
    pieces.append(box(((x0 + x1) / 2, PIT_H - .04, (z0 + z1) / 2), (x1 - x0, .2, z1 - z0), (.45, .45, .44)))
    props(s, "PitStructure", 0, 0, pieces, z + "/Props", y=0.0)
    # погрузочные платформы вдоль северной стены и навес
    props(s, "DockPlatform", -2, z0 + 4, [box((0, .6, 0), (90, 1.2, 8), CONCRETE),
                                          box((0, 6.0, -1), (90, .3, 12), METAL, False, surface="metal")],
          z + "/Props", y=PIT_H)
    for i, x in enumerate([-40, -22, 22, 38]):
        truck(s, f"Truck_{i}", x, z0 + 22, 180, z + "/Props", y=PIT_H)
    container(s, "Container_0", 30, 158, 90, z + "/Props", y=PIT_H)
    container(s, "Container_1", -42, 160, 0, z + "/Props", y=PIT_H, color=(.55, .27, .2))


def zone_plaza(s: Scene) -> None:
    """Площадь (4): остановка, киоски, автобус, брошенные машины, блоки."""
    z = zone_root(s, "Z04_Plaza")
    props(s, "PlazaPaving", 4, -128, [box((0, -.05, 0), (172, .2, 48), (.42, .42, .41))], z + "/Props", y=0.25, surface="asphalt")
    building(s, "BusShelter", 52, -150, 10, 2.4, 2.8, z + "/Buildings", title="", kind=4, doors=())
    bus(s, "Bus", 66, -158.5, 90, z + "/Props")
    for i, (x, zz) in enumerate([(-60, -140), (-46, -140), (-32, -140), (28, -114), (42, -114)]):
        building(s, f"Kiosk_{i}", x, zz, 4, 3, 2.9, z + "/Buildings", floors=0, doors=((0, 1),))
    for i, (x, zz, yaw) in enumerate([(-20, -120, 30), (12, -136, 95), (-70, -116, 160), (78, -126, 10), (-5, -150, 80)]):
        car(s, f"Car_{i}", x, zz, yaw, parent=z + "/Props")
    blocks(s, "Blocks_0", (-10, -158), (10, -158), z + "/Props")
    blocks(s, "Blocks_1", (-40, -110), (-28, -104), z + "/Props")


def zone_market(s: Scene) -> None:
    """Рынок (6): ряды павильонов и контейнеры в 1–2 яруса, узкие проходы, ангар-склад."""
    z = zone_root(s, "Z06_Market")
    props(s, "MarketPaving", -170, 25, [box((0, -.05, 0), (130, .2, 162), (.38, .38, .37))], z + "/Props", y=0.3, surface="asphalt")
    building(s, "Hangar", -192, 6, 24, 42, 9.0, z + "/Buildings", title="Ангар", floors=0, doors=((0, -1), (0, 1)), yaw=0)
    idx = 0
    for row, x in enumerate([-222, -160, -142, -124]):
        for k in range(8):
            zz = -45 + k * 9.5 + (row % 2) * 3
            if x == -160 and -24 < zz < 36:
                continue
            if (row + k) % 3 == 0:
                container(s, f"Container_{idx}", x, zz, 90, z + "/Props", color=[(.36, .45, .5), (.55, .27, .2), (.3, .42, .3)][k % 3])
                if k % 2 == 0:
                    container(s, f"Container_{idx}_top", x, zz, 90, z + "/Props", y=ground(x, zz) + 2.6, color=(.5, .45, .3))
            else:
                building(s, f"Stall_{idx}", x, zz, 6, 4.5, 2.8, z + "/Buildings", floors=0, yaw=90, doors=((0, -1),))
            idx += 1
    for row, zz in enumerate([62, 76, 92]):
        for k in range(7):
            x = -226 + k * 15
            building(s, f"Stall_S{row}_{k}", x, zz, 9, 4.5, 2.8, z + "/Buildings", floors=0, doors=((0, -1),))
    fence(s, "Fence_W", (-236, -55), (-236, 108), parent=z + "/Props")
    fence(s, "Fence_N", (-236, -55), (-108, -55), parent=z + "/Props")


def zone_fuel(s: Scene) -> None:
    """АЗС и шиномонтаж (7) у северной дороги."""
    z = zone_root(s, "Z07_Fuel")
    props(s, "Apron", 230, -126, [box((0, -.05, 0), (100, .2, 40), (.4, .4, .39))], z + "/Props", y=0.2, surface="asphalt")
    building(s, "Canopy", 226, -128, 30, 18, 5.5, z + "/Buildings", title="АЗС", kind=3, doors=())
    for i, x in enumerate([216, 226, 236]):
        props(s, f"Pump_{i}", x, -128, [box((0, .15, 0), (1.2, .3, 6), CONCRETE), box((0, 1.1, -1.5), (.8, 1.9, .5), (.75, .2, .15)),
                                       box((0, 1.1, 1.5), (.8, 1.9, .5), (.75, .2, .15))], z + "/Props")
    building(s, "Shop", 196, -130, 14, 9, 4.0, z + "/Buildings", title="Магазин АЗС", floors=1, doors=((0, 1),))
    building(s, "TyreShop", 262, -124, 16, 11, 4.5, z + "/Buildings", title="Шиномонтаж", floors=1,
             doors=((-.4, 1), (.3, 1)))
    car(s, "Car_0", 248, -112, 70, parent=z + "/Props")
    car(s, "Car_1", 208, -112, 0, parent=z + "/Props")


def zone_garages(s: Scene) -> None:
    """Гаражный кооператив (8): три ряда кирпичных боксов на склоне — уступами по 4 бокса."""
    z = zone_root(s, "Z08_Garages")
    for row, x in enumerate([268, 290, 312]):
        for seg in range(5):
            zz = -92 + seg * 22 + 11
            sf_model(s, f"Row{row}_Block{seg}", "sf_garage_row", x, zz, 180.0 if row % 2 else 0.0, z + "/Buildings",
                     y=ground(x, zz) - .05, surface="concrete")
    props(s, "GarageGateL", 262, -98, [box((0, 1, 0), (.2, 2, 8), METAL, surface="metal")], z + "/Props")
    fence(s, "Fence_E", (325, -100), (325, 20), parent=z + "/Props", solid=True)


def zone_construction(s: Scene) -> None:
    """Недострой 9 этажей (9) — каркас без стен наверху; башенный кран 30 м; бытовки."""
    z = zone_root(s, "Z09_Construction")
    cx, cz, w, d, floor_h = 236, 96, 36, 22, 3.0
    base = ground(cx, cz) + .1
    pieces = []
    for f in range(10):
        y = f * floor_h
        hole = f >= 7
        pieces.append(box((0, y, 0), (w if not hole else w * .7, .25, d), CONCRETE))
        if f == 9:
            break
        for ix in range(5):
            for iz in range(3):
                px, pz = -w / 2 + .4 + ix * (w - .8) / 4, -d / 2 + .4 + iz * (d - .8) / 2
                pieces.append(box((px, y + floor_h / 2, pz), (.45, floor_h, .45), CONCRETE))
        if f < 3:
            pieces.append(box((0, y + floor_h / 2, d / 2 - .15), (w - 4, floor_h, .3), (.58, .45, .4)))
    # лестничное ядро
    pieces.append(box((w / 2 - 3.5, 13.5, 0), (5, 27, 6), (.55, .55, .53)))
    props(s, "Frame", cx, cz, pieces, z + "/Props", y=base)
    crane_x, crane_z = 262, 80
    props(s, "TowerCrane", crane_x, crane_z, [
        box((0, 15, 0), (2, 30, 2), (.85, .7, .15), surface="metal"),
        box((12, 30.6, 0), (44, 1.2, 1.2), (.85, .7, .15), surface="metal"),
        box((-9, 30.6, 0), (14, 1.2, 1.6), (.85, .7, .15), surface="metal"),
        box((-14, 29.5, 0), (3, 2.5, 3), CONCRETE),
        box((1.6, 28.8, 0), (2.2, 2.2, 2.2), (.8, .75, .6), surface="metal"),
        box((0, .5, 0), (6, 1, 6), CONCRETE),
    ], z + "/Props", yaw=-25)
    for i, (x, zz, yaw) in enumerate([(206, 116, 0), (206, 104, 0), (276, 122, 90), (212, 76, 0)]):
        building(s, f"Cabin_{i}", x, zz, 6, 2.5, 2.6, z + "/Buildings", floors=0, yaw=yaw, doors=((0, -1),))
    fence(s, "SiteFence_S", (198, 132), (282, 132), parent=z + "/Props")
    fence(s, "SiteFence_W", (198, 70), (198, 132), parent=z + "/Props")


def zone_hill(s: Scene) -> None:
    """Холм (10) +16: мачта ретранслятора 25 м, аппаратная, старый дот, забор вокруг вершины."""
    z = zone_root(s, "Z10_Hill")
    top = HILL_H
    building(s, "Mast", 378, 176, 4, 4, 25, z + "/Buildings", title="Ретранслятор", kind=2, doors=(), y=top)
    building(s, "EquipmentShelter", 356, 184, 6, 4, 3.0, z + "/Buildings", title="Аппаратная", floors=1, doors=((0, -1),), y=top + .05)
    props(s, "Pillbox", 350, 202, [box((0, .9, 0), (6, 2.2, 6), CONCRETE), box((0, 1.1, -3.05), (2.0, .3, .2), (.1, .1, .1), False)],
          z + "/Props", yaw=200)
    for i, (a, b) in enumerate([((347, 162), (385, 162)), ((385, 162), (385, 206)), ((385, 206), (357, 206)), ((347, 162), (347, 178))]):
        fence(s, f"Fence_{i}", a, b, parent=z + "/Props")


def zone_substation(s: Scene) -> None:
    """Подстанция (11) за забором и два отстойника на насыпи +3 м."""
    z = zone_root(s, "Z11_Substation")
    x0, z0, x1, z1 = 64, 108, 152, 166
    for i, (a, b) in enumerate([((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0 + 10))]):
        fence(s, f"Fence_{i}", a, b, height=2.6, parent=z + "/Props")
    building(s, "ControlRoom", 76, 156, 16, 8, 4.0, z + "/Buildings", title="Щитовая", floors=1, doors=((0, -1),))
    for i in range(4):
        props(s, f"Transformer_{i}", 92 + i * 15, 128, [box((0, 1.6, 0), (4, 3.2, 3), (.38, .42, .38), surface="metal"),
                                                     box((0, 4.2, 0), (3, 2, .4), METAL, False, surface="metal")], z + "/Props")
    for i in range(6):
        props(s, f"Portal_{i}", 84 + i * 12, 146, [box((0, 5, 0), (.4, 10, .4), METAL, surface="metal"),
                                                  box((0, 9.6, 0), (.3, .3, 8), METAL, False, surface="metal")], z + "/Props")
    for i, (px0, pz0, px1, pz1) in enumerate(PONDS):
        pieces = []
        for (ax, az, bx, bz) in [(px0, pz0, px1, pz0), (px1, pz0, px1, pz1), (px1, pz1, px0, pz1), (px0, pz1, px0, pz0)]:
            yaw = 0 if az == bz else 90
            pieces.append(box(((ax + bx) / 2, 1.8, (az + bz) / 2), (math.dist((ax, az), (bx, bz)) + .4, 2.6, .4), CONCRETE,
                              rotation=[0, yaw, 0]))
        props(s, f"PondWalls_{i}", 0, 0, pieces, z + "/Props", y=0.6)
    fence(s, "PondsFence_N", (56, 172), (154, 172), parent=z + "/Props")
    fence(s, "PondsFence_S", (56, 208), (154, 208), parent=z + "/Props")


def zone_ravine(s: Scene) -> None:
    """Овраг (12): металлический ферменный мост на западе, три частных дома с огородами."""
    z = zone_root(s, "Z12_Ravine")
    by = ground(-372, 38)
    length = 58
    props(s, "Bridge", -343, 37, [
        box((0, 0, 0), (length, .3, 3.2), (.4, .38, .35), surface="metal"),
        box((0, 1.1, -1.65), (length, 2.2, .15), RUST, surface="metal"),
        box((0, 1.1, 1.65), (length, 2.2, .15), RUST, surface="metal"),
        box((0, -4.5, 0), (1.2, 9, 1.2), RUST, surface="metal"),
    ], z + "/Props", yaw=-4, y=by + .2)
    for i, (hx, hz, yaw) in enumerate([(-270, 3, 10), (-297, 25, -15), (-272, 50, 5)]):
        building(s, f"House_{i}", hx, hz, 8, 9, 5.2, z + "/Buildings", title="" if i else "Частные дома", floors=1,
                 style="residential", yaw=yaw, doors=((-.3, 1),))
        building(s, f"Shed_{i}", hx + 7, hz + 7, 3, 4, 2.4, z + "/Buildings", floors=0, yaw=yaw, doors=((0, 1),))
        fence(s, f"Fence_{i}", (hx - 10, hz + 12), (hx + 11, hz + 12), height=1.5, parent=z + "/Props", color=(.4, .33, .25))


def zone_checkpoint(s: Scene) -> None:
    """Блокпост (14) на восточной въездной дороге: будка, вышка 6 м, шлагбаум, блоки."""
    z = zone_root(s, "Z14_Checkpoint")
    building(s, "Booth", 404, 18, 3, 3, 2.7, z + "/Buildings", title="Блокпост", floors=0, doors=((0, 1),))
    props(s, "Tower", 416, 14, [box((-1.4, 3, -1.4), (.2, 6, .2), METAL), box((1.4, 3, -1.4), (.2, 6, .2), METAL),
                                box((-1.4, 3, 1.4), (.2, 6, .2), METAL), box((1.4, 3, 1.4), (.2, 6, .2), METAL),
                                box((0, 6, 0), (3.4, .2, 3.4), (.4, .38, .3)), box((0, 7.3, 0), (3.6, 2.6, 3.6), (.42, .4, .32), False),
                                box((0, 8.7, 0), (4, .2, 4), METAL, False)], z + "/Props", surface="metal")
    props(s, "Barrier", 398, 26, [box((0, .55, 0), (.4, 1.1, .4), (.8, .2, .15)), box((0, 1.0, 4.5), (.12, .12, 9), (.9, .9, .85), False)],
          z + "/Props")
    blocks(s, "Blocks_0", (388, 20), (388, 31), z + "/Props")
    blocks(s, "Blocks_1", (420, 30), (420, 40), z + "/Props")


# ------------------------------------------------------------------ двор (5): заглушка, если детальной сцены ещё нет

def yard_placeholder() -> None:
    path = OUT / "zone01_yard05.tscn"
    if path.exists():
        return
    s = Scene("Yard05")
    s.node("Buildings")
    for i, (x, z, w, d) in enumerate([(-212, -138, 60, 12), (-154, -114, 12, 60), (-238, -85, 12, 60)]):
        building(s, f"Khrushchevka_{i}", x, z, w, d, 15.0, "Buildings", title="Хрущёвка", floors=5, style="residential",
                 doors=((-.6, 1), (-.2, 1), (.2, 1), (.6, 1)) if w > d else ((1, -.6), (1, -.2), (1, .2), (1, .6)))
    s.save(path)


# ------------------------------------------------------------------ данные сектора и главная сцена

SPAWNS = [("Пролом у насыпи", -249, -176), ("Гаражи", 292, -136), ("Тропа в овраге", -344, 81), ("Лесополоса", -114, 282)]
EXTRACTS = [("Путепровод", 0, -206, ""), ("Мост через овраг", -386, 40, ""), ("Лесная дорога", 2, 292, ""),
            ("Блокпост", 432, 26, "За плату или по условию"), ("Погрузка ТЦ", -5, 186, "Машина — по контракту")]
AI_POINTS = [(-200, -95), (-170, 20), (-150, 80), (0, -128), (160, -14), (230, -126), (290, -40), (236, 96),
             (365, 190), (108, 137), (-5, 140), (-280, 30), (-100, 250), (200, 230)]
ROOMS = [("yard05", "Двор хрущёвок", (-228, -126, -160, -55)), ("market", "Рынок", (-232, -50, -110, 105)),
         ("plaza", "Площадь у ТЦ", (-80, -152, 90, -106)), ("parking", "Паркинг", (126, -66, 194, 38)),
         ("fuel", "АЗС", (180, -144, 280, -106)), ("garages", "Гаражи", (260, -96, 320, 14)),
         ("construction", "Недострой", (200, 72, 280, 128)), ("hill", "Холм", (348, 164, 384, 204)),
         ("substation", "Подстанция", (66, 110, 150, 164)), ("loading", "Погрузка", (-52, 116, 46, 164)),
         ("houses", "Дома у оврага", (-300, -8, -262, 60)), ("checkpoint", "Блокпост", (392, 12, 430, 42))]


def main_scene() -> None:
    s = Scene("Zone01_Mall")
    s.nodes[0] += "\nscript = " + gvalue(s.resource("res://src/world/sector_level.gd", "Script")) + f'\nsector_path = "{SECTOR}"'
    s.node("World", scene="res://scenes/levels/zone01/zone01_world.tscn")
    s.node("Blockout", scene="res://scenes/levels/zone01/zone01_blockout.tscn")
    s.node("Yard05", scene="res://scenes/levels/zone01/zone01_yard05.tscn")
    s.node("Gameplay")
    for i, (title, x, z) in enumerate(SPAWNS):
        s.node(f"Entry_{i}", "Gameplay", "res://scenes/world/spawn_point.tscn", position=v3(x, ground(x, z) + .15, z),
               display_name=title, entry=True)
    for i, (title, x, z, rule) in enumerate(EXTRACTS):
        attrs = dict(position=v3(x, ground(x, z) + .08, z), display_name=title, radius=6.0)
        if rule:
            attrs["rule"] = rule
        s.node(f"Extraction_{i}", "Gameplay", "res://scenes/world/extraction_point.tscn", **attrs)
    s.node("AI_Spawns", "Gameplay")
    for i, (x, z) in enumerate(AI_POINTS, 1):
        s.node(f"AI_Spawn_{i:02}", "Gameplay/AI_Spawns", kind="Marker3D", groups=["ai_spawn_points"],
               position=v3(x, ground(x, z) + .2, z))
    s.node("Navigation")
    s.node("Audio")
    s.node("Lighting")
    s.node("WorldEnvironment", kind="WorldEnvironment",
           environment=s.resource("res://scenes/levels/zone01/zone01_environment.tres", "Environment"))
    # мягкая полутень (солнце за облачностью — угловой размер больше настоящего)
    s.node("Sun", kind="DirectionalLight3D", rotation_degrees=v3(-21, -128, 0),
           light_color=Raw("Color(1, 0.88, 0.76, 1)"), light_energy=2.2, light_angular_distance=2.5, shadow_enabled=True,
           shadow_blur=2.5, directional_shadow_max_distance=260.0, light_volumetric_fog_energy=1.6)
    s.node("CameraRig", scene="res://scenes/player/camera_rig.tscn")
    s.node("HUD", kind="CanvasLayer")
    s.node("Root", "HUD", kind="Control", layout_mode=3, anchors_preset=15, anchor_right=1.0, anchor_bottom=1.0,
           grow_horizontal=2, grow_vertical=2, mouse_filter=2)
    s.node("Status", "HUD/Root", kind="Label", offset_left=24.0, offset_top=20.0, offset_right=700.0, offset_bottom=48.0, text="HP 100")
    s.node("Dead", "HUD/Root", kind="Label", visible=False)
    s.save(ROOT / "scenes/levels/zone01_mall.tscn")
    # «картинка» карты: приглушённые цвета, мягкий контраст, воздушная дымка вдаль (объёмный туман
    # с рассеянием солнца), мягкие тени и затенение в углах (SSAO/SSIL), лёгкое свечение светлого
    (OUT / "zone01_environment.tres").write_text("""[gd_resource type="Environment" load_steps=3 format=3]

[sub_resource type="PhysicalSkyMaterial" id="sky_material"]
rayleigh_coefficient = 2.6
mie_coefficient = 0.012
mie_color = Color(0.86, 0.8, 0.72, 1)
turbidity = 9.0
ground_color = Color(0.22, 0.22, 0.19, 1)

[sub_resource type="Sky" id="sky"]
sky_material = SubResource("sky_material")

[resource]
resource_local_to_scene = true
background_mode = 2
sky = SubResource("sky")
ambient_light_source = 3
ambient_light_color = Color(0.6, 0.64, 0.7, 1)
ambient_light_sky_contribution = 1.0
ambient_light_energy = 1.0
tonemap_mode = 4
tonemap_exposure = 0.95
ssao_enabled = true
ssao_radius = 1.2
ssao_intensity = 1.6
ssao_power = 1.2
ssao_detail = 0.5
ssao_light_affect = 0.0
ssil_enabled = true
ssil_radius = 8.0
ssil_intensity = 1.2
sdfgi_enabled = true
sdfgi_use_occlusion = true
sdfgi_cascades = 4
sdfgi_min_cell_size = 0.4
sdfgi_energy = 1.2
sdfgi_normal_bias = 1.4
sdfgi_probe_bias = 1.4
glow_enabled = true
glow_intensity = 0.3
glow_bloom = 0.03
glow_hdr_threshold = 1.1
glow_blend_mode = 1
fog_enabled = true
fog_mode = 1
fog_light_color = Color(0.66, 0.69, 0.72, 1)
fog_density = 0.55
fog_depth_begin = 25.0
fog_depth_end = 900.0
fog_depth_curve = 1.35
fog_aerial_perspective = 0.85
fog_sky_affect = 0.35
volumetric_fog_enabled = true
volumetric_fog_density = 0.0007
volumetric_fog_albedo = Color(0.8, 0.82, 0.85, 1)
volumetric_fog_anisotropy = 0.6
volumetric_fog_length = 140.0
volumetric_fog_detail_spread = 2.0
volumetric_fog_gi_inject = 0.0
volumetric_fog_ambient_inject = 0.0
volumetric_fog_sky_affect = 0.0
adjustment_enabled = true
adjustment_brightness = 1.0
adjustment_contrast = 0.94
adjustment_saturation = 0.82
""", encoding="utf-8")


def write_definition(h: np.ndarray) -> None:
    rooms = []
    for rid, title, (x0, z0, x1, z1) in ROOMS:
        rooms.append(dict(id="zone01_" + rid, name=title, type="yard", rect=[x0, z0, x1, z1],
                          y=round(ground((x0 + x1) / 2, (z0 + z1) / 2), 3), outdoor=True))
    area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(BOUNDARY, BOUNDARY[1:] + BOUNDARY[:1]))) / 2
    x, z = SPAWNS[0][1], SPAWNS[0][2]
    result = dict(
        id="zone01_mall", name="Зона 1 · Район ТЦ", layout="cartesian_scene", greybox=True,
        bounds=[X0, Z0, X0 + (NX - 1) * STEP, Z0 + (NZ - 1) * STEP], boundary=BOUNDARY, area_m2=area,
        units="metres", north="-Z", spawn=[x, round(ground(x, z) + .2, 3), z], camera_yaw=180,
        nav_cache="res://data/navigation/zone01",
        # свет: больше рассеянного неба, солнце мягче — тени читаются, свет не «выжигает»
        light=dict(ambient_k=1.9, sun_k=0.8, ambient_k_dusk=1.9, ambient_k_day_rain=2.4, ambient_k_dusk_rain=2.4, ambient_k_night_rain=4.2, ambient_k_night_fog=2.2),
        # небо: пасмурное утро Nqweba Dawn (Poly Haven, CC0) на дневные рейды — его размытое солнце
        # на высоте ~48°, как у дневного солнца рейда; sun_u — где оно на панораме (доля ширины)
        # horizon_cut — ниже 18° на панораме склоны и горы: их заменяет небо над ними и дымка
        # небо (Poly Haven, CC0, только небо): по времени суток и «время_погода»; солнце панорамы
        # совмещается с игровым по assets/sky/sky_info.json; veil — сколько пелены погоды добавить
        sky_hdri=dict(
            day=dict(a="res://assets/sky/kloppenheim_03_puresky.hdr", exposure=1.0, sun_k=0.9, haze=0.35),
            day_rain=dict(a="res://assets/sky/kloofendal_overcast_puresky.hdr", exposure=0.9, sun_k=0.0, veil=0.8, haze=0.55),
            day_fog=dict(a="res://assets/sky/kloofendal_overcast_puresky.hdr", exposure=1.05, sun_k=0.2, veil=0.4, haze=0.6),
            dusk=dict(a="res://assets/sky/kloppenheim_06_puresky.hdr", exposure=1.0, sun_k=1.0, haze=0.4),
            dusk_rain=dict(a="res://assets/sky/kloppenheim_01_puresky.hdr", exposure=0.9, sun_k=0.0, veil=0.8, haze=0.55),
            dusk_fog=dict(a="res://assets/sky/kloppenheim_01_puresky.hdr", exposure=1.05, sun_k=0.22, veil=0.4, haze=0.6),
        ),
        terrain=dict(heights="res://data/terrain/zone01_heights.r32", origin=[X0, Z0], grid=[NX, NZ], step=STEP,
                     layer_tiles=LAYER_TILES, layers=LAYERS,
                     textures=dict(albedo_array="res://assets/terrain/zone01_albedo.jpg",
                                   normal_array="res://assets/terrain/zone01_normal.jpg",
                                   arm_array="res://assets/terrain/zone01_arm.jpg",
                                   splat="res://assets/terrain/zone01_splat.png",
                                   noise="res://assets/terrain/zone01_noise.png")),
        rooms=rooms, roads=ROADS,
        districts=[dict(id=r[0], name=r[1], rect=list(r[2])) for r in ROOMS],
        heights=dict(rail_top=RAIL_TOP, ravine_depth=RAVINE_DEPTH, hill=HILL_H, pit=PIT_H, podium=PODIUM_H, ponds=PONDS_H),
    )
    (ROOT / "data/sectors/zone01_mall.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"zone01: площадь {area:.0f} м2, высоты {h.min():.1f}..{h.max():.1f} м, дорог {len(ROADS)}")


def main() -> None:
    global H
    OUT.mkdir(parents=True, exist_ok=True)
    H = build_heights()
    (ROOT / "data/terrain").mkdir(parents=True, exist_ok=True)
    H.astype("<f4").tofile(ROOT / "data/terrain/zone01_heights.r32")
    splat = build_splat(H)
    (ROOT / "assets/terrain").mkdir(parents=True, exist_ok=True)
    Image.fromarray(splat, mode="RGBA").save(ROOT / "assets/terrain/zone01_splat.png")
    imp = ROOT / "assets/terrain/zone01_splat.png.import"
    if not imp.exists():
        imp.write_text(IMPORT_SPLAT.format(name="zone01_splat.png"), encoding="utf-8")
    build_layer_arrays()
    build_noise_texture()
    build_vegetation(H, splat)
    world_scene()
    blockout_scene()
    yard_placeholder()
    main_scene()
    write_definition(H)
    # превью высот для документации
    norm = (H - H.min()) / (H.max() - H.min())
    Image.fromarray((norm * 255).astype(np.uint8)).save(ROOT / "docs/plans/zone01_heights.png")


if __name__ == "__main__":
    main()
