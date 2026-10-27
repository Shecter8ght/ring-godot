# Пробелы в навыках ассетов — что изучить и записать

Составлено 2026-10-27 (Claude) по просьбе владельца для следующей сессии, в том числе из другого профиля. Цель
владельца — максимально автоматизировать модели и приблизить их к уровню AAA. Навыки лежат в `tools/asset_skills/`:
`weapon-asset-texturing` (текстуры, Painter, самопроверка), `godot-asset-preparation` (игровая сетка, развёртка,
запекание), `blender-asset-workflow` (моделирование), `npc-character-gear` (NPC и снаряжение). Что уже записано из
роликов — `docs/STATUS.md`, записи 2026-10-25…27 («навыки: …»).

**Как начать:** спросить владельца, с чего начать. Предложение — пункты 1–3 (они ближе всего к работе), потом остальные.

## 1. RizomUV — подключить скриптами (главное)

Установлен владельцем 2026-10-27 (`D:\ПРОГРАММЫ\RizomUV 2024.1`, строка в AGENTS.md, задел в BACKLOG). Нужен для нормы
заполнения атласа 80 %: наш модуль `tools/asset_kit/uv.py` упёрся в 59–69 % у оружия и 72–77 % у кузовов машин.
- Изучить: управление из командной строки (Lua) и из Python через RizomUVLink (в папке программы); развёртка по
  швам на жёстких рёбрах, выпрямление, упаковка с группами и отступами, возврат развёртки в Blender без потери
  жёстких рёбер (в ролике «UV для прошаренных» мост RizomUV ↔ Blender их сохранял, FBX — терял).
- Запросы: `RizomUV Lua command line auto unwrap pack script`, `RizomUVLink Python example`, документация RizomUV
  по скриптам.
- Записать в `godot-asset-preparation/references/mesh-bake.md`; первыми проверять — новый ствол и кузов машины.

## 2. Запекание и одинаковые нормали Blender — Painter — Godot

Сейчас в навыке одна строка про cage. Ошибки дают швы и «волны» в игре.
- Тангенты MikkTSpace: у Painter в проекте есть настройка «compute tangent space per fragment» (по документации Adobe
  для Blender — включать); не экспортировать тангенты низкой сетки, чтобы Painter считал свои. Как Godot считает
  тангенты у glTF — в найденных источниках нет: проверить на кубе (запечь, открыть в Godot, искать швы).
- Группы запекания (соседняя деталь не печатается на другую), перекос мелочи (skew) и способы его исправить в
  Blender, сглаживание запекания.
