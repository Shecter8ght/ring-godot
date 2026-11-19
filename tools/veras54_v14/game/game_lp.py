"""ВЕРАС-54 v14 → игровая сетка от первого лица (кандидат ретопологии, навык weapon-retopology): детали по узлам игры
(подвижные и съёмные — свои узлы по приводам рига VERAS54_Controls), видимость граней лучами в крайних позах рига,
развёртка в атласы, LOD1.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_lp.py [-- --novis | --uv-only]
→ _asset_src/veras54_v14/game/lp/VERAS54_Game_LP.blend + parts.json (не в git).

Источник — принятая форма v14 (`Геометрия v14/ВЕРАС-54_геометрия_v14_04.blend`, четвёртая выдача: рама без выборки; 127 объектов);
файл только открывается, игровые копии делаются из вычисленных деталей, исходные удаляются перед сохранением в свою
папку. -y — приводы рига на выражениях.

Способ — как у «Частокола» (tools/pkp/game_lp.py): high-poly неявными поверхностями (OpenVDB) петель не имеет, игровая
сетка — упрощение по бюджету детали (плоское растворение, затем схлопывание); пружины — гладкие трубки по габариту;
канал ствола вглубь убран. Узлы — пустышки без поворота в оси мовера исходника, иерархия — как у моверов; сетки —
дочерние «<Узел>__<Атлас>». Дульное устройство (обойма, корпус, наконечник) — съёмный узел MuzzleDevice: в игре на его
место встаёт глушитель. Патроны магазина — одна сетка (гильза + пуля) на 30 мест Round_01…30 (Round_01 — верхний),
места — жёстким совмещением сеток патронов исходника. Патрон в патроннике — узел Chamber_Round (гильза) с дочерним
Chamber_Bullet (пуля: в игре прячется — остаётся стреляная гильза).
Видимость — tools/asset_kit/uv.py visibility во всех крайних позах: прижатые во всех позах грани удаляются (с перепроверкой
густой сеткой точек), скрытые ужимаются в развёртке. LOD1 — копии со схлопыванием до ¼, развёртка та же.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/geo'))
from asset_kit import uv as kit_uv  # noqa: E402
import part_rig as R  # noqa: E402

SRC = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Геометрия v14/ВЕРАС-54_геометрия_v14_04.blend')
WORK = ROOT / '_asset_src/veras54_v14/game'
OUT = WORK / 'lp'
MM = 0.001
CONTROLS = 'VERAS54_Controls'
ROOT_NODE = 'Receiver'
# атласы: Body — у глаза (коробка, крышка, целик, затворная группа, органы управления, рукоятка, шарнир, патрон
# в патроннике); Front — цевьё, ствол, газовый узел, дульное устройство, приклад; Mag — магазин и патроны
ATLAS_SIZE = {'Body': 4096, 'Front': 4096, 'Mag': 2048}
MATNAME = {a: f'ВЕРАС-54 v14 • игра • {a}' for a in ATLAS_SIZE}
# мовер исходника → узел игры
MOVERS = {
    'Bolt_Carrier': 'Bolt_Carrier', 'Bolt': 'Bolt', 'Recoil spring • coil': 'Recoil_Spring',
    'Selector_Lever': 'Selector_Lever', 'Trigger': 'Trigger', 'Mag_Catch': 'Mag_Catch',
    'Magazine_Body': 'Magazine', 'Magazine_Follower': 'Magazine_Follower',
    'Chambered_Case': 'Chamber_Round', 'Chambered_Bullet': 'Chamber_Bullet',
    'Dust_Cover': 'Dust_Cover', 'Cover_Button': 'Cover_Button',
    'Stock_Knuckle': 'Stock_Knuckle', 'Stock_Body': 'Stock_Body', 'Stock_Latch': 'Stock_Latch',
    'Hinge_Latch': 'Hinge_Latch', 'Handguard_Latch': 'Handguard_Latch',
    'Rear_Sight_Leaf': 'Rear_Sight_Leaf', 'Rear_Sight_Slider': 'Rear_Sight_Slider',
    'Rear_Sight_Button_L': 'Rear_Sight_Button_L', 'Rear_Sight_Button_R': 'Rear_Sight_Button_R',
    'Rear_Sight_Drum': 'Rear_Sight_Drum', 'Rear_Sight_Knob': 'Rear_Sight_Knob',
    'Muzzle_Collar': 'MuzzleDevice',
}
# детали без общей ветки в исходнике, но в одном узле игры
GROUP = {'Muzzle_Body': 'Muzzle_Collar', 'Muzzle_Tip': 'Muzzle_Collar'}
# начало узла не в начале мовера: дульное устройство — на оси у заднего торца обоймы (там встаёт глушитель)
PIVOT_OVERRIDE = {'MuzzleDevice': (0.5874, 0.0, 0.0)}
# начала узлов в середине габарита своей детали (у исходника начало у них в 0, 0, 0)
PIVOT_BBOX = {'Chamber_Bullet': 'Chambered_Bullet', 'Magazine_Follower': 'Magazine_Follower'}
# Источник упрощения без мелкого рельефа (заклёпки, клейма, насечки, сварной шов, неглубокие выборки, «вафли» магазина):
# те же модули формы с VERAS_PLAIN=1 (tools/veras54_v14/geo, сборка go.sh с VERAS_TAG=plain) → v14_k1_plain.blend;
# сетки вынимаются в npz режимом -- --dump-plain. Отклонение и запекание — по полной форме v14_04.
PLAIN_BLEND = ROOT / '_asset_src/veras54_v14_geo/work/v14_k1_plain.blend'
PLAIN_DIR = WORK / 'plain'
PLAIN_PARTS = ('Receiver', 'Bolt_Carrier', 'Charging_Handle', 'Front_Block', 'Handguard_Latch', 'Magazine_Body',
               'Pistol_Grip', 'Rear_Sight_Button_L', 'Rear_Sight_Button_R', 'Rear_Sight_Knob', 'Rear_Sight_Leaf',
               'Selector_Lever', 'Trigger_Guard')
# кольцо диоптра: сначала вся деталь до PRE треугольников, затем окрестность отверстия (r < R от линии прицеливания)
# замораживается группой вершин, остальное — до бюджета (кромка отверстия остаётся кругом)
RING_PROTECT = {'Rear_Sight_Drum': dict(pre=4000, r=0.0013, axis=(0.0, 0.0594), x=(0.044, 0.057))}
# деталь исходника → (бюджет треугольников, атлас). Всё оружие с магазином — до 40 тыс. (без 30 патронов)
PARTS = {
    # ствольная коробка, крышка, планка
    'Receiver': (5500, 'Body'), 'Front_Block': (800, 'Body'), 'Dust_Cover': (2600, 'Body'),
    'Cover_Rear_Block': (800, 'Body'), 'Cover_Button': (160, 'Body'), 'Top_Rail': (1500, 'Body'),
    'Barrel_Breech': (200, 'Body'),
    # целик (у глаза в прицеливании — плотнее)
    'Rear_Sight_Base': (900, 'Body'), 'Rear_Sight_Leaf': (700, 'Body'), 'Rear_Sight_Slider': (320, 'Body'),
    'Rear_Sight_Button_L': (70, 'Body'), 'Rear_Sight_Button_R': (70, 'Body'), 'Rear_Sight_Drum': (1200, 'Body'),
    'Rear_Sight_Knob': (800, 'Body'), 'Rear_Sight_Yoke': (320, 'Body'), 'Rear_Sight_Axle': (60, 'Body'),
    # затворная группа (в окне крышки)
    'Bolt_Carrier': (1800, 'Body'), 'Charging_Handle': (650, 'Body'), 'Bolt': (600, 'Body'),
    'Bolt_Extractor': (90, 'Body'), 'Bolt_Extractor_Spring': (16, 'Body'), 'Bolt carrier • gas piston': (220, 'Body'),
    'Recoil_Guide_Rod': (260, 'Body'), 'Recoil spring • coil': (16, 'Body'), 'Ejector': (90, 'Body'),
    # органы управления, рукоятка
    'Selector_Lever': (1300, 'Body'), 'Trigger': (260, 'Body'), 'Trigger_Guard': (900, 'Body'),
    'Mag_Catch': (420, 'Body'), 'Mag_Catch_Axle': (60, 'Body'),
    'Pistol_Grip': (1900, 'Body'), 'Grip_Cap': (400, 'Body'), 'Grip_Button_L': (60, 'Body'), 'Grip_Button_R': (60, 'Body'),
    # шарнир приклада
    'Hinge_Base': (320, 'Body'), 'Hinge_Latch': (200, 'Body'), 'Hinge_Pin': (60, 'Body'), 'Hinge_Spring': (16, 'Body'),
    # патрон в патроннике
    'Chambered_Case': (150, 'Body'), 'Chambered_Bullet': (60, 'Body'),
    # цевьё
    'Handguard_Upper': (1900, 'Front'), 'Handguard_Lower': (1650, 'Front'), 'Handguard_Latch': (140, 'Front'),
    'Side_Rail_L': (450, 'Front'), 'Side_Rail_R': (450, 'Front'), 'Side_Rail_Screws': (220, 'Front'),
    # ствол, газовый узел, мушка
    'Barrel': (360, 'Front'), 'Barrel_Collar': (360, 'Front'), 'Gas_Block': (1050, 'Front'),
    'Gas_Block_Pins': (160, 'Front'), 'Gas_Tube': (800, 'Front'), 'Gas_Tube_Pins': (80, 'Front'),
    'Front_Sight_Post': (220, 'Front'),
    # дульное устройство (дальнее — экономнее)
    'Muzzle_Collar': (700, 'Front'), 'Muzzle_Body': (700, 'Front'), 'Muzzle_Tip': (800, 'Front'),
    # приклад
    'Stock_Knuckle': (600, 'Front'), 'Stock_Tube': (500, 'Front'), 'Stock_Body': (1500, 'Front'),
    'Butt_Pad': (450, 'Front'), 'Stock_Latch': (380, 'Front'), 'Stock_Screws': (220, 'Front'), 'Sling_Stud': (220, 'Front'),
    # магазин
    'Magazine_Body': (2800, 'Mag'), 'Magazine_Floorplate': (300, 'Mag'), 'Magazine_Follower': (260, 'Mag'),
    'Magazine_Spring': (120, 'Mag'),
}
# патрон магазина: одна сетка на 30 мест (гильза + пуля), бюджет частей
ROUND_SRC = ('Magazine • loaded case {}', 'Magazine • loaded projectile {}')
ROUND_BUDGET = (80, 40)
ROUND_N = 30
PART_IDS = {n: i for i, n in enumerate(PARTS)}
ORGANIC = {'Pistol_Grip', 'Stock_Body', 'Butt_Pad', 'Handguard_Upper', 'Handguard_Lower', 'Magazine_Body'}
# пружины — гладкие трубки по габариту (число граней), витки — в карте нормалей
TUBES = {'Recoil spring • coil': 8, 'Bolt_Extractor_Spring': 6, 'Hinge_Spring': 8}
# канал ствола вглубь не виден: убирается до упрощения (радиус, мм), у концов остаётся BORE_KEEP_MM
BORE = {'Barrel': 4.0}
BORE_KEEP_MM = 25.0
UV_ANGLE = {'Barrel': 80, 'Gas_Tube': 75, 'Bolt carrier • gas piston': 80, 'Recoil_Guide_Rod': 80, 'Stock_Tube': 75,
            'Pistol_Grip': 70, 'Stock_Body': 66, 'Butt_Pad': 66, 'Handguard_Upper': 66, 'Handguard_Lower': 66,
            'Magazine_Body': 66, 'Muzzle_Collar': 66, 'Muzzle_Body': 70, 'Muzzle_Tip': 66, 'Barrel_Collar': 70,
            'Hinge_Pin': 80, 'Mag_Catch_Axle': 80, 'Rear_Sight_Axle': 80, 'Rear_Sight_Knob': 70, 'Rear_Sight_Drum': 66,
            'Chambered_Case': 80, 'Chambered_Bullet': 80, 'Round': 80, 'Barrel_Breech': 75, 'Grip_Cap': 66}
# позы видимости — из ползунков рига (part_rig.SLIDERS); база — умолчания рига с патроном в патроннике
BASE = {'live_round': 1.0}
FIRE = {'selector': R.SEL_AB}
POSES = {
    'charged': {**FIRE, 'carrier': 1.0},
    'open': {**FIRE, 'carrier': 1.0, 'mag_catch': 1.0, 'mag': 1.0},
    'folded': {'stock_fold': 1.0, 'hinge_latch': 1.0, 'stock_len': 1.0, 'stock_lever': 1.0},
    'misc': {'selector': 1.0, 'trigger': 1.0, 'sight_range': 1.0, 'windage': 1.0, 'sight_buttons': 1.0,
             'hg_latch': 1.0, 'cover_button': 1.0},
    'misc2': {'windage': 0.0, 'mag_catch': 1.0},
}
# глаз (оси исходника, м): в прицеливании — на линии прицеливания за диоптром; от бедра — левее (+Y) и выше:
# автомат у правого бедра, камера — над ним и левее
EYE_ADS = (-0.20, 0.0, 0.0594)
EYE_HIP = (-0.15, 0.11, 0.13)
LOD1_K = 0.25
KEEP_NODES = {'Magazine_Follower'}
log = lambda *a: print('VERAS14_LP', *a, flush=True)  # noqa: E731


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def refresh():
    sc = bpy.context.scene
    for o in bpy.data.objects:
        o.update_tag()
    sc.frame_set(sc.frame_current)
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def mover_of(o):
    """Ближайший мовер над деталью (сама деталь — тоже) или None."""
    while o is not None:
        if o.name in MOVERS:
            return o.name
        if o.name in GROUP:
            return GROUP[o.name]
        o = o.parent
    return None


def node_parent(mover):
    o = bpy.data.objects[mover].parent
    m = mover_of(o)
    return MOVERS[m] if m else ROOT_NODE


def rest_props():
    return {**{k: float(v) for k, _h, v in R.SLIDERS}, **BASE}


def set_props(ctl, props):
    for k, v in props.items():
        ctl[k] = float(v)


def control_poses(movers):
    """{поза: {узел: мировая дельта}} из ползунков исходника; узлы без движения не пишутся."""
    ctl = bpy.data.objects[CONTROLS]
    rest = rest_props()
    set_props(ctl, rest)
    dg = refresh()
    base = {n: bpy.data.objects[n].evaluated_get(dg).matrix_world.copy() for n in movers}
    poses = {'rest': {}}
    for pose, props in POSES.items():
        set_props(ctl, {**rest, **props})
        dg = refresh()
        moved = {}
        for n in movers:
            d = bpy.data.objects[n].evaluated_get(dg).matrix_world @ base[n].inverted()
            if d.translation.length > 1e-5 or abs(d.to_quaternion().angle) > 1e-4 or \
                    abs(d.to_scale().length - math.sqrt(3)) > 1e-4:
                moved[MOVERS[n]] = d
        poses[pose] = moved
        log('поза', pose, sorted(moved))
    set_props(ctl, rest)
    refresh()
    return poses


def strip(me) -> None:
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])
    me.materials.clear()


def clean(me) -> None:
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.validate(clean_customdata=False)


def collapse(o, budget: int, organic: bool, group: str = '') -> None:
    for _ in range(14):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(budget / n, 1 / 8) if organic else max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        if group:
            d.vertex_group = group
            d.vertex_group_factor = 1.0
        bpy.ops.object.modifier_apply(modifier=d.name)


def simplify(o, budget: int, organic: bool, ring: dict | None = None) -> int:
    me = o.data
    strip(me)
    clean(me)
    select_only(o)
    if tris(me) > budget and not organic:
        d = o.modifiers.new('planar', 'DECIMATE')
        d.decimate_type = 'DISSOLVE'
        d.angle_limit = math.radians(0.6)
        bpy.ops.object.modifier_apply(modifier=d.name)
    if ring:
        # вершины с весом 0 схлопывание не трогает (проверено: кромка отверстия сохраняется целиком)
        collapse(o, ring['pre'], organic)
        co = np.array([v.co for v in o.data.vertices])
        r = np.hypot(co[:, 1] - ring['axis'][0], co[:, 2] - ring['axis'][1])
        z = (r < ring['r']) & (co[:, 0] > ring['x'][0]) & (co[:, 0] < ring['x'][1])
        vg = o.vertex_groups.new(name='protect')
        vg.add([int(i) for i in np.flatnonzero(~z)], 1.0, 'REPLACE')
        vg.add([int(i) for i in np.flatnonzero(z)], 0.0, 'REPLACE')
        collapse(o, budget, organic, 'protect')
        o.vertex_groups.clear()
    else:
        collapse(o, budget, organic)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    clean(o.data)
    return tris(o.data)


def tube(o, sides: int) -> int:
    """Сетка объекта → гладкая трубка по габариту в собственных осях объекта (ось — самая длинная сторона)."""
    me = o.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    ext = hi - lo
    k = int(np.argmax(ext))
    a, b = [i for i in range(3) if i != k]
    c = 0.5 * (lo + hi)
    r = 0.25 * (ext[a] + ext[b])
    verts = []
    for end in (lo[k], hi[k]):
        for i in range(sides):
            t = 2 * math.pi * (i + 0.5) / sides
            v = [0.0, 0.0, 0.0]
            v[k] = float(end)
            v[a] = float(c[a] + r * math.cos(t))
            v[b] = float(c[b] + r * math.sin(t))
            verts.append(v)
    faces = [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    faces += [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    strip(me)
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    fs = [bm.faces.new([vs[i] for i in f]) for f in faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uvl = bm.loops.layers.uv.new('GameUV')
    arc = 2 * math.pi * r / sides
    length = float(hi[k] - lo[k])
    for fi, f in enumerate(fs):
        for lp in f.loops:
            j = vs.index(lp.vert)
            if fi < sides:
                i = j % sides
                if fi == sides - 1 and i == 0:
                    i = sides
                lp[uvl].uv = (arc * i, length if j >= sides else 0.0)
            else:
                ox = 0.0 if fi == sides else 4 * r
                lp[uvl].uv = (arc * sides + 2 * r + ox + (lp.vert.co[a] - c[a]), r + (lp.vert.co[b] - c[b]))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.validate()
    return tris(me)


def cut_bore(o, r_mm: float) -> int:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    xs = [v.co.x for v in bm.verts]
    x0, x1 = min(xs) + BORE_KEEP_MM * MM, max(xs) - BORE_KEEP_MM * MM
    r = r_mm * MM
    drop = [f for f in bm.faces if x0 < f.calc_center_median().x < x1
            and math.hypot(f.calc_center_median().y, f.calc_center_median().z) < r]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(o.data)
    bm.free()
    return len(drop)


def unwrap_piece(o, name: str) -> None:
    if 'GameUV' in o.data.uv_layers:
        return
    kit_uv.smart_unwrap([o], angle=math.radians(UV_ANGLE.get(name, 60)))


def mesh_bvh(me, m):
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3) @ np.array(m.to_3x3(), np.float32).T + np.array(m.translation, np.float32)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    return BVHTree.FromPolygons(co.tolist(), tri.reshape(-1, 3).tolist(), all_triangles=True)


def hp_bvh(hs):
    """BVH по вычисленным деталям исходника (одной или нескольким)."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in hs:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        m = eo.matrix_world
        base = len(verts)
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3) @ np.array(m.to_3x3(), np.float32).T + np.array(m.translation, np.float32)
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', tri)
        verts += co.tolist()
        polys += (tri.reshape(-1, 3) + base).tolist()
        eo.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=True)


