class_name Inventory
extends Node
## Рюкзак и снаряжение игрока в рейде. items — список {"id", "n"[, "dur"], "x", "y", "r"} в сетке
## backpack_grid() — рюкзака или карманов (см. ItemDb: запись — стопка на своём месте); equipment — слот ("primary", "secondary", "armor", "helmet") ->
## экземпляр предмета. Меняет только хост (авторитет узла — 1, как у Health); у всех peer
## реплицируется. Списки всегда переприсваиваются копией — синхронизатор сравнивает значения.

## Слота «Разгрузка» больше нет (gear_v2, 2026-10-24): подсумки с магазинами висят на броне или поясе в слоте брони.
const SLOTS := ["primary", "secondary", "sidearm", "launcher", "armor", "helmet", "ears", "eyes", "backpack"]
const SLOT_NAMES := {"primary": "Оружие 1", "secondary": "Оружие 2", "sidearm": "Пистолет", "launcher": "Ракетница", "armor": "Броня",
	"helmet": "Шлем", "ears": "Уши", "eyes": "Глаза", "backpack": "Рюкзак"}

var items: Array = []
## Ревизия слота не забывается, когда оружие вынуто: поздний пакет не попадёт в новый экземпляр.
var _weapon_slot_revisions: Dictionary = {}
var _weapon_generation_seq: int = 0
var equipment: Dictionary = {}:
	set(value):
		equipment = _prepare_equipment(value)
## Что не влезло в карманы, когда бросил рюкзак (выпадает вместе с ним; забирает Raid).
var spilled: Array = []
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
## Своя половина буфера обмена с напарником (Raid.trades): что отдаёшь. Сделку ведёт хост; обмен
## сорвался — возвращается в рюкзак, смерть — в тело.
var trade: Array = []


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
		for prop in [".:items", ".:equipment", ".:loadout_ready", ".:pocket", ".:pocket_grid", ".:buffer", ".:trade"]:
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
	return ItemDb.room_in(items, ItemDb.make(id, 1 << 20), backpack_grid())


## Кладёт до n штук id; возвращает, сколько положил (хост).
func add(id: String, n: int) -> int:
	return add_entry(ItemDb.make(id, n))


## Кладёт экземпляр (с прочностью и т.п.); возвращает, сколько штук влезло (хост).
func add_entry(entry: Dictionary) -> int:
	var list := items.duplicate(true)
	var k := ItemDb.add_to(list, entry, backpack_grid())
	if k > 0:
		items = list
	return k


## Сетки по имени: "backpack" (items), "pocket", "buffer"; у надетой разгрузки — "rig" (подсумки) и
## "dump" (сумка сброса пустых магазинов): лежат внутри записи снаряжения, принимают только магазины.
func list_of(role: String) -> Array:
	match role:
		"pocket":
			return pocket
		"buffer":
			return buffer
		"trade":
			return trade
		"rig", "dump":
			return ItemDb.rig_list(equipment, role)
	return items


func grid_of(role: String) -> Vector2i:
	match role:
		"pocket":
			return pocket_grid
		"buffer":
			return Balance.BUFFER_GRID
		"trade":
			return Vector2i(int(Balance.TRADE.grid[0]), int(Balance.TRADE.grid[1]))
		"rig", "dump":
			return ItemDb.rig_grid(equipment, role)
	return backpack_grid()


## Сетка рюкзака по надетому (без рюкзака — карманы).
func backpack_grid() -> Vector2i:
	return ItemDb.bag_grid(equipment)


## Ячеек в рюкзаке (без рюкзака — в карманах).
func capacity() -> int:
	var g := backpack_grid()
	return g.x * g.y


## Переприсвоить сетку (копией — синхронизатор сравнивает значения).
func _set_list(role: String, list: Array) -> void:
	match role:
		"pocket":
			pocket = list
		"buffer":
			buffer = list
		"trade":
			trade = list
		"rig", "dump":
			if not ItemDb.rig_entry(equipment).is_empty():
				var eq := equipment.duplicate(true)
				(eq.armor as Dictionary)["dump" if role == "dump" else "mags"] = list
				equipment = eq
		_:
			items = list


## Кладёт экземпляр куда влезет в сетку into ("backpack" / "pocket" / "buffer"); сколько положил (хост).
func add_entry_in(into: String, entry: Dictionary) -> int:
	var grid := grid_of(into)
	if grid == Vector2i.ZERO or not ItemDb.grid_accepts(into, entry):
		return 0
	var list := list_of(into).duplicate(true)
	var k := ItemDb.rig_add(equipment, list, entry) if into == "rig" else ItemDb.add_to(list, entry, grid)
	if k > 0:
		_set_list(into, list)
	return k


