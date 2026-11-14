#!/usr/bin/env python
"""Каталог моделей контейнеров лута: data/loot_containers.json.

Модели — партия 3 общежития (assets/models/dorm/furniture, закрытый и открытый вид); габариты берутся из её индекса
furniture.json. Второй источник — свои модели контейнеров (assets/models/loot_containers, индекс loot_containers_models.json:
медсумка lc_medbag; в записи модели — свои dir / index и расстояние смены на LOD1 «lod»). Виды без модели (model "") показываются прежним процедурным боксом / пропсом — их модели делаются в Blender
отдельно: подключение — правка этого файла (kinds.<вид>.model), без кода.
  python -X utf8 tools/gen_loot_containers.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = json.load(open(ROOT / "assets/models/dorm/furniture/furniture.json", encoding="utf8"))

# модель -> (открытая модель, варианты отделки; "" — как в файле)
MODELS = {
    "it_ammo": ("it_ammo_open", ["", "WD-PIN-RAW"]),
    "it_zip": ("it_zip_open", ["WD-PIN-RAW", ""]),
    "it_trunk": ("it_trunk_open", [""]),
    "it_toolbox": ("it_toolbox_open", ["EN-TBX-BLU", "EN-TBX-GRY"]),
    "it_suitcase": ("it_suitcase_open", ["PL-SHL-BLU", "PL-SHL-SLV"]),
    "it_duffel": ("it_duffel_half", ["FB-OXF-BLU", "FB-OXF-RED"]),
    "it_carton": ("it_carton_open", [""]),
    "it_pc": ("it_pc_opened", [""]),
}
# модели из assets/models/loot_containers: модель -> (открытая модель, варианты отделки)
LOOT_DIR = "res://assets/models/loot_containers"
LOOT_MODELS = {
    "lc_medbag": ("lc_medbag_open", [""]),
    "lc_safe": ("lc_safe_open", [""]),
    "lc_gun": ("lc_gun_open", [""]),
    "lc_file": ("lc_file_open", [""]),
    "lc_cash": ("lc_cash_open", [""]),
    "lc_aid": ("lc_aid_open", [""]),
    "lc_cell": ("lc_cell_open", [""]),   # встраиваемая в стену ячейка: только в каталоге, ни к какому виду не подключена
}
SUPPORT_MODELS = {"lc_cash"}   # стоят только на опоре (прилавок, стол): подгонка без опоры оставляет бокс (Balance.LOOT_SUPPORT_RANGE)
WALL_MODELS = {"lc_aid"}   # висят на стене: подгонка ищет стену и высоту Balance.LOOT_WALL_HEIGHT
# поверхность попаданий и шагов (Surfaces): металл, дерево, картон, ткань, пластик
SURFACE = {"it_ammo": "wood", "it_zip": "wood", "it_trunk": "metal", "it_toolbox": "metal", "it_suitcase": "plastic",
           "it_duffel": "fabric", "it_carton": "cardboard", "it_pc": "plastic", "lc_medbag": "fabric", "lc_safe": "metal",
           "lc_gun": "metal", "lc_file": "metal", "lc_cash": "plastic", "lc_aid": "metal", "lc_cell": "metal"}
LOD_DIST = 14.0   # дальше — узлы *_lod1 (≈ ¼ треугольников)
# вид -> модель по умолчанию ("" — модели пока нет)
KINDS = {
    "weapon_crate": "it_zip", "ammo_crate": "it_ammo", "weapon_locker": "lc_gun", "medbag": "lc_medbag", "med_cabinet": "lc_aid",
    "toolbox": "it_toolbox", "car_trunk": "", "duffel": "it_duffel", "suitcase": "it_suitcase", "jacket": "",
    "safe": "lc_safe", "pc_block": "it_pc", "tech_shelf": "", "filing": "lc_file", "ration_crate": "", "carton": "it_carton",
    "locker": "it_trunk", "register": "lc_cash",
}


LOOT_INDEX = json.load(open(ROOT / "assets/models/loot_containers/loot_containers_models.json", encoding="utf8"))


def box(model: str, index: dict = INDEX) -> dict:
    a = index[model]["aabb"]
    return {"center": [round(v, 4) for v in a["center"]], "size": [round(v, 4) for v in a["size"]]}


models = {}
for m, (op, variants) in MODELS.items():
    models[m] = {"open": op, "variants": variants, "aabb": box(m), "open_aabb": box(op)}
for m, (op, variants) in LOOT_MODELS.items():
    models[m] = {"open": op, "variants": variants, "aabb": box(m, LOOT_INDEX), "open_aabb": box(op, LOOT_INDEX), "dir": LOOT_DIR,
                 "index": LOOT_DIR + "/loot_containers_models.json", "lod": LOD_DIST}
    if m in WALL_MODELS:
        models[m]["wall"] = True
    if m in SUPPORT_MODELS:
        models[m]["support"] = True
for m in models:
    models[m]["surface"] = SURFACE[m]
out = {"version": 1, "dir": "res://assets/models/dorm/furniture", "index": "res://assets/models/dorm/furniture/furniture.json",
       "far": 45.0, "models": models, "kinds": {k: {"model": v} for k, v in KINDS.items()}}
open(ROOT / "data/loot_containers.json", "w", encoding="utf8", newline="\n").write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
print("моделей %d, видов %d" % (len(models), len(KINDS)))
