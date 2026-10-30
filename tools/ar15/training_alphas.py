# AR-15, тренировочная копия Painter: штампы-альфы для кисти из фото-масок CC0 библиотеки владельца
# (`Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures`, план износа — «маски с фото, не нейросетевые»).
# Карты ambientCG / ShareTextures — сплошные поля во весь квадрат: кистью таким полем ставится квадрат с краями и
# десятками отпечатков сразу. Здесь — вырезка участка (несколько отпечатков, пара мазков), растяжка уровней (маски
# тусклые, 0,2–0,3 в среднем — без неё штамп слабый) и круглое затухание к краю (штамп без рамки).
#   python -X utf8 tools/ar15/training_alphas.py [папка]
# По умолчанию пишет в полку Painter владельца (Documents/…/assets/alphas/RING_CC0_штампы) и лист превью
# в папку тренировочной копии; удалить папку из полки можно в любой момент — проекты от неё не зависят.
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SRC = "E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures"
SHELF = os.path.expanduser("~/Documents/Adobe/Adobe Substance 3D Painter/assets/alphas/RING_CC0_штампы")
SHEET = "E:/Models Blender/WEAPONS/AR-15 — модель/Тренировка_текстурирование/img/штампы_CC0.jpg"
SIZE = 1024

# имя штампа: (файл, доля стороны вырезки, центр вырезки (x, y), нижний и верхний перцентиль уровней, размытие)
STAMPS = {
    "CC0 Отпечатки 01 — несколько пальцев": ("Fingerprints002_2K-PNG_Opacity.png", 0.33, (0.30, 0.35), 45, 99.7, 0),
    "CC0 Отпечатки 02 — несколько пальцев": ("Fingerprints003_2K-PNG_Opacity.png", 0.33, (0.62, 0.55), 45, 99.7, 0),
    "CC0 Отпечатки 03 — плотные": ("Fingerprints001_2K-PNG_Opacity.png", 0.30, (0.50, 0.50), 35, 99.7, 0),
    "CC0 Отпечатки 04 — смазанные": ("Fingerprints009_2K-PNG_Opacity.png", 0.35, (0.45, 0.40), 30, 99.5, 0),
    "CC0 Отпечатки 05 — редкие": ("Fingerprints007_2K-PNG_Opacity.png", 0.40, (0.50, 0.50), 80, 99.8, 0),
    "CC0 Ладонь 01": ("Fingerprints004_2K-PNG_Opacity.png", 1.00, (0.50, 0.50), 2, 99.8, 0),
    "CC0 Развод 01 — круглый": ("Smear001_2K-JPG_Roughness.jpg", 1.00, (0.50, 0.50), 5, 99.8, 0),
    "CC0 Развод 02 — жирные мазки": ("Smear002_2K-JPG_Roughness.jpg", 0.40, (0.50, 0.50), 60, 99.6, 2),
    "CC0 Мазки 01 — штрихи": ("Smear005_2K-PNG_Opacity.png", 1.00, (0.50, 0.50), 2, 99.8, 0),
    "CC0 Протирка 01 — полосы": ("Smear006_2K-PNG_Opacity.png", 0.40, (0.50, 0.45), 30, 99.5, 2),
    "CC0 Царапины 01 — вдоль одной линии": ("Scratches001_2K-PNG_Opacity.png", 0.40, (0.50, 0.50), 20, 99.8, 0),
    "CC0 Царапины 02 — в разные стороны": ("Scratches002_2K-PNG_Opacity.png", 0.40, (0.45, 0.50), 10, 99.8, 0),
    "CC0 Царапины 03 — мелкие редкие": ("Scratches003_2K-PNG_Opacity.png", 0.50, (0.50, 0.50), 10, 99.8, 0),
    "CC0 Царапины 04 — пучок": ("scratches_5-4K.png", 0.30, (0.50, 0.50), 10, 99.8, 0),
    "CC0 Пыль 01 — крапинки": ("SurfaceImperfections007_2K-PNG_Opacity.png", 0.35, (0.50, 0.50), 0, 99.5, 0),
    "CC0 Брызги 01": ("SurfaceImperfections009_2K-PNG_Opacity.png", 0.40, (0.55, 0.45), 20, 99.5, 0),
    "CC0 Пятна 01 — мягкие": ("SurfaceImperfections001_2K-PNG_Opacity.png", 0.35, (0.50, 0.50), 30, 99.5, 3),
    "CC0 Грязь 01 — рваная": ("dirt_5-2K.png", 0.30, (0.50, 0.50), 20, 99.5, 0),
}


def find(fname):
    for root, _, files in os.walk(SRC):
        if fname in files:
            return os.path.join(root, fname)
    raise FileNotFoundError(fname)


def vignette(n):
    """Круглое затухание: внутри 0,3 радиуса — целиком, к 0,5 — в ноль (плавно)."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.hypot(x - (n - 1) / 2, y - (n - 1) / 2) / n
    t = np.clip((0.5 - r) / 0.2, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def stamp(spec):
    fname, frac, (cx, cy), lo, hi, blur = spec
    im = Image.open(find(fname)).convert("L")
    w, h = im.size
    side = int(min(w, h) * frac)
    x0 = int(np.clip(cx * w - side / 2, 0, w - side))
    y0 = int(np.clip(cy * h - side / 2, 0, h - side))
    im = im.crop((x0, y0, x0 + side, y0 + side)).resize((SIZE, SIZE), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32) / 255.0
    a0, a1 = np.percentile(a, [lo, hi])
    a = np.clip((a - a0) / max(a1 - a0, 1e-6), 0.0, 1.0) * vignette(SIZE)
    return Image.fromarray((a * 255.0 + 0.5).astype(np.uint8))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else SHELF
    os.makedirs(out, exist_ok=True)
    tiles = []
    for name, spec in STAMPS.items():
        im = stamp(spec)
        im.save(os.path.join(out, name + ".png"))
        tiles.append((name, im))
        print(name, spec[0])
    with open(os.path.join(out, "ИСТОЧНИКИ.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("Штампы для кисти Painter из фото-масок CC0 1.0 (ambientCG — https://ambientcg.com, ShareTextures — "
                "https://www.sharetextures.com).\nСобраны tools/ar15/training_alphas.py (проект RING) из\n"
                + SRC + "\n\n" + "\n".join(f"{n}: {s[0]}" for n, s in STAMPS.items()) + "\n")
    # лист превью для инструкции: 6 в ряд, подписи
    cols, cell, cap = 6, 220, 34
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + cap)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, (name, im) in enumerate(tiles):
        x, y = (i % cols) * cell, (i // cols) * (cell + cap)
        sheet.paste(im.resize((cell - 8, cell - 8)).convert("RGB"), (x + 4, y + 4))
        text = name.replace("CC0 ", "")
        for j, line in enumerate([text[:30], text[30:60]]):
            draw.text((x + 6, y + cell + 1 + j * 15), line, fill=(220, 220, 220), font=font)
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    sheet.save(SHEET, quality=90)
    print("лист", SHEET)


if __name__ == "__main__":
    main()
