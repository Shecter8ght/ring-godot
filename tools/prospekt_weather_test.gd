extends Node3D
## Все сочетания времени и погоды на настоящем окружении Проспекта без загрузки геометрии.
## Повторные переключения проверяют возврат исходного неба и отсутствие накопления множителей.

var sector_path: String = "res://data/sectors/prospekt.json"
var _fails: int = 0


func _ready() -> void:
	var we: WorldEnvironment = WorldEnvironment.new()
	we.name = "WorldEnvironment"
	we.environment = (load("res://scenes/levels/prospekt/prospekt_environment.tres") as Environment).duplicate(true) as Environment
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_angular_distance = 0.53
	sun.set_meta("authored_shadow", true)
	add_child(sun)
	_check("настройки сохраняют размер солнца карты", is_equal_approx(sun.light_angular_distance, 0.53))
	var ordinary: DirectionalLight3D = DirectionalLight3D.new()
	ordinary.light_angular_distance = 0.53
	add_child(ordinary)
	_check("защита потолков других карт сохранена", is_zero_approx(ordinary.light_angular_distance))
	ordinary.queue_free()
	var atm: RaidAtmosphere = RaidAtmosphere.new()
	add_child(atm)
	RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
	atm.apply()
	var weather: RaidWeather = RaidWeather.new()
	add_child(weather)
	await get_tree().process_frame
	var clear_sky: Sky = we.environment.sky
	var clear_sun: float = sun.light_energy
	var clear_ambient: float = we.environment.ambient_light_energy
	for time_key: String in ["day", "dusk", "night"]:
		for weather_key: String in ["clear", "overcast", "rain", "fog", "heat"]:
			RaidConditions.current = {"time": time_key, "weather": weather_key, "power": "on"}
			atm.apply()
			weather.conditions_changed()
			var clouded: bool = weather_key in ["overcast", "rain"]
			_check("%s/%s: прямой свет за тучами погашен" % [time_key, weather_key],
				(not sun.visible or is_zero_approx(sun.light_energy)) if clouded else sun.visible)
			_check("%s/%s: мягкость без просвета крыши" % [time_key, weather_key],
				is_equal_approx(sun.light_angular_distance, 0.53) if time_key == "day" else
				is_zero_approx(sun.light_angular_distance) and is_equal_approx(sun.shadow_blur, 1.5))
			if time_key != "night":
				_check("%s/%s: небосвод соответствует погоде" % [time_key, weather_key],
					we.environment.sky != clear_sky if weather_key in ["overcast", "rain", "fog"] else we.environment.sky == clear_sky)
			# Вернуть ясный день после каждого режима, в том числе после ночи и дождя.
			RaidConditions.current = {"time": "day", "weather": "clear", "power": "on"}
			atm.apply()
			weather.conditions_changed()
			_check("%s/%s → день/ясно: исходное небо и свет" % [time_key, weather_key],
				we.environment.sky == clear_sky and is_equal_approx(sun.light_energy, clear_sun)
				and is_equal_approx(we.environment.ambient_light_energy, clear_ambient))
	# Автоматический дождь вызывает только Weather._apply_static, без меню настроек.
	RaidConditions.current["weather"] = "rain"
	weather._apply_static()
	_check("дождь по расписанию тоже гасит солнце и меняет небо", not sun.visible and we.environment.sky != clear_sky)
	print("prospekt_weather_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("%s %s" % ["OK" if ok else "FAIL", label])
