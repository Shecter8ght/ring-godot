"""Fresh-file geometry QA and neutral Cycles views for PM v06."""
from pathlib import Path
import argparse, hashlib, json, math, sys
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap=argparse.ArgumentParser();ap.add_argument('--draft',action='store_true');ap.add_argument('--only',default='');ap.add_argument('--audit-only',action='store_true');ap.add_argument('--revision',default='v06',choices=['v06','v07'])
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement';OUT=ROOT/('review_'+args.revision)
S=bpy.context.scene;rig=bpy.data.objects['PM_CONTROLS • select me'];S.frame_set(1);bpy.context.view_layer.update()
action=rig.animation_data.action if rig.animation_data else None
rig.animation_data_clear()
for k in ('Slide','Hammer','Trigger','Safety','Magazine','Suppressor','MagCatch'):rig[k]=0.0
for marker in S.timeline_markers:marker.camera=None
def pose(**values):
    for k,v in values.items():rig[k]=float(v)
    rig.update_tag();S.frame_set(S.frame_current);bpy.context.view_layer.update()
def within(o,root):
    p=o
    while p:
        if p==root:return True
        p=p.parent
    return False
def tree_of(o):
    dg=bpy.context.evaluated_depsgraph_get();eo=o.evaluated_get(dg);m=eo.to_mesh()
    t=BVHTree.FromPolygons([eo.matrix_world@v.co for v in m.vertices],[tuple(p.vertices) for p in m.polygons]);eo.to_mesh_clear();return t
def bbox(objects):
    lo=np.array([math.inf]*3);hi=-lo.copy();dg=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        if o.type not in {'MESH','CURVE'}:continue
        eo=o.evaluated_get(dg);m=eo.to_mesh()
        if not m or not m.vertices:eo.to_mesh_clear();continue
        v=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3)
        matrix=np.asarray(eo.matrix_world,dtype=np.float32);v=v@matrix[:3,:3].T+matrix[:3,3]
        lo=np.minimum(lo,v.min(axis=0));hi=np.maximum(hi,v.max(axis=0));eo.to_mesh_clear()
    return dict(min_mm=(lo*1000).tolist(),max_mm=(hi*1000).tolist(),dimensions_mm=((hi-lo)*1000).tolist())
mount=bpy.data.objects['PM_OpticMount • asset root'];optic=bpy.data.objects['PM_ReflexSight • asset root']
props=[o for o in bpy.data.objects if o.type=='EMPTY' and o.name.startswith('Animation |')]
scope=[o for o in bpy.data.objects if within(o,rig) and o.type in {'MESH','CURVE'} and not within(o,bpy.data.objects['Suppressor • removal']) and not any(within(o,p) for p in props) and not o.name.startswith(('Animation','Reference','Safety wear'))]
for p in props:
    for o in bpy.data.objects:
        if within(o,p):o.hide_render=True
base=[o for o in scope if not within(o,mount)]
report=dict(file=bpy.data.filepath,sha256=hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),version=bpy.app.version_string,
    base_closed=bbox(base),assembly_closed=bbox(scope),mount=bbox([o for o in scope if within(o,mount) and not within(o,optic)]),optic=bbox([o for o in scope if within(o,optic)]),geometry={},poses=[],passages={})
rail=bbox([o for o in scope if o.name.startswith(('Mount | continuous','Mount | chamfered rail tooth'))])
slide_bounds=bbox([bpy.data.objects['Slide | continuous crown, rounded muzzle & rear']])
report['reference_proportions']=dict(rail=rail,slide=slide_bounds,
    rail_length_ratio=rail['dimensions_mm'][0]/slide_bounds['dimensions_mm'][0],
    rail_width_ratio=rail['dimensions_mm'][1]/slide_bounds['dimensions_mm'][1],
    mount_screw_count=sum(o.name.startswith('Mount | cross-slot fastener') for o in scope),
    trigger=bbox([o for o in scope if o.name.startswith('Trigger |')]),
    clamp_plate=bbox([o for o in scope if o.name.startswith('Mount | rounded two-screw')]))
