class_name RaidEvents
extends Node
## Случайные события рейда: отключение света, авария генератора (дым, гул, починить — у
## генератора), сброс припасов в атриум (вертолёт; туда бегут все, за грузом — ЧВК), ЧВК
## «Периметр» приезжают на парковку, жильцы в забаррикадированных магазинах, магазины на
## сигнализации, задание по рации от Михалыча (если в убежище есть рация).
## Что и когда — решает хост в начале рейда и рассылает всем (узел с одним именем у всех peer);
## людей ставит хост (спавнер), картинку, звук и сообщения — каждый peer у себя.
## Вероятности и времена — Balance.RAID_EVENTS. Создаёт SectorLevel.

static var current: RaidEvents
## Тесты старых систем выключают события: жильцы, ЧВК и свет не должны мешать проверкам.
static var enabled: bool = true

var level: Node
var _t: float = 0.0
var _schedule: Array = []
var _rng := RandomNumberGenerator.new()
var _alarms: Array = []
## Генератор ТЦ — узел уровня (MallGenerator); нет его на уровне — ставится у техкомплекса.
var _generator: MallGenerator
## Свет в ТЦ: положение главного рубильника (электрощитовая, MallBreaker) — "on" / "emergency" /
## "off", и стоит ли генератор (тогда даже «on» — только аварийный). Решает хост, знают все.
var breaker: String = "on"
var generator_down: bool = false
var _drop_pos: Vector3 = Vector3.INF
var _pmc_spawned: bool = false
var _radio: Dictionary = {}
var _radio_label: Label
var _setup_ready: bool = false
var _initial_homes: Array = []
var _initial_alarms: Array = []
var _known: Array[int] = []


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null


func _ready() -> void:
	_rng.randomize()
	level = get_parent()
	Net.scenes_changed.connect(_share_setup)
	# с чем пришли: «света нет» — рубильник внизу и генератор стоит (поднять можно только
	# аварийный), «аварийный» — генератор стоит
	match String(RaidConditions.current.get("power", "on")):
		"off":
			breaker = "off"
			generator_down = true
		"emergency":
			generator_down = true
	# стоит с начала рейда — должен быть где чинить (на уровне без своего генератора — поставить)
	if generator_down:
		generator.call_deferred()
	if not enabled:
		return
	if not Net.is_networked() or multiplayer.is_server():
		_setup_host.call_deferred()
	_setup_radio()


## Хост: жильцы, сигнализация, расписание событий — всем.
func _setup_host() -> void:
	var ev: Dictionary = Balance.RAID_EVENTS
	var rooms: Array = level.get("_rooms") if level.get("_rooms") != null else []
	var retail: Array = []
	for r in rooms:
		if String((r as Dictionary).get("type", "")) == "retail" and not bool((r as Dictionary).get("locked", false)) and not SectorBuilder.is_strip(r):
			retail.append(r)
	retail.shuffle()
	var homes: Array = []
	var res: Dictionary = Balance.RESIDENTS
	var ng := _rng.randi_range(int(res.groups[0]), int(res.groups[1]))
	for i in range(mini(ng, retail.size())):
		var r: Dictionary = retail.pop_back()
		homes.append([_room_center(r), _room_half(r), _rng.randf() < float(res.hostile_share)])
	var alarms: Array = []
	for i in range(mini(int(ev.alarm_shops), retail.size())):
		var r: Dictionary = retail.pop_back()
		alarms.append([_room_center(r), _room_half(r)])
	var sched: Array = []
	var power := String(RaidConditions.current.power)
	if power == "on" and _rng.randf() < float(ev.outage_chance):
		sched.append(["outage", _rng.randf_range(float(ev.outage_at[0]), float(ev.outage_at[1]))])
	elif power == "on" and _rng.randf() < float(ev.generator_chance):
		sched.append(["generator", _rng.randf_range(float(ev.generator_at[0]), float(ev.generator_at[1]))])
	if _rng.randf() < float(ev.drop_chance):
		sched.append(["drop", _rng.randf_range(float(ev.drop_at[0]), float(ev.drop_at[1]))])
	if _rng.randf() < float(ev.pmc_chance):
		sched.append(["pmc", _rng.randf_range(float(ev.pmc_at[0]), float(ev.pmc_at[1]))])
	if Net.is_networked():
		await get_tree().create_timer(2.0).timeout
		_rpc_setup(homes, alarms, sched)
		_initial_homes = homes
		_initial_alarms = alarms
		_setup_ready = true
		_share_setup()
	else:
		_rpc_setup(homes, alarms, sched)
	# жильцы — людей ставит хост
	for h in homes:
		_spawn_residents(h[0], float(h[1]), bool(h[2]))


