"""ВЕРАС-54 v13: сравнение исходника (стеки UCUPaint) и игровой сетки на запечённых картах в студии файла — одна камера,
один свет (Cycles). Только своя проверка запекания; листы для владельца не собираются.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 <исходник v13 Textured_v02.blend> --python tools/veras54_v13/bake_compare.py -- <префикс> [камера:x:y:z:куда_x:куда_y:куда_z:ширина …]
→ <префикс>_<кадр>_hp.png и _lp.png. Без кадров — камера студии файла («Студия • камера»).
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import game_mats  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
prefix = Path(args[0])
views = {}
for a in args[1:]:
    p = a.split(':')
    views[p[0]] = (Vector([float(v) for v in p[1:4]]), Vector([float(v) for v in p[4:7]]), float(p[7]))
WORK = HERE.parents[1] / '_asset_src/veras54_game_v13'
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != 'CPU'
sc.cycles.device = 'GPU'
for c in bpy.data.collections:
    if 'Suppressor' in c.name:
        for o in c.all_objects:
            if o is not None:
                o.hide_render = True
cam = bpy.data.objects.get('Студия • камера')


def shoot(tag: str) -> None:
    if not views:
        sc.camera = cam
        sc.render.filepath = str(prefix) + f'_studio_{tag}.png'
        bpy.ops.render.render(write_still=True)
        return
    c = bpy.data.objects.get('cmp_cam') or bpy.data.objects.new('cmp_cam', bpy.data.cameras.new('cmp_cam'))
    if c.name not in sc.collection.objects:
        sc.collection.objects.link(c)
    c.data.type = 'ORTHO'
    c.data.clip_start = 0.001
    for name, (loc, at, width) in views.items():
        z = (loc - at).normalized()
        x = Vector((0, 0, 1)).cross(z).normalized() if abs(z.z) < 0.99 else Vector((1, 0, 0))
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = loc
        c.matrix_world = m
        c.data.ortho_scale = width
        sc.camera = c
        sc.render.filepath = str(prefix) + f'_{name}_{tag}.png'
        bpy.ops.render.render(write_still=True)


prefix.parent.mkdir(parents=True, exist_ok=True)
shoot('hp')
hp = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]
for o in hp:
    o.hide_render = True
with bpy.data.libraries.load(str(WORK / 'lp/VERAS54_Game_LP.blend'), link=False) as (src, dst):
    dst.objects = list(src.objects)
coll = bpy.data.collections.new('LP_CMP')
sc.collection.children.link(coll)
for o in dst.objects:
    coll.objects.link(o)
print('CMP materials', game_mats.build_all())
shoot('lp')
print('CMP_DONE', prefix)
