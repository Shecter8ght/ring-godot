# Анимации персонажей — как устроено, что есть, чего нет

Аудит 2026-09-30. Один персонаж на всех: игрок, напарники и мародёры — модель Persona
(`assets/models/characters/persona_animated.glb`, скелет Mixamo `mixamorig_*`, 52 кости).

## Схема

```
assets/animations/**/*.fbx (Mixamo, 597 файлов)
        │  tools/character_clips.json — какой файл каким клипом (61 клип)
        ▼
tools/bake_character_clips.gd  → assets/models/characters/persona_clips.res (AnimationLibrary)
        │  ключи по именам костей; таз — из осей FBX (Z вверх, масштаб 100) в оси Persona,
        │  горизонтальный снос за клип убран, вертикаль оставлена (присел / лёг / упал — таз у пола)
        ▼
CharacterAnimator (src/player/character_animator.gd) — узел в player.tscn и marauder.tscn
        │  каждый кадр: скорость (сглаженная), стойка, оружие, прицел, ранен → циклический клип
        │  animation_event / animation_event_seq у Player / Marauder → одиночный клип по стойке
        │  die(death_clip(...)) → клип смерти, последний кадр держится
        ▼
WeaponSocket (BoneAttachment3D на mixamorig_RightHand) → Grip
        смещение по семейству рукояток — data/weapon_sockets.json (tools/bake_weapon_sockets.gd)
```

Перезапечь клипы (после правки `character_clips.json` или новых FBX):
`tools/godot.cmd --headless -s res://tools/bake_character_clips.gd`, затем
`tools/godot.cmd --headless -s res://tools/bake_weapon_sockets.gd` и `anim_test`.

## Главная найденная поломка

Запекание брало позицию таза из FBX как смещение по Y, а в FBX Mixamo скелет лежит под узлом
с поворотом (Z вверх) и масштабом 100 — вертикаль таза терялась во **всех** 61 клипе: таз всегда
на высоте стоя (0.94 м). Поэтому присед и лёжа опускали модель вручную на подобранные числа
(`crouch_drop` 0.57, `crouch_walk_drop` 0.29, `prone_drop` 0.63), а всё, что падает, — смерть,
нокаут — «висело» телом горизонтально на высоте метра. Теперь таз переносится правильно
(`_retarget_hips`), ручные опускания убраны, клип сам кладёт тело: присед — таз 0.37, лёжа — 0.12,
после смерти — грудь 0.13–0.25 м, ступни во всех клипах на полу (±0.04 м).

## Состояние → клип

| Состояние | Без оружия | Пистолет | Автомат / дробовик / винтовка |
|---|---|---|---|
| Стоит | unarmed_idle | pistol_idle | rifle_idle, в прицеле rifle_aim |
| Идёт вперёд / назад | unarmed_walk_f / _b | pistol_walk_f / _b | rifle_walk_f / _b |
| Идёт вбок | unarmed_walk_l / _r | pistol_walk_l / _r | rifle_walk_l / _r |
| Бежит | unarmed_run_f / _b (вбок — нет) | pistol_run_f / _b (вбок — нет) | rifle_run_f / _b / _l / _r |
| Спринт | — | — | rifle_sprint |
| Ранен (<35% HP), шагом вперёд | injured_walk | injured_walk | — (у клипа руки свободны) |
| Присел | unarmed_crouch_idle | pistol_crouch_idle | rifle_crouch_idle, в прицеле rifle_crouch_aim |
| Идёт вприсядку | rifle_crouch_walk_* (своих нет) | rifle_crouch_walk_* (своих нет) | rifle_crouch_walk_f / _b / _l / _r |
| Лежит | prone_move_b (стоп-кадр) | prone_aim | prone_aim |
| Ползёт назад / вперёд | prone_move_b / он же обратным ходом | то же | то же |
| Тяжело ранен | downed_fall (с разбега) / downed_fall_still, последний кадр | то же | то же |

Одиночные клипы (событие от Player / Marauder):

