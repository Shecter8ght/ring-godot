"""Транспорт «Проспекта»: проверочные снимки формы (Workbench, нейтральный свет) — для себя, не для показа.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/review.py -- \
        <файл.blend> <папка> <префикс> [glass] имя:x,y,z:цель_x,цель_y,цель_z[:фокус_мм] ...

glass — стёкла тёмные почти непрозрачные (Workbench иначе почти не рисует прозрачные).
Сетка земли под машинами, чтобы читалась посадка.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
if argv[0].lower().endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=argv[0])
else:
    # несколько .ply через «;» — рядом вдоль X со сдвигом 4 м (черновые объёмы)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for i, path in enumerate(argv[0].split(";")):
        bpy.ops.wm.ply_import(filepath=path)
        for ob in bpy.context.selected_objects:
            ob.location.x += i * 4.0
            for p in ob.data.polygons:
                p.use_smooth = True
out, prefix = Path(argv[1]), argv[2]
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_specular_highlight = True
sh.show_shadows = False
sh.show_cavity = True
sh.cavity_type = "WORLD"
scene.display.render_aa = "16"
scene.render.resolution_x, scene.render.resolution_y = 1500, 950
mat = bpy.data.materials.new("_ground")
mat.diffuse_color = (0.30, 0.30, 0.29, 1)
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.16, 0.155, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
bpy.ops.mesh.primitive_plane_add(size=40, location=(5, 0, 0))
bpy.context.active_object.data.materials.append(mat)
cam_data = bpy.data.cameras.new("_cam")
cam = bpy.data.objects.new("_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
for spec in argv[3:]:
    if spec == "glass":
        for m in bpy.data.materials:
            if "glass" in m.name or "lamp_red" in m.name:
                c = list(m.diffuse_color)
                m.diffuse_color = (c[0], c[1], c[2], 0.82)
        continue
    if spec == "eevee":
        scene.render.engine = "BLENDER_EEVEE"
        world = scene.world or bpy.data.worlds.new("w")
        scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        bg.inputs[0].default_value = (0.50, 0.56, 0.66, 1)
        bg.inputs[1].default_value = 0.45
        sun = bpy.data.objects.new("_sun", bpy.data.lights.new("_sun", "SUN"))
        sun.data.energy = 2.2
        sun.data.angle = 0.05
        sun.rotation_euler = (0.85, 0.25, 0.9)
        scene.collection.objects.link(sun)
        scene.view_settings.view_transform = "AgX"
        continue
    if spec.startswith("hide:"):
        for c in bpy.data.collections:
            if c.name == spec[5:]:
                c.hide_render = True
        continue
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
