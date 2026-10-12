"""Round split pin and an editable visual compression pose on geometry v04."""
import hashlib
import importlib.util
import json
import math
import os
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'_asset_src/grenade_codex'
INPUT=OUT/'Grenade_MkII_geometry_review_v04.blend'
FILE=Path(os.environ.get('GRENADE_GEOMETRY_REVIEW_FILE',str(OUT/'Grenade_MkII_geometry_review_v05.blend')))
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build'
spec=importlib.util.spec_from_file_location('grenade_geometry_v04',HERE/'repair_grenade_codex_geometry.py')
G=importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


def shape_digest(ob):
    me=ob.data
    return hashlib.sha256(b''.join(struct.pack('<3f',*v.co) for v in me.vertices)+
        b''.join(struct.pack('<I',i) for p in me.polygons for i in p.vertices)).hexdigest()


def spline(controls,steps=7):
    controls=[Vector(p) for p in controls]
    points=[]
    for i in range(len(controls)-1):
        a,b=controls[i:i+2]
        prev=controls[max(0,i-1)]
        after=controls[min(len(controls)-1,i+2)]
        ta=(b-prev)*.33
        tb=(after-a)*.33
        for j in range(steps):
            t=j/steps
            points.append((2*t**3-3*t**2+1)*a+(t**3-2*t**2+t)*ta+
                          (-2*t**3+3*t**2)*b+(t**3-t**2)*tb)
    points.append(controls[-1])
    return points


def pin_path(compression):
    # Exterior wire only. Two splayed ends, a rounded front return, no inner parts.
    leg=[(1.45,14.5),(1.40,13.9),(1.18,12.6),(.78,11.25),(.44,10.0),
         (.35,9.3),(.35,6.0),(.35,-6.0),(.42,-9.5),(.80,-10.7),(1.2,-11.6)]
    controls=[(-x,y) for x,y in leg]
    controls.extend((1.2*math.cos(math.pi*(1-i/16)),-11.6-1.2*math.sin(math.pi*(1-i/16)))
                    for i in range(1,17))
    controls.extend((x,y-.5 if y>12.5 else y) for x,y in reversed(leg[:-1]))
    points=spline(controls)
    for p in points:
        t=max(0,min(1,(p.y-9.3)/3.0))
        t=t*t*(3-2*t)
        p.x=math.copysign(.35+(abs(p.x)-.35)*(1-compression*t),p.x)
    return [Vector((.0115+p.x/1000,p.y/1000,.1021)) for p in points]


def wire_vertices(compression):
    points=pin_path(compression)
    verts=[]
    cross=20
    for i,p in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        normal=Vector((0,0,1))
        lateral=tangent.cross(normal).normalized()
        for j in range(cross):
            phi=j*math.tau/cross
            verts.append(p+.00033*(normal*math.cos(phi)+lateral*math.sin(phi)))
    return verts,points


def replace_pin():
    ob=bpy.data.objects['SafetyPin']
    inverse=ob.matrix_world.inverted()
    vertices,points=wire_vertices(0)
    compressed,_=wire_vertices(1)
    cross=20
    faces=[tuple(reversed(range(cross)))]
    for i in range(len(points)-1):
        for j in range(cross):
            k=(j+1)%cross
            faces.append((i*cross+j,i*cross+k,(i+1)*cross+k,(i+1)*cross+j))
    faces.append(tuple((len(points)-1)*cross+j for j in range(cross)))
    mesh=bpy.data.meshes.new('SafetyPin — continuous round split wire')
    mesh.from_pydata([inverse@v for v in vertices],[],faces)
    mesh.update()
    # Keep material, object transform and parent from the displayed v04.
    for mat in ob.data.materials:
        mesh.materials.append(mat)
    ob.data=mesh
    bm=bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth=len(p.vertices)==4
    ob.shape_key_add(name='Basis')
    shape=ob.shape_key_add(name='SplitTips_Compress')
    for point,vertex in zip(shape.data,compressed):
        point.co=inverse@vertex
    fc=shape.driver_add('value')
    fc.driver.expression='min(1,max(0,p/0.16))*min(1,max(0,(0.74-p)/0.14))'
    var=fc.driver.variables.new()
    var.name='p'
    var.type='SINGLE_PROP'
    var.targets[0].id=bpy.data.objects['CTRL_Grenade']
    var.targets[0].data_path='["pin_pull"]'
    ctrl=bpy.data.objects['CTRL_PinAssembly']
    for driver in ctrl.animation_data.drivers:
        if driver.data_path=='location' and driver.array_index==1:
            driver.driver.expression='-0.0006*min(1,p/0.16)-0.0514*max(0,(p-0.16)/0.84)'
    ob['geometry_revision']='v05: round wire, two splayed tips, driven compression'
    ob['visual_compression']='ends approach before sliding; relax once clear'
    return {'cross_sections':len(points),'vertices':len(vertices),
            'splayed_tip_centres_mm':[list(points[0]*1000),list(points[-1]*1000)],
            'compressed_tip_centres_mm':[list(pin_path(1)[0]*1000),list(pin_path(1)[-1]*1000)]}


