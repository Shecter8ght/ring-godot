"""Файл хвата левой на магазине 45 / барабане 60 для ручной правки владельцем (он настраивает пальцы сам).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 "<Риг v13>/VERAS54_Rig_v13.blend" --python tools/veras54_mags/mags_grip_file.py -- m45|d60 [--force]
→ «ВЕРАС-54/Игровая версия/Хваты магазинов 45 и 60/VERAS54_Grip_<Mag45|Drum60>_v01.blend».
Основа — риг v13 автомата (game_rig.py, не меняется): руки FPS_ArmsRig в позе файла — правая крюком на рукоятке затвора,
левая держит магазин в шахте (с этого хвата начинаются все перезарядки), оружие VERAS54_WeaponRig. Штатный магазин заменён
игровой сеткой 45 / 60 (tools/veras54_mags, карты внутри) на той же пустышке Magazine (оси автомата, начало — точка
крепления), имена — как у штатного (Magazine_Body, «Magazine • loaded case N»), чтобы клипы автомата (build_clips.py)
строились от этого файла без правок. Поза левой — начальная: у 45 — как на штатном (верх магазина тот же), у барабана — кисть
вынесена влево на ширину барабана, пальцы раскрыты. Владелец правит ik_hand.L и пальцы *.L и сохраняет (Ctrl+S);
файл, который он уже правил, без --force не перезаписывается.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mags_game_common as C  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
MID = ARGS[0]
M = C.MAGS[MID]
LIB = C.LIB / 'ВЕРАС-54/Игровая версия/Хваты магазинов 45 и 60'
OUT = LIB / f'VERAS54_Grip_{M["atlas"]}_v01.blend'
if OUT.exists() and '--force' not in ARGS:
    raise SystemExit(f'{OUT} уже есть (владелец мог править) — не перезаписываю; --force — заново')
WORK = C.work(MID)
MAPS = WORK / 'game'
TAG = C.tag(MID)
log = lambda *a: print('MAGS_GRIP', MID, *a, flush=True)

magob = bpy.data.objects['Magazine']
arms = bpy.data.objects['FPS_ArmsRig']
for c in bpy.data.collections:
    if 'Suppressor' in c.name:
        c.hide_viewport = c.hide_render = True

# штатный магазин — прочь (корпус, сталь, патроны, подаватель на своей кости)


def under(ob, root) -> bool:
    q = ob.parent
    while q is not None:
        if q == root:
            return True
        q = q.parent
    return False


old = [o for o in bpy.data.objects if o.type == 'MESH' and (under(o, magob) or o.name == 'Magazine_Follower')]
for o in old:
    bpy.data.objects.remove(o, do_unlink=True)
log('штатный магазин убран, деталей', len(old))

# игровая сетка магазина — на пустышку Magazine (её оси = оси сетки)
want = ['Magazine', 'MagazineFollower', 'DrumKey'] + [f'Round_{i:02d}' for i in range(1, M['rounds'] + 1)]
with bpy.data.libraries.load(str(WORK / 'lp.blend'), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in want]
coll = next(c for c in bpy.data.collections if c.name.startswith('06'))
rename = {'Magazine': 'Magazine_Body', 'MagazineFollower': 'Magazine_Follower', 'DrumKey': 'Magazine • drum key'}
for o in dst.objects:
    base = o.name.split('.')[0] if o.name.startswith('Magazine.') else o.name
    local = o.matrix_world.copy()
    coll.objects.link(o)
    o.parent = magob
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = local
    if base.startswith('Round_'):
        o.name = f'Magazine • loaded case {int(base[6:])}'      # гильза + пуля одной сеткой; имя — как у штатных
    else:
        o.name = rename[base]

# материал на картах (как в игре), карты встроены
mat = bpy.data.materials[C.matname(MID)]
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
p = nt.nodes.new('ShaderNodeBsdfPrincipled')
nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
uv = nt.nodes.new('ShaderNodeUVMap')
uv.uv_map = 'GameUV'


def tex(kind: str, cs: str):
    t = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(str(MAPS / f'{TAG}_{kind}.png'), check_existing=True)
    img.colorspace_settings.name = cs
    img.pack()
    t.image = img
    nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
    return t


nt.links.new(tex('albedo', 'sRGB').outputs['Color'], p.inputs['Base Color'])
sep = nt.nodes.new('ShaderNodeSeparateColor')
nt.links.new(tex('orm', 'Non-Color').outputs['Color'], sep.inputs['Color'])
nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
nm = nt.nodes.new('ShaderNodeNormalMap')
nm.uv_map = 'GameUV'
nt.links.new(tex('normal', 'Non-Color').outputs['Color'], nm.inputs['Color'])
nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
nt.links.new(tex('emission', 'sRGB').outputs['Color'], p.inputs['Emission Color'])
p.inputs['Emission Strength'].default_value = 1.0

# начальная поза левой: у барабана — кисть левее на ширину барабана, пальцы раскрыты (владелец сомкнёт)
if MID == 'd60':
    ik = arms.pose.bones['ik_hand.L']
    ik.matrix = Matrix.Translation(Vector((0.038, 0.0, -0.01))) @ ik.matrix
    for pb in arms.pose.bones:
        if pb.name.endswith('.L') and pb.name.split('.')[0] in ('f_index', 'f_middle', 'f_ring', 'f_pinky', 'thumb'):
            pb.matrix_basis = Matrix.Identity(4).lerp(pb.matrix_basis, 0.35)
bpy.context.view_layer.update()

arms['Grip file'] = (f'{M["title"]}: хват левой для перезарядок (tools/veras54_mags/mags_grip_file.py). Править ik_hand.L и пальцы '
                     f'*.L в Pose Mode, сохранить — клипы перезарядки пересобираются от этой позы.')
txt = bpy.data.texts.get('КАК ПРАВИТЬ') or bpy.data.texts.new('КАК ПРАВИТЬ')
txt.from_string(
    f'ХВАТ ЛЕВОЙ НА МАГАЗИНЕ — {M["title"]}\n\n'
    'С этого хвата начинаются все перезарядки: тактическая, полная, быстрая (новым магазином выбить старый). Кисть держит\n'
    'магазин в шахте; дальше клип ведёт магазин и кисть вместе, с тем же положением пальцев.\n\n'
    'Арматура FPS_ArmsRig, Pose Mode. ik_hand.L — положение и поворот всей левой кисти (G / R);\n'
    'пальцы: f_index.01–03.L, f_middle.01–03.L, f_ring.01–03.L, f_pinky.01–03.L, thumb.01–03.L, palm.01/02.L — клавиша R.\n'
    'Правую кисть (крюк на рукоятке затвора) и оружие не трогать. Rest Position и Edit Mode не менять. Автоключ выключен.\n'
    'Numpad 0 — камера от первого лица. Сохранить Ctrl+S и написать в чат, что хват готов.\n')
bpy.ops.object.select_all(action='DESELECT')
arms.select_set(True)
bpy.context.view_layer.objects.active = arms
LIB.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
log('saved', OUT)
