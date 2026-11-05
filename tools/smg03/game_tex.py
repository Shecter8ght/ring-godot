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
import math
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
# карта нормалей — запеканием в Blender (стадия normals): Painter 12.1 не берёт из FBX нормалей игровой сетки и пересчитывает
# их сам; его карта выправляла его же пересчёт, и на наших нормалях (их видят Blender и Godot) вокруг надписей шёл веер,
# у кромок — полосы (владелец 05.11, v2; то же у цевья Dolinskyi, tools/handguard_dolinskyi/bake_normal.py)
NORMAL_RES = {'Upper': 4096, 'Lower': 4096, 'Steel': 4096, 'Stock': 2048, 'Mag13': 2048, 'Mag30': 2048}
CAGE_M = 0.0008                    # луч стартует на 0.8 мм снаружи игровой сетки
CAGE_NEAR_M = 0.00015              # второе запекание — с 0.15 мм: для пазов у.же клетки (см. bake_normals)
RAY_M = 0.0025                     # и идёт до 1.7 мм внутрь: отклонение сетки до 0.47 мм, гравировка 0.25–0.45
PAIRS = []                         # (low, high, набор) — пары по слотам из build_fbx
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


def planar_snap(o, tol_mm: float = 0.08, min_area_mm2: float = 10.0, cos_lim: float = 0.9998):
    """Плоскости вдоль осей у high-poly — ровно в одну плоскость: местная нарезка вокруг знаков и надписей
    (lib.grid_split_local, допуск разреза 0.02 мм) оставляла ступеньки в 0.03 мм — утопленная панель переднего торца лежала
    на уровнях 105.27 / 105.30 / 105.33 мм, и затенение с картой нормалей показывали полосы по границе нарезки
    (владелец 05.11, v3). Грани с нормалью вдоль оси (до ~1°) кучкуются по смещению с зазором меньше tol_mm; куча
    площадью от min_area_mm2 сводится к среднему по площади, вершины её граней сдвигаются только по этой оси. Рельеф
    глубже tol_mm (гравировка, канавки, шагрень) не трогается. Возврат — сдвинуто вершин."""
    me = o.data
    co = np.array([v.co[:] for v in me.vertices], np.float64)
    moved = np.zeros(len(co), bool)
    for ax in range(3):
        for sgn in (1.0, -1.0):
            faces = [p for p in me.polygons if p.normal[ax] * sgn > cos_lim]
            if not faces:
                continue
            off = np.array([p.center[ax] for p in faces]) * 1000.0
            area = np.array([p.area for p in faces]) * 1e6
            order = np.argsort(off)
            groups, cur = [], [order[0]]
            for a, b in zip(order[:-1], order[1:]):
                if off[b] - off[a] < tol_mm * 0.5:
                    cur.append(b)
                else:
                    groups.append(cur)
                    cur = [b]
            groups.append(cur)
            for g in groups:
                g = np.array(g)
                if area[g].sum() < min_area_mm2 or off[g].max() - off[g].min() > tol_mm:
                    continue
                target = float((off[g] * area[g]).sum() / area[g].sum()) / 1000.0
                for i in g:
                    for vi in faces[i].vertices:
                        # вершина, общая с гранью другой плоскости (дно у знака), уезжала на 0.33 мм — наклонный
                        # треугольник через переднюю плоскость торца; двигаем только в пределах допуска
                        dv = abs(co[vi, ax] - target)
                        if 1e-9 < dv <= tol_mm / 1000.0:
                            co[vi, ax] = target
                            moved[vi] = True
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    return int(moved.sum())


def stamp_zones():
    """Зоны местной нарезки у high-poly корпуса (part_stamps: знаки и надписи) — (центр мм, радиус мм, ось нормали,
    смещение плоскости мм): здесь grid_split_local оставлял браки нарезки."""
    import lib
    import part_stamps
    zones = [((lib.FRONT_FACE_X, 0.0, 33.0), 11.0, 0, lib.FRONT_FACE_X)]
    for s in (1, -1):
        zones.append(((-80.0, s * lib.HALF_W, -32.0), 13.5, 1, s * lib.HALF_W))
    for txt, size, center, nrm, depth, red in part_stamps.text_stamps():
        zones.append((center, size * max(1.0, len(txt) * 0.42) + 2.0, 1, center[1]))
    return zones


