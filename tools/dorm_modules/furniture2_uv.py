"""Мебель общежития, партия 2: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture/models/RING_Dorm_Furniture2_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/furniture2_uv.py

Форма принята владельцем 2026-11-02 — сетки не меняются (вырезы-модификаторы применяются). На предмет — один набор
текстур (материал с его игровым именем), детали — сетками по слотам материалов. То, что в игре открывается или
снимается отдельно, — своя сетка уже здесь: «<слот>__<метка>» (дверцы, ящик, дверца духовки, дверца кабинки, сиденье);
слот finish-spec-2.json — часть имени до «__». Варианты формы с другой геометрией входят в набор основного предмета
своими сетками: отбитая раковина («__отбита»), оборванная смывная труба («__оборвана»), крайняя перегородка
(«__крайняя»); распахнутые дверцы — те же сетки в другом положении (игровой этап). Выход:
RING_Dorm_Furniture2_uv_v01.blend рядом с формой и _asset_src/dorm_furniture2/sp/<набор>.fbx.
"""
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import electrics_uv as E  # noqa: E402
import found_lights_uv as U  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_furniture2/sp"


def mover(name, c):
    """Метка подвижной детали по имени объекта формы (дочерние — ручки, стекло, петли — идут с дверцей)."""
    n = name.split(".")[0]
    if "_лев" in n and ("дверц" in n or "ручка" in n):
        return "дверца_лев"
    if "_прав" in n and ("дверц" in n or "ручка" in n):
        return "дверца_прав"
    if n.startswith("СР_") and ("ящик" in n):
        return "ящик"
    if n in ("ЭП_дверца", "ЭП_стекло", "ЭП_ручка_дверцы"):
        return "дверца"
    if n in ("КБ_дверца", "КБ_петли_щеколда"):
        return "дверца"
    if n == "УН_сиденье":
        return "сиденье"
    return ""


# набор: [(корень формы, начала имён деталей или None — все, разметка «отдельных узлов»)]
ITEMS = {
    "furn_stove": [("ЭП_плита", None, mover)],
    "furn_sink": [("МК_мойка", None, mover)],
    "furn_counter": [("СР_стол_тумба", None, mover)],
    "furn_dining": [("ОС_стол_обеденный", None, None)],
    "furn_wallcab": [("ШН_шкафчик", None, mover)],
    "furn_dishrack": [("ПП_полка_посуда", None, None)],
    "furn_pot": [("ПС_кастрюля", None, None)],
    "furn_kettle": [("ПС_чайник", None, None)],
    "furn_pan": [("ПС_сковорода", None, None)],
    "furn_can": [("БД_бидон", None, None)],
    "furn_bucket": [("БК_бак", None, None)],
    "furn_basin": [("РК_раковина", None, None), ("РК_раковина_отбита", ("РК_чаша",), lambda n, c: "отбита")],
    "furn_mirror": [("ЗР_зеркало", None, None)],
    "furn_toilet": [("УН_унитаз", None, mover), ("УН_унитаз_без_бачка", ("УН_смывная_труба",), lambda n, c: "оборвана")],
    "furn_stall": [("КБ_кабинка", None, mover), ("КБ_перегородка", None, lambda n, c: "крайняя")],
}
GAMES = list(ITEMS)  # для print_bake.py
# сдвиг сеток-вариантов на время текстур (м): лежа на месте основной детали, они затеняли её при запекании (пятна на
# целой раковине у отбитого угла); игровой этап и файл просмотра возвращают их на место (вычитают сдвиг)
OFFSETS = {"furn_basin": {"Фаянс__отбита": (0.8, 0.0, 0.0)},
           "furn_toilet": {"Труба_краска__оборвана": (0.6, 0.0, 0.0)},
           "furn_stall": {"Перегородка_краска__крайняя": (1.0, 0.0, 0.0), "Сталь_окраска__крайняя": (1.0, 0.0, 0.0)}}
E.OFFSETS.update(OFFSETS)
# крупнее в развёртке то, что разглядывают вблизи и где печать (SCALE ниже)
PANEL_N = Vector((0.0, -0.968, -0.249))


def uv_islands(bm, uv) -> list:
    """Острова развёртки: грани, соединённые ребром с совпадающими UV на обоих концах."""
    parent = {f.index: f.index for f in bm.faces}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        f0, f1 = lf
        same = True
        for v in e.verts:
            u0 = next(lp[uv].uv for lp in f0.loops if lp.vert == v)
            u1 = next(lp[uv].uv for lp in f1.loops if lp.vert == v)
            if (u0 - u1).length > 1e-5:
                same = False
        if same:
            parent[find(f0.index)] = find(f1.index)
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return list(groups.values())


def enlarge(objs) -> None:
    """Масштаб островов целиком (не отдельных граней — остров не рвётся), затем укладка заново."""
    for ob in objs:
        base = ob.name.split(".")[0]
        if base not in SCALE:
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv.active
        pick, k = SCALE[base]
        for island in uv_islands(bm, uv):
            if pick is not None and not any(pick(f) for f in island):
                continue
            loops = [lp for f in island for lp in f.loops]
            c = sum((lp[uv].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
            for lp in loops:
                lp[uv].uv = c + (lp[uv].uv - c) * k
        bm.to_mesh(ob.data)
        bm.free()
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")


# плита: панель (шкалы ручек) ×5, лицо и изнанка дверцы (марка) ×1,5, тёмная камера духовки ×0,5 — при общей
# плотности ~1 пикс/мм цифры шкал 4–5 мм выходили в 3–5 пикселей, теперь ~16
# панель — только сама наклонная полоса: лицо корпуса и задний борт смотрят почти так же (cos 0,97)
SCALE = {"Плита_эмаль": (lambda f: f.normal.dot(PANEL_N) > 0.995 and 0.76 < f.calc_center_median().z < 0.85
                         and f.calc_center_median().y < -0.25, 5.0),
         "Плита_эмаль__дверца": (None, 1.5), "Духовка_эмаль": (None, 0.5)}


def main() -> None:
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    for game, spec in ITEMS.items():
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = E.build_item(game, spec, coll)
        U.unwrap(objs)
        if game == "furn_stove":
            enlarge(objs)
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
