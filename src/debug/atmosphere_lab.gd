class_name AtmosphereLab
extends DevelopmentLab
## Свет на «Проспекте» с игровым циклом суток и погодой. Ползунки — той схемы света,
## что выбрана («Свет и небо»): у света Road to Vostok свой набор (LAB_RULES.atmosphere_tod), у прежнего — свой.

const AREA_HALF_SIZE := Vector2(25.0, 25.0)
const BOUNDARY_LAYER := 1 << 30
const SPAWN_OFFSETS := [Vector3.ZERO, Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.BACK]
const AREAS := [
	{"title": "Сквер", "center": Vector2(-14, 88), "spawn": Vector3(-20, 0.08, 66), "yaw": 0.12},
	{"title": "Стройка", "center": Vector2(-105, 152), "spawn": Vector3(-105, 0.08, 131), "yaw": -0.45},
	{"title": "Проспект у «Зерна»", "center": Vector2(-184, -35), "spawn": Vector3(-184, 0.08, -28), "yaw": PI},
]

@export var map_scene: PackedScene

var _area_index: int = 0
var _bounds: Rect2
var _boundary: StaticBody3D
var _ground_holes: Array[Rect2] = []
var _spawn_pending := false
var _sky_mode_before: String = "tod"


func _notification(what: int) -> void:
	if what == NOTIFICATION_SCENE_INSTANTIATED:
		_load_map()


func _ready() -> void:
	_sky_mode_before = Settings.sky_mode
	lab_domain = TodLight.LAB_DOMAIN if TodLight.active() else "atmosphere"
	super._ready()
	leave_overview_to_play = true
	var world: Node3D = $World
	var plan: Dictionary = world.get_node("Landscape").get("plan")
	for hole: Array in plan.get("ground_holes", []):
		var corner := Vector2(hole[0], hole[1])
		_ground_holes.append(Rect2(corner, Vector2(hole[2], hole[3]) - corner))
	_build_boundary()
	for batch_root: Node in get_tree().get_nodes_in_group("urban_prop_batches"):
		if world.is_ancestor_of(batch_root):
			PropBatcher.batch(batch_root as Node3D, float(Balance.URBAN_WORLD.batch_cell), float(Balance.URBAN_WORLD.prop_distance))
	var area_names: Array[String] = []
	for area: Dictionary in AREAS:
		area_names.append(area.title)
	var area_picker := panel.option("Площадка на «Проспекте» · 50 × 50 м", area_names, _move_location)
	area_picker.name = "AreaSelector"
	panel.action("К началу площадки · F9", _request_spawn)
	_move_location(0)
	start_atmosphere(16.0)
	panel.option("Погода для просмотра", ["Ясно", "Пасмурно", "Дождь", "Туман", "Жара"], set_weather)
	var names: Array[String] = []
	for mode: String in Settings.SKY_MODES:
		names.append(String(Settings.SKY_MODE_NAMES[mode]))
	var sky_mode: OptionButton = panel.option("Свет и небо", names, _set_light_model)
	sky_mode.select(maxi(0, Settings.SKY_MODES.find(Settings.sky_mode)))
	panel.number("Часы · 0–24 (условие просмотра)", 16.0, 0.0, 23.95, 0.1, set_hour)
	weapon_selector()
	panel.label(panel.context, "F6 — пройтись по площадке. F7 — сравнить свет в той же точке. Часы и погода действуют во всех трёх местах стенда.", 14)
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


func _load_map() -> void:
	# Подключаем геометрию и свет до входа в дерево, чтобы не запускать сценарий рейда.
	var level: Node3D = map_scene.instantiate() as Node3D
	for node: Node in [$Ground, $Sun, $WorldEnvironment]:
		node.free()
	var world: Node3D = level.get_node("World") as Node3D
	var sun: DirectionalLight3D = level.get_node("Sun") as DirectionalLight3D
	var environment_node: WorldEnvironment = level.get_node("WorldEnvironment") as WorldEnvironment
	world.get_node("WorldEnvironment").free()
	for node: Node in [world, sun, environment_node]:
		node.owner = null
		level.remove_child(node)
		add_child(node)
	level.free()


func _move_location(index: int) -> void:
	_area_index = index
	var area: Dictionary = AREAS[index]
	var center: Vector2 = area.center
	_bounds = Rect2(center - AREA_HALF_SIZE, AREA_HALF_SIZE * 2.0)
	_boundary.position = Vector3(center.x, 0.0, center.y)
	observer.position = Vector3(center.x, 100.0, center.y)
	observer.rotation_degrees = Vector3(-90.0, 0.0, 0.0)
	observer.fov = 38.0
	_request_spawn()


