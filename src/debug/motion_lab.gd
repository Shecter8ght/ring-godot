extends DevelopmentLab
## Проверка параметров на настоящей камере и оружии игрока.


func _ready() -> void:
	leave_overview_to_play = true
	super._ready()
	panel.label(panel.context, "Пройдись, пробеги и прыгни с любым оружием. F7 возвращает исходное движение для сравнения.")
	panel.label(panel.context, "Направление качания задаёт поворот траектории на экране. 0° — как в игре, ±90° меняют местами движение вверх-вниз и вбок.", 15)
	weapon_selector()
	panel.action("Вернуться к началу дорожки", _reset_position)
	panel.action("В главное меню", _back)
	panel.tabs.current_tab = 1
	($Interface/Hint/Label as Label).text = "F6 — движение / настройки   ·   F7 — исходный вариант   ·   Ctrl+S — сохранить\nWASD — шаг   ·   Shift — бег   ·   Пробел — прыжок   ·   ПКМ — прицел"
	var readout: PanelContainer = $Interface/Telemetry
	readout.anchor_left = 1.0
	readout.offset_left = -365
	readout.offset_bottom = 171
	for distance: int in [5, 15, 25, 35]:
		box($Samples, "Marker_%d" % distance, Vector3(-2.8, 0.5, -6 + distance), Vector3(0.3, 1.0, 0.3), Color("#907956"))
		text_3d($Samples, "%d м" % distance, Vector3(-2.8, 1.35, -6 + distance))


func _reset_position() -> void:
	player.position = Vector3(0, 0.03, -6)
	player.velocity = Vector3.ZERO
	player.reset_physics_interpolation()
	player._eye_tick_ready = false
	rig._look_yaw = 0.0
	rig._look_pitch = 0.0
	rig._motion.reset()


func _lab_tick(_delta: float) -> void:
	var speed: float = Vector2(player.velocity.x, player.velocity.z).length()
	var state: String = "В воздухе" if player.airborne else ("Бег" if speed > Balance.STEP_RUN_SPEED else ("Шаг" if speed > 0.35 else "На месте"))
	telemetry.text = "%s · %.1f м/с\nКамера %.1f мм   ·   Оружие %.1f мм" % [state, speed,
		rig._motion.offset.length() * 1000.0, rig._motion.weapon_bob.length() * 1000.0]
