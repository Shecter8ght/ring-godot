"""Read the approved PM and write a texture-stage inventory without saving it."""
from pathlib import Path
import sys,json,hashlib
import bpy,addon_utils
root=Path(__file__).resolve().parents[1]/'_asset_src/pm_texturing'
root.mkdir(parents=True,exist_ok=True)
source=Path(bpy.data.filepath)
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
import bl_ext.blender_org.ucupaint as U
def value(v):
    try:return list(v)
    except TypeError:return v
materials=[]
for m in bpy.data.materials:
    if not m.users:continue
    nodes=[]
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type.startswith('BSDF') or n.type=='GROUP':
                nodes.append(dict(name=n.name,type=n.type,group=n.node_tree.name if n.type=='GROUP' and n.node_tree else None,ucupaint=bool(n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node),inputs={s.identifier:value(s.default_value) for s in n.inputs if hasattr(s,'default_value')}))
    materials.append(dict(name=m.name,users=m.users,nodes=nodes))
objects=[]
for o in bpy.data.objects:
    if o.type!='MESH':continue
    verts=[o.matrix_world@v.co for v in o.data.vertices]
    lo=[min(v[i] for v in verts)*1000 for i in range(3)];hi=[max(v[i] for v in verts)*1000 for i in range(3)]
    objects.append(dict(name=o.name,parent=o.parent.name if o.parent else None,vertices=len(o.data.vertices),polygons=len(o.data.polygons),materials=[m.name if m else None for m in o.data.materials],uv=[l.name for l in o.data.uv_layers],helper=bool(o.get('PM engraving helper') or o.get('PM geometry helper')),bounds_mm=[lo,hi],matrix_world=[list(r) for r in o.matrix_world]))
r=dict(file=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),blender=bpy.app.version_string,ucupaint=U.common.get_current_version_str(),materials=materials,objects=objects,viewports=[a.spaces.active.shading.type for s in bpy.data.screens for a in s.areas if a.type=='VIEW_3D'])
(root/'source_inventory.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_TEXTURE_SOURCE',r['blender'],r['ucupaint'],r['sha256'],flush=True)
for o in objects:
    if 'lens' in o['name']:print('PM_GLASS',o,flush=True)
print('PM_TEXTURE_MATERIALS',[(m['name'],m['users']) for m in materials],flush=True)
