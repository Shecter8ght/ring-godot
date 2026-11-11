"""Пожарная АЦ в игру: упрощённые сетки LOD0 / LOD1 / LOD2 с той же развёрткой, что у high-poly.

Карты износа уже запечены по развёртке high-poly (16 наборов 4K): если упрощать сетку, не трогая развёртку, карты
подходят как есть — их только уменьшают и раскладывают по атласам (game_atlas.py). Поэтому здесь:
- берётся «Целая» (рольставни и двери закрыты); облицовка отсеков (набор lockers) не видна — её нет;
- мелочь меньше SMALL_M (заклёпки, болты) уходит — в карте она уже нарисована;
- у каждой сетки сначала сливаются грани одной плоскости (ровные панели из сотен треугольников), не переходя швов
  развёртки и острых рёбер, потом схлопываются рёбра до своей доли бюджета; доля — по площади детали и её месту
  (снаружи больше, в салоне и под кузовом меньше);
- связанные копии (колёса, рукава) упрощаются один раз.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/game_lod.py -- <выход.blend> [lod0|lod1|lod2]

Выход — сцена с деталями LOD (объекты с прежними ft_set / ft_slot и развёрткой — tex_view.py смотрит его как
high-poly) и отчёт треугольников в консоли.
"""
from __future__ import annotations

import math
import sys

import bmesh
import bpy
from mathutils import Vector

CLOSED = "Целая"
# уровень: (бюджет треугольников, мелочь меньше, м)
LEVELS = {"lod0": (150000, 0.03), "lod1": (40000, 0.08), "lod2": (8000, 0.25)}
DROP_SETS = {"lockers"}
# вес места: снаружи — 1, под кузовом и в отсеке насоса меньше, салон виден только в окна
WEIGHT = {"cab_interior": 0.35, "crew_interior": 0.2, "chassis": 0.45, "pump": 0.7, "glass": 0.5, "wheels": 3.0}
# детали, которые видно вблизи с улицы и у которых форма — круглая: рукава, колёса (по началу имени)
NAME_WEIGHT = {"suction_hose": 2.0, "tread_lug": 1.5, "rim": 2.0, "hub": 2.0, "tyre": 1.5}
SHARP_DEG = 35.0
# на дальних уровнях салона и низа почти не видно
FAR_DROP = {"lod1": {"crew_interior"}, "lod2": {"crew_interior", "cab_interior"}}
MIN_TRIS = 12


def log(*a):
    print(*a, flush=True)


def tris_of(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def area_of(o) -> float:
    s = o.matrix_world.to_scale()
    k = abs(s.x * s.y * s.z) ** (2.0 / 3.0)
    return sum(p.area for p in o.data.polygons) * k


def size_of(o) -> float:
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return max(max(v[i] for v in bb) - min(v[i] for v in bb) for i in range(3))


def split_uv_seams(bm) -> int:
    """Рёбра, по которым развёртка рвётся, — в настоящий разрез: схлопывание рёбер держит границы сетки (у
    Blender — штрафом границы), а шов развёртки внутри сплошной сетки переходит и тянет текстуру через остров
    (полоса на «17» двери, проба 2026-11-11)."""
    uv = bm.loops.layers.uv.active
    if uv is None:
        return 0
    cut = []
    for e in bm.edges:
        if len(e.link_loops) != 2:
            continue
        l1, l2 = e.link_loops
        # у соседних граней ребро идёт навстречу: угол l1 совпадает с l2.link_loop_next и наоборот
        a1, b1 = l1[uv].uv, l1.link_loop_next[uv].uv
        a2, b2 = l2.link_loop_next[uv].uv, l2[uv].uv
        if (a1 - a2).length > 1e-6 or (b1 - b2).length > 1e-6:
            cut.append(e)
    if cut:
        bmesh.ops.split_edges(bm, edges=cut)
    return len(cut)


def dissolve_flat(me, angle_deg=1.0):
    """Грани одной плоскости — в одну, не переходя швов развёртки, острых рёбер и границ материалов."""
    bm = bmesh.new()
    bm.from_mesh(me)
    split_uv_seams(bm)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle_deg), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:], delimit={"SEAM", "SHARP", "UV", "MATERIAL"})
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bm.to_mesh(me)
    bm.free()
    me.update()


def _box(me):
    import numpy as np
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    return co.min(0), co.max(0)


def _collapse(me, ratio):
    me2 = me.copy()
    tmp = bpy.data.objects.new("_dec", me2)
    bpy.context.scene.collection.objects.link(tmp)
    m = tmp.modifiers.new("dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = max(0.0005, ratio)
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = tmp
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tmp, do_unlink=True)
    return me2


