# Личный смартфон — форма и заводская отделка

Выбор владельца: корпус в духе iPhone Pro Max, постоянный телефон сохраняется после гибели.
Референсы, решения и предложение интерфейса: [docs/assets/quest_phone.md](../../docs/assets/quest_phone.md).

```powershell
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/build.py -- build
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/build.py -- verify
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/build.py -- render
```

`build` записывает геометрический кандидат `_asset_src/quest_phone/models/QuestPhone_v02.blend`.
Не перезаписывать принятую или вручную изменённую версию: сделать новый номер и сохранить источник.
`verify` повторно открывает файл, проверяет evaluated-геометрию, номинальные размеры и вход USB-C.
`render` повторно открывает файл и снимает четыре нейтральных вида в `previews`.

`_asset_src` и скачанные референсы не коммитятся. Выдача владельцу — отдельная папка
`E:/Models Blender/PROPS/QuestPhone`, как у других предметных моделей.
Форма v02 принята владельцем 2026-11-04. Игрового экспорта и импорта здесь нет.
В v02 блок камер поднят на 6,2 мм; верхний и боковой отступы по 2,3 мм.
`render <файл.blend> back camera_macro` обновляет только виды задней стороны и камер.

Отделка — отдельная копия `QuestPhone_factory_v01.blend`; принятую геометрию не перезаписывать.
Выбор: графит, матовое заднее стекло, атласная металлическая рамка, ободы камер в цвет рамки.

```powershell
python -X utf8 tools/quest_phone/finish_setup.py
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/factory.py -- build
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/factory.py -- check
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/factory.py -- render back front camera_macro bottom
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/factory.py -- glass
```

Нужен установленный `bl_ext.blender_org.ucupaint` 2.4.9. `finish_setup.py` добавляет только
отсутствующие рецепты и создаёт первичную спецификацию; существующий выбор не перезаписывает.
`finish-spec.json` рядом с этим README — снимок выданного выбора; рабочая спецификация и
спецификация в библиотеке находятся рядом с папкой `models`. `factory.py` читает рабочую
спецификацию, берёт числа из каталога, применяет `overrides`, строит десять нативных стеков
UCUPaint и студию с упакованным HDRI. Процедурная микроструктура не требует файлов карт.
`glass` рендерит временную шахматную подложку за настоящим стеклом с обеих сторон и ничего
не сохраняет в модель. `check` заново открывает файл и проверяет фактические цветовые
значения, шероховатость/металличность, подключения каналов и встроенные изображения.

В выданном файле экран выключен. Заводская отделка factory_v01 принята владельцем 2026-11-04 («принимаю»).
Принятый .blend не перезаписывать: последующие изменения — в новой версии.
Отпечатки, износ, игровой bake/LOD, хват и интерфейс телефона сюда не включены.

## Игровая версия

`game.py` читает принятый factory_v01 из библиотеки, проверяет его hash и создаёт производные
файлы в `_asset_src/quest_phone/game/`. Мастер не сохраняет. Команды в таком порядке:

```powershell
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/game.py -- lp
# тем же вызовом Blender: bake -> pack -> export
tools/godot.cmd --headless --import
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/quest_phone/game.py -- imports
tools/godot.cmd --headless --import
tools/godot.cmd --headless res://tools/quest_phone_shots.tscn -- check
tools/godot.cmd --windowed --resolution 1600x900 res://tools/phone_test.tscn
tools/godot.cmd --windowed --resolution 1600x900 res://tools/phone_grip_lab.tscn
```

4910/5000 треугольников, один 2K атлас, отдельные экран/оптика/кнопки, штатный LOD импортёра.
`compare.py` даёт native/baked с одинаковым светом. `phone_net_test.tscn -- host`, затем два
`-- client` (порт 17798) проверяют три настоящих peer. `phone_mission_shots.tscn` снимает
купе и устройство на уровне с отдельным тестовым профилем. Экран — два SubViewport,
постоянный инвентарь — PhoneGear, стартовый хват — phone_grip.json + профиль @phone.
Ограничения UV, стекла и анимации, управление и сохранения — `docs/assets/quest_phone.md`.

### Хват в Blender

`tools/godot.cmd --windowed --resolution 1280x900 res://tools/phone_grip_export.tscn`
выгружает фактическую позу и экран в `_asset_src/quest_phone/grip/` без сохранения профиля.
Затем Blender `--background --factory-startup --python-exit-code 1 --python tools/quest_phone/hand_grip_blender.py`
собирает `E:/Models Blender/новые руки/Phone_Grip_starter_v01.blend`: существующие руки,
игровой телефон, Pose Mode, кадр 1, упакованные текстуры, три камеры и встроенная инструкция.
Скрипт откажется перезаписать уже выданный файл: следующую сборку делать новой версией.
Сохранённая владельцем поза потребует отдельного переноса в Godot.

Текущий файл владельца — `E:/Models Blender/новые руки/Phone_Grip_owner_v02.blend`.
В нём статичная поза без Action: обычный Ctrl+S сохраняет правку без дополнительных ключей.
Первый v01 остаётся архивом: старые ключи при обычном открытии перекрывали его сохранённые
pose-каналы. `recover_grip.py` восстанавливает их через `grip_native.py` в новой копии;
существующую выдачу не перезаписывает.

После сохранения правки: Blender `--background --factory-startup --python-exit-code 1
--python tools/quest_phone/import_grip.py -- --export` (при необходимости `--source <файл>`).
По умолчанию читает owner_v02, сохраняет снимок по hash, проверяет rest, конвертирует
оси и пишет `data/phone_grip_pose.json`. Данные retarget встроены в owner_v02, fallback —
первоначальный `phone_pose.json`. Для одной проверки без рендеров — `--no-render`.
В игре применяется авторская поза целиком, без повторного уменьшения кисти и CCD пальцев.
