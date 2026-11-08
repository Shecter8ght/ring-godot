"""Пожарная АЦ, этап 2: фото-маски и фото-материалы износа для Painter из наборов CC0 (_asset_src/fire_truck_tex).

Рисунок каждого следа — со снимка или скана, а не из шума: пыль (ambientCG SurfaceImperfections015), водяные пятна
(SurfaceImperfections010), разводы (Smear006), царапины (Scratches003), мелкие сколы и крапины (Leaking012A),
пятна ржавчины (TextureCan metal_0055 — рыжие пятна на краске), ржавчина (Poly Haven rust_coarse_01: цвет, блеск,
рельеф), засохшая грязь (brown_mud_dry), прелая листва (dry_decay_leaves). Карты приводятся к 4096 и PNG
(маски — ч/б 8 бит, рельеф — 16 бит), чтобы Painter не тащил 8K EXR.

python -X utf8 tools/fire_truck/wear_masks.py   → WORK/wear/masks/*.png
EXR (шероховатость и рельеф Poly Haven) OpenCV здесь не читает — их сначала переводит в 16-битные PNG Blender:
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/fire_truck/wear_masks.py -- exr
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
try:
    import cv2  # noqa: E402
except ImportError:          # внутри Blender (перевод EXR) OpenCV нет
    cv2 = None
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import tex_sets as T  # noqa: E402

SRC = ROOT / "_asset_src" / "fire_truck_tex"
OUT = Path(T.WORK) / "wear" / "masks"
R = 4096


def read(path, gray=False):
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    scale = {np.dtype(np.uint8): 255.0, np.dtype(np.uint16): 65535.0}.get(im.dtype, 1.0)
    im = im.astype(np.float32) / scale
    if im.ndim == 3:
        im = im[..., :3][..., ::-1]
        if gray:
            im = im.mean(-1)
    return im


def fit(im, r=R):
    return cv2.resize(im, (r, r), interpolation=cv2.INTER_AREA)


def save8(name, im):
    im = np.clip(im, 0, 1)
    if im.ndim == 3:
        im = im[..., ::-1]
    cv2.imwrite(str(OUT / name), (im * 255 + 0.5).astype(np.uint8))


def save16(name, im):
    cv2.imwrite(str(OUT / name), (np.clip(im, 0, 1) * 65535 + 0.5).astype(np.uint16))


def norm(im, lo=1, hi=99):
    a, b = np.percentile(im, [lo, hi])
    return np.clip((im - a) / max(b - a, 1e-6), 0, 1)


EXR = [f"{b}_{k}_8k.exr" for b in ("polyhaven_rust_coarse_01/rust_coarse_01", "polyhaven_brown_mud_dry/brown_mud_dry",
                                    "polyhaven_dry_decay_leaves/dry_decay_leaves") for k in ("rough", "disp")]


def exr_to_png():
    """Внутри Blender: EXR → 16-битный PNG рядом в WORK/wear/masks/src (значения как есть, без цветового преобразования)."""
    import bpy
    dst = OUT / "src"
    dst.mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    sc.render.image_settings.color_mode = "BW"
    for rel in EXR:
        img = bpy.data.images.load(str(SRC / rel))
        img.colorspace_settings.name = "Non-Color"
        out = dst / (Path(rel).stem + ".png")
        img.save_render(str(out), scene=sc)
        print("EXR→PNG", out.name, flush=True)


def exr(rel):
    return OUT / "src" / (Path(rel).stem + ".png")


def main():
    if "exr" in sys.argv:
        exr_to_png()
        return
    OUT.mkdir(parents=True, exist_ok=True)
    ac = SRC
    save8("dust.png", fit(read(ac / "ambientcg_SurfaceImperfections015/SurfaceImperfections015_4K-PNG_Opacity.png", True)))
    save8("spots.png", fit(read(ac / "ambientcg_SurfaceImperfections010/SurfaceImperfections010_8K-PNG_Opacity.png", True)))
    save8("smear.png", fit(read(ac / "ambientcg_Smear006/Smear006_8K-PNG_Opacity.png", True)))
    save8("scratches.png", fit(read(ac / "ambientcg_Scratches003/Scratches003_4K-PNG_Opacity.png", True)))
    save8("specks.png", norm(fit(read(ac / "ambientcg_Leaking012A/Leaking012A_8K-PNG_Color.png", True)), 50, 99.7))
    # пятна ржавчины: рыжее на зелёной краске — по разнице красного и зелёного
    c = fit(read(ac / "texturecan_metal_0055/metal_0055_color_4k.jpg"))
    rp = norm(cv2.GaussianBlur(c[..., 0] - c[..., 1], (0, 0), 1.5), 30, 70)
    # тонкая сетка трещин зелёной краски — не ржавчина: открытие кругом 9 пикселей оставляет только пятна
    rp = cv2.morphologyEx(rp, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    save8("rustpatch.png", cv2.GaussianBlur(rp, (0, 0), 1.2))
    # ржавчина, грязь, листва — цвет (sRGB), шероховатость, рельеф
    for key, base in (("rust", "polyhaven_rust_coarse_01/rust_coarse_01"), ("mud", "polyhaven_brown_mud_dry/brown_mud_dry"),
                      ("leafmat", "polyhaven_dry_decay_leaves/dry_decay_leaves")):
        save8(f"{key}_color.png", fit(read(ac / f"{base}_diff_8k.jpg")))
        rough = read(exr(f"{base}_rough_8k.exr"))
        save8(f"{key}_rough.png", fit(rough if rough.ndim == 2 else rough[..., 0]))
        disp = read(exr(f"{base}_disp_8k.exr"))
        disp = disp if disp.ndim == 2 else disp[..., 0]
        save16(f"{key}_height.png", norm(fit(disp), 0.5, 99.5))
    # грязь пятнами: комья — где рельеф выше своей округи
    d = fit(read(exr("polyhaven_brown_mud_dry/brown_mud_dry_disp_8k.exr")))
    d = d if d.ndim == 2 else d[..., 0]
    hp = d - cv2.GaussianBlur(d, (0, 0), 40)
    save8("mud_clumps.png", norm(cv2.GaussianBlur(hp, (0, 0), 2), 35, 92))
    print("MASKS", sorted(p.name for p in OUT.glob("*.png")), flush=True)


if __name__ == "__main__":
    main()
