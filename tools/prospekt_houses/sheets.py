"""Листы сверки дома 7: концепт слева, наш кадр справа (PIL).
python -X utf8 tools/prospekt_houses/sheets.py <папка form>
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CONCEPT = Path(__file__).resolve().parents[2] / "референсы/prospekt_bc5_yard/concepts/04_house_9f_brutalist_podium.webp"
form = Path(sys.argv[1])
c = Image.open(CONCEPT).convert("RGB")
H = 760
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)


def sheet(name, ccrop, ours, ocrop, title):
    a = c.crop(ccrop)
    b = Image.open(form / ours).convert("RGB").crop(ocrop)
    a = a.resize((int(a.width * H / a.height), H), Image.LANCZOS)
    b = b.resize((int(b.width * H / b.height), H), Image.LANCZOS)
    im = Image.new("RGB", (a.width + b.width + 30, H + 40), (235, 232, 230))
    im.paste(a, (10, 30)); im.paste(b, (a.width + 20, 30))
    d = ImageDraw.Draw(im)
    d.text((12, 6), "КОНЦЕПТ  " + title, fill=(0, 0, 0), font=FONT)
    d.text((a.width + 22, 6), "НАШЕ (Blender, форма)", fill=(0, 0, 0), font=FONT)
    im.save(form / name)


sheet("сверка_front.png", (60, 5, 470, 500), "ortho_south.png", (150, 20, 950, 890), "FRONT")
sheet("сверка_rear.png", (570, 5, 980, 500), "ortho_north.png", (150, 20, 950, 890), "REAR")
sheet("сверка_right.png", (1090, 5, 1480, 500), "ortho_east.png", (195, 20, 865, 900), "RIGHT")
sheet("сверка_portal.png", (1002, 545, 1536, 985), "cam_portal.png", (0, 0, 1600, 1000), "DETAIL входа")
print("ok")
