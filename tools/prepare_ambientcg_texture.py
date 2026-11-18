"""Подготовка одного набора ambientCG к игре без переименования карт руками.

    python -X utf8 tools/prepare_ambientcg_texture.py Gravel023

Ищет исходники в _asset_src/textures/<id>/ рекурсивно, сохраняет их и собирает
albedo / normalGL / ARM / height в assets/textures/<id>/. Затем нужен --import Godot.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

import build_textures

ROOT = Path(__file__).resolve().parents[1]


def pick(source: Path, suffix: str) -> Path | None:
    found = sorted(p for p in source.rglob(f"*_{suffix}.*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if len(found) > 1:
        raise RuntimeError(f"Несколько карт {suffix}: {found}")
    return found[0] if found else None


def save_jpg(source: Path, dest: Path, gray: bool = False) -> None:
    with Image.open(source) as image:
        converted = image.convert("L" if gray else "RGB")
        converted.save(dest, "JPEG", quality=96, subsampling=0, optimize=True)


def add_credits(asset_id: str, info: dict[str, str]) -> None:
    path = ROOT / "assets" / "CREDITS.md"
    text = path.read_text(encoding="utf-8")
    marker = f"`assets/textures/{asset_id}/`"
    if marker in text:
        return
    section = text.find("## Текстуры")
    next_section = text.find("\n## ", section + 1)
    if section < 0 or next_section < 0:
        raise RuntimeError("В assets/CREDITS.md нет раздела текстур")
    role = f" — {info['role']}" if info.get("role") else ""
    line = (f"- {marker} — {info.get('title', asset_id)}, {info.get('author', '?')}, "
            f"{info.get('license', '?')}, {info.get('source', '')}{role}\n")
    text = text[:next_section] + "\n" + line + text[next_section:]
    path.write_text(text, encoding="utf-8", newline="\n")


def main(asset_id: str) -> None:
    source = ROOT / "_asset_src" / "textures" / asset_id
    if not source.is_dir():
        raise FileNotFoundError(source)
    license_path = next((p for p in source.iterdir() if p.name.lower() == "license.txt"), None)
    if license_path is None:
        raise FileNotFoundError(f"Нет license.txt: {source}")
    info = build_textures.read_license(license_path)
    albedo = pick(source, "Color")
    normal = pick(source, "NormalGL")
    roughness = pick(source, "Roughness")
    ao = pick(source, "AmbientOcclusion")
    height = pick(source, "Displacement")
    if albedo is None or normal is None or roughness is None or ao is None:
        raise RuntimeError("Нужны Color, NormalGL, Roughness и AmbientOcclusion")
    dest = ROOT / "assets" / "textures" / asset_id
    dest.mkdir(parents=True, exist_ok=True)
    save_jpg(albedo, dest / "albedo.jpg")
    save_jpg(normal, dest / "normal.jpg")
    with Image.open(roughness) as rough_image, Image.open(ao) as ao_image:
        rough = rough_image.convert("L")
        occlusion = ao_image.convert("L").resize(rough.size, Image.Resampling.LANCZOS)
        metal = Image.new("L", rough.size, 0)
        arm = Image.merge("RGB", (occlusion, rough, metal))
        arm.save(dest / "arm.jpg", "JPEG", quality=96, subsampling=0, optimize=True)
    maps = ["albedo", "normal", "arm"]
    if height is not None:
        save_jpg(height, dest / "height.jpg", gray=True)
        maps.append("height")
    for name in maps:
        build_textures.write_import(dest, asset_id, name)
    material_maps = [name for name in maps if name != "height"]
    materials = ROOT / "assets" / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / f"{asset_id}.tres").write_text(build_textures.material_tres(asset_id, material_maps), encoding="utf-8", newline="\n")
    add_credits(asset_id, info)
    print(f"{asset_id}: {', '.join(maps)} → {dest}")
    print("Дальше: tools/godot.cmd --headless --import")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Использование: python -X utf8 tools/prepare_ambientcg_texture.py <id>")
    main(sys.argv[1])
