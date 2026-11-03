"""Зона 1 «Пригород»: рельеф, маска поверхностей и каркас карты по раскладке data/zone01_layout.json —
квадрат ≈ 600 × 600 м по картинке владельца (решение 2026-10-17, docs/design/zone01_outskirts.md §11;
раскладку пишет tools/zone01_square_plan.py). Готовые двор хрущёвок, рынок и дома у оврага переезжают
целиком: их сцены ставятся со сдвигом / поворотом, а земля под ними переносится из вырезок прежней карты
высот (data/terrain/zone01_ready, tools/zone01_freeze_ready_ground.py) — до миллиметра прежняя.
Всё остальное — блокауты (tools/build_zone01_blockouts.py → zone01_layout.tscn).

Использование: python -X utf8 tools/build_zone01.py
Пишет:
  data/terrain/zone01_heights.r32          карта высот (float32, 1 м), её читает DistrictTerrain
  assets/terrain/zone01_splat.png          маска поверхностей R грязь, G камень, B щебень, A листва
  assets/terrain/zone01_{albedo,normal,arm}.jpg  массивы слоёв рельефа (6 слоёв, полосой)
  data/sectors/zone01_mall.json            данные сектора (границы, точки, дороги, растительность)
  scenes/levels/zone01_mall.tscn           главная сцена уровня
  scenes/levels/zone01/zone01_world.tscn   рельеф, дороги, вода (болото, ручей в овраге), периметр
  scenes/levels/zone01/zone01_blockout.tscn  готовые сцены рынка и домов на новых местах, гаражи, город за границей
  scenes/levels/zone01/zone01_layout.tscn  блокауты построек, путей, мостков, площадок, машины
  scenes/levels/zone01/zone01_yard05.tscn  двор с хрущёвками — ТОЛЬКО если файла ещё нет
                                           (детальную зону 5 собирает tools/build_zone01_yard.py)

Случайного размещения во время игры нет: план задан раскладкой, шум — с фиксированным зерном. Повторный
запуск перезаписывает мир, блокаут и блокауты построек (ручные правки этих сцен пропадут).
Оси: X — восток, Z — юг (север = -Z), 1 единица = 1 м. Начало координат — центр квадрата карты.
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
LAYOUT = json.loads((ROOT / "data/zone01_layout.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ сетка рельефа
# квадрат карты 600 × 600 м и лес / город вокруг — до ±440 м
X0, Z0, NX, NZ = -440.0, -440.0, 881, 881
STEP = 1.0
xs = X0 + np.arange(NX) * STEP
zs = Z0 + np.arange(NZ) * STEP
GX, GZ = np.meshgrid(xs, zs)
RNG = np.random.default_rng(20261017)

# граница игровой области (раскладка, квадрат с неровным краем леса)
BOUNDARY = [list(p) for p in LAYOUT["boundary"]]

# ж/д: ось из раскладки; главный ход — 2 пути, у вокзала парк из 7 путей. С севера пути идут по насыпи
# мостом над дорогой к ТЦ (дорога — под ним), в парке — почти вровень с землёй
RAIL = [tuple(p) for p in LAYOUT["tracks"]["axis"]]
RAIL_YARD = LAYOUT["tracks"]["yard"]
RAIL_HALF = 4.6
RAIL_YARD_HALF = (RAIL_YARD["count"] - 1) / 2 * RAIL_YARD["spacing"] + 3.5
RAIL_TOP_Z = [(-120.0, 6.2), (-56.0, 6.2), (-15.0, 4.6), (35.0, 1.6), (70.0, 0.9), (250.0, 0.9), (310.0, 1.3)]
RAIL_BRIDGE = LAYOUT["tracks"]["bridge"]
RAIL_BRIDGE_TOP = 6.2
RAIL_TOP = 6.2  # наибольшая высота насыпи (для данных сектора)

# овраг: сток из болота по северному краю, мимо домов на восток; у моста ось — прежняя, повёрнутая
RAVINE = [tuple(p) for p in LAYOUT["ravine"]]
RAVINE_DEPTH = 10.0
RAVINE_BOTTOM = 3.0
RAVINE_TOP = 22.0

# болото (1): топь ниже улиц, кочки над водой, окна открытой воды
SWAMP = [tuple(p) for p in LAYOUT["swamp"]]
SWAMP_FLOOR = -1.25   # дно открытой воды: ≈ 0,95 м под гладью — по пояс, вброд (владелец 2026-10-18)
SWAMP_WATER = -0.3
SWAMP_EDGE = 14.0
RIVER_WATER = -1.55  # речки больше нет (вода — ручей в овраге); значение оставлено для данных сектора

# готовые куски: сдвиг / поворот из раскладки
READY = LAYOUT["ready"]
READY_GROUND = json.loads((ROOT / "data/terrain/zone01_ready/ready.json").read_text(encoding="utf-8"))
READY_BAND = 6.0  # полоса плавного перехода от прежней земли куска к новой
SCENES = {"yard05": "Yard05", "market06": "Z06_Market", "houses12": "Z12_Ravine"}


def ready_new(key: str, x: float, z: float) -> tuple[float, float]:
    """Прежняя точка готового куска → новое место."""
    r = READY[key]
    if r["rotate"] == 180:
        (ox, oz), (nx, nz) = r["pivot_old"], r["pivot_new"]
        return nx - (x - ox), nz - (z - oz)
    dx, dz = r["move"]
    return x + dx, z + dz


def ready_old(key: str, x, z):
    """Новая точка → прежняя (работает и с массивами numpy)."""
    r = READY[key]
    if r["rotate"] == 180:
        (ox, oz), (nx, nz) = r["pivot_old"], r["pivot_new"]
        return ox - (x - nx), oz - (z - nz)
    dx, dz = r["move"]
    return x - dx, z - dz


def ready_transform(key: str) -> tuple[tuple[float, float, float], float]:
    """Положение и поворот узла-экземпляра сцены куска (сцены внутри — в прежних координатах)."""
    r = READY[key]
    if r["rotate"] == 180:
        (ox, oz), (nx, nz) = r["pivot_old"], r["pivot_new"]
        return (nx + ox, 0.0, nz + oz), 180.0
    dx, dz = r["move"]
    return (dx, 0.0, dz), 0.0


def instance_attrs(key: str) -> dict:
    """Свойства узла-экземпляра готового куска (положение и поворот) для записи сцены."""
    (x, y, z), yaw = ready_transform(key)
    attrs = {"position": v3(x, y, z)}
    if yaw:
        attrs["rotation_degrees"] = v3(0, yaw, 0)
    return attrs


def ready_crop_ground(x: float, z: float) -> float:
    """Прежняя земля готовых кусков в их прежних координатах (вырезки data/terrain/zone01_ready):
    генераторы двора, рынка и домов (build_zone01_yard.py, author_zone01_nw.py) ставят по ней свои
    модели — на новом месте под куском та же земля."""
    for key, crop in READY_GROUND["crops"].items():
        (ox, oz), (w, hgt) = crop["origin"], crop["size"]
        if ox <= x <= ox + w - 1 and oz <= z <= oz + hgt - 1:
            if key not in _CROP_CACHE:
                _CROP_CACHE[key] = np.fromfile(ROOT / f"data/terrain/zone01_ready/{key}.r32", dtype="<f4").reshape(hgt, w)
            data = _CROP_CACHE[key]
            fx, fz = min(x - ox, w - 1.001), min(z - oz, hgt - 1.001)
            ix, iz = int(fx), int(fz)
            tx, tz = fx - ix, fz - iz
            return float((data[iz, ix] * (1 - tx) + data[iz, ix + 1] * tx) * (1 - tz) +
                         (data[iz + 1, ix] * (1 - tx) + data[iz + 1, ix + 1] * tx) * tz)
    return 0.0


_CROP_CACHE: dict[str, np.ndarray] = {}

# двор хрущёвок (прежние координаты): подвал вырезан в рельефе — на новом месте со сдвигом двора
YARD_EXCAVATION_OLD = (-225.0, -1.9, -144.0, 17.0, 2.3, 12.0)


def yard_excavation() -> str:
    x, y, z, w, hh, d = YARD_EXCAVATION_OLD
    dx, dz = READY["yard05"]["move"]
    return f"Array[AABB]([AABB({x + dx:g}, {y:g}, {z + dz:g}, {w:g}, {hh:g}, {d:g})])"
HOUSES = [ready_new("houses12", x, z) for x, z in [(-270, 3), (-297, 25), (-272, 50)]]

ROADS: list[dict] = []
# дороги из раскладки: имя, точки, ширина проезжей части, тротуар, грунтовка (без асфальта — колея по маске)
SIDEWALK = {"north": 2.5, "south": 2.5, "artery": 2.5, "east": 2.0, "mall": 2.0, "evac3": 1.5, "tracks_lane": 0.0}
ROAD_DEFS = [(r["id"], [tuple(p) for p in r["points"]], float(r["width"]), 0.0 if r["dirt"] else SIDEWALK.get(r["id"], 1.5),
              bool(r["dirt"])) for r in LAYOUT["roads"]]

# площадки под постройками раскладки: (x0, z0, x1, z1) вокруг каждой — ровно, с откосом к рельефу
def _footprint_rect(b: dict, pad: float) -> tuple[float, float, float, float]:
    (x, z), (L, D), ang = b["at"], b["size"], b["angle"]
    a = math.radians(ang)
    hx = abs(L / 2 * math.cos(a)) + abs(D / 2 * math.sin(a)) + pad
    hz = abs(L / 2 * math.sin(a)) + abs(D / 2 * math.cos(a)) + pad
    return (x - hx, z - hz, x + hx, z + hz)


BUILDING_PADS = [_footprint_rect(b, 3.0) for b in LAYOUT["buildings"]] + [_footprint_rect(LAYOUT["court"], 2.0)]
POLY_PADS = [[tuple(p) for p in LAYOUT["site"]], [tuple(p) for p in LAYOUT["bus_lot"]]]

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
    """Плавный шум 0..1 на сетке карты."""
    return _noise_grid(cell, seed, NX, NZ)


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
    global PROTECT
    undulation = (fbm(140.0, 1) - 0.5) * 1.6 + (fbm(45.0, 2) - 0.5) * 0.6
    h = undulation.astype(np.float32)
    detail = fbm(18.0, 3)

    # площадки под постройками раскладки и большие площадки (стройка, автостанция)
    for x0, z0, x1, z1 in BUILDING_PADS:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        h = flatten(h, rect_distance(x0, z0, x1, z1), float(h[int(cz - Z0), int(cx - X0)]), 6.0, 0.15, detail)
    for poly in POLY_PADS:
        cx = sum(p[0] for p in poly) / len(poly)
        cz = sum(p[1] for p in poly) / len(poly)
        dist = np.where(inside_polygon(poly), 0.0, polygon_edge_distance(poly))
        h = flatten(h, dist, float(h[int(cz - Z0), int(cx - X0)]), 8.0, 0.3, detail)
    # фон за границей: ровные площадки под панельки
    for x0, z0, x1, z1 in PADS_BG:
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        h = flatten(h, rect_distance(x0 - 3, z0 - 3, x1 + 3, z1 + 3), float(h[int(cz - Z0), int(cx - X0)]), 10.0)
    # низины поднять до нуля — улицы и дворы не стоят в ямах; болото и овраг врезаются уже после
    h = np.maximum(h, 0.0)

    # болото (1): чаша к дну SWAMP_FLOOR с плавным краем; кочки и гряды выше воды, окна воды ниже
    inside = inside_polygon(SWAMP)
    edge = polygon_edge_distance(SWAMP)
    t = np.where(inside, smooth(edge / SWAMP_EDGE), 0.0)
    hummock = smooth((fbm(7.0, 61) - 0.5) / 0.16) * 1.15 + (detail - 0.5) * 0.5
    ridge = smooth((fbm(26.0, 62) - 0.55) / 0.12) * 0.7
    bottom = SWAMP_FLOOR + hummock + ridge
    h = h * (1.0 - t) + bottom * t

    # ж/д: насыпь по оси, у вокзала шире (парк путей); высота — по участкам (мост над дорогой к ТЦ)
    d_rail, _ = polyline_distance(RAIL)
    yard_t = rail_yard_weight()
    half = RAIL_HALF + (RAIL_YARD_HALF - RAIL_HALF) * yard_t
    top_h = np.interp(GZ, [z for z, _ in RAIL_TOP_Z], [v for _, v in RAIL_TOP_Z]).astype(np.float32)
    slope_w = np.maximum(6.0, top_h * 2.0)
    d_top = d_rail - half
    emb = np.where(d_top < 0.0, top_h, top_h * (1.0 - smooth(d_top / slope_w)))
    emb = np.where(d_top < slope_w, emb, -100.0)
    # проём под мостом: дорога к ТЦ проходит под путями
    (bx, bz) = RAIL_BRIDGE["at"]
    d_mall, _ = polyline_distance([tuple(p) for r in LAYOUT["roads"] if r["id"] == "mall" for p in r["points"]])
    near_bridge = np.hypot(GX - bx, GZ - bz) < 40.0
    emb = np.where((emb > -100.0) & near_bridge, emb * smooth((d_mall - 7.5) / 2.5), emb)
    h = np.maximum(h, emb)

    # овраг: чаша к руслу, неровные бровки; у болота мельче
    d_rav, along_rav = polyline_distance(RAVINE)
    top_w = RAVINE_TOP * (0.8 + 0.45 * noise(35.0, 5))
    depth = RAVINE_DEPTH * smooth(along_rav / 40.0) * 0.6 + RAVINE_DEPTH * 0.4
    s = np.clip((d_rav - RAVINE_BOTTOM) / (top_w - RAVINE_BOTTOM), 0.0, 1.0)
    cut = depth * (1.0 - s) ** 1.5
    cut += np.where(d_rav < RAVINE_BOTTOM, 0.0, (detail - 0.5) * 1.6 * (1.0 - s) * s * 4.0)
    h -= np.where(d_rav < top_w, cut, 0.0)

    # готовые куски: прежняя земля на новом месте (подвал двора, площадка рынка, склоны оврага у домов)
    h, PROTECT = place_ready_ground(h)

    # дороги — после рельефа: полотно по сглаженному профилю; землю готовых кусков не трогают
    for name, points, width, sidewalk, dirt in ROAD_DEFS:
        h = carve_road(h, name, points, width, sidewalk, dirt=dirt)
    return h.astype(np.float32)


PROTECT: np.ndarray = np.zeros((1, 1), np.float32)


def rail_yard_weight() -> np.ndarray:
    """0..1: где пути расходятся в парк (вдоль z, с плавными въездами по 40 м)."""
    y0, y1 = RAIL_YARD["from_z"], RAIL_YARD["to_z"]
    return np.clip(1.0 - np.maximum(np.maximum(y0 - GZ, GZ - y1), 0.0) / 40.0, 0.0, 1.0).astype(np.float32)


def place_ready_ground(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Вырезки прежней карты высот — на новые места кусков (сдвиг / поворот), с переходом READY_BAND."""
    protect = np.zeros(GX.shape, np.float32)
    for key, crop in READY_GROUND["crops"].items():
        (ox, oz), (w, hgt) = crop["origin"], crop["size"]
        data = np.fromfile(ROOT / f"data/terrain/zone01_ready/{key}.r32", dtype="<f4").reshape(hgt, w)
        corners = [ready_new(key, ox + dx, oz + dz) for dx in (0, w - 1) for dz in (0, hgt - 1)]
        x0, x1 = min(c[0] for c in corners), max(c[0] for c in corners)
        z0, z1 = min(c[1] for c in corners), max(c[1] for c in corners)
        i0, i1 = max(0, int(x0 - X0)), min(NX, int(x1 - X0) + 2)
        j0, j1 = max(0, int(z0 - Z0)), min(NZ, int(z1 - Z0) + 2)
        sx, sz = GX[j0:j1, i0:i1], GZ[j0:j1, i0:i1]
        px, pz = ready_old(key, sx, sz)
        fx, fz = px - ox, pz - oz
        ok = (fx >= 0) & (fz >= 0) & (fx <= w - 1) & (fz <= hgt - 1)
        fxc, fzc = np.clip(fx, 0, w - 1.001), np.clip(fz, 0, hgt - 1.001)
        ix, iz = fxc.astype(int), fzc.astype(int)
        tx, tz = fxc - ix, fzc - iz
        val = ((data[iz, ix] * (1 - tx) + data[iz, ix + 1] * tx) * (1 - tz) +
               (data[iz + 1, ix] * (1 - tx) + data[iz + 1, ix + 1] * tx) * tz)
        edge = np.minimum(np.minimum(fx, w - 1 - fx), np.minimum(fz, hgt - 1 - fz))
        wgt = np.where(ok, smooth(edge / READY_BAND), 0.0).astype(np.float32)
        sub = h[j0:j1, i0:i1]
        h[j0:j1, i0:i1] = sub * (1.0 - wgt) + val * wgt
        protect[j0:j1, i0:i1] = np.maximum(protect[j0:j1, i0:i1], wgt)
    return h, protect


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
    w = (1.0 - smooth((best - half) / 5.0)) * (1.0 - PROTECT)
    h = np.where(np.isnan(target), h, h * (1 - w) + (np.nan_to_num(target) - 0.06) * w)
    ROADS.append(dict(id=name, width=width, sidewalk=sidewalk, dirt=dirt,
                      points=[[round(x, 2), round(float(y), 3), round(z, 2)] for (x, z), y in list(zip(dense, ys))[::5]] +
                      ([] if (len(dense) - 1) % 5 == 0 else [[round(dense[-1][0], 2), round(float(ys[-1]), 3), round(dense[-1][1], 2)]])))
    return h


