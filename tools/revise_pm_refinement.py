"""PM v5 -> editable reference-led geometry v06. No UV, painting or game export."""
from pathlib import Path
import ast, hashlib, json, math, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from math import sin, cos, pi

ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement'
OUT=ROOT/'review_v06'; OUT.mkdir(parents=True,exist_ok=True)
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
SOURCE=Path(bpy.data.filepath)
SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
S=bpy.context.scene; S.frame_set(1); bpy.context.view_layer.update()
# Only import modelling helpers; never replay the old scene generator.
parsed=ast.parse((LIB/'90_История_и_резервные_копии/Скрипты_пистолета/build_pm_v4.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in parsed.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'PM_helpers','exec'))
BODY=bpy.data.collections['01 • Frame & bakelite']; SLIDE=bpy.data.collections['02 • Slide assembly']
STUDIO=bpy.data.collections['05 • Studio']; CTRL=bpy.data.collections['00 • CONTROLS']
rig=bpy.data.objects['PM_CONTROLS • select me']; slide=bpy.data.objects['Slide • translation']
hammer=bpy.data.objects['Hammer • pivot']; trigger=bpy.data.objects['Trigger • pivot']; safe=bpy.data.objects['Safety • pivot']
saved_action=rig.animation_data.action if rig.animation_data else None
saved_scale=rig.scale.copy(); saved_loc=rig.location.copy()
rig.animation_data_clear(); rig.scale=(1,1,1); rig.location=(0,0,0)
for k in ('Slide','Hammer','Trigger','Safety','Magazine','Suppressor'):rig[k]=0.0
bpy.context.view_layer.update()
steel=bpy.data.materials['01 | Bluing · polished steel']; edge=bpy.data.materials['02 | Machined steel']
dark=bpy.data.materials['03 | Recesses · charcoal']; bake=bpy.data.materials['04 | Oxblood bakelite · mottled resin']
knurlmat=bpy.data.materials['05 | Bakelite checkering']
shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear']
grip=bpy.data.objects['Bakelite | one-piece rounded grip']
changed=[]
def note(name):changed.append(name);print('PM_REVISION',name,flush=True)
def erase(prefixes):
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes):delete(o)
def flat_material(name,color,metal=0,rough=.34):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
    return m
def apply_bool(obj,cutter,label):
    bpy.context.view_layer.objects.active=obj
    md=obj.modifiers.new(label,'BOOLEAN');md.operation='DIFFERENCE';md.solver='FLOAT' if obj==shell or obj.name=='Frame | traced flowing silhouette' else 'EXACT';md.object=cutter
    while obj.modifiers[0]!=md:bpy.ops.object.modifier_move_up(modifier=md.name)
    bpy.ops.object.modifier_apply(modifier=md.name);delete(cutter)
def weighted(obj):
    for m in list(obj.modifiers):
        if m.type=='WEIGHTED_NORMAL':obj.modifiers.remove(m)
    md=obj.modifiers.new('Local face-area normals','WEIGHTED_NORMAL');md.keep_sharp=True;md.mode='FACE_AREA';md.weight=50
def bevel_local(obj,width=.002,segments=6):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.normal_update()
    weights=obj.data.attributes.get('bevel_weight_edge') or obj.data.attributes.new('bevel_weight_edge','FLOAT','EDGE')
    selected=[]
    for e in bm.edges:
        if len(e.link_faces)!=2:continue
        if e.calc_face_angle()<.42:continue
        if all(-.287<v.co.x<.078 and v.co.y>.020 and v.co.z>1.35 for v in e.verts):selected.append(e.index)
    for i in selected:weights.data[i].value=1.0
    bm.free()
    md=obj.modifiers.new('Window lip • local chamfer','BEVEL');md.limit_method='WEIGHT';md.width=width;md.segments=segments;md.harden_normals=True
    weighted(obj)
def outline_solid(name,points,width,mat,collection,owner,bevel=.003,y=0,smooth=0):
    o=extrude(name,points,width,mat,collection,owner,bevel,y=y,smooth=smooth)
    for m in o.modifiers:
        if m.type=='BEVEL':m.segments=6;m.harden_normals=True
    clean(o);return o

# Broad machined shoulders replace the featureless half-elliptic roof, while
# preserving the muzzle skirt, open underside, serrations and rear recess.
def shoulder_remap(co):
    x,y,z=co; factor=math.sqrt(max(.002,1-(max(0,x-.790)/.205)**2)) if x>.790 else 1.0
    z0=1.201+(1.393333333-1.201)*factor
    if z<=z0 or abs(y)<1e-6:return co
    yn=min(1.0,abs(y)/.150); old=math.sqrt(max(0,1-yn*yn))
    # Planar shoulder, with a small rounded crown above it and gentle roll-offs.
    if yn>.63:new=.318+(1.0-yn)/.37*.410
    else:new=1.0-.272*(yn/.63)**2
    top_weight=max(0,min(1,(z-z0)/(.135*factor)))
    co.z += (new-old)*.135*factor*top_weight
    return co
erase(('Crown tangent seam','Fine top rib','Safety wear |'))
note('Затвор: широкие верхние фаски, сохранены нижний профиль и сквозной кожух')

# A wider octagonal port and a separate recessed extractor track on the right.
bm=bmesh.new();bm.from_mesh(shell.data)
bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4])
bm.to_mesh(shell.data);bm.free();shell.data.update()
port_profile=[(-.270,1.398),(-.247,1.371),(.032,1.371),(.060,1.397),(.060,1.576),(.034,1.604),(-.243,1.604),(-.270,1.576)]
c=outline_solid('temporary widened port',port_profile,.294,None,SLIDE,None,.003,y=.173)
apply_mods(c);apply_bool(shell,c,'Reference ejection port')
track=[(.067,1.448),(.215,1.448),(.235,1.456),(.235,1.476),(.218,1.485),(.067,1.485)]
c=outline_solid('temporary recessed extractor seat',track,.111,None,SLIDE,None,.003,y=.155)
apply_mods(c);apply_bool(shell,c,'Extractor seat')
# Boolean operates on the original clean, planar cut surfaces. Deform the
# retained roof only afterwards, so the solver cannot discard distant caps.
for v in shell.data.vertices:shoulder_remap(v.co)
shell.data.update()
bevel_local(shell,.0024,6)
extractor=outline_solid('Extractor | recessed beveled body',[(.065,1.452),(.205,1.452),(.227,1.461),(.219,1.477),(.074,1.477)],.026,edge,SLIDE,slide,.0016,y=.111)
hook=outline_solid('Extractor | visible stepped hook',[(.036,1.449),(.039,1.459),(.065,1.463),(.087,1.474),(.097,1.474),(.096,1.447),(.070,1.439),(.048,1.439)],.036,steel,SLIDE,slide,.0017,y=.116)
hook['Role']='Видимый художественный зацеп в задней стенке окна; не рабочая реконструкция механизма'
cylinder('Extractor | recessed retaining pin',(.205,.132,1.465),.010,.0024,steel,SLIDE,slide,'Y',.0008,96)
note('Окно: фаска кромки, канал выбрасывателя и отдельный видимый зацеп')

