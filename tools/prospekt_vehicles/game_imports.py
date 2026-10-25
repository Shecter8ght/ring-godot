"""Транспорт «Проспекта»: настройки импорта карт после первого `tools/godot.cmd --headless --import`.

    python -X utf8 tools/prospekt_vehicles/game_imports.py, затем ещё раз `tools/godot.cmd --headless --import`.

Карты машин (assets/models/prospekt_vehicles/textures) — сжатие VRAM и mip-уровни сразу (не ждать «detect 3D»: машин на
карте сотни, без mip-уровней дальние рябят и тянут память), у нормалей — флаг карты нормалей, у ORM — сглаживание
шероховатости по нормали (блеск краски не рябит вдали). Автоматические LOD движка у моделей остаются включены.
"""
import re
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "assets/models/prospekt_vehicles/textures"
RES = "res://assets/models/prospekt_vehicles/textures/"


def setp(text: str, key: str, val: str) -> str:
    pat = re.compile(r"^" + re.escape(key) + r"=.*$", re.M)
    assert pat.search(text), key
    return pat.sub(f"{key}={val}", text)


n = 0
for f in sorted(D.glob("PV_*.webp.import")):
    base = f.name[: -len(".import")]
    t = f.read_text(encoding="utf-8")
    t = setp(t, "compress/mode", "2")
    t = setp(t, "mipmaps/generate", "true")
    t = setp(t, "detect_3d/compress_to", "0")
    if base.endswith("_normal.webp"):
        t = setp(t, "compress/normal_map", "1")
    elif base.endswith("_occlusionRoughnessMetallic.webp"):
        t = setp(t, "roughness/mode", "3")             # Detect, Disabled, Red, Green… — шероховатость в G
        t = setp(t, "roughness/src_normal", f'"{RES}{base.replace("_occlusionRoughnessMetallic", "_normal")}"')
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
print("PV_IMPORTS", n)
