"""Быстрый просмотр карт краски: серые карты и сборка «краска по штукатурке» при разном износе (как сделает материал).

  python -X utf8 tools/dorm_modules/preview_paint.py <папка карт> <выход.jpg>
"""
import sys

import numpy as np
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
N = 768


def load(name):
    im = Image.open(f"{src}/{name}.png")
    a = np.asarray(im).astype(np.float32)
    a = a / (65535.0 if a.max() > 255 else 255.0)
    if a.ndim == 3:
        a = a[..., 0]
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)).astype(np.float32) / 255


m = {k: load(k) for k in ["crack_mask", "peel_field", "paint_tone", "paint_height", "plaster_tone", "plaster_height"]}
green = np.array([0x59, 0x65, 0x4c]) / 255
plaster = np.array([0xc9, 0xc0, 0xae]) / 255
under = np.array([0xb5, 0xb7, 0x9c]) / 255


def shade(h):
    gy, gx = np.gradient(h)
    return np.clip(1.0 + (gx - gy) * 6.0, 0.6, 1.4)


def compose(wear):
    f = m["peel_field"]
    peeled = f < wear
    rim = (f >= wear) & (f < wear + 0.035)
    paint = green[None, None] * (0.8 + 0.4 * m["paint_tone"])[..., None] * (1 - 0.5 * m["crack_mask"])[..., None]
    pl = plaster[None, None] * (0.8 + 0.35 * m["plaster_tone"])[..., None]
    col = np.where(peeled[..., None], pl, paint)
    col = np.where(rim[..., None], under[None, None] * 0.95, col)
    h = np.where(peeled, m["plaster_height"] * 0.3, 0.5 + 0.1 * m["paint_height"]) + rim * 0.15
    return np.clip(col * shade(h)[..., None], 0, 1)


tiles = [np.repeat(m[k][..., None], 3, 2) for k in ["crack_mask", "peel_field", "paint_height"]]
tiles += [compose(w) for w in (0.2, 0.45, 0.7)]
sheet = np.zeros((N * 2, N * 3, 3), np.float32)
for i, t in enumerate(tiles):
    sheet[(i // 3) * N:(i // 3 + 1) * N, (i % 3) * N:(i % 3 + 1) * N] = t
Image.fromarray((sheet * 255).astype(np.uint8)).save(out, quality=88)
print("ok", out)
