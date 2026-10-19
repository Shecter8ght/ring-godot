"""Запекание карт игровой сетки ПМ с high-poly UCUPaint.

blender --background --factory-startup --python-exit-code 1 --python bake_state.py -- <kind> [--parts a,b] [--channels color,metal,rough,normal,ao] [--samples N] [--lp-rays]
  kind: 100 — атласы Steel и Grip из файла ПМ 100 % (вид в игре один, решение владельца 2026-10-19);
        mag — атлас Magazine из снаряжённого магазина 60%; ammo — атлас Ammo из патрона 60%.
Карты → maps/<kind>/<Atlas>_<channel>.png. Цвет — sRGB, остальное — Non-Color. Исходники не сохраняются.
--lp-rays — оставить игровым сеткам видимость для лучей (проверка: перекрывают ли они AO-маски).
"""
from pathlib import Path
import sys, json, argparse
import bpy
from mathutils import Matrix

REV = Path(__file__).resolve().parents[1] / '_asset_src/pm_game'   # рабочая папка ассета (не в git)
LIB = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
STATE_FILE = {'100': LIB / '18_Текстуры_v2_100_60_на_проверку/01_ПМ/PM_Textures_100_v02.blend',
              'mag': LIB / '19_Магазины_и_патрон_60_v01/01_Модели/magazine_loaded_60_v02.blend',
              'ammo': LIB / '19_Магазины_и_патрон_60_v01/01_Модели/cartridge_60_v01.blend',
              'supp': LIB / '19_Магазины_и_патрон_60_v01/01_Модели/suppressor_60_v01.blend'}
SIZE = {'Steel': 4096, 'Grip': 2048, 'Magazine': 1024, 'Ammo': 512, 'Suppressor': 2048}
ap = argparse.ArgumentParser()
ap.add_argument('kind')
ap.add_argument('--parts', default='')
ap.add_argument('--channels', default='color,metal,rough,normal')
ap.add_argument('--samples', type=int, default=32)
ap.add_argument('--lp-rays', action='store_true')
ap.add_argument('--tag', default='')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
REC = json.loads((REV / 'lp/parts.json').read_text(encoding='utf-8'))
ATLAS_PARTS = {'100': ('Steel', 'Grip'), 'mag': ('Magazine',), 'ammo': ('Ammo',), 'supp': ('Suppressor',)}[args.kind]
LP_NAME = {'Slide': 'Slide_Mesh', 'Frame': 'Frame_Mesh', 'Barrel': 'Barrel_Mesh', 'Hammer': 'Hammer_Mesh', 'Trigger': 'Trigger_Mesh',
           'Safety': 'Safety_Mesh', 'SlideStop': 'SlideStop_Mesh', 'MagCatch': 'MagCatch_Mesh', 'Grip': 'Grip_Mesh',
           'MagBody': 'Magazine_Mesh', 'Follower': 'Follower_Mesh', 'Spring': 'Spring_Mesh',
           'Case': 'LP_Case', 'Jacket': 'LP_Jacket', 'Primer': 'LP_Primer', 'Suppressor': 'Suppressor_Mesh'}
