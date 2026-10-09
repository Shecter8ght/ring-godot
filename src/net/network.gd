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
## После server_disconnected ENet уже закрыт: старый id нельзя запрашивать у него.
var _own_id: int = 1
## Где сейчас каждый peer (свой — тоже): "menu", "hideout", "raid". Синхронизаторы сцены шлют
## только тем, кто в той же сцене (visible_in) — ушедший в убежище не получает поток рейда, а
## спавн игрока приходит клиенту, когда его сцена уже загрузилась. Узнаём друг о друге при
## подключении (каждый — каждому, клиенты — и между собой) и при каждой смене сцены.
var peer_scene: Dictionary = {}
## Перед удалением уровня дождаться, пока остальные закроют его сетевые потоки.
var _changing_scene: bool = false
var _transition_serial: int = 0
var _transition_pending: Dictionary = {}
## _ready уровня ещё не означает, что пережили создание GPU-ресурсов первого кадра.
var _ready_scene: String = ""
## После потери хоста убежище показывает причину возврата.
var disconnect_message: String = ""


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
func host(display_name: String, port: int = PORT) -> String:
	disconnect_message = ""
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_server(port, MAX_PLAYERS)
	if err != OK:
		return "не удалось поднять сервер (%s)" % error_string(err)
	_keep_own_scene(peer)
	_active = true
	player_names.clear()
	player_names[1] = display_name
	player_list_changed.emit()
	return ""


func join(address: String, display_name: String, port: int = PORT) -> String:
	disconnect_message = ""
	var peer := ENetMultiplayerPeer.new()
	var err := peer.create_client(address.strip_edges(), port)
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
	var mine := String(peer_scene.get(_own_id, ""))
	multiplayer.multiplayer_peer = peer
	_own_id = multiplayer.get_unique_id()
	peer_scene.clear()
	if mine != "":
		peer_scene[_own_id] = mine


## Разрывает соединение и возвращает в состояние «не в сети» (для «Выйти в меню»).
## Пир — «оффлайн», а не null: с null get_unique_id() и RPC падают (убежище, соло-рейд).
func disconnect_all() -> void:
	var previous_peer: MultiplayerPeer = multiplayer.multiplayer_peer
	_active = false
	_transition_pending.clear()
	# Сохраняем свой id и сцену до close(): закрытый ENet уже не возвращает unique_id.
	_keep_own_scene(OfflineMultiplayerPeer.new())
	if previous_peer:
		previous_peer.close()
	player_names.clear()


## Только хост может позвать: переводит всех (включая себя) на карту scene — выбранный хостом
## в убежище маршрут (у клиентов маршрут может быть и не открыт: идут за хостом).
## conditions — условия рейда хоста (RaidConditions), у всех одинаковые.
@rpc("authority", "call_local", "reliable")
func start_level(scene: String, conditions: Dictionary) -> void:
	var target_scene: String = scene if scene != "" else LEVEL_SCENE
	var route_id: String = Floors.id_for_scene(target_scene)
	# Клиент следует выбору хоста: карта и её название должны относиться к одному маршруту.
	if route_id != "":
		Profile.floor = route_id
	# со снаряжением профиля — только если игрок пришёл в лобби из убежища (не тесты)
	Profile.pending_raid = Profile.from_hideout
	RaidConditions.from_host = conditions
	change_scene(target_scene)


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
	if _changing_scene:
		_ready_scene = key
		return
	peer_scene[multiplayer.get_unique_id()] = key
	_refresh_timeouts()
	print("net: сцена готова ", key, " peer=", _own_id)
	_refresh_scoped_syncs()
	scenes_changed.emit()
	if is_networked():
		_scene_is.rpc(key)


