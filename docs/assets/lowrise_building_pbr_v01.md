# Двухэтажный корпус R06 — PBR v01, 2026-10-24

Владелец принял показанную форму: «Форма подходит — переходи к текстурам».
На этой геометрии выполнена отдельная текстурная версия по трём фотографиям;
образец игровой отделки — ранее присланные владельцем кадры Tarkov.

Открыть [R06_building_pbr_v01.blend](<E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references/assets/R06_building/pbr_v01/model/R06_building_pbr_v01.blend>).
[Состояние, источники и управление слоями](<E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references/assets/R06_building/pbr_v01/asset-state.md>).
Принятый R06_building_geometry_v02.blend сохранён отдельно без перезаписи.
Остальные пять исправляемых предметов этим этапом не затронуты.

## Материалы

Светлая старая штукатурка с фотозерном, тональными пятнами окраски, наплывами
между этажами, разной шероховатостью и тонкими трещинами. Крупные геометрические
трещины и отслоения до кирпича сохранены. Отдельные маски привязаны к подоконникам,
карнизу и контакту с землёй; потёки не размножены одинаковым штампом.

Белый ПВХ, уплотнения EPDM и стекло отделены от металлических отливов. Есть
окрашенные красно-коричневые двери, жёлто-охристые помятые козырьки с локальным
износом краски у сгибов, кровля и цоколь. Рельеф материала — Bump/Normal, сетка
не смещается. Вывеска «УЧЕБНЫЙ КОРПУС» и адрес «17 А» остались вымышленными.

Blender 5.2.2 LTS, настоящий UCUPaint 2.4.9: **22 материала, 91 слой, 59 масок**.
У 1015 mesh-объектов — MetricUV, WeatherUV и PartUV: метрические проекции тайлов,
уникальные маски фасада и проекции деталей. Это не уникальный игровой атлас.
Игровое запекание, оптимизация, LOD и коллизии не выполнялись.

## Происхождение

- [Painted Plaster Wall](https://polyhaven.com/a/painted_plaster_wall), Amal Kumar,
  — фотозерно, Color/Roughness/Normal. Тон побелки — отдельный слой.
- Red Bricks 04 (Rob Tuytel), Rusty Metal Sheet (Amal Kumar), Rough Concrete,
  Wood Planks Grey — существующий CC0-кэш проекта; license.txt в комплекте.
  Roughness отделена из G канала ARM. Из карты кирпича вырезана одна грань без
  кладочных швов: сами ряды уже смоделированы.
- HDRI Kloofendal Overcast Pure Sky, Greg Zaal — диагностический дневной свет.
- Маски из E:/Models Blender/Маски_АЛЬФА сохранены без изменения байтов;
  они подписаны как пользовательские, их лицензия CC0 не заявляется.
- Уникальные маски потёков, карниза, сырости и трещин синтетические,
  воспроизводятся seeded-генератором по координатам проёмов. Это не сканы.
- Три фотографии владельца сохранены в references/building_user без обработки;
  они задают отделку, не служат игровым albedo.

Лицензия наборов — [CC0 Poly Haven](https://polyhaven.com/license).
Источники, операции, размеры и хеши — manifest.json и sources.json;
цветовые пространства и соответствие внешних файлов datablock —
checks/image_manifest.json. Встроены **34 изображения**, внешние копии используют
относительные пути в dependencies/. Данные — Non-Color, BaseColor — sRGB.

## Проверено

- Файл повторно открыт из библиотеки на E; все 22 нативные группы UCUPaint
  подключены к Principled BSDF, фактические параметры каналов читаются.
- Хеши 34 встроенных изображений совпадают с внешними копиями; пути разрешаются,
  размеры и color space сохраняются после открытия.
- audit_source со strict-objects и require-packed сравнил 1020 объектов принятого
  источника и кандидата: изменения сеток/кривых/текста, иерархии, локальных матриц,
  имён/типов/видимости модификаторов и добавленные объекты отсутствуют. Это не
  полная проверка каждого параметра Blender и не оценка сходства с фото.
- Девять свежих видов получены из передаваемого .blend: общий, передний, задний,
  вход, отслоение, штукатурка, козырёк, общий ночной и крупный ночной.
  Ночная подсветка — диагностическая студия, не сцена Godot.

Отчёты: checks/native_validation.json, accepted_geometry_audit.json, delivery.json.
Текстуры подготовлены к оценке владельцем; их принятие не заявляется.

## Воспроизведение

Из корня проекта:

```powershell
python -X utf8 tools/urban_screens/v02/building_maps.py
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/urban_screens/v02/building_pbr.py -- preview damage_day plaster_day canopy_day
# После визуальной доводки:
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/urban_screens/v02/building_pbr.py -- build
& 'D:/ПРОГРАММЫ/Blender 5/blender.exe' --background --factory-startup --python-exit-code 1 --python tools/urban_screens/v02/building_verify.py
```

Перед building_delivery.py нужны успешные checks/native_validation.json и
accepted_geometry_audit.json (audit_source.py навыка weapon-asset-texturing).
`building_delivery.py --deliver` копирует только R06 PBR и обновляет его статус.
`building_verify.py -- --delivery` и `building_pbr.py -- render-delivery` запускаются
через Blender из проекта; `building_delivery.py --finalize` сверяет выдачу.
Принятая геометрия не перегенерируется при текстурировании.
