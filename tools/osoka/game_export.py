"""«Осока» (ПЗРК): принятая игровая сетка v01 с картами износа v1 → glTF игры (как у ИЗЛОМ-45, tools/smg03/game_export.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/osoka/game_export.py [-- <папка карт>]
Карты по умолчанию — «Осока_износ_этап2_v1_карты» в папке модели (выгрузка Painter <Набор>_baseColor /
_occlusionRoughnessMetallic / _normal, принятые владельцем 2026-11-06). Сетка — work/osoka_game_uv_v01.blend (развёртка
GameUV, риг OSOKA_Controls). → assets/models/weapons/osoka/:
  osoka.gltf — комплекс в руках: узлы <Узел>_<Набор>; подвижные — свои узлы с началом на оси исходника (Trigger, Lever,
    Button, Plunger, RearSight, FrontSight, DustCover, Power), отдельно — колпачок светового индикатора на целике
    (SightLamp: светится при захвате), крышки трубы (FrontCap, RearCap) и нос ракеты в трубе (MissileNose: виден в
    раструбе, после пуска прячется); метки Muzzle (срез раструба), Breech (задний торец трубы), SightRear (центр
    диоптра), SightFront (точка мушки), MissileMount (сопло ракеты в трубе);
  osoka_missile.gltf — ракета в полёте: корпус, четыре стабилизатора и два руля своими узлами на шарнирах (сложены,
    раскрывает игра — повороты в отчёте), начало — торец сопла, +Z — к носу;
  osoka_<Набор>_100_{albedo,orm,normal}.png — карты; osoka.json — отчёт в осях игры.
Оси игры (как у всех стволов): +Z — к дулу, +Y — вверх, −X — правая сторона стрелка, начало — середина хвата рукояти
пускового механизма. Исходник: +X вперёд, +Y влево, +Z вверх (asset-state.md) — поворот на −90° вокруг Z, экспорт Y-up.
"""
from __future__ import annotations

import fnmatch
import json
import math
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
MODEL = Path('E:/Models Blender/WEAPONS/Верба — модель')
LP = MODEL / 'work/osoka_game_uv_v01.blend'
MAPS = MODEL / 'Осока_износ_этап2_v1_карты'
OUT = ROOT / 'assets/models/weapons/osoka'
OUT.mkdir(parents=True, exist_ok=True)
ATLASES = ('Tube', 'Launcher', 'Missile')
MAP_KIND = {'baseColor': 'albedo', 'occlusionRoughnessMetallic': 'orm', 'normal': 'normal'}
MM = 0.001
# узлы комплекса: имя, шаблоны деталей исходника, деталь, чьё начало — ось узла (None — середина габарита)
NODES = [
    ('Trigger', ['Trigger'], 'Trigger'),
    ('Lever', ['Lever'], 'Lever'),
    ('Button', ['Button_cap'], None),
    ('Plunger', ['Plunger'], None),
    ('RearSight', ['Rear_sight_leaf'], 'Rear_sight_leaf'),
    ('SightLamp', ['Rear_sight_indicator'], None),
    ('FrontSight', ['Front_sight_leaf'], 'Front_sight_leaf'),
    ('DustCover', ['Dust_cover'], 'Dust_cover'),
    ('FrontCap', ['Front_cap*'], None),
    ('RearCap', ['Rear_cap*'], None),
    ('Power', ['Power_source'], 'Power_source'),
    ('MissileNose', ['Missile_dome', 'Missile_needle'], None),
]
MISSILE_NODES = [
    ('Fin0', ['Missile_fin_0'], 'Missile_fin_0'),
    ('Fin1', ['Missile_fin_1'], 'Missile_fin_1'),
    ('Fin2', ['Missile_fin_2'], 'Missile_fin_2'),
    ('Fin3', ['Missile_fin_3'], 'Missile_fin_3'),
    ('RudderTop', ['Missile_rudder_top'], 'Missile_rudder_top'),
    ('RudderBottom', ['Missile_rudder_bottom'], 'Missile_rudder_bottom'),
]
# метки (мм исходника): центр диоптра целика и точка мушки — из сборки part_saddle.py (rear_sight: пластина xa…xa+4.5,
# отверстие y = hy + 9, z 58; front_sight: кольцо (hx + 4, hy + 3, 27)); срез раструба — Tube_bell; торец сопла — MISSILE_X0
MARKS_MM = {
    'Muzzle': (1633.7, 0.0, 0.0),
    'Breech': (-2.0, 0.0, 0.0),
    'SightRear': (1174.95, 49.0, 58.0),
    'SightFront': (1451.6, 57.0, 27.0),
    'MissileMount': (18.0, 0.0, 0.0),
}
LEVER_DEG = 18.0           # dims.LEVER_TRAVEL_DEG: «ИСХОДНОЕ» → «НАКОЛ», вокруг +Y исходника = +X игры
TRIGGER_DEG = 10.0         # part_rig.TRIGGER_DEG
log = lambda *a: print('OSOKA_EXPORT', *a, flush=True)


