extends Node
## Маршрут Зоны 2: новые/старые профили, выбор в убежище и сохранение; с host/client — настоящий ENet.
## tools/godot.cmd --headless res://tools/zone02_route_test.tscn [-- host|client]

const ROUTE_ID: String = "zone02"
const ROUTE_SCENE: String = "res://scenes/levels/zone02_urban_belt.tscn"
const WAIT_SEC: float = 45.0

var _fails: int = 0
var _role: String = "local"
var _client_confirmed: bool = false


func _ready() -> void:
	await get_tree().process_frame
	# Смена карты не должна удалить тест и его RPC-узел.
	get_tree().current_scene = null
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if not args.is_empty():
		_role = String(args[0])
	if _role not in ["local", "host", "client"]:
		push_error("zone02_route: ожидается local, host или client")
		get_tree().quit(1)
		return
	Profile.use_file("user://profile_zone02_route_%s_test.json" % _role, true)
	Profile.from_hideout = false
	Profile.pending_raid = false
	_test_availability()
	if _role != "client":
		await _test_selection()
	if _role == "host":
		await _host()
	elif _role == "client":
		await _client()
	print("zone02_route[%s]: провалено %d" % [_role, _fails])
	get_tree().quit(1 if _fails > 0 else 0)


func _test_availability() -> void:
	var route: Dictionary = Floors.find(ROUTE_ID)
	_check("маршрут зарегистрирован", not route.is_empty()
		and String(route.get("name", "")) == "Зона 2 · Городской пояс"
		and Floors.scene(ROUTE_ID) == ROUTE_SCENE and Floors.built(ROUTE_ID))
	_check("новый профиль: доступен без открытия", Floors.is_open(ROUTE_ID)
		and ROUTE_ID not in Profile.floors_open and Profile.floor == "f1")
	_check("пеший маршрут без платы", bool(route.get("available_by_default", false))
		and int(route.get("price", -1)) == 0 and int(route.get("fee", -1)) == 0)
	# Сохранение до появления нового маршрута: в списке только f1, денег и доверия нет.
	Profile.money = 0
	Profile.trust = 0
	Profile.floors_open = ["f1"]
	Profile.floor = "f1"
	Profile.save()
	Profile.use_file(Profile.path, false)
	var before: String = FileAccess.get_file_as_string(Profile.path)
	var open_before: Array = Profile.floors_open.duplicate()
	_check("старый профиль: маршрут доступен", Floors.is_open(ROUTE_ID)
		and Floors.start_block(ROUTE_ID) == "" and Floors.unlock_block(ROUTE_ID) == "")
	_check("открывать за деньги не требуется", not Floors.unlock(ROUTE_ID))
	Floors.pay_fee(ROUTE_ID)
	_check("проверка доступности не меняет сохранение", Profile.money == 0
		and Profile.floors_open == open_before and FileAccess.get_file_as_string(Profile.path) == before)
	_check("старые маршруты сохраняют ограничения", Floors.is_open("f1")
		and not Floors.is_open("f2") and Floors.unlock_block("f2").begins_with("доверие"))
	_check("сцена определяет id маршрута", Floors.id_for_scene(ROUTE_SCENE) == ROUTE_ID
		and Floors.id_for_scene(Floors.scene("f1")) == "f1"
		and Floors.id_for_scene("") == "" and Floors.id_for_scene("res://unknown.tscn") == "")
	_check("неизвестный маршрут закрыт", not Floors.is_open("unknown")
		and Floors.start_block("unknown") == "маршрут закрыт")


func _test_selection() -> void:
	var ui: HideoutUI = HideoutUI.new()
	ui.process_mode = Node.PROCESS_MODE_DISABLED
	add_child(ui)
	ui._floors_column()
	var button: Button = _select_button(ui, ROUTE_ID)
	_check("убежище: есть выбор Зоны 2", button != null and not button.disabled)
	if button != null:
		button.pressed.emit()
	_check("убежище: выбор дошёл до Floors", Profile.floor == ROUTE_ID)
	Profile.use_file(Profile.path, false)
	_check("выбор сохраняется после загрузки", Profile.floor == ROUTE_ID
		and Floors.start_block(Profile.floor) == "" and Profile.money == 0)
	var before: String = FileAccess.get_file_as_string(Profile.path)
	_check("закрытый и неизвестный маршрут выбрать нельзя", not Floors.select("f2")
		and not Floors.select("unknown") and Profile.floor == ROUTE_ID
		and FileAccess.get_file_as_string(Profile.path) == before)
	ui.queue_free()
	await get_tree().process_frame


