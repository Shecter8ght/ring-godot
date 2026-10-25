"""Склейка проверочных снимков в один лист (для себя): sheet.py <выход.jpg> <ширина_ячейки> <снимок> ..."""
import sys
from PIL import Image
out, w = sys.argv[1], int(sys.argv[2])
ims = [Image.open(p) for p in sys.argv[3:]]
ims = [im.resize((w, int(im.height * w / im.width))) for im in ims]
cols = 2 if len(ims) > 1 else 1
rows = (len(ims) + cols - 1) // cols
h = max(im.height for im in ims)
sheet = Image.new("RGB", (cols * w, rows * h), (30, 30, 30))
for i, im in enumerate(ims):
    sheet.paste(im, ((i % cols) * w, (i // cols) * h))
sheet.save(out, quality=86)
print(out)
