"""Глушитель ГРАНЬ-15 → обвес игры: игровая сетка, запекание с high-poly, glTF — тем же конвейером, что ствол
(game_lp.py, game_bake.py, game_export.py), и в формате обвесов-моделей (WeaponMods._model_part, как supp_veras, supp_pm).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/ar15/supp_game.py -- lp|bake|export [--cpu] [--samples N]
затем python -X utf8 tools/ar15/supp_pack.py (карты), export, --import, python -X utf8 tools/ar15/game_imports.py, --import.

Источник — та же принятая high-poly, что у ствола: `AR-15_износ_этап2_v1.blend` (глушитель там с отделкой этапа 1 «песок» v7 —
термостойкий Cerakote корпуса, жаропрочная сталь, хром штифта; в план износа этапа 2 глушитель не входил, его карты
совпадают с этапом 1). Отдельный `Глушитель_v01.blend` не текстурирован — в игру не идёт.
Оси: в исходнике начало Suppressor_body — центр посадочного торца на оси канала, ось канала +X, верх +Z; игровая сетка
строится в этих осях (поворот глушителя «в стороне» в исходнике не важен), на экспорте — оси обвеса игры: +Z к дулу,
+Y вверх, +X — левая сторона стрелка (как supp_veras), начало — задний торец.
Узлы: Body (корпус), Body_Latch (рычаг защёлки со штифтом — подвижная деталь, начало в оси штифта), Body_LOD1 (вдали,
одна сетка). Перегородки внутри корпуса не видны — в игру не идут. Атлас один, 2K.
→ lp: _asset_src/ar15/game/supp/AR15_Supp_LP.blend + supp.json; bake: supp/raw/Supp_<канал>.png;
  export: assets/models/attachments/supp_gran/supp_gran.glb + manifest.json.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/ar15'))
from asset_kit import uv as kit_uv  # noqa: E402
import game_bake  # noqa: E402
import game_lp  # noqa: E402

SRC = game_lp.SRC
WORK = ROOT / '_asset_src/ar15/game/supp'
RAW = WORK / 'raw'
OUT = ROOT / 'assets/models/attachments/supp_gran'
ROOT_PART = 'Suppressor_body'
SIZE = 2048
# деталь исходника → (узел игры, бюджет треугольников); корпус — тело вращения Ø40 со рёбрами сзади: 2400 держат круг
# без граней на виду (у тела ствола в руках то же правило «по видимости»), рычаг защёлки мелкий
PARTS = {'Suppressor_body': ('Body', 2400), 'Suppressor_latch': ('Latch', 200), 'Suppressor_latch_pin': ('Latch', 24)}
LOD1_RATIO = 0.3
log = lambda *a: print('SUPP', *a, flush=True)

ap = argparse.ArgumentParser()
ap.add_argument('stage', choices=['lp', 'bake', 'export'])
ap.add_argument('--cpu', action='store_true')
ap.add_argument('--samples', type=int, default=0)
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def body_frame():
    """Мировая матрица корпуса в исходнике (с драйверами) — от неё считаются оси глушителя."""
    dg = game_lp.refresh()
    return bpy.data.objects[ROOT_PART].evaluated_get(dg).matrix_world.copy()


def lp():
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    hp = {o.name: o for o in bpy.data.objects}
    to_local = body_frame().inverted()
    coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(coll)
    rec = {'source': str(SRC), 'parts': {}, 'nodes': {}}
    pieces = {}
    for name, (node, budget) in PARTS.items():
        o = game_lp.evaluated_copy(hp[name], 'lp_' + name, coll)
        o.data.transform(to_local)                   # evaluated_copy кладёт в мир — переводим в оси корпуса
        n0 = game_lp.tris(o.data)
        n = game_lp.simplify(o, min(budget, n0), organic=False)
        # отклонение — в тех же осях: копия исходника в осях корпуса
        ref = game_lp.evaluated_copy(hp[name], 'ref_' + name, coll)
        ref.data.transform(to_local)
        dev = game_lp.deviation(o, ref)
        bpy.data.objects.remove(ref, do_unlink=True)
        rec['parts'][name] = {'node': node, 'hp_tris': n0, 'tris': n, 'dev_mm': dev}
        if name == 'Suppressor_latch_pin':
            # ось рычага — середина штифта (в осях корпуса)
            vs = [v.co for v in o.data.vertices]
            rec['latch_pivot_m'] = [round(sum(v[i] for v in vs) / len(vs), 5) for i in range(3)]
        pieces.setdefault(node, []).append(o)
        log('деталь', name, n0, '→', n, 'отклонение, мм', dev)
    for o in list(bpy.data.objects):
        if o.name not in coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    game = []
    for node, objs in pieces.items():
        j = game_lp.join(objs, node) if len(objs) > 1 else objs[0]
        j.name = j.data.name = node
        j.data.materials.clear()
        mat = bpy.data.materials.get('AR15 • Supp') or bpy.data.materials.new('AR15 • Supp')
        mat.use_nodes = True
        j.data.materials.append(mat)
        j['node'] = node
        j['hp'] = [n for n, (nd, _b) in PARTS.items() if nd == node]
        game.append(j)
    body = bpy.data.objects['Body']
    xs = [v.co.x for v in body.data.vertices]
    rs = [math.hypot(v.co.y, v.co.z) for v in body.data.vertices]
    log('корпус: x от', round(min(xs) * 1000, 2), 'до', round(max(xs) * 1000, 2), 'мм, радиус до', round(max(rs) * 1000, 2))
    rec['length_m'] = round(max(xs), 5)
    rec['rear_m'] = round(min(xs), 5)
    rec['radius_m'] = round(max(rs), 5)
    # развёртка по видимости: поз механики у глушителя нет; глаз — от бедра и в прицеливании ГРАНЬ-15 (тормоз впереди
    # хвата на 0,51 м, задний торец глушителя на 0,05 м позади среза тормоза, линия прицеливания на 0,063 м выше оси)
    eyes = [kit_uv.Eye((-0.61, 0.13, 0.12), name='hip'), kit_uv.Eye((-0.57, 0.0, 0.063), k_max=kit_uv.ADS_K, name='ads')]
    poses = {'rest': {}}
    kit_uv.smart_unwrap(game)
    cls = kit_uv.visibility(game, poses, lambda o: o['node'])
    for o, c in zip(game, cls):
        drop = [i for i, k in enumerate(c) if k == kit_uv.CONTACT]
        if drop and len(drop) < len(o.data.polygons):
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES')
            bm.to_mesh(o.data)
            bm.free()
    cls = kit_uv.visibility(game, poses, lambda o: o['node'])
    rep = kit_uv.layout(game, SIZE, classes=cls, eyes=eyes, log=log)
    kit_uv.harden_on_seams(game)
    rep['report'] = kit_uv.report(game, SIZE, classes=cls)
    rep['verify'] = kit_uv.verify(game, SIZE, classes=cls)
    rec['atlas'] = {'size': SIZE, **rep}
    log('атлас', SIZE, rep['report'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True
        rec['nodes'][o.name] = {'tris': game_lp.tris(o.data), 'hp': list(o['hp'])}
    # вдали — одна сетка с той же развёрткой (карты общие)
    copies = []
    for o in game:
        c = o.copy()
        c.data = o.data.copy()
        coll.objects.link(c)
        copies.append(c)
    far = game_lp.join(copies, 'Body_LOD1')
    far.name = far.data.name = 'Body_LOD1'
    game_lp.select_only(far)
    d = far.modifiers.new('lod', 'DECIMATE')
    d.ratio = LOD1_RATIO
    d.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=d.name)
    far['node'] = 'LOD1'
    rec['nodes']['Body_LOD1'] = {'tris': game_lp.tris(far.data)}
    rec['tris'] = sum(v['tris'] for k, v in rec['nodes'].items() if k != 'Body_LOD1')
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    WORK.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'AR15_Supp_LP.blend'), compress=True)
    (WORK / 'supp.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('сохранено: в руках', rec['tris'], 'вдали', rec['nodes']['Body_LOD1']['tris'])


def bake():
    rec = json.loads((WORK / 'supp.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=rec['source'])
    hp = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
    frame = body_frame()
    with bpy.data.libraries.load(str(WORK / 'AR15_Supp_LP.blend'), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ('Body', 'Latch')]
    coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(coll)
    lp_objs = []
    for o in dst.objects:
        coll.objects.link(o)
        o.matrix_world = frame                       # сетка в осях корпуса → на место глушителя в исходнике
        lp_objs.append(o)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'GPU'
    try:
        if args.cpu:
            raise RuntimeError('cpu')
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for dv in prefs.devices:
            dv.use = dv.type == 'OPTIX'
    except Exception:
        sc.cycles.device = 'CPU'
    bk = sc.render.bake
    bk.use_clear = False
    bk.margin = 5
    bk.margin_type = 'EXTEND'
    shown = [o for o in hp.values() if not o.hide_render]
    kit_uv.shift_stack_copies(lp_objs, 1.0)
    RAW.mkdir(parents=True, exist_ok=True)
    for ch in game_bake.CHANNELS:
        img = game_bake.image(f'Supp_{ch}', SIZE, ch != 'color')
        for o in lp_objs:
            game_bake.target_node(o.data.materials[0], img)
        if ch == 'ao':
            for h in shown:
                h.hide_render = True
            sc.cycles.samples = args.samples or 128
            bpy.ops.object.select_all(action='DESELECT')
            for o in lp_objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = lp_objs[0]
            bk.use_selected_to_active = False
            bpy.ops.object.bake(type='AO')
            for h in shown:
                h.hide_render = False
        else:
            sc.cycles.samples = args.samples or (16 if ch == 'normal' else 1)
            for o in lp_objs:
                srcs = [hp[n] for n in o['hp'] if n in hp]
                swaps = {}
                if ch != 'normal':
                    for h in srcs:
                        for s in h.material_slots:
                            m = s.material
                            if m and m.name not in swaps and m.use_nodes:
                                swaps[m.name] = (m, game_bake.emission_swap(m, ch))
                bpy.ops.object.select_all(action='DESELECT')
                for h in srcs:
                    h.hide_set(False)
                    h.select_set(True)
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                bk.use_selected_to_active = True
                bk.cage_extrusion = game_bake.EXTRUSION
                bk.max_ray_distance = game_bake.RAY
                bpy.ops.object.bake(type='NORMAL' if ch == 'normal' else 'EMIT', normal_space='TANGENT')
                for m, keep in swaps.values():
                    game_bake.emission_restore(m, keep)
        path = RAW / f'Supp_{ch}.png'
        img.filepath_raw = str(path)
        img.file_format = 'PNG'
        img.save()
        log('запечено', ch, path.name)
    kit_uv.shift_stack_copies(lp_objs, -1.0)


def export():
    rec = json.loads((WORK / 'supp.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'AR15_Supp_LP.blend'))
    # оси глушителя (канал +X, верх +Z, левая сторона +Y) → оси обвеса игры после экспорта Y-up (+Z к дулу, +Y вверх,
    # +X влево): поворот на −90° вокруг Z, как у ствола (game_export.TO_GAME)
    to_game = Matrix.Rotation(math.radians(-90), 4, 'Z')
    mat = bpy.data.materials.get('AR15 • Supp')
    mat.name = 'supp_gran'
    objs = []
    for name, out in (('Body', 'Body'), ('Latch', 'Body_Latch'), ('Body_LOD1', 'Body_LOD1')):
        o = bpy.data.objects[name]
        o.name = o.data.name = out
        for uvl in list(o.data.uv_layers):
            if uvl.name != 'GameUV':
                o.data.uv_layers.remove(uvl)
        for a in ('uv_stack', 'uv_group'):
            if a in o.data.attributes:
                o.data.attributes.remove(o.data.attributes[a])
        o.data.transform(to_game)
        o.matrix_world = Matrix.Identity(4)
        objs.append(o)
    # рычаг защёлки — свой узел с началом в оси штифта
    latch = bpy.data.objects['Body_Latch']
    piv = to_game @ Vector(rec['latch_pivot_m'])
    latch.data.transform(Matrix.Translation(-piv))
    latch.location = piv
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'supp_gran.glb'), export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
                              export_tangents=False, export_animations=False, export_skins=False, export_morph=False,
                              export_extras=False, export_materials='PLACEHOLDER')
    pts = [o.matrix_world @ v.co for o in objs if o.name != 'Body_LOD1' for v in o.data.vertices]
    # оси Blender → оси игры (glTF Y-up): (x, y, z)_игры = (x, z, −y)_Blender
    g = [(p.x, p.z, -p.y) for p in pts]
    man = {'source': {'100': f'{Path(rec["source"]).name} — Suppressor_body, Suppressor_latch, Suppressor_latch_pin'},
           'triangles': {k: v['tris'] for k, v in rec['nodes'].items()},
           'axis': 'X left, Y up, Z forward',
           'bounds_m': {'min': [round(min(p[i] for p in g), 4) for i in range(3)],
                        'max': [round(max(p[i] for p in g), 4) for i in range(3)]},
           'latch_pivot_m': [round(piv.x, 5), round(piv.z, 5), round(-piv.y, 5)],
           'states': [100], 'texture_size': SIZE,
           'finish': 'этап 1 «песок» v7 (Cerakote корпуса, жаропрочная сталь, хром штифта); износа этапа 2 нет',
           'uv': rec['atlas']['report']}
    (OUT / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1, default=list) + '\n',
                                       encoding='utf-8', newline='\n')
    log('записано supp_gran.glb', man['triangles'], man['bounds_m'])


{'lp': lp, 'bake': bake, 'export': export}[args.stage]()
