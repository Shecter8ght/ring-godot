"""ВСС-М v8: игровая сетка (game_lp.py) с картами (game_pack.py) → glTF игры.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/game_export.py
→ assets/models/weapons/vss_m/:
  vss_m.gltf — винтовка: узлы Body_Steel / Body_Polymer / Body_Cerakote, Stock_Wood / Stock_Polymer / Stock_Steel
    (игра помечает part=stock), Magazine (магазин на 10 в гнезде, part=mag), метки Muzzle, SightRear, SightFront;
  vss_mag10.gltf, vss_mag20.gltf, vss_mag30.gltf — магазины-предметы (начало — точка гнезда, как у меток mag модели);
  vss_m_<Атлас>_100_{albedo,normal,orm}.png — общие карты; vss_m.json — отчёт (треугольники, размеры, метки).
Оси игры (как у ВЕРАС-54): +Z — к дулу, +Y — вверх, −X — правая сторона стрелка, начало — середина хвата в вырезе
приклада (game_lp.GRIP). Перевод из осей исходника — поворот на −90° вокруг Z и сдвиг к хвату; экспорт Y-up.
Мелкие LOD делает импорт Godot (генерация LOD сеток включена по умолчанию).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/vss_m_v8_game'
MAPS = WORK / 'maps/game'
OUT = ROOT / 'assets/models/weapons/vss_m'
OUT.mkdir(parents=True, exist_ok=True)
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
GRIP = Vector(REC['grip_m'])
TO_GAME = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-GRIP)
log = lambda *a: print('VSS_EXPORT', *a, flush=True)


def game_point(p) -> list:
    """Точка исходника (м) → оси игры (после экспорта Y-up): (y, z, x) от хвата."""
    q = Vector(p) - GRIP
    return [round(q.y, 5), round(q.z, 5), round(q.x, 5)]


def build_material(atlas: str):
    tag = f'vss_m_{atlas}_100'
    m = bpy.data.materials.get(f'VSS • {atlas}') or bpy.data.materials.new(f'VSS • {atlas}')
    m.name = f'VSS_{atlas}'
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
        img = bpy.data.images.load(str(MAPS / f'{tag}_{kind}.png'), check_existing=True)
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


def main():
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/VSS_Game_LP.blend'))
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
    rep = {'version': 'v8 (2026-10-26)', 'source': REC['source'], 'grip_source_m': REC['grip_m'], 'nodes': {}, 'mags': {}}
    mount = REC['marks_m']['MagMount']
    aside = {k: Vector(v) for k, v in REC['mag_aside_m'].items()}
    # магазины-предметы: начало — точка гнезда, оси игры
    for node in ('Mag10', 'Mag20', 'Mag30'):
        o = bpy.data.objects[node]
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        c.data.transform(Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-(Vector(mount) + aside[node])))
        c.name = node.lower().replace('mag', 'vss_mag')
        export(OUT / f'{c.name}.gltf', [c])
        rep['mags'][c.name] = {'tris': tris(c)}
        bpy.data.objects.remove(c, do_unlink=True)
    # винтовка: магазин на 10 — в гнездо
    mag = bpy.data.objects['Mag10']
    mag.data.transform(Matrix.Translation(-aside['Mag10']))
    mag.name = 'Magazine'
    for n in ('Mag20', 'Mag30'):
        bpy.data.objects.remove(bpy.data.objects[n], do_unlink=True)
    rifle = [o for o in bpy.data.objects if o.type == 'MESH']
    for o in rifle:
        o.data.transform(TO_GAME)
        o.matrix_world = Matrix.Identity(4)
        rep['nodes'][o.name] = tris(o)
    marks = {k: game_point(v) for k, v in REC['marks_m'].items()}
    for name in ('Muzzle', 'SightRear', 'SightFront'):
        rifle.append(empty(name, marks[name]))
    export(OUT / 'vss_m.gltf', rifle)
    pts = [v.co for o in rifle if o.type == 'MESH' for v in o.data.vertices]
    # габарит в осях игры [ширина x, высота y, длина z]: в Blender после TO_GAME высота — Z, длина — Y (glTF: Y вверх)
    rep['size_game_m'] = [round(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in (0, 2, 1)]
    rep['tris_in_hands'] = sum(rep['nodes'].values())
    rep['marks_game_m'] = marks
    (OUT / 'vss_m.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово', rep['tris_in_hands'], rep['size_game_m'])


main()
