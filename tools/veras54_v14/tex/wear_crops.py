"""ВЕРАС-54 v14, износ: кропы карт 1:1 по месту износа — «было | стало» (диагноз «мыла» и проверка правки).
Окно — там, где карта места (wear_place.py) набирает больше всего, в пикселях разрешения набора; карты обеих версий
режутся одним окном без масштабирования (1:1), затем лист увеличивается целым множителем (ближайший сосед — пиксели
видны как есть).

    python -X utf8 tools/veras54_v14/tex/wear_crops.py <лист.png> <набор> <место> <папка А>:<подпись> <папка Б>:<подпись> [окно=384] [зум=2]
      место — имя карты места (z_cover_rear_top, z_top_rail_wear, …); строки листа — baseColor, шероховатость (G ORM),
      металл (B ORM), нормаль
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets as T  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
WEAR = T.WORK + "/wear"


def window(set_name, place, win):
    m = np.asarray(Image.open(f"{WEAR}/{set_name}_{place}.png").convert("L"), np.float32) / 255.0
    n = m.shape[0]
    # сумма по окну через интеграл: окно с наибольшей массой места
    ii = np.pad(m.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    s = ii[win:, win:] - ii[:-win, win:] - ii[win:, :-win] + ii[:-win, :-win]
    y, x = np.unravel_index(np.argmax(s), s.shape)
    return int(x), int(y), n


def rows(folder, set_name, box, n):
    out = []
    for suf, ch, title in (("baseColor", None, "цвет"), ("occlusionRoughnessMetallic", 1, "шероховатость"),
                           ("occlusionRoughnessMetallic", 2, "металл"), ("normal", None, "нормаль")):
        im = Image.open(f"{folder}/{set_name}_{suf}.png").convert("RGB")
        if im.width != n:
            im = im.resize((n, n), Image.NEAREST)
        c = im.crop(box)
        if ch is not None:
            c = c.getchannel(ch).convert("RGB")
        elif suf == "baseColor":
            # тёмная сталь: растянуть уровни одинаково для обеих версий (×3), иначе на листе всё чёрное
            a = np.asarray(c, np.float32) * 3.0
            c = Image.fromarray(np.uint8(np.clip(a, 0, 255)))
        out.append((title, c))
    return out


def main():
    a = sys.argv[1:]
    out, set_name, place = a[0], a[1], a[2]
    cols = [x.rsplit(":", 1) for x in a[3:5]]
    win = int(a[5]) if len(a) > 5 else 384
    zoom = int(a[6]) if len(a) > 6 else 2
    x, y, n = window(set_name, place, win)
    box = (x, y, x + win, y + win)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    data = [rows(f, set_name, box, n) for f, _ in cols]
    cw = win * zoom
    sh = Image.new("RGB", (len(cols) * (cw + 8), 4 * (cw + 26) + 30), (30, 30, 30))
    d = ImageDraw.Draw(sh)
    d.text((8, 4), f"{set_name}, место {place}, окно {box} из {n}², 1:1 × {zoom} (цвет ×3 по уровням)",
           fill=(230, 230, 230), font=font)
    for ci, ((_, lab), col) in enumerate(zip(cols, data)):
        for ri, (title, im) in enumerate(col):
            px, py = ci * (cw + 8), 30 + ri * (cw + 26)
            d.text((px + 4, py + 2), f"{lab} — {title}", fill=(230, 230, 230), font=font)
            sh.paste(im.resize((cw, cw), Image.NEAREST), (px, py + 24))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    sh.save(out)
    print("CROP", out, box)


if __name__ == "__main__":
    main()
