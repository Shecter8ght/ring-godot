"""Медицинская сумка-укладка (RING_Loot_MedBag, принята 2026-11-13): игровая версия (навык godot-asset-preparation).

  blender --background --factory-startup --python-exit-code 1 --python tools/loot_containers/medbag_game.py -- lp|bake|export

Исходник не меняется: форма и отделка — models/RING_Loot_MedBag_finish_v03.blend (два состояния — закрыта и раскрыта, клапан —
узел МС_клапан с осью по задней кромке, карты high-poly в развёртке двух атласов 4096). Рабочий файл —
_asset_src/loot_containers/game_medbag/medbag_game_work.blend, карты — рядом (maps/).

  lp      — низкие сетки по деталям: корпус, клапан, карман, лента низа, стропы, металл (язычки молний), наконечники,
            перегородки, резинки — схлопыванием рёбер ОСНОВЫ (до утолщения), затем то же утолщение, что у high-poly
            (лицо и подкладка — разные стороны). Кант, строчки, спираль и тесьма молний, светоотражающая лента, окно бирки,
            нашивка, ярлык, липучки, сетка карманов геометрией не повторяются — только запекание. Форма РАСКРЫТОГО состояния
            строится первой, закрытая — смещением вершин по ближайшей вершине high (топология и развёртка общие у обоих
            состояний, поэтому карты тоже общие). Развёртка — одна на все детали, один атлас 2K.
  bake    — в атлас 2K с high-poly РАСКРЫТОГО состояния (подкладка и клапан открыты лучам, в закрытом они закрыты друг
            другом): цвет, шероховатость, металличность (через излучение, без освещения), нормаль (касательная, Cycles, 32
            выборки — плетение нити 0,85 мм мельче пикселя атласа), AO. Упаковка ORM = AO / шероховатость / металл.
  export  — две модели (lc_medbag, lc_medbag_open): корпус одной сеткой, клапан — узел с осью в шарнире (угол открытия
            и ось — в индексе, как у ящиков it_*), LOD1 ≈ ¼ (узлы *_lod1), карты WebP, индекс loot_containers_models.json.
  (сверка с high-poly — medbag_game_compare.py)

После export: tools/godot.cmd --headless --import, python -X utf8 tools/loot_containers/medbag_imports.py, --import ещё раз.
"""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector as V, kdtree

ROOT = "E:/Games/RING-godot"
LIB = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers"
SRC = LIB + "/models/RING_Loot_MedBag_finish_v03.blend"
GAME_BLEND = LIB + "/models/RING_Loot_MedBag_game_v01.blend"
WORK = ROOT + "/_asset_src/loot_containers/game_medbag"
WORK_BLEND = WORK + "/medbag_game_work.blend"
MAPS = WORK + "/maps"
OUT = ROOT + "/assets/models/loot_containers"
TEX = OUT + "/textures"
SHOTS = LIB + "/Просмотр/medbag_v02"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SIZE = 2048
MODEL = "lc_medbag"
FLAP = "клапан"
LOD1_RATIO = 0.25
# имя детали → (целевое число треугольников ОСНОВЫ до утолщения, группа: body — к корпусу, flap — к клапану)
PARTS = [
    ("МС_корпус", 1500, "body"), ("МС_карман", 320, "body"), ("МС_лента_низа", 420, "body"), ("МС_стропы", 800, "body"),
    ("МС_металл", 420, "body"), ("МС_наконечники", 150, "body"), ("МС_перегородки", 90, "body"),
    ("МС_резинки", 110, "body"), ("МС_клапан", 600, "flap"), ("МС_резинки_клапан", 120, "flap"),
]
ROOTS = {False: "МС_сумка_укладка", True: "МС_сумка_укладка_раскрыта"}


def hi(name: str, opened: bool):
    return bpy.data.objects[name + (".001" if opened else "")]


