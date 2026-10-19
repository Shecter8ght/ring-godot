"""Магазин ВЕРАС-54 → игровая сетка (low-poly со своей развёрткой), как game_lp.py автомата v13.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_mags/mags_game_lp.py -- m45|d60
→ _asset_src/veras54_game_mags/<m45|d60>/lp.blend + parts.json (не в git). Исходник (SHA-256 сверяется) не меняется.

Узлы: Magazine — корпус (у 45: с донцем и направляющими индикатора; у барабана: с ободом крышки, ступицей и кнопкой),
MagazineFollower — подаватель (у 45), DrumKey — ключ завода (у барабана; поворачивается вокруг оси ступицы),
Round_NN — патроны (01 — верхний): у губок два верхних — подробная сетка, остальные внутри корпуса — дешёвая (не видны
ни в одном ракурсе: игра показывает патроны сверху по счёту, нижние всегда закрыты корпусом). Сетка патрона общая.
Скрытые прижатые грани удаляются, скрытые просторные — мельче на развёртке; бюджеты — в mags_game_common.py.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mags_game_common as C  # noqa: E402

MID = sys.argv[sys.argv.index('--') + 1]
M = C.MAGS[MID]
OUT = C.work(MID)
SHARP = math.radians(M.get('sharp_deg', 60))     # жёсткие рёбра и швы: у 45-го 40° — фаски ячеек не сглаживаются
UV_SLAB = 0.15
CONTACT = 0.004
ROOMY = 0.008
HIDDEN_UV_SCALE = 0.1
HIDDEN_ROOMY_SCALE = 0.5
HARD_ON_SEAM = math.radians(30)
UV_MARGIN_PX = 12
log = lambda *a: print('MAGS_LP', MID, *a, flush=True)


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
    return bpy.data.objects.new(name, me)


def strip(me) -> None:
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    for a in [a.name for a in me.color_attributes]:
        me.color_attributes.remove(me.color_attributes[a])
    for a in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if a in me.attributes:
            me.attributes.remove(me.attributes[a])


def collapse_to(o, target: int, organic: bool) -> None:
    for _ in range(10):
        n = tris(o.data)
        if n <= target * 1.03:
            break
        d = o.modifiers.new('budget', 'DECIMATE')
        d.ratio = max(target / n, 1 / 8) if organic else max(1e-5, target / n)
        d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=d.name)


def slab_cut(o) -> None:
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
        d.delimit = {'NORMAL'}
        bpy.ops.object.modifier_apply(modifier=d.name)
        t = o.modifiers.new('tri', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=t.name)
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
    for p in [v.co.copy() for v in me.vertices] + [p.center.copy() for p in me.polygons]:
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


def build_bvh(objs):
    verts, polys = [], []
    for o in objs:
        base = len(verts)
        verts += [v.co.copy() for v in o.data.vertices]
        polys += [[base + i for i in pl.vertices] for pl in o.data.polygons]
    return BVHTree.FromPolygons(verts, polys)


def visible_faces(o, bvh) -> tuple:
    """Видимые грани (хоть один луч из полусферы уходит наружу), прижатые (все лучи упираются ближе CONTACT), просторные."""
    me = o.data
    vis, contact, roomy = set(), set(), set()
    for pl in me.polygons:
        n = pl.normal.normalized()
        c = pl.center
        starts = [c] + [c + (me.vertices[i].co - c) * 0.85 for i in pl.vertices]
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


def island_density(isl, uvl):
    a3 = sum(f.calc_area() for f in isl)
    a2 = 0.0
    for f in isl:
        uv = [l[uvl].uv for l in f.loops]
        for i in range(1, len(uv) - 1):
            a2 += abs((uv[i] - uv[0]).cross(uv[i + 1] - uv[0])) / 2
    return (math.sqrt(a2 / a3) if a3 > 1e-12 else float('inf')), a3


def scale_island(isl, uvl, k):
    loops = [l for f in isl for l in f.loops]
    c = sum((l[uvl].uv for l in loops), Vector((0, 0))) / len(loops)
    for l in loops:
        l[uvl].uv = c + (l[uvl].uv - c) * k


def clamp_density(objs) -> None:
    """Острова с плотностью текселей выше медианной вдвое (вырожденные) — к медиане."""
    rows = []
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        rows += [island_density(isl, uvl) for isl in uv_islands(bm, uvl, list(bm.faces))]
        bm.free()
    finite = sorted((d, a) for d, a in rows if math.isfinite(d))
    half, acc, median = sum(a for _d, a in finite) / 2, 0.0, 1.0
    for d, a in finite:
        acc += a
        if acc >= half:
            median = d
            break
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv['GameUV']
        for isl in uv_islands(bm, uvl, list(bm.faces)):
            d, _a = island_density(isl, uvl)
            if d > median * 2.0:
                scale_island(isl, uvl, median / d if math.isfinite(d) else 1e-3)
        bm.to_mesh(o.data)
        bm.free()


def harden_on_seams(objs) -> None:
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
            scale_island(isl, uvl, HIDDEN_ROOMY_SCALE if isl[0].index in room else HIDDEN_UV_SCALE)
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


# ---------------------------------------------------------------- исходник
bpy.context.preferences.use_preferences_save = False
sha = hashlib.sha256(Path(M['src']).read_bytes()).hexdigest()
if sha != M['sha']:
    raise SystemExit(f'исходник изменился: {sha} (принят {M["sha"]})')
bpy.ops.wm.open_mainfile(filepath=str(M['src']))
S = bpy.context.scene
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
lum = bpy.data.materials.get('13 • Luminous count marks')
if lum:
    p = next(n for n in lum.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    log('luminous emission', tuple(round(c, 3) for c in p.inputs['Emission Color'].default_value),
        round(p.inputs['Emission Strength'].default_value, 3))
lp = bpy.data.collections.new('MAG_GAME_LP')
S.collection.children.link(lp)

groups, budgets, devs_by_part = {}, {}, {}
for part, names in M['parts'].items():
    for n in names:
        src = bpy.data.objects[n]
        hp = evaluated_copy(src, dg, 'HP_' + n)
        before = tris(hp.data)
        bvh = BVHTree.FromPolygons([v.co.copy() for v in hp.data.vertices], [p.vertices[:] for p in hp.data.polygons])
        c = bpy.data.objects.new('LP_' + n, hp.data.copy())
        lp.objects.link(c)
        b = M['budget'].get(n, M['budget'].get(C.base_name(n), 48))
        after = simplify(c, b, organic=n in M['organic'])
        d = deviation(c, bvh)
        budgets[n] = [before, after, round(d[0], 3), round(d[1], 3)]
        devs_by_part.setdefault(part, []).append(d)
        groups.setdefault(part, []).append(c)
        bpy.data.meshes.remove(hp.data)
        log(part, n, before, '→', after, 'dev mm', round(d[0], 3), round(d[1], 3))

# Патрон: подробная и дешёвая сетки по патрону 1 (гильза + пуля одной сеткой), остальные — на месте своего патрона.
rounds_mats = {}
round_mesh = {}
pre = M['prefix']
first = {k: bpy.data.objects[f'{pre} • {k} 1'] for k in ('case', 'projectile')}
hp_first = {k: evaluated_copy(o, dg, f'HP_round_{k}') for k, o in first.items()}
centre1 = sum((v.co for v in hp_first['case'].data.vertices), Vector()) / len(hp_first['case'].data.vertices)
for level, budget in (('hi', C.ROUND_HI), ('lo', C.ROUND_LO)):
    pieces = []
    for k in ('case', 'projectile'):
        hp = hp_first[k]
        bvh = BVHTree.FromPolygons([v.co.copy() for v in hp.data.vertices], [p.vertices[:] for p in hp.data.polygons])
        c = bpy.data.objects.new(f'round_{level}_{k}', hp.data.copy())
        lp.objects.link(c)
        after = simplify(c, budget[k], organic=False)
        d = deviation(c, bvh)
        budgets[f'{pre} • {k} 1 ({level})'] = [tris(hp.data), after, round(d[0], 3), round(d[1], 3)]
        devs_by_part.setdefault(f'Round_{level}', []).append(d)
        pieces.append(c)
    o = join(pieces, f'Round_{level}', lp)
    o.data.transform(Matrix.Translation(-centre1))       # начало сетки — середина гильзы патрона 1
    round_mesh[level] = o
a_case = np.array([v.co[:] for v in hp_first['case'].data.vertices])
for i in range(1, M['rounds'] + 1):
    e = evaluated_copy(bpy.data.objects[f'{pre} • case {i}'], dg, 'tmp')
    b = np.array([v.co[:] for v in e.data.vertices])
    if len(b) != len(a_case):
        raise RuntimeError(f'патрон {i}: другая сетка')
    rounds_mats[i] = kabsch(a_case, b) @ Matrix.Translation(centre1)
    bpy.data.meshes.remove(e.data)
for hp in hp_first.values():
    bpy.data.meshes.remove(hp.data)

low = {}
for part, objs in groups.items():
    o = join(objs, 'G_' + part, lp)
    mark_sharp(o)
    low[part] = o
for level, o in round_mesh.items():
    mark_sharp(o)

cage = {}
for part, devs in devs_by_part.items():
    out_d = max(d[0] for d in devs)
    in_d = max(d[1] for d in devs)
    ext = min(3.0, max(0.3, out_d * 1.5 + 0.2))
    cage[part] = {'extrusion_mm': round(ext, 3), 'max_ray_mm': round(ext + in_d * 1.5 + 0.4, 3),
                  'dev_out_mm': round(out_d, 3), 'dev_in_mm': round(in_d, 3)}

# ---------------------------------------------------------------- скрытые грани (сам магазин, без патронов)
bvh = build_bvh(list(low.values()))
hidden, roomy, removed = {}, {}, 0
for part, o in low.items():
    if part != 'Magazine':
        continue        # подаватель и ключ ходят: в другом положении «скрытые» грани видны
    vis, cont, room = visible_faces(o, bvh)
    hid = set(range(len(o.data.polygons))) - vis
    drop_ids = cont & hid
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    mark = bm.faces.layers.int.new('lp_hidden')
    for i in hid:
        bm.faces[i][mark] = 2 if i in room else 1
    drop = [bm.faces[i] for i in drop_ids]
    removed += sum(len(f.verts) - 2 for f in drop)
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    hidden[o.name] = {f.index for f in bm.faces if f[mark]}
    roomy[o.name] = {f.index for f in bm.faces if f[mark] == 2}
    bm.faces.layers.int.remove(mark)
    bm.to_mesh(o.data)
    bm.free()
    log('visibility', part, 'hidden', len(hid), 'contact removed', len(drop_ids))
# дешёвый патрон не виден никогда — весь мелко на развёртке
hidden[round_mesh['lo'].name] = set(range(len(round_mesh['lo'].data.polygons)))

# ---------------------------------------------------------------- развёртка и материал
objs = list(low.values()) + [round_mesh['hi'], round_mesh['lo']]
unwrap(objs, UV_MARGIN_PX / M['size'], hidden, roomy)
tex = texel(objs, M['size'])
mat = bpy.data.materials.get(C.matname(MID)) or bpy.data.materials.new(C.matname(MID))
mat.use_nodes = True
for o in objs:
    o.data.materials.append(mat)
log('atlas', M['atlas'], M['size'], 'px/mm, uv area', tex)

# ---------------------------------------------------------------- узлы
pivots = {'Magazine': Vector((0, 0, 0))}
if 'MagazineFollower' in low:
    f = bpy.data.objects[M['parts']['MagazineFollower'][0]]
    pivots['MagazineFollower'] = f.matrix_world.translation.copy()
if 'DrumKey' in low:
    pivots['DrumKey'] = Vector(C.HUB_FACE_MM) * 0.001

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
for part, o in low.items():
    o.name = part
    o.data.name = part
    # начало детали — её ось (подаватель / ключ); вершины не двигаются в мире
    pv = pivots[part]
    o.data.transform(Matrix.Translation(-pv))
    o.matrix_world = Matrix.Translation(pv)
round_objs = []
for i in range(1, M['rounds'] + 1):
    level = 'hi' if i <= C.ROUNDS_HI else 'lo'
    o = bpy.data.objects.new(f'Round_{i:02d}', round_mesh[level].data)
    lp.objects.link(o)
    o.matrix_world = rounds_mats[i]
    round_objs.append(o.name)
for o in round_mesh.values():
    bpy.data.objects.remove(o, do_unlink=True)
round_mesh_names = {'hi': 'Round_hi', 'lo': 'Round_lo'}

body_tris = {p: tris(o.data) for p, o in low.items()}
rt = {lv: tris(bpy.data.meshes[n]) for lv, n in round_mesh_names.items()}
total_rounds = rt['hi'] * min(C.ROUNDS_HI, M['rounds']) + rt['lo'] * max(0, M['rounds'] - C.ROUNDS_HI)
record = dict(
    magazine=MID, title=M['title'], item=M['item'], source=str(M['src']), source_sha256=sha,
    axes='+X к дулу, +Y влево стрелка, +Z вверх; начало — точка крепления магазина (в автомате — (0,179; 0; −0,037) м от VERAS54)',
    parts={p: dict(sources=M['parts'][p], pivot_m=[round(c, 5) for c in pivots[p]]) for p in low},
    rounds=dict(count=M['rounds'], detailed=C.ROUNDS_HI, tris_hi=rt['hi'], tris_lo=rt['lo'], objects=round_objs,
                sources={k: f'{pre} • {k} 1' for k in ('case', 'projectile')}),
    material=C.matname(MID), atlas=M['atlas'], atlas_size=M['size'], uv_margin_px=UV_MARGIN_PX, texel_px_mm=tex,
    cage=cage, budgets=budgets, removed_hidden_tris=removed,
    triangles=dict(parts=body_tris, rounds=total_rounds, total=sum(body_tris.values()) + total_rounds))
(OUT / 'parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'lp.blend'))
log('SAVED', OUT / 'lp.blend', 'parts', body_tris, 'rounds', total_rounds, 'total', record['triangles']['total'])
