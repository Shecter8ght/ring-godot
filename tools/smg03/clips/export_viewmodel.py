"""ИЗЛОМ-45 (wpn_smg_03): вьюмодель — руки (мастер FPS-рук v14, кисти исправлены) и оружие с клипами
(tools/smg03/clips/build_clips.py) → assets/models/weapons/smg03/smg03_viewmodel.gltf; как tools/export_veras54.py viewmodel.

Сцена в осях камеры от первого лица (камера в начале, взгляд по −Z Godot). Клипы (NLA-дорожки → анимации glTF): idle,
reload_tactical, reload_full, mag_check, inspect, jam_clear; служебные: bolt_travel (кадр 0 — затвор закрыт, 1 — отведён на
45 мм) и selector_by_mode (флажки переводчика по порядку fire_modes ствола: АВ, «2», ОД). IK запечён в ключи костей.
Детали склеены по костям (Part_<кость>): Part_Magazine — магазин на 13, Part_MagazineFollower, Part_JamCase (гильза
задержки), патрон — Round_01. Метки у кости WeaponRoot: SightRear, SightFront, Muzzle, WeaponFrame (пистолетная рукоятка);
MagAsset — у кости Magazine: на неё игра ставит модель магазина на 30 (smg03_mag30.gltf, viewmodel_set «mag30»).
Карты — прежние файлы рядом (оружие — smg03_<Атлас>_100_*, руки — ../veras54/arm*.png), не перезаписываются.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/clips/export_viewmodel.py
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
LIB = Path('E:/Models Blender/WEAPONS/Vector — модель/Анимации')
RIG = LIB / 'ИЗЛОМ45_Rig_v01.blend'
OUT = ROOT / 'assets/models/weapons/smg03'
ARMS_TEX = ROOT / 'assets/models/weapons/veras54'
# клип в игре: (тег действий build_clips.py, файл клипа)
CLIPS = {'reload_tactical': ('Tactical', 'tactical'), 'reload_full': ('Full', 'full'), 'mag_check': ('Check', 'check'),
         'inspect': ('Inspect', 'inspect'), 'jam_clear': ('Jam', 'jam')}
BOLT_TRAVEL = 0.045
SELECTOR_DEG = {'auto': 60.0, 'burst': 30.0, 'semi': 0.0}
FIRE_MODES = ('auto', 'burst', 'semi')
MAG_MOUNT = Vector((-0.03546, 0.0, -0.0116))
MARKS_SRC = {'SightRear': (-0.2245, 0.0, 0.076), 'SightFront': (0.1005, 0.0, 0.076), 'Muzzle': (0.1419, 0.0, 0.0),
             'WeaponFrame': (-0.2122, 0.0, -0.035)}
report = {}


def log(*a):
    print('SMG03_VM', *a, flush=True)


def fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


def assign(ob, act):
    ad = ob.animation_data or ob.animation_data_create()
    ad.action = act
    if act is not None and act.slots:
        ad.action_slot = act.slots[0]


def sample(arms, wr, frames, skip=()):
    """Итоговая поза костей (с IK и ограничениями) в локальных осях — по кадрам; кости без ключей — в покое."""
    sc = bpy.context.scene
    data = {arms.name: {}, wr.name: {}}
    for arm in (arms, wr):
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    for f in frames:
        sc.frame_set(int(f))
        bpy.context.view_layer.update()
        for arm in (arms, wr):
            for pb in arm.pose.bones:
                if pb.name in skip:
                    continue
                m = arm.convert_space(pose_bone=pb, matrix=pb.matrix, from_space='POSE', to_space='LOCAL')
                data[arm.name].setdefault(pb.name, []).append(m.copy())
    return data


def bake_action(arm, name, frames, mats):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    assign(arm, act)
    for pb in arm.pose.bones:
        if pb.name not in mats:
            continue
        pb.rotation_mode = 'QUATERNION'
        for i, _ in enumerate(frames):
            loc, rot, scl = mats[pb.name][i].decompose()
            pb.location, pb.rotation_quaternion, pb.scale = loc, rot, scl
            for path in ('location', 'rotation_quaternion', 'scale'):
                pb.keyframe_insert(path, frame=i + 1)
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    assign(arm, None)
    return act


def push_track(arm, track_name, act):
    ad = arm.animation_data or arm.animation_data_create()
    tr = ad.nla_tracks.new()
    tr.name = track_name
    tr.strips.new(track_name, 1, act)


def join(group, name):
    if not group:
        return None
    for o in group:
        if o.data.users > 1:
            o.data = o.data.copy()
    if len(group) == 1:
        group[0].name = name
        return group[0]
    with bpy.context.temp_override(active_object=group[0], selected_editable_objects=group, selected_objects=group):
        bpy.ops.object.join()
    group[0].name = name
    return group[0]


def add_mark(name, world, parent, bone):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
    e.empty_display_size = 0.01
    e.parent = parent
    e.parent_type = 'BONE'
    e.parent_bone = bone
    bpy.context.view_layer.update()
    e.matrix_world = world
    return e


def main():
    bpy.ops.wm.open_mainfile(filepath=str(RIG))
    sc = bpy.context.scene
    arms = bpy.data.objects['FPS_ArmsRig']
    wr = bpy.data.objects['SMG03_WeaponRig']
    root = bpy.data.objects['SMG03']
    cam = bpy.data.objects['FPS • Camera']
    lengths = {}
    for clip, (tag, fname) in CLIPS.items():
        path = LIB / f'ИЗЛОМ45_Clip_{fname}_v01.blend'
        with bpy.data.libraries.load(str(path), link=False) as (src, dst):
            dst.actions = [a for a in src.actions if a in (f'IZLOM45_{tag}_Arms_v01', f'IZLOM45_{tag}_Weapon_v01')]
        act = bpy.data.actions[f'IZLOM45_{tag}_Arms_v01']
        lengths[clip] = int(round(act.frame_range[1]))
    acts = {a.name: a for a in bpy.data.actions}
    # карты рук — игровые ВЕРАСа (общие руки), а не упакованные в исходник
    tex = {p.name.lower(): p for p in ARMS_TEX.glob('arm*.png')}
    for img in bpy.data.images:
        name = Path(img.filepath).name.lower() if img.filepath else img.name.lower()
        if name in tex:
            if img.packed_file:
                img.unpack(method='REMOVE')
            img.filepath = str(tex[name])
            img.reload()
    skip = ('MagazineFollower',)
    baked = {}
    for clip, (tag, _) in CLIPS.items():
        assign(arms, acts[f'IZLOM45_{tag}_Arms_v01'])
        assign(wr, acts[f'IZLOM45_{tag}_Weapon_v01'])
        frames = list(range(1, lengths[clip] + 1))
        baked[clip] = (frames, sample(arms, wr, frames, skip))
        log('клип', clip, len(frames))
    assign(arms, acts['IZLOM45_Tactical_Arms_v01'])
    assign(wr, acts['IZLOM45_Tactical_Weapon_v01'])
    baked['idle'] = ([1, 2], sample(arms, wr, [1, 1], skip))
    for ob in (arms, wr):
        assign(ob, None)
    # служебные: затвор (отвод при выстреле и задержка после последнего патрона) и флажки переводчика по режиму
    bolt = [Matrix.Translation((0.0, -BOLT_TRAVEL * v, 0.0)) for v in (0.0, 1.0)]
    sel = [Matrix.Rotation(math.radians(SELECTOR_DEG[m]), 4, 'Y') for m in FIRE_MODES]
    # ограничения — прочь: дальше кости ведут только запечённые ключи
    for arm in (arms, wr):
        for pb in arm.pose.bones:
            for c in list(pb.constraints):
                pb.constraints.remove(c)
    for clip, (frames, data) in baked.items():
        push_track(arms, clip, bake_action(arms, f'VM_{clip}_arms', frames, data[arms.name]))
        push_track(wr, clip, bake_action(wr, f'VM_{clip}_weapon', frames, data[wr.name]))
    push_track(wr, 'bolt_travel', bake_action(wr, 'VM_bolt', [0, 1], {'Bolt': bolt}))
    push_track(wr, 'selector_by_mode', bake_action(wr, 'VM_selector', [0, 1, 2], {'Selector': sel}))
    for arm in (arms, wr):
        arm.data.pose_position = 'POSE'
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    sc.frame_set(1)
    bpy.context.view_layer.update()
    # метки — у кости WeaponRoot (оси мира, как у ВЕРАСа), магазин на 30 — на кости Magazine в осях модели магазина
    TW = root.matrix_world.copy()
    for name, p in MARKS_SRC.items():
        add_mark(name, Matrix.Translation(TW @ Vector(p)), wr, 'WeaponRoot')
    add_mark('MagAsset', TW @ Matrix.Translation(MAG_MOUNT) @ Matrix.Rotation(math.radians(90.0), 4, 'Z'), wr, 'Magazine')
    # скрытое (магазин на 30 — моделью на MagAsset), камеры кроме FPS, тексты — не в игру
    for ob in list(bpy.data.objects):
        if ob.type == 'MESH' and (ob.hide_render or ob.hide_get()):
            bpy.data.objects.remove(ob, do_unlink=True)
        elif ob.type in ('CAMERA', 'LIGHT') and ob is not cam:
            bpy.data.objects.remove(ob, do_unlink=True)
    groups = {}
    for ob in [o for o in bpy.data.objects if o.type == 'MESH']:
        if ob.name.startswith(('Round_', 'FPS_')):
            continue
        key = ob.parent_bone if ob.parent_type == 'BONE' else (ob.parent.name if ob.parent else '')
        groups.setdefault(key, []).append(ob)
    for bone, group in groups.items():
        join(group, 'Part_' + bone)
    report['parts'] = sorted('Part_' + b for b in groups)
    # оси камеры: камера в начале, взгляд Blender +Y (= −Z glTF/Godot), верх +Z
    to_cam = Matrix.Rotation(math.radians(90), 4, 'X') @ cam.matrix_world.inverted()
    arms.matrix_world = to_cam @ arms.matrix_world
    bpy.data.objects.remove(cam, do_unlink=True)
    dg = bpy.context.evaluated_depsgraph_get()
    tris = {}
    for ob in [o for o in bpy.data.objects if o.type == 'MESH']:
        me = ob.evaluated_get(dg).to_mesh()
        me.calc_loop_triangles()
        tris[ob.name] = len(me.loop_triangles)
        ob.evaluated_get(dg).to_mesh_clear()
    report['tris'] = sum(tris.values())
    report['tris_weapon'] = sum(v for k, v in tris.items() if not k.startswith('FPS_'))
    report['clips'] = {k: v for k, v in lengths.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'smg03_viewmodel.gltf'), export_format='GLTF_SEPARATE',
                              export_texture_dir='', export_keep_originals=True, export_yup=True,
                              export_materials='EXPORT', export_cameras=False, export_lights=False,
                              export_animations=True, export_animation_mode='NLA_TRACKS', export_skins=True,
                              export_all_influences=True, export_def_bones=False, export_force_sampling=True,
                              export_apply=False)
    # Godot переимпортирует .gltf по его сумме, а ключи клипов лежат в .bin: сумма .bin — в asset.extras, иначе правка
    # клипа без смены числа кадров в игру не попадает
    import hashlib
    gpath = OUT / 'smg03_viewmodel.gltf'
    doc = json.loads(gpath.read_text(encoding='utf-8'))
    doc.setdefault('asset', {}).setdefault('extras', {})['bin_md5'] = hashlib.md5((OUT / 'smg03_viewmodel.bin').read_bytes()).hexdigest()
    gpath.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    (OUT / 'smg03_viewmodel.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8',
                                              newline='\n')
    log('сохранено', OUT / 'smg03_viewmodel.gltf', report['tris'], report['clips'])


if __name__ == '__main__':
    main()
