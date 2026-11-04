"""Derived game phone: lp -> bake -> pack -> export -> imports; never saves the master."""
import hashlib,json,math,sys
from pathlib import Path
import bpy,bmesh,numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from asset_kit import uv as UV
WORK=ROOT/'_asset_src/quest_phone/game'
MASTER=Path('E:/Models Blender/PROPS/QuestPhone/models/QuestPhone_factory_v01.blend')
LP=WORK/'QuestPhone_LP.blend'
OUT=ROOT/'assets/items/models/quest_phone'
SIZE=2048
LIMIT=5000

def say(*a):print('PHONE_GAME',*a,flush=True)
def triangles(o):o.data.calc_loop_triangles();return len(o.data.loop_triangles)
def activate(o):
    bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.select_set(True)
    bpy.context.view_layer.objects.active=o

def reduced_mesh(src):
    me=src.data
    verts=np.array([tuple(v.co) for v in me.vertices]);nverts=len(verts)
    name=src.name
    # Microscopic solid bars/contacts: keep the volume, bake their rounded edges.
    if name=='DisplaySurface':
        around=np.concatenate([33*c+np.round(np.linspace(0,32,7)).astype(int) for c in range(4)])
        verts=verts[around];faces=[tuple(range(len(verts)))]
    elif name.startswith(('Динамик · Перемычка','33 ·','22 ·')):
        lo,hi=verts.min(0),verts.max(0)
        verts=np.array([(x,y,z) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
        faces=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    elif nverts%100==0 and nverts//100 in (1,2,14):
        levels=nverts//100
        selected=[0,6,7,13] if levels==14 else list(range(levels))
        steps=6 if name.startswith(('01 ·','02 ·','03 ·','10 ·','Резец · Активная')) else 2
        around=np.concatenate([25*c+np.round(np.linspace(0,24,steps+1)).astype(int) for c in range(4)])
        verts=verts.reshape(levels,100,3)[selected][:,around].reshape(-1,3)
        n=len(around);k=len(selected)
        if k==1:faces=[tuple(range(n))]
        else:
            faces=[tuple(reversed(range(n))),tuple((k-1)*n+j for j in range(n))]
            faces += [(i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j) for i in range(k-1) for j in range(n)]
    elif all(len(p.vertices)==4 for p in me.polygons) and nverts%128==0:
        levels=nverts//128;n=18 if name.startswith('11 ·') else 12
        around=np.round(np.linspace(0,127,n,endpoint=False)).astype(int)
        verts=verts.reshape(levels,128,3)[:,around].reshape(-1,3)
        faces=[(i*n+j,i*n+(j+1)%n,((i+1)%levels)*n+(j+1)%n,((i+1)%levels)*n+j) for i in range(levels) for j in range(n)]
    elif nverts%2==0 and len(me.polygons)==nverts//2+2 and len(me.polygons[0].vertices)==nverts//2:
        old=nverts//2;n=20 if name.startswith('12 ·') else 16 if name.startswith('15 ·') else 12 if name.startswith('14 ·') else 6 if name.startswith('34 ·') else 8
        around=np.round(np.linspace(0,old-1,min(n,old),endpoint=False)).astype(int)
        verts=verts.reshape(2,old,3)[:,around].reshape(-1,3);n=len(around)
        faces=[tuple(reversed(range(n))),tuple(n+j for j in range(n))]+[(j,(j+1)%n,n+(j+1)%n,n+j) for j in range(n)]
    else:return me.copy()
    new=bpy.data.meshes.new('LP '+name);new.from_pydata(verts.tolist(),[],faces);new.update()
    for mat in me.materials:new.materials.append(mat)
    bm=bmesh.new();bm.from_mesh(new);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(new);bm.free()
    return new

def lp():
    spec=json.loads((ROOT/'tools/quest_phone/finish-spec.json').read_text(encoding='utf8'))
    assert spec['accepted'] and hashlib.sha256(MASTER.read_bytes()).hexdigest()==spec['acceptance']['sha256']
    WORK.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    original=list(bpy.context.scene.objects)
    copies={}
    for src in original:
        if src.type!='MESH':continue
        if src.name.startswith(('Динамик · Перемычка','33 ·')):continue
        ob=src.copy();ob.data=reduced_mesh(src);ob.name='LP_'+str(len(copies)).zfill(3)
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world=src.matrix_world;ob.parent=None
        ob['source']=src.name;ob['pivot']=tuple(src.matrix_world.translation);copies[src.name]=ob
    records={}
    for source,ob in copies.items():
        for m in list(ob.modifiers):
            if m.type=='BOOLEAN':m.object=copies[m.object.name]
            elif m.type=='BEVEL':ob.modifiers.remove(m) # normals bake carries these 0.06 mm edges
        if ob.hide_render:continue
        ob.hide_set(False);activate(ob)
        for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        if source.startswith(('01 ·','02 ·','03 ·')):
            bm=bmesh.new();bm.from_mesh(ob.data)
            bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
                plane_co=(0,0,0),plane_no=(0,1,0),dist=1e-8,clear_inner=False,clear_outer=False)
            bm.to_mesh(ob.data);bm.free()
        # Display stays a separate, single-sided surface with a dedicated full-screen UV.
        if source=='DisplaySurface':
            ob.name='DisplaySurface';group='screen'
            uv=ob.data.uv_layers.new(name='GameUV')
            xy=np.array([(v.co.x,v.co.y) for v in ob.data.vertices]);lo=xy.min(0);ext=xy.max(0)-lo
            for poly in ob.data.polygons:
                for li in poly.loop_indices:
                    p=xy[ob.data.loops[li].vertex_index];uv.data[li].uv=tuple((p-lo)/ext)
        else:
            group='glass' if source.startswith('12 ·') else 'optics' if source.startswith(('14 ·','05 ·')) else 'body'
            if source.startswith('20 ·'):
                names={'Питание':'Power','Камера':'Shutter','Действие':'Action','Громкость плюс':'VolumeUp','Громкость минус':'VolumeDown'}
                ob.name='Button'+names[source.split(' · ',1)[1]]
            for p in ob.data.polygons:p.use_smooth=True
        # Hard normal edges with seams are re-evaluated after triangulation below.
        material=bpy.data.materials.new('TARGET '+ob.name);material.use_nodes=True
        ob.data.materials.clear();ob.data.materials.append(material)
        hp=[source]
        if source.startswith('06 ·'):hp += [o.name for o in original if o.name.startswith('Динамик · Перемычка')]
        if source.startswith('32 ·'):hp += [o.name for o in original if o.name.startswith('33 ·')]
        records[ob.name]=dict(hp=hp,atlas=group,cage_mm=.20,ray_mm=.65,pivot_blender=list(ob['pivot']))
    keep=set(records)
    for ob in list(bpy.context.scene.objects):
        if ob.name not in keep:bpy.data.objects.remove(ob,do_unlink=True)
    obs=[bpy.data.objects[n] for n in records]
    count=sum(triangles(o) for o in obs)
    say('INITIAL_TRIANGLES',count,sorted([(triangles(o),o['source']) for o in obs],reverse=True)[:8])
    assert count<=LIMIT,('budget before UV',count)
    reports={}
    for group in ['body','glass','optics']:
        members=[o for o in obs if records[o.name]['atlas']==group]
        UV.smart_unwrap(members,uv='GameUV')
        if group=='body':
            for ob in members:
                if ob['source'].startswith(('01 ·','02 ·','03 ·')):
                    # Split the long slab in two without distorting or scaling either half.
                    uv=ob.data.uv_layers['GameUV'].data
                    for poly in ob.data.polygons:
                        if poly.center.y>1e-8:
                            for li in poly.loop_indices:uv[li].uv.x+=2.
            # Contacts under panels get lower density; visible surfaces remain evenly scaled.
            classes=UV.visibility(members,contact=.00012,roomy=.0003)
            reports[group]=UV.layout(members,SIZE,uv='GameUV',classes=classes,stack=False,margin=8,group_margin=4,log=say)
            reports[group]['verification']=UV.verify(members,SIZE,uv='GameUV',margin=8,group_margin=4)
        UV.harden_on_seams(members,uv='GameUV')
    for ob in obs:
        activate(ob);mod=ob.modifiers.new('Stable triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
        bm=bmesh.new();bm.from_mesh(ob.data)
        for e in bm.edges:
            if e.is_manifold and e.calc_face_angle()>math.radians(60):e.smooth=False;e.seam=True
        bm.to_mesh(ob.data);bm.free()
        records[ob.name]['triangles']=triangles(ob)
    total=sum(r['triangles'] for r in records.values());assert total<=LIMIT
    (WORK/'parts.json').write_text(json.dumps(dict(source=str(MASTER),sha256=spec['acceptance']['sha256'],parts=records,
        triangles=total,limit=LIMIT,atlas_size=SIZE,uv=reports),ensure_ascii=False,indent=2,default=str),encoding='utf8')
    bpy.ops.wm.save_as_mainfile(filepath=str(LP));say('LP_READY',total)

def bake():
    bpy.context.preferences.use_preferences_save=False
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    import addon_utils
    addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
    hp={o.name:o for o in bpy.data.objects if o.type=='MESH'}
    rec=json.loads((WORK/'parts.json').read_text(encoding='utf8'))
    records={n:r for n,r in rec['parts'].items() if r['atlas']=='body'}
    with bpy.data.libraries.load(str(LP),link=False) as (src,dst):dst.objects=list(records)
    lp={}
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o);lp[o.name]=o
    sc=bpy.context.scene;sc.render.engine='CYCLES'
    prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type!='CPU'
    sc.cycles.device='GPU';sc.cycles.use_denoising=False
    sc.render.bake.margin_type='EXTEND';sc.render.bake.normal_space='TANGENT';sc.render.bake.use_cage=False
    images={};saved={}
    mats={m for o in hp.values() for m in o.data.materials if m and m.use_nodes}
    for m in mats:
        nt=m.node_tree;out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL')
        saved[m.name]=out.inputs['Surface'].links[0].from_socket
    # Bake all matching pairs in one exploded batch, preserving local coordinates
    # of native procedural materials. Each pair is 250 mm away from its neighbours.
    selected_hp=[]
    for i,(name,r) in enumerate(records.items()):
        offset=Vector((i*.25,0,0));lp[name].location+=offset
        for src in r['hp']:
            hp[src].location+=offset;hp[src].hide_render=False;hp[src].hide_set(False)
            selected_hp.append(hp[src])
    bpy.ops.object.select_all(action='DESELECT')
    for ob in lp.values():ob.select_set(True)
    bpy.context.view_layer.objects.active=next(iter(lp.values()))
    bpy.ops.object.join();batch=bpy.context.object
    def route(channel):
        for m in mats:
            nt=m.node_tree;out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL')
            if channel=='normal':nt.links.new(saved[m.name],out.inputs['Surface']);continue
            bs=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
            emit=nt.nodes.get('PHONE_BAKE') or nt.nodes.new('ShaderNodeEmission');emit.name='PHONE_BAKE'
            def feed(target,source):
                if source.is_linked:nt.links.new(source.links[0].from_socket,target)
                else:target.default_value=source.default_value
            if channel=='color':feed(emit.inputs['Color'],bs.inputs['Base Color'])
            else:
                c=nt.nodes.get('PHONE_MRA') or nt.nodes.new('ShaderNodeCombineColor');c.name='PHONE_MRA'
                feed(c.inputs['Red'],bs.inputs['Metallic']);feed(c.inputs['Green'],bs.inputs['Roughness'])
                c.inputs['Blue'].default_value=1.
                nt.links.new(c.outputs[0],emit.inputs['Color'])
            nt.links.new(emit.outputs[0],out.inputs['Surface'])
    raw=WORK/'raw';raw.mkdir(exist_ok=True)
    for channel in ['color','mra','normal','ao']:
        image=bpy.data.images.new('phone_'+channel,SIZE,SIZE,alpha=True,float_buffer=True)
        image.colorspace_settings.name='sRGB' if channel=='color' else 'Non-Color'
        image.generated_color=(.5,.5,1,0) if channel=='normal' else (0,0,0,0)
        images[channel]=image
        if channel=='ao':
            for o in hp.values():o.hide_render=True
            batch.hide_render=True
            with bpy.data.libraries.load(str(LP),link=False) as (src,dst):dst.objects=list(records)
            bpy.ops.object.select_all(action='DESELECT')
            assembled=[]
            for ob in dst.objects:
                bpy.context.scene.collection.objects.link(ob);ob.hide_render=False;ob.hide_set(False);ob.select_set(True);assembled.append(ob)
            bpy.context.view_layer.objects.active=assembled[0];bpy.ops.object.join();batch=bpy.context.object
            sc.world.light_settings.distance=.002
        else:
            route(channel)
        for material in batch.data.materials:
            nt=material.node_tree
            target=nt.nodes.get('PHONE_TARGET') or nt.nodes.new('ShaderNodeTexImage');target.name='PHONE_TARGET'
            target.image=image;nt.nodes.active=target
        sc.cycles.samples=16 if channel=='ao' else 4
        activate(batch)
        if channel!='ao':
            for ob in selected_hp:ob.select_set(True)
        bpy.ops.object.bake(type='NORMAL' if channel=='normal' else 'AO' if channel=='ao' else 'EMIT',
            use_clear=True,use_selected_to_active=channel!='ao',cage_extrusion=.00020,max_ray_distance=.00065,margin=4)
        image.filepath_raw=str(raw/f'body_{channel}.png');image.file_format='PNG';image.save()
        say('BAKED',channel)

def pack():
    # Same channel packing and push/pull padding as the accepted car-item exporter.
    sys.path.insert(0,str(ROOT/'tools/coupe_ilya'))
    import radiator_game as R
    def read(ch):
        im=bpy.data.images.load(str(WORK/f'raw/body_{ch}.png'),check_existing=False)
        # Read stored bytes unchanged, like radiator_game._load. The source colour
        # PNG is already sRGB; decoding and writing it into a byte image would gamma it twice.
        im.colorspace_settings.name='Non-Color'
        return np.array(im.pixels[:],np.float32).reshape(SIZE,SIZE,4)
    color,mra,normal,ao=[read(c) for c in ['color','mra','normal','ao']]
    mask=mra[...,2]>.05
    OUT.mkdir(parents=True,exist_ok=True)
    albedo=R._pushpull(color[...,:3],mask)
    n=R._pushpull(normal[...,:3],mask)*2.-1.;n/=np.maximum(np.linalg.norm(n,axis=2,keepdims=True),1e-6)
    rough=R._pushpull(mra[...,1:2],mask)[...,0]
    metal=R._pushpull(mra[...,0:1],mask)[...,0]
    occ=R._pushpull(ao[...,:1],mask)[...,0]
    occ=1.-(1.-occ)*.5
    for channel,pixels,srgb in [('albedo',albedo,True),('normal',n*.5+.5,False),('orm',np.dstack([occ,rough,metal]),False)]:
        R._save(pixels,OUT/f'quest_phone_{channel}.png',srgb)
    report=dict(covered_fraction=float(mask.mean()),mean_roughness=float(rough[mask].mean()),
        mean_metallic=float(metal[mask].mean()),miss_fraction=float((mra[...,2]<.01).mean()))
    (WORK/'bake.json').write_text(json.dumps(report,indent=2),encoding='utf8');say('PACKED',report)

def export():
    from mathutils import Matrix
    rec=json.loads((WORK/'parts.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    for r in rec['parts'].values():r['pivot_blender']=list(bpy.data.objects[r['hp'][0]].matrix_world.translation)
    (WORK/'parts.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf8')
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    def mat(name,col,rough,metal=0.):
        m=bpy.data.materials.new(name);m.use_nodes=True;p=m.node_tree.nodes['Principled BSDF']
        p.inputs['Base Color'].default_value=(*col,1);p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
        return m
    body=mat('PhoneBody',(1,1,1),1)
    nt=body.node_tree;p=nt.nodes['Principled BSDF']
    def tex(ch,space):
        node=nt.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(OUT/f'quest_phone_{ch}.png'))
        node.image.colorspace_settings.name=space;return node
    nt.links.new(tex('albedo','sRGB').outputs['Color'],p.inputs['Base Color'])
    orm=tex('orm','Non-Color');sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(orm.outputs['Color'],sep.inputs[0])
    nt.links.new(sep.outputs['Green'],p.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],p.inputs['Metallic'])
    nm=nt.nodes.new('ShaderNodeNormalMap');nm.uv_map='GameUV';nt.links.new(tex('normal','Non-Color').outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs[0],p.inputs['Normal'])
    tree=bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree');tree.interface.new_socket(name='Occlusion',in_out='INPUT',socket_type='NodeSocketFloat')
    gn=nt.nodes.new('ShaderNodeGroup');gn.node_tree=tree;nt.links.new(sep.outputs['Red'],gn.inputs['Occlusion'])
    screen=mat('PhoneScreen',(.00854,.00882,.00939),.055)
    glass=mat('PhoneCameraGlass',(.91,.93,.93),.02);glass.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=1
    glass.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value=1.52
    optics=mat('PhoneOptics',(.91,.93,.93),.02);optics.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=1
    optics.node_tree.nodes['Principled BSDF'].inputs['IOR'].default_value=1.52
    optics.node_tree.nodes['Principled BSDF'].inputs['Thin Film Thickness'].default_value=110
    mats={'body':body,'screen':screen,'glass':glass,'optics':optics}
    groups={}
    for name,r in rec['parts'].items():
        ob=bpy.data.objects[name];ob.data.materials.clear();ob.data.materials.append(mats[r['atlas']])
        key=name if name.startswith('Button') else 'DisplaySurface' if r['atlas']=='screen' else r['atlas']
        groups.setdefault(key,[]).append(ob)
    root=bpy.data.objects.new('QuestPhone',None);bpy.context.scene.collection.objects.link(root)
    rotation=Matrix.Rotation(math.pi/2,4,'X')
    names={'body':'Housing','glass':'CameraGlass','optics':'CameraOptics'}
    for key,obs in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in obs:o.select_set(True)
        bpy.context.view_layer.objects.active=obs[0]
        if len(obs)>1:bpy.ops.object.join()
        ob=bpy.context.object;ob.name=names.get(key,key)
        if key.startswith('Button'):
            pivot=Vector(rec['parts'][key]['pivot_blender'])
            ob.data.transform(Matrix.Translation(-pivot));ob.location=rotation@pivot
        ob.data.transform(rotation);ob.data.update();ob.parent=root
    for name,position in [('ScreenMarker',(0,0,.004126)),('CameraLensMarker',(.0095,.0692,-.0073))]:
        ob=bpy.data.objects.new(name,None);bpy.context.scene.collection.objects.link(ob);ob.location=rotation@Vector(position);ob.parent=root
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(OUT/'quest_phone.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_apply=True,export_tangents=True,export_extras=True,export_animations=False,
        export_cameras=False,export_lights=False,export_image_format='NONE')
    # Geometry-only GLB plus external project textures; Godot assigns the same materials explicitly.
    total=sum(triangles(o) for o in bpy.data.objects if o.type=='MESH');assert total<=LIMIT
    rec.update(triangles=total,axes='Godot: X width, Y up, +Z screen; metres',
        collision='Simple item box, no high-poly collision',lod='Godot automatic mesh LOD at import',
        material_maps='quest_phone_{albedo,normal,orm}.png; special glass and live screen assigned by phone scene')
    (OUT/'quest_phone.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'QuestPhone_Game.blend'));say('EXPORTED',total)

def imports():
    # Apply only this asset's image settings, following the car-item/PM pipeline.
    for p in OUT.glob('*.png.import'):
        s=p.read_text(encoding='utf8')
        import re
        values={'compress/mode':'2','mipmaps/generate':'true','roughness/mode':'3' if '_orm' in p.name else '1'}
        if '_normal' in p.name:values['compress/normal_map']='1'
        if '_orm' in p.name:values['roughness/src_normal']='"res://assets/items/models/quest_phone/quest_phone_normal.png"'
        for key,val in values.items():
            if re.search(r'^'+re.escape(key)+r'=',s,re.M):s=re.sub(r'^'+re.escape(key)+r'=.*$',key+'='+val,s,flags=re.M)
            else:s+='\n'+key+'='+val+'\n'
        p.write_text(s,encoding='utf8')
    say('IMPORT_SETTINGS_UPDATED')

if __name__=='__main__':
    command=sys.argv[sys.argv.index('--')+1]
    {'lp':lp,'bake':bake,'pack':pack,'export':export,'imports':imports}[command]()
