"""Проверочные виды пожарной машины (для самопроверки формы): Workbench, материал по цвету, полость.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background <файл.blend> --python tools/fire_truck/shots.py -- \
        <папка> [вид,вид…] [коллекция: closed|open]

Виды: left right front rear top fl rr low arch_f arch_r cab rear_cl roof
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0])
VIEWS = argv[1].split(",") if len(argv) > 1 and argv[1] else []
WHICH = argv[2] if len(argv) > 2 else "closed"
OUT.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
vl = bpy.context.view_layer
for lc in vl.layer_collection.children:
    want = (lc.name == "Целая") == (WHICH == "closed")
    lc.exclude = not want
    lc.hide_viewport = False

scene.render.engine = "BLENDER_WORKBENCH"
sh = scene.display.shading
sh.light = "STUDIO"
sh.color_type = "MATERIAL"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.show_shadows = True
sh.show_object_outline = False
scene.display.render_aa = "16"
scene.render.film_transparent = False
scene.world = scene.world or bpy.data.worlds.new("w")
scene.render.resolution_x, scene.render.resolution_y = 1800, 1100

# Y = 0 — середина базы; машина от −3,4 до 4,1 по Y
CENTER = Vector((0.0, 0.35, 1.55))
ORTHO = {
    "left": ((12, 0.35, 1.55), 8.4), "right": ((-12, 0.35, 1.55), 8.4),
    "front": ((0, -12, 1.7), 5.9), "rear": ((0, 12, 1.7), 5.9), "top": ((0, 0.35, 14), 8.4),
}
PERSP = {
    "fl": ((7.5, -8.5, 3.2), (0, 0.2, 1.4), 40), "rr": ((-7.0, 9.5, 3.4), (0, 0.6, 1.4), 40),
    "low": ((6.0, -2.0, 0.35), (0, 0.6, 0.7), 55), "arch_f": ((2.6, -2.4, 0.9), (1.0, -2.1, 0.6), 50),
    "arch_r": ((2.8, 1.6, 0.9), (1.0, 2.1, 0.65), 50), "cab": ((2.8, -5.6, 2.6), (0.2, -2.6, 1.8), 45),
    "rear_cl": ((-1.8, 7.4, 1.9), (0, 3.8, 1.4), 45), "roof": ((3.5, -3.0, 5.5), (0, 0.8, 3.1), 45),
    "bumper": ((1.2, -5.2, 1.1), (0.3, -3.3, 0.85), 40), "mirror": ((2.6, -4.4, 2.6), (1.35, -2.75, 2.35), 35),
    "intake": ((2.9, -0.9, 2.6), (1.25, -1.45, 2.3), 40), "shutter": ((3.0, 2.3, 1.2), (1.25, 2.6, 1.3), 45),
    "wheel_r": ((2.6, 2.1, 0.7), (1.0, 2.1, 0.55), 45), "locker": ((4.2, 0.4, 2.0), (1.0, 1.2, 1.9), 50),
    "door_in": ((3.1, -1.55, 2.25), (0.55, -2.35, 1.80), 55), "cap": ((2.4, -5.0, 3.9), (0.3, -2.6, 3.05), 35),
    "bumper34": ((2.6, -5.4, 1.3), (0.6, -3.3, 0.70), 35),
    "monitor": ((1.6, -2.4, 3.9), (0.25, -1.2, 3.25), 40), "ladder": ((-1.9, -1.9, 3.85), (-0.62, -0.25, 3.30), 38),
    "ladder_r": ((-1.9, 5.3, 3.9), (-0.62, 3.40, 3.30), 38),
    "pump": ((0.75, 5.0, 1.05), (0.0, 3.82, 0.72), 34), "tow": ((0.9, 4.9, 0.20), (0.0, 3.95, 0.45), 34), "dash": ((0.75, -1.85, 2.30), (0.40, -2.90, 1.85), 70),
    "ws_in": ((1.6, -5.2, 2.45), (0.2, -2.6, 2.0), 35), "crew_in": ((3.2, -0.2, 2.2), (0.4, -0.75, 1.75), 55), "rear_low": ((0.8, 6.0, 0.9), (0, 3.9, 0.7), 45),
}


def camera(name: str):
    cam_data = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_data)
    scene.collection.objects.link(cam)
    return cam


def aim(cam, loc, target) -> None:
    cam.location = Vector(loc)
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


views = VIEWS or list(ORTHO) + list(PERSP)
for v in views:
    cam = camera("cam_" + v)
    if v in ORTHO:
        loc, scale = ORTHO[v]
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = scale
        target = (loc[0] if v in ("front", "rear") else 0, 0.35 if v not in ("front", "rear") else 0, 1.55)
        if v == "top":
            target = (0, 0.35, 0)
        aim(cam, loc, (target[0] if v != "front" and v != "rear" else 0, target[1], target[2]))
        if v in ("left", "right"):
            aim(cam, loc, (0, loc[1], loc[2]))
        if v in ("front", "rear"):
            aim(cam, loc, (0, 0, loc[2]))
    else:
        loc, target, lens_deg = PERSP[v]
        cam.data.type = "PERSP"
        cam.data.angle = math.radians(lens_deg)
        aim(cam, loc, target)
    cam.data.clip_end = 200
    scene.camera = cam
    scene.render.filepath = str(OUT / f"{v}_{WHICH}.png")
    bpy.ops.render.render(write_still=True)
    print("снимок:", scene.render.filepath, flush=True)
