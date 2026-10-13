"""Four owner corrections on the saved artistic PM v09; preserve paint/marks.

World-space metres, closed editable meshes, visual controls only. No game export.
"""
from pathlib import Path
import hashlib,json,math,struct,sys
import bpy,bmesh,addon_utils
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v10'
for folder in ('01_ПМ','02_Крепление','03_Коллиматор','Превью','Проверки'):(OUT/folder).mkdir(parents=True,exist_ok=True)
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
body_details=json.loads((ROOT/'work/body_geometry_v10.json').read_text(encoding='utf-8'))
bpy.context.preferences.use_preferences_save=False;addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
rig=bpy.data.objects['PM_CONTROLS • select me'];slide=bpy.data.objects['Slide • translation'];mag=bpy.data.objects['Magazine • extraction']
mount=bpy.data.objects['PM_OpticMount • asset root'];optic=bpy.data.objects['PM_ReflexSight • asset root']
saved_action=rig.animation_data.action;rig.animation_data_clear()
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','Suppressor'):rig[key]=0.0
rig['SlideStop']=0.0;rig.id_properties_ui('SlideStop').update(min=0,max=1,description='Визуальное нажатие лепестка затворной задержки вниз')
bpy.context.view_layer.update()
BODY=bpy.data.collections['01 • Frame & bakelite'];SLIDE=bpy.data.collections['02 • Slide assembly'];MOUNT=bpy.data.collections['08 • Optic mount — separate asset']
steel=bpy.data.materials['Check | satin neutral metal'];dark=bpy.data.materials['Check | recess dark grey']
shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear'];catch=bpy.data.objects['MagCatch • pivot'];safe=bpy.data.objects['Safety • pivot']
details={};changed_names=set()

def fingerprint(o):
    h=hashlib.sha256()
    for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
    for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
    h.update(str(tuple(tuple(r) for r in o.matrix_local)).encode());h.update((o.parent.name if o.parent else '').encode());return h.hexdigest()

unchanged={o.name:fingerprint(o) for o in bpy.data.objects if o.type=='MESH' and not o.get('PM engraving helper') and not o.name.startswith(('Mount |','MagCatch |','Safety |','Slide catch |','Catch |','Reflex | K1 internal rail fitting pad')) and o!=shell}

def remove(prefixes):
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes):changed_names.add(o.name);bpy.data.objects.remove(o,do_unlink=True)

def mm(v):return Vector(tuple(x/1000 for x in v))

def make_mesh(name,vertices,faces,collection,owner,material=steel,bevel_mm=0,smooth=True):
    inv=owner.matrix_world.inverted() if owner else Matrix.Identity(4)
    data=bpy.data.meshes.new(name);data.from_pydata([tuple(inv@p) for p in vertices],[],faces);data.update()
    bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle(0)>.60:e.smooth=False
    bm.to_mesh(data);bm.free();o=bpy.data.objects.new(name,data);collection.objects.link(o)
    if owner:o.parent=owner;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Identity(4)
    bpy.context.view_layer.update()
    if material:data.materials.append(material)
    for p in data.polygons:p.use_smooth=smooth and len(p.vertices)<=4
    if bevel_mm:
        mod=o.modifiers.new('Local edge radii','BEVEL');mod.width=bevel_mm/1000/abs(o.matrix_world.determinant())**(1/3);mod.segments=8;mod.harden_normals=True
    mod=o.modifiers.new('Local face-area normals','WEIGHTED_NORMAL');mod.keep_sharp=True;mod.weight=45
    o['Geometry revision']='v10 — owner controls and rail corrections';changed_names.add(o.name);return o

def rounded(x0,x1,y0,y1,r,steps=20):
    return [(x+r*math.cos(a+j*math.pi/2/steps),y+r*math.sin(a+j*math.pi/2/steps)) for x,y,a in ((x1-r,y1-r,0),(x0+r,y1-r,math.pi/2),(x0+r,y0+r,math.pi),(x1-r,y0+r,3*math.pi/2)) for j in range(steps)]

