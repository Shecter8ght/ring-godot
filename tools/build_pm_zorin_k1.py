"""Replace only the v07 optic with the owner's arched micro reflex and Cyrillic brand.

Run on the saved PM v07 file. Geometry is authored in millimetres, transformed
into the existing artistic assembly, with editable markings and packed fonts.
"""
from pathlib import Path
import ast, hashlib, json, math, struct
from math import sin, cos, pi
import bpy, bmesh
from mathutils import Vector, Matrix

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v08'
for name in ('01_ПМ','02_Крепление','03_Коллиматор','Превью','Проверки'):(OUT/name).mkdir(parents=True,exist_ok=True)
SOURCE=Path(bpy.data.filepath);SOURCE_HASH=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
previous=json.loads((ROOT/'review_v07/Проверки/revision_manifest.json').read_text(encoding='utf-8'))
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
for source in (LIB/'90_История_и_резервные_копии/Скрипты_пистолета/build_pm_v4.py',PROJECT/'tools/correct_pm_refinement_v07.py'):
    parsed=ast.parse(source.read_text(encoding='utf-8'))
    exec(compile(ast.Module(body=[n for n in parsed.body if isinstance(n,ast.FunctionDef)],type_ignores=[]),str(source),'exec'))
S=bpy.context.scene;S.frame_set(1);bpy.context.view_layer.update()
rig=bpy.data.objects['PM_CONTROLS • select me'];mount=bpy.data.objects['PM_OpticMount • asset root'];optic=bpy.data.objects['PM_ReflexSight • asset root']
OPTIC=bpy.data.collections['09 • Reflex sight — separate asset']
saved_action=rig.animation_data.action;saved_scale=rig.scale.copy();saved_location=rig.location.copy()

def unchanged_fingerprint():
    records={}
    for o in bpy.data.objects:
        if o.type!='MESH' or o.name.startswith(('Reflex |','temporary')):continue
        if not any(c.name.startswith(tuple(f'{i:02d} •' for i in range(1,9))) for c in o.users_collection):continue
        h=hashlib.sha256()
        for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
        for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
        h.update(str(tuple(tuple(row) for row in o.matrix_local)).encode())
        h.update((o.parent.name if o.parent else '').encode())
        records[o.name]=h.hexdigest()
    return records

before=unchanged_fingerprint()
rig.animation_data_clear();rig.scale=(1,1,1);rig.location=(0,0,0)
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','Suppressor'):rig[key]=0.0
bpy.context.view_layer.update()
erase(('Reflex |',))
anchor=Vector((-.145,0,1.591));factor=.001/saved_scale.x
optic.location=mount.matrix_world.inverted()@anchor;optic.scale=(1,1,1)
optic['Brand']='ЗОРИН';optic['Model']='К-1';optic['Geometry revision']='v08: owner ten-view arched micro reflex'
optic['Scale reference']='46.1 x 33.2 x 33.0 mm body; custom shoe fitted to existing owner rail'

def P(v):return tuple(anchor+Vector(v)*factor)

def inspection_material(name,color,metallic=0,roughness=.35):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Metallic'].default_value=metallic;bs.inputs['Roughness'].default_value=roughness
    return m

steel=inspection_material('Check | K1 satin alloy',(.37,.40,.42),.55,.33)
shellmat=inspection_material('Check | K1 protective hood',(.30,.33,.35),.55,.31)
dark=inspection_material('Check | K1 elastomer',(.085,.10,.11),0,.48)
ink=inspection_material('Check | Cyrillic marking layout',(.78,.80,.79),.1,.42)
glass=inspection_material('Check | K1 curved lens',(.83,.95,.91),0,.025)
bs=glass.node_tree.nodes.get('Principled BSDF');bs.inputs['Transmission Weight'].default_value=1;bs.inputs['IOR'].default_value=1.48

def mm_mesh(name,vertices,faces,material=steel,bevel=.15):
    return edge_finish(mesh('Reflex | '+name,[P(v) for v in vertices],faces,material,OPTIC,optic,bevel*factor))

def mm_slab(name,xy,z0,z1,material=steel,bevel=.15):
    n=len(xy);v=[(x,y,z) for z in (z0,z1) for x,y in xy]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return mm_mesh(name,v,f,material,bevel)

def mm_extrude_x(name,x0,x1,yz,material=steel,bevel=.15):
    n=len(yz);v=[(x,y,z) for x in (x0,x1) for y,z in yz]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return mm_mesh(name,v,f,material,bevel)

