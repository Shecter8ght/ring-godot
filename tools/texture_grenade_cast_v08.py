"""Нативный UCUPaint v08 на явно принятой округлённой форме v07.
Литьё и осевшие частицы редактируются отдельно. Фото — только референсы.
Игровых механик и импорта в движок здесь нет.
"""
import hashlib, importlib.util, json, math, os, shutil, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'_asset_src/grenade_codex'
OUT=BASE/'texture_v08'
SOURCE=BASE/'geometry_review_v07/Grenade_MkII_geometry_review_v07.blend'
MASTER=OUT/'Grenade_MkII_UCUPaint_v08.blend'
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build-pilot'
FINAL=MODE in {'build','render','inspect','audit'}
SIZE=8192 if FINAL else 4096
EXTENT=160 if FINAL else 80

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
T=module(HERE/'texture_grenade_codex.py','grenade_v08_base')
P=T.P;S=T.S
P.TEXTURES=OUT/'textures/authoring'
L=T.L;nm=T.nm;attribute=T.attribute

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def mask(layer,file,label,uv=None,extent=160):
    path=P.TEXTURES/file
    im=bpy.data.images.load(str(path),check_existing=True);im.colorspace_settings.name='Non-Color'
    m=P.U.Mask.add_new_mask(layer,label,'IMAGE','UV' if uv else 'Object',uv or P.UV,image=im)
    node=P.U.common.get_mask_tree(m).nodes[m.source]
    if uv:node.extension='CLIP'
    else:
        node.projection='BOX';node.projection_blend=.12;m.scale=(1000/extent,)*3;m.translation=(.37,.52,.19)
    return m

def height(tree,name,file,distance,extent=160,amount=1):
    im=bpy.data.images.load(str(P.TEXTURES/file),check_existing=True);im.colorspace_settings.name='Non-Color'
    tree.yp.halt_update=True
    l=P.U.Layer.add_new_layer(tree,name,'IMAGE',-1,'MIX','OVERLAY','BUMP_MAP','Object',P.UV,image=im,use_designated_idx=True,designated_index=0)
    tree.yp.halt_update=False
    src=P.U.common.get_layer_source(l);src.projection='BOX';src.projection_blend=.12
    l.scale=(1000/extent,)*3;l.translation=(.37,.52,.19)
    for root,ch in zip(tree.yp.channels,l.channels):
        ch.enable=root.type=='NORMAL';ch.override=False
        if ch.enable:
            P.H.sync_property(P.U,ch,'bump_distance',distance);P.H.sync_property(P.U,ch,'bump_midlevel',.5)
    P.H.sync_property(P.U,l,'intensity_value',amount)
    return l

