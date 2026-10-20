"""Финальная посадка ткани, окантовка и согласованные крупные планы библиотеки NPC."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,addon_utils,bpy,bmesh,importlib,json,math,io
from contextlib import redirect_stdout
from mathutils import Vector
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_materials as M
import wardrobe_polish as P
import wardrobe_balaclavas as B

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/npc_wardrobe'
PI=math.pi
OldSurface=G.BodySurface


class OuterSurface(OldSurface):
    def __init__(self,obj):
        flags=[(m,m.show_viewport) for m in obj.modifiers if m.type=='SOLIDIFY']
        for m,_ in flags: m.show_viewport=False
        bpy.context.view_layer.update()
        super().__init__(obj)
        for m,flag in flags: m.show_viewport=flag
        bpy.context.view_layer.update()


def points(obj): return obj.data.shape_keys.key_blocks[-1].data if obj.data.shape_keys else obj.data.vertices


def cloth_folds(obj,code):
    if code.startswith('T'):
        cfg=W.TOPS[code]
        source=obj.data.shape_keys.key_blocks[0].data
        for original,target in zip(source,points(obj)):
            p=target.co;s=original.co
            if s.z<1.20 and abs(s.x)<.24:
                blend=1-G.smooth(1.13,1.20,s.z)
                width=G.profile(s.z,[(cfg['length'],.216),(1.06,.216),(1.20,.199)])
                u=G.clamp(s.x/(cfg['width']+.005),-1,1)
                angle=math.sqrt(max(0,1-u*u))
                front=s.y<-.008
                y=(-.187 if front else .154)*angle-.012*(1-angle)
                p.x=G.mix(p.x,u*width,blend);p.y=G.mix(p.y,y,blend)
            # Вырез сохраняет раскрой: симуляция не должна затягивать ворот к горлу.
            if abs(s.x)<.11 and s.z>1.40 and s.y<-.015:
                factor=G.smooth(1.40,1.46,s.z)*(1-G.smooth(.08,.115,abs(s.x)))
                p.z=G.mix(p.z,s.z,factor)
                p.y=G.mix(p.y,s.y-.004,factor)
            if abs(p.x)<.23:
                front=1 if p.y<-.012 else -1
                region=G.smooth(.015,.07,abs(p.x))*(1-G.smooth(.20,.23,abs(p.x)))
                hang=(.0042*math.sin(55*p.x+3*p.z)+.0014*math.sin(113*p.x-17*p.z))*(1-G.smooth(1.25,1.43,p.z))
                fan=0.
                for index in range(4):
                    line=1.325-index*.032-.54*(.215-abs(p.x))
                    distance=p.z-line
                    fan+=(.0052-index*.0006)*(math.exp(-(distance/.010)**2)-.42*math.exp(-((distance+.016)/.014)**2))
                hem=math.exp(-((p.z-(cfg['length']+.045))/.050)**2)*.0045*math.sin(83*p.x+31*p.z)
                p.y-=front*(hang+fan+hem)*region
            else:
                x=abs(p.x);theta=math.atan2(p.z-1.464,p.y+.003)
                normal=Vector((0,math.cos(theta),math.sin(theta)))
                elbow=math.exp(-((x-.465)/.065)**2)
                wrist=math.exp(-((x-.686)/.037)**2)
                fold=(.0050*math.sin(167*x+2.2*theta)+.0022*math.sin(99*x-3*theta))*elbow
                fold+=.0038*math.sin(198*x-2.3*theta)*wrist
                p+=normal*fold
    else:
        cfg=W.PANTS[code]
        for target in points(obj):
            p=target.co;side=1 if p.x>0 else -1
            theta=math.atan2(p.y+.01,p.x-side*.098)
            normal=Vector((math.cos(theta),math.sin(theta),0))
            front=G.smooth(.01,-.07,p.y)
            centre=.515+.015*side
            knee=math.exp(-((p.z-centre)/.105)**2)
            ankle=math.exp(-((p.z-(cfg['hem']+.067))/.067)**2)
            thigh=math.exp(-((p.z-(.87-.22*abs(p.x)))/.055)**2)
            wave=.0064*math.sin(157*p.z+3.1*theta+side)*knee
            wave+=.0070*math.sin(188*p.z-2.3*theta+side)*ankle
            wave+=.0044*math.sin(164*p.z+4*theta)*thigh*front
            p+=normal*wave
    obj.data.update();bpy.context.view_layer.update()


def fitted_cuffs(code,col,main,mats):
    paths=B.boundary_paths(main)
    for obj in list(col.objects):
        if 'sleeve cuff' in obj.name or 'cuff button' in obj.name: bpy.data.objects.remove(obj,do_unlink=True)
    mat=mats['rib_dark'] if code=='T04' else mats['field_olive'] if code=='T05' else mats[W.TOPS[code]['fabric']]
    for path in paths:
        centre=sum(path,Vector())/len(path)
        if abs(centre.x)<.60: continue
        side=1 if centre.x>0 else -1;n=len(path);verts=[];faces=[]
        for row in range(6):
            t=row/5
            for point in path:
                radial=Vector((0,point.y-centre.y,point.z-centre.z))
                verts.append(centre+radial*(1.035-.045*t)+Vector((side*(-.028+.028*t),0,0)))
        for row in range(5):
            for i in range(n):
                j=(i+1)%n;faces.append((row*n+i,row*n+j,(row+1)*n+j,(row+1)*n+i))
        cuff=W.object_mesh(code+' | fitted sleeve cuff '+str(side),verts,faces,col,mat,sub=1,thickness=.0012)
        W.metric_uv(cuff)
        if code in ['T01','T02','T06']:
            p=centre+Vector((-side*.015,-max((abs(p.y-centre.y) for p in path))-.002,0))
            W.button(code+' | cuff button '+str(side),p,col,mats['button'])


def correct_hood(code,col):
    main=next(obj for obj in col.objects if 'tailored hood shell' in obj.name)
    bm=bmesh.new();bm.from_mesh(main.data)
    boundary=[v for v in bm.verts if v.is_boundary and v.co.z>B.DESIGNS[code]['bottom']+.025]
    for _ in range(12):
        result={}
        for vertex in boundary:
            adjacent=[edge.other_vert(vertex) for edge in vertex.link_edges if edge.is_boundary]
            if len(adjacent)==2: result[vertex]=vertex.co.lerp((adjacent[0].co+adjacent[1].co)/2,.55)
        for v,co in result.items(): v.co=co
    # Закруглённая макушка без цилиндрического выступа и плавный чехол ушей.
    for v in bm.verts:
        p=v.co;cy=-.035;a=math.atan2(p.x,-(p.y-cy));r=math.hypot(p.x,p.y-cy)
        if p.z>1.739:
            z=p.z
            desired=.087*math.sqrt(max(.00002,1-((z-1.681)/.108)**2))
            factor=G.smooth(1.739,1.765,z)
            r=G.mix(r,desired,factor);p.x=math.sin(a)*r;p.y=cy-math.cos(a)*r
    bm.to_mesh(main.data);bm.free();main.data.update()
    # Перестроить окантовку на исправленном крае; старые нитки не оставлять рядом.
    for obj in list(col.objects):
        if obj!=main: bpy.data.objects.remove(obj,do_unlink=True)
    mat=main.data.materials[0];thread=bpy.data.materials['balaclava_thread']
    B.detail(code,main,col,mat,thread)
    rig=bpy.data.objects['M02_New_Anatomical_Rig']
    for obj in col.objects:
        if obj==main: continue
        obj['wardrobe_id']=code
        for name in ['head','neck01']: obj.vertex_groups.new(name=name)
        for v in obj.data.vertices:
            weight=G.smooth(1.516,1.574,v.co.z)
            obj.vertex_groups['head'].add([v.index],weight,'REPLACE');obj.vertex_groups['neck01'].add([v.index],1-weight,'REPLACE')
        arm=obj.modifiers.new('M02 anatomical head and neck','ARMATURE');arm.object=rig;obj.parent=rig


def material_finish(mats):
    U=importlib.import_module('bl_ext.blender_org.ucupaint');M.U=U
    with redirect_stdout(io.StringIO()):
        for key,mat in mats.items():
            node=next((n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node),None)
            if not node: continue
            tree=node.node_tree;cloth=key in M.SCAN and not key.startswith('leather') and key!='suede'
            for ly in tree.yp.layers:
                for root,ch in zip(tree.yp.channels,ly.channels):
                    if ly.name.startswith('01 |') and root.name=='Roughness' and cloth: M.sync(ch,'override_value',.86)
                    if ly.name.startswith('05 |') and cloth: M.sync(ly,'intensity_value',.16)
                    if ly.name.startswith('06 |'):
                        if root.name=='Color':
                            base=mat.diffuse_color[:3]
                            color=(.082,.115,.147) if key=='denim' else tuple(min(.7,v*1.45+.016) for v in base)
                            M.sync(ch,'override_color',color)
                        if root.name=='Roughness' and cloth: M.sync(ch,'override_value',.79)
                    if ly.name.startswith('07 |') and root.name=='Color':
                        M.sync(ch,'override_color',tuple(min(.7,v*1.20+.006) for v in mat.diffuse_color[:3]))
                # Новые маски подключаются и к группе слоя, и к общей группе.
                U.node_connections.reconnect_layer_nodes(ly)
            U.node_connections.reconnect_yp_nodes(tree)


def main(args):
    source=args.source.resolve();out=WORK/args.version;out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    for cfg in B.DESIGNS.values(): M.SCAN[cfg['fabric']]=cfg['scan']
    root=bpy.data.collections['09_Ring_Original_Wardrobe'];body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig'];control=bpy.data.objects['RING | Wardrobe Controls']
    items={col['wardrobe_id']:col for col in root.children if col.get('wardrobe_id') and col.asset_data}
    mats={m.name:m for m in bpy.data.materials if m.use_nodes}
    body_masks=[(m,m.show_viewport) for m in body.modifiers if m.type=='MASK']
    for m,_ in body_masks: m.show_viewport=False
    muted=[]
    for col in items.values():
        for obj in col.objects:
            if obj.animation_data:
                for curve in obj.animation_data.drivers: muted.append(curve);curve.mute=True
            obj.hide_render=False;obj.hide_viewport=False
    bpy.context.view_layer.update();G.BodySurface=OuterSurface
    for code,col in items.items():
        if code.startswith('P'):
            main_obj=next(o for o in col.objects if 'sewn trouser panels' in o.name);cloth_folds(main_obj,code)
            surface=W.outer_surface(main_obj)
            for obj in col.objects:
                if obj==main_obj: continue
                centre=sum((v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
                preferred=(1 if centre.x>0 else -1,0,0) if 'cargo' in obj.name else (0,1 if 'rear' in obj.name or centre.y>0 else -1,0)
                P.fit_detail(obj,surface,preferred,.0018)
        elif code.startswith('T'):
            main_obj=next(o for o in col.objects if 'sewn main surface' in o.name)
            cloth_folds(main_obj,code)
            for obj in list(col.objects):
                if obj!=main_obj: bpy.data.objects.remove(obj,do_unlink=True)
            W.top_details(code,col,main_obj,mats)
            if code!='T00': fitted_cuffs(code,col,main_obj,mats)
            if code in ['T02','T03','T04']:
                # Резинка строится после посадки, непосредственно по нижнему краю.
                P.PI=PI;P.waist_bands({code:col},mats,body,rig)
            detail_objs=[obj for obj in col.objects if obj!=main_obj and not obj.vertex_groups]
            G.bind(detail_objs,body,rig)
            if code=='T04':
                surface=W.outer_surface(main_obj)
                for obj in list(col.objects):
                    if 'cream shoulder piping' not in obj.name: continue
                    side=1 if '1'==obj.name[-1:] and '-1' not in obj.name else -1
                    bpy.data.objects.remove(obj,do_unlink=True)
                    path=[]
                    for step in range(160):
                        x=side*G.mix(.084,.715,step/159)
                        point,normal,_,_=surface.nearest(Vector((x,-.026,1.54)))
                        if normal.z<0: normal=-normal
                        path.append(point+normal*.0016)
                    new=G.line_mesh(code+' | cream shoulder piping '+str(side),[path],.00085,col,mats['piping'])
                    W.metric_uv(new);G.bind([new],body,rig)
            print('WARDROBE_FINISH '+code,flush=True)
        elif code.startswith('B'):
            correct_hood(code,col)
            print('BALACLAVA_FINISH '+code,flush=True)
        for obj in col.objects:
            if obj.type=='MESH': M.attributes(obj,code[:3])
    # Старый ворот футболки выступал сквозь закрытые куртки.
    for col in list(root.children):
        if col.name.startswith('Fitting |'):
            for obj in list(col.objects): bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.collections.remove(col)
    # Под рубашками остаётся самостоятельная нижняя футболка, в комплекте шея
    # закрывается сменной балаклавой; случайных накладок на куртках нет.
    material_finish(mats)
    P.refresh_weights([obj for code,col in items.items() if not code.startswith('B') for obj in col.objects],body)
    P.boot_weights(items,rig)
    for modifier,visible in body_masks: modifier.show_viewport=visible
    for code,col in items.items():
        idx=col['isolation_index'];presets=col.get('used_in_outfits','')
        if code.startswith('B'): continue
        condition=' or '.join('outfit == '+n for n in presets.split(',') if n) or 'False'
        for obj in col.objects:
            for path in ['hide_render','hide_viewport']:
                driver=obj.driver_add(path).driver
                while driver.variables: driver.variables.remove(driver.variables[0])
                for var,key in [('outfit','Комплект'),('preview','Предмет')]:
                    v=driver.variables.new();v.name=var;v.targets[0].id=control;v.targets[0].data_path='["'+key+'"]'
                driver.expression=f'not (preview == {idx} or (preview == 0 and ({condition})))'
    B.controls({code:items[code] for code in B.DESIGNS},control)
    # Старые детали удалены: их RNA-ссылки больше не разыменовывать.
    for obj in bpy.data.objects:
        if obj.animation_data:
            for curve in obj.animation_data.drivers: curve.mute=False
    control['Комплект']=1;control['Предмет']=0;control.update_tag();bpy.context.view_layer.update()
    scene=bpy.context.scene;scene.cycles.samples=args.samples
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU';scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'RING_NPC_Wardrobe.blend'),check_existing=False)
    for number in [int(n) for n in args.presets.split(',')]:
        control['Комплект']=number;control.update_tag();bpy.context.view_layer.update()
        for view in args.render.split(','):
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.resolution_x=1600;scene.render.resolution_y=1800
            scene.render.filepath=str(out/f'C{number:02d}_{view.lower()}.png');bpy.ops.render.render(write_still=True)
        scene.camera=bpy.data.objects['Balaclava_ThreeQuarter'];scene.render.resolution_x=1100;scene.render.resolution_y=1200
        scene.render.filepath=str(out/f'B{number:02d}_threequarter.png');bpy.ops.render.render(write_still=True)
    print('WARDROBE_FINISH_PASS '+str(out/'RING_NPC_Wardrobe.blend'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    parser.add_argument('--version',default='wardrobe_finished_v03');parser.add_argument('--samples',type=int,default=64)
    parser.add_argument('--render',default='Front,ThreeQuarter,Back');parser.add_argument('--presets',default='1,2,3,4,5,6')
    main(parser.parse_args(sys.argv[sys.argv.index('--')+1:]))
