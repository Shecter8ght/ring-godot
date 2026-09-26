class_name Raid
extends Node
## Состояние рейда: рубильники, эвакуация, лут, итог. Считает хост, остальным реплицируется
## синхронизатором (узел создаёт SectorLevel с одинаковым именем у всех peer).
##
## Эвакуация группой: живой игрок встал в открытую зону ExtractionPoint (рубильник включён; нужный
## ключ — в рюкзаке у кого-то из стоящих в зоне) — пошёл общий отсчёт EXTRACT_GROUP_SEC; из всех зон
## ушли — сброс. Все живые уже в зонах — ждать некого, короткий отсчёт точки (channel_s). Досчитал —
## кто в зоне, эвакуирован: пропадает из мира, выносит рюкзак (раненого в той же зоне выносят с
## собой); живые не в зоне — не успели: в убежище без добычи (stranded). Рейд окончен, когда каждый
## участник погиб или ушёл. Ключи — предметы в рюкзаке (data/items.json, категория key).
## Лут: игроки просят хост (RPC ниже) взять из контейнера, выбросить, полечиться — хост проверяет
## и меняет рюкзак (Inventory) и контейнер (LootContainer). Тела и выброшенное — динамические
## LootContainer через спавнер (узел Drops).

## Мне засчитали убийство мародёра (для тестов и HUD).
signal kill_credited

static var current: Raid

const LOOT_SCENE := preload("res://scenes/world/loot_container.tscn")
## Приписка к точке у того, кого дотащили раненым (итог рейда, хроника).
const CARRIED_SUFFIX := " (вынесли раненым)"

## Кто в рейде: peer_id -> имя. Заполняет хост при появлении игроков.
var participants: Dictionary = {}
## Включённые рубильники: switch_id -> true.
var switches: Dictionary = {}
## Эвакуированные: peer_id -> имя точки.
var extracted: Dictionary = {}
## Сколько вынес (₽): peer_id -> ценность рюкзака в момент эвакуации.
var loot_value: Dictionary = {}
## Кто в зоне: peer_id -> [id точки, секунд короткого отсчёта] (идёт, когда все живые в зонах).
var channel: Dictionary = {}
## Общий отсчёт эвакуации группы: осталось, с (-1 — в открытых зонах никого).
var evac_left: float = -1.0
## Кого ждём: живые не в зоне (peer_id).
var evac_wait: Array = []
## Не успели к эвакуации: peer_id -> точка, через которую ушла группа (вернулись без добычи).
var stranded: Dictionary = {}
var _all_in_t: float = 0.0
## Погибшие: peer_id -> true (хост — по сигналу Health).
var dead: Dictionary = {}
## Кто кого тащит: peer тащащего -> peer раненого (хост проверяет, видят все).
var drags: Dictionary = {}
var over: bool = false

var ui: InventoryUI
## Владелец уже записал итог рейда в профиль (эвакуация) — один раз.
var _profile_saved: bool = false
var _death_saved: bool = false
var _drops: Node3D
var _drop_spawner: MultiplayerSpawner
var _drop_count: int = 0

var _hud: CanvasLayer
var _progress: ProgressBar
var _progress_label: Label
var _prompt: Label
var _toast: Label
var _toast_t: float = 0.0
var _summary: Label
var _summary_bg: ColorRect
## Экран итога с хроникой: рассказ, вердикт, статистика, кто как ушёл, подсказка.
var _story_panel: PanelContainer
var _story_text: Label
var _story_verdict: Label
var _story_stats: GridContainer
var _story_footer: Label
var _story_box: VBoxContainer
## Держим F над раненым напарником — сколько секунд (поднять за REVIVE_SEC).
var _revive_t: float = 0.0
## Сюжет в этом рейде (места квестов, раненый NPC) — у каждого игрока свой.
var quest_world: QuestWorld
## Хроника рейда своего игрока: факты (RaidAnalytics) и готовый рассказ (строится в конце).
var analytics: RaidAnalytics
var chronicle: RaidStory
var _chronicle_wait: float = 0.0
var _delta: float = 0.0


func _ready() -> void:
	current = self
	_drops = Node3D.new()
	_drops.name = "Drops"
	add_child(_drops)
	_build_hud()
	# условия рейда — сводкой в начале
	notify.call_deferred(RaidConditions.title())
	quest_world = QuestWorld.new()
	quest_world.name = "QuestWorld"
	quest_world.raid = true
	add_child(quest_world)
	analytics = RaidAnalytics.new()
	analytics.name = "Analytics"
	add_child(analytics)
	ui = InventoryUI.new()
	ui.name = "InventoryUI"
	add_child(ui)
	if Net.is_networked():
		_setup_sync()
		_drop_spawner = MultiplayerSpawner.new()
		_drop_spawner.name = "DropSpawner"
		add_child(_drop_spawner)
		_drop_spawner.spawn_path = _drops.get_path()
		_drop_spawner.spawn_function = _make_drop


func _exit_tree() -> void:
	if current == self:
		current = null


## Хост — авторитет (умалчиваемый 1). Словари маленькие — шлём постоянно (ALWAYS): так их
## получает и peer, чей узел создался позже изменения.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	sync.name = "Sync"
	sync.replication_interval = 0.1
	var config := SceneReplicationConfig.new()
	for prop in [".:participants", ".:switches", ".:extracted", ".:loot_value", ".:dead", ".:over", ".:channel", ".:drags", ".:evac_left", ".:evac_wait", ".:stranded"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ALWAYS)
	sync.replication_config = config
	sync.set_multiplayer_authority(get_multiplayer_authority())
	Net.scope_sync(self, sync)
	add_child(sync)


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


# ---------------------------------------------------------------- состояние

func register(peer_id: int, display_name: String) -> void:
	var p := participants.duplicate()
	p[peer_id] = display_name
	participants = p


func player_of(peer_id: int) -> Player:
	for node in get_tree().get_nodes_in_group("all_players"):
		var pl := node as Player
		if pl and pl.peer_id == peer_id:
			return pl
	return null


func local_player() -> Player:
	return player_of(multiplayer.get_unique_id())


func key_name(key_id: String) -> String:
	return ItemDb.item_name(key_id)


func is_extracted(peer_id: int) -> bool:
	return extracted.has(peer_id)


## Ушёл из рейда живым: эвакуировался или не успел к эвакуации группы.
func has_left(peer_id: int) -> bool:
	return extracted.has(peer_id) or stranded.has(peer_id)


func set_switch(switch_id: String, on: bool) -> void:
	var s := switches.duplicate()
	s[switch_id] = on
	switches = s


## Хост: игрок погиб — рюкзак остаётся в теле, которое могут обыскать напарники.
func mark_dead(peer_id: int) -> void:
	# ушедший раненым (вынесли / не успел) истекает кровью уже не в рейде
	if not _is_host() or has_left(peer_id):
		return
	var d := dead.duplicate()
	d[peer_id] = true
	dead = d
	var pl := player_of(peer_id)
	if pl:
		_story_death(pl)
	if pl and not pl.inventory.items.is_empty():
		var who := String(Net.player_names.get(peer_id, participants.get(peer_id, "Игрок")))
		spawn_drop(pl.global_position, "Тело: " + who, pl.inventory.take_all(), LootContainer.Look.BAG)
	_check_over()


## Открыта ли точка и, если нет, почему (для подсказки у зоны). Ключ должен быть у кого-то
## из живых в зоне — группа проходит вместе с тем, у кого карта.
func extraction_block_reason(ext: ExtractionPoint) -> String:
	if ext.required_switch != "" and not bool(switches.get(ext.required_switch, false)):
		return "нет питания — включи рубильник"
	if ext.required_switch != "" and String(RaidConditions.current.get("power", "on")) == "off":
		return "в ТЦ нет электричества — ворота не открыть"
	if ext.required_key != "":
		for node in get_tree().get_nodes_in_group("players"):
			var pl := node as Player
			if pl and pl.is_alive() and ext.contains(pl.global_position) and pl.inventory.has(ext.required_key):
				return ""
		return "нужен предмет: " + key_name(ext.required_key)
	return ""


func _physics_process(delta: float) -> void:
	if not _is_host() or over:
		return
	_check_drags()
	_update_evac(delta)