def prep_coordinates():
    T.authoring_coords()
    # Маски контакта и укрытых мест плавно меняются по поверхности принятого литья.
    ob=bpy.data.objects['GrenadeBody'];me=ob.data
    co=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',co);co=co.reshape(-1,3)
    r=np.hypot(co[:-1,0],co[:-1,1]).reshape(641,512)
    local=r.copy()
    for _ in range(12):
        local=(np.roll(local,2,axis=1)+np.roll(local,-2,axis=1)+np.vstack((local[:2],local[:-2]))+np.vstack((local[2:],local[-2:]))+local*2)/6
    convex=np.clip((r-local-.000010)/.00022,0,1)
    recessed=np.clip((np.percentile(r,85,axis=1)[:,None]-r-.00012)/.0016,0,1)
    z=co[:,2];reach=np.r_[1-recessed.ravel(),0]*np.exp(-((z-.043)/.034)**4)
    contact=np.r_[convex.ravel(),0]*.80+reach*.20
    normals=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('normal',normals);normals=normals.reshape(-1,3)
    dust=np.clip((normals[:,2]-.08)/.75,0,1)*(.30+np.r_[recessed.ravel(),0]*.7)
    for name,arr in [('Wear_Contact',contact),('Wear_Recess',np.r_[recessed.ravel(),0]),('Wear_Dust',dust),('Wear_Reach',reach)]:
        old=me.color_attributes.get(name)
        if old:me.color_attributes.remove(old)
        att=me.color_attributes.new(name=name,type='FLOAT_COLOR',domain='POINT')
        rgba=np.ones((len(co),4),np.float32);rgba[:,:3]=arr[:,None];att.data.foreach_set('color',rgba.ravel())
    # UV для редактирования: цилиндр и отдельный нижний диск; координаты сетки сохраняются.
    ids=np.empty(len(me.loops),np.int32);me.loops.foreach_get('vertex_index',ids)
    pts=co[ids]; uv=np.column_stack(((np.arctan2(pts[:,1],pts[:,0])%(2*math.pi))/(2*math.pi),.06+.94*pts[:,2]/.086)).astype(np.float32)
    for face in me.polygons:
        a=face.loop_start;b=a+face.loop_total
        if face.loop_total==4:
            if uv[a:b,0].max()-uv[a:b,0].min()>.5:uv[a:b,0]=np.where(uv[a:b,0]<.5,uv[a:b,0]+1,uv[a:b,0])
        else:uv[a:b]=pts[a:b,:2]/.050+(.5,.03)
    uv[:,1]=np.clip(uv[:,1],0,1)
    me.uv_layers['UVMap'].data.foreach_set('uv',uv.ravel());me.uv_layers.active=me.uv_layers['UVMap'];me.uv_layers['UVMap'].active_render=True
    me.update()

def deposits(tree,body=False,amount=.65):
    l=L(tree,'70 • Dark compacted soil inside actual recesses',(.042,.030,.014),0,.86,amount=amount)
    attribute(l,'Wear_Recess','Geometry shelter')
    nm(l,'Interrupted packed soil, 1 mm clusters',950,.32,.57,(.021,.050,.024))
    l=L(tree,'72 • Dry dust film on upward sheltered ledges',(.13,.10,.058),0,.78,amount=.27)
    attribute(l,'Wear_Dust','Upward deposition')
    nm(l,'Patchy thin dust',1200,.34,.63,(.020,.013,.031))
    l=L(tree,'74 • Individual gritty particles trapped in grooves',(.14,.098,.047),0,.89,height=.92,normal_distance=.00012,amount=.92)
    attribute(l,'Wear_Recess','Grains remain in sheltered grooves')
    mask(l,f'deposit_grains_{SIZE//1024}k.png','Separate angular 0.05-0.20 mm grains',extent=EXTENT)
    # Рельеф частиц ограничен их отпечатком и укрытыми участками поверхности.
    l=L(tree,'76 • Sparse light dust particles on ledges',(.22,.18,.11),0,.85,height=.9,normal_distance=.000055,amount=.90)
    attribute(l,'Wear_Dust','Settled individual grains')
    mask(l,f'deposit_grains_{SIZE//1024}k.png','Individual small dust grains',extent=EXTENT)

