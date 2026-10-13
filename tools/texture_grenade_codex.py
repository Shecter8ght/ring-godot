"""Native UCUPaint authoring and a purely visual pin/lever rig on a saved Mk II."""
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / '_asset_src/grenade_codex'
SOURCE = Path('E:/Models Blender/From Scenario/Grenade/Grenade.blend')
MASTER = Path(os.environ.get('GRENADE_DELIVERY_FILE', str(OUT / 'Grenade_MkII_UCUPaint_Codex_v06.blend')))
GEOMETRY = Path('E:/Models Blender/From Scenario/Grenade/Codex_Geometry_v05/Grenade_MkII_geometry_review_v05.blend')
MODE = sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build'


def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P=module(HERE/'texture_flare_pistol_codex.py','grenade_native_helpers')
P.UV='UVMap'
P.TEXTURES=OUT/'textures/authoring'
S=module(HERE/'grenade_codex_blender.py','grenade_studio')
NAMES=['BottomPlug','FuzeCasting','GrenadeBody','SafetyLever','PinEyelet','PullRing','SafetyPin']


def L(tree,name,color=None,metal=None,rough=None,height=None,**kw):
    return P.layer(tree,name,color,metal,rough,height,**kw)


def nm(l,name,scale,lo=None,hi=None,offset=(0,0,0)):
    return P.noise_mask(l,name,scale,lo,hi,offset)


def attribute(l,name,label):
    return P.U.Mask.add_new_mask(l,label,'VCOL','Object',P.UV,vcol_name=name)


def imask(l,file,label,uv=None,offset=(.5,.5,.15)):
    im=bpy.data.images.load(str(P.TEXTURES/file),check_existing=True)
    im.colorspace_settings.name='Non-Color'
    m=P.U.Mask.add_new_mask(l,label,'IMAGE','UV' if uv else 'Object',uv or P.UV,image=im)
    src=P.U.common.get_mask_tree(m).nodes[m.source]
    if uv:
        src.extension='CLIP'
    else:
        src.projection='BOX'
        src.projection_blend=.18
        m.scale=(6.25,6.25,6.25)
        m.translation=offset
    return m


def create_stack(name,label,objects,color,metal,rough):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    for ob in objects:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    t,_=P.make_stack(mat.name,label,color,metal,rough)
    return t


def image_height(tree,name,file,distance,amount=1):
    image=bpy.data.images.load(str(P.TEXTURES/file),check_existing=True)
    image.colorspace_settings.name='Non-Color'
    tree.yp.halt_update=True
    layer=P.U.Layer.add_new_layer(tree,name,'IMAGE',-1,'MIX','OVERLAY','BUMP_MAP',
                                 'Object',P.UV,image=image,use_designated_idx=True,designated_index=0)
    tree.yp.halt_update=False
    source=P.U.common.get_layer_source(layer)
    source.projection='BOX'
    source.projection_blend=.18
    layer.scale=(6.25,6.25,6.25)
    layer.translation=(.5,.5,.15)
    for root,ch in zip(tree.yp.channels,layer.channels):
        ch.enable=root.type=='NORMAL'
        ch.override=False
        if ch.enable:
            P.H.sync_property(P.U,ch,'bump_distance',distance)
            P.H.sync_property(P.U,ch,'bump_midlevel',.5)
    P.H.sync_property(P.U,layer,'intensity_value',amount)
    return layer


def cc0_layer(tree,name,asset,map_name,channel,amount=.35,extent_mm=160,distance=.000025):
    """Actual IMAGE layer in native UCUPaint; source remains packed and editable."""
    path=OUT/'textures/cc0_sources'/asset/f'{asset}_8K-PNG_{map_name}.png'
    image=bpy.data.images.load(str(path),check_existing=True)
    image.colorspace_settings.name='sRGB' if channel=='Color' else 'Non-Color'
    tree.yp.halt_update=True
    layer=P.U.Layer.add_new_layer(tree,name,'IMAGE',-1,'MIX','OVERLAY','BUMP_MAP',
                                 'Object',P.UV,image=image,use_designated_idx=True,designated_index=0)
    tree.yp.halt_update=False
    source=P.U.common.get_layer_source(layer)
    source.projection='BOX'
    source.projection_blend=.16
    layer.scale=(1000/extent_mm,)*3
    layer.translation=(.5,.5,.15)
    for root,ch in zip(tree.yp.channels,layer.channels):
        ch.enable=root.name==channel
        ch.override=False
        if ch.enable and root.type=='NORMAL':
            P.H.sync_property(P.U,ch,'bump_distance',distance)
            P.H.sync_property(P.U,ch,'bump_midlevel',.5)
    P.H.sync_property(P.U,layer,'intensity_value',amount)
    return layer


def cc0_oxide_mask(layer):
    mask=imask(layer,'../cc0_sources/Metal063/Metal063_8K-PNG_Metalness.png','CC0 photo-derived oxide specks')
    P.mask_ramp(mask,.15,.85,invert=True)
    return mask


def reparent(ob,parent):
    mw=ob.matrix_world.copy()
    ob.parent=parent
    ob.matrix_parent_inverse=parent.matrix_world.inverted()
    ob.matrix_world=mw


