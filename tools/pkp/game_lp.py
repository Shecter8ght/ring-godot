"""«Частокол» (ПКП, слот wpn_lmg_01) → игровая сетка: детали по узлам игры (подвижные и съёмные — свои узлы по
приводам рига PKP_Controls), видимость в крайних позах рига, развёртка в атласы 4K, LOD1.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/pkp/game_lp.py [-- --novis]
→ _asset_src/pkp/game/lp/PKP_Game_LP.blend + parts.json (не в git).

Источник — принятая форма v04 с развёрткой под Painter (`Частокол_развёртка_v02.blend`, tex_sets.UV_BLEND): та же
геометрия, по которой написаны карты этапов 1 и 2, и тот же риг. Исходник не меняется: файл открывается, игровые копии
делаются из вычисленных деталей, исходные удаляются перед сохранением в свою папку. -y — приводы рига на выражениях.

Как у АСТЕН-919 и ГРАНЬ-15 (tools/asten919/game_lp.py, tools/ar15/game_lp.py): high-poly неявными поверхностями
(OpenVDB) петель не имеет — игровая сетка получается упрощением по бюджету детали (сначала плоское растворение, затем
схлопывание); рукоятка с насечкой — сначала вокселями и сглаживанием, насечка остаётся в карте нормалей.
Узлы игры — пустышки без поворота в оси привода исходника (ось детали-мовера), иерархия — как у моверов исходника
(затвор под рамой, ноги сошек под вилкой, крышка коробки под коробкой). Сетки — дочерние объекты узла «<Узел>__<Атлас>».
Съёмное без привода (ствол с кожухом и сошками, коробка с лентой, рычаг замка ствола) — тоже свои узлы.
Лента — одна сетка звена, спирали и патрона на семь мест (Link_NN, Spiral_NN, Round_NN под узлом Belt) и наконечник.
Видимость граней — лучами во всех крайних позах рига (tools/asset_kit/uv.py visibility): прижатые удаляются, скрытые
ужимаются в развёртке; нутро коробки для ленты видно только с открытой крышкой — для плотности оно «просторное
скрытое», но не удаляется. LOD1 — копии сеток со схлопыванием до ¼ (те же UV), объекты «…_LOD1» в коллекции GAME_LOD1.
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
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))
from asset_kit import uv as kit_uv  # noqa: E402
import part_rig as R  # noqa: E402
import tex_sets as T  # noqa: E402

SRC = T.UV_BLEND
WORK = ROOT / '_asset_src/pkp/game'
OUT = WORK / 'lp'
ATLAS_SIZE = {'Body': 4096, 'Front': 4096, 'Box': 4096}
MATNAME = {a: f'Частокол • игра • {a}' for a in ATLAS_SIZE}
# набор текстур исходника → атлас игры: «Body» — то, что у глаза (коробка, крышка, затворная группа, прицел, рукоятка);
# «Front» — ствол, кожух, сошки, приклад; «Box» — коробка для ленты и лента
SET_ATLAS = {'receiver': 'Body', 'cover': 'Body', 'bolt': 'Body', 'sight': 'Body', 'grip': 'Body',
             'barrel': 'Front', 'shroud': 'Front', 'bipod': 'Front', 'stock': 'Front',
             'box100': 'Box', 'belt': 'Box'}
# мовер исходника (деталь с приводом рига или съёмная) → узел игры
MOVERS = {
    'Top_Cover': 'Cover', 'Cover_Latch': 'CoverLatch', 'Feed_Flap': 'FeedFlap', 'Exit_Flap': 'ExitFlap',
    'Feed_Tray': 'Tray', 'Feed_Lever': 'FeedLever', 'Charging_Handle': 'ChargingHandle', 'Bolt_Carrier': 'BoltCarrier',
    'Bolt': 'Bolt', 'Recoil_Spring': 'RecoilSpring', 'Port_Cover': 'PortCover', 'Trigger': 'Trigger',
    'Safety_Lever': 'Safety', 'Shoulder_Rest': 'ShoulderRest', 'Bipod_Yoke': 'Bipod', 'Bipod_Leg_L': 'BipodLegL',
    'Bipod_Leg_R': 'BipodLegR', 'Bipod_Spring': 'BipodSpring', 'Rear_Sight_Leaf': 'SightLeaf',
    'Rear_Sight_Slider': 'SightSlider', 'Rear_Sight_Notch': 'SightNotch', 'Rear_Sight_Knob': 'SightKnob',
    'Box100_Lid': 'BoxLid', 'Box100_Flap': 'BoxFlap',
    # съёмное без привода: ствол быстросменный (с кожухом, газовым узлом, мушкой и сошками), коробка с лентой,
    # рычаг замка ствола
    'Barrel': 'Barrel', 'Box100_Body': 'Box', 'Barrel_Lock': 'BarrelLock',
}
ROOT_NODE = 'Receiver'
CONTROLS = 'PKP_Controls'
# деталь исходника → бюджет треугольников (игровая сетка в руках — до ~40 тыс. вместе с коробкой и лентой). Нет в
# списке — в игру не идёт (коробка на 200, отрезок ленты, патрон и гильза отдельно, кронштейны — свои обвесы позже)
PARTS = {
    # ствольная коробка
    'Receiver': 5200, 'Breech_Insert': 900, 'Barrel_Lock': 300, 'Box_Bracket': 350, 'Side_Rail': 260,
    'Sling_Bar': 260, 'Trigger_Housing': 800, 'Trigger': 200, 'Safety_Lever': 260, 'Cover_Catch': 80,
    'Port_Cover': 260, 'Cover_Hinge_Pin': 64,
    # крышка, лоток и подача
    'Top_Cover': 3200, 'Feed_Flap': 300, 'Exit_Flap': 180, 'Cover_Base_F': 140, 'Cover_Base_R': 140,
    'Cover_Latch': 220, 'Cover_Latch_Pin': 32, 'Feed_Tray': 1400, 'Cover_Guide': 160, 'Cover_Lever': 160,
    'Cover_Lever_Bracket': 120, 'Cover_Lever_Pin': 24, 'Cover_Lever_Spring': 40, 'Feed_Lever': 360,
    'Feed_Lever_Guard': 80, 'Feed_Lever_Pin': 24, 'Feed_Pawl_Arm': 140, 'Feed_Pawl_Shaft': 24,
    'Retainer_Pawl': 160, 'Retainer_Shaft': 24, 'Retainer_Spring': 40, 'Cartridge_Stop': 120,
    # ствол, газовый узел, мушка
    'Barrel': 1300, 'Flash_Hider': 600, 'Gas_Block': 380, 'Gas_Housing': 520, 'Gas_Tube': 280,
    'Front_Sight_Base': 700, 'Front_Sight_Post': 140,
    # кожух и ручка
    'Shroud': 1500, 'Shroud_Scoop': 280, 'Carry_Handle': 1400,
    # прицел (виден в прицеливании — плотнее)
    'Rear_Sight_Base': 420, 'Rear_Sight_Leaf': 480, 'Rear_Sight_Slider': 180, 'Rear_Sight_Notch': 100,
    'Rear_Sight_Knob': 160, 'Rear_Sight_Button': 60, 'Rear_Sight_Pin': 40, 'Rear_Sight_Spring': 80,
    # сошки
    'Bipod_Yoke': 420, 'Bipod_Leg_L': 700, 'Bipod_Leg_R': 700, 'Bipod_Foot_L': 240, 'Bipod_Foot_R': 240,
    'Bipod_Hinge_Pin_L': 64, 'Bipod_Hinge_Pin_R': 64, 'Bipod_Pin': 96, 'Bipod_Spring': 44,
    # затворная группа (видна в окне выброса и с открытой крышкой)
    'Bolt_Carrier': 900, 'Bolt': 420, 'Bolt_Extractor': 60, 'Gas_Piston': 260, 'Charging_Handle': 560,
    'Cartridge_Gripper': 260, 'Ejector': 80, 'Recoil_Guide': 80, 'Recoil_Spring': 36, 'Gripper_Pin': 24,
    'Piston_Pin': 24,
    # приклад и рукоятка
    'Stock': 1300, 'Buttplate': 320, 'Butt_Screw_L': 48, 'Butt_Screw_R': 48, 'Rest_Hinge': 200,
    'Shoulder_Rest': 300, 'Pistol_Grip': 800,
    # коробка на 100
    'Box100_Body': 1700, 'Box100_Lid': 560, 'Box100_Flap': 220, 'Box100_Latch': 260, 'Box100_Mount': 380,
    'Box100_Mount_Tooth': 60, 'Box100_Turnbutton': 80, 'Box100_Flap_Pin': 32, 'Box100_Hinge_Pin': 32,
    'Box100_Latch_Pin': 32, 'Box100_Latch_Spring': 40, 'Box100_Handle': 300,
}
# лента: одна сетка на все места (исходник — копии Belt_*_src); семь мест от лотка до коробки
BELT = {'Link': ('Belt_Link_00', 300), 'Spiral': ('Belt_Spiral_00', 28), 'Round': ('Belt_Round_00', 190)}
BELT_TIP = ('Belt_Tip', 200)
BELT_N = 7
ORGANIC = {'Pistol_Grip', 'Box100_Handle', 'Stock', 'Buttplate', 'Shoulder_Rest'}
# сначала вокселями (м) и сглаживанием: насечка рукоятки — рельеф сеткой исходника, по нему схлопывание тратит бюджет
REMESH = {'Pistol_Grip': 0.0006}
# пружины: схлопывание по виткам рвёт их (отклонение до 4 мм) — гладкая трубка по габариту пружины (число граней),
# витки — в карте нормалей
TUBES = {'Recoil_Spring': 8, 'Bipod_Spring': 12, 'Retainer_Spring': 6, 'Box100_Latch_Spring': 6,
         'Cover_Lever_Spring': 6, 'Belt_Spiral_00': 8}
# канал ствола вглубь не виден (из дула — на 25 мм, с казны — на 25 мм): убирается до упрощения, бюджет — наружной
# поверхности. (ось X, радиус в мм — канал 3,81 и запас)
BORE = {'Barrel': 4.6}
BORE_KEEP_MM = 25.0
# развёртка — по детали до объединения: Smart UV с изломом (градусы); по умолчанию 60 (kit_uv.SHARP). Круглые и плавные
# детали на 60° режутся на десятки узких полос, у каждой свой отступ 12 px, — у них излом крупнее (как ANGLES наборов
# текстур). Трубки пружин — цилиндрической развёрткой, одним прямоугольником.
UV_ANGLE = {'Barrel': 80, 'Shroud': 75, 'Gas_Tube': 80, 'Gas_Piston': 80, 'Flash_Hider': 70, 'Carry_Handle': 66,
            'Gas_Housing': 66, 'Bipod_Leg_L': 70, 'Bipod_Leg_R': 70, 'Pistol_Grip': 75, 'Stock': 70, 'Buttplate': 70,
            'Shoulder_Rest': 66, 'Box100_Handle': 75, 'Belt_Round_00': 80, 'Belt_Link_00': 66, 'Recoil_Guide': 80,
            'Cover_Hinge_Pin': 80, 'Bipod_Hinge_Pin_L': 80, 'Bipod_Hinge_Pin_R': 80, 'Bipod_Pin': 80,
            'Rear_Sight_Pin': 80, 'Rear_Sight_Knob': 70, 'Box100_Flap_Pin': 80, 'Box100_Hinge_Pin': 80,
            'Box100_Latch_Pin': 80, 'Cover_Latch_Pin': 80, 'Cover_Lever_Pin': 80, 'Feed_Lever_Pin': 80,
            'Feed_Pawl_Shaft': 80, 'Retainer_Shaft': 80, 'Gripper_Pin': 80, 'Piston_Pin': 80}
# позы видимости — из ползунков рига (part_rig.SLIDERS); несвязанные движения сведены в одну позу. Покой — умолчания рига
POSES = {
    'open': {'cover': 1.0, 'tray': 1.0},
    'open_charged': {'cover': 1.0, 'tray': 1.0, 'charge': 1.0, 'feed': 1.0, 'port_cover': 1.0},
    'charged': {'charge': 1.0, 'port_cover': 1.0},
    'misc1': {'cover_latch': 1.0, 'trigger': 1.0, 'safety': 1.0, 'rest': 1.0, 'bipod_close': 1.0, 'sight_range': 0.0,
              'windage': 0.0, 'box_flap': 0.0, 'feed_flap': 1.0, 'exit_flap': 1.0},
    'misc2': {'bipod_fold': 1.0, 'bipod_close': 0.6, 'sight_range': 1.0, 'windage': 1.0, 'box_flap': 1.0},
}
# крышка коробки открывается только на снятой коробке: поза нужна, чтобы не удалить грани под крышкой, но плотность
# нутра по ней не считается (иначе пустая коробка изнутри съела бы атлас)
POSE_BOX_OPEN = {'box_lid': 1.0}
# точки глаза (оси исходника, м): в прицеливании — щека на прикладе, 0,26 м за целиком; от бедра — левее и выше
EYE_ADS = (-0.48, 0.0, 0.056)
EYE_HIP = (-0.55, 0.13, 0.16)
LOD1_K = 0.25
log = lambda *a: print('PKP_LP', *a, flush=True)  # noqa: E731


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
        o = o.parent
    return None


def node_parent(mover):
    """Узел-родитель узла мовера: ближайший мовер выше по иерархии исходника; иначе корень."""
    o = bpy.data.objects[mover].parent
    m = mover_of(o)
    return MOVERS[m] if m else ROOT_NODE


def rest_props():
    return {k: float(v) for k, _h, v in R.SLIDERS}


def set_props(ctl, props):
    for k, v in props.items():
        ctl[k] = float(v)


def control_poses(movers, extra=None):
    """Позы видимости: {поза: {узел: мировая дельта}} — из ползунков исходника; узлы без движения не пишутся."""
    ctl = bpy.data.objects[CONTROLS]
    rest = rest_props()
    set_props(ctl, rest)
    dg = refresh()
    base = {n: bpy.data.objects[n].evaluated_get(dg).matrix_world.copy() for n in movers}
    poses = {'rest': {}}
    for pose, props in {**POSES, **(extra or {})}.items():
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
    """Без развёрток, цветов и своих нормалей исходника: сетка упрощается свободно, развёртка — заново."""
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal', 'uv_group', 'uv_stack'):
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
    for _ in range(12):
        n = tris(o.data)
        if n <= budget * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(budget / n, 1 / 8) if organic else max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(o.data)
    bm.free()
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def hp_bvh(o):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    m = eo.matrix_world
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3) @ np.array(m.to_3x3(), np.float32).T + np.array(m.translation, np.float32)
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get('vertices', tri)
    eo.to_mesh_clear()
    return BVHTree.FromPolygons(co.tolist(), tri.reshape(-1, 3).tolist(), all_triangles=True)


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
    # развёртка: бок — один прямоугольник (шов по последней грани), торцы — плоские круги
    uvl = bm.loops.layers.uv.new('GameUV')
    arc = 2 * math.pi * r / sides
    length = float(hi[k] - lo[k])
    for fi, f in enumerate(fs):
        for lp in f.loops:
            j = vs.index(lp.vert)
            if fi < sides:
                i = j % sides
                if fi == sides - 1 and i == 0:
                    i = sides                                   # шов: конец прямоугольника
                lp[uvl].uv = (arc * i, length if j >= sides else 0.0)
            else:
                ox = 0.0 if fi == sides else 4 * r
                lp[uvl].uv = (arc * sides + 2 * r + ox + (lp.vert.co[a] - c[a]),
                              r + (lp.vert.co[b] - c[b]))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.validate()
    return tris(me)


def cut_bore(o, r_mm: float) -> int:
    """Грани канала вдоль оси X (радиус меньше r_mm) дальше BORE_KEEP_MM от обоих концов детали — прочь."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    xs = [v.co.x for v in bm.verts]
    x0, x1 = min(xs) + BORE_KEEP_MM * 0.001, max(xs) - BORE_KEEP_MM * 0.001
    r = r_mm * 0.001
    drop = [f for f in bm.faces if x0 < f.calc_center_median().x < x1
            and math.hypot(f.calc_center_median().y, f.calc_center_median().z) < r]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(o.data)
    bm.free()
    return len(drop)


