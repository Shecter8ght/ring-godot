extends Node
## ВЕРАС-54 днём под открытым небом (Пригород, ясно): у бедра, проверка магазина у глаз (держать R), в прицеле — на
## солнце и от солнца. Материалы оружия под небом (отражения, блики): в помещении и в тёмной студии Blender отражать
## нечего, «стеклянный» глянец виден только тут (владелец 2026-10-19).
## tools/godot.cmd res://tools/veras_outdoor_shots.tscn → docs/screens/veras_outdoor_*.png (VERAS_OUT_TAG=имя — приставка)

const ID := "wpn_ar_01"
const OUT := "res://docs/screens/"

var _player: Player
var _camera: CameraRig
var _tag: String = ""


func _ready() -> void:
	_tag = OS.get_environment("VERAS_OUT_TAG")
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/zone01_mall.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	for _i in range(3000):
		_player = get_tree().get_first_node_in_group("players") as Player
		_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
		if _player != null and _camera != null:
			break
		await get_tree().process_frame
	if _player == null:
		push_error("veras_outdoor_shots: игрок не появился")
		get_tree().quit(1)
		return
	var marauders: Node = level.get_node_or_null("Marauders")
	if marauders:
		for enemy: Node in marauders.get_children():
			enemy.process_mode = Node.PROCESS_MODE_DISABLED
			(enemy as Node3D).visible = false
	_player.health.hp = 100000.0
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(2.0).timeout
	await _equip()
	print("veras_outdoor_shots: игрок ", _player.global_position)
	for side: Array in [["sun", 0.0], ["away", PI]]:
		_camera._look_yaw = float(side[1])
		_camera._look_pitch = 0.15
		await get_tree().create_timer(0.8).timeout
		await _shot("hip_" + String(side[0]))
		_player.ammo = 17
		Input.action_press("reload")
		await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 1.6).timeout
		await _shot("check_" + String(side[0]))
		Input.action_release("reload")
		await get_tree().create_timer(3.0).timeout
		Input.action_press("aim")
		await get_tree().create_timer(float(_player.spec().aim_time) + 0.4).timeout
		await _shot("ads_" + String(side[0]))
		Input.action_release("aim")
		await get_tree().create_timer(0.6).timeout
	get_tree().quit(0)


func _equip() -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": {},
		"mag": {"id": WeaponDb.default_mag(ID), "ammo": WeaponDb.default_ammo("545x39"), "rounds": 30}, "sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.6).timeout


func _shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var name: String = "veras_outdoor_%s%s.png" % [_tag + "_" if _tag != "" else "", label]
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(OUT + name))
	print("veras_outdoor_shots: ", name)
