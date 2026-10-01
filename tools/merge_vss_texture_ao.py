"""Добавить локальный AO в исходный ORM-слой; затем повторить композит Krita."""
from pathlib import Path
import argparse,json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]/'_asset_src/vss_textured'
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--id');args=parser.parse_args()
    source=ROOT/args.id if args.id else ROOT
    for path in source.rglob('cavity_ao.png'):
        folder=path.parent;orm_path=folder/'ORM_-_AO_roughness_metallic.png'
        orm=np.array(Image.open(orm_path).convert('RGBA'));ao=np.array(Image.open(path).convert('RGB'))[:,:,0]
        valid=(orm[:,:,3]>0)&(ao>0);orm[valid,0]=np.maximum(ao[valid],82)
        Image.fromarray(orm).save(orm_path)
        meta=json.loads((folder/'layers.json').read_text());meta['orm']='R=local cavity AO (3mm/6mm), G=roughness, B=metallic'
        (folder/'layers.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
        print('AO_LAYER_UPDATED',folder,flush=True)
if __name__=='__main__':main()