def copy_maps(folder: Path) -> None:
    for at in ATLASES:
        for src, kind in MAP_KIND.items():
            f = folder / f'{at}_{src}.png'
            if not f.exists():
                raise SystemExit(f'нет карты {f}')
            shutil.copy2(f, OUT / f'osoka_{at}_100_{kind}.png')
    log('карты скопированы из', folder)


def build_material(atlas: str):
    tag = f'osoka_{atlas}_100'
    m = bpy.data.materials.new(f'OSOKA_{atlas}')
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
        img = bpy.data.images.load(str(OUT / f'{tag}_{kind}.png'), check_existing=True)
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


def atlas_of(o) -> str:
    return o.data.materials[0].name.replace('Osoka_', '') if o.data.materials else 'Launcher'


def world_copy(o, coll):
    """Оценённая копия детали в мировых координатах (поза рига), только развёртка GameUV; нормали детали сохраняются."""
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


# поворот комплекса вокруг хвата: линия прицеливания (центр диоптра → точка мушки) — по +Z игры. Мушка ниже диоптра
# на 31 мм на базе 277 мм и левее на 8: труба смотрит выше линии прицела на 6.4° и правее на 1.7° — как в сборке формы;
# камера в прицеливании ставит взгляд по +Z модели, ракета уходит по оси трубы (метки Breech → Muzzle)
ALIGN = Matrix.Identity(4)


def sight_align() -> Matrix:
    d = Vector(MARKS_MM['SightFront']) - Vector(MARKS_MM['SightRear'])
    return d.normalized().rotation_difference(Vector((1.0, 0.0, 0.0))).to_matrix().to_4x4()


def game_point(p, origin: Vector, align: bool = True) -> list:
    """Точка исходника (м) → оси игры: (y, z, x) от начала origin (у комплекса — с поворотом ALIGN)."""
    q = Vector(p) - origin
    if align:
        q = ALIGN @ q
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def to_game(origin: Vector, align: bool = True) -> Matrix:
    return Matrix.Rotation(math.radians(-90), 4, 'Z') @ (ALIGN if align else Matrix.Identity(4)) @ Matrix.Translation(-origin)


def empty(name, p_game, coll):
    e = bpy.data.objects.new(name, None)
    coll.objects.link(e)
    # точка в осях игры → обратно в оси Blender перед экспортом Y-up: (x, y, z)_игры = (x, z, −y)_Blender
    e.location = (p_game[0], -p_game[2], p_game[1])
    return e


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


def grip_center() -> Vector:
    """Середина хвата: сечение рукояти на высоте ладони (Z −175 ± 8 мм исходника; спуск — на 50 мм выше)."""
    g = bpy.data.objects['Launcher_grip']
    vs = [g.matrix_world @ v.co for v in g.data.vertices]
    band = [v for v in vs if abs(v.z * 1000.0 + 175.0) < 8.0]
    x = sum(v.x for v in band) / len(band)
    return Vector((round(x, 4), 0.0, -0.175))