## Кладёт экземпляр в конкретное место сетки into ("backpack" / "pocket" / "buffer"); сколько
## положил (хост).
func put_at(entry: Dictionary, x: int, y: int, r: bool, into: String = "backpack") -> int:
	var grid := grid_of(into)
	if grid == Vector2i.ZERO or not ItemDb.grid_accepts(into, entry):
		return 0
	# в подсумки — только магазин своего вида (пистолетный / автоматный / большой)
	if into == "rig" and not ItemDb.rig_accepts_at(equipment, entry, x, y, r):
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
		var k := ItemDb.add_to(list, one, backpack_grid())
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
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(from, r[1], pocket_grid if src == "pocket" else backpack_grid()) == 0:
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
	if ItemDb.add_to(list, r[1], backpack_grid()) < int((r[1] as Dictionary).n):
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
	if ItemDb.add_to(bp, got, backpack_grid()) < int(got.n):
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
	if String(e.get("id", "")) == "signal_launcher":
		# Signals and their expensive payloads are spent only by the host's shot
		# transaction. An old state echo cannot put a fired round back in the gun.
		return
	# Хост считает ресурс по подтверждённому расходу патронов, не принимает чужой процент.
	var shot_count: int = int(e.get("_condition_shots", 0))
	var requested_shots: int = int(st.get("shots", shot_count))
	var spent: int = maxi(0, Gear.total_rounds(e) - (clampi(int(st.get("rounds", mag.get("rounds", 0))), 0, WeaponDb.capacity(e)) + int(st.get("chamber", e.get("chamber", 0)))))
	var shots: int = requested_shots - shot_count
	if shots < 0 or shots > spent or (shots > 0 and WeaponCondition.broken(e)):
		return
	WeaponCondition.wear_shots(e, shots)
	if shots > 0 or e.has("_condition_shots"):
		e["_condition_shots"] = requested_shots
	if not mag.is_empty():
		mag.rounds = clampi(int(st.get("rounds", mag.get("rounds", 0))), 0, WeaponDb.capacity(e))
		# патроны вперемешку: отстрелянное снято сверху — тип верхнего и слои по новому счёту
		Gear.mag_apply(mag, Gear.mag_layers(mag))
		e["mag"] = mag
	if int(WeaponDb.weapon(String(e.get("id", ""))).get("chamber_capacity", 0)) > 0:
		e["chamber"] = clampi(int(st.get("chamber", e.get("chamber", 0))), 0, 1)
		e["chamber_ammo"] = String(st.get("chamber_ammo", e.get("chamber_ammo", ""))) if int(e.chamber) > 0 else ""
	e["sight"] = String(st.get("sight", e.get("sight", "primary")))
	e["sight"] = WeaponStats.active_sight(e)
	if st.get("optic_zoom") is Dictionary:
		WeaponStats.apply_scope_zooms(e, st.optic_zoom)
	# пристрелка: щелчки барабанчиков крутит владелец (ошибку нуля он не видит и не меняет)
	if st.get("zero_c") is Array and (st.zero_c as Array).size() == 2:
		Gear.set_zero_clicks(e, Vector2i(int(st.zero_c[0]), int(st.zero_c[1])))
	# режим огня (переводчик) — только из режимов этого ствола
	var mode: String = String(st.get("fire_mode", ""))
	if mode != "" and WeaponDb.fire_modes(String(e.get("id", ""))).size() > 1:
		e["fire_mode"] = WeaponDb.fire_mode_of(String(e.get("id", "")), mode)
	# пылезащитная шторка откинута рамой (Player.dust_cover_open) — сама не закрывается
	if bool(st.get("cover_open", false)):
		e["cover_open"] = true
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
	if String((equipment[slot] as Dictionary).get("id", "")) == "signal_launcher":
		return _reload_signal(slot, st)
	apply_weapon_state(slot, st)
	if not equipment.has(slot):
		return ["", {}]
	if st.get("pick") is Dictionary:
		# магазин выбрал сам игрок (бросил на оружие в окне рюкзака): меняется именно он; старому нет места — под ноги
		var pick: Dictionary = st.pick
		var swapped: Array = _mag_swap(slot, String(pick.get("role", "")), int(pick.get("idx", -1)), String(pick.get("id", "")), true)
		return ["swap" if String(swapped[0]) == "" else "", swapped[1]]
	var eq := equipment.duplicate(true)
	var list := items.duplicate(true)
	var r: Array = []
	# магазин — из подсумков разгрузки (под рукой); нет там — из рюкзака, как раньше
	var pouches: Array = ItemDb.rig_list(eq, "rig")
	if ItemDb.rig_grid(eq, "rig") != Vector2i.ZERO:
		r = Gear.reload_weapon(eq[slot], pouches, ItemDb.rig_grid(eq, "rig"), true)
	if r.is_empty() or String(r[2]) != "swap":
		r = Gear.reload_weapon(eq[slot], list, backpack_grid(), true)
	if String(r[2]) == "":
		return ["", {}]
	eq[slot] = r[0]
	# старый магазин: сумка сброса → рюкзак → свободный подсумок → на землю
	var old: Dictionary = r[1]
	if not old.is_empty():
		for key in ["x", "y", "r"]:
			old.erase(key)
		if ItemDb.rig_grid(eq, "dump") != Vector2i.ZERO and ItemDb.add_to(ItemDb.rig_list(eq, "dump"), old, ItemDb.rig_grid(eq, "dump")) > 0:
			old = {}
		elif ItemDb.add_to(list, old, ItemDb.bag_grid(eq)) > 0:
			old = {}
		elif ItemDb.rig_add(eq, pouches, old) > 0:
			old = {}
	items = list
	equipment = eq
	return [String(r[2]), old]