# Continuous real tube: stepped cylindrical chamber, bore and rounded muzzle.
erase(('Barrel | visual 93.5','Barrel | stepped'))
profile=[(-1.001,.0754),(-.997,.076),(-.269,.076),(-.243,.077),(-.215,.089),(-.196,.094),(.139,.094),(.155,.091),(.171,.082)]
n=192;verts=[];faces=[]
for x,r in profile:verts.extend((x,r*cos(2*pi*j/n),1.398333333+r*sin(2*pi*j/n)) for j in range(n))
inner_offset=len(verts)
for x,_ in profile:verts.extend((x,.055*cos(2*pi*j/n),1.398333333+.055*sin(2*pi*j/n)) for j in range(n))
for base in (0,inner_offset):
    for k in range(len(profile)-1):
        for j in range(n):faces.append((base+k*n+j,base+k*n+(j+1)%n,base+(k+1)*n+(j+1)%n,base+(k+1)*n+j))
for k in (0,len(profile)-1):
    for j in range(n):faces.append((k*n+j,k*n+(j+1)%n,inner_offset+k*n+(j+1)%n,inner_offset+k*n+j))
barrel=mesh('Barrel | stepped cylindrical chamber and open bore',verts,faces,edge,BODY,rig,.0012)
for f in barrel.data.polygons:f.use_smooth=True
note('Ствол: цилиндрическая поверхность в окне, уступ казённой части и открытый канал')

