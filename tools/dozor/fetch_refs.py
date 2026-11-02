"""Download manufacturer photographs for private shape reference, never texture inputs."""
import json
import pathlib
import re
import urllib.request
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'референсы' / 'dozor'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'https://www.fenixlighting.com/cdn/shop/'
URLS = {
    'side': BASE + 'files/fenix-TK16_V2.0-tactical-flashlight-straight_1x1.jpg',
    'front': BASE + 'files/fenix-TK16_V2.0-tactical-flashlight-angle_1x1.jpg',
    'tail': BASE + 'files/fenix-TK16_V2.0-tactical-flashlight-tail-switch_1x1.jpg',
    'bezel': BASE + 'products/TK16-V2.0-Tactical-Flashlight-glass-breaker_1x1.jpg',
    'hero': BASE + 'files/TK16_V2.0_5000-web_1x1.jpg',
}

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read()

URLS = {name: url.replace('_1x1.jpg', '.jpg') for name, url in URLS.items()}
for name, url in list(URLS.items()):
    try:
        (OUT / (name + '.jpg')).write_bytes(fetch(url))
        print(name, 'OK', flush=True)
    except Exception as exc:
        print(name, str(exc), flush=True)

html = fetch('https://fenixlight.com.au/product/fenix-alg-00-flashlight-ring/').decode()
imgs = list(dict.fromkeys(x for x in re.findall(r'https://[^\s\"<>]+\.(?:jpg|png|webp)', html) if 'alg' in x.lower()))
for i, url in enumerate(imgs[:5]):
    name = f'mount_{i}'
    try:
        (OUT / (name + '.jpg')).write_bytes(fetch(url))
        URLS[name] = url
        print(name, 'OK', flush=True)
    except Exception as exc:
        print(name, str(exc), flush=True)
(OUT / 'urls.json').write_text(json.dumps(URLS, ensure_ascii=False, indent=2), encoding='utf-8')
files = [p for p in OUT.glob('*.jpg') if p.name != 'reference_sheet.jpg']
assert files, 'No reference images downloaded'
sheet = Image.new('RGB', (1200, 450 * ((len(files)+2)//3)), (225, 225, 225))
draw = ImageDraw.Draw(sheet)
for i, path in enumerate(files):
    img = Image.open(path).convert('RGB')
    img.thumbnail((390, 410))
    x, y = (i % 3)*400, (i//3)*450
    sheet.paste(img, (x+(400-img.width)//2, y+25))
    draw.text((x+10, y+5), path.stem, fill='black')
sheet.save(OUT / 'reference_sheet.jpg')
