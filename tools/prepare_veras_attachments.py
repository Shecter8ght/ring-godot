"""Обвесы ВЕРАС-54 в игру: рукоятки ВАРН V1 (вертикальная) и V2 (45° влево), глушитель 5.45.

Каждый — игровая сетка (Body + Body_LOD1) и карты состояния 100 (вид в игре один при любой прочности, решение
владельца 2026-10-19; прежние 60 / 20 удалены): assets/models/attachments/<id>/<id>.glb,
<id>_100_{base_color,roughness,metallic,normal}.png.

  рукоятки  — исходники библиотеки высокополигональные со слоями UCUPaint: сетка упрощается,
              новая развёртка, материалы проецируются запеканием (Cycles).
  глушитель — уже игровой (GameUV и карты): сетка склеивается, карты копируются.

Оси игры у GLB: X влево стрелка, Y вверх, Z к дулу. Начало рукоятки — нижняя плоскость планки
(середина зажима), начало глушителя — задний торец на оси ствола.

blender --background --factory-startup --python-exit-code 1 --python tools/prepare_veras_attachments.py -- <шаг> <id> [состояние]
  шаги: geometry <id> · bake <id> 100 · export <id> · imports <id> (после первого --import Godot)
  id: varn_v1 · varn_v2 · supp_veras
Исходники библиотеки только читаются. Промежуточные файлы — в _asset_src/veras_attachments.
"""
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
LIB = Path("E:/Models Blender/ВЕРАС-54 — модель и обвесы")
WORK = ROOT / "_asset_src/veras_attachments"
STATES = (100,)
CHANNELS = (("base_color", "Base Color"), ("roughness", "Roughness"), ("metallic", "Metallic"), ("normal", None))
# Источник (X вперёд, Y влево, Z вверх) → игра (X влево, Y вверх, Z вперёд).
TO_GAME = Matrix(((0, 1, 0, 0), (0, 0, 1, 0), (1, 0, 0, 0), (0, 0, 0, 1)))

ASSETS = {
    "varn_v1": {
        "dir": LIB / "ВАРН V1/Актуальное", "res": 1024,
        "files": {100: "Foregrip_Straight_State100_New_v11.blend"},
        # предел треугольников по имени детали (первое совпадение)
        "limits": (("sculpted grooved handle", 9000), ("cap knurl", 700), ("moulded shoulder", 600),
                   ("rounded base cap", 400), ("clamp bolt", 160), ("rail jaw", 320), ("", 400)),
    },
    "varn_v2": {
        "dir": LIB / "ВАРН V2/Актуальное", "res": 1024,
        "files": {100: "Foregrip_Angled_State100_New_v11.blend"},
        "limits": (("sculpted grooved handle", 9000), ("cap knurl", 700), ("OffsetGrip_Rigid_Adapter", 700),
                   ("rounded base cap", 400), ("clamp bolt", 160), ("rail jaw", 320), ("", 400)),
    },
    "supp_veras": {
        "dir": LIB / "ВЕРАС-54/Игровая версия/UV и карты v01", "res": 1024,
        "files": {100: "Глушитель отдельно/Suppressor_Game_State100_v01.blend"},
        "maps": {100: "Текстуры/100"},
    },
}


def out_dir(aid: str) -> Path:
    path = ROOT / "assets/models/attachments" / aid
    path.mkdir(parents=True, exist_ok=True)
    return path


def activate(objects) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[-1]


def source_objects():
    return [o for o in bpy.data.objects if o.type in ("MESH", "FONT") and not o.hide_render]


def tris(ob) -> int:
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


# ---------------------------------------------------------------- рукоятки: сетка, запекание

def geometry(aid: str) -> None:
    spec = ASSETS[aid]
    bpy.ops.wm.open_mainfile(filepath=str(spec["dir"] / spec["files"][100]))
    dg = bpy.context.evaluated_depsgraph_get()
    pieces = []
    for src in source_objects():
        # надписи проецируются в цвет, их геометрия в игровую сетку не входит
        if src.type == "FONT":
            continue
        mesh = bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        low = bpy.data.objects.new("LP_" + src.name, mesh)
        bpy.context.collection.objects.link(low)
        low.matrix_world = src.matrix_world.copy()
        activate([low])
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        weld = low.modifiers.new("weld", "WELD")
        weld.merge_threshold = 0.000001
        bpy.ops.object.modifier_apply(modifier=weld.name)
        limit = next(n for key, n in spec["limits"] if key in src.name)
        count = tris(low)
        if count > limit:
            mod = low.modifiers.new("reduce", "DECIMATE")
            mod.ratio = limit / count
            bpy.ops.object.modifier_apply(modifier=mod.name)
        low.data.materials.clear()
        pieces.append(low)
    activate(pieces)
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = "Body"
    while body.data.uv_layers:
        body.data.uv_layers.remove(body.data.uv_layers[0])
    body.data.uv_layers.new(name="GameUV")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004, area_weight=0.5)
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        if obj != body:
            bpy.data.objects.remove(obj, do_unlink=True)
    WORK.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / f"{aid}_low.blend"))
    print("ATT_GEOMETRY_OK", aid, tris(body), flush=True)


