"""Авторинг всей партии: родная геометрия -> native UCUPaint -> reopen -> проверка."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from plan import ROOT, DELIVERY, OWNER_REQUEST, prepare, sha
from profiles import PROFILES, SUSPENDED, surface
import materials as M


def load_audit():
    spec=importlib.util.spec_from_file_location('urban_source_audit',M.SKILL/'scripts/audit_source.py')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUDIT=load_audit()


def recipe_sha():
    return hashlib.sha256(b''.join((Path(__file__).parent/name).read_bytes()
        for name in ('process.py','materials.py','profiles.py'))).hexdigest()


def bounds():
    graph=bpy.context.evaluated_depsgraph_get()
    points=[ob.matrix_world@Vector(c) for ob in bpy.data.collections['MODEL | editable components'].objects
        if ob.type in ('MESH','FONT','CURVE') for c in ob.evaluated_get(graph).bound_box]
    return Vector(tuple(min(p[i] for p in points) for i in range(3))), Vector(tuple(max(p[i] for p in points) for i in range(3)))


def colour_attribute(mesh,name,values):
    attr=mesh.color_attributes.get(name) or mesh.color_attributes.new(name=name,type='FLOAT_COLOR',domain='CORNER')
    data=np.ones((len(mesh.loops),4),np.float32)
    data[:,:3]=np.asarray(values,dtype=np.float32)[:,None]
    attr.data.foreach_set('color',data.ravel())


def uv_and_assign(a):
    col=bpy.data.collections['MODEL | editable components']
    mats={}
    assigned=[]
    seed=int(hashlib.sha256(a['id'].encode()).hexdigest()[:8],16)
    rng=np.random.default_rng(seed)
    offset=rng.uniform(0,9,3)
    lo,hi=bounds()
    for ob in col.objects:
        if ob.type not in ('MESH','FONT','CURVE'):
            continue
        key=surface(a,ob)
        if key not in mats:
            mat=bpy.data.materials.new(a['id']+' • '+key)
            mat.use_nodes=True
            mat['surface_recipe']=key
            mat['texture_authorization']=OWNER_REQUEST
            mats[key]=mat
        ob.data.materials.clear()
        ob.data.materials.append(mats[key])
        assigned.append(dict(object=ob.name,surface=key))
        if ob.type!='MESH':
            continue
        me=ob.data
        for f in me.polygons:
            f.material_index=0
        co=np.empty(len(me.vertices)*3,np.float32)
        me.vertices.foreach_get('co',co)
        mw=np.array(ob.matrix_world,dtype=np.float64)
        p=co.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]
        idx=np.empty(len(me.loops),np.int32)
        me.loops.foreach_get('vertex_index',idx)
        lp=p[idx]
        normal=np.empty(len(me.polygons)*3,np.float32)
        me.polygons.foreach_get('normal',normal)
        face_n=normal.reshape(-1,3)@np.linalg.inv(mw[:3,:3])
        face_n/=np.maximum(np.linalg.norm(face_n,axis=1,keepdims=True),1e-12)
        counts=np.empty(len(me.polygons),np.int32)
        me.polygons.foreach_get('loop_total',counts)
        ns=np.repeat(face_n,counts,axis=0)
        axis=np.abs(ns).argmax(axis=1)
        metric=np.stack((lp[:,0]+offset[0],lp[:,2]+offset[2]),axis=1)
        metric[axis==0]=lp[axis==0][:,(1,2)]+offset[(1,2),]
        metric[axis==2]=lp[axis==2][:,(0,1)]+offset[(0,1),]
        part=np.empty_like(metric)
        pmin,pmax=p.min(axis=0),p.max(axis=0)
        normalized=(lp-pmin)/np.maximum(pmax-pmin,.00001)
        part[axis==0]=normalized[axis==0][:,(1,2)]
        part[axis==1]=normalized[axis==1][:,(0,2)]
        part[axis==2]=normalized[axis==2][:,(0,1)]
        length_axis=np.argmax(p.max(axis=0)-p.min(axis=0))
        grain=np.empty_like(metric)
        for normal_axis in range(3):
            take=axis==normal_axis
            transverse=next(i for i in range(3) if i!=normal_axis and i!=length_axis) if normal_axis!=length_axis else (normal_axis+1)%3
            along=length_axis if normal_axis!=length_axis else (normal_axis+2)%3
            grain[take,0]=lp[take,transverse]
            grain[take,1]=lp[take,along]
        partseed=int(hashlib.sha256(ob.name.encode()).hexdigest()[:8],16)
        prng=np.random.default_rng(partseed)
        grain+=prng.uniform(0,6,2)
        for name,values in ((M.UV,metric),(M.PART,part),(M.GRAIN,grain)):
            uv=me.uv_layers.get(name) or me.uv_layers.new(name=name)
            uv.data.foreach_set('uv',values.astype(np.float32).ravel())
        me.uv_layers.active=me.uv_layers[M.UV]
        me.uv_layers[M.UV].active_render=True
        up=np.clip(ns[:,2],0,1)**1.6
        ground=np.exp(-np.maximum(0,lp[:,2]-lo.z)/.15)
        if a['key'] in SUSPENDED:
            ground*=0
        touched=any(t in ob.name.lower() for t in ('handle','pull','key','button','handrail','grip','reader','armrest','latch','steering','touch'))
        hand=np.ones(len(lp),np.float32) if touched else np.zeros(len(lp),np.float32)
        road=np.clip((.68-(lp[:,2]-lo.z))/.48,0,1)
        for name,values in (('FaceUp',up),('GroundContact',ground),('HandContact',hand),('RoadFilm',road)):
            colour_attribute(me,name,values)
        # The cross-cut ends of actual long timber pieces have a separate material.
        d=p.max(axis=0)-p.min(axis=0)
        if key in ('wood_aged','timber_warm') and sorted(d)[-1]>2*max(sorted(d)[-2],.001):
            endkey=key+'_end'
            if endkey not in mats:
                mat=bpy.data.materials.new(a['id']+' • '+endkey)
                mat.use_nodes=True
                mat['surface_recipe']=endkey
                mats[endkey]=mat
            me.materials.append(mats[endkey])
            for face,n in zip(me.polygons,face_n):
                if abs(n[length_axis])>.8:
                    face.material_index=1
        me.update()
    return mats,assigned


def author_materials(a,mats):
    col=bpy.data.collections['MODEL | editable components']
    trees=[]
    for key,mat in mats.items():
        holder=next((o for o in col.objects if o.type=='MESH' and mat in list(o.data.materials)),None)
        temporary=holder is None
        if temporary:
            holder=next(o for o in col.objects if o.type=='MESH')
            holder.data.materials.append(mat)
        tree=M.author(mat,holder,key,a)
        trees.append(dict(material=mat.name,recipe=key,layers=len(tree.yp.layers),
            masks=sum(len(l.masks) for l in tree.yp.layers)))
        if temporary:
            holder.data.materials.pop(index=len(holder.data.materials)-1)
    return trees


def studio():
    sc=bpy.context.scene
    sc.render.engine='CYCLES'
    sc.cycles.samples=int(os.environ.get('URBAN_PBR_SAMPLES','24'))
    sc.cycles.use_denoising=True
    sc.cycles.max_bounces=8
    sc.cycles.transmission_bounces=6
    sc.render.resolution_x=1200
    sc.render.resolution_y=950
    sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG'
    sc.render.image_settings.color_mode='RGB'
    sc.view_settings.view_transform='AgX'
    sc.view_settings.look='AgX - Medium High Contrast'
    sc.view_settings.exposure=0
    world=sc.world or bpy.data.worlds.new('Urban PBR diagnostic sky')
    sc.world=world
    world.use_nodes=True
    nt=world.node_tree
    nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputWorld')
    bg=nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value=.65
    env=nt.nodes.new('ShaderNodeTexEnvironment')
    env.image=M.image('kloofendal_overcast_puresky.hdr',True)
    nt.links.new(env.outputs['Color'],bg.inputs['Color'])
    nt.links.new(bg.outputs[0],out.inputs[0])
    for ob in bpy.data.objects:
        if ob.type=='LIGHT':
            ob.data.energy=0
    lo,hi=bounds()
    c=(lo+hi)/2
    span=max(hi-lo)
    collection=next(c for c in bpy.data.collections if c.name.startswith('STUDIO |'))
    for name,vector,power,size in (
        ('PBR key',(1.1,-1.8,2.0),180,1.5),
        ('PBR strip',(-1.6,.1,1.3),95,1.2),
        ('PBR rim',(.8,1.5,1.8),150,1.0)):
        ob=bpy.data.objects.get(name)
        if not ob:
            data=bpy.data.lights.new(name,'AREA')
            ob=bpy.data.objects.new(name,data)
            collection.objects.link(ob)
        ob.location=c+Vector(vector)*span
        ob.rotation_euler=(c-ob.location).to_track_quat('-Z','Y').to_euler()
        ob.data.energy=power*span**2
        ob.data.size=size*span
    # The old Workbench source has no ground mesh; preserve its object set.
    for ob in collection.objects:
        if ob.type=='MESH':
            mat=bpy.data.materials.new('PBR studio matte, not model')
            mat.use_nodes=True
            bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            bsdf.inputs['Base Color'].default_value=(.22,.22,.22,1)
            bsdf.inputs['Roughness'].default_value=.88
            ob.data.materials.clear()
            ob.data.materials.append(mat)
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use=d.type=='OPTIX'
    sc.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
    return sc


def frame(direction,lo=None,hi=None):
    sc=bpy.context.scene
    low,high=bounds() if lo is None else (lo,hi)
    center=(low+high)/2
    cam=sc.camera
    direction=Vector(direction).normalized()
    cam.location=center+direction*(2*(high-low).length+2)
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO'
    bpy.context.view_layer.update()
    inv=cam.matrix_world.inverted()
    p=[inv@Vector((x,y,z)) for x in (low.x,high.x) for y in (low.y,high.y) for z in (low.z,high.z)]
    w=max(q.x for q in p)-min(q.x for q in p)
    h=max(q.y for q in p)-min(q.y for q in p)
    aspect=sc.render.resolution_x/sc.render.resolution_y
    cam.data.ortho_scale=max(w,h*aspect)*1.14
    cam.data.clip_end=1000
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.shading.type='MATERIAL'
                space.region_3d.view_location=center
                space.region_3d.view_distance=(high-low).length*1.4
                space.region_3d.view_rotation=cam.rotation_euler.to_quaternion()


def render_views(a,folder,detail=True):
    sc=bpy.context.scene
    previews=folder/'previews'
    previews.mkdir(parents=True,exist_ok=True)
    records=[]
    for name,direction in (('front34',(4,-6,3.2)),('rear34',(-4,6,2.8))):
        frame(direction)
        sc.render.filepath=str(previews/(name+'.png'))
        bpy.ops.render.render(write_still=True)
        records.append(dict(view=name,file=str(previews/(name+'.png')),source_blend=bpy.data.filepath))
    if detail:
        col=bpy.data.collections['MODEL | editable components']
        # Largest front-facing functional surface, rather than a random bolt.
        options=[o for o in col.objects if o.type=='MESH' and o.get('finish_role') not in ('interior','glass','rubber','screen')]
        ob=max(options,key=lambda o: sorted(o.dimensions)[-1]*sorted(o.dimensions)[-2])
        points=[ob.matrix_world@Vector(c) for c in ob.bound_box]
        center=sum(points,Vector())/8
        lo,hi=bounds()
        extent=max(.14,min(1.4,max(ob.dimensions)*.35))
        center.y=min(p.y for p in points)
        if a['id']=='R03':
            center=Vector((0,-.42,1.12))
            extent=.30
        if a['id']=='R04':
            center=Vector((-.35,-1.9,.8))
            extent=.65
        targetlo=center-Vector((extent,extent*.22,extent*.65))
        targethi=center+Vector((extent,extent*.22,extent*.65))
        frame((.4,-5,1.0),targetlo,targethi)
        sc.render.filepath=str(previews/'detail.png')
        bpy.ops.render.render(write_still=True)
        records.append(dict(view='detail',file=sc.render.filepath,source_blend=bpy.data.filepath,focus_part=ob.name))
    (folder/'checks').mkdir(exist_ok=True)
    (folder/'checks/render_views.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')


def pack_and_save(model):
    dep=ROOT/'dependencies'
    dep.mkdir(exist_ok=True)
    manifests=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        original=im.filepath
        im.pack()
        if not im.packed_file:
            raise RuntimeError('Image not packed: '+im.name)
        raw=bytes(im.packed_file.data)
        digest=hashlib.sha256(raw).hexdigest()
        suffix=Path(original).suffix.lower() or '.png'
        prefix=Path(original).parent.name+'_'+Path(original).stem
        prefix=''.join(c if c.isalnum() or c in '-_' else '_' for c in prefix)[:70]
        path=dep/(prefix+'_'+digest[:10]+suffix)
        if not path.exists():
            path.write_bytes(raw)
        im.filepath='//'+os.path.relpath(path,model.parent).replace('\\','/')
        manifests.append(dict(datablock=im.name,relative_file=path.relative_to(ROOT).as_posix(),
            sha256=digest,bytes=len(raw),size=list(im.size),colorspace=im.colorspace_settings.name,source=original))
    model.parent.mkdir(parents=True,exist_ok=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(model),compress=True,relative_remap=False)
    return manifests


def validate(a,original,model,image_manifest):
    final=AUDIT.snapshot(model)
    changed={name:[k for k in rec if final['objects'].get(name,{}).get(k)!=rec[k]]
        for name,rec in original['objects'].items() if final['objects'].get(name)!=rec}
    added=sorted(set(final['objects'])-set(original['objects']))
    errors=list(final['dependency_errors'])
    errors += ['Image not packed: '+r['name'] for r in final['images'] if not r['packed']]
    col=bpy.data.collections['MODEL | editable components']
    used={m for o in col.objects if o.type in ('MESH','FONT','CURVE') for m in o.data.materials if m}
    materials=[]
    for mat in sorted(used,key=lambda m:m.name):
        groups=[n for n in mat.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node]
        if len(groups)!=1:
            errors.append('Non-native model material: '+mat.name)
            continue
        group=groups[0]
        tree=group.node_tree
        links={l.to_socket.name for l in mat.node_tree.links if l.from_node==group and l.to_node.type=='BSDF_PRINCIPLED'}
        if not {'Base Color','Metallic','Roughness','Normal'}.issubset(links):
            errors.append('Missing native channel output: '+mat.name)
        if tree.yp.version!='2.4.9':
            errors.append('Native version changed: '+mat.name)
        for lay in tree.yp.layers:
            if not lay.enable:
                errors.append('Disabled production layer: '+lay.name)
            for root,ch in zip(tree.yp.channels,lay.channels):
                if ch.enable and ch.override:
                    val=M.U.common.get_entity_prop_value(ch,'override_color' if root.type=='RGB' else 'override_value')
                    values=list(val) if root.type=='RGB' else [val]
                    if any(v is None or not math.isfinite(float(v)) for v in values):
                        errors.append('Invalid native socket: '+lay.name)
        materials.append(dict(material=mat.name,recipe=mat.get('surface_recipe'),layers=len(tree.yp.layers),
            masks=sum(len(l.masks) for l in tree.yp.layers),native_version=tree.yp.version))
    for rec in image_manifest:
        im=bpy.data.images.get(rec['datablock'])
        if not im or not im.packed_file:
            errors.append('Missing image datablock: '+rec['datablock'])
            continue
        if hashlib.sha256(bytes(im.packed_file.data)).hexdigest()!=rec['sha256']:
            errors.append('Packed bytes changed: '+im.name)
        external=Path(bpy.path.abspath(im.filepath))
        if not external.exists() or sha(external)!=rec['sha256']:
            errors.append('External copy mismatch: '+im.name)
        if im.colorspace_settings.name!=rec['colorspace']:
            errors.append('Colorspace changed: '+im.name)
    for ob in col.objects:
        expected=(M.UV,M.PART,'WeatherUV') if a['id']=='R06' else (M.UV,M.PART,M.GRAIN)
        if ob.type=='MESH' and any(u not in ob.data.uv_layers for u in expected):
            errors.append('UV missing: '+ob.name)
    if sha(a['source_blend'])!=a['source_sha256']:
        errors.append('Source file changed during authoring')
    result=dict(id=a['id'],source=a['source_blend'],candidate=str(model),source_sha256=a['source_sha256'],
        blend_sha256=sha(model),saved_file_reopened=True,geometry_changes=changed,added_model_objects=added,
        geometry_objects_checked=len(original['objects']),errors=errors,materials=materials,
        native_materials=len(materials),native_layers=sum(m['layers'] for m in materials),
        packed_images=len(image_manifest),texture_approved=False,game_export=False,
        passed=not changed and not added and not errors)
    return result


def run_one(a,preview=False):
    start=time.time()
    original=AUDIT.snapshot(a['source_blend'])
    M.clear_cache()
    mats,assigned=uv_and_assign(a)
    author_materials(a,mats)
    studio()
    frame((4,-6,3.2))
    folder=ROOT/'assets'/a['folder']
    (folder/'checks').mkdir(parents=True,exist_ok=True)
    if preview:
        render_views(a,folder,True)
        print('URBAN_PREVIEW',a['id'],len(mats),round(time.time()-start,2),flush=True)
        return
    model=ROOT/a['output_model']
    sc=bpy.context.scene
    sc['stage']='Native PBR candidate; owner explicitly requested texturing all models'
    sc['source_geometry_sha256']=a['source_sha256']
    sc['texture_authorization']=OWNER_REQUEST
    for ob in bpy.data.collections['MODEL | editable components'].objects:
        if ob.type=='EMPTY':
            ob['production_uv']=True
            ob['production_textures']=True
            ob['texture_approved']=False
            ob['texture_authorization']=OWNER_REQUEST
    images=pack_and_save(model)
    (folder/'checks/image_manifest.json').write_text(json.dumps(images,ensure_ascii=False,indent=2),encoding='utf-8')
    result=validate(a,original,model,images)
    result['recipe_sha256']=recipe_sha()
    (folder/'checks/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'checks/part_materials.json').write_text(json.dumps(assigned,ensure_ascii=False,indent=2),encoding='utf-8')
    if not result['passed']:
        raise RuntimeError('Asset verification failed: '+a['id']+' '+str(result['errors'])+' '+str(result['geometry_changes']))
    render_views(a,folder,True)
    print('URBAN_TEXTURED',a['id'],a['key'],result['native_materials'],'materials',
        result['native_layers'],'layers',round(time.time()-start,2),'sec',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['preview','build'])
    parser.add_argument('--ids',default='')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    rows=prepare()
    selected=set(args.ids.split(',')) if args.ids else None
    assert all(a['key'] in PROFILES for a in rows if not a['existing_pbr'])
    M.native()
    for a in rows:
        if a['existing_pbr'] or selected and a['id'] not in selected:
            continue
        report=ROOT/'assets'/a['folder']/'checks/validation.json'
        if args.resume and report.exists():
            v=json.loads(report.read_text(encoding='utf-8'))
            previews=report.parent.parent/'previews'
            complete=all((previews/(view+'.png')).exists() for view in ('front34','rear34','detail'))
            if v['passed'] and complete and v.get('recipe_sha256')==recipe_sha() and (ROOT/a['output_model']).exists() and sha(ROOT/a['output_model'])==v['blend_sha256']:
                print('URBAN_RESUME_SKIP',a['id'],flush=True)
                continue
        run_one(a,args.mode=='preview')
    print('URBAN_BATCH_COMPLETE',args.mode,flush=True)


if __name__=='__main__':
    main()
