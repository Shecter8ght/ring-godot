"""Пожарная АЦ, этап 2 (износ): карты геометрии в развёртку наборов и места листьев и помёта.

Маски мест износа (wear_zones.py) и наклейки (граффити, надписи по пыли, ладони, листья, помёт) считаются вне
Blender по этим картам: у каждого пикселя развёртки известны положение в мире, нормаль и деталь. Наклейка —
«проектор» в мировых координатах, поэтому переходит со шва на шов и с набора на набор без разрывов.

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python
    tools/fire_truck/wear_maps.py -- [maps] [scatter] [набор …]

maps    → WORK/wear/geo/<набор>.npz: pos (uint16, (P − lo) / span, строки сверху вниз — как в картинке),
          nrm (int8, нормаль × 127), part (uint16, номер детали; 0 — пусто); geo.json — lo, span, детали наборов
          (номер → имя, слот), колёса (центр, радиус), габариты деталей «Целой».
scatter → WORK/wear/geo/scatter.json: листья (в углах и у бортов горизонталей, куда видно небо) и помёт (под
          насестами: поручни, лестница, мигалки, зеркала; немного — по крыше), лучами по всей машине.
Файл .blend не сохраняется: материалы наборов временно переключаются на излучение и остаются в памяти.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import tex_sets as T  # noqa: E402
import tex_uv as U  # noqa: E402  (_bvh)

OUT = T.WORK + "/wear/geo"
CLOSED = "Целая"
RES = 4096
MARGIN = 8
EXTERIOR = ["cab_panels", "cab_parts", "body_L", "body_R", "body_parts", "shutters", "roof", "trim", "pump", "chassis"]


def log(*a):
    print(*a, flush=True)


def reveal():
    def walk(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            walk(ch)
    walk(bpy.context.view_layer.layer_collection)
    for c in bpy.data.collections:
        c.hide_viewport = False
        c.hide_render = False
        c.hide_select = False
    for o in bpy.data.objects:
        o.hide_viewport = False
        o.hide_render = False
        o.hide_select = False
        o.hide_set(False)


def first_per_mesh():
    """Одна деталь на сетку — та же, что в FBX проектов Painter (tex_export): из «Целой», если есть."""
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    first = {}
    for o in sorted(meshes, key=lambda o: (CLOSED not in [c.name for c in o.users_collection], o.name)):
        first.setdefault(o.data.name, o)
    return first


def slot(o) -> str:
    if T.base_name(o.name) in ("body_L", "body_R", "top_band_L", "top_band_R"):
        return o.get("ft_slot", "paint_red")
    return T.slot_of(o.name, o.get("ft_mat", ""), o.get("ft_set", ""))


def bounds(objs):
    lo = np.full(3, 1e9)
    hi = np.full(3, -1e9)
    for o in objs:
        for c in o.bound_box:
            p = np.array(o.matrix_world @ Vector(c))
            lo = np.minimum(lo, p)
            hi = np.maximum(hi, p)
    return lo, hi


def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.bake.margin = MARGIN
    sc.render.bake.use_selected_to_active = False
    sc.render.bake.target = "IMAGE_TEXTURES"
    sc.render.bake.use_clear = True
    return sc


def bake_set(st, objs, lo, span, img):
    """Три прохода излучения: положение, нормаль, номер детали — в одну картинку по очереди, в массивы numpy."""
    mat = bpy.data.materials.get("FT_" + st)
    for o in objs:
        me = o.data
        if not me.materials or me.materials[0] != mat:
            raise RuntimeError(f"{o.name}: материал не FT_{st}")
        if T.UV in me.uv_layers:
            me.uv_layers[T.UV].active_render = True
            me.uv_layers.active = me.uv_layers[T.UV]
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    # положение: (P − lo) / span
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = tuple(lo)
    div = nt.nodes.new("ShaderNodeVectorMath")
    div.operation = "DIVIDE"
    div.inputs[1].default_value = (span, span, span)
    nt.links.new(geo.outputs["Position"], sub.inputs[0])
    nt.links.new(sub.outputs["Vector"], div.inputs[0])
    # нормаль: n × 0,5 + 0,5
    mad = nt.nodes.new("ShaderNodeVectorMath")
    mad.operation = "MULTIPLY_ADD"
    mad.inputs[1].default_value = (0.5, 0.5, 0.5)
    mad.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(geo.outputs["Normal"], mad.inputs[0])
    # номер детали / 65535
    pid = nt.nodes.new("ShaderNodeMath")
    pid.operation = "DIVIDE"
    pid.inputs[1].default_value = 65535.0
    nt.links.new(info.outputs["Object Index"], pid.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    bpy.ops.object.select_all(action="DESELECT")
    for k, o in enumerate(objs, 1):
        o.pass_index = k
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    res = {}
    buf = np.empty(RES * RES * 4, np.float32)
    for kind, sock in (("pos", div.outputs["Vector"]), ("nrm", mad.outputs["Vector"]), ("part", pid.outputs["Value"])):
        for lk in list(emit.inputs["Color"].links):
            nt.links.remove(lk)
        nt.links.new(sock, emit.inputs["Color"])
        t0 = time.time()
        bpy.ops.object.bake(type="EMIT", margin=MARGIN, use_clear=True)
        img.pixels.foreach_get(buf)
        a = np.flipud(buf.reshape(RES, RES, 4)[..., :3])        # Blender: строки снизу вверх → как в картинке
        if kind == "pos":
            res["pos"] = np.round(np.clip(a, 0, 1) * 65535).astype(np.uint16)
        elif kind == "nrm":
            res["nrm"] = np.round(np.clip(a * 2 - 1, -1, 1) * 127).astype(np.int8)
        else:
            res["part"] = np.round(a[..., 0] * 65535).astype(np.uint16)
        log(f"  {st} {kind}: {time.time() - t0:.0f} с")
    return res


def maps(only):
    reveal()
    sc = setup_scene()
    first = first_per_mesh()
    closed = [o for o in bpy.data.collections[CLOSED].all_objects if o.type == "MESH"]
    lo, hi = bounds([o for o in bpy.data.objects if o.type == "MESH"])
    lo = lo - 0.05
    span = float(max(hi - lo) + 0.05)
    os.makedirs(OUT, exist_ok=True)
    path = f"{OUT}/geo.json"
    info = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"sets": {}}
    info["lo"] = [float(x) for x in lo]
    info["span"] = span
    # колёса — шины «Целой»: центр и радиус (по высоте габарита)
    wheels = []
    for o in closed:
        if o.get("ft_set") == "wheels" and slot(o) == "tyre":
            a, b = bounds([o])
            wheels.append({"name": o.name, "c": [float(x) for x in (a + b) / 2], "r": float((b[2] - a[2]) / 2),
                           "w": float(b[0] - a[0])})
    info["wheels"] = wheels
    info["boxes"] = {o.name: [[float(x) for x in v] for v in bounds([o])] for o in closed}
    img = bpy.data.images.new("ft_wear_geo", RES, RES, float_buffer=True, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    for st in T.SETS:
        if only and st not in only:
            continue
        objs = [o for o in first.values() if o.get("ft_set") == st]
        if not objs:
            continue
        log(f"НАБОР {st}: деталей {len(objs)}")
        r = bake_set(st, objs, lo, span, img)
        np.savez_compressed(f"{OUT}/{st}.npz", **r)
        info["sets"][st] = {str(k): [o.name, slot(o)] for k, o in enumerate(objs, 1)}
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
    log("MAPS DONE")


# ------------------------------------------------------------------------------------------------ листья и помёт
def _hemi(n, rng, cone=None):
    """Случайные направления: в конусе вокруг +Z (cone, град) или по горизонту (возвышение 0…30°)."""
    out = []
    for _ in range(n):
        if cone is not None:
            ct = 1 - rng.random() * (1 - math.cos(math.radians(cone)))
            st_ = math.sqrt(max(0.0, 1 - ct * ct))
            ph = rng.random() * 2 * math.pi
            out.append(Vector((st_ * math.cos(ph), st_ * math.sin(ph), ct)))
        else:
            el = math.radians(rng.random() * 30)
            ph = rng.random() * 2 * math.pi
            out.append(Vector((math.cos(el) * math.cos(ph), math.cos(el) * math.sin(ph), math.sin(el))))
    return out


def _samples(objs, n_total, rng, min_nz):
    """Точки на гранях, смотрящих вверх (нормаль мира z > min_nz), пропорционально площади."""
    tris = []
    for o in objs:
        me = o.data
        me.calc_loop_triangles()
        M = o.matrix_world
        R = M.to_3x3()
        nv = len(me.vertices)
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(np.float64)
        Mn = np.array(M, np.float64)
        co = co @ Mn[:3, :3].T + Mn[:3, 3]
        lt = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", lt)
        lt = lt.reshape(-1, 3)
        a, b, c = co[lt[:, 0]], co[lt[:, 1]], co[lt[:, 2]]
        cr = np.cross(b - a, c - a)
        ar = np.linalg.norm(cr, axis=1) / 2
        nn = cr / np.maximum(ar[:, None] * 2, 1e-12)
        keep = (nn[:, 2] > min_nz) & (ar > 1e-6)
        if keep.any():
            tris.append((a[keep], b[keep], c[keep], nn[keep], ar[keep], o.name))
    allar = np.concatenate([t[4] for t in tris])
    total = allar.sum()
    pts = []
    for a, b, c, nn, ar, name in tris:
        k = rng.poisson(ar * n_total / total)
        idx = np.repeat(np.arange(len(ar)), k)
        if not len(idx):
            continue
        r1 = np.sqrt(rng.random(len(idx)))
        r2 = rng.random(len(idx))
        p = (1 - r1)[:, None] * a[idx] + (r1 * (1 - r2))[:, None] * b[idx] + (r1 * r2)[:, None] * c[idx]
        for q, nq in zip(p, nn[idx]):
            pts.append((Vector(q), Vector(nq), name))
    return pts


def scatter():
    import random
    reveal()
    rng = np.random.default_rng(7)
    prng = random.Random(7)
    closed = [o for o in bpy.data.collections[CLOSED].all_objects if o.type == "MESH"]
    bvh, ntri = U._bvh(closed)
    log(f"BVH: {ntri} треугольников")
    ext = [o for o in closed if o.get("ft_set") in EXTERIOR]
    up_dirs = _hemi(16, prng, cone=40)
    side_dirs = _hemi(24, prng)
    eps = 0.004

    def sky(p, n):
        o = p + n * eps
        free = sum(1 for d in up_dirs if bvh.ray_cast(o, d, 30.0)[0] is None)
        return free / len(up_dirs)

    def enclosure(p, n):
        o = p + n * 0.01
        hit = 0
        for d in side_dirs:
            h = bvh.ray_cast(o, d, 0.5)
            if h[0] is not None:
                hit += 1
        return hit / len(side_dirs)

    t0 = time.time()
    leaves = []
    cand = _samples(ext, 45000, rng, 0.55)
    log(f"листья: кандидатов {len(cand)}")
    for p, n, name in cand:
        s = sky(p, n)
        if s < 0.3:
            continue
        e = enclosure(p, n)
        # на открытом листья сдувает — лежат редко; в углах у бортов, поручней и рукавов набиваются (проба
        # 2026-11-08: при равной доле лист лёг «конфетти» по всей крыше)
        w = s * (0.012 + 1.5 * e ** 1.3)
        if p.z < 0.9:                       # у земли листья с машины сдувает меньше, но им сюда не долететь сверху
            w *= 0.5
        if prng.random() < w * 0.55:
            leaves.append({"p": list(p), "n": list(n), "s": prng.uniform(0.07, 0.15), "rot": prng.uniform(0, 6.283),
                           "k": prng.randrange(10 ** 6), "part": name, "e": round(e, 2)})
    log(f"листьев {len(leaves)} ({time.time() - t0:.0f} с)")
    # насесты: верхние точки высоко (поручни, лестница, мигалки, кромки крыши), где птице видно небо
    perches = [c for c in _samples(ext, 20000, rng, 0.8) if c[0].z > 2.6]
    prng.shuffle(perches)
    drops = []
    used = 0
    for p, n, name in perches:
        if used >= 34:
            break
        if sky(p, n) < 0.9:
            continue
        used += 1
        for _ in range(prng.randint(1, 5)):
            off = Vector((prng.gauss(0, 0.06), prng.gauss(0, 0.06), 0))
            o = p + off + Vector((0, 0, 0.25))
            h = bvh.ray_cast(o, Vector((0, 0, -1)), 4.0)
            if h[0] is None:
                continue
            q, nq = h[0], h[1]
            if nq.z < 0:
                nq = -nq
            drops.append({"p": list(q), "n": list(nq), "s": prng.uniform(0.018, 0.05), "rot": prng.uniform(0, 6.283),
                          "k": prng.randrange(10 ** 6), "perch": name})
    # одиночные — по крыше и верху кабины
    for p, n, name in _samples(ext, 900, rng, 0.85):
        if p.z > 2.4 and prng.random() < 0.06 and sky(p, n) > 0.8:
            drops.append({"p": list(p), "n": list(n), "s": prng.uniform(0.015, 0.04), "rot": prng.uniform(0, 6.283),
                          "k": prng.randrange(10 ** 6), "perch": ""})
    log(f"помёт: насестов {used}, пятен {len(drops)}")
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/scatter.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"leaves": leaves, "drops": drops}, f, ensure_ascii=False, indent=0)
    log("SCATTER DONE")


def main():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    steps = [x for x in a if x in ("maps", "scatter")] or ["maps", "scatter"]
    only = [x for x in a if x in T.SETS]
    if "maps" in steps:
        maps(only)
    if "scatter" in steps:
        scatter()


if __name__ == "__main__":
    main()
