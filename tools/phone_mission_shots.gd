extends Node
## Isolated profile, actual quest level. Public development shots, never the player's save.
const Q := "car_recovery"

func frames(n: int) -> void:
	for i: int in range(n): await get_tree().process_frame

func _ready() -> void:
	if name != "PhoneMissionRunner":
		var runner := Node.new(); runner.name = "PhoneMissionRunner"
		runner.set_script(get_script()); get_tree().root.add_child.call_deferred(runner)
		return
	Profile.use_file("user://phone_mission_shots.json", true)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time":"day", "weather":"clear", "power":"on"}
	Quests.dev_start(Q); Quests.dev_stage(Q, 4); Quests.dev_complete_objective(Q)
	Profile.quests[Q]["obj"] = 4
	Quests.finish_talk(Q, "ilya", "report_car")
	Quests.finish_talk(Q, "kirill", "kirill_task")
	Quests._durable_add(Q, "battery"); Quests._auto_all()
	PhoneGear.ensure_profile(); Profile.save()
	get_tree().change_scene_to_file("res://scenes/levels/zone01_mall.tscn")
	await get_tree().create_timer(4.0).timeout
	var level := get_tree().current_scene as Node3D
	while not bool(level.get("_nav_baked")): await get_tree().create_timer(0.1).timeout
	var player := Raid.current.local_player()
	player.health.invulnerable = true; player.set_physics_process(false)
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
	var rig := level.get_node("CameraRig") as CameraRig
	rig.first_person_mode = true
	await get_tree().create_timer(6.0).timeout
	rig.set_process(false); rig.set_physics_process(false)
	var cam := rig._ads_cam
	var hangar := level.find_child("Hangar8", true, false) as Node3D
	var car := hangar.get_node("IlyaCar") as Node3D
	await pose(cam, player, car.to_global(Vector3(4, 1.8, 6)), car.to_global(Vector3(0, 0.85, 0)))
	await shot("coupe")
	var hood := level.find_child("car_belt_photo_engine", true, false) as Node3D
	await pose(cam, player, hood.global_position + hangar.basis * Vector3(0.05, 1.55, 0.1), car.to_global(Vector3(0, 0.8, 1.3)))
	player.inventory.items = [ItemDb.make(PhoneGear.ID, 1)]
	await benchmark("stowed")
	Phone.set_active(true)
	await frames(45)
	await benchmark("live camera")
	await shot("camera")
	for sid: String in ["car_belt_photo_engine", "car_belt_photo_radiator", "car_belt_photo_wheel", "car_belt_photo_wiring"]:
		var site := level.find_child("Quest_" + sid, true, false) as QuestSite
		if site:
			Phone.frame_site(site)
			await Phone.capture()
	Phone.pointer = true; Phone.screen_ui.select("Связь")
	await get_tree().create_timer(4.0).timeout
	print("MISSION PHONE: modem ", Quests.field_link_unlocked(Q), ", report ready ", not Quests.field_action(Q).is_empty())
	await shot("modem")
	Phone.close()
	Quests.dev_stage(Q, 6)
	var kit := level.find_child("Quest_car_belt_delivery", true, false) as Node3D
	await pose(cam, player, kit.global_position + hangar.basis * Vector3(-2.0, 1.4, 2.0), kit.global_position + Vector3.UP * 0.15)
	await shot("kit")
	get_tree().quit()

func pose(cam: Camera3D, player: Player, eye: Vector3, at: Vector3) -> void:
	player.global_position = eye - Vector3.UP * 1.5
	cam.global_position = eye; cam.look_at(at)
	await frames(18)

func shot(tag: String) -> void:
	if Quests.hud:
		Quests.hud._test_t = 0.0
		Quests.hud._test_box.visible = false
		Quests.hud._toasts.visible = false
	await RenderingServer.frame_post_draw
	var path := "res://docs/screens/phone_mission_%s.png" % tag
	get_viewport().get_texture().get_image().save_png(path)
	print("MISSION PHONE SHOT ", path)

func benchmark(label: String) -> void:
	var times: Array[float] = []
	var previous := Time.get_ticks_usec()
	for i: int in range(120):
		await get_tree().process_frame
		var now := Time.get_ticks_usec()
		times.append(float(now - previous) / 1000.0)
		previous = now
	times.sort()
	print("MISSION PHONE FRAME ", label, " median_ms=", times[60], " p90_ms=", times[108])
