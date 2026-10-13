"""Native editable PM material authoring on the accepted v11 geometry."""
from pathlib import Path
import sys,importlib,importlib.util,json,math
import bpy,addon_utils,numpy as np
from mathutils import Color,Vector
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing'
SOURCE=ROOT/'approved/PM_Geometry_v11_APPROVED.blend';UV='PMWearUV'
SKILL=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing')
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'study'
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint')
spec=importlib.util.spec_from_file_location('pm_ucupaint_helpers',SKILL/'scripts/ucupaint_helpers.py');H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.context.scene;S.frame_set(1);rig=bpy.data.objects['PM_CONTROLS • select me']
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[key]=0.
bpy.context.view_layer.update()

def visible_part(o):
 return o.type=='MESH' and not(o.get('PM engraving helper') or o.get('PM geometry helper')) and not o.name.startswith(('Animation','Reference','Studio','Safety wear'))
def activate(o,slot=0):
 for p in bpy.context.selected_objects:p.select_set(False)
 o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o;o.active_material_index=slot
def coordinates(o):
 me=o.data;co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co);mw=np.array(o.matrix_world,dtype=np.float32);world=co.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]
 return world
def author_coordinates(o):
 me=o.data;world=coordinates(o)*1000;idx=np.empty(len(me.loops),dtype=np.int32);me.loops.foreach_get('vertex_index',idx)
 uv=me.uv_layers.get(UV) or me.uv_layers.new(name=UV)
 # Shared physical projection for local image masks; original UV remains intact.
 vals=np.column_stack(((world[idx,0]+82)/166,world[idx,2]/175)).astype(np.float32);uv.data.foreach_set('uv',vals.ravel())
 x,y,z=world.T
 if o.name.startswith('Frame |'):contact=.05+.65*np.exp(-((x-63)/22)**2-((z-89)/23)**2)+.30*np.exp(-((x+61)/14)**2-((z-108)/15)**2)
 elif o.name.startswith('Slide |'):contact=.03+.48*np.exp(-((x-35)/24)**2-((z-108)/14)**2)+.5*np.exp(-((x+66)/13)**2-((z-109)/15)**2)
 elif o.name.startswith(('Hammer |','Safety |','Trigger |','MagCatch |','Slide catch |')):contact=np.full(len(world),.8)
 elif 'fastener' in o.name or 'screw' in o.name:contact=np.full(len(world),.25)
 else:contact=np.full(len(world),.1)
 attr=me.color_attributes.get('PM_HandContact') or me.color_attributes.new(name='PM_HandContact',type='BYTE_COLOR',domain='POINT')
 rgba=np.ones((len(world),4),dtype=np.float32);rgba[:,:3]=np.clip(contact[:,None],0,1);attr.data.foreach_set('color',rgba.ravel());me.update()

def stack(name,ob,color,metal,rough):
 m=bpy.data.materials.new(name);m.use_nodes=True;p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 ob.data.materials.append(m);activate(ob,len(ob.data.materials)-1)
 bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=name+' • UCUPaint',color=True,metallic=True,roughness=True,normal=True,ao=False,switch_to_material_view=False,target_bsdf_name=p.name)
 group=next(n for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node);tree=group.node_tree
 normal=next(c for c in tree.yp.channels if c.type=='NORMAL');normal.enable_smooth_bump=False;normal.main_uv=UV
 # Temporary slot is removed; callers assign the finished material explicitly.
 ob.data.materials.pop(index=len(ob.data.materials)-1)
 m['authoring']='Native UCUPaint '+U.common.get_current_version_str();return m,tree,p
