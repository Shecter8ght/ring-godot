"""Мебель общежития, печать этапа 1 слоем для Painter: полосы матрасного тика, свой орнамент ковра, вымышленные марки —
шильдик холодильника «ИНЕЙ», панель телевизора «ИЛИМ» с подписями ручек, надпись и шкала у ручки плитки.

  python -X utf8 tools/dorm_modules/furniture_prints.py [предмет …]   # → _asset_src/dorm_furniture/prints/uv/<предмет>_print_*

Карты геометрии в развёртку — print_bake.py (furniture_uv) в _asset_src/dorm_furniture/prints/geo. Слой кладёт Painter
над заводской отделкой (sp_dorm_wear._print_layer — тот же слой «Печать (этап 1)» и у износа). Марки выдуманы, шрифты
DejaVu (как у мусора). Орнамент ковра — свой: стёганая сетка узлов 6 мм, медальон-ромб со ступенчатым краем,
угловые четвертинки, звёзды по полю, кайма с розетками — по мотивам ковров 70-х, не копия какого-то ковра.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as A  # noqa: E402
import print_designs as PD  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "_asset_src" / "dorm_furniture"


def srgb(c) -> np.ndarray:
    return np.array(c, np.float32) / 255.0


def smooth(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def to_array(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGBA"), np.float32) / 255.0


# ---------------------------------------------------------------- матрас: тик в полоску

def mattress() -> None:
    game = "furn_mattress"
    g = A.load_geo(BASE, game)
    mask = A.part_mask(g, "Матрас_тик")
    p, n = g["pos"], g["nrm"]
    # полосы идут вдоль матраса: на пластях и торцах — по ширине (x), на длинных боках — по высоте (z)
    side = np.abs(n[..., 0]) > 0.5
    s = np.where(side, p[..., 2] * 1000.0, p[..., 0] * 1000.0)
    rng = np.random.default_rng(7)
    jitter = np.interp(p[..., 1] * 1000.0, np.arange(-1000, 1001, 40), rng.normal(0, 0.25, 51))
    period = 30.0
    x = (s + jitter + period / 2) % period - period / 2
    soft = 0.35
    wide = 1 - smooth(4.0 - soft, 4.0 + soft, np.abs(x))
    thin = 1 - smooth(0.75 - soft, 0.75 + soft, np.abs(np.abs(x) - 8.0))
    slate, navy = srgb((86, 102, 126)), srgb((52, 62, 84))
    a = np.clip(wide + thin, 0, 1) * mask
    col = np.where(wide[..., None] > thin[..., None], slate, navy)
    prn = np.concatenate([col * np.ones_like(p), (a * 0.92)[..., None]], axis=-1).astype(np.float32)
    A.save_layer(BASE, game, [(prn, None, None, 1.0)])


# ---------------------------------------------------------------- ковёр: свой орнамент

FIELD, NAVY, IVORY, OCHRE, DARK, GREEN = ((148, 30, 28), (30, 33, 56), (214, 198, 160), (186, 132, 58), (40, 22, 20),
                                         (52, 84, 66))


def carpet_design(w_mm: int = 1500, h_mm: int = 2000, knot: float = 6.0) -> np.ndarray:
    """Рисунок ковра 1 пикс/мм: узлы по сетке knot мм (ступенчатый край узора), цвета чуть гуляют по узлам."""
    ys, xs = np.mgrid[0:h_mm, 0:w_mm].astype(np.float32)
    kx, ky = (np.floor(xs / knot) + 0.5) * knot, (np.floor(ys / knot) + 0.5) * knot
    col = np.empty((h_mm, w_mm, 3), np.float32)
    col[:] = srgb(FIELD)
    edge = np.minimum.reduce([kx, w_mm - kx, ky, h_mm - ky])

    def put(m, c):
        col[m] = srgb(c)

    # кайма: внешняя тёмная полоса, светлая нить, широкая тёмно-синяя кайма с розетками, нити, поле
    put(edge < 22, DARK)
    put((edge >= 22) & (edge < 32), IVORY)
    band = (edge >= 32) & (edge < 172)
    put(band, NAVY)
    put((edge >= 172) & (edge < 180), IVORY)
    put((edge >= 180) & (edge < 190), OCHRE)
    # розетки каймы: восьмиконечные звёзды через 130 мм по середине каймы
    t = np.where(np.minimum(kx, w_mm - kx) < np.minimum(ky, h_mm - ky), ky, kx)  # вдоль каймы
    along = (t - 66) % 130 - 65
    across = edge - 102
    r_l1 = np.abs(along) + np.abs(across)
    r_max = np.maximum(np.abs(along), np.abs(across))
    star = np.minimum(r_l1 / 1.25, r_max)
    put(band & (star < 48), IVORY)
    put(band & (star < 34), FIELD)
    put(band & (star < 14), OCHRE)
    # «бегущая волна» между розетками
    wave = np.abs(across - 34 * np.sin(along / 65.0 * math.pi * 0.5)) < 6
    put(band & (star >= 48) & wave, OCHRE)

    field = edge >= 190
    cx, cy = w_mm / 2, h_mm / 2
    dx, dy = np.abs(kx - cx), np.abs(ky - cy)
    # центральный медальон: ромб со ступенями, слои
    d = dx / 420 + dy / 600
    put(field & (d < 1.0), NAVY)
    put(field & (d < 0.93), IVORY)
    put(field & (d < 0.86), FIELD)
    inner = field & (d < 0.86) & (d > 0.5)
    # по красному кольцу медальона — ромбики-«глазки»
    eye = (np.abs((kx - cx) % 84 - 42) + np.abs((ky - cy) % 84 - 42)) < 16
    put(inner & eye, OCHRE)
    put(field & (d < 0.5), NAVY)
    core = np.minimum((dx + dy) / 1.3, np.maximum(dx, dy))
    put(field & (d < 0.5) & (core < 120), IVORY)
    put(field & (d < 0.5) & (core < 84), FIELD)
    put(field & (d < 0.5) & (core < 36), OCHRE)
    put(field & (d < 0.5) & (core < 14), DARK)
    # угловые четвертинки медальона
    fx0, fy0, fx1, fy1 = 190, 190, w_mm - 190, h_mm - 190
    qd = np.minimum.reduce([np.abs(kx - fx0) / 300 + np.abs(ky - fy0) / 300, np.abs(kx - fx1) / 300 + np.abs(ky - fy0) / 300,
                            np.abs(kx - fx0) / 300 + np.abs(ky - fy1) / 300, np.abs(kx - fx1) / 300 + np.abs(ky - fy1) / 300])
    put(field & (qd < 1.0) & (d >= 1.0), NAVY)
    put(field & (qd < 0.9) & (d >= 1.0), IVORY)
    put(field & (qd < 0.8) & (d >= 1.0), NAVY)
    put(field & (qd < 0.45) & (d >= 1.0), GREEN)
    # звёзды по полю, рядами со сдвигом
    gx = (kx - cx) % 170 - 85
    row = np.floor((ky - cy) / 170)
    gx = np.where(row % 2 == 0, gx, (kx - cx + 85) % 170 - 85)
    gy = (ky - cy) % 170 - 85
    st = np.minimum((np.abs(gx) + np.abs(gy)) / 1.3, np.maximum(np.abs(gx), np.abs(gy)))
    free = field & (d >= 1.06) & (qd >= 1.08)
    put(free & (st < 26), OCHRE)
    put(free & (st < 12), NAVY)
    # узлы: тон чуть гуляет, шерсть с годами неровно окрашена (крупные «абраши» — полосы по горизонтали)
    rng = np.random.default_rng(11)
    kn = rng.normal(1.0, 0.035, (int(h_mm / knot) + 1, int(w_mm / knot) + 1)).astype(np.float32)
    col *= kn[(ys / knot).astype(int), (xs / knot).astype(int)][..., None]
    abrash = 1.0 + 0.04 * np.sin(ys / 2000.0 * math.pi * 7.0 + 1.3) * np.sin(ys / 2000.0 * math.pi * 2.0)
    col *= abrash[..., None]
    return np.clip(col, 0, 1)


def carpet() -> None:
    game = "furn_carpet"
    g = A.load_geo(BASE, game)
    mask = A.part_mask(g, "Ковёр_шерсть")
    p, n = g["pos"], g["nrm"]
    img = carpet_design()
    h, w = img.shape[:2]
    rgba = np.concatenate([img, np.ones((h, w, 1), np.float32)], axis=-1)
    u = (p[..., 0] + 0.75) / 1.5
    v = (2.0 - p[..., 2]) / 2.0
    front = mask & (n[..., 1] < -0.5)
    back = mask & (n[..., 1] > 0.5)
    out = A.sample(rgba, np.clip(u, 0, 1), np.clip(v, 0, 1), front)
    # изнанка: тот же узор зеркально, тусклее — видны узлы
    b = A.sample(rgba, np.clip(1 - u, 0, 1), np.clip(v, 0, 1), back)
    b[..., :3] = b[..., :3] * 0.55 + 0.08
    out = np.where(back[..., None], b, out)
    edge = mask & ~front & ~back
    out[edge] = np.concatenate([srgb(DARK), [1.0]])
    A.save_layer(BASE, game, [(out.astype(np.float32), None, None, 1.0)])


# ---------------------------------------------------------------- холодильник, телевизор, плитка

def fridge_plate() -> np.ndarray:
    """Шильдик 120 × 28: красная эмаль, буквы и ободок — хром (без печати)."""
    im, d = PD.canvas(120, 28)
    d.rounded_rectangle([PD.mm(1.2), PD.mm(1.2), PD.mm(118.8), PD.mm(26.8)], radius=PD.mm(6.5), fill=(122, 18, 20, 255))
    PD.text(d, 60, 14.6, "ИНЕЙ", PD.font(PD.SANS_B, 15), (0, 0, 0, 0))
    return to_array(im)


def tv_panel() -> np.ndarray:
    """Панель управления 110 × 390 мм (верх — z 0,428): марка, подписи ручек, модель внизу."""
    im, d = PD.canvas(110, 390)
    ink = (34, 34, 34, 255)
    PD.text(d, 55, 15, "ИЛИМ", PD.font(PD.SANS_B, 10), ink)
    for y, s in ((72, "ГРОМКОСТЬ"), (132, "ЯРКОСТЬ"), (192, "КАНАЛ")):
        PD.text(d, 55, y, s, PD.font(PD.SANS, 4.2), ink)
    for k in range(6):
        a = math.radians(-120 + 48 * k)
        PD.text(d, 55 + 24 * math.sin(a), 170 - 24 * math.cos(a), str(k + 1), PD.font(PD.SANS_B, 3.6), ink)
    PD.text(d, 55, 381, "51ТЦ-2", PD.font(PD.SANS_B, 5), ink)
    return to_array(im)


def hotplate_front() -> np.ndarray:
    """Перед корпуса плитки 230 × 40 мм: надпись слева, шкала вокруг ручки (центр — 185, 23,5 мм)."""
    im, d = PD.canvas(230, 40)
    ink = (28, 28, 28, 255)
    PD.text(d, 70, 15, "ПЛИТКА ЭЛЕКТРИЧЕСКАЯ", PD.font(PD.SANS_B, 4.2), ink)
    PD.text(d, 70, 23, "ЭПЧ-1   220 В   1000 Вт", PD.font(PD.SANS, 3.4), ink)
    for k, s in enumerate(("0", "1", "2", "3")):
        a = math.radians(-120 + 80 * k)
        PD.text(d, 185 + 22 * math.sin(a), 23.5 - 22 * math.cos(a), s, PD.font(PD.SANS_B, 4), ink)
    return to_array(im)


def fridge() -> None:
    game = "furn_fridge"
    g = A.load_geo(BASE, game)
    prn = A.decal(g, A.part_mask(g, "Хром"), fridge_plate(), (-0.1, -0.298, 0.79), (0, -1, 0), (1, 0, 0), 120, 28,
                  depth=0.004)
    A.save_layer(BASE, game, [(prn, 0.0, 0.3, 1.0)])


def tv() -> None:
    game = "furn_tv"
    g = A.load_geo(BASE, game)
    prn = A.decal(g, A.part_mask(g, "Телевизор_панель"), tv_panel(), (0.215, -0.223, 0.233), (0, -1, 0), (1, 0, 0),
                  110, 390, depth=0.003)
    A.save_layer(BASE, game, [(prn, None, None, 1.0)])


def hotplate() -> None:
    game = "furn_hotplate"
    g = A.load_geo(BASE, game)
    prn = A.decal(g, A.part_mask(g, "Плитка_корпус"), hotplate_front(), (0.0, -0.125, 0.0435), (0, -1, 0), (1, 0, 0),
                  230, 40, depth=0.006)
    A.save_layer(BASE, game, [(prn, None, None, 1.0)])


ITEMS = {"furn_mattress": mattress, "furn_carpet": carpet, "furn_fridge": fridge, "furn_tv": tv, "furn_hotplate": hotplate}

if __name__ == "__main__":
    only = sys.argv[1:]
    for name, fn in ITEMS.items():
        if not only or name in only:
            fn()
