"""Preview the actual Painter exports on the unchanged editable high-poly source."""
import bpy,json,pathlib,hashlib
ROOT=pathlib.Path('E:/Games/RING-godot')
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
sc=bpy.context.scene
spec=json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))

def mat(key,texset,glass=False):
    folder=OUT/'textures/factory'/key
    m=bpy.data.materials.new('DOZOR_'+key+' • Painter factory')
    m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial');out.location=(600,0)
    bs=nt.nodes.new('ShaderNodeBsdfPrincipled');bs.location=(300,0)
    nt.links.new(bs.outputs[0],out.inputs['Surface'])
    uv=nt.nodes.new('ShaderNodeUVMap');uv.uv_map='PainterUV';uv.location=(-1000,0)
    def image(suffix,space,y):
        path=folder/(texset+'_'+suffix+'.png')
        assert path.exists(),path
        im=bpy.data.images.load(str(path),check_existing=True);im.colorspace_settings.name=space;im.pack()
        node=nt.nodes.new('ShaderNodeTexImage');node.image=im;node.location=(-760,y)
        nt.links.new(uv.outputs[0],node.inputs['Vector'])
        return node
    color=image('baseColor','sRGB',300)
    orm=image('occlusionRoughnessMetallic','Non-Color',0)
    normal=image('normal','Non-Color',-300)
    sep=nt.nodes.new('ShaderNodeSeparateColor');sep.location=(-400,0)
    n=nt.nodes.new('ShaderNodeNormalMap');n.uv_map='PainterUV';n.location=(-150,-260)
    nt.links.new(color.outputs['Color'],bs.inputs['Base Color'])
    nt.links.new(orm.outputs['Color'],sep.inputs[0])
    nt.links.new(sep.outputs['Green'],bs.inputs['Roughness']);nt.links.new(sep.outputs['Blue'],bs.inputs['Metallic'])
    nt.links.new(normal.outputs['Color'],n.inputs['Color']);nt.links.new(n.outputs['Normal'],bs.inputs['Normal'])
    if glass:
        bs.inputs['Transmission Weight'].default_value=1
        bs.inputs['IOR'].default_value=1.52
        bs.inputs['Thin Film Thickness'].default_value=110
        bs.inputs['Thin Film IOR'].default_value=1.38
    m['authoring']='Substance 3D Painter • DOZOR_factory_v01.spp'
    m['stage']='Factory finish; no wear'
    return m

mats={v:mat(v,'DOZOR_F1') for v in ('F1','F1M','F1S')}
mats['P']=mat('P','DOZOR_P');mats['LENS']=mat('LENS','DOZOR_LENS',True)
collections=['01 • ДОЗОР Ф-1 • master shape','02 • ДОЗОР Ф-1М • shared housing',
             '03 • ДОЗОР Ф-1С • shared housing','04 • ДОЗОР-П • independent Picatinny mount']
for cname in collections:
    for ob in bpy.data.collections[cname].all_objects:
        if ob.type!='MESH':continue
        key='LENS' if '.solid_glass' in ob.name else 'P' if ob.name.startswith('P.') else 'F1M' if ob.name.startswith('F1M.') else 'F1S' if ob.name.startswith('F1S.') else 'F1'
        ob.material_slots[0].link='OBJECT';ob.material_slots[0].material=mats[key]

# Studio reflections from Blender's bundled studio environment; packed in the file.
hdr=pathlib.Path(bpy.utils.resource_path('LOCAL'))/'datafiles/studiolights/world/studio.exr'
assert hdr.exists(),hdr
world=bpy.data.worlds.new('ДОЗОР • студия Painter preview');world.use_nodes=True
nt=world.node_tree;nt.nodes.clear()
env=nt.nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(hdr));env.image.pack()
bg=nt.nodes.new('ShaderNodeBackground');bg.inputs['Strength'].default_value=.35
nt.links.new(env.outputs[0],bg.inputs['Color'])
out=nt.nodes.new('ShaderNodeOutputWorld');nt.links.new(bg.outputs[0],out.inputs[0]);sc.world=world
sc.cycles.samples=64;sc.cycles.use_denoising=True;sc.cycles.max_bounces=12;sc.cycles.transmission_bounces=8
sc.view_settings.view_transform='AgX'
for cname in collections:bpy.data.collections[cname].hide_render=False
cam=sc.camera;cam.location=(-.10,-.22,.235)
from mathutils import Vector
cam.rotation_euler=(Vector((.07,.03,.035))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.27
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        sp=area.spaces.active;sp.shading.type='RENDERED';sp.clip_start=.001
        sp.region_3d.view_location=(.07,.025,.035);sp.region_3d.view_distance=.26
bpy.ops.file.pack_all()
path=OUT/'models/DOZOR_Factory_Painter_v01.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(path))
spec['model']=str(path);spec['painter_project']=str(OUT/'painter/DOZOR_factory_v01.spp')
spec['authoring']='Substance 3D Painter; native editable layer stacks; exact catalogue functions sp_finish.build_set'
spec['accepted']=False
spec['texture_sets']={'DOZOR_F1':4096,'DOZOR_P':2048,'DOZOR_LENS':512}
(OUT/'finish-spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest=[]
for im in bpy.data.images:
    if im.source=='FILE' and im.packed_file:
        manifest.append({'image':im.name,'colorspace':im.colorspace_settings.name,'size':list(im.size),
                         'sha256':hashlib.sha256(im.packed_file.data).hexdigest()})
(OUT/'checks/factory-packed-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('FACTORY PREVIEW READY',path,flush=True)
