"""Листы сверки материалов дома 7: концепт слева, наш кадр Cycles справа + замер цвета пипеткой (PIL).
python -X utf8 tools/prospekt_houses/sheets_finish.py <папка Просмотр/finish>
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
CONCEPT = ROOT / "референсы/prospekt_bc5_yard/concepts/04_house_9f_brutalist_podium.webp"
SERIES = Path(r"C:\Users\Schecter_8ght\.codex\visualizations\2026\11\08\01a1bbc7-a359-7192-a5a3-32b38b12d8af\prospekt-cordon\19-architecture-hybrid\01 Жилые — обзор.jpg")
fin = Path(sys.argv[1])
c = Image.open(CONCEPT).convert("RGB")
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
H = 760


def sheet(name, src, scrop, ours, ocrop, title, note="НАШЕ (Blender, материалы v01)"):
    a = src.crop(scrop)
    b = Image.open(fin / ours).convert("RGB").crop(ocrop)
    a = a.resize((int(a.width * H / a.height), H), Image.LANCZOS)
    b = b.resize((int(b.width * H / b.height), H), Image.LANCZOS)
    im = Image.new("RGB", (a.width + b.width + 30, H + 40), (235, 232, 230))
    im.paste(a, (10, 30)); im.paste(b, (a.width + 20, 30))
    d = ImageDraw.Draw(im)
    d.text((12, 6), title, fill=(0, 0, 0), font=FONT)
    d.text((a.width + 22, 6), note, fill=(0, 0, 0), font=FONT)
    im.save(fin / name)


sheet("сверка_front.png", c, (60, 5, 470, 500), "ortho_south.png", (170, 85, 930, 935), "КОНЦЕПТ FRONT")
sheet("сверка_portal.png", c, (1002, 545, 1536, 985), "cam_portal.png", (0, 0, 1400, 875), "КОНЦЕПТ DETAIL входа")
sheet("сверка_loggia.png", c, (1002, 545, 1536, 760), "cam_loggia_close.png", (0, 0, 1400, 875), "КОНЦЕПТ DETAIL (лоджии)")
try:
    s = Image.open(SERIES).convert("RGB")
    sheet("сверка_far.png", s, (645, 1485, 1075, 1795), "cam_avenue.png", (0, 0, 1400, 875), "СЕРИЯ: дом H10 из обзорного листа",
          "НАШЕ: дом 7 с проспекта")
except Exception as ex:
    print("far", ex)


def mean(img, b):
    a = np.asarray(img)[b[1]:b[3], b[0]:b[2]].reshape(-1, 3).astype(float)
    return tuple(int(x) for x in a.mean(0))


o = {n: Image.open(fin / (n + ".png")).convert("RGB") for n in ("cam_portal", "cam_loggia_close", "cam_eye6")}
rows = [
    ("панель бежевая", "концепт DETAIL", mean(c, (1010, 570, 1040, 650)), "кадр cam_portal", mean(o["cam_portal"], (600, 40, 740, 200))),
    ("панель бежевая 2", "концепт DETAIL", mean(c, (1470, 600, 1500, 680)), "кадр cam_loggia_close", mean(o["cam_loggia_close"], (650, 170, 730, 540))),
    ("бетон козырька", "концепт DETAIL", mean(c, (1100, 700, 1300, 730)), "кадр cam_portal", mean(o["cam_portal"], (100, 290, 700, 370))),
    ("бетон пилона", "концепт DETAIL", mean(c, (1100, 780, 1150, 860)), "кадр cam_portal", mean(o["cam_portal"], (10, 440, 130, 760))),
]
with open(fin / "сверка_цвета.txt", "w", encoding="utf-8") as f:
    for r in rows:
        f.write("%s | %s RGB%s | %s RGB%s\n" % r)
print(open(fin / "сверка_цвета.txt", encoding="utf-8").read())
