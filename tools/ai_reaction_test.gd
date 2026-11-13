extends "res://tools/hurt_direction_test.gd"
## Настоящие зрение, оружейный таймер и бой Marauder. Статистика — при фиксированном шаге 60 Гц.
## --headless res://tools/ai_reaction_test.tscn; -- host/client — предупреждение до попадания гостю.

const STEP: float = 1.0 / 60.0

class ReactionProbe:
	extends Marauder
	var shot_times: Array[float] = []
	var probe_time: float = 0.0
	var live: bool = false

	func _shoot(suppress: bool) -> void:
		shot_times.append(probe_time)
		if live:
			super._shoot(suppress)

var _enemy: ReactionProbe
var _noticed_ms: int = -1
var _hit_ms: int = -1


@rpc("authority", "call_local", "reliable")
func _spawn(client: int) -> void:
	super._spawn(client)
	var body: Marauder = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	body.set_script(ReactionProbe)
	_enemy = body as ReactionProbe
	_enemy.name = "ReactionShooter"
	_enemy.archetype = "gunner"
	_enemy.position = (_players[client] as Player).position + Vector3.BACK * 25.0
	add_child(_enemy)
	_enemy.set_physics_process(false)
	_enemy.set_process(false)
	_enemy.equipment.clear()
	_enemy._grenades = 0
	_enemy._spec.spread = 0.0
	_enemy._spec.damage = 10.0
	_enemy._spec.pellets = 1
	_enemy._spec.range = 150.0
	_rig._detection.set_process(false)
	if client != 1:
		(_players[1] as Player).remove_from_group("players")
		(_players[1] as Player).position += Vector3.RIGHT * 100.0


func _reset(arch: String = "gunner", seed_value: int = 1) -> void:
	_enemy.archetype = arch
	_enemy.state = Marauder.State.COMBAT
	_enemy.tactic = Marauder.Tactic.ENGAGE
	_enemy._tactic_t = 0.0
	_enemy._facing = PI
	_enemy.notice_timer = 0.0
	_enemy._seen_now = false
	_enemy._target_player = null
	_enemy._foe = null
	_enemy._shot_t = 0.0
	_enemy._reload_t = 0.0
	_enemy._burst_left = 0
	_enemy._mag = 99
	_enemy._callout_t = 1000.0
	_enemy._hurt_t = 0.0
	_enemy._suppress_t = 0.0
	_enemy._fire_reaction.reset()
	_enemy._fire_reaction.rng.seed = seed_value
	_enemy._opening_shots.clear()
	_enemy.shot_times.clear()
	_enemy.probe_time = 0.0
	_enemy.live = false
	_enemy._drop_fire_token()
	_rig._detection._contacts.clear()


func _step(delta: float = STEP) -> void:
	_enemy._perceive(delta)
	_enemy._tick_weapon(delta)
	if _enemy.state == Marauder.State.COMBAT:
		_enemy._combat(delta)


func _settle() -> void:
	await get_tree().physics_frame
	await get_tree().physics_frame
	await get_tree().process_frame