# Reference rear sight: a conforming foot and a tangible, irregular welded bead.
erase(('Rear sight |','Sight socket | Rear','Luminous point | Rear'))
def roof_yz(x,y):
    # Ray against the revised saved shell while the modelling root is identity.
    dg=bpy.context.evaluated_depsgraph_get(); eo=shell.evaluated_get(dg)
    me=eo.to_mesh();tree=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(f.vertices) for f in me.polygons]);eo.to_mesh_clear()
    return tree
roof_tree=roof_yz(0,0)
def rz(x,y):
    hit,_,_,_=roof_tree.ray_cast(Vector((x,y,1.8)),Vector((0,0,-1)),.65)
    return hit.z if hit else 1.525
points=[(.695,-.064),(.791,-.064),(.800,-.047),(.800,.047),(.791,.064),(.695,.064),(.684,.047),(.684,-.047)]
vv=[(x,y,rz(x,y)-.002) for x,y in points]+[(x,y,1.548) for x,y in points]
nn=len(points);ff=[tuple(range(nn-1,-1,-1)),tuple(range(nn,nn*2))]+[(j,(j+1)%nn,(j+1)%nn+nn,j+nn) for j in range(nn)]
mesh('Rear sight | foot seated into curved crown',vv,ff,steel,SLIDE,slide,.0018)
rear=cube('Rear sight | beveled twin-ear blade',(.749,0,1.566),(.050,.115,.067),steel,SLIDE,slide,.0035)
c=cube('temporary rear sight notch',(.749,0,1.593),(.075,.034,.055),None,SLIDE,None,.003)
apply_mods(c);apply_bool(rear,c,'Rear notch');weighted(rear)
def weld_bead(name,path,radius):
    # Closed tube woven along the actual surface; the lower half enters the host.
    vv=[];ff=[];count=12
    for i,p in enumerate(path):
        tangent=Vector(path[(i+1)%len(path)])-Vector(path[(i-1)%len(path)]);tangent.normalize()
        side=tangent.cross(Vector((0,0,1))).normalized();up=side.cross(tangent).normalized()
        r=radius*(1+.12*sin(i*1.91)+.05*sin(i*.713))
        for j in range(count):vv.append(tuple(Vector(p)+side*(r*cos(2*pi*j/count))+up*(r*.65*sin(2*pi*j/count))))
    for i in range(len(path)):
        for j in range(count):ff.append((i*count+j,i*count+(j+1)%count,((i+1)%len(path))*count+(j+1)%count,((i+1)%len(path))*count+j))
    obj=mesh(name,vv,ff,edge,SLIDE,slide);obj['Reference']='Сварной шов присланной художественной модели; штатная посадка настоящего ПМ отличается'
    return obj
seam=[]
for i,(x,y) in enumerate(points):
    nx,ny=points[(i+1)%len(points)]
    steps=18
    for k in range(steps):
        t=k/steps;px=x+(nx-x)*t;py=y+(ny-y)*t
        seam.append((px,py,rz(px,py)+.0007))
weld_bead('Rear sight | continuous irregular weld around foot',seam,.0041)
note('Целик: основание повторяет крышу, фаски ушей и отдельная непрерывная геометрия сварного шва')

# Broad side bevels and real cross-cut grooves on the thumb arc.
erase(('Hammer |',))
hp=[(.826,1.230),(.809,1.280),(.857,1.350),(.883,1.421),(.910,1.458),(.946,1.469),(.979,1.456),(.994,1.431),(.986,1.402),(.953,1.367),(.889,1.278)]
hm=outline_solid('Hammer | rounded spur with broad side chamfers',hp,.073,steel,BODY,hammer,.0064,smooth=6)
apply_mods(hm)
for i in range(7):
    x=.905+i*.0116;z=1.455+.012*math.sin(i*pi/6)
    c=cube('temporary rounded hammer groove',(x,0,z),(.0062,.092,.020),None,BODY,None,.0014)
    c.rotation_euler[1]=-.20;apply_mods(c);apply_bool(hm,c,'Thumb traction groove')
