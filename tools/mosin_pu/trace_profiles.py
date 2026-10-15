"""Профили из подложки blueprint_right.png (координаты модели, 4 px/мм).

python -X utf8 tools/mosin_pu/trace_profiles.py

Для каждого x (шаг 1 мм) — интервалы силуэта по z и интервалы «дерева» (красно-коричневый цвет).
Пишет trace/profiles.json; таблицу с шагом 10 мм печатает для просмотра.
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ASSET = r"E:\Models Blender\WEAPONS\Мосин — винтовка и узлы"
TR = os.path.join(ASSET, "trace")


def runs(col, z_of_row, min_len=3):
    ys = np.nonzero(col)[0]
    if len(ys) == 0:
        return []
    sp = np.split(ys, np.nonzero(np.diff(ys) > 1)[0] + 1)
    return [(round(float(z_of_row(s.max())), 2), round(float(z_of_row(s.min())), 2)) for s in sp if len(s) >= min_len]


def main():
    meta = json.load(open(os.path.join(TR, "blueprint.json"), encoding="utf-8"))
    P, X0, Z1 = meta["px_per_mm"], meta["x0"], meta["z1"]
    a = np.asarray(Image.open(os.path.join(TR, "blueprint_right.png")).convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    # фон: медиана верхних/нижних строк серого поля
    lum = a.mean(-1)
    bg_rows = [y for y in range(h) if lum[y].mean() < 240]
    top = np.median(a[bg_rows[0]:bg_rows[0] + 20], axis=0)
    bot = np.median(a[bg_rows[-1] - 20:bg_rows[-1]], axis=0)
    t = np.clip((np.arange(h)[:, None, None] - bg_rows[0]) / (bg_rows[-1] - bg_rows[0]), 0, 1)
    bg = top[None] * (1 - t) + bot[None] * t
    d = np.sqrt(((a - bg) ** 2).sum(-1))
    sil = ndi.binary_opening(d > 24, np.ones((3, 3)))
    lab, n = ndi.label(sil)
    sizes = ndi.sum(sil, lab, range(1, n + 1))
    sil = lab == (np.argmax(sizes) + 1)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    wood = (r - b > 30) & (r - g > 12) & (r > 55) & sil
    wood = ndi.binary_closing(ndi.binary_opening(wood, np.ones((3, 3))), np.ones((5, 5)))
    z_of_row = lambda row: Z1 - (row + 0.5) / P  # noqa: E731
    out = {"x": [], "sil": [], "wood": []}
    for xm in range(int(X0) + 1, int(meta["x1"])):
        c = int((xm - X0) * P)
        out["x"].append(xm)
        out["sil"].append(runs(sil[:, c], z_of_row))
        out["wood"].append(runs(wood[:, c], z_of_row, 6))
    json.dump(out, open(os.path.join(TR, "profiles.json"), "w", encoding="utf-8"))
    Image.fromarray((np.stack([sil * 200, wood * 255, np.zeros_like(sil)], -1)).astype(np.uint8)).save(
        os.path.join(TR, "masks_check.png"))
    for i in range(0, len(out["x"]), 10):
        print(out["x"][i], "W", out["wood"][i], "S", out["sil"][i])


main()