func _solo() -> void:
	await _settle()
	var player: Player = _players[1] as Player
	var profiles: Dictionary = {"gunner": [0.55, 0.9], "heavy": [0.35, 0.6], "pmc": [0.22, 0.4]}
	for arch: String in profiles:
		var samples: Array[float] = []
		var within: bool = true
		var not_early: bool = true
		for seed_value: int in range(1, 101):
			_reset(arch, seed_value)
			_step()
			var delay: float = _enemy._fire_reaction.last_delay
			within = within and delay >= float(profiles[arch][0]) and delay <= float(profiles[arch][1])
			not_early = not_early and _enemy.shot_times.is_empty() and _enemy._mag == 99
			for frame: int in range(1, 80):
				_enemy.probe_time = frame * STEP
				_step()
				if not _enemy.shot_times.is_empty():
					break
			var first: float = _enemy.shot_times[0] if not _enemy.shot_times.is_empty() else -1.0
			not_early = not_early and first >= delay and first <= delay + STEP + 0.0001
			samples.append(first)
		samples.sort()
		_check(arch + ": 100 задержек в заданном диапазоне", within)
		_check(arch + ": ни одного раннего выстрела, готовое оружие стреляет в следующий тик", not_early)
		print("AI_REACTION %s n=100 min=%.3f median=%.3f p95=%.3f max=%.3f" % [arch, samples[0], samples[49], samples[94], samples[99]])
	_reset()
	_enemy.state = Marauder.State.PATROL
	_step(0.01)
	_check("первичное распознавание ещё не подтверждено", not _enemy._seen_now and _enemy._fire_reaction.target_id == 0)
	_enemy._perceive(3.0)
	_enemy._try_fire()
	_check("предупреждение появляется при подтверждении, оружие ещё не стреляет", _enemy._seen_now and not _rig._detection._contacts.is_empty() and _enemy.shot_times.is_empty())
	_check("до наведения бот не занимает разрешение на прицельный огонь", _enemy._token_until == 0)
	var pending: float = _enemy._fire_reaction.remaining
	_enemy._try_fire(true)
	_check("подавление не обходит незавершённое наведение", _enemy.shot_times.is_empty())
	_enemy._facing = 0.0
	_enemy._perceive(0.1)
	_enemy._facing = PI
	_enemy._perceive(0.01)
	_check("короткий выход за тем же углом продолжает прежнее наведение", is_equal_approx(_enemy._fire_reaction.remaining, pending - 0.11))
	_enemy._perceive(1.0)
	_enemy._facing = 0.0
	_enemy._perceive(0.1)
	_enemy._facing = PI
	_enemy._perceive(0.01)
	_check("готовый прицел не даёт новую безопасную паузу при каждом выглядывании", _enemy._fire_reaction.can_fire())
	_check("при коротком выходе сохраняется и точность наведённого оружия", _enemy._aim < Balance.AI_AIM_COLD - 0.1)
	_enemy._facing = 0.0
	_enemy._perceive(1.21)
	_enemy._facing = PI
	_enemy._perceive(0.01)
	_check("долгая потеря требует нового наведения", _enemy._fire_reaction.remaining >= 0.55)
	# Выход с другой стороны: новая точка сначала проходит реальное зрение.
	_enemy._perceive(1.0)
	player.position = _enemy.position + Vector3.RIGHT * 25.0
	_enemy._facing = PI * 0.5
	await _settle()
	_enemy._perceive(STEP)
	_check("новое направление требует наведения", _enemy._seen_now and _enemy._fire_reaction.remaining >= 0.55)
	_enemy._perceive(1.0)
	for frame: int in range(20):
		player.position += Vector3.FORWARD * 0.05
		_enemy._perceive(STEP)
	_check("слежение за движущейся целью не запускает наведение каждый тик", _enemy._seen_now and _enemy._fire_reaction.can_fire())
	# Другая живая цель, пока предыдущая всё ещё видна.
	var second: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	second.name = "SecondTarget"
	second.loadout_mode = true
	second.position = player.position
	add_child(second)
	second.set_process(false)
	second.set_physics_process(false)
	player.remove_from_group("players")
	_enemy._perceive(1.0)
	await _settle()
	_enemy._perceive(STEP)
	_check("смена видимой цели тоже требует наведения", _enemy._target_player == second and _enemy._fire_reaction.target_id == second.get_instance_id() and _enemy._fire_reaction.remaining > 0.0)
	second.queue_free()
	player.add_to_group("players")
	player.position = _enemy.position + Vector3.FORWARD * 25.0
	await _settle()
	_reset()
	_enemy.tactic = Marauder.Tactic.AMBUSH
	_enemy._ambush_at = player.position
	_step()
	_check("подготовленная засада использует быстрый профиль", _enemy._fire_reaction.last_delay >= 0.15 and _enemy._fire_reaction.last_delay <= 0.3)
	player.position = _enemy.position + Vector3.FORWARD * 3.0
	await _settle()
	_reset()
	_step()
	_check("в упор отдельная короткая реакция", _enemy._fire_reaction.last_delay >= 0.15 and _enemy._fire_reaction.last_delay <= 0.25)
	player.position = _enemy.position + Vector3.FORWARD * 25.0
	await _settle()
	_reset()
	_enemy.live = true
	_step()
	var hp: float = player.health.hp
	_check("реальная пуля не наносит урон в тик обнаружения", is_equal_approx(hp, player.health.max_hp))
	for frame: int in range(1, 240):
		_enemy.probe_time = frame * STEP
		_step()
		if _enemy.shot_times.size() == int(Balance.AI_OPENING_FIRE.misses):
			break
	_check("первые три настоящих выстрела проходят мимо", _enemy.shot_times.size() == 3 and is_equal_approx(player.health.hp, hp) and _enemy._mag == 96)
	_check("первый выстрел после завершения наведения", not _enemy.shot_times.is_empty() and _enemy.shot_times[0] >= _enemy._fire_reaction.last_delay)
	_enemy._facing = 0.0
	_enemy._perceive(0.1)
	_enemy._facing = PI
	_enemy._perceive(0.01)
	_enemy._tick_weapon(3.0)
	_enemy._try_fire()
	_check("четвёртый выстрел может попасть после короткого выхода из виду", _enemy.shot_times.size() == 4 and player.health.hp < hp)
	await _check_hearing()
	_check_ammo()
	# Та же пауза применяется и к бою фракций, а не только к Player.
	var foe: Marauder = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	foe.archetype = "pmc"
	foe.position = player.position
	add_child(foe)
	foe.set_process(false)
	foe.set_physics_process(false)
	player.remove_from_group("players")
	await _settle()
	_reset()
	_enemy._foe_t = 0.0
	_step()
	_check("вражескую фракцию тоже сначала берёт на прицел", _enemy._foe == foe and _enemy._fire_reaction.remaining >= 0.55 and _enemy.shot_times.is_empty())
	foe.queue_free()
	player.add_to_group("players")


