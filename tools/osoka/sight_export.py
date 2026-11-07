"""«Осока», тепловизор ПН-36Т «ПОЛЫНЬ»: принятая игровая сетка v01 с картами износа v1 → glTF игры (обвес optic_polyn_01,
как у «Осоки», tools/osoka/game_export.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/osoka/sight_export.py [-- <папка карт>]
Карты по умолчанию — «Тепловизор_износ_этап2_v1_карты» в папке прицела (выгрузка Painter Polyn_baseColor /
_occlusionRoughnessMetallic / _normal, износ принят владельцем 2026-11-07). Сетка — work/thermal_game_uv_v01.blend
(развёртка GameUV, риг THERMAL_Controls). → assets/models/attachments/polyn/:
  polyn.gltf — прицел: Body (корпус, кронштейн, оптика), BodyEyecup (резиновый наглазник — у глаза его прячет камера),
    BodyLever (рычажок переключателя с ручкой и винтом; начало — на оси, в покое — «ВЫКЛ»), BodyCap (крышка объектива
    с язычком и петлёй; начало — на оси петли, в покое закрыта), Body_LOD1 — весь прицел одной упрощённой сеткой;
  polyn_100_{albedo,orm,normal}.png — карты; polyn.json — отчёт в осях игры.
Оси игры — как у «Осоки» (+Z — линия прицеливания, +Y — вверх, −X — правая сторона стрелка): тот же поворот ALIGN
(линия диоптр → мушка по +Z, труба выше на 6,6°). Начало модели — точка крепления (середина лапы на основании сверху
трубы, sight_build.ROOT): игра ставит её в сокет optic_primary «Осоки» без поворота.
"""
from __future__ import annotations

import ast
import json
import math
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sight_build as SB  # noqa: E402  константы формы (точка крепления, оси окуляра и объектива, ход рычажка, крышки)

ROOT = HERE.parents[1]
MODEL = Path('E:/Models Blender/WEAPONS/Верба — модель')
SIGHT = MODEL / 'Тепловизор'
LP = SIGHT / 'work/thermal_game_uv_v01.blend'
OSOKA_LP = MODEL / 'work/osoka_game_uv_v01.blend'
MAPS = SIGHT / 'Тепловизор_износ_этап2_v1_карты'
OUT = ROOT / 'assets/models/attachments/polyn'
OSOKA_REP = ROOT / 'assets/models/weapons/osoka/osoka.json'
MAP_KIND = {'baseColor': 'albedo', 'occlusionRoughnessMetallic': 'orm', 'normal': 'normal'}
TAG = 'polyn_100'
MM = 0.001
# узлы: имя, детали, деталь, чьё начало — ось узла (None — начало модели)
NODES = [
    ('BodyLever', ['Thermal_switch_lever', 'Thermal_switch_knob', 'Thermal_switch_screw'], 'Thermal_switch_lever'),
    ('BodyCap', ['Thermal_cap', 'Thermal_cap_knuckle', 'Thermal_cap_tab', 'Thermal_cap_web'], 'Thermal_cap'),
    ('BodyEyecup', ['Thermal_eyecup'], None),
]
LOD1_TRIS = 2600
log = lambda *a: print('POLYN_EXPORT', *a, flush=True)


def osoka_marks() -> dict:
    """Метки «Осоки» (мм исходника) — из game_export.py (тот же поворот ALIGN, что у комплекса)."""
    tree = ast.parse((HERE / 'game_export.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'MARKS_MM' for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit('нет MARKS_MM в game_export.py')


MARKS = osoka_marks()
_d = Vector(MARKS['SightFront']) - Vector(MARKS['SightRear'])
ALIGN = _d.normalized().rotation_difference(Vector((1.0, 0.0, 0.0))).to_matrix().to_4x4()
# исходник → оси Blender перед экспортом Y-up (то же, что to_game у «Осоки», без переноса)
TO_GAME = Matrix.Rotation(math.radians(-90), 4, 'Z') @ ALIGN


def game_vec(v) -> list:
    """Вектор исходника → оси игры: (y, z, x) после поворота ALIGN."""
    q = ALIGN.to_3x3() @ Vector(v)
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def game_point_osoka(p_m, origin: Vector) -> list:
    return game_vec(Vector(p_m) - origin)


def sight_point(p_src_mm) -> Vector:
    """Точка в осях «Осоки» (мм) → в осях файла прицела (м, начало — точка крепления)."""
    return (Vector(p_src_mm) - Vector(SB.ROOT)) * MM


def copy_maps(folder: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for src, kind in MAP_KIND.items():
        f = folder / f'Polyn_{src}.png'
        if not f.exists():
            raise SystemExit(f'нет карты {f}')
        shutil.copy2(f, OUT / f'{TAG}_{kind}.png')
    log('карты скопированы из', folder)


def build_material():
    m = bpy.data.materials.new('POLYN')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind, cs):
        t = nt.nodes.new('ShaderNodeTexImage')
        img = bpy.data.images.load(str(OUT / f'{TAG}_{kind}.png'), check_existing=True)
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
    g = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT']:
        g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = g
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])
    return m


