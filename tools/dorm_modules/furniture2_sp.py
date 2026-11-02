"""Мебель общежития, партия 2 (кухня, умывальня, туалеты), текстуры: тот же конвейер Painter, что у мебели партии 1
(furniture_sp.py) — свои папки, спецификация finish-spec-2.json, наборы и пара слотов «пласть — кромка».

  python -X utf8 tools/dorm_modules/furniture2_sp.py projects|stack|variants [набор …]

Свой экземпляр Painter (папка заданий _asset_src/dorm_furniture2/sp_jobs), проекты 2K, стек отделок по finish-spec-2.json,
печать слоем (furniture2_prints.py: ободки посуды, шкалы панели плиты, марка на дверце духовки), варианты — пласти ДСП
и кромки меняются парой («орех» → «бук» → крашеные белые / голубые).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "dorm_furniture2" / "sp_jobs"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import furniture_sp as F  # noqa: E402

F.SRC = ROOT / "_asset_src" / "dorm_furniture2"
F.LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture")
F.SPEC = F.LIB / "finish-spec-2.json"
F.RES = 2048
F.RES_ITEM = {}
F.PAIRS = {"chip": "edge"}
# набор: наибольший размер, мм (трёхпроекционные узоры, плотность развёртки — оценка по нему)
F.ITEMS = {"furn_stove": 850, "furn_sink": 850, "furn_counter": 850, "furn_dining": 1200, "furn_wallcab": 800,
           "furn_dishrack": 800, "furn_pot": 280, "furn_kettle": 260, "furn_pan": 410, "furn_can": 410, "furn_bucket": 330,
           "furn_basin": 550, "furn_mirror": 600, "furn_toilet": 2100, "furn_stall": 1950}


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    todo = rest or list(F.ITEMS)
    {"projects": F.projects, "stack": F.stack, "variants": F.variants}[mode](todo)
