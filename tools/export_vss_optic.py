"""Сохранённая оптика -> автономный PBR GLB с проверкой повторного импорта.

Blender CLI FILE.blend --python tools/export_vss_optic.py -- --id ID --output DIR.
Исходный .blend не перезаписывается. Экспорт: +Z вперёд, +Y вверх, -X вправо.
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

MAP = Matrix(((0, 1, 0, 0), (-1, 0, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
MARKERS = ('MountOrigin', 'OpticalAxis', 'Ocular', 'EyePoint', 'Objective')


def active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def triangles(obj: bpy.types.Object) -> int:
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def bounds(objects: list) -> dict:
    vertices = [obj.matrix_world @ vertex.co for obj in objects if obj.type == 'MESH'
                for vertex in obj.data.vertices]
    low = [min(v[i] for v in vertices) for i in range(3)]
    high = [max(v[i] for v in vertices) for i in range(3)]
    return {'min_mm': [v * 1000 for v in low], 'max_mm': [v * 1000 for v in high],
            'dimensions_mm': [(b - a) * 1000 for a, b in zip(low, high)]}


def topology(obj: bpy.types.Object, weld_gpu_seams: bool = False) -> dict:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if weld_gpu_seams:
        # glTF разделяет вершины на UV/normal seams; проверяется геометрическое замыкание.
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-8)
    bad_edges = sum(len(edge.link_faces) != 2 for edge in bm.edges)
    boundary = sum(len(edge.link_faces) == 1 for edge in bm.edges)
    overfull = sum(len(edge.link_faces) > 2 for edge in bm.edges)
    zero = 0
    for face in bm.faces:
        points = [obj.matrix_world @ v.co for v in face.verts]
        center = sum(points, Vector()) / len(points)
        twice = sum(((a - center).cross(b - center) for a, b in
            zip(points, points[1:] + points[:1])), Vector())
        zero += twice.length * .5 < 1e-18
    loose = sum(not v.link_edges for v in bm.verts)
    bm.free()
    return {'nonmanifold_edges': bad_edges, 'boundary_edges': boundary,
            'overfull_edges': overfull, 'zero_area_faces': zero, 'loose_vertices': loose}


def joined(objects: list, label: str, group: bpy.types.Collection, parent: bpy.types.Object) -> bpy.types.Object:
    deps = bpy.context.evaluated_depsgraph_get()
    copies = []
    for obj in objects:
        evaluated = obj.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=deps)
        mesh.transform(MAP @ obj.matrix_world)
        copy = bpy.data.objects.new(label + '_part', mesh)
        group.objects.link(copy)
        copies.append(copy)
    active(copies[0])
    for obj in copies:
        obj.select_set(True)
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = label
    obj.parent = parent
    return obj


def bake_maps(body: bpy.types.Object, folder: Path) -> dict:
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.device = 'CPU'
    scene.render.bake.margin = 8
    active(body)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.004,
                            area_weight=.5, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    materials = [slot.material for slot in body.material_slots]
    surfaces = []
    for mat in materials:
        nodes = mat.node_tree.nodes
        output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL')
        bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
        surfaces.append((mat, output, bsdf))
    images = {}
    for label in ('basecolor', 'orm', 'normal'):
        image = bpy.data.images.new(label, width=2048, height=2048, alpha=False)
        image.colorspace_settings.name = 'sRGB' if label == 'basecolor' else 'Non-Color'
        targets = []
        emissions = []
        for mat, output, bsdf in surfaces:
            nodes, links = mat.node_tree.nodes, mat.node_tree.links
            target = nodes.new('ShaderNodeTexImage')
            target.image = image
            target.select = True
            nodes.active = target
            targets.append((mat, target))
            if label != 'normal':
                emission = nodes.new('ShaderNodeEmission')
                color = bsdf.inputs['Base Color'].default_value[:]
                emission.inputs['Color'].default_value = color if label == 'basecolor' else (
                    1, bsdf.inputs['Roughness'].default_value, bsdf.inputs['Metallic'].default_value, 1)
                links.new(emission.outputs[0], output.inputs['Surface'])
                emissions.append((mat, output, bsdf, emission))
        bpy.ops.object.bake(type='NORMAL' if label == 'normal' else 'EMIT')
        image.filepath_raw = str(folder / (label + '.png'))
        B.enum_set(image, 'file_format', 'PNG')
        image.save()
        image.pack()
        images[label] = image
        for mat, output, bsdf, emission in emissions:
            mat.node_tree.links.new(bsdf.outputs[0], output.inputs['Surface'])
            mat.node_tree.nodes.remove(emission)
        for mat, target in targets:
            mat.node_tree.nodes.remove(target)
        print('OPTIC_EXPORT baked ' + label, flush=True)
    mat = B.material('Optic_Game_PBR', (.012, .015, .019), .65, .36)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    for label, image in images.items():
        node = nodes.new('ShaderNodeTexImage')
        node.image = image
        if label == 'basecolor':
            links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
        elif label == 'normal':
            normal = nodes.new('ShaderNodeNormalMap')
            links.new(node.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
        else:
            separate = nodes.new('ShaderNodeSeparateColor')
            B.enum_set(separate, 'mode', 'RGB')
            links.new(node.outputs['Color'], separate.inputs[0])
            links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
            links.new(separate.outputs['Blue'], bsdf.inputs['Metallic'])
    body.data.materials.clear()
    body.data.materials.append(mat)
    for poly in body.data.polygons:
        poly.material_index = 0
    return images


def portable_glass(obj: bpy.types.Object) -> None:
    # Простая прозрачность переносится в Godot без зависимости от объёмной оптики Cycles.
    mat = B.material('Optic_Game_Lens', (.02, .085, .095), .12, .08)
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Alpha'].default_value = .52
    bsdf.inputs['Coat Weight'].default_value = .4
    if hasattr(mat, 'surface_render_method'):
        B.enum_set(mat, 'surface_render_method', 'DITHERED')
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.material_index = 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True, choices=['PSO_VSS_4x24', 'Rail_4x32'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = Path(bpy.data.filepath)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    folder = args.output.resolve() / args.id
    folder.mkdir(parents=True, exist_ok=True)
    source_root = bpy.data.objects[args.id]
    source_root.name += '_Source'
    original_objects = list(bpy.context.scene.objects)
    parts = [o for o in source_root.children_recursive if o.type == 'MESH']
    marker_positions = {o.name.split('.')[0]: list(MAP @ o.matrix_world.translation)
        for o in source_root.children_recursive if o.type == 'EMPTY' and o.name.split('.')[0] in MARKERS}
    source_bounds = bounds(parts)
    group = bpy.data.collections.new('Game_Optic')
    bpy.context.scene.collection.children.link(group)
    root = bpy.data.objects.new(args.id, None)
    group.objects.link(root)
    root['asset_type'] = 'detachable_optic'
    root['axes_gltf'] = '+Z objective, +Y up, -X right'
    root['mount'] = source_root.get('mount', '')
    root['source_on_vss_mm'] = list(source_root.get('on_vss_mm', []))
    body = joined([o for o in parts if o.get('asset_role') != 'lens'], 'Body', group, root)
    lenses = joined([o for o in parts if o.get('asset_role') == 'lens'], 'Lenses', group, root)
    budget = 12500 if args.id.startswith('PSO') else 11000
    active(body)
    if triangles(body) > budget:
        mod = body.modifiers.new('Game budget', 'DECIMATE')
        mod.ratio = budget / triangles(body)
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    active(lenses)
    mod = lenses.modifiers.new('Lens budget', 'DECIMATE')
    mod.ratio = min(1, 640 / triangles(lenses))
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    for obj in parts:
        obj.hide_render = True
        obj.hide_set(True)
    lenses.hide_render = True
    bake_maps(body, folder)
    lenses.hide_render = False
    portable_glass(lenses)
    for label, position in marker_positions.items():
        obj = bpy.data.objects.new(label + '_export', None)
        group.objects.link(obj)
        obj.parent = root
        obj.location = position
        obj.empty_display_size = .004
    # Старые владельцы и детали исключаются из игровой копии, но остаются в исходнике.
    game_objects = {root, *root.children_recursive}
    for obj in list(bpy.data.objects):
        if obj not in game_objects and obj.type not in {'LIGHT', 'CAMERA'}:
            bpy.data.objects.remove(obj, do_unlink=True)
        elif obj.type in {'LIGHT', 'CAMERA'}:
            obj.matrix_world = MAP @ obj.matrix_world
    for obj in root.children:
        if obj.type == 'EMPTY':
            obj.name = obj.name.removesuffix('_export')
    bpy.context.view_layer.update()
    source_topology = {o.name: topology(o) for o in (body, lenses)}
    if any(any(values.values()) for values in source_topology.values()):
        raise RuntimeError('Некорректная игровая сетка: ' + str(source_topology))
    try:
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        pass
    glb = folder / (args.id + '.glb')
    active(root)
    for obj in root.children_recursive:
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True,
        export_extras=True, export_animations=False, export_cameras=False, export_lights=False)
    game_bounds = bounds([body, lenses])
    report = {'source': str(source), 'source_sha256': source_hash, 'source_bounds': source_bounds,
        'game_blender_bounds': game_bounds, 'triangles': triangles(body) + triangles(lenses),
        'body_triangles': triangles(body), 'lens_triangles': triangles(lenses),
        'topology_before_export': source_topology, 'markers_blender_m': marker_positions,
        'game_axes': '+Z forward, +Y up, -X right; root origin = mount contact',
        'uv': 'smart UV atlas, 2048 basecolor/ORM/normal, embedded',
        'orm': 'R = 1 (AO not baked), G roughness, B metallic',
        'glb': str(glb), 'glb_sha256': hashlib.sha256(glb.read_bytes()).hexdigest()}
    B.save_scene(folder / (args.id + '_Game.blend'))
    # Чистый повторный импорт проверяет фактический экспорт, а не только исходную сцену.
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    imported = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    actual_bounds = bounds(imported)
    actual_markers = {o.name: list(o.matrix_world.translation) for o in bpy.context.scene.objects
                      if o.name in MARKERS}
    issues = []
    if len(imported) != 2:
        issues.append('Ожидаются два меша: Body и Lenses')
    for label, expected in marker_positions.items():
        actual = actual_markers.get(label)
        if actual is None or max(abs(a - b) for a, b in zip(actual, expected)) > 1e-6:
            issues.append('Неверная метка ' + label)
    for a, b in zip(actual_bounds['dimensions_mm'], game_bounds['dimensions_mm']):
        if abs(a - b) > .02:
            issues.append('Изменён габарит после GLB')
    actual_topology = {o.name: topology(o, weld_gpu_seams=True) for o in imported}
    # Совпавшие границы самостоятельных закрытых деталей дают overfull после weld.
    # Это наблюдение, а не пробоина; исходные индексированные оболочки проверены выше.
    if any(v['boundary_edges'] or v['zero_area_faces'] or v['loose_vertices']
           for v in actual_topology.values()):
        issues.append('Нарушена топология при повторном импорте')
    report.update({'status': 'FAIL' if issues else 'PASS', 'issues': issues,
        'reimport_bounds': actual_bounds, 'reimport_markers': actual_markers,
        'reimport_topology': actual_topology,
        'reimport_topology_method': 'Weld GPU seams at 1e-8 m; no boundary/zero-area/loose. Touching-shell overfull is informational; source shells closed.',
        'source_unchanged': hashlib.sha256(source.read_bytes()).hexdigest() == source_hash})
    (folder / 'export-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if issues:
        raise RuntimeError(str(issues))
    print('OPTIC_EXPORT_PASS ' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
