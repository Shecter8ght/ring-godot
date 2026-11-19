"""Опись игровой сетки v14 (только чтение): объекты, родители, матрицы, габариты в мире, мм.

blender -b <VERAS54_Game_LP.blend> --factory-startup --python tools/veras54_v14/clips_port/list_lp.py
"""
import bpy
from mathutils import Vector

bpy.context.view_layer.update()
for o in sorted(bpy.data.objects, key=lambda o: o.name):
    bb = ""
    if o.type == "MESH":
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = [min(p[i] for p in pts) * 1000 for i in range(3)]
        hi = [max(p[i] for p in pts) * 1000 for i in range(3)]
        bb = f"tris {sum(len(p.vertices) - 2 for p in o.data.polygons)} bb {[round(v, 1) for v in lo]} .. {[round(v, 1) for v in hi]}"
    print("LP", o.name, o.type, "parent", o.parent.name if o.parent else None, o.parent_type,
          "loc", [round(v * 1000, 2) for v in o.matrix_world.translation], "hide", o.hide_viewport, o.hide_render,
          [c.name for c in o.users_collection], bb, flush=True)
for c in bpy.data.collections:
    print("COLL", c.name, len(c.objects), [ch.name for ch in c.children])
