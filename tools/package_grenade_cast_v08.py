"""Проверка карт, десять JPEG для инвесторов и выдача без перезаписи старых версий."""
import hashlib,json,shutil,sys,zipfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex/texture_v08'
LIB=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v08')
NAMES=['01_hero','02_landscape','03_head_and_mark','04_cast_detail','05_sun_slnshk','06_reverse_portrait','07_low_angle','08_split_pin_detail','09_visual_motion','10_opposite_profile']
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def validate_maps():
    rows=json.loads((OUT/'checks/image_manifest.json').read_text(encoding='utf8'))
    for r in rows:
        path=OUT/r['file'][2:];assert path.is_file() and sha(path)==r['sha256'],path
    for mapname in ['casting_relief_8k_16bit.png','deposit_grains_8k.png','contact_breaks_8k.png']:
        path=OUT/'textures/authoring'/mapname
        with Image.open(path) as im:assert im.size==(8192,8192)
    assert (OUT/'textures/authoring/casting_relief_8k_16bit.png').read_bytes()[24]==16
    print('MAPS_CHECKED',len(rows),flush=True)
def previews():
    for f in (OUT/'previews').rglob('*.png'):
        with Image.open(f) as im:
            image=im.convert('RGB');image.thumbnail((1280,1600),Image.Resampling.LANCZOS);image.save(f.with_suffix('.jpg'),quality=95,subsampling=0)
