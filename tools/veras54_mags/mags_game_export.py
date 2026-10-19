"""Магазин ВЕРАС-54 → игра: glTF с картами рядом (как модели автомата v13) и файл игровой версии для просмотра в Blender.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_mags/mags_game_export.py -- m45|d60
После mags_game_lp.py → mags_game_bake.py → mags_game_pack.py.
→ assets/models/weapons/veras54_mags/veras54_<mag45|drum60>.gltf (+ .bin) — игровая сетка целиком (в руках, вблизи);
  veras54_<…>_world.gltf — мировая: упрощена (world_ratio), из патронов только два верхних (остальные всегда в корпусе);
  карты veras54_<Атлас>_100_{albedo,normal,orm,emission}.png рядом (общие у обеих), маски жировой плёнки _coat кладёт pack;
  veras54_<…>.json — проверки (треугольники, габарит, узлы).
Оси игры: +Z к дулу, +Y вверх, −X — правая сторона стрелка (как мировая модель автомата); начало — точка крепления
магазина. Узлы: Magazine (корпус) → MagazineFollower / DrumKey, Round_01… (01 — верхний).
→ <библиотека>/<Магазин|Барабан>/Игровая версия/<Prefix>_Game_v01.blend — игровая сетка в осях автомата с материалами на
  картах (встроены) — владелец смотрит сам в Blender.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mags_game_common as C  # noqa: E402

MID = sys.argv[sys.argv.index('--') + 1]
M = C.MAGS[MID]
WORK = C.work(MID)
MAPS = WORK / 'game'
TAG = C.tag(MID)
NAME = {'m45': 'veras54_mag45', 'd60': 'veras54_drum60'}[MID]
REC = json.loads((WORK / 'parts.json').read_text(encoding='utf-8'))
log = lambda *a: print('MAGS_EXPORT', MID, *a, flush=True)


def material(m) -> None:
    """Principled на картах (как game_mats.py автомата); AO — через узел glTF Material Output."""
    nt = m.node_tree
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
        t.image = img
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    nt.links.new(tex('albedo', 'sRGB').outputs['Color'], p.inputs['Base Color'])
    orm = tex('orm', 'Non-Color')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.uv_map = 'GameUV'
    nt.links.new(tex('normal', 'Non-Color').outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    if (MAPS / f'{TAG}_emission.png').exists():
        nt.links.new(tex('emission', 'sRGB').outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
    g = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT']:
        g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = g
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])


def tris(objs) -> int:
    n = 0
    for o in objs:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH']


def export(path: Path) -> None:
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLTF_SEPARATE', export_texture_dir='', export_yup=True,
                              export_materials='EXPORT', export_image_format='AUTO', export_cameras=False,
                              export_lights=False, export_animations=False, export_apply=False)
    log('saved', path.name)


bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp.blend'))
mat = bpy.data.materials[C.matname(MID)]
mat.use_nodes = True
material(mat)
body = bpy.data.objects['Magazine']
# Подаватель по счёту патронов (у 45): стоит под последним патроном и поднимается по дуге вместе со стопкой —
# шаг стопки от патрона n к n−1 (Кабш по патронам), без бокового сдвига «шахматки»; 0 патронов — ещё шаг вверх.
follower_v = []
fol = bpy.data.objects.get('MagazineFollower')
if fol is not None:
    # начало узла — середина подавателя (в исходнике оно в начале автомата): сетка и развёртка на месте
    c = sum((v.co for v in fol.data.vertices), Vector()) / len(fol.data.vertices)
    fol.data.transform(Matrix.Translation(-c))
    fol.matrix_world = fol.matrix_world @ Matrix.Translation(c)
    bpy.context.view_layer.update()
    n_r = REC['rounds']['count']
    rm = {i: bpy.data.objects[f'Round_{i:02d}'].matrix_world.copy() for i in range(1, n_r + 1)}
    full = fol.matrix_world.copy()
    for n in range(n_r + 1):
        if n >= 1:
            m = rm[n] @ rm[n_r].inverted() @ full
        else:
            m = rm[1] @ rm[2].inverted() @ (rm[1] @ rm[n_r].inverted() @ full)
        m.translation.y = full.translation.y
        follower_v.append(m)
for o in meshes():
    if o is not body:
        mw = o.matrix_world.copy()
        o.parent = body
        o.matrix_world = mw

# файл игровой версии для владельца (оси автомата, карты внутри)
lib = Path(M['lib_dir'])
lib.mkdir(parents=True, exist_ok=True)
for im in bpy.data.images:
    if im.source == 'FILE' and not im.packed_file:
        im.pack()
body['Game version'] = (f'{M["title"]}: игровая сетка v01 (mags_game_lp.py), карты 2048 запечены с текстур v01 (приняты владельцем '
                        f'2026-10-19); в игре — {NAME}.gltf')
bpy.ops.wm.save_as_mainfile(filepath=str(lib / f'{M["prefix"]}_Game_v01.blend'), compress=True)
log('saved', lib / f'{M["prefix"]}_Game_v01.blend')

# оси игры: поворот −90° вокруг Z (дуло +X → −Y Blender → +Z glTF), начало — точка крепления
to_game = Matrix.Rotation(math.radians(-90), 4, 'Z')
body.matrix_world = to_game @ body.matrix_world
bpy.context.view_layer.update()
kids = {o: o.matrix_world.copy() for o in body.children}
with bpy.context.temp_override(object=body, active_object=body, selected_objects=[body], selected_editable_objects=[body]):
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False, properties=False, isolate_users=False)
bpy.context.view_layer.update()
for o, mw in kids.items():           # дочерние — на прежнее место в мире (поворот теперь в вершинах корпуса)
    o.matrix_world = mw
bpy.context.view_layer.update()
C.ASSET.mkdir(parents=True, exist_ok=True)
report = dict(model=NAME, title=M['title'], item=M['item'], source=REC['source'], source_sha256=REC['source_sha256'],
              axes='+Z к дулу, +Y вверх, −X — правая сторона стрелка; начало — точка крепления магазина',
              attach_in_veras54_m=list(C.ATTACH_IN_VERAS54), atlas=REC['atlas'], atlas_size=REC['atlas_size'],
              texel_px_mm=REC['texel_px_mm'], rounds=REC['rounds']['count'], rounds_detailed=REC['rounds']['detailed'],
              nodes=sorted(o.name for o in bpy.context.scene.objects if o.type in ('MESH', 'EMPTY')))
if follower_v:
    # в осях узла Magazine glTF (Y вверх): положение и поворот подавателя для 0…N патронов
    conv = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
    table = []
    for m in follower_v:
        local = body.matrix_world.inverted() @ (to_game @ m)
        g = conv @ local @ conv.inverted()
        q = g.to_quaternion()
        table.append([round(v, 6) for v in (*g.translation, q.x, q.y, q.z, q.w)])
    report['follower_by_rounds'] = table
bb = [body.matrix_world @ v.co for v in body.data.vertices]
report['size_m'] = [round(max(c[i] for c in bb) - min(c[i] for c in bb), 4) for i in range(3)]  # Blender X, Y, Z
report['tris'] = tris(meshes())
export(C.ASSET / f'{NAME}.gltf')

# мировая: упрощение и только два верхних патрона
for o in meshes():
    if o.name.startswith('Round_') and int(o.name[6:]) > C.ROUNDS_HI:
        bpy.data.objects.remove(o, do_unlink=True)
for o in meshes():
    if o.name.startswith('Round_'):
        continue
    d = o.modifiers.new('world', 'DECIMATE')
    d.ratio = M['world_ratio']
    d.use_collapse_triangulate = True
    with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
        bpy.ops.object.modifier_apply(modifier=d.name)
report['tris_world'] = tris(meshes())
export(C.ASSET / f'{NAME}_world.gltf')
(C.ASSET / f'{NAME}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
log('report', report['tris'], report['tris_world'], report['size_m'])
print('MAGS_EXPORT_DONE', MID, flush=True)