def prism_x(name,x0,x1,yz,collection,owner,bevel_mm=.12):
    n=len(yz);v=[mm((x,y,z)) for x in (x0,x1) for y,z in yz]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return make_mesh(name,v,f,collection,owner,bevel_mm=bevel_mm)

def prism_y(name,xz,y0,y1,collection,owner,material=steel,bevel_mm=.12):
    n=len(xz);v=[mm((x,y,z)) for y in (y0,y1) for x,z in xz]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return make_mesh(name,v,f,collection,owner,material,bevel_mm)

def slab(name,xy,z0,z1,collection,owner,bevel_mm=.12):
    n=len(xy);v=[mm((x,y,z)) for z in (z0,z1) for x,y in xy]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return make_mesh(name,v,f,collection,owner,bevel_mm=bevel_mm)

def tree(o):
    eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
    t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear();return t

def world_bounds(o):
    eo=o.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh();v=[eo.matrix_world@p.co for p in me.vertices];eo.to_mesh_clear()
    return [min(p[i] for p in v)*1000 for i in range(3)],[max(p[i] for p in v)*1000 for i in range(3)]

def boolean_cut(host,cutter,name,bake=True):
    bpy.context.view_layer.objects.active=host
    mod=host.modifiers.new(name,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='MANIFOLD';mod.object=cutter
    while host.modifiers.find(mod.name)>0 and (bake or host.modifiers[host.modifiers.find(mod.name)-1].type=='WEIGHTED_NORMAL'):bpy.ops.object.modifier_move_up(modifier=mod.name)
    if bake:
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    else:cutter.hide_render=True;cutter.hide_set(True);cutter['PM geometry helper']=True
    return mod

# 1. Remove the four little adapters and fit the rail directly to the main shoe.
remove(('Reflex | K1 internal rail fitting pad','Mount | continuous relieved rail spine','Mount | chamfered rail tooth','Mount | solid rail support pad'))
shoe=bpy.data.objects['Reflex | K1 relieved low cross-slot shoe'];z0=optic.matrix_world.translation.z*1000
fy=optic.matrix_world.to_3x3().col[1].length/optic.matrix_world.to_3x3().col[0].length
fz=optic.matrix_world.to_3x3().col[2].length/optic.matrix_world.to_3x3().col[0].length
rail_yz=[(-7.70,124.45),(7.70,124.45),(7.70,z0+1.2*fz),(10.2*fy-.25,z0+3.7*fz-.25),(10.2*fy-.25,z0+3.7*fz+.02),(7.7*fy-.25,z0+4.8*fz-.25),(-7.7*fy+.25,z0+4.8*fz-.25),(-10.2*fy+.25,z0+3.7*fz+.02),(-10.2*fy+.25,z0+3.7*fz-.25),(-7.70,z0+1.2*fz)]
# A broad neck continues under the cross slots; the tooth crowns fill the shoe.
prism_x('Mount | continuous relieved rail spine',-36.33772,17.51072,rounded(-7.70,7.70,124.45,z0+1.2*fz-.18,.13,16),MOUNT,mount,.08)
for i in range(7):
    x=-36.05851+i*7.977546;prism_x('Mount | chamfered rail tooth %02d'%i,x,x+5.26518,rail_yz,MOUNT,mount,.08)
for i,x in enumerate((-15.87531,3.03147)):
    slab('Mount | solid rail support pad %d'%i,rounded(x-2.52,x+2.52,-7.52,7.52,.32,16),123.8,124.80,MOUNT,mount,.08)
mount['Installation']='v10: direct fit into the main optic shoe, widened rail, no narrow internal prongs'
details['rail']=dict(width_mm=2*(10.2*fy-.25),top_z_mm=z0+4.8*fz-.25,bottom_z_mm=124.45,internal_prongs_removed=4,clearance_mm=.25,main_shoe=shoe.name)
print('PM_V10_RAIL',details['rail'],flush=True)

# 2. Heel catch below the floorplate, with cut valleys in its half-round lip.
remove(('MagCatch |',));floor=bpy.data.objects['Magazine | aligned thin floorplate and extraction toe'];floor_lo,floor_hi=world_bounds(floor)
catch.animation_data_clear();matrix=catch.matrix_world.copy();matrix.translation=mm((72.2,0,20.0));catch.matrix_world=matrix
driver=catch.driver_add('rotation_euler',1).driver;driver.expression='-v*0.20';var=driver.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["MagCatch"]'
radius=4.85;cz=floor_lo[2]-3.5+radius;cx=floor_hi[0]+radius+.10
# Profile samples explicitly include both shoulders of each recessed flute.
centers=[-math.pi+.30+i*(math.pi-.60)/8 for i in range(9)];angles=sorted(set([-math.pi+j*math.pi/256 for j in range(257)]+[a+t for a in centers for t in (-.038,-.028,-.014,0,.014,.028,.038)]))
ys=[-6.12,-5.98,5.98,6.12];v=[];f=[];N=len(angles);W=len(ys)
def groove(a):
    return max((.42*.5*(1+math.cos(math.pi*abs(a-c)/.038)) for c in centers if abs(a-c)<.038),default=0)
for inner in (False,True):
    for y in ys:
        for a in angles:
            r=radius-.85 if inner else radius-groove(a)
            v.append(mm((cx+r*math.cos(a),y,cz+r*math.sin(a))))
def idx(layer,j,k):return layer*W*N+j*N+k
for layer in (0,1):
    for j in range(W-1):
        for k in range(N-1):f.append((idx(layer,j,k),idx(layer,j,k+1),idx(layer,j+1,k+1),idx(layer,j+1,k)))
for j in (0,W-1):
    for k in range(N-1):f.append((idx(0,j,k),idx(0,j,k+1),idx(1,j,k+1),idx(1,j,k)))
for k in (0,N-1):
    for j in range(W-1):f.append((idx(0,j,k),idx(0,j+1,k),idx(1,j+1,k),idx(1,j,k)))
thumb=make_mesh('MagCatch | half-round folded ribbed heel',v,f,BODY,catch,bevel_mm=0)
spring=[(70.5,19.0),(71.4,20.4),(72.4,20.4),(73.25,19.0),(73.4,13),(73.05,7.5),(72.5,3.8),(73.8,1.8),(73.5,.4),(72.65,1.1),(71.0,2.8),(70.15,8),(70.25,14)]
prism_y('MagCatch | flat retaining spring',spring,-3.0,3.0,BODY,catch,bevel_mm=.15)
lip=slab('MagCatch | forward retaining lip',rounded(floor_hi[0]-1.65,floor_hi[0]+1.45,-5.4,5.4,.22,16),floor_lo[2]-.85,floor_lo[2]-.08,BODY,catch,.06)
thumb['Traction']='Nine recessed radial flutes, 0.42 mm deep; no added traction ribs'
details['magcatch']=dict(thumb=thumb.name,lip=lip.name,floorplate=floor.name,protrusion_target_mm=3.5,groove_depth_mm=.42,groove_count=9,
    groove_centers=centers,arc_center_mm=[cx,0,cz],radius_mm=radius,release='Toward +X, the backstrap, via a visual pivot')
print('PM_V10_MAGCATCH',cx,cz,floor_lo[2]-3.5,flush=True)

# 3. A thin continuous curved leaf, with recessed grooves in its thumb surface.
remove(('Slide catch |','Catch | fine'))
pivot=bpy.data.objects.new('SlideStop • pivot',None);BODY.objects.link(pivot);pivot.parent=rig;pivot.location=rig.matrix_world.inverted()@mm((26.4,0,95.0))
driver=pivot.driver_add('rotation_euler',1).driver;driver.expression='-v*0.11';var=driver.variables.new();var.name='v';var.type='SINGLE_PROP';var.targets[0].id=rig;var.targets[0].data_path='["SlideStop"]'
bpy.context.view_layer.update()
path=[Vector((-11.25,95.8)),Vector((-11.25,93.1))]
A,B,C,D=map(Vector,[(-11.25,93.1),(-11.25,91.6),(-14.2,90.55),(-16.2,90.55)])
path += [(1-t)**3*A+3*(1-t)**2*t*B+3*(1-t)*t*t*C+t**3*D for t in (j/180 for j in range(1,181))]
dist=[0]
for a,b in zip(path,path[1:]):dist.append(dist[-1]+(b-a).length)
slots=[3.8,4.6,5.4,6.2,7.0];cross=[-1,-.88,0,.88,1];v=[];f=[];P=len(path);Q=len(cross);samples=[]
for layer in (0,1):
    for j,p in enumerate(path):
        tangent=(path[min(j+1,P-1)]-path[max(0,j-1)]).normalized();normal=Vector((tangent.y,-tangent.x))
        halfwidth=6.25+1.1*math.sin(math.pi*dist[j]/dist[-1])
        cut=max((.19*.5*(1+math.cos(math.pi*abs(dist[j]-c)/.18)) for c in slots if abs(dist[j]-c)<.18),default=0)
        for u in cross:
            side=.525-cut*(1 if abs(u)<=.88 else 0) if layer==0 else -.525
            yy,zz=p+normal*side;v.append(mm((18.4+u*halfwidth,yy,zz)))
        if layer==0:
            for k,c in enumerate(slots):
                if abs(dist[j]-c)<.026:
                    samples.append(dict(slot=k,point_mm=[18.4,*list(p+normal*.525)],normal=[0,normal.x,normal.y],expected_depth_mm=cut))
def leafidx(layer,j,k):return layer*P*Q+j*Q+k
for layer in (0,1):
    for j in range(P-1):
        for k in range(Q-1):f.append((leafidx(layer,j,k),leafidx(layer,j,k+1),leafidx(layer,j+1,k+1),leafidx(layer,j+1,k)))
for j in (0,P-1):
    for k in range(Q-1):f.append((leafidx(0,j,k),leafidx(0,j,k+1),leafidx(1,j,k+1),leafidx(1,j,k)))
for k in (0,Q-1):
    for j in range(P-1):f.append((leafidx(0,j,k),leafidx(0,j+1,k),leafidx(1,j+1,k),leafidx(1,j,k)))
leaf=make_mesh('Slide catch | curved thin thumb leaf',v,f,BODY,pivot,bevel_mm=0)
leaf['Traction']='Five recessed grooves across the curved thumb face; 1.05 mm sheet, not a button'
details['slidestop']=dict(leaf=leaf.name,pivot=pivot.name,thickness_mm=1.05,groove_count=5,groove_depth_mm=.19,groove_samples=samples)
print('PM_V10_SLIDESTOP',len(v),len(samples),flush=True)

# 4. A more pronounced thumb wedge, in a true relieved envelope of its stroke.
remove(('Safety | tapered oval pivot plate','Safety | beveled tapered thumb flag','Safety | ribbed wedge on thumb flag','Safety | seated dark oval floor'))
poly=[(50.5,107.65),(51.65,106.9),(53.25,106.75),(59.8,110.0),(63.7,111.1),(65.0,112.55),(64.8,114.15),(63.35,115.45),(61.5,115.8),(59.75,115.15),(52.0,110.15),(50.45,109.05)]
baseplate=prism_y('Safety | beveled tapered thumb flag',poly,-13.95,-12.55,SLIDE,safe,bevel_mm=.25)
pad_poly=[(50.85,107.65),(52.1,107.30),(57.1,110.50),(57.6,111.55),(56.5,112.10),(51.05,109.1)]
n=len(pad_poly);v=[mm((x,-13.7,z)) for x,z in pad_poly]+[mm((x,-(15.45+max(0,min(1,(57.2-x)/6.3))*1.9),z)) for x,z in pad_poly]
f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
pad=make_mesh('Safety | prominent grooved thumb wedge',v,f,SLIDE,safe,bevel_mm=.055)
axis=Vector((.84,.54));side=Vector((-axis.y,axis.x));origin=Vector((51.6,108.3))
for i in range(7):
    c=origin+axis*(.35+i*.70);outline=[tuple(c+axis*a+side*b) for a,b in ((-.14,-2.2),(.14,-2.2),(.14,2.2),(-.14,2.2))]
    # The cutter stops 0.30 mm behind the local outer wedge surface.
    inside_y=-(15.45+max(0,min(1,(57.2-c.x)/6.3))*1.9)+.30
    cut=prism_y('temporary safety negative groove',outline,-20,inside_y,SLIDE,None,None,0)
    boolean_cut(pad,cut,'Recessed thumb groove %02d'%i)
pad['Traction']='Seven actual cut grooves in the raised thumb wedge'
bpy.context.view_layer.update();mw=safe.matrix_world.copy();pivot_world=mw.translation.copy()
# Dense stroke samples and a circular margin make a smooth swept outline.
points=[]
for value in [j/16 for j in range(17)]:
    theta=.91*value
    for x,z in poly:
        d=mm((x,0,z))-Vector((pivot_world.x,0,pivot_world.z));xx=pivot_world.x+d.x*math.cos(theta)+d.z*math.sin(theta);zz=pivot_world.z-d.x*math.sin(theta)+d.z*math.cos(theta)
        for j in range(24):
            a=2*math.pi*j/24;points.append((xx*1000+1.0*math.cos(a),zz*1000+1.0*math.sin(a)))
def hull(points):
    q=sorted(set(points));cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[]
    for p in q:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(q):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]