def sample_points(me, mw):
    """Вершины, центры граней и середины рёбер граней (широкая грань поперёк выемки вершин в ней не имеет)."""
    pts = [mw @ v.co for v in me.vertices]
    out = list(pts)
    for p in me.polygons:
        vs = [pts[i] for i in p.vertices]
        out.append(sum(vs, Vector()) / len(vs))
        for k in range(len(vs)):
            out.append((vs[k] + vs[(k + 1) % len(vs)]) * 0.5)
    return out


def deviation(lp, hs) -> tuple:
    """Отклонение low → high (мм): наибольшее, среднее, 99-й перцентиль; и обратное high → low (наибольшее, 99 %)
    по случайной выборке вершин исходника — ловит потерянные выступы и окна."""
    bvh = hp_bvh(hs)
    ds = np.array([d for d in (bvh.find_nearest(p)[3] for p in sample_points(lp.data, lp.matrix_world)) if d is not None])
    lb = mesh_bvh(lp.data, lp.matrix_world)
    dg = bpy.context.evaluated_depsgraph_get()
    back = []
    rng = np.random.default_rng(1)
    for o in hs:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        idx = rng.choice(n, min(n, 4000), replace=False)
        m = eo.matrix_world
        for i in idx:
            d = lb.find_nearest(m @ Vector(co[i]))[3]
            if d is not None:
                back.append(d)
        eo.to_mesh_clear()
    back = np.array(back) if back else np.zeros(1)
    if not len(ds):
        ds = np.zeros(1)
    return (round(float(ds.max()) * 1000, 2), round(float(ds.mean()) * 1000, 3), round(float(np.percentile(ds, 99)) * 1000, 2),
            round(float(back.max()) * 1000, 2), round(float(np.percentile(back, 99)) * 1000, 2))


