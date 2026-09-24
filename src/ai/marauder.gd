class_name Marauder
extends CharacterBody3D
## Мародёр: ходит отрядом по контейнерам и грабит их (ведущий роется, отряд прикрывает; сумка
## выпадает с трупа) → расследование шума → бой → поиск, раненый — отход.
## Позицию игрока получает только через Perception.can_see (зрение), NoiseBus.noise (слух) и
## NoiseBus.callout (окрик товарища, который сам видел цель) — никакого прямого чтения.
## Ходит по навмешу сектора, двери открывает сам (см. door.gd). Считает только хост.
##
## Бой — тактики: ENGAGE (стоит и стреляет), COVER_MOVE → COVER_HIDE ↔ COVER_PEEK (укрытие:
## присел, выглянул, дал очередь), FLANK (второй в отряде заходит сбоку), PUSH (идёт к последней
## известной точке), ADVANCE — перебежками от укрытия к укрытию к цели, которую не видно
## (попали издалека — угадал направление, сел за укрытие и двигается к стрелку). Не стреляет, если
## между стволом и целью стена. Не толпится: точки, куда уже идут другие, обходит; поиск —
## прочёсывание дугой от ближних точек к дальним. Тяжело ранен (DOWNED) — лежит, стреляет из
## пистолета, зовёт; ближайший товарищ, который слышал (AI_RESCUE_RADIUS), идёт спасать (RESCUE):
## лежит на виду — тащит за укрытие, потом поднимает (аптечка, AI_REVIVE_SEC). Лежащего игрока
## добивает, только если никто другой не стреляет (AI_FINISH_QUIET_SEC). Оружие (AI_WEAPONS): пистолет, автомат очередями, дробовик; магазин и
## перезарядка — в укрытии, если оно есть. Точность садится за AI_AIM_SETTLE_SEC после того, как
## заметил цель; бегущую цель и на бегу — хуже.

enum State { PATROL, INVESTIGATE, COMBAT, SEARCH, RETREAT, DEAD, DOWNED, RESCUE }
enum Tactic { ENGAGE, COVER_MOVE, COVER_HIDE, COVER_PEEK, FLANK, PUSH, ADVANCE }

const EYE_HEIGHT := 1.6
const CROUCH_EYE := 1.05

var state: State = State.PATROL
var tactic: Tactic = Tactic.ENGAGE
## Оружие (ключ Balance.AI_WEAPONS): ставит спавнер до добавления в дерево; пусто — по типу.
var weapon: String = ""
## Тип (ключ Balance.AI_ARCHETYPES): разведчик, штурмовик, тяжёлый, снайпер; пусто — случайный.
var archetype: String = ""
var squad: Squad
## Откуда брать точки патруля: Callable() -> Vector3 (даёт сцена сектора).
var patrol_point_provider: Callable
var last_known: Vector3 = Vector3.ZERO
var memory_timer: float = 0.0
var notice_timer: float = 0.0
var pause_timer: float = 0.0
var linger_timer: float = 0.0
## Присел (в укрытии) — ниже силуэт и коллизия; синхронизируется на клиентов.
var crouched: bool = false

var _rng := RandomNumberGenerator.new()
var _target_player: Player = null
var _facing: float = 0.0
var _nav_ready: bool = false
var _ragdoll: Ragdoll
var _last_hit_from: Vector3 = Vector3.ZERO
var _last_damage: float = 0.0
var _spec: Dictionary = {}
var _mag: int = 0
var _reload_t: float = 0.0
var _shot_t: float = 0.0
var _burst_left: int = 0
## Прицел «садится»: 1 — точно, AI_AIM_COLD — только что заметил.
var _aim: float = 1.0
var _seen_now: bool = false
var _unseen_t: float = 99.0
var _callout_t: float = 0.0
var _tactic_t: float = 0.0
var _cover_pos: Vector3 = Vector3.ZERO
var _peeks: int = 0
var _hurt_t: float = 0.0
var _suppress_t: float = 0.0
var _search_left: int = 0
var _search_total: int = 0
var _search_ang: float = 0.0
var _repath_t: float = 0.0
var _say_label: Label3D
var _arch: Dictionary = {}
var _base_scale: Vector3 = Vector3.ONE
## Попадание: «повело» (медленнее, хуже целится) и откинуло корпус назад.
var _stagger_t: float = 0.0
var _flinch: float = 0.0
## Пост (где появился) — у держащего позицию патруль вокруг него.
var _post: Vector3 = Vector3.INF
## Раненый: кто идёт спасать (null — никто), кто тащит; основное оружие на время пистолета.
var rescuer: Marauder = null
var dragged_by: Marauder = null
var _main_spec: Dictionary = {}
var _main_mag: int = 0
var _main_gun: Node3D
var _help_t: float = 0.0
var _shown_down: bool = false
## Спасатель: кого, фаза (0 — бежит, 1 — тащит, 2 — поднимает), сколько поднимает.
var _rescue_target: Marauder = null
var _rescue_phase: int = 0
var _rescue_t: float = 0.0
## Грабёж: куда идёт ведущий, сколько роется, что уже взял (сумка), где уже был.
## Метки «этот контейнер наш» — общие для всех: id контейнера -> [мародёр, время, мс].
static var _loot_claims: Dictionary = {}
var pack: Array = []
var _loot_target: LootContainer = null
var _loot_t: float = -1.0
var _rummage_t: float = 0.0
var _visited: Dictionary = {}
## Слышал выстрел игрока: сколько секунд назад и где (добивать лежащего — только в тишине).
var _shot_heard_t: float = 99.0
var _shot_heard_pos: Vector3 = Vector3.INF
var _capsule: CapsuleShape3D

@onready var _agent: NavigationAgent3D = $NavigationAgent3D
@onready var _health: Health = $Health
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle


