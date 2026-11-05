# «Осока» (ПЗРК по образцу 9К333): участок снимка с координатной сеткой — для снятия точек контуров вручную.
# python -X utf8 tools/osoka/trace_grid.py <снимок> <x0> <y0> <x1> <y1> <выход.jpg> [шаг сетки, пикс] [увеличение]
# Подписи — координаты исходного снимка (пиксели), линии через «шаг»; толстая — через 5 шагов.
import sys

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    src, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
    step = int(sys.argv[7]) if len(sys.argv) > 7 else 10
    k = float(sys.argv[8]) if len(sys.argv) > 8 else 2.0
    im = Image.open(src).convert("RGB").crop((x0, y0, x1, y1))
    im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 12)
    except OSError:
        f = ImageFont.load_default()
    gx = (x0 // step + 1) * step
    while gx < x1:
        X = (gx - x0) * k
        major = gx % (step * 5) == 0
        d.line([(X, 0), (X, im.height)], fill=(255, 0, 0, 150 if major else 60), width=1)
        if major:
            d.text((X + 2, 2), str(gx), fill=(200, 0, 0, 255), font=f)
        gx += step
    gy = (y0 // step + 1) * step
    while gy < y1:
        Y = (gy - y0) * k
        major = gy % (step * 5) == 0
        d.line([(0, Y), (im.width, Y)], fill=(0, 0, 255, 150 if major else 60), width=1)
        if major:
            d.text((2, Y + 2), str(gy), fill=(0, 0, 200, 255), font=f)
        gy += step
    im.save(out, quality=92)
    print(out, im.size)


main()
