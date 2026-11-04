"""Read an owner's saved pose, retarget rest axes, and export phone-relative bone matrices."""
import hashlib, json, math, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grip_native import load_saved_pose

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/quest_phone/grip'
SOURCE = Path('E:/Models Blender/новые руки/Phone_Grip_starter_v01.blend')
if SOURCE.with_name('Phone_Grip_owner_v02.blend').exists(): SOURCE = SOURCE.with_name('Phone_Grip_owner_v02.blend')
if '--source' in sys.argv: SOURCE = Path(sys.argv[sys.argv.index('--source') + 1])
C = Matrix.Rotation(math.pi / 2, 4, 'X')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(m): return [list(row) for row in m]

source_hash = sha(SOURCE)
snapshot = WORK / ('owner_' + source_hash[:12] + '.blend')
if not snapshot.exists(): shutil.copy2(SOURCE, snapshot)
assert sha(snapshot) == source_hash, 'Source changed during snapshot'
scene, arm, saved_objects = load_saved_pose(snapshot)
reference = bpy.data.texts.get('RING_PHONE_RETARGET')
original = json.loads(reference.as_string() if reference else (WORK / 'phone_pose.json').read_text(encoding='utf8'))
phone = next(o for o in scene.objects if o.parent_type == 'BONE' and o.parent_bone == 'mixamorig_RightHand')
saved_phone = phone.matrix_world.copy()
saved_bones = {b.name: arm.matrix_world @ b.matrix for b in arm.pose.bones}
saved_local_rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
saved_frame = scene.frame_current
saved_pose_position = arm.data.pose_position
assert saved_pose_position == 'POSE', 'Owner file is in Rest Position'
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT / 'assets/models/characters/veras_arms.gltf'))
native = set(bpy.data.objects) - before
base_arm = next(o for o in native if o.type == 'ARMATURE')
base_rest = {b.name: base_arm.matrix_world @ b.matrix_local for b in base_arm.data.bones}
rest_error = max(max(abs(saved_local_rest[b.name][i][j] - b.matrix_local[i][j]) for i in range(4) for j in range(4)) for b in base_arm.data.bones)
assert rest_error < 1e-6, ('Rest changed; do not silently replace the rig', rest_error)
for o in native: o.hide_render = True; o.hide_set(True)
pairs = [(b, base_rest[b['name']]) for b in original['bones']]
g = np.array([[b['rest'][i][3] for i in range(3)] for b, _ in pairs])
n = np.array([list(m.translation) for _, m in pairs])
gc, nc = g.mean(0), n.mean(0)
u, _, vt = np.linalg.svd((g - gc).T @ (n - nc)); r = vt.T @ u.T
if np.linalg.det(r) < 0: vt[-1] *= -1; r = vt.T @ u.T
convert = Matrix.Identity(4); t = nc - r @ gc
for i in range(3):
    for j in range(3): convert[i][j] = float(r[i,j])
    convert[i][3] = float(t[i])
alignment_error = max((convert @ Vector([b['rest'][i][3] for i in range(3)]) - m.translation).length for b,m in pairs)
assert alignment_error < .00005
phone_g = convert.inverted() @ saved_phone @ C
assert max(abs(s - 1) for s in phone_g.to_scale()) < .001, ('Phone was scaled', list(phone_g.to_scale()))
bones, changes = [], []
for bone in original['bones']:
    name = bone['name']; rest_g = Matrix(bone['rest'])
    pose_g = convert.inverted() @ saved_bones[name] @ base_rest[name].inverted() @ convert @ rest_g
    relative = phone_g.inverted() @ pose_g
    bones.append({'name':name, 'phone_transform':rows(relative)})
    old = Matrix(bone['pose']); delta_mm = (pose_g.translation - old.translation).length * 1000
    delta_deg = math.degrees(old.to_quaternion().rotation_difference(pose_g.to_quaternion()).angle)
    delta_deg = min(delta_deg, abs(360 - delta_deg))
    if delta_mm > .01 or delta_deg > .01: changes.append({'bone':name,'position_mm':delta_mm,'rotation_deg':delta_deg})
data = {'version':1,'source':str(SOURCE),'sha256':source_hash,'frame':saved_frame,
        'axes':'Godot phone local: X width, Y up, +Z display; metres',
        'phone_in_camera':rows(phone_g),'bones':bones,
        'scale_baked_in_pose':True,'note':'Owner pose: do not apply the 0.8 hand correction again or solve fingers over it.'}
report = {'source':str(SOURCE),'sha256':source_hash,'snapshot':str(snapshot),'frame':saved_frame,
          'bones':len(bones),'rest_error':rest_error,'alignment_error_m':alignment_error,
          'changed_bones':changes,'right_hand_global_scale':list((convert.inverted() @ saved_bones['mixamorig_RightHand']).to_scale())}
(WORK / 'owner_pose_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
if '--export' in sys.argv:
    (ROOT / 'data/phone_grip_pose.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
# Review the captured pose in memory; never resave the owner's file.
arm.animation_data_clear()
for b in arm.data.bones:
    arm.pose.bones[b.name].matrix = arm.matrix_world.inverted() @ saved_bones[b.name]
    bpy.context.view_layer.update()
for camera, tag in ([] if '--no-render' in sys.argv else [('02 — Осмотр хвата','inspect'),('03 — Пальцы сзади','back')]):
    scene.camera = bpy.data.objects[camera]
    scene.render.filepath = str(ROOT / 'docs/screens' / ('phone_grip_owner_' + tag + '.png'))
    bpy.ops.render.render(write_still=True)
print('OWNER PHONE POSE',json.dumps(report,ensure_ascii=False),flush=True)