def investor():
    rows=json.loads((OUT/'checks/studio_renders_v08.json').read_text(encoding='utf8'))
    assert {r['file'] for r in rows}=={n+'.png' for n in NAMES} and all(r['samples']==512 for r in rows)
    target=OUT/'Investor_Shots';target.mkdir(exist_ok=True)
    sheet=Image.new('RGB',(1800,1320),(18,22,27));draw=ImageDraw.Draw(sheet);font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',24)
    result=[]
    for i,n in enumerate(NAMES):
        path=OUT/'previews/studio'/(n+'.png');r=next(r for r in rows if r['file']==path.name);assert sha(path)==r['sha256']
        with Image.open(path) as im:image=im.convert('RGB');assert list(image.size)==r['size']
        dest=target/(n+'.jpg');image.save(dest,quality=97,subsampling=0,optimize=True)
        result.append({'name':n,'size':r['size'],'png_sha256':r['sha256'],'jpeg_sha256':sha(dest)})
        image.thumbnail((340,575),Image.Resampling.LANCZOS);x=(i%5)*360;y=(i//5)*660;sheet.paste(image,(x+(360-image.width)//2,y+(600-image.height)//2+20));draw.text((x+20,y+620),f'{i+1:02}',fill=(231,233,237),font=font)
    assert len({r['png_sha256'] for r in result})==10
    sheet.save(OUT/'Investor_Contact_Sheet_v08.jpg',quality=95,subsampling=0)
    (target/'README.txt').write_text('Граната: 10 кадров для инвесторов, JPEG 97%, полное разрешение. Геометрия v07 принята, текстуры v08 подготовлены к просмотру. PNG16 и редактируемая студия сохранены рядом.\n',encoding='utf8')
    archive=OUT/'Grenade_Investor_10_Shots_v08.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(target.iterdir()):z.write(f,'Investor_Shots/'+f.name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    (OUT/'checks/investor_v08.json').write_text(json.dumps({'count':10,'images':result,'archive_sha256':sha(archive)},indent=2),encoding='utf8')
    print('INVESTOR_10_READY',archive,flush=True)
def supporting():
    resources=OUT/'resources';resources.mkdir(exist_ok=True)
    for asset in ['Metal009','Metal049C','Metal063']:
        for name in ['provenance.json','metadata.json']:
            shutil.copy2(ROOT/'_asset_src/grenade_codex/textures/cc0_sources'/asset/name,resources/(asset+'_'+name))
    shutil.copy2(ROOT/'_asset_src/grenade_codex/textures/cc0_sources/ambientCG_license.html',resources/'ambientCG_license.html')
    (resources/'LICENSES.md').write_text('Sources: https://ambientcg.com/view?id=Metal049C ; https://ambientcg.com/view?id=Metal009 ; https://ambientcg.com/view?id=Metal063 . CC0 1.0: https://docs.ambientcg.com/license/ . Original source hashes/techniques recorded in the provenance files. Casting/deposit/contact masks and sun + СЛНШК are original project work. Scenario geometry and owner photographs retain their original rights. Photographs are visual references only and were not sampled for maps.\n',encoding='utf8')
    source=OUT/'source';source.mkdir(exist_ok=True)
    for name in ['grenade_cast_maps_v08.py','texture_grenade_cast_v08.py','check_grenade_cast_v08.py','studio_grenade_cast_v08.py','package_grenade_cast_v08.py','texture_grenade_codex.py','texture_flare_pistol_codex.py','grenade_codex_blender.py','round_grenade_codex_body.py','studio_grenade_codex.py','open_grenade_cast_v08.py','finish_grenade_cast_v08.cmd','finish_grenade_cast_v08.ps1']:
        shutil.copy2(ROOT/'tools'/name,source/name)
    shutil.copy2(Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts/ucupaint_helpers.py'),source/'ucupaint_helpers.py')
    refs=OUT/'references';refs.mkdir(exist_ok=True)
    path=Path('C:/Users/Schecter_8ght/.codex/codex-remote-attachments/01a13159-559d-7862-ae98-fbaf3bb01041/FB3DD496-4BD7-4378-BCAD-FF98747A64BA/1-Фото-1.jpg');shutil.copy2(path,refs/'owner_cast_closeup.jpg')
    images=['previews/'+x+'.jpg' for x in ['01_cast_raking','02_cast_reverse_raking','03_metal_and_band','04_overall']]+['previews/studio/'+n+'.jpg' for n in NAMES]
    css='body{background:#12161b;color:#ececec;font:18px system-ui;margin:30px} main{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:20px}img{width:100%;height:600px;object-fit:contain;background:#0b0d11}a{color:#dfbd74}h1{font-size:28px}'
    html='<!doctype html><meta charset="utf-8"><title>Граната v08 — просмотр</title><style>'+css+'</style><h1>Граната · текстуры v08</h1><p>Геометрия v07 принята владельцем. Текстуры подготовлены к просмотру. Наплывы литья, вытертое покрытие, следы контакта, пыль и отдельные частицы грязи.</p><p><a href="Grenade_MkII_UCUPaint_v08.blend">Редактируемый UCUPaint</a> · <a href="Grenade_MkII_Studio_v08.blend">Предметная студия</a> · <a href="Grenade_Investor_10_Shots_v08.zip">10 кадров для инвесторов</a></p><main>'+''.join('<a href="'+s.replace('.jpg','.png')+'"><img src="'+s+'"></a>' for s in images)+'</main>'
    (OUT/'gallery.html').write_text(html,encoding='utf8')
def copy():
    assert not LIB.exists(),'Existing delivery must not be overwritten'
    audit=json.loads((OUT/'checks/material_audit.json').read_text(encoding='utf8'));assert audit['pass'] and audit['sha256']==sha(OUT/'Grenade_MkII_UCUPaint_v08.blend')
    shutil.copytree(OUT,LIB,ignore=shutil.ignore_patterns('*.log','*.blend1','material_pilot_v08.blend','studio_pilot_*'))
    for f in OUT.rglob('*'):
        rel=f.relative_to(OUT)
        if f.is_file() and (LIB/rel).is_file():assert sha(f)==sha(LIB/rel),rel
    print('V08_LIBRARY_COPIED',LIB,flush=True)
def seal():
    audit=json.loads((OUT/'checks/delivered_audit.json').read_text(encoding='utf8'));assert audit['pass'] and Path(audit['file'])==LIB/'Grenade_MkII_UCUPaint_v08.blend'
    shutil.copy2(OUT/'checks/delivered_audit.json',LIB/'checks/delivered_audit.json')
    studio=json.loads((OUT/'checks/delivered_studio_audit.json').read_text(encoding='utf8'));assert studio['pass'] and Path(studio['file'])==LIB/'Grenade_MkII_Studio_v08.blend';shutil.copy2(OUT/'checks/delivered_studio_audit.json',LIB/'checks/delivered_studio_audit.json')
    rows=[{'file':f.relative_to(LIB).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)} for f in sorted(LIB.rglob('*')) if f.is_file() and f.name!='file_manifest.json']
    (LIB/'file_manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    print('V08_SEALED',len(rows),flush=True)
if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'maps'
    {'maps':validate_maps,'previews':previews,'investor':investor,'supporting':supporting,'copy':copy,'seal':seal}[mode]()

