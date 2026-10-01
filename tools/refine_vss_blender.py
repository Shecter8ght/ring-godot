"""Локальная доработка сохранённой ВСС; удачные части исходника сохраняются.

Blender --factory-startup --background SOURCE.blend --python tools/refine_vss_blender.py
После --: --output FILE.blend [--clay].
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Vector

SPEC = importlib.util.spec_from_file_location('vss_builder', Path(__file__).with_name('build_vss_blender.py'))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
BUILD.COLLECTIONS.update({c.name: c for c in bpy.data.collections})
BUILD.MATERIALS.update({m.name: m for m in bpy.data.materials})
BUILD.PARTS.update({o.name: o for o in bpy.data.objects})
MM = .001


def remove(name: str) -> None:
    obj = bpy.data.objects.get(name)
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)
    BUILD.PARTS.pop(name, None)


def curve_plate(name: str, loops: list, thickness: float, radius: float,
                material: str, group: str, parent) -> bpy.types.Object:
    data = bpy.data.curves.new(name + '_profile', 'CURVE')
    BUILD.enum_set(data, 'dimensions', '2D')
    BUILD.enum_set(data, 'fill_mode', 'BOTH')
    data.extrude = (thickness / 2 - radius) * MM
    data.bevel_depth = radius * MM
    data.bevel_resolution = 5
    data.resolution_u = 8
    for index, points in enumerate(loops):
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))
        reverse = (area < 0) if index == 0 else (area > 0)
        points = list(reversed(points)) if reverse else points
        spline = data.splines.new('POLY')
        spline.points.add(len(points) - 1)
        for point, (x, z) in zip(spline.points, points):
            point.co = (x * MM, z * MM, 0, 1)
        spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, data)
    BUILD.COLLECTIONS[group].objects.link(obj)
    data.materials.append(BUILD.MATERIALS[material])
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    # Профиль лежал в XY; толщина теперь вдоль Y сборки, высота вдоль Z.
    for vertex in obj.data.vertices:
        x, z, y = vertex.co
        vertex.co = (x, -y, z)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0000001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for polygon in obj.data.polygons:
        polygon.use_smooth = abs(polygon.normal.y) < .995
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.select_set(False)
    BUILD.PARTS[name] = obj
    return obj


def stock() -> None:
    remove('Wood_stock_with_integral_grip')
    outer = [(16, -20), (197, -20), (225, -18), (245, -9), (265, 7), (278, 8),
             (278, -25), (286, -30), (311, -30), (319, -40), (335, -42), (350, -56),
             (343, -64), (335, -90), (329, -113), (331, -121), (303, -121),
             (293, -111), (279, -106), (247, -107), (16, -114)]
    rear = [(50, -39), (163, -39), (177, -49), (163, -89), (149, -99), (61, -99), (53, -87)]
    forward = [(215, -40), (287, -40), (304, -49), (307, -58), (295, -93),
               (281, -101), (207, -100), (198, -88)]
    loops = [BUILD.rounded_polygon(outer, 2), BUILD.rounded_polygon(rear, 3),
             BUILD.rounded_polygon(forward, 3)]
    curve_plate('Wood_stock_with_integral_grip', loops, 36, 3.0,
                'Varnished walnut amber', '01_Stock', bpy.data.objects['Stock'])


def thin_details() -> None:
    # В первой версии convert антабки применил модификаторы и к выделенной маркировке.
    remove('Sling_stock_screw_1_slot')
    BUILD.box('Sling_stock_screw_1_slot', (30, 20.34, -99), (3.36, .03, .38),
              'Recess black', '06_Fasteners', 0, bpy.data.objects['Stock'])
    # У плоских маркировок фаска была шире толщины и схлопывала поверхности.
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH':
            continue
        is_thin = ('_slot' in obj.name or 'Magazine_short_groove_' in obj.name
                   or 'Rear_sight_index_' in obj.name)
        if is_thin:
            for mod in list(obj.modifiers):
                if mod.type in {'BEVEL', 'WEIGHTED_NORMAL'}:
                    obj.modifiers.remove(mod)
    for name in ('Rounded_dust_cover', 'Ejection_recess_dark_back',
                 'Magazine_rear_spine_-1', 'Magazine_rear_spine_1'):
        obj = bpy.data.objects.get(name)
        if obj:
            for mod in list(obj.modifiers):
                if mod.type == 'BEVEL':
                    obj.modifiers.remove(mod)


def butt_pad() -> None:
    remove('Ventilated_rubber_butt_pad')
    # Боковые углубления остаются слепыми; центральная резиновая перемычка целая.
    outline = [(1.0, -19), (15, -19), (18, -25), (16, -110), (12, -116), (1.0, -115)]
    pad = curve_plate('Ventilated_rubber_butt_pad', [outline], 40, 1.0,
                      'Butt pad rubber', '01_Stock', bpy.data.objects['Stock'])
    for side in (-1, 1):
        for row in range(10):
            for column in (4.5, 10.2):
                cutter = BUILD.cylinder('Cut_pad_recess', (column, side * 19, -27 - row * 8.6),
                                         1.9, 8, 'Recess black', '01_Stock', edge=0)
                BUILD.difference(pad, cutter)
    for polygon in pad.data.polygons:
        polygon.use_smooth = abs(polygon.normal.y) < .97


def magazine_and_contact_edges() -> None:
    # Короткий магазин ниже горловины приводится к пропорциям фото №2.
    for obj in BUILD.COLLECTIONS['04_Magazine'].objects:
        if obj.type != 'MESH':
            continue
        matrix = obj.matrix_world.copy()
        inverse = matrix.inverted()
        for vertex in obj.data.vertices:
            world = matrix @ vertex.co
            if world.z < -.034:
                world.z = -.034 + .81 * (world.z + .034)
            vertex.co = inverse @ world
        obj.data.update()
    handguard = bpy.data.objects['Tapered_polymer_handguard']
    BUILD.bevel(handguard, .45, 3)
    # Плоская торцевая шайба не должна наследовать нормаль округлого кожуха.
    for obj in BUILD.COLLECTIONS['03_Front'].objects:
        if obj.type == 'MESH' and obj.name.startswith('Suppressor_'):
            for polygon in obj.data.polygons:
                if abs(polygon.normal.x) > .995:
                    polygon.use_smooth = False


def finish_materials() -> None:
    settings = {
        'Blued steel': ((.009, .013, .018), .84, .32, .5),
        'Machined edges': ((.025, .030, .035), .9, .32, .5),
        'Recess black': ((.002, .003, .004), .2, .58, .3),
        'Handguard polymer': ((.007, .008, .009), .0, .45, .32),
        'Magazine polymer': ((.008, .007, .006), .0, .43, .32),
        'Butt pad rubber': ((.004, .005, .006), .0, .78, .25),
        'Suppressor fine crosshatch': ((.007, .011, .016), .78, .44, .5),
    }
    for name, (color, metal, roughness, specular) in settings.items():
        mat = BUILD.MATERIALS[name]
        bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        mat.diffuse_color = (*color, 1)
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Metallic'].default_value = metal
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Specular IOR Level'].default_value = specular
    wood = BUILD.MATERIALS['Varnished walnut amber']
    bsdf = next(n for n in wood.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    wood.diffuse_color = (.19, .06, .015, 1)
    bsdf.inputs['Coat Weight'].default_value = .42
    bsdf.inputs['Coat Roughness'].default_value = .23
    bsdf.inputs['Roughness'].default_value = .31
    ramp = next(n for n in wood.node_tree.nodes if n.type == 'VALTORGB')
    colors = [(.035, .008, .0015, 1), (.105, .028, .0045, 1),
              (.20, .065, .010, 1), (.32, .13, .028, 1)]
    for element, color in zip(ramp.color_ramp.elements, colors):
        element.color = color
    # Свет оставляет широкие блики для контроля формы, без пересвета чёрных покрытий.
    for name, energy in [('Large neutral key', 32), ('Soft opposite fill', 12),
                         ('Upper rim', 24), ('Long reflection strip', 4)]:
        bpy.data.objects[name].data.energy = energy


def inspection_cameras() -> None:
    BUILD.camera('Camera_Bottom', (.447, -.50, -.70), (.447, 0, -.04), 1.00)
    BUILD.camera('Camera_Stock_Back', (-.25, -.27, -.02), (.04, 0, -.068), .24)
    BUILD.camera('Camera_Rail_Detail', (.47, -.18, .28), (.383, 0, .050), .235)
    BUILD.camera('Camera_Beauty_Left', (.14, 1.25, .40), (.447, 0, -.033), 1.00)


def geometric_marking() -> None:
    remove('Receiver_discreet_marking')
    # Небольшая маркировка построена собственными контурами, без внешнего шрифта.
    letter_b = [[(0,0),(0,2.8),(1.4,2.8),(2.05,2.5),(2.05,1.7),
                 (1.65,1.4),(2.15,1.05),(2.15,.35),(1.55,0)],
                [(.4,.35),(1.45,.35),(1.7,.6),(1.7,1.0),(1.35,1.2),(.4,1.2)],
                [(.4,1.65),(1.3,1.65),(1.65,1.9),(1.65,2.25),(1.35,2.45),(.4,2.45)]]
    letter_c = [[(2.05,2.4),(1.7,2.8),(.55,2.8),(.1,2.4),(.1,.4),(.55,0),
                 (1.7,0),(2.05,.4),(2.05,.8),(1.55,.35),(.75,.35),(.5,.65),
                 (.5,2.15),(.75,2.45),(1.55,2.45),(2.05,2.0)]]
    for index, loops in enumerate((letter_b, letter_c, letter_c)):
        outlines = [[(438 + index * 2.8 + x, -10 + z) for x, z in loop] for loop in loops]
        obj = curve_plate('Receiver_stamp_' + str(index), outlines, .02, 0,
                          'Sight index', '06_Fasteners', bpy.data.objects['VSS_Vintorez_Picatinny'])
        obj.location.y = -.02072
    for font in list(bpy.data.fonts):
        if font.users == 0 and font.name != 'Bfont':
            bpy.data.fonts.remove(font)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--clay', action='store_true')
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    stock()
    thin_details()
    butt_pad()
    magazine_and_contact_edges()
    finish_materials()
    inspection_cameras()
    geometric_marking()
    bpy.context.view_layer.update()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    BUILD.save_scene(output)
    measurements = BUILD.report_bounds('VSS_Assembly')
    output.with_suffix('.measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
    print('REFINED_VSS ' + json.dumps(measurements), flush=True)
    if args.clay:
        if 'Silhouette clay' not in BUILD.MATERIALS:
            BUILD.material('Silhouette clay', (.28, .30, .32), 0, .58)
        bpy.context.view_layer.material_override = BUILD.MATERIALS['Silhouette clay']
        BUILD.render_views(output.parent, 'v2_clay', [('profile', 'Camera_Profile_Right', 1500, 560),
                           ('stock', 'Camera_Stock_Detail', 1100, 800)])
    if args.preview:
        BUILD.render_views(output.parent, 'v2', [('beauty', 'Camera_Beauty_Right', 1700, 760),
                           ('profile', 'Camera_Profile_Right', 1700, 620),
                           ('stock', 'Camera_Stock_Detail', 1100, 800)])


if __name__ == '__main__':
    main()
