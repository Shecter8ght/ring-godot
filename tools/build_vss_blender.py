"""Редактируемый наружный ассет ВСС по фотографиям владельца проекта.

Запуск выбранным Blender: --factory-startup --background --python tools/build_vss_blender.py
Аргументы после --: --stage blockout|final, --output каталог, --render.
Модель художественная; скрытая механика не реконструируется.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector


MM = 0.001
ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / '_asset_src' / 'vss_picatinny'
COLLECTIONS: dict[str, bpy.types.Collection] = {}
PARTS: dict[str, bpy.types.Object] = {}
MATERIALS: dict[str, bpy.types.Material] = {}


def enum_set(owner, property_name: str, desired: str) -> None:
    valid = [i.identifier for i in owner.bl_rna.properties[property_name].enum_items]
    if desired in valid:
        setattr(owner, property_name, desired)


def collection(name: str, parent=None) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(result)
    COLLECTIONS[name] = result
    return result


def relocate(obj: bpy.types.Object, group: str, parent=None) -> bpy.types.Object:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    COLLECTIONS[group].objects.link(obj)
    if parent is not None:
        matrix = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = matrix
    return obj


def empty(name: str, position: tuple, group: str, parent=None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    COLLECTIONS[group].objects.link(obj)
    obj.location = tuple(v * MM for v in position)
    obj.empty_display_size = 0.014
    bpy.context.view_layer.update()
    if parent:
        matrix = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = matrix
    PARTS[name] = obj
    return obj


def material(name: str, color: tuple, metallic: float, roughness: float) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    shader = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    MATERIALS[name] = mat
    return mat


def micro_surface(mat: bpy.types.Material, scale: float, strength: float, distance: float) -> None:
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nodes.new('ShaderNodeTexCoord')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 2.1
    links.new(coord.outputs['Object'], noise.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = distance
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])


def build_materials() -> None:
    steel = material('Blued steel', (0.028, 0.036, 0.044), 0.82, 0.31)
    micro_surface(steel, 1700, 0.12, 0.000018)
    material('Machined edges', (0.075, 0.087, 0.100), 0.9, 0.25)
    material('Recess black', (0.006, 0.008, 0.011), 0.35, 0.49)
    polymer = material('Handguard polymer', (0.034, 0.032, 0.029), 0.05, 0.48)
    micro_surface(polymer, 2100, 0.25, 0.000055)
    mag = material('Magazine polymer', (0.022, 0.020, 0.020), 0.05, 0.41)
    micro_surface(mag, 2200, 0.16, 0.000025)
    rubber = material('Butt pad rubber', (0.014, 0.015, 0.016), 0, 0.73)
    micro_surface(rubber, 1200, 0.2, 0.00006)
    material('Sight index', (0.47, 0.43, 0.32), 0.15, 0.51)
    material('Silhouette clay', (0.34, 0.36, 0.38), 0, 0.55)
    wood = material('Varnished walnut amber', (0.30, 0.10, 0.028), 0, 0.33)
    nodes, links = wood.node_tree.nodes, wood.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Coat Weight'].default_value = 0.32
    bsdf.inputs['Coat Roughness'].default_value = 0.24
    coord = nodes.new('ShaderNodeTexCoord')
    scale = nodes.new('ShaderNodeVectorMath')
    enum_set(scale, 'operation', 'MULTIPLY')
    scale.inputs[1].default_value = (1.7, 36, 19)
    links.new(coord.outputs['Generated'], scale.inputs[0])
    grain = nodes.new('ShaderNodeTexNoise')
    grain.inputs['Scale'].default_value = 4.0
    grain.inputs['Detail'].default_value = 4.0
    grain.inputs['Roughness'].default_value = 0.66
    links.new(scale.outputs['Vector'], grain.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (0.055, 0.014, 0.003, 1)
    ramp.color_ramp.elements[1].position = 0.84
    ramp.color_ramp.elements[1].color = (0.48, 0.22, 0.065, 1)
    element = ramp.color_ramp.elements.new(0.46)
    element.color = (0.205, 0.061, 0.012, 1)
    element = ramp.color_ramp.elements.new(0.64)
    element.color = (0.355, 0.132, 0.025, 1)
    links.new(grain.outputs['Fac'], ramp.inputs[0])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    pores = nodes.new('ShaderNodeTexNoise')
    pores.inputs['Scale'].default_value = 10
    pores.inputs['Detail'].default_value = 2
    links.new(scale.outputs['Vector'], pores.inputs['Vector'])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.16
    bump.inputs['Distance'].default_value = 0.00012
    links.new(pores.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    knurl = material('Suppressor fine crosshatch', (0.024, 0.030, 0.037), 0.78, 0.42)
    nodes, links = knurl.node_tree.nodes, knurl.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    coord = nodes.new('ShaderNodeTexCoord')
    separate = nodes.new('ShaderNodeSeparateXYZ')
    links.new(coord.outputs['UV'], separate.inputs[0])
    waves = []
    for sign in (1, -1):
        u = nodes.new('ShaderNodeMath')
        enum_set(u, 'operation', 'MULTIPLY')
        u.inputs[1].default_value = 180 * math.tau
        links.new(separate.outputs['X'], u.inputs[0])
        v = nodes.new('ShaderNodeMath')
        enum_set(v, 'operation', 'MULTIPLY')
        v.inputs[1].default_value = sign * 112 * math.tau
        links.new(separate.outputs['Y'], v.inputs[0])
        add = nodes.new('ShaderNodeMath')
        enum_set(add, 'operation', 'ADD')
        links.new(u.outputs[0], add.inputs[0])
        links.new(v.outputs[0], add.inputs[1])
        sine = nodes.new('ShaderNodeMath')
        enum_set(sine, 'operation', 'SINE')
        links.new(add.outputs[0], sine.inputs[0])
        waves.append(sine)
    multiply = nodes.new('ShaderNodeMath')
    enum_set(multiply, 'operation', 'MULTIPLY')
    links.new(waves[0].outputs[0], multiply.inputs[0])
    links.new(waves[1].outputs[0], multiply.inputs[1])
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.22
    bump.inputs['Distance'].default_value = 0.00014
    links.new(multiply.outputs[0], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])


def bevel(obj: bpy.types.Object, width: float, segments: int = 3) -> None:
    mod = obj.modifiers.new('Small edge radii', 'BEVEL')
    mod.width = width * MM
    mod.segments = segments
    enum_set(mod, 'limit_method', 'ANGLE')
    mod.angle_limit = math.radians(25)
    mod.harden_normals = True
    mod.use_clamp_overlap = True
    normal = obj.modifiers.new('Area weighted normals', 'WEIGHTED_NORMAL')
    enum_set(normal, 'mode', 'FACE_AREA')
    normal.keep_sharp = True
    normal.weight = 50


def mesh_object(name: str, vertices: list, faces: list, mat: str, group: str,
                radius: float = 0, parent=None) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata([tuple(c * MM for c in p) for p in vertices], [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    COLLECTIONS[group].objects.link(obj)
    if parent:
        obj.parent = parent
        obj.matrix_parent_inverse = parent.matrix_world.inverted()
    mesh.materials.append(MATERIALS[mat])
    PARTS[name] = obj
    if radius:
        bevel(obj, radius)
    return obj


def prism(name: str, outline: list, thickness: float, mat: str, group: str,
          radius: float = 0, y: float = 0, parent=None) -> bpy.types.Object:
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(outline, outline[1:] + outline[:1]))
    outline = outline if area > 0 else list(reversed(outline))
    n = len(outline)
    verts = [(x, y + side * thickness / 2, z) for side in (-1, 1) for x, z in outline]
    faces = [tuple(range(n)), tuple(reversed(range(n, 2 * n)))]
    faces.extend((i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n))
    obj = mesh_object(name, verts, faces, mat, group, radius, parent)
    for p in obj.data.polygons:
        p.use_smooth = p.index >= 2
    return obj


def rounded_polygon(points: list, iterations: int = 2) -> list:
    # Скругление сохраняет прямые участки между характерными углами контура.
    result = points
    for _ in range(iterations):
        fresh = []
        for a, b in zip(result, result[1:] + result[:1]):
            fresh.extend(((a[0] * .82 + b[0] * .18, a[1] * .82 + b[1] * .18),
                          (a[0] * .18 + b[0] * .82, a[1] * .18 + b[1] * .82)))
        result = fresh
    return result


def box(name: str, center: tuple, size: tuple, mat: str, group: str,
        radius: float = 0, parent=None) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(v * MM for v in center))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(v * MM for v in size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    relocate(obj, group, parent)
    obj.data.materials.append(MATERIALS[mat])
    PARTS[name] = obj
    if radius:
        bevel(obj, radius)
    return obj


def cylinder(name: str, center: tuple, radius: float, depth: float, mat: str,
             group: str, axis: str = 'Y', parent=None, edge: float = 0.2) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=radius * MM, depth=depth * MM,
                                       location=tuple(v * MM for v in center))
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = (math.pi / 2, 0, 0) if axis == 'Y' else (0, math.pi / 2, 0) if axis == 'X' else (0, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    relocate(obj, group, parent)
    obj.data.materials.append(MATERIALS[mat])
    PARTS[name] = obj
    if edge:
        bevel(obj, edge, 2)
    return obj


def difference(obj: bpy.types.Object, cutter: bpy.types.Object) -> None:
    cutter_name = cutter.name
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new('Profile recess', 'BOOLEAN')
    enum_set(mod, 'operation', 'DIFFERENCE')
    enum_set(mod, 'solver', 'EXACT')
    mod.object = cutter
    # Вычитание выполняется до фаски: скругляются и края новых отверстий.
    bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    PARTS.pop(cutter_name, None)


def loft(name: str, sections: list, mat: str, group: str, parent=None,
         radius: float = 0) -> bpy.types.Object:
    count = len(sections[0][1])
    vertices = [(x, y, z) for x, profile in sections for y, z in profile]
    faces = [tuple(reversed(range(count))), tuple(range((len(sections) - 1) * count, len(sections) * count))]
    for k in range(len(sections) - 1):
        faces.extend((k * count + i, k * count + (i + 1) % count,
                      (k + 1) * count + (i + 1) % count, (k + 1) * count + i) for i in range(count))
    obj = mesh_object(name, vertices, faces, mat, group, radius, parent)
    for p in obj.data.polygons:
        p.use_smooth = p.index > 1
    return obj


def lathe(name: str, profile: list, mat: str, group: str, z: float = 10,
          parent=None, segments: int = 96) -> bpy.types.Object:
    # Замкнутый профиль даёт наружный кожух и небольшой видимый торцевой recess.
    vertices = [(x, r * math.sin(i * math.tau / segments), z + r * math.cos(i * math.tau / segments))
                for x, r in profile for i in range(segments)]
    faces = []
    for k in range(len(profile)):
        nxt = (k + 1) % len(profile)
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((k * segments + i, k * segments + j, nxt * segments + j, nxt * segments + i))
    obj = mesh_object(name, vertices, faces, mat, group, 0, parent)
    uv = obj.data.uv_layers.new(name='Cylindrical_surface')
    xmin, xmax = min(p[0] for p in profile), max(p[0] for p in profile)
    for face in obj.data.polygons:
        face.use_smooth = True
        k, i = divmod(face.index, segments)
        nxt = (k + 1) % len(profile)
        coords = [((profile[k][0] - xmin) / max(1, xmax - xmin), i / segments),
                  ((profile[k][0] - xmin) / max(1, xmax - xmin), (i + 1) / segments),
                  ((profile[nxt][0] - xmin) / max(1, xmax - xmin), (i + 1) / segments),
                  ((profile[nxt][0] - xmin) / max(1, xmax - xmin), i / segments)]
        for loop_index, coordinate in zip(face.loop_indices, coords):
            uv.data[loop_index].uv = coordinate
    return obj


def rounded_section(width: float, height: float, z: float, corner: float, steps: int = 6) -> list:
    result = []
    for cy, cz, start in ((width / 2 - corner, z + height / 2 - corner, 0),
                          (-width / 2 + corner, z + height / 2 - corner, 90),
                          (-width / 2 + corner, z - height / 2 + corner, 180),
                          (width / 2 - corner, z - height / 2 + corner, 270)):
        for i in range(steps + 1):
            angle = math.radians(start + i * 90 / steps)
            result.append((cy + corner * math.cos(angle), cz + corner * math.sin(angle)))
    return result


def cover_section() -> list:
    result = [(-22, 8), (22, 8), (22, 25)]
    result.extend((22 * math.cos(i * math.pi / 24), 25 + 19 * math.sin(i * math.pi / 24)) for i in range(1, 25))
    return result


def screw(name: str, x: float, y: float, z: float, r: float = 2.3, parent=None) -> None:
    group = '06_Fasteners'
    cylinder(name + '_rim', (x, y, z), r + .5, 1.1, 'Blued steel', group, parent=parent)
    side = -1 if y < 0 else 1
    cylinder(name, (x, y + side * .5, z), r, .65, 'Machined edges', group, parent=parent)
    box(name + '_slot', (x, y + side * .84, z), (r * 1.4, .03, .38), 'Recess black', group, .08, parent)


def build_stock(detail: bool, root: bpy.types.Object) -> None:
    group = '01_Stock'
    parent = empty('Stock', (279, 0, -12), group, root)
    profile = [(15, -20), (198, -20), (224, -17), (247, -6), (268, 9), (279, 10),
               (279, -24), (286, -30), (310, -30), (316, -39), (333, -41), (352, -57),
               (344, -65), (336, -88), (330, -110), (333, -120), (306, -121),
               (295, -110), (283, -106), (252, -105), (15, -114)]
    stock = prism('Wood_stock_with_integral_grip', rounded_polygon(profile, 2), 36,
                  'Varnished walnut amber', group, 2.2, parent=parent)
    holes = [([(48, -37), (161, -37), (178, -45), (162, -88), (150, -97), (60, -97), (52, -87)], 'Rear'),
             ([(214, -38), (285, -38), (308, -48), (310, -58), (296, -91), (281, -99), (206, -98), (196, -88)], 'Forward')]
    for points, label in holes:
        cutter = prism('Cut_stock_' + label, rounded_polygon(points, 3), 80, 'Recess black', group)
        difference(stock, cutter)
    pad = prism('Ventilated_rubber_butt_pad', [(0, -19), (15, -19), (19, -25), (17, -110), (12, -117), (0, -116)],
                40, 'Butt pad rubber', group, 1.2, parent=parent)
    if not detail:
        return
    for column in (-9, 9):
        for row in range(10):
            cutter = cylinder('Cut_pad', (2.6, column, -25 - row * 9), 3.1, 7,
                              'Recess black', group, 'X', edge=0)
            difference(pad, cutter)
    for side in (-1, 1):
        screw('Stock_tang_' + str(side), 306, side * 18.2, -36, 3.2, parent)
        for x, z in ((269, -12), (317, -109), (28, -27)):
            cylinder('Wood_pin_' + str(side) + '_' + str(x), (x, side * 18.1, z), 1.15, .25,
                     'Machined edges', '06_Fasteners', parent=parent, edge=.1)


def build_receiver(detail: bool, root: bpy.types.Object) -> None:
    group = '02_Receiver'
    frame = prism('Receiver_lower_frame', [(282, 16), (482, 16), (482, -33), (415, -54), (405, -54),
                  (405, -19), (347, -19), (347, -47), (335, -48), (324, -26), (282, -25)],
                  39, 'Blued steel', group, .8, parent=root)
    cover_parent = empty('Dust_cover', (285, 0, 12), group, root)
    section = cover_section()
    cover = loft('Rounded_dust_cover', [(284, [(y * .87, z - 3) for y, z in section]),
                  (293, section), (474, section), (479, [(y * .92, z - 2) for y, z in section])],
                  'Blued steel', group, cover_parent, .55)
    guard = prism('Trigger_guard', rounded_polygon([(344, -18), (410, -18), (412, -53),
                  (405, -58), (348, -58), (343, -52)], 1), 12, 'Blued steel', group, .6, parent=root)
    cutter = prism('Cut_trigger_guard', rounded_polygon([(348, -21), (407, -21), (408, -50),
                   (403, -54), (350, -54), (348, -50)], 1), 40, 'Recess black', group)
    difference(guard, cutter)
    trigger_parent = empty('Trigger', (362, 0, -18), group, root)
    prism('Curved_trigger', rounded_polygon([(361, -19), (365, -19), (364, -29), (367, -39),
          (375, -47), (373, -49), (366, -45), (361, -38), (359, -29)], 1), 4.7,
          'Machined edges', group, .55, parent=trigger_parent)
    prism('Magazine_well_side_plate', [(406, 15), (482, 15), (482, -34), (415, -54), (406, -54)],
          41.3, 'Blued steel', group, .65, parent=root)
    if not detail:
        return
    cutter = box('Cut_ejection_recess', (440, -24, 25), (70, 12, 21), 'Recess black', group, 1.3)
    # Радиус окна включается в вычитание, а не остаётся скрытым модификатором cutter.
    bpy.context.view_layer.objects.active = cutter
    for mod in list(cutter.modifiers):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    difference(cover, cutter)
    box('Ejection_recess_dark_back', (440, -18.1, 25), (65, .8, 17), 'Recess black', group, .5, root)
    box('Bolt_visible_strip', (440, -20.1, 29), (64, 1.1, 5), 'Blued steel', group, .5, root)
    handle = empty('Charging_handle', (463, -20, 25), group, root)
    cylinder('Charging_handle_stem', (465, -27, 23), 2.3, 14, 'Blued steel', group, parent=handle)
    box('Charging_handle_tab', (467, -34, 23), (10, 5, 7), 'Blued steel', group, 1.6, handle)
    for x in (326, 365, 401):
        profile = [(y * 1.02, z + .65) for y, z in section[2:]]
        profile += [(y, z) for y, z in reversed(section[2:])]
        loft('Cover_pressed_rib_' + str(x), [(x - .65, profile), (x + .65, profile)],
             'Blued steel', group, cover_parent)
    for side in (-1, 1):
        box('Receiver_lower_seam_' + str(side), (379, side * 19.7, 5.3), (184, .6, 1.2),
            'Machined edges', group, .2, root)
        screw('Receiver_rear_pin_' + str(side), 296, side * 20, -14, 2.0, root)
        screw('Magazine_well_pin_' + str(side), 418, side * 21.1, -44, 1.6, root)
    selector = empty('Selector', (344, -21.3, -8), group, root)
    cylinder('Selector_pivot', (344, -23, -8), 5.1, 3.8, 'Blued steel', group, parent=selector)
    prism('Selector_lever', rounded_polygon([(343, -11), (344, -4), (362, 7), (390, 15),
          (411, 16), (412, 12), (384, 10), (359, 2), (349, -10)], 1), 2.3,
          'Blued steel', group, .5, -23.2, selector)
    screw('Selector_pin', 344, -25, -8, 2.6, selector)
    prism('Selector_lower_return', rounded_polygon([(349, -8), (354, -3), (380, 1),
          (384, 6), (382, 8), (351, 3), (346, -3)], 1), 1.6,
          'Machined edges', group, .4, -23.4, selector)
    box('Left_dovetail_mount', (361, 22, -3), (107, 5, 11), 'Blued steel', group, .7, root)
    box('Left_dovetail_channel', (361, 25, -1), (96, .8, 1.5), 'Recess black', group, .2, root)
    for x in (317, 409):
        screw('Left_mount_' + str(x), x, 25.4, -3, 2.1, root)
    release = empty('Magazine_release', (421, 0, -54), group, root)
    prism('Magazine_release_tab', [(416, -48), (422, -48), (421, -59), (417, -65), (414, -65), (417, -58)],
          5, 'Blued steel', group, .4, parent=release)


def build_front(detail: bool, root: bpy.types.Object) -> None:
    group = '03_Front'
    handguard = empty('Handguard', (480, 0, 15), group, root)
    loft('Tapered_polymer_handguard', [(480, rounded_section(48, 66, 13, 6)),
         (485, rounded_section(50, 66, 13, 7)), (552, rounded_section(43, 48, 19, 6)),
         (560, rounded_section(42, 45, 19, 6))], 'Handguard polymer', group, handguard)
    suppressor = empty('Suppressor', (560, 0, 10), group, root)
    lathe('Suppressor_outer_body', [(558, 18), (561, 20.3), (574, 20.3), (576, 19.4),
          (668, 19.4), (672, 19.0), (866, 19.0), (870, 20), (891, 20), (894, 19.2),
          (894, 5.0), (889, 5.0), (889, 17.3), (558, 17.3)],
          'Blued steel', group, parent=suppressor)
    lathe('Suppressor_front_recess', [(888.5, 5.0), (889, 5.0), (889, .8), (888.5, .8)],
          'Recess black', group, parent=suppressor)
    if not detail:
        return
    lathe('Suppressor_knurled_grip', [(687, 19.05), (688, 19.55), (850, 19.55), (851, 19.05)],
          'Suppressor fine crosshatch', group, parent=suppressor)
    for x in (577, 642, 667, 869, 889):
        r = 20.15 if x in (869, 889) else 19.65
        lathe('Suppressor_seam_' + str(x), [(x - .3, r - .35), (x, r), (x + .5, r), (x + .65, r - .35)],
              'Machined edges', group, parent=suppressor)
    for side in (-1, 1):
        box('Handguard_edge_trim_' + str(side), (482.6, side * 23.1, 12), (1.5, 1.7, 51),
            'Blued steel', group, .45, handguard)
        screw('Handguard_front_pin_' + str(side), 552, side * 21.5, 17, 1.6, handguard)


def build_magazine(detail: bool, root: bpy.types.Object) -> None:
    group = '04_Magazine'
    parent = empty('Magazine_10_round', (455, 0, -37), group, root)
    profile = [(424, -44), (478, -28), (486, -71), (494, -110), (491, -119),
               (441, -127), (436, -117), (430, -78)]
    prism('Short_magazine_body', profile, 28, 'Magazine polymer', group, 1.4, parent=parent)
    prism('Magazine_floor_plate', [(440, -122), (494, -114), (496, -124), (441, -133)],
          31, 'Magazine polymer', group, .85, parent=parent)
    if not detail:
        return
    for side in (-1, 1):
        for row in range(7):
            z = -53 - row * 9.5
            left = 430 + row * 1.55
            right = 480 + row * 1.75
            prism('Magazine_side_rib_' + str(side) + '_' + str(row),
                  [(left, z), (right, z + 8), (right + .25, z + 9.2), (left + .3, z + 1.3)],
                  .95, 'Magazine polymer', group, .28, side * 14.25, parent)
            center = (left + right) / 2
            prism('Magazine_short_groove_' + str(side) + '_' + str(row),
                  [(center - 8, z - 3.0), (center + 8, z - .6),
                   (center + 8, z + .55), (center - 8, z - 1.85)],
                  .05, 'Recess black', group, .1, side * 14.15, parent)
        prism('Magazine_front_spine_' + str(side), [(480, -43), (483, -44),
              (494, -110), (491, -119), (488, -119), (490, -110)],
              .9, 'Magazine polymer', group, .4, side * 14.2, parent)
        prism('Magazine_rear_spine_' + str(side), [(425, -45), (428, -45),
              (441, -122), (438, -122)], .8, 'Magazine polymer', group, .4, side * 14.2, parent)


def build_rail(detail: bool, root: bpy.types.Object) -> None:
    group = '05_Rail_and_sights'
    parent = empty('Top_Picatinny_rail', (383, 0, 44), group, root)
    for x in (310, 453):
        box('Rail_support_' + str(x), (x, 0, 45.2), (19, 13, 7), 'Blued steel', group, .65, parent)
    cross = [(-6, 46), (6, 46), (6, 50), (10.5, 52.5), (10.5, 55),
             (-10.5, 55), (-10.5, 52.5), (-6, 50)]
    loft('Picatinny_continuous_base', [(296, cross), (467, cross)], 'Blued steel', group, parent, .35)
    for index in range(18):
        x = 298.5 + index * 9.6
        box('Picatinny_tooth_' + str(index + 1).zfill(2), (x, 0, 56.3), (4.5, 21, 3.6),
            'Blued steel', group, .25, parent)
    if detail:
        for x in (310, 453):
            cylinder('Rail_mount_screw_' + str(x), (x, 0, 55.7), 2.25, .5,
                     'Machined edges', group, 'Z', parent)
            box('Rail_screw_slot_' + str(x), (x, 0, 56), (2.8, .6, .06), 'Recess black', group, .1, parent)
    rear = empty('Rear_iron_sight', (591, 0, 30), group, PARTS['Suppressor'])
    box('Rear_sight_base', (612, 0, 30.3), (63, 16, 4), 'Blued steel', group, .6, rear)
    prism('Rear_sight_ramp', [(585, 32), (643, 32), (643, 39), (638, 41), (595, 39), (585, 38)],
          10, 'Blued steel', group, .4, parent=rear)
    box('Rear_sight_leaf', (610, 0, 39.5), (46, 8, 1.2), 'Machined edges', group, .3, rear)
    for side in (-1, 1):
        box('Rear_notch_ear_' + str(side), (587.5, side * 3.9, 41), (3, 4.5, 6),
            'Blued steel', group, .5, rear)
    front = empty('Front_iron_sight', (882, 0, 29), group, PARTS['Suppressor'])
    box('Front_sight_foot', (882, 0, 29.5), (18, 18, 3.5), 'Blued steel', group, .9, front)
    profile = [(874, 29), (874, 40), (876, 48), (880, 51), (884, 51), (889, 46), (891, 29)]
    for side in (-1, 1):
        ear = prism('Front_sight_ear_' + str(side), rounded_polygon(profile, 1), 2.3,
                    'Blued steel', group, .45, side * 5.2, front)
        cutter = cylinder('Cut_front_sight', (882, side * 5.2, 44), 2.6, 8,
                          'Recess black', group, edge=0)
        difference(ear, cutter)
    cylinder('Front_sight_post', (882, 0, 39.7), 1.2, 17, 'Machined edges', group, 'Z', front)
    if detail:
        screw('Rear_sight_axis', 590, -8.3, 37, 2.1, rear)
        for i in range(6):
            box('Rear_sight_index_' + str(i), (598 + i * 5.5, -5.08, 38.7),
                (.55, .05, 1.3), 'Sight index', group, .05, rear)


def sling_loop(name: str, center: tuple, width: float, height: float, parent) -> None:
    group = '06_Fasteners'
    curve = bpy.data.curves.new(name + '_curve', 'CURVE')
    enum_set(curve, 'dimensions', '3D')
    curve.resolution_u = 12
    curve.bevel_depth = .85 * MM
    curve.bevel_resolution = 3
    spline = curve.splines.new('POLY')
    count = 48
    spline.points.add(count - 1)
    for i, point in enumerate(spline.points):
        angle = i * math.tau / count
        point.co = ((center[0] + width / 2 * math.cos(angle)) * MM,
                    center[1] * MM, (center[2] + height / 2 * math.sin(angle)) * MM, 1)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    COLLECTIONS[group].objects.link(obj)
    curve.materials.append(MATERIALS['Blued steel'])
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    obj.select_set(False)


def build_small_parts(root) -> None:
    for side in (-1, 1):
        screw('Sling_stock_screw_' + str(side), 30, side * 19.5, -99, 2.4, PARTS['Stock'])
    sling_loop('Stock_sling_swivel', (32, 21.7, -100), 11, 18, PARTS['Stock'])
    sling_loop('Front_sling_swivel', (563, 23, -1), 10, 14, PARTS['Handguard'])
    box('Front_sling_bracket', (561, 21, 8), (7, 6, 8), 'Blued steel', '06_Fasteners', .9, PARTS['Handguard'])
    bpy.ops.object.text_add(location=(438 * MM, -20.76 * MM, -10 * MM))
    text = bpy.context.object
    text.name = 'Receiver_discreet_marking'
    text.data.body = 'ВСС'
    font_path = Path('C:/Windows/Fonts/arial.ttf')
    if font_path.exists():
        text.data.font = bpy.data.fonts.load(str(font_path))
    text.data.size = 3.3 * MM
    text.data.extrude = .006 * MM
    text.data.materials.append(MATERIALS['Sight index'])
    text.rotation_euler = (math.pi / 2, 0, 0)
    relocate(text, '06_Fasteners', root)


def camera(name: str, location: tuple, target: tuple, scale: float) -> bpy.types.Object:
    data = bpy.data.cameras.new(name)
    enum_set(data, 'type', 'ORTHO')
    data.ortho_scale = scale
    data.lens = 60
    data.clip_start = .005
    data.clip_end = 20
    obj = bpy.data.objects.new(name, data)
    COLLECTIONS['90_Studio'].objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def area(name: str, location: tuple, target: tuple, energy: float, size: float,
         color: tuple = (1, 1, 1), narrow: float = 0) -> None:
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.color = color
    data.size = size
    if narrow:
        enum_set(data, 'shape', 'RECTANGLE')
        data.size_y = narrow
    obj = bpy.data.objects.new(name, data)
    COLLECTIONS['90_Studio'].objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def studio() -> None:
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_percentage = 100
    enum_set(scene.render.image_settings, 'file_format', 'PNG')
    enum_set(scene.render.image_settings, 'color_mode', 'RGBA')
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = '8'
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = 64
    scene.world.use_nodes = True
    background = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    background.inputs['Color'].default_value = (.22, .25, .29, 1)
    background.inputs['Strength'].default_value = .45
    area('Large neutral key', (.32, -.45, .72), (.43, 0, -.02), 75, .85)
    area('Soft opposite fill', (.38, .65, .35), (.44, 0, -.02), 45, .9)
    area('Upper rim', (.64, .22, .66), (.48, 0, -.01), 70, .8)
    area('Long reflection strip', (.61, -.19, .36), (.56, 0, .01), 12, .75, narrow=.05)
    camera('Camera_Beauty_Right', (.85, -1.3, .46), (.447, 0, -.032), 1.00)
    camera('Camera_Profile_Right', (.447, -2.0, -.029), (.447, 0, -.029), 1.00)
    camera('Camera_Profile_Left', (.447, 2.0, -.029), (.447, 0, -.029), 1.00)
    camera('Camera_Top', (.447, 0, 2), (.447, 0, 0), 1.00)
    camera('Camera_Receiver_Detail', (.49, -.40, .20), (.399, 0, .003), .32)
    camera('Camera_Stock_Detail', (-.09, -.45, .09), (.163, 0, -.066), .40)
    camera('Camera_Muzzle_Detail', (1.12, -.26, .14), (.841, 0, .021), .205)
    scene.camera = bpy.data.objects['Camera_Beauty_Right']


def report_bounds(group: str) -> dict:
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    vertices = []
    triangles = 0
    for obj in COLLECTIONS[group].all_objects:
        if obj.type not in {'MESH', 'CURVE', 'FONT'}:
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        if mesh is None:
            continue
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        vertices.extend(evaluated.matrix_world @ v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    low = [min(v[i] for v in vertices) for i in range(3)]
    high = [max(v[i] for v in vertices) for i in range(3)]
    return {'min_mm': [v / MM for v in low], 'max_mm': [v / MM for v in high],
            'dimensions_mm': [(high[i] - low[i]) / MM for i in range(3)],
            'evaluated_triangles': triangles, 'mesh_objects': sum(o.type == 'MESH' for o in COLLECTIONS[group].all_objects)}


def save_scene(path: Path) -> None:
    # Шейдеры и шрифт остаются внутри файла, внешние текстуры не нужны.
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def render_views(output: Path, stage: str, names: list) -> None:
    scene = bpy.context.scene
    for suffix, camera_name, width, height in names:
        scene.camera = bpy.data.objects[camera_name]
        scene.render.resolution_x, scene.render.resolution_y = width, height
        scene.render.filepath = str(output / (stage + '_' + suffix + '.png'))
        bpy.ops.render.render(write_still=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ASSET)
    parser.add_argument('--stage', choices=['blockout', 'final'], default='final')
    parser.add_argument('--render', action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for existing in list(bpy.data.collections):
        bpy.data.collections.remove(existing)
    assembly = collection('VSS_Assembly')
    for name in ('01_Stock', '02_Receiver', '03_Front', '04_Magazine', '05_Rail_and_sights', '06_Fasteners'):
        collection(name, assembly)
    collection('90_Studio')
    scene = bpy.context.scene
    enum_set(scene.unit_settings, 'system', 'METRIC')
    scene.unit_settings.scale_length = 1
    enum_set(scene.unit_settings, 'length_unit', 'MILLIMETERS')
    scene.render.fps = 24
    scene.frame_end = 1
    build_materials()
    root = empty('VSS_Vintorez_Picatinny', (0, 0, 0), '02_Receiver')
    root['variant'] = 'Classic wooden VSS, short magazine, custom top Picatinny rail, no optics'
    root['axis_convention'] = '+X muzzle, +Z up, -Y right side; 1 Blender unit = 1 metre'
    root['purpose'] = 'Editable visual asset; exterior reference reconstruction'
    detail = options.stage == 'final'
    build_stock(detail, root)
    bpy.context.view_layer.update()
    build_receiver(detail, root)
    bpy.context.view_layer.update()
    build_front(detail, root)
    bpy.context.view_layer.update()
    build_magazine(detail, root)
    build_rail(detail, root)
    if detail:
        build_small_parts(root)
    bpy.context.view_layer.update()
    studio()
    scene.render.resolution_x, scene.render.resolution_y = 1800, 760
    # При открытии файла предмет целиком виден в удобном ракурсе.
    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    for screen in bpy.data.screens:
        for area_ui in screen.areas:
            if area_ui.type == 'VIEW_3D':
                space = area_ui.spaces.active
                space.region_3d.view_distance = 1.1
                space.region_3d.view_location = Vector((.447, 0, -.03))
                space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
                enum_set(space.region_3d, 'view_perspective', 'ORTHO')
                space.overlay.show_extras = False
                space.shading.color_type = 'MATERIAL'
    bounds = report_bounds('VSS_Assembly')
    (output / (options.stage + '_measurements.json')).write_text(json.dumps(bounds, indent=2), encoding='utf-8')
    file_name = 'VSS_Blockout.blend' if not detail else 'VSS_Vintorez_Picatinny.blend'
    save_scene(output / file_name)
    print('VSS_RESULT ' + json.dumps(bounds))
    if options.render:
        original_camera = scene.camera
        if not detail:
            bpy.context.view_layer.material_override = MATERIALS['Silhouette clay']
        names = [('profile_right', 'Camera_Profile_Right', 1500, 550),
                 ('beauty', 'Camera_Beauty_Right', 1600, 700)]
        render_views(output, options.stage, names)
        bpy.context.view_layer.material_override = None
        scene.camera = original_camera


if __name__ == '__main__':
    main()
