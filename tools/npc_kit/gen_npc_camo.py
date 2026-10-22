"""Камуфляж брюк мародёра «Лесополоса» (свой рисунок, был процедурным в materials.mat_camo) — карта 4K для UCUPaint.

Хаки-основа, оливковые и бурые пятна, тёмные «ветки», светлые крапины; края пятен с изломом (поля слегка
искривлены шумом), пятна вытянуты по долевой нити (вдоль штанины). Бесшовный тайл: поля строятся в частотной
области, искривление — тоже периодическим полем.

python -X utf8 tools/npc_kit/gen_npc_camo.py → _asset_src/npc_kit/tex_gen/camo_lesopolosa_4k.png (sRGB; тайл 1,0 × 1,6 м)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "npc_kit" / "tex_gen"
PX = 4096
SEED = 1891
TILE_M = (1.0, 1.6)            # ширина × длина ткани на тайл (пятна вытянуты вдоль)
# Цвета прежнего рисунка (линейные из materials.mat_camo) → sRGB: основа, олива, бурый, тёмный, светлые крапины.
LINEAR = [(0.078, 0.074, 0.043), (0.040, 0.050, 0.022), (0.050, 0.034, 0.019), (0.014, 0.014, 0.010), (0.13, 0.12, 0.075)]


def to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def field(rng: np.random.Generator, n: int, sigma: float) -> np.ndarray:
    """Плавное бесшовное поле n×n: белый шум через гаусс (σ в пикселях) в частотной области."""
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    g = np.exp(-2 * np.pi ** 2 * sigma ** 2 * (f[None, :] ** 2 + f[:, None] ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * g))
    return (out - out.mean()) / (out.std() + 1e-9)


def warp_sample(f: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
    n = f.shape[0]
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xx + dx) % n
    y = (yy + dy) % n
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    tx, ty = x - x0, y - y0
    x1, y1 = (x0 + 1) % n, (y0 + 1) % n
    return (f[y0, x0] * (1 - tx) * (1 - ty) + f[y0, x1] * tx * (1 - ty) + f[y1, x0] * (1 - tx) * ty + f[y1, x1] * tx * ty)


def upsample(f: np.ndarray, n_hi: int) -> np.ndarray:
    """Периодическое поле в большее разрешение без ступенек: дополнение спектра нулями (поле гладкое)."""
    n = f.shape[0]
    F = np.fft.fftshift(np.fft.fft2(f))
    pad = (n_hi - n) // 2
    G = np.zeros((n_hi, n_hi), np.complex64)
    G[pad:pad + n, pad:pad + n] = F
    return np.real(np.fft.ifft2(np.fft.ifftshift(G))).astype(np.float32) * (n_hi / n) ** 2


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = 1024                                   # поля считаем на 1024² (плавные), порог — уже в 4K: края гладкие
    dx = upsample(field(rng, n, 18) * 14, PX) * (PX / n)
    dy = upsample(field(rng, n, 18) * 14, PX) * (PX / n)
    pal = np.array([[to_srgb(c) * 255 for c in col] for col in LINEAR], np.float32)
    idx = np.zeros((PX, PX), np.int8)
    # Размеры пятен — по прежним масштабам шума «Лесополосы»; пороги — доли цветов 37 / 24 / 21 / 11 / 7 %.
    for k, (sigma, q) in enumerate(((26.0, 0.62), (17.0, 0.74), (11.0, 0.88), (5.0, 0.93)), start=1):
        f = warp_sample(upsample(field(rng, n, sigma), PX), dx, dy)
        idx[f > np.quantile(f[::8, ::8], q)] = k
    a = pal[idx]
    # Краска чуть расплывается по саржевой ткани: размытие края на ~0,5 мм (тайл 3×3, середина — без шва).
    img = Image.fromarray(a.astype(np.uint8), "RGB")
    big = Image.new("RGB", (PX * 3, PX * 3))
    for i in range(3):
        for j in range(3):
            big.paste(img, (i * PX, j * PX))
    from PIL import ImageFilter
    a = np.asarray(big.crop((PX - 64, PX - 64, 2 * PX + 64, 2 * PX + 64)).filter(ImageFilter.GaussianBlur(1.6)))[64:-64, 64:-64]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "camo_lesopolosa_4k.png"
    Image.fromarray(a.astype(np.uint8), "RGB").save(path, optimize=True)
    print("CAMO", path, "доли", [round(float((idx == k).mean()), 2) for k in range(5)], "тайл", TILE_M)


if __name__ == "__main__":
    main()