def bake(aid: str, state: int) -> None:
    spec = ASSETS[aid]
    res = spec["res"]
    bpy.ops.wm.open_mainfile(filepath=str(spec["dir"] / spec["files"][state]))
    high = source_objects()
    with bpy.data.libraries.load(str(WORK / f"{aid}_low.blend"), link=False) as (_, target):
        target.objects = ["Body"]
    body = target.objects[0]
    bpy.context.collection.objects.link(body)
    body.name = "BakeTarget"
    mat = bpy.data.materials.new("BakeTargetMaterial")
    mat.use_nodes = True
    body.data.materials.clear()
    body.data.materials.append(mat)
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    mat.node_tree.nodes.active = node
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.use_cage = False
    scene.render.bake.cage_extrusion = 0.00065
    scene.render.bake.max_ray_distance = 0.0013
    scene.render.bake.margin = 8
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type != "CPU"
        if any(d.use for d in prefs.devices):
            scene.cycles.device = "GPU"
    except Exception as error:
        print("GPU_FALLBACK", error)
    original = {}
    for obj in high:
        for material in obj.data.materials:
            if not material or material in original or not material.use_nodes:
                continue
            bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            output = next((n for n in material.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None)
            if bsdf and output:
                original[material] = (bsdf, output)
    for channel, socket in CHANNELS:
        for material, (bsdf, output) in original.items():
            tree = material.node_tree
            if socket:
                emission = tree.nodes.get("GameBakeEmission") or tree.nodes.new("ShaderNodeEmission")
                emission.name = "GameBakeEmission"
                source = bsdf.inputs[socket]
                for link in list(emission.inputs["Color"].links):
                    tree.links.remove(link)
                if source.is_linked:
                    tree.links.new(source.links[0].from_socket, emission.inputs["Color"])
                else:
                    value = source.default_value
                    emission.inputs["Color"].default_value = value if hasattr(value, "__len__") else (value, value, value, 1)
                tree.links.new(emission.outputs[0], output.inputs["Surface"])
            else:
                tree.links.new(bsdf.outputs[0], output.inputs["Surface"])
        image = bpy.data.images.new(f"{aid}_{state}_{channel}", width=res, height=res, alpha=False)
        image.colorspace_settings.name = "sRGB" if channel == "base_color" else "Non-Color"
        node.image = image
        activate(high + [body])
        print("ATT_BAKE_START", aid, state, channel, flush=True)
        bpy.ops.object.bake(type="NORMAL" if channel == "normal" else "EMIT")
        image.filepath_raw = str(out_dir(aid) / f"{aid}_{state}_{channel}.png")
        image.file_format = "PNG"
        image.save()
    print("ATT_BAKE_OK", aid, state, flush=True)


# ---------------------------------------------------------------- глушитель: готовая игровая сетка

def suppressor_geometry(aid: str) -> None:
    spec = ASSETS[aid]
    bpy.ops.wm.open_mainfile(filepath=str(spec["dir"] / spec["files"][100]))
    root = bpy.data.objects["Suppressor"]
    inv = root.matrix_world.inverted()
    parts = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render
             and o.data.materials and o.data.materials[0] and "Suppressor" in o.data.materials[0].name]
    for o in parts:
        # в осях узла «Suppressor»: задний торец в начале, ось ствола — X
        local = inv @ o.matrix_world
        o.parent = None
        o.matrix_world = local
    activate(parts)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = "Body"
    for layer in [u for u in body.data.uv_layers if u.name != "GameUV"]:
        body.data.uv_layers.remove(layer)
    body.data.materials.clear()
    for obj in list(bpy.data.objects):
        if obj != body:
            bpy.data.objects.remove(obj, do_unlink=True)
    WORK.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / f"{aid}_low.blend"))
    for state, folder in spec["maps"].items():
        for channel, name in (("base_color", "BaseColor"), ("roughness", "Roughness"), ("metallic", "Metallic"), ("normal", "Normal")):
            src = spec["dir"] / folder / f"VERAS54_Suppressor_{state:03d}_{name}.png"
            image = bpy.data.images.load(str(src))
            image.scale(spec["res"], spec["res"])
            image.filepath_raw = str(out_dir(aid) / f"{aid}_{state}_{channel}.png")
            image.file_format = "PNG"
            image.save()
            bpy.data.images.remove(image)
    print("ATT_GEOMETRY_OK", aid, tris(body), flush=True)


