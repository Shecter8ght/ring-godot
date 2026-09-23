"""Модель из _asset_src в assets/models/props/<id> с записью лицензии в assets/CREDITS.md.

    python tools/import_model.py <id>

Сырьё: _asset_src/<id>/ — модель (.glb или .gltf с текстурами рядом) и license.txt вида:

    Название: Old sofa
    Автор: Someone
    Лицензия: CC0
    Источник: https://polyhaven.com/a/...

Только CC0 / CC-BY (правило проекта). Готовое — в assets/models/props/<id>/ (LFS), дальше в
редакторе: узел ModelProp, поле model → этот файл (см. docs/howto_props.md).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src"
DST = ROOT / "assets" / "models" / "props"
CREDITS = ROOT / "assets" / "CREDITS.md"
KEEP = {".glb", ".gltf", ".bin", ".png", ".jpg", ".jpeg", ".webp"}


def read_license(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    pid = sys.argv[1]
    src = SRC / pid
    lic_path = src / "license.txt"
    if not lic_path.is_file():
        raise SystemExit(f"Нет {lic_path} — без лицензии модель не берём.")
    lic = read_license(lic_path)
    kind = lic.get("лицензия", lic.get("license", ""))
    if not (kind.upper().startswith("CC0") or kind.upper().startswith("CC-BY") or kind.upper().startswith("CC BY")):
        raise SystemExit(f"Лицензия «{kind}» не подходит: только CC0 / CC-BY.")
    files = [p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in KEEP]
    models = [p for p in files if p.suffix.lower() in (".glb", ".gltf")]
    if not models:
        raise SystemExit(f"В {src} нет .glb / .gltf.")
    dst = DST / pid
    dst.mkdir(parents=True, exist_ok=True)
    for p in files:
        rel = p.relative_to(src)
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
    name = lic.get("название", lic.get("name", pid))
    author = lic.get("автор", lic.get("author", "?"))
    url = lic.get("источник", lic.get("source", ""))
    row = f"| {name} | {author} | {kind} {url} | models/props/{pid} |\n"
    text = CREDITS.read_text(encoding="utf-8") if CREDITS.is_file() else ""
    if f"models/props/{pid} |" not in text:
        with CREDITS.open("a", encoding="utf-8", newline="\n") as f:
            f.write(row)
    for m in models:
        print(f"готово: res://assets/models/props/{pid}/{m.relative_to(src).as_posix()}")
    print("дальше: tools/godot.cmd --headless --import, затем в редакторе ModelProp → model")


if __name__ == "__main__":
    main()
