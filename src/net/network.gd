extends Node
## Хост/клиент на ENet. Хост = peer 1 (стандарт Godot) и одновременно авторитет по умолчанию
## для каждого узла — этим и обеспечивается «авторитет у хоста» без явной настройки прав на
## большинстве узлов (Marauder, Door). Player — исключение: его авторитет отдаётся владельцу
## (см. sector_level.gd), чтобы движение было отзывчивым, а не как у остальных peer.
## Autoload `Net`.

const PORT := 7777
const MAX_PLAYERS := 3
const LEVEL_SCENE := "res://scenes/levels/f1_ring.tscn"
## Meta корня сцены-уровня: какая это сцена для синхронизаторов ("hideout", "raid"). Ставит сам
## уровень в _enter_tree — раньше, чем его дети создадут свои синхронизаторы.
const SCENE_META := "net_scene"

signal player_list_changed
## Кто в какой сцене поменялся (peer_scene).
signal scenes_changed
## Клиент подключился к хосту / не смог.
signal joined
signal join_failed
## Хост начислил деньги (текст для окна, где сейчас игрок).
signal money_received(text: String)
## Открыт для чтения из lobby.gd: peer_id -> имя.
var player_names: Dictionary = {}
## Свой флаг вместо multiplayer.has_multiplayer_peer(): в Godot 4.5 он true даже без реального
## MultiplayerPeer (умалчиваемая «оффлайн» сессия сама себе сервер, unique_id=1, is_server()=true) —
## по нему нельзя отличить одиночную игру от настоящей сети. Ставим true только сами, в host()/join().
var _active: bool = false
## Где сейчас каждый peer (свой — тоже): "menu", "hideout", "raid". Синхронизаторы сцены шлют
## только тем, кто в той же сцене (visible_in) — ушедший в убежище не получает поток рейда, а
## спавн игрока приходит клиенту, когда его сцена уже загрузилась. Узнаём друг о друге при
## подключении (каждый — каждому, клиенты — и между собой) и при каждой смене сцены.
var peer_scene: Dictionary = {}


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
	_keep_own_scene(peer)
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
	_keep_own_scene(peer)
	_active = true
	player_names.clear()
	player_names[multiplayer.get_unique_id()] = display_name
	return ""


## Сменился пир — сменился и свой id (оффлайн был 1): где я — переносится под новый id, чужие
## записи прежней сессии выбрасываются (иначе своё «hideout» под id 1 читалось бы как хост).
func _keep_own_scene(peer: MultiplayerPeer) -> void:
	var mine := String(peer_scene.get(multiplayer.get_unique_id(), ""))
	multiplayer.multiplayer_peer = peer
	peer_scene.clear()
	if mine != "":
		peer_scene[multiplayer.get_unique_id()] = mine


## Разрывает соединение и возвращает в состояние «не в сети» (для «Выйти в меню»).
## Пир — «оффлайн», а не null: с null get_unique_id() и RPC падают (убежище, соло-рейд).
func disconnect_all() -> void:
	if multiplayer.multiplayer_peer:
		multiplayer.multiplayer_peer.close()
	_keep_own_scene(OfflineMultiplayerPeer.new())
	_active = false
	player_names.clear()


## Только хост может позвать: переводит всех (включая себя) на этаж scene — выбранный хостом
## в убежище маршрут (у клиентов маршрут может быть и не открыт: идут за хостом).
## conditions — условия рейда хоста (RaidConditions), у всех одинаковые.
@rpc("authority", "call_local", "reliable")
func start_level(scene: String, conditions: Dictionary) -> void:
	# со снаряжением профиля — только если игрок пришёл в лобби из убежища (не тесты)
	Profile.pending_raid = Profile.from_hideout
	RaidConditions.from_host = conditions
	get_tree().change_scene_to_file(scene if scene != "" else LEVEL_SCENE)


