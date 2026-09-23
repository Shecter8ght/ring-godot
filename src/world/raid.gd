class_name Raid
extends Node
## Состояние рейда: рубильники, эвакуация, лут, итог. Считает хост, остальным реплицируется
## синхронизатором (узел создаёт SectorLevel с одинаковым именем у всех peer).
##
## Эвакуация: живой игрок стоит в зоне ExtractionPoint, зона открыта (рубильник включён; нужный
## ключ — в рюкзаке у кого-то из стоящих в зоне) — идёт отсчёт channel_s; вышел — сброс.
## Досчитал — эвакуирован: пропадает из мира, выносит рюкзак. Рейд окончен, когда каждый
## участник погиб или ушёл. Ключи — предметы в рюкзаке (data/items.json, категория key).
## Лут: игроки просят хост (RPC ниже) взять из контейнера, выбросить, полечиться — хост проверяет
## и меняет рюкзак (Inventory) и контейнер (LootContainer). Тела и выброшенное — динамические
## LootContainer через спавнер (узел Drops).

static var current: Raid

const LOOT_SCENE := preload("res://scenes/world/loot_container.tscn")

## Кто в рейде: peer_id -> имя. Заполняет хост при появлении игроков.
var participants: Dictionary = {}
## Включённые рубильники: switch_id -> true.
var switches: Dictionary = {}
## Эвакуированные: peer_id -> имя точки.
var extracted: Dictionary = {}
## Сколько вынес (₽): peer_id -> ценность рюкзака в момент эвакуации.
var loot_value: Dictionary = {}
## Отсчёт эвакуации: peer_id -> [id точки, секунд].
var channel: Dictionary = {}
## Погибшие: peer_id -> true (хост — по сигналу Health).
var dead: Dictionary = {}
var over: bool = false

var ui: InventoryUI
## Владелец уже записал итог рейда в профиль (эвакуация) — один раз.
var _profile_saved: bool = false
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


func _ready() -> void:
	current = self
	_drops = Node3D.new()
	_drops.name = "Drops"
	add_child(_drops)
	_build_hud()
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
	for prop in [".:participants", ".:switches", ".:extracted", ".:loot_value", ".:dead", ".:over", ".:channel"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ALWAYS)
	sync.replication_config = config
	sync.set_multiplayer_authority(get_multiplayer_authority())
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


func set_switch(switch_id: String, on: bool) -> void:
	var s := switches.duplicate()
	s[switch_id] = on
	switches = s


## Хост: игрок погиб — рюкзак остаётся в теле, которое могут обыскать напарники.
func mark_dead(peer_id: int) -> void:
	if not _is_host():
		return
	var d := dead.duplicate()
	d[peer_id] = true
	dead = d
	var pl := player_of(peer_id)
	if pl and not pl.inventory.items.is_empty():
		var who := String(Net.player_names.get(peer_id, participants.get(peer_id, "Игрок")))
		spawn_drop(pl.global_position, "Тело: " + who, pl.inventory.take_all(), LootContainer.Look.BAG)
	_check_over()


## Открыта ли точка и, если нет, почему (для подсказки у зоны). Ключ должен быть у кого-то
## из живых в зоне — группа проходит вместе с тем, у кого карта.
func extraction_block_reason(ext: ExtractionPoint) -> String:
	if ext.required_switch != "" and not bool(switches.get(ext.required_switch, false)):
		return "нет питания — включи рубильник"
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
	var ch := {}
	for node in get_tree().get_nodes_in_group("players"):
		var pl := node as Player
		if pl == null or not pl.is_alive() or is_extracted(pl.peer_id):
			continue
		for e in get_tree().get_nodes_in_group("extractions"):
			var ext := e as ExtractionPoint
			if ext == null or not ext.contains(pl.global_position) or extraction_block_reason(ext) != "":
				continue
			var prev: Array = channel.get(pl.peer_id, [])
			var t := delta
			if prev.size() == 2 and String(prev[0]) == String(ext.name):
				t += float(prev[1])
			if t >= ext.channel_s:
				_extract(pl, ext)
			else:
				ch[pl.peer_id] = [String(ext.name), t]
			break
	channel = ch


func _extract(pl: Player, ext: ExtractionPoint) -> void:
	var e := extracted.duplicate()
	e[pl.peer_id] = ext.display_name
	extracted = e
	var v := loot_value.duplicate()
	v[pl.peer_id] = pl.inventory.value()
	loot_value = v
	_check_over()


func _check_over() -> void:
	if participants.is_empty():
		return
	for peer in participants:
		if not extracted.has(peer) and not dead.has(peer):
			return
	over = true


# ---------------------------------------------------------------- лут (просьбы к хосту)

