"""Быстрый просмотр «побелка → штукатурка → кирпич» при разном повреждении (как сделает материал).

  python -X utf8 tools/dorm_modules/preview_plaster.py <папка карт> <кирпич albedo.jpg> <выход.jpg>
"""
import sys

import numpy as np
from PIL import Image

src, brick_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
N = 768


def load(name):
    a = np.asarray(Image.open(f"{src}/{name}.png")).astype(np.float32)
    a = a / (65535.0 if a.max() > 255 else 255.0)
    a = a[..., 0] if a.ndim == 3 else a
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BILINEAR)).astype(np.float32) / 255


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


m = {k: load(k) for k in ["wash_field", "wash_crack", "wash_tone", "loss_field", "crumble", "plaster_crack", "plaster_tone", "plaster_height"]}
brick = np.asarray(Image.open(brick_path).convert("RGB").resize((N, N))).astype(np.float32) / 255


def shade(h):
    gy, gx = np.gradient(h)
    return np.clip(1.0 + (gx - gy) * 8.0, 0.55, 1.45)


def compose(wash_wear, loss_wear):
    white = np.array([0.87, 0.88, 0.85]) * (0.88 + 0.16 * m["wash_tone"])[..., None]
    white *= (1 - 0.12 * m["wash_crack"])[..., None]
    grey = np.array([0.66, 0.64, 0.6]) * (0.85 + 0.3 * m["plaster_tone"])[..., None]
    flaked = (m["wash_field"] < wash_wear)[..., None]
    col = np.where(flaked, grey, white)
    col *= (1 - 0.6 * m["plaster_crack"])[..., None]
    keep = smooth(loss_wear, loss_wear + 0.05, m["loss_field"])          # 1 — штукатурка на месте
    edge = keep * (1 - keep) * 4
    col = col * keep[..., None] + brick * (1 - keep[..., None])
    col = np.where((edge > 0.3)[..., None], grey * 0.9, col)
    h = keep * (0.6 + 0.05 * m["plaster_height"]) + (1 - keep) * 0.1 - 0.03 * m["plaster_crack"]
    return np.clip(col * shade(h)[..., None], 0, 1)


tiles = [np.repeat(m[k][..., None], 3, 2) for k in ["wash_field", "loss_field", "plaster_crack"]]
tiles += [compose(0.15, 0.05), compose(0.35, 0.2), compose(0.6, 0.4)]
sheet = np.zeros((N * 2, N * 3, 3), np.float32)
for i, t in enumerate(tiles):
    sheet[(i // 3) * N:(i // 3 + 1) * N, (i % 3) * N:(i % 3 + 1) * N] = t
Image.fromarray((sheet * 255).astype(np.uint8)).save(out, quality=88)
print("ok", out)
