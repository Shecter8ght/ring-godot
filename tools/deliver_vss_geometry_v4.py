"""Передача утверждаемой геометрии ВСС в отдельный раздел пользовательской библиотеки."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_geometry_v4'
LIBRARY=Path('E:/Models Blender/ВСС Винторез — полный комплект')
REVIEW='08_На_согласование_геометрия_v4'


def digest(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,default=LIBRARY)
    args=parser.parse_args();library=args.destination.resolve();destination=library/REVIEW
    audit=json.loads((RAW/'geometry-audit.json').read_text(encoding='utf8'))
    build=json.loads((RAW/'build-report.json').read_text(encoding='utf8'))
    assert audit['status']=='PASS' and audit['saved_files_reopened']==8
    assert build['source_unchanged'] and digest(Path(build['source']))==build['source_sha256']
    destination.mkdir(parents=True,exist_ok=True)
    entries=[]

    def copy(source: Path,relative: str) -> None:
        target=destination/relative
        assert target.resolve().is_relative_to(destination.resolve()),target
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and digest(target)!=digest(source):
            raise RuntimeError('Different review file already exists: '+str(target))
        if not target.exists():shutil.copy2(source,target)
        assert digest(source)==digest(target)
        entries.append({'path':relative,'source':str(source),'bytes':target.stat().st_size,'sha256':digest(target)})

    copy(RAW/'VSS_and_Magazines_10_20_30.blend','00_ВСС_и_магазины_10_20_30.blend')
    copy(RAW/'VSS_Geometry_v4.blend','01_ВСС_Геометрия_v4.blend')
    for capacity in (10,20,30):
        for state,label in (('Empty','Пустой'),('Loaded','Снаряжённый')):
            identifier=f'Magazine_939_{capacity}_{state}'
            folder=RAW/'Магазины'/identifier
            source=folder/(identifier+'.blend')
            checked=next(row for row in audit['magazines'] if row['id']==identifier)
            assert digest(source)==checked['sha256'],identifier
            copy(source,f'Магазины/{capacity}_патронов/{label}.blend')
            for preview in folder.glob('v4_*.png'):
                copy(preview,f'Превью/Магазины/{capacity}_патронов/{label}/{preview.name}')
    for preview in RAW.glob('v4_*.png'):copy(preview,'Превью/'+preview.name)
    for reference in sorted((RAW/'Референсы').glob('*')):
        if reference.is_file():copy(reference,'Референсы/'+reference.name)
    for name in ('asset-state.md','geometry-audit.json','build-report.json'):
        copy(RAW/name,'Документы/'+name)
    readme='''ВСС ВИНТОРЕЗ — ГЕОМЕТРИЯ v4 ДЛЯ ПРОСМОТРА
Дата: 01.10.2026

ОТКРОЙТЕ СНАЧАЛА
00_ВСС_и_магазины_10_20_30.blend — винтовка и шесть самостоятельных магазинов.
Сверху винтовка, ниже ряд EMPTY (пустые), внизу LOADED (снаряжённые).
В каждом ряду слева направо: 10, 20, 30 патронов.
01_ВСС_Геометрия_v4.blend — винтовка по именованным деталям;
при открытии показан крупный план нового предохранителя.

ОТДЕЛЬНЫЕ АССЕТЫ
Магазины\\10_патронов\\Пустой.blend / Снаряжённый.blend
Магазины\\20_патронов\\Пустой.blend / Снаряжённый.blend
Магазины\\30_патронов\\Пустой.blend / Снаряжённый.blend
Origin каждого магазина — прежнее место посадки на ВСС.
Снаряжённый верх содержит два видимых патрона и опущенный подаватель;
скрытые внутренние стопки не моделировались.

ЧТО ИЗМЕНЕНО
Подогнаны дерево/коробка, добавлена округлая нижняя проушина крепления.
У рукояти увеличено скругление; убраны шипы у спусковой скобы.
Предохранитель переделан по четырём уточняющим крупным планам:
угловой силуэт, объёмное штампованное ребро, отогнутый передний язычок.
Все магазины имеют плавную оболочку и рёбра, следующие её изгибу.
Ранее исправленный вогнутый затыльник сохранён.

ПРОСМОТР В BLENDER
Файлы сохранены с камерой и простыми цветными материалами для оценки формы.
Numpad 0 — выйти из камеры/вернуться; вращение — средняя кнопка мыши.
В Outliner есть Camera_V4_Join_Right/Left, Camera_V4_Grip и камеры предохранителя.
Превью — свежие рендеры обеих сторон, рукояти, предохранителя и магазинов.

ЭТАП
Это проверка геометрии. Новые текстуры, UV/baking, Krita и игровые экспорты
в этой версии не выполнялись. Предыдущий текстурированный комплект v3
остаётся в папках 01–07 основной библиотеки.
Длина/профиль дополнительных магазинов оценены художественно.
Для 30-местного варианта точного пользовательского фото нет: это
удлинённая вариация с тем же верхом, а не проверенная серийная модификация.

ПРОВЕРКИ
8 сохранённых Blender-файлов повторно открыты.
35 точек стыка дерева/коробки, 15 точек прилегания затыльника,
9 лучей окон и по 5 лучей оболочки горловины каждого магазина.
Закрытая геометрия основных исправленных деталей без нулевых граней.
Документы\\geometry-audit.json содержит реальные результаты и габариты.
'''
    (destination/'НАЧНИ_ЗДЕСЬ.txt').write_text(readme,encoding='utf8')
    marker='НОВЫЕ ПРАВКИ ГЕОМЕТРИИ — v4 (01.10.2026)'
    main_guide=library/'00_НАЧНИ_ЗДЕСЬ.txt'
    if main_guide.exists():
        previous=main_guide.read_text(encoding='utf-8-sig')
        if not previous.startswith(marker):
            (destination/'Документы/Памятка_предыдущей_поставки_v3.txt').write_text(previous,encoding='utf8')
            main_guide.write_text(marker+'\nОткройте '+REVIEW+'\\00_ВСС_и_магазины_10_20_30.blend\n'
                'Там исправленный стык, рукоять, предохранитель и магазины 10/20/30.\n'
                'Эта версия пока без текстурирования и игровых экспортов.\n'
                'Подробная памятка — '+REVIEW+'\\НАЧНИ_ЗДЕСЬ.txt\n\n'
                'ПРЕДЫДУЩИЙ ТЕКСТУРИРОВАННЫЙ КОМПЛЕКТ v3:\n'+previous,encoding='utf8')
    report={'status':'PASS','destination':str(destination),'copied_files':len(entries),
            'blend_files':sum(row['path'].endswith('.blend') for row in entries),
            'bytes':sum(row['bytes'] for row in entries),'files':entries}
    (RAW/'library-copy-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (destination/'Документы/Список_файлов.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:report[k] for k in ('status','destination','copied_files','blend_files','bytes')},ensure_ascii=False))


if __name__=='__main__':main()