def unwrap_piece(o, name: str) -> None:
    """Своя развёртка куска (Smart UV с изломом детали); трубки уже развёрнуты в tube()."""
    if 'GameUV' in o.data.uv_layers:
        return
    kit_uv.smart_unwrap([o], angle=math.radians(UV_ANGLE.get(name, 60)))


def deviation(lp, hp_obj) -> tuple:
    """Отклонение игровой сетки от исходника, мм: наибольшее и среднее — по вершинам и по точкам граней (центры и
    середины рёбер: широкая грань поперёк выемки вершин в выемке не имеет)."""
    bvh = hp_bvh(hp_obj)
    mw = lp.matrix_world
    pts = [mw @ v.co for v in lp.data.vertices]
    me = lp.data
    for p in me.polygons:
        vs = [pts[i] for i in p.vertices]
        c = sum(vs, Vector()) / len(vs)
        pts.append(c)
        for k in range(len(vs)):
            pts.append((vs[k] + vs[(k + 1) % len(vs)]) * 0.5)
    ds = [bvh.find_nearest(p)[3] for p in pts]
    ds = [x for x in ds if x is not None]
    return (round(max(ds) * 1000, 2), round(sum(ds) / len(ds) * 1000, 3)) if ds else (0.0, 0.0)


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
    """Приводы мовера исходника: [(свойство, индекс, выражение, [переменные ползунков])] — для рига игры и просмотра."""
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