def driver(ob,path,index,expression,root,variables):
    fc=ob.driver_add(path,index)
    fc.driver.expression=expression
    for name,prop in variables:
        v=fc.driver.variables.new()
        v.name=name
        v.type='SINGLE_PROP'
        v.targets[0].id=root
        v.targets[0].data_path='["'+prop+'"]'


def prepare_rig():
    root=bpy.data.objects['MK2_Grenade']
    root['source_translation']=list(root.location)
    root.location=(0,0,0)
    root.name='CTRL_Grenade'
    bpy.context.view_layer.update()
    # Keep every mesh vertex, face, normal and source UV; change ownership only.
    mapping={}
    for i,name in enumerate(NAMES):
        old='Cube Claude Opus 5.5 3D'+(f'.{i:03}' if i else '')
        ob=bpy.data.objects[old]
        mapping[name]=old
        ob['source_object']=old
        ob.name=name
    root['pin_pull']=0.0
    root['lever_open']=0.0
    root.id_properties_ui('pin_pull').update(min=0,max=1,soft_min=0,soft_max=1,
        description='Visual prop only: pin and ring slide together; 0 assembled, 1 separate')
    root.id_properties_ui('lever_open').update(min=0,max=1,soft_min=0,soft_max=1,
        description='Visual prop only: outward lever pose; gated by pin_pull, no firing simulation')
    root.empty_display_type='CIRCLE'
    root.empty_display_size=.035
    ctrl=bpy.data.objects.new('CTRL_PinAssembly',None)
    bpy.context.scene.collection.objects.link(ctrl)
    ctrl.parent=root
    ctrl.location=(0,0,.100)
    ctrl.empty_display_size=.009
    bpy.context.view_layer.update()
    for name in ['SafetyPin','PinEyelet','PullRing']:
        reparent(bpy.data.objects[name],ctrl)
    driver(ctrl,'location',1,'-0.052*p',root,[('p','pin_pull')])
    lever=bpy.data.objects.new('CTRL_LeverPose',None)
    bpy.context.scene.collection.objects.link(lever)
    lever.parent=root
    lever.location=(-.009,0,.111)
    lever.empty_display_size=.009
    bpy.context.view_layer.update()
    for name in ['SafetyLever','LeverSidePlate','FuzeRivet_L1','FuzeRivet_R1',
                 'FuzeRivet_L2','FuzeRivet_R2','FuzeRivet_L3','FuzeRivet_R3']:
        reparent(bpy.data.objects[name],lever)
    driver(lever,'rotation_euler',1,'-1.18682389*l*min(1,max(0,(p-0.65)/0.35))',root,
           [('p','pin_pull'),('l','lever_open')])
    for f,p,l in [(1,0,0),(9,0,0),(25,1,0),(36,1,0),(54,1,1),(65,1,1),(83,1,0),(96,0,0)]:
        root['pin_pull'],root['lever_open']=float(p),float(l)
        root.keyframe_insert(data_path='["pin_pull"]',frame=f)
        root.keyframe_insert(data_path='["lever_open"]',frame=f)
    root.animation_data.action.name='DEMO_PinAndLever_VisualOnly'
    scene=bpy.context.scene
    scene.frame_start,scene.frame_end=1,96
    scene.render.fps=24
    for f,name in [(1,'Assembled'),(25,'Pin separate, lever held'),(54,'Lever outward - visual pose'),(96,'Assembled again')]:
        scene.timeline_markers.new(name,frame=f)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    (OUT/'checks').mkdir(parents=True,exist_ok=True)
    (OUT/'checks/object_mapping.json').write_text(json.dumps(mapping,indent=2),encoding='utf8')
    bpy.ops.wm.save_as_mainfile(filepath=str(GEOMETRY))
    return root


