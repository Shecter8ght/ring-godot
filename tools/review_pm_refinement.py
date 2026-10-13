"""Fresh-file geometry QA and neutral Cycles views for PM v06."""
from pathlib import Path
import argparse, hashlib, json, math, struct, sys
import bpy, bmesh, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap=argparse.ArgumentParser();ap.add_argument('--draft',action='store_true');ap.add_argument('--only',default='');ap.add_argument('--audit-only',action='store_true');ap.add_argument('--revision',default='v06',choices=['v06','v07','v08','v09','v10','v11'])
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement';OUT=ROOT/('review_'+args.revision)
if args.revision in {'v09','v10','v11'}:
    import addon_utils
    bpy.context.preferences.use_preferences_save=False
    addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
    bpy.ops.wm.open_mainfile(filepath=bpy.data.filepath)
S=bpy.context.scene;rig=bpy.data.objects['PM_CONTROLS • select me'];S.frame_set(1);bpy.context.view_layer.update()
action=rig.animation_data.action if rig.animation_data else None
rig.animation_data_clear()
for k in ('Slide','Hammer','Trigger','Safety','Magazine','Suppressor','MagCatch'):rig[k]=0.0
if args.revision in {'v10','v11'}:rig['SlideStop']=0.0
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
        if o.type not in {'MESH','CURVE','FONT'} or o.get('PM engraving helper') or o.get('PM geometry helper'):continue
        eo=o.evaluated_get(dg);m=eo.to_mesh()
        if not m or not m.vertices:eo.to_mesh_clear();continue
        v=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',v);v=v.reshape(-1,3)
        matrix=np.asarray(eo.matrix_world,dtype=np.float32);v=v@matrix[:3,:3].T+matrix[:3,3]
        lo=np.minimum(lo,v.min(axis=0));hi=np.maximum(hi,v.max(axis=0));eo.to_mesh_clear()
    return dict(min_mm=(lo*1000).tolist(),max_mm=(hi*1000).tolist(),dimensions_mm=((hi-lo)*1000).tolist())
mount=bpy.data.objects['PM_OpticMount • asset root'];optic=bpy.data.objects['PM_ReflexSight • asset root']
props=[o for o in bpy.data.objects if o.type=='EMPTY' and o.name.startswith('Animation |')]
scope=[o for o in bpy.data.objects if within(o,rig) and o.type in {'MESH','CURVE','FONT'} and not o.get('PM engraving helper') and not o.get('PM geometry helper') and not within(o,bpy.data.objects['Suppressor • removal']) and not any(within(o,p) for p in props) and not o.name.startswith(('Animation','Reference','Safety wear'))]
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
if args.revision in {'v10','v11'}:report['reference_proportions']['pass']=.30<report['reference_proportions']['rail_length_ratio']<.36 and 18<rail['dimensions_mm'][1]<22 and report['reference_proportions']['mount_screw_count']==2
names=[o.name for o in scope if o.type=='MESH' and o.name.startswith(('Frame | traced','Slide | continuous','Hammer |','Safety | tapered','Safety | beveled','Safety | prominent','Safety | ribbed','Slide catch |','Trigger |','Barrel | stepped','Rear sight |','Extractor |','MagCatch |','Lanyard | molded','Grip checkering |','Mount |','Reflex |','Magazine | aligned','Magazine | straight','Magazine | inset floorplate'))]
dg=bpy.context.evaluated_depsgraph_get()
if args.revision in {'v10','v11'}:names.append('Bakelite | one-piece rounded grip')
for name in names:
    o=bpy.data.objects[name];eo=o.evaluated_get(dg);m=eo.to_mesh();bm=bmesh.new();bm.from_mesh(m)
    row=dict(vertices=len(bm.verts),faces=len(bm.faces),boundary=sum(e.is_boundary for e in bm.edges),overfull=sum(len(e.link_faces)>2 for e in bm.edges),wire=sum(e.is_wire for e in bm.edges),zero_area=sum(f.calc_area()<1e-14 for f in bm.faces))
    row['closed_pass']=row['boundary']==row['overfull']==row['wire']==row['zero_area']==0
    report['geometry'][name]=row;bm.free();eo.to_mesh_clear()
    print('PM_TOPOLOGY',name,row,flush=True)
if args.revision in {'v08','v09','v10','v11'}:
    manifest=json.loads((OUT/'Проверки/revision_manifest.json').read_text(encoding='utf-8'));unchanged={}
    for name,expected in manifest['unchanged_fingerprints'].items():
        o=bpy.data.objects[name];h=hashlib.sha256()
        for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
        for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
        h.update(str(tuple(tuple(row) for row in o.matrix_local)).encode());h.update((o.parent.name if o.parent else '').encode())
        unchanged[name]=h.hexdigest()==expected
    markings=[o for o in bpy.data.objects if o.type=='FONT' and within(o,optic) and o.name.startswith('Reflex | Marking ')]
    mark_report=[dict(object=o.name,text=o.data.body,font_packed=bool(o.data.font.packed_file)) for o in markings]
    report['k1']=dict(unchanged=unchanged,markings=mark_report,brand=optic['Brand'],model=optic['Model'],
        pass_k1=all(unchanged.values()) and len(markings)>=10 and all(x['font_packed'] for x in mark_report))
