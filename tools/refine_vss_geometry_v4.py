"""Геометрия ВСС на согласование: стык, рычаг, рукоять и магазины 10/20/30.

Создаёт только нативные Blender-файлы и виды для осмотра; без карт и игровых экспортов.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import refine_vss_blender as R
import refine_vss_shoulder_stock as S

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_geometry_v4'
SOURCE=ROOT/'_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v3.blend'
PIVOT=Vector((.455,0,-.037))
CAPACITIES=(10,20,30)
LENGTHS={10:67.,20:132.,30:196.}
THETA=math.radians(15.5)
RADIUS=400.


def sync() -> None:
    B.COLLECTIONS.clear();B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    B.MATERIALS.clear();B.MATERIALS.update({m.name:m for m in bpy.data.materials})
    B.PARTS.clear();B.PARTS.update({o.name:o for o in bpy.data.objects})
    R.BUILD.COLLECTIONS.update(B.COLLECTIONS);R.BUILD.MATERIALS.update(B.MATERIALS)


def flat_materials() -> None:
    for name,color,metal,rough in (
        ('V4 steel',(.11,.14,.17),.35,.4),('V4 wood',(.45,.27,.12),0.,.5),
        ('V4 rubber',(.045,.055,.065),0.,.65),('V4 magazine',(.13,.15,.17),0.,.48),
        ('V4 brass',(.42,.29,.11),.45,.4),('V4 copper',(.38,.18,.09),.45,.4),
        ('V4 recess',(.035,.045,.055),0.,.55)):
        if name not in B.MATERIALS:B.material(name,color,metal,rough)
    R.BUILD.MATERIALS.update(B.MATERIALS)


def plain(root: bpy.types.Object) -> None:
    for obj in (root,*root.children_recursive):
        if obj.type!='MESH':continue
        name=obj.name
        if name.startswith('Wood_stock'):label='V4 wood'
        elif 'rubber' in name or 'butt_pad' in name:label='V4 rubber'
        elif any(t in name for t in ('Copper_projectile','Neck_seal')):label='V4 copper'
        elif any(t in name for t in ('Case_exterior','Primer')):label='V4 brass'
        elif 'groove' in name.lower() or '_slot' in name:label='V4 recess'
        elif obj.get('asset_role')=='body' or 'magazine' in name.lower():label='V4 magazine'
        else:label='V4 steel'
        obj.data.materials.clear();obj.data.materials.append(B.MATERIALS[label])


def remove(obj: bpy.types.Object) -> None:
    B.PARTS.pop(obj.name,None);R.BUILD.PARTS.pop(obj.name,None)
    bpy.data.objects.remove(obj,do_unlink=True)


def evaluated_copy(obj: bpy.types.Object,name: str) -> bpy.types.Object:
    deps=bpy.context.evaluated_depsgraph_get()
    mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),depsgraph=deps)
    copy=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(copy)
    copy.matrix_world=obj.matrix_world.copy()
    return copy


def receiver_and_stock() -> None:
    owner=bpy.data.objects['VSS_Vintorez_Picatinny']
    remove(bpy.data.objects['Receiver_lower_frame'])
    profile=[(282,16),(482,16),(482,-33),(415,-54),(405,-54),(405,-19),
             (347,-19),(347,-47),(335,-48),(324,-26),(320,-26)]
    profile.extend((313+7*math.cos(i*math.pi/16),-26-7*math.sin(i*math.pi/16)) for i in range(1,17))
    profile.append((282,-25))
    frame=B.prism('Receiver_lower_frame',profile,39,'V4 steel','02_Receiver',.65,parent=owner)
    remove(bpy.data.objects['Wood_stock_with_integral_grip'])
    outer=[(16,-20),(197,-20),(225,-18),(245,-9),(265,7),(278,8),
           (280,8),(281,-23),(306,-23),(324,-23),(335,-43),(342,-44),
           (342,-53),(342,-65),(339,-74),(335,-90),(329,-113),(331,-121),
           (303,-121),(293,-111),(279,-106),(247,-107),(16,-114)]
    rear=[(50,-39),(163,-39),(177,-49),(163,-89),(149,-99),(61,-99),(53,-87)]
    forward=[(215,-40),(287,-40),(304,-49),(307,-58),(295,-93),(281,-101),(207,-100),(198,-88)]
    loops=[B.rounded_polygon(outer,2),B.rounded_polygon(rear,3),B.rounded_polygon(forward,3)]
    # Сравниваем два радиуса на одной топологии и увеличиваем только переднюю рукоять.
    a=R.curve_plate('Wood_stock_with_integral_grip',loops,36,3.,'V4 wood','01_Stock',bpy.data.objects['Stock'])
    b=R.curve_plate('Grip_radius_candidate',loops,36,5.,'V4 wood','01_Stock',bpy.data.objects['Stock'])
    assert len(a.data.vertices)==len(b.data.vertices),'Bevel correspondence changed'
    assert [tuple(p.vertices) for p in a.data.polygons]==[tuple(p.vertices) for p in b.data.polygons]
    changed=0
    for vertex,other in zip(a.data.vertices,b.data.vertices):
        world=a.matrix_world@vertex.co
        wx=min(1.,max(0.,(world.x-.305)/.022))
        wz=min(1.,max(0.,(-world.z-.046)/.022))
        weight=wx*wx*(3-2*wx)*wz*wz*(3-2*wz)
        if weight:vertex.co=vertex.co.lerp(other.co,weight);changed+=1
    remove(b);a.data.update()
    S.seat_wood(a,bpy.data.objects['Ventilated_rubber_butt_pad'])
    bpy.context.view_layer.update()
    # Реальное вычитание по evaluated-поверхности корпуса устраняет просветы с обеих сторон.
    B.difference(a,evaluated_copy(frame,'Fit_receiver_to_stock'))
    # У скобы узкая задняя стенка: её объём нельзя вычитать только из середины
    # широкой рукояти — по бокам возникнут деревянные шипы. Посадка делается
    # единой поперечной выемкой со скруглённым переходом к передней грани.
    guard_seat=[(343.16,-44),(343.16,-56),(343.6,-58),(344.6,-60),
                (345.5,-62),(346.1,-64),(346.2,-66),(346.5,-68),(347,-71),
                (350,-75),(385,-80),(385,-40),(343.16,-40)]
    cutter=B.prism('Guard_seat_full_width',guard_seat,50,'V4 recess','01_Stock')
    B.difference(a,cutter)
    for face in a.data.polygons:face.use_smooth=abs(face.normal.y)<.995
    a['local_grip_bevel_mm']=5.;a['local_grip_vertices_adjusted']=changed
    a['join_method']='evaluated receiver/guard seat; old shoulder concavity retained'
    for side in (-1,1):
        for obj in bpy.data.objects:
            if obj.name.startswith('Stock_tang_'+str(side)):
                matrix=obj.matrix_world.copy()
                matrix.translation+=Vector((.007,side*.0018,.010))
                obj.matrix_world=matrix


def safety() -> None:
    owner=bpy.data.objects['Selector']
    for obj in list(owner.children_recursive):remove(obj)
    B.cylinder('Safety_pivot',(344,-21.1,-8),5.1,3.5,'V4 steel','02_Receiver',parent=owner,edge=.35)
    outline=[(339,-10),(338.8,-5),(341,-1),(348,2),(355,5),(363,9.5),
             (369,11),(382,11.8),(395,11.8),(400,10.8),(401,8.7),
             (411,8.7),(412,7.5),(412,5.6),(399,4.5),(392,1.8),
             (381,-1),(362,-6),(350,-10.5),(347,-13),(343,-13)]
    lever=B.prism('Safety_lever_contoured',B.rounded_polygon(outline,1),2.1,
                  'V4 steel','02_Receiver',0,-21.45,owner)
    # Передний язык слегка отогнут от плоскости коробки, как на новых фото.
    for v in lever.data.vertices:
        t=min(1.,max(0.,(v.co.x-.399)/.013));v.co.y-=.0022*t*t*(3-2*t)
    lever.data.update()
    pressed=[(342,-9.5),(341.5,-6),(344,-2.9),(351,1.4),(362,7.8),(368,8.6),
             (387,9.2),(391,8.8),(393,7),(393.3,5),(391.4,3.5),(388,3),
             (371,2.1),(366,1),(354,-5.5),(348,-11),(345,-11.2)]
    loop=B.rounded_polygon(pressed,2);cx,cz=365.,0.;n=len(loop)
    # Объёмное штампованное ребро с плавным скатом и плоской центральной площадкой.
    # Задняя поверхность заходит в лист, поэтому union даёт одну замкнутую деталь.
    verts=[];faces=[]
    for scale,y in ((1.,-22.2),(1.,-22.50),(.985,-22.85),(.965,-23.30),
                    (.94,-23.75),(.91,-24.02),(.88,-24.10)):
        verts.extend((cx+(x-cx)*scale,y,cz+(z-cz)*scale) for x,z in loop)
    faces.append(tuple(reversed(range(n))))
    for i in range(6):
        faces.extend((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for j in range(n))
    faces.append(tuple(range(6*n,7*n)))
    boss=B.mesh_object('Safety_pressed_rib_tool',verts,faces,'V4 steel','02_Receiver',0,owner)
    for face in boss.data.polygons:face.use_smooth=len(face.vertices)==4
    bpy.context.view_layer.objects.active=lever
    union=lever.modifiers.new('Pressed rib integral to lever','BOOLEAN')
    B.enum_set(union,'operation','UNION');B.enum_set(union,'solver','EXACT');union.object=boss
    bpy.ops.object.modifier_apply(modifier=union.name);remove(boss)
    B.bevel(lever,.22,3)
    lever['pressed_rib_visual_height_mm']=1.6;lever['tip_bend_visual_mm']=2.2
    B.cylinder('Safety_axis_washer',(344,-24.25,-8),3.6,.5,'V4 steel','02_Receiver',parent=owner,edge=.12)
    hexagon=[(344+2.65*math.cos(math.radians(30+i*60)),-8+2.65*math.sin(math.radians(30+i*60))) for i in range(6)]
    B.prism('Safety_axis_pin',hexagon,.85,'V4 steel','02_Receiver',.14,-24.65,owner)
    owner['visual_role']='external safety lever, corrected to user close-ups'


def angle(s: float) -> float:
    return THETA+(s-12+12*math.exp(-s/12))/RADIUS


def frame(s: float) -> tuple[float,float,float]:
    if s==0:return -1.5,2.,THETA
    count=max(12,int(abs(s)*3));step=s/count
    x=-1.5;z=2.
    for i in range(count):
        a=angle((i+.5)*step);x+=math.sin(a)*step;z-=math.cos(a)*step
    return x,z,angle(s)


def point(s: float,v: float,y: float) -> tuple[float,float,float]:
    x,z,a=frame(s)
    return x+v*math.cos(a),y,z+v*math.sin(a)


def width(s: float) -> float:
    t=min(1.,max(0.,s/18));return 66.5-7.5*t*t*(3-2*t)


def cross(w: float,t: float,r: float) -> list[tuple[float,float]]:
    result=[]
    for cx,cy,start in ((w/2-r,t/2-r,0),(-w/2+r,t/2-r,90),
                        (-w/2+r,-t/2+r,180),(w/2-r,-t/2+r,270)):
        for i in range(6):
            a=math.radians(start+i*90/5);result.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    return result


def magazine_body(capacity: int,owner: bpy.types.Object) -> bpy.types.Object:
    length=LENGTHS[capacity];group=owner.name
    count=48 if capacity==10 else 80
    steps=[length*i/count for i in range(count+1)]
    inner_steps=[(length-3)*i/count for i in range(count+1)]
    verts=[];outer=[];inner=[]
    for values,lists,hollow in ((steps,outer,False),(inner_steps,inner,True)):
        for s in values:
            profile=cross(width(s)-(4 if hollow else 0),24 if hollow else 28,1.0 if hollow else 2.0)
            ring=[]
            for v,y in profile:ring.append(len(verts));verts.append(point(s,v,y))
            lists.append(ring)
    n=len(outer[0]);faces=[]
    for rings,reverse in ((outer,False),(inner,True)):
        for a,b in zip(rings,rings[1:]):
            for j in range(n):
                k=(j+1)%n;quad=(a[j],a[k],b[k],b[j]);faces.append(tuple(reversed(quad)) if reverse else quad)
    for j in range(n):
        k=(j+1)%n;faces.append((outer[0][j],inner[0][j],inner[0][k],outer[0][k]))
    faces.append(tuple(outer[-1]));faces.append(tuple(reversed(inner[-1])))
    obj=B.mesh_object('Curved_magazine_body_'+str(capacity),verts,faces,'V4 magazine',group,.18,owner)
    for p in obj.data.polygons:p.use_smooth=abs(p.normal.y)<.99
    obj['asset_role']='body';obj['curve_radius_visual_mm']=RADIUS
    obj['curve_samples']=count;obj['wall_visual_mm']=2.
    return obj


def curved_prism(name: str,outline: list,thickness: float,y: float,group: str,owner: bpy.types.Object,
                 material: str='V4 magazine',radius: float=.18) -> bpy.types.Object:
    # Контур задаётся в координатах поперёк/вдоль дуги, а не ломаной в мировом XZ.
    n=len(outline);verts=[point(s,v,y+side*thickness/2) for side in (-1,1) for v,s in outline]
    faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
    faces.extend((i,(i+1)%n,n+(i+1)%n,n+i) for i in range(n))
    obj=B.mesh_object(name,verts,faces,material,group,radius,owner)
    obj['asset_role']='body'
    for p in obj.data.polygons:p.use_smooth=p.index>=2
    return obj


def magazine_details(capacity: int,owner: bpy.types.Object) -> None:
    length=LENGTHS[capacity];group=owner.name
    floor=[(-31,length-.4),(31,length-.4),(31,length+3.3),(-31,length+3.3)]
    curved_prism('Curved_floorplate_'+str(capacity),B.rounded_polygon(floor,1),31,0,group,owner,radius=.5)
    rows={10:6,20:12,30:18}[capacity]
    for side in (-1,1):
        for row in range(rows):
            s=18+row*(length-25)/(rows-1);half=width(s)/2-4
            outline=[(-half,s),(half,s),(half,s+1.2),(-half,s+1.2)]
            curved_prism('Curved_side_rib_'+str(side)+'_'+str(row),B.rounded_polygon(outline,1),
                         .75,side*14.23,group,owner,radius=.19)
            short=[(-8,s+3),(8,s+3),(8,s+4),(-8,s+4)]
            curved_prism('Short_side_inset_'+str(side)+'_'+str(row),B.rounded_polygon(short,1),
                         .06,side*14.035,group,owner,material='V4 recess',radius=0)
        for direction in (-1,1):
            outline=[(direction*(width(s)/2-1.6)+dv,s)
                     for dv,values in ((-.55,[18+i*(length-22)/36 for i in range(37)]),
                                       (.55,[18+i*(length-22)/36 for i in reversed(range(37))])) for s in values]
            curved_prism('Continuous_spine_'+str(side)+'_'+str(direction),outline,.5,side*14.15,group,owner,radius=.12)


def build_mag(capacity: int,loaded: bool) -> Path:
    source=ROOT/'_asset_src/vss_mag_ammo'/('Magazine_939_10_Loaded.blend' if loaded else 'Magazine_939_10_Empty.blend')
    bpy.ops.wm.open_mainfile(filepath=str(source));sync();flat_materials()
    old_root=bpy.data.objects['Magazine_939_10_Loaded' if loaded else 'Magazine_939_10_Empty']
    keep=set()
    for obj in old_root.children_recursive:
        if any(obj.name.startswith(p) for p in ('Feed_lip','Front_mount_lug','Rear_mount_lug','Follower',
             'Visible_rounds','Round_','Case_exterior','Copper_projectile','Neck_seal','Primer','MountOrigin','FeedPoint')):
            keep.add(obj)
    # Верх и два видимых патрона взяты из собственных отдельных ассетов; остальная оболочка новая.
    matrices={o:o.matrix_world.copy() for o in keep}
    for obj in list(bpy.data.objects):
        if obj.type in {'CAMERA','LIGHT'} or obj in keep:continue
        remove(obj)
    identifier='Magazine_939_'+str(capacity)+'_'+('Loaded' if loaded else 'Empty')
    if identifier not in B.COLLECTIONS:B.collection(identifier)
    owner=B.empty(identifier,(0,0,0),identifier)
    for obj in keep:
        if obj.parent not in keep:obj.parent=owner
        obj.matrix_world=matrices[obj]
        for collection in list(obj.users_collection):collection.objects.unlink(obj)
        B.COLLECTIONS[identifier].objects.link(obj)
    bpy.context.view_layer.update()
    magazine_body(capacity,owner);magazine_details(capacity,owner)
    owner['capacity']=capacity;owner['capacity_visual_variant']=capacity;owner['rounds_loaded']=capacity if loaded else 0
    owner['visible_rounds_geometry']=2 if loaded else 0
    owner['on_vss_mm']=[455,0,-37];owner['axes_source']='+X forward, +Z up, -Y right'
    owner['review_stage']='geometry only; no new texture maps, UV baking or game export'
    owner['variant_30']='artistic extended variant requested by owner; no dimensioned reference' if capacity==30 else 'visual photo-based approximation'
    plain(owner);bpy.context.view_layer.update()
    # Отдельная сценическая камера охватывает всю длину выбранного магазина.
    mid=point(LENGTHS[capacity]/2,0,0);target=tuple(p*.001 for p in mid)
    B.camera('Camera_Magazine_Profile',(target[0],-.6,target[2]),target,(LENGTHS[capacity]+75)*.001)
    B.camera('Camera_Magazine_Beauty',(target[0]+.12,-.45,target[2]+.16),target,(LENGTHS[capacity]+80)*.001)
    bpy.context.scene.camera=bpy.data.objects['Camera_Magazine_Beauty']
    bpy.context.scene.render.resolution_x=900;bpy.context.scene.render.resolution_y=1100
    configure_view(owner,'Camera_Magazine_Beauty')
    try:bpy.context.scene.render.engine='BLENDER_EEVEE'
    except TypeError:pass
    bpy.context.scene['stage']='Geometry approval; solid preview materials only'
    output=RAW/'Магазины'/identifier/(identifier+'.blend');output.parent.mkdir(parents=True,exist_ok=True)
    B.save_scene(output)
    return output


def append_root(path: Path,name: str,group: str) -> bpy.types.Object:
    with bpy.data.libraries.load(str(path),link=False) as (src,dst):dst.objects=src.objects
    root=next(o for o in dst.objects if o and o.name.split('.')[0]==name)
    descendants={root,*root.children_recursive}
    if group not in B.COLLECTIONS:B.collection(group)
    for obj in descendants:B.COLLECTIONS[group].objects.link(obj)
    for obj in dst.objects:
        if obj and obj not in descendants and obj.users==0:bpy.data.objects.remove(obj)
    return root


def build_rifle() -> Path:
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));sync();flat_materials()
    owner=bpy.data.objects['VSS_Vintorez_Picatinny'];before=S.snapshot(owner)
    excluded={'Wood_stock_with_integral_grip','Receiver_lower_frame'}
    excluded.update(o.name for o in bpy.data.objects['Selector'].children_recursive)
    excluded.update(o.name for o in B.COLLECTIONS['04_Magazine'].objects if o.type=='MESH')
    excluded.update(o.name for o in owner.children_recursive if o.name.startswith('Stock_tang_'))
    receiver_and_stock();safety()
    for obj in list(B.COLLECTIONS['04_Magazine'].objects):remove(obj)
    mag=append_root(RAW/'Магазины/Magazine_939_10_Empty/Magazine_939_10_Empty.blend',
                    'Magazine_939_10_Empty','04_Magazine')
    mag.parent=owner;mag.location=PIVOT
    plain(owner);bpy.context.view_layer.update()
    after=S.snapshot(owner);unchanged=[]
    for name in before:
        if name in excluded:continue
        assert before[name]==after[name],('Changed unrelated geometry',name)
        unchanged.append(name)
    for name,loc,target,scale in (
        ('Camera_V4_Join_Right',(.345,-.62,.035),(.32,0,-.037),.19),
        ('Camera_V4_Join_Left',(.345,.62,.035),(.32,0,-.037),.19),
        ('Camera_V4_Safety',(.379,-.60,.065),(.374,-.021,-.004),.13),
        ('Camera_V4_Safety_Angled',(.48,-.42,.085),(.374,-.021,-.004),.15),
        ('Camera_V4_Grip',(.54,-.48,-.016),(.32,0,-.084),.17),
        ('Camera_V4_Magazine',(.59,-.51,.055),(.457,0,-.076),.20)):
        B.camera(name,loc,target,scale)
    bpy.context.scene.camera=bpy.data.objects['Camera_V4_Safety_Angled']
    bpy.context.scene.render.resolution_x=1200;bpy.context.scene.render.resolution_y=850
    configure_view(owner,'Camera_V4_Safety_Angled')
    output=RAW/'VSS_Geometry_v4.blend';B.save_scene(output)
    report={'status':'BUILT','source':str(SOURCE),'source_sha256':digest,
            'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest,
            'unchanged_old_mesh_parts':len(unchanged),'unchanged_names':unchanged,
            'geometry_only':True,'no_texture_maps_generated':True,'no_game_export':True}
    (RAW/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return output


def gallery() -> Path:
    bpy.ops.wm.open_mainfile(filepath=str(RAW/'VSS_Geometry_v4.blend'));sync();flat_materials()
    for i,capacity in enumerate(CAPACITIES):
        for loaded in (False,True):
            identifier='Magazine_939_'+str(capacity)+'_'+('Loaded' if loaded else 'Empty')
            root=append_root(RAW/'Магазины'/identifier/(identifier+'.blend'),identifier,'Mag_Review_'+identifier)
            root.location=(.35+i*.16,0,-.51 if loaded else -.21)
    B.camera('Camera_V4_Gallery',(.69,-1.65,.35),(.447,0,-.24),1.33)
    B.camera('Camera_V4_Magazines',(.66,-.90,.12),(.54,0,-.39),.76)
    B.camera('Camera_V4_Mags_Profile',(.57,-1.50,-.31),(.57,0,-.31),.63)
    bpy.context.scene.camera=bpy.data.objects['Camera_V4_Gallery']
    bpy.context.scene.render.resolution_x=1600;bpy.context.scene.render.resolution_y=1250
    B.collection('95_Review_Labels')
    for i,capacity in enumerate(CAPACITIES):
        label('Review_capacity_'+str(capacity),str(capacity),(.35+i*.16,-.04,-.158),.015)
    label('Review_row_empty','EMPTY',(.20,-.04,-.24),.015)
    label('Review_row_loaded','LOADED',(.20,-.04,-.54),.015)
    configure_view(bpy.data.objects['VSS_Vintorez_Picatinny'],'Camera_V4_Gallery')
    output=RAW/'VSS_and_Magazines_10_20_30.blend';B.save_scene(output)
    return output


def label(name: str,body: str,location: tuple,size: float) -> None:
    data=bpy.data.curves.new(name,'FONT');data.body=body;data.size=size
    B.enum_set(data,'align_x','CENTER')
    obj=bpy.data.objects.new(name,data);B.COLLECTIONS['95_Review_Labels'].objects.link(obj)
    obj.location=location;obj.rotation_euler=(math.pi/2,0,0)
    data.materials.append(B.MATERIALS['V4 steel'])


def configure_view(owner: bpy.types.Object,camera_name: str) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active=owner
    camera=bpy.data.objects[camera_name]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type!='VIEW_3D':continue
            space=area.spaces.active
            B.enum_set(space.shading,'type','SOLID');B.enum_set(space.shading,'color_type','MATERIAL')
            space.overlay.show_overlays=False
            region=space.region_3d
            B.enum_set(region,'view_perspective','CAMERA');region.view_camera_zoom=6
            region.view_rotation=camera.rotation_euler.to_quaternion()
            region.view_location=owner.location;region.view_distance=camera.data.ortho_scale


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=('all','mags','rifle','gallery'),default='all')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    RAW.mkdir(parents=True,exist_ok=True)
    if args.stage in ('all','mags'):
        for capacity in CAPACITIES:
            for loaded in (False,True):build_mag(capacity,loaded)
    if args.stage in ('all','rifle'):build_rifle()
    if args.stage in ('all','gallery'):gallery()
    print('VSS_V4_GEOMETRY_BUILT',args.stage,flush=True)


if __name__=='__main__':main()
