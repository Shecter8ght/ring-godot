"""RGBA-атласы 2K для игровых растений: зелёный цвет, вырез и заполнение прозрачной кромки.

    python -X utf8 tools/prospekt_grass/prepare_model_textures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "prospekt_grass"
OUT = SRC / "game_textures"
RES = 2048
ASSETS = ("grass_bermuda_01", "grass_medium_01", "weed_plant_02")


def box(values: np.ndarray, radius: int) -> np.ndarray:
    padded = np.pad(values, ((radius + 1, radius), (radius + 1, radius)))
    sums = np.cumsum(np.cumsum(padded, 0, dtype=np.float32), 1, dtype=np.float32)
    return sums[2 * radius + 1:, 2 * radius + 1:] - sums[:-2 * radius - 1, 2 * radius + 1:] - sums[2 * radius + 1:, :-2 * radius - 1] + sums[:-2 * radius - 1, :-2 * radius - 1]


def bleed(rgb: np.ndarray, inside: np.ndarray) -> np.ndarray:
    result = rgb.copy()
    done = inside.copy()
    mask = inside.astype(np.float32)
    for radius in (2, 4, 8, 16, 32, 64):
        weights = box(mask, radius)
        fill = (~done) & (weights > 0.0)
        for channel in range(3):
            sums = box(rgb[..., channel] * mask, radius)
            plane = result[..., channel]
            plane[fill] = sums[fill] / weights[fill]
        done |= fill
    mean = np.mean(rgb[inside], axis=0) if np.any(inside) else np.array([0.15, 0.2, 0.08])
    result[~done] = mean
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    for asset in ASSETS:
        folder = SRC / asset / "textures"
        color = Image.open(folder / f"{asset}_diff_8k.jpg").convert("RGB").resize((RES, RES), Image.Resampling.LANCZOS)
        alpha_image = Image.open(folder / f"{asset}_alpha_8k.png").convert("L").resize((RES, RES), Image.Resampling.LANCZOS)
        rgb = np.asarray(color, dtype=np.float32) / 255.0
        alpha = np.asarray(alpha_image, dtype=np.float32) / 255.0
        inside = alpha > 0.02
        coverage_before = float(np.mean(alpha > 0.4))
        alpha = np.clip(alpha * 1.08, 0.0, 1.0)
        filled = bleed(rgb, inside)
        rgba = np.dstack((np.clip(filled, 0.0, 1.0), alpha))
        dest = OUT / f"{asset}_albedo.png"
        Image.fromarray((rgba * 255.0 + 0.5).astype(np.uint8), "RGBA").save(dest, optimize=True)
        report[asset] = {"file": dest.name, "resolution": RES, "coverage_before": coverage_before,
            "coverage_after": float(np.mean(alpha > 0.4)), "transparent_rgb_min": filled[~inside].min(axis=0).tolist(),
            "transparent_rgb_max": filled[~inside].max(axis=0).tolist()}
        print(f"{asset}: альфа {coverage_before:.3f} → {report[asset]['coverage_after']:.3f}", flush=True)
    (OUT / "textures.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
