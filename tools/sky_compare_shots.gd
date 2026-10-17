extends Node
## Небо смены суток: из фотопанорам и расчётное (Settings.sky_mode) — снимки с одной точки зоны 1 в
## одно и то же время: 05:00 (восход), 13:00, 18:30, 21:00 и днём в дождь. Для каждого времени три
## вида — на солнце, от солнца, вверх; лист сравнения: слева панорамы, справа расчёт, ряды — виды.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/sky_compare_shots.tscn
## → docs/screens/sky_cmp_<время>.png (отдельные кадры — user://sky_cmp/), кадры в секунду обоих режимов.
## SKY_CMP_ONLY=0500,2100 — выборочно; SKY_CMP_AT=x:z — другая точка.

const SCENE := "res://scenes/levels/zone01_mall.tscn"
const CASES := [
	{"id": "0500", "hour": 5.0, "weather": "clear"},
	{"id": "1300", "hour": 13.0, "weather": "clear"},
	{"id": "1830", "hour": 18.5, "weather": "clear"},
	{"id": "2100", "hour": 21.0, "weather": "clear"},
	{"id": "1300_rain", "hour": 13.0, "weather": "rain"},
]
## вид: имя, поворот от азимута солнца, °, взгляд над горизонтом, °
const VIEWS := [["sun", 0.0, 6.0], ["back", 180.0, 6.0], ["up", 0.0, 50.0]]
const MODES := ["hdri", "calc"]
const TILE := Vector2i(800, 450)

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	Settings.lens_fx = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
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
	var at := Vector3(88, 0.0, -5)
	var at_env: String = OS.get_environment("SKY_CMP_AT")
	if at_env != "":
		var p: PackedStringArray = at_env.split(":")
		at = Vector3(float(p[0]), 0.0, float(p[1]))
	var ground: Dictionary = (level as Node3D).get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(at + Vector3.UP * 60.0, at + Vector3.DOWN * 30.0, Hitscan.LAYER_WORLD))
	me.global_position = (ground.position as Vector3) + Vector3.UP * 0.1 if not ground.is_empty() else at
	await _frames(30)
	_check("смена суток идёт", DayCycle.current != null)
	_check("таблицы расчётного неба есть", AtmosphereSky.available())
	if DayCycle.current == null:
		get_tree().quit(1)
		return
	# часы стоят: оба режима — в одну и ту же минуту
	DayCycle.current.set_process(false)
	var only: String = OS.get_environment("SKY_CMP_ONLY")
	var out_dir: String = "user://sky_cmp"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	for c: Dictionary in CASES:
		if only != "" and not String(c.id) in only.split(","):
			continue
		if String(RaidConditions.current.weather) != String(c.weather):
			Settings.set_raid_conditions("", String(c.weather))
			await _frames(30)
		var sa: Vector2 = DayCycle.sun_at(float(c.hour))
		var sheet: Image = Image.create(TILE.x * MODES.size(), TILE.y * VIEWS.size(), false, Image.FORMAT_RGB8)
		for mi in range(MODES.size()):
			Settings.sky_mode = String(MODES[mi])
			DayCycle.current.rebuild()
			DayCycle.current.set_hour(float(c.hour))
			_check("%s %s: небо %s" % [c.id, MODES[mi], "расчётное" if DayCycle.current._calc else "из панорам"],
				DayCycle.current._calc == (MODES[mi] == "calc"))
			await _frames(90)
			for vi in range(VIEWS.size()):
				var v: Array = VIEWS[vi]
				_look(rig, me, fposmod(sa.y + float(v[1]), 360.0), float(v[2]))
				await _frames(20)
				if vi == 0:
					print("sky_compare_shots: %s %s — кадров в секунду %.0f" % [c.id, MODES[mi], await _fps(90)])
				await RenderingServer.frame_post_draw
				var img: Image = get_viewport().get_texture().get_image()
				img.convert(Image.FORMAT_RGB8)
				img.save_png(ProjectSettings.globalize_path("%s/%s_%s_%s.png" % [out_dir, c.id, v[0], MODES[mi]]))
				img.resize(TILE.x, TILE.y, Image.INTERPOLATE_LANCZOS)
				sheet.blit_rect(img, Rect2i(Vector2i.ZERO, TILE), Vector2i(TILE.x * mi, TILE.y * vi))
		sheet.save_png(ProjectSettings.globalize_path("res://docs/screens/sky_cmp_%s.png" % c.id))
		print("sky_compare_shots: %s — солнце %.1f° по азимуту %.0f°" % [c.id, sa.x, sa.y])
	# кадры в секунду честно: режимы по очереди, дважды, на восходе лицом к солнцу (неба в кадре много)
	if String(RaidConditions.current.weather) != "clear":
		Settings.set_raid_conditions("", "clear")
		await _frames(30)
	var sun0: Vector2 = DayCycle.sun_at(5.0)
	_look(rig, me, sun0.y, 6.0)
	var fps: Dictionary = {"hdri": [], "calc": []}
	for k in range(2):
		for mode: String in MODES:
			Settings.sky_mode = mode
			DayCycle.current.rebuild()
			DayCycle.current.set_hour(5.0)
			await _frames(120)
			(fps[mode] as Array).append(await _fps(240))
	print("sky_compare_shots: кадров в секунду на восходе — из панорам %s, расчётное %s" % [fps.hdri, fps.calc])
	print("sky_compare_shots: кадры — ", ProjectSettings.globalize_path(out_dir))
	print("sky_compare_shots: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Взгляд по азимуту az (от севера к востоку), на elev над горизонтом.
func _look(rig: CameraRig, me: Player, az: float, elev: float) -> void:
	var d: Vector3 = DayCycle.dir_from(elev, az)
	var target: Vector3 = me.eye_position() + d * 100.0
	var dd: Vector3 = target - me.eye_position()
	rig._look_yaw = atan2(dd.x, dd.z)
	rig._look_pitch = atan2(dd.y, Vector2(dd.x, dd.z).length())


func _fps(frames: int) -> float:
	var t0: int = Time.get_ticks_usec()
	for i in range(frames):
		await get_tree().process_frame
	return float(frames) * 1000000.0 / float(maxi(1, Time.get_ticks_usec() - t0))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("%s %s" % ["[ok]  " if ok else "[FAIL]", label])
