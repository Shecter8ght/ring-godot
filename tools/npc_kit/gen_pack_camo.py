"""Камуфляж рейдового рюкзака «Чаща» — свой рисунок в духе лесного «вудленда» (решение владельца 2026-10-22: рейдовый
«как тактические рюкзаки — ярко-зелёные, насыщенные, камуфляжные»; не копия существующих расцветок).

Сочный светло-зелёный фон, крупные тёмно-зелёные и коричневые пятна (вытянуты по горизонтали, края с изломом),
чёрные «ветки» — узкие вытянутые пятна. Бесшовный тайл: поля в частотной области (как «Лесополоса» брюк мародёра).

python -X utf8 tools/npc_kit/gen_pack_camo.py → _asset_src/npc_kit/tex_gen/camo_chascha_4k.png (sRGB; тайл 0,8 × 0,8 м)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_npc_camo import OUT, PX, upsample, warp_sample  # noqa: E402

SEED = 1965
TILE_M = 0.8
# sRGB: фон, тёмно-зелёный, коричневый, чёрный — насыщенные (в студии ткань светлеет и бледнеет на глаз)
PALETTE = [(60, 88, 26), (26, 48, 18), (66, 44, 24), (18, 20, 14)]


def field_aniso(rng: np.random.Generator, n: int, sx: float, sy: float) -> np.ndarray:
    """Бесшовное поле: белый шум через гаусс с разными σ по осям (пятна вытянуты по горизонтали при sx > sy)."""
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    g = np.exp(-2 * np.pi ** 2 * ((sx * f[None, :]) ** 2 + (sy * f[:, None]) ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * g))
    return (out - out.mean()) / (out.std() + 1e-9)


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = 1024
    dx = upsample(field_aniso(rng, n, 16, 16) * 16, PX) * (PX / n)
    dy = upsample(field_aniso(rng, n, 16, 16) * 16, PX) * (PX / n)
    idx = np.zeros((PX, PX), np.int8)
    # слои поверх фона: тёмно-зелёный, коричневый, чёрные «ветки»
    for k, (sx, sy, q) in enumerate(((34.0, 22.0, 0.58), (26.0, 15.0, 0.72), (20.0, 10.0, 0.88)), start=1):
        f = warp_sample(upsample(field_aniso(rng, n, sx, sy), PX), dx, dy)
        idx[f > np.quantile(f[::8, ::8], q)] = k
    pal = np.array(PALETTE, np.float32)
    img = Image.fromarray(pal[idx].astype(np.uint8), "RGB")
    big = Image.new("RGB", (PX * 3, PX * 3))
    for i in range(3):
        for j in range(3):
            big.paste(img, (i * PX, j * PX))
    a = np.asarray(big.crop((PX - 64, PX - 64, 2 * PX + 64, 2 * PX + 64)).filter(ImageFilter.GaussianBlur(1.6)))[64:-64, 64:-64]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "camo_chascha_4k.png"
    Image.fromarray(a.astype(np.uint8), "RGB").save(path, optimize=True)
    print("CAMO", path, "доли", [round(float((idx == k).mean()), 2) for k in range(4)], "тайл", TILE_M)


if __name__ == "__main__":
    main()
