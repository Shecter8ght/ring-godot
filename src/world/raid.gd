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
const LOOSE_SCENE := preload("res://scenes/world/loose_loot.tscn")
const SUPPLY_DROP_NAME := "Редкий груз снабжения"
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
## Пропал из рейда посреди рейда: отключился, вылетел или ушёл в убежище через меню — {peer: true}.
## Группа его не ждёт у эвакуации, и рейд может закончиться без него; вещи остаются мешком.
var gone: Dictionary = {}
## Обмен вещами между игроками: {peer: [с кем, готов]} — запись у каждого из двоих. Вещи лежат в
## Inventory.trade каждого; оба готовы — хост меняет их местами. Окно — autoload Trade.
var trades: Dictionary = {}
var _trade_sigs: Dictionary = {}
var _trade_hold_t: float = 0.0
var _seen_in_raid: Dictionary = {}
var _gone_poll: float = 0.0
var _all_in_t: float = 0.0
## Погибшие: peer_id -> true (хост — по сигналу Health).
var dead: Dictionary = {}
## Поштучные операции с предметами (хост): peer -> [MagOps, путь ящика или пусто].
var _ops: Dictionary = {}
## Кто кого тащит: peer тащащего -> peer раненого (хост проверяет, видят все).
var drags: Dictionary = {}
var over: bool = false

var ui: InventoryUI
## Владелец уже записал итог рейда в профиль (эвакуация) — один раз.
var _profile_saved: bool = false
var _death_saved: bool = false
var _drops: Node3D
## Подпись мешка с выброшенным из рюкзака (в него же складывается следующее выброшенное рядом).
const DROP_NAME := "Выброшено"
var _drop_spawner: MultiplayerSpawner
var _drop_count: int = 0

var _hud: CanvasLayer
var _progress: ProgressBar
var _progress_label: Label
var _prompt: Label
var _toast: Label
var _toast_t: float = 0.0
var _evac_sound_second: int = -1
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
var recovery: WeaponRecovery
var _exit_receipt: Dictionary = {}
## Сигнал снабжения общий на рейд; хост хранит время и факт единственного сброса.
var supply_state: Dictionary = {}
var _supply_visual: Node3D


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
	recovery = WeaponRecovery.new()
	recovery.name = "WeaponRecovery"
	recovery.raid = self
	add_child(recovery)
	analytics = RaidAnalytics.new()
	analytics.name = "Analytics"
	add_child(analytics)
	ui = InventoryUI.new()
	ui.name = "InventoryUI"
	add_child(ui)
	if Net.is_networked():
		_setup_sync()
		# отключился — сразу, пока его узел ещё в дереве (вещи — мешком); остальное ловит _check_gone
		multiplayer.peer_disconnected.connect(func(id: int) -> void:
			if _is_host() and participants.has(id) and not gone.has(id):
				_peer_gone(id))
		_drop_spawner = MultiplayerSpawner.new()
		_drop_spawner.name = "DropSpawner"
		add_child(_drop_spawner)
		_drop_spawner.spawn_path = _drops.get_path()
		_drop_spawner.spawn_function = _make_drop


func _exit_tree() -> void:
	if recovery != null:
		recovery.finish()
	if current == self:
		current = null


## Хост — авторитет (умалчиваемый 1). Словари маленькие — шлём постоянно (ALWAYS): так их
## получает и peer, чей узел создался позже изменения.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	sync.name = "Sync"
	sync.replication_interval = 0.1
	var config := SceneReplicationConfig.new()
	for prop in [".:participants", ".:switches", ".:extracted", ".:loot_value", ".:dead", ".:over", ".:channel", ".:drags", ".:evac_left", ".:evac_wait", ".:stranded", ".:supply_state", ".:gone", ".:trades"]:
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
	_check_gone(delta)
	_tick_trades()
	_check_drags()
	_tick_ops(delta)
	_update_evac(delta)


# ---------------------------------------------------------------- обмен вещами между игроками

## Предложить обмен игроку target: у обоих откроется окно (Trade).
func request_trade(target: int) -> void:
	if _is_host():
		_trade_start(multiplayer.get_unique_id(), target)
	else:
		_rpc_trade.rpc_id(1, "start", target)


## «Передать» нажато / отжато.
func request_trade_ready(on: bool) -> void:
	if _is_host():
		_trade_ready(multiplayer.get_unique_id(), on)
	else:
		_rpc_trade.rpc_id(1, "ready", 1 if on else 0)


## Отменить обмен: вещи из буфера возвращаются хозяевам.
func request_trade_close() -> void:
	if _is_host():
		_trade_end(multiplayer.get_unique_id(), "Обмен отменён")
	else:
		_rpc_trade.rpc_id(1, "close", 0)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_trade(kind: String, value: int) -> void:
	if not multiplayer.is_server():
		return
	var peer := multiplayer.get_remote_sender_id()
	match kind:
		"start":
			_trade_start(peer, value)
		"ready":
			_trade_ready(peer, value != 0)
		"close":
			_trade_end(peer, "Обмен отменён")


## Годится ли игрок для обмена: жив, на ногах, в рейде.
func _can_trade(peer_id: int) -> bool:
	var pl := player_of(peer_id)
	return pl != null and pl.is_alive() and not pl.is_downed() and not has_left(peer_id) and not gone.has(peer_id)


func _trade_start(a: int, b: int) -> void:
	if a == b or trades.has(a) or trades.has(b) or not _can_trade(a) or not _can_trade(b):
		if trades.has(b):
			_tell(a, "Напарник уже меняется с другим")
		return
	if player_of(a).global_position.distance_to(player_of(b).global_position) > float(Balance.TRADE.break_m):
		_tell(a, "Подойди ближе к напарнику")
		return
	_cancel_op(a)
	_cancel_op(b)
	var t := trades.duplicate(true)
	t[a] = [b, false]
	t[b] = [a, false]
	trades = t
	_trade_sigs[mini(a, b)] = _trade_sig(a, b)


func _trade_sig(a: int, b: int) -> String:
	var pa := player_of(a)
	var pb := player_of(b)
	return str(pa.inventory.trade if pa else []) + "|" + str(pb.inventory.trade if pb else [])


func _trade_ready(peer_id: int, on: bool) -> void:
	if not trades.has(peer_id):
		return
	var other := int((trades[peer_id] as Array)[0])
	var t := trades.duplicate(true)
	(t[peer_id] as Array)[1] = on
	trades = t
	if on and bool((trades.get(other, [0, false]) as Array)[1]):
		_trade_commit(peer_id, other)


## Оба готовы: вещи из половин буфера меняются хозяевами (в рюкзак). Кому-то не влезает — никому.
func _trade_commit(a: int, b: int) -> void:
	var pa := player_of(a)
	var pb := player_of(b)
	if pa == null or pb == null:
		_trade_end(a, "Обмен сорвался")
		return
	var a_items: Array = pa.inventory.items.duplicate(true)
	var b_items: Array = pb.inventory.items.duplicate(true)
	for pair: Array in [[pb.inventory.trade, a_items, pa.inventory.backpack_grid(), a], [pa.inventory.trade, b_items, pb.inventory.backpack_grid(), b]]:
		for e: Dictionary in pair[0]:
			var one: Dictionary = e.duplicate(true)
			for k in ["x", "y", "r", "op"]:
				one.erase(k)
			if ItemDb.add_to(pair[1], one, pair[2]) < int(one.get("n", 1)):
				var who := String(participants.get(int(pair[3]), "напарника"))
				for peer: int in [a, b]:
					_tell(peer, "Обмен не прошёл: у %s не хватает места в рюкзаке" % who)
				var t := trades.duplicate(true)
				(t[a] as Array)[1] = false
				(t[b] as Array)[1] = false
				trades = t
				return
	var gave_a := pa.inventory.trade.size()
	var gave_b := pb.inventory.trade.size()
	pa.inventory.trade = []
	pb.inventory.trade = []
	pa.inventory.items = a_items
	pb.inventory.items = b_items
	var t2 := trades.duplicate(true)
	t2.erase(a)
	t2.erase(b)
	trades = t2
	_trade_sigs.erase(mini(a, b))
	Audio.play("item_move", pa.global_position, -8.0)
	_tell(a, "Обмен с %s: отдал %d, получил %d" % [String(participants.get(b, "напарником")), gave_a, gave_b])
	_tell(b, "Обмен с %s: отдал %d, получил %d" % [String(participants.get(a, "напарником")), gave_b, gave_a])


