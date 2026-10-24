"""Фотокарты CC0 и пользовательские маски. Фотографии-референсы не редактируются."""
from pathlib import Path
import json
import shutil
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from plan import PROJECT, ROOT, sha

TEX = ROOT / 'textures'
UA = {'User-Agent': 'RING-art-authoring/1.0 (private game project)'}
CACHED = {
    **{k: PROJECT / '_asset_src/textures' / k for k in (
        'rough_concrete', 'concrete_wall_007', 'rusty_metal_sheet', 'green_metal_rust',
        'metal_plate', 'wood_planks_grey', 'plywood', 'natural_walnut_veneer',
        'painted_plaster_wall', 'tarred_gravel', 'mud_forest')},
    **{k: PROJECT / '_asset_src/shelter/textures' / k for k in (
        'denim_fabric_06', 'brown_leather', 'blue_metal_plate', 'rubber_tiles', 'rusty_metal_02')},
}
OWNER = {
    'dust': '03_Пыль_и_частицы/Пыль_редкая_01.png',
    'film': '04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png',
    'grime': '04_Грязь_и_налёт/Грязь_пятнами_01.png',
    'scratches': '09_Царапины/Царапины_редкие_01.png',
    'finger': '01_Отпечатки_пальцев/Отпечаток_грязный_01.png',
    'splash': '05_Брызги_и_высохшие_капли/Брызги_средние_01.png',
}


def request_json(url):
    req = urllib.request.Request(url, headers=UA)
    return json.load(urllib.request.urlopen(req, timeout=40))


def scan(key):
    folder = TEX / key
    folder.mkdir(parents=True, exist_ok=True)
    if key in CACHED:
        src = CACHED[key]
        for name in ('albedo.jpg', 'normal.jpg', 'arm.jpg', 'license.txt'):
            shutil.copy2(src / name, folder / name)
        origin = dict(source=str(src), url='https://polyhaven.com/a/' + key,
            license='CC0-1.0', operation='Original cached maps copied without pixel changes')
    else:
        if (folder/'license.txt').exists() and all((folder/n).exists() for n in ('albedo.jpg','normal.jpg','arm.jpg')):
            origin=json.loads((folder/'license.txt').read_text(encoding='utf-8'))
            with Image.open(folder/'arm.jpg') as im:
                im.getchannel('G').save(folder/'roughness.png')
            return dict(id=key,**origin,files=[dict(file=p.relative_to(ROOT).as_posix(),sha256=sha(p))
                for p in sorted(folder.iterdir()) if p.is_file()])
        info = request_json('https://api.polyhaven.com/info/' + key)
        files = request_json('https://api.polyhaven.com/files/' + key)
        for kind, name in (('Diffuse', 'albedo.jpg'), ('nor_gl', 'normal.jpg'), ('arm', 'arm.jpg')):
            path = folder / name
            if path.exists():
                continue
            spec = files[kind]['2k']
            spec = spec.get('jpg') or spec['png']
            req = urllib.request.Request(spec['url'], headers=UA)
            path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        origin = dict(source='https://polyhaven.com/a/' + key, author=info.get('authors'),
            license='CC0-1.0', downloaded='2026-10-24', operation='Original 2K maps downloaded')
        (folder / 'license.txt').write_text(json.dumps(origin, ensure_ascii=False, indent=2), encoding='utf-8')
    with Image.open(folder / 'arm.jpg') as im:
        im.getchannel('G').save(folder / 'roughness.png')
    return dict(id=key, **origin, files=[dict(file=p.relative_to(ROOT).as_posix(), sha256=sha(p))
        for p in sorted(folder.iterdir()) if p.is_file()])


def single_surface(key, crop, prefix='surface_'):
    """Одинаковое техническое окно PBR удаляет чужую сетку швов из скана."""
    for source in ('albedo.jpg', 'normal.jpg', 'roughness.png'):
        with Image.open(TEX / key / source) as im:
            box = tuple(round(v * im.width / 2048) for v in crop)
            im.crop(box).save(TEX / key / (prefix + source.replace('.jpg', '.png')))


