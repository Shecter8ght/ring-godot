"""ВЕРАС-54 v14: соответствие игровой сетки и подробной модели («адреса») — запекается один раз на игровую сетку
(game_lp.py → game_uv.py); перенос любых карт подробной модели потом идёт без Blender и видеокарты (game_transfer.py).
Образец — «Частокол» (tools/pkp/game_bake.py), способ тот же.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_bake.py -- [атлас …] [--passes hit,frame,ao] [--gpu] [--ao-samples N]

Исходник — подробная модель с развёрткой по наборам (`Карты v14/ВЕРАС-54_развёртка_v14_01.blend`, tex_sets.SETS), риг —
в позе, в которой снята игровая сетка (parts.json base_props: умолчания рига, переводчик на предохранителе, патрон
в патроннике). Проходы (каждая игровая деталь — только со своих деталей исходника, свойство hp объекта игровой сетки;
лучи — от оболочки игровой детали внутрь, оболочка — по замеренному отклонению детали в обе стороны: у 13 деталей,
упрощённых с гладкого варианта формы, это высота снятого рельефа — заклёпок, клейм, насечек, — он и уходит в нормаль):
  hit   — свечением: R, G — точка развёртки UVMap исходника, B — номер набора (tex_sets.SETS) + 1; 1 выборка;
  frame — касательный базис исходника в точке попадания и игровой сетки в своём текселе (узел Normal Map, оси X, Y, Z);
          матрица 3 × 3: нормаль карты исходника → нормаль в касательном пространстве игровой сетки;
  ao    — затенение игровой сетки в сборе (LOD0 со всеми патронами; с картой затенения исходника берётся меньшее).
Адреса и базис исходника — по кускам игровых объектов по деталям (part_id, split_parts): деталь видит только свою
деталь исходника, соседнюю по узлу — нет.
Патроны магазина: одна сетка на 30 мест — адреса с первого патрона исходника (Round_01; копии — та же сетка).
→ _asset_src/veras54_v14/game/bake/<Атлас>_hit.npz (set: uint8, uv: float32), <Атлас>_frame.npz (m: float16 × 9),
  <Атлас>_ao.npz (ao: float16); строки сверху вниз, как в PNG
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/tex'))
from asset_kit import uv as kit_uv  # noqa: E402
import tex_sets as T  # noqa: E402

SRC = Path(T.UV_BLEND)
WORK = ROOT / '_asset_src/veras54_v14/game'
LP_FILE = WORK / 'lp/VERAS54_Game_LP.blend'
OUT = WORK / 'bake'
SET_IDS = {s: i + 1 for i, s in enumerate(T.SETS)}          # 0 — нет попадания
# оболочка: отклонение детали × запас, в пределах; лучи — до двух оболочек и ещё миллиметр (м)
EXT_MIN, EXT_MAX, EXT_K = 0.0008, 0.0045, 1.25
FRAME_SAMPLES = 8
BAKE_MARGIN = 4                 # половина отступа 8 пикс между деталями (game_uv.py): края соседних островов не наезжают
SEE_THROUGH: dict = {}
log = lambda *a: print('VERAS14_BAKE', *a, flush=True)  # noqa: E731


def image(name, size):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    img.generated_color = (0, 0, 0, 1)
    return img


def pixels(img) -> np.ndarray:
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[::-1, :, :3]          # строки сверху вниз, как в PNG


def encode(nt, vec_socket):
    """Вектор → цвет 0…1 (v · 0,5 + 0,5): свечение отрицательным не бывает."""
    m = nt.nodes.new('ShaderNodeVectorMath')
    m.operation = 'MULTIPLY_ADD'
    m.inputs[1].default_value = (0.5, 0.5, 0.5)
    m.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(vec_socket, m.inputs[0])
    return m.outputs[0]


def emit_material(name, uv_map, mode, set_id=0):
    """Материал-свечение прохода: hit — (u, v, набор); T/B/N — ось касательного базиса по развёртке uv_map."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Strength'].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    if mode == 'hit':
        uv = nt.nodes.new('ShaderNodeUVMap')
        uv.uv_map = uv_map
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(uv.outputs['UV'], sep.inputs[0])
        cmb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(sep.outputs['X'], cmb.inputs['X'])
        nt.links.new(sep.outputs['Y'], cmb.inputs['Y'])
        cmb.inputs['Z'].default_value = set_id / 64.0
        nt.links.new(cmb.outputs[0], em.inputs['Color'])
    else:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.space = 'TANGENT'
        nm.uv_map = uv_map
        nm.inputs['Strength'].default_value = 1.0
        nm.inputs['Color'].default_value = {'T': (1.0, 0.5, 0.5, 1.0), 'B': (0.5, 1.0, 0.5, 1.0),
                                            'N': (0.5, 0.5, 1.0, 1.0)}[mode]
        nt.links.new(encode(nt, nm.outputs[0]), em.inputs['Color'])
    return m


