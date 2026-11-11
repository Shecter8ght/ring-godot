# -*- coding: utf-8 -*-
"""План «Проспекта» после переноса улиц в узлы (tools/prospekt_streets_to_nodes.tscn): покрытия, вырезы, плиты, стены,
коробки, колонны, лестницы, пандусы, балки, фонари, надписи — пусто, plan.lists_from_nodes — их имена (улицы — узлы
PlanPiece сцены prospekt_study.tscn, Landscape/Улицы). Места лута остаются в плане. Формат файла — как у
tools/build_prospekt.py.

    python -X utf8 tools/prospekt_streets_json.py
"""
import json
import re
from pathlib import Path

LISTS = ["surfaces", "ground_holes", "walk_holes", "slabs", "walls", "boxes", "columns", "stairs", "ramps", "beams",
         "lamps", "signs"]
PATH = Path(__file__).resolve().parent.parent / "data" / "blockouts" / "prospekt.json"
plan = json.loads(PATH.read_text(encoding="utf-8"))
for key in LISTS:
    plan[key] = []
plan["lists_from_nodes"] = LISTS
text = json.dumps(plan, ensure_ascii=False, indent=1)
text = re.sub(r"\[\s+((?:-?[\d.]+,\s+)*-?[\d.]+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
text = re.sub(r"\[\s+(\"[A-Za-z_0-9]+\",(?:\s+-?[\d.]+,?)+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
PATH.write_text(text + "\n", encoding="utf-8", newline="\n")
print("prospekt.json: улицы — узлами (lists_from_nodes: %d списков)" % len(LISTS))
