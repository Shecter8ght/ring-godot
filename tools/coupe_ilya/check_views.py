"""Купе Ильи: проверочные виды формы в Blender (нейтральный серый, Workbench).

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/check_views.py -- \
        <модель.ply|.blend> <папка снимков> [префикс]

Ортогональные виды сбоку/спереди/сзади/сверху с известным масштабом (для наложения чертежа —
overlay.py) и два вида 3/4 в перспективе. Рядом пишется views.json: центр и ширина каждого
ортогонального кадра в метрах.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC = Path(argv[0])
OUT = Path(argv[1])
PREFIX = argv[2] if len(argv) > 2 else "check"
OUT.mkdir(parents=True, exist_ok=True)

if SRC.suffix.lower() == ".blend":
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.ply_import(filepath=str(SRC))
    for ob in bpy.context.selected_objects:
        for p in ob.data.polygons:
            p.use_smooth = True

scene = bpy.context.scene
scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "SINGLE"
sh.single_color = (0.62, 0.62, 0.62)
sh.show_cavity = False
sh.show_shadows = False
sh.show_specular_highlight = True
scene.display.render_aa = "16"
scene.render.film_transparent = False
world = bpy.data.worlds.new("check") if scene.world is None else scene.world
scene.world = world

# Земля — тонкая тёмная плита под машиной, чтобы читалась посадка
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -0.001))
ground = bpy.context.active_object
ground.name = "_check_ground"
mat = bpy.data.materials.new("_check_ground")
mat.diffuse_color = (0.25, 0.25, 0.25, 1)
ground.data.materials.append(mat)
sh.color_type = "MATERIAL"
for ob in scene.objects:
    if ob.type == "MESH" and ob is not ground and not ob.data.materials:
        m = bpy.data.materials.get("_check_grey") or bpy.data.materials.new("_check_grey")
        m.diffuse_color = (0.62, 0.62, 0.62, 1)
        ob.data.materials.append(m)

cam_data = bpy.data.cameras.new("_check_cam")
cam = bpy.data.objects.new("_check_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

views: dict[str, dict] = {}


def shot(name: str, loc: tuple, look_at: tuple, ortho: float | None, res: tuple[int, int], lens: float = 50.0,
         roll: float = 0.0) -> None:
    cam.location = Vector(loc)
    d = Vector(look_at) - Vector(loc)
    if abs(d.normalized().z) > 0.999:
        # Сверху: кадр развёрнут так, что вправо — +Y (корма), вверх — −X (правый борт)
        cam.rotation_euler = (0.0, 0.0, math.pi / 2)
    else:
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho
    else:
        cam_data.type = "PERSP"
        cam_data.lens = lens
    cam_data.clip_end = 100
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(OUT / f"{PREFIX}_{name}.png")
    bpy.ops.render.render(write_still=True)
    if ortho:
        views[name] = {"center": list(look_at), "width_m": ortho, "res": list(res)}


# Ортогональные: сбоку слева (+X), спереди (−Y), сзади (+Y), сверху
shot("side", (8, 0.09, 0.72), (0, 0.09, 0.72), 5.6, (1800, 700))
shot("front", (0, -8, 0.72), (0, 0, 0.72), 2.4, (1000, 700))
shot("rear", (0, 8, 0.72), (0, 0, 0.72), 2.4, (1000, 700))
shot("top", (0, 0.09, 8), (0, 0.09, 0), 5.6, (1800, 800))  # вправо +Y, вверх −X
# Перспектива 3/4: спереди слева и сзади справа, на высоте глаз
shot("34front", (4.6, -5.2, 1.55), (0, -0.2, 0.62), None, (1600, 1000), 50)
shot("34rear", (-4.4, 5.4, 1.65), (0, 0.3, 0.62), None, (1600, 1000), 50)

(OUT / f"{PREFIX}_views.json").write_text(json.dumps(views, indent=1), encoding="utf-8")
print("готово:", OUT)
