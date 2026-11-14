# anim-spec.json — ответы владельца об анимациях рук

Лежит в папке модели в библиотеке (`E:/Models Blender/WEAPONS/<ствол>/anim-spec.json`), рядом с `finish-spec.json`
текстур. Это источник решений: агент читает файл, а не пересказ другой сессии.

```text
python -X utf8 tools/asset_skills/weapon-fps-hand-clips/scripts/anim_spec.py new "<папка модели>/anim-spec.json" wpn_hg_02 "АСТЕН-919" pistol
python -X utf8 tools/asset_skills/weapon-fps-hand-clips/scripts/anim_spec.py check "<папка модели>/anim-spec.json"
```

`new` — заготовка из памятки (все пункты этого вида, `need: "?"`, черновые фазы); существующий файл не перезаписывает.
`check` — проверка (у каждого пункта ответ, имена фаз не повторяются, у «живых» есть вопрос к игре, записан
характер) и выжимка markdown — её вставить в `asset-state.md`. Код выхода 1 — «не готово», с перечнем.

## Поля

```json
{
 "weapon": "wpn_hg_02", "name": "АСТЕН-919", "kind": "pistol", "created": "2026-11-12",
 "status": "interview | poses | clips | owner_editing | accepted | in_game",
 "style": {"reference": "Road to Vostok / EFT", "words": "плавно, не суетливо; упругость и тяжесть в передёргивании",
           "tempo": "неполная ~3,4 с, полная ~4,4 с"},
 "interview": [{"q": "…", "a": "…"}],
 "clips": [
  {"id": "reload_full_rack", "title": "…", "group": "reload", "need": "yes | no | later",
   "phases": [{"mark": "rack_pull", "text": "левая тянет затвор, пистолет уходит за рукой", "owner": true}],
   "blender": "что в клипе", "game": "что делает игра", "notes": "свои слова владельца, варианты"}
 ],
 "game_questions": [{"clip": "stress_mag_drop", "q": "при каком стрессе и как часто", "a": ""}],
 "accepted": false
}
```

- `phases[].owner: true` — фазу добавил или переставил владелец (видно, где его решение).
- Варианты одного пункта (два досыла) — отдельные записи `clips` со своими `id`.
- Свои пункты владельца, которых нет в памятке, — тоже в `clips` (`group: "owner"`), и в памятку
  (`animation-catalog.json`).
- `status` меняется по ходу работы; «клипы готовы» владельца → `accepted: true` и только тогда вывод в игру.
- Имена клипов в .blend — по `id` в CamelCase (`ASTEN919_Reload_Full_Rack`), роли в игре — в
  `weapons.<id>.weapon.viewmodel.clips` (`reload`, `reload_empty`, `reload_fast`, `reload_fast_empty`, `check`,
  `clear`, `inspect`, `shot`, `fire_mode_*`…); соответствие — при экспорте.

## Выжимка в asset-state.md

Раздел «Клипы рук» модели: выход `check` (характер, выбранные анимации с фазами, «позже», вопросы к игре) + путь к
файлу клипов, что черновое и что не проверено. Не дублировать файл целиком — `anim-spec.json` главный.

Пример заполнения задним числом по АСТЕН-919 — [anim-spec-example.json](anim-spec-example.json) (как было бы, если бы
интервью шло по этому навыку; файла владельца это не меняет).
