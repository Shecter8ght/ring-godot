"""Portable review gallery and provenance for the native Blender art asset."""
import base64
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex'
VERSION = 'v02'
MASTER = f'Grenade_MkII_UCUPaint_Codex_{VERSION}.blend'
PREVIEW = f'Grenade_MkII_PBR_Preview_{VERSION}.blend'
TARGET = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v02')


def package():
    audit = json.loads((OUT/'checks/fresh_reopen_audit.json').read_text(encoding='utf8'))
    maps = json.loads((OUT/'textures/pbr_v02/manifest.json').read_text(encoding='utf8'))
    measurements = json.loads((OUT/'checks/measurements_and_topology.json').read_text(encoding='utf8'))
    assert audit['pass'] and len(maps) == 16
    png_rows=[]
    for row in maps:
        data=(OUT/'textures/pbr_v02'/row['file']).read_bytes()
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and data[24]==16,row['file']
        width,height=struct.unpack('>II',data[16:24])
        assert [width,height]==row['size'],row['file']
        png_rows.append({'file':row['file'],'bit_depth':data[24],'size':[width,height]})
    (OUT/'checks/pbr_png_encoding.json').write_text(json.dumps(png_rows,indent=2),encoding='utf8')
    layer_count = sum(len(m['layers']) for m in audit['materials'])
    points = json.loads((OUT/'checks/size_annotation_points.json').read_text(encoding='utf8'))
    x, bottom = points['height_bottom']
    _, top = points['height_top']
    left, baseline = points['body_left']
    right, _ = points['body_right']
    size_image=base64.b64encode((OUT/'previews/09_size_front.png').read_bytes()).decode('ascii')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1900" viewBox="0 0 1600 1900">
<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#ffd883"/></marker></defs>
<image href="data:image/png;base64,{size_image}" width="1600" height="1900"/>
<g stroke="#ffd883" stroke-width="3" fill="none"><path d="M{x-30} {top}h80 M{x-30} {bottom}h80"/><path d="M{x} {top+7}V{bottom-7}" marker-start="url(#a)" marker-end="url(#a)"/>
<path d="M{left} {baseline-35}v75 M{right} {baseline-35}v75"/><path d="M{left+7} {baseline}H{right-7}" marker-start="url(#a)" marker-end="url(#a)"/></g>
<g fill="#ffd883" font-family="Arial,sans-serif" font-size="38"><text x="{x+25}" y="{(top+bottom)/2}">114,7 мм</text><text x="{(left+right)/2}" y="{baseline+72}" text-anchor="middle">Ø 63,4 мм — корпус</text></g></svg>'''
    (OUT/'previews/size_annotated.svg').write_text(svg, encoding='utf8')

    readme = f'''# Граната Mk II — текстуры Codex {VERSION}

Подготовлено к просмотру владельцем, 12 октября 2026.

Откройте `{MASTER}` для редактирования настоящих слоёв UCUPaint.
`{PREVIEW}` использует уже запечённые карты и удобен для быстрого просмотра.
Галерея `gallery.html` содержит крупные планы, сравнение с исходником и видео движения.

Габариты: общая высота 114,7 мм, диаметр корпуса 63,4 мм. Единицы сцены — метры,
отображение — миллиметры. Геометрия исходника сохранена без увеличения.

Выберите `CTRL_Grenade`: в пользовательских свойствах находятся `pin_pull` и
`lever_open` в диапазоне 0–1. Запуск таймлайна демонстрирует движение на кадрах 1–96,
24 кадра/с. Для ручных ползунков сначала отвяжите Action `DEMO_PinAndLever_VisualOnly`
от корня в редакторе Action (кнопка X рядом с именем Action); затем задайте свойства.
Чека и кольцо перемещаются вместе, рычаг имеет собственный управляющий объект.

Корпус: нерегулярные раковины литья, окраска olive drab, местами вытертый чугун,
царапины, стёртая жёлтая полоса, слабая грязь в защищённых бороздах.
Головка: светлый тусклый металл; верхняя часть рычага светлая, нижняя темнее;
кольцо: более гладкая стальная проволока. {layer_count} слоёв в четырёх материалах UCUPaint.

Главные слои корпуса: 07 — раковины; 18/19 — износ жёлтой полосы; 29/30 —
протёртая краска и полированные участки чугуна; 32 — тонкие царапины;
80/82 — грязь и пыль; 90 — слабый масляный след пальца в шероховатости.
Рельеф сделан через Height/Bump; вершины и силуэт источника сохранены.

