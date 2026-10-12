"""Read the owner's saved grenade in Blender without changing it."""
import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex'
SOURCE = Path('E:/Models Blender/From Scenario/Grenade/Grenade.blend')
OUT.mkdir(parents=True, exist_ok=True)
bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.view_layer.update()
report = {
    'source': str(SOURCE), 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'blender': bpy.app.version_string, 'units': {
        'system': bpy.context.scene.unit_settings.system,
        'scale_length': bpy.context.scene.unit_settings.scale_length,
        'length_unit': bpy.context.scene.unit_settings.length_unit,
    }, 'frame': bpy.context.scene.frame_current,
    'collections': [c.name for c in bpy.data.collections],
    'objects': [], 'materials': [], 'images': [], 'actions': [],
}
all_points = []
dg = bpy.context.evaluated_depsgraph_get()
for ob in bpy.context.scene.objects:
    row = {'name': ob.name, 'type': ob.type, 'parent': ob.parent.name if ob.parent else None,
           'location': list(ob.location), 'rotation': list(ob.rotation_euler), 'scale': list(ob.scale),
           'custom': {str(k): str(ob[k]) for k in ob.keys()},
           'modifiers': [{'name': m.name, 'type': m.type} for m in ob.modifiers],
           'hide_render': ob.hide_render, 'hide_viewport': ob.hide_viewport,
           'drivers': [{'path': f.data_path, 'index': f.array_index, 'expression': f.driver.expression}
                       for f in ob.animation_data.drivers] if ob.animation_data else [],
           'action': ob.animation_data.action.name if ob.animation_data and ob.animation_data.action else None}
    if ob.type == 'MESH':
        ev = ob.evaluated_get(dg)
        pts = [ev.matrix_world @ Vector(p) for p in ev.bound_box]
        mn = [min(p[i] for p in pts) for i in range(3)]
        mx = [max(p[i] for p in pts) for i in range(3)]
        row.update(vertices=len(ob.data.vertices), faces=len(ob.data.polygons),
                   materials=[m.name if m else None for m in ob.data.materials],
                   uv=[u.name for u in ob.data.uv_layers],
                   bounds_min=mn, bounds_max=mx,
                   dimensions_m=[mx[i]-mn[i] for i in range(3)])
        if not ob.hide_render:
            all_points.extend(pts)
    report['objects'].append(row)
if all_points:
    report['visible_mesh_bounds_m'] = [max(p[i] for p in all_points)-min(p[i] for p in all_points) for i in range(3)]
for mat in bpy.data.materials:
    report['materials'].append({'name': mat.name, 'nodes': [{'name': n.name, 'type': n.type,
        'image': n.image.name if n.type == 'TEX_IMAGE' and n.image else None} for n in mat.node_tree.nodes] if mat.node_tree else []})
for im in bpy.data.images:
    report['images'].append({'name': im.name, 'path': im.filepath, 'size': list(im.size), 'packed': bool(im.packed_file)})
for act in bpy.data.actions:
    report['actions'].append({'name': act.name, 'frames': list(act.frame_range)})
(OUT / 'source_inspection.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
print('GRENADE_INSPECTION_OK', flush=True)