def visible_opening():
    head=bpy.data.objects['FuzeCasting']
    # Widen the existing opening and form a shallow rounded mouth on both sides.
    # This is a real void in the mesh; the wire and its material cannot hide it.
    for mod in list(head.modifiers):
        if mod.type=='SUBSURF':
            head.modifiers.remove(mod)
    profile=[(-.016,.0013),(-.0102,.0013),(-.0099,.0015),(-.0097,.0017),
             (-.00935,.00145),(-.0089,.0013),(.0089,.0013),
             (.00935,.00145),(.0097,.0017),(.0099,.0015),(.0102,.0013),(.016,.0013)]
    cutter=G.lathe('Visible pin passage with rounded mouths',profile,128)
    for v in cutter.data.vertices:
        x,y,z=v.co
        # A proper rotation keeps outward winding; swapping Y/Z reflected the
        # cutter and silently left the earlier supposed opening closed.
        v.co=(x+.0115,-z,y+.1021)
    G.union(head,cutter,'DIFFERENCE')
    G.continuous_cast_skin(head)
    head['geometry_revision']='v05: continuous casting with visible through-opening and rounded rims'


def opening_audit():
    ob=bpy.data.objects['FuzeCasting'].evaluated_get(bpy.context.evaluated_depsgraph_get())
    me=ob.to_mesh()
    tree=BVHTree.FromPolygons([ob.matrix_world@v.co for v in me.vertices],
                             [list(p.vertices) for p in me.polygons])
    ob.to_mesh_clear()
    rows=[]
    for label,dx,dz,clear in [('centre',0,0,True),('left leg',-.00035,0,True),
                             ('right leg',.00035,0,True),('above',0,.0006,True),
                             ('solid rim',.0022,0,False)]:
        hit=tree.ray_cast(Vector((.0115+dx,.03,.1021+dz)),Vector((0,-1,0)),.06)[0]
        assert (hit is None)==clear,(label,hit)
        rows.append({'probe':label,'clear_through_head':hit is None})
    return {'real_through_opening':True,'probes':rows}


def object_tree(name):
    ob=bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())
    me=ob.to_mesh()
    tree=BVHTree.FromPolygons([ob.matrix_world@v.co for v in me.vertices],
                             [list(p.vertices) for p in me.polygons])
    ob.to_mesh_clear()
    return tree


def enable_gpu():
    pref=bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type='OPTIX'
    pref.get_devices()
    for dev in pref.devices:
        dev.use=dev.type=='OPTIX'
    bpy.context.scene.cycles.device='GPU'


