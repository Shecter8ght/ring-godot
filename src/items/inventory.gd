class_name Inventory
extends Node
## Рюкзак и снаряжение игрока в рейде. items — список {"id", "n"[, "dur"], "x", "y", "r"} в сетке
## Balance.BACKPACK_GRID (см. ItemDb: запись — стопка на своём месте); equipment — слот ("primary", "secondary", "armor", "helmet") ->
## экземпляр предмета. Меняет только хост (авторитет узла — 1, как у Health); у всех peer
## реплицируется. Списки всегда переприсваиваются копией — синхронизатор сравнивает значения.

const SLOTS := ["primary", "secondary", "armor", "helmet", "ears", "eyes"]
const SLOT_NAMES := {"primary": "Основное", "secondary": "Пистолет", "armor": "Броня", "helmet": "Шлем", "ears": "Уши", "eyes": "Глаза"}

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


## Обвес из рюкзака / кармана (src, запись idx) — на оружие в слоте weapon_slot, в точку mount
## ("" — первая подходящая); снятый с этой точки — туда, откуда взят новый (хост). "" — ошибок нет.
func install_mod(weapon_slot: String, src: String, idx: int, mount: String = "") -> String:
	var from: Array = (pocket if src == "pocket" else items).duplicate(true)
	if not equipment.has(weapon_slot) or idx < 0 or idx >= from.size():
		return "нечего ставить"
	var r := Gear.fit(equipment[weapon_slot], from[idx], mount)
	if String(r[2]) != "":
		return String(r[2])
	ItemDb.remove_at(from, idx, 1)
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(from, r[1], pocket_grid if src == "pocket" else Balance.BACKPACK_GRID) == 0:
		return "некуда положить снятое"
	var eq := equipment.duplicate(true)
	eq[weapon_slot] = r[0]
	if src == "pocket":
		pocket = from
	else:
		items = from
	equipment = eq
	return ""


## Снять часть (обвес "mod:<точка>", плиту "plate:<сторона>", магазин "mag") с предмета в слоте
## снаряжения — в рюкзак (хост). false — места нет.
func strip_equipped(slot: String, part: String) -> bool:
	if not equipment.has(slot):
		return false
	var r := Gear.strip(equipment[slot], part)
	if (r[1] as Dictionary).is_empty():
		return false
	var list := items.duplicate(true)
	if ItemDb.add_to(list, r[1], Balance.BACKPACK_GRID) < int((r[1] as Dictionary).n):
		return false
	var eq := equipment.duplicate(true)
	eq[slot] = r[0]
	items = list
	equipment = eq
	return true


## Совместимость со старым вызовом (слот обвеса = точка крепления).
func remove_mod(weapon_slot: String, mount: String) -> bool:
	return strip_equipped(weapon_slot, "mod:" + mount)


## Снять часть с предмета в рюкзаке items[idx] — в рюкзак же (хост).
func strip_item(idx: int, part: String) -> bool:
	if idx < 0 or idx >= items.size():
		return false
	var list := items.duplicate(true)
	var r := Gear.strip(list[idx], part)
	if (r[1] as Dictionary).is_empty():
		return false
	var keep: Dictionary = r[0]
	for k in ["x", "y", "r"]:
		if (list[idx] as Dictionary).has(k):
			keep[k] = list[idx][k]
	list[idx] = keep
	if ItemDb.add_to(list, r[1], Balance.BACKPACK_GRID) < int((r[1] as Dictionary).n):
		return false
	items = list
	return true


## Состояние оружия от владельца (патроны в магазине, износ, прицел, фонари/лазеры) — в запись
## слота (хост). Ревизию не трогает: это эхо владельца, а не новость для него.
func apply_weapon_state(slot: String, st: Dictionary) -> void:
	if not equipment.has(slot):
		return
	var e: Dictionary = (equipment[slot] as Dictionary).duplicate(true)
	if int(st.get("rev", -1)) != int(e.get("rev", 0)):
		# владелец ещё не видел последнюю перемену (сменили магазин / обвес) — его состояние устарело
		return
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not mag.is_empty():
		mag.rounds = clampi(int(st.get("rounds", mag.get("rounds", 0))), 0, WeaponDb.capacity(e))
		e["mag"] = mag
	e["dur"] = clampf(float(st.get("dur", e.get("dur", 100.0))), 0.0, 100.0)
	e["sight"] = String(st.get("sight", e.get("sight", "primary")))
	var mods: Dictionary = e.get("mods", {})
	var tac: Dictionary = st.get("tac", {})
	for m in mods:
		if not (mods[m] is Dictionary):
			mods[m] = {"id": String(mods[m])}
		if tac.has(m):
			(mods[m] as Dictionary)["light"] = bool((tac[m] as Dictionary).get("light", false))
			(mods[m] as Dictionary)["laser"] = bool((tac[m] as Dictionary).get("laser", false))
	var eq := equipment.duplicate(true)
	eq[slot] = e
	equipment = eq


