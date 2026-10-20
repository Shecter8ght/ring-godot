"""Получить конкретные CC0-фототекстуры для собственной одежды NPC."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'_asset_src/npc_wardrobe/materials'
ASSETS=['denim_fabric_03','jersey_melange','stretch_poplin','brown_leather','bi_stretch']


def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':'RING local asset authoring / CC0 download'})
    with urllib.request.urlopen(req,timeout=90) as response:
        return response.read()


def fetch(asset):
    folder=DEST/asset
    folder.mkdir(parents=True,exist_ok=True)
    files=json.loads(request('https://api.polyhaven.com/files/'+asset))
    info=json.loads(request('https://api.polyhaven.com/info/'+asset))
    (folder/'files.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
    (folder/'info.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    entries=[]
    aliases={'diff':['diff','Diffuse'],'rough':['rough','Rough'],'nor_gl':['nor_gl'],'disp':['disp','Displacement']}
    for kind,keys in aliases.items():
        actual=next(key for key in keys if key in files)
        formats=files[actual]['2k']
        fmt='jpg' if kind=='diff' and 'jpg' in formats else 'png' if 'png' in formats else 'jpg'
        entry=formats[fmt]
        filename=entry['url'].rsplit('/',1)[-1]
        target=folder/filename
        if not target.exists() or target.stat().st_size!=entry['size']:
            target.write_bytes(request(entry['url']))
        assert target.stat().st_size==entry['size'],target
        entries.append({'kind':kind,'file':str(target),'url':entry['url'],
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    return {'id':asset,'source':'https://polyhaven.com/a/'+asset,'license':'CC0',
        'license_url':'https://polyhaven.com/license','authors':info.get('authors'),
        'dimensions':info.get('dimensions'),'scale':info.get('scale'),'files':entries}


if __name__=='__main__':
    DEST.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(fetch,ASSETS))
    (DEST/'sources.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    (DEST/'license.txt').write_text('Poly Haven textures: CC0 1.0. https://polyhaven.com/license\nOriginal assets and authors are recorded in sources.json; downloads are unmodified.\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','assets':[{k:a[k] for k in ['id','authors','dimensions','scale']} for a in results]},ensure_ascii=False))
