"""True high-to-low Cycles channel transfer, isolated by original component."""
from pathlib import Path
import argparse
import json
import math
import sys
import time
import traceback

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,MODEL,rows,write,sha
from uv_repair import repair,thicken_islands
import build as B
P=B.P

CHANNELS=('BaseColor','Metallic','Roughness','Normal')


def gpu():
    sc=bpy.context.scene
    sc.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'; prefs.get_devices()
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
    sc.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    sc.cycles.samples=1
    sc.cycles.use_denoising=False
    sc.render.bake.use_selected_to_active=True
    sc.render.bake.use_cage=False
    sc.render.bake.cage_extrusion=.020
    sc.render.bake.max_ray_distance=.080
    sc.render.bake.margin=8
    sc.render.bake.margin_type='EXTEND'
    sc.render.bake.use_clear=True
    sc.render.bake.normal_space='TANGENT'
    sc.render.bake.normal_r='POS_X'; sc.render.bake.normal_g='POS_Y'; sc.render.bake.normal_b='POS_Z'


def socket_record(p):
    result={}
    for socket in p.inputs:
        if hasattr(socket,'default_value'):
            v=socket.default_value
            result[socket.name]=list(v) if hasattr(v,'__len__') else v
    result['_emission_linked']=p.inputs['Emission Color'].is_linked
    result['_coat_roughness_linked']=p.inputs['Coat Roughness'].is_linked
    return result


def surface(mat,channel):
    nt=mat.node_tree
    out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
    bsdf=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    for link in list(out.inputs['Surface'].links):
        nt.links.remove(link)
    if channel=='Normal':
        nt.links.new(bsdf.outputs['BSDF'],out.inputs['Surface'])
        return
    emission=next((n for n in nt.nodes if n.get('retopo_bake')),None)
    if emission is None:
        emission=nt.nodes.new('ShaderNodeEmission'); emission['retopo_bake']=True
    for link in list(emission.inputs['Color'].links):
        nt.links.remove(link)
    if channel=='MaterialData':
        combine=next((n for n in nt.nodes if n.get('retopo_data')),None)
        if combine is None:
            combine=nt.nodes.new('ShaderNodeCombineXYZ'); combine['retopo_data']=True
        for name,target in (('Metallic','X'),('Roughness','Y')):
            source=bsdf.inputs[name]
            if source.is_linked:
                nt.links.new(source.links[0].from_socket,combine.inputs[target])
            else:
                combine.inputs[target].default_value=source.default_value
        combine.inputs['Z'].default_value=1
        nt.links.new(combine.outputs[0],emission.inputs['Color'])
        nt.links.new(emission.outputs[0],out.inputs['Surface'])
        return
    source=bsdf.inputs['Base Color']
    if source.is_linked:
        nt.links.new(source.links[0].from_socket,emission.inputs['Color'])
    else:
        value=source.default_value
        emission.inputs['Color'].default_value=tuple(value) if hasattr(value,'__len__') else (value,value,value,1)
    nt.links.new(emission.outputs[0],out.inputs['Surface'])


