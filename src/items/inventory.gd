class_name Inventory
extends Node
## Рюкзак и снаряжение игрока в рейде. items — список {"id", "n"[, "dur"]}, вместимость —
## Balance.BACKPACK_CELLS ячеек; equipment — слот ("primary", "secondary", "armor", "helmet") ->
## экземпляр предмета. Меняет только хост (авторитет узла — 1, как у Health); у всех peer
## реплицируется. Списки всегда переприсваиваются копией — синхронизатор сравнивает значения.

const SLOTS := ["primary", "secondary", "armor", "helmet"]
const SLOT_NAMES := {"primary": "Основное", "secondary": "Пистолет", "armor": "Броня", "helmet": "Шлем"}

var items: Array = []
var equipment: Dictionary = {}
## Хост выдал снаряжение из профиля (рейд из убежища) — владелец может заряжать магазины.
var loadout_ready: bool = false


func _ready() -> void:
	if Net.is_networked():
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		for prop in [".:items", ".:equipment", ".:loadout_ready"]:
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
	return ItemDb.room_in(items, ItemDb.make(id, 1 << 20), Balance.BACKPACK_CELLS)


## Кладёт до n штук id; возвращает, сколько положил (хост).
func add(id: String, n: int) -> int:
	return add_entry(ItemDb.make(id, n))


## Кладёт экземпляр (с прочностью и т.п.); возвращает, сколько штук влезло (хост).
func add_entry(entry: Dictionary) -> int:
	var list := items.duplicate(true)
	var k := ItemDb.add_to(list, entry, Balance.BACKPACK_CELLS)
	if k > 0:
		items = list
	return k


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
	if not old.is_empty() and ItemDb.add_to(list, old, Balance.BACKPACK_CELLS) == 0:
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
func absorb(amount: float) -> float:
	var eq := equipment.duplicate(true)
	var taken := 0.0
	for slot in ["armor", "helmet"]:
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
