"""Патчи сборки для друзей: метка основы, проверка перед патчем, раскладка готового патча.

  base   — после полного выпуска (tools/build_release.cmd): новая метка основы в export/RING/patches/base.txt
           (уходит друзьям в архиве), снимок для проверок в export/base/base.json.
  check  — перед патчем (tools/build_patch.cmd): основа на месте и не пересобрана втихую; project.godot
           и загрузчик патчей не менялись — их патч не заменит, нужен полный выпуск. Удалённые с основы
           файлы — только предупреждение: из сборки друзей патч их не уберёт.
  pack   — выгруженный патч в export/patches/RING_patch_<N>_<метка>.pck (его и отправлять) и копия
           в export/RING/patches, чтобы своя распакованная сборка была как у друзей.

Патчи накопительные (каждый — все изменения от основы), игра берёт только последний: src/core/release_patch.gd.
"""

from pathlib import Path
import argparse
import datetime
import difflib
import hashlib
import json
import os
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "export" / "RING"
BASE_PCK = BUILD / "RING.pck"
BUILD_PATCHES = BUILD / "patches"
MARKER = BUILD_PATCHES / "base.txt"
SNAPSHOT = ROOT / "export" / "base" / "base.json"
PATCHES = ROOT / "export" / "patches"
PROJECT = ROOT / "project.godot"
LOADER = ROOT / "src" / "core" / "release_patch.gd"
PREFIX = "RING_patch_"

# Папки, которых нет в сборке (exclude_filter пресета и служебные), и что из файлов попадает в PCK.
SKIP_DIRS = {".git", ".godot", "export", "tools", "docs", "_asset_src", "_sound_try", "референсы"}
EXPORTED_SUFFIXES = {".tscn", ".tres", ".gd", ".gdshader", ".gdshaderinc", ".json", ".res", ".scn"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exported_files() -> list[str]:
    """Файлы проекта, которые экспорт кладёт в PCK (сцены, скрипты, данные, импортируемые ассеты)."""
    out: list[str] = []
    for folder, dirs, files in os.walk(ROOT):
        here = Path(folder)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                   and not (here / d / ".gdignore").exists()]
        names = set(files)
        for name in files:
            path = here / name
            rel = path.relative_to(ROOT).as_posix()
            if path.suffix in EXPORTED_SUFFIXES or name + ".import" in names or rel.startswith("data/terrain/"):
                out.append(rel)
    return sorted(out)


def load_snapshot() -> dict | None:
    if not SNAPSHOT.is_file() or not BASE_PCK.is_file():
        return None
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def patch_numbers(base_id: str) -> list[int]:
    suffix = "_" + base_id + ".pck"
    out: list[int] = []
    for path in PATCHES.glob(PREFIX + "*" + suffix):
        number = path.name[len(PREFIX):-len(suffix)]
        if number.isdigit():
            out.append(int(number))
    return sorted(out)


def cmd_base() -> int:
    if not BASE_PCK.is_file():
        print(f"Нет {BASE_PCK}: сначала выгрузить RING.pck (tools/build_release.cmd)")
        return 1
    base_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    BUILD_PATCHES.mkdir(parents=True, exist_ok=True)
    # Копии прежних патчей в папке сборки ушли бы друзьям в новом архиве; к новой основе они не подходят.
    for old in BUILD_PATCHES.glob(PREFIX + "*.pck"):
        old.unlink()
    MARKER.write_text(base_id + "\n", encoding="utf-8", newline="\n")
    stat = BASE_PCK.stat()
    snapshot = {
        "id": base_id,
        "pck_size": stat.st_size,
        "pck_mtime_ns": stat.st_mtime_ns,
        "project_godot": PROJECT.read_text(encoding="utf-8"),
        "loader_sha256": sha256(LOADER),
        "files": exported_files(),
    }
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Основа {base_id}: метка в {MARKER.relative_to(ROOT)}, снимок для патчей в {SNAPSHOT.relative_to(ROOT)}")
    return 0


def cmd_check() -> int:
    snapshot = load_snapshot()
    if snapshot is None:
        print("Нет основы для патча: сначала полный выпуск tools/build_release.cmd (и раздать его друзьям)")
        return 1
    base_id = str(snapshot["id"])
    marker = MARKER.read_text(encoding="utf-8").strip() if MARKER.is_file() else ""
    stat = BASE_PCK.stat()
    if marker != base_id or stat.st_size != snapshot["pck_size"] or stat.st_mtime_ns != snapshot["pck_mtime_ns"]:
        print(f"{BASE_PCK.relative_to(ROOT)} не та основа, что записана ({base_id}): пересобран мимо "
              "tools/build_release.cmd. Нужен полный выпуск.")
        return 1
    failed = False
    project_now = PROJECT.read_text(encoding="utf-8")
    if project_now != snapshot["project_godot"]:
        # Настройки проекта (автозагрузки, клавиши, рендер) игра читает до патча — патч их не поменяет.
        diff = list(difflib.unified_diff(str(snapshot["project_godot"]).splitlines(), project_now.splitlines(),
                                         "основа", "сейчас", lineterm="", n=0))
        print("project.godot изменился с основы — патч это не доставит, нужен полный выпуск:")
        for line in diff[2:32]:
            print("  " + line)
        if len(diff) > 32:
            print(f"  … ещё {len(diff) - 32} строк")
        failed = True
    if sha256(LOADER) != snapshot["loader_sha256"]:
        print(f"{LOADER.relative_to(ROOT).as_posix()} изменился с основы — загрузчик патчей сам патчем не "
              "меняется, нужен полный выпуск")
        failed = True
    if failed:
        return 1
    removed = sorted(set(snapshot["files"]) - set(exported_files()))
    if removed:
        print(f"Предупреждение: {len(removed)} файл(ов) удалено с основы — у друзей они останутся в RING.pck "
              "(не мешает, пока на них никто не ссылается и папку не перебирают):")
        for rel in removed[:20]:
            print("  " + rel)
        if len(removed) > 20:
            print(f"  … ещё {len(removed) - 20}")
    numbers = patch_numbers(base_id)
    print(f"Основа {base_id}: собираю патч {numbers[-1] + 1 if numbers else 1}")
    return 0


def cmd_pack(exported: Path) -> int:
    snapshot = load_snapshot()
    if snapshot is None or not exported.is_file():
        print(f"Нет основы или выгруженного патча {exported}")
        return 1
    base_id = str(snapshot["id"])
    numbers = patch_numbers(base_id)
    number = numbers[-1] + 1 if numbers else 1
    target = PATCHES / f"{PREFIX}{number}_{base_id}.pck"
    os.replace(exported, target)
    BUILD_PATCHES.mkdir(parents=True, exist_ok=True)
    for old in BUILD_PATCHES.glob(PREFIX + "*.pck"):
        old.unlink()
    shutil.copy2(target, BUILD_PATCHES / target.name)
    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"Патч {number} к основе {base_id}: {target.relative_to(ROOT)} ({size_mb:.1f} МБ)")
    print("Друзьям: положить файл в папку patches рядом с RING.exe (прежние патчи можно удалить).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("base", help="после полного выпуска: метка основы и снимок")
    sub.add_parser("check", help="перед патчем: можно ли собрать патч")
    pack = sub.add_parser("pack", help="разложить выгруженный патч")
    pack.add_argument("exported", type=Path)
    args = parser.parse_args()
    if args.command == "base":
        return cmd_base()
    if args.command == "check":
        return cmd_check()
    return cmd_pack(args.exported)


if __name__ == "__main__":
    sys.exit(main())
