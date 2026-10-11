"""Ускоритель снаряжения магазинов (предмет mag_loader): модель по фото полимерных планочных
загрузчиков под обойму (StripLULA и подобные; свой вариант без надписей и логотипов).

Образец: длинный П-образный жёлоб 135 x 28 x 30 мм (в него опускается обойма с патронами), сверху
ходит толкатель с широкой ребристой площадкой под большой палец, снизу — замок, которым загрузчик
садится на горловину магазина, и кольцо для карабина. Материал — чёрный стеклонаполненный полимер.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_mag_loader.py

Пишет _asset_src/mag_loader/mag_loader.blend, assets/items/models/mag_loader.glb и превью
docs/screens/mag_loader_preview.png. Модель лежит на спинке жёлоба: длина по X, ширина по Y.
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src" / "mag_loader"
OUT = ROOT / "assets" / "items" / "models" / "mag_loader.glb"
PREVIEW = ROOT / "docs" / "screens" / "mag_loader_preview.png"
MM = 0.001


def mat(name: str, color, rough: float, metal: float = 0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


def box(name: str, size, at, material, bevel: float = 0.0, segments: int = 2):
    """Брусок size (мм) с центром at (мм); bevel — фаска кромок, мм."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=Vector(at) * MM)
    o = bpy.context.active_object
    o.name = name
    o.scale = Vector(size) * MM
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(material)
    if bevel > 0.0:
        bv = o.modifiers.new("bevel", "BEVEL")
        bv.width = bevel * MM
        bv.segments = segments
        bv.limit_method = "ANGLE"
        bv.angle_limit = math.radians(35.0)
    return o


