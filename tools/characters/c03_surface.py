"""Фотографическая структура материалов и направленное истирание C03."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,importlib,math,io
from contextlib import redirect_stdout
import bpy
import m02_custom_clothes as G
import m02_custom_clothes_deliver as D
import wardrobe_materials as M
import c03_polish as P
import c03_refine as R


def refine():
    U=importlib.import_module('bl_ext.blender_org.ucupaint');M.U=U
    for key in ['denim','nylon_olive','suede']:
        mat=bpy.data.materials['C03 | '+key];tree=P.native(mat)
        for ly in tree.yp.layers:
            if ly.name.startswith('03 |'):
                ly.blend_type='MIX' if key in ['denim','suede'] else 'MULTIPLY'
                M.sync(ly,'intensity_value',.86 if key=='denim' else .60 if key=='suede' else .74)
                for mod in ly.modifiers:
                    if mod.type=='HUE_SATURATION':
                        node=U.common.get_mod_tree(ly).nodes[mod.huesat]
                        node.inputs['Saturation'].default_value=.74 if key=='denim' else .15 if key=='suede' else 0
                        node.inputs['Value'].default_value=1.0 if key=='denim' else 1.12 if key=='suede' else 2.25
            if ly.name.startswith('06 |'):
                M.sync(ly,'intensity_value',.94 if key=='denim' else .96)
                for root,ch in zip(tree.yp.channels,ly.channels):
                    if root.name=='Color':M.sync(ch,'override_color',(.145,.188,.232) if key=='denim' else (.155,.159,.116) if key=='nylon_olive' else (.20,.155,.106))
            if ly.name.startswith('10 |'):M.sync(ly,'intensity_value',.83)
            U.node_connections.reconnect_layer_nodes(ly)
        U.node_connections.reconnect_yp_nodes(tree)
    items={str(c['wardrobe_id']):c for c in bpy.data.collections if c.get('wardrobe_id') and c.asset_data}
    for ob in items['T03'].objects:
        if ob.type!='MESH':continue
        attr=ob.data.color_attributes.get('WardrobeWear');dirty=ob.data.color_attributes.get('C03EmbeddedGrime')
        if attr:
            for d in attr.data:
                value=G.clamp(d.color[0]*2.6);d.color=(value,value,value,1)
        if dirty:
            for d in dirty.data:
                value=G.clamp(d.color[0]*1.6);d.color=(value,value,value,1)
        if 'grey jersey under the open neck' in ob.name:
            for v in ob.data.vertices:
                p=v.co;p.x*=.75;p.z-=.013*G.smooth(1.47,1.53,p.z)
            ob.data.update()
    # Макушка сохраняет радиальный запас над реальной головой М02.
    # Аналитическая сфера здесь недопустима: голова имеет другой профиль.


def main(args):
    D.enable_layers();bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()));bpy.context.preferences.filepaths.save_version=0
    with redirect_stdout(io.StringIO()):refine()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);file=out/'C03_Refinement_M02.blend'
    bpy.context.scene.camera=bpy.data.objects['C03_ThreeQuarter'];bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False)
    # Повторное открытие фиксирует новые свойства и обеспечивает совпадение снимков с выдачей.
    bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
    R.render(out,args.views,args.samples);print('C03_SURFACE_PASS '+str(file),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--views',default='ThreeQuarter,Jacket,Shoes,Back,Jeans,Mask,Front,Side');p.add_argument('--samples',type=int,default=48)
    main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
