"""Fresh-file geometry/rig, native UCUPaint, and dependency checks for PM PBR."""
from pathlib import Path
import sys, importlib, importlib.util, json, math, hashlib
import numpy as np
import bpy, addon_utils
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing'
SKILL=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing')
ARGV=sys.argv[sys.argv.index('--')+1:];FILE=Path(ARGV[0]).resolve()
REPORT=Path(ARGV[1]).resolve() if len(ARGV)>1 else ROOT/'checks'/(FILE.stem+'_validation.json')
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint')
spec=importlib.util.spec_from_file_location('pm_source_audit',SKILL/'scripts/audit_source.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)

def serial(v):
 if isinstance(v,bpy.types.ID):return {'id':v.name_full,'type':v.bl_rna.identifier}
 if isinstance(v,(str,int,float,bool)) or v is None:return v
 try:return list(v)
 except TypeError:return str(v)

def mod_settings(o):
 result=[]
 for m in o.modifiers:
  params={}
  for p in m.bl_rna.properties:
   if p.is_readonly or p.identifier in {'rna_type'}:continue
   if p.type=='COLLECTION':continue
   try:params[p.identifier]=serial(getattr(m,p.identifier))
   except (TypeError,AttributeError):continue
  result.append(params)
 return result

def driver_data(id):
 ad=id.animation_data
 if not ad:return None
 return dict(action=ad.action.name if ad.action else None,
  drivers=[dict(path=d.data_path,index=d.array_index,type=d.driver.type,expression=d.driver.expression,
   variables=[dict(name=v.name,type=v.type,targets=[dict(id=t.id.name_full if t.id else None,path=t.data_path,bone=t.bone_target,transform=t.transform_type,space=t.transform_space,rotation=t.rotation_mode) for t in v.targets]) for v in d.driver.variables]) for d in ad.drivers])

def actions():
 result={}
 for action in bpy.data.actions:
  curves=[]
  for l in action.layers:
   for strip in l.strips:
    for bag in getattr(strip,'channelbags',[]):
     for f in bag.fcurves:
      curves.append(dict(path=f.data_path,index=f.array_index,points=[(tuple(p.co),tuple(p.handle_left),tuple(p.handle_right),p.interpolation) for p in f.keyframe_points]))
  result[action.name]=dict(curves=curves,slots=[s.identifier for s in action.slots],layers=[l.name for l in action.layers],fake=action.use_fake_user)
 return result

def extra_snapshot():
 return dict(modifiers={o.name:mod_settings(o) for o in bpy.data.objects if o.modifiers},
  animation={o.name:driver_data(o) for o in bpy.data.objects if o.animation_data},
  actions=actions(),
  keys={o.name:[(k.name,hashlib.sha256(np.asarray([tuple(v.co) for v in k.data],dtype=np.float32).tobytes()).hexdigest()) for k in o.data.shape_keys.key_blocks] for o in bpy.data.objects if o.type=='MESH' and o.data.shape_keys},
  custom_normals={o.name:bool(o.data.has_custom_normals) for o in bpy.data.objects if o.type=='MESH'})

reference=ROOT/'approved/PM_Geometry_v11_APPROVED.blend'
original=A.snapshot(reference);original_extra=extra_snapshot()
final=A.snapshot(FILE);final_extra=extra_snapshot()
changes={n:[k for k in rec if final['objects'].get(n,{}).get(k)!=rec[k]] for n,rec in original['objects'].items() if final['objects'].get(n)!=rec}
added=sorted(set(final['objects'])-set(original['objects']))
extra_changes=[k for k in original_extra if original_extra[k]!=final_extra[k]]
rig=bpy.data.objects['PM_CONTROLS • select me'];condition=int(rig['condition_percent'])
errors=list(final['dependency_errors']);native=[]
authoring=json.loads((ROOT/'checks'/f'authoring_{condition}.json').read_text(encoding='utf-8'))
for name in authoring['materials']:
 m=bpy.data.materials.get(name)
 groups=[n for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node] if m else []
 if len(groups)!=1:errors.append(f'{name}: no single native UCUPaint group');continue
 group=groups[0];t=group.node_tree;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 wired={key:bool(p.inputs[key].links) and p.inputs[key].links[0].from_node==group for key in ('Base Color','Metallic','Roughness','Normal')}
 if not all(wired.values()):errors.append(f'{name}: root shader wiring {wired}')
 if [(c.name,c.type) for c in t.yp.channels]!=[('Color','RGB'),('Metallic','VALUE'),('Roughness','VALUE'),('Normal','NORMAL')]:errors.append(f'{name}: incorrect native channels')
 layers=[]
 for l in t.yp.layers:
  actual=U.common.get_entity_prop_value(l,'intensity_value')
  if not math.isfinite(actual) or abs(actual-l.intensity_value)>1.e-6:errors.append(f'{name}/{l.name}: intensity input mismatch')
  channels={}
  for root,ch in zip(t.yp.channels,l.channels):
   if not ch.enable:continue
   row=dict(enabled=True,override=ch.override)
   if ch.override:
    key='override_color' if root.type=='RGB' else 'override_value'
    got=U.common.get_entity_prop_value(ch,key)
    got=list(got)[:3] if root.type=='RGB' else float(got)
    wanted=list(ch.override_color) if root.type=='RGB' else float(ch.override_value)
    if not np.allclose(got,wanted,atol=1.e-6):errors.append(f'{name}/{l.name}/{root.name}: override mismatch')
    row['value']=got
   if root.type=='NORMAL':
    row['distance_m']=float(U.common.get_entity_prop_value(ch,'bump_distance'))
    row['midpoint']=float(U.common.get_entity_prop_value(ch,'bump_midlevel'))
   channels[root.name]=row
  masks=[]
  for mask in l.masks:
   row=dict(name=mask.name,type=mask.type,enable=mask.enable,uv=mask.uv_name,modifiers=[m.type for m in mask.modifiers])
   if mask.type=='IMAGE':
    im=U.common.get_mask_tree(mask).nodes[mask.source].image
    row.update(image=im.name,input=mask.socket_input_name,color_space=im.colorspace_settings.name)
    if not im.packed_file or im.colorspace_settings.name!='Non-Color' or mask.socket_input_name!='Color':errors.append(f'{name}/{l.name}: image mask must use packed Non-Color luminance')
   if mask.type=='MODIFIER' and mask.modifier_type=='RAMP':errors.append(f'{name}/{l.name}: threshold of accumulated masks')
   masks.append(row)
  layers.append(dict(name=l.name,type=l.type,enable=l.enable,intensity=actual,channels=channels,masks=masks))
 native.append(dict(name=name,group=t.name,channels=[c.name for c in t.yp.channels],wired=wired,layers=layers))

for row in final['images']:
 if not row['packed']:errors.append(f"{row['name']}: image is not packed")
 if row['name'].startswith('PM_') and row['color_space']!='Non-Color':errors.append(f"{row['name']}: wrong data color space")
package_manifest=FILE.parent.parent/'texture_manifest.json'
if package_manifest.exists():
 manifest=json.loads(package_manifest.read_text(encoding='utf-8'))
 for row in [r for r in manifest['images'] if r['condition']==condition]:
  im=bpy.data.images.get(row['datablock']);external=package_manifest.parent/row['file']
  resolved=Path(bpy.path.abspath(im.filepath)).resolve()
  if not im.filepath.startswith('//') or resolved!=external.resolve() or not external.is_file():
   errors.append(f"{row['datablock']}: external relative copy is not resolvable")
  elif hashlib.sha256(external.read_bytes()).hexdigest()!=row['sha256'] or hashlib.sha256(bytes(im.packed_file.data)).hexdigest()!=row['sha256']:
   errors.append(f"{row['datablock']}: packed/external hash mismatch")
  if im.colorspace_settings.name!=row['color_space']:errors.append(f"{row['datablock']}: color space changed in delivery")
 for row in [r for r in manifest['fonts'] if r['condition']==condition]:
  font=bpy.data.fonts[row['datablock']];external=package_manifest.parent/row['file']
  if Path(bpy.path.abspath(font.filepath)).resolve()!=external.resolve() or not external.is_file() or hashlib.sha256(bytes(font.packed_file.data)).hexdigest()!=row['sha256']:
   errors.append(f"{font.name}: font copy mismatch")
if rig.animation_data and rig.animation_data.action:errors.append('Demonstration Action is assigned to manual controls')
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):
 if abs(rig[key])>1.e-7:errors.append('Control not at rest: '+key)
