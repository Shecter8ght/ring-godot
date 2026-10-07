"""PBR и графика котельной (убежище в зоне 5) и тира. Только production authoring.

Дополняет shelter_materials.py: те же фототекстуры Poly Haven CC0 с тинтом и упаковкой ORM,
плюс собственная графика — армированное стекло окон, лист «мишень № 4», пробоина, кнопки пульта.
python tools/shelter_boiler_materials.py [--fetch]
"""
from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shelter_materials as sm

OUT = sm.OUT
SRC = sm.SRC
DATE = '2026-10-07'
# Новые фотоисточники: кирпич котельной, побелка, облезлая краска зала, обшивка котлов, газоходы.
BOILER_KEYS = ['factory_brick', 'whitewashed_brick', 'peeling_painted_wall', 'blue_metal_plate', 'rusty_metal_02']
sm.NEW.extend(k for k in BOILER_KEYS if k not in sm.NEW)
sm.SPECS.update({
    'Brick': ('factory_brick', (.92, .86, .80), .88, 0, 2),
    'Whitewash': ('whitewashed_brick', (.93, .93, .90), .92, 0, 2),
    'PeelingPaint': ('peeling_painted_wall', (.86, .93, .88), .82, 0, 2),
    'BoilerSteel': ('blue_metal_plate', (1.30, 1.36, 1.30), .60, 0, 1),
    'FlueRust': ('rusty_metal_02', (.74, .66, .60), .86, .15, 1),
    'ButtonGreen': ('rubber_tiles', (1, 1, 1), .42, 0, 1),
    'ButtonRed': ('rubber_tiles', (1, 1, 1), .42, 0, 1),
    'ButtonYellow': ('rubber_tiles', (1, 1, 1), .42, 0, 1),
})
sm.SOLID.update({'BoilerSteel': [88, 100, 104], 'ButtonGreen': [44, 128, 58], 'ButtonRed': [158, 34, 26], 'ButtonYellow': [196, 152, 34]})


