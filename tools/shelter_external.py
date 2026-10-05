"""Проверяемые CC0 модели Poly Haven: сырьё и лицензия, затем Blender integration pass."""
from pathlib import Path
import json, urllib.request

ROOT = Path(__file__).resolve().parent.parent
UA = {'User-Agent': 'RING-asset-tool/1.0'}
MODELS = {'sofa_02': ('PH_Sofa', '2k'), 'ArmChair_01': ('PH_Armchair', '2k'),
          'old_military_crate': ('PH_Crate', '1k'), 'Barrel_01': ('PH_Barrel', '1k'),
          'ammo_box': ('PH_AmmoBox', '1k')}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read()

if __name__ == '__main__':
    catalog = json.loads(get('https://api.polyhaven.com/assets?t=models'))
    records = []
    for key, (name, resolution) in MODELS.items():
        folder = ROOT / '_asset_src/shelter/external' / key
        folder.mkdir(parents=True, exist_ok=True)
        files = json.loads(get('https://api.polyhaven.com/files/' + key))
        spec = files['gltf'][resolution]['gltf']
        for path, info in {key + '.gltf': spec, **spec.get('include', {})}.items():
            target = folder / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists(): target.write_bytes(get(info['url']))
        record = {'id': key, 'asset': name, 'author': ', '.join(catalog[key]['authors']),
                  'url': 'https://polyhaven.com/a/' + key, 'license': 'CC0 1.0',
                  'download_date': '2026-10-05', 'modified': True, 'resolution': resolution}
        records.append(record)
        (folder / 'license.txt').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print('FETCHED', name, flush=True)
    (ROOT / '_asset_src/shelter/external_sources.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
