extends Node
## Погода: дождь (слышно хуже, видно хуже, капли, мокрый асфальт), дождь начинается в рейде, пасмурно (сыро без капель),
## туман (снайпер с пистолетом, рассеялся — снова винтовка), жара (пересвет без очков),
## выносливость (бег тратит, в жару быстрее). С окном — снимки docs/screens/weather_*.png.
## godot --path . res://tools/weather_test.tscn (можно --headless)
## Карта ТЦ Ø200 с территорией: точки — на земле (_ground), уличные — на открытом месте к северу и югу от ТЦ.

## Улица к северу от ТЦ (сквер, ровная земля, крыши нет) и площадь к югу: вдоль +X свободно 80 м — там бегут.
const OUT_NORTH := Vector2(-90.0, 160.0)
const OUT_SOUTH := Vector2(90.0, 150.0)

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
	var street := _ground(OUT_NORTH)
	_check("дождь: на улице видно хуже", not RaidAtmosphere.current.is_indoor(street) and is_equal_approx(RaidAtmosphere.current.view_distance(street, false),
		float(Balance.RAID_TIME.day.view) * float(Balance.RAID_WEATHER.rain.view)), "%.0f м" % RaidAtmosphere.current.view_distance(street, false))
	_check("дождь: капли и шум", _level.find_child("Rain", true, false) != null, "")
	if shots:
		await _shot("weather_rain", _ground(OUT_NORTH))
	# ясно → дождь по ходу рейда
	await _load({"time": "day", "weather": "clear", "power": "on"})
	RaidWeather.current._rpc_schedule(1.0, -1.0)
	await get_tree().create_timer(1.6).timeout
	_check("дождь начался в рейде", RaidWeather.current.is_raining() and _level.find_child("Rain", true, false) != null, str(RaidConditions.current))
	# пасмурно (сырой вечер — одна из погод): сыро без капель, ниже сырости не сохнет, может пойти дождь
	await _load({"time": "dusk", "weather": "overcast", "power": "on"})
	var dmp: Array = Balance.WET_GROUND.damp
	var rw := RaidWeather.current
	_check("пасмурно: сыро и лужи, капель нет", rw.wet >= float(dmp[0]) - 0.01 and rw.puddles >= float(dmp[1]) - 0.01
		and _level.find_child("Rain", true, false) == null, "плёнка %.2f, лужи %.2f" % [rw.wet, rw.puddles])
	rw._tick_wet(600.0)
	_check("пасмурно: за 10 минут не высохло, фасады и рельеф сырые", rw.wet >= float(dmp[0]) - 0.01 and RaidWeather.surface_damp() > 0.2,
		"плёнка %.2f, сырость %.2f" % [rw.wet, RaidWeather.surface_damp()])
	if shots:
		await _shot("weather_overcast", _ground(OUT_NORTH))
	rw._rpc_schedule(rw._t + 0.5, -1.0)
	await get_tree().create_timer(1.2).timeout
	_check("пасмурно → пошёл дождь", rw.is_raining() and _level.find_child("Rain", true, false) != null, str(RaidConditions.current))
	# туман: снайпер — с пистолетом; рассеялся — снова винтовка
	await _load({"time": "day", "weather": "fog", "power": "on"})
	var sn := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	sn.name = "FogSniper"
	sn.archetype = "sniper"
	_level.get_node("Marauders").add_child(sn)
	sn.global_position = _ground(Vector2(-120.0, 150.0)) + Vector3(0, 0.1, 0)
	# В scav_sniper есть и автомат с ПСО: вернуть надо своё основное оружие,
	# а не обязательно класс SNIPER/DMR из прежней версии таблицы.
	var primary_class: String = String(WeaponStats.compute(sn.equipment.primary).get("class", ""))
	await get_tree().create_timer(0.3).timeout
	var fogged: bool = sn._active == "secondary" and String(sn._spec["class"]) == "PISTOL" and not sn._holds()
	if shots:
		await _shot("weather_fog", _ground(OUT_NORTH))
	RaidWeather.current._rpc_schedule(-1.0, RaidWeather.current._t + 0.3)
	await get_tree().create_timer(0.8).timeout
	_check("туман: снайпер с пистолетом, рассеялся — своё основное оружие", fogged and sn._active == "primary" and String(sn._spec["class"]) == primary_class and sn._holds(), str(sn._spec.get("class")))
	# жара
	await _load({"time": "day", "weather": "heat", "power": "on"})
	var me := Raid.current.local_player()
	me.global_position = _ground(OUT_NORTH) + Vector3(0, 0.1, 0)
	await get_tree().create_timer(2.5).timeout
	var env := (_level.find_children("*", "WorldEnvironment", true, false)[0] as WorldEnvironment).environment
	var glare := env.adjustment_enabled and env.adjustment_brightness > 1.2
	if shots:
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/weather_heat.png"))
	me.inventory.equipment = {"eyes": ItemDb.make("sunglasses", 1)}
	await get_tree().create_timer(2.5).timeout
	# цветокоррекция карты остаётся — в очках нет только пересвета
	_check("жара: на улице пересвет, в очках — нет", glare and env.adjustment_brightness <= 1.2, "")
	if shots:
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/weather_heat_glasses.png"))
	# выносливость: бег тратит, в жару быстрее. Один и тот же забег по площади — в жару и в ясную погоду
	# (та же стойка, оружие, рюкзак; меняется только погода в условиях рейда, которую читает Player._tick_stamina)
	var hot_used := await _sprint(me)
	var hot_left := me.stamina
	await get_tree().create_timer(3.0).timeout
	_check("отдых восстанавливает", me.stamina > hot_left + 10.0, "%.0f → %.0f" % [hot_left, me.stamina])
	RaidConditions.current["weather"] = "clear"
	var clear_used := await _sprint(me)
	RaidConditions.current["weather"] = "heat"
	# в жару на улице расход × Balance.STAMINA_HEAT (1.7); запас на разгон и торможение
	_check("бег тратит выносливость, в жару быстрее", clear_used > Balance.STAMINA_DRAIN and hot_used > clear_used * 1.3,
		"за 3 с бега: в жару %.1f, в ясную %.1f" % [hot_used, clear_used])
	print("weather_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Три секунды бега вдоль +X по площади к югу от ТЦ с полной выносливости; сколько потрачено.
func _sprint(me: Player) -> float:
	me.global_position = _ground(OUT_SOUTH) + Vector3(0, 0.1, 0)
	me.velocity = Vector3.ZERO
	for i in range(5):
		await get_tree().physics_frame
	me.stamina = Balance.STAMINA_MAX
	_face(Vector3.RIGHT)
	Input.action_press("sprint")
	Input.action_press("move_forward")
	await get_tree().create_timer(3.0).timeout
	var used := Balance.STAMINA_MAX - me.stamina
	Input.action_release("sprint")
	Input.action_release("move_forward")
	return used


## Повернуть взгляд игрока по направлению dir: из глаз ход задаёт взгляд (CameraRig._look_yaw → Player.look_yaw),
## сверху — поворот камеры.
func _face(dir: Vector3) -> void:
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	rig.rotation.y = atan2(-dir.x, -dir.z)
	rig._look_yaw = atan2(dir.x, dir.z)


## Точка карты по углу и радиусу (SectorBuilder.polar) — на земле: рельеф территории не на нуле (горки, выемки).
func _ground(ar: Vector2) -> Vector3:
	var p := SectorBuilder.polar(ar.x, ar.y)
	var hit := get_viewport().get_world_3d().direct_space_state.intersect_ray(
		PhysicsRayQueryParameters3D.create(p + Vector3.UP * 60.0, p + Vector3.DOWN * 60.0, 1))
	return hit.position as Vector3 if not hit.is_empty() else p


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
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
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
