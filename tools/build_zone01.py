"""Зона 1 «Городской пояс» (бывший «Район ТЦ»): рельеф, маска поверхностей и каркас карты по схеме
docs/design/zone01_outskirts.md (решение владельца 2026-10-15: ТЦ — отдельная карта, зона 1 — окраина
с болотом, ж/д насыпью на востоке, речкой на севере). Готовые двор, рынок и дома у оврага стоят на
прежних координатах; шум рельефа для них считается на прежней сетке — их земля не сдвигается.
Новых построек-коробок здесь нет: недостающее делается отдельными моделями в Blender.

Использование: python tools/build_zone01.py
Пишет:
  data/terrain/zone01_heights.r32          карта высот (float32, 1 м), её читает DistrictTerrain
  assets/terrain/zone01_splat.png          маска поверхностей R грязь, G камень, B щебень, A листва
  assets/terrain/zone01_{albedo,normal,arm}.jpg  массивы слоёв рельефа (6 слоёв, полосой)
  data/sectors/zone01_mall.json            данные сектора (границы, точки, дороги, растительность)
  scenes/levels/zone01_mall.tscn           главная сцена уровня
  scenes/levels/zone01/zone01_world.tscn   рельеф, дороги, вода (ручей, болото, речка), периметр
  scenes/levels/zone01/zone01_blockout.tscn  готовые сцены рынка и домов, гаражи у путей, город за границей
  scenes/levels/zone01/zone01_yard05.tscn  двор с хрущёвками — ТОЛЬКО если файла ещё нет
                                           (детальную зону 5 собирает tools/build_zone01_yard.py)

Случайного размещения во время игры нет: план задан координатами здесь, шум — с фиксированным
зерном. Повторный запуск перезаписывает мир и блокаут (ручные правки этих двух сцен пропадут).
Оси: X — восток, Z — юг (север = -Z), 1 единица = 1 м. Начало координат — центр бывшего ТЦ.
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
# Прежняя сетка (до 2026-10-15). Шум рельефа считается на ней: двор, рынок и дома у оврага стоят на
# земле, посчитанной этим шумом, и не должны сдвинуться. Новая сетка шире на север (болото, речка,
# лес за ними); к северному краю прежней сетки прежний шум плавно переходит в новый (BLEND_M).
OLD_X0, OLD_Z0, OLD_NX, OLD_NZ = -480.0, -300.0, 1011, 640
BLEND_M = 60.0
X0, Z0, NX, NZ = -480.0, -440.0, 1011, 780
STEP = 1.0
xs = X0 + np.arange(NX) * STEP
zs = Z0 + np.arange(NZ) * STEP
GX, GZ = np.meshgrid(xs, zs)
RNG = np.random.default_rng(20261007)

# граница игровой области (схема docs/design/zone01_outskirts_concept.png; z = −Y схемы)
BOUNDARY = [
    [-395, 300], [-170, 312], [140, 305], [262, 300], [272, 120], [276, -130], [258, -325],
    [40, -342], [-210, -338], [-370, -330], [-405, -160], [-410, 80],
]

# ж/д насыпь вдоль востока: одна линия, у станции — станционные пути; под «улицей к ТЦ» — проём
# под будущий мост (модель моста — отдельно, в Blender)
RAIL = [(217.0, -470.0), (217.0, -120.0), (213.0, 60.0), (195.0, 200.0), (185.0, 320.0), (181.0, 460.0)]
STATION_TRACKS = [(210.0, 70.0), (200.0, 150.0), (188.0, 235.0)]
RAIL_TOP = 3.0
RAIL_HALF = 3.5
STATION_HALF = 7.0
RAIL_SLOPE = 6.5
RAIL_GAP_Z = -60.0     # проём насыпи над «улицей к ТЦ»
RAIL_GAP_HALF = 8.0

# овраг (12): ось русла с севера на юг, глубина 10 м — как был; теперь его исток — болото
RAVINE = [(-305, -176), (-312, -140), (-318, -108), (-334, -70), (-345, -36), (-343, 4),
          (-340, 38), (-326, 66), (-310, 90), (-276, 112), (-240, 132), (-208, 158),
          (-190, 182), (-196, 214), (-214, 250), (-232, 280)]
RAVINE_DEPTH = 10.0
RAVINE_BOTTOM = 3.0
RAVINE_TOP = 22.0

# болото (1): топь ниже улиц, кочки над водой, окна открытой воды
SWAMP = [(-288, -184), (-250, -200), (-180, -188), (-120, -205), (-60, -197), (0, -214), (20, -250),
         (5, -290), (-60, -304), (-150, -296), (-240, -300), (-282, -284), (-298, -235)]
SWAMP_FLOOR = -1.7
SWAMP_WATER = -1.15
SWAMP_EDGE = 14.0

# речка из болота на восток, под насыпью — дальше за карту
RIVER = [(8.0, -292.0), (60.0, -300.0), (130.0, -307.0), (200.0, -301.0), (250.0, -313.0), (300.0, -321.0),
         (380.0, -334.0), (530.0, -350.0)]
RIVER_BOTTOM = -2.3
RIVER_WATER = -1.55
RIVER_HALF = 3.0
RIVER_BANK = 9.0

# площадки под участки (x0, z0, x1, z1, высота, откос, доля исходного рельефа); постройки на них —
# отдельными моделями, пока пусто
PADS = [
    ((-282, -160, -132, -44), 0.35, 10.0, 0.5),   # двор хрущёвок (5) — как был
    ((-238, -58, -104, 112), 0.25, 8.0, 0.0),      # рынок (6) — как был
    ((-92, -150, -24, -72), 0.3, 8.0, 0.3),        # второй двор (панельки) — между улицами, не задевая их ось
    ((30, -236, 165, -92), 0.3, 8.0, 0.3),         # недострой
    ((25, -45, 152, 35), 0.25, 6.0, 0.0),          # спортплощадка
    ((160, -45, 198, -15), 0.3, 6.0, 0.0),         # АЗС
    ((-94, 97, 60, 215), 0.2, 8.0, 0.0),           # автостанция
    ((118, 95, 186, 240), 0.3, 6.0, 0.0),          # привокзальная площадь
    ((176, -232, 205, -108), None, 6.0, 0.0),      # гаражи у путей — на своей высоте
]
HOUSES = [(-270, 3), (-297, 25), (-272, 50)]

ROADS: list[dict] = []
ROAD_DEFS = [
    # имя, точки, ширина проезжей части, тротуар, грунтовка (без асфальта — только колея по маске)
    ("NorthRoad", [(-272, -164), (-100, -164), (-10, -164)], 9.0, 2.5, False),
    ("WestLink", [(-100, -164), (-100, -60), (-100, -14)], 8.0, 2.0, False),
    ("Prospekt", [(-10, -164), (-10, -60), (-10, 40), (-10, 97)], 9.0, 2.5, False),
    ("MallStreet", [(-94, -60), (-10, -60), (100, -60), (190, -60), (300, -60), (420, -60)], 9.0, 2.0, False),
    ("StationRoad", [(-10, 70), (60, 72), (115, 90), (140, 118)], 7.0, 1.5, False),
    ("BridgeRoad", [(-10, -164), (25, -182), (25, -262), (58, -292), (60, -360)], 7.0, 0.0, False),
    ("ForestRoad", [(-276, -168), (-272, -195), (-318, -240), (-340, -300), (-356, -362)], 4.5, 0.0, True),
]

# ------------------------------------------------------------------ помощники numpy


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _noise_grid(cell: float, seed: int, nx: int, nz: int) -> np.ndarray:
    """Плавный шум 0..1 с размером пятна ~cell метров (бикубическое растяжение решётки)."""
    rng = np.random.default_rng(seed)
    w = int(math.ceil(nx * STEP / cell)) + 2
    h = int(math.ceil(nz * STEP / cell)) + 2
    small = Image.fromarray(rng.random((h, w)).astype(np.float32), mode="F")
    big = small.resize((int(w * cell / STEP), int(h * cell / STEP)), Image.BICUBIC)
    arr = np.asarray(big, dtype=np.float32)[:nz, :nx]
    return np.clip(arr, 0.0, 1.0)


def noise(cell: float, seed: int) -> np.ndarray:
    """Шум на новой сетке. Внутри прежней — прежние значения (земля готовых кусков не сдвигается);
    к её северному краю на BLEND_M метрах плавно переходит в шум новой сетки."""
    old = _noise_grid(cell, seed, OLD_NX, OLD_NZ)
    out = _noise_grid(cell, seed + 7919, NX, NZ)
    row = int(round((OLD_Z0 - Z0) / STEP))
    col = int(round((OLD_X0 - X0) / STEP))
    w = smooth((zs[row:row + OLD_NZ] - OLD_Z0) / BLEND_M)[:, None].astype(np.float32)
    window = out[row:row + OLD_NZ, col:col + OLD_NX]
    out[row:row + OLD_NZ, col:col + OLD_NX] = old * w + window * (1.0 - w)
    return out


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

def polygon_edge_distance(poly) -> np.ndarray:
    """Расстояние до контура многоугольника (для плавного края болота)."""
    d, _ = polyline_distance(list(poly) + [poly[0]])
    return d


def build_heights() -> np.ndarray:
    undulation = (fbm(140.0, 1) - 0.5) * 2.0 + (fbm(45.0, 2) - 0.5) * 0.7
    h = undulation.astype(np.float32)
    detail = fbm(18.0, 3)

    # площадки (что ниже приоритетом — раньше); двор и рынок — первыми, как было
    for (x0, z0, x1, z1), height, fall, keep in PADS:
        if height is None:
            height = float(h[int((z0 + z1) / 2 - Z0), int((x0 + x1) / 2 - X0)])
        h = flatten(h, rect_distance(x0, z0, x1, z1), height, fall, keep, detail)
    # фон за границей: ровные площадки под панельки
    for x0, z0, x1, z1 in PADS_BG:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        h = flatten(h, rect_distance(x0 - 3, z0 - 3, x1 + 3, z1 + 3), float(h[int(cz - Z0), int(cx - X0)]), 10.0)
    # частные дома у оврага (12)
    for hx, hz in HOUSES:
        h = flatten(h, rect_distance(hx - 10, hz - 9, hx + 10, hz + 9), float(h[int(hz - Z0), int(hx - X0)]), 6.0)
    # место бывшего ТЦ — ровное, как было (на нём держатся край рынка и улица у него)
    d_c = np.hypot(GX, GZ)
    h = flatten(h, np.maximum(d_c - 109.0, 0.0), 0.2, 8.0)
    # низины поднять до нуля — так было всегда (прежняя насыпь делала это попутно), на этом стоят
    # двор, рынок и дома; болото и речка врезаются уже после
    h = np.maximum(h, 0.0)

    # болото (1): чаша к дну SWAMP_FLOOR с плавным краем; кочки и гряды выше воды, окна воды ниже
    inside = inside_polygon(SWAMP)
    edge = polygon_edge_distance(SWAMP)
    t = np.where(inside, smooth(edge / SWAMP_EDGE), 0.0)
    hummock = smooth((fbm(7.0, 61) - 0.5) / 0.16) * 1.15 + (detail - 0.5) * 0.5
    ridge = smooth((fbm(26.0, 62) - 0.55) / 0.12) * 0.7
    bottom = SWAMP_FLOOR + hummock + ridge
    h = h * (1.0 - t) + bottom * t

    # речка (вытекает из болота на восток): русло с пологими берегами
    d_riv, _ = polyline_distance(RIVER)
    s = np.clip((d_riv - RIVER_HALF) / (RIVER_BANK - RIVER_HALF), 0.0, 1.0)
    bed = RIVER_BOTTOM + (detail - 0.5) * 0.3
    h = np.where(d_riv < RIVER_BANK, np.minimum(h, bed * (1.0 - smooth(s)) + h * smooth(s)), h)

    # ж/д насыпь вдоль востока: трапеция, у станции шире; проём над «улицей к ТЦ»
    d_rail, _ = polyline_distance(RAIL)
    d_st, _ = polyline_distance(STATION_TRACKS)
    top = np.minimum(d_rail - RAIL_HALF, d_st - STATION_HALF)
    emb = np.where(top < 0.0, RAIL_TOP, RAIL_TOP * (1.0 - smooth(top / RAIL_SLOPE)))
    emb = np.where(top < RAIL_SLOPE, emb, -100.0)
    emb = np.where(emb > -100.0, emb * smooth((np.abs(GZ - RAIL_GAP_Z) - RAIL_GAP_HALF) / 2.5), emb)
    h = np.maximum(h, emb)

    # овраг (12): чаша к руслу, неровные бровки; в начале мельче — как был
    d_rav, along_rav = polyline_distance(RAVINE)
    top_w = RAVINE_TOP * (0.8 + 0.45 * noise(35.0, 5))
    depth = RAVINE_DEPTH * smooth(along_rav / 40.0) * 0.6 + RAVINE_DEPTH * 0.4
    s = np.clip((d_rav - RAVINE_BOTTOM) / (top_w - RAVINE_BOTTOM), 0.0, 1.0)
    cut = depth * (1.0 - s) ** 1.5
    cut += np.where(d_rav < RAVINE_BOTTOM, 0.0, (detail - 0.5) * 1.6 * (1.0 - s) * s * 4.0)
    h -= np.where(d_rav < top_w, cut, 0.0)

    # дороги — после рельефа: полотно по сглаженному профилю
    for name, points, width, sidewalk, dirt in ROAD_DEFS:
        h = carve_road(h, name, points, width, sidewalk, dirt=dirt)
    return h.astype(np.float32)


def sample(h: np.ndarray, x: float, z: float) -> float:
    fx = min(max((x - X0) / STEP, 0.0), NX - 1.001)
    fz = min(max((z - Z0) / STEP, 0.0), NZ - 1.001)
    ix, iz = int(fx), int(fz)
    tx, tz = fx - ix, fz - iz
    a, b = h[iz, ix], h[iz, ix + 1]
    c, d = h[iz + 1, ix], h[iz + 1, ix + 1]
    return float((a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz)


def carve_road(h, name, points, width, sidewalk, closed=False, dirt=False):
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
    ROADS.append(dict(id=name, width=width, sidewalk=sidewalk, dirt=dirt,
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

    # ж/д: щебень балласта по верху и откосам, у подошвы — пятнами
    d_rail, _ = polyline_distance(RAIL)
    d_st, _ = polyline_distance(STATION_TRACKS)
    d_track = np.minimum(d_rail - RAIL_HALF, d_st - STATION_HALF)
    gravel = np.maximum(gravel, 1.0 - smooth((d_track - 1.0) / 2.5))
    gravel = np.maximum(gravel, (1.0 - smooth(d_track / (RAIL_SLOPE + 2))) * smooth((detail - 0.35) / 0.3))

    d_rav, _ = polyline_distance(RAVINE)
    mud = np.maximum(mud, 1.0 - smooth((d_rav - RAVINE_BOTTOM - 1.5) / 3.0))
    rock = np.maximum(rock, (1.0 - smooth((d_rav - 14.0) / 6.0)) * smooth((d_rav - 3.5) / 2.0) * smooth((detail - 0.3) / 0.35))
    leaves = np.maximum(leaves, (1.0 - smooth((d_rav - 26.0) / 8.0)) * 0.75 * smooth((patches - 0.3) / 0.3))

    # болото: ил под водой и по урезу, на кочках — прелая трава и листва
    in_swamp = inside_polygon(SWAMP)
    wet = in_swamp & (h < SWAMP_WATER + 0.25)
    mud = np.maximum(mud, np.where(wet, 1.0, 0.0))
    shore = in_swamp & ~wet
    leaves = np.maximum(leaves, np.where(shore, 0.55 + 0.35 * detail, 0.0))
    # речка: ил по руслу и урезу
    d_riv, _ = polyline_distance(RIVER)
    mud = np.maximum(mud, 1.0 - smooth((d_riv - RIVER_HALF - 1.5) / 2.5))

    # лес по краям; листва под деревьями
    forest = forest_mask()
    leaves = np.maximum(leaves, forest * (0.65 + 0.35 * detail))

    # грунтовки и тропы: лесная дорога, тропа к домам, к южной лесополосе; двор хрущёвок — как был
    for path, width in [
        ([(-100, 40), (-160, 38), (-240, 30), (-272, 18), (-310, 34), (-385, 40)], 2.5),
        ([(-120, 110), (-200, 150), (-185, 200), (-150, 260), (-114, 292)], 2.0),
        # двор хрущёвок (5): вытоптанные тропинки поперёк газонов, к бакам, к гаражам
        ([(-204.0, -126.0), (-199.0, -104.0), (-197.0, -92.0)], 1.2),
        ([(-188.0, -126.0), (-180.0, -96.0), (-176.0, -70.0)], 1.0),
        ([(-164.0, -100.0), (-182.0, -95.0), (-197.0, -92.0)], 1.1),
        ([(-228.0, -85.0), (-212.0, -88.0), (-197.0, -92.0)], 1.0),
        ([(-228.0, -60.0), (-205.0, -57.0)], 1.0),
        ([(-240.0, -150.0), (-262.0, -150.0)], 1.5),
        # тропа вдоль путей и проезд гаражей
        ([(190, -100), (191, -236)], 4.0),
        ([(205, -10), (208, 60)], 1.5),
    ] + [(name_pts, w) for _, name_pts, w, _, dirt in ROAD_DEFS if dirt]:
        d, _ = polyline_distance(path)
        mud = np.maximum(mud, 1.0 - smooth((d - width * 0.5) / 2.5 + (detail - 0.5)))
    # детская площадка: вытоптанная земля с песком; полоса у гаражей двора
    d_play = np.hypot(GX + 197.0, GZ + 92.0)
    mud = np.maximum(mud, (1.0 - smooth((d_play - 9.0 - 4.0 * detail) / 4.0)) * 0.85)
    mud = np.maximum(mud, (1.0 - smooth(rect_distance(-275, -164, -258, -100) / 3.0)) * (0.5 + 0.5 * detail))
    leaves = np.maximum(leaves, (1.0 - smooth(rect_distance(-250, -158, -150, -48) / 2.0)) * smooth((patches - 0.35) / 0.35) * 0.55)
    # стройплощадка — щебень с грязью и колеями; площадки автостанции и станции — щебень пятнами
    site = rect_distance(30, -236, 165, -92)
    gravel = np.maximum(gravel, (1.0 - smooth(site / 4.0)) * (0.55 + 0.45 * detail))
    mud = np.maximum(mud, (1.0 - smooth(site / 6.0)) * smooth((patches - 0.4) / 0.3))
    for rect in ((-94, 97, 60, 215), (118, 95, 186, 240), (160, -45, 198, -15), (176, -232, 205, -108)):
        gravel = np.maximum(gravel, (1.0 - smooth(rect_distance(*rect) / 3.0)) * (0.35 + 0.5 * detail))
    # пятна вытоптанной земли и голой глины по всей карте
    mud = np.maximum(mud, smooth((patches - 0.72) / 0.15) * smooth((detail - 0.4) / 0.4) * 0.8)
    # вне границы — сплошная листва и подлесок (декорация)
    leaves = np.where(inside, leaves, np.maximum(leaves, 0.6))
    rgba = np.stack([mud, rock, gravel, leaves], axis=-1)
    return (np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ растительность всей карты

PADS_BG = [(x - 30, z - 12, x + 30, z + 12) if abs(yaw) < 45 else (x - 12, z - 30, x + 12, z + 30)
           for _, x, z, yaw in [("sf_panel5_brutal", -450, -110, 90), ("sf_panel5_brutal", -452, -40, 92), ("sf_panel12", -450, 60, 88),
                                ("sf_panel12", -150, -405, 0), ("sf_panel5_brutal", 70, -412, 4), ("sf_panel12", 300, -402, -6),
                                ("sf_panel12", 420, 130, -92), ("sf_panel5_brutal", 380, 230, -84), ("sf_panel12", 470, -40, -90),
                                ("sf_panel5_brutal", 470, 60, -90)]]
PADS_PAVED = PADS_BG + [rect for rect, _, _, _ in PADS]
# не сажать деревья на готовые дома с сараями, тропы к ним и подход к мосту через овраг
KEEP_CLEAR = [(hx - 12, hz - 10, hx + 12, hz + 14) for hx, hz in HOUSES] + [(-372, 30, -300, 42)]

def build_vegetation(h: np.ndarray, splat: np.ndarray) -> None:
    """Деревья и сухая трава по всей карте (двор хрущёвок — свой генератор): точки в JSON для
    DistrictScatter. Лес — по маске лесополосы, склоны оврага, кольцо вокруг холма; трава — везде,
    где нет покрытия, площадок и голой грязи/щебня."""
    rng = np.random.default_rng(31)
    inside = inside_polygon(BOUNDARY)
    paved = np.zeros(GX.shape, bool)
    for rect in PADS_PAVED + KEEP_CLEAR:
        paved |= rect_distance(*rect) < 2.0
    d_path, _ = polyline_distance([(-100, 40), (-160, 38), (-240, 30), (-272, 18), (-310, 34), (-385, 40)])
    paved |= d_path < 2.5
    for road in ROADS:
        pts = [(p[0], p[2]) for p in road["points"]]
        d, _ = polyline_distance(pts)
        paved |= d < road["width"] * 0.5 + road["sidewalk"] + 1.5
    d_rail, _ = polyline_distance(RAIL)
    d_st, _ = polyline_distance(STATION_TRACKS)
    d_track = np.minimum(d_rail - RAIL_HALF, d_st - STATION_HALF)
    paved |= d_track < 1.0
    d_rav, _ = polyline_distance(RAVINE)
    swamp = inside_polygon(SWAMP)
    dry = h > SWAMP_WATER + 0.3
    forest = forest_mask()
    mud, gravel = splat[..., 0] / 255.0, splat[..., 2] / 255.0
    trees: dict[str, list] = {f"tree_{k}_{v}": [] for k in ("birch", "poplar", "maple") for v in range(3)}
    trees.update({k: [] for k in SPRUCES + BIRCHES})

    def put(kind: str, x: float, z: float) -> None:
        # ель — своя (tools/build_spruce.py): в лесу высокие с сухими сучьями и подрост, на открытом —
        # одиночные с юбкой до земли; лиственные — свои
        if kind == "bog":
            # болото: сухостойные и молодые берёзы на кочках
            key = rng.choice(["birch_bare", "birch_bare", "birch_bare", "birch_young", "birch_c"])
        elif kind == "fir":
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
            if swamp[iz, ix]:
                if dry[iz, ix] and rng.random() < 0.3:
                    put("bog", x, z)
                continue
            if f > 0.5 and rng.random() < 0.75 * f:
                put(rng.choice(["fir", "fir", "fir", "birch", "birch", "maple", "poplar"]), x, z)
            elif 4.0 < r < 30.0 and rng.random() < 0.38:
                put(rng.choice(["maple", "maple", "birch", "fir"]), x, z)
            elif not inside[iz, ix] and rng.random() < 0.3:
                # за границей — сплошной лес (декорация края карты)
                put(rng.choice(["fir", "fir", "birch", "maple", "poplar"]), x, z)
            elif inside[iz, ix] and rng.random() < 0.012:
                put(rng.choice(["birch", "maple", "spruce_open"]), x, z)
    # тополя по обе стороны «улицы к ТЦ» — советская посадка, с пропусками
    for x in np.arange(-88, 190, 11.0):
        for z in (-51.0, -69.0):
            if rng.random() < 0.7 and ok(int(x - X0), int(z - Z0)):
                put("poplar", x + rng.uniform(-2, 2), z + rng.uniform(-1.0, 1.0))
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
            if swamp[iz, ix]:
                if dry[iz, ix]:
                    for name, pr in (("forest_dead_trunk", 0.03), ("forest_stump_01", 0.025), ("forest_stump_02", 0.025),
                                     ("forest_dry_branches", 0.06), ("forest_fern", 0.03)):
                        if roll < pr:
                            key = name
                            break
                        roll -= pr
            elif f > 0.4:
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
    near_edge = np.maximum(near_edge, (1.0 - smooth((d_track - RAIL_SLOPE) / 6.0)))

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
    # болото: на кочках — густая высокая трава, в воде — ничего
    dens = np.where(swamp & dry, np.maximum(dens, 0.8), np.where(swamp, 0.0, dens))
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
    """Лес по краям: за болотом и речкой на севере, за оврагом на западе, полоса на юге; дороги — просеки."""
    n = fbm(50.0, 21)
    north = smooth((-GZ - 312.0 - (n - 0.5) * 24.0) / 10.0)
    west = smooth((-GX - 372.0 - (n - 0.5) * 20.0) / 10.0)
    south = smooth((GZ - 272.0 - (n - 0.5) * 24.0) / 10.0) * smooth((GX + 340.0) / 20.0) * (1.0 - smooth((GX - 160.0) / 20.0))
    mask = np.maximum(np.maximum(north, west), south)
    for name, points, width, sidewalk, _ in ROAD_DEFS:
        if name in ("ForestRoad", "BridgeRoad"):
            d, _ = polyline_distance(points)
            mask *= smooth((d - width * 0.5 - 2.0) / 3.0)
    d, _ = polyline_distance([(-343, 37), (-420, 40)])
    mask *= smooth((d - 3.0) / 3.0)
    return np.clip(mask, 0.0, 1.0)

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


# ------------------------------------------------------------------ мир: рельеф, дороги, вода

def world_scene() -> None:
    s = Scene("World")
    s.node("Terrain", script=s.resource("res://src/world/district_terrain.gd", "Script"), data_path=SECTOR,
           excavations=Raw("Array[AABB]([AABB(-225, -1.9, -144, 17, 2.3, 12)])"))
    s.node("Roads")
    for road in ROADS:
        if road.get("dirt"):
            continue  # грунтовка — колея в маске поверхностей, без асфальта
        raw = "PackedVector3Array(" + ", ".join(str(v) for p in road["points"] for v in p) + ")"
        s.node(road["id"], "Roads", "res://scenes/world/urban_road.tscn", points=Raw(raw),
               carriage_width=road["width"], sidewalk_width=road["sidewalk"], sidewalks=road["sidewalk"] > 0,
               markings=road["id"] not in ("BridgeRoad", "StationRoad"))
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
    # болото: одна гладь на уровне SWAMP_WATER — кочки и берега выше неё, окна воды ниже
    sx0, sz0 = min(p[0] for p in SWAMP), min(p[1] for p in SWAMP)
    sx1, sz1 = max(p[0] for p in SWAMP), max(p[1] for p in SWAMP)
    mesh = s.sub("PlaneMesh", size=v2(sx1 - sx0, sz1 - sz0), material=mat, subdivide_width=16, subdivide_depth=8)
    s.node("Swamp", "Water", kind="MeshInstance3D", mesh=mesh, position=v3((sx0 + sx1) / 2, SWAMP_WATER, (sz0 + sz1) / 2),
           cast_shadow=0)
    # речка — полосами вдоль русла; под насыпью и дорогой гладь спрятана рельефом
    for i, ((ax, az), (bx, bz)) in enumerate(zip(RIVER, RIVER[1:])):
        length = math.dist((ax, az), (bx, bz)) + 3.0
        mesh = s.sub("PlaneMesh", size=v2(RIVER_HALF * 2 + 2.0, length), material=mat)
        s.node(f"River_{i}", "Water", kind="MeshInstance3D", mesh=mesh,
               position=v3((ax + bx) / 2, RIVER_WATER, (az + bz) / 2),
               rotation_degrees=v3(0, math.degrees(math.atan2(bx - ax, bz - az)), 0), cast_shadow=0)
    perimeter(s)
    vegetation_nodes(s)
    s.save(OUT / "zone01_world.tscn")


def perimeter(s: Scene) -> None:
    """Невидимая граница по контуру (высота 6 м над землёй); видимые преграды — насыпь, овраг, лес, болото."""
    s.node("Perimeter")
    poly = BOUNDARY + BOUNDARY[:1]
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        x, z = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        length = math.dist(a, b)
        yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        low = min(ground(*a), ground(x, z), ground(*b)) - 12
        props(s, f"Wall_{i}", x, z, [box((0, (low + 8) / 2 - ground(x, z) + 4, 0), (length + 1, 20 + 8, .6), GREY, True, render=False)],
              "Perimeter", yaw)


# ------------------------------------------------------------------ постройки: готовые сцены, гаражи, город за границей

# город за границей — декорация без входа: на западе за оврагом, на севере за лесом, на востоке за полем
BACKGROUND = [("sf_panel5_brutal", -450, -110, 90), ("sf_panel5_brutal", -452, -40, 92), ("sf_panel12", -450, 60, 88),
              ("sf_panel12", -150, -405, 0), ("sf_panel5_brutal", 70, -412, 4), ("sf_panel12", 300, -402, -6),
              ("sf_panel12", 420, 130, -92), ("sf_panel5_brutal", 380, 230, -84), ("sf_panel12", 470, -40, -90),
              ("sf_panel5_brutal", 470, 60, -90)]

# гаражи у путей: два ряда кирпичных боксов (Sketchfab, ворота модели — на её −X) воротами в общий проезд
GARAGE_ROWS = [(182.0, 180.0), (199.0, 0.0)]   # x оси ряда, поворот
GARAGE_BLOCKS_Z = [-121.0, -143.0, -165.0, -187.0, -209.0]


def background(s: "Scene") -> None:
    s.node("Background")
    for i, (model, x, z, yaw) in enumerate(BACKGROUND):
        sf_model(s, f"Building_{i}", model, x, z, yaw, "Background", y=ground(x, z) - 0.3, surface="concrete")


def blockout_scene() -> None:
    s = Scene("Blockout")
    background(s)
    if (OUT / "zone01_market06.tscn").exists():
        s.node("Z06_Market", scene="res://scenes/levels/zone01/zone01_market06.tscn")
    else:
        print("zone01: нет сцены рынка zone01_market06.tscn — tools/author_zone01_nw.py")
    if (OUT / "zone01_houses12.tscn").exists():
        s.node("Z12_Ravine", scene="res://scenes/levels/zone01/zone01_houses12.tscn")
    else:
        print("zone01: нет сцены домов zone01_houses12.tscn — tools/author_zone01_nw.py")
    s.node("Z08_Garages")
    s.node("Buildings", "Z08_Garages")
    for row, (x, yaw) in enumerate(GARAGE_ROWS):
        for k, gz in enumerate(GARAGE_BLOCKS_Z):
            sf_model(s, f"Row{row}_Block{k}", "sf_garage_row", x, gz, yaw, "Z08_Garages/Buildings",
                     y=ground(x, gz) - .05, surface="concrete")
    s.save(OUT / "zone01_blockout.tscn")


# ------------------------------------------------------------------ данные сектора и главная сцена

SPAWNS = [("Лесная дорога", -372, -215), ("За речкой", 150, -322), ("Из-за насыпи", 252, 30),
          ("Южная лесополоса", 110, 290), ("Юго-запад", -250, 292), ("За оврагом", -385, 150)]
EXTRACTS = [("Лесная дорога", -345, -322, ""), ("Старый мост", 58, -286, ""), ("Мост через овраг", -386, 40, ""),
            ("Ж/д пути", 188, 292, ""), ("Автостанция", 8, 126, ""), ("К ТЦ", 258, -60, "")]
AI_POINTS = [(-200, -95), (-170, 20), (-150, 80), (-280, 30), (-70, -110), (100, -160), (190, -170),
             (95, 10), (180, -30), (-20, 150), (150, 160), (-150, -194), (100, -285), (240, 0), (-120, 240)]
ROOMS = [("yard05", "Двор хрущёвок", (-228, -126, -160, -55)), ("market", "Рынок", (-232, -50, -110, 105)),
         ("houses", "Дома у оврага", (-300, -8, -262, 60)), ("swamp", "Болото", (-290, -300, 10, -190)),
         ("second_yard", "Второй двор", (-92, -150, -24, -72)), ("construction", "Недострой", (30, -236, 165, -92)),
         ("sports", "Спортплощадка", (25, -45, 152, 35)), ("fuel", "АЗС", (160, -45, 198, -15)),
         ("bus_station", "Автостанция", (-94, 97, 60, 215)), ("station", "Ж/д станция", (118, 95, 186, 240)),
         ("garages", "Гаражи у путей", (176, -232, 205, -108))]

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
    if (OUT / "zone01_environment.tres").exists():
        return
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
        id="zone01_mall", name="Зона 1 · Городской пояс", layout="cartesian_scene", greybox=True,
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
        rooms=rooms, roads=[r for r in ROADS],
        districts=[dict(id=r[0], name=r[1], rect=list(r[2])) for r in ROOMS],
        heights=dict(rail_top=RAIL_TOP, ravine_depth=RAVINE_DEPTH, swamp_water=SWAMP_WATER, river_water=RIVER_WATER),
    )
    definition_path = ROOT / "data/sectors/zone01_mall.json"
    # Отдельно авторские слои (россыпь и население) не теряются при пересборке географии.
    if definition_path.exists():
        old = json.loads(definition_path.read_text(encoding="utf-8"))
        result["extras"] = old.get("extras", [])
        # ключи, которые дописали руками или другие инструменты (птицы и т. п.), — сохранить
        for key, value in old.items():
            result.setdefault(key, value)
    definition_path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
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
    main_scene()
    write_definition(H)
    # превью высот для документации
    norm = (H - H.min()) / (H.max() - H.min())
    Image.fromarray((norm * 255).astype(np.uint8)).save(ROOT / "docs/plans/zone01_heights.png")


if __name__ == "__main__":
    main()