func _select_button(ui: HideoutUI, route_id: String) -> Button:
	var title: String = String(Floors.find(route_id).get("name", ""))
	for node: Node in ui.find_children("*", "Label", true, false):
		var label: Label = node as Label
		if label.text.strip_edges() != title:
			continue
		for child: Node in label.get_parent().get_children():
			if child is Button and (child as Button).text == "Выбрать":
				return child as Button
	return null


func _host() -> void:
	if not FileAccess.file_exists(ROUTE_SCENE):
		_check("сцена Зоны 2 готова к запуску", false)
		return
	RaidEvents.enabled = false
	Profile.from_hideout = true
	var error: String = Net.host("Zone02 host")
	_check("хост поднят", error == "")
	if error != "":
		return
	var lobby: Control = (load("res://scenes/net/lobby.tscn") as PackedScene).instantiate() as Control
	add_child(lobby)
	Profile.floor = "f2"
	lobby.call("_refresh")
	lobby.call("_on_start_pressed")
	_check("лобби не запускает закрытый маршрут", get_tree().current_scene == null
		and not Profile.pending_raid and (lobby.get_node("Center/Panel/VBox/StartButton") as Button).disabled)
	Profile.floor = ROUTE_ID
	lobby.call("_refresh")
	var start: Button = lobby.get_node("Center/Panel/VBox/StartButton") as Button
	_check("лобби разрешает Зону 2 без денег", not start.disabled)
	if not await _wait(func() -> bool: return Net.player_names.size() == 2):
		_check("клиент подключился", false)
		lobby.queue_free()
		return
	start.pressed.emit()
	await _wait(_in_zone02)
	_check("хост загрузил выбранную карту", _in_zone02() and Profile.floor == ROUTE_ID and Profile.pending_raid)
	_check("хост дождался навигации", await _wait(_navigation_ready))
	lobby.queue_free()
	await _wait(func() -> bool: return _client_confirmed)
	_check("клиент подтвердил ту же карту и маршрут", _client_confirmed)
	await get_tree().create_timer(2.0).timeout


func _client() -> void:
	_check("у клиента до старта выбран f1", Profile.floor == "f1" and ROUTE_ID not in Profile.floors_open)
	RaidEvents.enabled = false
	var error: String = Net.join("127.0.0.1", "Zone02 client")
	_check("подключение к хосту начато", error == "")
	if error != "":
		return
	await _wait(_in_zone02)
	_check("клиент загрузил карту хоста", _in_zone02())
	_check("выбор хоста дошёл до клиента", Profile.floor == ROUTE_ID and not Profile.pending_raid
		and ROUTE_ID not in Profile.floors_open)
	_check("клиент дождался навигации", await _wait(_navigation_ready))
	if _in_zone02():
		_client_route_seen.rpc_id(1, Profile.floor, get_tree().current_scene.scene_file_path)
		await get_tree().create_timer(1.0).timeout


@rpc("any_peer", "call_remote", "reliable")
func _client_route_seen(route_id: String, scene_path: String) -> void:
	if Net.is_host() and multiplayer.get_remote_sender_id() in Net.player_names:
		_client_confirmed = route_id == ROUTE_ID and scene_path == ROUTE_SCENE


func _in_zone02() -> bool:
	var scene: Node = get_tree().current_scene
	return scene != null and scene.scene_file_path == ROUTE_SCENE


func _navigation_ready() -> bool:
	return _in_zone02() and bool(get_tree().current_scene.get("_nav_baked"))


func _wait(predicate: Callable) -> bool:
	var start: int = Time.get_ticks_msec()
	while not predicate.call():
		if float(Time.get_ticks_msec() - start) / 1000.0 > WAIT_SEC:
			return false
		await get_tree().process_frame
	return true


func _check(label: String, ok: bool) -> void:
	print("%s zone02_route[%s]: %s" % ["OK" if ok else "FAIL", _role, label])
	if not ok:
		_fails += 1