## Обмен окончен без сделки: у каждого из двоих буфер возвращается в рюкзак (не влезло — мешком под ноги).
func _trade_end(peer_id: int, why: String) -> void:
	if not trades.has(peer_id):
		return
	var other := int((trades[peer_id] as Array)[0])
	for peer: int in [peer_id, other]:
		var pl := player_of(peer)
		if pl and not pl.inventory.trade.is_empty():
			var back: Array = pl.inventory.trade.duplicate(true)
			pl.inventory.trade = []
			var list: Array = pl.inventory.items.duplicate(true)
			var spill: Array = []
			for e: Dictionary in back:
				for k in ["x", "y", "r", "op"]:
					e.erase(k)
				var left := int(e.get("n", 1)) - ItemDb.add_to(list, e, pl.inventory.backpack_grid())
				if left > 0:
					e["n"] = left
					spill.append(e)
			pl.inventory.items = list
			if not spill.is_empty():
				spawn_drop(pl.global_position, DROP_NAME, spill, LootContainer.Look.BAG)
		if why != "":
			_tell(peer, why)
	var t := trades.duplicate(true)
	t.erase(peer_id)
	t.erase(other)
	trades = t
	_trade_sigs.erase(mini(peer_id, other))


## Хост, каждый тик: кто-то упал, ушёл, отошёл — обмен рвётся; буфер тронули — готовность снята у обоих.
func _tick_trades() -> void:
	if trades.is_empty():
		return
	for raw: Variant in trades.keys():
		var a := int(raw)
		if not trades.has(a):
			continue
		var b := int((trades[a] as Array)[0])
		if a > b:
			continue
		if not _can_trade(a) or not _can_trade(b):
			_trade_end(a, "Обмен прерван")
			continue
		if player_of(a).global_position.distance_to(player_of(b).global_position) > float(Balance.TRADE.break_m):
			_trade_end(a, "Разошлись — обмен отменён")
			continue
		var sig := _trade_sig(a, b)
		if sig != String(_trade_sigs.get(a, "")):
			_trade_sigs[a] = sig
			if bool((trades[a] as Array)[1]) or bool((trades[b] as Array)[1]):
				var t := trades.duplicate(true)
				(t[a] as Array)[1] = false
				(t[b] as Array)[1] = false
				trades = t


## Хост: кто из участников пропал (нет соединения или его сцена уже не рейд) — раз в полсекунды.
## «Был в рейде» запоминается: пока гость ещё грузит уровень, его сцена тоже не «raid».
func _check_gone(delta: float) -> void:
	if not Net.is_networked():
		return
	_gone_poll -= delta
	if _gone_poll > 0.0:
		return
	_gone_poll = 0.5
	var me: int = multiplayer.get_unique_id()
	var peers: PackedInt32Array = multiplayer.get_peers()
	for raw: Variant in participants.keys():
		var peer: int = int(raw)
		if peer == me or gone.has(peer):
			continue
		if not peer in peers:
			_peer_gone(peer)
		elif Net.visible_in(peer, "raid"):
			_seen_in_raid[peer] = true
		elif _seen_in_raid.has(peer) and String(Net.peer_scene.get(peer, "")) != "loading":
			_peer_gone(peer)


## Участник пропал: что нёс — мешком на месте (свои подберут), сам он больше не в рейде.
func _peer_gone(peer_id: int) -> void:
	var g := gone.duplicate()
	g[peer_id] = true
	gone = g
	_cancel_op(peer_id)
	var who := String(participants.get(peer_id, "Игрок"))
	var pl := player_of(peer_id)
	if pl and not has_left(peer_id) and not dead.has(peer_id):
		if pl.is_alive() and not pl.inventory.items.is_empty():
			spawn_drop(pl.global_position, "Вещи: " + who, pl.inventory.take_all(), LootContainer.Look.BAG)
		var d := drags.duplicate()
		d.erase(peer_id)
		drags = d
		_clear_drag_of(peer_id)
	if pl:
		pl.remove_from_group("players")
		if not pl.is_queued_for_deletion():
			pl.queue_free()
	print("raid: участник пропал peer=", peer_id)
	Net.broadcast_scene(self, &"_rpc_notify_all", ["%s вышел из игры — его вещи остались мешком" % who])
	_check_over()


@rpc("authority", "call_remote", "reliable")
func _rpc_notify_all(text: String) -> void:
	notify(text)


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
		if pl == null or not pl.is_alive() or has_left(pl.peer_id) or gone.has(pl.peer_id) or pl.is_queued_for_deletion():
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
	_trade_end(pl.peer_id, "")
	var e := extracted.duplicate()
	e[pl.peer_id] = ext.display_name + CARRIED_SUFFIX
	var v := loot_value.duplicate()
	v[pl.peer_id] = pl.inventory.value()
	extracted = e
	loot_value = v
	Audio.play("raid_leave", pl.global_position)
	_clear_drag_of(pl.peer_id)
	_quest_extracted(pl)


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
	_trade_end(pl.peer_id, "")
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
	Audio.play("raid_leave", pl.global_position)
	_quest_extracted(pl)
	if carried and carried.is_downed():
		_quest_extracted(carried)
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
	Audio.play("revive", t.global_position + Vector3.UP)
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
	Audio.play("drag", t.global_position)


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
		if not has_left(int(peer)) and not dead.has(peer) and not gone.has(peer):
			return
	over = true
	if recovery != null:
		recovery.finish()


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
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	var c := _near_container(pl, path) if pl else null
	if c == null or not pl.is_alive() or idx < 0 or idx >= c.items.size():
		return
	var id := String(c.items[idx].id)
	var k := pl.inventory.add_entry((c.items[idx] as Dictionary).duplicate(true))
	if k > 0:
		c.take_at(idx, k)
		Audio.play(_pickup_sound(id), c.global_position, -8.0)


# ---------------------------------------------------------------- предметы поштучно (MagOps)

## Снарядить один магазин, разрядить магазин, вынуть плиты из жилета — поштучно, не мгновенно (MagOps
## на хосте; у игрока одна операция — новая прерывает старую). role — где предмет: "backpack",
## "pocket", "buffer" или "loot" (ящик container). load: ammo и src — с перетаскивания (этот патрон из
## этой сетки), иначе — любые подходящие патроны игрока; plates: side — только эту сторону.
func request_item_op(kind: String, role: String, idx: int, container: LootContainer = null, ammo: String = "", src: String = "", side: String = "") -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_item_op(multiplayer.get_unique_id(), kind, role, idx, path, ammo, src, side)
	else:
		_rpc_item_op.rpc_id(1, kind, role, idx, path, ammo, src, side)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_item_op(kind: String, role: String, idx: int, path: NodePath, ammo: String, src: String, side: String) -> void:
	if multiplayer.is_server():
		_item_op(multiplayer.get_remote_sender_id(), kind, role, idx, path, ammo, src, side)


## Хост: игрок peer_id для просьбы what (снарядить, сортировать, надеть…) — или null с отказом. Отказ
## пишется в журнал хоста и строкой тому, кто просил: «ничего не происходит» молча больше не бывает
## (по журналу после игры видно, почему хост не выполнил просьбу).
func _actor(peer_id: int, what: String) -> Player:
	var pl := player_of(peer_id)
	var why := ""
	if pl == null:
		why = "хост не нашёл твоего персонажа"
	elif not pl.is_alive():
		why = "у хоста ты числишься убитым"
	elif has_left(peer_id) or gone.has(peer_id):
		why = "у хоста ты числишься ушедшим из рейда"
	if why == "":
		return pl
	print("raid: отказ peer=%d «%s» — %s (участники %s, убиты %s, ушли %s/%s/%s)" % [peer_id, what, why, str(participants.keys()), str(dead.keys()),
		str(extracted.keys()), str(stranded.keys()), str(gone.keys())])
	_tell(peer_id, "Не выполнено (%s): %s" % [what, why])
	return null


## Прервать свою операцию (закрыл окно, взялся за другое): что сделано — остаётся.
func request_cancel_op() -> void:
	if _is_host():
		_cancel_op(multiplayer.get_unique_id())
	else:
		_rpc_cancel_op.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_cancel_op() -> void:
	if multiplayer.is_server():
		_cancel_op(multiplayer.get_remote_sender_id())


func _cancel_op(peer_id: int) -> void:
	if _ops.has(peer_id):
		((_ops[peer_id] as Array)[0] as MagOps).cancel()
		_ops.erase(peer_id)


