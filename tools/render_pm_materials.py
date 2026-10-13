"""Working stills only, plus a two-sided transmission diagnostic."""
from pathlib import Path
import sys,argparse,os,json
import bpy,addon_utils
from mathutils import Vector
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing'
ap=argparse.ArgumentParser();ap.add_argument('--file',default=str(ROOT/'work/PM_MaterialStudy.blend'));ap.add_argument('--glass',action='store_true');ap.add_argument('--full',action='store_true');ap.add_argument('--fingerprint-diagnostic',action='store_true');ap.add_argument('--views',default='left,controls,grip');args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
for sub in ('work/optix_cache','work/cuda_cache','images'):(ROOT/sub).mkdir(parents=True,exist_ok=True)
os.environ['OPTIX_CACHE_PATH']=str(ROOT/'work/optix_cache');os.environ['CUDA_CACHE_PATH']=str(ROOT/'work/cuda_cache')
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True);bpy.ops.wm.open_mainfile(filepath=args.file)
S=bpy.context.scene;S.frame_set(1);rig=bpy.data.objects['PM_CONTROLS • select me']
for k in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[k]=0.
rig.update_tag();bpy.context.view_layer.update()
sys.path.insert(0,str(PROJECT/'tools'));from pm_engraving_geometry import cache_engraving_preview
cache_engraving_preview()
for o in bpy.data.objects:
 if o.name.startswith(('Animation |','Reference')):o.hide_render=True
S.render.engine='CYCLES';S.cycles.samples=48;S.cycles.use_denoising=True
p=bpy.context.preferences.addons['cycles'].preferences
try:
 p.compute_device_type='OPTIX';p.get_devices()
 for d in p.devices:d.use=d.type!='CPU'
 if any(d.use for d in p.devices):S.cycles.device='GPU'
except Exception as e:print('PM_DEVICE',str(e),flush=True)
S.cycles.transmission_bounces=16;S.cycles.max_bounces=20
S.render.resolution_x=1400;S.render.resolution_y=1000;S.render.resolution_percentage=100;S.render.image_settings.file_format='PNG';S.render.film_transparent=False
S.view_settings.exposure=-1.0
cam=bpy.data.objects['CHECK 01 | Complete PM and separate sight'];cam.data.type='ORTHO';cam.data.clip_start=.0001;cam.data.clip_end=10;S.camera=cam

def light(name,location,energy,size,target=(0,0,.09)):
 data=bpy.data.lights.new(name,'AREA');data.energy=energy;data.shape='DISK';data.size=size
 o=bpy.data.objects.new(name,data);S.collection.objects.link(o);o.location=location;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();return o

if args.full:
 for o in bpy.data.objects:
  if o.type=='LIGHT':o.hide_render=True
 light('DIAGNOSTIC neutral key',(-.08,-.23,.31),13,.19)
 light('DIAGNOSTIC neutral fill',(.11,.16,.22),9,.16)
 light('DIAGNOSTIC grazing strip',(.05,.065,.25),5,.045)
 light('DIAGNOSTIC front reflection',(0,-.31,.125),4,.20)
 S.render.resolution_x=1600;S.render.resolution_y=1200
def view(name,eye,target,scale):
 cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;S.render.filepath=str(ROOT/'images'/name);bpy.ops.render.render(write_still=True);print('PM_MATERIAL_IMAGE',S.render.filepath,flush=True)
if args.glass:
 # Test only optical parts. The checker is never saved to the asset.
 def within(o):
  while o:
   if o.name=='PM_ReflexSight • asset root':return True
   o=o.parent
  return False
 for o in bpy.data.objects:
  if o.type=='MESH' and not within(o):o.hide_render=True
 material=bpy.data.materials.new('DIAGNOSTIC checker');material.use_nodes=True;nt=material.node_tree;nt.nodes.clear();tex=nt.nodes.new('ShaderNodeTexChecker');tex.inputs['Color1'].default_value=(.02,.2,.8,1);tex.inputs['Color2'].default_value=(.8,.5,.01,1);tex.inputs['Scale'].default_value=12
 coord=nt.nodes.new('ShaderNodeTexCoord');emit=nt.nodes.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=.7;output=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(coord.outputs['Generated'],tex.inputs['Vector']);nt.links.new(tex.outputs['Color'],emit.inputs['Color']);nt.links.new(emit.outputs[0],output.inputs['Surface'])
 bpy.ops.mesh.primitive_plane_add(size=.060,location=(-.020,0,.156));board=bpy.context.object;board.rotation_euler[1]=1.57079632679;board.data.materials.append(material)
 prefix=f"PM_{rig['condition_percent']}_" if 'condition_percent' in rig else ''
 view(prefix+'glass_front.png',(-.16,0,.156),(-.032,0,.156),.040)
 board.location.x=-.048;view(prefix+'glass_rear.png',(.095,0,.156),(-.032,0,.156),.040)
