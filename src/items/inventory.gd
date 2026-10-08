class_name Inventory
extends Node
## Рюкзак и снаряжение игрока в рейде. items — список {"id", "n"[, "dur"], "x", "y", "r"} в сетке
## Balance.BACKPACK_GRID (см. ItemDb: запись — стопка на своём месте); equipment — слот ("primary", "secondary", "armor", "helmet") ->
## экземпляр предмета. Меняет только хост (авторитет узла — 1, как у Health); у всех peer
## реплицируется. Списки всегда переприсваиваются копией — синхронизатор сравнивает значения.

const SLOTS := ["primary", "secondary", "armor", "helmet", "ears", "eyes"]
const SLOT_NAMES := {"primary": "Оружие 1", "secondary": "Оружие 2", "armor": "Броня", "helmet": "Шлем", "ears": "Уши", "eyes": "Глаза"}

var items: Array = []
## Ревизия слота не забывается, когда оружие вынуто: поздний пакет не попадёт в новый экземпляр.
var _weapon_slot_revisions: Dictionary = {}
var _weapon_generation_seq: int = 0
var equipment: Dictionary = {}:
	set(value):
		equipment = _prepare_equipment(value)
## Последний слой, который принял пулю; нужен только для соответствующего звука попадания.
var last_armor_layer: String = ""
## Защищённый карман (модуль убежища): при смерти не выпадает — возвращается в профиль.
var pocket: Array = []
var pocket_grid: Vector2i = Vector2i.ZERO
## Хост выдал снаряжение из профиля (рейд из убежища) — владелец может заряжать магазины.
var loadout_ready: bool = false
## Буфер — сетка Balance.BUFFER_GRID посередине окна лута: переложить, разрядить магазин, снарядить
## отсюда. Живёт, только пока открыт ящик: закрыли окно — что осталось, пропадает (окно спросит);
## эвакуация — в рюкзак, смерть — в тело.
var buffer: Array = []


## Все пути экипировки, включая назначения из Raid/Profile, проходят через один барьер.
## Маркер сохраняется в копиях записи, но при новом помещении в слот выдаётся заново.
func _prepare_equipment(value: Dictionary) -> Dictionary:
	var next: Dictionary = value.duplicate(true)
	var can_author: bool = not Net.is_networked() or Net.scene_of(self) == "hideout" \
		or (is_inside_tree() and multiplayer.is_server())
	for raw_slot: Variant in equipment:
		var slot: String = String(raw_slot)
		var previous: Dictionary = equipment[raw_slot]
		if WeaponDb.is_weapon(String(previous.get("id", ""))):
			_weapon_slot_revisions[slot] = maxi(int(_weapon_slot_revisions.get(slot, -1)), int(previous.get("rev", 0)))
	for raw_slot: Variant in next:
		var slot: String = String(raw_slot)
		var entry: Dictionary = next[raw_slot]
		if not WeaponDb.is_weapon(String(entry.get("id", ""))):
			continue
		var revision: int = int(entry.get("rev", 0))
		var high_water: int = int(_weapon_slot_revisions.get(slot, -1))
		if can_author:
			var previous: Dictionary = equipment.get(slot, {})
			var generation: String = String(entry.get("_equip_generation", ""))
			var continuing: bool = generation != "" and generation == String(previous.get("_equip_generation", "")) \
				and String(entry.get("id", "")) == String(previous.get("id", "")) \
				and revision >= int(previous.get("rev", 0))
			if not continuing:
				# Первый снимок нового Inventory сохраняет ревизию из профиля. Повторное
				# помещение в использованный слот всегда старше всех его прежних запросов.
				revision = maxi(revision, high_water + 1)
				if high_water >= 0 or generation == "":
					_weapon_generation_seq += 1
					entry["_equip_generation"] = "%s:%s:%d" % [str(get_instance_id()), slot, _weapon_generation_seq]
			else:
				revision = maxi(revision, high_water)
			entry["rev"] = revision
		# Клиент принимает ревизию и маркер хоста без собственной перенумерации.
		_weapon_slot_revisions[slot] = maxi(high_water, revision)
	return next


func _weapon_state_matches(entry: Dictionary, state: Dictionary) -> bool:
	return int(state.get("rev", -1)) == int(entry.get("rev", 0)) \
		and (not state.has("id") or String(state.id) == String(entry.get("id", "")))


