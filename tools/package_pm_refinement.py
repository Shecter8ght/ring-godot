"""Offline review gallery, state and a bounded copy manifest for PM v06."""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, html, json, shutil
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont, ImageOps

ap=argparse.ArgumentParser();ap.add_argument('--revision',default='v06',choices=['v06','v07','v08','v09']);args=ap.parse_args()
rev=args.revision;accessory_rev={'v06':'v01','v07':'v02','v08':'v03','v09':'v04'}[rev]
PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/('review_'+rev)
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры')/{'v06':'08_Доработка_v6_на_проверку','v07':'09_Доработка_v7_на_проверку','v08':'10_Доработка_v8_ЗОРИН_на_проверку','v09':'11_Доработка_v9_Гравировка_на_проверку'}[rev]
qa=json.loads((OUT/'Проверки/fresh_file_geometry.json').read_text(encoding='utf-8'))
revision=json.loads((OUT/'Проверки/revision_manifest.json').read_text(encoding='utf-8'))
assert qa['audit_pass']
assert hashlib.sha256((OUT/f'01_ПМ/PM_Geometry_{rev}.blend').read_bytes()).hexdigest()==qa['sha256']
for source,folder in [(ROOT/'references','Референсы'),(ROOT/'surface_sources','Сырьё_для_текстур')]:
    target=OUT/folder;target.mkdir(exist_ok=True)
    for p in source.rglob('*'):
        if p.is_file():
            dest=target/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
scripts=OUT/'Скрипты';scripts.mkdir(exist_ok=True)
for name in ('inspect_pm_refinement.py','fetch_pm_refinement_sources.py','fetch_pm_optic_references.py','fetch_pm_k1_references.py','revise_pm_refinement.py','correct_pm_refinement_v07.py','build_pm_zorin_k1.py','engrave_pm_zorin_k1.py','engrave_pm_kors9.py','clear_pm_windage_markings.py','pm_engraving_geometry.py','review_pm_refinement.py','separate_pm_refinement.py','animate_pm_refinement.py','package_pm_refinement.py','check_pm_refinement_delivery.py','publish_pm_refinement.py'):
    p=PROJECT/'tools'/name
    if p.exists():shutil.copy2(p,scripts/name)
