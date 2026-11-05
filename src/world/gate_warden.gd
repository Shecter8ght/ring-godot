class_name GateWarden
extends Marker3D
## Ворота кордона (docs/design/prologue.md §8 — в прологе и в обычных рейдах): бойцы поста post_name (ЧВК
## «Периметр») держат ворота и игроков не трогают, пока те не подошли к воротам ближе
## Balance.GATE_WARDEN.zone_m. Подошёл — окрик; стоит — предупредительный в воздух; всё ещё стоит — огонь:
## бойцы поста враждебны игрокам, как обычные ЧВК, до конца рейда. Попал в бойца — огонь сразу. Ушёл от
## ворот до огня — через reset_sec всё сначала. Считает хост; окрик и выстрел видят и слышат все (их
## рассылают сами бойцы). Узел ставит build_prospekt_raid.py у ворот в плитах.

## 1 — окрик, 2 — предупредительный, 3 — огонь (пролог: Михалыч «Я же сказал»).
signal escalated(stage: int)

## Пост ЧВК у ворот (AIPost, имя узла): его бойцы — охрана ворот.
@export var post_name: String = "Cordon_PMC"

var stage: int = 0
var hostile: bool = false
var _t: float = 0.0
var _away: float = 0.0
var _scan: float = 0.0
var _guards: Array[Marauder] = []


func _ready() -> void:
	add_to_group("gate_wardens")
	# боец поста появился — «мирный» сразу, до первого взгляда (заход пролога — у самых ворот)
	get_tree().node_added.connect(_on_node_added)


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
	if hostile:
		return
	for g in _guards:
		if is_instance_valid(g) and g.last_attacker() > 0:
			_open_fire()
			return
	var cfg: Dictionary = Balance.GATE_WARDEN
	if _player_at_gate(float(cfg.zone_m)):
		_away = 0.0
		_t += delta
		if stage == 0:
			_set_stage(1)
			var g := _nearest()
			if g:
				g.say("Стой! Назад!")
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
		m.set_meta("gate_warden", true)
		m.hostile_to_players = hostile
		_guards.append(m)
	# живые охранники; filter возвращает нетипизированный Array — его нельзя присвоить Array[Marauder] (ошибка на каждой
	# проверке, погибшие и удалённые оставались в списке), поэтому собираем заново
	var alive: Array[Marauder] = []
	for g: Variant in _guards:
		if is_instance_valid(g) and (g as Marauder).state != Marauder.State.DEAD:
			alive.append(g as Marauder)
	_guards = alive


func _player_at_gate(zone_m: float) -> bool:
	for n in get_tree().get_nodes_in_group("players"):
		var p := n as Player
		if p == null or not p.is_alive():
			continue
		if Vector2(p.global_position.x - global_position.x, p.global_position.z - global_position.z).length() < zone_m:
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


func _set_stage(s: int) -> void:
	stage = s
	escalated.emit(s)
