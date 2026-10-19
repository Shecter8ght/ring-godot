"""ВЕРАС-54 v13: запекание игровых карт с high-poly (стеки UCUPaint, состояние 100 %) на игровую сетку game_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_v13/game_bake.py -- <kind> [--channels …] [--parts …] [--samples N]
  kind: gun — атласы Steel, Polymer, Magazine (все детали автомата и магазина); ammo — атлас Ammo (патрон 1);
        ao — AO самой игровой сетки (щели между деталями, канал R карты ORM).
Каналы (по проходу на деталь):
  color  — цвет (sRGB); normal — нормали (касательное пространство, OpenGL +Y);
  mrh    — R металл, G шероховатость, B места хвата и трения (свойство bake_hand детали исходника, см. HAND);
  ecm    — маска износа шейдера: R выпуклые кромки (AO «изнутри» по самой детали), G углубления (AO снаружи по самой
           детали), B = 1 — покрытие (где запечено; по нему game_pack.py добирает поля островов);
  coat   — R: жировая плёнка (канал стека Oil film → Coat Weight исходника: отпечатки, ладони, масло), B = 1;
  emit   — свечение (цвет × сила; светонакопительные цифры магазина), только атлас Magazine.
→ _asset_src/veras54_game_v13/maps/raw/<Атлас>_<канал>.png. Исходник не сохраняется.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/veras54_game_v13'
ap = argparse.ArgumentParser()
ap.add_argument('kind', choices=('gun', 'ammo', 'ao'))
ap.add_argument('--channels', default='')
ap.add_argument('--parts', default='')
ap.add_argument('--samples', type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
LP_FILE = WORK / 'lp/VERAS54_Game_LP.blend'
OUT = WORK / 'maps/raw'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = None if args.kind == 'ao' else REC['source']
if args.kind == 'ammo':
    PARTS = {'Round_case': ['Magazine • loaded case 1'], 'Round_projectile': ['Magazine • loaded projectile 1']}
    LP_NAMES = {'Round_case': 'Magazine • loaded case 1', 'Round_projectile': 'Magazine • loaded projectile 1'}
else:
    PARTS = {p: v['sources'] for p, v in REC['parts'].items()}
    LP_NAMES = {p: p for p in PARTS}
if args.parts:
    PARTS = {p: v for p, v in PARTS.items() if p in args.parts.split(',')}
ATLAS = {p: ('Ammo' if p.startswith('Round') else REC['parts'][p]['atlas']) for p in PARTS}
DEFAULT_CH = {'ao': 'ao', 'ammo': 'ecm,mrh,color,normal,coat'}.get(args.kind, 'ecm,mrh,coat,emit,color,normal')
CHANNELS = (args.channels or DEFAULT_CH).split(',')
SAMPLES = {'color': 32, 'mrh': 24, 'normal': 16, 'ecm': 48, 'coat': 24, 'emit': 8, 'ao': 64}
WEAR_AO = {'edge': (True, 0.0010), 'cavity': (False, 0.0040)}
# Места хвата и трения (B маски износа) по деталям исходника — как маски частого контакта стека v13 v02 (pass_index):
# рукоятка — ладонь, крючок и защёлка — палец, рама и рукоятка затвора — рука и ход рамы, переводчик, цевье снизу и
# магазин — левая рука, планки — обвесы, кромки коробки, крышки, скобы — общий износ. Остальное 0 (жировые следы
# добавляет game_pack.py из канала coat).
HAND = {'Pistol grip • sculpted continuous body': 1.0, 'Trigger • curved blade': 1.0, 'Magazine catch • paddle': 1.0,
        'Bolt carrier • charging handle': 1.0, 'Bolt carrier • body': 0.7, 'Bolt • rotating head': 0.5,
        'Selector • stamped lever -1': 0.9, 'Handguard • integrated sculpted lower shell': 0.6,
        'Handguard • upper ventilated shell': 0.35, 'Magazine_Body': 0.55, 'Magazine_Floorplate': 0.6,
        'Cover release • ribbed thumb button': 0.8, 'Rear sight • range slider buttons': 0.6,
        'Rear sight • large knurled windage drum': 0.4, 'Stock • adjustment latch -1': 0.5, 'Stock • adjustment latch 1': 0.5,
        'Stock • rubber buttpad': 0.4, 'Stock • continuous moulded skeleton': 0.25,
        'Receiver • left wall': 0.3, 'Receiver • right wall / ejection opening': 0.3, 'Dust cover • continuous capped sheet': 0.3,
        'Trigger guard • thin formed bow': 0.4}
HAND_PREFIX = {'Handguard upper rail • tooth': 0.5, 'Handguard lower rail • tooth': 0.5, 'Receiver top rail': 0.45}
# Затвор ходит — запекается без остальной сборки (иначе грязь закрытого места и тень коробки на открытом в игре
# затворе); магазин с подавателем — без автомата (вынимается при перезарядке). Остальное — без них.
ISOLATED = {'Bolt_Steel': 'bolt', 'Magazine_Body': 'mag', 'Magazine_Steel': 'mag', 'Magazine_Follower': 'mag'}
BAKE_MARGIN = max(3, int(REC.get('uv_margin_px', 12)) // 2 - 1)
log = lambda *a: print('VERAS_BAKE', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
if SOURCE:
    bpy.ops.wm.open_mainfile(filepath=SOURCE)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.hide_render = True
if SOURCE:
    root = bpy.data.objects['VERAS54']
    for k, v in (('Bolt pull', 0.0), ('Safety raised', False), ('Magazine removed', 0.0), ('Stock fold', 0.0),
                 ('Cover button press', 0.0), ('Muzzle attachment', 0)):
        root[k] = v
    bpy.data.objects['Magazine']['Rounds remaining'] = 30
    for c in bpy.data.collections:
        if 'Suppressor' in c.name or 'Студия' in c.name:
            for o in c.all_objects:
                if o is not None:
                    o.hide_render = True
    for o in bpy.data.objects:
        o.update_tag()
        if o.type == 'MESH':
            v = HAND.get(o.name)
            if v is None:
                v = next((h for k, h in HAND_PREFIX.items() if o.name.startswith(k)), 0.0)
            o['bake_hand'] = float(v)
    if args.kind == 'ammo':
        # патрон 1 — без остальной сборки: в окнах магазина и в руке он целиком на виду
        keep = set(sum(PARTS.values(), []))
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name not in keep:
                o.hide_render = True
bpy.context.view_layer.update()

# Игровые сетки — из lp-файла (имена могут получить .001 — берём по порядку запроса).
want = list(LP_NAMES.values())
with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
    asked = [n for n in src.objects if n in want]
    dst.objects = list(asked)
lpc = bpy.data.collections.new('LP_BAKE')
S.collection.children.link(lpc)
lp = {}
lp_names = set()
by_name = dict(zip(asked, dst.objects))
for part, name in LP_NAMES.items():
    o = by_name[name]
    lpc.objects.link(o)
    lp[part] = o
    lp_names.add(o.name)
bpy.context.view_layer.update()
for o in lp.values():
    o.hide_render = False
    if args.kind != 'ao':
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
        o.visible_volume_scatter = o.visible_shadow = False

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


def target(atlas: str, channel: str):
    key = (atlas, channel)
    if key in images:
        return images[key]
    size = REC['atlas_size'][atlas]
    path = OUT / f'{atlas}_{channel}.png'
    if args.parts and path.exists():
        # дозапекание отдельных деталей — поверх прежней карты
        im = bpy.data.images.load(str(path))
        im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        images[key] = [im, True]
    else:
        im = bpy.data.images.new(f'{atlas}_{channel}', size, size, alpha=True, float_buffer=(channel == 'normal'))
        im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        im.generated_color = (0.5, 0.5, 1.0, 0.0) if channel == 'normal' else (0, 0, 0, 0)
        images[key] = [im, False]
    return images[key]


def set_target(o, atlas: str, channel: str):
    rec = target(atlas, channel)
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
    """Канал → Emission у всех материалов high-poly (для EMIT); normal — обратно BSDF."""
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
            sock, value = pbr_source(nt, 'emit_strength')
            feed(nt, mul.inputs[7], (sock, value))
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


ALL_SOURCES = {n for p, v in REC['parts'].items() for n in v['sources']} if args.kind == 'gun' else set()
GROUP_SOURCES = {}
for p, v in REC['parts'].items():
    GROUP_SOURCES.setdefault(ISOLATED.get(p, 'rest'), set()).update(v['sources'])
ROUND_SOURCES = {f'Magazine • loaded {k} {i}' for k in ('case', 'projectile') for i in range(1, 31)}


def isolate(part: str) -> list:
    """Спрятать от лучей детали, которые при работе не стоят рядом (затвор / магазин / остальное)."""
    if args.kind != 'gun':
        return []
    grp = ISOLATED.get(part, 'rest')
    allowed = GROUP_SOURCES[grp] | (ROUND_SOURCES if grp == 'mag' else set())
    hidden = [o for o in bpy.data.objects if o.type == 'MESH' and o.name not in lp_names and not o.hide_render
              and (o.name in ALL_SOURCES or o.name in ROUND_SOURCES) and o.name not in allowed]
    for o in hidden:
        o.hide_render = True
    return hidden


def bake_part(part: str, channel: str) -> None:
    if channel == 'emit' and ATLAS[part] != 'Magazine':
        return
    o = lp[part]
    cage = REC['cage'][part]
    srcs = [bpy.data.objects[n] for n in PARTS[part]]
    hidden = isolate(part)
    bpy.ops.object.select_all(action='DESELECT')
    for s in srcs:
        s.hide_render = False
        s.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    rec = set_target(o, ATLAS[part], channel)
    S.cycles.samples = args.samples or SAMPLES[channel]
    bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=not rec[1], use_selected_to_active=True,
                        cage_extrusion=cage['extrusion_mm'] / 1000, max_ray_distance=cage['max_ray_mm'] / 1000,
                        margin=BAKE_MARGIN)
    rec[1] = True
    for h in hidden:
        h.hide_render = False


if args.kind == 'ao':
    S.world = bpy.data.worlds.new('AO') if S.world is None else S.world
    S.world.light_settings.distance = 0.008
    for part in PARTS:
        grp = ISOLATED.get(part, 'rest')
        off = [m for k, m in lp.items() if ISOLATED.get(k, 'rest') != grp]
        for m in off:
            m.hide_render = True
        bpy.ops.object.select_all(action='DESELECT')
        o = lp[part]
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        rec = set_target(o, ATLAS[part], 'ao')
        S.cycles.samples = args.samples or SAMPLES['ao']
        bpy.ops.object.bake(type='AO', use_clear=not rec[1], use_selected_to_active=False, margin=BAKE_MARGIN)
        rec[1] = True
        for m in off:
            m.hide_render = False
        log('ao', part)
else:
    for ch in CHANNELS:
        route(ch)
        for part in PARTS:
            bake_part(part, ch)
            log(ch, part, '←', len(PARTS[part]), 'objects')
for (atlas, ch), (im, used) in images.items():
    if not used:
        continue
    path = OUT / f'{atlas}_{ch}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    if ch == 'normal':
        im.use_half_precision = False
    im.save()
    log('saved', path)
print('VERAS_BAKE_DONE', args.kind, flush=True)
