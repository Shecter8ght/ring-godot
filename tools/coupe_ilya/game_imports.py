"""Купе Ильи: настройки импорта Godot после первого `tools/godot.cmd --headless --import`.

    python -X utf8 tools/coupe_ilya/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.

coupe_ilya.glb — как машины RING (assets/models/ring_vehicles): корень StaticBody3D, скрипт
tools/editor/vehicle_import.gd (одна выпуклая коллизия на машину, след на навмеше); свои LOD (150 / 50 / 12 тыс.,
владелец 2026-10-18) — автоматические LOD движка выключены; встроенные карты извлекаются рядом с моделью.
Карты — как у ПМ и Мосина: сжатие VRAM, mip-уровни; у нормалей — флаг карты нормалей, у ORM — сглаживание
шероховатости по нормали (блеск лака не рябит вдали).
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "assets/models/props/coupe_ilya"
RES = "res://assets/models/props/coupe_ilya/"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


glb = D / "coupe_ilya.glb.import"
t = glb.read_text(encoding="utf-8")
t = setp(t, "nodes/root_type", '"StaticBody3D"')
t = setp(t, "import_script/path", '"res://tools/editor/vehicle_import.gd"')
t = setp(t, "meshes/generate_lods", "false")
t = setp(t, "gltf/embedded_image_handling", "1")
glb.write_text(t, encoding="utf-8", newline="\n")
print("COUPE_IMPORTS", glb.name)
for f in sorted(D.glob("*.png.import")):
    base = f.name[: -len(".import")]
    t = f.read_text(encoding="utf-8")
    t = setp(t, "compress/mode", "2")
    t = setp(t, "mipmaps/generate", "true")
    t = setp(t, "detect_3d/compress_to", "0")
    if base.endswith("_normal.png"):
        t = setp(t, "compress/normal_map", "1")
        t = setp(t, "roughness/mode", "1")
        t = setp(t, "roughness/src_normal", f'"{RES}{base}"')
    elif base.endswith("_orm.png"):
        t = setp(t, "roughness/mode", "3")             # Detect,Disabled,Red,Green… — шероховатость в G
        t = setp(t, "roughness/src_normal", f'"{RES}{base.replace("_orm.png", "_normal.png")}"')
    f.write_text(t, encoding="utf-8", newline="\n")
    print("COUPE_IMPORTS", f.name)
