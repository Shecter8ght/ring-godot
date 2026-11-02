"""Editable high-poly shape candidate. Blender 5.2; units metres, dimensions below mm.

Manufacturer photographs are private shape references only. No production UV, textures,
game meshes, export, or changes to FPS arms. Run using -- --out <asset-library-folder>.
"""
import argparse
import json
import math
import pathlib
import shutil
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

MM = .001
ROOT = pathlib.Path(__file__).resolve().parents[2]
args = argparse.ArgumentParser()
args.add_argument('--out', required=True)
args.add_argument('--render', action='store_true')
opt = args.parse_args(sys.argv[sys.argv.index('--')+1:])
OUT = pathlib.Path(opt.out)
for folder in ('models', 'references', 'renders', 'checks'):
    (OUT / folder).mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 1
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.cycles.use_denoising = True
scene.render.threads_mode = 'FIXED'
scene.render.threads = 12
try:
    pref = bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type = 'OPTIX'
    pref.get_devices()
    for d in pref.devices:
        d.use = d.type != 'CPU'
    if any(d.use for d in pref.devices):
        scene.cycles.device = 'GPU'
except Exception as exc:
    print('GPU fallback:', exc, flush=True)
scene.render.resolution_x, scene.render.resolution_y = 1400, 800
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.world = bpy.data.worlds.new('Neutral inspection world')
scene.world.use_nodes = True
scene.world.node_tree.nodes.get('Background').inputs['Color'].default_value = (.42, .45, .50, 1)
scene.world.node_tree.nodes.get('Background').inputs['Strength'].default_value = .45

