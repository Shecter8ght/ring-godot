extends Node
## Голограф ЛУМАР H1 ночью, от первого лица в прицеле: метка рисуется шейдером — форма, цвет и толщина
## из настроек (Settings.reticle); под ПНВ на голове окно остаётся прозрачным, метка тускнеет; ночной
## режим окна (sight_nv) показывает усиленную картинку только в стекле; окно настройки открывается.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/lumar_reticle_shots.tscn → docs/screens/lumar_ret_*.png

const MODS := {"optic_primary": "optic_holo_01"}

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "off"}
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for mm in level.get_node("Marauders").get_children():
		mm.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	me.inventory.equipment = {"eyes": ItemDb.make("nvg", 1)}
	await _frames(5)
	var key: String = String(me.weapon_keys()[0])
	me.set_sandbox_mods(key, MODS)
	me._switch(key, false)
	await _frames(5)
	var at := SectorBuilder.polar(-104.0, 72.0)
	var look := SectorBuilder.polar(-97.0, 67.0) + Vector3(0, 1.2, 0)
	me.global_position = at + Vector3(0, 0.1, 0)
	CameraRig.first_person_mode = true
	Input.action_press("aim")
	await _frames(12)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var d := look - me.eye_position()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
	await _frames(60)
	_check("у прицела в руках найдены метка и стекло", rig._sight_reticles.size() == 1 and rig._sight_lenses.size() == 1, "%d / %d" % [rig._sight_reticles.size(), rig._sight_lenses.size()])
	if rig._sight_reticles.is_empty():
		get_tree().quit(1)
		return
	var mark := rig._sight_reticles[0].material_override as ShaderMaterial
	var glass := rig._sight_lenses[0].material_override as ShaderMaterial
	# формы и цвета
	for row: Array in [[1, 0, 1, "ring_red"], [2, 1, 2, "chevron_green_bold"], [0, 2, 2, "dot_amber_bold"], [3, 3, 0, "cross_blue_thin"]]:
		Settings.reticle = {"shape": int(row[0]), "color": int(row[1]), "bold": int(row[2])}
		await _frames(8)
		_check("метка: форма %d, цвет %d, толщина %d — параметры дошли до шейдера" % [int(row[0]), int(row[1]), int(row[2])],
			int(mark.get_shader_parameter("shape")) == int(row[0]) and is_equal_approx(float(mark.get_shader_parameter("bold")), float(SightMenu.BOLDS[int(row[2])][0])), "")
		_save("lumar_ret_" + String(row[3]))
	Settings.reticle = {"shape": 1, "color": 0, "bold": 1}
	# ПНВ на голове: окно прозрачное, метка тусклая
	me.nvg_on = true
	await _frames(40)
	_check("ПНВ на голове: стекло не бликует, метка приглушена", is_equal_approx(float(glass.get_shader_parameter("head_nvg")), 1.0)
		and float(mark.get_shader_parameter("energy")) <= float(Balance.LUMAR.nvg_energy) + 0.001, str(mark.get_shader_parameter("energy")))
	_save("lumar_ret_head_nvg")
	me.nvg_on = false
	await _frames(30)
	# ночной режим окна
	_save("lumar_ret_dark")
	rig.sight_nv = true
	await _frames(20)
	_check("ночной режим окна включён в стекле", is_equal_approx(float(glass.get_shader_parameter("window_nv")), 1.0), "")
	_save("lumar_ret_window_nv")
	me.nvg_on = true
	await _frames(20)
	_check("с ПНВ на голове ночной режим окна не накладывается", is_equal_approx(float(glass.get_shader_parameter("window_nv")), 0.0), "")
	me.nvg_on = false
	rig.sight_nv = false
	# окно настройки
	Input.action_release("aim")
	await _frames(10)
	Input.action_press("sight_menu")
	await _frames(2)
	Input.action_release("sight_menu")
	await _frames(10)
	_check("клавиша открывает окно настройки прицела", rig._sight_menu != null and rig._sight_menu.is_open(), "")
	if rig._sight_menu:
		# режим окна — в том же окне настройки, парой кнопок «Обычный / Ночной»
		for mode: String in ["Ночной (NV)", "Обычный"]:
			for raw: Node in rig._sight_menu.find_children("*", "Button", true, false):
				if (raw as Button).text == mode:
					(raw as Button).pressed.emit()
					break
			await _frames(4)
			_check("окно настройки: режим окна «%s»" % mode, rig.sight_nv == (mode != "Обычный"), "")
			if mode != "Обычный":
				_save("lumar_ret_menu")
		rig._sight_menu.close_ui()
	print("lumar_reticle_shots: провалено %d" % _fails)
	get_tree().quit(_fails)


func _save(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