def pose_info(frame):
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    root=bpy.data.objects['CTRL_Grenade']
    p=float(root['pin_pull'])
    shape=bpy.data.objects['SafetyPin'].data.shape_keys.key_blocks['SplitTips_Compress']
    c=float(shape.value)
    expected_c=min(1,max(0,p/.16))*min(1,max(0,(.74-p)/.14))
    expected_y=-.0006*min(1,p/.16)-.0514*max(0,(p-.16)/.84)
    assert abs(c-expected_c)<1e-5,(frame,c,expected_c)
    assert abs(bpy.data.objects['CTRL_PinAssembly'].location.y-expected_y)<1e-6,frame
    if p<.16:
        assert abs(bpy.data.objects['CTRL_PinAssembly'].location.y)<=.00061
    # Verify evaluated wire, not just the visible custom-property value.
    ev=bpy.data.objects['SafetyPin'].evaluated_get(bpy.context.evaluated_depsgraph_get())
    me=ev.to_mesh()
    left=sum((ev.matrix_world@v.co for v in me.vertices[:20]),Vector())/20
    right=sum((ev.matrix_world@v.co for v in me.vertices[-20:]),Vector())/20
    ev.to_mesh_clear()
    assert abs(left.y-(.0145+expected_y))<1e-6,('Left tip world movement',frame)
    assert abs(right.y-(.0140+expected_y))<1e-6,('Right tip world movement',frame)
    assert abs(abs(left.x-right.x)-(.0029-.0022*c))<1e-6,('Actual tip compression',frame)
    matrix=bpy.data.objects['FuzeCasting'].matrix_world
    assert max(abs(matrix[r][col]-(1 if r==col else 0))
               for r in range(4) for col in range(4))<1e-6,('Casting moved',frame)
    return {'frame':frame,'pin_pull':p,'compression':c,
            'pin_offset_mm':expected_y*1000,'tip_centres_world_mm':[list(left*1000),list(right*1000)],
            'tip_span_x_mm':abs(left.x-right.x)*1000,
            'lever_angle_degrees':math.degrees(bpy.data.objects['CTRL_LeverPose'].rotation_euler.y)}


