"""Замок Padlock_01: кадр «игровая низкая сетка рядом с high-poly» в одной студии (Cycles, процессор).

  blender --background --factory-startup --python-exit-code 1 --python tools/padlock_v01/game_compare.py -- [front|rear|both] [выборки]

Слева — high-poly v05 с лаком, справа — игровая версия (LOD0, карты 1K без лака). Результат —
E:/Models Blender/PROPS/Padlock_01/previews/game_vs_high.png (front и rear — в одном кадре, два ряда).
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

sys.path.insert(0, "E:/Games/RING-godot/tools/loot_containers")
import lc_game_lib as G  # noqa: E402

WORK = G.ROOT + "/_asset_src/padlock_v01/game"
OUT = "E:/Models Blender/PROPS/Padlock_01/previews/game_vs_high.png"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
samples = int(argv[1]) if len(argv) > 1 else 48
which = argv[0] if argv else "both"

bpy.ops.wm.open_mainfile(filepath=WORK + "/work_baked.blend")
sc = bpy.context.scene
highs = [o for o in bpy.data.collections["PADLOCK | geometry candidate"].objects if o.type == "MESH"]
lows = [o for o in bpy.data.objects if o.name.startswith("низк:")]
mat = G.game_material("Padlock", WORK + "/maps")
for lo in lows:
    lo.data.materials.clear()
    lo.data.materials.append(mat)
    lo.hide_render = lo.hide_viewport = False
for o in bpy.data.objects:
    if o.type == "CURVE":
        o.hide_render = True
for o in highs:
    o.hide_render = o.hide_viewport = False
# низкие — вправо на 0,1 м (мировые координаты сеток уже в метрах)
for lo in lows:
    lo.location.x += 0.1
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = samples
sc.cycles.use_denoising = False
sc.render.resolution_x, sc.render.resolution_y = 1800, 760
sc.render.film_transparent = False
w = bpy.data.worlds.new("w") if not sc.world else sc.world
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.055, 1)
for o in list(bpy.data.objects):
    if o.type == "LIGHT":
        bpy.data.objects.remove(o)
for name, loc, e, size in (("key", (-0.25, -0.35, 0.3), 14.0, 0.25), ("rim", (0.3, 0.3, 0.2), 6.0, 0.3), ("fill", (0.2, -0.4, 0.05), 3.0, 0.3)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = e
    ld.size = size
    lo_ = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo_)
    lo_.location = loc
    d = V((0.05, 0, 0.06)) - V(loc)
    lo_.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
cam = bpy.data.cameras.new("cmp")
cam.lens = 60
co = bpy.data.objects.new("cmp", cam)
sc.collection.objects.link(co)
sc.camera = co
if os.path.exists(OUT):
    os.remove(OUT)


def render(path, eye, at):
    co.location = eye
    co.rotation_euler = (V(at) - V(eye)).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


tmp = WORK + "/cmp_%s.png"
views = {"front": ((0.05 - 0.07, -0.6, 0.1), (0.05, 0, 0.06)), "rear": ((0.05 + 0.07, 0.6, 0.1), (0.05, 0, 0.06))}
for v in (["front", "rear"] if which == "both" else [which]):
    render(tmp % v, *views[v])
# склейка двух кадров в один (Blender-пиксели → numpy)
import numpy as np
imgs = []
for v in (["front", "rear"] if which == "both" else [which]):
    im = bpy.data.images.load(tmp % v)
    a = np.empty(im.size[0] * im.size[1] * 4, np.float32)
    im.pixels.foreach_get(a)
    imgs.append(a.reshape(im.size[1], im.size[0], 4))
stack = np.concatenate(imgs[::-1], 0)    # строки Blender снизу вверх: первым идёт нижний кадр
h, wd = stack.shape[:2]
out = bpy.data.images.new("out", wd, h, alpha=False)
out.pixels.foreach_set(stack.ravel())
out.filepath_raw = OUT
out.file_format = "PNG"
out.save()
print("СРАВНЕНИЕ", OUT)
