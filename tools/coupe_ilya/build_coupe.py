"""Купе Ильи: сборка кузова панелями в Blender.

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/build_coupe.py -- \
        <черновик.blend (колёса)> <выход.blend>

Поле формы — fieldcore + field_profiles.npz, панели — layout.py. Черновой объём остаётся
тёмной подложкой (утоплен на 8 мм): видно, где панелей ещё нет.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import bpy

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import fieldcore  # noqa: E402
import layout  # noqa: E402
from surface import Surface  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
BASE, OUT = Path(argv[0]), Path(argv[1])

MATERIALS = {
    "paint": ((0.42, 0.43, 0.45), 0.35, 0.0),
    "lamp_glass": ((0.05, 0.06, 0.07), 0.05, 0.0),
    "trim_black": ((0.02, 0.02, 0.02), 0.5, 0.0),
    "chrome": ((0.8, 0.8, 0.8), 0.1, 1.0),
    "glass": ((0.03, 0.035, 0.04), 0.02, 0.0),
    "lamp_red": ((0.35, 0.02, 0.02), 0.08, 0.0),
}


def material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb, rough, metal = MATERIALS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0))
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = rough
    m.metallic = metal
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


bpy.ops.wm.open_mainfile(filepath=str(BASE))
body = bpy.data.objects.get("Body_blockout")
if body is not None:
    ghost = bpy.data.materials.new("blockout_ghost")
    ghost.diffuse_color = (0.12, 0.13, 0.16, 1.0)
    body.data.materials.clear()
    body.data.materials.append(ghost)
    disp = body.modifiers.new("inset", "DISPLACE")
    disp.strength = -0.008
    disp.mid_level = 0.0

t0 = time.time()
surf = Surface(fieldcore.BodyField(fieldcore.load_profiles(HERE / "field_profiles.npz")))
col = bpy.data.collections.new("Body")
bpy.context.scene.collection.children.link(col)
total = 0
for name, mat, V, F in layout.build_all(surf):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material(mat))
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    total += len(F)
    print(f"  {name}: {len(V)} вершин, {len(F)} граней")
print(f"панелей: {len(col.objects)}, граней {total}, {time.time() - t0:.1f} с")
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("сохранено:", OUT)