func _item_op(peer_id: int, kind: String, role: String, idx: int, path: NodePath, ammo: String, src: String, side: String) -> void:
	var pl := _actor(peer_id, "магазин / плиты")
	if pl == null:
		return
	_cancel_op(peer_id)
	var c := _near_container(pl, path) if not path.is_empty() else null
	if (role == "loot" or src == "loot") and c == null:
		return
	if c:
		c.ensure_grid()
	var op := _make_op(pl, c, kind, role)
	op.ammo = ammo
	op.only_side = side
	var pocket := ["pocket"] if pl.inventory.pocket_grid != Vector2i.ZERO else []
	if kind == "load":
		if src != "":
			op.sources.assign([src])
		else:
			# любые подходящие патроны игрока: сначала из буфера (он временный), потом рюкзак, карман
			op.sources.assign(["buffer", "backpack"] + pocket)
	else:
		# вынутое — в ту же сетку; из ящика — в ящик, потом в буфер (прямо в рюкзак — нет)
		match role:
			"loot":
				op.dests.assign(["loot", "buffer"])
			"buffer":
				op.dests.assign(["buffer", "loot"] if c else ["buffer", "backpack"])
			"pocket":
				op.dests.assign(["pocket", "backpack"])
			_:
				op.dests.assign(["backpack", "buffer"] if c else ["backpack"])
	op.active_ids.assign(_ops.keys())
	if not op.start(idx):
		var why := {"full": "Магазин и так полный", "empty": "Нечего вынимать",
			"no_ammo": "Нет подходящих патронов", "no_room": "Некуда класть — нет места ни в ящике, ни в буфере",
			"busy": "С этим уже что-то делают"}
		if why.has(op.reason):
			_tell(peer_id, String(why[op.reason]))
		return
	_ops[peer_id] = [op, path]


## Операция над сетками игрока pl и ящика c (на хосте): рабочие копии, запись — переприсвоением
## (синхронизатор сравнивает значения).
func _make_op(pl: Player, c: LootContainer, kind: String, role: String) -> MagOps:
	var inv := pl.inventory
	var get_list := func(r: String) -> Array:
		if r == "loot":
			return c.items.duplicate(true) if is_instance_valid(c) else []
		return inv.list_of(r).duplicate(true)
	var commit := func(r: String, list: Array) -> void:
		if r == "loot":
			if is_instance_valid(c):
				c.items = list
		else:
			inv._set_list(r, list)
	var grid_of := func(r: String) -> Vector2i:
		if r == "loot":
			return c.grid if is_instance_valid(c) else Vector2i(1, 1)
		# нет кармана — ничего не влезает (ZERO у ItemDb — «без предела»)
		var g := inv.grid_of(r)
		return g if g != Vector2i.ZERO else Vector2i(1, 1)
	var op := MagOps.make(kind, role, pl.peer_id, get_list, commit, grid_of)
	op.all_roles.assign(["backpack", "pocket", "buffer", "rig", "dump"] + (["loot"] if c else []))
	return op


## Хост: операции идут — шаг за шагом; игрок погиб, ушёл, отошёл от ящика — прервать.
func _tick_ops(delta: float) -> void:
	for peer in _ops.keys():
		var rec: Array = _ops[peer]
		var op: MagOps = rec[0]
		var pl := player_of(int(peer))
		var ok := pl != null and pl.is_alive() and not has_left(int(peer))
		if ok and not (rec[1] as NodePath).is_empty():
			ok = _near_container(pl, rec[1]) != null
		if not ok:
			op.cancel()
			_ops.erase(peer)
			continue
		var before := op.steps
		var more := op.tick(delta)
		if op.steps > before:
			if op.kind == "load":
				# патрон в магазин — синтетический щелчок (Audio «mag_round»)
				Audio.play("mag_round", pl.global_position + Vector3.UP)
			else:
				var event := "round_out" if op.kind == "unload" else "plate_out"
				Audio.play(event, pl.global_position, -16.0, 1.1)
		if not more:
			var t := MagOps.reason_text(op.reason)
			if t != "":
				_tell(int(peer), t)
			_ops.erase(peer)


## Проверить магазин (правая кнопка → «Проверить патроны»): сетка запомнит, сколько было при проверке
## (пока не изменилось — видна оценка словами).
func request_check_mag(role: String, idx: int, container: LootContainer = null) -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_check_mag(multiplayer.get_unique_id(), role, idx, path)
	else:
		_rpc_check_mag.rpc_id(1, role, idx, path)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_check_mag(role: String, idx: int, path: NodePath) -> void:
	if multiplayer.is_server():
		_check_mag(multiplayer.get_remote_sender_id(), role, idx, path)


func _check_mag(peer_id: int, role: String, idx: int, path: NodePath) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var c := _near_container(pl, path) if role == "loot" else null
	if role == "loot" and c == null:
		return
	var list: Array = c.items.duplicate(true) if c else pl.inventory.list_of(role).duplicate(true)
	if idx < 0 or idx >= list.size() or not (list[idx] as Dictionary).has("rounds"):
		return
	list[idx]["checked"] = int(list[idx].rounds)
	if c:
		c.items = list
	else:
		pl.inventory._set_list(role, list)


## Разрядить магазин (сетка role, запись idx) — поштучно; into — старый вызов, вынутое идёт в ту же
## сетку, из ящика — в ящик и буфер (см. _item_op).
func request_unload(role: String, idx: int, _into: String = "", container: LootContainer = null) -> void:
	request_item_op("unload", role, idx, container)


## Патроны (ammo_role, ammo_idx) перетащили на магазин (mag_role, mag_idx) — снарядить его этими
## патронами, поштучно, сколько влезет (остаток остаётся в своей клетке).
func request_fill(ammo_role: String, ammo_idx: int, mag_role: String, mag_idx: int, container: LootContainer = null) -> void:
	var src_list: Array = container.items if ammo_role == "loot" and container else (local_player().inventory.list_of(ammo_role) if local_player() else [])
	if ammo_idx < 0 or ammo_idx >= src_list.size():
		return
	request_item_op("load", mag_role, mag_idx, container, String(src_list[ammo_idx].id), ammo_role)


## Окно ящика закрыто — что осталось в буфере, пропадает (буфер живёт только пока открыт ящик).
func request_clear_buffer() -> void:
	if _is_host():
		_clear_buffer(multiplayer.get_unique_id())
	else:
		_rpc_clear_buffer.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_clear_buffer() -> void:
	if multiplayer.is_server():
		_clear_buffer(multiplayer.get_remote_sender_id())


func _clear_buffer(peer_id: int) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl:
		pl.inventory.buffer = []


## Сказать игроку peer_id (хост — себе на экран или клиенту).
func _tell(peer_id: int, text: String) -> void:
	if not Net.is_networked() or peer_id == multiplayer.get_unique_id():
		notify(text)
	elif peer_id in multiplayer.get_peers():
		_rpc_tell.rpc_id(peer_id, text)


@rpc("authority", "call_remote", "reliable")
func _rpc_tell(text: String) -> void:
	notify(text)


## Надеть / взять в руки прямо из сетки src ("backpack", "pocket", "buffer", "loot" — ящик): что было в
## слоте — в рюкзак; не влезло — туда, откуда взято новое; иначе — под ноги.
## want — слот, на который бросили (оружие встаёт в любой слот оружия); пусто — по данным.
func request_equip_from(src: String, idx: int, container: LootContainer = null, want: String = "") -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_equip_from(multiplayer.get_unique_id(), src, idx, path, want)
	else:
		_rpc_equip_from.rpc_id(1, src, idx, path, want)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_equip_from(src: String, idx: int, path: NodePath, want: String) -> void:
	if multiplayer.is_server():
		_equip_from(multiplayer.get_remote_sender_id(), src, idx, path, want)


