"""Все 101 .blend открываются непосредственно из передаваемой библиотеки."""
from pathlib import Path
import argparse
import json
import sys
import time

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
import process as P
from plan import DELIVERY, sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ids',default='')
    parser.add_argument('--renderids',default='R01,R02,R03,R04,R05,R06')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    selected=set(args.ids.split(',')) if args.ids else None
    renderids=set(args.renderids.split(','))
    manifest=json.loads((DELIVERY/'manifest.json').read_text(encoding='utf-8'))
    P.M.native()
    results=[]
    for a in manifest['assets']:
        if selected and a['id'] not in selected:
            continue
        start=time.time()
        folder=DELIVERY/'assets'/a['folder']
        images=json.loads((folder/'checks/image_manifest.json').read_text(encoding='utf-8'))
        original=P.AUDIT.snapshot(a['source_blend'])
        model=DELIVERY/a['model']
        result=P.validate(a,original,model,images)
        result['reopened_from_delivery']=True
        result['delivered_file_hash_matches_manifest']=sha(model)==a['blend_sha256']
        result['passed'] &= result['delivered_file_hash_matches_manifest']
        if not result['passed']:
            (folder/'checks/delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            raise RuntimeError('Delivery validation failed: '+a['id']+' '+str(result['errors'])+' '+str(result['geometry_changes']))
        if a['id'] in renderids:
            # Fresh pictures from the final .blend; do not save diagnostic changes to geometry or materials.
            P.M.clear_cache()
            sc=bpy.context.scene
            prefs=bpy.context.preferences.addons['cycles'].preferences
            prefs.compute_device_type='OPTIX'
            prefs.get_devices()
            for d in prefs.devices:
                d.use=d.type=='OPTIX'
            sc.cycles.device='GPU' if any(d.use for d in prefs.devices) else 'CPU'
            sc.cycles.samples=24
            sc.cycles.use_denoising=True
            P.render_views(a,folder,True)
            result['fresh_views_from_delivery']=3
        else:
            result['fresh_views_from_saved_source']=3
        (folder/'checks/delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        results.append(result)
        print('URBAN_DELIVERY_VERIFIED',a['id'],round(time.time()-start,2),'sec',flush=True)
    reports=[json.loads(p.read_text(encoding='utf-8')) for p in (DELIVERY/'assets').glob('*/checks/delivery_validation.json')]
    summary=dict(models=len(reports),passed=sum(r['passed'] for r in reports),
        native_materials=sum(r['native_materials'] for r in reports),
        native_layers=sum(r['native_layers'] for r in reports),
        packed_image_datablocks=sum(r['packed_images'] for r in reports),
        geometry_objects_checked=sum(r['geometry_objects_checked'] for r in reports),
        all_101_passed=len(reports)==101 and all(r['passed'] for r in reports),
        all_reopened_from_delivery=all(r['reopened_from_delivery'] for r in reports),
        texture_approved=False,game_export=False,results=[dict(id=r['id'],passed=r['passed'],
            sha256=r['blend_sha256']) for r in reports])
    (DELIVERY/'checks').mkdir(exist_ok=True)
    (DELIVERY/'checks/delivery_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('URBAN_DELIVERY_SUMMARY',json.dumps({k:v for k,v in summary.items() if k!='results'}),flush=True)


if __name__=='__main__':
    main()