report['reference_proportions']['pass']=all(.30<report['reference_proportions'][k]<.36 for k in ('rail_length_ratio','rail_width_ratio')) and report['reference_proportions']['mount_screw_count']==2
names=[o.name for o in scope if o.type=='MESH' and o.name.startswith(('Frame | traced','Slide | continuous','Hammer |','Safety | tapered','Safety | beveled','Trigger |','Barrel | stepped','Rear sight |','Extractor |','MagCatch |','Lanyard | molded','Grip checkering |','Mount |','Reflex |','Magazine | aligned','Magazine | straight','Magazine | inset floorplate'))]
dg=bpy.context.evaluated_depsgraph_get()
for name in names:
    o=bpy.data.objects[name];eo=o.evaluated_get(dg);m=eo.to_mesh();bm=bmesh.new();bm.from_mesh(m)
    row=dict(vertices=len(bm.verts),faces=len(bm.faces),boundary=sum(e.is_boundary for e in bm.edges),overfull=sum(len(e.link_faces)>2 for e in bm.edges),wire=sum(e.is_wire for e in bm.edges),zero_area=sum(f.calc_area()<1e-14 for f in bm.faces))
    row['closed_pass']=row['boundary']==row['overfull']==row['wire']==row['zero_area']==0
    report['geometry'][name]=row;bm.free();eo.to_mesh_clear()
    print('PM_TOPOLOGY',name,row,flush=True)
for key in ('Slide','Hammer','Safety','Trigger','Magazine','MagCatch'):
    for value in (0,.5,1):
        pose(**{key:value})
        root={'Slide':'Slide • translation','Hammer':'Hammer • pivot','Safety':'Safety • pivot','Trigger':'Trigger • pivot','Magazine':'Magazine • extraction','MagCatch':'MagCatch • pivot'}[key]
        o=bpy.data.objects[root].evaluated_get(bpy.context.evaluated_depsgraph_get())
        report['poses'].append(dict(control=key,value=value,world_location_mm=[v*1000 for v in o.matrix_world.translation],world_rotation=[v for v in o.matrix_world.to_euler()],finite=all(math.isfinite(v) for row in o.matrix_world for v in row)))
    pose(**{key:0})
motion={}
for key in ('Slide','Hammer','Safety','Trigger','Magazine','MagCatch'):
    rows=[r for r in report['poses'] if r['control']==key];a=rows[0];b=rows[-1]
    delta=[b['world_location_mm'][i]-a['world_location_mm'][i] for i in range(3)]
    angle=b['world_rotation'][1]-a['world_rotation'][1]
    passed=(25<delta[0]<45) if key=='Slide' else (delta[2]<-65) if key=='Magazine' else (angle<-.15) if key=='Trigger' else (angle>.1)
    motion[key]=dict(delta_mm=delta,delta_angle_rad=angle,pass_motion=passed)
catch_matrix=bpy.data.objects['MagCatch • pivot'].matrix_world.copy()
mount_matrix=mount.matrix_world.copy()
pose(Magazine=1)
motion['Catch independent of magazine']=dict(pass_motion=max(abs(catch_matrix[i][j]-bpy.data.objects['MagCatch • pivot'].matrix_world[i][j]) for i in range(4) for j in range(4))<1e-7)
pose(Magazine=0,Slide=1)
motion['Mount follows slide']=dict(pass_motion=abs((mount.matrix_world.translation.x-mount_matrix.translation.x)*1000-motion['Slide']['delta_mm'][0])<.001)
pose(Slide=0)
report['motion']=motion
# Nine sample lines through the barrel, from either end, across the bore.
t=tree_of(bpy.data.objects['Barrel | stepped cylindrical chamber and open bore']);mw=rig.matrix_world
samples=[]
for dy,dz in ((0,0),(.025,0),(-.025,0),(0,.025),(0,-.025),(.017,.017),(.017,-.017),(-.017,.017),(-.017,-.017)):
    a=mw@Vector((-1.03,dy,1.398333333+dz));b=mw@Vector((.195,dy,1.398333333+dz));direction=b-a;dist=direction.length;direction.normalize()
    hit,_,_,_=t.ray_cast(a,direction,dist);rh,_,_,_=t.ray_cast(b,-direction,dist)
    samples.append(dict(offset=[dy,dz],front_clear=hit is None,rear_clear=rh is None))
