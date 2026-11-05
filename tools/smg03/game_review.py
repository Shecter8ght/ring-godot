"""ИЗЛОМ-45: файл просмотра игровой сетки для владельца — игровые узлы с шахматкой по развёртке (GameUV), рядом
скрытая high-poly v06 для сравнения (коллекция «High-poly v06 (сравнение)», включается глазом в Outliner).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/game_review.py -- <выход.blend>
"""
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP.blend'
HP = Path('E:/Models Blender/WEAPONS/Vector — модель/ПП-Vector_геометрия_v06.blend')
out = sys.argv[sys.argv.index('--') + 1]

bpy.ops.wm.open_mainfile(filepath=str(LP))
sc = bpy.context.scene
sc.unit_settings.system = 'METRIC'
sc.unit_settings.length_unit = 'MILLIMETERS'
# шахматка: видна в режиме Solid → Texture и в Material Preview
img = bpy.data.images.new('Шахматка развёртки', 2048, 2048)
img.generated_type = 'COLOR_GRID'
for m in bpy.data.materials:
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'GameUV'
    nt.links.new(uvn.outputs['UV'], tex.inputs['Vector'])
    if bsdf is not None:
        nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nt.nodes.active = tex
lp_coll = bpy.data.collections.get('LP')
if lp_coll is not None:
    lp_coll.name = 'Игровая сетка v1'
for o in bpy.data.objects:
    if o.type == 'MESH' and 'GameUV' in o.data.uv_layers:
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
        if o.get('atlas') == 'Mag30':
            o.hide_set(True)
            o.hide_render = True
# high-poly для сравнения — скрыта
with bpy.data.libraries.load(str(HP)) as (src, dst):
    dst.objects = [n for n in src.objects]
hc = bpy.data.collections.new('High-poly v06 (сравнение)')
sc.collection.children.link(hc)
for ob in dst.objects:
    if ob is not None and ob.type == 'MESH':
        hc.objects.link(ob)
for lc in bpy.context.view_layer.layer_collection.children:
    if lc.collection == hc:
        lc.hide_viewport = True
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'SOLID'
                    sp.shading.color_type = 'TEXTURE'
                    sp.clip_start = 0.001
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print('REVIEW_SAVED', out)
