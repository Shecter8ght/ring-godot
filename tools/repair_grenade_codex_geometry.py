"""Local casting/lever repair, neutral geometry review before new texturing."""
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'_asset_src/grenade_codex'
INPUT=OUT/'Grenade_MkII_visual_rig_geometry_v01.blend'
FILE=Path(os.environ.get('GRENADE_GEOMETRY_REVIEW_FILE',str(OUT/'Grenade_MkII_geometry_review_v04.blend')))
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'study'
spec=importlib.util.spec_from_file_location('grenade_studio',HERE/'grenade_codex_blender.py')
S=importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def source():
    bpy.context.preferences.use_preferences_save=False
    bpy.ops.wm.open_mainfile(filepath=str(INPUT))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def neutral():
    mat=bpy.data.materials.new('Neutral geometry — continuous metal review')
    mat.use_nodes=True
    p=mat.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(.26,.28,.30,1)
    p.inputs['Metallic'].default_value=.5
    p.inputs['Roughness'].default_value=.28
    for ob in bpy.context.scene.objects:
        if ob.type=='MESH':
            ob.data.materials.clear()
            ob.data.materials.append(mat)
    S.setup_studio((0,0,0))
    scene=bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y=1800,2000
    scene.cycles.samples=128
    scene.cycles.use_denoising=False