report['passages']['barrel']=samples
# Preserve a finite test of the frame's magazine passage. Exclude the installed
# magazine, the frame-edge catch, and the optical accessories deliberately.
frame_tree=tree_of(bpy.data.objects['Frame | traced flowing silhouette']);passage=[]
for u in (-.085,0,.085):
    for y in (-.045,0,.045):
        def at(h):return mw@Vector((.613+u*math.cos(-.139)+h*math.sin(-.139),y,.035-u*math.sin(-.139)+h*math.cos(-.139)))
        a=at(-.065);b=at(1.46);d=b-a;l=d.length;d.normalize();hit,_,_,_=frame_tree.ray_cast(a,d,l)
        passage.append(dict(u=u,y=y,clear=hit is None,hit_mm=[v*1000 for v in hit] if hit else None))
report['passages']['frame_magazine']=passage
if args.revision=='v07':
    spine=bbox([bpy.data.objects['Mount | continuous relieved rail spine']])
    roof_world=mw@Vector((-.118,0,1.528333333))
    gap=spine['min_mm'][2]-roof_world.z*1000
    eo=bpy.data.objects['Magazine | aligned thin floorplate and extraction toe'].evaluated_get(bpy.context.evaluated_depsgraph_get());me=eo.to_mesh()
    face=max(me.polygons,key=lambda f:f.area);normal=(eo.matrix_world.to_3x3().inverted().transposed()@face.normal).normalized()
    normal_dot=abs(normal.dot(Vector((0,0,1))));eo.to_mesh_clear()
    new_rear=bbox([bpy.data.objects['Rear sight | beveled twin-ear blade']])
    optic_anchor=optic.matrix_world.translation
    expected_anchor=mw@Vector((-.145,0,1.591))
    report['owner_corrections']=dict(rail_underside_gap_mm=gap,rail_height_mm=rail['dimensions_mm'][2],
        floorplate_parallel_dot=normal_dot,rear_blade_mm=new_rear['dimensions_mm'],
        optic_origin_error_mm=(optic_anchor-expected_anchor).length*1000,
        pass_corrections=1.2<gap<2.0 and 2.9<rail['dimensions_mm'][2]<3.8 and normal_dot>.999999 and (optic_anchor-expected_anchor).length<1e-6)
report['audit_pass']=all(r['closed_pass'] for r in report['geometry'].values()) and all(r['front_clear'] and r['rear_clear'] for r in samples) and all(r['clear'] for r in passage) and all(r['finite'] for r in report['poses']) and report['reference_proportions']['pass'] and all(r['pass_motion'] for r in motion.values())
if args.revision=='v07':report['audit_pass']=report['audit_pass'] and report['owner_corrections']['pass_corrections']
(OUT/'Проверки/fresh_file_geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_QA',report['audit_pass'],'base',report['base_closed']['dimensions_mm'],'assembly',report['assembly_closed']['dimensions_mm'],flush=True)
if not report['audit_pass']:raise RuntimeError('Fresh-file PM geometry QA failed; see saved report')
if args.audit_only:sys.exit(0)
S.render.engine='CYCLES';S.cycles.use_denoising=True
p=bpy.context.preferences.addons['cycles'].preferences
try:
    p.compute_device_type='OPTIX';p.get_devices()
    for device in p.devices:device.use=device.type!='CPU'
    if any(d.use for d in p.devices):S.cycles.device='GPU'
except Exception as e:print('PM_GPU',str(e),flush=True);S.cycles.device='CPU'
S.cycles.samples=24 if args.draft else 96
S.view_settings.exposure=-1.25
S.render.image_settings.file_format='PNG';S.render.resolution_percentage=100
S.render.film_transparent=False
S.render.resolution_x=1100 if args.draft else 1800;S.render.resolution_y=760 if args.draft else 1240
cam=bpy.data.objects['CHECK 01 | Complete PM and separate sight']
cam.data.type='ORTHO';cam.data.clip_start=.0001;cam.data.clip_end=10
def set_accessories(show):
    for name in ('08 • Optic mount — separate asset','09 • Reflex sight — separate asset'):bpy.data.collections[name].hide_render=not show
