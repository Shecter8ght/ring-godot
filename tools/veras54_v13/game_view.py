"""ВЕРАС-54 v13: кадры для собственной проверки игровой сетки рядом с high-poly (Workbench, одинаковые камеры).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 <файл .blend> --python tools/veras54_v13/game_view.py -- <префикс> [вид,вид…] [--textured]
Файл — high-poly v13 или _asset_src/veras54_game_v13/lp/VERAS54_Game_LP.blend (оси те же). Кадры — <префикс>_<вид>.png.
--textured — Material Preview (EEVEE) вместо глины: игровые материалы с картами (после game_export.py).
Листы для владельца не собираются (он смотрит сам в Blender) — это только своя проверка.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

args = sys.argv[sys.argv.index('--') + 1:]
prefix = Path(args[0])
TEXTURED = '--textured' in args
args = [a for a in args if not a.startswith('--')]
VIEWS = {   # имя: (куда смотреть, откуда — смещение, ширина кадра м)
    'right': (Vector((0.24, 0, -0.03)), Vector((0.0, -1.0, 0.0)), 1.0),
    'left': (Vector((0.24, 0, -0.03)), Vector((0.0, 1.0, 0.0)), 1.0),
    'top': (Vector((0.24, 0, 0.0)), Vector((0.0, 0.0, 1.0)), 1.0),
    'eye': (Vector((0.5, 0, 0.057)), Vector((-0.6, 0.0, 0.0)), 0.12),
    'notch': (Vector((0.031, 0, 0.052)), Vector((-0.08, -0.04, 0.03)), 0.05),
    'front_sight': (Vector((0.518, 0, 0.045)), Vector((-0.06, -0.06, 0.04)), 0.07),
    'muzzle': (Vector((0.66, 0, 0.0)), Vector((0.08, -0.12, 0.05)), 0.14),
    'vents': (Vector((0.35, 0, 0.02)), Vector((-0.05, -0.12, 0.12)), 0.2),
    'bolt': (Vector((0.2, -0.02, 0.01)), Vector((0.0, -0.15, 0.05)), 0.14),
    'grip': (Vector((0.06, 0, -0.07)), Vector((0.0, -0.2, 0.0)), 0.16),
    'mag': (Vector((0.205, 0, -0.11)), Vector((0.0, -0.25, 0.0)), 0.22),
    'stock': (Vector((-0.12, 0, -0.06)), Vector((0.0, -0.3, 0.05)), 0.3),
    'rear_sight': (Vector((0.05, 0, 0.05)), Vector((-0.1, -0.12, 0.1)), 0.1),
}
want = args[1].split(',') if len(args) > 1 else list(VIEWS)
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.hide_render = True
for c in bpy.data.collections:
    if 'Suppressor' in c.name:
        for o in c.all_objects:
            o.hide_render = True
sc.render.engine = 'BLENDER_EEVEE' if TEXTURED else 'BLENDER_WORKBENCH'
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
sc.render.film_transparent = False
if not TEXTURED:
    sh = sc.display.shading
    sh.light = 'STUDIO'
    sh.color_type = 'SINGLE'
    sh.single_color = (0.62, 0.62, 0.6)
    sh.show_cavity = True
    sh.cavity_type = 'WORLD'
    sh.show_object_outline = False
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.85, 0.45, 0.6)     # розовый фон: дыры видны
else:
    w = sc.world or bpy.data.worlds.new('W')
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    sun = bpy.data.objects.new('chk_sun', bpy.data.lights.new('chk_sun', 'SUN'))
    sc.collection.objects.link(sun)
    sun.data.energy = 4.0
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(-30))
cam = bpy.data.objects.new('chk_cam', bpy.data.cameras.new('chk_cam'))
sc.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.clip_start = 0.001
sc.camera = cam
prefix.parent.mkdir(parents=True, exist_ok=True)
for v in want:
    focus, off, width = VIEWS[v]
    loc = focus + off.normalized() * 1.5
    z = (loc - focus).normalized()
    up = Vector((0, 0, 1)) if abs(z.z) < 0.99 else Vector((1, 0, 0))
    x = up.cross(z).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = loc
    cam.matrix_world = m
    cam.data.ortho_scale = width
    sc.render.filepath = str(prefix) + f'_{v}.png'
    bpy.ops.render.render(write_still=True)
print('VIEW_DONE', prefix)