func _ready() -> void:
	add_to_group("marauders")
	_rng.seed = hash(name) + int(global_position.x * 13.0)
	if not Balance.AI_ARCHETYPES.has(archetype):
		archetype = pick_archetype(_rng)
	_arch = Balance.AI_ARCHETYPES[archetype]
	if weapon == "" or not Balance.AI_WEAPONS.has(weapon):
		weapon = weapon_for(archetype, _rng)
	_spec = Balance.AI_WEAPONS[weapon]
	_mag = int(_spec.mag)
	_health.max_hp = Balance.MARAUDER_HP * float(_arch.hp)
	_health.hp = _health.max_hp
	# броня: проходит только доля урона
	var armor := float(_arch.armor)
	if armor < 1.0:
		_health.damage_filter = func(a: float, _zone: String) -> float: return a * armor
	# тяжело ранен вместо смерти; в шлеме (тяжёлый) голова держит
	_health.can_down = true
	_health.head_protected = func() -> bool: return bool(_arch.get("helmet", false))
	_health.downed_changed.connect(_on_downed_changed)
	# видно, кто перед тобой: цвет куртки и фигура (тяжёлый шире, разведчик уже)
	_base_scale = _arch.scale
	_body.scale = _base_scale
	var torso := _body.get_node("Torso") as MeshInstance3D
	var coat := (torso.get_surface_override_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	coat.albedo_color = _arch.color
	torso.set_surface_override_material(0, coat)
	_health.died.connect(_on_died)
	_health.damaged.connect(_on_damaged)
	NoiseBus.noise.connect(_on_noise)
	NoiseBus.callout.connect(_on_callout)
	_agent.path_desired_distance = 0.6
	_agent.target_desired_distance = 0.8
	_agent.radius = 0.4
	_muzzle.visible = false
	# своя форма коллизии — присев, мародёр ниже (форма в сцене общая для всех)
	var cs := $Capsule as CollisionShape3D
	_capsule = (cs.shape as CapsuleShape3D).duplicate()
	cs.shape = _capsule
	# оружие в правой руке — видно, чем вооружён; при смерти прячется вместе с телом
	var gun := WeaponModels.build(String(_spec.model))
	gun.position = Vector3(-0.17, 1.24, 0.3 if weapon == "pistol" else 0.22) / _base_scale
	_body.add_child(gun)
	_main_gun = gun
	pause_timer = _rng.randf_range(0.5, 2.0)
	# шаги слышны у всех peer (AI считает хост, позицию клиенты получают синхронизатором)
	var steps := Footsteps.new()
	steps.name = "Footsteps"
	steps.ai = true
	steps.loud_db = func() -> float: return -5.0 if crouched else 0.0
	add_child(steps)
	# Навмеш печётся после загрузки сектора — пока его нет, стоим (готовность проверяем в
	# _physics_process: появившийся позже сигнала map_changed не должен стоять вечно).
	NavigationServer3D.map_changed.connect(func(_m: RID) -> void: _nav_ready = true)
	if Net.is_networked():
		_setup_sync()


## Случайный тип по долям AI_ARCHETYPES.
static func pick_archetype(rng: RandomNumberGenerator) -> String:
	var total := 0.0
	for k in Balance.AI_ARCHETYPES:
		total += float(Balance.AI_ARCHETYPES[k].weight)
	var pick := rng.randf() * total
	for k in Balance.AI_ARCHETYPES:
		pick -= float(Balance.AI_ARCHETYPES[k].weight)
		if pick <= 0.0:
			return String(k)
	return "gunner"


## Оружие для типа — случайное из его списка.
static func weapon_for(arch: String, rng: RandomNumberGenerator) -> String:
	var list: Array = Balance.AI_ARCHETYPES.get(arch, Balance.AI_ARCHETYPES.gunner).weapons
	return String(list[rng.randi_range(0, list.size() - 1)])


## Куда попала пуля: голова — выше HEAD_ZONE (присел — ниже), лежащий — всё корпус.
func hit_zone(point: Vector3) -> String:
	if _health.downed:
		return "body"
	var hz := float(Balance.HEAD_ZONE["crouch" if crouched else "stand"]) * _base_scale.y
	return "head" if point.y - global_position.y >= hz else "body"


## Держит позицию (снайпер): не сближается, ищет глазами.
func _holds() -> bool:
	return bool(_arch.get("holds", false))


## Память о цели по типу (разведчик забывает быстро, снайпер помнит долго).
func _mem() -> float:
	return Balance.AI_MEMORY_SEC * float(_arch.get("memory", 1.0))


## Случайное оружие по долям AI_WEAPONS.
static func pick_weapon(rng: RandomNumberGenerator) -> String:
	var total := 0.0
	for k in Balance.AI_WEAPONS:
		total += float(Balance.AI_WEAPONS[k].weight)
	var pick := rng.randf() * total
	for k in Balance.AI_WEAPONS:
		pick -= float(Balance.AI_WEAPONS[k].weight)
		if pick <= 0.0:
			return String(k)
	return "pistol"


## Мародёр целиком авторитет хоста (умалчиваемый multiplayer authority узла — 1). AI и движение
## считает только хост; остальные peer просто получают позицию/позу синхронизатором.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", "Body:position", "Body:scale", ".:state", ".:crouched"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	add_child(sync)


func _physics_process(delta: float) -> void:
	if Net.is_networked() and not is_multiplayer_authority():
		return
	if state == State.DEAD:
		return
	if not _nav_ready:
		var map := get_world_3d().navigation_map
		_nav_ready = NavigationServer3D.map_get_iteration_id(map) > 0 and not NavigationServer3D.map_get_regions(map).is_empty()
	_hurt_t = maxf(0.0, _hurt_t - delta)
	_stagger_t = maxf(0.0, _stagger_t - delta)
	_flinch = move_toward(_flinch, 0.0, delta * 3.0)
	if _post == Vector3.INF:
		_post = global_position
	_suppress_t = maxf(0.0, _suppress_t - delta)
	_shot_heard_t += delta
	_repath_t -= delta
	_perceive(delta)
	_tick_weapon(delta)
	match state:
		State.DOWNED:
			_downed(delta)
		State.RESCUE:
			_rescue(delta)
		State.PATROL:
			_patrol(delta)
		State.INVESTIGATE:
			_investigate(delta)
		State.COMBAT:
			_combat(delta)
		State.SEARCH:
			_search(delta)
		State.RETREAT:
			_retreat(delta)
	_move(delta)


func _eye() -> Vector3:
	return global_position + Vector3.UP * (CROUCH_EYE if crouched else EYE_HEIGHT)


# ---------------------------------------------------------------- восприятие

func _perceive(delta: float) -> void:
	var seen: Player = null
	var seen_down: Player = null
	var fwd := Vector3(sin(_facing), 0.0, cos(_facing))
	var exclude: Array[RID] = [get_rid()]
	for p in get_tree().get_nodes_in_group("players"):
		var player := p as Player
		if player == null or not player.is_alive():
			continue
		if Perception.can_see(get_world_3d(), _eye(), fwd, player, exclude, float(_arch.get("view", 1.0))):
			if player.is_downed():
				if seen_down == null:
					seen_down = player
			else:
				seen = player
				break
	# лежащий — не угроза, пока стреляют другие; стреляет сам или тихо — добить
	if seen == null and seen_down != null and _may_finish(seen_down):
		seen = seen_down
	var was_seen := _seen_now
	_seen_now = false
	if seen:
		# Заметить — не мгновенно: чем ближе, тем быстрее.
		var dist := global_position.distance_to(seen.global_position)
		notice_timer += delta * clampf(30.0 / maxf(dist, 1.0), 1.0, 6.0)
		if notice_timer >= Balance.AI_NOTICE_SEC or state == State.COMBAT:
			_seen_now = true
			_unseen_t = 0.0
			_target_player = seen
			last_known = seen.global_position
			memory_timer = _mem()
			if not was_seen:
				# только что поймал в поле зрения — первые выстрелы мимо
				_aim = Balance.AI_AIM_COLD
			if state != State.COMBAT and state != State.RETREAT and state != State.DOWNED and state != State.RESCUE:
				_enter_combat(Tactic.ENGAGE)
				say("Контакт!")
				_shout()
			_callout_t -= delta
			if _callout_t <= 0.0:
				_shout()
	else:
		notice_timer = maxf(0.0, notice_timer - delta)
		_unseen_t += delta
		if state == State.COMBAT:
			memory_timer -= delta
			if memory_timer <= 0.0:
				_start_search()
	# прицел садится, пока цель на виду
	if _seen_now:
		_aim = move_toward(_aim, 1.0, delta * (Balance.AI_AIM_COLD - 1.0) / Balance.AI_AIM_SETTLE_SEC)


## Добить лежащего игрока можно, если давно никто не стрелял — или стреляет он сам.
func _may_finish(p: Player) -> bool:
	return _shot_heard_t >= Balance.AI_FINISH_QUIET_SEC or _shot_heard_pos.distance_to(p.global_position) < 2.5


## Окрик: товарищи в радиусе узнают, где цель (сами её могут и не видеть).
func _shout() -> void:
	_callout_t = Balance.AI_CALLOUT_EVERY
	NoiseBus.shout(global_position, Balance.AI_CALLOUT_RADIUS, last_known, self)


func _on_callout(from: Vector3, radius_m: float, target: Vector3, speaker: Node) -> void:
	if speaker == self or state in [State.DEAD, State.RETREAT, State.DOWNED, State.RESCUE]:
		return
	if global_position.distance_to(from) > radius_m:
		return
	if _seen_now:
		return
	last_known = target
	memory_timer = maxf(memory_timer, _mem() * 0.6)
	if state != State.COMBAT:
		# сам не видел — идёт туда, куда крикнули (второй в отряде — в обход, далеко — перебежками)
		_enter_combat(Tactic.FLANK if _rank() == 1 else _closing_tactic())


func _on_noise(pos: Vector3, radius_m: float, kind: String) -> void:
	if state == State.DEAD:
		return
	if kind == "shot" and global_position.distance_to(pos) <= radius_m:
		_shot_heard_t = 0.0
		_shot_heard_pos = pos
	if state == State.DOWNED or state == State.RESCUE:
		return
	var d := global_position.distance_to(pos)
	if d > radius_m:
		return
	if state == State.COMBAT:
		# стреляет цель, которую мы и так ищем, — пули свистят рядом: пора в укрытие
		if kind == "shot" and pos.distance_to(last_known) < 8.0 and d < Balance.AI_ENGAGE_RANGE:
			_suppress_t = 2.0
			if not _seen_now:
				last_known = pos
		return
	if state == State.RETREAT:
		return
	# ведомый: шёпотом ведущему — проверяют отрядом, строем за ним
	var lead := squad.leader() if squad else null
	if lead != null and lead != self and lead.state in [State.PATROL, State.INVESTIGATE] \
			and lead.global_position.distance_to(global_position) < 15.0:
		lead.investigate_at(pos)
		return
	# другой отряд уже идёт смотреть это место — не толпимся (если шум не под самым носом)
	if d > Balance.AI_INVESTIGATE_NEAR and _someone_checking(pos):
		return
	investigate_at(pos)


## Проверить шум: идти к месту, постоять, осмотреться; потом прочесать рядом.
func investigate_at(pos: Vector3) -> void:
	if state in [State.COMBAT, State.RETREAT, State.DEAD, State.DOWNED, State.RESCUE]:
		return
	last_known = pos
	state = State.INVESTIGATE
	linger_timer = Balance.AI_INVESTIGATE_LINGER
	# держащий позицию — не идёт, только поворачивается на шум
	_agent.target_position = global_position if _holds() else _snap(pos)
	if _holds():
		_face(pos)


## Другой отряд уже проверяет / прочёсывает место рядом с pos.
func _someone_checking(pos: Vector3) -> bool:
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.squad == squad or not (m.state in [State.INVESTIGATE, State.SEARCH]):
			continue
		if m.last_known.distance_to(pos) < Balance.AI_INVESTIGATE_SHARE_M:
			return true
	return false


## Куда сейчас идёт (для «не толпиться»): цель навигации.
func move_target() -> Vector3:
	return _agent.target_position


## Кто-то другой (жив, в бою/поиске/проверке) уже идёт к точке или стоит ближе r.
func _claimed_near(p: Vector3, r: float) -> bool:
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.state in [State.DEAD, State.PATROL]:
			continue
		if m.move_target().distance_to(p) < r or m.global_position.distance_to(p) < r * 0.6:
			return true
	return false


## Точка рядом с center, куда никто не идёт: сам center, если свободен, иначе в стороне.
func _spread_point(center: Vector3) -> Vector3:
	var c := _snap(center)
	if not _claimed_near(c, Balance.AI_SPREAD_CLAIM_M):
		return c
	for i in range(8):
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(float(Balance.AI_SPREAD_RADIUS[0]), float(Balance.AI_SPREAD_RADIUS[1]))
		var p := _snap(center + Vector3(cos(a), 0.0, sin(a)) * r)
		if absf(p.y - c.y) < 0.5 and not _claimed_near(p, Balance.AI_SPREAD_CLAIM_M):
			return p
	return c


func _on_damaged(amount: float, from: Vector3) -> void:
	_last_hit_from = from
	_last_damage = amount
	if state == State.DEAD:
		return
	_hurt_t = 2.5
	# повело: медленнее, целится хуже, следующий выстрел позже; корпус откинуло (тяжёлого — меньше)
	_stagger_t = Balance.AI_HIT_STAGGER_SEC
	_flinch = clampf(amount / 25.0, 0.4, 1.0) / float(_arch.get("hp", 1.0))
	_shot_t = maxf(_shot_t, Balance.AI_HIT_FLINCH_DELAY)
	# Попадание — улика: откуда прилетело, понятно примерно (направление ± AI_HIT_DIR_ERR_DEG,
	# дальность ± AI_HIT_DIST_ERR); кого видит — того и так знает
	if not _seen_now:
		var to := from - global_position
		to.y = 0.0
		var guess := to.rotated(Vector3.UP, deg_to_rad(_rng.randf_range(-1.0, 1.0) * Balance.AI_HIT_DIR_ERR_DEG))
		guess *= 1.0 + _rng.randf_range(-1.0, 1.0) * Balance.AI_HIT_DIST_ERR
		last_known = global_position + guess
	memory_timer = maxf(memory_timer, _mem() * 1.5)
	_facing = atan2(last_known.x - global_position.x, last_known.z - global_position.z)
	if state == State.DOWNED or state == State.RESCUE or _health.downed:
		return
	if state != State.COMBAT and state != State.RETREAT:
		state = State.COMBAT
		say("По нам стреляют!")
		_shout()
		# стрелка не видно — сначала за укрытие, потом перебежками к нему
		if _seen_now or not _try_cover(Balance.AI_COVER_RADIUS, false):
			_set_tactic(Tactic.ENGAGE if _seen_now else Tactic.ADVANCE)
	elif not _seen_now and tactic in [Tactic.ENGAGE, Tactic.PUSH, Tactic.FLANK, Tactic.ADVANCE]:
		_try_cover(Balance.AI_COVER_RADIUS, false)
	# тяжело ранен, товарищей рядом нет — отход
	if _health.hp < _health.max_hp * Balance.AI_RETREAT_HP and _mates_near(15.0) == 0 and state != State.RETREAT:
		_start_retreat()


# ---------------------------------------------------------------- состояния

func _rank() -> int:
	return squad.rank_of(self) if squad else 0


func _mates_near(r: float) -> int:
	if squad == null:
		return 0
	var n := 0
	for m in squad.alive():
		if m != self and m.global_position.distance_to(global_position) <= r:
			n += 1
	return n


func _patrol(delta: float) -> void:
	if _loot_t < 0.0:
		_set_crouch(false)
	if not _nav_ready:
		return
	var lead := squad.leader() if squad else null
	if lead != null and lead != self:
		# ведомый: строем за ведущим, чуть в стороне
		if _repath_t <= 0.0:
			_repath_t = 0.5
			var lf := Vector3(sin(lead._facing), 0.0, cos(lead._facing))
			var side := Vector3(lf.z, 0.0, -lf.x) * (1.0 if _rank() % 2 == 1 else -1.0)
			_agent.target_position = _snap(lead.global_position - lf * Balance.AI_FOLLOW_DIST * _rank() + side * 1.0)
		return
	if _agent.is_navigation_finished():
		pause_timer -= delta
		if _loot_tick(delta):
			return
		if pause_timer <= 0.0 and _holds() and _post != Vector3.INF:
			# держит позицию: пара шагов у поста, долго смотрит
			var a := _rng.randf() * TAU
			_agent.target_position = _snap(_post + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(0.0, Balance.AI_HOLD_PATROL_R))
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1])) * 3.0
		elif pause_timer <= 0.0 and not _holds() and _pick_loot():
			pass
		elif pause_timer <= 0.0 and patrol_point_provider.is_valid():
			_agent.target_position = _snap(patrol_point_provider.call())
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1]))