pocket=hull(points);baseline=tree(shell);surface=[];floor_samples=[]
center=sum((Vector(p) for p in pocket),Vector((0,0)))/len(pocket)
xz=[tuple(center)]+[tuple(center+(Vector(p)-center)*(r/12)) for r in range(1,13) for p in pocket]
back_y=-11.28
for x,z in xz:
    hit,_,_,_=baseline.ray_cast(mm((x,-30,z)),Vector((0,1,0)),.050)
    if hit is None:continue
    inner,_,_,_=baseline.ray_cast(hit+Vector((0,.00001,0)),Vector((0,1,0)),.006)
    depth=back_y-hit.y*1000
    if depth<.025:continue # The rounded crown already clears the entire flag.
    if inner is not None and inner.y*1000<back_y+.15:
        raise RuntimeError('Planar safety pocket would breach the visual slide wall at '+str((x,z,inner.y*1000)))
    surface.append(hit.y*1000)
    floor_samples.append(dict(point_mm=[x,hit.y*1000,z],depth_mm=depth))
# A single flat floor avoids the jagged relief caused by following triangulated
# skin samples. The rounded crown above this plane already leaves free space.
cut=prism_y('Safety relief | full-stroke pocket operand',pocket,-30,back_y,SLIDE,slide,None,0)
cut.data.materials.append(steel);cut.data.materials.append(dark)
for p in cut.data.polygons:p.material_index=1
boolean_cut(shell,cut,'CONTROLS | full safety-stroke recess',bake=False)
if dark.name not in [m.name for m in shell.data.materials]:shell.data.materials.append(dark)
for i,material in enumerate(shell.data.materials):
    if material is None:shell.data.materials[i]=dark
