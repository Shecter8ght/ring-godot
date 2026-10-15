"""Граната с теми же перчатками/ригом FPS_ArmsRig, что у ВЕРАС-54.

Blender --background --factory-startup --python-exit-code 1 --python tools/prepare_grenade_hands.py -- build|export|stills|audit|edit_files
Оба исходника только читаются. Производный Blender сохраняет IK и редактируемый хват.
В игру экспортируются только руки; игровая граната и её чека остаются прежними.
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import struct

import bpy
from mathutils import Matrix, Vector, Quaternion
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Перезарядка v01 (Claude)/VERAS54_Reload_Full_v05.blend')
GRENADE = ROOT / '_asset_src/grenade_game/Grenade_Game.blend'
WORK = ROOT / '_asset_src/grenade_hands'
OUT = ROOT / 'assets/models/weapons/grenade'
BLEND = WORK / 'Grenade_VERAS_Hands.blend'
FINGERS = ('f_index', 'f_middle', 'f_ring', 'f_pinky')
POSE = Vector((.13, -.10, -.38))
ASSET_TO_CAMERA = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
log = lambda *args: print('GRENADE_HANDS', *args, flush=True)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assign(arm, action):
    data = arm.animation_data or arm.animation_data_create()
    data.action = action
    if action and action.slots:
        data.action_slot = action.slots[0]


def curves(action):
    return [curve for layer in action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves]


def frame(across, forward):
    forward = Vector(forward).normalized()
    across = Vector(across)
    across = (across - forward * across.dot(forward)).normalized()
    return Matrix((across, forward, across.cross(forward))).transposed()


def hand_frame(arm, side):
    wrist = arm.matrix_world @ arm.pose.bones['hand.' + side].head
    forward = arm.matrix_world @ arm.pose.bones['f_middle.01.' + side].head - wrist
    across = arm.matrix_world @ (arm.pose.bones['f_index.01.' + side].head - arm.pose.bones['f_pinky.01.' + side].head)
    return frame(across, forward)


def world(arm, bone):
    return arm.matrix_world @ arm.pose.bones[bone].matrix


def target(arm, side, matrix):
    arm.pose.bones['ik_hand.' + side].matrix = arm.matrix_world.inverted() @ matrix
    bpy.context.view_layer.update()


def tree_of(objects):
    vertices, faces = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh()
        offset = len(vertices)
        vertices.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        faces.extend([offset + i for i in face.vertices] for face in mesh.polygons)
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices, faces)


def finger_axis(arm, name, palm):
    bone = arm.pose.bones[name]
    direction = (arm.matrix_world.to_3x3() @ (bone.tail - bone.head)).normalized()
    axis = direction.cross(palm).normalized()
    return (arm.matrix_world.to_3x3() @ bone.matrix.to_3x3()).inverted() @ axis


def finger_pose(arm, side, palm, angles):
    result = {}
    for finger in FINGERS:
        for joint in range(1, 4):
            name = f'{finger}.{joint:02d}.{side}'
            bone = arm.pose.bones[name]
            old = bone.rotation_quaternion.copy()
            bone.rotation_quaternion = Quaternion()
            bpy.context.view_layer.update()
            axis = finger_axis(arm, name, palm)
            values = angles.get(finger, angles['default'])
            result[name] = Quaternion(axis.normalized(), math.radians(values[joint-1]))
            bone.rotation_quaternion = old
    return result


def apply(arm, pose):
    for name, rotation in pose.items():
        arm.pose.bones[name].rotation_quaternion = rotation
    bpy.context.view_layer.update()


def close_thumb(arm, side, point):
    # CCD только большого пальца: подвести подушечку к месту прижима, без изменения кисти.
    tip_name = 'thumb.03.' + side
    for _ in range(35):
        tip = arm.matrix_world @ arm.pose.bones[tip_name].tail
        if (tip - point).length < .006:
            break
        for joint in (2, 1):
            bone = arm.pose.bones[f'thumb.{joint:02d}.{side}']
            start = arm.matrix_world @ bone.head
            tip = arm.matrix_world @ arm.pose.bones[tip_name].tail
            before, after = (tip-start).normalized(), (point-start).normalized()
            rotation = before.rotation_difference(after)
            angle = min(rotation.angle, math.radians(5))
            rotate = Quaternion(rotation.axis, angle).to_matrix().to_4x4()
            matrix = Matrix.Translation(start) @ rotate @ Matrix.Translation(-start) @ world(arm, bone.name)
            bone.matrix = arm.matrix_world.inverted() @ matrix
            bpy.context.view_layer.update()


def build():
    bpy.context.preferences.use_preferences_save = False
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.unit_settings.system = 'METRIC'
    with bpy.data.libraries.load(str(SOURCE), link=False) as (src, dst):
        dst.objects = ['FPS_ArmsRig', 'FPS_Arms', 'FPS • Camera']
        dst.actions = ['VERAS54_Grip_Manual_v02']
    for obj in dst.objects:
        scene.collection.objects.link(obj)
    arm = bpy.data.objects['FPS_ArmsRig']
    camera = bpy.data.objects['FPS • Camera']
    scene.camera = camera
    arm.animation_data_clear()
    for bone in arm.pose.bones:
        bone.rotation_mode = 'QUATERNION'
    assign(arm, bpy.data.actions['VERAS54_Grip_Manual_v02'])
    scene.frame_set(1)
    bpy.context.view_layer.update()
    source_frames = {side: hand_frame(arm, side) for side in ('R', 'L')}
    source_basis = {side: world(arm, 'hand.' + side).to_3x3() for side in ('R', 'L')}
    ready = {bone.name: bone.matrix_basis.copy() for bone in arm.pose.bones}
    assign(arm, None)
    for bone in arm.pose.bones:
        bone.matrix_basis = ready[bone.name]
    with bpy.data.libraries.load(str(GRENADE), link=False) as (src, dst):
        dst.collections = ['GRENADE_GAME']
    coll = dst.collections[0]
    scene.collection.children.link(coll)
    grenade = coll.objects['Grenade']
    grenade.matrix_world = camera.matrix_world @ Matrix.Translation(POSE) @ ASSET_TO_CAMERA
    bpy.context.view_layer.update()
    desired_frames = {'R': frame((0, .15, 1), (0, 1, -.15)),
                      'L': frame((0, .5, 1), (.8, .5, -.3))}
    def wrist(side, position):
        basis = camera.matrix_world.to_3x3() @ desired_frames[side] @ source_frames[side].inverted() @ source_basis[side]
        matrix = basis.to_4x4()
        matrix.translation = camera.matrix_world @ Vector(position)
        return matrix
    right = wrist('R', POSE + Vector((.043, -.105, .02)))
    left_park = wrist('L', POSE + Vector((-.16, -.12, .03)))
    target(arm, 'R', right)
    target(arm, 'L', left_park)
    # Ось сгиба — в ладонь: разные локальные оси правых и левых фаланг учитываются явно.
    palm_r = camera.matrix_world.to_3x3() @ desired_frames['R'].col[2]
    right_fingers = finger_pose(arm, 'R', palm_r, {'default': (38, 80, 55), 'f_index': (35, 80, 55), 'f_pinky': (48, 85, 55)})
    apply(arm, right_fingers)
    body_tree = tree_of([coll.objects['LP_GrenadeBody'], coll.objects['LP_SafetyLever']])
    thumb = arm.matrix_world @ arm.pose.bones['thumb.03.R'].tail
    nearest, normal, _, _ = body_tree.find_nearest(thumb)
    close_thumb(arm, 'R', nearest + normal * .007)
    for name in ['thumb.01.R', 'thumb.02.R', 'thumb.03.R']:
        right_fingers[name] = arm.pose.bones[name].rotation_quaternion.copy()
    # Левая берёт наружную сторону кольца; положение запястья выводим из контакта указательного.
    palm_l = camera.matrix_world.to_3x3() @ desired_frames['L'].col[2]
    left_open = finger_pose(arm, 'L', palm_l, {'default': (8, 20, 15), 'f_index': (10, 20, 15)})
    left_pinch = finger_pose(arm, 'L', palm_l, {'default': (55, 85, 65), 'f_index': (40, 70, 50)})
    hook = wrist('L', POSE + Vector((-.09, -.04, 0)))
    target(arm, 'L', hook)
    apply(arm, left_pinch)
    ring_point = grenade.matrix_world @ Vector((.0295, -.0122, .0475))
    index_tip = arm.matrix_world @ arm.pose.bones['f_index.03.L'].tail
    hook.translation += ring_point - index_tip
    target(arm, 'L', hook)
    close_thumb(arm, 'L', ring_point + camera.matrix_world.to_3x3() @ Vector((0, -.007, .004)))
    for name in ['thumb.01.L', 'thumb.02.L', 'thumb.03.L']:
        left_pinch[name] = arm.pose.bones[name].rotation_quaternion.copy()
        left_open[name] = left_pinch[name].slerp(Quaternion(), .5)
    action = bpy.data.actions.new('Grenade_Hold_Pin')
    assign(arm, action)
    pin = coll.objects['Pin']
    home = pin.location.copy()
    key = coll.objects['LP_SafetyPin'].data.shape_keys.key_blocks.get('SplitTips_Compress')
    pose_report = []
    for index in range(31):
        amount = index / 30
        scene.frame_set(index + 1)
        travel = .0006 * min(1, amount/.16) + .0514 * max(0, (amount-.16)/.84)
        approach = min(1, amount/.16)
        approach = approach*approach*(3-2*approach)
        target(arm, 'R', right)
        desired = left_park.lerp(hook, approach)
        desired.translation += grenade.matrix_world.to_3x3() @ Vector((0, -travel, 0)) * approach
        target(arm, 'L', desired)
        apply(arm, right_fingers)
        apply(arm, {name: left_open[name].slerp(value, approach) for name, value in left_pinch.items()})
        for bone in arm.pose.bones:
            for prop in ('location', 'rotation_quaternion', 'scale'):
                bone.keyframe_insert(prop, frame=index+1)
        pin.location = home + Vector((0, -travel, 0))
        pin.keyframe_insert('location', frame=index+1)
        if key:
            key.value = min(1, amount/.16)
            key.keyframe_insert('value', frame=index+1)
        pose_report.append({'progress': amount, 'right_wrist_error': (world(arm, 'hand.R').translation-right.translation).length,
                            'left_wrist_error': (world(arm, 'hand.L').translation-desired.translation).length})
    for curve in curves(action):
        for point in curve.keyframe_points:
            point.interpolation = 'LINEAR'
    scene.frame_set(1)
    bpy.context.view_layer.update()
    scene['grenade_hands_source'] = str(SOURCE)
    scene['grenade_hands_instruction'] = 'Frames 1-31: hold → ring contact → pin extracted. Original IK targets remain editable.'
    # Предмет следует за правой кистью и остаётся с отдельными Pin/Lever для будущих клипов.
    matrix = grenade.matrix_world.copy()
    grenade.parent = arm
    grenade.parent_type = 'BONE'
    grenade.parent_bone = 'hand.R'
    grenade.matrix_world = matrix
    bpy.context.view_layer.update()
    for name, position, energy, size in [('Key', (-.6, -.6, 2.3), 45, .8), ('Fill', (.5, .1, 2.0), 25, .7)]:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, 'AREA'))
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (matrix.translation-light.location).to_track_quat('-Z','Y').to_euler()
        light.data.energy = energy
        light.data.shape = 'DISK'
        light.data.size = size
    scene.world = bpy.data.worlds.new('GrenadeHands_Studio')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.18,.2,.24,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .35
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.render.resolution_x, scene.render.resolution_y = 1280,720
    scene.render.resolution_percentage = 100
    camera.data.clip_start = .005
    camera.data.lens = 28
    scene.render.image_settings.file_format = 'PNG'
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=True)
    report = {'arms_source': str(SOURCE), 'arms_source_sha256': sha(SOURCE), 'grenade_source': str(GRENADE),
              'grenade_source_sha256': sha(GRENADE), 'mesh': 'FPS_Arms', 'vertices': len(bpy.data.objects['FPS_Arms'].data.vertices),
              'bones': len(arm.pose.bones), 'poses': pose_report}
    (WORK/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    log('BUILD', BLEND, 'max wrist error', max(p['right_wrist_error'] for p in pose_report), max(p['left_wrist_error'] for p in pose_report))


def export():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    arm = bpy.data.objects['FPS_ArmsRig']
    mesh = bpy.data.objects['FPS_Arms']
    root = bpy.data.objects['Grenade']
    scene.frame_set(1)
    bpy.context.view_layer.update()
    to_grenade = root.matrix_world.inverted()
    sampled = []
    for index in range(31):
        scene.frame_set(index+1)
        bpy.context.view_layer.update()
        sampled.append({bone.name: arm.convert_space(pose_bone=bone,matrix=bone.matrix,from_space='POSE',to_space='LOCAL').copy() for bone in arm.pose.bones})
    arm.animation_data_clear()
    for bone in arm.pose.bones:
        for constraint in list(bone.constraints):
            bone.constraints.remove(constraint)
    action = bpy.data.actions.new('GrenadeHands_Pin')
    assign(arm, action)
    for index, poses in enumerate(sampled):
        for name, matrix in poses.items():
            bone = arm.pose.bones[name]
            bone.location, bone.rotation_quaternion, bone.scale = matrix.decompose()
            for prop in ('location','rotation_quaternion','scale'):
                bone.keyframe_insert(prop,frame=index+1)
    for curve in curves(action):
        for point in curve.keyframe_points:
            point.interpolation='LINEAR'
    assign(arm,None)
    track=arm.animation_data.nla_tracks.new()
    track.name='pin_pull'
    track.strips.new('pin_pull',1,action)
    for obj in list(bpy.data.objects):
        if obj not in (arm,mesh):
            bpy.data.objects.remove(obj,do_unlink=True)
    arm.matrix_world=to_grenade@arm.matrix_world
    scene.frame_set(1)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.export_scene.gltf(filepath=str(OUT/'grenade_veras_hands.glb'),export_format='GLB',use_selection=True,
                              export_yup=True,export_skins=True,export_all_influences=True,export_def_bones=False,
                              export_animations=True,export_animation_mode='NLA_TRACKS',export_force_sampling=True,
                              export_materials='EXPORT',export_image_format='AUTO',export_cameras=False,export_lights=False)
    credits()
    log('EXPORT',OUT/'grenade_veras_hands.glb')


def credits():
    path = ROOT / 'assets/CREDITS.md'
    marker = '## Руки ВЕРАС-54 с гранатой (2026-10-15)'
    text = path.read_text(encoding='utf8')
    if marker not in text:
        text += ('\n' + marker + '\n\n'
                 '`assets/models/weapons/grenade/grenade_veras_hands.glb` и карты `grenade_veras_hands_arm*` —\n'
                 'те же собственные FPS-руки, перчатки, рукава, UV и веса владельца проекта из\n'
                 '`VERAS54_Reload_Full_v05.blend`, которые используются у ВЕРАС-54. Исходник не изменялся.\n'
                 'Производный хват и извлечение чеки — `tools/prepare_grenade_hands.py`;\n'
                 'редактируемый файл — `_asset_src/grenade_hands/Grenade_VERAS_Hands.blend`.\n')
        path.write_text(text, encoding='utf8')
    # Godot извлекает три карты из GLB при первом импорте.
    for path in OUT.glob('grenade_veras_hands_*.png.import'):
        settings = path.read_text(encoding='utf8')
        settings = settings.replace('compress/mode=0', 'compress/mode=2')
        settings = settings.replace('detect_3d/compress_to=1', 'detect_3d/compress_to=0')
        settings = settings.replace('mipmaps/generate=false', 'mipmaps/generate=true')
        if 'Normal' in path.name:
            settings = settings.replace('compress/normal_map=0', 'compress/normal_map=1')
        path.write_text(settings, encoding='utf8')


def mesh_signature(obj):
    data = obj.data
    values = {'positions': [tuple(v.co) for v in data.vertices],
              'faces': [tuple(p.vertices) for p in data.polygons],
              'uv': [[tuple(loop.uv) for loop in uv.data] for uv in data.uv_layers],
              'groups': [group.name for group in obj.vertex_groups],
              'weights': [[(g.group, g.weight) for g in v.groups] for v in data.vertices]}
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def material_maps(obj):
    result = {}
    for slot in obj.material_slots:
        for node in slot.material.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image = node.image
                result[node.name] = {'size': list(image.size), 'packed': bool(image.packed_file),
                                     'sha256': hashlib.sha256(image.packed_file.data).hexdigest() if image.packed_file else None}
    return result


def audit():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    arm, mesh = bpy.data.objects['FPS_ArmsRig'], bpy.data.objects['FPS_Arms']
    grenade = bpy.data.objects['Grenade']
    checks = {}
    build_report = json.loads((WORK/'build_report.json').read_text(encoding='utf8'))
    checks['source_hands_unchanged'] = sha(SOURCE) == build_report['arms_source_sha256']
    checks['source_grenade_unchanged'] = sha(GRENADE) == build_report['grenade_source_sha256']
    checks['skin'] = any(m.type == 'ARMATURE' and m.object == arm for m in mesh.modifiers)
    checks['right_hand_attachment'] = grenade.parent == arm and grenade.parent_bone == 'hand.R'
    checks['separate_pin_lever'] = all(bpy.data.objects.get(name) for name in ('Pin','Lever','LP_SafetyPin'))
    checks['pin_morph'] = 'SplitTips_Compress' in bpy.data.objects['LP_SafetyPin'].data.shape_keys.key_blocks
    poses, first_right = [], None
    for index in range(31):
        scene.frame_set(index+1)
        bpy.context.view_layer.update()
        amount = index / 30
        right = world(arm, 'hand.R')
        if first_right is None:
            first_right = right.copy()
        travel = .0006 * min(1, amount/.16) + .0514 * max(0, (amount-.16)/.84)
        ring = grenade.matrix_world @ Vector((.0295, -.0122-travel, .0475))
        tip = arm.matrix_world @ arm.pose.bones['f_index.03.L'].tail
        poses.append({'progress': amount, 'right_wrist_drift_m': (right.translation-first_right.translation).length,
                      'right_wrist_rotation_rad': right.to_quaternion().rotation_difference(first_right.to_quaternion()).angle,
                      'left_index_to_ring_m': (tip-ring).length})
    max_contact = max(p['left_index_to_ring_m'] for p in poses if p['progress'] >= .16)
    checks['ring_contact_after_approach'] = max_contact < .001
    checks['right_grip_fixed'] = all(p['right_wrist_drift_m'] < .0005 and p['right_wrist_rotation_rad'] < .001 for p in poses)
    # Сравнение именно с исходной сеткой/UV/весами, а не только с записанными количествами.
    with bpy.data.libraries.load(str(SOURCE), link=False) as (_, dst):
        dst.objects = ['FPS_ArmsRig','FPS_Arms']
    source_arm, source_mesh = dst.objects
    checks['original_mesh_uv_weights'] = mesh_signature(mesh) == mesh_signature(source_mesh)
    checks['original_maps'] = material_maps(mesh) == material_maps(source_mesh)
    checks['original_rest_bones'] = len(arm.data.bones) == len(source_arm.data.bones) == 60 and all(
        bone.name in source_arm.data.bones and bone.matrix_local == source_arm.data.bones[bone.name].matrix_local
        for bone in arm.data.bones)
    maps = material_maps(mesh)
    checks['packed_2k_maps'] = len(maps) == 3 and all(m['packed'] and m['size'] == [2048,2048] for m in maps.values())
    glb_path = OUT/'grenade_veras_hands.glb'
    data = glb_path.read_bytes()
    size = struct.unpack_from('<I',data,12)[0]
    gltf = json.loads(data[20:20+size])
    checks['glb_hands_only'] = len(gltf.get('meshes',[])) == 1 and len(gltf.get('skins',[])) == 1 and len(gltf['skins'][0]['joints']) == 60
    checks['glb_pin_clip'] = [a['name'] for a in gltf.get('animations',[])] == ['pin_pull']
    checks['glb_maps'] = len(gltf.get('images',[])) == 3 and len(gltf.get('materials',[])) == 1
    checks['glb_eight_weights'] = all('WEIGHTS_1' in primitive['attributes'] for primitive in gltf['meshes'][0]['primitives'])
    report = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
              'arms_source': str(SOURCE), 'arms_source_sha256': sha(SOURCE),
              'grenade_source_sha256': sha(GRENADE), 'editable_blend': str(BLEND.relative_to(ROOT)),
              'editable_blend_sha256': sha(BLEND), 'glb_sha256': sha(glb_path), 'glb_bytes': len(data),
              'vertices': len(mesh.data.vertices), 'triangles': sum(len(p.vertices)-2 for p in mesh.data.polygons),
              'bones': len(arm.data.bones), 'maps': maps, 'max_ring_contact_error_m': max_contact, 'poses': poses}
    (OUT/'hands_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    log('AUDIT',report['status'],len(checks),'checks; ring contact',max_contact,'m')
    assert all(checks.values()), {name: value for name,value in checks.items() if not value}


def stills():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    pref=bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type='OPTIX'
    pref.get_devices()
    for device in pref.devices:
        device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    for index in [1,31]:
        scene.frame_set(index)
        scene.render.filepath=str(WORK/f'hands_{index:02d}.png')
        bpy.ops.render.render(write_still=True)
        log('STILL',index)


def edit_files():
    """Две статичные копии для ручной правки. Повторный запуск не затирает файлы владельца."""
    entries = [('Grenade_VERAS_Grip_Edit_v01.blend', 1, 'Хват: чека вставлена'),
               ('Grenade_VERAS_Pin_Edit_v01.blend', 31, 'Чека вынута: левая кисть у кольца')]
    for name, _, _ in entries:
        if (WORK/name).exists():
            raise FileExistsError(f'Не перезаписываю файл для ручной правки: {WORK/name}')
    guide = '''РУКИ ВЕРАС-54 С ГРАНАТОЙ — ПРАВКА ХВАТА

Grenade_VERAS_Grip_Edit_v01.blend — исходный хват, чека вставлена.
Grenade_VERAS_Pin_Edit_v01.blend — чека вынута, левая кисть у кольца.
Оба файла статичные: ключи отключены, поза не сбрасывается от смены кадра.
Все изображения встроены. Исходники ВЕРАС-54 и гранаты не изменены.

Риг FPS_ArmsRig уже выбран в Pose Mode.
ik_hand.R / ik_hand.L: G — положение кисти, R — её поворот.
Пальцы: f_index / f_middle / f_ring / f_pinky, фаланги .01–.03, стороны .R / .L.
Большой палец: thumb.01–.03.R / .L. Пальцы сгибать поворотом R, без масштаба.
hand.R / hand.L управляются IK — для перемещения кистей использовать ik_hand.

Граната привязана к hand.R и следует за правой кистью.
Чтобы поправить предмет относительно ладони: Tab в Object Mode, объект Grenade.
Чека с кольцом: объект Pin. Скоба: Lever. Это отдельные узлы, не объединять с руками.
У LP_SafetyPin сохранён morph SplitTips_Compress для сжатия концов чеки.

Num 0 — исходная камера от первого лица. Num . — приблизить выбранную кость.
Для внешнего обзора выйти из камеры средней кнопкой мыши.
Автоключ выключен. Сохранять правки в этих файлах через Ctrl+S.

Grenade_VERAS_Hands.blend — отдельная исходная заготовка с клипом, кадры 1–31.
1: начальный хват; 6: кольцо взято; 31: чека вынута.
Файлы Grip_Edit / Pin_Edit сохраняют IK, а не запечённый экспортный скелет.
Их сохранение не меняет игру автоматически. Для игрового экспорта использовать
исправленные копии; повторный build пересоздаёт только первоначальную заготовку.
'''
    expected, report = {}, []
    for name, source_frame, label in entries:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND))
        bpy.context.preferences.use_preferences_save = False
        scene = bpy.context.scene
        scene.frame_set(source_frame)
        bpy.context.view_layer.update()
        arm = bpy.data.objects['FPS_ArmsRig']
        bases = {bone.name: bone.matrix_basis.copy() for bone in arm.pose.bones}
        for obj in scene.objects:
            obj.animation_data_clear()
            if obj.type == 'MESH' and obj.data.shape_keys:
                obj.data.shape_keys.animation_data_clear()
        for name_bone, basis in bases.items():
            arm.pose.bones[name_bone].matrix_basis = basis
        scene.frame_start = scene.frame_end = 1
        scene.frame_set(1)
        scene.tool_settings.use_keyframe_insert_auto = False
        scene['grip_edit_pose'] = label
        scene['grip_edit_source_frame'] = source_frame
        notes = bpy.data.texts.get('НАЧАТЬ_ХВАТ.txt') or bpy.data.texts.new('НАЧАТЬ_ХВАТ.txt')
        notes.clear()
        notes.write(guide)
        bpy.ops.object.select_all(action='DESELECT')
        arm.hide_set(False)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        arm.show_in_front = True
        arm.data.display_type = 'STICK'
        for bone in arm.data.bones:
            bone.hide = False
            bone.hide_select = False
            arm.pose.bones[bone.name].select = bone.name in ('ik_hand.R','ik_hand.L')
        arm.data.bones.active = arm.data.bones['ik_hand.R']
        bpy.ops.object.mode_set(mode='POSE')
        for obj in scene.objects:
            if obj.type == 'LIGHT':
                obj.hide_set(True)
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.shading.type = 'MATERIAL'
                    space.overlay.show_floor = False
                    space.overlay.show_relationship_lines = False
                    space.region_3d.view_perspective = 'CAMERA'
                elif area.type == 'PROPERTIES':
                    area.spaces.active.context = 'DATA'
        bpy.context.view_layer.update()
        expected[name] = {side: world(arm, 'hand.'+side).translation.copy() for side in ('R','L')}
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=str(WORK/name),compress=True)
    # Проверяем точные выдаваемые файлы после повторного открытия.
    for name, _, label in entries:
        path = WORK/name
        bpy.ops.wm.open_mainfile(filepath=str(path))
        arm, mesh = bpy.data.objects['FPS_ArmsRig'], bpy.data.objects['FPS_Arms']
        bpy.context.view_layer.update()
        checks = {'pose_preserved': all((world(arm,'hand.'+side).translation-expected[name][side]).length < .0001 for side in ('R','L')),
                  'ik_editable': all(any(c.type == 'IK' for c in arm.pose.bones['forearm.'+side].constraints) for side in ('R','L')),
                  'static_pose': not arm.animation_data and not bpy.data.objects['Pin'].animation_data,
                  'packed_maps': all(m['packed'] for m in material_maps(mesh).values()),
                  'right_hand_parent': bpy.data.objects['Grenade'].parent_bone == 'hand.R',
                  'rig_60_bones': len(arm.data.bones) == 60,
                  'start_in_pose_mode': arm.mode == 'POSE',
                  'embedded_guide': bool(bpy.data.texts.get('НАЧАТЬ_ХВАТ.txt'))}
        assert all(checks.values()), (name,checks)
        report.append({'file':name,'pose':label,'bytes':path.stat().st_size,'sha256':sha(path),'checks':checks})
        log('EDIT_FILE PASS',path)
    (WORK/'НАЧАТЬ_ХВАТ.txt').write_text(guide,encoding='utf8')
    (WORK/'edit_files_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':
    WORK.mkdir(parents=True,exist_ok=True)
    stage=sys.argv[sys.argv.index('--')+1]
    globals()[stage]()
