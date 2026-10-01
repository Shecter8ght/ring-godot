"""Внешняя геометрия и постановочный ход затворной рукоятки ВСС в Blender."""
from __future__ import annotations
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import refine_vss_geometry_v4 as V
import refine_vss_shoulder_stock as S

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_motion_v5'
SOURCE=RAW/'Live_Source_v4.blend'
FILE=RAW/'VSS_Motion_v5.blend'
FULL=.074
RAISE=math.radians(10)
CLEARANCE=.00018


def reparent(obj,parent):
    matrix=obj.matrix_world.copy();obj.parent=parent;obj.matrix_world=matrix


def union(obj,tool):
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Integral folded feature','BOOLEAN')
    B.enum_set(mod,'operation','UNION');B.enum_set(mod,'solver','EXACT');mod.object=tool
    bpy.ops.object.modifier_move_to_index(modifier=mod.name,index=0)
    bpy.ops.object.modifier_apply(modifier=mod.name);V.remove(tool)


def tree(obj):
    deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    verts=[ev.matrix_world@v.co for v in mesh.vertices]
    result=BVHTree.FromPolygons(verts,[p.vertices[:] for p in mesh.polygons])
    ev.to_mesh_clear();return result


def weld_degenerate_corners(obj):
    deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps);mesh=ev.to_mesh()
    bm=bmesh.new();bm.from_mesh(mesh);ev.to_mesh_clear()
    bad=[face for face in bm.faces if face.calc_area()<1e-14]
    if not bad:bm.free();return
    # Только совпавшие вершины конкретных вырожденных граней; остальные
    # фаски и мелкие детали не попадают в область очистки.
    vertices={v for face in bad for v in face.verts}
    bmesh.ops.remove_doubles(bm,verts=list(vertices),dist=5e-8)
    assert not any(face.calc_area()<1e-14 for face in bm.faces),(obj.name,'Remaining collapsed face')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    mesh=bpy.data.meshes.new(obj.name+'_clean');bm.to_mesh(mesh);bm.free()
    for material in obj.data.materials:mesh.materials.append(material)
    obj.data=mesh
    for modifier in list(obj.modifiers):obj.modifiers.remove(modifier)
    obj['local_duplicate_corner_cleanup']=len(bad)


def receiver():
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];cover_parent=bpy.data.objects['Dust_cover']
    for name in ('Rounded_dust_cover','Ejection_recess_dark_back','Bolt_visible_strip',
                 'Charging_handle_stem','Charging_handle_tab'):V.remove(bpy.data.objects[name])
    section=B.cover_section()
    cover=B.loft('Rounded_dust_cover',[(284,[(y*.87,z-3) for y,z in section]),
                 (293,section),(474,section),(479,[(y*.92,z-2) for y,z in section])],
                 'V4 steel','02_Receiver',cover_parent)
    # Тонкая оболочка допускает уход наружной крышки рамы под неподвижный кожух.
    inner=[(-20.8,1),(20.8,1),(20.8,25)]
    inner.extend((20.8*math.cos(i*math.pi/24),25+17.7*math.sin(i*math.pi/24)) for i in range(1,25))
    cutter=B.loft('Cover_inner_clearance',[(294,inner),(474,inner)],'V4 recess','02_Receiver')
    B.difference(cover,cutter)
    port=[(343,12),(343.2,13),(344,14),(360,19.8),(365,21),(396.5,21),
          (396.5,27.5),(397.1,29),(399,31.5),(401,33),(404,34),
          (474,34),(476,32),(477.8,30),(477.8,12.3),(477.5,12)]
    for target in (cover,bpy.data.objects['Receiver_lower_frame'],bpy.data.objects['Cover_pressed_rib_401']):
        cutter=B.prism('Ejection_window_cut',port,35,'V4 recess','02_Receiver',0,-26)
        B.difference(target,cutter)
    # Радиус внешней оболочки задан её сечением; общий Bevel на тонком
    # вырезанном листе схлопывал малые угловые грани окна.
    for face in cover.data.polygons:face.use_smooth=abs(face.normal.x)<.98
    B.prism('Ejection_cavity_inner_wall',[(320,12),(479,12),(479,37),(320,37)],
            .8,'V4 recess','02_Receiver',.15,-7.5,root)
    cover['window_role']='external case-ejection window and rear handle slot; visual asset'
    carrier=B.empty('Bolt_carrier',(0,0,0),'02_Receiver',root)
    leaf=[(398,13.2),(397,25.5),(399.5,30),(404,33),(472,33),(476.4,30),
          (476.4,14),(470,13.2)]
    plate=B.prism('Bolt_carrier_visible_cover',B.rounded_polygon(leaf,1),.75,
                  'V4 steel','02_Receiver',.25,-20.175,carrier)
    notch=B.cylinder('Carrier_top_index_cut',(444,-20,33.7),1.45,8,
                     'V4 recess','02_Receiver',parent=None,edge=0)
    B.difference(plate,notch)
    # Верх листа повторяет внутренний радиус кожуха и уходит под него
    # при отводе. Плоская пластина здесь пересекала бы округлую оболочку.
    for vertex in plate.data.vertices:
        z=vertex.co.z*1000
        if z>25:
            inner_y=-20.8*math.sqrt(max(0.,1-((z-25)/17.7)**2))
            vertex.co.y+=(inner_y+20.8)*.001
    plate.data.update()
    B.cylinder('Carrier_cover_pin',(423,-20.40,26.7),.75,.18,
                'V4 steel','02_Receiver',parent=carrier,edge=.09)
    handle=bpy.data.objects['Charging_handle'];reparent(handle,carrier)
    hook(handle)
    carrier['visual_role']='visible carrier cover and hooked handle move as one'
    return carrier


