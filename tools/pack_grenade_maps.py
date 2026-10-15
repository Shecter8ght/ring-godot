"""Игровые PNG гранаты: sRGB albedo, normal GL, ORM = AO/roughness/metallic."""
from pathlib import Path
import hashlib
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_asset_src/grenade_game'
OUT = ROOT / 'assets/models/weapons/grenade'
OUT.mkdir(parents=True, exist_ok=True)
manifest = []
for atlas in ['body', 'mechanism']:
    for source, target in [('color', 'albedo'), ('normal', 'normal')]:
        image = Image.open(WORK / 'maps' / f'{atlas}_{source}.png').convert('RGB')
        path = OUT / f'grenade_{atlas}_{target}.png'
        image.save(path)
        manifest.append({'file': path.name, 'size': image.size, 'color_space': 'sRGB' if target == 'albedo' else 'linear',
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    channels = [Image.open(WORK / 'maps' / f'{atlas}_{c}.png').convert('RGB').getchannel(0) for c in ['ao', 'rough', 'metal']]
    image = Image.merge('RGB', channels)
    path = OUT / f'grenade_{atlas}_orm.png'
    image.save(path)
    manifest.append({'file': path.name, 'size': image.size, 'color_space': 'linear',
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
(OUT / 'maps.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
for path in OUT.glob('*.png.import'):
    if not path.name.startswith(('grenade_body_', 'grenade_mechanism_')):
        continue
    settings = path.read_text(encoding='utf8')
    settings = settings.replace('compress/mode=0', 'compress/mode=2')
    settings = settings.replace('mipmaps/generate=false', 'mipmaps/generate=true')
    settings = settings.replace('detect_3d/compress_to=1', 'detect_3d/compress_to=0')
    atlas = 'body' if '_body_' in path.name else 'mechanism'
    if '_normal.' in path.name:
        settings = settings.replace('compress/normal_map=0', 'compress/normal_map=1')
    roughness_mode = '8' if '_orm.' in path.name else '1'
    settings = settings.replace('roughness/mode=0', 'roughness/mode=' + roughness_mode)
    settings = settings.replace('roughness/src_normal=""', f'roughness/src_normal="res://assets/models/weapons/grenade/grenade_{atlas}_normal.png"')
    path.write_text(settings, encoding='utf8')
print('grenade maps:', len(manifest), 'PNG')
