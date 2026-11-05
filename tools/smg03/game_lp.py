"""ИЗЛОМ-45 (ПП по мотивам KRISS Vector Gen II) → игровая сетка: детали по узлам игры (подвижные и съёмные — свои узлы
по моверам исходника), атласы, развёртка по видимости.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/smg03/game_lp.py
→ _asset_src/smg03/game/lp/SMG03_Game_LP.blend + lp/parts.json (не в git).

Источник — принятая геометрия v06 (владелец 2026-11-05: «можно переходить к ретопологии»): `ПП-Vector_геометрия_v06.blend`
в папке модели. Исходник не меняется: игровые копии делаются из вычисленных деталей, исходные удаляются перед
сохранением в свою папку. -y — драйверы механики (SMG03_Controls) на выражениях Python: без них позы видимости не
считаются. Оси исходника: дуло +X, верх +Z, левая сторона стрелка +Y, метры; в оси игры — на экспорте.

Как у ГРАНЬ-15 (tools/ar15/game_lp.py): упрощение по бюджету детали (сначала плоское растворение, затем схлопывание),
развёртка — tools/asset_kit/uv.py. Отличие: лучи видимости — по всей сборке сразу (корпус закрывает затвор, ось — головку),
дважды: с магазином на 13 и с магазином на 30 (стоят в одном месте и закрывали бы друг друга). Бюджет — «в руках до
40 тыс.» с магазином (владелец 2026-10-19); магазин на 30 — свой предмет. Мелкий рельеф (шагрень и рифление рукояти,
надписи, знак, рифление рычагов и маховичка, витки барабана, канавки накладки) — в карту нормалей. Текстуры — дальше
на этой сетке (Painter, запекание с high-poly).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402
from ar15.game_lp import (tris, refresh, evaluated_copy, strip, select_only, deviation, join,  # noqa: E402
                          world_bbox)

SRC = Path('E:/Models Blender/WEAPONS/Vector — модель/ПП-Vector_геометрия_v06.blend')
# корпус для игровой сетки — та же сборка без надписей, знаков и шагрени (SMG03_LP_SOURCE=1 build.py): от них после
# упрощения оставались обрывки и «шум»; в карту нормалей они запекаются с настоящей high-poly (SRC)
LP_SOURCE = ROOT / '_asset_src/smg03/SMG03_lp_source.blend'
LP_FROM_SOURCE = ('Receiver',)
WORK = ROOT / '_asset_src/smg03/game'
OUT = WORK / 'lp'
OUT.mkdir(parents=True, exist_ok=True)
# атласы: корпус (полимер, крупные плоскости, рукоять и скоба) — 4K; сталь и мелкие органы управления, прицельные
# у глаза — 4K; приклад — 2K; магазины — по 2K (предметы игры)
ATLAS_SIZE = {'Receiver': 4096, 'Steel': 4096, 'Stock': 2048, 'Mag13': 2048, 'Mag30': 2048}
MATNAME = {a: f'SMG03 • {a}' for a in ATLAS_SIZE}
CONTROLS = 'SMG03_Controls'
# мовер исходника → узел игры (навык godot-asset-preparation, «Подвижные и съёмные детали»): узел — по ближайшему
# объекту с драйвером над деталью; магазины — узел Magazine (атласы Mag13 / Mag30 — разные предметы)
MOVERS = {
    'Bolt_mover': 'Bolt', 'Charging_handle_mover': 'ChargingSlider', 'Charging_handle': 'ChargingHandle',
    'Trigger': 'Trigger', 'Safety_L': 'SafetyL', 'Safety_R': 'SafetyR', 'Selector_L': 'SelectorL',
    'Selector_R': 'SelectorR', 'Mag_release_L': 'MagReleaseL', 'Mag_release_R': 'MagReleaseR',
    'Bolt_catch': 'BoltCatch', 'Rear_sight_leaf': 'RearSightLeaf', 'Front_sight_leaf': 'FrontSightLeaf',
    'Stock_latch': 'StockLatch', 'Stock_pivot': 'Stock', 'Magazine_mover': 'Magazine',
}
# позы видимости — из органов управления исходника (значения покоя возвращаются): всё нажато и отведено, магазин вынут,
# приклад сложен; рукоятка только откинута (её внутренняя сторона у борта); задержка снята (рычаг в другую сторону);
# прицельные сложены
POSE_PROPS = {
    'moved': {'charging_handle': 1.0, 'trigger': 1.0, 'safety': 1.0, 'selector': 1.0, 'mag_release': 1.0,
              'mag_out': 1.0, 'bolt_catch': 1.0, 'stock_fold': 1.0, 'stock_latch': 1.0},
    'turned': {'charging_handle': 0.2, 'bolt_release': 1.0, 'selector': 0.5, 'stock_fold': 0.5},
    'folded': {'front_sight': 0.0, 'rear_sight': 0.0},
}

# деталь исходника → (атлас, бюджет треугольников); узел — по моверу. Нет в списке — в игру не идёт.
PARTS = {
    # корпус: верх с планкой, передний блок с нижней планкой, шахта, рукоять, скоба и тяги — одно тело исходника
    'Receiver': ('Receiver', 15000),
    # сталь и мелочь корпуса
    'Side_rail_L': ('Steel', 500), 'Side_rail_R': ('Steel', 500),
    'Side_rail_screw_L0': ('Steel', 60), 'Side_rail_screw_L1': ('Steel', 60),
    'Side_rail_screw_R0': ('Steel', 60), 'Side_rail_screw_R1': ('Steel', 60),
    'Barrel': ('Steel', 700), 'Thread_cap': ('Steel', 900),
    'Bolt': ('Steel', 900), 'Extractor': ('Steel', 80), 'Extractor_pin': ('Steel', 24), 'Bolt_arm_pin': ('Steel', 40),
    'Firing_pin_retainer': ('Steel', 24), 'Ejector': ('Steel', 40),
    'Charging_handle': ('Steel', 700), 'Charging_handle_slider': ('Steel', 160), 'Charging_handle_pin': ('Steel', 60),
    'Trigger': ('Steel', 300), 'Safety_L': ('Steel', 350), 'Safety_R': ('Steel', 350),
    'Selector_L': ('Steel', 350), 'Selector_R': ('Steel', 350),
    'Mag_release_L': ('Steel', 250), 'Mag_release_R': ('Steel', 80),
    'Bolt_catch': ('Steel', 500), 'Bolt_catch_boss': ('Steel', 20), 'Side_block': ('Steel', 400),
    'Side_plate_low': ('Steel', 160), 'Side_fins_front': ('Steel', 300), 'Side_fins_rear': ('Steel', 300),
    'Stud_R': ('Steel', 60),
    # прицельные (у глаза)
    'Rear_sight_base': ('Steel', 500), 'Rear_sight_leaf': ('Steel', 900), 'Rear_sight_base_bolt': ('Steel', 60),
    'Rear_sight_base_bolt_head': ('Steel', 80), 'Rear_sight_base_nut': ('Steel', 40),
    'Rear_sight_base_hinge_pin': ('Steel', 24),
    'Front_sight_base': ('Steel', 500), 'Front_sight_leaf': ('Steel', 450), 'Front_sight_drum': ('Steel', 300),
    'Front_sight_drum_wheel': ('Steel', 200), 'Front_sight_post': ('Steel', 120), 'Front_sight_base_bolt': ('Steel', 60),
    'Front_sight_base_bolt_head': ('Steel', 80), 'Front_sight_base_nut': ('Steel', 40),
    'Front_sight_base_hinge_pin': ('Steel', 24),
    # приклад и шарнир
    'Stock_body': ('Stock', 3500), 'Stock_buttplate': ('Stock', 1800), 'Stock_buttplate_core': ('Stock', 300),
    'Stock_latch': ('Stock', 300), 'Stock_hinge_block': ('Stock', 600), 'Stock_hinge_pin': ('Stock', 150),
    'Stock_screw': ('Stock', 80), 'Stock_screw.001': ('Stock', 80), 'Stock_screw.002': ('Stock', 80),
    'Stock_screw.003': ('Stock', 80),
    # магазины: корпус, крышка, подаватель и верхний патрон (в шахте ниже не разглядеть)
    'Magazine13_body': ('Mag13', 1500), 'Magazine13_floorplate': ('Mag13', 150), 'Magazine13_follower': ('Mag13', 100),
    'Magazine13_round_00_case': ('Mag13', 160), 'Magazine13_round_00_bullet': ('Mag13', 120),
    'Magazine30_body': ('Mag30', 1700), 'Magazine30_sleeve': ('Mag30', 900), 'Magazine30_floorplate': ('Mag30', 150),
    'Magazine30_follower': ('Mag30', 100), 'Magazine30_round_00_case': ('Mag30', 160),
    'Magazine30_round_00_bullet': ('Mag30', 120),
}
# головки осей: большие (фланец с канавкой, полая с пружинкой) и малые (с шестигранником) — по бюджету на головку
for i in (0, 1, 6, 7):
    for s in 'LR':
        PARTS[f'Pin_{i:02d}_{s}'] = ('Steel', 220)
for nm in ('Pin_02_L', 'Pin_03_L', 'Pin_03_R', 'Pin_04_L', 'Pin_04_R', 'Pin_05_L', 'Pin_05_R'):
    PARTS[nm] = ('Steel', 120)
log = lambda *a: print('SMG03_LP', *a, flush=True)


def simplify(o, budget: int) -> int:
    """Упрощение по бюджету только схлопыванием рёбер. Плоское растворение (как у ГРАНЬ-15) сливало плоскость
    с вырезами в многоугольник «с дырами» через разрез, и разбиение на треугольники закрывало дыры: у целика окна
    между ушами и кольцом залило сплошной плитой (v1, 05.11)."""
    me = o.data
    strip(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='EAR_CLIP')
    bm.to_mesh(me)
    bm.free()
    select_only(o)
    for _ in range(12):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def mover_node(o):
    """Узел игры по ближайшему моверу над деталью (сама деталь с драйвером-мовером — тоже); иначе — Receiver."""
    while o is not None:
        if o.name in MOVERS:
            return MOVERS[o.name]
        o = o.parent
    return 'Receiver'


def control_poses():
    """Позы видимости: {поза: {узел: мировая дельта}} и начала узлов (м) — из органов управления исходника."""
    ctl = bpy.data.objects[CONTROLS]
    movers = {n: bpy.data.objects[n] for n in MOVERS if n in bpy.data.objects}
    dg = refresh()
    rest = {n: o.evaluated_get(dg).matrix_world.copy() for n, o in movers.items()}
    pivots = {MOVERS[n]: [round(v, 6) for v in m.translation] for n, m in rest.items()}
    poses = {'rest': {}}
    for pose, props in POSE_PROPS.items():
        keep = {k: ctl[k] for k in props}
        for k, v in props.items():
            ctl[k] = v
        dg = refresh()
        moved = {}
        for n, o in movers.items():
            d = o.evaluated_get(dg).matrix_world @ rest[n].inverted()
            if d.translation.length > 1e-5 or abs(d.to_quaternion().angle) > 1e-4:
                moved[MOVERS[n]] = d
        poses[pose] = moved
        log('поза', pose, {k: (round(v.translation.length * 1000, 1), round(math.degrees(v.to_quaternion().angle), 1))
                          for k, v in moved.items()})
        for k, v in keep.items():
            ctl[k] = v
    refresh()
    return poses, pivots


def material(atlas):
    m = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    m.use_nodes = True
    return m


def drop_faces(o, idx):
    if not idx or len(idx) >= len(o.data.polygons):
        return 0
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in idx], context='FACES')
    bm.to_mesh(o.data)
    bm.free()
    return len(idx)


def assembly_classes(game, poses):
    """Классы граней лучами по всей сборке: с магазином на 13 (без 30) и с магазином на 30 (без 13)."""
    node_of = lambda o: o['node']
    with13 = [o for o in game if o['atlas'] != 'Mag30']
    with30 = [o for o in game if o['atlas'] != 'Mag13']
    c13 = kit_uv.visibility(with13, poses, node_of)
    c30 = kit_uv.visibility(with30, poses, node_of)
    out = {o.name: c for o, c in zip(with13, c13)}
    for o, c in zip(with30, c30):
        if o['atlas'] == 'Mag30':
            out[o.name] = c
    return out


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    hp = {o.name: o for o in bpy.data.objects}
    lp_src = {}
    if LP_SOURCE.exists():
        with bpy.data.libraries.load(str(LP_SOURCE)) as (src, dst):
            dst.objects = [n for n in LP_FROM_SOURCE if n in src.objects]
        for n, ob in zip(LP_FROM_SOURCE, dst.objects):
            if ob is not None:
                bpy.context.scene.collection.objects.link(ob)
                ob.name = 'lpsrc_' + n
                lp_src[n] = ob
        log('корпус для игровой сетки — из', LP_SOURCE.name, list(lp_src))
    poses, pivots = control_poses()
    # метки (оси исходника, м): дуло, прицельные, гнездо магазина, хват
    cmin, cmax = world_bbox(hp['Thread_cap'])
    ap_min, ap_max = world_bbox(hp['Rear_sight_leaf'])
    fp_min, fp_max = world_bbox(hp['Front_sight_post'])
    dg = refresh()
    mag_mount = hp['Magazine_mover'].evaluated_get(dg).matrix_world.translation
    marks = {'Muzzle': [round(cmax.x, 5), 0.0, 0.0],
             'SightRear': [round(0.5 * (ap_min.x + ap_max.x), 5), 0.0, 0.076],
             'SightFront': [round(0.5 * (fp_min.x + fp_max.x), 5), 0.0, round(fp_max.z, 5)],
             'MagMount': [round(v, 5) for v in mag_mount]}
    rec = {'source': str(SRC), 'marks_m': marks, 'parts': {}, 'nodes': {}, 'atlases': {}}
    lp_coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(lp_coll)
    pieces = {}
    sources = {}
    totals = {}
    for name, (atlas, budget) in PARTS.items():
        if name not in hp:
            log('нет детали', name)
            continue
        node = mover_node(hp[name])
        if atlas in ('Mag13', 'Mag30'):
            node = 'Magazine'
        o = evaluated_copy(lp_src.get(name, hp[name]), 'lp_' + name, lp_coll)
        n0 = tris(o.data)
        n = simplify(o, min(budget, n0))
        dev = deviation(o, hp[name])
        rec['parts'][name] = {'node': node, 'atlas': atlas, 'hp_tris': n0, 'tris': n, 'dev_mm': dev}
        pieces.setdefault((node, atlas), []).append(o)
        sources[o.name] = [name]
        totals[atlas] = totals.get(atlas, 0) + n
        if dev[0] > 0.5:
            log('отклонение', name, dev)
    rec['tris_by_atlas'] = totals
    rec['in_hands_tris'] = sum(v for k, v in totals.items() if k != 'Mag30')
    log('треугольников в руках (с магазином на 13):', rec['in_hands_tris'], totals)
    for o in list(bpy.data.objects):
        if o.name not in lp_coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    game = []
    for (node, atlas), objs in pieces.items():
        nm = atlas if atlas in ('Mag13', 'Mag30') else (node if node == 'Receiver' and atlas == 'Receiver'
                                                         else f'{node}_{atlas}')
        hp_list = sum((sources.get(o.name, []) for o in objs), [])
        j = join(objs, nm) if len(objs) > 1 else objs[0]
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
        if node in pivots:
            rec['nodes'][nm]['pivot'] = pivots[node]
    # развёртка: острова, лучи видимости по всей сборке, прижатое — прочь, ещё раз лучи, укладка по атласам
    kit_uv.smart_unwrap(game)
    cls = assembly_classes(game, poses)
    dropped = 0
    for o in game:
        dropped += drop_faces(o, [i for i, k in enumerate(cls[o.name]) if k == kit_uv.CONTACT])
    log('прижатых граней удалено:', dropped)
    cls = assembly_classes(game, poses)
    # глаз (оси исходника): от бедра — левее и выше, за коробкой; в прицеливании — за диоптром
    sr = Vector(marks['SightRear'])
    eyes = [kit_uv.Eye((sr.x - 0.16, 0.13, sr.z + 0.06), name='hip'),
            kit_uv.Eye((sr.x - 0.075, 0.0, sr.z), k_max=kit_uv.ADS_K, name='ads')]
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        if not objs:
            continue
        c = [cls[o.name] for o in objs]
        rep = kit_uv.layout(objs, size, classes=c, eyes=eyes if not atlas.startswith('Mag') else [],
                            occluders=game, log=log)
        kit_uv.harden_on_seams(objs)
        rep['report'] = kit_uv.report(objs, size, classes=c)
        rep['verify'] = kit_uv.verify(objs, size, classes=c)
        rec['atlases'][atlas] = {'size': size, 'objects': [o.name for o in objs], **rep}
        if rep['report']['fill'] < kit_uv.FILL_MIN:
            log('UV_FILL_LOW', atlas, rep['report']['fill'])
        log('атлас', atlas, size, rep['report'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True
        rec['nodes'][o.name]['tris'] = tris(o.data)
    rec['in_hands_tris_final'] = sum(v['tris'] for v in rec['nodes'].values() if v['atlas'] != 'Mag30')
    rec['mag30_tris_final'] = sum(v['tris'] for v in rec['nodes'].values() if v['atlas'] == 'Mag30')
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / 'SMG03_Game_LP.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('сохранено', path, 'в руках', rec['in_hands_tris_final'], 'магазин на 30', rec['mag30_tris_final'])


if __name__ == '__main__':
    main()