@rpc("authority", "call_local", "reliable")
func _rpc_setup(homes: Array, alarms: Array, sched: Array) -> void:
	_schedule = sched
	for h in homes:
		_barricade(h[0], float(h[1]))
	for a in alarms:
		var z := AlarmZone.new()
		z.name = "Alarm_%d" % _alarms.size()
		z.radius = float(a[1])
		level.add_child(z)
		z.global_position = a[0]
		_alarms.append(z)


## Настройка приходит только после готовности Events у гостя, включая поздний вход.
func _share_setup() -> void:
	if not Net.is_host() or not _setup_ready:
		return
	var here: Array[int] = []
	for peer: int in multiplayer.get_peers():
		if Net.visible_in(peer, "raid"):
			here.append(peer)
			if not peer in _known:
				_receive_setup.rpc_id(peer, _initial_homes, _initial_alarms, _schedule, _t, breaker, generator_down)
	_known = here


@rpc("authority", "call_remote", "reliable")
func _receive_setup(homes: Array, alarms: Array, sched: Array, elapsed: float, pos: String, gen_down: bool) -> void:
	_t = elapsed
	_rpc_setup(homes, alarms, sched)
	_rpc_breaker(pos, gen_down)


## Для отладки и тестов: событие сейчас (хост рассылает).
func trigger(kind: String) -> void:
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_event", [kind])
	else:
		_rpc_event(kind)


func _process(delta: float) -> void:
	_t += delta
	for e in _schedule.duplicate():
		if _t >= float(e[1]):
			_schedule.erase(e)
			_rpc_event(String(e[0]))
	_tick_radio()


@rpc("authority", "call_local", "reliable")
func _rpc_event(kind: String) -> void:
	match kind:
		"outage":
			breaker = "off"
			_set_power(effective_power())
			Audio.play("power_down", _listener() + Vector3(0, 3, 6))
			_notify("Где-то щёлкнуло в щитовой — свет погас. Главный рубильник — в электрощитовой")
		"generator":
			_generator_fail()
		"generator_fixed":
			generator_down = false
			_set_power(effective_power())
			Audio.play("gen_start", generator().global_position + Vector3.UP)
			if breaker != "off":
				Audio.play("power_up", _listener())
			_notify("Генератор запущен — свет вернулся" if breaker != "off" else "Генератор запущен — теперь поднять главный рубильник в электрощитовой")
		"drop":
			_supply_drop()
		"pmc":
			_pmc_arrive()


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


func _notify(text: String) -> void:
	if Raid.current:
		Raid.current.notify(text)


func _listener() -> Vector3:
	var me: Player = Raid.current.local_player() if Raid.current else null
	return me.global_position if me else Vector3.ZERO


# ---------------------------------------------------------------- электричество

func _set_power(p: String) -> void:
	RaidConditions.current["power"] = p
	if RaidAtmosphere.current:
		RaidAtmosphere.current.apply_power(p)


## Что горит на самом деле: рубильник внизу — ничего; генератор стоит — только аварийный.
func effective_power() -> String:
	if breaker == "off":
		return "off"
	if generator_down or breaker == "emergency":
		return "emergency"
	return "on"


## Главный рубильник: следующее положение — выкл → аварийный → весь → выкл. Генератор стоит —
## выкл ↔ вкл (горит аварийный; починят — сразу весь).
func next_breaker() -> String:
	match breaker:
		"off":
			return "on" if generator_down else "emergency"
		"emergency":
			return "off" if generator_down else "on"
	return "off"


func set_breaker(pos: String) -> void:
	if not _is_host():
		return
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_breaker", [pos, generator_down])
	else:
		_rpc_breaker(pos, generator_down)


@rpc("authority", "call_local", "reliable")
func _rpc_breaker(pos: String, gen_down: bool) -> void:
	breaker = pos
	generator_down = gen_down
	_set_power(effective_power())


func _generator_fail() -> void:
	generator_down = true
	_set_power(effective_power())
	Audio.play("gen_stop", generator().global_position + Vector3.UP)
	_notify("Генератор встал — аварийный свет. Починить — %s (шумно)" % generator().where)


