"""Owner corrections on saved PM v06, with a newly traced MRS/R47-type optic."""
from pathlib import Path
import ast, hashlib, json, math
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from math import sin, cos, pi

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v07'
for name in ('01_ПМ','02_Крепление','03_Коллиматор','Превью','Проверки'):(OUT/name).mkdir(parents=True,exist_ok=True)
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
previous=json.loads((ROOT/'review_v06/Проверки/revision_manifest.json').read_text(encoding='utf-8'))
parsed=ast.parse((LIB/'90_История_и_резервные_копии/Скрипты_пистолета/build_pm_v4.py').read_text(encoding='utf-8'))
exec(compile(ast.Module(body=[n for n in parsed.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),'PM_helpers','exec'))
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
rig=bpy.data.objects['PM_CONTROLS • select me'];slide=bpy.data.objects['Slide • translation'];mag=bpy.data.objects['Magazine • extraction']
BODY=bpy.data.collections['01 • Frame & bakelite'];SLIDE=bpy.data.collections['02 • Slide assembly']
MAG=bpy.data.collections['03 • Magazine'];MOUNT=bpy.data.collections['08 • Optic mount — separate asset'];OPTIC=bpy.data.collections['09 • Reflex sight — separate asset']
saved_action=rig.animation_data.action if rig.animation_data else None
saved_scale=rig.scale.copy();saved_location=rig.location.copy()
rig.animation_data_clear();rig.scale=(1,1,1);rig.location=(0,0,0)
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','Suppressor'):rig[key]=0.0
bpy.context.view_layer.update()
steel=bpy.data.materials['Check | satin neutral metal'];dark=bpy.data.materials['Check | recess dark grey']
glass=bpy.data.materials['Check | clear sight lens']

def erase(prefixes):
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes):delete(o)

def edge_finish(o,segments=10):
    clean(o)
    for m in o.modifiers:
        if m.type=='BEVEL':m.segments=segments;m.harden_normals=True
    return o

def bool_cut(o,c,label):
    apply_mods(c);bpy.context.view_layer.objects.active=o
    m=o.modifiers.new(label,'BOOLEAN');m.operation='DIFFERENCE';m.solver='EXACT';m.object=c
    while o.modifiers[0]!=m:bpy.ops.object.modifier_move_up(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name);delete(c);edge_finish(o)

def extrude_x(name,x0,x1,yz,material,collection,owner,bevel=.0015):
    n=len(yz);v=[(x,y,z) for x in (x0,x1) for y,z in yz]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return edge_finish(mesh(name,v,f,material,collection,owner,bevel))

def slab_xy(name,xy,z0,z1,material,collection,owner,bevel=.0015):
    n=len(xy);v=[(x,y,z) for z in (z0,z1) for x,y in xy]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return edge_finish(mesh(name,v,f,material,collection,owner,bevel))

def rounded(a,b,c,d,r,steps=20):
    p=[]
    for x,y,a0 in ((b-r,d-r,0),(a+r,d-r,90),(a+r,c+r,180),(b-r,c+r,270)):
        for j in range(steps):
            t=math.radians(a0+j*90/steps);p.append((x+r*cos(t),y+r*sin(t)))
    return p

