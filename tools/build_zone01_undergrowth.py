"""Подлесок и травяной покров зоны 1 из Poly Haven «Nature» (CC0), bpy → GLB по одному варианту.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_zone01_undergrowth.py
Исходники: python tools/fetch_polyhaven_models.py nature shrub_02 nettle_plant ... (_asset_src/nature/).

Сканы — уже с карточками и альфой; здесь: каждый вариант отдельно, основание в ноль (центр по X/Z,
низ по Y), лишнее упрощается Decimate до бюджета, текстуры — JPEG внутри GLB. Материал в игре
переводит в «листву» DistrictScatter (foliage = true): отсечение по альфе, обе стороны, приглушение.
Пишет assets/zone01/models/ug_<имя>.glb и assets/zone01/models/undergrowth.json (размеры).
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src"
OUT = ROOT / "assets/zone01/models"

# (папка, модель, префикс объекта → имя в игре, бюджет треугольников)
ITEMS = [
    ("nature", "shrub_02", [("shrub_02_a", "bush_a"), ("shrub_02_b", "bush_b"), ("shrub_02_c", "bush_c"), ("shrub_02_d", "bush_d")], 6000),
    ("nature", "nettle_plant", [("nettle_plant_tall_a", "nettle_tall_a"), ("nettle_plant_tall_b", "nettle_tall_b"),
                                ("nettle_plant_medium_a", "nettle_mid_a"), ("nettle_plant_medium_b", "nettle_mid_b")], 4000),
    ("nature", "weed_plant_02", [("weed_plant_02_a", "weed_a"), ("weed_plant_02_b", "weed_b"), ("weed_plant_02_c", "weed_c")], 2500),
    ("nature", "dandelion_01", [("dandelion_01_c", "dandelion_c"), ("dandelion_01_d", "dandelion_d"), ("dandelion_01_e", "dandelion_e")], 2500),
    ("nature", "grass_medium_01", [("grass_medium_01_large_b", "grass_large"), ("grass_medium_01_mid_b", "grass_mid_b"),
                                   ("grass_medium_01_mid_c", "grass_mid_c"), ("grass_medium_01_tall_a", "grass_tall_a"),
                                   ("grass_medium_01_tall_b", "grass_tall_b"), ("grass_medium_01_small_a", "grass_small")], 3000),
    ("nature", "grass_medium_02", [("grass_medium_02_c", "grass2_c"), ("grass_medium_02_d", "grass2_d"), ("grass_medium_02_e", "grass2_e")], 3000),
    ("nature", "fir_sapling", [("fir_sapling_a", "sapling_a"), ("fir_sapling_b", "sapling_b"), ("fir_sapling_c", "sapling_c")], 9000),
]


def tris(o) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def main() -> None:
    manifest = {}
    for folder, asset, picks, budget in ITEMS:
        for prefix, name in picks:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=str(SRC / folder / asset / f"{asset}.gltf"))
            objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
            keep = next((o for o in objs if o.name.startswith(prefix)), None)
            if keep is None:
                print("UNDERGROWTH пропущен", prefix, flush=True)
                continue
            for o in list(bpy.context.scene.objects):
                if o is not keep:
                    bpy.data.objects.remove(o, do_unlink=True)
            keep.parent = None
            # цвет с альфой (склеен tools/fetch_polyhaven_models.py): отсечение по ней в игре
            rgba = SRC / folder / asset / "textures" / f"{asset}_rgba.png"
            if rgba.exists():
                img = bpy.data.images.load(str(rgba))
                for mat in keep.data.materials:
                    nt = mat.node_tree
                    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
                    node = nt.nodes.new("ShaderNodeTexImage")
                    node.image = img
                    uv = next((n for n in nt.nodes if n.type == "UVMAP"), None)
                    nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
                    nt.links.new(node.outputs["Alpha"], bsdf.inputs["Alpha"])
            bpy.context.view_layer.objects.active = keep
            keep.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if tris(keep) > budget:
                m = keep.modifiers.new("dec", "DECIMATE")
                m.ratio = budget / tris(keep)
                bpy.ops.object.modifier_apply(modifier="dec")
            bb = [keep.matrix_world @ Vector(c) for c in keep.bound_box]
            cx = (min(v.x for v in bb) + max(v.x for v in bb)) * 0.5
            cy = (min(v.y for v in bb) + max(v.y for v in bb)) * 0.5
            zmin = min(v.z for v in bb)
            keep.data.transform(__import__("mathutils").Matrix.Translation((-cx, -cy, -zmin)))
            keep.name = f"ug_{name}"
            bpy.ops.export_scene.gltf(filepath=str(OUT / f"ug_{name}.glb"), export_format="GLB", use_selection=True,
                                      export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                                      export_image_format="AUTO", export_animations=False)
            size = [round(max(v.x for v in bb) - min(v.x for v in bb), 2), round(max(v.z for v in bb) - zmin, 2),
                    round(max(v.y for v in bb) - min(v.y for v in bb), 2)]
            manifest[f"ug_{name}"] = dict(triangles=tris(keep), size=size, source=f"https://polyhaven.com/a/{asset}")
            print("UNDERGROWTH", name, tris(keep), size, flush=True)
    (OUT / "undergrowth.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


main()
