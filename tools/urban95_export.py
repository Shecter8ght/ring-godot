# -*- coding: utf-8 -*-
"""Городская библиотека RING_Urban_95 (ретопология v01) → glTF для игры.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/urban95_export.py -- [ID …]

Источник: E:/Models Blender/ENVIRONMENT/RING_Urban_95/retopology_v01 (manifest.json; свои модели в Blender, отделка
UCUPaint запечена в атласы). Владелец 2026-10-25: «где-то тут лежат лоуполи ассеты, остальное делай сам».
Для каждого предмета: открыть .blend, убрать свет и камеры, свести детали в одну сетку (части с одним атласом — один
материал, сплошные цвета надписей — свои), оставить одну развёртку BakeUV, экспорт glTF (Y вверх: лицо Blender −Y →
игровое +Z) в assets/models/urban95/<ID>.gltf (+ .bin, карты WebP в textures/ — не дублируются при импорте). Габарит в игровых осях и число треугольников — data/urban95_models.json
(по нему коллизия предмета на карте). LOD и сжатие карт — импорт Godot.
"""
import json
import os
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
SRC = Path("E:/Models Blender/ENVIRONMENT/RING_Urban_95/retopology_v01")
OUT = ROOT / "assets" / "models" / "urban95"
INDEX = ROOT / "data" / "urban95_models.json"
MAX_TEX = 2048                                                  # карты в игре — не больше 2K (4K/8K атласы ужимаются)


def atlas_key(mat: bpy.types.Material) -> str:
    """Материал на атласе — ключ по картам; без карт (сплошной цвет надписи) — пусто."""
    if not mat or not mat.use_nodes:
        return ""
    imgs = sorted(n.image.name for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.image)
    return "|".join(imgs)


def export_one(entry: dict) -> dict:
    blend = SRC / entry["model"]
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    for o in list(bpy.data.objects):
        if o.type not in ("MESH", "EMPTY"):
            bpy.data.objects.remove(o, do_unlink=True)
    # только детали предмета — потомки его корня («ID | название»); студийный пол и фон не берём
    roots = [o for o in bpy.data.objects if o.type == "EMPTY" and o.parent is None and o.name.split(" ")[0] == entry["id"]]
    root_m = roots[0].matrix_world.copy() if roots else None

    def under_root(o: bpy.types.Object) -> bool:
        while o.parent is not None:
            o = o.parent
        return o in roots

    for o in [o for o in bpy.data.objects if o.type == "MESH" and roots and not under_root(o)]:
        bpy.data.objects.remove(o, do_unlink=True)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    # одна развёртка: BakeUV — первой и единственной (glTF берёт TEXCOORD_0)
    for o in meshes:
        uvs = o.data.uv_layers
        bake = uvs.get("BakeUV")
        if bake is None:
            continue
        for uv in [u for u in uvs if u.name != "BakeUV"]:
            uvs.remove(uv)
        uvs["BakeUV"].name = "UVMap"
    # материалы на одном атласе → один материал
    first: dict[str, bpy.types.Material] = {}
    for o in meshes:
        for slot in o.material_slots:
            k = atlas_key(slot.material)
            if not k:
                continue
            if k not in first:
                first[k] = slot.material
                slot.material.name = entry["id"] + "_atlas"
            slot.material = first[k]
    # свести в одну сетку в мировых координатах
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    for o in meshes:
        o.parent = None if o.parent is None else o.parent
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = entry["id"]
    obj.data.name = entry["id"]
    # пустые слоты одного атласа — убрать (после join слоты дублируются)
    bpy.ops.object.material_slot_remove_unused()
    for o in [o for o in bpy.data.objects if o.type == "EMPTY"]:
        bpy.data.objects.remove(o, do_unlink=True)
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    # игровые оси: x = x, y = z (вверх), z = −y
    lo = (min(xs), min(zs), -max(ys))
    hi = (max(xs), max(zs), -min(ys))
    for img in bpy.data.images:
        if img.size[0] > MAX_TEX or img.size[1] > MAX_TEX:
            k = MAX_TEX / max(img.size[0], img.size[1])
            img.scale(int(img.size[0] * k), int(img.size[1] * k))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / (entry["id"] + ".gltf")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures", use_selection=True, export_apply=True, export_yup=True,
                              export_texcoords=True, export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=90,
                              export_cameras=False, export_lights=False, export_animations=False)
    return {"id": entry["id"], "name": entry["name"], "file": "res://assets/models/urban95/%s.gltf" % entry["id"],
            "triangles": tris, "materials": len(obj.material_slots),
            "aabb": {"center": [round((lo[i] + hi[i]) * 0.5, 4) for i in range(3)], "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
            "root_offset": [round(v, 4) for v in root_m.translation] if root_m else [0, 0, 0]}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    wanted = set(argv)
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {"_comment": "", "models": {}}
    index["_comment"] = ("Модели городской библиотеки RING_Urban_95 (ретопология v01) в игре: tools/urban95_export.py. "
                         "aabb — габарит в игровых осях (м, Y вверх, лицо +Z) для коллизии; triangles — треугольников LOD0.")
    for entry in manifest["assets"]:
        if wanted and entry["id"] not in wanted:
            continue
        info = export_one(entry)
        index["models"][entry["id"]] = info
        print("urban95: %s %s — %d треуг., материалов %d, габарит %s" % (entry["id"], entry["name"], info["triangles"], info["materials"],
                                                                      info["aabb"]["size"]))
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


main()