def evaluated_copy(o, name, coll):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def join(objs, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
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


def material(atlas):
    m = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    m.use_nodes = True
    return m


def set_material(o, atlas):
    o.data.materials.clear()
    o.data.materials.append(material(atlas))
    for p in o.data.polygons:
        p.material_index = 0


def driver_specs(o):
    out = []
    if o.animation_data:
        for f in o.animation_data.drivers:
            vs = [v.targets[0].data_path.strip('[]"') for v in f.driver.variables]
            out.append([f.data_path, f.array_index, f.driver.expression, vs])
    return out


def face_attr(o, name, values):
    me = o.data
    at = me.attributes.get(name) or me.attributes.new(name, 'INT', 'FACE')
    at.data.foreach_set('value', np.asarray(values, np.int32))


def face_attr_get(o, name):
    me = o.data
    v = np.zeros(len(me.polygons), np.int32)
    me.attributes[name].data.foreach_get('value', v)
    return v


def world_verts(o):
    """Вершины вычисленной детали в мировых осях (n, 3)."""
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('co', co)
    m = np.array(eo.matrix_world)
    eo.to_mesh_clear()
    co = co.reshape(-1, 3)
    return co @ m[:3, :3].T + m[:3, 3]


def kabsch(a, b):
    """Жёсткое движение (4×4), переводящее точки a в точки b (соответствие по номеру), и остаточная ошибка, м."""
    ca, cb = a.mean(0), b.mean(0)
    H = (a - ca).T @ (b - cb)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    Rm = Vt.T @ D @ U.T
    t = cb - Rm @ ca
    M = np.eye(4)
    M[:3, :3], M[:3, 3] = Rm, t
    err = float(np.abs((a @ Rm.T + t) - b).max())
    return Matrix([list(r) for r in M]), err


def recheck_contact(objs, poses, cls, node_of) -> dict:
    """Кандидаты на удаление (прижатые во всех позах) — ещё раз густой сеткой точек грани: длинный треугольник
    упрощённой сетки бывает прижат серединой и виден краем. Хоть один луч ушёл из сборки хоть в одной позе — грань остаётся."""
    dirs = [Vector(d) for d in kit_uv._FIB[::4]]
    bary = [(1 / 3, 1 / 3, 1 / 3)] + [tuple(0.9 if j == i else 0.05 for j in range(3)) for i in range(3)] + \
        [tuple(0.05 if j == i else 0.475 for j in range(3)) for i in range(3)] + \
        [tuple(0.6 if j == i else 0.2 for j in range(3)) for i in range(3)]
    cand = {o.data.name: set(np.flatnonzero(cls[o.data.name] == kit_uv.CONTACT).tolist()) for o in objs}
    eye4 = Matrix.Identity(4)
    for pose in poses.values():
        posed = [(o, pose.get(node_of(o), eye4)) for o in objs]
        verts, polys = [], []
        for o, mx in posed:
            m = mx @ o.matrix_world
            base = len(verts)
            verts += [m @ v.co for v in o.data.vertices]
            polys += [[base + i for i in pl.vertices] for pl in o.data.polygons]
        bvh = BVHTree.FromPolygons(verts, polys)
        for o, mx in posed:
            c = cand[o.data.name]
            if not c:
                continue
            m = mx @ o.matrix_world
            nm = m.to_3x3().inverted().transposed()
            me = o.data
            for fi in list(c):
                pl = me.polygons[fi]
                n = (nm @ pl.normal).normalized()
                vs = [m @ me.vertices[i].co for i in pl.vertices[:3]]
                ds = [d for d in dirs if d.dot(n) > 0.05]
                seen = False
                for w in bary:
                    st = vs[0] * w[0] + vs[1] * w[1] + vs[2] * w[2] + n * 1e-5
                    for d in ds:
                        if bvh.ray_cast(st, d, 2.0)[0] is None:
                            seen = True
                            break
                    if seen:
                        break
                if seen:
                    c.discard(fi)
    return cand


def merge_classes(objs, cls_list, rep_of):
    out = {}
    for o, c in zip(objs, cls_list):
        r = rep_of(o)
        out[r] = c.copy() if r not in out else np.minimum(out[r], c)
    return out


SPARSE_SOLIDITY = 0.45
SPARSE_MIN_M2 = 1.5e-4


def split_sparse(objs, uv: str = 'GameUV') -> int:
    """«Рамки» и сильно вогнутые острова режутся пополам поперёк длинной стороны, пока остров не станет плотным
    (как у «Частокола»)."""
    cuts = 0
    for o in objs:
        m = kit_uv._Mesh(o, uv)
        piece = np.zeros(m.npoly, np.int64)
        nid = 1
        work = [i.polys for i in kit_uv.islands_of([m])]
        pc = np.stack([np.bincount(m.poly_of_loop, m.uv[:, k], m.npoly) for k in range(2)], 1) / \
            np.maximum(m.lt, 1)[:, None]
        tri_a2 = np.abs(m.tri_a2s)
        while work:
            polys = work.pop()
            if len(polys) < 2:
                continue
            a3 = float(m.poly_a3[polys].sum())
            loops = kit_uv._ranges(m.ls[polys], m.lt[polys])
            pts = m.uv[loops]
            tr = kit_uv._ranges(m.tri_start[polys], m.tri_start[polys + 1] - m.tri_start[polys])
            a2 = float(tri_a2[tr].sum())
            if a2 <= 1e-16:
                continue
            ang = kit_uv._min_rect_angle(pts)
            c, sn = math.cos(ang), math.sin(ang)
            q = pts @ np.array([[c, sn], [-sn, c]])
            ext = q.max(0) - q.min(0)
            rect = float(ext[0] * ext[1])
            if len(polys) < 8 or a3 < SPARSE_MIN_M2 or rect <= 1e-14 or a2 / rect >= SPARSE_SOLIDITY:
                continue
            axis = 0 if ext[0] >= ext[1] else 1
            d = (pc[polys] @ np.array([[c, sn], [-sn, c]]))[:, axis]
            w = m.poly_a3[polys]
            o_ = np.argsort(d)
            cut = d[o_][np.searchsorted(np.cumsum(w[o_]), 0.5 * w.sum())]
            A, B = polys[d <= cut], polys[d > cut]
            if not len(A) or not len(B):
                continue
            piece[B] = nid
            nid += 1
            cuts += 1
            work += [A, B]
        if nid > 1:
            uvn = m.uv.copy()
            uvn[:, 0] += 3.0 * piece[m.poly_of_loop]
            m.write_uv(uvn)
    log('разрезано «рамок»', cuts)
    return cuts


def weighted_normals(o) -> None:
    """Свои нормали по площади граней (жёсткие рёбра — на швах развёртки): плоские грани упрощённой сетки — плоские,
    без размазанного затенения по длинным треугольникам; с ними же запекаются карты нормалей."""
    others = [x for x in bpy.data.objects if x is not o and x.data is o.data]
    if others:
        o.data = o.data.copy()          # общая сетка патронов: модификатор применяется к одной копии, остальным — её сетка
    select_only(o)
    m = o.modifiers.new('wn', 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.weight = 50
    m.keep_sharp = True
    m.thresh = 0.01
    bpy.ops.object.modifier_apply(modifier=m.name)
    if others:
        old = others[0].data
        name = old.name
        for x in others:
            x.data = o.data
        bpy.data.meshes.remove(old)
        o.data.name = name


def lod1_per_part(c) -> None:
    """LOD1: каждая деталь (атрибут part_id) схлопывается до ¼ своих треугольников отдельно — общее упрощение сборки
    съедало тонкое (скоба, рукоятка) ради крупного; развёртка переносится схлопыванием (те же атласы)."""
    me = c.data
    pid = face_attr_get(c, 'part_id') if 'part_id' in me.attributes else np.zeros(len(me.polygons), np.int32)
    pieces = []
    for v in np.unique(pid):
        o = bpy.data.objects.new(f'{c.name}_p{v}', me.copy())
        bpy.context.scene.collection.objects.link(o)
        o.matrix_world = Matrix.Identity(4)   # куски — в осях сетки; мировая c ещё не посчитана и меняется по ходу
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.flatnonzero(pid != v)], context='FACES')
        bm.to_mesh(o.data)
        bm.free()
        n0 = tris(o.data)
        budget = max(12, int(n0 * LOD1_K))
        select_only(o)
        for _ in range(6):
            n = tris(o.data)
            if n <= budget * 1.05 or n <= 12:
                break
            d = o.modifiers.new('lod', 'DECIMATE')
            d.ratio = max(budget / n, 0.05)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
        pieces.append(o)
    old = c.data
    bpy.ops.object.select_all(action='DESELECT')
    for o in pieces:
        o.select_set(True)
    bpy.context.view_layer.objects.active = pieces[0]
    if len(pieces) > 1:
        bpy.ops.object.join()
    j = bpy.context.view_layer.objects.active
    c.data = j.data
    c.data.name = old.name
    bpy.data.objects.remove(j, do_unlink=True)
    bpy.data.meshes.remove(old)


