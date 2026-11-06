"""ИЗЛОМ-45, клипы рук: боевой хват владельца с ВЕРАСа v13 (как tools/veras54_v13/clips/build_clips.py: поза файла, затем
кадр 1 VERAS54_Grip_Manual_v02) — кисти, цели IK, Weapon_CTRL, корень оружия, ближайшие к кистям точки оружия — в мире
→ JSON (_asset_src/smg03/anim/veras_ready.json): от него tools/smg03/clips/rig.py ставит стартовый хват ИЗЛОМа.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b ".../ВЕРАС-54/Игровая версия/Риг v13/VERAS54_Rig_v13.blend" --python tools/smg03/clips/veras_ready_dump.py -- <json>
"""
import json
import sys

import bpy

out = sys.argv[sys.argv.index('--') + 1]
arms = bpy.data.objects['FPS_ArmsRig']
wr = bpy.data.objects['VERAS54_WeaponRig']
for a in (arms, wr):
    if a.animation_data:
        a.animation_data.action = None
bpy.context.view_layer.update()
# поза файла: левая — хват магазина (MAGPOSE у build_clips), правая — крюк на рукоятке затвора
M0 = lambda m: [list(r) for r in m]
filepose = {'basis': {pb.name: M0(pb.matrix_basis) for pb in arms.pose.bones},
            'world': {n: M0(arms.matrix_world @ arms.pose.bones[n].matrix) for n in
                      ('hand.L', 'ik_hand.L', 'f_middle.01.L', 'hand.R', 'ik_hand.R', 'f_middle.01.R', 'Weapon_CTRL')},
            'mag_control': M0(wr.matrix_world @ wr.pose.bones['Magazine_Control'].matrix)}
mb = bpy.data.objects.get('Magazine_Body')
if mb:
    dg0 = bpy.context.evaluated_depsgraph_get()
    em = mb.evaluated_get(dg0)
    pts = [em.matrix_world @ v.co for v in em.to_mesh().vertices]
    em.to_mesh_clear()
    ax = (wr.matrix_world @ wr.pose.bones['Magazine_Control'].matrix).to_3x3().col[1].normalized()
    low = min(pts, key=lambda p: p.dot(ax))
    filepose['mag_body_center'] = list(sum(pts, type(pts[0])()) / len(pts))
    filepose['mag_axis'] = list(ax)
    filepose['mag_low'] = list(low)
ad = arms.animation_data or arms.animation_data_create()
act = bpy.data.actions['VERAS54_Grip_Manual_v02']
ad.action = act
if act.slots:
    ad.action_slot = act.slots[0]
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
keyed = sorted({fc.data_path.split('"')[1] for layer in act.layers for strip in layer.strips for bag in strip.channelbags
                for fc in bag.fcurves if '"' in fc.data_path})
M = lambda m: [list(r) for r in m]
rec = {'keyed_bones': keyed, 'filepose': filepose}
for n in ('hand.R', 'hand.L', 'ik_hand.R', 'ik_hand.L', 'Weapon_CTRL', 'forearm.R', 'forearm.L', 'upper_arm.R',
          'upper_arm.L', 'pole.R', 'pole.L', 'f_middle.01.R', 'f_middle.01.L'):
    pb = arms.pose.bones[n]
    rec[n] = M(arms.matrix_world @ pb.matrix)
rec['WeaponRoot'] = M(wr.matrix_world @ wr.pose.bones['WeaponRoot'].matrix)
rec['VERAS54'] = M(bpy.data.objects['VERAS54'].matrix_world)
for n in ('SightRear', 'SightFront', 'Muzzle', 'WeaponFrame', 'ChargingHandle'):
    o = bpy.data.objects.get(n)
    if o:
        rec['obj_' + n] = list(o.matrix_world.translation)
# нижняя точка цевья под левой кистью и рукоятка под правой (по сетке оружия)
dg = bpy.context.evaluated_depsgraph_get()
hl = (arms.matrix_world @ arms.pose.bones['hand.L'].matrix).translation
hr = (arms.matrix_world @ arms.pose.bones['hand.R'].matrix).translation
best = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name.startswith('FPS') or o.find_armature() == arms:
        continue
    if o.hide_render:
        continue
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    mw = eo.matrix_world
    for v in me.vertices:
        p = mw @ v.co
        for key, h in (('L', hl), ('R', hr)):
            d = (p - h).length
            if d < best.get(key, (9, None, None))[0]:
                best[key] = (d, list(p), o.name)
    eo.to_mesh_clear()
rec['nearest_weapon'] = best
open(out, 'w', encoding='utf-8').write(json.dumps(rec, ensure_ascii=False, indent=1))
print('DUMP ok', keyed[:8], len(keyed))