# ---------------------------------------------------------------- GLB

def export(aid: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(WORK / f"{aid}_low.blend"))
    out = out_dir(aid)
    body = bpy.data.objects["Body"]
    body.data.transform(TO_GAME)
    body.data.update()
    root = bpy.data.objects.new(aid, None)
    bpy.context.collection.objects.link(root)
    body.parent = root
    mat = bpy.data.materials.new(aid)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    for channel, socket in (("base_color", "Base Color"), ("roughness", "Roughness"), ("metallic", "Metallic"), ("normal", "Normal")):
        image = bpy.data.images.load(str(out / f"{aid}_100_{channel}.png"))
        image.colorspace_settings.name = "sRGB" if channel == "base_color" else "Non-Color"
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        if channel == "normal":
            normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            mat.node_tree.links.new(tex.outputs["Color"], normal.inputs["Color"])
            mat.node_tree.links.new(normal.outputs["Normal"], bsdf.inputs[socket])
        else:
            mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs[socket])
    body.data.materials.clear()
    body.data.materials.append(mat)
    # вид со стороны (напарники, мародёры, на земле) — отдельный узел, выбирает код
    world = body.copy()
    world.data = body.data.copy()
    world.name = "Body_LOD1"
    bpy.context.collection.objects.link(world)
    world.parent = root
    activate([world])
    mod = world.modifiers.new("lod", "DECIMATE")
    mod.ratio = 0.2
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for obj in (body, world):
        activate([obj])
        mod = obj.modifiers.new("tri", "TRIANGULATE")
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for attr in list(obj.data.color_attributes):
            obj.data.color_attributes.remove(attr)
    activate([root, body, world])
    bpy.ops.export_scene.gltf(filepath=str(out / f"{aid}.glb"), export_format="GLB", use_selection=True,
                              export_yup=False, export_animations=False, export_texcoords=True, export_normals=True,
                              export_tangents=True, export_extras=True)
    bb = [v.co for v in body.data.vertices]
    size = {"min": [round(min(c[i] for c in bb), 4) for i in range(3)], "max": [round(max(c[i] for c in bb), 4) for i in range(3)]}
    report = {"source": {str(k): str(v) for k, v in ASSETS[aid]["files"].items()}, "triangles": {"Body": tris(body), "Body_LOD1": tris(world)},
              "axis": "X left, Y up, Z forward", "bounds_m": size, "states": list(STATES), "texture_size": ASSETS[aid]["res"]}
    (out / "manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ATT_EXPORT_OK", aid, report["triangles"], size, flush=True)


def configure_imports(aid: str) -> None:
    """После первого --import Godot: карты со сжатием видеопамяти и mip-уровнями."""
    for path in out_dir(aid).glob("*.png.import"):
        settings = path.read_text(encoding="utf-8")
        settings = settings.replace("compress/mode=0", "compress/mode=2")
        settings = settings.replace("mipmaps/generate=false", "mipmaps/generate=true")
        settings = settings.replace("detect_3d/compress_to=1", "detect_3d/compress_to=0")
        if "_normal.png.import" in path.name:
            settings = settings.replace("compress/normal_map=0", "compress/normal_map=1")
        path.write_text(settings, encoding="utf-8")
    print("ATT_IMPORT_SETTINGS_OK", aid, flush=True)


args = sys.argv[sys.argv.index("--") + 1:]
step, asset = args[0], args[1]
if step == "geometry":
    suppressor_geometry(asset) if "maps" in ASSETS[asset] else geometry(asset)
elif step == "bake":
    bake(asset, int(args[2]))
elif step == "export":
    export(asset)
elif step == "imports":
    configure_imports(asset)
else:
    raise ValueError(args)
