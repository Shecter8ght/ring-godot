"""Магазины и патрон -> PBR GLB; проверка исходника и чистого повторного импорта."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
from build_vss_mag_ammo import IDENTIFIERS


def reduce(obj: bpy.types.Object, budget: int) -> None:
    E.active(obj)
    count = E.triangles(obj)
    if count > budget:
        mod = obj.modifiers.new('External prop budget', 'DECIMATE')
        mod.ratio = budget / count
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', choices=IDENTIFIERS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(bpy.data.filepath)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    folder = args.output.resolve() / args.id
    folder.mkdir(parents=True, exist_ok=True)
    original = bpy.data.objects[args.id]
    original.name += '_Source'
    parts = [o for o in original.children_recursive if o.type == 'MESH']
    source_bounds = E.bounds([o.evaluated_get(bpy.context.evaluated_depsgraph_get()) for o in parts])
    labels = ('Base', 'Tip', 'Center') if args.id.startswith('Cartridge') else ('MountOrigin', 'FeedPoint', 'Floorplate')
    positions = {o.name.split('.')[0]: list(E.MAP @ o.matrix_world.translation)
        for o in original.children_recursive if o.type == 'EMPTY' and o.name.split('.')[0] in labels}
    group = bpy.data.collections.new('Game_' + args.id)
    bpy.context.scene.collection.children.link(group)
    root = bpy.data.objects.new(args.id, None)
    group.objects.link(root)
    for key in ('asset_type', 'caliber', 'variant', 'capacity', 'rounds_loaded',
                'visible_rounds_geometry', 'game_item_id', 'on_vss_mm'):
        if key in original:
            root[key] = original[key]
    root['axes_gltf'] = '+Z forward, +Y up, -X right'
    copies = []
    if args.id.startswith('Cartridge'):
        body = E.joined(parts, 'Body', group, root)
        reduce(body, 1400)
    else:
        body = E.joined([o for o in parts if o.get('asset_role') != 'rounds'], 'Body', group, root)
        for child in original.children_recursive:
            if child.type == 'EMPTY' and child.get('round_number'):
                mesh = E.joined([o for o in child.children_recursive if o.type == 'MESH'],
                                'Round_' + str(child['round_number']), group, root)
                reduce(mesh, 1400)
                copies.append(mesh)
        if copies:
            E.active(body)
            for obj in copies:
                obj.select_set(True)
            bpy.ops.object.join()
            body = bpy.context.object
            body.name = 'Body'
    for obj in parts:
        obj.hide_render = True
        obj.hide_set(True)
    # Запекается собственный атлас; визуальные состояния заменяются целиком.
    E.bake_maps(body, folder)
    for label, position in positions.items():
        marker = bpy.data.objects.new(label + '_export', None)
        group.objects.link(marker)
        marker.parent = root
        marker.location = position
        marker.empty_display_size = .003
    game = {root, *root.children_recursive}
    for obj in list(bpy.data.objects):
        if obj not in game and obj.type not in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(obj, do_unlink=True)
        elif obj.type in {'CAMERA', 'LIGHT'}:
            obj.matrix_world = E.MAP @ obj.matrix_world
    for obj in root.children:
        if obj.type == 'EMPTY':
            obj.name = obj.name.removesuffix('_export')
    bpy.context.view_layer.update()
    before = E.topology(body)
    if any(before.values()):
        raise RuntimeError('Незамкнутая игровая оболочка: ' + str(before))
    glb = folder / (args.id + '.glb')
    E.active(root)
    for obj in root.children_recursive:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
        export_extras=True, export_animations=False, export_cameras=False, export_lights=False)
    report = {'id': args.id, 'source': str(source), 'source_sha256': digest,
        'source_bounds': source_bounds, 'game_blender_bounds': E.bounds([body]),
        'triangles': E.triangles(body), 'topology_before_export': before,
        'markers_blender_m': positions, 'markers': list(labels),
        'axes': '+Z forward, +Y up, -X right', 'surfaces': 1,
        'uv': '2048 basecolor/ORM/normal embedded',
        'orm': 'R=1 (AO not baked), G roughness, B metallic',
        'glb': str(glb), 'glb_sha256': hashlib.sha256(glb.read_bytes()).hexdigest()}
    B.save_scene(folder / (args.id + '_Game.blend'))
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    imported_bounds = E.bounds(meshes)
    imported_positions = {o.name: list(o.matrix_world.translation)
        for o in bpy.context.scene.objects if o.name in labels}
    issues = []
    if len(meshes) != 1:
        issues.append('Ожидается один статический меш')
    for label, expected in positions.items():
        actual = imported_positions.get(label)
        if actual is None or max(abs(a-b) for a,b in zip(actual, expected)) > 1e-6:
            issues.append('Утрачена метка ' + label)
    if len(positions) != 3:
        issues.append('Недостаточно исходных меток')
    for a,b in zip(imported_bounds['dimensions_mm'], report['game_blender_bounds']['dimensions_mm']):
        if abs(a-b) > .02:
            issues.append('Изменён габарит')
    after = {o.name: E.topology(o, weld_gpu_seams=True) for o in meshes}
    if any(v['boundary_edges'] or v['zero_area_faces'] or v['loose_vertices'] for v in after.values()):
        issues.append('Нарушена оболочка при повторном импорте')
    unchanged = hashlib.sha256(source.read_bytes()).hexdigest() == digest
    if not unchanged:
        issues.append('Исходник изменён экспортом')
    report.update({'status': 'FAIL' if issues else 'PASS', 'issues': issues,
        'source_unchanged': unchanged, 'reimport_bounds': imported_bounds,
        'reimport_markers': imported_positions, 'reimport_topology': after})
    (folder / 'export-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if issues:
        raise RuntimeError(str(issues))
    print('VSS_MAG_AMMO_EXPORT_PASS ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