## Открытая зона эвакуации, в которой стоит точка p (null — ни в какой).
func open_zone_at(p: Vector3) -> ExtractionPoint:
	for e in get_tree().get_nodes_in_group("extractions"):
		var ext := e as ExtractionPoint
		if ext and ext.contains(p) and extraction_block_reason(ext) == "":
			return ext
	return null


## Хост: эвакуация группой (правила — в шапке файла).
func _update_evac(delta: float) -> void:
	# кто цел и в открытой зоне; остальные живые
	var inside := {}
	var others: Array[Player] = []
	for node in get_tree().get_nodes_in_group("players"):
		var pl := node as Player
		if pl == null or not pl.is_alive() or has_left(pl.peer_id):
			continue
		var ext := open_zone_at(pl.global_position)
		# раненый сам не эвакуируется — только если его дотащили или он лежит в зоне рядом со своими
		if ext and not pl.is_downed():
			inside[pl.peer_id] = ext
		else:
			others.append(pl)
	if inside.is_empty():
		if evac_left >= 0.0 or not channel.is_empty():
			evac_left = -1.0
			evac_wait = []
			channel = {}
		_all_in_t = 0.0
		return
	var used := {}
	for p in inside:
		used[inside[p]] = true
	# раненого в той же зоне или того, кого тащит стоящий в зоне, — выносят; остальных ждём
	var carried := {}
	var wait: Array = []
	for pl in others:
		var ext := open_zone_at(pl.global_position)
		var dragger := dragger_of(pl.peer_id)
		if pl.is_downed() and ext and used.has(ext):
			carried[pl.peer_id] = ext
		elif pl.is_downed() and dragger and inside.has(dragger.peer_id):
			carried[pl.peer_id] = inside[dragger.peer_id]
		else:
			wait.append(pl.peer_id)
	if evac_left < 0.0:
		evac_left = Balance.EXTRACT_GROUP_SEC
	evac_left = maxf(0.0, evac_left - delta)
	# все здесь — короткий отсчёт (самой долгой из занятых точек); кто-то ушёл — заново
	var need := 0.0
	for ext in used:
		need = maxf(need, (ext as ExtractionPoint).channel_s)
	_all_in_t = _all_in_t + delta if wait.is_empty() else 0.0
	var ch := {}
	for p in inside:
		ch[p] = [String((inside[p] as ExtractionPoint).name), _all_in_t]
	if (wait.is_empty() and _all_in_t >= need) or evac_left <= 0.0:
		_evacuate(inside, carried, wait)
		return
	channel = ch
	if evac_wait != wait:
		evac_wait = wait


## Отсчёт кончился: кто в зоне — уходят (с ранеными), кого ждали — не успели.
func _evacuate(inside: Dictionary, carried: Dictionary, wait: Array) -> void:
	var exit_name := ""
	for p in inside:
		var pl := player_of(int(p))
		if pl and not has_left(pl.peer_id):
			if exit_name == "":
				exit_name = (inside[p] as ExtractionPoint).display_name
			_extract(pl, inside[p])
	for p in carried:
		var pl := player_of(int(p))
		if pl and not has_left(pl.peer_id):
			_extract_carried(pl, carried[p])
	for p in wait:
		var pl := player_of(int(p))
		if pl and pl.is_alive() and not has_left(pl.peer_id):
			_strand(pl, exit_name)
	evac_left = -1.0
	evac_wait = []
	channel = {}
	_all_in_t = 0.0
	_check_over()


## Раненый в зоне: выносят с собой — со всем, что при нём.
func _extract_carried(pl: Player, ext: ExtractionPoint) -> void:
	var e := extracted.duplicate()
	e[pl.peer_id] = ext.display_name + CARRIED_SUFFIX
	var v := loot_value.duplicate()
	v[pl.peer_id] = pl.inventory.value()
	extracted = e
	loot_value = v
	_clear_drag_of(pl.peer_id)


## Живой не успел к эвакуации группы: уходит из рейда без добычи — всё, что нёс, пропало
## (профиль не получает ничего, как при смерти; защищённый карман остаётся).
func _strand(pl: Player, exit_name: String) -> void:
	var s := stranded.duplicate()
	s[pl.peer_id] = exit_name
	stranded = s
	pl.inventory.buffer = []
	var d := drags.duplicate()
	d.erase(pl.peer_id)
	drags = d
	_clear_drag_of(pl.peer_id)


func _extract(pl: Player, ext: ExtractionPoint) -> void:
	# буфер окна лута — в рюкзак (что не влезло — остаётся лежать)
	var left := pl.inventory.flush_buffer()
	if not left.is_empty():
		spawn_drop(pl.global_position, "Выложено", left, LootContainer.Look.BAG)
	var e := extracted.duplicate()
	e[pl.peer_id] = ext.display_name
	var v := loot_value.duplicate()
	v[pl.peer_id] = pl.inventory.value()
	# дотащил раненого до точки — уходят оба
	var carried := player_of(drag_target_of(pl.peer_id))
	if carried and carried.is_downed():
		e[carried.peer_id] = ext.display_name + CARRIED_SUFFIX
		v[carried.peer_id] = carried.inventory.value()
	extracted = e
	loot_value = v
	var d := drags.duplicate()
	d.erase(pl.peer_id)
	drags = d
	_check_over()


# ---------------------------------------------------------------- раненые: поднять, тащить, сдаться

func drag_target_of(peer_id: int) -> int:
	return int(drags.get(peer_id, 0))


## Кто тащит раненого peer_id (null — никто).
func dragger_of(peer_id: int) -> Player:
	for k in drags:
		if int(drags[k]) == peer_id:
			return player_of(int(k))
	return null


## Раненый напарник рядом с me (для подсказки «поднять / тащить»).
func downed_mate_near(me: Player) -> Player:
	var best: Player = null
	var best_d := Balance.REVIVE_RADIUS
	for n in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl == null or pl == me or not pl.is_downed():
			continue
		var d := pl.global_position.distance_to(me.global_position)
		if d <= best_d:
			best = pl
			best_d = d
	return best


func request_revive(target_peer: int) -> void:
	if _is_host():
		_revive(multiplayer.get_unique_id(), target_peer)
	else:
		_rpc_revive.rpc_id(1, target_peer)


func request_drag(target_peer: int, on: bool) -> void:
	if _is_host():
		_drag(multiplayer.get_unique_id(), target_peer, on)
	else:
		_rpc_drag.rpc_id(1, target_peer, on)


func request_give_up() -> void:
	if _is_host():
		_give_up(multiplayer.get_unique_id())
	else:
		_rpc_give_up.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_revive(target_peer: int) -> void:
	if multiplayer.is_server():
		_revive(multiplayer.get_remote_sender_id(), target_peer)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_drag(target_peer: int, on: bool) -> void:
	if multiplayer.is_server():
		_drag(multiplayer.get_remote_sender_id(), target_peer, on)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_give_up() -> void:
	if multiplayer.is_server():
		_give_up(multiplayer.get_remote_sender_id())


## Хост: rescuer поднимает раненого target — рядом, сам не ранен, аптечка из его рюкзака.
func _revive(rescuer_peer: int, target_peer: int) -> void:
	var r := player_of(rescuer_peer)
	var t := player_of(target_peer)
	if r == null or t == null or not r.is_alive() or r.is_downed() or not t.is_downed():
		return
	if r.global_position.distance_to(t.global_position) > Balance.REVIVE_RADIUS + 0.8:
		return
	if r.inventory.remove("medkit", 1) == 0:
		return
	t.health.revive(Balance.REVIVE_HP)
	_clear_drag_of(target_peer)


func _drag(dragger_peer: int, target_peer: int, on: bool) -> void:
	var d := drags.duplicate()
	if not on:
		d.erase(dragger_peer)
		drags = d
		return
	var r := player_of(dragger_peer)
	var t := player_of(target_peer)
	if r == null or t == null or not r.is_alive() or r.is_downed() or not t.is_downed() or dragger_of(target_peer) != null:
		return
	if r.global_position.distance_to(t.global_position) > Balance.REVIVE_RADIUS + 0.8:
		return
	d[dragger_peer] = target_peer
	drags = d


func _give_up(peer_id: int) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_downed():
		pl.health.give_up()


