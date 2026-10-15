"""Наложение рендера (прозрачный фон) на референс в одном масштабе.

python -X utf8 tools/mosin_pu/compare_overlay.py <ref.png> <render.png> <out.png> \
    <ref_x0> <ref_y0> <ref_px_per_mm> <ren_x0> <ren_y0> <ren_px_per_mm> [alpha] [crop x0,y0,x1,y1]

(ref_x0, ref_y0) и (ren_x0, ren_y0) — пиксели одной и той же точки модели (начало координат).
Результат: слева референс, в середине наложение (модель красным, 50 %), справа рендер.
"""
import sys

from PIL import Image, ImageChops, ImageOps


def main():
    a = sys.argv[1:]
    ref = Image.open(a[0]).convert("RGBA")
    ren = Image.open(a[1]).convert("RGBA")
    out = a[2]
    rx0, ry0, rs = float(a[3]), float(a[4]), float(a[5])
    nx0, ny0, ns = float(a[6]), float(a[7]), float(a[8])
    alpha = float(a[9]) if len(a) > 9 else 0.5
    k = rs / ns
    ren = ren.resize((round(ren.width * k), round(ren.height * k)), Image.LANCZOS)
    ox, oy = round(rx0 - nx0 * k), round(ry0 - ny0 * k)
    layer = Image.new("RGBA", ref.size, (0, 0, 0, 0))
    layer.paste(ren, (ox, oy), ren)
    mask = layer.split()[3].point(lambda v: int(v * alpha))
    red = Image.new("RGBA", ref.size, (230, 30, 30, 255))
    over = ref.copy()
    over.paste(red, (0, 0), mask)
    # контур силуэта модели — синим, чтобы видеть край поверх фото
    edge = layer.split()[3].point(lambda v: 255 if v > 128 else 0)
    edge = ImageChops.difference(edge, edge.filter(__import__("PIL.ImageFilter", fromlist=["x"]).MinFilter(3)))
    blue = Image.new("RGBA", ref.size, (20, 60, 255, 255))
    over.paste(blue, (0, 0), edge)
    if len(a) > 10:
        x0, y0, x1, y1 = (int(v) for v in a[10].split(","))
        ref, over, layer = ref.crop((x0, y0, x1, y1)), over.crop((x0, y0, x1, y1)), layer.crop((x0, y0, x1, y1))
    plain = Image.new("RGBA", ref.size, (255, 255, 255, 255))
    plain.paste(layer, (0, 0), layer)
    sheet = Image.new("RGB", (ref.width, ref.height * 3), (255, 255, 255))
    sheet.paste(ref.convert("RGB"), (0, 0))
    sheet.paste(over.convert("RGB"), (0, ref.height))
    sheet.paste(plain.convert("RGB"), (0, ref.height * 2))
    sheet.save(out)
    print("COMPARE", out, sheet.size)


main()
