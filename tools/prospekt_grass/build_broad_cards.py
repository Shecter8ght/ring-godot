"""Широкие низкие куртины D из разрешённых Poly Haven-растений RING.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_grass/build_broad_cards.py

Сначала рендер небольшой группы готовых растений в RGBA, затем кромка альфы и
изогнутые карточки LOD0/LOD1. Исходники и Road to Vostok не используются как игровые файлы.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "prospekt_grass"
WORK = SRC / "broad_cards"
OUT = ROOT / "assets" / "models" / "prospekt_grass"
VARIANTS = [
    {"key": "grass_broad_01_a", "asset": "grass_medium_01", "source": "grass_medium_01_a_lod0", "count": 3, "step": 0.18, "seed": 1201},
    {"key": "grass_broad_01_b", "asset": "grass_medium_01", "source": "grass_medium_01_b_lod0", "count": 4, "step": 0.15, "seed": 1202},
    {"key": "grass_broad_01_c", "asset": "grass_bermuda_01", "source": "grass_bermuda_01_a_lod0", "count": 3, "step": 0.16, "seed": 1203},
]


def load_pixels(path: Path) -> np.ndarray:
    image = bpy.data.images.load(str(path))
    image.colorspace_settings.name = "Non-Color"
    width, height = image.size
    data = np.empty(width * height * 4, np.float32)
    image.pixels.foreach_get(data)
    bpy.data.images.remove(image)
    return data.reshape(height, width, 4)[::-1].copy()


def save_pixels(path: Path, data: np.ndarray) -> None:
    height, width = data.shape[:2]
    image = bpy.data.images.new("card_tmp", width, height, alpha=True)
    image.colorspace_settings.name = "Non-Color"
    image.pixels.foreach_set(np.ascontiguousarray(data[::-1], np.float32).ravel())
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def box(values: np.ndarray, radius: int) -> np.ndarray:
    padded = np.pad(values, ((radius + 1, radius), (radius + 1, radius)))
    sums = np.cumsum(np.cumsum(padded, 0, dtype=np.float32), 1, dtype=np.float32)
    return sums[2 * radius + 1:, 2 * radius + 1:] - sums[:-2 * radius - 1, 2 * radius + 1:] - sums[2 * radius + 1:, :-2 * radius - 1] + sums[:-2 * radius - 1, :-2 * radius - 1]


def process_image(raw: Path, dest: Path) -> dict:
    rgba = load_pixels(raw)
    alpha = rgba[..., 3]
    ys, xs = np.where(alpha > 0.02)
    if len(xs) == 0:
        raise RuntimeError(f"Пустой атлас {raw}")
    margin = 12
    x0, x1 = max(0, int(xs.min()) - margin), min(rgba.shape[1], int(xs.max()) + margin + 1)
    y0, y1 = max(0, int(ys.min()) - margin), min(rgba.shape[0], int(ys.max()) + margin + 1)
    rgba = rgba[y0:y1, x0:x1]
    inside = rgba[..., 3] > 0.02
    rgb = rgba[..., :3]
    done = inside.copy()
    mask = inside.astype(np.float32)
    for radius in (2, 4, 8, 16, 32):
        weights = box(mask, radius)
        fill = (~done) & (weights > 0.0)
        for channel in range(3):
            sums = box(rgb[..., channel] * mask, radius)
            plane = rgb[..., channel]
            plane[fill] = sums[fill] / weights[fill]
        done |= fill
    rgba[..., :3] = rgb
    rgba[..., 3] = np.clip(rgba[..., 3] * 1.08, 0.0, 1.0)
    save_pixels(dest, rgba)
    return {"width": int(rgba.shape[1]), "height": int(rgba.shape[0]),
        "coverage": float(np.mean(rgba[..., 3] > 0.18))}


def arrangement(spec: dict) -> None:
    asset = spec["asset"]
    source_path = SRC / "game" / f"{asset}_models.blend"
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    source = bpy.data.objects.get(spec["source"])
    if source is None:
        raise RuntimeError(f"Нет исходной сетки {spec['source']}")
    rng = random.Random(spec["seed"])
    copies = []
    for index in range(spec["count"]):
        obj = bpy.data.objects.new(f"Render_{index}", source.data.copy())
        bpy.context.scene.collection.objects.link(obj)
        obj.rotation_euler = (0.0, 0.0, rng.uniform(-0.7, 0.7))
        scale = rng.uniform(0.9, 1.1)
        obj.scale = (scale, scale, scale)
        obj.location = ((index - (spec["count"] - 1) * 0.5) * spec["step"], rng.uniform(-0.035, 0.035), 0.0)
        copies.append(obj)
    for obj in list(bpy.context.scene.objects):
        if obj not in copies:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(corner) for obj in copies for corner in obj.bound_box]
    lo = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    hi = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (lo + hi) * 0.5
    center.z = lo.z + (hi.z - lo.z) * 0.45
    camera_data = bpy.data.cameras.new("CardCamera")
    camera = bpy.data.objects.new("CardCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = center + Vector((0.0, -2.5, 0.75))
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(hi.x - lo.x, hi.z - lo.z) * 1.18
    bpy.context.scene.camera = camera
    world = bpy.data.worlds.new("CardWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.45
    bpy.context.scene.world = world
    for name, offset, energy in (("Key", Vector((-0.8, -0.8, 1.1)), 45.0), ("Fill", Vector((0.8, 0.1, 0.7)), 20.0)):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = 1.0
        light = bpy.data.objects.new(name, light_data)
        bpy.context.scene.collection.objects.link(light)
        light.location = center + offset
        light.rotation_euler = (center - light.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.render.filepath = str(WORK / "raw" / f"{spec['key']}.png")
    Path(scene.render.filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def card_mesh(key: str, lod: int, width: float, height: float) -> bpy.types.Object:
    vertices: list = []
    faces: list = []
    uvs: list = []
    planes = 3 if lod == 0 else 2
    segments_x = 4 if lod == 0 else 1
    segments_z = 2 if lod == 0 else 1
    for plane in range(planes):
        yaw = math.pi * plane / planes
        rotation = Matrix.Rotation(yaw, 4, "Z")
        offset = len(vertices)
        for row in range(segments_z + 1):
            v = row / segments_z
            for col in range(segments_x + 1):
                u = col / segments_x
                bend = (abs(u - 0.5) ** 1.5) * width * 0.09
                point = Vector(((u - 0.5) * width, bend, v * height * (0.97 + plane * 0.02)))
                vertices.append(tuple(rotation @ point))
                uvs.append((u, v))
        stride = segments_x + 1
        for row in range(segments_z):
            for col in range(segments_x):
                a = offset + row * stride + col
                faces.append((a, a + 1, a + stride + 1, a + stride))
    mesh = bpy.data.meshes.new(f"{key}_lod{lod}")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        polygon.use_smooth = True
        for loop_index in polygon.loop_indices:
            uv_layer.data[loop_index].uv = uvs[mesh.loops[loop_index].vertex_index]
    obj = bpy.data.objects.new(f"{key}_lod{lod}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def card_material(key: str) -> bpy.types.Material:
    material = bpy.data.materials.new("PG_" + key)
    material.use_nodes = True
    material.use_backface_culling = False
    if "surface_render_method" in material.bl_rna.properties:
        material.surface_render_method = "DITHERED"
    tree = material.node_tree
    bsdf = next(node for node in tree.nodes if node.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.85
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(WORK / f"{key}.png"), check_existing=True)
    texture.image.colorspace_settings.name = "sRGB"
    tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    tree.links.new(texture.outputs["Alpha"], bsdf.inputs["Alpha"])
    return material


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"textures": {}, "models": {}}
    for spec in VARIANTS:
        arrangement(spec)
        key = spec["key"]
        report["textures"][key] = process_image(WORK / "raw" / f"{key}.png", WORK / f"{key}.png")
        print(f"АТЛАС {key}: {report['textures'][key]}", flush=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = []
    for index, spec in enumerate(VARIANTS):
        key = spec["key"]
        texture = report["textures"][key]
        width = 0.82 if key != "grass_broad_01_c" else 0.72
        height = min(0.32, width * texture["height"] / texture["width"])
        material = card_material(key)
        for lod in range(2):
            obj = card_mesh(key, lod, width, height)
            obj.data.materials.append(material)
            objects.append(obj)
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            path = OUT / f"{obj.name}.gltf"
            bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures",
                use_selection=True, export_yup=True, export_texcoords=True, export_normals=True, export_tangents=True,
                export_materials="EXPORT", export_image_format="AUTO", export_animations=False,
                export_cameras=False, export_lights=False)
            obj.data.calc_loop_triangles()
            report["models"][obj.name] = {"triangles": len(obj.data.loop_triangles),
                "dimensions_m": [round(v, 4) for v in obj.dimensions],
                "file": f"res://assets/models/prospekt_grass/{obj.name}.gltf"}
            obj.location = (index * 1.0 + lod * 0.15, 0.0, 0.0)
            print(f"СЕТКА {obj.name}: {report['models'][obj.name]['triangles']} треугольников", flush=True)
    bpy.ops.file.pack_all()
    blend_path = WORK / "grass_broad_01_cards.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    combined_path = SRC / "game_assets.json"
    combined = json.loads(combined_path.read_text(encoding="utf-8")) if combined_path.exists() else {}
    combined.setdefault("models", {}).update(report["models"])
    combined["broad_textures"] = report["textures"]
    combined_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    missing = [image.name for image in bpy.data.images if image.source == "FILE" and not image.packed_file and not Path(bpy.path.abspath(image.filepath)).exists()]
    if missing:
        raise RuntimeError("Отсутствуют карты: " + ", ".join(missing))
    print("ПЕРЕОТКРЫТ ИГРОВОЙ BLEND, картинки вшиты", flush=True)


if __name__ == "__main__":
    main()
