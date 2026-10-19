extends Node
## ПМ: сохранение боезапаса, атомарные операции хоста, риг, LOD и процедурный запасной вариант.

const PM_ID: String = "wpn_hg_01"
const SUP_ID: String = "muzzle_supp_pm_01"
var _fails: int = 0
var _checks: int = 0

class StateHost extends Node:
	var actor: Player

	func request_weapon_state(slot: String, state: Dictionary) -> void:
		actor.inventory.apply_weapon_state(slot, state)


class AILootCapture extends Raid:
	var dropped: Array = []

	func credit_kill(_peer_id: int, _arch: String = "", _info: Dictionary = {}) -> void:
		pass

	func spawn_drop(_pos: Vector3, _display: String, list: Array, _look: LootContainer.Look, _toss: Vector3 = Vector3.ZERO) -> void:
		dropped = list.duplicate(true)


func _ready() -> void:
	_run.call_deferred()


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("  [%s] %s %s" % ["ok" if ok else "FAIL", label, detail])
	if not ok:
		_fails += 1


func _weapon(mag_rounds: int, chamber: int) -> Dictionary:
	return {"id": PM_ID, "n": 1, "dur": 100.0, "rev": 0, "mods": {}, "sight": "primary",
		"mag": {"id": "mag_918_8", "ammo": "ammo_918_pst", "rounds": mag_rounds},
		"chamber": chamber, "chamber_ammo": "ammo_918_pst" if chamber > 0 else ""}


func _state(entry: Dictionary) -> Dictionary:
	var mag: Dictionary = entry.get("mag", {})
	return {"id": String(entry.get("id", "")), "rev": int(entry.get("rev", 0)), "rounds": int(mag.get("rounds", 0)),
		"chamber": int(entry.get("chamber", 0)), "chamber_ammo": String(entry.get("chamber_ammo", "")), "dur": float(entry.get("dur", 100.0))}


func _rounds(entry: Dictionary, items: Array) -> int:
	var total: int = Gear.total_rounds(entry)
	for raw: Dictionary in items:
		if WeaponDb.is_weapon(String(raw.id)):
			total += Gear.total_rounds(raw)
		elif raw.has("rounds"):
			total += int(raw.rounds)
		elif WeaponDb.ammo_fits(PM_ID, String(raw.id)):
			total += int(raw.n)
	return total


func _run() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	var legacy: Dictionary = _weapon(8, 0)
	legacy.erase("chamber")
	legacy.erase("chamber_ammo")
	var migrated: Dictionary = Gear.normalize_chamber(legacy)
	_check("миграция старой записи сохраняет восемь патронов", Gear.total_rounds(migrated) == 8 and int(migrated.chamber) == 1 and int(migrated.mag.rounds) == 7)
	_check("миграция не меняет исходную запись", not legacy.has("chamber") and int(legacy.mag.rounds) == 8)
	_check("повторная миграция не переносит второй патрон", Gear.normalize_chamber(migrated) == migrated)
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	var preset_entry: Dictionary = {}
	for preset_id: String in WeaponDb.ids("presets"):
		if String(WeaponDb.preset(preset_id).get("weapon", "")) == PM_ID:
			preset_entry = WeaponDb.make_weapon(preset_id, rng, [100, 100])
			break
	_check("создание ПМ сразу учитывает патронник", not preset_entry.is_empty() and preset_entry.has("chamber") and Gear.total_rounds(preset_entry) == 8)
	var stats: Dictionary = WeaponStats.compute(_weapon(0, 0))
	_check("полная перезарядка дольше неполной", float(stats.reload_empty) > float(stats.reload))
	_check("клавиша глушителя есть в InputMap", InputMap.has_action("toggle_suppressor") and not InputMap.action_get_events("toggle_suppressor").is_empty())
	for slot: String in ["suppressor_on", "suppressor_off", "mag_out", "mag_in", "bolt_lock", "charge"]:
		_check("звуковой слот " + slot, String(WeaponDb.weapon_sound_map(PM_ID).get(slot, "")) != "")
	_inventory_cases()
	_revision_cases()
	_model_cases()
	await _player_cases()
	await _ai_cases()
	print("pm_test: проверок %d, провалено %d" % [_checks, _fails])
	# Dummy-аудиодрайвер завершает playback после стопа; ресурсы стенда не остаются при выходе.
	var sounds: Array[Node] = get_tree().root.find_children("*", "AudioStreamPlayer", true, false)
	sounds.append_array(get_tree().root.find_children("*", "AudioStreamPlayer3D", true, false))
	for sound: Node in sounds:
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	await get_tree().create_timer(0.15).timeout
	get_tree().quit(_fails)


