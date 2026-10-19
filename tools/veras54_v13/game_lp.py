"""ВЕРАС-54 v13 → игровая сетка вида от первого лица (low-poly со своей развёрткой).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_v13/game_lp.py
→ _asset_src/veras54_game_v13/lp/VERAS54_Game_LP.blend + lp/parts.json (не в git).

Источник — принятый владельцем текстурированный high-poly v13 (геометрия v13 и текстуры v13 v02 приняты 2026-10-19):
E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Актуальное/VERAS54_Only_State100_v13_Textured_v02.blend
(SHA-256 — в parts.json); исходник не меняется. Оси — оси автомата (дуло +X, +Y влево стрелка, +Z вверх, начало — ось канала
у заднего торца коробки; метры), как у узла VERAS54 в сцене рук и клипов; затвор закрыт, переводчик на «АВ».

Бюджет (владелец, 2026-10-19): модель в руках — до 40 000 треугольников. Автомат с магазином ≈ 34 тыс., 30 патронов ≈ 5 тыс.
Мелкое круглое (заклёпки, винты, оси) — своя доля, кольцо из упрощения не выпадает; U-прорезь целика и мушка — свой бюджет.

Узлы (кости рига оружия, как у прежнего «Риг v01»): WeaponRoot — неподвижное; DustCover — крышка с планкой и целиком;
Bolt — рама, затвор, шток, рукоятка, выбрасыватель; Selector; Trigger; MagazineLatch (лопатка защёлки); CoverButton;
StockFold — складная часть приклада; MuzzleAttachment — дульное устройство; RecoilSpring — пружина (сжимается рамой);
Magazine — корпус и пятка; MagazineFollower; патроны Magazine • loaded case/projectile N (одна сетка на все 30, развёртка общая).
Атласы: Steel 4096 (сталь и крепёж), Polymer 4096 (цевьё, рукоятка, приклад, затыльник), Magazine 2048, Ammo 1024.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/veras54_game_v13'
SRC = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Актуальное/VERAS54_Only_State100_v13_Textured_v02.blend')
SRC_SHA = 'acb5afc842647ec4c079268aaa1497fa6beb3c720cc9f2ab28d7bd9f5cb283dc'
OUT = WORK / 'lp'
OUT.mkdir(parents=True, exist_ok=True)
SHARP = math.radians(60)
BOLT_TRAVEL = 0.1006                     # ход рамы на «АВ» (м), как драйвер исходника
MAG_OUT = Vector((-0.035, 0.0, -0.140))  # магазин вынут (драйвер исходника)
HINGE = Vector((-0.006, 0.027, -0.010))  # ось складывания приклада
SPRING_O = Vector((0.018, 0.0, 0.0155))  # задний конец пружины: сжимается к нему
SPRING_LEN = 0.1640

# Целевые треугольники по имени детали исходника (без номера/стороны в конце): доля бюджета, у глаза больше.
# Не указанные — SMALL. Сумма ≈ 33 тыс. на автомат с магазином.
BUDGET = {
    'Bolt carrier • body': 1000, 'Bolt carrier • charging handle': 440, 'Bolt carrier • gas piston': 140,
    'Bolt • extractor': 60, 'Bolt • rotating head': 420,
    'Cover release • ribbed thumb button': 260, 'Cover release • rounded housing': 240, 'Cover retaining pin': 80,
    'Dust cover • continuous capped sheet': 1500, 'Magwell • side lip': 40,
    'Rear sight • clamp bolt head': 96, 'Rear sight • front ladder stop': 120, 'Rear sight • front support pivot': 96,
    'Rear sight • large knurled windage drum': 600, 'Rear sight • mounting foot': 60,
    'Rear sight • plain opposite retainer': 200, 'Rear sight • rail clamp jaw': 100, 'Rear sight • range leaf': 520,
    'Rear sight • range slider buttons': 100, 'Rear sight • range spring bridge': 120,
    'Rear sight • transverse retaining bolt': 80, 'Rear sight • windage bar with U-notch': 560,
    'Rear sight • windage end cap': 200, 'Rear sling plate': 100,
    'Receiver top rail • integral channelled rail': 2000, 'Receiver • carrier guide rails': 60,
    'Receiver • front trunnion': 120, 'Receiver • left wall': 1100, 'Receiver • lower front bridge': 40,
    'Receiver • lower rear bridge': 80, 'Receiver • rear closure': 40, 'Receiver • right wall / ejection opening': 1400,
    'Receiver • rivet': 56, 'Receiver • trigger pin heads': 80, 'Recoil spring • coil': 240, 'Recoil spring • guide rod': 60,
    'Selector • domed pivot': 160, 'Selector • stamped lever': 520,
    'Barrel band': 200, 'Barrel band • lower lug': 40, 'Barrel • through bore': 420, 'Brake • body pin': 80,
    'Front bayonet loop • transverse ring': 400, 'Front bayonet loop • upper lug': 40,
    'Front sight • tapered centre post': 160, 'Front sight • threaded post foot': 120, 'Gas block • cross pins': 80,
    'Gas block • front sight base': 900, 'Gas block • front sling loop': 140,
    'Gas tube • distinct front seating collar': 400, 'Gas tube • rear-fluted tube': 1100,
    'Muzzle • bayonet / retaining band': 360, 'Muzzle • visible bare muzzle': 400,
    'Handguard bracket fastener • rear': 96, 'Handguard lower rail • spine': 120, 'Handguard lower rail • tooth': 60,
    'Handguard retaining bracket • rear': 200, 'Handguard upper rail • spine': 120, 'Handguard upper rail • tooth': 72,
    'Handguard • curved rear retaining clip': 160, 'Handguard • front bushings': 300, 'Handguard • inner vent support': 240,
    'Handguard • integrated sculpted lower shell': 2300, 'Handguard • moulded front end': 400,
    'Handguard • upper ventilated shell': 2300, 'Side rail • front screw': 80, 'Side rail • integral front mounting': 260,
    'Stock hinge • axle cap': 120, 'Stock hinge • fixed knuckle': 200, 'Stock hinge • fixed rear plate': 40,
    'Stock hinge • moving knuckle': 200, 'Stock hinge • moving tongue': 40, 'Stock hinge • release button': 40,
    'Stock hinge • stock tube shoulder': 260, 'Stock hinge • vertical axle': 140, 'Stock • QD metal socket': 160,
    'Stock • adjustment latch': 260, 'Stock • continuous moulded skeleton': 2600, 'Stock • front collar': 520,
    'Stock • latch pivot': 72, 'Stock • rubber buttpad': 800, 'Stock • sliding extension tube': 300,
    'Magazine catch • axle': 100, 'Magazine catch • paddle': 280, 'Magazine catch • pivot rivet': 64,
    'Magazine catch • rounded pivot wing': 180, 'Pistol grip • base cap': 160, 'Pistol grip • latch bezel': 60,
    'Pistol grip • latch button': 60, 'Pistol grip • sculpted continuous body': 1700, 'Trigger group • hammer': 100,
    'Trigger guard • thin formed bow': 220, 'Trigger • curved blade': 260,
    'Magazine_Body': 2600, 'Magazine_Floorplate': 200, 'Magazine_Follower': 160, 'Magazine_Indicator_Channel': 80,
    'Brake • retaining pin': 72, 'Muzzle brake • open chamber': 900,
}
SMALL = 48
ROUND_BUDGET = {'case': 110, 'projectile': 70}
# Органика — ступенями (не более чем в 8 раз за проход): без длинных клиньев на изгибах
ORGANIC = ('Stock • continuous moulded skeleton', 'Stock • rubber buttpad', 'Handguard • integrated sculpted lower shell',
           'Handguard • upper ventilated shell', 'Pistol grip • sculpted continuous body', 'Magazine_Body')
# Крупные детали (бюджет больше SCALE_FROM) ужимаются в FP_SCALE раз — итог ≈ 34 тыс. на автомат с магазином после
# удаления скрытых граней; мелкое (крепёж, зубья планок, оси) — как в таблице: на меньшем числе граней круглое гранится.
FP_SCALE = 0.74
SCALE_FROM = 150
NOSCALE = ('Rear sight • windage bar with U-notch', 'Front sight • tapered centre post', 'Stock • front collar')
# Замки вершин (группа free) здесь не используются: на U-прорези целика замок ломал брусок вокруг неё (отклонение 1 мм) —
# прорезь держится своим бюджетом; проверка — кадр notch (game_view.py).
PROTECT = {}
UV_SLAB = 0.15
CONTACT = 0.004
ROOMY = 0.008
HIDDEN_UV_SCALE = 0.1
HIDDEN_ROOMY_SCALE = 0.5
HARD_ON_SEAM = math.radians(30)
UV_MARGIN_PX = 12
ATLAS_SIZE = {'Steel': 4096, 'Polymer': 4096, 'Magazine': 2048, 'Ammo': 1024}
MATNAME = {a: f'GAME • {a} • 100' for a in ATLAS_SIZE}
MATNAME['Ammo'] = 'GAME • Ammo'
log = lambda *a: print('VERAS_LP', *a, flush=True)


def base_name(n: str) -> str:
    """Имя детали без стороны и номера в конце («Receiver • rivet +1 03» → «Receiver • rivet»)."""
    parts = n.split(' ')
    while len(parts) > 1 and re.fullmatch(r'[+-]?\d+(\.\d+)?', parts[-1]):
        parts.pop()
    return ' '.join(parts)


def budget_for(n: str) -> int:
    b = base_name(n)
    v = BUDGET.get(n, BUDGET.get(b, SMALL))
    if v > SCALE_FROM and b not in NOSCALE:
        v = int(v * FP_SCALE)
    return v


def atlas_of_material(m) -> str:
    name = m.name if m else ''
    if name.startswith(('01', '02', '09')):
        return 'Steel'
    if name.startswith(('03', '05')):
        return 'Polymer'
    if name.startswith(('04', '13')) or name.startswith('Magazine_Follower'):
        return 'Magazine'
    if name.startswith(('11', '12')):
        return 'Ammo'
    raise RuntimeError(f'материал без атласа: {name}')


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def evaluated_copy(o, dg, name):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    ob = bpy.data.objects.new(name, me)
    return ob


def strip(me) -> None:
    """Без своих нормалей, цветов и развёртки исходника: игровая развёртка строится заново по low-poly."""
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])


def collapse_to(o, target: int, organic: bool, group: str = '') -> None:
    for _ in range(10):
        n = tris(o.data)
        if n <= target * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(target / n, 1 / 8) if organic else max(1e-5, target / n)
        d.use_collapse_triangulate = True
        if group:
            d.vertex_group = group
        bpy.ops.object.modifier_apply(modifier=d.name)


def slab_cut(o) -> None:
    """Длинные рёбра (ствол, газовая трубка, планки) — на отрезки UV_SLAB: длинный остров иначе задаёт размер атласа."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    by_cuts = {}
    for e in bm.edges:
        n = math.ceil(e.calc_length() / UV_SLAB) - 1
        if n > 0:
            by_cuts.setdefault(n, []).append(e)
    for n, edges in by_cuts.items():
        edges = [e for e in edges if e.is_valid]
        if edges:
            bmesh.ops.subdivide_edges(bm, edges=edges, cuts=n, use_grid_fill=False)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-6)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(o.data)
    bm.free()