def authoring_coords():
    for ob in bpy.context.scene.objects:
        if ob.type!='MESH':
            continue
        me=ob.data
        co=np.empty(len(me.vertices)*3,np.float32)
        me.vertices.foreach_get('co',co)
        co=co.reshape(-1,3)
        idx=np.empty(len(me.loops),np.int32)
        me.loops.foreach_get('vertex_index',idx)
        mw=np.array(ob.matrix_world,np.float32)
        pts=co[idx]@mw[:3,:3].T+mw[:3,3]
        fn=np.empty(len(me.polygons)*3,np.float32)
        me.polygons.foreach_get('normal',fn)
        total=np.empty(len(me.polygons),np.int32)
        me.polygons.foreach_get('loop_total',total)
        n=np.repeat(fn.reshape(-1,3)@mw[:3,:3].T,total,axis=0)
        front=np.clip((-n[:,1]-.20)/.6,0,1)
        contact=np.ones(len(idx),np.float32)*.30
        recess=np.zeros(len(idx),np.float32)
        dust=np.clip((n[:,2]-.45)/.45,0,1)
        banduv=np.column_stack((pts[:,0]/.08+.5,pts[:,2]/.086))
        stampuv=np.column_stack((pts[:,0]/.022+.5,pts[:,1]/.011+.5))
        fingeruv=np.column_stack(((pts[:,0]+.011)/.016+.5,(pts[:,2]-.043)/.021+.5))
        if ob.name=='GrenadeBody':
            rad=np.hypot(pts[:,0],pts[:,1])
            bins=np.clip((pts[:,2]/.086*180).astype(int),0,179)
            rmax=np.zeros(180,np.float32)
            for b in range(180):
                values=rad[bins==b]
                rmax[b]=np.percentile(values,98) if len(values) else 0
            recess=np.clip((rmax[bins]-rad-.00015)/.0019,0,1)
            contact=np.clip(1-recess,0,1)*np.exp(-((pts[:,2]-.044)/.029)**2)
            dust*=.32+recess*.68
        elif ob.name in {'SafetyLever','LeverSidePlate'}:
            contact=np.clip(.35+front*.50+np.abs(n[:,0])*.15,0,1)
            recess=np.clip(1-front*.75,0,1)*.5
            fingeruv=np.column_stack(((pts[:,0]-.031)/.012+.5,(pts[:,2]-.041)/.019+.5))
        else:
            contact=np.clip(.25+np.abs(n[:,0])*.45+front*.25,0,1)
            recess=np.clip(1-contact,0,1)*.35
        for name,arr in [('Wear_Contact',contact),('Wear_Recess',recess),('Wear_Dust',dust),
                         ('Wear_FrontFace',front),('Wear_StampTop',np.clip((n[:,2]-.7)/.25,0,1)),
                         ('Wear_LowerLever',np.clip((.097-pts[:,2])/.010,0,1)),
                         ('Wear_PinRubbing',np.clip(np.abs(n[:,1])*.7+.2,0,1))]:
            att=me.color_attributes.get(name) or me.color_attributes.new(name=name,type='FLOAT_COLOR',domain='CORNER')
            rgba=np.ones((len(idx),4),np.float32)
            rgba[:,:3]=arr[:,None]
            att.data.foreach_set('color',rgba.ravel())
        if not me.uv_layers.active:
            uv=me.uv_layers.new(name=P.UV)
            uv.data.foreach_set('uv',np.column_stack((pts[:,0]/.16+.5,pts[:,2]/.16+.15)).astype(np.float32).ravel())
        active=me.uv_layers.active.name
        for name,arr in [('BandProjection',banduv),('StampProjection',stampuv),('FingerprintProjection',fingeruv)]:
            uv=me.uv_layers.get(name) or me.uv_layers.new(name=name)
            uv.data.foreach_set('uv',arr.astype(np.float32).ravel())
        me.uv_layers.active=me.uv_layers[active]
        me.uv_layers[active].active_render=True
        me.update()


def protected_grime(t,amount=.30):
    l=L(t,'80 • Protected groove grime',(.024,.019,.012),0,.86,amount=amount)
    attribute(l,'Wear_Recess','Actual protected grooves')
    nm(l,'Uneven deposits',650,.32,.60,(.020,.021,.003))
    l=L(t,'82 • Settled dust on sheltered ledges',(.12,.096,.060),0,.87,amount=.20)
    attribute(l,'Wear_Dust','Upward ledges, cleaned at grip')
    nm(l,'Patchy dust',1150,.44,.66,(.032,.004,.040))


def fingerprints(t,amount=.22):
    l=L(t,'90 • Partial finger oil - roughness only',rough=.23,amount=amount)
    imask(l,'single_partial_print_1k.png','CC0 partial print - 16 x 21 mm','FingerprintProjection')
    attribute(l,'Wear_FrontFace','Front-facing contact only')


