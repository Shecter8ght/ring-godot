# -*- coding: utf-8 -*-
"""План «Проспекта» после переноса наполнения в узлы (tools/prospekt_items_to_nodes.tscn): filler.items — пусто,
filler.from_nodes — да (вещи — узлы PropSpot сцены prospekt_study.tscn). Формат файла — как у tools/build_prospekt.py.

    python -X utf8 tools/prospekt_items_json.py
"""
import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "data" / "blockouts" / "prospekt.json"
plan = json.loads(PATH.read_text(encoding="utf-8"))
plan["filler"]["items"] = []
plan["filler"]["from_nodes"] = True
plan["items_count"] = 0
text = json.dumps(plan, ensure_ascii=False, indent=1)
text = re.sub(r"\[\s+((?:-?[\d.]+,\s+)*-?[\d.]+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
text = re.sub(r"\[\s+(\"[A-Za-z_0-9]+\",(?:\s+-?[\d.]+,?)+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
PATH.write_text(text + "\n", encoding="utf-8", newline="\n")
print("prospekt.json: вещи наполнения — узлами (filler.from_nodes)")
