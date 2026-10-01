"""Контроль геометрии и драйверов визуальной демонстрации после нового открытия."""
from pathlib import Path
import json,math,sys,hashlib
import bpy,bmesh
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_vss_motion_v5 as M
import refine_vss_geometry_v4 as V
import build_vss_blender as B
from check_vss_geometry_v4 import evaluated,no_maps


def mesh_positions(obj):
    deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    pts=[ev.matrix_world@v.co for v in mesh.vertices];ev.to_mesh_clear();return pts


def pose(safety,pull):
    c=bpy.data.objects['VSS_Controls'];c['safety_up']=safety;c['bolt_pull']=pull
    c.update_tag();bpy.context.view_layer.update()


def manual_check():
    controls=bpy.data.objects['VSS_Controls'];controls.animation_data.action=None
    carrier=bpy.data.objects['Bolt_carrier'];selector=bpy.data.objects['Selector']
    lever=bpy.data.objects['Safety_lever_contoured'];hook=bpy.data.objects['Charging_handle_hook']
    samples=json.loads((M.RAW/'contact-samples.json').read_text(encoding='utf8'));results=[]
    start_cover=mesh_positions(bpy.data.objects['Bolt_carrier_visible_cover']);start_hook=mesh_positions(hook)
    static_trees={name:M.tree(bpy.data.objects[name]) for name in
                  ('Rounded_dust_cover','Receiver_lower_frame','Cover_pressed_rib_401','Cover_pressed_rib_365')}
    for safety in (0,.125,.25,.375,.5,.625,.75,.875,1):
        position=safety*40;i=min(39,int(position));t=position-i
        expected=(samples[i]['allowed_mm']*(1-t)+samples[i+1]['allowed_mm']*t)*.001
        for pull in (0,.25,.5,.75,1):
            pose(safety,pull)
            move=-min(pull*M.FULL,expected)
            ev=carrier.evaluated_get(bpy.context.evaluated_depsgraph_get())
            assert abs(ev.matrix_world.translation.x-move)<1e-7,('Driver motion',safety,pull,ev.matrix_world.translation.x,move)
            angle=selector.evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler.y
            assert abs(angle+M.RAISE*safety)<1e-7,('Safety pivot',safety,angle)
            for name,baseline in (('Bolt_carrier_visible_cover',start_cover),('Charging_handle_hook',start_hook)):
                points=mesh_positions(bpy.data.objects[name]);assert len(points)==len(baseline)
                error=max((p-q-Vector((move,0,0))).length for p,q in zip(points,baseline))
                assert error<1e-7,('Moving owner',name,error)
            intersections=M.tree(lever).overlap(M.tree(hook))
            assert not intersections,('Lever/handle overlap',safety,pull,len(intersections))
            for name in ('Bolt_carrier_visible_cover','Charging_handle_hook','Carrier_cover_pin'):
                moving=M.tree(bpy.data.objects[name])
                for static_name,static in static_trees.items():
                    assert not moving.overlap(static),('Moving/static overlap',safety,pull,name,static_name)
            results.append({'safety':safety,'pull':pull,'actual_travel_mm':-move*1000,'allowed_travel_mm':expected*1000})
    # Приподнятый рычаг физически пересекает следующий шаг рукоятки;
    # это проверка реальной геометрии, а не только значения контрола.
    pose(1,1)
    controls['bolt_pull']=1;carrier.driver_remove('location',0)
    carrier.location.x=-(samples[-1]['allowed_mm']*.001+.0007);bpy.context.view_layer.update()
    beyond=M.tree(lever).overlap(M.tree(hook))
    assert beyond,'Raised stop has no actual handle contact'
    return results,{'probe_extra_travel_mm':.7,'overlapping_face_pairs':len(beyond)}


