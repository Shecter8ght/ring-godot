"""Только маска краски: поле из физических координат на проверенную UV-копию."""
from pathlib import Path
import bpy

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/'padlock_v02_texture_source.blend'))
target=bpy.data.images.new('Padlock_paint_coverage',width=2048,height=2048,alpha=False)
target.colorspace_settings.name='Non-Color'

def material(kind,field='paint'):
    mat=bpy.data.materials.new('MASK_'+field+'_'+kind);mat.use_nodes=True
    n=mat.node_tree.nodes;n.clear();links=mat.node_tree.links
    out=n.new('ShaderNodeOutputMaterial');em=n.new('ShaderNodeEmission')
    links.new(em.outputs[0],out.inputs['Surface'])
    if kind=='none':em.inputs['Color'].default_value=(0,0,0,1)
    else:
        tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(WORK/'textures'/'sources'/(field+'_'+kind+'.png')),check_existing=True)
        tex.image.colorspace_settings.name='Non-Color'
        geo=n.new('ShaderNodeNewGeometry')
        if kind=='band':
            scale=n.new('ShaderNodeVectorMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=(12.5,35,14.25)
            links.new(geo.outputs['Position'],scale.inputs[0])
            offset=n.new('ShaderNodeVectorMath');offset.operation='ADD';offset.inputs[1].default_value=(.5,.5,0)
            links.new(scale.outputs[0],offset.inputs[0]);links.new(offset.outputs[0],tex.inputs['Vector'])
            tex.projection='BOX';tex.projection_blend=.35
            color=tex.outputs['Color']
        else:
            split=n.new('ShaderNodeSeparateXYZ');links.new(geo.outputs['Position'],split.inputs[0])
            x=n.new('ShaderNodeMath');x.operation='MULTIPLY_ADD';x.inputs[1].default_value=12.5;x.inputs[2].default_value=.5
            z=n.new('ShaderNodeMath');z.operation='MULTIPLY';z.inputs[1].default_value=1/.0703
            links.new(split.outputs['X'],x.inputs[0]);links.new(split.outputs['Z'],z.inputs[0])
            combine=n.new('ShaderNodeCombineXYZ');links.new(x.outputs[0],combine.inputs['X']);links.new(z.outputs[0],combine.inputs['Y'])
            links.new(combine.outputs[0],tex.inputs['Vector']);tex.extension='EXTEND'
            normal=n.new('ShaderNodeSeparateXYZ');links.new(geo.outputs['Normal'],normal.inputs[0])
            facing=n.new('ShaderNodeMath');facing.operation='LESS_THAN' if kind=='front' else 'GREATER_THAN'
            facing.inputs[1].default_value=-.30 if kind=='front' else .30
            links.new(normal.outputs['Y'],facing.inputs[0])
            multiply=n.new('ShaderNodeMath');multiply.operation='MULTIPLY'
            links.new(tex.outputs['Color'],multiply.inputs[0]);links.new(facing.outputs[0],multiply.inputs[1])
            color=multiply.outputs[0]
        links.new(color,em.inputs['Color'])
    bake=n.new('ShaderNodeTexImage');bake.image=target;n.active=bake
    return mat

mats={kind:material(kind) for kind in ('front','rear','band','none')}
parts=[o for o in bpy.data.objects if o.get('stage')=='accepted_shape_highpoly_texture_copy']
bpy.ops.object.select_all(action='DESELECT')
for obj in parts:
    kind='front' if obj.name.startswith('Front_cheek') else 'rear' if obj.name.startswith('Rear_cheek') else 'band' if obj.name.startswith('Body_perimeter') else 'none'
    obj.data.materials.clear();obj.data.materials.append(mats[kind])
bpy.context.view_layer.objects.active=parts[0]
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1
scene.render.bake.use_clear=False
for obj in parts:
    if not obj.name.startswith(('Front_cheek','Rear_cheek','Body_perimeter')):continue
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.bake(type='EMIT',margin=3,use_clear=False)
    print('PAINT_MASK_PART',obj.name,flush=True)
target.filepath_raw=str(WORK/'textures'/'padlock_paint_mask.png');target.file_format='PNG';target.save()
print('PAINT_COVERAGE_READY',target.filepath_raw,flush=True)

target=bpy.data.images.new('Padlock_worn_stamp',width=2048,height=2048,alpha=False)
target.colorspace_settings.name='Non-Color'
front=next(obj for obj in parts if obj.name.startswith('Front_cheek'))
front.data.materials.clear();front.data.materials.append(material('front','stamp'))
bpy.ops.object.select_all(action='DESELECT');front.select_set(True)
bpy.context.view_layer.objects.active=front
bpy.ops.object.bake(type='EMIT',margin=3,use_clear=False)
target.filepath_raw=str(WORK/'textures'/'padlock_stamp_mask.png');target.file_format='PNG';target.save()
print('STAMP_MASK_READY',target.filepath_raw,flush=True)
