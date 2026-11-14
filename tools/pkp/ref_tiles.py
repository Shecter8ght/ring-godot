# ПКП: увеличенные куски снимка-образца с сеткой — по ним читаются координаты деталей.
#   python -X utf8 tools/pkp/ref_tiles.py <снимок> <папка> <имя> x0 y0 x1 y1 [--zoom 3] [--step 20] [--mm] [--y 22.5]
# Без --mm сетка в пикселях снимка; с --mm — в миллиметрах модели (привязка — refmap.py: снимки 13 и 14
# владельца, виды сбоку с поправкой на перспективу; --y — глубина плоскости сетки: на сколько она ближе к камере,
# чем средняя плоскость оружия: борт коробки — 22.5).
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    a = sys.argv[1:]
    src, out_dir, name = a[0], a[1], a[2]
    x0, y0, x1, y1 = [int(v) for v in a[3:7]]
    zoom = 3; step = 20; mm = False; depth = 0.0
    i = 7
    while i < len(a):
        if a[i] == "--zoom": zoom = float(a[i + 1]); i += 2
        elif a[i] == "--step": step = float(a[i + 1]); i += 2
        elif a[i] == "--mm": mm = True; i += 1
        elif a[i] == "--y": depth = float(a[i + 1]); i += 2
        else: i += 1
    im = Image.open(src).convert("RGB")
    crop = im.crop((x0, y0, x1, y1))
    # серые рендеры на чёрном тёмные — растягиваем уровни, чтобы читались кромки
    arr = np.asarray(crop).astype(np.float32) / 255.0
    hi = max(0.2, float(np.percentile(arr, 99.7)))
    arr = np.clip(arr / hi, 0, 1) ** 0.75
    crop = Image.fromarray((arr * 255).astype(np.uint8))
    W, H = int((x1 - x0) * zoom), int((y1 - y0) * zoom)
    big = crop.resize((W, H), Image.LANCZOS)
    dr = ImageDraw.Draw(big, "RGBA")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    if mm:
        import refmap
        img = os.path.splitext(os.path.basename(src))[0]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        corners = [refmap.to_mm(img, px, py, depth) for px in (x0, x1) for py in (y0, y1)]
        u_a, u_b = min(c[0] for c in corners), max(c[0] for c in corners)
        v_a, v_b = min(c[1] for c in corners), max(c[1] for c in corners)
        zc = refmap.to_mm(img, cx, cy, depth)[1]; xc = refmap.to_mm(img, cx, cy, depth)[0]
        k = int(np.ceil(u_a / step))
        while k * step <= u_b:
            pa = refmap.to_px(img, k * step, v_a, depth); pb = refmap.to_px(img, k * step, v_b, depth)
            major = (k * step) % (step * 5) == 0
            dr.line([((pa[0] - x0) * zoom, (pa[1] - y0) * zoom), ((pb[0] - x0) * zoom, (pb[1] - y0) * zoom)],
                    fill=(255, 210, 60, 160 if major else 75), width=1)
            pt = refmap.to_px(img, k * step, zc, depth)
            dr.text(((pt[0] - x0) * zoom + 2, 2), f"{k * step:g}", fill=(255, 220, 90, 255), font=font)
            k += 1
        k = int(np.ceil(v_a / step))
        while k * step <= v_b:
            pa = refmap.to_px(img, u_a, k * step, depth); pb = refmap.to_px(img, u_b, k * step, depth)
            major = (k * step) % (step * 5) == 0
            dr.line([((pa[0] - x0) * zoom, (pa[1] - y0) * zoom), ((pb[0] - x0) * zoom, (pb[1] - y0) * zoom)],
                    fill=(90, 220, 255, 160 if major else 75), width=1)
            pt = refmap.to_px(img, xc, k * step, depth)
            dr.text((2, (pt[1] - y0) * zoom + 1), f"{k * step:g}", fill=(120, 230, 255, 255), font=font)
            k += 1
    else:
        gx = int(np.ceil(x0 / step) * step)
        while gx <= x1:
            px = (gx - x0) * zoom
            major = gx % (step * 5) == 0
            dr.line([(px, 0), (px, H)], fill=(255, 210, 60, 150 if major else 70), width=1)
            dr.text((px + 2, 2), str(gx), fill=(255, 220, 90, 255), font=font)
            gx += int(step)
        gy = int(np.ceil(y0 / step) * step)
        while gy <= y1:
            py = (gy - y0) * zoom
            major = gy % (step * 5) == 0
            dr.line([(0, py), (W, py)], fill=(90, 220, 255, 150 if major else 70), width=1)
            dr.text((2, py + 1), str(gy), fill=(120, 230, 255, 255), font=font)
            gy += int(step)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".png")
    big.save(path)
    print("TILE", path, big.size)


main()
