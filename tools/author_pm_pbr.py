"""Native UCUPaint PBR on accepted PM v11; no mesh or rig changes.

Run Blender --background --factory-startup --python-exit-code 1 --python
tools/author_pm_pbr.py -- 60 (or 100 / 20). No game bake/export.
"""
from pathlib import Path
import sys, importlib, importlib.util, json, hashlib
import bpy, addon_utils, numpy as np
from mathutils import Color, Vector
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_texturing'
SOURCE=ROOT/'approved/PM_Geometry_v11_APPROVED.blend'
SKILL=Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing')
ARGV=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['60']
CONDITION=int(ARGV[0]);assert CONDITION in (100,60,20)
UV='PMWearUV';TOP='PMTopUV';LENS='LensUV'
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
U=importlib.import_module('bl_ext.blender_org.ucupaint')
spec=importlib.util.spec_from_file_location('pm_ucupaint_helpers',SKILL/'scripts/ucupaint_helpers.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)
assert U.common.get_current_version_str()=='2.4.9'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.context.scene;S.frame_set(1);rig=bpy.data.objects['PM_CONTROLS • select me']
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[key]=0.
rig.update_tag();bpy.context.view_layer.update()
FRAME=bpy.data.objects['Frame | traced flowing silhouette']
MANIFEST=json.loads((ROOT/'textures/mask_manifest.json').read_text(encoding='utf-8'))
IMAGES={};CREATED=[]

def in_parent(o,prefix):
 while o:
  if o.name.startswith(prefix):return True
  o=o.parent
 return False

def author_coordinates(o):
 """Rest-pose physical projections move with each accepted part."""
 me=o.data;co=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',co)
 mw=np.array(o.matrix_world,dtype=np.float32)
 world=(co.reshape(-1,3)@mw[:3,:3].T+mw[:3,3])*1000
 idx=np.empty(len(me.loops),dtype=np.int32);me.loops.foreach_get('vertex_index',idx)
 x,y,z=world.T
 projections=[(UV,np.column_stack(((x+82)/332+(y>=0)*.5,z/175))),
              (TOP,np.column_stack(((x+82)/166,(y+25)/50)))]
 if 'lens' in o.name.lower():projections.append((LENS,np.column_stack(((y+16)/32,(z-146)/24))))
 for name,vals in projections:
  uv=me.uv_layers.get(name) or me.uv_layers.new(name=name)
  uv.data.foreach_set('uv',np.asarray(vals[idx],dtype=np.float32).ravel())
 norm=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('normal',norm)
 # Hidden chamber/ejection props use a zero-scale visibility driver at rest.
 # Their factory-only shader needs no projected contact stamp. A pseudoinverse
 # permits attributes without changing those accepted drivers or their pose.
 norm=norm.reshape(-1,3)@np.linalg.pinv(mw[:3,:3]);norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-8)
 side=np.abs(norm[:,1])**3;top=np.maximum(norm[:,2],0)**3
 if o.name.startswith('Frame |'):
  contact=.08+.65*np.exp(-((x-64)/19)**2-((z-89)/22)**2)+.25*np.exp(-((x+48)/20)**2-((z-83)/13)**2)
 elif o.name.startswith('Slide |'):
  contact=.08+.55*np.exp(-((x-40)/27)**2-((z-109)/14)**2)+.52*np.exp(-((x+66)/15)**2-((z-107)/17)**2)
 elif o.name.startswith(('Bakelite |','Grip ')):
  contact=.30+.60*np.exp(-((x-53)/30)**2-((z-43)/37)**2)
 elif o.name.startswith(('Hammer |','Safety |','Trigger |','MagCatch |','Slide catch |')):contact=np.full(len(world),.9)
 elif 'fastener' in o.name or 'screw' in o.name or 'adjustment' in o.name:contact=np.full(len(world),.55)
 elif o.name.startswith('Magazine |'):contact=np.full(len(world),.55)
 elif 'battery' in o.name:contact=np.full(len(world),.45)
 elif o.name.startswith(('Reflex |','Mount |')):contact=np.full(len(world),.22)
 else:contact=np.full(len(world),.18)
 for name,data in (('PM_HandContact',np.clip(contact,0,1)),('PM_SideSurface',side),('PM_TopSurface',top),('PM_Protected',1-np.clip(contact,0,1)*.8)):
  a=me.color_attributes.get(name) or me.color_attributes.new(name=name,type='BYTE_COLOR',domain='POINT')
  rgba=np.ones((len(world),4),dtype=np.float32);rgba[:,:3]=data[:,None];a.data.foreach_set('color',rgba.ravel())
 me.update()