elif args.fingerprint_diagnostic:
 # Unsaved diagnostic of the actual native Roughness output, rather than a
 # claim based on an enabled layer. The scale only amplifies this QA image.
 for material in bpy.data.materials:
  if not material.use_nodes:continue
  groups=[n for n in material.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node]
  if not groups:continue
  group=groups[0]
  for l in group.node_tree.yp.layers:l.enable=l.name.startswith('00') or 'Масляные отпечатки' in l.name
  output=next(n for n in material.node_tree.nodes if n.type=='OUTPUT_MATERIAL')
  remap=material.node_tree.nodes.new('ShaderNodeMapRange');remap.inputs['From Min'].default_value=.26;remap.inputs['From Max'].default_value=.30;remap.inputs['To Min'].default_value=1;remap.inputs['To Max'].default_value=0
  emit=material.node_tree.nodes.new('ShaderNodeEmission');emit.inputs['Strength'].default_value=1.
  material.node_tree.links.new(group.outputs['Roughness'],remap.inputs['Value']);material.node_tree.links.new(remap.outputs['Result'],emit.inputs['Color']);material.node_tree.links.new(emit.outputs[0],output.inputs['Surface'])
 view('PM_60_fingerprint_diagnostic.png',(0,-.4,.095),(.021,0,.095),.175)
elif args.full:
 condition=rig.get('condition_percent','study')
 views=dict(left=((- .18,-.42,.224),(-.002,0,.083),.26),
            right=((- .19,.42,.224),(-.002,0,.083),.26),
            controls=((.104,-.135,.143),(.055,-.011,.106),.076),
            grip=((.094,-.18,.091),(.052,-.010,.043),.134),
            optic=((.055,-.094,.203),(-.016,0,.148),.084),
            underside=((.09,-.11,-.045),(.045,0,.014),.118))
 for key in args.views.split(','):
  if key=='grazing':
   for o in bpy.data.objects:
    if o.type=='LIGHT' and o.name.startswith('DIAGNOSTIC'):
     o.location.y=-o.location.y;o.rotation_euler=(Vector((.025,0,.095))-o.location).to_track_quat('-Z','Y').to_euler()
   view(f'PM_{condition}_grazing.png',(.104,-.135,.143),(.055,-.011,.106),.076)
  elif key=='underside':
   stage=bpy.data.objects['Studio | matte charcoal stage'];old=stage.hide_render;stage.hide_render=True
   under=light('DIAGNOSTIC bottom reflection',(.055,-.085,-.055),3,.07,target=(.045,0,.012))
   view(f'PM_{condition}_{key}.png',*views[key]);under.hide_render=True;stage.hide_render=old
  else:view(f'PM_{condition}_{key}.png',*views[key])
else:
 for n in ('08 • Optic mount — separate asset','09 • Reflex sight — separate asset'):bpy.data.collections[n].hide_render=True
 view('material_study_neutral.png',(.104,-.135,.143),(.055,-.011,.106),.076)
 lights=[o for o in bpy.data.objects if o.type=='LIGHT']
 for o in lights:
  o.location.y=-o.location.y;o.rotation_euler=(Vector((.025,0,.095))-o.location).to_track_quat('-Z','Y').to_euler()
 view('material_study_reverse_light.png',(.104,-.135,.143),(.055,-.011,.106),.076)
print('PM_MATERIAL_REVIEW_DONE',flush=True)
