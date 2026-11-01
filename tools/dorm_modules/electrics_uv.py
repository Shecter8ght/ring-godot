"""Электрика общежития: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Electrics/models/RING_Dorm_Electrics_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/electrics_uv.py

Форма принята владельцем 2026-11-01 — сетки не меняются (вырезы-модификаторы применяются). Наборы текстур — по
деталям, а не по вариантам: трубка ЛБ-40 и лампа А60 общие у всех светильников (целая и битая — в одном наборе),
корпуса светильников, плафон, патрон, выключатели, розетки, коробка, провода — свои. Игровые варианты потом включают
и выключают детали, поэтому то, что в игре отдельный узел, — своя сетка уже здесь: имя «<слот>__<метка>» (рычажок,
клавиша, рассеиватель, битая колба, обломок трубки, модули провода). Слот finish-spec.json — часть имени до «__».
Выход: RING_Dorm_Electrics_uv_v01.blend рядом с формой и _asset_src/dorm_electrics/sp/<набор>.fbx.
"""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import found_lights_uv as U  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_electrics/sp"


def tube_tag(name, c):
    return "обломок" if c.y > 0 else ""          # в «одна и обломок» обломок — на +Y


def wire_tag(name, c):
    for k in ("прямой_1м", "залом_вниз", "стена_потолок"):
        if k in name:
            return k
    return ""


# набор: [(корень формы, начала имён деталей или None — все, разметка «отдельных узлов» (имя, центр грани) → метка)]
ITEMS = {
    "el_tube": [("СВ_ЛСП_одна_и_обломок", ("ЛСП_трубки_", "ЛСП_цоколи_", "ЛСП_штырьки_"), tube_tag)],
    "el_bulb": [("СВ_патрон_лампа", ("Патрон_лампа_лампа_",), None),
                ("СВ_патрон_разбита", ("Патрон_лампа_разбита_колба",), lambda n, c: "разбита")],
    "el_lsp": [("СВ_ЛСП_пусто", None, None)],
    "el_lpo": [("СВ_ЛПО_закрыт", ("ЛПО_корпус_", "ЛПО_держатели_", "ЛПО_рассеиватель_"),
                lambda n, c: "рассеиватель" if "рассеиватель" in n else "")],
    "el_plafond": [("СВ_плафон_стекло", ("Плафон_основание_", "Плафон_патрон_", "Плафон_стекло_"), None)],
    "el_pendant": [("СВ_патрон_нет_лампы", None, None)],
    "el_switch_round": [("ВК_круглый", None, lambda n, c: "рычажок" if "рычажок" in n else "")],
    "el_socket_round": [("РЗ_круглая", None, None)],
    "el_switch_white": [("ВК_белый", None, lambda n, c: "клавиша" if "клавиша" in n else "")],
    "el_socket_white": [("РЗ_белая", None, None)],
    "el_box": [("КР_распаечная", None, None)],
    "el_wire_flat": [("ПР_плоский", None, wire_tag)],
    "el_wire_twisted": [("ПР_витой", None, None)],
}

GAMES = list(ITEMS)  # для print_bake.py
# сдвиг детали в наборе на время текстур (м): совпавшая с соседней поверхность портит запекание затенения;
# игровой этап возвращает деталь на место (вычитает сдвиг)
OFFSETS = {"el_bulb": {"Лампа_стекло__разбита": (0.12, 0.0, 0.0)}}


def split(root, prefixes, tagger, coll, buckets):
    """Детали корня → грани по ключу «материал[__метка]», в осях корня, с применёнными модификаторами."""
    dg = bpy.context.evaluated_depsgraph_get()
    to_root = root.matrix_world.inverted()
    for ob in root.children_recursive:
        if ob.type != "MESH" or ob.hide_render:
            continue
        if prefixes and not ob.name.startswith(prefixes):
            continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        me.transform(to_root @ ob.matrix_world)
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            mat = me.materials[f.material_index].name.split(".")[0] if me.materials else "без_материала"
            tag = tagger(ob.name, f.calc_center_median()) if tagger else ""
            key = mat + (f"__{tag}" if tag else "")
            buckets.setdefault(key, []).append((bm, f.index, me.materials[f.material_index] if me.materials else None))
        buckets.setdefault("__keep__", []).append(bm)
        bpy.data.meshes.remove(me)


def build_item(game, spec, coll):
    buckets = {}
    for root_name, prefixes, tagger in spec:
        split(bpy.data.objects[root_name], prefixes, tagger, coll, buckets)
    objs = []
    for key, faces in buckets.items():
        if key == "__keep__":
            continue
        out = bmesh.new()
        by_src = {}
        for bm, idx, mat in faces:
            by_src.setdefault(id(bm), (bm, set()))[1].add(idx)
        for bm, idxs in by_src.values():
            part = bm.copy()
            part.faces.ensure_lookup_table()
            bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in idxs], context="FACES")
            tmp = bpy.data.meshes.new("tmp")
            part.to_mesh(tmp)
            part.free()
            out.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
        bmesh.ops.triangulate(out, faces=[f for f in out.faces if len(f.verts) > 4])
        off = OFFSETS.get(game, {}).get(key)
        if off:
            bmesh.ops.translate(out, vec=off, verts=out.verts)
        me = bpy.data.meshes.new(key)
        out.to_mesh(me)
        out.free()
        ob = bpy.data.objects.new(key, me)
        coll.objects.link(ob)
        objs.append(ob)
    for bm in buckets.get("__keep__", []):
        bm.free()
    return objs


def main() -> None:
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    for game, spec in ITEMS.items():
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = build_item(game, spec, coll)
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
        print(f"UV {game}: {sorted(o.name for o in objs)}, {tris} треуг.", flush=True)
        coll.hide_viewport = True
    out = bpy.data.filepath.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
