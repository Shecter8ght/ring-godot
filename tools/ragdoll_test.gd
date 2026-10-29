extends Node
## Трупы на модели (SkinRagdoll) не рвутся (владелец 2026-10-29: «трупы бойцов шакалит» — тела растягивались нитями
## на метры). Рейд «Проспекта», шесть ботов: обычная смерть, сильный удар в голову, добили лежачего (дважды — поза
## лёжа уводила руки под пол), у стены, огромный толчок. Потом пули по телам и разбор ящиков. Растяжение — длина
## каждой кости к её длине в rest (запись модификатором после регдолла), разлёт — самые дальние физкости тела.

## Растяжение кости не больше, разлёт физкостей — не больше, м (тело лежит в рост ~1,8 м)
const STRETCH_MAX := 1.35
const SPREAD_MAX := 2.3


## Поза после всех модификаторов (и регдолла): самое сильное растяжение кости за окно.
class PoseTap extends SkeletonModifier3D:
	var worst: float = 0.0
	var worst_bone: String = ""

	func _process_modification() -> void:
		var sk := get_skeleton()
		for b: int in range(sk.get_bone_count()):
			var p: int = sk.get_bone_parent(b)
			if p < 0:
				continue
			var rest: float = sk.get_bone_global_rest(b).origin.distance_to(sk.get_bone_global_rest(p).origin)
			if rest < 0.03:
				continue
			var k: float = sk.get_bone_global_pose(b).origin.distance_to(sk.get_bone_global_pose(p).origin) / rest
			if k > worst:
				worst = k
				worst_bone = sk.get_bone_name(b)


