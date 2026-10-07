@tool
extends EditorPlugin
## Автоматизация редактора для инструментов (tools/bake_shelter_light.cmd). Запекание LightmapGI есть
## только в редакторе — кнопкой «Bake Lightmaps» у выделенного узла; плагин открывает сцену, выделяет
## узел, нажимает кнопку, сохраняет сцену и закрывает редактор. Без переменной окружения
## RING_BAKE_LIGHTMAP (путь res:// к сцене) ничего не делает — обычной работе в редакторе не мешает.


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
	var glass: StandardMaterial3D = load(ShelterWeather.GLASS) as StandardMaterial3D
	var glass_was: Array = [glass.emission, glass.emission_energy_multiplier]
	var report: PackedStringArray = PackedStringArray()
	for scene: String in job.split(";", false):
		var result: String = await _bake_one(tree, scene)
		report.append(result)
		print("RING_BAKE_STEP " + result)
	glass.emission = glass_was[0]
	glass.emission_energy_multiplier = glass_was[1]
	var failed: bool = false
	for r: String in report:
		failed = failed or r.begins_with("FAIL")
	_done(1 if failed else 0, "; ".join(report))


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
	EditorInterface.save_scene()
	await _frames(tree, 20)
	return "%s за %d с" % [expected.get_file(), (Time.get_ticks_msec() - started) / 1000]


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
