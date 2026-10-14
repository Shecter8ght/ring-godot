"""ПМ / КОРС-9 v11 → игровая сетка без прицела + настоящий магазин 60% → lp/PM_Game_LP_v01.blend.

blender --background --factory-startup --python-exit-code 1 --python build_lp.py
Исходники не меняются. Координаты — мировые сцены ПМ в покое (дуло к −X, верх +Z, мм → м);
перевод в оси игры — на экспорте. Узлы: PM → Frame, Grip, Barrel, Slide(→Safety), Hammer, Trigger,
SlideStop, MagCatch, Magazine(→Follower, Spring, Round_01..08; 1 — верхний), RoundChamber, JamCase.
Материалы-атласы: GAME • Steel • 100, GAME • Grip • 100 (три состояния), GAME • Magazine • 60,
GAME • Ammo • 60 (одно состояние). Связь игровых деталей с исходными объектами — lp/parts.json.
"""
from pathlib import Path
import json, math
import bpy, bmesh
from mathutils import Matrix, Vector

REV = Path(__file__).resolve().parents[1] / '_asset_src/pm_game'   # рабочая папка ассета (не в git)
LIB = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
SRC_PM = LIB / '17_Текстуры_v4_20_на_проверку/01_ПМ/PM_Textures_20_v04.blend'
SRC_MAG = LIB / '19_Магазины_и_патрон_60_v01/01_Модели/magazine_loaded_60_v02.blend'
SRC_ROUND = LIB / '19_Магазины_и_патрон_60_v01/01_Модели/cartridge_60_v01.blend'
FIT = json.loads((REV / 'work/magazine_fit.json').read_text(encoding='utf-8'))
OUT = REV / 'lp'
OUT.mkdir(exist_ok=True)
SHARP = math.radians(60)
EXCLUDE = ('Suppressor', 'Highpoly |', 'Mount |', 'Reflex |', 'Magazine |', 'Magazine round', 'Studio |')
GRIP = ('Bakelite |', 'Grip checkering', 'Grip emblem', 'Lanyard |')
PIVOTS = {'Hammer': 'Hammer • pivot', 'Trigger': 'Trigger • pivot', 'Safety': 'Safety • pivot',
          'SlideStop': 'SlideStop • pivot', 'MagCatch': 'MagCatch • pivot'}
# Бюджет треугольников игровой детали (вид от первого лица).
BUDGET = {'Slide': 6000, 'Frame': 4500, 'Grip': 2600, 'Barrel': 1400, 'Hammer': 700, 'Trigger': 420,
          'Safety': 700, 'SlideStop': 420, 'MagCatch': 700, 'MagBody': 1700, 'Follower': 220, 'Spring': 600,
          'Case': 170, 'Jacket': 110, 'Primer': 24}
ATLAS = {'Steel': ('Slide', 'Frame', 'Barrel', 'Hammer', 'Trigger', 'Safety', 'SlideStop', 'MagCatch'),
         'Grip': ('Grip',), 'Magazine': ('MagBody', 'Follower', 'Spring'), 'Ammo': ('Case', 'Jacket', 'Primer')}
MATNAME = {'Steel': 'GAME • Steel • 100', 'Grip': 'GAME • Grip • 100', 'Magazine': 'GAME • Magazine • 60', 'Ammo': 'GAME • Ammo • 60'}
log = lambda *a: print('PM_LP', *a, flush=True)


def chain(o):
    out, p = [], o.parent
    while p:
        out.append(p.name)
        p = p.parent
    return out


def part_of(o):
    if o.type != 'MESH' or o.hide_render or o.matrix_world.to_scale().x < 1e-5 or o.name.startswith(EXCLUDE):
        return None
    if o.get('PM engraving helper') or o.get('PM geometry helper') and o.name.startswith('ENGRAVE'):
        return None
    c = chain(o)
    if any(x.startswith(('Suppressor •', 'PM_OpticMount', 'PM_ReflexSight', 'Magazine •')) for x in c):
        return None
    if o.name.startswith(GRIP):
        return 'Grip'
    if o.name.startswith('Barrel |') or o.name.startswith('Muzzle | recessed steel rim'):
        return 'Barrel'
    for key, piv in PIVOTS.items():
        if piv in c:
            return key
    if 'Slide • translation' in c:
        return 'Slide'
    return 'Frame'


def tris(me):
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def evaluated_copy(o, dg, name):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(eo.matrix_world)
    ob = bpy.data.objects.new(name, me)
    return ob


def join(objs, name, coll):
    for o in objs:
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


def simplify(o, budget, organic=False):
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=2e-6)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    for m in list(o.modifiers):
        o.modifiers.remove(m)
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
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
    # Острые рёбра — раздельные нормали и швы развёртки (иначе запечённые нормали дают полосы).
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