def body():
    t=T.create_stack('UCUPaint_v08_CastBody','v08 • painted iron casting, wear and deposits',[bpy.data.objects['GrenadeBody']],(.064,.070,.038),0,.40)
    L(t,'00 • Olive enamel over rough iron',(.064,.070,.038),0,.40)
    height(t,'03 • Casting flows, raised nodules and negative cavities',f'casting_relief_{SIZE//1024}k_16bit.png',.0008,EXTENT)
    L(t,'04 • Fine raised paint grain, 7 microns',height='source',source_type='NOISE',scale=18000,normal_distance=.000007)
    l=L(t,'06 • Uneven but restrained enamel hue',(.038,.042,.020),0,.43,amount=.24);nm(l,'Subtle coating variation',1000,.22,.72,(.030,.017,.021))
    l=L(t,'07 • Roughness changes across cast microstructure',rough=.50,amount=.30);nm(l,'Submillimetre finish differences',6500)
    l=L(t,'10 • Saturated yellow painted neck band',(.80,.58,.008),0,.38);mask(l,'neck_band_8kx4k.png','4.1 mm neck band','BandProjection')
    l=L(t,'11 • Paint missing from portions of yellow band',(.047,.050,.026),0,.43,amount=.97);mask(l,'neck_band_8kx4k.png','Only yellow band','BandProjection');nm(l,'Small fractured yellow-paint islands',2800,.48,.63,(.13,.06,.02))
    l=L(t,'12 • Broken band at strongest rubbing',(.14,.15,.10),1,.40);mask(l,'neck_band_8kx4k.png','Band limit','BandProjection');mask(l,f'contact_breaks_{SIZE//1024}k.png','Irregular worn-off patches',extent=EXTENT)
    l=L(t,'13 • Thin muted red seal paint',(.28,.010,.011),0,.42);mask(l,'red_neck_seal_8kx4k.png','1.2 mm red seal line','BandProjection')
    l=L(t,'20 • Worn paint revealing actual dark iron',(.26,.28,.22),1,.40,height=0,normal_distance=.000025)
    mask(l,f'contact_breaks_{SIZE//1024}k.png','Irregular 1-5 mm loss patches',extent=EXTENT);attribute(l,'Wear_Reach','Exposed grip; grooves retain coating');nm(l,'Fine ragged enamel-loss boundary',10500,.24,.39,(.033,.015,.044))
    l=L(t,'21 • Exposed substrate keeps its fine cast grain',height='source',source_type='NOISE',scale=11000,normal_distance=.000021,amount=.80);mask(l,f'contact_breaks_{SIZE//1024}k.png','Only original iron within coating breaks',extent=EXTENT);attribute(l,'Wear_Reach','Raised contact faces')
    l=L(t,'22 • Small discontinuous bare spots on convex ridges',(.17,.18,.135),1,.37,height=0,normal_distance=.000020,amount=.85)
    attribute(l,'Wear_Contact','Smoothed convex handling contacts');nm(l,'Small broken edge contacts',4300,.49,.66,(.011,.020,.014))
    l=L(t,'24 • Fine scratches through coating',(.19,.20,.15),1,.35,height=0,normal_distance=.000012,amount=.72)
    mask(l,'micro_scratches_8k.png','20-75 micron hairlines');attribute(l,'Wear_Reach','Gripped protrusions')
    l=L(t,'26 • Contact burnishing without paint removal',rough=.27,amount=.52);attribute(l,'Wear_Contact','Local convex rubbing');nm(l,'Limited polished areas',1100,.35,.58)
    l=L(t,'30 • Tiny dark oxide at a few paint breaks',(.069,.025,.008),0,.70,height='source',source_type='NOISE',scale=8400,normal_distance=.000012,amount=.40)
    mask(l,f'contact_breaks_{SIZE//1024}k.png','Only unprotected iron',extent=EXTENT);nm(l,'Sparse oxidation',3600,.52,.67)
    deposits(t,True,.64)
    return t

