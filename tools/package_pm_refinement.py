"""Offline review gallery, state and a bounded copy manifest for PM v06."""
from pathlib import Path
from datetime import datetime
import hashlib, html, json, shutil
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont, ImageOps

PROJECT=Path(__file__).resolve().parents[1];ROOT=PROJECT/'_asset_src/pm_refinement';OUT=ROOT/'review_v06'
LIB=Path('E:/Models Blender/WEAPONS/ПМ — модели и текстуры/08_Доработка_v6_на_проверку')
qa=json.loads((OUT/'Проверки/fresh_file_geometry.json').read_text(encoding='utf-8'))
revision=json.loads((OUT/'Проверки/revision_manifest.json').read_text(encoding='utf-8'))
assert qa['audit_pass']
assert hashlib.sha256((OUT/'01_ПМ/PM_Geometry_v06.blend').read_bytes()).hexdigest()==qa['sha256']
for source,folder in [(ROOT/'references','Референсы'),(ROOT/'surface_sources','Сырьё_для_текстур')]:
    target=OUT/folder;target.mkdir(exist_ok=True)
    for p in source.rglob('*'):
        if p.is_file():
            dest=target/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
scripts=OUT/'Скрипты';scripts.mkdir(exist_ok=True)
for name in ('inspect_pm_refinement.py','fetch_pm_refinement_sources.py','revise_pm_refinement.py','review_pm_refinement.py','separate_pm_refinement.py','animate_pm_refinement.py','package_pm_refinement.py','check_pm_refinement_delivery.py','publish_pm_refinement.py'):
    p=PROJECT/'tools'/name
    if p.exists():shutil.copy2(p,scripts/name)
def dims(bounds):return ' × '.join(f'{v:.2f}' for v in bounds['dimensions_mm'])+' мм'
state=f'''# ПМ — доработка v06

Сохранено: {datetime.now().astimezone().isoformat(timespec='seconds')}.
Этап: геометрия готова к просмотру. Явного принятия v06 владельцем пока нет.
Текстурирование UCUPaint / производственная UV не начинались.
Владелец сообщил о выключении ПК в 01:00; результат и план продолжения сохранены на диске.

## Актуальные файлы

- Основной: `{LIB}/01_ПМ/PM_Geometry_v06.blend`.
- Крепление: `{LIB}/02_Крепление/PM_OpticMount_Geometry_v01.blend`.
- Коллиматор: `{LIB}/03_Коллиматор/PM_ReflexSight_Geometry_v01.blend`.
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
Для ручных свойств отключить Action у корня. Активная `Geometry inspection v06`: 1–120, 24 fps;
исходная `Demo v5` сохранена в Actions, диапазон 1–240.
Ролик `22_Движение_контролов.mp4`: 5 с, 12 fps, постановочная демонстрация геометрии.
Монтажные roots: `PM_OpticMount • asset root`, `PM_ReflexSight • asset root`.

## Неопределённости

Размеры аксессуаров, профиль флажка и форма насечек оценены по перспективным изображениям.
Сварной шов целика повторяет художественный образец владельца; это вариант данного ассета.
Маркировки на металле, надписи/метка на коллиматоре и микроповреждения ещё требуют текстурного этапа.
Сам прицел геометрический: визуальная линза есть, прицельная метка пока не сделана.
Галерея показывает нейтральные проверочные материалы. Итоговая засаленная отделка ещё не создана.
Живая сцена Blender через MCP недоступна: открывать переданные новые файлы; старые окна автоматически не обновлялись.

## Следующий этап после принятия геометрии

1. Записать явное принятие конкретной v06 и сохранить её отдельной копией перед UCUPaint.
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
(OUT/'asset-state.md').write_text(state,encoding='utf-8')
(OUT/'00_ОТКРЫТЬ_СНАЧАЛА.txt').write_text('ПМ v06 — геометрия на проверку\n\nОткройте gallery.html для просмотра.\nМодели: 01_ПМ, 02_Крепление, 03_Коллиматор.\nУправление, состояние и следующий этап: asset-state.md.\nТекстуры UCUPaint ещё не начинались: сначала принятие показанной геометрии.\n',encoding='utf-8')

images=sorted(p for p in (OUT/'Превью').glob('*.png') if not p.stem.endswith('_draft') and p.stem[:2].isdigit())
hero=next(p for p in images if p.name.startswith('01_'))
groups=[('Сборка и пропорции',{'01','02','03','04','20','21'}),('Детали крупным планом',{'05','06','07','08','09','10','11','12','13','23'}),('Движение и отдельные обвесы',{'14','15','16','17','18','19'})]
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
document+='<div class="links">'+''.join(f'<a href="{quote(path)}">{label}</a>' for path,label in [('01_ПМ/PM_Geometry_v06.blend','ПМ · .blend'),('02_Крепление/PM_OpticMount_Geometry_v01.blend','Крепление · .blend'),('03_Коллиматор/PM_ReflexSight_Geometry_v01.blend','Коллиматор · .blend'),('asset-state.md','Состояние и управление')])+'</div>'
document+=f'<img class="hero" src="{quote("Превью/"+hero.name)}" alt="Новая сборка ПМ">'+''.join(sections)
if (OUT/'Превью/22_Движение_контролов.mp4').is_file():document+='<section><h2>Демонстрация контролов</h2><p>5 секунд, постановочная анимация геометрии. Редактируемые ключи сохранены в основном .blend.</p><video controls preload="metadata" src="'+quote('Превью/22_Движение_контролов.mp4')+'"></video></section>'
document+='''<footer>Основа v5 сохранена. Референсы и CC0-сырьё — в соответствующих папках; новые текстуры ещё не создавались. Нажмите изображение, чтобы увеличить.</footer></main><dialog id="zoom"><div class="dialogbar"><span id="caption"></span><button class="close" id="close">Закрыть</button></div><img id="full" alt=""></dialog><script>const d=document.getElementById('zoom'),i=document.getElementById('full'),c=document.getElementById('caption');document.querySelectorAll('.card').forEach(b=>b.addEventListener('click',()=>{i.src=b.dataset.src;i.alt=b.dataset.label;c.textContent=b.dataset.label;d.showModal()}));document.getElementById('close').onclick=()=>d.close();d.addEventListener('click',e=>{if(e.target===d)d.close()});</script></html>'''
(OUT/'gallery.html').write_text(document,encoding='utf-8')

sheet=Image.new('RGB',(1920,1420),'#151b22');draw=ImageDraw.Draw(sheet)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',27)
for j,(prefix,label) in enumerate([('01','Сборка / короткое крепление'),('05','Ствол и зацеп в окне'),('06','Курок и фаски'),('12','Нижняя рифлёная защёлка')]):
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