## Взять из контейнера n штук id (n <= 0 — всё, что есть этого id).
func request_take(container: LootContainer, id: String, n: int) -> void:
	if _is_host():
		_take(multiplayer.get_unique_id(), container.get_path(), id, n)
	else:
		_rpc_take.rpc_id(1, container.get_path(), id, n)


func request_take_all(container: LootContainer) -> void:
	for it in container.items.duplicate(true):
		request_take(container, String(it.id), int(it.n))


func request_drop(id: String, n: int) -> void:
	if _is_host():
		_drop(multiplayer.get_unique_id(), id, n)
	else:
		_rpc_drop.rpc_id(1, id, n)


## Владелец: отдать хосту снаряжение из профиля (вызывает уровень при появлении игрока).
func submit_loadout(lo: Dictionary) -> void:
	if _is_host():
		_give_loadout(multiplayer.get_unique_id(), lo.equipment, lo.backpack)
	else:
		_rpc_give_loadout.rpc_id(1, lo.equipment, lo.backpack)


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


## Из контейнера — запись idx прямо в клетку (x, y) рюкзака (перетащили мышью).
func request_take_to(container: LootContainer, idx: int, x: int, y: int, r: bool) -> void:
	if _is_host():
		_take_to(multiplayer.get_unique_id(), container.get_path(), idx, x, y, r)
	else:
		_rpc_take_to.rpc_id(1, container.get_path(), idx, x, y, r)


