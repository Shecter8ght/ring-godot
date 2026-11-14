"""«Частокол», текстуры: опись принятой формы — объекты, коллекции, сетки (общие у экземпляров ленты), треугольники,
габариты и площадь поверхности; JSON для разбивки на наборы текстур (tex_sets.py).

    blender -b "<Частокол_геометрия_v03.blend>" --factory-startup --python tools/pkp/tex_dump.py -- <out.json>
"""
import json
import sys

import bpy
import numpy as np

out = sys.argv[sys.argv.index("--") + 1]
rows = []
for ob in bpy.data.objects:
    rec = {"name": ob.name, "type": ob.type, "parent": ob.parent.name if ob.parent else None,
           "collections": [c.name for c in ob.users_collection], "hidden": ob.hide_get() if ob.name in bpy.context.view_layer.objects else None,
           "hide_render": ob.hide_render}
    if ob.type == "MESH":
        me = ob.data
        rec["mesh"] = me.name
        rec["mesh_users"] = me.users
        n = len(me.polygons)
        rec["faces"] = n
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if len(co):
            rec["bbox_local"] = [co.min(0).round(2).tolist(), co.max(0).round(2).tolist()]
        ar = np.empty(n, np.float32)
        me.polygons.foreach_get("area", ar)
        rec["area_mm2"] = float(ar.sum())
        rec["uv_layers"] = [u.name for u in me.uv_layers]
        rec["materials"] = [m.name if m else None for m in me.materials]
        rec["scale"] = list(ob.matrix_world.to_scale())
    rows.append(rec)
cols = {c.name: {"objects": len(c.objects), "children": [x.name for x in c.children],
                 "exclude": None} for c in bpy.data.collections}


def walk(lc):
    if lc.collection.name in cols:
        cols[lc.collection.name]["exclude"] = lc.exclude
        cols[lc.collection.name]["hide_viewport"] = lc.hide_viewport
    for ch in lc.children:
        walk(ch)


walk(bpy.context.view_layer.layer_collection)
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    json.dump({"file": bpy.data.filepath, "unit_scale": bpy.context.scene.unit_settings.scale_length,
               "objects": rows, "collections": cols}, fh, ensure_ascii=False, indent=1)
print("DUMP", len(rows), "objects")
