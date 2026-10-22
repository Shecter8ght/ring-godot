"""Свой пиксельный лесной камуфляж для брони «крутая» (решение владельца 2026-10-22: «пиксельная, лесной»).

Рисунок оригинальный (не копия ЕМР, ММ14, MARPAT и т. п.): четыре цвета — светлая хаки-олива, зелёный,
коричневый, почти чёрный зелёный; пятна — пороги плавных бесшовных полей на сетке клеток 12 мм, края пятен
«рассыпаны» клетками (цифровой рисунок), печать чуть расплывается по ткани. Бесшовный: поля строятся в
частотной области, тайл повторяется без шва.

python -X utf8 tools/npc_kit/gen_armor_camo.py [--preview]
→ _asset_src/npc_kit/armor/tex/camo_pixel_forest_4k.png (sRGB; тайл 0,768 м — 64 × 64 клетки)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "npc_kit" / "armor" / "tex"
CELLS = 64                  # клеток на тайл
CELL_M = 0.012              # клетка 12 мм → тайл 0,768 м
PX = 4096
SEED = 20261022
# цвета печати (sRGB): от фона к самому тёмному; доля площади — примерно 30 / 36 / 19 / 15 % (лесной: зелени больше)
COLORS = [(116, 117, 80), (74, 88, 50), (86, 69, 47), (36, 41, 30)]


def field(rng: np.random.Generator, n: int, scale_cells: float, aniso: float = 1.0) -> np.ndarray:
    """Плавное бесшовное поле на сетке n×n: белый шум, отфильтрованный гауссом в частотной области."""
    white = rng.standard_normal((n, n))
    fx = np.fft.fftfreq(n)[None, :]
    fy = np.fft.fftfreq(n)[:, None]
    sx, sy = scale_cells * aniso / 2.0, scale_cells / aniso / 2.0     # гаусс с σ в клетках (размер пятна ≈ 2σ)
    g = np.exp(-2.0 * np.pi ** 2 * ((sx * fx) ** 2 + (sy * fy) ** 2))
    f = np.real(np.fft.ifft2(np.fft.fft2(white) * g))
    return (f - f.mean()) / (f.std() + 1e-9)


def wrapped(img: Image.Image, op) -> np.ndarray:
    """Применить фильтр к тайлу без шва: собрать 3×3, обработать, вернуть середину."""
    w, h = img.size
    big = Image.new(img.mode, (w * 3, h * 3))
    for i in range(3):
        for j in range(3):
            big.paste(img, (i * w, j * h))
    return np.asarray(op(big)).astype(np.float32)[h:2 * h, w:2 * w]


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = CELLS
    # Три слоя пятен разного размера (крупные кляксы с вытянутостью, как у лесного рисунка); каждый
    # следующий цвет кладётся поверх предыдущего.
    layers = [
        (field(rng, n, 9.0, 1.4) + 0.35 * field(rng, n, 3.0), 0.55),   # зелёный поверх фона
        (field(rng, n, 7.0, 0.8) + 0.40 * field(rng, n, 2.5), 0.79),   # коричневый
        (field(rng, n, 5.0, 1.2) + 0.45 * field(rng, n, 2.0), 0.86),   # тёмный
    ]
    idx = np.zeros((n, n), dtype=np.int32)
    for k, (f, q) in enumerate(layers, start=1):
        thr = np.quantile(f, q)
        # рассыпать край пятна: клетки у порога случайно переходят в соседний цвет
        jitter = rng.uniform(-0.28, 0.28, (n, n))
        idx[f + jitter > thr] = k
    # одиночные клетки внутри пятен — «цифровой» шум, как у печати пиксельных рисунков
    lone = rng.random((n, n)) < 0.035
    idx[lone] = rng.integers(0, 4, lone.sum())
    pal = np.array(COLORS, dtype=np.float32)
    small = pal[idx]                                            # n×n×3
    img = Image.fromarray(small.astype(np.uint8), "RGB").resize((PX, PX), Image.NEAREST)
    # Краска чуть расплывается по плетению (лёгкое размытие края клетки), прокрас неравномерный. Размытие
    # и масштаб пятнистости — по тайлу 3×3 с вырезкой середины, иначе на стыке тайлов остаётся линия.
    a = wrapped(img, lambda im: im.filter(ImageFilter.GaussianBlur(radius=PX / n * 0.06)))
    mott = field(rng, 256, 6.0)
    mott_img = Image.fromarray(((mott - mott.min()) / (mott.max() - mott.min()) * 255).astype(np.uint8))
    m3 = Image.new("L", (768, 768))
    for i in range(3):
        for j in range(3):
            m3.paste(mott_img, (i * 256, j * 256))
    mott = np.asarray(m3.resize((PX * 3, PX * 3), Image.BICUBIC)).astype(np.float32)[PX:2 * PX, PX:2 * PX] / 255.0
    a *= (0.94 + 0.10 * mott)[..., None]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "camo_pixel_forest_4k.png"
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB").save(path, optimize=True)
    share = [float((idx == k).mean()) for k in range(4)]
    print("CAMO", path, "доли цветов", [round(s, 2) for s in share], "тайл", CELLS * CELL_M, "м")
    if "--preview" in sys.argv:
        tiled = Image.new("RGB", (PX, PX))
        q = Image.open(path).resize((PX // 2, PX // 2))
        for i in range(2):
            for j in range(2):
                tiled.paste(q, (i * PX // 2, j * PX // 2))
        tiled.save(OUT / "camo_pixel_forest_preview_2x2.jpg", quality=88)


if __name__ == "__main__":
    main()
