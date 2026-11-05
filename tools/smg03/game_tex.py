"""ИЗЛОМ-45, текстуры этап 1 на игровой сетке (владелец 2026-11-05: текстурировать low-poly) — заготовки для Painter.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/smg03/game_tex.py -- [fbx] [maps]
→ _asset_src/smg03/tex/ (не в git):
  SMG03_low.fbx   — игровая сетка: материал = атлас (набор текстур Painter: Upper, Lower, Steel, Stock, Mag13, Mag30), узел игры
                    поделён по слотам отделки finish-spec.json — сетка «<узел>__<слот>_low» (маска слоя по имени сетки);
  SMG03_high.fbx  — принятая high-poly v06 (с надписями, знаками, шагренью) теми же группами: «<узел>__<слот>_high» — Painter
                    печёт нормаль, AO, кривизну, толщину с high-poly с отбором по имени сетки (подвижные детали в покое
                    вплотную друг к другу: без отбора лучи с затвора ловили бы корпус);
  meshes.json     — набор → слот → сетки, отделка слота (для sp_finish.build_set);
  Upper_maps.npz, Lower_maps.npz, marks.json — положение и нормаль в каждом пикселе развёртки верха и низа корпуса
                    и контуры красных меток: по ним tools/smg03/tex_masks.py считает маску красной заливки.
Корпус (v2, владелец 05.11: «Два атласа 4K») — два узла-атласа по линии шва (game_lp.py, receiver_seam.py); high-poly
корпуса делится тем же правилом, чтобы у каждой половины была своя пара (одинаковые копии high-poly внахлёст затеняли бы
друг друга в AO).
Магазины в обоих FBX опущены вниз (у каждого свой сдвиг): это отдельные предметы игры, AO от шахты и друг от друга им не
нужен. Развёртка — GameUV игровой сетки (tools/smg03/game_lp.py), в FBX она одна и первая.
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/smg03'))
from ar15.game_lp import evaluated_copy, tris  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402
import receiver_seam  # noqa: E402

SRC = Path('E:/Models Blender/WEAPONS/Vector — модель/ПП-Vector_геометрия_v06.blend')
SPEC = Path('E:/Models Blender/WEAPONS/Vector — модель/finish-spec.json')
LP = ROOT / '_asset_src/smg03/game/lp/SMG03_Game_LP.blend'
OUT = ROOT / '_asset_src/smg03/tex'
# половины корпуса: атлас игровой сетки → слот finish-spec.json; high-poly делится со сдвигом точки грани внутрь, мм
RECEIVER_HALF = {'Upper': 'receiver_upper', 'Lower': 'receiver_lower'}
HP_INSET_MM = 0.3
RED_SETS = ('Upper', 'Lower')
MAG_SHIFT = {'Mag13': (0.0, 0.0, -0.35), 'Mag30': (0.0, 0.0, -0.75)}
log = lambda *a: print('SMG03_TEX', *a, flush=True)


def slot_table():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    return spec, [(s['id'], s['parts'], s['finish']) for s in spec['slots']]


def slot_of(part, table, atlas=None):
    if part == 'Receiver':
        return RECEIVER_HALF[atlas]
    for sid, pats, _ in table:
        if any(fnmatch.fnmatchcase(part, p) for p in pats):
            return sid
    raise KeyError(f'деталь {part} не попала ни в один слот finish-spec.json')


def bvh_of(o):
    me = o.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [list(p.vertices) for p in me.polygons])


def face_parts(o, high):
    """Номер детали исходника у каждой грани: атрибут hp_part (game_lp.py после 05.11) или ближайшая поверхность среди
    деталей узла — по центру и вершинам грани (сумма расстояний: грань у стыка двух деталей уходит к своей)."""
    me = o.data
    n = len(me.polygons)
    names = list(o['hp'])
    if 'hp_part' in me.attributes:
        v = np.zeros(n, dtype=np.int32)
        me.attributes['hp_part'].data.foreach_get('value', v)
        return v, 'атрибут'
    if len(names) == 1:
        return np.zeros(n, dtype=np.int32), 'одна деталь'
    trees = [bvh_of(high[nm]) for nm in names]
    out = np.zeros(n, dtype=np.int32)
    for p in me.polygons:
        pts = [Vector(p.center)] + [me.vertices[i].co for i in p.vertices]
        best, bi = 1e9, 0
        for i, t in enumerate(trees):
            d = 0.0
            for q in pts:
                hit = t.find_nearest(q)
                d += hit[3] if hit[3] is not None else 1.0
            if d < best:
                best, bi = d, i
        out[p.index] = bi
    return out, 'ближайшая деталь'


def split_faces(o, keep, name, coll):
    """Копия узла с гранями keep (маска по граням); развёртка — только GameUV (первая и единственная). Нормали — тем же
    правилом, что у игровой сетки (game_lp.weighted_normals): слоты — целые детали, их оболочки не связаны с соседними,
    и нормали куска совпадают с нормалями узла в игре."""
    me = o.data.copy()
    me.name = name
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep[f.index]], context='FACES')
    bm.to_mesh(me)
    bm.free()
    for uv in [u.name for u in me.uv_layers if u.name != 'GameUV']:
        me.uv_layers.remove(me.uv_layers[uv])
    me.uv_layers['GameUV'].name = 'UVMap'
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    import game_lp
    game_lp.weighted_normals(ob)
    return ob


def half_copy(src, upper, name, coll):
    """Половина high-poly корпуса по линии шва (receiver_seam.is_upper со сдвигом HP_INSET_MM)."""
    me = src.data.copy()
    sides = receiver_seam.face_sides(me, HP_INSET_MM)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if sides[f.index] != upper], context='FACES')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def material(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    return m


def set_material(o, name):
    o.data.materials.clear()
    o.data.materials.append(material(name))
    for p in o.data.polygons:
        p.material_index = 0


def high_normals(o, angle_deg: float = 60.0):
    """Нормали high-poly для запекания: рёбра круче angle (стенки букв, канавок, вырезов — 90°) — жёсткие, затем по
    площади граней. Свои нормали исходника гнулись у стенок букв, и вокруг надписей в карте шёл слабый веер полос
    (05.11); фаски в 2 сегмента (45°) остаются гладкими."""
    import math
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
    # физический разрез этих рёбер (bmesh.ops.split_edges) пробовали 05.11: карта верха не изменилась ни на пиксель,
    # а низ корпуса запёкся пустым (нормаль плоская, AO чёрный) — не делать
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    m = o.modifiers.new('wn', 'WEIGHTED_NORMAL')
    m.mode = 'FACE_AREA'
    m.weight = 100
    m.keep_sharp = True
    m.thresh = 0.01
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=m.name)


def keep_normals(me):
    """Свои нормали high-poly (по площади граней — lib.weighted: плоское плоское рядом с фасками) — в атрибут углов:
    bmesh хранит свои нормали в пространствах углов, и после удаления граней (половины корпуса) или склейки они могли
    исказиться. Возвращает их restore_normals после склейки (join_copies)."""
    n = np.zeros(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get('vector', n)
    a = me.attributes.get('keep_normal') or me.attributes.new('keep_normal', 'FLOAT_VECTOR', 'CORNER')
    a.data.foreach_set('vector', n)


def restore_normals(me):
    """Нормали углов из атрибута keep_normal — снова своими нормалями сетки (их FBX и передаёт Painter)."""
    a = me.attributes.get('keep_normal')
    if a is None:
        return
    n = np.zeros(len(me.loops) * 3, np.float32)
    a.data.foreach_get('vector', n)
    me.attributes.remove(a)
    for p in me.polygons:
        p.use_smooth = True
    me.normals_split_custom_set(n.reshape(-1, 3).tolist())


def join_copies(objs, name, coll):
    """Копии деталей high-poly одной группы — в одну сетку (у Painter пара low/high — по имени)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    for o in objs:
        bm.from_mesh(o.data)
    # треугольниками — здесь, в Blender: плоскость с вырезанными буквами — многоугольник с перемычками, и Painter при
    # чтении FBX бил его на треугольники по-своему, затягивая часть букв («ИЗЛ» слева не запекалась, 05.11)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY',
                          ngon_method='BEAUTY')
    bm.to_mesh(me)
    bm.free()
    restore_normals(me)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def export_fbx(objs, path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, apply_unit_scale=True,
                             apply_scale_options='FBX_SCALE_UNITS', mesh_smooth_type='FACE', use_mesh_modifiers=False,
                             axis_forward='-Z', axis_up='Y', object_types={'MESH'}, bake_anim=False)