def body_stack():
    t=create_stack('UCUPaint_Body_CastIron_OD','Mk II • olive drab on cast iron',
                   [bpy.data.objects['GrenadeBody']],(.041,.047,.025),0,.52)
    L(t,'00 • Olive drab paint over cast iron',(.041,.047,.025),0,.52)
    cc0_layer(t,'03 • CC0 dented iron substrate relief 8K','Metal049C','Displacement','Normal',.55,distance=.000048)
    L(t,'05 • Cast surface - 38 micron relief',height='source',source_type='NOISE',scale=2350,normal_distance=.000038)
    image_height(t,'07 • Irregular casting cavities - owner photo relief',
                 'cast_pitting_soft_8k_16bit.png',.00065)
    L(t,'06 • Fine casting pores - 18 micron relief',height='source',source_type='NOISE',scale=7100,normal_distance=.000018)
    L(t,'08 • Paint micrograin - 9 micron relief',height='source',source_type='NOISE',scale=14000,normal_distance=.000009)
    l=L(t,'10 • Subtle uneven coating colour',(.025,.031,.014),0,.57,amount=.27)
    imask(l,'nonuniform_storage_4k.png','Own 16 bit multiscale coat variation')
    l=L(t,'12 • Fine roughness variation',rough=.73,amount=.31)
    nm(l,'Submillimetre roughness',5800)
    l=L(t,'16 • Narrow yellow neck identification band',(.69,.47,.022),0,.53)
    imask(l,'neck_band_8kx4k.png','4.1 mm painted neck band','BandProjection')
    l=L(t,'18 • Worn patches of yellow marking',(.043,.049,.027),0,.61,amount=.8)
    imask(l,'neck_band_8kx4k.png','Band area','BandProjection')
    nm(l,'Broken marking spots',1600,.47,.63,(.13,.06,.02))
    l=L(t,'19 • Rubbed breaks in yellow neck band',(.058,.062,.038),.30,.58,height=0,normal_distance=.000025,amount=.84)
    imask(l,'neck_band_8kx4k.png','Only identification band','BandProjection')
    imask(l,'rubbed_paint_patches_8k.png','Irregular neck handling wear')
    l=L(t,'19b • Thin red neck seal paint',(.24,.012,.016),0,.52)
    imask(l,'red_neck_seal_8kx4k.png','1.2 mm red line below head','BandProjection')
    l=L(t,'20 • Dark undercoat at edge impacts',(.018,.019,.017),.4,.60,height=0,normal_distance=.000023)
    P.edge_mask(l,.0010,.010,.045)
    nm(l,'Irregular edge damage',1650,.53,.63,(.031,.012,.034))
    l=L(t,'24 • Exposed dark cast iron at worn edges',(.105,.109,.104),1,.43,height=0,normal_distance=.000035,amount=.83)
    P.edge_mask(l,.00068,.015,.060)
    nm(l,'Small interrupted exposed edges',2350,.51,.63,(.007,.020,.046))
    l=L(t,'28 • A few small coating chips on contact faces',(.091,.095,.089),1,.49,height=0,normal_distance=.000032,amount=.72)
    imask(l,'sparse_chips_4k.png','Sparse submillimetre chips')
    attribute(l,'Wear_Contact','Raised grip faces')
    l=L(t,'29 • Paint wiped from raised cast panels',(.13,.139,.12),1,.48,height=0,normal_distance=.000032,amount=.94)
    imask(l,'rubbed_paint_patches_8k.png','3-8 mm irregular coating-loss patches')
    attribute(l,'Wear_Contact','Raised panels; sheltered grooves retain paint')
    l=L(t,'30 • Partly polished iron within rubbed patches',(.235,.249,.218),1,.37,amount=.65)
    imask(l,'rubbed_iron_centres_8k.png','Inner worn contact facets')
    attribute(l,'Wear_Contact','Raised handling contact')
    l=cc0_layer(t,'31 • Photographic aged iron within paint breaks 8K','Metal063','Color','Color',.26)
    imask(l,'rubbed_paint_patches_8k.png','Only exposed substrate')
    attribute(l,'Wear_Contact','Raised rubbed panels')
    l=L(t,'32 • Hairline scratches, few through paint',(.15,.153,.142),1,.40,height=0,normal_distance=.000020,amount=.57)
    imask(l,'micro_scratches_8k.png','8K, 20-75 micron scratches')
    attribute(l,'Wear_Contact','Handling contact zone')
    l=L(t,'36 • Short superficial packing scuffs',(.061,.068,.037),0,.66,height=0,normal_distance=.000012,amount=.48)
    imask(l,'short_scuffs_4k.png','Small intermittent surface scuffs')
    l=L(t,'42 • Raised faces polished by handling',rough=.40,amount=.35)
    attribute(l,'Wear_Contact','Actual grip contact')
    nm(l,'Uneven hand polish',600,.34,.63)
    l=L(t,'52 • Very restrained oxide at exposed chips',(.071,.031,.011),0,.83,height='source',source_type='NOISE',scale=6700,normal_distance=.000012,amount=.27)
    imask(l,'sparse_chips_4k.png','Only coating breaks')
    nm(l,'Localized oxidized spots',2600,.45,.68,(.019,.055,.040))
    protected_grime(t,.47)
    fingerprints(t,.18)
    return t


def lever_stack():
    t=create_stack('UCUPaint_Lever_SilverAndDarkSteel','Mk II • bright upper cap and dark aged lever',
                   [bpy.data.objects['SafetyLever']],(.31,.319,.284),1,.40)
    L(t,'00 • Light warm-grey pressed steel',(.31,.319,.284),1,.40)
    cc0_layer(t,'03 • CC0 metal base variation 8K','Metal049C','Color','Color',.20)
    cc0_layer(t,'04 • CC0 fine directional scuff roughness 8K','Metal009','Roughness','Roughness',.34,extent_mm=110)
    cc0_layer(t,'05 • CC0 shallow pressed-metal dents 8K','Metal049C','Displacement','Normal',.42,distance=.000036)
    L(t,'06 • Crisp etched micrograin 22 microns',height='source',source_type='NOISE',scale=9500,normal_distance=.000022)
    l=L(t,'09 • Aged protective finish on lower lever',(.092,.105,.071),.72,.48,amount=.72)
    attribute(l,'Wear_LowerLever','Below head: dark lever, bright upper cap')
    l=L(t,'10 • Slight oxide tint in thin lower finish',(.078,.083,.048),.52,.54,amount=.18)
    attribute(l,'Wear_LowerLever','Lower lever only')
    nm(l,'Mottled passivation',1900)
    l=L(t,'11 • Local photographic oxide grains',(.092,.038,.014),0,.76,amount=.35)
    cc0_oxide_mask(l)
    attribute(l,'Wear_Recess','Protected areas retain oxidation')
    l=L(t,'12 • Small roughness variation',rough=.63,amount=.24)
    nm(l,'Fine finish variation',5300)
    l=L(t,'20 • Dull steel exposed on rubbed edges',(.26,.27,.24),1,.39,height=0,normal_distance=.000018,amount=.78)
    P.edge_mask(l,.00035,.02,.085)
    nm(l,'Interrupted edge polishing',2300,.44,.63,(.036,.013,.026))
    l=L(t,'26 • Sparse finish-loss spots',(.19,.20,.174),1,.46,height=0,normal_distance=.000013,amount=.75)
    imask(l,'sparse_chips_4k.png','0.15-1.4 mm wear spots')
    l=L(t,'32 • Thin direction-dependent handling scratches',(.30,.31,.28),1,.36,height=0,normal_distance=.000011,amount=.61)
    imask(l,'micro_scratches_8k.png','Thin handling marks, 8K')
    l=L(t,'36 • Contact polishing',rough=.31,amount=.20)
    attribute(l,'Wear_Contact','Press and grip contact')
    nm(l,'Localized polish',650,.42,.68)
    l=L(t,'55 • Sun icon and exact Cyrillic СЛНШК',(.009,.010,.008),0,.67,amount=.94)
    imask(l,'sun_slnshk_4kx2k.png','Original sun and СЛНШК; fine print abrasion','StampProjection')
    attribute(l,'Wear_StampTop','Upper flat only')
    protected_grime(t,.20)
    fingerprints(t,.25)
    return t


