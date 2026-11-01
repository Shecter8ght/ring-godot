"""Мебель общежития: настройки импорта карт после первого `tools/godot.cmd --headless --import`.

    python -X utf8 tools/dorm_modules/furniture_imports.py [furniture|electrics], затем ещё раз `tools/godot.cmd --headless --import`.

Карты assets/models/dorm/furniture/textures — сжатие VRAM и mip-уровни сразу (мебели в общежитии много, без mip-уровней
дальняя рябит), у нормалей — флаг карты нормалей (RGTC), у ORM — сглаживание шероховатости по нормали, канал явно
(зелёный: значение 8, которое пишет редактор, фильтр выключает — навык godot-asset-preparation). Варианты отделки
(<предмет>__<код>_*) — так же, со своей нормалью; плитка панцирной сетки (net_*) — тоже. Электрика (electrics) — те же
настройки; у её вариантов нормали нет — шероховатость сглаживается по нормали набора.
"""
import re
import sys
from pathlib import Path

KIND = sys.argv[1] if len(sys.argv) > 1 else "furniture"
D = Path(__file__).resolve().parents[2] / f"assets/models/dorm/{KIND}/textures"
RES = f"res://assets/models/dorm/{KIND}/textures/"


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
        t = setp(t, "roughness/mode", "3")             # Detect, Disabled, Red, Green… — шероховатость в G
        normal = base.replace("_occlusionRoughnessMetallic", "_normal")
        if not (D / normal).exists():
            normal = normal.split("__")[0] + "_normal.webp"
        t = setp(t, "roughness/src_normal", f'"{RES}{normal}"')
    f.write_text(t, encoding="utf-8", newline="\n")
    n += 1
print("IMPORTS", KIND, n)
