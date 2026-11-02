"""Export the <=5000-triangle family using the project's external-map glTF pipeline."""
import sys,pathlib,json,math,hashlib
import bpy
from mathutils import Matrix,Vector
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
REC=json.loads((WORK/'parts.json').read_text(encoding='utf-8'))
bpy.context.preferences.use_preferences_save=False
bpy.ops.wm.open_mainfile(filepath=str(WORK/'dozor_lp.blend'))
sc=bpy.context.scene
src=[o for o in bpy.data.objects if o.type=='MESH']
F=Matrix(((0,-1,0,0),(0,0,1,-.035),(-1,0,0,.0805),(0,0,0,1)))
P=Matrix(((0,-1,0,-.064),(0,0,1,-.011),(-1,0,0,.0805),(0,0,0,1)))

def empty(name,parent=None,pos=(0,0,0)):
    o=bpy.data.objects.new(name,None);sc.collection.objects.link(o);o.parent=parent;o.location=pos;return o

def material(key):
    atlas='p' if key=='p' else 'f1'
    m=bpy.data.materials.new('DOZOR_GAME_'+key);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    bs=nt.nodes.new('ShaderNodeBsdfPrincipled');out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(bs.outputs[0],out.inputs[0])
    uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='GameUV'
    def tex(file,space):
        im=bpy.data.images.load(str(OUT/file),check_existing=True);im.colorspace_settings.name=space
        t=nt.nodes.new('ShaderNodeTexImage');t.image=im;nt.links.new(uv.outputs[0],t.inputs['Vector']);return t
    nt.links.new(tex('dozor_'+key+'_base_color.png','sRGB').outputs['Color'],bs.inputs['Base Color'])
    orm=tex('dozor_'+atlas+'_orm.png','Non-Color');sep=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(orm.outputs[0],sep.inputs[0])
    nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
    normal=nt.nodes.new('ShaderNodeNormalMap');normal.uv_map='GameUV'
    nt.links.new(tex('dozor_'+atlas+'_normal.png','Non-Color').outputs['Color'],normal.inputs['Color']);nt.links.new(normal.outputs[0],bs.inputs['Normal'])
    g=bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s,'in_out','')=='INPUT']:g.interface.new_socket('Occlusion',in_out='INPUT',socket_type='NodeSocketFloat')
    gn=nt.nodes.new('ShaderNodeGroup');gn.node_tree=g;nt.links.new(sep.outputs['Red'],gn.inputs['Occlusion'])
    return m

def join_pieces(objs,name,parent,frame,pivot=(0,0,0)):
    copies=[]
    for s in objs:
        cp=s.copy();cp.data=s.data.copy();sc.collection.objects.link(cp);cp.name='EXPORT_'+s.name
        cp.data.transform(frame@cp.matrix_world);cp.matrix_world=Matrix.Identity(4);copies.append(cp)
    select(copies);bpy.ops.object.join();o=bpy.context.object;o.name=name
    o.data.transform(Matrix.Translation(-Vector(pivot)));o.parent=parent;o.location=pivot
    return o

def export(root,key):
    objs=[root,*root.children_recursive];select(objs)
    bpy.ops.export_scene.gltf(filepath=str(OUT/('dozor_'+key+'.gltf')),export_format='GLTF_SEPARATE',use_selection=True,
        export_yup=False,export_apply=True,export_texcoords=True,export_normals=True,export_tangents=True,
        export_animations=False,export_skins=False,export_morph=False,export_extras=True,export_texture_dir='',export_image_format='AUTO')
    # External BIN can change UV coordinates while the glTF JSON stays identical.
    # Include its digest in JSON so Godot cannot keep a stale imported mesh.
    path=OUT/('dozor_'+key+'.gltf');data=json.loads(path.read_text(encoding='utf-8'))
    data['asset'].setdefault('extras',{})['ring_binary_sha256']=hashlib.sha256((OUT/data['buffers'][0]['uri']).read_bytes()).hexdigest()
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return objs

