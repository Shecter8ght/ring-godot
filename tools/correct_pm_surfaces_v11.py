"""Local artistic PM repairs: normals, rail, safety, radial hammer and drives.

No movie, presentation, production texturing or game export. World-space mm.
"""
from pathlib import Path
import ast,hashlib,json,math,struct
import bpy,bmesh,addon_utils,numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v11'
for sub in ('01_ПМ','02_Крепление','03_Коллиматор','Проверки','Рабочие_снимки'):(OUT/sub).mkdir(parents=True,exist_ok=True)
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True);bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.context.scene;S.frame_set(1);rig=bpy.data.objects['PM_CONTROLS • select me'];rig.animation_data_clear()
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[key]=0.
bpy.context.view_layer.update();SLIDE=bpy.data.collections['02 • Slide assembly'];BODY=bpy.data.collections['01 • Frame & bakelite'];MOUNT=bpy.data.collections['08 • Optic mount — separate asset']
steel=bpy.data.materials['Check | satin neutral metal'];dark=bpy.data.materials['Check | recess dark grey'];changed=set();details={}

def mm(p):return Vector(p)/1000
def fingerprint(o):
 h=hashlib.sha256()
 for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
 for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
 h.update(str(tuple(tuple(r) for r in o.matrix_local)).encode());h.update((o.parent.name if o.parent else '').encode());return h.hexdigest()
def tree(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=eo.to_mesh();t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons]);eo.to_mesh_clear();return t
def bounds(o):
 eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());m=eo.to_mesh();v=[eo.matrix_world@v.co for v in m.vertices];eo.to_mesh_clear();return [min(p[i] for p in v) for i in range(3)],[max(p[i] for p in v) for i in range(3)]
def weighted(o):
 for m in list(o.modifiers):
  if m.type=='WEIGHTED_NORMAL':o.modifiers.remove(m)
 m=o.modifiers.new('Local face-area normals','WEIGHTED_NORMAL');m.keep_sharp=True;m.mode='FACE_AREA';m.weight=50
def mesh(name,vertices,faces,owner,collection,material=steel,bevel=0):
 inv=owner.matrix_world.inverted() if owner else Matrix.Identity(4);me=bpy.data.meshes.new(name);me.from_pydata([tuple(inv@v) for v in vertices],[],faces);me.update()
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
 for e in bm.edges:
  if e.is_manifold and e.calc_face_angle(0)>.60:e.smooth=False
 bm.to_mesh(me);bm.free();o=bpy.data.objects.new(name,me);collection.objects.link(o)
 if owner:o.parent=owner;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Identity(4)
 bpy.context.view_layer.update()
 if material:me.materials.append(material)
 for p in me.polygons:p.use_smooth=len(p.vertices)<=4
 if bevel:
  m=o.modifiers.new('Local physical edge radii','BEVEL');m.width=bevel/1000/abs(o.matrix_world.determinant())**(1/3);m.segments=12;m.harden_normals=True;m.mark_sharp=True
 weighted(o);return o
def prism(name,xz,y0,y1,owner,collection,material=steel,bevel=0):
 n=len(xz);v=[mm((x,y,z)) for y in (y0,y1) for x,z in xz];f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)];return mesh(name,v,f,owner,collection,material,bevel)
def apply_geometry(o):
 bpy.context.view_layer.objects.active=o
 for m in list(o.modifiers):
  if m.type!='WEIGHTED_NORMAL':bpy.ops.object.modifier_apply(modifier=m.name)
def boolean(o,cutter,operation,label,remove=True,solver='MANIFOLD'):
 bpy.context.view_layer.objects.active=o;m=o.modifiers.new(label,'BOOLEAN');m.operation=operation;m.solver=solver;m.object=cutter
 while o.modifiers[0]!=m:bpy.ops.object.modifier_move_up(modifier=m.name)
 bpy.ops.object.modifier_apply(modifier=m.name)
 if remove:bpy.data.objects.remove(cutter,do_unlink=True)
