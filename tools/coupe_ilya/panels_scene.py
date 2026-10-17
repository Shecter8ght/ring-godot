"""Купе Ильи: сцена панелей — OBJ из panels.py, черновой кузов полупрозрачно для сверки, колёса.

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/panels_scene.py -- \
        <панели.obj> <черновик.blend> <выход.blend>
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
OBJ, BLOCKOUT, OUT = Path(argv[0]), Path(argv[1]), Path(argv[2])

bpy.ops.wm.open_mainfile(filepath=str(BLOCKOUT))
body = bpy.data.objects.get("Body_blockout")
if body is not None:
    # Черновик — тёмная подложка: видно, где панели легли на объём
    ghost = bpy.data.materials.new("blockout_ghost")
    ghost.diffuse_color = (0.18, 0.2, 0.24, 1.0)
    body.data.materials.clear()
    body.data.materials.append(ghost)
    # Утопить на 8 мм, чтобы панели не мерцали на той же поверхности
    disp = body.modifiers.new("inset", "DISPLACE")
    disp.strength = -0.008
    disp.mid_level = 0.0

before = set(bpy.data.objects)
bpy.ops.wm.obj_import(filepath=str(OBJ), forward_axis="Y", up_axis="Z")
paint = bpy.data.materials.new("paint_check")
paint.diffuse_color = (0.62, 0.63, 0.65, 1.0)
col = bpy.data.collections.new("Panels")
bpy.context.scene.collection.children.link(col)
for ob in set(bpy.data.objects) - before:
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)
    for p in ob.data.polygons:
        p.use_smooth = True
    ob.data.materials.clear()
    ob.data.materials.append(paint)

bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("сохранено:", OUT)
