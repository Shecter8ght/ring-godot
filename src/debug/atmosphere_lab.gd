class_name AtmosphereLab
extends DevelopmentLab
## Свет на настоящем цикле суток и погоде игры; часы и лампа — условия осмотра стенда. Ползунки — той схемы света,
## что выбрана («Свет и небо»): у света Road to Vostok свой набор (LAB_RULES.atmosphere_tod), у прежнего — свой.

var _lamp: OmniLight3D
var _sky_mode_before: String = "tod"


func _ready() -> void:
	_sky_mode_before = Settings.sky_mode
	lab_domain = TodLight.LAB_DOMAIN if TodLight.active() else "atmosphere"
	super._ready()
	_build_samples()
	start_atmosphere(16.0)
	panel.option("Погода для просмотра", ["Ясно", "Пасмурно", "Дождь", "Туман", "Жара"], set_weather)
	var names: Array[String] = []
	for mode: String in Settings.SKY_MODES:
		names.append(String(Settings.SKY_MODE_NAMES[mode]))
	var sky_mode: OptionButton = panel.option("Свет и небо", names, _set_light_model)
	sky_mode.select(maxi(0, Settings.SKY_MODES.find(Settings.sky_mode)))
	panel.number("Часы · 0–24 (условие просмотра)", 16.0, 0.0, 23.95, 0.1, set_hour)
	panel.number("Лампа в комнате · яркость", 4.0, 0.0, 16.0, 0.1,
		func(value: float) -> void: _lamp.light_energy = value)
	panel.action("Перенести игрока: улица / комната", _move_location)
	weapon_selector()
	panel.label(panel.context, "Общий профиль всех рейдовых карт, включая будущие. Во вкладке «Варианты» включи «Применять на всех картах» и сохрани. Часы, погода и лампа — только условия осмотра.", 14)
	panel.use_in_game.text = "Применять на всех картах после сохранения"
	if LabTuning.names(lab_domain).is_empty():
		panel.use_in_game.set_pressed_no_signal(true)
	_update_status()
	_settings_changed()


## Схема света для осмотра: ползунки — её набора; в игре выбор — Esc → Читы → Мир → «Свет и небо».
func _set_light_model(index: int) -> void:
	var mode: String = String(Settings.SKY_MODES[index])
	var model_changed: bool = (mode == "tod") != (Settings.sky_mode == "tod")
	Settings.sky_mode = mode
	if model_changed:
		set_domain(TodLight.LAB_DOMAIN if mode == "tod" else "atmosphere")
		if atmosphere:
			atmosphere.relight()
	elif DayCycle.current:
		DayCycle.current.rebuild()
	_update_status()
	_settings_changed()


func _update_status() -> void:
	panel.status.text = "Общий свет всех карт · свет Road to Vostok (их числа по часам)." if TodLight.active() else "Общий свет всех карт · прежний профиль Проспекта."


func _build_samples() -> void:
	var samples: Node3D = $Samples
	box(samples, "RoomBack", Vector3(7, 1.7, 9), Vector3(7, 3.4, 0.25), Color(0.5, 0.48, 0.43))
	box(samples, "RoomLeft", Vector3(3.5, 1.7, 5.5), Vector3(0.25, 3.4, 7), Color(0.45, 0.46, 0.45))
	box(samples, "RoomRight", Vector3(10.5, 1.7, 5.5), Vector3(0.25, 3.4, 7), Color(0.45, 0.46, 0.45))
	box(samples, "RoomRoof", Vector3(7, 3.5, 5.5), Vector3(7.2, 0.25, 7.2), Color(0.5, 0.5, 0.5))
	text_3d(samples, "КОМНАТА · ЛАМПА", Vector3(7, 3.8, 2))
	for index: int in range(4):
		var color: Color = [Color(0.8, 0.8, 0.78), Color(0.35, 0.38, 0.42), Color(0.45, 0.27, 0.12), Color(0.06, 0.065, 0.07)][index]
		box(samples, "Material_%d" % index, Vector3(-4.5 + index * 1.5, 0.65, 4), Vector3(1, 1.3, 1), color, "metal" if index == 1 else "wood")
	text_3d(samples, "БЕЛОЕ · МЕТАЛЛ · ДЕРЕВО · ТЁМНОЕ", Vector3(-2.25, 2.1, 4))
	box(samples, "RoomTable", Vector3(7, 0.45, 6), Vector3(2.2, 0.9, 1.2), Color(0.28, 0.32, 0.35), "metal")
	_lamp = OmniLight3D.new()
	_lamp.name = "TestLamp"
	_lamp.position = Vector3(7, 2.7, 6)
	_lamp.omni_range = 7.0
	_lamp.light_energy = 4.0
	_lamp.light_color = Color(1.0, 0.8, 0.55)
	_lamp.shadow_enabled = true
	samples.add_child(_lamp)
	for distance: int in [10, 20, 40, 60]:
		box(samples, "Distance_%d" % distance, Vector3(-10, 1.5, distance), Vector3(0.3, 3, 0.3), Color(0.65, 0.65, 0.62))
		text_3d(samples, "%d м" % distance, Vector3(-10, 3.5, distance))


func _move_location() -> void:
	player.position = Vector3(7, 0.03, 3.5) if player.position.x < 3.0 else Vector3(0, 0.03, -6)
	player.velocity = Vector3.ZERO
	player._eye_tick_ready = false
	rig._look_yaw = 0.0
	rig._look_pitch = 0.0
	if atmosphere:
		atmosphere._indoor_cache.clear()


func _settings_changed() -> void:
	if atmosphere:
		atmosphere.apply()
	if DayCycle.current:
		DayCycle.current.set_process(false)
		DayCycle.current.set_hour(DayCycle.current.hour)
	if rig and rig._look:
		rig._look._apply_exposure()
	if weather:
		weather._apply_static()
		weather._tick_fog(0.0)


func _exit_tree() -> void:
	Settings.sky_mode = _sky_mode_before
	super._exit_tree()


func _lab_tick(_delta: float) -> void:
	var environment: Environment = world_environment.environment
	var sun: DirectionalLight3D = $Sun
	telemetry.text = "СВЕТ И АТМОСФЕРА\nВремя: %s · погода: %s\nСолнце / Луна: %.3f · рассеянный свет: %.3f\nЭкспозиция: %.2f · туман: %.4f\n%s\n%s" % [
		DayCycle.current.clock_text() if DayCycle.current else "—", String(RaidConditions.spec("weather").get("name", RaidConditions.current.weather)),
		sun.light_energy, environment.ambient_light_energy, environment.tonemap_exposure, environment.fog_density,
		"Игрок в комнате" if atmosphere and atmosphere.is_indoor(player.position) else "Игрок на улице",
		"СРАВНЕНИЕ: исходный свет" if panel.compare.button_pressed else "Предпросмотр выбранного варианта"]
