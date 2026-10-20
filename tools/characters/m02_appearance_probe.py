"""Inspect saved M02 and the local native painting API without changing the source."""
import addon_utils
import bpy
import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '_asset_src/npc_m02/appearance_work'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / '_asset_src/npc_m02/geometry_v06/M02_Body_Head_Geometry_v06.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
bpy.context.preferences.use_preferences_save = False
module = 'bl_ext.blender_org.ucupaint'
if module not in bpy.context.preferences.addons:
    bpy.context.preferences.addons.new().module = module
addon_utils.enable(module, default_set=False, persistent=False)
U = importlib.import_module(module)
result = {'blender': bpy.app.version_string, 'ucupaint': U.common.get_current_version_str(), 'objects': []}
for obj in bpy.data.objects:
    if obj.type != 'MESH' or not obj.name.startswith('M02_'):
        continue
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    result['objects'].append({'name': obj.name, 'verts': len(points),
        'bounds': [[min(p[a] for p in points), max(p[a] for p in points)] for a in range(3)],
        'materials': [m.name if m else None for m in obj.data.materials],
        'shape_keys': list(obj.data.shape_keys.key_blocks.keys()) if obj.data.shape_keys else [],
        'modifiers': [{'name':m.name,'type':m.type} for m in obj.modifiers]})
body = bpy.data.objects['M02_Body_Head']
result['facial_rows'] = {}
for height in [1.55,1.58,1.60,1.62,1.64,1.66,1.68,1.70,1.72,1.74,1.76]:
    points = [obj for obj in [(v.index,body.matrix_world @ v.co) for v in body.data.vertices]
        if abs(obj[1].z-height)<0.003 and abs(obj[1].x)<0.012 and obj[1].y<0]
    result['facial_rows'][str(height)] = [[idx,list(p)] for idx,p in sorted(points,key=lambda x:x[1].y)[:4]]
result['devices'] = []
cycles = bpy.context.preferences.addons.get('cycles')
if cycles:
    try:
        cycles.preferences.compute_device_type = 'OPTIX'
        cycles.preferences.get_devices()
        result['devices'] = [{'name':d.name,'type':d.type} for d in cycles.preferences.devices]
    except Exception as exc:
        result['gpu_error'] = str(exc)
result['principled_inputs'] = [i.name for i in next(n for n in body.active_material.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs]
eye=bpy.data.objects['M02_Eyes'].active_material
result['eye_nodes']=[{'name':n.name,'type':n.type,'group':n.node_tree.name if n.type=='GROUP' else None,
    'inputs':{i.name:(list(i.default_value) if hasattr(i.default_value,'__len__') else i.default_value) for i in n.inputs if hasattr(i,'default_value') and i.type in {'VALUE','RGBA'}},
    'links':[(l.from_socket.name,l.to_node.name,l.to_socket.name) for s in n.outputs for l in s.links]}
    for n in eye.node_tree.nodes]
(OUT/'environment.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('M02_APPEARANCE_PROBE '+json.dumps(result))
