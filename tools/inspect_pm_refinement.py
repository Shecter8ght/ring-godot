"""Read the owner's saved PM without modifying it; JSON for the geometry revision."""
from pathlib import Path
import json
import bpy
from mathutils import Vector

OUT = Path(__file__).resolve().parents[1] / '_asset_src/pm_refinement/work'
OUT.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.frame_set(1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
rows = []
for obj in bpy.data.objects:
    eo = obj.evaluated_get(dg)
    row = dict(name=obj.name, type=obj.type, parent=obj.parent.name if obj.parent else None,
               loc=list(obj.location), scale=list(obj.scale), matrix=[list(r) for r in obj.matrix_world],
               hidden=obj.hide_render, collections=[c.name for c in obj.users_collection])
    if obj.type in {'MESH', 'CURVE'}:
        corners = [eo.matrix_world @ Vector(v) for v in eo.bound_box]
        row['bounds_mm'] = [[min(v[i] for v in corners)*1000 for i in range(3)],
                            [max(v[i] for v in corners)*1000 for i in range(3)]]
        row['materials'] = [s.material.name if s.material else None for s in obj.material_slots]
    if obj.type == 'MESH':
        row['vertices'] = len(obj.data.vertices)
        row['faces'] = len(obj.data.polygons)
        row['data_bounds'] = [[min(v.co[i] for v in obj.data.vertices) for i in range(3)],
                              [max(v.co[i] for v in obj.data.vertices) for i in range(3)]]
        row['modifiers'] = [dict(name=m.name, type=m.type,
            **{k:getattr(m,k) for k in ('width','segments','limit_method','angle_limit','use_clamp_overlap','harden_normals') if hasattr(m,k)}) for m in obj.modifiers]
    rows.append(row)
report = dict(file=bpy.data.filepath, version=bpy.app.version_string,
    scene_scale=scene.unit_settings.scale_length, engine=scene.render.engine,
    root_properties=dict(bpy.data.objects['PM_CONTROLS • select me'].items()),
    collections=[c.name for c in bpy.data.collections], objects=rows,
    images=[dict(name=i.name,path=i.filepath,size=list(i.size),packed=bool(i.packed_file)) for i in bpy.data.images])
(OUT/'source_inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),encoding='utf-8')
print('PM_INSPECT', bpy.data.filepath, bpy.app.version_string, len(rows), flush=True)
for row in rows:
    if row['type'] == 'MESH' and any(row['name'].startswith(n) for n in ('Slide |','Hammer |','Safety |','Bakelite |','Trigger |','Sight |','Barrel |','Extractor')):
        print(row['name'], row['bounds_mm'], row['vertices'], row['modifiers'], flush=True)