func _inventory_cases() -> void:
	for empty: bool in [false, true]:
		var inv: Inventory = Inventory.new()
		add_child(inv)
		var e: Dictionary = _weapon(0, 0) if empty else _weapon(3, 1)
		inv.equipment = {"secondary": e}
		ItemDb.add_to(inv.items, WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8), Balance.BACKPACK_GRID)
		var before: int = _rounds(e, inv.items)
		var result: Array = inv.reload_slot("secondary", _state(e))
		var after: Dictionary = inv.equipment.secondary
		_check("полная даёт 8, неполная 8+1: " + str(empty), String(result[0]) == "swap" and Gear.total_rounds(after) == (8 if empty else 9), str(after))
		_check("перезарядка сохраняет суммарный боезапас: " + str(empty), _rounds(after, inv.items) + int((result[1] as Dictionary).get("rounds", 0)) == before)
		_check("магазин не превышает вместимость", int(after.mag.rounds) <= 8 and int(after.chamber) == 1)
		var snapshot: String = JSON.stringify([inv.equipment, inv.items])
		inv.reload_slot("secondary", _state(e))
		_check("повтор старого запроса перезарядки отклонён", JSON.stringify([inv.equipment, inv.items]) == snapshot)
		inv.free()
	var inv: Inventory = Inventory.new()
	add_child(inv)
	inv.equipment = {"secondary": _weapon(4, 1)}
	ItemDb.add_to(inv.items, ItemDb.make(SUP_ID, 1), Balance.BACKPACK_GRID)
	var before_entry: Dictionary = inv.equipment.secondary.duplicate(true)
	var before_items: Array = inv.items.duplicate(true)
	var install_error: String = inv.toggle_suppressor("secondary", _state(before_entry), true, PM_ID)
	_check("глушитель устанавливается из рюкзака", install_error == "" and bool(WeaponStats.compute(inv.equipment.secondary).suppressed))
	_check("при установке в рюкзаке нет копии", _supp_count(inv.items) == 0 and _rounds(inv.equipment.secondary, inv.items) == _rounds(before_entry, before_items))
	var mounted: Dictionary = inv.equipment.secondary.duplicate(true)
	var mounted_snapshot: String = JSON.stringify([inv.equipment, inv.items])
	_check("повтор установки старой ревизией отклонён", inv.toggle_suppressor("secondary", _state(before_entry), true, PM_ID) != "" and JSON.stringify([inv.equipment, inv.items]) == mounted_snapshot)
	var remove_error: String = inv.toggle_suppressor("secondary", _state(mounted), false, PM_ID)
	_check("снятый глушитель возвращается в рюкзак", remove_error == "" and not bool(WeaponStats.compute(inv.equipment.secondary).suppressed) and _supp_count(inv.items) == 1)
	_check("переустановка без потери боезапаса", _rounds(inv.equipment.secondary, inv.items) == _rounds(before_entry, before_items))
	inv.equipment = {"secondary": mounted}
	inv.items = []
	for idx: int in range(Balance.BACKPACK_GRID.x * Balance.BACKPACK_GRID.y):
		inv.items.append({"id": "bandage", "n": 1, "x": idx % Balance.BACKPACK_GRID.x, "y": idx / Balance.BACKPACK_GRID.x, "r": false})
	var full_snapshot: String = JSON.stringify([inv.equipment, inv.items])
	_check("в полном рюкзаке снятие атомарно отклоняется", inv.toggle_suppressor("secondary", _state(inv.equipment.secondary), false, PM_ID) != "" and JSON.stringify([inv.equipment, inv.items]) == full_snapshot)
	inv.free()
	var plus_one: Dictionary = _weapon(8, 1)
	var no_chamber: Dictionary = _weapon(8, 0)
	_check("патронник учитывается в массе", ItemDb.entry_weight(plus_one) > ItemDb.entry_weight(no_chamber))
	_check("патронник учитывается в цене", ItemDb.entry_value(plus_one) > ItemDb.entry_value(no_chamber))


