class_name Inventory
extends Node
## Рюкзак и снаряжение игрока в рейде. items — список {"id", "n"[, "dur"], "x", "y", "r"} в сетке
## Balance.BACKPACK_GRID (см. ItemDb: запись — стопка на своём месте); equipment — слот ("primary", "secondary", "armor", "helmet") ->
## экземпляр предмета. Меняет только хост (авторитет узла — 1, как у Health); у всех peer
## реплицируется. Списки всегда переприсваиваются копией — синхронизатор сравнивает значения.

const SLOTS := ["primary", "secondary", "armor", "helmet"]
const SLOT_NAMES := {"primary": "Основное", "secondary": "Пистолет", "armor": "Броня", "helmet": "Шлем"}

var items: Array = []
var equipment: Dictionary = {}
## Защищённый карман (модуль убежища): при смерти не выпадает — возвращается в профиль.
var pocket: Array = []
var pocket_grid: Vector2i = Vector2i.ZERO
## Хост выдал снаряжение из профиля (рейд из убежища) — владелец может заряжать магазины.
var loadout_ready: bool = false


func _ready() -> void:
	if Net.is_networked():
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		for prop in [".:items", ".:equipment", ".:loadout_ready", ".:pocket", ".:pocket_grid"]:
			var path := NodePath(prop)
			config.add_property(path)
			config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
		sync.replication_config = config
		sync.set_multiplayer_authority(get_multiplayer_authority())
		add_child(sync)


func cells_used() -> int:
	return ItemDb.cells_of(items)


## Ценность рюкзака и снаряжения.
func value() -> int:
	var v := ItemDb.value_of(items)
	for slot in equipment:
		v += ItemDb.entry_value(equipment[slot])
	return v


func has(id: String) -> bool:
	return count(id) > 0


func count(id: String) -> int:
	var c := 0
	for it in items:
		if String(it.id) == id:
			c += int(it.n)
	return c


## Сколько штук id влезет (с учётом неполной стопки).
func room_for(id: String) -> int:
	return ItemDb.room_in(items, ItemDb.make(id, 1 << 20), Balance.BACKPACK_GRID)


## Кладёт до n штук id; возвращает, сколько положил (хост).
func add(id: String, n: int) -> int:
	return add_entry(ItemDb.make(id, n))


## Кладёт экземпляр (с прочностью и т.п.); возвращает, сколько штук влезло (хост).
func add_entry(entry: Dictionary) -> int:
	var list := items.duplicate(true)
	var k := ItemDb.add_to(list, entry, Balance.BACKPACK_GRID)
	if k > 0:
		items = list
	return k


## Кладёт экземпляр в конкретное место сетки into ("backpack" / "pocket"); сколько положил (хост).
func put_at(entry: Dictionary, x: int, y: int, r: bool, into: String = "backpack") -> int:
	var grid := pocket_grid if into == "pocket" else Balance.BACKPACK_GRID
	if grid == Vector2i.ZERO:
		return 0
	var list := (pocket if into == "pocket" else items).duplicate(true)
	var k := ItemDb.put_at(list, entry, grid, x, y, r)
	if k > 0:
		if into == "pocket":
			pocket = list
		else:
			items = list
	return k


## Обвес из рюкзака / кармана (src, запись idx) — на оружие в слоте weapon_slot; старый из того
## же слота обвеса — туда, откуда взят новый (хост). false — не подходит или некуда деть старый.
func install_mod(weapon_slot: String, src: String, idx: int) -> bool:
	var from: Array = (pocket if src == "pocket" else items).duplicate(true)
	if not equipment.has(weapon_slot) or idx < 0 or idx >= from.size():
		return false
	var mod := String(from[idx].id)
	var weapon: Dictionary = (equipment[weapon_slot] as Dictionary).duplicate(true)
	if not ItemDb.mod_fits(mod, String(weapon.id)):
		return false
	var mslot := String(ItemDb.mod_spec(mod).slot)
	ItemDb.remove_at(from, idx, 1)
	var mods: Dictionary = weapon.get("mods", {}).duplicate()
	if mods.has(mslot):
		if ItemDb.add_to(from, ItemDb.make(String(mods[mslot]), 1), pocket_grid if src == "pocket" else Balance.BACKPACK_GRID) == 0:
			return false
	mods[mslot] = mod
	weapon["mods"] = mods
	var eq := equipment.duplicate(true)
	eq[weapon_slot] = weapon
	if src == "pocket":
		pocket = from
	else:
		items = from
	equipment = eq
	return true


## Снять обвес mod_slot с оружия weapon_slot — в рюкзак (хост). false — места нет.
func remove_mod(weapon_slot: String, mod_slot: String) -> bool:
	if not equipment.has(weapon_slot):
		return false
	var weapon: Dictionary = (equipment[weapon_slot] as Dictionary).duplicate(true)
	var mods: Dictionary = weapon.get("mods", {}).duplicate()
	if not mods.has(mod_slot):
		return false
	var list := items.duplicate(true)
	if ItemDb.add_to(list, ItemDb.make(String(mods[mod_slot]), 1), Balance.BACKPACK_GRID) == 0:
		return false
	mods.erase(mod_slot)
	weapon["mods"] = mods
	var eq := equipment.duplicate(true)
	eq[weapon_slot] = weapon
	items = list
	equipment = eq
	return true