def mm_extrude_y(name,poly,y0,y1,material=steel,bevel=.15):
    n=len(poly);v=[(x,y,z) for y in (y0,y1) for x,z in poly]
    f=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]+[(j,j+n,(j+1)%n+n,(j+1)%n) for j in range(n)]
    return mm_mesh(name,v,f,material,bevel)

def mm_cylinder(name,loc,r,depth,material=steel,axis='Z',bevel=.1,segments=192):
    return edge_finish(cylinder('Reflex | '+name,P(loc),r*factor,depth*factor,material,OPTIC,optic,axis,bevel*factor,segments))

def mm_box(name,loc,dim,material=steel,bevel=.15):
    return edge_finish(cube('Reflex | '+name,P(loc),tuple(d*factor for d in dim),material,OPTIC,optic,bevel*factor))

def torx(name,loc,r=3.1,axis='Y',depth=.75,side=-1):
    o=mm_cylinder(name,loc,r,depth,steel,axis,.12);apply_mods(o)
    loop=[]
    for i in range(192):
        a=i*2*pi/192;rr=r*(.405+.105*cos(6*a));loop.append((rr*cos(a),rr*sin(a)))
    x,y,z=loc
    if axis=='Y':
        poly=[(x+u,z+w) for u,w in loop]
        cut0,cut1=sorted((y+side*.10,y+side*1.2))
        c=mm_extrude_y('temporary torx cutter',poly,cut0,cut1,None,.018)
    else:
        c=mm_slab('temporary torx cutter',[(x+u,y+w) for u,w in loop],z+.12,z+1.2,None,.018)
    bool_cut(o,c,'Six-lobe recessed socket');return o

# Custom shoe: the visible outer wedge follows the new reference, while the
# actual relief fits the owner's narrow, short rail and is documented as custom.
yz=[(-13.7,-1.45),(-13.7,3.9),(-11.9,5.7),(-9.6,8.25),(9.6,8.25),(11.9,5.7),(13.7,3.9),(13.7,-1.45),
    (10.2,-1.45),(8.0,1.2),(10.2,3.7),(7.7,4.8),(-7.7,4.8),(-10.2,3.7),(-8.0,1.2),(-10.2,-1.45)]
shoe=mm_extrude_x('K1 relieved low cross-slot shoe',-21.95,21.95,yz,steel,.07)
mm_extrude_y('K1 separate clamp jaw',rounded(-21.9,21.9,-1.35,4.0,.6,18),-14.4,-13.65,steel,.13)
for i,x in enumerate((-14.3,14.3)):torx(f'K1 clamp six-lobe fastener {i}',(x,-14.75,1.2),2.85,depth=.9)
pad=[(4.27,-.22),(5.25,-.22),(5.35,5.0),(4.27,5.0),(4.27,.38),(4.90,.38),(4.90,.02),(4.27,.02)]
for i,x in enumerate((-14.3,14.3)):
    for side in (-1,1):
        mm_extrude_x(f'K1 internal rail fitting pad {i} {side}',x-2.5,x+2.5,[(side*y,z) for y,z in pad],steel,.06)

# One main casting, with a waist, a front apron and a low aft deck. The broad
# surfaces and their transitions are traced; no separate rear tower remains.
xy=rounded(-23.05,23.05,-16.6,16.6,.7,24)
v=[];f=[];levels=[(8.4,1.25),(9.5,.15),(17.95,.15),(18.4,.50)];n=len(xy)
for z,inset in levels:
    for x,y in xy:v.append((x-math.copysign(inset,x),y-math.copysign(inset,y),z))
f=[tuple(range(n-1,-1,-1)),tuple(range(3*n,4*n))]
for k in range(3):
    for j in range(n):f.append((k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j))
casting=mm_mesh('K1 one-piece rounded lower casting',v,f,steel,.15)
mm_slab('K1 thin base seam',rounded(-23.0,23.0,-16.3,16.3,.65,24),7.95,8.42,shellmat,.08)

def arch(w,bottom,shoulder,rise,r):
    out=[]
    for j in range(32):out.append((-w+r+(2*w-2*r)*j/32,bottom))
    for j in range(16):
        a=-pi/2+j*pi/32;out.append((w-r+r*cos(a),bottom+r+r*sin(a)))
    for j in range(40):out.append((w,bottom+r+(shoulder-bottom-r)*j/40))
    for j in range(128):
        a=j*pi/128;out.append((w*cos(a),shoulder+rise*sin(a)))
    for j in range(40):out.append((-w,shoulder-(shoulder-bottom-r)*j/40))
    for j in range(16):
        a=pi+j*pi/32;out.append((-w+r+r*cos(a),bottom+r+r*sin(a)))
    return out

