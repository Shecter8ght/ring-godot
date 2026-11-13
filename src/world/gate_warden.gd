class_name GateWarden
extends Marker3D
## Ворота кордона (docs/design/prologue.md §8 — в прологе и в обычных рейдах): бойцы поста post_name (ЧВК
## «Периметр») держат ворота и игроков не трогают, пока те не подошли к воротам ближе
## Balance.GATE_WARDEN.zone_m. Подошёл — окрик; стоит — предупредительный в воздух; всё ещё стоит — огонь:
## бойцы поста враждебны игрокам до конца рейда, но держат свой участок. Попал в бойца — огонь сразу. Ушёл от
## ворот до огня — через reset_sec всё сначала. Считает хост; окрик и выстрел видят и слышат все (их
## рассылают сами бойцы). Узел ставит build_prospekt_raid.py у ворот в плитах.

## 1 — окрик, 2 — предупредительный, 3 — огонь (пролог: Михалыч «Я же сказал»).
signal escalated(stage: int)

## Пост ЧВК у ворот (AIPost, имя узла): его бойцы — охрана ворот.
@export var post_name: String = "Cordon_PMC"
## Направление от ворот к району, в локальных координатах узла.
@export var approach: Vector3 = Vector3.RIGHT

var stage: int = 0
var hostile: bool = false
var seconds_left: int = 0
var occupied: bool = false
var _t: float = 0.0
var _away: float = 0.0
var _scan: float = 0.0
var _guards: Array[Marauder] = []


func _ready() -> void:
	add_to_group("gate_wardens")
	_draw_boundary()
	# боец поста появился — «мирный» сразу, до первого взгляда (заход пролога — у самых ворот)
	get_tree().node_added.connect(_on_node_added)
	Net.scenes_changed.connect(_send_warning)


func _exit_tree() -> void:
	if get_tree().node_added.is_connected(_on_node_added):
		get_tree().node_added.disconnect(_on_node_added)


func _on_node_added(n: Node) -> void:
	if n is Marauder and _is_host():
		_collect.call_deferred()


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


func _physics_process(delta: float) -> void:
	if not _is_host():
		return
	_scan -= delta
	if _scan <= 0.0:
		_scan = 0.5
		_collect()
	if hostile or not occupied:
		return
	for g in _guards:
		if is_instance_valid(g) and g.last_attacker() > 0:
			_open_fire()
			return
	var cfg: Dictionary = Balance.GATE_WARDEN
	if _player_at_gate():
		_away = 0.0
		_t += delta
		if stage == 0:
			_set_stage(1)
			var g := _nearest()
			if g:
				g.say("Стой! Назад за линию!", "ai_cordon_warning")
		elif stage == 1 and _t >= float(cfg.shout_sec):
			_set_stage(2)
			var g := _nearest()
			if g:
				g.warning_shot()
		elif stage == 2 and _t >= float(cfg.shout_sec) + float(cfg.warn_sec):
			_open_fire()
	elif stage > 0:
		_away += delta
		if _away >= float(cfg.reset_sec):
			stage = 0
			_t = 0.0
	var left := ceili(maxf(0.0, float(cfg.shout_sec) + float(cfg.warn_sec) - _t)) if stage in [1, 2] else 0
	if left != seconds_left:
		seconds_left = left
		_send_warning()


