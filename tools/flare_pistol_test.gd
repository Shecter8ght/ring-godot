extends Node3D
## Реальные игровые ресурсы и операции: один патрон, две роли, отмена и повторы пакетов.
var fails: int = 0
var checks: int = 0
var actor: Player

class TestRaid extends Raid:
	func _ready() -> void:
		set_process(false)
		current = self

	func notify(text: String) -> void:
		print("signal notification: ", text)


func _ready() -> void:
	_run.call_deferred()


func check(label: String, ok: bool, detail: String = "") -> void:
	checks += 1
	print("[%s] %s %s" % ["ok" if ok else "FAIL", label, detail])
	if not ok:
		fails += 1


func _entry(aid: String = "flare", n: int = 0) -> Dictionary:
	var e: Dictionary = ItemDb.make("signal_launcher", 1)
	e["mag"] = {"id": "", "ammo": aid, "rounds": n}
	e["rev"] = 0
	return e


func _state(e: Dictionary, aid: String) -> Dictionary:
	return {"id": "signal_launcher", "rev": int(e.get("rev", 0)), "reload_ammo": aid}


func _reset(e: Dictionary, items: Array = []) -> void:
	actor.cancel_weapon_action()
	actor.weapon_id = ""
	actor.weapon_slot = ""
	actor._ws.clear()
	actor._pm_entries.clear()
	actor._ws_dirty = false
	actor.loadout_mode = true
	actor.inventory.equipment = {"secondary": e.duplicate(true), "backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	actor.inventory.items = items.duplicate(true)
	actor.inventory.buffer = []
	actor.stress = 0.0
	actor._signal_host_fire_ms = -10000
	actor.signal_reload_ammo = "flare"
	actor._switch("secondary", false)
	actor._update_hand()


func _run() -> void:
	Profile.use_file("user://flare_pistol_test.json", true)
	RaidEvents.enabled = false
	check("каталог: оружие во вторичном слоте", WeaponDb.is_weapon("signal_launcher") and String(WeaponDb.weapon("signal_launcher").slot) == "secondary")
	check("красный и зелёный подходят, обычные пули отклоняются", WeaponDb.ammo_fits("signal_launcher", "flare") and WeaponDb.ammo_fits("signal_launcher", "supply_signal") and not WeaponDb.ammo_fits("signal_launcher", "ammo_918_pst"))
	check("один патрон, без съёмного магазина", WeaponDb.capacity(_entry()) == 1 and WeaponDb.default_mag("signal_launcher") == "")
	var inv := Inventory.new()
	add_child(inv)
	inv.equipment = {"secondary": _entry(), "backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	inv.items = [ItemDb.make("flare", 2), ItemDb.make("supply_signal", 2)]
	var result: Array = inv.reload_slot("secondary", _state(inv.equipment.secondary, "flare"))
	check("заряжание красного расходует ровно один", String(result[0]) == "signal" and inv.count("flare") == 1 and inv.count("supply_signal") == 2 and Gear.total_rounds(inv.equipment.secondary) == 1)
	result = inv.reload_slot("secondary", _state(inv.equipment.secondary, "supply_signal"))
	check("смена типа возвращает живой красный", String(result[0]) == "signal" and inv.count("flare") == 2 and inv.count("supply_signal") == 1 and Gear.mag_top(inv.equipment.secondary.mag) == "supply_signal")
	var snapshot: String = JSON.stringify([inv.equipment, inv.items])
	result = inv.reload_slot("secondary", _state(inv.equipment.secondary, "supply_signal"))
	check("повтор заряжания того же типа ничего не меняет", String(result[0]) == "" and JSON.stringify([inv.equipment, inv.items]) == snapshot)
	result = inv.reload_slot("secondary", {"id": "signal_launcher", "rev": -1, "reload_ammo": "flare"})
	check("старая ревизия не расходует патрон", String(result[0]) == "" and JSON.stringify([inv.equipment, inv.items]) == snapshot)
	inv.apply_weapon_state("secondary", {"id": "signal_launcher", "rev": int(inv.equipment.secondary.rev), "rounds": 0, "dur": 1})
	check("клиентский кэш не затирает патрон хоста", JSON.stringify([inv.equipment, inv.items]) == snapshot)
	inv.free()
	_model_cases()
	actor = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(actor)
	await get_tree().process_frame
	actor.process_mode = Node.PROCESS_MODE_DISABLED
	actor.health.invulnerable = true
	_reset(_entry(), [ItemDb.make("flare", 2), ItemDb.make("supply_signal", 2)])
	snapshot = JSON.stringify([actor.inventory.equipment, actor.inventory.items])
	actor._start_reload(actor.spec())
	check("перезарядка запускает клип без раннего расхода", actor.reload_timer > 5.0 and not actor._pm_action.is_empty() and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	actor.cancel_weapon_action()
	check("отмена сохраняет снаряжение", actor.reload_timer == 0.0 and actor._pm_action.is_empty() and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	actor._start_reload(actor.spec())
	actor._finish_reload(actor.spec())
	check("завершение заряжает один красный", actor.ammo == 1 and actor.inventory.count("flare") == 1)
	actor._fire(actor.spec())
	await get_tree().process_frame
	check("выстрел расходует заряженный патрон", actor.ammo == 0 and Gear.total_rounds(actor.inventory.equipment.secondary) == 0 and actor.inventory.count("flare") == 1)
	check("выстрел создал красную осветительную ракету", get_tree().get_nodes_in_group("sky_flares").size() == 1 and get_tree().get_nodes_in_group("supply_signals").is_empty())
	var rockets: int = get_tree().get_nodes_in_group("flares").size()
	actor._fire(actor.spec())
	check("пустая ракетница не создаёт второй выстрел", get_tree().get_nodes_in_group("flares").size() == rockets)
	_reset(_entry("supply_signal", 1), [ItemDb.make("flare", 2), ItemDb.make("supply_signal", 2)])
	actor._fire(actor.spec())
	check("зелёный вне рейда не расходуется", actor.ammo == 1 and Gear.total_rounds(actor.inventory.equipment.secondary) == 1)
	await _supply_cases()
	await _clip_cases()
	Raid.current = null
	print("flare_pistol_test: проверок %d, провалено %d" % [checks, fails])
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	await get_tree().create_timer(0.3).timeout
	get_tree().quit(1 if fails else 0)


func _model_cases() -> void:
	var model: Node3D = WeaponModels.build("signal_launcher")
	add_child(model)
	var rig: WeaponRig = WeaponRig.find_on(model)
	check("загружена именно GLB-модель Codex с ригом", bool(model.get_meta("asset_loaded", false)) and rig != null and rig.has_parts())
	var bounds: AABB = ItemModels.bounds(model)
	check("реальные габариты около 20 × 13 × 3 см", bounds.size.z > .19 and bounds.size.z < .21 and bounds.size.y > .12 and bounds.size.y < .14 and bounds.size.x > .03 and bounds.size.x < .04, str(bounds))
	if rig:
		for part: String in ["Frame", "Barrel", "Hammer", "Trigger", "Latch", "FiringPin"]:
			check("отдельная подвижная деталь " + part, rig.part(part) != null)
		var closed: Vector3 = rig.marker("Muzzle").global_position
		rig.pose_action("reload", 40.0 / 155.0, true)
		check("ствол отклоняется на 48° вокруг шарнира", absf(absf(rad_to_deg(rig.part("Barrel").rotation.x)) - 48.0) < .1 and rig.marker("Muzzle").global_position.distance_to(closed) > .03, "%s; muzzle travel %.4f m" % [rig.part("Barrel").rotation_degrees, rig.marker("Muzzle").global_position.distance_to(closed)])
		rig.pose_action("reload", 41.0 / 155.0, true)
		check("казённый срез направлен вниз после разворота", rig.part("Barrel").global_basis.z.normalized().dot(Vector3.UP) > .97)
		var raised: float = rig._visual.position.y
		rig.pose_action("reload", 47.0 / 155.0, true)
		check("первое встряхивание опускает пистолет", rig._visual.position.y < raised - .02)
		rig.pose_action("reload", 49.0 / 155.0, true)
		check("между встряхиваниями кисть возвращается", rig._visual.position.y > raised - .005)
		rig.pose_action("reload", 55.0 / 155.0, true)
		check("второе встряхивание — отдельный взмах", rig._visual.position.y < raised - .025)
		rig.pose_action("reload", 109.0 / 155.0, true)
		check("патрон вставляется в раскрытый ствол", absf(rad_to_deg(rig.part("Barrel").rotation.x) - 48.0) < .1)
		rig.pose_action("reload", 127.0 / 155.0, true)
		check("после рывка правой кисти ствол закрыт", absf(rig.part("Barrel").rotation.x) < .01)
		rig.cancel_action()
		check("отмена закрывает ствол", rig.marker("Muzzle").global_position.is_equal_approx(closed))
		rig.set_ammo_state(1)
		rig.pose_action("shot", 6.0 / 23.0)
		check("спуск имеет реальный ход", absf(rad_to_deg(rig.part("Trigger").rotation.x)) > 8.0)
		rig.cancel_action()
	model.free()


func _supply_cases() -> void:
	var raid := TestRaid.new()
	add_child(raid)
	var floor_body := StaticBody3D.new()
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(20, .2, 20)
	collision.shape = shape
	floor_body.add_child(collision)
	add_child(floor_body)
	floor_body.position.y = -.1
	actor.global_position = Vector3(0, .1, 0)
	var roof: StaticBody3D = floor_body.duplicate() as StaticBody3D
	add_child(roof)
	roof.position.y = 3.0
	await get_tree().physics_frame
	actor._fire(actor.spec())
	check("крыша блокирует airdrop, сохраняя зелёный патрон", raid.supply_state.is_empty() and actor.ammo == 1)
	roof.queue_free()
	await get_tree().physics_frame
	await get_tree().physics_frame
	actor.fire_timer = 0.0
	actor._fire(actor.spec())
	await get_tree().process_frame
	check("зелёный расходует заряженный патрон и вызывает груз", not raid.supply_state.is_empty() and actor.ammo == 0 and actor.inventory.count("supply_signal") == 2)
	check("зелёная ракета не считается осветительной", get_tree().get_nodes_in_group("supply_signals").size() == 1 and get_tree().get_nodes_in_group("sky_flares").size() == 1)
	var duplicate: Dictionary = actor._host_pm_commit({"kind": "signal_shot", "seq": actor._pm_host_seq, "slot": "secondary", "id": "signal_launcher", "state": actor._ws_state("secondary")})
	check("повтор пакета не создаёт второй сигнал", String(duplicate.error) != "" and get_tree().get_nodes_in_group("supply_signals").size() == 1)
	_reset(_entry("supply_signal", 1))
	actor._fire(actor.spec())
	check("повтор вызова в рейде оставляет второй патрон", actor.ammo == 1 and Gear.total_rounds(actor.inventory.equipment.secondary) == 1)
	Raid.current = null
	raid.free()
	floor_body.free()


func _clip_cases() -> void:
	var vm: ViewmodelClips = ViewmodelClips.create("signal_launcher", {})
	add_child(vm)
	await get_tree().process_frame
	check("FPS-руки из рига ВЕРАС-54", vm.find_child("FPS_Arms_Right", true, false) != null and vm._arm_skel != null and vm._arm_skel.find_bone("hand.R") >= 0)
	check("левая рука скрыта в стойке", vm._signal_left_arm != null and not vm._signal_left_arm.visible)
	check("в GLB есть 12 клипов всех стадий", vm._anim.get_animation_list().size() >= 12)
	vm._play(vm._clip_name("idle"), 0.0)
	vm._anim.advance(0.0)
	await get_tree().process_frame
	var volumes: Array[AABB] = vm.clearance_boxes()
	var gun_bounds: AABB = volumes[0] if not volumes.is_empty() else AABB()
	for box: AABB in volumes:
		gun_bounds = gun_bounds.merge(box)
	check("габарит подвижной сетки учитывает все шесть деталей", volumes.size() == 6 and gun_bounds.size.length() < .3 and gun_bounds.size.length() > .15, str(gun_bounds))
	var muzzle: Node3D = vm.find_child("Muzzle", true, false) as Node3D
	check("габарит ствола включает реальное дуло", muzzle != null and gun_bounds.grow(.003).has_point(vm.to_local(muzzle.global_position)))
	for clip: String in ["break_open", "insert_cartridge", "close_breech", "cock_hammer", "trigger_pull", "fire", "reload_empty", "reload_live"]:
		check("импортирован клип " + clip, vm._anim.has_animation(clip))
	_reset(_entry("flare", 0), [ItemDb.make("supply_signal", 1)])
	actor.signal_reload_ammo = "supply_signal"
	actor._start_reload(actor.spec())
	vm.update(actor, 0.0)
	check("левая рука подключается только к перезарядке", vm._signal_left_arm.visible)
	vm._anim.seek(47.0 / 30.0, true)
	vm.update(actor, 0.0)
	check("левая не держит ствол во время встряхивания", not vm._signal_left_arm.visible)
	vm._anim.seek(122.0 / 30.0, true)
	vm.update(actor, 0.0)
	check("ствол закрывается без левой руки", not vm._signal_left_arm.visible)
	vm._anim.seek(90.0 / 30.0, true)
	vm.update(actor, 0.0)
	check("в левой руке показывается выбранный зелёный", vm._signal_props.size() == 4 and (vm._signal_props.LoadRoundGreen as Node3D).visible and not (vm._signal_props.LoadRoundRed as Node3D).visible)
	check("без гильзы в пустой ракетнице старая гильза скрыта", not (vm._signal_props.OldRoundRed as Node3D).visible)
	vm._anim.seek(122.0 / 30.0, true)
	vm.update(actor, 0.0)
	check("новый патрон остаётся внутри при закрытии", (vm._signal_props.LoadRoundGreen as Node3D).visible)
	actor.cancel_weapon_action()
	vm.update(actor, .1)
	check("после отмены остаётся одна правая рука", not vm._signal_left_arm.visible)
	check("отмена убирает незаряженный патрон из рук", not (vm._signal_props.LoadRoundGreen as Node3D).visible)
	_reset(_entry("flare", 1))
	vm.update(actor, 0.0)
	check("заряженный красный виден в патроннике", (vm._signal_props.LoadRoundRed as Node3D).visible and not (vm._signal_props.LoadRoundGreen as Node3D).visible)
	var spent: Dictionary = _entry("flare", 0)
	spent["signal_spent"] = true
	_reset(spent)
	vm.update(actor, 0.0)
	check("после выстрела остаётся гильза до перезарядки", (vm._signal_props.OldRoundRed as Node3D).visible and not (vm._signal_props.LoadRoundRed as Node3D).visible)
	vm.weapon_action("shot")
	check("выстрел запускает клип движения курка и пальца", String(vm._anim.current_animation) == "fire")
	vm.free()
