"""ВСС-М v8 → игровая сетка (статичная модель игры: Body / Stock / Magazine) и магазины на 10, 20, 30 как предметы.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/game_lp.py
→ _asset_src/vss_m_v8_game/lp/VSS_Game_LP.blend + lp/parts.json (не в git).

Источник — _asset_src/vss_m_v8/VSS_M_v8_sp.blend: форма v8 и развёртки наборов Painter (отделка принята владельцем 26.10;
исходник не меняется). Оси исходника: дуло +X, верх +Z, левая сторона стрелка +Y, метры; перевод в оси игры — на
экспорте (game_export.py). Своих рук и клипов у ВСС нет (руки делает владелец): в игре это статичная модель
(asset_kind static) с общими руками на метках хвата, поэтому подвижные детали склеены в узлы:
  Body — коробка, затворная группа в окне, органы управления, цевьё, муфта с планками, глушитель, прицельные;
  Stock — приклад с затыльником и крепежом (узел Stock* игра помечает part=stock);
  Magazine — вставленный магазин на 10 с двумя верхними патронами (part=mag: его заменяет магазин на 20 / 30) —
    на экспорте копия Mag10, поставленная в гнездо.
Магазины-предметы (Mag10 / Mag20 / Mag30) — свои узлы в атласе Mags.
Скрытое внутри (пружина, перегородки глушителя, канал ствола в муфте, патроны ниже двух верхних) — в игру не идёт.

Бюджет — по видимости (правило «в руках до 40 тыс.» на ствол с магазином; владелец 2026-10-19): мелкий рельеф —
в нормалях. Атласы: Steel 4096, Wood 4096, Polymer 2048 (цевьё, затыльник), Cerakote 2048 (муфта и задний прицел —
свой материал с приглушённым отражением, как в Blender), Mags 4096 (три магазина: на 2048 было 3,8 пикс/мм). Развёртка — tools/asset_kit/uv.py.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402

SRC = ROOT / '_asset_src/vss_m_v8/VSS_M_v8_sp.blend'
WORK = ROOT / '_asset_src/vss_m_v8_game'
OUT = WORK / 'lp'
OUT.mkdir(parents=True, exist_ok=True)
SHARP = math.radians(60)
ATLAS_SIZE = {'Steel': 4096, 'Wood': 4096, 'Polymer': 2048, 'Cerakote': 2048, 'Mags': 4096}
MATNAME = {a: f'VSS • {a}' for a in ATLAS_SIZE}

# деталь исходника → (узел игры, атлас, бюджет треугольников). Нет в списке — в игру не идёт.
PARTS = {
    # коробка и крышка
    'Receiver_cover': ('Body', 'Steel', 3400), 'Receiver_lower': ('Body', 'Steel', 1800),
    'Cover_picatinny': ('Body', 'Steel', 1100), 'Receiver_trunnion': ('Body', 'Steel', 300),
    'Cover_latch_button': ('Body', 'Steel', 120),
    **{f'Receiver_pin_{i}_{s}': ('Body', 'Steel', 40) for i in range(6) for s in 'LR'},
    'Side_mount_dovetail': ('Body', 'Steel', 420),
    **{f'Side_mount_rivet_{i}': ('Body', 'Steel', 40) for i in range(3)},
    # затворная группа в окне коробки
    'Bolt_carrier': ('Body', 'Steel', 800), 'Bolt': ('Body', 'Steel', 600), 'Bolt_carrier_plate': ('Body', 'Steel', 450),
    'Bolt_carrier_web': ('Body', 'Steel', 160), 'Bolt_extractor': ('Body', 'Steel', 60), 'Charging_handle': ('Body', 'Steel', 600),
    # органы управления
    'Safety_lever': ('Body', 'Steel', 700), 'Safety_axis_end_L': ('Body', 'Steel', 60), 'Safety_visor': ('Body', 'Steel', 160),
    'Fire_selector': ('Body', 'Steel', 320), 'Trigger': ('Body', 'Steel', 380), 'Trigger_guard': ('Body', 'Steel', 520),
    'Magazine_catch': ('Body', 'Steel', 320),
    # перед: глушитель, мушка, антабка
    'Suppressor_body': ('Body', 'Steel', 2600), 'Suppressor_knurl': ('Body', 'Steel', 1600), 'Barrel': ('Body', 'Steel', 260),
    'Front_sight_base': ('Body', 'Steel', 620), 'Front_sight_post': ('Body', 'Steel', 140), 'Front_sight_weld': ('Body', 'Steel', 140),
    'Front_sling_bracket': ('Body', 'Steel', 260), 'Front_sling_swivel': ('Body', 'Steel', 260), 'Rail_sleeve_screws': ('Body', 'Steel', 240),
    # цевьё
    'Handguard': ('Body', 'Polymer', 3200),
    # муфта с планками и задний прицел — Cerakote
    'Rail_sleeve': ('Body', 'Cerakote', 3600), 'Rear_sight_base': ('Body', 'Cerakote', 560),
    'Rear_sight_leaf': ('Body', 'Cerakote', 760), 'Rear_sight_slider': ('Body', 'Cerakote', 320),
    'Rear_sight_weld': ('Body', 'Cerakote', 300), 'Rear_sight_hinge_pin': ('Body', 'Steel', 60),
    # приклад
    'Wood_stock_v8': ('Stock', 'Wood', 6800), 'Rubber_butt_pad': ('Stock', 'Polymer', 1100),
    'Stock_release_button': ('Stock', 'Steel', 160), 'Stock_screw_L': ('Stock', 'Steel', 60), 'Stock_screw_R': ('Stock', 'Steel', 60),
    'Stock_sling_plate': ('Stock', 'Steel', 160), 'Stock_sling_rivet_0': ('Stock', 'Steel', 40), 'Stock_sling_rivet_1': ('Stock', 'Steel', 40),
    'Stock_sling_swivel': ('Stock', 'Steel', 220),
}
# магазины: корпус и мелкие детали — свой узел; патроны — два верхних (ниже их не видно в корпусе)
# вставленный в винтовку магазин — та же сетка, что Mag10 (экспорт ставит её на место): атлас не тратится дважды
MAGS = {'Mag10': ('Magazine_10', 0.0, 2400), 'Mag20': ('Magazine_20', 0.160, 2800), 'Mag30': ('Magazine_30', 0.300, 3200)}
MAG_PARTS = ('_floorplate', '_follower', '_plate_button')
MAG_ROUNDS, ROUND_TRIS = 2, 320
# магазины-предметы не стоят в винтовке: на время развёртки и запекания их сдвигают от неё (иначе лучи видимости и
# запекания ловят чужую копию в том же месте); игровые оси — от гнезда магазина, сдвиг экспорт снимает
MAG_ASIDE = {'Mag10': (0, -0.25, 0), 'Mag20': (0, -0.40, 0), 'Mag30': (0, -0.55, 0)}

# метки (оси исходника, м): начало осей игры — середина хвата в вырезе приклада
GRIP = Vector((0.320, 0.0, -0.072))
MARKS = {'Muzzle': (0.894, 0.0, 0.010), 'SightRear': (0.607, 0.0, 0.0553), 'SightFront': (0.8795, 0.0, 0.0563),
         'MagMount': (0.4585, 0.0, 0.0075)}
# точки глаза для плотности развёртки: от бедра (камера левее и выше, винтовка правее) и в прицеливании (над гребнем)
EYES = [kit_uv.Eye((0.10, 0.14, 0.10), name='hip'),
        kit_uv.Eye((0.17, 0.0, 0.0553), k_max=kit_uv.ADS_K, name='ads')]
log = lambda *a: print('VSS_LP', *a, flush=True)


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def append_source(coll):
    with bpy.data.libraries.load(str(SRC), link=False) as (src, dst):
        dst.objects = list(src.objects)
    out = {}
    for o in dst.objects:
        if o is None:
            continue
        coll.objects.link(o)
        out[o.name] = o
    return out


def evaluated_copy(o, name, coll, shift=None):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    if shift is not None:
        me.transform(Matrix.Translation(shift))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def strip(me) -> None:
    """Без развёрток, цветов и своих нормалей исходника: сетка упрощается свободно, развёртка — заново."""
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    me.materials.clear()


def simplify(o, budget: int, organic: bool) -> int:
    me = o.data
    strip(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    select_only(o)
    if tris(me) > budget and not organic:
        d = o.modifiers.new('planar', 'DECIMATE')
        d.decimate_type = 'DISSOLVE'
        d.angle_limit = math.radians(0.6)
        bpy.ops.object.modifier_apply(modifier=d.name)
    for _ in range(8):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        # органика (приклад): ступенями не более чем в 8 раз — без длинных клиньев на изгибах
        d.ratio = max(budget / n, 1 / 8) if organic else max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def deviation(lp, hp_objs) -> tuple:
    """Отклонение игровой сетки от исходника, мм: наибольшее и среднее по вершинам."""
    verts, polys = [], []
    for h in hp_objs:
        base = len(verts)
        m = h.matrix_world
        verts += [m @ v.co for v in h.data.vertices]
        polys += [[base + i for i in p.vertices] for p in h.data.polygons]
    if not polys:
        return 0.0, 0.0
    bvh = BVHTree.FromPolygons(verts, polys)
    ds = []
    for v in lp.data.vertices:
        hit = bvh.find_nearest(lp.matrix_world @ v.co)
        if hit[0] is not None:
            ds.append(hit[3])
    return (round(max(ds) * 1000, 2), round(sum(ds) / len(ds) * 1000, 3)) if ds else (0.0, 0.0)


def join(objs, name, coll):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = name
    j.data.name = name
    return j


def material(atlas):
    m = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    m.use_nodes = True
    return m


def main():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    hp_coll = bpy.data.collections.new('HP')
    bpy.context.scene.collection.children.link(hp_coll)
    lp_coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(lp_coll)
    hp = append_source(hp_coll)
    rec = {'source': str(SRC), 'grip_m': list(GRIP), 'marks_m': MARKS, 'parts': {}, 'nodes': {}, 'atlases': {},
           'mag_aside_m': MAG_ASIDE}
    pieces = {}                                   # (узел, атлас) → [игровые куски]
    sources = {}                                  # имя игрового куска → [детали исходника]
    total = 0
    for name, (node, atlas, budget) in PARTS.items():
        if name not in hp:
            log('нет детали', name)
            continue
        o = evaluated_copy(hp[name], 'lp_' + name, lp_coll)
        n0 = tris(o.data)
        n = simplify(o, min(budget, n0), organic=name == 'Wood_stock_v8')
        dev = deviation(o, [hp[name]])
        rec['parts'][name] = {'node': node, 'atlas': atlas, 'hp_tris': n0, 'tris': n, 'dev_mm': dev}
        pieces.setdefault((node, atlas), []).append(o)
        sources[o.name] = [name]
        total += n
    # магазины: вставленный (Magazine) и предметы (Mag10/20/30, сдвинуты на место вставленного и в сторону)
    for node, (base, dy, budget) in MAGS.items():
        names = [base] + [base + p for p in MAG_PARTS if base + p in hp]
        rounds = [f'{base}_round_{i:02d}' for i in range(1, MAG_ROUNDS + 1) if f'{base}_round_{i:02d}' in hp]
        shift = Vector((0, -dy, 0)) + Vector(MAG_ASIDE.get(node, (0, 0, 0)))
        objs = []
        body_budget = budget - ROUND_TRIS * len(rounds)
        for i, nm in enumerate(names):
            o = evaluated_copy(hp[nm], f'lp_{node}_{nm}', lp_coll, shift)
            n0 = tris(o.data)
            b = body_budget if i == 0 else max(80, int(n0 * 0.15))
            simplify(o, min(b, n0), organic=False)
            objs.append(o)
        for nm in rounds:
            o = evaluated_copy(hp[nm], f'lp_{node}_{nm}', lp_coll, shift)
            simplify(o, ROUND_TRIS, organic=False)
            objs.append(o)
        j = join(objs, f'lp_{node}', lp_coll)
        n = tris(j.data)
        rec['parts'][node] = {'node': node, 'atlas': 'Mags', 'hp': names + rounds, 'tris': n, 'shift_m': list(shift)}
        pieces.setdefault((node, 'Mags'), []).append(j)
        sources[j.name] = names + rounds
        if node == 'Mag10':
            total += n
    rec['rifle_tris'] = total
    log('треугольников в руках (винтовка с магазином на 10):', total)
    # узлы игры: по куску на (узел, атлас), материал атласа
    game = []
    for (node, atlas), objs in pieces.items():
        nm = f'{node}_{atlas}' if node in ('Body', 'Stock') else node
        hp_list = sum((sources.get(o.name, []) for o in objs), [])
        j = join(objs, nm, lp_coll) if len(objs) > 1 else objs[0]
        j.name = nm
        j.data.name = nm
        j.data.materials.clear()
        j.data.materials.append(material(atlas))
        for p in j.data.polygons:
            p.material_index = 0
        j['atlas'] = atlas
        j['node'] = node
        j['hp'] = hp_list
        game.append(j)
        rec['nodes'][nm] = {'node': node, 'atlas': atlas, 'tris': tris(j.data), 'hp': list(j['hp'])}
    # развёртка по атласам
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        if not objs:
            continue
        kit_uv.smart_unwrap(objs)
        cls = kit_uv.visibility(objs)
        # прижатые грани (во всех лучах ближе 4 мм к соседней детали) не видны — удаляются
        for o, c in zip(objs, cls):
            drop = [i for i, k in enumerate(c) if k == kit_uv.CONTACT]
            if drop and len(drop) < len(o.data.polygons):
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES')
                bm.to_mesh(o.data)
                bm.free()
        cls = kit_uv.visibility(objs)
        eyes = EYES if atlas != 'Mags' else []
        rep = kit_uv.layout(objs, size, classes=cls, eyes=eyes, log=log)
        kit_uv.harden_on_seams(objs)
        rep['report'] = kit_uv.report(objs, size, classes=cls)
        rep['verify'] = kit_uv.verify(objs, size, classes=cls)
        rec['atlases'][atlas] = {'size': size, 'objects': [o.name for o in objs], **rep}
        if rep['report']['fill'] < kit_uv.FILL_MIN:
            log('UV_FILL_LOW', atlas, rep['report']['fill'])
        log('атлас', atlas, size, rep['report'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True
        rec['nodes'][o.name]['tris'] = tris(o.data)
    bpy.data.collections.remove(hp_coll)
    for o in list(bpy.data.objects):
        if o.name not in [g.name for g in game]:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / 'VSS_Game_LP.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8', newline='\n')
    log('сохранено', path, 'в руках', total)


main()