var _fails: int = 0
var _taps: Dictionary = {}
var _cases: Dictionary = {}


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node3D = load("res://scenes/levels/prospekt.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() < 6:
		await get_tree().process_frame
	for i in range(30):
		await get_tree().process_frame
	var bots: Array = level.get_node("Marauders").get_children()
	for m: Marauder in bots:
		m.process_mode = Node.PROCESS_MODE_DISABLED
	var cases: Array = ["обычная смерть", "сильный удар в голову", "добили лежачего", "добили лежачего", "у стены", "огромный толчок"]
	for i: int in range(cases.size()):
		var m: Marauder = bots[i]
		_cases[m] = cases[i]
		m.process_mode = Node.PROCESS_MODE_INHERIT
		if String(cases[i]) == "у стены":
			_to_wall(m, level)
		var from: Vector3 = m.global_position + Vector3(8.0, 1.5, 2.0)
		m._last_hit_from = from
		match String(cases[i]):
			"сильный удар в голову":
				await _kill(m, from, 220.0, "head")
			"огромный толчок":
				await _kill(m, from, 10000.0, "head")
			"добили лежачего":
				await _kill(m, from, 45.0, "thorax", true)
				for f in range(240):
					await get_tree().physics_frame
				await _kill(m, from, 45.0, "thorax")
			_:
				await _kill(m, from, 45.0, "thorax")
		var sk := _skel(m)
		_check("%s (%s): убит, регдолл на модели" % [m.name, cases[i]], m.state == Marauder.State.DEAD and sk != null and sk.get_node_or_null("SkinRagdoll") != null)
		if sk:
			var tap := PoseTap.new()
			tap.name = "PoseTap"
			sk.add_child(tap)
			_taps[m] = tap
	await _measure("упали", 120)
	# пули по телам — толчок как у ВЕРАС-54 (урон 45), по каждой части
	for m: Marauder in _taps:
		var sim := _skel(m).get_node("SkinRagdoll") as SkinRagdoll
		for c: Node in sim.get_children():
			if c is PhysicalBone3D:
				sim.push(Vector3(-1.0, -0.2, 0.3).normalized() * 45.0 * Balance.BULLET_PUSH, (c as PhysicalBone3D).global_position)
	await _measure("пули по телам", 150)
	# разобрали ящики — тело раздевается на лету
	for m: Marauder in _taps:
		if is_instance_valid(m._crate):
			m._crate.items = []
	await _measure("разобрали ящики", 120)
	await _measure("лежат 8 с", 480)
	await _fallback_death(level, (bots[0] as Marauder).global_position + Vector3(0.0, 0.0, 3.0))
	print("ragdoll_test: %s, провалов %d" % ["OK" if _fails == 0 else "FAIL", _fails])
	get_tree().quit(1 if _fails > 0 else 0)


## Несовместимый скелет раньше включал клип смерти: теперь и здесь тело падает только физикой.
func _fallback_death(level: Node3D, at: Vector3) -> void:
	var m := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "FallbackDeath"
	level.get_node("Marauders").add_child(m)
	m.global_position = at
	var anim := m.get_node("CharacterAnimator") as CharacterAnimator
	var source_model := anim._model
	# Отдельный скелет без скина: несовместимые имена не ломают привязку сеток исходной модели.
	var model := Node3D.new()
	var sk := Skeleton3D.new()
	sk.add_bone("unsupported_Hips")
	model.add_child(sk)
	m._body.add_child(model)
	anim._model = model
	await _kill(m, at + Vector3(8.0, 1.5, 2.0), 10000.0, "head")
	_check("несовместимый скелет: смерть без клипа, запасной регдолл", m.state == Marauder.State.DEAD
		and is_instance_valid(m._ragdoll) and m._ragdoll.is_in_group("ragdolls") and not m._body.visible
		and not anim._pose.begins_with("death"))
	# Повторная обработка синхронизированной смерти не создаёт второе тело.
	var body := m._ragdoll
	m._process(0.016)
	_check("повторная обработка смерти: тот же регдолл", m._ragdoll == body and is_instance_valid(body))
	anim._model = source_model
	model.queue_free()


func _kill(m: Marauder, from: Vector3, dmg: float, zone: String, down_only: bool = false) -> void:
	for t in range(40):
		if m.state == Marauder.State.DEAD or (down_only and m.state == Marauder.State.DOWNED):
			return
		m._health.take_damage(dmg, from, zone)
		for i in range(4):
			await get_tree().physics_frame


## Встать в 0,3 м от ближайшей стены (16 направлений, до 25 м).
func _to_wall(m: Marauder, level: Node3D) -> void:
	var space := level.get_world_3d().direct_space_state
	var best := INF
	var best_hit: Dictionary = {}
	for a in range(16):
		var o: Vector3 = m.global_position + Vector3.UP * 1.2
		var h := space.intersect_ray(PhysicsRayQueryParameters3D.create(o, o + Vector3(cos(a * TAU / 16.0), 0.0, sin(a * TAU / 16.0)) * 25.0, 1))
		if not h.is_empty() and o.distance_to(h.position) < best:
			best = o.distance_to(h.position)
			best_hit = h
	if best_hit.is_empty():
		return
	var n: Vector3 = best_hit.normal
	n.y = 0.0
	var at: Vector3 = (best_hit.position as Vector3) + n.normalized() * 0.3
	m.global_position = Vector3(at.x, m.global_position.y, at.z)


func _measure(stage: String, frames: int) -> void:
	for t: PoseTap in _taps.values():
		t.worst = 0.0
	for i in range(frames):
		await get_tree().physics_frame
	for m: Marauder in _taps:
		var t: PoseTap = _taps[m]
		var spread := _spread(_skel(m))
		_check("%s · %s (%s): растяжение %.2f (%s), разлёт %.2f м" % [stage, m.name, _cases[m], t.worst, t.worst_bone, spread],
			t.worst <= STRETCH_MAX and spread <= SPREAD_MAX)


func _spread(sk: Skeleton3D) -> float:
	var pos: Array[Vector3] = []
	for c: Node in sk.get_node("SkinRagdoll").get_children():
		if c is PhysicalBone3D:
			pos.append((c as PhysicalBone3D).global_position)
	var far := 0.0
	for a: Vector3 in pos:
		for b: Vector3 in pos:
			far = maxf(far, a.distance_to(b))
	return far


func _skel(m: Marauder) -> Skeleton3D:
	var model: Node = m.get_node_or_null("Body/Persona")
	if model == null:
		return null
	var f: Array[Node] = model.find_children("*", "Skeleton3D", true, false)
	return f[0] as Skeleton3D if not f.is_empty() else null


func _check(label: String, ok: bool) -> void:
	if not ok:
		_fails += 1
	print("ragdoll_test: %s · %s" % ["PASS" if ok else "FAIL", label])