weighted(hm)
note('Курок: округлый гребень, широкие боковые фаски, скруглённые края семи поперечных пазов')

# A slim continuously curved trigger, with a deliberately cut-off, beveled tip.
erase(('Trigger |',))
tp=[(-.017,1.119),(-.059,1.117),(-.063,1.076),(-.079,1.024),(-.103,.973),(-.135,.928),(-.178,.892),(-.213,.876),(-.226,.870),(-.226,.857),(-.209,.851),(-.188,.860),(-.148,.888),(-.109,.928),(-.078,.975),(-.055,1.026),(-.035,1.080)]
tr=outline_solid('Trigger | flowing curved blade and beveled tip',tp,.055,steel,BODY,trigger,.0027,smooth=7)
note('Спуск: плавная вогнутая рабочая поверхность и гранёный округлённый кончик')

# Tapered oval flag; grooves are cut into its raised thumb pad.
erase(('Safety | rounded pivot','Safety | slim','Safety | raised'))
oval=[(.770+.069*cos(2*pi*j/128),1.396+.044*sin(2*pi*j/128)) for j in range(128)]
outline_solid('Safety | tapered oval pivot plate',oval,.018,steel,SLIDE,safe,.0023,y=-.157)
sp=[(.795,1.410),(.781,1.429),(.757,1.425),(.660,1.355),(.642,1.337),(.646,1.322),(.665,1.318),(.685,1.326),(.786,1.383)]
saf=outline_solid('Safety | beveled tapered thumb flag',sp,.025,steel,SLIDE,safe,.0039,y=-.173,smooth=6)
pad=outline_solid('Safety | ribbed wedge on thumb flag',[(.650,1.333),(.666,1.326),(.729,1.369),(.716,1.388)],.013,steel,SLIDE,safe,.0018,y=-.188,smooth=3)
for i in range(7):
    t=i/6;c=cube('temporary safety traction',(.662+.055*t,-.198,1.338+.039*t),(.022,.014,.0031),None,SLIDE,None,.0007)
    c.rotation_euler[1]=-.63;apply_mods(c);apply_bool(pad,c,'Flag traction')
weighted(pad)
note('Предохранитель: овальная площадка, клиновидный флажок, вырезанная насечка')

# Refine the owner's dense moulding locally, instead of destroying its surface
# with another global remesh. A raised upper palm swell is part of the mesh.
arr=np.empty(len(grip.data.vertices)*3,dtype=np.float32);grip.data.vertices.foreach_get('co',arr);arr=arr.reshape(-1,3)
x=arr[:,0];y=arr[:,1];z=arr[:,2]
swell=np.exp(-((x-.55)/.24)**2-((z-.925)/.18)**2)
side_weight=np.clip((np.abs(y)-.12)/.045,0,1)
arr[:,1]+=np.sign(y)*.012*swell*side_weight
# Tuck the upper front edge under the tang while keeping the lower passage.
arr[:,0]-=.014*np.exp(-((x-.315)/.13)**2-((z-.92)/.14)**2)
grip.data.vertices.foreach_set('co',arr.ravel());grip.data.update()
erase(('Bakelite | moulded palm-swell','Bakelite | checkering boundary','Highpoly | clean diamond','Bakelite | recessed emblem','Bakelite | emblem rim','Bakelite | moulded star','Grip | screw recess','Grip | slotted screw','Frame | lanyard eye'))
bpy.context.view_layer.update()
tree=BVHTree.FromPolygons([v.co for v in grip.data.vertices],[tuple(f.vertices) for f in grip.data.polygons])
def surface(x,z,side):
    hit,_,_,_=tree.ray_cast(Vector((x,side*.35,z)),Vector((0,-side,0)),.34)
    return hit.y if hit else side*.168
