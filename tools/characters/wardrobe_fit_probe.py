"""Снимок фактических координат, связей масок и модификаторов для проверки посадки."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,json,addon_utils,importlib
from mathutils import Vector
source=Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.wm.open_mainfile(filepath=str(source))
bpy.context.preferences.use_preferences_save=False
module='bl_ext.blender_org.ucupaint'
if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
addon_utils.enable(module,default_set=False,persistent=False)
U=importlib.import_module(module)
control=bpy.data.objects['RING | Wardrobe Controls']
control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
result={'cuffs':[],'bones':[b.name for b in bpy.data.objects['M02_New_Anatomical_Rig'].data.bones if 'neck' in b.name],'top':[],'masks':[]}
result['near_wrists']=[]
for obj in bpy.data.objects:
    if obj.type!='MESH' or obj.hide_render: continue
    verts=[obj.matrix_world@Vector(co) for co in obj.bound_box]
    if any(.66<abs(p.x)<.8 and 1.39<p.z<1.45 for p in verts):
        result['near_wrists'].append(obj.name)
for obj in bpy.data.objects:
    if obj.type!='MESH' or obj.get('wardrobe_id')!='T01': continue
    verts=[obj.matrix_world@Vector(co) for co in obj.bound_box]
    if max(abs(p.x) for p in verts)>.6:
        result['cuffs'].append({'name':obj.name,'min':[min(p[i] for p in verts) for i in range(3)],'max':[max(p[i] for p in verts) for i in range(3)],'hidden':obj.hide_render})
    if 'sewn main' in obj.name:
        ev=obj.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
        result['top']=[list(v.co) for v in mesh.vertices if abs(v.co.x)<.004 and v.co.y<-.02 and v.co.z>1.40]
        ev.to_mesh_clear()
for name in ['combat_knit','denim']:
    mat=bpy.data.materials[name];tree=next(n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    for ly in tree.yp.layers:
        if not ly.masks: continue
        lt=U.common.get_tree(ly)
        masks=[]
        for mask in ly.masks:
            src=U.common.get_mask_source(mask)
            masks.append({'type':mask.type,'socket':mask.socket_input_name,'source':src.name,'links':[(l.from_socket.name,l.to_node.name,l.to_socket.name) for o in src.outputs for l in o.links]})
        result['masks'].append({'material':name,'layer':ly.name,'masks':masks})
(source.parent/'fit_diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'wrists':result['near_wrists'],'bones':result['bones'],'top_max':max((p[2] for p in result['top']),default=0)}),flush=True)
