"""Посадка магазинов ВСС и неглубокий крючок в противоположную сторону."""
from pathlib import Path
import hashlib,json,math,sys
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import refine_vss_geometry_v4 as V
import refine_vss_motion_v5 as M
import refine_vss_shoulder_stock as S

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_fit_v7'
SOURCE=RAW/'Live_Source.blend'
FILE=RAW/'VSS_Fit_v7.blend'
LIBRARY=Path('E:/Models Blender/ВСС Винторез — полный комплект')


def digest(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def well():
    profile=[(419.4,-22),(486.6,-22),(486.6,-33.5),(497,-65),(419.4,-65)]
    for name in ('Magazine_well_side_plate','Receiver_lower_frame'):
        obj=bpy.data.objects[name]
        matrix=obj.matrix_world.copy();inverse=matrix.inverted()
        # Передний обод охватывает фактический верх плавного магазина;
        # исходный обод был уже магазина и пересекал его наружную стенку.
        for vertex in obj.data.vertices:
            point=matrix@vertex.co
            if point.x>.4818:
                point.x+=.0055;vertex.co=inverse@point
        obj.data.update()
        tool=B.prism('Magazine_socket_clearance',profile,30,'V4 recess','02_Receiver')
        B.difference(obj,tool)
        obj['magazine_socket']='actual open pocket and front lip fitted around original magazine envelope'
        M.weld_degenerate_corners(obj)


def hook():
    owner=bpy.data.objects['Charging_handle'];V.remove(bpy.data.objects['Charging_handle_hook'])
    path=M.catmull([(467,-20.3,18),(467,-25,18),(467.6,-29.3,18),
                    (470,-32.2,17.5),(473.4,-33.6,16.5),(476.8,-34,15),(479,-33.7,13.3)])
    section=V.cross(3.4,4.7,.55);n=len(section);verts=[];faces=[]
    for i,center in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(i-1,0)]).normalized()
        side=Vector((-tangent.y,tangent.x,0)).normalized();up=tangent.cross(side).normalized()
        verts.extend(tuple(center+side*w+up*h) for w,h in section)
    faces.append(tuple(reversed(range(n))))
    for i in range(len(path)-1):
        faces.extend((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for j in range(n))
    faces.append(tuple(range((len(path)-1)*n,len(path)*n)))
    obj=B.mesh_object('Charging_handle_hook',verts,faces,'V4 steel','02_Receiver',0,owner)
    for face in obj.data.polygons:face.use_smooth=len(face.vertices)==4
    obj['shape']='shallow trigger-like arc; free end points forward, opposite the previous hook'
    return obj


def rebuild_motion():
    carrier=bpy.data.objects['Bolt_carrier'];selector=bpy.data.objects['Selector']
    for path,index in (('location',0),('["travel_limit"]',None)):
        if index is None:carrier.driver_remove(path)
        else:carrier.driver_remove(path,index)
    selector.driver_remove('rotation_euler',1)
    old=bpy.data.objects['VSS_Controls'];action=old.animation_data.action
    V.remove(old)
    if action.users==0:bpy.data.actions.remove(action)
    carrier.location.x=0;selector.rotation_euler.y=0;bpy.context.view_layer.update()
    M.RAW=RAW
    M.motion(carrier,selector,bpy.data.objects['Safety_lever_contoured'])


def rifle():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));V.sync()
    scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];before=S.snapshot(root)
    well();hook();rebuild_motion()
    changed={'Magazine_well_side_plate','Receiver_lower_frame','Charging_handle_hook'}
    after=S.snapshot(root);unchanged=[]
    for name,data in before.items():
        if name in changed:continue
        assert data==after[name],('Unrelated geometry changed',name)
        unchanged.append(name)
    for name,location,target,scale in (
        ('Camera_V7_Mag_Front',(.70,-.30,-.08),(.473,0,-.037),.14),
        ('Camera_V7_Mag_Left',(.68,.30,-.08),(.473,0,-.037),.14),
        ('Camera_V7_Mag_Bottom',(.50,-.25,-.22),(.454,0,-.039),.17),
        ('Camera_V7_Hook_Top',(.467,-.07,.28),(.467,-.025,.017),.095),
        ('Camera_V7_Hook_Angle',(.57,-.30,.10),(.469,-.026,.017),.095),
        ('Camera_V7_Review',(.64,-.55,.20),(.426,-.005,-.018),.25)):
        B.camera(name,location,target,scale)
    scene.camera=bpy.data.objects['Camera_V7_Review'];scene.render.resolution_x=1400;scene.render.resolution_y=1000
    V.configure_view(root,'Camera_V7_Review');B.save_scene(FILE)
    return {'source_sha256':digest(SOURCE),'unchanged_mesh_parts':len(unchanged),
            'unchanged_names':unchanged,'changed_names':sorted(changed)}


def magazines():
    rows=[]
    for capacity in (10,20,30):
        for state,label in (('Empty','Пустой'),('Loaded','Снаряжённый')):
            identifier=f'Magazine_939_{capacity}_{state}'
            source=LIBRARY/'08_На_согласование_геометрия_v4'/'Магазины'/f'{capacity}_патронов'/(label+'.blend')
            original=digest(source)
            file=RAW/'Магазины'/identifier/(identifier+'.blend');file.parent.mkdir(parents=True,exist_ok=True)
            import shutil
            shutil.copy2(source,file);assert digest(source)==original==digest(file)
            rows.append({'id':identifier,'source_sha256':original,'source':str(source),'file':str(file)})
    return rows


def gallery():
    bpy.ops.wm.open_mainfile(filepath=str(FILE));V.sync()
    for i,capacity in enumerate((10,20,30)):
        for state in ('Empty','Loaded'):
            identifier=f'Magazine_939_{capacity}_{state}'
            owner=V.append_root(RAW/'Магазины'/identifier/(identifier+'.blend'),identifier,'V7_Review_'+identifier)
            owner.location=(.35+i*.16,0,-.51 if state=='Loaded' else -.21)
    B.camera('Camera_V7_Gallery',(.69,-1.65,.35),(.447,0,-.24),1.33)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera_V7_Gallery']
    scene.render.resolution_x=1600;scene.render.resolution_y=1250
    V.configure_view(bpy.data.objects['VSS_Vintorez_Picatinny'],'Camera_V7_Gallery')
    B.save_scene(RAW/'VSS_and_Magazines_v7.blend')


def main():
    source=digest(SOURCE);report=rifle();report['magazines']=magazines();gallery()
    report.update(status='BUILT',source_unchanged=digest(SOURCE)==source,new_texture_maps=False,game_exports=False)
    (RAW/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V7_FIT_BUILT',flush=True)


if __name__=='__main__':main()
