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

В выданном файле экран выключен. Заводская отделка подготовлена к просмотру, ещё не принята.
Отпечатки, износ, игровой bake/LOD, хват и интерфейс телефона сюда не включены.