def tris(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def coords(me) -> np.ndarray:
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def eval_co(ob) -> np.ndarray:
    """Вершины с модификаторами, в осях объекта."""
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.to_mesh()
    c = coords(me)
    e.to_mesh_clear()
    return c


def copy_props(src, dst) -> None:
    for p in src.bl_rna.properties:
        if p.is_readonly or p.identifier in ("name", "type"):
            continue
        try:
            setattr(dst, p.identifier, getattr(src, p.identifier))
        except Exception:
            pass


def low_mesh(ob, target: int):
    """Низкая сетка детали: схлопывание рёбер основы до target треугольников, затем то же утолщение, что у high-poly."""
    n = tris(ob.data)
    tmp = bpy.data.objects.new("tmp", ob.data.copy())
    bpy.context.scene.collection.objects.link(tmp)
    if n > target:
        md = tmp.modifiers.new("dec", "DECIMATE")
        md.decimate_type = "COLLAPSE"
        md.ratio = max(0.003, target / n)
        md.use_collapse_triangulate = True
    for m in ob.modifiers:
        if m.type == "SOLIDIFY":
            copy_props(m, tmp.modifiers.new("sol", "SOLIDIFY"))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(tmp)
    me.materials.clear()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    return me


def displaced(me, open_co: np.ndarray, closed_co: np.ndarray):
    """Копия низкой сетки раскрытого состояния, сдвинутая в закрытое: каждая вершина берёт сдвиг ближайшей вершины high."""
    kd = kdtree.KDTree(len(open_co))
    for i, p in enumerate(open_co):
        kd.insert(p, i)
    kd.balance()
    out = me.copy()
    co = coords(out)
    for i, p in enumerate(co):
        _, j, _ = kd.find(p)
        co[i] = p + (closed_co[j] - open_co[j])
    out.vertices.foreach_set("co", co.ravel())
    out.update()
    return out


def stage_lp() -> None:
    bpy.ops.wm.open_mainfile(filepath=SRC)
    sc = bpy.context.scene
    coll = bpy.data.collections.new("Игровая_низкая")
    sc.collection.children.link(coll)
    meshes = {}   # (имя, состояние) → сетка в осях объекта детали
    for name, target, grp in PARTS:
        ho, hc = hi(name, True), hi(name, False)
        co_o, co_c = eval_co(ho), eval_co(hc)
        assert co_o.shape == co_c.shape, name
        mo = low_mesh(ho, target)
        mc = displaced(mo, co_o, co_c)
        meshes[(name, True)], meshes[(name, False)] = mo, mc
        print("ДЕТАЛЬ", name, "основа", tris(ho.data), "→ после утолщения", tris(mo), "сдвиг до", round(float(np.abs(co_c - co_o).max()), 4), flush=True)
    # одна развёртка: сетки раскрытого состояния склеиваются, раскладываются, UV возвращаются по номеру петли
    bm = bmesh.new()
    order = []
    for name, _, _ in PARTS:
        order.append((name, len(meshes[(name, True)].loops)))
        bm.from_mesh(meshes[(name, True)])
    jm = bpy.data.meshes.new("J")
    bm.to_mesh(jm)
    bm.free()
    jm.uv_layers.new(name="UVMap")
    J = bpy.data.objects.new("J", jm)
    coll.objects.link(J)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    J.select_set(True)
    bpy.context.view_layer.objects.active = J
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = np.empty(len(jm.loops) * 2, np.float32)
    jm.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    off = 0
    for name, nl in order:
        for opened in (True, False):
            me = meshes[(name, opened)]
            assert len(me.loops) == nl, (name, opened)
            me.uv_layers.new(name="UVMap")
            me.uv_layers["UVMap"].data.foreach_set("uv", uv[off:off + nl].ravel())
        off += nl
    # плотность: пикселей атласа на мм поверхности
    a3 = sum(sum(p.area for p in meshes[(n, True)].polygons) for n, _, _ in PARTS)
    au = 0.0
    for p in jm.polygons:
        pts = [uv[jm.loops[k].index] for k in p.loop_indices]
        s = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            s += x1 * y2 - x2 * y1
        au += abs(s) * 0.5
    print("РАЗВЁРТКА: площадь поверхности %.3f м², занято атласа %.1f %%, плотность %.2f пикс/мм" % (a3, au * 100, math.sqrt(au * SIZE * SIZE / (a3 * 1e6))), flush=True)
    bpy.data.objects.remove(J)
    bpy.data.meshes.remove(jm)
    # объекты состояний: те же родители и позы, что у high-poly (запекание — в мировых осях, как они стоят в файле)
    for opened in (True, False):
        root = bpy.data.objects[ROOTS[opened]]
        hf = hi("МС_клапан", opened)
        fl = bpy.data.objects.new("низк_клапан" + (".o" if opened else ".c"), None)
        coll.objects.link(fl)
        fl.parent = root
        fl.matrix_parent_inverse = hf.matrix_parent_inverse.copy()
        fl.matrix_basis = hf.matrix_basis.copy()
        for name, _, grp in PARTS:
            me = meshes[(name, opened)]
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
            me.set_sharp_from_angle(angle=math.radians(60))  # бинормаль Godot — в вершинах: круче 60° — жёстко
            me.name = "низк:" + name + (".o" if opened else ".c")
            ob = bpy.data.objects.new(me.name, me)
            coll.objects.link(ob)
            h = hi(name, opened)
            ob.parent = fl if grp == "flap" else root
            ob.matrix_parent_inverse = h.matrix_parent_inverse.copy() if grp == "body" else Matrix.Identity(4)
            ob.matrix_basis = h.matrix_basis.copy() if grp == "body" else Matrix.Identity(4)
            ob["part"] = name
            ob["group"] = grp
            ob["opened"] = opened
    # сами high-poly закрытого состояния и подвижные узлы остаются как есть — для сверки
    os.makedirs(WORK, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=WORK_BLEND, compress=True)
    print("saved", WORK_BLEND)


# ------------------------------------------------------------------ запекание

def emit_variant(mat, kind: str):
    """Копия материала high-poly, где излучение несёт одно свойство Principled: цвет, шероховатость или металличность
    (кроме прозрачных мест: там лучи идут дальше, как в настоящем материале)."""
    m = mat.copy()
    nt = m.node_tree
    bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    sock = {"color": "Base Color", "rough": "Roughness", "metal": "Metallic"}[kind]
    inp = bs.inputs[sock]
    em = nt.nodes.new("ShaderNodeEmission")
    if inp.links:
        nt.links.new(inp.links[0].from_socket, em.inputs["Color"])
    else:
        v = inp.default_value
        em.inputs["Color"].default_value = tuple(v) if hasattr(v, "__len__") else (v, v, v, 1.0)
    shader = em.outputs["Emission"]
    al = bs.inputs["Alpha"]
    if al.links:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(al.links[0].from_socket, mx.inputs["Fac"])
        nt.links.new(tr.outputs["BSDF"], mx.inputs[1])
        nt.links.new(em.outputs["Emission"], mx.inputs[2])
        shader = mx.outputs["Shader"]
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    nt.links.new(shader, out.inputs["Surface"])
    m.surface_render_method = "DITHERED"
    return m


def stage_bake() -> None:
    bpy.ops.wm.open_mainfile(filepath=WORK_BLEND)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    os.makedirs(MAPS, exist_ok=True)
    highs = [hi(n, True) for n in set(o.name.rsplit(".", 1)[0] for o in bpy.data.objects if o.type == "MESH" and o.name.endswith(".001") and not o.name.startswith("низк"))]
    lows = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("низк:") and o["opened"]]
    # скрыть всё лишнее: закрытое состояние high и закрытые низкие сетки лучам не нужны
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in highs and o not in lows:
            o.hide_render = True
            o.hide_viewport = True
    orig = {h: [m for m in h.data.materials] for h in highs}
    variants = {}
    for k in ("color", "rough", "metal"):
        variants[k] = {m.name: emit_variant(m, k) for m in {m for ms in orig.values() for m in ms if m}}
    tgt = bpy.data.materials.new("запекание")
    tgt.use_nodes = True
    node = tgt.node_tree.nodes.new("ShaderNodeTexImage")
    tgt.node_tree.nodes.active = node
    for lo in lows:
        lo.data.materials.clear()
        lo.data.materials.append(tgt)

    def bake(label: str, btype: str, mats: str | None, colorspace: str, samples: int, extra: dict) -> np.ndarray:
        for h in highs:
            for i, m in enumerate(orig[h]):
                h.data.materials[i] = variants[mats][m.name] if mats else m
        img = bpy.data.images.new("b_" + label, SIZE, SIZE, alpha=False, float_buffer=(colorspace != "sRGB"))
        img.colorspace_settings.name = colorspace
        node.image = img
        sc.cycles.samples = samples
        first = True
        for lo in lows:
            for o in bpy.context.view_layer.objects:
                o.select_set(False)
            for h in highs:
                h.select_set(True)
            lo.select_set(True)
            bpy.context.view_layer.objects.active = lo
            bpy.ops.object.bake(type=btype, use_selected_to_active=True, cage_extrusion=0.012, max_ray_distance=0.03,
                                margin=6, use_clear=first, **extra)
            first = False
        px = np.empty(SIZE * SIZE * 4, np.float32)
        img.pixels.foreach_get(px)
        print("запечено", label, flush=True)
        return px.reshape(SIZE, SIZE, 4)[..., :3].copy()

    color = bake("color", "EMIT", "color", "sRGB", 24, {})
    rough = bake("rough", "EMIT", "rough", "Non-Color", 24, {})
    metal = bake("metal", "EMIT", "metal", "Non-Color", 24, {})
    normal = bake("normal", "NORMAL", None, "Non-Color", 32, {"normal_space": "TANGENT"})
    sc.world.light_settings.distance = 0.04
    ao = bake("ao", "AO", None, "Non-Color", 48, {})
    for h in highs:
        for i, m in enumerate(orig[h]):
            h.data.materials[i] = m
    np.save(MAPS + "/color.npy", color)
    np.save(MAPS + "/rough.npy", rough)
    np.save(MAPS + "/metal.npy", metal)
    np.save(MAPS + "/normal.npy", normal)
    np.save(MAPS + "/ao.npy", ao)
    orm = np.stack([ao[..., 0], rough[..., 0], metal[..., 0]], -1)
    for fn, arr, cs in (("baseColor", color, "sRGB"), ("occlusionRoughnessMetallic", orm, "Non-Color"), ("normal", normal, "Non-Color")):
        im = bpy.data.images.new("out_" + fn, SIZE, SIZE, alpha=False)
        im.colorspace_settings.name = cs
        a = np.ones((SIZE, SIZE, 4), np.float32)
        a[..., :3] = np.clip(arr, 0, 1)
        im.pixels.foreach_set(a.ravel())
        im.filepath_raw = f"{MAPS}/{MODEL}_{fn}.png"
        im.file_format = "PNG"
        im.save()
        print("карта", fn, "среднее", [round(float(x), 3) for x in arr.reshape(-1, 3).mean(0)], flush=True)


