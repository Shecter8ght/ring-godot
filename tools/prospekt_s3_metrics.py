#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Сводка чисел разбора расстановки (audit.json) — для сравнения «до / после». python -X utf8 tools/prospekt_s3_metrics.py [audit.json]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
p = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/screens/prospekt/props_audit/audit.json"
a = json.loads(p.read_text(encoding="utf-8"))
t, e, k, m = a["cat1_trees"], a["cat2_entrances"], a["cat3_kiosks"], a["cat4_misc"]
bc = t["by_class"]
print("items", a["items_total"], "деревьев", t["total"])
for c, n in sorted(bc.items()):
    print("  дерево:", c, n)
print("  флаги деревьев", t["flags"])
print("входов", e["total"], "перегорожено", e["blocked"], e["blocked_by_name"])
print("ларьков", k["kiosks_total"], "остановок", k["bus_stops_total"], "за остановками", k["kiosks_behind_stops_total"],
      "скоплений>=2", k["clusters_ge2_within_6m"], ">=3", k["clusters_ge3"], k["flags"])
print("кластеры>=3:", [(c["n"], c["cx"], c["cz"], c["zone"]) for c in k["clusters"] if c["n"] >= 3])
for c, v in m["по классам"].items():
    print("  мебель", c, v)
print("проезжая часть", m["on_road_total"], m["on_road_by_class"])
print("пересечений", m["overlaps_total"], m["overlaps_by_pair"])
print("в зданиях", m["inside_building_total"], "в стенах", m["in_wall_total"])
print("столбики", {kk: v for kk, v in m["bollards"].items() if kk != "chains"})
print("проход", json.dumps(a["cat5_passage"], ensure_ascii=False)[:600])
