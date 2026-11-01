# Цевьё по ролику Dolinskyi — план эксперимента (2026-11-01)

Ролик: [Realistic Hard-Anodized Metal in Substance Painter | Complete Breakdown](https://www.youtube.com/watch?v=tfA1eReuX1w),
14 мин, автор Dolinskyi. Задача владельца: повторить разбор 1:1 — такое же цевьё и тем же способом текстуры, —
чтобы понять, чего не хватает нашему текстурированию. Модель экспериментальная, в игру без слова владельца не идёт.

Как изучено. Речь — субтитры (их уже доставала сессия 26.10, текст тот же). Картинка — кадры 1080p из плеера:
стек слоёв по папкам, состав масок, видимые значения, режимы вида, маски слоёв на модели, фото-референсы автора,
развёртка (2D-вид на 6:50). Кадры — `_asset_src/handguard_dolinskyi/video_frames/`.

**Главное, что видно только в картинке, а не в речи:**
- Автор работает в **Specular / Glossiness** (каналы Diffuse, Specular, Glossiness), не в Metal / Rough.
- Почти все маски — **генератор + grunge + слой рисования кистью** (Paint) в разных режимах (Subtract, Multiply,
  Linear Dodge). Ручная правка есть почти в каждой маске: «лишнее убрал кистью».
- Нормали всех папок смешиваются в режиме **Normal Map Detail**.
- Много своих масок автора: 11 трафаретов царапин, 4 отпечатка, «STAINS», «parkerization», «milling»,
  фото грязи «dirt_albedo». Они продаются в его комплекте за $5 (см. ниже).
- Значения большинства слоёв в ролике не показаны: автор включает слои по одному, не открывая настройки.
  Видимые числа выписаны ниже; остальное — подбор по кадрам («оценка»).

## 1. Цевьё: что моделируем

Прототип — FAB Defense NFR (квадрорельсовое drop-in цевьё под M4, карабинная длина, две половины: верх и низ).
Размеры из магазинов: длина 177 мм, ширина 55 мм, высота 60 мм ([OpticsPlanet](https://www.opticsplanet.com/fab-defense-nfr-carbine-length-m16-aluminum-quad-rail.html),
[TactX](https://tactx.no/en-as/products/nfr-carbine-length-m16-aluminum-quad-rail)). Своя модель по этим размерам и кадрам.

Форма по кадрам 1:58, 7:54 и фото автора (3:00–3:35):
- труба ≈ Ø41 мм, четыре планки Picatinny (MIL-STD-1913: ширина 21,2 мм, шаг пазов 10,01 мм, паз 5,23 мм, скосы 45°);
- верхняя планка длиннее корпуса спереди (консоль на 2 зуба), метки U1…U17;
- нижняя — во всю длину, метки B1…B15;
- боковые — между квадратными площадками с отверстием (гнездо QD / антабки) на обоих концах, метки L1…L13 и R1…R13;
- на четырёх диагональных гранях — по 13 наклонных овальных окон;
- сзади — посадочный буртик под дельта-кольцо с вырезами и «замочная скважина» сверху под газовую трубку;
- шов половин по горизонтали;
- надпись на верхней левой диагонали. **Маркировка вымышленная** (правило навыка): вместо «FAB-DEFENSE NFR-RS»
  предлагаю «VARN-DEFENSE   QR-7» (ВАРН — наши вымышленные рукоятки). Скажите, если нужно другое.

## 2. Моделирование (Blender 5, скрипты `tools/handguard_dolinskyi/`)

1. **High-poly** генератором: профиль трубы и планок → вырезы пазов, окон, отверстий, буртика (булевы) → фаски
   модификатором Bevel (0,3–0,6 мм, 3 сегмента) → проверка замкнутости и пересечений.
2. **Low-poly** той же формы без фасок, ~8–12 тыс. треугольников, окна — 16 сегментов по кругу. Многоугольники
   режутся на треугольники до FBX (грабли Painter).
3. **Развёртка** 2K, как у автора (2D-вид 6:50): планки — прямыми полосами, метки — по полосам; диагональные грани
   с окнами — длинными полосами; торцы — кругами. Отличие от автора: у него правая сторона зеркальна, а планки
   повторяют левую; у нас всё уникально, иначе надписи R1… читались бы зеркально.
4. **Запекание в Painter** (как у автора — видны handguard_position, normalobj): нормаль, нормаль в мире, ID, AO,
   кривизна, позиция, толщина.

Владелец смотрит форму в `.blend` до текстур. Если что-то не так — правлю и только потом запекаю.

## 3. Текстуры — стек по ролику (Painter 12.1, шаблон PBR Specular/Glossiness, 2K)

Вид в Painter (0:25): окружение Studio Tomoco, Blur 35, поворот 234, выравнивание Camera, тени выкл, TAA 32,
тонкривая Linear, анизотропная фильтрация High (8spp), MipMap bias Z-Sharp.

Стек снизу вверх (так в кадре 13:20). «Видно» — число из ролика, «оценка» — подбор по кадрам.

**BASE** (Normal)
1. *Color* — заливка: Diffuse #1D1D1E (видно), Specular #383838 = 0,04, как у неметалла (видно), Glossiness 0,40 (видно).
2. *MatFinish Powder Coated* — слой рисования Passthrough, внутри фильтр `matfinish_powder_coated`
   (Scale 6, Flakes Intensity 0,5, Custom Flake и Triplanar выкл — видно), над фильтром якорь «MatFinish Powder Coated».
3. *noise* — заливка Diffuse #3F4145, Glossiness 0,6704, прозрачность 44 % (видно); маска — заливка из якоря,
   канал Normal, Keep alpha, Levels: вход 0,004 / 1 / 0,788 (видно).

**Color variations** (Passthrough) — *oclussion*: маска снизу вверх Paint → AO (Linear Dodge) → Grunge Wipe Smudgy
Soft (Subtract) → Grunge Wipe Smudgy Soft (Linear Dodge) → Paint → Curvature (Subtract) → Paint. Цвет и сила — оценка.

**Height/Normal** (нормали — Normal Map Detail)
- *milling*: «milling top», «milling left»… — заливки рельефа, маска из десятков заливок текстуры «milling» в Linear
  Dodge (каждая — отдельный след фрезы на своём месте), Paint (Multiply), Levels; *lines* — маска Paint → Curvature
  (Subtract) → Fill (Subtract); *lines 02*.
- *metal imperfection* — маска Anisotropic Noise → Paint (Multiply) → Paint → якорь «metal imperfection mask».
- *soft* — мягкие вмятины кромок.
- *edge damage*: «hard+height» — маска Fill → Histogram Scan → Warp → Grunge Pebbles (Subtract) → Blur →
  Histogram Scan → Paint (Multiply) → Paint → Sharpen → Paint (Multiply); «hard+height 1». Сколы — мелкие точки
  там, где цевьё бьётся; в высоту вдавлены лишь немногие.

**decals** — одна маска надписей из файла с автообновлением.
- *decal* — заливка Diffuse ≈ #ACA6A0 (замер по кадру), вдавлена в высоту; маска: Fill (картинка надписей) → якорь
  «decal mask» → Warp.
- *Fill layer 2* — тёмный ободок: маска из якоря → Blur → Levels (буквы чуть тоньше).

**weathering** (главный этап, канал — блеск)
1. *ao dust* — Diffuse #161616, Glossiness 0,3 (видно): пыль в углах, генератор Dirt + grunge_dust_wide, лишнее кистью.
2. *dust* — ровная лёгкая пыль: Fill (Linear Dodge) → AO (Subtract) → Curvature (Subtract) — с выступов вычищена.
3. *glossy smudges* — Grunge Wipe Smudgy → AO (Multiply) → Paint: швы островов развёртки замазаны кистью.
4. *glossy stains* — своя маска автора «STAINS» → AO (Multiply) → Paint → Levels.
5. *rail wearing* — Diffuse #0F0F0F, Specular #696765, Glossiness 0,65 (видно); маска — фото износа планки
   (Photoshop: ч/б, Levels, контраст, лишнее кистью) → Levels.
6. *gloss variations* — Grunge Dirt Scratchy (Levels выкл); *gloss variations 02* — Grunge Concrete → Blur.
7. *rail scratches* — только блеск: Paint → AO (Multiply) → [Grunge Dust Wide (Subtract), выкл] → трафарет
   царапин (Linear Dodge 100) → трафарет (Linear Dodge 90) → Paint.
8. *circles* — кольцевые следы в гнёздах QD: Paint → Curvature (Subtract).
9. *High_matte* — матовые контрастные пятна, Diffuse тёмно-красный; маска Dirt → Grunge Dust Wide (Subtract) → Paint →
   Grunge Plaster Faded (Subtract) → Paint → Histogram Scan → Paint (Linear Dodge) → Paint → якорь «matte02 mask».
10. *High_Gloss* — глянцевые контрастные пятна, маска — альфы кистью.

**edges** — *edges*: только блеск, светлые глянцевые кромки: Metal Edge Wear → Paint → Blur → Grunge Leaks (Subtract).

**Dirt**
- *dots_white* — белые точки пыли: Fill → Histogram Scan → Paint (вычищено у мест касания);
- *dots_orange* — тёмно-жёлтые точки;
- *ao dark* — засохшее масло: матовое, тёмное, Diffuse — фото грязи «dirt_albedo»;
- *dots ao light*.

**AO** (папка, в конце выключена) · *shapen* — Sharpen на блеск · *CC_GLoss* — Levels по блеску (контраст) ·
*glossy*, *matte* — контрастные пятна кистью поверх всего.

## 4. Ресурсы: что есть, чего нет

| Ресурс из ролика | Painter 12.1 | Чем заменить |
|---|---|---|
| Окружение Studio Tomoco | есть | — |
| Фильтр matfinish_powder_coated | есть | — |
| Генераторы Dirt, AO, Curvature, Metal Edge Wear | есть | — |
| Фильтры Levels, Histogram Scan, Warp, Blur, Sharpen | есть | — |
| Grunge: Dust Wide, Wipe Smudgy (Soft), Plaster Faded, Concrete, Dirt Scratchy, Leaks, Pebbles | есть | — |
| Anisotropic Noise | есть (noise_anisotropic_noise) | — |
| Трафареты царапин 01–11 (свои) | нет | ambientCG Scratches001–005 + ваши `09_Царапины`; царапины от обвесов — промпт 1 |
| Отпечатки 01–04 (свои) | есть похожие (fingerprint_*) | ambientCG Fingerprints001–009 из вашей библиотеки |
| STAINS (глянцевые пятна, свои) | нет | ambientCG Smear001–008 + ваши `06_Разводы`; промпт 4 |
| Фото износа планки → маска | нет | промпт 2 |
| Альфы контрастных пятен (сделаны из фото) | нет | промпт 3 |
| «milling» — текстура следов фрезы | нет | сделаю кодом (дуги торцевой фрезы, параллельные риски) |
| «parkerization» | нет | назначение в ролике не показано — шум кодом |
| «dirt_albedo» — фото грязи для масла | нет | промпт 5 (или CC0 ambientCG по вашему разрешению на скачивание) |
| Надписи (Photoshop + автообновление) | — | PNG кодом, вымышленные; автообновление ресурса Painter то же |
| Фото-референсы автора | — | его бесплатный набор «115 photos of AR-15 attachments» (нужен ваш вход на ArtStation) |

Substance 3D Community Assets: для этого ролика не нужны — всё стандартное есть в Painter, а своих ресурсов автора
там нет.

**Комплект автора за $5** ([ArtStation](https://www.artstation.com/a/53609385), «Black GunMetal — Source Files»):
сцена Painter 11.0.3, трафареты царапин, фото-референсы. С ним «1:1» станет буквальным: все числа слоёв и маски
кистью — из его файла, а не подбором. Купить может только владелец. Его трафареты — не CC0: в игру они пойдут только
с вашего решения (лицензия Extended Commercial это позволяет, но правило 6 AGENTS.md требует CC0/CC-BY).

## 5. Промпты для ChatGPT (если решите делать)

Формат — как у ваших масок в «Маски_АЛЬФА»: квадрат 2048, ч/б, светлое на чёрном, без света и тени.

1. **Царапины от обвесов на планке** (папка `09_Царапины`):
   `Use case: production grayscale alpha brush mask for Substance Painter. One square image 2048x2048. FLAT SCALAR COVERAGE MASK, NOT a photograph. Subject: a dense band of short straight parallel scratches and scuffs left by clamping and sliding rail-mounted accessories on an anodized aluminum rail: 60-90 thin bright lines 1-6 px wide, mostly perpendicular to the band, varying length 20-300 px, some broken and doubled, a few deeper bright gouges, faint micro-scratches in between. Band runs horizontally through the middle, occupies 35 percent of image height, ragged uneven edges, fades out at left and right ends. Light marks on absolute pitch black RGB 0 0 0. Strictly neutral grayscale. NO lighting, no highlights, no shadows, no bevel, no depth, no metal, no rail object, no text, no border.`
2. **Износ планки от установки и снятия обвеса** (то, что автор делал из фото):
   `Use case: production grayscale alpha mask for Substance Painter. One square image 2048x2048. FLAT SCALAR COVERAGE MASK, NOT a photograph. Subject: wear footprint left on top of a Picatinny rail by repeatedly mounted and removed accessories: a row of 8 rectangular rubbed patches spaced evenly along a horizontal line, each patch about 180x120 px, polished brighter at the edges and corners, softer and mottled in the middle, with short scuffs and tiny bright dents; uneven, each patch different, some barely visible. Light marks on absolute pitch black RGB 0 0 0. Neutral grayscale only. NO lighting, no shadows, no bevel, no rail object, no metal texture, no text, no border.`
3. **Контрастные пятна — набор альф** (матовые и глянцевые «приманки для глаза»):
   `Use case: production grayscale alpha brush sheet for Substance Painter. One square image 2048x2048, a 3x3 grid of nine separate brush alphas, each centered in its cell with wide black margins. FLAT SCALAR COVERAGE MASKS, NOT photographs. Subjects: small irregular smudges and blotches as left by a greasy fingertip, a dried water drop ring, a wiped dust patch, a short rubbed scuff, a cluster of tiny specks, a dried oil spot with a darker rim, a thumb smear, a faint cloudy stain, a crescent rub mark. Soft and hard edges mixed, multiscale micro-detail at the borders. Light marks on absolute pitch black RGB 0 0 0. Neutral grayscale. NO lighting, no shadows, no bevel, no surface, no text, no grid lines.`
4. **Глянцевые пятна по всей поверхности** (замена «STAINS»):
   `Use case: production grayscale tileable mask for Substance Painter. One square image 2048x2048, SEAMLESS (tiles on all four sides). FLAT SCALAR COVERAGE MASK, NOT a photograph. Subject: sparse glossy stains on matte metal: 25-40 irregular soft-edged patches of different size (40-400 px), some faint and cloudy, some with a sharper drying rim, a few wipe streaks; about 25 percent coverage, uneven distribution with empty areas. Light marks on absolute pitch black RGB 0 0 0. Neutral grayscale. NO lighting, no shadows, no bevel, no metal texture, no text.`
5. **Фото грязи для засохшего масла** («dirt_albedo»; здесь нужен цвет):
   `Seamless tileable photographic texture, 2048x2048, top-down, flat even diffuse light, no shadows from lighting: dusty grimy concrete wall surface with dried dirty oil and yellowish-brown dust stains, contrasting patches of grey, ochre, dark brown and pale yellow, fine grit, small dark specks. No objects, no text, no vignette, tiles seamlessly on all four sides.`

## 6. Мазки кистью

Проверено по документации Painter 12.1: **Python API мазки не рисует** («Strokes are not accessible from the Python API»).
Слой рисования создать можно, а провести по нему кистью — нет. Есть три пути:

- **А. Маски «мазков» кодом в развёртке** (как штрихи в `tools/ar15/wear_magazine.py`): по картам позиции,
  нормали и кривизны рисую мазки нужной формы и направления и кладу их в маску заливкой картинки вместо Paint.
  Быстро и повторяемо, но это всё равно расчёт, а не рука художника.
- **Б. Вы мажете сами по инструкции:** в стеке оставлю пустые слои рисования «РУКАМИ: …» — какой слой, какая кисть,
  какая альфа, где и сколько. Ближе всего к ролику: у автора это и есть ручная работа.
- **В. Я мажу мышью в окне Painter** (computer-use: выбираю кисть и альфу, провожу по модели). Тоже настоящие мазки,
  но медленно, и нужно ваше разрешение на доступ к окну Painter.

Ближе к ролику — Б и В. Делаю А сразу, чтобы был готовый результат, и оставляю слои для Б. Если разрешите В —
переделаю ручные места мышью.

## 7. Чего не получится и почему

- **Точные числа большинства слоёв.** В ролике они не показаны. Нужно: комплект автора ($5) — тогда возьму их из его
  сцены. Без него — подбор по кадрам.
- **Его трафареты и фото.** Нужно: комплект автора или маски по промптам 1–5. Пока — CC0 из вашей библиотеки.
- **Настоящие мазки кистью скриптом** — невозможно (см. п. 6). Нужно: вы (Б) или доступ к экрану (В).
- **Своё фото реального цевья в руках** (автор снимал в оружейном магазине) — его у нас нет. Работаю по фото автора
  из ролика.
- **Spec/Gloss в Godot.** Godot — Metal/Rough. Для эксперимента держу Spec/Gloss, как в ролике; для игры понадобится
  перевод (у основы specular 0,04 перевод простой: металличность 0, шероховатость = 1 − глянец). В игру — только
  с вашего слова.

## 8. Расхождения с навыками проекта (по заданию — следовать ролику)

- Навык: сначала этап 1 «идеально новая заводская отделка», износ — отдельно и только по заказу. В ролике износ сразу:
  пыль, масло, сколы, следы обвесов на одном проходе. Следую ролику; заводская основа (BASE, decals, Height/Normal)
  при этом отдельными папками.
- Навык: рабочий процесс Metal/Rough. В ролике — Spec/Gloss.
- Навык: маски износа — фото-маски CC0 трипланарно. В ролике — генератор + grunge + ручная чистка кистью в каждой маске,
  контрастные пятна — нарисованы альфами.
- Навык: нормали в Normal / Normal Map Combined. В ролике — Normal Map Detail у всех папок.

## 9. Что получите

- `E:/Models Blender/WEAPONS/Цевьё — Dolinskyi, анодирование 2026-11-01/`: high-poly и low-poly `.blend` со студией;
  проект Painter `.spp` со стеком, как в ролике; файл просмотра с картами и студией.
- Свои рендеры в ракурсах кадров ролика рядом с кадрами и отличия словами.
- Разбор ролика — в навык `weapon-asset-texturing` (новая справка), Codex и архив для claude.ai.

## Итог (2026-11-01, вечер)

Сделано по плану: модель, развёртка, запекание, стек Painter (13 папок, 35 слоёв, 124 эффекта, 30 пустых слоёв
«РУКАМИ»), маски мазков кодом, рендеры рядом с кадрами ролика. Комплект и отличия от кадров —
`E:/Models Blender/WEAPONS/Цевьё — Dolinskyi, анодирование 2026-11-01/asset-state.md`; разбор ролика и чего нам не
хватало — навык `weapon-asset-texturing/references/hard-anodized-dolinskyi.md`. Проект Painter открывать
`tools/handguard_dolinskyi/painter_open.cmd`. Отклонения от плана: Scale фильтра MatFinish 24 вместо 6 (масштаб под нашу
развёртку; в нормаль — 25 %), окна 15,5 × 6 мм с наклоном 25° (по рендеру автора сбоку), «Fill layer 9» не сделан (в ролике не показан).
