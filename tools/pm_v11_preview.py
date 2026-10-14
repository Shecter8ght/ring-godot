"""Игровая сетка ПМ с запечёнными картами в той же студии (render_look): проверка запекания против high-poly.

blender --background --factory-startup --python-exit-code 1 --python preview_lp.py -- <maps_dir> <prefix> [views]
Собирает временную сцену: lp/PM_Game_LP_v01.blend + Principled на картах (color, metal, rough, normal).
Каналы, которых нет в папке, заменяются постоянными значениями (metal 1, rough 0.32).
"""
from pathlib import Path
import sys, subprocess, json
import bpy

REV = Path(__file__).resolve().parents[1] / '_asset_src/pm_game'   # рабочая папка ассета (не в git)
args = sys.argv[sys.argv.index('--') + 1:]
maps_list, prefix = [Path(x) for x in args[0].split(',')], args[1]
views = args[2] if len(args) > 2 else 'ref1,ref3,ref4,ref6'
bpy.ops.wm.open_mainfile(filepath=str(REV / 'lp/PM_Game_LP_v01.blend'))
for o in bpy.data.objects:
    if o.get('bake_only') or o.name in ('RoundChamber', 'JamCase'):
        o.hide_render = True
for m in bpy.data.materials:
    if not m.name.startswith('GAME •'):
        continue
    atlas = m.name.split(' • ')[1]
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(ch, cs):
        f = next((d / f'{atlas}_{ch}.png' for d in maps_list if (d / f'{atlas}_{ch}.png').exists()), None)
        if f is None:
            return None
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(f), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    c = tex('color', 'sRGB')
    if c:
        nt.links.new(c.outputs['Color'], p.inputs['Base Color'])
    mt = tex('metal', 'Non-Color')
    if mt:
        nt.links.new(mt.outputs['Color'], p.inputs['Metallic'])
    else:
        p.inputs['Metallic'].default_value = 1.0 if atlas != 'Grip' else 0.0
    r = tex('rough', 'Non-Color')
    if r:
        nt.links.new(r.outputs['Color'], p.inputs['Roughness'])
    else:
        p.inputs['Roughness'].default_value = 0.32
    n = tex('normal', 'Non-Color')
    if n:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.uv_map = 'GameUV'
        nt.links.new(n.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    if atlas == 'Grip':
        p.inputs['Coat Weight'].default_value = 0.65
        p.inputs['Coat Roughness'].default_value = 0.06
tmp = REV / f'work/_preview_{prefix}.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(tmp))
B = bpy.app.binary_path
subprocess.run([B, '--background', '--factory-startup', '--python-exit-code', '1', '--python', str(REV / 'work/render_look.py'), '--',
                '--file', str(tmp), '--views', views, '--prefix', prefix, '--no-lamps', '--cam-lights', '--hdri-strength', '0.9',
                '--samples', '64', '--width', '1100', '--out', str(REV / 'images')], check=True)
tmp.unlink()
print('PREVIEW_DONE', prefix, flush=True)
