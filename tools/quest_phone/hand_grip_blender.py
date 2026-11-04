"""Editable phone grip copied from the runtime pose; accepted sources stay unchanged."""
import hashlib
import json
import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/quest_phone/grip'
SOURCE = Path('E:/Models Blender/PROPS/QuestPhone/game/QuestPhone_Game_v01.blend')
OUTPUT = Path('E:/Models Blender/новые руки/Phone_Grip_starter_v01.blend')
C = Matrix.Rotation(math.pi / 2, 4, 'X')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def align_rest(arm, bones):
    pairs = [(b, arm.matrix_world @ arm.data.bones[b['name']].matrix_local)
             for b in bones if b['name'] in arm.data.bones]
    g = np.array([[b['rest'][i][3] for i in range(3)] for b, _ in pairs])
    n = np.array([list(m.translation) for _, m in pairs])
    gc, nc = g.mean(0), n.mean(0)
    u, _, vt = np.linalg.svd((g - gc).T @ (n - nc))
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    t = nc - r @ gc
    result = Matrix.Identity(4)
    for i in range(3):
        for j in range(3): result[i][j] = float(r[i, j])
        result[i][3] = float(t[i])
    error = max((result @ Vector([b['rest'][i][3] for i in range(3)]) - m.translation).length for b, m in pairs)
    assert error < .00005, ('rest alignment', error)
    return result, error

def parent_to_hand(obj, arm):
    world = obj.matrix_world.copy()
    obj.parent = arm; obj.parent_type = 'BONE'; obj.parent_bone = 'mixamorig_RightHand'
    bpy.context.view_layer.update(); obj.matrix_world = world; bpy.context.view_layer.update()
    assert max(abs(obj.matrix_world[i][j] - world[i][j]) for i in range(4) for j in range(4)) < .00001

assert not OUTPUT.exists(), 'Keep the owner file; create a new named version instead'
sources = [SOURCE, ROOT / 'assets/models/characters/veras_arms.gltf', ROOT / 'assets/models/characters/veras_arms.bin']
hashes = {str(p): sha(p) for p in sources}
pose = json.loads((WORK / 'phone_pose.json').read_text(encoding='utf8'))
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene; scene.name = 'Телефон — правый хват'
phone_objects = set(scene.objects)
phone_roots = [ob for ob in phone_objects if ob.parent not in phone_objects]
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(sources[1]))
hands = set(bpy.data.objects) - before
arm = next(ob for ob in hands if ob.type == 'ARMATURE')
arm.name = 'Phone_Arms_Rig'
for ob in hands: ob.animation_data_clear()
arm.show_in_front = True; arm.data.display_type = 'STICK'
for bone in arm.pose.bones: bone.custom_shape = None
convert, rest_error = align_rest(arm, pose['bones'])
rest = {b.name: arm.matrix_world @ b.matrix_local for b in arm.data.bones}
rest_local = {b.name: [list(row) for row in b.matrix_local] for b in arm.data.bones}
desired = {}
for bone in pose['bones']:
    name = bone['name']
    if name not in rest: continue
    deform = convert @ Matrix(bone['pose']) @ Matrix(bone['rest']).inverted() @ convert.inverted()
    desired[name] = arm.matrix_world.inverted() @ deform @ rest[name]
for bone in arm.data.bones:
    if bone.name in desired:
        arm.pose.bones[bone.name].matrix = desired[bone.name]
        bpy.context.view_layer.update()
pose_error = max((arm.pose.bones[n].matrix.translation - m.translation).length for n, m in desired.items())
assert pose_error < .0001, ('pose transfer', pose_error)
action = bpy.data.actions.new('Phone_Grip_starter — кадр 1')
arm.animation_data_create(); arm.animation_data.action = action
for bone in arm.pose.bones:
    bone.rotation_mode = 'QUATERNION'
    for prop in ['location', 'rotation_quaternion', 'scale']:
        bone.keyframe_insert(data_path=prop, frame=1, group=bone.name)
for bone in arm.data.bones:
    bone.hide = 'Right' not in bone.name
correction = convert @ Matrix(pose['phone']) @ C.inverted()
for ob in phone_roots: ob.matrix_world = correction @ ob.matrix_world
bpy.context.view_layer.update()
phone = next(ob for ob in phone_roots if ob.name == 'QuestPhone')
parent_to_hand(phone, arm)
phone.name = 'Phone — следует правой кисти'
phone.empty_display_type = 'PLAIN_AXES'; phone.empty_display_size = .03
for ob in phone_objects:
    if ob.type == 'MESH': ob.hide_select = True
    elif ob.type == 'EMPTY': ob.empty_display_size = .004
