"""Реестр источников и проверенная выдача исправлений, без изменения партии v01."""
from pathlib import Path
import argparse,hashlib,json,shutil
from PIL import Image

PROJECT=Path(__file__).resolve().parents[3]
ROOT=PROJECT/'_asset_src/urban_realrefs_v02'
DELIVERY=Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references')
SELECTION={
 'atm':{'ref_01.jpg','ref_02.pdf'},
 'dumpster':{'ref_02.jpeg','ref_03.jpeg'},
 'car_official':{'ref_01.jpg','ref_04.jpg','ref_05.jpg'},
 'kiosk':{'ref_08.jpg'},
 'fence':{'ref_01.jpg','ref_02.jpg','ref_03.jpg'},
 'fence_foot':{'ref_01.png'},
 'fence_install':{'ref_01.jpg'},
 'building_user':{'ref_01.jpg','ref_02.jpg','ref_03.jpg'},
}
NAMES={'fence':'Высокий секционный бетонный забор','atm':'Банкомат','dumpster':'Большой мусорный бункер','car':'Статичный трёхдверный хэтчбек','kiosk':'Ларёк с фастфудом','building':'Двухэтажный корпус по фотографиям владельца'}

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare():
    reports=[]
    for key in ('fence','dumpster','atm','car','kiosk','building'):
        folder=next((ROOT/'assets').glob('R??_'+key))
        report=json.loads((folder/'checks/geometry.json').read_text(encoding='utf-8'))
        model=next((folder/'model').glob('*.blend'))
        assert report['saved_file_reopened'] and sha(model)==report['blend_sha256'],model
        assert report['zero_area_faces']==report['nonmanifold_edges']==report['loose_vertices']==0,(key,report['part_flags'])
        unexpected=[f for f in report['part_flags'] if f['boundary'] and f['type']!='FONT']
        assert not unexpected,(key,unexpected)
        for name in ('front34','rear34','front','right'):
            with Image.open(folder/'previews'/(name+'.png')) as im: im.verify()
        report.update(name=NAMES[key],model=model.relative_to(ROOT).as_posix(),folder=folder.relative_to(ROOT).as_posix())
        reports.append(report)
    references=[]
    for record_path in sorted((ROOT/'references').glob('*/*.source.json')):
        data=json.loads(record_path.read_text(encoding='utf-8'))
        path=record_path.parent/data['file']
        assert sha(path)==data['sha256'],path
        data['relative_path']=path.relative_to(ROOT).as_posix()
        data['used_for_model']=path.name in SELECTION.get(path.parent.name,set())
        data['disposition']='chosen reference' if data['used_for_model'] else 'research only; another product variant'
        references.append(data)
    manifest=dict(version='v02_real_references',date='2026-10-24',assets=reports,references=references,
        fence=dict(status='type_confirmed_by_owner',type='Высокий секционный бетонный забор',model_generated=True),
        geometry_approved=False,production_uv=False,production_textures=False,game_export=False)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Сохранённые интернет-референсы, 2026-10-24','',
        'Фото служат для построения собственной геометрии. Это не игровые текстуры и не лицензия на их распространение в игре.',
        'Водяные знаки исходников сохранены. У каждого файла есть соседний `.source.json` с URL, датой и SHA-256.','',
        '## Выбранные прототипы','',
        '- Бункер: РостМеталл 1408, БН 8 м³, открытый вариант. В работе реальные фото 02/03 одного изделия.',
        '- Банкомат: NCR SelfServ 22e CEN I front access. Фото 01 и таблица производителя на странице 2 PDF. Не смешан с задним доступом.',
        '- Машина: синий стандартный трёхдверный Golf V. Основные ракурсы 01/04, интерьер 05. Серебристый пятидверный и красный GT из этой же подборки не задают кузов.',
        '- Ларёк: киоск «Хот-Дог», фото 08 Mobifood. Фотографии других киосков оставлены как история исследования.',
        '- Забор: владелец выбрал высокий секционный. Лицевая схема ПО-2М, реальные задние виды 02/03, отдельные изображение стакана и фото монтажа. Глубины и сечение гнезда оценочные.',
        '- Дополнительное здание: три фотографии владельца, сохранённые без изменения пикселей. По ним построены лицевой фасад и основные повреждения.','',
        '## Подтверждённые и оценочные размеры','',
        '- NCR: 1412 × 450 × 784 мм в заводской таблице для front access. Измеренный размер модели больше по глубине из-за внешних элементов.',
        '- Бункер: 3300 × 1900 × 1420 мм в карточке. Выбран лист 3 мм из перечисленных вариантов. Захваты и усиления увеличивают полный измеренный габарит.',
        '- VW: заводская страница семейства даёт базу 2578 мм, длину 4204–4246 мм, ширину 1759 мм, высоту 1465–1651 мм. Здесь выбраны 4204 и высота 1485 мм; точная высота комплектации по фото не подтверждена. Габарит аудита включает зеркала, антенну и номера.',
        '- Mobifood: конструктивный принцип подтверждён фото; общий габарит и невидимая планировка оценочные. Служебный проём выбран 1,17 × 2,42 м под масштаб E проекта.',
        '- ПО-2М: выбрана панель 2500 × 3000 × 160 мм. Ориентация высоты 3000 мм дополнительно сверена по заводской статье монтажа. Стаканы 950 × 750 × 550 мм длинной стороной поперёк линии ограждения; шаг секций 2500 мм. Полный габарит включает стаканы и монтажные петли.',
        '- Здание: проектная оценка корпуса 34,8 × 10,5 × 6,65 м. Точного обмера нет; боковые/задняя стороны и внутренние перегородки реконструированы. Дверные проёмы выбраны 1,82 × 2,42 м под масштаб E. В измеренный габарит входят отливы, козырьки и кровельные элементы.',
        '- Толщины скрытых креплений, внутреннее устройство банкомата, днище машины и оснащение киоска реконструированы. Набор не является инженерными чертежами.','',
        '## Файлы','', '| Файл | Применение | Страница | Прямой URL |','|---|---|---|---|']
    for r in references:
        role='По нему строилась форма' if r['used_for_model'] else 'Исследование / не выбран'
        if r.get('origin')=='user_attachment':
            lines.append(f"| [{r['relative_path']}]({r['relative_path']}) | {role} | Фотография владельца в этом чате | Оригинал скопирован без изменений |")
        else:
            lines.append(f"| [{r['relative_path']}]({r['relative_path']}) | {role} | [источник]({r['source_page']}) | [файл]({r['url']}) |")
    lines+=['','Wikimedia не использовалась: загрузки двух оригиналов вернули HTTP 429. Достаточные ракурсы автомобиля получены из официальной коллекции VW.',
            'PNG datasheet-1/2 — локально отрендеренные страницы сохранённого NCR PDF; первичным источником является PDF, а не эти PNG.','']
    (ROOT/'references.md').write_text('\n'.join(lines),encoding='utf-8')
    readme=['# Исправления по реальным фотографиям — v02','',
        'Готовы пять переделанных предметов и дополнительное двухэтажное здание по фотографиям владельца — шесть самостоятельных кандидатов геометрии. Их можно открыть в Blender 5.2.2. Старые 95 файлов v01 сохранены.',
        'Тип забора выбран владельцем: высокий секционный бетонный, ПО-2М с фартуком и фундаментами ФО-2.','',
        '| Модель | Открыть в Blender | Нейтральный вид |','|---|---|---|']
    for r in reports:
        readme.append(f"| {r['name']} | [.blend]({r['model']}) | [спереди]({r['folder']}/previews/front34.png), [сзади]({r['folder']}/previews/rear34.png) |")
    readme+=['','Фотографии, заводской PDF и таблица происхождения: [references.md](references.md).',
        'У каждого предмета — `asset-state.md`, четыре основных вида и `checks/geometry.json`. Коллекция MODEL содержит редактируемые детали; STUDIO и REFERENCES исключаются из игрового экспорта.',
        'Машина — неподвижное окружение: кузов, закрытая пятая дверь, салон, колёса и оптика. Риг, вождение и анимация открывания не сделаны.',
        'REVIEW-материалы нейтральные, только для оценки формы. Производственные UV, UCUPaint/PBR, игровая сетка, LOD, коллизии и импорт в Godot не выполнены. Форма ещё не принята владельцем.',
        'Все шесть .blend сохранены и повторно открыты. Нет нулевых граней, свободных вершин и рёбер с более чем двумя гранями. Открытые контуры FONT на вывесках учтены отдельно; это не разрывы оболочек.',
        'У здания дополнительно есть крупные виды damage_close, entry_close и plaster_close: отслоения до кирпича, трещины, деформированная штукатурка и вход. Фактура и цвет со снимков ещё не перенесены в PBR: сначала владелец принимает показанную геометрию.',
        'Автоматическая проверка не подтверждает точное сходство с фото. Оценочные и скрытые детали перечислены в карточках предметов и реестре источников.',
        'Все позиции независимы, координаты — метры, Z вверх, лицевой вид -Y, origin в центре основания. Производственные игровые материалы из исходной игры не извлекались.','',
        'Исходный генератор в проекте: `tools/urban_screens/v02/build.py -- --only fence,atm,dumpster,kiosk,car,building` через Blender; `inspect_views.py` и `building_views.py` создают дополнительные Cycles-виды без перезаписи модели.',
        'Копия собственных скриптов — `source/urban_screens/`. Большие .blend и фотографии хранятся локально; в git — рецепты и документация.','']
    (ROOT/'README.md').write_text('\n'.join(readme),encoding='utf-8')
    return manifest

