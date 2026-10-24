"""Фотографии прототипов: только локальные визуальные референсы, не текстуры."""
from pathlib import Path
import argparse
from urllib.parse import urljoin,urlsplit
import hashlib
import json
import requests
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[3]/'_asset_src/urban_realrefs_v02'
PAGES={
 'fence':'https://zaogbi.ru/catalog/po-2/plity-zabora-po-2/',
 'dumpster':'https://rostmetall.ru/blagoustrojstvo-goroda/bunkery-nakopiteli/bn-8-m3.html',
 'atm':'https://ncr.co.il/ncr-selfserv_22e/',
 'car_official':'https://www.volkswagen-newsroom.com/en/golf-5-20032008-19480',
 'car_front':'https://commons.wikimedia.org/wiki/File:VW_Golf_V_20090809_front.JPG',
 'car_rear':'https://commons.wikimedia.org/wiki/File:VW_Golf_V_20090809_rear.JPG',
}
SESSION=requests.Session()
SESSION.headers['User-Agent']='Mozilla/5.0 (compatible; RING asset reference research)'


def inventory(key,url):
    folder=ROOT/'references'/key
    folder.mkdir(parents=True,exist_ok=True)
    response=SESSION.get(url,timeout=40); response.raise_for_status()
    (folder/'source.html').write_text(response.text,encoding='utf-8')
    soup=BeautifulSoup(response.text,'html.parser')
    rows=[]; seen=set()
    for tag in soup.find_all(['img','a','source','meta']):
        for attr in ('href','src','data-src','data-large_image','data-full','content','srcset'):
            value=tag.get(attr,'')
            if not value: continue
            if attr=='content' and tag.get('property') not in ('og:image','twitter:image'): continue
            if attr=='srcset': value=value.split(',')[-1].strip().split(' ')[0]
            candidate=urljoin(url,value)
            if not any(s in urlsplit(candidate).path.lower() for s in ('.jpg','.jpeg','.png','.webp','.pdf')): continue
            if candidate in seen: continue
            seen.add(candidate)
            rows.append(dict(url=candidate,alt=tag.get('alt',tag.get('title','')),tag=tag.name))
    (folder/'inventory.json').write_text(json.dumps(dict(page=url,images=rows),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(key=key,page=url,images=rows),ensure_ascii=False),flush=True)


def download(key,url,name,page,notes):
    folder=ROOT/'references'/key; folder.mkdir(parents=True,exist_ok=True)
    response=SESSION.get(url,timeout=60); response.raise_for_status()
    path=folder/name; path.write_bytes(response.content)
    record=dict(file=name,url=url,source_page=page,sha256=hashlib.sha256(response.content).hexdigest(),
       downloaded='2026-10-24',purpose='Visual modelling reference only; never a game texture',notes=notes)
    (folder/(name+'.source.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SAVED',path,len(response.content),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--inventory',nargs='*')
    parser.add_argument('--download',nargs=5,metavar=('KEY','URL','NAME','PAGE','NOTES'))
    parser.add_argument('--page',nargs=2)
    parser.add_argument('--selected',action='store_true')
    a=parser.parse_args()
    if a.inventory:
        for key in a.inventory:
            try: inventory(key,PAGES[key])
            except Exception as error: print('FETCH_ERROR',key,type(error).__name__,str(error),flush=True)
    if a.page: inventory(*a.page)
    if a.download: download(*a.download)
    if a.selected:
        jobs=[]
        for key in ('fence','dumpster','atm','car_front','car_rear','car_official','kiosk'):
            inv=json.loads((ROOT/'references'/key/'inventory.json').read_text(encoding='utf-8'))
            rows=inv['images']
            if key=='fence': selected=[r['url'] for r in rows if '/iblock/' in r['url']]
            elif key=='dumpster': selected=[r['url'] for r in rows if '/image/data/' in r['url'] and '1408' in r['url']][:8]
            elif key=='atm': selected=[rows[0]['url']]+[r['url'] for r in rows if r['url'].endswith('.pdf')]
            elif key in ('car_front','car_rear'):
                selected=[r['url'].split('?')[0] for r in rows if r['url'].startswith('https://upload.wikimedia.org/') and '/thumb/' not in r['url']][:1]
            elif key=='car_official': selected=list(dict.fromkeys(r['url'] for r in rows if 'B2025NR' in r['url'] and '_1600.' in r['url']))[:8]
            else: selected=[r['url'].replace('_w159_h159','_w1600_h1600') for r in rows if 'kiosk-na-zamovlennya' in r['url'] and r['tag']=='img'][:8]
            for i,url in enumerate(selected,1):
                ext=Path(urlsplit(url).path).suffix.lower()
                jobs.append((key,url,f'ref_{i:02d}{ext}',inv['page'],
                  'Manufacturer or named photographer image. Research reference, not a texture; rights retained by source.'))
        def safe(job):
            try: download(*job)
            except Exception as error: print('DOWNLOAD_ERROR',job[0],job[1],str(error),flush=True)
        with ThreadPoolExecutor(max_workers=5) as pool: list(pool.map(safe,jobs))
