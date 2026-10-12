"""Package the corrected geometry separately from superseded paint experiments."""
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex'
VERSION=os.environ.get('GRENADE_GEOMETRY_VERSION','v05')
STAGE=OUT/f'geometry_review_{VERSION}'
TARGET=Path(f'E:/Models Blender/From Scenario/Grenade/Codex_Geometry_{VERSION}')
BLEND=f'Grenade_MkII_geometry_review_{VERSION}.blend'
SOURCE=Path('E:/Models Blender/From Scenario/Grenade/Grenade.blend')
SOURCE_SHA='8da97241329e0cd5907570db46ab685e7623beec50114a959d2c321749db5cc9'
VIEWS=[('overall','Общий вид'),('front','Головка и загиб рычага'),
       ('side','Боковой контур'),('top','Вид сверху'),('reverse','Обратная сторона'),
       ('pin_separate','Чека отдельно, рычаг удержан'),('lever_outward','Рычаг отведён')]
if VERSION=='v05':
    VIEWS.extend([('split_tips','Раздвоенные концы и сквозное отверстие'),
                  ('tips_compressed','Концы сходятся при начале тяги'),
                  ('pin_outside','Чека снаружи — концы снова раздельны')])


def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()


def put(source,relative):
    dest=STAGE/relative
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,dest)


