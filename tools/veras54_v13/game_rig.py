"""ВЕРАС-54 v13: риг для клипов рук — прежние руки, хват владельца и риг оружия, детали — игровая сетка v13.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_v13/game_rig.py
(после game_lp.py и game_pack.py — материалы на готовых картах)
Основа — VERAS54_Charging_Hook_v01.blend (библиотека, «Перезарядка v01 (Claude)»; не меняется): руки FPS_ArmsRig с боевым хватом
владельца (action VERAS54_Grip_Manual_v02), поза файла — левая на магазине, правая крюком на рукоятке затвора (из неё
build_clips.py берёт хваты), риг оружия VERAS54_WeaponRig (кости WeaponRoot, Bolt, Selector, Trigger, MagazineLatch, DustCover,
CoverButton, StockFold, MuzzleAttachment, Magazine_Control → Magazine → MagazineFollower…) и свойства управления на VERAS54
(Bolt pull, Fire mode, Magazine latch press, Trigger pull…). Детали v11 заменяются игровой сеткой v13 (оси VERAS54 — те же).
Что меняется в риге под v13:
  ход рамы 74 → 100,6 мм (на предохранителе 72,9 — рукоятка упирается в лезвие переводчика); переводчик: «АВ» — поза модели,
  предохранитель −5°, «ОД» +7,85° (метки v13); ось спуска — у головок оси в коробке (93; −27 мм); защёлка магазина нажимается
  вперёд (к магазину); новая кость RecoilSpring — пружина сжимается рамой (масштаб по X от заднего конца);
  метка ChargingHandle у кости Bolt — середина рукоятки-крючка (по ней build_clips.py ведёт правую руку).
  Правая кисть позы файла сдвинута на разницу середин прежней рукоятки и крючка v13 (−4 мм по высоте).
→ E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Риг v13/VERAS54_Rig_v13.blend
Для просмотра владельцем в Blender библиотека самодостаточна: карты — копией в «Игровая версия/Карты v13» (на них ссылаются
материалы рига и клипов), игровая сетка с картами отдельно — «Геометрия v13/VERAS54_Game_v13.blend».
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import game_mats  # noqa: E402

ROOT = HERE.parents[1]
WORK = ROOT / '_asset_src/veras54_game_v13'
LIB = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия')
BASE = LIB / 'Перезарядка v01 (Claude)/VERAS54_Charging_Hook_v01.blend'
OUT = LIB / 'Риг v13/VERAS54_Rig_v13.blend'
LIB_MAPS = LIB / 'Карты v13'
LIB_GEO = LIB / 'Геометрия v13/VERAS54_Game_v13.blend'
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
KEEP = {'FPS_ArmsRig', 'FPS_Arms', 'VERAS54', 'VERAS54_WeaponRig', 'Magazine', 'Magazine_Rounds', 'FPS • Camera'}
BONE_OF = {'WeaponRoot': 'WeaponRoot', 'DustCover': 'DustCover', 'Bolt': 'Bolt', 'Selector': 'Selector', 'Trigger': 'Trigger',
           'MagazineLatch': 'MagazineLatch', 'CoverButton': 'CoverButton', 'StockFold': 'StockFold',
           'MuzzleAttachment': 'MuzzleAttachment', 'RecoilSpring': 'RecoilSpring', 'MagazineFollower': 'MagazineFollower'}
OLD_HANDLE = Vector((0.23001, -0.02882, 0.017485))     # середина прежней рукоятки (v11 «flattened shoe»), оси VERAS54
TRAVEL, SAFE_STOP = REC['bolt_travel_m'], REC['bolt_safety_m']
SPRING_LEN = REC['spring']['length']
# переводчик: «АВ» — поза модели v13; предохранитель на 5° выше, «ОД» на 7,85° ниже (метки на коробке; «2» — 3,92°)
SEL = {'safe': -0.0872665, 'auto': 0.0, 'single': 0.1370083}
log = lambda *a: print('VERAS_RIG', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
# карты — копией в библиотеку; игровая сетка с ними — отдельным файлом для просмотра
if game_mats.ready():
    LIB_MAPS.mkdir(parents=True, exist_ok=True)
    for f in game_mats.MAPS.glob('veras54_*.png'):
        shutil.copy2(f, LIB_MAPS / f.name)
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/VERAS54_Game_LP.blend'))
    log('review materials', game_mats.build_all(LIB_MAPS))
    LIB_GEO.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(LIB_GEO))
    log('SAVED', LIB_GEO)
bpy.ops.wm.open_mainfile(filepath=str(BASE))
S = bpy.context.scene
arms = bpy.data.objects['FPS_ArmsRig']
wr = bpy.data.objects['VERAS54_WeaponRig']
root = bpy.data.objects['VERAS54']
magob = bpy.data.objects['Magazine']
for o in (arms, wr, root, magob):
    if o.animation_data:
        o.animation_data.action = None
for pb in wr.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
for k, v in (('Bolt pull', 0.0), ('Fire mode', 1), ('Selector from mode', 1), ('Selector blend', 1.0), ('Magazine latch press', 0.0),
             ('Trigger pull', 0.0), ('Magazine removed', 0.0), ('Stock fold', 0.0), ('Cover button press', 0.0), ('Cover lift', 0.0)):
    if k in root.keys():
        root[k] = v
magob['Rounds remaining'] = 30
bpy.context.view_layer.update()

# ---------------------------------------------------------------- старые детали v11 — прочь
removed = 0
for o in list(bpy.data.objects):
    if o.name not in KEEP:
        bpy.data.objects.remove(o, do_unlink=True)
        removed += 1
for c in list(bpy.data.collections):
    if not c.all_objects:
        bpy.data.collections.remove(c)
bpy.ops.outliner.orphans_purge(do_recursive=True)
log('removed v11 objects', removed)

# ---------------------------------------------------------------- кости под v13
W = wr.matrix_world.inverted() @ root.matrix_world       # оси VERAS54 → пространство арматуры (постоянно)
bpy.context.view_layer.objects.active = wr
wr.hide_set(False)
wr.hide_viewport = False
bpy.ops.object.mode_set(mode='EDIT')
eb = wr.data.edit_bones
step = eb['Trigger'].tail - eb['Trigger'].head
eb['Trigger'].head = W @ Vector(REC['pivots_m']['Trigger'])
eb['Trigger'].tail = eb['Trigger'].head + step
if 'RecoilSpring' not in eb:
    b = eb.new('RecoilSpring')
    b.parent = eb['WeaponRoot']
    b.use_deform = True
else:
    b = eb['RecoilSpring']
b.head = W @ Vector(REC['pivots_m']['RecoilSpring'])
b.tail = b.head + step
b.roll = eb['Trigger'].roll
bpy.ops.object.mode_set(mode='OBJECT')
wr.pose.bones['RecoilSpring'].rotation_mode = 'XYZ'

# ---------------------------------------------------------------- драйверы рига
expr = {
    ('pose.bones["Bolt"].location', 0): f'-min(min(max(pull,0),1)*{TRAVEL:.6f},{SAFE_STOP:.6f} if mode<0.5 else {TRAVEL:.6f})',
    ('pose.bones["Selector"].rotation_euler', 1):
        f'({SEL["safe"]} if previous<.5 else ({SEL["auto"]} if previous<1.5 else {SEL["single"]}))*(1-(min(max(blend,0),1)))'
        f'+({SEL["safe"]} if mode<.5 else ({SEL["auto"]} if mode<1.5 else {SEL["single"]}))*(min(max(blend,0),1))',
    # защёлку жмут вперёд, к магазину (упором нового магазина или пальцем)
    ('pose.bones["MagazineLatch"].rotation_euler', 1): '-.20*min(max(v,0),1)',
}
bolt_vars = None
for fc in wr.animation_data.drivers:
    key = (fc.data_path, fc.array_index)
    if key in expr:
        fc.driver.expression = expr[key]
        log('driver', key, fc.driver.expression)
    if key == ('pose.bones["Bolt"].location', 0):
        bolt_vars = [(v.name, v.targets[0].id, v.targets[0].data_path) for v in fc.driver.variables]
# пружина: длина 164 мм сжимается на ход рамы (масштаб по X от заднего конца — головы кости)
pb = wr.pose.bones['RecoilSpring']
pb.driver_remove('scale', 0)
fc = pb.driver_add('scale', 0)
for name, idv, path in bolt_vars:
    v = fc.driver.variables.new()
    v.name, v.type = name, 'SINGLE_PROP'
    v.targets[0].id = idv
    v.targets[0].data_path = path
fc.driver.expression = (f'max(0.25,({SPRING_LEN:.4f}-min(min(max(pull,0),1)*{TRAVEL:.6f},{SAFE_STOP:.6f} if mode<0.5 else {TRAVEL:.6f}))'
                        f'/{SPRING_LEN:.4f})')
wr['bolt_visual_stroke_m'] = TRAVEL
wr['status'] = 'Риг v13 (2026-10-19): игровая сетка v13, ход рамы 100,6 мм (предохранитель — 72,9), пружина сжимается'
root['Geometry version'] = 'v13 игровая (low-poly с картами 100 % и масками износа), риг v13'
bpy.context.view_layer.update()

# ---------------------------------------------------------------- игровая сетка v13
LP = WORK / 'lp/VERAS54_Game_LP.blend'
with bpy.data.libraries.load(str(LP), link=False) as (src, dst):
    dst.objects = list(src.objects)
coll = bpy.data.collections.new('VERAS54 v13 • игровая сетка')
S.collection.children.link(coll)
for o in dst.objects:
    coll.objects.link(o)
bpy.context.view_layer.update()
RW = root.matrix_world.copy()
mag_rounds = bpy.data.objects['Magazine_Rounds']
node_of = {p: v['node'] for p, v in REC['parts'].items()}
placed = []
for o in dst.objects:
    world = RW @ o.matrix_world
    o.parent = None
    if o.name.startswith('Magazine • loaded'):
        o.parent = mag_rounds
    elif node_of.get(o.name) == 'Magazine':
        o.parent = magob
    else:
        o.parent = wr
        o.parent_type = 'BONE'
        o.parent_bone = BONE_OF[node_of[o.name]]
    bpy.context.view_layer.update()
    o.matrix_world = world
    placed.append(o.name)
# патроны прячутся по счёту, как в исходнике
for i in range(1, 31):
    for kind in ('case', 'projectile'):
        o = bpy.data.objects[f'Magazine • loaded {kind} {i}']
        for prop in ('hide_render', 'hide_viewport'):
            o.driver_remove(prop)
            d = o.driver_add(prop).driver
            d.type = 'SCRIPTED'
            v = d.variables.new()
            v.name, v.type = 'n', 'SINGLE_PROP'
            v.targets[0].id = magob
            v.targets[0].data_path = '["Rounds remaining"]'
            d.expression = f'n<{i}'
# метка рукоятки затвора (едет с рамой)
h = bpy.data.objects.new('ChargingHandle', None)
coll.objects.link(h)
h.empty_display_size = 0.01
h.parent = wr
h.parent_type = 'BONE'
h.parent_bone = 'Bolt'
bpy.context.view_layer.update()
h.matrix_world = RW @ Matrix.Translation(Vector(REC['markers_m']['ChargingHandle']))
# правая кисть позы файла — к новой рукоятке
delta = RW.to_3x3() @ (Vector(REC['markers_m']['ChargingHandle']) - OLD_HANDLE)
ik = arms.pose.bones['ik_hand.R']
m = ik.matrix.copy()
m.translation += arms.matrix_world.inverted().to_3x3() @ delta
ik.matrix = m
log('right hook shifted mm', [round(c * 1000, 1) for c in delta])
mats = game_mats.build_all(LIB_MAPS) if game_mats.ready(LIB_MAPS) else []
log('materials', mats)
bpy.context.view_layer.update()
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
log('SAVED', OUT, 'parts', len(placed))
