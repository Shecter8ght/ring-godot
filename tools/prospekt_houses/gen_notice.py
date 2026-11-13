"""Лист-объявление А4 для двери вестибюля дома 7 (вымышленная нейтральная табличка, без названий, дат и сведений): пожелтевшая бумага,
крупно «ПОДЪЕЗД ЗАКРЫТ», ниже мелкий нечитаемый текст, выцветшая печать. Шрифт DejaVu Sans Bold (из matplotlib).
  python -X utf8 tools/prospekt_houses/gen_notice.py   →  E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures/notice.png
"""
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import matplotlib

OUT = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures"
FONT = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSans-Bold.ttf")
W, H = 1240, 1754
rng = random.Random(4)


def main():
    # бумага: тёплая, пожелтевшая к краям, пятна по маске владельца (налёт)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = np.minimum(np.minimum(xx, W - xx), np.minimum(yy, H - yy)) / 260.0
    edge = np.clip(edge, 0, 1)
    base = np.zeros((H, W, 3), np.float32)
    base[...] = (236, 228, 205)
    yel = (1 - edge)[..., None] * np.array([-28, -52, -62], np.float32)
    mask = Image.open(OUT + "/masks/m_plaque.png").convert("L").resize((W, H))
    m = np.asarray(mask, np.float32)[..., None] / 255.0
    arr = np.clip(base + yel - m * np.array([30, 40, 52], np.float32), 0, 255)
    im = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(im)
    big = ImageFont.truetype(FONT, 205)
    for i, line in enumerate(("ПОДЪЕЗД", "ЗАКРЫТ")):
        tw = d.textlength(line, font=big)
        d.text(((W - tw) / 2, 190 + i * 250), line, font=big, fill=(28, 26, 24))
    small = ImageFont.truetype(FONT, 38)
    letters = "абвгдежзиклмнопрстуфхцчшэюя"
    y = 860
    for _ in range(5):
        words = ["".join(rng.choice(letters) for _ in range(rng.randint(3, 9))) for _ in range(rng.randint(5, 9))]
        d.text((130, y), " ".join(words), font=small, fill=(40, 38, 36))
        y += 62
    # печать: два кольца, ряды чёрточек вместо текста, повернута и выцвела
    st = Image.new("RGBA", (420, 420), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    col = (96, 58, 120, 200)
    sd.ellipse((8, 8, 412, 412), outline=col, width=10)
    sd.ellipse((60, 60, 360, 360), outline=col, width=6)
    for k in range(5):
        sd.line((110, 150 + k * 28, 310 - rng.randint(0, 50), 150 + k * 28), fill=col, width=7)
    st = st.rotate(-17, resample=Image.BICUBIC)
    st = st.filter(ImageFilter.GaussianBlur(1.2))
    im.paste(st, (700, 1210), st)
    im = im.filter(ImageFilter.GaussianBlur(0.9))
    # царапины-складки: горизонтальный сгиб посередине (лист был в файле)
    a = np.asarray(im).astype(np.float32)
    a[H // 2 - 3:H // 2 + 3] *= 0.93
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(OUT + "/notice.png")
    print("notice ok")


main()
