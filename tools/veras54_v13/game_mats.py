"""ВЕРАС-54 v13: игровые материалы на готовых картах (общие для рига клипов и экспорта).

Карты — _asset_src/veras54_game_v13/maps/game/veras54_<Атлас>_100_{albedo,normal,orm}.png (патрон — veras54_Ammo_…),
у магазина ещё _emission. Экспорт glTF кладёт их рядом с моделью под теми же именами — маски жировой плёнки
_coat (game_pack.py) лежат там же, игра находит их по имени карты цвета.
"""
from __future__ import annotations

from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
MAPS = ROOT / '_asset_src/veras54_game_v13/maps/game'
TAGS = {'GAME • Steel • 100': 'veras54_Steel_100', 'GAME • Polymer • 100': 'veras54_Polymer_100',
        'GAME • Magazine • 100': 'veras54_Magazine_100', 'GAME • Ammo': 'veras54_Ammo'}
EMISSION_STRENGTH = 0.35     # как у материала «13 • Luminous count marks» исходника


def ready(maps: Path = MAPS) -> bool:
    return all((maps / f'{t}_albedo.png').exists() for t in TAGS.values())


def build(name: str, maps: Path = MAPS) -> bool:
    """Материал name (если есть в файле) — Principled на картах из maps; AO — через узел glTF Material Output."""
    m = bpy.data.materials.get(name)
    tag = TAGS.get(name)
    if m is None or tag is None or not (maps / f'{tag}_albedo.png').exists():
        return False
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind: str, cs: str):
        t = nt.nodes.new('ShaderNodeTexImage')
        path = maps / f'{tag}_{kind}.png'
        img = bpy.data.images.load(str(path), check_existing=True)
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
    if (maps / f'{tag}_emission.png').exists():
        nt.links.new(tex('emission', 'sRGB').outputs['Color'], p.inputs['Emission Color'])
        p.inputs['Emission Strength'].default_value = 1.0
    g = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT']:
        g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = g
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])
    return True


def build_all(maps: Path = MAPS) -> list:
    return [n for n in TAGS if build(n, maps)]
