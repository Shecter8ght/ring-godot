"""Seal the PM 20-v03 review folder; record its checked library publication."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / '_asset_src/pm_texturing'
REV = ROOT / 'revision_20_v03'
OUT = REV / 'delivery'
LIBRARY = Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/16_Текстуры_v3_20_на_проверку')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(check):
    assert check['pass_checks']
    assert not check['geometry_changes']
    assert not check['modifier_driver_action_shape_key_changes']


def seal(folder, check):
    records = []
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.name == 'package_manifest.json' or path.suffix in ('.blend1', '.blend2'):
            continue
        assert not path.is_symlink(), path
        records.append(dict(file=path.relative_to(folder).as_posix(),
                            bytes=path.stat().st_size, sha256=digest(path)))
    write(folder / 'package_manifest.json', dict(
        revision='20-v03', conditions=[20], owner_accepted=False,
        geometry_source_sha256=check['source_sha256'], files=records))
    return len(records)


ap = argparse.ArgumentParser()
ap.add_argument('mode', choices=('seal', 'published'), nargs='?', default='seal')
args = ap.parse_args()
if args.mode == 'seal':
    check = read(REV / 'checks/delivery_validation.json')
    validate(check)
    shutil.copy2(REV / 'checks/delivery_validation.json', OUT / '04_Проверки/delivery_validation.json')
    stills = [('detail', 'micro_slide', 'neutral'), ('detail', 'micro_slide', 'right'),
              ('detail', 'micro_grip', 'neutral'), ('detail', 'micro_grip', 'right'),
              ('detail', 'hammer', 'neutral'), ('review', 'left', 'neutral'),
              ('review', 'right', 'neutral'), ('review', 'trigger', 'neutral'),
              ('review', 'index', 'neutral')]
    for prefix, view, lighting in stills:
        name = f'PM_20_v03_{prefix}_{view}_{lighting}.png'
        shutil.copy2(REV / 'images' / name, OUT / '04_Проверки' / name)
    shutil.copy2(Path(__file__), OUT / '05_Скрипты' / Path(__file__).name)
    print('PM_20_V03_SEALED', seal(OUT, check), 'files')
else:
    check = read(REV / 'checks/final_validation.json')
    publication = read(REV / 'checks/publication.json')
    validate(check)
    assert publication['pass_checks']
    delivered = LIBRARY / '01_ПМ/PM_Textures_20_v03.blend'
    assert Path(check['file']).resolve() == delivered.resolve()
    assert digest(delivered) == digest(OUT / '01_ПМ/PM_Textures_20_v03.blend')
    for name in ('final_validation.json', 'publication.json'):
        shutil.copy2(REV / 'checks' / name, LIBRARY / '04_Проверки' / name)
    count = seal(LIBRARY, check)
    state = read(ROOT / 'texture_state.json')
    state.update(stage='Native UCUPaint PBR 20-v03, prepared for owner review',
                 delivery=str(LIBRARY), latest_model=str(delivered),
                 previous_delivery=str(LIBRARY.parent / '15_Текстуры_v2_20_на_проверку'),
                 texture_approved=False, focus_condition=20,
                 latest_owner_direction='Irregular moulded glossy phenolic; fine steel grain and rare pits; oily film, protected deposits and skin/dust particles in real grooves; edge wear to steel. Keep dark factory bluing and all hand marks.')
    write(ROOT / 'texture_state.json', state)
    print('PM_20_V03_PUBLICATION_RECORDED', count, 'files', digest(delivered))