views=[
('01_ПМ_с_прицелом',(-.24,-.34,.235),(.003,0,.082),.231,True,{}),
('02_ПМ_справа',(-.18,.34,.23),(.000,0,.082),.232,True,{}),
('03_Силуэт_слева',(.000,-.36,.074),(.000,0,.074),.208,False,{}),
('04_Силуэт_справа',(.000,.36,.074),(.000,0,.074),.208,False,{}),
('05_Окно_ствол_выбрасыватель',(-.065,.16,.181),(-.008,.01,.117),.075,False,{}),
('06_Курок_фаски',(.146,-.076,.165),(.073,0,.117),.053,False,{}),
('07_Целик_сварной_шов',(.073,-.068,.167),(.060,0,.124),.028,False,{}),
('08_Предохранитель',(.066,-.13,.143),(.060,-.011,.112),.043,False,{}),
('09_Спуск_и_скоба',(-.015,-.14,.072),(-.007,0,.074),.064,False,{}),
('10_Накладка_насечка',(.043,-.20,.071),(.049,0,.045),.105,False,{}),
('11_Снизу_защёлка_магазина',(.128,-.075,-.063),(.057,0,.013),.077,False,{}),
('12_Защёлка_крупно',(.035,-.086,-.115),(.065,-.002,.010),.044,False,{}),
('13_Дульный_канал',(-.175,-.018,.118),(-.069,0,.113),.052,False,{}),
('14_Затвор_назад_снизу',(.049,.26,.052),(.021,0,.098),.178,False,{'Slide':1}),
('15_Курок_взведён',(.143,-.078,.15),(.075,0,.113),.074,False,{'Hammer':1}),
('16_Предохранитель_вверх',(.077,-.13,.142),(.062,-.011,.113),.057,False,{'Safety':1}),
('17_Крепление_отдельно',(-.110,-.16,.197),(-.010,-.004,.121),.087,True,{},'mount'),
('18_Коллиматор_отдельно',(-.128,-.13,.203),(-.010,0,.146),.072,True,{},'optic'),
('19_Пятка_без_магазина',(.118,-.073,-.054),(.057,0,.014),.074,False,{'Magazine':1}),
('20_Планка_пропорции_сверху',(-.009,-.038,.36),(-.006,0,.107),.196,True,{}),
('21_Крепление_над_спуском',(-.003,-.33,.098),(-.003,0,.098),.181,True,{}),
('23_Защёлка_закруглённый_профиль',(.045,-.15,.025),(.064,0,.011),.032,False,{},'catch')]
if args.revision=='v07':
    views += [
    ('24_Коллиматор_сбоку',(-.009,-.25,.142),(-.013,0,.142),.071,True,{},'optic'),
    ('25_Коллиматор_спереди',(-.24,0,.147),(-.016,0,.147),.060,True,{},'optic'),
    ('26_Коллиматор_сзади',(.20,-.13,.177),(-.012,0,.143),.070,True,{},'optic'),
    ('27_Скругление_и_низкая_посадка',(-.018,-.105,.170),(-.008,-.009,.123),.064,True,{}),
    ('28_Параллельная_пятка',(.043,-.18,.008),(.052,0,.008),.076,False,{}),
    ('29_Защёлка_сбоку',(.068,-.18,.010),(.068,0,.009),.029,False,{},'catch')]
only=set(args.only.split(',')) if args.only else set()
saved_hide={o.name:o.hide_render for o in bpy.data.objects}
fill_data=bpy.data.lights.new('Inspection | heel fill','AREA');fill_data.energy=.45;fill_data.size=.12
fill=bpy.data.objects.new('Inspection | heel fill',fill_data);S.collection.objects.link(fill)
fill.location=(.065,-.025,-.080);fill.rotation_euler=(Vector((.061,0,.009))-fill.location).to_track_quat('-Z','Y').to_euler();fill.hide_render=True
for view in views:
    name,eye,target,scale,accessories,values,*kind=view
    if only and name.split('_')[0] not in only:continue
    for o in bpy.data.objects:
        if o.name in saved_hide:o.hide_render=saved_hide[o.name]
    pose(Slide=0,Hammer=0,Safety=0,Trigger=0,Magazine=0,MagCatch=0)
    pose(**values);set_accessories(accessories)
    fill.hide_render=name.split('_')[0] not in {'11','12','19','28','29'}
    if not fill.hide_render:bpy.data.objects['Studio | matte charcoal stage'].hide_render=True
    if kind:
        for o in scope:
            if kind[0]=='mount':o.hide_render=not(within(o,mount) and not within(o,optic))
            elif kind[0]=='optic':o.hide_render=not within(o,optic)
            else:o.hide_render=not within(o,bpy.data.objects['MagCatch • pivot'])
    cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;S.camera=cam
    S.render.filepath=str(OUT/'Превью'/((name+'_draft' if args.draft else name)+'.png'))
    bpy.ops.render.render(write_still=True);print('PM_RENDER',name,flush=True)
print('PM_REVIEW_FINISHED',flush=True)