def final_material(original,images):
    p=next(n for n in original.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    parameters=socket_record(p)
    m=bpy.data.materials.new(original.name+' | baked retopology')
    m.use_nodes=True
    m['source_material']=original.name
    m['source_surface_recipe']=original.get('surface_recipe','')
    m['bake_source']='Untouched high-poly native UCUPaint master'
    nt=m.node_tree
    bsdf=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    for name,v in parameters.items():
        if name in bsdf.inputs:
            try:
                bsdf.inputs[name].default_value=v
            except (TypeError,ValueError):
                pass
    uv=nt.nodes.new('ShaderNodeUVMap'); uv.uv_map='BakeUV'; uv.location=(-700,100)
    nodes={}
    for i,channel in enumerate(CHANNELS):
        n=nt.nodes.new('ShaderNodeTexImage'); n.image=images[channel]
        n.label=channel+' — high to low'; n.location=(-450,250-i*270)
        n.extension='EXTEND'
        nt.links.new(uv.outputs['UV'],n.inputs['Vector']); nodes[channel]=n
    for channel,target in (('BaseColor','Base Color'),('Metallic','Metallic'),('Roughness','Roughness')):
        nt.links.new(nodes[channel].outputs['Color'],bsdf.inputs[target])
    normal=nt.nodes.new('ShaderNodeNormalMap'); normal.space='TANGENT'; normal.uv_map='BakeUV'
    normal.location=(-80,-520)
    nt.links.new(nodes['Normal'].outputs['Color'],normal.inputs['Color'])
    nt.links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
    if parameters['_emission_linked']:
        nt.links.new(nodes['BaseColor'].outputs['Color'],bsdf.inputs['Emission Color'])
    if parameters['_coat_roughness_linked']:
        nt.links.new(nodes['Roughness'].outputs['Color'],bsdf.inputs['Coat Roughness'])
    if parameters.get('Coat Weight',0)>0:
        nt.links.new(normal.outputs['Normal'],bsdf.inputs['Coat Normal'])
    m.diffuse_color=original.diffuse_color
    constant_ink(m)
    return m


def constant_ink(mat):
    """Literal source colors need no atlas samples on subpixel raised lettering."""
    key=mat.get('source_surface_recipe','') or mat.get('surface_recipe','')
    name=mat.get('source_material',mat.name).split(' | baked')[0]
    if 'R06_lettering' in name:
        rgb=(.81,.80,.69); rough=.56
    elif key=='ink_ivory' or '• ink_ivory' in name:
        rgb=(.83,.82,.71); rough=.64
    elif key=='ink_black' or '• ink_black' in name:
        rgb=(.045,.05,.04); rough=.64
    else:
        return False
    color=(*P.M.linear(rgb),1)
    p=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    for socket in ('Base Color','Metallic','Roughness','Normal','Coat Normal'):
        for link in list(p.inputs[socket].links):mat.node_tree.links.remove(link)
    p.inputs['Base Color'].default_value=color
    p.inputs['Metallic'].default_value=0; p.inputs['Roughness'].default_value=rough
    mat.diffuse_color=color
    mat['constant_source_ink']=True
    mat['constant_source_ink_srgb']=list(rgb)
    return True


def resolution(a,override):
    if override:
        return override
    if a['id']=='R06':
        return 8192
    if a['id'] in ('R04','U14_01','U13_01','U19_01'):
        return 4096
    lo,hi=P.bounds()
    return 1024 if max(hi-lo)<3.2 else 2048


def coverage(target,blue,size):
    me=target.data; me.calc_loop_triangles()
    uv=me.uv_layers['BakeUV']
    values=np.array([[tuple(uv.data[j].uv) for j in t.loops] for t in me.loop_triangles])
    area=np.abs(np.cross(values[:,1]-values[:,0],values[:,2]-values[:,0]))*.5*size*size
    centers=values.mean(axis=1)
    xy=np.clip((centers*size).astype(int),0,size-1)
    hit=blue[xy[:,1]*size+xy[:,0]]>.9
    meaningful=area>4
    misses=meaningful&~hit
    result=dict(sampled_triangles=int(meaningful.sum()),missed_triangles=int(misses.sum()),
        missed_area_fraction=float(area[misses].sum()/max(area[meaningful].sum(),1e-9)),
        method='Blue=1 emitted by high mesh, sampled at UV centroids of triangles larger than four pixels')
    result['passed']=result['missed_area_fraction']<.002
    return result


def append_high(a,low):
    # Free original names so appended HP keeps its exact component names.
    names={o:o.name for o in bpy.data.collections[MODEL].objects}
    for ob,name in names.items():
        ob.name='LP_SAVED__'+name
    with bpy.data.libraries.load(a['source_pbr'],link=False) as (src,dst):
        dst.collections=[MODEL]
    hpcol=dst.collections[0]
    bpy.context.scene.collection.children.link(hpcol)
    hp={o.name:o for o in hpcol.objects if o.type in ('MESH','FONT','CURVE')}
    if set(names[o] for o in low)!=set(hp):
        raise RuntimeError('HP/LP component names differ')
    matrices={names[ob]:ob.matrix_world.copy() for ob in low}
    # Parents outside MODEL are not linked by collection append. Use the verified
    # source-equivalent LP transforms before evaluating HP, instead of stale identity.
    for name,ob in hp.items():
        ob.parent=None
        ob.matrix_world=matrices[name]
    bpy.context.view_layer.update()
    # Evaluated high geometry preserves all source vertex attributes and UVs.
    for ob in list(hp.values()):
        matrix=ob.matrix_world.copy()
        me=B.evaluated(ob)
        if ob.type!='MESH':
            B.activate(ob); bpy.ops.object.convert(target='MESH')
        for mod in list(ob.modifiers):
            ob.modifiers.remove(mod)
        ob.data=me
        ob.parent=None; ob.matrix_world=matrix
        coordinates=np.empty(len(me.vertices)*3,np.float32); me.vertices.foreach_get('co',coordinates)
        points=coordinates.reshape(-1,3)
        for attribute,values in (
            ('RetopoSourceObjectCoord',points),
            ('RetopoSourceGeneratedCoord',(points-points.min(axis=0))/np.maximum(points.max(axis=0)-points.min(axis=0),1e-9))):
            attr=me.attributes.new(attribute,'FLOAT_VECTOR','POINT')
            attr.data.foreach_set('vector',values.ravel())
    return names,hpcol,hp


def join_high(objects):
    """One high BVH, preserving each object's native texture coordinates as fields.

    Cycles' selected-to-active CPU projection otherwise tests every source object
    for every atlas pixel, even when components are exploded far apart.
    """
    mats={m for ob in objects for m in ob.data.materials}
    visited=set()
    changes=[]
    def visit(tree):
        if tree in visited:return
        visited.add(tree)
        for node in list(tree.nodes):
            if node.type=='GROUP' and node.node_tree:
                visit(node.node_tree)
            if node.type!='TEX_COORD':continue
            for output,attribute in (('Object','RetopoSourceObjectCoord'),('Generated','RetopoSourceGeneratedCoord')):
                links=list(node.outputs[output].links)
                if not links:continue
                if output=='Object' and node.object:
                    raise RuntimeError('Explicit coordinate reference needs a separate field: '+node.object.name)
                field=tree.nodes.new('ShaderNodeAttribute'); field.attribute_name=attribute
                for link in links:
                    socket=link.to_socket; tree.links.remove(link)
                    tree.links.new(field.outputs['Vector'],socket)
                changes.append(dict(tree=tree.name,output=output,attribute=attribute))
    for mat in mats:visit(mat.node_tree)
    B.activate(objects[0])
    for ob in objects:ob.select_set(True)
    bpy.ops.object.join()
    joined=bpy.context.object; joined.name='TEMP | isolated high components, one projection BVH'
    return joined,changes


def bake_one(a,override=0,fresh_uv=False):
    start=time.time()
    model=WORK/a['retopo_model']
    folder=model.parent.parent
    report=json.loads((folder/'checks/retopology.json').read_text(encoding='utf-8'))
    assert report['passed'] and sha(a['source_pbr'])==report['source_sha256']
    bpy.ops.wm.open_mainfile(filepath=str(model))
    low=[o for o in bpy.data.collections[MODEL].objects if o.type=='MESH']
    if fresh_uv:B.unique_uv()
    size=resolution(a,override)
    if a['id'] in ('U15_01','U18_04','U19_01'):
        size=max(2048,size)
        wire_uv=thicken_islands(low,size)
    uvreport=repair(low)
    if a['id'] in ('U15_01','U18_04','U19_01'):uvreport['thin_islands_expanded']=wire_uv
    write(folder/'checks/uv.json',uvreport)
    # Final original materials are captured before HP shader rerouting.
    originals={m for o in low for m in o.data.materials}
    original_hidden={o:o.hide_render for o in low}
    original_active={o:o.data.uv_layers.active.name for o in low}
    names,hpcol,hp=append_high(a,low)
    proxies=[]
    all_hp=list(hp.values())
    maxsize=max(max(o.dimensions) for o in all_hp)
    spacing=max(5,maxsize*3)
    grid=math.ceil(len(low)**(1/3))
    for i,lo in enumerate(low):
        hi=hp[names[lo]]
        displacement=Vector((i%grid,(i//grid)%grid,i//(grid*grid)))*spacing
        hmat=hi.matrix_world.copy(); hmat.translation+=displacement; hi.matrix_world=hmat
        proxy=lo.copy(); proxy.data=lo.data.copy()
        bpy.context.scene.collection.objects.link(proxy)
        matrix=lo.matrix_world.copy(); matrix.translation+=displacement
        proxy.parent=None; proxy.matrix_world=matrix
        proxy.hide_render=False; proxy.hide_viewport=False; proxy.hide_set(False)
        proxy.data.uv_layers.active=proxy.data.uv_layers['BakeUV']
        proxy.data.uv_layers['BakeUV'].active_render=True
        proxies.append(proxy)
        lo.hide_render=True
    # One target atlas; separate high components avoid transfer from neighbours.
    B.activate(proxies[0])
    for ob in proxies:
        ob.select_set(True)
    bpy.ops.object.join()
    target=bpy.context.object; target.name='TEMP | exploded atlas bake target'
    joined_high,coordinate_fields=join_high(all_hp)
    all_hp=[joined_high]
    target.data.materials.clear()
    material=bpy.data.materials.new('TEMP | active bake image'); material.use_nodes=True
    target.data.materials.append(material)
    for f in target.data.polygons:
        f.material_index=0
    inode=material.node_tree.nodes.new('ShaderNodeTexImage')
    material.node_tree.nodes.active=inode
    mats={m for ob in all_hp for m in ob.data.materials}
    gpu()
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in all_hp+[target]:
        ob.hide_render=False; ob.hide_set(False); ob.select_set(True)
    bpy.context.view_layer.objects.active=target
    tex=folder/'textures'; tex.mkdir(exist_ok=True)
    images={}; records=[]
    coverage_report=None
    for channel in ('BaseColor','MaterialData','Normal'):
        channel_start=time.time()
        bpy.context.scene.cycles.samples=4 if channel=='Normal' else 1
        for mat in mats:
            surface(mat,channel)
        name=a['id']+'_'+channel
        image=bpy.data.images.new(name,width=size,height=size,alpha=False,float_buffer=True)
        image.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
        image.generated_color=(.5,.5,1,1) if channel=='Normal' else (0,0,0,1)
        inode.image=image
        print('BAKE_CHANNEL',a['id'],channel,size,flush=True)
        bpy.ops.object.bake(type='NORMAL' if channel=='Normal' else 'EMIT',uv_layer='BakeUV')
        # save() writes unlit scene-linear values to sRGB only for BaseColor.
        path=tex/(name+'.png')
        image.filepath_raw=str(path); image.file_format='PNG'
        image.save()
        bpy.data.images.remove(image)
        image=bpy.data.images.load(str(path),check_existing=False)
        image.colorspace_settings.name='sRGB' if channel=='BaseColor' else 'Non-Color'
        image.pack(); image.filepath='//../textures/'+path.name
        images[channel]=image
        records.append(dict(channel=channel,file='textures/'+path.name,size=list(image.size),
            colorspace=image.colorspace_settings.name,sha256=sha(path)))
        if channel=='MaterialData':
            pixels=np.empty(size*size*4,np.float32); image.pixels.foreach_get(pixels)
            pixels=pixels.reshape(-1,4)
            coverage_report=coverage(target,pixels[:,2],size)
            write(folder/'checks/bake_coverage.json',coverage_report)
            records.pop(); images.pop(channel)
            for index,key in enumerate(('Metallic','Roughness')):
                scalar=bpy.data.images.new(a['id']+'_'+key,width=size,height=size,alpha=False,float_buffer=False)
                scalar.colorspace_settings.name='Non-Color'
                rgba=np.ones_like(pixels); rgba[:,:3]=pixels[:,index,None]
                scalar.pixels.foreach_set(rgba.ravel())
                scalar.filepath_raw=str(tex/(a['id']+'_'+key+'.png')); scalar.file_format='PNG'; scalar.save()
                scalar_path=Path(scalar.filepath_raw)
                bpy.data.images.remove(scalar)
                scalar=bpy.data.images.load(str(scalar_path),check_existing=False)
                scalar.colorspace_settings.name='Non-Color'; scalar.pack()
                scalar.filepath='//../textures/'+scalar_path.name
                images[key]=scalar
                records.append(dict(channel=key,file='textures/'+a['id']+'_'+key+'.png',size=list(scalar.size),
                    colorspace='Non-Color',sha256=sha(tex/(a['id']+'_'+key+'.png'))))
            bpy.data.images.remove(image)
            del pixels,rgba
        print('BAKE_CHANNEL_DONE',a['id'],channel,round(time.time()-channel_start,1),flush=True)
    if not coverage_report or not coverage_report['passed']:
        raise RuntimeError('Bake coverage failed: '+str(coverage_report))
    new_mats={m:final_material(m,images) for m in originals}
    bpy.data.objects.remove(target,do_unlink=True)
    for ob in list(hpcol.objects):
        bpy.data.objects.remove(ob,do_unlink=True)
    bpy.data.collections.remove(hpcol)
    for lo in low:
        lo.name=names[lo]
        for index,m in enumerate(list(lo.data.materials)):
            lo.data.materials[index]=new_mats[m]
        lo.hide_render=original_hidden[lo]
        lo.data.uv_layers.active=lo.data.uv_layers['BakeUV']
    for ob,name in names.items():
        ob.name=name
    # Keep editability in the untouched native master; LP stores only its maps.
    bpy.data.orphans_purge(do_recursive=True)
    sc=bpy.context.scene
    sc['stage']='Retopology and high-to-low PBR transfer; no game import'
    sc['bake_source']=a['source_pbr']; sc['bake_source_sha256']=report['source_sha256']
    sc['normal_convention']='OpenGL tangent +X +Y +Z; BakeUV'
    sc.render.bake.use_selected_to_active=False
    B.activate(low[0])
    P.frame((4,-6,3.2))
    bpy.context.preferences.filepaths.save_version=0
    image_names={key:im.name for key,im in images.items()}
    bpy.ops.wm.save_as_mainfile(filepath=str(model),compress=True,relative_remap=False)
    bpy.ops.wm.open_mainfile(filepath=str(model))
    for channel,name in image_names.items():
        loaded=bpy.data.images.get(name)
        assert loaded and loaded.packed_file
    report['model_sha256']=sha(model); report['bake']=True
    report['atlas_resolution']=size; report['baked_channels']=records
    report['uv_passed']=uvreport['passed']
    write(folder/'checks/retopology.json',report)
    write(folder/'checks/bake.json',dict(passed=True,source_sha256=sha(a['source_pbr']),
        method='Cycles selected-to-active; separately exploded original components; unlit EMIT color/metal/roughness and tangent NORMAL',
        ray_extrusion_m=.020,ray_distance_m=.080,margin_px=8,channels=records,coverage=coverage_report,
        source_projection_objects=1,source_coordinate_fields=coordinate_fields,
        model_sha256=sha(model),saved_file_reopened=True,seconds=time.time()-start))
    gpu(); sc=bpy.context.scene; sc.cycles.samples=24; sc.cycles.use_denoising=True
    sc.render.filepath=str(folder/'previews/front34.png')
    bpy.ops.render.render(write_still=True)
    print('BAKE_DONE',a['id'],round(time.time()-start,1),'sec',flush=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--ids',default=''); parser.add_argument('--resume',action='store_true')
    parser.add_argument('--resolution',type=int,default=0)
    parser.add_argument('--shard',default='0/1'); parser.add_argument('--exclude',default='')
    parser.add_argument('--fresh-uv',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=set(args.ids.split(',')) if args.ids else None
    excluded=set(args.exclude.split(','))
    shard,count=map(int,args.shard.split('/'))
    errors=[]
    P.M.native()
    for index,a in enumerate(rows()):
        if index%count!=shard or a['id'] in excluded or (selected and a['id'] not in selected):
            continue
        report=WORK/'assets'/a['folder']/'checks/bake.json'
        if args.resume and report.exists():
            data=json.loads(report.read_text(encoding='utf-8'))
            if data['passed'] and sha(WORK/a['retopo_model'])==data['model_sha256']:
                print('BAKE_SKIP',a['id'],flush=True); continue
        try:
            bake_one(a,args.resolution,args.fresh_uv)
        except Exception as exc:
            errors.append(dict(id=a['id'],error=str(exc)))
            traceback.print_exc()
            print('BAKE_FAILED',a['id'],str(exc),flush=True)
    if errors:
        write(WORK/('bake_errors_'+str(shard)+'.json'),errors)
        raise RuntimeError('Unresolved bakes: '+str([e['id'] for e in errors]))
    print('BAKE_COMPLETE',flush=True)


if __name__=='__main__':
    main()