if args.revision in {'v09','v10','v11'}:
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from pm_engraving_geometry import engraving_report,cache_engraving_preview,paint_fill_report
    report['engraving']=engraving_report(json.loads((OUT/'Проверки/engraving.json').read_text(encoding='utf-8')))
    report['paint_fill']=paint_fill_report()
    native_pass=all(r['closed_pass'] for r in report['geometry'].values()) and report['k1']['pass_k1'] and report['engraving']['pass_engraving'] and len(report['engraving']['markings'])==25 and report['paint_fill']['pass_paint']
    if not native_pass:
        report['audit_pass']=False
        (OUT/'Проверки/fresh_file_geometry.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        raise RuntimeError('Saved native engraving/mesh/paint QA failed before motion checks')
    # Native operands, depths, source meshes and topology have been inspected.
    # Freeze evaluated cuts in this unsaved process for transform-only checks.
    report['unsaved_inspection_cache']=cache_engraving_preview()
control_keys=('Slide','Hammer','Safety','Trigger','Magazine','MagCatch')+(('SlideStop',) if args.revision in {'v10','v11'} else ())
for key in control_keys:
    for value in (0,.5,1):
        pose(**{key:value})
        root={'Slide':'Slide • translation','Hammer':'Hammer • pivot','Safety':'Safety • pivot','Trigger':'Trigger • pivot','Magazine':'Magazine • extraction','MagCatch':'MagCatch • pivot','SlideStop':'SlideStop • pivot'}[key]
        o=bpy.data.objects[root].evaluated_get(bpy.context.evaluated_depsgraph_get())
        report['poses'].append(dict(control=key,value=value,world_location_mm=[v*1000 for v in o.matrix_world.translation],world_rotation=[v for v in o.matrix_world.to_euler()],finite=all(math.isfinite(v) for row in o.matrix_world for v in row)))
    pose(**{key:0})
motion={}
for key in control_keys:
    rows=[r for r in report['poses'] if r['control']==key];a=rows[0];b=rows[-1]
    delta=[b['world_location_mm'][i]-a['world_location_mm'][i] for i in range(3)]
    angle=b['world_rotation'][1]-a['world_rotation'][1]
    passed=(25<delta[0]<45) if key=='Slide' else (delta[2]<-65) if key=='Magazine' else (angle<-.15) if key=='Trigger' else (angle>.1)
    if args.revision in {'v10','v11'} and key in {'MagCatch','SlideStop'}:passed=angle<-.05
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
if args.revision in {'v07','v08','v09','v10','v11'}:
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
    if args.revision in {'v10','v11'}:report['owner_corrections']['pass_corrections']=1.2<gap<2.0 and 6<rail['dimensions_mm'][2]<10 and normal_dot>.999999 and (optic_anchor-expected_anchor).length<1e-6
report['audit_pass']=all(r['closed_pass'] for r in report['geometry'].values()) and all(r['front_clear'] and r['rear_clear'] for r in samples) and all(r['clear'] for r in passage) and all(r['finite'] for r in report['poses']) and report['reference_proportions']['pass'] and all(r['pass_motion'] for r in motion.values())
if args.revision in {'v07','v08','v09','v10','v11'}:report['audit_pass']=report['audit_pass'] and report['owner_corrections']['pass_corrections']
if args.revision in {'v08','v09','v10','v11'}:report['audit_pass']=report['audit_pass'] and report['k1']['pass_k1']
if args.revision in {'v09','v10','v11'}:
    report['audit_pass']=report['audit_pass'] and report['engraving']['pass_engraving']
    report['audit_pass']=report['audit_pass'] and len(report['engraving']['markings'])==25
    report['audit_pass']=report['audit_pass'] and report['paint_fill']['pass_paint']
if args.revision=='v10':
    from check_pm_controls_v10 import inspect_controls
    report['controls_v10']=inspect_controls(json.loads((OUT/'Проверки/controls_geometry.json').read_text(encoding='utf-8')))
    report['audit_pass']=report['audit_pass'] and report['controls_v10']['pass_controls']
    from check_pm_body_v10 import inspect_body
    report['body_v10']=inspect_body(json.loads((OUT/'Проверки/body_geometry.json').read_text(encoding='utf-8')))
    report['audit_pass']=report['audit_pass'] and report['body_v10']['pass_body']
if args.revision=='v11':
    from check_pm_surfaces_v11 import inspect_repairs
    report['repairs_v11']=inspect_repairs(json.loads((OUT/'Проверки/repairs_geometry.json').read_text(encoding='utf-8')),json.loads((OUT/'Проверки/controls_geometry.json').read_text(encoding='utf-8')))
    report['audit_pass']=report['audit_pass'] and report['repairs_v11']['pass_repairs']
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
if args.revision in {'v07','v08','v09','v10','v11'}:
    views += [
    ('24_Коллиматор_сбоку',(-.009,-.25,.142),(-.013,0,.142),.071,True,{},'optic'),
    ('25_Коллиматор_спереди',(-.24,0,.147),(-.016,0,.147),.060,True,{},'optic'),
    ('26_Коллиматор_сзади',(.20,-.13,.177),(-.012,0,.143),.070,True,{},'optic'),
    ('27_Скругление_и_низкая_посадка',(-.018,-.105,.170),(-.008,-.009,.123),.064,True,{}),
    ('28_Параллельная_пятка',(.043,-.18,.008),(.052,0,.008),.076,False,{}),
    ('29_Защёлка_сбоку',(.068,-.18,.010),(.068,0,.009),.029,False,{},'catch')]
if args.revision in {'v08','v09','v10','v11'}:
    optic_scales={'18':.085,'24':.078,'25':.075,'26':.080}
    views=[(name,eye,(target[0],target[1],.149),optic_scales[name[:2]],accessories,values,*tail) if name[:2] in optic_scales else (name,eye,target,scale,accessories,values,*tail) for name,eye,target,scale,accessories,values,*tail in views]
    views += [
    ('30_ЗОРИН_справа_маркировка',(-.009,.25,.146),(-.011,0,.148),.073,True,{},'optic'),
    ('31_ЗОРИН_сверху_крышка',(-.011,0,.38),(-.011,0,.146),.066,True,{},'optic')]
if args.revision in {'v09','v10','v11'}:
    views += [
    ('32_Гравировка_ЗОРИН_и_эмблема',(-.0176,-.115,.158),(-.0176,-.01685,.1460),.040,True,{},'engraving'),
    ('33_Гравировка_ВВЕРХ_и_стрелка',(.005,.003,.300),(.005,.003,.146),.022,True,{},'engraving'),
    ('34_Гравировка_3В_крышка',(-.016,0,.300),(-.016,0,.146),.030,True,{},'engraving'),
    ('35_Гравировка_ВПРАВО_и_стрелка',(.013,.120,.147),(.0054,.0165,.1400),.028,True,{},'engraving'),
    ('36_КОРС9_рамка_светлая_эмаль',(.053,-.105,.101),(.053,-.0108,.0928),.032,False,{},'frame-marking'),
    ('37_КОРС9_калибр_и_партия',(.056,.105,.101),(.056,.0108,.0928),.028,False,{},'frame-marking'),
    ('38_КОРС9_буквы_дно_и_сколы',(.060,-.060,.097),(.057,-.0108,.094),.015,False,{},'frame-marking')]
if args.revision in {'v10','v11'}:
    views += [
    ('39_Планка_в_основном_зажиме',(.16,0,.134),(-.008,0,.130),.057,True,{}),
    ('40_Лепесток_задержки_и_прорези',(.010,-.115,.105),(.018,-.014,.092),.035,False,{}),
    ('41_Лепесток_нажат_вниз',(.010,-.115,.105),(.018,-.014,.092),.035,False,{'SlideStop':1}),
    ('42_Фиксатор_упор_под_магазином',(.105,-.09,-.025),(.067,0,.002),.042,False,{}),
    ('43_Фиксатор_к_затыльнику',(.075,-.105,.003),(.068,0,.003),.035,False,{'MagCatch':1,'Magazine':.15}),
    ('44_Предохранитель_и_полная_выемка',(.045,-.12,.136),(.058,-.013,.113),.047,False,{}),
    ('45_Предохранитель_верхняя_поза',(.045,-.12,.136),(.058,-.013,.113),.047,False,{'Safety':1}),
    ('46_Плавный_затыльник_слева',(.135,-.08,.144),(.068,0,.110),.052,False,{}),
    ('47_Плавный_затыльник_справа',(.135,.08,.144),(.068,0,.110),.052,False,{}),
    ('48_Задний_вид_и_пять_пазов',(.17,0,.128),(.070,0,.111),.041,False,{}),
    ('49_Расширения_и_насечки_слева',(.045,-.12,.124),(.031,-.012,.109),.077,False,{}),
    ('50_Расширения_и_насечки_справа',(.045,.12,.124),(.031,.012,.109),.077,False,{}),
    ('51_Тонкие_стенки_накладки',(.040,-.070,.140),(.050,0,.055),.102,False,{},'grip'),
    ('52_Курок_широкие_вырезы',(.115,-.065,.143),(.074,0,.115),.029,False,{'Hammer':.12})]
if args.revision=='v11':
    views=[
      ('53_Рамка_слева_плавный_блик',(.095,-.160,.086),(.056,-.0108,.085),.072,False,{}),
      ('54_Рамка_справа_плавный_блик',(.095,.160,.086),(.060,.0108,.085),.072,False,{}),
      ('55_Планка_единая_поверхность',(.025,-.120,.127),(-.010,0,.126),.077,True,{},'mount'),
      ('56_Предохранитель_горизонтальные_прорези',(.034,-.120,.130),(.057,-.013,.113),.044,False,{}),
      ('57_Скругление_выемки',(.034,-.120,.130),(.057,-.013,.113),.044,False,{'Safety':1}),
      ('58_Курок_радиальные_вырезы',(.130,-.090,.165),(.074,0,.115),.039,False,{}),
      ('59_Глубокие_шлицы_крепления',(-.035,-.120,.137),(-.016,-.015,.131),.060,True,{}),
      ('60_Шлиц_затыльника',(.145,-.075,.054),(.075,0,.040),.026,False,{}),
      ('61_Шлицы_верхних_винтов',(-.012,-.034,.230),(-.003,0,.145),.068,True,{},'optic')]
only=set(args.only.split(',')) if args.only else set()
saved_hide={o.name:o.hide_render for o in bpy.data.objects}
fill_data=bpy.data.lights.new('Inspection | heel fill','AREA');fill_data.energy=.45;fill_data.size=.12
fill=bpy.data.objects.new('Inspection | heel fill',fill_data);S.collection.objects.link(fill)
fill.location=(.065,-.025,-.080);fill.rotation_euler=(Vector((.061,0,.009))-fill.location).to_track_quat('-Z','Y').to_euler();fill.hide_render=True
for view in views:
    name,eye,target,scale,accessories,values,*kind=view
    if only and name.split('_')[0] not in only:continue
    macro=(kind and kind[0] in {'engraving','frame-marking'}) or (args.revision in {'v10','v11'} and int(name[:2])>=39)
    S.render.resolution_x=1100 if args.draft else (2400 if macro else 1800)
    S.render.resolution_y=760 if args.draft else (1600 if macro else 1240)
    S.cycles.samples=24 if args.draft else (128 if macro else 96)
    for o in bpy.data.objects:
        if o.name in saved_hide:o.hide_render=saved_hide[o.name]
    pose(Slide=0,Hammer=0,Safety=0,Trigger=0,Magazine=0,MagCatch=0)
    if args.revision in {'v10','v11'}:pose(SlideStop=0)
    pose(**values);set_accessories(accessories)
    fill.hide_render=name.split('_')[0] not in {'11','12','19','28','29','42','43'}
    if not fill.hide_render:bpy.data.objects['Studio | matte charcoal stage'].hide_render=True
    if kind:
        for o in scope:
            if kind[0]=='mount':o.hide_render=not(within(o,mount) and not within(o,optic))
            elif kind[0] in {'optic','engraving'}:o.hide_render=not within(o,optic)
            elif kind[0]=='frame-marking':o.hide_render=o not in base
            elif kind[0]=='grip':o.hide_render=not o.name.startswith(('Bakelite |','Grip checkering |','Backstrap |'))
            else:o.hide_render=not within(o,bpy.data.objects['MagCatch • pivot'])
    cam.location=eye;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;S.camera=cam
    if args.revision in {'v08','v09','v10','v11'} and ((kind and kind[0] in {'optic','mount'}) or name[:2] in {'01','02','03','04','14','15','16'}):
        bpy.context.view_layer.update();inv=cam.matrix_world.inverted();dg=bpy.context.evaluated_depsgraph_get();coords=[]
        for o in scope:
            if o.hide_render:continue
            eo=o.evaluated_get(dg)
            coords.extend(inv@eo.matrix_world@Vector(p) for p in eo.bound_box)
        lo=Vector((min(p.x for p in coords),min(p.y for p in coords),0));hi=Vector((max(p.x for p in coords),max(p.y for p in coords),0))
        aspect=S.render.resolution_x/S.render.resolution_y
        cam.data.ortho_scale=max(scale,max(hi.x-lo.x,(hi.y-lo.y)*aspect)*1.12)
        cam.location+=cam.matrix_world.to_3x3()@((lo+hi)/2)
    S.render.filepath=str(OUT/'Превью'/((name+'_draft' if args.draft else name)+'.png'))
    bpy.ops.render.render(write_still=True);print('PM_RENDER',name,flush=True)
print('PM_REVIEW_FINISHED',flush=True)
