"""Read-only: критерии skill-аудита и физические площади сохранённой оптики."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    identifier = Path(bpy.data.filepath).stem
    root = bpy.data.objects[identifier]
    objects = [o for o in root.children_recursive if o.type == 'MESH']
    opaque = [o.name for o in objects if o.get('asset_role') != 'lens']
    pso = identifier.startswith('PSO')
    axis_y, axis_z = (-15.5, 90) if pso else (0, 32)
    extent = (-195, 190) if pso else (-95, 94)
    samples = [{'start': [extent[0], axis_y + y, axis_z + z],
                'end': [extent[1], axis_y + y, axis_z + z]}
               for y in (-8, 0, 8) for z in (-8, 0, 8)]
    extra = [{'start': [x, -20, z], 'end': [x, 35, z]}
             for x in (-10, 10) for z in (25, 35)] if pso else [
                {'start': [x, -7.9, z], 'end': [x, 7.9, z]}
                for x in (-20, 20) for z in (-2, -5)]
    closed = {'max_boundary_edges': 0, 'max_nonmanifold_edges': 0,
              'max_overfull_edges': 0, 'max_wire_edges': 0,
              'max_loose_vertices': 0, 'max_nonfinite_vertices': 0}
    config = {'schema_version': 1, 'description': 'Наружная оптика: размеры дизайна, оболочки и декоративный проход без линз',
        'targets': [{'id': identifier, 'objects': [o.name for o in objects],
            'dimensions_mm': {'expected': [375, 70.34, 133.64] if pso else [180, 61.08, 69.54],
                              'tolerance_mm': [.03, .05, .05]},
            'finite_transforms': True, 'topology': {'evaluated': closed}}],
        'passages': [{'id': 'Optical_shell_clearance_without_lenses', 'objects': opaque,
                      'unit': 'mm', 'samples': samples, 'max_hits': 0},
                     {'id': 'Bracket_or_rail_recess', 'objects': opaque,
                      'unit': 'mm', 'samples': extra, 'max_hits': 0}]}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / (identifier + '_audit_config.json')).write_text(json.dumps(config, indent=2), encoding='utf-8')
    deps = bpy.context.evaluated_depsgraph_get()
    results = []
    for obj in objects:
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        zero = 0
        for polygon in mesh.polygons:
            points = [evaluated.matrix_world @ mesh.vertices[i].co for i in polygon.vertices]
            center = sum(points, Vector()) / len(points)
            twice = sum(((a - center).cross(b - center) for a, b in
                zip(points, points[1:] + points[:1])), Vector())
            zero += twice.length * .5 < 1e-18
        results.append({'object': obj.name, 'zero_area_faces': zero})
        evaluated.to_mesh_clear()
    zero_total = sum(r['zero_area_faces'] for r in results)
    report = {'status': 'FAIL' if zero_total else 'PASS', 'zero_area_faces': zero_total,
              'epsilon_m2': 1e-18, 'scope': identifier, 'objects': results}
    (output / (identifier + '_native_area.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('OPTIC_NATIVE_AREA ' + json.dumps({'status': report['status'], 'zero_area_faces': zero_total}), flush=True)
    if zero_total:
        raise RuntimeError('Нулевые evaluated грани')


if __name__ == '__main__':
    main()