def activate(o,slot=0):
 for p in bpy.context.selected_objects:p.select_set(False)
 o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o;o.active_material_index=slot

def stack(label,color,metal,rough,uv=UV):
 name=f'ПМ • {CONDITION} • {label}';m=bpy.data.materials.new(name);m.use_nodes=True
 p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
 p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 FRAME.data.materials.append(m);activate(FRAME,len(FRAME.data.materials)-1)
 bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=name+' • UCUPaint',color=True,metallic=True,roughness=True,normal=True,ao=False,switch_to_material_view=False,target_bsdf_name=p.name)
 tree=next(n.node_tree for n in m.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node)
 normal=next(c for c in tree.yp.channels if c.type=='NORMAL');normal.enable_smooth_bump=False;normal.main_uv=uv
 FRAME.data.materials.pop(index=len(FRAME.data.materials)-1)
 m['Native UCUPaint']='2.4.9';m['condition_percent']=CONDITION;m['Accepted geometry']='PM v11, unchanged';CREATED.append(m)
 return m,tree,p

def layer(tree,name,color=None,metal=None,rough=None,height=None,kind='COLOR',scale=1000,amount=1.,distance=.000004,stretch=(1,1,1)):
 tree.yp.halt_update=True
 l=U.Layer.add_new_layer(tree,name,kind,-1,'MIX','OVERLAY','BUMP_MAP','Object',UV,use_designated_idx=True,designated_index=0)
 tree.yp.halt_update=False;values={'Color':color,'Metallic':metal,'Roughness':rough,'Normal':height}
 for root,ch in zip(tree.yp.channels,l.channels):
  val=values[root.name];ch.enable=val is not None
  if val is None:continue
  if not isinstance(val,str):
   ch.override=True;ch.override_type='DEFAULT'
   H.sync_property(U,ch,'override_color' if root.type=='RGB' else 'override_value',Color(val) if root.type=='RGB' else val)
  if root.type=='NORMAL':H.sync_property(U,ch,'bump_distance',distance);H.sync_property(U,ch,'bump_midlevel',.5)
 if kind=='NOISE':
  src=U.common.get_layer_source(l);src.inputs['Scale'].default_value=scale;src.inputs['Detail'].default_value=2.5;src.inputs['Roughness'].default_value=.6;l.scale=stretch
 H.sync_property(U,l,'intensity_value',amount);return l

def noise(l,name,scale,lo=None,hi=None,shift=None):
 m=U.Mask.add_new_mask(l,name,'NOISE','Object',UV)
 n=U.common.get_mask_tree(m).nodes[m.source];n.inputs['Scale'].default_value=scale;n.inputs['Detail'].default_value=2.5;n.inputs['Roughness'].default_value=.65
 m.translation=shift if shift is not None else ((.17,.06,.03) if CONDITION==20 else (0,0,0))
 if lo is not None:H.local_noise_ramp(U,m,lo,hi)
 return m

def vmask(l,name):return U.Mask.add_new_mask(l,name,'VCOL','Object',UV,vcol_name=name)

def edge(l,radius=None):
 m=U.Mask.add_new_mask(l,'Выпуклые кромки принятой геометрии','EDGE_DETECT','Object',UV,edge_detect_radius=radius or (.00075 if CONDITION==20 else .00032),hemi_use_prev_normal=False)
 MM=importlib.import_module(U.__name__+'.MaskModifier');MM.add_new_mask_modifier(m,'RAMP')
 n=U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp]
 n.color_ramp.elements[0].position=.02;n.color_ramp.elements[1].position=.10;return m

