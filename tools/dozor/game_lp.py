"""Separate LP from accepted HP: structured lathe reduction before UV packing.

Never saves the accepted scene. Tiny button dots are baked with their parent button.
"""
import sys,math,json,pathlib
import bpy,bmesh,numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
sys.path.insert(0,str(ROOT/'tools'))
from asset_kit import uv as U
bpy.context.preferences.use_preferences_save=False
assert json.loads((ASSET/'finish-spec.json').read_text(encoding='utf-8'))['wear']['accepted']
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
sc=bpy.context.scene;dg=bpy.context.evaluated_depsgraph_get()
coll=bpy.data.collections.new('DOZOR_GAME_DERIVATIVE');sc.collection.children.link(coll)
sets={'F1':[],'P':[]};records={};generic=[]

def lathe_copy(src):
    me=src.data
    for n in (192,128,96,64):
        if len(me.vertices)%n or len(me.vertices)<n*3 or len(me.polygons)!=len(me.vertices):continue
        if set(me.polygons[0].vertices)!=set([0,1,n,n+1]):continue
        if any(len(f.vertices)!=4 for f in me.polygons):continue
        p=np.array([tuple(v.co) for v in me.vertices],np.float64).reshape(-1,n,3)
        target=32 if any(s in src.name for s in ('.Head.','.Tail.fluted','.Bezel.three','.parabolic_reflector')) else 16
        step=max(1,n//target)
        if '.Body.ribbed_grip' in src.name:
            # Retain the eight axial valleys; the 0.755 mm rings become normals.
            prof=[(43,12.7),(44,12.7),(45,12.45),(46,12.70),(112.9,12.70),
                  (113,12.6),(114,12.7),(118.5,12.7),(119,12.4),(119,11.25),(43,11.25)]
            nn=32;arr=[]
            for z,r in prof:
                for i in range(nn):
                    t=i*math.tau/nn
                    rr=r-.85*max(0,math.cos(8*t))**10 if 45<=z<=113 and r>12 else r
                    arr.append((rr*.001*math.cos(t),rr*.001*math.sin(t),z*.001))
            p=np.array(arr).reshape(-1,nn,3)
        else:
            p=p[:,::step,:]
            if '.parabolic_reflector' in src.name:
                keep=sorted(set(list(range(0,33,8))+[32]+list(range(33,66,8))+[65]))
                p=p[keep]
        m,nn=p.shape[:2]
        faces=[(j*nn+i,j*nn+(i+1)%nn,((j+1)%m)*nn+(i+1)%nn,((j+1)%m)*nn+i) for j in range(m) for i in range(nn)]
        new=bpy.data.meshes.new('LP lathe '+src.name);new.from_pydata(p.reshape(-1,3).tolist(),[],faces);new.update()
        # Unwrap the profile in coherent strips; planar end faces use planar UV.
        uv=new.uv_layers.new(name='GameUV')
        rr=np.linalg.norm(p[:,:,:2],axis=2).mean(1);zz=p[:,:,2].mean(1)
        dr=np.roll(rr,-1)-rr;dz=np.roll(zz,-1)-zz;ds=np.hypot(dr,dz)
        slope=np.arctan2(dr,dz);group=0;distance=0.;last=None
        for j in range(m):
            angle=abs((slope[j]-slope[j-1]+math.pi)%(2*math.pi)-math.pi)
            if j==0 or angle>math.radians(55):group+=1;distance=0.
            planar=abs(dz[j])<1e-7
            c=math.tau*(rr[j]+rr[(j+1)%m])*.5
            for i in range(nn):
                face=new.polygons[j*nn+i]
                coords=[(i/nn*c,distance),((i+1)/nn*c,distance),((i+1)/nn*c,distance+ds[j]),(i/nn*c,distance+ds[j])]
                for li,vi,co in zip(face.loop_indices,face.vertices,coords):
                    uv.data[li].uv=(p.reshape(-1,3)[vi,0]+group*.3,p.reshape(-1,3)[vi,1]) if planar else (co[0]+group*.3,co[1])
            distance+=ds[j]
        return new
    return None

def cylinder_copy(src):
    me=src.data
    # Closed primitive cylinder with two n-gon caps; all coordinates already in source local axes.
    n=len(me.vertices)//2
    if n<8 or len(me.vertices)!=2*n or len(me.polygons)!=n+2:return None
    if sorted(len(f.vertices) for f in me.polygons)!=[4]*n+[n,n]:return None
    if n<=8:step=1
    else:step=max(1,n//16)
    p=np.array([tuple(v.co) for v in me.vertices]).reshape(2,n,3)[:,::step]
    radii=np.linalg.norm(p[0]-p[0].mean(0),axis=1)
    if np.ptp(radii)>max(radii.mean()*.001,1e-7):return None # an extruded prism is not a cylinder
    n=p.shape[1];flat=p.reshape(-1,3)
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    new=bpy.data.meshes.new('LP cylinder '+src.name);new.from_pydata(flat.tolist(),[],faces);new.update()
    uv=new.uv_layers.new(name='GameUV');center=p[0].mean(0)
    axis=p[1].mean(0)-center;depth=np.linalg.norm(axis);axis/=depth
    e=(p[0,0]-center);radius=np.linalg.norm(e);e/=radius;f=np.cross(axis,e)
    for poly in new.polygons:
        for j,(li,vi) in enumerate(zip(poly.loop_indices,poly.vertices)):
            if poly.index<2:
                q=flat[vi]-center;uv.data[li].uv=(float(q@e)+poly.index*.1,float(q@f))
            else:
                i=poly.index-2
                uv.data[li].uv=(.3+([i,i+1,i+1,i][j]/n)*math.tau*radius,[0,0,depth,depth][j])
    return new

def arc_copy(src):
    # Preserve the mounting bore analytically: collapse must not pull its inner
    # chord through the 25.4 mm tube. Liners need 32 samples per half-circle.
    if not src.name.startswith(('P.Ring.','P.Liner.')):return None
    me=src.data;n=len(me.vertices)//4-1
    if n<32 or len(me.vertices)!=4*(n+1):return None
    count=32 if '.Liner.' in src.name else 24
    p=np.array([tuple(v.co) for v in me.vertices]).reshape(4,n+1,3)[:,np.linspace(0,n,count+1).astype(int)]
    k=count+1
    faces=[(j*k+i,j*k+i+1,((j+1)%4)*k+i+1,((j+1)%4)*k+i) for j in range(4) for i in range(count)]
    faces +=[(0,k,2*k,3*k),(count,3*k+count,2*k+count,k+count)]
    new=bpy.data.meshes.new('LP bore '+src.name);new.from_pydata(p.reshape(-1,3).tolist(),[],faces);new.update();return new

for src in sorted(list(bpy.data.objects),key=lambda o:o.name):
    if src.type!='MESH' or not src.name.startswith(('F1.','P.')):continue
    if any(s in src.name for s in ('.Button.dot','.Button.mode_bar','.Body.transition_band','.Tail.fine_ring','.Clamp.pad_rib')):continue
    key='F1' if src.name.startswith('F1.') else 'P'
    if role(src.name)=='Lens':continue # explicit thin optical shell in export, no opaque atlas
    arc=arc_copy(src)
    me=lathe_copy(src) if arc is None else arc
    if me is None:me=cylinder_copy(src)
    if src.name in ('F1.Optics.LED_ceramic','F1.Optics.LED_die'):
        me=src.data.copy() # tiny hidden cuboids: their bevels are in the normal atlas
    if src.name in ('P.Clamp.fixed_jaw','P.Clamp.moving_jaw'):
        me=src.data.copy() # preserve dovetail profile, unwrap its hard corners as a prism
    structured=me is not None and arc is None
    if me is None:
        me=bpy.data.meshes.new_from_object(src.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
    ob=bpy.data.objects.new('LP__'+src.name,me);coll.objects.link(ob);ob.matrix_world=src.matrix_world.copy()
    select([ob])
    if structured and me.uv_layers.get('GameUV') is None:generic.append(ob)
    if not structured:
        count=sum(len(f.vertices)-2 for f in me.polygons)
        limit=90 if '.lanyard_wing' in src.name else 90 if '.Clip.' in src.name else 96 if 'Button.' in src.name else 20 if '.tip_' in src.name else 200 if '.Ring.' in src.name else 96 if '.Liner.' in src.name else 80 if 'socket_head' in src.name else 90 if '_jaw' in src.name else 64
        if count>limit and arc is None:
            mod=ob.modifiers.new('Game surface reduction','DECIMATE');mod.ratio=limit/count
            bpy.ops.object.modifier_apply(modifier=mod.name)
        generic.append(ob)
    sources=[src.name]
    if '.Button.primary' in src.name:sources +=[o.name for o in bpy.data.objects if o.name.startswith('F1.Button.dot')]
    if '.Button.secondary' in src.name:sources +=[o.name for o in bpy.data.objects if o.name.startswith('F1.Button.mode_bar')]
    if '.Body.ribbed_grip' in src.name:sources +=[o.name for o in bpy.data.objects if o.name.startswith('F1.Body.transition_band')]
    if '.Tail.fluted' in src.name:sources +=[o.name for o in bpy.data.objects if o.name.startswith('F1.Tail.fine_ring')]
    if '.Clamp.press_pad' in src.name:
        sy=sum(v.co.y for v in src.data.vertices)
        sources +=[o.name for o in bpy.data.objects if o.name.startswith('P.Clamp.pad_rib') and sum(v.co.y for v in o.data.vertices)*sy>0]
    # Exact per-piece budgets are applied before final UV layout, not after baking.
    cap=600 if '.Body.ribbed_grip' in src.name else 400 if '.Head.' in src.name or '.Tail.fluted' in src.name else 352 if '.Neck.' in src.name else 340 if '.parabolic_reflector' in src.name else 180 if '.Bezel.three' in src.name else 112 if '.lens_gasket' in src.name else 48 if '.emitter_centering' in src.name else 128 if '.Clip.retaining' in src.name else None
    count=sum(len(f.vertices)-2 for f in ob.data.polygons)
    if cap and count>cap:
        mod=ob.modifiers.new('Owner 5000 triangle budget','DECIMATE');mod.ratio=cap/count
        bpy.ops.object.modifier_apply(modifier=mod.name)
    me=ob.data
    me.materials.clear();m=bpy.data.materials.new('GAME_TARGET '+ob.name);m.use_nodes=True;me.materials.append(m)
    # Bake/export use explicit world coordinates, preserving the exact source alignment.
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(ob.data);bm.free()
    me=ob.data
    for face in me.polygons:face.use_smooth=True
    partrole=role(src.name)
    if '.Clamp.press_pad' in src.name:partrole='ClampPadNegative' if sy<0 else 'ClampPadPositive'
    records[ob.name]={'sources':sources,'atlas':key,'role':partrole,'structured_lathe':structured,
                     'cage_mm':.9 if '.Tail.fluted' in src.name or '.Bezel.' in src.name else .65,'ray_mm':2.0}
    sets[key].append(ob)
if generic:U.smart_unwrap(generic,uv='GameUV')
uvreports={}
for key,objs in sets.items():
    print('PACK',key,len(objs),flush=True)
    classes=[]
    for ob in objs:
        cls=np.zeros(len(ob.data.polygons),np.int32)
        src=bpy.data.objects[records[ob.name]['sources'][0]]
        if key=='F1' and any(n in src.name for n in ('.Body.','.Head.','.Neck.','.Tail.fluted')):
            inv=src.matrix_world.inverted()
            for face in ob.data.polygons:
                c=inv@face.center;n=inv.to_3x3()@face.normal
                r=math.hypot(c.x,c.y)
                if r>1e-6 and (n.x*c.x+n.y*c.y)/r<-.2:cls[face.index]=U.ROOMY
        classes.append(cls)
    best=None;bestuv=None
    for score,order in [('bl','area'),('top','area'),('waste','area'),('bl','side')]:
        rep=U.layout(objs,SIZES[key],uv='GameUV',classes=classes,stack=False,margin=12,group_margin=6,
                     score=score,order=order,precision=.006,log=lambda *a:print(*a,flush=True))
        if best is None or rep['fill']>best['fill']:
            best=rep;bestuv=[[tuple(v.uv) for v in ob.data.uv_layers['GameUV'].data] for ob in objs]
    for ob,coords in zip(objs,bestuv):
        for v,co in zip(ob.data.uv_layers['GameUV'].data,coords):v.uv=co
    uvreports[key]=best
    U.harden_on_seams(objs,uv='GameUV')
    verify=U.verify(objs,SIZES[key],uv='GameUV',margin=12,group_margin=6)
    print('UV_VERIFY',key,verify,flush=True)
    uvreports[key]['verify']=verify
    for ob in objs:
        for layer in list(ob.data.uv_layers):
            if layer.name!='GameUV':ob.data.uv_layers.remove(layer)
        ob.data.uv_layers.active_index=0;ob.data.uv_layers[0].active_render=True
        select([ob]);mod=ob.modifiers.new('Stable game triangles','TRIANGULATE');mod.quad_method='FIXED'
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # Triangulating a non-planar quad can introduce another steep edge.
        # Enforce the Godot normal rule on the final triangles as well.
        bm=bmesh.new();bm.from_mesh(ob.data)
        for e in bm.edges:
            if e.is_manifold and e.calc_face_angle()>math.radians(60):e.smooth=False;e.seam=True
        bm.to_mesh(ob.data);bm.free()
        ob.data.calc_loop_triangles();records[ob.name]['triangles']=len(ob.data.loop_triangles)
for ob in list(bpy.data.objects):
    if ob.name not in records:bpy.data.objects.remove(ob,do_unlink=True)
record={'source':str(SOURCE),'atlas_size':SIZES,'parts':records,'uv':uvreports,
        'roles':'first-person handheld, close item/constructor, world item; no new hand animation',
        'budget_basis':'Existing 2K attachment pipeline; RTX 5070 Ti development hardware; geometry reduced by projected feature size',
        'states':['working100'],'lod':'Godot automatic mesh LOD, individual movers retained',
        'triangle_limit_complete_assembly':TRIANGLE_LIMIT}
assert sum(r['triangles'] for r in records.values())<=TRIANGLE_LIMIT-128,'Reserve 128 triangles for the optical lens'
(WORK/'parts.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,default=lambda o:o.tolist() if hasattr(o,'tolist') else str(o)),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'dozor_lp.blend'))
print('LP READY',sum(r['triangles'] for r in records.values()),flush=True)