# ------------------------------------------------------------------ маска поверхностей

def track_distance() -> np.ndarray:
    """Расстояние от края полотна путей (меньше нуля — на полотне; в парке полотно шире)."""
    d_rail, _ = polyline_distance(RAIL)
    return d_rail - (RAIL_HALF + (RAIL_YARD_HALF - RAIL_HALF) * rail_yard_weight())


def place_ready_maps(img: np.ndarray, name: str) -> np.ndarray:
    """Маска поверхностей / густота травы под готовыми кусками — из вырезок прежних карт (как рельеф)."""
    out = img.astype(np.float32)
    for key, crop in READY_GROUND["crops"].items():
        (ox, oz), (w, hgt) = crop["origin"], crop["size"]
        src = np.asarray(Image.open(ROOT / f"data/terrain/zone01_ready/{key}_{name}.png"), dtype=np.float32)
        corners = [ready_new(key, ox + dx, oz + dz) for dx in (0, w - 1) for dz in (0, hgt - 1)]
        x0, x1 = min(c[0] for c in corners), max(c[0] for c in corners)
        z0, z1 = min(c[1] for c in corners), max(c[1] for c in corners)
        i0, i1 = max(0, int(x0 - X0)), min(NX, int(x1 - X0) + 2)
        j0, j1 = max(0, int(z0 - Z0)), min(NZ, int(z1 - Z0) + 2)
        px, pz = ready_old(key, GX[j0:j1, i0:i1], GZ[j0:j1, i0:i1])
        fx, fz = px - ox, pz - oz
        ok = (fx >= 0) & (fz >= 0) & (fx <= w - 1) & (fz <= hgt - 1)
        ix = np.clip(np.rint(fx), 0, w - 1).astype(int)
        iz = np.clip(np.rint(fz), 0, hgt - 1).astype(int)
        edge = np.minimum(np.minimum(fx, w - 1 - fx), np.minimum(fz, hgt - 1 - fz))
        wgt = np.where(ok, smooth(edge / READY_BAND), 0.0)[..., None]
        sub = out[j0:j1, i0:i1]
        out[j0:j1, i0:i1] = sub * (1.0 - wgt) + src[iz, ix] * wgt
    return out