def tris(o) -> int:
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def world_copy(o, coll):
    """Оценённая копия детали в осях файла (поза рига), только развёртка GameUV; нормали детали сохраняются."""
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
    me.transform(oe.matrix_world)
    for lay in [u.name for u in me.uv_layers if u.name != 'GameUV']:
        me.uv_layers.remove(me.uv_layers[lay])
    for a in ('uv_stack', 'uv_group', 'hp_part', 'pid'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    ob = bpy.data.objects.new('c_' + o.name, me)
    coll.objects.link(ob)
    return ob


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def export(path: Path, objs: list) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLTF_SEPARATE', use_selection=True, export_apply=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
                              export_animations=False, export_skins=False, export_morph=False, export_extras=False,
                              export_image_format='AUTO', export_texture_dir='')
    log('записано', path.name)


def osoka_folds(origin: Vector) -> dict:
    """Откидные прицельные «Осоки» с прицелом на основании: оси листов (их Y в покое, драйверы part_rig.py) в осях
    игры. Целик складывается на −SIGHT_FOLD_DEG, мушка на +SIGHT_FOLD_DEG, колпачок индикатора — с целиком."""
    bpy.ops.wm.open_mainfile(filepath=str(OSOKA_LP))
    ctrl = bpy.data.objects['OSOKA_Controls']
    for k in list(ctrl.keys()):
        if isinstance(ctrl[k], (int, float)):
            ctrl[k] = 1.0 if k in ('front_sight', 'rear_sight') else 0.0
    bpy.context.view_layer.update()
    import part_rig
    out = {}
    for leaf, sign in (('Rear_sight_leaf', -1.0), ('Front_sight_leaf', 1.0)):
        ob = bpy.data.objects[leaf]
        axis = (ob.matrix_world.to_3x3().normalized() @ Vector((0.0, 1.0, 0.0))).normalized()
        out[leaf] = {'axis': game_vec(axis), 'deg': sign * part_rig.SIGHT_FOLD_DEG,
                     'pivot': game_point_osoka(ob.matrix_world.translation, origin)}
    return out


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    copy_maps(Path(argv[0]) if argv else MAPS)
    orep = json.loads(OSOKA_REP.read_text(encoding='utf-8'))
    origin = Vector(orep['grip_source_m'])
    folds = osoka_folds(origin)
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    ctrl = bpy.data.objects['THERMAL_Controls']
    ctrl['mode'] = 0.0      # в покое — «ВЫКЛ» (рычажок на +SW_DEG), крышка объектива закрыта
    ctrl['cap'] = 0.0
    ctrl.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    mat = build_material()
    coll = bpy.data.collections.new('GAME')
    bpy.context.scene.collection.children.link(coll)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.polygons)]
    taken = set()
    groups = []
    for name, pats, piv in NODES:
        part = [o for o in meshes if o.name in pats]
        taken.update(o.name for o in part)
        groups.append((name, part, piv))
    groups.append(('Body', [o for o in meshes if o.name not in taken], None))
    rep = {'version': 'v1 (2026-11-07): форма v03, игровая сетка v01, отделка этап 1 v1 + износ этап 2 v1',
           'nodes': {}, 'pivots_m': {}, 'axes': {}}
    nodes = []
    for name, part, piv in groups:
        node = join([world_copy(o, coll) for o in part], name)
        node.data.materials.clear()
        node.data.materials.append(mat)
        p = bpy.data.objects[piv].matrix_world.translation.copy() if piv else Vector((0.0, 0.0, 0.0))
        node.data.transform(TO_GAME)
        pg = TO_GAME @ p
        node.data.transform(Matrix.Translation(-pg))
        node.location = pg
        rep['pivots_m'][name] = game_vec(p)
        rep['nodes'][name] = tris(node)
        if piv:
            axis = (bpy.data.objects[piv].matrix_world.to_3x3().normalized() @ Vector((0.0, 1.0, 0.0))).normalized()
            rep['axes'][name] = game_vec(axis)
        nodes.append(node)
    # дальний вид: всё одной сеткой, упрощено до LOD1_TRIS
    lod_parts = []
    for name, part, piv in groups:
        lod_parts += [world_copy(o, coll) for o in part]
    lod = join(lod_parts, 'Body_LOD1')
    lod.data.materials.clear()
    lod.data.materials.append(mat)
    lod.data.transform(TO_GAME)
    full = tris(lod)
    dec = lod.modifiers.new('dec', 'DECIMATE')
    dec.decimate_type = 'COLLAPSE'
    dec.ratio = min(1.0, LOD1_TRIS / max(1, full))
    dec.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = lod
    bpy.ops.object.modifier_apply(modifier=dec.name)
    rep['lod1_tris'] = tris(lod)
    nodes.append(lod)
    bpy.context.view_layer.update()
    export(OUT / 'polyn.gltf', nodes)
    pts = [o.matrix_world @ v.co for o in nodes[:-1] for v in o.data.vertices]
    # габарит в осях игры (Blender x = игры x, Blender −y = игры z, Blender z = игры y)
    rep['size_game_m'] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in (0, 2, 1)]
    rep['tris_in_hands'] = sum(rep['nodes'].values())
    # точка крепления на «Осоке» (сокет optic_primary) и метки прицела в его осях (начало — точка крепления)
    rep['socket_on_osoka_m'] = game_point_osoka(Vector(SB.ROOT) * MM, origin)
    ocular_mm = (SB.XR - 22.4, SB.YC, SB.Z_EYE)       # центр задней поверхности линзы окуляра (sight_build.eyepiece)
    eye = bpy.data.objects['Thermal_eye_point'].matrix_world.translation
    obj = bpy.data.objects['Thermal_obj_axis'].matrix_world.translation
    day = bpy.data.objects['Thermal_day_lens']
    dvs = [day.matrix_world @ v.co for v in day.data.vertices]
    day_c = Vector([(min(v[i] for v in dvs) + max(v[i] for v in dvs)) * 0.5 for i in range(3)])
    rep['marks_m'] = {'Ocular': game_vec(sight_point(ocular_mm)), 'Eye': game_vec(eye), 'Objective': game_vec(obj),
                      'DayLens': game_vec(day_c)}
    rep['ocular_r_m'] = 0.0151                         # радиус линзы окуляра (sight_build.eyepiece, Thermal_eye_lens)
    rep['eye_relief_m'] = round((eye - sight_point(ocular_mm)).length, 4)
    # ход рычажка (driver: radians(SW_DEG) * (1 − 2·mode)) от покоя «ВЫКЛ»: «ДЕНЬ» −SW_DEG, «ТЕПЛО» −2·SW_DEG;
    # крышка объектива откидывается на −CAP_OPEN_DEG вокруг своей петли
    rep['lever_deg'] = {'off': 0.0, 'day': -SB.SW_DEG, 'thermal': -2.0 * SB.SW_DEG}
    rep['cap_open_deg'] = -SB.CAP_OPEN_DEG
    # откидные прицельные «Осоки»: узлы комплекса (game_export.py NODES) и их шарниры
    rep['osoka_folds'] = {'RearSight_Launcher': folds['Rear_sight_leaf'],
                          'SightLamp_Launcher': folds['Rear_sight_leaf'],
                          'FrontSight_Launcher': folds['Front_sight_leaf']}
    (OUT / 'polyn.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово: в руках', rep['tris_in_hands'], 'LOD1', rep['lod1_tris'], 'габарит', rep['size_game_m'],
        'сокет', rep['socket_on_osoka_m'], 'окуляр', rep['marks_m']['Ocular'], 'вынос глаза', rep['eye_relief_m'])


main()
