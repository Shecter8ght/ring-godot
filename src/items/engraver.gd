class_name Engraver
extends RefCounted
## Головка оплачивает ровно одно успешное, постоянное нанесение на существующий ствол.


static func block() -> String:
	if Quests.flag("engraver_installed") != true:
		return "Восстановите станок по заданию Михалыча «Своя метка»."
	if int(Quests.campaign_modules().get("generator", 0)) < 1:
		return "Нужно питание: восстановите генератор убежища."
	return ""


static func weapons() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for slot: String in Profile.equipment:
		var entry: Dictionary = Profile.equipment[slot]
		if WeaponDb.is_weapon(String(entry.get("id", ""))):
			out.append({"where": "equip:" + slot, "idx": -1, "entry": entry})
	for role: String in ["stash", "backpack", "pocket"]:
		var list: Array = Profile.list_of(role)
		for index: int in range(list.size()):
			if WeaponDb.is_weapon(String(list[index].get("id", ""))):
				out.append({"where": role, "idx": index, "entry": list[index]})
	return out


static func heads() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for role: String in ["stash", "backpack", "pocket"]:
		var list: Array = Profile.list_of(role)
		for index: int in range(list.size()):
			var entry: Dictionary = list[index]
			if String(entry.get("id", "")) == "laser_head" and int(entry.get("charges", 0)) > 0:
				out.append({"where": role, "idx": index, "entry": entry})
	return out


static func apply(where: String, idx: int, expected_uid: String, head_where: String, head_idx: int, head_uid: String, text: String, preview: Dictionary) -> String:
	var reason: String = block()
	if reason != "":
		return reason
	var entry: Dictionary = Profile._entry_at(where, idx)
	var head: Dictionary = Profile._entry_at(head_where, head_idx)
	if not WeaponDb.is_weapon(String(entry.get("id", ""))) or String(entry.get("uid", "")) != expected_uid:
		return "Оружие переместилось. Выберите его снова."
	if not (entry.get("engraving", {}) as Dictionary).is_empty():
		return "На этом стволе уже есть постоянная гравировка."
	if String(head.get("id", "")) != "laser_head" or String(head.get("uid", "")) != head_uid or int(head.get("charges", 0)) <= 0:
		return "Головка переместилась или исчерпана. Выберите её снова."
	var clean: String = WeaponMark.clean_text(text)
	if clean == "" or clean.length() > int(Balance.ENGRAVING.max_text):
		return "Введите надпись длиной от 1 до %d символов." % int(Balance.ENGRAVING.max_text)
	if String(preview.get("text", "")) != clean or String(preview.get("serial", "")) != expected_uid.substr(0, 10).to_upper():
		return "Предпросмотр устарел. Проверьте надпись снова."
	var site: String = String(preview.get("site", "right_1"))
	if WeaponMark.position_spec(String(entry.id), site).is_empty():
		return "Выберите место нанесения на оружии."
	var before_weapon: Dictionary = entry.duplicate(true)
	var before_head: Dictionary = head.duplicate(true)
	var changed: Dictionary = entry.duplicate(true)
	changed["engraving"] = WeaponMark.make(entry, clean, site)
	Profile._set_entry(where, idx, changed)
	var updated_head: Dictionary = head.duplicate(true)
	updated_head["charges"] = int(head.charges) - 1
	Profile._set_entry(head_where, head_idx, updated_head)
	if not Profile.save():
		Profile._set_entry(where, idx, before_weapon)
		Profile._set_entry(head_where, head_idx, before_head)
		return "Не удалось сохранить нанесение. Ресурс головки сохранён."
	return ""