func _build_boundary() -> void:
	# Край площадки участвует только в движении игрока, поэтому не влияет на свет и физические лучи карты.
	_boundary = StaticBody3D.new()
	_boundary.name = "AreaBoundary"
	_boundary.collision_layer = BOUNDARY_LAYER
	_boundary.collision_mask = 0
	for outward: Vector3 in [Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.BACK]:
		var wall := CollisionShape3D.new()
		var box_shape := BoxShape3D.new()
		box_shape.size = Vector3(1.0, 160.0, 52.0) if outward.x != 0.0 else Vector3(52.0, 160.0, 1.0)
		wall.shape = box_shape
		wall.position = outward * (AREA_HALF_SIZE.x + 0.5)
		_boundary.add_child(wall)
	add_child(_boundary)
	player.collision_mask |= BOUNDARY_LAYER


func _request_spawn() -> void:
	_spawn_pending = true


func _physics_process(_delta: float) -> void:
	if not _spawn_pending:
		return
	_spawn_pending = false
	var area: Dictionary = AREAS[_area_index]
	var destination := _safe_spawn(area.spawn)
	if not destination.is_finite():
		panel.status.text = "На площадке нет свободной точки появления. Выбери другую площадку."
		set_editing(true)
		return
	if player.ladder != null:
		player._release_ladder(Vector3.ZERO)
	player._vault_t = -1.0
	player._vault_then = ""
	player._vault_stumble = false
	player._dive_t = -1.0
	player._draw_after_traversal()
	player.seated = false
	player.stance = Player.Stance.STAND
	player._apply_stance()
	player._eye_dy = 0.0
	player._stance_eye = -1.0
	player.position = destination
	player.reset_physics_interpolation()
	player.velocity = Vector3.ZERO
	player._eye_tick_ready = false
	player.face(area.yaw)
	rig._look_yaw = area.yaw
	rig._look_pitch = 0.0
	if atmosphere:
		atmosphere._indoor_cache.clear()


func _safe_spawn(anchor: Vector3) -> Vector3:
	var space := player.get_world_3d().direct_space_state
	var capsule := CapsuleShape3D.new()
	capsule.radius = Balance.CAPSULE_RADIUS
	capsule.height = float(Balance.STANCE_HEIGHT.stand)
	var clearance := PhysicsShapeQueryParameters3D.new()
	clearance.shape = capsule
	clearance.collision_mask = player.collision_mask
	clearance.exclude = [player.get_rid()]
	for offset: Vector3 in SPAWN_OFFSETS:
		var at := anchor + offset
		var ray := PhysicsRayQueryParameters3D.create(at + Vector3.UP * 1.5, at + Vector3.DOWN, Hitscan.LAYER_WORLD)
		var hit := space.intersect_ray(ray)
		if hit.is_empty() or (hit.normal as Vector3).y < cos(player.floor_max_angle):
			continue
		var feet: Vector3 = hit.position + Vector3.UP * 0.06
		clearance.transform.origin = feet + Vector3.UP * capsule.height * 0.5
		if space.intersect_shape(clearance, 1).is_empty():
			return feet
	return Vector3.INF


func _check_player_position() -> void:
	var position_xz := Vector2(player.position.x, player.position.z)
	if player.position.y < -9.0 or not _bounds.grow(0.1).has_point(position_xz):
		_request_spawn()
		return
	if player.position.y >= -0.6:
		return
	for hole: Rect2 in _ground_holes:
		if hole.grow(Balance.CAPSULE_RADIUS).has_point(position_xz):
			return
	_request_spawn()


func _input(event: InputEvent) -> void:
	if not PauseMenu.shown and event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F9:
		_request_spawn()
		get_viewport().set_input_as_handled()
		return
	super._input(event)


func set_editing(enabled: bool) -> void:
	super.set_editing(enabled)
	$Interface/Telemetry.visible = enabled
	$Interface/Hint.visible = enabled


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
	telemetry.text = "%s · 50 × 50 м\nВремя: %s · погода: %s\nСолнце / Луна: %.3f · рассеянный свет: %.3f\nЭкспозиция: %.2f · туман: %.4f\n%s\n%s" % [
		AREAS[_area_index].title,
		DayCycle.current.clock_text() if DayCycle.current else "—", String(RaidConditions.spec("weather").get("name", RaidConditions.current.weather)),
		sun.light_energy, environment.ambient_light_energy, environment.tonemap_exposure, environment.fog_density,
		"Игрок под крышей" if atmosphere and atmosphere.is_indoor(player.position) else "Игрок на улице",
		"СРАВНЕНИЕ: исходный свет" if panel.compare.button_pressed else "Предпросмотр выбранного варианта"]