16 карт PBR PNG 16 bit: корпус 8K; головка и рычаг 4K; кольцо и чека 2K.
BaseColor — sRGB; Metallic/Roughness/NormalGL — Non-Color; UV — PBRUV.
Все {len(audit['images'])} изображения встроены в оба итоговых .blend; внешние копии
рядом с файлами сохранены для редактирования и проверки.

Подробнее о происхождении, ограничениях геометрии и проверках — `asset-state.md`.
Оригинальный Grenade.blend не перезаписан. Для исторически точной формы головки
потребуется отдельная правка геометрии: сохранённая модель Scenario имеет условные детали.
'''
    (OUT/'00_НАЧНИ_ЗДЕСЬ.md').write_text(readme, encoding='utf8')

    topology = [(r['name'],r['welded_boundary_edges'],r['welded_nonmanifold_edges'])
                for r in measurements['mesh_topology']]
    state = f'''# Состояние ассета: Grenade Mk II / Codex {VERSION}

Статус: **подготовлено к просмотру владельцем**. Текстуры ещё не утверждены владельцем.

## Источник и объём поручения

- Сохранённый исходник: `E:/Models Blender/From Scenario/Grenade/Grenade.blend`.
- SHA-256: `{audit['source_sha256']}`. Исходник не перезаписан.
- Владелец поручил проверить готовую модель, её масштаб, сделать визуальное движение
  чеки/рычага и текстурирование. Силуэт и конструктивная форма не переделывались.
- Первая рабочая версия v01 сохранена в `_asset_src/grenade_codex/`; v02 учитывает три
  позднее присланных фотографии владельца: раковины, выемки, местами вытертую краску.
- Blender {audit['blender']}, настоящий UCUPaint {audit['ucupaint']}; четыре нативных стека,
  {layer_count} слоёв, каналы Color/Metallic/Roughness/Normal.

## Масштаб и геометрия

Z вверх; модель стоит у начала координат. Единица сцены = 1 метр.
Габарит сборки: 65,20 × 63,40 × 114,70 мм. Корпус: Ø63,40 × 86,00 мм.
Это полный предмет ручного размера; увеличивать его из-за масштаба сцены не нужно.
Корпус несколько шире встречающихся в справочных/коллекционных описаниях Mk II
(обычно около 57–60 мм). Это особенность исходной формы, оставленная без изменения.

Все 16 исходных meshes, их вершины/рёбра/грани, smooth flags и UVMap побайтно
сверены со снимком исходника. Мировые матрицы в собранном положении совпадают после
переноса исходного корня к нулю (погрешность менее 0,0003 мм).
Родители изменены для заказанного управления отдельными деталями.
На временной копии выполнено слияние совпадающих вершин с допуском 0,0001 мм,
чтобы отличить разрезанные вершины импорта от открытых краёв. Результат по объектам
(открытые / неманифолдные рёбра): `{topology}`. Доставленная сетка не сваривалась.
Условная головка, шесть декоративных заклёпок, широкая форма рычага и ровные грани
исходника не являются точной реконструкцией исторического Mk II.

## Состояние поверхности

Один художественный вариант умеренного старения, ориентир — фотографии 1/2 владельца;
фотография 3 уточняет характер шероховатости и литья. Условия цены/лута не назначались.
Раковины: оригинальная 8K-карта 16 bit, нейтраль 0,5, Object BOX-проекция 160 мм;
поры 0,15–0,66 мм, редкие выемки 0,7–1,8 мм, локальные углубления до около 0,35 мм.
Height/Bump не меняет силуэт и не моделирует конструктивные отверстия.
Размеры царапин/отпечатка/полосы заданы в миллиметрах; остальные micrograin — процедурные.
Свежие макрорендеры подтверждают работу слоёв рельефа и протёртой краски.

## UV и карты

UVMap исходника сохранён. BandProjection/StampProjection/FingerprintProjection
обслуживают локальные детали покраски; цветовые атрибуты Wear_* ограничивают контакт
и защищённые борозды. PBRUV — отдельная развёртка для 16 запечённых карт.
Корпус 8192², головка/рычаг 4096², чека/кольцо 2048². PNG 16 bit,
BaseColor sRGB; остальные Non-Color; нормали tangent OpenGL (+Y).
Нормали запечены из поверхности нативного стека, а не увеличены из карт Scenario.
При разборе UV нет вырожденных треугольников. Папки `textures/authoring`,
`textures/pbr_v02`, `textures/sources`, `textures/original_scenario` имеют manifest/хеши.

## Движение

