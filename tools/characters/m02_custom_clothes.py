"""Original M02 clothing geometry: drafted panels, sewn details and constructed boots.

No clothing mesh, fitting data or texture from the installed clothing packs is used.
The accepted character is an unchanged fitting mannequin in a separate scene copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import addon_utils
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[2]
SOURCE=Path('E:/Models Blender/RING_NPC_2026-10-20_v01/M02_Appearance_v05/M02_Appearance_v05.blend')
WORK=ROOT/'_asset_src/npc_m02'
PI=math.pi


def clamp(x,lo=0.,hi=1.):
    return max(lo,min(hi,x))


def smooth(a,b,x):
    t=clamp((x-a)/(b-a))
    return t*t*(3-2*t)


def mix(a,b,t):
    return a*(1-t)+b*t


def profile(z,keys):
    if z<=keys[0][0]: return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if z<=b: return mix(x,y,smooth(a,b,z))
    return keys[-1][1]


def activate(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj


def collection(name,parent=None):
    result=bpy.data.collections.new(name)
    (parent.children if parent else bpy.context.scene.collection.children).link(result)
    return result


def material(name,color,roughness=.65,metallic=0):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    shader=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=roughness
    shader.inputs['Metallic'].default_value=metallic
    mat.diffuse_color=(*color,1)
    return mat


def mesh_object(name,verts,faces,col,mat,weld=False,sub=0,thickness=0):
    mesh=bpy.data.meshes.new(name+' | editable surface')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    bm=bmesh.new()
    bm.from_mesh(mesh)
    if weld:
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000015)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.000001)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm,geom=loose,context='VERTS')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj=bpy.data.objects.new(name,mesh)
    col.objects.link(obj)
    if mat: mesh.materials.append(mat)
    for face in mesh.polygons: face.use_smooth=True
    if sub:
        mod=obj.modifiers.new('Editable fabric smoothing','SUBSURF')
        mod.levels=1
        mod.render_levels=sub
    if thickness:
        mod=obj.modifiers.new('Real material thickness','SOLIDIFY')
        mod.thickness=thickness
        mod.offset=-1
        mod.use_even_offset=False
    obj['authoring']='Original RING clothing geometry; parametric sewing draft and constructed surfaces, no preset clothing meshes.'
    return obj


def line_mesh(name,paths,radius,col,mat,cyclic=False):
    curve=bpy.data.curves.new(name,'CURVE')
    curve.dimensions='3D'
    curve.resolution_u=2
    curve.bevel_depth=radius
    curve.bevel_resolution=2
    for path in paths:
        spline=curve.splines.new('POLY')
        spline.points.add(len(path)-1)
        for point,co in zip(spline.points,path): point.co=(*co,1)
        spline.use_cyclic_u=cyclic
    obj=bpy.data.objects.new(name,curve)
    col.objects.link(obj)
    curve.materials.append(mat)
    activate(obj)
    bpy.ops.object.convert(target='MESH')
    obj=bpy.context.object
    for face in obj.data.polygons: face.use_smooth=True
    return obj


def ribbon(name,loop,width,normal,col,mat,closed=True):
    center=sum((Vector(p) for p in loop),Vector())/len(loop)
    verts=[]
    for amount in [0,.08,.92,1]:
        for p in loop:
            p=Vector(p)
            direction=(p-center).normalized()
            verts.append(p+direction*(width*amount)+Vector(normal)*.001)
    n=len(loop)
    faces=[]
    for row in range(3):
        for i in range(n if closed else n-1):
            j=(i+1)%n
            faces.append((row*n+i,row*n+j,(row+1)*n+j,(row+1)*n+i))
    return mesh_object(name,verts,faces,col,mat,sub=1,thickness=.0014)


def stitches(name,paths,col,mat,radius=.00023):
    dashed=[]
    for path in paths:
        points=[Vector(p) for p in path]
        length=sum((b-a).length for a,b in zip(points,points[1:]))
        if length<.001: continue
        distance=0.0
        for a,b in zip(points,points[1:]):
            segment=(b-a).length
            if segment<1e-9: continue
            direction=(b-a)/segment
            t=0.
            while t<segment:
                phase=(distance+t)%.0045
                take=min(segment-t,.0026-phase if phase<.0026 else .0045-phase)
                if phase<.0026 and take>.00015:
                    dashed.append([a+direction*t,a+direction*(t+take)])
                t+=max(take,.00001)
            distance+=segment
    return line_mesh(name,dashed,radius,col,mat) if dashed else None


def front_patch(name,surface,col,mat,thread,x0,x1,z0,z1,front=-1,bulge=.002,taper=.0):
    verts=[]
    faces=[]
    nx,nz=12,18
    for r in range(nz+1):
        v=r/nz
        scale=1-taper*(1-v)
        for i in range(nx+1):
            u=i/nx
            x=(x0+x1)/2+(u-.5)*(x1-x0)*scale
            z=mix(z0,z1,v)+.004*(abs(2*u-1)**8)*(1-v)**8
            ys=surface.ys(x,z)
            y=ys[0 if front<0 else 1]+front*(.002+bulge*math.sin(PI*u)*math.sin(PI*v))
            verts.append(Vector((x,y,z)))
    for r in range(nz):
        for i in range(nx):
            a=r*(nx+1)+i
            faces.append((a,a+1,a+nx+2,a+nx+1))
    obj=mesh_object(name,verts,faces,col,mat,sub=1,thickness=.0012)
    left=[verts[r*(nx+1)]+Vector((0,front*.0008,0)) for r in range(nz+1)]
    right=[verts[r*(nx+1)+nx]+Vector((0,front*.0008,0)) for r in range(nz+1)]
    bottom=[verts[i]+Vector((0,front*.0008,0)) for i in range(nx+1)]
    stitches(name+' | sewn edges',[left,right,bottom],col,thread)
    return obj


class BodySurface:
    def __init__(self,body):
        evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        self.points=[evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        self.tree=BVHTree.FromPolygons(self.points,[tuple(p.vertices) for p in mesh.polygons])
        evaluated.to_mesh_clear()

    def ys(self,x,z,fallback=(-.12,.07)):
        a,*_=self.tree.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
        b,*_=self.tree.ray_cast(Vector((x,1,z)),Vector((0,-1,0)))
        return (a.y,b.y) if a is not None and b is not None else fallback

    def nearest(self,p):
        return self.tree.find_nearest(Vector(p))


def shirt(col,mats,body):
    verts=[]
    faces=[]
    panel={}
    nx=64
    lower=[.89+(.365+.02)*i/26 for i in range(27)]
    # The actual armhole is below the biceps, not a pasted-on cylinder.
    arm_bottom=1.365
    arm_top=1.535
    lower=[.89+(arm_bottom-.89)*i/40 for i in range(40)]
    upper=[1.45+.085*math.sin(-PI/2+PI*i/12) for i in range(13)]
    rows=lower+upper
    first_arm=len(lower)
    nr=len(rows)
    cut=10
    def halfwidth(z):
        return profile(z,[(.89,.205),(1.05,.205),(1.27,.232),(1.365,.235),(1.535,.228)])
    def coordinate(side,row,i):
        z=rows[row]
        u=2*i/nx-1
        x=u*halfwidth(z)
        if row==nr-1:
            if abs(i-nx//2)<=cut:
                t=abs(i-nx//2)/cut
                z=(1.510+.030*t*t) if side<0 else (1.536+.004*t*t)
            else:
                z=1.54-.005*smooth(.07,.228,abs(x))
        front=profile(z,[(.89,-.187),(1.08,-.185),(1.30,-.167),(1.40,-.145),(1.50,-.110),(1.54,-.095)])
        back=profile(z,[(.89,.170),(1.08,.155),(1.30,.108),(1.40,.100),(1.50,.078),(1.54,.064)])
        cy=(front+back)/2
        ry=max((back-front)/2,.070)
        arm_width=.073*math.sqrt(max(0,1-((rows[row]-1.45)/.085)**2)) if row>=first_arm else 0
        edge=abs(u)**8
        cy=mix(cy,-.010,edge)
        y=cy+side*(ry*math.sqrt(max(0,1-u*u))+edge*arm_width)
        if abs(u)<.90 and z>1.40:
            surface=body.ys(x,z,fallback=(y,y))
            y=min(y,surface[0]-.010) if side<0 else max(y,surface[1]+.010)
        if row==nr-1 and abs(i-nx//2)<=cut:
            t=abs(i-nx//2)/cut
            y=(-.078 if side<0 else .052)*math.sqrt(max(0,1-t*t))-.008*t*t
        # Directed hanging folds, plus diagonal stress from each armhole.
        hanging=(1-smooth(1.20,1.42,z))*(.0038*math.sin(42*x+1.1*math.sin(6*z))+.0013*math.sin(78*x-4*z))
        d=1.33-z-.65*(.22-abs(x))
        tension=.0024*math.exp(-(d/.055)**2)*math.sin(95*d+1.2*x)
        y+=side*(hanging+tension)*(1-abs(u)**12)
        return Vector((x,y,z))
    for side in [-1,1]:
        ids=[]
        for r in range(nr):
            row=[]
            for i in range(nx+1):
                row.append(len(verts))
                verts.append(coordinate(side,r,i))
            ids.append(row)
        panel[side]=ids
        for r in range(nr-1):
            for i in range(nx):
                face=(ids[r][i],ids[r][i+1],ids[r+1][i+1],ids[r+1][i])
                faces.append(face if side<0 else tuple(reversed(face)))
    # Sew shoulders, keeping a genuinely open neckline.
    for i in range(nx):
        if nx//2-cut<=i<nx//2+cut: continue
        faces.append((panel[-1][-1][i],panel[1][-1][i],panel[1][-1][i+1],panel[-1][-1][i+1]))
    cuff_loops=[]
    for end in [0,nx]:
        sign=-1 if end==0 else 1
        loop=[panel[-1][r][end] for r in range(first_arm,nr)]
        loop+=[panel[1][r][end] for r in range(nr-2,first_arm,-1)]
        n=len(loop)
        ring=loop
        for k in range(1,14):
            t=k/13
            nxt=[]
            for j,original in enumerate(loop):
                original=Vector(verts[original])
                angle=-PI/2+2*PI*j/n
                outer=Vector((sign*.390,-.003-.055*math.cos(angle),1.465+.060*math.sin(angle)))
                p=original.lerp(outer,t)
                p.y+=.002*math.sin(3*angle+5*t)*math.sin(PI*t)
                nxt.append(len(verts))
                verts.append(p)
            for j in range(n):
                j2=(j+1)%n
                faces.append((ring[j],ring[j2],nxt[j2],nxt[j]))
            ring=nxt
        cuff_loops.append([Vector(verts[i]) for i in ring])
    # Matching seam vertices are welded; openings remain only at neck, hem and cuffs.
    main=mesh_object('M02_Custom_TShirt',verts,faces,col,mats['shirt'],weld=True,sub=2,thickness=.0015)
    neckline=[Vector(verts[panel[-1][-1][i]]) for i in range(nx//2-cut,nx//2+cut+1)]
    neckline+=[Vector(verts[panel[1][-1][i]]) for i in range(nx//2+cut,nx//2-cut-1,-1)]
    ribbon('TShirt | rib collar',neckline,.008,(0,-.2,.1),col,mats['rib'])
    hem=[Vector(verts[panel[-1][0][i]]) for i in range(nx+1)]
    hem+=[Vector(verts[panel[1][0][i]]) for i in range(nx-1,0,-1)]
    # Turned hem and cuffs are separate bands, not painted stripes.
    hem_upper=[p+Vector((0,0,.011)) for p in hem]
    bandverts=hem+hem_upper
    n=len(hem)
    mesh_object('TShirt | turned bottom hem',bandverts,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],col,mats['rib'],sub=1,thickness=.0016)
    for side,loop in zip(['R','L'],cuff_loops):
        sign=-1 if side=='R' else 1
        inset=[p-Vector((sign*.011,0,0)) for p in loop]
        n=len(loop)
        mesh_object('TShirt | sleeve cuff '+side,loop+inset,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],col,mats['rib'],sub=1,thickness=.0015)
    surface=BodySurface(main)
    pocket=front_patch('TShirt | open chest pocket',surface,col,mats['shirt'],mats['thread'],.052,.137,1.222,1.325,bulge=.0025)
    seam=[]
    for i in range(25):
        x=mix(.054,.135,i/24)
        seam.append(Vector((x,surface.ys(x,1.319)[0]-.004,1.319)))
    stitches('TShirt | pocket top hem',[seam],col,mats['thread'])
    stitches('TShirt | hem stitching',[[p+Vector((0,-.001,.007)) for p in hem]],col,mats['thread'])
    return main


def trousers(col,mats,body):
    verts=[]
    faces=[]
    nz=64
    nx=24
    crotch=.805
    def point(side,front,z,u):
        center=profile(z,[(.15,.090),(.50,.104),(.78,.105),(.89,.102),(1.04,.092)])
        radius=profile(z,[(.15,.071),(.30,.067),(.53,.073),(.69,.082),(.805,.103),(1.04,.092)])
        hip=smooth(crotch,crotch+.07,z)
        # The two inner edges meet as front/back rise seams above the crotch.
        inner=mix(max(.005,center-radius),0,smooth(.77,crotch,z))
        outer=profile(z,[(.15,.163),(.50,.177),(.78,.200),(.91,.202),(1.04,.181)])
        x=side*mix(inner,outer,u)
        front_y,back_y=body.ys(side*center,min(z,.99),fallback=(-.09,.06))
        cy=(front_y+back_y)/2
        ry=(back_y-front_y)/2+.014+.022*(1-smooth(.15,.29,z))
        leg_shape=math.sqrt(max(0,1-(2*u-1)**2))
        hip_shape=math.sqrt(max(0,1-(abs(x)/outer)**2))
        shape=mix(leg_shape,hip_shape,hip)
        y=cy+front*ry*shape
        # Hip front is slightly fuller; waist takes up the excess fabric.
        if z>.805 and u<.98:
            hf,hb=body.ys(x,z,fallback=(y,y))
            if front<0: y=min(y,hf-.012*hip)
            else: y=max(y,hb+.012*hip)
        if u==0 and z>=crotch:
            hf,hb=body.ys(0,z)
            y=(hf+hb)/2+front*((hb-hf)/2+.014)*smooth(crotch,crotch+.07,z)
        # Knee, crotch and boot-top folds: explicit placement and direction.
        knee=math.exp(-((z-.52)/.085)**2)
        ankle=math.exp(-((z-.235)/.070)**2)
        groin=math.exp(-((z-(.88-.25*u))/.045)**2)
        fold=(.0058*math.sin(115*z+3.2*u+side)*knee+
              .0070*math.sin(127*z-5*u+side)*ankle+
              .0045*math.sin(145*z+11*u)*groin)
        y+=front*fold*math.sin(PI*u)
        x+=side*.38*fold*math.sin(PI*u)
        return Vector((x,y,z))
    panels={}
    heights=sorted(set([.15+(1.04-.15)*r/nz for r in range(nz+1)]+[crotch]))
    nz=len(heights)-1
    for side in [-1,1]:
        for front in [-1,1]:
            ids=[]
            for r in range(nz+1):
                z=heights[r]
                row=[]
                for i in range(nx+1):
                    row.append(len(verts))
                    verts.append(point(side,front,z,i/nx))
                ids.append(row)
            panels[(side,front)]=ids
            for r in range(nz):
                for i in range(nx):
                    faces.append((ids[r][i],ids[r][i+1],ids[r+1][i+1],ids[r+1][i]))
    main=mesh_object('M02_Custom_Work_Trousers',verts,faces,col,mats['pants'],weld=True,sub=2,thickness=.0018)
    # Waistband, with a separate fly and belt loops to be added on the fitted surface.
    loop=[]
    for side,front,reverse in [(-1,-1,True),(1,-1,False),(1,1,True),(-1,1,False)]:
        indices=panels[(side,front)][-1]
        if reverse: indices=list(reversed(indices))
        loop.extend(Vector(verts[i]) for i in indices)
    waist_up=[p+Vector((0,0,.031)) for p in loop]
    n=len(loop)
    mesh_object('Trousers | waistband',loop+waist_up,[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],col,mats['pants'],weld=True,sub=1,thickness=.0022)
    surface=BodySurface(main)
    for side in [-1,1]:
        x0,x1=sorted((side*.037,side*.166))
        front_patch('Trousers | double knee '+str(side),surface,col,mats['pants'],mats['thread'],x0,x1,.395,.775,bulge=.0015,taper=.13)
        x0,x1=sorted((side*.055,side*.146))
        front_patch('Trousers | rear patch pocket '+str(side),surface,col,mats['pants'],mats['thread'],x0,x1,.903,1.010,front=1,bulge=.004,taper=.08)
        path=[]
        for i in range(30):
            t=i/29
            x=side*mix(.162,.100,t)
            z=mix(1.025,.947,t)
            path.append(Vector((x,surface.ys(x,z)[0]-.003,z)))
        line_mesh('Trousers | pocket entry '+str(side),[path],.0012,col,mats['pants'])
        stitches('Trousers | entry topstitch '+str(side),[[p+Vector((side*.003,-.0005,.003)) for p in path]],col,mats['thread'])
    front_patch('Trousers | fly shield',surface,col,mats['pants'],mats['thread'],-.009,.022,.895,1.038,bulge=.0005)
    for angle in [-PI/2,-PI/4,PI/5,PI/2,4*PI/5,5*PI/4]:
        x=.17*math.cos(angle)
        front=-1 if math.sin(angle)<0 else 1
        points=[]
        for v in range(9):
            z=1.024+v/8*.046
            for u in range(3):
                xx=x+(u-1)*.004
                y=body.ys(xx,min(z,1.035))[0 if front<0 else 1]+front*(.016+.003*math.sin(PI*v/8))
                points.append((xx,y,z))
        mesh_object('Trousers | belt loop '+str(round(angle,2)),points,
            [(r*3+i,r*3+i+1,(r+1)*3+i+1,(r+1)*3+i) for r in range(8) for i in range(2)],col,mats['pants'],sub=1,thickness=.0015)
    return main


def boots(col,mats,body):
    for side in [-1,1]:
        label='L' if side>0 else 'R'
        def contour(theta):
            y=-.080+.150*math.sin(theta)
            width=profile(y,[(-.230,.050),(-.160,.058),(-.080,.049),(.015,.043),(.070,.042)])
            return Vector((side*.083+width*math.cos(theta),y,0))
        count=64
        sole_verts=[]
        sole_faces=[]
        for z,scale in [(-.022,.985),(-.019,1.018),(.001,1.018),(.006,.975)]:
            for i in range(count):
                p=contour(2*PI*i/count)
                p.x=side*.083+(p.x-side*.083)*scale
                p.y=-.080+(p.y+.080)*scale
                p.z=z+.003*smooth(-.12,-.23,p.y)
                sole_verts.append(p)
        for r in range(3):
            for i in range(count):
                j=(i+1)%count
                sole_faces.append((r*count+i,r*count+j,(r+1)*count+j,(r+1)*count+i))
        sole_faces+=[tuple(reversed(range(count))),tuple(3*count+i for i in range(count))]
        sole=mesh_object('Boot '+label+' | shaped outsole',sole_verts,sole_faces,col,mats['rubber'])
        bevel=sole.modifiers.new('Outsole edge radii','BEVEL')
        bevel.width=.0014
        bevel.segments=3
        bevel.affect='EDGES'
        def upper(u,theta,offset=0):
            # Horizontal last sections establish a rounded toe, nearly flat vamp,
            # distinct instep and upright quarters. A linear foot-to-ankle loft
            # would make an implausible wedge instead of a boot.
            z=.006+.172*u
            front_y=profile(u,[(0,-.228),(.08,-.229),(.18,-.222),(.27,-.206),(.36,-.156),(.46,-.104),(.58,-.075),(.75,-.063),(1,-.062)])
            back_y=profile(u,[(0,.068),(.20,.062),(.45,.051),(.75,.048),(1,.055)])
            y=mix((front_y+back_y)/2,front_y if math.sin(theta)<0 else back_y,abs(math.sin(theta)))
            foot_width=profile(y,[(-.230,.044),(-.160,.058),(-.080,.049),(.015,.043),(.070,.039)])
            width=mix(foot_width,.050,smooth(.35,.80,u))
            cx=mix(side*.083,side*.096,smooth(.22,.7,u))
            p=Vector((cx+width*math.cos(theta),y,z))
            radial=Vector((p.x-side*.09,p.y+.015,0)).normalized()
            p+=radial*offset
            p+=radial*(.0010*math.sin(4*theta+13*u)*math.exp(-((u-.57)/.20)**2))
            return p
        levels=[0,.02,.06,.10,.14,.18,.22,.27,.32,.36,.40,.46,.52,.58,.65,.72,.80,.88,.96,1]
        verts=[upper(u,2*PI*i/count) for u in levels for i in range(count)]
        faces=[]
        gap=.30
        for r,u in enumerate(levels[:-1]):
            for i in range(count):
                theta=2*PI*(i+.5)/count
                distance=abs((theta-1.5*PI+PI)%(2*PI)-PI)
                if u>=.38 and distance<gap: continue
                j=(i+1)%count
                faces.append((r*count+i,r*count+j,(r+1)*count+j,(r+1)*count+i))
        mesh_object('Boot '+label+' | leather quarters and vamp',verts,faces,col,mats['leather'],sub=2,thickness=.0028)
        # Tongue sits behind the open lacing slit, not painted onto a closed upper.
        tongue=[]
        tf=[]
        for r in range(20):
            u=.34+.69*r/19
            for j in range(11):
                theta=1.5*PI+mix(-.49,.49,j/10)
                p=upper(min(u,1),theta,-.0015)
                p.z+=max(0,u-1)*.20
                tongue.append(p)
        for r in range(19):
            for j in range(10):
                a=r*11+j
                tf.append((a,a+1,a+12,a+11))
        mesh_object('Boot '+label+' | separate gusseted tongue',tongue,tf,col,mats['leather'],sub=1,thickness=.002)
        collar=[upper(1,2*PI*i/count,.0015) for i in range(count)]
        collar_inner=[p-Vector((0,0,.015)) for p in collar]
        mesh_object('Boot '+label+' | padded collar',collar+collar_inner,
            [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)],col,mats['leather'],sub=1,thickness=.005)
        welt=[upper(.01,2*PI*i/count,.0015)+Vector((0,0,.002)) for i in range(count+1)]
        line_mesh('Boot '+label+' | welt',[welt],.0018,col,mats['leather'])
        stitches('Boot '+label+' | welt stitching',[[p+Vector((0,0,.0014)) for p in welt]],col,mats['thread'],.00025)
        # Six pairs of eyelets and crossed round laces.
        eyes=[]
        for u in [.45,.54,.63,.72,.82,.93]:
            row=[]
            for direction in [-1,1]:
                theta=1.5*PI+direction*.39
                p=upper(u,theta,.0040)
                normal=Vector((p.x-side*.096,p.y+.006,0)).normalized()
                tangent=Vector((0,0,1))
                across=normal.cross(tangent).normalized()
                rim=[]
                rf=[]
                n,m=16,6
                for i in range(n):
                    ang=2*PI*i/n
                    radial=tangent*math.cos(ang)+across*math.sin(ang)
                    for j in range(m):
                        b=2*PI*j/m
                        rim.append(p+radial*(.0022+.00055*math.cos(b))+normal*(.00055*math.sin(b)))
                for i in range(n):
                    for j in range(m):
                        rf.append((i*m+j,((i+1)%n)*m+j,((i+1)%n)*m+(j+1)%m,i*m+(j+1)%m))
                mesh_object('Boot '+label+' | eyelet '+str(len(eyes))+' '+str(direction),rim,rf,col,mats['metal'])
                row.append(p+normal*.0010)
            eyes.append(row)
        lace_paths=[]
        for i in range(len(eyes)-1):
            for direction in [0,1]:
                a=eyes[i][direction]
                b=eyes[i+1][1-direction]
                path=[]
                for j in range(13):
                    t=j/12
                    p=a.lerp(b,t)
                    p.y-=.006*math.sin(PI*t)
                    p.z+=.0012*math.sin(PI*t)*(1 if direction==0 else -1)
                    path.append(p)
                lace_paths.append(path)
        line_mesh('Boot '+label+' | crossed laces',lace_paths,.0010,col,mats['rubber'])
        seam_paths=[]
        for direction in [-1,1]:
            seam_paths.append([upper(u,1.5*PI+direction*.57,.0040) for u in [.33+i*.66/40 for i in range(41)]])
        seam_paths.append([upper(.21,PI+PI*i/count,.0040) for i in range(count+1)])
        stitches('Boot '+label+' | panel topstitch',seam_paths,col,mats['thread'],.00023)
        # Discrete outsole lugs, following the shoe outline, with open channels.
        for y,width in [(.040,.060),(.010,.058),(-.050,.064),(-.110,.082),(-.170,.075),(-.205,.052)]:
            for section in [-1,1]:
                cx=side*.083+section*width*.26
                dx=width*.21
                dy=.009
                ring=[(cx-dx,y-dy),(cx+dx,y-dy),(cx+dx*.85,y+dy),(cx-dx*.85,y+dy)]
                lv=[(x,yy,z) for z in [-.025,-.020] for x,yy in ring]
                lf=[(0,3,2,1),(4,5,6,7)]+[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]
                lug=mesh_object('Boot '+label+' | tread lug',lv,lf,col,mats['rubber'])
                bevel=lug.modifiers.new('Lug edge radius','BEVEL')
                bevel.width=.0008
                bevel.segments=2


def bind(objects,body,rig):
    for obj in objects:
        if obj.type!='MESH': continue
        for group in body.vertex_groups:
            if group.name in rig.data.bones and rig.data.bones[group.name].use_deform:
                obj.vertex_groups.new(name=group.name)
        activate(obj)
        transfer=obj.modifiers.new('Fit weights from M02 anatomy','DATA_TRANSFER')
        transfer.object=body
        transfer.use_vert_data=True
        transfer.data_types_verts={'VGROUP_WEIGHTS'}
        transfer.vert_mapping='POLYINTERP_NEAREST'
        transfer.layers_vgroup_select_src='ALL'
        transfer.layers_vgroup_select_dst='NAME'
        while obj.modifiers[0]!=transfer:
            bpy.ops.object.modifier_move_up(modifier=transfer.name)
        bpy.ops.object.modifier_apply(modifier=transfer.name)
        arm=obj.modifiers.new('M02 shared anatomical rig','ARMATURE')
        arm.object=rig
        while obj.modifiers[0]!=arm:
            bpy.ops.object.modifier_move_up(modifier=arm.name)
        world=obj.matrix_world.copy()
        obj.parent=rig
        obj.matrix_world=world


def wardrobe_controls(root,modules,body,rig):
    controls=bpy.data.objects.new('M02_Clothing_Controls',None)
    root.objects.link(controls)
    controls.empty_display_type='PLAIN_AXES'
    controls.empty_display_size=.15
    controls['readme']='Toggle shirt / trousers / boots. Body masks follow the selected clothes without deleting anatomy. Geometry review, no game export.'
    for key,col in modules.items():
        controls[key]=bool(col.objects)
        controls.id_properties_ui(key).update(description='Show this original garment and its corresponding reversible body mask')
        for obj in col.all_objects:
            covered_by_shirt=(key=='trousers' and any(token in obj.name for token in [
                'rear patch pocket','waistband','fly shield','belt loop','pocket entry','entry topstitch']))
            for path in ['hide_viewport','hide_render']:
                driver=obj.driver_add(path).driver
                variable=driver.variables.new()
                variable.name='enabled'
                variable.targets[0].id=controls
                variable.targets[0].data_path='["'+key+'"]'
                if covered_by_shirt:
                    variable=driver.variables.new()
                    variable.name='top_layer'
                    variable.targets[0].id=controls
                    variable.targets[0].data_path='["shirt"]'
                    driver.expression='not enabled or top_layer'
                else:
                    driver.expression='not enabled'
    covered={key:[] for key in modules}
    for vertex in body.data.vertices:
        x,y,z=body.matrix_world @ vertex.co
        if (.905<z<1.478 and abs(x)<.233) or (.185<abs(x)<.367 and 1.383<z<1.513):
            covered['shirt'].append(vertex.index)
        if .175<z<1.065: covered['trousers'].append(vertex.index)
        if z<.170: covered['boots'].append(vertex.index)
    for key,indices in covered.items():
        group=body.vertex_groups.new(name='ClothingMask_'+key)
        if indices: group.add(indices,1.0,'REPLACE')
        mod=body.modifiers.new('Clothing | hide anatomy under '+key,'MASK')
        mod.vertex_group=group.name
        mod.invert_vertex_group=True
        mod.use_smooth=False
        activate(body)
        while body.modifiers[0]!=mod:
            bpy.ops.object.modifier_move_up(modifier=mod.name)
        for path in ['show_viewport','show_render']:
            driver=mod.driver_add(path).driver
            variable=driver.variables.new()
            variable.name='enabled'
            variable.targets[0].id=controls
            variable.targets[0].data_path='["'+key+'"]'
            driver.expression='enabled'
    world=rig.matrix_world.copy()
    rig.parent=controls
    rig.matrix_world=world
    controls.location.z=.025
    return controls


def render_setup(samples):
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=samples
    scene.cycles.use_denoising=True
    preferences=bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type='OPTIX'
    preferences.get_devices()
    for d in preferences.devices: d.use=d.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.use for d in preferences.devices) else 'CPU'
    scene.render.resolution_x=1400
    scene.render.resolution_y=1600
    scene.render.resolution_percentage=100
    for name,pos,target,scale in [
        ('Custom_Clothes_Front',(0,-4,.95),(0,0,.95),2.20),
        ('Custom_Clothes_Back',(0,4,.95),(0,0,.95),2.20),
        ('Custom_Clothes_ThreeQuarter',(2.7,-4,1.2),(0,0,.94),2.20),
        ('Custom_Clothes_Boots',(.65,-.95,.40),(.0,-.04,.13),.58),
    ]:
        data=bpy.data.cameras.new(name)
        camera=bpy.data.objects.new(name,data)
        bpy.data.collections['06_Review_Studio'].objects.link(camera)
        camera.location=pos
        camera.rotation_euler=(Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        data.type='ORTHO'
        data.ortho_scale=scale
    scene.camera=bpy.data.objects['Custom_Clothes_ThreeQuarter']
    return scene


def build(args):
    out=WORK/args.version
    out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons:
        bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    body=bpy.data.objects['M02_Body_Head']
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    body_surface=BodySurface(body)
    root=collection('08_Original_Clothing_Assets')
    top=collection('01_Original_TShirt_M02',root)
    pants=collection('02_Original_Work_Trousers_M02',root)
    footwear=collection('03_Original_Work_Boots_M02',root)
    mats={
        'shirt':material('Draft | medium grey cotton',(.205,.22,.215)),
        'rib':material('Draft | ribbing and turned edges',(.17,.18,.175)),
        'pants':material('Draft | warm grey canvas',(.235,.217,.185)),
        'leather':material('Draft | boot upper',(.18,.15,.13),.55),
        'rubber':material('Draft | sole',(.065,.065,.06),.74),
        'thread':material('Draft | seam thread',(.32,.30,.26),.78),
        'metal':material('Draft | eyelets',(.11,.11,.10),.45,.5),
    }
    if 'pants' in args.parts: trousers(pants,mats,body_surface)
    if 'shirt' in args.parts: shirt(top,mats,body_surface)
    if 'boots' in args.parts: boots(footwear,mats,body_surface)
    bpy.context.view_layer.update()
    objects=list(root.all_objects)
    bind(objects,body,rig)
    bpy.context.view_layer.update()
    diagnostics=[]
    for obj in objects:
        raw=[obj.matrix_world @ v.co for v in obj.data.vertices]
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        points=[evaluated.matrix_world @ v.co for v in mesh.vertices]
        evaluated.to_mesh_clear()
        diagnostics.append({'name':obj.name,'raw_z':[min(p.z for p in raw),max(p.z for p in raw)],
            'evaluated_z':[min(p.z for p in points),max(p.z for p in points)],'scale':list(obj.matrix_world.to_scale())})
    (out/'fit_diagnostics.json').write_text(json.dumps(diagnostics,indent=2),encoding='utf-8')
    wardrobe_controls(root,{'shirt':top,'trousers':pants,'boots':footwear},body,rig)
    bpy.data.objects['M02_Simple_Reference_Shorts'].hide_render=True
    bpy.data.objects['M02_Simple_Reference_Shorts'].hide_set(True)
    scene=render_setup(args.samples)
    for col,description in [(top,'Original crew-neck short sleeve T-shirt fitting M02'),
                            (pants,'Original work trousers fitting M02'),
                            (footwear,'Original constructed boots fitting M02')]:
        if col.objects:
            col.asset_mark()
            col.asset_data.description=description
    activate(body)
    filename=out/('M02_Custom_Clothes_'+args.version.rsplit('_',1)[-1]+'.blend')
    bpy.ops.file.pack_all()
    if not args.no_save: bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False)
    report={'file':str(filename),'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'authorship':'All garment and footwear geometry is original RING construction, not fitted clothing-pack meshes.',
        'parts':[{'name':o.name,'vertices':len(o.data.vertices),'faces':len(o.data.polygons)} for o in objects if o.type=='MESH']}
    (out/'clothes_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('M02_ORIGINAL_CLOTHES_BUILT '+json.dumps({'file':str(filename),'parts':len(objects)}),flush=True)
    for view in args.render.split(','):
        if not view: continue
        scene.camera=bpy.data.objects['Custom_Clothes_'+view]
        scene.render.filepath=str(out/(view.lower()+'.png'))
        bpy.ops.render.render(write_still=True)
        print('M02_CLOTHES_RENDER '+view,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default='custom_clothes_v09')
    parser.add_argument('--parts',default='shirt,pants,boots')
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--render',default='ThreeQuarter,Front')
    parser.add_argument('--no-save',action='store_true')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    args=parser.parse_args(argv)
    args.parts=args.parts.split(',')
    build(args)