patch=[(.331,.737),(.455,.706),(.665,.738),(.808,.720),(.855,.526),(.883,.291),(.870,.090),(.684,.064),(.504,.073),(.445,.257),(.394,.509)]
ex,ez=.626,.410
for side in (-1,1):
    vv=[];ff=[];pitch=.0185;dx=.0090;dz=.0102
    for row in range(44):
        pz=.082+row*pitch
        for col in range(33):
            px=.316+col*pitch+(pitch*.5 if row%2 else 0)
            corners=[(px-dx,pz),(px,pz-dz),(px+dx,pz),(px,pz+dz)]
            if not all(inside(cx,cz,patch) for cx,cz in corners):continue
            if (px-ex)**2+(pz-ez)**2<.083**2:continue
            k=len(vv)
            for cx,cz in corners:vv.append((cx,surface(cx,cz,side)-side*.00055,cz))
            vv.append((px,surface(px,pz,side)+side*.0058,pz))
            ff.extend([(k,k+1,k+4),(k+1,k+2,k+4),(k+2,k+3,k+4),(k+3,k,k+4),(k+3,k+2,k+1,k)])
    obj=mesh('Grip checkering | sharp sculpted pyramids '+str(side),vv,ff,knurlmat,BODY,rig,.00035)
    clean(obj,True)
    ey=surface(ex,ez,side)
    cylinder('Grip emblem | recessed circular field '+str(side),(ex,ey+side*.0015,ez),.078,.004,bake,BODY,rig,'Y',.0015,128)
    torus('Grip emblem | molded circular lip '+str(side),(ex,ey+side*.004,ez),.070,.0024,bake,BODY,rig,'Y')
    star=[]
    for j in range(10):
        a=pi/2+j*pi/5;r=.047 if j%2==0 else .020
        star.append((ex+r*cos(a),ez+r*sin(a)))
    outline_solid('Grip emblem | five-point star '+str(side),star,.006,bake,BODY,rig,.0012,y=ey+side*.005)
    border=[]
    for i,(px,pz) in enumerate(patch):
        nx,nz=patch[(i+1)%len(patch)]
        for k in range(10):
            t=k/10;cx=px+(nx-px)*t;cz=pz+(nz-pz)*t;border.append((cx,surface(cx,cz,side)+side*.0002,cz))
    tube_curve('Grip | fine molded checkering perimeter '+str(side),border,.0009,bake,BODY,rig,True)
note('Накладка: цельный верхний наплыв, более глубокая насечка, убраны лишние боковые винты')

# The heel catch is fixed to the pistol. Its half-round folded sheet and ribs
# remain in place when the magazine and its floorplate are pulled out.
heel_frame=bpy.data.objects['Frame | traced flowing silhouette']
# The existing lower rim contains long concave faces. Keep those intact:
# triangulating them before this local FLOAT cut creates collinear slivers.
c=cube('temporary open heel catch recess',(.843,0,.113),(.183,.194,.262),None,BODY,None,.007)
apply_mods(c);apply_bool(heel_frame,c,'Open heel recess for visible folded catch');weighted(heel_frame)
catch=empty('MagCatch • pivot',BODY,(.785,0,.105));catch.parent=rig
rig['MagCatch']=0.0;rig.id_properties_ui('MagCatch').update(min=0,max=1,description='Визуальное отклонение защёлки в пятке рукоятки')
drive(catch,'rotation_euler',1,'MagCatch','v*0.22')
n=80;vv=[];ff=[]
for y in (-.076,.076):
    for inner in (False,True):
        for j in range(n+1):
            a=-pi*.54+j/n*pi*1.16
            # Seven rounded, radial traction ridges cut across the full width.
            ripple=(.0021*(.5+.5*cos(j/n*14*pi))**5) if not inner else 0
            r=(.067+ripple) if not inner else .053
            vv.append((.793+r*cos(a),y,.108+r*sin(a)))
N=n+1
for layer in (0,2):
    for j in range(n):ff.append((layer*N+j,layer*N+j+1,(layer+1)*N+j+1,(layer+1)*N+j))
