"""Электрика общежития, текстуры: тот же конвейер Painter, что у мебели (furniture_sp.py) — свои папки, спецификация,
наборы и пары слотов.

  python -X utf8 tools/dorm_modules/electrics_sp.py projects|stack|variants [набор …]

Свой экземпляр Painter (папка заданий _asset_src/dorm_electrics/sp_jobs), проекты 2K, стек отделок по finish-spec.json
электрики, печать слоем (electrics_prints.py), варианты — корпус и отражатель меняются парой.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "dorm_electrics" / "sp_jobs"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import furniture_sp as F  # noqa: E402

F.SRC = ROOT / "_asset_src" / "dorm_electrics"
F.LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Electrics")
F.SPEC = F.LIB / "finish-spec.json"
F.RES = 2048
F.RES_ITEM = {}
F.PAIRS = {"housing": "reflector"}
# набор: наибольший размер, мм (трёхпроекционные узоры, плотность развёртки — оценка по нему)
F.ITEMS = {"el_tube": 1214, "el_bulb": 240, "el_lsp": 1240, "el_lpo": 1290, "el_plafond": 250, "el_pendant": 700,
           "el_switch_round": 60, "el_socket_round": 60, "el_switch_white": 80, "el_socket_white": 80, "el_box": 95,
           "el_wire_flat": 1900, "el_wire_twisted": 1600}

if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    todo = rest or list(F.ITEMS)
    {"projects": F.projects, "stack": F.stack, "variants": F.variants, "wear": F.wear}[mode](todo)
