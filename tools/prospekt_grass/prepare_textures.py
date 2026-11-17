"""Игровые 4K-карты земли для стенда и одного газона «Проспекта».

    python -X utf8 tools/prospekt_grass/prepare_textures.py

Исходники 8K остаются в _asset_src/prospekt_grass. В assets попадают только
производные 4K: albedo/normal/arm/height.jpg и настройки VRAM-импорта Godot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "prospekt_grass"
OUT = ROOT / "assets" / "textures" / "prospekt_grass"
RES = 4096

IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="{source}"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map={normal}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode={rough_mode}
roughness/src_normal="{rough_src}"
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def source_maps(candidate: str) -> dict[str, Path]:
    if candidate in ("leafy", "soil"):
        asset = "leafy_grass" if candidate == "leafy" else "grass_ground"
        return {name: SRC / asset / f"{name}_8k.jpg" for name in ("albedo", "normal", "arm", "height")}
    folder = SRC / "Grass001"
    maps = {
        "albedo": folder / "Grass001_8K-JPG_Color.jpg",
        "normal": folder / "Grass001_8K-JPG_NormalGL.jpg",
        "height": folder / "Grass001_8K-JPG_Displacement.jpg",
    }
    rough = Image.open(folder / "Grass001_8K-JPG_Roughness.jpg").convert("L")
    ao = Image.open(folder / "Grass001_8K-JPG_AmbientOcclusion.jpg").convert("L")
    metal = Image.new("L", rough.size, 0)
    arm = Image.merge("RGB", (ao.resize(rough.size), rough, metal))
    arm_path = folder / "derived_arm_8k.png"
    if not arm_path.exists():
        arm.save(arm_path)
    maps["arm"] = arm_path
    return maps


def linear_mean(image: Image.Image) -> list[float]:
    small = np.asarray(image.convert("RGB").resize((256, 256)), dtype=np.float32) / 255.0
    linear = np.where(small <= 0.04045, small / 12.92, ((small + 0.055) / 1.055) ** 2.4)
    return [round(float(v), 6) for v in linear.mean(axis=(0, 1))]


def write_import(path: Path, candidate: str, name: str) -> None:
    source = f"res://assets/textures/prospekt_grass/{path.name}"
    normal_source = f"res://assets/textures/prospekt_grass/{candidate}_normal.jpg"
    text = IMPORT.format(source=source, normal=1 if name == "normal" else 0,
        rough_mode=1 if name == "normal" else 3 if name == "arm" else 0,
        rough_src=normal_source if name in ("normal", "arm") else "")
    path.with_suffix(path.suffix + ".import").write_text(text, encoding="utf-8", newline="\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"textures": {}}
    for candidate in ("leafy", "grass001", "soil"):
        entry: dict = {"resolution": RES, "source": source_maps(candidate)["albedo"].parent.name, "maps": {}}
        for name, source in source_maps(candidate).items():
            image = Image.open(source).convert("RGB")
            if image.size != (RES, RES):
                image = image.resize((RES, RES), Image.Resampling.LANCZOS)
            dest = OUT / f"{candidate}_{name}.jpg"
            image.save(dest, "JPEG", quality=96, subsampling=0, optimize=True)
            write_import(dest, candidate, name)
            entry["maps"][name] = {
                "file": dest.name,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                "mean_linear": linear_mean(image) if name == "albedo" else None,
            }
            print(f"{candidate}/{name}: {RES} × {RES}", flush=True)
        report["textures"][candidate] = entry
    report_path = SRC / "game_assets.json"
    if report_path.exists():
        old = json.loads(report_path.read_text(encoding="utf-8"))
        old.update(report)
        report = old
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