## Генератор ТЦ: стоит на уровне (мастерская). На уровне без него (старый сектор) — ставится у
## техкомплекса, с тем же именем у всех peer.
func generator() -> MallGenerator:
	if _generator != null and is_instance_valid(_generator):
		return _generator
	_generator = get_tree().get_first_node_in_group("mall_generator") as MallGenerator
	if _generator == null:
		var tech := level.get_node_or_null("Buildings/TechComplex") as Node3D
		_generator = MallGenerator.new()
		_generator.name = "Generator"
		_generator.where = "у технического комплекса"
		level.add_child(_generator)
		_generator.global_position = tech.global_position if tech else SectorBuilder.polar(-10.0, 170.0)
	return _generator


## Хост: генератор починили — свет всем.
func generator_fixed() -> void:
	if _is_host():
		if Net.is_networked():
			Net.broadcast_scene(self, &"_rpc_event", ["generator_fixed"])
		else:
			_rpc_event("generator_fixed")


# ---------------------------------------------------------------- сброс припасов

func _supply_drop() -> void:
	_drop_pos = SectorBuilder.polar(-90.0, 10.0)
	Audio.play("heli", _drop_pos + Vector3(0, 40, 0))
	_notify("Вертолёт над атриумом — что-то сбросили")
	# красный дым у груза
	var smoke := _smoke(Color(0.8, 0.15, 0.1, 0.5))
	level.add_child(smoke)
	smoke.global_position = _drop_pos
	get_tree().create_timer(float(Balance.RAID_EVENTS.drop_smoke_sec)).timeout.connect(func() -> void:
		if is_instance_valid(smoke):
			smoke.emitting = false)
	if _is_host():
		get_tree().create_timer(4.0).timeout.connect(func() -> void:
			if Raid.current == null:
				return
			var rng := RandomNumberGenerator.new()
			rng.randomize()
			Raid.current.spawn_drop(_drop_pos, "Сброшенный груз", ItemDb.roll("supply_drop", rng), LootContainer.Look.CRATE, Vector3(0, 30, 0))
			Audio.play("drop_land", _drop_pos)
			# слышно далеко — туда пойдут все
			NoiseBus.emit(_drop_pos, float(Balance.RAID_EVENTS.drop_noise_m), "drop"))
		# за своим грузом едут ЧВК
		if not _pmc_spawned:
			get_tree().create_timer(20.0).timeout.connect(func() -> void: trigger("pmc"))


# ---------------------------------------------------------------- ЧВК

func _pmc_arrive() -> void:
	if _pmc_spawned:
		return
	_pmc_spawned = true
	var at := SectorBuilder.polar(-169.0, 160.0)
	Audio.play("engine", at, 4.0)
	Audio.play("truck_doors", at)
	_notify("На парковке заглушили мотор. Хлопнули двери.")
	if _is_host() and level.has_method("spawn_squad"):
		var n := int(Balance.PMC_SQUAD)
		var archs: Array = []
		for i in range(n):
			archs.append("pmc")
		var target := _drop_pos if _drop_pos != Vector3.INF else Vector3.INF
		level.call("spawn_squad", at, archs, {"target": target})


# ---------------------------------------------------------------- жильцы

func _spawn_residents(at: Vector3, radius: float, hostile: bool) -> void:
	if not level.has_method("spawn_squad"):
		return
	var res: Dictionary = Balance.RESIDENTS
	var n := _rng.randi_range(int(res.size[0]), int(res.size[1]))
	var archs: Array = []
	for i in range(n):
		archs.append("resident")
	level.call("spawn_squad", at, archs, {"home": at, "home_r": maxf(3.0, radius * 0.7), "hostile": hostile})


## Баррикада у магазина жильцов: ящики поперёк — видно, что тут живут.
func _barricade(at: Vector3, radius: float) -> void:
	var root := Node3D.new()
	root.name = "Barricade"
	level.add_child(root)
	root.global_position = at
	var rng := RandomNumberGenerator.new()
	rng.seed = int(at.x * 13.0 + at.z * 7.0)
	for i in range(6):
		var a := TAU * float(i) / 6.0 + rng.randf() * 0.4
		var p := Vector3(cos(a), 0.0, sin(a)) * radius * 0.85
		root.add_child(QuestProps.build({"kind": "crate", "at": [p.x, 0.0, p.z], "yaw": rng.randf() * 90.0}, rng))
	root.add_child(QuestProps.build({"kind": "cot", "at": [0.0, 0.0, 0.0], "yaw": 30.0}, rng))
	root.add_child(QuestProps.build({"kind": "item", "id": "canned", "at": [0.8, 0.0, 0.4]}, rng))
	var lamp := OmniLight3D.new()
	lamp.light_color = Color(1.0, 0.7, 0.4)
	lamp.light_energy = 1.2
	lamp.omni_range = 7.0
	lamp.position = Vector3(0.4, 1.0, 0.2)
	root.add_child(lamp)