def bezier(points,steps):
    a,b,c,d=map(Vector,points)
    return [(1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d for t in (i/steps for i in range(steps))]

shell=bpy.data.objects['Slide | continuous crown, rounded muzzle & rear']
eo=shell.evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
roof=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear()
def rz(x,y):
    hit,_,_,_=roof.ray_cast(Vector((x,y,1.8)),Vector((0,0,-1)),.65)
    if hit is None:raise RuntimeError('No slide roof at requested seating point')
    return hit.z

# Low, flat rail. The horizontal spans and two-screw position remain as approved
# by the owner's previous dimensional clarification, while the stand-off changes.
mount=bpy.data.objects['PM_OpticMount • asset root']
mount.location.z=1.538
erase(('Mount | continuous','Mount | chamfered rail tooth','Mount | fitted wraparound','Mount | solid rail support','Mount | rounded two-screw'))
cube('Mount | continuous relieved rail spine',(-.118,0,1.558),(.675,.068,.020),steel,MOUNT,mount,.003)
rail_yz=[(-.050,1.556),(-.050,1.570),(-.039,1.589),(.039,1.589),(.050,1.570),(.050,1.556)]
for i in range(7):
    x=-.452+i*.100
    extrude_x('Mount | chamfered rail tooth %02d'%i,x,x+.066,rail_yz,steel,MOUNT,mount,.0026)
# Two C1-connected cubic sections and an offset sheet cross-section. Dense samples
# eliminate the old visible kink; cap edges retain a small editable edge radius.
center=[Vector((-.172,1.350)),Vector((-.172,1.382))]
center+=bezier([(-.172,1.382),(-.172,1.453),(-.110,1.520),(-.058,1.535)],64)
center+=bezier([(-.058,1.535),(-.036,1.54135),(.005,1.539),(.031,1.539)],48)
center.append(Vector((.031,1.539)))
unique=[]
for p in center:
    if not unique or (p-unique[-1]).length>1e-8:unique.append(p)
center=unique
cross=rounded(-.032,.032,-.0075,.0075,.0015,8)
for i,x in enumerate((-.199,.038)):
    v=[];f=[];n=len(cross)
    for j,p in enumerate(center):
        tangent=center[min(j+1,len(center)-1)]-center[max(0,j-1)]
        normal=Vector((-tangent.y,tangent.x)).normalized()
        for u,w in cross:v.append((x+u,p.x+normal.x*w,p.y+normal.y*w))
    f=[tuple(range(n-1,-1,-1)),tuple(range((len(center)-1)*n,len(center)*n))]
    for j in range(len(center)-1):
        for k in range(n):f.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
    saddle=mesh('Mount | fitted wraparound saddle %d'%i,v,f,steel,MOUNT,mount)
    for modifier in list(saddle.modifiers):saddle.modifiers.remove(modifier)
    for face in saddle.data.polygons:face.use_smooth=len(face.vertices)==4
    edge_finish(cube('Mount | solid rail support pad %d'%i,(x,-.008,1.547),(.063,.058,.011),steel,MOUNT,mount,.0014))
plate=rounded(-.247,.095,1.350,1.477,.016,16)
edge_finish(extrude('Mount | rounded two-screw clamp plate',plate,.019,steel,MOUNT,mount,.0028,y=-.175))
for o in bpy.data.objects:
    if o.name.startswith('Mount | cross-slot fastener'):
        matrix=o.matrix_world.copy();matrix.translation.z=1.414;o.matrix_world=matrix
mount['Installation']='v07: low smooth saddles; rail underside approximately 1.6 mm above slide crown'

# Slim rear blade with sloping flanks and a thinner, roof-conforming foot.
# The owner's accepted weld path is preserved exactly.
erase(('Rear sight | foot','Rear sight | beveled twin-ear'))
points=[(.695,-.064),(.791,-.064),(.800,-.047),(.800,.047),(.791,.064),(.695,.064),(.684,.047),(.684,-.047)]
cx,cy=.742,0
v=[(cx,cy,rz(cx,cy)-.002)]+[(x,y,rz(x,y)-.002) for x,y in points]
v+=[(cx,cy,rz(cx,cy)+.009)]+[(x,y,rz(x,y)+.009) for x,y in points]
n=len(points);k=n+1;f=[]
for j in range(n):
    a=j+1;b=(j+1)%n+1
    f.extend([(0,b,a),(k,k+a,k+b),(a,b,k+b,k+a)])
edge_finish(mesh('Rear sight | foot seated into curved crown',v,f,steel,SLIDE,slide,.0010))
yz=[(-.056,1.524),(.056,1.524),(.051,1.548),(.037,1.578),(.016,1.578),(.016,1.555),(-.016,1.555),(-.016,1.578),(-.037,1.578),(-.051,1.548)]
v=[(x0(z),y,z) for x0 in (lambda z:.726+(z-1.524)*.28,lambda z:.779-(z-1.524)*.14) for y,z in yz]
n=len(yz);f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
rear=edge_finish(mesh('Rear sight | beveled twin-ear blade',v,f,steel,SLIDE,slide,.0014))
rear['Profile']='Tapered sides and front-to-back thickness, traced for a finer PM rear sight'

# The floorplate lies parallel to the moulded heel cut, rather than inheriting
# the magazine body's lean. The lower shell transitions into this straight plate.
erase(('Magazine | thin rounded floorplate','Magazine | folded floorplate','Magazine | inset floorplate','Magazine | small stamped heel marking'))
outline=rounded(.394,.810,-.096,.096,.028,24)
plate=slab_xy('Magazine | aligned thin floorplate and extraction toe',outline,-.002,.017,steel,MAG,mag,.0019)
rim=slab_xy('Magazine | straight folded floorplate rim',rounded(.457,.766,-.078,.078,.012,16),.017,.041,steel,MAG,mag,.0017)
c=slab_xy('temporary rim opening',rounded(.469,.754,-.065,.065,.008,16),.022,.056,None,MAG,None,.0005)
bool_cut(rim,c,'Recess inside floorplate rim')
edge_finish(cylinder('Magazine | inset floorplate button',(.665,0,-.003),.018,.003,steel,MAG,mag,'Z',.0007,128))
# Modify only the bottom joining zone of the existing shell/seams. The upper
# magazine, feed lips, follower and animation remain the existing geometry.
for o in bpy.data.objects:
    if o.type!='MESH' or o.parent!=mag or not o.name.startswith(('Magazine | parallel','Magazine | rolled')):continue
    matrix=o.matrix_world.copy();inv=matrix.inverted()
    for vertex in o.data.vertices:
        p=matrix@vertex.co
        if p.z<.17:
            w=max(0,min(1,(.17-p.z)/.10));p.z-=w*.1399*(p.x-.463)
            vertex.co=inv@p
    o.data.update()

# Reorient the folded half cylinder: its opening and two lips follow the heel
# plane, its axis runs across the grip, and the ribbed convex face looks out of
# the heel recess. The open face looks back into the grip, as on owner_15.
erase(('MagCatch |',))
catch=bpy.data.objects['MagCatch • pivot'];catch.location=(.904,0,.232)
n=192;v=[];f=[];profile=[];fr=.0013
for j in range(9):
    a=j*pi/16;profile.append((-.076+fr*(1-cos(a)),.067-fr+fr*sin(a)))
for j in range(9):
    a=j*pi/16;profile.append((.076-fr+fr*sin(a),.067-fr+fr*cos(a)))
for j in range(9):
    a=j*pi/16;profile.append((.076-fr+fr*cos(a),.053+fr-fr*sin(a)))
for j in range(9):
    a=j*pi/16;profile.append((-.076+fr-fr*sin(a),.053+fr-fr*cos(a)))
N=len(profile)
for j in range(n+1):
    a=-j*pi/n;ripple=.00135*(.5+.5*cos(a*14))**5
    for y,r in profile:
        r+=ripple*max(0,min(1,(r-.053)/(.067-.053)))
        v.append((.850+r*cos(a),y,.094+r*sin(a)))
f=[tuple(range(N-1,-1,-1)),tuple(range(n*N,(n+1)*N))]
for j in range(n):
    for k in range(N):f.append((j*N+k,j*N+(k+1)%N,(j+1)*N+(k+1)%N,(j+1)*N+k))
f=[tuple(reversed(face)) for face in f]
thumb=mesh('MagCatch | half-round folded ribbed heel',v,f,steel,BODY,catch)
for modifier in list(thumb.modifiers):thumb.modifiers.remove(modifier)
for face in thumb.data.polygons:face.use_smooth=len(face.vertices)==4
thumb['Reference']='Owner lower close-up: semicylinder opening parallel to the floorplate, axis across grip'
spring=[(.900,.044),(.916,.059),(.917,.096),(.913,.232),(.904,.249),(.891,.233),(.897,.094),(.887,.060)]
edge_finish(extrude('MagCatch | flat retaining spring',spring,.093,steel,BODY,catch,.0015,smooth=3))
lip=slab_xy('MagCatch | forward retaining lip',rounded(.778,.797,-.065,.065,.004,12),.082,.095,steel,BODY,catch,.001)

# Rebuild every component of the optic from photographs of Umarex R47 and the
# Walther MRS manual. No third-party mesh is imported; the owner's size/rail fit
# is retained as an artistic miniature of this familiar multi-reticle shape.
erase(('Reflex |',))
optic=bpy.data.objects['PM_ReflexSight • asset root'];optic.scale=(1,1,1)
optic.location=mount.matrix_world.inverted()@Vector((-.145,0,1.591))
optic['Variant']='v07: MRS/R47-type open reflex, traced from official Umarex photographs and MRS manual; fit scaled to owner rail'
optic['Sources']='https://www.umarexusa.com/axeon-r47-multi-reticle-reflex-sight ; Umarex Walther MRS manual'
foot=[(-.102,1.574),(-.102,1.632),(.102,1.632),(.102,1.574),(.052,1.574),(.054,1.581),(.045,1.591),(-.045,1.591),(-.054,1.581),(-.052,1.574)]
extrude_x('Reflex | relieved rail mounting shoe',-.388,.079,foot,steel,OPTIC,optic,.0018)
jaw_profile=rounded(-.387,.078,1.578,1.630,.005,12)
edge_finish(extrude('Reflex | separate two-screw clamp jaw',jaw_profile,.019,steel,OPTIC,optic,.0014,y=-.109))

def socket_screw(name,loc,r,axis='Y',depth=.008):
    o=cylinder(name,loc,r,depth,steel,OPTIC,optic,axis,.0012,128);apply_mods(o)
    if axis=='Y':
        x,y,z=loc;pp=[(x+r*.51*cos(j*pi/3),z+r*.51*sin(j*pi/3)) for j in range(6)]
        c=extrude('temporary hex socket',pp,depth*.8,None,OPTIC,None,.00035,y=y-depth*.5)
    else:
        x,y,z=loc;pp=[(x+r*.51*cos(j*pi/3),y+r*.51*sin(j*pi/3)) for j in range(6)]
        c=slab_xy('temporary hex socket',pp,z+depth*.10,z+depth,None,OPTIC,None,.00035)
    bool_cut(o,c,'Hex socket');return o

for i,x in enumerate((-.303,.004)):socket_screw('Reflex | clamp hex fastener %d'%i,(x,-.125,1.608),.022)
xy=rounded(-.444,.224,-.150,.150,.029,24)
v=[];f=[];levels=[(1.629,.008),(1.642,0),(1.690,0),(1.699,.007)]
for z,inset in levels:
    for x,y in xy:v.append((x+inset if x<-.110 else x-inset,y-math.copysign(inset,y),z))
n=len(xy);f=[tuple(range(n-1,-1,-1)),tuple(range((len(levels)-1)*n,len(levels)*n))]
for k in range(len(levels)-1):
    for j in range(n):f.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
body=edge_finish(mesh('Reflex | rounded waisted main casting',v,f,steel,OPTIC,optic,.0012))

# The rear projector housing is a tapered volume, with a recessed emitter
# window on its sloping face, rather than the old tall rectangular fin.
hp=[(.054,1.694),(.218,1.694),(.223,1.869),(.200,1.895),(.126,1.895),(.058,1.746)]
n=len(hp);v=[(x,side*(.150-(z-1.694)*.21),z) for side in (-1,1) for x,z in hp]
f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
hood=edge_finish(mesh('Reflex | tapered projector rear hood',v,f,steel,OPTIC,optic,.0033));apply_mods(hood)
c=cube('temporary emitter recess',(.117,0,1.794),(.170,.060,.048),None,OPTIC,None,.0024)
bool_cut(hood,c,'Recessed projector window')
emitter=cube('Reflex | recessed projector window',(.183,0,1.794),(.004,.048,.037),dark,OPTIC,optic,.0018);edge_finish(emitter)
socket_screw('Reflex | side windage socket',(.070,-.153,1.705),.024)
socket_screw('Reflex | top elevation socket',(.083,0,1.714),.018,'Z',.009)

# A real curved, rounded panoramic frame, slanted towards the front. Both the
# outer and inner walls are generated densely, with a small continuous radius.
outer=rounded(-.180,.180,1.685,1.984,.105,32)
inner=rounded(-.156,.156,1.710,1.958,.091,32)
n=len(outer);v=[];f=[]
def fx(z):return -.434-(z-1.685)*.22
for back in (False,True):
    for loop in (outer,inner):
        for y,z in loop:v.append((fx(z)+(.034 if back else 0),y,z))
for j in range(n):
    k=(j+1)%n
    f.extend([(j,k,n+k,n+j),(2*n+j,3*n+j,3*n+k,2*n+k),(j,2*n+j,2*n+k,k),(n+j,n+k,3*n+k,3*n+j)])
frame=edge_finish(mesh('Reflex | panoramic rounded window frame',v,f,steel,OPTIC,optic,.0014))
# Closed biconvex lens with concentric rings and triangulated centres. It has
# curved surfaces, a genuine rim and thickness; no flat outline n-gon stands in.
v=[];f=[];rings=12;centre=Vector((0,(1.710+1.958)/2));layer_size=1+rings*n
def lens_x(y,z,back):
    bow=.014*(y/.156)**2+.010*((z-centre.y)/.124)**2
    return fx(z)+.012+bow+(.0038 if back else 0)
for back in (False,True):
    v.append((lens_x(0,centre.y,back),0,centre.y))
    for k in range(1,rings+1):
        t=k/rings
        for y,z in inner:
            y*=t;z=centre.y+(z-centre.y)*t;v.append((lens_x(y,z,back),y,z))
for layer in (0,1):
    off=layer*layer_size
    for j in range(n):f.append((off,off+1+j,off+1+(j+1)%n))
    for k in range(rings-1):
        a=off+1+k*n;b=a+n
        for j in range(n):f.append((a+j,a+(j+1)%n,b+(j+1)%n,b+j))
a=1+(rings-1)*n;b=layer_size+a
for j in range(n):f.append((a+j,b+j,b+(j+1)%n,a+(j+1)%n))
lens=mesh('Reflex | inset transparent lens',v,f,glass,OPTIC,optic)
for m in list(lens.modifiers):lens.modifiers.remove(m)
for face in lens.data.polygons:face.use_smooth=True

# Machined selector drum and coin-slot cap: continuous shallow knurling, rather
# than separate oversized blocks attached around a smooth cylinder.
n=512;v=[];f=[];levels=[(1.698,.100),(1.704,.104),(1.737,.104),(1.743,.100)]
for z,r in levels:
    for j in range(n):
        a=j*2*pi/n;rr=r+.00065*(.5+.5*cos(a*64));v.append((-.244+rr*cos(a),rr*sin(a),z))
f=[tuple(range(n-1,-1,-1)),tuple(range((len(levels)-1)*n,len(levels)*n))]
for k in range(len(levels)-1):
    for j in range(n):f.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
wheel=edge_finish(mesh('Reflex | finely knurled selector drum',v,f,steel,OPTIC,optic))
cap=cylinder('Reflex | coin-slot battery cap',(-.244,0,1.747),.097,.010,steel,OPTIC,optic,'Z',.002,192);apply_mods(cap)
c=cube('temporary cap coin slot',(-.244,0,1.753),(.123,.007,.007),None,OPTIC,None,.0010)
c.rotation_euler[2]=.48;bool_cut(cap,c,'Coin slot in cap')
# Small rear reticle lever and its circular pivot complete the visible silhouette.
edge_finish(cylinder('Reflex | rear reticle selector pivot',(.221,0,1.672),.024,.044,steel,OPTIC,optic,'X',.0014,128))
edge_finish(extrude_x('Reflex | rear reticle selector lever',.226,.246,[(-.052,1.678),(-.051,1.690),(.009,1.690),(.020,1.680),(.010,1.670)],steel,OPTIC,optic,.0018))

rig.scale=saved_scale;rig.location=saved_location
if saved_action:
    saved_action.use_fake_user=True;action=saved_action.copy();action.name='Geometry inspection v07';action.use_fake_user=True
    rig.animation_data_create();rig.animation_data.action=action
S.frame_set(1);bpy.context.view_layer.update()
S.camera=bpy.data.objects['CHECK 01 | Complete PM and separate sight']
for o in bpy.data.objects:
    if o.type=='MESH' and o.name.startswith(('Mount |','Reflex |','Rear sight |','MagCatch |','Magazine | aligned','Magazine | straight')):
        o['Geometry revision']='Owner corrections v07'
changes=[
'Крепление: плавные скобы вместо ломаного профиля, уменьшены зазор до затвора и толщина планки',
'Целик: тонкое прилегающее основание, скошенные боковые стороны и более тонкая верхняя часть; сварной шов v06 сохранён',
'Магазин: плоскость крышки параллельна срезу пятки, нижний переход корпуса сопряжён с крышкой',
'Защёлка: полуцилиндр ориентирован вдоль плоскости пятки, перенесён к заднему краю; правильная верхняя ось отклонения',
'Коллиматор: полностью новая форма по официальным фотографиям Umarex R47 и руководству Walther MRS — округлая рамка и изогнутая линза, скошенный кожух с окном, барабан, регулировки и зажим на двух винтах']
record=dict(source=previous['source'],source_sha256=previous['source_sha256'],parent_geometry=str(SOURCE),parent_sha256=SOURCE_HASH,
            revision='v07',changes=changes,inherited_changes=previous['changes'],texture_approval=False,
            optic_sources=['https://www.umarexusa.com/axeon-r47-multi-reticle-reflex-sight','https://www.pyramydair.com/airgun-resources/manuals/manual-walther-multi-reticle-sight.pdf'])
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v07.blend'))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_V07_SAVED',str(OUT/'01_ПМ/PM_Geometry_v07.blend'),flush=True)
