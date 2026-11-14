"""Опоры касс v01, отделка: замер карты цвета (приём lc3_measure.py) — медиана и разброс base color на плоскости детали
(лицо с нормалью к зрителю, без зон кромки, касания, низа, верха и следов ног), доля «сердечника» вдоль кромок.

  python -X utf8 -I tools/loot_containers/counters_measure.py [набор деталь [ось±]] …
  по умолчанию: cn_counter ПТ_панель_передняя −y, cn_checkout КБ_корпус −y
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "loot_containers"
GEO = SRC / "prints" / "geo_counters"


def zone(game, name):
    return cv2.imread(str(SRC / "wear_counters" / f"{game}_{name}.png"), 0).astype(np.float32) / 255.0


def measure(game: str, part: str, axis: str = "-y") -> None:
    nrm = np.load(GEO / f"{game}_nrm.npy")
    pid = np.rint(np.load(GEO / f"{game}_part.npy")[..., 0]).astype(np.int32)
    names = {int(k): v for k, v in json.loads((GEO / f"{game}_parts.json").read_text(encoding="utf-8")).items()}
    ids = [i for i, n in names.items() if n.split(".")[0] == part]
    img = cv2.imread(str(SRC / "maps_counters" / game / f"{game}_baseColor.png"), cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32)
    k = "xyz".index(axis[1])
    sgn = -1 if axis[0] == "-" else 1
    m = np.isin(pid, ids)
    m = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    plane = m & (nrm[..., k] * sgn > 0.9)
    for zn in ("edgew", "touch", "floor", "up", "kick", "front_knee"):
        plane &= zone(game, zn) < 0.05
    px = img[plane]
    print(f"{game} / {part} ({axis}): пикселей плоскости {len(px)}")
    if not len(px):
        return
    print("  медиана RGB", np.median(px, 0).round(1), " среднее", px.mean(0).round(1))
    print("  разброс (σ) RGB", px.std(0).round(2), " 5–95 перцентили по G: %.1f … %.1f" % tuple(np.percentile(px[:, 1], [5, 95])))
    e = np.isin(pid, ids) & (zone(game, "edge") > 0.5)
    lum = img.mean(-1)
    thr = float(np.median(px.mean(-1)))
    print(f"  кромка (зона edge > 0,5): пикселей {int(e.sum())}, отличается от плоскости больше чем на 30/255: "
          f"{float((np.abs(lum[e] - thr) > 30).mean()):.2%}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        a = ["cn_counter", "ПТ_панель_передняя", "-y", "cn_checkout", "КБ_корпус", "-y"]
    for i in range(0, len(a), 3):
        measure(a[i], a[i + 1], a[i + 2] if i + 2 < len(a) else "-y")