def unwrap(objs, margin):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=SHARP, island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def texel_report(objs, size):
    import bmesh as _bm
    out = {}
    for o in objs:
        bm = _bm.new()
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


def empty(name, coll, parent=None, world=None):
    e = bpy.data.objects.new(name, None)
    coll.objects.link(e)
    e.empty_display_size = 0.006
    if parent is not None:
        e.parent = parent
    if world is not None:
        e.matrix_world = world
    return e


bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SRC_PM))
S = bpy.context.scene
S.frame_set(1)
rig = bpy.data.objects['PM_CONTROLS • select me']
for k in ('Slide', 'Hammer', 'Trigger', 'Safety', 'Magazine', 'MagCatch', 'SlideStop', 'Suppressor'):
    if k in rig.keys():
        rig[k] = 0.0
rig.update_tag()
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

parts = {}
for o in bpy.data.objects:
    key = part_of(o)
    if key:
        parts.setdefault(key, []).append(o.name)
pivot_world = {k: bpy.data.objects[v].matrix_world.copy() for k, v in PIVOTS.items()}
pivot_world['Slide'] = bpy.data.objects['Slide • translation'].matrix_world.copy()
lp = bpy.data.collections.new('PM_GAME_LP')
S.collection.children.link(lp)
low = {}
# Насечка и звезда щёчек — только источники запекания (нормали), в игровой сетке их нет.
BAKE_ONLY_SOURCES = ('Grip checkering', 'Grip emblem')
for key, names in parts.items():
    geo = [n for n in names if not n.startswith(BAKE_ONLY_SOURCES)]
    copies = [evaluated_copy(bpy.data.objects[n], dg, f'{key}_{i}') for i, n in enumerate(geo)]
    o = join(copies, f'LP_{key}', lp)
    before = tris(o.data)
    after = simplify(o, BUDGET[key], organic=(key == 'Grip'))
    low[key] = o
    log(key, len(names), 'objects', before, '->', after)

# Настоящий магазин и патроны (60%): посадка из work/magazine_fit.json.
with bpy.data.libraries.load(str(SRC_MAG), link=False) as (src, dst):
    dst.objects = list(src.objects)
tmp = bpy.data.collections.new('MAG_TMP')
S.collection.children.link(tmp)
for o in dst.objects:
    if o is not None and o.type not in ('CAMERA', 'LIGHT'):
        tmp.objects.link(o)
mroot = next(o for o in tmp.objects if o.name.startswith('PM_magazine_loaded'))
mroot.matrix_world = Matrix([list(r) for r in FIT['new_root_matrix']])
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
mag_names = {'MagBody': [o.name for o in tmp.objects if o.type == 'MESH' and o.name.startswith(('Magazine • continuous', 'Magazine • curved', 'Magazine • folded', 'Magazine • thin'))],
             'Follower': [o.name for o in tmp.objects if o.name.startswith('Magazine • contoured follower')],
             'Spring': [o.name for o in tmp.objects if o.name.startswith('Magazine • visible spring')]}
for key, names in mag_names.items():
    copies = [evaluated_copy(bpy.data.objects[n], dg, f'{key}_{i}') for i, n in enumerate(names)]
    o = join(copies, f'LP_{key}', lp)
    log(key, tris(o.data), '->', simplify(o, BUDGET[key]))
    low[key] = o
    parts[key] = names
# Патрон: одна развёртка на все патроны; позиции восьми — из снаряжённого магазина.
round_slots = []
for i in range(1, 9):
    e = next(o for o in tmp.objects if o.name.startswith(f'Round_{i:02d}'))
    round_slots.append(e.matrix_world.copy())
with bpy.data.libraries.load(str(SRC_ROUND), link=False) as (src, dst2):
    dst2.objects = list(src.objects)
rtmp = bpy.data.collections.new('ROUND_TMP')
S.collection.children.link(rtmp)
for o in dst2.objects:
    if o is not None and o.type == 'MESH':
        rtmp.objects.link(o)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for key, prefix in (('Case', 'Case •'), ('Jacket', 'Jacket •'), ('Primer', 'Primer •')):
    src_o = next(o for o in rtmp.objects if o.name.startswith(prefix))
    o = join([evaluated_copy(src_o, dg, f'{key}_0')], f'LP_{key}', lp)
    log(key, tris(o.data), '->', simplify(o, BUDGET[key]))
    low[key] = o
    parts[key] = [src_o.name]