def study():
    source()
    rows=[]
    for name in ['FuzeBody','FuzeCollar','FuzeLug','LeverSidePlate','SafetyLever']:
        ob=bpy.data.objects[name]
        bm=bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
        bm.verts.ensure_lookup_table()
        remaining=set(bm.verts)
        components=[]
        while remaining:
            frontier=[remaining.pop()]
            component=[]
            while frontier:
                v=frontier.pop()
                component.append(v)
                for e in v.link_edges:
                    other=e.other_vert(v)
                    if other in remaining:
                        remaining.remove(other)
                        frontier.append(other)
            pts=[ob.matrix_world@v.co for v in component]
            components.append({'verts':len(pts),
                'min_mm':[min(p[i] for p in pts)*1000 for i in range(3)],
                'max_mm':[max(p[i] for p in pts)*1000 for i in range(3)]})
        row={'object':name,'welded_vertices':len(bm.verts),'components':components,
             'coordinates_mm':[[float(x)*1000 for x in v.co] for v in bm.verts],
             'faces':[[v.index for v in f.verts] for f in bm.faces]}
        rows.append(row)
        bm.free()
    (OUT/'checks/head_geometry_study.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    neutral()
    for name,cam,target,scale in [
        ('geometry_before_front',(.06,-.14,.16),(.003,0,.101),.050),
        ('geometry_before_side',(.15,-.018,.14),(.005,0,.103),.049),
        ('geometry_before_top',(.07,-.10,.25),(0,0,.103),.052)]:
        S.shot(name,(0,0,0),cam,target,scale)
    print('HEAD_GEOMETRY_STUDY_OK',flush=True)


def active(ob):
    for old in bpy.context.selected_objects:
        old.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active=ob


def weld(ob):
    bm=bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def mesh_audit(ob):
    bm=bmesh.new()
    bm.from_mesh(ob.data)
    row={'vertices':len(bm.verts),'faces':len(bm.faces),
         'boundary_edges':sum(e.is_boundary for e in bm.edges),
         'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
         'small_faces':sum(f.calc_area()<1e-14 for f in bm.faces)}
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    row['audit_copy_welded_boundary_edges']=sum(e.is_boundary for e in bm.edges)
    row['audit_copy_welded_nonmanifold_edges']=sum(not e.is_manifold for e in bm.edges)
    bm.free()
    return row


def continuous_cast_skin(ob):
    """Local high-poly casting skin rounds Boolean junctions into one surface."""
    active(ob)
    remesh=ob.modifiers.new('Cast junction skin — 0.12 mm resolution','REMESH')
    remesh.mode='VOXEL'
    remesh.voxel_size=.00012
    remesh.adaptivity=0
    remesh.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    smooth=ob.modifiers.new('Small cast junction radii','SMOOTH')
    smooth.factor=.62
    smooth.iterations=10
    bpy.ops.object.modifier_apply(modifier=smooth.name)
    sub=ob.modifiers.new('Continuous casting highlights','SUBSURF')
    sub.levels=1
    sub.render_levels=1
    # Retain editable subdivision; evaluated skin is equally smooth but the
    # review source keeps a practical base mesh for the later UV/paint stage.
    for p in ob.data.polygons:
        p.use_smooth=True


def lever_mesh(ob,body):
    """Closed swept sheet with a continuous bend, replacing folded sliver faces."""
    # Measured old lower centre profile retained; top bend is rebuilt cleanly.
    controls=[(-8.9,109.5),(-10.5,109.45),(-11.6,110.0),(-11.9,111.1),
              (-11.0,112.25),(-9.4,112.85),(7.0,112.85),(11.3,112.65),
              (14.4,110.7),(16.55,107.25),(17.7,103.5),(18.1,94.0),
              (18.2,85.0),(20.3,76.0),
              (23.8,66.0),(30.2,58.0),(32.7,49.0),(33.0,40.0),
              (31.5,30.0),(28.9,21.0),(25.7,13.0),(23.3,8.1)]
    # Cardinal Hermite spline, clamped ends; ordered cross sections never overlap.
    controls=[Vector(p) for p in controls]
    points=[]
    for i in range(len(controls)-1):
        a,b=controls[i],controls[i+1]
        prev=controls[max(0,i-1)]
        after=controls[min(len(controls)-1,i+2)]
        ta=(b-prev)*.34
        tb=(after-a)*.34
        for step in range(10):
            t=step/10
            point=(2*t**3-3*t**2+1)*a+(t**3-2*t**2+t)*ta+(-2*t**3+3*t**2)*b+(t**3-t**2)*tb
            points.append(point)
    points.append(controls[-1])
    # Keep the sheet outside the body: the earlier imported profile crossed
    # the shoulder, showing circular/triangular body fragments through it.
    body_profile=[(v.co.z*1000,math.hypot(v.co.x,v.co.y)*1000)
                  for v in body.data.vertices]
    required=[]
    for p in points:
        radii=[r for z,r in body_profile if abs(z-p.y)<1.0]
        required.append(max(0,max(radii,default=0)+1.0-p.x)
                        if p.y<85 else 0)
    for i,p in enumerate(points):
        # A smooth envelope spreads local shoulder clearance along the bend.
        shift=max((need*math.exp(-((p.y-q.y)/5.0)**2)
                   for q,need in zip(points,required)),default=0)
        if p.y<85:
            p.x+=shift
    vertices=[]
    section_count=16
    # Rounded sheet: .85 mm thick, wider head cover tapering to the lower lever.
    thickness=.85
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        normal=Vector((-tangent.y,tangent.x))
        width=10.4+11.6*max(0,min(1,(p.y-8.1)/100))
        # Explicit radiused corners; no bevel modifier can produce folded spikes.
        radius=.10
        for cy,cn,start in [(width/2-radius,thickness/2-radius,0),
                            (-width/2+radius,thickness/2-radius,90),
                            (-width/2+radius,-thickness/2+radius,180),
                            (width/2-radius,-thickness/2+radius,270)]:
            for k in range(4):
                angle=math.radians(start+k*30)
                y=cy+radius*math.cos(angle)
                n=cn+radius*math.sin(angle)
                xz=p+normal*n
                vertices.append((xz.x/1000,y/1000,xz.y/1000))
    faces=[]
    faces.append(tuple(reversed(range(section_count))))
    for i in range(len(points)-1):
        for j in range(section_count):
            k=(j+1)%section_count
            faces.append((i*section_count+j,i*section_count+k,
                          (i+1)*section_count+k,(i+1)*section_count+j))
    faces.append(tuple((len(points)-1)*section_count+j for j in range(section_count)))
    mesh=bpy.data.meshes.new('SafetyLever — continuous radiused pressed sheet')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    ob.data=mesh
    weld(ob)
    for p in mesh.polygons:
        p.use_smooth=True
    if hasattr(mesh,'set_sharp_from_angle'):
        mesh.set_sharp_from_angle(angle=math.radians(50))
    # The original rig uses an inverse parent matrix while meshes remain at origin.
    bpy.context.view_layer.update()


def body_lever_clearance():
    """Check the closed lower sheet against the evaluated body surface."""
    dg=bpy.context.evaluated_depsgraph_get()
    body=bpy.data.objects['GrenadeBody'].evaluated_get(dg)
    lever=bpy.data.objects['SafetyLever'].evaluated_get(dg)
    def tree(ob):
        me=ob.to_mesh()
        result=BVHTree.FromPolygons([ob.matrix_world@v.co for v in me.vertices],
                                   [list(p.vertices) for p in me.polygons])
        ob.to_mesh_clear()
        return result
    overlaps=tree(body).overlap(tree(lever))
    assert not overlaps,('Body/lever triangle intersections',len(overlaps))
    return {'body_lever_intersecting_face_pairs':len(overlaps)}


def mesh_object(name,vertices,faces):
    mesh=bpy.data.meshes.new(name+' mesh')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    ob=bpy.data.objects.new(name,mesh)
    bpy.context.scene.collection.objects.link(ob)
    weld(ob)
    return ob


def lathe(name,profile,segments=160):
    vertices=[]
    for z,r in profile:
        for i in range(segments):
            phi=i*math.tau/segments
            vertices.append((r*math.cos(phi),r*math.sin(phi),z))
    faces=[tuple(reversed(range(segments)))]
    for row in range(len(profile)-1):
        for i in range(segments):
            nxt=(i+1)%segments
            faces.append((row*segments+i,row*segments+nxt,(row+1)*segments+nxt,(row+1)*segments+i))
    faces.append(tuple((len(profile)-1)*segments+i for i in range(segments)))
    return mesh_object(name,vertices,faces)


def contour(name,points,half_width):
    n=len(points)
    vertices=[(x,side*half_width,z) for side in [-1,1] for x,z in points]
    faces=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]
    for i in range(n):
        nxt=(i+1)%n
        faces.append((i,nxt,n+nxt,n+i))
    return mesh_object(name,vertices,faces)


