"""Транспорт «Проспекта» → glTF для игры (как tools/urban95_export.py: glTF + карты WebP ≤ 2K, индекс с габаритами).

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_export.py -- [класс …]

Источник — «<Имя>_textured_v01.blend» машины (apply_maps.py: игровая сетка LOD0 с картами Painter, варианты коллекциями
«Целый», «Открыт», «Битый», «Сгоревший»). Каждый вариант — одна сетка (колёса и створки в своих положениях вмерзают),
материал на набор текстур: кузов, салон, колесо, низ; стёкла и линзы — прозрачные без карт. Выход:
assets/models/prospekt_vehicles/PV_<класс>[_open|_wreck|_burnt].gltf, карты — в textures/ рядом (имя с классом и семьёй:
у открытого те же карты, что у целого, — файл один). Габарит в игровых осях (Y вверх, лицо машины — +Z) и треугольники —
в общий индекс моделей карты data/urban95_models.json (записи PV_*; чужие записи не трогаются) вместе с группами «вперемешку»
(variants — MallFiller выбирает модель по позиции). LOD — импорт Godot, коллизия на карте — бокс по габариту.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LIB = Path("E:/Models Blender/VEHICLES/Город_партия1")
OUT = ROOT / "assets" / "models" / "prospekt_vehicles"
INDEX = ROOT / "data" / "urban95_models.json"
TMP = ROOT / "_asset_src" / "prospekt_vehicles" / "export_maps"      # копии карт с именами для экспорта (не в git)
MAX_TEX = 2048

# класс: (папка в библиотеке, имя файлов, название)
CARS = {"sedan": ("Седан", "Sedan", "Седан"), "hatch": ("Хэтчбек", "Hatchback", "Хэтчбек"),
        "wagon": ("Универсал", "Wagon", "Универсал"), "suv": ("Внедорожник", "SUV", "Внедорожник"),
        "bus12": ("Автобус_12м", "Bus12", "Автобус 12 м"), "paz": ("ПАЗ", "PAZ", "ПАЗ"),
        "gazel": ("ГАЗель_маршрутка", "Gazel", "ГАЗель-маршрутка")}
VARIANTS = {"Целый": ("", "целый"), "Открыт": ("_open", "двери открыты"), "Битый": ("_wreck", "битый"),
            "Сгоревший": ("_burnt", "сгоревший")}
# группы «вперемешку» для наборов карты (KIT_MODELS в tools/build_prospekt.py): id → (название, состав)
LIGHT = ("sedan", "hatch", "wagon", "suv")
GROUPS = {
    "PV_car": ("Легковые целые вперемешку", [f"PV_{c}" for c in LIGHT]),
    "PV_car_open": ("Легковые с открытыми дверями вперемешку", [f"PV_{c}_open" for c in LIGHT]),
    "PV_car_wreck": ("Легковые битые и сгоревшие вперемешку", [f"PV_{c}_wreck" for c in LIGHT] + [f"PV_{c}_burnt" for c in LIGHT]),
    # брошенные на улицах (бывшие «m:U14_01»): целые, открытые, побитые и хэтчбек Urban 95 среди них
    "PV_car_street": ("Брошенные легковые вперемешку", [f"PV_{c}" for c in LIGHT] + [f"PV_{c}_open" for c in LIGHT] +
                      [f"PV_{c}_wreck" for c in ("sedan", "hatch")] + ["U14_01", "U14_01"]),
    "PV_bus_city": ("Автобусы 12 м: закрыт или двери открыты", ["PV_bus12", "PV_bus12_open"]),
    "PV_paz_any": ("ПАЗ: закрыт или двери открыты", ["PV_paz", "PV_paz_open"]),
    "PV_minibus": ("ГАЗель-маршрутка: закрыта или двери открыты", ["PV_gazel", "PV_gazel_open"]),
}


def occlusion_group() -> bpy.types.NodeTree:
    """Группа «glTF Material Output»: экспортёр берёт из её входа Occlusion карту AO (канал R той же ORM)."""
    g = bpy.data.node_groups.get("glTF Material Output")
    if g:
        return g
    g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def prepare_material(m: bpy.types.Material, cls: str) -> None:
    """Карты с уникальными именами (класс, семья, набор), не больше 2K; AO — в выход glTF."""
    nt = m.node_tree
    sep = None
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeTexImage" and n.image:
            img = n.image
            if not img.name.startswith("PV_"):
                # экспортёр называет карту по имени файла, а у всех машин они одинаковые (Body_baseColor.png) —
                # копия с именем класса и семьи (семья — папка карты: у битой салон и колесо из «clean»)
                fam = Path(bpy.path.abspath(img.filepath)).parent.name
                want = f"PV_{cls}_{fam}_{Path(img.filepath).stem}"
                if max(img.size) > MAX_TEX:
                    k = MAX_TEX / max(img.size)
                    img.scale(int(img.size[0] * k), int(img.size[1] * k))
                TMP.mkdir(parents=True, exist_ok=True)
                img.filepath_raw = str(TMP / f"{want}.png")
                img.file_format = "PNG"
                img.save()
                img.name = want
        if n.bl_idname == "ShaderNodeSeparateColor":
            sep = n
    if sep is not None and not any(n.bl_idname == "ShaderNodeGroup" for n in nt.nodes):
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = occlusion_group()
        nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])


def variant_mesh(col: bpy.types.Collection, name: str) -> bpy.types.Object:
    """Все сетки варианта → одна сетка в осях корня варианта (корень — пустышка без родителя)."""
    root = next(o for o in col.objects if o.type == "EMPTY" and o.parent is None)
    inv = root.matrix_world.inverted()
    meshes = [o for o in col.objects if o.type == "MESH"]
    copies = []
    for o in meshes:
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.matrix_world = Matrix.Identity(4)
        c.data.transform(inv @ o.matrix_world)
        if (inv @ o.matrix_world).determinant() < 0:      # зеркальная копия (внутреннее колесо пары) — нормали наружу
            c.data.flip_normals()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    bpy.ops.object.material_slot_remove_unused()
    return ob


def export_class(cls: str, index: dict) -> None:
    folder, fname, title = CARS[cls]
    src = LIB / folder / "game" / f"{fname}_textured_v01.blend"
    if not src.exists():
        print("нет файла:", src)
        return
    bpy.ops.wm.open_mainfile(filepath=str(src))
    for m in bpy.data.materials:
        if m.name.startswith("SP_") and m.use_nodes:
            prepare_material(m, cls)
    cols = [c for c in bpy.data.collections if c.name in VARIANTS]
    OUT.mkdir(parents=True, exist_ok=True)
    for col in cols:
        suffix, vname = VARIANTS[col.name]
        mid = f"PV_{cls}{suffix}"
        ob = variant_mesh(col, mid)
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        xs = [v.co.x for v in ob.data.vertices]
        ys = [v.co.y for v in ob.data.vertices]
        zs = [v.co.z for v in ob.data.vertices]
        lo = (min(xs), min(zs), -max(ys))                     # игровые оси: x = x, y = z (вверх), z = −y
        hi = (max(xs), max(zs), -min(ys))
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        path = OUT / f"{mid}.gltf"
        bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures",
                                  use_selection=True, export_apply=True, export_yup=True, export_texcoords=True,
                                  export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                                  export_image_quality=90, export_cameras=False, export_lights=False,
                                  export_animations=False)
        index["models"][mid] = {
            "id": mid, "name": f"{title}, {vname}", "file": f"res://assets/models/prospekt_vehicles/{mid}.gltf",
            "triangles": tris, "materials": len(ob.material_slots),
            "aabb": {"center": [round((lo[i] + hi[i]) * 0.5, 4) for i in range(3)],
                     "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
            "root_offset": [0, 0, 0]}
        print(f"vehicles: {mid} — {tris} треуг., материалов {len(ob.material_slots)}, габарит "
              f"{index['models'][mid]['aabb']['size']}")
        bpy.data.objects.remove(ob, do_unlink=True)


def groups(index: dict) -> None:
    """Группы «вперемешку»: состав — только то, что уже выгружено; габарит — охватывающий (для отбора в build_prospekt)."""
    models = index["models"]
    for gid, (name, members) in GROUPS.items():
        have = [m for m in members if m in models]
        if not have:
            continue
        lo = [min(models[m]["aabb"]["center"][i] - models[m]["aabb"]["size"][i] / 2 for m in have) for i in range(3)]
        hi = [max(models[m]["aabb"]["center"][i] + models[m]["aabb"]["size"][i] / 2 for m in have) for i in range(3)]
        models[gid] = {"id": gid, "name": name, "file": "", "variants": have,
                       "triangles": max(int(models[m]["triangles"]) for m in have), "materials": 0,
                       "aabb": {"center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)],
                                "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
                       "root_offset": [0, 0, 0]}
        print(f"группа {gid}: {len(have)} — {', '.join(have)}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    wanted = argv or list(CARS)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    for cls in wanted:
        export_class(cls, index)
    groups(index)
    # индекс общий (Urban 95, растения других сессий): перечитать перед записью и заменить только свои записи PV_*
    fresh = json.loads(INDEX.read_text(encoding="utf-8"))
    for k, v in index["models"].items():
        if k.startswith("PV_"):
            fresh["models"][k] = v
    INDEX.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


main()