def build_splat(h: np.ndarray) -> np.ndarray:
    detail = fbm(12.0, 11)
    patches = fbm(30.0, 12)
    inside = inside_polygon(BOUNDARY)
    mud = np.zeros(GX.shape, np.float32)
    rock = np.zeros(GX.shape, np.float32)
    gravel = np.zeros(GX.shape, np.float32)
    leaves = np.zeros(GX.shape, np.float32)

    # ж/д: щебень балласта по полотну и откосам, у подошвы — пятнами
    d_track = track_distance()
    gravel = np.maximum(gravel, 1.0 - smooth((d_track - 1.0) / 2.5))
    gravel = np.maximum(gravel, (1.0 - smooth(d_track / 10.0)) * smooth((detail - 0.35) / 0.3))

    d_rav, _ = polyline_distance(RAVINE)
    mud = np.maximum(mud, 1.0 - smooth((d_rav - RAVINE_BOTTOM - 1.5) / 3.0))
    rock = np.maximum(rock, (1.0 - smooth((d_rav - 14.0) / 6.0)) * smooth((d_rav - 3.5) / 2.0) * smooth((detail - 0.3) / 0.35))
    leaves = np.maximum(leaves, (1.0 - smooth((d_rav - 26.0) / 8.0)) * 0.75 * smooth((patches - 0.3) / 0.3))

    # болото: ил под водой и по урезу, на кочках — прелая трава и листва
    in_swamp = inside_polygon(SWAMP)
    wet = in_swamp & (h < SWAMP_WATER + 0.25)
    mud = np.maximum(mud, np.where(wet, 1.0, 0.0))
    leaves = np.maximum(leaves, np.where(in_swamp & ~wet, 0.55 + 0.35 * detail, 0.0))

    # лес по краям; листва под деревьями
    forest = forest_mask()
    leaves = np.maximum(leaves, forest * (0.65 + 0.35 * detail))

    # грунтовки и тропы: дороги-грунтовки раскладки, тропы болота, вытоптанные тропинки между домами
    paths = [(pts, w) for _, pts, w, _, dirt in ROAD_DEFS if dirt] + [([tuple(p) for p in t], 1.6) for t in LAYOUT["trails"]]
    for path, width in paths:
        d, _ = polyline_distance(path)
        mud = np.maximum(mud, 1.0 - smooth((d - width * 0.5) / 2.5 + (detail - 0.5)))
    # стройплощадка — щебень с грязью и колеями; площадка автостанции — щебень пятнами, стоянка
    site = np.where(inside_polygon(POLY_PADS[0]), 0.0, polygon_edge_distance(POLY_PADS[0]))
    gravel = np.maximum(gravel, (1.0 - smooth(site / 4.0)) * (0.55 + 0.45 * detail))
    mud = np.maximum(mud, (1.0 - smooth(site / 6.0)) * smooth((patches - 0.4) / 0.3))
    lot = np.where(inside_polygon(POLY_PADS[1]), 0.0, polygon_edge_distance(POLY_PADS[1]))
    gravel = np.maximum(gravel, (1.0 - smooth(lot / 3.0)) * (0.45 + 0.45 * detail))
    # двор ремонтных площадок — укатанный щебень с масляной грязью пятнами
    ry0 = LAYOUT["repair_yard"]["fence"]
    rrect = (min(q[0] for q in ry0), min(q[1] for q in ry0), max(q[0] for q in ry0), max(q[1] for q in ry0))
    yard_d = rect_distance(*rrect)
    gravel = np.maximum(gravel, (1.0 - smooth(yard_d / 2.0)) * (0.6 + 0.35 * detail))
    mud = np.maximum(mud, (1.0 - smooth(yard_d / 2.0)) * smooth((patches - 0.5) / 0.25) * 0.7)
    # у ангаров, складов, вокзала — укатанный щебень вокруг
    for b in LAYOUT["buildings"]:
        if b["kind"] in ("hall", "station", "skeleton"):
            x0, z0, x1, z1 = _footprint_rect(b, 6.0)
            gravel = np.maximum(gravel, (1.0 - smooth(rect_distance(x0, z0, x1, z1) / 3.0)) * (0.3 + 0.5 * detail))
    # пятна вытоптанной земли и голой глины по всей карте
    mud = np.maximum(mud, smooth((patches - 0.72) / 0.15) * smooth((detail - 0.4) / 0.4) * 0.8)
    # вне границы — сплошная листва и подлесок (декорация)
    leaves = np.where(inside, leaves, np.maximum(leaves, 0.6))
    rgba = np.stack([mud, rock, gravel, leaves], axis=-1)
    rgba = (np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5)
    # готовые куски — их прежняя маска (тропинки двора, площадка, грязь у домов и моста)
    return np.clip(place_ready_maps(rgba, "splat") + 0.5, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ растительность всей карты

# город за границей — декорация без входа: панельки за лесом с трёх сторон (на востоке — за путями)
BACKGROUND = [("sf_panel5_brutal", -395, -150, 90), ("sf_panel5_brutal", -398, -40, 92), ("sf_panel12", -395, 80, 88),
              ("sf_panel12", -150, -400, 0), ("sf_panel5_brutal", 40, -405, 4), ("sf_panel12", 220, -398, -6),
              ("sf_panel12", 395, 150, -92), ("sf_panel5_brutal", 385, 260, -84), ("sf_panel12", 395, 40, -90),
              ("sf_panel12", -120, 400, 180), ("sf_panel5_brutal", 60, 402, 178)]
# высотки-блокауты за лесом: (x, z, длина, глубина, этажей, угол) — tools/build_zone01_blockouts.py skyline()
SKYLINE = [(-300, -370, 24, 24, 16, 0), (-40, -380, 60, 13, 12, 0), (130, -372, 24, 24, 14, 0), (320, -360, 60, 13, 9, 30),
           (370, -250, 24, 24, 16, 0), (380, -110, 60, 13, 12, 90), (372, 330, 24, 24, 12, 0), (250, 380, 60, 13, 9, 0),
           (-20, 385, 24, 24, 16, 0), (-240, 380, 60, 13, 12, 0), (-370, 330, 24, 24, 9, 0), (-380, -260, 60, 13, 12, 90),
           (-372, 200, 24, 24, 16, 0)]
PADS_BG = [(x - 30, z - 12, x + 30, z + 12) if abs(yaw) < 45 or abs(yaw) > 135 else (x - 12, z - 30, x + 12, z + 30)
           for _, x, z, yaw in BACKGROUND]
PADS_BG += [(x - (D if yaw > 45 else L) / 2 - 3, z - (L if yaw > 45 else D) / 2 - 3, x + (D if yaw > 45 else L) / 2 + 3,
             z + (L if yaw > 45 else D) / 2 + 3) for x, z, L, D, _, yaw in SKYLINE]
PADS_PAVED = PADS_BG + BUILDING_PADS
# не сажать деревья на готовые дома с сараями (дома развёрнуты: огороды к северу) и подход к мосту
KEEP_CLEAR = [(hx - 12, hz - 14, hx + 12, hz + 10) for hx, hz in HOUSES] + [(210, -167, 282, -155)]
# ремонтные дворы автобазы и пустырь до стоянки автобусов — без деревьев (левел-дизайн: открытый подход)
REPAIR_CLEAR = tuple(LAYOUT["repair_yard"]["clear"])
_rf = LAYOUT["repair_yard"]["fence"]
REPAIR_RECT = (min(q[0] for q in _rf), min(q[1] for q in _rf), max(q[0] for q in _rf), max(q[1] for q in _rf))
# двор хрущёвок — свой генератор деревьев и травы; рынок — свои площадки
YARD_RECT = tuple(v + d for v, d in zip((-285.0, -165.0, -135.0, -42.0), (*READY["yard05"]["move"], *READY["yard05"]["move"])))
MARKET_RECT = (min(p[0] for p in READY["market06"]["outline"]), min(p[1] for p in READY["market06"]["outline"]),
               max(p[0] for p in READY["market06"]["outline"]), max(p[1] for p in READY["market06"]["outline"]))


def in_rect(x: float, z: float, r) -> bool:
    return r[0] < x < r[2] and r[1] < z < r[3]


def build_vegetation(h: np.ndarray, splat: np.ndarray) -> None:
    """Деревья, подлесок и трава по всей карте (двор хрущёвок — свой генератор): точки в JSON для
    DistrictScatter. Лес — полосой у края квадрата и сплошь за ним, по склонам оврага, на кочках болота;
    внутри — деревья по зелени картинки (раскладка), трава — везде, где нет покрытия и голой грязи/щебня."""
    rng = np.random.default_rng(31)
    inside = inside_polygon(BOUNDARY)
    paved = np.zeros(GX.shape, bool)
    for rect in PADS_PAVED + KEEP_CLEAR + [MARKET_RECT]:
        paved |= rect_distance(*rect) < 2.0
    paved |= inside_polygon(POLY_PADS[1])  # площадка автостанции — асфальт и щебень
    for road in ROADS:
        pts = [(p[0], p[2]) for p in road["points"]]
        d, _ = polyline_distance(pts)
        paved |= d < road["width"] * 0.5 + road["sidewalk"] + 1.5
    d_track = track_distance()
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
            key = rng.choice(["birch_bare", "birch_bare", "birch_bare", "birch_young", "birch_c"])
        elif kind == "fir":
            key = rng.choice(["spruce_forest_a", "spruce_forest_a", "spruce_forest_b", "spruce_forest_b", "spruce_young_a", "spruce_young_b"])
        elif kind == "spruce_open":
            key = "spruce_open"
        elif kind == "birch":
            key = rng.choice(["birch_a", "birch_a", "birch_b", "birch_c", "birch_bare", "birch_bare", "birch_young"])
        else:
            key = f"tree_{kind}_{int(rng.integers(0, 3))}"
        trees[key].append([round(x, 2), round(sample(h, x, z) - 0.1, 3), round(z, 2), round(float(rng.uniform(0, 360)), 1),
                           round(float(rng.uniform(0.8, 1.2)), 3)])

    def ok(ix: int, iz: int) -> bool:
        return 0 <= ix < NX and 0 <= iz < NZ and not paved[iz, ix]

    # лес, склоны оврага, кочки болота, сплошной лес за границей — сеткой 6,5 м
    for gz in np.arange(Z0 + 4, Z0 + NZ - 4, 6.5):
        for gx in np.arange(X0 + 4, X0 + NX - 4, 6.5):
            x, z = gx + rng.uniform(-2.8, 2.8), gz + rng.uniform(-2.8, 2.8)
            ix, iz = int(x - X0), int(z - Z0)
            if not ok(ix, iz) or in_rect(x, z, YARD_RECT):
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
                put(rng.choice(["fir", "fir", "birch", "maple", "poplar"]), x, z)
    # деревья с картинки владельца: внутри квадрата по её зелени — дворы, обочины, пустыри
    for x, z in LAYOUT["trees"]:
        ix, iz = int(x - X0), int(z - Z0)
        if not ok(ix, iz) or in_rect(x, z, YARD_RECT) or forest[iz, ix] > 0.5 or 4.0 < d_rav[iz, ix] < 30.0:
            continue
        if swamp[iz, ix]:
            if dry[iz, ix] and rng.random() < 0.6:
                put("bog", x, z)
            continue
        if x < 0 and -95 < z < 100:  # дворы панелек — берёзы, клёны, тополя
            put(rng.choice(["birch", "birch", "maple", "maple", "poplar"]), x, z)
        else:
            put(rng.choice(["birch", "birch", "maple", "poplar", "spruce_open", "fir"]), x, z)
    add_pines(trees, h, forest, inside, d_rav)
    # подлесок: папоротник, валежник, пни, сухостой, корни — в лесу; камни со мхом — по склонам оврага
    under: dict[str, list] = {k: [] for k in ("forest_fern", "forest_dry_branches", "forest_stump_01", "forest_stump_02",
                                              "forest_dead_trunk", "forest_roots", "forest_rocks_01", "forest_rocks_02")}
    for gz in np.arange(Z0 + 3, Z0 + NZ - 3, 4.0):
        for gx in np.arange(X0 + 3, X0 + NX - 3, 4.0):
            x, z = gx + rng.uniform(-1.8, 1.8), gz + rng.uniform(-1.8, 1.8)
            ix, iz = int(x - X0), int(z - Z0)
            if not ok(ix, iz) or in_rect(x, z, YARD_RECT):
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
    near_edge = np.maximum(near_edge, (1.0 - smooth((d_track - 8.0) / 6.0)))

    def accept(x: float, z: float) -> bool:
        ix, iz = int(x - X0), int(z - Z0)
        if not (0 <= ix < NX and 0 <= iz < NZ) or paved[iz, ix] or in_rect(x, z, YARD_RECT):
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
    dens = np.clip(0.18 + 0.55 * smooth((patch - 0.35) / 0.35) + 0.4 * near_edge, 0.0, 1.0) * smooth((clump - 0.15) / 0.4)
    dens = (dens * (1.0 - 0.6 * forest) + 0.12 * forest) * np.where(inside, 1.0, 0.35)
    dens = np.where((mud > 0.4) | (gravel > 0.45) | (d_rav < 2.5) | paved, 0.0, dens)
    dens = dens * (1.0 - smooth((mud - 0.15) / 0.25) * 0.8)
    # болото: на кочках — густая высокая трава, в воде — ничего
    dens = np.where(swamp & dry, np.maximum(dens, 0.8), np.where(swamp, 0.0, dens))
    weeds = np.clip(0.3 + 0.7 * near_edge, 0.0, 1.0) * (dens > 0.05)
    img = np.stack([dens, weeds, np.zeros_like(dens)], -1) * 255.0
    # двор хрущёвок, рынок, дома у оврага — их прежняя густота (тротуары, проезды, стены, площадка)
    img = place_ready_maps(img, "grass")
    Image.fromarray(np.clip(img + 0.5, 0, 255).astype(np.uint8), mode="RGB").save(ROOT / "assets/terrain/zone01_grass.png")
    imp = ROOT / "assets/terrain/zone01_grass.png.import"
    if not imp.exists():
        imp.write_text(IMPORT_SPLAT.format(name="zone01_grass.png"), encoding="utf-8")
    # ремонтные дворы и пустырь до стоянки — без деревьев; во дворе (за забором) — и без подлеска
    for pts in trees.values():
        pts[:] = [q for q in pts if not in_rect(q[0], q[2], REPAIR_CLEAR)]
    for key, pts in under.items():
        if key not in ("grass", "weed"):
            pts[:] = [q for q in pts if not in_rect(q[0], q[2], REPAIR_RECT)]
    data = dict(trees)
    data.update(under)
    data["grass"] = []
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


# клёны и тополя (tools/zone01_trees): LOD0 до 45 м, LOD1 до 160 м, дальний силуэт до 900 м крупной клеткой; материалы свои;
# коллизия ствола — по радиусу экземпляра (у ясенелистного — общий низ трёх стволов)
TREES_Z1 = "res://assets/zone01/trees"
TREE_Z1_RADIUS = {"tree_maple_0": 0.22, "tree_maple_1": 0.13, "tree_maple_2": 0.18, "tree_poplar_0": 0.36, "tree_poplar_1": 0.44,
                  "tree_poplar_2": 0.16}


def z1_tree(key: str) -> dict:
    """Свойства узла DistrictScatter клёна / тополя зоны 1 (одни и те же в мире и во дворе)."""
    return dict(model=f"{TREES_Z1}/{key}_lod0.glb", mid_model=f"{TREES_Z1}/{key}_lod1.glb", far_model=f"{TREES_Z1}/{key}_far.glb",
                materials_dir=f"{TREES_Z1}/materials", mid_distance=45.0, near_distance=160.0, view_distance=900.0, cell=24.0,
                far_cell=128.0, trunk_radius=TREE_Z1_RADIUS[key])


def vegetation_nodes(s: "Scene") -> None:
    script = s.resource("res://src/world/district_scatter.gd", "Script")
    s.node("Vegetation")
    keys = [f"tree_{k}_{v}" for k in ("poplar", "maple") for v in range(3)]
    for key in keys:
        s.node(key.title().replace("_", ""), "Vegetation", script=script, data_path="res://data/zone01_vegetation.json",
               key=key, **z1_tree(key))
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
    """Лес полосой у края квадрата (неровно, 12–32 м) и сплошь за ним; дороги к выходам, пути и овраг — просеки."""
    n = fbm(50.0, 21)
    inside = inside_polygon(BOUNDARY)
    edge = polygon_edge_distance([tuple(p) for p in BOUNDARY])
    belt = 1.0 - smooth((edge - 12.0 - n * 20.0) / 8.0)
    mask = np.where(inside, belt, 1.0)
    for name, points, width, sidewalk, _ in ROAD_DEFS:
        d, _ = polyline_distance(points)
        mask *= smooth((d - width * 0.5 - sidewalk - 2.0) / 3.0)
    mask *= smooth((track_distance() - 4.0) / 4.0)
    d, _ = polyline_distance(RAVINE)
    mask *= smooth((d - 4.0) / 3.0)
    return np.clip(mask, 0.0, 1.0).astype(np.float32)

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
    def __init__(self, name: str, root_kind: str = "Node3D", groups=None):
        self.resources: dict[str, tuple[str, str]] = {}
        self.subs: list[str] = []
        root = f'[node name="{name}" type="{root_kind}"'
        if groups:
            root += " groups=" + gvalue(groups)
        self.nodes: list[str] = [root + "]"]

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
           excavations=Raw(yard_excavation()))
    s.node("Roads")
    for road in ROADS:
        if road.get("dirt"):
            continue  # грунтовка — колея в маске поверхностей, без асфальта
        raw = "PackedVector3Array(" + ", ".join(str(v) for p in road["points"] for v in p) + ")"
        s.node(road["id"].title(), "Roads", "res://scenes/world/urban_road.tscn", points=Raw(raw),
               carriage_width=road["width"], sidewalk_width=road["sidewalk"], sidewalks=road["sidewalk"] > 0,
               markings=False)  # старые улицы — разметка стёрлась (кадры картинки)
    s.node("Water")
    water = s.resource("res://src/world/district_water.gdshader", "Shader")
    body = s.resource("res://src/world/water_body.gd", "Script")  # глубина вброд, плеск, брызги
    noise_tex = gvalue(s.resource("res://assets/terrain/zone01_noise.png", "Texture2D"))
    mat = s.sub("ShaderMaterial", shader=water)
    s.subs[-1] += "\nshader_parameter/noise_tex = " + noise_tex
    # ручей по дну оврага — полосы вдоль русла чуть выше дна
    for i, ((ax, az), (bx, bz)) in enumerate(zip(RAVINE, RAVINE[1:])):
        ya = min(ground(ax, az), ground((ax + bx) / 2, (az + bz) / 2)) + 0.35
        length = math.dist((ax, az), (bx, bz)) + 2.0
        mesh = s.sub("PlaneMesh", size=v2(3.2, length), material=mat)
        s.node(f"Stream_{i}", "Water", kind="MeshInstance3D", script=body, mesh=mesh,
               position=v3((ax + bx) / 2, ya, (az + bz) / 2),
               rotation_degrees=v3(0, math.degrees(math.atan2(bx - ax, bz - az)), 0), cast_shadow=0)
    # болото: одна гладь на уровне SWAMP_WATER — кочки и берега выше неё, окна воды ниже; у болота свой
    # материал: карта глубины (мелко у берега — мутно, глубже — тёмная гладь) и ряска
    sx0, sz0 = min(p[0] for p in SWAMP), min(p[1] for p in SWAMP)
    sx1, sz1 = max(p[0] for p in SWAMP), max(p[1] for p in SWAMP)
    depth_png = swamp_depth_map(sx0, sz0, sx1, sz1)
    swamp_mat = s.sub("ShaderMaterial", shader=water)
    s.subs[-1] += ("\nshader_parameter/noise_tex = " + noise_tex +
                   "\nshader_parameter/depth_tex = " + gvalue(s.resource(depth_png, "Texture2D")) +
                   f"\nshader_parameter/depth_rect = Vector4({sx0}, {sz0}, {sx1 - sx0}, {sz1 - sz0})" +
                   f"\nshader_parameter/depth_max = {SWAMP_DEPTH_MAX}\nshader_parameter/duckweed = 0.25")
    mesh = s.sub("PlaneMesh", size=v2(sx1 - sx0, sz1 - sz0), material=swamp_mat, subdivide_width=16, subdivide_depth=12)
    s.node("Swamp", "Water", kind="MeshInstance3D", script=body, mesh=mesh,
           position=v3((sx0 + sx1) / 2, SWAMP_WATER, (sz0 + sz1) / 2), cast_shadow=0)
    perimeter(s)
    vegetation_nodes(s)
    s.save(OUT / "zone01_world.tscn")


