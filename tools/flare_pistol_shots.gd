extends Node
## Кадры настоящей игровой камеры и клипов рук ВЕРАС-54, не имитация UI.
var player: Player
var camera: CameraRig
var captures: Array[String] = []
var samples: Array[Dictionary] = []
var fails: int = 0


func _ready() -> void:
	Engine.max_fps = 60
	if DisplayServer.get_name() == "headless":
		get_tree().quit(1)
		return
	get_window().content_scale_size = Vector2i(1600, 900)
	get_window().size = Vector2i(1600, 900)
	Profile.use_file("user://profile_flare_shots.json", true)
	Profile.ensure()
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
		(enemy as Node3D).visible = false
	player = get_tree().get_first_node_in_group("players") as Player
	camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	player.global_position = Vector3(100, .1, -5)
	player.health.invulnerable = true
	CameraRig.first_person_mode = true
	camera._look_yaw = -PI * .5
	var slot: String = String(WeaponDb.sandbox()[0])
	player.loadout_mode = false
	player.sandbox_weapons[slot] = {"id": "signal_launcher", "n": 1, "dur": 100.0, "rev": 1, "mods": {},
		"mag": {"id": "", "ammo": "flare", "rounds": 1}}
	player.weapon_slot = ""
	player._switch(slot, false)
	await get_tree().create_timer(1.2).timeout
	if not camera._viewmodel is ViewmodelClips:
		push_error("flare_pistol_shots: нужен GLB с FPS-руками ВЕРАС-54")
		get_tree().quit(1)
		return
	var vm: ViewmodelClips = camera._viewmodel as ViewmodelClips
	if vm._signal_left_arm == null or vm._signal_left_arm.visible:
		fails += 1
	await shot("idle_right_only")
	Input.action_press("aim")
	await get_tree().create_timer(.6).timeout
	await shot("ads")
	Input.action_release("aim")
	await get_tree().create_timer(.4).timeout
	player._fire(player.spec())
	await get_tree().create_timer(.22).timeout
	await shot("trigger_hammer")
	await get_tree().create_timer(.9).timeout
	player.stress = 0.0
	player.signal_reload_ammo = "supply_signal"
	player._start_reload(player.spec())
	print("flare_pistol_shots: duration ",player.reload_timer)
	await get_tree().process_frame
	for stage: Array in [[14,"latch"],[30,"barrel_open"],[42,"chamber_down"],[48,"shake_1"],
		[56,"shake_2"],[70,"upright"],[91,"green_round_align"],
		[110,"round_seated"],[123,"snap_close"],[128,"barrel_closed"],[140,"hammer_cocked"]]:
		while player.reload_timer > 0.0 and vm._anim.current_animation_position * 30.0 + 1.0 < float(stage[0]):
			await get_tree().process_frame
		await shot(String(stage[1]))
	while player.reload_timer > 0.0 or not player._pm_action.is_empty():
		await get_tree().process_frame
	await get_tree().create_timer(.35).timeout
	if player.ammo != 1 or vm._signal_left_arm.visible:
		fails += 1
	await shot("reload_complete_right_only")
	var report := {"weapon":"signal_launcher", "hands":"VERAS54 FPS arms", "captures":captures, "samples":samples,"failures":fails}
	var file: FileAccess = FileAccess.open("res://docs/screens/flare_codex_manifest.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(report,"\t"))
	print("flare_pistol_shots: провалено ", fails)
	get_tree().quit(1 if fails else 0)


func shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/flare_codex_" + label + ".png"
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	captures.append(path)
	var vm: ViewmodelClips = camera._viewmodel as ViewmodelClips
	var frame: float = vm._anim.current_animation_position * 30.0 + 1.0
	samples.append({"stage":label,"clip":vm._anim.current_animation,"frame":frame,
		"speed":vm._anim.speed_scale,"timer":player.reload_timer,"left_visible":vm._signal_left_arm.visible})
	print("flare_pistol_shots: ",label," f=",frame," speed=",vm._anim.speed_scale," left=",vm._signal_left_arm.visible)
