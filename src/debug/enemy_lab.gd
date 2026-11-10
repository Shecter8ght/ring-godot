extends DevelopmentLab
## Настройка на живой модели мародёра. Пули, отдача, перезарядка и падение идут штатным путём.

const MARAUDER: PackedScene = preload("res://scenes/ai/marauder.tscn")
const START: Vector3 = Vector3(0, 0.03, 3)

var enemy: Marauder
var animator: CharacterAnimator
var clip_player: AnimationPlayer
var _loadouts: PackedStringArray
var _weapons: PackedStringArray
var _clips: PackedStringArray
var _loadout: String = "scav_standard"
var _weapon: String = ""
var _clip: String = ""
var _clip_paused: bool = false
var _timeline: HSlider
var _auto_fire: CheckButton
var _crouch: CheckButton
var _one_shot: bool = false
var _orbit: float = 35.0
var _distance: float = 3.6
var _last_hit: String = ""


func _ready() -> void:
	leave_overview_to_play = true
	super._ready()
	panel.tabs.set_tab_title(0, "Боец")
	panel.tabs.set_tab_title(1, "Настройка")
	panel.tabs.add_theme_font_size_override("font_size", 15)
	panel.label(panel.context, "Выбери снаряжение и оружие, затем проверь модель, физику падения и стрельбу.")
	_loadouts = PackedStringArray(WeaponDb.loadouts().keys())
	var loadout_names: Array[String] = []
	for id: String in _loadouts:
		loadout_names.append(String(WeaponDb.loadout(id).get("name", id)))
	var loadouts: OptionButton = panel.option("Комплект противника", loadout_names, func(index: int) -> void:
		_loadout = _loadouts[index]
		_reset_enemy())
	loadouts.select(maxi(0, _loadouts.find(_loadout)))
	_weapons = PackedStringArray(WeaponDb.presets().keys())
	_weapons.sort()
	var weapon_names: Array[String] = ["Из комплекта"]
	for id: String in _weapons:
		var spec: Dictionary = WeaponDb.preset(id)
		weapon_names.append(String(spec.get("name", id)))
	panel.option("Оружие противника", weapon_names, func(index: int) -> void:
		_weapon = _weapons[index - 1] if index > 0 else ""
		_reset_enemy())
	panel.action("Восстановить бойца", _reset_enemy)
	panel.number("Поворот камеры вокруг бойца, °", _orbit, -180.0, 180.0, 1.0, func(value: float) -> void:
		_orbit = value
		_update_camera())
	panel.number("Камера от бойца, м", _distance, 1.8, 14.0, 0.1, func(value: float) -> void:
		_distance = value
		_update_camera())
	panel.action("Камера осмотра / из глаз · F8", toggle_overview)
	panel.action("В главное меню", _back)
	_build_clip_controls()
	_build_combat_controls()
	var readout: PanelContainer = $Interface/Telemetry
	readout.anchor_left = 1.0
	readout.offset_left = -475
	readout.offset_bottom = 172
	var fill: OmniLight3D = OmniLight3D.new()
	fill.position = Vector3(-2, 3.5, -1)
	fill.omni_range = 8.0
	fill.light_energy = 1.0
	add_child(fill)
	box($Samples, "Backstop", Vector3(0, 1.5, 9), Vector3(10, 3, 0.3), Color("#555c5d"))
	observer.h_offset = -0.5
	($Interface/Hint/Label as Label).text = "F8 — осмотр / из глаз   ·   F6 — панель / взять управление\nF7 — сравнить с исходными настройками"
	panel.use_in_game.text = "Применять бой, перезарядку и падение в рейдах"
	panel.overview_button.text = "Камера осмотра / из глаз · F8"
	_reset_enemy()
	toggle_overview()


func _build_clip_controls() -> void:
	var page: VBoxContainer = panel._page("Клипы")
	panel.tabs.move_child(page.get_parent(), 1)
	panel.label(page, "Прокрути клип на модели, останови на нужном кадре и проверь падение из этой позы. Скорость просмотра — на вкладке «Настройка».")
	_clips = CharacterAnimator.clip_names()
	_clips.sort()
	var clips: OptionButton = panel.option("Клип", Array(_clips), func(index: int) -> void:
		_clip = _clips[index]
		_play_clip(), page)
	if not _clips.is_empty():
		var index: int = maxi(0, _clips.find("r8_walk_f"))
		clips.select(index)
		_clip = _clips[index]
	var row: HBoxContainer = HBoxContainer.new()
	page.add_child(row)
	panel.action("Воспроизвести", _play_clip, row)
	panel.action("Пауза / дальше", func() -> void:
		_clip_paused = not _clip_paused
		_settings_changed(), row)
	_timeline = HSlider.new()
	_timeline.step = 0.01
	_timeline.editable = false
	_timeline.custom_minimum_size.y = 26
	page.add_child(_timeline)
	_timeline.value_changed.connect(func(value: float) -> void:
		if is_instance_valid(clip_player):
			clip_player.seek(value, true))
	panel.action("Вернуть игровую анимацию", _stop_clip, page)
	panel.action("Падение из текущей позы", _fall, page)
	panel.action("Восстановить бойца", _reset_enemy, page)


