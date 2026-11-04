# Личный смартфон — геометрия

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
Форма v02 требует принятия. Производственных UV, текстур и импорта в игру здесь нет.
В v02 блок камер поднят на 6,2 мм; верхний и боковой отступы по 2,3 мм.
`render <файл.blend> back camera_macro` обновляет только виды задней стороны и камер.
