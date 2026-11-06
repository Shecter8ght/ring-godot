"""ИЗЛОМ-45: игровая сетка (game_lp.py) с картами износа (Painter, этап 2) → glTF игры — как у ГРАНЬ-15
(tools/ar15/game_export.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/smg03/game_export.py [-- <папка карт>]
(карты по умолчанию — «Текстуры_этап2_v3» в папке модели: выгрузка Painter <Атлас>_baseColor / _occlusionRoughnessMetallic /
_normal) → assets/models/weapons/smg03/:
  smg03.gltf — оружие: узлы <Узел>_<Атлас> (подвижные и съёмные детали — свои узлы с началом в оси мовера исходника:
    Bolt_Steel, ChargingHandle_Steel, ChargingSlider_Steel, Trigger_Steel, SafetyL/R_Steel, SelectorL/R_Steel,
    MagReleaseL/R_Steel, BoltCatch_Steel, RearSightLeaf_Steel, FrontSightLeaf_Steel, Stock_Stock, StockLatch_Stock),
    Magazine (магазин на 13 в гнезде), MuzzleDevice (заглушка резьбы: обвес на резьбу её прячет), метки Muzzle,
    SightRear, SightFront;
  smg03_mag13.gltf, smg03_mag30.gltf — магазины-предметы (начало — точка гнезда);
  smg03_<Атлас>_100_{albedo,orm,normal}.png — карты; smg03.json — отчёт в осях игры: треугольники, габарит, метки,
    начала узлов, планки Picatinny с пазами, ход затвора, повороты флажков переводчика.
Оси игры (как у ГРАНЬ-15): +Z — к дулу, +Y — вверх, −X — правая сторона стрелка, начало — середина хвата пистолетной
рукояти. Исходник: дуло +X, левая сторона +Y, верх +Z (game_lp.py) — тот же поворот на −90° вокруг Z, экспорт Y-up.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/smg03/game'
MAPS = Path('E:/Models Blender/WEAPONS/Vector — модель/Текстуры_этап2_v3')
# магазины v2 (Glock 21 на 13 и с удлинителем на 30; приняты владельцем 06.11 с износом v2) — свои карты из своего
# проекта Painter (sp_smg03_mags.py), сетки — game_lp_mags.py → game_lp_mags_merge.py
MAGS_MAPS = Path('E:/Models Blender/WEAPONS/Vector — модель/Текстуры_магазины_v2_износ_v2')
MAG_ATLASES = ('Mag13', 'Mag30')
# точка гнезда магазина (м, исходник) — та же, что у магазинов v1 (smg03.json: MagMount): от неё сокет магазина в
# data/weapons.json, хват левой руки при перезарядке и начало моделей-предметов — с новыми магазинами не сдвигаются
MAG_MOUNT = Vector((-0.03546, 0.0, -0.0116))
OUT = ROOT / 'assets/models/weapons/smg03'
OUT.mkdir(parents=True, exist_ok=True)
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
# хват — середина пистолетной рукояти (контур th_grip: X −252…−172 мм, ладонь по высоте Z ≈ −35 мм; как у ГРАНЬ-15 —
# середина рукояти чуть выше середины её высоты)
GRIP = Vector((-0.2122, 0.0, -0.035))
TO_GAME = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-GRIP)
ATLASES = ('Upper', 'Lower', 'Steel', 'Stock', 'Mag13', 'Mag30')
MAP_KIND = {'baseColor': 'albedo', 'occlusionRoughnessMetallic': 'orm', 'normal': 'normal'}
# планки (part_receiver.py, lib.py; мм исходника): верхняя X −262…104, верх зубьев Z 57.5, первый паз X 97.6, шаг 10;
# нижняя X 24…102.5, низ зубьев Z −29.5, первый паз 96.5; боковые X 26…103.5, середина Z 1.5, вершины зубьев на
# ±(21.75 + 7.5) по Y, первый паз 100
RAILS = {
    'RailTop': {'x': (-262.0, 104.0), 'first': 97.6, 'line': (0.0, 57.5), 'up': (0, 0, 1)},
    'RailBottom': {'x': (24.0, 102.5), 'first': 96.5, 'line': (0.0, -29.5), 'up': (0, 0, -1)},
    'RailLeft': {'x': (26.0, 103.5), 'first': 100.0, 'line': (29.25, 1.5), 'up': (0, 1, 0)},
    'RailRight': {'x': (26.0, 103.5), 'first': 100.0, 'line': (-29.25, 1.5), 'up': (0, -1, 0)},
}
SLOT_W = 5.23
BOLT_TRAVEL = 0.045                     # part_bolt.BOLT_TRAVEL, м
SELECTOR_DEG = 60.0                     # part_rig.SELECTOR_DEG: 0 «ОД», 0.5 «2», 1 «АВ»
log = lambda *a: print('SMG03_EXPORT', *a, flush=True)


def game_point(p) -> list:
    """Точка исходника (м) → оси игры (после экспорта Y-up): (y, z, x) от хвата."""
    q = Vector(p) - GRIP
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def copy_maps(folder: Path) -> None:
    for at in ATLASES:
        for src, kind in MAP_KIND.items():
            f = (MAGS_MAPS if at in MAG_ATLASES else folder) / f'{at}_{src}.png'
            if not f.exists():
                raise SystemExit(f'нет карты {f}')
            shutil.copy2(f, OUT / f'smg03_{at}_100_{kind}.png')
    log('карты скопированы из', folder)


def build_material(atlas: str):
    tag = f'smg03_{atlas}_100'
    m = bpy.data.materials.new(f'SMG03_{atlas}')
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


def empty(name, p_game):
    e = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(e)
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


def split_faces(o, names: set, new_name: str):
    """Грани деталей исходника names (атрибут hp_part — индекс в o['hp']) → отдельный объект new_name."""
    hp = list(o['hp'])
    idx = {i for i, n in enumerate(hp) if n in names}
    if not idx or 'hp_part' not in o.data.attributes:
        return None
    vals = [0] * len(o.data.polygons)
    o.data.attributes['hp_part'].data.foreach_get('value', vals)
    sel = [i for i, v in enumerate(vals) if v in idx]
    if not sel:
        return None
    c = o.copy()
    c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    for ob, keep in ((c, set(sel)), (o, set(range(len(vals))) - set(sel))):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
        bm.to_mesh(ob.data)
        bm.free()
    c.name = new_name
    c.data.name = new_name
    return c


def rails_game() -> dict:
    """Планки в осях игры: линия вершин зубьев (x, y), отрезок вдоль ствола, середины пазов z."""
    out = {}
    for name, r in RAILS.items():
        slots = []
        x = r['first']
        while x - SLOT_W / 2 > r['x'][0] + 2.0:
            slots.append(x)
            x -= 10.0
        y_mm, z_mm = r['line']
        a = game_point((r['x'][0] * 0.001, y_mm * 0.001, z_mm * 0.001))
        b = game_point((r['x'][1] * 0.001, y_mm * 0.001, z_mm * 0.001))
        up = r['up']
        out[name] = {'line_xy': a[:2], 'z': [[a[2], b[2]]],
                     'slots_z': sorted(round(s * 0.001 - GRIP.x, 5) for s in slots),
                     'up': [up[1], up[2], up[0]]}
    return out


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    copy_maps(Path(argv[0]) if argv else MAPS)
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/SMG03_Game_LP.blend'))
    mats = {at: build_material(at) for at in ATLASES}
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]:
        o.data.materials.clear()
        o.data.materials.append(mats[o['atlas']])
        for uvl in list(o.data.uv_layers):
            if uvl.name != 'GameUV':
                o.data.uv_layers.remove(uvl)
    # заглушка резьбы — своя деталь: на резьбу ставят обвес — она прячется (WeaponModels.apply_markers: MuzzleDevice)
    steel = bpy.data.objects['Receiver_Steel']
    cap = split_faces(steel, {'Thread_cap'}, 'MuzzleDevice')
    log('заглушка резьбы', 'выделена' if cap else 'НЕ НАЙДЕНА', tris(cap) if cap else 0)
    for o in [o for o in bpy.data.objects if o.type == 'MESH']:
        for a in ('uv_stack', 'uv_group', 'hp_part'):
            if a in o.data.attributes:
                o.data.attributes.remove(o.data.attributes[a])
    rep = {'version': 'v2 (2026-11-06): геометрия v06 (магазины — v07), игровая сетка v3 (магазины v2), отделка этап 1 '
                      'v4 + износ этап 2 v3; магазины — отделка и износ v2',
           'source': REC['source'], 'grip_source_m': list(GRIP), 'nodes': {}}
    # точка гнезда магазина — середина верха корпуса магазина на 13 (там, где он входит в шахту)
    mag13 = bpy.data.objects['Mag13']
    mag30 = bpy.data.objects['Mag30']
    vs = [mag13.matrix_world @ v.co for v in mag13.data.vertices]
    top = max(v.z for v in vs)
    near = [v for v in vs if v.z > top - 0.004]
    geo = Vector((sum(v.x for v in near) / len(near), 0.0, top))
    mount = MAG_MOUNT.copy()
    log('гнездо магазина (исходник, мм)', [round(c * 1000, 1) for c in mount], 'по верху сетки было бы',
        [round(c * 1000, 1) for c in geo])
    for src, name in ((mag13, 'smg03_mag13'), (mag30, 'smg03_mag30')):
        c = src.copy()
        c.data = src.data.copy()
        bpy.context.scene.collection.objects.link(c)
        c.data.transform(Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-mount) @ src.matrix_world)
        c.matrix_world = Matrix.Identity(4)
        c.name = name
        export(OUT / f'{name}.gltf', [c])
        rep[f'{name}_tris'] = tris(c)
        bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.objects.remove(mag30, do_unlink=True)
    mag13.name = 'Magazine'
    # дульный срез без заглушки (конец резьбы) — сюда встаёт обвес на резьбу; метка Muzzle — срез заглушки
    st_pts = [steel.matrix_world @ v.co for v in steel.data.vertices if abs(v.co.y) < 0.012 and abs(v.co.z) < 0.012]
    thread_tip = max(p.x for p in st_pts)
    cap_tip = max((cap.matrix_world @ v.co).x for v in cap.data.vertices) if cap else thread_tip
    log('конец резьбы / срез заглушки (мм)', round(thread_tip * 1000, 1), round(cap_tip * 1000, 1))
    gun = [o for o in bpy.data.objects if o.type == 'MESH']
    pivots = {}
    for o in gun:
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.transform(TO_GAME)
        rep['nodes'][o.name] = tris(o)
        piv = list(mount) if o.name == 'Magazine' else REC['nodes'].get(o.name, {}).get('pivot')
        if piv:
            pg = TO_GAME @ Vector(piv)
            o.data.transform(Matrix.Translation(-pg))
            o.location = pg
            pivots[o.name] = game_point(piv)
    rep['pivots_game_m'] = pivots
    marks = {k: game_point(v) for k, v in REC['marks_m'].items() if k != 'MagMount'}
    marks['Muzzle'] = game_point((cap_tip, 0.0, 0.0))
    marks['ThreadTip'] = game_point((thread_tip, 0.0, 0.0))
    marks['MagMount'] = game_point(mount)
    for name in ('Muzzle', 'SightRear', 'SightFront'):
        gun.append(empty(name, marks[name]))
    export(OUT / 'smg03.gltf', gun)
    pts = [o.matrix_world @ v.co for o in gun if o.type == 'MESH' for v in o.data.vertices]
    rep['size_game_m'] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in (0, 2, 1)]
    rep['tris_in_hands'] = sum(rep['nodes'].values())
    rep['marks_game_m'] = marks
    rep['rails_game'] = rails_game()
    # затвор: назад по −Z игры на свой ход (рукоятка заряжания на выстреле стоит — неподвижная); флажки переводчика —
    # вокруг оси флажков (+Y исходника = +X игры): «ОД» 0°, «2» 30°, «АВ» 60° (драйвер Selector_L/R)
    rep['action_game'] = {'bolt_travel_m': BOLT_TRAVEL,
                          'selector_deg': {'semi': 0.0, 'burst': SELECTOR_DEG * 0.5, 'auto': SELECTOR_DEG}}
    (OUT / 'smg03.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово: в руках', rep['tris_in_hands'], 'габарит', rep['size_game_m'])


main()