outer=arch(16.6,17.8,33.5,7.9,.8)
inner=arch(12.85,21.4,33.4,5.5,2.0);n=len(outer)
def front_x(z):return -23.0+max(0,z-26.0)*.22
def rear_x(z):
    if z<25.1:
        # Cubic concave transition, tangent to the flat aft deck. The source
        # silhouette has this substantial fillet rather than a triangular kink.
        if z<=18.4:return 1.8
        lo,hi=0.0,1.0
        for _ in range(28):
            t=(lo+hi)/2;u=1-t;zz=u**3*25.1+3*u*u*t*21.1+3*u*t*t*18.4+t**3*18.4
            if zz>z:lo=t
            else:hi=t
        t=(lo+hi)/2;u=1-t
        return u**3*(-5.3)+3*u*u*t*(-3.0)+3*u*t*t*(-3.0)+t**3*1.8
    if z<33.5:return -5.3-(z-25.1)*5.2/(33.5-25.1)
    return -10.5+(z-33.5)*.5/7.9

def hood_back(y,z):
    # The lower front bridge is shallow through the centre: deep side walls
    # protect the lens without covering the round top-access battery door.
    side_weight=max(0,min(1,(abs(y)-11.8)/3.8))
    lower_weight=max(0,min(1,(24.0-z)/2.6));lower_weight=lower_weight*lower_weight*(3-2*lower_weight)
    weight=1-lower_weight*(1-side_weight)
    return (front_x(z)+2.0)*(1-weight)+rear_x(z)*weight

def band(name,outside,inside,xfront,xback,material,bevel):
    count=len(outside);v=[]
    for xx in (xfront,xback):
        for loop in (outside,inside):
            for y,z in loop:v.append((xx(y,z),y,z))
    f=[]
    for j in range(count):
        k=(j+1)%count
        f.extend([(j,k,count+k,count+j),(2*count+j,3*count+j,3*count+k,2*count+k),
            (j,2*count+j,2*count+k,k),(count+j,count+k,3*count+k,3*count+j)])
    return mm_mesh(name,v,f,material,bevel)

hood=band('K1 deep arched protective hood',outer,inner,lambda y,z:front_x(z),hood_back,shellmat,.20)
hood['Reference']='Owner views 1,2,4,5,7,8,9: arched front and deep tapered side profile'
def lens_plane(z):return -22.25+(z-21.4)*(2.838/17.5)
seat_outer=[(y*1.005,30.15+(z-30.15)*1.005) for y,z in inner]
seat_inner=[(y*.973,30.15+(z-30.15)*.973) for y,z in inner]
band('K1 inset continuous lens seat',seat_outer,seat_inner,lambda y,z:lens_plane(z)-.15,lambda y,z:lens_plane(z)+1.25,dark,.055)

# Closed curved optical element, with actual thickness and a dense curved crown.
v=[];f=[];rings=12;loop=seat_inner;n=len(loop);zc=30.15;layer_size=1+rings*n
def lx(y,z,back):return lens_plane(z)+.38*(y/12.85)**2+.15*((z-zc)/8.75)**2+(.66 if back else 0)
for back in (False,True):
    v.append((lx(0,zc,back),0,zc))
    for ring in range(1,rings+1):
        t=ring/rings
        for yy,zz in loop:
            y=yy*t;z=zc+(zz-zc)*t;v.append((lx(y,z,back),y,z))
for layer in range(2):
    off=layer*layer_size
    for j in range(n):f.append((off,off+1+j,off+1+(j+1)%n))
    for k in range(rings-1):
        a=off+1+k*n;b=a+n
        for j in range(n):f.append((a+j,a+(j+1)%n,b+(j+1)%n,b+j))
a=1+(rings-1)*n;b=layer_size+a
for j in range(n):f.append((a+j,b+j,b+(j+1)%n,a+(j+1)%n))
lens=mm_mesh('K1 curved aspheric lens',v,f,glass,0)
for modifier in list(lens.modifiers):lens.modifiers.remove(modifier)
for p in lens.data.polygons:p.use_smooth=True

