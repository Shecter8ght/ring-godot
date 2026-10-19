"""Собирает текстуры из _asset_src/textures/<id>/ в assets/textures/<id>/ и пишет
материалы assets/materials/<id>.tres (StandardMaterial3D, ORM) и assets/CREDITS.md.

Использование: python tools/build_textures.py
Игра обязана запускаться и без assets/textures — сборщик сектора подставляет плоские
цвета, если материала нет (см. src/world/sector_materials.gd).
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src" / "textures"
OUT_TEX = ROOT / "assets" / "textures"
OUT_MAT = ROOT / "assets" / "materials"
CREDITS = ROOT / "assets" / "CREDITS.md"

# Физический размер одной плитки текстуры, м — чтобы швы и плитка были в масштабе.
TILE_M: dict[str, float] = {
    "large_floor_tiles_02": 2.0,
    "worn_tile_floor": 1.5,
    "concrete_floor_worn_001": 3.0,
    # реально 3 м; чуть крупнее — издали не рябит (повтор ломает шейдер мокрого асфальта)
    "asphalt_02": 4.5,
    "painted_plaster_wall": 3.0,
    "concrete_wall_006": 3.0,
    "concrete_panels": 4.0,
    "concrete_block_wall_02": 2.5,
    "painted_metal_shutter": 2.0,
    "corrugated_iron_02": 2.0,
    "metal_plate": 1.5,
    # оружие: текстура ложится трипланарно на мелкие детали, плитка — четверть метра
    "sapele_veneer": 0.35,
    "natural_walnut_veneer": 0.35,
    "green_metal_rust": 0.25,
    # рельеф зоны 1: плитка в метрах (шейдер district_terrain берёт сами текстуры, не материалы)
    "leafy_grass": 3.0,
    "sparse_grass": 3.0,
    "forest_floor": 2.5,
    "mud_forest": 3.0,
    "rocks_ground_02": 4.0,
    "gravel_stones": 2.0,
    # двор хрущёвок (5)
    "rough_concrete": 2.0,
    "concrete_wall_007": 3.0,
    "concrete_wall_008": 3.0,
    "whitewashed_brick": 2.0,
    "red_bricks_04": 2.0,
    "tarred_gravel": 3.0,
    "rusty_metal_sheet": 2.0,
    "worn_corrugated_iron": 2.0,
    "plywood": 2.4,
    "wood_planks_grey": 2.0,
    "concrete_floor_02": 3.0,
    "worn_asphalt": 4.0,
    "bark_brown_02": 1.5,
    # территория ТЦ: реальные размеры наборов Poly Haven
    "asphalt_04": 4.0,
    "brick_pavement_03": 2.5,
    "patterned_paving": 2.0,
    "patterned_brick_floor": 1.81,
}


def read_license(path: Path) -> dict[str, str]:
    info: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def material_tres(asset_id: str, maps: list[str]) -> str:
    """Текст ресурса материала. UV-масштаб = 1/размер плитки: UV у мешей заданы в метрах."""
    tile = TILE_M.get(asset_id, 2.0)
    ext: list[str] = []
    for i, m in enumerate(maps, start=1):
        ext.append(f'[ext_resource type="Texture2D" path="res://assets/textures/{asset_id}/{m}.jpg" id="{i}"]')
    body = [
        f"[gd_resource type=\"StandardMaterial3D\" load_steps={len(maps) + 1} format=3]",
        "",
        *ext,
        "",
        "[resource]",
        f'resource_name = "{asset_id}"',
        "texture_filter = 5",
    ]
    idx = {m: i for i, m in enumerate(maps, start=1)}
    if "albedo" in idx:
        body.append(f'albedo_texture = ExtResource("{idx["albedo"]}")')
    if "arm" in idx:
        # arm = R:AO G:roughness B:metallic — те же каналы, что ORM в Godot
        body.append("roughness_texture_channel = 1")
        body.append(f'roughness_texture = ExtResource("{idx["arm"]}")')
        body.append("metallic_texture_channel = 2")
        body.append(f'metallic_texture = ExtResource("{idx["arm"]}")')
        body.append("ao_enabled = true")
        body.append("ao_texture_channel = 0")
        body.append(f'ao_texture = ExtResource("{idx["arm"]}")')
    else:
        if "rough" in idx:
            body.append(f'roughness_texture = ExtResource("{idx["rough"]}")')
        if "ao" in idx:
            body.append("ao_enabled = true")
            body.append(f'ao_texture = ExtResource("{idx["ao"]}")')
    if "normal" in idx:
        body.append("normal_enabled = true")
        body.append(f'normal_texture = ExtResource("{idx["normal"]}")')
    body.append(f"uv1_scale = Vector3({1 / tile:.4f}, {1 / tile:.4f}, 1)")
    body.append("")
    return "\n".join(body)


IMPORT_TEX = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/textures/{asset}/{name}.jpg"

[params]

compress/mode=2
compress/high_quality=false
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map={normal_map}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode={rough_mode}
roughness/src_normal="{rough_src}"
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def write_import(dest: Path, asset_id: str, name: str) -> None:
    """Настройки импорта новой карты — сразу сжатие VRAM и мип-уровни, как у карт, которые
    редактор уже пометил трёхмерными (без редактора --headless --import оставил бы несжатые)."""
    imp = dest / f"{name}.jpg.import"
    if imp.exists():
        return
    normal = name == "normal"
    imp.write_text(IMPORT_TEX.format(asset=asset_id, name=name, normal_map=1 if normal else 0,
                                     rough_mode=1 if normal else 0,
                                     rough_src=f"res://assets/textures/{asset_id}/normal.jpg" if normal else ""),
                   encoding="utf-8", newline="\n")


def main() -> None:
    OUT_TEX.mkdir(parents=True, exist_ok=True)
    OUT_MAT.mkdir(parents=True, exist_ok=True)
    credits = [
        "# Источники ассетов",
        "",
        "Каждый внешний ассет — строкой: путь в `assets/`, название, автор, лицензия, ссылка.",
        "Допустимы только CC0 / CC-BY и собственные работы. Сырьё лежит в `_asset_src/<тип>/<id>/` с `license.txt`.",
        "Файл собирается скриптами из `tools/` — руками не править.",
        "",
        "## Текстуры (assets/textures, материалы в assets/materials)",
        "",
    ]
    for src in sorted(p for p in SRC.iterdir() if p.is_dir()):
        lic = src / "license.txt"
        if not lic.exists():
            print(f"{src.name}: нет license.txt — пропуск")
            continue
        info = read_license(lic)
        maps = [m for m in ("albedo", "normal", "arm", "rough", "ao") if (src / f"{m}.jpg").exists()]
        dest = OUT_TEX / src.name
        dest.mkdir(parents=True, exist_ok=True)
        # высоты — только текстурой (их читает шейдер мокрого асфальта), в .tres не идут
        for m in maps + (["height"] if (src / "height.jpg").exists() else []):
            shutil.copy2(src / f"{m}.jpg", dest / f"{m}.jpg")
            write_import(dest, src.name, m)
        (OUT_MAT / f"{src.name}.tres").write_text(material_tres(src.name, maps), encoding="utf-8")
        credits.append(
            f"- `assets/textures/{src.name}/` — {info.get('title', src.name)}, "
            f"{info.get('author', '?')}, {info.get('license', '?')}, {info.get('source', '')}"
            + (f" — {info['role']}" if info.get("role") else "")
        )
        print(f"{src.name}: {', '.join(maps)}")
    credits.append("")
    # разделы других скриптов («Звук» — import_audio, «Небо» — fetch_sky, …) — сохраняем
    tail = ""
    if CREDITS.exists():
        old = CREDITS.read_text(encoding="utf-8")
        cut = old.find("\n## ", old.find("## Текстуры") + 1)
        if cut >= 0:
            tail = old[cut:]
    CREDITS.write_text("\n".join(credits) + tail, encoding="utf-8")


if __name__ == "__main__":
    main()
