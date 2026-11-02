"""Bake accepted Painter-on-HP to LP atlases using exploded, matched source groups.

Each source is moved with its own LP piece before joining; nearby components cannot
project onto each other. The accepted file is only read. Existing Painter AO is transferred.
"""
import sys,json,pathlib,time
import bpy,bmesh,numpy as np
from mathutils import Vector
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
REC=json.loads((WORK/'parts.json').read_text(encoding='utf-8'))
bpy.context.preferences.use_preferences_save=False
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.samples=8;sc.cycles.use_denoising=False
pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='OPTIX';pref.get_devices()
for d in pref.devices:d.use=d.type!='CPU'
sc.cycles.device='GPU';sc.render.bake.margin=5;sc.render.bake.margin_type='EXTEND'
sc.render.bake.use_selected_to_active=True;sc.render.bake.normal_space='TANGENT'
sc.render.bake.use_cage=True;sc.render.bake.max_ray_distance=.002
dg=bpy.context.evaluated_depsgraph_get()
originals={o.name:o for o in bpy.data.objects}
for ob in originals.values():ob.hide_render=True
targets=list(REC['parts'])
with bpy.data.libraries.load(str(WORK/'dozor_lp.blend'),link=False) as (a,b):b.objects=list(targets)
low_by_name=dict(zip(targets,b.objects))
coll=bpy.data.collections.new('DOZOR_MATCHED_BAKE');sc.collection.children.link(coll)
for ob in b.objects:coll.objects.link(ob)
report=[]

def join(objs,name):
    select(objs);bpy.ops.object.join();o=bpy.context.object;o.name=name;return o

