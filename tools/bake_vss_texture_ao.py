"""Локальный AO по неизменённой UV-сетке, без запекания большого светового пятна."""
from pathlib import Path
import argparse,json,sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
RAW=Path(__file__).resolve().parents[1]/'_asset_src/vss_textured'
def main():
    p=argparse.ArgumentParser();p.add_argument('--id',required=True);a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    folder=RAW/a.id;meta=json.loads((folder/'prepare.json').read_text());bpy.ops.wm.open_mainfile(filepath=str(folder/(a.id+'_UV.blend')))
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.device='CPU';scene.render.bake.margin=16
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and obj.name not in meta['atlas_objects']:obj.hide_render=True
    for label in meta['atlas_objects']:
        obj=bpy.data.objects[label];resolution=json.loads((folder/(label+'_surfaces.json')).read_text())['resolution']
        mat=bpy.data.materials.new('Local AO');mat.use_nodes=True;nodes=mat.node_tree.nodes;nodes.clear()
        out=nodes.new('ShaderNodeOutputMaterial');ao=nodes.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=.006 if label=='Wood' else .003
        ao.samples=24;emit=nodes.new('ShaderNodeEmission');mat.node_tree.links.new(ao.outputs['Color'],emit.inputs['Color']);mat.node_tree.links.new(emit.outputs[0],out.inputs['Surface'])
        image=bpy.data.images.new(label+'_cavityAO',width=resolution,height=resolution,alpha=False);image.colorspace_settings.name='Non-Color'
        target=nodes.new('ShaderNodeTexImage');target.image=image;nodes.active=target
        obj.data.materials.clear();obj.data.materials.append(mat)
        for face in obj.data.polygons:face.material_index=0
        E.active(obj);bpy.ops.object.bake(type='EMIT')
        image.filepath_raw=str(folder/label/'cavity_ao.png');B.enum_set(image,'file_format','PNG');image.save()
        print('LOCAL_AO_BAKED',a.id,label,flush=True)
if __name__=='__main__':main()
