"""Закрепки строп MOLLE для UCUPaint: высота и тень на один шаг 38,1 × 25 мм (по фото владельца 2026-10-22:
настоящая стропа MOLLE — плоская, тканая, прошита поперёк закрепками, которые делят её на прямоугольники).

Закрепка — плотный зигзаг нити поперёк стропы шириной ~2,5 мм с отступом ~1,5 мм от краёв; нить вдавливает стропу,
у краёв закрепки ткань чуть собрана. Тайл повторяется по длине стропы (u — вдоль, шаг MOLLE), по v — ширина стропы.

python -X utf8 tools/npc_kit/gen_molle_tack.py → _asset_src/npc_kit/tex_gen/molle_tack_height.png (16 бит, Non-Color),
molle_tack_shade.png (sRGB, множитель цвета: темнее в закрепке)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_npc_camo import OUT  # noqa: E402

PITCH_MM, WIDTH_MM = 38.1, 25.0
PX_PER_MM = 24
TACK_W, MARGIN = 2.6, 1.4          # ширина закрепки и отступ от края стропы, мм
STITCH = 0.45                      # шаг стежков зигзага, мм


def main() -> None:
    w, h = int(PITCH_MM * PX_PER_MM), int(WIDTH_MM * PX_PER_MM)
    u = (np.arange(w) + 0.5) / PX_PER_MM                    # мм вдоль стропы
    v = (np.arange(h) + 0.5) / PX_PER_MM                    # мм поперёк
    U, V = np.meshgrid(u, v)
    du = np.minimum(U, PITCH_MM - U)                        # расстояние до закрепки (она на стыке тайлов)
    inside_v = (V > MARGIN) & (V < WIDTH_MM - MARGIN)
    edge_v = np.clip(np.minimum(V - MARGIN, WIDTH_MM - MARGIN - V) / 0.4, 0.0, 1.0)
    band = np.clip((TACK_W / 2 - du) / 0.25, 0.0, 1.0) * edge_v * inside_v
    # стропа вдавлена под закрепкой, рядом чуть собрана
    height = 0.5 - 0.28 * band + 0.05 * np.exp(-((du - TACK_W / 2 - 0.6) / 0.5) ** 2) * inside_v
    # нить зигзага: стежки поперёк закрепки, каждый — валик, через один чуть наклонён
    k = np.floor(V / STITCH)
    t = (V / STITCH) - k
    thread = np.exp(-((t - 0.5) / 0.22) ** 2) * (1.0 - 0.25 * (k % 2))
    height += 0.22 * thread * band
    shade = 1.0 - 0.45 * band * (0.7 + 0.3 * (1.0 - thread))
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(height * 65535, 0, 65535).astype(np.uint16)).save(OUT / "molle_tack_height.png")
    s8 = (np.clip(shade, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(np.stack([s8] * 3, -1), "RGB").save(OUT / "molle_tack_shade.png")
    print("TACK", w, "×", h, OUT / "molle_tack_height.png")


if __name__ == "__main__":
    main()
