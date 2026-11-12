"""Проверка развёртки контейнеров: каждая сетка набора своим цветом (Workbench), открытое и закрытое состояния, три ракурса.

  blender --background <RING_Loot_Containers_uv_v01.blend> --python tools/loot_containers/lc_check.py -- <папка> [набор …]
"""
import colorsys
import math
import os
import sys
import zlib

import bpy
from mathutils import Vector as V

argv = sys.argv[sys.argv.index("--") + 1:]
out, only = argv[0], argv[1:]
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y = 900, 900
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "OBJECT"
sc.view_settings.view_transform = "Standard"
top = bpy.data.collections["Развёртка_v01"]
top.hide_viewport = False
for o in bpy.data.objects:
    if o.name.startswith("_src_"):
        o.hide_render = True
        o.hide_viewport = True
for c in top.children:
    c.hide_render = True
    c.hide_viewport = True
cam = bpy.data.cameras.new("c")
cam.lens = 60
co = bpy.data.objects.new("c", cam)
sc.collection.objects.link(co)
sc.camera = co
VIEWS = {"f": (-25, 20), "b": (-150, 25), "t": (-60, 60)}
games = [c.name for c in top.children if "__closed" not in c.name]
for game in games:
    if only and game not in only:
        continue
    for suffix, state in (("", "open"), ("__closed", "closed")):
        coll = bpy.data.collections[game + suffix]
        coll.hide_viewport = False
        coll.hide_render = False
        objs = [o for o in coll.objects if o.type == "MESH"]
        mn = V((1e9,) * 3)
        mx = V((-1e9,) * 3)
        for o in objs:
            o.hide_viewport = False
            o.hide_render = False
            h = zlib.crc32(o.name.encode()) % 360 / 360.0
            o.color = (*colorsys.hsv_to_rgb(h, 0.65, 0.95), 1.0)
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                mn = V(map(min, mn, w))
                mx = V(map(max, mx, w))
        c = (mn + mx) / 2
        r = (mx - mn).length
        for vn, (az, el) in VIEWS.items():
            a, e = math.radians(az - 90), math.radians(el)
            co.location = c + V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * r * 1.5
            d = c - co.location
            co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = f"{out}/{game}_{state}_{vn}.png"
            bpy.ops.render.render(write_still=True)
        coll.hide_viewport = True
        coll.hide_render = True
print("done")