OUT = REV / 'maps' / (args.kind + args.tag)
OUT.mkdir(parents=True, exist_ok=True)
log = lambda *a: print('PM_BAKE', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
import addon_utils
addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
bpy.ops.wm.open_mainfile(filepath=str(STATE_FILE[args.kind]))
S = bpy.context.scene
S.frame_set(1)
rig = bpy.data.objects.get('PM_CONTROLS • select me')
if rig:
    for k in ('Slide', 'Hammer', 'Trigger', 'Safety', 'Magazine', 'MagCatch', 'SlideStop', 'Suppressor'):
        if k in rig.keys():
            rig[k] = 0.0
    rig.update_tag()
if args.kind == 'mag':
    root = next(o for o in bpy.data.objects if o.name.startswith('PM_magazine_loaded'))
    root.matrix_world = Matrix(REC['magazine_fit'])
if args.kind == 'supp':
    seat = Matrix(REC['suppressor_seat'])
    for o in bpy.data.objects:
        if o.parent is None and o.type in ('MESH', 'EMPTY') and o.type != 'CAMERA':
            o.matrix_world = seat @ o.matrix_world
bpy.context.view_layer.update()
# Лишнее из сцены ПМ не участвует ни как источник, ни в AO-масках (в игре этих деталей нет).
for o in bpy.data.objects:
    if o.name.startswith(('Suppressor', 'Highpoly |', 'Mount |', 'Reflex |', 'Magazine |', 'Magazine round', 'Studio |')) or o.type == 'LIGHT':
        o.hide_render = True
# Игровая сетка — из lp/PM_Game_LP_v01.blend.
with bpy.data.libraries.load(str(REV / 'lp/PM_Game_LP_v01.blend'), link=False) as (src, dst):
    dst.objects = list(src.objects)
lpc = bpy.data.collections.new('LP_BAKE')
S.collection.children.link(lpc)
for o in dst.objects:
    lpc.objects.link(o)
bpy.context.view_layer.update()
lp_meshes = [o for o in lpc.objects if o.type == 'MESH']
for o in lp_meshes:
    o.hide_render = False
    if not args.lp_rays:
        # Игровая сетка не должна затенять AO-маски high-poly: лучи её не видят.
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
        o.visible_volume_scatter = o.visible_shadow = False

S.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != 'CPU'
S.cycles.device = 'GPU'
S.cycles.samples = args.samples
S.cycles.use_denoising = False
bk = S.render.bake
bk.margin = 8
bk.margin_type = 'EXTEND'
bk.normal_space = 'TANGENT'
bk.use_selected_to_active = True
bk.use_cage = False
bk.cage_extrusion = 0.0015
bk.max_ray_distance = 0.004

images = {}


def target(atlas, channel):
    key = (atlas, channel)
    if key not in images:
        im = bpy.data.images.new(f'{atlas}_{channel}', SIZE[atlas], SIZE[atlas], alpha=False, float_buffer=(channel == 'normal'))
        im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        im.generated_color = (0.5, 0.5, 1.0, 1.0) if channel == 'normal' else (0, 0, 0, 1)
        images[key] = [im, False]
    return images[key]


def set_target(atlas, channel):
    im, used = target(atlas, channel)
    for o in lp_meshes:
        for m in o.data.materials:
            if m is None:
                continue
            nt = m.node_tree
            node = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
            node.name = 'BAKE_TARGET'
            node.image = im
            nt.nodes.active = node
    return images[(atlas, channel)]


def ypaint_group(mat):
    return next((n for n in mat.node_tree.nodes if n.type == 'GROUP' and n.node_tree and getattr(n.node_tree, 'yp', None)
                 and n.node_tree.yp.is_ypaint_node), None)


saved = {}


def route(channel):
    """Канал стека UCUPaint → Emission у всех материалов high-poly (для EMIT); normal — обратно BSDF."""
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.startswith('GAME •'):
            continue
        g = ypaint_group(m)
        out = next((n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
        if out is None:
            continue
        nt = m.node_tree
        if m.name not in saved:
            link = out.inputs['Surface'].links[0] if out.inputs['Surface'].links else None
            saved[m.name] = (link.from_socket if link else None)
        if channel == 'normal':
            if saved[m.name] is not None:
                nt.links.new(saved[m.name], out.inputs['Surface'])
            continue
        emit = nt.nodes.get('BAKE_EMIT') or nt.nodes.new('ShaderNodeEmission')
        emit.name = 'BAKE_EMIT'
        emit.inputs['Strength'].default_value = 1.0
        for l in list(emit.inputs['Color'].links):
            nt.links.remove(l)
        p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        sock_name = {'color': 'Color', 'metal': 'Metallic', 'rough': 'Roughness'}[channel]
        bsdf_name = {'color': 'Base Color', 'metal': 'Metallic', 'rough': 'Roughness'}[channel]
        if g is not None and sock_name in g.outputs:
            nt.links.new(g.outputs[sock_name], emit.inputs['Color'])
        elif p is not None:
            inp = p.inputs[bsdf_name]
            if inp.links:
                nt.links.new(inp.links[0].from_socket, emit.inputs['Color'])
            else:
                v = inp.default_value
                emit.inputs['Color'].default_value = (v[0], v[1], v[2], 1) if hasattr(v, '__len__') else (v, v, v, 1)
        nt.links.new(emit.outputs[0], out.inputs['Surface'])


key_atlas = {k: a for a, ks in REC['atlas'].items() for k in ks}
keys = [k for k in REC['parts'] if key_atlas.get(k) in ATLAS_PARTS]
if args.kind == 'ammo':
    keys = ['Case', 'Jacket', 'Primer']
if args.parts:
    keys = [k for k in keys if k in args.parts.split(',')]
chans = args.channels.split(',')
for ch in chans:
    if ch == 'ao':
        continue
    route(ch)
    for key in keys:
        atlas = key_atlas[key]
        lpo = bpy.data.objects[LP_NAME[key]]
        names = REC['parts'][key]
        if args.kind == 'ammo':
            names = [o.name for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith({'Case': 'Case •', 'Jacket': 'Jacket •', 'Primer': 'Primer •'}[key])]
        srcs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
        bpy.ops.object.select_all(action='DESELECT')
        for s in srcs:
            s.hide_render = False
            s.select_set(True)
        lpo.select_set(True)
        bpy.context.view_layer.objects.active = lpo
        rec = set_target(atlas, ch)
        bk.use_clear = not rec[1]
        bpy.ops.object.bake(type='NORMAL' if ch == 'normal' else 'EMIT', use_clear=bk.use_clear, use_selected_to_active=True,
                            cage_extrusion=bk.cage_extrusion, max_ray_distance=bk.max_ray_distance, margin=bk.margin)
        rec[1] = True
        log(ch, key, '←', len(srcs), 'objects')
if 'ao' in chans:
    # AO самой игровой сетки (не зависит от состояния): все игровые детали видны лучам.
    for o in lp_meshes:
        o.visible_diffuse = o.visible_shadow = o.visible_glossy = True
    for o in bpy.data.objects:
        if o.type == 'MESH' and o not in lp_meshes:
            o.hide_render = True
    for key in keys:
        atlas = key_atlas[key]
        lpo = bpy.data.objects[LP_NAME[key]]
        bpy.ops.object.select_all(action='DESELECT')
        lpo.select_set(True)
        bpy.context.view_layer.objects.active = lpo
        rec = set_target(atlas, 'ao')
        if S.world:
            S.world.light_settings.distance = 0.01
        bpy.ops.object.bake(type='AO', use_clear=not rec[1], use_selected_to_active=False, margin=bk.margin)
        rec[1] = True
        log('ao', key)
for (atlas, ch), (im, used) in images.items():
    if not used:
        continue
    path = OUT / f'{atlas}_{ch}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    log('saved', path)
print('PM_BAKE_DONE', args.kind, flush=True)
