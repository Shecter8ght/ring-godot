extends Control
## Экран лобби: хост поднимает сервер, остальные подключаются по IP. Список игроков — из
## `Net.player_names`. «Начать рейд» доступна только хосту и переводит всех в сектор.

@onready var _name_edit: LineEdit = $Center/Panel/VBox/NameRow/NameEdit
@onready var _address_edit: LineEdit = $Center/Panel/VBox/PreConnect/JoinRow/AddressEdit
@onready var _host_button: Button = $Center/Panel/VBox/PreConnect/ButtonsRow/HostButton
@onready var _join_button: Button = $Center/Panel/VBox/PreConnect/ButtonsRow/JoinButton
@onready var _start_button: Button = $Center/Panel/VBox/StartButton
@onready var _leave_button: Button = $Center/Panel/VBox/LeaveButton
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
	_address_edit.text = "127.0.0.1"
	_refresh()


func _on_host_pressed() -> void:
	var err := Net.host(_name_edit.text)
	_status.text = err if err != "" else "Сервер поднят на порту %d. Ждём остальных." % Net.PORT
	_refresh()


func _on_join_pressed() -> void:
	var err := Net.join(_address_edit.text, _name_edit.text)
	_status.text = err if err != "" else "Подключаюсь…"
	_refresh()


func _on_start_pressed() -> void:
	Net.start_level.rpc()


func _on_leave_pressed() -> void:
	Net.disconnect_all()
	_status.text = ""
	_refresh()


func _refresh() -> void:
	var networked := Net.is_networked()
	_pre_connect.visible = not networked
	_leave_button.visible = networked
	_start_button.visible = Net.is_host()
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
