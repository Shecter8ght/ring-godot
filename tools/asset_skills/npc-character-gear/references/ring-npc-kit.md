# Инструменты RING: `tools/npc_kit`

## Пути

- Рабочие файлы — `_asset_src/npc_kit/` (не в git): мародёр `npc_scav_<версия>.blend` (форма) и `npc_scav_<версия>_tex.blend`
  (с текстурами — на него садятся вещи, `kit_common.npc_file()`), вещи — `armor/`, `helmets/`, `backpacks/`, `pouches/`,
  свои карты — `tex_gen/`, фото — `tex/`, игровые — `game/`, снимки — `previews/`.
- Выдача владельцу — `E:/Models Blender/RING_NPC_Claude_2026-10-21/<Вещь>/<Вещь>_v0N_{форма,текстуры}.blend`,
  игровые — `…/Игровые/`, примерочная брони — `…/Броня/`. Прежние версии остаются рядом.
- Blender — `"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python <скрипт> -- <аргументы>`.
  Один процесс Blender за раз. Длинные прогоны — в фоне с журналом в файл.

## Скрипты

| Что | Скрипт |
|---|---|
| Пути, студия, камеры, рендер, сохранение, журнал | `kit_common.py` (`WORK`, `VERSION`, `studio`, `camera`, `render`, `save`, `log`) |
| Помощники UCUPaint | `ucup.py` |
| Тело | `body.py` |
| Одежда: швейная машина, оболочка, брюки, куртка, карманы, балаклава, берцы | `garment.py`, `shell.py`, `pants.py`, `jacket.py`, `pockets.py`, `balaclava.py`, `boots.py` |
| Сборка мародёра, швы и строчка картами, износ по месту | `assemble.py`, `details.py`, `wear.py` |
| Текстуры мародёра; фото Poly Haven; подготовка фото | `npc_texture.py`, `fetch_textures.py`, `prep_textures.py` |
| Детали брони и общие построители (лента, MOLLE, пакеты, фурнитура, `Mesh.build` с ключами формы) | `armor_kit.py` |
| Броня трёх уровней, пояс, примерочная, текстуры брони | `armor_poor.py`, `armor_mid.py`, `armor_top.py`, `armor_belt.py`, `armor_fitting.py`, `armor_texture.py` |
| Шлемы и их текстуры | `helmets.py`, `helmet_texture.py` |
| Мягкая ткань: складки, стропы, продавливание, строчки, проверка «внутри» | `soft_goods.py` |
| Рюкзаки, подсумки, места подсумков на броне | `backpacks.py`, `pouches.py`, `pouch_places.py` |
| Текстуры рюкзаков, подсумков, пояса | `gear_texture.py` |
| Свои карты: камуфляжи, закрепки MOLLE, липучка и стропа | `gen_npc_camo.py`, `gen_pack_camo.py`, `gen_pouch_camo.py`, `gen_armor_camo.py`, `gen_molle_tack.py`, `gen_velcro_maps.py` |
| Игровая версия мародёра и снаряжения | `game_lp.py`, `game_gear.py` |
| Крупные проверочные снимки любого .blend | `inspect_shots.py -- <файл> <вид:x:y:z:tx:ty:tz[:hide=…]> … out=<папка>` |
| Файл на просмотр | `deliver.py`, у вещей — `deliver=` в своём скрипте |

Генераторы карт (`gen_*.py`) — обычный Python: `python -X utf8 tools/npc_kit/<скрипт>.py`.
Аргументы скриптов Blender: `render` / `shots` — снимки в `previews`, `deliver=<папка>` — выдача;
у рюкзаков проба одной посадки — `only=<вид> fit=none closeups`.

## Правки и git

- Длинные правки скриптов с кириллицей — файлом в scratchpad (`patch_*.py` с уникальным именем), а не heredoc;
  запись — `write_text(..., encoding="utf-8", newline="\n")`, иначе файл уйдёт в CRLF.
- Рядом работают другие сессии и Codex: коммить только свои файлы через временный индекс; общие файлы
  (`docs/STATUS.md`) — блобом «HEAD + свой кусок» в той же команде, затем `git reset -q -- <свои пути>`
  в обычном индексе и тот же кусок — в рабочую копию. `_asset_src/` и `референсы/` не коммитятся.
- Документ вещи — `docs/assets/npc_<вещь>_vNN.md`; общие решения по снаряжению — `docs/design/gear_v2.md`.
