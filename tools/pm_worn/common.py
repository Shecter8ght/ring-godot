"""ПМ / КОРС-9 «пошарпанный» v01 в игру: общие пути и помощники конвейера tools/pm_worn.

Исходник — принятая владельцем 2026-10-20 выдача «21_ПМ_в_манере_ВЕРАС_v01_на_проверку» (библиотека Blender только
читается). Рабочая папка — _asset_src/pm_worn_game (не в git): lp/ — игровая сетка, maps/raw — запечённое,
maps/game — упакованное. Координаты сборки ПМ: дуло −X, верх +Z, правая сторона стрелка +Y, метры.
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/pm_worn_game'
LIB = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/21_ПМ_в_манере_ВЕРАС_v01_на_проверку')
SRC_PM = LIB / '01_ПМ/PM_Textures_Worn_v01.blend'
SRC_MAG = LIB / '02_Глушитель_и_магазины/magazine_loaded_worn_v01.blend'
SRC_ROUND = LIB / '02_Глушитель_и_магазины/cartridge_worn_v01.blend'
SRC_SUPP = LIB / '02_Глушитель_и_магазины/suppressor_worn_v01.blend'
SRC_SIGHT = LIB / '03_Коллиматор/PM_ReflexSight_on_mount_Worn_v01.blend'
LP_FILE = WORK / 'lp/PM_Worn_LP.blend'
PARTS_FILE = WORK / 'lp/parts.json'
MARKERS_FILE = WORK / 'lp/markers.json'
RAW = WORK / 'maps/raw'
GAME = WORK / 'maps/game'
ASSET = ROOT / 'assets/models/weapons/pm'
ATT_SUPP = ROOT / 'assets/models/attachments/supp_pm'
ATT_SIGHT = ROOT / 'assets/models/attachments/zorin_k1'
SHARP = math.radians(60)
# Глушитель отдельного файла: ось +Y от переходника → сцена ПМ (поворот +90° вокруг Z), переходник у x = −79.22 мм,
# ось канала z = 112.53 мм (как глушитель в сборке).
SUPP_SEAT = Matrix.Translation((-0.07922, 0.0, 0.11253)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
# Атласы и их размер (пикселей): сталь — основа вида в руках.
SIZE = {'Steel': 4096, 'Grip': 2048, 'Magazine': 2048, 'Ammo': 512, 'Suppressor': 4096}
ATLAS = {'Steel': ('Slide', 'Frame', 'Barrel', 'Hammer', 'Trigger', 'Safety', 'SlideStop', 'MagCatch'),
         'Grip': ('Grip',), 'Magazine': ('MagBody', 'Follower', 'Spring'), 'Ammo': ('Case', 'Jacket', 'Primer'),
         'Suppressor': ('Suppressor',)}
MATNAME = {'Steel': 'GAME • Steel • 100', 'Grip': 'GAME • Grip • 100', 'Magazine': 'GAME • Magazine • 100',
           'Ammo': 'GAME • Ammo • 100', 'Suppressor': 'GAME • Suppressor • 100'}
LP_NAME = {'Slide': 'Slide_Mesh', 'Frame': 'Frame_Mesh', 'Barrel': 'Barrel_Mesh', 'Hammer': 'Hammer_Mesh',
           'Trigger': 'Trigger_Mesh', 'Safety': 'Safety_Mesh', 'SlideStop': 'SlideStop_Mesh', 'MagCatch': 'MagCatch_Mesh',
           'Grip': 'Grip_Mesh', 'MagBody': 'Magazine_Mesh', 'Follower': 'Follower_Mesh', 'Spring': 'Spring_Mesh',
           'Case': 'LP_Case', 'Jacket': 'LP_Jacket', 'Primer': 'LP_Primer', 'Suppressor': 'Suppressor_Mesh'}
CONTROLS = 'PM_CONTROLS • select me'
CONTROL_KEYS = ('Slide', 'Hammer', 'Trigger', 'Safety', 'Magazine', 'MagCatch', 'SlideStop', 'Suppressor')


def log(tag: str, *a) -> None:
    print(tag, *a, flush=True)


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def obj_tris(o) -> int:
    return tris(o.data)


def rest_pose() -> None:
    """Сборка ПМ в покое: все контролы 0 (глушитель надет, затвор закрыт)."""
    rig = bpy.data.objects.get(CONTROLS)
    if rig is None:
        return
    for k in CONTROL_KEYS:
        if k in rig.keys():
            rig[k] = 0.0
    rig.update_tag()
    bpy.context.view_layer.update()


def gpu_cycles(scene, samples: int) -> None:
    scene.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU'
        if any(d.use for d in prefs.devices):
            scene.cycles.device = 'GPU'
    except Exception as error:  # noqa: BLE001
        log('PM_WORN', 'GPU недоступен:', error)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False


def enable_ucupaint() -> None:
    import addon_utils
    try:
        addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    except Exception as error:  # noqa: BLE001
        log('PM_WORN', 'UCUPaint не включён:', error)


def evaluated_copy(o, dg, name: str):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    return bpy.data.objects.new(name, me)


def activate(objs) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[-1]


def join(objs, name: str, coll):
    for o in objs:
        coll.objects.link(o)
    activate(objs)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


def simplify(o, budget: int, organic: bool = False) -> int:
    """Сетка под бюджет: сварка, растворение плоскостей, схлопывание; острые рёбра — швы развёртки."""
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    for m in list(o.modifiers):
        o.modifiers.remove(m)
    activate([o])
    if tris(me) > budget and not organic:
        d = o.modifiers.new('planar', 'DECIMATE')
        d.decimate_type = 'DISSOLVE'
        d.angle_limit = math.radians(0.6)
        d.delimit = {'NORMAL'}
        bpy.ops.object.modifier_apply(modifier=d.name)
        t = o.modifiers.new('tri', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=t.name)
    for _ in range(4):
        n = tris(o.data)
        if n <= budget * 1.05:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        # органика (рукоять): ступенями, не более чем в 30 раз за проход — без длинных клиньев
        d.ratio = max(budget / n, 1 / 30) if organic else max(1e-5, budget / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)
    me = o.data
    me.validate(clean_customdata=False)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    for e in bm.edges:
        sharp = (not e.is_manifold) or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > SHARP)
        e.smooth = not sharp
        e.seam = sharp
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    me.uv_layers.new(name='GameUV')
    me.materials.clear()
    return tris(me)


def unwrap(objs, margin: float) -> None:
    activate(objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=SHARP, island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def texel_report(objs, size: int) -> dict:
    out = {}
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        a3 = sum(f.calc_area() for f in bm.faces) * 1e6
        a2 = 0.0
        for f in bm.faces:
            uv = [l[uvl].uv for l in f.loops]
            for i in range(1, len(uv) - 1):
                a2 += abs((uv[i].x - uv[0].x) * (uv[i + 1].y - uv[0].y) - (uv[i + 1].x - uv[0].x) * (uv[i].y - uv[0].y)) / 2
        bm.free()
        out[o.name] = round(math.sqrt(a2 * size * size / max(a3, 1e-9)), 2)
    return out


def empty(name: str, coll, parent=None, world=None):
    e = bpy.data.objects.new(name, None)
    coll.objects.link(e)
    e.empty_display_size = 0.006
    if parent is not None:
        e.parent = parent
    if world is not None:
        e.matrix_world = world
    return e


def parent_keep(o, parent) -> None:
    w = o.matrix_world.copy()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = w


def load_objects(path: Path, names=None, coll_name: str = 'TMP'):
    """Объекты другого .blend (копией) в новую коллекцию сцены; возвращает (коллекция, объекты)."""
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if names is None or names(n)]
    coll = bpy.data.collections.new(coll_name)
    bpy.context.scene.collection.children.link(coll)
    objs = []
    for o in dst.objects:
        if o is None or o.type in ('CAMERA', 'LIGHT'):
            continue
        coll.objects.link(o)
        objs.append(o)
    bpy.context.view_layer.update()
    return coll, objs
