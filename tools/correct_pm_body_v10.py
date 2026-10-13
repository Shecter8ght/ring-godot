"""Reference-led slide, hammer and grip changes, before the v10 control fit.

Uses the archived modeller's outline helpers only, never replays his scene.
Retains frame, marks, localized enamel, optic and the animation owners.
"""
from pathlib import Path
import ast,hashlib,json,math,sys
import bpy,bmesh,addon_utils
import numpy as np
from math import sin,cos,pi
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement';OUT=ROOT/'work'
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE));S=bpy.context.scene;S.frame_set(1)
rig=bpy.data.objects['PM_CONTROLS • select me'];slide=bpy.data.objects['Slide • translation'];hammer=bpy.data.objects['Hammer • pivot']
saved_action=rig.animation_data.action;saved_scale=rig.scale.copy();saved_loc=rig.location.copy()
rig.animation_data_clear();rig.scale=(1,1,1);rig.location=(0,0,0)
for k in ('Slide','Hammer','Trigger','Safety','Magazine','Suppressor','MagCatch'):rig[k]=0.
bpy.context.view_layer.update()
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
outline_source=Path(__file__).with_name('pm_v4_outline_source.py')
if not outline_source.exists():outline_source=LIB/'90_История_и_резервные_копии/Скрипты_пистолета/build_pm_v4.py'
parsed=ast.parse(outline_source.read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in parsed.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'PM_outline_helpers','exec'))
BODY=bpy.data.collections['01 • Frame & bakelite'];SLIDE=bpy.data.collections['02 • Slide assembly']
steel=bpy.data.materials['Check | satin neutral metal'];dark=bpy.data.materials['Check | recess dark grey']
details={}

def tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
 t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return t

