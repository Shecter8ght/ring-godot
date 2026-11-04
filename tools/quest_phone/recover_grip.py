"""Recover Ctrl+S pose property values and deliver a static editing copy with no Action."""
import hashlib, json, sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grip_native import load_saved_pose

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/quest_phone/grip'
SOURCE = Path('E:/Models Blender/новые руки/Phone_Grip_starter_v01.blend')
OUT = Path('E:/Models Blender/новые руки/Phone_Grip_owner_v02.blend')
if '--source' in sys.argv: SOURCE = Path(sys.argv[sys.argv.index('--source') + 1])
if '--output' in sys.argv: OUT = Path(sys.argv[sys.argv.index('--output') + 1])
assert not OUT.exists(), 'Never overwrite an owner editing file; use a new named version'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source_hash = sha(SOURCE)
scene, arm, objects = load_saved_pose(SOURCE)
assert arm.animation_data is None
expected = {b.name: [list(row) for row in b.matrix] for b in arm.pose.bones}
instructions = '''ВОССТАНОВЛЕННЫЙ ХВАТ ТЕЛЕФОНА
Пальцы восстановлены из сохранённых каналов исходного файла до применения старой анимации.
В этой копии нет активной анимации и ключей, которые могли бы сбросить ручную позу.

Выбрать Phone_Arms_Rig → Pose Mode. Править кисть и пальцы, затем просто Ctrl+S.
Клавишу I для статичного хвата нажимать не требуется.
Rest Position / Pose as Rest Pose не применять: игровые 80% уже содержатся в позе.
Телефон следует правой кисти. Экран — неподвижный снимок, используется только при позировании.
Камеры 01 — глаз игрока, 02 — осмотр хвата, 03 — пальцы сзади.
Перенос в игру выполняется отдельным шагом; автоматической синхронизации нет.
Исходный Phone_Grip_starter_v01.blend сохранён отдельно и не перезаписан.
'''
text = bpy.data.texts.get('00 — КАК ПРАВИТЬ ХВАТ') or bpy.data.texts.new('00 — КАК ПРАВИТЬ ХВАТ')
text.clear(); text.write(instructions)
reference = bpy.data.texts.get('RING_PHONE_RETARGET') or bpy.data.texts.new('RING_PHONE_RETARGET')
reference.clear(); reference.write((WORK / 'phone_pose.json').read_text(encoding='utf8'))
scene.name = 'Телефон — хват владельца'
scene['Источник сохранения'] = str(SOURCE)
scene['SHA исходника'] = source_hash
scene.frame_start = scene.frame_end = 1
scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1
for ob in objects: ob.select_set(False)
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
for image in bpy.data.images:
    if image.source == 'FILE' and not image.packed_file: image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
bpy.ops.wm.open_mainfile(filepath=str(OUT))
arm = bpy.data.objects['Phone_Arms_Rig']
assert arm.animation_data is None
def error():
    return max(abs(b.matrix[i][j] - expected[b.name][i][j]) for b in arm.pose.bones for i in range(4) for j in range(4))
reopen_error = error(); assert reopen_error < 1e-5, reopen_error
bpy.context.scene.frame_set(2); bpy.context.scene.frame_set(1)
frame_error = error(); assert frame_error < 1e-5, frame_error
assert all(im.packed_file for im in bpy.data.images if im.source == 'FILE')
assert sha(SOURCE) == source_hash
OUT.with_suffix('.README.txt').write_text(instructions, encoding='utf8')
report = {'source':str(SOURCE),'source_sha256':source_hash,'output':str(OUT),'sha256':sha(OUT),
          'method':'Append raw saved object pose channels; detach old Action before scene linking',
          'active_animation':False,'reopen_matrix_error':reopen_error,'frame_change_error':frame_error,
          'source_unchanged':True,'packed_images':len([i for i in bpy.data.images if i.packed_file])}
(WORK / 'recovery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('PHONE POSE RECOVERED',json.dumps(report,ensure_ascii=False),flush=True)
