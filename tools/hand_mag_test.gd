extends Node
## Обойма оружия в руках из окна рюкзака (Player.hand_mag_eject / hand_mag_insert, Balance.HAND_MAG) на АСТЕН-919:
## «Вынуть обойму» — руки вынимают, предмет уходит в рюкзак только по окончании движения, патрон в стволе остаётся;
## магазин на оружие с пустой шахтой — вставить (затвор на задержке — с досылом), на оружие с магазином — перезарядка
## этим магазином (старый — в рюкзак); руки заняты — отказ, отмена не трогает вещи, полный рюкзак — магазин остаётся
## в оружии. Риг: части перезарядки «вынуть» / «вставить» на модели с магазином и с пустой шахтой, подпись записи.
## Оружие без рига (ВЕРАС-54): «вынуть» идёт по таймеру перезарядки (вид «eject»), магазин на оружие — перезарядка
## именно выбранным магазином, а не самым полным, и при открытом рюкзаке.
## tools/godot.cmd --headless res://tools/hand_mag_test.tscn

const GUN: String = "wpn_hg_02"
const MAG: String = "mag_919_17"
const AMMO: String = "ammo_919_fmj"
const SLOT: String = "sidearm"
var _fails: int = 0
var _checks: int = 0


class StateHost extends Node:
	var actor: Player

	func request_weapon_state(slot: String, state: Dictionary) -> void:
		actor.inventory.apply_weapon_state(slot, state)

	func request_reload(slot: String, state: Dictionary) -> void:
		actor.inventory.reload_slot(slot, state)

	## Сброс вещи на землю (быстрая перезарядка): запомнить, что упало, и убрать из списка.
	var dropped: Array = []

	func request_drop_entry(where: String, idx: int, _quiet: bool = false) -> void:
		var list: Array = actor.inventory.list_of(where)
		if idx >= 0 and idx < list.size():
			dropped.append((list[idx] as Dictionary).duplicate(true))
			list.remove_at(idx)

	func request_toss_entry(where: String, idx: int, _data: Dictionary) -> void:
		request_drop_entry(where, idx)


func _ready() -> void:
	_run.call_deferred()


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("  [%s] %s %s" % ["ok" if ok else "FAIL", label, detail])
	if not ok:
		_fails += 1


func _weapon(mag_rounds: int, chamber: int, with_mag: bool = true) -> Dictionary:
	return {"id": GUN, "n": 1, "dur": 100.0, "rev": 0, "mods": {}, "sight": "primary",
		"mag": {"id": MAG if with_mag else "", "ammo": AMMO, "rounds": mag_rounds if with_mag else 0},
		"chamber": chamber, "chamber_ammo": AMMO if chamber > 0 else ""}


func _reset(actor: Player, entry: Dictionary, spare_rounds: Array = [17]) -> void:
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
	actor.inventory.equipment = {SLOT: entry}
	actor.inventory.items = []
	actor.inventory.buffer = []
	for n: int in spare_rounds:
		ItemDb.add_to(actor.inventory.items, WeaponDb.make_mag(MAG, AMMO, n), Balance.BACKPACK_GRID)
	actor._switch(SLOT, false)
	actor._update_hand()


## Довести движение рук до конца (как кадры игры при открытом рюкзаке).
func _finish(actor: Player) -> void:
	for i: int in range(400):
		if actor._pm_action.is_empty():
			return
		actor._tick_hand_mag(0.05)


func _mags(actor: Player) -> Array:
	var out: Array = []
	for it: Dictionary in actor.inventory.items:
		if it.has("rounds"):
			out.append(int(it.rounds))
	out.sort()
	return out


func _snapshot(actor: Player) -> String:
	return JSON.stringify([actor.inventory.equipment, actor.inventory.items])