phone.empty_display_size = .03
# Static native UI reference: useful for framing, not a live camera inside Blender.
screen = next(ob for ob in phone_objects if ob.name == 'DisplaySurface')
material = bpy.data.materials.new('Phone — снимок интерфейса для позирования')
material.use_nodes = True; nt = material.node_tree; bsdf = nt.nodes.get('Principled BSDF')
tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(str(WORK / 'phone_display.png'))
tex.image.pack(); nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(tex.outputs['Color'], bsdf.inputs['Emission Color']); bsdf.inputs['Emission Strength'].default_value = .5
bsdf.inputs['Roughness'].default_value = .12
screen.data.materials.clear(); screen.data.materials.append(material)
world = bpy.data.worlds.new('Phone — нейтральная студия'); world.use_nodes = True
world.node_tree.nodes['Background'].inputs[0].default_value = (.12, .15, .19, 1)
world.node_tree.nodes['Background'].inputs[1].default_value = .55; scene.world = world
target = convert @ Matrix(pose['phone']).translation
for index, offset in enumerate([(-.4, .3, .3), (.4, .15, .15)]):
    data = bpy.data.lights.new('Софтбокс ' + str(index + 1), 'AREA')
    light = bpy.data.objects.new(data.name, data); scene.collection.objects.link(light)
    light.location = convert @ Vector(offset)
    light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    data.energy = 45; data.shape = 'DISK'; data.size = .45
def camera(name, eye, at, lens):
    data = bpy.data.cameras.new(name); data.lens = lens; data.clip_start = .005
    ob = bpy.data.objects.new(name, data); scene.collection.objects.link(ob)
    ob.location = convert @ Vector(eye)
    ob.rotation_euler = ((convert @ Vector(at)) - ob.location).to_track_quat('-Z', 'Y').to_euler()
    return ob
centre = Matrix(pose['phone']).translation
inspection = camera('02 — Осмотр хвата', (.40, .05, -.06), centre, 48)
eye = camera('01 — Глаз игрока', (0, 0, 0), (0, 0, -.5), 28)
back = camera('03 — Пальцы сзади', (.25, .03, -.66), centre, 48)
scene.camera = inspection
scene.render.engine = 'CYCLES'; scene.cycles.samples = 24; scene.cycles.use_denoising = True
scene.render.resolution_x = 1280; scene.render.resolution_y = 900; scene.render.resolution_percentage = 100
scene.frame_start = 1; scene.frame_end = 1; scene.frame_set(1)
instructions = '''Телефон в правой руке — стартовая поза из игры, кадр 1.
Выбран Phone_Arms_Rig, Pose Mode. Правьте кости RightHand и RightHandThumb/Index/Middle/Ring/Pinky.
Остальные кости скрыты для удобства: Alt+H в Pose Mode вернёт их.
Телефон следует кости mixamorig_RightHand; пальцы гнутся независимо.
Положение телефона относительно ладони меняется объектом «Phone — следует правой кисти».
Сетки телефона защищены от случайного выбора, редактировать их для хвата не нужно.
Камеры: 01 — глаз игрока, 02 — осмотр, 03 — пальцы сзади.
Экран — неподвижный снимок интерфейса для позирования, не живая камера Blender.
После правки выделите изменённые кости, I → Location/Rotation/Scale на кадре 1 и сохраните копию.
Не применять Pose as Rest Pose, не менять имена костей, веса и rest-геометрию.
Изменения Blender не синхронизируются с Godot автоматически: готовый .blend надо перенести в игру.
Это стартовая поза, окончательный хват владельцем не принят.
'''
bpy.data.texts.new('00 — КАК ПРАВИТЬ ХВАТ').write(instructions)
arm['Инструкция'] = 'Pose Mode, кадр 1; текст 00 — КАК ПРАВИТЬ ХВАТ'
scene['Источник'] = 'Точная стартовая поза Phone из Godot; телефон game_v01, существующие veras_arms'
for image in bpy.data.images:
    if image.source == 'FILE' and not image.packed_file: image.pack()
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True); bpy.context.view_layer.objects.active = arm
arm.data.bones.active = arm.data.bones['mixamorig_RightHand']
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='DESELECT')
if hasattr(arm.pose.bones['mixamorig_RightHand'], 'select'):
    arm.pose.bones['mixamorig_RightHand'].select = True
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.shading.type = 'MATERIAL'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
arm = bpy.data.objects['Phone_Arms_Rig']
assert len([o for o in bpy.data.objects if o.type == 'ARMATURE']) == 1
assert all(list(map(list, arm.data.bones[n].matrix_local)) == rows for n, rows in rest_local.items())
assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE')
assert all(sha(Path(p)) == digest for p, digest in hashes.items()), 'Source modified'
report = {'output':str(OUTPUT), 'sha256':sha(OUTPUT), 'sources_unchanged':hashes,
          'bones':len(desired), 'rest_error_m':rest_error, 'pose_error_m':pose_error,
          'packed_images':len([im for im in bpy.data.images if im.packed_file]), 'frame':1,
          'status':'Starter for owner editing; not finally accepted; no automatic Godot sync'}
(WORK / 'blender_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
OUTPUT.with_suffix('.README.txt').write_text(instructions, encoding='utf8')
for view, name in [('02 — Осмотр хвата','inspect'),('03 — Пальцы сзади','back')]:
    bpy.context.scene.camera = bpy.data.objects[view]
    bpy.context.scene.render.filepath = str(ROOT / 'docs/screens' / ('phone_grip_blender_' + name + '.png'))
    bpy.ops.render.render(write_still=True)
print('PHONE EDITABLE GRIP SAVED AND REOPENED', json.dumps(report, ensure_ascii=False), flush=True)