def target(mat, img):
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.name == '_bake_target']:
        nt.nodes.remove(n)
    t = nt.nodes.new('ShaderNodeTexImage')
    t.name = '_bake_target'
    t.image = img
    nt.nodes.active = t


def setup_cycles(gpu):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    if gpu:
        try:
            import addon_utils
            addon_utils.enable('cycles')
            prefs = bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type = 'OPTIX'
            prefs.get_devices()
            for d in prefs.devices:
                d.use = d.type == 'OPTIX'
            sc.cycles.device = 'GPU'
        except Exception as e:      # noqa: BLE001
            log('видеокарта недоступна, процессор:', e)
    bk = sc.render.bake
    bk.use_clear = False
    bk.margin = BAKE_MARGIN
    bk.margin_type = 'EXTEND'
    sc.cycles.use_denoising = False
    return sc


def set_name_of(o):
    s = T.set_of(o.name)
    if s is None and o.material_slots and o.material_slots[0].material:
        s = o.material_slots[0].material.name
    return s if s in SET_IDS else None


def extrusion(rec, names):
    """Оболочка лучей детали: наибольшее отклонение low → high и 99 % обратного (снятый рельеф) × запас."""
    d = 0.0
    for n in names:
        p = rec['parts'].get(n)
        if not p:
            continue
        dm = p['dev_mm']
        d = max(d, dm['max'], dm['back_p99'])
    return min(EXT_MAX, max(EXT_MIN, EXT_K * d / 1000.0))


