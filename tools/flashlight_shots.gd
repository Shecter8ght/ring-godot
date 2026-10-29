extends Node
## Фонари в паркинге «Проспекта»: прежнее и новое пятно в одинаковых условиях, прицел,
## светлая стена, обычное освещение, мощный фонарь и комбо. Профиль игрока — отдельный.
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/flashlight_shots.tscn
## FLASHLIGHT_COMPARE=soft — сравнить с первой мягкой версией (32°); FLASHLIGHT_OUTPUT — папка кадров.

const OUT: String = "res://docs/screens/flashlight_eft_20261029"
const AISLE: Vector3 = Vector3(-174.0, -7.22, -60.4)
const AISLE_TARGET: Vector3 = Vector3(-158.0, -5.6, -60.4)
const WALL: Vector3 = Vector3(-170.0, -7.22, -81.0)
const WALL_TARGET: Vector3 = Vector3(-170.0, -5.5, -88.0)

var level: Node3D
var me: Player
var rig: CameraRig
var lamps: Array[Light3D] = []
var key: String
var output_dir: String = OUT
var compare_soft: bool = false


func _enter_tree() -> void:
	Profile.use_file("user://profile_flashlight_shots.json", true)


func _ready() -> void:
	compare_soft = OS.get_environment("FLASHLIGHT_COMPARE") == "soft"
	var requested_output: String = OS.get_environment("FLASHLIGHT_OUTPUT")
	if not requested_output.is_empty():
		output_dir = requested_output
	if DisplayServer.get_name() == "headless":
		push_error("flashlight_shots: для снимков нужен оконный запуск")
		get_tree().quit(1)
		return
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "off"}
	for singleton: String in ["Quests", "Contracts", "Pause"]:
		get_node("/root/" + singleton).process_mode = Node.PROCESS_MODE_DISABLED
	await get_tree().process_frame
	level = (load("res://scenes/levels/prospekt.tscn") as PackedScene).instantiate() as Node3D
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while Raid.current == null or Raid.current.local_player() == null or not bool(level.get("_nav_baked")):
		await get_tree().process_frame
	me = Raid.current.local_player()
	rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	rig.set_process_unhandled_input(false)
	me.health.invulnerable = true
	for node_name: String in ["Population", "Rivals", "Events"]:
		var system: Node = level.get_node_or_null(node_name)
		if system != null:
			system.process_mode = Node.PROCESS_MODE_DISABLED
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.queue_free()
	var hud: CanvasLayer = level.get_node_or_null("HUD") as CanvasLayer
	if hud != null:
		hud.hide()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output_dir))
	me.loadout_mode = false
	key = String(me.weapon_keys()[0])
	me.set_sandbox_mods(key, {"side_right": "tac_flashlight_01"})
	me._switch(key, false)
	me.carry_low = false
	CameraRig.first_person_mode = true
	await _frames(90)
	for node: Node in level.find_children("*", "OmniLight3D", true, false):
		var lamp: OmniLight3D = node as OmniLight3D
		if lamp.global_position.y < -0.5 and lamp.visible and not me.is_ancestor_of(lamp) and not rig.is_ancestor_of(lamp):
			lamps.append(lamp)
			lamp.hide()
	_place(AISLE, AISLE_TARGET)
	await _frames(150)
	await _save("01_aisle_off")
	me._toggle_tac("light")
	await _frames(45)
	_legacy(true)
	await _frames(120)
	await _save("02_aisle_before")
	_legacy(false)
	await _frames(120)
	await _save("03_aisle_after")
	Input.action_press("aim")
	await _frames(90)
	await _save("04_aim_after")
	Input.action_release("aim")
	_place(WALL, WALL_TARGET)
	_legacy(true)
	await _frames(120)
	await _save("05_wall_before")
	_legacy(false)
	await _frames(120)
	await _save("06_wall_after")
	me._toggle_tac("light")
	await _frames(120)
	await _save("07_wall_off")
	# Стационарные лампы снова горят: свет фонаря добавляется к обычному свету карты.
	for lamp: Light3D in lamps:
		lamp.show()
	await _frames(120)
	await _save("08_lit_wall_off")
	me._toggle_tac("light")
	await _frames(120)
	await _save("09_lit_wall_on")
	for lamp: Light3D in lamps:
		lamp.hide()
	_place(AISLE, AISLE_TARGET)
	await _attachment("tac_flashlight_hp_01", "side_right")
	await _save("10_powerful_after")
	await _attachment("tac_combo_01", "underbarrel")
	await _save("11_combo_after")
	print("flashlight_shots: готово · ", output_dir)
	get_tree().quit()


func _place(at: Vector3, target: Vector3) -> void:
	me.global_position = at
	me.velocity = Vector3.ZERO
	var direction: Vector3 = (target - (at + Vector3.UP * 1.62)).normalized()
	rig._look_yaw = atan2(direction.x, direction.z)
	rig._look_pitch = asin(direction.y)


## Прежние параметры нужны только для парного кадра; штатный профиль берётся из тех же данных, что в рейде.
func _legacy(enabled: bool) -> void:
	var spec: Dictionary = WeaponDb.attachment("tac_flashlight_01").light
	var before: Dictionary = {"angle": 22.0, "energy": 6.0, "indirect": 1.3, "specular": 0.45}
	if compare_soft:
		before = {"angle": 32.0, "energy": 3.2, "indirect": 0.8, "specular": 0.4}
	var selected: Dictionary = before if enabled else spec
	for node: Node in rig.find_children("Flashlight*", "SpotLight3D", true, false):
		var beam: SpotLight3D = node as SpotLight3D
		beam.light_projector = null if enabled and not compare_soft else WeaponMods.FLASHLIGHT_BEAM
		beam.spot_angle = float(selected.angle)
		beam.light_color = Color(1.0, 0.96, 0.9) if enabled and not compare_soft else Color(0.96, 0.98, 1.0)
		beam.light_indirect_energy = float(selected.indirect)
		beam.light_specular = float(selected.specular)
		var energy: float = float(selected.energy)
		beam.set_meta("condition_energy", energy)
		beam.light_energy = energy


func _attachment(id: String, mount: String) -> void:
	me.set_sandbox_mods(key, {mount: id})
	await _frames(60)
	if not me.light_on:
		me._toggle_tac("light")
	await _frames(120)


func _save(label: String) -> void:
	var active: int = 0
	for node: Node in rig.find_children("Flashlight*", "SpotLight3D", true, false):
		var beam: SpotLight3D = node as SpotLight3D
		if beam.is_visible_in_tree():
			active += 1
			print("flashlight_shots: ", label, " · energy=", beam.light_energy, " angle=", beam.spot_angle,
				" projector=", beam.light_projector != null, " shadow=", beam.shadow_enabled)
	if me.light_on != (active > 0):
		push_error("flashlight_shots: состояние фонаря не совпало с видимым светом")
		get_tree().quit(1)
		return
	await RenderingServer.frame_post_draw
	var path: String = ProjectSettings.globalize_path(output_dir.path_join(label + ".png"))
	var error: Error = get_viewport().get_texture().get_image().save_png(path)
	print("flashlight_shots: ", label, " · error=", error)
	if error != OK:
		get_tree().quit(1)


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().process_frame
