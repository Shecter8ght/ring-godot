"""Мастер-файл FPS-рук с исправленными кистями (владелец 2026-11-06: «руки в порядок привести … как раз исходник рук и
трогай, чтобы потом избежать проблем с размерами»; «пальцам не надо длины»). Правка — tools/fps_hands_fix.py.

  veras  — из принятых рук ВЕРАСа v13 (Клипы v13/VERAS54_Reload_Full_v13.blend: риг FPS_ArmsRig с IK, сетка FPS_Arms,
           камера «FPS • Камера» 54°) → E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend: только руки и камера,
           действия хвата владельца (VERAS54_Grip_Manual_v02, Grip_Ready, Finger_On_Trigger) — в файле для новых клипов,
           оружие ВЕРАСа и его клипы — нет. Отсюда берут общие руки игры (tools/export_shared_fps_arms.py) и клипы
           новых стволов.
  owner <вход.blend> <выход.blend> — та же правка рук владельца (new hands.blend: риг metarig, сетка Arms) копией.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/fps_hands_master.py -- veras
Исходники не перезаписываются.
"""
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import fps_hands_fix as HF  # noqa: E402

VERAS = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Клипы v13/'
             'VERAS54_Reload_Full_v13.blend')
MASTER = Path('E:/Models Blender/WEAPONS/FPS-руки/FPS_Arms_v14.blend')
KEEP_ACTIONS = ('VERAS54_Grip_Manual_v02', 'VERAS54_Grip_Ready_v01', 'VERAS54_Finger_On_Trigger_v01')


def log(*a):
    print('FPS_HANDS', *a, flush=True)


def rest_pose(rig):
    if rig.animation_data:
        rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()


def veras():
    bpy.ops.wm.open_mainfile(filepath=str(VERAS))
    rig = bpy.data.objects['FPS_ArmsRig']
    mesh = bpy.data.objects['FPS_Arms']
    cam = bpy.data.objects.get('FPS • Camera')
    keep = {rig, mesh} | ({cam} if cam else set())
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        if a.name in KEEP_ACTIONS:
            a.use_fake_user = True
        else:
            bpy.data.actions.remove(a)
    for c in list(bpy.data.collections):
        if not c.all_objects:
            bpy.data.collections.remove(c)
    rest_pose(rig)
    before, after = HF.fix_objects(rig, mesh)
    log('кисти, см:', before, '→', after)
    rig['hands_source'] = str(VERAS)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER), compress=True)
    log('сохранено', MASTER)


def owner(src, out):
    bpy.ops.wm.open_mainfile(filepath=src)
    rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.find_armature() == rig)
    rest_pose(rig)
    before, after = HF.fix_objects(rig, mesh)
    log('кисти, см:', before, '→', after)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    log('сохранено', out)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    if a[0] == 'veras':
        veras()
    elif a[0] == 'owner':
        owner(a[1], a[2])
