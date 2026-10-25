"""Prioritize visual review with native/baked images from identical saved studios."""
from pathlib import Path
import argparse
import json
import sys

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,SOURCE,rows,write


def main():
    results=[]
    for a in rows():
        folder=WORK/'assets'/a['folder']
        check=folder/'checks/bake.json'
        if not check.exists():continue
        result=json.loads(check.read_text(encoding='utf-8'))
        if not result.get('passed'):continue
        source=SOURCE/'assets'/a['folder']/'previews/front34.png'
        candidate=folder/'previews/front34.png'
        if not candidate.exists() or candidate.stat().st_mtime<(WORK/a['retopo_model']).stat().st_mtime:
            continue
        native=np.asarray(Image.open(source).convert('RGB'),dtype=np.float32)/255
        baked=np.asarray(Image.open(candidate).convert('RGB'),dtype=np.float32)/255
        if native.shape!=baked.shape:
            results.append(dict(id=a['id'],error='Different image dimensions',native=list(native.shape),baked=list(baked.shape)))
            continue
        delta=np.abs(native-baked)
        r=dict(id=a['id'],mae=float(delta.mean()),rmse=float(np.sqrt((delta**2).mean())),
            changed_pixels_gt_32=float((delta.max(axis=2)>32/255).mean()),
            native=str(source),baked=str(candidate),
            interpretation='Review aid only; not artistic approval or a replacement for inspecting geometry and materials')
        results.append(r)
        write(folder/'checks/native_baked_compare.json',r)
    write(WORK/'native_baked_comparisons.json',results)
    print('COMPARE',len(results))
    for r in sorted(results,key=lambda x:-x.get('mae',1))[:20]:
        print(r['id'],'MAE',round(r.get('mae',1),4),'changed',round(r.get('changed_pixels_gt_32',1),4))


if __name__=='__main__':main()
