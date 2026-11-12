"""АСТЕН-919: настройки импорта карт Godot после первого `tools/godot.cmd --headless --import` (как у ГРАНЬ-15,
tools/ar15/game_imports.py).

python -X utf8 tools/asten919/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.
Сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей, у ORM — сглаживание шероховатости по своей карте нормалей
(roughness/mode=3: G — шероховатость; значение 8, которое пишет редактор Godot 4.7.2, фильтр выключает).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = "assets/models/weapons/asten919"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


res = f"res://{D}/"
for f in sorted((ROOT / D).glob("*.png.import")):
    base = f.name[:-len(".import")]
    t = f.read_text(encoding="utf-8")
    t = setp(t, "compress/mode", "2")
    t = setp(t, "mipmaps/generate", "true")
    t = setp(t, "detect_3d/compress_to", "0")
    if base.endswith("_normal.png"):
        t = setp(t, "compress/normal_map", "1")
        t = setp(t, "roughness/mode", "1")
        t = setp(t, "roughness/src_normal", f'"{res}{base}"')
    elif base.endswith("_orm.png"):
        t = setp(t, "roughness/mode", "3")
        t = setp(t, "roughness/src_normal", f'"{res}{base.replace("_orm.png", "_normal.png")}"')
    f.write_text(t, encoding="utf-8", newline="\n")
    print("ASTEN_IMPORTS", f.name)