func _supp_count(items: Array) -> int:
	var count: int = 0
	for raw: Dictionary in items:
		if String(raw.id) == SUP_ID:
			count += int(raw.n)
	return count


func _revision_cases() -> void:
	var inv: Inventory = Inventory.new()
	add_child(inv)
	inv.equipment = {"secondary": _weapon(3, 1)}
	ItemDb.add_to(inv.items, WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8), Balance.BACKPACK_GRID)
	ItemDb.add_to(inv.items, ItemDb.make(SUP_ID, 1), Balance.BACKPACK_GRID)
	var old: Dictionary = inv.equipment.secondary.duplicate(true)
	var state: Dictionary = _state(old)
	inv.apply_weapon_state("secondary", state)
	_check("обычный снимок патронов сохраняет поколение и ревизию", inv.equipment.secondary.get("_equip_generation") == old.get("_equip_generation") and int(inv.equipment.secondary.rev) == int(old.rev))
	inv.equipment = {}
	inv.equipment = {"secondary": old}
	_check("возврат оружия в пустой слот получает новую ревизию", int(inv.equipment.secondary.rev) > int(old.rev))
	var snapshot: String = JSON.stringify([inv.equipment, inv.items])
	state["rounds"] = 8
	inv.apply_weapon_state("secondary", state)
	inv.reload_slot("secondary", state)
	inv.toggle_suppressor("secondary", state, true, PM_ID)
	_check("запоздалые state/reload/suppressor после удаления слота не меняют вещи", JSON.stringify([inv.equipment, inv.items]) == snapshot)
	var previous_rev: int = int(inv.equipment.secondary.rev)
	inv.equipment = {"secondary": _weapon(0, 0)}
	_check("прямое назначение другого ПМ повышает ревизию", int(inv.equipment.secondary.rev) > previous_rev and Gear.total_rounds(inv.equipment.secondary) == 0)
	var saved: Dictionary = inv.equipment.secondary.duplicate(true)
	var reloaded: Inventory = Inventory.new()
	add_child(reloaded)
	reloaded.equipment = {"secondary": saved}
	_check("новый Inventory сохраняет ревизию и поколение профиля", reloaded.equipment.secondary == saved)
	var wrong_id: Dictionary = _state(saved)
	wrong_id["id"] = "wpn_hg_02"
	wrong_id["rounds"] = 8
	reloaded.apply_weapon_state("secondary", wrong_id)
	_check("id защищает снимок от другого оружия", reloaded.equipment.secondary == saved)
	reloaded.free()
	inv.free()


func _triangles(node: Node, parent_visible: bool = true) -> int:
	var shown: bool = parent_visible and (not node is Node3D or (node as Node3D).visible)
	if not shown:
		return 0
	var count: int = 0
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] is PackedInt32Array else PackedInt32Array()
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			count += (indices.size() if not indices.is_empty() else vertices.size()) / 3
	for child: Node in node.get_children():
		count += _triangles(child, shown)
	return count


