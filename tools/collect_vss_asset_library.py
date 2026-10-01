"""Понятная автономная библиотека ВСС: подготовка списка, копирование и сверка."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / '_asset_src'
KIT = RAW / 'vss_textured'
PLAN = KIT / 'library-plan.json'
DEFAULT_DEST = Path('E:/Models Blender/ВСС Винторез — полный комплект')
ITEMS = (
    ('VSS_Vintorez_Picatinny', '01_ВСС', 'ВСС', RAW/'vss_picatinny/VSS_Vintorez_Picatinny_v3.blend'),
    ('PSO_VSS_4x24', '02_Оптика/01_ПСО_4x24', 'ПСО_4x24', RAW/'vss_optics/PSO_VSS_4x24.blend'),
    ('Rail_4x32', '02_Оптика/02_Прицел_4x32', 'Прицел_4x32', RAW/'vss_optics/Rail_4x32.blend'),
    ('Magazine_939_10_Empty', '03_Магазины/01_Пустой', 'Магазин_пустой', RAW/'vss_mag_ammo/Magazine_939_10_Empty.blend'),
    ('Magazine_939_10_Loaded', '03_Магазины/02_Снаряжённый', 'Магазин_снаряжённый', RAW/'vss_mag_ammo/Magazine_939_10_Loaded.blend'),
    ('Cartridge_939_SP5', '04_Патрон_СП5', 'Патрон_СП5', RAW/'vss_mag_ammo/Cartridge_939_SP5.blend'),
)


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256')
    return digest.hexdigest()


def make_plan(destination: Path) -> dict:
    # Поставленный ранее manifest защищает от случайной смеси старых и новых карт.
    delivered = json.loads((KIT/'delivery-manifest.json').read_text(encoding='utf8'))
    for entry in delivered['files']:
        if sha(KIT/entry['path']) != entry['sha256']:
            raise ValueError('Изменился проверенный исходник: '+entry['path'])
    files: list[dict] = []

    def add(source: Path, relative: str, kind: str) -> None:
        if not source.is_file() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Недопустимый исходник: '+str(source))
        target = Path(relative)
        if target.is_absolute() or '..' in target.parts:
            raise ValueError('Недопустимый путь поставки')
        files.append({'source': str(source), 'path': target.as_posix(), 'kind': kind,
                      'bytes': source.stat().st_size, 'sha256': sha(source)})

    add(KIT/'VSS_Textured_Kit.blend', '01_Blender/00_Весь_комплект.blend', 'current_blend')
    add(KIT/'VSS_Vintorez_Picatinny/VSS_Vintorez_Picatinny_Textured_Editable.blend',
        '01_Blender/01_ВСС/ВСС_Редактируемая_с_текстурами_v3.blend', 'current_blend')
    assets = []
    for identifier, subdir, label, native in ITEMS:
        folder = KIT/identifier
        report = json.loads((folder/'texturing-report.json').read_text(encoding='utf8'))
        if report['status'] != 'PASS' or sha(folder/(identifier+'.glb')) != report['glb_sha256']:
            raise ValueError('Ассет не проверен: '+identifier)
        blend = '01_Blender/'+subdir+'/'+label+'_С_текстурами_игровая_сетка.blend'
        native_target = '01_Blender/'+subdir+'/'+label+'_Исходник_геометрии.blend'
        glb = '02_Для_игры_GLB/'+subdir+'/'+identifier+'.glb'
        add(folder/(identifier+'_Textured.blend'), blend, 'current_blend')
        add(native, native_target, 'current_blend')
        add(folder/(identifier+'.glb'), glb, 'game_glb')
        atlas_targets = []
        for atlas in report['atlas_objects']:
            atlas_label = {'Metal_Polymer': '01_Металл_и_полимер', 'Wood': '02_Дерево', 'Body': 'Материал'}[atlas]
            prefix = '03_Текстуры_и_Krita/'+subdir+'/'+atlas_label
            add(folder/atlas/'Textures.kra', prefix+'/'+label+'_Текстуры.kra', 'krita')
            for map_name in ('basecolor', 'orm', 'normal'):
                add(folder/atlas/(map_name+'.png'), prefix+'/'+map_name+'.png', 'texture_png')
            for guide in ('UV_Guide.png', 'Material_IDs.png'):
                if (folder/atlas/guide).is_file():
                    add(folder/atlas/guide, prefix+'/Направляющие/'+guide, 'uv_guide')
            atlas_targets.append(prefix)
        # Только финальные виды; диагностические и устаревшие кандидаты остаются в сырье.
        for preview in sorted(folder.glob('textured_*.png')):
            add(preview, '04_Превью/'+subdir+'/'+preview.name, 'preview')
        assets.append({'id': identifier, 'name': label, 'blend': blend, 'geometry': native_target,
                       'glb': glb, 'texture_folders': atlas_targets, 'triangles': report['triangles']})
    rifle = KIT/'VSS_Vintorez_Picatinny'
    for preview in sorted(rifle.glob('editable_reopened_*.png')):
        add(preview, '04_Превью/01_ВСС/'+preview.name, 'preview')
    for name in ('kit_all.png', 'kit_rifle.png', 'kit_optics.png', 'kit_mag_ammo.png', 'godot_materials.png'):
        add(KIT/name, '04_Превью/00_Общий_вид/'+name, 'preview')
    for group, label in (('vss_picatinny', '01_ВСС'), ('vss_optics', '02_ПСО'), ('vss_mag_ammo', '03_Патрон')):
        for ref in sorted((RAW/group/'references').glob('*')):
            if ref.is_file(): add(ref, '05_Референсы/'+label+'/'+ref.name, 'reference')
    add(RAW/'vss_stock_v3/user_stock_before.jpg', '05_Референсы/01_ВСС/Приклад_до_исправления.jpg', 'reference')
    for group in ('vss_textured', 'vss_picatinny', 'vss_optics', 'vss_mag_ammo'):
        add(RAW/group/'license.txt', '06_Документы/Лицензии/'+group+'.txt', 'license')
        add(RAW/group/'asset-state.md', '06_Документы/Состояние_в_исходном_проекте/'+group+'.md', 'source_notes')
    add(KIT/'README.md', '06_Документы/Описание_исходного_текстурного_комплекта.md', 'source_notes')
    add(KIT/'delivery-manifest.json', '06_Документы/Проверки/manifest_исходной_поставки.json', 'audit')
    for entry in delivered['files']:
        if entry['path'].endswith('.json'):
            add(KIT/entry['path'], '06_Документы/Проверки/'+entry['path'], 'audit')
    portability = KIT/'library-blend-check.json'
    if portability.exists():
        check = json.loads(portability.read_text(encoding='utf8'))
        if check['status'] == 'PASS' and Path(check['destination']).resolve() == destination.resolve():
            add(portability, '06_Документы/Проверки/Автономность_Blender.json', 'audit')
    current_native = {row[3].resolve() for row in ITEMS}
    for group in ('vss_picatinny', 'vss_optics', 'vss_mag_ammo'):
        for native in sorted((RAW/group).glob('*.blend')):
            if native.resolve() not in current_native and '_clay' not in native.stem:
                add(native, '07_Архивы/История_сцен/'+group+'/'+native.name, 'previous_blend')
    add(KIT/'VSS_Textured_Kit.zip', '07_Архивы/ВСС_Актуальный_комплект_2026-10-01.zip', 'current_archive')
    add(RAW/'vss_stock_v3/Before_Shoulder_Correction.zip',
        '07_Архивы/ВСС_Комплект_до_исправления_приклада.zip', 'previous_archive')
    if len({f['path'] for f in files}) != len(files): raise ValueError('Дубли путей')
    return {'destination': str(destination.resolve()), 'assets': assets, 'files': files}


def guide(plan: dict) -> str:
    lines = [
        'ВСС ВИНТОРЕЗ — ПОЛНЫЙ КОМПЛЕКТ',
        'Актуальная версия: 01.10.2026, исправленный вогнутый приклад и прилегающий затыльник.',
        '', 'С ЧЕГО НАЧАТЬ',
        'Посмотреть все предметы: 01_Blender\\00_Весь_комплект.blend',
        'Править ВСС по отдельным деталям: 01_Blender\\01_ВСС\\ВСС_Редактируемая_с_текстурами_v3.blend',
        'Здесь 161 именованная деталь. Текстуры уже упакованы в модели Blender.',
        '', 'ЧТО В КАКОЙ ПАПКЕ',
        '01_Blender — общий просмотр и отдельные модели каждого предмета.',
        '02_Для_игры_GLB — шесть готовых GLB со встроенными материалами и картами.',
        '03_Текстуры_и_Krita — слоистые KRA, готовые PNG и направляющие каждого предмета.',
        '04_Превью — финальные изображения и крупные планы исправленного приклада.',
        '05_Референсы — фотографии для сверки внешней формы.',
        '06_Документы — лицензии, проверки и описание исходного комплекта.',
        '07_Архивы — предыдущие сцены и резервные ZIP; для текущей работы используйте 01–03.',
        '', 'КАКОЙ BLENDER-ФАЙЛ ВЫБРАТЬ',
        '* Редактируемая_с_текстурами_v3 — основная ВСС с отдельными деталями и картами Krita.',
        '* С_текстурами_игровая_сетка — готовая текстурная сетка соответствующего предмета.',
        '* Исходник_геометрии — отдельные детали с базовыми материалами для правки формы.',
        '  У прицелов, магазинов и патрона это исходник до финального текстурирования в Krita.',
        '* 00_Весь_комплект — сцена для осмотра; предметы разложены для показа.',
        '', 'ПРЕДМЕТЫ В КОМПЛЕКТЕ',
    ]
    for asset in plan['assets']:
        lines.extend([asset['name']+' — '+str(asset['triangles'])+' треугольников',
                      '  Blender: '+asset['blend'].replace('/', '\\'),
                      '  Для игры: '+asset['glb'].replace('/', '\\'),
                      '  Текстуры: '+', '.join(p.replace('/', '\\') for p in asset['texture_folders'])])
    lines.extend([
        '', 'ТЕКСТУРЫ',
        'ВСС: два атласа 4096×4096 — металл/полимер и дерево.',
        'Прицелы, оба магазина и СП-5: по одному атласу 2048×2048.',
        'basecolor.png — цвет; orm.png — R: AO, G: шероховатость, B: металличность;',
        'normal.png — нормали OpenGL (+Y). ORM/Normal использовать как Non-Color.',
        'В KRA группы Base Color, ORM, Normal и Guides. Для экспорта показывать одну группу;',
        'Guides оставлять скрытой. Итоговые PNG лежат рядом с KRA.',
        '', 'ДЛЯ ИГРЫ',
        'Отдельные GLB/игровые сетки: метры, +Z вперёд, +Y вверх, -X правая сторона.',
        'Исходные отдельные детали ВСС: +X вперёд, +Z вверх, -Y правая сторона.',
        'ВСС без установленной оптики; оба прицела — самостоятельные предметы.',
        'Пустой магазин показывает подаватель, снаряжённый — два верхних патрона.',
        'Скрытые восемь патронов и внутренний механизм не моделировались.',
        'К базе предметов, ADS и анимациям перезарядки ассеты пока не подключены.',
        '', 'О ПРОВЕРКАХ И ВЕРСИЯХ',
        'Модели и карты проверены в Blender, Krita и Godot 4.5.1 до передачи.',
        'Размеры и детали восстановлены по фото; изгиб приклада — художественная оценка.',
        'Список_файлов.json содержит пути и контрольные суммы копий в этой папке.',
        'Технические документы из проекта сохраняют исходные названия и пути проекта;',
        'для работы здесь ориентируйтесь на эту памятку и пронумерованные папки.',
        'Все исходники в проекте RING также сохранены.',
    ])
    return '\n'.join(lines)+'\n'


def copy_plan(plan: dict) -> dict:
    destination = Path(plan['destination']).resolve()
    allowed = Path('E:/Models Blender').resolve()
    if destination == allowed or not destination.is_relative_to(allowed):
        raise ValueError('Поставка должна быть подпапкой E:/Models Blender')
    # Существующие отличающиеся файлы не перезаписываются.
    for entry in plan['files']:
        source = Path(entry['source'])
        target = (destination/entry['path']).resolve()
        if not target.is_relative_to(destination): raise ValueError('Выход за пределы папки')
        if sha(source) != entry['sha256']: raise ValueError('Исходник изменился после подготовки')
        if target.exists() and (not target.is_file() or sha(target) != entry['sha256']):
            raise FileExistsError('В папке уже есть другая версия: '+str(target))
    text = guide(plan)
    guide_path = destination/'00_НАЧНИ_ЗДЕСЬ.txt'
    if guide_path.exists() and guide_path.read_text(encoding='utf-8-sig') != text:
        raise FileExistsError('В папке уже есть другая памятка: '+str(guide_path))
    destination.mkdir(parents=True, exist_ok=True)
    for entry in plan['files']:
        target = destination/entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists(): shutil.copy2(entry['source'], target)
        if sha(target) != entry['sha256']: raise ValueError('Копия не совпадает: '+str(target))
    guide_path.write_text(text, encoding='utf-8-sig')
    public = {'status': 'PASS', 'assets': plan['assets'],
              'files': [{k:v for k,v in entry.items() if k!='source'} for entry in plan['files']]}
    (destination/'Список_файлов.json').write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding='utf8')
    result = {'status': 'PASS', 'destination': str(destination), 'files_copied': len(plan['files']),
              'assets': len(plan['assets']), 'bytes': sum(e['bytes'] for e in plan['files']),
              'copies_verified_sha256': True}
    (KIT/'library-copy-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--copy', action='store_true')
    parser.add_argument('--destination', type=Path, default=DEFAULT_DEST)
    args = parser.parse_args()
    if args.copy:
        print(json.dumps(copy_plan(json.loads(PLAN.read_text(encoding='utf8'))), ensure_ascii=False))
    else:
        plan = make_plan(args.destination)
        PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({'status': 'PLAN_READY', 'files': len(plan['files']), 'assets': len(plan['assets']),
                          'destination': plan['destination'], 'bytes': sum(f['bytes'] for f in plan['files'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