SWAMP_DEPTH_MAX = 1.5


def swamp_depth_map(x0: float, z0: float, x1: float, z1: float) -> str:
    """Глубина под гладью болота (1 пиксель = 1 м, 255 = SWAMP_DEPTH_MAX) — для шейдера воды."""
    i0, j0 = int(x0 - X0), int(z0 - Z0)
    i1, j1 = int(x1 - X0) + 1, int(z1 - Z0) + 1
    depth = np.clip((SWAMP_WATER - H[j0:j1, i0:i1]) / SWAMP_DEPTH_MAX, 0.0, 1.0)
    path = ROOT / "assets/terrain/zone01_swamp_depth.png"
    Image.fromarray((depth * 255 + 0.5).astype(np.uint8), mode="L").save(path)
    imp = path.with_name(path.name + ".import")
    if not imp.exists():
        imp.write_text(IMPORT_SPLAT.format(name=path.name), encoding="utf-8")
    return "res://assets/terrain/zone01_swamp_depth.png"


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


# ------------------------------------------------------------------ постройки: готовые сцены, город за границей


def background(s: "Scene") -> None:
    s.node("Background")
    for i, (model, x, z, yaw) in enumerate(BACKGROUND):
        sf_model(s, f"Building_{i}", model, x, z, yaw, "Background", y=ground(x, z) - 0.3, surface="concrete")