| Событие | Стоя | В приседе | Лёжа |
|---|---|---|---|
| Выстрел | rifle_fire (у пистолета — нет) | crouch_fire | prone_fire |
| Перезарядка | rifle_reload, на ходу reload_move | — | prone_reload |
| Достать оружие | pistol_draw / rifle_draw | — | — |
| Граната | grenade_throw (оружие спрятано) | — | prone_throw |
| Попадание | hit | — | — |
| Поднять предмет | pickup (оружие спрятано) | — | — |

Смерть (`death_clip`): лёжа или раненым — death_prone; взрыв — death_blast; в приседе —
death_crouch / death_crouch_head; в голову — death_head_front / death_head_back; иначе по стороне
выстрела — death_front / death_back / death_right (слева — тоже death_right, зеркального нет).
Без модели Persona — прежний регдолл-манекен (запасной вариант).

## Есть в assets/animations, но не подключено

- **Переходы стоек:** `Pistol_Handgun Locomotion Pack/pistol stand to kneel`, `… kneel to stand`,
  `Crouch weapons/Crouch To Prone`, `Prone To Crouch Transition`, `Rifle/Rifle Kneel To Prone`,
  `Rifle Prone To Kneel` — сейчас стойка меняется сменой клипа с плавным переходом 0.16 с.
- **Перелезание и бросок на землю** (механика есть — `Vault`, `_try_dive`, анимации нет):
  `jump away/Jump low with rifle Forward`, `Jumping Over Into Combat`, `Jump Away`.
- **Лёжа:** `prone/Prone Left Turn`, `Prone Right Turn`, `Rifle/Rifle Prone Hit Reaction`,
  `prone/Moving Backward In Crawl Position`.
- **Бросок гранаты на бегу:** `run grenades/Run And Throw Grenade`.
- **Реакция на попадание с пистолетом:** `pistol/Hit Reaction`, `Hit Reaction (1)`.
- Прыжки (`Pro Rifle Pack/jump *`, `Shooter Pack/jump *`) — прыжка в игре нет.

## Нет совсем (нужно скачать с Mixamo на Persona / любой скелет Mixamo)

| Что | Где нужно | Сейчас |
|---|---|---|
| Пистолет: прицеливание, выстрел, перезарядка | игрок и мародёры с пистолетом | поза pistol_idle, без отдачи и перезарядки |
| Бег вбок с пистолетом и без оружия | стрейф бегом | ходьба вперёд |
| Без оружия / с пистолетом: ходьба вприсядку | присед с пистолетом, без ствола | ноги от автоматной ходьбы |
| Ползком вперёд | лёжа, вперёд | ползание назад обратным ходом |
| Лечение (бинт, аптечка, шприц) | Meds, обезболивающее | нет |
| Взаимодействие: дверь, рубильник, ключ | двери, щитовая, генератор | нет |
| Обыск ящика / тела | лут | нет (pickup только на поднятие) |
| Тащить раненого, нести на плече, поднять раненого | downed: тащить / поднять / «несёшь Антона» | поза нокаута у раненого, у тащащего — обычная ходьба |
| Смерть слева | death_clip | death_right |
| Лестница, сесть, осмотр оружия, ПНВ на глаза | — | нет |

Mixamo: выбрать персонажа «Y Bot» или загрузить Persona, скачать FBX Binary, **Without Skin**,
30 fps, для циклов — In Place; положить в `assets/animations/<папка>/`, прописать в
`tools/character_clips.json`, перезапечь (см. выше). Имя клипа задаёт поведение: `idle`, `walk`,
`run`, `sprint`, `prone_move` в имени — клип зациклен.

## Проверка

- `tools/godot.cmd --headless res://tools/anim_test.tscn` — ходьба при 144 к/с, спринт, присед и
  ходьба вприсядку (ступни на полу), лёжа (таз у земли), оружие в руке во всех стойках.
- `tools/godot.cmd res://tools/weapons_test.tscn` — мародёр умер: своя модель, грудь ниже 0.7 м;
  снимок `wt_death`.
