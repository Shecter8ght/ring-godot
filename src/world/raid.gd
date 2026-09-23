class_name Raid
extends Node
## Состояние рейда: ключи группы, рубильники, эвакуация, итог. Считает хост, остальным
## реплицируется синхронизатором (узел создаёт SectorLevel с одинаковым именем у всех peer).
##
## Эвакуация: живой игрок стоит в зоне ExtractionPoint, зона открыта (рубильник включён, нужный
## ключ у группы) — идёт отсчёт channel_s; вышел — сброс. Досчитал — игрок эвакуирован: пропадает
## из мира, мародёры его больше не видят. Рейд окончен, когда каждый участник погиб или ушёл.
## Ключи пока общие на группу (инвентаря ещё нет): подобрал один — открывает любой.

static var current: Raid

## Кто в рейде: peer_id -> имя. Заполняет хост при появлении игроков.
var participants: Dictionary = {}
## Включённые рубильники: switch_id -> true.
var switches: Dictionary = {}
## Ключи группы: key_id -> true.
var team_keys: Dictionary = {}
## Эвакуированные: peer_id -> имя точки.
var extracted: Dictionary = {}
## Отсчёт эвакуации: peer_id -> [id точки, секунд].
var channel: Dictionary = {}
## Погибшие: peer_id -> true (хост — по сигналу Health).
var dead: Dictionary = {}
var over: bool = false
## Названия ключей для подсказок: key_id -> «Ключ от серверной» (из KeyPickup сцены, лениво).
var key_names: Dictionary = {}

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
	_build_hud()
	if Net.is_networked():
		_setup_sync()


func _exit_tree() -> void:
	if current == self:
		current = null


## Хост — авторитет (умалчиваемый 1). Словари всегда переприсваиваются копией: синхронизатор
## сравнивает значения, изменение «на месте» он бы не заметил.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:participants", ".:switches", ".:team_keys", ".:extracted", ".:dead", ".:over"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	var ch := NodePath(".:channel")
	config.add_property(ch)
	config.property_set_replication_mode(ch, SceneReplicationConfig.REPLICATION_MODE_ALWAYS)
	sync.replication_config = config
	sync.set_multiplayer_authority(get_multiplayer_authority())
	add_child(sync)


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


# ---------------------------------------------------------------- состояние (хост)

func register(peer_id: int, display_name: String) -> void:
	var p := participants.duplicate()
	p[peer_id] = display_name
	participants = p


func has_key(key_id: String) -> bool:
	return key_id == "" or team_keys.has(key_id)


func key_name(key_id: String) -> String:
	if key_names.is_empty():
		for n in get_tree().get_nodes_in_group("key_pickups"):
			key_names[(n as KeyPickup).key_id] = (n as KeyPickup).display_name
	return String(key_names.get(key_id, key_id))


func is_extracted(peer_id: int) -> bool:
	return extracted.has(peer_id)


func add_key(key_id: String) -> void:
	var k := team_keys.duplicate()
	k[key_id] = true
	team_keys = k


func set_switch(switch_id: String, on: bool) -> void:
	var s := switches.duplicate()
	s[switch_id] = on
	switches = s


func mark_dead(peer_id: int) -> void:
	if not _is_host():
		return
	var d := dead.duplicate()
	d[peer_id] = true
	dead = d
	_check_over()


## Открыта ли точка и, если нет, почему (для подсказки у зоны).
func extraction_block_reason(ext: ExtractionPoint) -> String:
	if ext.required_switch != "" and not bool(switches.get(ext.required_switch, false)):
		return "нет питания — включи рубильник"
	if ext.required_key != "" and not has_key(ext.required_key):
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
	_check_over()


func _check_over() -> void:
	if participants.is_empty():
		return
	for peer in participants:
		if not extracted.has(peer) and not dead.has(peer):
			return
	over = true


# ---------------------------------------------------------------- HUD (у каждого peer)

func _process(delta: float) -> void:
	var me := _local_player()
	_update_channel_hud(me)
	_update_prompt(me)
	_toast_t -= delta
	_toast.visible = _toast_t > 0.0
	_update_summary(me)
	if over and Input.is_action_just_pressed("reload"):
		_restart()


## Короткое сообщение внизу по центру («Заперто: нужен …»).
func notify(text: String) -> void:
	_toast.text = text
	_toast_t = 2.5


func _local_player() -> Player:
	for node in get_tree().get_nodes_in_group("all_players"):
		var pl := node as Player
		if pl and pl.is_local():
			return pl
	return null


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
	if me == null or not me.is_alive() or is_extracted(me.peer_id):
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
			lines.append("%s — эвакуировался (%s)" % [who, String(extracted[peer])])
		elif dead.has(peer):
			lines.append("%s — погиб" % who)
		else:
			lines.append("%s — ещё в рейде" % who)
	lines.append("")
	if over:
		lines.append("R — новый рейд" if _is_host() else "ждём хоста")
	else:
		lines.append("ждём остальных")
	_summary.text = "\n".join(lines)


## Новый рейд: хост переводит всех заново в сектор; без сети — перезагрузка сцены.
func _restart() -> void:
	if not Net.is_networked():
		get_tree().reload_current_scene()
	elif multiplayer.is_server():
		Net.start_level.rpc()


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
	_summary.offset_left = -360
	_summary.offset_right = 360
	_summary.offset_top = -170
	_summary.offset_bottom = 170
	_summary.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_summary.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_summary.add_theme_font_size_override("font_size", 26)
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