def flatten_dents(o, max_mm: float = 0.13):
    """Вмятины мельче max_mm в зонах нарезки у знаков и надписей — в плоскость: по границе квадратной нарезки вокруг знака
    на переднем торце остались канавки 0.1 мм (z 23 и 43, левая половина) — полосы на торце (владелец 05.11, v3).
    Гравировка (0.25–0.45 мм) и её фаска (0.18) глубже — не трогаются. Возврат — сдвинуто вершин."""
    me = o.data
    co = np.array([v.co[:] for v in me.vertices], np.float64) * 1000.0
    moved = 0
    for center, r, ax, plane in stamp_zones():
        other = [i for i in range(3) if i != ax]
        # нарезка — квадратом со стороной 2r (lib.grid_split_local), канавки — по его краю: расстояние по Чебышёву
        d = np.maximum(np.abs(co[:, other[0]] - center[other[0]]), np.abs(co[:, other[1]] - center[other[1]]))
        sgn = 1.0 if plane >= 0 else -1.0
        depth = (plane - co[:, ax]) * sgn            # >0 — внутрь детали
        # и вмятины, и бугорки: по границе нарезки у знака на торце — гребешок ~0.02 мм над плоскостью (допуск разреза)
        sel = (d < r) & (np.abs(depth) > 1e-6) & (np.abs(depth) < max_mm)
        co[sel, ax] = plane
        moved += int(sel.sum())
    me.vertices.foreach_set('co', (co / 1000.0).astype(np.float32).ravel())
    me.update()
    return moved


