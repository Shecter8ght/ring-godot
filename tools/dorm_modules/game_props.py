"""Игровые версии оставленного света, мусора и обломков общежития (навык godot-asset-preparation): упрощённая сетка,
карты 512 / 1K, glTF в assets/models/dorm/props. Бюджет — «экономно» (владелец 2026-10-31): мелочь скрывается
дальше ~10 м, ступени детализации — автоматические при импорте Godot.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_FoundLights_uv_v01.blend | RING_Dorm_Clutter_uv_v01.blend |
      RING_Dorm_Bags_uv_v01.blend>" --python-exit-code 1 --python tools/dorm_modules/game_props.py -- props [вещь …]
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Rubble_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/game_props.py -- rubble [вещь …]

props: сетки развёртки (коллекция «Развёртка_v01/<вещь>», в осях корня) — копия, этикетки без оборота, упрощение
схлопыванием рёбер с той же развёрткой → карты Painter (отделка, печать, износ — _asset_src/<набор>/maps) просто
уменьшаются, рельеф high-poly и его карта нормалей запекаются в нормали низкой сетки (Cycles на процессоре).
Стекло (линзы, рассеиватель, трубка) и светящееся (светодиод, пламя) — свои материалы «<вещь>_стекло» / «<вещь>_свет»
(стенд делает их прозрачными и светящимися), нагар, табак и нутро банки — «<вещь>_<деталь>» простым цветом.
rubble: обломки — сетка упрощается, развёртка заново, цвет, шероховатость и нормали запекаются с фотоматериалов.
Низкие сетки сохраняются копией рядом с исходником: <файл>_game_v01.blend.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = "E:/Games/RING-godot"
OUT = ROOT + "/assets/models/dorm/props"
SRC = {"found": ROOT + "/_asset_src/dorm_found_lights/maps", "clutter": ROOT + "/_asset_src/dorm_clutter/maps"}
# вещь: (набор карт, треугольников у низкой сетки, размер карт)
PROPS = {
    "found_flashlight": ("found", 1400, 512), "found_headlamp": ("found", 1200, 512), "found_chemlight": ("found", 600, 512),
    "found_lantern": ("found", 1600, 1024), "found_candles": ("found", 2000, 1024), "found_beacon": ("found", 2000, 1024),
    "clutter_can": ("clutter", 700, 512), "clutter_can_dented": ("clutter", 900, 512), "clutter_can_crushed": ("clutter", 900, 512),
    "clutter_bottle_vodka": ("clutter", 1400, 1024), "clutter_bottle_vodka_worn": ("clutter", 1400, 1024),
    "clutter_bottle_beer": ("clutter", 1400, 1024), "clutter_bottle_broken": ("clutter", 800, 1024),
    "clutter_butts": ("clutter", 2600, 1024), "clutter_casings": ("clutter", 1600, 512),
    "clutter_bag_full": ("clutter", 3000, 1024), "clutter_bag_lying": ("clutter", 3000, 1024), "clutter_bag_half": ("clutter", 3000, 1024),
}
# обломок: (корень, треугольников, размер карт)
RUBBLE = {
    "rubble_wall": ("CL_глыба_стена_в_кирпич", 3000, 1024), "rubble_partition": ("CL_глыба_перегородка", 2200, 1024),
    "rubble_bricks": ("CL_кирпичи", 1600, 1024), "rubble_slab": ("CL_плита_обломок", 1600, 1024),
    "rubble_plaster": ("CL_штукатурка_куски", 900, 512), "rubble_crumbs": ("CL_крошка", 2300, 512),
}
GLASS = ("стекло", "линза")
GLOW = ("светодиод", "пламя")  # без отделки — просто светятся
GLOW_MAPPED = ("трубка", "рассеиватель", "мигалка_линза")  # с отделкой (цвет пластика) и светятся в стенде
PLAIN = {"нагар": ((0.03, 0.028, 0.026), 0.95), "табак": ((0.16, 0.09, 0.04), 0.95), "отверстие": ((0.01, 0.01, 0.01), 0.6)}


def kind_of(name: str) -> str:
    low = name.lower()
    if any(k in low for k in GLOW + GLOW_MAPPED):
        return "свет"
    if any(k in low for k in GLASS):
        return "стекло"
    for k in PLAIN:
        if k in low:
            return k
    return ""


def tris(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def setup_cycles() -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    sc.render.bake.margin = 8


def new_image(name, size, non_color, color=(0.5, 0.5, 1.0, 1.0)):
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.generated_color = color
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def target_node(mat, img):
    """Узел картинки — цель запекания (активный в каждом материале низкой сетки)."""
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.name == "bake_target":
            nt.nodes.remove(n)
    n = nt.nodes.new("ShaderNodeTexImage")
    n.name = "bake_target"
    n.image = img
    nt.nodes.active = n


def bake(kind, low, highs, img, extrusion, pass_filter=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for h in highs:
        h.hide_set(False)
        h.hide_render = False
        h.select_set(True)
    low.hide_set(False)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    for slot in low.material_slots:
        if slot.material:
            target_node(slot.material, img)
    kw = dict(type=kind, use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=extrusion * 3, margin=8,
              use_clear=True)
    if pass_filter:
        kw["pass_filter"] = pass_filter
    bpy.ops.object.bake(**kw)


def decimate(ob, target: int) -> None:
    n = tris(ob.data)
    if n <= target:
        return
    md = ob.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = max(0.002, target / n)
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.remove(md)
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)


def label_outer(bm, glass) -> None:
    """Этикетка — один лист: оборот (смотрит на стекло) и торцы листа убираются."""
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromObject(glass, bpy.context.evaluated_depsgraph_get())
    bm.normal_update()
    gone = []
    for f in bm.faces:
        c = f.calc_center_median()
        p = tree.find_nearest(c)[0]
        away = (c - p).normalized() if p is not None and (c - p).length > 1e-7 else f.normal
        if f.normal.dot(away) < 0.5:
            gone.append(f)
    bmesh.ops.delete(bm, geom=gone, context="FACES")


def lift(ob, dist: float) -> None:
    """Сдвиг листа по нормалям вершин — упрощённое стекло не протыкает этикетку."""
    me = ob.data
    for v in me.vertices:
        v.co += v.normal * dist


def material(name, maps_dir, game, kind):
    """Материал glTF: карты вещи (цвет, блеск/металл, нормали); стекло — прозрачное, свет — светится, простые — цвет."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL", "BSDF_PRINCIPLED"):
            nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if kind in PLAIN:
        b.inputs["Base Color"].default_value = (*PLAIN[kind][0], 1.0)
        b.inputs["Roughness"].default_value = PLAIN[kind][1]
        return m
    if kind == "свет" and game not in ("found_chemlight", "found_lantern", "found_beacon"):
        b.inputs["Base Color"].default_value = (1.0, 0.9, 0.7, 1.0)
        b.inputs["Emission Color"].default_value = (1.0, 0.85, 0.6, 1.0)
        b.inputs["Emission Strength"].default_value = 2.0
        return m

    def img(suffix, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(f"{maps_dir}/{game}_{suffix}.png", check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        return n
    nt.links.new(img("baseColor", False).outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("occlusionRoughnessMetallic", True).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if kind == "стекло":
        b.inputs["Alpha"].default_value = 0.35
        m.surface_render_method = "BLENDED"
    return m


def export(ob, game) -> None:
    os.makedirs(OUT, exist_ok=True)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    loc = ob.matrix_world.copy()
    ob.matrix_world = Matrix.Identity(4)
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{game}.gltf", export_format="GLTF_SEPARATE", use_selection=True,
                              export_yup=True, export_apply=True, export_image_format="AUTO", export_materials="EXPORT",
                              export_texcoords=True, export_normals=True, export_tangents=False)
    ob.matrix_world = loc
    print("EXPORT", game, tris(ob.data), "треуг.", flush=True)


def save_png(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()


def props(only) -> None:
    setup_cycles()
    top = bpy.data.collections.get("Развёртка_v01")
    game_coll = bpy.data.collections.get("Игровая_v01") or bpy.data.collections.new("Игровая_v01")
    if game_coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(game_coll)
    done = []
    for game, (setkey, target, size) in PROPS.items():
        coll = bpy.data.collections.get(game)
        if coll is None or (only and game not in only):
            continue
        top.hide_viewport = False
        coll.hide_viewport = False
        coll.hide_render = False
        maps_dir = f"{SRC[setkey]}/{game}"
        highs = [o for o in coll.objects if o.type == "MESH"]
        # высокая сетка для запекания нормалей: карта нормалей Painter в её материале
        hmat = material(f"{game}__high", maps_dir, game, "")
        for h in highs:
            h.data.materials.clear()
            h.data.materials.append(hmat)
            h.matrix_world = Matrix.Identity(4)
        # низкая: каждая деталь упрощается в той же доле (мелкие — не меньше 150 треугольников), материал — по виду
        # детали; этикетка — один лист на 1 мм над стеклом; затем одной сеткой
        glass = next((h for h in highs if "стекло" in h.name.lower()), None)
        parts = []
        for h in highs:
            k = kind_of(h.name)
            me = h.data.copy()
            me.materials.clear()
            me.materials.append(material(game if k == "" else f"{game}_{k}", maps_dir, game, k))
            ob = bpy.data.objects.new(f"{game}__{h.name}", me)
            game_coll.objects.link(ob)
            label = "этикетка" in h.name.lower() and glass is not None
            if label:
                bm = bmesh.new()
                bm.from_mesh(me)
                label_outer(bm, glass)
                bm.to_mesh(me)
                bm.free()
            parts.append((ob, label))
        # доля детали — по корню из её треугольников: плотная этикетка не съедает бюджет стекла
        weight = sum(tris(ob.data) ** 0.5 for ob, _ in parts)
        for ob, label in parts:
            n = tris(ob.data)
            decimate(ob, max(min(n, 150), round(target * n ** 0.5 / weight)))
            if label:
                lift(ob, 0.001)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for ob, _ in parts:
            ob.select_set(True)
        low = parts[0][0]
        bpy.context.view_layer.objects.active = low
        if len(parts) > 1:
            bpy.ops.object.join()
        low.name = game
        low.data.name = game
        for p in low.data.polygons:
            p.use_smooth = True
        # нормали high → low в ту же развёртку
        size_m = max(low.dimensions)
        ext = max(0.002, size_m * 0.012)
        nimg = new_image(f"{game}_normal_game", size, True)
        bake("NORMAL", low, highs, nimg, ext)
        os.makedirs(OUT, exist_ok=True)
        save_png(nimg, f"{OUT}/{game}_normal.png")
        # цвет и блеск/металл — карты Painter, уменьшенные
        for suffix in ("baseColor", "occlusionRoughnessMetallic"):
            src = bpy.data.images.load(f"{maps_dir}/{game}_{suffix}.png", check_existing=False)
            src.scale(size, size)
            save_png(src, f"{OUT}/{game}_{suffix}.png")
            bpy.data.images.remove(src)
        # материалы игровой сетки — на уменьшенные карты
        for m in low.data.materials:
            bt = m.node_tree.nodes.get("bake_target")
            if bt:
                m.node_tree.nodes.remove(bt)
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE":
                    stem = n.image.filepath.replace("\\", "/").rsplit("/", 1)[-1]
                    n.image = bpy.data.images.load(f"{OUT}/{stem}", check_existing=True)
                    if "baseColor" not in stem:
                        n.image.colorspace_settings.name = "Non-Color"
        export(low, game)
        coll.hide_viewport = True
        done.append(game)
    out = bpy.data.filepath.replace("_uv_v01.blend", "_game_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out, done)


def hide_inner(ob) -> None:
    """Грани, которых не видно (между кирпичами кладки, низ на полу), — прочь: развёртка отдаёт карту видимому."""
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    floor = min(v.co.z for v in bm.verts)
    gone = []
    for f in bm.faces:
        c = f.calc_center_median()
        if f.normal.z < -0.7 and c.z < floor + 0.01:
            gone.append(f)
            continue
        if f.normal.z > 0.5:
            continue  # верх виден всегда; тонкая краска после упрощения проваливается в штукатурку — не дырявить
        # прочь, только если закрыта вся грань: и от центра, и у каждой вершины луч упирается в соседнее
        points = [c] + [v.co.lerp(c, 0.15) for v in f.verts]
        if all(tree.ray_cast(p + f.normal * 0.0005, f.normal, 0.03)[0] is not None for p in points):
            gone.append(f)
    bmesh.ops.delete(bm, geom=gone, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    print("скрытых граней", len(gone), "из", len(ob.data.polygons) + len(gone), flush=True)


def rubble(only) -> None:
    """Обломки: фотоматериалы (кубическая проекция) запекаются в развёртку упрощённой сетки — цвет, блеск, нормали."""
    setup_cycles()
    sc = bpy.context.scene
    game_coll = bpy.data.collections.get("Игровая_v01") or bpy.data.collections.new("Игровая_v01")
    if game_coll.name not in sc.collection.children:
        sc.collection.children.link(game_coll)
    dg = bpy.context.evaluated_depsgraph_get()
    done = []
    for game, (root_name, target, size) in RUBBLE.items():
        if only and game not in only:
            continue
        root = bpy.data.objects[root_name]
        highs = [o for o in root.children_recursive if o.type == "MESH"]
        to_root = root.matrix_world.inverted()
        bm = bmesh.new()
        for h in highs:
            me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), depsgraph=dg)
            me.transform(to_root @ h.matrix_world)
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        for f in bm.faces:
            f.material_index = 0
        me = bpy.data.meshes.new(game)
        bm.to_mesh(me)
        bm.free()
        low = bpy.data.objects.new(game, me)
        game_coll.objects.link(low)
        low.matrix_world = root.matrix_world
        for uv in list(me.uv_layers):
            me.uv_layers.remove(uv)
        decimate(low, target)
        hide_inner(low)
        me = low.data
        me.uv_layers.new(name="UVMap")
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        low.select_set(True)
        bpy.context.view_layer.objects.active = low
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.006, area_weight=0.0, correct_aspect=True,
                                 scale_to_bounds=False)
        bpy.ops.uv.pack_islands(rotate=True, margin=0.006)
        bpy.ops.object.mode_set(mode="OBJECT")
        for p in me.polygons:
            p.use_smooth = True
        bake_mat = bpy.data.materials.new(f"{game}__bake")
        me.materials.append(bake_mat)
        ext = max(0.004, max(low.dimensions) * 0.015)
        col = new_image(f"{game}_baseColor", size, False, (0.5, 0.5, 0.5, 1.0))
        bake("DIFFUSE", low, highs, col, ext, pass_filter={"COLOR"})
        rough = new_image(f"{game}_rough", size, True, (0.9, 0.9, 0.9, 1.0))
        bake("ROUGHNESS", low, highs, rough, ext)
        nrm = new_image(f"{game}_normal_game", size, True)
        bake("NORMAL", low, highs, nrm, ext)
        os.makedirs(OUT, exist_ok=True)
        save_png(col, f"{OUT}/{game}_baseColor.png")
        save_png(nrm, f"{OUT}/{game}_normal.png")
        # ORM: R — без затенения (1), G — блеск, B — металл (0: ржавая проволока у плиты — тоже не металл)
        import numpy as np
        px = np.array(rough.pixels[:], dtype=np.float32).reshape(-1, 4)
        orm = np.ones_like(px)
        orm[:, 1] = px[:, 0]
        orm[:, 2] = 0.0
        oimg = new_image(f"{game}_occlusionRoughnessMetallic", size, True)
        oimg.pixels[:] = orm.ravel()
        save_png(oimg, f"{OUT}/{game}_occlusionRoughnessMetallic.png")
        me.materials.clear()
        mat = bpy.data.materials.new(game)
        me.materials.append(mat)
        mat.use_nodes = True
        nt = mat.node_tree
        b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

        def tex(stem, non_color):
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = bpy.data.images.load(f"{OUT}/{stem}.png", check_existing=True)
            if non_color:
                n.image.colorspace_settings.name = "Non-Color"
            return n
        nt.links.new(tex(f"{game}_baseColor", False).outputs["Color"], b.inputs["Base Color"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex(f"{game}_occlusionRoughnessMetallic", True).outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
        nmn = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex(f"{game}_normal", True).outputs["Color"], nmn.inputs["Color"])
        nt.links.new(nmn.outputs["Normal"], b.inputs["Normal"])
        export(low, game)
        done.append(game)
    out = bpy.data.filepath.replace("_v01.blend", "_game_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out, done)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    {"props": props, "rubble": rubble}[argv[0]](argv[1:])
