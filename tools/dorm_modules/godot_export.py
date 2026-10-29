"""Модули общежития → Godot: assets/models/dorm/*.glb (сетки с применёнными фасками, имена материалов; карт нет —
материалы ставит стенд, src/blockout/dorm_modules.gd).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/models/RING_Dorm_Modules_v03.blend" \
      --python-exit-code 1 --python tools/dorm_modules/godot_export.py

Каждый файл — одна сетка (части слиты, поверхность на материал) от своего корня в начале координат (оси Blender: X вдоль стены, +Y — коридор у двери / комната у окна,
Z вверх; glTF: Y вверх, +Y Blender → −Z):
  door_frame — коробка с добором и наличниками, номерок (M01 без полотна), корень — середина проёма на полу, ось стены;
  door_leaf  — полотно, ручки, петли и скважина от оси петель (M01), начало — на оси петель;
  window     — окно с переплётами, стёклами, фурнитурой, подоконником и отливом (M03), корень — середина окна на полу,
               ось фасадной стены;
  radiator   — батарея МС-140 с подводкой (M05), корень — внутренняя грань фасада на полу под серединой окна;
  stair_flight_12 / _10 — марш M09 / M10, корень — передняя кромка первой ступени у пола, середина ширины, подъём по +Y;
  stair_rail_12 / _10   — ограждение марша M12 (сбоку +X) в осях того же марша;
  stair_turn_<a>_<b>    — поворот ограждения M13 через просвет 0,30 между маршами (тем же railing_turn, что в сборке):
               начало — середина просвета на кромке площадки, на её уровне, +Y — в площадку; слева (−X) конец поручня
               марша с подступёнком a мм, справа — начало марша с b (12 — 164,2 мм первого этажа, 10 — 162 мм жилых).
"""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUT = "E:/Games/RING-godot/assets/models/dorm"
# имя файла: (корень, объекты)
PARTS = {
    "door_frame": ("M01_дверь_комнаты", ["дверь_коробка_наличники", "дверь_номерок"]),
    "door_leaf": ("дверь_полотно_ось_петель", ["дверь_полотно", "дверь_ручки", "дверь_петли_скважина"]),
    "window": ("M03_окно", ["окно_коробка", "окно_створки", "окно_стёкла", "окно_фурнитура", "окно_подоконник", "окно_отлив"]),
    "radiator": ("M05_батарея_МС140", ["батарея_секции", "батарея_подводка"]),
    "stair_flight_12": ("M09_марш_12", ["M09_марш_12_бетон"]),
    "stair_flight_10": ("M10_марш_10", ["M10_марш_10_бетон"]),
    "stair_rail_12": ("M12_ограждение_марша_12", ["M12_ограждение_марша_12_сталь", "M12_ограждение_марша_12_поручень"]),
    "stair_rail_10": ("M12_ограждение_марша_10", ["M12_ограждение_марша_10_сталь", "M12_ограждение_марша_10_поручень"]),
}
# подступёнки маршей плана: 12 ступеней первого этажа и 10 жилых
RISERS = {"12": 0.1642, "10": 0.162}
TURNS = [("12", "12"), ("10", "10"), ("12", "10")]


def export(name: str, root: bpy.types.Object, objects: list) -> None:
    """Части модуля сливаются в одну сетку (поверхность на материал) в осях корня — в Godot один узел на место,
    уровни детализации строит импорт."""
    to_root = root.matrix_world.inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    joined = bpy.data.meshes.new(name)
    bm = bmesh.new()
    mats = []
    for ob in objects:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        me.transform(to_root @ ob.matrix_world)
        # номера материалов — в общий список слотов
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for poly in me.polygons:
            poly.material_index = remap[poly.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bm.to_mesh(joined)
    bm.free()
    for m in mats:
        joined.materials.append(m)
    ob = bpy.data.objects.new(name, joined)
    bpy.context.scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(OUT, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_materials="EXPORT", export_image_format="NONE",
                              export_texcoords=True, export_normals=True, export_tangents=True,
                              export_cameras=False, export_lights=False, export_extras=False)
    print(f"{name}: {len(joined.polygons)} граней, {sum(len(p.vertices) - 2 for p in joined.polygons)} треугольников, "
          f"материалы {[m.name for m in mats]} → {path}")
    bpy.data.objects.remove(ob)


def turn(a: str, b: str) -> None:
    """Поворот ограждения по концам поручней двух маршей (как stair_core сборки), во временной коллекции."""
    import build_modules as B
    import mlib as L
    xb = B.FLIGHT_W / 2 + 0.03
    x = 0.9 - xb                       # оси маршей — в 0,9 от середины просвета
    strip_top = 0.855
    ra, rb = RISERS[a], RISERS[b]
    # конец поручня марша a — на 0,01 за кромкой площадки, начало марша b — так же (y_end / y_start ограждения)
    p_low = (-x, 0.01, ra + ra / B.TREAD * 0.01 + strip_top)
    p_high = (x, 0.01, rb - rb / B.TREAD * 0.01 + strip_top)
    coll = L.collection("_экспорт_повороты")
    m = {"handrail": bpy.data.materials["Поручень_дерево"], "rail": bpy.data.materials["Ограждение_краска"]}
    root = B.railing_turn(coll, m, p_low, p_high, 0.0)
    export(f"stair_turn_{a}_{b}", root, [o for o in root.children_recursive if o.type == "MESH"])
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for name, (root, names) in PARTS.items():
        if not only or name in only:
            export(name, bpy.data.objects[root], [bpy.data.objects[n] for n in names])
    for a, b in TURNS:
        if not only or f"stair_turn_{a}_{b}" in only:
            turn(a, b)


if __name__ == "__main__":
    main()
