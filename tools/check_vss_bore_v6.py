"""Новый процесс: проход глушителя с двух сторон, стенки и сохранённое движение."""
from pathlib import Path
import hashlib,json,math,sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_vss_bore_v6 as F
import refine_vss_motion_v5 as M
import refine_vss_geometry_v4 as V
import build_vss_blender as B
from check_vss_geometry_v4 import evaluated,no_maps


def passage(owner,start,end):
    trees={obj.name:M.tree(obj) for obj in (owner,*owner.children_recursive) if obj.type=='MESH'}
    rays=[]
    offsets=[(0.,0.)]
    for radius in (.002,.0046):
        offsets.extend((radius*math.cos(i*math.tau/12),radius*math.sin(i*math.tau/12)) for i in range(12))
    for y,z in offsets:
        for x,direction in ((start,1),(end,-1)):
            for name,tree in trees.items():
                hit=tree.ray_cast(Vector((x,y,.010+z)),Vector((direction,0,0)),abs(end-start))
                assert hit[0] is None,('Passage obstructed',name,x,y,z,hit)
            rays.append({'origin_mm':[x*1000,y*1000,10+z*1000],'direction_x':direction})
    return rays


def main():
    report_path=F.RAW/'bore-audit.json';report_path.write_text('{"status":"RUNNING"}',encoding='utf8')
    bpy.ops.wm.open_mainfile(filepath=str(F.FILE));V.sync()
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];no_maps(root)
    topology={}
    for name in ('Suppressor_outer_body','Suppressor_barrel_through_tube','Tapered_polymer_handguard'):
        _,counts,_,_=evaluated(bpy.data.objects[name]);assert not any(counts.values()),(name,counts)
        topology[name]=counts
    assert bpy.data.objects.get('Suppressor_front_recess') is None
    rays=passage(root,.5574,.896)
    walls=[];tree=M.tree(bpy.data.objects['Suppressor_barrel_through_tube'])
    for x in (.56,.60,.65,.70,.75,.80,.85,.888):
        for y,z in ((1,0),(-1,0),(0,1),(0,-1)):
            hit=tree.ray_cast(Vector((x,0,.010)),Vector((0,y,z)),.008)
            assert hit[0] and abs(hit[3]-.005)<.00005,('Tube wall',x,y,z,hit)
            walls.append({'x_mm':x*1000,'direction_yz':[y,z],'distance_mm':hit[3]*1000})
    timeline=[]
    for frame in (1,20,45,88,95,120,145,180):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        controls=bpy.data.objects['VSS_Controls']
        carrier=bpy.data.objects['Bolt_carrier'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        assert controls.animation_data.action.name=='VSS_Demo'
        assert not M.tree(bpy.data.objects['Safety_lever_contoured']).overlap(M.tree(bpy.data.objects['Charging_handle_hook']))
        if frame==45:assert abs(carrier.location.x+.074)<1e-7
        if frame==145:assert .054<-carrier.location.x<.056
        timeline.append({'frame':frame,'safety':controls['safety_up'],'pull':controls['bolt_pull'],
                         'actual_travel_mm':-carrier.location.x*1000})
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    bounds=B.report_bounds('VSS_Assembly')
    B.render_views(F.RAW,'v6',[('muzzle','Camera_V6_Muzzle',1100,1000),
        ('rifle','Camera_Beauty_Right',1800,850)])
    bpy.ops.wm.open_mainfile(filepath=str(F.DETACHED));V.sync()
    owner=bpy.data.objects['Suppressor'];assert owner.parent is None;no_maps(owner)
    isolated_rays=passage(owner,.556,.896)
    B.render_views(F.RAW,'v6',[('front_through','Camera_V6_Front_Through',1100,1000),
        ('rear_through','Camera_V6_Rear_Through',1100,1000),
        ('suppressor','Camera_V6_Suppressor',1500,800)])
    files=[]
    for file in (F.FILE,F.DETACHED):
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert not bpy.data.libraries
        external=[]
        for image in bpy.data.images:
            if image.source=='FILE' and not image.packed_file:external.append(image.filepath)
        for font in bpy.data.fonts:
            if font.filepath not in {'','<builtin>'} and not font.packed_file:external.append(font.filepath)
        assert not external,external
        files.append({'name':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                      'external_dependencies':external})
    report={'status':'PASS','topology':topology,'assembly_passage_rays':rays,
            'isolated_passage_rays':isolated_rays,'tube_wall_rays':walls,
            'closed_assembly_bounds':bounds,'timeline':timeline,'files_reopened':files,
            'new_textures':False,'game_exports':False}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V6_BORE_AUDIT_PASS',flush=True)


def check_library():
    copy=json.loads((F.RAW/'library-copy-report.json').read_text(encoding='utf8'))
    assert copy['status']=='PASS';destination=Path(copy['destination']);rows=[]
    for row in copy['files']:
        if not row['path'].endswith('.blend'):continue
        file=destination/row['path'];assert hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256']
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert not bpy.data.libraries
        assert all(image.source!='FILE' or image.packed_file for image in bpy.data.images)
        assert all(font.filepath in {'','<builtin>'} or font.packed_file for font in bpy.data.fonts)
        owner=bpy.data.objects['Suppressor'];rays=passage(owner,.556,.896)
        full=bpy.data.objects.get('VSS_Vintorez_Picatinny')
        if full:assert bpy.data.objects['VSS_Controls'].animation_data.action.name=='VSS_Demo'
        else:assert owner.parent is None
        rows.append({'path':row['path'],'sha256':row['sha256'],'external_dependencies':[],
                     'passage_rays':len(rays),'full_rifle':bool(full)})
    assert len(rows)==2
    (F.RAW/'library-blend-check.json').write_text(json.dumps({'status':'PASS','files':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V6_LIBRARY_REOPEN_PASS',flush=True)


if __name__=='__main__':
    if '--library' in sys.argv:check_library()
    else:main()
