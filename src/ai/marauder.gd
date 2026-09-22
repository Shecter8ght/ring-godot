class_name Marauder
extends CharacterBody3D
## Мародёр: патруль по помещениям → расследование шума → бой, если видит.
## Позицию игрока получает только через Perception.can_see (зрение) и NoiseBus (слух) —
## никакого прямого чтения. Ходит по навмешу сектора, двери открывает сам (см. door.gd).

enum State { PATROL, INVESTIGATE, COMBAT, DEAD }

const EYE_HEIGHT := 1.6

var state: State = State.PATROL
## Откуда брать точки патруля: Callable() -> Vector3 (даёт сцена сектора).
var patrol_point_provider: Callable
var last_known: Vector3 = Vector3.ZERO
var memory_timer: float = 0.0
var notice_timer: float = 0.0
var pause_timer: float = 0.0
var linger_timer: float = 0.0
var fire_timer: float = 0.0
var _rng := RandomNumberGenerator.new()
var _target_player: Player = null
var _facing: float = 0.0
var _nav_ready: bool = false
var _step_timer: float = 0.0
var _ragdoll: Ragdoll
var _last_hit_from: Vector3 = Vector3.ZERO
var _last_damage: float = 0.0

@onready var _agent: NavigationAgent3D = $NavigationAgent3D
@onready var _health: Health = $Health
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle


func _ready() -> void:
	add_to_group("marauders")
	_rng.seed = hash(name) + int(global_position.x * 13.0)
	_health.max_hp = Balance.MARAUDER_HP
	_health.hp = _health.max_hp
	_health.died.connect(_on_died)
	_health.damaged.connect(_on_damaged)
	NoiseBus.noise.connect(_on_noise)
	_agent.path_desired_distance = 0.6
	_agent.target_desired_distance = 0.8
	_agent.radius = 0.4
	_muzzle.visible = false
	# пистолет в правой руке — видно, чем вооружён; при смерти прячется вместе с телом
	var gun := WeaponModels.build("pistol")
	gun.position = Vector3(-0.17, 1.24, 0.3)
	_body.add_child(gun)
	pause_timer = _rng.randf_range(0.5, 2.0)
	# Навмеш печётся после загрузки сектора — пока его нет, стоим.
	NavigationServer3D.map_changed.connect(func(_m: RID) -> void: _nav_ready = true)
	if Net.is_networked():
		_setup_sync()


## Мародёр целиком авторитет хоста (умалчиваемый multiplayer authority узла — 1). AI и движение
## считает только хост; остальные peer просто получают позицию/позу синхронизатором.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", "Body:position", ".:state"]:
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
	_perceive(delta)
	match state:
		State.PATROL:
			_patrol(delta)
		State.INVESTIGATE:
			_investigate(delta)
		State.COMBAT:
			_combat(delta)
	_move(delta)


# ---------------------------------------------------------------- восприятие

func _perceive(delta: float) -> void:
	var seen: Player = null
	var eye := global_position + Vector3.UP * EYE_HEIGHT
	var fwd := Vector3(sin(_facing), 0.0, cos(_facing))
	var exclude: Array[RID] = [get_rid()]
	for p in get_tree().get_nodes_in_group("players"):
		var player := p as Player
		if player == null or not player.is_alive():
			continue
		if Perception.can_see(get_world_3d(), eye, fwd, player, exclude):
			seen = player
			break
	if seen:
		# Заметить — не мгновенно: чем ближе, тем быстрее.
		var dist := global_position.distance_to(seen.global_position)
		notice_timer += delta * clampf(30.0 / maxf(dist, 1.0), 1.0, 6.0)
		if notice_timer >= Balance.AI_NOTICE_SEC or state == State.COMBAT:
			_target_player = seen
			last_known = seen.global_position
			memory_timer = Balance.AI_MEMORY_SEC
			if state != State.COMBAT:
				state = State.COMBAT
	else:
		notice_timer = maxf(0.0, notice_timer - delta)
		if state == State.COMBAT:
			memory_timer -= delta
			if memory_timer <= 0.0:
				state = State.INVESTIGATE
				linger_timer = Balance.AI_INVESTIGATE_LINGER
				_agent.target_position = _snap(last_known)


func _on_noise(pos: Vector3, radius_m: float, _kind: String) -> void:
	if state == State.DEAD or state == State.COMBAT:
		return
	if global_position.distance_to(pos) > radius_m:
		return
	last_known = pos
	state = State.INVESTIGATE
	linger_timer = Balance.AI_INVESTIGATE_LINGER
	_agent.target_position = _snap(pos)