def cleanup(o):
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
def is_drive(o):
 return o.name=='Backstrap | slotted screw' or o.name.startswith(('Mount | cross-slot fastener','Reflex | K1 cheek fastener','Reflex | K1 clamp six-lobe fastener','Reflex | K1 upper anchor')) or o.name in ('Reflex | K1 elevation adjustment','Reflex | K1 windage adjustment')
frame=bpy.data.objects['Frame | traced flowing silhouette'];shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear'];hammer=bpy.data.objects['Hammer | rounded spur with broad side chamfers']
targets={frame.name,shell.name,hammer.name,'Safety | beveled tapered thumb flag','Safety | prominent grooved thumb wedge','Safety | flush red witness enamel'}
unchanged={o.name:fingerprint(o) for o in bpy.data.objects if o.type=='MESH' and not o.get('PM engraving helper') and not o.get('PM geometry helper') and o.name not in targets and not o.name.startswith(('Mount | continuous relieved','Mount | chamfered rail tooth')) and not is_drive(o)}

# 1. Flat side caps must not interpolate the rounded web/backstrap normals.
raw_before=fingerprint(frame);caps=0
if frame.data.has_custom_normals:frame.data.normals_split_custom_set([(0,0,0)]*len(frame.data.loops))
for p in frame.data.polygons:
 if abs(p.normal.y)>.999999 and all(abs(abs(frame.data.vertices[j].co.y)-.134)<2e-6 for j in p.vertices):p.use_smooth=False;caps+=1
frame.data.update();weighted(frame);assert fingerprint(frame)==raw_before
details['frame']=dict(flat_caps=caps,vertices_and_topology_unchanged=True,method='Flat planar caps; rounded outer web and all native engravings retained')
print('PM_V11_FRAME',caps,flush=True)

