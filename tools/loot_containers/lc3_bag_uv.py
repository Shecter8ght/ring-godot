"""Сумка v02: развёртка в атласы и запекание карт геометрии (положение, нормаль, номер детали, AO) для отделки v03.

  blender --background "<RING_Loot_MedBag_v02.blend>" --python tools/loot_containers/lc3_bag_uv.py -- pack "<RING_Loot_MedBag_uv_v02.blend>"
  blender --background "<RING_Loot_MedBag_uv_v02.blend>" --python tools/loot_containers/lc3_bag_uv.py -- bake [A|B]

Острова берутся из слоя «UVmm» (миллиметры) и атрибута «isl», упаковка — полками в два атласа 4096: A — ткань корпуса
(корпус, лента низа, клапан, карман), B — всё остальное (стропы, кант, молнии, металл, ленты, нашивки, строчки).
Закрытое и раскрытое состояния получают одну и ту же раскладку (по именам без «.001»). Нить ткани идёт вдоль U.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

OUT = "E:/Games/RING-godot/_asset_src/loot_containers/maps_v03/lc_bag"
SIZE = 4096
GAP = 28
FIXED = {"t_red": (20.0, 4090.0), "t_black": (84.0, 4090.0), "t_gray": (148.0, 4090.0), "t_white": (212.0, 4090.0)}
RESERVED_BOTTOM = 80          # нижняя полоса атласа B — клетки ниток
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def base_name(n):
    return n.rsplit(".", 1)[0] if n.rsplit(".", 1)[-1].isdigit() else n


def island_data(ob):
    me = ob.data
    n = len(me.loops)
    uv = np.empty(n * 2, np.float32)
    me.uv_layers["UVmm"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    npoly = len(me.polygons)
    ls = np.empty(npoly, np.int32)
    lt = np.empty(npoly, np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    pol_of_loop = np.repeat(np.arange(npoly), lt)
    isl = np.empty(npoly, np.int32)
    me.attributes["isl"].data.foreach_get("value", isl)
    return uv, pol_of_loop, isl[pol_of_loop]


def shelf_pack(rects, W, H, gap):
    """rects: [(key, w, h)] → ({key: (x, y)}, высота) или None."""
    order = sorted(rects, key=lambda r: -r[2])
    pos = {}
    x = y = shelf = 0
    for key, w, h in order:
        if w + gap > W:
            return None
        if x + w + gap > W:
            x = 0
            y += shelf + gap
            shelf = 0
        pos[key] = (x + gap // 2, y + gap // 2)
        x += w + gap
        shelf = max(shelf, h)
    if y + shelf + gap > H:
        return None
    return pos, y + shelf + gap


def pack_set(objs_closed, label):
    isl_boxes = {}
    for ob in objs_closed:
        uv, _, il = island_data(ob)
        for i in np.unique(il):
            if i == 255:
                continue
            m = il == i
            u, v = uv[m, 0], uv[m, 1]
            isl_boxes[(ob.name, int(i))] = (float(u.min()), float(v.min()), float(u.max()), float(v.max()))
    H = SIZE - (RESERVED_BOTTOM if label == "B" else 0)
    lo, hi = 0.5, 12.0
    best = None
    for _ in range(18):
        d = (lo + hi) / 2
        rects = [(k, max(1, math.ceil((b[2] - b[0]) * d)), max(1, math.ceil((b[3] - b[1]) * d))) for k, b in isl_boxes.items()]
        r = shelf_pack(rects, SIZE, H, GAP)
        if r:
            best = (d, rects, r)
            lo = d
        else:
            hi = d
    d, rects, (pos, used) = best
    sizes = {k: (w, h) for k, w, h in rects}
    layout = {}
    for k, b in isl_boxes.items():
        layout[k] = {"x": pos[k][0], "y": pos[k][1], "w": sizes[k][0], "h": sizes[k][1], "umin": b[0], "vmax": b[3], "vmin": b[1], "umax": b[2]}
    print(f"НАБОР {label}: островов {len(layout)}, плотность {d:.2f} пикс/мм, занято по высоте {used} из {H}", flush=True)
    return layout, d


def apply_uv(ob, layout, d):
    uv, _, il = island_data(ob)
    key = base_name(ob.name)
    out = np.zeros_like(uv)
    for i in np.unique(il):
        m = il == i
        if i == 255:
            continue
        r = layout.get((key, int(i)))
        if r is None:
            continue
        x = r["x"] + (uv[m, 0] - r["umin"]) * d
        y = r["y"] + (r["vmax"] - uv[m, 1]) * d
        out[m, 0] = x / SIZE
        out[m, 1] = 1.0 - y / SIZE
    # строчки — клетки ниток (материал → нить)
    me = ob.data
    if ob.get("kind") == "stitch":
        mi = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("material_index", mi)
        lt = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_total", lt)
        mloop = np.repeat(mi, lt)
        for k, name in enumerate(("t_red", "t_black", "t_gray", "t_white")):
            m = (mloop == k)
            out[m, 0] = FIXED[name][0] / SIZE
            out[m, 1] = 1.0 - FIXED[name][1] / SIZE
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    me.uv_layers["UVMap"].data.foreach_set("uv", out.reshape(-1))
    me.uv_layers.active = me.uv_layers["UVMap"]


def do_pack(out_path):
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.get("lc_set")]
    closed = [o for o in meshes if base_name(o.name) == o.name]
    layouts = {}
    res = {}
    for label in ("A", "B"):
        objs = [o for o in closed if o["lc_set"] == label]
        lay, d = pack_set(objs, label)
        layouts[label] = (lay, d)
    for o in meshes:
        lay, d = layouts[o["lc_set"]]
        apply_uv(o, lay, d)
    # убрать рабочий слой мм после упаковки
    for o in meshes:
        me = o.data
        if "UVmm" in me.uv_layers:
            me.uv_layers.remove(me.uv_layers["UVmm"])
        o["lc_set_density"] = layouts[o["lc_set"]][1]
    os.makedirs(OUT, exist_ok=True)
    js = {}
    for label, (lay, d) in layouts.items():
        items = []
        for (name, i), r in lay.items():
            ob = bpy.data.objects[name]
            names = json.loads(ob.get("isl_names", "{}")) if ob.get("isl_names") else {}
            tag = next((k for k, v in names.items() if v == i), "")
            items.append({"obj": name, "isl": i, "tag": tag, **r})
        js[label] = {"size": SIZE, "density": d, "islands": items}
    with open(os.path.join(OUT, "layout.json"), "w", encoding="utf-8") as fh:
        json.dump(js, fh, ensure_ascii=False, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
    print("saved", out_path)


def do_bake(which):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.cycles.samples = 1
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.get("lc_set") == which and base_name(o.name) == o.name]
    for o in bpy.data.objects:
        o.select_set(False)
    for o in bpy.data.objects:
        if o.type == "MESH" and base_name(o.name) != o.name:
            o.hide_render = True
            o.hide_viewport = True
    # материал для запекания
    mat = bpy.data.materials.new("запекание")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(info.outputs["Object Index"], comb.inputs["X"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = tex
    for k, o in enumerate(meshes, 1):
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.pass_index = k
        for md in o.modifiers:
            md.show_render = False
            md.show_viewport = False
        o.hide_render = False
        o.hide_viewport = False
        o.select_set(True)
        o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    bpy.context.view_layer.objects.active = meshes[0]
    parts = {k: base_name(o.name) for k, o in enumerate(meshes, 1)}
    res = SIZE
    kinds = [("pos", geo.outputs["Position"]), ("nrm", geo.outputs["Normal"]), ("part", comb.outputs["Vector"])]
    os.makedirs(OUT, exist_ok=True)
    for kind, sock in kinds:
        img = bpy.data.images.new(f"{which}_{kind}", res, res, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        tex.image = img
        for l in list(em.inputs["Color"].links):
            nt.links.remove(l)
        nt.links.new(sock, em.inputs["Color"])
        bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
        buf = np.empty(res * res * 4, np.float32)
        img.pixels.foreach_get(buf)
        np.save(os.path.join(OUT, f"{which}_{kind}.npy"), np.flipud(buf.reshape(res, res, 4))[..., :3].copy())
        bpy.data.images.remove(img)
        print("baked", which, kind, flush=True)
    with open(os.path.join(OUT, f"{which}_parts.json"), "w", encoding="utf-8") as fh:
        json.dump(parts, fh, ensure_ascii=False)
    # AO
    wd = sc.world
    wd.light_settings.distance = 0.05
    sc.cycles.samples = 40
    img = bpy.data.images.new(f"{which}_ao", res, res, float_buffer=True, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    tex.image = img
    bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
    buf = np.empty(res * res * 4, np.float32)
    img.pixels.foreach_get(buf)
    np.save(os.path.join(OUT, f"{which}_ao.npy"), np.flipud(buf.reshape(res, res, 4))[..., 0].copy())
    print("baked", which, "ao", flush=True)


if argv and argv[0] == "pack":
    do_pack(argv[1])
elif argv and argv[0] == "bake":
    for w in (argv[1:] or ["A", "B"]):
        do_bake(w)