def catmull(points,subdivisions=12):
    result=[]
    for i in range(len(points)-1):
        a=Vector(points[max(i-1,0)]);b=Vector(points[i]);c=Vector(points[i+1]);d=Vector(points[min(i+2,len(points)-1)])
        for k in range(subdivisions):
            t=k/subdivisions
            result.append((2*b+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)*.5)
    result.append(Vector(points[-1]));return result


def hook(owner):
    path=catmull([(467,-20.3,18),(467,-24.5,18),(467,-29.5,18),
                  (465.5,-34.5,18.2),(462.5,-38.3,18.5),(458.4,-40.5,18.4),
                  (454.5,-41.5,17.7),(451.5,-41.1,16.3),(449.5,-39.5,14.3)])
    section=V.cross(4.2,5.6,.65);n=len(section);verts=[];faces=[]
    for i,center in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(i-1,0)]).normalized()
        side=Vector((-tangent.y,tangent.x,0)).normalized()
        up=tangent.cross(side).normalized()
        verts.extend(tuple(center+side*w+up*h) for w,h in section)
    faces.append(tuple(reversed(range(n))))
    for i in range(len(path)-1):
        faces.extend((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for j in range(n))
    faces.append(tuple(range((len(path)-1)*n,len(path)*n)))
    obj=B.mesh_object('Charging_handle_hook',verts,faces,'V4 steel','02_Receiver',0,owner)
    for face in obj.data.polygons:face.use_smooth=len(face.vertices)==4
    obj['shape']='continuous J-shaped blade: outward stem, rearward curl, rounded dropped tip'


def safety_tip():
    lever=bpy.data.objects['Safety_lever_contoured'];owner=bpy.data.objects['Selector']
    cutter=B.box('Replace_safety_tip',(427,0,0),(55,120,150),'V4 recess','02_Receiver')
    B.difference(lever,cutter)
    web=B.prism('Safety_front_web_tool',[(398.5,8.7),(412.5,8.7),(413,1),
                 (410,.2),(398.5,2.8)],1.65,'V4 steel','02_Receiver',0,-22.8,owner)
    union(lever,web)
    for name,z,extent in (('Upper',8.5,4.5),('Lower',.8,3.8)):
        tab=B.box('Safety_'+name+'_fold_tool',(406.5,-24,z),(12.6,extent,1.15),
                  'V4 steel','02_Receiver',0,owner)
        union(lever,tab)
    # Болт оси и шайба неподвижны, поворачивается только сам рычаг.
    root=bpy.data.objects['VSS_Vintorez_Picatinny']
    for name in ('Safety_axis_pin','Safety_axis_washer','Safety_pivot'):reparent(bpy.data.objects[name],root)
    lever['tip_role']='two folded returns around the forward web; raised upper stop'
    return owner,lever


def variable(driver,name,obj,path):
    var=driver.variables.new();var.name=name;B.enum_set(var,'type','SINGLE_PROP')
    var.targets[0].id=obj;var.targets[0].data_path=path


def motion(carrier,selector,lever):
    root=bpy.data.objects['VSS_Vintorez_Picatinny']
    controls=B.empty('VSS_Controls',(383,0,92),'02_Receiver',root)
    controls['safety_up']=0.;controls['bolt_pull']=0.
    for key,description in (('safety_up','0 — опущен, 1 — поднят'),('bolt_pull','Запрошенный отвод рукоятки: 0–1')):
        controls.id_properties_ui(key).update(min=0.,max=1.,soft_min=0.,soft_max=1.,description=description)
    controls['purpose']='visual Blender demo; disable VSS_Demo action for manual sliders'
    handle=bpy.data.objects['Charging_handle_hook'];samples=[]
    for i in range(41):
        safety=i/40;selector.rotation_euler.y=-RAISE*safety;carrier.location.x=0
        bpy.context.view_layer.update();stop_tree=tree(lever)
        def contact(distance):
            carrier.location.x=-distance;bpy.context.view_layer.update()
            return bool(stop_tree.overlap(tree(handle)))
        previous=0.;found=None
        for k in range(1,149):
            distance=FULL*k/148
            if contact(distance):
                low=previous;high=distance
                for _ in range(13):
                    middle=(low+high)*.5
                    if contact(middle):high=middle
                    else:low=middle
                found=low;break
            previous=distance
        limit=max(0.,found-CLEARANCE) if found is not None else FULL
        samples.append({'safety':safety,'contact_mm':found*1000 if found is not None else None,'allowed_mm':limit*1000})
    assert samples[0]['contact_mm'] is None and samples[-1]['contact_mm'] is not None
    carrier.location.x=0;selector.rotation_euler.y=0;bpy.context.view_layer.update()
    # Таблица сопоставления хранится в нативной driver FCurve, без Python handler/namespace.
    carrier['travel_limit']=FULL
    curve=carrier.driver_add('["travel_limit"]')
    for modifier in list(curve.modifiers):curve.modifiers.remove(modifier)
    B.enum_set(curve.driver,'type','AVERAGE')
    variable(curve.driver,'safety',controls,'["safety_up"]')
    for row in samples:
        point=curve.keyframe_points.insert(row['safety'],row['allowed_mm']*.001)
        B.enum_set(point,'interpolation','LINEAR')
    B.enum_set(curve,'extrapolation','CONSTANT');curve.update()
    curve=selector.driver_add('rotation_euler',1);curve.driver.expression='-angle*safety'
    controls['safety_angle']=RAISE
    variable(curve.driver,'angle',controls,'["safety_angle"]');variable(curve.driver,'safety',controls,'["safety_up"]')
    curve=carrier.driver_add('location',0);curve.driver.expression='-min(pull*stroke,stop)'
    controls['visual_full_travel']=FULL
    variable(curve.driver,'pull',controls,'["bolt_pull"]');variable(curve.driver,'stroke',controls,'["visual_full_travel"]')
    variable(curve.driver,'stop',carrier,'["travel_limit"]')
    poses=[(1,0,0),(15,0,0),(35,0,1),(50,0,1),(65,0,0),
           (80,0,0),(95,1,0),(110,1,0),(135,1,1),(155,1,1),(175,1,0),(180,1,0)]
    for frame,safety,pull in poses:
        controls['safety_up']=float(safety);controls['bolt_pull']=float(pull)
        controls.keyframe_insert(data_path='["safety_up"]',frame=frame)
        controls.keyframe_insert(data_path='["bolt_pull"]',frame=frame)
    controls.animation_data.action.name='VSS_Demo'
    scene=bpy.context.scene;scene.render.fps=30;scene.frame_start=1;scene.frame_end=180
    scene.timeline_markers.clear()
    for frame,name in ((1,'Предохранитель опущен'),(35,'Полный ход назад'),
                       (95,'Предохранитель поднят'),(135,'Упор рукоятки в предохранитель')):
        scene.timeline_markers.new(name,frame=frame)
    scene.frame_set(1);bpy.context.view_layer.update()
    (RAW/'contact-samples.json').write_text(json.dumps(samples,indent=2),encoding='utf8')
    return controls


def main():
    RAW.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));V.sync()
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];before=S.snapshot(root)
    changed={'Rounded_dust_cover','Receiver_lower_frame','Cover_pressed_rib_401',
             'Bolt_visible_strip','Ejection_recess_dark_back','Charging_handle_stem','Charging_handle_tab',
             'Safety_lever_contoured','Safety_axis_pin','Safety_axis_washer','Safety_pivot'}
    carrier=receiver();selector,lever=safety_tip()
    for name in ('Rounded_dust_cover','Bolt_carrier_visible_cover','Safety_lever_contoured'):
        weld_degenerate_corners(bpy.data.objects[name])
    motion(carrier,selector,lever)
    after=S.snapshot(root);unchanged=[]
    for name,data in before.items():
        if name in changed:continue
        assert data==after[name],('Unrelated geometry changed',name)
        unchanged.append(name)
    for name,location,target,scale in (
        ('Camera_V5_Side',(.408,-.63,.047),(.408,-.018,.005),.18),
        ('Camera_V5_Hook',(.59,-.40,.11),(.455,-.024,.019),.115),
        ('Camera_V5_Top',(.453,-.18,.31),(.455,-.025,.015),.12),
        ('Camera_V5_Stop',(.49,-.46,.065),(.419,-.024,.020),.13)):
        B.camera(name,location,target,scale)
    bpy.context.scene.camera=bpy.data.objects['Camera_V5_Stop']
    bpy.context.scene.render.resolution_x=1300;bpy.context.scene.render.resolution_y=850
    V.configure_view(root,'Camera_V5_Stop');B.save_scene(FILE)
    for name,frame in (('01_Closed',1),('02_Full_Travel',45),('03_Safety_Stop',145)):
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        B.save_scene(RAW/(name+'.blend'))
    bpy.context.scene.frame_set(1);B.save_scene(FILE)
    report={'status':'BUILT','source_sha256':digest,'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest,
            'unchanged_mesh_parts':len(unchanged),'unchanged_names':unchanged,'changed_names':sorted(changed),
            'geometry_and_visual_motion_only':True,'game_exports':False,'new_texture_maps':False}
    (RAW/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V5_MOTION_BUILT',flush=True)


if __name__=='__main__':main()
