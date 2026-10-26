"""Unsaved clearcoat diagnostic under the unchanged v03 studio lights."""
from pathlib import Path
import bpy

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v03_studio.blend'))
mat=bpy.data.materials['Padlock_PBR_from_Painter'];n=mat.node_tree.nodes;l=mat.node_tree.links
bsdf=next(x for x in n if x.type=='BSDF_PRINCIPLED')
mask=n.new('ShaderNodeTexImage');mask.image=bpy.data.images.load(str(WORK/'textures'/'contact_v03'/'paint_finish.png'))
mask.image.colorspace_settings.name='Non-Color'
weight=n.new('ShaderNodeMath');weight.operation='MULTIPLY';weight.inputs[1].default_value=.95
l.new(mask.outputs['Color'],weight.inputs[0]);l.new(weight.outputs[0],bsdf.inputs['Coat Weight'])
geometry=n.new('ShaderNodeNewGeometry');l.new(geometry.outputs['Normal'],bsdf.inputs['Coat Normal'])
noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=230
l.new(geometry.outputs['Position'],noise.inputs['Vector'])
rough=n.new('ShaderNodeMath');rough.operation='MULTIPLY_ADD';rough.inputs[1].default_value=.20;rough.inputs[2].default_value=.09
l.new(noise.outputs['Fac'],rough.inputs[0]);l.new(rough.outputs[0],bsdf.inputs['Coat Roughness'])
old=bsdf.inputs['Roughness'].links[0].from_socket
mix=n.new('ShaderNodeMixRGB');l.new(mask.outputs['Color'],mix.inputs[0]);l.new(old,mix.inputs[1]);mix.inputs[2].default_value=(.22,.22,.22,1)
l.new(mix.outputs[0],bsdf.inputs['Roughness'])
scene=bpy.context.scene;scene.frame_set(74);scene.render.engine='CYCLES';scene.cycles.device='CPU'
scene.cycles.samples=64;scene.cycles.use_denoising=False
scene.render.resolution_x=1100;scene.render.resolution_y=807
scene.render.filepath=str(WORK/'previews'/'v04_gloss_probe.png')
bpy.ops.render.render(write_still=True)
print('UNSAVED_GLOSS_PROBE',scene.render.filepath)