def plain_copy(name, new, coll):
    """Сетка детали без мелкого рельефа (мировые оси) из PLAIN_DIR/<деталь>.npz."""
    d = np.load(PLAIN_DIR / f'{name}.npz')
    me = bpy.data.meshes.new(new)
    me.from_pydata(d['v'].tolist(), [], d['f'].tolist())
    me.validate()
    ob = bpy.data.objects.new(new, me)
    coll.objects.link(ob)
    return ob


def dump_plain():
    """Вынуть вычисленные сетки гладких деталей (мировые оси, позы по умолчанию) из PLAIN_BLEND в npz."""
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(PLAIN_BLEND))
    dg = refresh()
    for name in PLAIN_PARTS:
        o = bpy.data.objects[name]
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64)
        me.vertices.foreach_get('co', co)
        m = np.array(eo.matrix_world)
        co = co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get('vertices', tri)
        np.savez_compressed(PLAIN_DIR / f'{name}.npz', v=co, f=tri.reshape(-1, 3))
        eo.to_mesh_clear()
        log('гладкая', name, n, len(tri) // 3)


def uv_only():
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(OUT / 'VERAS54_Game_LP_stage.blend'))
    rec = json.loads((OUT / 'parts_stage.json').read_text(encoding='utf-8'))
    for c in [c for c in bpy.data.collections if c.name.startswith('GAME_LOD1')]:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
    seen, game, copies = set(), [], []
    for o in sorted(objs, key=lambda x: x.name):
        (copies if o.data.name in seen else game).append(o)
        seen.add(o.data.name)
    cls = {o.data.name: face_attr_get(o, 'vis_cls') for o in game}
    refresh()
    finish(rec, game, copies, cls, t0)


