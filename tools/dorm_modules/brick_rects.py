"""Кирпичи с фотоскана стены (Red Bricks 04, CC0): прямоугольники отдельных кирпичей без швов — для развёртки
обломков (tools/dorm_modules/build_rubble.py: каждый кирпич берёт лицо случайного настоящего кирпича).

  python -X utf8 tools/dorm_modules/brick_rects.py [--preview]

Раствор на фото — светлый и мало насыщенный, кирпич — красный: маска по насыщенности и тону, размыкание, связные
области; берутся области размером с ложок (≈ 3,2–4,6 к 1), прямоугольник ужат внутрь на 12 %, чтобы не задеть шов.
Выход — _asset_src/dorm_textures/ph_red_bricks_04_4k/brick_rects.json (доли картинки: u0, v0, u1, v1; v — снизу,
как в Blender), --preview — снимок с рамками рядом.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "dorm_textures" / "ph_red_bricks_04_4k"


def main() -> None:
    im = Image.open(SRC / "red_bricks_04_diff_4k.jpg").convert("RGB")
    w, h = im.size
    hsv = np.asarray(im.convert("HSV")).astype(np.float32) / 255.0
    sat, val = hsv[..., 1], hsv[..., 2]
    hue = hsv[..., 0]
    brick = (sat > 0.42) & ((hue < 0.09) | (hue > 0.95)) & (val > 0.12)
    brick = ndimage.binary_opening(brick, structure=np.ones((5, 5)))
    brick = ndimage.binary_fill_holes(brick)
    lab, n = ndimage.label(brick)
    rects = []
    for sl in ndimage.find_objects(lab):
        if sl is None:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        bw, bh = x1 - x0, y1 - y0
        if bh < 25 or bw < 90:
            continue
        aspect = bw / bh
        if not 3.0 <= aspect <= 4.8:
            continue
        fill = (lab[y0:y1, x0:x1] > 0).mean()
        if fill < 0.8:
            continue
        ix, iy = bw * 0.12, bh * 0.12
        u0, u1 = (x0 + ix) / w, (x1 - ix) / w
        v0, v1 = 1.0 - (y1 - iy) / h, 1.0 - (y0 + iy) / h
        rects.append([round(u0, 5), round(v0, 5), round(u1, 5), round(v1, 5)])
    out = SRC / "brick_rects.json"
    out.write_text(json.dumps({"source": "red_bricks_04_diff_4k.jpg", "rects": rects}, indent=0), encoding="utf-8")
    print("bricks", len(rects), "of", n, "->", out)
    if "--preview" in sys.argv:
        pv = im.copy()
        d = ImageDraw.Draw(pv)
        for u0, v0, u1, v1 in rects:
            d.rectangle([u0 * w, (1 - v1) * h, u1 * w, (1 - v0) * h], outline=(0, 255, 0), width=4)
        pv.resize((1024, 1024)).save(SRC / "brick_rects_preview.jpg")


if __name__ == "__main__":
    main()
