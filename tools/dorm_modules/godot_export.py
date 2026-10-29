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
  radiator   — батарея МС-140 с подводкой (M05), корень — внутренняя грань фасада на полу под серединой окна.
"""
import os

import bpy
from mathutils import Matrix

OUT = "E:/Games/RING-godot/assets/models/dorm"
# имя файла: (корень, объекты; None — все потомки корня кроме перечисленных в skip)
PARTS = {
    "door_frame": ("M01_дверь_комнаты", ["дверь_коробка_наличники", "дверь_номерок"]),
    "door_leaf": ("дверь_полотно_ось_петель", ["дверь_полотно", "дверь_ручки", "дверь_петли_скважина"]),
    "window": ("M03_окно", ["окно_коробка", "окно_створки", "окно_стёкла", "окно_фурнитура", "окно_подоконник", "окно_отлив"]),
    "radiator": ("M05_батарея_МС140", ["батарея_секции", "батарея_подводка"]),
}


def export(name: str, root_name: str, names: list) -> None:
    """Части модуля сливаются в одну сетку (поверхность на материал) в осях корня — в Godot один узел на место,
    уровни детализации строит импорт."""
    root = bpy.data.objects[root_name]
    to_root = root.matrix_world.inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    joined = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    mats = []
    for n in names:
        ob = bpy.data.objects[n]
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


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for name, (root, names) in PARTS.items():
        export(name, root, names)


if __name__ == "__main__":
    main()
