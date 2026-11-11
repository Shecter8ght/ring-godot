"""«Осока», тепловизор ПН-36Т «ПОЛЫНЬ», текстуры → файл просмотра владельцу в Blender (как tools/osoka/tex_review.py):
игровая сетка с развёрткой (work/thermal_game_uv_v01.blend) с картами Painter (glTF: Polyn_baseColor /
_occlusionRoughnessMetallic / _normal), студия прямо в файле (tools/ar15/tex_apply.studio: HDRI в отражениях, мягкие
источники, камера, Cycles, вьюпорт в Rendered). Линза объектива — те же карты и тонкая плёнка просветления (поле render
карточки GE-AR), стёкла окуляра и дневного канала — с пропусканием (GL-AR). Карты — копией рядом с файлом, пути
относительные. Риг THERMAL_Controls (mode — переключатель, cap — крышка объектива) — как в игровой сетке.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/osoka/sight_review.py -- <папка карт> <выход.blend> [снимки <папка>]
"""
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ar15'))
import tex_apply  # noqa: E402

LP = Path('E:/Models Blender/WEAPONS/Верба — модель/Тепловизор/work/thermal_game_uv_v01.blend')
ATLAS = 'Polyn'
CENTER = Vector((-0.015, 0.046, 0.09))


def material(folder, kind=''):
    m = bpy.data.materials.new('ПОЛЫНЬ' + (' • ' + kind if kind else ''))
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
        t.image = bpy.data.images.load(os.path.join(folder, f'{ATLAS}_{suffix}.png'), check_existing=True)
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
    if kind == 'стекло':
        b.inputs['Transmission Weight'].default_value = 1.0
        b.inputs['IOR'].default_value = 1.52
    if kind == 'германий':
        # просветление — тонкая плёнка (карточка GE-AR: 260 нм, n 1.38 — фиолетовый отлив; 160 нм давало янтарь);
        # в Godot — только цвет основы
        if 'Thin Film Thickness' in b.inputs:
            b.inputs['Thin Film Thickness'].default_value = 260.0
            b.inputs['Thin Film IOR'].default_value = 1.38
    return m


def shots(out_dir, samples=64):
    S = bpy.context.scene
    S.cycles.samples = samples
    S.render.resolution_x, S.render.resolution_y = 1600, 1000
    os.makedirs(out_dir, exist_ok=True)
    cam = S.camera
    keep = cam.matrix_world.copy()
    ctrl = bpy.data.objects.get('THERMAL_Controls')
    views = {
        'слева': ((-0.02, 0.62, 0.11), (-0.02, 0.05, 0.09), 50, {}),
        'спереди_слева': ((0.36, 0.38, 0.24), (0.0, 0.04, 0.09), 50, {}),
        'сзади_справа': ((-0.40, -0.30, 0.25), (-0.03, 0.04, 0.09), 50, {}),
        'надписи': ((-0.03, 0.36, 0.10), (-0.03, 0.10, 0.10), 60, {}),
        'объектив_крышка_откинута': ((0.34, 0.20, 0.16), (0.06, 0.05, 0.10), 60, {'cap': 1.0}),
        'окуляр': ((-0.30, 0.15, 0.14), (-0.12, 0.05, 0.085), 60, {}),
    }
    for name, (loc, look, lens, state) in views.items():
        if ctrl is not None:
            ctrl['cap'] = state.get('cap', 0.0)
            ctrl['mode'] = state.get('mode', 1.0)
            ctrl.update_tag()
            S.frame_set(1)
        cam.location = Vector(loc)
        cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = lens
        S.render.filepath = os.path.join(out_dir, f'{name}.png')
        bpy.ops.render.render(write_still=True)
        print('SHOT', name)
    if ctrl is not None:
        ctrl['cap'] = 0.0
        ctrl['mode'] = 1.0
        ctrl.update_tag()
        S.frame_set(1)
    cam.matrix_world = keep


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    folder, out = os.path.abspath(a[0]), os.path.abspath(a[1])
    shots_dir = a[3] if len(a) > 3 and a[2] == 'снимки' else None
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    S = bpy.context.scene
    S.unit_settings.system = 'METRIC'
    S.unit_settings.length_unit = 'MILLIMETERS'
    maps_dir = os.path.join(os.path.dirname(out), Path(out).stem + '_карты')
    os.makedirs(maps_dir, exist_ok=True)
    for f in os.listdir(folder):
        if f.endswith('.png'):
            shutil.copy2(os.path.join(folder, f), os.path.join(maps_dir, f))
    pool = {}
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.materials:
            continue
        fm = str(o.get('finish_material', ''))
        kind = 'германий' if 'Germanium' in fm else ('стекло' if 'Lens' in fm else '')
        if kind not in pool:
            pool[kind] = material(maps_dir, kind)
        o.data.materials.clear()
        o.data.materials.append(pool[kind])
        o.data.uv_layers.active = o.data.uv_layers['GameUV']
    tex_apply.CENTER = CENTER
    tex_apply.studio()
    cam = S.camera
    cam.location = CENTER + Vector((0.45, 0.75, 0.35)).normalized() * 0.75
    cam.rotation_euler = (CENTER - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 50
    try:
        bpy.ops.file.make_paths_relative()
    except RuntimeError:
        pass
    if shots_dir:
        shots(shots_dir)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=True)
    print('POLYN_REVIEW_SAVED', out)


if __name__ == '__main__':
    main()
