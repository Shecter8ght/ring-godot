extends Node
## Обойма оружия в руках из окна рюкзака (Player.hand_mag_eject / hand_mag_insert, Balance.HAND_MAG) на АСТЕН-919:
## «Вынуть обойму» — руки вынимают, предмет уходит в рюкзак только по окончании движения, патрон в стволе остаётся;
## магазин на оружие с пустой шахтой — вставить (затвор на задержке — с досылом), на оружие с магазином — перезарядка
## этим магазином (старый — в рюкзак); руки заняты — отказ, отмена не трогает вещи, полный рюкзак — магазин остаётся
## в оружии. Риг: части перезарядки «вынуть» / «вставить» на модели с магазином и с пустой шахтой, подпись записи.
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
	with_mag.play_reload(false, 1.0, "out")
	with_mag.advance_action(0.4)
	var moved: float = (mag.position - rest).length()
	var mid_weight: float = with_mag.get_hand_weight()
	_check("«вынуть»: на середине магазин выходит из рукояти, рука на нём", mag.visible and moved > 0.03 and mid_weight > 0.9,
		"сдвиг %.3f м, рука %.2f" % [moved, mid_weight])
	with_mag.advance_action(0.5)
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
	empty.advance_action(0.35)
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
	world.queue_free()
