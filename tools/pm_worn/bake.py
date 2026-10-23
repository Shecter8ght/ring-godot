"""ПМ «пошарпанный» v01: запекание игровых карт с high-poly (стеки UCUPaint) на игровую сетку build_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/bake.py -- <kind> [--channels …] [--parts a,b] [--samples N]
  kind: pm — атласы Steel и Grip из сборки 01_ПМ (хвостовик ствола без глушителя, без крепления К-1);
        mag — атлас Magazine (магазин с патронами, отдельный файл); ammo — атлас Ammo (патрон);
        supp — атлас Suppressor (глушитель отдельного файла, посажен на ствол);
        ao — AO самой игровой сетки (щели между деталями, канал R карты ORM): магазин и глушитель — порознь.
Каналы (проход на деталь): color — цвет (sRGB); normal — нормали (касательное, OpenGL +Y);
  mrh — R металл, G шероховатость, B = 1 (покрытие — где запечено; по нему pack.py добирает поля островов);
  coat — R жировая плёнка (Coat Weight стека: отпечатки, ладони, масло), B = 1.
→ _asset_src/pm_worn_game/maps/raw/<Атлас>_<канал>.png. Исходники не сохраняются.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('kind', choices=('pm', 'mag', 'ammo', 'supp', 'ao'))
ap.add_argument('--channels', default='')
ap.add_argument('--parts', default='')
ap.add_argument('--samples', type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
REC = json.loads(C.PARTS_FILE.read_text(encoding='utf-8'))
# Глушитель — из сборки (те же объекты и стеки, что принял владелец, уже на стволе); отдельный файл suppressor_worn_v01
# при запекании даёт плоские карты (стек без масок) — причина не найдена, PM_BAKE_SUPP_FILE=1 — прежний путь для сравнения.
SUPP_FROM_ASSEMBLY = os.environ.get('PM_BAKE_SUPP_FILE') != '1'
SOURCE = {'pm': C.SRC_PM, 'mag': C.SRC_MAG, 'ammo': C.SRC_ROUND, 'supp': C.SRC_PM if SUPP_FROM_ASSEMBLY else C.SRC_SUPP, 'ao': None}[args.kind]
ATLASES = {'pm': ('Steel', 'Grip'), 'mag': ('Magazine',), 'ammo': ('Ammo',), 'supp': ('Suppressor',),
           'ao': ('Steel', 'Grip', 'Magazine', 'Ammo', 'Suppressor')}[args.kind]
key_atlas = {k: a for a, ks in REC['atlas'].items() for k in ks}
PARTS = [k for k in REC['parts'] if key_atlas.get(k) in ATLASES]
if args.parts:
    PARTS = [k for k in PARTS if k in args.parts.split(',')]
CHANNELS = (args.channels or ('ao' if args.kind == 'ao' else 'mrh,coat,color,normal')).split(',')
SAMPLES = {'color': 32, 'mrh': 24, 'normal': 16, 'coat': 24, 'ao': 64}
# Детали, что при работе не стоят рядом: магазин вынимается, глушитель снимается — их AO и тени порознь.
ISOLATED = {'MagBody': 'mag', 'Follower': 'mag', 'Spring': 'mag', 'Case': 'ammo', 'Jacket': 'ammo', 'Primer': 'ammo',
            'Suppressor': 'supp'}
# Лишнее в сборке: глушитель и его насечка, крепление и К-1, реквизит, студия — не источник и не тень.
HIDE_PREFIX = ('Suppressor', 'Highpoly |', 'Mount |', 'Reflex |', 'Magazine |', 'Magazine round', 'Studio |',
               'Animation |', 'Engraving |', 'Check |')
log = lambda *a: C.log('PM_BAKE', *a)  # noqa: E731

bpy.context.preferences.use_preferences_save = False
C.enable_ucupaint()
if SOURCE:
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
S = bpy.context.scene
S.frame_set(1)
C.rest_pose()


def unhide_collections(layer_coll) -> None:
    layer_coll.exclude = False
    layer_coll.hide_viewport = False
    layer_coll.collection.hide_viewport = False
    for child in layer_coll.children:
        unhide_collections(child)


# скрытые во вьюпорте коллекции (глушитель в сборке) нельзя выбрать для запекания
unhide_collections(bpy.context.view_layer.layer_collection)
if args.kind == 'mag':
    root = next(o for o in bpy.data.objects if o.name.startswith('PM_magazine_loaded'))
    root.matrix_world = Matrix(REC['magazine_fit'])
if args.kind == 'supp' and not SUPP_FROM_ASSEMBLY:
    seat = Matrix(REC['suppressor_seat'])
    for o in bpy.data.objects:
        if o.parent is None and o.type in ('MESH', 'EMPTY'):
            o.matrix_world = seat @ o.matrix_world
bpy.context.view_layer.update()
SUPP_NAMES = set(REC['parts']['Suppressor'])
for o in bpy.data.objects:
    if o.type == 'LIGHT' or (args.kind == 'pm' and o.name.startswith(HIDE_PREFIX)):
        o.hide_render = True
    if args.kind == 'pm' and o.name.startswith('Barrel | threaded'):
        o.hide_render = False
    if args.kind == 'supp' and SUPP_FROM_ASSEMBLY and o.type == 'MESH':
        # в сборке остаётся только глушитель с насечкой: пистолет не затеняет его маски
        o.hide_render = o.name not in SUPP_NAMES

# Игровая сетка — из lp-файла: все детали (для AO) или только нужные атласы.
with bpy.data.libraries.load(str(C.LP_FILE), link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in C.LP_NAME.values()]
lpc = bpy.data.collections.new('LP_BAKE')
S.collection.children.link(lpc)
lp = {}
for o in dst.objects:
    if o is None:
        continue
    lpc.objects.link(o)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
    key = next(k for k, n in C.LP_NAME.items() if n == o.name)
    lp[key] = o
bpy.context.view_layer.update()
# Положение сеток в мире: в lp-файле они лежат под пустышками узлов; здесь ставим их туда же через parent_keep наоборот —
# данные сеток хранятся в мировых координатах сборки (transform при копировании), пустышки их не смещают.
lp_meshes = list(lp.values())
for o in lp_meshes:
    o.hide_render = False
    if args.kind != 'ao':
        # Игровая сетка не должна затенять источники: лучи её не видят.
        o.visible_camera = o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
        o.visible_volume_scatter = o.visible_shadow = False

# Проба: PM_BAKE_AO_LOCAL=1 — узлы AO масок стека считают только свою деталь (игровая сетка-цель не затеняет источник).
if os.environ.get('PM_BAKE_AO_LOCAL') == '1':
    n_ao = 0
    for tree in bpy.data.node_groups:
        for node in tree.nodes:
            if node.type == 'AMBIENT_OCCLUSION':
                node.only_local = True
                n_ao += 1
    log('AO nodes only_local:', n_ao)
C.gpu_cycles(S, 16)
bk = S.render.bake
bk.margin = 6
bk.margin_type = 'EXTEND'
bk.normal_space = 'TANGENT'
bk.use_selected_to_active = True
bk.use_cage = False
images = {}


def target(atlas: str, channel: str):
    key = (atlas, channel)
    if key not in images:
        im = bpy.data.images.new(f'{atlas}_{channel}', C.SIZE[atlas], C.SIZE[atlas], alpha=False, float_buffer=(channel == 'normal'))
        im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
        im.generated_color = (0.5, 0.5, 1.0, 1.0) if channel == 'normal' else (0, 0, 0, 1)
        images[key] = [im, False]
    return images[key]


def set_target(o, atlas: str, channel: str):
    rec = target(atlas, channel)
    for m in o.data.materials:
        if m is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        node = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
        node.name = 'BAKE_TARGET'
        node.image = rec[0]
        nt.nodes.active = node
    return rec


INPUT = {'color': 'Base Color', 'metal': 'Metallic', 'rough': 'Roughness', 'coat': 'Coat Weight'}
saved = {}


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
    """Канал стека → Emission у всех материалов high-poly (для EMIT); normal — обратно BSDF."""
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
                comb.inputs[k].default_value = 0.0
            if channel == 'mrh':
                feed(nt, comb.inputs['Red'], pbr_source(nt, 'metal'))
                feed(nt, comb.inputs['Green'], pbr_source(nt, 'rough'))
            else:
                feed(nt, comb.inputs['Red'], pbr_source(nt, 'coat'))
            comb.inputs['Blue'].default_value = 1.0
            nt.links.new(comb.outputs['Color'], emit.inputs['Color'])
        nt.links.new(emit.outputs[0], out.inputs['Surface'])


def sources(part: str) -> list:
    names = REC['parts'][part]
    if args.kind == 'ammo':
        prefix = {'Case': 'Case •', 'Jacket': 'Jacket •', 'Primer': 'Primer •'}[part]
        return [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith(prefix)]
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def bake_part(part: str, channel: str) -> None:
    o = lp[part]
    srcs = sources(part)
    assert srcs, f'нет источников детали {part}'
    bpy.ops.object.select_all(action='DESELECT')
    for s in srcs:
        s.hide_render = False
        s.hide_viewport = False
        s.hide_set(False)
        s.select_set(True)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    rec = set_target(o, key_atlas[part], channel)
    S.cycles.samples = args.samples or SAMPLES[channel]
    # Патрон и магазин в игре мелкие: короткий луч, чтобы соседние патроны не проецировались друг на друга.
    small = key_atlas[part] in ('Ammo', 'Magazine')
    bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=not rec[1], use_selected_to_active=True,
                        cage_extrusion=0.0008 if small else 0.0015, max_ray_distance=0.002 if small else 0.004, margin=bk.margin)
    rec[1] = True


if args.kind == 'ao':
    S.world = bpy.data.worlds.new('AO') if S.world is None else S.world
    S.world.light_settings.distance = 0.01
    for part in PARTS:
        grp = ISOLATED.get(part, 'rest')
        off = [m for k, m in lp.items() if ISOLATED.get(k, 'rest') != grp]
        for m in off:
            m.hide_render = True
        bpy.ops.object.select_all(action='DESELECT')
        o = lp[part]
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        rec = set_target(o, key_atlas[part], 'ao')
        S.cycles.samples = args.samples or SAMPLES['ao']
        bpy.ops.object.bake(type='AO', use_clear=not rec[1], use_selected_to_active=False, margin=bk.margin)
        rec[1] = True
        for m in off:
            m.hide_render = False
        log('ao', part)
else:
    for ch in CHANNELS:
        route(ch)
        for part in PARTS:
            bake_part(part, ch)
            log(ch, part, '←', len(sources(part)), 'objects')
C.RAW.mkdir(parents=True, exist_ok=True)
for (atlas, ch), (im, used) in images.items():
    if not used:
        continue
    path = C.RAW / f'{atlas}_{ch}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    if ch == 'normal':
        im.use_half_precision = False
    im.save()
    log('saved', path)
print('PM_BAKE_DONE', args.kind, flush=True)
