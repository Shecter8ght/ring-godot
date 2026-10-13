"""Manufacturer photographs for matching the owner's open reflex sight."""
from pathlib import Path
from urllib.parse import urljoin
import hashlib, json, re
import requests

OUT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement/references/optic_photos'
OUT.mkdir(parents=True,exist_ok=True)
s=requests.Session();s.headers['User-Agent']='Mozilla/5.0'
rows=[]
for name,url,key in [('RG49','https://www.umarexusa.com/axeon-rg49','rg49'),('R47','https://www.umarexusa.com/axeon-r47-multi-reticle-reflex-sight','r47')]:
    r=s.get(url,timeout=30);r.raise_for_status();(OUT/f'umarex_{name}.html').write_text(r.text,encoding='utf-8')
    links=sorted(set(urljoin(url,v) for v in re.findall(r'(?:src|href|data-full-image-url)=[\"\']([^\"\']+\.(?:jpeg|jpg|png))',r.text,re.I) if key in v.lower()))
    for u in links:
        if '_105.' in u:continue
        p=OUT/(name+'_'+u.rsplit('/',1)[-1]);rr=s.get(u,timeout=30)
        if rr.ok:
            p.write_bytes(rr.content);rows.append(dict(page=url,url=u,file=p.name,bytes=len(rr.content),sha256=hashlib.sha256(rr.content).hexdigest()))
url='https://www.pyramydair.com/airgun-resources/manuals/manual-walther-multi-reticle-sight.pdf'
r=s.get(url,timeout=30);r.raise_for_status();(OUT/'Walther_MRS_Umarex_manual.pdf').write_bytes(r.content)
rows.append(dict(url=url,file='Walther_MRS_Umarex_manual.pdf',sha256=hashlib.sha256(r.content).hexdigest()))
(OUT/'manufacturer_manifest.json').write_text(json.dumps(dict(images=rows,license='Manufacturer photographs/manual, reference-only; not CC0 and not used as textures'),ensure_ascii=False,indent=2),encoding='utf-8')
print('OPTIC_MANUFACTURER_REFS',len(rows),json.dumps(rows),flush=True)