def package():
    audit=json.loads((OUT/f'checks/geometry_delivery_audit_{VERSION}.json').read_text(encoding='utf8'))
    assert audit['pass'] and audit['closed_clearance']['body_lever_intersecting_face_pairs']==0
    assert digest(SOURCE)==SOURCE_SHA
    assert digest(OUT/BLEND)==audit['sha256']
    STAGE.mkdir(parents=True,exist_ok=True)
    put(OUT/BLEND,BLEND)
    for name,_ in VIEWS:
        put(OUT/f'previews/geometry_{VERSION}_{name}.png',f'previews/{name}.png')
    for name in ['front','side','top']:
        put(OUT/f'previews/geometry_before_{name}.png',f'previews/before_{name}.png')
    for name in [f'geometry_review_{VERSION}.json',f'geometry_delivery_audit_{VERSION}.json']:
        put(OUT/'checks'/name,'checks/'+name)
    if VERSION=='v05':
        put(OUT/'previews/pin_split_motion_v05.mp4','previews/pin_split_motion.mp4')
    put(OUT/'source_inspection.json','checks/source_inspection.json')
    put(OUT/'references/owner_latest/СЛНШК_маркировка.svg','marking/СЛНШК_маркировка.svg')
    for folder in ['owner','owner_latest']:
        for file in sorted((OUT/'references'/folder).rglob('*')):
            if file.is_file():
                put(file,'references/'+file.relative_to(OUT/'references').as_posix())
    x,y,z=audit['closed_dimensions_mm']
    dims=f'{x:.1f} × {y:.1f} × {z:.1f}'.replace('.',',')
    review=json.loads((OUT/f'checks/geometry_review_{VERSION}.json').read_text(encoding='utf8'))
    head=review.get('head_topology',review.get('meshes',{}).get('FuzeCasting',{}))
    head_vertices=f"{head.get('vertices',248710):,}".replace(',',' ')
    pin_notes='''В v05 исправлена чека по уточнению владельца: круглая проволока с двумя раздельными
концами. В начале тяги они сходятся, затем чека выходит; снаружи снова расходятся.
В головке сделан настоящий сквозной вырез с округлённой кромкой на обеих сторонах.
Остальные пять mesh совпадают с сохранённой v04. Короткий ролик —
`previews/pin_split_motion.mp4`, замедленный просмотр кадров 1–30 при 12 fps.
Рельеф кончиков редактируется в Shape Key `SplitTips_Compress`, связанном с `pin_pull`.
Движение визуальное: физическое усилие не рассчитывается.
''' if VERSION=='v05' else ''
    readme=f'''# Граната — проверка исправленной геометрии {VERSION}

Откройте `{BLEND}` в Blender. Виды — `gallery.html` и `previews/`.
Версия подготовлена для согласования формы; нейтральный металл служит для проверки геометрии.

Габарит закрытой сборки: **{dims} мм**. Корпус: **Ø63,4 мм**, высота 86 мм.
Сцена: 1 единица = 1 метр, отображение в миллиметрах. Масштаб не увеличивался.

Пересобраны цельная наружная головка и непрерывный листовой рычаг с загнутым крюком.
Удалены отдельная боковая пластина и шесть условных заклёпок прежней головки.
Кольцо увеличено, у проволоки видны раздельные концы. На верхней горловине добавлены
восемь плавных канавок. Нижняя часть исходного корпуса сохранена.
Пересечение рычага с плечом корпуса устранено; проверка треугольников — 0 пересечений.

{pin_notes}

Движение: таймлайн 1–96, 24 кадра/с. Кадр 1 — собрана; 30 — чека отдельно;
59 — рычаг отведён. `CTRL_Grenade` содержит `pin_pull` и `lever_open`, диапазон 0–1.
Для ручных ползунков отвяжите `DEMO_PinAndLever_VisualOnly` от корня в Action Editor
кнопкой X рядом с Action. Чека и кольцо двигаются вместе. Это внешняя художественная анимация.

Маркировка следующего текстурного прохода: простое солнышко и **СЛНШК** в тёмном цвете
вместо обеих английских строк. Эскиз — `marking/СЛНШК_маркировка.svg`.
На модель он ещё не нанесён. После согласования формы — нативные слои UCUPaint,
резкие раковины и зерно металла, износ краски и кромок, потёртая жёлтая полоса,
раздельные цвет, металлическость, шероховатость и рельеф.

Исходный `Grenade.blend` сохранён, SHA-256 проверен. Предыдущий текстурный опыт v02
не является финальной версией и не входит в эту выдачу. Подробности — `asset-state.md`.
'''
    (STAGE/'00_НАЧНИ_ЗДЕСЬ.md').write_text(readme,encoding='utf8')
    state=f'''# Состояние ассета — геометрия {VERSION}

Дата: 2026-10-12. Статус: **awaiting_geometry_approval**.
Владелец ещё не одобрял эту конкретную исправленную форму.

Источник: `{SOURCE.as_posix()}`. SHA-256: `{SOURCE_SHA}`.
Кандидат: `{BLEND}`. SHA-256: `{audit['sha256']}`.
Blender 5.2.2 LTS. Сохраняемые исходники и промежуточные материалы —
`E:/Games/RING-godot/_asset_src/grenade_codex/`.

Габарит закрытого предмета: {dims} мм. Исходник был высотой 114,7 мм и с тем же
диаметром корпуса 63,4 мм. Новый верхний загиб немного изменил общую высоту.
Это модель ручного размера; маленький вид в сцене сам по себе не требует увеличения.

Новая головка: один замкнутый mesh с округлёнными переходами внешнего контура.
Основа {head_vertices} вершин; редактируемый Subdivision уровня 1. Отдельные условные накладки
и заклёпки удалены. Новый замкнутый рычаг имеет непрерывное сечение с округлёнными
кромками. Кольцо и ушко остаются отдельными и сохраняют управление в группе чеки.
У верхней горловины изменены 3360 вершин, максимальная глубина канавок 0,563 мм.
Топология и исходная UVMap корпуса сохранены. Нижние вершины корпуса не изменены.

{pin_notes}

У новой головки/рычага/кольца нет открытых или неманифолдных рёбер.
У старого корпуса на временной сваренной копии остаются 104 граничных ребра
в скрытом отверстии горловины: это сохранённая особенность исходника.
У импортированных прочих деталей разрезанные вершины нормалей не считаются дырками:
результаты проверки записаны отдельно в `checks/geometry_review_{VERSION}.json`.
Кандидат открывался заново; проверены все 96 кадров v05, неподвижность головки,
закрытый габарит, 11 встроенных старых изображений и отсутствие пересечения рычага
с корпусом в собранном положении. Старые карты сохранены внутри файла как архив,
но не подключены к нейтральному материалу. Игровая оптимизация и импорт не выполнялись.

Следующий проход текстур должен открыть именно одобренную копию {VERSION} и не пересоздавать
эту геометрию из исходника. Требования: светлая шероховатая головка, отчётливое
мелкое зерно и раковины, локальная ржавчина и полировка, потёртый olive drab,
изношенная жёлтая полоса; солнышко и точная кириллица СЛНШК вместо английского текста.
Прежние размытые материалы v02 требуют нового прохода на принятой форме.

Фото владельца и последние пять скриншотов сохранены в `references/` только для
визуальной сверки. Их пиксели не использованы как текстурные карты. Лицензия на
предоставленные владельцем исходники и сторонние скриншоты не назначалась.
Дополнительно изучены реальные наружные поверхности:
[Inert Ordnance](https://inert-ord.net/usa03a/usa2/index.html),
[IMA](https://www.ima-usa.com/products/original-u-s-wwii-inert-mkii-pineapple-grenade-with-yellow-ring-m10a3-fuze-14).
Исследование касается внешнего вида художественного ассета.
'''
    (STAGE/'asset-state.md').write_text(state,encoding='utf8')
    (STAGE/'variants.json').write_text(json.dumps({'version':f'geometry_{VERSION}',
        'stage':'awaiting_geometry_approval','candidate_sha256':audit['sha256'],
        'new_texturing_status':'pending_approved_geometry',
        'marking_requested':'sun icon + СЛНШК','price':None,'loot':None},
        ensure_ascii=False,indent=2),encoding='utf8')
    cards=''.join(f'<button class="card" data-full="previews/{name}.png"><img loading="lazy" src="previews/{name}.png" alt="{label}"><span>{label}</span></button>' for name,label in VIEWS[1:])
    html='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Граната — геометрия v04</title>
