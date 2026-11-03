extends Control
## Понятные причины замков конструктора: уровень верстака, доверие и подсказка об открытии.

var _b: WeaponBuilder
var _fails: int = 0
var _checks: int = 0


func _ready() -> void:
	Settings.unlock_all = false
	Settings.all_weapons = false
	Profile.use_file("user://builder_lock_test.json", true)
	Profile.money = 60000
	Profile.trust = 0
	Profile.modules = {"workbench": 1, "generator": 0}
	Profile.stash.clear()
	Profile.equipment["primary"] = {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": {}, "sight": "primary",
		"mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}}
	_b = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await _frames(12)
	if OS.get_environment("BUILDER_LOCK_SMALL") == "1" and DisplayServer.get_name() != "headless":
		get_window().size = Vector2i(1280, 720)
		await _frames(8)
	_b._select("optic_primary")
	await _frames(3)
	var text: String = _b._lock_note.text
	_check("выбранный замок имеет постоянное объяснение", _b._lock_note.visible and text.contains("уровня 2 (сейчас 1)"))
	_check("сказано, где улучшить верстак", text.contains("Модули убежища") and text.contains("улучши «Верстак»"))
	_check("сказано о недостающем генераторе", text.contains("Генератор") and text.contains("сейчас 0"))
	_check("показаны деньги и детали из тайника", text.contains(InventoryUI.money(180000)) and text.contains(ItemDb.item_name("toolset")) and text.contains(ItemDb.item_name("wires")))
	_check("показано текущее доверие и способ повысить", text.contains("сейчас 1") and text.contains("эвакуациями") and text.contains("заданиями"))
	_check("дочернее крепление объясняет уровень родительской точки", _b._locked("optic_primary#2/rail").contains("уровня 2"))
	var with_tooltip: bool = false
	for card: Node in _b._cards.get_children():
		if card.get("key") == "optic_primary":
			with_tooltip = (card as Control).tooltip_text.contains("Модули убежища")
	_check("карточка крепления имеет полную подсказку", with_tooltip)
	_check("объяснение и кнопки помещаются по высоте", _b._lock_note.get_global_rect().end.y <= _b._strip.get_global_rect().position.y
		and _b._apply_btn.get_global_rect().end.y <= get_viewport_rect().end.y)
	await _shot("workbench")
	Profile.stash.append({"id": "optic_holo_01", "n": 1, "dur": 100.0})
	_b._select("")
	for part: Dictionary in _b._pool():
		if String(part.id) == "optic_holo_01":
			_b._choose(part)
			break
	_check("свой прицел при закрытом верстаке показывает условия, не раздвигая нижнюю строку", _b._draft.is_empty()
		and _b._lock_note.visible and _b._lock_note.text.contains("уровня 2") and not _b._status.text.contains("\n"))
	_b._select("muzzle")
	_check("на открытой точке сообщение о замке скрыто", not _b._lock_note.visible and _b._locked("muzzle") == "")
	Profile.modules.workbench = 2
	_b._select("optic_primary")
	_check("улучшенный верстак открывает точку и убирает сообщение", not _b._lock_note.visible and _b._locked("optic_primary") == "")
	_b._select("")
	_b._pick_source("shop")
	var locked: Dictionary = {}
	for part: Dictionary in _b._pool():
		if String(part.get("lock", "")) != "" and not WeaponBuild.candidate_keys(_b._draft_entry(), String(part.id)).is_empty():
			locked = part
			break
	_check("в ассортименте есть закрытая доверием совместимая деталь", not locked.is_empty())
	if not locked.is_empty():
		var draft: Dictionary = _b._draft.duplicate(true)
		_b._choose(locked)
		_check("нажатие на закрытый товар объясняет открытие без изменения сборки", _b._draft == draft
			and _b._lock_note.visible and _b._lock_note.text.contains("Михалыч пока не продаёт") and _b._lock_note.text.contains("эвакуациями"))
		_b._process(4.0)
		_check("объяснение не исчезает вместе с кратким уведомлением", _b._lock_note.visible and _b._lock_note.text.contains("Михалыч пока не продаёт"))
		var card: Control = _b._part_card(locked, "")
		_check("товар имеет полную подсказку о доверии", card.tooltip_text.contains("Доверие Михалыча") and card.tooltip_text.contains("заданиями"))
		card.free()
		await _shot("trust")
		Profile.trust = TraderStock.step_of(maxi(TraderStock.catalog_of(String(locked.id)), 1)) - 1
		var open: bool = false
		for part: Dictionary in _b._pool():
			if String(part.id) == String(locked.id):
				open = String(part.get("lock", "")) == ""
		_check("достигнутое доверие снимает замок товара", open)
		Profile.trust = 0
		Profile.stash.append({"id": String(locked.id), "n": 1, "dur": 100.0})
		_b._pick_source("mine")
		_check("своя деталь не закрыта доверием торговца", _b._pool().any(func(p: Dictionary) -> bool: return String(p.id) == String(locked.id) and String(p.get("lock", "")) == ""))
	_b.mode = "raid"
	_check("рейд объясняет, что приклад меняют после эвакуации", _b._locked("stock").contains("Эвакуируйся"))
	_b.mode = "sandbox"
	_check("в стенде замков верстака нет", _b._locked("optic_primary") == "")
	_b.mode = "hideout"
	print("builder_lock_test: проверок %d, провалено %d" % [_checks, _fails])
	_b._close()
	get_tree().quit(_fails)


func _shot(id: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	DirAccess.make_dir_recursive_absolute("res://docs/screens/builder_lock_20261103")
	await _frames(8)
	await RenderingServer.frame_post_draw
	var suffix: String = "_small" if OS.get_environment("BUILDER_LOCK_SMALL") == "1" else ""
	get_viewport().get_texture().get_image().save_png("res://docs/screens/builder_lock_20261103/%s%s.png" % [id, suffix])


func _frames(n: int) -> void:
	for i: int in range(n):
		await get_tree().process_frame


func _check(label: String, ok: bool) -> void:
	_checks += 1
	if not ok:
		_fails += 1
	print("%s %s" % ["OK" if ok else "FAIL", label])