def build():
    bpy.context.preferences.use_preferences_save=False
    bpy.ops.wm.open_mainfile(filepath=str(INPUT))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    preserved={ob.name:shape_digest(ob) for ob in bpy.context.scene.objects
               if ob.type=='MESH' and ob.name not in {'SafetyPin','FuzeCasting'}}
    pin=replace_pin()
    visible_opening()
    bpy.context.view_layer.update()
    root=bpy.data.objects['CTRL_Grenade']
    root.id_properties_ui('pin_pull').update(description='Visual pose: tips close first, wire slides, tips relax outside')
    old_notes=bpy.data.texts.get('00_GEOMETRY_REVIEW_V04')
    if old_notes:
        old_notes.name='ARCHIVE_GEOMETRY_REVIEW_V04'
    notes=bpy.data.texts.new('00_GEOMETRY_REVIEW_V05_SPLIT_PIN')
    notes.write('v05: two round split tips. Shape key SplitTips_Compress is driven by pin_pull.\n'
                'The early part of pin_pull compresses the ends before translation.\n'
                'Ends relax outside. Other v04 geometry is unchanged. Awaiting owner review.\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    for name,sha in preserved.items():
        assert shape_digest(bpy.data.objects[name])==sha,name
    audit=G.mesh_audit(bpy.data.objects['SafetyPin'])
    assert audit['boundary_edges']==0 and audit['nonmanifold_edges']==0,audit
    head_audit=G.mesh_audit(bpy.data.objects['FuzeCasting'])
    assert head_audit['boundary_edges']==0 and head_audit['nonmanifold_edges']==0,head_audit
    report={'candidate':str(FILE),'source':str(INPUT),'preserved_mesh_sha256':preserved,
            'pin':pin,'pin_topology':audit,'stage':'awaiting_geometry_approval',
            'head_topology':head_audit,'opening':opening_audit(),
            'poses':[pose_info(f) for f in [1,10,11,12,13,14,17,20,25,30,45,59,75,90,96]]}
    (OUT/'checks/geometry_review_v05.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    scene=bpy.context.scene
    scene.frame_set(1)
    enable_gpu()
    for name,cam,target,scale,frame in [
        ('geometry_v05_overall',(.17,-.28,.18),(0,0,.057),.167,1),
        ('geometry_v05_front',(.06,-.14,.16),(.003,0,.101),.050,1),
        ('geometry_v05_side',(.15,-.018,.14),(.005,0,.103),.049,1),
        ('geometry_v05_top',(.07,-.10,.25),(0,0,.103),.052,1),
        ('geometry_v05_reverse',(-.08,.14,.15),(0,0,.100),.052,1),
        ('geometry_v05_pin_separate',(.17,-.28,.18),(0,-.009,.061),.173,30),
        ('geometry_v05_lever_outward',(.20,-.30,.19),(.025,-.009,.074),.16,59),
        ('geometry_v05_split_tips',(.065,.10,.134),(.0115,.0108,.1021),.023,1),
        ('geometry_v05_tips_compressed',(.065,.10,.134),(.0115,.0108,.1021),.023,13),
        ('geometry_v05_pin_outside',(.05,-.12,.16),(.0115,-.057,.1021),.047,30)]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        G.S.shot(name,(0,0,0),cam,target,scale)
    print('GEOMETRY_REVIEW_V05_OK',FILE,flush=True)


def audit():
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    scene=bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    reference=json.loads((OUT/'checks/geometry_review_v05.json').read_text(encoding='utf8'))
    for name,sha in reference['preserved_mesh_sha256'].items():
        assert shape_digest(bpy.data.objects[name])==sha,name
    points=[]
    for ob in scene.objects:
        if ob.type=='MESH':
            ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
            points.extend(ev.matrix_world@Vector(p) for p in ev.bound_box)
    dims=[(max(p[i] for p in points)-min(p[i] for p in points))*1000 for i in range(3)]
    head_tree=object_tree('FuzeCasting')
    poses=[]
    for frame in range(1,97):
        row=pose_info(frame)
        overlaps=head_tree.overlap(object_tree('SafetyPin'))
        assert not overlaps,('Pin/head intersection',frame,len(overlaps))
        row['pin_head_intersecting_face_pairs']=len(overlaps)
        poses.append(row)
    assert min(r['tip_span_x_mm'] for r in poses)<.71
    assert poses[0]['tip_span_x_mm']>2.8 and poses[29]['tip_span_x_mm']>2.8
    images=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        assert im.packed_file,im.name
        images.append({'name':im.name,'packed':True})
    scene.frame_set(1)
    bpy.context.view_layer.update()
    report={'candidate':str(FILE),'sha256':hashlib.sha256(FILE.read_bytes()).hexdigest(),
            'pass':True,'v04_other_five_meshes_unchanged':True,'closed_dimensions_mm':dims,
            'closed_clearance':G.body_lever_clearance(),'packed_images':images,
            'pin_topology':G.mesh_audit(bpy.data.objects['SafetyPin']),
            'opening':opening_audit(),
            'verified_pose_frames':list(range(1,97)),'poses':poses}
    path=Path(os.environ.get('GRENADE_GEOMETRY_AUDIT_REPORT',str(OUT/'checks/geometry_delivery_audit_v05.json')))
    path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('GEOMETRY_DELIVERY_V05_AUDIT_OK',dims,flush=True)


def motion():
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    enable_gpu()
    scene=bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y=900,1080
    scene.cycles.samples=32
    scene.cycles.use_denoising=False
    folder=OUT/'previews/pin_split_motion_v05'
    folder.mkdir(parents=True,exist_ok=True)
    for frame in range(1,31):
        pose_info(frame)
        scene.camera.location=(.085,.17,.145)
        G.S.aim(scene.camera,(.0115,.003,.1021))
        scene.camera.data.ortho_scale=.070
        scene.render.filepath=str(folder/f'{frame:03}.png')
        bpy.ops.render.render(write_still=True)
    print('PIN_SPLIT_MOTION_RENDER_OK',flush=True)


def finalize():
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    old=bpy.data.texts.get('00_GEOMETRY_REVIEW_V04')
    if old:
        old.name='ARCHIVE_GEOMETRY_REVIEW_V04'
    note=bpy.data.texts.get('01_GEOMETRY_REVIEW_V05_SPLIT_PIN')
    if note:
        note.name='00_GEOMETRY_REVIEW_V05_SPLIT_PIN'
    for frame,label in [(11,'Начало тяги — кончики сходятся'),
                        (14,'Кончики прижаты — чека выходит'),(25,'Чека снаружи — концы раздельны')]:
        bpy.context.scene.timeline_markers.new(label,frame=frame)
    G.active(bpy.data.objects['SafetyPin'])
    camera=bpy.context.scene.camera
    old_rotation=camera.rotation_euler.copy()
    old_location=camera.location.copy()
    camera.location=(.065,.10,.134)
    G.S.aim(camera,(.0115,.0108,.1021))
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                sp=area.spaces.active
                sp.region_3d.view_location=(.0115,.008,.1021)
                sp.region_3d.view_distance=.065
                sp.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
    camera.location=old_location
    camera.rotation_euler=old_rotation
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE))
    print('GEOMETRY_V05_LAYOUT_FINALIZED',flush=True)


if __name__=='__main__':
    {'build':build,'audit':audit,'motion':motion,'finalize':finalize}[MODE]()