<style>*{box-sizing:border-box}body{margin:0;background:#182127;color:#edf0ed;font:16px/1.6 system-ui,sans-serif}main{max-width:1300px;margin:auto;padding:36px 24px 70px}h1{font-size:clamp(32px,5vw,62px);line-height:1.1;font-weight:600;letter-spacing:-.035em;margin:14px 0 25px}h2{font-size:27px;font-weight:550;margin-top:45px}p{max-width:800px;color:#b7c4c9}a{color:#e9cc8e}.tag{font-size:12px;color:#e9cc8e;letter-spacing:.15em}.hero,.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}img{max-width:100%;display:block;border-radius:8px}.links{display:flex;gap:15px;flex-wrap:wrap;margin:25px 0}.links a{border:1px solid #83714e;border-radius:6px;padding:10px 16px;text-decoration:none}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.card{padding:0;border:1px solid #3d4b53;background:#253038;border-radius:8px;overflow:hidden;color:inherit;font:inherit;text-align:left;cursor:zoom-in}.card span{display:block;padding:15px}.small{font-size:13px}.marking{padding:32px;background:#c7c6ba;display:flex;align-items:center;border-radius:8px}.marking img{width:100%}table{border-collapse:collapse}td,th{text-align:left;padding:10px 22px 10px 0;border-bottom:1px solid #3d4b53;font-weight:400}dialog{background:#182127;border:1px solid #657984;padding:0;border-radius:9px;max-width:95vw;max-height:95vh}dialog::backdrop{background:#000c}dialog img{max-width:93vw;max-height:90vh}dialog button{position:absolute;right:12px;top:12px;background:#19282fed;color:white;border:0;border-radius:6px;padding:10px 16px;font-size:22px;cursor:pointer}@media(max-width:800px){.hero,.pair{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:480px){main{padding:25px 14px}.grid{grid-template-columns:1fr}}</style>
<main><div class="tag">BLENDER · ГЕОМЕТРИЯ V04 · 12.10.2026</div><div class="hero"><div><h1>Цельная головка.<br>Новый контур рычага.</h1><p>Исправленная форма по последним образцам владельца: плавные переходы литья, загнутый крюк, раздельные концы большого кольца и канавки на горловине.</p><p><strong>Подготовлено для согласования геометрии.</strong> Нейтральный материал показывает форму. Новые детальные текстуры будут выполнены после её принятия.</p><div class="links"><a href="BLEND_FILE">Открыть .blend ↗</a><a href="00_НАЧНИ_ЗДЕСЬ.md">Как смотреть и двигать детали</a></div><table><tr><th>Высота</th><td>HEIGHT мм</td></tr><tr><th>Корпус</th><td>Ø63,4 мм</td></tr><tr><th>Габарит</th><td>DIMS мм</td></tr></table><p class="small">Масштаб соответствует ручному предмету. Исходный файл сохранён. Проверка рычага с корпусом: 0 пересечений.</p></div><button class="card" data-full="previews/overall.png"><img src="previews/overall.png" alt="Исправленная геометрия — общий вид"><span>Общий вид · нажмите для увеличения</span></button></div>
<h2>Форма и движение</h2><div class="grid">CARDS</div><p>В Blender: кадр 1 — собрана; 30 — чека отдельно; 59 — рычаг отведён. Таймлайн 1–96. Выберите CTRL_Grenade для свойств pin_pull и lever_open.</p>
<h2>Головка до и после</h2><div class="pair"><div><img src="previews/before_front.png" alt="Прежняя головка — нейтральный материал"><p>До: отдельные пластины, условные заклёпки и неровные стыки.</p></div><div><img src="previews/front.png" alt="Новая цельная головка"><p>v04: цельное литьё и непрерывный листовой рычаг с закруглёнными кромками.</p></div></div>
<h2>Маркировка следующего прохода</h2><div class="pair"><div class="marking"><img src="marking/СЛНШК_маркировка.svg" alt="Тёмное солнышко и аббревиатура СЛНШК"></div><div><p>Обе английские строки заменяются простым солнышком и точной кириллицей <strong>СЛНШК</strong> в том же тёмном цвете. Это отдельный эскиз: на геометрию маркировка пока не нанесена.</p><p>Для поверхности запланированы отчётливые раковины литья, резкое зерно металла, износ краски, полировка на контактах, локальная коррозия и потёртая жёлтая полоса.</p></div></div>
<p class="small"><a href="asset-state.md">Состояние ассета и источники</a> · <a href="checks/geometry_delivery_audit_v04.json">Проверка сохранённого файла</a></p></main><dialog id="full"><button aria-label="Закрыть">×</button><img alt="Геометрия крупно"></dialog><script>const d=document.querySelector('#full');for(const b of document.querySelectorAll('[data-full]'))b.addEventListener('click',()=>{d.querySelector('img').src=b.dataset.full;d.querySelector('img').alt=b.querySelector('img').alt;d.showModal()});d.querySelector('button').addEventListener('click',()=>d.close());d.addEventListener('click',e=>{if(e.target===d)d.close()});</script></html>'''
    html=html.replace('BLEND_FILE',BLEND).replace('HEIGHT',f'{z:.1f}'.replace('.',','))
    html=html.replace('DIMS',dims).replace('CARDS',cards)
    html=html.replace('v04',VERSION).replace('V04',VERSION.upper())
    if VERSION=='v05':
        html=html.replace('<h2>Головка до и после</h2>',
            '<h2>Раздвоенная чека в движении</h2><video controls loop playsinline preload="metadata" style="width:520px;max-width:100%;border-radius:9px" poster="previews/split_tips.png"><source src="previews/pin_split_motion.mp4" type="video/mp4"></video><p>Замедленный просмотр кадров 1–30: кончики сходятся при начале тяги, проходят через реальное отверстие и расходятся снаружи.</p><h2>Головка до и после</h2>')
    (STAGE/'gallery.html').write_text(html,encoding='utf8')
    rows=[{'file':p.relative_to(STAGE).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)}
          for p in sorted(STAGE.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json']
    (STAGE/'delivery_manifest.json').write_text(json.dumps({'destination':str(TARGET),
        'source_sha256':SOURCE_SHA,'stage':'awaiting_geometry_approval','files':rows},
        ensure_ascii=False,indent=2),encoding='utf8')
    verify(STAGE)
    print('GEOMETRY_PACKAGE_OK',len(rows),'files',sum(r['bytes'] for r in rows),'bytes',flush=True)


def verify(path):
    manifest=json.loads((path/'delivery_manifest.json').read_text(encoding='utf8'))
    for row in manifest['files']:
        assert digest(path/row['file'])==row['sha256'],row['file']
    html=(path/'gallery.html').read_text(encoding='utf8')
    links=re.findall(r'(?:href|src|data-full)="([^"]+)"',html)
    for link in links:
        if not link.startswith(('https:','data:','#')):
            assert (path/link).is_file(),link
    print('GEOMETRY_PACKAGE_VERIFIED',path,len(manifest['files']),flush=True)


def copy():
    verify(STAGE)
    manifest=json.loads((STAGE/'delivery_manifest.json').read_text(encoding='utf8'))
    TARGET.mkdir(parents=True,exist_ok=True)
    for relative in [r['file'] for r in manifest['files']]+['delivery_manifest.json']:
        target=TARGET/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(STAGE/relative,target)
    verify(TARGET)
    assert digest(SOURCE)==SOURCE_SHA
    print('GEOMETRY_REVIEW_DELIVERED',TARGET,flush=True)


if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'package'
    if mode=='verify':
        verify(Path(sys.argv[2]) if len(sys.argv)>2 else STAGE)
    else:
        {'package':package,'copy':copy}[mode]()
