"""Клёны и тополя зоны 1: проверка сохранённых форм повторным открытием (bpy).

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/zone01_trees/check_forms.py

Каждый models/*_форма_v01.blend: экземпляры на месте, начало у земли, листва-узлы раскладывают модули (габарит с листвой
не меньше габарита ветвей), внешних файлов нет; SHA-256 файла. → checks/forms_v01_reopen.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prospekt_plants"))
import plib  # noqa: E402
import species_z1 as S  # noqa: E402

LIB = Path(os.environ.get("ZONE01_TREES_LIB", "E:/Models Blender/ENVIRONMENT/RING_Zone01_Trees"))


def main() -> None:
    out = {}
    bad = []
    seen = set()
    for path in sorted((LIB / "models").glob("*_форма_v01.blend")):
        bpy.ops.wm.open_mainfile(filepath=str(path))
        libs = [l.filepath for l in bpy.data.libraries] + [i.filepath for i in bpy.data.images if i.filepath]
        rec = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_mb=round(path.stat().st_size / 1e6, 1),
                   external=libs, plants={})
        for pl in S.PLANTS:
            emp = bpy.data.objects.get(pl.key)
            if emp is None:
                continue
            seen.add(pl.key)
            kids = list(emp.children)
            lo, hi = plib.evaluated_bounds(kids)
            wood = [o for o in kids if o.name.endswith("_ствол_и_ветви")]
            wlo, whi = plib.evaluated_bounds(wood)
            b = emp.location
            r = dict(label=pl.label, height_m=round(hi.z, 2), crown_m=[round(hi.x - lo.x, 2), round(hi.y - lo.y, 2)],
                     below_ground_m=round(lo.z, 2), origin=[round(b.x, 2), round(b.y, 2), round(b.z, 2)],
                     wood_height_m=round(whi.z, 2),
                     leaves_instanced=hi.z >= whi.z - 0.01 and (hi.x - lo.x) >= (whi.x - wlo.x) - 0.01)
            if not r["leaves_instanced"] or abs(b.z) > 1e-6:
                bad.append(pl.key)
            rec["plants"][pl.key] = r
            print("CHECK %s: %.2f м, крона %.2f × %.2f, листва %s" % (pl.key, r["height_m"], *r["crown_m"], r["leaves_instanced"]))
        if libs:
            bad.append(path.name + ": внешние файлы")
        out[path.name] = rec
    missing = [p.key for p in S.PLANTS if p.key not in seen]
    if missing:
        bad.append("нет экземпляров: " + ", ".join(missing))
    (LIB / "checks" / "forms_v01_reopen.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                                          newline="\n")
    print("CHECK итог:", "ошибки " + ", ".join(bad) if bad else "всё на месте")
    if bad:
        sys.exit(1)


main()
