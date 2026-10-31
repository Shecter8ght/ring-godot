"""Оставленный свет: производственная развёртка принятой формы и FBX для Painter (этап текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_FoundLights/models/RING_Dorm_FoundLights_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/found_lights_uv.py

Форма v01 принята владельцем 2026-10-30 — сетки не меняются, фаски применяются как есть. На предмет — один набор
текстур (один материал с именем предмета), детали — отдельными сетками по слотам материалов (их имена — слоты
finish-spec.json, по ним стек Painter раздаёт отделки). Развёртка: Smart UV по углу 66°, общая упаковка всех деталей
предмета с отступом, одинаковая плотность. Выход: models/RING_Dorm_FoundLights_uv_v01.blend (рядом с формой) и
_asset_src/dorm_found_lights/sp/<предмет>.fbx.
"""
import math
import os

import bmesh
import bpy

LIB = "E:/Models Blender/ENVIRONMENT/RING_Dorm_FoundLights/models"
OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_found_lights/sp"
ITEMS = {
    "FL_фонарь_ручной": "found_flashlight", "FL_налобник": "found_headlamp", "FL_химсвет": "found_chemlight",
    "FL_фонарь_кемпинговый": "found_lantern", "FL_свечи": "found_candles", "FL_мигалка": "found_beacon",
}


def split_by_material(root, coll) -> list:
    """Детали предмета → сетки по слотам материалов, в осях корня, с применёнными модификаторами."""
    dg = bpy.context.evaluated_depsgraph_get()
    to_root = root.matrix_world.inverted()
    by_mat = {}
    for ob in root.children_recursive:
        # скрытые от рендера — резцы булевых вырезов, не детали
        if ob.type != "MESH" or ob.hide_render:
            continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        me.transform(to_root @ ob.matrix_world)
        bm = bmesh.new()
        bm.from_mesh(me)
        for mi, mat in enumerate(me.materials):
            faces = [f for f in bm.faces if f.material_index == mi]
            if not faces:
                continue
            part = bm.copy()
            keep = {f.index for f in faces}
            bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in keep], context="FACES")
            by_mat.setdefault(mat.name, []).append(part)
        bm.free()
        bpy.data.meshes.remove(me)
    objs = []
    for name, parts in by_mat.items():
        joined = bmesh.new()
        for part in parts:
            tmp = bpy.data.meshes.new("tmp")
            part.to_mesh(tmp)
            part.free()
            joined.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        # Painter режет многоугольники сам и путает AO на тонких гранях — треугольники заранее
        bmesh.ops.triangulate(joined, faces=[f for f in joined.faces if len(f.verts) > 4])
        me = bpy.data.meshes.new(name)
        joined.to_mesh(me)
        joined.free()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        objs.append(ob)
    return objs


def unwrap(objs) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
        for uv in list(ob.data.uv_layers):
            ob.data.uv_layers.remove(uv)
        ob.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")


def main() -> None:
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    for root_name, game in ITEMS.items():
        root = bpy.data.objects[root_name]
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = split_by_material(root, coll)
        unwrap(objs)
        mat = bpy.data.materials.get(game) or bpy.data.materials.new(game)
        for ob in objs:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            ob.location = (0, 0, 0)
        bpy.ops.object.select_all(action="DESELECT")
        for ob in objs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.fbx(filepath=f"{OUT_FBX}/{game}.fbx", use_selection=True, apply_unit_scale=True,
                                 bake_space_transform=False, object_types={"MESH"}, mesh_smooth_type="FACE",
                                 use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y")
        tris = sum(len(p.vertices) - 2 for ob in objs for p in ob.data.polygons)
        print(f"UV {game}: {len(objs)} деталей {[o.name for o in objs]}, {tris} треуг.")
        coll.hide_viewport = True
    # форма v01 остаётся нетронутой: сохраняем копию с развёрткой рядом
    bpy.ops.wm.save_as_mainfile(filepath=f"{LIB}/RING_Dorm_FoundLights_uv_v01.blend", copy=True, compress=True)
    print("saved", f"{LIB}/RING_Dorm_FoundLights_uv_v01.blend")


if __name__ == "__main__":
    main()
