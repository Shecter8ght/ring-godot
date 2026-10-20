"""Контроль наружных поверхностей: макушка, швы реглана и спокойные складки брюк."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,addon_utils,bpy,math,json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_polish as P
import wardrobe_balaclavas as B
import wardrobe_finish as F

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/npc_wardrobe'


def cover_head(p,tree,maximum):
    cy=-.035;a=math.atan2(p.x,-(p.y-cy));direction=Vector((math.sin(a),-math.cos(a),0))
    if p.z>1.735:
        sample=p.z-.006
        hit,_,_,_=tree.ray_cast(Vector((0,cy,sample))+direction*.4,-direction,.8)
        if hit is not None:
            radius=(hit-Vector((0,cy,sample))).dot(direction)+.0055
        else:
            radius=.007*math.sqrt(max(.00001,1-((p.z-(maximum+.005))/.008)**2))
        p.x=direction.x*radius;p.y=cy+direction.y*radius
    elif p.z<1.56:
        hit,_,_,_=tree.ray_cast(Vector((0,cy,p.z))+direction*.4,-direction,.8)
        if hit is not None:
            radius=(hit-Vector((0,cy,p.z))).dot(direction)+.004
            current=math.hypot(p.x,p.y-cy);amount=1-G.smooth(1.535,1.56,p.z)
            radius=G.mix(current,radius,amount);p.x=direction.x*radius;p.y=cy+direction.y*radius


def soften_trousers(main,code):
    cfg=W.PANTS[code]
    for vertex in F.points(main):
        p=vertex.co;side=1 if p.x>0 else -1;theta=math.atan2(p.y+.01,p.x-side*.098)
        normal=Vector((math.cos(theta),math.sin(theta),0));front=G.smooth(.01,-.07,p.y)
        knee=math.exp(-((p.z-(.515+.015*side))/.105)**2)
        ankle=math.exp(-((p.z-(cfg['hem']+.067))/.067)**2)
        old=.0064*math.sin(157*p.z+3.1*theta+side)*knee+.007*math.sin(188*p.z-2.3*theta+side)*ankle
        new=.0029*math.sin(112*p.z+3.1*theta+side)*knee+.0041*math.sin(143*p.z-2.3*theta+side)*ankle
        p+=normal*(new-old)
    main.data.update()


def main(args):
    source=args.source.resolve();out=WORK/args.version;out.mkdir(exist_ok=True,parents=True)
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
    items={c['wardrobe_id']:c for c in bpy.data.collections['09_Ring_Original_Wardrobe'].children if c.asset_data and c.get('wardrobe_id')}
    flags=[(m,m.show_viewport) for m in body.modifiers if m.type=='MASK']
    for m,_ in flags: m.show_viewport=False
    for col in items.values():
        for obj in col.objects:
            if obj.animation_data:
                for curve in obj.animation_data.drivers: curve.mute=True
            obj.hide_viewport=False;obj.hide_render=False
    bpy.context.view_layer.update()
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh()
    vertices=[v.co.copy() for v in mesh.vertices];maximum=max(v.z for v in vertices)
    faces=[tuple(f.vertices) for f in mesh.polygons if all(vertices[i].z>1.43 and abs(vertices[i].x)<.145 for i in f.vertices)]
    head=BVHTree.FromPolygons(vertices,faces);ev.to_mesh_clear()
    for code,col in items.items():
        if code.startswith('B'):
            for obj in col.objects:
                for vertex in obj.data.vertices: cover_head(vertex.co,head,maximum)
                obj.data.update()
        elif code.startswith('P'):
            main_obj=next(o for o in col.objects if 'sewn trouser panels' in o.name);soften_trousers(main_obj,code)
            surface=W.outer_surface(main_obj)
            for obj in col.objects:
                if obj==main_obj: continue
                centre=sum((v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
                preferred=(1 if centre.x>0 else -1,0,0) if 'cargo' in obj.name else (0,1 if 'rear' in obj.name or centre.y>0 else -1,0)
                P.fit_detail(obj,surface,preferred,.0018)
        elif code.startswith('T'):
            main_obj=next(o for o in col.objects if 'sewn main surface' in o.name);surface=W.outer_surface(main_obj)
            for obj in col.objects:
                if obj==main_obj or any(t in obj.name for t in ['collar','hood','cuff','waistband','cream shoulder piping']): continue
                preferred=(0,1 if any(t in obj.name for t in ['back yoke','elbow']) else -1,0)
                P.fit_detail(obj,surface,preferred,.0018)
            if code=='T05':
                attribute=main_obj.data.color_attributes['CombatSleeveRegion']
                for loop in main_obj.data.loops:
                    p=F.points(main_obj)[loop.vertex_index].co
                    threshold=.075+(1.535-p.z)*.90;v=G.smooth(threshold-.020,threshold+.020,abs(p.x))
                    attribute.data[loop.index].color=(v,v,v,1)
                for side in [-1,1]:
                    path=W.path_on(surface,[(side*(.075+(1.535-z)*.90),z) for z in [1.385+i*.145/80 for i in range(81)]],offset=.0019)
                    seam=G.stitches('T05 | raglan flatlock '+str(side),[path],col,bpy.data.materials['thread_dark'],radius=.00016)
                    if seam: seam['wardrobe_id']='T05';W.metric_uv(seam);M.attributes(seam,'T05');G.bind([seam],body,rig)
        print('WARDROBE_CLEARANCE '+code,flush=True)
    for modifier,visible in flags: modifier.show_viewport=visible
    for obj in bpy.data.objects:
        if obj.animation_data:
            for curve in obj.animation_data.drivers: curve.mute=False
    # Новые швы получают штатные драйверы предмета.
    template=next(o for o in items['T05'].objects if 'sewn main surface' in o.name)
    for obj in items['T05'].objects:
        if 'raglan flatlock' not in obj.name: continue
        for path in ['hide_render','hide_viewport']:
            original=next(c for c in template.animation_data.drivers if c.data_path==path)
            driver=obj.driver_add(path).driver;driver.expression=original.driver.expression
            for old in original.driver.variables:
                v=driver.variables.new();v.name=old.name;v.targets[0].id=control;v.targets[0].data_path=old.targets[0].data_path
    control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
    scene=bpy.context.scene;scene.cycles.samples=args.samples
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU';scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'RING_NPC_Wardrobe.blend'),check_existing=False)
    for number in range(1,7):
        control['Комплект']=number;control.update_tag();bpy.context.view_layer.update()
        for view in ['Front','ThreeQuarter','Back']:
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.resolution_x=1600;scene.render.resolution_y=1800
            scene.render.filepath=str(out/f'C{number:02d}_{view.lower()}.png');bpy.ops.render.render(write_still=True)
        scene.camera=bpy.data.objects['Balaclava_ThreeQuarter'];scene.render.resolution_x=1100;scene.render.resolution_y=1200
        scene.render.filepath=str(out/f'B{number:02d}_threequarter.png');bpy.ops.render.render(write_still=True)
    print('WARDROBE_CLEARANCE_PASS '+str(out/'RING_NPC_Wardrobe.blend'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('--version',default='wardrobe_final_v04');parser.add_argument('--samples',type=int,default=64)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);main(args)