# Contoured steel cheek plates and recessed fasteners on each side.
cheek=[(-22.65,9.7),(8.8,9.7),(9.0,13.8),(7.6,16.2),(-2.0,17.7),(-8.2,20.0),(-22.65,20.0)]
for side in (-1,1):
    y0,y1=sorted((side*16.40,side*16.83))
    mm_extrude_y('K1 contoured side cheek '+str(side),cheek,y0,y1,shellmat,.10)
    for i,x in enumerate((-16.2,3.4)):torx(f'K1 cheek fastener {side} {i}',(x,side*17.02,13.5),2.95,depth=.72,side=side)

# Round top-access cover and central rubber brightness button. The cover is
# recessed into the deck; its continuous seat and latch are independent objects.
mm_cylinder('K1 battery cover seal',(-4.0,0,18.36),11.65,.36,dark,bevel=.08)
mm_cylinder('K1 hinged round battery cover',(-4.0,0,18.67),11.35,.45,steel,bevel=.12)
mm_cylinder('K1 central recessed rubber brightness button',(-4.0,0,19.05),3.9,.37,dark,bevel=.15)
mm_extrude_y('K1 front battery hinge',rounded(-15.2,-13.45,18.3,19.3,.40,14),-2.5,2.5,steel,.12)
mm_box('K1 battery release latch',(7.32,0,18.67),(.9,5.8,.64),shellmat,.11)
for side in (-1,1):torx('K1 upper anchor '+str(side),(9.0,side*9.5,18.68),2.7,'Z',.65)

def coin_adjustment(name,loc,axis='Z',r=3.7):
    mm_cylinder(name+' recessed bezel',loc,r+.38,.32,shellmat,axis,.08)
    o=mm_cylinder(name,loc,r,.44,steel,axis,.09);apply_mods(o)
    x,y,z=loc
    if axis=='Z':c=mm_box('temporary adjustment slot',(x,y,z+.31),(r*1.45,.6,.5),None,.055)
    else:c=mm_box('temporary adjustment slot',(x,y+.29,z),(r*1.45,.5,.6),None,.055)
    bool_cut(o,c,'Recessed straight adjustment slot');return o

coin_adjustment('K1 elevation adjustment',(17.05,0,18.65))
coin_adjustment('K1 windage adjustment',(17.0,16.50,13.9),'Y')
mm_cylinder('K1 windage stop',(21.0,16.7,17.1),.65,.24,steel,'Y',.07,128)
mm_extrude_x('K1 removable rear inspection plate',23.00,23.32,rounded(-9.2,9.2,9.1,17.7,.5,20),shellmat,.07)
mm_box('K1 recessed emitter seat',(20.7,0,17.45),(2.7,3.4,.8),dark,.15)

# Editable Cyrillic lettering and a simple independent brand emblem. These are
# a geometry-review layout, with no production UV or paint stack yet.
font=bpy.data.fonts.load('C:/Windows/Fonts/bahnschrift.ttf');font.pack()
def lettering(name,body,loc,size,orient='left',material=ink):
    data=bpy.data.curves.new('ЗОРИН | '+name,'FONT');data.body=body;data.font=font;data.size=size*factor
    data.align_x='CENTER';data.align_y='CENTER';data.extrude=.008*factor;data.bevel_depth=.004*factor;data.bevel_resolution=3
    data.resolution_u=16
    o=bpy.data.objects.new('Reflex | Marking '+name,data);OPTIC.objects.link(o)
    o.location=P(loc)
    if orient=='left':o.rotation_euler=(pi/2,0,0)
    elif orient=='right':o.rotation_euler=(pi/2,0,pi)
    elif orient=='top':o.rotation_euler=(0,0,0)
    elif orient=='front':o.rotation_euler=(pi/2,0,-pi/2)
    data.materials.append(material);parent(o,optic);o['Marking role']='Editable Cyrillic geometry-review layout'
    return o

for side in (-1,1):
    orient='left' if side<0 else 'right'
    lettering('brand '+str(side),'ЗОРИН',(-6.1,side*16.95,13.8),2.6,orient)
    lettering('model '+str(side),'К-1',(-6.1,side*16.95,11.5),.98,orient)
lettering('Russian origin','РОССИЯ',(15.3,-16.56,15.75),.95)
lettering('serial','№ 061284',(15.3,-16.56,11.5),.85)
lettering('elevation','ВВЕРХ',(17.0,5.9,18.84),.92,'top')
lettering('windage','ВПРАВО',(16.9,16.50,9.5),.90,'right')
lettering('battery voltage','3 В',(-4.1,6.8,18.98),.95,'top')
lettering('front brand','ЗОРИН',(-23.24,0,14.1),2.35,'front')

