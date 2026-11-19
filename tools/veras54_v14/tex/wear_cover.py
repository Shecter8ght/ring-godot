"""ВЕРАС-54 v14, износ: доля съёма покрытия внутри места (подбор порога scan без рендера).
Съём — пиксель, где цвет износа ушёл от заводского к основанию больше чем наполовину; место — карта wear_place.py > 0,5.

    python -X utf8 tools/veras54_v14/tex/wear_cover.py <папка заводской> <папка износа> <набор>:<место> [<набор>:<место> …]
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets as T  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
BASE_L = 150.0      # светлота основания (светлая сталь ~0,6 sRGB)


def lum(p):
    return np.asarray(Image.open(p).convert("RGB"), np.float32).mean(-1)


def main():
    fac, wear = sys.argv[1], sys.argv[2]
    cache = {}
    for item in sys.argv[3:]:
        s, place = item.split(":")
        if s not in cache:
            a, b = lum(f"{fac}/{s}_baseColor.png"), lum(f"{wear}/{s}_baseColor.png")
            cache[s] = np.clip((b - a) / np.maximum(BASE_L - a, 1.0), 0, 1)
        t = cache[s]
        m = np.asarray(Image.open(f"{T.WORK}/wear/{s}_{place}.png").convert("L").resize(t.shape[::-1]), np.float32) > 127
        print(f"{s:9s} {place:24s} место {m.sum():8d} пикс, снято {100 * (t[m] > 0.5).mean():5.1f} %")


if __name__ == "__main__":
    main()
