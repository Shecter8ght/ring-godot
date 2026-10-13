"""Freeze approved geometry, inspect mask inputs, and plan bounded PM cleanup."""
from pathlib import Path
import csv,json,hashlib,shutil
from PIL import Image,ImageDraw,ImageOps
PROJECT=Path(__file__).resolve().parents[1]
OUT=PROJECT/'_asset_src/pm_texturing'
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')
MASK=Path('E:/Models Blender/Маски_АЛЬФА')
for name in ('approved','sources/alphas','checks','work','images','textures'):(OUT/name).mkdir(parents=True,exist_ok=True)
inventory=json.loads((OUT/'source_inventory.json').read_text(encoding='utf-8'))
source=Path(inventory['file']);target=OUT/'approved/PM_Geometry_v11_APPROVED.blend'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert digest(source)==inventory['sha256']
if not target.exists():shutil.copy2(source,target)
assert digest(target)==inventory['sha256']
rows=[]
for p in sorted(MASK.rglob('*.png')):
    with Image.open(p) as im:shape=im.size;mode=im.mode
    rows.append(dict(source=str(p),relative=p.relative_to(MASK).as_posix(),sha256=digest(p),size=shape,mode=mode,origin='Owner supplied artistic mask; not measured PBR'))
(OUT/'sources/alpha_manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
# Small contact sheet for internal source selection only; no gallery deliverable.
sheet=Image.new('RGB',(900,180*9),(28,28,28));draw=ImageDraw.Draw(sheet)
for i,row in enumerate(rows):
    with Image.open(row['source']) as im:thumb=ImageOps.contain(im.convert('RGB'),(155,145))
    x=(i%5)*180;y=(i//5)*180;sheet.paste(thumb,(x,y));draw.text((x+3,y+148),str(i)+' '+Path(row['source']).stem[:18],fill='white')
sheet.save(OUT/'work/alpha_selection.png')
reference=PROJECT/'_asset_src/pm_refinement/references'
state=dict(asset='ПМ / КОРС-9 with installed ZORIN K-1',geometry_accepted=True,accepted_on='2026-10-13',acceptance='Owner: всё просто прекрасно; начинаем текстурирование',source=str(source),sha256=inventory['sha256'],frozen_source=str(target),blender=inventory['blender'],ucupaint=inventory['ucupaint'],skill='weapon-asset-texturing',conditions=[100,60,20],geometry_policy='Keep accepted v11 for all texture-only conditions',reference_root=str(reference),alpha_root=str(MASK),stage='Material study before full texture assembly',glass=dict(metallic=0,transmission=1,viewport=inventory['viewports'],diagnosis='Solid viewport hides shader transmission; render test required'),presentation='Working screenshots in chat; final .blend only, no movie/gallery')
if not (OUT/'texture_state.json').exists():
    (OUT/'texture_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
# Only explicitly superseded/unapproved candidates and their working duplicates.
candidates=[p for p in LIB.iterdir() if p.is_dir() and p.name[:3] in ('08_','09_','10_','11_','12_','99_')]
history=LIB/'90_История_и_резервные_копии'
candidates += [history/n for n in ('Магазины_v2','Магазины_v3_резерв','Обзор_v2_резерв','Отдельные_ассеты_v1','Отдельные_ассеты_v2_резерв','Пистолет_до_упаковки_света','Пистолет_предыдущие_версии','Ранее_выданные_архивы') if (history/n).exists()]
work=PROJECT/'_asset_src/pm_refinement'
candidates += [work/n for n in ('review_v06','review_v07','review_v08','review_v09','review_v10') if (work/n).exists()]
plan=[]
for p in candidates:
    files=list(p.rglob('*'));plan.append(dict(path=str(p.resolve()),files=sum(f.is_file() for f in files),bytes=sum(f.stat().st_size for f in files if f.is_file())))
if not (OUT/'checks/cleanup_plan.json').exists():
    (OUT/'checks/cleanup_plan.json').write_text(json.dumps(dict(roots=[str(LIB),str(work)],targets=plan,approved_file=str(source),approved_sha256=inventory['sha256'],authorization='Owner explicitly requested deleting old unapproved iterations on 2026-10-13'),ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_TEXTURE_PREPARED',len(rows),'masks;',len(plan),'old candidate folders;',sum(p['bytes'] for p in plan),'bytes')
for i,r in enumerate(rows):print('ALPHA',i,r['relative'])