def union(head,part,operation='UNION'):
    active(head)
    boolean=head.modifiers.new('External casting '+operation,'BOOLEAN')
    boolean.operation=operation
    boolean.solver='EXACT'
    boolean.object=part
    bpy.ops.object.modifier_apply(modifier=boolean.name)
    bpy.data.objects.remove(part,do_unlink=True)
    weld(head)


def new_casting(root):
    # Exterior proportions traced from the owner's latest front/rear examples.
    head=lathe('FuzeCasting',[(.0857,.0112),(.0859,.01155),(.0867,.01155),
          (.08715,.01055),(.1095,.01040),(.1111,.01050),(.1119,.01060)])
    head.parent=root
    wing=contour('Cast side contour',[(-.004,.1107),(.0121,.1107),
                 (.0146,.1050),(.0168,.0891),(.0160,.0870),(-.004,.0870)],.0097)
    union(head,wing)
    lug=contour('Cast front alignment rib',[(-.00165,.089),(.00165,.089),
                  (.00165,.0948),(-.00165,.0948)],.00145)
    for v in lug.data.vertices:
        v.co.y-=.0103
    union(head,lug)
    # Visible exterior clearance for the existing animated pin; no inner mechanism.
    hole=lathe('Visual pin opening',[(-.015,.00112),(.015,.00112)],96)
    for v in hole.data.vertices:
        x,y,z=v.co
        v.co=(x+.0115,-z,y+.1021)
    union(head,hole,'DIFFERENCE')
    continuous_cast_skin(head)
    return head


def wire_ring(ob,eyelet=False):
    vertices=[]
    faces=[]
    sections=240 if not eyelet else 96
    cross=24
    for i in range(sections+1):
        t=i/sections
        phi=(math.radians(45)+t*(math.tau+.08)) if not eyelet else t*math.tau
        if eyelet:
            centre=Vector((.0115,-.0124,.1021))
            radial=Vector((0,math.cos(phi),math.sin(phi)))
            normal=Vector((1,0,0))
            point=centre+radial*.00165
            radius=.00045
        else:
            radial=Vector((math.cos(phi),0,math.sin(phi)))
            normal=Vector((0,1,0))
            roll=max(0,min(1,(t-.79)/.21))
            drift=.0022*roll*roll*(3-2*roll)
            point=Vector((.0188,-.0124+drift,.0889))+radial*.0151
            radius=.0010
        for j in range(cross):
            angle=j*math.tau/cross
            v=point+radius*(radial*math.cos(angle)+normal*math.sin(angle))
            vertices.append(tuple(v))
    for i in range(sections):
        for j in range(cross):
            k=(j+1)%cross
            faces.append((i*cross+j,i*cross+k,(i+1)*cross+k,(i+1)*cross+j))
    if not eyelet:
        faces.append(tuple(reversed(range(cross))))
        faces.append(tuple(sections*cross+j for j in range(cross)))
    mesh=bpy.data.meshes.new(ob.name+' — rounded wire with visible ends')
    # Unlike the main body, the original ring/eyelet keep nonzero origins and
    # rotations. Convert authored world positions to their retained local space.
    inverse=ob.matrix_world.inverted()
    mesh.from_pydata([tuple(inverse@Vector(v)) for v in vertices],[],faces)
    mesh.update()
    ob.data=mesh
    weld(ob)
    for p in mesh.polygons:
        p.use_smooth=len(p.vertices)==4