func _equip_from(peer_id: int, src: String, idx: int, path: NodePath, want: String = "") -> void:
	var pl := _actor(peer_id, "надеть")
	if pl == null:
		return
	_cancel_op(peer_id)
	var inv := pl.inventory
	var c := _near_container(pl, path) if src == "loot" else null
	if src == "loot" and c == null:
		return
	var list: Array = c.items.duplicate(true) if c else inv.list_of(src).duplicate(true)
	if idx < 0 or idx >= list.size():
		return
	var id := String(list[idx].id)
	var slot := ItemDb.pick_slot(id, inv.equipment, want)
	if slot == "":
		return
	var one := ItemDb.remove_at(list, idx, 1)
	for k in ["x", "y", "r", "op"]:
		one.erase(k)
	if not one.has("dur") and ItemDb.equip(id).has("durability"):
		one.dur = float(ItemDb.equip(id).durability)
	var eq := inv.equipment.duplicate(true)
	var old: Dictionary = eq.get(slot, {})
	eq[slot] = one
	var bp: Array = list if src == "backpack" else inv.items.duplicate(true)
	if slot == "backpack":
		# новый рюкзак: вещи — в его сетку; не влезло — под ноги
		var rf := ItemDb.refit(bp, ItemDb.bag_grid(eq))
		bp = rf[0]
		if src == "backpack":
			list = bp
		if not (rf[1] as Array).is_empty():
			spawn_drop(pl.global_position, DROP_NAME, rf[1], LootContainer.Look.BAG)
	if not old.is_empty() and ItemDb.add_to(bp, old, ItemDb.bag_grid(eq)) == 0:
		var g := c.grid if c else inv.grid_of(src)
		if src == "backpack" or g == Vector2i.ZERO or ItemDb.add_to(list, old, g) == 0:
			spawn_drop(pl.global_position, DROP_NAME, [old], LootContainer.Look.BAG)
	if c:
		c.items = list
	elif src != "backpack":
		inv._set_list(src, list)
	inv.items = bp
	inv.equipment = eq
	Audio.play(_equip_sound(id), pl.global_position, -8.0)


## Поставить предмет из сетки src (запись si) в предмет из сетки dst (запись di; "equip:<слот>" —
## надетое): плиту в плитоносец, магазин в оружие, обвес. Вытесненное — туда, откуда взят новый.
func request_fit_grid(src: String, si: int, dst: String, di: int, container: LootContainer = null) -> void:
	var path := container.get_path() if container else NodePath()
	if _is_host():
		_fit_grid(multiplayer.get_unique_id(), src, si, dst, di, path)
	else:
		_rpc_fit_grid.rpc_id(1, src, si, dst, di, path)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_fit_grid(src: String, si: int, dst: String, di: int, path: NodePath) -> void:
	if multiplayer.is_server():
		_fit_grid(multiplayer.get_remote_sender_id(), src, si, dst, di, path)


func _fit_grid(peer_id: int, src: String, si: int, dst: String, di: int, path: NodePath) -> void:
	var pl := _actor(peer_id, "вставить")
	if pl == null:
		return
	_cancel_op(peer_id)
	var inv := pl.inventory
	var c := _near_container(pl, path) if (src == "loot" or dst == "loot") else null
	if (src == "loot" or dst == "loot") and c == null:
		return
	var lists := {}
	var get := func(r: String) -> Array:
		if not lists.has(r):
			lists[r] = c.items.duplicate(true) if r == "loot" else inv.list_of(r).duplicate(true)
		return lists[r]
	var grid := func(r: String) -> Vector2i:
		return c.grid if r == "loot" else inv.grid_of(r)
	var from: Array = get.call(src)
	if si < 0 or si >= from.size():
		return
	var target: Dictionary = {}
	var slot := dst.trim_prefix("equip:") if dst.begins_with("equip:") else ""
	if slot != "":
		target = inv.equipment.get(slot, {})
	else:
		var to: Array = get.call(dst)
		if di >= 0 and di < to.size() and not (src == dst and si == di):
			target = to[di]
	if target.is_empty():
		return
	var fitted_id := String((from[si] as Dictionary).id)
	var r := Gear.fit(target, from[si], "")
	if String(r[2]) != "":
		_tell(peer_id, "Не встаёт: " + String(r[2]))
		return
	ItemDb.remove_at(from, si, 1)
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(from, r[1], grid.call(src)) == 0:
		_tell(peer_id, "Некуда положить снятое")
		return
	var fitted: Dictionary = r[0]
	fitted.erase("op")
	if slot != "":
		var eq := inv.equipment.duplicate(true)
		eq[slot] = fitted
		inv.equipment = eq
	else:
		var to: Array = get.call(dst)
		# источник мог стоять раньше цели в той же сетке — ищем цель по самой записи
		for i in range(to.size()):
			if is_same(to[i], target):
				for k in ["x", "y", "r"]:
					if target.has(k):
						fitted[k] = target[k]
				to[i] = fitted
				break
	for rr in lists:
		if String(rr) == "loot":
			c.items = lists[rr]
		else:
			inv._set_list(String(rr), lists[rr])
	Audio.play(_fit_sound(fitted_id), pl.global_position, -6.0)


## Внутри ящика — передвинуть запись в клетку (x, y).
func request_loot_move(container: LootContainer, idx: int, x: int, y: int, r: bool) -> void:
	if _is_host():
		_loot_move(multiplayer.get_unique_id(), container.get_path(), idx, x, y, r)
	else:
		_rpc_loot_move.rpc_id(1, container.get_path(), idx, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_loot_move(path: NodePath, idx: int, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_loot_move(multiplayer.get_remote_sender_id(), path, idx, x, y, r)


func _loot_move(peer_id: int, path: NodePath, idx: int, x: int, y: int, r: bool) -> void:
	var c := _near_container(player_of(peer_id), path)
	if c == null:
		return
	c.ensure_grid()
	var list := c.items.duplicate(true)
	if ItemDb.move_in(list, c.grid, idx, x, y, r):
		c.items = list
		Audio.play("item_move", c.global_position, -10.0)


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
	_cancel_op(peer_id)
	var pl := _actor(peer_id, "снять")
	if pl == null:
		return
	if pl.inventory.unequip(slot, x, y, r):
		Audio.play("item_drop", pl.global_position, -10.0)
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
	_cancel_op(peer_id)
	var pl := _actor(peer_id, "сортировка")
	if pl == null:
		return
	if not pl.inventory.sort_grid(where) and peer_id == multiplayer.get_unique_id():
		notify("Не разложить — сначала освободи место")


## Выбросить предмет целиком (с обвесом, магазином, износом) — мешком на землю перед собой;
## where — "backpack" / "pocket" (индекс) или "equip:<слот>".
## loose — уронить под ноги саму вещь (сброшенный магазин): лежит моделью, а не мешком.
func request_drop_entry(where: String, idx: int, loose: bool = false) -> void:
	if _is_host():
		_drop_entry(multiplayer.get_unique_id(), where, idx, loose)
	else:
		_rpc_drop_entry.rpc_id(1, where, idx, loose)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_drop_entry(where: String, idx: int, loose: bool) -> void:
	if multiplayer.is_server():
		_drop_entry(multiplayer.get_remote_sender_id(), where, idx, loose)


func _drop_entry(peer_id: int, where: String, idx: int, loose: bool = false) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	pl.inventory.spilled = []
	var e := pl.inventory.take_entry(where, idx)
	if e.is_empty():
		return
	if loose and where != "equip:backpack":
		spawn_loose(pl, e)
		return
	var fwd := Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw()))
	# бросил рюкзак — с ним и то, что не влезло в карманы
	spawn_drop(pl.global_position + fwd * 0.8, DROP_NAME, [e] + pl.inventory.spilled, LootContainer.Look.BAG)
	pl.inventory.spilled = []
	Audio.play("item_drop", pl.global_position)


## Владелец: отдать хосту снаряжение из профиля (вызывает уровень при появлении игрока).
func submit_loadout(lo: Dictionary) -> void:
	if _is_host():
		_give_loadout(multiplayer.get_unique_id(), lo.equipment, lo.backpack, lo.get("pocket", []), lo.get("pocket_grid", Vector2i.ZERO), String(lo.get("profile_id", "")))
	else:
		_rpc_give_loadout.rpc_id(1, lo.equipment, lo.backpack, lo.get("pocket", []), lo.get("pocket_grid", Vector2i.ZERO), String(lo.get("profile_id", "")))


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
	_cancel_op(peer_id)
	var pl := _actor(peer_id, "переложить")
	if pl and "trade" in [src, dst] and not trades.has(peer_id):
		return
	if pl:
		if pl.inventory.move_between(src, idx, dst, x, y, r):
			Audio.play("item_move", pl.global_position, -10.0)


