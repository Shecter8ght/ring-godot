"""Быстрая проверка экспортированных карт Painter на той же подробной поверхности."""
import argparse
import sys
from pathlib import Path
import bpy

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
parser=argparse.ArgumentParser();parser.add_argument('--save',action='store_true')
parser.add_argument('--save-only',action='store_true')
parser.add_argument('--views',default='front_34,rear_34');parser.add_argument('--size',type=int,default=900)
parser.add_argument('--lighting',choices=['studio','side'],default='studio')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v02_texture_source.blend'))
files=list((WORK/'textures'/'export').glob('*.png'))
def find(token):
    found=[p for p in files if token in p.stem.lower()]
    if len(found)!=1:raise RuntimeError('Expected one '+token+' map: '+str(found))
    return found[0]
mat=bpy.data.materials.new('Padlock_PBR_from_Painter');mat.use_nodes=True
nodes=mat.node_tree.nodes;links=mat.node_tree.links
bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
bsdf.location=(0,180)
next(n for n in nodes if n.type=='OUTPUT_MATERIAL').location=(340,180)
def texture(path,data,x,y):
    n=nodes.new('ShaderNodeTexImage');n.image=bpy.data.images.load(str(path),check_existing=True)
    n.image.colorspace_settings.name='Non-Color' if data else 'sRGB';n.location=(x,y)
    n.image.pack();n.image.filepath='//../textures/export/'+path.name
    return n
color=texture(find('basecolor'),False,-700,300)
orm=texture(find('occlusionroughnessmetallic'),True,-700,0)
normal=texture(find('normal'),True,-700,-350)
links.new(color.outputs['Color'],bsdf.inputs['Base Color'])
split=nodes.new('ShaderNodeSeparateColor');split.mode='RGB';split.location=(-420,0)
links.new(orm.outputs['Color'],split.inputs[0]);links.new(split.outputs[1],bsdf.inputs['Roughness']);links.new(split.outputs[2],bsdf.inputs['Metallic'])
nm=nodes.new('ShaderNodeNormalMap');nm.location=(-400,-300)
links.new(normal.outputs['Color'],nm.inputs['Color']);links.new(nm.outputs[0],bsdf.inputs['Normal'])
for obj in bpy.data.objects:
    if obj.get('stage')=='accepted_shape_highpoly_texture_copy':
        obj.data.materials.clear();obj.data.materials.append(mat);obj['stage']='textured_highpoly_candidate'
floor=bpy.data.objects.get('Studio_ground')
if floor:
    node=next(n for n in floor.active_material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    node.inputs['Base Color'].default_value=(.018,.018,.018,1)
    node.inputs['Roughness'].default_value=.90
for lamp in bpy.data.lights:
    lamp.energy*=.5
background=next(n for n in bpy.context.scene.world.node_tree.nodes if n.type=='BACKGROUND')
background.inputs['Strength'].default_value=.6
bpy.data.objects['Padlock_ROOT']['paint_source']='../painter/padlock_v02_textured.spp'
bpy.data.objects['Padlock_ROOT']['status']='Shape accepted 2026-10-26; Painter texture candidate v02, awaiting visual review'
scene=bpy.context.scene;scene.view_settings.exposure=-1.0
scene.render.resolution_x=scene.render.resolution_y=args.size;scene.cycles.samples=64
scene.cycles.use_denoising=False
scene.camera=bpy.data.objects['front_34']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
if args.save or args.save_only:
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'models'/'padlock_v02_textured.blend'),relative_remap=False)
if args.lighting=='side':
    from mathutils import Vector
    lamp=bpy.data.objects['Large_key'];lamp.location=(-.20,-.08,.16)
    lamp.rotation_euler=(Vector((0,0,.055))-lamp.location).to_track_quat('-Z','Y').to_euler()
    lamp.data.shape='DISK';lamp.data.size=.08
    for name in ('Broad_fill','Rear_fill'):
        bpy.data.objects[name].data.energy*=.22
    background.inputs['Strength'].default_value=.20
for name in ([] if args.save_only else args.views.split(',')):
    suffix='_textured' if args.lighting=='studio' else '_side_light'
    scene.camera=bpy.data.objects[name];scene.render.filepath=str(WORK/'previews'/(name+suffix+'.png'))
    bpy.ops.render.render(write_still=True);print('TEXTURE_PREVIEW',name,flush=True)
