"""Скачивает наборы PBR-текстур с Poly Haven (CC0) в _asset_src/textures/<id>/.

Использование: python tools/fetch_polyhaven.py [id ...]
Без аргументов качает набор из TEXTURES. Каждый набор — albedo/normal/arm (AO-rough-metal) 2K jpg
и license.txt с автором и ссылкой. Дальше: python tools/build_textures.py.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src" / "textures"
UA = {"User-Agent": "RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)"}
RES = "2k"

# id на Poly Haven → роль в игре (для чего материал)
TEXTURES: dict[str, str] = {
    "large_floor_tiles_02": "пол галереи ТЦ",
    "worn_tile_floor": "пол торгового зала",
    "concrete_floor_worn_001": "пол склада и служебных помещений",
    "asphalt_02": "асфальт парковки и доков",
    "painted_plaster_wall": "стены магазинов",
    "concrete_wall_006": "стены служебных коридоров",
    "concrete_panels": "внешняя стена здания",
    "concrete_block_wall_02": "стены доков и ограждения",
    "painted_metal_shutter": "роллеты магазинов",
    "corrugated_iron_02": "профлист, крыши доков",
    "metal_plate": "рампы и металлические полы",
    "sapele_veneer": "дерево автомата (красноватый лак)",
    "natural_walnut_veneer": "ореховое ложе дробовика и винтовки",
    "green_metal_rust": "крашеный корпус гранаты",
    # зона 1 (район ТЦ): земля — смешивает шейдер рельефа district_terrain
    "leafy_grass": "рельеф: осенний газон с листвой (основа)",
    "sparse_grass": "рельеф: редкая трава, пятна на газоне",
    "forest_floor": "рельеф: опавшая листва (лесополоса, под деревьями)",
    "mud_forest": "рельеф: грязь, тропы, колеи",
    "rocks_ground_02": "рельеф: каменистые склоны оврага, холма",
    "gravel_stones": "рельеф: щебень насыпи, стройплощадки",
    # зона 1, двор хрущёвок (5): фасады и благоустройство
    "rough_concrete": "хрущёвка 1-464: панели с каменной крошкой",
    "concrete_wall_007": "хрущёвка: цоколь, торцы, бетонные плиты",
    "concrete_wall_008": "хрущёвка: шифер, козырьки",
    "whitewashed_brick": "хрущёвка 1-447: силикатный кирпич",
    "red_bricks_04": "кирпичный цоколь, вентшахты на крыше",
    "tarred_gravel": "плоская кровля (рубероид)",
    "rusty_metal_sheet": "отливы, двери, гаражи",
    "worn_corrugated_iron": "обшивка балконов, навесы",
    "plywood": "заколоченные окна",
    "wood_planks_grey": "деревянная обшивка балконов, сараи",
    "concrete_floor_02": "ступени, бордюры, плиты дорожек",
    "worn_asphalt": "асфальт двора",
    "bark_brown_02": "кора тополя и клёна",
}

# карта Poly Haven → имя файла у нас
MAPS = {"Diffuse": "albedo", "nor_gl": "normal", "arm": "arm", "Rough": "rough", "AO": "ao"}
# доп. карты для отдельных наборов: асфальту — высоты (вода собирается во впадинах, шейдер мокрой земли)
EXTRA_MAPS: dict[str, dict[str, str]] = {"asphalt_02": {"Displacement": "height"}}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r:
        return json.load(r)


def download(url: str, dest: Path) -> int:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(dest, "wb") as f:
        data = r.read()
        f.write(data)
    return len(data)


def fetch(asset_id: str, info: dict) -> None:
    out = SRC / asset_id
    out.mkdir(parents=True, exist_ok=True)
    files = get_json(f"https://api.polyhaven.com/files/{asset_id}")
    got: list[str] = []
    total = 0
    for key, name in {**MAPS, **EXTRA_MAPS.get(asset_id, {})}.items():
        # arm заменяет rough+ao; если есть — остальные не нужны
        if key in ("Rough", "AO") and "arm" in files:
            continue
        entry = files.get(key)
        if not entry:
            continue
        variant = entry.get(RES, {}).get("jpg") or next(iter(entry.get(RES, {}).values()), None)
        if not variant:
            continue
        dest = out / f"{name}.jpg"
        if not dest.exists():
            total += download(variant["url"], dest)
        got.append(name)
    authors = ", ".join(info.get("authors", {}).keys()) or "Poly Haven"
    (out / "license.txt").write_text(
        f"title: {info.get('name', asset_id)}\n"
        f"author: {authors}\n"
        f"license: CC0 1.0\n"
        f"source: https://polyhaven.com/a/{asset_id}\n"
        f"maps: {', '.join(got)}\n"
        f"role: {TEXTURES.get(asset_id, '')}\n",
        encoding="utf-8",
    )
    print(f"{asset_id}: {', '.join(got)} ({total // 1024} КБ)")


def main() -> None:
    ids = sys.argv[1:] or list(TEXTURES)
    catalog = get_json("https://api.polyhaven.com/assets?t=textures")
    for asset_id in ids:
        if asset_id not in catalog:
            print(f"{asset_id}: нет на Poly Haven", file=sys.stderr)
            continue
        fetch(asset_id, catalog[asset_id])


if __name__ == "__main__":
    main()