func _build_combat_controls() -> void:
	var page: VBoxContainer = panel._page("Огонь")
	panel.tabs.move_child(page.get_parent(), 2)
	panel.label(page, "В режиме осмотра видно бойца со стороны. F6 даёт управление, ЛКМ — выстрел по бойцу.")
	_crouch = CheckButton.new()
	_crouch.text = "Противник присел"
	page.add_child(_crouch)
	_crouch.toggled.connect(func(value: bool) -> void:
		if enemy._health.alive:
			_stop_clip()
			enemy._set_crouch(value))
	_auto_fire = CheckButton.new()
	_auto_fire.text = "Противник стреляет по игроку"
	page.add_child(_auto_fire)
	_auto_fire.toggled.connect(func(enabled: bool) -> void:
		if enabled:
			_stop_clip()
		if enemy._health.alive:
			enemy.state = Marauder.State.COMBAT if enabled else Marauder.State.PATROL)
	panel.action("Один выстрел противника", func() -> void:
		_stop_clip()
		_one_shot = true, page)
	panel.action("Перезарядить противника", func() -> void:
		if enemy._health.alive:
			_stop_clip()
			enemy._start_reload()
			if enemy._reload_t <= 0.0:
				panel.status.text = "Сначала израсходуй хотя бы один патрон.", page)
	panel.action("Проверить падение", _fall, page)
	panel.action("Восстановить бойца", _reset_enemy, page)
	panel.action("Выбрать оружие игрока на вкладке «Боец»", func() -> void: panel.tabs.current_tab = 0, page)
	weapon_selector()


func _reset_enemy() -> void:
	_stop_clip()
	if is_instance_valid(enemy):
		if is_instance_valid(enemy._ragdoll):
			enemy._ragdoll.queue_free()
		remove_child(enemy)
		enemy.queue_free()
	_auto_fire.set_pressed_no_signal(false)
	_crouch.set_pressed_no_signal(false)
	_one_shot = false
	_last_hit = ""
	enemy = MARAUDER.instantiate() as Marauder
	enemy.name = "TestEnemy"
	enemy.archetype = "gunner"
	enemy.loadout_id = _loadout
	enemy.weapon = _weapon
	enemy.position = START
	add_child(enemy)
	enemy.set_physics_process(false)
	enemy._face(player.global_position)
	enemy._body.rotation.y = enemy._facing
	enemy._health.damaged.connect(func(_amount: float, _from: Vector3) -> void:
		_last_hit = String(enemy._health.last_zone))
	animator = enemy.get_node("CharacterAnimator") as CharacterAnimator
	_update_camera()


func _play_clip() -> void:
	if not enemy._health.alive or _clip.is_empty():
		return
	_one_shot = false
	_auto_fire.set_pressed_no_signal(false)
	_clip_paused = false
	clip_player = animator.preview_clip(_clip, Balance.lab_number("enemy", "clip_speed"))
	_timeline.editable = clip_player != null
	if clip_player:
		_timeline.max_value = clip_player.current_animation_length
		_timeline.set_value_no_signal(0.0)


func _stop_clip() -> void:
	if is_instance_valid(animator):
		animator.stop_clip_preview()
	clip_player = null
	if _timeline:
		_timeline.editable = false
		_timeline.set_value_no_signal(0.0)


func _settings_changed() -> void:
	if is_instance_valid(clip_player):
		clip_player.speed_scale = 0.0 if _clip_paused else Balance.lab_number("enemy", "clip_speed")


func _fall() -> void:
	if enemy._health.alive:
		enemy._health.take_damage(enemy._health.max_hp, player.global_position, "blast_close")


func _update_camera() -> void:
	var center: Vector3 = START + Vector3.UP * 0.95
	var angle: float = deg_to_rad(_orbit)
	observer.global_position = center + Vector3(sin(angle), 0.3, -cos(angle)) * _distance
	observer.look_at(center)


func _physics_process(delta: float) -> void:
	if not is_instance_valid(enemy) or not enemy._health.alive:
		return
	enemy._tick_weapon(delta)
	if not (_one_shot or _auto_fire.button_pressed) or enemy._reload_t > 0.0 or enemy._shot_t > 0.0:
		return
	enemy.state = Marauder.State.COMBAT
	enemy.last_known = player.global_position
	enemy._face(enemy.last_known)
	enemy._body.rotation.y = enemy._facing
	enemy._try_fire()
	_one_shot = false


func _lab_tick(_delta: float) -> void:
	if not is_instance_valid(enemy):
		return
	if is_instance_valid(clip_player) and enemy._health.alive:
		_timeline.set_value_no_signal(clip_player.current_animation_position)
		telemetry.text = "%s   ·   %.2f / %.2f с" % [_clip, _timeline.value, _timeline.max_value]
		return
	if _timeline.editable:
		_stop_clip()
	var state: String = "Стоит" if enemy._health.alive else "Тело · физика"
	if enemy._health.downed:
		state = "Ранен"
	elif enemy._reload_t > 0.0:
		state = "Перезаряжается"
	elif enemy._health.alive and enemy.state == Marauder.State.COMBAT:
		state = "Целится"
	telemetry.text = "%s   ·   Здоровье %.0f / %.0f   ·   Патроны %d" % [state, enemy._health.hp, enemy._health.max_hp, enemy._mag]
	if _last_hit != "":
		telemetry.text += "\nПоследнее попадание · " + String({"head": "голова", "thorax": "грудь",
			"arms": "руки", "legs": "ноги", "blast_close": "проверка падения"}.get(_last_hit, _last_hit))
