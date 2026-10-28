"""Побайтный архив только переснимаемых видов редакции 6.1."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/screens/dorm'
ARCHIVE = OUT / 'light6_archive.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create():
    if ARCHIVE.exists():
        raise RuntimeError('Архив уже существует; используйте --verify')
    plan = json.loads((ROOT / 'data/blockouts/dorm.json').read_text(encoding='utf-8'))
    captures = []
    for case in ['evening_A', 'evening_B', 'overcast_A', 'evening_B_no_windows', 'night_A', 'night_B']:
        ids = ['04_wash', '05_stairs_bottom', '06_stairs_top', '14_toilets']
        if case in ['evening_A', 'evening_B']:
            ids += ['01_corridor', '02_room', '08_street', '09_lounge']
        if case.startswith('night_'):
            ids = ['01_corridor', '02_room', '08_street']
        for view in plan['shots']:
            if view['id'] not in ids:
                continue
            for fov in [80, 95]:
                if fov == 95 and view['id'] not in ['01_corridor', '02_room', '05_stairs_bottom']:
                    continue
                tag = case + ('_fov95' if fov == 95 else '')
                captures.append({'case': case, 'tag': tag, 'view': view['id'], 'fov': fov,
                                 'source': f'light_{tag}_{view["id"]}.png'})
    sources = [c['source'] for c in captures] + ['light_views.json', 'light_performance.json']
    copies = [(OUT / name, OUT / name.replace('light_', 'light6_', 1)) for name in sources]
    copies += [(OUT / f'r6_calibration/{gi}_02_room.png', OUT / f'light6_calibration_{gi}_02_room.png') for gi in ['A', 'B']]
    rows = []
    for source, before in copies:
        assert source.is_file() and not source.read_bytes().startswith(b'version https://git-lfs'), source
        assert not before.exists(), before
        shutil.copyfile(source, before)
        assert digest(source) == digest(before)
        rows.append({'source': source.relative_to(OUT).as_posix(), 'before': before.name,
                     'sha256': digest(before), 'bytes': before.stat().st_size})
    ARCHIVE.write_text(json.dumps({'base_commit': 'a34dbea7', 'captures': captures, 'files': rows},
                                 ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('LIGHT6_BYTE_ARCHIVE_CREATED', len(rows), 'files;', len(captures), 'views')


def verify():
    archive = json.loads(ARCHIVE.read_text(encoding='utf-8'))
    for row in archive['files']:
        assert digest(OUT / row['before']) == row['sha256'], row['before']
    print('LIGHT6_BYTE_ARCHIVE_PASS', len(archive['files']))


if __name__ == '__main__':
    verify() if '--verify' in sys.argv else create()
