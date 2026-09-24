extends Node
## Погода: дождь (слышно хуже, видно хуже, капли, мокрый асфальт), дождь начинается в рейде,
## туман (снайпер с пистолетом, рассеялся — снова винтовка), жара (пересвет без очков),
## выносливость (бег тратит, в жару быстрее). С окном — снимки docs/screens/weather_*.png.
## godot --path . res://tools/weather_test.tscn (можно --headless)

var _fails: int = 0
var _level: Node


func _ready() -> void:
	Profile.use_file("user://profile_weather_test.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var shots := DisplayServer.get_name() != "headless"
	# дождь с начала
	await _load({"time": "day", "weather": "rain", "power": "on"})
	var heard := [0.0]
	NoiseBus.noise.connect(func(_p: Vector3, r: float, _k: String) -> void: heard[0] = r)
	NoiseBus.emit(Vector3.ZERO, 50.0, "shot")
	_check("дождь: шум слышно ближе", is_equal_approx(heard[0], 50.0 * 0.6), "%.0f м вместо 50" % heard[0])
	_check("дождь: на улице видно хуже", is_equal_approx(RaidAtmosphere.current.view_distance(SectorBuilder.polar(-100.0, 150.0), false), 45.0), "")
	_check("дождь: капли и шум", _level.find_child("Rain", true, false) != null, "")
	if shots:
		await _shot("weather_rain", SectorBuilder.polar(-96.0, 150.0))
	# ясно → дождь по ходу рейда
	await _load({"time": "day", "weather": "clear", "power": "on"})
	RaidWeather.current._rpc_schedule(1.0, -1.0)
	await get_tree().create_timer(1.6).timeout
	_check("дождь начался в рейде", RaidWeather.current.is_raining() and _level.find_child("Rain", true, false) != null, str(RaidConditions.current))
	# туман: снайпер — с пистолетом; рассеялся — снова винтовка
	await _load({"time": "day", "weather": "fog", "power": "on"})
	var sn := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	sn.name = "FogSniper"
	sn.archetype = "sniper"
	_level.get_node("Marauders").add_child(sn)
	sn.global_position = SectorBuilder.polar(-120.0, 150.0) + Vector3(0, 0.1, 0)
	await get_tree().create_timer(0.3).timeout
	var fogged := sn._spec == Balance.AI_WEAPONS.pistol and not sn._holds()
	if shots:
		await _shot("weather_fog", SectorBuilder.polar(-96.0, 150.0))
	RaidWeather.current._rpc_schedule(-1.0, RaidWeather.current._t + 0.3)
	await get_tree().create_timer(0.8).timeout
	_check("туман: снайпер с пистолетом, рассеялся — снова винтовка", fogged and sn._spec == Balance.AI_WEAPONS.bolt and sn._holds(), "")
	# жара
	await _load({"time": "day", "weather": "heat", "power": "on"})
	var me := Raid.current.local_player()
	me.global_position = SectorBuilder.polar(-96.0, 150.0) + Vector3(0, 0.1, 0)
	await get_tree().create_timer(2.5).timeout
	var env := (_level.find_children("*", "WorldEnvironment", true, false)[0] as WorldEnvironment).environment
	var glare := env.adjustment_enabled and env.adjustment_brightness > 1.2
	if shots:
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/weather_heat.png"))
	me.inventory.equipment = {"eyes": ItemDb.make("sunglasses", 1)}
	await get_tree().create_timer(2.5).timeout
	_check("жара: на улице пересвет, в очках — нет", glare and not env.adjustment_enabled, "")
	if shots:
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/weather_heat_glasses.png"))
	# выносливость: бег тратит, в жару быстрее
	me.stamina = Balance.STAMINA_MAX
	Input.action_press("sprint")
	Input.action_press("move_forward")
	await get_tree().create_timer(1.0).timeout
	var hot_left := me.stamina
	Input.action_release("sprint")
	Input.action_release("move_forward")
	# за секунду бега в жару уходит больше обычного расхода
	_check("бег тратит выносливость, в жару быстрее", hot_left < Balance.STAMINA_MAX - Balance.STAMINA_DRAIN * 1.3, "осталось %.0f" % hot_left)
	await get_tree().create_timer(3.0).timeout
	_check("отдых восстанавливает", me.stamina > hot_left + 10.0, "%.0f" % me.stamina)
	print("weather_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _shot(n: String, at: Vector3) -> void:
	var me := Raid.current.local_player()
	me.global_position = at + Vector3(0, 0.1, 0)
	await get_tree().create_timer(2.0).timeout
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _load(c: Dictionary) -> void:
	if _level:
		_level.queue_free()
		await get_tree().process_frame
	RaidConditions.from_host = c
	_level = load("res://scenes/levels/f1_ring.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in _level.get_node("Marauders").get_children():
		m.queue_free()
	Raid.current.local_player().health.hp = 1e9
	for i in range(5):
		await get_tree().physics_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
