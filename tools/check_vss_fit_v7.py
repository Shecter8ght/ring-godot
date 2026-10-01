"""Посадка в шахту, направление крючка и пересчитанный ход после открытия."""
from pathlib import Path
import hashlib,json,sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_vss_fit_v7 as F
import refine_vss_motion_v5 as M
import refine_vss_geometry_v4 as V
import build_vss_blender as B
import check_vss_motion_v5 as A
from check_vss_geometry_v4 import evaluated,no_maps
from check_vss_bore_v6 import passage


def mesh_bounds(obj):
    _,_,points,_=evaluated(obj)
    return {'min_mm':[min(p[i]*1000 for p in points) for i in range(3)],
            'max_mm':[max(p[i]*1000 for p in points) for i in range(3)]}


def seat(owner):
    shaft={name:M.tree(bpy.data.objects[name]) for name in ('Magazine_well_side_plate','Receiver_lower_frame')}
    result=[]
    for obj in owner.children_recursive:
        if obj.type!='MESH':continue
        tree=M.tree(obj)
        for name,static in shaft.items():
            intersections=tree.overlap(static)
            assert not intersections,('Magazine/socket intersection',obj.name,name,len(intersections))
            result.append({'magazine_part':obj.name,'shaft_part':name,'intersections':0})
    # Прямой вид внутрь шахты: центральный объём теперь полый, боковые стенки сохранены.
    static=shaft['Magazine_well_side_plate'];rays=[]
    for x in (.426,.440,.460,.475):
        hit=static.ray_cast(Vector((x,0,-.070)),Vector((0,0,1)),.020)
        assert hit[0] is None,('Socket bottom obstructed',x,hit)
        for sign in (-1,1):
            side=static.ray_cast(Vector((x,0,-.029)),Vector((0,sign,0)),.025)
            assert side[0],('Missing socket side wall',x,sign)
            rays.append({'x_mm':x*1000,'side':sign,'wall_distance_mm':side[3]*1000})
    return result,rays