def outward_shells(bm, min_mm3: float = 1.0):
    """Замкнутые оболочки, вывернутые целиком (объём со знаком меньше нуля: у корпуса магазина на 30 — вся оболочка
    наизнанку), — лицом наружу. Открытые (половины корпуса по шву) не трогаются: знак их объёма ничего не значит.
    Возврат — развёрнуто граней."""
    bm.faces.ensure_lookup_table()
    seen = set()
    flip = []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        seen.add(f0.index)
        comp, st = [], [f0]
        while st:
            f = st.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        st.append(g)
        if any(len(e.link_faces) < 2 for f in comp for e in f.edges):
            continue
        vol = 0.0
        for f in comp:
            vs = [v.co for v in f.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
        if vol * 1e9 < -min_mm3:
            flip += comp
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
        bm.normal_update()
    return len(flip)


def unfold_planes(bm, min_area_mm2: float = 10.0, cos_lim: float = 0.9998, tol_mm: float = 0.02):
    """Вывернутые грани в больших плоскостях вдоль осей — лицом наружу. У v06 на переднем торце после нарезки остались
    многоугольники, сложенные «наизнанку» (нормаль −X среди граней +X: длинные полосы у края панели), и Blender при
    запекании берёт нормаль попавшей грани как есть — в карте 180°, штрихи по торцу (владелец 05.11, v3); AO у Painter
    от них тоже темнел. Сетка к этому времени — треугольники (у сложенного многоугольника вывернута лишь часть).

    В каждой плоскости вдоль оси сторона наружу — та, чьих граней по площади больше (вывернутых на торце набирается
    70 мм² — сами они плоскостью не считаются); грань другой стороны, все вершины которой в плоскости и у которой есть
    сосед по ребру лицом наружу из этой же плоскости, разворачивается; полоса — с краю внутрь, по ряду за проход.
    Общее правило «соседи по ребру не бывают обращены друг против друга» пробовали 05.11 — оно ломает острые кромки
    (манжета магазина на 30 вывернулась целиком): складки вне больших плоскостей (скругления, фаски) ловит запекание
    (bake_normals: вторая клетка и дорисовка). Возврат — развёрнуто граней."""
    total = 0
    for _ in range(30):
        n = _unfold_pass(bm, min_area_mm2, cos_lim, tol_mm)
        total += n
        if not n:
            break
    return total


def _unfold_pass(bm, min_area_mm2, cos_lim, tol_mm):
    flip = set()
    half = tol_mm / 2000.0
    for ax in range(3):
        area = {}
        along = []
        for f in bm.faces:
            s = f.normal[ax]
            if abs(s) <= cos_lim:
                continue
            k = round(f.calc_center_median()[ax] * 1000.0 / tol_mm)
            a = area.setdefault(k, [0.0, 0.0])
            a[0 if s > 0 else 1] += f.calc_area() * 1e6
            along.append((f, k, 1 if s > 0 else -1))
        major = {}
        for k, (ap, an) in area.items():
            big, small = max(ap, an), min(ap, an)
            if big >= min_area_mm2 and small * 2.0 < big:
                major[k] = 1 if ap > an else -1
        for f, k, sg in along:
            m = major.get(k)
            if m is None or sg == m:
                continue
            pl = k * tol_mm / 1000.0
            if not all(abs(v.co[ax] - pl) < half for v in f.verts):
                continue
            for e in f.edges:
                if any(g is not f and g.normal[ax] * m > cos_lim and all(abs(v.co[ax] - pl) < half for v in g.verts)
                       for g in e.link_faces):
                    flip.add(f)
                    break
    if flip:
        bmesh.ops.reverse_faces(bm, faces=list(flip))
        bm.normal_update()
    return len(flip)


def high_normals(o, angle_deg: float = 60.0):
    """Нормали high-poly для запекания: рёбра круче angle (стенки букв, канавок, вырезов — 90°) — жёсткие, затем по
    площади граней. Свои нормали исходника гнулись у стенок букв, и вокруг надписей в карте шёл слабый веер полос
    (05.11); фаски в 2 сегмента (45°) остаются гладкими."""
    import math
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    # неплоские многоугольники — по плоским частям: у v06 передняя плоскость торца и начало фаски края панели слиты в одну
    # грань, при разбиении на треугольники длинный треугольник шёл от плоскости к краю на 0.33 мм глубже — линия на
    # торце (владелец 05.11, v3; видна и в самом исходнике)
    bmesh.ops.connect_verts_nonplanar(bm, angle_limit=math.radians(0.5), faces=bm.faces[:])
    # треугольниками — до своих нормалей: у сложенного многоугольника вывернута только часть треугольников (unfold_planes);
    # join_copies бьёт на треугольники и сам, но здесь уже нечего
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY',
                          ngon_method='BEAUTY')
    # треугольники нулевой площади (многоугольники с вершинами на одной прямой) — прочь: их нормаль случайна, рёбра у них
    # выходили «острыми», и нормали соседних граней гнулись до 50° — пятно на скруглении левого борта (X −12, Z 49; v4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges[:])
    bm.normal_update()
    bm.faces.index_update()
    inside_out = outward_shells(bm)
    if inside_out:
        log('оболочки наизнанку — развёрнуто граней', o.name, inside_out)
    unfolded = unfold_planes(bm)
    if unfolded:
        log('развёрнуто вывернутых граней', o.name, unfolded)
    lim = math.radians(angle_deg)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim and                 min(f.calc_area() for f in e.link_faces) > 1e-12:     # у щепки (меньше 1e-6 мм²) нормаль случайна
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
    flat_planes(o)
    wild = tame_corners(o)
    if wild:
        log('нормали углов, ушедшие от грани больше 35°, — по грани', o.name, wild)


