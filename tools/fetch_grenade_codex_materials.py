"""Verified official CC0 source archives; keep provenance with the art source."""
import concurrent.futures
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / '_asset_src/grenade_codex'
BASE = OUT / 'textures/cc0_sources'
IDS = ['Metal049C', 'Metal009', 'Metal063']


def request(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (RING art material acquisition)',
        'Referer': 'https://ambientcg.com/'}), timeout=90)


def fetch(asset_id):
    folder = BASE / asset_id
    folder.mkdir(parents=True, exist_ok=True)
    metadata = json.loads((OUT / 'references/material_candidates' / (asset_id+'.json')).read_text())
    a = metadata['foundAssets'][0]
    downloads = a['downloadFolders']['default']['downloadFiletypeCategories']['zip']['downloads']
    item = next(d for d in downloads if d['attribute'] == '8K-PNG')
    archive = folder / item['fileName']
    if not archive.exists() or archive.stat().st_size != item['size']:
        temp = archive.with_suffix('.part')
        with request(item['downloadLink']) as response, temp.open('wb') as stream:
            while chunk := response.read(4*1024*1024):
                stream.write(chunk)
        assert temp.stat().st_size == item['size'], asset_id
        temp.replace(archive)
    maps = []
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None, asset_id
        for entry in z.infolist():
            target = (folder / entry.filename).resolve()
            assert target.is_relative_to(folder.resolve()), entry.filename
            z.extract(entry, folder)
            if target.suffix.lower() == '.png':
                data = target.read_bytes()
                assert data[:8] == b'\x89PNG\r\n\x1a\n'
                maps.append({'file': target.name, 'size': [int.from_bytes(data[16:20],'big'),
                              int.from_bytes(data[20:24],'big')], 'bit_depth': data[24],
                             'sha256': hashlib.sha256(data).hexdigest()})
    (folder / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    row = {'asset': asset_id, 'page': 'https://ambientcg.com/view?id='+asset_id,
           'license': 'CC0 1.0', 'license_url': 'https://docs.ambientcg.com/license/',
           'technique': a['creationMethod'], 'archive_bytes': archive.stat().st_size,
           'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'maps': maps}
    (folder / 'provenance.json').write_text(json.dumps(row, indent=2), encoding='utf8')
    print('CC0_SOURCE_OK', asset_id, len(maps), flush=True)
    return row


if __name__ == '__main__':
    BASE.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(fetch, IDS))
    (BASE / 'manifest.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
    with request('https://docs.ambientcg.com/license/') as r:
        (BASE / 'ambientCG_license.html').write_bytes(r.read())
    print('GRENADE_CC0_ACQUISITION_OK', flush=True)