def check_library():
    copy=json.loads((M.RAW/'library-copy-report.json').read_text(encoding='utf8'))
    assert copy['status']=='PASS';destination=Path(copy['destination']);rows=[]
    for row in copy['files']:
        if not row['path'].endswith('.blend'):continue
        file=destination/row['path']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256']
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert not bpy.data.libraries
        external=[]
        for image in bpy.data.images:
            if image.source=='FILE' and not image.packed_file:external.append(image.filepath)
        for font in bpy.data.fonts:
            if font.filepath not in {'','<builtin>'} and not font.packed_file:external.append(font.filepath)
        assert not external,(file,external)
        controls=bpy.data.objects['VSS_Controls']
        carrier=bpy.data.objects['Bolt_carrier'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        safety=controls['safety_up'];pull=controls['bolt_pull']
        assert bpy.data.objects['Charging_handle_hook'].parent.name=='Charging_handle'
        assert bpy.data.objects['Charging_handle'].parent.name=='Bolt_carrier'
        assert bpy.data.objects['Safety_axis_pin'].parent.name=='VSS_Vintorez_Picatinny'
        assert controls.animation_data.action.name=='VSS_Demo'
        assert not M.tree(bpy.data.objects['Safety_lever_contoured']).overlap(M.tree(bpy.data.objects['Charging_handle_hook']))
        rows.append({'path':row['path'],'sha256':row['sha256'],'external_dependencies':external,
                     'saved_frame':bpy.context.scene.frame_current,'safety':safety,'pull':pull,
                     'actual_travel_mm':-carrier.location.x*1000})
    assert len(rows)==4
    report={'status':'PASS','saved_copies_reopened':len(rows),'files':rows}
    (M.RAW/'library-blend-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V5_LIBRARY_REOPEN_PASS',flush=True)


def main():
    report_path=M.RAW/'motion-audit.json';report_path.write_text('{"status":"RUNNING"}',encoding='utf8')
    bpy.ops.wm.open_mainfile(filepath=str(M.FILE));V.sync()
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];no_maps(root)
    topology={}
    for name in ('Rounded_dust_cover','Receiver_lower_frame','Cover_pressed_rib_401',
                 'Bolt_carrier_visible_cover','Charging_handle_hook','Safety_lever_contoured',
                 'Ejection_cavity_inner_wall'):
        _,counts,_,_=evaluated(bpy.data.objects[name]);assert not any(counts.values()),(name,counts)
        topology[name]=counts
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update();bounds=B.report_bounds('VSS_Assembly')
    port=[]
    static=[M.tree(bpy.data.objects[name]) for name in ('Rounded_dust_cover','Receiver_lower_frame','Cover_pressed_rib_401')]
    for x,z in ((.352,.0145),(.368,.0175),(.383,.0175),(.409,.027),(.426,.029),(.454,.023),(.47,.021)):
        for tree in static:
            assert tree.ray_cast(Vector((x,-.035,z)),Vector((0,1,0)),.019)[0] is None,('Closed port',x,z)
        port.append([x,z])
    poses,contact=manual_check()
    bpy.ops.wm.open_mainfile(filepath=str(M.FILE));V.sync()
    timeline=[]
    for frame in (1,20,35,45,65,88,95,120,135,145,155,180):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        carrier=bpy.data.objects['Bolt_carrier'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        ctrl=bpy.data.objects['VSS_Controls'];pull=ctrl['bolt_pull'];safety=ctrl['safety_up']
        if frame==20:assert 0<pull<1,('Bolt animation does not interpolate',pull)
        if frame==88:assert 0<safety<1,('Safety animation does not interpolate',safety)
        assert not M.tree(bpy.data.objects['Safety_lever_contoured']).overlap(M.tree(bpy.data.objects['Charging_handle_hook']))
        timeline.append({'frame':frame,'safety':safety,'requested_pull':pull,'actual_travel_mm':-carrier.location.x*1000})
    for frame,suffix in ((1,'closed'),(45,'full_travel'),(145,'safety_stop')):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        B.render_views(M.RAW,'v5',[(suffix,'Camera_V5_Side',1500,850),
            (suffix+'_angle','Camera_V5_Stop',1300,850)])
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    B.render_views(M.RAW,'v5',[('hook','Camera_V5_Hook',1250,950),('hook_top','Camera_V5_Top',1100,1000),
                             ('rifle','Camera_Beauty_Right',1800,850)])
    files=[]
    for file in (M.FILE,*(M.RAW/name for name in ('01_Closed.blend','02_Full_Travel.blend','03_Safety_Stop.blend'))):
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert len(bpy.data.objects['Charging_handle'].children)==1
        assert bpy.data.objects['Charging_handle'].parent.name=='Bolt_carrier'
        assert not bpy.data.libraries
        files.append({'name':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                      'saved_frame':bpy.context.scene.frame_current})
    report={'status':'PASS','closed_bounds':bounds,'topology':topology,'window_rays':port,
            'manual_poses':poses,'actual_contact_probe':contact,'timeline':timeline,
            'files_reopened':files,'new_textures':False,'game_exports':False,
            'motion_kind':'staged external Blender demonstration; stroke and shape estimated visually'}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V5_MOTION_AUDIT_PASS',flush=True)


if __name__=='__main__':
    if '--library' in sys.argv:check_library()
    else:main()
