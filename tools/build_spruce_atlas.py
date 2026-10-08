"""Склейка атласа лап ели из рендеров tools/build_spruce.py -- atlas.

python tools/build_spruce_atlas.py
→ assets/zone01/textures/spruce_atlas_albedo.png (RGB — цвет с затенением слоёв, A — маска),
  spruce_atlas_normal.png (касательное пространство, OpenGL), spruce_atlas.json (ячейки: UV, размеры, якорь).
Цвет: скан — свежие светлые побеги; старая хвоя ели темнее и синее — тон сдвигается к тёмно-зелёному.
Прозрачные пиксели заливаются цветом ближайшей хвои: без тёмной каймы на мипах.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "_asset_src/spruce/render"
OUT = ROOT / "assets/zone01/textures"
SIZE, CW, CH = 4096, 2048, 1365

IMPORT_COLOR = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/zone01/textures/{name}"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/normal_map={nm}
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
process/fix_alpha_border=true
process/premult_alpha=false
process/size_limit=0
detect_3d/compress_to=0
"""


def load(name: str) -> np.ndarray:
    return np.asarray(Image.open(R / name).convert("RGBA")).astype(np.float32) / 255.0


def dilate(rgb: np.ndarray, a: np.ndarray, steps: int = 48) -> np.ndarray:
    """Цвет внутрь прозрачного: итеративное размытие с весом маски."""
    out = rgb.copy()
    w = (a > 0.5).astype(np.float32)
    acc = out * w[..., None]
    for _ in range(steps):
        if w.min() > 0:
            break
        im_c = Image.fromarray(np.clip(acc * 255, 0, 255).astype(np.uint8))
        bc = np.asarray(im_c.filter(ImageFilter.BoxBlur(2))).astype(np.float32) / 255
        bw = np.asarray(Image.fromarray((w * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(2))).astype(np.float32) / 255
        fill = (w < 0.5) & (bw > 0.01)
        col = bc / np.maximum(bw[..., None], 1e-3)
        out[fill] = col[fill]
        w = np.where(fill, 1.0, w)
        acc = out * w[..., None]
    return out


def main() -> None:
    cells = json.loads((R / "cells.json").read_text(encoding="utf-8"))
    albedo = np.zeros((SIZE, SIZE, 4), np.float32)
    normal = np.zeros((SIZE, SIZE, 3), np.float32)
    normal[...] = (0.5, 0.5, 1.0)
    meta = {}
    for name, c in cells.items():
        i = c["cell"]
        x0, y0 = (i % 2) * CW, (i // 2) * CH
        col = load(f"{name}_albedo.png")
        ao = load(f"{name}_ao.png")[..., 0]
        nor = load(f"{name}_normal.png")
        a = col[..., 3]
        rgb = col[..., :3]
        if name != "dead":
            # скан — свежие желтоватые побеги; хвоя ели в целом синее и чуть темнее (фото владельца)
            rgb = rgb * np.array([0.84, 0.98, 1.08])
        rgb = rgb * (0.68 + 0.32 * ao[..., None])
        rgb = dilate(rgb, a)
        n = dilate(nor[..., :3], a)
        h = min(CH, SIZE - y0)
        albedo[y0:y0 + h, x0:x0 + CW, :3] = rgb[:h]
        albedo[y0:y0 + h, x0:x0 + CW, 3] = a[:h]
        normal[y0:y0 + h, x0:x0 + CW] = n[:h]
        meta[name] = dict(uv=[x0 / SIZE, y0 / SIZE, CW / SIZE, h / SIZE], width=c["width"], height=c["height"],
                          anchor=c["anchor"], view=c["view"], axis_len=c["axis_len"])
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(albedo, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(OUT / "spruce_atlas_albedo.png")
    Image.fromarray((np.clip(normal, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(OUT / "spruce_atlas_normal.png")
    for name, nm in (("spruce_atlas_albedo.png", 0), ("spruce_atlas_normal.png", 1)):
        (OUT / (name + ".import")).write_text(IMPORT_COLOR.format(name=name, nm=nm), encoding="utf-8")
    (OUT / "spruce_atlas.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print("атлас ели:", ", ".join(meta))


if __name__ == "__main__":
    main()


def impostors() -> None:
    """Силуэты дальних елей: два вида рядом (1024×1024), цвет+маска и нормаль, заливка краёв."""
    meta = json.loads((ROOT / "assets/zone01/models/spruce.json").read_text(encoding="utf-8"))
    for name in meta:
        cols, nors = [], []
        for vi in (0, 1):
            c = load(f"imp_{name}_albedo_{vi}.png")
            n = load(f"imp_{name}_normal_{vi}.png")
            a = c[..., 3]
            cols.append(np.dstack([dilate(c[..., :3], a, 24), a]))
            nors.append(dilate(n[..., :3], a, 24))
        alb = np.concatenate(cols, axis=1)
        nor = np.concatenate(nors, axis=1)
        for suffix, img, nm in (("albedo", alb, 0), ("normal", nor, 1)):
            fname = f"{name}_far_{suffix}.png"
            mode = "RGBA" if suffix == "albedo" else "RGB"
            Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), mode).save(OUT / fname)
            (OUT / (fname + ".import")).write_text(IMPORT_COLOR.format(name=fname, nm=nm), encoding="utf-8")
    print("силуэты:", ", ".join(meta))


if __name__ == "__main__" and "--far" in __import__("sys").argv:
    impostors()