func _process(_delta: float) -> void:
	if _role != "client" or not _players.has(_client):
		return
	if _noticed_ms < 0 and not _rig._detection._contacts.is_empty():
		_noticed_ms = Time.get_ticks_msec()
	var player: Player = _players[_client] as Player
	if _hit_ms < 0 and player.health.hp < player.health.max_hp:
		_hit_ms = Time.get_ticks_msec()


func _network_host() -> void:
	await _settle()
	_reset()
	_enemy.live = true
	_step()
	_check("хост подтвердил гостя и ещё не стреляет", _enemy._target_player == _players[_client] and _enemy.shot_times.is_empty())
	var guest: Player = _players[_client] as Player
	var misses_safe := true
	for frame: int in range(1, 240):
		await get_tree().physics_frame
		_enemy.probe_time = frame * STEP
		_step()
		if _enemy.shot_times.size() <= int(Balance.AI_OPENING_FIRE.misses):
			misses_safe = misses_safe and guest.health.hp == guest.health.max_hp
		if _enemy.shot_times.size() > int(Balance.AI_OPENING_FIRE.misses):
			break
	_check("гость цел после трёх выстрелов хоста", misses_safe)
	_check("четвёртая пуля хоста может попасть гостю", guest.health.hp < guest.health.max_hp and _enemy.shot_times.size() == 4)
	_check("чужое предупреждение не показано хосту", _rig._detection._contacts.is_empty())
	await get_tree().create_timer(0.3).timeout
	_check_guest.rpc_id(_client)
	_check("гость проверил окно реакции", await _wait(func() -> bool: return _finished, 10.0))
	_finish.rpc_id(_client)
	await get_tree().create_timer(0.3).timeout


