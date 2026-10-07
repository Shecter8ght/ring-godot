@tool
extends EditorPlugin

var _glass: StandardMaterial3D
var _glass_was: Array = []
## Автоматизация редактора для инструментов (tools/bake_shelter_light.cmd). Запекание LightmapGI есть
## только в редакторе — кнопкой «Bake Lightmaps» у выделенного узла; плагин открывает сцену, выделяет
## узел, нажимает кнопку, сохраняет сцену и закрывает редактор. Без переменной окружения
## RING_BAKE_LIGHTMAP (путь res:// к сцене) ничего не делает — обычной работе в редакторе не мешает.
## RING_BAKE_QUALITY=draft — черновое (низкое качество, половинная плотность карты, в разы быстрее),
## иначе чистовое (высокое). RING_BAKE_ONLY=day_sun,night — только сцены, в имени которых есть
## одно из слов (варианты погоды убежища). Ошибки «Parameter "scenario" is null» (renderer_scene_cull)
## во время расчёта — внутренние у движка (зонды отражений), на результат не влияют.


func _enter_tree() -> void:
	var scene: String = OS.get_environment("RING_BAKE_LIGHTMAP")
	if scene != "":
		_bake.call_deferred(scene)


## job — путь сцены или несколько через «;»; «@файл» — список из файла (варианты погоды убежища).
func _bake(job: String) -> void:
	var tree: SceneTree = get_tree()
	if job.begins_with("@"):
		job = FileAccess.get_file_as_string(job.substr(1)).strip_edges()
	await _frames(tree, 120)
	# стекло окон меняется в памяти под каждый вариант — потом вернуть как было
	_glass = load(ShelterWeather.GLASS) as StandardMaterial3D
	_glass_was = [_glass.emission, _glass.emission_energy_multiplier]
	var glass: StandardMaterial3D = _glass
	var glass_was: Array = _glass_was
	var report: PackedStringArray = PackedStringArray()
	var only: PackedStringArray = OS.get_environment("RING_BAKE_ONLY").replace(" ", ",").split(",", false)
	for scene: String in job.split(";", false):
		if not only.is_empty() and not _wanted(scene, only):
			continue
		var result: String = await _bake_one(tree, scene)
		report.append(result)
		print("RING_BAKE_STEP " + result)
	glass.emission = glass_was[0]
	glass.emission_energy_multiplier = glass_was[1]
	var failed: bool = false
	for r: String in report:
		failed = failed or r.begins_with("FAIL")
	_done(1 if failed else 0, "; ".join(report))


## Сцена из списка RING_BAKE_ONLY: её вариант (Shelter_<вид>) совпадает со словом целиком
## («day_sun» не берёт «day_sun_off»; «day_sun_off» — отдельно).
func _wanted(scene: String, only: PackedStringArray) -> bool:
	var variant: String = scene.get_file().get_basename().trim_prefix("Shelter_")
	for w: String in only:
		if variant == w.strip_edges():
			return true
	return false


func _bake_one(tree: SceneTree, scene: String) -> String:
	EditorInterface.open_scene_from_path(scene)
	EditorInterface.set_main_screen_editor("3D")
	await _frames(tree, 60)
	var root: Node = EditorInterface.get_edited_scene_root()
	var lm: LightmapGI = root.get_node_or_null("LightmapGI") as LightmapGI if root else null
	if lm == null:
		return "FAIL %s: нет LightmapGI" % scene
	# вариант погоды убежища: Shelter_<вид>.tscn — та же погода, что ShelterWeather ставит в игре
	var variant: String = scene.get_file().get_basename().trim_prefix("Shelter_")
	for v: Array in ShelterWeather.bake_variants():
		if String(v[0]) == variant:
			ShelterWeather.apply_state(root, v[1], v[2], true)
	# черновое — быстро для проверки правок, чистовое — перед сборкой игры
	var draft: bool = OS.get_environment("RING_BAKE_QUALITY") == "draft"
	lm.quality = LightmapGI.BAKE_QUALITY_LOW if draft else LightmapGI.BAKE_QUALITY_HIGH
	lm.texel_scale = 0.5 if draft else 1.0
	lm.bounces = 2 if draft else 3
	EditorInterface.get_selection().clear()
	EditorInterface.get_selection().add_node(lm)
	EditorInterface.edit_node(lm)
	await _frames(tree, 20)
	var button: Button = _find_button(EditorInterface.get_base_control())
	if button == null:
		return "FAIL %s: кнопка запекания не найдена" % scene
	var expected: String = scene.get_basename() + ".lmbake"
	# редактор запекает в файл данных, уже назначенный узлу (у наследника это был бы файл основы) —
	# заранее назначить пустой файл варианта
	if not ResourceLoader.exists(expected):
		ResourceSaver.save(LightmapGIData.new(), expected)
	var target: LightmapGIData = ResourceLoader.load(expected, "", ResourceLoader.CACHE_MODE_REPLACE) as LightmapGIData
	lm.light_data = target
	var stamp: int = FileAccess.get_modified_time(expected)
	var started: int = Time.get_ticks_msec()
	button.pressed.emit()
	# готово, когда файл варианта перезаписан и узел снова держит данные этого файла
	while not (FileAccess.get_modified_time(expected) > stamp and lm.light_data and lm.light_data.resource_path == expected) and Time.get_ticks_msec() - started < 900000:
		await _frames(tree, 30)
	if FileAccess.get_modified_time(expected) <= stamp:
		return "FAIL %s: свет не запёкся (запись ушла в %s)" % [scene, lm.light_data.resource_path if lm.light_data else "—"]
	# стекло окон менялось в памяти под вариант — не дать редактору записать это в материал
	_glass.emission = _glass_was[0]
	_glass.emission_energy_multiplier = _glass_was[1]
	EditorInterface.save_scene()
	await _frames(tree, 20)
	return "%s за %d с%s" % [expected.get_file(), (Time.get_ticks_msec() - started) / 1000, " (черновое)" if draft else ""]


func _find_button(n: Node) -> Button:
	for b: Node in n.find_children("*", "Button", true, false):
		var t: String = (b as Button).text
		if t.findn("bake lightmap") >= 0 or (t.findn("запе") >= 0 and t.findn("освещ") >= 0):
			return b as Button
	return null


func _frames(tree: SceneTree, n: int) -> void:
	for i: int in range(n):
		await tree.process_frame


func _done(code: int, message: String) -> void:
	print("RING_BAKE %d %s" % [code, message])
	get_tree().quit(code)
