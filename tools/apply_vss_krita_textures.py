"""Карты, экспортированные Krita -> текстурированные .blend и GLB без изменения сетки."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src'/'vss_textured'

def apply(obj,folder,candidate=False):
    mat=B.material('VSS_Krita_'+obj.name,(.015,.018,.024),.8,.4)
    nodes,links=mat.node_tree.nodes,mat.node_tree.links;bsdf=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    for label in ('basecolor','orm','normal'):
        path=folder/(label+('_candidate' if candidate else '')+'.png')
        im=bpy.data.images.load(str(path),check_existing=False)
        im.name=label if obj.name=='Body' else obj.name+'_'+label
        im.colorspace_settings.name='sRGB' if label=='basecolor' else 'Non-Color';im.pack()
        node=nodes.new('ShaderNodeTexImage');node.image=im;node.label=label
        if label=='basecolor':links.new(node.outputs['Color'],bsdf.inputs['Base Color'])
        elif label=='normal':
            normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.16 if obj.name in ('Metal_Polymer','Wood') else .20
            links.new(node.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],bsdf.inputs['Normal'])
        else:
            rgb=nodes.new('ShaderNodeSeparateColor');B.enum_set(rgb,'mode','RGB')
            links.new(node.outputs['Color'],rgb.inputs[0]);links.new(rgb.outputs['Green'],bsdf.inputs['Roughness']);links.new(rgb.outputs['Blue'],bsdf.inputs['Metallic'])
            from io_scene_gltf2.blender.imp.pbrMetallicRoughness import get_settings_group
            group=get_settings_group()
            marker=nodes.new('ShaderNodeGroup');marker.node_tree=group
            links.new(rgb.outputs['Red'],marker.inputs['Occlusion'])
    if obj.name=='Wood':bsdf.inputs['Coat Weight'].default_value=.28;bsdf.inputs['Coat Roughness'].default_value=.26
    obj.data.materials.clear();obj.data.materials.append(mat)
    for face in obj.data.polygons:face.material_index=0
    obj['texture_authoring']='Krita 5.3.4; geometry-aware source layers and editable KRA'
    return mat

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--id',required=True);parser.add_argument('--candidate',action='store_true');parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);folder=RAW/args.id;meta=json.loads((folder/'prepare.json').read_text())
    bpy.ops.wm.open_mainfile(filepath=str(folder/(args.id+'_UV.blend')))
    root=bpy.data.objects[args.id];mesh_objects=[o for o in root.children_recursive if o.type=='MESH']
    before=E.bounds(mesh_objects);before_tris=sum(E.triangles(o) for o in mesh_objects)
    for image in list(bpy.data.images):
        if image.name in ('basecolor','orm','normal'):image.name+='_Previous'
    for label in meta['atlas_objects']:
        atlas=folder/label
        if not args.candidate and json.loads((atlas/'krita-report.json').read_text())['status']!='PASS':raise RuntimeError('Krita not verified')
        apply(bpy.data.objects[label],atlas,args.candidate)
    B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    bpy.context.view_layer.update()
    if args.candidate:
        # Временный вид не выдаётся за финальный экспорт Krita.
        name=args.id+'_Candidate.blend'
    else:name=args.id+'_Textured.blend'
    try:bpy.context.scene.render.engine='BLENDER_EEVEE'
    except TypeError:pass
    B.save_scene(folder/name)
    if not args.candidate:
        glb=folder/(args.id+'.glb');E.active(root)
        for obj in root.children_recursive:obj.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(glb),export_format='GLB',use_selection=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False)
        after=E.bounds(mesh_objects)
        report={'status':'PASS','triangles':before_tris,'bounds':after,'atlas_objects':meta['atlas_objects'],
                'source_sha256':meta['native_sha256'],'source':meta['native'],
                'source_unchanged':hashlib.sha256(Path(meta['native']).read_bytes()).hexdigest()==meta['native_sha256'],
                'glb_sha256':hashlib.sha256(glb.read_bytes()).hexdigest(),'Krita_maps':True}
        if before!=after:raise RuntimeError('Changed geometry bounds')
        for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.ops.import_scene.gltf(filepath=str(glb))
        imported=[o for o in bpy.context.scene.objects if o.type=='MESH']
        report['reimport_bounds']=E.bounds(imported);report['reimport_triangles']=sum(E.triangles(o) for o in imported)
        if report['reimport_triangles']!=before_tris:raise RuntimeError('GLB changed triangles')
        if max(abs(a-b) for a,b in zip(after['dimensions_mm'],report['reimport_bounds']['dimensions_mm']))>.025:raise RuntimeError('GLB changed dimensions')
        (folder/'texturing-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        bpy.ops.wm.open_mainfile(filepath=str(folder/name))
        B.COLLECTIONS.clear();B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    if args.render:
        if args.id=='VSS_Vintorez_Picatinny':views=[('beauty','Camera_Beauty_Right',1800,800),('stock','Camera_Stock_Detail',1300,900),('receiver','Camera_Receiver_Detail',1300,850)]
        elif args.id.startswith('Cartridge'):views=[('beauty','Camera_Cartridge',1500,800),('base','Camera_Cartridge_Base',1000,800)]
        elif args.id.startswith('Magazine'):views=[('beauty','Camera_Beauty',1300,1000),('top','Camera_Top',1200,1000)]
        else:
            cams=[o for o in bpy.context.scene.objects if o.type=='CAMERA']
            views=[('beauty',next((c.name for c in cams if 'Beauty' in c.name),cams[0].name),1600,850)]
        B.render_views(folder,'candidate' if args.candidate else 'textured',views)
    print('VSS_TEXTURE_APPLIED',args.id,'candidate' if args.candidate else 'Krita verified',flush=True)
if __name__=='__main__':main()
