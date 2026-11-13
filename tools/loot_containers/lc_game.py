"""Контейнеры лута (принятые 2026-11-13): игровые версии шести предметов — сейф, ячейка, оружейный шкаф, картотека, касса, аптечка.

  blender --background --factory-startup --python-exit-code 1 --python tools/loot_containers/lc_game.py -- <предмет|all> [lp] [bake] [export]

Предмет: lc_safe, lc_cell, lc_gun, lc_file, lc_cash, lc_aid. Без стадий — все три. Источник — RING_Loot_Containers_uv_v01.blend
(детали high-poly в развёртке v01, коллекции <предмет> — открыто и <предмет>__closed — закрыто, детали «c:<имя>») и карты принятой
отделки v03 (textures/finish_v03/<предмет>/). Исходники не меняются; рабочий файл и карты — _asset_src/loot_containers/game_<предмет>/.

  lp     — низкие сетки деталей раскрытого состояния (схлопывание рёбер до бюджета, веса по важности детали; плоские
           наклейки и шильдики запекаются в поверхность), закрытое состояние — жёстким переносом каждой детали (у всех
           подвижных перемещений жёсткие: ошибка 0), развёртка укладчиком проекта в один атлас на оба состояния.
  bake   — карты в атлас с high раскрытого: цвет, шероховатость, металл, AO — переносом карт v03 (излучением, без света),
           нормаль — касательная, с геометрией и картой нормалей high; у кассы ещё излучение цифр индикаторов.
  export — две модели (<предмет> и <предмет>_open): закрытая — одна сетка; раскрытая — неподвижное + узлы подвижных деталей
           (шарнир: ось, угол; выдвижное: ось, ход — в индексе movers), LOD1 ≈ ¼ (узлы *_lod1), WebP, loot_containers_models.json.

После export: tools/godot.cmd --headless --import, python -X utf8 tools/loot_containers/medbag_imports.py, --import ещё раз.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lc_game_lib as G  # noqa: E402

SRC = G.LIB + "/models/RING_Loot_Containers_uv_v01.blend"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

# бюджет треугольников на состояние, атлас, имена подвижных узлов (деталь → узел), веса важности (по подстроке в имени детали)
ITEMS = {
    "lc_safe": dict(budget=4900, size=2048, margin=6, names={"СН_дверца": "дверца", "СН_ручка_штурвал": "штурвал", "СН_трейзер_дверца": "трейзер"}),
    "lc_cell": dict(budget=2400, size=1024, margin=5, angle=60, names={"СЯ_дверца": "дверца", "СЯ_ручка": "ручка"}),
    "lc_gun": dict(budget=5900, size=2048, margin=6, names={"ОШ_створка_лев": "створка_лев", "ОШ_створка_прав": "створка_прав",
                                                         "ОШ_ручка_замок": "ручка_замок"}),
    "lc_file": dict(budget=4900, size=2048, margin=6, names={"КШ_ящик_второй_коробка": "ящик"}),
    "lc_cash": dict(budget=7900, size=2048, margin=6, names={"КМ_лоток_коробка": "лоток", "КМ_дисплей_покупателя": "дисплей"}),
    "lc_aid": dict(budget=1900, size=1024, margin=5, names={"АП_дверца": "дверца", "АП_защёлка": "защёлка"}),
}
# детали, которых в игре можно упростить сильнее (скрытое, мелкое, повторяющееся)
LOW_W = ("петли", "петля", "механизм", "тяги", "проушины", "скоба", "ригел", "замок", "рейки", "направляющая", "шкала", "трейзер",
         "войлок", "накладка", "ножки", "полка", "ложемент", "прижимы", "рельсы", "вставка", "клавиатура", "ярлык")
DROP_TRIS = 16          # плоские наклейки и шильдики: в сетке не нужны, рисунок — в карте
MOVE_MIN = 0.03         # детали, сместившиеся меньше (стержни петель), неподвижные: в каждом состоянии — своя поза
EMISSIVE = ("lc_cash",)


def key(o) -> str:
    n = o.name[2:] if o.name.startswith("c:") else o.name
    return n.split(".")[0] if n.rsplit(".", 1)[-1].isdigit() else n


def work_dir(item: str) -> str:
    d = f"{G.ROOT}/_asset_src/loot_containers/game_{item}"
    os.makedirs(d, exist_ok=True)
    return d


def weight(k: str) -> float:
    return 0.3 if any(w in k for w in LOW_W) else 1.0


# ------------------------------------------------------------------ lp

def stage_lp(item: str) -> None:
    cfg = dict(ITEMS[item])
    if os.environ.get("LC_OVR"):     # LC_OVR='{"angle": 75, "budget": 1850}' — пробы укладки без правки таблицы
        import json
        cfg.update(json.loads(os.environ["LC_OVR"]))
    bpy.ops.wm.open_mainfile(filepath=SRC)
    top = bpy.data.collections["Развёртка_v01"]
    for c in [top] + list(top.children):
        c.hide_viewport = False
        c.hide_render = False
    sc = bpy.context.scene
    ho = {key(o): o for o in bpy.data.collections[item].objects if o.type == "MESH"}
    hc = {key(o): o for o in bpy.data.collections[item + "__closed"].objects if o.type == "MESH"}
    coll = bpy.data.collections.new("Игровая_низкая")
    sc.collection.children.link(coll)
    # жёсткое перемещение закрытое ← раскрытое по деталям
    T = {}
    for k, o in ho.items():
        if k in hc:
            a, b = G.coords(o.data), G.coords(hc[k].data)
            if a.shape != b.shape:
                raise RuntimeError("другая топология " + k)
            if float(np.abs(a - b).max()) < 1e-6:
                T[k] = (np.eye(3), np.zeros(3), 0.0, 0.0)
            else:
                r, t, err = G.rigid(a, b)
                assert err < 1e-3, (k, err)
                T[k] = (r, t, err, float(np.abs(a - b).max()))
    parts = [k for k, o in ho.items() if G.tris(o.data) > DROP_TRIS]
    total = sum(G.tris(ho[k].data) for k in parts)
    # масштаб подбирается: число треугольников после схлопывания не равно цели
    scale = cfg["budget"] / total
    for _ in range(6):
        meshes = {}
        for k in parts:
            n = G.tris(ho[k].data)
            target = int(max(12, min(n, n * scale * weight(k))))
            meshes[k] = G.low_mesh(ho[k], target, solidify=False)
        got = sum(G.tris(m) for m in meshes.values())
        print("ПОДБОР масштаб %.3f → %d (бюджет %d)" % (scale, got, cfg["budget"]), flush=True)
        if got <= cfg["budget"] and got >= cfg["budget"] * 0.9:
            break
        for m in meshes.values():
            bpy.data.meshes.remove(m)
        scale *= (cfg["budget"] * 0.96) / max(got, 1)
    low_o, low_c = [], []
    for k in parts:
        o = bpy.data.objects.new("низк:" + k, meshes[k])
        meshes[k].name = "низк:" + k
        coll.objects.link(o)
        o["part"] = k
        low_o.append(o)
    G.layout_uv(low_o, cfg["size"], margin=cfg["margin"], group_margin=max(2, cfg["margin"] // 2), angle_deg=cfg.get("angle", 80.0), score="top", order="side", precision=0.002)
    G.finish_shading(low_o)
    for k, o in zip(parts, low_o):
        print("ДЕТАЛЬ", k, "high", G.tris(ho[k].data), "→", G.tris(o.data), flush=True)
        if k in hc:
            r, t, _, d = T[k]
            me = G.apply_rigid(o.data, r, t)
            me.name = "низк_з:" + k
            c = bpy.data.objects.new("низк_з:" + k, me)
            coll.objects.link(c)
            c["part"] = k
            low_c.append(c)
            c["move"] = d
            c["R"] = [float(x) for x in r.ravel()]
            c["t"] = [float(x) for x in t]
    G.pack_uv_to_twin([o for o in low_o if o["part"] in hc], low_c)
    print("ИТОГО %s: LOD0 раскрыто %d, закрыто %d" % (item, sum(G.tris(o.data) for o in low_o), sum(G.tris(o.data) for o in low_c)), flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=work_dir(item) + "/work.blend", compress=True)


# ------------------------------------------------------------------ bake

def hi_material(item: str, maps_dir: str, kind: str):
    m = bpy.data.materials.new("hi_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")

    def tex(suffix, srgb):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(f"{maps_dir}/{item}_{suffix}.png", check_existing=True)
        t.image.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
        t.interpolation = "Linear"
        return t
    if kind == "normal":
        bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex("normal", False).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
        nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
        return m
    em = nt.nodes.new("ShaderNodeEmission")
    if kind == "color":
        nt.links.new(tex("baseColor", True).outputs["Color"], em.inputs["Color"])
    elif kind == "emissive":
        nt.links.new(tex("emissive", True).outputs["Color"], em.inputs["Color"])
    else:
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex("occlusionRoughnessMetallic", False).outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs[{"ao": "Red", "rough": "Green", "metal": "Blue"}[kind]], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def stage_bake(item: str) -> None:
    cfg = ITEMS[item]
    size = cfg["size"]
    bpy.ops.wm.open_mainfile(filepath=work_dir(item) + "/work.blend")
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    maps_src = f"{G.LIB}/textures/finish_v03/{item}"
    highs = [o for o in bpy.data.collections[item].objects if o.type == "MESH"]
    lows = [o for o in bpy.data.objects if o.name.startswith("низк:")]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in highs and o not in lows:
            o.hide_render = True
            o.hide_viewport = True
    for o in highs + lows:
        o.hide_render = False
        o.hide_viewport = False
    for lo in lows:
        lo.data.uv_layers["GameUV"].active_render = True
    G.bake_target_material(lows)
    kinds = ["color", "rough", "metal", "ao", "normal"] + (["emissive"] if item in EMISSIVE else [])
    mats = {k: hi_material(item, maps_src, k) for k in kinds}
    orig = {h: [m for m in h.data.materials] for h in highs}

    def prep(kind):
        def f():
            for h in highs:
                h.data.materials.clear()
                h.data.materials.append(mats[kind])
        return f

    def restore():
        for h in highs:
            h.data.materials.clear()
            for m in orig[h]:
                h.data.materials.append(m)

    def run(kind, btype, samples, srgb, extra=None):
        return G.bake_image(kind, btype, size, highs, lows, samples, prep(kind), restore, srgb=srgb, extra=extra,
                            extrusion=0.008, max_dist=0.02, margin=3)
    color = run("color", "EMIT", 16, True)
    rough = run("rough", "EMIT", 16, False)
    metal = run("metal", "EMIT", 16, False)
    ao = run("ao", "EMIT", 16, False)
    normal = run("normal", "NORMAL", 32, False, {"normal_space": "TANGENT"})
    emissive = run("emissive", "EMIT", 16, True) if item in EMISSIVE else None
    G.write_maps(work_dir(item) + "/maps", item, size, color, rough, metal, normal, ao, emissive)
    bpy.ops.wm.save_as_mainfile(filepath=work_dir(item) + "/work_baked.blend", compress=True)


# ------------------------------------------------------------------ export

def cluster_movers(low_c: list) -> list:
    """Подвижные детали (смещение ≥ MOVE_MIN) — по одинаковому жёсткому перемещению."""
    out = []
    for o in low_c:
        if o["move"] < MOVE_MIN:
            continue
        r, t = np.array(o["R"]).reshape(3, 3), np.array(o["t"])
        for c in out:
            if np.abs(c["R"] - r).max() < 1e-3 and np.abs(c["t"] - t).max() < 2e-3:
                c["parts"].append(o)
                break
        else:
            out.append({"R": r, "t": t, "parts": [o]})
    return out


def hinge_of(r: np.ndarray, t: np.ndarray):
    """Закрытое = R · раскрытое + t: ось, угол (0…180°) и точка оси (Blender)."""
    ang = math.acos(max(-1.0, min(1.0, (np.trace(r) - 1) / 2)))
    if ang < math.radians(1.0):
        return None
    w = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]])
    axis = w / np.linalg.norm(w)
    p = np.linalg.lstsq(np.eye(3) - r, t, rcond=None)[0]
    p = p - axis * float(p @ axis)    # ближайшая к началу координат точка оси
    return axis, math.degrees(ang), p


def stage_export(item: str) -> None:
    cfg = ITEMS[item]
    bpy.ops.wm.open_mainfile(filepath=work_dir(item) + "/work_baked.blend")
    sc = bpy.context.scene
    maps_dir = work_dir(item) + "/maps"
    os.makedirs(G.TEX, exist_ok=True)
    mat = G.game_material(item, maps_dir, emissive=item in EMISSIVE)
    low_o = [o for o in bpy.data.objects if o.name.startswith("низк:")]
    low_c = [o for o in bpy.data.objects if o.name.startswith("низк_з:")]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in low_o and o not in low_c:
            o.hide_render = True
            o.hide_viewport = True
    entries = {}

    def dup(o):
        c = o.copy()
        c.data = o.data.copy()
        c.data.materials.clear()
        c.data.materials.append(mat)
        c.hide_viewport = False
        c.hide_render = False
        sc.collection.objects.link(c)
        c.hide_set(False)
        return c

    def lod(ob, name, parent, basis=None):
        lo = G.decimate_copy(ob, G.LOD1_RATIO, name)
        lo.data.polygons.foreach_set("use_smooth", [True] * len(lo.data.polygons))
        lo.parent = parent
        lo.matrix_parent_inverse = Matrix.Identity(4)
        lo.matrix_basis = (basis if basis is not None else ob.matrix_basis).copy()
        return lo
    clusters = cluster_movers(low_c)
    movers_of = {id(p): i for i, c in enumerate(clusters) for p in c["parts"]}
    for opened in (False, True):
        name = item + ("_open" if opened else "")
        root = bpy.data.objects.new(name, None)
        sc.collection.objects.link(root)
        src = low_o if opened else low_c
        nodes = []
        if opened:
            mover_keys = {p["part"] for c in clusters for p in c["parts"]}
            static = [o for o in low_o if o["part"] not in mover_keys]
        else:
            static = src
        body = G.join([dup(o) for o in static], "корпус")
        body.parent = root
        body.matrix_parent_inverse = Matrix.Identity(4)
        body.matrix_world = Matrix.Identity(4)
        lb = lod(body, "корпус_lod1", root)
        nodes += [body]
        t0, t1 = G.tris(body.data), G.tris(lb.data)
        movers = []
        if opened:
            for i, c in enumerate(clusters):
                pk = [p["part"] for p in c["parts"]]
                nm = next((v for k, v in cfg["names"].items() if k in pk), f"подвижное{i + 1}")
                members = [dup(next(o for o in low_o if o["part"] == p["part"])) for p in c["parts"]]
                node = G.join(members, nm)
                h = hinge_of(c["R"], c["t"])
                if h is not None:
                    axis_b, ang, p = h
                    pivot = V(p)
                    axis_g = [-x for x in G.gd(axis_b)]
                    kind, amount = "hinge", round(ang, 2)
                else:
                    tv = c["t"]
                    L = float(np.linalg.norm(tv))
                    pivot = V(np.mean([np.array(v.co) for v in node.data.vertices], axis=0))
                    axis_g = G.gd(-tv / L)
                    kind, amount = "slide", round(L, 4)
                node.data.transform(Matrix.Translation(-pivot))
                node.parent = root
                node.matrix_parent_inverse = Matrix.Identity(4)
                node.location = pivot
                ln = lod(node, nm + "_lod1", root)
                for n_ in (nm, nm + "_lod1"):
                    movers.append({"node": n_, "kind": kind, "pivot": G.gd(pivot), "axis": [round(x, 4) for x in axis_g], "open": amount})
                nodes.append(node)
                t0 += G.tris(node.data)
                t1 += G.tris(ln.data)
                print("ПОДВИЖНОЕ", nm, kind, amount, "деталей", len(pk), "треуг.", G.tris(node.data), flush=True)
        bpy.context.view_layer.update()
        G.export_gltf(root, name)
        e = {"file": f"res://assets/models/loot_containers/{name}.gltf", "triangles": t0, "triangles_lod1": t1,
             "aabb": G.aabb_of(nodes), "material": item, "variants": [""]}
        if movers:
            e["movers"] = movers
        entries[name] = e
        print("MODEL", name, "LOD0", t0, "LOD1", t1, e["aabb"], flush=True)
        for c in [root] + list(root.children_recursive):
            c.name = "готово:" + c.name
    G.write_index(entries)


for it in (list(ITEMS) if (argv and argv[0] == "all") else argv[:1]):
    stages = [a for a in argv[1:] if a in ("lp", "bake", "export")] or ["lp", "bake", "export"]
    for st in stages:
        {"lp": stage_lp, "bake": stage_bake, "export": stage_export}[st](it)