def mat(name, color, metallic=0, rough=.38, transmission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    n = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value = (*color, 1)
    n.inputs['Metallic'].default_value = metallic
    n.inputs['Roughness'].default_value = rough
    n.inputs['Transmission Weight'].default_value = transmission
    n.inputs['IOR'].default_value = 1.46
    return m

M = {
    'body': mat('DIAGNOSTIC • grey housing', (.24,.26,.29), .22, .32),
    'metal': mat('DIAGNOSTIC • edge metal', (.48,.50,.53), .6, .25),
    'rubber': mat('DIAGNOSTIC • rubber', (.085,.095,.11), 0, .63),
    'reflector': mat('DIAGNOSTIC • optical bowl', (.72,.74,.77), .93, .12),
    'glass': mat('DIAGNOSTIC • solid lens', (.92,.96,1), 0, .035, 1),
    'label': mat('DIAGNOSTIC • lettering', (.70,.72,.74), .1, .4),
    'led': mat('DIAGNOSTIC • emitter ceramic', (.46,.46,.46), .05, .4),
    'floor': mat('DIAGNOSTIC • backdrop', (.13,.15,.18), 0, .7),
}

def collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

def empty(name, c, loc=(0,0,0), parent=None):
    o = bpy.data.objects.new(name, None)
    c.objects.link(o)
    o.location = Vector(loc)*MM
    o.parent = parent
    o.empty_display_size = .008
    return o

def mesh(name, verts, faces, c, parent, material='body', smooth=True):
    me = bpy.data.meshes.new(name+' • editable')
    me.from_pydata([tuple(Vector(v)*MM) for v in verts], [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    o.parent = parent
    o.data.materials.append(M[material])
    for p in me.polygons:
        p.use_smooth = smooth
    # Keep designed corners crisp, smooth the dense curved surfaces.
    bm = bmesh.new()
    bm.from_mesh(me)
    for e in bm.edges:
        if e.is_manifold and e.calc_face_angle() > math.radians(38):
            e.smooth = False
    bm.to_mesh(me)
    bm.free()
    return o

def bevel(o, width=.18, segments=3):
    mod = o.modifiers.new('Edge radii • mm', 'BEVEL')
    mod.width = width*MM
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(28)
    mod.harden_normals = True
    wn = o.modifiers.new('Planar face normals', 'WEIGHTED_NORMAL')
    wn.keep_sharp = True
    wn.weight = 40
    return o

def lathe(name, profile, c, parent, material='body', n=128, fn=None):
    """Closed revolution of a closed cross section; profile has (axial z, radius)."""
    vs = []
    for j,(z,r) in enumerate(profile):
        for i in range(n):
            t = i*math.tau/n
            rr, zz = (fn(j,z,r,t) if fn else (r,z))
            vs.append((rr*math.cos(t), rr*math.sin(t), zz))
    faces = []
    for j in range(len(profile)):
        k = (j+1)%len(profile)
        for i in range(n):
            q = (i+1)%n
            faces.append((j*n+i,j*n+q,k*n+q,k*n+i))
    return mesh(name,vs,faces,c,parent,material)

def box(name, center, dims, c, parent, material='body', radius=.2):
    x,y,z = center
    a,b,d = [v/2 for v in dims]
    vs=[(x+sx*a,y+sy*b,z+sz*d) for sx,sy,sz in
        [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]]
    fs=[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]
    o=mesh(name,vs,fs,c,parent,material,False)
    if radius:
        bevel(o,min(radius,min(dims)*.18))
    return o

def cyl(name, center, radius, depth, c, parent, material='body', axis='Z', n=64):
    vs=[]
    for h in (-depth/2,depth/2):
        for i in range(n):
            t=i*math.tau/n
            p=Vector((radius*math.cos(t),radius*math.sin(t),h))
            if axis=='X':p=Vector((p.z,p.x,p.y))
            if axis=='Y':p=Vector((p.y,p.z,p.x))
            vs.append(tuple(p+Vector(center)))
    fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    fs += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return bevel(mesh(name,vs,fs,c,parent,material),min(.08,depth*.16,radius*.18),3)

def sphere(name, center, radius, c, parent, material='metal'):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius*MM, location=Vector(center)*MM)
    o=bpy.context.object
    o.name=name
    for old in list(o.users_collection):old.objects.unlink(o)
    c.objects.link(o)
    o.parent=parent
    o.data.materials.append(M[material])
    for p in o.data.polygons:p.use_smooth=True
    return o

def cut(o, tool):
    bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Machined opening','BOOLEAN')
    mod.operation='DIFFERENCE'
    mod.solver='EXACT'
    mod.object=tool
    bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_move_up(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool,do_unlink=True)

def ribbon(name, points, width, thickness, c, parent, material='metal'):
    # Rounded rectangular section swept explicitly: no bevel slivers on tight bends.
    section=[]
    rad=min(.12,thickness*.22)
    for cy,cn,start in [(width/2-rad,thickness/2-rad,0),(-width/2+rad,thickness/2-rad,math.pi/2),
                        (-width/2+rad,-thickness/2+rad,math.pi),(width/2-rad,-thickness/2+rad,3*math.pi/2)]:
        for k in range(5):
            a=start+k*math.pi/8
            section.append((cy+rad*math.cos(a),cn+rad*math.sin(a)))
    vs=[]
    for i,p in enumerate(points):
        before=Vector(points[max(0,i-1)]);after=Vector(points[min(len(points)-1,i+1)])
        tangent=(after-before).normalized()
        normal=Vector((-tangent.z,0,tangent.x))
        for y,n in section:
            vs.append(tuple(Vector(p)+Vector((0,y,0))+normal*n))
    count=len(section)
    fs=[tuple(reversed(range(count)))]
    for i in range(len(points)-1):
        for j in range(count):fs.append((i*count+j,i*count+(j+1)%count,(i+1)*count+(j+1)%count,(i+1)*count+j))
    fs.append(tuple((len(points)-1)*count+j for j in range(count)))
    return mesh(name,vs,fs,c,parent,material)

FONT=bpy.data.fonts.load('C:/Windows/Fonts/arialbd.ttf')
def text(name, body, loc, size, c, parent, rot=(0,0,0)):
    cu=bpy.data.curves.new(name,'FONT')
    cu.body=body;cu.size=size*MM;cu.font=FONT
    cu.align_x='CENTER';cu.align_y='CENTER'
    cu.extrude=.006*MM
    ob=bpy.data.objects.new(name,cu);c.objects.link(ob);ob.parent=parent
    ob.location=Vector(loc)*MM;ob.rotation_euler=rot
    cu.materials.append(M['label'])
    return ob

def build_flashlight():
    c=collection('01 • ДОЗОР Ф-1 • master shape')
    root=empty('DOZOR_F1_ROOT',c)
    root.rotation_euler.y=math.pi/2
    root.location.z=.035
    root['length_mm']=143.0;root['head_diameter_mm']=34.0;root['body_diameter_mm']=25.4
    root['prototype']='Fenix TK16 V2.0 — service reference only'
    root['stage']='SHAPE REVIEW — no production UV / textures'
    # Distinct shell, optical insert, solid lens, bezel; no black disks closing the mouth.
    def facets(j,z,r,t):
        if j < 7:
            flat=min(r,(r-.55)/math.cos((t+math.pi/6)%(math.pi/3)-math.pi/6))
            return flat,z
        return r,z
    lathe('F1.Head.hollow_faceted_housing',[(3.5,16.7),(4,17),(26.5,17),(29.5,16.6),
        (33.5,14.35),(35.5,13.85),(36.5,13.8),(36.5,11.75),(21,11.75),(4,14.25)],c,root,fn=facets)
    # Three scalloped crown tips and inward wall; frontmost point is z=0.
    def crown(j,z,r,t):
        if j in (0,1):z=1.35*(1-math.cos(3*t))
        return r,z
    bezel=lathe('F1.Bezel.three_lobe_crown',[(0,17),(0,14.1),(3.7,14.1),(3.7,17)],c,root,'metal',fn=crown)
    bevel(bezel,.12,3)
    for i in range(3):
        t=i*math.tau/3
        sphere('F1.Bezel.tip_%d'%i,(15.65*math.cos(t),15.65*math.sin(t),.55),.50,c,root)
    lathe('F1.Optics.lens_gasket',[(3.3,14.1),(3.3,13.5),(4.5,13.5),(4.5,14.1)],c,root,'rubber')
    cyl('F1.Optics.solid_glass_0.8mm',(0,0,4.05),13.52,.8,c,root,'glass',n=128)
    # Smooth parabolic reflector, backed by a second surface with genuine wall thickness.
    bowl=[]
    for i in range(33):
        r=2.65+(13.5-2.65)*i/32
        z=18.8-14*((r/13.5)**2-(2.65/13.5)**2)/(1-(2.65/13.5)**2)
        bowl.append((z,r))
    lathe('F1.Optics.parabolic_reflector',bowl+[(z+.40,r+.25) for z,r in reversed(bowl)],c,root,'reflector')
    lathe('F1.Optics.emitter_centering_ring',[(18.4,3.0),(18.4,2.15),(19.2,2.15),(19.2,3)],c,root,'led',n=64)
    box('F1.Optics.LED_ceramic',(0,0,19.0),(3.8,3.8,.6),c,root,'led',.15)
    box('F1.Optics.LED_die',(0,0,18.61),(2.1,2.1,.18),c,root,'metal',.08)
    neck=[(35.8,13.65),(37.0,13.65),(37.3,12.95),(38.1,12.95),(38.4,13.4),
          (40.0,13.4),(40.3,12.7),(42.9,12.7),(43.2,12.5),(43.2,11.5),(35.8,11.5)]
    lathe('F1.Neck.collar_and_relief_groove',neck,c,root)
    # Tube with real axial valleys and fine circumferential machining ribs.
    prof=[(43.0,12.7),(44,12.7),(45.0,12.45)]
    for i in range(88):
        z=46+i*.755
        prof.extend([(z,12.62),(z+.12,12.70),(z+.29,12.70),(z+.43,12.53)])
    prof.extend([(113.0,12.6),(114,12.7),(118.5,12.7),(119,12.4),(119,11.25),(43,11.25)])
    def grip(j,z,r,t):
        if j < len(prof)-2 and 45 <= z <= 113:
            groove=max(0,math.cos(8*t))**10
            return r-.85*groove,z
        return r,z
    lathe('F1.Body.ribbed_grip_hollow_tube',prof,c,root,n=192,fn=grip)
    for z in (44.3,114.6,117.3):
        lathe('F1.Body.transition_band_%s'%z,[(z,12.72),(z+.75,12.72),(z+.75,12.38),(z,12.38)],c,root)
    # Spring clip is independently removable; remove for ring installation.
    clipgroup=empty('F1.REMOVABLE_CLIP',c,parent=root)
    clipgroup['remove_for_ring_mount']=True
    ribbon('F1.Clip.spring_steel', [(-12.8,0,115.9),(-13.8,0,116.7),(-15.2,0,116.5),
        (-16.0,0,115.3),(-16,0,112),(-15.5,0,109),(-15.4,0,57),(-15.6,0,54),
        (-16.2,0,52),(-16.8,0,51),(-17.0,0,51.2)],3.8,.58,c,clipgroup)
    lathe('F1.Clip.retaining_band',[(114.1,12.95),(115.8,12.95),(115.8,12.72),(114.1,12.72)],c,clipgroup,'metal')
    # Independent tail cap with shallow longitudinal flutes and a closed switch plate.
    tailprof=[(119,12.7),(120,13.2),(122,13.45),(135.8,13.45),(137,13.0),
              (138.7,13),(138.7,0.6),(137.4,.6),(137.4,11.3),(119,11.3)]
    def tailflute(j,z,r,t):
        if j in (2,3):r-=.42*max(0,math.cos(16*t))**6
        return r,z
    tail=lathe('F1.Tail.fluted_cap',tailprof,c,root,fn=tailflute)
    bevel(tail,.15,3)
    for z in (120.4,122.1,135.6):
        lathe('F1.Tail.fine_ring_%s'%z,[(z,13.47),(z+.45,13.47),(z+.45,13.18),(z,13.18)],c,root)
    cyl('F1.Tail.recessed_switch_plate',(0,0,138.7),12.35,.7,c,root,'rubber',n=96)
    button=cyl('F1.Button.primary_rubber',(-3.9,0,140.9),5.7,4.2,c,root,'rubber')
    # Fine geometric grip dots on the rubber cap.
    for ix in range(-5,6):
        for iy in range(-5,6):
            x=ix*.77;y=iy*.77
            if x*x+y*y < 17.2:
                cyl('F1.Button.dot',(-3.9+x,y,143.02),.18,.10,c,root,'rubber',n=8)
    secondary=cyl('F1.Button.secondary_mode',(6.0,0,140.0),3.5,2.5,c,root,'rubber')
    secondary.scale.y=1.38
    # Distinguishing raised bars rather than another brand's symbol.
    for y in (-1.2,0,1.2):box('F1.Button.mode_bar',(6,y,141.31),(2.6,.35,.18),c,root,'body',.12)
    # Lanyard holes pass through the two protective wings.
    for sy in (-1,1):
        a=sy*math.pi/2
        wing=arc_ring('F1.Tail.lanyard_wing',a-.52,a+.52,c,root,'body',9.2,13,137.7,141.3)
        cutter=box('CUT.slot',(0,sy*11.0,139.4),(4.2,1.5,8.0),c,root,'body',.5)
        # Apply cutter bevel first to get a rounded slot with real walls.
        bpy.context.view_layer.objects.active=cutter
        for mod in list(cutter.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
        cut(wing,cutter)
    # A flat on the head faces the viewer; text is editable and uses fictional branding only.
    text('F1.Mark.DOZOR','ДОЗОР',(-16.52,0,17.5),2.8,c,root,rot=(0,-math.pi/2,0))
    text('F1.Mark.version','Ф-1',(-16.52,0,25),1.65,c,root,rot=(0,-math.pi/2,0))
    return c,root

def arc_ring(name, a0,a1,c,parent,material='body', inner=12.85,outer=16.0,z0=63,z1=98):
    n=96
    vs=[]
    for z,r in ((z0,inner),(z0,outer),(z1,outer),(z1,inner)):
        for i in range(n+1):
            t=a0+(a1-a0)*i/n
            vs.append((r*math.cos(t),r*math.sin(t),z))
    fs=[]; k=n+1
    for j in range(4):
        jj=(j+1)%4
        for i in range(n):fs.append((j*k+i,j*k+i+1,jj*k+i+1,jj*k+i))
    fs.extend([(0,k,2*k,3*k),(n,3*k+n,2*k+n,k+n)])
    return bevel(mesh(name,vs,fs,c,parent,material),min(.18,(outer-inner)*.18),3)

def prism(name, profile, z0,z1,c,parent,material='body'):
    # Profile points are local x,y; extrusion along flashlight axis.
    n=len(profile);vs=[(x,y,z) for z in (z0,z1) for x,y in profile]
    fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    fs += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return bevel(mesh(name,vs,fs,c,parent,material,False),.22,3)

def build_mount():
    c=collection('04 • ДОЗОР-П • independent Picatinny mount')
    root=empty('DOZOR_P_ROOT',c)
    root.rotation_euler.y=math.pi/2;root.location=(0,-.064,.035)
    root['interface']='Picatinny • matches existing project rail profile'
    root['bore_diameter_mm']=25.46;root['tube_diameter_mm']=25.4
    root['prototype']='ALG-00 type • interpreted visible geometry, not an exact mechanical replica'
    arc_ring('P.Ring.lower_cradle',-math.pi/2+.009,math.pi/2-.009,c,root)
    cap=empty('P.CAP_HINGE',c,(0,15.5,80.5),root)
    cap['hinge_axis']='local Z';cap['review_open_angle_deg']=-65
    upper=arc_ring('P.Ring.upper_cap',math.pi/2+.009,3*math.pi/2-.009,c,cap)
    # Preserve model coordinates, put the upper cap origin on its hinge.
    upper.location=Vector((0,-15.5,-80.5))*MM
    # Two protective liner halves have their own finite wall thickness.
    arc_ring('P.Liner.lower',-math.pi/2+.025,math.pi/2-.025,c,root,'rubber',12.73,12.85,64,97)
    liner=arc_ring('P.Liner.upper',math.pi/2+.025,3*math.pi/2-.025,c,cap,'rubber',12.73,12.85,64,97)
    liner.location=upper.location.copy()
    box('P.Saddle.bridge',(17.4,0,80.5),(7.8,24,35),c,root,'body',.6)
    # Dovetail jaw profile based on the project's standard Picatinny head.
    pos=[(20.8,8.0),(20.8,14.0),(28.3,14.0),(28.3,9.5),
         (26.65,8.45),(24.65,10.85),(23.85,10.85),(21.7,8.45)]
    prism('P.Clamp.fixed_jaw',pos,63,98,c,root)
    neg=[(x,-y) for x,y in reversed(pos)]
    prism('P.Clamp.moving_jaw',neg,64,97,c,root)
    # Rear and front hinge barrels; cap barrel follows the cap when opened.
    for z in (66,95):
        cyl('P.Hinge.fixed_knuckle',(0,15.5,z),2.05,6,c,root,'body')
    h=cyl('P.Hinge.cap_knuckle',(0,15.5,80.5),2.05,22,c,cap,'body')
    h.location=Vector((0,-15.5,-80.5))*MM
    cyl('P.Hinge.pin',(0,15.5,80.5),.8,35,c,root,'metal')
    # Captive closure screw (not a decorative dark hole).
    box('P.Lock.lower_lug',(1.8,-16.4,80.5),(4.0,7.6,12),c,root,'body',.5)
    lug=box('P.Lock.upper_lug',(-1.8,-16.4,80.5),(3.0,7.6,12),c,cap,'body',.5)
    lug.location=upper.location.copy()
    cyl('P.Lock.threaded_shank',(0,-17.5,80.5),1.55,9,c,root,'metal','X')
    screw=cyl('P.Lock.hex_socket_head',(-5.5,-17.5,80.5),3.1,2.2,c,root,'metal','X')
    socket=cyl('CUT.hex',(-6.4,-17.5,80.5),1.35,1.8,c,root,'metal','X',6)
    cut(screw,socket)
    # Two clamp paddles, a transverse pin, and a recoil key entering a rail slot.
    for sign in (-1,1):
        pad=box('P.Clamp.press_pad',(24.0,sign*18.3,80.5),(6,4.5,24),c,root,'body',.8)
        for i in range(7):
            box('P.Clamp.pad_rib',(24.0,sign*20.60,72.7+i*2.6),(4.7,.48,.65),c,root,'body',.13)
    cyl('P.Clamp.cross_pin',(23,0,80.5),1.8,41.5,c,root,'metal','Y')
    box('P.Clamp.recoil_key',(22.6,0,80.5),(2.2,16,4.8),c,root,'metal',.18)
    text('P.Mark','ДОЗОР-П',(-16.1,0,80.5),2.0,c,root,rot=(0,-math.pi/2,0))
    return c,root,cap

base,base_root=build_flashlight()
mount,mount_root,cap_root=build_mount()
# Remove sub-micron sliver edges left by bevel/Boolean at the captive screw socket.
# This targeted cleanup preserves the designed silhouette; other parts stay untouched.
for name in ('P.Lock.hex_socket_head',):
    ob=bpy.data.objects[name]
    bpy.context.view_layer.objects.active=ob
    for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
    bm=bmesh.new();bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.001*MM)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.0005*MM)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(ob.data);bm.free();ob.data.update()
variants=[]
for idx,suffix in enumerate(('М','С'),2):
    c=collection('%02d • ДОЗОР Ф-1%s • shared housing'%(idx,suffix))
    mapping={}
    for o in base.objects:
        cp=o.copy()
        if o.type=='FONT':cp.data=o.data.copy()
        c.objects.link(cp);mapping[o]=cp
        cp.name=o.name.replace('F1','F1'+('M' if suffix=='М' else 'S'))
    for old,cp in mapping.items():
        cp.parent=mapping.get(old.parent)
        if old.name=='F1.Mark.version':cp.data.body='Ф-1'+suffix
    r=mapping[base_root];r.name='DOZOR_F1'+('M' if suffix=='М' else 'S')+'_ROOT'
    r.location.y=.058*(idx-1)
    r['variant']='Power LED' if suffix=='М' else 'Strobe'
    variants.append(c)

studio=collection('90 • REVIEW studio • exclude from asset')
ground=box('Review.Ground',(.075*1000,.025*1000,-.75),(650,600,1.5),studio,None,'floor',0)
# A removable inspection coupon, using the existing project Picatinny cross section.
railprofile=[(21.9,-8.2),(21.9,8.2),(24,10.6),(24.5,10.6),
             (26.5,8.2),(29.5,8.2),(29.5,-8.2),(26.5,-8.2),(24.5,-10.6),(24,-10.6)]
rail=prism('Review.Picatinny_coupon',railprofile,48,113,studio,mount_root,'rubber')
for z in (50.47,60.48,70.49,80.5,90.51,100.52,110.53):
    tool=box('CUT.rail_slot',(22.9,0,z),(4.0,28,5.23),studio,mount_root,'body',0)
    cut(rail,tool)
bpy.context.view_layer.update()
from mathutils.bvhtree import BVHTree
def world_bvh(ob):
    ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    vertices=[ev.matrix_world @ v.co for v in me.vertices]
    polygons=[tuple(p.vertices) for p in me.polygons]
    tree=BVHTree.FromPolygons(vertices,polygons,all_triangles=False)
    ev.to_mesh_clear()
    return tree
rt=world_bvh(rail)
intersections={}
for ob in mount.objects:
    if ob.type=='MESH':
        pairs=rt.overlap(world_bvh(ob))
        if pairs:intersections[ob.name]=len(pairs)
fit={'status':'FAIL' if intersections else 'PASS','scope':'mount evaluated surfaces versus project Picatinny coupon',
     'surface_intersections':intersections,'rail_width_mm':21.2,'slot_width_mm':5.23,'slot_pitch_mm':10.01,
     'note':'Surface intersection test of this closed pose; not a claim of mechanical manufacturing tolerances.'}
(OUT/'checks'/'rail-fit.json').write_text(json.dumps(fit,ensure_ascii=False,indent=2),encoding='utf-8')
rail.hide_render=True;rail.hide_set(True)

def aim(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
for name,loc,power,size in [('Key',(-.08,-.13,.24),20,.16),('Fill',(.22,.12,.18),13,.12),('Rim',(.06,.18,.22),23,.1)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power/16;data.shape='DISK';data.size=size
    ob=bpy.data.objects.new('Review.'+name,data);studio.objects.link(ob);ob.location=loc;aim(ob,(.07,0,.02))
camdata=bpy.data.cameras.new('InspectionCamera');cam=bpy.data.objects.new('InspectionCamera',camdata);studio.objects.link(cam)
camdata.type='ORTHO';camdata.clip_start=.001;camdata.clip_end=10;scene.camera=cam

def set_view(name,loc,target,scale,visible,assembly=False,opened=False):
    for c in [base,*variants,mount]:c.hide_render=c.name not in visible
    mount_root.location.y=0 if assembly else -.064
    for o in base.objects:
        if o.name.startswith('F1.Clip.'):
            o.hide_render=assembly
    cap_root.rotation_euler.z=math.radians(-65) if opened else 0
    cam.location=Vector(loc)+Vector((0,0,.015));aim(cam,Vector(target)+Vector((0,0,.015)));camdata.ortho_scale=scale
    scene.render.filepath=str(OUT/'renders'/(name+'.png'))
    scene.render.resolution_x,scene.render.resolution_y=(1400,800)
    bpy.context.view_layer.update()
    print('RENDER',name,flush=True)
    bpy.ops.render.render(write_still=True)

# Metadata: no unsupported precision claims for unmeasured secondary details.
sources = '''# ДОЗОР — источники формы

Выбран владельцем: Fenix TK16 V2.0. Названия ДОЗОР Ф-1, Ф-1М, Ф-1С и ДОЗОР-П приняты 2026-11-02.
Фонарь: https://www.fenixlighting.com/products/fenix-tk16-v2-tactical-flashlight
Подтверждено производителем: 143 × 34 × 25,4 мм (длина / головка / корпус).
Крепление: https://fenixlight.com.au/product/fenix-alg-00-flashlight-ring/
ALG-00: 35 × 46 × 43 мм, кольцо для 22,5–26 мм. Использован как тип конструкции,
не как точная механическая копия; внутренний механизм пружинного зажима не реконструирован.
Профиль планки — существующий профиль проекта tools/build_adapters.py (21,2 мм, шаг 10,01, паз 5,23).
Фото side — боковые пропорции, разделение головки и трубки, клипса.
Фото front — гранёная головка, трёхлепестковый ободок, оптический отражатель.
Фото tail — две кнопки, накатка хвостовика, сквозные отверстия темляка.
Фото mount_0 — раскрывающееся кольцо, шарнир, прижимные лапки.
Мелкие фаски, внутренние стенки, скрытый крепёж и расположение LED — оценка по фото;
это редактируемый художественный ассет, не производственная модель.
Один общий корпус для трёх игровых вариантов, отличающихся маркировкой и будущей логикой света.
Фотографии производителя — только частные референсы, право переноса в текстуры не заявляется.
Все надписи ассета вымышленные; реальных логотипов нет.
'''
(OUT/'references'/'sources.md').write_text(sources,encoding='utf-8')
for path in (ROOT/'референсы'/'dozor').glob('*'):
    if path.is_file():shutil.copy2(path,OUT/'references'/path.name)

state='''# ДОЗОР — состояние ассета

2026-11-02. Стадия: геометрический кандидат v01, ожидает просмотра формы владельцем.
Прототип: Fenix TK16 V2.0; имя и линейка приняты, форма кандидата ещё не принята.
Файл: models/DOZOR_Family_form_v01.blend. Blender 5.2.2 LTS.
Ось фонарей: +X от переднего ободка к хвостовику; светит в -X; размер 1:1, метры.
Три самостоятельных root: DOZOR_F1_ROOT, DOZOR_F1M_ROOT, DOZOR_F1S_ROOT;
корпус общий (linked mesh), версия обозначается отдельным редактируемым текстом.
Крепёж DOZOR_P_ROOT, верхняя половина кольца P.CAP_HINGE: локальная Z, проверочный угол 65°.
Клипса — отдельная съёмная группа; в проверочном сборочном виде снята для установки кольца.
Все материалы диагностические, производственной UV, PBR, износа, low-poly и игрового экспорта нет.
Пистолет: L достаёт фонарь в левую руку. Длинноствольное: отдельный покупной крепёж Picatinny.
FPS-руки, их риг и клипы агент не менял. Код игры не менялся.
Неопределённости: точная поза рук; баланс трёх вариантов; мелкие скрытые детали прототипа.
Габариты мелких деталей оценены по фото; подтверждённые основные размеры — sources.md.
Следующий этап — просмотр кандидата владельцем. UV и текстурирование после принятия формы.
'''
(OUT/'asset-state.md').write_text(state,encoding='utf-8')

# Meaningful scope-specific audit. Optical barrel is not intended to be an empty through-hole.
top={'max_nonmanifold_edges':0,'max_overfull_edges':0,'max_wire_edges':0,'max_loose_vertices':0,
     'max_nonfinite_vertices':0,'max_zero_area_faces':0}
config={'schema_version':1,'description':'DOZOR form v01: bounds, closed shells, ring/slot passages',
 'targets':[
   {'id':'flashlight_shell_dimensions','objects':['F1.Head.hollow_faceted_housing','F1.Bezel.three_lobe_crown','F1.Body.ribbed_grip_hollow_tube','F1.Button.primary_rubber'],
    'dimensions_mm':{'expected':[143,34,34],'tolerance_mm':[.15,.15,.15]},'finite_transforms':True},
   {'id':'base_closed_meshes','collections':[base.name],'finite_transforms':True,'topology':{'evaluated':top}},
   {'id':'mount_closed_meshes','collections':[mount.name],'finite_transforms':True,'topology':{'evaluated':top}}],
 'passages':[
   {'id':'mount_bore_clearance','collections':[mount.name],'reference_object':mount_root.name,'unit':'mm',
    'samples':[{'start':[x,y,60],'end':[x,y,101]} for x,y in [(0,0),(12.6,0),(-12.6,0),(0,12.6),(0,-12.6),(8.7,8.7),(-8.7,-8.7)]], 'max_hits':0},
   {'id':'lanyard_slots','objects':['F1.Tail.lanyard_wing','F1.Tail.lanyard_wing.001'],'reference_object':base_root.name,'unit':'mm',
    'samples':[{'start':[x,y,135],'end':[x,y,145]} for y in [-11.0,11.0] for x in [-1.5,0,1.5]],'max_hits':0}]
}
(OUT/'checks'/'audit-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')

# Save with all variants visible in the editor, independent mount next to them.
for c in [base,*variants,mount]:c.hide_render=False
cam.location=(-.10,-.22,.22);aim(cam,(.07,.03,.018));camdata.ortho_scale=.27
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=.28
        area.spaces.active.region_3d.view_location=(.07,.02,.02)
        area.spaces.active.clip_start=.001
        area.spaces.active.shading.type='MATERIAL'
for o in bpy.context.selected_objects:o.select_set(False)
base_root.select_set(True);bpy.context.view_layer.objects.active=base_root
bpy.ops.file.pack_all()
path=OUT/'models'/'DOZOR_Family_form_v01.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
print('SAVED',path,flush=True)
if opt.render:
    set_view('01_flashlight_34',(-.055,-.17,.16),(.071,0,.02),.183,[base.name])
    set_view('02_side',(.071,-.24,.02),(.071,0,.02),.177,[base.name])
    set_view('03_optics',(-.050,-.07,.060),(.015,0,.020),.060,[base.name])
    set_view('04_tail',(.19,-.075,.09),(.132,0,.020),.054,[base.name])
    set_view('05_mount',(.018,-.145,.095),(.0805,-.064,.013),.078,[mount.name])
    set_view('06_assembly',(-.025,-.15,.13),(.073,0,.012),.182,[base.name,mount.name],assembly=True)
    set_view('07_ring_open',(.020,-.14,.10),(.0805,-.064,.016),.090,[mount.name],opened=True)
    set_view('08_family',(-.045,-.23,.25),(.070,.058,.019),.240,[base.name,*[c.name for c in variants]])
print('BUILD COMPLETE',flush=True)
