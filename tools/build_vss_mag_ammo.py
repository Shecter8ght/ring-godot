"""Отдельные художественные магазин ВСС и патрон: исходник -> редактируемые сборки.

Blender --factory-startup --background --python tools/build_vss_mag_ammo.py -- --output DIR.
Оболочка берётся из сохранённой ВСС, внутренний вид — визуальное приближение.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v2.blend'
PIVOT = Vector((.455, 0, -.037))
IDENTIFIERS = ('Magazine_939_10_Empty', 'Magazine_939_10_Loaded', 'Cartridge_939_SP5')


def lathe(name: str, outline: list, material: str, group: str,
          parent: bpy.types.Object, segments: int = 48) -> bpy.types.Object:
    # Нулевая окружность представлена одной вершиной, а не набором совпадающих точек.
    vertices, rings, faces = [], [], []
    for x, radius in outline:
        if radius == 0:
            rings.append([len(vertices)])
            vertices.append((x, 0, 0))
        else:
            ring = []
            for i in range(segments):
                angle = math.tau * i / segments
                ring.append(len(vertices))
                vertices.append((x, radius * math.cos(angle), radius * math.sin(angle)))
            rings.append(ring)
    for a, b in zip(rings, rings[1:] + rings[:1]):
        if len(a) == len(b) == 1:
            continue
        for i in range(segments):
            j = (i + 1) % segments
            if len(a) == 1:
                faces.append((a[0], b[j], b[i]))
            elif len(b) == 1:
                faces.append((a[i], a[j], b[0]))
            else:
                faces.append((a[i], a[j], b[j], b[i]))
    obj = B.mesh_object(name, vertices, faces, material, group, parent=parent)
    for poly in obj.data.polygons:
        # Торцевые плоскости имеют отдельные плоские нормали.
        points = [obj.data.vertices[i].co.x for i in poly.vertices]
        poly.use_smooth = max(points) - min(points) > 1e-7
    return obj


def marker(name: str, position: tuple, group: str, root: bpy.types.Object) -> None:
    obj = B.empty(name, position, group, root)
    obj.empty_display_size = .003


def materials() -> None:
    B.MATERIALS.update({m.name: m for m in bpy.data.materials})
    B.material('Follower dark steel', (.052, .060, .067), .72, .4)
    case = B.material('SP5 lacquered olive case', (.205, .178, .052), .78, .32)
    B.micro_surface(case, 4400, .09, .000006)
    bullet = B.material('SP5 copper jacket', (.42, .205, .064), .94, .26)
    B.micro_surface(bullet, 5000, .055, .000004)
    B.material('Primer brass', (.36, .26, .08), .88, .33)
    B.material('Primer and neck red lacquer', (.22, .008, .004), .05, .32)
    B.material('Clay check', (.38, .40, .42), 0, .58)


def cartridge(group: str) -> bpy.types.Object:
    root = B.empty('Cartridge_939_SP5', (0, 0, 0), group)
    root['asset_type'] = 'reusable_cartridge_prop'
    root['caliber'] = '9x39'
    root['variant'] = 'SP5 exterior visual approximation'
    root['axes_source'] = '+X bullet, +Z up, -Y right; origin = base center'
    root['length_design_mm'] = 56.0
    root['game_item_id'] = 'ammo_939_sp5'
    case = lathe('Case_exterior', [(0.25, 0), (.25, 2.54), (0, 2.75),
        (0, 5.38), (.22, 5.675), (.85, 5.675), (1.16, 5.4), (1.5, 4.82),
        (2.45, 4.82), (3.10, 5.50), (29, 5.12), (33.2, 5.06),
        (35.5, 4.96), (38.8, 4.96), (39, 4.83), (39, 0)],
        'SP5 lacquered olive case', group, root)
    case['asset_role'] = 'case_exterior'
    lathe('Copper_projectile', [(38.85, 0), (38.85, 4.63), (40.9, 4.63),
        (44, 4.28), (47, 3.70), (50, 2.84), (52.5, 1.91), (54.5, .93),
        (55.6, .31), (56, 0)], 'SP5 copper jacket', group, root)
    lathe('Neck_seal', [(38.5, 4.87), (38.5, 5.0), (39.17, 5.0), (39.17, 4.65)],
        'Primer and neck red lacquer', group, root)
    lathe('Primer_seal', [(.15, 2.40), (.14, 2.58), (.21, 2.67), (.28, 2.55)],
        'Primer and neck red lacquer', group, root)
    primer = B.cylinder('Primer_cap', (.18, 0, 0), 2.39, .13,
        'Primer brass', group, axis='X', parent=root, edge=.03)
    primer['asset_role'] = 'primer_cap'
    for name, position in [('Base', (0, 0, 0)), ('Tip', (56, 0, 0)), ('Center', (28, 0, 0))]:
        marker(name, position, group, root)
    return root


def extract_magazine() -> tuple:
    group = bpy.data.collections['04_Magazine']
    kept = [o for o in list(group.objects) if o.type == 'MESH']
    deps = bpy.context.evaluated_depsgraph_get()
    old_bounds = B.report_bounds('04_Magazine')
    # Удачные наружные детали сохраняют базовую сетку и модификаторы v2.
    matrices = {o: Matrix.Translation(-PIVOT) @ o.matrix_world for o in kept}
    for obj in list(bpy.data.objects):
        if obj not in kept:
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in kept:
        obj.parent = None
        obj.data = obj.data.copy()
        obj.data.transform(matrices[obj])
        obj.matrix_world = Matrix.Identity(4)
        obj['asset_role'] = 'body'
    group.name = 'Magazine_939_10_Empty'
    B.COLLECTIONS[group.name] = group
    root = B.empty(group.name, (0, 0, 0), group.name)
    root['asset_type'] = 'detachable_magazine'
    root['capacity'] = 10
    root['rounds_loaded'] = 0
    root['game_item_id'] = 'mag_939_10'
    root['on_vss_mm'] = [455, 0, -37]
    root['axes_source'] = '+X muzzle, +Z up, -Y right; origin = original magazine socket'
    for obj in kept:
        obj.parent = root
    bpy.context.view_layer.update()
    return root, old_bounds


def magazine_top(root: bpy.types.Object) -> None:
    group = root.name
    body = bpy.data.objects['Short_magazine_body']
    # Прежний закрытый верх был упрощён под ствольной коробкой. Отдельной модели
    # нужен немного более длинный верх: нижний силуэт и посадочный pivot сохраняются.
    for vertex in body.data.vertices:
        if abs(vertex.co.x + .031) < 1e-6 and vertex.co.z > -.010:
            vertex.co.x = -.034
            vertex.co.z = -.007
        elif abs(vertex.co.x - .023) < 1e-6 and vertex.co.z > .005:
            vertex.co.x = .031
            vertex.co.z = .011
    inner = [(424, -28), (485, -10), (484.5, -70), (490, -108),
             (488, -115), (445, -123), (440, -115), (434, -78)]
    profile = [(x - 455, (z if z >= -34 else -34 + .81 * (z + 34)) + 37)
               for x, z in inner]
    cutter = B.prism('Mouth_cutter', profile, 24, 'Recess black', group)
    B.difference(body, cutter)
    # Внутренние края требуют меньшего радиуса, чем внешняя сплошная заготовка.
    for mod in body.modifiers:
        if mod.type == 'BEVEL':
            mod.width = .00045
    for side in (-1, 1):
        outline = [(-31, -7.15), (15, 5.58), (15, 6.96), (-31, -5.77)]
        lip = B.prism('Feed_lip_' + ('right' if side < 0 else 'left'), outline,
            3.1, 'Blued steel', group, .24, side * 11.55, root)
        lip['asset_role'] = 'body'
    # Оба небольших наружных зацепа принадлежат магазину; рычаг остаётся у винтовки.
    for label, outline, width in [
        ('Front_mount_lug', [(23, 6), (28, 7), (29, 4), (24, 2)], 15),
        ('Rear_mount_lug', [(-33, -8), (-35, -8.5), (-35, -12), (-32, -11)], 12)]:
        obj = B.prism(label, outline, width, 'Blued steel', group, .3, parent=root)
        obj['asset_role'] = 'body'
    owner = B.empty('Follower_assembly', (0, 0, 0), group, root)
    owner['asset_role'] = 'follower'
    follower = B.prism('Follower_platform', [(-26, -13.3), (23, 1.20),
        (23, 3.65), (-26, -10.85)], 21.4, 'Follower dark steel', group, .5, parent=owner)
    follower['asset_role'] = 'follower'
    ridge = B.prism('Follower_support_ridge', [(-24, -10.6), (18, 1.82),
        (18, 3.35), (-24, -9.07)], 7.5, 'Follower dark steel', group, .45, -4.8, owner)
    ridge['asset_role'] = 'follower'
    for name, position in [('MountOrigin', (0, 0, 0)), ('FeedPoint', (0, -5.6, -1.2)),
                            ('Floorplate', (13, 0, -74))]:
        marker(name, position, group, root)


def clone_tree(source: bpy.types.Object, identifier: str, target_group: str) -> bpy.types.Object:
    bpy.context.view_layer.update()
    originals = [source, *source.children_recursive]
    group = B.COLLECTIONS[target_group]
    copies = {}
    for obj in originals:
        copy = obj.copy()
        if obj.data and obj.type == 'MESH':
            # Общие mesh datablocks позволяют редактировать одинаковые наружные состояния вместе.
            copy.data = obj.data
        group.objects.link(copy)
        copies[obj] = copy
    for obj, copy in copies.items():
        copy.parent = copies.get(obj.parent)
        copy.matrix_parent_inverse = Matrix.Identity(4)
        copy.matrix_basis = (obj.parent.matrix_world.inverted_safe() @ obj.matrix_world
                             if copy.parent else obj.matrix_world.copy())
    root = copies[source]
    root.name = identifier
    bpy.context.view_layer.update()
    return root


def add_loaded_rounds(root: bpy.types.Object, reusable: bpy.types.Object) -> None:
    group = root.name
    root['rounds_loaded'] = 10
    root['visible_rounds_geometry'] = 2
    follower = next(o for o in root.children_recursive if o.name.startswith('Follower_assembly'))
    follower.location.z -= .053
    follower.location.x += .006
    owner = B.empty('Visible_rounds', (0, 0, 0), group, root)
    owner['asset_role'] = 'rounds'
    # Для внешнего игрового состояния достаточно двух видимых патронов.
    # Остальные места задаёт игровая вместимость, скрытая механика не моделируется.
    for i in range(2):
        child = clone_tree(reusable, 'Round_' + str(i + 1).zfill(2), group)
        child.parent = owner
        child.location = Vector((-27 + i * .67, -5.6 if i % 2 == 0 else 5.6,
                                 -8.8 - i * 5.4)) * .001
        child.rotation_euler[1] = -math.radians(16.5 + i * 1.15)
        child['round_number'] = i + 1
        child['asset_role'] = 'rounds'
        for obj in child.children_recursive:
            obj['asset_role'] = 'rounds'
    bpy.context.view_layer.update()


def studio() -> None:
    scene = bpy.context.scene
    if '90_Studio' not in B.COLLECTIONS:
        B.collection('90_Studio')
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('Magazine studio')
    world.use_nodes = True
    background = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
    background.inputs['Color'].default_value = (.20, .23, .26, 1)
    background.inputs['Strength'].default_value = .6
    scene.world = world
    B.enum_set(scene.view_settings, 'view_transform', 'AgX')
    B.area('Mag_Key', (.0, -.28, .35), (0, 0, -.02), 9, .30)
    B.area('Mag_Fill', (-.16, .18, .22), (0, 0, -.02), 5, .20)
    B.area('Mag_Rim', (.18, .1, .06), (0, 0, -.02), 6, .12)
    B.camera('Camera_Beauty', (.16, -.23, .17), (0, 0, -.03), .16)
    B.camera('Camera_Side', (0, -.45, -.029), (0, 0, -.029), .12)
    B.camera('Camera_Top', (.065, -.095, .135), (0, 0, -.003), .095)
    B.camera('Camera_Front', (.35, -.06, .04), (.012, 0, -.032), .135)
    B.camera('Camera_Rear', (-.3, -.02, .03), (0, 0, -.03), .13)
    B.camera('Camera_Bottom', (.11, -.18, -.20), (0, 0, -.058), .13)
    B.camera('Camera_Cartridge', (.10, -.105, .06), (.028, 0, 0), .071)
    B.camera('Camera_Cartridge_Base', (-.09, -.02, .015), (.009, 0, 0), .065)
    scene.camera = bpy.data.objects['Camera_Beauty']


def visible(root: bpy.types.Object, state: bool) -> None:
    for obj in [root, *root.children_recursive]:
        obj.hide_render = not state
        obj.hide_set(not state)


def gallery(output: Path) -> None:
    for obj in [o for o in list(bpy.data.objects) if o.name.startswith('Loose_SP5_')]:
        for child in list(obj.children_recursive):
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(obj, do_unlink=True)
    roots = [bpy.data.objects[name] for name in IDENTIFIERS]
    for item, position in zip(roots, [(-.060, 0, 0), (.050, 0, 0), (.145, 0, -.025)]):
        visible(item, True)
        item.location = position
    bpy.context.view_layer.update()
    for i, offset in enumerate((-.025, .025)):
        loose = clone_tree(roots[2], 'Loose_SP5_' + str(i + 1), 'Cartridge_939_SP5')
        loose.location.z += offset
        loose.location.x += .003 * i
    if 'Camera_Gallery' in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects['Camera_Gallery'], do_unlink=True)
    B.camera('Camera_Gallery', (.18, -.55, .28), (.043, 0, -.028), .36)
    bpy.context.scene.camera = bpy.data.objects['Camera_Gallery']
    B.save_scene(output / 'VSS_Magazine_Ammo.blend')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('clay', 'final'), default='clay')
    parser.add_argument('--gallery-only', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.gallery_only:
        bpy.ops.wm.open_mainfile(filepath=str(output / 'VSS_Magazine_Ammo.blend'))
        B.COLLECTIONS.update({c.name: c for c in bpy.data.collections})
        gallery(output)
        return
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    B.COLLECTIONS.update({c.name: c for c in bpy.data.collections})
    root, old_bounds = extract_magazine()
    materials()
    magazine_top(root)
    B.collection('Cartridge_939_SP5')
    ammo = cartridge('Cartridge_939_SP5')
    B.collection('Magazine_939_10_Loaded')
    loaded = clone_tree(root, 'Magazine_939_10_Loaded', 'Magazine_939_10_Loaded')
    add_loaded_rounds(loaded, ammo)
    roots = [root, loaded, ammo]
    studio()
    original_materials = []
    if args.stage == 'clay':
        for obj in list(bpy.context.scene.objects):
            if obj.type == 'MESH':
                original_materials.append((obj, list(obj.data.materials)))
                obj.data.materials.clear()
                obj.data.materials.append(B.MATERIALS['Clay check'])
    report = {'source': str(SOURCE), 'source_sha256': digest, 'source_bounds': old_bounds, 'assets': {}}
    for item in roots:
        for other in roots:
            visible(other, other == item)
        bpy.context.view_layer.update()
        report['assets'][item.name] = B.report_bounds(item.name)
        views = [('beauty', 'Camera_Beauty', 1100, 900), ('top', 'Camera_Top', 1100, 850)]
        if item == ammo:
            views = [('beauty', 'Camera_Cartridge', 1300, 700), ('base', 'Camera_Cartridge_Base', 900, 700)]
            bpy.context.scene.camera = bpy.data.objects['Camera_Cartridge']
        else:
            bpy.context.scene.camera = bpy.data.objects['Camera_Beauty']
        B.save_scene(output / (item.name + ('_clay' if args.stage == 'clay' else '') + '.blend'))
        B.render_views(output, args.stage + '_' + item.name, views)
    report['source_unchanged'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    (output / ('build-report-' + args.stage + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not report['source_unchanged']:
        raise RuntimeError('Исходная винтовка изменилась')
    if args.stage == 'final':
        gallery(output)
    print('VSS_MAG_AMMO_BUILD ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
