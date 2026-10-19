"""Кадры клипа для собственной проверки (EEVEE): вид стрелка и крупные планы у рукоятки затвора / окна выброса.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup <клип .blend> --python tools/veras54_v13/clips/clip_view.py -- <префикс> <кадры через запятую> [виды через запятую] [focus=x:y:z]
Виды — rig_common.VIEWS (fps, left, below, front, right). Листы для владельца не собираются — только своя проверка.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig_common as rc  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
prefix = Path(args[0])
frames = [int(f) for f in args[1].split(',')]
views = args[2].split(',') if len(args) > 2 and not args[2].startswith('focus=') else ['fps', 'right']
focus = None
for a in args:
    if a.startswith('focus='):
        focus = Vector([float(v) for v in a[6:].split(':')])
rc.hide_suppressor()
if focus is None:
    bpy.context.scene.frame_set(frames[0])
    bpy.context.view_layer.update()
    focus = bpy.data.objects['ChargingHandle'].matrix_world.translation.copy()
rc.preview(prefix, focus, views, frames)
print('CLIP_VIEW_DONE', prefix)
