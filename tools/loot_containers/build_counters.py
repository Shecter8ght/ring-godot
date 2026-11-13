"""Опоры под кассовый аппарат (форма без текстур): прилавок торговый ПТ_ и кассовый бокс супермаркета КБ_.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/loot_containers/build_counters.py -- "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Counters_v01.blend" \
      [preview <папка>] [check]

Коллекция «Опоры_касс_v01» (по коллекции на предмет), «Для_масштаба» — закрытая касса партии 1 экземпляром на socket_register
и фигура 1,75 м; камеры — в «Камеры». Детали — counters.py.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import counters  # noqa: E402
import lc  # noqa: E402
from lc import L, V, B  # noqa: E402

CASH_SRC = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_Containers_v01.blend"
ITEMS = [("counter", "Прилавок торговый", counters.counter, 0.0), ("checkout", "Кассовый бокс", counters.checkout, 4.4)]
FIG = {"counter": ((-0.25, 0.80, 0.0), 0.0), "checkout": ((4.8, 1.10, 0.0), 0.0)}


def build(out: str):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    m = counters.cmats()
    top = L.collection("Опоры_касс_v01")
    placed = {}
    for key, label, fn, x in ITEMS:
        c = L.collection(label, top)
        placed[key] = (c, fn(c, m, (x, 0.0, 0.0)))
    B.studio(L.collection("Студия"), 5.5)
    wm = bpy.data.materials["Студия_стена"]
    wm.diffuse_color = (0.07, 0.08, 0.09, 1)
    for n in wm.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            n.inputs["Base Color"].default_value = (0.07, 0.08, 0.09, 1)
    # для масштаба: закрытая касса партии 1 на socket_register и фигура
    sc_coll = L.collection("Для_масштаба")
    with bpy.data.libraries.load(CASH_SRC, link=False) as (df, dt):
        dt.collections = [n for n in df.collections if n == "Кассовое место"]
    cc = dt.collections[0]
    root = next(o for o in cc.all_objects if o.name.startswith("КМ_кассовое_место"))
    cc.instance_offset = root.location.copy()
    bpy.context.scene.collection.children.link(cc)   # исходник экземпляров лежит в исключённой коллекции (как принято для инстансов)
    bpy.context.view_layer.layer_collection.children[cc.name].exclude = True
    for key, (c, _) in placed.items():
        sock = next(o for o in c.objects if o.name.startswith("socket_register"))
        e = bpy.data.objects.new("Касса_" + key, None)
        e.instance_type = "COLLECTION"
        e.instance_collection = cc
        e.parent = sock
        sc_coll.objects.link(e)
        counters.human(sc_coll, m["human"], FIG[key][0], FIG[key][1]).name = "Фигура_" + key
    # камеры
    kc = L.collection("Камеры")
    views = make_cameras(kc, placed)
    # свет для проверки скользящим
    sun = bpy.data.lights.new("Скользящий", "SUN")
    sun.energy = 0.0
    so = bpy.data.objects.new("Скользящий", sun)
    kc.objects.link(so)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)
    return placed, views


# (имя, цель от корня, дистанция, азимут (0 — камера с −Y), подъём, фокус, [скользящий свет: азимут света])
VIEWS = {
    "counter": [("buyer34", (0, 0, 0.45), 3.4, -35, 16, 40, None), ("seller34", (0, 0, 0.45), 3.4, 145, 18, 40, None),
                ("top", (0, 0, 0.9), 2.6, 0, 89, 40, None),
                ("detail_edge", (-0.73, -0.28, 0.85), 0.55, -40, 24, 50, None),
                ("detail_drawer", (0.0, 0.28, 0.65), 1.2, 150, 14, 45, None),
                ("buyer34_graze", (0, 0, 0.45), 3.4, -35, 16, 40, 60), ("seller34_graze", (0, 0, 0.45), 3.4, 145, 18, 40, -70),
                ("scale", (0, 0.15, 0.85), 4.3, 150, 12, 40, None)],
    "checkout": [("buyer34", (0.1, 0, 0.5), 5.2, -38, 18, 40, None), ("seller34", (0.1, 0, 0.5), 5.2, 140, 20, 40, None),
                 ("top", (0.1, 0, 0.8), 4.4, 0, 89, 40, None),
                 ("detail_belt", (0.0, -0.25, 0.84), 1.5, -28, 28, 45, None),
                 ("detail_accum", (0.8, -0.25, 0.9), 1.4, -35, 24, 45, None),
                 ("detail_cashier", (0.45, 0.4, 0.85), 1.6, 150, 24, 45, None),
                 ("buyer34_graze", (0.1, 0, 0.5), 5.2, -38, 18, 40, 70), ("seller34_graze", (0.1, 0, 0.5), 5.2, 140, 20, 40, -70),
                 ("scale", (0.1, 0.2, 0.9), 6.0, 145, 14, 40, None)],
}


def make_cameras(kc, placed) -> list:
    out = []
    for key, vs in VIEWS.items():
        c, root = placed[key]
        for name, tgt, dist, az, el, lens, gl in vs:
            cd = bpy.data.cameras.new(f"Кам_{key}_{name}")
            cd.lens = lens
            cd.clip_start = 0.02
            co = bpy.data.objects.new(f"Кам_{key}_{name}", cd)
            ctr = V(root.location) + V(tgt)
            a, e = math.radians(az), math.radians(el)
            co.location = ctr + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            co.rotation_euler = (ctr - co.location).to_track_quat("-Z", "Y" if el < 80 else "Y").to_euler()
            kc.objects.link(co)
            out.append((key, name, co, gl))
    return out


def preview(views, folder: str) -> None:
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    sc_coll = bpy.data.collections["Для_масштаба"]
    sun = bpy.data.objects["Скользящий"]
    wall = bpy.data.objects.get("студия_стена")
    if wall:
        wall.hide_render = True   # камеры со стороны продавца стоят за стеной студии
    areas = [o for o in bpy.data.objects if o.type == "LIGHT" and o.data.type == "AREA"]
    base_e = {o: o.data.energy for o in areas}
    world_bg = next(n for n in sc.world.node_tree.nodes if n.type == "BACKGROUND")
    w0 = world_bg.inputs[1].default_value
    for key, name, cam, gl in views:
        sc.camera = cam
        sc_coll.hide_render = name != "scale"
        for o in areas:
            o.data.energy = base_e[o] * (0.08 if gl is not None else 1.0)
        world_bg.inputs[1].default_value = w0 * (0.15 if gl is not None else 1.0)
        sun.data.energy = 6.0 if gl is not None else 0.0
        if gl is not None:
            a, e = math.radians(gl), math.radians(9)
            p = V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
            sun.rotation_euler = (-p).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(folder, f"{key}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("view", key, name, flush=True)
    sun.data.energy = 0.0
    for o in areas:
        o.data.energy = base_e[o]
    world_bg.inputs[1].default_value = w0
    sc_coll.hide_render = False


# ---------------------------------------------------------------- проверка

def _tree(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    vs, ps = [], []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(vs)
        vs += [ev.matrix_world @ v.co for v in me.vertices]
        ps += [tuple(base + i for i in p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, ps) if ps else None


def _flipped(ob) -> int:
    """Число замкнутых островов с отрицательным объёмом (вывернутые нормали)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    bm = bmesh.new()
    bm.from_mesh(ev.to_mesh())
    ev.to_mesh_clear()
    bm.transform(ev.matrix_world)
    seen, bad = set(), 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack, comp = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        closed = all(len(e.link_faces) == 2 for f in comp for e in f.edges)
        if not closed:
            continue
        vol = 0.0
        for f in comp:
            vs = [v.co for v in f.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
        if vol < 0:
            bad += 1
    bm.free()
    return bad


def check(placed) -> None:
    bpy.context.view_layer.update()
    for key, (c, root) in placed.items():
        mn, mx = lc.bounds([c])
        sz = mx - mn
        print(f"SIZE {key}: {sz.x*1000:.0f} (ш) x {sz.y*1000:.0f} (г) x {sz.z*1000:.0f} (в) мм; tri {lc.tri_count([c])}")
        obs = [o for o in c.objects if o.type == "MESH"]
        trees = {o: _tree([o]) for o in obs}
        bb = {}
        dg = bpy.context.evaluated_depsgraph_get()
        for o in obs:
            ev = o.evaluated_get(dg)
            pts = [ev.matrix_world @ V(b) for b in ev.bound_box]
            bb[o] = (V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))), V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))
        n_pairs = 0
        for i, a in enumerate(obs):
            for b in obs[i + 1:]:
                (a0, a1), (b0, b1) = bb[a], bb[b]
                if any(a1[k] < b0[k] or b1[k] < a0[k] for k in range(3)):
                    continue
                if trees[a] and trees[b]:
                    n = len(trees[a].overlap(trees[b]))
                    if n:
                        n_pairs += 1
                        print(f"  OVERLAP {key}: {a.name} x {b.name}: {n} пар граней")
        print(f"OVERLAPS {key}: пар объектов {n_pairs}")
        fl = {o.name: _flipped(o) for o in obs}
        fl = {k: v for k, v in fl.items() if v}
        print(f"FLIPPED {key}: {fl if fl else 'нет'}")
        # касса на socket_register
        sock = next(o for o in c.objects if o.name.startswith("socket_register"))
        sup = _tree(obs)
        M = sock.matrix_world
        gaps = []
        for dx in (-0.205, 0.0, 0.205):
            for dy in (-0.21, 0.0, 0.21):
                p = M @ V((dx, dy, 0.0))
                hit = sup.ray_cast(p + V((0, 0, 0.05)), V((0, 0, -1)), 0.2)
                gaps.append(None if hit[0] is None else (p.z - hit[0].z) * 1000)
        ok = all(g is not None and -0.5 <= g <= 2.0 for g in gaps)
        print(f"SOCKET {key}: зазоры мм {[None if g is None else round(g, 2) for g in gaps]} -> {'ОК' if ok else 'ПЛОХО'}")
        # подвижный ящик
        for mv in lc.MOVERS.get(c.name, []):
            print(f"MOVER {key}: {mv.name} начало {tuple(round(v, 4) for v in mv.matrix_world.translation)}")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed, views = build(argv[0])
    if "check" in argv:
        check(placed)
    if "preview" in argv:
        preview(views, argv[argv.index("preview") + 1])
        bpy.ops.wm.save_as_mainfile(filepath=argv[0], compress=True)
