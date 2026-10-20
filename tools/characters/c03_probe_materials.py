"""Проверить реальные сокеты и маски сохранённых материалов C03."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy,json,importlib
import m02_custom_clothes_deliver as D
import wardrobe_materials as M
D.enable_layers();M.U=importlib.import_module('bl_ext.blender_org.ucupaint')
bpy.ops.wm.open_mainfile(filepath=str(Path(sys.argv[sys.argv.index('--')+1])))
report={}
for name in ['C03 | nylon_olive','C03 | denim','balaclava_cotton_olive']:
    mat=bpy.data.materials.get(name)
    if not mat:continue
    group=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree=group.node_tree
    data={'diffuse':list(mat.diffuse_color),'links':[(l.from_node.name,l.from_socket.name,l.to_node.name,l.to_socket.name) for l in mat.node_tree.links],'layers':[]}
    for ly in tree.yp.layers:
        record={'name':ly.name,'enabled':ly.enable,'intensity':M.U.common.get_entity_prop_value(ly,'intensity_value'),'masks':[],'channels':[]}
        for root,ch in zip(tree.yp.channels,ly.channels):
            record['channels'].append({'root':root.name,'enabled':ch.enable,'override':ch.override,'value':list(ch.override_color) if root.type=='RGB' else ch.override_value})
        for mask in ly.masks:
            node=M.U.common.get_mask_source(mask)
            record['masks'].append({'name':mask.name,'type':mask.type,'enabled':mask.enable,'socket_input_name':mask.socket_input_name,'source':node.bl_idname if node else None,
                'attribute':getattr(node,'attribute_name',None) if node else None,'vcol':getattr(node,'layer_name',None) if node else None,'inputs':{s.name:s.default_value for s in node.inputs if hasattr(s,'default_value') and isinstance(s.default_value,(str,float,int))} if node else {}})
        data['layers'].append(record)
    report[name]=data
out=Path(sys.argv[sys.argv.index('--')+1]).parent/'material_probe.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('C03_MATERIAL_PROBE '+str(out),flush=True)