## Перезарядка оружия в слоте (хост): сначала — состояние владельца, потом смена магазина из
## рюкзака или досыпка россыпью (Gear.reload_weapon). Возвращает вид ("swap"/"topup") и выпавшее.
func reload_slot(slot: String, st: Dictionary) -> Array:
	apply_weapon_state(slot, st)
	if not equipment.has(slot):
		return ["", {}]
	var list := items.duplicate(true)
	var r := Gear.reload_weapon(equipment[slot], list, Balance.BACKPACK_GRID)
	if String(r[2]) == "":
		return ["", {}]
	items = list
	var eq := equipment.duplicate(true)
	eq[slot] = r[0]
	equipment = eq
	return [String(r[2]), r[1]]


## Начало рейда (хост): пустые магазины в рюкзаке и оружие в слотах снарядить россыпью.
func prepare_mags() -> void:
	var list := items.duplicate(true)
	var eq := equipment.duplicate(true)
	var extra: Array = []
	for slot in ["primary", "secondary"]:
		if eq.has(slot):
			extra.append(eq[slot])
	if Gear.load_mags(list, extra) > 0:
		for e in extra:
			Gear._bump(e)
		items = list
		equipment = eq


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


## Разложить рюкзак или карман по порядку (хост). false — не вышло.
func sort_grid(where: String = "backpack") -> bool:
	var pk := where == "pocket"
	var grid := pocket_grid if pk else Balance.BACKPACK_GRID
	var src: Array = pocket if pk else items
	if grid == Vector2i.ZERO or src.is_empty():
		return false
	var out := ItemDb.arranged(src, grid)
	if out.is_empty():
		return false
	if pk:
		pocket = out
	else:
		items = out
	return true


## Снять из слота в рюкзак: в клетку x, y (перетащили в сетку) или куда влезет. Не влезло — false.
func unequip(slot: String, x: int = -1, y: int = -1, r: bool = false) -> bool:
	if not equipment.has(slot):
		return false
	var list := items.duplicate(true)
	var e: Dictionary = (equipment[slot] as Dictionary).duplicate(true)
	var k := ItemDb.put_at(list, e, Balance.BACKPACK_GRID, x, y, r) if x >= 0 else ItemDb.add_to(list, e, Balance.BACKPACK_GRID)
	if k <= 0:
		return false
	var eq := equipment.duplicate(true)
	eq.erase(slot)
	items = list
	equipment = eq
	return true


## Вынуть запись целиком, со всем состоянием (выбросить): "backpack" / "pocket" — по индексу,
## "equip:<слот>" — из слота. Нет — пусто.
func take_entry(where: String, idx: int) -> Dictionary:
	if where.begins_with("equip:"):
		var slot := where.trim_prefix("equip:")
		if not equipment.has(slot):
			return {}
		var eq := equipment.duplicate(true)
		var e: Dictionary = eq[slot]
		eq.erase(slot)
		equipment = eq
		return e
	var list: Array = (pocket if where == "pocket" else items).duplicate(true)
	if idx < 0 or idx >= list.size():
		return {}
	var out: Dictionary = list[idx]
	list.remove_at(idx)
	for k in ["x", "y", "r"]:
		out.erase(k)
	if where == "pocket":
		pocket = list
	else:
		items = list
	return out


func slot_item(slot: String) -> String:
	return String((equipment.get(slot, {}) as Dictionary).get("id", ""))


## Какое оружие (id предмета) в слоте, "" — пусто.
func slot_weapon(slot: String) -> String:
	var id := slot_item(slot)
	return id if WeaponDb.is_weapon(id) else ""


## Попадание по снаряжению (хост, из Health): броня, плиты, шлем — Armor. forward — куда смотрит
## корпус. Возвращает [урон, насмерть?]; износ брони записывается в снаряжение.
func absorb(amount: float, zone: String, from: Vector3, at: Vector3, forward: Vector3, bullet: Dictionary, rng: RandomNumberGenerator) -> Array:
	var r := Armor.hit(equipment, amount, zone, from, at, forward, bullet, rng)
	if String(r.layer) != "":
		equipment = r.equipment
	return [float(r.damage), bool(r.lethal)]
