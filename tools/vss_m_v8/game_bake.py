"""ВСС-М v8: запекание игровых карт с high-poly (отделка Painter) на игровую сетку game_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/game_bake.py -- [атлас …] [--channels color,rough,metal,normal,ao] [--samples N]
Исходник — _asset_src/vss_m_v8/VSS_M_v8_sp.blend с материалами SP_* (карты Painter, sp_apply.py: те же, что в студии
и сцене на столе). Каждая игровая деталь печётся только со своих деталей исходника (список hp в game_lp) — соседняя
деталь в карту не попадает. Каналы:
  color — цвет (через свечение: проход «цвет» у металла даёт чёрное), rough / metal — каналы G / B карты ORM Painter
  (свечением), normal — нормали в касательном пространстве (исходные материалы: входят нормали Painter),
  ao — затенение самой игровой сетки (щели между деталями; канал R карты ORM игры).
Копии внахлёст (uv_stack) на время запекания уходят за квадрат (asset_kit.uv.shift_stack_copies).
→ _asset_src/vss_m_v8_game/maps/raw/<Атлас>_<канал>.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/vss_m_v8'))
from asset_kit import uv as kit_uv  # noqa: E402
import sp_apply  # noqa: E402

WORK = ROOT / '_asset_src/vss_m_v8_game'
SRC = ROOT / '_asset_src/vss_m_v8/VSS_M_v8_sp.blend'
OUT = WORK / 'maps/raw'
OUT.mkdir(parents=True, exist_ok=True)
CHANNELS = ('color', 'rough', 'metal', 'normal', 'ao')
EXTRUSION, RAY = 0.003, 0.006                    # м: сетка упрощена — отклонение до 1–2 мм
log = lambda *a: print('VSS_BAKE', *a, flush=True)

ap = argparse.ArgumentParser()
ap.add_argument('atlases', nargs='*')
ap.add_argument('--channels', default=','.join(CHANNELS))
ap.add_argument('--samples', type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))


def image(name, size, data):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False)
    img.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
    img.generated_color = (0.5, 0.5, 1.0, 1.0) if name.endswith('_normal') else (0, 0, 0, 1)
    return img


def target_node(mat, img):
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.name == '_bake_target']:
        nt.nodes.remove(n)
    t = nt.nodes.new('ShaderNodeTexImage')
    t.name = '_bake_target'
    t.image = img
    nt.nodes.active = t


def emission_swap(mat, channel):
    """Материал SP_*: на время запекания — свечение нужного канала карт Painter (цвет / G / B карты ORM)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return None
    keep = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = '_bake_emit'
    if channel == 'color':
        src = bsdf.inputs['Base Color']
    elif channel == 'rough':
        src = bsdf.inputs['Roughness']
    else:
        src = bsdf.inputs['Metallic']
    if src.links:
        nt.links.new(src.links[0].from_socket, em.inputs['Color'])
    else:
        v = src.default_value
        em.inputs['Color'].default_value = (v[0], v[1], v[2], 1) if channel == 'color' else (v, v, v, 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return keep


def emission_restore(mat, keep):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    for n in [n for n in nt.nodes if n.name == '_bake_emit']:
        nt.nodes.remove(n)
    if keep is not None:
        nt.links.new(keep, out.inputs['Surface'])


def main():
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/VSS_Game_LP.blend'))
    lp = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
    with bpy.data.libraries.load(str(SRC), link=False) as (src, dst):
        dst.objects = list(src.objects)
    hp_coll = bpy.data.collections.new('HP')
    bpy.context.scene.collection.children.link(hp_coll)
    hp = {}
    for o in dst.objects:
        if o is not None:
            hp_coll.objects.link(o)
            hp[o.name] = o
    sp_apply.apply_all()
    # магазины-предметы стоят в стороне (game_lp: MAG_ASIDE): исходник — вычисленные копии деталей со сдвигом, как
    # evaluated_copy в game_lp. Сдвигать сами детали нельзя: они вложены друг в друга (корпус → крышка, патроны), и
    # сохранённое положение расходится с вычисленным — исходник уходил на 15 см, лучи не попадали, карты были пустые.
    shifted = {}                                  # (игровой магазин, деталь исходника) → копия на месте игровой
    dg = bpy.context.evaluated_depsgraph_get()
    for node, part in REC['parts'].items():
        if 'shift_m' not in part:
            continue
        for nm in part['hp']:
            o = hp.get(nm)
            if o is None:
                continue
            eo = o.evaluated_get(dg)
            me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
            me.transform(Matrix.Translation(Vector(part['shift_m'])) @ eo.matrix_world)
            for i, slot in enumerate(o.material_slots):
                if i < len(me.materials):
                    me.materials[i] = slot.material
            c = bpy.data.objects.new(f'{nm}@{node}', me)
            hp_coll.objects.link(c)
            shifted[(node, nm)] = c
    hp_all = list(hp.values()) + list(shifted.values())
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
    except Exception:
        sc.cycles.device = 'CPU'
    bk = sc.render.bake
    bk.use_clear = False
    bk.margin = 5
    bk.margin_type = 'EXTEND'
    atlases = args.atlases or list(REC['atlases'].keys())
    channels = [c for c in args.channels.split(',') if c]
    for atlas in atlases:
        size = REC['atlases'][atlas]['size']
        objs = [o for o in lp if o['atlas'] == atlas]
        kit_uv.shift_stack_copies(objs, 1.0)
        for ch in channels:
            img = image(f'{atlas}_{ch}', size, ch != 'color')
            for o in objs:
                mat = o.data.materials[0]
                target_node(mat, img)
            if ch == 'ao':
                # исходник лежит поверх игровой сетки и закрыл бы её целиком — на этот проход его нет
                for h in hp_all:
                    h.hide_render = True
                sc.cycles.samples = args.samples or 128
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bk.use_selected_to_active = False
                bpy.ops.object.bake(type='AO')
                for h in hp_all:
                    h.hide_render = False
            else:
                sc.cycles.samples = args.samples or (16 if ch == 'normal' else 1)
                for o in objs:
                    srcs = [shifted.get((o.name, n)) or hp[n] for n in o['hp'] if (o.name, n) in shifted or n in hp]
                    if not srcs:
                        log('нет исходника', o.name)
                        continue
                    swaps = {}
                    if ch != 'normal':
                        for h in srcs:
                            for s in h.material_slots:
                                m = s.material
                                if m and m.name not in swaps and m.use_nodes:
                                    swaps[m.name] = (m, emission_swap(m, ch))
                    bpy.ops.object.select_all(action='DESELECT')
                    for h in srcs:
                        h.hide_render = False
                        h.hide_set(False)
                        h.select_set(True)
                    o.select_set(True)
                    bpy.context.view_layer.objects.active = o
                    bk.use_selected_to_active = True
                    bk.cage_extrusion = EXTRUSION
                    bk.max_ray_distance = RAY
                    bpy.ops.object.bake(type='NORMAL' if ch == 'normal' else 'EMIT', normal_space='TANGENT')
                    for m, keep in swaps.values():
                        emission_restore(m, keep)
            path = OUT / f'{atlas}_{ch}.png'
            img.filepath_raw = str(path)
            img.file_format = 'PNG'
            img.save()
            log('запечено', atlas, ch, path.name)
        kit_uv.shift_stack_copies(objs, -1.0)
    log('готово', atlases, channels)


main()
