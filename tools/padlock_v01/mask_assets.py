"""Авторские контактные поля на основе альфа-масок владельца, без карт референсной модели."""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/"_asset_src"/"padlock_v01"/"textures"
SOURCES=WORK/"sources"
OWNER=Path('E:/Models Blender/Маски_АЛЬФА')
SOURCES.mkdir(parents=True,exist_ok=True)
files={
 'chips':OWNER/'10_Сколы_и_потёртости_покрытия'/'Сколы_пятнами_01.png',
 'chips_second':OWNER/'10_Сколы_и_потёртости_покрытия'/'Сколы_с_потёртостями_01.png',
 'pitting':OWNER/'12_Пористая_коррозия'/'Коррозия_03_Смешанные_раковины.png',
 'fine_pitting':OWNER/'12_Пористая_коррозия'/'Коррозия_10_Слабый_питтинг.png',
}
manifest=[]
for key,source in files.items():
    destination=SOURCES/(key+'.png');shutil.copyfile(source,destination)
    manifest.append({'source':str(source),'copy':destination.name,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
                     'rights':'Owner-provided alpha library; not asserted CC0; used as masks, not as third-party model textures.'})
size=2048
def load(name):return np.asarray(Image.open(SOURCES/(name+'.png')).convert('L').resize((size,size),Image.Resampling.LANCZOS),dtype=np.float32)/255
raw=load('chips');raw2=np.fliplr(np.roll(raw,(size//3,size//5),(0,1)))
v,u=np.mgrid[0:1:complex(size),0:1:complex(size)]
front_score=raw+.28*np.exp(-((u-.28)/.46)**2-((v-.23)/.45)**2)-.32*v-.15*u
back_score=1-raw2+.15*np.exp(-((u-.30)/.65)**2-((v-.40)/.70)**2)-.10*u
def mask(score,fraction):
    threshold=float(np.quantile(score,1-fraction))
    t=np.clip((score-threshold)/.025+.5,0,1)
    return t*t*(3-2*t)
front=mask(front_score,.28)*np.clip((raw-.025)/.035,0,1);back=mask(back_score,.56)
band=mask(1-np.rot90(raw)+.08*np.sin(u*2.4),.60)
for name,array in (('paint_front',front),('paint_rear',back),('paint_band',band)):
    Image.fromarray(np.round(array*65535).astype(np.uint16)).save(SOURCES/(name+'.png'))
    print(name,'coverage',round(float(array.mean()),4))
    if name=='paint_front':print('front top/bottom',float(array[:size//2].mean()),float(array[size//2:].mean()))
# The reference stamp is illegible. Keep a small, deliberately non-verbal worn
# factory mark rather than inventing readable branding or copying source pixels.
stamp_image=Image.new('L',(size,size),0);draw=ImageDraw.Draw(stamp_image)
def pts(points):return [(round(x*size),round(y*size)) for x,y in points]
draw.line(pts([(.470,.369),(.470,.342),(.493,.322),(.526,.325),(.546,.345),(.546,.374),(.470,.374)]),fill=255,width=6)
draw.line(pts([(.483,.352),(.531,.352)]),fill=255,width=8)
draw.line(pts([(.483,.363),(.531,.363)]),fill=255,width=7)
for index,x in enumerate(np.linspace(.454,.558,9)):
    draw.rectangle((round(x*size),round(.395*size),round((x+.004)*size),round((.431-(index%3)*.004)*size)),fill=255)
stamp=np.asarray(stamp_image,dtype=np.float32)/255
stamp*=np.clip(.90-.55*np.roll(load('fine_pitting'),(217,643),(0,1)),0,1)
Image.fromarray(np.round(stamp*65535).astype(np.uint16)).save(SOURCES/'stamp_front.png')
(SOURCES/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
