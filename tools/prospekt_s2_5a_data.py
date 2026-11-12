"""«Проспект», вторая очередь, этап 5а — данные плана (вызывается из tools/prospekt_patch.py): маршрут ring_deck под пять маршей башен схода.

Правит текстом data/blockouts/prospekt.json (повтор не дублирует).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def plan_data(p=None) -> None:
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = open(path, encoding="utf-8", newline="").read()
    pts = p.ring_route
    body = ",\n".join("    [%s, %s]" % (repr(float(x)), repr(float(z))) for x, z in pts)
    pat = re.compile(r'("id": "ring_deck",\n   "label": "[^"]*",\n   "max_open_m": 0\.0,\n   "points": \[\n)(.*?)(\n   \])', re.S)
    m = pat.search(text)
    if not m:
        raise SystemExit("prospekt.json: нет маршрута ring_deck")
    text = text[:m.start(2)] + body + text[m.end(2):]
    open(path, "w", encoding="utf-8", newline="").write(text)
    if p is not None:
        print("  данные: маршрут ring_deck — %d точек (пять маршей в башнях схода)" % len(pts))
