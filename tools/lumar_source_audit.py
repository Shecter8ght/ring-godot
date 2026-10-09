"""Чтение сохранённого исходника ЛУМАР без изменения библиотеки владельца."""
import bpy
import json
import sys
from pathlib import Path

args = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=args[0])
rows = []
dg = bpy.context.evaluated_depsgraph_get()
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    evaluated = obj.evaluated_get(dg)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    rows.append(dict(name=obj.name, tris=len(mesh.loop_triangles), hidden=obj.hide_render,
                     bounds=[list(obj.matrix_world @ __import__('mathutils').Vector(v)) for v in obj.bound_box],
                     materials=[s.material.name if s.material else '' for s in obj.material_slots],
                     uv=[u.name for u in obj.data.uv_layers], parent=obj.parent.name if obj.parent else None))
    evaluated.to_mesh_clear()
materials = []
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    materials.append(dict(name=mat.name, nodes=[dict(name=n.name, type=n.type,
        group=n.node_tree.name if n.type == 'GROUP' and n.node_tree else None) for n in mat.node_tree.nodes]))
report = dict(meshes=rows, tris=sum(r['tris'] for r in rows), materials=materials,
    objects=[dict(name=o.name, type=o.type, parent=o.parent.name if o.parent else None,
                  location=list(o.matrix_world.translation)) for o in bpy.data.objects if o.type != 'MESH'])
Path(args[1]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('LUMAR_AUDIT_OK', report['tris'], len(rows))
