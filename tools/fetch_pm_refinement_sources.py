"""Archive owner's visual references and CC0 surface sources; no painting."""
from pathlib import Path
import hashlib, json, shutil, urllib.request, zipfile

ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement'
REF=ROOT/'references'; REF.mkdir(parents=True,exist_ok=True)
ids=['f2a931c1-3289-4d95-a2d3-a56694a6efea','53a5445d-37fb-4679-9e26-98b2d6bf236f','10ce5ae4-4e2a-428b-add4-98abee190865','9fa6629d-66fb-4be2-bd47-5e3e5fe58761','4a9ef4ee-5a11-47e8-9c77-18ad365e5fbf','0d0ccbaa-8227-4ca2-ae31-cfb1db519f13','ee6f0e44-45ce-4d7a-a1b9-9fdc4a6f21ca','dc7ae67f-f89f-4aa9-be96-1086182a0649','c4c5b600-0cf8-4ff3-855e-4798728b7656','983d91f6-c8d9-43fd-9602-c601899421ca','4e8195ae-5611-49ac-989f-db369a9a96b8','133453ec-60dc-4977-9aba-a20525c02120','ed242839-2d98-4147-a178-ac3dfe56d6cc','a4caddd6-0756-4792-abb5-112cb3e45768','abb863a2-35cc-40e4-ac05-6a241397406d']
for i,uid in enumerate(ids,1):
    p=Path('C:/Users/SCHECT~1/AppData/Local/Temp')/f'codex-clipboard-{uid}.png'
    if p.is_file():shutil.copy2(p,REF/f'owner_{i:02d}.png')
for i,uid in enumerate(['ddbc2487-23f7-4d5b-8a22-e52929c55bc3','e964562f-d444-4fa9-936f-54d933ac709b','ca07739a-223e-4d04-98c7-778f56377f68'],16):
    p=Path('C:/Users/SCHECT~1/AppData/Local/Temp')/f'codex-clipboard-{uid}.png'
    if p.is_file():shutil.copy2(p,REF/f'owner_{i:02d}.png')

sources=[]
def fetch(url,path):
    if path.exists() and path.stat().st_size>1000:return
    req=urllib.request.Request(url,headers={'User-Agent':'RING-asset-reference/1.0'})
    with urllib.request.urlopen(req,timeout=100) as response, path.open('wb') as out:shutil.copyfileobj(response,out)

for asset,res in [('Smear002','8K-JPG'),('Scratches004','4K-PNG')]:
    dest=ROOT/'surface_sources'/asset; dest.mkdir(parents=True,exist_ok=True)
    page=f'https://ambientcg.com/view?id={asset}'
    url=f'https://ambientcg.com/get?file={asset}_{res}.zip'
    try:
        fetch(page,dest/'source_page.html')
        fetch('https://docs.ambientcg.com/license/',dest/'license_page.html')
        archive=dest/f'{asset}_{res}.zip'; fetch(url,archive)
        with zipfile.ZipFile(archive) as pack:
            for item in pack.infolist():
                target=(dest/item.filename).resolve()
                if not target.is_relative_to(dest.resolve()):raise ValueError('Archive path escapes asset directory')
            pack.extractall(dest)
        row=dict(asset=asset,source=page,download=url,license='CC0 1.0',source_resolution=res,
            files=[dict(name=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in dest.iterdir() if p.is_file()])
        sources.append(row);print('SOURCE_SAVED',asset,res,len(row['files']),flush=True)
    except Exception as exc:
        sources.append(dict(asset=asset,source=page,error=str(exc)));print('SOURCE_ERROR',asset,str(exc),flush=True)
(ROOT/'surface_sources/manifest.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
(REF/'sources.md').write_text('# Источники\n\n18 изображений владельца от 2026-10-12 — визуальные референсы. Не используются для извлечения чужих текстур.\n\nSketchfab: https://sketchfab.com/3d-models/makarov-73624f76346d49d8a5fa9829b44092b3 — ссылка владельца, веб-инструмент не смог открыть просмотр. Модель не скачивалась.\n\nФото Bruno Ardovini: https://www.all4shooters.com/en/shooting/pistols/makarov-pm-9x18mm-semi-automatic-pistol-technical-analysis/ — уточнение принадлежности нижней защёлки.\n\nambientCG Smear002 (8K JPG), Scratches004 (4K PNG) — CC0; только архив сырья до принятия геометрии. 4K не выдаётся за настоящую 8K.\n',encoding='utf-8')