CTRL_Grenade содержит float-ползунки pin_pull/lever_open. Кольцо и чека — единая группа;
рычаг и его декоративные заклёпки — отдельная группа. Demo 1–96, 24 fps.
Контроль промежуточных поз и закрытого положения есть в fresh_reopen_audit.json.
Это анимация внешних деталей художественного предмета; внутреннее устройство отсутствует.

## Источники и права

- Три фотографии владельца: `references/owner/`, только визуальная сверка.
- [Inert Ordnance: Mk II](https://inert-ord.net/usa03a/usa2/index.html): реальные
  окрашенные экземпляры разных лет, только визуальная сверка.
- [IMA: исходный экземпляр Mk II](https://www.ima-usa.com/products/original-u-s-wwii-inert-mkii-pineapple-grenade-with-yellow-ring-m10a3-fuze-14):
  фото литья, жёлтой полосы и наружных металлических деталей, только сверка.
- [The Grenade Recognition Manual, Mk II](https://tgrm.foxed.ca/Americangrenades/Mk%20II/The%20Mk%202%20grenade.html):
  общий вид и приблизительные габариты.
- [Ordnance School OS 9-18, Vol. 3](https://www.bulletpicker.com/pdf/OS-9-18-Vol-3.pdf),
  исторический официальный документ: наружный корпус головки — цинковый сплав,
  рычаг — листовая сталь. Использована только информация о внешнем материале.
- [ambientCG Fingerprints003](https://ambientcg.com/view?id=Fingerprints003),
  [CC0](https://docs.ambientcg.com/license/): один слабый частичный отпечаток;
  исходная opacity сохранена, выполнены кадрирование, поворот и изменение размера.
- Остальные маски оригинальные синтетические, воспроизводимые скриптами;
  ни одна фотография не проецировалась в текстуры. Надпись LOT R-102 художественная.
- Исходная модель Scenario предоставлена владельцем; новая лицензия на чужой источник
  не назначалась. Внешние фото не входят в экспортируемые карты.

## Проверки и следующая работа

Свежие открытия master и preview; фактические входы native stack; SHA-256 packed/external;
геометрия и исходные UV; 13 промежуточных поз; 16 PBR-файлов и их PNG bit depth;
оба общих вида, нижняя часть, головка/кольцо, поверхность рычага, крупный план корпуса;
сравнение нативных материалов и карт, 96 кадров демонстрации, пути локальной галереи.
Проверки сохранены в `checks/`, карты — рядом с .blend.
После копирования в папку выдачи выполняется повторный audit именно файла из неё.

Следующий этап при желании владельца — согласование внешнего вида и отдельная точная
правка формы головки/рычага. Игровая оптимизация, LOD, коллизии и импорт Godot этим
поручением не выполнялись.
'''
    (OUT/'asset-state.md').write_text(state, encoding='utf8')
    (OUT/'variants.json').write_text(json.dumps({'version': VERSION, 'states': [
        {'id': 'aged_reference', 'label': 'Литьё и местами вытертая краска',
         'review_status': 'prepared_for_owner_review', 'price': None, 'loot': None,
         'native': MASTER, 'preview': PREVIEW}]},ensure_ascii=False,indent=2),encoding='utf8')

    cards = [
        ('03_cast_and_wear','Раковины литья и вытертая краска'),
        ('04_head_ring_marking','Светлая головка, кольцо и стёртая полоса'),
        ('05_lever_surface','Поверхность рычага'),
        ('02_textured_other_side','Обратная сторона'),
        ('08_bottom','Нижняя часть'),
        ('06_pin_separate_lever_held','Чека отдельно, рычаг удержан'),
        ('07_lever_outward','Рычаг отведён наружу'),
        ('10_baked_comparison','Проверка запечённых PBR-карт')]
    card_html = ''.join(f'<button class="card" data-full="previews/{name}.png"><img loading="lazy" src="previews/{name}.png" alt="{title}"><span>{title}<b>Открыть крупно ↗</b></span></button>' for name,title in cards)
    html = '''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Граната Mk II — Codex</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#151b1f;color:#ecece4;font:16px/1.55 system-ui,sans-serif}main{max-width:1320px;margin:auto;padding:40px 28px 80px}a{color:#ebc879}h1{font-size:clamp(32px,5vw,64px);line-height:1.05;margin:12px 0 20px;font-weight:620;letter-spacing:-.04em}h2{font-size:27px;font-weight:580;margin:55px 0 16px}p{max-width:850px;color:#b8c0c3}.eyebrow{color:#ebc879;letter-spacing:.18em;font-size:12px}.badges{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}.badges span{border:1px solid #38434a;border-radius:30px;padding:7px 14px;font-size:13px}.intro{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:center}.intro img{width:100%;border-radius:12px}.links{display:flex;flex-wrap:wrap;gap:12px;margin:25px 0}.links a{padding:12px 16px;border:1px solid #7d703f;border-radius:7px;text-decoration:none;color:#f1da9f}.note{font-size:13px;color:#91a0a7}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.card{border:1px solid #344149;border-radius:8px;background:#1e272c;padding:0;color:inherit;cursor:zoom-in;text-align:left;overflow:hidden;font:inherit}.card img{width:100%;display:block}.card span{display:block;padding:15px}.card b{display:block;font-size:11px;font-weight:400;color:#93a3aa;margin-top:7px}.compare{position:relative;max-width:700px;aspect-ratio:1600/1900;overflow:hidden;border:1px solid #40505a;border-radius:9px}.compare img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}.before{clip-path:inset(0 50% 0 0)}.line{position:absolute;left:50%;height:100%;border-left:2px solid #f0d195;pointer-events:none}.compare-label{position:absolute;top:15px;background:#121a20d9;padding:8px 12px;border-radius:6px;font-size:12px}.compare-label.old{left:15px}.compare-label.new{right:15px}input[type=range]{width:min(700px,100%);accent-color:#e9c87b;display:block;margin:18px 0}video{max-width:100%;width:520px;border-radius:10px;background:#222e35}.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}.size{width:100%;border-radius:10px}table{border-collapse:collapse;min-width:430px;max-width:100%}td,th{text-align:left;border-bottom:1px solid #344149;padding:12px 18px 12px 0;font-size:14px}th{color:#a7b5bc;font-weight:500}code{color:#e5d095;background:#263239;padding:2px 5px;border-radius:3px}dialog{background:#111b20;border:1px solid #586873;border-radius:10px;padding:0;max-width:95vw;max-height:95vh}dialog::backdrop{background:#000b}dialog img{display:block;max-height:90vh;max-width:92vw}dialog button{position:absolute;right:10px;top:10px;border:0;border-radius:6px;padding:9px 14px;color:#fff;background:#19282fea;font-size:18px;cursor:pointer}footer{border-top:1px solid #344149;margin-top:60px;padding-top:24px;font-size:13px;color:#95a3aa}@media(max-width:800px){.intro,.pair{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,1fr)}main{padding:25px 16px}table{min-width:0;width:100%}}@media(max-width:470px){.grid{grid-template-columns:1fr}}
</style><main>
<div class="eyebrow">BLENDER · UCUPAINT · V02 · 12.10.2026</div>
<div class="intro"><div><h1>Граната Mk II<br>Литьё и износ</h1><p>Нерегулярные раковины и выемки, местами вытертая краска, светлая металлическая головка. Внешний вид уточнён по трём фотографиям владельца и снимкам реальных экземпляров.</p><div class="badges"><span>8K корпус</span><span>16 bit PBR</span><span>49 слоёв UCUPaint</span><span>Чека и рычаг отдельно</span></div><div class="links"><a href="MASTER_FILE">Редактируемый .blend ↗</a><a href="PREVIEW_FILE">Быстрый PBR-просмотр ↗</a></div><p class="note">Подготовлено к просмотру владельцем. Исходный Grenade.blend сохранён.</p></div><img src="previews/01_textured_overall.png" alt="Общий вид готовых текстур"></div>
<h2>Крупные планы</h2><p>Нажмите на изображение, чтобы рассмотреть поверхность в полном размере.</p><div class="grid">CARD_HTML</div>
<h2>Исходник и новые текстуры</h2><p>Одинаковые камера, свет и масштаб. Ползунок меняет границу сравнения.</p><div class="compare"><img src="previews/01_textured_overall.png" alt="Новые текстуры"><img class="before" src="previews/source_original.png" alt="Исходные текстуры"><div class="line"></div><span class="compare-label old">Исходник</span><span class="compare-label new">Codex v02</span></div><label for="split" class="note">Граница сравнения</label><input id="split" type="range" min="0" max="100" value="50">
<h2>Масштаб и движение</h2><div class="pair"><div><img class="size" src="previews/size_annotated.svg" alt="Высота 114,7 мм; корпус диаметром 63,4 мм"><p>Модель имеет полный ручной размер. Общий габарит — 65,2 × 63,4 × 114,7 мм. Размеры исходника сохранены.</p></div><div><video controls playsinline loop preload="metadata" poster="previews/07_lever_outward.png"><source src="previews/pin_and_lever_demo.mp4" type="video/mp4"></video><p>Демонстрация внешних деталей: чека и кольцо выходят вместе, рычаг отводится наружу. В Blender — кадры 1–96, 24 кадра/с.</p><p>Выберите <code>CTRL_Grenade</code>. Свойства <code>pin_pull</code> и <code>lever_open</code> управляют позами. Для ручной настройки отвяжите демонстрационный Action от корня; подробности в <a href="00_НАЧНИ_ЗДЕСЬ.md">памятке</a>.</p><p class="note">Головка и форма рычага сохранены из модели Scenario; для точного исторического силуэта потребуется отдельная правка геометрии.</p></div></div>
<h2>Карты и редактирование</h2><table><tr><th>Детали</th><th>Разрешение</th><th>Каналы</th></tr><tr><td>Корпус</td><td>8192 × 8192</td><td rowspan="3">BaseColor · Metallic<br>Roughness · NormalGL</td></tr><tr><td>Головка и рычаг</td><td>4096 × 4096</td></tr><tr><td>Кольцо и чека</td><td>2048 × 2048</td></tr></table><p>PNG 16 bit, отдельная развёртка PBRUV. Все изображения встроены в .blend, внешние копии сохранены рядом. Слои раковин, протёртой краски, царапин, шероховатости и грязи редактируются независимо.</p><p><a href="asset-state.md">Состояние ассета и проверки</a> · <a href="textures/pbr_v02/manifest.json">Манифест PBR-карт</a> · <a href="checks/fresh_reopen_audit.json">Проверка сохранённой сцены</a></p>
<footer>Материалы сверены по <a href="https://inert-ord.net/usa03a/usa2/index.html">Inert Ordnance</a>, <a href="https://www.ima-usa.com/products/original-u-s-wwii-inert-mkii-pineapple-grenade-with-yellow-ring-m10a3-fuze-14">IMA</a> и фотографиям владельца. Фотографии служат референсами; их пиксели не извлекались в карты. Частичный отпечаток — <a href="https://ambientcg.com/view?id=Fingerprints003">ambientCG, CC0</a>; остальные маски оригинальные.</footer>
</main><dialog id="large"><button aria-label="Закрыть">×</button><img alt="Крупный план"></dialog><script>
const split=document.querySelector('#split');split.addEventListener('input',()=>{document.querySelector('.before').style.clipPath=`inset(0 ${100-split.value}% 0 0)`;document.querySelector('.line').style.left=split.value+'%'});const dialog=document.querySelector('#large');for(const card of document.querySelectorAll('.card'))card.addEventListener('click',()=>{dialog.querySelector('img').src=card.dataset.full;dialog.querySelector('img').alt=card.querySelector('span').textContent;dialog.showModal()});dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
</script></html>'''.replace('MASTER_FILE',MASTER).replace('PREVIEW_FILE',PREVIEW).replace('CARD_HTML',card_html)
    html=html.replace('49 слоёв',f'{layer_count} слоёв')
    (OUT/'gallery.html').write_text(html, encoding='utf8')

    files=[MASTER,PREVIEW,'gallery.html','00_НАЧНИ_ЗДЕСЬ.md','asset-state.md','variants.json','source_inspection.json']
    for folder in ['checks','references','textures/authoring','textures/pbr_v02','textures/sources','textures/original_scenario']:
        files.extend(p.relative_to(OUT).as_posix() for p in (OUT/folder).rglob('*') if p.is_file())
    views=[name for name,_ in cards]+['01_textured_overall','09_size_front','source_original']
    files.extend(f'previews/{name}.png' for name in views)
    files.extend(['previews/size_annotated.svg','previews/pin_and_lever_demo.mp4'])
    rows=[]
    for file in sorted(set(files)):
        path=OUT/file
        assert path.is_file(),file
        rows.append({'file':file,'bytes':path.stat().st_size,
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (OUT/'delivery_manifest.json').write_text(json.dumps({'destination':str(TARGET),'files':rows},indent=2),encoding='utf8')
    print('PACKAGE_OK',len(rows),'files',sum(r['bytes'] for r in rows),'bytes',flush=True)


def verify(path):
    manifest=json.loads((path/'delivery_manifest.json').read_text(encoding='utf8'))
    for row in manifest['files']:
        file=path/row['file']
        assert file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256'],row['file']
    html=(path/'gallery.html').read_text(encoding='utf8')
    local=[]
    for link in re.findall(r'(?:src|href|data-full)="([^"]+)"',html):
        if not link.startswith(('http','data:','#')):
            assert (path/link).is_file(),link
            local.append(link)
    print('DELIVERY_HASHES_AND_GALLERY_OK',len(manifest['files']),'files',len(local),'local links',flush=True)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='verify':
        verify(Path(sys.argv[2]) if len(sys.argv)>2 else OUT)
    else:
        package()