# Развёртки по атласам и материалы.
for atlas, keys in ATLAS.items():
    objs = [low[k] for k in keys if k in low]
    unwrap(objs, 0.004 if atlas != 'Ammo' else 0.008)
    mat = bpy.data.materials.get(MATNAME[atlas]) or bpy.data.materials.new(MATNAME[atlas])
    mat.use_nodes = True
    for o in objs:
        o.data.materials.append(mat)
    log('atlas', atlas, 'px/mm', texel_report(objs, {'Steel': 2048, 'Grip': 1024, 'Magazine': 1024, 'Ammo': 512}[atlas]))

# Узлы игры: пустышки с осями поворота, детали — дочерние.
PM = empty('PM', lp)
PM['asset_id'] = 'wpn_hg_01'
PM['source'] = str(SRC_PM)
groups = {}
for key in ('Frame', 'Grip', 'Barrel', 'Slide', 'Hammer', 'Trigger', 'SlideStop', 'MagCatch'):
    w = pivot_world.get(key, Matrix.Identity(4))
    w = Matrix.Translation(w.translation)
    groups[key] = empty(key, lp, PM, w)
groups['Safety'] = empty('Safety', lp, groups['Slide'], Matrix.Translation(pivot_world['Safety'].translation))
groups['Magazine'] = empty('Magazine', lp, PM, Matrix([list(r) for r in FIT['new_root_matrix']]))
bpy.context.view_layer.update()


def parent_keep(o, parent):
    w = o.matrix_world.copy()
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
    o.matrix_world = w


for key in ('Frame', 'Grip', 'Barrel', 'Slide', 'Hammer', 'Trigger', 'SlideStop', 'MagCatch', 'Safety'):
    low[key].name = f'{key}_Mesh'
    parent_keep(low[key], groups[key])
low['MagBody'].name = 'Magazine_Mesh'
parent_keep(low['MagBody'], groups['Magazine'])
fol = empty('Follower', lp, groups['Magazine'], Matrix.Translation(low['Follower'].matrix_world.translation))
low['Follower'].name = 'Follower_Mesh'
parent_keep(low['Follower'], groups['Magazine'])
low['Spring'].name = 'Spring_Mesh'
parent_keep(low['Spring'], groups['Magazine'])
rounds = empty('Rounds', lp, groups['Magazine'], groups['Magazine'].matrix_world.copy())
bpy.context.view_layer.update()
pieces = [low['Case'], low['Jacket'], low['Primer']]


def make_round(name, world, with_jacket=True):
    objs = []
    for p in pieces if with_jacket else [low['Case'], low['Primer']]:
        c = p.copy()
        c.data = p.data.copy()
        lp.objects.link(c)
        c.matrix_world = world @ p.matrix_world
        objs.append(c)
    bpy.ops.object.select_all(action='DESELECT')
    for c in objs:
        c.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    r = bpy.context.view_layer.objects.active
    r.name = name
    r.data.name = name
    return r


# В снаряжённом магазине Round_01 — нижний; в игре 1 — верхний (как у ВЕРАС-54).
for n, world in enumerate(reversed(round_slots), start=1):
    r = make_round(f'Round_{n:02d}', world)
    parent_keep(r, rounds)
chamber = make_round('RoundChamber', Matrix.Identity(4))
parent_keep(chamber, groups['Barrel'])
jam = make_round('JamCase', Matrix.Identity(4), with_jacket=False)
parent_keep(jam, groups['Slide'])
chamber.hide_render = jam.hide_render = False
chamber['place_later'] = jam['place_later'] = 'Положение задаётся на этапе вьюмодели (патронник / окно выброса)'
for p in pieces:
    p.hide_render = True
    p.hide_set(True)
    p['bake_only'] = 'Образец патрона: по нему запекается атлас Ammo (все патроны с той же развёрткой)'

# Убрать исходную сцену: остаются только игровые узлы и образцы патрона.
keep = set(o.name for o in lp.all_objects)
for o in list(bpy.data.objects):
    if o.name not in keep:
        bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    if c != lp:
        bpy.data.collections.remove(c)
bpy.ops.outliner.orphans_purge(do_recursive=True)
total = sum(tris(o.data) for o in lp.all_objects if o.type == 'MESH' and not o.get('bake_only'))
record = dict(source_pm=str(SRC_PM), source_magazine=str(SRC_MAG), source_round=str(SRC_ROUND), parts=parts,
              atlas=ATLAS, materials=MATNAME, triangles_first_person=total,
              meshes={o.name: tris(o.data) for o in lp.all_objects if o.type == 'MESH'},
              rounds_order='Round_01 — верхний', magazine_fit=FIT['new_root_matrix'])
(OUT / 'parts.json').write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'PM_Game_LP_v01.blend'))
log('SAVED', OUT / 'PM_Game_LP_v01.blend', 'tris', total)