for layer in (0,1):
    for j in range(n):ff.append((layer*N+j,layer*N+j+1,(layer+2)*N+j+1,(layer+2)*N+j))
for j in (0,n):ff.append((j,N+j,3*N+j,2*N+j))
mesh('MagCatch | half-round folded ribbed heel',vv,ff,steel,BODY,catch,.0013)
outline_solid('MagCatch | flat retaining spring',[(.769,.100),(.788,.122),(.810,.172),(.822,.276),(.807,.282),(.795,.177)],.095,steel,BODY,catch,.0015)
# Compact lanyard lug and real oval ring on the left lower moulding.
lug=outline_solid('Lanyard | molded mounting lug',[(.894,.094),(.943,.087),(.950,.144),(.905,.156)],.049,bake,BODY,rig,.007,y=-.174,smooth=4)
c=cylinder('temporary lanyard hole',(.922,-.174,.120),.012,.09,None,BODY,None,'Y',0,96)
apply_bool(lug,c,'Lanyard opening')
ring_points=[(.922+.035*cos(2*pi*j/96),-.207-.028*sin(2*pi*j/96),.110+.014*cos(2*pi*j/96)) for j in range(96)]
tube_curve('Lanyard | oval steel ring',ring_points,.0054,steel,BODY,rig,True)
note('Пятка: отдельная закруглённая рифлёная защёлка и боковое кольцо ремешка')

# Separate removable clamp/rail assembly, traced from the owner's sight mount.
MOUNT=coll('08 • Optic mount — separate asset'); OPTIC=coll('09 • Reflex sight — separate asset')
mount=empty('PM_OpticMount • asset root',MOUNT,(-.118,0,1.555));parent(mount,slide)
mount['Installation']='Художественное крепление по скриншотам владельца; следует за затвором'
mount['Owner proportions']='Планка около трети длины и ширины затвора; крепление над спусковым крючком, два винта'
rail_profile=[(-.050,1.612),(-.050,1.640),(-.038,1.668),(.038,1.668),(.050,1.640),(.050,1.612)]
def extrude_x(name,x0,x1,yz,mat,collection,owner,bevel=.0015):
    n=len(yz);vv=[(x,y,z) for x in (x0,x1) for y,z in yz]
    ff=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return mesh(name,vv,ff,mat,collection,owner,bevel)
cube('Mount | continuous relieved rail spine',(-.118,0,1.618),(.675,.068,.032),steel,MOUNT,mount,.003)
for i in range(7):
    x=-.452+i*.100
    extrude_x('Mount | chamfered rail tooth %02d'%i,x,x+.066,rail_profile,steel,MOUNT,mount,.0019)
for i,x in enumerate((-.199,.038)):
    path=[(-.173,1.347),(-.173,1.398),(-.164,1.455),(-.138,1.509),(-.097,1.558),(0,1.592),(.033,1.586),(.029,1.566),(0,1.571),(-.087,1.542),(-.118,1.502),(-.144,1.450),(-.154,1.398),(-.154,1.347)]
    extrude_x('Mount | fitted wraparound saddle %d'%i,x-.035,x+.035,path,steel,MOUNT,mount,.0020)
    cube('Mount | solid rail support pad %d'%i,(x,-.008,1.599),(.069,.066,.024),steel,MOUNT,mount,.0018)
side_plate=outline_solid('Mount | rounded two-screw clamp plate',[(-.247,1.366),(-.233,1.350),(.082,1.350),(.095,1.370),(.095,1.513),(-.247,1.513)],.022,steel,MOUNT,mount,.0037,y=-.174)
for i,x in enumerate((-.199,.038)):
    screw=cylinder('Mount | cross-slot fastener %d'%i,(x,-.194,1.431),.028,.018,edge,MOUNT,mount,'Y',.0024,128)
    apply_mods(screw)
    pp=[(x+dx,1.431+dz) for dx,dz in [(-.016,-.004),(-.004,-.004),(-.004,-.016),(.004,-.016),(.004,-.004),(.016,-.004),(.016,.004),(.004,.004),(.004,.016),(-.004,.016),(-.004,.004),(-.016,.004)]]
    c=outline_solid('temporary single cross-slot cutter',pp,.020,steel,MOUNT,None,.00055,y=-.203)
    apply_mods(c);apply_bool(screw,c,'Single cross slot');weighted(screw)
