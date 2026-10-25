"""Preserve the exact literal source ink on tiny raised glyphs, independent of UV."""
from pathlib import Path
import sys
import json
import argparse
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,MODEL,rows,sha,write
import bake as K


def main():
    p=argparse.ArgumentParser();p.add_argument('--exclude',default='')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    excluded=set(args.exclude.split(','))
    for a in rows():
        if a['id'] in excluded:continue
        model=WORK/a['retopo_model']; folder=model.parent.parent
        proof=folder/'checks/bake.json'
        if not proof.exists():continue
        data=json.loads(proof.read_text(encoding='utf-8'))
        if not data['passed'] or sha(model)!=data['model_sha256']:continue
        bpy.ops.wm.open_mainfile(filepath=str(model))
        changed=[]
        for mat in {m for ob in bpy.data.collections[MODEL].objects if ob.type=='MESH' for m in ob.data.materials}:
            if mat.get('constant_source_ink'):continue
            if K.constant_ink(mat):changed.append(mat.name)
        if not changed:continue
        bpy.context.preferences.filepaths.save_version=0
        bpy.ops.wm.save_as_mainfile(filepath=str(model),compress=True,relative_remap=False)
        digest=sha(model)
        for filename in ('retopology.json','bake.json'):
            file=folder/'checks'/filename
            result=json.loads(file.read_text(encoding='utf-8'))
            result['model_sha256']=digest; result['constant_ink_materials']=changed
            write(file,result)
        print('LETTERING',a['id'],len(changed),flush=True)
    print('LETTERING_COMPLETE',flush=True)


if __name__=='__main__':main()
