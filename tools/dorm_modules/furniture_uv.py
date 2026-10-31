"""Мебель общежития: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture/models/RING_Dorm_Furniture_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/furniture_uv.py

Форма принята владельцем 2026-10-31 — сетки не меняются (вырезы-модификаторы применяются при разбиении). Как у мусора
(clutter_uv.py): на предмет — один набор текстур (материал с его игровым именем), детали — сетками по слотам материалов
(имена — части слотов finish-spec.json). Выход: RING_Dorm_Furniture_uv_v01.blend рядом с формой (копия)
и _asset_src/dorm_furniture/sp/<предмет>.fbx.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import found_lights_uv as U  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_furniture/sp"
ITEMS = {
    "КР_двухъярусная": "furn_bunk_bed", "КР_одноярусная": "furn_bed", "МТ_матрас": "furn_mattress",
    "ТМ_тумбочка": "furn_nightstand", "ШК_шкаф": "furn_wardrobe", "СТ_стол": "furn_table", "СТУ_стул": "furn_chair",
    "ТБ_табурет": "furn_stool", "ПЛ_полка": "furn_shelf", "ХЛ_холодильник": "furn_fridge", "ДВ_диван": "furn_sofa",
    "КВ_ковёр": "furn_carpet", "ТВ_телевизор": "furn_tv", "ЭП_плитка": "furn_hotplate",
}


def main() -> None:
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    done = []
    for root_name, game in ITEMS.items():
        root = bpy.data.objects.get(root_name)
        if root is None:
            continue
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = U.split_by_material(root, coll)
        U.unwrap(objs)
        mat = bpy.data.materials.get(game) or bpy.data.materials.new(game)
        for ob in objs:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.fbx(filepath=f"{OUT_FBX}/{game}.fbx", use_selection=True, apply_unit_scale=True,
                                 bake_space_transform=False, object_types={"MESH"}, mesh_smooth_type="FACE",
                                 use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y")
        tris = sum(len(p.vertices) - 2 for ob in objs for p in ob.data.polygons)
        print(f"UV {game}: {[o.name for o in objs]}, {tris} треуг.", flush=True)
        coll.hide_viewport = True
        done.append(game)
    src = bpy.data.filepath
    out = src.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out, done)


if __name__ == "__main__":
    main()
