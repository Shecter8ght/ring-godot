"""Купе Ильи: крупные планы деталей (Workbench, нейтральный серый).

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/close_views.py -- \
        <файл.blend> <папка> <префикс> [rot:Объект:ось:рад] [show:Коллекция] [hide:Коллекция]         имя:x,y,z:цель_x,цель_y,цель_z[:фокус_мм] ...

rot — повернуть объект (например rot:Hood_Hinge:x:-0.87 — капот открыт), show/hide — состояния.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
out, prefix = Path(argv[1]), argv[2]
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_specular_highlight = True
scene.display.render_aa = "16"
cam_data = bpy.data.cameras.new("_close_cam")
cam = bpy.data.objects.new("_close_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
shots = []
for spec in argv[3:]:
    kind = spec.split(":")[0]
    if kind == "rot":
        _, obn, ax, val = spec.split(":")
        ob = bpy.data.objects[obn]
        ob.rotation_euler["xyz".index(ax)] = float(val)
    elif kind in ("show", "hide"):
        c = bpy.data.collections[spec.split(":")[1]]
        c.hide_render = kind == "hide"
        for ob in c.all_objects:
            if ob is not None:
                ob.hide_render = kind == "hide"
    else:
        shots.append(spec)
for spec in shots:
    parts = spec.split(":")
    name = parts[0]
    loc = Vector([float(v) for v in parts[1].split(",")])
    tgt = Vector([float(v) for v in parts[2].split(",")])
    cam_data.lens = float(parts[3]) if len(parts) > 3 else 50.0
    cam_data.clip_start = 0.01
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / f"{prefix}_{name}.png")
    bpy.ops.render.render(write_still=True)
print("готово:", out)