def blockout_scene() -> None:
    """Город за границей и готовые рынок и дома у оврага — их сцены в прежних координатах, на новом месте
    их ставит сдвиг / поворот экземпляра (дорожки и россыпь внутри — local_points)."""
    s = Scene("Blockout")
    background(s)
    if (OUT / "zone01_market06.tscn").exists():
        s.node("Z06_Market", scene="res://scenes/levels/zone01/zone01_market06.tscn", **instance_attrs("market06"))
    else:
        print("zone01: нет сцены рынка zone01_market06.tscn — tools/author_zone01_nw.py")
    if (OUT / "zone01_houses12.tscn").exists():
        s.node("Z12_Ravine", scene="res://scenes/levels/zone01/zone01_houses12.tscn", **instance_attrs("houses12"))
    else:
        print("zone01: нет сцены домов zone01_houses12.tscn — tools/author_zone01_nw.py")
    s.save(OUT / "zone01_blockout.tscn")


# ------------------------------------------------------------------ данные сектора и главная сцена

SPAWNS = [("Запад", -292, -150), ("За болотом", -130, -292), ("Северная просека", 120, -222),
          ("Из-за путей", 292, 30), ("Южная лесополоса", -95, 294), ("Юго-запад", -292, 210)]
# «Старый мост» — за мостом через овраг, там же, где был выход «Мост через овраг» (на новом месте домов)
_BRIDGE_EXIT = ready_new("houses12", -386, 40)
EXTRACTS = [("Лесная дорога", -292, -287, ""), ("Служебная дорога", -262, 292, ""), ("Ж/д пути", 205, 294, ""),
            ("Старый мост", round(_BRIDGE_EXIT[0], 1), round(_BRIDGE_EXIT[1], 1), ""), ("Автостанция", -40, 214, ""),
            ("К ТЦ", 296, -50, "")]