def fuze_stack():
    t=create_stack('UCUPaint_Fuze_LightZincAlloy','Mk II • dull light die-cast zinc alloy',
                   [bpy.data.objects[n] for n in ['FuzeCasting','BottomPlug']],
                   (.34,.355,.32),1,.41)
    L(t,'00 • Light silver die-cast zinc alloy',(.34,.355,.32),1,.41)
    cc0_layer(t,'02 • CC0 dented light-metal variation 8K','Metal049C','Color','Color',.27)
    cc0_layer(t,'03 • CC0 irregular metal roughness 8K','Metal049C','Roughness','Roughness',.40)
    cc0_layer(t,'04 • CC0 shallow casting relief 8K','Metal049C','Displacement','Normal',.6,distance=.00006)
    L(t,'06 • Sharp cast grain 36 microns',height='source',source_type='NOISE',scale=7300,normal_distance=.000036)
    L(t,'07 • Fine secondary grain 13 microns',height='source',source_type='NOISE',scale=17500,normal_distance=.000013)
    image_height(t,'08 • Shallow die-cast surface imperfections',
                 'cast_pitting_soft_8k_16bit.png',.00043,amount=.75)
    l=L(t,'10 • Restrained zinc oxide stain',(.139,.151,.127),.72,.58,amount=.13)
    nm(l,'Light-metal oxide mottling',2100)
    l=L(t,'12 • Local fine oxide specks from CC0 source',(.086,.041,.022),.15,.78,amount=.26)
    cc0_oxide_mask(l)
    nm(l,'Oxide accumulation breakup',850,.30,.66,(.014,.021,.042))
    l=L(t,'18 • Light silver metal on rubbed edges',(.29,.31,.28),1,.39,amount=.71)
    P.edge_mask(l,.00018,.028,.095)
    nm(l,'Discontinuous contact',3400,.43,.63,(.019,.046,.030))
    l=L(t,'22 • Fine tool and contact scratches',(.23,.245,.215),1,.41,height=0,normal_distance=.000010,amount=.48)
    imask(l,'micro_scratches_8k.png','Small head-surface hairlines')
    l=L(t,'30 • Partial polish on exposed contacts',rough=.35,amount=.27)
    attribute(l,'Wear_Contact','Exposed faces only')
    nm(l,'Polish breakup',780,.35,.67)
    protected_grime(t,.24)
    return t


def pin_stack():
    t=create_stack('UCUPaint_PinRing_AgedSteel','Mk II • light steel wire, aged finish and contact polish',
                   [bpy.data.objects[n] for n in ['PinEyelet','PullRing','SafetyPin']],(.22,.235,.197),1,.37)
    L(t,'00 • Dull greenish steel wire with aged surface',(.22,.235,.197),1,.37)
    cc0_layer(t,'03 • CC0 drawn steel roughness 8K','Metal009','Roughness','Roughness',.28,extent_mm=110)
    cc0_layer(t,'04 • CC0 sparse wire surface relief 8K','Metal049C','Displacement','Normal',.25,distance=.000014)
    L(t,'06 • Crisp fine wire grain 11 microns',height='source',source_type='NOISE',scale=12500,normal_distance=.000011)
    l=L(t,'10 • Restrained oxide discolouration',(.058,.048,.030),.6,.58,amount=.27)
    nm(l,'Patchy wire ageing',2500,.39,.67)
    l=L(t,'12 • Small protected oxide specks',(.071,.042,.019),.4,.64,amount=.24)
    cc0_oxide_mask(l)
    l=L(t,'18 • Bright rubbed wire contact',(.33,.34,.30),1,.30,amount=.53)
    attribute(l,'Wear_PinRubbing','Pull and eyelet contact')
    nm(l,'Localized burnishing',1500,.33,.61,(.004,.024,.049))
    l=L(t,'24 • Tiny handling hairlines',rough=.31,height=0,normal_distance=.000003,amount=.35)
    imask(l,'micro_scratches_8k.png','Micro-abrasions on steel')
    return t