# 2. One full rail section with subtractive cross slots avoids both overlapping
# side sheets and unstable coplanar unions of the old tooth bodies.
rail=bpy.data.objects['Mount | continuous relieved rail spine'];teeth=sorted((o for o in bpy.data.objects if o.name.startswith('Mount | chamfered rail tooth')),key=lambda o:o.name)
before=bounds(rail);tooth_bounds=[bounds(o) for o in teeth]
owner=rail.parent;profile=[teeth[0].matrix_world@v.co for v in list(teeth[0].data.vertices)[:len(teeth[0].data.vertices)//2]];n=len(profile)
v=[Vector((x,p.y,p.z)) for x in (before[0][0],before[1][0]) for p in profile]
f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
bpy.data.objects.remove(rail,do_unlink=True)
rail=mesh('Mount | continuous relieved rail spine',v,f,owner,MOUNT)
gaps=[(before[0][0]-.001,tooth_bounds[0][0][0])]+[(tooth_bounds[i][1][0],tooth_bounds[i+1][0][0]) for i in range(len(teeth)-1)]+[(tooth_bounds[-1][1][0],before[1][0]+.001)]
for a,b in gaps:
 cutter=prism('temporary rail cross slot',[(a*1000,before[1][2]*1000),(b*1000,before[1][2]*1000),(b*1000,135),(a*1000,135)],-20,20,None,MOUNT,None)
 boolean(rail,cutter,'DIFFERENCE','Continuous rail cross slot')
for tooth in teeth:bpy.data.objects.remove(tooth,do_unlink=True)
cleanup(rail)
be=rail.modifiers.new('Continuous rail edge radii','BEVEL');be.width=.00008/abs(rail.matrix_world.determinant())**(1/3);be.segments=8;be.harden_normals=True;be.mark_sharp=True
weighted(rail);rail['Construction']='One closed rail section with cut cross slots; no coplanar tooth/spine side faces'
details['rail']=dict(rail=rail.name,merged_teeth=len(teeth),source_spine_bounds=before,source_tooth_bounds=tooth_bounds)
print('PM_V11_RAIL',len(rail.data.vertices),flush=True)

# 3. Rebuild the projecting pad with horizontal recessed bands and round both
# its outline and the thin thumb leaf. No raised traction strips are added.
safe=bpy.data.objects['Safety • pivot'];leaf=bpy.data.objects['Safety | beveled tapered thumb flag']
for m in leaf.modifiers:
 if m.type=='BEVEL':m.width=.00042/abs(leaf.matrix_world.determinant())**(1/3);m.segments=16;m.mark_sharp=True;m.harden_normals=True
weighted(leaf)
old=bpy.data.objects['Safety | prominent grooved thumb wedge'];bpy.data.objects.remove(old,do_unlink=True)
poly=[(50.85,107.65),(52.1,107.30),(57.1,110.50),(57.6,111.55),(56.5,112.10),(51.05,109.1)]
def pad_y(x):return -(15.45+max(0,min(1,(57.2-x)/6.3))*1.9)
n=len(poly);v=[mm((x,-13.7,z)) for x,z in poly]+[mm((x,pad_y(x),z)) for x,z in poly];f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
pad=mesh('Safety | prominent grooved thumb wedge',v,f,safe,SLIDE,bevel=.18);apply_geometry(pad)
grooves=[]
for i in range(7):
 z=107.9+i*.50;xs=(50.30,50.90,57.20,57.95);xy=[(xs[0],-20),(xs[-1],-20)]+[(x,pad_y(x)+.40) for x in reversed(xs)];n=len(xy)
 v=[mm((x,y,zz)) for zz in (z-.13,z+.13) for x,y in xy];f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
 cutter=mesh('temporary horizontal safety band',v,f,None,SLIDE,None,0);boolean(pad,cutter,'DIFFERENCE','Horizontal recessed thumb band')
 grooves.append(dict(z_mm=z,width_mm=.26,depth_mm=.40))
cleanup(pad);weighted(pad);details['safety_pad']=dict(pad=pad.name,leaf=leaf.name,bands=grooves,leaf_bevel_mm=.42,pad_bevel_mm=.18,orientation='Horizontal X direction in the closed pose')

# 4. Replace the old pocket from the untouched slide skin, then bevel only the
# new rim/floor edges. The previous source file remains the clean archive.
old_details=json.loads((ROOT/'review_v10/Проверки/controls_geometry.json').read_text(encoding='utf-8'))
curve=[Vector(p) for p in old_details['safety']['pocket']]
# Remove redundant convex-hull samples, then fillet the outline itself. Tiny
# inherited steps otherwise force a clamped 3D bevel down to a microscopic size.
while len(curve)>6:
 scores=[]
 for i,b in enumerate(curve):
  a=curve[i-1];c=curve[(i+1)%len(curve)];d=c-a
  scores.append((b-a-d*max(0,min(1,(b-a).dot(d)/d.length_squared))).length)
 i=min(range(len(scores)),key=lambda j:scores[j])
 if scores[i]>.075:break
 curve.pop(i)
rounded_curve=[];corner_radii=[]
for i,b in enumerate(curve):
 a=curve[i-1];c=curve[(i+1)%len(curve)];u=(a-b).normalized();v=(c-b).normalized();theta=math.acos(max(-1,min(1,u.dot(v))))
 trim=min(.8/math.tan(theta/2),.42*(a-b).length,.42*(c-b).length);radius=trim*math.tan(theta/2)
 center=b+(u+v).normalized()*radius/math.sin(theta/2);p=b+u*trim;q=b+v*trim
 start=math.atan2(p.y-center.y,p.x-center.x);end=math.atan2(q.y-center.y,q.x-center.x);sweep=(end-start+math.pi)%(2*math.pi)-math.pi
 steps=max(2,math.ceil(abs(sweep)/math.radians(5)))
 rounded_curve.extend(center+Vector((math.cos(start+sweep*j/steps),math.sin(start+sweep*j/steps)))*radius for j in range(steps+1));corner_radii.append(radius)
curve=rounded_curve
for m in list(shell.modifiers):
 if m.name.startswith(('CONTROLS | full safety','Control pocket')):shell.modifiers.remove(m)
old_operand=bpy.data.objects.get('Safety relief | full-stroke pocket operand')
if old_operand:bpy.data.objects.remove(old_operand,do_unlink=True)
# The accepted rear-rim bevel belongs to the uncut skin. Bake it first, as in
# v10's original modifier order; its inherited edge weights must never act on
# newly created pocket edges a second time.
apply_geometry(shell)
# A rounded machining tool provides the upper lip directly. Beveling the
# triangulated host rim produced folded strips despite closed topology.
# The tool's own simple floor perimeter receives the native Blender bevel.
area=sum(p.x*curve[(i+1)%len(curve)].y-p.y*curve[(i+1)%len(curve)].x for i,p in enumerate(curve));sign=1 if area>0 else -1
normals=[];baseline=tree(shell);floor_y=-11.28
for i,p in enumerate(curve):
 a=(p-curve[i-1]).normalized();b=(curve[(i+1)%len(curve)]-p).normalized()
 na=Vector((-a.y,a.x))*sign;nb=Vector((-b.y,b.x))*sign;n=(na+nb).normalized();normals.append(n/max(.1,n.dot(na)))
def ring(inset,heights):return [mm((p.x+normal.x*inset,y,p.y+normal.y*inset)) for p,normal,y in zip(curve,normals,heights)]
rings=[ring(0,[-30]*len(curve))]
for j in range(17):
 a=j*math.pi/32;inset=.35*math.sin(a);heights=[]
 for p,normal in zip(curve,normals):
  q=p+normal*inset;hit=baseline.ray_cast(mm((q.x,-30,q.y)),Vector((0,1,0)),.06)[0]
  heights.append(min(hit.y*1000-.006 if hit else -13.54,floor_y-.65)+.35*(1-math.cos(a)))
 rings.append(ring(inset,heights))
rings.append(ring(.35,[floor_y]*len(curve)))
n=len(curve);v=[p for row in rings for p in row]
f=[tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]+[(r*n+j,r*n+(j+1)%n,(r+1)*n+(j+1)%n,(r+1)*n+j) for r in range(len(rings)-1) for j in range(n)]
cut=mesh('Safety relief | rounded full-stroke pocket operand',v,f,bpy.data.objects['Slide • translation'],SLIDE,None)
cut.data.materials.append(steel);cut.data.materials.append(dark)
for p in cut.data.polygons:p.material_index=1
weights=cut.data.attributes.new('bevel_weight_edge','FLOAT','EDGE');edges=[]
for e in cut.data.edges:
 if all(abs((cut.matrix_world@cut.data.vertices[j].co).y*1000-floor_y)<.0001 for j in e.vertices):weights.data[e.index].value=1.;edges.append(e.index)
be=cut.modifiers.new('Safety pocket • native floor bevel','BEVEL');be.limit_method='WEIGHT';be.width=.00022/abs(cut.matrix_world.determinant())**(1/3);be.segments=12;be.harden_normals=True;be.mark_sharp=True;be.use_clamp_overlap=False
bpy.context.view_layer.objects.active=cut
while cut.modifiers[0]!=be:bpy.ops.object.modifier_move_up(modifier=be.name)
apply_geometry(cut)
boolean(shell,cut,'DIFFERENCE','Rounded full-stroke pocket',remove=False,solver='EXACT');cut.hide_render=True;cut.hide_set(True);cut['PM geometry helper']=True
cleanup(shell)
if shell.data.has_custom_normals:shell.data.normals_split_custom_set([(0,0,0)]*len(shell.data.loops))
weighted(shell)
details['safety_pocket']=dict(operand=cut.name,outline_mm=[list(p) for p in curve],floor_y_mm=floor_y,beveled_edges=len(edges),bevel_mm=.22,upper_lip_radius_mm=.35,outline_corner_radii_mm=corner_radii,editability='Rounded cutter upper lip, native Blender floor bevel; baked editable slide plus hidden tool; clean v10 retained')
print('PM_V11_POCKET',len(curve),len(edges),flush=True)

# 5. Uncut traced spur, then five annular-sector grooves converging on one point.
lib=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/90_История_и_резервные_копии/Скрипты_пистолета/build_pm_v4.py')
parsed=ast.parse(lib.read_text(encoding='utf-8'));exec(compile(ast.Module(body=[p for p in parsed.body if isinstance(p,ast.FunctionDef) and p.name=='smooth2'],type_ignores=[]),'PM_curve_helper','exec'))
hp=[(.826,1.230),(.809,1.280),(.857,1.350),(.883,1.421),(.910,1.458),(.946,1.469),(.979,1.456),(.994,1.431),(.986,1.402),(.953,1.367),(.889,1.278)]
bpy.data.objects.remove(hammer,do_unlink=True);profile=smooth2(hp,6,True);n=len(profile);mw=rig.matrix_world
v=[mw@Vector((x,y,z)) for y in (-.0365,.0365) for x,z in profile];f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
hammer=mesh('Hammer | rounded spur with broad side chamfers',v,f,bpy.data.objects['Hammer • pivot'],BODY,bevel=.50);apply_geometry(hammer)
sample=[mw@Vector((x,0,z)) for x,z in hp[4:7]];p0=Vector((sample[0].x,sample[0].z))*1000
a=np.array([[2*(p.x*1000-p0.x),2*(p.z*1000-p0.y)] for p in sample[1:]]);b=np.array([(p.x*1000)**2+(p.z*1000)**2-p0.length_squared for p in sample[1:]])
center=Vector(np.linalg.solve(a,b));uncut=tree(hammer);radial=[]
for i in range(5):
 angle=math.radians(138-i*24);d=Vector((math.cos(angle),0,math.sin(angle)));start=mm((center.x,0,center.y))+d*.012;hit=uncut.ray_cast(start,-d,.015)[0]
 if hit is None:raise RuntimeError('Radial hammer sector misses the traced crest')
 radius=(hit-mm((center.x,0,center.y))).length*1000;inner=radius-1.35;half=math.radians(5.2)
 outline=[(center.x+r*math.cos(angle+t),center.y+r*math.sin(angle+t)) for r,tt in ((12,[half-j*2*half/12 for j in range(13)]),(inner,[-half+j*2*half/12 for j in range(13)])) for t in tt]
 cutter=prism('temporary radial hammer groove',outline,-4.2,4.2,None,BODY,None,.035);apply_geometry(cutter);boolean(hammer,cutter,'DIFFERENCE','Radial traction groove')
 radial.append(dict(angle_deg=math.degrees(angle),crest_mm=list(hit*1000),radius_mm=radius,depth_mm=1.35,half_angle_deg=5.2))
cleanup(hammer);weighted(hammer);details['hammer']=dict(center_xz_mm=list(center),grooves=radial,groove_count=5,land_count=4)
print('PM_V11_HAMMER',list(center),flush=True)

# 6. Deepen the actual socket/slot floor and its walls, retaining the original
# drive outlines and screw bodies. Pins without a drive remain pins.
drives=[]
for o in [p for p in bpy.data.objects if p.type=='MESH' and is_drive(p)]:
 apply_geometry(o);lo,hi=bounds(o);center=Vector(tuple((a+b)/2 for a,b in zip(lo,hi)))
 if o.name=='Backstrap | slotted screw':normal=Vector((1,0,0));mask=2.02
 elif 'upper anchor' in o.name or 'elevation adjustment' in o.name:normal=Vector((0,0,1));mask=1.60 if 'anchor' in o.name else 3.15
 else:normal=Vector((0,1 if 'cheek fastener 1 ' in o.name or 'windage adjustment' in o.name else -1,0));mask=1.72 if 'fastener' in o.name else 3.15
 if o.name.startswith('Mount |'):mask=1.72
 coords=[o.matrix_world@v.co for v in o.data.vertices];front=max(p.dot(normal) for p in coords);back=min(p.dot(normal) for p in coords);thickness=(front-back)*1000
 t=tree(o);probe=center+normal*(front-center.dot(normal)+.002);hit=t.ray_cast(probe,-normal,.005)[0]
 if hit is None:raise RuntimeError('Missing screw drive floor '+o.name)
 floor=hit.dot(normal);old_depth=(front-floor)*1000;new_depth=max(old_depth+.13,min(.95,thickness*.76))
 # The already deep, thin rear head needs a little backing inside its existing
 # seat. Its visible face, drive outline and outer diameter remain fixed.
 backing=max(.10,min(.20,thickness*.20));extension=max(0,new_depth+backing-thickness)
 inv=o.matrix_world.inverted();moved=0
 if extension:
  for i,(v,p) in enumerate(zip(o.data.vertices,coords)):
   q=p.dot(normal)
   if q<floor-.000001:
    p=p-normal*(extension/1000*min(1,(floor-q)/max(1e-8,floor-back)));v.co=inv@p;coords[i]=p
  thickness+=extension
 for v,p in zip(o.data.vertices,coords):
  q=p.dot(normal);r=(p-center-normal*(p-center).dot(normal)).length*1000
  if r<mask and q>=floor-.000008 and front-q>1e-8:
   delta=(front-q)*(new_depth/old_depth-1);v.co=inv@(p-normal*delta);moved+=1
 o.data.update()
 if o.data.has_custom_normals:o.data.normals_split_custom_set([(0,0,0)]*len(o.data.loops))
 weighted(o);drives.append(dict(object=o.name,normal=list(normal),center_mm=list(center*1000),front_mm=front*1000,old_depth_mm=old_depth,new_depth_mm=new_depth,backing_mm=thickness-new_depth,inward_backing_extension_mm=extension,moved_vertices=moved))
details['drives']=drives;print('PM_V11_DRIVES',len(drives),flush=True)

# The flush witness follows the altered surface rather than floating over it.
w=bpy.data.objects['Safety | flush red witness enamel'];t=tree(shell);inv=w.matrix_world.inverted()
for v in w.data.vertices:
 p=w.matrix_world@v.co;hit,normal,_,_=t.ray_cast(Vector((p.x,-.030,p.z)),Vector((0,1,0)),.060)
 if hit:v.co=inv@(hit+normal*.000006)
w.data.update()
for name,value in unchanged.items():assert fingerprint(bpy.data.objects[name])==value,'Unrequested change '+name
previous=json.loads((ROOT/'review_v10/Проверки/revision_manifest.json').read_text(encoding='utf-8'))
manifest=dict(previous);manifest.update(revision='v11',parent_geometry=str(SOURCE),parent_sha256=SOURCE_HASH,unchanged_fingerprints=unchanged,unchanged_meshes=len(unchanged),repairs=details,
 changes=['Устранён диагональный излом нормалей на обеих плоскостях рамки','Основа и семь зубцов планки объединены без совпадающих боковых граней','Прорези предохранителя горизонтальные; лепесток и выемка скруглены bevel','Существующие шлицы всех 13 винтов и регулировок углублены; винты сохранены','Пять вырезов курка направлены радиально к центру округлой части'])
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');(OUT/'Проверки/repairs_geometry.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('engraving.json','controls_geometry.json','body_geometry.json'):(OUT/'Проверки'/name).write_bytes((ROOT/'review_v10/Проверки'/name).read_bytes())
rig['Revision']='v11 — local surface and traction repairs, manual controls';S.frame_set(1);bpy.context.view_layer.update()
for o in bpy.context.selected_objects:o.select_set(False)
rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v11.blend'));assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_V11_SAVED',len(unchanged),flush=True)
