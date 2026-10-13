"""Десять студийных кадров полного разрешения и JPEG-архив для презентации."""
import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image,ImageDraw,ImageFont

OUT=Path(__file__).resolve().parents[1]/'_asset_src/grenade_codex'
SOURCE=OUT/'previews/studio'
TARGET=OUT/'Investor_Shots'
NAMES=['01_hero','02_landscape','03_head_and_mark','04_cast_detail','05_sun_slnshk',
       '06_reverse_portrait','07_low_angle','08_split_pin_detail','09_visual_motion','10_opposite_profile']


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    renders=json.loads((OUT/'checks/studio_renders_v06.json').read_text(encoding='utf8'))
    assert {row['file'] for row in renders}=={name+'.png' for name in NAMES}
    assert all(row['samples']==512 for row in renders),'Final studio quality is required'
    render_by_name={row['file']:row for row in renders}
    rows=[]
    sheet=Image.new('RGB',(1800,1320),(20,24,29))
    draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',24)
    for i,name in enumerate(NAMES):
        path=SOURCE/(name+'.png')
        assert sha(path)==render_by_name[path.name]['sha256'],path
        with Image.open(path) as raw:
            image=raw.convert('RGB')
        assert min(image.size)>=2160 and max(image.size)>=3200,path
        dest=TARGET/(name+'.jpg')
        image.save(dest,quality=97,subsampling=0,optimize=True)
        with Image.open(dest) as check:assert check.size==image.size
        rows.append({'index':i+1,'jpeg':dest.name,'source_png':path.name,'size':list(image.size),
                     'jpeg_sha256':sha(dest),'png_sha256':sha(path),'quality':97,'chroma_subsampling':0})
        thumb=image.copy()
        thumb.thumbnail((340,575),Image.Resampling.LANCZOS)
        x=(i%5)*360;y=(i//5)*660
        sheet.paste(thumb,(x+(360-thumb.width)//2,y+(600-thumb.height)//2+20))
        draw.text((x+20,y+620),f'{i+1:02d}',fill=(231,233,237),font=font)
    assert len({r['png_sha256'] for r in rows})==10,'Repeated source image'
    sheet.save(OUT/'Investor_Contact_Sheet_v06.jpg',quality=95,subsampling=0)
    note='Граната — 10 кадров для инвесторов. JPEG 97%, без уменьшения разрешения.\nИсходные PNG 16 bit: previews/studio.\nКадры от 3200 до 4000 px; сцена: Grenade_MkII_Studio_v06.blend.\nГеометрия v05 принята владельцем; текстуры v06 подготовлены к просмотру.\n'
    (TARGET/'README.txt').write_text(note,encoding='utf8')
    archive=OUT/'Grenade_Investor_10_Shots_v06.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in rows:z.write(TARGET/row['jpeg'],'Investor_Shots/'+row['jpeg'])
        z.write(TARGET/'README.txt','Investor_Shots/README.txt')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.endswith('.jpg')])==10
    report={'images':rows,'count':10,'render_samples':512,'zip_sha256':sha(archive),'zip_bytes':archive.stat().st_size}
    (OUT/'checks/investor_screens_v06.json').write_text(json.dumps(report,indent=2))
    print('INVESTOR_PACKAGE_OK',len(rows),archive,flush=True)


if __name__=='__main__':main()
