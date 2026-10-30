"""AR-15 «ГРАНЬ-15» → игровая сетка: детали по узлам игры (подвижные и съёмные — свои узлы по моверам исходника),
атласы, развёртка по видимости; метки (дуло, прицельные, гнездо магазина, хват) и планки Picatinny с пазами.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/ar15/game_lp.py
→ _asset_src/ar15/game/lp/AR15_Game_LP.blend + lp/parts.json (не в git).

Источник — принятая high-poly с износом: `AR-15_износ_этап2_v1.blend` в папке модели (геометрия v08, этап 1 «песок» v7,
этап 2 v1; карты — Текстуры_этап2_износ_v1). Исходник не меняется: файл открывается, игровые копии делаются из
вычисленных деталей, исходные удаляются перед сохранением в свою папку. -y — драйверы механики (AR15_Controls) на
выражениях Python: без них позы видимости не считаются.
Оси исходника: дуло +X, верх +Z, левая сторона стрелка +Y, метры; перевод в оси игры — на экспорте (game_export.py).
Как у ВСС-М (tools/vss_m_v8/game_lp.py): упрощение по бюджету детали (сначала плоское растворение, затем схлопывание),
развёртка — tools/asset_kit/uv.py (лучи видимости в покое и крайних позах механики, плотность у глаза, укладка).
Бюджет — «в руках до 40 тыс.» на ствол с магазином (владелец 2026-10-19); мелкий рельеф (насечка рукояти, пазы M-LOK
кромками, надписи) — в нормалях. Скрытое внутри (пружины, буфер, курок, разобщитель, ударник, гайки планок, перегородки
глушителя) — в игру не идёт; глушитель — отдельный обвес, позже.
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

SRC = Path('E:/Models Blender/WEAPONS/AR-15 — модель/AR-15_износ_этап2_v1.blend')
WORK = ROOT / '_asset_src/ar15/game'
OUT = WORK / 'lp'
OUT.mkdir(parents=True, exist_ok=True)
# атласы игры: коробки и трубка (песок, крупные плоскости) и цевьё с прицелами — 4K; сталь, полимер, магазин — 2K
ATLAS_SIZE = {'Receiver': 4096, 'Handguard': 4096, 'Steel': 2048, 'Polymer': 2048, 'Mag': 2048}
MATNAME = {a: f'AR15 • {a}' for a in ATLAS_SIZE}
# мовер исходника → узел игры (навык godot-asset-preparation, «Подвижные и съёмные детали»): узел — по ближайшему
# моверу над деталью. Верхний ресивер (Upper_group_pivot — откидывается при разборке) — свой узел; нижний — Lower.
MOVERS = {
    'Upper_group_pivot': 'Upper', 'Bolt_carrier_mover': 'BoltCarrier', 'Bolt_mover': 'Bolt',
    'Charging_handle_mover': 'ChargingHandle', 'CH_latch_L_pivot': 'ChLatchL', 'CH_latch_R_pivot': 'ChLatchR',
    'Dust_cover_hinge': 'DustCover', 'Forward_assist_mover': 'ForwardAssist', 'Trigger_pivot': 'Trigger',
    'Selector_pivot': 'Selector', 'Mag_catch_mover': 'MagCatch', 'Bolt_catch_pivot': 'BoltCatch',
    'Pivot_pin_mover': 'PivotPin', 'Takedown_pin_mover': 'TakedownPin', 'Stock_mover': 'Stock',
    'Magazine_mover': 'Magazine', 'Rear_sight_leaf': 'RearSightLeaf', 'Front_sight_leaf': 'FrontSightLeaf',
    'Rear_sight_aperture': 'RearAperture', 'Mag_release_L': 'MagReleaseL', 'Stock_latch': 'StockLatch',
}
CONTROLS = 'AR15_Controls'
# позы видимости — из органов управления исходника: всё нажато и отведено (рама назад, шторка открыта, магазин вынут,
# приклад выдвинут) и прицельные сложены. Значения покоя возвращаются из исходника (селектор 0,5, курок 1 и т. п.)
POSE_PROPS = {
    'moved': {'charging_handle': 1.0, 'ch_latch': 1.0, 'dust_cover': 1.0, 'trigger': 1.0, 'selector': 1.0,
              'mag_catch': 1.0, 'bolt_catch': 1.0, 'forward_assist': 1.0, 'stock': 1.0, 'stock_latch': 1.0,
              'mag_out': 1.0},
    'folded': {'rear_sight': 0.0, 'front_sight': 0.0, 'rear_aperture': 1.0},
}

# деталь исходника → (атлас, бюджет треугольников); узел — по моверу. Нет в списке — в игру не идёт.
PARTS = {
    # коробки, трубка приклада, органы управления (песок и чёрная сталь)
    'Upper_receiver': ('Receiver', 4200), 'Upper_rail': ('Receiver', 1500), 'Lower_receiver': ('Receiver', 4800),
    'Buffer_tube': ('Receiver', 900), 'Castle_nut': ('Receiver', 360), 'End_plate': ('Receiver', 420),
    'Forward_assist': ('Receiver', 420), 'Dust_cover': ('Receiver', 360), 'Dust_cover_rod': ('Receiver', 40),
    'Bolt_catch': ('Receiver', 220), 'Mag_catch': ('Receiver', 100), 'Mag_button': ('Receiver', 220),
    'Mag_release_L': ('Receiver', 220), 'Mag_release_bracket': ('Receiver', 60), 'Mag_release_pin': ('Receiver', 24),
    'Mag_release_screw0': ('Receiver', 20), 'Mag_release_screw1': ('Receiver', 20),
    'Selector': ('Receiver', 80), 'Selector_lever_L': ('Receiver', 300), 'Selector_lever_R': ('Receiver', 260),
    'Pivot_pin': ('Receiver', 110), 'Takedown_pin': ('Receiver', 110), 'Guard_pin': ('Receiver', 30),
    'Guard_pin_front': ('Receiver', 30), 'Hammer_pin': ('Receiver', 30), 'Trigger_pin': ('Receiver', 30),
    'Auto_sear_pin': ('Receiver', 30), 'Trigger': ('Receiver', 300),
    'Charging_handle': ('Receiver', 700), 'CH_latch_L': ('Receiver', 360), 'CH_latch_R': ('Receiver', 360),
    'CH_latch_L_pin': ('Receiver', 16), 'CH_latch_R_pin': ('Receiver', 16),
    # цевьё, планки и прицельные (у глаза — плотнее)
    'Handguard': ('Handguard', 5600), 'Handguard_rail': ('Handguard', 1700), 'Bottom_rail_long': ('Handguard', 900),
    'Bottom_rail_long_screw0': ('Handguard', 60), 'Bottom_rail_long_screw1': ('Handguard', 60),
    'Side_rail': ('Handguard', 320), 'Side_rail_R': ('Handguard', 320),
    'Side_rail_screw0': ('Handguard', 60), 'Side_rail_screw1': ('Handguard', 60),
    'Side_rail_R_screw0': ('Handguard', 60), 'Side_rail_R_screw1': ('Handguard', 60),
    'Handguard_screw0': ('Handguard', 80), 'Handguard_screw1': ('Handguard', 80),
    'Handguard_QD_L': ('Handguard', 100), 'Handguard_QD_R': ('Handguard', 100),
    'Front_sight_base': ('Handguard', 600), 'Front_sight_base_bolt': ('Handguard', 120),
    'Front_sight_base_button': ('Handguard', 80), 'Front_sight_base_hinge_pin': ('Handguard', 24),
    'Front_sight_leaf': ('Handguard', 520), 'Front_sight_drum': ('Handguard', 260), 'Front_sight_post': ('Handguard', 120),
    'Rear_sight_base': ('Handguard', 760), 'Rear_sight_base_bolt': ('Handguard', 120),
    'Rear_sight_base_button': ('Handguard', 80), 'Rear_sight_base_hinge_pin': ('Handguard', 24),
    'Rear_sight_leaf': ('Handguard', 600), 'Rear_sight_aperture': ('Handguard', 360),
    'Rear_sight_aperture_pin': ('Handguard', 60), 'Rear_sight_drum': ('Handguard', 280),
    # сталь: ствол, газоотвод, ДТК, затворная группа (видна в окне)
    'Barrel': ('Steel', 700), 'Barrel_extension': ('Steel', 200), 'Barrel_nut': ('Steel', 320),
    'Gas_block': ('Steel', 300), 'Gas_tube': ('Steel', 60), 'Gas_tube_pin': ('Steel', 16),
    'Muzzle_brake': ('Steel', 1300), 'Muzzle_jam_nut': ('Steel', 120), 'Muzzle_lock_collar': ('Steel', 480),
    'Bolt_carrier': ('Steel', 900), 'Gas_key': ('Steel', 160), 'Gas_key_screw0': ('Steel', 40),
    'Gas_key_screw1': ('Steel', 40), 'Firing_pin_retainer': ('Steel', 24), 'Bolt': ('Steel', 480),
    'Cam_pin': ('Steel', 80), 'Extractor': ('Steel', 80), 'Ejector': ('Steel', 16),
    # полимер и резина: рукоять, приклад с затыльником и фиксатором
    'Pistol_grip': ('Polymer', 1800), 'Stock_body': ('Polymer', 2400), 'Stock_buttpad': ('Polymer', 700),
    'Stock_latch': ('Polymer', 180), 'Stock_latch_axis': ('Polymer', 24), 'Stock_lock_pin': ('Polymer', 30),
    'Stock_QD_cup_front_L': ('Polymer', 150), 'Stock_QD_cup_front_R': ('Polymer', 150),
    'Stock_QD_cup_rear_L': ('Polymer', 150), 'Stock_QD_cup_rear_R': ('Polymer', 150),
    # магазин: корпус, крышка, защёлка крышки, подаватель и два верхних патрона (ниже их в окнах не разглядеть)
    'Magazine_body': ('Mag', 2000), 'Magazine_floorplate': ('Mag', 220), 'Magazine_floorplate_lock': ('Mag', 60),
    'Magazine_follower': ('Mag', 160), 'Magazine_round_00': ('Mag', 260), 'Magazine_round_01': ('Mag', 260),
}
ORGANIC = {'Pistol_grip', 'Stock_body', 'Stock_buttpad', 'Magazine_body'}
# сначала вокселями (размер вокселя, м) и сглаживанием: насечка рукояти — рельеф сеткой исходника (74 тыс.), схлопывание
# по нему выбрасывало вершины на 10 мм; сетка вокселей 0,6 мм → 1800 треугольников отходит от исходника на 0,3 мм,
# насечка остаётся в карте нормалей
REMESH = {'Pistol_grip': 0.0006}
# планки Picatinny (MIL-STD-1913): детали исходника → имя планки игры и сторона, куда смотрят зубья (в осях исходника)
RAILS = {'Upper_rail': ('RailTop', (0, 0, 1)), 'Handguard_rail': ('RailTop', (0, 0, 1)),
         'Bottom_rail_long': ('RailBottom', (0, 0, -1)), 'Side_rail': ('RailLeft', (0, 1, 0)),
         'Side_rail_R': ('RailRight', (0, -1, 0))}
log = lambda *a: print('AR15_LP', *a, flush=True)


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def mover_node(o):
    """Узел игры по ближайшему моверу над деталью (сама деталь с драйвером-мовером — тоже); иначе — Lower."""
    while o is not None:
        if o.name in MOVERS:
            return MOVERS[o.name]
        o = o.parent
    return 'Lower'


def refresh():
    sc = bpy.context.scene
    for o in bpy.data.objects:
        o.update_tag()
    sc.frame_set(sc.frame_current)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


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


def action_from_controls():
    """Ход механики для игры (м, градусы) — из драйверов исходника, как action у ВСС-М: рама и рукоятка назад, отставание
    затвора, шторка, магазин, спуск, переводчик."""
    ctl = bpy.data.objects[CONTROLS]
    probe = {'charging_handle': ('Charging_handle_mover', 'Bolt_carrier_mover', 'Bolt_mover', 'Dust_cover_hinge'),
             'mag_out': ('Magazine_mover',), 'trigger': ('Trigger_pivot',), 'selector': ('Selector_pivot',),
             'bolt_catch': ('Bolt_catch_pivot',), 'stock': ('Stock_mover',)}
    dg = refresh()
    rest = {n: bpy.data.objects[n].evaluated_get(dg).matrix_world.copy() for ns in probe.values() for n in ns}
    out = {}
    for prop, names in probe.items():
        keep = ctl[prop]
        ctl[prop] = 1.0 if prop != 'selector' else 0.0
        dg = refresh()
        for n in names:
            d = bpy.data.objects[n].evaluated_get(dg).matrix_world @ rest[n].inverted()
            out[f'{prop}:{MOVERS[n]}'] = {'move_m': [round(v, 5) for v in d.translation],
                                          'rot_deg': round(math.degrees(d.to_quaternion().angle), 2)}
        ctl[prop] = keep
    refresh()
    return out


def evaluated_copy(o, name, coll):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
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


def simplify(o, budget: int, organic: bool, voxel: float = 0.0) -> int:
    me = o.data
    strip(me)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    select_only(o)
    if voxel > 0.0:
        r = o.modifiers.new('voxel', 'REMESH')
        r.mode = 'VOXEL'
        r.voxel_size = voxel
        r.adaptivity = 0.0
        bpy.ops.object.modifier_apply(modifier=r.name)
        sm = o.modifiers.new('smooth', 'SMOOTH')
        sm.factor = 0.5
        sm.iterations = 2
        bpy.ops.object.modifier_apply(modifier=sm.name)
    if tris(me) > budget and not organic:
        d = o.modifiers.new('planar', 'DECIMATE')
        d.decimate_type = 'DISSOLVE'
        d.angle_limit = math.radians(0.6)
        bpy.ops.object.modifier_apply(modifier=d.name)
    for _ in range(10):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(budget / n, 1 / 8) if organic else max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def deviation(lp, hp_obj) -> tuple:
    """Отклонение игровой сетки от исходника, мм: наибольшее и среднее по вершинам."""
    dg = bpy.context.evaluated_depsgraph_get()
    eo = hp_obj.evaluated_get(dg)
    me = eo.to_mesh()
    m = eo.matrix_world
    verts = [m @ v.co for v in me.vertices]
    polys = [list(p.vertices) for p in me.polygons]
    eo.to_mesh_clear()
    if not polys:
        return 0.0, 0.0
    bvh = BVHTree.FromPolygons(verts, polys)
    ds = [bvh.find_nearest(lp.matrix_world @ v.co)[3] for v in lp.data.vertices]
    ds = [x for x in ds if x is not None]
    return (round(max(ds) * 1000, 2), round(sum(ds) / len(ds) * 1000, 3)) if ds else (0.0, 0.0)


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    j.name = name
    j.data.name = name
    return j


def world_bbox(o):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    pts = [eo.matrix_world @ Vector(c) for c in eo.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def rail_slots(o, up) -> dict:
    """Планка Picatinny по геометрии исходника: ось вдоль X, высота вершин зубьев, середины поперечных пазов (м, оси
    исходника). Вершины зубьев — грани, смотрящие в сторону зубьев на самом верху; паз — промежуток между соседними
    вершинами шириной 3–8 мм (MIL-STD-1913: шаг 10,01 мм, паз 5,23 мм). Вершины граней верха лежат только по краям
    планки, поэтому пазы ищутся по граням, а не по точкам средней линии."""
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    M = eo.matrix_world
    R = M.to_3x3()
    u = Vector(up)
    co = [M @ v.co for v in me.vertices]
    top = max(c.dot(u) for c in co)
    spans = []
    for p in me.polygons:
        n = (R @ p.normal).normalized()
        if n.dot(u) < 0.95:
            continue
        xs = [co[i].x for i in p.vertices]
        if min(co[i].dot(u) for i in p.vertices) > top - 0.0005:
            spans.append((min(xs), max(xs)))
    side = [c.z for c in co] if abs(u.y) > 0.5 else [c.y for c in co]
    eo.to_mesh_clear()
    spans.sort()
    teeth = []
    for a, b in spans:                                    # слить грани одной вершины зуба
        if teeth and a <= teeth[-1][1] + 1e-5:
            teeth[-1][1] = max(teeth[-1][1], b)
        else:
            teeth.append([a, b])
    slots = [round(0.5 * (teeth[i][1] + teeth[i + 1][0]), 5) for i in range(len(teeth) - 1)
             if 0.003 < teeth[i + 1][0] - teeth[i][1] < 0.008]
    xs_all = [c.x for c in co]
    return {'x0': round(min(xs_all), 5), 'x1': round(max(xs_all), 5), 'top_m': round(top, 5),
            'side_m': round(0.5 * (min(side) + max(side)), 5), 'up': list(up), 'slots_x': slots,
            'teeth': len(teeth)}


def material(atlas):
    m = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    m.use_nodes = True
    return m


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    hp = {o.name: o for o in bpy.data.objects}
    poses, pivots = control_poses()
    action = action_from_controls()
    # метки (оси исходника, м): дуло, прицельные, гнездо магазина, хват (середина рукояти — начало осей игры)
    bmin, bmax = world_bbox(hp['Muzzle_brake'])
    ap_min, ap_max = world_bbox(hp['Rear_sight_aperture'])
    fp_min, fp_max = world_bbox(hp['Front_sight_post'])
    g_min, g_max = world_bbox(hp['Pistol_grip'])
    dg = refresh()
    mag_mount = hp['Magazine_mover'].evaluated_get(dg).matrix_world.translation
    grip = Vector((0.5 * (g_min.x + g_max.x), 0.0, 0.5 * (g_min.z + g_max.z) + 0.01))
    marks = {'Muzzle': [round(bmax.x, 5), 0.0, 0.0],
             'SightRear': [round(0.5 * (ap_min.x + ap_max.x), 5), 0.0, round(0.5 * (ap_min.z + ap_max.z), 5)],
             'SightFront': [round(0.5 * (fp_min.x + fp_max.x), 5), 0.0, round(fp_max.z, 5)],
             'MagMount': [round(v, 5) for v in mag_mount]}
    rails = {}
    for part, (rname, up) in RAILS.items():
        if part in hp:
            r = rail_slots(hp[part], up)
            if rname in rails:                              # верхняя: планка ресивера и планка цевья — одна линия
                q = rails[rname]
                q['segments'].append(r)
                q['slots_x'] = sorted(q['slots_x'] + r['slots_x'])
            else:
                rails[rname] = {'segments': [r], 'slots_x': list(r['slots_x']), 'up': list(up)}
    for k, r in rails.items():
        log('планка', k, 'пазов', len(r['slots_x']), 'от', r['slots_x'][:1], 'до', r['slots_x'][-1:])
    rec = {'source': str(SRC), 'grip_m': list(grip), 'marks_m': marks, 'rails_m': rails, 'action': action,
           'parts': {}, 'nodes': {}, 'atlases': {}}
    lp_coll = bpy.data.collections.new('LP')
    bpy.context.scene.collection.children.link(lp_coll)
    pieces = {}                                   # (узел, атлас) → [игровые куски]
    sources = {}
    total = 0
    for name, (atlas, budget) in PARTS.items():
        if name not in hp:
            log('нет детали', name)
            continue
        node = mover_node(hp[name])
        o = evaluated_copy(hp[name], 'lp_' + name, lp_coll)
        n0 = tris(o.data)
        n = simplify(o, min(budget, n0), organic=name in ORGANIC, voxel=REMESH.get(name, 0.0))
        dev = deviation(o, hp[name])
        rec['parts'][name] = {'node': node, 'atlas': atlas, 'hp_tris': n0, 'tris': n, 'dev_mm': dev}
        pieces.setdefault((node, atlas), []).append(o)
        sources[o.name] = [name]
        total += n
    rec['rifle_tris'] = total
    log('треугольников в руках (с магазином):', total)
    # исходник больше не нужен: удаляется до развёртки (лучи видимости — только по игровым деталям)
    for o in list(bpy.data.objects):
        if o.name not in lp_coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    game = []
    for (node, atlas), objs in pieces.items():
        nm = 'Magazine' if node == 'Magazine' else f'{node}_{atlas}'
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
    # точки глаза (оси исходника): от бедра (левее и выше, за коробкой) и в прицеливании (за целиком)
    sr = Vector(marks['SightRear'])
    eyes = [kit_uv.Eye((sr.x - 0.16, 0.13, sr.z + 0.06), name='hip'),
            kit_uv.Eye((sr.x - 0.075, 0.0, sr.z), k_max=kit_uv.ADS_K, name='ads')]
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        if not objs:
            continue
        kit_uv.smart_unwrap(objs)
        cls = kit_uv.visibility(objs, poses, lambda o: o['node'])
        for o, c in zip(objs, cls):
            drop = [i for i, k in enumerate(c) if k == kit_uv.CONTACT]
            if drop and len(drop) < len(o.data.polygons):
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES')
                bm.to_mesh(o.data)
                bm.free()
        cls = kit_uv.visibility(objs, poses, lambda o: o['node'])
        rep = kit_uv.layout(objs, size, classes=cls, eyes=eyes if atlas != 'Mag' else [], log=log)
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
    rec['rifle_tris_final'] = sum(v['tris'] for v in rec['nodes'].values())
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / 'AR15_Game_LP.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('сохранено', path, 'в руках', rec['rifle_tris_final'])


main()
