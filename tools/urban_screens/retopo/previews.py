"""Actual baked front/rear/detail views; source-matched studio and camera recipe."""
from pathlib import Path
import argparse
import json
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,rows,write,sha
import bake as K


def main():
    p=argparse.ArgumentParser(); p.add_argument('--ids',default=''); p.add_argument('--resume',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    ids=set(args.ids.split(',')) if args.ids else None
    done=0
    for a in rows():
        if ids and a['id'] not in ids:continue
        model=WORK/a['retopo_model']; folder=model.parent.parent
        check=folder/'checks/bake.json'; proof=folder/'checks/previews.json'
        if not check.exists():continue
        result=json.loads(check.read_text(encoding='utf-8'))
        if not result.get('passed') or sha(model)!=result['model_sha256']:continue
        if args.resume and proof.exists():
            data=json.loads(proof.read_text(encoding='utf-8'))
            if data['model_sha256']==result['model_sha256']:continue
        bpy.ops.wm.open_mainfile(filepath=str(model))
        K.gpu(); sc=bpy.context.scene; sc.cycles.samples=24; sc.cycles.use_denoising=True
        K.P.render_views(a,folder,detail=True)
        write(proof,dict(id=a['id'],model_sha256=result['model_sha256'],
            images={name:sha(folder/'previews'/name) for name in ('front34.png','rear34.png','detail.png')}))
        done+=1
        print('PREVIEW_DONE',a['id'],flush=True)
    print('PREVIEWS_COMPLETE',done,flush=True)


if __name__=='__main__':main()
