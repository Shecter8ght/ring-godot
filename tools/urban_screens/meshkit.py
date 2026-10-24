"""Сечения, оболочки и гнутые детали для редактируемых Blender-кандидатов."""
import math
from math import sin, cos, pi
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

COLLECTION = None
PARTS = []
MATS = {}


def initialize():
    global COLLECTION, PARTS, MATS
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    COLLECTION = bpy.data.collections.new('MODEL | editable components')
    scene.collection.children.link(COLLECTION)
    PARTS = []
    MATS = {}


def material(role):
    if role not in MATS:
        m = bpy.data.materials.new('SLOT_' + role)
        m.use_nodes = True
        p = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        # Нейтральные диагностические материалы; это не стадия PBR.
        c = .36 if role not in ('rubber', 'interior', 'screen', 'soil') else .16
        if role in ('glass', 'diffuser'):
            c = .48
        p.inputs['Base Color'].default_value = (c,c,c,1)
        p.inputs['Roughness'].default_value = .47
        m.diffuse_color = (c,c,c,1)
        m['purpose'] = 'Neutral geometry review slot; production texture work not started'
        MATS[role] = m
    return MATS[role]


def mesh(name, vertices, faces, role='metal', bevel=0.0, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0000001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    COLLECTION.objects.link(ob)
    ob.data.materials.append(material(role))
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if bevel:
        mod = ob.modifiers.new('Edge radii | physical metres', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = 'ANGLE'
        mod.angle_limit = .50
        mod.harden_normals = True
        mod = ob.modifiers.new('Face weighted normals', 'WEIGHTED_NORMAL')
        mod.keep_sharp = True
        mod.weight = 30
    ob['finish_role'] = role
    PARTS.append(ob)
    return ob


def box(name, center, size, role='metal', bevel=.003):
    x,y,z = size
    bevel=min(bevel,min(abs(x),abs(y),abs(z))*.20)
    cx,cy,cz = center
    verts = [(cx+a*x/2,cy+b*y/2,cz+c*z/2)
             for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                           (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    return mesh(name, verts, [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),
                             (2,3,7,6),(3,0,4,7)],role,bevel)


def extrude(name, profile, axis, start, end, role='metal', bevel=.002):
    # Замкнутое, в том числе вогнутое, сечение с триангуляцией торцов.
    def point(uv, t):
        u,v = uv
        return (t,u,v) if axis=='X' else ((u,t,v) if axis=='Y' else (u,v,t))
    bevel=min(bevel,abs(end-start)*.20)
    n = len(profile)
    verts = [point(p,t) for t in (start,end) for p in profile]
    poly = [Vector((u,v,0)) for u,v in profile]
    lookup = {(round(v.x,8),round(v.y,8)):i for i,v in enumerate(poly)}
    tris = [[v if isinstance(v,int) else lookup[(round(v.x,8),round(v.y,8))] for v in tri]
            for tri in tessellate_polygon([poly])]
    def area(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if any(abs(area(*(profile[i] for i in t)))<1e-12 for t in tris):
        # Blender 5.2 даёт нулевые треугольники на вогнутых торцах двутавра.
        # Локальная триангуляция сохраняет все вершины именно этого сечения.
        active=list(range(n))
        signed=sum(profile[i][0]*profile[(i+1)%n][1]-profile[(i+1)%n][0]*profile[i][1] for i in range(n))
        if signed<0: active.reverse()
        tris=[]
        while len(active)>3:
            found=False
            for j,b in enumerate(active):
                a=active[j-1]; c=active[(j+1)%len(active)]
                if area(profile[a],profile[b],profile[c])<1e-12: continue
                occupied=False
                for p in active:
                    if p in (a,b,c): continue
                    if all(area(profile[u],profile[v],profile[p])>=-1e-12 for u,v in ((a,b),(b,c),(c,a))):
                        occupied=True; break
                if not occupied:
                    tris.append([a,b,c]); active.pop(j); found=True; break
            if not found: raise ValueError('Invalid or self-intersecting section: '+name)
        tris.append(active)
    faces = [tuple(reversed(t)) for t in tris] + [tuple(i+n for i in t) for t in tris]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh(name,verts,faces,role,bevel)


def section(name, path, radius=.018, role='metal', sides=16, caps=True):
    pts = [Vector(p) for p in path]
    verts=[]
    closed=(pts[0]-pts[-1]).length<1e-7
    previous_a=None
    first_a=None
    for i,p in enumerate(pts):
        incoming=(p-pts[i-1]).normalized() if i else ((p-pts[-2]).normalized() if closed else (pts[1]-p).normalized())
        outgoing=(pts[i+1]-p).normalized() if i<len(pts)-1 else ((pts[1]-p).normalized() if closed else incoming)
        tangent=(incoming+outgoing).normalized()
        reference=Vector((0,0,1)) if abs(tangent.z)<.92 else Vector((0,1,0))
        a=(previous_a-tangent*previous_a.dot(tangent)).normalized() if previous_a is not None else tangent.cross(reference).normalized()
        if a.length<.5: a=tangent.cross(reference).normalized()
        if first_a is None: first_a=a.copy()
        if closed and i==len(pts)-1: a=first_a.copy()
        b=tangent.cross(a).normalized()
        previous_a=a
        for j in range(sides):
            t=2*pi*j/sides
            verts.append(tuple(p+radius*(a*cos(t)+b*sin(t))))
    faces=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j)
           for i in range(len(pts)-1) for j in range(sides)]
    if caps and not closed:
        faces += [tuple(reversed(range(sides))),tuple((len(pts)-1)*sides+j for j in range(sides))]
    return mesh(name,verts,faces,role,0,True)


def bar(name,a,b,r=.018,role='metal',sides=16):
    return section(name,[a,b],r,role,sides)


def beam(name,a,b,width=.05,depth=.05,role='metal',bevel=.002):
    v=Vector(b)-Vector(a)
    ob=box(name,(0,0,0),(width,depth,v.length),role,bevel)
    ob.rotation_mode='QUATERNION'
    ob.rotation_quaternion=v.to_track_quat('Z','Y')
    ob.location=(Vector(a)+Vector(b))/2
    return ob


def lathe(name,profile,loc=(0,0,0),axis='Z',role='metal',n=64):
    # Профиль (радиус, осевая координата) описывает настоящую стенку.
    verts=[]
    rings=[]
    for r,z in profile:
        inds=[]
        count=1 if abs(r)<1e-8 else n
        for j in range(count):
            a=2*pi*j/n
            p=(r*cos(a),r*sin(a),z)
            if axis=='Y': p=(p[0],p[2],p[1])
            if axis=='X': p=(p[2],p[0],p[1])
            inds.append(len(verts))
            verts.append(tuple(p[k]+loc[k] for k in range(3)))
        rings.append(inds)
    faces=[]
    for i in range(len(rings)-1):
        a,b=rings[i:i+2]
        for j in range(n):
            if len(a)==1 and len(b)==1: continue
            if len(a)==1: faces.append((a[0],b[j],b[(j+1)%n]))
            elif len(b)==1: faces.append((a[j],b[0],a[(j+1)%n]))
            else: faces.append((a[j],b[j],b[(j+1)%n],a[(j+1)%n]))
    closed=abs(profile[0][0]-profile[-1][0])<1e-7 and abs(profile[0][1]-profile[-1][1])<1e-7
    if not closed:
        if len(rings[0])>1: faces.append(tuple(reversed(rings[0])))
        if len(rings[-1])>1: faces.append(tuple(rings[-1]))
    return mesh(name,verts,faces,role,0,True)


def cylinder(name,loc,radius,depth,role='metal',axis='Z',n=48):
    return lathe(name,[(0,-depth/2),(radius,-depth/2),(radius,depth/2),(0,depth/2)],loc,axis,role,n)


def ring(name,center,r,tube=.012,role='metal',axis='Z',n=64):
    prof=[(r+tube*cos(2*pi*i/12),tube*sin(2*pi*i/12)) for i in range(13)]
    return lathe(name,prof,center,axis,role,n)


def rounded_path_xz(width,height,y=0,z0=0,r=.14,steps=8):
    # Незамкнутая U-дуга с настоящими радиусами углов.
    pts=[(-width/2,y,z0),(-width/2,y,z0+height-r)]
    for j in range(1,steps+1):
        a=pi-pi/2*j/steps
        pts.append((-width/2+r+r*cos(a),y,z0+height-r+r*sin(a)))
    pts.append((width/2-r,y,z0+height))
    for j in range(1,steps+1):
        a=pi/2-pi/2*j/steps
        pts.append((width/2-r+r*cos(a),y,z0+height-r+r*sin(a)))
    pts.append((width/2,y,z0))
    return pts


def rounded_rect(w,h,r=.05,n=6):
    pts=[]
    for x,y,a in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,pi/2),
                  (-w/2+r,-h/2+r,pi),(w/2-r,-h/2+r,3*pi/2)]:
        for j in range(n+1):
            t=a+j*pi/2/n
            pts.append((x+r*cos(t),y+r*sin(t)))
    return pts


