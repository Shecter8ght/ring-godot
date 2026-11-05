"""ИЗЛОМ-45, текстуры этап 1 → файл просмотра владельцу в Blender: игровая сетка (SMG03_Game_LP.blend) с картами
из Painter (выгрузка glTF: <набор>_baseColor / _occlusionRoughnessMetallic / _normal), студия прямо в файле — как
у ГРАНЬ-15 (tools/ar15/tex_apply.py: HDRI только в отражениях, тёмный фон, мягкие источники, камера, Cycles, вьюпорт
в Rendered). Магазин на 30 — своя коллекция, скрыта (в руках — на 13). Карты — внешние PNG по относительным путям.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/tex_review.py -- <папка карт> <выход.blend>
"""
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ar15'))
import tex_apply  # noqa: E402

LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP.blend'


def material(atlas, folder):
    m = bpy.data.materials.new(f'ИЗЛОМ-45 • {atlas}')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location = (600, 0)
    b.location = (300, 0)
    if not os.path.exists(os.path.join(folder, f'{atlas}_baseColor.png')):
        b.inputs['Base Color'].default_value = (0.3, 0.3, 0.3, 1)
        b.inputs['Roughness'].default_value = 0.6
        return m

    def img(suffix, noncolor, y):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(os.path.join(folder, f'{atlas}_{suffix}.png'), check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
        t.interpolation = 'Cubic'
        t.location = (-500, y)
        return t
    uvn = nt.nodes.new('ShaderNodeUVMap')
    uvn.uv_map = 'GameUV'
    uvn.location = (-800, 0)
    bc = img('baseColor', False, 300)
    orm = img('occlusionRoughnessMetallic', True, 0)
    nm = img('normal', True, -300)
    for t in (bc, orm, nm):
        nt.links.new(uvn.outputs['UV'], t.inputs['Vector'])
    nt.links.new(bc.outputs[0], b.inputs['Base Color'])
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    sp.location = (-150, 0)
    nt.links.new(orm.outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.uv_map = 'GameUV'
    nmap.location = (-150, -300)
    nt.links.new(nm.outputs[0], nmap.inputs['Color'])
    nt.links.new(nmap.outputs[0], b.inputs['Normal'])
    return m


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    folder, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    S = bpy.context.scene
    S.unit_settings.system = 'METRIC'
    S.unit_settings.length_unit = 'MILLIMETERS'
    mats = {}
    game = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
    for o in game:
        at = o['atlas']
        if at not in mats:
            mats[at] = material(at, folder)
        o.data.materials.clear()
        o.data.materials.append(mats[at])
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
    coll = bpy.data.collections.get('LP')
    if coll is not None:
        coll.name = 'ИЗЛОМ-45 — игровая сетка'
    m30 = bpy.data.collections.new('Магазин на 30 (свой предмет)')
    S.collection.children.link(m30)
    for o in game:
        if o['atlas'] == 'Mag30':
            for c in list(o.users_collection):
                c.objects.unlink(o)
            m30.objects.link(o)
    for lc in bpy.context.view_layer.layer_collection.children:
        if lc.collection == m30:
            lc.hide_viewport = True
            m30.hide_render = True
    tex_apply.CENTER = Vector((-0.12, 0.0, 0.0))
    tex_apply.studio()
    try:
        bpy.ops.file.make_paths_relative()
    except RuntimeError:
        pass
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print('TEX_REVIEW_SAVED', out)


if __name__ == '__main__':
    main()