def image_mask(l,kind,projection='side'):
 key=(projection,kind)
 if key not in IMAGES:
  row=next(r for r in MANIFEST['images'] if r['condition']==CONDITION and r['projection']==projection and r['purpose']==kind)
  path=ROOT/row['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
  im=bpy.data.images.load(str(path),check_existing=True);im.name=f'PM_{CONDITION}_{projection}_{kind}';im.colorspace_settings.name='Non-Color';IMAGES[key]=im
 m=U.Mask.add_new_mask(l,f'{kind} • собственные локальные маски','IMAGE','UV',{'side':UV,'top':TOP,'lens':LENS}[projection],image=IMAGES[key],socket_input_name='Color')
 U.common.get_mask_tree(m).nodes[m.source].extension='CLIP'
 if projection!='lens':vmask(l,'PM_SideSurface' if projection=='side' else 'PM_TopSurface')
 return m

def local_layer(t,label,kind,color=None,metal=None,rough=None,height=None,amount=1.,distance=.000004,projection='side',protected=False):
 l=layer(t,label,color,metal,rough,height,amount=amount,distance=distance);image_mask(l,kind,projection)
 if protected:vmask(l,'PM_Protected')
 return l

def factory(t,rough,grain=3.e-6):
 layer(t,'10 • Мелкое заводское зерно',height='source',kind='NOISE',scale=1800,distance=grain)
 layer(t,'11 • Направленные следы обработки',height='source',kind='NOISE',scale=2900,distance=grain*.5,stretch=(.18,1,5),amount=.38)
 l=layer(t,'12 • Микроразличие шероховатости',rough=min(rough+.10,.8),amount=.22);noise(l,'Структура материала 0,2–0,6 мм',230)

def handling(t,substrate,metal=1,rough=.3,plastic=False):
 if CONDITION==100:return
 heavy=CONDITION==20
 l=layer(t,'20 • Полировка фактического хвата',rough=max(.14,rough-.10),amount=.78 if heavy else .38)
 vmask(l,'PM_HandContact');noise(l,'Неполная контактная полировка',90)
 l=local_layer(t,'21 • Отдельные потёртости покрытия','rub',substrate,metal,rough,.48,.92 if heavy else .5,distance=.000012 if heavy else .000006)
 vmask(l,'PM_HandContact');noise(l,'Разрыв границ потёртости',1800,.26,.47)
 l=layer(t,'22 • Снятый верхний слой на кромках',substrate,metal,rough,height=.47,amount=.94 if heavy else .52,distance=.000018 if heavy else .000007)
 edge(l);vmask(l,'PM_HandContact');noise(l,'Раздельные малые очаги',1400,.43 if heavy else .51,.63 if heavy else .72)
 local_layer(t,'23 • Локальные царапины от обращения','scratches',substrate,metal,min(.57,rough+.11),
             .18 if plastic and heavy else .40,.8 if heavy else .38,
             distance=.00009 if plastic and heavy else (.000024 if heavy else .000006))
 for projection in ('side','top'):
  local_layer(t,'30 • Масляные отпечатки — '+projection,'fingerprints',rough=.16 if not plastic else .19,amount=.8 if heavy else .55,projection=projection)
  local_layer(t,'31 • Следы протирания — '+projection,'wipes',rough=.21,amount=.42 if heavy else .22,projection=projection)
  local_layer(t,'40 • Тонкая пыль в защищённых местах — '+projection,'deposit',(.083,.069,.046),0,.78,.52,.54 if heavy else .22,distance=.000008 if heavy else .000003,projection=projection,protected=True)
 local_layer(t,'41 • Осадок около реальных винтов','fasteners',(.043,.035,.021),0,.83,.53,.68 if heavy else .25,distance=.000012 if heavy else .000004,protected=True)
 if heavy:
  local_layer(t,'42 • Немного высохших капель','droplets',rough=.64,amount=.38)
  l=local_layer(t,'43 • Отдельные частицы сухого осадка','deposit',(.12,.105,.072),0,.87,.65,.4,distance=.000025,protected=True)
  noise(l,'Отдельные частицы, а не сплошная корка',3000,.69,.78)

def blued():
 m,t,p=stack('воронёная сталь',(.014,.017,.023),1,.30)
 layer(t,'00 • Чёрное воронение',(.014,.017,.023),1,.30);factory(t,.30,2.5e-6);handling(t,(.31,.34,.38),1,.30)
 if CONDITION==20:
  l=local_layer(t,'50 • Тёмный окисел в отдельных защищённых очагах','deposit',(.064,.029,.013),0,.84,.54,.27,distance=.000012,protected=True)
  noise(l,'Редкие отдельные очаги окисления стали',280,.62,.74)
 H.reconnect(U,t);return m

def machined(label,color=(.34,.37,.41),rough=.26):
 m,t,p=stack(label,color,1,rough);layer(t,'00 • Обработанная сталь',color,1,rough);factory(t,rough,1.2e-6)
 if CONDITION<100:
  local_layer(t,'20 • Тонкие риски контактной стали','scratches',(.27,.30,.34),1,.38,.48,.38,distance=.000003)
  local_layer(t,'30 • Масляная плёнка','wipes',rough=.19,amount=.38)
 H.reconnect(U,t);return m

def anodized():
 m,t,p=stack('чёрный анодированный алюминий',(.008,.009,.011),.90,.43)
 p.inputs['Coat Weight'].default_value=0.
 layer(t,'00 • Чёрное анодирование',(.008,.009,.011),.90,.43);factory(t,.43,3.8e-6)
 layer(t,'13 • Тонкая матовая обработка корпуса',height='source',kind='NOISE',scale=900,distance=.000006,amount=.48)
 handling(t,(.43,.46,.49),1,.35)
 H.reconnect(U,t);return m

def bakelite():
 m,t,p=stack('красно-коричневый бакелит',(.060,.007,.004),0,.34)
 p.inputs['Coat Weight'].default_value=.12;p.inputs['Coat Roughness'].default_value=.32
 layer(t,'00 • Красно-коричневая фенольная масса',(.060,.007,.004),0,.34)
 l=layer(t,'10 • Тёмные включения прессованного бакелита',(.025,.003,.0015),0,.39,amount=.35);noise(l,'Локальный пигмент, не окраска шумом всего металла',90,.30,.66)
 l=layer(t,'11 • Мелкая неоднородность смолы',(.085,.016,.007),0,.36,amount=.18);noise(l,'Мелкие волокна наполнителя',900,.48,.70)
 layer(t,'12 • Микропоры прессования — 3 мкм',height='source',kind='NOISE',scale=2300,distance=.000003,amount=.7)
 handling(t,(.11,.025,.014),0,.49,plastic=True)
 if CONDITION<100:
  l=local_layer(t,'44 • Устоявшаяся грязь в основании насечки','deposit',(.025,.016,.008),0,.83,.54,.65 if CONDITION==20 else .20,distance=.000016,protected=True)
  mask=U.Mask.add_new_mask(l,'Защищённые впадины настоящей насечки','AO','Object',UV,ao_distance=.0007)
  importlib.import_module(U.__name__+'.MaskModifier').add_new_mask_modifier(mask,'INVERT')
 H.reconnect(U,t);return m

def rubber():
 m,t,p=stack('резина кнопки и уплотнителей',(.011,.013,.012),0,.68)
 layer(t,'00 • Матовый эластомер',(.011,.013,.012),0,.68)
 layer(t,'10 • Микротекстура резины',height='source',kind='NOISE',scale=1500,distance=.000006)
 if CONDITION<100:
  local_layer(t,'20 • Полировка кнопки пальцем','fingerprints',rough=.41,amount=.58,projection='top')
  local_layer(t,'30 • Пыль около уплотнений','deposit',(.058,.047,.028),0,.85,.52,.48 if CONDITION==20 else .2,distance=.000005,protected=True)
 H.reconnect(U,t);return m

def simple(label,color,metal,rough,grain=0.):
 m,t,p=stack(label,color,metal,rough);layer(t,'00 • Основание',color,metal,rough)
 if grain:layer(t,'10 • Микроструктура',height='source',kind='NOISE',scale=3000,distance=grain)
 H.reconnect(U,t);return m

def glass():
 m,t,p=stack('прозрачная линза с тонким покрытием',(.94,.975,.95),0,.018,uv=LENS)
 p.inputs['Transmission Weight'].default_value=1.;p.inputs['IOR'].default_value=1.48
 p.inputs['Coat Weight'].default_value=.14;p.inputs['Coat Roughness'].default_value=.035
 p.inputs['Thin Film Thickness'].default_value=285.;p.inputs['Thin Film IOR'].default_value=1.36
 m['Optics']='Dielectric transmission; accepted thickness; subtle green/violet reflection. Game shader is a later stage.'
 layer(t,'00 • Чистое диэлектрическое стекло',(.94,.975,.95),0,.018)
 if CONDITION<100:
  local_layer(t,'20 • Слабый отпечаток у края линзы','fingerprints',rough=.17,amount=.42,projection='lens')
  local_layer(t,'30 • Осадок у оправы, центр остаётся чистым','deposit',(.55,.54,.48),0,.4,.52,.44 if CONDITION==20 else .13,distance=.0000015,projection='lens')
  if CONDITION==20:local_layer(t,'31 • Тонкие следы чистки края','scratches',rough=.28,height=.51,amount=.27,distance=.0000018,projection='lens')
 H.reconnect(U,t);return m

# Useful hidden cartridge props are retained. Optional suppressor remains an
# independent existing asset; this job commissions one pistol assembly.
parts=[o for o in bpy.data.objects if o.type=='MESH' and not o.name.startswith(('Studio','Reference','Suppressor','Highpoly |')) and not in_parent(o,'Suppressor •')]
for i,o in enumerate(parts):
 author_coordinates(o)
 if i%15==0:print('PM_COORDINATES',i,len(parts),o.name,flush=True)
materials=dict(blue=blued(),bare=machined('обработанная сталь ствола'),screws=machined('воронёный крепёж',(.024,.029,.035),.32),
               alloy=anodized(),bakelite=bakelite(),rubber=rubber(),lens=glass(),
               brass=simple('латунь патронов',(.58,.40,.13),1,.26,1.e-6),copper=simple('томпак оболочки пули',(.53,.25,.13),1,.25,1.e-6),
               primer=simple('металл капсюля',(.42,.43,.38),1,.29,.6e-6),red=simple('красная эмаль положения предохранителя',(.39,.015,.009),0,.34,1.e-6),
               luminous=simple('светлая точка мушки',(.78,.76,.60),0,.47))

def family(o):
 name=o.name
 if 'brass outer case' in name:return 'brass'
 if 'copper nose' in name:return 'copper'
 if 'primer disk' in name:return 'primer'
 if name.startswith(('Bakelite |','Grip ','Lanyard |')):return 'bakelite'
 if name.startswith('Barrel |') or name=='Muzzle | recessed steel rim':return 'bare'
 if name=='Safety | flush red witness enamel':return 'red'
 if name.startswith('Luminous point |'):return 'luminous'
 if 'fastener' in name or 'slotted screw' in name:return 'screws'
 if name.startswith('Reflex |'):
  if 'curved aspheric lens' in name:return 'lens'
  if any(m and m.name=='Check | K1 elastomer' for m in o.data.materials):return 'rubber'
  return 'alloy'
 if name.startswith('Mount |'):return 'alloy'
 return 'blue'

assignments={}
for o in parts:
 if o.get('PM engraving helper'):continue
 f=family(o);assignments[o.name]=f
 for i,old in enumerate(o.data.materials):
  if old and old.name.startswith('Check |') and old.name!='Check | Cyrillic mark layout':o.data.materials[i]=materials[f]
fill=bpy.data.materials['КОРС-9 • светлая краска в клеймах']
fill['condition_percent']=CONDITION;fill['Preserved from']='Accepted v11 native two-layer fill'
ft=next(n.node_tree for n in fill.node_tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node)
fl=next(l for l in ft.yp.layers if l.masks)
if CONDITION==100:
 for mask in fl.masks:mask.enable=False
elif CONDITION==20:
 for mask in fl.masks:
  if mask.type=='NOISE':mask.translation=(.41,.27,.08);H.local_noise_ramp(U,mask,.43,.54)
H.reconnect(U,ft);CREATED.append(fill)

# Assign pale fill to bottom faces of the existing optical engravings. Their
# topology, depth, local matrices and Boolean modifiers stay unchanged.
record=json.loads((PROJECT/'_asset_src/pm_refinement/review_v11/Проверки/engraving.json').read_text(encoding='utf-8'))
for row in record['markings']:
 cutter=bpy.data.objects[row['cutter']];host=bpy.data.objects[row['host']]
 for i,old in enumerate(cutter.data.materials):
  if old and old.name.startswith('Check |'):cutter.data.materials[i]=materials[family(host)]
 if not host.name.startswith('Reflex |'):continue
 if fill not in list(host.data.materials):host.data.materials.append(fill)
 paint_index=list(host.data.materials).index(fill);cutter.data.materials.clear()
 for mat in host.data.materials:cutter.data.materials.append(mat)
 normal=Vector(row['normal_local']).normalized()
 for face in cutter.data.polygons:face.material_index=paint_index if face.normal.dot(normal)<-.99 else 0
for o in parts:
 if o.get('PM geometry helper'):
  for i,old in enumerate(o.data.materials):
   if old and old.name.startswith('Check |'):o.data.materials[i]=materials['blue']
rig['condition_percent']=CONDITION;rig['Texture stage']='Native UCUPaint PBR v01; prepared for owner review'
rig['Deferred geometry']='Owner postponed lower left/right lens housing corner defect until after texture acceptance.'
note=bpy.data.texts.get('ПМ • как смотреть текстуры') or bpy.data.texts.new('ПМ • как смотреть текстуры')
note.clear();note.write(f'ПМ / КОРС-9 — состояние {CONDITION}%\nПринятая геометрия v11 и ручные контролы сохранены.\nМатериалы — настоящие UCUPaint 2.4.9; изображения встроены.\nМаски эксплуатации отсутствуют у 100%, независимы у 60/20.\nДля стекла используйте Material Preview или Rendered.\nВсе состояния используют принятую форму; трещины/поломки не добавлены.\nДефект корпуса у нижних углов линзы отложен по указанию владельца.\n')
for o in bpy.context.selected_objects:o.select_set(False)
rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':
   a.spaces.active.shading.type='MATERIAL';a.spaces.active.overlay.show_extras=False;a.spaces.active.overlay.show_relationship_lines=False
S.render.engine='CYCLES';bpy.ops.file.pack_all()
folder=ROOT/'candidate'/str(CONDITION);folder.mkdir(parents=True,exist_ok=True)
path=folder/f'PM_Textures_{CONDITION}_v01.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
report=dict(condition=CONDITION,file=str(path),materials=[m.name for m in CREATED],assignments=assignments,masks=[im.name for im in IMAGES.values()],
            blender=bpy.app.version_string,ucupaint=U.common.get_current_version_str(),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            deferred_geometry=rig['Deferred geometry'],geometry_changed=False)
(ROOT/'checks'/f'authoring_{CONDITION}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_NATIVE_TEXTURE_SAVED',path,len(CREATED),'materials;',len(IMAGES),'mask images',flush=True)
