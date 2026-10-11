"""Маски износа для текстурирования ракетницы Claude — собственные, рисуются этим скриптом (без чужих карт).

Каждая маска — квадрат 200 × 200 мм (2048 пикс, 10.24 пикс/мм), бесшовный: в UCUPaint кладётся на модель
объёмной проекцией в настоящем масштабе. Белое — где слой действует.

  scratches_deep.png  — редкие длинные царапины до металла (ширина 0.1–0.25 мм, с разрывами);
  scratches_fine.png  — много волосяных рисок от носки и чистки;
  chips.png           — мелкие сколы краски на плоскостях (0.3–1.8 мм, кучками);
  stains.png          — крупные мягкие пятна (неравномерность краски, потёки грязи).

python tools/flare_gun_claude_wear_masks.py → _asset_src/flare_gun_claude/textures/worn_v01/*.png + manifest.json
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_asset_src/flare_gun_claude/textures/worn_v01"
N = 2048
PX_MM = N / 200.0


def wrap_draw(img: np.ndarray, fn) -> None:
    """Рисует примитив девять раз со сдвигами — чтобы рисунок сходился на краях квадрата."""
    for dx in (-N, 0, N):
        for dy in (-N, 0, N):
            fn(dx, dy)


def scratches(seed: int, count: int, len_mm: tuple, width_px: tuple, level: tuple, gap: float, bias_deg: float | None, spread_deg: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    big = np.zeros((N * 3, N * 3), np.float32)

    def stroke(points: np.ndarray, width: int, value: float) -> None:
        for dx in (0, N, 2 * N):
            for dy in (0, N, 2 * N):
                cv2.polylines(big, [np.round(points + (dx, dy)).astype(np.int32).reshape(-1, 1, 2)], False, float(value), width, cv2.LINE_AA)

    for _ in range(count):
        length = rng.uniform(*len_mm) * PX_MM
        ang = math.radians(rng.uniform(0, 360) if bias_deg is None else bias_deg + rng.normal(0, spread_deg))
        bend = rng.normal(0, 0.25) / max(length, 1.0)                 # лёгкая дуга
        p = rng.uniform(0, N, 2)
        steps = max(4, int(length / 6))
        pts = [p.copy()]
        for _s in range(steps):
            ang += bend * 6
            p = p + 6 * np.array([math.cos(ang), math.sin(ang)]) + rng.normal(0, 0.18, 2)
            pts.append(p.copy())
        pts = np.array(pts, np.float32)
        value = rng.uniform(*level)
        width = int(rng.integers(width_px[0], width_px[1] + 1))
        i = 0
        while i < len(pts) - 1:                                      # разрывы: царапина идёт не сплошной линией
            run = int(rng.integers(3, 14))
            stroke(pts[i:i + run + 1], width, value * rng.uniform(0.6, 1.0))
            i += run + (int(rng.integers(1, 4)) if rng.random() < gap else 0)
    return big[N:2 * N, N:2 * N]


def chips(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    big = np.zeros((N * 3, N * 3), np.float32)

    def blob(c: np.ndarray, r: float, value: float) -> None:
        k = int(rng.integers(6, 11))
        angs = np.sort(rng.uniform(0, math.tau, k))
        rad = r * rng.uniform(0.45, 1.0, k)
        poly = np.stack([c[0] + rad * np.cos(angs), c[1] + rad * np.sin(angs)], axis=1)
        for dx in (0, N, 2 * N):
            for dy in (0, N, 2 * N):
                cv2.fillPoly(big, [np.round(poly + (dx, dy)).astype(np.int32).reshape(-1, 1, 2)], float(value), cv2.LINE_AA)

    for _ in range(170):                                             # очаг: скол и мелочь вокруг него
        c = rng.uniform(0, N, 2)
        r = rng.uniform(0.3, 1.8) * PX_MM / 2
        blob(c, r, rng.uniform(0.75, 1.0))
        for _k in range(int(rng.integers(0, 6))):
            blob(c + rng.normal(0, r * 2.2, 2), r * rng.uniform(0.15, 0.45), rng.uniform(0.5, 1.0))
    for _ in range(900):                                             # россыпь точек
        blob(rng.uniform(0, N, 2), rng.uniform(0.08, 0.3) * PX_MM / 2, rng.uniform(0.35, 0.9))
    return cv2.GaussianBlur(big, (0, 0), 0.6)[N:2 * N, N:2 * N]


def stains(seed: int) -> np.ndarray:
    """Мягкие пятна: сумма нескольких октав сглаженного шума, бесшовно (сглаживание с заворотом)."""
    rng = np.random.default_rng(seed)
    out = np.zeros((N, N), np.float32)
    for sigma, weight in ((140, 1.0), (60, 0.6), (22, 0.35), (8, 0.18)):
        layer = rng.random((N, N)).astype(np.float32)
        tiled = np.tile(layer, (3, 3))
        tiled = cv2.GaussianBlur(tiled, (0, 0), sigma)
        layer = tiled[N:2 * N, N:2 * N]
        layer = (layer - layer.min()) / (layer.max() - layer.min())
        out += weight * layer
    return (out - out.min()) / (out.max() - out.min())


def save(name: str, img: np.ndarray, note: str, manifest: dict) -> None:
    data = np.clip(img * 255.0 + 0.5, 0, 255).astype(np.uint8)
    cv2.imwrite(str(OUT / name), data)
    manifest[name] = {"size": [N, N], "physical_mm": 200, "colorspace": "Non-Color", "coverage": round(float((data > 96).mean()), 4),
                      "sha256": hashlib.sha256((OUT / name).read_bytes()).hexdigest(), "source": "tools/flare_gun_claude_wear_masks.py (собственный рисунок)",
                      "purpose": note}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}
    save("scratches_deep.png", scratches(11, 46, (6, 55), (1, 2), (0.7, 1.0), 0.45, None, 0), "редкие царапины до металла", manifest)
    fine = np.maximum(scratches(23, 520, (2, 22), (1, 1), (0.25, 0.75), 0.25, 20.0, 28.0), scratches(29, 260, (2, 16), (1, 1), (0.2, 0.6), 0.25, None, 0))
    save("scratches_fine.png", fine, "волосяные риски от носки и чистки", manifest)
    save("chips.png", chips(37), "мелкие сколы краски на плоскостях", manifest)
    save("stains.png", stains(41), "мягкие пятна: неравномерность краски и грязи", manifest)
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in manifest.items():
        print("MASK", k, "coverage", v["coverage"])
