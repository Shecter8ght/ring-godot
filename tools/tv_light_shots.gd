extends Node
## Свет от телевизора в убежище: ночь, генератор выключен, телевизор включён — видно мебель и дальнюю
## стену, а не только экран. Снимки docs/screens/tv_light_*.png (off — телевизор выключен, для сравнения).
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/tv_light_shots.tscn

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://tv_light_shots.json", true)
	Profile.modules.generator = 1
	Profile.hideout_media = {"tv": 0, "radio": 0, "power": false}
	Profile.next_conditions = {"time": "night", "weather": "clear", "power": "on"}
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(200)
	var level: Node = get_tree().current_scene
	var pl: Player = level.get("_player") as Player
	var weather: ShelterWeather = level.find_child("Weather", true, false) as ShelterWeather
	if weather:
		weather.refresh(true)
	var tv: HideoutActivity = null
	for n: Node in level.find_children("*", "", true, false):
		if n is HideoutActivity and (n as HideoutActivity).kind == HideoutActivity.Kind.TV:
			tv = n as HideoutActivity
	_check("телевизор найден", tv != null)
	if tv == null:
		get_tree().quit(1)
		return
	var glow: OmniLight3D = tv.get_node_or_null(tv.glow_light) as OmniLight3D
	var at: Vector3 = tv.global_position
	# с дивана на экран; от экрана на дальнюю стену; сбоку на комнату
	var views: Array = [["sofa", at + Vector3(0.4, -1.36, 3.6), at], ["wall", at + Vector3(0.0, -1.36, 0.9), at + Vector3(0.3, -0.2, 6.0)],
		["side", at + Vector3(2.6, -1.36, 2.4), at + Vector3(-1.5, -0.4, 1.0)]]
	var lum: Dictionary = {}
	for mode: Array in [["off", 0], ["news", 1], ["football", 2]]:
		tv._switch(int(mode[1]))
		await _frames(20)
		for v: Array in views:
			_place(pl, v[1], v[2])
			await _frames(90)
			lum["%s_%s" % [mode[0], v[0]]] = await _save("tv_light_%s_%s" % [mode[0], v[0]])
	_check("свет от экрана включён, с тенями, дальность по балансу", glow != null and glow.visible and glow.shadow_enabled
		and is_equal_approx(glow.omni_range, float(Balance.TV_LIGHT.range)), "")
	_check("с телевизором дальняя стена светлее, чем без него (%.4f → %.4f)" % [float(lum.off_wall), float(lum.news_wall)],
		float(lum.news_wall) > float(lum.off_wall) * 1.5 + 0.002)
	tv._switch(0)
	await _frames(10)
	_check("выключили телевизор — свет погас", glow != null and not glow.visible)
	print("tv_light_shots: провалено %d" % _fails)
	get_tree().quit(_fails)


func _place(pl: Player, at: Vector3, look_at: Vector3) -> void:
	pl.global_position = at
	pl.velocity = Vector3.ZERO
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var eye: Vector3 = at + Vector3(0, 1.62, 0)
	var d: Vector3 = (look_at - eye).normalized()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = asin(clampf(d.y, -1.0, 1.0))


## Сохранить кадр; вернуть среднюю яркость (без окна — 0).
func _save(label: String) -> float:
	if DisplayServer.get_name() == "headless":
		return 0.0
	await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % label))
	var sum: float = 0.0
	var n: int = 0
	for y: int in range(0, img.get_height(), 16):
		for x: int in range(0, img.get_width(), 16):
			sum += img.get_pixel(x, y).get_luminance()
			n += 1
	return sum / float(maxi(n, 1))


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
