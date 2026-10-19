"""Действия клипа автомата (build_clips.py) → имена набора магазина: VERAS54_<Клип>[_<рукоятка>]_<что>_v01 →
VERAS54_<Клип>[_<рукоятка>]_<mag45|drum60>_<что>_v01 (иначе при сборке вьюмодели они совпали бы с клипами штатного).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup <клип .blend> --python tools/veras54_mags/mags_rename_actions.py -- <Клип[_рукоятка]> <mag45|drum60>
"""
import sys

import bpy

tag, mset = sys.argv[sys.argv.index('--') + 1:][:2]
n = 0
for a in bpy.data.actions:
    for kind in ('Arms', 'Weapon', 'Controls', 'Rounds'):
        if a.name == f'VERAS54_{tag}_{kind}_v01':
            a.name = f'VERAS54_{tag}_{mset}_{kind}_v01'
            n += 1
if n == 0:
    raise SystemExit(f'нет действий VERAS54_{tag}_*_v01')
bpy.ops.wm.save_mainfile()
print('MAGS_RENAME', tag, mset, n, flush=True)
