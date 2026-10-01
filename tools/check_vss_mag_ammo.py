"""Read-only: evaluated размеры, оболочки, владельцы и свободный верх магазина."""
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
    output = args.output.resolve()
    identifier = Path(bpy.data.filepath).stem
    root = bpy.data.objects[identifier]
    meshes = [o for o in root.children_recursive if o.type == 'MESH']
    ammo = identifier.startswith('Cartridge')
    closed = {'max_boundary_edges': 0, 'max_nonmanifold_edges': 0,
        'max_overfull_edges': 0, 'max_wire_edges': 0,
        'max_loose_vertices': 0, 'max_nonfinite_vertices': 0}
    config = {'schema_version': 1,
        'description': 'Сохранённый художественный prop: размеры дизайна, закрытые оболочки, видимый верх',
        'targets': [{'id': identifier, 'objects': [o.name for o in meshes],
            'dimensions_mm': {'expected': [56, 11.35, 11.35] if ammo else [75.79622, 31, 87.999],
                              'tolerance_mm': [.025, .025, .025]},
            'finite_transforms': True, 'topology': {'evaluated': closed}}]}
    if not ammo:
        shell = [o.name for o in meshes if o.get('asset_role') == 'body']
        samples = [{'start': [x, y, .277*x+18], 'end': [x, y, .277*x-9]}
                   for x in (-15, 0, 15) for y in (-8, 0, 8)]
        config['passages'] = [{'id': 'Open_mouth_without_intentional_follower_or_rounds',
            'objects': shell, 'unit': 'mm', 'samples': samples, 'max_hits': 0}]
    (output / (identifier + '_audit_config.json')).write_text(json.dumps(config, indent=2), encoding='utf-8')
    deps = bpy.context.evaluated_depsgraph_get()
    zero_total, results = 0, []
    for obj in meshes:
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        zero = 0
        for poly in mesh.polygons:
            points = [evaluated.matrix_world @ mesh.vertices[i].co for i in poly.vertices]
            center = sum(points, Vector()) / len(points)
            area2 = sum(((a-center).cross(b-center) for a,b in zip(points, points[1:]+points[:1])), Vector())
            zero += area2.length*.5 < 1e-18
        zero_total += zero
        results.append({'object': obj.name, 'zero_area_faces': zero})
        evaluated.to_mesh_clear()
    rounds = [o for o in root.children_recursive if o.get('round_number')]
    issues = []
    if zero_total:
        issues.append('Нулевая evaluated площадь')
    if not ammo:
        loaded = identifier.endswith('Loaded')
        if root['rounds_loaded'] != (10 if loaded else 0) or len(rounds) != (2 if loaded else 0):
            issues.append('Неверное визуальное состояние магазина')
        if any(o.parent is None for o in meshes):
            issues.append('Есть деталь без владельца')
    if max(abs(v) for v in root.matrix_world.translation) > 1e-8:
        issues.append('Корень исходного ассета не в нуле')
    report = {'status': 'FAIL' if issues else 'PASS', 'issues': issues,
        'id': identifier, 'zero_area_faces': zero_total, 'objects': results,
        'capacity_state': root.get('rounds_loaded'), 'visible_round_props': len(rounds),
        'root_world_mm': [v*1000 for v in root.matrix_world.translation]}
    (output / (identifier + '_native_check.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('VSS_MAG_AMMO_NATIVE ' + json.dumps({k:v for k,v in report.items() if k != 'objects'}), flush=True)
    if issues:
        raise RuntimeError(str(issues))


if __name__ == '__main__':
    main()