def soft(name,loc,size,role='fabric',roundness=.35,seed=0):
    # Непримитивная мягкая оболочка: сглаженный суперэллипсоид с посадочной вмятиной.
    def s(v,e): return math.copysign(abs(v)**e,v)
    sx,sy,sz=size
    n,m=48,20
    verts=[(loc[0],loc[1],loc[2]-sz/2)]
    for i in range(1,m):
        v=-pi/2+pi*i/m
        for j in range(n):
            u=2*pi*j/n
            x=.5*sx*s(cos(v),roundness)*s(cos(u),roundness)
            y=.5*sy*s(cos(v),roundness)*s(sin(u),roundness)
            z=.5*sz*s(sin(v),roundness)
            ripple=.003*sin(u*5+seed)*sin(v*4+seed)*cos(v)
            verts.append((x+loc[0],y+loc[1],z+loc[2]+ripple))
    top=len(verts)
    verts.append((loc[0],loc[1],loc[2]+sz/2))
    faces=[(0,1+(j+1)%n,1+j) for j in range(n)]
    faces += [(1+i*n+j,1+i*n+(j+1)%n,1+(i+1)*n+(j+1)%n,1+(i+1)*n+j)
              for i in range(m-2) for j in range(n)]
    faces += [(top,1+(m-2)*n+j,1+(m-2)*n+(j+1)%n) for j in range(n)]
    return mesh(name,verts,faces,role,0,True)