func _ready() -> void:
	# в убежище вещи — в профиле у каждого свой, рюкзак игрока по сети не нужен (хост слал бы
	# чужой пустой рюкзак новичку раньше, чем тот увидит его хозяина, — путь не находился)
	if Net.is_networked() and Net.scene_of(self) != "hideout":
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		for prop in [".:items", ".:equipment", ".:loadout_ready", ".:pocket", ".:pocket_grid", ".:buffer"]:
			var path := NodePath(prop)
			config.add_property(path)
			config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
		sync.replication_config = config
		sync.set_multiplayer_authority(get_multiplayer_authority())
		Net.scope_sync(self, sync)
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


## Сетки по имени: "backpack" (items), "pocket", "buffer".
func list_of(role: String) -> Array:
	match role:
		"pocket":
			return pocket
		"buffer":
			return buffer
	return items


func grid_of(role: String) -> Vector2i:
	match role:
		"pocket":
			return pocket_grid
		"buffer":
			return Balance.BUFFER_GRID
	return Balance.BACKPACK_GRID


## Переприсвоить сетку (копией — синхронизатор сравнивает значения).
func _set_list(role: String, list: Array) -> void:
	match role:
		"pocket":
			pocket = list
		"buffer":
			buffer = list
		_:
			items = list


## Кладёт экземпляр куда влезет в сетку into ("backpack" / "pocket" / "buffer"); сколько положил (хост).
func add_entry_in(into: String, entry: Dictionary) -> int:
	var grid := grid_of(into)
	if grid == Vector2i.ZERO:
		return 0
	var list := list_of(into).duplicate(true)
	var k := ItemDb.add_to(list, entry, grid)
	if k > 0:
		_set_list(into, list)
	return k


## Кладёт экземпляр в конкретное место сетки into ("backpack" / "pocket" / "buffer"); сколько
## положил (хост).
func put_at(entry: Dictionary, x: int, y: int, r: bool, into: String = "backpack") -> int:
	var grid := grid_of(into)
	if grid == Vector2i.ZERO:
		return 0
	var list := list_of(into).duplicate(true)
	var k := ItemDb.put_at(list, entry, grid, x, y, r)
	if k > 0:
		_set_list(into, list)
	return k


## Буфер — в рюкзак; что не влезло — вернуть (вызывающий бросает мешком) (хост).
func flush_buffer() -> Array:
	if buffer.is_empty():
		return []
	var list := items.duplicate(true)
	var left: Array = []
	for e in buffer:
		var one: Dictionary = (e as Dictionary).duplicate(true)
		for key in ["x", "y", "r"]:
			one.erase(key)
		var k := ItemDb.add_to(list, one, Balance.BACKPACK_GRID)
		if k < int(one.n):
			one.n = int(one.n) - k
			left.append(one)
	items = list
	buffer = []
	return left


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
	return strip_in("backpack", idx, part)


## Снять часть с предмета в сетке role (рюкзак, карман, буфер) — в ту же сетку, нет места — в рюкзак
## (хост).
func strip_in(role: String, idx: int, part: String) -> bool:
	var list := list_of(role).duplicate(true)
	if idx < 0 or idx >= list.size():
		return false
	var r := Gear.strip(list[idx], part)
	var got: Dictionary = r[1]
	if got.is_empty():
		return false
	list[idx] = r[0]
	if ItemDb.add_to(list, got, grid_of(role)) >= int(got.n):
		_set_list(role, list)
		return true
	if role == "backpack":
		return false
	var bp := items.duplicate(true)
	if ItemDb.add_to(bp, got, Balance.BACKPACK_GRID) < int(got.n):
		return false
	_set_list(role, list)
	items = bp
	return true


## Состояние оружия от владельца (патроны в магазине, износ, прицел, фонари/лазеры) — в запись
## слота (хост). Ревизию не трогает: это эхо владельца, а не новость для него.
func apply_weapon_state(slot: String, st: Dictionary) -> void:
	if not equipment.has(slot):
		return
	var e: Dictionary = Gear.normalize_chamber(equipment[slot])
	if not _weapon_state_matches(e, st):
		# владелец ещё не видел последнюю перемену (сменили магазин / обвес) — его состояние устарело
		return
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	if not mag.is_empty():
		mag.rounds = clampi(int(st.get("rounds", mag.get("rounds", 0))), 0, WeaponDb.capacity(e))
		e["mag"] = mag
	if int(WeaponDb.weapon(String(e.get("id", ""))).get("chamber_capacity", 0)) > 0:
		e["chamber"] = clampi(int(st.get("chamber", e.get("chamber", 0))), 0, 1)
		e["chamber_ammo"] = String(st.get("chamber_ammo", e.get("chamber_ammo", ""))) if int(e.chamber) > 0 else ""
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
	# Устаревший пакет не должен перезарядить уже заменённое оружие.
	if not equipment.has(slot) or not _weapon_state_matches(equipment[slot], st):
		return ["", {}]
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


