# Снимки формы цевья (Workbench, белая модель как в кадре ролика 1:58) — для самопроверки, не для владельца.
#   blender --background <форма.blend> --python tools/handguard_dolinskyi/preview.py -- <папка> [high|low] [вид,…]
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "C:/tmp/hg_preview"
WHICH = argv[1] if len(argv) > 1 else "high"
ONLY = set(argv[2].split(",")) if len(argv) > 2 else None
CENTER = Vector((0.088, 0.0, 0.0))
# вид: направление от центра к камере, расстояние, фокусное
VIEWS = {
    "v118": (Vector((-0.45, -0.80, 0.42)), 0.40, 50),   # 3/4 сзади сверху со стороны надписей, как кадр 1:58
    "side": (Vector((0.0, -1.0, 0.0)), 0.40, 50),       # сбоку со стороны надписей (перед справа, как фото 3:05)
    "rear": (Vector((-1.0, -0.45, 0.35)), 0.30, 50),    # задний торец, как кадр 7:54
    "front": (Vector((1.0, 0.30, 0.25)), 0.20, 50),
    "top": (Vector((0.0, 0.0, 1.0)), 0.40, 50),
    "under": (Vector((0.3, -0.6, -0.7)), 0.40, 50),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene
    for c in bpy.data.collections:
        if c.name in ("High-poly", "Low-poly"):
            want = (c.name == "High-poly") == (WHICH == "high")
            c.hide_render = not want
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.8, 0.8, 0.8)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_object_outline = False
    sh.show_specular_highlight = True
    if WHICH == "low":
        sh.show_xray = False
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1000
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("w")
    cd = bpy.data.cameras.new("prev")
    cam = bpy.data.objects.new("prev", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name, (d, dist, lens) in VIEWS.items():
        if ONLY and name not in ONLY:
            continue
        cd.lens = lens
        cd.clip_start = 0.002
        cam.location = CENTER + d.normalized() * dist
        up = "Y" if abs(d.normalized().z) < 0.99 else "X"
        cam.rotation_euler = (CENTER - cam.location).to_track_quat("-Z", up).to_euler()
        sc.render.filepath = os.path.join(OUT, f"{WHICH}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", sc.render.filepath)


main()
