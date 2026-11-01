"""Мебель общежития: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture/models/RING_Dorm_Furniture_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/furniture_uv.py
  … --background "<RING_Dorm_Furniture_uv_v01.blend>" … furniture_uv.py -- furn_carpet   # только этот предмет, в файле развёртки

Форма принята владельцем 2026-10-31 — сетки не меняются (вырезы-модификаторы применяются при разбиении). Как у мусора
(clutter_uv.py): на предмет — один набор текстур (материал с его игровым именем), детали — сетками по слотам материалов
(имена — части слотов finish-spec.json). Выход: RING_Dorm_Furniture_uv_v01.blend рядом с формой (копия)
и _asset_src/dorm_furniture/sp/<предмет>.fbx.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import found_lights_uv as U  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_furniture/sp"
ITEMS = {
    "КР_двухъярусная": "furn_bunk_bed", "КР_одноярусная": "furn_bed", "МТ_матрас": "furn_mattress",
    "ТМ_тумбочка": "furn_nightstand", "ШК_шкаф": "furn_wardrobe", "СТ_стол": "furn_table", "СТУ_стул": "furn_chair",
    "ТБ_табурет": "furn_stool", "ПЛ_полка": "furn_shelf", "ХЛ_холодильник": "furn_fridge", "ДВ_диван": "furn_sofa",
    "КВ_ковёр": "furn_carpet", "ТВ_телевизор": "furn_tv", "ЭП_плитка": "furn_hotplate",
}
# разрешение набора, если не 2K (карты геометрии print_bake.py, проект Painter — furniture_sp.RES_ITEM): ковёр — 4K,
# лицо почти на всю развёртку, иначе пучки ворса 2,4 × 2 мм не видны (было 0,7 пикс/мм — «кусок пластика», 2026-11-01)
RES = {"furn_carpet": 4096}
# блеск ткани в файле просмотра — Sheen (вес, шероховатость); в Godot — rim (поле godot карточки CP-WOL-RED)
SHEEN = {"furn_carpet": (0.8, 0.45)}


def carpet_uv(objs) -> None:
    """Ковёр: лицо — почти вся развёртка (~2 пикс/мм при 4K); изнанка у стены, торцы и гвозди — вчетверо мельче."""
    wool = next(o for o in objs if o.name.startswith("Ковёр_шерсть"))
    bm = bmesh.new()
    bm.from_mesh(wool.data)
    bm.normal_update()
    uv = bm.loops.layers.uv.active
    loops = [lp for f in bm.faces if f.normal.y < -0.5 for lp in f.loops]
    c = sum((lp[uv].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
    for lp in loops:
        lp[uv].uv = c + (lp[uv].uv - c) * 4.0
    bm.to_mesh(wool.data)
    bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = wool
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")


def main() -> None:
    """Без аргументов — все предметы из файла формы в новый файл развёртки; с именами (-- furn_carpet …) — только они,
    в готовом файле развёртки (прежние сетки предмета удаляются, остальные не трогаются)."""
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    done = []
    for root_name, game in ITEMS.items():
        root = bpy.data.objects.get(root_name)
        if root is None or (only and game not in only):
            continue
        old = bpy.data.collections.get(game)
        if old is not None:
            for ob in list(old.objects):
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            bpy.data.collections.remove(old)
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = U.split_by_material(root, coll)
        U.unwrap(objs)
        if game == "furn_carpet":
            carpet_uv(objs)
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
    if src.endswith("_uv_v01.blend"):
        bpy.ops.wm.save_mainfile(compress=True)
        print("saved", src, done)
        return
    out = src.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out, done)


if __name__ == "__main__":
    main()