func _on_damaged(amount: float, from: Vector3) -> void:
	_last_hit_from = from
	_last_damage = amount
	if state == State.DEAD:
		return
	# Попадание — улика: разворот в сторону выстрела, бежим смотреть.
	last_known = from
	if state != State.COMBAT:
		state = State.INVESTIGATE
		linger_timer = Balance.AI_INVESTIGATE_LINGER
		_agent.target_position = _snap(from)
	_facing = atan2(from.x - global_position.x, from.z - global_position.z)


# ---------------------------------------------------------------- состояния

func _patrol(delta: float) -> void:
	if not _nav_ready:
		return
	if _agent.is_navigation_finished():
		pause_timer -= delta
		if pause_timer <= 0.0 and patrol_point_provider.is_valid():
			_agent.target_position = _snap(patrol_point_provider.call())
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1]))


func _investigate(delta: float) -> void:
	if _agent.is_navigation_finished():
		linger_timer -= delta
		# осматриваемся
		_facing += delta * 1.2
		if linger_timer <= 0.0:
			state = State.PATROL
			pause_timer = 0.5


func _combat(delta: float) -> void:
	fire_timer -= delta
	var dist := global_position.distance_to(last_known)
	_facing = atan2(last_known.x - global_position.x, last_known.z - global_position.z)
	var sees_now := _target_player != null and memory_timer >= Balance.AI_MEMORY_SEC - 0.05
	if sees_now and dist <= Balance.AI_ENGAGE_RANGE:
		# стоим и стреляем
		_agent.target_position = global_position
		if fire_timer <= 0.0:
			_shoot()
			fire_timer = Balance.AI_FIRE_INTERVAL
	else:
		# идём к последней известной точке
		_agent.target_position = _snap(last_known)


func _shoot() -> void:
	var from := global_position + Vector3.UP * 1.4
	var target := last_known + Vector3.UP * float(Perception.TARGET_HEIGHT[Perception.stance_key(_target_player)])
	var exclude: Array[RID] = [get_rid()]
	var hit := Hitscan.fire(get_world_3d(), from, (target - from).normalized(), Balance.AI_SPREAD_DEG, Balance.AI_ENGAGE_RANGE * 1.5,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_PLAYER, Balance.AI_DAMAGE, exclude, _rng)
	Tracer.spawn(get_tree().current_scene, from, hit.get("position", hit.get("end", from)), Color(1.0, 0.6, 0.35))
	_muzzle.visible = true
	get_tree().create_timer(0.06).timeout.connect(func() -> void: _muzzle.visible = false)
	NoiseBus.emit(global_position, float(Balance.PISTOL.noise_m), "shot")
	Audio.play("shot_ai", from)


# ---------------------------------------------------------------- движение

func _move(delta: float) -> void:
	var speed := Balance.MARAUDER_WALK if state == State.PATROL else Balance.MARAUDER_RUN
	var wish := Vector3.ZERO
	if _nav_ready and not _agent.is_navigation_finished():
		var next := _agent.get_next_path_position()
		var to := next - global_position
		to.y = 0.0
		if to.length() > 0.05:
			wish = to.normalized() * speed
			if state != State.COMBAT:
				_facing = lerp_angle(_facing, atan2(to.x, to.z), minf(1.0, 8.0 * delta))
	velocity.x = move_toward(velocity.x, wish.x, 14.0 * delta)
	velocity.z = move_toward(velocity.z, wish.z, 14.0 * delta)
	if not is_on_floor():
		velocity.y -= 9.8 * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	_body.rotation.y = _facing
	# Шаги мародёра слышны игроку — так его можно засечь до того, как он тебя увидит.
	if Vector2(velocity.x, velocity.z).length() > 0.3:
		_step_timer -= delta
		if _step_timer <= 0.0:
			_step_timer = 0.55 if state == State.PATROL else 0.36
			Audio.play("step_ai", global_position)


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
	state = State.DEAD
	collision_layer = 0
	collision_mask = 0
	set_physics_process(false)
	_spawn_ragdoll()


## У клиентов сигнала died нет (урон считает хост) — смерть видна по синхронизированному alive.
func _process(_delta: float) -> void:
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
	var imp := (away + Vector3.UP * 0.25) * (float(push.base) + float(push.per_damage) * _last_damage)
	var xf := Transform3D(Basis(Vector3.UP, _body.rotation.y), global_position)
	_ragdoll = Ragdoll.spawn(get_tree().current_scene, xf, velocity, imp, global_position + Vector3.UP * 1.25, mat, mat)
	velocity = Vector3.ZERO
	_body.visible = false
	Audio.play("death", global_position + Vector3.UP * 1.5)
	Audio.play("fall", global_position, -4.0)
