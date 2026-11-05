# «Осока»: наложение рендера вида слева на снимок КБМ (50 %) и контуры силуэтов — где расходятся.
# python -X utf8 tools/osoka/overlay.py <снимок КБМ> <рендер> <выход.png>
# Снимок срезается по наклону оси трубы (lib: y = 414 − 0.0043·(x − 1700)), чтобы ось стала горизонтальной на y = 414.
import sys

import numpy as np
from PIL import Image, ImageChops, ImageFilter

AXIS_Y0, AXIS_X0, AXIS_K = 414.0, 1700.0, 0.0043


def main() -> None:
    src, model, out = sys.argv[1:4]
    a = Image.open(src).convert("RGB")
    # выход (x, y) ← вход (x, y − K·(x − X0)): ось на всём снимке на y = 414
    a = a.transform(a.size, Image.AFFINE, (1, 0, 0, -AXIS_K, 1, AXIS_K * AXIS_X0), resample=Image.BICUBIC,
                    fillcolor=(255, 255, 255))
    b = Image.open(model).convert("RGB").resize(a.size)
    blend = Image.blend(a, b, 0.5)
    # силуэты: фото — не белое, модель — не фон рендера
    fa = (np.asarray(a).min(axis=2) < 215)
    bg = np.asarray(b)[2, 2].astype(int)
    fb = (np.abs(np.asarray(b).astype(int) - bg).sum(axis=2) > 25)
    ea = np.asarray(Image.fromarray((fa * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)) > 0
    eb = np.asarray(Image.fromarray((fb * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)) > 0
    arr = np.asarray(blend).copy()
    arr[ea] = (220, 30, 30)       # контур снимка — красный
    arr[eb] = (30, 90, 230)       # контур модели — синий
    Image.fromarray(arr).save(out)
    inter = (fa & fb).sum(); union = (fa | fb).sum()
    print("OVERLAY", out, "IoU", round(inter / max(union, 1), 4), "photo_only", int((fa & ~fb).sum()),
          "model_only", int((fb & ~fa).sum()))


main()