# Tiny physical chamfers around the cut preserve a smooth, readable recess.
mod=shell.modifiers.new('Control pocket • rounded machined edge','BEVEL');mod.width=.00012/abs(shell.matrix_world.determinant())**(1/3);mod.segments=6;mod.limit_method='ANGLE';mod.angle_limit=.65;mod.harden_normals=True;mod.mark_sharp=True
while shell.modifiers.find(mod.name)>0 and shell.modifiers[shell.modifiers.find(mod.name)-1].type=='WEIGHTED_NORMAL':bpy.ops.object.modifier_move_up(modifier=mod.name)
# Keep the existing witness enamel flush on the reshaped crown, clear of the
# pocket edge. It is an open painted surface, not a raised mechanical button.
bpy.context.view_layer.update();witness=bpy.data.objects['Safety | flush red witness enamel'];skin=tree(shell)
points=[witness.matrix_world@v.co for v in witness.data.vertices];center=sum(points,Vector())/len(points);inv=witness.matrix_world.inverted()
for v,p in zip(witness.data.vertices,points):
    p.x+=.0482-center.x;p.z+=.1167-center.z
    hit,normal,_,_=skin.ray_cast(Vector((p.x,-.030,p.z)),Vector((0,1,0)),.060)
    if hit is None:raise RuntimeError('Witness mark has no slide surface')
    v.co=inv@(hit+normal*.000006)