def build_fbx():
    """Пары low/high по слотам, FBX для Painter и meshes.json; возвращает сетки наборов верха и низа корпуса (для карт
    масок) — {набор: [сетки]}."""
    spec, table = slot_table()
    finish_of = {sid: fin for sid, _, fin in table}
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    hp = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
    with bpy.data.libraries.load(str(LP)) as (src, dst):
        dst.objects = list(src.objects)
    lows = [o for o in dst.objects if o is not None and o.type == 'MESH' and 'atlas' in o]
    work = bpy.data.collections.new('TEX_WORK')
    bpy.context.scene.collection.children.link(work)
    for o in lows:
        work.objects.link(o)
    need = sorted({n for o in lows for n in o['hp']})
    high = {n: evaluated_copy(hp[n], 'hpc_' + n, work) for n in need}
    for o in high.values():
        high_normals(o)
        keep_normals(o.data)
    log('деталей high-poly', len(high), 'треугольников', sum(tris(o.data) for o in high.values()))
    halves = {a: half_copy(high['Receiver'], a == 'Upper', 'hpc_Receiver_' + a, work) for a in RECEIVER_HALF}
    log('high-poly корпуса по шву:', {a: tris(o.data) for a, o in halves.items()})
    lo_coll = bpy.data.collections.new('LOW')
    hi_coll = bpy.data.collections.new('HIGH')
    bpy.context.scene.collection.children.link(lo_coll)
    bpy.context.scene.collection.children.link(hi_coll)
    meshes = {}
    low_out, high_out = [], []
    for o in sorted(lows, key=lambda x: x.name):
        atlas = o['atlas']
        idx, how = face_parts(o, high)
        names = list(o['hp'])
        slots = [slot_of(n, table, atlas) for n in names]
        face_slot = np.array([slots[i] for i in idx])
        for sid in sorted(set(slots)):
            keep = face_slot == sid
            if not keep.any():
                continue
            # у исходника есть свой «Receiver» — игровой при загрузке получает «.001»: имя узла — без суффикса
            key = re.sub(r'[.]\d{3}$', '', o.name) + '__' + sid
            # «_low» внутри имени: Painter находил суффикс в «_Lower» / «_lower» и не сводил пару low/high — низ корпуса
            # и площадка задержки запекались пустыми (нормаль плоская, AO чёрный; 05.11)
            key = re.sub('lower', 'bottom', re.sub('Lower', 'Bottom', key))
            lo = split_faces(o, keep, key + '_low', lo_coll)
            set_material(lo, atlas)
            # копии внахлёст (одинаковое мелкое) — за квадрат развёртки: Painter печёт только 0…1, копия берёт карту
            # своего оригинала (в игре развёртка та же, без сдвига)
            shifted = kit_uv.shift_stack_copies([lo], 1.0, uv='UVMap')
            # деталь исходника — один раз: верх корпуса в игре склеен из кусков развёртки (game_lp.chunks_x), и у узла
            # 'Receiver' в списке hp пять раз — high-poly вкладывалась пятью копиями одна в другую (FBX v2: «шахматка»,
            # надпись слева пропадала, AO верха затенял сам себя)
            parts = list(dict.fromkeys(n for n, s in zip(names, slots) if s == sid))
            hi = join_copies([halves[atlas] if n == 'Receiver' else high[n] for n in parts], key + '_high', hi_coll)
            set_material(hi, atlas)
            if atlas in MAG_SHIFT:
                for ob in (lo, hi):
                    ob.location = MAG_SHIFT[atlas]
            low_out.append(lo)
            high_out.append(hi)
            fin = finish_of[sid]
            meshes.setdefault(atlas, {}).setdefault(sid, {'finish': fin, 'meshes': []})['meshes'].append(lo.name)
            log(atlas, key, 'граней', int(keep.sum()), 'деталей', len(parts), how,
                'копий внахлёст', shifted)
    OUT.mkdir(parents=True, exist_ok=True)
    for ob in low_out + high_out:
        ob.data.update()
    export_fbx(low_out, OUT / 'SMG03_low.fbx')
    export_fbx(high_out, OUT / 'SMG03_high.fbx')
    (OUT / 'meshes.json').write_text(json.dumps(meshes, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('FBX', len(low_out), 'пар low/high →', OUT)
    return {a: [o for o in low_out if o.data.materials[0].name == a] for a in RED_SETS}


def _emit_material(kind, off, scale):
    """Свечение = положение (сдвиг и масштаб в 0…1) или нормаль — как tools/ar15/wear_maps.py."""
    mat = bpy.data.materials.new('tm_' + kind)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs[0])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    a = nt.nodes.new('ShaderNodeVectorMath')
    a.operation = 'MULTIPLY_ADD'
    nt.links.new(geo.outputs['Position' if kind == 'pos' else 'Normal'], a.inputs[0])
    a.inputs[1].default_value = scale
    a.inputs[2].default_value = off
    nt.links.new(a.outputs[0], em.inputs['Color'])
    tex = nt.nodes.new('ShaderNodeTexImage')
    nt.nodes.active = tex
    return mat, tex


def bake_maps(set_name, objs, size=4096):
    """Положение (мм) и нормаль в каждом пикселе развёртки сеток objs — на процессоре (видеокарта бывает занята
    соседними сессиями), 1 выборка, без размытия края."""
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = 1
    S.render.bake.margin = 8
    S.render.bake.margin_type = 'EXTEND'
    S.cycles.filter_width = 0.01
    for ob in bpy.context.view_layer.objects:
        ob.select_set(False)
        ob.hide_render = ob not in objs
    pts = np.concatenate([np.array([v.co for v in o.data.vertices]) for o in objs])
    lo = pts.min(0) - 0.01
    hi = pts.max(0) + 0.01
    sc = 1.0 / (hi - lo)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    old = {o.name: list(o.data.materials) for o in objs}
    res = {}
    for kind, off, scale in (('pos', tuple(-lo * sc), tuple(sc)), ('nrm', (0.5,) * 3, (0.5,) * 3)):
        mat, tex = _emit_material(kind, off, scale)
        img = bpy.data.images.new('tm_' + kind, size, size, float_buffer=True, alpha=False)
        img.colorspace_settings.name = 'Non-Color'
        tex.image = img
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        bpy.ops.object.bake(type='EMIT')
        px = np.empty(size * size * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        res[kind] = px.reshape(size, size, 4)[::-1, :, :3]          # сверху вниз, как в файле картинки
    for o in objs:
        o.data.materials.clear()
        for m in old[o.name]:
            o.data.materials.append(m)
    # пиксели вне островов: запекание их не трогает (0) — отметить, чтобы маски их не красили
    filled = np.any(res['nrm'] != 0.0, axis=-1)
    pos = ((res['pos'] / sc + lo) * 1000.0).astype(np.float32)
    nrm = res['nrm'] * 2.0 - 1.0
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    path = OUT / f'{set_name}_maps.npz'
    np.savez_compressed(path, pos=pos, nrm=nrm.astype(np.float16), filled=filled)
    log('карты развёртки', set_name, size, 'пикселей на сетке', int(filled.sum()), '→', path)


def red_marks_json():
    """Контуры красных меток (part_stamps.red_marks) — треугольники лиц букв на плоскости XZ (мм) по сторонам."""
    import part_stamps
    coll = bpy.data.collections.new('MARKS')
    bpy.context.scene.collection.children.link(coll)
    anchor = bpy.data.objects.new('marks_anchor', None)
    coll.objects.link(anchor)
    out = []
    for txt, size, center, nrm in part_stamps.red_marks():
        cut = part_stamps.text_cutter(txt, size, 0.85, coll)
        part_stamps.place(cut, center, nrm, (0, 0, 1), 0.6, anchor)
        me = cut.data
        me.calc_loop_triangles()
        tris = []
        for t in me.loop_triangles:
            if abs(t.normal.y) < 0.5:
                continue
            tris.append([[round(me.vertices[i].co.x * 1000, 4), round(me.vertices[i].co.z * 1000, 4)]
                         for i in t.vertices])
        out.append({'text': txt, 'side': 1 if nrm[1] > 0 else -1, 'center_mm': list(center), 'tris': tris})
    (OUT / 'marks.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8', newline='\n')
    log('красных меток', len(out), '→', OUT / 'marks.json')


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    stages = set(args) or {'fbx', 'maps'}
    rec = build_fbx()
    if 'maps' in stages:
        for set_name, objs in rec.items():
            bake_maps(set_name, objs)
        red_marks_json()


if __name__ == '__main__':
    main()
