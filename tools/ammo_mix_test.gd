extends Node
## Патроны в магазине вперемешку (Gear.mag_layers): снаряжать можно разными типами — новый ложится
## сверху и уходит в ствол первым; разряжается сверху, по типам; выстрелы идут по слоям (у пули — данные
## своего патрона); вынутый и сменённый магазин сохраняют состав; досыпать россыпью — и другим типом.
## tools/godot.cmd --headless res://tools/ammo_mix_test.tscn

const ID := "wpn_ar_01"
const MAG := "mag_545_30"
const STD := "ammo_545_std"
const AP := "ammo_545_ap"

var _fails: int = 0
var _raid: Raid
var _me: Player


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_pure()
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
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
	var inv := _me.inventory
	var per := float(Balance.MAG_OPS.load_sec)

	# --- «Снарядить»: сверху тот же тип, кончился — другим не подменяет; бросили другие патроны — мешает
	inv.items = []
	inv.add_entry(WeaponDb.make_mag(MAG, STD, 10))
	inv.add(AP, 5)
	_raid.request_item_op("load", "backpack", 0, null, AP, "backpack")
	await get_tree().create_timer(per * 7.0).timeout
	var m: Dictionary = _mag(inv.items)
	_check("бросил другие патроны на неполный магазин — легли сверху", int(m.rounds) == 15 and Gear.mag_layers(m) == [[STD, 10], [AP, 5]] and String(m.ammo) == AP, str(m))
	_check("подпись состава — сверху вниз", Gear.mag_text(m).begins_with(String(ItemDb.item(AP).get("short", ""))) and Gear.mag_text(m).contains("×5") and Gear.mag_text(m).contains("×10"), Gear.mag_text(m))
	# --- разрядить: сверху, по типам
	_raid.request_item_op("unload", "backpack", _mag_idx(inv.items))
	await get_tree().create_timer(float(Balance.MAG_OPS.unload_sec) * 6.5).timeout
	m = _mag(inv.items)
	_check("разряжается сверху: сначала верхний тип", int(m.rounds) <= 10 and inv.count(AP) == 5 and not m.has("mix"), "%s, AP в рюкзаке %d" % [str(m), inv.count(AP)])
	_raid.request_cancel_op()
	await get_tree().create_timer(0.3).timeout

	# --- стрельба по слоям: 3 бронебойных сверху, ниже обычные
	var mixed: Dictionary = WeaponDb.make_mag(MAG, STD, 6)
	Gear.mag_push(mixed, AP, 3)
	_arm(Gear.mag_record(mixed), [])
	var types: Array[String] = []
	var pens: Array[float] = []
	for i in range(5):
		var spec: Dictionary = _me.spec()
		types.append(String(spec.ammo))
		pens.append(float(spec.pen))
		_me.fire_timer = 0.0
		_me._fire(spec)
	_check("в ствол идут по слоям: 3 верхних, потом нижние", types == [AP, AP, AP, STD, STD], str(types))
	_check("у пули — пробитие своего патрона", pens[0] > pens[4], str(pens))
	_check("после пяти выстрелов осталось 4", _me.ammo == 4)
	# --- вынуть магазин: состав цел, отстрелянное снято сверху
	_me._send_ws(_me.weapon_slot)
	await get_tree().physics_frame
	var stripped: Array = Gear.strip(inv.equipment.primary, "mag")
	_check("вынутый магазин: 4 обычных, слоёв нет", int(stripped[1].rounds) == 4 and Gear.mag_layers(stripped[1]) == [[STD, 4]], str(stripped[1]))

	# --- смена магазина: старый (вперемешку) уходит в рюкзак с составом
	mixed = WeaponDb.make_mag(MAG, STD, 6)
	Gear.mag_push(mixed, AP, 3)
	_arm(Gear.mag_record(mixed), [30])
	var r: Array = inv.reload_slot("primary", _me._ws_state("primary"))
	var old: Dictionary = {}
	for it: Dictionary in inv.items:
		if it.has("rounds"):
			old = it
	_check("смена: в оружии полный, старый в рюкзаке с тем же составом", String(r[0]) == "swap" and int(inv.equipment.primary.mag.rounds) == 30 and Gear.mag_layers(old) == [[STD, 6], [AP, 3]], str(old))

	# --- досыпать россыпью другим типом (своего сверху нет)
	_arm({"id": MAG, "ammo": STD, "rounds": 20}, [])
	inv.add(AP, 4)
	r = inv.reload_slot("primary", _me._ws_state("primary"))
	var wm: Dictionary = inv.equipment.primary.mag
	_check("досыпал другим типом — лёг сверху", String(r[0]) == "topup" and Gear.mag_layers(wm) == [[STD, 20], [AP, 4]] and inv.count(AP) == 0, str(wm))
	# хост принял расход: один выстрел — сверху бронебойный, осталось 20 + 3
	_me._ws.clear()
	_me.weapon_slot = ""
	_me._switch("primary", false)
	await get_tree().physics_frame
	var spec2: Dictionary = _me.spec()
	_me.fire_timer = 0.0
	_me._fire(spec2)
	_me._send_ws("primary")
	await get_tree().physics_frame
	wm = inv.equipment.primary.mag
	_check("хост: после выстрела слои 20 + 3, сверху тот же тип", Gear.mag_layers(wm) == [[STD, 20], [AP, 3]] and String(wm.ammo) == AP, str(wm))
	print("ammo_mix_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Чистые функции слоёв — без уровня.
func _pure() -> void:
	var mag: Dictionary = WeaponDb.make_mag(MAG, STD, 2)
	_check("один тип — слоёв в записи нет", not mag.has("mix") and Gear.mag_layers(mag) == [[STD, 2]] and not Gear.mag_mixed(mag), str(mag))
	Gear.mag_push(mag, AP, 2)
	Gear.mag_push(mag, AP, 1)
	Gear.mag_push(mag, STD, 1)
	_check("слои снизу вверх, соседние одного типа сливаются", Gear.mag_layers(mag) == [[STD, 2], [AP, 3], [STD, 1]] and int(mag.rounds) == 6 and String(mag.ammo) == STD, str(mag))
	var popped: Array[String] = []
	for i in range(4):
		popped.append(Gear.mag_pop(mag))
	_check("снимается сверху", popped == [STD, AP, AP, AP] and Gear.mag_layers(mag) == [[STD, 2]] and not mag.has("mix"), "%s %s" % [str(popped), str(mag)])
	# выстрелы уменьшают только счёт: лишнее сверху отбрасывается при чтении
	var shot: Dictionary = {"id": MAG, "ammo": AP, "rounds": 3, "mix": [[STD, 2], [AP, 3]]}
	_check("счёт меньше слоёв — верх отброшен", Gear.mag_layers(shot) == [[STD, 2], [AP, 1]] and Gear.mag_top(shot) == AP, str(Gear.mag_layers(shot)))
	shot.rounds = 2
	_check("дострелял верхний тип — сверху нижний", Gear.mag_top(shot) == STD and not Gear.mag_mixed(shot), Gear.mag_top(shot))
	# после сохранения в JSON числа — дробные
	var saved: Dictionary = JSON.parse_string(JSON.stringify({"id": MAG, "n": 1, "ammo": AP, "rounds": 5, "mix": [[STD, 2], [AP, 3]]}))
	_check("после JSON слои читаются", Gear.mag_layers(saved) == [[STD, 2], [AP, 3]], str(Gear.mag_layers(saved)))
	_check("патрон другого типа подходит к непустому магазину, чужой калибр — нет", MagOps.ammo_fits(saved, STD) and MagOps.ammo_fits(saved, AP) and not MagOps.ammo_fits(saved, "ammo_919_fmj"), "")
	_check("вес и цена — по слоям", ItemDb.entry_weight(saved) > ItemDb.weight(MAG) and absf(ItemDb.entry_weight(saved) - (ItemDb.weight(MAG) + 2.0 * ItemDb.weight(STD) + 3.0 * ItemDb.weight(AP))) < 0.0001, str(ItemDb.entry_weight(saved)))


## Игрок со снаряжением: ВЕРАС с записью магазина mag, в рюкзаке — полные магазины spare.
func _arm(mag: Dictionary, spare: Array) -> void:
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry["mag"] = mag
	_me.loadout_mode = true
	_me.cancel_weapon_action()
	_me.inventory.equipment = {"primary": entry}
	_me.inventory.items = []
	for n: int in spare:
		_me.inventory.add_entry(WeaponDb.make_mag(MAG, STD, n))
	_me.weapon_slot = ""
	_me._ws.clear()
	_me._switch("primary", false)
	_me.weapon_obstruction = 0.0


func _mag(list: Array) -> Dictionary:
	for it: Dictionary in list:
		if it.has("rounds"):
			return it
	return {}


func _mag_idx(list: Array) -> int:
	for i in range(list.size()):
		if (list[i] as Dictionary).has("rounds"):
			return i
	return -1


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["[ok]  " if ok else "[FAIL]", label, "  (" + detail + ")" if detail != "" and not ok else ""])