def layer(tree,name,color=None,metal=None,rough=None,height=None,kind='COLOR',scale=1000,amount=1.,distance=.000004,stretch=(1,1,1)):
 tree.yp.halt_update=True;l=U.Layer.add_new_layer(tree,name,kind,-1,'MIX','OVERLAY','BUMP_MAP','Object',UV,use_designated_idx=True,designated_index=0);tree.yp.halt_update=False
 values={'Color':color,'Metallic':metal,'Roughness':rough,'Normal':height}
 for root,ch in zip(tree.yp.channels,l.channels):
  val=values[root.name];ch.enable=val is not None
  if val is None:continue
  if not isinstance(val,str):ch.override=True;ch.override_type='DEFAULT';H.sync_property(U,ch,'override_color' if root.type=='RGB' else 'override_value',Color(val) if root.type=='RGB' else val)
  if root.type=='NORMAL':H.sync_property(U,ch,'bump_distance',distance);H.sync_property(U,ch,'bump_midlevel',.5)
 if kind=='NOISE':
  src=U.common.get_layer_source(l);src.inputs['Scale'].default_value=scale;src.inputs['Detail'].default_value=2.5;src.inputs['Roughness'].default_value=.6;l.scale=stretch
 H.sync_property(U,l,'intensity_value',amount);return l
def noise(l,name,scale,lo=None,hi=None,shift=(0,0,0)):
 m=U.Mask.add_new_mask(l,name,'NOISE','Object',UV);n=U.common.get_mask_tree(m).nodes[m.source];n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=2.5;n.inputs['Roughness'].default_value=.65;m.translation=shift
 if lo is not None:H.local_noise_ramp(U,m,lo,hi)
 return m
def contact(l):return U.Mask.add_new_mask(l,'Фактические места хвата и трения','VCOL','Object',UV,vcol_name='PM_HandContact')
def edge(l,radius=.0004):
 m=U.Mask.add_new_mask(l,'Локальные выпуклые кромки','EDGE_DETECT','Object',UV,edge_detect_radius=radius,hemi_use_prev_normal=False)
 importlib.import_module(U.__name__+'.MaskModifier').add_new_mask_modifier(m,'RAMP');node=U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp];node.color_ramp.elements[0].position=.025;node.color_ramp.elements[1].position=.09
 return m
def steel(ob,condition=60):
 m,t,p=stack('ПМ • '+str(condition)+' • воронёная сталь',ob,(.016,.019,.025),1,.31)
 layer(t,'00 • Воронение по обработанной стали',(.016,.019,.025),1,.31)
 layer(t,'10 • Заводское микрозерно стали — 4 мкм',height='source',kind='NOISE',scale=1550,distance=.000004)
 layer(t,'11 • Тонкие направленные следы обработки',height='source',kind='NOISE',scale=2300,distance=.000002,stretch=(.35,1,5),amount=.45)
 l=layer(t,'12 • Неодинаковая заводская шероховатость',rough=.42,amount=.22);noise(l,'Плавная микро-вариация',260)
 if condition<100:
  l=layer(t,'20 • Полировка контактов — сохранённое воронение',(.040,.046,.055),1,.24,amount=.75);contact(l);noise(l,'Неравномерное трение',105,.45,.66)
  l=layer(t,'21 • Локальная потёртость до стали',(.27,.29,.32),1,.3,height=.47,distance=.000008,amount=.75);contact(l);noise(l,'Раздельные очаги потёртости',155,.61,.78)
  l=layer(t,'22 • Малые сколы выпуклых кромок',(.38,.40,.43),1,.25,height=.46,distance=.00001,amount=.8);edge(l);contact(l);noise(l,'Рваная граница кромки',1800,.47,.70)
 H.reconnect(U,t);return m

parts=[o for o in bpy.data.objects if visible_part(o)]
steel_parts=[o for o in parts if any(m and m.name=='Check | satin neutral metal' for m in o.data.materials)]
for o in steel_parts:author_coordinates(o)
frame=bpy.data.objects['Frame | traced flowing silhouette'];m=steel(frame)
for o in steel_parts:
 for i,old in enumerate(o.data.materials):
  if old and old.name=='Check | satin neutral metal':o.data.materials[i]=m
rig['condition_percent']=60;rig['Texture stage']='Material study before full authoring'
for o in bpy.context.selected_objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_extras=False;a.spaces.active.overlay.show_relationship_lines=False
bpy.ops.file.pack_all();path=ROOT/'work/PM_MaterialStudy.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
print('PM_MATERIAL_STUDY_SAVED',path,len(steel_parts),flush=True)