## Бойцы поста: ЧВК, чей дом — у поста; новые (пост занимается после навигации) — сразу «мирные».
func _collect() -> void:
	var post: AIPost = null
	for n in get_tree().get_nodes_in_group("ai_posts"):
		if String(n.name) == post_name:
			post = n as AIPost
	if post == null:
		return
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == null or m.faction != "pmc" or m.home == Vector3.INF or _guards.has(m):
			continue
		if m.home.distance_to(post.global_position) > post.radius + 2.0:
			continue
		m.assign_gate_post(hostile, global_basis * approach)
		_guards.append(m)
	# живые охранники; filter возвращает нетипизированный Array — его нельзя присвоить Array[Marauder] (ошибка на каждой
	# проверке, погибшие и удалённые оставались в списке), поэтому собираем заново
	var alive: Array[Marauder] = []
	for g: Variant in _guards:
		if is_instance_valid(g) and (g as Marauder).state != Marauder.State.DEAD:
			alive.append(g as Marauder)
	_guards = alive
	var has_guards := not _guards.is_empty()
	if occupied != has_guards:
		occupied = has_guards
		if not occupied and not hostile:
			stage = 0
			_t = 0.0
			seconds_left = 0
		_send_warning()


func _player_at_gate() -> bool:
	for n in get_tree().get_nodes_in_group("players"):
		var p := n as Player
		if p == null or not p.is_alive() or (Raid.current and Raid.current.has_left(p.peer_id)):
			continue
		if is_past_line(p.global_position):
			return true
	return false


func _nearest() -> Marauder:
	var best: Marauder = null
	var best_d := INF
	for g in _guards:
		if not is_instance_valid(g) or g.state == Marauder.State.DEAD:
			continue
		var d := g.global_position.distance_to(global_position)
		if d < best_d:
			best = g
			best_d = d
	return best


func _open_fire() -> void:
	hostile = true
	for g in _guards:
		if is_instance_valid(g):
			g.hostile_to_players = true
	_set_stage(3)
	seconds_left = 0
	_send_warning()


func _set_stage(s: int) -> void:
	stage = s
	escalated.emit(s)


func _distance(pos: Vector3) -> float:
	var d := pos - global_position
	return Vector2(d.x, d.z).length() if absf(d.y) <= float(Balance.GATE_WARDEN.height_m) else INF


func is_past_line(pos: Vector3) -> bool:
	return _distance(pos) < float(Balance.GATE_WARDEN.zone_m)


## Подсказка для каждого игрока показывается по его расстоянию; время — от хоста.
func player_hint(pos: Vector3) -> String:
	var dist := _distance(pos)
	var zone := float(Balance.GATE_WARDEN.zone_m)
	if not occupied or dist > float(Balance.GATE_WARDEN.notice_m):
		return ""
	if hostile:
		return "КОРДОН ОТКРЫЛ ОГОНЬ  ·  ОТОЙДИТЕ"
	if dist >= zone:
		return "КОРДОН  ·  ДО СТОП-ЛИНИИ %d м" % maxi(1, ceili(dist - zone))
	var warning := "ПРЕДУПРЕДИТЕЛЬНЫЙ ВЫСТРЕЛ  ·  " if stage == 2 else ""
	return warning + "НАЗАД ЗА ЛИНИЮ  ·  ДО ОГНЯ %d с" % seconds_left if seconds_left > 0 else "КОРДОН  ·  НАЗАД ЗА ЛИНИЮ"


func _send_warning() -> void:
	if _is_host() and Net.is_networked():
		Net.broadcast_scene(self, &"_sync_warning", [stage, seconds_left, occupied], false)


@rpc("authority", "call_remote", "reliable")
func _sync_warning(value: int, left: int, has_guards: bool) -> void:
	stage = value
	hostile = stage == 3
	seconds_left = left
	occupied = has_guards


func _draw_boundary() -> void:
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_color = Color("dfab48")
	var mesh := ImmediateMesh.new()
	mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLE_STRIP, material)
	var radius := float(Balance.GATE_WARDEN.zone_m)
	for i in range(65):
		var angle := TAU * float(i) / 64.0
		var direction := Vector3(cos(angle), 0.0, sin(angle))
		mesh.surface_add_vertex(direction * radius + Vector3.UP * 0.08)
		mesh.surface_add_vertex(direction * (radius + 0.13) + Vector3.UP * 0.08)
	mesh.surface_end()
	var line := MeshInstance3D.new()
	line.name = "StopLine"
	line.mesh = mesh
	line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(line)