AI_POINTS = [(-170, -10), (-190, 170), (185, -150), (-120, -200), (-60, 10), (60, -120), (110, -60), (60, 75),
             (120, 125), (-20, 190), (30, 255), (210, 120), (180, 185), (200, 50), (60, -205), (-230, 255), (-255, -255)]


def _bbox(points) -> tuple[float, float, float, float]:
    return (round(min(p[0] for p in points)), round(min(p[1] for p in points)),
            round(max(p[0] for p in points)), round(max(p[1] for p in points)))


ROOMS = [("yard05", "Двор хрущёвок", tuple(v + d for v, d in zip((-228, -126, -160, -55), (*READY["yard05"]["move"], *READY["yard05"]["move"])))),
         ("market", "Рынок", _bbox(READY["market06"]["outline"])),
         ("houses", "Дома у оврага", _bbox([ready_new("houses12", x, z) for x, z in ((-300, -8), (-262, 60))])),
         ("swamp", "Болото", _bbox(SWAMP)),
         ("second_yard", "Панельки", (-125, -45, -15, 95)),
         ("construction", "Недострой", _bbox(LAYOUT["site"])),
         ("sports", "Спортплощадка", (14, 25, 68, 64)),
         ("blocks", "Корпуса у спортплощадки", (75, 30, 150, 165)),
         ("bus_station", "Автостанция", (-124, 114, 60, 255)),
         ("station", "Ж/д станция", (170, 75, 290, 260)),
         ("garages", "Гаражи у путей", (180, 28, 215, 68)),
         ("center", "Универсам и администрация", (0, -10, 70, 110)),
         ("repair", "Ремонтные дворы автобазы", (60, 256, 186, 296)),
         ("north", "Техкорпус", (20, -235, 95, -200))]


# ------------------------------------------------------------------ население: посты, маршруты, гнёзда, подходы
# (сцена zone01_ai.tscn, слой extras сектора; район поста — id из ROOMS, только для журнала)