# ---------------------------------------------------------------- рация Михалыча

## С рацией в убежище (модуль) — по ходу рейда Михалыч просит вынести вещь: заплатит втрое.
func _setup_radio() -> void:
	if not Profile.pending_raid or Upgrades.level("radio") <= 0:
		return
	var ev: Dictionary = Balance.RAID_EVENTS
	var ids: Array = ev.radio_items
	var id := String(ids[_rng.randi_range(0, ids.size() - 1)])
	_radio = {"id": id, "at": _rng.randf_range(float(ev.radio_at[0]), float(ev.radio_at[1])), "shown": false,
		"reward": ItemDb.value(id) * int(ev.radio_mult)}


func _tick_radio() -> void:
	if _radio.is_empty() or bool(_radio.shown) or _t < float(_radio.at):
		return
	_radio.shown = true
	Audio.play("radio", _listener(), -4.0)
	_notify("Рация, Михалыч: «%s — вынеси, заплачу %s ₽»" % [ItemDb.item_name(String(_radio.id)), InventoryUI.money(int(_radio.reward))])
	var layer := CanvasLayer.new()
	layer.layer = 11
	add_child(layer)
	_radio_label = Label.new()
	_radio_label.anchor_left = 1.0
	_radio_label.anchor_right = 1.0
	_radio_label.offset_left = -440
	_radio_label.offset_right = -24
	_radio_label.offset_top = 250
	_radio_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_radio_label.add_theme_font_size_override("font_size", 15)
	_radio_label.add_theme_color_override("font_color", Color(0.7, 0.9, 1.0))
	_radio_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_radio_label.add_theme_constant_override("outline_size", 5)
	_radio_label.text = "Рация: вынести «%s» — %s ₽" % [ItemDb.item_name(String(_radio.id)), InventoryUI.money(int(_radio.reward))]
	layer.add_child(_radio_label)


## Свой игрок эвакуировался: предмет из задания по рации в рюкзаке — Михалыч платит.
func on_local_extracted(me: Player) -> void:
	if _radio.is_empty() or not bool(_radio.shown) or me == null or not me.inventory.has(String(_radio.id)):
		return
	Profile.money += int(_radio.reward)
	Profile.save()
	_notify("Михалыч: «Принёс — держи %s ₽»" % InventoryUI.money(int(_radio.reward)))
	_radio = {}


# ---------------------------------------------------------------- помощники

func _room_center(r: Dictionary) -> Vector3:
	if r.has("rect"):
		var rect: Array = r.rect
		return Vector3((float(rect[0]) + float(rect[2])) * 0.5, float(r.get("y", 0.0)), (float(rect[1]) + float(rect[3])) * 0.5)
	return SectorBuilder.polar((float(r.a[0]) + float(r.a[1])) * 0.5, (float(r.r[0]) + float(r.r[1])) * 0.5)


func _room_half(r: Dictionary) -> float:
	if r.has("rect"):
		var rect: Array = r.rect
		return minf(float(rect[2]) - float(rect[0]), float(rect[3]) - float(rect[1])) * 0.5
	var depth := float(r.r[1]) - float(r.r[0])
	var arc := deg_to_rad(float(r.a[1]) - float(r.a[0])) * (float(r.r[0]) + float(r.r[1])) * 0.5
	return minf(depth, arc) * 0.5


static func _smoke(color: Color) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = 160
	p.lifetime = 6.0
	p.visibility_aabb = AABB(Vector3(-10, 0, -10), Vector3(20, 40, 20))
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3(0, 1, 0)
	pm.spread = 12.0
	pm.initial_velocity_min = 1.5
	pm.initial_velocity_max = 3.0
	pm.gravity = Vector3(0.3, 0.4, 0.0)
	pm.scale_min = 1.0
	pm.scale_max = 2.5
	pm.damping_min = 0.2
	pm.damping_max = 0.5
	p.process_material = pm
	var q := QuadMesh.new()
	q.size = Vector2(1.6, 1.6)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = color
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	q.material = m
	p.draw_pass_1 = q
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return p
