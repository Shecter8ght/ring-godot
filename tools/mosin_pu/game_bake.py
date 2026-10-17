"""Запекание игровых карт Мосина ПУ (состояние 20 %) с high-poly UCUPaint на игровую сетку game_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_bake.py -- <kind> [--variant fp|detail] [--channels …] [--samples N]
  kind: rifle — атласы Wood и Steel из винтовки; mount, затем scope — атлас Optic (второй дописывает, не стирая);
        ammo — атлас Ammo из патрона; ao — AO самой игровой сетки (щели между деталями, канал R карты ORM).
Каналы (по проходу на деталь; скалярные упакованы по три — каждый проход заново грузит 8K-карты исходника):
  color — цвет (sRGB); normal — нормали (касательное пространство);
  mrh — R металл, G шероховатость, B места хвата и трения (атрибут Wear_Contact исходника);
  ecm — маска износа шейдера (формат — навык godot-asset-preparation, образец — tools/pm_v11_bake.py): R выпуклые
        кромки (AO «изнутри» по самой детали), G углубления (AO снаружи по самой детали), B = 1 — покрытие атласа
        (где запечено; по нему game_pack.py добирает поля островов).
→ _asset_src/mosin_pu_game/<вариант>/maps/raw/<Атлас>_<канал>.png (вариант — game_lp.py). Исходники не сохраняются.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/mosin_pu_game'
ap = argparse.ArgumentParser()
ap.add_argument('kind', choices=('rifle', 'mount', 'scope', 'ammo', 'ao'))
ap.add_argument('--variant', choices=('fp', 'detail'), default='fp')
ap.add_argument('--channels', default='')
ap.add_argument('--samples', type=int, default=0)
ap.add_argument('--groups', default='')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
REC = json.loads((WORK / args.variant / 'lp/parts.json').read_text(encoding='utf-8'))
LP_FILE = WORK / args.variant / 'lp/Mosin_Game_LP.blend'
OUT = WORK / args.variant / 'maps/raw'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = {'rifle': REC['sources']['rifle'], 'mount': REC['sources']['mount'], 'scope': REC['sources']['scope'],
          'ammo': REC['sources']['ammo'], 'ao': None}[args.kind]
KIND_GROUPS = {'rifle': lambda g: g.startswith(('Frame_', 'Trigger', 'Follower', 'RearSight', 'Bolt', 'Interrupter')),
               'mount': lambda g: g.startswith('Mount'), 'scope': lambda g: g.startswith('Scope'),
               'ammo': lambda g: g.startswith('Round'), 'ao': lambda g: not g.startswith('Round')}[args.kind]
GROUPS = [g for g in REC['groups'] if KIND_GROUPS(g)]
if args.groups:
    GROUPS = [g for g in GROUPS if g in args.groups.split(',')]
DEFAULT_CH = {'ao': 'ao'}.get(args.kind, 'ecm,mrh,color,normal')
CHANNELS = (args.channels or DEFAULT_CH).split(',')
SAMPLES = {'color': 24, 'mrh': 24, 'normal': 16, 'ecm': 48, 'ao': 64}
# Маска износа: AO-узел только по самой детали, расстояния — метры (кромки фасок 0,5–1,5 мм; пазы, шлицы, щели).
WEAR_AO = {'edge': (True, 0.0010), 'cavity': (False, 0.0040)}
# места хвата: металл — Wear_Contact; дерево — Wood_Wear (лак стёрт хватом и щекой; фон 0,28 снимает game_pack.py)
HAND_ATTR = {'Wood': 'Wood_Wear'}
HAND_DEFAULT = 'Wear_Contact'
# меньше половины полей островов развёртки: соседние детали не затираются (остальное добирает game_pack.py)
BAKE_MARGIN = max(3, int(REC.get('uv_margin_px', 8)) // 2 - 1)
KEEP = args.kind == 'scope'                      # атлас Optic начат креплением — прицел дописывает
log = lambda *a: print('MOSIN_BAKE', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
if SOURCE:
    bpy.ops.wm.open_mainfile(filepath=SOURCE)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.hide_render = True
if args.kind == 'scope':
    root = bpy.data.objects['PU_Scope']
    root.matrix_world = Matrix(REC['scope_socket'])
    bpy.data.objects['Scope_Reticle'].hide_render = True
bpy.context.view_layer.update()

# Игровые сетки — из lp-файла (родители-пустышки подтягиваются сами; имена могут получить .001 — берём по порядку).
want = [g for g in REC['groups'] if KIND_GROUPS(g)]
with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
    asked = [n for n in src.objects if n in want]
    dst.objects = list(asked)
lpc = bpy.data.collections.new('LP_BAKE')
S.collection.children.link(lpc)
lp = {}
lp_names = set()
for name, o in zip(asked, dst.objects):
    lpc.objects.link(o)
    lp[name] = o
    lp_names.add(o.name)
bpy.context.view_layer.update()
for o in lp.values():
    o.hide_render = False
    if args.kind != 'ao':
        # игровая сетка не затеняет AO-маски high-poly и не попадает в лучи
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


def atlas_of(g: str) -> str:
    a = REC['groups'][g]['atlas']
    return REC['uv_atlas'].get(a, a)


def target(atlas: str, channel: str):
    key = (atlas, channel)
    if key in images:
        return images[key]
    size = REC['atlas_size'][atlas]
    path = OUT / f'{atlas}_{channel}.png'
    if KEEP and path.exists():
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


def hand_socket(nt, mat_name: str):
    attr = nt.nodes.get('BAKE_HAND') or nt.nodes.new('ShaderNodeAttribute')
    attr.name = 'BAKE_HAND'
    attr.attribute_type = 'GEOMETRY'
    attr.attribute_name = next((v for k, v in HAND_ATTR.items() if mat_name.startswith(k)), HAND_DEFAULT)
    return attr.outputs['Fac']


def ao_socket(nt, key: str):
    """1 — кромка (inside) / углубление: AO-узел только по самой детали, инвертирован."""
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


def pbr_source(nt, which: str):
    """То, что реально приходит во вход BSDF (выход стека UCUPaint или узлы после него), иначе значение входа."""
    p = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if p is None:
        return None, 0.0
    inp = p.inputs[{'color': 'Base Color', 'metal': 'Metallic', 'rough': 'Roughness'}[which]]
    if inp.links:
        return inp.links[0].from_socket, None
    return None, inp.default_value


def feed(nt, socket_in, src) -> None:
    sock, value = src
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
        else:
            comb = nt.nodes.get('BAKE_COMB') or nt.nodes.new('ShaderNodeCombineColor')
            comb.name = 'BAKE_COMB'
            for k in ('Red', 'Green', 'Blue'):
                for l in list(comb.inputs[k].links):
                    nt.links.remove(l)
            if channel == 'mrh':
                feed(nt, comb.inputs['Red'], pbr_source(nt, 'metal'))
                feed(nt, comb.inputs['Green'], pbr_source(nt, 'rough'))
                nt.links.new(hand_socket(nt, m.name), comb.inputs['Blue'])
            else:                                   # ecm
                nt.links.new(ao_socket(nt, 'edge'), comb.inputs['Red'])
                nt.links.new(ao_socket(nt, 'cavity'), comb.inputs['Green'])
                comb.inputs['Blue'].default_value = 1.0
            nt.links.new(comb.outputs['Color'], emit.inputs['Color'])
        nt.links.new(emit.outputs[0], out.inputs['Surface'])


# Затвор ходит: в покое стебель внутри коробки, и слои грязи исходника по затенению (AO не только по детали) дали бы ему
# грязь закрытого места, а коробке изнутри — тень от затвора. Затвор запекается без остальной винтовки, всё остальное —
# без затвора (было: открытый в игре затвор в тёмном шуме, внутри коробки грязно).
BOLT_GROUPS = ('Bolt_Rotor_Mesh', 'Bolt_Bar_Mesh', 'Bolt_Cocking_Mesh')
BOLT_SOURCES = {n for g in BOLT_GROUPS if g in REC['groups'] for n in REC['groups'][g]['sources']}


def isolate(g: str) -> list:
    """Спрятать от лучей то, что при работе затвора не стоит рядом с деталью; вернуть — список спрятанных."""
    if args.kind != 'rifle':
        return []
    bolt = g in BOLT_GROUPS
    hidden = [o for o in bpy.data.objects if o.type == 'MESH' and o.name not in lp_names and not o.hide_render
              and ((o.name not in BOLT_SOURCES) if bolt else (o.name in BOLT_SOURCES))]
    for o in hidden:
        o.hide_render = True
    return hidden


def bake_group(g: str, channel: str) -> None:
    o = lp[g]
    cage = REC['cage'][g]
    srcs = [bpy.data.objects[n] for n in REC['groups'][g]['sources']]
    hidden = isolate(g)
    bpy.ops.object.select_all(action='DESELECT')
    for s in srcs:
        s.hide_render = False
        s.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    rec = set_target(o, atlas_of(g), channel)
    S.cycles.samples = args.samples or SAMPLES[channel]
    bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=not rec[1], use_selected_to_active=True,
                        cage_extrusion=cage['extrusion_mm'] / 1000, max_ray_distance=cage['max_ray_mm'] / 1000,
                        margin=BAKE_MARGIN)
    rec[1] = True
    for h in hidden:
        h.hide_render = False


if args.kind == 'ao':
    # AO игровой сетки (одна на всё): все игровые детали видны лучам, high-poly нет
    S.world = bpy.data.worlds.new('AO') if S.world is None else S.world
    S.world.light_settings.distance = 0.008     # щели между деталями; 2 см «укрывали» почти всё — нагар шейдера пятнами
    for g in GROUPS:
        o = lp[g]
        # затвор — без остальной винтовки, остальное — без затвора: в покое стебель в тени коробки, и открытый в игре
        # затвор (AO гасит рассеянный свет) выходил в тёмных пятнах
        bolt = g in BOLT_GROUPS
        off = [m for k, m in lp.items() if (k in BOLT_GROUPS) != bolt]
        for m in off:
            m.hide_render = True
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        rec = set_target(o, atlas_of(g), 'ao')
        S.cycles.samples = args.samples or SAMPLES['ao']
        bpy.ops.object.bake(type='AO', use_clear=not rec[1], use_selected_to_active=False, margin=BAKE_MARGIN)
        rec[1] = True
        for m in off:
            m.hide_render = False
        log('ao', g)
else:
    for ch in CHANNELS:
        route(ch)
        for g in GROUPS:
            bake_group(g, ch)
            log(ch, g, '←', len(REC['groups'][g]['sources']), 'objects')
for (atlas, ch), (im, used) in images.items():
    if not used:
        continue
    path = OUT / f'{atlas}_{ch}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    log('saved', path)
print('MOSIN_BAKE_DONE', args.kind, flush=True)