def cut(host,cutter,label):
 bpy.context.view_layer.objects.active=host;mod=host.modifiers.new(label,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='MANIFOLD';mod.object=cutter
 while host.modifiers[0]!=mod:bpy.ops.object.modifier_move_up(modifier=mod.name)
 bpy.ops.object.modifier_apply(modifier=mod.name);delete(cutter)

def weighted(o):
 for m in list(o.modifiers):
  if m.type=='WEIGHTED_NORMAL':o.modifiers.remove(m)
 m=o.modifiers.new('Local face-area normals','WEIGHTED_NORMAL');m.keep_sharp=True;m.weight=50

def smoothstep(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)

# Inner-only thinning: the ray direction is the inward skin normal reversed.
# Each moved vertex has an independently found exit on the untouched exterior.
grip=bpy.data.objects['Bakelite | one-piece rounded grip'];bpy.context.view_layer.update();grip.data.update();original=tree(grip)
mw=grip.matrix_world;inv=mw.inverted();normal_m=mw.to_3x3().inverted().transposed();moved=0;short=0
coordinates=np.empty(len(grip.data.vertices)*3,dtype=np.float32);normals=np.empty_like(coordinates)
grip.data.vertices.foreach_get('co',coordinates);grip.data.vertices.foreach_get('normal',normals)
coordinates=coordinates.reshape(-1,3);normals=normals.reshape(-1,3);new_coordinates=coordinates.copy()
before=[]
for x,z in ((.63,.15),(.63,.40),(.63,.65),(.75,.35),(.82,.15),(.90,.22)):
 for sy in (-1,1):
  p=Vector((x,sy*.4,z));direction=Vector((0,-sy,0));h=original.ray_cast(p,direction,1)[0]
  if h is None:continue
  inner=original.ray_cast(h+direction*.000015,direction,.2)[0]
  if inner:before.append(dict(point=[x,sy*.4,z],direction=list(direction),outer=list(h),inner=list(inner),thickness=(inner-h).length))
for index,(co,normal) in enumerate(zip(coordinates,normals)):
 p=mw@Vector(co);n=(normal_m@Vector(normal)).normalized()
 radial=Vector((p.x-(.51+.27*(1-p.z)),p.y,0))
 inner_side=abs(p.y)>.100 and n.y*math.copysign(1,p.y)<-.55
 if not inner_side and (radial.length<1e-6 or n.dot(radial.normalized())>-.50):continue
 d=-n;h=original.ray_cast(p+d*.000020,d,.14)[0]
 if h is None:short+=1;continue
 distance=(h-p).length
 if not .0010<distance<.135:short+=1;continue
 new_coordinates[index]=inv@(p+d*distance*.5);moved+=1
grip.data.vertices.foreach_set('co',new_coordinates.ravel());grip.data.update()
# Fair only the moved inner vertices. The exposed lip joins stay anchored to
# the unchanged exterior; this removes tiny ridges from the remeshed source.
bm=bmesh.new();bm.from_mesh(grip.data);bm.verts.ensure_lookup_table()
inner=[bm.verts[i] for i in np.flatnonzero(np.linalg.norm(new_coordinates-coordinates,axis=1)>1e-7)]
for j in range(12):bmesh.ops.smooth_vert(bm,verts=inner,factor=.48,use_axis_x=True,use_axis_y=True,use_axis_z=True)
bm.to_mesh(grip.data);bm.free();grip.data.update()
details['grip']=dict(inner_vertices_moved=moved,unpaired_transition_vertices=short,wall_samples=before,ratio=.5,outer_skin_retained=True,inner_surface_fairing_iterations=12)
print('PM_V10_GRIP',moved,short,flush=True)

# Recreate the closed visual slide skin from its archived continuous outline.
# Front, bore clearance and openings keep the previous coordinates. The rear
# gets an earlier curved descent and loses the kink from the planar shoulders.
old_shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear'];delete(old_shell)
half=.150;radius=.135;zc=1.393333333;bore_z=zc+.005
front_profile=[(-1.012,1.309),(-.996,1.310),(-.960,1.310),(-.930,1.309),(-.885,1.307),(-.820,1.310),(-.740,1.310),(-.670,1.300),(-.610,1.279),(-.550,1.249),(-.490,1.223),(-.430,1.209),(-.36,1.201)]
def front_side_bottom(x):
 if x<=front_profile[0][0]:return front_profile[0][1]
 if x>=front_profile[-1][0]:return 1.201
 for i in range(len(front_profile)-1):
  a,b=front_profile[i:i+2]
  if a[0]<=x<=b[0]:
   t=(x-a[0])/(b[0]-a[0]);h=b[0]-a[0]
   ma=(b[1]-a[1])/h if i==0 else (b[1]-front_profile[i-1][1])/(b[0]-front_profile[i-1][0])
   mb=0 if i+2>=len(front_profile) else (front_profile[i+2][1]-a[1])/(front_profile[i+2][0]-a[0])
   return (2*t**3-3*t*t+1)*a[1]+(t**3-2*t*t+t)*h*ma+(-2*t**3+3*t*t)*b[1]+(t**3-t*t)*h*mb
def old_rear(x):return math.sqrt(max(0,1-max(0,min(.998,(x-.790)/.205))**2))
def rear_factor(x):
 # A broad continuously curved descent; preserve the front of the rear-sight seat.
 t=max(0,min(.998,(x-.765)/.230));return math.sqrt(max(0,1-t*t))**1.22
def nose_bottom(x):return 1.201+.026*math.exp(-((x+1.011)/.045)**2)
def lower_surface(x,y):
 side=max(1.220,front_side_bottom(x));bottom=nose_bottom(x)
 z=side-(side-bottom)*math.sqrt(max(0,1-(y/half)**2));return bottom+(z-bottom)*old_rear(x)
xs=sorted(set([-1.011,-1.006,-.993,-.976]+[-.960+i*.015 for i in range(41)]+[-.36+i*.012 for i in range(112)]+[.750+i*.003 for i in range(81)]))
vs=[];faces=[]
for xi,x in enumerate(xs):
 fac=[.93,.976,.999,1][min(xi,3)];width=half*fac;bottom=nose_bottom(x);side=max(1.220,front_side_bottom(x))
 nose_t=max(0,min(1,(x+1.011)/.035));nose_drop=.002*(1-math.sqrt(max(0,1-(1-nose_t)**2)))
 cs=[(-width,side+(zc-side)*j/16) for j in range(17)]
 cs += [(width*cos(pi-j*pi/96),zc+radius*sin(pi-j*pi/96)-nose_drop*sin(pi-j*pi/96)**2) for j in range(1,97)]
 cs += [(width,zc+(side-zc)*j/16) for j in range(1,17)]
 cs += [(width*cos(j*pi/48),side-(side-bottom)*sin(j*pi/48)) for j in range(1,48)]
 for y,z in cs:
  original_z=z;yn=min(1.,abs(y)/half);old=math.sqrt(max(0,1-yn*yn))
  shoulder=.318+(1-yn)/.37*.410 if yn>.63 else 1-.272*(yn/.63)**2
  if z>zc:z+=(shoulder-old)*radius*max(0,min(1,(z-zc)/radius))*(1-smoothstep(.730,.855,x))
  # Machined longitudinal shoulders: outward flared sides and a rounded ledge.
  flare=.0173*smoothstep(-.06,.08,x)*(1-smoothstep(.905,.990,x))
  ledge=1-smoothstep(zc+.006,zc+.021,original_z)
  y += math.copysign(flare*ledge*min(1,abs(y)/.128),y) if abs(y)>1e-8 else 0
  tail_width=1-.10*smoothstep(.870,.990,x);y*=tail_width
  z=bottom+(z-bottom)*rear_factor(x)
  vs.append((x,y,z))
N=len(cs);faces=[tuple(range(N-1,-1,-1)),tuple(range((len(xs)-1)*N,len(xs)*N))]
for i in range(len(xs)-1):
 for j in range(N):faces.append((i*N+j,i*N+(j+1)%N,(i+1)*N+(j+1)%N,(i+1)*N+j))
shell=mesh('Slide | continuous crown, rounded muzzle & rear',vs,faces,steel,SLIDE,slide,0)
# Preserve the bounded visual hollow, muzzle and hammer aperture.
ixs=[-.994,-.976,-.930,-.885,-.82,-.74,-.67,-.61,-.55,-.49,-.43,-.36,0,.4,.735];iv=[]
for x in ixs:
 ic=[(-.129,lower_surface(x,-.129)+.027),(-.129,1.370)]
 ic += [(.129*cos(pi-j*pi/64),1.370+.113*sin(pi-j*pi/64)) for j in range(1,65)]
 ic += [(.129,lower_surface(x,.129)+.027)]
 ic += [(.129*cos(pi*j/48),lower_surface(x,.129*cos(pi*j/48))+.027) for j in range(1,48)]
 iv.extend((x,y,z) for y,z in ic)
n=len(ic);ff=[tuple(range(n-1,-1,-1)),tuple(range((len(ixs)-1)*n,len(ixs)*n))]
ff += [(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j) for k in range(len(ixs)-1) for j in range(n)]
cut(shell,mesh('temporary preserved visual hollow',iv,ff,None,SLIDE),'Preserved visual hollow')
c=cube('temporary hammer aperture',(.989,0,1.441),(.29,.088,.392),None,SLIDE,bevel=.011);apply_mods(c);cut(shell,c,'Preserved hammer aperture')
cut(shell,cylinder('temporary muzzle aperture',(-.985,0,bore_z),.086,.16,None,SLIDE,bevel=0,vertices=192),'Preserved muzzle aperture')
port=[(-.270,1.398),(-.247,1.371),(.032,1.371),(.060,1.397),(.060,1.576),(.034,1.604),(-.243,1.604),(-.270,1.576)]
c=extrude('temporary original port',port,.294,None,SLIDE,None,.003,y=.173);apply_mods(c);cut(shell,c,'Preserved reference port')
track=[(.067,1.448),(.215,1.448),(.235,1.456),(.235,1.476),(.218,1.485),(.067,1.485)]
c=extrude('temporary extractor track',track,.111,None,SLIDE,None,.003,y=.155);apply_mods(c);cut(shell,c,'Preserved extractor track')
# 13 negative cuts on each side, through the shoulder down to the open lower rim.
for sy in (-1,1):
 for i in range(13):
  c=cube('temporary full-height slide groove',(.175+i*.034,sy*.1690,1.310),(.0125,.029,.260),None,SLIDE,bevel=.0018)
  c.rotation_euler[1]=-.205;apply_mods(c);cut(shell,c,'Full-height recessed serration')
clean(shell)
shell.data.materials.clear();shell.data.materials.append(steel)
for p in shell.data.polygons:p.material_index=0
# Broaden only the sharp rear opening/rim edges; keep the crown and front intact.
bm=bmesh.new();bm.from_mesh(shell.data);bm.normal_update()
weights=shell.data.attributes.new('bevel_weight_edge','FLOAT','EDGE');rear_edges=[]
for e in bm.edges:
 if e.is_manifold and min(v.co.x for v in e.verts)>.82 and e.calc_face_angle(0)>.42:rear_edges.append(e.index)
bm.free()
for index in rear_edges:weights.data[index].value=1.
be=shell.modifiers.new('Rear opening and tail • local rounded edges','BEVEL');be.limit_method='WEIGHT';be.width=.006;be.segments=8;be.harden_normals=True;be.mark_sharp=True
weighted(shell)
shell['Revision']='v10: rounded rear descent, flared longitudinal shoulders, full-height cuts'
details['slide']=dict(side_flare_mm=.0173*saved_scale.y*1000,serrations_per_side=13,serration_depth_mm=.0085*saved_scale.y*1000,rear_start_mm=.765*saved_scale.x*1000,regular_loft_sections=len(xs),rear_edge_radius_mm=.006*saved_scale.x*1000)
print('PM_V10_SLIDE',len(shell.data.vertices),flush=True)

# Five cut valleys with four intervening traction lands, not raised ribs.
for o in list(bpy.data.objects):
 if o.name.startswith('Hammer |'):delete(o)
hp=[(.826,1.230),(.809,1.280),(.857,1.350),(.883,1.421),(.910,1.458),(.946,1.469),(.979,1.456),(.994,1.431),(.986,1.402),(.953,1.367),(.889,1.278)]
hm=extrude('Hammer | rounded spur with broad side chamfers',hp,.073,steel,BODY,hammer,.0064,smooth=6);apply_mods(hm)
cuts=[]
for i in range(5):
 x=.902+i*.020;z=1.455+.012*sin(i*pi/4)
 c=cube('temporary wide hammer groove',(x,0,z-.004),(.0125,.092,.037),None,BODY,None,.0018);c.rotation_euler[1]=-.20;apply_mods(c);cut(hm,c,'Wide recessed thumb groove')
 cuts.append(dict(x=x,z=z,width_mm=.0125*saved_scale.x*1000,pitch_mm=.020*saved_scale.x*1000))
clean(hm);weighted(hm);hm['Traction']='Five deep transverse cuts and four intermediate lands'
details['hammer']=dict(groove_count=5,land_count=4,cuts=cuts)
rig.scale=saved_scale;rig.location=saved_loc;rig.animation_data_create();rig.animation_data.action=saved_action;S.frame_set(1);bpy.context.view_layer.update()
details['parent_geometry']=str(SOURCE);details['parent_sha256']=SOURCE_HASH
(OUT/'body_geometry_v10.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'PM_Body_v10.blend'))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_BODY_V10_SAVED',flush=True)