func _model_cases() -> void:
	var model: Node3D = WeaponModels.build(PM_ID)
	add_child(model)
	var rig: WeaponRig = WeaponRig.find_on(model)
	_check("GLB ПМ загружается с WeaponRig", rig != null)
	if rig != null:
		for name_: String in ["Frame", "Slide", "Barrel", "Trigger", "Hammer", "SlideStop", "Safety", "MagCatch", "Magazine", "Suppressor"]:
			_check("деталь " + name_, rig.part(name_) != null)
		for name_: String in ["Muzzle", "MuzzleSuppressed", "SightFront", "SightRear"]:
			_check("метка " + name_, rig.marker(name_) != null)
		for meta: String in ["muzzle", "sight_h", "ads_z"]:
			_check("meta " + meta, model.has_meta(meta))
		var front: Vector3 = model.get_meta("sight_front", Vector3.ZERO)
		var rear: Vector3 = model.get_meta("sight_rear", Vector3.ZERO)
		_check("прицельные метки лежат на настоящей верхней линии", front.y > 0.07 and is_equal_approx(front.y, rear.y) and front.z > rear.z + 0.1)
		for pivot_name: String in ["Trigger", "Hammer", "Magazine", "Suppressor"]:
			_check("ось детали не обнулена при экспорте: " + pivot_name, WeaponRig._relative_transform(rig.part(pivot_name), rig).origin.length() > 0.01)
		_check("метки хвата на месте", model.find_child("RightGrip", true, false) != null and model.find_child("LeftGrip", true, false) != null)
		_check("магазин распознаётся игрой", rig.part("Magazine").get_meta("part", "") == "mag")
		_check("глушитель распознаётся игрой", rig.part("Suppressor").get_meta("part", "") == "muzzle_device")
		rig.set_ammo_state(9)
		rig.set_suppressed(true)
		_check("FP-бюджет со всеми деталями и патронами", _triangles(model) <= 40000, str(_triangles(model)))
		rig.set_suppressed(false)
		rig.set_ammo_state(0)
		_check("на нуле затвор на задержке", rig.is_slide_locked())
		rig.set_ammo_state(8)
		_check("снаряжённый ПМ закрыт", not rig.is_slide_locked())
		var mag_transform: Transform3D = rig.part("Magazine").transform
		rig.pose_action("reload", 0.22, false)
		_check("магазин выходит при перезарядке", rig.part("Magazine").transform.origin.distance_to(mag_transform.origin) > 0.01)
		_check("перезарядка отводит ПМ в сторону от линии взгляда", rig.view_offset().length() > 0.01)
		rig.cancel_action()
		_check("прерывание восстанавливает магазин", rig.part("Magazine").transform.is_equal_approx(mag_transform) and rig.part("Magazine").visible)
		_check("отмена перезарядки убирает смещение ПМ", rig.view_offset().is_zero_approx())
		rig.set_suppressed(true)
		var muzzle_sup: Vector3 = model.get_meta("muzzle")
		rig.set_suppressed(false)
		var muzzle_bare: Vector3 = model.get_meta("muzzle")
		_check("дульный срез меняется с глушителем", muzzle_sup.z > muzzle_bare.z and not rig.part("Suppressor").visible, "%s → %s" % [muzzle_bare, muzzle_sup])
		rig.pose_action("suppressor", 0.5)
		rig.cancel_action()
		_check("прерывание установки скрывает незакреплённый глушитель", not rig.part("Suppressor").visible)
		rig.set_ammo_state(0)
		rig.play_reload(true, 0.2)
		rig.advance_action(0.25)
		var waiting_slide: Transform3D = rig.part("Slide").transform
		rig.set_ammo_state(0)
		_check("поза досыла ждёт ответа хоста после таймера", rig.is_busy() and rig.action == "reload" and rig.part("Slide").transform.is_equal_approx(waiting_slide))
		rig.finish_reload(8)
		_check("подтверждение завершает ожидающую позу", not rig.is_busy() and not rig.is_slide_locked())
		_check("завершение перезарядки убирает смещение ПМ", rig.view_offset().is_zero_approx())
		rig.play_suppressor(true, 0.2)
		rig.advance_action(0.25)
		rig.set_ammo_state(8)
		_check("накрученный глушитель виден до ответа хоста", rig.is_busy() and rig.part("Suppressor").visible)
		rig.cancel_action()
	model.free()
	var lod_model: Node3D = WeaponModels.build(PM_ID, {}, 1)
	add_child(lod_model)
	_check("LOD1 имеет риг и укладывается в бюджет", WeaponRig.find_on(lod_model) != null and _triangles(lod_model) <= 5000, str(_triangles(lod_model)))
	lod_model.free()
	# Недоступный путь проверяет реальную ветку build, не меняя файл ассета на диске.
	var definition: Dictionary = WeaponDb.weapon(PM_ID)
	var asset_path: String = String(definition.get("asset", ""))
	definition["asset"] = "res://assets/models/weapons/pm/absent_for_pm_test.glb"
	var fallback: Node3D = WeaponModels.build(PM_ID, {"muzzle": {"id": SUP_ID}})
	definition["asset"] = asset_path
	_check("без GLB работает процедурный запасной вариант", fallback != null and fallback.has_meta("muzzle") and WeaponRig.find_on(fallback) == null)
	fallback.free()