def build_nodes(spec: list, objs: list, mats: dict, coll, origin: Vector, pivots: dict, rep_nodes: dict,
                align: bool = True) -> list:
    """Детали по узлам spec (остальное — в «Body») → сетки <Узел>_<Набор> в осях игры с началом на оси узла."""
    taken = set()
    groups = []
    for name, pats, piv in spec:
        part = [o for o in objs if any(fnmatch.fnmatchcase(o.name, p) for p in pats) and o.name not in taken]
        taken.update(o.name for o in part)
        groups.append((name, part, piv))
    groups.append(('Body', [o for o in objs if o.name not in taken], None))
    out = []
    tg = to_game(origin, align)
    for name, part, piv in groups:
        if not part:
            log('узел без деталей', name)
            continue
        by_atlas = {}
        for o in part:
            by_atlas.setdefault(atlas_of(o), []).append(o)
        for at, lst in sorted(by_atlas.items()):
            node = join([world_copy(o, coll) for o in lst], f'{name}_{at}')
            node.data.materials.clear()
            node.data.materials.append(mats[at])
            if piv:
                p = bpy.data.objects[piv].matrix_world.translation.copy()
            else:
                vs = [node.matrix_world @ v.co for v in node.data.vertices]
                p = Vector([(min(v[i] for v in vs) + max(v[i] for v in vs)) * 0.5 for i in range(3)])
            node.data.transform(tg)
            pg = tg @ p
            node.data.transform(Matrix.Translation(-pg))
            node.location = pg
            pivots[node.name] = game_point(p, origin, align)
            rep_nodes[node.name] = tris(node)
            out.append(node)
    return out


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    copy_maps(Path(argv[0]) if argv else MAPS)
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    ctrl = bpy.data.objects['OSOKA_Controls']
    for k in list(ctrl.keys()):
        if isinstance(ctrl[k], (int, float)):
            ctrl[k] = 1.0 if k in ('front_sight', 'rear_sight') else 0.0
    bpy.context.view_layer.update()
    mats = {at: build_material(at) for at in ATLASES}
    coll = bpy.data.collections.new('GAME')
    bpy.context.scene.collection.children.link(coll)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.polygons)]
    gun_src = [o for o in meshes if not o.name.startswith('Missile_') or o.name in ('Missile_dome', 'Missile_needle')]
    mis_src = [o for o in meshes if o.name.startswith('Missile_')]
    global ALIGN
    ALIGN = sight_align()
    origin = grip_center()
    log('середина хвата (исходник, мм)', [round(c * 1000, 1) for c in origin])
    rep = {'version': 'v1 (2026-11-06): форма v07, игровая сетка v01, отделка этап 1 v1 + износ этап 2 v1',
           'grip_source_m': list(origin), 'nodes': {}, 'missile_nodes': {}}
    pivots, mpivots = {}, {}
    gun = build_nodes(NODES, gun_src, mats, coll, origin, pivots, rep['nodes'])
    marks = {k: game_point(Vector(v) * MM, origin) for k, v in MARKS_MM.items()}
    for name, p in marks.items():
        gun.append(empty(name, p, coll))
    # ракета: начало — торец сопла в трубе (Missile_root), стабилизаторы и рули сложены (fins = 0)
    m_origin = bpy.data.objects['Missile_root'].matrix_world.translation.copy()
    missile = build_nodes(MISSILE_NODES, mis_src, mats, coll, m_origin, mpivots, rep['missile_nodes'], align=False)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in gun if o.type == 'MESH' for v in o.data.vertices]
    mpts = [o.matrix_world @ v.co for o in missile for v in o.data.vertices]
    export(OUT / 'osoka.gltf', gun)
    export(OUT / 'osoka_missile.gltf', missile)
    # габарит в осях игры (после поворота: Blender x = игры x, Blender −y = игры z, Blender z = игры y)
    size = lambda ps: [round(max(p[i] for p in ps) - min(p[i] for p in ps), 4) for i in (0, 2, 1)]
    rep['size_game_m'] = size(pts)
    rep['missile_size_game_m'] = size(mpts)
    rep['tris_in_hands'] = sum(rep['nodes'].values())
    rep['missile_tris'] = sum(rep['missile_nodes'].values())
    rep['pivots_game_m'] = pivots
    rep['missile_pivots_game_m'] = mpivots
    rep['marks_game_m'] = marks
    ax = Vector(MARKS_MM['Muzzle']) - Vector(MARKS_MM['Breech'])
    sl = Vector(MARKS_MM['SightFront']) - Vector(MARKS_MM['SightRear'])
    rep['tube_above_sight_deg'] = round(math.degrees(ax.angle(sl)), 2)
    # повороты в осях игры (поворот исходника вокруг +X — вокруг +Z игры, вокруг +Y — вокруг +X игры, знак тот же):
    # стабилизаторы раскрываются на −90° вокруг своей оси, параллельной корпусу; рули выходят из пазов — верхний на
    # +90°, нижний на −90° вокруг поперечной оси (part_rig.py, fins); рычаг «НАКОЛ» +18°, спуск +10° — вокруг +X
    rep['missile_deploy'] = {**{f'Fin{k}_Missile': {'axis': [0, 0, 1], 'deg': -90.0} for k in range(4)},
                             'RudderTop_Missile': {'axis': [1, 0, 0], 'deg': 90.0},
                             'RudderBottom_Missile': {'axis': [1, 0, 0], 'deg': -90.0}}
    rep['levers_game'] = {'Lever_Launcher': {'axis': [1, 0, 0], 'deg': LEVER_DEG},
                          'Trigger_Launcher': {'axis': [1, 0, 0], 'deg': TRIGGER_DEG}}
    (OUT / 'osoka.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово: в руках', rep['tris_in_hands'], 'ракета', rep['missile_tris'], 'габарит', rep['size_game_m'],
        'ракета', rep['missile_size_game_m'])


main()
