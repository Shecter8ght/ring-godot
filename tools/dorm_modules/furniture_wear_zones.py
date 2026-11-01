"""Мебель общежития, износ (этап 2): места в развёртке по картам геометрии print_bake.py (положение и нормаль каждого
пикселя в осях корня предмета, метры). Рисунок следа кладёт Painter (sp_furniture_wear.py) — эти карты только
ограничивают место.

  python -X utf8 tools/dorm_modules/furniture_wear_zones.py [предмет …]   # → _asset_src/dorm_furniture/wear/<предмет>_<зона>.png

Интервью 2026-10-31: как в Таркове (долго жили, потом бросили); сколы эмали и ржавчина на кроватях; пятна на матрасе и
диване; прожоги сигаретами и кольца от кружек; выцветание заметное; крови нет. Зоны:
  up — грани к небу (пыль); floor — низ до 18 см (грязь от пола, обувь); hits — где бьют и хватают раму (низ стоек,
  верх спинок, разбросанные удары: сколы эмали); rust_low — касание пола (ржавчина); touch — где трогают руками и сидят
  (лак и полировка затёрты до мата, ткань вытерта); greasy — где лежит голова (засалено); stains — пятна с ободком;
  burns / burn_ring — прожоги и их бурый ореол; rings / rings_water — кольца от кружек (кофе и вода);
  heat — побежалость эмали плитки вокруг диска; scuff — проножки табурета и стула (обувью).
Координаты — размеры build_furniture.py (телевизор поднят на ножки на 8 мм).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"  # карты геометрии — EXR; до первого import cv2
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as P  # noqa: E402
from wear_zones import blobs, noise, smooth  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "dorm_furniture"
ITEMS = ["furn_bunk_bed", "furn_bed", "furn_mattress", "furn_nightstand", "furn_wardrobe", "furn_table", "furn_chair",
         "furn_stool", "furn_shelf", "furn_fridge", "furn_sofa", "furn_carpet", "furn_tv", "furn_hotplate"]

TOUCH = {
    "furn_table": [((0.0, -0.05, 0.75), 0.26)],
    "furn_chair": [((0.0, -0.02, 0.45), 0.16)],
    "furn_stool": [((0.0, 0.0, 0.45), 0.12)],
    "furn_nightstand": [((0.0, 0.0, 0.65), 0.18), ((0.0, -0.216, 0.57), 0.07), ((0.15, -0.216, 0.38), 0.07)],
    "furn_wardrobe": [((-0.045, -0.291, 1.02), 0.12), ((0.045, -0.291, 1.02), 0.12), ((-0.07, -0.291, 1.79), 0.06),
                      ((0.07, -0.291, 1.79), 0.06)],
    "furn_sofa": [((-0.45, -0.06, 0.47), 0.28), ((0.35, 0.0, 0.47), 0.28)],
    "furn_fridge": [((0.24, -0.29, 0.68), 0.09)],
    "furn_tv": [((0.215, -0.226, 0.338), 0.08)],
    "furn_hotplate": [((0.07, -0.13, 0.04), 0.04)],
}
STAINS = {"furn_mattress": [((0.1, 0.3, 0.1), 0.18), ((-0.15, -0.4, 0.1), 0.13), ((0.22, 0.72, 0.1), 0.09)],
          "furn_sofa": [((0.6, -0.1, 0.47), 0.12), ((-0.7, 0.147, 0.72), 0.10)]}
BURNS = {"furn_table": [((0.32, -0.18, 0.75), 0.006), ((-0.25, 0.12, 0.75), 0.005)],
         "furn_nightstand": [((0.12, 0.08, 0.65), 0.006)],
         "furn_mattress": [((0.25, -0.6, 0.1), 0.008), ((-0.2, 0.15, 0.1), 0.007)]}
RINGS = {"furn_table": [((-0.1, 0.05, 0.75), 0.042), ((0.18, -0.08, 0.75), 0.038)],
         "furn_nightstand": [((-0.06, -0.05, 0.65), 0.04)]}
RINGS_WATER = {"furn_table": [((0.05, 0.16, 0.75), 0.04)]}
HITS = ("furn_bunk_bed", "furn_bed", "furn_chair")
OFF_FLOOR = ("furn_mattress", "furn_shelf", "furn_carpet", "furn_tv", "furn_hotplate")
RUST_LOW = ("furn_bunk_bed", "furn_bed", "furn_chair", "furn_fridge")  # плитка — 7,5 см: зона накрыла бы её целиком


def disc(g, items, core=True, seed=5):
    """Маленькие пятна (прожоги): core — обугленная середина, иначе ореол вокруг неё."""
    pos = g["pos"]
    out = np.zeros(pos.shape[:2], np.float32)
    nz = noise(*pos.shape[:2], 8, seed)
    for c, r in items:
        d = np.linalg.norm(pos - np.array(c, np.float32), axis=-1) / r
        d = d * (0.85 + 0.3 * nz)
        out = np.maximum(out, 1 - smooth(d, 0.45, 0.8) if core else np.exp(-((d - 1.0) / 0.55) ** 2) * (d > 0.5))
    return out


def rings(g, items, seed=9):
    """Кольца от кружек: тонкий ободок с разрывами (донышко стояло неровно), внутри — слабая заливка."""
    pos = g["pos"]
    out = np.zeros(pos.shape[:2], np.float32)
    for k, (c, r) in enumerate(items):
        d3 = pos - np.array(c, np.float32)
        d = np.linalg.norm(d3[..., :2], axis=-1) / r
        a = np.arctan2(d3[..., 1], d3[..., 0])
        gap = 0.55 + 0.45 * np.sin(a * 2 + k * 1.7) * np.sin(a * 5 + seed + k)
        ring = np.exp(-((d - 1.0) / 0.05) ** 2) * np.clip(gap + 0.35, 0, 1)
        fill = 0.18 * (1 - smooth(d, 0.85, 1.0))
        flat = np.abs(d3[..., 2]) < 0.01
        out = np.maximum(out, (ring + fill) * flat)
    return np.clip(out, 0, 1)


def zones(game: str) -> None:
    g = P.load_geo(BASE, game)
    valid = g["part_id"] > 0
    pos, nrm = g["pos"], g["nrm"]
    h = pos[..., 2] - pos[..., 2][valid].min()
    hmax = h[valid].max()
    # грязь от пола — только у того, что стоит на полу (матрас лежит на кровати, полка и ковёр висят, телевизор
    # и плитка стоят на мебели)
    on_floor = game not in OFF_FLOOR
    maps = {"up": smooth(nrm[..., 2], 0.15, 0.75), "floor": (1 - smooth(h, 0.04, 0.18)) * on_floor}
    if game in HITS:
        rng = np.random.default_rng(13)
        pts = pos[valid]
        centers = [(tuple(pts[i]), float(rng.uniform(0.03, 0.08))) for i in rng.integers(0, len(pts), 28)]
        scatter = blobs(g, centers, 17)
        low = 1 - smooth(h, 0.15, 0.35)
        top = smooth(h, hmax - 0.15, hmax - 0.03)
        maps["hits"] = np.maximum.reduce([low, top * 0.8, scatter * 0.7])
    if game in RUST_LOW:
        maps["rust_low"] = (1 - smooth(h, 0.008, 0.07)) * (0.6 + 0.4 * noise(*h.shape, 48, 23))
    touch = blobs(g, TOUCH[game], 31) if game in TOUCH else np.zeros(h.shape, np.float32)
    if game == "furn_bed":  # верхние перекладины спинок — за них берутся руками
        rails = ((pos[..., 1] > 0.9) & (pos[..., 2] > 0.88)) | ((pos[..., 1] < -0.9) & (pos[..., 2] > 0.68))
        touch = np.maximum(touch, rails * (1 - smooth(np.abs(pos[..., 0]), 0.15, 0.42)))
    if game == "furn_bunk_bed":  # перекладины торца — лестница: руками и ногами
        touch = np.maximum(touch, ((pos[..., 1] < -0.9) & (pos[..., 2] > 0.1) & (pos[..., 2] < 1.7)).astype(np.float32))
    if game == "furn_table":  # передний край столешницы — локти и руки
        touch = np.maximum(touch, (pos[..., 2] > 0.74) * (1 - smooth(pos[..., 1], -0.3, -0.12)))
    if game == "furn_chair":  # верх спинки — за неё берут стул
        touch = np.maximum(touch, smooth(pos[..., 2], 0.76, 0.8) * (pos[..., 1] > 0.1))
    if game == "furn_sofa":  # передний край сиденья — подколенки
        touch = np.maximum(touch, ((pos[..., 2] > 0.3) & (pos[..., 2] < 0.47)) * (1 - smooth(pos[..., 1], -0.34, -0.26)))
    if touch.any():
        maps["touch"] = touch
    if game == "furn_sofa":  # где лежит голова — верх спинки спереди
        maps["greasy"] = smooth(pos[..., 2], 0.76, 0.84) * (nrm[..., 1] < -0.4)
    if game == "furn_mattress":  # изголовье — подушка и голова
        maps["greasy"] = smooth(pos[..., 1], 0.55, 0.8) * (nrm[..., 2] > 0.5) * (0.6 + 0.4 * noise(*h.shape, 64, 41))
    if game in STAINS:
        maps["stains"] = blobs(g, STAINS[game], 11, ring=True)
    if game in BURNS:
        maps["burns"] = disc(g, BURNS[game], True)
        maps["burn_ring"] = disc(g, BURNS[game], False)
    if game in RINGS:
        maps["rings"] = rings(g, RINGS[game])
    if game in RINGS_WATER:
        maps["rings_water"] = rings(g, RINGS_WATER[game], seed=4)
    if game == "furn_hotplate":  # эмаль вокруг диска пожелтела и побурела от жара
        rr = np.linalg.norm(pos[..., :2], axis=-1)
        maps["heat"] = (np.exp(-((rr - 0.1) / 0.018) ** 2)) * (pos[..., 2] > 0.068) * (0.7 + 0.3 * noise(*h.shape, 32, 5))
    if game in ("furn_stool", "furn_chair"):  # проножки — ставят ноги
        maps["scuff"] = ((h > 0.1) & (h < 0.2)).astype(np.float32)
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