## Магазин из сетки role[idx] — в оружие в слоте slot, в руках владельца (хост, по окончании движения рук): сначала —
## состояние владельца, потом смена (Gear.fit) и досыл, если патронник пуст. Старый магазин — туда же, откуда взят
## новый (карман, буфер), иначе как у перезарядки: сумка сброса → рюкзак → свободный подсумок. "" — сделано.
func hand_mag_insert(slot: String, st: Dictionary, role: String, idx: int, mag_id: String) -> String:
	if not equipment.has(slot) or not _weapon_state_matches(equipment[slot], st):
		return "Оружие уже изменилось"
	apply_weapon_state(slot, st)
	return String(_mag_swap(slot, role, idx, mag_id, false)[0])


## Смена магазина оружия в слоте на магазин role[idx] (состояние владельца уже применено): [ошибка, выпавшее].
## spill_ok — старому магазину нет места: он выпадает (вернётся вторым значением), иначе — отказ без перемен.
func _mag_swap(slot: String, role: String, idx: int, mag_id: String, spill_ok: bool) -> Array:
	if not equipment.has(slot):
		return ["Оружия уже нет", {}]
	if not role in ["backpack", "pocket", "buffer", "rig", "dump"]:
		return ["Отсюда магазин в оружие не вставить", {}]
	var eq := equipment.duplicate(true)
	var bag: Array = items.duplicate(true)
	var side: Array = pocket.duplicate(true) if role == "pocket" else (buffer.duplicate(true) if role == "buffer" else [])
	var from: Array = bag if role == "backpack" else (ItemDb.rig_list(eq, role) if role in ["rig", "dump"] else side)
	if idx < 0 or idx >= from.size() or String((from[idx] as Dictionary).get("id", "")) != mag_id or not (from[idx] as Dictionary).has("rounds"):
		return ["Магазина уже нет на месте", {}]
	var r: Array = Gear.fit(eq[slot], from[idx], "")
	if String(r[2]) != "":
		return ["Не встаёт: " + String(r[2]), {}]
	ItemDb.remove_at(from, idx, 1)
	var fitted: Dictionary = r[0]
	Gear.chamber_round(fitted)
	eq[slot] = fitted
	var old: Dictionary = r[1]
	if not old.is_empty():
		for key: String in ["x", "y", "r"]:
			old.erase(key)
		var placed: bool = role in ["pocket", "buffer"] and ItemDb.add_to(side, old, grid_of(role)) > 0
		if not placed and ItemDb.rig_grid(eq, "dump") != Vector2i.ZERO:
			placed = ItemDb.add_to(ItemDb.rig_list(eq, "dump"), old, ItemDb.rig_grid(eq, "dump")) > 0
		if not placed:
			placed = ItemDb.add_to(bag, old, ItemDb.bag_grid(eq)) > 0
		if not placed and ItemDb.rig_grid(eq, "rig") != Vector2i.ZERO:
			placed = ItemDb.rig_add(eq, ItemDb.rig_list(eq, "rig"), old) > 0
		if placed:
			old = {}
		elif not spill_ok:
			return ["Некуда положить старый магазин", {}]
	items = bag
	if role == "pocket":
		pocket = side
	elif role == "buffer":
		buffer = side
	equipment = eq
	return ["", old]