def recheck_contact(objs, poses, cls, node_of) -> dict:
    """Кандидаты на удаление (прижатые во всех позах по kit_uv.visibility: лучи из центра и у вершин) — ещё раз густой
    сеткой точек грани: длинный треугольник упрощённой сетки бывает прижат серединой и виден краем (у гильз ленты
    под звеном вышли дыры-«стрелки»). Хоть один луч ушёл из сборки хоть в одной позе — грань остаётся."""
    from mathutils import Matrix, Vector
    dirs = [Vector(d) for d in kit_uv._FIB[::4]]
    bary = [(1 / 3, 1 / 3, 1 / 3)] + [tuple(0.9 if j == i else 0.05 for j in range(3)) for i in range(3)] +         [tuple(0.05 if j == i else 0.475 for j in range(3)) for i in range(3)] +         [tuple(0.6 if j == i else 0.2 for j in range(3)) for i in range(3)]
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
    """Классы граней у общей сетки (копии ленты): видимая, если видна хоть в одной копии; прижатая — если во всех."""
    out = {}
    for o, c in zip(objs, cls_list):
        r = rep_of(o)
        out[r] = c.copy() if r not in out else np.minimum(out[r], c)
    return out


SPARSE_SOLIDITY = 0.45     # площадь острова в UV к его наименьшему описанному прямоугольнику
SPARSE_MIN_M2 = 1.5e-4     # острова меньше 1,5 см² не режутся: каждый лишний кусок — ещё отступ 12 px
# Длинные узкие острова (торцы листа 1–1,5 мм, кромки) не режутся: проба 2026-11-15 — нарезка на куски по 40 мм
# опустила заполнение Body 62 → 44 %, а только длиннее 220 мм — до 50 %: отступ 12 px у полосы шириной в толщину
# листа больше самой полосы, каждый разрез добавляет ещё отступы.