if condition==100:
 for mat in native:
  for l in mat['layers']:
   if any(mask['enable'] and mask['type']=='IMAGE' for mask in l['masks']):errors.append('100% has exploitation image mask')
glass=bpy.data.objects['Reflex | K1 curved aspheric lens'].data.materials[0]
gp=next(n for n in glass.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
optics={k:gp.inputs[k].default_value for k in ('Transmission Weight','IOR','Coat Weight','Thin Film Thickness','Thin Film IOR')}
if optics['Transmission Weight']!=1 or optics['IOR']<1.4:errors.append('Glass transmission setup is invalid')
report=dict(condition=condition,file=str(FILE),source_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
 native_version=U.common.get_current_version_str(),geometry_changes=changes,added_objects=added,
 modifier_driver_action_shape_key_changes=extra_changes,reference_objects=len(original['objects']),
 candidate_objects=len(final['objects']),images=final['images'],native_materials=native,optics=optics,errors=errors,
 deferred_geometry=rig.get('Deferred geometry'),
 pass_checks=not(changes or added or extra_changes or errors),
 limits='Visual masking, reflected glass and appearance checked in working stills; game import is not part of this stage.')
REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_PBR_VALIDATION',condition,report['pass_checks'],len(native),'native materials;',len(final['images']),'packed images;',len(changes),'geometry changes;',extra_changes,'rig/modifier changes;',errors,flush=True)
if not report['pass_checks']:raise RuntimeError('PM PBR validation failed: '+str(REPORT))