def split_parts(objs, rec, coll):
    """Объект игровой сетки → куски по деталям (атрибут part_id), у куска hp — одна деталь исходника. Объект узла
    собирает несколько деталей (коробка + спусковая скоба, рама + рукоятка): прижатые грани соседней детали лежат
    в 0,1–0,4 мм над поверхностью, и луч от коробки упирался в изнанку скобы (нормаль «назад»). Куски — только для
    проходов hit и frame (адреса и базис исходника); базис игровой сетки и затенение — по целым объектам."""
    import bmesh
    names = list(rec['parts'])
    n_parts = sum(1 for n, p in rec['parts'].items() if not p.get('copies'))
    out = []
    for o in objs:
        me = o.data
        pid = np.zeros(len(me.polygons), np.int32)
        me.attributes['part_id'].data.foreach_get('value', pid)
        hp = list(o['hp'])
        for v in np.unique(pid):
            if v < n_parts:
                part = names[v]
            else:                                   # патрон: гильза и пуля верхнего патрона (порядок hp у Round_01)
                part = hp[int(v) - n_parts]
            m2 = me.copy()
            bm = bmesh.new()
            bm.from_mesh(m2)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.flatnonzero(pid != v)], context='FACES')
            bm.to_mesh(m2)
            bm.free()
            q = bpy.data.objects.new(f'{o.name}#{part}', m2)
            coll.objects.link(q)
            q.matrix_world = o.matrix_world.copy()
            q['hp'], q['atlas'] = [part], o['atlas']
            q.hide_render = True
            out.append(q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('atlases', nargs='*')
    ap.add_argument('--passes', default='hit,frame,ao')
    ap.add_argument('--gpu', action='store_true', help='Cycles на видеокарте (предупредить соседние сессии)')
    ap.add_argument('--ao-samples', type=int, default=128)
    args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    passes = set(args.passes.split(','))
    OUT.mkdir(parents=True, exist_ok=True)
    rec = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    ctl = bpy.data.objects[T.CONTROLS]
    for k, v in rec['base_props'].items():
        ctl[k] = float(v)
    for o in bpy.data.objects:
        o.update_tag()
    bpy.context.scene.frame_set(bpy.context.scene.frame_current)
    hp = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
    hp_set = {}
    for o in hp.values():
        o.hide_render = False
        o.hide_set(False)
        hp_set[o.name] = set_name_of(o)
    bad = [n for n, s in hp_set.items() if s is None]
    if bad:
        log('детали без набора', bad)
    # игровые детали: только объекты со своей сеткой (копии патронов делят её с Round_01), без LOD1
    with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
        dst.objects = list(src.objects)
    lp_coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(lp_coll)
    lp_all, lp = [], []
    owners = set()
    for o in dst.objects:
        if o is None:
            continue
        lp_coll.objects.link(o)
        if o.type != 'MESH':
            continue
        if o.name.endswith('_LOD1'):
            o.hide_render = True
            continue
        lp_all.append(o)
        if o.data.name in owners:
            continue
        owners.add(o.data.name)
        lp.append(o)
    bpy.context.view_layer.update()
    sc = setup_cycles(args.gpu)
    mats = {}
    for s, i in SET_IDS.items():
        mats[('hit', s)] = emit_material(f'_bake_hit_{s}', 'UVMap', 'hit', i)
        for ax in 'TBN':
            mats[(ax, s)] = emit_material(f'_bake_{ax}_{s}', 'UVMap', ax)
    lp_mats = {ax: emit_material(f'_bake_lp_{ax}', 'GameUV', ax) for ax in 'TBN'}
    hp_keep = {n: [s.material for s in o.material_slots] for n, o in hp.items()}

    def hp_material(o, key):
        m = mats[(key, hp_set[o.name])]
        for slot in o.material_slots:
            slot.material = m

    atlases = args.atlases or list(rec['atlases'])
    shells = {}
    for atlas in atlases:
        size = rec['atlases'][atlas]['size']
        objs = [o for o in lp if o['atlas'] == atlas]
        kit_uv.shift_stack_copies(objs, 1.0)
        for o in objs:
            o.data.uv_layers.active = o.data.uv_layers['GameUV']
            for p in o.data.polygons:
                p.material_index = 0
        keep_lp = {o.name: o.data.materials[0] for o in objs}
        out = {}
        pieces = split_parts(objs, rec, lp_coll) if passes & {'hit', 'frame'} else []
        if passes & {'hit', 'frame'}:
            keys = (['hit'] if 'hit' in passes else []) + (['T', 'B', 'N'] if 'frame' in passes else [])
            for key in keys:
                img = image(f'{atlas}_{key}', size)
                sc.cycles.samples = 1 if key == 'hit' else FRAME_SAMPLES
                for o in pieces:
                    names = list(o['hp']) + [x for n in o['hp'] for x in SEE_THROUGH.get(n, [])]
                    srcs = [hp[n] for n in names if n in hp and hp_set.get(n)]
                    if not srcs:
                        log('нет исходника', o.name)
                        continue
                    e = extrusion(rec, list(o['hp']))
                    shells[o.name] = round(e * 1000, 2)
                    for h in srcs:
                        hp_material(h, key)
                    o.data.materials[0] = bpy.data.materials.get(f'_lp_target_{atlas}') or \
                        bpy.data.materials.new(f'_lp_target_{atlas}')
                    mt = o.data.materials[0]
                    mt.use_nodes = True
                    target(mt, img)
                    src_names = {h.name for h in srcs}
                    for h in hp.values():
                        h.hide_render = h.name not in src_names
                    for q in lp_all + pieces:
                        q.hide_render = q is not o
                    bpy.ops.object.select_all(action='DESELECT')
                    for h in srcs:
                        h.select_set(True)
                    o.select_set(True)
                    bpy.context.view_layer.objects.active = o
                    bk = sc.render.bake
                    bk.use_selected_to_active = True
                    bk.use_cage = False
                    bk.cage_extrusion = e
                    bk.max_ray_distance = 2 * e + 0.001
                    bpy.ops.object.bake(type='EMIT')
                out[key] = pixels(img)
                bpy.data.images.remove(img)
                log('запечено', atlas, key, f'{time.time() - t0:.0f} с')
            for q in pieces:
                q.hide_render = True
            if 'frame' in passes:
                for h in hp.values():
                    h.hide_render = True
                for q in lp_all:
                    q.hide_render = q not in objs
                for ax in 'TBN':
                    img = image(f'{atlas}_lp{ax}', size)
                    target(lp_mats[ax], img)
                    for o in objs:
                        o.data.materials[0] = lp_mats[ax]
                    sc.cycles.samples = 1
                    bpy.ops.object.select_all(action='DESELECT')
                    for o in objs:
                        o.select_set(True)
                    bpy.context.view_layer.objects.active = objs[0]
                    sc.render.bake.use_selected_to_active = False
                    bpy.ops.object.bake(type='EMIT')
                    out['lp' + ax] = pixels(img)
                    bpy.data.images.remove(img)
                    log('запечено', atlas, 'lp' + ax, f'{time.time() - t0:.0f} с')
        if 'hit' in out:
            h = out['hit']
            sid = np.rint(h[..., 2] * 64.0).astype(np.int32)
            ok = (sid >= 1) & (sid <= len(SET_IDS))
            np.savez_compressed(OUT / f'{atlas}_hit.npz', set=np.where(ok, sid, 0).astype(np.uint8),
                                uv=np.where(ok[..., None], h[..., :2], 0.0).astype(np.float32))
            log('адреса', atlas, 'попаданий', round(float(ok.mean()), 4))
        if 'frame' in passes:
            # столбцы — оси исходника в мире; строки — оси игровой сетки: m = Lᵀ · H (нормаль игровой = m · нормаль карты)
            H = np.stack([out[k] * 2.0 - 1.0 for k in 'TBN'], -1)
            L = np.stack([out['lp' + k] * 2.0 - 1.0 for k in 'TBN'], -1)
            for A in (H, L):
                A /= np.maximum(np.linalg.norm(A, axis=2, keepdims=True), 1e-6)
            M = np.einsum('hwki,hwkj->hwij', L, H).astype(np.float16)
            np.savez_compressed(OUT / f'{atlas}_frame.npz', m=M.reshape(size, size, 9))
            del H, L, M
            log('базис', atlas)
        out.clear()
        for q in pieces:
            me = q.data
            bpy.data.objects.remove(q, do_unlink=True)
            bpy.data.meshes.remove(me)
        for o in objs:
            o.data.materials[0] = keep_lp[o.name]
        if 'ao' in passes:
            for h in hp.values():
                h.hide_render = True
            for q in lp_all:
                q.hide_render = False
            img = image(f'{atlas}_ao', size)
            for o in objs:
                o.data.materials[0].use_nodes = True
                target(o.data.materials[0], img)
            sc.cycles.samples = args.ao_samples
            bpy.ops.object.select_all(action='DESELECT')
            for o in objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = objs[0]
            sc.render.bake.use_selected_to_active = False
            bpy.ops.object.bake(type='AO')
            np.savez_compressed(OUT / f'{atlas}_ao.npz', ao=pixels(img)[..., 0].astype(np.float16))
            bpy.data.images.remove(img)
            log('затенение', atlas, f'{time.time() - t0:.0f} с')
        kit_uv.shift_stack_copies(objs, -1.0)
    for n, ms in hp_keep.items():
        for slot, m in zip(hp[n].material_slots, ms):
            slot.material = m
    info_p = OUT / 'bake.json'
    info = json.loads(info_p.read_text(encoding='utf-8')) if info_p.exists() else {}
    info.update({'when': time.strftime('%Y-%m-%d %H:%M:%S'), 'source': str(SRC), 'lp': str(LP_FILE),
                 'base_props': rec['base_props'], 'margin_px': BAKE_MARGIN, 'passes': sorted(passes)})
    info.setdefault('shell_mm', {}).update(shells)
    info_p.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('готово', atlases, sorted(passes), f'{time.time() - t0:.0f} с')


if __name__ == '__main__':
    main()