## Сначала закрыть старую сцену у всех, затем удалить её. Иначе пакеты движения
## продолжают приходить по старому пути во время тяжёлой загрузки следующего уровня.
func change_scene(path: String) -> void:
	if not is_networked():
		get_tree().change_scene_to_file(path)
		return
	if _changing_scene:
		return
	_changing_scene = true
	_ready_scene = ""
	var session: MultiplayerPeer = multiplayer.multiplayer_peer
	var began: int = Time.get_ticks_msec()
	print("net: загрузка ", path, " peer=", _own_id)
	_transition_serial += 1
	_transition_pending.clear()
	for peer: int in multiplayer.get_peers():
		_transition_pending[peer] = true
	peer_scene[multiplayer.get_unique_id()] = "loading"
	_refresh_timeouts()
	_refresh_scoped_syncs()
	scenes_changed.emit()
	_scene_is.rpc("loading", _transition_serial)
	while is_networked() and not _transition_pending.is_empty():
		for peer: int in _transition_pending.keys():
			if not peer in multiplayer.get_peers():
				_transition_pending.erase(peer)
		await get_tree().process_frame
	# Чтение большой карты в главном потоке останавливает ENet: медленный компьютер
	# исчезал у хоста, а после загрузки получал server_disconnected и возвращался в убежище.
	var result: Error = ResourceLoader.load_threaded_request(path, "PackedScene")
	if result != OK:
		_finish_scene_error(path, result)
		return
	while ResourceLoader.load_threaded_get_status(path) == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
		await get_tree().process_frame
		if not is_networked() or multiplayer.multiplayer_peer != session:
			_changing_scene = false
			return
	if not is_networked() or multiplayer.multiplayer_peer != session:
		_changing_scene = false
		return
	if ResourceLoader.load_threaded_get_status(path) != ResourceLoader.THREAD_LOAD_LOADED:
		_finish_scene_error(path, ERR_CANT_OPEN)
		return
	var scene: PackedScene = ResourceLoader.load_threaded_get(path) as PackedScene
	if scene == null:
		_finish_scene_error(path, ERR_INVALID_DATA)
		return
	await get_tree().process_frame
	if not is_networked() or multiplayer.multiplayer_peer != session:
		_changing_scene = false
		return
	result = get_tree().change_scene_to_packed(scene)
	if result == OK:
		await get_tree().scene_changed
		# До первого отрисованного кадра компиляция шейдеров ещё может остановить поток.
		# Пока этого не прошли, остальные видят loading и сохраняют увеличенный таймаут.
		await get_tree().process_frame
		await get_tree().process_frame
	else:
		_finish_scene_error(path, result)
		return
	if not is_networked() or multiplayer.multiplayer_peer != session:
		_changing_scene = false
		return
	_changing_scene = false
	var key: String = _ready_scene
	_ready_scene = ""
	if key != "":
		enter_scene(key)
	else:
		_refresh_timeouts()
	print("net: переход завершён за ", Time.get_ticks_msec() - began, " мс peer=", _own_id)


func _finish_scene_error(path: String, error: Error) -> void:
	_changing_scene = false
	push_error("Net: не удалось загрузить %s (%s)" % [path, error_string(error)])
	if is_networked():
		enter_scene(scene_of(get_tree().current_scene))


## Таймаут увеличен у обеих сторон, пока хотя бы один участник загружает сцену.
## Потоки ресурсов идут в фоне, но создание коллизий и первый кадр шейдеров ещё могут задержаться.
func _refresh_timeouts() -> void:
	if not is_networked():
		return
	var enet: ENetMultiplayerPeer = multiplayer.multiplayer_peer as ENetMultiplayerPeer
	if enet == null or enet.host == null:
		return
	var loading: bool = _changing_scene or "loading" in peer_scene.values()
	var settings: Dictionary = Balance.NET_TIMEOUT
	for peer: ENetPacketPeer in enet.host.get_peers():
		peer.set_timeout(int(settings.factor), int(settings.loading_ms if loading else settings.min_ms),
			int(settings.loading_ms if loading else settings.max_ms))