# ---------------------------------------------------------------- грабёж

## Выбрать контейнер: ближний (с разбросом), не пустой, не занятый другими, где ещё не был.
func _pick_loot() -> bool:
	if pack.size() >= Balance.AI_LOOT_PACK_MAX:
		return false
	var now := Time.get_ticks_msec()
	var best: LootContainer = null
	var best_s := INF
	for n in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null or (c.rolled and c.items.is_empty()) or _visited.has(c.get_instance_id()):
			continue
		var claim: Array = _loot_claims.get(c.get_instance_id(), [])
		if not claim.is_empty() and is_instance_valid(claim[0]) and claim[0] != self and now - int(claim[1]) < int(Balance.AI_LOOT_CLAIM_SEC * 1000.0):
			continue
		var d := c.global_position.distance_to(global_position)
		if d > Balance.AI_LOOT_RANGE:
			continue
		var s := d + _rng.randf() * 20.0
		if s < best_s:
			best = c
			best_s = s
	if best == null:
		return false
	_drop_loot_claim()
	_loot_target = best
	_loot_t = -1.0
	_loot_claims[best.get_instance_id()] = [self, now]
	_agent.target_position = _snap(best.global_position)
	return true


func _drop_loot_claim() -> void:
	if _loot_target and is_instance_valid(_loot_target):
		var claim: Array = _loot_claims.get(_loot_target.get_instance_id(), [])
		if not claim.is_empty() and claim[0] == self:
			_loot_claims.erase(_loot_target.get_instance_id())
	_loot_target = null
	_loot_t = -1.0


