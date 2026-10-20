"""Зафиксировать новые свойства управления и повторно открыть сцену перед съёмкой."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json,bpy
import m02_custom_clothes_deliver as D
import wardrobe_geometry as W
import c03_refine as R


def main(args):
    D.enable_layers();bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()));bpy.context.preferences.filepaths.save_version=0
    control=bpy.data.objects['RING | Wardrobe Controls'];items={str(c['wardrobe_id']):c for c in bpy.data.collections if c.get('wardrobe_id') and c.asset_data}
    report={'properties':dict(control.items()),'before':[]}
    for code,col in items.items():
        first=next(o for o in col.objects if o.type=='MESH');report['before'].append({'code':code,'hidden':first.hide_render,'drivers':[{'expression':f.driver.expression,'type':f.driver.type,'valid':f.driver.is_valid,'vars':[{'type':v.type,'path':v.targets[0].data_path,'target':v.targets[0].id.name if v.targets[0].id else None} for v in f.driver.variables]} for f in first.animation_data.drivers]})
        for ob in col.objects:
            if ob.type=='MESH' and not ob.data.uv_layers.get('UV_Fabric_Metres'):W.metric_uv(ob)
    for ob in bpy.data.objects:
        if ob.animation_data:
            for f in ob.animation_data.drivers:
                if any(v.targets[0].id==control for v in f.driver.variables):f.driver.type='SCRIPTED'
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);file=out/'C03_Refinement_M02.blend'
    for key in ['Ветровка','Джинсы','Обувь','Балаклава']:control[key]=True
    control.update_tag(refresh={'OBJECT','DATA','TIME'});bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(file),check_existing=False)
    bpy.ops.wm.open_mainfile(filepath=str(file));bpy.context.view_layer.update()
    control=bpy.data.objects['RING | Wardrobe Controls'];items={str(c['wardrobe_id']):c for c in bpy.data.collections if c.get('wardrobe_id') and c.asset_data}
    report['after']=[{'code':code,'visible':sum(not o.hide_render for o in col.objects),'meshes':sum(o.type=='MESH' for o in col.objects)} for code,col in items.items()]
    (out/'driver_reopen.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(not o.hide_render for col in items.values() for o in col.objects if o.type=='MESH'),report['after']
    R.render(out,args.views,args.samples);print('C03_REOPEN_RENDER_PASS '+str(file),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--views',default='ThreeQuarter,Jacket,Shoes,Back,Jeans,Mask');p.add_argument('--samples',type=int,default=40)
    main(p.parse_args(sys.argv[sys.argv.index('--')+1:]))