## Из рюкзака (или буфера, кармана — from) — запись idx в контейнер (перетащили в окно лута): в клетку
## (x, y), x < 0 — в первую свободную. Места нет — не кладётся.
func request_put(container: LootContainer, idx: int, from: String = "backpack", x: int = -1, y: int = -1, r: bool = false) -> void:
	if _is_host():
		_put(multiplayer.get_unique_id(), container.get_path(), idx, from, x, y, r)
	else:
		_rpc_put.rpc_id(1, container.get_path(), idx, from, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_move_item(idx: int, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_move_item(multiplayer.get_remote_sender_id(), idx, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take_to(path: NodePath, idx: int, x: int, y: int, r: bool, into: String) -> void:
	if multiplayer.is_server():
		_take_to(multiplayer.get_remote_sender_id(), path, idx, x, y, r, into)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_put(path: NodePath, idx: int, from: String, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_put(multiplayer.get_remote_sender_id(), path, idx, from, x, y, r)


func _move_item(peer_id: int, idx: int, x: int, y: int, r: bool) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		if pl.inventory.move(idx, x, y, r):
			Audio.play("item_move", pl.global_position, -10.0)


## Контейнер рядом с игроком (обыскивать можно только в радиусе).
func _near_container(pl: Player, path: NodePath) -> LootContainer:
	var c := get_node_or_null(path) as LootContainer
	if pl == null or c == null or not pl.is_alive() or has_left(pl.peer_id):
		return null
	if pl.global_position.distance_to(c.global_position) > Balance.INTERACT_RADIUS + 1.5:
		return null
	if not c.reachable_from(pl):
		return null
	return c


func _pickup_sound(id: String) -> String:
	var cat := String(ItemDb.item(id).get("cat", ""))
	if cat == "ammo" or cat == "mag":
		return "pick_ammo"
	if cat == "med":
		return "pick_med"
	if cat == "weapon":
		return "pick_weapon"
	if cat == "armor" or cat == "plate" or cat == "rig":
		return "pick_cloth"
	return "item_pick"


func _equip_sound(id: String) -> String:
	return "equip_gun" if String(ItemDb.item(id).get("cat", "")) == "weapon" else "equip_gear"


func _fit_sound(id: String) -> String:
	if not WeaponDb.plate(id).is_empty():
		return "plate_in"
	if not WeaponDb.magazine(id).is_empty():
		return "mag_in"
	return "mod_fit"


func _take_to(peer_id: int, path: NodePath, idx: int, x: int, y: int, r: bool, into: String = "backpack") -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= c.items.size():
		return
	_cancel_op(peer_id)
	# клетка не задана — куда влезет
	var entry := (c.items[idx] as Dictionary).duplicate(true)
	var k := pl.inventory.put_at(entry, x, y, r, into) if x >= 0 else pl.inventory.add_entry_in(into, entry)
	if k > 0:
		c.take_at(idx, k)
		Audio.play(_pickup_sound(String(entry.id)), c.global_position, -8.0)


func _put(peer_id: int, path: NodePath, idx: int, from: String = "backpack", x: int = -1, y: int = -1, r: bool = false) -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= pl.inventory.list_of(from).size():
		return
	if c is LooseLoot:
		return
	_cancel_op(peer_id)
	c.ensure_grid()
	var src := pl.inventory.list_of(from).duplicate(true)
	var entry: Dictionary = (src[idx] as Dictionary).duplicate(true)
	var list := c.items.duplicate(true)
	var k := ItemDb.put_at(list, entry, c.grid, x, y, r) if x >= 0 else ItemDb.add_to(list, entry, c.grid)
	if k <= 0:
		_tell(peer_id, "Сюда не встаёт" if x >= 0 else "В «%s» нет места" % c.display_name)
		return
	ItemDb.remove_at(src, idx, k)
	pl.inventory._set_list(from, src)
	c.items = list
	c.rolled = true
	Audio.play("item_move", c.global_position, -10.0)


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
		spawn_loose(pl, r[1])


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


## Сборка из конструктора (BuildPlan): детали — из рюкзака и с самого оружия, торговца нет,
## приклад в рейде не меняют. where — "equip:<слот>" или "backpack" (idx). Снятое — в рюкзак.
func request_build(where: String, idx: int, draft: Dictionary, draft_mag: Dictionary) -> void:
	if _is_host():
		_build(multiplayer.get_unique_id(), where, idx, draft, draft_mag)
	else:
		_rpc_build.rpc_id(1, where, idx, draft, draft_mag)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_build(where: String, idx: int, draft: Dictionary, draft_mag: Dictionary) -> void:
	if multiplayer.is_server():
		_build(multiplayer.get_remote_sender_id(), where, idx, draft, draft_mag)


func _build(peer_id: int, where: String, idx: int, draft: Dictionary, draft_mag: Dictionary) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var inv: Inventory = pl.inventory
	var weapon: Dictionary = {}
	if where.begins_with("equip:"):
		weapon = inv.equipment.get(where.trim_prefix("equip:"), {})
	elif where == "backpack" and idx >= 0 and idx < inv.items.size():
		weapon = inv.items[idx]
	var r: Dictionary = BuildPlan.resolve(weapon, draft, draft_mag, {"backpack": inv.items},
		{"shop": false, "lists": BuildPlan.RAID_LISTS, "locked": ["stock"]}) if not weapon.is_empty() else {"why": "оружия нет"}
	var why: String = String(r.why)
	if why == "":
		var items: Array = inv.items.duplicate(true)
		var taken: Array = []
		for t: Variant in r.take:
			taken.append(int(t[1]))
		taken.sort()
		taken.reverse()
		var target := idx
		for i: Variant in taken:
			ItemDb.remove_at(items, int(i), 1)
			if where == "backpack" and int(i) < idx:
				target -= 1
		for item: Variant in r.returned:
			if ItemDb.add_to(items, item, inv.backpack_grid()) < int((item as Dictionary).get("n", 1)):
				why = "в рюкзаке нет места для снятого"
				break
		if why == "":
			if where.begins_with("equip:"):
				var eq := inv.equipment.duplicate(true)
				eq[where.trim_prefix("equip:")] = r.entry
				inv.items = items
				inv.equipment = eq
			else:
				var entry: Dictionary = r.entry
				for k: String in ["x", "y", "r"]:
					if (items[target] as Dictionary).has(k):
						entry[k] = items[target][k]
				items[target] = entry
				inv.items = items
			Audio.play("mod_fit", pl.global_position, -6.0)
	if why != "":
		if peer_id == multiplayer.get_unique_id():
			notify("Не собрать: " + why)
		else:
			_rpc_build_failed.rpc_id(peer_id, why)


@rpc("authority", "call_remote", "reliable")
func _rpc_build_failed(why: String) -> void:
	notify("Не собрать: " + why)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_strip(where: String, idx: int, part: String, path: NodePath) -> void:
	if multiplayer.is_server():
		_strip(multiplayer.get_remote_sender_id(), where, idx, part, path)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_fit(where: String, idx: int, src_idx: int, hint: String, path: NodePath) -> void:
	if multiplayer.is_server():
		_fit(multiplayer.get_remote_sender_id(), where, idx, src_idx, hint, path)


func _strip(peer_id: int, where: String, idx: int, part: String, path: NodePath) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var ok := false
	if where.begins_with("equip:"):
		ok = pl.inventory.strip_equipped(where.trim_prefix("equip:"), part)
	elif where in ["backpack", "pocket", "buffer", "rig", "dump"]:
		ok = pl.inventory.strip_in(where, idx, part)
	elif where == "loot":
		# с предмета в ящике — в тот же ящик, нет места — в буфер (прямо в рюкзак — нет)
		var c := _near_container(pl, path)
		if c and idx >= 0 and idx < c.items.size():
			c.ensure_grid()
			var list := c.items.duplicate(true)
			var r := Gear.strip(list[idx], part)
			var got: Dictionary = r[1]
			if not got.is_empty():
				list[idx] = r[0]
				if ItemDb.add_to(list, got, c.grid) >= int(got.n):
					c.items = list
					ok = true
				else:
					var list2 := c.items.duplicate(true)
					list2[idx] = r[0]
					var buf := pl.inventory.buffer.duplicate(true)
					if ItemDb.add_to(buf, got, Balance.BUFFER_GRID) >= int(got.n):
						c.items = list2
						pl.inventory.buffer = buf
						ok = true
	if ok:
		Audio.play("plate_out" if part.begins_with("plate:") else ("mag_out" if part == "mag" else "mod_fit"),
			pl.global_position, -6.0)
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
	if not (r[1] as Dictionary).is_empty() and ItemDb.add_to(items, r[1], pl.inventory.backpack_grid()) == 0:
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
	Audio.play(_fit_sound(String(src.id)), pl.global_position, -6.0)


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
		Audio.play("mod_fit", pl.global_position, -6.0)
	elif peer_id == multiplayer.get_unique_id():
		notify(why)


func _remove_mod(peer_id: int, weapon_slot: String, mod_slot: String) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		if pl.inventory.remove_mod(weapon_slot, mod_slot):
			Audio.play("mod_fit", pl.global_position, -6.0)
		elif peer_id == multiplayer.get_unique_id():
			notify("Некуда положить — освободи место в рюкзаке")


## Надеть / взять в руки предмет из рюкзака (индекс в items).
func request_equip(idx: int) -> void:
	if _is_host():
		_equip(multiplayer.get_unique_id(), idx)
	else:
		_rpc_equip.rpc_id(1, idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_give_loadout(eq: Dictionary, items: Array, pocket: Array, pgrid: Vector2i, owner: String = "") -> void:
	if multiplayer.is_server():
		_give_loadout(multiplayer.get_remote_sender_id(), eq, items, pocket, pgrid, owner)


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


func request_unpack(idx: int, expected_id: String) -> void:
	if _is_host():
		_unpack(multiplayer.get_unique_id(), idx, expected_id)
	else:
		_rpc_unpack.rpc_id(1, idx, expected_id)


func request_supply_signal() -> void:
	if _is_host():
		_supply_signal(multiplayer.get_unique_id())
	else:
		_rpc_supply_signal.rpc_id(1)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_supply_signal() -> void:
	if multiplayer.is_server():
		_supply_signal(multiplayer.get_remote_sender_id())


func _supply_signal(peer_id: int) -> void:
	var pl: Player = player_of(peer_id)
	if pl == null or not pl.is_alive() or pl.is_downed() or has_left(peer_id) or over:
		return
	if not supply_state.is_empty():
		_tell(peer_id, "Самолёт снабжения уже вызван в этом рейде")
		return
	if not pl.has_signal_launcher() or not pl.inventory.has("supply_signal"):
		_tell(peer_id, "Нужны сигнальный пистолет и патрон снабжения в рюкзаке")
		return
	var pos: Vector3 = _supply_site(pl)
	if not pos.is_finite():
		_tell(peer_id, "Выйди под открытое небо к свободному месту для сброса")
		return
	# Проверки закончены: предмет расходуется ровно один раз, без ожидания RPC.
	if pl.inventory.remove("supply_signal", 1) != 1:
		return
	supply_state = {"pos": pos, "origin": pl.global_position + Vector3.UP, "elapsed": 0.0, "dropped": false}
	NoiseBus.emit(pl.global_position, float(Balance.SUPPLY_SIGNAL.noise_m), "shot")
	_tell(peer_id, "Сигнал принят. Самолёт сбросит груз примерно через %d с" % int(Balance.SUPPLY_SIGNAL.delay))


## The player's host transaction has already validated the loaded green round.
## This operation checks the drop site before the transaction spends that round.
func start_loaded_supply_signal(pl: Player) -> String:
	if not _is_host() or pl == null or not pl.is_alive() or pl.is_downed() or has_left(pl.peer_id) or over:
		return "Вызов снабжения недоступен"
	if not supply_state.is_empty():
		return "Самолёт снабжения уже вызван в этом рейде"
	var pos: Vector3 = _supply_site(pl)
	if not pos.is_finite():
		return "Выйди под открытое небо к свободному месту для сброса"
	supply_state = {"pos": pos, "origin": pl.global_position + Vector3.UP, "elapsed": 0.0, "dropped": false}
	NoiseBus.emit(pl.global_position, float(Balance.SUPPLY_SIGNAL.noise_m), "shot")
	_tell(pl.peer_id, "Сигнал принят. Самолёт сбросит груз примерно через %d с" % int(Balance.SUPPLY_SIGNAL.delay))
	return ""


## Физика хоста: небо над стрелком и площадкой, опора и свободные боковые стороны ящика.
func _supply_site(pl: Player) -> Vector3:
	var space: PhysicsDirectSpaceState3D = pl.get_world_3d().direct_space_state
	var mask: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	var sky: Vector3 = pl.global_position + Vector3.UP * float(Balance.SUPPLY_SIGNAL.roof_check)
	if not space.intersect_ray(PhysicsRayQueryParameters3D.create(pl.global_position + Vector3.UP, sky, mask)).is_empty():
		return Vector3.INF
	var forward: Vector3 = Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw()))
	var at: Vector3 = pl.global_position + forward * float(Balance.SUPPLY_SIGNAL.clear_radius)
	var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(at + Vector3.UP, at - Vector3.UP * float(Balance.SUPPLY_SIGNAL.ground_check), mask))
	if hit.is_empty() or (hit.normal as Vector3).dot(Vector3.UP) < float(Balance.SUPPLY_SIGNAL.normal_min):
		return Vector3.INF
	at = hit.position
	if not space.intersect_ray(PhysicsRayQueryParameters3D.create(at + Vector3.UP, at + Vector3.UP * float(Balance.SUPPLY_SIGNAL.roof_check), mask)).is_empty():
		return Vector3.INF
	for direction: Vector3 in [Vector3.LEFT, Vector3.RIGHT, Vector3.FORWARD, Vector3.BACK, Vector3(-1, 0, -1), Vector3(-1, 0, 1), Vector3(1, 0, -1), Vector3(1, 0, 1)]:
		var center: Vector3 = at + Vector3.UP * float(Balance.SUPPLY_SIGNAL.site_height)
		var edge: Vector3 = at + direction * float(Balance.SUPPLY_SIGNAL.site_half)
		if not space.intersect_ray(PhysicsRayQueryParameters3D.create(center, edge + Vector3.UP * float(Balance.SUPPLY_SIGNAL.site_height), mask)).is_empty():
			return Vector3.INF
		var support: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(edge + Vector3.UP, edge - Vector3.UP * float(Balance.SUPPLY_SIGNAL.ground_check), mask))
		if support.is_empty() or absf(float(support.position.y) - at.y) > float(Balance.SUPPLY_SIGNAL.terrain_tolerance):
			return Vector3.INF
		if not space.intersect_ray(PhysicsRayQueryParameters3D.create(edge + Vector3.UP * float(Balance.SUPPLY_SIGNAL.site_height), edge + Vector3.UP * float(Balance.SUPPLY_SIGNAL.roof_check), mask)).is_empty():
			return Vector3.INF
	return at


func _tick_supply(delta: float) -> void:
	if supply_state.is_empty():
		return
	if _is_host() and not over:
		var state: Dictionary = supply_state.duplicate()
		state.elapsed = minf(float(state.elapsed) + delta, float(Balance.SUPPLY_SIGNAL.delay) + float(Balance.SUPPLY_SIGNAL.flight))
		if not bool(state.dropped) and float(state.elapsed) >= float(Balance.SUPPLY_SIGNAL.delay):
			state.dropped = true
			spawn_drop(state.pos, SUPPLY_DROP_NAME, _supply_loot(), LootContainer.Look.CRATE, Vector3.UP * float(Balance.SUPPLY_SIGNAL.drop_height))
		if not bool(state.get("landed", false)) and float(state.elapsed) >= float(Balance.SUPPLY_SIGNAL.delay) + float(Balance.SUPPLY_SIGNAL.fall_sec):
			state["landed"] = true
			Audio.play("drop_land", state.pos)
			NoiseBus.emit(state.pos, float(Balance.SUPPLY_SIGNAL.noise_m), "drop")
		supply_state = state
	if not is_instance_valid(_supply_visual):
		_supply_visual = (load("res://scenes/world/supply_flight.tscn") as PackedScene).instantiate() as Node3D
		_supply_visual.name = "SupplyFlight"
		get_parent().add_child(_supply_visual)


## Ценные вещи без сигнальных патронов: вызов не позволяет бесконечно размножать вызовы.
func _supply_loot() -> Array:
	# груз снабжения — то, что помогает в бою (Balance.SUPPLY_LOOT): готовые стволы высокого тира в
	# хорошем состоянии, к каждому — снаряжённые магазины, лучший патрон калибра и обвес, который на
	# него встаёт; броня с плитами, шлем, медицина, гранаты. Ценностей на продажу в нём нет.
	var spec: Dictionary = Balance.SUPPLY_LOOT
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.randomize()
	var result: Array = []
	var taken: Array[String] = []
	for i: int in range(rng.randi_range(int(spec.weapons[0]), int(spec.weapons[1]))):
		var pid: String = WeaponDb.pick("kind=preset;min_tier=%d" % int(spec.weapon_tier), rng)
		var weapon: Dictionary = WeaponDb.make_weapon(pid.trim_prefix("preset:"), rng, spec.dur)
		if weapon.is_empty() or String(weapon.id) in taken:
			continue
		taken.append(String(weapon.id))
		result.append(weapon)
		var wid: String = String(weapon.id)
		var caliber: String = String(WeaponDb.weapon(wid).caliber)
		# лучший патрон калибра — по пробитию
		var ammo_id: String = WeaponDb.default_ammo(caliber)
		for aid: Variant in WeaponDb.ids("ammo"):
			var a: Dictionary = WeaponDb.ammo(String(aid))
			if String(a.get("caliber", "")) == caliber and int(a.get("pen", 0)) > int(WeaponDb.ammo(ammo_id).get("pen", 0)):
				ammo_id = String(aid)
		if weapon.get("mag") is Dictionary:
			(weapon.mag as Dictionary)["ammo"] = ammo_id
		var mag_id: String = String((weapon.get("mag", {}) as Dictionary).get("id", ""))
		var cap: int = int(WeaponDb.magazine(mag_id).get("capacity", 0))
		if mag_id != "":
			for k: int in range(int(spec.mags)):
				result.append(WeaponDb.make_mag(mag_id, ammo_id, cap))
		var rounds: int = maxi(cap, int(WeaponDb.capacity(weapon))) * int(spec.ammo_mags)
		var st: int = maxi(ItemDb.stack(ammo_id), 1)
		while rounds > 0:
			result.append(ItemDb.make(ammo_id, mini(rounds, st)))
			rounds -= st
		# обвес под этот ствол: по одному каждого вида, которого на нём ещё нет (прицел, дульное, цевьё)
		var have: Array[String] = []
		for m: Variant in weapon.get("mods", {}):
			have.append(WeaponBuilder.tab_of(WeaponDb.mod_id(weapon.mods[m])))
		var by_tab: Dictionary = {}
		for att: Variant in WeaponDb.ids("attachments"):
			var aid2: String = String(att)
			var tab: String = WeaponBuilder.tab_of(aid2)
			if tab in have or not tab in ["optic", "muzzle", "fore"] or int(ItemDb.item(aid2).get("tier", 1)) < int(spec.mod_tier):
				continue
			if WeaponDb.free_mount_for(weapon, aid2) == "":
				continue
			if not by_tab.has(tab):
				by_tab[tab] = []
			(by_tab[tab] as Array).append(aid2)
		var tabs: Array = by_tab.keys()
		tabs.shuffle()
		for t: int in range(mini(int(spec.mods), tabs.size())):
			var pool: Array = by_tab[tabs[t]]
			result.append(ItemDb.make(String(pool[rng.randi() % pool.size()]), 1))
	# броня: плитоносец с плитами того же уровня и шлем
	var vest_id: String = WeaponDb.pick("kind=vest;min_tier=%d" % int(spec.armor_tier), rng)
	var plate_id: String = WeaponDb.pick("kind=plate;min_tier=%d" % int(spec.armor_tier), rng)
	if vest_id != "":
		var plates: Dictionary = {}
		for side: Variant in WeaponDb.vest(vest_id).get("plates", []):
			if plate_id != "":
				plates[String(side)] = plate_id
		result.append(WeaponDb.make_vest(vest_id, plates))
	var helmet_id: String = WeaponDb.pick("kind=helmet;min_tier=%d" % int(spec.armor_tier), rng)
	if helmet_id != "":
		result.append(ItemDb.make(helmet_id, 1))
	for pair: Array in spec.extras:
		var n: int = rng.randi_range(int(pair[1]), int(pair[2]))
		if n > 0:
			result.append(ItemDb.make(String(pair[0]), n))
	for entry: Dictionary in result:
		entry["fir"] = true
	return result


@rpc("any_peer", "call_remote", "reliable")
func _rpc_unpack(idx: int, expected_id: String) -> void:
	if multiplayer.is_server():
		_unpack(multiplayer.get_remote_sender_id(), idx, expected_id)


func _unpack(peer_id: int, idx: int, expected_id: String) -> void:
	var pl: Player = player_of(peer_id)
	if pl == null or not pl.is_alive() or pl.is_downed() or has_left(peer_id):
		return
	var result: Array = ItemDb.unpack(pl.inventory.items, pl.inventory.backpack_grid(), idx, expected_id)
	if result.is_empty():
		_tell(peer_id, "Вскрыть не удалось: проверь место в рюкзаке")
		return
	pl.inventory.items = result
	Audio.play(_pickup_sound(expected_id), pl.global_position)


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
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	var c := get_node_or_null(path) as LootContainer
	if pl == null or c == null or not pl.is_alive() or has_left(peer_id):
		return
	if pl.global_position.distance_to(c.global_position) > Balance.INTERACT_RADIUS + 1.5:
		return
	if not c.reachable_from(pl):
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
			Audio.play(_pickup_sound(id), c.global_position, -8.0)
		return


## Хост: снаряжение из профиля игрока (рейд из убежища) — в его рюкзак и слоты.
func _give_loadout(peer_id: int, eq: Dictionary, items: Array, pocket: Array = [], pgrid: Vector2i = Vector2i.ZERO, owner: String = "") -> void:
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
	if recovery != null:
		recovery.register_owner(peer_id, owner)


func _consume(peer_id: int, id: String, n: int) -> void:
	var pl := player_of(peer_id)
	if pl:
		pl.inventory.remove(id, n)


func _equip(peer_id: int, idx: int) -> void:
	_cancel_op(peer_id)
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var id := String(pl.inventory.items[idx].id) if idx >= 0 and idx < pl.inventory.items.size() else ""
	var spill := pl.inventory.equip_from_items(idx)
	if id != "":
		Audio.play(_equip_sound(id), pl.global_position, -8.0)
	if not spill.is_empty():
		spawn_drop(pl.global_position, DROP_NAME, [spill], LootContainer.Look.BAG)


func _drop(peer_id: int, id: String, n: int) -> void:
	var pl := player_of(peer_id)
	if pl == null or not pl.is_alive():
		return
	var k := pl.inventory.remove(id, n)
	if k > 0:
		var fwd := Vector3(sin(pl.body_yaw()), 0.0, cos(pl.body_yaw()))
		spawn_drop(pl.global_position + fwd * 0.8, DROP_NAME, [{"id": id, "n": k}], LootContainer.Look.BAG)
		Audio.play("item_drop", pl.global_position)


## Лечение: предмет уходит сразу, здоровье прибавляется через use.time (если игрок ещё жив).
## Лёжа раненым: аптечка — подняться (REVIVE_SELF_SEC), бинт — дольше не истечь кровью.
func _use_med(peer_id: int, id: String) -> void:
	var pl := player_of(peer_id)
	var use: Dictionary = ItemDb.item(id).get("use", {})
	if pl == null or use.is_empty() or not pl.is_alive():
		return
	var med_sound := "bandage" if id == "bandage" else ("pills" if id == "painkillers" else "inject")
	if pl.is_downed():
		if id != "medkit" and id != "bandage":
			return
		if pl.inventory.remove(id, 1) == 0:
			return
		Audio.play(med_sound, pl.global_position + Vector3.UP)
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
	Audio.play(med_sound, pl.global_position + Vector3.UP)
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
	# сюжет общий: «убить N» — за любого участника, считает хост
	Quests.event("kill", {"arch": arch})
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
	# выброшенное из рюкзака — в тот же мешок, что уже лежит рядом (не россыпь мешков по полу)
	if display == DROP_NAME and _merge_drop(pos, list):
		return
	var data := {"name": "Drop_%d" % _drop_count, "pos": pos, "display": display, "items": list, "look": int(look), "toss": toss, "fall_sec": float(Balance.SUPPLY_SIGNAL.fall_sec) if display == SUPPLY_DROP_NAME else 0.0}
	_drop_count += 1
	if _drop_spawner:
		_drop_spawner.spawn(data)
	else:
		_drops.add_child(_make_drop(data))


## Хост: вещь упала под ноги игроку и лежит сама по себе (сброшенный магазин) — рядом с ногами, на
## полу, повёрнута как упала. Не мешок: издалека не видно, найдёшь — подберёшь (F).
func spawn_loose(pl: Player, entry: Dictionary) -> void:
	var data := {"name": "Drop_%d" % _drop_count, "pos": LooseLoot.floor_near(pl), "display": ItemDb.item_name(String(entry.id)), "items": [entry], "look": int(LootContainer.Look.NONE),
		"toss": Vector3.UP * float(Balance.DROPPED_MAG.fall), "fall_sec": 0.0, "loose": true, "yaw": randf() * TAU}
	_drop_count += 1
	if _drop_spawner:
		_drop_spawner.spawn(data)
	else:
		_drops.add_child(_make_drop(data))


## Хост: ближайший мешок «Выброшено» в Balance.DROP_MERGE_M от pos — добавить в него list
## (сетка ящика растёт, ничего не теряется). Нет такого — false.
func _merge_drop(pos: Vector3, list: Array) -> bool:
	var best: LootContainer = null
	var best_d := Balance.DROP_MERGE_M
	for n in _drops.get_children():
		var c := n as LootContainer
		if c == null or c.is_queued_for_deletion() or c.display_name != DROP_NAME:
			continue
		var d := c.global_position.distance_to(pos)
		if d < best_d:
			best_d = d
			best = c
	if best == null:
		return false
	var merged := best.items.duplicate(true)
	merged.append_array(list.duplicate(true))
	best.items = merged
	best.place_all()
	best.rolled = true
	return true


func _make_drop(data: Dictionary) -> Node:
	var loose: bool = bool(data.get("loose", false))
	var c := (LOOSE_SCENE if loose else LOOT_SCENE).instantiate() as LootContainer
	if loose:
		(c as LooseLoot).dropped = true
		(c as LooseLoot).lay_yaw = float(data.get("yaw", 0.0))
	c.name = String(data.name)
	c.position = data.pos
	c.display_name = String(data.display)
	c.look = int(data.look) as LootContainer.Look
	c.items = (data.items as Array).duplicate(true)
	c.place_all()
	c.rolled = true
	c.toss_from = data.get("toss", Vector3.ZERO)
	c.toss_duration = float(data.get("fall_sec", 0.0))
	c.search_s = Balance.SEARCH_BODY_SEC
	return c


# ---------------------------------------------------------------- HUD (у каждого peer)

func _process(delta: float) -> void:
	_delta = delta
	_tick_supply(delta)
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
	Audio.play_ui("ui_notify", -5.0)


func _update_channel_hud(me: Player) -> void:
	_progress.visible = false
	_progress_label.visible = false
	if me == null or not me.is_alive() or has_left(me.peer_id) or over:
		_evac_sound_second = -1
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
		_play_evac_tick(evac_left)
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
		_play_evac_tick(evac_left)
		_progress_label.text = "ЭВАКУАЦИЯ · %s — через %s · ждём: %s" % [here.display_name, _clock(evac_left), ", ".join(names)]
		return
	var t := float(cur[1]) if cur.size() == 2 else 0.0
	_progress.max_value = here.channel_s
	_progress.value = t
	var left := maxf(0.0, here.channel_s - t)
	_play_evac_tick(left)
	_progress_label.text = "ЭВАКУАЦИЯ · %s — %.1f с" % [here.display_name, left]


func _play_evac_tick(left: float) -> void:
	var second := int(ceil(left))
	if second != _evac_sound_second:
		_evac_sound_second = second
		Audio.play_ui("evac_tick", -5.0)


## «2:41».
static func _clock(sec: float) -> String:
	var s := int(ceil(sec))
	return "%d:%02d" % [s / 60, s % 60]


## Подсказка «F — …» у ближайшего предмета, с которым можно что-то сделать. Рядом раненый
## напарник — «поднять» (держать F, аптечка) и «тащить» (X).
func _update_prompt(me: Player) -> void:
	_prompt.visible = false
	if me == null or not me.is_alive() or has_left(me.peer_id) or ui.is_looting() or Trade.is_open():
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
			if it is LootContainer and not (it as LootContainer).reachable_from(me):
				continue
			best = it
			best_d = d
	# напарник на ногах рядом (ближе любого предмета) — подержать «действие»: обмен вещами
	var pal: Player = null
	var pal_d: float = Balance.TRADE.reach_m
	if Net.is_networked() and not trades.has(me.peer_id):
		for n in get_tree().get_nodes_in_group("players"):
			var other := n as Player
			if other == null or other == me or not other.is_alive() or other.is_downed() or trades.has(other.peer_id):
				continue
			var d2 := other.global_position.distance_to(me.global_position)
			if d2 < pal_d:
				pal_d = d2
				pal = other
	if pal != null and pal_d < best_d:
		_prompt.visible = true
		_prompt.text = "%s (держать) — обмен вещами: %s" % [PauseMenu.key_name("interact"), String(Net.player_names.get(pal.peer_id, participants.get(pal.peer_id, "напарник")))]
		_trade_hold_t = _trade_hold_t + _delta if Input.is_action_pressed("interact") and not PauseMenu.shown else 0.0
		if _trade_hold_t >= float(Balance.TRADE.hold_sec):
			_trade_hold_t = 0.0
			request_trade(pal.peer_id)
		return
	_trade_hold_t = 0.0
	if best == null:
		return
	_prompt.visible = true
	_prompt.text = PauseMenu.key_name("interact") + " — " + best.prompt()
	if Input.is_action_just_pressed("interact"):
		if best is LootContainer and not best is LooseLoot:
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
		elif gone.has(peer):
			lines.append("%s — вышел из игры, вещи остались в рейде" % who)
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
	if _exit_receipt.is_empty():
		return
	_profile_saved = true
	var items: Array = (_exit_receipt.items as Array).duplicate(true)
	# Подтверждённый хостом состав после приёмки груза: износ, магазин и обвесы сохранены.
	Profile.return_loadout(_exit_receipt.equipment, items, int(loot_value.get(me.peer_id, 0)))
	# Михалыч доплачивает за риск условий: доля ценности вынесенного
	var bonus := int(float(loot_value.get(me.peer_id, 0)) * RaidConditions.pay_bonus())
	if bonus > 0:
		Profile.money += bonus
		Profile.save()
		notify("Михалыч доплатит за риск: %s ₽" % InventoryUI.money(bonus))
	Profile.set_pocket(_exit_receipt.pocket)
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


## Сюжет (хост): участник эвакуировался — с тем, что вынес; сделанное группой засчитано всем.
func _quest_extracted(pl: Player) -> void:
	var delivery: String = ""
	if quest_world:
		var payload: Dictionary = quest_world.extraction_payload(pl.peer_id)
		var objective: Dictionary = Quests.objective("own_mark")
		if Quests.state("own_mark") == "ACTIVE" and String(objective.get("type", "")) == "extract_cargo" and String(objective.get("site", "")) in payload.cargo:
			delivery = String(objective.item)
		Quests.on_extracted(payload)
	# Михалычу передан один нужный узел, включая обычный лут. Остальные находки остаются.
	for role: String in ["backpack", "pocket"]:
		var list: Array = pl.inventory.list_of(role).duplicate(true)
		for idx: int in range(list.size() - 1, -1, -1):
			var sid: String = String(list[idx].get("quest_cargo", ""))
			if delivery in ["engraver_frame", "engraver_controller"] and String(list[idx].id) == delivery and bool(list[idx].get("fir", false)):
				list.remove_at(idx)
				delivery = ""
			elif sid == "engraver_head":
				list[idx].erase("quest_cargo")
		if role == "backpack":
			pl.inventory.items = list
		else:
			pl.inventory.pocket = list
	var receipt: Dictionary = {"equipment": pl.equipment_state(), "items": pl.inventory.items.duplicate(true), "pocket": pl.inventory.pocket.duplicate(true)}
	if recovery != null:
		recovery.escaped((receipt.equipment as Dictionary).values() + receipt.items + receipt.pocket)
	if not Net.is_networked() or pl.peer_id == multiplayer.get_unique_id():
		_exit_receipt = receipt
	else:
		_rpc_exit_receipt.rpc_id(pl.peer_id, receipt)


@rpc("authority", "call_remote", "reliable")
func _rpc_exit_receipt(receipt: Dictionary) -> void:
	_exit_receipt = receipt.duplicate(true)


func notify_peer(peer: int, text: String) -> void:
	if not Net.is_networked() or peer == multiplayer.get_unique_id():
		notify(text)
	else:
		_rpc_notify_peer.rpc_id(peer, text)


@rpc("authority", "call_remote", "reliable")
func _rpc_notify_peer(text: String) -> void:
	notify(text)


## Сюжет считает хост (см. _quest_extracted); у себя ничего не нужно.
func _quest_hooks(_me: Player) -> void:
	pass


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
		for peer: int in multiplayer.get_peers():
			if Net.visible_in(peer, "raid"):
				_host_left.rpc_id(peer)
	Profile.pending_raid = false
	Net.change_scene(Balance.HIDEOUT_SCENE)


@rpc("authority", "call_remote", "reliable")
func _host_left() -> void:
	notify("Хост ушёл из рейда — все в убежище")
	await get_tree().create_timer(2.5).timeout
	if is_inside_tree():
		Profile.pending_raid = false
		Net.change_scene(Balance.HIDEOUT_SCENE)


## Новый рейд: хост переводит всех заново в сектор; без сети — перезагрузка сцены.
func _restart() -> void:
	if not Net.is_networked():
		Net.change_scene(get_tree().current_scene.scene_file_path)
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