def stand_in(me):
    """Коробка по габариту детали — для дальних уровней, если упростить сетку не вышло: все углы развёртки — в одну
    точку острова детали (цвет детали ровным тоном), за 100 м разницы не видно."""
    lo, hi = _box(me)
    uv_layer = me.uv_layers.active
    pick = tuple(uv_layer.data[me.polygons[len(me.polygons) // 2].loop_start].uv) if uv_layer and me.polygons else (0, 0)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector([lo[i] + (v.co[i] + 0.5) * (hi[i] - lo[i]) for i in range(3)])
    uv = bm.loops.layers.uv.new(uv_layer.name if uv_layer else "UVMap")
    for f in bm.faces:
        for lp in f.loops:
            lp[uv].uv = pick
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    me2 = bpy.data.meshes.new(me.name + "_box")
    bm.to_mesh(me2)
    bm.free()
    for m in me.materials:
        me2.materials.append(m)
    return me2


def decimate(me, ratio, far=False):
    """Схлопывание рёбер на временной копии сетки (у связанных копий сетка общая — модификатор к ней не применить).
    При сильном упрощении грязной сетки (слои граней друг на друге у правого лонжерона, торцы лестниц, крайние
    рольставни) схлопывание выбрасывает вершины за габарит детали на метры — тогда упрощать мягче."""
    if ratio >= 0.999:
        return me
    lo0, hi0 = _box(me)
    tol = max(0.02, 0.02 * float((hi0 - lo0).max()))
    for _ in range(6):
        me2 = _collapse(me, ratio)
        lo, hi = _box(me2)
        if (lo >= lo0 - tol).all() and (hi <= hi0 + tol).all():
            return me2
        bpy.data.meshes.remove(me2)
        ratio = min(1.0, ratio * 1.7)
        if ratio >= 0.999:
            break
    if far:
        log(f"    {me.name}: упрощение выбрасывает вершины — на дальнем уровне коробка по габариту")
        return stand_in(me)
    log(f"    {me.name}: упрощение выбрасывает вершины — оставлена после слияния плоскостей")
    return me


def build(level: str):
    budget, small = LEVELS[level]
    drop = DROP_SETS | FAR_DROP.get(level, set())
    closed = [o for o in bpy.data.collections[CLOSED].all_objects if o.type == "MESH"]
    keep = [o for o in closed if o.get("ft_set") not in drop and size_of(o) >= small]
    gone = [o for o in bpy.data.objects if o.type == "MESH" and o not in keep]
    log(f"{level}: деталей {len(keep)} из {len(closed)}, убрано мелочи и скрытого {len(closed) - len(keep)}")
    for o in gone:
        bpy.data.objects.remove(o, do_unlink=True)
    # по сетке: одна обработка на связанные копии; площадь — сумма по копиям
    users = {}
    for o in keep:
        users.setdefault(o.data, []).append(o)
    for me in users:
        me_tris0 = tris_of(me)
        dissolve_flat(me)
        users[me] = (users[me], me_tris0)
    total0 = sum(t0 * len(obs) for obs, t0 in users.values())
    flat = sum(tris_of(me) * len(obs) for me, (obs, _) in users.items())
    log(f"  треугольников: было {total0}, после слияния плоскостей {flat}")
    # бюджет по площади^0,6 × вес места (у связанных копий сетка общая — бюджет делится на копии)
    score = {}
    for me, (obs, _) in users.items():
        w = WEIGHT.get(obs[0].get("ft_set"), 1.0)
        base = obs[0].name.split(".")[0]
        w *= next((v for k, v in NAME_WEIGHT.items() if base.startswith(k)), 1.0)
        score[me] = w * sum(area_of(o) for o in obs) ** 0.6
    want = {me: tris_of(me) for me in users}
    left = budget
    todo = set(users)
    for _ in range(4):
        s = sum(score[me] for me in todo)
        if s <= 0:
            break
        free = []
        for me in todo:
            obs = users[me][0]
            share = left * score[me] / s / len(obs)
            if share >= tris_of(me):
                want[me] = tris_of(me)
                free.append(me)
            else:
                want[me] = max(MIN_TRIS, int(share))
        if not free:
            break
        for me in free:
            todo.discard(me)
            left -= tris_of(me) * len(users[me][0])
    for me, (obs, _) in users.items():
        t = tris_of(me)
        me2 = decimate(me, want[me] / t, far=(level != "lod0")) if want[me] < t else me
        # гладко, но рёбра круче SHARP_DEG — жёсткие: у упрощённой панели с бывшей фаской иначе тянется тень
        for p in me2.polygons:
            p.use_smooth = True
        me2.set_sharp_from_angle(angle=math.radians(SHARP_DEG))
        for o in obs:
            o.data = me2
    final = sum(tris_of(o.data) for o in keep)
    log(f"  итог {level}: {final} треугольников, сеток {len(users)}")
    by_set = {}
    for o in keep:
        by_set[o.get("ft_set")] = by_set.get(o.get("ft_set"), 0) + tris_of(o.data)
    log("  по наборам: " + ", ".join(f"{k} {v}" for k, v in sorted(by_set.items(), key=lambda kv: -kv[1])))
    return keep


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    level = a[1] if len(a) > 1 else "lod0"
    for c in bpy.data.collections:
        c.hide_viewport = False
        c.hide_render = False
    build(level)
    for c in list(bpy.data.collections):
        if c.name != CLOSED and not c.all_objects:
            bpy.data.collections.remove(c)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    log("SAVED", out)


if __name__ == "__main__":
    main()
