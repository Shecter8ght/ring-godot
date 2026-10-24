extends Node3D
## МЕТКА-4 через реальные операции сборки, сохранения, лута и импортированный риг.
var _fails: int = 0
var _checks: int = 0
var _pair: Dictionary = {}


func _ready() -> void:
	if name != "Metka4Runner":
		var runner: Node3D = Node3D.new()
		runner.name = "Metka4Runner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	Profile.use_file("user://metka4_test.json", true)
	RaidEvents.enabled = false
	await get_tree().process_frame
	_data()
	await _models()
	await _builder()
	await _world()
	print("metka4_test: checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("PASS " if ok else "FAIL ", label, " ", detail)
	if not ok:
		_fails += 1


func _base() -> Dictionary:
	return ItemDb.make("wpn_ar_01", 1)


func _data() -> void:
	_check("имя в каталоге и старый алиас", ItemDb.item_name(Metka4Model.ID) == "ВЕЙР «МЕТКА-4»" and WeaponDb.canonical("mod_laser") == Metka4Model.ID)
	for wid: String in WeaponDb.weapon_ids():
		if String(WeaponDb.weapon(wid).get("class", "")) == "PISTOL":
			_check("не ставится на пистолет " + wid, String(Gear.fit(ItemDb.make(wid, 1), ItemDb.make(Metka4Model.ID, 1))[2]) != "")
	var one: Dictionary = ItemDb.make("wpn_sn_01", 1)
	_check("одной верхней планки недостаточно", not String(Gear.fit(one, ItemDb.make(Metka4Model.ID, 1))[2]).is_empty())
	var fitted: Array = Gear.fit(_base(), {"id": Metka4Model.ID, "n": 1, "dur": 63.0, "laser": true}, "side_right")
	_check("блок с пультом устанавливается одним предметом", String(fitted[2]) == "", str(fitted[2]))
	if String(fitted[2]) != "":
		return
	_pair = fitted[0]
	var rec: Dictionary = _pair.mods.side_right
	_check("две разные планки, один ресурс", rec.has("remote") and String(rec.remote.point) != "side_right" and (_pair.mods as Dictionary).size() == 1 and float(rec.dur) == 63.0)
	var model: String = WeaponBuild.model_of(String(_pair.id))
	var rpoint: String = String(rec.remote.point)
	var span: Vector2 = AttachmentRemote.remote_span(model, rec)
	var g: Dictionary = WeaponBuild.point(String(_pair.id), _pair.mods, rpoint)
	var competitor: String = "mount_rail_ext_01"
	var slot: int = WeaponBuild.nearest_slot(g.rail, WeaponBuild.clamp_of(competitor), (span.x + span.y) * 0.5)
	_check("пульт запрещает пересечение другим обвесом", WeaponBuild.block(_pair, rpoint, competitor, slot) != "")
	var removed: Array = Gear.strip(_pair, "mod:side_right")
	_check("снятие возвращает весь комплект один раз", String(removed[1].id) == Metka4Model.ID and float(removed[1].dur) == 63.0 and not (removed[1] as Dictionary).has("remote") and (removed[0].mods as Dictionary).is_empty())
	_check("после снятия планка свободна", WeaponBuild.block(removed[0], rpoint, competitor, slot) == "")
	var occupied: Dictionary = _base()
	for point: String in ["side_left", "top_front", "underbarrel"]:
		var pt: Dictionary = WeaponBuild.point(String(occupied.id), {}, point)
		for n: int in range(WeaponBuild.slot_count(pt.rail, WeaponBuild.clamp_of("tac_flashlight_01"))):
			occupied.mods[point + "#" + str(n + 2)] = {"id": "tac_flashlight_01", "slot": n}
	_check("без второй свободной планки установка отклонена", WeaponBuild.block(occupied, "side_right", Metka4Model.ID) != "")
	var draft: Dictionary = BuildPlan.draft_of(_pair)
	var choices: Array[Dictionary] = AttachmentRemote.options(String(_pair.id), _pair.mods, "side_right")
	var move: Dictionary = choices[choices.size() - 1]
	draft.side_right.remote = {"point": String(move.point), "slot": int(move.slot), "reverse": bool(move.reverse)}
	var plan: Dictionary = BuildPlan.resolve(_pair, draft, {"from": "weapon"}, {}, {"shop": false})
	_check("конструктор сохраняет отдельное место пульта", String(plan.why) == "" and plan.entry.mods.side_right.remote == draft.side_right.remote, String(plan.why))
	_check("перестановка пульта меняет ключ модели", WeaponCondition.model_key(String(_pair.id), _pair.mods) != WeaponCondition.model_key(String(_pair.id), plan.entry.mods))
	var invalid: Dictionary = BuildPlan.draft_of(_pair)
	invalid.side_right.remote = {"point": "side_right", "slot": 0}
	_check("хост отклоняет пульт на планке блока", String(BuildPlan.resolve(_pair, invalid, {"from": "weapon"}, {}, {}).why) != "")
	invalid.side_right.remote = "bad"
	_check("хост отклоняет повреждённое место пульта", String(BuildPlan.resolve(_pair, invalid, {"from": "weapon"}, {}, {}).why) != "")
	Profile.equipment = {"primary": plan.entry}
	var template: Dictionary = LoadoutTemplates.capture("МЕТКА-4: пульт")
	_check("шаблон снаряжения помнит место пульта", template.slots.primary.place.side_right.remote == plan.entry.mods.side_right.remote)
	Profile.save()
	Profile._loaded = false
	Profile.ensure()
	_check("сохранение оставляет комплект и место пульта", Profile.equipment.primary.mods.side_right.remote == plan.entry.mods.side_right.remote and float(Profile.equipment.primary.mods.side_right.dur) == 63.0)
	var old: Dictionary = {"id": "wpn_ar_01", "mods": {"side_right": {"id": Metka4Model.ID, "dur": 42.0}}}
	var migrated: Array = WeaponDb.migrate(old)
	_check("старый ЛЦУ получает пульт без потери ресурса", (migrated[1] as Array).is_empty() and migrated[0].mods.side_right.has("remote") and float(migrated[0].mods.side_right.dur) == 42.0)
	old.id = "wpn_hg_02"
	var pistol: Array = WeaponDb.migrate(old)
	_check("несовместимый старый комплект возвращается в вещи", not (pistol[0].mods as Dictionary).has("side_right") and (pistol[1] as Array).size() == 1 and float(pistol[1][0].dur) == 42.0)
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 4299
	var in_crate: bool = false
	var on_floor: bool = false
	for i: int in range(12000):
		if not in_crate:
			for item: Dictionary in ItemDb.roll("security", rng):
				if String(item.id) == Metka4Model.ID:
					in_crate = bool(item.fir)
		if not on_floor:
			on_floor = ItemDb.loose_item("security", rng) == Metka4Model.ID
		if in_crate and on_floor:
			break
	_check("доступен в ящиках охраны", in_crate)
	_check("доступен отдельной находкой охраны", on_floor)
	var sight: Dictionary = WeaponBuild.insert(_base(), "optic_primary", {"id": "optic_holo_01"}, 0)[0]
	_check("МЕТКА-4 ставится сверху перед коллиматором", not WeaponBuild.valid_slots(sight, "top_front", Metka4Model.ID).is_empty())
	var front: Dictionary = WeaponBuild.insert(sight, "top_front", ItemDb.make(Metka4Model.ID, 1), 4)[0]
	var warning_draft: Dictionary = BuildPlan.draft_of(front)
	warning_draft.top_front.src = {"from": "backpack", "idx": 0}
	var plan_with_sight: Dictionary = BuildPlan.resolve(sight, warning_draft, {}, {"backpack": [ItemDb.make(Metka4Model.ID, 1)]}, {"lists": ["backpack"]})
	_check("хост принимает сборку несмотря на перекрытие обзора", String(plan_with_sight.why) == "" and (plan_with_sight.take as Array).size() == 1, String(plan_with_sight.why))
	_check("перекрытие обзора вызывает предупреждение", not WeaponBuild.sight_warnings(front).is_empty())
	_check("блок разрешён на подходящей верхней планке коробки", not WeaponBuild.valid_slots(_base(), "optic_primary", Metka4Model.ID).is_empty())
	for side: String in ["side_left", "side_right"]:
		var rail: Dictionary = WeaponMods.socket("veras54", side)
		_check("сокет на настоящей короткой планке " + side, is_equal_approx(absf((rail.pos as Vector3).x), 0.031) and is_equal_approx((rail.pos as Vector3).y, 0.094))
		var pair: Dictionary = WeaponBuild.insert(_base(), "top_front", ItemDb.make(Metka4Model.ID, 1), 4)[0]
		var choices_side: Array[Dictionary] = AttachmentRemote.options(String(pair.id), pair.mods, "top_front")
		var side_record: Dictionary = {}
		for option: Dictionary in choices_side:
			if String(option.point) == side:
				side_record = {"id": Metka4Model.ID, "remote": {"point": side, "slot": int(option.slot), "reverse": bool(option.reverse)}}
				break
		_check("пульт развернут назад и не выходит за цевьё " + side, not side_record.is_empty() and bool(side_record.remote.reverse) and AttachmentRemote.remote_span("veras54", side_record).y <= 0.3551)


func _models() -> void:
	var count: int = 0
	for main: String in AttachmentRemote.FOREEND:
		for remote: String in AttachmentRemote.FOREEND:
			if main == remote:
				continue
			var entry: Dictionary = _base()
			var selected: Dictionary = {}
			for slot: int in WeaponBuild.valid_slots(entry, main, Metka4Model.ID):
				var probe: Dictionary = {main: {"id": Metka4Model.ID, "slot": slot}}
				for choice: Dictionary in AttachmentRemote.options(String(entry.id), probe, main):
					if String(choice.point) == remote:
						probe[main]["remote"] = {"point": remote, "slot": int(choice.slot), "reverse": bool(choice.reverse)}
						selected = probe
						break
				if not selected.is_empty():
					break
			_check("монтаж " + main + " → " + remote, not selected.is_empty())
			if selected.is_empty():
				continue
			count += 1
			var model: Node3D = WeaponModels.build(String(entry.id), selected)
			add_child(model)
			await get_tree().process_frame
			var kit: Node3D = model.find_child("METKA4", true, false) as Node3D
			_check("две части и рабочий лазер " + main + " → " + remote, kit != null and kit.find_child("Main_Mount", true, false) != null and kit.find_child("Remote_Mount", true, false) != null and kit.find_child("LaserBeam_*", true, false) is LaserSight)
			if kit:
				_check("провод сохраняет длину " + main + " → " + remote, absf(float(kit.get_meta("cable_length_m", 0.0)) - AttachmentRemote.LENGTH) < 0.0002)
				var s: Skeleton3D = kit.find_child("Skeleton3D", true, false) as Skeleton3D
				var start: Vector3 = (kit.find_child("Cable_Start", true, false) as Node3D).global_position
				var bone_start: Vector3 = s.global_transform * s.get_bone_global_pose(0).origin
				var last: Transform3D = s.get_bone_global_pose(s.get_bone_count() - 1)
				var bone_end: Vector3 = s.global_transform * (last * Vector3(0, AttachmentRemote.LENGTH / s.get_bone_count(), 0))
				var end: Vector3 = (kit.find_child("Cable_End", true, false) as Node3D).global_position
				_check("оба конца провода в разъёмах " + main + " → " + remote, start.distance_to(bone_start) < 0.0001 and end.distance_to(bone_end) < 0.0001, str([start.distance_to(bone_start), end.distance_to(bone_end)]))
			model.free()
	_check("все 12 сочетаний сторон", count == 12)
	var bracket: Dictionary = WeaponBuild.insert(_base(), "optic_primary", ItemDb.make("mount_offset45_01", 1), 4)[0]
	var with_lumar: Array = Gear.fit(bracket, ItemDb.make("optic_holo_01", 1), "optic_primary/rail")
	_check("ЛУМАР устанавливается на переходник 45°", String(with_lumar[2]) == "")
	var gun: Node3D = WeaponModels.build("wpn_ar_01", with_lumar[0].mods)
	add_child(gun)
	await get_tree().process_frame
	var part: Node3D = gun.find_child("Attachment_optic_primary__rail", true, false) as Node3D
	var lumar: Node3D = part.find_child("LUMAR_H1", true, false) as Node3D
	var pivot: Node3D = part.get_node("Mount") as Node3D
	_check("ЛУМАР опирается прямо на площадку без длинной ножки", lumar.position.length() < 0.0001 and pivot.get_child_count() == 1, str(lumar.position))
	var expected: Transform3D = WeaponMods.point_frame(gun, "veras54", with_lumar[0].mods, "optic_primary/rail")
	_check("ось ЛУМАРа совпадает с переходником 45°", WeaponModels.between(gun, lumar).origin.distance_to(expected.origin) < 0.0001)
	gun.free()
	var alone: Node3D = ItemModels.build(Metka4Model.ID)
	add_child(alone)
	await get_tree().process_frame
	var box: AABB = ItemModels.bounds(alone)
	_check("мировой предмет в реальном масштабе", box.size.length() > 0.12 and box.size.length() < 0.3, str(box))
	alone.free()


func _builder() -> void:
	Profile.equipment = {"primary": _pair}
	Profile.modules["workbench"] = 2
	var builder: WeaponBuilder = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await get_tree().process_frame
	builder._sel = "side_right"
	builder._refresh()
	await get_tree().process_frame
	var selector: OptionButton = null
	for node: Node in builder._actions.get_children():
		if node is OptionButton:
			selector = node as OptionButton
	_check("конструктор показывает выбор места пульта", selector != null and selector.item_count > 2)
	var choices: Array[Dictionary] = AttachmentRemote.options(String(_pair.id), _pair.mods, "side_right")
	var target: Dictionary = choices[choices.size() - 1]
	builder._move_remote("side_right", target)
	_check("команда конструктора меняет место пульта", String(builder._draft.side_right.remote.point) == String(target.point) and int(builder._draft.side_right.remote.slot) == int(target.slot))
	builder._remove("side_right")
	_check("в конструкторе пульт снимается с блоком", builder._draft.is_empty())
	builder.queue_free()
	await get_tree().process_frame
	var sight: Dictionary = WeaponBuild.insert(_base(), "optic_primary", {"id": "optic_holo_01"}, 0)[0]
	var front: Dictionary = WeaponBuild.insert(sight, "top_front", ItemDb.make(Metka4Model.ID, 1), 4)[0]
	Profile.equipment = {"primary": sight}
	Profile.backpack = [ItemDb.make(Metka4Model.ID, 1)]
	builder = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await get_tree().process_frame
	builder._draft = BuildPlan.draft_of(front)
	builder._draft.top_front.src = {"from": "backpack", "idx": 0}
	builder._refresh()
	_check("в интерфейсе есть предупреждение и доступна кнопка Применить", not builder._apply_btn.disabled and builder._status.text.contains("Установка разрешена"), builder._status.text)
	builder.queue_free()
	await get_tree().process_frame


func _world() -> void:
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = []
	Profile.pending_raid = true
	Profile.from_hideout = true
	Profile.save()
	get_tree().change_scene_to_file("res://scenes/levels/mall_map.tscn")
	for i: int in range(30):
		await get_tree().process_frame
	var player: Player = Raid.current.local_player()
	player.set_physics_process(false)
	player.health.hp = 1e9
	var point: LooseLoot = (load("res://scenes/items/metka4_loot.tscn") as PackedScene).instantiate() as LooseLoot
	get_tree().current_scene.add_child(point)
	point.global_position = player.global_position
	_check("отдельный предмет в мире с новым названием", point.items.size() == 1 and point.prompt().contains("МЕТКА-4") and point._vis.get_child_count() == 1)
	player.inventory.items = []
	player.global_position = point.global_position + Vector3(20, 0, 0)
	point._use(1)
	_check("нельзя подобрать издалека", point.items.size() == 1)
	player.global_position = point.global_position
	point._use(1)
	point._use(1)
	_check("подбор выдаёт один комплект и убирает модель", player.inventory.count(Metka4Model.ID) == 1 and point.items.is_empty() and point._vis.get_child_count() == 0)
	_check("находка сохраняет статус найдено в рейде", bool(player.inventory.items[0].get("fir", false)))
