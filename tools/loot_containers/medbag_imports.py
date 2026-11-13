"""Контейнеры лута (assets/models/loot_containers): настройки импорта карт после первого `tools/godot.cmd --headless --import`.

    python -X utf8 tools/loot_containers/medbag_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.

Сжатие VRAM и mip-уровни; у нормалей — флаг карты нормалей (RGTC); у ORM — сглаживание шероховатости по нормали, канал
явно (зелёный: значение 8, которое пишет редактор, фильтр выключает — навык godot-asset-preparation).
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "assets/models/loot_containers/textures"
RES = "res://assets/models/loot_containers/textures/"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


n = 0
for f in sorted(D.glob("*.webp.import")):
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
print("IMPORTS loot_containers", n)