def split_sparse(objs, uv: str = 'GameUV') -> int:
    """«Рамки» и сильно вогнутые острова (скругления краёв коробки разворачиваются кольцом: внутри кольца упаковщик
    оставляет пустое место) режутся пополам поперёк длинной стороны описанного прямоугольника, пока остров не станет
    плотным. Куски разводятся сдвигом UV — связь по общей кромке рвётся, layout кладёт их отдельно."""
    cuts = 0
    for o in objs:
        m = kit_uv._Mesh(o, uv)
        piece = np.zeros(m.npoly, np.int64)
        nid = 1
        work = [i.polys for i in kit_uv.islands_of([m])]
        pc = np.stack([np.bincount(m.poly_of_loop, m.uv[:, k], m.npoly) for k in range(2)], 1) /             np.maximum(m.lt, 1)[:, None]
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


def uv_only():
    """Пересборка развёртки и LOD1 с промежуточного файла (после видимости)."""
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=str(OUT / 'PKP_Game_LP_stage.blend'))
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
    for n in movers:
        e = hp[n].matrix_world.to_euler()
        if max(abs(a) for a in e) > 1e-5:
            log('ВНИМАНИЕ: мовер с поворотом', n, tuple(round(math.degrees(a), 2) for a in e))
    poses = control_poses(movers)
    poses_box = control_poses(movers, {'box_open': POSE_BOX_OPEN})
    dg = refresh()
    pivots = {MOVERS[n]: hp[n].evaluated_get(dg).matrix_world.translation.copy() for n in movers}
    pivots[ROOT_NODE] = Vector((0.0, 0.0, 0.0))
    parents = {MOVERS[n]: node_parent(n) for n in movers}
    parents['Belt'] = 'Box'
    pivots['Belt'] = hp[BELT['Link'][0]].matrix_world.translation.copy()
    drivers = {MOVERS[n]: driver_specs(hp[n]) for n in movers}

    # метки (оси исходника, м)
    fh0, fh1 = world_bbox(hp['Flash_Hider'])
    n0, n1 = world_bbox(hp['Rear_Sight_Notch'])
    p0, p1 = world_bbox(hp['Front_Sight_Post'])
    g0, g1 = world_bbox(hp['Pistol_Grip'])
    b0, b1 = world_bbox(hp['Shoulder_Rest'])
    marks = {'Muzzle': [round(fh1.x, 5), 0.0, 0.0],
             'SightRear': [round(0.5 * (n0.x + n1.x), 5), 0.0, round(n1.z, 5)],
             'SightFront': [round(0.5 * (p0.x + p1.x), 5), 0.0, round(p1.z, 5)],
             'Grip': [round(0.5 * (g0.x + g1.x), 5), 0.0, round(0.5 * (g0.z + g1.z), 5)],
             'Butt': [round(b0.x, 5), 0.0, round(0.5 * (b0.z + b1.z), 5)],
             'FeedRound': [round(hp['Belt_Round_00'].matrix_world.translation.x, 5), 0.0,
                           round(hp['Belt_Round_00'].matrix_world.translation.z, 5)]}
    log('метки', marks)

    coll = bpy.data.collections.new('GAME')
    bpy.context.scene.collection.children.link(coll)
    # узлы: пустышки (временные имена — у исходника есть Bolt, Trigger, Barrel), иерархия от корня
    nodes = {}

    def node_empty(name):
        if name in nodes:
            return nodes[name]
        par = None if name == ROOT_NODE else node_empty(parents[name])
        e = bpy.data.objects.new('node:' + name, None)
        e.empty_display_type = 'PLAIN_AXES'
        e.empty_display_size = 0.02
        coll.objects.link(e)
        e.parent = par
        e.location = pivots[name] - (pivots[parents[name]] if par else Vector())
        nodes[name] = e
        return e
    for n in [ROOT_NODE] + [MOVERS[m] for m in movers] + ['Belt']:
        node_empty(n)
    refresh()

    rec = {'source': str(SRC), 'axes_source': '+X дуло, +Z верх, −Y правая сторона стрелка; м', 'marks': marks,
           'nodes': {}, 'parts': {}, 'atlases': {}, 'belt': {}, 'poses': {k: sorted(v) for k, v in poses.items()},
           'drivers': drivers, 'controls': rest_props()}
    for n in nodes:
        rec['nodes'][n] = {'parent': None if n == ROOT_NODE else parents[n],
                           'pivot': [round(c, 6) for c in pivots[n]], 'meshes': []}

    # детали: упрощение по бюджету, сборка по (узел, атлас)
    pieces = {}
    total = 0
    for name, budget in PARTS.items():
        if name not in hp:
            log('нет детали', name)
            continue
        h = hp[name]
        m = mover_of(h)
        node = MOVERS[m] if m else ROOT_NODE
        atlas = SET_ATLAS[h['pkp_set']]
        o = evaluated_copy(h, 'lp_' + name, coll)
        n0 = tris(o.data)
        if name in TUBES:
            n = tube(o, TUBES[name])
        else:
            if name in BORE:
                log('канал', name, 'граней прочь', cut_bore(o, BORE[name]))
            n = simplify(o, min(budget, n0), organic=name in ORGANIC, voxel=REMESH.get(name, 0.0))
        dev = deviation(o, h)
        unwrap_piece(o, name)
        rec['parts'][name] = {'node': node, 'atlas': atlas, 'hp_tris': n0, 'tris': n, 'dev_mm': dev,
                              'uv_angle': UV_ANGLE.get(name, 60) if name not in TUBES else 'cyl'}
        log(f'{name}: {n0} → {n}, отклонение наиб. {dev[0]} мм, среднее {dev[1]} мм, узел {node}, атлас {atlas}')
        o['hp'] = [name]
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

    # лента: общие сетки и копии по местам исходника, под узлом Belt
    belt_node = nodes['Belt']
    refresh()
    belt_reps = {}
    for key, (src, budget) in list(BELT.items()) + [('Tip', BELT_TIP)]:
        h = hp[src]
        me = h.data.copy()
        me.name = f'Belt{key}'
        o = bpy.data.objects.new(f'{key}_00' if key != 'Tip' else 'Tip', me)
        coll.objects.link(o)
        o.matrix_world = h.matrix_world.copy()
        n0 = tris(me)
        n = tube(o, TUBES[src]) if src in TUBES else simplify(o, min(budget, n0), organic=False)
        dev = deviation(o, h)
        log(f'лента {key}: {n0} → {n}, отклонение наиб. {dev[0]} мм, среднее {dev[1]} мм')
        unwrap_piece(o, src)
        set_material(o, 'Box')
        o['atlas'], o['node'], o['hp'] = 'Box', 'Belt', [src]
        mw = o.matrix_world.copy()
        o.parent = belt_node
        o.matrix_parent_inverse = belt_node.matrix_world.inverted()
        o.matrix_world = mw
        belt_reps[key] = o
        game.append(o)
        rec['parts'][src] = {'node': 'Belt', 'atlas': 'Box', 'hp_tris': n0, 'tris': n, 'dev_mm': dev,
                             'copies': BELT_N if key != 'Tip' else 1}
        total += n * (BELT_N if key != 'Tip' else 1)
    belt_copies = []
    for key, (src, _b) in BELT.items():
        rec['belt'][key] = []
        for i in range(BELT_N):
            h = hp[src.replace('_00', f'_{i:02d}')]
            if i == 0:
                o = belt_reps[key]
            else:
                o = bpy.data.objects.new(f'{key}_{i:02d}', belt_reps[key].data)
                coll.objects.link(o)
                o['atlas'], o['node'], o['hp'] = 'Box', 'Belt', [h.name]
                o.parent = belt_node
                o.matrix_parent_inverse = belt_node.matrix_world.inverted()
                o.matrix_world = h.matrix_world.copy()
                belt_copies.append(o)
            rec['belt'][key].append({'object': o.name, 'hp': h.name,
                                     'matrix': [list(r) for r in h.matrix_world]})
    rec['tris_first_person_budget'] = total
    log('треугольников в руках после упрощения:', total, f'{time.time() - t0:.0f} с')

    # исходник больше не нужен: удаляется до развёртки (лучи видимости — только по игровым деталям)
    for o in list(bpy.data.objects):
        if o.name not in coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    for n, e in nodes.items():
        e.name = n
    refresh()
    allobj = game + belt_copies
    node_of = lambda o: o['node']  # noqa: E731
    rep_of = lambda o: o.data.name  # noqa: E731

    if novis:
        cls = {o.data.name: np.zeros(len(o.data.polygons), np.int32) for o in game}
    else:
        tv = time.time()
        cls_a = merge_classes(allobj, kit_uv.visibility(allobj, poses_box, node_of), rep_of)
        log('видимость со всеми позами', f'{time.time() - tv:.0f} с')
        tv = time.time()
        n0 = sum(int((c == kit_uv.CONTACT).sum()) for c in cls_a.values())
        cand = recheck_contact(game, poses_box, cls_a, node_of)
        log('прижатые: кандидатов', n0, 'после перепроверки', sum(len(c) for c in cand.values()),
            f'{time.time() - tv:.0f} с')
        # прижатые во всех позах (и с открытой крышкой коробки) — удалить
        for o in game:
            drop = np.array(sorted(cand[o.data.name]), np.int64)
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
                log('удалены прижатые', o.name, len(drop))
        refresh()
        tv = time.time()
        cls_b = merge_classes(allobj, kit_uv.visibility(allobj, poses, node_of), rep_of)
        log('видимость без открытой коробки', f'{time.time() - tv:.0f} с')
        cls = {}
        for k, c in cls_b.items():
            # грань, прижатая без позы «коробка открыта», но не прижатая с ней, — скрытая: остаётся, плотность мала
            cls[k] = np.where(c == kit_uv.CONTACT, kit_uv.HIDDEN, c)
    # промежуточный файл после видимости: развёртку и LOD1 можно пересобрать без лучей (-- --uv-only)
    for o in game:
        face_attr(o, 'vis_cls', cls[o.data.name])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'PKP_Game_LP_stage.blend'), compress=True)
    (OUT / 'parts_stage.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                          newline='\n')
    finish(rec, game, belt_copies, cls, t0)


def finish(rec, game, belt_copies, cls, t0):
    """Разрезание «рамок», укладка атласов, LOD1, сохранение."""
    rec['visibility'] = {}
    for o in game:
        c = cls[o.data.name]
        a = np.array([p.area for p in o.data.polygons]) * 1e4
        rec['visibility'][o.name] = {nm: round(float(a[c == k].sum()), 1) for nm, k in
                                     (('visible_cm2', 0), ('roomy_cm2', 1), ('hidden_cm2', 2))}
    for atlas in ATLAS_SIZE:
        objs = [o for o in game if o['atlas'] == atlas]
        a = {k: round(sum(rec['visibility'][o.name][k] for o in objs), 1) for k in ('visible_cm2', 'roomy_cm2', 'hidden_cm2')}
        log('площадь', atlas, a)

    # развёртка по атласам: только объекты со своей сеткой (копии ленты делят развёртку звена, спирали и патрона)
    eyes = [kit_uv.Eye(EYE_HIP, name='hip'), kit_uv.Eye(EYE_ADS, k_max=kit_uv.ADS_K, name='ads')]
    for atlas, size in ATLAS_SIZE.items():
        objs = [o for o in game if o['atlas'] == atlas]
        if not objs:
            continue
        split_sparse(objs)
        classes = [cls[o.data.name] for o in objs]
        rep = kit_uv.layout(objs, size, classes=classes, eyes=eyes if atlas != 'Box' else eyes[:1], log=log,
                            hidden_pool=True, precision=0.004)
        kit_uv.harden_on_seams(objs)
        rep['report'] = kit_uv.report(objs, size, classes=classes)
        rep['verify'] = kit_uv.verify(objs, size, classes=classes)
        rec['atlases'][atlas] = {'size': size, 'objects': [o.name for o in objs], **rep}
        if rep['fill'] < kit_uv.FILL_MIN:
            log('UV_FILL_LOW', atlas, rep['fill'])
        log('атлас', atlas, size, 'заполнение', rep['fill'], 'пикс/мм', rep['px_mm'], rep['report'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True

    # LOD1: копии сеток со схлопыванием до ¼, развёртка та же; копии ленты — на общих сетках LOD1
    lod_coll = bpy.data.collections.new('GAME_LOD1')
    bpy.context.scene.collection.children.link(lod_coll)
    lod_mesh = {}
    lod_total = 0
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
        n0 = tris(me)
        budget = max(12, int(n0 * LOD1_K))
        select_only(c)
        for _ in range(6):
            n = tris(c.data)
            if n <= budget * 1.05:
                break
            d = c.modifiers.new('lod', 'DECIMATE')
            d.ratio = max(budget / n, 0.05)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
        kit_uv.harden_on_seams([c])
        for p in c.data.polygons:
            p.use_smooth = True
        lod_mesh[o.data.name] = c.data
        k = BELT_N if o['node'] == 'Belt' and o.name != 'Tip' else 1
        lod_total += tris(c.data) * k
    for o in belt_copies:
        c = bpy.data.objects.new(o.name + '_LOD1', lod_mesh[o.data.name])
        lod_coll.objects.link(c)
        c.parent = o.parent
        c.matrix_parent_inverse = o.matrix_parent_inverse.copy()
        c.matrix_basis = o.matrix_basis.copy()
        for k in ('atlas', 'node', 'hp'):
            c[k] = o[k]
    lod_coll.hide_render = True
    bpy.context.view_layer.layer_collection.children['GAME_LOD1'].hide_viewport = True

    first = 0
    for o in game:
        k = BELT_N if o['node'] == 'Belt' and o.name != 'Tip' else 1
        n = tris(o.data)
        first += n * k
        rec['nodes'][o['node']].setdefault('mesh_tris', {})[o.name] = n
    rec['tris_first_person'] = first
    rec['tris_lod1'] = lod_total
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    path = OUT / 'PKP_Game_LP.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    (OUT / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('сохранено', path, 'в руках', first, 'LOD1', lod_total, f'{time.time() - t0:.0f} с')


if __name__ == '__main__':
    uv_only() if '--uv-only' in sys.argv else main()