AI_POSTS = [
    # имя, x, z, район, вес, всегда с N игроков, радиус, группа
    ("Post_yard05", -176, 2, "yard05", 1.0, 0, 22, None),
    ("Post_market_hangar", -213, 163, "market", 2.0, 1, 16, None),
    ("Post_market_rows", -171, 237, "market", 2.0, 2, 18, None),
    ("Post_houses", 190, -155, "houses", 0.6, 0, 16, None),
    ("Post_bus_station", -30, 170, "bus_station", 1.5, 0, 22, None),
    ("Post_depot", 15, 205, "bus_station", 1.0, 0, 18, None),
    ("Post_station", 200, 135, "station", 1.0, 0, 20, None),
    ("Post_construction", 75, -110, "construction", 1.2, 0, 22, None),
    ("Post_garages", 200, 48, "garages", 1.0, 0, 18, None),
    ("Post_second_yard", -52, 2, "second_yard", 0.6, 0, 18, None),
    ("Post_sports", 45, 45, "sports", 0.6, 0, 20, (1, 2)),
    ("Post_swamp_edge", -150, -95, "swamp", 0.5, 0, 14, (1, 2)),
    ("Post_north", 60, -200, "north", 0.6, 0, 16, (1, 2)),
    # левел-дизайн 2026-10-19: середина и ремонтные дворы (бригада заказа «Вернуть машину» — отдельно)
    ("Post_supermarket", 35, 27, "center", 0.8, 0, 18, None),
    ("Post_admin", 22, 102, "center", 0.6, 0, 16, (1, 2)),
    ("Post_cinema", 100, 128, "blocks", 0.7, 0, 18, (1, 3)),
    ("Post_repair", 120, 278, "repair", 1.2, 0, 20, None),
]
AI_ROUTES = [
    ("Route_north", "Северный: улица у болота — двор — стройка — дома у оврага",
     [(-200, -82), (-128, -85), (-58, -62), (12, -36), (82, -13), (155, -2), (156, -60), (155, -150)]),
    ("Route_west", "Западный: двор — панельки — рынок",
     [(-176, 25), (-150, 72), (-184, 99), (-205, 140), (-170, 200), (-235, 230)]),
    ("Route_east", "Восточный: дорога к ТЦ — станция — автостанция",
     [(200, -66), (156, 0), (154, 70), (148, 140), (100, 165), (20, 150), (-40, 170)]),
    ("Route_south", "Южный: рынок — автостанция — ремонтные дворы — дорога к путям",
     [(-150, 105), (-60, 103), (5, 140), (55, 262), (100, 265), (150, 270), (190, 271)]),
]
AI_NESTS = [
    # имя, подпись, x, z, куда смотрит (поворот), вес, сектор
    ("Nest_rail_bridge", "Насыпь у моста к ТЦ", 268, -25, 90.0, 0.8, 75),
    ("Nest_rail_station", "Насыпь у станции", 236, 172, 90.0, 0.8, 75),
    ("Nest_ravine_rim", "Бровка оврага у стройки", 100, -242, 180.0, 0.6, 70),
]
AI_ARRIVALS = [("Arrive_nw", "Лесная дорога", -275, -200), ("Arrive_ravine_n", "Бровка оврага у болота", 60, -240),
               ("Arrive_east", "За путями", 290, 110), ("Arrive_se", "Южная лесополоса", -20, 294),
               ("Arrive_sw", "За рынком", -200, 290), ("Arrive_west", "Западный лес", -292, 40)]


def ai_scene() -> None:
    s = Scene("Zone01AI")
    post, route = "res://scenes/world/ai_post.tscn", "res://scenes/world/ai_route.tscn"
    nest, arrival = "res://scenes/world/ai_nest.tscn", "res://scenes/world/ai_arrival.tscn"
    s.node("Posts")
    for name, x, z, district, weight, always, radius, group in AI_POSTS:
        attrs = dict(position=v3(x, ground(x, z) + 0.3, z), district=district, radius=radius)
        if weight != 1.0:
            attrs["weight"] = weight
        if always:
            attrs["always_from"] = always
        if group:
            attrs["group_size"] = Raw(f"Vector2i({group[0]}, {group[1]})")
        s.node(name, "Posts", post, **attrs)
    s.node("Routes")
    for name, title, pts in AI_ROUTES:
        s.node(name, "Routes", route, title=title)
        for i, (x, z) in enumerate(pts, 1):
            s.node(f"P{i:02}", f"Routes/{name}", kind="Marker3D", position=v3(x, ground(x, z) + 0.3, z))
    s.node("Nests")
    for name, title, x, z, yaw, weight, sector in AI_NESTS:
        s.node(name, "Nests", nest, position=v3(x, ground(x, z) + 0.5, z), rotation_degrees=v3(0, yaw, 0),
               title=title, weight=weight, sector_deg=sector, radius=3)
    s.node("Arrivals")
    for name, title, x, z in AI_ARRIVALS:
        s.node(name, "Arrivals", arrival, position=v3(x, ground(x, z) + 0.4, z), title=title)
    s.save(OUT / "zone01_ai.tscn")


def move_yard_loose_loot() -> None:
    """Находки у гаражей двора лежат в общей сцене россыпи (не в сцене двора) — сдвинуть вместе с двором.
    Сдвигаются только точки, стоящие на прежнем месте гаражного ряда (x = −264,5)."""
    path = OUT / "zone01_loose_loot.tscn"
    if not path.exists():
        return
    dx, dz = READY["yard05"]["move"]
    lines = path.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -264.5, "):
            vals = line[len("transform = Transform3D("):-1].split(", ")
            x, y, z = float(vals[9]), float(vals[10]), float(vals[11])
            lines[i] = f"transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {x + dx:g}, {y:g}, {z + dz:g})"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def layout_scene() -> None:
    """Блокауты построек раскладки (tools/build_zone01_blockouts.py)."""
    import sys

    import build_zone01_blockouts as blockouts
    blockouts.build(sys.modules[__name__], LAYOUT)


# ------------------------------------------------------------------ заказ «Вернуть машину»: места на карте

# ангар № 8 — машина Ильи носом к воротам (на север); точки — в осях машины: перёд +Z, левый борт +X
CAR_AT = (100.0, 276.5)
CAR_SITES = [
    # site_id, x, z (оси машины), поворот, назначение
    ("car_belt_hangar", 0.0, 0.0, 0.0, "ангар № 8: машина Ильи, вокруг — бригада заказа"),
    ("car_belt_car_body", 2.6, -0.8, 0.0, "съёмка кузова и треснувшей накладки на левом пороге"),
    ("car_belt_car_marking", -1.7, -0.4, 0.0, "съёмка заводской маркировки на правой стойке"),
    ("car_belt_photo_engine", 0.0, 3.3, 0.0, "съёмка подкапотного пространства спереди"),
    ("car_belt_photo_radiator", 0.9, 3.0, 0.0, "съёмка места радиатора"),
    ("car_belt_photo_wheel", 1.8, 1.44, 0.0, "съёмка колёсной ниши переднего левого"),
    ("car_belt_car_wheel", 1.8, 2.4, 0.0, "установка колеса"),
    ("car_belt_car_battery", -1.5, 1.2, 0.0, "установка аккумулятора справа под капотом"),
    ("car_belt_photo_wiring", -1.5, 0.2, 0.0, "съёмка проводки у аккумулятора"),
    ("car_belt_delivery", 7.4, -4.0, -90.0, "ящик у задней части машины: радиатор кладут на его верх"),
]
# кладовая и район поиска — в осях карты
SITES_WORLD = [
    ("car_belt_parts_radiator", 131.7, 266.4, -90.0, "Storeroom", "кладовая: радиатор с патрубками, бирка «ЮР / 8»"),
    ("car_belt_parts_wheel", 131.7, 269.0, -90.0, "Storeroom", "кладовая: колесо, бирка «ЮР / 8»"),
    ("car_belt_search", 120.0, 276.0, 0.0, "", "центр района ремонтных дворов, радиус 60 м"),
]


