"""Доводка построенной библиотеки с сохранением прежних кандидатов и расчёта ткани."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse
import addon_utils
import bpy
import bmesh
import importlib
import json
import math
import shutil
from mathutils import Vector
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_materials as M

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'_asset_src/npc_wardrobe'
DYES={'work_blue':(.015,.029,.055),'track_red':(.078,.009,.016),
      'nylon_olive':(.055,.065,.048),'field_olive':(.068,.078,.043),
      'cargo_olive':(.070,.074,.043),'denim':(.012,.026,.044),
      'work_grey':(.052,.056,.054),'combat_knit':(.036,.041,.030),
      'leather_brown':(.055,.024,.010),'leather_field':(.083,.046,.022),
      'suede':(.052,.042,.029)}


def active_points(obj):
    return obj.data.shape_keys.key_blocks[-1].data if obj.data.shape_keys else obj.data.vertices


def connected_components(mesh):
    adjacent=[[] for _ in mesh.vertices]
    for edge in mesh.edges:
        a,b=edge.vertices;adjacent[a].append(b);adjacent[b].append(a)
    pending=set(range(len(mesh.vertices)))
    while pending:
        start=pending.pop();group=[start];stack=[start]
        while stack:
            i=stack.pop()
            for j in adjacent[i]:
                if j in pending: pending.remove(j);group.append(j);stack.append(j)
        yield group


def oriented_normal(normal,preferred):
    return normal if normal.dot(preferred)>=0 else -normal


def fit_detail(obj,surface,preferred,offset=.0022):
    preferred=Vector(preferred)
    detail=obj.name.lower()
    rigid=any(token in detail for token in ['stitch','thread','button','snap','teeth','pull tab','seam','piping'])
    if rigid:
        for indices in connected_components(obj.data):
            centre=sum((obj.data.vertices[i].co for i in indices),Vector())/len(indices)
            point,normal,_,distance=surface.nearest(centre)
            if point is None: continue
            normal=oriented_normal(normal,preferred)
            delta=point+normal*(.004 if 'button' in detail or 'snap' in detail else offset)-centre
            for i in indices: obj.data.vertices[i].co+=delta
    else:
        for vertex in obj.data.vertices:
            point,normal,_,distance=surface.nearest(vertex.co)
            if point is None: continue
            normal=oriented_normal(normal,preferred)
            allowance=.004 if 'cargo' in detail else offset
            vertex.co=point+normal*allowance
    obj.data.update()


def waist_fit(items):
    for code,col in items.items():
        if not code.startswith('T'): continue
        main=next(obj for obj in col.objects if 'sewn main surface' in obj.name)
        if main.data.shape_keys:
            source=main.data.shape_keys.key_blocks[0].data
            target=active_points(main)
            for a,b in zip(source,target):
                blend=1-G.smooth(1.085,1.17,a.co.z)
                b.co=b.co.lerp(a.co,blend)
        pants={'T00':'P02','T01':'P01','T02':'P02','T03':'P01','T04':'P03','T05':'P04','T06':'P04'}[code]
        lower=next(obj for obj in items[pants].objects if 'sewn trouser panels' in obj.name)
        # Зазор учитывает толщину карманов и ширинки; проверяется сглаженная сетка.
        W.resolve_layers(main,lower,.018)
        surface=W.outer_surface(main)
        for obj in col.objects:
            if obj==main: continue
            text=obj.name.lower()
            if any(token in text for token in ['collar','hood','cuff']): continue
            front=1 if any(token in text for token in ['back yoke','elbow']) else -1
            fit_detail(obj,surface,(0,front,0))


def pants_fit(items):
    for code in ['P01','P02','P03','P04']:
        col=items[code]
        main=next(obj for obj in col.objects if 'sewn trouser panels' in obj.name)
        if code=='P04':
            for vertex in active_points(main):
                p=vertex.co
                influence=1-G.smooth(.22,.30,p.z)
                side=1 if p.x>0 else -1
                centre=side*.094
                p.x=centre+(p.x-centre)*(1-.20*influence)
                p.y=-.007+(p.y+.007)*(1-.28*influence)
        surface=W.outer_surface(main)
        for obj in col.objects:
            if obj==main: continue
            text=obj.name.lower()
            centre=sum((vertex.co for vertex in obj.data.vertices),Vector())/len(obj.data.vertices)
            if 'cargo' in text or 'outer leg seam' in text: preferred=(1 if centre.x>0 else -1,0,0)
            else: preferred=(0,1 if 'rear' in text or centre.y>0 else -1,0)
            fit_detail(obj,surface,preferred)


def waist_bands(items,mats,body,rig):
    for code in ['T02','T03','T04']:
        if code not in items: continue
        col=items[code]
        main=next(obj for obj in col.objects if 'sewn main surface' in obj.name)
        paths=W.lower_boundary(main,W.TOPS[code]['length'])
        for loop in paths:
            if len(loop)<20: continue
            if (loop[0]-loop[-1]).length<.002: loop=loop[:-1]
            verts=[];faces=[];n=len(loop)
            for row in range(6):
                t=row/5
                for p in loop:
                    radial=Vector((p.x,p.y+.01,0)).normalized()
                    verts.append(p+Vector((0,0,.028*t))+radial*(.003-.0005*math.sin(PI*t)))
            for row in range(5):
                for i in range(n):
                    j=(i+1)%n;faces.append((row*n+i,row*n+j,(row+1)*n+j,(row+1)*n+i))
            mat=mats['rib_dark'] if code=='T04' else mats[W.TOPS[code]['fabric']]
            obj=W.object_mesh(code+' | fitted elastic waistband',verts,faces,col,mat,sub=1,thickness=.0015)
            W.metric_uv(obj)
            M.attributes(obj,code)
            G.bind([obj],body,rig)


def undershirt(items,root,mats,body,rig,controls):
    source=next(obj for obj in items['T00'].objects if 'sewn main surface' in obj.name)
    evaluated=source.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=evaluated.to_mesh()
    verts=[];faces=[];indices={}
    for face in mesh.polygons:
        if not all(mesh.vertices[i].co.z>1.475 and abs(mesh.vertices[i].co.x)<.10 for i in face.vertices): continue
        result=[]
        for i in face.vertices:
            if i not in indices: indices[i]=len(verts);verts.append(mesh.vertices[i].co.copy())
            result.append(indices[i])
        faces.append(tuple(result))
    evaluated.to_mesh_clear()
    col=G.collection('Fitting | shared T00 collar insert',root);col['wardrobe_id']='T00'
    obj=W.object_mesh('T00 | visible undershirt collar',verts,faces,col,mats['jersey'],sub=0,thickness=0)
    W.metric_uv(obj);M.attributes(obj,'T00');G.bind([obj],body,rig)
    for path in ['hide_render','hide_viewport']:
        driver=obj.driver_add(path).driver
        for name,key in [('outfit','Комплект'),('preview','Предмет')]:
            variable=driver.variables.new();variable.name=name;variable.targets[0].id=controls;variable.targets[0].data_path='["'+key+'"]'
        driver.expression='not (preview == 0 and (outfit == 2 or outfit == 3 or outfit == 4))'


def refresh_weights(objects,body):
    for obj in objects:
        if obj.type!='MESH': continue
        if obj.data.users>1: obj.data=obj.data.copy()
        G.activate(obj)
        modifier=obj.modifiers.new('Final fitting weights refresh','DATA_TRANSFER')
        modifier.object=body;modifier.use_vert_data=True;modifier.data_types_verts={'VGROUP_WEIGHTS'}
        modifier.vert_mapping='POLYINTERP_NEAREST';modifier.layers_vgroup_select_src='ALL';modifier.layers_vgroup_select_dst='NAME'
        while obj.modifiers[0]!=modifier: bpy.ops.object.modifier_move_up(modifier=modifier.name)
        bpy.ops.object.modifier_apply(modifier=modifier.name)


def boot_weights(items,rig):
    for code in ['F01','F02','F02B','F03']:
        for obj in items[code].objects:
            centre=sum((vertex.co.x for vertex in obj.data.vertices))/len(obj.data.vertices)
            side='L' if centre>0 else 'R'
            foot='foot.'+side;leg='lowerleg02.'+side
            if leg not in rig.data.bones: leg='lowerleg01.'+side
            groups={name:obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name) for name in [foot,leg]}
            deform=[group for group in obj.vertex_groups if group.name in rig.data.bones and rig.data.bones[group.name].use_deform]
            for vertex in obj.data.vertices:
                for group in deform:
                    try: group.remove([vertex.index])
                    except RuntimeError: pass
                weight=G.smooth(.105,.245,vertex.co.z)*.85
                if any(token in obj.name for token in ['outsole','tread','welt','midsole']): weight=0
                groups[foot].add([vertex.index],1-weight,'REPLACE')
                if weight>0: groups[leg].add([vertex.index],weight,'REPLACE')


def native_polish(items,mats):
    U=importlib.import_module('bl_ext.blender_org.ucupaint');M.U=U
    for key,mat in mats.items():
        group=next((node for node in mat.node_tree.nodes if node.type=='GROUP' and getattr(node.node_tree,'yp',None) and node.node_tree.yp.is_ypaint_node),None)
        if group is None: continue
        tree=group.node_tree
        base=next(layer for layer in tree.yp.layers if layer.name.startswith('01 |'))
        if key in DYES:
            ch=next(channel for root,channel in zip(tree.yp.channels,base.channels) if root.name=='Color')
            M.sync(ch,'override_color',DYES[key]);mat.diffuse_color=(*DYES[key],1)
        shader=next(node for node in mat.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
        shader.inputs['Sheen Weight'].default_value=.065 if key in M.SCAN else .015
    # Плавная маска и шов реглана отделяют ткани без ступенек индексов материала.
    code='T05';col=items[code];mat=mats['combat_knit']
    main=next(obj for obj in col.objects if 'sewn main surface' in obj.name)
    for face in main.data.polygons: face.material_index=0
    attribute=main.data.color_attributes.get('CombatSleeveRegion') or main.data.color_attributes.new('CombatSleeveRegion','FLOAT_COLOR','CORNER')
    for loop in main.data.loops:
        p=main.data.vertices[loop.vertex_index].co
        boundary=.075+(1.535-p.z)*.90
        value=G.smooth(boundary-.006,boundary+.006,abs(p.x))
        attribute.data[loop.index].color=(value,value,value,1)
    G.activate(main)
    group=next(node for node in mat.node_tree.nodes if node.type=='GROUP' and getattr(node.node_tree,'yp',None) and node.node_tree.yp.is_ypaint_node)
    ly=M.layer(group.node_tree,'10 | woven raglan sleeve colour',color=DYES['field_olive'],rough=.78)
    M.masked(ly,'CombatSleeveRegion')


def main(args):
    global PI
    PI=math.pi
    source=args.source.resolve();out=WORK/args.version;out.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bpy.context.preferences.use_preferences_save=False
    module='bl_ext.blender_org.ucupaint'
    if module not in bpy.context.preferences.addons: bpy.context.preferences.addons.new().module=module
    addon_utils.enable(module,default_set=False,persistent=False)
    body=bpy.data.objects['M02_Body_Head'];rig=bpy.data.objects['M02_New_Anatomical_Rig'];controls=bpy.data.objects['RING | Wardrobe Controls']
    root=bpy.data.collections['09_Ring_Original_Wardrobe']
    items={col['wardrobe_id']:col for col in root.children if 'wardrobe_id' in col}
    mats={name:bpy.data.materials[name] for name in set(M.SCAN)|{'thread_dark','thread_jeans','thread_boot','hardware','button','zip_tape','piping','rubber','midsole'} if name in bpy.data.materials}
    # Для посадки временно вычисляются все поверхности скрытых комплектов.
    muted=[]
    for col in items.values():
        for obj in col.objects:
            if obj.animation_data:
                for curve in obj.animation_data.drivers:
                    muted.append(curve);curve.mute=True
            obj.hide_viewport=False;obj.hide_render=False
    bpy.context.view_layer.update()
    pants_fit(items);waist_fit(items)
    print('WARDROBE_POLISH fitting complete',flush=True)
    waist_bands(items,mats,body,rig)
    for col in items.values():
        for obj in col.objects:
            if obj.type=='MESH': M.attributes(obj,col['wardrobe_id'][:3])
    refresh_weights([obj for col in items.values() for obj in col.objects],body)
    boot_weights(items,rig)
    native_polish(items,mats)
    undershirt(items,root,mats,body,rig,controls)
    # Новые резинки получают те же переключатели видимости, что и основная вещь.
    for code,col in items.items():
        if not code.startswith('T'): continue
        template=next(obj for obj in col.objects if 'sewn main surface' in obj.name)
        for obj in col.objects:
            if 'fitted elastic waistband' not in obj.name: continue
            for path in ['hide_render','hide_viewport']:
                original=next(curve for curve in template.animation_data.drivers if curve.data_path==path)
                driver=obj.driver_add(path).driver;driver.expression=original.driver.expression
                for old in original.driver.variables:
                    variable=driver.variables.new();variable.name=old.name;variable.targets[0].id=controls;variable.targets[0].data_path=old.targets[0].data_path
    for curve in muted: curve.mute=False
    controls['Комплект']=1;controls['Предмет']=0;controls.update_tag();bpy.context.view_layer.update()
    scene=bpy.context.scene;scene.cycles.samples=args.samples
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for device in prefs.devices: device.use=device.type=='OPTIX'
    scene.cycles.device='GPU'
    scene.camera=bpy.data.objects['Wardrobe_ThreeQuarter']
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(out/'RING_Wardrobe.blend'),check_existing=False)
    for name in ['wardrobe_report.json','materials_report.json','original_plaid_repeat.png']:
        shutil.copy2(source.parent/name,out/name)
    for preset in range(1,7):
        controls['Комплект']=preset;controls.update_tag();bpy.context.view_layer.update()
        for view in args.render.split(','):
            scene.camera=bpy.data.objects['Wardrobe_'+view];scene.render.filepath=str(out/('C%02d_%s.png'%(preset,view.lower())))
            bpy.ops.render.render(write_still=True)
            print('WARDROBE_POLISHED C%02d %s'%(preset,view),flush=True)
    print('WARDROBE_POLISH_PASS '+str(out/'RING_Wardrobe.blend'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path)
    parser.add_argument('--version',default='wardrobe_polished_v02');parser.add_argument('--samples',type=int,default=64)
    parser.add_argument('--render',default='Front,ThreeQuarter,Back')
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    main(parser.parse_args(argv))