def ui_images():
    folder = TEX / 'original_graphics'
    folder.mkdir(exist_ok=True)
    font = 'C:/Windows/Fonts/arial.ttf'
    for name, title, lines, bg in (
        ('atm', 'РИНГ БАНК', ['БАНКОМАТ', 'Сеть недоступна', 'Обслуживание приостановлено'], (24, 43, 44)),
        ('ticket', 'ПАРКОВКА', ['ТЕРМИНАЛ ВЪЕЗДА', 'Нет связи', 'Ожидайте обслуживания'], (28, 33, 32)),
        ('monitor', 'РИНГ', ['СЛУЖЕБНЫЙ ТЕРМИНАЛ', 'Соединение прервано'], (21, 28, 31)),
    ):
        im = Image.new('RGB', (768, 512), bg)
        d = ImageDraw.Draw(im)
        d.rectangle((24, 24, 743, 487), outline=(99, 132, 120), width=2)
        for y, text, size in [(68, title, 47)] + [(190 + i * 69, t, 29 if i == 0 else 26) for i, t in enumerate(lines)]:
            f = ImageFont.truetype(font, size)
            b = d.textbbox((0, 0), text, font=f)
            d.text(((768 - b[2]) / 2, y), text, font=f, fill=(191, 201, 172))
        im.save(folder / (name + '.png'))
    y,x = np.mgrid[0:512,0:512].astype(np.float32)/511
    edge=np.minimum.reduce([x,y,1-x,1-y])
    value=np.exp(-edge/.035)
    Image.fromarray(np.uint8(value*255)).save(folder/'perimeter.png')
    for name,title,lines,base,size in (
        ('poster','РИНГ',['ГОРОД РЯДОМ','МАГАЗИНЫ · КАФЕ · СЕРВИСЫ'],(105,40,72),(768,1280)),
        ('billboard','КВАРТАЛ 07',['ВСЁ РЯДОМ','РИНГ'],(48,72,66),(1536,768)),
        ('warning','ПРОХОД',['ЗАКРЫТ','ТЕХНИЧЕСКАЯ ЗОНА'],(199,177,94),(768,1024)),
    ):
        im=Image.new('RGB',size,base)
        d=ImageDraw.Draw(im)
        w,h=size
        d.rectangle((w*.045,h*.04,w*.955,h*.96),outline=(210,202,168),width=5)
        d.polygon([(w*.10,h*.57),(w*.45,h*.35),(w*.87,h*.67),(w*.87,h*.76),(w*.10,h*.76)],fill=(79,100,89) if name!='warning' else (47,47,36))
        d.rectangle((w*.10,h*.78,w*.88,h*.80),fill=(214,192,151))
        for y,text,fs in [(h*.12,title,int(w*.085))]+[(h*(.29+i*.57),t,int(w*.040)) for i,t in enumerate(lines)]:
            f=ImageFont.truetype(font,fs)
            box=d.textbbox((0,0),text,font=f)
            d.text(((w-box[2])/2,y),text,font=f,fill=(224,217,190) if name!='warning' else (37,38,29))
        im.save(folder/(name+'.png'))


def main():
    TEX.mkdir(parents=True, exist_ok=True)
    sources = []
    for key in list(CACHED) + ['granite_tile', 'marble_01']:
        sources.append(scan(key))
        print('SCAN_READY', key, flush=True)
    # Tile-free regions are selected after inspecting these maps; originals remain.
    for key, crop in (('granite_tile', (35, 35, 380, 380)),
                      ('marble_01', (70, 42, 660, 390)),
                      ('concrete_wall_007', (160, 190, 1000, 380)),
                      ('wood_planks_grey', (38, 350, 360, 1990))):
        single_surface(key, crop)
        sources.append(dict(id=key + '_surface', source='https://polyhaven.com/a/' + key,
            license='CC0-1.0', operation='Matching PBR crop in 2048 coordinate system', crop=crop))
    ownerroot = Path('E:/Models Blender/Маски_АЛЬФА')
    for name, rel in OWNER.items():
        source = ownerroot / rel
        if not source.exists() and name == 'scratches':
            source = sorted((ownerroot / '09_Царапины').glob('*.png'))[0]
        path = TEX / ('owner_' + name + '.png')
        shutil.copy2(source, path)
        sources.append(dict(id='owner_' + name, source=str(source), file=path.relative_to(ROOT).as_posix(),
            sha256=sha(path), license='Owner supplied, no CC0 claim', operation='Original bytes'))
    sky = TEX / 'kloofendal_overcast_puresky.hdr'
    shutil.copy2(PROJECT / 'assets/sky' / sky.name, sky)
    shutil.copy2(PROJECT / '_asset_src/sky/kloofendal_overcast_puresky/license.txt', TEX / 'sky_license.txt')
    sources.append(dict(id='sky', source='https://polyhaven.com/a/kloofendal_overcast_puresky',
        license='CC0-1.0', sha256=sha(sky), operation='Original cached HDRI'))
    ui_images()
    sources.append(dict(id='original_graphics', license='Original project graphics',
        operation='Code-authored fictional LCD/poster/sign typography and technical glass perimeter mask; no copied brand graphics'))
    (ROOT / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2), encoding='utf-8')
    print('URBAN_TEXTURE_INPUTS_READY', len(sources), flush=True)


if __name__ == '__main__':
    main()