def pack_all():
    tex=OUT/'textures/original_scenario'
    tex.mkdir(parents=True,exist_ok=True)
    rows=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        if im.packed_file and not im.filepath:
            path=tex/(im.name+'.png')
            path.write_bytes(bytes(im.packed_file.data))
            im.filepath='//textures/original_scenario/'+path.name
        elif im.filepath:
            path=Path(bpy.path.abspath(im.filepath))
            if path.exists():
                if not im.packed_file:
                    im.pack()
                im.filepath='//'+path.relative_to(OUT).as_posix()
            elif im.packed_file:
                path=tex/(im.name+'.png')
                path.write_bytes(bytes(im.packed_file.data))
                im.filepath='//textures/original_scenario/'+path.name
        if im.packed_file:
            path=Path(bpy.path.abspath(im.filepath))
            with path.open('rb') as stream:
                header=stream.read(24)
            size=[int.from_bytes(header[16:20],'big'),int.from_bytes(header[20:24],'big')] if header[:8]==b'\x89PNG\r\n\x1a\n' else list(im.size)
            rows.append({'name':im.name,'path':im.filepath,'size':size,'color_space':im.colorspace_settings.name,
                         'sha256':hashlib.sha256(bytes(im.packed_file.data)).hexdigest()})
    (OUT/'textures/packed_image_manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf8')


def build():
    bpy.context.preferences.use_preferences_save=False
    P.native()
    approval=json.loads((OUT/'checks/geometry_approved_v05.json').read_text(encoding='utf8'))
    assert approval['status']=='explicitly_approved_by_owner'
    assert hashlib.sha256(GEOMETRY.read_bytes()).hexdigest()==approval['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(GEOMETRY))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    for mat in bpy.data.materials:
        mat.use_fake_user=True
        mat['preserved']='Original Scenario material; retained as unassigned backup'
    root=bpy.data.objects['CTRL_Grenade']
    authoring_coords()
    trees=[]
    for make in [body_stack,lever_stack,fuze_stack,pin_stack]:
        t=make()
        P.H.reconnect(P.U,t)
        trees.append(t)
        pack_all()
        checkpoint=OUT/f'checkpoint_v06_{make.__name__}.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),relative_remap=False)
        print('CHECKPOINT_SAVED',checkpoint.name,flush=True)
    print('STACKS_READY',[(t.name,len(t.yp.layers)) for t in trees],flush=True)
    S.setup_studio((0,0,0))
    scene=bpy.context.scene
    scene.cycles.use_denoising=False
    scene.camera.location=(.17,-.28,.18)
    S.aim(scene.camera,(0,0,.057))
    scene.camera.data.ortho_scale=.167
    scene.frame_set(1)
    # Open directly on the object with useful material viewport and metre units.
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1.0
    scene.unit_settings.length_unit='MILLIMETERS'
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_location=(0,0,.055)
                area.spaces.active.region_3d.view_distance=.22
                area.spaces.active.clip_start=.001
                area.spaces.active.shading.type='MATERIAL'
                area.spaces.active.shading.studiolight_rotate_z=.7
    text=bpy.data.texts.get('00_TEXTURES_V06') or bpy.data.texts.new('00_TEXTURES_V06')
    text.clear()
    text.write('Mk II artistic asset / native UCUPaint 2.4.9 / textures v06\n'
               'Geometry v05 explicitly approved: 63.4 mm body diameter, 114.51 mm total height.\n'
               'No manufacturing internals or firing simulation.\n'
               'Select CTRL_Grenade: pin_pull and lever_open, both 0..1.\n'
               'The lever control is gated while the pin is seated.\n'
               'Frames 1..96: visual demonstration, 24 fps. Unlink DEMO action for manual sliders.\n'
               'Materials each contain a real native UCUPaint stack; original Scenario materials retained.\n'
               'Noise scales use metres; image imperfections use 160 mm object projection.\n'
               'Sun icon + Cyrillic СЛНШК replace both English stencil lines.\n'
               'CC0 sources: ambientCG Metal049C (procedural), Metal009 (procedural), Metal063 (photo approximation).\n'
               '8K sources supplement physically scaled original casting pores and contact wear.\n')
    pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),relative_remap=False)
    print('GRENADE_BUILD_OK',str(MASTER),flush=True)


def render():
    P.native()
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    S.setup_studio((0,0,0))
    scene=bpy.context.scene
    scene.cycles.use_denoising=False
    scene.frame_set(1)
    only=[s for s in sys.argv[sys.argv.index('--')+2:] if s] if '--' in sys.argv else []
    views=[
        ('01_textured_overall',(.17,-.28,.18),(0,0,.057),.167,1),
        ('02_textured_other_side',(-.17,.28,.14),(0,0,.057),.163,1),
        ('03_cast_and_wear',(.09,-.18,.105),(0,-.007,.040),.066,1),
        ('04_head_ring_marking',(.09,-.14,.22),(0,0,.101),.071,1),
        ('05_lever_surface',(.19,-.13,.068),(.029,0,.049),.083,1),
        ('06_pin_separate_lever_held',(.17,-.28,.18),(0,-.009,.061),.173,30),
        ('07_lever_outward',(.23,-.34,.20),(.025,-.009,.071),.199,59),
        ('08_bottom',(.10,-.18,-.10),(0,0,.025),.103,1),
        ('09_sun_slnshk_top',(.003,-.005,.25),(0,0,.112),.037,1),
        ('10_real_hole_and_split_tips',(.065,.10,.134),(.0115,.008,.1021),.047,1),
    ]
    for name,cam,target,scale,frame in views:
        if only and name not in only:
            continue
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        scene.cycles.samples=int(os.environ.get('GRENADE_RENDER_SAMPLES','256'))
        scene.render.resolution_x,scene.render.resolution_y=1800,2200
        S.shot(name,(0,0,0),cam,target,scale)
    print('GRENADE_RENDER_OK',flush=True)