@rpc("authority", "call_remote", "reliable")
func _check_guest() -> void:
	_check("гость получил предупреждение раньше урона", _noticed_ms >= 0 and _hit_ms > _noticed_ms)
	var window_ms: int = _hit_ms - _noticed_ms
	_check("окно на госте не съедено доставкой по локальной сети", window_ms >= 400)
	_check("гость сам не рассчитывает выстрелы", _enemy.shot_times.is_empty())
	print("AI_REACTION guest_warning_to_hit_ms=%d" % window_ms)
	_peer_checked.rpc_id(1)


func _check_hearing() -> void:
	var actor: Vector3 = _enemy.global_position
	var source := actor + Vector3.LEFT * 8.0
	var door := StaticBody3D.new()
	door.collision_layer = Hitscan.LAYER_DOOR
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.25, 3.0, 2.0)
	shape.shape = box
	door.add_child(shape)
	add_child(door)
	door.global_position = actor + Vector3.LEFT * 4.0 + Vector3.UP
	await _settle()
	var ear := actor + Vector3.UP * 1.4
	var world := get_world_3d()
	_check("закрытая дверь глушит шаги, близкий выстрел всё ещё слышен",
		not NoiseBus.audible(world, ear, source, 10.0, "step") and NoiseBus.audible(world, ear, source, 15.0, "shot"))
	door.collision_layer = Hitscan.LAYER_WORLD
	await _settle()
	_check("стена глушит шаги", not NoiseBus.audible(world, ear, source, 10.0, "step"))
	door.global_position += Vector3.BACK * 4.0
	await _settle()
	_check("открытый проём пропускает те же шаги", NoiseBus.audible(world, ear, source, 10.0, "step"))
	door.queue_free()


func _check_ammo() -> void:
	var bot := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	bot.archetype = "pmc"
	bot.loadout_id = "perimeter_leader"
	bot.position = Vector3(-10, 1, -10)
	add_child(bot)
	bot.set_physics_process(false)
	bot.last_known = bot.global_position + Vector3.FORWARD * 6.0
	var loaded := bot._mag
	var cap := WeaponDb.capacity(bot.equipment.primary)
	for i in range(loaded):
		bot._shot_t = 0.0
		bot._try_fire()
	_check("пустой основной, запас ещё на одну перезарядку", bot._mag == 0 and bot._can_reload("primary") and bot._ammo_refill.is_empty())
	bot._start_reload()
	bot._tick_weapon(bot._reload_t + 0.01)
	_check("полный магазин взят из запаса основного", bot._mag == cap and not bot._can_reload("primary") and bot._can_reload("secondary"))
	for i in range(cap):
		bot._shot_t = 0.0
		bot._try_fire()
	var left := float(bot._ammo_refill.get("primary", 0))
	bot._start_reload()
	_check("после второго магазина основной ждёт 30–60 с, боец взял запасной",
		left >= 30.0 and left <= 60.0 and bot._active == "secondary" and bot._mag > 0)
	bot._tick_weapon(left - 0.1)
	_check("запас основного не вернулся раньше срока", not bot._can_reload("primary"))
	bot._tick_weapon(0.2)
	_check("вернулся только запас, боец продолжает с пистолетом",
		bot._can_reload("primary") and Gear.total_rounds(bot.equipment.primary) == 0 and bot._active == "secondary")
	bot._use("primary")
	bot._start_reload()
	bot._tick_weapon(bot._reload_t + 0.01)
	_check("после ожидания можно снова зарядить основной", bot._mag == cap and not bot._can_reload("primary"))
	var pump := WeaponDb.make_weapon("SG_03_BASE", bot._rng)
	bot.equipment.primary = pump
	bot._equip_reserve("primary", String(pump.mag.ammo))
	bot._use("primary")
	var tube_cap := WeaponDb.capacity(pump)
	for i in range(tube_cap):
		bot._shot_t = 0.0
		bot._try_fire()
	bot._start_reload()
	bot._tick_weapon(bot._reload_t + 0.01)
	_check("ружьё получает одну полную пачку россыпью", bot._mag == tube_cap and not bot._can_reload("primary"))
	bot.queue_free()