def cut(target, cutter):
    """Вычесть cutter из target (точный решатель) и убрать резак."""
    m = target.modifiers.new("cut", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    bpy.context.view_layer.objects.active = target
    # вырез — до фаски: фаска идёт по уже готовой форме
    while target.modifiers[0].name != "cut":
        bpy.ops.object.modifier_move_up(modifier="cut")
    bpy.ops.object.modifier_apply(modifier="cut")
    bpy.data.objects.remove(cutter, do_unlink=True)


def build() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    polymer = mat("loader_polymer", (0.028, 0.03, 0.033), 0.56)
    polymer_smooth = mat("loader_polymer_smooth", (0.04, 0.042, 0.046), 0.34)
    steel = mat("loader_steel", (0.55, 0.56, 0.58), 0.32, 1.0)
    parts = []

    # --- жёлоб: спинка внизу (z = 0), открыт вверх; длина 135 по X
    body = box("Channel", (135, 28, 20), (0, 0, 10), polymer, 0.9)
    cut(body, box("c", (140, 21, 18), (0, 0, 13), polymer))
    # скос на свободном конце: обойма заходит под углом
    wedge = box("c", (30, 40, 30), (70, 0, 31), polymer)
    wedge.rotation_euler.y = math.radians(-35.0)
    cut(body, wedge)
    # окно в спинке: видно, сколько патронов осталось в обойме
    cut(body, box("c", (52, 9, 12), (8, 0, 0), polymer))
    parts.append(body)
    # направляющие под закраины обоймы — по обеим стенкам изнутри
    for side in (-1, 1):
        parts.append(box("Rail", (128, 1.4, 1.6), (-2, side * 9.9, 9.5), polymer, 0.3, 1))
    # гладкая площадка на стенке (под маркировку; надписей нет)
    parts.append(box("Plate", (44, 0.7, 11), (-6, -14.2, 10.5), polymer_smooth, 0.25, 1))
    # рёбра жёсткости снаружи стенок
    for side in (-1, 1):
        for i in range(5):
            parts.append(box("Rib", (2.2, 1.0, 16), (30 + i * 7.5, side * 14.3, 10), polymer, 0.3, 1))

    # --- замок на горловину магазина: шире жёлоба, с пазом и защёлкой
    clamp = box("Clamp", (26, 37, 27), (-62, 0, 13.5), polymer, 1.1)
    cut(clamp, box("c", (30, 24.5, 30), (-62, 0, 19), polymer))   # паз под магазин
    cut(clamp, box("c", (12, 44, 9), (-66, 0, 22), polymer))      # вырез под зуб защёлки
    parts.append(clamp)
    latch = box("Latch", (14, 5, 15), (-57, 20.2, 12), polymer_smooth, 0.8)
    parts.append(latch)
    parts.append(box("LatchGrip", (10, 1.2, 2), (-57, 23.0, 16), polymer, 0.3, 1))
    parts.append(box("LatchGrip", (10, 1.2, 2), (-57, 23.0, 12), polymer, 0.3, 1))
    parts.append(box("LatchGrip", (10, 1.2, 2), (-57, 23.0, 8), polymer, 0.3, 1))
    # ось защёлки и кольцо для карабина
    bpy.ops.mesh.primitive_cylinder_add(radius=1.3 * MM, depth=10 * MM, location=Vector((-66, 18.5, 12)) * MM, vertices=20)
    pin = bpy.context.active_object
    pin.name = "LatchPin"
    pin.data.materials.append(steel)
    parts.append(pin)
    bpy.ops.mesh.primitive_torus_add(major_radius=5.2 * MM, minor_radius=0.7 * MM, major_segments=36, minor_segments=10,
                                     location=Vector((-78.5, -11, 6)) * MM, rotation=(math.radians(90.0), 0.0, math.radians(25.0)))
    ring = bpy.context.active_object
    ring.name = "Ring"
    ring.data.materials.append(steel)
    parts.append(ring)
    parts.append(box("RingEar", (5, 3, 7), (-74.5, -11, 6), polymer, 0.7))

    # --- толкатель: шток в жёлобе и широкая ребристая площадка под большой палец
    parts.append(box("Stem", (96, 8, 11), (4, 0, 14.5), polymer_smooth, 0.9))
    pad = box("Pad", (30, 62, 9), (50, 0, 25.5), polymer, 1.6, 3)
    # выемка под палец — площадка слегка вогнута
    bpy.ops.mesh.primitive_cylinder_add(radius=70 * MM, depth=70 * MM, vertices=96, location=Vector((50, 0, 99.2)) * MM,
                                        rotation=(math.radians(90.0), 0.0, 0.0))
    cut(pad, bpy.context.active_object)
    parts.append(pad)
    for i in range(7):
        x = 38.5 + i * 3.85
        # рёбра следуют выемке: по краям выше
        z = 29.4 + ((x - 50.0) ** 2) / 140.0
        parts.append(box("PadRib", (1.5, 56, 1.3), (x, 0, z), polymer, 0.35, 1))
    # шейка между площадкой и штоком
    parts.append(box("Neck", (18, 9, 8), (48, 0, 19.5), polymer, 0.8))
    # упоры площадки: не дают ей уйти в жёлоб глубже стенок
    for side in (-1, 1):
        parts.append(box("PadStop", (22, 4, 3), (50, side * 16, 21.6), polymer, 0.5, 1))

    # --- собрать в один объект, применить фаски, сгладить по углу
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        for m in list(o.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    loader = bpy.context.active_object
    loader.name = "MagLoader"
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38.0))
    # начало координат — в центр основания: предмет лежит на спинке
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

    box_min = Vector((min(v.co.x for v in loader.data.vertices), min(v.co.y for v in loader.data.vertices), min(v.co.z for v in loader.data.vertices)))
    box_max = Vector((max(v.co.x for v in loader.data.vertices), max(v.co.y for v in loader.data.vertices), max(v.co.z for v in loader.data.vertices)))
    size = (box_max - box_min) * 1000.0
    print("mag_loader: габариты %.1f x %.1f x %.1f мм, вершин %d, граней %d" % (size.x, size.y, size.z, len(loader.data.vertices), len(loader.data.polygons)))

    SRC.mkdir(parents=True, exist_ok=True)
    (SRC / "license.txt").write_text("Собственная модель проекта RING (tools/build_mag_loader.py), 2026-10-11.\n"
                                     "Образец формы — полимерные планочные загрузчики магазинов под обойму; надписей и логотипов нет.\n", encoding="utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT), export_format="GLB", export_apply=True, export_yup=True)

    # --- превью: три источника, вид в три четверти
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 70
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = Vector((0.20, -0.26, 0.21))
    direction = Vector((-0.005, 0.0, 0.012)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    for name, at, energy, size_m in (("key", (0.3, -0.25, 0.4), 5.0, 0.3), ("fill", (-0.35, -0.2, 0.25), 1.5, 0.5), ("rim", (-0.1, 0.35, 0.3), 4.0, 0.3)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size_m
        lo = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(lo)
        lo.location = at
        lo.rotation_euler = (Vector((0, 0, 0.01)) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, -0.0002))
    floor = bpy.context.active_object
    floor.data.materials.append(mat("floor", (0.16, 0.15, 0.14), 0.85))
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.055, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
    bpy.context.scene.world = world
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 900
    scene.render.filepath = str(PREVIEW)
    bpy.ops.wm.save_as_mainfile(filepath=str(SRC / "mag_loader.blend"))
    bpy.ops.render.render(write_still=True)
    # пол превью в игру не идёт: он добавлен после экспорта


build()