## One cartridge, committed at the end of the hand animation. A live round is
## returned before replacing its type; failure leaves both inventories intact.
func _reload_signal(slot: String, state: Dictionary) -> Array:
	var aid: String = String(state.get("reload_ammo", "flare"))
	if not WeaponDb.ammo_fits("signal_launcher", aid) or not has(aid):
		return ["", {}]
	var entry: Dictionary = (equipment[slot] as Dictionary).duplicate(true)
	var mag: Dictionary = entry.get("mag", {})
	if int(mag.get("rounds", 0)) > 0 and Gear.mag_top(mag) == aid:
		return ["", {}]
	var list: Array = items.duplicate(true)
	var found: int = -1
	for index: int in range(list.size()):
		if String((list[index] as Dictionary).id) == aid and int((list[index] as Dictionary).n) > 0:
			found = index
			break
	if found < 0:
		return ["", {}]
	ItemDb.remove_at(list, found, 1)
	if int(mag.get("rounds", 0)) > 0:
		var old := {"id": Gear.mag_top(mag), "n": 1}
		if ItemDb.add_to(list, old, backpack_grid()) != 1:
			return ["", {}]
	entry["mag"] = {"id": "", "ammo": aid, "rounds": 1}
	entry["signal_spent"] = false
	Gear._bump(entry)
	var eq: Dictionary = equipment.duplicate(true)
	eq[slot] = entry
	items = list
	equipment = eq
	return ["signal", {}]


## Есть ли в подсумках разгрузки магазин к оружию slot (перезарядка из них — быстрая).
func rig_has_mag(slot: String) -> bool:
	var e: Dictionary = equipment.get(slot, {})
	if e.is_empty():
		return false
	var out: bool = e.get("mag") is Dictionary and String((e.mag as Dictionary).get("id", "")) == ""
	for it: Dictionary in list_of("rig"):
		if it.has("rounds") and WeaponDb.mag_fits(String(e.id), String(it.id)) and (int(it.get("rounds", 0)) > 0 or out):
			return true
	return false


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
	for slot in ItemDb.WEAPON_SLOTS:
		if eq.has(slot):
			extra.append(eq[slot])
	# магазины в подсумках разгрузки тоже снаряжаются
	var pouched: Array = ItemDb.rig_list(eq, "rig")
	var used := Gear.load_mags(list, extra + pouched)
	if used > 0:
		for e in extra:
			Gear._bump(e)
	# подсумки пусты — снаряжённые магазины к своим стволам переезжают из рюкзака в них сами
	var moved := false
	var rg := ItemDb.rig_grid(eq, "rig")
	if rg != Vector2i.ZERO and pouched.is_empty():
		var i := 0
		while i < list.size():
			var it: Dictionary = list[i]
			var fits := false
			for w in extra:
				fits = fits or WeaponDb.mag_fits(String((w as Dictionary).id), String(it.id))
			if it.has("rounds") and int(it.get("rounds", 0)) > 0 and fits:
				var one: Dictionary = it.duplicate(true)
				for key in ["x", "y", "r"]:
					one.erase(key)
				if ItemDb.rig_add(eq, pouched, one) > 0:
					list.remove_at(i)
					moved = true
					continue
			i += 1
	if used > 0 or moved:
		items = list
		equipment = eq


