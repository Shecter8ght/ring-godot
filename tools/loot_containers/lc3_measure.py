"""Замеры карты цвета v03 по числам владельца (пипетка по образцам): медиана и разброс base color на плоскости двери и доля
светлых пикселей вдоль рёбер двери.

  python -X utf8 -I tools/loot_containers/lc3_measure.py [набор] [деталь-дверь]   # по умолчанию lc_gun ОШ_створка_лев

Плоскость двери — лицо детали (нормаль к зрителю, −Y) без зон кромки, ручки, потёков, низа, верха; цифры — sRGB 0…255.
"""
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "loot_containers"))
import lc3_zones as Z  # noqa: E402


def zone(game: str, name: str) -> np.ndarray:
    return cv2.imread(str(Z.OUT / f"{game}_{name}.png"), 0).astype(np.float32) / 255.0


def main() -> None:
    game = sys.argv[1] if len(sys.argv) > 1 else "lc_gun"
    part = sys.argv[2] if len(sys.argv) > 2 else "ОШ_створка_лев"
    g = Z.load_geo(game)
    img = cv2.imread(str(ROOT / "_asset_src" / "loot_containers" / "maps_v03" / game / f"{game}_baseColor.png"), cv2.IMREAD_COLOR)
    img = img[..., ::-1].astype(np.float32)   # RGB
    m = Z.FZ.core(Z.FZ.parts(g, part), 3)
    front = m & (g["nrm"][..., 1] < -0.9)
    plane = front.copy()
    for zn in ("edgew", "touch", "drip", "floor", "up"):
        plane &= zone(game, zn) < 0.05
    px = img[plane]
    print(f"{game} / {part}: пикселей плоскости {len(px)}")
    print("  медиана RGB", np.median(px, 0).round(1), " среднее", px.mean(0).round(1))
    print("  разброс (σ) RGB", px.std(0).round(2), " 5–95 перцентили по G: %.1f … %.1f" % tuple(np.percentile(px[:, 1], [5, 95])))
    e = m & (zone(game, "edge") > 0.5)
    lum = img.mean(-1)
    thr = float(np.median(px.mean(-1))) + 30
    print(f"  кромка (зона edge >0,5): пикселей {int(e.sum())}, светлее плоскости на 30/255: {float((lum[e] > thr).mean()):.2%}")
    # вдоль одного ребра: самая длинная полоса зоны edge — доля светлых по строке/столбцу окна 9×9
    near = cv2.dilate(e.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    print(f"  в окне 9×9 вдоль кромки светлых пикселей: {float((lum[near & m] > thr).mean()):.2%}")


if __name__ == "__main__":
    main()
