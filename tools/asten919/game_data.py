"""АСТЕН-919 в данные игры: запись пистолета wpn_hg_02 (id прежний ради сохранений) — модель, название, ход механики.

python -X utf8 tools/asten919/game_data.py
Пишет в data/weapons.json: weapons.wpn_hg_02 (название и код — вымышленные, как гравировка модели; asset — новая
модель; риг — ход затвора, углы спуска и рычага задержки, путь магазина по оси рукояти из размеров построителя),
magazines.mag_919_17 (название, модель-предмет). Характеристики, цена, крепления, хваты рук и места гравировки не
меняются. Повторный запуск перезаписывает те же ключи. Прежняя модель glock17.glb удалена из игры (2026-11-12):
ремонтные детали (data/valuable_loot_assets.json) и магазин для подсумков NPC берутся с этой модели.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dims as D  # noqa: E402

WEAPONS = ROOT / "data/weapons.json"
ASSET = "res://assets/models/weapons/asten919/"
REP = json.loads((ROOT / "assets/models/weapons/asten919/asten919.json").read_text(encoding="utf-8"))


def main():
    d = json.loads(WEAPONS.read_text(encoding="utf-8"))
    w = d["weapons"]["wpn_hg_02"]
    w["name"] = "АСТЕН-919"
    w["code"] = "АСТЕН"
    wp = w["weapon"]
    wp["asset"] = ASSET + "asten919.gltf"
    rig = wp["rig"]
    a = math.radians(D.GRIP_DEG)
    out = D.MAG_OUT * 0.001
    rig["slide_travel_m"] = round(D.SLIDE_TRAVEL * 0.001, 4)
    rig["trigger_angle_deg"] = float(D.TRIGGER_DEG)          # вокруг +X игры (ось спуска поперёк), назад
    rig["trigger_axis"] = [1, 0, 0]
    rig["slide_stop_angle_deg"] = float(D.STOP_UP_DEG)        # площадка рычага позади оси — вверх
    rig["mag_catch_angle_deg"] = 0.0
    # магазин выходит вдоль оси рукояти: вниз и назад (оси игры: +Y верх, +Z дуло)
    rig["magazine_out_m"] = [0, round(-math.cos(a) * out, 4), round(-math.sin(a) * out, 4)]
    m = d["magazines"]["mag_919_17"]
    m["name"] = "Магазин АСТЕН 9×19 на 17"
    m["model"] = ASSET + "asten919_mag.gltf"
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("ASTEN_DATA", w["name"], wp["asset"], {k: rig[k] for k in ("slide_travel_m", "trigger_angle_deg",
                                                                    "slide_stop_angle_deg", "magazine_out_m")},
          "метки", REP["markers_game_m"])


if __name__ == "__main__":
    main()