- Запросы: `bake groups Blender hard surface weapon artifacts skew`, `Godot 4 MikkTSpace glTF tangents normal map seams`.
- Источники: [Marmoset — запекание, группы, skew](https://marmoset.co/?p=16956),
  [Adobe — tangent space](https://experienceleague.adobe.com/zh-hant/docs/substance-3d/bakers/features/tangent-space),
  [Polycount — MikkTSpace](https://polycount.com/discussion/comment/2762295),
  [Polycount — cage и skew](https://polycount.com/discussion/comment/2716577/).

## 3. Импорт карт в Godot

В навыках ничего нет. По документации Godot (`ResourceImporterTexture`):
- нормали — сжатие RGTC (`compress/normal_map`), синий канал не нужен;
- `roughness/src_normal` — фильтр шероховатости по карте нормалей при импорте: меньше мерцания бликов на металле;
- мипмапы в 3D обязательны (+~33 % памяти).
- Проверить, что сейчас стоит у ВЕРАС, ПМ и ВСС-М (их `*_imports.py`), записать правило в `godot-checks.md`.
- Источник: [Godot — импорт текстур](https://docs.godotengine.org/en/4.4/classes/class_resourceimportertexture.html).

## 4. Трим-листы и декали для окружения

Навыки почти целиком про оружие, а «Проспекту» нужны здания, бетон, заборы. Бесплатно:
[PCPER — трим-листы](https://irc.pcper.com/vod-trim-sheets-101.html),
[80.lv — улица на трим-листах и декалях](https://80.lv/articles/005cg-001agt-sanxia-street-1940-modular-approach-trim-sheets-decals).
Запрос: `trim sheet tutorial Blender Substance Painter free`. Записать отдельной справкой (новый навык или раздел в
`blender-asset-workflow`) — спросить владельца.

## 5. LOD и коллизии в цифрах

Сколько треугольников на каждом уровне, на каких расстояниях переключать, как в Godot (visibility range, авто-LOD).
Сессия транспорта собирается делать свои дальние LOD машин. Запрос: `game LOD guidelines percent triangles distance
weapon props`.

## 6. Трафареты по местам без кисти

В AAA маски износа на 80–90 % рисуют рукой. У нас — генераторы, маски владельца, запечённые следы контакта и маски из
данных игры (`tools/wear_from_use`). Узнать, можно ли скриптом Painter класть трафарет проекцией в нужное место.
Запрос: `Substance Painter Python API fill layer projection mask script`.

Ещё не разобран ролик EnterStudio3D «Peeling Metal Smart Material» (https://www.youtube.com/watch?v=M-GK1BfTXLg) —
без речи; разбирать по кадрам — только если владелец захочет.

## Как доставать текст роликов YouTube

Встроенный браузер приложения. С этой машины YouTube может показать капчу или потребовать вход — входит владелец сам
в панели браузера (агент не вводит пароли). Затем в странице ролика (javascript_tool) включить субтитры плеера и
перехватить их запрос с токеном — прямой запрос `timedtext` без токена отдаёт пустоту:

```js
performance.clearResourceTimings(); performance.setResourceTimingBufferSize(5000);
const mp = document.getElementById('movie_player'); mp.mute();
const pr = mp.getPlayerResponse(); const title = pr.videoDetails.title;
const langs = pr.captions.playerCaptionsTracklistRenderer.captionTracks.map(t => t.languageCode);
const lang = /[а-яё]/i.test(title) && langs.includes('ru') ? 'ru' : (langs.includes('en') ? 'en' : langs[0]);
try { mp.setOption('captions','track',{}); mp.unloadModule('captions'); } catch(e) {}
mp.loadModule('captions'); mp.setOption('captions','track',{languageCode: lang}); mp.playVideo();
await new Promise(r => setTimeout(r, 5000)); mp.pauseVideo();
const url = performance.getEntriesByType('resource').map(e => e.name)
  .filter(u => u.includes('timedtext') && u.includes('pot=') && u.includes('lang=' + lang)).pop();
const j = await (await fetch(url)).json();   // события → текст по минутам: ev.segs[].utf8, ev.tStartMs
```

Длинный текст отдавать кусками (`window.__vt.slice(...)`). Ролик без речи субтитров не имеет.

## Как ставить изменённые навыки

- Проверка исходника: `python -X utf8 tools/install_asset_skills.py --check` (ссылки, общий `working-rules.md`).
- Claude Code этого компьютера: `~/.claude/skills/<навык>` — ссылки (junction) на `tools/asset_skills/<навык>`, правка
  видна сразу. У другого профиля проверить, куда смотрят его навыки.
- Codex: скопировать папку навыка в `~/.codex/skills/<навык>` и в `~/.agents/skills/<навык>` (во вторую — только если
  навык там уже есть), прежние — в `_asset_src/asset_skill_backups/<дата>/`. Codex подхватит после перечитывания
  навыка или новой сессии.
- claude.ai: zip папки навыка без `agents/` (корень архива — папка навыка) в `Скиллы для Claude — загрузить в профиль/`,
  строка в `00 — Как загрузить.txt`; загружает владелец.

## Git — грабли этой недели

Параллельно работают несколько сессий и Codex. Коммитить только свои файлы через временный индекс
(`GIT_INDEX_FILE=… git read-tree HEAD`, add, commit), общие журналы (`docs/STATUS.md`, BACKLOG, AGENTS.md) — блобом
«HEAD + свой кусок». После коммита — `git reset -q -- <свои пути>` в обычном индексе и `git diff --cached --stat`.
Пустой `.git/index.lock` старше 20–40 с без процессов `git.exe` / `git-lfs.exe` (висящий с 25.10 `hash-object
--stdin-paths` не в счёт) — брошенный, его можно снять. Подготовленная запись, совпадающая со старым коммитом пути
(`git rev-parse :<путь>` = `HEAD~N:<путь>`), — застрявший откат чужого коммита: сбросить к HEAD; совпадающую с
рабочей копией — не трогать.
