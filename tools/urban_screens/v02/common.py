"""Сечения и студия для пяти предметов, заново построенных по фотографиям."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import math
from math import sin,cos,pi
import bpy
import bmesh
from mathutils import Vector,Matrix
import meshkit as k

ROOT=Path(__file__).resolve().parents[3]/'_asset_src/urban_realrefs_v02'
DELIVERY=Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references')


def neutral_material(role):
    if role in k.MATS: return k.MATS[role]
    m=bpy.data.materials.new('REVIEW_'+role)
    m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    grey={'rubber':.045,'interior':.065,'screen':.065,'plastic':.14,'glass':.2,
          'metal':.48,'chrome':.58,'stone':.52,'concrete':.48,'fabric':.31,'paint':.36,
          'diffuser':.62,'wood':.42,'reflector':.62}.get(role,.4)
    p.inputs['Base Color'].default_value=(grey,grey,grey,1)
    p.inputs['Roughness'].default_value=.45
    if role in ('metal','chrome'):
        p.inputs['Metallic'].default_value=.65
        p.inputs['Roughness'].default_value=.31
    if role=='glass':
        p.inputs['Transmission Weight'].default_value=.92
        p.inputs['Roughness'].default_value=.1
        p.inputs['IOR'].default_value=1.46
    if role=='rubber': p.inputs['Roughness'].default_value=.7
    m.diffuse_color=(grey,grey,grey,1)
    m['purpose']='Neutral diagnostic material; no production UV or texture layers'
    k.MATS[role]=m
    return m


def start():
    k.initialize()
    k.material=neutral_material


def boolean(ob,cutter,operation='DIFFERENCE'):
    bpy.context.view_layer.objects.active=ob
    mod=ob.modifiers.new('Actual modelled recess','BOOLEAN')
    mod.operation=operation; mod.solver='EXACT'; mod.object=cutter
    while ob.modifiers[0]!=mod: bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if cutter in k.PARTS: k.PARTS.remove(cutter)
    bpy.data.objects.remove(cutter,do_unlink=True)


def rounded_panel(name,w,h,depth,center,role='paint',r=.02,bevel=.001):
    x,y,z=center
    profile=[(u+x,v+z) for u,v in k.rounded_rect(w,h,r,10)]
    return k.extrude(name,profile,'Y',y-depth/2,y+depth/2,role,bevel)


def rounded_opening(ob,name,w,h,center,depth=.2,r=.015):
    cut=rounded_panel('TEMP_'+name,w,h,depth,center,'interior',r,0)
    boolean(ob,cut)


def sheet(name,points,role='metal',thickness=.003,bevel=0,smooth=False):
    ob=k.mesh(name,points,[tuple(range(len(points)))],role,0,smooth)
    mod=ob.modifiers.new('Physical sheet thickness','SOLIDIFY'); mod.thickness=thickness
    if bevel:
        mod=ob.modifiers.new('Small formed edge radius','BEVEL'); mod.width=bevel; mod.segments=2
    return ob


def ring_rect(name,outer,inner,y_front,y_back,role='plastic'):
    # Замкнутая прямоугольная рама с действительным сквозным проёмом.
    assert len(outer)==len(inner)
    n=len(outer)
    verts=[(x,y,z) for y in (y_front,y_back) for loop in (outer,inner) for x,z in loop]
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                      (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)])
    return k.mesh(name,verts,faces,role,.001)


def cap_curve(name,points,role='metal',r=.005):
    return k.section(name,points,r,role,12)


def shell_loft(name,rings,role='paint',smooth=True,caps=True,bevel=0):
    n=len(rings[0]); assert all(len(r)==n for r in rings)
    verts=[v for ring in rings for v in ring]
    faces=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i)
           for j in range(len(rings)-1) for i in range(n)]
    if caps: faces += [tuple(reversed(range(n))),tuple((len(rings)-1)*n+i for i in range(n))]
    return k.mesh(name,verts,faces,role,bevel,smooth)


def tube_rect(name,a,b,w=.05,d=.05,t=.003,role='metal'):
    # Замкнутое RHS-сечение с внутренними стенками и кольцевыми торцами.
    v=Vector(b)-Vector(a)
    outer=[(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]
    inner=[(-w/2+t,-d/2+t),(w/2-t,-d/2+t),(w/2-t,d/2-t),(-w/2+t,d/2-t)]
    verts=[(x,y,z) for z in (0,v.length) for ring in (outer,inner) for x,y in ring]
    faces=[]
    for i in range(4):
        j=(i+1)%4
        faces.extend([(i,j,4+j,4+i),(8+i,12+i,12+j,8+j),(i,8+i,8+j,j),(4+i,4+j,12+j,12+i)])
    ob=k.mesh(name,verts,faces,role,.0008)
    ob.rotation_mode='QUATERNION'; ob.rotation_quaternion=v.to_track_quat('Z','Y')
    ob.location=Vector(a)
    return ob


def bolt_line(name,a,b,count=6,r=.004):
    a,b=Vector(a),Vector(b)
    for i in range(count): k.bolt(name,tuple(a.lerp(b,i/max(1,count-1))),r=r)


def sharp_planar(ob,angle=.55):
    # Большие плоскости остаются плоскими, непрерывная обводка — гладкой.
    if ob.type!='MESH': return
    bm=bmesh.new(); bm.from_mesh(ob.data)
    for edge in bm.edges:
        if len(edge.link_faces)==2:
            edge.smooth=edge.calc_face_angle()<angle
    bm.to_mesh(ob.data); bm.free()


def studio(objects,low,high):
    sc=bpy.context.scene
    collection=bpy.data.collections.new('STUDIO | neutral lights, no export')
    sc.collection.children.link(collection)
    camdata=bpy.data.cameras.new('Review_camera'); cam=bpy.data.objects.new('Review_camera',camdata)
    collection.objects.link(cam); sc.camera=cam
    try: sc.render.engine='BLENDER_EEVEE'
    except TypeError: sc.render.engine='CYCLES'; sc.cycles.samples=24; sc.cycles.use_denoising=True
    sc.render.resolution_x=1400; sc.render.resolution_y=1050; sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'
    if not sc.world: sc.world=bpy.data.worlds.new('Neutral grey world')
    sc.world.use_nodes=True
    bg=next(n for n in sc.world.node_tree.nodes if n.type=='BACKGROUND')
    bg.inputs['Color'].default_value=(.3,.3,.3,1); bg.inputs['Strength'].default_value=.55
    center=(low+high)/2; span=max(high-low)
    def area(name,pos,power,size):
        data=bpy.data.lights.new(name,'AREA'); data.energy=power; data.shape='DISK'; data.size=size
        ob=bpy.data.objects.new(name,data); collection.objects.link(ob)
        ob.location=center+Vector(pos)*span
        ob.rotation_euler=(center-ob.location).to_track_quat('-Z','Y').to_euler()
    area('Large soft key',(1.2,-1.5,2.2),550*span**2,span*1.8)
    area('Soft fill',(-1.4,-.2,1.0),260*span**2,span*1.6)
    area('Rim softbox',(.4,1.4,1.7),450*span**2,span*1.3)
    floor=bpy.data.meshes.new('Studio_floor')
    size=max(12,span*8)
    floor.from_pydata([(-size,-size,-.012),(size,-size,-.012),(size,size,-.012),(-size,size,-.012)],[],[(0,1,2,3)])
    ob=bpy.data.objects.new('Studio_floor',floor); collection.objects.link(ob)
    m=bpy.data.materials.new('Studio_matte_grey'); m.use_nodes=True
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    p.inputs['Base Color'].default_value=(.27,.27,.27,1); p.inputs['Roughness'].default_value=.9
    floor.materials.append(m)
    sc.view_settings.view_transform='AgX'
    sc.render.film_transparent=False
    return cam
