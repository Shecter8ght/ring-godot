extends Node
## Свет: заградительные огни на крыше ТЦ (ночь, туман днём — горят; ясный день — нет) и мягкий
## свет ламп в ТЦ ночью. godot --path . res://tools/light_shots.tscn → docs/screens/light_*.png

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	Profile.use_file("user://profile_light_shots.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var shots := DisplayServer.get_name() != "headless"
	for c in [{"time": "night", "weather": "clear", "power": "on"}, {"time": "day", "weather": "fog", "power": "on"}, {"time": "day", "weather": "clear", "power": "on"}]:
		var level := await _load(c)
		var lit := 0
		for b in get_tree().get_nodes_in_group("obstruction_lights"):
			if (b as Node3D).visible:
				lit += 1
		var want := String(c.time) != "day" or String(c.weather) == "fog"
		_check("заградительные огни: %s/%s — %s" % [c.time, c.weather, "горят" if want else "нет"], (lit > 10) == want, "горит %d" % lit)
		if shots and want:
			var tag := "%s_%s" % [c.time, c.weather]
			await _shot(level, "light_roof_%s" % tag, SectorBuilder.polar(-96.0, 150.0), true, -10.0, 0.55)
			await _shot(level, "light_roof_iso_%s" % tag, SectorBuilder.polar(-96.0, 128.0), false, 0.0, 0.0)
		if shots and String(c.time) == "night":
			await _shot(level, "light_mall_fps", SectorBuilder.polar(-100.0, 72.0), true, 90.0, 0.05)
			await _shot(level, "light_mall_iso", SectorBuilder.polar(-100.0, 72.0), false, 0.0, 0.0)
		level.queue_free()
		await get_tree().process_frame
	CameraRig.first_person_mode = false
	print("light_shots: провалено %d" % _fails)
	get_tree().quit(_fails)


func _load(c: Dictionary) -> Node:
	RaidConditions.from_host = c
	var level: Node = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	Raid.current.local_player().health.hp = 1e9
	await _frames(5)
	return level


func _shot(_level: Node, n: String, at: Vector3, fps: bool, yaw: float, pitch: float) -> void:
	var me := Raid.current.local_player()
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	me.global_position = at + Vector3(0, 0.1, 0)
	CameraRig.first_person_mode = fps
	await _frames(12)
	if fps:
		rig._look_yaw = deg_to_rad(yaw)
		rig._look_pitch = pitch
	await _frames(60)
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
