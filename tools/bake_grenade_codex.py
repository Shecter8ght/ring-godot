"""High resolution PBR images for the art source; no mesh simplification/export."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

import bpy
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT/'_asset_src/grenade_codex'
MASTER=OUT/'Grenade_MkII_UCUPaint_Codex_v06.blend'
PREVIEW=OUT/'Grenade_MkII_PBR_Preview_v06.blend'
MAPS=OUT/'textures/pbr_v06'
MAPS.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
T.P.native()
bpy.ops.wm.open_mainfile(filepath=os.environ.get('GRENADE_BAKE_SOURCE',str(MASTER)))
scene=bpy.context.scene
scene.frame_set(1)
bpy.context.view_layer.update()
scene.render.engine='CYCLES'
scene.cycles.samples=1
scene.cycles.device='GPU'
scene.render.bake.use_selected_to_active=False
scene.render.bake.use_clear=True
scene.render.bake.margin=24
scene.render.bake.margin_type='EXTEND'
pref=bpy.context.preferences.addons['cycles'].preferences
pref.compute_device_type='OPTIX'
pref.get_devices()
for dev in pref.devices:
    dev.use=dev.type=='OPTIX'
original_links={}
results=json.loads((MAPS/'manifest.partial.json').read_text(encoding='utf8')) if os.environ.get('GRENADE_BAKE_SOURCE') else []
materials={}


def select(objects):
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objects:
        ob.hide_set(False)
        ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]


for suffix,size in [('Body_CastIron_OD',8192),('Lever_SilverAndDarkSteel',8192),
                    ('Fuze_LightZincAlloy',8192),('PinRing_AgedSteel',4096)]:
    mat=bpy.data.materials['UCUPaint_'+suffix]
    objects=[o for o in scene.objects if o.type=='MESH' and mat in list(o.data.materials)]
    select(objects)
    expected=[f'MkII_{suffix}_{label}_{size//1024}K.png' for label in ['BaseColor','Metallic','Roughness','NormalGL']]
    completed={r['file']:r for r in results}
    if all(f in completed and (MAPS/f).is_file() and
           hashlib.sha256((MAPS/f).read_bytes()).hexdigest()==completed[f]['sha256'] for f in expected) and all('PBRUV' in ob.data.uv_layers for ob in objects):
        images={}
        for channel,file in zip(['Color','Metallic','Roughness','Normal'],expected):
            im=bpy.data.images.get(file) or bpy.data.images.load(str(MAPS/file),check_existing=True)
            im.use_fake_user=True
            images[channel]=im
            im.buffers_free()
        materials[mat.name]=(objects,images)
        print('PBR_RESUME_GROUP_OK',suffix,flush=True)
        continue
    for ob in scene.objects:
        if ob.type=='MESH':
            ob.hide_render=ob not in objects
    for ob in objects:
        uv=ob.data.uv_layers.get('PBRUV') or ob.data.uv_layers.new(name='PBRUV')
        ob.data.uv_layers.active=uv
        uv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.008,
                             area_weight=0,correct_aspect=True,scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    # New v05 meshes had no source unwrap. Keep the original body UVMap intact;
    # copy the unique atlas into the newly created authoring UV on other meshes.
    for ob in objects:
        if ob.name not in {'GrenadeBody','BottomPlug'}:
            coords=np.empty(len(ob.data.uv_layers['PBRUV'].data)*2,np.float32)
            ob.data.uv_layers['PBRUV'].data.foreach_get('uv',coords)
            ob.data.uv_layers['UVMap'].data.foreach_set('uv',coords)
    uv_report=[]
    for ob in objects:
        uv=ob.data.uv_layers['PBRUV']
        ob.data.calc_loop_triangles()
        coords=np.empty(len(uv.data)*2,np.float32)
        uv.data.foreach_get('uv',coords)
        coords=coords.reshape(-1,2)
        tri=np.array([t.loops for t in ob.data.loop_triangles])
        a,b,c=coords[tri[:,0]],coords[tri[:,1]],coords[tri[:,2]]
        areas=.5*np.abs((b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0]))
        assert np.isfinite(coords).all() and coords.min()>=-1e-5 and coords.max()<=1.00001,ob.name
        uv_report.append({'object':ob.name,'triangles':len(tri),'uv_area':float(areas.sum()),
                          'tiny_uv_triangles':int((areas<1e-11).sum())})
    nt=mat.node_tree
    yp=next(n for n in nt.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
    surface=output.inputs['Surface']
    old_socket=surface.links[0].from_socket
    emit=nt.nodes.new('ShaderNodeEmission')
    target=nt.nodes.new('ShaderNodeTexImage')
    target.label='High resolution PBR bake target - no shader link'
    images={}
    for channel,kind in [('Color','EMIT'),('Metallic','EMIT'),('Roughness','EMIT'),('Normal','NORMAL')]:
        label='BaseColor' if channel=='Color' else 'NormalGL' if channel=='Normal' else channel
        file=f'MkII_{suffix}_{label}_{size//1024}K.png'
        im=bpy.data.images.new(file,width=size,height=size,alpha=False,float_buffer=True,is_data=channel!='Color')
        im.colorspace_settings.name='sRGB' if channel=='Color' else 'Non-Color'
        if channel=='Normal':
            im.generated_color=(.5,.5,1,1)
        target.image=im
        for node in nt.nodes:
            node.select=False
        target.select=True
        nt.nodes.active=target
        if kind=='EMIT':
            nt.links.new(yp.outputs[channel],emit.inputs['Color'])
            nt.links.new(emit.outputs['Emission'],surface)
            scene.cycles.samples=1
        else:
            nt.links.new(old_socket,surface)
            scene.cycles.samples=8
        print('PBR_BAKE_BEGIN',file,flush=True)
        bpy.ops.object.bake(type=kind,normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z')
        scene.render.image_settings.file_format='PNG'
        scene.render.image_settings.color_mode='RGB'
        scene.render.image_settings.color_depth='16'
        # Image.save_render applies color management; use raw image save for PBR.
        im.file_format='PNG'
        im.filepath_raw=str(MAPS/file)
        im.save()
        pixels=np.empty(len(im.pixels),np.float32)
        im.pixels.foreach_get(pixels)
        assert np.isfinite(pixels).all(),file
        row={'file':file,'channel':label,'size':[size,size],'color_space':im.colorspace_settings.name,
             'sha256':hashlib.sha256((MAPS/file).read_bytes()).hexdigest(),
             'min_r':float(pixels[::4].min()),'max_r':float(pixels[::4].max()),
             'uv':'PBRUV','uv_report':uv_report}
        results.append(row)
        del pixels
        # Reload the encoded PNG so packed data exactly equals the supplied file.
        target.image=None
        bpy.data.images.remove(im)
        im=bpy.data.images.load(str(MAPS/file),check_existing=False)
        im.name=file
        im.pack()
        im.filepath='//textures/pbr_v06/'+file
        im.use_fake_user=True
        images[channel]=im
        im.buffers_free()
        print('PBR_BAKE_OK',file,flush=True)
    nt.links.new(old_socket,surface)
    nt.nodes.remove(emit)
    nt.nodes.remove(target)
    materials[mat.name]=(objects,images)
    (MAPS/'manifest.partial.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    T.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/f'checkpoint_v06_bake_{suffix}.blend'),relative_remap=False)
    print('PBR_GROUP_CHECKPOINT_OK',suffix,flush=True)

(MAPS/'manifest.json').write_text(json.dumps(results,indent=2),encoding='utf8')
scene.frame_set(1)
for ob in scene.objects:
    if ob.type=='MESH':ob.hide_render=False
scene.cycles.samples=96
scene.render.image_settings.color_depth='8'
T.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(MASTER),relative_remap=False)

# A second studio copy uses the maps for instant viewport preview and animations.
# Every native stack remains in the editing master and as a retained datablock.
for name,(objects,images) in materials.items():
    native=bpy.data.materials[name]
    native.use_fake_user=True
    baked=bpy.data.materials.new(name.replace('UCUPaint_','PBR_Preview_'))
    baked.use_nodes=True
    p=baked.node_tree.nodes.get('Principled BSDF')
    uv=baked.node_tree.nodes.new('ShaderNodeUVMap')
    uv.uv_map='PBRUV'
    for channel,im in images.items():
        tex=baked.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image=im
        baked.node_tree.links.new(uv.outputs['UV'],tex.inputs['Vector'])
        if channel=='Normal':
            normal=baked.node_tree.nodes.new('ShaderNodeNormalMap')
            normal.uv_map='PBRUV'
            baked.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color'])
            baked.node_tree.links.new(normal.outputs['Normal'],p.inputs['Normal'])
        else:
            socket='Base Color' if channel=='Color' else channel
            baked.node_tree.links.new(tex.outputs['Color'],p.inputs[socket])
    for ob in objects:
        ob.data.materials[0]=baked
bpy.ops.wm.save_as_mainfile(filepath=str(PREVIEW),relative_remap=False)
print('PBR_TEXTURE_SET_OK',len(results),'maps',str(PREVIEW),flush=True)
