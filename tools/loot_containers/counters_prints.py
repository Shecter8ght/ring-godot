"""Опоры касс v01, отделка: печать (вымышленная, DejaVu Sans) в развёртку по картам геометрии counters_bake.py.
  • бокс: табличка номера кассы «3» на обеих панелях стойки (цифра с двух сторон читается правильно), мелкая надпись «КАССА»;
  • прилавок: наклейка-инвентарник на боковине (рамка, «ИНВ. № 04-117», штрихи вместо кода, надорванный угол).
Реальных марок и сюжетных сведений нет.

  python -X utf8 -I tools/loot_containers/counters_prints.py [набор …]
→ _asset_src/loot_containers/wear_counters/<набор>_print_color.png и _print_alpha.png (размер набора)
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "_asset_src" / "loot_containers" / "prints" / "geo_counters"
OUT = ROOT / "_asset_src" / "loot_containers" / "wear_counters"
FONTS = Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf")
BOLD, REG = str(FONTS / "DejaVuSans-Bold.ttf"), str(FONTS / "DejaVuSans.ttf")


def font(path, px):
    return ImageFont.truetype(path, px)


def sign_art(w=1040, h=640):
    """Табличка номера: белая пластина, цифра «3» тёмно-серо-синяя, под ней «КАССА»; тонкая рамка."""
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (38, 46, 58, 255)
    d.rounded_rectangle((18, 18, w - 18, h - 18), 36, outline=ink, width=10)
    f = font(BOLD, 420)
    bb = d.textbbox((0, 0), "3", font=f)
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], 40 - bb[1]), "3", font=f, fill=ink)
    f2 = font(BOLD, 74)
    bb = d.textbbox((0, 0), "КАССА", font=f2)
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], h - 150 - bb[1]), "КАССА", font=f2, fill=ink)
    return im


def sticker_art(w=800, h=480):
    """Инвентарная наклейка: бумага, рамка, строки, штрих-полосы, надорванный правый верхний угол (прозрачный срез)."""
    im = Image.new("RGBA", (w, h), (226, 222, 205, 255))
    d = ImageDraw.Draw(im)
    ink = (40, 40, 44, 255)
    d.rectangle((14, 14, w - 14, h - 14), outline=ink, width=6)
    d.text((40, 36), "ИНВ. № 04-117", font=font(BOLD, 74), fill=ink)
    d.text((40, 140), "прилавок торговый", font=font(REG, 50), fill=ink)
    d.text((40, 206), "уч. 2 / 2018", font=font(REG, 50), fill=ink)
    rnd = random.Random(7)
    x = 40
    while x < w - 160:
        bw = rnd.choice((4, 6, 10, 14))
        d.rectangle((x, 290, x + bw, 440), fill=ink)
        x += bw + rnd.choice((4, 8, 12))
    d.polygon([(w, 0), (w - 150, 0), (w - 60, 60), (w, 170)], fill=(0, 0, 0, 0))
    return im


def paint(game: str, key: str, plates, canvas_by_part) -> None:
    pos = np.load(GEO / f"{game}_pos.npy").astype(np.float32)
    nrm = np.load(GEO / f"{game}_nrm.npy").astype(np.float32)
    pid = np.rint(np.load(GEO / f"{game}_part.npy")[..., 0]).astype(np.int32)
    names = {int(k): v for k, v in json.loads((GEO / f"{game}_parts.json").read_text(encoding="utf-8")).items()}
    res = pos.shape[0]
    col = np.zeros((res, res, 3), np.uint8)
    alpha = np.zeros((res, res), np.uint8)
    for pname, fn in plates:
        ids = [i for i, n in names.items() if n.split(".")[0] == pname]
        if not ids:
            print("нет детали", pname)
            continue
        art = canvas_by_part[pname]
        aw, ah = art.size
        arr = np.asarray(art)
        m = np.isin(pid, ids)
        ys, xs = np.nonzero(m)
        for sgn in (-1, 1):
            sel = nrm[ys, xs, 0] * sgn > 0.9
            yy, xx = ys[sel], xs[sel]
            if not len(yy):
                continue
            u, v = fn(pos[yy, xx], sgn)
            ok = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
            px = np.clip((u * aw).astype(int), 0, aw - 1)
            py = np.clip(((1 - v) * ah).astype(int), 0, ah - 1)
            c = arr[py, px]
            col[yy[ok], xx[ok]] = c[ok, :3]
            alpha[yy[ok], xx[ok]] = c[ok, 3]
    OUT.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT / f"{game}_{key}_color.png"), col[..., ::-1])
    cv2.imwrite(str(OUT / f"{game}_{key}_alpha.png"), alpha)
    print("печать", game, "покрыто %.4f" % float((alpha > 0).mean()))


def sign_uv(p, sgn):
    py, z0 = 0.48, 1.81
    y = p[:, 1] - py
    u = 0.5 + sgn * y / 0.26
    return u, (p[:, 2] - z0) / 0.16


def sign_bg(art: Image.Image, bg=(236, 236, 230)) -> Image.Image:
    base = Image.new("RGBA", art.size, bg + (255,))
    base.alpha_composite(art)
    return base


def main() -> None:
    want = sys.argv[1:] or ["cn_counter", "cn_checkout"]
    if "cn_checkout" in want:
        # цифра с обеих сторон; белая пластина целиком красится печатью (бумажно-белый 236 — не ярче 235 sRGB по заданию → 232)
        paint("cn_checkout", "print", [("КБ_табличка_панели", sign_uv)], {"КБ_табличка_панели": sign_bg(sign_art(), (230, 230, 224))})
    if "cn_counter" in want:
        def stk(p, sgn):
            # наклейка на боковине x = −0,75 (нормаль −x): взгляд с −x, вправо — −y
            u = 0.5 - (p[:, 1] + 0.10) / 0.10
            return u, (p[:, 2] - 0.53) / 0.06
        art = sticker_art()
        paint("cn_counter", "print", [("ПТ_наклейка_инвентарник", stk)], {"ПТ_наклейка_инвентарник": art})


if __name__ == "__main__":
    main()
