extends Node
## Сохранение настройки, единственное меню читов, выполнение команд и границы интерфейса.
## Для проверки записи настроек нужен APPDATA в tools/_probe. С -- capture — снимки окна.

var _fails: int = 0


func _ready() -> void:
	var probe_root: String = ProjectSettings.globalize_path("res://tools/_probe/").replace("\\", "/")
	if not OS.get_user_data_dir().replace("\\", "/").begins_with(probe_root):
		push_error("cheats_settings_test: нужен отдельный APPDATA в tools/_probe")
		get_tree().quit(1)
		return
	Profile.use_file("user://cheats_settings_test.json", true)
	await get_tree().process_frame
	_check("хит-маркер включён по умолчанию", Settings.hitmarker)
	Settings._tool_run = false
	Settings.set_hitmarker(false)
	Settings.hitmarker = true
	Settings._load()
	_check("отключение сохраняется", not Settings.hitmarker)
	Settings.set_hitmarker(true)
	Settings.hitmarker = false
	Settings._load()
	_check("включение сохраняется", Settings.hitmarker)
	Settings._tool_run = true
	Pause.open_settings()
	await _frames(3)
	var settings: VBoxContainer = Pause.get("_settings") as VBoxContainer
	_check("переключатель в обычных настройках", settings.find_child("HitmarkerToggle", true, false) != null)
	_check("в настройках нет преимуществ и подмены мира", not _has_text(settings, ["бессмертие", "открыть всё", "лут в продаже", "полёт", "скорость", "Погода", "Время суток"]))
	_check("отдельная кнопка Читы", _has_text(Pause.get("_main") as Node, ["Читы"]))
	await _capture("settings_clean")
	Pause.open_cheats()
	await _frames(3)
	var cheats: VBoxContainer = Pause.get("_cheats") as VBoxContainer
	var tabs: TabContainer = cheats.find_children("*", "TabContainer", true, false)[0] as TabContainer
	_check("четыре раздела читов", tabs.get_tab_count() == 4)
	_check("возможности перенесены", _has_all_text(cheats, ["бессмертие", "открыть всё", "лут в продаже", "полёт", "скорость"]))
	_check("время, погода и телепорт перенесены", _has_all_text(cheats, ["Погода", "Время суток", "Переместиться"]))
	cheats.call("run_command", "fly on")
	_check("команда и переключатель полёта согласованы", Settings.cheat_fly and (cheats.get("_toggles") as Dictionary).cheat_fly.button_pressed)
	cheats.call("run_command", "speed 3")
	_check("команда и ползунок скорости согласованы", is_equal_approx(Settings.cheat_speed, 3.0) and is_equal_approx(((cheats.get("_speed") as Node).get_child(0) as HSlider).value, 3.0))
	cheats.call("run_command", "fly off")
	cheats.call("run_command", "speed 1")
	var ammo_before: int = _stash_count("ammo_545_ap")
	cheats.call("run_command", "give ammo 545_AP 30")
	_check("выдача предметов работает из раздела команд", _stash_count("ammo_545_ap") == ammo_before + 30)
	var money_before: int = Profile.money
	cheats.call("refresh_money")
	var money_rows: GridContainer = cheats.get("_money_rows") as GridContainer
	(money_rows.get_child(3) as Button).pressed.emit()
	_check("деньги начисляются из раздела читов", Profile.money == money_before + 100000)
	await _capture("cheats_abilities")
	for index: int in range(1, 4):
		tabs.current_tab = index
		await _frames(3)
		await _capture("cheats_%d" % index)
	_check("старая консоль удалена из HUD", Quests.hud.get("_console") == null and not Quests.hud.has_method("_run"))
	var panel: Control = (Pause.get("_root") as Control).find_children("*", "PanelContainer", true, false)[0] as Control
	var screen: Rect2 = get_viewport().get_visible_rect()
	_check("меню помещается на экране", screen.encloses(panel.get_global_rect()))
	Pause.close_menu()
	var shortcut: InputEventAction = InputEventAction.new()
	shortcut.action = "dev_console"
	shortcut.pressed = true
	Pause._input(shortcut)
	_check("старая клавиша открывает раздел Читы", PauseMenu.shown and cheats.visible and not settings.visible)
	Pause.close_menu()
	# Клиентский peer без сервера достаточен, чтобы проверить ограничения панели гостя.
	var guest: ENetMultiplayerPeer = ENetMultiplayerPeer.new()
	var error: Error = guest.create_client("127.0.0.1", 17798)
	if error == OK:
		multiplayer.multiplayer_peer = guest
		Net._active = true
		Pause.open_cheats()
		_check("гость не получает панель начисления денег", not money_rows.visible)
		var world: GridContainer = cheats.get("_world") as GridContainer
		_check("гость не меняет условия общего мира", (world.get_child(1) as OptionButton).disabled and not ((world.get_child(3) as Node).get_child(0) as HSlider).editable)
		_check("команды изменения заданий доступны хосту", String(cheats.call("run_command", "quest start missing_anton")) == "задания изменяет хост")
		guest.close()
		multiplayer.multiplayer_peer = null
		Net._active = false
		Pause.close_menu()
	else:
		_check("создан тестовый гостевой peer", false)
	print("cheats_settings_test: провалов ", _fails)
	get_tree().quit(_fails)


func _has_text(root: Node, words: Array) -> bool:
	var texts: Array[String] = []
	for node: Node in root.find_children("*", "", true, false):
		if node is Label:
			texts.append((node as Label).text)
		elif node is BaseButton:
			texts.append(String(node.get("text")))
	var all: String = "\n".join(texts)
	for word: String in words:
		if word.to_lower() in all.to_lower():
			return true
	return false


func _has_all_text(root: Node, words: Array) -> bool:
	for word: String in words:
		if not _has_text(root, [word]):
			return false
	return true


func _stash_count(id: String) -> int:
	var total: int = 0
	for entry: Dictionary in Profile.stash:
		if String(entry.id) == id:
			total += int(entry.n)
	return total


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame


func _capture(name: String) -> void:
	if DisplayServer.get_name() == "headless" or not "capture" in OS.get_cmdline_user_args():
		return
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/%s.png" % name)


func _check(label: String, okay: bool) -> void:
	if not okay:
		_fails += 1
	print("%s cheats/settings: %s" % ["OK" if okay else "FAIL", label])
