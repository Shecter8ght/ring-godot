class_name Stickers
extends RefCounted
## Наклейки на оружии (решения владельца 2026-10-11): до Balance.STICKERS.max штук на стволе, клеятся на
## верстаке убежища на те же места, что гравировка; наклейка-предмет при этом тратится; снять можно, но
## снятая пропадает. Запись ствола: "stickers" — [{id, site, scale, n}]; n — зарубки наклейки «Счёт»:
## +1 за каждую эвакуацию с этим стволом в слоте оружия (до tally_max). Характеристик и цены не меняют.
## Видны у всех и от первого лица — едут вместе с гравировкой (WeaponMark.marks).

static func is_sticker(id: String) -> bool:
	return id in (Balance.STICKERS.ids as Array)


static func of(entry: Dictionary) -> Array:
	return entry.get("stickers", []) if entry.get("stickers") is Array else []


## Наклейки-предметы у игрока: [{where, idx, entry}].
static func owned() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for role: String in ["stash", "backpack", "pocket"]:
		var list: Array = Profile.list_of(role)
		for index: int in range(list.size()):
			if is_sticker(String(list[index].get("id", ""))):
				out.append({"where": role, "idx": index, "entry": list[index]})
	return out


## Почему на это место ствола клеить нельзя ("" — можно).
static func block(entry: Dictionary, site: String) -> String:
	if not WeaponDb.is_weapon(String(entry.get("id", ""))):
		return "Нужно оружие."
	if of(entry).size() >= int(Balance.STICKERS.max):
		return "На стволе уже %d наклейки — больше не помещается. Снимите одну." % int(Balance.STICKERS.max)
	if WeaponMark.position_spec(String(entry.id), site).is_empty():
		return "Выберите место на оружии."
	for st: Dictionary in of(entry):
		if String(st.get("site", "")) == site:
			return "На этом месте уже есть наклейка."
	var mark: Dictionary = entry.get("engraving", {})
	if not mark.is_empty() and String(mark.get("site", "right_1")) == site:
		return "На этом месте гравировка."
	return ""


## Наклеить: ствол (where, idx, uid — проверка, что он на месте), наклейка-предмет (src_where, src_idx,
## sticker_id). "" — наклеено, предмет потрачен.
static func apply(where: String, idx: int, uid: String, src_where: String, src_idx: int, sticker_id: String, site: String, scale: float) -> String:
	var entry: Dictionary = Profile._entry_at(where, idx)
	if not WeaponDb.is_weapon(String(entry.get("id", ""))) or String(entry.get("uid", "")) != uid:
		return "Оружие переместилось. Выберите его снова."
	var why: String = block(entry, site)
	if why != "":
		return why
	var src: Array = Profile.list_of(src_where)
	if src_idx < 0 or src_idx >= src.size() or String(src[src_idx].get("id", "")) != sticker_id or not is_sticker(sticker_id):
		return "Наклейка переместилась. Выберите её снова."
	var before_weapon: Dictionary = entry.duplicate(true)
	var before_src: Array = src.duplicate(true)
	var changed: Dictionary = entry.duplicate(true)
	var list: Array = of(changed).duplicate(true)
	list.append({"id": sticker_id, "site": site, "scale": scale, "n": 0})
	changed["stickers"] = list
	changed["rev"] = int(changed.get("rev", 0)) + 1
	ItemDb.remove_at(src, src_idx, 1)
	# ствол мог лежать в той же сетке ниже по списку — после списания стопки индекс сдвигается
	var at: int = idx
	if not where.begins_with("equip:") and where == src_where and src.size() < before_src.size() and src_idx < idx:
		at -= 1
	Profile._set_entry(where, at, changed)
	if not Profile.save():
		src.clear()
		src.append_array(before_src)
		Profile._set_entry(where, idx, before_weapon)
		return "Не удалось сохранить. Наклейка осталась у вас."
	return ""