## Ведущий у контейнера: присел, роется (слышно), забрал ценное. true — занят грабежом.
func _loot_tick(delta: float) -> bool:
	if _loot_target == null:
		return false
	if not is_instance_valid(_loot_target) or (_loot_target.rolled and _loot_target.items.is_empty() and _loot_t < 0.0):
		_drop_loot_claim()
		return false
	if _loot_t < 0.0:
		var to_c := _loot_target.global_position - global_position
		if Vector2(to_c.x, to_c.z).length() > 2.4:
			# ещё идёт; застрял (дошёл, а не рядом) — бросить
			if _agent.is_navigation_finished():
				_visited[_loot_target.get_instance_id()] = true
				_drop_loot_claim()
				return false
			return true
		_loot_t = maxf(Balance.AI_LOOT_SEARCH_MIN, _loot_target.search_s * Balance.AI_LOOT_SEARCH_MULT)
		_agent.target_position = global_position
	_set_crouch(true)
	_face(_loot_target.global_position)
	_loot_t -= delta
	_rummage_t -= delta
	if _rummage_t <= 0.0:
		_rummage_t = _rng.randf_range(0.5, 1.1)
		Audio.play("rummage", _loot_target.global_position, _rng.randf_range(-3.0, 0.0))
	if _loot_t > 0.0:
		return true
	_take_loot(_loot_target)
	_visited[_loot_target.get_instance_id()] = true
	_drop_loot_claim()
	_set_crouch(false)
	# разбирает, что взял, осматривается — и дальше
	pause_timer = _rng.randf_range(2.0, 5.0)
	return true


## Забрать из контейнера самое ценное (до AI_LOOT_TAKE записей) в сумку.
func _take_loot(c: LootContainer) -> void:
	c.roll()
	var list := c.items.duplicate(true)
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return ItemDb.entry_value(a) > ItemDb.entry_value(b))
	var took := 0
	for e in list:
		if took >= Balance.AI_LOOT_TAKE or pack.size() >= Balance.AI_LOOT_PACK_MAX:
			break
		var n := c.take(String(e.id), int(e.n))
		if n <= 0:
			continue
		var got: Dictionary = (e as Dictionary).duplicate(true)
		got.n = n
		pack.append(got)
		took += 1
	if took > 0 and _rng.randf() < 0.3:
		say("Есть кое-что")


func _investigate(delta: float) -> void:
	_set_crouch(false)
	if _agent.is_navigation_finished():
		linger_timer -= delta
		# осматриваемся
		_facing += delta * 1.2
		if linger_timer <= 0.0:
			_start_search(Balance.AI_INVESTIGATE_SEARCH)


func _enter_combat(t: Tactic) -> void:
	_drop_loot_claim()
	state = State.COMBAT
	_set_tactic(t)


func _set_tactic(t: Tactic) -> void:
	tactic = t
	_tactic_t = 0.0
	match t:
		Tactic.FLANK:
			# заходим сбоку: точка на AI_FLANK_OFFSET в сторону от линии «мы — цель»
			var to := last_known - global_position
			to.y = 0.0
			var side := Vector3(to.z, 0.0, -to.x).normalized() * (1.0 if _rng.randf() < 0.5 else -1.0)
			_agent.target_position = _snap(last_known + side * Balance.AI_FLANK_OFFSET - to.normalized() * 4.0)
			say("Обхожу!")
		Tactic.PUSH:
			_agent.target_position = _spread_point(last_known)
		Tactic.ADVANCE:
			if not _try_advance():
				tactic = Tactic.PUSH
				_agent.target_position = _spread_point(last_known)
		Tactic.ENGAGE:
			_agent.target_position = global_position
		_:
			pass