def metal(kind):
    if kind=='head':names=['FuzeCasting','BottomPlug'];color=(.26,.28,.24);rough=.39;label='aged cast head'
    elif kind=='lever':names=['SafetyLever'];color=(.23,.25,.205);rough=.35;label='pressed steel lever'
    else:names=['PinEyelet','PullRing','SafetyPin'];color=(.23,.25,.19);rough=.32;label='drawn steel wire'
    t=T.create_stack('UCUPaint_v08_'+kind,'v08 • '+label,[bpy.data.objects[n] for n in names],color,1,rough)
    L(t,'00 • Aged silver metal substrate',color,1,rough)
    # Лицензированные карты добавляются как настоящие IMAGE-слои UCUPaint.
    T.cc0_layer(t,'02 • CC0 fine metal reflectance variation','Metal049C','Color','Color',.12)
    T.cc0_layer(t,'03 • CC0 physical machining roughness','Metal009' if kind!='head' else 'Metal049C','Roughness','Roughness',.21,extent_mm=110)
    height(t,'04 • Shallow manufacturing relief and irregular raised grains',f'casting_relief_{SIZE//1024}k_16bit.png',.00026 if kind=='head' else .00006 if kind=='lever' else .000025,EXTENT)
    L(t,'05 • Fine metal tooth',height='source',source_type='NOISE',scale=15000,normal_distance=.000010 if kind=='head' else .000005)
    l=L(t,'10 • Uneven grey-green oxidation',(.082,.095,.064),.68,.57,amount=.22);nm(l,'Small oxide and passivation patches',1500,.25,.72,(.022,.003,.031))
    l=L(t,'12 • Restrained rusty flecks on exposed metal',(.07,.026,.008),.20,.71,amount=.48)
    ox=mask(l,str(BASE/'textures/cc0_sources/Metal063/Metal063_8K-PNG_Metalness.png'),'CC0 photo-derived oxide specks');P.mask_ramp(ox,.15,.85,invert=True);nm(l,'Sparse local oxide',2300,.47,.62)
    l=L(t,'20 • Contact-polished edges',(.30,.32,.255),1,.27,amount=.62);P.edge_mask(l,.00028,.020,.075);nm(l,'Interrupted contacts',3200,.38,.65)
    l=L(t,'22 • Hairline handling abrasion',rough=.29,height=0,normal_distance=.000007,amount=.70);mask(l,'micro_scratches_8k.png','Physically fine scratches')
    if kind=='lever':
        l=L(t,'28 • Darker aged finish on lower lever',(.047,.060,.032),.65,.43,amount=.84);attribute(l,'Wear_LowerLever','Darkened lower lever')
        l=L(t,'40 • Sun icon and exact Cyrillic СЛНШК',(.009,.010,.007),0,.57,amount=.94);mask(l,'sun_slnshk_4kx2k.png','Original project stamp','StampProjection');attribute(l,'Wear_StampTop','Top plate only')
    if kind!='wire':deposits(t,False,.33)
    return t

def pack():
    rows=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:continue
        path=Path(bpy.path.abspath(im.filepath)) if im.filepath else None
        if path and path.is_file():
            data=path.read_bytes();sub='authoring' if path.parent==P.TEXTURES else 'reference' if 'reference' in str(path) else 'cc0_sources'
        elif im.packed_file:data=bytes(im.packed_file.data);sub='reference'
        else:raise RuntimeError('Image without stored data: '+im.name)
        name=path.name if path and path.is_file() else im.name+'.png'
        dest=OUT/'textures'/sub/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():dest.write_bytes(data)
        assert sha(dest)==hashlib.sha256(data).hexdigest()
        if not im.packed_file:im.pack()
        assert hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==sha(dest)
        im.filepath='//'+dest.relative_to(OUT).as_posix()
        header=data[:24];size=[int.from_bytes(header[16:20],'big'),int.from_bytes(header[20:24],'big')] if header[:8]==b'\x89PNG\r\n\x1a\n' else list(im.size)
        rows.append({'name':im.name,'file':im.filepath,'size':size,'color_space':im.colorspace_settings.name,'sha256':sha(dest)})
        im.buffers_free()
    (OUT/'checks/image_manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')

def setup():
    S.setup_studio((0,0,0));sc=bpy.context.scene
    sc.cycles.samples=192;sc.cycles.use_denoising=False;sc.cycles.adaptive_threshold=.005
    sc.render.image_settings.color_mode='RGB';sc.render.image_settings.color_depth='16'
    sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.16
    sc.view_settings.look='AgX - Medium High Contrast';sc.view_settings.exposure=0
    key=bpy.data.objects['Key softbox'];key.location=(-.14,-.12,.18);key.data.size=.040;key.data.energy=1.2;key.data.color=(1,.96,.90);S.aim(key,(0,0,.048))
    bpy.data.objects['Fill softbox'].data.energy=.20
    bpy.data.objects['Rim strip'].data.energy=.65

