"""Камуфляж подсумков «Барханы» — свой песочный рисунок (владелец 2026-10-23: «не просто песочный, а песочный
камуфляж»; не копия существующих расцветок).

Светлый песочный фон, крупные мягкие пятна хаки-табака, поверх — бурые пятна с изломанным краем (вытянуты
по горизонтали, как наносы), мелкие тёмно-коричневые «камешки» и редкие светлые крапины. Контраст сдержанный —
пустынные расцветки читаются тоном, а не цветом. Бесшовный тайл: поля в частотной области (как «Чаща» рюкзака).

python -X utf8 tools/npc_kit/gen_pouch_camo.py → _asset_src/npc_kit/tex_gen/camo_barkhany_4k.png (sRGB; тайл 0,6 × 0,6 м)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_npc_camo import OUT, PX, upsample, warp_sample  # noqa: E402
from gen_pack_camo import field_aniso  # noqa: E402

SEED = 1979
TILE_M = 0.6
# sRGB: фон, хаки-табак, бурый, тёмно-коричневые «камешки», светлые крапины (в студии ткань светлеет на глаз)
PALETTE = [(138, 116, 82), (116, 96, 66), (90, 70, 48), (60, 47, 34), (152, 133, 100)]


def main() -> None:
    rng = np.random.default_rng(SEED)
    n = 1024
    dx = upsample(field_aniso(rng, n, 14, 14) * 18, PX) * (PX / n)
    dy = upsample(field_aniso(rng, n, 14, 14) * 18, PX) * (PX / n)
    idx = np.zeros((PX, PX), np.int8)
    # слои поверх фона: (σx, σy, порог доли) — хаки крупно, бурый вытянут, «камешки» мелко, крапины совсем мелко
    # мелким пятнам искривление вполовину — иначе «камешки» вытягиваются в червячков
    for k, (sx, sy, q, w) in enumerate(((40.0, 30.0, 0.56, 1.0), (28.0, 14.0, 0.82, 1.0), (7.0, 6.0, 0.955, 0.35),
                                        (4.0, 4.0, 0.975, 0.35)), start=1):
        f = warp_sample(upsample(field_aniso(rng, n, sx, sy), PX), dx * w, dy * w)
        idx[f > np.quantile(f[::8, ::8], q)] = k
    pal = np.array(PALETTE, np.float32)
    img = Image.fromarray(pal[idx].astype(np.uint8), "RGB")
    big = Image.new("RGB", (PX * 3, PX * 3))
    for i in range(3):
        for j in range(3):
            big.paste(img, (i * PX, j * PX))
    a = np.asarray(big.crop((PX - 64, PX - 64, 2 * PX + 64, 2 * PX + 64)).filter(ImageFilter.GaussianBlur(1.6)))[64:-64, 64:-64]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "camo_barkhany_4k.png"
    Image.fromarray(a.astype(np.uint8), "RGB").save(path, optimize=True)
    print("CAMO", path, "доли", [round(float((idx == k).mean()), 3) for k in range(len(PALETTE))], "тайл", TILE_M)


if __name__ == "__main__":
    main()
