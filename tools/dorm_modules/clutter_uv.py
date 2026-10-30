"""Мусор общежития: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Clutter/models/RING_Dorm_Clutter_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/clutter_uv.py
  (то же на RING_Dorm_Bags_v01.blend)

Формы приняты владельцем 2026-10-30 — сетки не меняются. Как у оставленного света (found_lights_uv.py): на вещь —
один набор текстур (материал с её игровым именем), детали — сетками по слотам материалов (имена — части слотов
finish-spec.json). Лежащая банка — та же целая, отдельного набора нет. Выход: <файл>_uv рядом с формой (копия)
и _asset_src/dorm_clutter/sp/<вещь>.fbx.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import found_lights_uv as U  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_clutter/sp"
ITEMS = {
    "CL_банка_целая": "clutter_can", "CL_банка_мятая": "clutter_can_dented", "CL_банка_раздавлена": "clutter_can_crushed",
    "CL_бутылка_водка": "clutter_bottle_vodka", "CL_бутылка_водка_лежит": "clutter_bottle_vodka_worn",
    "CL_бутылка_пиво": "clutter_bottle_beer", "CL_бутылка_разбита": "clutter_bottle_broken",
    "CL_окурки": "clutter_butts", "CL_гильзы": "clutter_casings",
    "CL_мешок_полный": "clutter_bag_full", "CL_мешок_лежит": "clutter_bag_lying", "CL_мешок_полупустой": "clutter_bag_half",
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
    out = src[:-6] + "_uv.blend" if not src.endswith("_uv.blend") else src
    out = out.replace("_v01_uv.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out, done)


if __name__ == "__main__":
    main()
