"""Мосин 1891/30 ПУ (винтовка v07 + крепление + прицел) → игровая сетка вида от первого лица.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_lp.py -- [fp|detail]
  fp     — основная игровая модель: 15 000 треугольников на винтовку с креплением и прицелом (владелец, 2026-10-17:
           «low poly в 15000 треугольников … главное, чтобы геометрия/текстуры не поехали»); своя развёртка и запекание;
  detail — подробная (~109 тыс.): разглядывать вблизи (как veras54_detail).
→ _asset_src/mosin_pu_game/<вариант>/lp/Mosin_Game_LP.blend + lp/parts.json (не в git).

Источник — замороженные принятые файлы библиотеки (models/approved, SHA-256 в SHA256.txt): форма v07 с текстурами
20 % v02 и прицел/крепление с текстурами 20 % v01; исходники не меняются. Координаты — оси винтовки в покое
(дуло +X, верх +Z, правая сторона стрелка −Y, начало — ось канала у казённого среза; метры), перевод в оси игры —
на экспорте (game_export.py). Затвор закрыт, курок спущен (cocked = 0) — как в файле.

Детали игры (каждая — своя развёртка в атласе своего материала, запекание — с её high-poly):
  Frame_Wood, Frame_Steel — неподвижное (ложа, накладка / ствол, коробка, магазинная коробка, кольца…);
  Bolt (ход по X) → Bolt_Bar (соединительная планка), Bolt_Rotor (поворот вокруг оси канала: стебель, рукоять,
  личинка, выбрасыватель), Bolt_Cocking (курок, грибок); Interrupter (отсечка-отражатель); Trigger (ось спуска);
  Follower (подаватель); RearSight_Leaf (ось колодки) → RearSight_Slider (хомутик); Mount_Base, Mount_Bracket →
  Scope (труба с барабанками; Scope_Lens — стёкла). Боёк спрятан в стебле — в игре его нет.
Патрон 7,62×54R — отдельные детали Round_Case / Round_Bullet / Round_Primer (атлас Ammo; гильза — без пули).
Атласы: Wood 4096, Steel 4096, Optic 2048 (прицел + крепление), Ammo 1024.
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
WORK = ROOT / '_asset_src/mosin_pu_game'
LIB = Path('E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models/approved')
SRC = {'rifle': LIB / 'Mosin_9130PU_Rifle_v07_tex20_v02.blend',
       'mount': LIB / 'Mosin_PU_Mount_v01_tex20_v01.blend',
       'scope': LIB / 'Mosin_PU_Scope_v01_tex20_v01.blend',
       'ammo': LIB / 'Mosin_Cartridge_762x54R_v01_tex_v01.blend'}
VARIANT = (sys.argv[sys.argv.index('--') + 1:] + ['fp'])[0] if '--' in sys.argv else 'fp'
assert VARIANT in ('fp', 'detail'), VARIANT
OUT = WORK / VARIANT / 'lp'
OUT.mkdir(parents=True, exist_ok=True)
SHARP = math.radians(60)

# Деталь игры → (атлас, узел-владелец, исходные объекты). None в списке Frame_Steel — «всё остальное стальное».
GROUPS = {
    'Frame_Wood_Stock': ('Wood', 'Frame', ['Stock']),
    'Frame_Wood_Handguard': ('Wood', 'Frame', ['Handguard']),
    'Frame_Steel': ('Steel', 'Frame', None),
    'Trigger_Mesh': ('Steel', 'Trigger', ['Trigger']),
    'Follower_Mesh': ('Steel', 'Follower', ['Magazine_Follower']),
    'RearSight_Leaf_Mesh': ('Steel', 'RearSight_Leaf', ['RearSight_Leaf_Mesh']),
    'RearSight_Slider_Mesh': ('Steel', 'RearSight_Slider', ['RearSight_Slider']),
    'Bolt_Rotor_Mesh': ('Steel', 'Bolt_Rotor', ['Bolt_Body', 'Bolt_Head', 'Bolt_Handle', 'Bolt_Handle_Ball', 'Bolt_Extractor']),
    'Bolt_Bar_Mesh': ('Steel', 'Bolt', ['Bolt_ConnectingBar']),
    'Bolt_Cocking_Mesh': ('Steel', 'Bolt_Cocking', ['Bolt_CockingPiece', 'Bolt_Knob', 'Bolt_FiringPin_End']),
    'Interrupter_Mesh': ('Steel', 'Interrupter', ['Receiver_Interrupter']),
    'Mount_Base_Mesh': ('Optic', 'Mount_Base', ['Mount_Base', 'Mount_Base_FrontStop', 'Mount_Base_RearBlock', 'Mount_Base_Screw', 'Mount_LockScrew']),
    'Mount_Bracket_Mesh': ('Optic', 'Mount_Bracket', ['Mount_Bracket', 'Mount_RingScrew', 'Mount_RingScrew.001', 'Mount_RingScrew.002']),
    'Scope_Body_Mesh': ('Optic', 'Scope', ['Scope_Body', 'Scope_TurretElev_Boss', 'Scope_TurretElev_Cap', 'Scope_TurretElev_CapScrew',
                                          'Scope_TurretElev_Scale', 'Scope_TurretWind_Boss', 'Scope_TurretWind_Cap', 'Scope_TurretWind_CapScrew',
                                          'Scope_TurretWind_CapScrew.001', 'Scope_TurretWind_CapScrew.002', 'Scope_TurretWind_Scale']),
    'Scope_Lens_Mesh': ('Lens', 'Scope', ['Scope_Lens_Eyepiece', 'Scope_Lens_Objective']),
    'Round_Case': ('Ammo', 'Round', ['Cartridge_Case']),
    'Round_Bullet': ('Ammo', 'Round', ['Cartridge_Bullet']),
    'Round_Primer': ('Ammo', 'Round', ['Cartridge_Primer']),
}
SKIP = ('Bolt_FiringPin', 'Scope_Reticle')      # боёк внутри стебля; сетку прицела рисует картинка оптики
ORGANIC = ('Stock', 'Handguard')
# detail: треугольники игровой детали (по исходному объекту) — разглядывают вблизи (владелец, 2026-10-17: «в руках —
# на 100 % идеально»). Не указанные — половина исходного, не меньше 48.
BUDGET_DETAIL = {'Stock': 26000, 'Handguard': 3000, 'Barrel': 4500, 'Receiver': 9000, 'Magazine_Box': 2000, 'TriggerGuard': 2200,
          'RearSight_Base': 2600, 'RearSight_Leaf_Mesh': 3200, 'RearSight_Slider': 900, 'RearSight_Pin': 300,
          'Bolt_Body': 4000, 'Bolt_Head': 3000, 'Bolt_Handle': 1800, 'Bolt_Handle_Ball': 1200, 'Bolt_CockingPiece': 2400,
          'Bolt_Knob': 1400, 'Bolt_ConnectingBar': 1200, 'Bolt_FiringPin_End': 160, 'Bolt_Extractor': 200,
          'Trigger': 900, 'Receiver_Tang': 900, 'Receiver_TangScrew': 400, 'Receiver_Interrupter': 450,
          'Band_Front': 1200, 'Band_Rear': 1200, 'Handguard_Ferrule_Front': 480, 'Handguard_Ferrule_Rear': 480,
          'Stock_NoseCap': 700, 'FrontSight_Base': 600, 'FrontSight_Hood': 600, 'CleaningRod': 400, 'Sling_Escutcheon': 300,
          'Scope_Body': 9000, 'Scope_Lens_Eyepiece': 320, 'Scope_Lens_Objective': 320,
          'Scope_TurretElev_Cap': 1400, 'Scope_TurretWind_Cap': 1400, 'Scope_TurretElev_Scale': 700, 'Scope_TurretWind_Scale': 700,
          'Scope_TurretElev_Boss': 400, 'Scope_TurretWind_Boss': 400, 'Mount_Bracket': 5000, 'Mount_LockScrew': 1200,
          'Cartridge_Case': 2000, 'Cartridge_Bullet': 1200, 'Cartridge_Primer': 160}
# fp: доли бюджета FP_TOTAL (винтовка, крепление, прицел; патрон — свой) — больше у глаза: коробка, затвор, шейка,
# прицел (обод окуляра обрамляет картинку прицела), круглое под рукой (шар рукояти, грибок, головка стопора — иначе
# вблизи видны грани); меньше у дальнего и
# скрытого. Не указанные детали — FP_SMALL.
FP_TOTAL = 12600                                 # запас на деление длинных рёбер и швы развёртки: в итоге ≈ 15 000
FP_WEIGHTS = {'Stock': 2700, 'Handguard': 420, 'Barrel': 600, 'Receiver': 1050, 'Magazine_Box': 320, 'TriggerGuard': 330,
              'RearSight_Base': 380, 'RearSight_Leaf_Mesh': 460, 'RearSight_Slider': 150, 'RearSight_Pin': 56,
              'Bolt_Body': 550, 'Bolt_Head': 380, 'Bolt_Handle': 340, 'Bolt_Handle_Ball': 380, 'Bolt_CockingPiece': 320,
              'Bolt_Knob': 300, 'Bolt_ConnectingBar': 180, 'Bolt_FiringPin_End': 24, 'Bolt_Extractor': 32,
              'Trigger': 110, 'Receiver_Tang': 110, 'Receiver_TangScrew': 44, 'Receiver_Interrupter': 56,
              'Band_Front': 190, 'Band_Rear': 190, 'Band_Spring': 24, 'Handguard_Ferrule_Front': 110, 'Handguard_Ferrule_Rear': 110,
              'Stock_NoseCap': 130, 'FrontSight_Base': 110, 'FrontSight_Hood': 110, 'FrontSight_Block': 36, 'FrontSight_Post': 12,
              'CleaningRod': 90, 'Buttplate': 130, 'Buttplate_Screw': 32, 'Sling_Escutcheon': 44, 'Stock_CrossScrew': 40,
              'Magazine_FrontScrew': 32, 'Magazine_Latch': 36, 'Magazine_Follower': 36,
              'Scope_Body': 2500, 'Scope_Lens_Eyepiece': 96, 'Scope_Lens_Objective': 96, 'Scope_TurretElev_Cap': 240,
              'Scope_TurretWind_Cap': 240, 'Scope_TurretElev_Scale': 100, 'Scope_TurretWind_Scale': 100,
              'Scope_TurretElev_Boss': 80, 'Scope_TurretWind_Boss': 80, 'Scope_TurretElev_CapScrew': 24, 'Scope_TurretWind_CapScrew': 24,
              'Mount_Bracket': 700, 'Mount_LockScrew': 240, 'Mount_Base': 120, 'Mount_Base_FrontStop': 120,
              'Mount_Base_RearBlock': 120, 'Mount_Base_Screw': 32, 'Mount_RingScrew': 32}
FP_SMALL = 32
FP_AMMO = {'Cartridge_Case': 700, 'Cartridge_Bullet': 420, 'Cartridge_Primer': 64}
# У глаза (шейка, гребень, коробка, затвор, начало накладки; x −380…+170 мм) сетка гуще в EYE_DENSITY раз;
# переход к дальней плотности — за 150 мм.
EYE_X = (-0.38, 0.17)
EYE_FALL = 0.15
EYE_DENSITY = 2.5
EYE_TEXEL, FAR_TEXEL = 1.35, 0.8                # fp: плотность текселей у глаза и вдали
HARD_ON_SEAM = math.radians(30)
ATLAS_SIZE = {'Wood': 4096, 'Steel': 4096, 'Optic': 4096, 'Ammo': 1024}
# Развёртка исходника (Smart UV по плотной сетке) — крупные чистые острова; заново по игровой сетке — только у деталей,
# чья развёртка — сотни островков (стенки букв клейм: ствол, коробка, стебель, планка); у всех заново круглые детали
# рвутся на узкие полосы и атлас пустеет (проверено: сталь заполнена на 28 % против 47 %). detail — всё исходника.
UV_RESET_ISLANDS = 150 if VARIANT == 'fp' else 10 ** 9
HIDDEN_UV_SCALE = 0.1                           # скрытые грани — в 10 раз реже текселей
UV_SLAB = 0.15                                  # длина полосы развёртки вдоль оси, м
# поля островов развёртки, пикселей атласа: в fp побольше — на mip-уровнях швы не плывут
UV_MARGIN_PX = 12 if VARIANT == 'fp' else 8
UV_ATLAS = {'Lens': 'Optic'}                    # стёкла — в атласе прицела, но свой материал
MATNAME = {'Wood': 'GAME • Wood • 20', 'Steel': 'GAME • Steel • 20', 'Optic': 'GAME • Optic • 20',
           'Lens': 'GAME • Lens • 20', 'Ammo': 'GAME • Ammo'}
log = lambda *a: print('MOSIN_LP', *a, flush=True)


def tris(me: bpy.types.Mesh) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def budget_for(name: str, n: int) -> int:
    base = name.split('.')[0]
    if VARIANT == 'detail':
        if name in BUDGET_DETAIL:
            return BUDGET_DETAIL[name]
        if base in BUDGET_DETAIL:
            return BUDGET_DETAIL[base]
        return max(48, int(n * 0.5))
    if base in FP_AMMO:
        return FP_AMMO[base]
    return max(12, min(n, int(FP_WEIGHTS.get(base, FP_SMALL) * FP_SCALE)))


def append_objects(path: Path, coll: bpy.types.Collection) -> list:
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = list(src.objects)
    out = []
    for o in dst.objects:
        if o is None or o.type in ('CAMERA', 'LIGHT'):
            continue
        coll.objects.link(o)
        out.append(o)
    return out


def evaluated_copy(o, dg, name):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    ob = bpy.data.objects.new(name, me)
    return ob


def source_islands(me: bpy.types.Mesh) -> int:
    if not me.uv_layers:
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    n = len(uv_islands(bm, bm.loops.layers.uv[0], list(bm.faces)))
    bm.free()
    return n


def strip(me: bpy.types.Mesh) -> None:
    """Без цветов и своих нормалей: сжатие сетки не держится за швы исходника. В варианте fp у деталей, чья
    развёртка — сотни островков (стенки букв клейм), она сбрасывается: их границы не дают сжать сетку до бюджета;
    такие грани помечены needs_uv и разворачиваются заново по игровой сетке (unwrap)."""
    if VARIANT == 'fp' and source_islands(me) > UV_RESET_ISLANDS:
        for uv in list(me.uv_layers):
            me.uv_layers.remove(uv)
        a = me.attributes.new('needs_uv', 'INT', 'FACE')
        a.data.foreach_set('value', [1] * len(me.polygons))
    # развёртка исходника (Smart UV по плотной сетке) идёт в игру: сжатие держит её швы, атлас — переупаковка
    for uv in list(me.uv_layers)[1:]:
        me.uv_layers.remove(uv)
    if me.uv_layers:
        me.uv_layers[0].name = 'GameUV'
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def collapse_to(o, target: int, organic: bool, group: str = '') -> None:
    """Сжатие до target треугольников; group — вес вершин (0 — не трогать, 1 — сжимать)."""
    for _ in range(8):
        n = tris(o.data)
        if n <= target * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        # органика (ложа): ступенями, не более чем в 8 раз за проход — без длинных клиньев на изгибах
        d.ratio = max(target / n, 1 / 8) if organic else max(1e-5, target / n)
        d.use_collapse_triangulate = True
        if group:
            d.vertex_group = group
        bpy.ops.object.modifier_apply(modifier=d.name)


def near_share(me) -> float:
    near = total = 0.0
    for pl in me.polygons:
        total += pl.area
        if EYE_X[0] <= pl.center.x <= EYE_X[1]:
            near += pl.area
    return near / max(total, 1e-12)


def split_regions(o) -> list:
    """Копии детали: [у глаза, вдали]; вершины на плоскостях шва не входят в группу 'free'."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    for x in EYE_X:
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
    bm.to_mesh(o.data)
    bm.free()
    out = []
    for near in (True, False):
        c = bpy.data.objects.new(o.name + ('_near' if near else '_far'), o.data.copy())
        for col in o.users_collection:
            col.objects.link(c)
        bm = bmesh.new()
        bm.from_mesh(c.data)
        drop = [f for f in bm.faces if (EYE_X[0] <= f.calc_center_median().x <= EYE_X[1]) != near]
        bmesh.ops.delete(bm, geom=drop, context='FACES')
        bm.to_mesh(c.data)
        bm.free()
        vg = c.vertex_groups.new(name='free')
        vg.add([v.index for v in c.data.vertices if min(abs(v.co.x - x) for x in EYE_X) > 1e-6], 1.0, 'REPLACE')
        out.append(c)
    return out