## Перенос между рюкзаком и карманом (или внутри одного) в клетку (x, y) (хост).
func move_between(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> bool:
	if src == dst:
		if src == "pocket":
			var pl := pocket.duplicate(true)
			if not ItemDb.move_in(pl, pocket_grid, idx, x, y, r):
				return false
			pocket = pl
			return true
		return move(idx, x, y, r)
	var from: Array = pocket if src == "pocket" else items
	if idx < 0 or idx >= from.size():
		return false
	var k := put_at((from[idx] as Dictionary).duplicate(true), x, y, r, dst)
	if k <= 0:
		return false
	var rest := from.duplicate(true)
	ItemDb.remove_at(rest, idx, k)
	if src == "pocket":
		pocket = rest
	else:
		items = rest
	return true


## Передвинуть запись idx внутри рюкзака (хост).
func move(idx: int, x: int, y: int, r: bool) -> bool:
	var list := items.duplicate(true)
	if not ItemDb.move_in(list, Balance.BACKPACK_GRID, idx, x, y, r):
		return false
	items = list
	return true


## Забирает до n штук id (патроны, лекарства); возвращает, сколько забрал (хост).
func remove(id: String, n: int) -> int:
	var list := items.duplicate(true)
	var left := n
	var i := list.size() - 1
	while i >= 0 and left > 0:
		if String(list[i].id) == id:
			left -= int(ItemDb.remove_at(list, i, left).n)
		i -= 1
	if left < n:
		items = list
	return n - left


## Вынимает из items[idx] до n штук; возвращает вынутое (хост).
func remove_at(idx: int, n: int) -> Dictionary:
	var list := items.duplicate(true)
	var out := ItemDb.remove_at(list, idx, n)
	if not out.is_empty():
		items = list
	return out


## Всё содержимое наружу (смерть — рюкзак и снаряжение в тело), пусто (хост).
func take_all() -> Array:
	var all := items.duplicate(true)
	for slot in equipment:
		all.append((equipment[slot] as Dictionary).duplicate(true))
	items = []
	equipment = {}
	return all


## Надеть / взять в руки предмет из рюкзака: старый из слота — в рюкзак. Возвращает
## то, что не влезло обратно ({} — всё на местах), — его вызывающий бросает на пол (хост).
func equip_from_items(idx: int) -> Dictionary:
	if idx < 0 or idx >= items.size():
		return {}
	var id := String(items[idx].id)
	var slot := String(ItemDb.equip(id).get("slot", ""))
	if slot == "":
		return {}
	var list := items.duplicate(true)
	var entry := ItemDb.remove_at(list, idx, 1)
	if not entry.has("dur") and ItemDb.equip(id).has("durability"):
		entry.dur = float(ItemDb.equip(id).durability)
	var eq := equipment.duplicate(true)
	var old: Dictionary = eq.get(slot, {})
	eq[slot] = entry
	var spill := {}
	if not old.is_empty() and ItemDb.add_to(list, old, Balance.BACKPACK_GRID) == 0:
		spill = old
	items = list
	equipment = eq
	return spill


func slot_item(slot: String) -> String:
	return String((equipment.get(slot, {}) as Dictionary).get("id", ""))


## Какое оружие (id в Balance.WEAPONS) в слоте, "" — пусто.
func slot_weapon(slot: String) -> String:
	var id := slot_item(slot)
	return String(ItemDb.equip(id).get("weapon", "")) if id != "" else ""


## Патроны (id предмета) к оружию weapon_id из снаряжения.
func ammo_for(weapon_id: String) -> String:
	for slot in ["primary", "secondary"]:
		if slot_weapon(slot) == weapon_id:
			return String(ItemDb.equip(slot_item(slot)).get("ammo", ""))
	return ""


## Броня и шлем снимают часть урона, пока целы; износ — по снятому (хост, из Health).
func absorb(amount: float, zone: String = "") -> float:
	var eq := equipment.duplicate(true)
	var taken := 0.0
	# в голову — только шлем, в корпус — только броня; взрыв и неизвестно куда — оба
	var slots: Array = ["helmet"] if zone == "head" else (["armor"] if zone == "body" else ["armor", "helmet"])
	for slot in slots:
		var e: Dictionary = eq.get(slot, {})
		if e.is_empty() or float(e.get("dur", 0.0)) <= 0.0:
			continue
		var part := amount * float(ItemDb.equip(String(e.id)).get("protect", 0.0))
		part = minf(part, float(e.dur))
		e.dur = maxf(0.0, float(e.dur) - part)
		taken += part
	if taken > 0.0:
		equipment = eq
	return amount - taken
