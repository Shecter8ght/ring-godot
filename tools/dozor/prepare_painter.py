"""Painter authoring copy: continuous lathe UVs, packed sets, flat marking masks.
No game mesh simplification or export; editable accepted sources are preserved.
"""
import bpy,bmesh,math,json,pathlib,hashlib
import numpy as np
from mathutils import Vector
ROOT=pathlib.Path('E:/Games/RING-godot')
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
WORK=ROOT/'_asset_src/dozor/painter'
WORK.mkdir(parents=True,exist_ok=True)
(OUT/'painter').mkdir(exist_ok=True)
(OUT/'textures/factory').mkdir(parents=True,exist_ok=True)
sc=bpy.context.scene
sc.render.engine='CYCLES';sc.cycles.samples=1;sc.cycles.bake_type='EMIT'
sc.render.bake.use_clear=True;sc.render.bake.margin=4
UV='PainterUV'
base=bpy.data.collections['01 • ДОЗОР Ф-1 • master shape']
mount=bpy.data.collections['04 • ДОЗОР-П • independent Picatinny mount']
sets={'DOZOR_F1':[],'DOZOR_P':[],'DOZOR_LENS':[]}
for c in (base,mount):
 for o in c.all_objects:
  if o.type=='MESH':
   key='DOZOR_LENS' if '.solid_glass' in o.name else 'DOZOR_P' if c==mount else 'DOZOR_F1'
   sets[key].append(o)

def select(objects):
 if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.hide_set(False);o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0]

