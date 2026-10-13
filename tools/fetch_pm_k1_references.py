"""Archive the owner's new K-1 sight views and the maker's scale reference."""
from pathlib import Path
import hashlib, json, shutil
import requests

ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement/references/k1'
ROOT.mkdir(parents=True,exist_ok=True)
SOURCE=Path('C:/Users/Schecter_8ght/.codex/codex-remote-attachments/01a131a7-fff9-7651-9b58-f7343c0f1b13/AEA65D4C-53F4-4A03-BCFC-4C62869E0D5E')
rows=[]
for i in range(1,11):
    src=SOURCE/f'{i}-Фото-{i}.jpg';dst=ROOT/f'owner_k1_{i:02d}.jpg'
    shutil.copy2(src,dst)
    rows.append(dict(file=dst.name,origin='Owner supplied reference',sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
session=requests.Session();session.headers['User-Agent']='Mozilla/5.0'
for name,url in [('Leupold_DeltaPoint_Pro.html','https://www.leupold.com/deltapoint-pro-red-dot'),('Leupold_DeltaPoint_Pro_manual.pdf','https://www.leupold.com/media/manuals/deltapoint-pro-manual.pdf')]:
    r=session.get(url,timeout=30);r.raise_for_status();(ROOT/name).write_bytes(r.content)
    rows.append(dict(file=name,url=url,sha256=hashlib.sha256(r.content).hexdigest()))
(ROOT/'sources.json').write_text(json.dumps(dict(files=rows,usage='Reference only; owner screenshots and manufacturer manual are not texture sources',measured_source='Manual: body 46.1 x 33.2 x 33.0 mm; window 25.7 x 17.5 mm'),ensure_ascii=False,indent=2),encoding='utf-8')
print('K1_REFERENCES_SAVED',len(rows),flush=True)