def fetch() -> None:
    catalog = json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/assets?t=textures', headers=sm.UA)))
    records = json.loads((SRC/'sources.json').read_text(encoding='utf-8')) if (SRC/'sources.json').exists() else []
    known = {r['id'] for r in records}
    for key in BOILER_KEYS:
        dest = SRC/'textures'/key
        dest.mkdir(parents=True, exist_ok=True)
        spec = json.load(urllib.request.urlopen(urllib.request.Request('https://api.polyhaven.com/files/' + key, headers=sm.UA)))
        for mapkey, filename in [('Diffuse', 'albedo'), ('nor_gl', 'normal'), ('arm', 'arm')]:
            variant = spec.get(mapkey, {}).get('1k', {})
            variant = variant.get('jpg') or variant.get('png')
            if not variant:
                raise RuntimeError(f'{key}: нет {mapkey}')
            target = dest/(filename + '.jpg')
            if not target.exists():
                target.write_bytes(urllib.request.urlopen(urllib.request.Request(variant['url'], headers=sm.UA), timeout=60).read())
        info = catalog[key]
        record = {'name': info['name'], 'id': key, 'author': ', '.join(info['authors']), 'url': 'https://polyhaven.com/a/' + key, 'license': 'CC0 1.0', 'download_date': DATE}
        (dest/'license.txt').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        if key not in known:
            records.append(record)
        print('Fetched', key, flush=True)
    (SRC/'sources.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


def wired_glass() -> None:
    # Армированное матовое стекло старых окон котельной: рассеянный свет, сетка проволоки 25 мм,
    # пыль и потёки по низу рамы. Плитка — 1 м на 1024 px.
    rng = np.random.default_rng(1207)
    size = 1024
    y = np.linspace(0, 1, size)[:, None]
    base = np.array([168, 178, 176], dtype=np.float32)[None, None, :] * np.ones((size, size, 1), dtype=np.float32)
    base += rng.normal(0, 3.5, (size, size, 1))
    # грязь собирается к низу листа
    base *= (1.0 - 0.22 * np.clip((y - .55) / .45, 0, 1))[:, :, None]
    im = Image.fromarray(np.clip(base, 0, 255).astype('uint8'))
    d = ImageDraw.Draw(im)
    step = 25.6
    for i in range(41):
        v = int(i * step)
        d.line((v, 0, v, size), fill=(92, 96, 94), width=2)
        d.line((0, v, size, v), fill=(92, 96, 94), width=2)
    im = im.filter(ImageFilter.GaussianBlur(.6))
    im.save(OUT/'WiredGlass_base.jpg', quality=92)
    Image.new('RGB', (size, size), (255, 70, 0)).save(OUT/'WiredGlass_orm.jpg', quality=94)
    Image.new('RGB', (size, size), (128, 128, 255)).save(OUT/'WiredGlass_normal.jpg', quality=94)


def range_paper() -> None:
    # Лист тира 600 × 1000 мм (1 px = 1 мм): грудная фигура с головой (мишень № 4 с удлинённым
    # листом), оценочные кольца по груди, типографская подпись внизу. Голова — верхние 250 мм.
    w, h = 600, 1000
    rng = np.random.default_rng(404)
    paper = np.array([226, 220, 199], dtype=np.float32)[None, None, :] * np.ones((h, w, 1), dtype=np.float32)
    paper += rng.normal(0, 3.0, (h, w, 1))
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)).astype(np.float32)
    paper *= (0.93 + 0.07 * np.clip(edge / 40.0, 0, 1))[:, :, None]
    im = Image.fromarray(np.clip(paper, 0, 255).astype('uint8'))
    d = ImageDraw.Draw(im)
    figure = (34, 38, 30)
    # голова и шея
    d.ellipse((215, 40, 385, 235), fill=figure)
    d.rectangle((262, 200, 338, 290), fill=figure)
    # плечи и грудь — трапеция со скруглёнными плечами
    d.polygon([(95, 340), (505, 340), (545, 820), (55, 820)], fill=figure)
    d.ellipse((60, 260, 260, 430), fill=figure)
    d.ellipse((340, 260, 540, 430), fill=figure)
    d.rectangle((150, 280, 450, 360), fill=figure)
    # оценочные кольца по центру груди
    cx, cy = 300, 520
    ring = (196, 190, 168)
    for k, r in enumerate([40, 80, 120, 160, 200]):
        d.ellipse((cx - r, cy - int(r * 1.18), cx + r, cy + int(r * 1.18)), outline=ring, width=3)
        score = str(10 - k)
        d.text((cx - 6, cy - int(r * 1.18) + 8), score, font=sm.font(20), fill=ring)
    d.line((cx - 12, cy, cx + 12, cy), fill=ring, width=2)
    d.line((cx, cy - 12, cx, cy + 12), fill=ring, width=2)
    # кольцо головы
    d.ellipse((265, 95, 335, 175), outline=ring, width=3)
    d.text((24, 935), 'МИШЕНЬ № 4 — ГРУДНАЯ ФИГУРА', font=sm.font(26), fill=(60, 58, 50))
    d.text((24, 966), 'ТИР КОТЕЛЬНОЙ · ОГНЕВОЙ РУБЕЖ', font=sm.font(18), fill=(96, 90, 78))
    d.rectangle((4, 4, w - 5, h - 5), outline=(150, 142, 120), width=2)
    im.save(OUT/'RangePaper_base.png')
    Image.new('RGB', (w, h), (255, 230, 0)).save(OUT/'RangePaper_orm.png')


def range_hole() -> None:
    # Пробоина для декали на манекене: тёмное отверстие, рваная светлая кромка, мягкий край.
    s = 64
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    d = np.hypot(xx - 31.5, yy - 31.5)
    a = np.arctan2(yy - 31.5, xx - 31.5)
    r = 11.0 * (1 + .2 * np.sin(a * 5 + 1.3) + .1 * np.sin(a * 11))
    rgba = np.zeros((s, s, 4), dtype=np.float32)
    core = d <= r
    rim = (d > r) & (d <= r * 1.6)
    rgba[core] = [10, 9, 8, 255]
    rgba[rim] = [200, 194, 180, 200]
    halo = (d > r * 1.6) & (d <= r * 2.4)
    rgba[halo] = [40, 36, 30, 90]
    Image.fromarray(rgba.astype('uint8'), 'RGBA').filter(ImageFilter.GaussianBlur(.7)).save(OUT/'range_hole.png')


if __name__ == '__main__':
    if '--fetch' in sys.argv:
        fetch()
    for name in ['Brick', 'Whitewash', 'PeelingPaint', 'BoilerSteel', 'FlueRust', 'ButtonGreen', 'ButtonRed', 'ButtonYellow']:
        sm.make_material(name)
    wired_glass()
    range_paper()
    range_hole()
    sm.room_signs()
    print('BOILER_MATERIALS done')