def deliver():
    manifest=prepare()
    DELIVERY.mkdir(parents=True,exist_ok=True)
    for name in ('assets','references'):
        shutil.copytree(ROOT/name,DELIVERY/name,dirs_exist_ok=True)
    for name in ('manifest.json','README.md','references.md'):
        shutil.copy2(ROOT/name,DELIVERY/name)
    target=DELIVERY/'source/urban_screens'
    target.mkdir(parents=True,exist_ok=True)
    for source in sorted((PROJECT/'tools/urban_screens').glob('*.py')):
        shutil.copy2(source,target/source.name)
    shutil.copytree(PROJECT/'tools/urban_screens/v02',target/'v02',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    checked=[]
    for r in manifest['assets']:
        assert sha(DELIVERY/r['model'])==r['blend_sha256']
        checked.append(r['model'])
    for r in manifest['references']: assert sha(DELIVERY/r['relative_path'])==r['sha256']
    verification=dict(models_checked=checked,reference_files_checked=len(manifest['references']),
        v01_preserved=True,status='copied and hashes verified',destination=str(DELIVERY))
    (DELIVERY/'delivery-check.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(verification,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--deliver',action='store_true')
    args=parser.parse_args()
    if args.deliver: deliver()
    else:
        m=prepare(); print('PACKAGE_READY',len(m['assets']),'models',len(m['references']),'reference sources; geometry review')