def main():
    report_path=F.RAW/'fit-audit.json';report_path.write_text('{"status":"RUNNING"}',encoding='utf8')
    M.RAW=F.RAW
    bpy.ops.wm.open_mainfile(filepath=str(F.FILE));V.sync()
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];no_maps(root)
    topology={}
    for name in ('Magazine_well_side_plate','Receiver_lower_frame','Curved_magazine_body_10','Charging_handle_hook'):
        _,counts,_,_=evaluated(bpy.data.objects[name]);assert not any(counts.values()),(name,counts)
        topology[name]=counts
    owner=bpy.data.objects['Magazine_939_10_Empty'];fits,walls=seat(owner)
    hook=bpy.data.objects['Charging_handle_hook'];_,_,points,_=evaluated(hook)
    first=sum(points[:24],Vector())/24;last=sum(points[-24:],Vector())/24
    assert last.x-first.x>.010,('Wrong hook direction',tuple(first),tuple(last))
    assert min(p.y for p in points)>-.037,('Hook too deeply curled',min(p.y for p in points))
    hook_shape={'root_mm':list(first*1000),'tip_mm':list(last*1000),'bounds':mesh_bounds(hook),
                'direction':'free end points towards +X, opposite v5/v6; shallow open arc'}
    pose_rows,probe=A.manual_check()
    bpy.ops.wm.open_mainfile(filepath=str(F.FILE));V.sync()
    timeline=[]
    for frame in (1,20,35,45,65,88,95,120,135,145,155,180):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        ctrl=bpy.data.objects['VSS_Controls'];carrier=bpy.data.objects['Bolt_carrier'].evaluated_get(bpy.context.evaluated_depsgraph_get())
        if frame==20:assert 0<ctrl['bolt_pull']<1
        if frame==88:assert 0<ctrl['safety_up']<1
        assert not M.tree(bpy.data.objects['Safety_lever_contoured']).overlap(M.tree(bpy.data.objects['Charging_handle_hook']))
        timeline.append({'frame':frame,'safety':ctrl['safety_up'],'pull':ctrl['bolt_pull'],'actual_travel_mm':-carrier.location.x*1000})
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    bore_rays=passage(bpy.data.objects['Suppressor'],.556,.896)
    bounds=B.report_bounds('VSS_Assembly')
    B.render_views(F.RAW,'v7',[('mag_front','Camera_V7_Mag_Front',1200,1000),
        ('mag_left','Camera_V7_Mag_Left',1200,1000),('mag_bottom','Camera_V7_Mag_Bottom',1300,950),
        ('hook_top','Camera_V7_Hook_Top',1100,1000),('hook_angle','Camera_V7_Hook_Angle',1200,950),
        ('review','Camera_V7_Review',1400,1000),('rifle','Camera_Beauty_Right',1800,850)])
    for frame,suffix in ((45,'full_travel'),(145,'safety_stop')):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        B.render_views(F.RAW,'v7',[(suffix,'Camera_V5_Side',1500,850)])
    magazines=[]
    for capacity in (10,20,30):
        for state in ('Empty','Loaded'):
            identifier=f'Magazine_939_{capacity}_{state}'
            file=F.RAW/'Магазины'/identifier/(identifier+'.blend')
            bpy.ops.wm.open_mainfile(filepath=str(file));V.sync()
            owner=bpy.data.objects[identifier];no_maps(owner)
            _,counts,_,_=evaluated(bpy.data.objects[f'Curved_magazine_body_{capacity}'])
            assert not any(counts.values()),(identifier,counts)
            assert owner['rounds_loaded']==(capacity if state=='Loaded' else 0)
            assert tuple(owner.location)==(0,0,0)
            B.render_views(file.parent,'v7',[('profile','Camera_Magazine_Profile',900,1100),('top','Camera_Top',1000,850)])
            # Все шесть самостоятельных вариантов действительно примеряются к сохранённой шахте.
            bpy.ops.wm.open_mainfile(filepath=str(F.FILE));V.sync()
            old=bpy.data.objects['Magazine_939_10_Empty']
            for part in list(old.children_recursive):V.remove(part)
            V.remove(old)
            appended=V.append_root(file,identifier,'Check_'+identifier)
            appended.parent=bpy.data.objects['VSS_Vintorez_Picatinny'];appended.location=V.PIVOT
            bpy.context.view_layer.update();contacts,_=seat(appended)
            magazines.append({'id':identifier,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                              'socket_checks':len(contacts),'body_topology':counts})
    bpy.ops.wm.open_mainfile(filepath=str(F.RAW/'VSS_and_Magazines_v7.blend'));V.sync()
    B.render_views(F.RAW,'v7',[('gallery','Camera_V7_Gallery',1600,1250)])
    files=[]
    paths=[F.FILE,F.RAW/'VSS_and_Magazines_v7.blend']
    paths.extend(F.RAW/'Магазины'/row['id']/(row['id']+'.blend') for row in magazines)
    for file in paths:
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert not bpy.data.libraries
        assert all(img.source!='FILE' or img.packed_file for img in bpy.data.images)
        assert all(font.filepath in {'','<builtin>'} or font.packed_file for font in bpy.data.fonts)
        files.append({'file':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'external_dependencies':[]})
    report={'status':'PASS','topology':topology,'socket_checks':fits,'socket_wall_rays':walls,
            'hook_shape':hook_shape,'manual_poses':pose_rows,'contact_probe':probe,'timeline':timeline,
            'preserved_bore_rays':len(bore_rays),'closed_bounds':bounds,'magazines':magazines,
            'files_reopened':files,'new_textures':False,'game_exports':False}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V7_FIT_AUDIT_PASS',flush=True)


def library_check():
    manifest=json.loads((F.RAW/'library-copy-report.json').read_text(encoding='utf8'))
    destination=Path(manifest['destination']);rows=[]
    for row in manifest['files']:
        if not row['path'].endswith('.blend'):continue
        file=destination/row['path']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256']
        bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
        assert not bpy.data.libraries
        assert all(img.source!='FILE' or img.packed_file for img in bpy.data.images)
        assert all(font.filepath in {'','<builtin>'} or font.packed_file for font in bpy.data.fonts)
        if 'VSS_Controls' in bpy.data.objects:
            assert 'Charging_handle_hook' in bpy.data.objects and 'Suppressor_barrel_through_tube' in bpy.data.objects
            assert bpy.data.objects['Charging_handle_hook'].parent.name=='Charging_handle'
            ctrl=bpy.data.objects['VSS_Controls']
            assert ctrl.animation_data and ctrl.animation_data.action
            assert len(bpy.data.objects['Bolt_carrier'].animation_data.drivers)>0
        else:
            owner=next(obj for obj in bpy.data.objects if obj.name.startswith('Magazine_939_') and obj.parent is None)
            assert tuple(owner.location)==(0,0,0)
            assert owner['rounds_loaded']==(0 if 'Empty' in owner.name else int(owner.name.split('_')[2]))
        rows.append({'file':str(file),'sha256':row['sha256'],'external_dependencies':[]})
    assert len(rows)==8
    (F.RAW/'library-blend-check.json').write_text(json.dumps({'status':'PASS','files':rows},ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V7_LIBRARY_CHECK_PASS',flush=True)


if __name__=='__main__':
    library_check() if '--library' in sys.argv else main()
