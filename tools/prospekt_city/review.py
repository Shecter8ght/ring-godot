"""«Проспект», ограждения и город: проверочные снимки формы (для сверки, не презентация).

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_city/review.py -- \
        <файл.blend> <папка> <префикс> [eevee] [hide:Коллекция] [solo:Коллекция] имя:x,y,z:цель_x,цель_y,цель_z[:фокус_мм] ...

Workbench с полостями (cavity) по умолчанию, eevee — солнце и небо. Под предметами — земля.
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
sh.show_shadows = True
sh.shadow_intensity = 0.35
sh.show_cavity = True
sh.cavity_type = "BOTH"
scene.display.render_aa = "16"
scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
g = bpy.data.materials.new("_ground")
g.diffuse_color = (0.24, 0.24, 0.23, 1)
g.use_nodes = True
g.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.16, 0.155, 1)
g.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
bpy.ops.mesh.primitive_plane_add(size=120, location=(10, 0, -0.001))
bpy.context.active_object.data.materials.append(g)
cam_data = bpy.data.cameras.new("_cam")
cam = bpy.data.objects.new("_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
for spec in argv[3:]:
    if spec == "eevee":
        scene.render.engine = "BLENDER_EEVEE"
        world = scene.world or bpy.data.worlds.new("w")
        scene.world = world
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        bg.inputs[0].default_value = (0.50, 0.56, 0.66, 1)
        bg.inputs[1].default_value = 0.5
        sun = bpy.data.objects.new("_sun", bpy.data.lights.new("_sun", "SUN"))
        sun.data.energy = 3.0
        sun.data.angle = 0.03
        sun.rotation_euler = (0.9, 0.2, 2.3)
        scene.collection.objects.link(sun)
        scene.view_settings.view_transform = "AgX"
        continue
    if spec.startswith("hide:"):
        for c in bpy.data.collections:
            if c.name == spec[5:]:
                c.hide_render = True
        continue
    if spec.startswith("solo:"):
        for c in bpy.data.collections:
            c.hide_render = c.name != spec[5:]
        continue
    if spec.startswith("res:"):
        w, h = spec[4:].split("x")
        scene.render.resolution_x, scene.render.resolution_y = int(w), int(h)
        continue
    parts = spec.split(":")
    name = parts[0]
    loc = Vector([float(v) for v in parts[1].split(",")])
    tgt = Vector([float(v) for v in parts[2].split(",")])
    cam_data.lens = float(parts[3]) if len(parts) > 3 else 50.0
    cam_data.clip_start = 0.01
    cam_data.clip_end = 500
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / f"{prefix}_{name}.png")
    bpy.ops.render.render(write_still=True)
print("готово:", out)
