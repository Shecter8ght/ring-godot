"""Дома «Проспекта»: настройки импорта после первого `tools/godot.cmd --headless --import` (затем импорт ещё раз).
  python -X utf8 tools/prospekt_houses/game_imports.py

Модели (assets/models/prospekt_houses/*/*.gltf): без автоматических LOD движка (generate_lods=false — свои LOD0/1/2, а
упрощение движка рвёт рисунок по швам), касательные — для parallax бетона и нормалей. Карты assets/textures/prospekt_houses:
сжатие VRAM и mip-уровни; у нормалей — флаг карты нормалей; у ORM — сглаживание шероховатости по нормали, канал — зелёный
(значение 8, которое пишет редактор, фильтр выключает — навык godot-asset-preparation); у атласа грязи и LOD2 — VRAM с mip.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "assets/textures/prospekt_houses"
MOD = ROOT / "assets/models/prospekt_houses"
RES_TEX = "res://assets/textures/prospekt_houses/"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


n = 0
for f in sorted(list(TEX.glob("*.import")) + list(MOD.glob("*/*.png.import"))):
    base = f.name[: -len(".import")]
    t = f.read_text(encoding="utf-8")
    if "importer=\"texture\"" not in t:
        continue
    t = setp(t, "compress/mode", "2")
    t = setp(t, "mipmaps/generate", "true")
    t = setp(t, "detect_3d/compress_to", "0")
    if base.endswith("_normal.png"):
        t = setp(t, "compress/normal_map", "1")
        t = setp(t, "roughness/mode", "0")
    elif base.endswith("_orm.webp"):
        t = setp(t, "roughness/mode", "3")
        t = setp(t, "roughness/src_normal", f'"{RES_TEX}{base.replace("_orm.webp", "_normal.png")}"')
    else:
        t = setp(t, "roughness/mode", "0")
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
for f in sorted(MOD.glob("*/*.gltf.import")):
    t = f.read_text(encoding="utf-8")
    t = setp(t, "meshes/generate_lods", "false")
    t = setp(t, "meshes/ensure_tangents", "true")
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
print("IMPORTS prospekt_houses", n)
