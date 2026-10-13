from pathlib import Path
import bpy, addon_utils, importlib, json
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint')
root=Path(__file__).resolve().parents[1]/'_asset_src/pm_texturing'
bpy.ops.wm.open_mainfile(filepath=str(root/'approved/PM_Geometry_v11_APPROVED.blend'))
m=bpy.data.materials['КОРС-9 • светлая краска в клеймах']
out=[]
for n in m.node_tree.nodes:
 if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node:
  t=n.node_tree
  print('PM_PAINT_CHANNELS',[(c.name,c.type) for c in t.yp.channels])
  for l in t.yp.layers:
   row=dict(name=l.name,type=l.type,enable=l.enable,texcoord_type=l.texcoord_type,uv_name=l.uv_name,intensity=l.intensity_value,channels=[dict(enable=c.enable,override=c.override,value=c.override_value,color=list(c.override_color)) for c in l.channels],masks=[])
   for mask in l.masks:
    src=U.common.get_mask_tree(mask).nodes.get(mask.source)
    row['masks'].append(dict(name=mask.name,type=mask.type,enable=mask.enable,uv_name=mask.uv_name,source=src.bl_idname if src else None,image=src.image.name if src and hasattr(src,'image') and src.image else None,modifiers=[(x.type,x.ramp) for x in mask.modifiers]))
   out.append(row)
(root/'work/paint_layers.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_PAINT_LAYERS',out,flush=True)
