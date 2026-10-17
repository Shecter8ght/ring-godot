# -*- coding: utf-8 -*-
"""Земля под готовыми кусками зоны 1 до переезда (2026-10-17) — вырезки прежней карты высот.

Зона 1 сжимается в квадрат 600 × 600 м (docs/design/zone01_outskirts.md §11); двор хрущёвок, рынок и дома
у оврага переезжают целиком. Их земля (подвал двора, площадка рынка, склоны оврага у домов и моста)
должна остаться той же до миллиметра. Скрипт один раз вырезает прямоугольники из прежней карты высот
(сетка −480 … 530 × −440 … 339, шаг 1 м, как её писал прежний tools/build_zone01.py), tools/build_zone01.py
переносит их на новые места.

    python -X utf8 tools/zone01_freeze_ready_ground.py   →  data/terrain/zone01_ready/<кусок>.r32, _splat.png, _grass.png + ready.json

Повторно запускать только на прежней карте высот: на новой вырезки получатся неверными (скрипт это проверяет).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/terrain/zone01_heights.r32"
OUT = ROOT / "data/terrain/zone01_ready"
OLD_X0, OLD_Z0, OLD_NX, OLD_NZ = -480, -440, 1011, 780

# прямоугольники в прежних координатах (x0, z0, x1, z1): кусок с запасом под плавный переход
CROPS = {
    "yard05": (-288, -178, -124, -34),
    "market06": (-240, -58, -96, 102),
    "houses12": (-384, -34, -246, 92),
}


def main() -> None:
    raw = np.fromfile(SRC, dtype="<f4")
    if raw.size != OLD_NX * OLD_NZ:
        raise SystemExit(f"карта высот уже не прежняя ({raw.size} точек) — вырезки брать из git: 857ff05c")
    h = raw.reshape(OLD_NZ, OLD_NX)
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"source": "data/terrain/zone01_heights.r32 @ 857ff05c (сетка −480, −440, 1011 × 780, шаг 1 м)",
            "step": 1.0, "crops": {}}
    for key, (x0, z0, x1, z1) in CROPS.items():
        i0, j0 = x0 - OLD_X0, z0 - OLD_Z0
        crop = h[j0:j0 + (z1 - z0) + 1, i0:i0 + (x1 - x0) + 1].astype("<f4")
        crop.tofile(OUT / f"{key}.r32")
        # маска поверхностей и густота травы — та же сетка: тропинки двора, площадка, грязь у домов
        box = (i0, j0, i0 + (x1 - x0) + 1, j0 + (z1 - z0) + 1)
        for name in ("splat", "grass"):
            Image.open(ROOT / f"assets/terrain/zone01_{name}.png").crop(box).save(OUT / f"{key}_{name}.png")
        meta["crops"][key] = {"origin": [x0, z0], "size": [crop.shape[1], crop.shape[0]],
                              "min": round(float(crop.min()), 3), "max": round(float(crop.max()), 3)}
        print(key, crop.shape, f"{crop.min():.2f}..{crop.max():.2f}")
    (OUT / "ready.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