def cylinder_uv(ob):
 me=ob.data
 for n in (128,192,64):
  if len(me.vertices)%n or len(me.vertices)<n*3 or len(me.polygons)!=len(me.vertices):continue
  if set(me.polygons[0].vertices)!=set([0,1,n,n+1]):continue
  if any(len(f.vertices)!=4 for f in me.polygons):continue
  count=len(me.vertices)//n
  pts=np.array([tuple(v.co) for v in me.vertices]).reshape(count,n,3)
  rr=np.mean(np.linalg.norm(pts[:,:,:2],axis=2),axis=1)
  zz=np.mean(pts[:,:,2],axis=1)
  dist=np.sqrt(np.diff(rr)**2+np.diff(zz)**2)
  chain=np.r_[0,np.cumsum(dist)]
  total=chain[-1]+math.hypot(rr[-1]-rr[0],zz[-1]-zz[0])
  circumference=math.tau*float(np.mean(rr))
  uv=me.uv_layers.get(UV) or me.uv_layers.new(name=UV)
  for face in me.polygons:
   rings=[v//n for v in face.vertices];angles=[v%n for v in face.vertices]
   seam_u=max(angles)-min(angles)>n/2;seam_v=max(rings)-min(rings)>count/2
   for li,vi in zip(face.loop_indices,face.vertices):
    j,i=divmod(vi,n)
    u=(1 if seam_u and i==0 else i/n)*circumference
    v=total if seam_v and j==0 else chain[j]
    uv.data[li].uv=(u,v)
  me.uv_layers.active=uv;uv.active_render=True
  return True
 return False

generic=[]
for objects in sets.values():
 for ob in objects:
  if not cylinder_uv(ob):
   if not ob.data.uv_layers.get(UV):ob.data.uv_layers.new(name=UV)
   ob.data.uv_layers.active=ob.data.uv_layers[UV];ob.data.uv_layers[UV].active_render=True
   generic.append(ob)
if generic:
 select(generic);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
 bpy.ops.uv.smart_project(angle_limit=math.radians(60),island_margin=.003)
 bpy.ops.object.mode_set(mode='OBJECT')
report={}
for name,objects in sets.items():
 select(objects);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
 bpy.ops.uv.select_all(action='SELECT');bpy.ops.uv.average_islands_scale()
 bpy.ops.uv.pack_islands(rotate=True,margin=.003)
 bpy.ops.object.mode_set(mode='OBJECT')
 a3=a2=0
 for ob in objects:
  me=ob.data;me.calc_loop_triangles();uv=me.uv_layers[UV]
  for tri in me.loop_triangles:
   pts=[uv.data[i].uv for i in tri.loops]
   a2+=abs((pts[1]-pts[0]).cross(pts[2]-pts[0]))*.5
   a3+=tri.area
 report[name]={'mesh_count':len(objects),'uv_area':a2,'surface_mm2':a3*1e6,'px_per_mm_2K':2048*math.sqrt(a2/max(a3,1e-12))/1000}
 print('UV',name,report[name],flush=True)

# Preserve original scene with editable topology plus authoring UVs.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'models/DOZOR_Painter_UV_v01.blend'))

# Temporary evaluated clones for bake and Painter, never written over the high-poly master.
coll=bpy.data.collections.new('Painter evaluated source');sc.collection.children.link(coll)
clones={};original_materials={}
dg=bpy.context.evaluated_depsgraph_get()
for name,objects in sets.items():
 clones[name]=[]
 for ob in objects:
  me=bpy.data.meshes.new_from_object(ob.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
  # Painter uses the first UV channel. Primitive spheres retain a legacy UVMap
  # spanning the full atlas, so export only the packed authoring channel.
  for layer in list(me.uv_layers):
   if layer.name!=UV:me.uv_layers.remove(layer)
  me.uv_layers.active_index=0;me.uv_layers[0].active_render=True
  new=bpy.data.objects.new(ob.name+'__paint',me);coll.objects.link(new);new.matrix_world=ob.matrix_world.copy()
  me.materials.clear()
  for slot in ob.material_slots:me.materials.append(slot.material)
  clones[name].append(new);original_materials[new.name]=list(me.materials)
for c in list(sc.collection.children):
 if c!=coll:c.hide_render=True

def emission(name,source=None):
 m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
 out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission')
 nt.links.new(em.outputs[0],out.inputs['Surface']);em.inputs['Color'].default_value=(0,0,0,1)
 if source:
  coord=nt.nodes.new('ShaderNodeTexCoord');g=nt.nodes.new('ShaderNodeGroup');g.node_tree=source
  g.inputs['Цвет корпуса'].default_value=(0,0,0,1);g.inputs['Цвет надписи'].default_value=(1,1,1,1)
  nt.links.new(coord.outputs['Object'],g.inputs['Координаты детали']);nt.links.new(g.outputs[0],em.inputs['Color'])
 return m

black=emission('Bake black')
def bake_marks(setname,variant):
 objects=[o for o in clones[setname] if '.Head.hollow_faceted_housing' in o.name or o.name.startswith('P.Ring.upper_cap')]
 res=4096 if setname=='DOZOR_F1' else 2048
 im=bpy.data.images.new(setname+'_'+variant,res,res,alpha=False)
 im.colorspace_settings.name='Non-Color'
 mats=[]
 for ob in objects:
  src=None
  if '.Head.hollow_faceted_housing' in ob.name:
   mat=bpy.data.objects[variant+'.Head.hollow_faceted_housing'].material_slots[0].material
   src=next(n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP')
  elif ob.name.startswith('P.Ring.upper_cap'):
   mat=original_materials[ob.name][0];src=next(n.node_tree for n in mat.node_tree.nodes if n.type=='GROUP')
  mat=emission('Bake '+ob.name,src) if src else black
  ob.data.materials.clear();ob.data.materials.append(mat);mats.append(mat)
 for mat in set(mats):
  node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=im;mat.node_tree.nodes.active=node
 select(objects);bpy.ops.object.bake(type='EMIT')
 path=WORK/(setname+'_'+variant+'_mark.png');im.filepath_raw=str(path);im.file_format='PNG';im.save()
 print('MARK MASK',path,flush=True)
for variant in ('F1','F1M','F1S'):bake_marks('DOZOR_F1',variant)
bake_marks('DOZOR_P','P')

# One Painter texture set per material; mesh names are stable for geometry masks.
for name,objects in clones.items():
 mat=bpy.data.materials.new(name)
 for ob in objects:
  ob.data.materials.clear();ob.data.materials.append(mat)
select([o for objects in clones.values() for o in objects])
fbx=OUT/'painter'/'DOZOR_authoring.fbx'
bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},
    add_leaf_bones=False,bake_anim=False,mesh_smooth_type='FACE',use_custom_props=False,
    axis_forward='-Y',axis_up='Z',global_scale=1.0)
meshmap={}
spec=json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))
for slot in spec['slots']:
 meshmap[slot['id']]={name:[o.name for o in objects if o.name.removesuffix('__paint') in slot['parts']] for name,objects in clones.items()}
(WORK/'painter_meshes.json').write_text(json.dumps({'sets':report,'slots':meshmap,'fbx':str(fbx)},ensure_ascii=False,indent=2),encoding='utf-8')
print('PAINTER INPUT READY',fbx,flush=True)