def inspect():
    P.native()
    candidate=Path(os.environ.get('GRENADE_INSPECT_CANDIDATE',str(MASTER)))
    bpy.ops.wm.open_mainfile(filepath=str(GEOMETRY))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    source={}
    root_translation=np.zeros(3)
    for ob in bpy.context.scene.objects:
        if ob.type=='MESH':
            keys={}
            if ob.data.shape_keys:
                for key in ob.data.shape_keys.key_blocks:
                    ar=np.empty(len(key.data)*3,np.float32)
                    key.data.foreach_get('co',ar)
                    keys[key.name]=hashlib.sha256(ar.tobytes()).hexdigest()
            source[ob.name]={'mesh':ob.data.copy(),'matrix':np.array(ob.matrix_world),'normal':[(p.use_smooth) for p in ob.data.polygons],
                'keys':keys,'modifiers':[(m.name,m.type,getattr(m,'levels',None),getattr(m,'render_levels',None)) for m in ob.modifiers],
                'parent':ob.parent.name if ob.parent else None}
    # Numeric snapshots, not references invalidated by open_mainfile.
    def signature(me):
        arrays=[]
        for collection,prop,components,dtype in [(me.vertices,'co',3,np.float32),(me.edges,'vertices',2,np.int32),
                (me.loops,'vertex_index',1,np.int32),(me.polygons,'loop_start',1,np.int32),(me.polygons,'loop_total',1,np.int32)]:
            arr=np.empty(len(collection)*components,dtype)
            collection.foreach_get(prop,arr)
            arrays.append(arr.tobytes())
        return hashlib.sha256(b''.join(arrays)).hexdigest()
    for row in source.values():
        me=row.pop('mesh')
        row['hash']=signature(me)
        row['uv_hashes']={}
        for uv in me.uv_layers:
            arr=np.empty(len(uv.data)*2,np.float32)
            uv.data.foreach_get('uv',arr)
            row['uv_hashes'][uv.name]=hashlib.sha256(arr.tobytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(candidate))
    report={'pass':True,'candidate':str(candidate),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'materials':[],
            'geometry':[],'poses':[],'images':[],'assigned_materials':[],
            'blender':bpy.app.version_string,'ucupaint':P.U.common.get_current_version_str()}
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    for ob in bpy.context.scene.objects:
        if ob.type=='MESH':
            if ob.name not in source and os.environ.get('GRENADE_INSPECT_STUDIO')=='1':
                assert ob.name in {'STUDIO • seamless graphite backdrop','STUDIO • charcoal mineral pedestal'},ob.name
                report.setdefault('presentation_meshes',[]).append(ob.name)
                continue
            old=source[ob.name]
            sig=signature(ob.data)
            assert sig==old['hash'],ob.name
            mw=old['matrix'].copy()
            mw[:3,3]-=root_translation
            error=float(np.max(np.abs(np.array(ob.matrix_world)-mw)))
            assert error<3e-7,(ob.name,error)
            assert old['normal']==[p.use_smooth for p in ob.data.polygons],ob.name
            assert old['parent']==(ob.parent.name if ob.parent else None),ob.name
            assert old['modifiers']==[(m.name,m.type,getattr(m,'levels',None),getattr(m,'render_levels',None)) for m in ob.modifiers],ob.name
            for keyname,keysha in old['keys'].items():
                key=ob.data.shape_keys.key_blocks[keyname]
                ar=np.empty(len(key.data)*3,np.float32)
                key.data.foreach_get('co',ar)
                assert hashlib.sha256(ar.tobytes()).hexdigest()==keysha,(ob.name,keyname)
            for name,digest in old['uv_hashes'].items():
                uv=ob.data.uv_layers[name]
                arr=np.empty(len(uv.data)*2,np.float32)
                uv.data.foreach_get('uv',arr)
                assert hashlib.sha256(arr.tobytes()).hexdigest()==digest,(ob.name,name)
            report['geometry'].append({'object':ob.name,'mesh_unchanged':True,'closed_transform_error_m':error,
                                       'uv':[u.name for u in ob.data.uv_layers]})
            mat=ob.data.materials[0]
            assignment={'object':ob.name,'material':mat.name}
            assert mat.use_nodes,ob.name
            if mat.name.startswith('PBR_Preview_'):
                assignment['mode']='baked_preview'
                principled=mat.node_tree.nodes.get('Principled BSDF')
                channels={}
                for socket in ['Base Color','Metallic','Roughness','Normal']:
                    assert principled.inputs[socket].is_linked,(ob.name,socket)
                    node=principled.inputs[socket].links[0].from_node
                    if socket=='Normal':
                        assert node.type=='NORMAL_MAP' and node.uv_map=='PBRUV',ob.name
                        node=node.inputs['Color'].links[0].from_node
                    assert node.type=='TEX_IMAGE' and node.image and node.image.packed_file,ob.name
                    assert node.inputs['Vector'].is_linked,ob.name
                    assert node.inputs['Vector'].links[0].from_node.uv_map=='PBRUV',ob.name
                    channels[socket]=node.image.name
                assignment['maps']=channels
            else:
                assert mat.name.startswith('UCUPaint_'),ob.name
                assert any(n.type=='GROUP' and getattr(n.node_tree,'yp',None)
                           and n.node_tree.yp.is_ypaint_node for n in mat.node_tree.nodes),ob.name
                assignment['mode']='native_ucupaint'
            report['assigned_materials'].append(assignment)
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in mat.node_tree.nodes:
            if node.type!='GROUP' or not getattr(node.node_tree,'yp',None) or not node.node_tree.yp.is_ypaint_node:
                continue
            t=node.node_tree
            e={'material':mat.name,'channels':[(c.name,c.type) for c in t.yp.channels],'layers':[]}
            assert len(t.yp.channels)==4
            for lay in t.yp.layers:
                actual=P.U.common.get_entity_prop_value(lay,'intensity_value')
                assert abs(actual-lay.intensity_value)<1e-6,lay.name
                row={'name':lay.name,'enabled':lay.enable,'intensity':actual,'masks':[]}
                if lay.type=='IMAGE':
                    source_node=P.U.common.get_layer_source(lay)
                    assert source_node.image and source_node.image.packed_file,lay.name
                    if lay.texcoord_type=='Object':
                        assert source_node.projection=='BOX',lay.name
                    row['image_source']={'name':source_node.image.name,'projection':source_node.projection,
                                         'scale':list(lay.scale),'translation':list(lay.translation)}
                for ch in lay.channels:
                    if ch.enable and ch.override:
                        prop='override_color' if t.yp.channels[list(lay.channels).index(ch)].type=='RGB' else 'override_value'
                        value=P.U.common.get_entity_prop_value(ch,prop)
                        a=list(value)[:3] if prop=='override_color' else [value]
                        exp=list(getattr(ch,prop)) if prop=='override_color' else [getattr(ch,prop)]
                        assert max(abs(x-y) for x,y in zip(a,exp))<1e-6,(lay.name,prop)
                    if ch.enable and ch.id_data.yp.channels[list(lay.channels).index(ch)].type=='NORMAL':
                        assert abs(P.U.common.get_entity_prop_value(ch,'bump_distance')-ch.bump_distance)<1e-6,lay.name
                for m in lay.masks:
                    src=P.U.common.get_mask_tree(m).nodes.get(m.source)
                    mr={'name':m.name,'type':m.type,'enabled':m.enable}
                    if src and src.type=='TEX_IMAGE':
                        assert src.image and src.image.packed_file,m.name
                        mr.update(projection=src.projection,image=src.image.name)
                        if m.texcoord_type=='Object':
                            assert src.projection=='BOX',m.name
                    row['masks'].append(mr)
                e['layers'].append(row)
            report['materials'].append(e)
    assert len(report['materials'])==4
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        if im.name=='Viewer Node':
            continue
        path=Path(bpy.path.abspath(im.filepath))
        assert im.packed_file and path.is_file(),im.name
        if im.name.startswith('MkII_'):
            expected_space='sRGB' if '_BaseColor_' in im.name else 'Non-Color'
            assert im.colorspace_settings.name==expected_space,(im.name,im.colorspace_settings.name,expected_space)
        a=hashlib.sha256(bytes(im.packed_file.data)).hexdigest()
        assert a==hashlib.sha256(path.read_bytes()).hexdigest(),im.name
        report['images'].append({'name':im.name,'path':im.filepath,'sha256':a,'size':list(im.size),
                                'color_space':im.colorspace_settings.name,'packed':True})
        im.buffers_free()
    scene=bpy.context.scene
    for frame in [1,17,25,30,36,45,54,59,65,75,83,90,96]:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        pin=bpy.data.objects['CTRL_PinAssembly']
        lever=bpy.data.objects['CTRL_LeverPose']
        root=bpy.data.objects['CTRL_Grenade']
        angle=math.degrees(lever.rotation_euler.y)
        p=root['pin_pull']
        expected=-.0006*min(1,p/.16)-.0514*max(0,(p-.16)/.84)
        assert abs(pin.location.y-expected)<1e-6,frame
        c=min(1,max(0,p/.16))*min(1,max(0,(.74-p)/.14))
        assert abs(bpy.data.objects['SafetyPin'].data.shape_keys.key_blocks['SplitTips_Compress'].value-c)<1e-6,frame
        assert abs(angle)<=68.0001,frame
        if root['pin_pull']<.65:
            assert abs(angle)<1e-5,frame
        report['poses'].append({'frame':frame,'pin_pull':root['pin_pull'],'lever_open':root['lever_open'],
                                'pin_offset_m':pin.location.y,'lever_angle_degrees':angle})
    report['approved_geometry']='v05'
    report['approval_reply']='Да, v05 принята — делай текстуры'
    report['approved_file_sha256']=hashlib.sha256(GEOMETRY.read_bytes()).hexdigest()
    report_path=Path(os.environ.get('GRENADE_AUDIT_REPORT',str(OUT/'checks/fresh_reopen_audit_v06.json')))
    report_path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print('FRESH_REOPEN_AUDIT_OK',len(report['geometry']),'unchanged meshes',
          sum(len(m['layers']) for m in report['materials']),'native layers',len(report['images']),'packed maps',flush=True)


if __name__=='__main__':
    {'build':build,'render':render,'inspect':inspect}[MODE]()