def tame_corners(o, max_deg: float = 35.0):
    """Нормаль угла, ушедшая от своей грани больше чем на max_deg, — нормалью грани. У фасок high-poly в два сегмента
    законное расхождение — до ~22°; больше — от щепок нулевой площади рядом (их нормаль случайна, а по площади
    граней веер у вершины гнуло до 50°): пятно на скруглении левого борта у затвора (X −12, Z 49; v4). Возврат —
    исправлено углов."""
    me = o.data
    n_c = np.zeros(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get('vector', n_c)
    n_c = n_c.reshape(-1, 3)
    lim = math.cos(math.radians(max_deg))
    fixed = 0
    for p in me.polygons:
        if p.area < 1e-12:
            continue
        fn = np.array(p.normal[:], np.float32)
        for li in p.loop_indices:
            if float(n_c[li] @ fn) < lim:
                n_c[li] = fn
                fixed += 1
    if fixed:
        me.normals_split_custom_set(n_c.tolist())
    return fixed


def flat_planes(o, min_area_mm2: float = 10.0, cos_lim: float = 0.9998, tol_mm: float = 0.02):
    """Грани больших плоскостей вдоль осей — строго плоской нормалью в своих углах. По площади граней нормаль у вершины
    на краю плоскости тянулась к соседней фаске и по длинным узким треугольникам местной нарезки расходилась внутрь
    плоскости — на переднем торце шли полосы по границе нарезки вокруг знака (они есть и в исходнике v06; владелец 05.11).
    Фаска своих нормалей не меняет: её край у плоскости остаётся гладким со стороны фаски."""
    me = o.data
    n_c = np.zeros(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get('vector', n_c)
    n_c = n_c.reshape(-1, 3)
    hit = 0
    for ax in range(3):
        for sgn in (1.0, -1.0):
            faces = [p for p in me.polygons if p.normal[ax] * sgn > cos_lim]
            if not faces:
                continue
            off = np.round(np.array([p.center[ax] for p in faces]) * 1000.0 / tol_mm)
            area = np.array([p.area for p in faces]) * 1e6
            tot = {}
            for k, a in zip(off, area):
                tot[k] = tot.get(k, 0.0) + a
            f = np.zeros(3, np.float32)
            f[ax] = sgn
            planes = []
            for p, k in zip(faces, off):
                if tot[k] < min_area_mm2:
                    continue
                for li in p.loop_indices:
                    n_c[li] = f
                hit += 1
                if k not in planes:
                    planes.append(k)
            # тонкие почти вырожденные треугольники в самой плоскости (нарезка): их нормаль по вершинам случайна, и в карте
            # от них оставалась линия на переднем торце — по положению вершин тоже в плоскость
            if planes:
                pv = np.array(planes) * tol_mm / 1000.0
                co = np.array([v.co[ax] for v in me.vertices])
                cos3 = math.cos(math.radians(3.0))
                for p in me.polygons:
                    if abs(p.normal[ax] * sgn) > cos_lim and p.normal[ax] * sgn > 0:
                        continue
                    vs = co[list(p.vertices)]
                    on = np.abs(vs[:, None] - pv[None, :]) < 3e-6          # вершина × плоскость
                    in_plane = on.all(axis=0).any() and p.normal[ax] * sgn > -0.5
                    # почти плоская полоска (до 3°), у которой две вершины в плоскости, а третья — у края фаски (Т-стык
                    # без вершины на торце v06: полоска 0.19 × 12 мм с наклоном 1.5°, нормаль у фаски тянула на 7°)
                    strip = p.normal[ax] * sgn > cos3 and (on.sum(axis=0) >= 2).any()
                    if in_plane or strip:
                        for li in p.loop_indices:
                            n_c[li] = f
                        hit += 1
    for p in me.polygons:
        p.use_smooth = True
    me.normals_split_custom_set(n_c.tolist())
    return hit


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
    snapped = flatten_dents(high['Receiver'])
    log('high-poly корпуса: вмятин нарезки выровнено вершин', snapped)
    for o in high.values():
        snapped += planar_snap(o)
        high_normals(o)
        keep_normals(o.data)
    log('high-poly: вершин сведено в плоскости', snapped)
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
            PAIRS.append((lo, hi, atlas))
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
    # габарит всей сцены игровой сетки (с опущенными магазинами): трёхпроекционная заливка Painter считает плитки на
    # наибольший размер сцены, а не набора — по нему sp_smg03 переводит зерно в мм (v4: по габариту набора вышло в 3 раза
    # крупнее)
    cs = np.array([ob.matrix_world @ Vector(c) for ob in low_out for c in ob.bound_box]) * 1000.0
    scene = {'min_mm': cs.min(0).round(1).tolist(), 'max_mm': cs.max(0).round(1).tolist(),
             'size_mm': float((cs.max(0) - cs.min(0)).max().round(1))}
    (OUT / 'scene.json').write_text(json.dumps(scene, ensure_ascii=False), encoding='utf-8', newline='\n')
    log('FBX', len(low_out), 'пар low/high →', OUT, 'габарит сцены', scene['size_mm'], 'мм')
    # сетки всех наборов: карты положения нужны и маскам износа по местам (этап 2), не только корпусу
    return {a: [o for o in low_out if o.data.materials[0].name == a]
            for a in sorted({o.data.materials[0].name for o in low_out})}


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
    """Контуры надписей и меток (part_stamps.text_stamps) — треугольники лиц букв на плоскости XZ (мм) по сторонам, с
    глубиной гравировки и признаком красной заливки: tex_masks.py строит по ним маску заливки и гравировку в карте нормалей."""
    import part_stamps
    coll = bpy.data.collections.new('MARKS')
    bpy.context.scene.collection.children.link(coll)
    anchor = bpy.data.objects.new('marks_anchor', None)
    coll.objects.link(anchor)
    out = []
    for txt, size, center, nrm, depth, red in part_stamps.text_stamps():
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
        out.append({'text': txt, 'side': 1 if nrm[1] > 0 else -1, 'center_mm': list(center), 'depth_mm': depth,
                    'red': red, 'tris': tris})
    (OUT / 'marks.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8', newline='\n')
    log('надписей и меток', len(out), '→', OUT / 'marks.json')
    # зоны местной нарезки (там браки high-poly) и сами знаки — tex_masks.clean_planes выравнивает зону, обходя знак
    emblems = []
    for c, r, n in part_stamps.emblem_places():
        ax = [i for i, v in enumerate(n) if v][0]
        axes = [i for i in range(3) if i != ax]
        # лицо резца в плоскости знака (кольцо и ломаная) — контур гравировки знака для белой заливки (этап 2)
        e = part_stamps.emblem_cutter(r, 0.45, coll)
        part_stamps.place(e, c, n, (0, 0, 1), 0.0, anchor)
        e.data.calc_loop_triangles()
        tris = [[[round(e.data.vertices[i].co[a] * 1000, 4) for a in axes] for i in t.vertices]
                for t in e.data.loop_triangles if abs(t.normal[ax]) > 0.5]
        emblems.append({'center_mm': list(c), 'r_mm': r, 'axis': ax, 'axes': axes, 'tris': tris})
    zones = {'cuts': [{'center_mm': list(c), 'half_mm': r, 'axis': ax, 'plane_mm': pl} for c, r, ax, pl in stamp_zones()],
             'emblems': emblems}
    (OUT / 'zones.json').write_text(json.dumps(zones, ensure_ascii=False), encoding='utf-8', newline='\n')
    log('зон нарезки', len(zones['cuts']), 'знаков', len(zones['emblems']), '→', OUT / 'zones.json')


def bake_normals(samples=4, dilate_px=16):
    """Карта нормалей наборов в Blender (Cycles на процессоре): каждая сетка-слот — только со своей high-poly (пары из
    build_fbx), касательные — по нашим нормалям игровой сетки, OpenGL (как проект Painter). Пиксели, куда запекание не
    попало, — плоская нормаль; края островов дорисованы наружу на dilate_px. → OUT/normals/<набор>_normal.png (16 бит).

    Запекание дважды — с клеткой CAGE_M и CAGE_NEAR_M. Луч берёт первую попавшуюся грань, и в Blender нет «пропускать
    изнанку», как у Painter: в пазах у.же клетки (продольные канавки бортов, шлицы) луч стартовал за дальней стенкой паза,
    бил в неё с изнанки, и нормаль выходила внутрь детали (z < 0 — 0.6 % верхнего атласа, у стали 5 %; владелец 05.11,
    v3). Где с большой клеткой изнанка — берётся малая; где изнанка у обеих — пиксель дорисовывается по соседям тем же
    расширением, что и края островов."""
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = samples
    bk = S.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = CAGE_M
    bk.max_ray_distance = RAY_M
    bk.margin = 0
    bk.use_clear = False
    bk.normal_space = 'TANGENT'
    bk.normal_r, bk.normal_g, bk.normal_b = 'POS_X', 'POS_Y', 'POS_Z'
    out_dir = OUT / 'normals'
    out_dir.mkdir(parents=True, exist_ok=True)
    for ob in bpy.data.objects:
        ob.hide_render = False
    for atlas, size in NORMAL_RES.items():
        pairs = [(lo, hi) for lo, hi, a in PAIRS if a == atlas]
        if not pairs:
            continue
        runs = []
        for cage in (CAGE_M, CAGE_NEAR_M):
            bk.cage_extrusion = cage
            img = bpy.data.images.new('nb_' + atlas, size, size, float_buffer=True, alpha=True)
            img.colorspace_settings.name = 'Non-Color'
            img.pixels.foreach_set(np.tile(np.array([0.5, 0.5, 1.0, 0.0], np.float32), size * size))
            mat = bpy.data.materials.new('nb_' + atlas)
            mat.use_nodes = True
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = img
            mat.node_tree.nodes.active = tex
            for lo, hi in pairs:
                keep = list(lo.data.materials)
                lo.data.materials.clear()
                lo.data.materials.append(mat)
                bpy.ops.object.select_all(action='DESELECT')
                hi.select_set(True)
                lo.select_set(True)
                bpy.context.view_layer.objects.active = lo
                bpy.ops.object.bake(type='NORMAL')
                lo.data.materials.clear()
                for m in keep:
                    lo.data.materials.append(m)
            px = np.empty(size * size * 4, np.float32)
            img.pixels.foreach_get(px)
            runs.append(px.reshape(size, size, 4))
        bk.cage_extrusion = CAGE_M
        (far, near) = runs
        rgb, filled = far[..., :3].copy(), far[..., 3] > 0.5
        back = filled & (far[..., 2] < 0.5)                      # z < 0: попадание в изнанку
        take = back & (near[..., 3] > 0.5) & (near[..., 2] >= 0.5)
        rgb[take] = near[..., :3][take]
        left = back & ~take
        filled = filled & ~left                                  # и у малой клетки изнанка — дорисовать по соседям
        n_baked = int(filled.sum())
        log('нормаль', atlas, 'изнанка с клеткой', round(CAGE_M * 1000, 2), 'мм:', int(back.sum()), 'взято с',
            round(CAGE_NEAR_M * 1000, 2), 'мм:', int(take.sum()), 'дорисовано:', int(left.sum()))
        # дорисовка краёв островов наружу (в Blender нет OpenCV): кольцо за кольцом — среднее запечённых соседей
        for _ in range(dilate_px):
            acc = np.zeros_like(rgb)
            cnt = np.zeros(filled.shape, np.float32)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
                f = np.roll(np.roll(filled, dy, 0), dx, 1)
                acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * f[..., None]
                cnt += f
            grow = (~filled) & (cnt > 0)
            if not grow.any():
                break
            rgb[grow] = acc[grow] / cnt[grow][:, None]
            filled = filled | grow
        rgb[~filled] = (0.5, 0.5, 1.0)
        n = rgb * 2.0 - 1.0
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
        rgb = n * 0.5 + 0.5
        out = bpy.data.images.new('nbo_' + atlas, size, size, float_buffer=True, alpha=False)
        out.colorspace_settings.name = 'Non-Color'
        out.pixels.foreach_set(np.concatenate([rgb, np.ones((size, size, 1), np.float32)], -1).ravel())
        path = out_dir / f'{atlas}_normal.png'
        S.render.image_settings.file_format = 'PNG'
        S.render.image_settings.color_mode = 'RGB'
        S.render.image_settings.color_depth = '16'
        out.save_render(str(path), scene=S)
        filled_n = n_baked
        log('нормаль', atlas, size, 'пар', len(pairs), 'запечено пикселей', filled_n, '→', path)


def main():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    stages = set(args) or {'fbx', 'maps'}
    if stages == {'marks'}:          # только marks.json и zones.json — по данным part_stamps, без сборки FBX
        red_marks_json()
        return
    rec = build_fbx()
    if 'maps' in stages:
        for set_name, objs in rec.items():
            bake_maps(set_name, objs, NORMAL_RES.get(set_name, 4096))
        red_marks_json()
    if 'normals' in stages:
        bake_normals()


if __name__ == '__main__':
    main()
