"""PBR и графика убежища. Только production authoring; игра этот файл не вызывает."""
from __future__ import annotations
import json, math, urllib.request, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/shelter/textures'
SRC = ROOT / '_asset_src/shelter'
UA = {'User-Agent': 'RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)'}
NEW = ['brown_leather', 'dirty_carpet', 'denim_fabric_06', 'rusty_metal_sheet', 'oak_wood_planks', 'rubber_tiles']

def fetch():
    catalog = json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/assets?t=textures', headers=UA)))
    credits = []
    for key in NEW:
        dest = SRC / 'textures' / key
        dest.mkdir(parents=True, exist_ok=True)
        spec = json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/' + key, headers=UA)))
        for mapkey, filename in [('Diffuse', 'albedo'), ('nor_gl', 'normal'), ('arm', 'arm')]:
            variants = spec.get(mapkey, {}).get('1k', {})
            variant = variants.get('jpg') or variants.get('png')
            if not variant:
                raise RuntimeError(f'{key}: отсутствует {mapkey}')
            target = dest / (filename + '.jpg')
            if not target.exists():
                data = urllib.request.urlopen(urllib.request.Request(variant['url'], headers=UA), timeout=60).read()
                target.write_bytes(data)
        info = catalog[key]
        record = {'name': info['name'], 'id': key, 'author': ', '.join(info['authors']), 'url': 'https://polyhaven.com/a/' + key, 'license': 'CC0 1.0', 'download_date': '2026-10-05'}
        credits.append(record)
        (dest/'license.txt').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Fetched', key, flush=True)
    (SRC/'sources.json').write_text(json.dumps(credits, ensure_ascii=False, indent=2), encoding='utf-8')

# Общие материалы: tint не заменяет фототекстуру; ORM остаётся отдельной картой.
SPECS = {
    'RawConcrete': ('concrete_wall_006', (0.84,0.82,0.76), .86, 0, 3),
    'PaintedConcrete': ('painted_plaster_wall', (.38,.46,.42), .70, 0, 3),
    'DampConcrete': ('concrete_wall_006', (.55,.57,.51), .78, 0, 3),
    'WetConcrete': ('concrete_floor_worn_001', (.68,.68,.63), .52, 0, 3),
    'IndustrialConcreteFloor': ('concrete_floor_worn_001', (.88,.87,.8), .91, 0, 4),
    'PaintedSteel': ('green_metal_rust', (.55,.62,.57), .69, 0, 1),
    'OchreSteel': ('green_metal_rust', (1.15,.87,.40), .67, 0, 1),
    'BareSteel': ('metal_plate', (.64,.69,.7), .52, .95, 1),
    'RustedSteel': ('rusty_metal_sheet', (.85,.67,.49), .87, 0, 1),
    'GalvanizedSteel': ('metal_plate', (.92,.99,1), .53, .90, 1),
    'DirtyAluminum': ('metal_plate', (.74,.79,.8), .59, .88, 1),
    'OldWood': ('oak_wood_planks', (.65,.54,.40), .68, 0, 2),
    'RawWood': ('oak_wood_planks', (.95,.84,.67), .80, 0, 2),
    'Rubber': ('rubber_tiles', (.35,.36,.35), .84, 0, .7),
    'OldPlastic': ('rubber_tiles', (.58,.56,.50), .60, 0, 1),
    'Canvas': ('denim_fabric_06', (.58,.53,.36), .90, 0, .7),
    'MilitaryFabric': ('denim_fabric_06', (.37,.46,.32), .89, 0, .7),
    'Leatherette': ('brown_leather', (.73,.50,.34), .61, 0, 1),
    'Glass': ('metal_plate', (.20,.25,.21), .12, .05, 1),
    'Oil': ('concrete_floor_worn_001', (.09,.10,.08), .16, .1, 1),
    'PuddleWater': ('concrete_floor_worn_001', (.56,.61,.58), .07, .05, 1),
    'WornCarpet': ('dirty_carpet', (.88,.52,.35), .98, 0, 2),
    'Paper': ('painted_plaster_wall', (1,.98,.82), .91, 0, 1),
    'Cardboard': ('oak_wood_planks', (.8,.68,.45), .95, 0, 1),
    'RedPaint': ('green_metal_rust', (1.25,.28,.13), .69, 0, 1),
}

def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', size)