func _clear_drag_of(target_peer: int) -> void:
	var d := drags.duplicate()
	for k in drags:
		if int(drags[k]) == target_peer:
			d.erase(k)
	drags = d


## Хост: тащить можно, пока оба на месте — тащащий цел, раненый лежит, не разошлись.
func _check_drags() -> void:
	if drags.is_empty():
		return
	var d := drags.duplicate()
	for k in drags:
		var r := player_of(int(k))
		var t := player_of(int(drags[k]))
		if r == null or t == null or not r.is_alive() or r.is_downed() or not t.is_downed() \
				or has_left(r.peer_id) or r.global_position.distance_to(t.global_position) > 3.0:
			d.erase(k)
	if d.size() != drags.size():
		drags = d


func _check_over() -> void:
	if participants.is_empty():
		return
	for peer in participants:
		if not has_left(int(peer)) and not dead.has(peer):
			return
	over = true


# ---------------------------------------------------------------- лут (просьбы к хосту)

## Взять из контейнера n штук id (n <= 0 — всё, что есть этого id).
func request_take(container: LootContainer, id: String, n: int) -> void:
	if _is_host():
		_take(multiplayer.get_unique_id(), container.get_path(), id, n)
	else:
		_rpc_take.rpc_id(1, container.get_path(), id, n)


## Взять запись idx из ящика целиком (со своим состоянием — именно этот экземпляр).
func request_take_idx(container: LootContainer, idx: int) -> void:
	if _is_host():
		_take_idx(multiplayer.get_unique_id(), container.get_path(), idx)
	else:
		_rpc_take_idx.rpc_id(1, container.get_path(), idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take_idx(path: NodePath, idx: int) -> void:
	if multiplayer.is_server():
		_take_idx(multiplayer.get_remote_sender_id(), path, idx)


func _take_idx(peer_id: int, path: NodePath, idx: int) -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path) if pl else null
	if c == null or not pl.is_alive() or idx < 0 or idx >= c.items.size():
		return
	var k := pl.inventory.add_entry((c.items[idx] as Dictionary).duplicate(true))
	if k > 0:
		c.take_at(idx, k)
		Audio.play("pin", c.global_position, -8.0)


## Снарядить магазины в рюкзаке россыпью из рюкзака.
func request_load_mags() -> void:
	if _is_host():
		_load_mags(multiplayer.get_unique_id())
	else:
		_rpc_load_mags.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_load_mags() -> void:
	if multiplayer.is_server():
		_load_mags(multiplayer.get_remote_sender_id())


