extends Node
## Осветительная ракета из сигнального пистолета (SkyFlare) во дворе зоны 1 ночью: взлёт, вершина, спуск,
## затухание — от первого лица вдоль двора и вверх на ракету; сколько висит в воздухе, как высоко,
## виден ли игрок в её круге издалека; кадры в секунду до и во время.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/sky_flare_shots.tscn → docs/screens/sky_flare_*.png
## SKY_FLARE_TIME=dusk|day — другое время суток (суффикс в имени снимка).

const SCENE := "res://scenes/levels/zone01_mall.tscn"

var _fails: int = 0
var _suffix: String = ""


func _ready() -> void:
	RaidEvents.enabled = false
	var tod: String = OS.get_environment("SKY_FLARE_TIME") if OS.get_environment("SKY_FLARE_TIME") != "" else "night"
	_suffix = "" if tod == "night" else "_" + tod
	RaidConditions.from_host = {"time": tod, "weather": "clear", "power": "on"}
	var level: Node = (load(SCENE) as PackedScene).instantiate()
	get_tree().root.add_child.call_deferred(level)
	await get_tree().process_frame
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me: Player = Raid.current.local_player()
	me.health.hp = 1e9
	me.health.max_hp = 1e9
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	CameraRig.first_person_mode = true
	var at := Vector3(-196, 0.0, -66)
	var ground: Dictionary = (level as Node3D).get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(at + Vector3.UP * 30.0, at + Vector3.DOWN * 30.0, Hitscan.LAYER_WORLD))
	me.global_position = (ground.position as Vector3) + Vector3.UP * 0.1 if not ground.is_empty() else at
	await _frames(30)
	_look(rig, me, Vector3(-212, 7, -136))
	await _frames(90)
	var fps_before: float = await _fps(60)
	await _save("sky_flare_0_before")
	var view_dark: float = RaidAtmosphere.current.view_distance(me.global_position, false) if RaidAtmosphere.current else 0.0
	# выстрел: штатное действие игрока (песочница — без счёта)
	_check("выстрел принят", me.launch_sky_flare())
	await _frames(2)
	var flare: SkyFlare = get_tree().get_first_node_in_group("sky_flares") as SkyFlare
	_check("ракета в воздухе", flare != null)
	if flare == null:
		get_tree().quit(1)
		return
	var start_y: float = me.global_position.y
	var top: float = 0.0
	var t0: int = Time.get_ticks_msec()
	var burn_sec: float = float(Balance.SKY_FLARE.air_sec) - flare.time_left()
	var shots: Array = [[1.2, "1_rise"], [4.0, "2_top"], [9.0, "3_fall"], [13.6, "4_fade"]]
	var fps_during: float = 0.0
	var view_lit: float = 0.0
	while is_instance_valid(flare):
		var t: float = float(Time.get_ticks_msec() - t0) / 1000.0
		top = maxf(top, flare.global_position.y - start_y)
		# время ракеты — игровое: сохранение снимка задерживает кадр, а не её часы
		burn_sec = float(Balance.SKY_FLARE.air_sec) - flare.time_left()
		if not shots.is_empty() and t >= float(shots[0][0]):
			var name: String = String(shots[0][1])
			shots.pop_front()
			await _save("sky_flare_" + name)
			if name == "2_top":
				fps_during = await _fps(60)
				view_lit = RaidAtmosphere.current.view_distance(me.global_position, false) if RaidAtmosphere.current else 0.0
				# вверх на саму ракету
				_look(rig, me, flare.global_position)
				await _frames(20)
				await _save("sky_flare_2_top_up")
				_look(rig, me, Vector3(-212, 7, -136))
		await get_tree().process_frame
	_check("в воздухе %.1f с (нужно %.0f)" % [burn_sec, float(Balance.SKY_FLARE.air_sec)], absf(burn_sec - float(Balance.SKY_FLARE.air_sec)) < 0.3)
	_check("поднялась на %.0f м" % top, top > float(Balance.SKY_FLARE.rise_m) * 0.9)
	_check("в её свете на улице видно дальше: %.0f → %.0f м" % [view_dark, view_lit], view_lit >= Balance.FLARE_LIT_VIEW - 0.1 and (tod != "night" or view_lit > view_dark))
	print("sky_flare_shots: кадров в секунду до %.0f, с ракетой %.0f" % [fps_before, fps_during])
	await _frames(30)
	await _save("sky_flare_5_after")
	print("sky_flare_shots: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


func _look(rig: CameraRig, me: Player, target: Vector3) -> void:
	var d: Vector3 = target - me.eye_position()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())


func _fps(frames: int) -> float:
	var t0: int = Time.get_ticks_usec()
	for i in range(frames):
		await get_tree().process_frame
	return float(frames) * 1000000.0 / float(maxi(1, Time.get_ticks_usec() - t0))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(name: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s%s.png" % [name, _suffix]))
	print("sky_flare_shots: ", name)


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("%s %s" % ["[ok]  " if ok else "[FAIL]", label])
