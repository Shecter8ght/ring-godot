"""Настройки повторного импорта Godot для сеток и общих карт glTF.

    tools/godot.cmd --headless --import
    python -X utf8 tools/prospekt_grass/configure_imports.py
    tools/godot.cmd --headless --import
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "assets" / "models" / "prospekt_grass"
GROUND = ROOT / "assets" / "textures" / "prospekt_grass"


def param(text: str, key: str, value: str) -> str:
    pattern = rf"(?m)^{re.escape(key)}=.*$"
    line = f"{key}={value}"
    if re.search(pattern, text):
        return re.sub(pattern, line, text)
    return text.rstrip() + "\n" + line + "\n"


def main() -> None:
    count = 0
    for path in MODELS.glob("*.gltf.import"):
        text = path.read_text(encoding="utf-8")
        for key, value in (("meshes/ensure_tangents", "true"), ("meshes/generate_lods", "false"),
                           ("meshes/create_shadow_meshes", "false"), ("animation/import", "false")):
            text = param(text, key, value)
        path.write_text(text, encoding="utf-8", newline="\n")
        count += 1
    for path in MODELS.glob("textures/*.png.import"):
        text = path.read_text(encoding="utf-8")
        for key, value in (("compress/mode", "2"), ("compress/high_quality", "true"),
                           ("mipmaps/generate", "true"), ("process/fix_alpha_border", "true"),
                           ("process/premult_alpha", "false"), ("detect_3d/compress_to", "0")):
            text = param(text, key, value)
        path.write_text(text, encoding="utf-8", newline="\n")
        count += 1
    for path in GROUND.glob("*.jpg.import"):
        text = path.read_text(encoding="utf-8")
        name = path.name
        normal = "_normal.jpg.import" in name
        arm = "_arm.jpg.import" in name
        candidate = name.split("_", 1)[0]
        normal_path = f"res://assets/textures/prospekt_grass/{candidate}_normal.jpg"
        for key, value in (("compress/mode", "2"), ("compress/high_quality", "true"),
                           ("compress/normal_map", "1" if normal else "0"), ("mipmaps/generate", "true"),
                           ("roughness/mode", "1" if normal else "3" if arm else "0"),
                           ("roughness/src_normal", f'"{normal_path}"' if normal or arm else '""'),
                           ("detect_3d/compress_to", "0")):
            text = param(text, key, value)
        path.write_text(text, encoding="utf-8", newline="\n")
        count += 1
    print(f"Настроено импортов: {count}")


if __name__ == "__main__":
    main()
