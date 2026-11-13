"""Контейнеры для лута, v03: места износа в развёртке по картам геометрии (prints/geo/*.exr: положение и нормаль каждого
пикселя в осях корня набора, метры). Износ собран ПО ФОРМЕ, плоскости чистые (замечание владельца 2026-11-13):
кромки, наружные углы, вокруг ручек / замков / лимба, низ у пола, верхние плоскости (пыль).

  python -X utf8 -I tools/loot_containers/lc3_zones.py [набор …]   # → _asset_src/loot_containers/wear_v03/<набор>_<зона>.png

Зоны (серые 8-бит, размер набора; рисунок следа кладёт Painter масками владельца, зона — только МЕСТО):
  edge   — выпуклое ребро, полоса 1,5–4,5 мм (расстояние до другой грани; вогнутые углы не в счёт) — приём
           furniture2_wear_zones.edge_zone: генератор кривизны Painter на листовых деталях полосу не даёт;
  edgew  — то же, до 10 мм (затёртый металл у кромки, пыль и желтизна на выступах);
  up     — грани, смотрящие вверх (пыль);
  floor  — нижние 8–14 см (тёмная грязь у пола);
  kick   — нижние 30 см вертикальных граней (обувь, тележка);
  touch  — 2–8 см вокруг ручек, замков, лимба (следы рук); touch_core — 0–3 см (потёртость до грунта узким пятном).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "dorm_modules"))
import furniture2_wear_zones as FZ  # noqa: E402
import print_apply as P  # noqa: E402
from wear_zones import smooth  # noqa: E402

SRC = ROOT / "_asset_src" / "loot_containers"
OUT = SRC / "wear_v03"
# набор: детали-«места хвата» (имя до «__» — любое из перечня; с «__» — точное)
TOUCH = {
    "lc_gun": ["ОШ_ручка_замок", "ОШ_накладка_замка"],
    "lc_safe": ["СН_лимб", "СН_ручка_штурвал"],
    "lc_cell": ["СЯ_ручка", "СЯ_замок"],
    "lc_file": ["КШ_ящик_верхний_лицо__ручка", "КШ_ящик_второй_лицо__ручка", "КШ_ящик_третий_лицо__ручка",
                "КШ_ящик_нижний_лицо__ручка", "КШ_замок_центральный"],
    "lc_cash": ["КМ_лоток_лицо__замок", "КМ_клавиатура__красная", "КМ_клавиатура__зелёная", "КМ_клавиатура__синяя"],
    "lc_aid": ["АП_защёлка"],
}
ITEMS = list(TOUCH)
# места потёков (под жалюзи шкафа) и поля клавиш (грязь между клавишами)
DRIP = {"lc_gun": ["ОШ_жалюзи_лев", "ОШ_жалюзи_прав"]}
KEYS = {"lc_cash": ["КМ_клавиатура__тёмные", "КМ_клавиатура__светлые", "КМ_клавиатура__красная",
                    "КМ_клавиатура__зелёная", "КМ_клавиатура__синяя"]}
_core = FZ.core
FZ.core = lambda mask, px=1: _core(mask, 1)   # рёбра лежат на границах островов — срез в 2 пикселя съедал всю полосу
INSIDE = {"lc_gun": ["ОШ_корпус", "ОШ_полка", "ОШ_ящик_патроны", "ОШ_ложемент"]}   # нутро шкафа: нормаль к центру корпуса
ONLY = set(__import__("os").environ.get("LC3_ZONES", "").split(",")) - {""}   # только эти зоны (быстрый пересчёт)


def want(name: str) -> bool:
    return not ONLY or name in ONLY


def island_border(g: dict, px: int) -> np.ndarray:
    """Пиксели не дальше px от границы острова детали (соседний пиксель другой детали или пустой): кромки листа лежат на
    границах островов развёртки, а «кромочные» пятна посреди панели (кольцо у лимба, штриховка) — нет."""
    pid = g["part_id"]
    b = np.zeros(pid.shape, np.uint8)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        b |= (np.roll(pid, (dy, dx), (0, 1)) != pid).astype(np.uint8)
    d = cv2.distanceTransform((1 - b).astype(np.uint8), cv2.DIST_L2, 3)
    return d <= px


SMALL = {"lc_cell", "lc_aid", "lc_cash"}   # малые предметы: зоны вдвое уже (иначе вся деталь «у ручки» и «у пола»)


def save(name: str, game: str, a: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{game}_{name}.png"), np.clip(a * 255, 0, 255).astype(np.uint8))


def load_geo(game: str) -> dict:
    """Карты геометрии: EXR (набор целиком) или .npy (файл, партия 1: часть наборов лежит в .npy)."""
    geo = SRC / "prints" / "geo"
    if all((geo / f"{game}_{k}.exr").exists() for k in ("pos", "nrm", "part")):
        return P.load_geo(SRC, game)
    import json
    g = {k: np.load(geo / f"{game}_{k}.npy").astype(np.float32) for k in ("pos", "nrm", "part")}
    g["part_id"] = np.rint(g["part"][..., 0]).astype(np.int32)
    g["names"] = {int(k): v for k, v in json.loads((geo / f"{game}_parts.json").read_text(encoding="utf-8")).items()}
    return g


def clean(zone: np.ndarray, win: int = 13, dens: float = 0.4) -> np.ndarray:
    """Кромочная зона без «штриховки»: панели с шумной нормалью давали плотную сетку полос по всей плоскости, а
    настоящая кромка — полоса в 3–5 пикселей (плотность в окне ~0,2–0,3): где плотнее — не кромка."""
    d = cv2.boxFilter((zone > 0.5).astype(np.float32), -1, (win, win))
    z = np.where(d > dens, 0.0, zone)
    return np.where(z < 0.35, 0.0, z).astype(np.float32)   # слабый серый фон панелей — не кромка


def zones(game: str) -> None:
    g = load_geo(game)
    pos, nrm = g["pos"], g["nrm"]
    valid = FZ.core(g["part_id"] > 0)
    zmin = float(pos[..., 2][valid].min())
    h = pos[..., 2] - zmin
    # круг 3: цепочка сколов должна читаться с двух метров при 0,85 пикс/мм — полоса 4–16 мм; сейф и ячейка — тонкая 1,5–5 мм
    if want("edge"):
        save("edge", game, clean(clean(FZ.edge_zone(g, 0.004, 0.016), 9, 0.95), 41, 0.45))
    if want("edge_c"):
        # круг 4: прерывистая светлая линия 3–6 мм вдоль длинных рёбер (рисунок кладёт Painter крупными чешуйками)
        save("edge_c", game, clean(clean(FZ.edge_zone(g, 0.003, 0.006), 9, 0.95), 41, 0.45))
    if want("edge_s"):
        # сейф и ячейка: сколы только по самим рёбрам — полоса 2–6 мм у границ островов, кольцо у лимба и т. п. вне
        z = clean(clean(FZ.edge_zone(g, 0.002, 0.006), 9, 0.95), 41, 0.30)
        save("edge_s", game, z * island_border(g, 7))
    if want("edgew"):
        save("edgew", game, clean(clean(FZ.edge_zone(g, 0.004, 0.024), 9, 0.95), 41, 0.45))
    if want("inside") and game in INSIDE:
        m = FZ.parts(g, *INSIDE[game]) & valid
        c = pos[FZ.parts(g, INSIDE[game][0]) & valid].mean(0)
        v = c - pos
        cosv = (nrm * v).sum(-1) / (np.linalg.norm(v, axis=-1) + 1e-6)
        save("inside", game, smooth(cosv, 0.1, 0.5) * m)
    elif want("inside"):
        save("inside", game, np.zeros(valid.shape, np.float32))
    save("up", game, smooth(nrm[..., 2], 0.55, 0.95) * valid)
    k = 0.35 if game in SMALL else 1.0
    save("floor", game, (1 - smooth(h, 0.12 * k, 0.25 * k)) * valid)   # нижние 20–25 см (малые предметы — ниже)
    vert = 1 - smooth(np.abs(nrm[..., 2]), 0.2, 0.5)
    save("kick", game, (1 - smooth(h, 0.12, 0.30)) * vert * valid)
    k2 = 0.5 if (game in SMALL or game == "lc_safe") else 1.0
    hand = FZ.parts(g, *TOUCH[game])
    if hand.any():
        d, _ = cKDTree(pos[hand][::3]).query(pos[valid])
        dist = np.full(valid.shape, 9.0, np.float32)
        dist[valid] = d
        save("touch", game, (1 - smooth(dist, 0.02 * k2, 0.08 * k2)) * valid)
        save("touch_core", game, (1 - smooth(dist, 0.0, 0.03 * k2)) * valid)
    else:
        save("touch", game, np.zeros(valid.shape, np.float32))
        save("touch_core", game, np.zeros(valid.shape, np.float32))
    drip = FZ.parts(g, *DRIP[game]) if game in DRIP else None
    if drip is not None and drip.any():
        zmax = float(pos[..., 2][drip].max())
        d, _ = cKDTree(pos[drip][::3]).query(pos[valid])
        dd = np.full(valid.shape, 9.0, np.float32)
        dd[valid] = d
        save("drip", game, (1 - smooth(dd, 0.0, 0.12)) * (pos[..., 2] < zmax) * valid)
    else:
        save("drip", game, np.zeros(valid.shape, np.float32))
    kp = FZ.parts(g, *KEYS[game]) if game in KEYS else None
    if kp is not None and kp.any():
        d, _ = cKDTree(pos[kp][::3]).query(pos[valid])
        dd = np.full(valid.shape, 9.0, np.float32)
        dd[valid] = d
        # верх клавиш чистый: грязь — в щелях между клавишами и у их оснований (на корпусе и боках клавиш)
        tops = kp & (nrm[..., 2] > 0.7)
        save("keyfield", game, (1 - smooth(dd, 0.004, 0.02)) * valid * (~tops))
    else:
        save("keyfield", game, np.zeros(valid.shape, np.float32))
    print("зоны", game, valid.shape, "zmin %.3f" % zmin, flush=True)


if __name__ == "__main__":
    for n in sys.argv[1:] or ITEMS:
        zones(n)
