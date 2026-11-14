extends Node
## Перезарядка и проверка магазина со снаряжением (ВЕРАС-54): одно R — обычная смена, старый магазин в
## рюкзаке; два быстрых R — быстрая: короче в Balance.RELOAD_FAST.time_k раз, старый магазин лежит на
## земле — сам магазин (LooseLoot), а не мешок, и подбирается обратно с теми же патронами; второе R позже окна — обычная; держать R — проверка: магазин остаётся в
## руке, пока держат (Player.mag_inspect), перезарядка не начинается; отпустили — убран.
## Старый магазин быстрой перезарядки вылетает настоящим телом (TossedItem, Balance.MAG_TOSS): появляется на кадре
## сброса клипа рук там, где виден в руках, летит по физике и остаётся лежать там, где успокоился; звук — при ударе;
## запасной бросок вправо (ствол без кадра сброса), точка вылета за стеной, тело улетело за карту.
## tools/godot.cmd --headless res://tools/reload_fast_test.tscn

const ID := "wpn_ar_01"

var _fails: int = 0
var _raid: Raid
var _me: Player


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_raid = Raid.current
	_me = _raid.local_player()
	_me.health.invulnerable = true
	await get_tree().create_timer(0.3).timeout
	# без разгрузки магазин достаётся из рюкзака — дольше (Balance.RIG.backpack_reload_k); из подсумков —
	# по паспорту ствола (раздел «разгрузка» ниже)
	var base_reload: float = float(WeaponDb.weapon(ID).stats.reload)
	var spec_reload: float = base_reload * float(Balance.RIG.backpack_reload_k)
	var k: float = float(Balance.RELOAD_FAST.time_k)
	_check("быстрая перезарядка на 25–30 %% быстрее обычной (%.0f %%)" % ((1.0 - k) * 100.0), k >= 0.70 and k <= 0.75)

	# --- одно R: обычная, старый магазин — в рюкзак
	_arm(12, [30])
	await _tap()
	_check("одно R — обычная перезарядка", _me.reload_timer > 0.0 and not _me._reload_fast and absf(_me.reload_timer - spec_reload) < 0.25, "%.2f" % _me.reload_timer)
	_check("магазин из рюкзака — липучки нет", _me._velcro_at < 0.0, "%.2f" % _me._velcro_at)
	await _until_done()
	_check("обычная: в оружии полный магазин", _me.ammo == 30, str(_me.ammo))
	_check("обычная: старый магазин (12) в рюкзаке", _mag_rounds().has(12), str(_mag_rounds()))
	_check("обычная: на земле ничего", _dropped().is_empty(), str(_dropped()))

	# --- два быстрых R: быстрая, старый магазин — на землю
	_arm(12, [30])
	await _tap()
	await _tap()
	_check("два быстрых R — быстрая перезарядка", _me._reload_fast and _me.reload_timer > 0.0)
	var left: float = _me.reload_timer + _me._reload_age
	_check("быстрая: короче в %.2f раза" % k, absf(left - spec_reload * k) < 0.2, "%.2f с при обычной %.2f" % [left, spec_reload])
	_check("быстрая: магазин отпустит клип рук (кадр сброса), не запасной бросок", _me._toss_at < 0.0, "%.2f" % _me._toss_at)
	# магазин вылетает настоящим телом посреди перезарядки — с кадра сброса клипа, а не в её конце
	var flight: Dictionary = await _watch_flight()
	_check("быстрая: тело магазина появилось до конца перезарядки (осталось %.2f с из %.2f)" % [float(flight.get("left", 0.0)), left],
		not flight.is_empty() and float(flight.left) > 0.2 and float(flight.left) < left - 0.3, str(flight.get("left", -1.0)))
	if not flight.is_empty():
		var from_eye: Vector3 = (flight.start as Vector3) - (flight.eye as Vector3)
		_check("быстрая: вылетает от оружия перед стрелком (%.2f м от глаз), слой debris" % from_eye.length(),
			from_eye.length() > 0.2 and from_eye.length() < 0.9 and int(flight.layer) == Hitscan.LAYER_DEBRIS, str(from_eye))
		_check("быстрая: скорость вылета — из клипа (%.2f м/с)" % (flight.vel as Vector3).length(),
			(flight.vel as Vector3).length() > 0.3 and (flight.vel as Vector3).length() <= float(Balance.MAG_TOSS.max_speed) + 0.01, str(flight.vel))
		_check("быстрая: в полёте магазина нет ни в рюкзаке, ни на земле", bool(flight.clean))
		_check("быстрая: летело и падало (%.2f с, ниже точки вылета на %.2f м), ударилось со звуком %d раз" % [float(flight.time), float(flight.fell), int(flight.hits)],
			float(flight.time) > 0.3 and float(flight.fell) > 0.5 and int(flight.hits) >= 1)
	await _until_done()
	_check("быстрая: в оружии полный магазин", _me.ammo == 30, str(_me.ammo))
	_check("быстрая: старого магазина в рюкзаке нет", not _mag_rounds().has(12), str(_mag_rounds()))
	_check("быстрая: старый магазин лежит на земле", _dropped().has(12), str(_dropped()))
	var lying: LooseLoot = _lying()
	_check("быстрая: на земле сам магазин, а не мешок", lying != null and lying.dropped and lying.look == LootContainer.Look.NONE)
	if lying and not flight.is_empty():
		var holder: Node3D = lying._vis.get_node_or_null("Laid") as Node3D
		var off: float = holder.global_position.distance_to(flight.last) if holder else 99.0
		_check("быстрая: лежит там, куда прилетел (%.0f мм от места, где тело успокоилось), в той же позе" % (off * 1000.0),
			lying.posed and off < 0.03 and holder.global_basis.orthonormalized().is_equal_approx((flight.basis as Basis)), "%.3f" % off)
		var flat: Vector3 = lying.global_position - _me.global_position
		_check("быстрая: в %.2f м от стрелка" % Vector2(flat.x, flat.z).length(), Vector2(flat.x, flat.z).length() < 6.0, str(flat))
		var box: AABB = ItemModels.bounds(lying._vis)
		_check("быстрая: лежит на поверхности, не в ней и не над ней (низ модели %.0f мм от точки под центром; на склоне край ниже)" % (box.position.y * 1000.0),
			box.position.y > -0.06 and box.position.y < 0.06 and not TossedItem.floor_under(lying.get_world_3d(), lying.global_position + Vector3.UP * 0.05, 0.3).is_empty(), str(box))
		_check("быстрая: подсказка — подобрать магазин", lying.can_use() and lying.prompt().begins_with("подобрать"), lying.prompt())
		lying.request_use()
		await get_tree().create_timer(0.2).timeout
		_check("подобрал: магазин с теми же 12 патронами снова в рюкзаке, на земле пусто", _mag_rounds().has(12) and _dropped().is_empty(), str(_mag_rounds()))

	# --- второе R позже окна — перезарядка остаётся обычной
	_arm(12, [30])
	await _tap()
	await get_tree().create_timer(float(Balance.RELOAD_FAST.tap_sec) + 0.25).timeout
	await _tap()
	_check("второе R с опозданием — обычная", _me.reload_timer > 0.0 and not _me._reload_fast)
	await _until_done()
	_check("опоздал: магазин в рюкзаке, не на земле", _mag_rounds().has(12))

	# --- нет запасного магазина: двойное R не выбрасывает единственный
	_arm(12, [])
	await _tap()
	await _tap()
	_check("без запасного магазина быстрой нет", not _me._reload_fast)
	await _until_done()

	# --- держать R: проверка, магазин в руке, пока держат
	_arm(17, [30])
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 0.3).timeout
	_check("держать R — проверка, магазин остаётся в руке", _me.mag_inspect and _me.reload_timer <= 0.0 and _me.ammo_check_text != "")
	await get_tree().create_timer(2.0).timeout
	_check("держат дальше — всё ещё в руке, ответ на экране", _me.mag_inspect and _me.ammo_check_t > 0.0)
	Input.action_release("reload")
	await get_tree().create_timer(0.2).timeout
	_check("отпустили — магазин убран, перезарядки нет", not _me.mag_inspect and _me.reload_timer <= 0.0 and _me.ammo == 17)

	# --- магазин вынут: R (по нажатию) вставляет новый; двойное R и удержание — ничего особенного
	var insert_sec: float = float(WeaponDb.weapon(ID).stats.reload_empty) * float(Balance.RELOAD_INSERT.time_k) * float(Balance.RIG.backpack_reload_k)
	_arm(-1, [30])
	await get_tree().create_timer(0.4).timeout
	_check("магазин вынут: в руках оружие без магазина", _me.mag_out() and _me.ammo == 0, _me.weapon_mag)
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	_check("без магазина: R сразу вставляет новый (не ждёт отпускания)", _me.reload_timer > 0.0 and _me._reload_insert, "%.2f" % _me.reload_timer)
	_check("без магазина: вставка короче полной перезарядки", absf(_me.reload_timer + _me._reload_age - insert_sec) < 0.25, "%.2f при %.2f" % [_me.reload_timer, insert_sec])
	Input.action_release("reload")
	await get_tree().physics_frame
	await _tap()
	_check("без магазина: двойное R — быстрой нет", not _me._reload_fast and _me.reload_timer > 0.0)
	await _until_done()
	_check("без магазина: вставлен полный магазин", _me.ammo == 30 and not _me.mag_out() and _dropped().is_empty(), "%d %s" % [_me.ammo, _me.weapon_mag])
	_arm(-1, [])
	await get_tree().create_timer(0.4).timeout
	_me.ammo_check_text = ""
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 0.4).timeout
	_check("без магазина: держать R — ни проверки, ни перезарядки", not _me.mag_inspect and _me.ammo_check_text == "" and _me.reload_timer <= 0.0)
	Input.action_release("reload")
	await get_tree().physics_frame
	# только пустой магазин в рюкзаке — вставляется и он (дальше можно досыпать россыпью)
	_arm(-1, [0])
	await get_tree().create_timer(0.4).timeout
	await _tap()
	await _until_done()
	_check("без магазина: вставляется и пустой магазин", not _me.mag_out() and _me.ammo == 0 and _mag_rounds().is_empty(), "%s %s" % [_me.weapon_mag, str(_mag_rounds())])
	# --- подсумки на броне: магазин из подсумка — без надбавки, старый — в сброс пустых
	_arm(12, [])
	_wear_rig("armor_mid", 4, [30, 30])
	await _tap()
	_check("разгрузка: перезарядка из подсумка — по паспорту ствола", _me.reload_timer > 0.0 and absf(_me.reload_timer - base_reload) < 0.25, "%.2f при %.2f" % [_me.reload_timer, base_reload])
	# липучка — когда старый магазин скрылся из вида (доля перезарядки velcro_fraction), не при нажатии
	var whole: float = _me.reload_timer + _me._reload_age
	var cue: float = _me._velcro_at
	var played0: int = _me.velcro_count
	_check("из подсумка: липучка запланирована на момент «магазин скрылся» (%.2f с из %.2f, доля %.2f)" % [cue, whole, _me.velcro_fraction()],
		cue > 0.2 and absf(cue - whole * _me.velcro_fraction()) < 0.1 and played0 == 0)
	await get_tree().create_timer(maxf(0.0, cue - _me._reload_age - 0.15)).timeout
	_check("до этого момента — тишина", _me.velcro_count == played0)
	await get_tree().create_timer(0.3).timeout
	_check("в этот момент — липучка, один раз", _me.velcro_count == played0 + 1, str(_me.velcro_count - played0))
	await _until_done()
	_check("за перезарядку липучка прозвучала один раз", _me.velcro_count == played0 + 1)
	_check("разгрузка: в оружии полный магазин, в подсумках остался один", _me.ammo == 30 and _rounds_in("rig") == [30], "%d, %s" % [_me.ammo, str(_rounds_in("rig"))])
	_check("разгрузка: старый магазин (12) — в сумке сброса, не в рюкзаке", _rounds_in("dump") == [12] and _mag_rounds().is_empty(), "%s / %s" % [str(_rounds_in("dump")), str(_mag_rounds())])
	_check("разгрузка: счётчик запасных магазинов видит подсумки", _me.spare_mags() == 1, str(_me.spare_mags()))
	# быстрая (два R): старый магазин — из сумки сброса на землю
	_me._ws.clear()
	var eq2: Dictionary = _me.inventory.equipment.duplicate(true)
	(eq2.primary.mag as Dictionary)["rounds"] = 7
	_me.inventory.equipment = eq2
	_me.weapon_slot = ""
	_me._switch("primary", false)
	await get_tree().create_timer(0.3).timeout
	var played1: int = _me.velcro_count
	await _tap()
	await _tap()
	_check("быстрая из подсумка: липучка сразу (новый магазин берут первым)", _me._reload_fast and _me.velcro_count == played1 + 1 and _me._velcro_at < 0.0, str(_me.velcro_count - played1))
	await _until_done()
	_check("быстрая: липучка один раз за перезарядку", _me.velcro_count == played1 + 1)
	await _until_landed()
	_check("разгрузка, быстрая: старый магазин (7) лежит на земле, в сумке сброса — только прежний", _dropped().has(7) and _rounds_in("dump") == [12], "%s / %s" % [str(_dropped()), str(_rounds_in("dump"))])
	# в подсумки — только магазины; сумка сброса полна — старый магазин уходит в рюкзак
	_check("в подсумки кладутся только магазины", _me.inventory.add_entry_in("rig", ItemDb.make("bandage", 1)) == 0
		and _me.inventory.add_entry_in("rig", WeaponDb.make_mag(WeaponDb.default_mag(ID), "ammo_545_std", 30)) == 1)
	_arm(5, [])
	_wear_rig("belt_pouches", 2, [30])
	_me.inventory.add_entry_in("dump", WeaponDb.make_mag(WeaponDb.default_mag(ID), "", 0))
	_me.inventory.add_entry_in("dump", WeaponDb.make_mag(WeaponDb.default_mag(ID), "", 0))
	var dump_before: int = _me.inventory.list_of("dump").size()
	await _tap()
	await _until_done()
	_check("сброс пустых полон — старый магазин (5) в рюкзаке", _me.inventory.list_of("dump").size() == dump_before and _mag_rounds().has(5), "%s / %s" % [str(_rounds_in("dump")), str(_mag_rounds())])
	# вес и цена пояса — с подсумками и магазинами внутри; снял пояс — всё едет с ним
	var rig_entry: Dictionary = _me.inventory.equipment.armor
	_check("вес пояса — с подсумками и магазинами внутри", ItemDb.entry_weight(rig_entry) > ItemDb.weight("belt_pouches") + 2.0 * ItemDb.weight("pouch_rifle") + 0.1, "%.2f" % ItemDb.entry_weight(rig_entry))
	_check("мест на поясе больше нет, третий подсумок не вешается", not ItemDb.attach_pouch(rig_entry, "pouch_rifle") and is_equal_approx(ItemDb.places_free(rig_entry), 0.0), "свободно %.1f" % ItemDb.places_free(rig_entry))
	await _toss_cases()
	print("reload_fast_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Следить за телом вылетевшего магазина (TossedItem) от появления до места, где оно успокоилось.
## {start, eye, vel, layer, left — сколько оставалось перезарядки, clean, time, fell, hits, last, basis}; пусто — тела не было.
func _watch_flight() -> Dictionary:
	var body: TossedItem = null
	var guard: float = 0.0
	while body == null and guard < 8.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
		body = get_tree().get_first_node_in_group("tossed_items") as TossedItem
	if body == null:
		return {}
	var out: Dictionary = {"start": body.global_position, "eye": _me.eye_position(), "vel": body._velocity, "layer": body.collision_layer,
		"left": _me.reload_timer, "clean": not _mag_rounds().has(int(body.entry.rounds)) and _dropped().is_empty(), "time": 0.0}
	while is_instance_valid(body) and not body.is_queued_for_deletion():
		out["last"] = body.global_position
		out["basis"] = body.global_basis.orthonormalized()
		out["hits"] = body.hit_count
		out["time"] = float(out.time) + get_physics_process_delta_time()
		if OS.has_environment("TOSS_TRACE") and Engine.get_physics_frames() % 6 == 0:
			var under: Dictionary = TossedItem.floor_under(body.get_world_3d(), body.global_position, 50.0)
			print("trace t=%.2f pos=%s v=%s hits=%d floor=%s %s" % [float(out.time), str(body.global_position), str(body.linear_velocity), body.hit_count, str(under.get("position", "-")), str(under.get("collider", "-"))])
		await get_tree().physics_frame
	out["fell"] = (out.start as Vector3).y - (out.last as Vector3).y
	await get_tree().physics_frame
	return out


## Дождаться, пока все вылетевшие магазины лягут.
func _until_landed() -> void:
	var guard: float = 0.0
	while not get_tree().get_nodes_in_group("tossed_items").is_empty() and guard < 10.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
	await get_tree().physics_frame
	await get_tree().physics_frame


## Запасной бросок, проверка точки вылета хостом, тело улетело за карту.
func _toss_cases() -> void:
	var cfg: Dictionary = Balance.MAG_TOSS
	# --- ствол без кадра сброса в клипе: бросок вправо числами Balance на доле перезарядки
	await _arm(9, [30])
	await _tap()
	await _tap()
	_me._toss_at = (_me.reload_timer + _me._reload_age) * float(cfg.fallback_at)
	var view: Transform3D = get_viewport().get_camera_3d().global_transform
	var flight: Dictionary = await _watch_flight()
	_check("запасной бросок: тело появилось посреди перезарядки", not flight.is_empty() and float(flight.get("left", 0.0)) > 0.1)
	if not flight.is_empty():
		var side: float = ((flight.start as Vector3) - view.origin).dot(view.basis.x)
		_check("запасной бросок: справа от стрелка (%.2f м) и летит вправо (%.2f м/с)" % [side, (flight.vel as Vector3).dot(view.basis.x)],
			side > 0.05 and (flight.vel as Vector3).dot(view.basis.x) > 1.0)
	await _until_done()
	await _until_landed()
	_check("запасной бросок: магазин (9) лежит на земле как упал", _dropped().has(9) and _lying() != null and _lying().posed, str(_dropped()))
	# --- хост не верит точке вылета: за стеной — отодвигает к стрелку, слишком далеко — берёт у глаз, скорость режет
	var eye: Vector3 = _me.eye_position()
	var fwd: Vector3 = -get_viewport().get_camera_3d().global_basis.z
	var wall := StaticBody3D.new()
	wall.collision_layer = Hitscan.LAYER_WORLD
	var shape := CollisionShape3D.new()
	var slab := BoxShape3D.new()
	slab.size = Vector3(3.0, 3.0, 0.1)
	shape.shape = slab
	wall.add_child(shape)
	get_tree().current_scene.add_child(wall)
	wall.global_transform = Transform3D(Basis.looking_at(fwd, Vector3.UP), eye + fwd * 0.4)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var behind: Dictionary = TossedItem.checked_launch(_me, {"pos": eye + fwd * 0.7, "vel": fwd * 50.0, "spin": Vector3.ONE * 900.0, "rot": Quaternion.IDENTITY})
	var along: float = ((behind.pos as Vector3) - eye).dot(fwd)
	_check("точка вылета за стеной — отодвинута к стрелку (%.2f м при стене в 0,35 м)" % along, along > 0.05 and along < 0.35, str(behind.pos))
	_check("скорость и вращение обрезаны (%.1f м/с, %.1f рад/с)" % [(behind.vel as Vector3).length(), (behind.spin as Vector3).length()],
		(behind.vel as Vector3).length() <= float(cfg.max_speed) + 0.01 and (behind.spin as Vector3).length() <= float(cfg.max_spin) + 0.01)
	wall.queue_free()
	await get_tree().physics_frame
	var far: Dictionary = TossedItem.checked_launch(_me, {"pos": eye + Vector3(40.0, 0.0, 0.0)})
	_check("точка вылета далеко от стрелка — не принята", (far.pos as Vector3).distance_to(eye) < float(cfg.reach))
	# --- тело улетело за карту (провалилось): магазин кладётся на пол под точкой вылета, не пропадает
	await _arm(4, [30])
	_me.inventory.add_entry(WeaponDb.make_mag(WeaponDb.default_mag(ID), WeaponDb.default_ammo("545x39"), 21))
	var idx: int = -1
	for i: int in range(_me.inventory.items.size()):
		if int((_me.inventory.items[i] as Dictionary).get("rounds", -1)) == 21:
			idx = i
	var from: Vector3 = _me.eye_position() + Vector3.DOWN * 0.3
	_raid.request_toss_entry("backpack", idx, {"pos": from, "vel": Vector3.ZERO, "spin": Vector3.ZERO, "rot": Quaternion.IDENTITY})
	await get_tree().physics_frame
	var body: TossedItem = get_tree().get_first_node_in_group("tossed_items") as TossedItem
	_check("просьба хосту: магазин (21) ушёл из рюкзака в тело", body != null and not _mag_rounds().has(21))
	if body:
		body.global_position = from + Vector3.DOWN * (float(cfg.max_fall) + 5.0)
		body._prev = body.global_position
		await _until_landed()
		var lost: LooseLoot = _lying()
		var under: Dictionary = TossedItem.floor_under(_me.get_world_3d(), from, float(cfg.fallback_drop))
		_check("улетел за карту: магазин (21) лежит на полу под точкой вылета", lost != null and _dropped().has(21) and not under.is_empty()
			and lost.global_position.distance_to(under.position) < 0.05, str(lost.global_position if lost else Vector3.ZERO))


## Игрок со снаряжением: ВЕРАС с магазином на rounds патронов (−1 — магазин вынут), в рюкзаке — магазины spare.
func _arm(rounds: int, spare: Array) -> void:
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c and (c.display_name == Raid.DROP_NAME or (c is LooseLoot and (c as LooseLoot).dropped)):
			c.queue_free()
	for n: Node in get_tree().get_nodes_in_group("tossed_items"):
		n.queue_free()
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	var ammo_id: String = WeaponDb.default_ammo("545x39")
	entry["mag"] = {"id": WeaponDb.default_mag(ID), "ammo": ammo_id, "rounds": rounds}
	if rounds < 0:
		# магазин вынут
		entry["mag"] = {"id": "", "ammo": ammo_id, "rounds": 0}
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	for n: int in spare:
		_me.inventory.add_entry(WeaponDb.make_mag(WeaponDb.default_mag(ID), ammo_id, n))
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	await get_tree().create_timer(0.3).timeout


## Короткое нажатие R (перезарядка начинается по отпусканию).
func _tap() -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame


func _until_done() -> void:
	var guard := 0.0
	while _me.reload_timer > 0.0 and guard < 8.0:
		await get_tree().physics_frame
		guard += get_physics_process_delta_time()
	await get_tree().create_timer(0.2).timeout


## Надеть броню id с pouches автоматными подсумками и магазинами (патронов в каждом — по списку) в них.
func _wear_rig(id: String, pouches: int, mags: Array) -> void:
	var eq: Dictionary = _me.inventory.equipment.duplicate(true)
	var armor := ItemDb.make(id, 1)
	for i in range(pouches):
		ItemDb.attach_pouch(armor, "pouch_rifle")
	eq["armor"] = armor
	_me.inventory.equipment = eq
	for n: int in mags:
		_me.inventory.add_entry_in("rig", WeaponDb.make_mag(WeaponDb.default_mag(ID), WeaponDb.default_ammo("545x39"), n))


## Остатки в магазинах сетки разгрузки role ("rig" — подсумки, "dump" — сумка сброса).
func _rounds_in(role: String) -> Array:
	var out: Array = []
	for it: Dictionary in _me.inventory.list_of(role):
		out.append(int(it.rounds))
	return out


## Остатки во всех магазинах рюкзака.
func _mag_rounds() -> Array:
	var out: Array = []
	for it: Dictionary in _me.inventory.items:
		if it.has("rounds"):
			out.append(int(it.rounds))
	return out


## Сброшенный магазин, лежащий на земле сам по себе.
func _lying() -> LooseLoot:
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LooseLoot
		if c != null and c.dropped and not c.is_queued_for_deletion() and not c.items.is_empty():
			return c
	return null


## Остатки в магазинах, лежащих на земле (сами по себе или в мешках «Выброшено»).
func _dropped() -> Array:
	var out: Array = []
	for n: Node in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null or c.is_queued_for_deletion() or not (c.display_name == Raid.DROP_NAME or (c is LooseLoot and (c as LooseLoot).dropped)):
			continue
		for it: Dictionary in c.items:
			if it.has("rounds"):
				out.append(int(it.rounds))
	return out


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
