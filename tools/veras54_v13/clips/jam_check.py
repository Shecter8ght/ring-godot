"""Задержка «гильза в окне» (клип jam): с чем пересекается зажатая гильза в начале клипа; крупный кадр на неё.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup <VERAS54_Jam_Clear_v13.blend> --python tools/veras54_v13/clips/jam_check.py -- <префикс кадра>
Печатает JAM_OVERLAP <деталь> <число пар треугольников> (0 — не задевает) и сохраняет <префикс>_jam_<вид>.png.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

prefix = Path(sys.argv[sys.argv.index('--') + 1])
sc = bpy.context.scene
sc.frame_set(1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()


def bvh(o):
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    t = BVHTree.FromPolygons([eo.matrix_world @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons])
    eo.to_mesh_clear()
    return t


case = bpy.data.objects['JamCase • stuck case']
cb = bvh(case)
for o in bpy.data.objects:
    if o.type != 'MESH' or o == case or o.name.startswith(('FPS_', 'Magazine • loaded', 'SpareMag')) or o.hide_render:
        continue
    n = len(cb.overlap(bvh(o)))
    print('JAM_OVERLAP', o.name, n)
# крупно: камера справа-сверху на гильзу
c = case.matrix_world.translation
cam = bpy.data.objects.new('jam_cam', bpy.data.cameras.new('jam_cam'))
sc.collection.objects.link(cam)
cam.data.lens = 50
cam.data.clip_start = 0.005
sun = bpy.data.objects.new('jam_sun', bpy.data.lights.new('jam_sun', 'SUN'))
sc.collection.objects.link(sun)
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(40), 0, math.radians(200))
for o in bpy.data.objects:
    if o.name.startswith('FPS_Arms') and o.type == 'MESH':
        o.hide_render = True
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1000, 700
for name, off in (('right', Vector((-0.16, -0.03, 0.05))), ('top', Vector((-0.06, -0.02, 0.16)))):
    loc = c + off
    z = (loc - c).normalized()
    x = Vector((0, 0, 1)).cross(z).normalized() if abs(z.z) < 0.99 else Vector((1, 0, 0))
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = loc
    cam.matrix_world = m
    sc.camera = cam
    sc.render.filepath = str(prefix) + f'_jam_{name}.png'
    bpy.ops.render.render(write_still=True)
print('JAM_CHECK_DONE')
