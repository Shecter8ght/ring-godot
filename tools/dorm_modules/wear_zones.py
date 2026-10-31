"""Места износа (этап 2) в развёртке вещей — по картам геометрии print_bake.py (положение и нормаль каждого пикселя
в осях корня вещи): где лежит пыль, где грязь от пола, куда стёк подтёк, где пятно сырости, где кровь. Рисунок следа
кладёт Painter (фото-маски CC0, гранжи полки), эти карты только ограничивают место (sp_dorm_wear.py).

  python -X utf8 tools/dorm_modules/wear_zones.py [вещь …]   # → _asset_src/<набор>/wear/<вещь>_<зона>.png (8 бит, 2048)

Зоны: up — грани к небу в том положении, в каком вещь лежит (у лежащей водки верх — её бок +Y); floor — полоса
у пола (до 15 мм над нижней точкой); drip — подтёк пива от отверстия банки вниз по стенке; damp — пятно сырости
с ободком на этикетке; blood — места крови (выбраны вещи, интервью 2026-10-31: «кровь на некоторых вещах»).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # карты геометрии — EXR; до первого import cv2
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as P  # noqa: E402  (load_geo, part_mask)

# верх в осях корня: у лежащей водки корень повёрнут на 90° вокруг X — к небу смотрит её +Y
UP = {"clutter_bottle_vodka_worn": (0.0, 1.0, 0.0)}
# кровь: (центр в осях корня, радиус м) — у фонаря отпечатки на корпусе, у водки капли у этикетки, у мешка мазок по боку
BLOOD = {"found_flashlight": [((0.0, 0.0, 0.034), 0.05)],
         "clutter_bottle_vodka_worn": [((0.0, 0.03, 0.10), 0.06), ((0.02, 0.035, 0.20), 0.03)],
         "clutter_bag_lying": [("dir", (0.1, -0.6, 0.8), 0.13)]}  # «dir» — самая дальняя точка поверхности в эту сторону
# сырость на этикетках: (центр, радиус)
DAMP = {"clutter_bottle_vodka_worn": [((0.03, 0.0, 0.07), 0.035)], "clutter_bottle_beer": [((0.03, 0.0, 0.06), 0.03)],
        "clutter_butts": [((0.215, 0.06, 0.012), 0.03)]}
DRIP = ("clutter_can", "clutter_can_dented")

ITEMS = {"clutter": ["clutter_can", "clutter_can_dented", "clutter_can_crushed", "clutter_bottle_vodka",
                     "clutter_bottle_vodka_worn", "clutter_bottle_beer", "clutter_bottle_broken", "clutter_butts",
                     "clutter_casings", "clutter_bag_full", "clutter_bag_lying", "clutter_bag_half"],
         "found": ["found_flashlight", "found_headlamp", "found_chemlight", "found_lantern", "found_candles", "found_beacon"]}


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def noise(h, w, cell, seed):
    rng = np.random.default_rng(seed)
    n = rng.random((h // cell + 3, w // cell + 3)).astype(np.float32)
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)


def blobs(g, centers, seed, ring=False):
    """Пятна вокруг точек в пространстве: неровный край (шум по положению), ring — ободок по краю (высохшее пятно)."""
    pos = g["pos"]
    h, w = pos.shape[:2]
    out = np.zeros((h, w), np.float32)
    nz = noise(h, w, 96, seed)
    valid = g["part_id"] > 0
    for k, item in enumerate(centers):
        if item[0] == "dir":
            pts = pos[valid]
            c, r = pts[np.argmax(pts @ np.array(item[1], np.float32))], item[2]
        else:
            c, r = item
        d = np.linalg.norm(pos - np.array(c, np.float32), axis=-1) / r
        d = d * (0.8 + 0.4 * nz)
        if ring:
            out = np.maximum(out, 0.45 * (1 - smooth(d, 0.6, 1.0)) + 0.9 * np.exp(-((d - 0.92) / 0.06) ** 2))
        else:
            out = np.maximum(out, 1 - smooth(d, 0.5, 1.0))
    return out


def zones(set_key: str, game: str) -> None:
    base = P.SETS[set_key]
    g = P.load_geo(base, game)
    valid = g["part_id"] > 0
    pos, nrm = g["pos"], g["nrm"]
    up = np.array(UP.get(game, (0.0, 0.0, 1.0)), np.float32)
    out = base / "wear"
    out.mkdir(parents=True, exist_ok=True)
    maps = {}
    maps["up"] = smooth(nrm @ up, 0.15, 0.75)
    hgt = pos @ up
    hgt = hgt - hgt[valid].min()
    maps["floor"] = 1 - smooth(hgt, 0.003, 0.016)
    if game in DRIP:
        m = P.part_mask(g, "Банка_алюминий")
        a = np.degrees(np.arctan2(pos[..., 1], pos[..., 0]))  # отверстие банки — в сторону +Y (90°)
        z = pos[..., 2]
        top = z.max() if not m.any() else pos[..., 2][m].max()
        length = (top - z) / max(top - 0.012, 1e-3)  # 0 у крышки … 1 у дна
        width = 18 * (1 - 0.6 * length) * (0.7 + 0.6 * noise(*z.shape, 64, 3))
        streak = (1 - smooth(np.abs(a - 90), width * 0.5, width)) * (1 - smooth(length, 0.45, 0.75))
        maps["drip"] = streak * m * (np.abs(nrm[..., 2]) < 0.8)
    if game in DAMP:
        maps["damp"] = blobs(g, DAMP[game], 11, ring=True)
    if game in BLOOD:
        maps["blood"] = blobs(g, BLOOD[game], 21)
    for k, v in maps.items():
        v = np.where(valid, v, 0)
        cv2.imwrite(str(out / f"{game}_{k}.png"), (np.clip(v, 0, 1) * 255 + 0.5).astype(np.uint8))
    print("ZONES", game, sorted(maps), flush=True)


def main() -> None:
    only = sys.argv[1:]
    for set_key, games in ITEMS.items():
        for game in games:
            if not only or game in only:
                zones(set_key, game)


if __name__ == "__main__":
    main()
