"""ВЕРАС-54 v14, текстуры: опись принятой формы (по образцу tools/pkp/tex_dump.py) — объекты, родители, коллекции,
сетки (общие у экземпляров), материалы-заглушки с площадью по материалам, треугольники, габариты в мировых осях (мм),
площадь поверхности (мм²), подвижность (приводы рига и родители-подвижные), симметрия относительно плоскости XZ.
JSON — для разбивки на наборы текстур (tex_sets.py).

    blender -b "<ВЕРАС-54_геометрия_v14_04.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_dump.py -- <out.json>
"""
import json
import sys

import bpy
import numpy as np

out = sys.argv[sys.argv.index("--") + 1]

# подвижные: у кого приводы на трансформах
moving = {}
for ob in bpy.data.objects:
    ad = ob.animation_data
    if ad and ad.drivers:
        props = sorted({f"{d.data_path}[{d.array_index}]" for d in ad.drivers})
        moving[ob.name] = props


def mover_of(ob):
    """Ближайший подвижный предок (или сам) — деталь едет вместе с ним."""
    p = ob
    while p is not None:
        if p.name in moving:
            return p.name
        p = p.parent
    return None


rows = []
tot_tris = 0
for ob in bpy.data.objects:
    rec = {"name": ob.name, "type": ob.type, "parent": ob.parent.name if ob.parent else None,
           "collections": [c.name for c in ob.users_collection],
           "hidden": ob.hide_get() if ob.name in bpy.context.view_layer.objects else None,
           "hide_render": ob.hide_render, "drivers": moving.get(ob.name), "mover": mover_of(ob)}
    if ob.type == "MESH":
        me = ob.data
        rec["mesh"] = me.name
        rec["mesh_users"] = me.users
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        rec["tris"] = nt
        rec["faces"] = len(me.polygons)
        tot_tris += nt
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_total", lt)
        rec["ngons"] = int((lt > 4).sum())
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(ob.matrix_world, np.float64)
        cw = co @ mw[:3, :3].T + mw[:3, 3]
        if len(cw):
            lo, hi = cw.min(0) * 1000, cw.max(0) * 1000
            rec["bbox_mm"] = [lo.round(2).tolist(), hi.round(2).tolist()]
            rec["size_mm"] = (hi - lo).round(2).tolist()
            # симметрия по Y: габарит отражается сам в себя (вершины точнее не сравнить — сетки OpenVDB несимметричны)
            rec["sym_y"] = bool(abs(lo[1] + hi[1]) < 0.02 * max(hi[1] - lo[1], 1e-6) + 0.05)
        ar = np.empty(len(me.polygons), np.float64)
        me.polygons.foreach_get("area", ar)
        s = float(np.prod(np.abs(np.array(ob.matrix_world.to_scale()))) ** (2.0 / 3.0))
        rec["area_mm2"] = float(ar.sum()) * s * 1e6
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("material_index", mi)
        mats = [m.name if m else None for m in me.materials]
        rec["materials"] = mats
        rec["area_by_material_mm2"] = {str(mats[i] if i < len(mats) else i): round(float(ar[mi == i].sum()) * s * 1e6, 1)
                                       for i in np.unique(mi)}
        rec["uv_layers"] = [u.name for u in me.uv_layers]
        rec["scale"] = [round(v, 5) for v in ob.matrix_world.to_scale()]
    rows.append(rec)
cols = {c.name: {"objects": [o.name for o in c.objects], "children": [x.name for x in c.children],
                 "exclude": None} for c in bpy.data.collections}


def walk(lc):
    if lc.collection.name in cols:
        cols[lc.collection.name]["exclude"] = lc.exclude
        cols[lc.collection.name]["hide_viewport"] = lc.hide_viewport
    for ch in lc.children:
        walk(ch)


walk(bpy.context.view_layer.layer_collection)
ctl = bpy.data.objects.get("VERAS54_Controls")
controls = {k: float(ctl[k]) for k in ctl.keys() if isinstance(ctl[k], (int, float))} if ctl else {}
with open(out, "w", encoding="utf-8", newline="\n") as fh:
    json.dump({"file": bpy.data.filepath, "unit_scale": bpy.context.scene.unit_settings.scale_length,
               "tris_total": tot_tris, "controls": controls, "objects": rows, "collections": cols},
              fh, ensure_ascii=False, indent=1)
print("DUMP", len(rows), "objects", tot_tris, "tris")