## Панель админа (хост в сети; в соло — себе): начислить amount ₽ игроку peer_id (себе — тоже). Деньги лежат в профиле
## на компьютере игрока — туда и пишутся (хост — доверенный: играют друзья).
func grant_money(peer_id: int, amount: int) -> void:
	if (is_networked() and not is_host()) or amount == 0:
		return
	if not is_networked() or peer_id == multiplayer.get_unique_id():
		_receive_money(amount)
	else:
		_receive_money.rpc_id(peer_id, amount)


@rpc("authority", "call_remote", "reliable")
func _receive_money(amount: int) -> void:
	Profile.ensure()
	Profile.money = maxi(0, Profile.money + amount)
	Profile.save()
	var who := "Хост начислил" if is_networked() and not is_host() else "Начислено"
	var text := "%s %s ₽ — на счету %s ₽" % [who, InventoryUI.money(amount), InventoryUI.money(Profile.money)]
	if Raid.current:
		Raid.current.notify(text)
	money_received.emit(text)


## Сцена загружена: сказать всем, где я (и запомнить у себя).
func enter_scene(key: String) -> void:
	peer_scene[multiplayer.get_unique_id()] = key
	scenes_changed.emit()
	if is_networked():
		_scene_is.rpc(key)


## Виден ли peer синхронизаторам сцены key (он в ней же). Не отозвался ещё — нет.
func visible_in(peer: int, key: String) -> bool:
	return String(peer_scene.get(peer, "")) == key


@rpc("any_peer", "call_remote", "reliable")
func _scene_is(key: String) -> void:
	peer_scene[multiplayer.get_remote_sender_id()] = key
	scenes_changed.emit()


## Синхронизатор узла node — только тем, кто в той же сцене, что и узел (уровень с meta
## SCENE_META среди предков). Звать ДО add_child(sync): войдя в дерево без фильтра, он на кадр
## виден всем — Godot успевает послать путь к нему тем, кто ещё в другой сцене; у них узла нет,
## путь не подтверждается, и этому peer узел больше не шлётся никогда (хост «стоял» у клиентов).
func scope_sync(node: Node, sync: MultiplayerSynchronizer) -> void:
	var key := scene_of(node)
	if key != "":
		filter_sync(sync, key)


## В какой сцене узел ("hideout", "raid"; вне уровня — "").
func scene_of(node: Node) -> String:
	var n := node
	while n != null:
		if n.has_meta(SCENE_META):
			return String(n.get_meta(SCENE_META))
		n = n.get_parent()
	return ""


## Для синхронизаторов сцены key: показывать данные только peer из той же сцены. Второй раз
## (узел уже с фильтром) — ничего.
func filter_sync(sync: MultiplayerSynchronizer, key: String) -> void:
	if sync.has_meta(SCENE_META):
		return
	sync.set_meta(SCENE_META, key)
	sync.add_visibility_filter(func(peer: int) -> bool: return visible_in(peer, key))


func _on_peer_connected(id: int) -> void:
	# новому — где я (клиент клиенту тоже: хост не пересказывает, а без этого двое клиентов в
	# убежище друг друга не видели — каждый сообщал о себе, пока другого ещё не знал)
	if peer_scene.has(multiplayer.get_unique_id()):
		_scene_is.rpc_id(id, String(peer_scene[multiplayer.get_unique_id()]))
	if is_host():
		# Сообщаем новому peer имена уже подключённых, и всем — что появился новый (имя придёт RPC'ом от него).
		_send_names.rpc_id(id, player_names)


func _on_peer_disconnected(id: int) -> void:
	player_names.erase(id)
	peer_scene.erase(id)
	scenes_changed.emit()
	player_list_changed.emit()


func _on_connected_to_server() -> void:
	_announce_name.rpc_id(1, player_names.get(multiplayer.get_unique_id(), "Игрок"))
	joined.emit()


func _on_connection_failed() -> void:
	_keep_own_scene(OfflineMultiplayerPeer.new())
	_active = false
	join_failed.emit()


func _on_server_disconnected() -> void:
	_keep_own_scene(OfflineMultiplayerPeer.new())
	_active = false
	player_names.clear()
	player_list_changed.emit()
	# хост ушёл: снаряжение, взятое в рейд, остаётся там (как при смерти); дальше — в своё убежище
	Profile.pending_raid = false
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)


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