## RPC уровня отправляется только тем, у кого уже есть эта сцена и её узлы.
func broadcast_scene(node: Node, method: StringName, arguments: Array, include_local: bool = true) -> void:
	if is_networked():
		var key: String = scene_of(node)
		if key == "" or visible_in(multiplayer.get_unique_id(), key):
			for peer: int in multiplayer.get_peers():
				if key == "" or visible_in(peer, key):
					node.rpc_id.callv([peer, method] + arguments)
	if include_local:
		node.callv(method, arguments)


## Виден ли peer синхронизаторам сцены key (он в ней же). Не отозвался ещё — нет.
func visible_in(peer: int, key: String) -> bool:
	return String(peer_scene.get(peer, "")) == key


@rpc("any_peer", "call_remote", "reliable")
func _scene_is(key: String, serial: int = 0) -> void:
	var peer: int = multiplayer.get_remote_sender_id()
	peer_scene[peer] = key
	_refresh_timeouts()
	print("net: peer=", peer, " сцена=", key)
	_refresh_scoped_syncs()
	scenes_changed.emit()
	if key == "loading":
		_ack_loading.call_deferred(peer, serial)


func _ack_loading(peer: int, serial: int) -> void:
	# Спавнеры и queue_free завершают закрытие потока в конце кадра.
	await get_tree().process_frame
	await get_tree().process_frame
	if is_networked() and peer in multiplayer.get_peers():
		_scene_closed.rpc_id(peer, serial)


@rpc("any_peer", "call_remote", "reliable")
func _scene_closed(serial: int) -> void:
	if serial == _transition_serial:
		_transition_pending.erase(multiplayer.get_remote_sender_id())


func _refresh_scoped_syncs() -> void:
	for node: Node in get_tree().get_nodes_in_group("net_scoped_syncs"):
		var sync: MultiplayerSynchronizer = node as MultiplayerSynchronizer
		if sync.is_inside_tree() and sync.is_multiplayer_authority():
			sync.update_visibility()


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
	sync.add_to_group("net_scoped_syncs")
	sync.add_visibility_filter(func(peer: int) -> bool:
		return visible_in(multiplayer.get_unique_id(), key) and visible_in(peer, key))


func _on_peer_connected(id: int) -> void:
	_refresh_timeouts()
	print("net: подключён peer=", id)
	# новому — где я (клиент клиенту тоже: хост не пересказывает, а без этого двое клиентов в
	# убежище друг друга не видели — каждый сообщал о себе, пока другого ещё не знал)
	if peer_scene.has(multiplayer.get_unique_id()):
		_scene_is.rpc_id(id, String(peer_scene[multiplayer.get_unique_id()]))
	if is_host():
		# Сообщаем новому peer имена уже подключённых, и всем — что появился новый (имя придёт RPC'ом от него).
		_send_names.rpc_id(id, player_names)


func _on_peer_disconnected(id: int) -> void:
	print("net: отключён peer=", id, " сцена=", peer_scene.get(id, ""))
	player_names.erase(id)
	peer_scene.erase(id)
	_refresh_timeouts()
	# Два клиента могут уйти за один poll ENet. RPC — после обработки обоих отключений.
	scenes_changed.emit.call_deferred()
	player_list_changed.emit()


func _on_connected_to_server() -> void:
	_announce_name.rpc_id(1, player_names.get(multiplayer.get_unique_id(), "Игрок"))
	joined.emit()


func _on_connection_failed() -> void:
	_keep_own_scene(OfflineMultiplayerPeer.new())
	_active = false
	join_failed.emit()


func _on_server_disconnected() -> void:
	print("net: потеряно соединение с хостом; сцена=", peer_scene.get(_own_id, ""), " переход=", _changing_scene)
	disconnect_message = "Потеряно соединение с хостом — возвращение в убежище"
	_changing_scene = false
	_ready_scene = ""
	_transition_pending.clear()
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
