extends Node3D
## Профиль Проспекта на территории ТЦ: движущееся солнце, все погоды и оба режима неба.

var sector_path: String = "res://data/sectors/mall_map.json"
var _fails: int = 0


func _ready() -> void:
	Settings.raid_hour = -1.0
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = (load("res://scenes/levels/mall/mall_environment.tres") as Environment).duplicate(true) as Environment
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.set_meta("authored_shadow", true)
	add_child(sun)
	var cam: Camera3D = Camera3D.new()
	cam.position = Vector3(22, 1.62, 150)
	add_child(cam)
	cam.make_current()
	var atm: RaidAtmosphere = RaidAtmosphere.new()
	add_child(atm)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	atm.apply()
	var weather: RaidWeather = RaidWeather.new()
	add_child(weather)
	await get_tree().process_frame
	var cycle: DayCycle = DayCycle.current
	_check("смена суток территории ТЦ сохранена", cycle != null)
	if cycle == null:
		get_tree().quit(1)
		return
	cycle.set_process(false)
	for mode: String in ["calc", "hdri"]:
		Settings.sky_mode = mode
		for time_key: String in ["day", "dusk", "night"]:
			for weather_key: String in ["clear", "overcast", "rain", "fog", "heat"]:
				RaidConditions.current = {"time": time_key, "weather": weather_key, "power": "on"}
				AtmosphereSky.reset_blend()
				atm.apply()
				weather.conditions_changed()
				cycle.set_hour(float((Balance.RAID_TIME[time_key] as Dictionary).start_hour))
				var label: String = "%s/%s/%s" % [mode, time_key, weather_key]
				_check(label + ": свой режим неба сохранён", cycle._calc == (mode == "calc") and we.environment.sky.sky_material is ShaderMaterial)
				var soft: bool = cycle.sun_elev >= 20.0
				_check(label + ": мягкость следует высоте движущегося солнца", is_equal_approx(sun.light_angular_distance, 0.53 if soft else 0.0)
					and is_equal_approx(sun.shadow_blur, 1.0 if soft else 1.5))
				if weather_key in ["overcast", "rain"]:
					_check(label + ": за сплошными тучами нет прямого луча", not sun.visible and is_zero_approx(sun.light_energy))
				_check(label + ": дневной рассеянный как у Проспекта", is_equal_approx(float((cycle._profiles.day as Dictionary).ambient),
					0.64 if weather_key in ["overcast", "rain"] else 0.32))
		RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
		atm.apply()
		weather.conditions_changed()
		cycle.set_hour(11.0)
		var basis_before: Basis = sun.global_basis
		cycle.set_hour(11.25)
		_check(mode + ": солнце продолжает двигаться по часам", not sun.global_basis.is_equal_approx(basis_before))
		cycle.set_hour(18.0)
		_check(mode + ": к закату включается защита крыши", is_zero_approx(sun.light_angular_distance))
	print("mall_light_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("%s %s" % ["OK" if ok else "FAIL", label])