func _combat(delta: float) -> void:
	_tactic_t += delta
	var dist := global_position.distance_to(last_known)
	var rng_m := float(_spec.range)
	var want_cover := _hurt_t > 0.0 or _suppress_t > 0.0 or (_mag == 0 and _reload_t > 0.0)
	match tactic:
		Tactic.ENGAGE:
			_set_crouch(false)
			_face(last_known)
			if _seen_now and dist <= rng_m:
				_agent.target_position = global_position
				_try_fire()
				if want_cover and _tactic_t > 0.4 and _try_cover(Balance.AI_COVER_RADIUS, false):
					return
			elif _seen_now and not _holds():
				# далеко — подходим на дальность своего оружия (дробовик — вплотную)
				_agent.target_position = _snap(last_known)
			elif _unseen_t < 1.5 and _mag > 0:
				# только что ушёл из виду — подавляющий огонь туда, где был
				_try_fire(true)
			else:
				_set_tactic(Tactic.FLANK if _rank() == 1 and _mates_near(30.0) > 0 else _closing_tactic())
		Tactic.COVER_MOVE:
			_set_crouch(false)
			if _agent.is_navigation_finished() or global_position.distance_to(_cover_pos) < 0.9:
				_set_tactic(Tactic.COVER_HIDE)
				_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_HIDE[0]), float(Balance.AI_COVER_HIDE[1]))
			elif _seen_now and dist <= rng_m and _tactic_t > 0.6:
				_try_fire()
		Tactic.COVER_HIDE:
			_set_crouch(true)
			_face(last_known)
			if _reload_t <= 0.0 and _mag == 0:
				_start_reload()
			if _tactic_t >= 0.0 and _reload_t <= 0.0:
				_peeks += 1
				_set_tactic(Tactic.COVER_PEEK)
				_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_PEEK[0]), float(Balance.AI_COVER_PEEK[1]))
		Tactic.COVER_PEEK:
			# выглянул (встал): стреляет, если видит; потом снова вниз
			_set_crouch(false)
			_face(last_known)
			if _seen_now and dist <= rng_m:
				_try_fire()
			if _tactic_t >= 0.0:
				if not _cover_still_good() or _peeks >= 4 or (not _seen_now and _unseen_t > 3.0):
					_peeks = 0
					_set_tactic(Tactic.ENGAGE if _seen_now else _closing_tactic())
				else:
					_set_tactic(Tactic.COVER_HIDE)
					_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_HIDE[0]), float(Balance.AI_COVER_HIDE[1]))
		Tactic.ADVANCE:
			# перебежка не нашлась (иначе была бы COVER_MOVE) — идём как PUSH
			_set_tactic(Tactic.PUSH)
		Tactic.FLANK, Tactic.PUSH:
			_set_crouch(false)
			if _seen_now:
				_set_tactic(Tactic.ENGAGE)
			elif _agent.is_navigation_finished():
				if tactic == Tactic.FLANK:
					_set_tactic(Tactic.PUSH)
				else:
					# дошли, а там пусто — осматриваемся, дальше поиск по памяти
					_facing += delta * 1.5
			elif _mag < int(_spec.mag) / 3 and _reload_t <= 0.0:
				_start_reload()


## Цель не видно: далеко — перебежками по укрытиям, близко — прямо (каждый в свою точку).
func _closing_tactic() -> Tactic:
	if _holds():
		return Tactic.ENGAGE
	return Tactic.ADVANCE if global_position.distance_to(last_known) > Balance.AI_ADVANCE_MIN_DIST else Tactic.PUSH


