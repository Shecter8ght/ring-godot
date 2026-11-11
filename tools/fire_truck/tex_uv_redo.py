"""Пожарная АЦ: переразвернуть один набор в готовом файле развёртки, остальные наборы не трогая.

Детали из списка `--fresh` берутся заново из принятой формы (tex_sets.SOURCE) — их сетка испорчена (грань через проём
после деления рёбер сеткой); затем для набора те же шаги, что в tex_uv.py: деление длинных рёбер (без многоугольников),
перетриангуляция граней через проём, классы видимости лучами, острова, развёртка, укладка, проверка растром.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/tex_uv_redo.py -- <набор> [--fresh деталь,деталь]
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import bpy  # noqa: E402

import fix_ngons  # noqa: E402
import tex_sets as T  # noqa: E402
import tex_uv as U  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402


def fresh(names):
    """Сетки деталей из принятой формы — вместо испорченных (копии с той же сеткой получают новую тоже)."""
    with bpy.data.libraries.load(T.SOURCE, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    for ob_new in dst.objects:
        if ob_new is None:
            continue
        name = ob_new.name.rsplit(".", 1)[0] if ob_new.name not in names else ob_new.name
        old = bpy.data.objects.get(name)
        if old is None:
            continue
        me_old = old.data
        mat = me_old.materials[0] if me_old.materials else None
        me = ob_new.data
        me.materials.clear()
        if mat:
            me.materials.append(mat)
        for o in [o for o in bpy.data.objects if o.data is me_old]:
            o.data = me
        bpy.data.objects.remove(ob_new)
        U.log(f"  {name}: сетка из принятой формы ({len(me.polygons)} граней)")


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    st = a[0]
    names = a[a.index("--fresh") + 1].split(",") if "--fresh" in a else []
    t0 = time.time()
    if names:
        fresh(names)
    objs = [o for o in bpy.data.objects if o.type == "MESH" and o.get("ft_set") == st]
    U.log(f"деталей набора {st}: {len(objs)}; рёбер поделено {U.subdivide_long(objs)}; "
          f"через проём {fix_ngons.fix(objs, verbose=False)}")
    um, seen = [], set()
    for o in objs:
        if o.data not in seen:
            seen.add(o.data)
            um.append(o)
    cls = U.visibility(um)
    kept, total = U.unwrap(um)
    classes = [cls.get(o.data.name) if o.data.name in cls else None for o in um]
    classes = [c if c is not None else __import__("numpy").full(len(o.data.polygons), kit_uv.VISIBLE, "int32")
               for c, o in zip(classes, um)]
    res, title = T.SETS[st]
    rep = kit_uv.layout(um, res, uv=T.UV, classes=classes, stack=False, margin=T.PADDING_PX, group_margin=6,
                        log=lambda *x: U.log("  ", *x))
    ver = kit_uv.verify(um, res, uv=T.UV, margin=T.PADDING_PX, group_margin=6)
    entry = dict(title=title, res=res, meshes=len(um), islands=rep.get("islands"), fill=rep.get("fill"),
                 px_mm=rep.get("px_mm"), projection_kept=f"{kept}/{total}", verify=ver, sec=round(time.time() - t0))
    U.log("SET", st, json.dumps(entry, ensure_ascii=False, default=str))
    path = f"{T.WORK}/uv_report.json"
    rep_all = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    rep_all[st] = entry
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep_all, f, ensure_ascii=False, indent=1, default=str)
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
    U.log("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
