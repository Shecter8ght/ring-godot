"""Сборка 14 собственных вещей RING по шести концептам владельца."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import hashlib
import json
import math
import addon_utils
import bpy
from mathutils import Vector
import m02_custom_clothes as G
import wardrobe_geometry as W

ROOT=Path(__file__).resolve().parents[2]
SOURCE=G.SOURCE
WORK=ROOT/'_asset_src/npc_wardrobe'
OUTFITS={1:('T01','P01','F01'),2:('T02','P02','F02'),3:('T03','P01','F01'),
         4:('T04','P03','F02B'),5:('T05','P04','F03'),6:('T06','P04','F03')}


def placeholder_materials():
    result={}
    for configs in [W.TOPS,W.PANTS,W.SHOES]:
        for code,cfg in configs.items():
            result.setdefault(cfg['fabric'],G.material(cfg['fabric'],cfg['color'],.76))
    for name,color in {'thread_dark':(.11,.105,.089),'thread_jeans':(.28,.19,.085),
        'thread_boot':(.20,.14,.085),'hardware':(.12,.12,.10),'button':(.065,.06,.055),
        'rib_dark':(.035,.035,.032),'zip_tape':(.027,.028,.024),'piping':(.49,.47,.36),
        'repair_olive':(.073,.089,.059),'rubber':(.025,.024,.021),'midsole':(.29,.25,.18),
        'trek_mesh':(.032,.032,.027),'leather_black':(.012,.013,.012)}.items():
        result[name]=G.material(name,color,.65,.68 if name=='hardware' else 0)
    return result


def studio(samples):
    scene=bpy.context.scene
    studio_col=bpy.data.collections['06_Review_Studio']
    for obj in list(studio_col.objects):
        if obj.type=='LIGHT': bpy.data.objects.remove(obj,do_unlink=True)
    for name,pos,power,size in [('Wardrobe_Key',(-2,-3.5,4),280,3.0),
                              ('Wardrobe_Fill',(2.5,-1.5,2.6),120,3.2),
                              ('Wardrobe_Rim',(0,2.2,3.1),200,2.5)]:
        light=bpy.data.lights.new(name,'AREA');light.energy=power;light.shape='DISK';light.size=size
        obj=bpy.data.objects.new(name,light);studio_col.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector((0,0,.9))-obj.location).to_track_quat('-Z','Y').to_euler()
    world=scene.world
    world.use_nodes=True
    background=next(node for node in world.node_tree.nodes if node.type=='BACKGROUND')
    background.inputs['Color'].default_value=(.40,.44,.49,1)
    background.inputs['Strength'].default_value=.25
    # Матовый пол сохраняет читаемую контактную тень.
    floor=G.mesh_object('Wardrobe | studio floor',[(-200,-200,-.025),(200,-200,-.025),(200,200,-.025),(-200,200,-.025)],[(0,1,2,3)],studio_col,G.material('Wardrobe | grey backdrop',(.26,.29,.33),.93))
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.view_settings.exposure=0
    scene.render.engine='CYCLES';scene.cycles.samples=samples;scene.cycles.use_denoising=True
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU' if any(device.use for device in prefs.devices) else 'CPU'
    scene.render.resolution_x=1440;scene.render.resolution_y=1600;scene.render.resolution_percentage=100
    for name,pos,target,scale in [('Front',(0,-4,.91),(0,0,.91),2.15),('Back',(0,4,.91),(0,0,.91),2.15),
        ('ThreeQuarter',(2.2,-4,1.25),(0,-.02,.93),2.15),('Side',(4,0,.96),(0,0,.96),2.1),
        ('TopDetail',(.6,-2,1.55),(0,-.03,1.27),.77),('BootDetail',(.6,-1,.38),(0,-.05,.12),.54)]:
        data=bpy.data.cameras.new('Wardrobe_'+name);data.type='ORTHO';data.ortho_scale=scale
        obj=bpy.data.objects.new('Wardrobe_'+name,data);studio_col.objects.link(obj);obj.location=pos
        obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    return scene


def add_controls(items,root,body,rig):
    controls=bpy.data.objects.new('RING | Wardrobe Controls',None)
    root.objects.link(controls)
    controls['Комплект']=1
    controls.id_properties_ui('Комплект').update(min=1,max=6,description='1 everyday, 2 work, 3 windbreaker, 4 sports, 5 combat shirt, 6 field jacket')
    controls['Предмет']=0
    controls.id_properties_ui('Предмет').update(min=0,max=len(items),description='0 full outfit; isolated asset index is recorded on each collection')
    for index,(code,col) in enumerate(sorted(items.items()),1):
        presets=[number for number,codes in OUTFITS.items() if code in codes]
        col['isolation_index']=index
        col['used_in_outfits']=','.join(map(str,presets))
        condition=' or '.join('outfit == '+str(number) for number in presets) or 'False'
        for obj in col.objects:
            for path in ['hide_render','hide_viewport']:
                driver=obj.driver_add(path).driver
                for name,key in [('outfit','Комплект'),('preview','Предмет')]:
                    var=driver.variables.new();var.name=name;var.targets[0].id=controls;var.targets[0].data_path='["'+key+'"]'
                driver.expression='not (preview == '+str(index)+' or (preview == 0 and ('+condition+')))'
    world=rig.matrix_world.copy();rig.parent=controls;rig.matrix_world=world
    controls.empty_display_size=.12
    controls['readme']='Original separate garment assets, fitted on unchanged M02. Switch outfit 1–6; 0 resets isolated item.'
    return controls


def black_boot_variant(items,root,mats):
    if 'F02' not in items: return
    col=G.collection('F02B | black work boot material variant',root);col['wardrobe_id']='F02B'
    for original in items['F02'].objects:
        obj=original.copy();col.objects.link(obj);obj.name=original.name.replace('F02 |','F02B |');obj['wardrobe_id']='F02B'
        for slot in obj.material_slots:
            if slot.material==mats['leather_brown']:
                slot.link='OBJECT';slot.material=mats['leather_black']
    col.asset_mark();col.asset_data.description='F02 work boots: shared original geometry, black leather material variant'
    items['F02B']=col


def build(args):
    out=WORK/args.version;out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    source_surface=G.BodySurface(body)
    root=G.collection('09_Ring_Original_Wardrobe')
    construction=G.collection('Construction diagnostics')
    collider=W.make_collider(body,construction)
    mats=placeholder_materials()
    items={};report=[]
    requested=args.items.split(',')
    ordered=sorted(requested,key=lambda code:(0 if code.startswith('P') else 1 if code.startswith('F') else 2,code))
    for code in ordered:
        cfg=W.TOPS.get(code) or W.PANTS.get(code) or W.SHOES.get(code)
        col=G.collection(code+' | '+cfg['title'],root);col['wardrobe_id']=code
        print('WARDROBE_CONSTRUCT '+code,flush=True)
        drape=0
        if code.startswith('T'):
            main=W.main_top(code,col,mats)
            pants={'T00':'P02','T01':'P01','T02':'P02','T03':'P01','T04':'P03','T05':'P04','T06':'P04'}[code]
            if args.drape: drape=W.garment_drape(main,collider,args.drape)
            if pants in items:
                lower=next(obj for obj in items[pants].objects if 'sewn trouser panels' in obj.name)
                W.resolve_layers(main,lower)
            W.top_details(code,col,main,mats)
        elif code.startswith('P'):
            main=W.main_pants(code,col,mats,source_surface)
            if args.drape: drape=W.garment_drape(main,collider,args.drape)
            W.pants_details(code,col,main,mats)
        else:
            W.footwear(code,col,mats)
        for obj in col.objects:
            obj['wardrobe_id']=code
            if obj.type=='MESH' and not obj.data.uv_layers: W.metric_uv(obj)
        G.bind(list(col.objects),body,rig)
        col.asset_mark();col.asset_data.description=cfg['title']+' | original RING construction | M02 fitting size'
        items[code]=col
        report.append({'id':code,'name':cfg['title'],'collection':col.name,'objects':len(col.objects),'drape_displacement_m':drape})
        print('WARDROBE_ITEM_READY '+code,flush=True)
    bpy.data.objects.remove(collider,do_unlink=True)
    black_boot_variant(items,root,mats)
    # Обратимая маска оставляет исходную сетку тела и UV целыми.
    group=body.vertex_groups.new(name='Wardrobe | covered anatomy')
    covered=[]
    for vertex in body.data.vertices:
        x,y,z=body.matrix_world @ vertex.co
        chest_opening=abs(x)<.080 and y<-.015 and z>1.455
        if z<1.515 and (z<1.30 or abs(x)<.70) and not chest_opening: covered.append(vertex.index)
    group.add(covered,1.0,'REPLACE')
    mask=body.modifiers.new('Wardrobe | reversible anatomy coverage','MASK');mask.vertex_group=group.name;mask.invert_vertex_group=True
    G.activate(body)
    while body.modifiers[0]!=mask: bpy.ops.object.modifier_move_up(modifier=mask.name)
    shorts=bpy.data.objects['M02_Simple_Reference_Shorts'];shorts.hide_render=True;shorts.hide_set(True)
    scene=studio(args.samples)
    controls=add_controls(items,root,body,rig)
    if args.materials:
        import wardrobe_materials
        wardrobe_materials.apply(items,mats,out)
    filename=out/'RING_Wardrobe.blend'
    scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    scene.render.filepath=str(out/'threequarter.png')
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(filename),check_existing=False)
    (out/'wardrobe_report.json').write_text(json.dumps({'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'file':str(filename),'items':report},indent=2),encoding='utf-8')
    for preset in [int(value) for value in args.outfits.split(',')]:
        controls['Комплект']=preset;controls.update_tag();bpy.context.view_layer.update()
        for view in args.render.split(','):
            if not view: continue
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.filepath=str(out/(('C%02d_'%preset)+view.lower()+'.png'))
            bpy.ops.render.render(write_still=True)
            print('WARDROBE_RENDER C%02d %s'%(preset,view),flush=True)
    controls['Комплект']=1;controls.update_tag();bpy.context.view_layer.update()
    print('WARDROBE_BUILD_PASS '+str(filename),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default='wardrobe_probe_v01')
    parser.add_argument('--items',default='T01,P01,F01')
    parser.add_argument('--drape',type=int,default=0)
    parser.add_argument('--materials',action='store_true')
    parser.add_argument('--samples',type=int,default=48)
    parser.add_argument('--render',default='Front,ThreeQuarter')
    parser.add_argument('--outfits',default='1')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    build(parser.parse_args(argv))
