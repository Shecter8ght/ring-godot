extends Node
## Кровь (BloodFx) на асфальте у стены в зоне 1: мародёр у стены, четыре попадания — капли в полёте,
## следы на асфальте и стене, подтёки стекают; убит — лужа растекается под телом; высохло. Потом
## игрок: попадание в себя (без облака в глаза), лёг раненым — лужа, подняли — лужа не растёт.
## Часы крови ускорены (BloodFx.time_k); игра и физика идут как обычно. Нужен рендер — только с окном.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/blood_shots.tscn → docs/screens/blood_*.png
## BLOOD_AT=x:z — своё место (иначе ищет асфальт со стеной рядом), BLOOD_TIME=day|dusk|night.

const SCENE := "res://scenes/levels/zone01_mall.tscn"
const PREFER := Vector2(-200.0, -60.0)

var _level: Node3D
var _me: Player
var _rig: CameraRig
var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	var tod: String = OS.get_environment("BLOOD_TIME") if OS.get_environment("BLOOD_TIME") != "" else "day"
	RaidConditions.from_host = {"time": tod, "weather": "clear", "power": "on"}
	_level = (load(SCENE) as PackedScene).instantiate() as Node3D
	get_tree().root.add_child.call_deferred(_level)
	await get_tree().process_frame
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	await _frames(5)
	var dummy: Marauder = null
	for m in _level.get_node("Marauders").get_children():
		if dummy == null and m is Marauder:
			dummy = m as Marauder
		else:
			m.queue_free()
	_me = Raid.current.local_player()
	_me.health.hp = 1e9
	_me.health.max_hp = 1e9
	_me.set_physics_process(false)
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	CameraRig.first_person_mode = true
	var spot := _find_spot()
	if spot.is_empty():
		print("blood_shots: не нашёл асфальт у стены")
		get_tree().quit(1)
		return
	var ground: Vector3 = spot.ground
	var wall_n: Vector3 = spot.wall_n
	var wall_p: Vector3 = spot.wall_p
	print("blood_shots: место %s, стена в %.1f м" % [ground, Vector2(ground.x, ground.z).distance_to(Vector2(wall_p.x, wall_p.z))])
	# мародёр — в 1.3 м от стены, игрок — в 4 м, смотрит на стену
	var to_wall := Vector3(-wall_n.x, 0.0, -wall_n.z).normalized()
	var target_at := _ground(wall_p + wall_n * 1.3)
	var eye_at := _ground(wall_p + wall_n * 4.2 + Vector3(wall_n.z, 0.0, -wall_n.x) * 1.2)
	dummy.global_position = target_at
	dummy.process_mode = Node.PROCESS_MODE_DISABLED
	_me.global_position = eye_at + Vector3.UP * 0.1
	await _frames(30)
	_look(target_at + to_wall * 0.6 + Vector3.UP * 0.7)
	await _frames(60)
	var blood := BloodFx.current
	_check("BloodFx есть", blood != null)
	_check("карты крови найдены", blood.stats().maps == 8)
	if OS.get_environment("BLOOD_PROBE") == "1":
		# проверка шейдера: лужа перед камерой и подтёк на стене, быстро
		var probe_g := _ground(eye_at - wall_n * 1.6 + Vector3(wall_n.z, 0.0, -wall_n.x) * 1.0)
		blood.pool(_level, probe_g, Vector3.UP, 1.4, 1.5)
		blood.drip(_level, wall_p + Vector3.UP * 1.1 + wall_n * 0.01, wall_n, 0.008)
		_look(probe_g)
		await get_tree().create_timer(2.5).timeout
		await _shot("blood_0_probe")
		_look(wall_p + Vector3.UP * 0.8)
		blood.time_k = 6.0
		await get_tree().create_timer(3.0).timeout
		blood.time_k = 1.0
		await _shot("blood_0_probe_wall")
		get_tree().quit(0)
		return
	var splats0: int = int(blood.stats().splats)
	# четыре попадания в корпус на разной высоте; пуля летит от игрока к стене
	for i in range(4):
		var hit_p := target_at + Vector3.UP * (1.05 + 0.15 * i) + Vector3(wall_n.z, 0.0, -wall_n.x) * (0.12 * (i - 1.5))
		var dir := (hit_p - _me.eye_position()).normalized()
		ImpactFx.spawn_hit({"position": hit_p, "normal": -dir, "collider": dummy}, dir)
		await _frames(3)
	_check("капли летят", int(blood.stats().drops) > 10)
	await _frames(4)
	await _shot("blood_1_spray")
	await get_tree().create_timer(1.2).timeout
	_check("следы легли: %d" % (int(blood.stats().splats) - splats0), int(blood.stats().splats) - splats0 >= 8)
	await _shot("blood_2_splats")
	# подтёки стекают по стене (часы крови быстрее в 4 раза)
	blood.time_k = 4.0
	await get_tree().create_timer(10.0 / 4.0).timeout
	blood.time_k = 1.0
	_check("подтёки есть: %d" % int(blood.stats().boxes), int(blood.stats().boxes) >= 1)
	await _shot("blood_3_drips")
	_look(wall_p + Vector3.UP * 0.9)
	await _frames(10)
	await _shot("blood_3_drips_close")
	# убит: лужа под телом
	dummy.process_mode = Node.PROCESS_MODE_INHERIT
	var from := _me.eye_position()
	# первое — ранен (лежит и отстреливается), дальше — добит в том же кадре (урон обычный: толчок
	# тела растёт с уроном)
	var dh := dummy.get_node("Health") as Health
	for i in range(8):
		if not dh.alive:
			break
		dh.take_damage(120.0, from, "thorax")
	_check("мародёр убит", not dh.alive)
	await get_tree().create_timer(2.0).timeout
	var anim := dummy.get_node_or_null("CharacterAnimator") as CharacterAnimator
	var spine := anim.bone_node("mixamorig_Spine") if anim else null
	var model_vis := "?"
	if anim:
		var models := dummy.find_children("*", "MeshInstance3D", true, false)
		model_vis = "%d сеток, видны %d" % [models.size(), models.filter(func(m: Node) -> bool: return (m as MeshInstance3D).is_visible_in_tree()).size()]
	print("blood_shots: убит: узел %s, грудь %s, модель %s" % [dummy.global_position, spine.global_position if spine else Vector3.INF, model_vis])
	_look(dummy.global_position)
	await _frames(4)
	await _shot("blood_4_dead")
	blood.time_k = 6.0
	await get_tree().create_timer(30.0 / 6.0).timeout
	_check("лужа под убитым", int(blood.stats().bodies) >= 1)
	if is_instance_valid(dummy):
		var ms := dummy.find_children("*", "MeshInstance3D", true, false)
		print("blood_shots: через 30 с: в дереве %s, виден %s, грудь %s, видимых сеток %d" % [dummy.is_inside_tree(), dummy.is_visible_in_tree(),
			spine.global_position if is_instance_valid(spine) else Vector3.INF, ms.filter(func(m: Node) -> bool: return (m as MeshInstance3D).is_visible_in_tree()).size()])
	else:
		print("blood_shots: через 30 с: мародёр удалён")
	_look(dummy.global_position + Vector3.UP * 0.0)
	await _frames(6)
	await _shot("blood_4_pool")
	await get_tree().create_timer(60.0 / 6.0).timeout
	blood.time_k = 1.0
	await _shot("blood_5_pool_full")
	# сверху — форма лужи
	_me.global_position = dummy.global_position + wall_n * 2.0 + Vector3.UP * 1.2
	_look(dummy.global_position + wall_n * 0.3)
	await _frames(6)
	await _shot("blood_5_pool_top")
	# высохло: часы крови вперёд
	blood.set("_clock", blood.clock() + float(Balance.BLOOD.dry_sec) * 1.1)
	blood.call("_dry_splats")
	await _frames(6)
	await _shot("blood_6_dried")
	# игрок: попадание в себя, лёг раненым, лужа; подняли — лужа не растёт.
	# подошедших за это время мародёров (население рейда) убираем — стрелять в игрока некому
	for m in _level.get_node("Marauders").get_children():
		if m != dummy:
			m.queue_free()
	_me.health.revive(1.0)
	_me.global_position = _ground(eye_at + wall_n * 3.0) + Vector3.UP * 0.1
	await _frames(10)
	var boxes0: int = int(blood.stats().boxes)
	var chest := _me.global_position + Vector3.UP * 1.3
	ImpactFx.spawn_hit({"position": chest, "normal": wall_n, "collider": _me}, -wall_n)
	await _frames(2)
	_check("попадание в себя — капли", int(blood.stats().drops) > 0)
	_me.health.max_hp = 100.0
	_me.health.hp = 50.0
	_me.health.take_damage(500.0, chest + wall_n * 5.0, "thorax")
	_check("игрок лёг раненым (жив %s, лежит %s, ранений %d)" % [_me.health.alive, _me.health.downed, _me.health.downs], _me.health.downed)
	await get_tree().create_timer(3.0).timeout
	_check("лужа под раненым игроком", int(blood.stats().boxes) > boxes0)
	await _shot("blood_7_me_down")
	# тащат 2.5 м: за телом мазок, на новом месте — новая лужа
	var splats1: int = int(blood.stats().splats)
	var boxes1: int = int(blood.stats().boxes)
	var drag_from := _me.global_position
	var drag_dir := Vector3(wall_n.z, 0.0, -wall_n.x)
	for i in range(120):
		_me.global_position = _ground(drag_from + drag_dir * 2.5 * float(i) / 119.0) + Vector3.UP * 0.1
		await get_tree().physics_frame
	await get_tree().create_timer(2.5).timeout
	_check("тащили — мазок: %d следов" % (int(blood.stats().splats) - splats1), int(blood.stats().splats) > splats1)
	_check("на новом месте — новая лужа", int(blood.stats().boxes) > boxes1)
	_look(drag_from + drag_dir * 1.2 + Vector3.DOWN * 1.0)
	await _frames(6)
	await _shot("blood_8_dragged")
	_me.health.revive(0.5)
	await get_tree().create_timer(1.0).timeout
	_check("подняли — раненый снят с учёта", int(blood.stats().bodies) <= 1)
	print("blood_shots: ", blood.stats())
	print("blood_shots: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Асфальт, рядом отвесная стена (1–2.5 м): ближе к PREFER. BLOOD_AT — своё место.
func _find_spot() -> Dictionary:
	var space := _level.get_world_3d().direct_space_state
	var points: Array[Vector2] = []
	if OS.get_environment("BLOOD_AT") != "":
		var p := OS.get_environment("BLOOD_AT").split(":")
		points.append(Vector2(float(p[0]), float(p[1])))
	else:
		for r in range(0, 260, 4):
			for k in range(maxi(1, r / 2)):
				var a := TAU * float(k) / float(maxi(1, r / 2))
				points.append(PREFER + Vector2(cos(a), sin(a)) * float(r))
	for pt in points:
		var top := Vector3(pt.x, 80.0, pt.y)
		var down: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(top, top + Vector3.DOWN * 160.0, Hitscan.LAYER_WORLD))
		if down.is_empty() or (down.normal as Vector3).y < 0.95:
			continue
		if Surfaces.kind_at(down) != "asphalt" and OS.get_environment("BLOOD_AT") == "":
			continue
		var g: Vector3 = down.position
		for i in range(12):
			var a := TAU * float(i) / 12.0
			var d := Vector3(cos(a), 0.0, sin(a))
			var from := g + Vector3.UP * 1.0
			var w: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from + d * 2.5, Hitscan.LAYER_WORLD))
			if w.is_empty():
				continue
			var n: Vector3 = w.normal
			if absf(n.y) > 0.2 or from.distance_to(w.position) < 1.4:
				continue
			# настоящий фасад: та же стена и выше (низкие невидимые коробки и заборы не годятся)
			var tall := true
			var side := Vector3(-d.z, 0.0, d.x)
			for off: Vector3 in [Vector3.UP * 2.5, Vector3.UP * 4.5, Vector3.UP * 1.0 + side * 1.2, Vector3.UP * 1.0 - side * 1.2]:
				var f2 := g + off
				var w2: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(f2, f2 + d * 3.0, Hitscan.LAYER_WORLD))
				if w2.is_empty() or (w2.normal as Vector3).dot(n) < 0.95 or absf(f2.distance_to(w2.position) - from.distance_to(w.position)) > 0.3:
					tall = false
					break
			if not tall:
				continue
			# у стены и сзади (где игрок) — свободно
			var back: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(from, from - d * 4.5, Hitscan.LAYER_WORLD))
			if not back.is_empty():
				continue
			return {"ground": g, "wall_p": Vector3((w.position as Vector3).x, g.y, (w.position as Vector3).z), "wall_n": Vector3(n.x, 0.0, n.z).normalized()}
	return {}


func _ground(p: Vector3) -> Vector3:
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 3.0, p + Vector3.DOWN * 6.0, Hitscan.LAYER_WORLD)
	var hit: Dictionary = _level.get_world_3d().direct_space_state.intersect_ray(q)
	return (hit.position as Vector3) if not hit.is_empty() else p


func _look(target: Vector3) -> void:
	var d := target - _me.eye_position()
	_rig._look_yaw = atan2(d.x, d.z)
	_rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())


func _check(what: String, ok: bool) -> void:
	print("blood_shots: %s — %s" % ["OK" if ok else "ПРОВАЛ", what])
	if not ok:
		_fails += 1


func _shot(name: String) -> void:
	await RenderingServer.frame_post_draw
	var path := "res://docs/screens/%s.png" % name
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path(path))
	print("blood_shots: ", path)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
