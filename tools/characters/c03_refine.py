"""Собрать и снять художественную редакцию C03, сохраняя анатомию М02."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import bpy
import importlib
import io
import json
import math
from contextlib import redirect_stdout
from mathutils import Vector
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_balaclavas as B
import npc_wardrobe as N
import c03_geometry as C

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/npc_wardrobe/c03_refinement'
SOURCE=Path('E:/Models Blender/RING_NPC_2026-10-20_v01/NPC_Wardrobe_Concepts_v01/RING_NPC_Wardrobe_M02_v01.blend')


def materials():
    result=N.placeholder_materials()
    colors={'nylon_olive':(.145,.155,.125),'denim':(.032,.064,.098),
        'jersey':(.18,.18,.175),'combat_knit':(.048,.051,.044),
        'trek_mesh':(.038,.042,.041),'suede':(.150,.127,.099),
        'midsole':(.285,.254,.211),'rubber':(.020,.020,.018),
        'thread_boot':(.175,.156,.127),'thread_dark':(.116,.126,.103),
        'thread_jeans':(.255,.178,.090),'zip_tape':(.057,.063,.050),
        'hardware':(.095,.101,.090)}
    for key,mat in result.items():
        mat.name='C03 | '+key
        if key in colors:
            mat.diffuse_color=(*colors[key],1)
            next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(*colors[key],1)
    return result


def finish_materials(items,mats,out):
    with redirect_stdout(io.StringIO()): M.apply(items,mats,out)
    U=M.U
    for key,mat in mats.items():
        node=next((n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node),None)
        if not node:continue
        tree=node.node_tree;bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        bsdf.inputs['Specular IOR Level'].default_value=.20 if key not in ['hardware','rubber'] else .30
        bsdf.inputs['Sheen Weight'].default_value=.28 if key in ['denim','suede','trek_mesh','jersey'] else .08
        for ly in tree.yp.layers:
            if ly.name.startswith('01 |'):
                for root,ch in zip(tree.yp.channels,ly.channels):
                    if root.name=='Roughness':M.sync(ch,'override_value',.84 if key in ['denim','suede','trek_mesh','jersey'] else .70 if key=='nylon_olive' else .78)
            if ly.name.startswith('03 |'):
                M.sync(ly,'intensity_value',.38 if key=='denim' else .22)
                for mod in ly.modifiers:
                    if mod.type=='HUE_SATURATION':
                        n=U.common.get_mod_tree(ly).nodes[mod.huesat]
                        n.inputs['Saturation'].default_value=.55 if key=='denim' else 0
                        n.inputs['Value'].default_value=2.25
            if ly.name.startswith('04 |'):
                for root,ch in zip(tree.yp.channels,ly.channels):
                    if root.type=='NORMAL':M.sync(ch,'bump_distance',.000070 if key in ['denim','suede'] else .000035)
            if ly.name.startswith('05 |'):M.sync(ly,'intensity_value',.12)
            if ly.name.startswith('06 |'):
                M.sync(ly,'intensity_value',.75 if key=='denim' else .25)
                for root,ch in zip(tree.yp.channels,ly.channels):
                    if root.name=='Color':M.sync(ch,'override_color',(.13,.19,.25) if key=='denim' else tuple(c*1.30+.008 for c in mat.diffuse_color[:3]))
                    if root.name=='Roughness':M.sync(ch,'override_value',.80)
            if ly.name.startswith('08 |'):M.sync(ly,'intensity_value',.16)
            if ly.name.startswith('09 |'):M.sync(ly,'intensity_value',.14 if key not in ['rubber','midsole','suede'] else .25)
            U.node_connections.reconnect_layer_nodes(ly)
        U.node_connections.reconnect_yp_nodes(tree)
        print('C03_NATIVE_MATERIAL '+key,flush=True)


def camera(name,pos,target,scale,col):
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=scale
    ob=bpy.data.objects.new(name,data);col.objects.link(ob);ob.location=pos
    ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
    return ob


def studio(samples):
    scene=bpy.context.scene;col=bpy.data.collections['06_Review_Studio']
    for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
    scene.render.engine='CYCLES';scene.cycles.samples=samples;scene.cycles.use_denoising=True
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.25
    background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
    background.inputs['Color'].default_value=(.58,.62,.67,1);background.inputs['Strength'].default_value=.40
    for name,pos,power,size in [('Key',(-2.3,-3.6,4),400,3.2),('Fill',(2.5,-2,2.7),210,3),('Rim',(1.0,2.2,3.3),330,2.5)]:
        data=bpy.data.lights.new('C03_'+name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        ob=bpy.data.objects.new('C03_'+name,data);col.objects.link(ob);ob.location=pos
        ob.rotation_euler=(Vector((0,0,1))-ob.location).to_track_quat('-Z','Y').to_euler()
    G.mesh_object('C03 | matte studio floor',[(-200,-200,.001),(200,-200,.001),(200,200,.001),(-200,200,.001)],[(0,1,2,3)],col,G.material('C03 | neutral grey backdrop',(.34,.37,.40),.92))
    for name,pos,target,scale in [('Front',(0,-4,.91),(0,0,.91),2.02),('ThreeQuarter',(2.1,-4,1.15),(0,0,.91),2.02),('Back',(0,4,.91),(0,0,.91),2.02),('Side',(4,0,.91),(0,0,.91),2.02),('Jacket',(.42,-2,1.50),(0,-.03,1.27),.85),('Jeans',(.55,-2,.72),(0,-.02,.60),1.08),('Shoes',(.48,-.9,.43),(0,-.08,.075),.52),('Mask',(.38,-1.6,1.72),(0,-.035,1.645),.37)]:
        camera('C03_'+name,pos,target,scale,col)
    scene.camera=bpy.data.objects['C03_ThreeQuarter'];scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    return scene


def use_render_device(scene):
    # --factory-startup сбрасывает настройки устройств между фоновыми запусками.
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices:device.use=device.type=='OPTIX'
    scene.cycles.device='GPU' if any(device.use for device in prefs.devices) else 'CPU'


def render(out,views,samples):
    scene=bpy.context.scene;scene.cycles.samples=samples
    use_render_device(scene)
    for view in views.split(','):
        if not view:continue
        scene.camera=bpy.data.objects['C03_'+view]
        scene.render.resolution_x=1500 if view in ['Front','Back','Side','ThreeQuarter'] else 1400
        scene.render.resolution_y=1700 if view in ['Front','Back','Side','ThreeQuarter'] else 1100
        scene.render.filepath=str(out/('C03_'+view.lower()+'.png'))
        bpy.ops.render.render(write_still=True);print('C03_RENDER '+view,flush=True)


def build(args):
    out=WORK/args.version;out.mkdir(parents=True,exist_ok=True)
    D.enable_layers();bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    control=bpy.data.objects['RING | Wardrobe Controls'];control['Комплект']=3;control['Балаклава']=True;control['Вариант балаклавы']=3;control.update_tag();bpy.context.view_layer.update()
    items={}
    for col in list(bpy.data.collections):
        code=str(col.get('wardrobe_id',''))
        if not code:continue
        if code in ['T03','P01','F01','B03']:
            items[code]=col
            if code!='B03':
                for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
        else:
            for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
            bpy.data.collections.remove(col)
    for ob in list(bpy.data.objects):
        if 'undershirt' in ob.name.lower() or 'collar insert' in ob.name.lower():bpy.data.objects.remove(ob,do_unlink=True)
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig']
    masks=[(mod,mod.show_viewport,mod.show_render) for mod in body.modifiers if mod.type=='MASK']
    for mod,_,_ in masks:mod.show_viewport=False;mod.show_render=False
    bpy.context.view_layer.update();mats=materials()
    print('C03_BUILD_TOP',flush=True)
    top=W.main_top('T03',items['T03'],mats)
    C.open_neck(top);C.sculpt_top(top);W.metric_uv(top,'top');C.top_details(top,items['T03'],mats)
    print('C03_BUILD_JEANS',flush=True)
    pants=W.main_pants('P01',items['P01'],mats,G.BodySurface(body))
    C.sculpt_pants(pants);W.metric_uv(pants,'pants');C.jeans_details(pants,items['P01'],mats)
    print('C03_BUILD_SHOES',flush=True);C.shoes(items['F01'],mats)
    for code in ['T03','P01','F01']:
        for ob in items[code].objects:
            ob['wardrobe_id']=code
            if ob.type=='MESH':W.metric_uv(ob,'top' if code=='T03' else 'detail')
        print('C03_BIND '+code,flush=True)
        if code!='F01':G.bind(list(items[code].objects),body,rig)
    for ob in items['F01'].objects:
        if ob.type!='MESH':continue
        cx=sum(v.co.x for v in ob.data.vertices)/len(ob.data.vertices);name='foot.L' if cx>0 else 'foot.R'
        for group in list(ob.vertex_groups):ob.vertex_groups.remove(group)
        group=ob.vertex_groups.new(name=name);group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
        if not any(mod.type=='ARMATURE' for mod in ob.modifiers):
            arm=ob.modifiers.new('M02 footwear rigid foot binding','ARMATURE');arm.object=rig;ob.parent=rig
    print('C03_BUILD_MASK',flush=True)
    mask=C.balaclava(items['B03'],body)
    for group in list(mask.vertex_groups):mask.vertex_groups.remove(group)
    for mod in list(mask.modifiers):
        if mod.type=='ARMATURE':mask.modifiers.remove(mod)
    # Материал маски остаётся нативным исходником с отдельной фактурой хлопка.
    B.detail('B03',mask,items['B03'],mask.data.materials[0],bpy.data.materials['balaclava_thread'])
    B.bind(items['B03'],rig)
    print('C03_PAINT',flush=True)
    finish_materials({code:items[code] for code in ['T03','P01','F01']},mats,out)
    for mod,vis,ren in masks:mod.show_viewport=vis;mod.show_render=ren
    for code,col in items.items():
        col.asset_mark();col.asset_data.description=code+' | C03 artistic refinement | M02 | editable UCUPaint'
        for ob in col.objects:
            ob.hide_set(False)
            for prop in ['hide_render','hide_viewport']:
                try:ob.driver_remove(prop)
                except TypeError:pass
                setattr(ob,prop,False)
    # Удалённые части больше не участвуют в переключателях; исходный контроллер сохранён для волос.
    for ob in bpy.data.objects:
        if ob.type=='CURVES' and 'Chestnut' in ob.name:ob.hide_render=True;ob.hide_set(True)
    scene=studio(args.samples);D.frame((0,0,.94),2.55)
    bpy.ops.file.pack_all();scene.camera=bpy.data.objects['C03_ThreeQuarter']
    file=out/'C03_Refinement_M02.blend';bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False)
    report={'source':str(SOURCE),'candidate':str(file),'items':[{'id':c,'collection':col.name,'objects':len(col.objects)} for c,col in items.items()],
        'source_body':str(G.SOURCE),'stage':'editable art refinement, not game export',
        'refs':'Original owner C03 sheet; 11 owner-supplied finish references. No mesh or texture extracted from reference games.'}
    (out/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    render(out,args.views,args.samples);print('C03_BUILD_PASS '+str(file),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--version',default='probe_v01');p.add_argument('--views',default='ThreeQuarter,Shoes,Jacket');p.add_argument('--samples',type=int,default=32)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);build(args)