def merge_into(o, regions) -> None:
    """Сшить части по запертому шву и вернуть сетку детали в o."""
    bpy.ops.object.select_all(action='DESELECT')
    for r in regions:
        r.select_set(True)
    bpy.context.view_layer.objects.active = regions[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    bm = bmesh.new()
    bm.from_mesh(joined.data)
    seam = [v for v in bm.verts if min(abs(v.co.x - x) for x in EYE_X) <= 1e-6]
    bmesh.ops.remove_doubles(bm, verts=seam, dist=1e-6)
    bm.to_mesh(joined.data)
    bm.free()
    old = o.data
    o.data = joined.data
    bpy.data.objects.remove(joined, do_unlink=True)
    bpy.data.meshes.remove(old)
    select_only(o)


def simplify(o, budget: int, organic: bool, eye: bool = True) -> int:
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
        d.delimit = {'NORMAL', 'UV'}
        bpy.ops.object.modifier_apply(modifier=d.name)
        t = o.modifiers.new('tri', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=t.name)
    share = near_share(o.data)
    # fp — без зоны у глаза: на малом бюджете запертые кольца шва (сотни вершин) не дают сжать деталь; приоритет — бюджетами
    if VARIANT == 'detail' and eye and 0.05 < share < 0.95 and tris(o.data) > budget:
        # деталь тянется от глаза вдаль: у глаза плотность в EYE_DENSITY раз выше. Деталь режется плоскостями
        # x = EYE_X на ближнюю и дальнюю части, шов запирается (вершины шва вне группы 'free' — модификатор их не
        # трогает, проверено), каждая часть сжимается до своей доли, затем швы сшиваются.
        near_t = budget * share * EYE_DENSITY / (share * EYE_DENSITY + 1 - share)
        regions = split_regions(o)
        for reg, target in zip(regions, (near_t, budget - near_t)):
            select_only(reg)
            collapse_to(reg, int(target), organic, 'free')
            reg.vertex_groups.clear()
        merge_into(o, regions)
    else:
        collapse_to(o, budget, organic)
    slab_cut(o)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def slab_cut(o):
    """Разрез плоскостями x = k·UV_SLAB: длинные иглы-треугольники (шомпол, ствол, канал) иначе одним островом
    задают размер атласа; заодно острова исходника режутся по тем же границам (unwrap)."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if VARIANT == 'fp':
        # на малом бюджете плоскости через всю деталь дают +30 % треугольников — делятся только длинные рёбра
        for _ in range(4):
            long = [e for e in bm.edges if e.calc_length() > UV_SLAB]
            if not long:
                break
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
    else:
        xs = [v.co.x for v in bm.verts]
        x = (math.floor(min(xs) / UV_SLAB) + 1) * UV_SLAB
        while x < max(xs):
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=(x, 0, 0), plane_no=(1, 0, 0))
            x += UV_SLAB
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    # разрезы и сжатие оставляют треугольники нулевой площади: при выравнивании плотности такой остров
    # раздувается на весь атлас и перекрывает соседние (было — пятна на карте нормалей стали)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(o.data)
    bm.free()


def deviation(lp, hp_bvh) -> tuple[float, float]:
    """Насколько игровая поверхность ушла от high-poly: (снаружи — high-poly глубже игровой, внутри), мм, 99,7 %."""
    outside, inside = [], []
    me = lp.data
    pts = [v.co.copy() for v in me.vertices] + [p.center.copy() for p in me.polygons]
    for p in pts:
        loc, nrm, _i, dist = hp_bvh.find_nearest(p)
        if loc is None:
            continue
        (inside if (p - loc).dot(nrm) > 0 else outside).append(dist * 1000)
    q = lambda a: sorted(a)[int(len(a) * 0.997)] if a else 0.0
    return q(outside), q(inside)


def mark_sharp(o):
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    for e in bm.edges:
        sharp = (not e.is_manifold) or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > SHARP)
        e.smooth = not sharp
        e.seam = sharp
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(me)
    bm.free()
    if 'GameUV' not in me.uv_layers:
        me.uv_layers.new(name='GameUV')
    me.materials.clear()


def join(objs, name, coll):
    for o in objs:
        if o.name not in coll.objects:
            coll.objects.link(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o


FIB = [Vector((math.cos(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / 160) ** 2),
                math.sin(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / 160) ** 2),
                1 - (2 * k + 1) / 160)) for k in range(160)]   # равномерные направления на сфере


def build_bvh(posed):
    verts, polys = [], []
    for o, m in posed:
        base = len(verts)
        verts += [m @ v.co for v in o.data.vertices]
        polys += [[base + i for i in pl.vertices] for pl in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def visible_faces(o, m, bvh) -> set:
    """Грани, с которых хоть один луч из полусферы уходит за пределы сборки (2 м). Лучи — из центра и от углов
    грани: длинная грань трубы прицела или шомпола видна лишь краем (центр под кольцом / в ложе)."""
    nm = m.to_3x3()
    me = o.data
    vis = set()
    for pl in me.polygons:
        n = (nm @ pl.normal).normalized()
        c = m @ pl.center
        starts = [c] + [c + ((m @ me.vertices[i].co) - c) * 0.85 for i in pl.vertices]
        if any(bvh.ray_cast(s + n * 1e-5, d, 2.0)[0] is None for s in starts for d in FIB if d.dot(n) > 0.05):
            vis.add(pl.index)
    return vis


def uv_islands(bm, uvl, faces) -> list:
    """Острова развёртки среди faces: связь — общая кромка с теми же UV у обеих вершин."""
    pos = {f.index: i for i, f in enumerate(faces)}
    parent = list(range(len(faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for f in faces:
        mine = {l.vert.index: l[uvl].uv for l in f.loops}
        for e in f.edges:
            for g in e.link_faces:
                if g is f or g.index not in pos:
                    continue
                theirs = {l.vert.index: l[uvl].uv for l in g.loops}
                if all((mine[v.index] - theirs[v.index]).length < 1e-6 for v in e.verts):
                    parent[find(pos[f.index])] = find(pos[g.index])
    groups = {}
    for f in faces:
        groups.setdefault(find(pos[f.index]), []).append(f)
    return list(groups.values())


def clamp_density(objs) -> None:
    """Острова с плотностью текселей выше медианной вдвое (вырожденные, почти нулевой площади) — к медиане."""
    rows = []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for isl in uv_islands(bm, uvl, list(bm.faces)):
            a3 = sum(f.calc_area() for f in isl)
            a2 = 0.0
            for f in isl:
                uv = [l[uvl].uv for l in f.loops]
                for i in range(1, len(uv) - 1):
                    a2 += abs((uv[i] - uv[0]).cross(uv[i + 1] - uv[0])) / 2
            rows.append((math.sqrt(a2 / a3) if a3 > 1e-12 else float('inf'), a3))
        bm.free()
    finite = sorted((d, a) for d, a in rows if math.isfinite(d))
    half, acc, median = sum(a for _d, a in finite) / 2, 0.0, 1.0
    for d, a in finite:
        acc += a
        if acc >= half:
            median = d
            break
    fixed = 0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for isl in uv_islands(bm, uvl, list(bm.faces)):
            a3 = sum(f.calc_area() for f in isl)
            a2 = 0.0
            for f in isl:
                uv = [l[uvl].uv for l in f.loops]
                for i in range(1, len(uv) - 1):
                    a2 += abs((uv[i] - uv[0]).cross(uv[i + 1] - uv[0])) / 2
            d = math.sqrt(a2 / a3) if a3 > 1e-12 else float('inf')
            if d > median * 2.0:
                k = median / d if math.isfinite(d) else 1e-3
                loops = [l for f in isl for l in f.loops]
                c = sum((l[uvl].uv for l in loops), Vector((0, 0))) / len(loops)
                for l in loops:
                    l[uvl].uv = c + (l[uvl].uv - c) * k
                fixed += 1
        bm.to_mesh(o.data)
        bm.free()
    log('density clamp: islands fixed', fixed)


def smart_new(objs) -> None:
    """Грани needs_uv — Smart UV по игровой сетке полосами UV_SLAB вдоль оси (острова не длиннее полосы)."""
    marked = [o for o in objs if 'needs_uv' in o.data.attributes]
    if not marked:
        return
    bpy.ops.object.select_all(action='DESELECT')
    for o in marked:
        o.select_set(True)
    bpy.context.view_layer.objects.active = marked[0]
    bpy.ops.object.mode_set(mode='EDIT')
    xs = [f.center.x for o in marked for f in o.data.polygons]
    x0 = math.floor(min(xs) / UV_SLAB) * UV_SLAB
    while x0 <= max(xs):
        count = 0
        for o in marked:
            bm = bmesh.from_edit_mesh(o.data)
            layer = bm.faces.layers.int.get('needs_uv')
            for f in bm.faces:
                f.select_set(bool(layer is not None and f[layer]) and x0 <= f.calc_center_median().x < x0 + UV_SLAB)
                count += f.select
            bmesh.update_edit_mesh(o.data)
        if count:
            bpy.ops.uv.smart_project(angle_limit=SHARP, island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        x0 += UV_SLAB
    bpy.ops.object.mode_set(mode='OBJECT')
    log('smart uv', [o.name for o in marked])


def eye_texels(objs) -> None:
    """Плотность текселей выше у глаза (коробка, затвор, шейка, гребень: x в EYE_X — × EYE_TEXEL), ниже вдали
    (за EYE_FALL от зоны — × FAR_TEXEL): так делают у оружия от первого лица."""
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for isl in uv_islands(bm, uvl, list(bm.faces)):
            area = sum(f.calc_area() for f in isl)
            x = sum(f.calc_center_median().x * f.calc_area() for f in isl) / max(area, 1e-12)
            out = max(EYE_X[0] - x, x - EYE_X[1], 0.0)
            k = EYE_TEXEL + (FAR_TEXEL - EYE_TEXEL) * min(1.0, out / EYE_FALL)
            loops = [l for f in isl for l in f.loops]
            c = sum((l[uvl].uv for l in loops), Vector((0, 0))) / len(loops)
            for l in loops:
                l[uvl].uv = c + (l[uvl].uv - c) * k
        bm.to_mesh(o.data)
        bm.free()


def harden_on_seams(objs) -> None:
    """Жёсткое ребро — только на шве развёртки (иначе на запечённой нормали полоса вдоль ребра), и шов с изломом
    больше HARD_ON_SEAM — жёсткий: меньше градиентов на карте нормалей, она лучше переносит сжатие."""
    hard = soft = 0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            f1, f2 = e.link_faces
            u1 = {l.vert.index: l[uvl].uv for l in f1.loops}
            u2 = {l.vert.index: l[uvl].uv for l in f2.loops}
            seam = any((u1[v.index] - u2[v.index]).length > 1e-6 for v in e.verts)
            want_sharp = seam and e.calc_face_angle(0.0) > HARD_ON_SEAM
            if want_sharp and e.smooth:
                hard += 1
            elif not want_sharp and not e.smooth:
                soft += 1
            e.smooth = not want_sharp
        bm.to_mesh(o.data)
        bm.free()
    log('hard edges on seams: +', hard, 'softened', soft)


def unwrap(objs, margin, hidden, eye: bool = True):
    """Развёртка исходника (Smart UV по плотной сетке) — переупаковка в атлас. Острова режутся на отрезки
    UV_SLAB вдоль оси (длинная ложа, ствол и шомпол иначе задают размер атласа и оставляют его пустым); скрытые
    грани (канал ствола, ложе под стволом, ствол под накладкой) отделяются и уменьшаются в HIDDEN_UV_SCALE раз."""
    smart_new(objs)
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        hid = hidden.get(o.name, set())
        for f in bm.faces:
            # сдвиг в пределах плитки 0–1 рвёт связь островов (упаковка держит острова в их UDIM)
            off = 0.0005 * (math.floor(f.calc_center_median().x / UV_SLAB) % 40) + (0.0003 if f.index in hid else 0.0)
            for l in f.loops:
                l[uvl].uv.x += off
        bm.to_mesh(o.data)
        bm.free()
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    clamp_density(objs)
    if VARIANT == 'fp' and eye:
        eye_texels(objs)
    for o in objs:
        hid = hidden.get(o.name, set())
        if not hid:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        uvl = bm.loops.layers.uv['GameUV']
        for isl in uv_islands(bm, uvl, [bm.faces[i] for i in hid]):
            loops = [l for f in isl for l in f.loops]
            c = sum((l[uvl].uv for l in loops), Vector((0, 0))) / len(loops)
            for l in loops:
                l[uvl].uv = c + (l[uvl].uv - c) * HIDDEN_UV_SCALE
        bm.to_mesh(o.data)
        bm.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    # поля — точной долей атласа (в пикселях), иначе мелкие острова тонут в полях
    # ровные острова (по осям): иначе фаска на запечённой карте «лесенкой»
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='AXIS_ALIGNED' if VARIANT == 'fp' else 'ANY', scale=True,
                            margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    if VARIANT == 'fp':
        harden_on_seams(objs)


def texel(objs, size) -> float:
    a3 = a2 = 0.0
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for f in bm.faces:
            a3 += f.calc_area() * 1e6
            uv = [l[uvl].uv for l in f.loops]
            for i in range(1, len(uv) - 1):
                a2 += abs((uv[i].x - uv[0].x) * (uv[i + 1].y - uv[0].y) - (uv[i + 1].x - uv[0].x) * (uv[i].y - uv[0].y)) / 2
        bm.free()
    return round(math.sqrt(a2 * size * size / max(a3, 1e-9)), 2), round(a2, 3)


def empty(name, coll, parent=None, world=None):
    e = bpy.data.objects.new(name, None)
    coll.objects.link(e)
    e.empty_display_size = 0.01
    if parent is not None:
        e.parent = parent
    if world is not None:
        e.matrix_world = world
    return e


def parent_keep(o, parent):
    w = o.matrix_world.copy()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = w


def mm(v):
    return [round(x * 1000, 3) for x in v]


bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SRC['rifle']))
S = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)
rifle_names = [o.name for o in bpy.data.objects]
tmp = bpy.data.collections.new('HP_APPENDED')
S.collection.children.link(tmp)
mount_objs = append_objects(SRC['mount'], tmp)
scope_objs = append_objects(SRC['scope'], tmp)
ammo_objs = append_objects(SRC['ammo'], tmp)
bpy.context.view_layer.update()
socket = next(o for o in mount_objs if o.name.startswith('Mount_ScopeSocket'))
scope_root = next(o for o in scope_objs if o.name == 'PU_Scope')
scope_root.matrix_world = socket.matrix_world.copy()
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

# Состав деталей: неподвижная сталь — все прочие сетки винтовки.
named = {n for g in GROUPS.values() if g[2] for n in g[2]}
GROUPS['Frame_Steel'] = ('Steel', 'Frame', sorted(o.name for o in bpy.data.objects
                                                  if o.name in rifle_names and o.type == 'MESH' and o.name not in named
                                                  and not o.name.startswith(SKIP)))
lp = bpy.data.collections.new('MOSIN_GAME_LP')
all_sources = [n for g in GROUPS.values() for n in g[2] if not n.startswith('Cartridge')]
FP_SCALE = FP_TOTAL / sum(FP_WEIGHTS.get(n.split('.')[0], FP_SMALL) for n in all_sources)
S.collection.children.link(lp)
low, parts, cage, budgets = {}, {}, {}, {}
for gname, (atlas, node, names) in GROUPS.items():
    copies, devs = [], []
    for i, n in enumerate(names):
        src = bpy.data.objects[n]
        hp = evaluated_copy(src, dg, f'HP_{n}')
        before = tris(hp.data)
        bvh = BVHTree.FromPolygons([v.co.copy() for v in hp.data.vertices], [p.vertices[:] for p in hp.data.polygons])
        c = bpy.data.objects.new(f'{gname}_{i}', hp.data.copy())
        lp.objects.link(c)
        b = budget_for(n, before)
        after = simplify(c, b, organic=n in ORGANIC, eye=not gname.startswith('Round'))
        devs.append(deviation(c, bvh))
        budgets[n] = [before, after] + [round(x, 3) for x in devs[-1]] if devs else [before, after]
        bpy.data.meshes.remove(hp.data)
        copies.append(c)
    o = join(copies, gname, lp)
    mark_sharp(o)
    low[gname] = o
    parts[gname] = names
    out_d = max(d[0] for d in devs)
    in_d = max(d[1] for d in devs)
    # запас лучей: затыльник и плоские щёки после упрощения уходили от high-poly дальше 99,7-го перцентиля
    ext = min(4.0, max(0.4, out_d * 1.5 + 0.3))
    cage[gname] = {'extrusion_mm': round(ext, 3), 'max_ray_mm': round(ext + in_d * 1.5 + 0.5, 3),
                   'dev_out_mm': round(out_d, 3), 'dev_in_mm': round(in_d, 3)}
    log(gname, atlas, len(names), 'objects', tris(o.data), 'tris', cage[gname])

# Скрытые грани: ни один луч не уходит наружу ни в покое, ни при открытом отведённом затворе (взведён).
rifle_low = [o for g, o in low.items() if not g.startswith('Round')]
I4 = Matrix.Identity(4)
back = Matrix.Translation((-0.088, 0, 0))
OPEN = {'Bolt_Rotor_Mesh': back @ Matrix.Rotation(math.radians(-90), 4, 'X'), 'Bolt_Bar_Mesh': back,
        'Bolt_Cocking_Mesh': back @ Matrix.Translation((-0.0095, 0, 0))}
hidden, hidden_share = {}, {}
for pose in (None, OPEN):
    posed = [(o, (pose or {}).get(o.name, I4)) for o in rifle_low]
    bvh = build_bvh(posed)
    for o, m in posed:
        vis = visible_faces(o, m, bvh)
        hidden[o.name] = (hidden.get(o.name, set(range(len(o.data.polygons))))) - vis
for g, o in low.items():
    if g.startswith('Round'):
        continue
    area = sum(pl.area for pl in o.data.polygons)
    hidden_share[g] = round(sum(o.data.polygons[i].area for i in hidden[o.name]) / max(area, 1e-12), 3)
log('hidden area share', hidden_share)

# Развёртки по атласам и материалы.
texels = {}
for atlas, size in ATLAS_SIZE.items():
    keys = [g for g, v in GROUPS.items() if UV_ATLAS.get(v[0], v[0]) == atlas]
    objs = [low[k] for k in keys]
    unwrap(objs, UV_MARGIN_PX / size, hidden, eye=atlas != 'Ammo')   # патрон не на винтовке — без прибавки у глаза
    texels[atlas] = texel(objs, size)
    log('atlas', atlas, size, 'px/mm, uv area', texels[atlas])
for gname, (atlas, node, names) in GROUPS.items():
    mat = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    mat.use_nodes = True
    low[gname].data.materials.append(mat)

# Узлы игры: пустышки без поворота в точках осей, детали — дочерние.
src_world = lambda n: bpy.data.objects[n].matrix_world.translation.copy()
bbox_c = lambda o: sum((Vector(c) for c in o.bound_box), Vector()) / 8 if o.type == 'MESH' else o.location
T = Matrix.Translation
root = empty('Mosin_PU', lp)
root['asset'] = 'Мосин 1891/30 ПУ, состояние 20 %'
root['source'] = str(SRC['rifle'])
nodes = {'Mosin_PU': root}
nodes['Frame'] = empty('Frame', lp, root, T((0, 0, 0)))
nodes['Bolt'] = empty('Bolt', lp, root, T(src_world('Bolt')))
nodes['Bolt_Rotor'] = empty('Bolt_Rotor', lp, nodes['Bolt'], T(src_world('Bolt_Rotor')))
nodes['Bolt_Cocking'] = empty('Bolt_Cocking', lp, nodes['Bolt'], T(src_world('Bolt_Cocking')))
nodes['Interrupter'] = empty('Interrupter', lp, root, T(src_world('Interrupter_Slide')))
nodes['Trigger'] = empty('Trigger', lp, root, T(src_world('Trigger')))
fol = bpy.data.objects['Magazine_Follower']
nodes['Follower'] = empty('Follower', lp, root, T(fol.matrix_world @ bbox_c(fol)))
nodes['RearSight_Leaf'] = empty('RearSight_Leaf', lp, root, T(src_world('RearSight_Leaf')))
sl = bpy.data.objects['RearSight_Slider']
nodes['RearSight_Slider'] = empty('RearSight_Slider', lp, nodes['RearSight_Leaf'], T(sl.matrix_world @ bbox_c(sl)))
base_root = next(o for o in mount_objs if o.name.startswith('Mount_Base_Root'))
br_root = next(o for o in mount_objs if o.name.startswith('Mount_Bracket_Root'))
nodes['Mount_Base'] = empty('Mount_Base', lp, root, T(base_root.matrix_world.translation))
nodes['Mount_Bracket'] = empty('Mount_Bracket', lp, root, T(br_root.matrix_world.translation))
nodes['Scope'] = empty('Scope', lp, nodes['Mount_Bracket'], T(socket.matrix_world.translation))
ammo_root = empty('Round', lp, None, Matrix.Identity(4))
ammo_root['asset'] = 'Патрон 7,62×54R (гильза — те же Case и Primer без пули)'
nodes['Round'] = ammo_root
bpy.context.view_layer.update()
for gname, (atlas, node, names) in GROUPS.items():
    parent_keep(low[gname], nodes[node])

# Метки (мм, оси винтовки): дуло, мушка, прорезь хомутика, окуляр и объектив прицела.
post = bpy.data.objects['FrontSight_Post']
pw = [post.matrix_world @ Vector(c) for c in post.bound_box]
# прорезь целика — сзади планки (x < 90 мм): дно U-прорези по оси, верх целика 26,0
leaf = bpy.data.objects['RearSight_Leaf_Mesh']
leaf_eval = leaf.evaluated_get(dg).to_mesh()
mid = [leaf.matrix_world @ v.co for v in leaf_eval.vertices]
mid = [p for p in mid if abs(p.y) < 0.00005 and p.x < 0.090]
top = max(p.z for p in mid)
notch_pts = [p for p in mid if p.z > top - 0.0001]
notch_x = sum(p.x for p in notch_pts) / len(notch_pts)
leaf.evaluated_get(dg).to_mesh_clear()
sock = socket.matrix_world.translation.copy()
socket_world = [list(r) for r in socket.matrix_world]
scope_len = max((scope_root.matrix_world.inverted() @ (o.matrix_world @ Vector(c))).x
                for o in scope_objs if o.name.startswith('Scope_Body') for c in o.bound_box)
markers = {'Muzzle': mm(Vector((0.7288, 0, 0))),
           'SightFront': mm(Vector((sum(p.x for p in pw) / 8, 0, max(p.z for p in pw)))),
           'SightRear': mm(Vector((notch_x, 0, top))),
           'ScopeEye': mm(sock),
           'ScopeFront': mm(sock + Vector((scope_len, 0, 0)))}
log('markers', markers)

# Убрать исходную сцену: остаются игровые узлы.
keep = set(o.name for o in lp.all_objects)
for o in list(bpy.data.objects):
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c != lp:
        bpy.data.collections.remove(c)
for im in list(bpy.data.images):
    bpy.data.images.remove(im)
bpy.ops.outliner.orphans_purge(do_recursive=True)
for g, o in low.items():                        # имена игровых деталей были заняты исходными объектами (…001)
    o.name = g
    o.data.name = g
for k, e in nodes.items():                      # то же у пустышек узлов (Bolt, Trigger, RearSight_Leaf…)
    e.name = k
fp = sum(tris(o.data) for o in lp.all_objects if o.type == 'MESH' and not o.name.startswith('Round'))
record = dict(variant=VARIANT, sources={k: str(v) for k, v in SRC.items()}, groups={g: dict(atlas=v[0], node=v[1], sources=parts[g]) for g, v in GROUPS.items()},
              materials=MATNAME, atlas_size=ATLAS_SIZE, uv_margin_px=UV_MARGIN_PX, uv_atlas=UV_ATLAS, texel_px_mm=texels, hidden_area_share=hidden_share, cage=cage, budgets=budgets,
              triangles_first_person=fp, meshes={o.name: tris(o.data) for o in lp.all_objects if o.type == 'MESH'},
              pivots_mm={k: mm(v.matrix_world.translation) for k, v in nodes.items()}, markers_mm=markers,
              scope_socket=socket_world, skipped=list(SKIP),
              rest_pose='затвор закрыт, курок спущен (cocked 0), отсечка-отражатель внутри коробки на 2,8 мм')
(OUT / 'parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'Mosin_Game_LP.blend'))
log('SAVED', VARIANT, OUT / 'Mosin_Game_LP.blend', 'first person tris', fp)
