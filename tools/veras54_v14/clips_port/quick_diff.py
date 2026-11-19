"""Быстрое сравнение действий трёх описей (генератор / до пересборки / текущий файл владельца): длина, маркеры, число ключей.

python -X utf8 tools/veras54_v14/clips_port/quick_diff.py <папка dump>
"""
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
inv = {k: json.loads((D / f"inv_{k}.json").read_text(encoding="utf-8")) for k in ("gen", "pre", "v01")}
keys = {k: json.loads((D / f"keys_{k}.json").read_text(encoding="utf-8")) for k in ("gen", "pre", "v01")}
names = sorted(set().union(*[set(inv[k]["actions"]) for k in inv]))
for n in names:
    row = []
    for k in ("gen", "pre", "v01"):
        a = inv[k]["actions"].get(n)
        if a is None:
            row.append(f"{k}: —")
            continue
        nk = sum(len(v) for v in keys[k][n].values())
        row.append(f"{k}: fc {a['fcurves']} keys {nk} last {max(a['frames']) if a['frames'] else None} marks {a['props'].get('marks', '')[:0]}")
    same = []
    for k in ("pre", "v01"):
        if n in keys[k] and n in keys["gen"]:
            same.append(f"{k}=gen" if keys[k][n] == keys["gen"][n] else f"{k}!=gen")
    if n in keys["pre"] and n in keys["v01"]:
        same.append("v01=pre" if keys["pre"][n] == keys["v01"][n] else "v01!=pre")
    if "__" in n:
        continue
    print(n, " | ".join(row), same)
# маркеры фаз
print()
for n in names:
    if "__" in n:
        continue
    m = {k: inv[k]["actions"].get(n, {}).get("props", {}).get("marks") for k in inv}
    if len(set(map(str, m.values()))) > 1:
        print("MARKS differ", n, m)
nver = {k: sum(1 for a in inv[k]["actions"] if "__" in a) for k in inv}
print("versions", nver)
