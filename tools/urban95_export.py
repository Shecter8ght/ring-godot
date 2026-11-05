# -*- coding: utf-8 -*-
"""Городская библиотека RING_Urban_95 (ретопология v01) → glTF для игры.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/urban95_export.py -- [ID …]

Источник: E:/Models Blender/ENVIRONMENT/RING_Urban_95/retopology_v01 (manifest.json; свои модели в Blender, отделка
UCUPaint запечена в атласы). Владелец 2026-10-25: «где-то тут лежат лоуполи ассеты, остальное делай сам».
Для каждого предмета: открыть .blend, убрать свет и камеры, свести детали в одну сетку (части с одним атласом — один
материал, сплошные цвета надписей — свои, стекло — своё прозрачное по виду, см. GLASS), оставить одну развёртку BakeUV, экспорт glTF (Y вверх: лицо Blender −Y →
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
# Стекло исходника — Principled с пропусканием (Transmission Weight ≥ 0,5); его цвет в атласе — белый (у прозрачного
# стекла Blender цвет — оттенок прошедшего света). Слитое с атласом, оно в игре было непрозрачным белым зеркалом
# (альбедо 0,9, шероховатость 0,04: окна R06, стеклянные двери, навесы, ограждения). Поэтому у стекла свой материал:
# вид по имени материала → цвет (линейный), прозрачность, шероховатость; числа «стекла» — как у машин «Проспекта»
# (tools/prospekt_vehicles/apply_maps.py, GLASS), линзы — как их фонари.
GLASS = {"glass": ((0.06, 0.07, 0.075), 0.30, 0.04),           # прозрачное (окна, двери, навесы, ограждения)
         "glass_clear": ((0.06, 0.07, 0.075), 0.30, 0.04),
         "glass_smoke": ((0.025, 0.027, 0.03), 0.55, 0.04),     # тонированное
         "glass_green": ((0.045, 0.08, 0.07), 0.40, 0.04),      # зеленоватое фасадное
         "pet_blue": ((0.12, 0.30, 0.50), 0.55, 0.15),          # синий ПЭТ
         "optic_red": ((0.55, 0.03, 0.02), 0.65, 0.08),         # линзы фар и светофоров
         "optic_amber": ((0.65, 0.30, 0.02), 0.65, 0.08),
         "optic_green": ((0.03, 0.40, 0.15), 0.65, 0.08)}
GLASS_TRANSMISSION = 0.5


def glass_kind(mat: bpy.types.Material) -> str:
    """Вид стекла по материалу исходника («U08_02 • glass_clear | baked retopology», «R06_glass | …»); не стекло — пусто."""
    if not mat or not mat.use_nodes:
        return ""
    bsdf = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    tw = bsdf.inputs.get("Transmission Weight") if bsdf else None
    if tw is None or tw.is_linked or tw.default_value < GLASS_TRANSMISSION:
        return ""
    base = mat.name.split("|")[0].strip()
    kind = base.split("•", 1)[1].strip() if "•" in base else base.split("_", 1)[-1]
    if kind not in GLASS:
        print("urban95: стекло неизвестного вида %r — как прозрачное" % mat.name)
        kind = "glass"
    return kind


def glass_material(model_id: str, kind: str) -> bpy.types.Material:
    """Стекло без карт: цвет, прозрачность (glTF alphaMode BLEND), шероховатость; с обеих сторон."""
    name = "%s_%s" % (model_id, kind if kind.startswith(("glass", "optic")) else "glass_" + kind)
    m = bpy.data.materials.get(name)
    if m:
        return m
    rgb, alpha, rough = GLASS[kind]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = rough
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*rgb, alpha)
    m.surface_render_method = "BLENDED"
    m.use_backface_culling = False
    return m


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
    # материалы на одном атласе → один материал; стекло — своим материалом по виду (не в атлас)
    first: dict[str, bpy.types.Material] = {}
    for o in meshes:
        for slot in o.material_slots:
            kind = glass_kind(slot.material)
            if kind:
                slot.material = glass_material(entry["id"], kind)
                continue
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