func _load_mags(peer_id: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	if pl.inventory.load_all_mags() > 0:
		Audio.play("reload_rifle", pl.global_position, -8.0)
	elif peer_id == multiplayer.get_unique_id():
		notify("Нечем снаряжать — нет подходящих патронов")


## Разрядить магазин (сетка role, запись idx): патроны — в сетку into (открыт буфер — туда).
func request_unload(role: String, idx: int, into: String) -> void:
	if _is_host():
		_unload(multiplayer.get_unique_id(), role, idx, into)
	else:
		_rpc_unload.rpc_id(1, role, idx, into)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_unload(role: String, idx: int, into: String) -> void:
	if multiplayer.is_server():
		_unload(multiplayer.get_remote_sender_id(), role, idx, into)


func _unload(peer_id: int, role: String, idx: int, into: String) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	if pl.inventory.unload_mag(role, idx, into) > 0:
		Audio.play("pin", pl.global_position, -6.0)
	elif peer_id == multiplayer.get_unique_id():
		notify("Разрядить некуда или магазин пуст")


## Патроны (ammo_role, ammo_idx) перетащили на магазин (mag_role, mag_idx) — снарядить его.
func request_fill(ammo_role: String, ammo_idx: int, mag_role: String, mag_idx: int) -> void:
	if _is_host():
		_fill(multiplayer.get_unique_id(), ammo_role, ammo_idx, mag_role, mag_idx)
	else:
		_rpc_fill.rpc_id(1, ammo_role, ammo_idx, mag_role, mag_idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_fill(ammo_role: String, ammo_idx: int, mag_role: String, mag_idx: int) -> void:
	if multiplayer.is_server():
		_fill(multiplayer.get_remote_sender_id(), ammo_role, ammo_idx, mag_role, mag_idx)


func _fill(peer_id: int, ammo_role: String, ammo_idx: int, mag_role: String, mag_idx: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	if pl.inventory.fill_mag(ammo_role, ammo_idx, mag_role, mag_idx) > 0:
		Audio.play("reload_rifle", pl.global_position, -8.0)
	elif peer_id == multiplayer.get_unique_id():
		notify("Не снарядить: другой калибр, другие патроны или магазин полон")


## Закрыл окно лута — буфер в рюкзак; что не влезло — мешком под ноги.
func request_flush_buffer() -> void:
	if _is_host():
		_flush_buffer(multiplayer.get_unique_id())
	else:
		_rpc_flush_buffer.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_flush_buffer() -> void:
	if multiplayer.is_server():
		_flush_buffer(multiplayer.get_remote_sender_id())


func _flush_buffer(peer_id: int) -> void:
	var pl := player_of(peer_id)
	if pl == null:
		return
	var left := pl.inventory.flush_buffer()
	if not left.is_empty():
		spawn_drop(pl.global_position + Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw())) * 0.8, "Выложено", left, LootContainer.Look.BAG)
		if peer_id == multiplayer.get_unique_id():
			notify("Не всё влезло в рюкзак — остальное положено рядом")


func request_take_all(container: LootContainer) -> void:
	for it in container.items.duplicate(true):
		request_take(container, String(it.id), int(it.n))


func request_drop(id: String, n: int) -> void:
	if _is_host():
		_drop(multiplayer.get_unique_id(), id, n)
	else:
		_rpc_drop.rpc_id(1, id, n)


## Снять из слота в рюкзак (x, y — клетка, если перетащили в сетку).
func request_unequip(slot: String, x: int = -1, y: int = -1, r: bool = false) -> void:
	if _is_host():
		_unequip(multiplayer.get_unique_id(), slot, x, y, r)
	else:
		_rpc_unequip.rpc_id(1, slot, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_unequip(slot: String, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_unequip(multiplayer.get_remote_sender_id(), slot, x, y, r)


func _unequip(peer_id: int, slot: String, x: int, y: int, r: bool) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	if pl.inventory.unequip(slot, x, y, r):
		Audio.play("pin", pl.global_position, -10.0)
	elif peer_id == multiplayer.get_unique_id():
		notify("В рюкзаке нет места — выброси что-нибудь или брось это на землю (ПКМ)")


## Разложить рюкзак (или карман) по порядку — освободить место.
func request_sort(where: String = "backpack") -> void:
	if _is_host():
		_sort(multiplayer.get_unique_id(), where)
	else:
		_rpc_sort.rpc_id(1, where)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_sort(where: String) -> void:
	if multiplayer.is_server():
		_sort(multiplayer.get_remote_sender_id(), where)


func _sort(peer_id: int, where: String) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	if not pl.inventory.sort_grid(where) and peer_id == multiplayer.get_unique_id():
		notify("Не разложить — сначала освободи место")


## Выбросить предмет целиком (с обвесом, магазином, износом) — мешком на землю перед собой;
## where — "backpack" / "pocket" (индекс) или "equip:<слот>".
func request_drop_entry(where: String, idx: int) -> void:
	if _is_host():
		_drop_entry(multiplayer.get_unique_id(), where, idx)
	else:
		_rpc_drop_entry.rpc_id(1, where, idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_drop_entry(where: String, idx: int) -> void:
	if multiplayer.is_server():
		_drop_entry(multiplayer.get_remote_sender_id(), where, idx)


func _drop_entry(peer_id: int, where: String, idx: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var e := pl.inventory.take_entry(where, idx)
	if e.is_empty():
		return
	var fwd := Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw()))
	spawn_drop(pl.global_position + fwd * 0.8, "Выброшено", [e], LootContainer.Look.BAG)


## Владелец: отдать хосту снаряжение из профиля (вызывает уровень при появлении игрока).
func submit_loadout(lo: Dictionary) -> void:
	if _is_host():
		_give_loadout(multiplayer.get_unique_id(), lo.equipment, lo.backpack, lo.get("pocket", []), lo.get("pocket_grid", Vector2i.ZERO))
	else:
		_rpc_give_loadout.rpc_id(1, lo.equipment, lo.backpack, lo.get("pocket", []), lo.get("pocket_grid", Vector2i.ZERO))


## Потратить патроны/гранату из рюкзака (перезарядка, бросок).
func request_consume(id: String, n: int) -> void:
	if _is_host():
		_consume(multiplayer.get_unique_id(), id, n)
	else:
		_rpc_consume.rpc_id(1, id, n)


## Сетка рюкзака: передвинуть запись idx в (x, y) с поворотом r.
func request_move(idx: int, x: int, y: int, r: bool) -> void:
	if _is_host():
		_move_item(multiplayer.get_unique_id(), idx, x, y, r)
	else:
		_rpc_move_item.rpc_id(1, idx, x, y, r)


## Из контейнера — запись idx прямо в клетку (x, y) рюкзака или кармана (перетащили мышью).
func request_take_to(container: LootContainer, idx: int, x: int, y: int, r: bool, into: String = "backpack") -> void:
	if _is_host():
		_take_to(multiplayer.get_unique_id(), container.get_path(), idx, x, y, r, into)
	else:
		_rpc_take_to.rpc_id(1, container.get_path(), idx, x, y, r, into)


## Между рюкзаком и карманом (или внутри одного) — в клетку (x, y).
func request_grid_move(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> void:
	if _is_host():
		_grid_move(multiplayer.get_unique_id(), src, idx, dst, x, y, r)
	else:
		_rpc_grid_move.rpc_id(1, src, idx, dst, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_grid_move(src: String, idx: int, dst: String, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_grid_move(multiplayer.get_remote_sender_id(), src, idx, dst, x, y, r)


func _grid_move(peer_id: int, src: String, idx: int, dst: String, x: int, y: int, r: bool) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		pl.inventory.move_between(src, idx, dst, x, y, r)


## Из рюкзака (или буфера, кармана — from) — запись idx в контейнер (перетащили в окно лута).
func request_put(container: LootContainer, idx: int, from: String = "backpack") -> void:
	if _is_host():
		_put(multiplayer.get_unique_id(), container.get_path(), idx, from)
	else:
		_rpc_put.rpc_id(1, container.get_path(), idx, from)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_move_item(idx: int, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_move_item(multiplayer.get_remote_sender_id(), idx, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take_to(path: NodePath, idx: int, x: int, y: int, r: bool, into: String) -> void:
	if multiplayer.is_server():
		_take_to(multiplayer.get_remote_sender_id(), path, idx, x, y, r, into)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_put(path: NodePath, idx: int, from: String) -> void:
	if multiplayer.is_server():
		_put(multiplayer.get_remote_sender_id(), path, idx, from)


func _move_item(peer_id: int, idx: int, x: int, y: int, r: bool) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		pl.inventory.move(idx, x, y, r)


## Контейнер рядом с игроком (обыскивать можно только в радиусе).
func _near_container(pl: Player, path: NodePath) -> LootContainer:
	var c := get_node_or_null(path) as LootContainer
	if pl == null or c == null or not pl.is_alive() or has_left(pl.peer_id):
		return null
	if pl.global_position.distance_to(c.global_position) > Balance.INTERACT_RADIUS + 1.5:
		return null
	return c


func _take_to(peer_id: int, path: NodePath, idx: int, x: int, y: int, r: bool, into: String = "backpack") -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= c.items.size():
		return
	var k := pl.inventory.put_at((c.items[idx] as Dictionary).duplicate(true), x, y, r, into)
	if k > 0:
		c.take_at(idx, k)
		Audio.play("pin", c.global_position, -8.0)


func _put(peer_id: int, path: NodePath, idx: int, from: String = "backpack") -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= pl.inventory.list_of(from).size():
		return
	var out := pl.inventory.take_entry(from, idx)
	if out.is_empty():
		return
	var list := c.items.duplicate(true)
	ItemDb.add_to(list, out, Vector2i.ZERO)
	c.items = list
	c.rolled = true


## Перезарядка оружия в слоте (владелец шлёт своё состояние): хост меняет магазин из рюкзака или
## досыпает россыпью (Inventory.reload_slot); старый магазин, если некуда, — под ноги.
func request_reload(slot: String, state: Dictionary) -> void:
	if _is_host():
		_reload(multiplayer.get_unique_id(), slot, state)
	else:
		_rpc_reload.rpc_id(1, slot, state)


## Состояние оружия владельца (патроны, износ, прицел, фонари) — в снаряжение у хоста.
func request_weapon_state(slot: String, state: Dictionary) -> void:
	if _is_host():
		_weapon_state(multiplayer.get_unique_id(), slot, state)
	else:
		_rpc_weapon_state.rpc_id(1, slot, state)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_reload(slot: String, state: Dictionary) -> void:
	if multiplayer.is_server():
		_reload(multiplayer.get_remote_sender_id(), slot, state)


@rpc("any_peer", "call_remote", "unreliable_ordered")
func _rpc_weapon_state(slot: String, state: Dictionary) -> void:
	if multiplayer.is_server():
		_weapon_state(multiplayer.get_remote_sender_id(), slot, state)


func _reload(peer_id: int, slot: String, state: Dictionary) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var r := pl.inventory.reload_slot(slot, state)
	if not (r[1] as Dictionary).is_empty():
		spawn_drop(pl.global_position, "Выброшено", [r[1]], LootContainer.Look.BAG)


func _weapon_state(peer_id: int, slot: String, state: Dictionary) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		pl.inventory.apply_weapon_state(slot, state)


## Снять часть (обвес "mod:<точка>", плиту "plate:<сторона>", магазин "mag") с предмета — в рюкзак.
## where: "equip:<слот>", "backpack" (idx — запись рюкзака), "loot" (container — ящик / тело).
func request_strip(where: String, idx: int, part: String, container: LootContainer = null) -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_strip(multiplayer.get_unique_id(), where, idx, part, path)
	else:
		_rpc_strip.rpc_id(1, where, idx, part, path)


## Поставить предмет из рюкзака (src_idx) в предмет where/idx: обвес, плиту, магазин; hint — точка
## / сторона ("" — первая подходящая). Вытесненное — в рюкзак.
func request_fit(where: String, idx: int, src_idx: int, hint: String, container: LootContainer = null) -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_fit(multiplayer.get_unique_id(), where, idx, src_idx, hint, path)
	else:
		_rpc_fit.rpc_id(1, where, idx, src_idx, hint, path)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_strip(where: String, idx: int, part: String, path: NodePath) -> void:
	if multiplayer.is_server():
		_strip(multiplayer.get_remote_sender_id(), where, idx, part, path)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_fit(where: String, idx: int, src_idx: int, hint: String, path: NodePath) -> void:
	if multiplayer.is_server():
		_fit(multiplayer.get_remote_sender_id(), where, idx, src_idx, hint, path)


func _strip(peer_id: int, where: String, idx: int, part: String, path: NodePath) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var ok := false
	if where.begins_with("equip:"):
		ok = pl.inventory.strip_equipped(where.trim_prefix("equip:"), part)
	elif where == "backpack":
		ok = pl.inventory.strip_item(idx, part)
	elif where == "loot":
		var c := _near_container(pl, path)
		if c and idx >= 0 and idx < c.items.size():
			var list := c.items.duplicate(true)
			var r := Gear.strip(list[idx], part)
			if not (r[1] as Dictionary).is_empty() and pl.inventory.add_entry(r[1]) >= int((r[1] as Dictionary).n):
				list[idx] = r[0]
				c.items = list
				ok = true
	if ok:
		Audio.play("reload_pistol", pl.global_position, -6.0)
	elif peer_id == multiplayer.get_unique_id():
		notify("Некуда положить — освободи место в рюкзаке")


func _fit(peer_id: int, where: String, idx: int, src_idx: int, hint: String, path: NodePath) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive() or src_idx < 0 or src_idx >= pl.inventory.items.size():
		return
	var items := pl.inventory.items.duplicate(true)
	var src: Dictionary = items[src_idx]
	var target: Dictionary = {}
	var c: LootContainer = null
	if where.begins_with("equip:"):
		target = pl.inventory.equipment.get(where.trim_prefix("equip:"), {})
	elif where == "backpack" and idx >= 0 and idx < items.size() and idx != src_idx:
		target = items[idx]
	elif where == "loot":
		c = _near_container(pl, path)
		if c and idx >= 0 and idx < c.items.size():
			target = c.items[idx]
	if target.is_empty():
		return
	var r := Gear.fit(target, src, hint)
	if String(r[2]) != "":
		if peer_id == multiplayer.get_unique_id():
			notify(String(r[2]))
		return
	var one := ItemDb.remove_at(items, src_idx, 1)
	if one.is_empty():
		return
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(items, r[1], Balance.BACKPACK_GRID) == 0:
		if peer_id == multiplayer.get_unique_id():
			notify("Некуда положить снятое")
		return
	var fitted: Dictionary = r[0]
	if where.begins_with("equip:"):
		var eq := pl.inventory.equipment.duplicate(true)
		eq[where.trim_prefix("equip:")] = fitted
		pl.inventory.items = items
		pl.inventory.equipment = eq
	elif where == "backpack":
		# индекс цели мог сдвинуться, если источник стоял раньше неё
		var ti := idx - (1 if src_idx < idx else 0)
		for k in ["x", "y", "r"]:
			if target.has(k):
				fitted[k] = target[k]
		items[ti] = fitted
		pl.inventory.items = items
	else:
		var list := c.items.duplicate(true)
		list[idx] = fitted
		c.items = list
		pl.inventory.items = items
	Audio.play("reload_pistol", pl.global_position, -6.0)


## Обвес на оружие прямо в рейде: из рюкзака/кармана (src, idx) — на оружие в слоте weapon_slot.
func request_install_mod(weapon_slot: String, src: String, idx: int) -> void:
	if _is_host():
		_install_mod(multiplayer.get_unique_id(), weapon_slot, src, idx)
	else:
		_rpc_install_mod.rpc_id(1, weapon_slot, src, idx)


func request_remove_mod(weapon_slot: String, mod_slot: String) -> void:
	if _is_host():
		_remove_mod(multiplayer.get_unique_id(), weapon_slot, mod_slot)
	else:
		_rpc_remove_mod.rpc_id(1, weapon_slot, mod_slot)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_install_mod(weapon_slot: String, src: String, idx: int) -> void:
	if multiplayer.is_server():
		_install_mod(multiplayer.get_remote_sender_id(), weapon_slot, src, idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_remove_mod(weapon_slot: String, mod_slot: String) -> void:
	if multiplayer.is_server():
		_remove_mod(multiplayer.get_remote_sender_id(), weapon_slot, mod_slot)


func _install_mod(peer_id: int, weapon_slot: String, src: String, idx: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var why := pl.inventory.install_mod(weapon_slot, src, idx)
	if why == "":
		Audio.play("reload_pistol", pl.global_position, -6.0)
	elif peer_id == multiplayer.get_unique_id():
		notify(why)


func _remove_mod(peer_id: int, weapon_slot: String, mod_slot: String) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		if pl.inventory.remove_mod(weapon_slot, mod_slot):
			Audio.play("reload_pistol", pl.global_position, -6.0)
		elif peer_id == multiplayer.get_unique_id():
			notify("Некуда положить — освободи место в рюкзаке")


## Надеть / взять в руки предмет из рюкзака (индекс в items).
func request_equip(idx: int) -> void:
	if _is_host():
		_equip(multiplayer.get_unique_id(), idx)
	else:
		_rpc_equip.rpc_id(1, idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_give_loadout(eq: Dictionary, items: Array, pocket: Array, pgrid: Vector2i) -> void:
	if multiplayer.is_server():
		_give_loadout(multiplayer.get_remote_sender_id(), eq, items)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_consume(id: String, n: int) -> void:
	if multiplayer.is_server():
		_consume(multiplayer.get_remote_sender_id(), id, n)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_equip(idx: int) -> void:
	if multiplayer.is_server():
		_equip(multiplayer.get_remote_sender_id(), idx)


func request_use_med(id: String) -> void:
	# хроника: лечился (сколько раз — «аптечка без выходных»)
	var me := local_player()
	if me and me.is_alive() and me.inventory.has(id) and (me.is_downed() or me.health.hp < me.health.max_hp):
		analytics.on_heal(id)
	if _is_host():
		_use_med(multiplayer.get_unique_id(), id)
	else:
		_rpc_use_med.rpc_id(1, id)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take(path: NodePath, id: String, n: int) -> void:
	if multiplayer.is_server():
		_take(multiplayer.get_remote_sender_id(), path, id, n)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_drop(id: String, n: int) -> void:
	if multiplayer.is_server():
		_drop(multiplayer.get_remote_sender_id(), id, n)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_use_med(id: String) -> void:
	if multiplayer.is_server():
		_use_med(multiplayer.get_remote_sender_id(), id)


func _take(peer_id: int, path: NodePath, id: String, n: int) -> void:
	var pl := player_of(peer_id)
	var c := get_node_or_null(path) as LootContainer
	if pl == null or c == null or not pl.is_alive() or has_left(peer_id):
		return
	if pl.global_position.distance_to(c.global_position) > Balance.INTERACT_RADIUS + 1.5:
		return
	for i in range(c.items.size()):
		if String(c.items[i].id) != id:
			continue
		# экземпляр как есть (у брони — своя прочность): сколько влезет в рюкзак
		var entry: Dictionary = (c.items[i] as Dictionary).duplicate(true)
		entry.n = mini(n, int(entry.n)) if n > 0 else int(entry.n)
		var k := pl.inventory.add_entry(entry)
		if k > 0:
			c.take_at(i, k)
			Audio.play("pin", c.global_position, -8.0)
		return


## Хост: снаряжение из профиля игрока (рейд из убежища) — в его рюкзак и слоты.
func _give_loadout(peer_id: int, eq: Dictionary, items: Array, pocket: Array = [], pgrid: Vector2i = Vector2i.ZERO) -> void:
	var pl := player_of(peer_id)
	if pl == null:
		return
	pl.inventory.items = items.duplicate(true)
	pl.inventory.equipment = eq.duplicate(true)
	pl.inventory.pocket_grid = pgrid
	pl.inventory.pocket = pocket.duplicate(true)
	# пустые магазины и оружие — снарядить россыпью из рюкзака
	pl.inventory.prepare_mags()
	pl.inventory.loadout_ready = true


func _consume(peer_id: int, id: String, n: int) -> void:
	var pl := player_of(peer_id)
	if pl:
		pl.inventory.remove(id, n)


func _equip(peer_id: int, idx: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var spill := pl.inventory.equip_from_items(idx)
	if not spill.is_empty():
		spawn_drop(pl.global_position, "Выброшено", [spill], LootContainer.Look.BAG)


func _drop(peer_id: int, id: String, n: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var k := pl.inventory.remove(id, n)
	if k > 0:
		var fwd := Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw()))
		spawn_drop(pl.global_position + fwd * 0.8, "Выброшено", [{"id": id, "n": k}], LootContainer.Look.BAG)


## Лечение: предмет уходит сразу, здоровье прибавляется через use.time (если игрок ещё жив).
## Лёжа раненым: аптечка — подняться (REVIVE_SELF_SEC), бинт — дольше не истечь кровью.
func _use_med(peer_id: int, id: String) -> void:
	var pl := player_of(peer_id)
	var use: Dictionary = ItemDb.item(id).get("use", {})
	if pl == null or use.is_empty() or not pl.is_alive():
		return
	if pl.is_downed():
		if id != "medkit" and id != "bandage":
			return
		if pl.inventory.remove(id, 1) == 0:
			return
		var wait := Balance.REVIVE_SELF_SEC if id == "medkit" else float(use.time)
		get_tree().create_timer(wait).timeout.connect(func() -> void:
			if not is_instance_valid(pl) or not pl.is_downed():
				return
			if id == "medkit":
				pl.health.revive(Balance.REVIVE_HP)
				_clear_drag_of(pl.peer_id)
			else:
				pl.health.add_bleed(Balance.DOWN_BANDAGE_SEC))
		return
	if pl.health.hp >= pl.health.max_hp:
		return
	if pl.inventory.remove(id, 1) == 0:
		return
	get_tree().create_timer(float(use.time)).timeout.connect(func() -> void:
		if is_instance_valid(pl) and pl.is_alive():
			pl.health.heal(float(use.heal)))


## Хост: положить на землю контейнер с вещами (тело, выброшенное). В сети — через спавнер,
## чтобы появился у всех; содержимое едет в данных спавна.
## toss — откуда предмет «вываливается» к месту pos (смещение; ноль — появляется на месте).
## Хост: мародёр убит — «убить N» засчитывается тому, чья пуля добила (задания — в его профиле,
## на его компьютере), ему же метка убийства.
## info — для хроники рейда: {faction, grenade}.
func credit_kill(peer_id: int, arch: String = "", info: Dictionary = {}) -> void:
	# убил ИИ (ЧВК, жильцы, мародёры друг друга) — никому
	if peer_id <= 0:
		return
	if not Net.is_networked() or peer_id == multiplayer.get_unique_id():
		_kill_credited(arch, info)
	elif peer_id in multiplayer.get_peers():
		_rpc_kill_credit.rpc_id(peer_id, arch, info)


@rpc("authority", "call_remote", "reliable")
func _rpc_kill_credit(arch: String, info: Dictionary) -> void:
	_kill_credited(arch, info)


func _kill_credited(arch: String = "", info: Dictionary = {}) -> void:
	kill_credited.emit()
	analytics.on_kill(arch, info)
	Quests.event("kill", {"arch": arch})
	if Profile.pending_raid:
		Missions.on_kill()
	var me := local_player()
	if me and Net.is_networked() and not multiplayer.is_server():
		me.show_kill_marker()


# ---------------------------------------------------------------- хроника рейда: факты от хоста

## Хост: по игроку peer_id попали (сколько, кто, чем) — в его хронику.
func story_hit(peer_id: int, amount: float, attacker: int, src: Dictionary) -> void:
	if not Net.is_networked() or peer_id == multiplayer.get_unique_id():
		analytics.on_hit(amount, attacker, src)
	elif peer_id in multiplayer.get_peers():
		_rpc_story_hit.rpc_id(peer_id, amount, attacker, src)


@rpc("authority", "call_remote", "reliable")
func _rpc_story_hit(amount: float, attacker: int, src: Dictionary) -> void:
	analytics.on_hit(amount, attacker, src)


## Хост: игрок peer_id ранил мародёра — урон в его хронику.
func story_dealt(peer_id: int, amount: float) -> void:
	if not Net.is_networked() or peer_id == multiplayer.get_unique_id():
		analytics.on_dealt(amount)
	elif peer_id in multiplayer.get_peers():
		_rpc_story_dealt.rpc_id(peer_id, amount)


@rpc("authority", "call_remote", "reliable")
func _rpc_story_dealt(amount: float) -> void:
	analytics.on_dealt(amount)


## Хост: то, что было у всех на виду (мародёр подорвался на своей гранате), — в хронику каждого.
func story_world(kind: String, data: Dictionary) -> void:
	if not _is_host():
		return
	analytics.on_world(kind, data)
	if Net.is_networked():
		for peer in participants:
			if int(peer) != multiplayer.get_unique_id() and int(peer) in multiplayer.get_peers():
				_rpc_story_world.rpc_id(int(peer), kind, data)


@rpc("authority", "call_remote", "reliable")
func _rpc_story_world(kind: String, data: Dictionary) -> void:
	analytics.on_world(kind, data)


## Хост: игрок погиб — отчего (последнее попадание, кровопотеря, сдался) — в его хронику.
func _story_death(pl: Player) -> void:
	var h := pl.health
	var src := h.last_src
	var kind := String(src.get("kind", ""))
	var cause := {"cause": "ai", "attacker": h.last_attacker, "zone": h.last_zone,
		"arch": String(src.get("arch", "")), "faction": String(src.get("faction", "")), "weapon": String(src.get("weapon", ""))}
	var by_player := kind == "player" or (kind == "grenade" and String(src.get("by", "")) == "player")
	if h.died_of == "bleed" or h.died_of == "give_up":
		cause.cause = h.died_of
	elif kind == "grenade" and by_player and h.last_attacker == pl.peer_id:
		cause.cause = "self_grenade"
	elif by_player and h.last_attacker > 0 and h.last_attacker != pl.peer_id:
		cause.cause = "friendly"
	elif kind == "grenade":
		cause.cause = "grenade"
	if not Net.is_networked() or pl.peer_id == multiplayer.get_unique_id():
		analytics.on_death(cause)
	elif pl.peer_id in multiplayer.get_peers():
		_rpc_story_death.rpc_id(pl.peer_id, cause)


@rpc("authority", "call_remote", "reliable")
func _rpc_story_death(cause: Dictionary) -> void:
	analytics.on_death(cause)


func spawn_drop(pos: Vector3, display: String, list: Array, look: LootContainer.Look, toss: Vector3 = Vector3.ZERO) -> void:
	var data := {"name": "Drop_%d" % _drop_count, "pos": pos, "display": display, "items": list, "look": int(look), "toss": toss}
	_drop_count += 1
	if _drop_spawner:
		_drop_spawner.spawn(data)
	else:
		_drops.add_child(_make_drop(data))


func _make_drop(data: Dictionary) -> Node:
	var c := LOOT_SCENE.instantiate() as LootContainer
	c.name = String(data.name)
	c.position = data.pos
	c.display_name = String(data.display)
	c.look = int(data.look) as LootContainer.Look
	c.items = (data.items as Array).duplicate(true)
	c.rolled = true
	c.toss_from = data.get("toss", Vector3.ZERO)
	c.search_s = Balance.SEARCH_BODY_SEC
	return c


# ---------------------------------------------------------------- HUD (у каждого peer)

func _process(delta: float) -> void:
	_delta = delta
	var me := local_player()
	_update_channel_hud(me)
	_update_prompt(me)
	_toast_t -= delta
	_toast.visible = _toast_t > 0.0
	_update_summary(me)
	_save_profile(me)
	_save_death(me)
	_story_end(me)
	_quest_hooks(me)
	if Profile.pending_raid:
		# рейд из убежища: закончил (ушёл или погиб) — Enter возвращает в убежище
		# в коопе Enter — чат, в убежище — пробелом
		var go := Input.is_action_just_pressed("ui_accept") and not (Net.is_networked() and (Input.is_key_pressed(KEY_ENTER) or Input.is_key_pressed(KEY_KP_ENTER)))
		if me != null and (not me.is_alive() or has_left(me.peer_id)) and go:
			go_hideout()
	elif over and Input.is_action_just_pressed("reload"):
		_restart()


## Интерфейс рюкзака/лута открыт — игрок не стреляет и не целится (клики идут в кнопки).
func ui_open() -> bool:
	return ui != null and ui.is_open()


## Короткое сообщение внизу по центру («Заперто: нужен …»).
func notify(text: String) -> void:
	_toast.text = text
	_toast_t = 2.5


func _update_channel_hud(me: Player) -> void:
	_progress.visible = false
	_progress_label.visible = false
	if me == null or not me.is_alive() or has_left(me.peer_id) or over:
		return
	var here: ExtractionPoint = null
	for e in get_tree().get_nodes_in_group("extractions"):
		if e is ExtractionPoint and (e as ExtractionPoint).contains(me.global_position):
			here = e
			break
	var reason := extraction_block_reason(here) if here else ""
	var cur: Array = channel.get(me.peer_id, [])
	# я не в зоне (или она закрыта), а группа у выхода — успеть
	if cur.is_empty() and evac_left >= 0.0:
		_progress_label.visible = true
		_progress.visible = true
		_progress.max_value = Balance.EXTRACT_GROUP_SEC
		_progress.value = Balance.EXTRACT_GROUP_SEC - evac_left
		var where := ("%s закрыта: %s. " % [here.display_name, reason]) if here and reason != "" else ""
		_progress_label.text = "%sГРУППА У ВЫХОДА · %s — успей в зону, иначе вернёшься без добычи" % [where, _clock(evac_left)]
		return
	if here == null:
		return
	_progress_label.visible = true
	if reason != "":
		_progress_label.text = "%s — закрыто: %s" % [here.display_name, reason]
		return
	_progress.visible = true
	# ждём своих — общий отсчёт; все здесь — короткий отсчёт точки
	if not evac_wait.is_empty() and evac_left >= 0.0:
		var names: Array[String] = []
		for p in evac_wait:
			names.append(String(Net.player_names.get(p, participants.get(p, "напарник"))))
		_progress.max_value = Balance.EXTRACT_GROUP_SEC
		_progress.value = Balance.EXTRACT_GROUP_SEC - evac_left
		_progress_label.text = "ЭВАКУАЦИЯ · %s — через %s · ждём: %s" % [here.display_name, _clock(evac_left), ", ".join(names)]
		return
	var t := float(cur[1]) if cur.size() == 2 else 0.0
	_progress.max_value = here.channel_s
	_progress.value = t
	_progress_label.text = "ЭВАКУАЦИЯ · %s — %.1f с" % [here.display_name, maxf(0.0, here.channel_s - t)]


## «2:41».
static func _clock(sec: float) -> String:
	var s := int(ceil(sec))
	return "%d:%02d" % [s / 60, s % 60]


## Подсказка «F — …» у ближайшего предмета, с которым можно что-то сделать. Рядом раненый
## напарник — «поднять» (держать F, аптечка) и «тащить» (X).
func _update_prompt(me: Player) -> void:
	_prompt.visible = false
	if me == null or not me.is_alive() or has_left(me.peer_id) or ui.is_looting():
		_revive_t = 0.0
		return
	if me.is_downed():
		_revive_t = 0.0
		return
	var mate := downed_mate_near(me)
	if mate:
		_prompt.visible = true
		var dragging := drag_target_of(me.peer_id) == mate.peer_id
		_prompt.text = "%s (держать) — поднять (аптечка)   ·   %s — %s" % [PauseMenu.key_name("interact"), PauseMenu.key_name("drag"), "отпустить" if dragging else "тащить"]
		if Input.is_action_just_pressed("drag") and not PauseMenu.shown:
			request_drag(mate.peer_id, not dragging)
		if Input.is_action_pressed("interact") and not PauseMenu.shown:
			if not me.inventory.has("medkit"):
				if Input.is_action_just_pressed("interact"):
					notify("Нужна аптечка")
			else:
				_revive_t += _delta
				_progress.visible = true
				_progress_label.visible = true
				_progress.max_value = Balance.REVIVE_SEC
				_progress.value = _revive_t
				_progress_label.text = "Поднимаю: %s" % String(Net.player_names.get(mate.peer_id, participants.get(mate.peer_id, "напарник")))
				if _revive_t >= Balance.REVIVE_SEC:
					_revive_t = 0.0
					request_revive(mate.peer_id)
		else:
			_revive_t = 0.0
		return
	_revive_t = 0.0
	if drag_target_of(me.peer_id) != 0:
		# раненый отстал (проверит хост) — отпустить можно и так
		_prompt.visible = true
		_prompt.text = "%s — отпустить" % PauseMenu.key_name("drag")
		if Input.is_action_just_pressed("drag"):
			request_drag(drag_target_of(me.peer_id), false)
		return
	var best: Interactable = null
	var best_d := INF
	for n in get_tree().get_nodes_in_group("interactables"):
		var it := n as Interactable
		if it == null or not it.can_use():
			continue
		var d := it.global_position.distance_to(me.global_position)
		if d < Balance.INTERACT_RADIUS and d < best_d:
			best = it
			best_d = d
	if best == null:
		return
	_prompt.visible = true
	_prompt.text = PauseMenu.key_name("interact") + " — " + best.prompt()
	if Input.is_action_just_pressed("interact"):
		if best is LootContainer:
			ui.start_search(best as LootContainer)
		best.request_use()


func _update_summary(me: Player) -> void:
	var show := over or (me != null and (not me.is_alive() or has_left(me.peer_id)))
	var story := show and chronicle != null
	_summary.visible = show and not story
	_summary_bg.visible = show and not story
	_story_panel.visible = story
	if story:
		_fit_story_panel()
	if not show:
		return
	var lines: Array[String] = []
	# сначала — как кончилось у меня, потом — у группы
	var mine := ""
	if me == null:
		mine = ""
	elif is_extracted(me.peer_id):
		mine = "ЭВАКУИРОВАН · " + String(extracted[me.peer_id])
	elif stranded.has(me.peer_id):
		mine = "НЕ УСПЕЛ К ЭВАКУАЦИИ · группа ушла через «%s», ты вернулся без добычи" % String(stranded[me.peer_id])
	elif not me.is_alive():
		mine = "УБИТ"
	if over:
		lines.append("РЕЙД ОКОНЧЕН" + (" · " + mine if mine != "" else ""))
	else:
		lines.append(mine)
	lines.append("")
	for peer in participants:
		# имя из лобби может прийти позже появления игрока — берём самое свежее
		var who := String(Net.player_names.get(peer, participants[peer]))
		if extracted.has(peer):
			lines.append("%s — эвакуировался (%s), вынес на %s ₽" % [who, String(extracted[peer]), InventoryUI.money(int(loot_value.get(peer, 0)))])
		elif stranded.has(peer):
			lines.append("%s — не успел к эвакуации, вернулся без добычи" % who)
		elif dead.has(peer):
			lines.append("%s — погиб, рюкзак остался в рейде" % who)
		else:
			lines.append("%s — ещё в рейде" % who)
	lines.append("")
	if Profile.pending_raid:
		lines.append("Пробел — в убежище   ·   Enter — чат" if Net.is_networked() else "Enter — в убежище")
	elif over:
		lines.append("R — новый рейд" if _is_host() else "ждём хоста")
	else:
		lines.append("ждём остальных")
	if story:
		_story_footer.text = "\n".join(lines)
	else:
		_summary.text = "\n".join(lines)


## Свой рейд окончен — собрать хронику, один раз (задания и профиль к этому времени уже
## записаны). Причину смерти присылает хост; не пришла за полторы секунды — без неё.
func _story_end(me: Player) -> void:
	if chronicle != null or me == null:
		return
	if analytics.outcome == "":
		if is_extracted(me.peer_id):
			analytics.on_extracted(String(extracted[me.peer_id]))
		elif stranded.has(me.peer_id):
			analytics.on_stranded(String(stranded[me.peer_id]))
		elif not me.is_alive():
			_chronicle_wait += _delta
			if _chronicle_wait < 1.5:
				return
			analytics.on_death({})
		else:
			return
	# в историю — только настоящие рейды (из убежища); песочница профиль не трогает
	chronicle = RaidStory.make(analytics, Profile.pending_raid)
	if Profile.pending_raid:
		Profile.save()
	_fill_story_panel()


## Эвакуировался (владелец): снаряжение, рюкзак и патроны из магазинов — обратно в профиль.
## Погиб — ничего: снаряжение снято с профиля при входе в рейд и осталось в теле.
func _save_profile(me: Player) -> void:
	if _profile_saved or me == null or not me.loadout_mode or not is_extracted(me.peer_id):
		return
	_profile_saved = true
	var items: Array = me.inventory.items.duplicate(true)
	# оружие — с тем, что в магазине сейчас, износом, прицелом, фонарями (у владельца свежее хоста)
	Profile.return_loadout(me.equipment_state(), items, int(loot_value.get(me.peer_id, 0)))
	# Михалыч доплачивает за риск условий: доля ценности вынесенного
	var bonus := int(float(loot_value.get(me.peer_id, 0)) * RaidConditions.pay_bonus())
	if bonus > 0:
		Profile.money += bonus
		Profile.save()
		notify("Михалыч доплатит за риск: %s ₽" % InventoryUI.money(bonus))
	Profile.set_pocket(me.inventory.pocket)
	if RaidEvents.current:
		RaidEvents.current.on_local_extracted(me)
	# задание «уйти через точку»: в итоге рейда — видимое имя, задания знают имя узла
	for e in get_tree().get_nodes_in_group("extractions"):
		var ext := e as ExtractionPoint
		if ext and ext.display_name == String(extracted.get(me.peer_id, "")):
			Missions.on_extract(String(ext.name))
			break


## Погиб или не успел к эвакуации группы (свой игрок, рейд из убежища): взятое потеряно, карман
## остаётся с тобой, «выжить подряд» — заново.
func _save_death(me: Player) -> void:
	if _death_saved or me == null or not me.loadout_mode or (me.is_alive() and not stranded.has(me.peer_id)):
		return
	_death_saved = true
	Profile.set_pocket(me.inventory.pocket)
	Missions.on_death()


## Сюжет: эвакуировался (с тем, что вынес) или погиб — сообщить квестам один раз.
func _quest_hooks(me: Player) -> void:
	if quest_world == null or me == null:
		return
	if is_extracted(me.peer_id):
		quest_world.on_local_extracted()
	elif not me.is_alive() or stranded.has(me.peer_id):
		quest_world.on_local_lost()


## Охрана сюжетного места: ставит хост (клиент просит).
func request_quest_guards(pos: Vector3, n: int, radius: float) -> void:
	if _is_host():
		_spawn_quest_guards(pos, n, radius)
	else:
		_rpc_quest_guards.rpc_id(1, pos, n, radius)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_quest_guards(pos: Vector3, n: int, radius: float) -> void:
	if multiplayer.is_server():
		_spawn_quest_guards(pos, n, radius)


func _spawn_quest_guards(pos: Vector3, n: int, radius: float) -> void:
	var lvl := get_parent()
	if lvl and lvl.has_method("spawn_guards"):
		lvl.call("spawn_guards", pos, n, radius)


## В убежище: из сети выходим, рейд забыт.
## В убежище. В сети связь не рвётся — встречаемся в убежище; хост уходит — рейд кончается и
## у остальных (кто не вышел — теряет взятое, как при смерти).
func go_hideout() -> void:
	if Net.is_host():
		_host_left.rpc()
	Profile.pending_raid = false
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)


@rpc("authority", "call_remote", "reliable")
func _host_left() -> void:
	notify("Хост ушёл из рейда — все в убежище")
	await get_tree().create_timer(2.5).timeout
	if is_inside_tree():
		Profile.pending_raid = false
		get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)


## Новый рейд: хост переводит всех заново в сектор; без сети — перезагрузка сцены.
func _restart() -> void:
	if not Net.is_networked():
		get_tree().reload_current_scene()
	elif multiplayer.is_server():
		Net.start_level.rpc(get_tree().current_scene.scene_file_path, RaidConditions.current)


func _build_hud() -> void:
	_hud = CanvasLayer.new()
	_hud.layer = 11
	add_child(_hud)
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hud.add_child(root)
	_progress = ProgressBar.new()
	_progress.show_percentage = false
	_progress.anchor_left = 0.5
	_progress.anchor_right = 0.5
	_progress.anchor_top = 1.0
	_progress.anchor_bottom = 1.0
	_progress.offset_left = -220
	_progress.offset_right = 220
	_progress.offset_top = -150
	_progress.offset_bottom = -136
	_progress.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(0.35, 0.9, 0.45)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.55)
	_progress.add_theme_stylebox_override("fill", fill)
	_progress.add_theme_stylebox_override("background", bg)
	root.add_child(_progress)
	_progress_label = _label(root, -186, 22, Color(0.75, 1.0, 0.78))
	_prompt = _label(root, -110, 22, Color(1.0, 0.92, 0.7))
	_toast = _label(root, -230, 20, Color(1.0, 0.6, 0.45))
	# итог — на затемнённой полосе через весь экран
	_summary_bg = ColorRect.new()
	_summary_bg.color = Color(0, 0, 0, 0.6)
	_summary_bg.anchor_right = 1.0
	_summary_bg.anchor_top = 0.5
	_summary_bg.anchor_bottom = 0.5
	_summary_bg.offset_top = -190
	_summary_bg.offset_bottom = 190
	_summary_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_summary_bg.visible = false
	root.add_child(_summary_bg)
	_summary = Label.new()
	_summary.set_anchors_preset(Control.PRESET_CENTER)
	_summary.offset_left = -420
	_summary.offset_right = 420
	_summary.offset_top = -170
	_summary.offset_bottom = 170
	_summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_summary.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_summary.add_theme_font_size_override("font_size", 24)
	_summary.add_theme_color_override("font_color", Color(0.95, 0.9, 0.8))
	_summary.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_summary.add_theme_constant_override("outline_size", 8)
	_summary.visible = false
	root.add_child(_summary)
	_build_story_panel(root)


## Экран итога рейда: «ХРОНИКА РЕЙДА» (2–5 абзацев), «ВЕРДИКТ» (одна фраза), статистика.
func _build_story_panel(root: Control) -> void:
	var amber := Color(1.0, 0.78, 0.4)
	var paper := Color(0.93, 0.9, 0.84)
	# по центру, высота — по тексту (_fit_story_panel), длинный — прокрутка
	_story_panel = PanelContainer.new()
	_story_panel.set_anchors_preset(Control.PRESET_CENTER)
	_story_panel.offset_left = -470
	_story_panel.offset_right = 470
	_story_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.055, 0.06, 0.93)
	sb.border_color = Color(amber, 0.45)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(4)
	sb.set_content_margin_all(26)
	_story_panel.add_theme_stylebox_override("panel", sb)
	_story_panel.visible = false
	root.add_child(_story_panel)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.mouse_filter = Control.MOUSE_FILTER_PASS
	_story_panel.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 10)
	scroll.add_child(box)
	_story_box = box
	box.add_child(_story_heading("ХРОНИКА РЕЙДА", amber))
	_story_text = Label.new()
	_story_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_story_text.add_theme_font_size_override("font_size", 17)
	_story_text.add_theme_color_override("font_color", paper)
	_story_text.add_theme_constant_override("line_spacing", 3)
	box.add_child(_story_text)
	var gap := Control.new()
	gap.custom_minimum_size.y = 6
	box.add_child(gap)
	box.add_child(_story_heading("ВЕРДИКТ", amber))
	_story_verdict = Label.new()
	_story_verdict.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_story_verdict.add_theme_font_size_override("font_size", 21)
	_story_verdict.add_theme_color_override("font_color", Color(1.0, 0.9, 0.7))
	box.add_child(_story_verdict)
	box.add_child(HSeparator.new())
	_story_stats = GridContainer.new()
	_story_stats.columns = 2
	_story_stats.add_theme_constant_override("h_separation", 24)
	_story_stats.add_theme_constant_override("v_separation", 3)
	box.add_child(_story_stats)
	box.add_child(HSeparator.new())
	_story_footer = Label.new()
	_story_footer.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_story_footer.add_theme_font_size_override("font_size", 15)
	_story_footer.add_theme_color_override("font_color", Color(paper, 0.75))
	box.add_child(_story_footer)


func _story_heading(text: String, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", 15)
	l.add_theme_color_override("font_color", color)
	return l


## Высота окна итога — по содержимому, не выше экрана без полей.
func _fit_story_panel() -> void:
	var margin := 52.0
	var h := minf(_story_box.get_combined_minimum_size().y + margin, _story_panel.get_viewport_rect().size.y - 72.0)
	_story_panel.offset_top = -h * 0.5
	_story_panel.offset_bottom = h * 0.5


## Хроника готова — заполнить экран итога.
func _fill_story_panel() -> void:
	_story_text.text = "\n\n".join(chronicle.paragraphs)
	_story_verdict.text = chronicle.verdict
	for c in _story_stats.get_children():
		c.queue_free()
	for row in chronicle.stats:
		var k := Label.new()
		k.text = String(row[0])
		k.add_theme_font_size_override("font_size", 15)
		k.add_theme_color_override("font_color", Color(0.7, 0.68, 0.62))
		var v := Label.new()
		v.text = String(row[1])
		v.add_theme_font_size_override("font_size", 15)
		v.add_theme_color_override("font_color", Color(0.95, 0.93, 0.88))
		_story_stats.add_child(k)
		_story_stats.add_child(v)


## Строка внизу по центру на высоте y от низа экрана.
func _label(root: Control, y: float, size: int, color: Color) -> Label:
	var l := Label.new()
	l.anchor_left = 0.5
	l.anchor_right = 0.5
	l.anchor_top = 1.0
	l.anchor_bottom = 1.0
	l.offset_left = -500
	l.offset_right = 500
	l.offset_top = y
	l.offset_bottom = y + 30
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	l.add_theme_constant_override("outline_size", 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	l.visible = false
	root.add_child(l)
	return l