def build():
    P.native();approval=json.loads((OUT/'checks/geometry_approved_v07.json').read_text(encoding='utf-8-sig'))
    assert approval['status']=='explicitly_approved_by_owner' and sha(SOURCE)==approval['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update()
    # Материалы исходника остаются отдельными архивными datablock.
    for mat in bpy.data.materials:mat.use_fake_user=True
    for name in ['micro_scratches_8k.png','neck_band_8kx4k.png','red_neck_seal_8kx4k.png','sun_slnshk_4kx2k.png']:
        dst=P.TEXTURES/name
        if not dst.exists():shutil.copy2(BASE/'textures/authoring'/name,dst)
    # Источник рисунка оксидов сохраняет проверенную исходную лицензию.
    prep_coordinates()
    trees=[]
    for func in [body,lambda:metal('head'),lambda:metal('lever'),lambda:metal('wire')]:
        tree=func();P.H.reconnect(P.U,tree);trees.append(tree);print('STACK_READY',tree.name,len(tree.yp.layers),flush=True)
    setup();sc.camera.location=(.10,-.17,.09);S.aim(sc.camera,(.002,-.005,.043));sc.camera.data.ortho_scale=.078
    text=bpy.data.texts.new('00 • MATERIAL V08 NOTES');text.write('Owner accepted rounded geometry v07. Native UCUPaint: casting nodules and pits, coating, bare iron, burnishing, scratches, oxide, compact soil, dust film and discrete grains. Manufacturing height does not alter saved mesh coordinates. Sun + СЛНШК is original project artwork. v06 sources retained in the previous master.\n')
    pack();sc.render.filepath='//previews/01_cast_raking.png'
    file=MASTER if FINAL else OUT/'material_pilot_v08.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(file),relative_remap=False,compress=True)
    (OUT/'checks/build.json').write_text(json.dumps({'source':str(SOURCE),'source_sha256':approval['sha256'],'file':str(file),'native_stacks':[{'name':t.name,'layers':len(t.yp.layers)} for t in trees],'original_meshes':T.NAMES,'height_span_mm':.8,'grain_diameter_mm':[.046,.20],'mode':MODE},ensure_ascii=False,indent=2),encoding='utf8')
    print('V08_SAVED',file,flush=True)

def render():
    P.native();bpy.ops.wm.open_mainfile(filepath=str(MASTER if FINAL else OUT/'material_pilot_v08.blend'))
    setup();sc=bpy.context.scene;sc.render.resolution_x=1800;sc.render.resolution_y=1800
    sc.camera.location=(.10,-.17,.09);S.aim(sc.camera,(.002,-.005,.043));sc.camera.data.ortho_scale=.065
    for label,pos in [('01_cast_raking',(-.14,-.12,.18)),('02_cast_reverse_raking',(.13,-.14,.078))]:
        key=bpy.data.objects['Key softbox'];key.location=pos;S.aim(key,(0,0,.045))
        sc.render.filepath=str(OUT/'previews'/f'{label}.png');bpy.ops.render.render(write_still=True);print('PROOF_RENDER_OK',label,flush=True)
    key.location=(-.14,-.12,.18);S.aim(key,(0,0,.048))
    sc.camera.location=(.085,-.15,.182);S.aim(sc.camera,(.002,0,.093));sc.camera.data.ortho_scale=.064
    sc.render.filepath=str(OUT/'previews/03_metal_and_band.png');bpy.ops.render.render(write_still=True)
    sc.camera.location=(.17,-.28,.18);S.aim(sc.camera,(0,0,.057));sc.camera.data.ortho_scale=.158
    sc.render.resolution_x=1500;sc.render.resolution_y=1900;sc.render.filepath=str(OUT/'previews/04_overall.png');bpy.ops.render.render(write_still=True)

if __name__=='__main__':
    if MODE.startswith('build'):build()
    elif MODE.startswith('render'):render()





