"""Две самостоятельные наружные модели оптики для ВСС.

Blender CLI: --factory-startup --background --python tools/build_vss_optics.py
После --: --output DIR, --blockout. Единицы геометрии — миллиметры.
ПСО реконструируется по предметному фото; Rail 4x32 — собственный игровой дизайн.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B

OUT = B.ROOT / '_asset_src' / 'vss_optics'
DETAIL = True
SEGMENTS = 64
CURRENT = ''
AXIS_Y = 0.0
AXIS_Z = 0.0
ROOT: bpy.types.Object | None = None


def active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def name(label: str) -> str:
    return CURRENT + '_' + label


def box(label: str, center: tuple, size: tuple, mat: str = 'Coated aluminium',
        edge: float = .3) -> bpy.types.Object:
    obj = B.box(name(label), center, size, mat, CURRENT, edge, ROOT)
    if obj.modifiers:
        obj.modifiers[0].segments = 2
    return obj


def cylinder(label: str, center: tuple, radius: float, depth: float,
             mat: str = 'Coated aluminium', axis: str = 'Z', edge: float = .15) -> bpy.types.Object:
    obj = B.cylinder(name(label), center, radius, depth, mat, CURRENT, axis, ROOT, edge)
    return obj


def lathe(label: str, profile: list, mat: str = 'Coated aluminium',
          y: float | None = None, z: float | None = None) -> bpy.types.Object:
    # Каждый контур замкнут: отдельные наружная и внутренняя стенки имеют толщину.
    obj = B.lathe(name(label), profile, mat, CURRENT,
                  AXIS_Z if z is None else z, ROOT, SEGMENTS)
    obj.location.y += (AXIS_Y if y is None else y) * B.MM
    for poly in obj.data.polygons:
        if abs(poly.normal.x) > .995:
            poly.use_smooth = False
    return obj


def prism(label: str, outline: list, thickness: float, y: float,
          mat: str = 'Coated aluminium', edge: float = .4) -> bpy.types.Object:
    return B.prism(name(label), outline, thickness, mat, CURRENT, edge, y, ROOT)


def lens(label: str, x: float, radius: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=12,
        radius=1, location=(x * B.MM, AXIS_Y * B.MM, AXIS_Z * B.MM))
    obj = bpy.context.object
    obj.name = name(label)
    obj.scale = (.00075, radius * B.MM, radius * B.MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    B.relocate(obj, CURRENT, ROOT)
    obj.data.materials.append(B.MATERIALS['Coated optical glass'])
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj['asset_role'] = 'lens'
    return obj


def knob(label: str, center: tuple, radius: float, height: float, axis: str = 'Z',
         mat: str = 'Machined rim') -> None:
    obj = cylinder(label, center, radius, height, mat, axis, 0)
    # Рёбра насечки — одна замкнутая сетка, а не сотни отдельных деталей.
    for vertex in obj.data.vertices:
        radial = math.hypot(vertex.co.x, vertex.co.y)
        if radial > radius * B.MM * .9:
            angle = math.atan2(vertex.co.y, vertex.co.x)
            index = round(angle * 48 / math.tau)
            factor = 1 if index % 2 else .96
            vertex.co.x *= factor
            vertex.co.y *= factor
    if DETAIL and axis == 'Z':
        for index in range(12):
            angle = index * math.tau / 12
            tick = box(label + '_tick_' + str(index),
                (center[0] + (radius - 2) * math.cos(angle),
                 center[1] + (radius - 2) * math.sin(angle), center[2] + height / 2 + .02),
                (1.3 if index % 3 else 2.1, .22, .04), 'Engraving', 0)
            tick.rotation_euler.z = angle
    cylinder(label + '_cover', center, radius * .69, height + .08, 'Coated aluminium', axis, .05)


def screw(label: str, center: tuple, axis: str = 'Y', radius: float = 2.1) -> None:
    cylinder(label, center, radius, .7, 'Machined rim', axis, .08)
    if DETAIL:
        sizes = {'X': (.04, radius * 1.4, .38), 'Y': (radius * 1.4, .04, .38),
                 'Z': (radius * 1.4, .38, .04)}
        position = list(center)
        position['XYZ'.index(axis)] += .37
        box(label + '_slot', tuple(position), sizes[axis], 'Inner black', 0)


def text_label(label: str, text: str, position: tuple, size: float,
               rotation: tuple) -> None:
    if not DETAIL:
        return
    data = bpy.data.curves.new(name(label), 'FONT')
    data.body = text
    data.size = size * B.MM
    data.extrude = .018 * B.MM
    data.resolution_u = 2
    obj = bpy.data.objects.new(name(label), data)
    B.COLLECTIONS[CURRENT].objects.link(obj)
    obj.location = tuple(v * B.MM for v in position)
    obj.rotation_euler = rotation
    data.materials.append(B.MATERIALS['Engraving'])
    active(obj)
    bpy.ops.object.convert(target='MESH')
    # FONT-конвертация разделяет вершины крышек и стенок; замыкаем только совпадения.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-9)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    B.relocate(obj, CURRENT, ROOT)
    obj['asset_role'] = 'marking'


def marker(label: str, position: tuple) -> bpy.types.Object:
    obj = B.empty(label, position, CURRENT, ROOT)
    obj.empty_display_size = .005
    return obj


def begin(identifier: str, y: float, z: float) -> None:
    global CURRENT, AXIS_Y, AXIS_Z, ROOT
    CURRENT, AXIS_Y, AXIS_Z = identifier, y, z
    B.collection(identifier)
    ROOT = B.empty(identifier, (0, 0, 0), identifier)
    ROOT['asset_type'] = 'detachable_optic'
    ROOT['source_axes'] = '+X objective, +Z up; origin = mount contact'


def pso() -> None:
    begin('PSO_VSS_4x24', -15.5, 90)
    ROOT['variant'] = 'PSO-1M2-1 exterior, extended rubber eyecup'
    ROOT['mount'] = 'left_dovetail'
    ROOT['on_vss_mm'] = [361, 24.5, -3]
    lathe('Main_tube', [(-112, 15), (-105, 15), (-103, 13.8), (-40, 13.8),
        (-33, 19), (25, 19), (30, 13.8), (127, 13.8), (132, 16),
        (142, 16), (142, 12.15), (-112, 12.15)])
    lathe('Ocular', [(-153, 17), (-145, 17), (-145, 18.2), (-120, 18.2),
        (-117, 15.5), (-102, 15.5), (-102, 13), (-153, 13)])
    lathe('Ocular_focus_ring', [(-150, 17.4), (-148, 18.4), (-144, 18.4),
        (-142, 17.4), (-142, 16.8), (-150, 16.8)], 'Machined rim')
    lathe('Rubber_eyecup', [(-190, 23), (-189, 24), (-185, 24), (-183, 21),
        (-177, 17), (-174, 16), (-173, 20), (-170, 20), (-168, 16),
        (-165, 16), (-164, 19), (-161, 19), (-159, 16), (-151, 16),
        (-149, 17), (-145, 17), (-145, 14), (-162, 14), (-175, 14.5),
        (-186, 20), (-190, 21)], 'Rubber')
    lathe('Sliding_sunshade', [(131, 16.1), (132, 17.2), (181, 17.2), (185, 16.7),
        (185, 14.6), (133, 14.6), (133, 15.1), (131, 15.1)])
    lathe('Objective_retain_ring', [(136, 12.8), (137, 12.8), (137, 11.8), (136, 11.8)], 'Inner black')
    lens('Objective_lens', 135, 11.8)
    lens('Ocular_lens', -135, 12.7)
    cylinder('Elevation_boss', (-18, AXIS_Y, 109), 12.5, 10)
    knob('Elevation_dial', (-18, AXIS_Y, 119), 10.5, 8)
    cylinder('Windage_boss', (-17, AXIS_Y - 19, 90), 12, 10, axis='Y')
    knob('Windage_dial', (-17, AXIS_Y - 26, 90), 10.5, 8, 'Y')
    lathe('Battery_housing', [(-64, 9), (-15, 9), (-12, 8.5),
        (-12, 7.1), (-64, 7.1)], y=12, z=64)
    lathe('Battery_cap', [(-78, 9.8), (-65, 9.8), (-65, 8.1), (-78, 8.1)], y=12, z=64)
    box('Battery_attachment_bridge', (-21, 3, 70), (29, 15, 14))
    # Окно литого бокового кронштейна отделяет две несущие ветви.
    web = prism('Cast_side_bracket', [(-62, -10), (60, -10), (60, 20), (37, 25),
        (20, 72), (-10, 76), (-27, 59), (-41, 29), (-62, 23)], 7, 5)
    cutter = B.prism(name('Cut_bracket_window'), [(-30, 11), (25, 11),
        (14, 50), (-10, 54), (-22, 36)], 28, 'Inner black', CURRENT, 0, 5)
    B.difference(web, cutter)
    box('Dovetail_clamp', (0, 7, -3), (110, 14, 14), edge=.6)
    box('Upper_clamp_lip', (0, -1, 5.5), (104, 4, 3.2), edge=.3)
    box('Lower_clamp_lip', (0, -1, -9), (104, 4, 3.2), edge=.3)
    cylinder('Clamp_axle', (-43, 18, -1), 5, 9, axis='Y')
    lever = prism('Clamp_lever', [(-47, -3), (-42, -7), (-5, -6),
        (16, -3), (14, 1), (-10, -1), (-42, 2)], 3, 23, edge=.8)
    cylinder('Clamp_handle_end', (14, 23, -1), 4, 3.6, axis='Y')
    for x, z in [(-50, 14), (48, 14), (-18, 62)]:
        screw('Mount_screw_' + str(x), (x, 9, z))
    box('Illumination_switch_base', (-30, 10, 40), (17, 8, 24))
    cylinder('Illumination_switch', (-31, 15, 44), 3.8, 3.2, axis='Y')
    switch = box('Illumination_toggle', (-28, 17, 44), (11, 2, 2.8), 'Inner black', .4)
    switch.rotation_euler.y = math.radians(-25)
    text_label('Body_mark', 'PSO 4x24', (5, -34.55, 89), 2.4, (math.pi / 2, 0, 0))
    text_label('Bracket_serial', 'VSS / 01', (-48, 1.45, 20), 3.0, (math.pi / 2, 0, 0))
    marker('MountOrigin', (0, 0, 0))
    marker('OpticalAxis', (0, AXIS_Y, AXIS_Z))
    marker('Ocular', (-135, AXIS_Y, AXIS_Z))
    marker('EyePoint', (-203, AXIS_Y, AXIS_Z))
    marker('Objective', (135, AXIS_Y, AXIS_Z))


def rail_scope() -> None:
    begin('Rail_4x32', 0, 32)
    ROOT['variant'] = 'Original compact fixed 4x32 game optic, no brand replica'
    ROOT['mount'] = 'picatinny_top'
    ROOT['on_vss_mm'] = [383, 0, 58.1]
    lathe('Main_tube', [(-67, 15), (-63, 16), (-24, 16), (-20, 18),
        (20, 18), (24, 16), (52, 16), (70, 21.5), (85, 21.5),
        (89, 21), (89, 17), (61, 12.8), (-67, 12.8)])
    lathe('Ocular', [(-91, 19.5), (-90, 20.5), (-71, 20.5), (-69, 19),
        (-63, 19), (-63, 16.1), (-70, 16.1), (-91, 16.1)])
    lathe('Rubber_focus_grip', [(-86, 20.8), (-70, 20.8), (-70, 20), (-86, 20)], 'Rubber')
    if DETAIL:
        for index in range(24):
            angle = index * math.tau / 24
            rib = box('Focus_rib_' + str(index), (-78, 20.9 * math.sin(angle),
                32 + 20.9 * math.cos(angle)), (13, 1.1, .9), 'Rubber', .15)
            rib.rotation_euler.x = -angle
    lathe('Objective_guard_ring', [(83, 22.1), (88, 22.1), (88, 21), (83, 21)], 'Machined rim')
    lathe('Objective_inner_ring', [(82, 16.7), (83, 16.7), (83, 15.8), (82, 15.8)], 'Inner black')
    lens('Objective_lens', 80, 15.8)
    lens('Ocular_lens', -88, 15.8)
    cylinder('Elevation_boss', (0, 0, 51), 10, 8)
    knob('Elevation_cap', (0, 0, 58), 10.2, 8, mat='Coated aluminium')
    cylinder('Windage_boss', (0, -19, 32), 9.5, 8, axis='Y')
    knob('Windage_cap', (0, -26, 32), 9.5, 8, 'Y', 'Coated aluminium')
    cylinder('Brightness_boss', (0, 20, 32), 9, 7, axis='Y')
    knob('Brightness_dial', (0, 27, 32), 9, 8, 'Y', 'Coated aluminium')
    for x in (-43, 40):
        lathe('Mount_ring_' + str(x), [(x - 6, 18), (x + 6, 18),
            (x + 6, 16.05), (x - 6, 16.05)])
        box('Ring_pedestal_' + str(x), (x, 0, 14), (13, 19, 14), edge=.7)
        for side in (-1, 1):
            box('Ring_ear_' + str(x) + '_' + str(side), (x, side * 19, 32), (12, 7, 6))
            screw('Ring_bolt_' + str(x) + '_' + str(side), (x, side * 19, 35.1), 'Z', 1.9)
    box('Mount_bridge', (0, 0, 5), (106, 23, 10), edge=.5)
    # Профиль губок оставляет паз под фактическую верхнюю планку модели ВСС.
    jaw = [(-14, -7.5), (-8.2, -7.5), (-8.2, -5.7), (-10.7, -3.7),
           (-10.7, .2), (-10.7, 5.5), (-14, 5.5)]
    B.loft(name('Fixed_rail_jaw'), [(-53, jaw), (53, jaw)],
           'Coated aluminium', CURRENT, ROOT, .25)
    other = [(-y, z) for y, z in reversed(jaw)]
    B.loft(name('Moving_rail_jaw'), [(-53, other), (53, other)],
           'Coated aluminium', CURRENT, ROOT, .25)
    box('Recoil_key', (-2.9, 0, -2), (4, 17, 4), 'Machined rim', .15)
    for x in (-35, 35):
        cylinder('Clamp_bolt_' + str(x), (x, -16, 2), 4, 5, axis='Y')
        screw('Clamp_bolt_face_' + str(x), (x, -18.9, 2), 'Y', 3.0)
    text_label('Body_mark', '4x32', (-61, -16.12, 31), 2.4, (math.pi / 2, 0, 0))
    marker('MountOrigin', (0, 0, 0))
    marker('OpticalAxis', (0, 0, 32))
    marker('Ocular', (-88, 0, 32))
    marker('EyePoint', (-158, 0, 32))
    marker('Objective', (80, 0, 32))


def materials() -> None:
    for label, color, metal, roughness in [
        ('Coated aluminium', (.012, .015, .019), .22, .39),
        ('Machined rim', (.16, .19, .21), .9, .3),
        ('Rubber', (.006, .007, .009), 0, .72),
        ('Inner black', (.0015, .002, .003), 0, .8),
        ('Engraving', (.62, .59, .51), .1, .5),
        ('Coated optical glass', (.017, .09, .11), .16, .09),
        ('Diagnostic clay', (.29, .32, .35), 0, .58),
    ]:
        mat = B.material(label, color, metal, roughness)
        if label in {'Coated aluminium', 'Rubber'}:
            B.micro_surface(mat, 2400 if metal else 1800, .10, .000008)
        if label == 'Coated optical glass':
            bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
            bsdf.inputs['Transmission Weight'].default_value = .78
            bsdf.inputs['IOR'].default_value = 1.46
            bsdf.inputs['Coat Weight'].default_value = .35


def studio() -> None:
    B.collection('90_Studio')
    scene = bpy.context.scene
    B.enum_set(scene.unit_settings, 'system', 'METRIC')
    scene.unit_settings.scale_length = 1
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    B.enum_set(scene.render.image_settings, 'file_format', 'PNG')
    B.enum_set(scene.render.image_settings, 'color_mode', 'RGBA')
    B.enum_set(scene.view_settings, 'view_transform', 'AgX')
    scene.world.use_nodes = True
    background = next(n for n in scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    background.inputs['Color'].default_value = (.20, .23, .27, 1)
    background.inputs['Strength'].default_value = .4
    B.area('Optics_key', (.05, -.4, .58), (0, 0, .06), 24, .55)
    B.area('Optics_fill', (-.13, .4, .3), (0, 0, .05), 10, .5)
    B.area('Optics_rim', (.25, .15, .4), (0, 0, .07), 18, .45)
    B.area('Optics_strip', (.15, -.3, .1), (0, 0, .07), 2, .4, narrow=.025)
    B.camera('Camera_Beauty', (.35, -.60, .30), (0, 0, .065), .48)
    B.camera('Camera_Left', (0, .8, .066), (0, 0, .066), .43)
    B.camera('Camera_Right', (0, -.8, .066), (0, 0, .066), .43)
    B.camera('Camera_Front', (.6, -.02, .09), (.03, -.012, .057), .19)
    B.camera('Camera_Rear', (-.6, -.04, .10), (-.03, -.012, .057), .19)
    B.camera('Camera_Bottom', (.15, -.32, -.32), (0, 0, .02), .37)
    B.camera('Camera_Gallery', (.28, -.68, .51), (0, 0, .059), .55)
    scene.camera = bpy.data.objects['Camera_Beauty']
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            B.enum_set(space.shading, 'type', 'MATERIAL')
            space.overlay.show_overlays = False
            space.region_3d.view_location = (0, 0, .065)
            space.region_3d.view_distance = .55
            space.region_3d.view_rotation = bpy.data.objects['Camera_Beauty'].rotation_euler.to_quaternion()


def set_visible(identifier: str, value: bool) -> None:
    for obj in list(B.COLLECTIONS[identifier].objects):
        obj.hide_render = not value
        obj.hide_set(not value)


def save_individual(identifier: str, output: Path) -> None:
    other = 'Rail_4x32' if identifier == 'PSO_VSS_4x24' else 'PSO_VSS_4x24'
    set_visible(identifier, True)
    set_visible(other, False)
    # Второй вариант убирается только из отдельной сцены, исходные данные остаются.
    collection = B.COLLECTIONS[other]
    bpy.context.scene.collection.children.unlink(collection)
    for camera in ['Camera_Beauty', 'Camera_Left', 'Camera_Right', 'Camera_Bottom']:
        bpy.data.objects[camera].data.ortho_scale = (.48 if camera == 'Camera_Beauty' else .43) if identifier == 'PSO_VSS_4x24' else .255
    for camera in ['Camera_Front', 'Camera_Rear']:
        bpy.data.objects[camera].data.ortho_scale = .19 if identifier == 'PSO_VSS_4x24' else .125
    if identifier == 'Rail_4x32':
        for camera in ['Camera_Beauty', 'Camera_Left', 'Camera_Right', 'Camera_Front', 'Camera_Rear']:
            bpy.data.objects[camera].location.z -= .033
    bpy.context.scene.camera = bpy.data.objects['Camera_Beauty']
    B.save_scene(output / (identifier + '.blend'))
    bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.update()
    set_visible(other, True)


def main() -> None:
    global DETAIL, SEGMENTS, OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--blockout', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    DETAIL, SEGMENTS = not args.blockout, 48 if args.blockout else 64
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)
    materials()
    pso()
    rail_scope()
    studio()
    reports = {identifier: B.report_bounds(identifier) for identifier in ('PSO_VSS_4x24', 'Rail_4x32')}
    (OUT / ('blockout_measurements.json' if args.blockout else 'measurements.json')).write_text(
        json.dumps(reports, indent=2), encoding='utf-8')
    if args.blockout:
        bpy.context.view_layer.material_override = B.MATERIALS['Diagnostic clay']
        for identifier in reports:
            for other in reports:
                set_visible(other, other == identifier)
            B.render_views(OUT, 'blockout_' + identifier,
                [('profile', 'Camera_Left', 1400, 720), ('front', 'Camera_Front', 850, 850)])
        return
    for identifier in reports:
        save_individual(identifier, OUT)
    for identifier in reports:
        set_visible(identifier, True)
    # В общей сцене это независимые сборки с собственными точками крепления.
    bpy.data.objects['PSO_VSS_4x24'].location.y = .09
    bpy.data.objects['Rail_4x32'].location.y = -.12
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_rotation = bpy.data.objects['Camera_Gallery'].rotation_euler.to_quaternion()
    bpy.context.scene.camera = bpy.data.objects['Camera_Gallery']
    B.save_scene(OUT / 'VSS_Optics.blend')
    print('OPTICS_BUILT ' + json.dumps(reports), flush=True)


if __name__ == '__main__':
    main()
