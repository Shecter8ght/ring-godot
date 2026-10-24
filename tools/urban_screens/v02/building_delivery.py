"""Package only R06's approved-geometry PBR candidate; preserve the other assets."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

from PIL import Image

PROJECT = Path(__file__).resolve().parents[3]
WORK = PROJECT / '_asset_src/urban_realrefs_v02'
LIB = Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references')
REL = Path('assets/R06_building/pbr_v01')
ROOT = WORK / REL


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    native = json.loads((ROOT / 'checks/native_validation.json').read_text(encoding='utf-8'))
    audit = json.loads((ROOT / 'checks/accepted_geometry_audit.json').read_text(encoding='utf-8'))
    model = ROOT / 'model/R06_building_pbr_v01.blend'
    assert native['problems'] == [] and audit['pass']
    assert sha(model) == native['blend_sha256']
    source = WORK / 'assets/R06_building/model/R06_building_geometry_v02.blend'
    assert sha(source) == '6f3301969fd8148b42c227ca4348e36c20c2db33896dc9ef32046e4eb81b066d'
    records = []
    for path in sorted((ROOT / 'textures').rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        first = path.relative_to(ROOT / 'textures').parts[0]
        if first == 'weather':
            origin = 'Synthetic causal masks; building_maps.py, seeds front=6411, rear=6532, side=6653'
            lic = 'Original project texture mask; not a scan'
            operation = 'Architectural elevations, 176 px/m, actual sill/eaves/plinth positions'
        elif first.startswith('owner_'):
            origin = 'Owner mask library E:/Models Blender/Маски_АЛЬФА; exact source in sources.json'
            lic = 'Owner supplied; no CC0 claim'
            operation = 'Original bytes; native layer sets scale and masks'
        else:
            key = 'kloofendal_overcast_puresky' if first.endswith('.hdr') or first == 'sky_license.txt' else first
            origin, lic = 'https://polyhaven.com/a/' + key, 'CC0-1.0'
            operation = ('Single brick-face crop of 2048 source (130,12,245,42), same window for each PBR map'
                if path.name.startswith('single_') else 'ARM green-channel separation' if path.name == 'roughness.png' else 'Unmodified cached source')
        record = dict(file=rel, sha256=sha(path), bytes=path.stat().st_size,
            source=origin, license=lic, operation=operation)
        if path.suffix.lower() in ('.png', '.jpg'):
            with Image.open(path) as im:
                record['size'] = list(im.size)
        records.append(record)
    manifest = dict(asset='R06_building', version='pbr_v01', date='2026-10-24',
        geometry_source='model/R06_building_geometry_v02.blend', geometry_sha256=sha(source),
        approval='Owner: Форма подходит — переходи к текстурам', geometry_approved=True,
        texture_approved=False, status='Textured native source prepared for owner review',
        blender=native['blender'], ucupaint=native['ucupaint'],
        model='model/R06_building_pbr_v01.blend', blend_sha256=sha(model),
        native_materials=native['native_materials'], native_layers=native['native_layers'], native_masks=native['native_masks'],
        packed_image_datablocks=native['image_datablocks_checked'],
        authoring_uvs=dict(MetricUV='Overlapping world-metre projections, tiled scans; not a game atlas',
            WeatherUV='Unique normalized elevation masks; front/rear/side', PartUV='Local detail projection'),
        accepted_geometry_unchanged=True, geometry_audit='checks/accepted_geometry_audit.json',
        game_export=False, materials=records)
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    state = f'''# R06 — текстурный кандидат v01, 2026-10-24

Форма явно принята владельцем: «Форма подходит — переходи к текстурам».
Принятый источник сохранён отдельно: `../model/R06_building_geometry_v02.blend`.
SHA-256 геометрии: `{sha(source)}`.

Открыть: `model/R06_building_pbr_v01.blend`. Blender {native['blender']}, настоящий
UCUPaint {native['ucupaint']}: {native['native_materials']} материала,
{native['native_layers']} редактируемый слой, {native['native_masks']} масок.
{native['image_datablocks_checked']} image datablocks встроены; внешние копии с
относительными путями и SHA-256 лежат в dependencies, их список — checks/image_manifest.json.

## Форма и масштаб

Корпус 34,8 × 10,5 × 6,65 м; габарит с выступами 35,374 × 11,9845 × 6,75763 м.
Метры, Z вверх, передняя сторона −Y, origin в середине основания. Принятые сетки,
тексты, модификаторы и иерархия сохранены; audit_source сравнил 1020 объектов,
добавленных объектов и изменений геометрии нет. У 1015 mesh-объектов добавлены
авторские UV. Это перекрывающиеся проекции в метрах и отдельная развёртка масок
фасада, не уникальный игровой атлас. Реальный адрес и название не копировались:
в модели «УЧЕБНЫЙ КОРПУС» и «17 А».

## Материалы по трём фотографиям

- Светлая старая окрашенная штукатурка: фотозерно, разная шероховатость,
  неровная окраска, отдельный Normal/Height наплывов между этажами.
- Угловые трещины и отслоения до кирпича сохраняют принятую форму;
  тонкие трещины — дополнительные локальные слои материала.
- Грязь под подоконниками, накопление под карнизом, капиллярная сырость у цоколя
  имеют разные уникальные маски; это синтетические рисунки по месту, не сканы.
- Белый состарившийся ПВХ, EPDM-уплотнители, стекло IOR 1,46, красно-коричневые
  окрашенные деревянные двери, выцветший жёлто-охристый стальной козырёк.
- Грязь/окислы/краска — диэлектрики; металлическая основа и ручки отдельны.
  Скрытые стороны сохраняют ранее принятую реконструкцию.

Изменение отделки: выберите материал R06_*, откройте нативный стек UCUPaint.
Слои 30/35/40 меняют потёки/карниз/сырость, 16 — рельеф старой штукатурки,
45/48 — тонкие трещины; слой 05 задаёт оттенок побелки.
Рельеф — шейдерный Bump/Normal, геометрический displacement не включён.

## Источники и проверка

Референсы — три неизменённых файла в ../../../references/building_user;
стиль готовой игровой отделки — ранее присланные владельцем кадры Tarkov.
Фототекстуры Poly Haven: Painted Plaster Wall (Amal Kumar), Red Bricks 04
(Rob Tuytel), Rusty Metal Sheet (Amal Kumar), Rough Concrete и Wood Planks Grey
(автор в соседнем license.txt); HDRI Kloofendal Overcast Pure Sky (Greg Zaal).
Наборы CC0; исходные license.txt сохранены. Карты roughness технически отделены
из ARM, у кирпича вырезана одна грань без швов, чтобы не дублировать
смоделированные ряды. Маски владельца — из E:/Models Blender/Маски_АЛЬФА,
их лицензия CC0 не заявляется. Фото владельца не являются игровым albedo.
sources.json, manifest.json и checks/image_manifest.json перечисляют происхождение,
обработку, размеры, color space и хеши. BaseColor — sRGB, данные — Non-Color.

Проверены общий вид, задняя сторона, вход, штукатурка, отслоение и козырёк;
дневной свет и ночные лампы. Итоговый файл повторно открывается из папки
библиотеки; отчёты — checks/native_validation.json и accepted_geometry_audit.json.
Ночная подсветка — диагностическая настройка студии, не внедрение освещения в игру.

Текстуры подготовлены к просмотру владельцем. Игровые UV/bake/LOD, коллизии,
оптимизация, риг и импорт в Godot в этот этап не входят.
'''
    (ROOT / 'asset-state.md').write_text(state, encoding='utf-8')
    (ROOT / 'README.md').write_text('# Здание R06 — PBR v01\n\n'
        '[Открыть .blend](model/R06_building_pbr_v01.blend) · [Состояние](asset-state.md)\n\n'
        'Форма принята, текстуры подготовлены к просмотру. Нативные слои UCUPaint сохранены.\n\n'
        '[Днём](previews/front34_day.png) · [Ночью](previews/front34_night.png) · '
        '[Штукатурка](previews/plaster_night.png) · [Отслоение](previews/damage_day.png) · '
        '[Вход](previews/entry_day.png) · [Козырёк](previews/canopy_day.png)\n', encoding='utf-8')
    return manifest


def update_parent(root, manifest):
    file = root / 'manifest.json'
    data = json.loads(file.read_text(encoding='utf-8'))
    record = next(r for r in data['assets'] if r['id'] == 'R06')
    record.update(geometry_approved=True, production_uv=True, production_textures=True,
        texture_approved=False, pbr_model=(REL / manifest['model']).as_posix(),
        pbr_manifest=(REL / 'manifest.json').as_posix(), pbr_sha256=manifest['blend_sha256'])
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    note = root / 'README.md'
    text = note.read_text(encoding='utf-8')
    text = text.replace('REVIEW-материалы нейтральные, только для оценки формы. Производственные UV, UCUPaint/PBR, игровая сетка, LOD, коллизии и импорт в Godot не выполнены. Форма ещё не принята владельцем.',
        'Пять предметов R01–R05 пока имеют нейтральные REVIEW-материалы для оценки формы. Геометрия R06 принята владельцем; её новая текстурная версия — отдельный файл ниже. Игровые LOD, коллизии и импорт не выполнены.')
    text = text.replace('Фактура и цвет со снимков ещё не перенесены в PBR: сначала владелец принимает показанную геометрию.',
        'Форма здания принята; фактура и цвет перенесены в отдельный кандидат PBR v01.')
    marker = '\n## Текстурная версия здания R06\n'
    if marker in text:
        text = text[:text.index(marker)]
    text += marker + '\n[Открыть здание с текстурами](assets/R06_building/pbr_v01/model/R06_building_pbr_v01.blend). '
    text += '[Материалы и проверки](assets/R06_building/pbr_v01/asset-state.md). '
    text += 'Принятая геометрия сохранена отдельно. Текстуры ожидают оценки владельцем.\n'
    note.write_text(text, encoding='utf-8')
    state = root / 'assets/R06_building/asset-state.md'
    state.write_text('# R06 — форма принята; текстуры v01\n\n'
        '2026-10-24 владелец: «Форма подходит — переходи к текстурам».\n\n'
        '[Текущий PBR .blend](pbr_v01/model/R06_building_pbr_v01.blend) · '
        '[Материалы, источники и проверки](pbr_v01/asset-state.md).\n\n'
        'Принятая геометрия сохранена без перезаписи: model/R06_building_geometry_v02.blend. '
        'Текстуры подготовлены к просмотру; игровой экспорт не выполнялся.\n', encoding='utf-8')


def deliver():
    manifest = prepare()
    dst = LIB / REL
    dst.mkdir(parents=True, exist_ok=True)
    for name in ('model', 'textures', 'dependencies', 'checks'):
        shutil.copytree(ROOT / name, dst / name, dirs_exist_ok=True)
    for name in ('sources.json', 'manifest.json', 'asset-state.md', 'README.md'):
        shutil.copy2(ROOT / name, dst / name)
    for root in (WORK, LIB):
        update_parent(root, manifest)
    target = LIB / 'source/urban_screens/v02'
    target.mkdir(parents=True, exist_ok=True)
    for script in Path(__file__).parent.glob('*.py'):
        shutil.copy2(script, target / script.name)
    assert sha(dst / manifest['model']) == manifest['blend_sha256']
    for row in json.loads((dst / 'checks/image_manifest.json').read_text(encoding='utf-8')):
        assert sha(dst / row['file']) == row['sha256']
    report = dict(destination=str(dst), blend_sha256=manifest['blend_sha256'],
        accepted_geometry_preserved=True, model_copied_and_hash_verified=True,
        all_external_dependency_hashes_verified=True, other_five_models_unchanged=True,
        reopen_from_delivery_pending=True)
    (dst / 'checks/delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('R06_PBR_DELIVERED', dst)


def finalize():
    dst = LIB / REL
    native = json.loads((dst / 'checks/native_validation.json').read_text(encoding='utf-8'))
    audit = json.loads((dst / 'checks/accepted_geometry_audit.json').read_text(encoding='utf-8'))
    model = dst / 'model/R06_building_pbr_v01.blend'
    assert Path(native['file']) == model and not native['problems']
    assert Path(audit['candidate']) == model and audit['pass']
    assert sha(model) == native['blend_sha256']
    views = json.loads((dst / 'checks/render_views.json').read_text(encoding='utf-8'))
    for view in views:
        assert Path(view['source_blend']) == model
        file = Path(view['file'])
        assert file.is_file()
        with Image.open(file) as im:
            im.verify()
    assert len(views) == 9
    report = dict(destination=str(dst), blend_sha256=sha(model),
        accepted_geometry_preserved=True, model_copied_and_hash_verified=True,
        all_external_dependency_hashes_verified=True, other_five_models_unchanged=True,
        reopened_from_delivery=True, native_validation_passed=True,
        geometry_audit_passed=True, fresh_views_from_delivery=len(views), texture_approved=False)
    (dst / 'checks/delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copytree(dst / 'previews', ROOT / 'previews', dirs_exist_ok=True)
    for name in ('native_validation.json', 'accepted_geometry_audit.json', 'render_views.json', 'delivery.json'):
        shutil.copy2(dst / 'checks' / name, ROOT / 'checks' / name)
    target = LIB / 'source/urban_screens/v02'
    for script in Path(__file__).parent.glob('*.py'):
        shutil.copy2(script, target / script.name)
    print('R06_PBR_FINALIZED', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--deliver', action='store_true')
    parser.add_argument('--finalize', action='store_true')
    args = parser.parse_args()
    if args.finalize:
        finalize()
    elif args.deliver:
        deliver()
    else:
        prepare()
        print('R06_PBR_PACKAGE_PREPARED')