witness.data.update()
details['safety']=dict(flag=baseplate.name,pad=pad.name,pocket=pocket,back_y_mm=back_y,groove_count=7,groove_depth_mm=.30,
    minimum_relief_mm=min(s['depth_mm'] for s in floor_samples),outline_margin_mm=1.0,thumb_outer_y_mm=-17.35,driver_angle_rad=.91,
    floor_samples=floor_samples,relief='Flat machined pocket floor; existing rounded crown clears the upper part of the swept envelope')
print('PM_V10_SAFETY',len(pocket),min(surface),max(surface),back_y,flush=True)

# Persist the previous engraving reports: each mark retains its source and host.
previous=json.loads((ROOT/'review_v09/Проверки/revision_manifest.json').read_text(encoding='utf-8'))
engraving=json.loads((ROOT/'review_v09/Проверки/engraving.json').read_text(encoding='utf-8'))
(OUT/'Проверки/engraving.json').write_text(json.dumps(engraving,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Проверки/controls_geometry.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'Проверки/body_geometry.json').write_text(json.dumps(body_details,ensure_ascii=False,indent=2),encoding='utf-8')
manifest=dict(source=previous['source'],source_sha256=previous['source_sha256'],parent_geometry=body_details['parent_geometry'],parent_sha256=body_details['parent_sha256'],body_intermediate_sha256=SOURCE_HASH,
    revision='v10',changes=['Удалены внутренние усики прицела; планка расширена и утолщена под основной зажим','Фиксатор магазина выступает на 3,5 мм ниже пятки, имеет настоящие прорези и отклоняется к затыльнику','Затворная задержка — тонкий изогнутый лепесток с отрицательными прорезями и отдельным контролом','Предохранитель — выраженная выступающая площадка с прорезями; на затворе вырезана выемка всей траектории'],
    inherited_changes=previous['changes']+previous['inherited_changes'],texture_approval=False,brand='ЗОРИН',model='К-1',
    optic_sources=previous['optic_sources'],unchanged_fingerprints=unchanged,unchanged_meshes=len(unchanged),
    non_optic_geometry_unchanged=False,localized_paint_authorized=previous['localized_paint_authorized'],full_surface_texturing_approval=False,
    fit_note='Rail now fits the main shoe directly, owner supersedes earlier one-third-width request; length retained',controls=details,body=body_details)
manifest['changes']+=['Задняя часть затвора плавно спускается к затыльнику, переходы округлены','Продольные боковые расширения затвора с насечками от плеча до нижнего края с обеих сторон','На курке пять более глубоких широких вырезов и четыре промежуточных выступа','Стенки накладки уменьшены вдвое со стороны внутренней полости; наружная форма сохранена']
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
for name,expected in unchanged.items():assert fingerprint(bpy.data.objects[name])==expected,'Unrequested base geometry changed: '+name
saved_action.use_fake_user=True;rig.animation_data_clear()
# Owner preference: manual controls, preserve older actions without a new demo.
S.frame_set(1);bpy.context.view_layer.update();rig['Revision']='v10 — corrected controls and direct rail fit'
note=bpy.data.texts.new('ПМ v10 • проверка рычагов')
note.write('Рельсы под основной зажим без внутренних усиков. Фиксатор ниже пятки на 3,5 мм, с отрицательными канавками; MagCatch идёт к затыльнику.\nSlideStop — визуальное нажатие тонкого лепестка вниз. Предохранитель имеет выступающую площадку и реальную выемку полного хода.\nЭто художественная геометрия и постановочные контролы; не конструкторская или физическая модель. Клейма и локальный UCUPaint v09 сохранены.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v10.blend'))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_V10_SAVED',len(unchanged),flush=True)
