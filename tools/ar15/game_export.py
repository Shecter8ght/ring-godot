"""AR-15 «ГРАНЬ-15»: игровая сетка (game_lp.py) с картами (game_pack.py) → glTF игры — как у ВСС-М
(tools/vss_m_v8/game_export.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/ar15/game_export.py
→ assets/models/weapons/ar15/:
  ar15.gltf — винтовка: узлы <Узел>_<Атлас> (подвижные и съёмные детали — свои узлы с началом в оси мовера исходника:
    BoltCarrier_Steel, Bolt_Steel, ChargingHandle_Receiver, ChLatchL/R_Receiver, DustCover_Receiver, ForwardAssist_…,
    Trigger_…, Selector_…, MagCatch_…, MagReleaseL_…, BoltCatch_…, PivotPin_…, TakedownPin_…, Stock_Polymer,
    StockLatch_Polymer, RearSightLeaf_…, RearAperture_…, FrontSightLeaf_…), Magazine (магазин в гнезде, начало —
    точка гнезда), метки Muzzle, SightRear, SightFront;
  ar15_mag30.gltf — магазин-предмет (начало — точка гнезда, как у метки mag модели);
  ar15_<Атлас>_100_{albedo,normal,orm}.png — общие карты; ar15.json — отчёт: треугольники, габарит, метки, ход
    механики и планки Picatinny с пазами — всё в осях игры.
Оси игры (как у ВСС-М и ВЕРАС-54): +Z — к дулу, +Y — вверх, −X — правая сторона стрелка, начало — середина хвата
пистолетной рукояти (game_lp: grip_m). Перевод из осей исходника — поворот на −90° вокруг Z и сдвиг к хвату; экспорт
Y-up. Мелкие LOD делает импорт Godot (генерация LOD сеток включена по умолчанию).
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/ar15/game'
MAPS = WORK / 'maps/game'
OUT = ROOT / 'assets/models/weapons/ar15'
OUT.mkdir(parents=True, exist_ok=True)
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
GRIP = Vector(REC['grip_m'])
TO_GAME = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-GRIP)
log = lambda *a: print('AR15_EXPORT', *a, flush=True)


def game_point(p) -> list:
    """Точка исходника (м) → оси игры (после экспорта Y-up): (y, z, x) от хвата."""
    q = Vector(p) - GRIP
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def build_material(atlas: str):
    tag = f'ar15_{atlas}_100'
    m = bpy.data.materials.get(f'AR15 • {atlas}') or bpy.data.materials.new(f'AR15 • {atlas}')
    m.name = f'AR15_{atlas}'
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


def rails_game() -> dict:
    """Планки Picatinny в осях игры: линия вершин зубьев (x, y), отрезок вдоль ствола z0…z1 по сегментам, середины
    пазов z (сокеты обвесов ставятся в паз), сторона зубьев."""
    out = {}
    for name, r in REC['rails_m'].items():
        up = Vector(r['up'])
        segs = []
        for s in r['segments']:
            # точка на линии вершин зубьев посередине планки (оси исходника): x — вдоль, по стороне — top_m, поперёк — side_m
            if abs(up.z) > 0.5:
                a = Vector((s['x0'], s['side_m'], s['top_m'] * up.z))
                b = Vector((s['x1'], s['side_m'], s['top_m'] * up.z))
            else:
                a = Vector((s['x0'], s['top_m'] * up.y, s['side_m']))
                b = Vector((s['x1'], s['top_m'] * up.y, s['side_m']))
            segs.append([game_point(a), game_point(b)])
        line = segs[0][0]
        out[name] = {'line_xy': line[:2], 'z': [[s[0][2], s[1][2]] for s in segs],
                     'slots_z': [round(x - GRIP.x, 5) for x in r['slots_x']],
                     'up': [round(up.y, 3), round(up.z, 3), round(up.x, 3)]}
    return out


def main():
    for f in MAPS.glob('ar15_*_100_*.png'):
        shutil.copy2(f, OUT / f.name)
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/AR15_Game_LP.blend'))
    for o in [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]:
        mat = build_material(o['atlas'])
        o.data.materials.clear()
        o.data.materials.append(mat)
        for uvl in list(o.data.uv_layers):
            if uvl.name != 'GameUV':
                o.data.uv_layers.remove(uvl)
        for a in ('uv_stack', 'uv_group'):
            if a in o.data.attributes:
                o.data.attributes.remove(o.data.attributes[a])
    rep = {'version': 'v1 (2026-10-30): геометрия v08, этап 1 «песок» v7 + износ этап 2 v1', 'source': REC['source'],
           'grip_source_m': REC['grip_m'], 'nodes': {}}
    # точка гнезда магазина — середина верха корпуса магазина (там, где он входит в шахту): мовер исходника стоит в
    # начале осей винтовки, точки гнезда не даёт
    mag = bpy.data.objects['Magazine']
    vs = [mag.matrix_world @ v.co for v in mag.data.vertices]
    top = max(v.z for v in vs)
    near = [v for v in vs if v.z > top - 0.004]
    mount = Vector((sum(v.x for v in near) / len(near), 0.0, top))
    # магазин-предмет: начало — точка гнезда, оси игры
    c = mag.copy()
    c.data = mag.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.data.transform(Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-mount))
    c.name = 'ar15_mag30'
    export(OUT / 'ar15_mag30.gltf', [c])
    rep['mag_item_tris'] = tris(c)
    bpy.data.objects.remove(c, do_unlink=True)
    rifle = [o for o in bpy.data.objects if o.type == 'MESH']
    pivots = {}
    for o in rifle:
        o.data.transform(TO_GAME)
        o.matrix_world = Matrix.Identity(4)
        rep['nodes'][o.name] = tris(o)
        piv = list(mount) if o.name == 'Magazine' else REC['nodes'].get(o.name, {}).get('pivot')
        if piv:
            pg = TO_GAME @ Vector(piv)
            o.data.transform(Matrix.Translation(-pg))
            o.location = pg
            pivots[o.name] = game_point(piv)
    rep['pivots_game_m'] = pivots
    marks = {k: game_point(v) for k, v in REC['marks_m'].items() if k != 'MagMount'}
    marks['MagMount'] = game_point(mount)
    for name in ('Muzzle', 'SightRear', 'SightFront'):
        rifle.append(empty(name, marks[name]))
    export(OUT / 'ar15.gltf', rifle)
    pts = [o.matrix_world @ v.co for o in rifle if o.type == 'MESH' for v in o.data.vertices]
    rep['size_game_m'] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in (0, 2, 1)]
    rep['tris_in_hands'] = sum(rep['nodes'].values())
    rep['marks_game_m'] = marks
    rep['rails_game'] = rails_game()
    # ход механики (оси игры): рама и рукоятка назад, отставание и поворот затвора, шторка, магазин, спуск
    act = {}
    for k, v in REC['action'].items():
        m = Vector(v['move_m'])
        act[k] = {'move': [round(m.y, 5), round(m.z, 5), round(m.x, 5)], 'rot_deg': v['rot_deg']}
    rep['action_game'] = act
    (OUT / 'ar15.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово', rep['tris_in_hands'], rep['size_game_m'])


main()