def building_floor(bid: str) -> float:
    """Пол постройки раскладки — как его ставит генератор блокаутов (низший угол минус 5 см)."""
    import build_zone01_blockouts as blockouts
    b = next(q for q in LAYOUT["buildings"] if q["id"] == bid)
    x, z = b["at"]
    return min(ground(x + dx, z + dz) for dx, dz in blockouts.corners(0, 0, b["size"][0], b["size"][1], b["angle"])) - 0.05


def car_sites_scene() -> None:
    """Места заказа «Вернуть машину» в Пригороде (docs/tasks/car_recovery_maps.md §6): ангар № 8 с машиной
    Ильи (вид по состоянию заказа — src/quests/car_hangar.gd), точки QuestAnchor, кладовая, бокс № 5 для
    исключения по приметам. Реестр — data/quest_sites/car_recovery_belt.json."""
    s = Scene("CarRecoverySites", groups=["nav_source"])
    anchor = s.resource("res://src/quests/quest_anchor.gd", "Script")
    hy = building_floor("Hangar_8")
    cx, cz = CAR_AT
    s.node("Hangar8", script=s.resource("res://src/quests/car_hangar.gd", "Script"), position=v3(cx, hy, cz),
           rotation_degrees=v3(0, 180, 0))
    s.node("IlyaCar", "Hangar8", "res://scenes/props/coupe_ilya.tscn", hood_open=True)
    # корпус машины — простая коллизия (у сцены модели её нет): пули, игрок, навигация
    s.node("CarBody", "Hangar8", kind="StaticBody3D", collision_mask=0)
    s.node("Shape", "Hangar8/CarBody", kind="CollisionShape3D", position=v3(0, 0.78, -0.08),
           shape=s.sub("BoxShape3D", size=v3(2.08, 1.22, 4.86)))
    registry = []
    for sid, lx, lz, yaw, purpose in CAR_SITES:
        ly = 1.0 if sid == "car_belt_delivery" else 0.05
        s.node(sid, "Hangar8", kind="Marker3D", script=anchor, site_id=sid, position=v3(lx, ly, lz),
               rotation_degrees=v3(0, yaw, 0))
        wx, wz = cx - lx, cz - lz
        registry.append({"id": sid, "node": f"Hangar8/{sid}", "position": [round(wx, 2), round(hy + ly, 2), round(wz, 2)],
                         "yaw": round((180.0 + yaw) % 360.0, 1), "purpose": purpose})
    s.node("Sites")
    for sid, wx, wz, yaw, bid, purpose in SITES_WORLD:
        wy = building_floor(bid) + 0.05 if bid else ground(wx, wz) + 0.05
        s.node(sid, "Sites", kind="Marker3D", script=anchor, site_id=sid, position=v3(wx, wy, wz),
               rotation_degrees=v3(0, yaw, 0))
        registry.append({"id": sid, "node": f"Sites/{sid}", "position": [wx, round(wy, 2), wz], "yaw": yaw, "purpose": purpose})
    # бокс № 5 — другая машина на разборке: окружение, квест его не проверяет
    b5 = next(q for q in LAYOUT["buildings"] if q["id"] == "Box_5")
    s.node("car_belt_candidate", "Sites", kind="Marker3D", position=v3(b5["at"][0], building_floor("Box_5") + 0.05, b5["at"][1]))
    registry.append({"id": "car_belt_candidate", "node": "Sites/car_belt_candidate", "position": [b5["at"][0], 0.0, b5["at"][1]],
                     "purpose": "бокс № 5: другая машина на разборке, для исключения по приметам (не место квеста)"})
    s.save(OUT / "zone01_car_recovery_sites.tscn")
    data = {
        "_comment": "Места заказа «Вернуть машину» в Пригороде (зона 1): сцена, узлы, позиции, подходы. Генератор — "
                    "tools/build_zone01.py (car_sites_scene). Игра читает только QuestAnchor в сцене; этот файл — для людей и проверок.",
        "map": "Пригород (зона 1)", "level": "zone01_mall",
        "scene": "res://scenes/levels/zone01/zone01_car_recovery_sites.tscn",
        "reference": "docs/design/concepts/urban_belt_2026-10-15/01_urban_belt_starting_concept.png",
        "design": "docs/design/zone01_level_design.md §6",
        "area": {"name": "Ремонтные дворы автобазы", "fence": LAYOUT["repair_yard"]["fence"],
                 "gaps": LAYOUT["repair_yard"]["gaps"], "clear": LAYOUT["repair_yard"]["clear"]},
        "approaches": [
            {"name": "открытый", "from": "стоянка автобусов (запад)", "via": "пустырь, проход в заборе x 62, z 275"},
            {"name": "прикрытый", "from": "дорога к путям, насыпь (восток)", "via": "гаражи у дороги, проход x 184, z 271"},
            {"name": "наблюдение", "from": "эстакада (север, 9,5 м)", "via": "видно двор и ворота ангара № 8"},
            {"name": "под эстакадой", "from": "Южная улица", "via": "проходы x 80 и x 142 в северном заборе"},
        ],
        "camera": {"overpass": [100.0, 12.1, 255.0], "look_at": [100.0, 1.0, 274.0]},
        "limits": ["без вождения и NPC при машине", "машина меняет вид только по состоянию заказа",
                   "обычный выход «Автостанция» всегда открыт"],
        "sites": registry,
    }
    out = ROOT / "data/quest_sites/car_recovery_belt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def main_scene() -> None:
    s = Scene("Zone01_Mall")
    s.nodes[0] += "\nscript = " + gvalue(s.resource("res://src/world/sector_level.gd", "Script")) + f'\nsector_path = "{SECTOR}"'
    s.node("World", scene="res://scenes/levels/zone01/zone01_world.tscn")
    s.node("Blockout", scene="res://scenes/levels/zone01/zone01_blockout.tscn")
    s.node("Yard05", scene="res://scenes/levels/zone01/zone01_yard05.tscn", **instance_attrs("yard05"))
    s.node("Layout", scene="res://scenes/levels/zone01/zone01_layout.tscn")
    s.node("CarRecovery", scene="res://scenes/levels/zone01/zone01_car_recovery_sites.tscn")
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
        id="zone01_mall", name="Зона 1 · Пригород", layout="cartesian_scene", greybox=True,
        bounds=[X0, Z0, X0 + (NX - 1) * STEP, Z0 + (NZ - 1) * STEP], boundary=BOUNDARY, area_m2=area,
        units="metres", north="-Z", spawn=[x, round(ground(x, z) + .2, 3), z], camera_yaw=180,
        nav_cache="res://data/navigation/zone01",
        # свет: больше рассеянного неба, солнце мягче — тени читаются, свет не «выжигает»
        light=dict(ambient_k=1.9, sun_k=0.8, ambient_k_dusk=1.9, ambient_k_day_rain=2.4, ambient_k_dusk_rain=2.4, ambient_k_night_rain=4.2, ambient_k_night_fog=2.2,
                   ambient_k_day_overcast=2.2, ambient_k_dusk_overcast=2.2, ambient_k_night_overcast=3.6),
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
            # пасмурно (сырой вечер с картинки — одна из погод): те же пасмурные панорамы, солнце едва пробивается
            day_overcast=dict(a="res://assets/sky/kloofendal_overcast_puresky.hdr", exposure=1.0, sun_k=0.35, veil=0.6, haze=0.45),
            dusk_overcast=dict(a="res://assets/sky/kloppenheim_01_puresky.hdr", exposure=1.0, sun_k=0.4, veil=0.6, haze=0.45),
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
    layout_scene()
    car_sites_scene()
    ai_scene()
    move_yard_loose_loot()
    main_scene()
    write_definition(H)
    # превью высот для документации
    norm = (H - H.min()) / (H.max() - H.min())
    Image.fromarray((norm * 255).astype(np.uint8)).save(ROOT / "docs/plans/zone01_heights.png")


if __name__ == "__main__":
    main()
