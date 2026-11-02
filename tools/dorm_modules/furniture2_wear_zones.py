"""Мебель общежития, партия 2 (кухня, умывальня, туалеты), износ (этап 2): места в развёртке по картам геометрии
print_bake.py (положение и нормаль каждого пикселя в осях корня набора, метры). Рисунок следа кладёт Painter
(sp_furniture2_wear.py) — эти карты ограничивают место, а потёки, налёт и трещины глазури рисуют сами.

  python -X utf8 tools/dorm_modules/furniture2_wear_zones.py [набор …]   # → _asset_src/dorm_furniture2/wear/<набор>_<зона>.png

Интервью 2026-11-02: степень — как у мебели комнат (долго жили, потом бросили); плита — жир и нагар, сколы эмали
плиты и мойки с ржавчиной; тумбы — разбухшая ДСП у мойки, сбитые кромки, облупленная краска, на столешницах пятна,
порезы, кольца и прожоги; умывальня и туалеты — налёт и ржавые потёки, сколы и трещины фаянса, краска кабинок и трубы
облуплена слоями, грязь в чашах и у пола. Закопчённой посуды и ржавчины на чугуне нет.
Зоны: edge — выпуклые рёбра, 1,5–10 мм от ребра (сколы, стёртые кромки: генератор кривизны Painter на панелях давал
полосу в ладонь шириной); up — грани к небу (пыль); floor — низ до 18 см у стоящего на полу; hits — где бьют (сколы); rust_low — касание
пола; touch — у ручек и где берут; grease / burnt — жир на верху плиты и пригар вокруг конфорок; oven — копоть
камеры; drain — ржавчина у выпуска мойки; swell — разбухшая ДСП; stains / rings / burns / burn_ring / cuts — следы на
столешницах; wet — где стекает вода с посуды; streak / scale / bowl / craze — потёки, налёт, грязь в чаше и сетка
трещин глазури; drip — ржавые потёки по чугуну и трубе; torn — рваный конец трубы; peel — где краска кабинок
облуплена; kick — низ дверцы кабинки (обувь); desilver / spots — зеркало темнеет по краям, брызги.
Координаты — размеры build_furniture2.py; детали, сдвинутые на время текстур (furniture2_uv.OFFSETS), возвращаются
на место до расчёта.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # карты геометрии — EXR; до первого import cv2
import cv2
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import print_apply as P  # noqa: E402
from furniture_wear_zones import disc, rings  # noqa: E402
from wear_zones import blobs, noise, smooth  # noqa: E402

BASE = HERE.parents[1] / "_asset_src" / "dorm_furniture2"
ITEMS = ["furn_stove", "furn_sink", "furn_counter", "furn_dining", "furn_wallcab", "furn_dishrack", "furn_pot",
         "furn_kettle", "furn_pan", "furn_can", "furn_bucket", "furn_basin", "furn_mirror", "furn_toilet", "furn_stall"]
ON_FLOOR = ("furn_stove", "furn_sink", "furn_counter", "furn_dining", "furn_can", "furn_bucket", "furn_toilet", "furn_stall")


def offsets() -> dict:
    """furniture2_uv.OFFSETS без импорта (тот модуль требует bpy)."""
    tree = ast.parse((HERE / "furniture2_uv.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "OFFSETS")
    return ast.literal_eval(node.value)


def load(game: str):
    g = P.load_geo(BASE, game)
    for name, off in offsets().get(game, {}).items():
        m = P.part_mask(g, name)
        g["pos"][m] -= np.array(off, np.float32)
    return g


def parts(g, *prefixes) -> np.ndarray:
    """Пиксели деталей, имя которых (до «__») — одно из prefixes; с «__» в префиксе — точное имя."""
    ids = [k for k, v in g["names"].items() if any(v == p or ("__" not in p and v.split("__")[0] == p) for p in prefixes)]
    return np.isin(g["part_id"], ids)


def core(mask, px=2):
    """Без края островов: поля развёртки за кромкой острова несут чужое положение — ореол и пятна от них ложились
    в случайные места (самопроверка 2026-11-02)."""
    return cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=px).astype(bool)


def near(g, mask, r, sub=6):
    """Близость к деталям mask в пространстве (ореол вокруг ручек: где их берут, пачкают соседнюю поверхность)."""
    pts = g["pos"][core(mask)][::sub]
    if not len(pts):
        return np.zeros(mask.shape, np.float32)
    valid = g["part_id"] > 0
    d = np.full(mask.shape, 9.0, np.float32)
    d[valid] = cKDTree(pts).query(g["pos"][valid], distance_upper_bound=r * 2)[0]
    return (1 - smooth(np.minimum(d, 9.0), r * 0.25, r)).astype(np.float32)


def scatter(g, mask, n, rmin, rmax, seed):
    """Разбросанные пятна по деталям mask (удары, сколы)."""
    rng = np.random.default_rng(seed)
    pts = g["pos"][core(mask)]
    if not len(pts):
        return np.zeros(mask.shape, np.float32)
    centers = [(tuple(pts[i]), float(rng.uniform(rmin, rmax))) for i in rng.integers(0, len(pts), n)]
    return blobs(g, centers, seed + 3) * mask


def vnoise(x, y, cell, seed):
    """Плавный шум по двум координатам пространства (метры): решётка случайных чисел, билинейно."""
    rng = np.random.default_rng(seed)
    lat = rng.random((257, 257)).astype(np.float32)
    fx, fy = x / cell, y / cell
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    tx, ty = smooth(fx - ix, 0, 1), smooth(fy - iy, 0, 1)
    ix, iy = ix % 256, iy % 256
    a, b = lat[iy, ix], lat[iy, ix + 1]
    c, d = lat[iy + 1, ix], lat[iy + 1, ix + 1]
    return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty


def fbm(g, cells=(0.07, 0.03, 0.012, 0.005), seed=0):
    """Многослойный шум по поверхности (0…1): координаты — плоскость, поперёк главной оси нормали (у кабинок, зеркала,
    плоских панелей — без растяжений)."""
    pos, nrm = g["pos"], g["nrm"]
    ax = np.argmax(np.abs(nrm), axis=-1)
    u = np.where(ax == 0, pos[..., 1], pos[..., 0])
    v = np.where(ax == 2, pos[..., 1], pos[..., 2])
    out = np.zeros(u.shape, np.float32)
    amp, tot = 1.0, 0.0
    for k, c in enumerate(cells):
        out += amp * vnoise(u + 13.7 * k, v + 7.1 * k, c, seed + k)
        tot += amp
        amp *= 0.55
    return out / tot


def flakes(g, density, thr, seed, soft=0.012):
    """Чешуйки облупленной краски: шум плюс плотность места выше порога — края неровные и резкие, чем гуще место,
    тем крупнее и чаще чешуйки."""
    return smooth(fbm(g, seed=seed) + 0.45 * density - thr, 0.0, soft)


def inside(pos, rings_zabp, grow=1.04):
    """Внутри чаши: точка в сечении-суперэллипсе внутреннего контура на своей высоте (кольца лофта build_furniture2)."""
    r = sorted(rings_zabp)
    zs = np.array([q[0] for q in r], np.float32)
    a, b, cy, p = (np.interp(pos[..., 2], zs, [q[k] for q in r]) for k in (1, 2, 3, 4))
    u = np.abs(pos[..., 0]) / (a * grow) + 1e-6
    v = np.abs(pos[..., 1] - cy) / (b * grow) + 1e-6
    return (u ** p + v ** p <= 1.0) & (pos[..., 2] >= zs[0] - 0.003) & (pos[..., 2] <= zs[-1] + 0.002)


def px_per_mm(g, mask) -> float:
    """Плотность развёртки на деталях mask: соседние пиксели — сколько миллиметров между ними."""
    pos = g["pos"]
    d = np.linalg.norm(pos[:, 1:] - pos[:, :-1], axis=-1)
    ok = mask[:, 1:] & mask[:, :-1] & (d < 0.01)
    return float(1.0 / (np.median(d[ok]) * 1000.0)) if ok.any() else 1.0


def craze(g, mask, cell, width, seed):
    """Сетка трещин глазури (кракелюр): границы ячеек Вороного в пространстве, тонкие, пятнами гуще."""
    pos = g["pos"]
    pts = pos[mask]
    out = np.zeros(mask.shape, np.float32)
    if not len(pts):
        return out
    rng = np.random.default_rng(seed)
    lo, hi = pts.min(0) - cell, pts.max(0) + cell
    grid = np.stack(np.meshgrid(*[np.arange(lo[k], hi[k], cell) for k in range(3)], indexing="ij"), -1).reshape(-1, 3)
    seeds = grid + rng.uniform(0, cell, grid.shape) * rng.uniform(0.6, 1.4, (len(grid), 1))
    d, _ = cKDTree(seeds).query(pts, k=2)
    edge = 1 - smooth(d[:, 1] - d[:, 0], 0.0, width)
    # трещины пятнами: сплошная сетка по всему фаянсу читалась грязной сеткой
    patch = smooth(noise(*mask.shape, 160, seed + 7), 0.45, 0.75)
    out[mask] = edge * patch[mask]
    return out


def bowl_streaks(pos, inner, axis_xy, n, width, z_top, z_bot, seed, back=0.0):
    """Потёки под ободком чаши: полосы от верха вниз по внутренней стенке (вода из-под ободка), к низу слабее;
    back — сзади (к стене, +Y) гуще."""
    rng = np.random.default_rng(seed)
    dx, dy = pos[..., 0] - axis_xy[0], pos[..., 1] - axis_xy[1]
    ang = np.arctan2(dy, dx)
    rad = np.hypot(dx, dy)
    out = np.zeros(pos.shape[:2], np.float32)
    for k in range(n):
        a0 = rng.uniform(-np.pi, np.pi)
        w = width * rng.uniform(0.6, 1.5)
        da = np.angle(np.exp(1j * (ang - a0)))
        along = np.clip((z_top - pos[..., 2]) / (z_top - z_bot), 0, 1)
        fade = (1 - along) ** rng.uniform(0.6, 1.6)
        weight = rng.uniform(0.5, 1.0) * (1 + back * max(0.0, np.sin(a0)))
        out = np.maximum(out, np.exp(-((da * rad) / w) ** 2) * fade * min(weight, 1.0))
    return out * inner


def drip(pos, mask, sources, length, cell, seed):
    """Ржавые потёки по вертикальной поверхности: столбцы по горизонтали (шум), от источников (низ рёбер, край) вниз
    затухают; у самого источника — полоса ржавчины."""
    z = pos[..., 2]
    col = smooth(vnoise(pos[..., 0] + 3.1, pos[..., 1] + 7.7, cell, seed), 0.55, 0.78)
    lng = length * (0.4 + 1.2 * vnoise(pos[..., 0] + 1.3, pos[..., 1] + 2.9, cell * 1.7, seed + 1))
    src = np.sort(np.array(sources, np.float32))
    idx = np.searchsorted(src, z)                 # ближайший источник выше точки
    above = src[np.clip(idx, 0, len(src) - 1)]
    dz = np.where(idx < len(src), above - z, 9.0)
    trail = col * np.exp(-dz / np.maximum(lng, 1e-3))
    band = np.exp(-(dz / 0.006) ** 2) * (0.5 + 0.5 * vnoise(pos[..., 0], pos[..., 1], cell * 0.5, seed + 2))
    return np.clip(np.maximum(trail, band), 0, 1) * mask


def edge_zone(g, w0=0.0015, w1=0.010, sub=2):
    """Близость к выпуклому ребру: грани делятся по главной оси нормали (±X, ±Y, ±Z); у каждого пикселя — ближайший
    пиксель другой грани; ребро выпуклое, если та грань лежит позади касательной плоскости (вогнутые углы — грязь,
    а не износ)."""
    pos, nrm = g["pos"], g["nrm"]
    valid = core(g["part_id"] > 0)   # поля развёртки с чужим положением давали точки посреди дверец
    ax = np.argmax(np.abs(nrm), axis=-1)
    cls = ax * 2 + (np.take_along_axis(nrm, ax[..., None], -1)[..., 0] > 0)
    # опорные пиксели граней — только где вокруг та же ориентация: одиночные пиксели с чужой нормалью на лице панели
    # давали круглые пятна «ребра» посреди дверец
    steady = np.zeros(valid.shape, bool)
    for c in range(6):
        mc = (valid & (cls == c)).astype(np.float32)
        steady |= (mc > 0) & (cv2.boxFilter(mc, -1, (5, 5)) > 0.6)
    out = np.zeros(valid.shape, np.float32)
    pts, n_all, c_all, st_all = pos[valid], nrm[valid], cls[valid], steady[valid]
    res = np.zeros(len(pts), np.float32)
    for c in np.unique(c_all):
        me = c_all == c
        other = np.flatnonzero(~me & st_all)[::sub]
        if not len(other):
            continue
        d, i = cKDTree(pts[other]).query(pts[me], distance_upper_bound=w1 * 2)
        hit = np.isfinite(d)
        q = np.zeros((me.sum(), 3), np.float32)
        q[hit] = pts[other][i[hit]]
        convex = np.einsum("ij,ij->i", q - pts[me], n_all[me]) < 0.0005
        res[me] = np.where(hit & convex, 1 - smooth(np.where(hit, d, 9.0), w0, w1), 0.0)
    out[valid] = res
    return out


def zones(game: str) -> None:
    g = load(game)
    valid = g["part_id"] > 0
    pos, nrm = g["pos"], g["nrm"]
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    h = z - z[valid].min()
    hmax = h[valid].max()
    shp = h.shape
    maps = {"up": smooth(nrm[..., 2], 0.15, 0.75), "edge": edge_zone(g)}
    if game in ON_FLOOR:
        maps["floor"] = 1 - smooth(h, 0.04, 0.18)

    if game == "furn_stove":
        enamel = parts(g, "Плита_эмаль")
        top = (z > 0.845) & (nrm[..., 2] > 0.7)
        burners = (((-0.11, -0.1), 0.09), ((0.12, -0.12), 0.0725), ((-0.12, 0.14), 0.0725), ((0.11, 0.12), 0.09))
        burnt = np.zeros(shp, np.float32)
        near_b = np.zeros(shp, np.float32)
        for (bx, by), rad in burners:
            rr = np.hypot(x - bx, y - by)
            burnt = np.maximum(burnt, np.exp(-((rr - rad - 0.032) / 0.014) ** 2))
            near_b = np.maximum(near_b, 1 - smooth(rr, rad + 0.02, rad + 0.11))
        nz = noise(*shp, 40, 3)
        maps["burnt"] = burnt * top * enamel * (0.55 + 0.45 * nz)
        # жир — по всему верху, гуще у конфорок; брызги на заднем борту спереди
        splash = (y > 0.27) & (nrm[..., 1] < -0.5) & (z > 0.85)
        maps["grease"] = np.maximum(top * (0.45 + 0.55 * near_b), splash * (1 - smooth(z, 0.86, 0.93))) * (0.6 + 0.4 * nz)
        maps["oven"] = parts(g, "Духовка_эмаль") * (0.45 + 0.55 * (1 - smooth(z, 0.22, 0.45)))
        front_low = (nrm[..., 1] < -0.6) & (h < 0.12)
        edges = (z > 0.8) & ((np.abs(x) > 0.225) | (y < -0.265))
        door_edge = parts(g, "Плита_эмаль__дверца") & ((z > 0.56) | (np.abs(x) > 0.2))
        maps["hits"] = np.maximum.reduce([front_low * smooth(noise(*shp, 50, 12), 0.3, 0.7), edges * 0.6, door_edge * 0.5])
        # отбито на плоском — только точками ударов (полосой по всей панели читалось гранитом, самопроверка)
        maps["impact"] = scatter(g, enamel | parts(g, "Плита_эмаль__дверца"), 14, 0.012, 0.03, 11)
        maps["rust_low"] = (1 - smooth(h, 0.006, 0.05)) * (0.6 + 0.4 * noise(*shp, 48, 23))
        knobs = np.zeros(shp, np.float32)
        for k in range(5):
            knobs = np.maximum(knobs, 1 - smooth(np.linalg.norm(pos - np.array((-0.18 + k * 0.09, -0.29, 0.805)), axis=-1),
                                                 0.02, 0.05))
        # ручка духовки — хром на дверце (Ручка_металл у плиты — решётка и ТЭН в камере)
        maps["touch"] = np.maximum(knobs, near(g, parts(g, "Хром__дверца"), 0.06) * (z > 0.45))

    if game == "furn_sink":
        sink = parts(g, "Мойка_эмаль")
        cx, cyb, top = -0.15, -0.03, 0.85
        rr = np.hypot(x - cx, y - cyb)
        bottom = sink & (z < top - 0.13)
        nz = noise(*shp, 30, 5)
        maps["drain"] = bottom * np.maximum(1 - smooth(rr, 0.03, 0.07), 0.35 * (1 - smooth(rr, 0.06, 0.15))) * (0.5 + 0.5 * nz)
        # борт чаши и передняя кромка — без заднего бортика (он весь выходил в сколах)
        rim = sink & (z > top - 0.012) & (z < top + 0.008) & (y < 0.26)
        maps["hits"] = rim * 0.55
        maps["impact"] = np.maximum(scatter(g, bottom, 9, 0.012, 0.03, 7), scatter(g, rim, 8, 0.012, 0.03, 8))
        dsp = parts(g, "ДСП_ламинат", "ДСП_кромка")
        # вода с мойки: низ тумбы (мытьё пола, протечки сифона) и верх фасада под бортом
        patchy = smooth(noise(*shp, 60, 9), 0.25, 0.75)
        low = (1 - smooth(h, 0.03, 0.15)) * (0.35 + 0.65 * patchy)
        # под бортом — где капает с края чаши (чаша слева), не во всю ширину
        under = ((z > 0.74) & (z < 0.83) & (y < -0.25)) * np.exp(-((x - cx) / 0.2) ** 2) * patchy
        inside_low = (np.abs(x) < 0.37) & (y > -0.27) & (h < 0.12)  # дно тумбы под сифоном
        maps["swell"] = dsp * np.maximum.reduce([low, under, inside_low * 0.8])
        maps["touch"] = near(g, parts(g, "Ручка_металл"), 0.09)

    if game == "furn_counter":
        dsp = parts(g, "ДСП_ламинат", "ДСП_кромка")
        maps["swell"] = dsp * (1 - smooth(h, 0.05, 0.12)) * 0.6
        maps["touch"] = np.maximum(near(g, parts(g, "Ручка_металл"), 0.09),
                                   (z > 0.845) * (1 - smooth(y, -0.3, -0.18)))
        tz = 0.852
        maps["stains"] = blobs(g, [((0.18, 0.05, tz), 0.07), ((-0.22, -0.12, tz), 0.05), ((0.3, 0.2, tz), 0.04)], 11,
                               ring=True) * (z > tz - 0.003)
        maps["rings"] = rings(g, [((-0.12, 0.1, tz), 0.085), ((0.2, -0.05, tz), 0.075)], seed=6)
        maps["cuts"] = (z > tz - 0.003) * np.exp(-(((x + 0.02) / 0.22) ** 2 + ((y + 0.08) / 0.14) ** 2))

    if game == "furn_dining":
        top_z = 0.752
        on_top = z > top_z - 0.003
        # сидят с обеих длинных сторон: руки и локти у краёв столешницы
        maps["touch"] = np.maximum(on_top * smooth(np.abs(y), 0.22, 0.36), near(g, parts(g, "Алюминий"), 0.03) * 0.5)
        maps["stains"] = blobs(g, [((0.25, 0.1, top_z), 0.08), ((-0.35, -0.15, top_z), 0.06), ((0.0, -0.2, top_z), 0.045)],
                               11, ring=True) * on_top
        maps["rings"] = rings(g, [((-0.1, 0.05, top_z), 0.042), ((0.3, -0.12, top_z), 0.038), ((-0.4, 0.18, top_z), 0.085)],
                              seed=9)
        maps["burns"] = disc(g, [((0.42, 0.22, top_z), 0.006), ((-0.18, -0.25, top_z), 0.005)], True)
        maps["burn_ring"] = disc(g, [((0.42, 0.22, top_z), 0.006), ((-0.18, -0.25, top_z), 0.005)], False)
        maps["cuts"] = on_top * np.exp(-(((x - 0.1) / 0.3) ** 2 + (y / 0.25) ** 2))
        frame = parts(g, "Сталь_окраска")
        maps["hits"] = frame * np.maximum(1 - smooth(h, 0.12, 0.3), scatter(g, frame, 16, 0.02, 0.05, 13))
        maps["rust_low"] = frame * (1 - smooth(h, 0.008, 0.06)) * (0.6 + 0.4 * noise(*shp, 48, 23))

    if game == "furn_wallcab":
        maps["touch"] = near(g, parts(g, "Ручка_металл"), 0.09)

    if game == "furn_dishrack":
        # с посуды стекает вода: дно и низ боковин, потёки по передней кромке
        zmin = z[valid].min()
        drips = smooth(vnoise(x + 1.7, y + 0.3, 0.02, 5), 0.6, 0.8) * (1 - smooth(z - zmin, 0.0, 0.12))
        maps["wet"] = np.maximum(1 - smooth(z - zmin, 0.005, 0.04), drips) * (0.6 + 0.4 * noise(*shp, 48, 8))
        maps["touch"] = near(g, parts(g, "Ручка_металл"), 0.05)

    if game == "furn_pot":
        maps["touch"] = smooth(np.abs(x), 0.112, 0.125) * 1.0
    if game == "furn_kettle":
        maps["touch"] = near(g, parts(g, "Чёрная_краска"), 0.03)
    if game == "furn_pan":
        maps["touch"] = smooth(-x, 0.13, 0.16)

    if game == "furn_basin":
        fa = parts(g, "Фаянс")
        inner = fa & inside(pos, [(0.804, 0.24, 0.165, -0.265, 3.2), (0.788, 0.228, 0.15, -0.268, 3.0),
                                  (0.75, 0.19, 0.12, -0.27, 2.6), (0.70, 0.11, 0.075, -0.27, 2.2),
                                  (0.682, 0.022, 0.022, -0.27, 2.0)])
        maps["bowl"] = inner * (0.35 + 0.65 * (1 - smooth(z, 0.69, 0.78)))
        # струя из излива бьёт в заднюю стенку чаши и бежит к выпуску: потёк от места удара к стоку
        ly, dy_ = -0.18, -0.27
        t = np.clip((y - ly) / (dy_ - ly), 0, 1)
        w = 0.012 + 0.016 * t
        off = x - 0.006 * np.sin(t * 5.0)
        span = (y < ly + 0.01) & (y > dy_ - 0.015)   # от места удара до выпуска, дальше вода не бежит
        lane = np.exp(-(off / w) ** 2) * span * (0.6 + 0.4 * noise(*shp, 24, 4))
        drain = 1 - smooth(np.hypot(x, y + 0.27), 0.022, 0.05)
        maps["streak"] = inner * np.maximum(lane, drain * 0.8)
        tap_base = (1 - smooth(np.hypot(x, y + 0.055), 0.025, 0.06)) * (z > 0.798) * (nrm[..., 2] > 0.5)
        maps["scale"] = fa * np.maximum.reduce([tap_base, inner * np.exp(-((np.abs(off) / w - 1.1) / 0.45) ** 2) * span,
                                                inner * np.exp(-((np.hypot(x, y + 0.27) - 0.03) / 0.012) ** 2)])
        cell_mm = 9.0
        ppm = px_per_mm(g, fa)
        maps["craze"] = craze(g, fa, cell_mm / 1000, max(0.35, 0.8 / ppm) / 1000, 17)
        rim = fa & (z > 0.795) & ~inner
        maps["hits"] = np.maximum(rim * smooth(-y, 0.38, 0.44), scatter(g, rim, 8, 0.01, 0.025, 19))
        maps["rust_low"] = parts(g, "Чугун_окраска") * (0.6 + 0.4 * noise(*shp, 48, 23))
        print("  фаянс", f"{ppm:.2f} пикс/мм", flush=True)

    if game == "furn_toilet":
        fa = parts(g, "Фаянс")
        cy = -0.32
        inner = fa & inside(pos, [(0.405, 0.168, 0.25, cy - 0.005, 2.3), (0.398, 0.152, 0.232, cy - 0.005, 2.2),
                                  (0.37, 0.14, 0.215, cy, 2.2), (0.3, 0.1, 0.155, cy + 0.02, 2.1),
                                  (0.24, 0.06, 0.08, cy + 0.05, 2.0), (0.215, 0.035, 0.04, cy + 0.06, 2.0)])
        maps["bowl"] = inner * (1 - smooth(z, 0.235, 0.34)) * (0.6 + 0.4 * noise(*shp, 30, 6))
        maps["streak"] = bowl_streaks(pos, inner, (0.0, cy), 13, 0.008, 0.398, 0.22, 21, back=0.8)
        maps["scale"] = inner * np.maximum(np.exp(-((z - 0.255) / 0.012) ** 2), 0.6 * (1 - smooth(z, 0.215, 0.24)))
        ppm = px_per_mm(g, fa)
        maps["craze"] = craze(g, fa, 14.0 / 1000, max(0.5, 0.8 / ppm) / 1000, 23)
        rim = fa & (z > 0.39) & ~inner
        maps["hits"] = np.maximum(rim * smooth(-y, 0.52, 0.58) * 0.7, scatter(g, rim, 8, 0.01, 0.03, 29))
        # у основания — сильнее, чем просто грязь от пола (мокрая тряпка не доходила)
        maps["floor"] = np.maximum(maps["floor"], fa * (1 - smooth(h, 0.02, 0.09)))
        iron = parts(g, "Чугун_окраска")
        tank_src = [1.8, 1.86, 1.94, 2.02, 2.1]
        maps["drip"] = np.maximum(drip(pos, iron & (z > 1.75), tank_src, 0.05, 0.012, 31),
                                  drip(pos, parts(g, "Труба_краска"), [1.81, 0.5], 0.35, 0.006, 37))
        torn = parts(g, "Труба_краска__оборвана")
        maps["torn"] = torn * np.maximum(smooth(z, 0.8, 0.9), ((z > 1.6) & (z < 1.67)).astype(np.float32))
        chain_handle = (np.linalg.norm(pos - np.array((-0.24, -0.242, 1.43)), axis=-1) < 0.06).astype(np.float32)
        seat_front = parts(g, "Сиденье_пластик") * smooth(-y, 0.45, 0.54)
        maps["touch"] = np.maximum(chain_handle, seat_front)
        print("  фаянс", f"{ppm:.2f} пикс/мм", flush=True)

    if game == "furn_stall":
        board = parts(g, "Перегородка_краска")
        door = parts(g, "Перегородка_краска__дверца")
        steel = parts(g, "Сталь_окраска")
        maps["floor"] = np.maximum(maps["floor"], board * (1 - smooth(h, 0.17, 0.42)) * (0.6 + 0.4 * noise(*shp, 40, 4)))
        maps["kick"] = door * (1 - smooth(z, 0.25, 0.65))
        # щеколда — у свободного края дверцы (хром дверцы — ещё и петли у перегородки, их не трогают)
        latch = near(g, parts(g, "Хром__дверца"), 0.12) * (x > 0.0)
        maps["touch"] = latch
        low = 1 - smooth(h, 0.2, 0.55)
        # чешуйки — формой из шума с порогом (кругами мест с узором Painter читались круги); гуще у пола и щеколды,
        # до основы — середины крупных чешуек
        dens = np.maximum.reduce([low * 0.8, latch * 0.8, scatter(g, board, 20, 0.05, 0.16, 41) * 0.6])
        maps["peel"] = board * flakes(g, dens, 0.78, 61)
        maps["peel_deep"] = board * flakes(g, dens, 0.88, 61)
        maps["hits"] = steel * np.maximum(1 - smooth(h, 0.08, 0.25), scatter(g, steel, 10, 0.02, 0.06, 43))
        maps["rust_low"] = steel * (1 - smooth(h, 0.006, 0.05)) * (0.6 + 0.4 * noise(*shp, 48, 23))

    if game == "furn_mirror":
        mir = parts(g, "Зеркало")
        de = np.minimum.reduce([0.2 - np.abs(x), z + 0.6, -z])
        blot = smooth(noise(*shp, 70, 51), 0.3, 0.75)
        # амальгама сходит от края пятнами с рваной кромкой и мелким крапом рядом (кляксы с ровным краем — нет)
        near_edge = 1 - smooth(de, 0.0, 0.045)
        maps["desilver"] = mir * np.maximum(flakes(g, near_edge * (0.6 + 0.6 * blot), 0.86, 71, soft=0.02),
                                            0.7 * flakes(g, near_edge, 0.9, 73, soft=0.01))
        rng = np.random.default_rng(53)
        spots = [((float(rng.uniform(-0.17, 0.17)), -0.006, float(rng.uniform(-0.58, -0.35))), float(rng.uniform(0.002, 0.006)))
                 for _ in range(40)]
        maps["spots"] = mir * blobs(g, spots, 55)

    out = BASE / "wear"
    out.mkdir(parents=True, exist_ok=True)
    for k, v in maps.items():
        v = np.where(valid, v, 0)
        cv2.imwrite(str(out / f"{game}_{k}.png"), (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8))
    print("ZONES", game, sorted(maps), flush=True)


if __name__ == "__main__":
    only = sys.argv[1:]
    for game in ITEMS:
        if not only or game in only:
            zones(game)
