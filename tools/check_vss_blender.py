"""Контроль сохранённого ассета в новом Blender-процессе.

Геометрия не меняется. Площадь через локальный векторный контур дополняет
skill-аудит: tessellate_polygon теряет некоторые тонкие, но целые грани.
"""
import json
from pathlib import Path
import bpy
from mathutils import Vector

scene = bpy.context.scene
scope = bpy.data.collections['VSS_Assembly']
depsgraph = bpy.context.evaluated_depsgraph_get()
area_to_mm2 = (scene.unit_settings.scale_length * 1000) ** 2
report = {'blend': bpy.data.filepath, 'objects': [], 'zero_area_faces': 0, 'status': 'PASS'}
for obj in scope.all_objects:
    if obj.type != 'MESH':
        continue
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    world = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
    zero_faces = []
    for polygon in mesh.polygons:
        points = [world[i] for i in polygon.vertices]
        origin = points[0]
        normal_area = Vector((0, 0, 0))
        for a, b in zip(points, points[1:] + points[:1]):
            normal_area += (a - origin).cross(b - origin)
        area_mm2 = normal_area.length * .5 * area_to_mm2
        if area_mm2 <= 1e-10:
            zero_faces.append(polygon.index)
    report['objects'].append({'object': obj.name, 'zero_area_faces': len(zero_faces), 'indices': zero_faces})
    report['zero_area_faces'] += len(zero_faces)
    evaluated.to_mesh_clear()
report['status'] = 'PASS' if report['zero_area_faces'] == 0 else 'FAIL'
output = Path(bpy.data.filepath).parent / 'vss_native_area_report.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('VSS_NATIVE_AREA', report['status'], report['zero_area_faces'])
for item in report['objects']:
    if item['zero_area_faces']:
        print(item['object'], item['zero_area_faces'])