if rev=='v09':shutil.copy2(Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts/ucupaint_helpers.py'),scripts/'ucupaint_helpers.py')
def dims(bounds):return ' × '.join(f'{v:.2f}' for v in bounds['dimensions_mm'])+' мм'
state=f'''# ПМ — доработка {rev}

Сохранено: {datetime.now().astimezone().isoformat(timespec='seconds')}.
Этап: геометрия готова к просмотру. Явного принятия {rev} владельцем пока нет.
Текстурирование UCUPaint / производственная UV не начинались.
Результат и план продолжения сохранены на диске.

## Актуальные файлы

- Основной: `{LIB}/01_ПМ/PM_Geometry_{rev}.blend`.
- Крепление: `{LIB}/02_Крепление/PM_OpticMount_Geometry_{accessory_rev}.blend`.
- Коллиматор: `{LIB}/03_Коллиматор/PM_ReflexSight_Geometry_{accessory_rev}.blend`.
- Галерея: `gallery.html`; проверочные изображения и ролик — `Превью/`.
- Рабочая копия: `{OUT}`.
- Исходный v5: `{revision['source']}`; SHA-256 `{revision['source_sha256']}`.
  Исходник сохранён без изменений. Независимые магазины v3, патрон и глушитель библиотеки сохранены.

## Вариант и размеры

Художественный high-poly ПМ по присланным скриншотам с отдельным креплением и открытым коллиматором.
Оси: X вдоль ствола, отрицательный X к дулу; Y поперёк; Z вверх. World-space метры.
Корень сохраняет масштаб исходного v5. Blender {qa['version']}.
Габариты без прицела/крепления, с кольцом ремешка: {dims(qa['base_closed'])}.
С прицелом: {dims(qa['assembly_closed'])}. Крепление: {dims(qa['mount'])}. Прицел: {dims(qa['optic'])}.
Планка: {dims(qa['reference_proportions']['rail'])};
{qa['reference_proportions']['rail_length_ratio']*100:.1f}% длины и
{qa['reference_proportions']['rail_width_ratio']*100:.1f}% ширины затвора, по уточнению владельца.
Боковая пластина с двумя винтами находится над спусковым крючком.

## Выполнено

'''+'\n'.join('- '+x for x in revision['changes'])+f'''
- Для рифлёной нижней защёлки открыта отдельная выемка рамки. Защёлка остаётся на пистолете при извлечении магазина.
- Обвесы сохранены отдельными редактируемыми .blend и входят в сборку отдельными коллекциями.

## Проверки и управление

Свежий процесс: {len(qa['geometry'])} затронутых сеток, 0 boundary / overfull / wire / zero-area дефектов.
Проверены 18 поз, фактическое движение шести контролов, отдельность защёлки от магазина,
следование крепления за затвором, 9 лучей канала ствола с обоих концов и 9 лучей шахты магазина.
Это проверки указанных критериев, а не доказательство точной реконструкции реального механизма.
Отчёты — `Проверки/`.

Выбрать `PM_CONTROLS • select me`. Контролы 0..1: Slide, Hammer, Safety, Trigger, Magazine, MagCatch.
Для ручных свойств отключить Action у корня. Активная `Geometry inspection {rev}`: 1–120, 24 fps;
исходная `Demo v5` сохранена в Actions, диапазон 1–240.
Ролик `22_Движение_контролов.mp4`: 5 с, 12 fps, постановочная демонстрация геометрии.
Монтажные roots: `PM_OpticMount • asset root`, `PM_ReflexSight • asset root`.

## Неопределённости

Размеры аксессуаров, профиль флажка и форма насечек оценены по перспективным изображениям.
Сварной шов целика повторяет художественный образец владельца; это вариант данного ассета.
Маркировки на металле, надписи/метка на коллиматоре и микроповреждения ещё требуют текстурного этапа.
Сам прицел геометрический: визуальная линза есть, прицельная метка пока не сделана.
Галерея показывает нейтральные проверочные материалы. Итоговая засаленная отделка ещё не создана.
Работа выполнена на сохранённом источнике: для просмотра открыть новые переданные файлы; прежние окна автоматически не обновляются.

## Следующий этап после принятия геометрии

1. Записать явное принятие конкретной {rev} и сохранить её отдельной копией перед UCUPaint.
2. Native UCUPaint, отдельные editable слои: воронение, контактный износ кромок, разнонаправленные царапины,
   мелкие раковины/вмятины, жирные следы рук, отпечатки и локальные масляные пятна.
3. Бакелит: тёмный красно-коричневый неоднородный цвет, глянцевые засаленные зоны,
   выщерблины, царапины; насечка/медальон читаются в бликах.
4. Основные уникальные PBR-карты 8K, где оправдано; не выдавать увеличенную 4K за исходную 8K.
   До финала проверять крупные планы и поверхность при двух направлениях света.
5. CC0-сырьё уже скачано: ambientCG Smear002 8K JPG и Scratches004 4K PNG,
   с официальными страницами лицензии, исходными ZIP и SHA-256. Это сырьё, не готовые карты ПМ.
6. Референсы владельца: 18 PNG. Sketchfab-ссылка записана; веб-инструмент не смог открыть модель,
   она не скачивалась. Из чужих скриншотов текстуры не извлекались.

Скрипты запускаются из `{PROJECT}`, их копии в комплекте — для сохранения рецепта.
Игровой экспорт, импорт и новые руки не входят в эту доработку и не выполнялись.
'''
if rev=='v07':
    state+='\n## Исправления после просмотра v06\n\n'
    state+='Сохранённая v06 — источник правок: `'+revision['parent_geometry']+'`, SHA-256 `'+revision['parent_sha256']+'`.\n'
    state+=f"Зазор планки над затвором: {qa['owner_corrections']['rail_underside_gap_mm']:.2f} мм. Полная высота планки: {qa['owner_corrections']['rail_height_mm']:.2f} мм.\n"
    state+='Полуцилиндр защёлки открывается внутрь рукоятки; выпуклая рифлёная поверхность видна из пятки.\n'
    state+='Коллиматор восстановлен по официальным фото R47 и авторскому руководству Umarex/Walther MRS, с размерами по скриншотам владельца. Точная марка его образца не установлена.\n'
    state+='Источники: '+', '.join(revision['optic_sources'])+'.\nФото/руководство архивированы только как визуальные референсы; это материалы с авторскими правами, не CC0-текстуры.\n'
    state+='RG49 из архива рассматривался и отвергнут: его корпус не соответствует образцу.\n'
if rev=='v08':
    state+='\n## ЗОРИН К-1 — новый вариант по десяти видам владельца\n\n'
    state+='Предыдущий коллиматор R47/MRS заменён. Новая форма: арочная глубокая защитная дуга, компактное окно, низкий хвост, круглая верхняя крышка с кнопкой и отдельный зажим.\n'
    state+='Русские надписи редактируются как FONT/Curve; шрифт встроен в .blend. Это проверочная компоновка маркировок до производственного UCUPaint.\n'
    state+='Вымышленный бренд ЗОРИН, модель К-1. Маркировки: ЗОРИН, К-1, РОССИЯ, № 061284, ВВЕРХ, ВПРАВО и 3 В.\n'
    state+=f"Геометрия {len(qa['k1']['unchanged'])} сеток ПМ/крепления/других прежних узлов совпала с v07 по вершинам, граням, матрицам и родителям.\n"
    state+='Новая база адаптирована к узкой планке данного художественного ПМ; внешняя форма по скриншотам владельца, масштаб корпуса по руководству DeltaPoint Pro.\n'
    state+='Официальный источник масштаба: https://www.leupold.com/media/manuals/deltapoint-pro-manual.pdf . Руководство использовалось для габаритов и расположения видимых деталей.\n'
    state+='Новые референсы и первичный документ — Референсы/k1. Прежние оптические референсы сохранены как история, а не источник текущей формы.\n'
if rev=='v09':
    state=state.replace('Текстурирование UCUPaint / производственная UV не начинались.','Полное текстурирование и производственные UV ещё ждут принятия геометрии. По отдельному поручению владельца создан локальный нативный UCUPaint для светлого заполнения клейм рамки.')
    state=state.replace('Маркировки на металле, надписи/метка на коллиматоре и микроповреждения ещё требуют текстурного этапа.','Маркировки рамки и коллиматора вырезаны настоящей геометрией. Светлая эмаль со сколами нанесена только на дно клейм рамки. Прицельная метка и общий износ ещё требуют текстурного этапа.')
    state=state.replace('Галерея показывает нейтральные проверочные материалы.','Галерея показывает проверочные материалы и заказанное светлое заполнение клейм рамки.')
    state+='\n## Настоящая гравировка v09\n\n'
    state+='Коллиматор: 18 вырезов; крупные буквы 0,09 мм, мелкие 0,045 мм, эмблемы 0,04 мм, стрелки 0,025 мм.\n'
    state+='Рамка: КОРС-9 0,12 мм; № КР061284, 9×18, КР · 06/24, ОТК, условные кольцо/треугольник — 0,08 мм. Клейма художественные.\n'
    state+='Дно клейм рамки: два настоящих слоя UCUPaint 2.4.9 — тёмный металл и светлая эмаль; редкие сколы задаёт Noise с локальным Ramp. Остальные материалы проверочные.\n'
    state+='Источник FONT/Curve и замкнутый Mesh-резак каждой надписи сохранены скрытыми. Boolean DIFFERENCE остаются редактируемыми; для правки текста требуется обновить резак, автоматической связи с FONT нет.\n'
    state+=f"Свежий файл: {len(qa['engraving']['markings'])} групп выемок прошли замер глубины, нативные операнды и стек заполнения проверены. Базовые сетки {len(qa['k1']['unchanged'])} прежних узлов сохранились; новые выемки рамки добавлены модификаторами.\n"
    state+='Все три .blend проверены после повторного открытия; макроракурсы 32–38 показывают дно, кромки и заполнение выемок.\n'
(OUT/'asset-state.md').write_text(state,encoding='utf-8')
next_stage='Полное текстурирование ждёт принятия геометрии; локальное заполнение клейм рамки уже выполнено.' if rev=='v09' else 'Текстуры UCUPaint ещё не начинались: сначала принятие показанной геометрии.'
(OUT/'00_ОТКРЫТЬ_СНАЧАЛА.txt').write_text(f'ПМ {rev} — геометрия на проверку\n\nОткройте gallery.html для просмотра.\nМодели: 01_ПМ, 02_Крепление, 03_Коллиматор.\nУправление, состояние и следующий этап: asset-state.md.\n{next_stage}\n',encoding='utf-8')

images=sorted(p for p in (OUT/'Превью').glob('*.png') if not p.stem.endswith('_draft') and p.stem[:2].isdigit())
expected_images={'v06':22,'v07':28,'v08':30,'v09':37}[rev]
assert len(images)==expected_images, (len(images),expected_images)
assert (OUT/'Превью/22_Движение_контролов.mp4').is_file()
delivery=json.loads((OUT/'Проверки/delivery_check.json').read_text(encoding='utf-8'))
assert delivery['pass_delivery']
hero=next(p for p in images if p.name.startswith('01_'))
groups=[('Сборка и пропорции',{'01','02','03','04','20','21'}),('Детали крупным планом',{'05','06','07','08','09','10','11','12','13','23'}),('Движение и отдельные обвесы',{'14','15','16','17','18','19'})]
if rev=='v07':groups.insert(0,('Исправления по вашему просмотру',{'24','25','26','27','28','29'}))
if rev in {'v08','v09'}:
    groups=[('ЗОРИН К-1 — новая форма и русские надписи',{'18','24','25','26','30','31'})]+[(title,ids-{'18'}) for title,ids in groups]+[('Крепление и пятка v07',{'27','28','29'})]
if rev=='v09':groups.insert(0,('Утопленные клейма и светлая эмаль',{'32','33','34','35','36','37','38'}))
sections=[]
for title,ids in groups:
    cards=[]
    for p in images:
        if p.name[:2] not in ids:continue
        label=p.stem[3:].replace('_',' ');url=quote('Превью/'+p.name)
        cards.append(f'<button class="card" data-src="{url}" data-label="{html.escape(label)}"><img src="{url}" alt="{html.escape(label)}" loading="lazy"><span>{html.escape(label)}</span></button>')
    sections.append('<section><h2>'+title+'</h2><div class="grid">'+''.join(cards)+'</div></section>')
document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ПМ — геометрия v06</title>
<style>
:root{color-scheme:dark;--bg:#12161b;--panel:#1c232b;--line:#343f4b;--text:#eaf0f5;--muted:#a8b7c5;--accent:#d4b387}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 'Segoe UI',sans-serif}main{max-width:1280px;margin:auto;padding:42px 28px 60px}h1{font-size:42px;letter-spacing:-1px;margin:10px 0 12px}h2{font-size:24px;font-weight:600;margin:40px 0 18px}p{max-width:940px;color:var(--muted)}.tag{color:var(--accent);letter-spacing:2px;font-size:12px;text-transform:uppercase}.hero{display:block;width:100%;border:1px solid var(--line);border-radius:14px;margin-top:25px}.links{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}.links a{padding:10px 15px;border:1px solid var(--line);border-radius:8px;color:var(--text);text-decoration:none;background:var(--panel)}.links a:hover,.links a:focus{border-color:var(--accent)}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card{padding:0;text-align:left;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--panel);color:var(--text);cursor:pointer;font:inherit}.card img{width:100%;display:block;aspect-ratio:1800/1240;object-fit:contain}.card span{display:block;padding:12px 14px}.card:hover,.card:focus-visible{outline:2px solid var(--accent);outline-offset:2px}video{max-width:100%;width:850px;border:1px solid var(--line);border-radius:12px}dialog{max-width:96vw;max-height:95vh;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:12px;padding:14px}dialog::backdrop{background:#000c}dialog img{display:block;max-width:91vw;max-height:80vh;object-fit:contain}.dialogbar{display:flex;align-items:center;justify-content:space-between;gap:25px;margin:0 0 10px}.close{border:1px solid var(--line);color:var(--text);background:var(--panel);border-radius:6px;padding:6px 14px;font:inherit;cursor:pointer}footer{margin-top:45px;color:var(--muted);font-size:14px}@media(max-width:800px){main{padding:26px 16px}h1{font-size:34px}.grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:480px){.grid{grid-template-columns:1fr}}
</style><main><div class="tag">Редактируемые Blender-ассеты · v06</div><h1>Пистолет Макарова</h1><p>Геометрия для проверки: затвор, окно и зацеп выбрасывателя, курок, флажок, спуск, накладка и нижняя рифлёная защёлка. Крепление с двумя винтами и коллиматор — отдельные ассеты.</p><p>Планка укорочена до трети длины и ширины затвора, крепление перенесено над крючком. Сейчас показаны нейтральные материалы; засаленная отделка будет следующим этапом после принятия формы.</p>
'''
document=document.replace('v06',rev)
if rev=='v07':
    document+='<p>Правки v07: плавные скобы; плоская планка ближе к затвору; тонкий целик со скошенными боковинами; прямая пятка магазина; развёрнутая рифлёная защёлка. Коллиматор полностью перестроен по фотографиям Umarex R47 и Walther MRS, масштаб подогнан под ваши референсы.</p>'
if rev=='v08':
    document=document.replace('<h1>Пистолет Макарова</h1>','<h1>ЗОРИН К-1 · ПМ v08</h1>')
    document+='<p>Коллиматор заменён по вашим десяти новым видам: глубокая арочная защита, компактное окно, круглая крышка с кнопкой, плоский хвост и низкий зажим. Вымышленный бренд «ЗОРИН», модель «К-1»; надписи русские и редактируемые. Геометрия ПМ и крепления v07 сохранена. Сейчас показаны материалы проверки формы; окончательная отделка следует после принятия.</p>'
if rev=='v09':
    document=document.replace('<h1>Пистолет Макарова</h1>','<h1>КОРС-9 · ЗОРИН К-1</h1>')
    document+='<p>Надписи коллиматора теперь вырезаны в металле. На рамке — утопленные «КОРС-9», серийный номер, калибр, партия и условные технические клейма. Светлая краска на дне выемок местами облупилась; она сохранена отдельными нативными слоями UCUPaint. Общая отделка ПМ ещё ждёт принятия формы.</p>'
document+='<div class="links">'+''.join(f'<a href="{quote(path)}">{label}</a>' for path,label in [(f'01_ПМ/PM_Geometry_{rev}.blend','ПМ · .blend'),(f'02_Крепление/PM_OpticMount_Geometry_{accessory_rev}.blend','Крепление · .blend'),(f'03_Коллиматор/PM_ReflexSight_Geometry_{accessory_rev}.blend','Коллиматор · .blend'),('asset-state.md','Состояние и управление')])+'</div>'
document+=f'<img class="hero" src="{quote("Превью/"+hero.name)}" alt="Новая сборка ПМ">'+''.join(sections)
if rev in {'v08','v09'}:
    pairs=[]
    for owner,prefix,label in [('01','25','Спереди'),('02','24','Сбоку'),('06','31','Сверху')]:
        rendered=next(p for p in images if p.name.startswith(prefix+'_'))
        cards=[]
        for path,title in [(f'Референсы/k1/owner_k1_{owner}.jpg',label+' · ваш образец'),('Превью/'+rendered.name,label+' · ЗОРИН К-1')]:
            url=quote(path);cards.append(f'<button class="card" data-src="{url}" data-label="{title}"><img src="{url}" alt="{title}" loading="lazy"><span>{title}</span></button>')
        pairs.append('<div class="grid" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-bottom:18px">'+''.join(cards)+'</div>')
    document+='<section><h2>Сверка с вашими ракурсами</h2><p>Исходные скриншоты и текущая форма. Цвет и износ на образце относятся к следующему текстурному этапу.</p>'+''.join(pairs)+'</section>'
if (OUT/'Превью/22_Движение_контролов.mp4').is_file():document+='<section><h2>Демонстрация контролов</h2><p>5 секунд, постановочная анимация геометрии. Редактируемые ключи сохранены в основном .blend.</p><video controls preload="metadata" src="'+quote('Превью/22_Движение_контролов.mp4')+'"></video></section>'
document+='''<footer>Основа v5 сохранена. Референсы и CC0-сырьё — в соответствующих папках; новые текстуры ещё не создавались. Нажмите изображение, чтобы увеличить.</footer></main><dialog id="zoom"><div class="dialogbar"><span id="caption"></span><button class="close" id="close">Закрыть</button></div><img id="full" alt=""></dialog><script>const d=document.getElementById('zoom'),i=document.getElementById('full'),c=document.getElementById('caption');document.querySelectorAll('.card').forEach(b=>b.addEventListener('click',()=>{i.src=b.dataset.src;i.alt=b.dataset.label;c.textContent=b.dataset.label;d.showModal()}));document.getElementById('close').onclick=()=>d.close();d.addEventListener('click',e=>{if(e.target===d)d.close()});</script></html>'''
if rev=='v09':document=document.replace('новые текстуры ещё не создавались','создано локальное заполнение клейм; полная отделка впереди')
(OUT/'gallery.html').write_text(document,encoding='utf-8')

sheet=Image.new('RGB',(1920,1420),'#151b22');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',27)
overview=[('01','Сборка / короткое крепление'),('05','Ствол и зацеп в окне'),('06','Курок и фаски'),('12','Нижняя рифлёная защёлка')]
if rev=='v07':overview=[('27','Плавное низкое крепление'),('07','Тонкий целик / скошенные боковины'),('18','Новый коллиматор'),('12','Параллельная пятка / защёлка')]
if rev=='v08':overview=[('18','ЗОРИН К-1 / арочная форма'),('24','Боковой профиль / русский бренд'),('31','Крышка, кнопка и регулировки'),('01','Новый коллиматор на ПМ')]
if rev=='v09':overview=[('36','КОРС-9 / светлая эмаль в клеймах'),('38','Утопленные буквы / сколы заполнения'),('32','ЗОРИН / геометрия выемок'),('33','Утопленные стрелка и ВВЕРХ')]
for j,(prefix,label) in enumerate(overview):
    p=next(p for p in images if p.name.startswith(prefix+'_'));im=ImageOps.contain(Image.open(p).convert('RGB'),(940,650))
    x=(j%2)*960;y=(j//2)*710;sheet.paste(im,(x+(960-im.width)//2,y+45+(650-im.height)//2));draw.text((x+22,y+8),label,font=font,fill='#e5edf3')
sheet.save(OUT/'Превью/Обзор_геометрии.png')

files=[]
for p in OUT.rglob('*'):
    if not p.is_file() or p.name.endswith(('.blend1','_draft.png')) or p.name in {'package_manifest.json'}:continue
    files.append(dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
manifest=dict(source=str(OUT),destination=str(LIB),created=datetime.now().astimezone().isoformat(timespec='seconds'),files=files)
(OUT/'Проверки/package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('PM_PACKAGE_READY',len(files),sum(f['bytes'] for f in files),'bytes',str(OUT),flush=True)
