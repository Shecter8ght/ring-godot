"""Навесной замок (assets/models/props/padlock_01): настройки импорта после первого `tools/godot.cmd --headless --import`.

    python -X utf8 tools/padlock_v01/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.

Те же настройки, что у контейнеров лута (tools/loot_containers/medbag_imports.py): сжатие VRAM и mip-уровни; у модели — без
автоматических LOD (generate_lods=false: на мелком предмете рвут рисунок по швам развёртки; свои LOD — узлы *_lod1);
у нормали — флаг карты нормалей, у ORM — сглаживание шероховатости по нормали, канал явно (режим 3, не 8).
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2] / "assets/models/props/padlock_01"
RES = "res://assets/models/props/padlock_01/textures/"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


n = 0
for f in sorted((BASE / "textures").glob("*.webp.import")):
    base = f.name[: -len(".import")]
    t = f.read_text(encoding="utf-8")
    t = setp(t, "compress/mode", "2")
    t = setp(t, "mipmaps/generate", "true")
    t = setp(t, "detect_3d/compress_to", "0")
    if base.endswith("_normal.webp"):
        t = setp(t, "compress/normal_map", "1")
        t = setp(t, "roughness/mode", "1")
    elif base.endswith("_occlusionRoughnessMetallic.webp"):
        t = setp(t, "roughness/mode", "3")
        t = setp(t, "roughness/src_normal", f'"{RES}{base.replace("_occlusionRoughnessMetallic", "_normal")}"')
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
for f in sorted(BASE.glob("*.gltf.import")):
    t = f.read_text(encoding="utf-8")
    t = setp(t, "meshes/generate_lods", "false")
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
print("IMPORTS padlock_01", n)