def stroke(name,points,width=.065,material=ink):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D';data.resolution_u=16;data.bevel_depth=width*factor/2;data.bevel_resolution=5;data.use_fill_caps=True
    spline=data.splines.new('POLY');spline.points.add(len(points)-1)
    for p,v in zip(spline.points,points):p.co=(*P(v),1)
    o=bpy.data.objects.new('Reflex | Marking '+name,data);OPTIC.objects.link(o);data.materials.append(material);parent(o,optic);return o

arc=[]
for j in range(65):
    a=.22+j*1.58/64;arc.append((17.05+4.7*cos(a),4.7*sin(a),18.89))
stroke('elevation direction',arc)
p=Vector(arc[-1]);stroke('elevation arrow',[tuple(p+Vector((.1,-.7,0))),tuple(p),tuple(p+Vector((.65,-.2,0)))],.09)
arc=[]
for j in range(65):
    a=2.75-j*1.70/64;arc.append((17.0+4.65*cos(a),16.58,13.9+4.65*sin(a)))
stroke('windage direction',arc)
p=Vector(arc[-1]);stroke('windage arrow',[tuple(p+Vector((-.1,0,-.7))),tuple(p),tuple(p+Vector((-.65,0,-.15)))],.09)
for side in (-1,1):
    # Emblem: open optical ring and a centre diamond, placed on the taller hood.
    y=side*16.87;arc=[(-18.0+1.18*cos(.45+j*5.35/96),y,24.2+1.18*sin(.45+j*5.35/96)) for j in range(97)]
    stroke('brand emblem ring '+str(side),arc,.10)
    stroke('brand emblem diamond '+str(side),[(-18.0,y,24.78),(-17.42,y,24.2),(-18.0,y,23.62),(-18.58,y,24.2),(-18.0,y,24.78)],.10)

rig.scale=saved_scale;rig.location=saved_location
saved_action.use_fake_user=True;action=saved_action.copy();action.name='Geometry inspection v08';action.use_fake_user=True
rig.animation_data_create();rig.animation_data.action=action
S.frame_set(1);bpy.context.view_layer.update()
after=unchanged_fingerprint();assert before==after,'Unrequested pistol or mount geometry changed'
S.camera=bpy.data.objects['CHECK 01 | Complete PM and separate sight']
S.camera.data.ortho_scale=.261
for o in OPTIC.objects:
    if o.name.startswith('Reflex |'):o['Geometry revision']='v08 — ЗОРИН К-1'
note=bpy.data.texts.new('ЗОРИН К-1 • замысел и надписи')
note.write('Вымышленный бренд ЗОРИН, модель К-1. Форма по десяти видам владельца; основной габарит по руководству DeltaPoint Pro.\nНадписи русские, отдельные редактируемые FONT/Curve с packed шрифтом. Это компоновка до UCUPaint.\nПМ и низкое крепление v07 сохранены; переходник к узкой планке индивидуальный, художественный.\n')
record=dict(source=previous['source'],source_sha256=previous['source_sha256'],parent_geometry=str(SOURCE),parent_sha256=SOURCE_HASH,
    revision='v08',changes=['Полностью новый компактный коллиматор ЗОРИН К-1 по десяти видам владельца: арочная глубокая защита, изогнутая линза, плоский хвост, круглая крышка с кнопкой и низкий зажим','Русские редактируемые надписи и эмблема: ЗОРИН, К-1, РОССИЯ, серийный номер, ВВЕРХ, ВПРАВО и 3 В'],
    inherited_changes=previous['changes']+previous['inherited_changes'],texture_approval=False,brand='ЗОРИН',model='К-1',
    optic_sources=['Owner supplied 10 JPG views','https://www.leupold.com/deltapoint-pro-red-dot','https://www.leupold.com/media/manuals/deltapoint-pro-manual.pdf'],
    non_optic_geometry_unchanged=True,unchanged_meshes=len(before),unchanged_fingerprints=before,
    fit_note='Individual narrow-rail shoe fitted to existing PM reference rail; optical outer form follows owner views')
(OUT/'Проверки/revision_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v08.blend'))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_HASH
print('PM_K1_SAVED',len(OPTIC.objects),len(before),str(OUT/'01_ПМ/PM_Geometry_v08.blend'),flush=True)
