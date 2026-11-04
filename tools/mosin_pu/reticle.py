"""Сетка прицела ПУ — своя текстура окуляра (CameraRig: meta reticle_tex модели в руках).

python -X utf8 tools/mosin_pu/reticle.py, затем `tools/godot.cmd --headless --import` и python -X utf8
tools/mosin_pu/game_imports.py (без сжатия, с mip-уровнями), ещё раз --import.
→ assets/models/weapons/mosin_pu/mosin_pu_reticle.png

Формат — как у сеток ВСС-М (tools/vss_m_v8/reticles.py): квадрат — окно окуляра, край поля — круг радиусом в половину
стороны, центр — точка прицеливания; R — нити (чёрные), G — подсветка (у ПУ её нет — пусто). Рисунок — тот же, что
у принятого high-poly прицела (build_scope.reticle, мм в фокальной плоскости, поле — R_IN): заострённый пенёк снизу
до центра и горизонтальные нити по бокам с разрывом у центра. Рисуется вчетверо крупнее и уменьшается — сглаженные края.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'assets/models/weapons/mosin_pu/mosin_pu_reticle.png'
SIZE, SS = 2048, 4
N = SIZE * SS
R_IN = 10.6                                  # радиус поля в фокальной плоскости, мм (build_scope.py)
POST = [(-0.9, -R_IN + 0.1), (0.9, -R_IN + 0.1), (0.35, -1.2), (0.0, 0.0), (-0.35, -1.2)]
LINE_GAP, LINE_HALF = 2.2, 0.06              # нити: разрыв у центра, полутолщина, мм


def px(x: float, y: float) -> tuple[int, int]:
    """мм фокальной плоскости (y вверх) → пиксели рисунка (y вниз)."""
    return int(round(N / 2 + x / R_IN * N / 2)), int(round(N / 2 - y / R_IN * N / 2))


def main() -> None:
    ink = np.zeros((N, N), np.uint8)
    cv2.fillPoly(ink, [np.array([px(x, y) for x, y in POST], np.int32)], 255, cv2.LINE_AA)
    for sx in (-1, 1):
        x0, x1 = sx * LINE_GAP, sx * (R_IN - 0.1)
        cv2.fillPoly(ink, [np.array([px(x0, -LINE_HALF), px(x1, -LINE_HALF), px(x1, LINE_HALF), px(x0, LINE_HALF)],
                                    np.int32)], 255, cv2.LINE_AA)
    small = cv2.resize(ink, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    bgr = np.dstack([np.zeros_like(small), np.zeros_like(small), small])     # B 0, G подсветки нет, R нити
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(OUT), bgr)
    print('RETICLE', OUT.relative_to(ROOT), 'нити', round(float((small > 0).mean()) * 100, 2), '%')


if __name__ == '__main__':
    main()