manifest={'triangle_limit_complete_assembly':TRIANGLE_LIMIT,'states':['working100'],
    'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'axes':'Godot native X right, Y up, +Z light emission; glTF export_yup=false avoids a second conversion',
    'flashlight_root':'tube axis at axial 80.5 mm; emitter at +Z 80.5 mm',
    'mount_root':'Picatinny mounting datum; FlashlightSocket at Y +24 mm',
    'roles':'Handheld / mounted first-person attachment and world item, same mesh, automatic import LOD',
    'triangles':{},'nodes':{},'atlas':REC['uv'],'texture_size':SIZES,
    'uv_limit':'Below 80%: 12/6-pixel safety margins and curved/end-face islands. Four pack variants tried; maps not enlarged.',
    'movable':{'flashlight':['Clip','PrimaryButton','ModeButton','TailCap','Bezel'],
               'mount':['CapHinge','MovingJaw','LockScrew','ClampPadNegative','ClampPadPositive']},
    'controls':{'CapHinge':{'axis':'Z','open_deg':65,'pivot_m':[-.0155,.024,0]}},
    'collision':'Separate simple shapes in DozorAsset loader; no HP collision',
    'integration':'Assets and validation stand only; gameplay, prices and FPS hands unchanged'}
keepers=[]
for key in ['f1','f1m','f1s','p']:
    atlas='P' if key=='p' else 'F1';root=empty('DOZOR_'+key.upper());mat=material(key);frame=P if key=='p' else F
    roles=sorted({r['role'] for r in REC['parts'].values() if r['atlas']==atlas})
    for r in roles:
        pieces=[o for o in src if REC['parts'][o.name]['atlas']==atlas and REC['parts'][o.name]['role']==r]
        pivot=(-.0155,.024,0) if r=='CapHinge' else (0,.024,0) if key=='p' else (0,0,-.0604) if r in ('PrimaryButton','ModeButton') else (0,0,0)
        o=join_pieces(pieces,r,root,frame,pivot);o.data.materials.clear();o.data.materials.append(mat)
        for f in o.data.polygons:f.material_index=0
    if key!='p':
        # 32-segment thin closed glass shell. Its visible contour matches the 27.04 mm source lens.
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.01352,depth=.0008,location=(0,0,.07645),rotation=(0,0,0))
        lens=bpy.context.object;lens.name='Lens';lens.parent=root
        glass=bpy.data.materials.new('DOZOR_GL_AR');glass.use_nodes=True
        bs=glass.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.96,.97,.97,1)
        bs.inputs['Roughness'].default_value=.02;bs.inputs['Transmission Weight'].default_value=1;bs.inputs['IOR'].default_value=1.52
        bs.inputs['Alpha'].default_value=.075;glass.surface_render_method='DITHERED';lens.data.materials.append(glass)
        for f in lens.data.polygons:f.use_smooth=len(f.vertices)==4
        empty('LightEmitter',root,(0,0,.0805));empty('RingMountSocket',root);empty('GripAxis',root,(0,0,-.002))
        empty('TailSwitch',root,(0,.0039,-.0625))
    else:empty('FlashlightSocket',root,(0,.024,0))
    nodes={}
    for o in root.children_recursive:
        if o.type=='MESH':o.data.calc_loop_triangles();nodes[o.name]=len(o.data.loop_triangles)
    count=sum(nodes.values());manifest['triangles'][key]=count;manifest['nodes'][key]=nodes
    keepers+=export(root,key)
    root.location.x={'f1':-.09,'f1m':0,'f1s':.09,'p':.18}[key] # preview row only, after export
assert manifest['triangles']['f1']+manifest['triangles']['p']<=TRIANGLE_LIMIT,manifest['triangles']
for ob in src:bpy.data.objects.remove(ob,do_unlink=True)
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
camera_data=bpy.data.cameras.new('Game review camera');camera=bpy.data.objects.new('Review.Camera',camera_data);sc.collection.objects.link(camera)
camera.location=(.30,.32,.43);forward=(Vector((.04,.0,.009))-camera.location).normalized()
right=forward.cross(Vector((0,1,0))).normalized();up=right.cross(forward).normalized()
camera.rotation_euler=Matrix((right,up,-forward)).transposed().to_euler();camera_data.type='ORTHO';camera_data.ortho_scale=.37;camera_data.clip_start=.001;sc.camera=camera
sc.render.resolution_x=1600;sc.render.resolution_y=1000;sc.render.resolution_percentage=100
sc.cycles.samples=32;sc.cycles.use_denoising=True
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'DOZOR_Game_v01.blend'))
bpy.ops.wm.save_as_mainfile(filepath=str(ASSET/'models/DOZOR_Game_v01.blend'))
print('GAME EXPORT',manifest['triangles'],'complete assembly',manifest['triangles']['f1']+manifest['triangles']['p'],flush=True)