## Быстрое действие глушителя — атомарно: на ошибке ни обвес, ни рюкзак не меняются.
## install задаёт намерение, поэтому повторный сетевой пакет не превратится в обратное действие.
func toggle_suppressor(slot: String, st: Dictionary, install: bool, expected_id: String) -> String:
	if not equipment.has(slot):
		return "Оружия нет"
	var before: Dictionary = equipment[slot]
	if String(before.get("id", "")) != expected_id or not _weapon_state_matches(before, st):
		return "Оружие уже изменилось"
	var mods: Dictionary = before.get("mods", {})
	var mounted: String = WeaponDb.mod_id(mods.get("muzzle", {}))
	var mounted_fx: Dictionary = WeaponDb.attachment(mounted).get("fx", {})
	if not install:
		if not bool(mounted_fx.get("suppressed", false)):
			return "Глушителя на оружии нет"
		if not strip_equipped(slot, "mod:muzzle"):
			return "В рюкзаке нет места для глушителя"
	else:
		if mounted != "":
			return "Дульная насадка уже установлена"
		var chosen: int = -1
		for idx: int in range(items.size()):
			var iid: String = String((items[idx] as Dictionary).get("id", ""))
			var fx: Dictionary = WeaponDb.attachment(iid).get("fx", {})
			if bool(fx.get("suppressed", false)) and WeaponDb.attach_block(before, "muzzle", iid) == "":
				chosen = idx
				break
		if chosen < 0:
			return "В рюкзаке нет подходящего глушителя"
		var error: String = install_mod(slot, "backpack", chosen, "muzzle")
		if error != "":
			return error
	# Перенос обвеса изменил ревизию; состояние патронов принимаем с исходной ревизии.
	var state: Dictionary = st.duplicate(true)
	state["rev"] = int((equipment[slot] as Dictionary).get("rev", 0))
	apply_weapon_state(slot, state)
	return ""


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


## Перенос между рюкзаком, карманом и буфером (или внутри одного) в клетку (x, y) (хост).
func move_between(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> bool:
	if src == dst:
		var same := list_of(src).duplicate(true)
		if not ItemDb.move_in(same, grid_of(src), idx, x, y, r):
			return false
		_set_list(src, same)
		return true
	var from: Array = list_of(src)
	if idx < 0 or idx >= from.size():
		return false
	# клетка не задана (x < 0) — куда влезет
	if x < 0:
		var one: Dictionary = (from[idx] as Dictionary).duplicate(true)
		for key in ["x", "y", "r"]:
			one.erase(key)
		var dl := list_of(dst).duplicate(true)
		var k2 := ItemDb.add_to(dl, one, grid_of(dst))
		if k2 <= 0:
			return false
		_set_list(dst, dl)
		var rest2 := list_of(src).duplicate(true)
		ItemDb.remove_at(rest2, idx, k2)
		_set_list(src, rest2)
		return true
	var k := put_at((from[idx] as Dictionary).duplicate(true), x, y, r, dst)
	if k <= 0:
		return false
	var rest := list_of(src).duplicate(true)
	ItemDb.remove_at(rest, idx, k)
	_set_list(src, rest)
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
	var all := items.duplicate(true) + buffer.duplicate(true)
	buffer = []
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
	var slot := ItemDb.pick_slot(id, equipment)
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
	var grid := grid_of(where)
	var src: Array = list_of(where)
	if grid == Vector2i.ZERO or src.is_empty():
		return false
	var out := ItemDb.arranged(src, grid)
	if out.is_empty():
		return false
	_set_list(where, out)
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
	var list: Array = list_of(where).duplicate(true)
	if idx < 0 or idx >= list.size():
		return {}
	var out: Dictionary = list[idx]
	list.remove_at(idx)
	for k in ["x", "y", "r"]:
		out.erase(k)
	_set_list(where, list)
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
	last_armor_layer = String(r.layer)
	if String(r.layer) != "":
		equipment = r.equipment
	return [float(r.damage), bool(r.lethal)]
