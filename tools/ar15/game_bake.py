"""AR-15 «ГРАНЬ-15»: запекание игровых карт с high-poly (отделка этапа 1 + износ этапа 2) на игровую сетку game_lp.py.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/ar15/game_bake.py -- [атлас …] [--channels color,rough,metal,normal,ao] [--samples N] [--cpu]
Как у ВСС-М (tools/vss_m_v8/game_bake.py), но наоборот по файлам: открывается сам исходник (`AR-15_износ_этап2_v1.blend`
— у его материалов AR15_<набор> относительные пути к картам Текстуры_этап2_износ_v1, при подгрузке в чужой файл они
бы сломались), игровые детали подгружаются из lp/AR15_Game_LP.blend. Каждая игровая деталь печётся только со своих
деталей исходника (список hp в parts.json) — соседняя деталь в карту не попадает. Каналы:
  color — цвет (через свечение: проход «цвет» у металла даёт чёрное), rough / metal — входы шероховатости и металла
  материала (свечением), normal — нормали в касательном пространстве (с картой нормалей Painter), ao — затенение самой
  игровой сетки (щели между деталями; канал R карты ORM игры).
Копии внахлёст (uv_stack) на время запекания уходят за квадрат (asset_kit.uv.shift_stack_copies).
→ _asset_src/ar15/game/maps/raw/<Атлас>_<канал>.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402

WORK = ROOT / '_asset_src/ar15/game'
OUT = WORK / 'maps/raw'
OUT.mkdir(parents=True, exist_ok=True)
CHANNELS = ('color', 'rough', 'metal', 'normal', 'ao')
EXTRUSION, RAY = 0.003, 0.006                    # м: сетка упрощена — отклонение до 1–2 мм
log = lambda *a: print('AR15_BAKE', *a, flush=True)



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
    """Материал исходника: на время запекания — свечение нужного канала (цвет / шероховатость / металл)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return None
    keep = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
    em = nt.nodes.new('ShaderNodeEmission')
    em.name = '_bake_emit'
    src = bsdf.inputs['Base Color' if channel == 'color' else 'Roughness' if channel == 'rough' else 'Metallic']
    if src.links:
        nt.links.new(src.links[0].from_socket, em.inputs['Color'])
    else:
        v = src.default_value
        em.inputs['Color'].default_value = (v[0], v[1], v[2], 1) if channel == 'color' else (v, v, v, 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return keep


def emission_restore(mat, keep):
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    for n in [n for n in nt.nodes if n.name == '_bake_emit']:
        nt.nodes.remove(n)
    if keep is not None:
        nt.links.new(keep, out.inputs['Surface'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('atlases', nargs='*')
    ap.add_argument('--channels', default=','.join(CHANNELS))
    ap.add_argument('--samples', type=int, default=0)
    ap.add_argument('--cpu', action='store_true', help='печь процессором (видеокарта занята другой работой)')
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=REC['source'])
    hp = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
    with bpy.data.libraries.load(str(WORK / 'lp/AR15_Game_LP.blend'), link=False) as (src, dst):
        dst.objects = list(src.objects)
    lp_coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(lp_coll)
    lp = []
    for o in dst.objects:
        if o is not None and o.type == 'MESH' and 'atlas' in o:
            lp_coll.objects.link(o)
            lp.append(o)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    try:
        if args.cpu:
            raise RuntimeError('cpu')
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
    shown = [o for o in hp.values() if not o.hide_render]
    atlases = args.atlases or list(REC['atlases'].keys())
    channels = [c for c in args.channels.split(',') if c]
    for atlas in atlases:
        size = REC['atlases'][atlas]['size']
        objs = [o for o in lp if o['atlas'] == atlas]
        kit_uv.shift_stack_copies(objs, 1.0)
        for ch in channels:
            img = image(f'{atlas}_{ch}', size, ch != 'color')
            for o in objs:
                target_node(o.data.materials[0], img)
            if ch == 'ao':
                # исходник лежит поверх игровой сетки и закрыл бы её целиком — на этот проход его нет
                for h in shown:
                    h.hide_render = True
                sc.cycles.samples = args.samples or 128
                bpy.ops.object.select_all(action='DESELECT')
                for o in objs:
                    o.select_set(True)
                bpy.context.view_layer.objects.active = objs[0]
                bk.use_selected_to_active = False
                bpy.ops.object.bake(type='AO')
                for h in shown:
                    h.hide_render = False
            else:
                sc.cycles.samples = args.samples or (16 if ch == 'normal' else 1)
                for o in objs:
                    srcs = [hp[n] for n in o['hp'] if n in hp]
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


# помощники (свечение канала, цель запекания) берёт и глушитель (supp_game.py)
if __name__ == '__main__':
    main()