func _player_cases() -> void:
	var world: Node3D = Node3D.new()
	add_child(world)
	var actor: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	world.add_child(actor)
	actor.set_physics_process(false)
	actor.health.invulnerable = true
	var host: StateHost = StateHost.new()
	host.actor = actor
	world.add_child(host)
	host.add_to_group("hideout_level")
	await get_tree().process_frame
	_reset_player(actor, _weapon(3, 1))
	var snapshot: String = JSON.stringify([actor.inventory.equipment, actor.inventory.items])
	actor._start_reload(actor.spec())
	_check("Player начинает неполную перезарядку без переноса предметов", not actor._pm_action.is_empty() and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	actor.cancel_weapon_action()
	_check("отмена перезарядки не меняет вещи", actor._pm_action.is_empty() and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	actor._start_reload(actor.spec())
	actor._finish_reload(actor.spec())
	_check("Player завершает неполную перезарядку в 8+1", actor.ammo == 9 and actor._pm_action.is_empty() and int(actor.weapon_entry().chamber) == 1)
	var equipped: Dictionary = actor.weapon_entry().duplicate(true)
	var all_rounds: int = _rounds(equipped, actor.inventory.items)
	_check("Player начинает установку глушителя", actor.toggle_suppressor())
	actor.cancel_weapon_action()
	_check("отмена установки оставляет единственный глушитель в рюкзаке", _supp_count(actor.inventory.items) == 1 and not bool(actor.spec().suppressed))
	actor.toggle_suppressor()
	actor._tick_suppressor(float(Balance.PM_ACTION.suppressor_sec) + 0.01)
	_check("Player подтверждает установку и пересчитывает характеристики", bool(actor.spec().suppressed) and _supp_count(actor.inventory.items) == 0 and _rounds(actor.weapon_entry(), actor.inventory.items) == all_rounds)
	actor.toggle_suppressor()
	actor.cancel_weapon_action()
	_check("отмена снятия сохраняет установленный глушитель", bool(actor.spec().suppressed) and _supp_count(actor.inventory.items) == 0)
	actor.toggle_suppressor()
	actor._tick_suppressor(float(Balance.PM_ACTION.suppressor_sec) + 0.01)
	_check("Player снимает глушитель без копии и потери патронов", not bool(actor.spec().suppressed) and _supp_count(actor.inventory.items) == 1 and _rounds(actor.weapon_entry(), actor.inventory.items) == all_rounds)
	_reset_player(actor, _weapon(0, 0))
	actor._start_reload(actor.spec())
	# магазин лежит в рюкзаке, разгрузки нет — надбавка Balance.RIG.backpack_reload_k
	_check("Player выбирает длительность пустой перезарядки", is_equal_approx(actor.reload_timer, float(actor.spec().reload_empty) * float(Balance.RIG.backpack_reload_k)))
	actor._finish_reload(actor.spec())
	_check("Player завершает пустую перезарядку в 8 патронов", actor.ammo == 8 and int(actor.weapon_entry().mag.rounds) == 7 and int(actor.weapon_entry().chamber) == 1)
	_reset_player(actor, _weapon(8, 0))
	actor._fire(actor.spec())
	_check("выстрел после пустого патронника расходует один патрон", actor.ammo == 7 and Gear.total_rounds(actor.weapon_entry()) == 7)
	actor._start_reload(actor.spec())
	actor.cancel_weapon_action()
	_check("прерывание после выстрела сохраняет расход на хосте", Gear.total_rounds(actor.inventory.equipment.sidearm) == 7)
	_reset_player(actor, _weapon(0, 1))
	actor._update_hand()
	actor._fire(actor.spec())
	if actor._weapon_rig:
		actor._weapon_rig.advance_action(0.1)
	_check("последний выстрел Player оставляет затвор на задержке", actor.ammo == 0 and actor._weapon_rig != null and actor._weapon_rig.is_slide_locked())
	_reset_player(actor, _weapon(2, 1))
	actor._start_reload(actor.spec())
	snapshot = JSON.stringify([actor.inventory.equipment, actor.inventory.items])
	actor._switch("primary", false)
	_check("смена оружия прерывает действие и сохраняет предметы", actor._pm_action.is_empty() and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	_reset_player(actor, _weapon(3, 1))
	actor._start_reload(actor.spec())
	var pending: Dictionary = actor._pm_action.duplicate(true)
	ItemDb.add_to(actor.inventory.items, _weapon(0, 0), Balance.BACKPACK_GRID)
	var replacement_idx: int = -1
	for idx: int in range(actor.inventory.items.size()):
		if String(actor.inventory.items[idx].id) == PM_ID:
			replacement_idx = idx
	actor.inventory.equip_from_items(replacement_idx)
	snapshot = JSON.stringify([actor.inventory.equipment, actor.inventory.items])
	_check("замена ПМ другим ПМ перечитывает состояние владельца", Gear.total_rounds(actor.weapon_entry()) == 0)
	var rejected: Dictionary = actor._host_pm_commit(pending)
	_check("старое действие не применяется к заменённому ПМ", String(rejected.get("error", "")) != "" and JSON.stringify([actor.inventory.equipment, actor.inventory.items]) == snapshot)
	actor.cancel_weapon_action()
	actor._start_reload(actor.spec())
	actor.health.downed = true
	actor.health.downed_changed.emit(true)
	_check("тяжёлое ранение отменяет перезарядку", actor._pm_action.is_empty() and actor.reload_timer == 0.0)
	world.free()


func _reset_player(actor: Player, entry: Dictionary) -> void:
	actor.cancel_weapon_action()
	actor.weapon_id = ""
	actor.weapon_slot = ""
	actor._ws.clear()
	actor._pm_entries.clear()
	actor._ws_dirty = false
	actor.stress = 0.0
	actor.health.alive = true
	actor.health.downed = false
	actor.loadout_mode = true
	actor.inventory.equipment = {"sidearm": entry}
	actor.inventory.items = []
	actor.inventory.buffer = []
	ItemDb.add_to(actor.inventory.items, WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8), Balance.BACKPACK_GRID)
	ItemDb.add_to(actor.inventory.items, ItemDb.make(SUP_ID, 1), Balance.BACKPACK_GRID)
	actor._switch("sidearm", false)


## Настоящий ИИ стреляет и перезаряжается; только получение ящика заменено сборщиком.
func _ai_cases() -> void:
	var world: Node3D = Node3D.new()
	add_child(world)
	var npc: Marauder = (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	npc.name = "PMAmmoNpc"
	npc.archetype = "pmc"
	npc.loadout_id = "perimeter_marksman"
	npc.process_mode = Node.PROCESS_MODE_DISABLED
	world.add_child(npc)
	# Без случайного лута и целей: проверяем боезапас, не меняя профиль или мир рейда.
	# На стенде нет навмеша: собственный выстрел не запускает поиск источника шума.
	NoiseBus.noise.disconnect(npc._on_noise)
	npc.loadout_id = ""
	npc.meds = []
	npc.pack = []
	await get_tree().physics_frame
	_reset_ai(npc, _weapon(8, 0))
	_check("AI досылает из магазина без создания патрона", npc._mag == 8 and int(npc.equipment.secondary.mag.rounds) == 7 and int(npc.equipment.secondary.chamber) == 1)
	npc._try_fire()
	_check("AI первый выстрел из досланного ПМ расходует патрон", npc._mag == 7 and Gear.total_rounds(npc.equipment.secondary) == 7)
	_reset_ai(npc, _weapon(7, 1))
	var spent: int = 0
	for shot: int in range(7):
		npc._shot_t = 0.0
		var before: int = npc._mag
		npc._try_fire()
		spent += before - npc._mag
	_check("AI после семи выстрелов сохраняет последний патрон в патроннике", spent == 7 and npc._mag == 1 and int(npc.equipment.secondary.mag.rounds) == 0 and int(npc.equipment.secondary.chamber) == 1)
	npc._shot_t = 0.0
	npc._try_fire()
	_check("AI выпускает все восемь патронов, включая патронник", npc._mag == 0 and Gear.total_rounds(npc.equipment.secondary) == 0 and String(npc.equipment.secondary.chamber_ammo) == "")
	_reset_ai(npc, _weapon(0, 1))
	npc._try_fire()
	_check("AI стреляет с пустым магазином и единственным патроном в патроннике", npc._mag == 0 and int(npc.equipment.secondary.chamber) == 0)
	for empty: bool in [false, true]:
		_reset_ai(npc, _weapon(0, 0) if empty else _weapon(3, 1), [WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8)])
		var before: int = _rounds(npc.equipment.secondary, npc.spare)
		npc._finish_reload()
		var after: Dictionary = npc.equipment.secondary
		_check("AI полная перезарядка даёт 8, неполная 8+1: " + str(empty), npc._mag == (8 if empty else 9) and int(after.chamber) == 1 and int(after.mag.rounds) == (7 if empty else 8))
		_check("AI перезарядка возвращает точный остаток старого магазина: " + str(empty), npc.spare.size() == 1 and int(npc.spare[0].rounds) == (0 if empty else 3) and _rounds(after, npc.spare) == before)
	var rifle: Dictionary = WeaponDb.make_weapon("AR_03_BASE", npc._rng, [100, 100])
	_reset_ai(npc, _weapon(3, 1))
	npc.equipment["primary"] = rifle
	npc._use("primary")
	_check("AI при смене оружия сохраняет отдельно магазин и патронник", int(npc.equipment.secondary.mag.rounds) == 3 and int(npc.equipment.secondary.chamber) == 1)
	npc._use("secondary")
	_check("AI после возвращения ПМ восстанавливает общий боезапас", npc._mag == 4 and Gear.total_rounds(npc.equipment.secondary) == 4)
	_reset_ai(npc, _weapon(0, 1))
	(rifle.mag as Dictionary)["rounds"] = 0
	npc.equipment["primary"] = rifle
	npc._use("primary")
	npc._start_reload()
	_check("AI выбирает запасной ПМ с единственным патроном в патроннике", npc._active == "secondary" and npc._mag == 1 and not npc._dry)
	_reset_ai(npc, _weapon(3, 1), [WeaponDb.make_mag("mag_918_8", "ammo_918_pst", 8)])
	var before_drop: int = _rounds(npc.equipment.secondary, npc.spare)
	var previous_raid: Raid = Raid.current
	var capture: AILootCapture = AILootCapture.new()
	Raid.current = capture
	npc._on_died()
	Raid.current = previous_raid
	var dropped_weapon: Dictionary = {}
	var dropped_mags: Array = []
	for raw: Dictionary in capture.dropped:
		if String(raw.id) == PM_ID:
			dropped_weapon = raw
		elif raw.has("rounds"):
			dropped_mags.append(raw)
	_check("AI с тела выпадает ПМ с реальным магазином и патронником", not dropped_weapon.is_empty() and int((dropped_weapon.get("mag", {}) as Dictionary).get("rounds", -1)) == 3 and int(dropped_weapon.get("chamber", 0)) == 1)
	_check("AI смерть сохраняет общий боезапас оружия и запасных магазинов", not dropped_weapon.is_empty() and dropped_mags.size() == 1 and _rounds(dropped_weapon, dropped_mags) == before_drop)
	capture.free()
	# Вспышки и звуки завершатся до удаления узла, к которому привязаны их таймеры.
	await get_tree().create_timer(0.5).timeout
	world.free()


func _reset_ai(npc: Marauder, entry: Dictionary, reserves: Array = []) -> void:
	npc.equipment = {"secondary": entry.duplicate(true)}
	npc.spare = reserves.duplicate(true)
	npc._spec.clear()
	npc._dry = false
	npc._shot_t = 0.0
	npc._target_player = null
	npc._foe = null
	npc._use("secondary")
	npc.last_known = npc.global_position + Vector3(0.0, 0.0, 10.0)
