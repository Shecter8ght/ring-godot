"""«Осока», текстуры этап 1 → файл просмотра владельцу в Blender: игровая сетка с развёрткой (work/osoka_game_uv_v01.blend)
с картами из Painter (выгрузка glTF: <набор>_baseColor / _occlusionRoughnessMetallic / _normal), студия прямо в файле
(tools/ar15/tex_apply.studio: HDRI только в отражениях, тёмный фон, мягкие источники, камера, Cycles, вьюпорт в
Rendered). Стекло купола и окон ракеты — тот же набор карт, но с пропусканием (поле render карточки GL-AR). Карты копируются
рядом с файлом и подключаются относительными путями. Риг OSOKA_Controls — как в игровой сетке.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/osoka/tex_review.py -- <папка карт> <выход.blend> [снимки <папка>]
"""
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ar15'))
sys.path.insert(0, str(ROOT / 'tools/osoka'))
import tex_apply  # noqa: E402

LP = Path('E:/Models Blender/WEAPONS/Верба — модель/work/osoka_game_uv_v01.blend')
SETS = ('Tube', 'Launcher', 'Missile')
TITLE = {'Tube': 'труба', 'Launcher': 'механизм', 'Missile': 'ракета'}


def material(atlas, folder, glass=False):
    m = bpy.data.materials.new(f'Осока • {TITLE[atlas]}' + (' • стекло' if glass else ''))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location = (600, 0)
    b.location = (300, 0)

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
    if glass:
        b.inputs['Transmission Weight'].default_value = 1.0
        b.inputs['IOR'].default_value = 1.5
    return m


def shots(out_dir, samples=48):
    S = bpy.context.scene
    S.cycles.samples = samples
    S.render.resolution_x, S.render.resolution_y = 1600, 900
    os.makedirs(out_dir, exist_ok=True)
    cam = S.camera
    keep = cam.matrix_world.copy()
    views = {'общий': ((1.9, -1.6, 0.9), (0.85, 0.0, -0.05), 40), 'слева': ((1.2, 1.3, 0.35), (1.15, 0.0, -0.07), 50),
             'механизм_слева': ((1.36, 0.55, 0.02), (1.3, 0.0, -0.08), 50),
             'механизм_справа': ((1.38, -0.55, 0.05), (1.3, 0.0, -0.08), 50),
             'перед': ((2.15, 0.45, 0.25), (1.62, 0.0, 0.0), 50), 'трафарет': ((0.72, 0.62, 0.40), (0.72, 0.0, 0.0), 50),
             'от_глаза': ((0.98, 0.10, 0.13), (1.6, 0.02, 0.0), 30)}
    for name, (loc, look, lens) in views.items():
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        S.render.filepath = os.path.join(out_dir, f'{name}.png')
        bpy.ops.render.render(write_still=True)
        print('SHOT', name)
    cam.matrix_world = keep


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    folder, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    shots_dir = a[3] if len(a) > 3 and a[2] == 'снимки' else None
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    S = bpy.context.scene
    S.unit_settings.system = 'METRIC'
    S.unit_settings.length_unit = 'MILLIMETERS'
    # карты — рядом с файлом просмотра (относительные пути)
    maps_dir = os.path.join(os.path.dirname(out), Path(out).stem + '_карты')
    os.makedirs(maps_dir, exist_ok=True)
    for f in os.listdir(folder):
        if f.endswith('.png'):
            shutil.copy2(os.path.join(folder, f), os.path.join(maps_dir, f))
    mats, glass = {}, {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials:
            continue
        at = o.data.materials[0].name.replace('Osoka_', '')
        if at not in SETS:
            continue
        is_glass = 'Lens' in str(o.get('finish_material', ''))
        pool = glass if is_glass else mats
        if at not in pool:
            pool[at] = material(at, maps_dir, glass=is_glass)
        o.data.materials.clear()
        o.data.materials.append(pool[at])
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
    tex_apply.CENTER = Vector((0.85, 0.0, -0.05))
    tex_apply.studio()
    cam = S.camera
    cam.location = Vector((0.85, 0.0, -0.05)) + Vector((0.55, -0.8, 0.35)).normalized() * 2.4
    cam.rotation_euler = (Vector((0.85, 0.0, -0.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    try:
        bpy.ops.file.make_paths_relative()
    except RuntimeError:
        pass
    if shots_dir:
        shots(shots_dir)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print('TEX_REVIEW_SAVED', out)


if __name__ == '__main__':
    main()
