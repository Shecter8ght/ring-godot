"""ПМ «пошарпанный» v01 → игровая сетка от первого лица (lp/PM_Worn_LP.blend, parts.json, markers.json).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/build_lp.py

Источники только читаются: сборка 01_ПМ (пистолет с резьбовым хвостовиком ствола), магазин с патронами, патрон и
глушитель — отдельные файлы 02_. Координаты — сцены ПМ в покое (дуло −X, верх +Z); в оси игры переводит export.py.
Узлы: PM → Frame, Grip, Barrel, Slide(→Safety), Hammer, Trigger, SlideStop, MagCatch, Magazine(→Follower, Spring,
Rounds → Round_01..08; 1 — верхний), Suppressor; образцы патрона LP_Case/LP_Jacket/LP_Primer — только для запекания.
Бюджет (владелец 2026-10-20: «пистолет в руках должен изумительно читаться, 20–30 тысяч»): пистолет ~26 тыс.
треугольников, с магазином и патронами ~31 тыс., глушитель 2 тыс.; насечки, звезда щёчки, витки резьбы — в нормалях.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

FIT = json.loads((C.WORK / 'work/magazine_fit.json').read_text(encoding='utf-8'))
EXCLUDE = ('Suppressor', 'Highpoly |', 'Mount |', 'Reflex |', 'Magazine |', 'Magazine round', 'Studio |', 'Animation |',
           'Engraving |', 'Check |')
GRIP = ('Bakelite |', 'Grip checkering', 'Grip emblem', 'Lanyard |')
BARREL = ('Barrel |', 'Muzzle | recessed steel rim')
PIVOTS = {'Hammer': 'Hammer • pivot', 'Trigger': 'Trigger • pivot', 'Safety': 'Safety • pivot',
          'SlideStop': 'SlideStop • pivot', 'MagCatch': 'MagCatch • pivot'}
BUDGET = {'Slide': 9000, 'Frame': 7000, 'Grip': 3600, 'Barrel': 2400, 'Hammer': 900, 'Trigger': 600,
          'Safety': 900, 'SlideStop': 600, 'MagCatch': 900, 'MagBody': 1800, 'Follower': 220, 'Spring': 600,
          'Case': 170, 'Jacket': 110, 'Primer': 24, 'Suppressor': 2000}
# Насечка и звезда щёчек, насечка глушителя — только источники запекания (нормали), в игровой сетке их нет.
BAKE_ONLY = ('Grip checkering', 'Grip emblem', 'Highpoly |')
MARGIN = {'Steel': 0.004, 'Grip': 0.004, 'Magazine': 0.004, 'Ammo': 0.008, 'Suppressor': 0.004}
log = lambda *a: C.log('PM_LP', *a)  # noqa: E731


def chain(o) -> list[str]:
    out, p = [], o.parent
    while p:
        out.append(p.name)
        p = p.parent
    return out


def part_of(o) -> str | None:
    if o.type != 'MESH' or o.matrix_world.to_scale().x < 1e-5 or o.name.startswith(EXCLUDE):
        return None
    if o.hide_render and not o.name.startswith('Barrel | threaded'):
        return None
    if o.get('PM engraving helper') or (o.get('PM geometry helper') and o.name.startswith('ENGRAVE')):
        return None
    c = chain(o)
    if any(x.startswith(('Suppressor •', 'PM_OpticMount', 'PM_ReflexSight', 'Magazine •', 'Animation |')) for x in c):
        return None
    if o.name.startswith(GRIP):
        return 'Grip'
    if o.name.startswith(BARREL):
        return 'Barrel'
    for key, piv in PIVOTS.items():
        if piv in c:
            return key
    if 'Slide • translation' in c:
        return 'Slide'
    return 'Frame'


def points(o, dg) -> np.ndarray:
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    mw = np.array(eo.matrix_world)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    eo.to_mesh_clear()
    return co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]


def markers(dg) -> dict:
    """Метки в координатах сборки (м): мушка, целик (дно прорези), срез ствола (хвостовик), срез глушителя,
    оси деталей, крепление К-1 (начало и центр линзы) — для данных обвеса."""
    f = points(bpy.data.objects['Front sight | low rounded post'], dg)
    r = points(bpy.data.objects['Rear sight | beveled twin-ear blade'], dg)
    b = points(bpy.data.objects['Barrel | stepped cylindrical chamber and open bore'], dg)
    ext = points(bpy.data.objects['Barrel | threaded muzzle extension'], dg)
    axis_y, axis_z = float(np.median(b[:, 1])), float((b[:, 2].min() + b[:, 2].max()) / 2)
    notch = r[np.abs(r[:, 1]) < 0.0006]
    out = dict(SightFront=[float(f[:, 0].mean()), 0.0, float(f[:, 2].max())],
               SightRear=[float(r[:, 0].mean()), 0.0, float(notch[:, 2].max()) if len(notch) else float(r[:, 2].max())],
               Muzzle=[float(ext[:, 0].min()), axis_y, axis_z])
    sup = next((o for o in bpy.data.objects if o.name.startswith('Suppressor | eccentric front face')), None)
    if sup is not None:
        s = points(sup, dg)
        out['MuzzleSuppressed'] = [float(s[:, 0].min()), axis_y, axis_z]
    for k in ('Slide • translation', *PIVOTS.values()):
        out['pivot:' + k] = list(bpy.data.objects[k].matrix_world.translation)
    mount = bpy.data.objects.get('PM_OpticMount • asset root')
    lens = bpy.data.objects.get('Reflex | K1 curved aspheric lens')
    if mount is not None and lens is not None:
        lp = points(lens, dg)
        out['K1Mount'] = list(mount.matrix_world.translation)
        out['K1Lens'] = [float((lp[:, i].min() + lp[:, i].max()) / 2) for i in range(3)]
    return out


bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(C.SRC_PM))
S = bpy.context.scene
S.frame_set(1)
C.rest_pose()
dg = bpy.context.evaluated_depsgraph_get()
MARK = markers(dg)
log('markers', {k: [round(x * 1000, 2) for x in v] for k, v in MARK.items()})

parts: dict[str, list[str]] = {}
for o in bpy.data.objects:
    key = part_of(o)
    if key:
        parts.setdefault(key, []).append(o.name)
for key in BUDGET:
    if key in ('MagBody', 'Follower', 'Spring', 'Case', 'Jacket', 'Primer', 'Suppressor'):
        continue
    assert key in parts, f'нет исходных объектов детали {key}'
pivot_world = {k: bpy.data.objects[v].matrix_world.copy() for k, v in PIVOTS.items()}
pivot_world['Slide'] = bpy.data.objects['Slide • translation'].matrix_world.copy()
lp = bpy.data.collections.new('PM_GAME_LP')
S.collection.children.link(lp)
low = {}
for key, names in parts.items():
    geo = [n for n in names if not n.startswith(BAKE_ONLY)]
    copies = [C.evaluated_copy(bpy.data.objects[n], dg, f'{key}_{i}') for i, n in enumerate(geo)]
    o = C.join(copies, f'LP_{key}', lp)
    before = C.obj_tris(o)
    after = C.simplify(o, BUDGET[key], organic=(key == 'Grip'))
    low[key] = o
    log(key, len(names), 'objects', before, '->', after)

# Магазин с патронами (отдельный файл): посадка из work/magazine_fit.json.
tmp, mag_objs = C.load_objects(C.SRC_MAG, coll_name='MAG_TMP')
mroot = next(o for o in mag_objs if o.name.startswith('PM_magazine_loaded'))
mroot.matrix_world = Matrix([list(r) for r in FIT['new_root_matrix']])
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
mag_names = {'MagBody': [o.name for o in mag_objs if o.type == 'MESH' and o.name.startswith(('Magazine • continuous', 'Magazine • curved', 'Magazine • folded', 'Magazine • thin'))],
             'Follower': [o.name for o in mag_objs if o.name.startswith('Magazine • contoured follower')],
             'Spring': [o.name for o in mag_objs if o.name.startswith('Magazine • visible spring')]}
for key, names in mag_names.items():
    assert names, f'нет исходных объектов {key}'
    copies = [C.evaluated_copy(bpy.data.objects[n], dg, f'{key}_{i}') for i, n in enumerate(names)]
    o = C.join(copies, f'LP_{key}', lp)
    log(key, C.obj_tris(o), '->', C.simplify(o, BUDGET[key]))
    low[key] = o
    parts[key] = names
round_slots = []
for i in range(1, 9):
    e = next(o for o in mag_objs if o.name.startswith(f'Round_{i:02d}'))
    round_slots.append(e.matrix_world.copy())
# Патрон: одна развёртка на все патроны; позиции восьми — из снаряжённого магазина.
rtmp, round_objs = C.load_objects(C.SRC_ROUND, coll_name='ROUND_TMP')
dg = bpy.context.evaluated_depsgraph_get()
for key, prefix in (('Case', 'Case •'), ('Jacket', 'Jacket •'), ('Primer', 'Primer •')):
    src_o = next(o for o in round_objs if o.type == 'MESH' and o.name.startswith(prefix))
    o = C.join([C.evaluated_copy(src_o, dg, f'{key}_0')], f'LP_{key}', lp)
    log(key, C.obj_tris(o), '->', C.simplify(o, BUDGET[key]))
    low[key] = o
    parts[key] = [src_o.name]
# Глушитель (отдельный файл) на хвостовик ствола; насечка втулки — только источник запекания.
stmp, supp_objs = C.load_objects(C.SRC_SUPP, names=lambda n: n.startswith(('Suppressor |', 'Highpoly |')), coll_name='SUPP_TMP')
for o in supp_objs:
    o.parent = None
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
supp_names = [o.name for o in supp_objs if o.name.startswith('Suppressor |')]
copies = []
for i, o in enumerate(o for o in supp_objs if o.name.startswith('Suppressor |')):
    eo = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
    me.transform(C.SUPP_SEAT @ eo.matrix_world)
    copies.append(bpy.data.objects.new(f'Supp_{i}', me))
o = C.join(copies, 'LP_Suppressor', lp)
log('Suppressor', C.obj_tris(o), '->', C.simplify(o, BUDGET['Suppressor']))
low['Suppressor'] = o
# имена без суффиксов .NNN: при добавлении в сборку одноимённые объекты глушителя переименовались; запекание берёт
# глушитель из сборки (bake.py), где имена исходные
parts['Suppressor'] = [re.sub(r'\.\d{3}$', '', n) for n in supp_names] + ['Highpoly | visible crossed micro knurl']

# Развёртки по атласам и материалы.
for atlas, keys in C.ATLAS.items():
    objs = [low[k] for k in keys if k in low]
    C.unwrap(objs, MARGIN[atlas])
    mat = bpy.data.materials.get(C.MATNAME[atlas]) or bpy.data.materials.new(C.MATNAME[atlas])
    mat.use_nodes = True
    for ob in objs:
        ob.data.materials.append(mat)
    log('atlas', atlas, 'px/mm', C.texel_report(objs, C.SIZE[atlas]))

# Узлы игры: пустышки с осями поворота, детали — дочерние.
PM = C.empty('PM', lp)
PM['asset_id'] = 'wpn_hg_01'
PM['source'] = str(C.SRC_PM)
groups = {}
for key in ('Frame', 'Grip', 'Barrel', 'Slide', 'Hammer', 'Trigger', 'SlideStop', 'MagCatch'):
    w = pivot_world.get(key, Matrix.Identity(4))
    groups[key] = C.empty(key, lp, PM, Matrix.Translation(w.translation))
groups['Safety'] = C.empty('Safety', lp, groups['Slide'], Matrix.Translation(pivot_world['Safety'].translation))
groups['Magazine'] = C.empty('Magazine', lp, PM, Matrix([list(r) for r in FIT['new_root_matrix']]))
groups['Suppressor'] = C.empty('Suppressor', lp, PM, Matrix.Translation((-0.08065, 0.0, 0.11253)))
bpy.context.view_layer.update()
for key in ('Frame', 'Grip', 'Barrel', 'Slide', 'Hammer', 'Trigger', 'SlideStop', 'MagCatch', 'Safety', 'Suppressor'):
    low[key].name = f'{key}_Mesh'
    C.parent_keep(low[key], groups[key])
low['MagBody'].name = 'Magazine_Mesh'
C.parent_keep(low['MagBody'], groups['Magazine'])
low['Follower'].name = 'Follower_Mesh'
C.parent_keep(low['Follower'], groups['Magazine'])
low['Spring'].name = 'Spring_Mesh'
C.parent_keep(low['Spring'], groups['Magazine'])
rounds = C.empty('Rounds', lp, groups['Magazine'], groups['Magazine'].matrix_world.copy())
bpy.context.view_layer.update()
pieces = [low['Case'], low['Jacket'], low['Primer']]


def make_round(name: str, world: Matrix, with_jacket: bool = True):
    objs = []
    for p in pieces if with_jacket else [low['Case'], low['Primer']]:
        c = p.copy()
        c.data = p.data.copy()
        lp.objects.link(c)
        c.matrix_world = world @ p.matrix_world
        objs.append(c)
    C.activate(objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    r = bpy.context.view_layer.objects.active
    r.name = name
    r.data.name = name
    return r


# В снаряжённом магазине Round_01 — нижний; в игре 1 — верхний (как у ВЕРАС-54).
for n, world in enumerate(reversed(round_slots), start=1):
    r = make_round(f'Round_{n:02d}', world)
    C.parent_keep(r, rounds)
chamber = make_round('RoundChamber', Matrix.Identity(4))
C.parent_keep(chamber, groups['Barrel'])
jam = make_round('JamCase', Matrix.Identity(4), with_jacket=False)
C.parent_keep(jam, groups['Slide'])
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
meshes = {o.name: C.obj_tris(o) for o in lp.all_objects if o.type == 'MESH'}
pistol = sum(v for k, v in meshes.items() if k.endswith('_Mesh') and k not in ('Magazine_Mesh', 'Follower_Mesh', 'Spring_Mesh', 'Suppressor_Mesh'))
total = sum(v for k, v in meshes.items() if not k.startswith('LP_') and k not in ('RoundChamber', 'JamCase', 'Suppressor_Mesh'))
record = dict(source_pm=str(C.SRC_PM), source_magazine=str(C.SRC_MAG), source_round=str(C.SRC_ROUND), source_suppressor=str(C.SRC_SUPP),
              parts=parts, atlas={k: list(v) for k, v in C.ATLAS.items()}, materials=C.MATNAME, sizes=C.SIZE,
              triangles=dict(pistol=pistol, first_person_with_magazine=total, suppressor=meshes['Suppressor_Mesh']),
              meshes=meshes, rounds_order='Round_01 — верхний', magazine_fit=FIT['new_root_matrix'],
              suppressor_seat=[list(r) for r in C.SUPP_SEAT])
C.PARTS_FILE.parent.mkdir(parents=True, exist_ok=True)
C.PARTS_FILE.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
C.MARKERS_FILE.write_text(json.dumps(MARK, indent=1), encoding='utf-8', newline='\n')
bpy.ops.wm.save_as_mainfile(filepath=str(C.LP_FILE))
log('SAVED', C.LP_FILE, 'pistol', pistol, 'with magazine', total, 'suppressor', meshes['Suppressor_Mesh'])
