"""«Осока», текстуры этап 1 на игровой сетке — заготовки для Painter (по образцу tools/smg03/game_tex.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/osoka/game_tex.py -- [fbx] [maps] [normals]
→ _asset_src/osoka/tex/ (не в git):
  Osoka_low.fbx   — игровая сетка с развёрткой (work/osoka_game_uv_v01.blend, game_uv.py): материал = набор текстур Painter
                    (Tube, Launcher, Missile), детали слота набора — одна сетка «<набор>__<слот>_low» (маска слоя по имени);
  Osoka_high.fbx  — принятая форма v07 теми же группами «<набор>__<слот>_high» (детали игровой и принятой совпадают
                    по именам один к одному): Painter печёт AO, кривизну, толщину, положение с отбором по имени сетки;
  meshes.json     — набор → слот → сетки и отделка (для sp_finish.build_set); scene.json — габарит сцены;
  <набор>_maps.npz — положение (мм) и нормаль в каждом пикселе развёртки (Tube, Missile) — маски трафарета и отсека
                    ракеты считает tools/osoka/tex_masks.py;
  normals/<набор>_normal.png — карта нормалей запеканием в Blender (Painter 12.1 пересчитывает нормали игровой сетки
                    по-своему — у ИЗЛОМ-45 вокруг надписей шёл веер, у кромок полосы; приём tools/smg03/game_tex.py).
Копии внахлёст (uv_stack) на время запекания уходят за квадрат развёртки: Painter и Blender пекут только 0…1, копия берёт
карту своего оригинала (в игре развёртка без сдвига).
"""
from __future__ import annotations

import fnmatch
import math
import json
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402

MODEL = Path('E:/Models Blender/WEAPONS/Верба — модель')
HP = MODEL / 'work/osoka_v07.blend'
LP = MODEL / 'work/osoka_game_uv_v01.blend'
SPEC = MODEL / 'finish-spec.json'
OUT = ROOT / '_asset_src/osoka/tex'
UV = 'GameUV'
RES = {'Tube': 4096, 'Launcher': 4096, 'Missile': 2048}
MAP_SETS = ('Tube', 'Missile')
CAGE_M = 0.0008                    # луч нормали стартует на 0.8 мм снаружи игровой сетки
CAGE_NEAR_M = 0.00015              # второе запекание — с 0.15 мм (пазы у.же клетки, как у ИЗЛОМ-45)
RAY_M = 0.003                      # и идёт до 2.2 мм внутрь: отклонение игровой сетки до 0.9 мм, буквы 0.35
PAIRS = []
log = lambda *a: print('OSOKA_TEX', *a, flush=True)


def slot_table():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    return [(s['id'], s['parts'], s['finish']) for s in spec['slots']]


def slot_of(name, table):
    for sid, pats, _ in table:
        if any(fnmatch.fnmatchcase(name, p) for p in pats):
            return sid
    raise KeyError(f'деталь {name} не попала ни в один слот finish-spec.json')


def world_copy(o, name, coll, triangulate=False, keep_uv=True):
    """Оценённая копия детали в мировых координатах (поза покоя рига): одна развёртка GameUV или без развёртки."""
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(oe, preserve_all_data_layers=True, depsgraph=dg)
    me.transform(oe.matrix_world)
    for lay in [u.name for u in me.uv_layers if not (keep_uv and u.name == UV)]:
        me.uv_layers.remove(me.uv_layers[lay])
    if triangulate:
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY',
                              ngon_method='BEAUTY')
        # копия принятой формы теряла её взвешенные нормали: плоская боковина, нарезанная клетками 4 мм, затенялась
        # полосами по клеткам, и запекание переносило их в карты (штрихи по литью справа, проба v2). Нормали заново:
        # рёбра круче 30° — жёсткие (шаги скругления — 15°), остальное гладкое, вес — по площади граней
        bm.normal_update()
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0.0) <= math.radians(30.0)
        bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if triangulate:
        m = ob.modifiers.new('wn', 'WEIGHTED_NORMAL')
        m.keep_sharp = True
        m.weight = 50
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        ob.modifiers.clear()
        old = ob.data
        ob.data = me2
        me2.name = name
        bpy.data.meshes.remove(old)
    return ob