def neck_relief(body):
    moved=0
    maximum=0
    for v in body.data.vertices:
        z=v.co.z
        if not .067<z<.0846:
            continue
        rise=max(0,min(1,(z-.067)/.006))
        fall=max(0,min(1,(.0846-z)/.003))
        envelope=rise*rise*(3-2*rise)*fall*fall*(3-2*fall)
        phi=math.atan2(v.co.y,v.co.x)
        # Eight continuous casting flutes aligned to the existing eight columns.
        groove=math.exp(-(math.sin(4*phi)/.30)**2)
        delta=-.00072*envelope*groove
        r=math.hypot(v.co.x,v.co.y)
        v.co.x*=1+delta/r
        v.co.y*=1+delta/r
        moved+=1
        maximum=max(maximum,abs(delta))
    body.data.update()
    return {'moved_vertices':moved,'max_neck_relief_mm':maximum*1000,
            'region_z_mm':[67,84.6],'lower_body_unchanged':True}


def build():
    source()
    body=bpy.data.objects['GrenadeBody']
    # Record the original body numerically; Blender meshes in this step are unpainted.
    import struct
    original_body=hashlib.sha256(b''.join(struct.pack('<3f',*v.co) for v in body.data.vertices)).hexdigest()
    root=bpy.data.objects['CTRL_Grenade']
    for name in ['FuzeBody','FuzeCollar','FuzeLug','LeverSidePlate']:
        bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    head=new_casting(root)
    head['geometry_revision']='v04: continuous reference-shaped exterior casting'
    for name in ['FuzeRivet_L1','FuzeRivet_R1','FuzeRivet_L2','FuzeRivet_R2','FuzeRivet_L3','FuzeRivet_R3']:
        bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    neck=neck_relief(body)
    lever=bpy.data.objects['SafetyLever']
    lever_mesh(lever,body)
    lever['geometry_revision']='v04: continuous pressed sheet; original taper and lower silhouette retained approximately'
    # Corrected larger split wire ring, attached through the retained pin assembly.
    for name in ['PullRing','PinEyelet']:
        ob=bpy.data.objects[name]
        wire_ring(ob,name=='PinEyelet')
    revised_body=hashlib.sha256(b''.join(struct.pack('<3f',*v.co) for v in body.data.vertices)).hexdigest()
    neutral()
    scene=bpy.context.scene
    scene.camera.location=(.17,-.28,.18)
    S.aim(scene.camera,(0,0,.057))
    scene.camera.data.ortho_scale=.167
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1
    scene.unit_settings.length_unit='MILLIMETERS'
    active(head)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                sp=area.spaces.active
                sp.region_3d.view_location=(0,0,.080)
                sp.region_3d.view_distance=.16
                sp.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
                sp.clip_start=.001
                sp.shading.type='MATERIAL'
                sp.overlay.show_floor=False
                sp.overlay.show_axis_x=False
                sp.overlay.show_axis_y=False
    notes=bpy.data.texts.new('00_GEOMETRY_REVIEW_V04')
    notes.write('Geometry repair v04; awaiting owner review before revised texturing.\n'
                'Casting contour, folded hook and split ring follow the latest owner examples.\n'
                'Eight casting flutes added only on the upper neck; lower body preserved.\n'
                'Next texture marking: sun icon and Cyrillic СЛНШК in dark ink.\n'
                'CTRL_Grenade sliders/action retained.\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    # Explicit fresh-file review, not a render of the unsaved build session.
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    report={'candidate':str(FILE),'source':str(INPUT),'original_body_vertices_sha256':original_body,
            'body_vertices_sha256':revised_body,'neck_revision':neck,
            'meshes':{},'poses':[],'stage':'geometry_candidate_pending_owner_review',
            'closed_clearance':body_lever_clearance()}
    for ob in bpy.context.scene.objects:
        if ob.type=='MESH':
            row=mesh_audit(ob)
            evaluated=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            row['evaluated_vertices']=len(evaluated.data.vertices)
            row['evaluated_faces']=len(evaluated.data.polygons)
            report['meshes'][ob.name]=row
            if ob.name!='GrenadeBody':
                assert row['audit_copy_welded_boundary_edges']==0 and row['audit_copy_welded_nonmanifold_edges']==0,(ob.name,row)
    for frame in [1,17,30,45,59,75,96]:
        scene=bpy.context.scene
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        report['poses'].append({'frame':frame,
             'pin_offset_mm':bpy.data.objects['CTRL_PinAssembly'].location.y*1000,
             'lever_angle_degrees':math.degrees(bpy.data.objects['CTRL_LeverPose'].rotation_euler.y),
             'casting_matrix':list(map(list,bpy.data.objects['FuzeCasting'].matrix_world))})
    (OUT/'checks/geometry_review_v04.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    scene.frame_set(1)
    for name,cam,target,scale,frame in [
        ('geometry_v04_overall',(.17,-.28,.18),(0,0,.057),.167,1),
        ('geometry_v04_front',(.06,-.14,.16),(.003,0,.101),.050,1),
        ('geometry_v04_side',(.15,-.018,.14),(.005,0,.103),.049,1),
        ('geometry_v04_top',(.07,-.10,.25),(0,0,.103),.052,1),
        ('geometry_v04_reverse',(-.08,.14,.15),(0,0,.100),.052,1),
        ('geometry_v04_pin_separate',(.17,-.28,.18),(0,-.009,.061),.173,30),
        ('geometry_v04_lever_outward',(.20,-.30,.19),(.025,-.009,.074),.16,59)]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        S.shot(name,(0,0,0),cam,target,scale)
    print('GEOMETRY_REVIEW_V04_OK',str(FILE),flush=True)


def audit():
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    scene=bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    reference=json.loads((OUT/'checks/geometry_review_v04.json').read_text(encoding='utf8'))
    import struct
    body=bpy.data.objects['GrenadeBody']
    digest=hashlib.sha256(b''.join(struct.pack('<3f',*v.co) for v in body.data.vertices)).hexdigest()
    assert digest==reference['body_vertices_sha256']
    points=[]
    for ob in scene.objects:
        if ob.type=='MESH':
            ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            points.extend(ev.matrix_world@Vector(p) for p in ev.bound_box)
    dimensions=[(max(p[i] for p in points)-min(p[i] for p in points))*1000 for i in range(3)]
    images=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        assert im.packed_file,im.name
        images.append({'name':im.name,'packed':True})
    for frame in [1,17,30,45,59,75,96]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        root=bpy.data.objects['CTRL_Grenade']
        assert abs(bpy.data.objects['CTRL_PinAssembly'].location.y+.052*root['pin_pull'])<1e-6,frame
        if root['pin_pull']<.65:
            assert abs(bpy.data.objects['CTRL_LeverPose'].rotation_euler.y)<1e-5,frame
        assert abs(bpy.data.objects['FuzeCasting'].matrix_world.translation.length)<1e-7,frame
    report={'candidate':str(FILE),'sha256':hashlib.sha256(FILE.read_bytes()).hexdigest(),
            'pass':True,'body_matches_review_candidate':True,'closed_dimensions_mm':dimensions,
            'packed_images':images,'verified_pose_frames':[1,17,30,45,59,75,96]}
    scene.frame_set(1)
    bpy.context.view_layer.update()
    report['closed_clearance']=body_lever_clearance()
    path=Path(os.environ.get('GRENADE_GEOMETRY_AUDIT_REPORT',str(OUT/'checks/geometry_delivery_audit_v04.json')))
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('GEOMETRY_DELIVERY_AUDIT_OK',dimensions,flush=True)


if __name__=='__main__':
    {'study':study,'build':build,'audit':audit}[MODE]()