## Снять наклейку номер n со ствола — она пропадает. "" — снята.
static func remove(where: String, idx: int, uid: String, n: int) -> String:
	var entry: Dictionary = Profile._entry_at(where, idx)
	if not WeaponDb.is_weapon(String(entry.get("id", ""))) or String(entry.get("uid", "")) != uid:
		return "Оружие переместилось. Выберите его снова."
	var list: Array = of(entry).duplicate(true)
	if n < 0 or n >= list.size():
		return "Этой наклейки на стволе уже нет."
	list.remove_at(n)
	var changed: Dictionary = entry.duplicate(true)
	if list.is_empty():
		changed.erase("stickers")
	else:
		changed["stickers"] = list
	changed["rev"] = int(changed.get("rev", 0)) + 1
	Profile._set_entry(where, idx, changed)
	Profile.save()
	return ""


# ---------------------------------------------------------------- принтер

## Принтер собран и отдан в пользование (задание «Фирменный знак»; чит «открыть всё» — тоже).
static func printer_ready() -> bool:
	return Settings.unlocked() or Quests.flag(String(Balance.STICKERS.printer_flag)) == true


## На сколько листов ещё хватит начатого комплекта картриджей (и подарка Михалыча).
static func ink_left() -> int:
	var media: Dictionary = Profile.hideout_media
	if not media.has("printer_ink"):
		return int(Balance.STICKERS.free_prints)
	return int(media.printer_ink)


## Почему сейчас нельзя напечатать ("" — можно).
static func print_block(id: String) -> String:
	if not printer_ready():
		return "Принтера нет. Его собирает Михалыч — задание «Фирменный знак»."
	if not id in (Balance.STICKERS.printable as Array):
		return "Такой рисунок принтер не печатает."
	var free: bool = not Profile.hideout_media.has("printer_ink") and int(Balance.STICKERS.free_prints) > 0
	if not free and Profile.stash_count(String(Balance.STICKERS.film)) < 1:
		return "Нет плёнки в тайнике. Плёнку продаёт Михалыч."
	if ink_left() <= 0 and Profile.stash_count(String(Balance.STICKERS.ink)) < 1:
		return "Краска кончилась — нужен комплект картриджей в тайнике."
	if ItemDb.room_in(Profile.stash, ItemDb.make(id, 1), Profile.stash_grid()) < 1:
		return "В тайнике нет места для наклейки."
	return ""


## Напечатать наклейку id: лист плёнки и краска — из тайника, наклейка — в тайник. "" — готово.
static func print_sticker(id: String) -> String:
	var why: String = print_block(id)
	if why != "":
		return why
	var free: bool = not Profile.hideout_media.has("printer_ink") and int(Balance.STICKERS.free_prints) > 0
	var ink: int = ink_left()
	if ink <= 0:
		Profile.take_from_stash(String(Balance.STICKERS.ink), 1)
		ink = int(Balance.STICKERS.ink_sheets)
	if not free:
		Profile.take_from_stash(String(Balance.STICKERS.film), 1)
	Profile.hideout_media["printer_ink"] = ink - 1
	ItemDb.add_to(Profile.stash, ItemDb.make(id, 1), Profile.stash_grid())
	Profile.save()
	return ""


## Эвакуация со стволом: наклейкам «Счёт» на нём — по зарубке.
static func tally_extract(entry: Dictionary) -> void:
	for st: Variant in of(entry):
		if st is Dictionary and String((st as Dictionary).get("id", "")) == String(Balance.STICKERS.tally):
			st["n"] = mini(int((st as Dictionary).get("n", 0)) + 1, int(Balance.STICKERS.tally_max))


## Подпись наклейки на стволе для списков: «Счёт · 7 зарубок · слева, коробка сзади».
static func label(weapon_id: String, st: Dictionary) -> String:
	var text: String = ItemDb.item_name(String(st.get("id", "")))
	if String(st.get("id", "")) == String(Balance.STICKERS.tally):
		text += " · зарубок: %d" % int(st.get("n", 0))
	var site: Dictionary = WeaponMark.position_spec(weapon_id, String(st.get("site", "")))
	if not site.is_empty():
		text += " · " + String(site.name).to_lower()
	return text
