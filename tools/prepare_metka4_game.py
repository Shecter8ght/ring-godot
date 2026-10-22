"""Accepted METKA-4 retopology -> two independent game mounts and a skinned cable.

Blender --background --factory-startup --python-exit-code 1 --python tools/prepare_metka4_game.py -- export
Python tools/prepare_metka4_game.py imports  (after Godot's first --import)
"""
from pathlib import Path
import sys,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/models/attachments/metka4';WORK=ROOT/'_asset_src/metka4_game'
SRC=Path('E:/Models Blender/VEYR_METKA-4/Модели/МЕТКА-4_v01_ретопология.blend');SHA='38c5187ba84ad56845de751499462f86f94c2be8034d37eaab9fa33f539675c5'
def imports():
 for f in OUT.glob('*.png.import'):
  s=f.read_text(encoding='utf-8').replace('compress/mode=0','compress/mode=2').replace('mipmaps/generate=false','mipmaps/generate=true').replace('detect_3d/compress_to=1','detect_3d/compress_to=0')
  if '_normal.png' in f.name:s=s.replace('compress/normal_map=0','compress/normal_map=1')
  f.write_text(s,encoding='utf-8')
 print('METKA4_IMPORTS_CONFIGURED')
def export():
 import bpy
 from mathutils import Matrix,Vector
 assert hashlib.sha256(SRC.read_bytes()).hexdigest()==SHA,'Accepted source changed'
 OUT.mkdir(parents=True,exist_ok=True);WORK.mkdir(parents=True,exist_ok=True)
 bpy.ops.wm.open_mainfile(filepath=str(SRC));bpy.context.view_layer.update()
 main=bpy.data.objects['Main_Mount'];remote=bpy.data.objects['Remote_Mount'];kit=bpy.data.objects['METKA4_Kit'];cable=bpy.data.objects['LP_Remote_cable'];rig=bpy.data.objects['CableRig']
 main['release']=0;main.update_tag();bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
 for b in rig.pose.bones:
  for c in list(b.constraints):b.constraints.remove(c)
  b.matrix_basis=Matrix.Identity(4)
 for o in list(bpy.context.scene.objects):
  if o.animation_data:o.animation_data_clear()
 bpy.context.view_layer.update()
 main_origin=main.matrix_world.translation.copy()
 meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('LP_')]
 def parent_keep(o,p):
  w=o.matrix_world.copy();o.parent=p;o.matrix_world=w
 def under(o,p):
  while o:
   if o==p:return True
   o=o.parent
  return False
 groups={}
 for o in meshes:
  if o==cable:continue
  if o.name=='LP_Protective_window':group='Main_Window'
  elif o.name.startswith('LP_Emitter_lens'):group='Main_Lenses'
  elif under(o,remote):group='Remote_Body'
  else:group='Main_Body' if o['atlas']=='main' else 'Main_Details'
  groups.setdefault(group,[]).append(o)
 keep={kit,main,remote,cable,rig};counts={}
 for label,obs in groups.items():
  bpy.ops.object.select_all(action='DESELECT')
  for o in obs:o.hide_set(False);o.select_set(True);parent_keep(o,None)
  bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();o=bpy.context.object;o.name=label;o['source_parts']=[x['hp_source'] for x in obs if x.name in bpy.data.objects] if len(obs)==1 else label
  parent_keep(o,remote if label.startswith('Remote') else main);o['atlas']='remote' if label.startswith('Remote') else 'main' if label=='Main_Body' else 'details';keep.add(o)
  o.data.calc_loop_triangles();counts[label]=len(o.data.loop_triangles)
 for name in ['Cable_Start','Cable_End']:
  o=bpy.data.objects[name];keep.add(o);parent_keep(o,main if name=='Cable_Start' else remote)
 parent_keep(rig,kit);parent_keep(cable,rig);cable.name='Cable';keep.add(cable)
 emitter=bpy.data.objects.new('Laser_Emitter',None);bpy.context.collection.objects.link(emitter);emitter.matrix_world=Matrix.Translation((.04085,-.0149,.0159));parent_keep(emitter,main);keep.add(emitter)
 for o in list(bpy.context.scene.objects):
  if o not in keep:bpy.data.objects.remove(o,do_unlink=True)
 parent_keep(main,kit);parent_keep(remote,kit)
 bpy.context.view_layer.update();worlds={o:o.matrix_world.copy() for o in keep}
 xf=Matrix(((0,1,0,0),(0,0,1,0),(1,0,0,0),(0,0,0,1)));inv=xf.inverted();shift=Matrix.Translation(-(xf@main_origin))
 for o in keep:
  if o.type=='MESH':o.data.transform(xf);o.data.update()
  elif o.type=='ARMATURE':o.data.transform(xf)
 kit.matrix_world=Matrix.Identity(4)
 # Parent-first assignment keeps both mount frames in project axes (+Z muzzle,+Y out).
 order=[main,remote,rig,cable]+[o for o in keep if o not in [kit,main,remote,rig,cable]]
 for o in order:o.matrix_world=shift@xf@worlds[o]@inv
 bpy.context.view_layer.update()
 for o in keep:
  if o.type=='MESH':
   for a in list(o.data.color_attributes):o.data.color_attributes.remove(a)
   o.data.calc_loop_triangles();counts[o.name]=len(o.data.loop_triangles)
 # Geometry-only glTF; three reusable game materials load their external atlases.
 bpy.ops.object.select_all(action='DESELECT')
 for o in keep:o.hide_set(False);o.select_set(True)
 bpy.context.view_layer.objects.active=main
 bpy.ops.export_scene.gltf(filepath=str(OUT/'metka4.glb'),export_format='GLB',use_selection=True,export_yup=False,export_animations=False,export_materials='PLACEHOLDER',export_normals=True,export_tangents=True,export_texcoords=True,export_skins=True,export_extras=True)
 for f in (SRC.parents[1]/'Текстуры/МЕТКА-4_ретопология_v01').glob('*.png'):shutil.copy2(f,OUT/f.name)
 records={name:{'matrix':[list(r) for r in bpy.data.objects[name].matrix_world]} for name in ['Main_Mount','Remote_Mount','CableRig','Cable_Start','Cable_End','Laser_Emitter']}
 optical={}
 for name in ['Main_Lenses','Main_Window']:
  optical[name]=[]
  for mat in bpy.data.objects[name].data.materials:
   bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
   optical[name].append({'name':mat.name,'color':list(bs.inputs['Base Color'].default_value),'roughness':float(bs.inputs['Roughness'].default_value),'metallic':float(bs.inputs['Metallic'].default_value),'transmission':float(bs.inputs['Transmission Weight'].default_value)})
 manifest={'accepted_source':str(SRC),'source_sha256':SHA,'axis':'Godot +Z muzzle,+Y out,+X left; metres','triangles':counts,'total_triangles':sum(counts.values()),'mounts_and_markers':records,'cable_bones':[b.name for b in rig.data.bones],'cable_rest_length_m':float(cable['Rest_length_m']),'materials':'main 4K, details 4K, remote 2K; external BaseColor/Roughness/Metallic/Normal','optical_materials':optical,'gameplay_id':'tac_laser_01'}
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'metka4_game_axes.blend'))
 assert hashlib.sha256(SRC.read_bytes()).hexdigest()==SHA
 print('METKA4_EXPORTED',manifest['total_triangles'],counts,flush=True)
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
if not args or args[0]=='export':export()
elif args[0]=='imports':imports()
else:raise ValueError(args)
