extends Control
## Экран лобби: хост поднимает сервер, остальные подключаются по IP. Список игроков — из
## `Net.player_names`. «Начать рейд» доступна только хосту и переводит всех в сектор.

@onready var _name_edit: LineEdit = $Center/Panel/VBox/NameRow/NameEdit
@onready var _address_edit: LineEdit = $Center/Panel/VBox/PreConnect/JoinRow/AddressEdit
@onready var _host_button: Button = $Center/Panel/VBox/PreConnect/ButtonsRow/HostButton
@onready var _join_button: Button = $Center/Panel/VBox/PreConnect/ButtonsRow/JoinButton
@onready var _start_button: Button = $Center/Panel/VBox/StartButton
@onready var _leave_button: Button = $Center/Panel/VBox/LeaveButton
var _admin_button: Button
@onready var _status: Label = $Center/Panel/VBox/Status
@onready var _players_list: Label = $Center/Panel/VBox/PlayersList
@onready var _pre_connect: Control = $Center/Panel/VBox/PreConnect


func _ready() -> void:
	Net.player_list_changed.connect(_refresh)
	_host_button.pressed.connect(_on_host_pressed)
	_join_button.pressed.connect(_on_join_pressed)
	_start_button.pressed.connect(_on_start_pressed)
	_leave_button.pressed.connect(_on_leave_pressed)
	_name_edit.text = "Игрок%d" % (randi() % 900 + 100)
	# назад в убежище — из сети выходим
	var back := Button.new()
	back.text = "В убежище"
	back.pressed.connect(func() -> void:
		Net.disconnect_all()
		get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE))
	($Center/Panel/VBox as VBoxContainer).add_child(back)
	# хост: деньги игрокам — то же окно, что в меню Esc
	_admin_button = Button.new()
	_admin_button.text = "Деньги игрокам (админ)"
	_admin_button.pressed.connect(func() -> void: Pause.open_admin())
	($Center/Panel/VBox as VBoxContainer).add_child(_admin_button)
	Net.money_received.connect(func(t: String) -> void: _status.text = t)
	# имя и адрес хоста — с прошлого раза
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	_name_edit.text = String(cfg.get_value("net", "name", _name_edit.text))
	_address_edit.text = String(cfg.get_value("net", "address", "127.0.0.1"))
	_refresh()


func _remember() -> void:
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	cfg.set_value("net", "name", _name_edit.text)
	cfg.set_value("net", "address", _address_edit.text)
	cfg.save(CameraRig.SETTINGS_PATH)


func _on_host_pressed() -> void:
	_remember()
	var err := Net.host(_name_edit.text)
	_status.text = err if err != "" else "Сервер поднят на порту %d. Ждём остальных." % Net.PORT
	_refresh()


func _on_join_pressed() -> void:
	_remember()
	var err := Net.join(_address_edit.text, _name_edit.text)
	_status.text = err if err != "" else "Подключаюсь…"
	_refresh()


func _on_start_pressed() -> void:
	# из убежища — на выбранный этаж (плата за вылет — с хоста); иначе — первый этаж
	var scene := Net.LEVEL_SCENE
	if Profile.from_hideout:
		scene = Floors.scene(Profile.floor)
		Floors.pay_fee(Profile.floor)
	Net.start_level.rpc(scene)


func _on_leave_pressed() -> void:
	Net.disconnect_all()
	_status.text = ""
	_refresh()


func _refresh() -> void:
	var networked := Net.is_networked()
	_pre_connect.visible = not networked
	_leave_button.visible = networked
	_start_button.visible = Net.is_host()
	_admin_button.visible = Net.is_host()
	if networked:
		var lines: Array[String] = []
		for id in Net.player_names.keys():
			var tag := " (хост)" if id == 1 else ""
			lines.append("· %s%s" % [String(Net.player_names[id]), tag])
		_players_list.text = "\n".join(lines)
		if not _status.text.begins_with("не") and Net.is_host():
			_status.text = "Сервер поднят на порту %d. Ждём остальных." % Net.PORT
	else:
		_players_list.text = ""
