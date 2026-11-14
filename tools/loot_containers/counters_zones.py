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


# ---------------------------------------------------------------------------------------------- круг 2: сколы точками
# Сколы — не порог маски по пикселям (давал «лесенку» и облупленную краску по всей кромке), а несколько мелких пятен
# в 3D: расстояние от каждого пикселя (карта положения) до места скола с неровным радиусом и мягким краем в ~1 пиксель.
# Места — по причине: выступающие углы, кромка со стороны продавца, низ у пола (ноги, тележки), лицо ящика, у поручня.
# (центр, радиус м); наборы мест по предмету, случайные — из пикселей кромки в заданной области (seed — постоянный).

def chip_blobs(pos, valid, sites, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros(valid.shape, np.float32)
    ys, xs = np.nonzero(valid)
    p = pos[ys, xs]
    for c, r in sites:
        c = np.asarray(c, np.float32)
        near = np.abs(p - c).max(1) < r * 2.2
        if not near.any():
            continue
        q = p[near] - c
        d = np.linalg.norm(q, axis=1)
        # неровный край: радиус меняется по направлению (сумма синусов от углов в двух плоскостях)
        a1, a2 = np.arctan2(q[:, 1], q[:, 0]), np.arctan2(q[:, 2], np.hypot(q[:, 0], q[:, 1]))
        ph = rng.uniform(0, 6.28, 4)
        rr = r * (1 + 0.28 * np.sin(3 * a1 + ph[0]) + 0.18 * np.sin(5 * a1 + ph[1]) + 0.22 * np.sin(4 * a2 + ph[2]))
        soft = 0.0009
        v = np.clip((rr - d) / soft + 0.5, 0, 1)
        cur = out[ys[near], xs[near]]
        out[ys[near], xs[near]] = np.maximum(cur, v)
    return out


def pick_sites(pos, cand, k: int, rmin: float, rmax: float, seed: int):
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(cand)
    if not len(ys):
        return []
    idx = rng.choice(len(ys), size=min(k, len(ys)), replace=False)
    return [(pos[ys[i], xs[i]], float(rng.uniform(rmin, rmax))) for i in idx]


def chips_counter(g, h, valid) -> np.ndarray:
    pos, edge = g["pos"], g["edge"][..., 0]
    ZT = 0.899
    sites = [((-0.75, -0.30, ZT), 0.0035), ((0.75, 0.30, ZT), 0.004), ((-0.75, 0.30, ZT), 0.0025),
             ((-0.44, 0.30, ZT), 0.002), ((-0.02, 0.30, ZT), 0.0015), ((0.37, 0.30, ZT), 0.0025)]
    lam = parts(g, "ПТ_боковины", "ПТ_панель_передняя", "ПТ_полки", "ПТ_дно", "ПТ_перегородки", "ПТ_ящик_лицо")
    e = (edge > 0.7) & lam & valid
    sites += pick_sites(pos, e & (h < 0.14), 7, 0.002, 0.005, 11)                          # низ у пола: ноги, швабра
    sites += pick_sites(pos, e & (np.abs(pos[..., 1] + 0.265) < 0.01) & (np.abs(np.abs(pos[..., 0]) - 0.75) < 0.01), 3,
                        0.002, 0.004, 12)                                                    # передние рёбра боковин
    sites += pick_sites(pos, e & parts(g, "ПТ_ящик_лицо"), 2, 0.0015, 0.003, 13)            # лицо ящика
    sites += pick_sites(pos, e & parts(g, "ПТ_полки") & (pos[..., 1] > 0.27), 3, 0.0015, 0.003, 14)  # передние кромки полок
    return chip_blobs(pos, valid, sites, 21)


def chips_checkout(g, h, valid) -> np.ndarray:
    pos, edge = g["pos"], g["edge"][..., 0]
    body = parts(g, "КБ_корпус")
    e = (edge > 0.7) & valid
    sites = pick_sites(pos, e & body & (h < 0.35) & (h > 0.10), 6, 0.003, 0.007, 31)     # нижние углы корпуса: тележки
    sites += [((0.30, -0.551, 0.20), 0.008), ((1.10, -0.551, 0.20), 0.007)]               # у фланцев отбойника
    sites += pick_sites(pos, e & parts(g, "КБ_стол_кассира"), 3, 0.002, 0.004, 32)         # кромка стола кассира
    sites += pick_sites(pos, e & parts(g, "КБ_стол_торцевая_панель") & (h < 0.15), 2, 0.002, 0.004, 33)
    return chip_blobs(pos, valid, sites, 41)


def extra_zones(game: str, g: dict, h, vert, valid) -> None:
    """Круг 2: сколы точками и их кайма, полоса истирания по ребру у продавца, низ узкой полосой, пояс ног и тележек,
    место у поручня."""
    pos = g["pos"]
    ch = chips_counter(g, h, valid) if game == "cn_counter" else chips_checkout(g, h, valid)
    save(game, "chips", ch)
    halo = cv2.GaussianBlur(cv2.dilate(ch, np.ones((5, 5), np.uint8)), (0, 0), 1.2)
    save(game, "chips_halo", np.clip(halo * 1.4, 0, 1) * valid)
    save(game, "floor_low", (1 - smooth(h, 0.004, 0.03)) * valid)
    save(game, "kick_low", smooth(h, 0.04, 0.07) * (1 - smooth(h, 0.22, 0.30)) * vert * valid)
    edge = cv2.GaussianBlur(g["edge"][..., 0], (0, 0), 1.0)
    if game == "cn_counter":
        rim = smooth(edge, 0.3, 0.8) * (pos[..., 1] > 0.27) * parts(g, "ПТ_столешница") * valid
    else:
        rim = smooth(edge, 0.3, 0.8) * parts(g, "КБ_стол_кассира") * (pos[..., 1] > 0.5) * valid
    save(game, "rim_sell", rim)
    if game == "cn_checkout":
        from scipy.spatial import cKDTree
        rail = parts(g, "КБ_отбойник_труба")
        d, _ = cKDTree(pos[rail][::3]).query(pos[valid])
        dist = np.full(valid.shape, 9.0, np.float32)
        dist[valid] = d
        save(game, "rail", (1 - smooth(dist, 0.03, 0.15)) * parts(g, "КБ_корпус") * valid)
    else:
        save(game, "rail", np.zeros(valid.shape, np.float32))


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
    extra_zones(game, g, h, vert, valid)
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
