"""Проверка фактических значений нативных слоёв независимо от освещения рендера."""
import bpy, addon_utils, importlib, json, sys
from pathlib import Path
path=Path(sys.argv[sys.argv.index('--')+1]).resolve()
bpy.ops.wm.open_mainfile(filepath=str(path))
bpy.context.preferences.use_preferences_save=False
module='bl_ext.blender_org.ucupaint'
if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
addon_utils.enable(module,default_set=False,persistent=False)
U=importlib.import_module(module)
result={}
for name in ['denim','plaid','suede']:
    mat=bpy.data.materials[name]
    node=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree=node.node_tree
    entries=[]
    for layer in tree.yp.layers:
        entries.append({'layer':layer.name,'amount':float(U.common.get_entity_prop_value(layer,'intensity_value')),
            'channels':[{'name':root.name,'enabled':channel.enable,'override':channel.override,
                'value':list(U.common.get_entity_prop_value(channel,'override_color')) if root.type=='RGB' else float(U.common.get_entity_prop_value(channel,'override_value'))}
                for root,channel in zip(tree.yp.channels,layer.channels)],
            'masks':[{'name':mask.name,'enabled':mask.enable,'source_type':U.common.get_mask_source(mask).bl_idname,
                'attribute':getattr(U.common.get_mask_source(mask),'attribute_name',getattr(U.common.get_mask_source(mask),'layer_name',None))}
                for mask in layer.masks]})
    bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    objs=[o for o in bpy.data.objects if o.type=='MESH' and any(s.material==mat for s in o.material_slots)]
    values=[]
    for obj in objs:
        attr=obj.data.color_attributes.get('WardrobeWear')
        if attr: values.append({'object':obj.name,'max':max((d.color[0] for d in attr.data),default=0)})
    result[name]={'base_color_links':[(l.from_node.name,l.from_socket.name) for l in bsdf.inputs['Base Color'].links],
                  'wear_attributes':values,'layers':entries}
(path.parent/'material_diagnostics.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('MATERIAL_DIAGNOSTICS '+str(path.parent/'material_diagnostics.json'),flush=True)