# ------------------------------------------------------------------ экспорт

def gd(v) -> list[float]:
    """Точка Blender → оси Godot (y вверх, z = −y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def material():
    m = bpy.data.materials.get(MODEL) or bpy.data.materials.new(MODEL)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL", "BSDF_PRINCIPLED"):
            nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def img(suffix, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(f"{MAPS}/{MODEL}_{suffix}.png", check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        return n
    nt.links.new(img("baseColor", False).outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("occlusionRoughnessMetallic", True).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def join(objs: list, name: str):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def decimate_copy(ob, ratio: float, name: str):
    c = ob.copy()
    c.data = ob.data.copy()
    bpy.context.scene.collection.objects.link(c)
    md = c.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = ratio
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(c.evaluated_get(dg), depsgraph=dg)
    c.modifiers.remove(md)
    old = c.data
    c.data = me
    bpy.data.meshes.remove(old)
    c.name = name
    c.data.name = name
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.set_sharp_from_angle(angle=math.radians(60))
    return c


def build_state(opened: bool, mat):
    """Итоговая модель состояния: корень в начале координат, корпус одной сеткой, клапан — узел в шарнире (+ _lod1)."""
    suffix = ".o" if opened else ".c"
    root = bpy.data.objects.new(MODEL + ("_open" if opened else ""), None)
    bpy.context.scene.collection.objects.link(root)
    fl_src = bpy.data.objects["низк_клапан" + suffix]
    body = [o for o in bpy.data.objects if o.get("part") and o["opened"] == opened and o["group"] == "body"]
    flap = [o for o in bpy.data.objects if o.get("part") and o["opened"] == opened and o["group"] == "flap"]
    # копии: исходные низкие сетки остаются в файле
    def dup(o):
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        return c
    body_c = [dup(o) for o in body]
    flap_c = [dup(o) for o in flap]
    for c in body_c + flap_c:
        c.data.materials.clear()
        c.data.materials.append(mat)
    for c in body_c:
        c.parent = None
        c.matrix_world = Matrix.Identity(4)
    flap_basis = bpy.data.objects[ROOTS[opened]].matrix_world.inverted() @ fl_src.matrix_world
    for c in flap_c:
        c.parent = None
        c.matrix_world = Matrix.Identity(4)
    jb = join(body_c, "корпус")
    jf = join(flap_c, FLAP)
    # у клапана вершины — в его осях: объект в шарнире
    jf.parent = root
    jf.matrix_parent_inverse = Matrix.Identity(4)
    jf.matrix_world = flap_basis
    jb.parent = root
    jb.matrix_parent_inverse = Matrix.Identity(4)
    jb.matrix_world = Matrix.Identity(4)
    # вершины корпуса были в осях корня состояния (у раскрытого корень стоял в x = 0,95): вернуть в начало
    root_src = bpy.data.objects[ROOTS[opened]]
    jb.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    lod_b = decimate_copy(jb, LOD1_RATIO, "корпус_lod1")
    lod_f = decimate_copy(jf, LOD1_RATIO, FLAP + "_lod1")
    for c, src in ((lod_b, jb), (lod_f, jf)):
        c.parent = root
        c.matrix_parent_inverse = Matrix.Identity(4)
        c.matrix_basis = src.matrix_basis.copy()
    bpy.context.view_layer.update()
    return root, jb, jf, lod_b, lod_f, root_src


def stage_export() -> None:
    bpy.ops.wm.open_mainfile(filepath=WORK_BLEND)
    os.makedirs(TEX, exist_ok=True)
    mat = material()
    idx_path = OUT + "/loot_containers_models.json"
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    for opened in (False, True):
        for o in bpy.data.objects:
            if o.type == "MESH" and not o.name.startswith("низк") and not o.get("part"):
                o.hide_viewport = True
                o.hide_render = True
        root, jb, jf, lb, lf, root_src = build_state(opened, mat)
        name = root.name
        movers = []
        if opened:
            # закрытая поза клапана — поворот открытого вокруг оси узла: ось X, закрывает +угол (в Godot — те же оси X)
            fl_o = bpy.data.objects["низк_клапан.o"]
            fl_c = bpy.data.objects["низк_клапан.c"]
            rel = fl_o.matrix_world.to_3x3().inverted() @ fl_c.matrix_world.to_3x3()
            ang = math.degrees(rel.to_euler()[0])
            print("поворот закрыто относительно раскрыто (X), °:", round(ang, 2), flush=True)
            pivot = gd(fl_o.matrix_world.translation - root_src.matrix_world.translation)
            for nm in (FLAP, FLAP + "_lod1"):
                movers.append({"node": nm, "kind": "hinge", "pivot": pivot, "axis": [-1.0, 0.0, 0.0], "open": round(abs(ang), 2)})
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        root.select_set(True)
        for c in root.children_recursive:
            c.select_set(True)
        bpy.context.view_layer.objects.active = root
        bpy.ops.export_scene.gltf(filepath=f"{OUT}/{name}.gltf", export_format="GLTF_SEPARATE", export_texture_dir="textures",
                                  use_selection=True, export_yup=True, export_apply=True, export_texcoords=True,
                                  export_normals=True, export_tangents=True, export_materials="EXPORT", export_image_format="WEBP",
                                  export_image_quality=92, export_cameras=False, export_lights=False, export_animations=False)
        pts = []
        for c in (jb, jf):
            pts += [c.matrix_world @ v.co for v in c.data.vertices]
        glo = gd([min(p[i] for p in pts) for i in range(3)])
        ghi = gd([max(p[i] for p in pts) for i in range(3)])
        lo, hi_ = [min(glo[i], ghi[i]) for i in range(3)], [max(glo[i], ghi[i]) for i in range(3)]
        t0 = tris(jb.data) + tris(jf.data)
        t1 = tris(lb.data) + tris(lf.data)
        entry = {"file": f"res://assets/models/loot_containers/{name}.gltf", "triangles": t0, "triangles_lod1": t1,
                 "aabb": {"center": [round((lo[i] + hi_[i]) / 2, 4) for i in range(3)], "size": [round(hi_[i] - lo[i], 4) for i in range(3)]},
                 "material": MODEL, "variants": [""]}
        if movers:
            entry["movers"] = movers
        index[name] = entry
        print("MODEL", name, "LOD0", t0, "LOD1", t1, entry["aabb"], flush=True)
        for c in [root] + list(root.children_recursive):
            c.name = "готово:" + c.name
    with open(idx_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    bpy.ops.wm.save_as_mainfile(filepath=GAME_BLEND, copy=True, compress=True)
    print("saved", GAME_BLEND)


if argv and argv[0] == "lp":
    stage_lp()
elif argv and argv[0] == "bake":
    stage_bake()
elif argv and argv[0] == "export":
    stage_export()
