"""Import the locally stored RING vehicle package into the Godot asset layout.

Run from the project root: python tools/import_ring_vehicles.py
Requires _asset_src/ring_vehicles/package, created when the asset pack is installed.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "_asset_src" / "ring_vehicles" / "package"
MODELS = ROOT / "assets" / "models" / "ring_vehicles"
TEXTURES = ROOT / "assets" / "textures" / "ring_vehicles"
CREDITS = ROOT / "assets" / "CREDITS.md"
STATUS = ROOT / "docs" / "STATUS.md"
ATTRIBUTES = ROOT / ".gitattributes"


def main() -> None:
    if not (RAW / "manifest.json").is_file():
        raise SystemExit(f"Исходный пакет не найден: {RAW}")
    if MODELS.exists() or TEXTURES.exists():
        raise SystemExit("Папки готовых моделей уже существуют; импорт не перезаписывает файлы.")

    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["vehicles"]) == 9
    assert sum(len(v["doors"]) for v in manifest["vehicles"]) == 36
    source_models = sorted((RAW / "gltf").glob("*.gltf"))
    assert len(source_models) == 45
    source_textures = sorted((RAW / "textures").glob("*.png"))
    assert len(source_textures) >= 36

    MODELS.mkdir(parents=True)
    TEXTURES.mkdir(parents=True)
    for texture in source_textures:
        shutil.copy2(texture, TEXTURES / texture.name)

    for source in source_models:
        doc = json.loads(source.read_text(encoding="utf-8"))
        for image in doc.get("images", []):
            original_uri = image["uri"]
            if not original_uri.startswith("../textures/"):
                raise ValueError(f"Неожиданный путь текстуры: {source.name}: {original_uri}")
            name = Path(original_uri).name
            if not (TEXTURES / name).exists():
                raise FileNotFoundError(TEXTURES / name)
            image["uri"] = f"../../textures/ring_vehicles/{name}"
        (MODELS / source.name).write_text(
            json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        shutil.copy2(source.with_suffix(".bin"), MODELS / source.with_suffix(".bin").name)

    shutil.copy2(RAW / "manifest.json", MODELS / "manifest.json")
    shutil.copy2(RAW / "TEXTURE_SOURCES.json", MODELS / "TEXTURE_SOURCES.json")
    (MODELS / "README_RU.md").write_text(
        "# Транспорт RING для Godot\n\n"
        "Девять собранных glTF-моделей: sedan, truck, bus × worn, damaged, wreck. "
        "У каждой модели четыре двери в отдельных glTF-файлах с pivot на петле. "
        "Все карты лежат в `res://assets/textures/ring_vehicles/`; пути в glTF уже настроены.\n\n"
        "Список моделей, дверей и координат петель — в `manifest.json`. "
        "Редактируемые `.blend` и исходные фототекстуры — "
        "в `_asset_src/ring_vehicles/` (эта папка не коммитится). "
        "В проекте ещё нужно настроить коллизии, LOD и, при необходимости, анимацию дверей.\n",
        encoding="utf-8",
    )

    lfs_rule = "assets/models/ring_vehicles/*.bin filter=lfs diff=lfs merge=lfs -text"
    attributes = ATTRIBUTES.read_text(encoding="utf-8")
    if lfs_rule not in attributes:
        ATTRIBUTES.write_text(attributes.rstrip() + "\n" + lfs_rule + "\n", encoding="utf-8")

    credit_lines = (
        "\n## Транспорт RING\n\n"
        "- `assets/models/ring_vehicles/` — модели седана, грузовика и автобуса, созданные для RING; текстуры на основе CC0 Poly Haven.\n"
        "- `assets/textures/ring_vehicles/` — Blue Metal Plate, Rob Tuytel, CC0 1.0, https://polyhaven.com/a/blue_metal_plate\n"
        "- `assets/textures/ring_vehicles/` — Rusty Metal Sheet, Amal Kumar, CC0 1.0, https://polyhaven.com/a/rusty_metal_sheet\n"
        "- `assets/textures/ring_vehicles/` — Rubber Tiles, Amal Kumar, CC0 1.0, https://polyhaven.com/a/rubber_tiles\n"
        "- `assets/textures/ring_vehicles/` — Denim Fabric 06, Greg Zaal (фото), Rico Cilliers (обработка), CC0 1.0, https://polyhaven.com/a/denim_fabric_06\n"
    )
    credits = CREDITS.read_text(encoding="utf-8")
    if "## Транспорт RING" not in credits:
        CREDITS.write_text(credits.rstrip() + "\n" + credit_lines, encoding="utf-8")

    status_line = (
        "\n## 2026-09-22 — транспорт окружения\n\n"
        "- Добавлен транспорт окружения: 9 glTF-моделей (седан, грузовик, автобус × "
        "3 состояния) и 36 отдельных дверей, фототекстуры CC0. "
        "Лежат в `assets/models/ring_vehicles/` и `assets/textures/ring_vehicles/`. "
        "Проверить в игровых сценах свет, коллизии и LOD.\n"
    )
    status = STATUS.read_text(encoding="utf-8")
    if "Добавлен транспорт окружения: 9 glTF-моделей" not in status:
        STATUS.write_text(status.rstrip() + "\n" + status_line, encoding="utf-8")

    print(f"Импортировано {len(source_models)} glTF, {len(source_textures)} текстур")


if __name__ == "__main__":
    main()
