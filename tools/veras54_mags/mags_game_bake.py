"""Магазин ВЕРАС-54: запекание игровых карт с high-poly (стеки UCUPaint текстур v01) на игровую сетку mags_game_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_mags/mags_game_bake.py -- m45|d60 [--channels …] [--samples N]
Каналы — как у автомата (tools/veras54_v13/game_bake.py):
  color — цвет (sRGB); normal — нормали (касательное пространство, OpenGL +Y); mrh — R металл, G шероховатость, B места хвата;
  ecm — маска износа: R выпуклые кромки, G углубления (AO по самой детали), B = 1 — покрытие; coat — R жировая плёнка
  (канал Oil film → Coat Weight исходника); emit — свечение (светонакопительные цифры); ao — AO самой игровой сетки.
→ _asset_src/veras54_game_mags/<m45|d60>/raw/<Атлас>_<канал>.png. Исходник не сохраняется.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mags_game_common as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('mid', choices=tuple(C.MAGS))
ap.add_argument('--channels', default='ecm,mrh,coat,emit,color,normal,ao')
ap.add_argument('--samples', type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
M = C.MAGS[args.mid]
WORK = C.work(args.mid)
REC = json.loads((WORK / 'parts.json').read_text(encoding='utf-8'))
OUT = WORK / 'raw'
OUT.mkdir(parents=True, exist_ok=True)
ATLAS = M['atlas']
SIZE = M['size']
SAMPLES = {'color': 32, 'mrh': 24, 'normal': 16, 'ecm': 48, 'coat': 24, 'emit': 8, 'ao': 64}
WEAR_AO = {'edge': (True, 0.0010), 'cavity': (False, 0.0040)}
BAKE_MARGIN = max(3, int(REC.get('uv_margin_px', 12)) // 2 - 1)
log = lambda *a: print('MAGS_BAKE', args.mid, *a, flush=True)
pre = M['prefix']
# игровая деталь → (объект игровой сетки, детали исходника)
LP_OF = {p: p for p in REC['parts']}
LP_OF['Round_hi'] = 'Round_01'
LP_OF['Round_lo'] = f'Round_{C.ROUNDS_HI + 1:02d}'
SRC_OF = {p: v['sources'] for p, v in REC['parts'].items()}
SRC_OF['Round_hi'] = [f'{pre} • case 1', f'{pre} • projectile 1']
SRC_OF['Round_lo'] = [f'{pre} • case {C.ROUNDS_HI + 1}', f'{pre} • projectile {C.ROUNDS_HI + 1}']

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(M['src']))
S = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.hide_render = True
    if o.type == 'MESH':
        o['bake_hand'] = float(M['hand'].get(o.name, 0.0))
bpy.context.view_layer.update()

want = list(LP_OF.values())
with bpy.data.libraries.load(str(WORK / 'lp.blend'), link=False) as (src, dst):
    asked = [n for n in src.objects if n in want]
    dst.objects = list(asked)
lpc = bpy.data.collections.new('LP_BAKE')
S.collection.children.link(lpc)
by_name = dict(zip(asked, dst.objects))
lp = {}
for part, name in LP_OF.items():
    o = by_name[name]
    lpc.objects.link(o)
    lp[part] = o
bpy.context.view_layer.update()
for o in lp.values():
    o.hide_render = False

S.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type != 'CPU'
S.cycles.device = 'GPU'
S.cycles.use_denoising = False
bk = S.render.bake
bk.margin = BAKE_MARGIN
bk.margin_type = 'EXTEND'
bk.normal_space = 'TANGENT'
bk.use_selected_to_active = True
bk.use_cage = False

images = {}


def target(channel: str):
    if channel not in images:
        im = bpy.data.images.new(f'{ATLAS}_{channel}', SIZE, SIZE, alpha=True, float_buffer=(channel == 'normal'))
        im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        im.generated_color = (0.5, 0.5, 1.0, 0.0) if channel == 'normal' else (0, 0, 0, 0)
        images[channel] = [im, False]
    return images[channel]


def set_target(o, channel: str):
    rec = target(channel)
    for m in o.data.materials:
        nt = m.node_tree
        node = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'BAKE_TARGET'
        node.image = rec[0]
        nt.nodes.active = node
    return rec


saved = {}


def ao_socket(nt, key: str):
    inside, distance = WEAR_AO[key]
    ao = nt.nodes.get('BAKE_AO_' + key) or nt.nodes.new('ShaderNodeAmbientOcclusion')
    ao.name = 'BAKE_AO_' + key
    ao.inside = inside
    ao.only_local = True
    ao.samples = 32
    ao.inputs['Distance'].default_value = distance
    inv = nt.nodes.get('BAKE_INV_' + key) or nt.nodes.new('ShaderNodeMath')
    inv.name = 'BAKE_INV_' + key
    inv.operation = 'SUBTRACT'
    inv.inputs[0].default_value = 1.0
    nt.links.new(ao.outputs['AO'], inv.inputs[1])
    return inv.outputs[0]


def hand_socket(nt):
    a = nt.nodes.get('BAKE_HAND') or nt.nodes.new('ShaderNodeAttribute')
    a.name = 'BAKE_HAND'
    a.attribute_type = 'OBJECT'
    a.attribute_name = 'bake_hand'
    return a.outputs['Fac']


INPUT = {'color': 'Base Color', 'metal': 'Metallic', 'rough': 'Roughness', 'coat': 'Coat Weight',
         'emit_color': 'Emission Color', 'emit_strength': 'Emission Strength'}


def pbr_source(nt, which: str):
    p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if p is None:
        return None, 0.0
    inp = p.inputs[INPUT[which]]
    if inp.links:
        return inp.links[0].from_socket, None
    return None, inp.default_value


def feed(nt, socket_in, src) -> None:
    sock, value = src
    for l in list(socket_in.links):
        nt.links.remove(l)
    if sock is not None:
        nt.links.new(sock, socket_in)
    elif hasattr(value, '__len__'):
        socket_in.default_value = value
    else:
        socket_in.default_value = (value, value, value, 1) if socket_in.type == 'RGBA' else value


def route(channel: str) -> None:
    """Канал → Emission у всех материалов high-poly; normal — обратно BSDF."""
    for m in bpy.data.materials:
        if m.name.startswith('GAME •') or m.node_tree is None:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
        if out is None:
            continue
        if m.name not in saved:
            link = out.inputs['Surface'].links[0] if out.inputs['Surface'].links else None
            saved[m.name] = link.from_socket if link else None
        if channel == 'normal':
            if saved[m.name] is not None:
                nt.links.new(saved[m.name], out.inputs['Surface'])
            continue
        emit = nt.nodes.get('BAKE_EMIT') or nt.nodes.new('ShaderNodeEmission')
        emit.name = 'BAKE_EMIT'
        emit.inputs['Strength'].default_value = 1.0
        for l in list(emit.inputs['Color'].links):
            nt.links.remove(l)
        if channel == 'color':
            feed(nt, emit.inputs['Color'], pbr_source(nt, 'color'))
        elif channel == 'emit':
            mul = nt.nodes.get('BAKE_EMUL') or nt.nodes.new('ShaderNodeMix')
            mul.name = 'BAKE_EMUL'
            mul.data_type = 'RGBA'
            mul.blend_type = 'MULTIPLY'
            mul.inputs['Factor'].default_value = 1.0
            feed(nt, mul.inputs[6], pbr_source(nt, 'emit_color'))
            feed(nt, mul.inputs[7], pbr_source(nt, 'emit_strength'))
            nt.links.new(mul.outputs[2], emit.inputs['Color'])
        else:
            comb = nt.nodes.get('BAKE_COMB') or nt.nodes.new('ShaderNodeCombineColor')
            comb.name = 'BAKE_COMB'
            for k in ('Red', 'Green', 'Blue'):
                for l in list(comb.inputs[k].links):
                    nt.links.remove(l)
                comb.inputs[k].default_value = 0.0
            if channel == 'mrh':
                feed(nt, comb.inputs['Red'], pbr_source(nt, 'metal'))
                feed(nt, comb.inputs['Green'], pbr_source(nt, 'rough'))
                nt.links.new(hand_socket(nt), comb.inputs['Blue'])
            elif channel == 'coat':
                feed(nt, comb.inputs['Red'], pbr_source(nt, 'coat'))
                comb.inputs['Blue'].default_value = 1.0
            else:                                   # ecm
                nt.links.new(ao_socket(nt, 'edge'), comb.inputs['Red'])
                nt.links.new(ao_socket(nt, 'cavity'), comb.inputs['Green'])
                comb.inputs['Blue'].default_value = 1.0
            nt.links.new(comb.outputs['Color'], emit.inputs['Color'])
        nt.links.new(emit.outputs[0], out.inputs['Surface'])


def bake_part(part: str, channel: str) -> None:
    o = lp[part]
    cage = REC['cage'][part]
    srcs = [bpy.data.objects[n] for n in SRC_OF[part]]
    bpy.ops.object.select_all(action='DESELECT')
    for s in srcs:
        s.hide_render = False
        s.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    rec = set_target(o, channel)
    S.cycles.samples = args.samples or SAMPLES[channel]
    bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=not rec[1], use_selected_to_active=True,
                        cage_extrusion=cage['extrusion_mm'] / 1000, max_ray_distance=cage['max_ray_mm'] / 1000,
                        margin=BAKE_MARGIN)
    rec[1] = True


channels = args.channels.split(',')
# сначала проходы по high-poly, AO игровой сетки — последним (исходник от лучей прячется)
for ch in [c for c in channels if c != 'ao']:
    route(ch)
    for o in lp.values():
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
        o.visible_volume_scatter = o.visible_shadow = False
    for part in LP_OF:
        bake_part(part, ch)
        log(ch, part, '←', len(SRC_OF[part]), 'objects')
if 'ao' in channels:
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name not in {x.name for x in lp.values()}:
            o.hide_render = True
    for o in lp.values():
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = True
        o.visible_volume_scatter = o.visible_shadow = True
    S.world = S.world or bpy.data.worlds.new('AO')
    S.world.light_settings.distance = 0.008
    for part, o in lp.items():
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        rec = set_target(o, 'ao')
        S.cycles.samples = args.samples or SAMPLES['ao']
        bpy.ops.object.bake(type='AO', use_clear=not rec[1], use_selected_to_active=False, margin=BAKE_MARGIN)
        rec[1] = True
        log('ao', part)
for ch, (im, used) in images.items():
    if not used:
        continue
    path = OUT / f'{ATLAS}_{ch}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    log('saved', path)
print('MAGS_BAKE_DONE', args.mid, flush=True)
