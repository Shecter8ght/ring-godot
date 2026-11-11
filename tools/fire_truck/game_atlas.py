"""Пожарная АЦ в игру: 16 наборов карт износа 4K → четыре атласа (три 2K и один 1K) для glTF.

Развёртка у игровых сеток та же, что у high-poly (game_lod.py), поэтому карты не перепекаются: каждый набор уменьшается
до своей клетки атласа (снаружи — 1K, салон экипажа и стёкла — 512) с полем 8 пикселей (края продлены — mip-уровни
не тянут соседа), а развёртка сдвигается в клетку (game_export.py берёт ту же раскладку LAYOUT). Нормали после
уменьшения нормируются заново. Атлас D: салон экипажа (непрозрачный) и стёкла — у стекла в альфе прозрачность:
чистое пропускает, грязное и матовое мутнеет (по шероховатости износа).

    python -X utf8 tools/fire_truck/game_atlas.py   → _asset_src/fire_truck/game/atlas/PV_fire_tanker_<A|B|C|D>_*.png
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MAPS = Path("E:/Models Blender/VEHICLES/Пожарная_АЦ/textures/worn_v01")
OUT = ROOT / "_asset_src" / "fire_truck" / "game" / "atlas"
NAME = "PV_fire_tanker"
MARGIN = 8
# атлас: (размер, {набор: (x, y, клетка)}) — x, y в пикселях от левого верхнего угла
ATLASES = {
    "A": (2048, {"body_L": (0, 0, 1024), "body_R": (1024, 0, 1024), "cab_panels": (0, 1024, 1024),
                 "shutters": (1024, 1024, 1024)}),
    "B": (2048, {"body_parts": (0, 0, 1024), "cab_parts": (1024, 0, 1024), "roof": (0, 1024, 1024),
                 "trim": (1024, 1024, 1024)}),
    "C": (2048, {"chassis": (0, 0, 1024), "wheels": (1024, 0, 1024), "pump": (0, 1024, 1024),
                 "cab_interior": (1024, 1024, 1024)}),
    "D": (1024, {"crew_interior": (0, 0, 512), "glass": (512, 0, 512)}),
}
GLASS = "glass"


def layout() -> dict:
    """Набор → (атлас, сдвиг u, сдвиг v, масштаб) для развёртки (v Blender — снизу вверх)."""
    out = {}
    for a, (size, cells) in ATLASES.items():
        for st, (x, y, c) in cells.items():
            k = (c - 2 * MARGIN) / size
            u0 = (x + MARGIN) / size
            v0 = 1.0 - (y + c - MARGIN) / size              # низ клетки в осях развёртки
            out[st] = (a, u0, v0, k)
    return out


def _read(path):
    import cv2
    import numpy as np
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    return im


def _write(path, im):
    import cv2
    ok, buf = cv2.imencode(".png", im)
    buf.tofile(str(path))


def main():
    import cv2
    import numpy as np
    OUT.mkdir(parents=True, exist_ok=True)
    for a, (size, cells) in ATLASES.items():
        canv = {k: np.zeros((size, size, 4 if k == "baseColor" else 3), np.uint8)
                for k in ("baseColor", "occlusionRoughnessMetallic", "normal")}
        canv["normal"][:] = (255, 128, 128)                   # BGR: плоская нормаль (0,5; 0,5; 1)
        canv["occlusionRoughnessMetallic"][:] = (0, 230, 255)  # BGR: AO 1, шероховатость 0,9, металл 0
        canv["baseColor"][..., 3] = 255
        for st, (x, y, c) in cells.items():
            inner = c - 2 * MARGIN
            for kind in canv:
                src = _read(MAPS / f"FT_{st}_{kind}.png")
                if src.ndim == 2:
                    src = cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)
                src = src[..., :3]
                small = cv2.resize(src, (inner, inner), interpolation=cv2.INTER_AREA)
                if kind == "normal":
                    v = small.astype(np.float32) / 127.5 - 1.0
                    v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
                    small = np.clip((v + 1.0) * 127.5, 0, 255).astype(np.uint8)
                tile = cv2.copyMakeBorder(small, MARGIN, MARGIN, MARGIN, MARGIN, cv2.BORDER_REPLICATE)
                if kind == "baseColor":
                    alpha = np.full((c, c), 255, np.uint8)
                    if st == GLASS:
                        orm = _read(MAPS / f"FT_{st}_occlusionRoughnessMetallic.png")[..., :3]
                        rough = cv2.resize(orm, (inner, inner), interpolation=cv2.INTER_AREA)[..., 1]
                        rough = cv2.copyMakeBorder(rough, MARGIN, MARGIN, MARGIN, MARGIN, cv2.BORDER_REPLICATE)
                        r = rough.astype(np.float32) / 255
                        # чистое стекло (0,05) пропускает почти всё, пыльное (0,6) — наполовину: сквозь грязное стекло
                        # кабины салон ещё видно (при 0,22 + 1,25 × r в игре стёкла вышли молочно-непрозрачными)
                        alpha = np.clip((0.15 + 0.7 * np.clip(r - 0.05, 0, 1)) * 255, 0, 255).astype(np.uint8)
                    tile = np.dstack([tile, alpha])
                canv[kind][y:y + c, x:x + c] = tile
        for kind, im in canv.items():
            _write(OUT / f"{NAME}_{a}_{kind}.png", im)
        print("ATLAS", a, size, list(cells), flush=True)


if __name__ == "__main__":
    main()