## Перенос между рюкзаком, карманом и буфером (или внутри одного) в клетку (x, y) (хост).
func move_between(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> bool:
	if src == dst:
		var same := list_of(src).duplicate(true)
		if src == "rig" and idx >= 0 and idx < same.size() and not ItemDb.rig_accepts_at(equipment, same[idx], x, y, r):
			return false
		if not ItemDb.move_in(same, grid_of(src), idx, x, y, r):
			return false
		_set_list(src, same)
		return true
	var from: Array = list_of(src)
	if idx < 0 or idx >= from.size() or grid_of(dst) == Vector2i.ZERO or not ItemDb.grid_accepts(dst, from[idx]):
		return false
	if PhoneGear.personal(from[idx]):
		return false
	# клетка не задана (x < 0) — куда влезет
	if x < 0:
		var one: Dictionary = (from[idx] as Dictionary).duplicate(true)
		for key in ["x", "y", "r"]:
			one.erase(key)
		var dl := list_of(dst).duplicate(true)
		var k2 := ItemDb.rig_add(equipment, dl, one) if dst == "rig" else ItemDb.add_to(dl, one, grid_of(dst))
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
	if not ItemDb.move_in(list, backpack_grid(), idx, x, y, r):
		return false
	items = list
	return true


## Забирает до n штук id (патроны, лекарства); возвращает, сколько забрал (хост).
func remove(id: String, n: int) -> int:
	if id == PhoneGear.ID:
		return 0
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
	if idx >= 0 and idx < items.size() and PhoneGear.personal(items[idx]):
		return {}
	var list := items.duplicate(true)
	var out := ItemDb.remove_at(list, idx, n)
	if not out.is_empty():
		items = list
	return out


## Всё содержимое наружу (смерть — рюкзак и снаряжение в тело), пусто (хост).
func take_all() -> Array:
	var all := PhoneGear.without_phone(items + buffer + trade)
	buffer = []
	trade = []
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
	# подсумок — на броню (есть свободные места), сам в слот не встаёт
	if ItemDb.pouch_cost(id) > 0.0:
		var eq_p := equipment.duplicate(true)
		if eq_p.has("armor") and ItemDb.attach_pouch(eq_p.armor as Dictionary, id):
			var lst := items.duplicate(true)
			ItemDb.remove_at(lst, idx, 1)
			items = lst
			equipment = eq_p
		return {}
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
	if not old.is_empty() and ItemDb.add_to(list, old, backpack_grid()) == 0:
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
	if slot.begins_with("pouch:"):
		return _pouch_off(int(slot.trim_prefix("pouch:")), x, y, r)
	if not equipment.has(slot):
		return false
	# рюкзак в рейде не снять «внутрь себя» — только бросить (выбросить из слота)
	if slot == "backpack":
		return false
	var list := items.duplicate(true)
	var e: Dictionary = (equipment[slot] as Dictionary).duplicate(true)
	var k := ItemDb.put_at(list, e, backpack_grid(), x, y, r) if x >= 0 else ItemDb.add_to(list, e, backpack_grid())
	if k <= 0:
		return false
	var eq := equipment.duplicate(true)
	eq.erase(slot)
	items = list
	equipment = eq
	return true


## Снять подсумок с полуслота at в рюкзак (в клетку x, y; x < 0 — куда влезет); магазины без подсумка
## своего вида — туда же, не влезли — в spilled (Raid бросает под ноги) (хост).
func _pouch_off(at: int, x: int, y: int, r: bool) -> bool:
	var eq := equipment.duplicate(true)
	var i := ItemDb.pouch_index_at(ItemDb.rig_entry(eq), at)
	if i < 0:
		return false
	var list := items.duplicate(true)
	var out := ItemDb.detach_pouch(eq, i)
	var pouch: Dictionary = out.pop_front()
	var k := ItemDb.put_at(list, pouch, backpack_grid(), x, y, r) if x >= 0 else ItemDb.add_to(list, pouch, backpack_grid())
	if k <= 0:
		return false
	spilled = []
	for m: Dictionary in out:
		if ItemDb.add_to(list, m, backpack_grid()) == 0:
			spilled.append(m)
	items = list
	equipment = eq
	return true


## Переставить подсумок на броне с полуслота from_at на to_at; не влезшие магазины — в рюкзак, дальше —
## spilled (хост).
func move_pouch(from_at: int, to_at: int) -> bool:
	var eq := equipment.duplicate(true)
	var res := ItemDb.move_pouch(eq, from_at, to_at)
	if not bool(res[0]):
		return false
	var list := items.duplicate(true)
	spilled = []
	for m: Dictionary in res[1]:
		if ItemDb.add_to(list, m, backpack_grid()) == 0:
			spilled.append(m)
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
		if slot == "backpack":
			# бросил рюкзак: в карманы — что влезло, остальное выпадает вместе с ним
			var rf := ItemDb.refit(PhoneGear.phone_first(items), backpack_grid())
			items = rf[0]
			spilled = rf[1]
		return e
	var list: Array = list_of(where).duplicate(true)
	if idx < 0 or idx >= list.size():
		return {}
	if PhoneGear.personal(list[idx]):
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
