"""Fetch public photographic references only, never use them as texture maps."""
import hashlib
import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / '_asset_src/grenade_codex/references'
OUT.mkdir(parents=True, exist_ok=True)
PRODUCT = 'https://www.ima-usa.com/products/original-u-s-wwii-inert-mkii-pineapple-grenade-with-yellow-ring-m10a3-fuze-14'


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return urllib.request.urlopen(req, timeout=35).read()


manifest = []
for name, url in [
    ('late_war_pair.jpg', 'https://inert-ord.net/usa03a/usa2/mk2-45.jpg'),
    ('early_od_pair.jpg', 'https://inert-ord.net/usa03a/usa2/mk2-4243.jpg'),
    ('ima_closeup.jpg', 'https://www.ima-usa.com/cdn/shop/files/ONSV24NWS075__04_1024x1024.jpg?v=1737781141'),
    ('ima_neck.jpg', 'https://www.ima-usa.com/cdn/shop/products/ONSV22SOS290__05.jpg?v=1647644821'),
    ('ima_spoon.jpg', 'https://www.ima-usa.com/cdn/shop/files/ONJR23NSTG122__11.jpg?v=1702066726'),
]:
    try:
        data = fetch(url)
        (OUT/name).write_bytes(data)
        manifest.append({'file':name, 'url':url, 'sha256':hashlib.sha256(data).hexdigest(),
                         'use':'visual reference only', 'rights':'copyright holder; not texture content'})
        print('REF_OK', name, len(data), flush=True)
    except Exception as e:
        print('REF_UNAVAILABLE', url, str(e), flush=True)
try:
    data = json.loads(fetch(PRODUCT+'.json'))['product']
    for i, row in enumerate(data['images'][:5]):
        url = row['src']
        name = f'ima_original_{i+1:02}.jpg'
        content = fetch(url)
        (OUT/name).write_bytes(content)
        manifest.append({'file':name, 'url':url, 'page':PRODUCT,
                         'sha256':hashlib.sha256(content).hexdigest(),
                         'use':'visual reference only', 'rights':'International Military Antiques; not texture content'})
        print('REF_OK', name, len(content), flush=True)
except Exception as e:
    print('IMA_UNAVAILABLE', str(e), flush=True)
(OUT/'reference_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
assert manifest, 'No reference photograph fetched'