## Из рюкзака — запись idx в контейнер (перетащили в окно лута).
func request_put(container: LootContainer, idx: int) -> void:
	if _is_host():
		_put(multiplayer.get_unique_id(), container.get_path(), idx)
	else:
		_rpc_put.rpc_id(1, container.get_path(), idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_move_item(idx: int, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_move_item(multiplayer.get_remote_sender_id(), idx, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_take_to(path: NodePath, idx: int, x: int, y: int, r: bool) -> void:
	if multiplayer.is_server():
		_take_to(multiplayer.get_remote_sender_id(), path, idx, x, y, r)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_put(path: NodePath, idx: int) -> void:
	if multiplayer.is_server():
		_put(multiplayer.get_remote_sender_id(), path, idx)


func _move_item(peer_id: int, idx: int, x: int, y: int, r: bool) -> void:
	var pl := player_of(peer_id)
	if pl and pl.is_alive():
		pl.inventory.move(idx, x, y, r)


## Контейнер рядом с игроком (обыскивать можно только в радиусе).
func _near_container(pl: Player, path: NodePath) -> LootContainer:
	var c := get_node_or_null(path) as LootContainer
	if pl == null or c == null or not pl.is_alive() or is_extracted(pl.peer_id):
		return null
	if pl.global_position.distance_to(c.global_position) > Balance.INTERACT_RADIUS + 1.5:
		return null
	return c


func _take_to(peer_id: int, path: NodePath, idx: int, x: int, y: int, r: bool) -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= c.items.size():
		return
	var k := pl.inventory.put_at((c.items[idx] as Dictionary).duplicate(true), x, y, r)
	if k > 0:
		c.take_at(idx, k)
		Audio.play("pin", c.global_position, -8.0)


func _put(peer_id: int, path: NodePath, idx: int) -> void:
	var pl := player_of(peer_id)
	var c := _near_container(pl, path)
	if c == null or idx < 0 or idx >= pl.inventory.items.size():
		return
	var out := pl.inventory.remove_at(idx, int(pl.inventory.items[idx].n))
	if out.is_empty():
		return
	var list := c.items.duplicate(true)
	ItemDb.add_to(list, out, Vector2i.ZERO)
	c.items = list
	c.rolled = true


## Надеть / взять в руки предмет из рюкзака (индекс в items).
func request_equip(idx: int) -> void:
	if _is_host():
		_equip(multiplayer.get_unique_id(), idx)
	else:
		_rpc_equip.rpc_id(1, idx)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_give_loadout(eq: Dictionary, items: Array) -> void:
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
	if pl == null or c == null or not pl.is_alive() or is_extracted(peer_id):
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
func _give_loadout(peer_id: int, eq: Dictionary, items: Array) -> void:
	var pl := player_of(peer_id)
	if pl == null:
		return
	pl.inventory.items = items.duplicate(true)
	pl.inventory.equipment = eq.duplicate(true)
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
func _use_med(peer_id: int, id: String) -> void:
	var pl := player_of(peer_id)
	var use: Dictionary = ItemDb.item(id).get("use", {})
	if pl == null or use.is_empty() or not pl.is_alive() or pl.health.hp >= pl.health.max_hp:
		return
	if pl.inventory.remove(id, 1) == 0:
		return
	get_tree().create_timer(float(use.time)).timeout.connect(func() -> void:
		if is_instance_valid(pl) and pl.is_alive():
			pl.health.heal(float(use.heal)))


## Хост: положить на землю контейнер с вещами (тело, выброшенное). В сети — через спавнер,
## чтобы появился у всех; содержимое едет в данных спавна.
## toss — откуда предмет «вываливается» к месту pos (смещение; ноль — появляется на месте).
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
	var me := local_player()
	_update_channel_hud(me)
	_update_prompt(me)
	_toast_t -= delta
	_toast.visible = _toast_t > 0.0
	_update_summary(me)
	_save_profile(me)
	if Profile.pending_raid:
		# рейд из убежища: закончил (ушёл или погиб) — Enter возвращает в убежище
		if me != null and (not me.is_alive() or is_extracted(me.peer_id)) and Input.is_action_just_pressed("ui_accept"):
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
	if me == null or not me.is_alive() or is_extracted(me.peer_id) or over:
		return
	var here: ExtractionPoint = null
	for e in get_tree().get_nodes_in_group("extractions"):
		if e is ExtractionPoint and (e as ExtractionPoint).contains(me.global_position):
			here = e
			break
	if here == null:
		return
	_progress_label.visible = true
	var reason := extraction_block_reason(here)
	if reason != "":
		_progress_label.text = "%s — закрыто: %s" % [here.display_name, reason]
		return
	var cur: Array = channel.get(me.peer_id, [])
	var t := float(cur[1]) if cur.size() == 2 else 0.0
	_progress.visible = true
	_progress.max_value = here.channel_s
	_progress.value = t
	_progress_label.text = "ЭВАКУАЦИЯ · %s — %.1f с" % [here.display_name, maxf(0.0, here.channel_s - t)]


## Подсказка «F — …» у ближайшего предмета, с которым можно что-то сделать.
func _update_prompt(me: Player) -> void:
	_prompt.visible = false
	if me == null or not me.is_alive() or is_extracted(me.peer_id) or ui.is_looting():
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
	_prompt.text = "F — " + best.prompt()
	if Input.is_action_just_pressed("interact"):
		if best is LootContainer:
			ui.start_search(best as LootContainer)
		best.request_use()


func _update_summary(me: Player) -> void:
	var show := over or (me != null and (not me.is_alive() or is_extracted(me.peer_id)))
	_summary.visible = show
	_summary_bg.visible = show
	if not show:
		return
	var lines: Array[String] = []
	if over:
		lines.append("РЕЙД ОКОНЧЕН")
	elif is_extracted(me.peer_id):
		lines.append("ЭВАКУИРОВАН · " + String(extracted[me.peer_id]))
	else:
		lines.append("УБИТ")
	lines.append("")
	for peer in participants:
		# имя из лобби может прийти позже появления игрока — берём самое свежее
		var who := String(Net.player_names.get(peer, participants[peer]))
		if extracted.has(peer):
			lines.append("%s — эвакуировался (%s), вынес на %s ₽" % [who, String(extracted[peer]), InventoryUI.money(int(loot_value.get(peer, 0)))])
		elif dead.has(peer):
			lines.append("%s — погиб, рюкзак остался в рейде" % who)
		else:
			lines.append("%s — ещё в рейде" % who)
	lines.append("")
	if Profile.pending_raid:
		lines.append("Enter — в убежище")
	elif over:
		lines.append("R — новый рейд" if _is_host() else "ждём хоста")
	else:
		lines.append("ждём остальных")
	_summary.text = "\n".join(lines)


## Эвакуировался (владелец): снаряжение, рюкзак и патроны из магазинов — обратно в профиль.
## Погиб — ничего: снаряжение снято с профиля при входе в рейд и осталось в теле.
func _save_profile(me: Player) -> void:
	if _profile_saved or me == null or not me.loadout_mode or not is_extracted(me.peer_id):
		return
	_profile_saved = true
	var items: Array = me.inventory.items.duplicate(true)
	for e in me.mag_ammo_items():
		# патроны из магазинов — обратно в рюкзак; не влезло — без места, профиль разложит
		var placed := ItemDb.add_to(items, e, Balance.BACKPACK_GRID)
		if placed < int(e.n):
			var rest: Dictionary = (e as Dictionary).duplicate(true)
			rest.n = int(e.n) - placed
			items.append(rest)
	Profile.return_loadout(me.inventory.equipment, items, int(loot_value.get(me.peer_id, 0)))


## В убежище: из сети выходим, рейд забыт.
func go_hideout() -> void:
	Net.disconnect_all()
	Profile.pending_raid = false
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)


## Новый рейд: хост переводит всех заново в сектор; без сети — перезагрузка сцены.
func _restart() -> void:
	if not Net.is_networked():
		get_tree().reload_current_scene()
	elif multiplayer.is_server():
		Net.start_level.rpc(get_tree().current_scene.scene_file_path)


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
