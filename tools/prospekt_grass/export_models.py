"""Игровые LOD растений «Проспекта» из сохранённых исходников Poly Haven.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_grass/export_models.py

Bermuda: три небольших ковра из отдельных листьев исходника, без сферы Geometry Nodes.
Medium/Weed: готовые низкие LOD исходника. Исходные .blend не перезаписываются.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "prospekt_grass"
OUT = ROOT / "assets" / "models" / "prospekt_grass"
WORK = SRC / "game"
TEX = SRC / "game_textures"


def triangles(mesh: bpy.types.Mesh) -> int:
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


def game_material(asset: str) -> bpy.types.Material:
    name = "PG_" + asset
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.use_backface_culling = False
    if "surface_render_method" in material.bl_rna.properties:
        material.surface_render_method = "DITHERED"
    tree = material.node_tree
    bsdf = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(TEX / f"{asset}_albedo.png"), check_existing=True)
    texture.image.colorspace_settings.name = "sRGB"
    tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(texture.outputs["Alpha"], bsdf.inputs["Alpha"])
    return material


def center_object(obj: bpy.types.Object) -> None:
    obj.parent = None
    obj.location = (0.0, 0.0, 0.0)
    if obj.type != "MESH":
        return
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    cx = (min(point.x for point in points) + max(point.x for point in points)) * 0.5
    cy = (min(point.y for point in points) + max(point.y for point in points)) * 0.5
    zmin = min(point.z for point in points)
    obj.data.transform(Matrix.Translation((-cx, -cy, -zmin)))
    obj.data.update()


def clone_mesh(source: bpy.types.Object, name: str, material: bpy.types.Material) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, source.data.copy())
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_euler = source.rotation_euler
    obj.scale = source.scale
    obj.data.materials.clear()
    obj.data.materials.append(material)
    center_object(obj)
    return obj


def append_blade(vertices: list, faces: list, uvs: list, source: bpy.types.Object, transform: Matrix) -> None:
    mesh = source.data
    mesh.calc_loop_triangles()
    offset = len(vertices)
    for vertex in mesh.vertices:
        vertices.append(tuple(transform @ vertex.co))
    uv_layer = mesh.uv_layers.active
    for triangle in mesh.loop_triangles:
        faces.append(tuple(offset + index for index in triangle.vertices))
        for loop_index in triangle.loops:
            loop = mesh.loops[loop_index]
            uvs.append(tuple(uv_layer.data[loop_index].uv) if uv_layer else (0.0, 0.0))


def bermuda_patch(sources: dict[str, list], seed: int, lod: int, material: bpy.types.Material) -> bpy.types.Object:
    rng = random.Random(seed)
    placements: list[tuple] = []
    live_count = 20 if lod == 0 else 8
    dead_count = 3 if lod == 0 else 2
    for index in range(live_count + dead_count):
        dead = index >= live_count
        group = "dead" if dead else rng.choices(("small", "medium", "flattened"), weights=(0.55, 0.3, 0.15))[0]
        source = rng.choice(sources[group])
        angle = rng.random() * math.tau
        radius = 0.15 * math.sqrt(rng.random())
        position = Vector((math.cos(angle) * radius, math.sin(angle) * radius, 0.0))
        yaw = rng.random() * math.tau
        scale = rng.uniform(0.78, 1.16) * (1.12 if lod == 1 else 1.0)
        rotation = Matrix.Rotation(yaw, 4, "Z")
        transform = Matrix.Translation(position) @ rotation @ Matrix.Diagonal((scale, scale, scale, 1.0))
        placements.append((source, transform))
    vertices: list = []
    faces: list = []
    uvs: list = []
    for source, transform in placements:
        append_blade(vertices, faces, uvs, source, transform)
    mesh = bpy.data.meshes.new(f"PG_Bermuda_{seed}_{lod}")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for loop, uv in zip(mesh.loops, uvs):
        uv_layer.data[loop.index].uv = uv
    mesh.materials.append(material)
    obj = bpy.data.objects.new(f"grass_bermuda_01_{'abc'[(seed - 7100) // 97]}_lod{lod}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    center_object(obj)
    return obj


def open_source(asset: str) -> None:
    bpy.ops.wm.open_mainfile(filepath=str(SRC / asset / f"{asset}_8k.blend"))


def build_bermuda() -> list:
    open_source("grass_bermuda_01")
    material = game_material("grass_bermuda_01")
    sources = {"small": [], "medium": [], "dead": [], "flattened": []}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        for group in sources:
            if obj.name.startswith(f"grass_bermuda_01_{group}_"):
                sources[group].append(obj)
    if not all(sources.values()):
        raise RuntimeError("Bermuda: не найдены исходные листья")
    return [bermuda_patch(sources, 7100 + variant * 97, lod, material)
        for variant in range(3) for lod in range(2)]


def build_lod_asset(asset: str, picks: list) -> list:
    open_source(asset)
    material = game_material(asset)
    result = []
    for key, source_stem, source_lods in picks:
        for game_lod, source_lod in enumerate(source_lods):
            wanted = f"{asset}_{source_stem}_LOD{source_lod}"
            source = next((obj for obj in bpy.context.scene.objects if obj.name == wanted), None)
            if source is None:
                raise RuntimeError(f"Не найден {wanted}")
            result.append(clone_mesh(source, f"{key}_lod{game_lod}", material))
    return result


def export_objects(objects: list, key: str) -> dict:
    for obj in list(bpy.context.scene.objects):
        if obj not in objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    report: dict = {}
    for index, obj in enumerate(objects):
        obj.location = (0.0, 0.0, 0.0)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = OUT / f"{obj.name}.gltf"
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures", use_selection=True,
            export_yup=True, export_texcoords=True, export_normals=True, export_tangents=True,
            export_materials="EXPORT", export_image_format="AUTO", export_animations=False,
            export_cameras=False, export_lights=False)
        obj.location = (index * 0.55, 0.0, 0.0)
        mesh = obj.data
        report[obj.name] = {"triangles": triangles(mesh), "dimensions_m": [round(v, 4) for v in obj.dimensions],
            "file": f"res://assets/models/prospekt_grass/{obj.name}.gltf"}
        print(f"LOD {obj.name}: {report[obj.name]['triangles']} треугольников", flush=True)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.file.pack_all()
    blend_path = WORK / f"{key}_models.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    return report


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    groups = [
        ("grass_bermuda_01", lambda: build_bermuda()),
        ("grass_medium_01", lambda: build_lod_asset("grass_medium_01", [
            ("grass_medium_01_a", "geonodes_mid_a", (0, 2)),
            ("grass_medium_01_b", "geonodes_mid_b", (0, 2)),
            ("grass_medium_01_tall", "geonodes_tall_a", (0, 2)),
        ])),
        ("weed_plant_02", lambda: build_lod_asset("weed_plant_02", [
            ("weed_plant_02_a", "a", (0, 2)),
            ("weed_plant_02_b", "b", (0, 2)),
        ])),
    ]
    for key, builder in groups:
        report.update(export_objects(builder(), key))
    report_path = SRC / "game_assets.json"
    combined = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    combined["models"] = report
    report_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    for key, _builder in groups:
        bpy.ops.wm.open_mainfile(filepath=str(WORK / f"{key}_models.blend"))
        missing = [image.name for image in bpy.data.images if image.source == "FILE" and not image.packed_file and not Path(bpy.path.abspath(image.filepath)).exists()]
        if missing:
            raise RuntimeError("В игровом .blend отсутствуют карты: " + ", ".join(missing))
    print(f"ПЕРЕОТКРЫТО: {len(groups)} игровых .blend, {len(report)} сеток, карты вшиты", flush=True)


if __name__ == "__main__":
    main()