def patch(name,fn,nu=24,nv=16,role='fabric',thickness=.003):
    verts=[fn(i/nu,j/nv) for j in range(nv+1) for i in range(nu+1)]
    faces=[(j*(nu+1)+i,j*(nu+1)+i+1,(j+1)*(nu+1)+i+1,(j+1)*(nu+1)+i)
           for j in range(nv) for i in range(nu)]
    ob=mesh(name,verts,faces,role,0,True)
    if thickness:
        mod=ob.modifiers.new('Real fabric / sheet thickness','SOLIDIFY')
        mod.thickness=thickness
    return ob


def bolt(name,loc,axis='Z',r=.009):
    ring(name+'_washer',loc,r*1.25,.0018,'metal',axis,24)
    return cylinder(name+'_hex',loc,r,.009,'metal',axis,6)


def foot(name,x,y,w=.14,d=.14):
    box(name,(x,y,.015),(w,d,.03),'metal',.007)
    for dx in (-w*.3,w*.3):
        for dy in (-d*.3,d*.3): bolt(name+'_anchor',(x+dx,y+dy,.035),r=.007)


def panel_frame(name,w,h,y,z,role='metal',bar_size=.04):
    for x in (-w/2,w/2): box(name+'_stile',(x,y,z+h/2),(bar_size,.06,h),role,.002)
    for zz in (z,z+h): box(name+'_rail',(0,y,zz),(w,.06,bar_size),role,.002)


def slotted_panel(name,center,size,count=12,role='metal',direction='horizontal'):
    x,y,z=center
    w,d,h=size
    panel_frame(name,w,h,y,z-h/2,role,.025)
    for j in range(count):
        zz=z-h/2+(j+.5)*h/count
        ob=box(name+'_louver',(x,y,zz),(w-.05,d,h/count*.55),role,.0015)
        ob.rotation_euler.x=math.radians(15)


def caster(name,x,y,z=.08,r=.06):
    cylinder(name+'_wheel',(x,y,z),r,.04,'rubber','Y',32)
    for yy in (y-.032,y+.032):
        beam(name+'_fork',(x-.015,yy,z),(x+.025,yy,z+.1),.014,.014)
    cylinder(name+'_swivel',(x+.025,y,z+.12),.025,.03)
    bolt(name+'_axle',(x,y-.04,z),'Y',.008)


def lettering(name,text,loc,size=.1,rot=(pi/2,0,0),role='metal'):
    cu=bpy.data.curves.new(name,'FONT')
    cu.body=text
    cu.size=size
    cu.extrude=.0007
    cu.bevel_depth=.0003
    cu.align_x='CENTER'
    ob=bpy.data.objects.new(name,cu)
    COLLECTION.objects.link(ob)
    ob.location=loc
    ob.rotation_euler=rot
    ob.data.materials.append(material(role))
    PARTS.append(ob)
    return ob


def transform(objects, offset=(0,0,0), rotation=(0,0,0)):
    from mathutils import Euler, Matrix
    mat=Matrix.Translation(Vector(offset)) @ Euler(rotation).to_matrix().to_4x4()
    for ob in objects:
        ob.matrix_world=mat@ob.matrix_world


def since(index):
    return PARTS[index:]