def simplify(o, budget: int, organic: bool, protect=None) -> int:
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
        d.delimit = {'NORMAL'}
        bpy.ops.object.modifier_apply(modifier=d.name)
        t = o.modifiers.new('tri', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=t.name)
    if protect is not None:
        vg = o.vertex_groups.new(name='free')
        vg.add([v.index for v in o.data.vertices if not protect(v.co)], 1.0, 'REPLACE')
        collapse_to(o, budget, organic, 'free')
        o.vertex_groups.clear()
    else:
        collapse_to(o, budget, organic)
    slab_cut(o)
    t = o.modifiers.new('tri', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=t.name)
    o.data.validate(clean_customdata=False)
    return tris(o.data)


def deviation(lp, hp_bvh) -> tuple:
    """Насколько игровая поверхность ушла от high-poly: (снаружи, внутри), мм, 99,7 %."""
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
        f.material_index = 0
    bm.to_mesh(me)
    bm.free()
    me.materials.clear()


FIB_N = 320
FIB = [Vector((math.cos(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / FIB_N) ** 2),
                math.sin(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / FIB_N) ** 2),
                1 - (2 * k + 1) / FIB_N)) for k in range(FIB_N)]


def build_bvh(posed):
    verts, polys = [], []
    for o, m in posed:
        base = len(verts)
        verts += [m @ v.co for v in o.data.vertices]
        polys += [[base + i for i in pl.vertices] for pl in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def visible_faces(o, m, bvh) -> tuple:
    """Видимые грани (хоть один луч из полусферы уходит за пределы сборки), прижатые (все лучи упираются ближе CONTACT)
    и просторные скрытые."""
    nm = m.to_3x3()
    me = o.data
    vis, contact, roomy = set(), set(), set()
    for pl in me.polygons:
        n = (nm @ pl.normal).normalized()
        c = m @ pl.center
        starts = [c] + [c + ((m @ me.vertices[i].co) - c) * 0.85 for i in pl.vertices]
        dirs = [d for d in FIB if d.dot(n) > 0.05]
        dist, seen = [], False
        for st in starts:
            for d in dirs:
                hit = bvh.ray_cast(st + n * 1e-5, d, 2.0)
                if hit[0] is None:
                    seen = True
                    break
                dist.append(hit[3])
            if seen:
                break
        if seen:
            vis.add(pl.index)
        else:
            med = sorted(dist)[len(dist) // 2]
            if med < CONTACT:
                contact.add(pl.index)
            elif med > ROOMY:
                roomy.add(pl.index)
    return vis, contact, roomy


def uv_islands(bm, uvl, faces) -> list:
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
    """Острова с плотностью текселей выше медианной вдвое (вырожденные) — к медиане."""
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


def harden_on_seams(objs) -> None:
    """Жёсткое ребро — только на шве развёртки; шов с изломом больше HARD_ON_SEAM — жёсткий."""
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
            e.smooth = not (seam and e.calc_face_angle(0.0) > HARD_ON_SEAM)
        bm.to_mesh(o.data)
        bm.free()


def unwrap(objs, margin, hidden, roomy) -> None:
    """Smart UV по игровой сетке (острова по изломам), выравнивание плотности, скрытые грани — мельче, упаковка."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        if 'GameUV' not in o.data.uv_layers:
            o.data.uv_layers.new(name='GameUV')
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=SHARP, island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')
    clamp_density(objs)
    for o in objs:
        hid = hidden.get(o.name, set())
        if not hid:
            continue
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        uvl = bm.loops.layers.uv['GameUV']
        room = roomy.get(o.name, set())
        for isl in uv_islands(bm, uvl, [bm.faces[i] for i in hid]):
            k = HIDDEN_ROOMY_SCALE if isl[0].index in room else HIDDEN_UV_SCALE
            loops = [l for f in isl for l in f.loops]
            c = sum((l[uvl].uv for l in loops), Vector((0, 0))) / len(loops)
            for l in loops:
                l[uvl].uv = c + (l[uvl].uv - c) * k
        bm.to_mesh(o.data)
        bm.free()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(rotate=True, rotate_method='AXIS_ALIGNED', scale=True, margin_method='FRACTION', margin=margin,
                            shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    harden_on_seams(objs)


def texel(objs, size) -> tuple:
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


def kabsch(a: np.ndarray, b: np.ndarray) -> Matrix:
    """Жёсткое преобразование, переводящее точки a в b (вершины одинаковых патронов)."""
    ca, cb = a.mean(0), b.mean(0)
    h = (a - ca).T @ (b - cb)
    u, _s, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1, 1, d]) @ u.T
    t = cb - r @ ca
    m = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            m[i][j] = float(r[i, j])
        m[i][3] = float(t[i])
    return m


def under(o, name: str) -> bool:
    p = o.parent
    while p is not None:
        if p.name == name:
            return True
        p = p.parent
    return False


def node_of(o) -> str:
    n = o.name
    if under(o, 'BoltCarrier • visual inspection control'):
        return 'Bolt'
    if under(o, 'Selector • inspection pivot'):
        return 'Selector'
    if under(o, 'CoverRelease • visual press control'):
        return 'CoverButton'
    if under(o, 'StockFold • left hinge control'):
        return 'StockFold'
    if under(o, 'MuzzleDevice'):
        return 'MuzzleAttachment'
    if under(o, 'Magazine'):
        return 'MagazineFollower' if n == 'Magazine_Follower' else 'Magazine'
    if n == 'Trigger • curved blade':
        return 'Trigger'
    if n == 'Magazine catch • paddle':
        return 'MagazineLatch'
    if n == 'Recoil spring • coil':
        return 'RecoilSpring'
    if n.startswith(('Dust cover', 'Receiver top rail', 'Rear sight')):
        return 'DustCover'
    return 'WeaponRoot'


# имя игровой детали по узлу и атласу
PART = {('WeaponRoot', 'Steel'): 'Body_Steel', ('WeaponRoot', 'Polymer'): 'Body_Polymer',
        ('DustCover', 'Steel'): 'DustCover_Steel', ('Bolt', 'Steel'): 'Bolt_Steel', ('Selector', 'Steel'): 'Selector_Steel',
        ('Trigger', 'Steel'): 'Trigger_Steel', ('MagazineLatch', 'Steel'): 'MagazineLatch_Steel',
        ('CoverButton', 'Steel'): 'CoverButton_Steel', ('StockFold', 'Steel'): 'StockFold_Steel',
        ('StockFold', 'Polymer'): 'StockFold_Polymer', ('MuzzleAttachment', 'Steel'): 'MuzzleDevice_Steel',
        ('RecoilSpring', 'Steel'): 'RecoilSpring_Steel', ('Magazine', 'Magazine'): 'Magazine_Body',
        ('Magazine', 'Steel'): 'Magazine_Steel', ('MagazineFollower', 'Magazine'): 'Magazine_Follower'}

# ---------------------------------------------------------------- исходник
bpy.context.preferences.use_preferences_save = False
sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
if sha != SRC_SHA:
    raise SystemExit(f'исходник изменился: {sha} (принят {SRC_SHA})')
bpy.ops.wm.open_mainfile(filepath=str(SRC))
S = bpy.context.scene
root = bpy.data.objects['VERAS54']
for k, v in (('Bolt pull', 0.0), ('Safety raised', False), ('Magazine removed', 0.0), ('Stock fold', 0.0),
             ('Cover button press', 0.0), ('Muzzle attachment', 0)):
    root[k] = v
bpy.data.objects['Magazine']['Rounds remaining'] = 30
for o in bpy.data.objects:
    o.update_tag()
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
supp = {o.name for c in bpy.data.collections if 'Suppressor' in c.name for o in c.all_objects}
sources = [o for o in bpy.data.objects if o.type == 'MESH' and o.name not in supp and not o.hide_render
           and not o.name.startswith('Magazine • loaded')]
lp = bpy.data.collections.new('VERAS54_GAME_LP')
S.collection.children.link(lp)

groups, budgets, devs_by_part = {}, {}, {}
for src in sorted(sources, key=lambda o: o.name):
    atlas = atlas_of_material(src.data.materials[0] if src.data.materials else None)
    part = PART[(node_of(src), atlas)]
    hp = evaluated_copy(src, dg, 'HP_' + src.name)
    before = tris(hp.data)
    bvh = BVHTree.FromPolygons([v.co.copy() for v in hp.data.vertices], [p.vertices[:] for p in hp.data.polygons])
    c = bpy.data.objects.new('LP_' + src.name, hp.data.copy())
    lp.objects.link(c)
    b = budget_for(src.name)
    after = simplify(c, b, organic=src.name in ORGANIC, protect=PROTECT.get(src.name))
    d = deviation(c, bvh)
    budgets[src.name] = [before, after, round(d[0], 3), round(d[1], 3)]
    devs_by_part.setdefault(part, []).append(d)
    groups.setdefault(part, []).append((src.name, c))
    bpy.data.meshes.remove(hp.data)
    log(part, src.name, before, '→', after, 'dev mm', round(d[0], 3), round(d[1], 3))

# Патрон: одна low-poly по патрону 1, остальные 29 — та же сетка на месте своего патрона (Кабш по вершинам исходника).
rounds = {}
for kind in ('case', 'projectile'):
    first = bpy.data.objects[f'Magazine • loaded {kind} 1']
    hp = evaluated_copy(first, dg, f'HP_round_{kind}')
    bvh = BVHTree.FromPolygons([v.co.copy() for v in hp.data.vertices], [p.vertices[:] for p in hp.data.polygons])
    c = bpy.data.objects.new(f'Round_{kind}', hp.data.copy())
    lp.objects.link(c)
    after = simplify(c, ROUND_BUDGET[kind], organic=False)
    d = deviation(c, bvh)
    budgets[f'Magazine • loaded {kind} 1'] = [tris(hp.data), after, round(d[0], 3), round(d[1], 3)]
    devs_by_part.setdefault(f'Round_{kind}', []).append(d)
    a = np.array([v.co[:] for v in hp.data.vertices])
    mats = {}
    for i in range(1, 31):
        o = bpy.data.objects[f'Magazine • loaded {kind} {i}']
        e = evaluated_copy(o, dg, 'tmp')
        b = np.array([v.co[:] for v in e.data.vertices])
        mats[i] = kabsch(a, b) if len(b) == len(a) else None
        if mats[i] is None:
            raise RuntimeError(f'патрон {i}: другая сетка')
        bpy.data.meshes.remove(e.data)
    rounds[kind] = (c, mats)
    bpy.data.meshes.remove(hp.data)
    log('round', kind, '→', after)

# Детали одной игровой части — одной сеткой
low, parts = {}, {}
for part, items in groups.items():
    # во время работы — с приставкой G_: имена исходника (Magazine_Body…) ещё заняты
    o = join([c for _n, c in items], 'G_' + part, lp)
    mark_sharp(o)
    low[part] = o
    parts[part] = [n for n, _c in items]
for kind, (c, _m) in rounds.items():
    mark_sharp(c)
    low[f'Round_{kind}'] = c
    parts[f'Round_{kind}'] = [f'Magazine • loaded {kind} {i}' for i in range(1, 31)]

cage = {}
for part, devs in devs_by_part.items():
    out_d = max(d[0] for d in devs)
    in_d = max(d[1] for d in devs)
    ext = min(3.0, max(0.3, out_d * 1.5 + 0.2))
    cage[part] = {'extrusion_mm': round(ext, 3), 'max_ray_mm': round(ext + in_d * 1.5 + 0.4, 3),
                  'dev_out_mm': round(out_d, 3), 'dev_in_mm': round(in_d, 3)}

# ---------------------------------------------------------------- скрытые грани
NODE = {'G_' + p: k[0] for k, p in PART.items()}
I4 = Matrix.Identity(4)
T = Matrix.Translation
spring_k = (SPRING_LEN - BOLT_TRAVEL) / SPRING_LEN
SPRING_BACK = T(SPRING_O) @ Matrix.Diagonal((spring_k, 1, 1, 1)) @ T(-SPRING_O)
FOLD = T(HINGE) @ Matrix.Rotation(math.radians(-180), 4, 'Z') @ T(-HINGE)
POSES = {
    'rest': {},
    'bolt_back': {'Bolt': T((-BOLT_TRAVEL, 0, 0)), 'RecoilSpring': SPRING_BACK},
    'mag_out': {'Magazine': T(MAG_OUT), 'MagazineFollower': T(MAG_OUT)},
    'stock_folded': {'StockFold': FOLD},
}
gun_low = [o for p, o in low.items() if not p.startswith('Round')]
hidden, contact, roomy = {}, {}, {}
for pose_name, pose in POSES.items():
    posed = [(o, pose.get(NODE[o.name], I4)) for o in gun_low]
    bvh = build_bvh(posed)
    for o, m in posed:
        vis, cont, room = visible_faces(o, m, bvh)
        hidden[o.name] = hidden.get(o.name, set(range(len(o.data.polygons)))) - vis
        contact[o.name] = contact.get(o.name, cont) & cont
        roomy[o.name] = roomy.get(o.name, set()) | room
    log('visibility pose', pose_name)
removed_hidden, dropped = 0, []
for o in list(gun_low):
    if len(hidden[o.name]) == len(o.data.polygons):
        # деталь не видна ни в одной позе (пружина под крышкой и т. п.) — в игру не идёт
        dropped.append(o.name[2:])
        removed_hidden += tris(o.data)
        low.pop(o.name[2:])
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    cont = contact[o.name] & hidden[o.name]
    if not cont:
        continue
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    mark = bm.faces.layers.int.new('lp_hidden')
    for i in hidden[o.name]:
        bm.faces[i][mark] = 2 if i in roomy[o.name] else 1
    drop = [bm.faces[i] for i in cont]
    removed_hidden += sum(len(f.verts) - 2 for f in drop)
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    hidden[o.name] = {f.index for f in bm.faces if f[mark]}
    roomy[o.name] = {f.index for f in bm.faces if f[mark] == 2}
    bm.faces.layers.int.remove(mark)
    bm.to_mesh(o.data)
    bm.free()
log('hidden contact faces removed, tris', removed_hidden, 'dropped parts', dropped)

# ---------------------------------------------------------------- развёртка и материалы
ATLAS_OF_PART = {p: a for (n, a), p in PART.items()}
ATLAS_OF_PART.update({'Round_case': 'Ammo', 'Round_projectile': 'Ammo'})
texels = {}
for atlas, size in ATLAS_SIZE.items():
    objs = [o for p, o in low.items() if ATLAS_OF_PART[p] == atlas]
    if not objs:
        continue
    unwrap(objs, UV_MARGIN_PX / size, hidden, roomy)
    texels[atlas] = texel(objs, size)
    mat = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    mat.use_nodes = True
    for o in objs:
        o.data.materials.append(mat)
    log('atlas', atlas, size, 'px/mm, uv area', texels[atlas])

# ---------------------------------------------------------------- узлы-пустышки и патроны
dg = bpy.context.evaluated_depsgraph_get()
bbox_c = lambda o: o.matrix_world @ (sum((Vector(c) for c in o.bound_box), Vector()) / 8)
src_loc = lambda n: bpy.data.objects[n].matrix_world.translation.copy()
pivots = {
    'WeaponRoot': Vector((0, 0, 0)), 'DustCover': Vector((0.110, 0, 0.025)),
    'Bolt': Vector((0.209, 0, 0.008)), 'Selector': src_loc('Selector • inspection pivot'),
    # ось спуска — у головок оси в коробке (v13), не прежняя 85/−33
    'Trigger': bbox_c(bpy.data.objects['Receiver • trigger pin heads']),
    'MagazineLatch': bbox_c(bpy.data.objects['Magazine catch • axle']),
    'CoverButton': Vector((0.013, 0, 0.030)), 'StockFold': HINGE.copy(),
    'MuzzleAttachment': src_loc('MuzzleDevice'), 'RecoilSpring': SPRING_O.copy(),
    'Magazine': src_loc('Magazine'), 'MagazineFollower': src_loc('Magazine_Follower'),
}
pivots['Trigger'].y = pivots['MagazineLatch'].y = 0.0
handle = bbox_c(bpy.data.objects['Bolt carrier • charging handle'])
notch = bpy.data.objects['Rear sight • windage bar with U-notch']
nme = notch.evaluated_get(dg).to_mesh()
npts = [notch.matrix_world @ v.co for v in nme.vertices]
notch.evaluated_get(dg).to_mesh_clear()
post = bpy.data.objects['Front sight • tapered centre post']
pme = post.evaluated_get(dg).to_mesh()
ppts = [post.matrix_world @ v.co for v in pme.vertices]
post.evaluated_get(dg).to_mesh_clear()
shoulder_z = max(p.z for p in npts)
markers = {
    # плечики U-прорези и вершина мушки — одна высота 57 мм над осью канала («ровная мушка»)
    'SightRear': [sum(p.x for p in npts) / len(npts), 0.0, shoulder_z],
    'SightFront': [sum(p.x for p in ppts) / len(ppts), 0.0, max(p.z for p in ppts)],
    'Muzzle': [0.606, 0.0, 0.0], 'MuzzleBrakeEnd': [0.705, 0.0, 0.0],
    'ChargingHandle': list(handle),
}
log('markers m', {k: [round(c, 4) for c in v] for k, v in markers.items()})

# Убрать исходную сцену: остаются игровые детали.
keep = {o.name for o in lp.all_objects}
for o in list(bpy.data.objects):
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c != lp:
        bpy.data.collections.remove(c)
for im in list(bpy.data.images):
    bpy.data.images.remove(im)
bpy.ops.outliner.orphans_purge(do_recursive=True)
for p, o in low.items():
    o.name = p
    o.data.name = p
NODE = {k[2:]: v for k, v in NODE.items()}
# патроны: сетка патрона 1 — у 30 объектов «Magazine • loaded case/projectile N» (матрица своего патрона)
round_objs = []
for kind, (c, mats) in rounds.items():
    for i in range(1, 31):
        o = bpy.data.objects.new(f'Magazine • loaded {kind} {i}', c.data)
        lp.objects.link(o)
        o.matrix_world = mats[i]
        round_objs.append(o.name)
    bpy.data.objects.remove(c, do_unlink=True)
    low.pop(f'Round_{kind}')

fp = sum(tris(o.data) for o in lp.all_objects if o.type == 'MESH' and not o.name.startswith('Magazine • loaded'))
round_tris = sum(tris(bpy.data.objects[f'Magazine • loaded {k} 1'].data) for k in ('case', 'projectile'))
record = dict(
    source=str(SRC), source_sha256=sha, axes='+X дуло, +Y влево стрелка, +Z вверх; начало — ось канала у заднего торца коробки; м',
    parts={p: dict(node=NODE[p], atlas=ATLAS_OF_PART[p], sources=parts[p]) for p in parts if p in low},
    rounds=dict(sources={k: f'Magazine • loaded {k} 1' for k in ('case', 'projectile')}, objects=round_objs,
                tris_per_round=round_tris),
    materials=MATNAME, atlas_size=ATLAS_SIZE, uv_margin_px=UV_MARGIN_PX, texel_px_mm=texels, cage=cage, budgets=budgets,
    removed_hidden_tris=removed_hidden, dropped_hidden_parts=dropped,
    triangles=dict(weapon_with_magazine=fp, rounds=round_tris * 30, total=fp + round_tris * 30),
    meshes={o.name: tris(o.data) for o in lp.all_objects if o.type == 'MESH' and not o.name.startswith('Magazine • loaded')},
    pivots_m={k: [round(c, 5) for c in v] for k, v in pivots.items()}, markers_m=markers,
    bolt_travel_m=BOLT_TRAVEL, bolt_safety_m=0.0729, magazine_out_m=list(MAG_OUT), spring=dict(origin=list(SPRING_O), length=SPRING_LEN),
    rest_pose='затвор закрыт, переводчик «АВ», магазин с 30 патронами, приклад разложен, дульный тормоз стоит')
(OUT / 'parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'VERAS54_Game_LP.blend'))
log('SAVED', OUT / 'VERAS54_Game_LP.blend', 'weapon+magazine', fp, 'rounds', round_tris * 30, 'total', fp + round_tris * 30)