def join(objs, name, coll):
    """Детали слота — одна сетка (у Painter пара low/high — по имени); нормали деталей сохраняются."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return m


def set_material(o, name):
    o.data.materials.clear()
    o.data.materials.append(material(name))


def export_fbx(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE', use_mesh_modifiers=False,
                             axis_forward='-Z', axis_up='Y', object_types={'MESH'}, bake_anim=False)


def build_fbx():
    table = slot_table()
    finish_of = {sid: fin for sid, _, fin in table}
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    lows = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.data.polygons)]
    names = [o.name for o in lows]
    with bpy.data.libraries.load(str(HP), link=False) as (src, dst):
        hp_names = [str(n) for n in src.objects]
        dst.objects = list(hp_names)
    hp_coll = bpy.data.collections.new('HP_SRC')
    bpy.context.scene.collection.children.link(hp_coll)
    hp = {}
    for n, ob in zip(hp_names, dst.objects):
        if ob is None:
            continue
        hp_coll.objects.link(ob)
        if ob.type == 'MESH':
            hp[n] = ob
    bpy.context.view_layer.update()
    lo_coll = bpy.data.collections.new('LOW')
    hi_coll = bpy.data.collections.new('HIGH')
    for c in (lo_coll, hi_coll):
        bpy.context.scene.collection.children.link(c)
    groups = {}
    for o in lows:
        atlas = o.data.materials[0].name.replace('Osoka_', '') if o.data.materials else 'Launcher'
        groups.setdefault((atlas, slot_of(o.name, table)), []).append(o)
    meshes, low_out, high_out = {}, [], []
    for (atlas, sid), objs in sorted(groups.items()):
        key = f'{atlas}__{sid}'
        lo = join([world_copy(o, 'lc_' + o.name, lo_coll) for o in objs], key + '_low', lo_coll)
        set_material(lo, atlas)
        shifted = kit_uv.shift_stack_copies([lo], 1.0, uv=UV)
        miss = [o.name for o in objs if o.name not in hp]
        hi = join([world_copy(hp[o.name], 'hc_' + o.name, hi_coll, triangulate=True, keep_uv=False)
                   for o in objs if o.name in hp], key + '_high', hi_coll)
        set_material(hi, atlas)
        low_out.append(lo); high_out.append(hi)
        PAIRS.append((lo, hi, atlas))
        meshes.setdefault(atlas, {}).setdefault(sid, {'finish': finish_of[sid], 'meshes': []})['meshes'].append(lo.name)
        log(atlas, sid, 'деталей', len(objs), 'копий внахлёст', shifted, 'нет в принятой' if miss else '', miss or '')
    OUT.mkdir(parents=True, exist_ok=True)
    export_fbx(low_out, OUT / 'Osoka_low.fbx')
    export_fbx(high_out, OUT / 'Osoka_high.fbx')
    (OUT / 'meshes.json').write_text(json.dumps(meshes, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    cs = np.array([Vector(c) for ob in low_out for c in ob.bound_box]) * 1000.0
    scene = {'min_mm': cs.min(0).round(1).tolist(), 'max_mm': cs.max(0).round(1).tolist(),
             'size_mm': float((cs.max(0) - cs.min(0)).max().round(1))}
    (OUT / 'scene.json').write_text(json.dumps(scene, ensure_ascii=False), encoding='utf-8', newline='\n')
    # плотность наборов — из отчёта развёртки
    rep = json.loads((MODEL / 'work/osoka_game_uv_v01_uv.json').read_text(encoding='utf-8'))
    (OUT / 'px_mm.json').write_text(json.dumps({k: v['px_mm'] for k, v in rep.items() if isinstance(v, dict)}),
                                    encoding='utf-8', newline='\n')
    for o in list(hp_coll.objects):
        o.hide_render = True
    log('FBX', len(low_out), 'пар →', OUT, 'габарит сцены', scene['size_mm'], 'мм')
    return {a: [lo for lo, hi, at in PAIRS if at == a] for a in RES}


def _emit_material(kind, off, scale):
    mat = bpy.data.materials.new('tm_' + kind)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs[0])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    a = nt.nodes.new('ShaderNodeVectorMath')
    a.operation = 'MULTIPLY_ADD'
    nt.links.new(geo.outputs['Position' if kind == 'pos' else 'Normal'], a.inputs[0])
    a.inputs[1].default_value = scale
    a.inputs[2].default_value = off
    nt.links.new(a.outputs[0], em.inputs['Color'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    nt.nodes.active = tex
    return mat, tex


def bake_maps(set_name, objs, size):
    """Положение (мм) и нормаль в каждом пикселе развёртки набора — на процессоре, 1 выборка."""
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = 1
    S.render.bake.margin = 8
    S.render.bake.margin_type = 'EXTEND'
    S.render.bake.use_selected_to_active = False
    S.cycles.filter_width = 0.01
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
        ob.hide_render = ob not in objs
    pts = np.concatenate([np.array([v.co for v in o.data.vertices]) for o in objs])
    lo = pts.min(0) - 0.01
    hi = pts.max(0) + 0.01
    sc = 1.0 / (hi - lo)
    for o in objs:
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers[UV]
    bpy.context.view_layer.objects.active = objs[0]
    old = {o.name: list(o.data.materials) for o in objs}
    res = {}
    for kind, off, scale in (('pos', tuple(-lo * sc), tuple(sc)), ('nrm', (0.5,) * 3, (0.5,) * 3)):
        mat, tex = _emit_material(kind, off, scale)
        img = bpy.data.images.new('tm_' + kind, size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = 'Non-Color'
        tex.image = img
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        bpy.ops.object.bake(type='EMIT')
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        res[kind] = px.reshape(size, size, 4)[::-1, :, :3]
    for o in objs:
        o.data.materials.clear()
        for m in old[o.name]:
            o.data.materials.append(m)
    filled = np.any(res['nrm'] != 0.0, axis=-1)
    pos = ((res['pos'] / sc + lo) * 1000.0).astype(np.float32)
    nrm = res['nrm'] * 2.0 - 1.0
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    path = OUT / f'{set_name}_maps.npz'
    np.savez_compressed(path, pos=pos, nrm=nrm.astype(np.float16), filled=filled)
    log('карты развёртки', set_name, size, 'пикселей на сетке', int(filled.sum()), '→', path)


def bake_normals(samples=4, dilate_px=16):
    """Карта нормалей наборов в Blender (Cycles на процессоре): каждая сетка-слот — со своей принятой (пары по имени),
    касательные — по нормалям игровой сетки, OpenGL; изнанка с большой клеткой берётся с малой, остаток дорисовывается
    по соседям (tools/smg03/game_tex.py.bake_normals). → OUT/normals/<набор>_normal.png (16 бит)."""
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = samples
    bk = S.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.max_ray_distance = RAY_M
    bk.margin = 0
    bk.use_clear = False
    bk.normal_space = 'TANGENT'
    bk.normal_r, bk.normal_g, bk.normal_b = 'POS_X', 'POS_Y', 'POS_Z'
    out_dir = OUT / 'normals'
    out_dir.mkdir(parents=True, exist_ok=True)
    for ob in bpy.data.objects:
        ob.hide_render = False
    for atlas, size in RES.items():
        pairs = [(lo, hi) for lo, hi, a in PAIRS if a == atlas]
        if not pairs:
            continue
        runs = []
        for cage in (CAGE_M, CAGE_NEAR_M):
            bk.cage_extrusion = cage
            img = bpy.data.images.new('nb_' + atlas, size, size, float_buffer=True, alpha=True)
            img.colorspace_settings.name = 'Non-Color'
            img.pixels.foreach_set(np.tile(np.array([0.5, 0.5, 1.0, 0.0], np.float32), size * size))
            mat = bpy.data.materials.new('nb_' + atlas)
            mat.use_nodes = True
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = img
            mat.node_tree.nodes.active = tex
            for lo, hi in pairs:
                keep = list(lo.data.materials)
                lo.data.materials.clear()
                lo.data.materials.append(mat)
                lo.data.uv_layers.active = lo.data.uv_layers[UV]
                bpy.ops.object.select_all(action='DESELECT')
                hi.select_set(True)
                lo.select_set(True)
                bpy.context.view_layer.objects.active = lo
                bpy.ops.object.bake(type='NORMAL')
                lo.data.materials.clear()
                for m in keep:
                    lo.data.materials.append(m)
            px = np.empty(size * size * 4, np.float32)
            img.pixels.foreach_get(px)
            runs.append(px.reshape(size, size, 4))
        bk.cage_extrusion = CAGE_M
        far, near = runs
        rgb, filled = far[..., :3].copy(), far[..., 3] > 0.5
        back = filled & (far[..., 2] < 0.5)
        take = back & (near[..., 3] > 0.5) & (near[..., 2] >= 0.5)
        rgb[take] = near[..., :3][take]
        left = back & ~take
        filled = filled & ~left
        log('нормаль', atlas, 'изнанка', int(back.sum()), 'взято с малой клеткой', int(take.sum()), 'дорисовано',
            int(left.sum()))
        for _ in range(dilate_px):
            acc = np.zeros_like(rgb)
            cnt = np.zeros(filled.shape, np.float32)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
                f = np.roll(np.roll(filled, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * f[..., None]
                cnt += f
            grow = (~filled) & (cnt > 0)
            if not grow.any():
                break
            rgb[grow] = acc[grow] / cnt[grow][:, None]
            filled = filled | grow
        rgb[~filled] = (0.5, 0.5, 1.0)
        n = rgb * 2.0 - 1.0
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
        rgb = n * 0.5 + 0.5
        out = bpy.data.images.new('nbo_' + atlas, size, size, float_buffer=True, alpha=False)
        out.colorspace_settings.name = 'Non-Color'
        out.pixels.foreach_set(np.concatenate([rgb, np.ones((size, size, 1), np.float32)], -1).ravel())
        path = out_dir / f'{atlas}_normal.png'
        S.render.image_settings.file_format = 'PNG'
        S.render.image_settings.color_mode = 'RGB'
        S.render.image_settings.color_depth = '16'
        out.save_render(str(path), scene=S)
        log('нормаль', atlas, size, 'пар', len(pairs), '→', path)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    stages = set(args) or {'fbx', 'maps'}
    sets = build_fbx()
    if 'maps' in stages:
        for s in MAP_SETS:
            bake_maps(s, sets[s], RES[s])
    if 'normals' in stages:
        bake_normals()


if __name__ == '__main__':
    main()
