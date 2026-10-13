"""Matched comparison images and portable review delivery for grenade task 1.

No gallery, video, presentation, asset export or cleanup of the accepted v08.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '_asset_src/grenade_codex/materials_v09_stage1'
LIBRARY = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v09_Task1_На_проверку')
NAME = 'Grenade_MkII_Studio_v09_Task1.blend'
TITLES = {'head': 'Головка — отдельная мелкозернистая фактура',
          'lever': 'Скоба — тонкая фактура листового металла',
          'wire': 'Кольцо — продольная фактура волочения'}
CROPS = {'head': (490, 550, 1130, 1190),
         'lever': (280, 320, 1380, 1380),
         'wire': (940, 270, 1620, 1170)}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def comparison(shot):
    folder = WORK / 'comparisons'
    before = json.loads((folder / f'{shot}_before.json').read_text(encoding='utf8'))
    after = json.loads((folder / f'{shot}_after.json').read_text(encoding='utf8'))
    if before['comparison_spec'] != after['comparison_spec']:
        raise RuntimeError(('Unequal comparison setup', shot))
    originals = [folder / f'{shot}_{version}.png' for version in ['before', 'after']]
    for path in originals:
        header = path.read_bytes()[:26]
        if header[24] != 16:
            raise RuntimeError(('Comparison original is not PNG16', path))
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    font = ImageFont.truetype(str(font_path), 27)
    label_font = ImageFont.truetype(str(font_path), 23)
    rows = []
    for detail in [False, True]:
        images = []
        for path in originals:
            with Image.open(path) as im:
                im = im.convert('RGB')
                if detail:
                    im = im.crop(CROPS[shot])
                else:
                    im = im.resize((1152, 1152), Image.Resampling.LANCZOS)
                images.append(im.copy())
        width, height = images[0].size
        margin, top = 12, 82
        canvas = Image.new('RGB', (2 * width + margin, height + top), (20, 24, 27))
        draw = ImageDraw.Draw(canvas)
        title = TITLES[shot] + (' · фрагмент 1:1' if detail else '')
        draw.text((14, 7), title, fill=(237, 239, 239), font=font)
        draw.text((14, 44), 'ДО · принятая v08', fill=(185, 195, 197), font=label_font)
        draw.text((width + margin + 14, 44), 'ПОСЛЕ · только фактура v09', fill=(221, 209, 167), font=label_font)
        canvas.paste(images[0], (0, top))
        canvas.paste(images[1], (width + margin, top))
        path = folder / f'{shot}_comparison{"_detail" if detail else ""}.jpg'
        canvas.save(path, quality=98, subsampling=0)
        rows.append({'file': path.name, 'size': list(canvas.size), 'sha256': sha(path),
                     'same_crop_both': list(CROPS[shot]) if detail else None,
                     'processing': 'labels and layout only; identical display resize or identical 1:1 crop'})
    return {'shot': shot, 'equal_camera_lights_exposure_render_seed': True,
            'before_source_sha256': before['source_sha256'],
            'after_source_sha256': after['source_sha256'],
            'originals': [{'file': p.name, 'sha256': sha(p), 'PNG_depth': 16} for p in originals],
            'views': rows}


def compare(shots):
    path = WORK / 'checks/comparisons_verified.json'
    record = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    for shot in shots:
        record[shot] = comparison(shot)
        print('COMPARISON_OK', shot, flush=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')


def deliver():
    verification = json.loads((WORK / 'checks/verify_task1.json').read_text(encoding='utf8'))
    comparisons = json.loads((WORK / 'checks/comparisons_verified.json').read_text(encoding='utf8'))
    if not verification['pass'] or set(comparisons) != set(TITLES):
        raise RuntimeError('Verify protected state and all three render comparisons before delivery')
    if sha(WORK / NAME) != verification['sha256']:
        raise RuntimeError('Candidate changed since final verification')
    if LIBRARY.exists():
        raise RuntimeError('Review folder already exists; do not overwrite it blindly')
    LIBRARY.mkdir(parents=True)
    shutil.copy2(WORK / NAME, LIBRARY / NAME)
    for name in ['textures', 'resources', 'source', 'comparisons']:
        shutil.copytree(WORK / name, LIBRARY / name)
    (LIBRARY / 'checks').mkdir()
    for name in ['baseline_v08.json', 'verify_task1.json', 'patch_task1.json',
                 'self_contained_images.json', 'comparisons_verified.json']:
        shutil.copy2(WORK / 'checks' / name, LIBRARY / 'checks' / name)
    shutil.copy2(WORK / 'backup_v08/manifest.json', LIBRARY / 'checks/backup_manifest.json')
    shutil.copy2(ROOT / 'tools/package_grenade_surface_v09.py', LIBRARY / 'source/package_grenade_surface_v09.py')
    shutil.copy2(WORK / 'asset-state.md', LIBRARY / 'asset-state.md')
    (LIBRARY / '00_НАЧНИ_ЗДЕСЬ.txt').write_text(
        'На визуальную проверку — ТОЛЬКО задача 1: разные производственные фактуры.\n'
        'Открой Grenade_MkII_Studio_v09_Task1.blend в Blender.\n'
        'Внутри High Poly и нативные стеки UCUPaint, все 28 изображений встроены.\n'
        'Сравнения: comparisons/*_comparison.jpg; крупные фрагменты *_detail.jpg.\n'
        'Исходные PNG16 до/после сохранены вместе с одинаковыми настройками рендера.\n'
        'Принятая v08 сохранена; резервные копии и их хеши указаны в checks/backup_manifest.json.\n'
        'Загрязнения, износ, Metallic, геометрия и маркировка не редактировались.\n'
        'Дальнейшие задачи — только после визуального подтверждения владельца.\n', encoding='utf8')
    records = []
    for path in sorted(LIBRARY.rglob('*')):
        if not path.is_file():
            continue
        source = WORK / path.relative_to(LIBRARY)
        digest = sha(path)
        if source.exists() and source.is_file() and sha(source) != digest:
            raise RuntimeError(('Delivered copy differs', path))
        records.append({'file': path.relative_to(LIBRARY).as_posix(), 'bytes': path.stat().st_size,
                        'sha256': digest})
    (LIBRARY / 'file_manifest.json').write_text(json.dumps({'status': 'pending_owner_visual_review',
        'scope': 'task_1_only', 'files': records}, ensure_ascii=False, indent=2), encoding='utf8')
    print('DELIVERY_OK', LIBRARY, len(records), sha(LIBRARY / NAME), flush=True)


def seal():
    """Refresh this task's verification/source copies; never save the model."""
    record = json.loads((WORK / 'checks/verify_task1.json').read_text(encoding='utf8'))
    if not record['pass'] or Path(record['file']).resolve() != (LIBRARY / NAME).resolve():
        raise RuntimeError('Fresh verification must refer to the delivered file')
    if sha(LIBRARY / NAME) != record['sha256']:
        raise RuntimeError('Delivered model changed after verification')
    for name in ['grenade_surface_v09.py', 'grenade_manufacturing_maps_v09.py', 'package_grenade_surface_v09.py']:
        shutil.copy2(ROOT / 'tools' / name, LIBRARY / 'source' / name)
    shutil.copy2(WORK / 'checks/verify_task1.json', LIBRARY / 'checks/verify_task1.json')
    records = [{'file': p.relative_to(LIBRARY).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
               for p in sorted(LIBRARY.rglob('*')) if p.is_file() and p.name != 'file_manifest.json']
    (LIBRARY / 'file_manifest.json').write_text(json.dumps({'status': 'pending_owner_visual_review',
        'scope': 'task_1_only', 'files': records}, ensure_ascii=False, indent=2), encoding='utf8')
    # Verify v08 originals and exact backups after all work, too.
    backups = json.loads((WORK / 'backup_v08/manifest.json').read_text(encoding='utf-8-sig'))
    for item in backups:
        for key in ['source', 'backup']:
            if sha(Path(item[key])).lower() != item['sha256'].lower():
                raise RuntimeError(('Accepted v08 or backup changed', item[key]))
    print('SEAL_OK', len(records), 'V08_AND_BACKUPS_UNCHANGED', record['sha256'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['compare', 'deliver', 'seal'])
    parser.add_argument('--shot', choices=list(TITLES))
    args = parser.parse_args()
    if args.mode == 'compare':
        compare([args.shot] if args.shot else list(TITLES))
    elif args.mode == 'deliver':
        deliver()
    else:
        seal()


if __name__ == '__main__':
    main()
