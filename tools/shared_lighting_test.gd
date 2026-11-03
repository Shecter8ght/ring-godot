extends Node3D
## Общий профиль: существующие карты и новая без собственных настроек света; сохранение стенда.

var sector_path: String = ""
var _checks: int = 0
var _fails: int = 0


func _ready() -> void:
	Profile.use_file("user://shared_lighting_profile_test.json", true)
	LabTuning.storage_path = "user://shared_lighting_test.cfg"
	DirAccess.remove_absolute(LabTuning.storage_path)
	LabTuning.reload()
	Settings.raid_hour = -1.0
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	add_child(sun)
	var cam: Camera3D = Camera3D.new()
	add_child(cam)
	cam.make_current()
	var atm: RaidAtmosphere = RaidAtmosphere.new()
	add_child(atm)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	atm.apply()
	var weather: RaidWeather = RaidWeather.new()
	add_child(weather)
	await get_tree().process_frame
	var baseline: Dictionary = {}
	for path: String in ["prospekt", "mall_map", "zone01_mall", "future_map_without_settings"]:
		sector_path = "res://data/sectors/%s.json" % path
		# Заведомо другое окружение карты не должно переопределить общий свет.
		we.environment = Environment.new()
		we.environment.tonemap_mode = Environment.TONE_MAPPER_AGX
		we.environment.ambient_light_energy = 9.0
		weather._e = null
		for mode: String in ["hdri", "calc"]:
			Settings.sky_mode = mode
			for time_key: String in ["day", "dusk", "night"]:
				for weather_key: String in ["clear", "overcast", "rain", "fog", "heat"]:
					RaidConditions.current = {"time": time_key, "weather": weather_key, "power": "on"}
					AtmosphereSky.reset_blend()
					atm.apply()
					weather.conditions_changed()
					var cycle: DayCycle = DayCycle.current
					cycle.set_process(false)
					cycle.set_hour(float(Balance.RAID_TIME[time_key].start_hour))
					weather._tick_fog(100.0)
					var label: String = "%s/%s/%s" % [mode, time_key, weather_key]
					var sample: Array = [sun.light_energy, we.environment.ambient_light_energy, sun.light_angular_distance,
						sun.shadow_blur, we.environment.tonemap_mode, we.environment.adjustment_saturation,
						we.environment.fog_depth_begin, we.environment.fog_depth_end, we.environment.fog_density]
					if path == "prospekt":
						baseline[label] = sample
					_check(path + "/" + label + ": тот же профиль", sample == baseline[label])
					if weather_key in ["overcast", "rain"]:
						_check(path + "/" + label + ": нет солнечного луча за тучами", not sun.visible and is_zero_approx(sun.light_energy))
		_check(path + ": окружение Проспекта вместо настроек сцены", we.environment.has_meta("shared_lighting")
			and we.environment.tonemap_mode == Environment.TONE_MAPPER_FILMIC and is_equal_approx(we.environment.ssao_intensity, 4.0))
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	Settings.sky_mode = "hdri"
	atm.apply()
	var cycle: DayCycle = DayCycle.current
	cycle.set_process(false)
	cycle.set_hour(12.0)
	var energy: float = sun.light_energy
	var values: Dictionary = LabTuning.defaults("atmosphere")
	values.sun = 1.7
	values.shadow_angle = 0.8
	values.saturation = 0.7
	values.adapt_scale = 0.42
	values.fog_distance = 1.5
	LabTuning.preview("atmosphere", values)
	atm.apply()
	weather.conditions_changed()
	cycle.set_hour(12.0)
	_check("черновик изменяет настоящий свет и тени", is_equal_approx(sun.light_energy, energy * 1.7) and is_equal_approx(sun.light_angular_distance, 0.8))
	_check("черновик изменяет цветокоррекцию, глаз и дальность дымки", is_equal_approx(we.environment.adjustment_saturation, 0.7)
		and is_equal_approx(float(RaidLighting.look().exposure_scale_raid), 0.42) and is_equal_approx(we.environment.fog_depth_end, 1350.0))
	var changed: float = sun.light_energy
	atm.apply()
	cycle.set_hour(12.0)
	_check("повторное применение не копит яркость", is_equal_approx(changed, sun.light_energy))
	_check("сохранение общего варианта", LabTuning.save("atmosphere", "Общий свет", values, true) == OK)
	LabTuning.end_preview("atmosphere")
	LabTuning.reload()
	sector_path = "res://another_future_map.json"
	atm.apply()
	cycle.set_hour(12.0)
	_check("сохранённый вариант работает на новой карте после перезагрузки", is_equal_approx(sun.light_energy, changed)
		and is_equal_approx(we.environment.adjustment_saturation, 0.7))
	RaidConditions.current.weather = "rain"
	weather._apply_static()
	_check("дождь по расписанию обновляет общий свет", not sun.visible and is_zero_approx(sun.light_energy))
	LabTuning.save("atmosphere", "Общий свет", values, false)
	atm.apply()
	_check("выключение варианта возвращает профиль Проспекта", is_equal_approx(we.environment.adjustment_saturation, 0.9))
	print("shared_lighting_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(_fails)


func _check(label: String, ok: bool) -> void:
	_checks += 1
	if not ok:
		_fails += 1
	print("%s %s" % ["OK" if ok else "FAIL", label])
