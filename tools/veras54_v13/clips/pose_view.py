"""Кадры клипа для собственной проверки позы — Workbench (светлая студия, без материалов): видно, где пальцы и что
они задевают. Листы владельцу не собираются.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup <клип .blend> --python tools/veras54_v13/clips/pose_view.py
    -- <префикс> <кадры через запятую> focus=x:y:z [виды через запятую: right,top,low,back,fps]
focus — в осях VERAS54 (м). Камера смотрит на focus с расстояния ~0,3 м.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index("--") + 1:]
prefix = Path(args[0])
frames = [int(f) for f in args[1].split(",")]
focus_l = Vector([float(v) for v in next(a for a in args if a.startswith("focus="))[6:].split(":")])
views = next((a for a in args[2:] if not a.startswith("focus=")), "right,top,low").split(",")
root = bpy.data.objects["VERAS54"]
for c in bpy.data.collections:
    if "Suppressor" in c.name:
        c.hide_render = True
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "OBJECT"
sh.show_cavity = True
sh.cavity_type = "BOTH"
sh.show_shadows = True
sc.render.resolution_x, sc.render.resolution_y = 960, 640
sc.render.film_transparent = False
for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.color = (0.95, 0.75, 0.55, 1) if ob.name.startswith("FPS_Arms") else ((0.9, 0.2, 0.2, 1) if ob.name.startswith("Selector") else (0.55, 0.58, 0.62, 1))
# смещения камеры в осях VERAS54 (дуло +X, влево +Y, вверх +Z)
OFFS = {"right": Vector((0.02, -0.30, 0.03)), "top": Vector((0.0, -0.12, 0.28)), "low": Vector((0.05, -0.25, -0.18)),
        "back": Vector((-0.28, -0.12, 0.08)), "front": Vector((0.30, -0.15, 0.05)),
        "left": Vector((0.02, 0.30, 0.04)), "left_high": Vector((-0.10, 0.22, 0.16)),
        "left_graze": Vector((0.16, 0.10, 0.03)), "right_close": Vector((0.02, -0.16, 0.04)), "right_front": Vector((0.14, -0.14, 0.02)),
        "right_back": Vector((-0.12, -0.14, 0.05))}
cam = bpy.data.objects.new("chk_pose_cam", bpy.data.cameras.new("chk_pose_cam"))
sc.collection.objects.link(cam)
cam.data.lens = 35
cam.data.clip_start = 0.005
prefix.parent.mkdir(parents=True, exist_ok=True)
for f in frames:
    sc.frame_set(f)
    bpy.context.view_layer.update()
    focus = root.matrix_world @ focus_l
    for v in views:
        if v == "fps":
            sc.camera = bpy.data.objects["FPS • Camera"]
        else:
            off = root.matrix_world.to_3x3() @ OFFS[v]
            cam.location = focus + off
            z = off.normalized()
            up = root.matrix_world.to_3x3() @ Vector((0, 0, 1))
            if abs(z.dot(up)) > 0.95:
                up = root.matrix_world.to_3x3() @ Vector((1, 0, 0))
            x = up.cross(z).normalized()
            m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
            m.translation = cam.location
            cam.matrix_world = m
            sc.camera = cam
        sc.render.filepath = str(prefix) + f"_{v}_{f:03d}.png"
        bpy.ops.render.render(write_still=True)
print("POSE_VIEW_DONE", prefix)
