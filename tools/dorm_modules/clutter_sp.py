"""Мусор общежития, этап 1 текстур: проекты Painter по вещам, запекание, стек отделок по finish-spec.json, выгрузка карт —
тем же порядком и тем же экземпляром Painter, что оставленный свет (found_lights_sp.py).

  set FINISH_SP_JOBS=E:/Games/RING-godot/_asset_src/dorm_found_lights/sp_jobs
  python -X utf8 tools/dorm_modules/clutter_sp.py projects [вещь …]   # создать, запечь, сохранить .spp
  python -X utf8 tools/dorm_modules/clutter_sp.py stack [вещь …]      # стек по выбору + выгрузка карт

Плотность (пикс/мм) — замер развёртки (_asset_src/dorm_clutter/sp/density.json: площадь UV к площади сетки), габарит —
для узоров по трём проекциям. У россыпей (окурки, гильзы) габарит большой, а вещи мелкие — поэтому не оценка.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import found_lights_sp as S  # noqa: E402

S.SRC = S.ROOT / "_asset_src" / "dorm_clutter"
S.LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Clutter")
S.SPEC = S.LIB / "finish-spec.json"
_dens = json.loads((S.SRC / "sp" / "density.json").read_text(encoding="utf-8"))
S.ITEMS = {k: v["bbox_mm"] for k, v in _dens.items()}
S.PX = {k: v["px_mm"] for k, v in _dens.items()}

if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    names = rest or list(S.ITEMS)
    {"projects": S.projects, "stack": S.stack, "wear": S.wear}[mode](names)