func _run() -> void:
	_rig_cases()
	await _player_cases()
	print("hand_mag_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _rig_cases() -> void:
	var with_mag: WeaponRig = WeaponModels.build(GUN) as WeaponRig
	_check("модель — риг с магазином", with_mag != null and with_mag.part("Magazine") != null)
	if with_mag == null:
		return
	add_child(with_mag)
	var mag: Node3D = with_mag.part("Magazine")
	var rest: Vector3 = mag.position
	# моменты проверок — по долям фаз из данных (у АСТЕН-919 они сняты с клипов рук владельца): середина «вынул —
	# скрылся» и середина «новый в руке — вставлен»
	var rig_cfg: Dictionary = WeaponDb.weapon(GUN).get("rig", {}) as Dictionary
	var tac: Dictionary = rig_cfg.get("reload", {}) as Dictionary
	var full: Dictionary = rig_cfg.get("reload_empty", tac) as Dictionary
	var hidden: float = float(tac.get("mag_hidden", 0.34))
	var out_mid: float = float(Balance.HAND_MAG.out_hold) * lerpf(float(tac.get("mag_out", 0.22)), hidden, 0.5) / hidden
	var full_hidden: float = float(full.get("mag_hidden", 0.34))
	var in_mid: float = (lerpf(float(full.get("mag_new", 0.48)), float(full.get("mag_in", 0.65)), 0.5) - full_hidden) / (1.0 - full_hidden)
	with_mag.play_reload(false, 1.0, "out")
	with_mag.advance_action(out_mid)
	var moved: float = (mag.position - rest).length()
	var mid_weight: float = with_mag.get_hand_weight()
	_check("«вынуть»: на середине магазин выходит из рукояти, рука на нём", mag.visible and moved > 0.03 and mid_weight > 0.9,
		"сдвиг %.3f м, рука %.2f" % [moved, mid_weight])
	with_mag.advance_action(0.9 - out_mid)
	_check("«вынуть»: к концу магазина не видно, рука возвращается", not mag.visible and with_mag.get_hand_weight() < 0.5,
		"рука %.2f" % with_mag.get_hand_weight())
	with_mag.advance_action(0.2)
	_check("«вынуть»: движение кончилось, рука свободна, магазин не вернулся", not mag.visible and with_mag.get_hand_weight() < 0.01)
	with_mag.finish_reload(1)
	_check("после подтверждения модель с магазином цела", mag.visible and mag.position.is_equal_approx(rest))
	with_mag.queue_free()
	var empty: WeaponRig = WeaponModels.build(GUN, {}, 0, 100.0, "") as WeaponRig
	add_child(empty)
	var body: MeshInstance3D = empty._mag_body
	var rounds_shown: int = 0
	empty.set_ammo_state(5)
	for node: Node3D in empty._rounds:
		rounds_shown += 1 if node.visible else 0
	_check("пустая шахта: корпуса магазина и патронов не видно", body != null and not body.visible and rounds_shown == 0, "патронов видно %d" % rounds_shown)
	empty.play_reload(true, 1.0, "in")
	empty.advance_action(0.05)
	var start_weight: float = empty.get_hand_weight()
	empty.advance_action(maxf(in_mid - 0.05, 0.0))
	var mag_in: Node3D = empty.part("Magazine")
	_check("«вставить»: магазин показан и идёт в рукоять, рука подошла", body.visible and mag_in.visible and start_weight < 0.6 and empty.get_hand_weight() > 0.9,
		"рука %.2f → %.2f" % [start_weight, empty.get_hand_weight()])
	_check("«вставить» с досылом: затвор ещё на задержке", (empty._rest["Slide"] as Transform3D).origin.z - empty.part("Slide").position.z > 0.02, "z %.3f" % empty.part("Slide").position.z)
	empty.advance_action(0.7)
	_check("«вставить»: к концу затвор впереди", absf(empty.part("Slide").position.z - (empty._rest["Slide"] as Transform3D).origin.z) < 0.001)
	empty.finish_reload(17)
	_check("после действия модель с пустой шахтой снова без магазина", not body.visible)
	empty.queue_free()


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
	# --- вынуть
	_reset(actor, _weapon(5, 1), [17])
	_check("оружие в руках: обойму можно вынимать руками", actor.hand_mag_ready(SLOT) and not actor.hand_mag_ready("primary"),
		"свой %s, риг на теле %s" % [str(actor.is_local()), str(is_instance_valid(actor._weapon_rig))])
	var before: String = _snapshot(actor)
	var why: String = actor.hand_mag_eject()
	_check("«Вынуть обойму» начинает движение, вещи на месте", why == "" and String(actor._pm_action.get("kind", "")) == "mag_out" and _snapshot(actor) == before, why)
	_check("риг показывает часть «вынуть»", is_instance_valid(actor._weapon_rig) and actor._weapon_rig.action == "reload" and actor._weapon_rig._reload_part == "out")
	_check("пока руки заняты, второй магазин не вставить", actor.hand_mag_insert("backpack", 0) == "Руки заняты")
	actor._tick_hand_mag(0.1)
	_check("посреди движения вещи ещё на месте", _snapshot(actor) == before)
	actor.cancel_weapon_action()
	_check("отмена не трогает вещи", actor._pm_action.is_empty() and _snapshot(actor) == before)
	actor.hand_mag_eject()
	_finish(actor)
	var entry: Dictionary = actor.weapon_entry()
	_check("движение кончилось: магазин в рюкзаке с остатком, патрон в стволе", String((entry.mag as Dictionary).id) == "" and int(entry.chamber) == 1
		and _mags(actor) == [5, 17] and actor.ammo == 1, "рюкзак %s, в оружии %d" % [str(_mags(actor)), actor.ammo])
	_check("подпись записи: без магазина", ItemDb.label(entry).contains("без магазина"), ItemDb.label(entry))
	_check("вид оружия — пустая шахта", WeaponMods.mag_state(entry) == "")
	actor.weapon_mag = WeaponMods.mag_state(entry)
	_check("вынимать нечего — отказ", actor.hand_mag_eject() == "Магазина в оружии нет")
	# --- вставить в пустую шахту
	var full_at: int = -1
	for i: int in range(actor.inventory.items.size()):
		if int((actor.inventory.items[i] as Dictionary).get("rounds", -1)) == 17:
			full_at = i
	before = _snapshot(actor)
	why = actor.hand_mag_insert("backpack", full_at)
	_check("магазин на оружие с пустой шахтой — движение «вставить»", why == "" and String(actor._pm_action.get("kind", "")) == "mag_in"
		and actor._weapon_rig._reload_part == "in" and _snapshot(actor) == before, why)
	_finish(actor)
	entry = actor.weapon_entry()
	_check("вставлен: 17 в магазине, патрон в стволе тот же, в рюкзаке остался старый", String((entry.mag as Dictionary).id) == MAG
		and int((entry.mag as Dictionary).rounds) == 17 and int(entry.chamber) == 1 and _mags(actor) == [5] and actor.ammo == 18,
		"магазин %d, рюкзак %s" % [int((entry.mag as Dictionary).rounds), str(_mags(actor))])
	actor.weapon_mag = WeaponMods.mag_state(entry)
	# --- магазин на оружие с магазином: перезарядка этим магазином
	why = actor.hand_mag_insert("backpack", 0)
	_check("магазин на оружие с магазином — полная перезарядка", why == "" and actor._weapon_rig._reload_part == "" and actor._weapon_rig.action == "reload", why)
	_finish(actor)
	entry = actor.weapon_entry()
	_check("перезаряжено выбранным: 5 в оружии, 17 вернулись в рюкзак", int((entry.mag as Dictionary).rounds) == 5 and _mags(actor) == [17] and int(entry.chamber) == 1,
		"магазин %d, рюкзак %s" % [int((entry.mag as Dictionary).rounds), str(_mags(actor))])
	# --- пустое оружие на задержке: вставить с досылом
	_reset(actor, _weapon(0, 0, false), [17])
	actor.weapon_mag = ""
	why = actor.hand_mag_insert("backpack", 0)
	_check("пустое оружие: вставить с досылом", why == "" and actor._weapon_rig._empty_reload, why)
	_finish(actor)
	entry = actor.weapon_entry()
	_check("дослан патрон: 16 + 1", int((entry.mag as Dictionary).rounds) == 16 and int(entry.chamber) == 1 and actor.ammo == 17,
		"магазин %d, ствол %d" % [int((entry.mag as Dictionary).rounds), int(entry.chamber)])
	# --- полный рюкзак: вынуть некуда
	_reset(actor, _weapon(9, 1), [])
	var grid: Vector2i = actor.inventory.backpack_grid()
	for i: int in range(grid.x * grid.y + 4):
		if ItemDb.add_to(actor.inventory.items, WeaponDb.make_mag(MAG, AMMO, 1), grid) == 0:
			break
	before = _snapshot(actor)
	actor.hand_mag_eject()
	_finish(actor)
	_check("полный рюкзак: магазин остался в оружии, вещи целы", _snapshot(actor) == before and actor._pm_action.is_empty())
	# --- чужой слот и не то оружие
	_check("магазин не того оружия — отказ", actor.hand_mag_insert("backpack", 999) != "")
	_pistol_fast_cases(actor, host)
	_rifle_cases(actor)
	world.queue_free()


## Пистолет с патронником (владелец 2026-11-14): быстрая перезарядка (двойное R) — при любом остатке в магазине, старый
## падает на землю, патрон в стволе остаётся; последний выстрел без магазина — затвор закрыт, вставить и передёрнуть
## (своё время stats.reload_empty_rack).
func _pistol_fast_cases(actor: Player, host: StateHost) -> void:
	_reset(actor, _weapon(5, 1), [17])
	actor.weapon_mag = WeaponMods.mag_state(actor.weapon_entry())
	host.dropped.clear()
	actor._start_reload(actor.spec())
	var normal: float = actor.reload_timer
	actor._try_fast_reload()
	_check("пистолет: двойное R — быстрая перезарядка", actor._reload_fast and actor.reload_timer < normal and String(actor._pm_action.get("kind", "")) == "reload",
		"%.2f → %.2f с" % [normal, actor.reload_timer])
	_finish_reload(actor)
	var entry: Dictionary = actor.weapon_entry()
	var fell: int = int((host.dropped[0] as Dictionary).get("rounds", -1)) if host.dropped.size() == 1 else -1
	_check("пистолет, быстрая: новый в оружии, патрон в стволе, старый (5) на земле, не в рюкзаке",
		int((entry.mag as Dictionary).rounds) == 17 and int(entry.chamber) == 1 and fell == 5 and _mags(actor).is_empty(),
		"магазин %d, упал %d, рюкзак %s" % [int((entry.mag as Dictionary).rounds), fell, str(_mags(actor))])
	# полный магазин — тоже можно
	_reset(actor, _weapon(17, 1), [17])
	actor.weapon_mag = WeaponMods.mag_state(actor.weapon_entry())
	actor._start_reload(actor.spec())
	actor._try_fast_reload()
	_check("пистолет: быстрая и с полным магазином", actor._reload_fast)
	actor.cancel_weapon_action()
	# последний выстрел без магазина: затвор закрыт, а не на задержке
	_reset(actor, _weapon(0, 1, false), [17])
	actor.weapon_mag = ""
	actor.ammo = 1
	actor.weapon_obstruction = 0.0
	actor._fire(actor.spec())
	_check("пистолет без магазина: последний выстрел — затвор закрыт на пустом патроннике", actor.ammo == 0 and actor.slide_closed_empty)
	var raw: Dictionary = WeaponDb.weapon(GUN).stats
	# в пустую шахту — «только вставить» (Balance.HAND_MAG.in_k) от времени с передёргиванием
	var want: float = float(actor.spec().reload_empty) * float(raw.reload_empty_rack) / float(raw.reload_empty) * float(Balance.HAND_MAG.in_k)
	var why: String = actor.hand_mag_insert("backpack", 0)
	_check("вставить: с передёргиванием — своё время", why == "" and absf(float(actor._pm_action.get("remaining", 0.0)) - want) < 0.05,
		"%.2f с, ждали %.2f" % [float(actor._pm_action.get("remaining", 0.0)), want])
	_finish(actor)
	_check("после досыла затвор снова как обычно", actor.ammo == 17 and not actor.slide_closed_empty, "в оружии %d" % actor.ammo)
	# с магазином последний выстрел ставит на задержку
	_reset(actor, _weapon(0, 1), [17])
	actor.weapon_mag = WeaponMods.mag_state(actor.weapon_entry())
	actor.ammo = 1
	actor._fire(actor.spec())
	_check("с магазином последний выстрел — на задержку", actor.ammo == 0 and not actor.slide_closed_empty)


## Довести перезарядку, начатую из окна рюкзака (кадры игры при открытом окне).
func _finish_reload(actor: Player) -> void:
	for i: int in range(400):
		if actor.reload_timer <= 0.0:
			return
		actor._tick_reload(0.05, actor.spec(), false)


func _rifle_mags(actor: Player) -> Array:
	var out: Array = []
	for it: Dictionary in actor.inventory.items:
		if it.has("rounds"):
			out.append(int(it.rounds))
	out.sort()
	return out


func _rifle_cases(actor: Player) -> void:
	const RIFLE: String = "wpn_ar_01"
	const RMAG: String = "mag_545_30"
	const RAMMO: String = "ammo_545_std"
	actor.cancel_weapon_action()
	actor.weapon_id = ""
	actor.weapon_slot = ""
	actor._ws.clear()
	actor._pm_entries.clear()
	actor._ws_dirty = false
	actor.inventory.equipment = {"primary": {"id": RIFLE, "n": 1, "dur": 100.0, "rev": 0, "mods": {}, "sight": "primary",
		"mag": {"id": RMAG, "ammo": RAMMO, "rounds": 12}}}
	actor.inventory.items = []
	for n: int in [30, 7]:
		ItemDb.add_to(actor.inventory.items, WeaponDb.make_mag(RMAG, RAMMO, n), Balance.BACKPACK_GRID)
	actor._switch("primary", false)
	actor.weapon_mag = WeaponMods.mag_state(actor.weapon_entry())
	_check("автомат в руках: магазин тоже вынимают руками", actor.hand_mag_ready("primary") and not actor._hand_mag_rig())
	var before: String = _snapshot(actor)
	var why: String = actor.hand_mag_eject()
	_check("автомат «вынуть»: действие по таймеру перезарядки, вещи на месте", why == "" and String(actor._pm_action.get("kind", "")) == "mag_out"
		and actor.reload_timer > 0.0 and actor._reload_kind == "eject" and _snapshot(actor) == before, why)
	_finish(actor)
	var entry: Dictionary = actor.weapon_entry()
	_check("автомат: магазин в рюкзаке с остатком, шахта пуста", String((entry.mag as Dictionary).id) == "" and _rifle_mags(actor) == [7, 12, 30]
		and actor.reload_timer <= 0.0 and actor._reload_kind == "", "рюкзак %s" % str(_rifle_mags(actor)))
	actor.weapon_mag = WeaponMods.mag_state(entry)
	var at: int = -1
	for i: int in range(actor.inventory.items.size()):
		if int((actor.inventory.items[i] as Dictionary).get("rounds", -1)) == 7:
			at = i
	why = actor.hand_mag_insert("backpack", at)
	_check("автомат «вставить»: перезарядка выбранным магазином, идёт при открытом окне", why == "" and actor.reload_timer > 0.0 and actor._reload_ui
		and actor._reload_insert and actor.reload_next_mag() == "*", why)
	_finish_reload(actor)
	entry = actor.weapon_entry()
	_check("автомат: вставлен выбранный (7), а не самый полный", int((entry.mag as Dictionary).rounds) == 7 and _rifle_mags(actor) == [12, 30],
		"в оружии %d, рюкзак %s" % [int((entry.mag as Dictionary).rounds), str(_rifle_mags(actor))])
	actor.weapon_mag = WeaponMods.mag_state(entry)
	actor.ammo = actor._state_rounds("primary")
	at = -1
	for i: int in range(actor.inventory.items.size()):
		if int((actor.inventory.items[i] as Dictionary).get("rounds", -1)) == 12:
			at = i
	why = actor.hand_mag_insert("backpack", at)
	_check("автомат с магазином: перезарядка выбранным", why == "" and actor.reload_timer > 0.0 and not actor._reload_insert, why)
	_finish_reload(actor)
	entry = actor.weapon_entry()
	_check("автомат: в оружии выбранный (12), прежний (7) вернулся в рюкзак", int((entry.mag as Dictionary).rounds) == 12 and _rifle_mags(actor) == [7, 30]
		and actor._reload_pick.is_empty(), "в оружии %d, рюкзак %s" % [int((entry.mag as Dictionary).rounds), str(_rifle_mags(actor))])