## Перебежка: точка на AI_ADVANCE_STEP ближе к цели, лучше — закрытая от неё стеной; дошёл —
## присел, выглянул, дальше. false — некуда (тогда PUSH).
func _try_advance() -> bool:
	var to := last_known - global_position
	to.y = 0.0
	var dist := to.length()
	if dist < Balance.AI_ADVANCE_MIN_DIST:
		return false
	var dir := to / dist
	var threat := last_known + Vector3.UP * 1.3
	var space := get_world_3d().direct_space_state
	var own_y := _snap(global_position).y
	var map := get_world_3d().navigation_map
	var best := Vector3.INF
	var best_s := INF
	for i in range(18):
		var ang := _rng.randf_range(-0.9, 0.9)
		var step := _rng.randf_range(float(Balance.AI_ADVANCE_STEP[0]), float(Balance.AI_ADVANCE_STEP[1]))
		var cand := _snap(global_position + dir.rotated(Vector3.UP, ang) * step)
		if absf(cand.y - own_y) > 0.3 or cand.distance_to(global_position) < 3.0:
			continue
		var nd := cand.distance_to(last_known)
		if nd > dist - 2.5 or _claimed_near(cand, Balance.AI_SPREAD_CLAIM_M):
			continue
		var q := PhysicsRayQueryParameters3D.create(threat, cand + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
		var hidden := not space.intersect_ray(q).is_empty()
		var score := nd + (0.0 if hidden else 7.0) + absf(ang) * 3.0
		if score >= best_s:
			continue
		# и дойти туда можно без обхода через полкарты
		var path := NavigationServer3D.map_get_path(map, global_position, cand, true)
		var plen := 0.0
		for k in range(1, path.size()):
			plen += path[k - 1].distance_to(path[k])
		if path.size() < 2 or plen > cand.distance_to(global_position) * 1.6 + 3.0:
			continue
		best = cand
		best_s = score
	if best == Vector3.INF:
		return false
	_cover_pos = best
	_agent.target_position = best
	# дошёл — одно «присел-выглянул» и дальше
	_peeks = 3
	memory_timer = maxf(memory_timer, _mem() * 0.6)
	tactic = Tactic.COVER_MOVE
	_tactic_t = 0.0
	if _rng.randf() < 0.35:
		say("Двигаюсь!")
	return true


func _start_search(points: int = Balance.AI_SEARCH_POINTS) -> void:
	state = State.SEARCH
	_set_crouch(false)
	_search_left = points
	_search_total = points
	# прочёсывание дугой — от той стороны, откуда пришли, каждый в свою сторону
	_search_ang = atan2(global_position.z - last_known.z, global_position.x - last_known.x) + (0.8 if hash(name) % 2 == 0 else -0.8)
	_agent.target_position = global_position if _holds() else _spread_point(last_known)
	linger_timer = 1.5
	say("Ушёл…" if points == Balance.AI_SEARCH_POINTS else "Проверю тут…")


## Поиск: к последней точке, потом прочёсывание вокруг — от ближних мест к дальним, дугой,
## в стороне от тех, кого уже смотрят другие; на каждой — постоять, осмотреться.
func _search(delta: float) -> void:
	if _reload_t <= 0.0 and _mag < int(_spec.mag):
		_start_reload()
	if not _agent.is_navigation_finished():
		return
	linger_timer -= delta
	_facing += delta * 1.4
	if linger_timer > 0.0:
		return
	if _search_left <= 0:
		state = State.PATROL
		pause_timer = 1.0
		return
	_search_left -= 1
	if _holds():
		# ищет глазами с места
		linger_timer = _rng.randf_range(2.0, 3.5)
		return
	var done := float(_search_total - _search_left) / float(maxi(_search_total, 1))
	var r := lerpf(4.0, Balance.AI_SEARCH_RADIUS, done)
	var sweep := 1.1 if hash(name) % 2 == 0 else -1.1
	var target := last_known
	for attempt in range(8):
		var a := _search_ang + _rng.randf_range(-0.35, 0.35)
		_search_ang += sweep
		var p := _snap(last_known + Vector3(cos(a), 0.0, sin(a)) * r * _rng.randf_range(0.8, 1.1))
		if p.distance_to(global_position) > 2.0 and not _claimed_near(p, Balance.AI_SEARCH_CLAIM_M):
			target = p
			break
	_agent.target_position = target
	linger_timer = _rng.randf_range(1.2, 2.4)


func _start_retreat() -> void:
	state = State.RETREAT
	say("Отхожу!")
	if not _try_cover(Balance.AI_COVER_RADIUS * 1.8, true):
		# укрытия нет — просто прочь от угрозы
		var away := global_position - last_known
		away.y = 0.0
		_agent.target_position = _snap(global_position + away.normalized() * 12.0)
	linger_timer = _rng.randf_range(float(Balance.AI_RETREAT_HOLD[0]), float(Balance.AI_RETREAT_HOLD[1]))


func _retreat(delta: float) -> void:
	if not _agent.is_navigation_finished():
		_set_crouch(false)
		return
	_set_crouch(true)
	_face(last_known)
	if _reload_t <= 0.0 and _mag < int(_spec.mag):
		_start_reload()
	# отсиделся — или стреляет по тому, кто пришёл, или снова ищет
	if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
		_try_fire()
	linger_timer -= delta
	if linger_timer <= 0.0:
		_start_search()


# ---------------------------------------------------------------- тяжело ранен, спасение

## Лёг раненым (хост): пистолет вместо основного, зовёт; поднялся — обратно в бой.
func _on_downed_changed(on: bool) -> void:
	if on:
		_release_rescue()
		state = State.DOWNED
		crouched = false
		_apply_shape()
		_main_spec = _spec
		_main_mag = _mag
		_spec = Balance.AI_WEAPONS.pistol
		_mag = int(_spec.mag)
		_reload_t = 0.0
		_burst_left = 0
		_agent.target_position = global_position
		say("Меня зацепило!")
		NoiseBus.emit(global_position, Balance.AI_RESCUE_RADIUS, "death")
		_help_t = 0.0
		_call_for_help()
	else:
		rescuer = null
		dragged_by = null
		if not _main_spec.is_empty():
			_spec = _main_spec
			_mag = _main_mag
			_main_spec = {}
		_apply_shape()
		say("Живой!")
		memory_timer = maxf(memory_timer, _mem())
		_enter_combat(Tactic.ENGAGE)
		_try_cover(Balance.AI_COVER_RADIUS, false)


## Раненый зовёт: ближайший живой товарищ, который слышит (свой отряд — в первую очередь), идёт спасать.
func _call_for_help() -> void:
	var best: Marauder = null
	var best_s := INF
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.state in [State.DEAD, State.DOWNED, State.RESCUE, State.RETREAT]:
			continue
		var d := m.global_position.distance_to(global_position)
		if d > Balance.AI_RESCUE_RADIUS:
			continue
		var s := d * (1.0 if m.squad == squad else 1.8)
		if s < best_s:
			best = m
			best_s = s
	if best:
		best.start_rescue(self)


func start_rescue(who: Marauder) -> void:
	who.rescuer = self
	_rescue_target = who
	_rescue_phase = 0
	_rescue_t = 0.0
	state = State.RESCUE
	crouched = false
	_apply_shape()
	_agent.target_position = _snap(who.global_position)
	say("Держись, иду!")


## Бросить спасение (сам ранен / умер / тот умер): раненого — отпустить.
func _release_rescue() -> void:
	var t := _rescue_target
	_rescue_target = null
	if t and is_instance_valid(t):
		if t.rescuer == self:
			t.rescuer = null
		if t.dragged_by == self:
			t.dragged_by = null


## Лежит: отстреливается из пистолета, ждёт помощи; никто не идёт — зовёт снова.
func _downed(delta: float) -> void:
	_face(last_known)
	if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
		_try_fire()
	if rescuer == null or not is_instance_valid(rescuer) or rescuer.state != State.RESCUE:
		rescuer = null
		_help_t += delta
		if _help_t >= 4.0:
			_help_t = 0.0
			_call_for_help()


## Раненого тащат — тело на «верёвке» за тем, кто тащит; иначе лежит на месте.
func _move_downed(delta: float) -> void:
	velocity = Vector3.ZERO
	if dragged_by and is_instance_valid(dragged_by) and dragged_by.state == State.RESCUE:
		var off := global_position - dragged_by.global_position
		off.y = 0.0
		if off.length() < 0.05:
			off = -Vector3(sin(dragged_by._facing), 0.0, cos(dragged_by._facing))
		var goal := dragged_by.global_position + off.normalized() * Balance.DRAG_DIST
		var pull := (goal - global_position) / maxf(delta, 0.001)
		velocity.x = clampf(pull.x, -6.0, 6.0)
		velocity.z = clampf(pull.z, -6.0, 6.0)
	if not is_on_floor():
		velocity.y -= 9.8
	move_and_slide()
	_body.rotation.y = _facing
	# лежит лицом вниз (Body:rotation синхронизируется)
	_body.rotation.x = 1.35


## Спасатель: добежать, лежит на виду — утащить за укрытие, поднять.
func _rescue(delta: float) -> void:
	var t := _rescue_target
	if t == null or not is_instance_valid(t) or t.state != State.DOWNED:
		_end_rescue()
		return
	var d := global_position.distance_to(t.global_position)
	match _rescue_phase:
		0:
			_set_crouch(false)
			if _repath_t <= 0.0:
				_repath_t = 0.5
				_agent.target_position = _snap(t.global_position)
			# по пути отвечает огнём, если видит
			if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
				_try_fire()
			if d <= 1.4:
				last_known = t.last_known
				var threat := t.last_known + Vector3.UP * 1.3
				var q := PhysicsRayQueryParameters3D.create(threat, t.global_position + Vector3.UP * 0.5, Hitscan.LAYER_WORLD)
				var exposed := get_world_3d().direct_space_state.intersect_ray(q).is_empty()
				var cover := _cover_point(Balance.AI_DRAG_COVER_M, false) if exposed else Vector3.INF
				if cover != Vector3.INF:
					_rescue_phase = 1
					t.dragged_by = self
					_agent.target_position = cover
					say("Тащу! Прикрой!")
				else:
					_rescue_phase = 2
					_rescue_t = 0.0
		1:
			if _agent.is_navigation_finished() or d > 3.0:
				t.dragged_by = null
				_rescue_phase = 2
				_rescue_t = 0.0
		2:
			_agent.target_position = global_position
			_set_crouch(true)
			_face(t.global_position)
			_rescue_t += delta
			if _rescue_t >= Balance.AI_REVIVE_SEC:
				t._health.revive(Balance.REVIVE_HP)
				_end_rescue()


func _end_rescue() -> void:
	_release_rescue()
	if state != State.RESCUE:
		return
	_set_crouch(false)
	if memory_timer > 0.0:
		_enter_combat(_closing_tactic())
	else:
		state = State.PATROL
		pause_timer = 1.0


# ---------------------------------------------------------------- укрытие

## Ищет рядом место, которое стена закрывает от угрозы (last_known), и идёт туда.
## far — отход: чем дальше от угрозы, тем лучше.
func _try_cover(radius: float, far: bool) -> bool:
	var best := _cover_point(radius, far)
	if best == Vector3.INF:
		return false
	_cover_pos = best
	_agent.target_position = best
	if state == State.COMBAT:
		_set_tactic(Tactic.COVER_MOVE)
	return true


## Точка укрытия от last_known в радиусе (Vector3.INF — нет): стена закрывает присевшего,
## дойти можно без большого обхода.
func _cover_point(radius: float, far: bool) -> Vector3:
	var threat := last_known + Vector3.UP * 1.3
	var space := get_world_3d().direct_space_state
	var cands: Array = []
	# высота навмеша под собой — он лежит чуть выше пола
	var own_y := _snap(global_position).y
	for ring in [0.35, 0.65, 1.0]:
		for i in range(12):
			var a := TAU * float(i) / 12.0 + _rng.randf() * 0.3
			var cand := _snap(global_position + Vector3(cos(a), 0.0, sin(a)) * radius * float(ring))
			# на уровне своего пола (не на лавке и не на ящике)
			if cand.distance_to(global_position) < 1.0 or absf(cand.y - own_y) > 0.3:
				continue
			# присевший за этой точкой не виден с угрозы
			var q := PhysicsRayQueryParameters3D.create(threat, cand + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
			if space.intersect_ray(q).is_empty():
				continue
			var travel := cand.distance_to(global_position)
			var to_threat := cand.distance_to(last_known)
			var score := travel - (to_threat * 0.8 if far else 0.0)
			# не лезть ближе к угрозе (кроме дробовика — ему вблизи и надо)
			if not far and weapon != "shotgun" and to_threat < global_position.distance_to(last_known) - 3.0:
				score += 6.0
			cands.append([score, cand, travel])
	cands.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
	# идти до укрытия — не в обход через полкарты: путь не длиннее полутора прямых + 4 м
	var map := get_world_3d().navigation_map
	var best := Vector3.INF
	for c in cands.slice(0, 6):
		var path := NavigationServer3D.map_get_path(map, global_position, c[1], true)
		var plen := 0.0
		for k in range(1, path.size()):
			plen += path[k - 1].distance_to(path[k])
		if path.size() >= 2 and plen <= float(c[2]) * 1.5 + 4.0:
			best = c[1]
			break
	return best


## Укрытие всё ещё закрывает от того места, где цель сейчас (по памяти)?
func _cover_still_good() -> bool:
	var q := PhysicsRayQueryParameters3D.create(last_known + Vector3.UP * 1.3, global_position + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
	return not get_world_3d().direct_space_state.intersect_ray(q).is_empty()


func _set_crouch(on: bool) -> void:
	if crouched == on:
		return
	crouched = on
	_apply_shape()


## Фигура и коллизия по позе: стоит, присел, лежит раненым.
func _apply_shape() -> void:
	_body.scale = _base_scale * Vector3(1.0, 0.68 if crouched else 1.0, 1.0)
	_capsule.height = 0.8 if _health.downed else (1.25 if crouched else 1.8)
	($Capsule as CollisionShape3D).position.y = _capsule.height * 0.5


func _face(p: Vector3) -> void:
	_facing = atan2(p.x - global_position.x, p.z - global_position.z)


# ---------------------------------------------------------------- стрельба

func _tick_weapon(delta: float) -> void:
	_shot_t -= delta
	if _reload_t > 0.0:
		_reload_t -= delta
		if _reload_t <= 0.0:
			_mag = int(_spec.mag)


func _start_reload() -> void:
	if _reload_t > 0.0 or _mag >= int(_spec.mag):
		return
	_reload_t = float(_spec.reload)
	_burst_left = 0
	Audio.play("reload_" + ("pistol" if weapon == "pistol" else weapon), global_position)
	if state == State.COMBAT:
		say("Перезаряжаюсь!")


## Выстрел, если готов: очередь, пауза между очередями, магазин. suppress — по памяти, реже и хуже.
func _try_fire(suppress: bool = false) -> void:
	if _reload_t > 0.0:
		return
	if _mag <= 0:
		_start_reload()
		return
	if _target_player and is_instance_valid(_target_player) and _target_player.is_downed() and not _may_finish(_target_player):
		# лежащего не добивает, пока стреляет кто-то другой
		return
	if not _line_of_fire():
		# между стволом и целью стена — стрелять некуда (ни прицельно, ни «на подавление»)
		return
	if _shot_t > 0.0:
		return
	_shoot(suppress)
	_mag -= 1
	if _burst_left <= 0:
		_burst_left = int(_spec.burst)
	_burst_left -= 1
	if _burst_left > 0:
		_shot_t = float(_spec.interval)
	else:
		_shot_t = float(_spec.interval) + float(_spec.burst_pause) + (0.6 if suppress else 0.0)


## Ствол → точка цели (по памяти) не упирается в стену / дверь раньше, чем за метр до неё.
func _line_of_fire() -> bool:
	var from := _gun_pos()
	var target := last_known + Vector3.UP * 1.1
	var q := PhysicsRayQueryParameters3D.create(from, target, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [get_rid()])
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	return hit.is_empty() or from.distance_to(hit.position) > from.distance_to(target) - 1.0


## Откуда стреляет: стоя, присев, лёжа.
func _gun_pos() -> Vector3:
	return global_position + Vector3.UP * (0.35 if _health.downed else (1.0 if crouched else 1.4))


func _shoot(suppress: bool) -> void:
	var from := _gun_pos()
	var h := 1.1
	if _target_player and is_instance_valid(_target_player):
		h = float(Perception.TARGET_HEIGHT[Perception.stance_key(_target_player)])
	var target := last_known + Vector3.UP * h
	var spread := float(_spec.spread) * _aim
	if _target_player and is_instance_valid(_target_player) and _target_player.velocity.length() > 2.0:
		spread *= Balance.AI_TARGET_MOVING
	if Vector2(velocity.x, velocity.z).length() > 0.5:
		spread *= Balance.AI_SELF_MOVING
	if suppress:
		spread *= 2.0
	if _stagger_t > 0.0:
		spread *= Balance.AI_HIT_STAGGER_SPREAD
	if _health.downed:
		spread *= Balance.DOWN_SPREAD
	var exclude: Array[RID] = [get_rid()]
	var dir := (target - from).normalized()
	for i in range(int(_spec.pellets)):
		var hit := Hitscan.fire(get_world_3d(), from, dir, spread, float(_spec.range) * 1.5,
			Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_PLAYER, float(_spec.damage), exclude, _rng)
		if i == 0 or i % 3 == 0:
			Tracer.spawn(get_tree().current_scene, from, hit.get("position", hit.get("end", from)), Color(1.0, 0.6, 0.35))
	_muzzle.visible = true
	get_tree().create_timer(0.06).timeout.connect(func() -> void: _muzzle.visible = false)
	# свои выстрелы товарищи слышат как «бой» — не как свист пуль у себя
	NoiseBus.emit(global_position, float(_spec.noise_m), "shot_ai")
	Audio.play(String(_spec.sound), from)


# ---------------------------------------------------------------- реплики

## Реплика над головой («Контакт!», «Перезаряжаюсь!») — видна всем игрокам.
func say(text: String) -> void:
	if Net.is_networked():
		_say_rpc.rpc(text)
	else:
		_show_say(text)


@rpc("authority", "call_local", "unreliable")
func _say_rpc(text: String) -> void:
	_show_say(text)


func _show_say(text: String) -> void:
	if _say_label == null:
		_say_label = Label3D.new()
		_say_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_say_label.pixel_size = 0.006
		_say_label.font_size = 48
		_say_label.outline_size = 12
		_say_label.modulate = Color(1.0, 0.85, 0.6)
		_say_label.no_depth_test = true
		_say_label.position = Vector3(0, 2.25, 0)
		add_child(_say_label)
	_say_label.text = text
	_say_label.visible = true
	var shown := text
	get_tree().create_timer(1.6).timeout.connect(func() -> void:
		if is_instance_valid(_say_label) and _say_label.text == shown:
			_say_label.visible = false)


# ---------------------------------------------------------------- движение

func _move(delta: float) -> void:
	if state == State.DOWNED:
		_move_downed(delta)
		return
	var speed := Balance.MARAUDER_WALK if state == State.PATROL else Balance.MARAUDER_RUN
	if state == State.RESCUE:
		speed = Balance.AI_DRAG_SPEED if _rescue_phase == 1 else (Balance.MARAUDER_RUN if _rescue_phase == 0 else 0.0)
	if state == State.SEARCH or state == State.INVESTIGATE:
		speed = lerpf(Balance.MARAUDER_WALK, Balance.MARAUDER_RUN, 0.55)
	if crouched:
		speed = Balance.MARAUDER_WALK * 0.7
	speed *= float(_arch.get("speed", 1.0))
	if _stagger_t > 0.0:
		speed *= Balance.AI_HIT_STAGGER_SPEED
	var wish := Vector3.ZERO
	if _nav_ready and not _agent.is_navigation_finished():
		var next := _agent.get_next_path_position()
		var to := next - global_position
		to.y = 0.0
		if to.length() > 0.05:
			wish = to.normalized() * speed
			# в бою смотрит на цель, а не под ноги
			if state != State.COMBAT or not _seen_now:
				_facing = lerp_angle(_facing, atan2(to.x, to.z), minf(1.0, 8.0 * delta))
	velocity.x = move_toward(velocity.x, wish.x, 14.0 * delta)
	velocity.z = move_toward(velocity.z, wish.z, 14.0 * delta)
	if not is_on_floor():
		velocity.y -= 9.8 * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	_body.rotation.y = _facing
	# попадание откидывает корпус назад (Body:rotation синхронизируется — видно всем)
	_body.rotation.x = -0.35 * _flinch
	# шаги (их слышно — так мародёра можно засечь раньше, чем он тебя) — Footsteps


## Вспышка на теле при попадании — видно, что пуля дошла.
func hit_flash() -> void:
	var overlay := StandardMaterial3D.new()
	overlay.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	overlay.albedo_color = Color(1.0, 0.25, 0.2, 0.55)
	overlay.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	for child in _body.get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).material_overlay = overlay
	get_tree().create_timer(0.09).timeout.connect(func() -> void:
		for child in _body.get_children():
			if child is MeshInstance3D:
				(child as MeshInstance3D).material_overlay = null)


func _snap(p: Vector3) -> Vector3:
	var map := get_world_3d().navigation_map
	return NavigationServer3D.map_get_closest_point(map, p)


func _on_died() -> void:
	_release_rescue()
	_drop_loot_claim()
	if rescuer and is_instance_valid(rescuer):
		rescuer._rescue_target = null
	state = State.DEAD
	_set_crouch(false)
	# падение тела слышат соседи — придут смотреть
	NoiseBus.emit(global_position, Balance.AI_DEATH_NOISE, "death")
	# задание «убить N» — тому, чья пуля добила
	if Raid.current:
		Raid.current.credit_kill(_health.last_attacker)
	# хост: тело можно обыскать (содержимое — по таблице «marauder»)
	if Raid.current:
		var rng := RandomNumberGenerator.new()
		rng.randomize()
		# ящик вываливается из трупа в сторону стрелявшего (там точно свободно — его было видно)
		var to_shooter := _last_hit_from - global_position
		to_shooter.y = 0.0
		to_shooter = to_shooter.normalized() if to_shooter.length() > 0.01 else Vector3(sin(_facing), 0.0, cos(_facing))
		var rest := global_position + to_shooter * Balance.CRATE_TOSS_DIST
		# его ствол и патроны: что осталось в магазине и немного запаса
		# лёжа стрелял из пистолета — выпадает основное оружие и патроны к нему
		var wspec: Dictionary = Balance.AI_WEAPONS[weapon]
		var in_mag := _main_mag if not _main_spec.is_empty() else _mag
		var drop := ItemDb.roll("marauder", rng)
		drop.push_front(ItemDb.make(String(wspec.item), 1))
		var rounds := mini(in_mag + rng.randi_range(0, int(wspec.mag)), ItemDb.stack(String(wspec.ammo)))
		if rounds > 0:
			drop.append(ItemDb.make(String(wspec.ammo), rounds))
		# награбленное — тоже здесь
		drop.append_array(pack)
		pack = []
		Raid.current.spawn_drop(rest, "Ящик мародёра", drop, LootContainer.Look.CRATE,
			global_position + Vector3.UP * 1.1 - rest)
	collision_layer = 0
	collision_mask = 0
	set_physics_process(false)
	_spawn_ragdoll()


## У клиентов сигнала died нет (урон считает хост) — смерть видна по синхронизированному alive.
func _process(_delta: float) -> void:
	# раненый (видно у всех по синхронизированному downed): основное оружие убрано
	if _health.downed != _shown_down:
		_shown_down = _health.downed
		if _main_gun:
			_main_gun.visible = not _shown_down
		# у клиентов пули ищут тело своей физикой — коллизия лежащего тоже низкая
		_apply_shape()
	if not _health.alive and _ragdoll == null:
		collision_layer = 0
		collision_mask = 0
		_spawn_ragdoll()


## Капсула прячется, падает регдолл, толкнутый от стрелявшего — сильнее от мощного попадания.
func _spawn_ragdoll() -> void:
	if _ragdoll != null:
		return
	var mat := (_body.get_node("Torso") as MeshInstance3D).get_surface_override_material(0)
	var away := global_position - _last_hit_from
	away.y = 0.0
	away = away.normalized() if away.length() > 0.01 else -Vector3(sin(_facing), 0.0, cos(_facing))
	var push: Dictionary = Balance.RAGDOLL_DEATH_PUSH
	var imp := away * (float(push.base) + float(push.per_damage) * _last_damage)
	var xf := Transform3D(Basis(Vector3.UP, _body.rotation.y), global_position)
	_ragdoll = Ragdoll.spawn(get_tree().current_scene, xf, velocity, imp, global_position + Vector3.UP * 1.25, mat, mat)
	velocity = Vector3.ZERO
	_body.visible = false
	if _say_label:
		_say_label.visible = false
	Audio.play("death", global_position + Vector3.UP * 1.5)
	Audio.play("fall", global_position, -4.0)
