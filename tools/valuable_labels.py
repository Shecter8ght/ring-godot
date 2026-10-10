"""Новые этикетки запечатанных партий: никаких чужих брендов и логотипов."""
import json
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
out = ROOT / '_asset_src/loot_value/labels'
out.mkdir(parents=True, exist_ok=True)
specs = json.loads((ROOT/'data/valuable_loot_assets.json').read_text(encoding='utf8'))
font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 64)
small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 22)
bands = {'electronics':(35,65,92),'medical':(30,100,75),'vehicle':(160,82,32),
         'parts':(58,62,57),'food':(110,105,45),'ammo':(100,53,35),'signal':(177,43,28)}
for item, spec in specs.items():
    if not spec.get('label'): continue
    im = Image.new('RGB', (512, 320), (213,212,200)); d = ImageDraw.Draw(im)
    d.rectangle((8,8,503,311), outline=(45,48,47), width=4)
    d.rectangle((10,10,501,70),fill=bands[spec['group']])
    d.text((26,24), 'SEALED / '+spec['group'].upper(), font=small, fill=(242,242,230))
    label = spec.get('print', spec['label'].split(' / ')[0])
    d.multiline_text((26,88), '\n'.join(textwrap.wrap(label,13)), font=font, fill=(28,33,32), spacing=4)
    d.text((26,262), spec['label'][:32], font=small, fill=(58,61,59))
    im.save(out/(item+'.png'))