ROOM_SIGNS = ['ТОРГОВЛЯ', 'ОРУЖЕЙНАЯ', 'КОМНАТА ОТДЫХА', 'МАСТЕРСКАЯ', 'СКЛАД',
              'ДГУ / ЭЛЕКТРОЩИТОВАЯ', 'ТАМБУР / ВОЗВРАЩЕНИЕ', 'СПАЛЬНЫЕ МЕСТА',
              'ВЕНТИЛЯЦИЯ', 'РЕЗЕРВНЫЙ СКЛАД', 'БОКС 1', 'БОКС 2', 'БОКС 3',
              'КОТЕЛЬНЫЙ ЗАЛ / ТИР', 'ОГНЕВОЙ РУБЕЖ', 'ОСТОРОЖНО: СТРЕЛЬБА']

def room_signs():
    # Печатная эмаль на стальной основе: один атлас на все реальные mesh-таблички.
    rng = np.random.default_rng(842)
    noise = rng.normal(0, 1.4, (2048,2048,1))
    rgb = np.clip(np.array([29,38,39])[None,None,:]+noise,0,255).astype('uint8')
    im = Image.fromarray(rgb); d = ImageDraw.Draw(im)
    for i, text in enumerate(ROOM_SIGNS):
        x,y = (i%2)*1024,(i//2)*256
        d.rounded_rectangle((x+12,y+12,x+1011,y+243),radius=8,outline=(145,151,141),width=4)
        size=94
        while d.textbbox((0,0),text,font=font(size))[2]>920:size-=2
        f=font(size); bounds=d.textbbox((0,0),text,font=f)
        d.text((x+(1024-bounds[2])/2,y+(256-(bounds[3]-bounds[1]))/2-bounds[1]),text,font=f,fill=(224,224,210))
    im.save(OUT/'RoomSigns_base.png')
    Image.new('RGB',im.size,(255,195,0)).save(OUT/'RoomSigns_orm.png')
    Image.new('RGB',im.size,(128,128,255)).save(OUT/'RoomSigns_normal.png')

# Цельные материалы с фотографическим микрорельефом: цвет по маске яркости фото, а не тинт.
SOLID = {'OchreSteel': [151,116,48], 'RedPaint': [117,42,27]}

def make_material(name):
    key,tint,rough,metal,tile = SPECS[name]
    source = SRC/'textures'/key if key in NEW else ROOT/'assets/textures'/key
    rgb = np.asarray(Image.open(source/'albedo.jpg').convert('RGB').resize((1024,1024)), dtype=np.float32)
    # Лёгкое изменение roughness сохраняет фотографический рисунок.
    if name in SOLID:
        lum = rgb.mean(axis=2)/255
        rgb = np.array(SOLID[name])[None,None,:] * (.7 + lum[:,:,None]*.6)
    else:
        rgb *= np.array(tint)[None,None,:]
    Image.fromarray(np.clip(rgb,0,255).astype('uint8')).save(OUT/(name+'_base.jpg'), quality=91)
    Image.open(source/'normal.jpg').resize((1024,1024)).save(OUT/(name+'_normal.jpg'), quality=93)
    arm = np.asarray(Image.open(source/'arm.jpg').convert('RGB').resize((1024,1024))).copy()
    original_rough = arm[:,:,1].astype(float)/255
    arm[:,:,1] = np.clip((rough + (original_rough-.5)*.15)*255,0,255).astype('uint8')
    arm[:,:,2] = int(metal*255)
    Image.fromarray(arm).save(OUT/(name+'_orm.jpg'), quality=94)

def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in SPECS:
        make_material(name)
    # Собственный промышленный trim: 8 горизонтальных полос, единый атлас 1024.
    im = Image.new('RGB',(1024,1024),(45,49,46)); draw=ImageDraw.Draw(im)
    for i in range(8):
        col=[(68,76,73),(101,61,40),(79,89,72),(124,120,110),(171,132,49),(64,68,67),(142,145,141),(81,91,89)][i]
        draw.rectangle((0,i*128,1024,i*128+126),fill=col)
        draw.line((0,i*128+5,1024,i*128+5),fill=(180,174,145),width=3)
    for x in range(-128,1152,128):
        draw.polygon([(x,512),(x+64,512),(x-64,638),(x-128,638)],fill=(28,30,28))
    im.save(OUT/'IndustrialTrim_base.png')
    Image.new('RGB',(1024,1024),(255,135,190)).save(OUT/'IndustrialTrim_orm.png')
    Image.new('RGB',(1024,1024),(128,128,255)).save(OUT/'IndustrialTrim_normal.png')
    # План ТЦ — данные реального уровня, без выдуманной новой карты или сюжета.
    im=Image.new('RGB',(1024,512),(187,178,143)); d=ImageDraw.Draw(im)
    d.text((25,20),'RING / ПЛАН ОБЪЕКТА / 1F',font=font(27),fill=(38,45,39))
    center=(375,274)
    for r in [180,160,112,94,58,43]:
        d.ellipse((center[0]-r,center[1]-r,center[0]+r,center[1]+r),outline=(54,61,48),width=3)
    for a in range(0,360,60):
        c,s=math.cos(math.radians(a)),math.sin(math.radians(a))
        d.line((375+43*c,274+43*s,375+180*c,274+180*s),fill=(64,67,53),width=3)
    d.line((375,94,375,228),fill=(137,54,37),width=7)
    d.text((600,105),'МАРШРУТ / ЭТАЖ',font=font(22),fill=(45,52,44))
    for i,tx in enumerate(['01  Проверить снаряжение','02  Разгрузить рюкзак','03  Выбрать маршрут','СЕВЕР ↑','МАСШТАБ 1 : 1250']):
        d.text((600,156+i*48),tx,font=font(16),fill=(57,61,49))
    im.save(OUT/'PlanningMap_base.png')
    # Подписи на предметах и таблички — единый печатный атлас.
    im=Image.new('RGB',(1024,1024),(178,168,139)); d=ImageDraw.Draw(im)
    labels=['RING / СКЛАД','ОПАСНО / 380 V','ДИЗЕЛЬ / ДГУ-16','НЕ КУРИТЬ','ВОДА / 20 Л','АПТЕЧКА','ИНСТРУМЕНТ','ИНВ. № 0842']
    for i,text in enumerate(labels):
        y=i*128; d.rectangle((0,y,1023,y+126),fill=(188,177,144))
        d.rectangle((8,y+8,1014,y+118),outline=(37,42,34),width=5)
        d.text((40,y+42),text,font=font(44),fill=(37,42,34))
    im.save(OUT/'Labels_base.png')
    # Декали: контактные пятна по сценариям использования, фиксированные в .tscn.
    for name,color in [('oil_stain',(19,21,16)),('wet_patch',(66,68,57)),('dirt',(70,55,38)),('rust_streak',(89,42,20)),('water_streak',(72,69,54)),('shoe_marks',(37,33,27)),('scratches',(164,153,126)),('paint_damage',(94,97,85))]:
        im=Image.new('RGBA',(256,256),(0,0,0,0)); d=ImageDraw.Draw(im)
        if name in ['rust_streak','water_streak']:
            for x,w,h in [(82,11,185),(104,5,216),(134,16,155),(151,7,190)]:d.rectangle((x,10,x+w,h),fill=color+(95,))
        elif name=='shoe_marks':
            for x,y in [(60,60),(142,150)]:
                d.rounded_rectangle((x,y,x+36,y+72),radius=13,fill=color+(75,))
                for yy in range(y+10,y+65,8):d.line((x,yy,x+36,yy),fill=(0,0,0,0),width=3)
        elif name=='scratches':
            for i in range(9):d.line((30+i*18,60,80+i*15,155-i*6),fill=color+(125,),width=2)
        else:
            d.polygon([(19,116),(36,62),(88,43),(119,62),(160,27),(213,83),(229,144),(192,207),(123,221),(55,187)],fill=color+(112,))
        im=im.filter(ImageFilter.GaussianBlur(6 if name not in ['shoe_marks','scratches'] else 1))
        im.save(OUT/(name+'.png'))
        if name in ['oil_stain','wet_patch']:
            orm=Image.new('RGBA',im.size,(255,100 if name=='oil_stain' else 74,0,0))
            orm.putalpha(im.getchannel('A'))
            orm.save(OUT/(name+'_orm.png'))
    room_signs()
    print('Prepared',len(SPECS),'PBR materials + trim/map/labels/signs/decals')

if __name__=='__main__':
    SRC.mkdir(parents=True,exist_ok=True)
    if '--fetch' in sys.argv:fetch()
    prepare()