for key in ['F1','P']:
    lows=[];highs=[];extrusions=[]
    for i,(name,part) in enumerate(REC['parts'].items()):
        if part['atlas']!=key:continue
        low=low_by_name[name];offset=Vector(((i%10)*.35,(i//10)*.35,0))
        low.location+=offset;low.hide_render=False;lows.append(low)
        extrusions.extend([part['cage_mm']*.001]*len(low.data.vertices))
        for source in part['sources']:
            src=originals[source]
            me=bpy.data.meshes.new_from_object(src.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
            bm=bmesh.new();bm.from_mesh(me)
            if bm.calc_volume(signed=True)<0:
                bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(me)
            bm.free()
            me.materials.clear()
            for slot in src.material_slots:me.materials.append(slot.material)
            hi=bpy.data.objects.new('BAKE_HIGH__'+source,me);coll.objects.link(hi)
            hi.matrix_world=src.matrix_world.copy();hi.location+=offset
            hi.hide_render=False
            select([hi]);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            highs.append(hi)
    # Join preserves component vertex order with the active object's vertices first.
    # A per-vertex cage displacement is stored before joining rather than assuming order.
    for low in lows:
        # Export splits hard normals. Split the bake copy too: averaged vertex
        # normals made the cage cross narrow annular grooves and missed HP rays.
        bm=bmesh.new();bm.from_mesh(low.data)
        bmesh.ops.split_edges(bm,edges=[e for e in bm.edges if not e.smooth])
        bm.to_mesh(low.data);bm.free()
        distance=REC['parts'][low.name]['cage_mm']*.001
        attr=low.data.attributes.new('bake_cage','FLOAT','POINT')
        attr.data.foreach_set('value',np.full(len(low.data.vertices),distance,np.float32))
    low=join(lows,'BAKE_TARGET_'+key);high=join(highs,'BAKE_SOURCE_'+key)
    low.data.uv_layers.active=low.data.uv_layers['GameUV'];low.data.uv_layers['GameUV'].active_render=True
    cage=low.copy();cage.data=low.data.copy();coll.objects.link(cage);cage.name='CAGE_'+key
    dist=np.empty(len(cage.data.vertices),np.float32);cage.data.attributes['bake_cage'].data.foreach_get('value',dist)
    for v,d in zip(cage.data.vertices,dist):v.co+=v.normal*float(d)
    cage.hide_render=True
    sc.render.bake.cage_object=cage
    mat=bpy.data.materials.new('TARGET_'+key);mat.use_nodes=True
    low.data.materials.clear();low.data.materials.append(mat)
    for f in low.data.polygons:f.material_index=0
    node=mat.node_tree.nodes.new('ShaderNodeTexImage');mat.node_tree.nodes.active=node
    highmats=list(set(high.data.materials))
    saved={m:next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED') for m in highmats}
    channels=[('normal',None),('orm',None)]+[('base_color',v) for v in (('F1','F1M','F1S') if key=='F1' else ('P',))]+[('hit_coverage',None)]
    for channel,variant in channels:
        for m in highmats:
            nt=m.node_tree;out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');bs=saved[m]
            if channel=='normal':nt.links.new(bs.outputs[0],out.inputs['Surface']);continue
            emit=nt.nodes.get('DOZOR_BAKE_EMISSION') or nt.nodes.new('ShaderNodeEmission')
            if channel=='hit_coverage':
                for link in list(emit.inputs['Color'].links):nt.links.remove(link)
                emit.inputs['Color'].default_value=(1,1,1,1);nt.links.new(emit.outputs[0],out.inputs['Surface']);continue
            image_node=next(n for n in nt.nodes if n.type=='TEX_IMAGE' and ('baseColor' in n.image.name if channel=='base_color' else 'occlusionRoughnessMetallic' in n.image.name))
            if channel=='base_color':
                texset='DOZOR_F1' if key=='F1' else 'DOZOR_P'
                im=bpy.data.images.load(str(ASSET/'textures/working100'/variant/(texset+'_baseColor.png')),check_existing=True)
                im.colorspace_settings.name='sRGB';image_node.image=im
            nt.links.new(image_node.outputs['Color'],emit.inputs['Color']);nt.links.new(emit.outputs[0],out.inputs['Surface'])
        im=bpy.data.images.new('GAME_'+key+'_'+channel+'_'+str(variant),SIZES[key],SIZES[key],alpha=False,float_buffer=channel=='normal')
        im.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
        im.generated_color=(.5,.5,1,1) if channel=='normal' else (1,1,1,1) if channel=='orm' else (0,0,0,1)
        node.image=im
        select([high,low]);t0=time.time()
        print('BAKE_START',key,channel,variant,flush=True)
        bpy.ops.object.bake(type='NORMAL' if channel=='normal' else 'EMIT',use_clear=True,margin=0 if channel=='hit_coverage' else 5)
        filename=('dozor_'+str(variant).lower()+'_base_color.png') if channel=='base_color' else ('dozor_'+key.lower()+'_'+channel+'.png')
        if channel=='hit_coverage':filename='hit_coverage_'+key+'.png'
        im.filepath_raw=str((WORK if channel=='hit_coverage' else OUT)/filename);im.file_format='PNG';im.save()
        report.append({'atlas':key,'channel':channel,'variant':variant,'file':filename,'seconds':round(time.time()-t0,2)})
        print('BAKE_DONE',filename,flush=True)
    # Independent low-mesh UV coverage, for detecting missed projection rays.
    hit=mat.node_tree.nodes.new('ShaderNodeEmission');hit.inputs['Color'].default_value=(1,1,1,1)
    mat.node_tree.links.new(hit.outputs[0],mat.node_tree.nodes.get('Material Output').inputs['Surface'])
    im=bpy.data.images.new('UV_COVERAGE_'+key,SIZES[key],SIZES[key],alpha=False);im.colorspace_settings.name='Non-Color';node.image=im
    select([low]);bpy.ops.object.bake(type='EMIT',use_clear=True,use_selected_to_active=False,margin=0)
    im.filepath_raw=str(WORK/('uv_coverage_'+key+'.png'));im.file_format='PNG';im.save()
    for ob in [low,high,cage]:bpy.data.objects.remove(ob,do_unlink=True)
(WORK/'bake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('BAKE COMPLETE',len(report),flush=True)