def main():
    novis = '--novis' in sys.argv
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    hp = {o.name: o for o in bpy.data.objects}
    ctl = hp[CONTROLS]
    set_props(ctl, rest_props())
    refresh()
    movers = [n for n in MOVERS if n in hp]
    poses = control_poses(movers)
    dg = refresh()
    pivots = {MOVERS[n]: hp[n].evaluated_get(dg).matrix_world.translation.copy() for n in movers}
    for k, v in PIVOT_OVERRIDE.items():
        pivots[k] = Vector(v)
    for k, src in PIVOT_BBOX.items():
        b0, b1 = world_bbox(hp[src])
        pivots[k] = (b0 + b1) * 0.5
    pivots[ROOT_NODE] = Vector((0.0, 0.0, 0.0))
    parents = {MOVERS[n]: node_parent(n) for n in movers}
    drivers = {MOVERS[n]: driver_specs(hp[n]) for n in movers}

    # метки (оси исходника, м)
    mz0, mz1 = world_bbox(hp['Muzzle_Tip'])
    fs0, fs1 = world_bbox(hp['Front_Sight_Post'])
    g0, g1 = world_bbox(hp['Pistol_Grip'])
    b0, b1 = world_bbox(hp['Butt_Pad'])
    marks = {'Muzzle': [round(mz1.x, 5), 0.0, 0.0], 'MuzzleSeat': list(PIVOT_OVERRIDE['MuzzleDevice']),
             'SightRear': [0.051, 0.0, 0.0594], 'SightFront': [round(0.5 * (fs0.x + fs1.x), 5), 0.0, round(fs1.z, 5)],
             'Grip': [round(0.5 * (g0.x + g1.x), 5), 0.0, round(0.5 * (g0.z + g1.z), 5)],
             'Butt': [round(b0.x, 5), 0.0, round(0.5 * (b0.z + b1.z), 5)],
             'Chamber': [0.2214, 0.0, 0.0]}
    log('метки', marks)

    coll = bpy.data.collections.new('GAME')
    bpy.context.scene.collection.children.link(coll)
    nodes = {}

    def node_empty(name):
        if name in nodes:
            return nodes[name]
        par = None if name == ROOT_NODE else node_empty(parents[name])
        e = bpy.data.objects.new('node:' + name, None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 0.015
        coll.objects.link(e)
        e.parent = par
        e.location = pivots[name] - (pivots[parents[name]] if par else Vector())
        nodes[name] = e
        return e
    for n in [ROOT_NODE] + [MOVERS[m] for m in movers]:
        node_empty(n)
    refresh()

    rec = {'source': str(SRC), 'axes_source': '+X дуло, +Y влево стрелка, +Z верх, −Y правая сторона; м', 'marks': marks,
           'base_props': rest_props(), 'nodes': {}, 'parts': {}, 'atlases': {}, 'rounds': [],
           'poses': {k: sorted(v) for k, v in poses.items()}, 'pose_props': POSES, 'drivers': drivers}
    for n in nodes:
        rec['nodes'][n] = {'parent': None if n == ROOT_NODE else parents[n],
                           'pivot': [round(c, 6) for c in pivots[n]], 'meshes': []}

    pieces = {}
    total = 0
    for name, (budget, atlas) in PARTS.items():
        if name not in hp:
            log('нет детали', name)
            continue
        h = hp[name]
        m = mover_of(h)
        node = MOVERS[m] if m else ROOT_NODE
        if name in PLAIN_PARTS:
            o = plain_copy(name, 'lp_' + name, coll)
        else:
            o = evaluated_copy(h, 'lp_' + name, coll)
        n0 = tris(o.data)
        if name in TUBES:
            n = tube(o, TUBES[name])
        else:
            if name in BORE:
                log('канал', name, 'граней прочь', cut_bore(o, BORE[name]))
            n = simplify(o, min(budget, n0), organic=name in ORGANIC, ring=RING_PROTECT.get(name))
        dev = deviation(o, [h])
        unwrap_piece(o, name)
        rec['parts'][name] = {'node': node, 'atlas': atlas, 'hp_tris': n0, 'budget': budget, 'tris': n,
                              'plain_source': name in PLAIN_PARTS,
                              'dev_mm': dict(zip(('max', 'mean', 'p99', 'back_max', 'back_p99'), dev)),
                              'uv': 'cyl' if name in TUBES else UV_ANGLE.get(name, 60)}
        log(f'{name}: {n0} → {n}, отклонение наиб. {dev[0]} ср. {dev[1]} p99 {dev[2]}; обратно наиб. {dev[3]} p99 {dev[4]} мм, '
            f'узел {node}, атлас {atlas}')
        o['hp'] = [name]
        face_attr(o, 'part_id', [PART_IDS[name]] * len(o.data.polygons))
        pieces.setdefault((node, atlas), []).append(o)
        total += n
    game = []
    for (node, atlas), objs in pieces.items():
        hp_list = sum((list(o['hp']) for o in objs), [])
        j = join(objs, f'{node}__{atlas}')
        set_material(j, atlas)
        j.data.transform(Matrix.Translation(-pivots[node]))
        j.parent = nodes[node]
        j.matrix_parent_inverse = Matrix.Identity(4)
        j.location = (0, 0, 0)
        j['atlas'], j['node'], j['hp'] = atlas, node, hp_list
        game.append(j)
        rec['nodes'][node]['meshes'].append(j.name)
    rec['tris_weapon_simplified'] = total

    # патрон магазина: гильза и пуля верхнего патрона (места — по 30 гильзам исходника)
    refresh()
    mag_node = nodes['Magazine']
    case1, proj1 = hp[ROUND_SRC[0].format(1)], hp[ROUND_SRC[1].format(1)]
    parts_r = []
    for h, b in zip((case1, proj1), ROUND_BUDGET):
        o = evaluated_copy(h, 'lp_round_' + h.name, coll)
        n0 = tris(o.data)
        n = simplify(o, min(b, n0), organic=False)
        dev = deviation(o, [h])
        log(f'патрон {h.name}: {n0} → {n}, отклонение {dev}')
        rec['parts'][h.name] = {'node': 'Magazine', 'atlas': 'Mag', 'hp_tris': n0, 'tris': n,
                                'dev_mm': dict(zip(('max', 'mean', 'p99', 'back_max', 'back_p99'), dev)), 'copies': ROUND_N}
        unwrap_piece(o, 'Round')
        face_attr(o, 'part_id', [len(PART_IDS) + len(parts_r)] * len(o.data.polygons))
        parts_r.append(o)
    rnd = join(parts_r, 'Round_01')
    rnd.data.name = 'Round'
    set_material(rnd, 'Mag')
    # сетка патрона — в осях гильзы верхнего патрона
    dg = refresh()
    M1 = case1.evaluated_get(dg).matrix_world.copy()
    rnd.data.transform(M1.inverted())
    rnd.parent = mag_node
    rnd.matrix_parent_inverse = Matrix.Identity(4)
    rnd.matrix_basis = Matrix.Translation(-pivots['Magazine']) @ M1
    rnd['atlas'], rnd['node'], rnd['hp'] = 'Mag', 'Magazine', [case1.name, proj1.name]
    game.append(rnd)
    rec['nodes']['Magazine']['meshes'].append(rnd.name)
    a1 = np.concatenate([world_verts(case1), world_verts(proj1)])
    round_copies = []
    worst = 0.0
    for i in range(1, ROUND_N + 1):
        hc, hpj = hp[ROUND_SRC[0].format(i)], hp[ROUND_SRC[1].format(i)]
        T, err = kabsch(a1, np.concatenate([world_verts(hc), world_verts(hpj)]))
        worst = max(worst, err)
        if i == 1:
            o = rnd
        else:
            o = bpy.data.objects.new(f'Round_{i:02d}', rnd.data)
            coll.objects.link(o)
            o['atlas'], o['node'], o['hp'] = 'Mag', 'Magazine', [hc.name, hpj.name]
            o.parent = mag_node
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = Matrix.Translation(-pivots['Magazine']) @ T @ M1
            round_copies.append(o)
        rec['rounds'].append({'object': o.name, 'hp': [hc.name, hpj.name],
                              'matrix_local': [[round(c, 7) for c in r] for r in (Matrix.Translation(-pivots['Magazine']) @ T @ M1)],
                              'fit_err_mm': round(err * 1000, 4)})
    log('места патронов: наибольшая ошибка совмещения', round(worst * 1000, 4), 'мм')
    rec['tris_round'] = tris(rnd.data)
    log('треугольников: оружие', total, 'патрон', rec['tris_round'], f'{time.time() - t0:.0f} с')

    for o in list(bpy.data.objects):
        if o.name not in coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    for n, e in nodes.items():
        e.name = n
    refresh()
    allobj = game + round_copies
    node_of = lambda o: o['node']  # noqa: E731
    rep_of = lambda o: o.data.name  # noqa: E731

    if novis:
        cls = {o.data.name: np.zeros(len(o.data.polygons), np.int32) for o in game}
    else:
        tv = time.time()
        cls_a = merge_classes(allobj, kit_uv.visibility(allobj, poses, node_of), rep_of)
        log('видимость', f'{time.time() - tv:.0f} с')
        tv = time.time()
        n0 = sum(int((c == kit_uv.CONTACT).sum()) for c in cls_a.values())
        cand = recheck_contact(game, poses, cls_a, node_of)
        log('прижатые: кандидатов', n0, 'после перепроверки', sum(len(c) for c in cand.values()), f'{time.time() - tv:.0f} с')
        rec['removed_contact'] = {}
        for o in game:
            # подаватель и патроны не режутся: в игре патронов бывает меньше 30 — верх подавателя и стороны патронов,
            # прижатые к соседям, тогда видны
            if o['node'] in KEEP_NODES or o.data.name == 'Round':
                cand[o.data.name] = set()
                c = cls_a[o.data.name]
                c[c == kit_uv.CONTACT] = kit_uv.VISIBLE
            drop = np.array(sorted(cand[o.data.name]), np.int64)
            keep_cls = np.delete(cls_a[o.data.name], drop) if len(drop) else cls_a[o.data.name]
            if len(drop) and len(drop) < len(o.data.polygons):
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES_ONLY')
                loose = [v for v in bm.verts if not v.link_faces]
                if loose:
                    bmesh.ops.delete(bm, geom=loose, context='VERTS')
                bm.to_mesh(o.data)
                bm.free()
                rec['removed_contact'][o.name] = int(len(drop))
                log('удалены прижатые', o.name, len(drop))
            cls_a[o.data.name] = keep_cls
        cls = {k: np.where(c == kit_uv.CONTACT, kit_uv.HIDDEN, c) for k, c in cls_a.items()}
    for o in game:
        face_attr(o, 'vis_cls', cls[o.data.name])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'VERAS54_Game_LP_stage.blend'), compress=True)
    (OUT / 'parts_stage.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                          newline='\n')
    finish(rec, game, round_copies, cls, t0)


def finish(rec, game, round_copies, cls, t0):
    """Разрезание «рамок», укладка атласов, LOD1, сохранение."""
    rec['visibility'] = {}
    for o in game:
        c = cls[o.data.name]
        a = np.array([p.area for p in o.data.polygons]) * 1e4
        rec['visibility'][o.name] = {nm: round(float(a[c == k].sum()), 1) for nm, k in
                                     (('visible_cm2', 0), ('roomy_cm2', 1), ('hidden_cm2', 2))}
    eyes = [kit_uv.Eye(EYE_HIP, name='hip'), kit_uv.Eye(EYE_ADS, k_max=kit_uv.ADS_K, name='ads')]
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        if not objs:
            continue
        split_sparse(objs)
        classes = [cls[o.data.name] for o in objs]
        rep = kit_uv.layout(objs, size, classes=classes, eyes=eyes, log=log, hidden_pool=True, precision=0.004)
        kit_uv.harden_on_seams(objs)
        rep['report'] = kit_uv.report(objs, size, classes=classes)
        rep['verify'] = kit_uv.verify(objs, size, classes=classes)
        rec['atlases'][atlas] = {'size': size, 'objects': [o.name for o in objs], **rep}
        if rep['fill'] < kit_uv.FILL_MIN:
            log('UV_FILL_LOW', atlas, rep['fill'])
        log('атлас', atlas, size, 'заполнение', rep['fill'], 'пикс/мм', rep['px_mm'], rep['report'], rep['verify'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True

    lod_coll = bpy.data.collections.new('GAME_LOD1')
    bpy.context.scene.collection.children.link(lod_coll)
    lod_mesh = {}
    lod_total = lod_round = 0
    for o in game:
        me = o.data.copy()
        me.name = o.data.name + '_LOD1'
        c = bpy.data.objects.new(o.name + '_LOD1', me)
        lod_coll.objects.link(c)
        c.parent = o.parent
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy()
        for k in ('atlas', 'node', 'hp'):
            c[k] = o[k]
        lod1_per_part(c)
        kit_uv.harden_on_seams([c])
        for p in c.data.polygons:
            p.use_smooth = True
        weighted_normals(c)
        lod_mesh[o.data.name] = c.data
        rec['nodes'][o['node']].setdefault('mesh_tris_lod1', {})[c.name] = tris(c.data)
        if o.data.name == 'Round':
            lod_round = tris(c.data)
        else:
            lod_total += tris(c.data)
    for o in round_copies:
        c = bpy.data.objects.new(o.name + '_LOD1', lod_mesh[o.data.name])
        lod_coll.objects.link(c)
        c.parent = o.parent
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy()
        for k in ('atlas', 'node', 'hp'):
            c[k] = o[k]
    lod_coll.hide_render = True
    bpy.context.view_layer.layer_collection.children['GAME_LOD1'].hide_viewport = True

    for o in game:
        weighted_normals(o)
    weapon = 0
    for o in game:
        n = tris(o.data)
        rec['nodes'][o['node']].setdefault('mesh_tris', {})[o.name] = n
        if o.data.name == 'Round':
            rec['tris_round_final'] = n
        else:
            weapon += n
    rec['tris_weapon_lod0'] = weapon
    rec['tris_rounds_lod0'] = rec['tris_round_final'] * ROUND_N
    rec['tris_weapon_lod1'] = lod_total
    rec['tris_rounds_lod1'] = lod_round * ROUND_N
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / 'VERAS54_Game_LP.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('сохранено', path, 'оружие LOD0', weapon, 'патроны', rec['tris_rounds_lod0'], 'LOD1', lod_total,
        rec['tris_rounds_lod1'], f'{time.time() - t0:.0f} с')


if __name__ == '__main__':
    if '--dump-plain' in sys.argv:
        dump_plain()
    elif '--uv-only' in sys.argv:
        uv_only()
    else:
        main()
