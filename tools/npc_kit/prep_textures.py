"""Подготовка фототекстур одежды NPC: у части наборов Poly Haven в кадре строчка шва (fabric_leather_01,
_02) — при повторе она легла бы полосами по всей куртке. Вырезаем полосу без шва и делаем её снова
бесшовной по горизонтали: левый край смешивается с продолжением правого по шумовой маске (не
линейным наплывом — меньше «двоения»). Все карты набора режутся одинаково.

python tools/npc_kit/prep_textures.py → _asset_src/npc_kit/tex/<id>_clean/<id>_clean_<карта>_2k.<ext>
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "_asset_src" / "npc_kit" / "tex"
# Набор: доля ширины, с которой начинается чистая полоса, и где кончается (шов — вне её).
CROPS = {
    "fabric_leather_01": (0.245, 1.0),
    "fabric_leather_02": (0.405, 1.0),
}
BLEND = 0.16          # доля ширины на сведение краёв


def blend_mask(h: int, w: int, seed: int) -> np.ndarray:
    """Маска сведения 0 → 1 слева направо, с изрезанной границей (низкочастотный шум)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 1.0, w)[None, :]
    # Шум по высоте: сумма синусов разных частот — граница смешения ломаная, не прямая.
    yy = np.linspace(0.0, 1.0, h)[:, None]
    wob = np.zeros((h, 1))
    for k in (2, 5, 11, 23):
        wob += np.sin(2 * np.pi * (k * yy + rng.random())) / k
    wob = wob / np.abs(wob).max() * 0.22
    t = np.clip((x - 0.5 + wob) / 0.35 + 0.5, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def make_clean(asset: str, x0: float, x1: float) -> None:
    src = TEX / asset
    dst = TEX / f"{asset}_clean"
    dst.mkdir(exist_ok=True)
    for f in sorted(src.iterdir()):
        if f.suffix.lower() not in (".png", ".jpg"):
            continue
        im = Image.open(f)
        mode = im.mode
        a = np.asarray(im).astype(np.float64)
        h, w = a.shape[:2]
        c = a[:, int(round(x0 * w)):int(round(x1 * w))]
        wc = c.shape[1]
        b = int(round(BLEND * w))
        out_w = wc - b
        out = c[:, :out_w].copy()
        # Левая полоса [0, b): смешать с тем, что идёт сразу за правым краем (c[:, out_w:]):
        # тогда out[-1] → out[0] переходит непрерывно (out[0] ≈ c[out_w]).
        m = blend_mask(h, b, 7)
        if a.ndim == 3:
            m = m[:, :, None]
        out[:, :b] = c[:, out_w:out_w + b] * (1 - m) + c[:, :b] * m
        if asset in f.name and "nor_gl" in f.name:
            # Нормали после смешения — снова единичной длины.
            n = out[..., :3] / 255.0 * 2 - 1
            n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
            out[..., :3] = (n + 1) / 2 * 255.0
        # Квадрат той же стороны — растягиваем по ширине (повтор по реальному размеру поправим в материале).
        res = Image.fromarray(np.clip(out, 0, 65535 if a.max() > 255 else 255).astype(a.dtype if a.max() > 255 else np.uint8), mode)
        res = res.resize((h, h), Image.LANCZOS)
        name = f.name.replace(asset, f"{asset}_clean")
        res.save(dst / name, quality=95) if f.suffix.lower() == ".jpg" else res.save(dst / name)
        print(asset, f.name, "→", name, res.size)
    info = json.loads((src / "info.json").read_text(encoding="utf-8"))
    dims = info.get("dimensions", [400, 400])
    real_w = dims[0] * (x1 - x0 - BLEND)
    (dst / "info.json").write_text(json.dumps({"source": asset, "crop": [x0, x1], "blend": BLEND,
                                               "dimensions_mm": [real_w, dims[1]], "authors": info.get("authors")},
                                              ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def main() -> None:
    for asset, (x0, x1) in CROPS.items():
        make_clean(asset, x0, x1)


if __name__ == "__main__":
    main()