note('Отдельное крепление: короткая узкая планка около трети затвора, две скобы и два винта над спусковым крючком')

# Open reflex sight: actual window/transparent lens, adjustment drum, clamp,
# hood and small fasteners. Shape is an estimate from the supplied screenshots.
optic=empty('PM_ReflexSight • asset root',OPTIC,(-.145,0,1.670));parent(optic,mount)
optic['Variant']='Безымянный открытый коллиматор по визуальным референсам; оценочные пропорции'
opticmat=flat_material('Check | optic dark grey',(.080,.083,.086),.4,.32)
glass=flat_material('Check | clear sight lens',(.32,.43,.45),0,.08)
bs=next(n for n in glass.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Transmission Weight'].default_value=.85;bs.inputs['IOR'].default_value=1.46
base_outline=[(-.532,1.678),(.276,1.678),(.293,1.703),(.293,1.812),(.213,1.821),(-.466,1.821),(-.534,1.791)]
base=outline_solid('Reflex | stepped machined body',base_outline,.313,opticmat,OPTIC,optic,.0039)
cube('Reflex | rail clamping jaw',(-.142,-.085,1.688),(.682,.036,.057),opticmat,OPTIC,optic,.0031)
cylinder('Reflex | clamp hex screw',(.137,-.111,1.701),.022,.022,edge,OPTIC,optic,'Y',.0014,128)
# Tapered protective hood on the rear of the body, with a bevelled upper lip.
hood=[(.158,1.815),(.288,1.820),(.303,2.006),(.274,2.039),(.176,1.916)]
outline_solid('Reflex | sloped protective rear hood',hood,.316,opticmat,OPTIC,optic,.0041)
# Window cross-section along the sight's front-to-back axis; smooth rounded
# upper corners, inset lens and real wall thickness around the opening.
def rounded_rect(yhalf,zlo,zhi,r):
    ps=[]
    for cy,cz,a0 in ((yhalf-r,zhi-r,0),(-yhalf+r,zhi-r,90),(-yhalf+r,zlo+r,180),(yhalf-r,zlo+r,270)):
        for j in range(17):
            a=math.radians(a0+j*90/16);ps.append((cy+r*cos(a),cz+r*sin(a)))
    return ps
outer=rounded_rect(.188,1.788,2.068,.045);inner=rounded_rect(.158,1.812,2.040,.030)
n=len(outer);vv=[];ff=[]
for back in (False,True):
    for loop in (outer,inner):
        for y,z in loop:vv.append((-.510-(z-1.79)*.27+(.038 if back else 0),y,z))
for j in range(n):
    k=(j+1)%n
    ff.extend([(j,k,n+k,n+j),(2*n+j,3*n+j,3*n+k,2*n+k),(j,2*n+j,2*n+k,k),(n+j,n+k,3*n+k,3*n+j)])
mesh('Reflex | rounded open window frame',vv,ff,opticmat,OPTIC,optic,.0018)
verts=[(-.510-(z-1.79)*.27+.020,y,z) for y,z in inner]
lens=mesh('Reflex | inset transparent lens',verts,[tuple(range(n))],glass,OPTIC,optic)
for m in list(lens.modifiers):lens.modifiers.remove(m)
sol=lens.modifiers.new('Actual lens thickness','SOLIDIFY');sol.thickness=.003
bev=lens.modifiers.new('Polished glass edge','BEVEL');bev.width=.0008;bev.segments=4
# Top selector wheel and clean engraved index strokes, no branding invented.
cylinder('Reflex | selector drum',(-.042,0,1.840),.085,.036,opticmat,OPTIC,optic,'Z',.002,128)
for i in range(36):
    a=i*2*pi/36
    groove=cube('Reflex | selector knurl %02d'%i,(-.042+.084*cos(a),.084*sin(a),1.840),(.010,.004,.025),opticmat,OPTIC,optic,.0008)
    groove.rotation_euler[2]=a
for i,(x,z) in enumerate(((.197,1.850),(-.354,1.762))):
    screw=cylinder('Reflex | side adjustment screw %d'%i,(x,-.162,z),.026,.010,edge,OPTIC,optic,'Y',.0013,96)
    c=cube('temporary adjustment slot',(x,-.171,z),(.034,.017,.005),None,OPTIC,None,.0006);apply_mods(c);apply_bool(screw,c,'Adjustment slot')
optic.scale=(.67,.68,.80)
optic.location.z-=.008
note('Отдельный коллиматор: открытое окно, настоящая линза, козырёк, регулировки и зажим')

# Original controls and action are kept. Simple materials expose the new form.
rig.scale=saved_scale;rig.location=saved_loc
if saved_action:rig.animation_data_create();rig.animation_data.action=saved_action
S.frame_set(1);bpy.context.view_layer.update()
for marker in S.timeline_markers:marker.camera=None
bpy.data.collections['04 • Detachable suppressor'].hide_render=True
for o in bpy.data.collections['04 • Detachable suppressor'].objects:o.hide_set(True)
clay=flat_material('Check | satin neutral metal',(.245,.255,.270),.48,.31)
resin=flat_material('Check | neutral molded grip',(.170,.181,.193),0,.38)
recess=flat_material('Check | recess dark grey',(.07,.078,.085),.3,.39)
saved_mats={}
for o in bpy.data.objects:
    if o.type not in {'MESH','CURVE'} or STUDIO in o.users_collection or o.name.startswith('Reference'):continue
    if o.name=='Reflex | inset transparent lens':continue
    saved_mats[o.name]=[m.name if m else None for m in o.data.materials]
    o['Original material names']=json.dumps(saved_mats[o.name],ensure_ascii=False)
    material=resin if any(t in o.name for t in ('Bakelite','Grip emblem','Grip checkering','molded','Lanyard | molded')) else clay
    if o.name.startswith(('Extractor','Reflex |','Mount |')):material=opticmat if o.name.startswith('Reflex') else recess if o.name.startswith('Extractor') else clay
    o.data.materials.clear();o.data.materials.append(material)
    for poly in o.data.polygons if o.type=='MESH' else []:poly.material_index=0
rig['Revision']='v06 — geometry review, 2026-10-12';rig['Textures approved']=False
S.name='PM | Geometry review v06'
S.view_settings.exposure=-1.25
txt=bpy.data.texts.new('ПМ v06 • что проверять')
txt.write('Геометрия на просмотр. Текстурирование не начато.\n\n'+ '\n'.join(changed)+'\n\nРанее существовавшая Demo v5 сохранена. Для ручных свойств отключить Action у PM_CONTROLS.\nОбвесы отдельные: PM_OpticMount / PM_ReflexSight. Глушитель сохранён скрытым.\nСварной шов целика взят с художественного референса, а не утверждает штатную конструкцию ПМ.\n')
# The new saved file opens on a readable assembly view.
cam=camera('CHECK 01 | Complete PM and separate sight',(-.24,-.34,.235),(.003,0,.082),.230)
S.camera=cam;cam.data.clip_start=.0005;cam.data.clip_end=10
for area in bpy.context.screen.areas if bpy.context.screen else []:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_perspective='CAMERA'
        area.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT');rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
for name in ('01_ПМ','02_Крепление','03_Коллиматор','Превью','Проверки'):(OUT/name).mkdir(exist_ok=True)
S.render.resolution_x=1800;S.render.resolution_y=1200;S.render.resolution_percentage=100
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v06.blend'))
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(dict(source=str(SOURCE),source_sha256=SOURCE_HASH,
    version=bpy.app.version_string,changes=changed,original_materials=saved_mats,geometry_approved=False,
    textures_started=False,accessories=['PM_OpticMount','PM_ReflexSight'],scope_note='High-poly artistic Blender source; no game export'),ensure_ascii=False,indent=2),encoding='utf-8')
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_V06_SAVED',bpy.data.filepath,flush=True)
