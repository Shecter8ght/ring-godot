# UCUPaint: API, маски и фактические входы

Проверенный локальный контекст: Blender 5.2.2 LTS, расширение `bl_ext.blender_org.ucupaint`, UCUPaint 2.4.9. Примеры описывают именно эту версию. Выясни путь/версию установленного расширения, свойства RNA, enum и реализацию операций перед использованием в другой версии. Старые пакеты могут иметь другой модуль. Не подменяй недоступный UCUPaint самодельной группой без сообщения владельцу.

## Нативный стек и рабочая копия

Отключай автоматическое сохранение пользовательских настроек перед включением аддона в фоне:

```python
import bpy, addon_utils, importlib
bpy.context.preferences.use_preferences_save = False
addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
U = importlib.import_module('bl_ext.blender_org.ucupaint')
print(U.common.get_current_version_str())
```

Активируй нужный mesh и слот материала. Для нового настоящего стека в 2.4.9 применялась операция:

```python
bpy.ops.wm.y_quick_ypaint_node_setup(
    tree_name='Asset • editable surface',
    color=True, metallic=True, roughness=True, normal=True, ao=False,
    switch_to_material_view=False, target_bsdf_name=principled.name)
```

Нативную группу определяли по `node.type == 'GROUP'`, наличию `node.node_tree.yp` и `node.node_tree.yp.is_ypaint_node`. Не выбирай группу по одному имени. При сохранении существующего стека ищи назначение каналов в `tree.yp.channels`; фиксированные индексы Color=0, Normal=3 верны только для известной последовательности конкретного исходника.

`U.Layer.add_new_layer` создаёт нативный слой; в кейсе назначение `designated_index=0` вставляло слой наверх, поэтому порядок нужно было проверять. Режимы normal/height проверяй по enum; `height_blend_type='ADD'` в этой версии отсутствовал. В кейсе использовался OVERLAY. Нейтраль высоты определяется режимом/настройкой Bump; для midpoint=0.5 карта должна иметь соответствующий фон.

## Не путай RNA со значением группы

В 2.4.9 изменение некоторых свойств из Python не гарантировало обновление фактического входа группы. Это касалось интенсивности, override и высоты/силы normal. Синхронизируй через API и сверяй прочитанное значение:

```python
entity.intensity_value = value
U.common.set_entity_prop_value(entity, 'intensity_value', value)
actual = U.common.get_entity_prop_value(entity, 'intensity_value')
assert abs(actual - value) < 1e-6
```

RGB override в кейсе присваивался как `mathutils.Color`, а прочитанный socket возвращал RGBA: для проверки цвета сравнивались первые три значения. Не присваивай имя изображения свойству `source`, если оно хранит имя узла. У Principled печатный список socket-меток не всегда совпадал с допустимыми ключами `inputs[...]`: попытка `inputs['Weight']` дала KeyError. Уточняй реальные идентификаторы и версии, не добавляй угадываемые параметры.

После структурного изменения стеков в 2.4.9 применялись:

```python
U.input_outputs.check_all_channel_ios(tree.yp, reconnect=True)
U.input_outputs.check_start_end_root_ch_nodes(tree)
for layer in tree.yp.layers:
    U.node_connections.reconnect_layer_nodes(layer)
U.node_connections.reconnect_yp_nodes(tree)
```

Не воспринимай эти вызовы как замену проверке подключений и рендера. У стекла проверь, что постоянная Transmission остаётся подключена корректно и группы управляют нужными каналами.

## Критическая ошибка: область действия Ramp

Два внешне похожих варианта дают разные результаты:

- Image/AO × Noise, затем отдельная маска типа MODIFIER/RAMP — порог преобразует уже накопленную маску слоя.
- Ramp как модификатор **внутри** маски Noise, затем Image/AO × этот Noise — порог применяется только к шуму.

В ЛУМАР первый вариант срезал слабые пиксели грязи, отпечатков и средних царапин. Все слои были включены, но значительная часть эффектов отсутствовала в финальном изображении. Правильный второй вариант сохранил мягкую контактную маску и добавил нерегулярность.

Для 2.4.9:

```python
MM = importlib.import_module(U.__name__ + '.MaskModifier')
MM.add_new_mask_modifier(noise_mask, 'RAMP')  # возвращает None
modifier = noise_mask.modifiers[-1]
mask_tree = U.common.get_mask_tree(noise_mask)
ramp_node = mask_tree.nodes[modifier.ramp]
ramp_node.color_ramp.elements[0].position = lo
ramp_node.color_ramp.elements[1].position = hi
```

Для уже существующего локального Ramp редактируй его, не добавляй бесконечную цепочку. Помощник `scripts/ucupaint_helpers.py` делает это с проверкой типа Noise и точной версии. Он не создаёт материал, не сохраняет файл и не исправляет произвольную сцену автоматически.

Отдельный накопленный MODIFIER уместен, если именно такова цель: например, инверсия единственной AO-маски до умножения на шум. Не меняй все Ramp массово без анализа графа. В исправлении ЛУМАР старые накопленные Range-маски были отключены, параметры перенесены внутрь предшествующих Noise; старые слои оставлены редактируемыми.

## Узкие проверенные помощники

Пример в Blender после создания настоящего стека и Noise-маски:

```python
import sys
sys.path.insert(0, str(skill_dir / 'scripts'))
from ucupaint_helpers import load_ucupaint, sync_property, local_noise_ramp, reconnect
U = load_ucupaint()
sync_property(U, layer, 'intensity_value', 0.4)
local_noise_ramp(U, noise_mask, 0.28, 0.66)
reconnect(U, tree)
```

Для override/height helper принимает фактическое имя свойства и значение; за включение override, выбор типа нормали, назначение UV и принадлежность канала отвечает вызывающий код. В случае несовпадения RNA/socket он выдаёт ошибку, которую нужно решить до упаковки. Не скрывай ошибку и не продолжай выдачу полусобранного файла.

## Контакт инструмента и грязь

После исправления порога проявилась старая плохая маска: полосы ToolWear покрывали всю головку винта и выглядели как ткань/«ёлочка». Для винтов/регулировок ЛУМАР её заменили на EDGE_DETECT × атрибут `V9ToolContact` × локально пороговый Noise. Атрибут был 1 на объектах инструментального контакта и 0 на остальных; кромка шлица/фаски стала главным местом повреждения. Это пример разграничения по деталям, не обязательное имя атрибута для любого ассета.

Для грязи полезны разные масштабы: явный шов/основание детали, инверсия AO, мелкая нерегулярность отложения. Маску проверяй в изоляции, затем в шейдере; «включён слой 39» не подтверждает, что он заметен или размещён верно.

## Исполнение в фоне

Запускай Blender с `--background --factory-startup --python-exit-code 1 --python ...`. Без `--python-exit-code` Python-ошибка в кейсе могла оставлять код завершения 0. Проверяй завершение процесса, ожидаемые файлы и явный маркер успеха перед следующим зависимым шагом. Генератор карт должен закончиться до сборки `.blend`; запуск обоих одновременно дал отсутствующую карту BroadWear.

Используй отдельную рабочую копию и task-local кеши GPU, когда обычный кеш недоступен. В локальной среде OptiX на RTX 5070 Ti работал, но непишущийся кеш резко замедлял рендер; `OPTIX_CACHE_PATH` и `CUDA_CACHE_PATH` в рабочей папке решили это. Не изменяй глобальные настройки пользователя ради одного задания. Фоновые тесты не должны закрывать его Blender.
