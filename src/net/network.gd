extends Node
## Хост/клиент на ENet. Хост = peer 1 (стандарт Godot) и одновременно авторитет по умолчанию
## для каждого узла — этим и обеспечивается «авторитет у хоста» без явной настройки прав на
## большинстве узлов (Marauder, Door). Player — исключение: его авторитет отдаётся владельцу
## (см. sector_level.gd), чтобы движение было отзывчивым, а не как у остальных peer.
## Autoload `Net`.

const PORT := 7777
const MAX_PLAYERS := 3
const LEVEL_SCENE := "res://scenes/levels/f1_market.tscn"

signal player_list_changed
## Открыт для чтения из lobby.gd: peer_id -> имя.
var player_names: Dictionary = {}
## Свой флаг вместо multiplayer.has_multiplayer_peer(): в Godot 4.5 он true даже без реального
## MultiplayerPeer (умалчиваемая «оффлайн» сессия сама себе сервер, unique_id=1, is_server()=true) —
## по нему нельзя отличить одиночную игру от настоящей сети. Ставим true только сами, в host()/join().
var _active: bool = false


func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(_on_connected_to_server)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)


func is_networked() -> bool:
	return _active


func is_host() -> bool:
	return is_networked() and multiplayer.is_server()


## Возвращает "" при успехе, иначе текст ошибки для UI.
func host(display_name: String) -> String:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_server(PORT, MAX_PLAYERS)
	if err != OK:
		return "не удалось поднять сервер (%s)" % error_string(err)
	multiplayer.multiplayer_peer = peer
	_active = true
	player_names.clear()
	player_names[1] = display_name
	player_list_changed.emit()
	return ""


func join(address: String, display_name: String) -> String:
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_client(address.strip_edges(), PORT)
	if err != OK:
		return "не удалось подключиться (%s)" % error_string(err)
	multiplayer.multiplayer_peer = peer
	_active = true
	player_names.clear()
	player_names[multiplayer.get_unique_id()] = display_name
	return ""


## Разрывает соединение и возвращает в состояние «не в сети» (для «Выйти в меню»).
func disconnect_all() -> void:
	if multiplayer.multiplayer_peer:
		multiplayer.multiplayer_peer.close()
	multiplayer.multiplayer_peer = null
	_active = false
	player_names.clear()


## Только хост может позвать: переводит всех (включая себя) в сектор.
@rpc("authority", "call_local", "reliable")
func start_level() -> void:
	get_tree().change_scene_to_file(LEVEL_SCENE)


func _on_peer_connected(id: int) -> void:
	if is_host():
		# Сообщаем новому peer имена уже подключённых, и всем — что появился новый (имя придёт RPC'ом от него).
		_send_names.rpc_id(id, player_names)


func _on_peer_disconnected(id: int) -> void:
	player_names.erase(id)
	player_list_changed.emit()


func _on_connected_to_server() -> void:
	_announce_name.rpc_id(1, player_names.get(multiplayer.get_unique_id(), "Игрок"))


func _on_connection_failed() -> void:
	multiplayer.multiplayer_peer = null
	_active = false


func _on_server_disconnected() -> void:
	multiplayer.multiplayer_peer = null
	_active = false
	player_names.clear()
	player_list_changed.emit()
	get_tree().change_scene_to_file("res://scenes/net/lobby.tscn")


@rpc("any_peer", "reliable")
func _announce_name(name_str: String) -> void:
	if not is_host():
		return
	var id := multiplayer.get_remote_sender_id()
	player_names[id] = name_str
	_send_names.rpc(player_names)
	player_list_changed.emit()


@rpc("authority", "reliable")
func _send_names(names: Dictionary) -> void:
	player_names = names
	player_list_changed.emit()
