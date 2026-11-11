extends Node
## Ракетница Claude в настоящей игровой камере: стойка одной правой рукой, прицел по ПКМ, выстрел и
## перезарядка по кадрам. Модель в руках подменяется только в памяти этого теста (данные игры и
## подключённую ракетницу Codex тест не трогает); снимки — docs/screens/flare_claude_*.png.

const CONFIG := "res://assets/models/weapons/flare_gun_claude/flare_gun_claude_viewmodel.json"
const WORLD := "res://assets/models/weapons/flare_gun_claude/flare_gun_claude.glb"

var player: Player
var camera: CameraRig
var samples: Array[Dictionary] = []
var fails: int = 0


func _ready() -> void:
	Engine.max_fps = 60
	if DisplayServer.get_name() == "headless":
		print("flare_claude_shots: нужен запуск с окном")
		get_tree().quit(1)
		return
	get_window().content_scale_size = Vector2i(1600, 900)
	get_window().size = Vector2i(1600, 900)
	Profile.use_file("user://profile_flare_claude_shots.json", true)
	Profile.ensure()
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	# подмена модели в руках: описание оружия — общий словарь, правим его копию в памяти процесса
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CONFIG))
	var weapon: Dictionary = WeaponDb.weapon("signal_launcher")
	if weapon.is_empty():
		push_error("flare_claude_shots: в данных игры нет signal_launcher")
		get_tree().quit(1)
		return
	var vm: Dictionary = (weapon.get("viewmodel", {}) as Dictionary).duplicate(true)
	for key: String in ["scene", "fps", "clips", "ads_z", "hip_offset", "round_windows", "left_hand_windows", "events", "clearance_parts"]:
		vm[key] = cfg[key]
	weapon["viewmodel"] = vm
	weapon["asset"] = WORLD
	var stats: Dictionary = weapon.get("stats", {})
	stats["reload"] = float(cfg.reload_sec)
	stats["reload_empty"] = float(cfg.reload_sec)
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
		(enemy as Node3D).visible = false
	player = get_tree().get_first_node_in_group("players") as Player
	camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	player.global_position = Vector3(100, 0.1, -5)
	player.health.invulnerable = true
	CameraRig.first_person_mode = true
	camera._look_yaw = -PI * 0.5
	var slot: String = String(WeaponDb.sandbox()[0])
	player.loadout_mode = false
	player.sandbox_weapons[slot] = {"id": "signal_launcher", "n": 1, "dur": 100.0, "rev": 1, "mods": {},
		"mag": {"id": "", "ammo": "flare", "rounds": 1}}
	player.weapon_slot = ""
	player._switch(slot, false)
	await get_tree().create_timer(1.2).timeout
	if not camera._viewmodel is ViewmodelClips:
		push_error("flare_claude_shots: модель в руках не загрузилась")
		get_tree().quit(1)
		return
	var clips: ViewmodelClips = camera._viewmodel as ViewmodelClips
	_check(clips._signal_left_arm != null and not clips._signal_left_arm.visible, "в стойке левая рука скрыта")
	await shot("idle")
	Input.action_press("aim")
	await get_tree().create_timer(0.7).timeout
	_check(clips._signal_left_arm != null and not clips._signal_left_arm.visible, "в прицеле левая рука скрыта")
	await shot("ads")
	print("flare_claude_shots: прицел: виден=", clips.visible, " упор=", camera.weapon_clearance.valid, " рама=", clips.frame.name,
		" sight_h=", clips.frame.get_meta("sight_h", -1.0), " ads_z=", clips.frame.get_meta("ads_z", -1.0),
		" рама в модели=", clips.global_transform.affine_inverse() * clips.frame.global_transform, " ads=", clips.ads_transform(), " сейчас=", clips.transform)
	Input.action_release("aim")
	await get_tree().create_timer(0.5).timeout
	player._fire(player.spec())
	await get_tree().create_timer(0.2).timeout
	await shot("fire")
	await get_tree().create_timer(0.9).timeout
	player.stress = 0.0
	player.signal_reload_ammo = "supply_signal"
	player._start_reload(player.spec())
	print("flare_claude_shots: перезарядка, с ", player.reload_timer)
	await get_tree().process_frame
	var events: Dictionary = cfg.events
	for stage: Array in [[17, "left_on_barrel"], [int(events.open), "barrel_open"], [int(events.chamber_down), "chamber_down"],
			[int(events.shake_1), "shake_1"], [int(events.case_free) + 2, "case_out"], [int(events.upright) + 4, "ready_to_load"],
			[92, "round_at_chamber"], [102, "round_half"], [int(events.insert), "round_seated"],
			[int(events.snap), "snap"], [int(events.close) + 2, "barrel_closed"]]:
		while player.reload_timer > 0.0 and clips._anim.current_animation_position * 30.0 + 1.0 < float(stage[0]):
			await get_tree().process_frame
		await shot("reload_%03d_%s" % [int(stage[0]), String(stage[1])])
	while player.reload_timer > 0.0 or not player._pm_action.is_empty():
		await get_tree().process_frame
	await get_tree().create_timer(0.4).timeout
	_check(player.ammo == 1, "после перезарядки патрон в стволе")
	_check(not clips._signal_left_arm.visible, "после перезарядки левая рука скрыта")
	await shot("reload_done")
	var file: FileAccess = FileAccess.open("res://docs/screens/flare_claude_manifest.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"weapon": "signal_launcher", "viewmodel": cfg.scene, "samples": samples, "failures": fails}, "\t"))
	print("flare_claude_shots: провалено ", fails)
	get_tree().quit(1 if fails else 0)


func _check(ok: bool, what: String) -> void:
	print("flare_claude_shots: ", "ok   " if ok else "FAIL ", what)
	if not ok:
		fails += 1


func shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/flare_claude_" + label + ".png"
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	var clips: ViewmodelClips = camera._viewmodel as ViewmodelClips
	var frame: float = clips._anim.current_animation_position * 30.0 + 1.0
	samples.append({"stage": label, "clip": clips._anim.current_animation, "frame": frame, "left_visible": clips._signal_left_arm.visible})
	print("flare_claude_shots: ", label, " клип=", clips._anim.current_animation, " кадр=", snappedf(frame, 0.1), " левая=", clips._signal_left_arm.visible)
