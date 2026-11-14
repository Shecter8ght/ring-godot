"""Опоры касс v01, отделка: места износа в развёртке по картам геометрии (counters_bake.py: положение, нормаль, номер детали,
кромки из 3D). Приёмы — lc3_zones.py партии 1; рисунок следа кладёт Painter масками владельца, зона — только МЕСТО.

  python -X utf8 -I tools/loot_containers/counters_zones.py [набор …]   # → _asset_src/loot_containers/wear_counters/<набор>_<зона>.png

Зоны (серые 8 бит, размер набора):
  edge / edgew — выпуклые рёбра из 3D (узкая / широкая полоса);   up — верхние грани (пыль);   floor — нижние 18 см;
  kick — нижние 30 см вертикальных граней (обувь);   touch / touch_core — вокруг ручки ящика и места кассира на столешнице;
  front_knee — лицо на высоте колена и стопы (20–60 см);   edge_cust / edge_sell — кромка столешницы у покупателя / у продавца (затёрта руками);
  track — дорожка товара по нержавейке и ленте бокса (полоса вдоль X);   cups — места колец от стаканов на столешнице (пятна, не кольца: кольца рисует маска).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "_asset_src" / "loot_containers" / "prints" / "geo_counters"
OUT = ROOT / "_asset_src" / "loot_containers" / "wear_counters"
GAMES = ["cn_counter", "cn_checkout"]


def smooth(x, lo, hi):
    t = np.clip((x - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    return (t * t * (3 - 2 * t)).astype(np.float32)


def load(game: str) -> dict:
    g = {k: np.load(GEO / f"{game}_{k}.npy").astype(np.float32) for k in ("pos", "nrm", "part", "edge")}
    g["pid"] = np.rint(g["part"][..., 0]).astype(np.int32)
    g["names"] = {int(k): v for k, v in json.loads((GEO / f"{game}_parts.json").read_text(encoding="utf-8")).items()}
    return g


def parts(g: dict, *names) -> np.ndarray:
    ids = [i for i, n in g["names"].items() if any(n == x or n.startswith(x + "__") for x in names)]
    return np.isin(g["pid"], ids)


def save(game: str, name: str, a: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{game}_{name}.png"), np.clip(a * 255, 0, 255).astype(np.uint8))


def zones(game: str) -> None:
    g = load(game)
    pos, nrm, pid = g["pos"], g["nrm"], g["pid"]
    valid = pid > 0
    h = pos[..., 2] - float(pos[..., 2][valid].min())
    r = cv2.GaussianBlur(g["edge"][..., 0], (0, 0), 0.8)
    save(game, "edge", smooth(r, 0.5, 0.95) * valid)
    save(game, "edgew", smooth(cv2.GaussianBlur(g["edge"][..., 0], (0, 0), 3.0), 0.2, 0.55) * valid)
    save(game, "up", smooth(nrm[..., 2], 0.55, 0.95) * valid)
    save(game, "floor", (1 - smooth(h, 0.10, 0.18)) * valid)
    vert = 1 - smooth(np.abs(nrm[..., 2]), 0.2, 0.5)
    save(game, "kick", (1 - smooth(h, 0.10, 0.30)) * vert * valid)
    save(game, "front_knee", smooth(h, 0.15, 0.25) * (1 - smooth(h, 0.55, 0.65)) * vert * valid)
    if game == "cn_counter":
        hand = parts(g, "ПТ_ящик_ручка")
        from scipy.spatial import cKDTree
        d, _ = cKDTree(pos[hand][::3]).query(pos[valid])
        dist = np.full(valid.shape, 9.0, np.float32)
        dist[valid] = d
        reg = np.zeros(valid.shape, np.float32)
        # место кассира на столешнице: вокруг (−0,25; 0; 0,9), радиус 0,25 м, и затёртая зона у края продавца
        top = parts(g, "ПТ_столешница") & (nrm[..., 2] > 0.7)
        dr = np.hypot(pos[..., 0] + 0.25, pos[..., 1] - 0.05)
        reg = (1 - smooth(dr, 0.18, 0.40)) * top
        save(game, "touch", np.maximum((1 - smooth(dist, 0.02, 0.10)) * valid, reg))
        save(game, "touch_core", (1 - smooth(dist, 0.0, 0.03)) * valid)
        edge_top = parts(g, "ПТ_столешница")
        save(game, "edge_cust", (1 - smooth(pos[..., 1] + 0.30, 0.0, 0.06)) * smooth(pos[..., 2], 0.86, 0.88) * edge_top * (nrm[..., 2] > 0.5))
        save(game, "edge_sell", (1 - smooth(0.30 - pos[..., 1], 0.0, 0.06)) * smooth(pos[..., 2], 0.86, 0.88) * edge_top * (nrm[..., 2] > 0.5))
        coin = np.hypot(pos[..., 0] - 0.30, pos[..., 1] + 0.10)
        save(game, "cups", (1 - smooth(coin, 0.10, 0.22)) * top)
        save(game, "track", np.zeros(valid.shape, np.float32))
    else:
        steel = parts(g, "КБ_столешница_нержавейка", "КБ_столешница_сканер", "КБ_лента_транспортёра") & (nrm[..., 2] > 0.7)
        lane = (1 - smooth(np.abs(pos[..., 1] + 0.25), 0.18, 0.30)) * steel
        save(game, "track", lane * (0.6 + 0.4 * (1 - smooth(np.abs(pos[..., 0] + 0.4), 0.5, 1.2))))
        top = parts(g, "КБ_стол_кассира") & (nrm[..., 2] > 0.7)
        dr = np.hypot(pos[..., 0] - 0.40, pos[..., 1] - 0.30)
        save(game, "touch", (1 - smooth(dr, 0.25, 0.45)) * top)
        save(game, "touch_core", np.zeros(valid.shape, np.float32))
        save(game, "edge_cust", np.zeros(valid.shape, np.float32))
        save(game, "edge_sell", np.zeros(valid.shape, np.float32))
        save(game, "cups", (1 - smooth(dr, 0.30, 0.50)) * top)
    print("зоны", game, valid.shape, flush=True)


if __name__ == "__main__":
    for n in sys.argv[1:] or GAMES:
        zones(n)
