extends Node3D
## Коллизия моделей контейнеров лута (LootContainerVisual, Balance.LOOT_COLLISION): тело есть у высоких и настенных, нет у мелочи;
## коробка по габариту закрытой модели; пуля спереди упирается в сейф, шкаф и картотеку и даёт «металл»; идущий в них останавливается;
## обыск (близость и обзор) с фасада работает; раскрытый шкаф не добавляет коллизий створкам; тела не входят в выпечку навигации (группа nav_source).
## godot --headless --path . res://tools/loot_collision_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	var ground := StaticBody3D.new()
	ground.add_to_group("nav_source")
	ground.collision_layer = Hitscan.LAYER_WORLD
	add_child(ground)
	var gs := CollisionShape3D.new()
	var gb := BoxShape3D.new()
	gb.size = Vector3(160, 1, 160)
	gs.shape = gb
	gs.position = Vector3(0, -0.5, 0)
	ground.add_child(gs)
	var kinds: Dictionary = LootContainerVisual.catalog().get("kinds", {}) as Dictionary
	var boxes: Dictionary = {}
	var x: float = -60.0
	for kind: String in kinds:
		if LootContainerVisual.kind_model(kind) == "":
			continue
		var c: LootContainer = LootContainer.new()
		c.kind = kind
		c.name = "T_" + kind
		c.require_line_of_sight = true
		add_child(c)
		c.global_position = Vector3(x, 0, -30)
		x += 6.0
		boxes[kind] = c
	await get_tree().physics_frame
	await get_tree().physics_frame
	var rules: Dictionary = Balance.LOOT_COLLISION
	for kind: String in boxes:
		var c: LootContainer = boxes[kind] as LootContainer
		var spec: Dictionary = LootContainerVisual.model_spec(LootContainerVisual.kind_model(kind))
		var body: StaticBody3D = c.find_child(LootContainerVisual.BODY_NAME, true, false) as StaticBody3D
		var size: Array = (spec.aabb as Dictionary).size
		var want: bool = float(size[1]) >= float(rules.min_height) or bool(spec.get("wall", false))
		_check("%s: тело %s по порогу" % [kind, "есть" if want else "нет"], (body != null) == want, "высота %.2f" % float(size[1]))
		if body == null:
			continue
		var bs: BoxShape3D = (body.get_child(0) as CollisionShape3D).shape as BoxShape3D
		_check("%s: коробка по габариту" % kind, bs != null and absf(bs.size.x - float(size[0])) < 0.001 and absf(bs.size.y - float(size[1])) < 0.001
			and absf(bs.size.z - float(size[2])) < 0.001, str(bs.size if bs else null))
		_check("%s: слой world, поверхность %s" % [kind, String(body.get_meta("surface", ""))], body.collision_layer == Hitscan.LAYER_WORLD and body.has_meta("surface"), "")
	var space := get_world_3d().direct_space_state
	for kind: String in ["safe", "weapon_locker", "filing"]:
		if not boxes.has(kind):
			continue
		var c: LootContainer = boxes[kind] as LootContainer
		var spec: Dictionary = LootContainerVisual.model_spec(LootContainerVisual.kind_model(kind))
		var center: Vector3 = c.global_position + Vector3(0, 0.5, 0)
		var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(center + Vector3(0, 0, 3.0), center, Hitscan.LAYER_WORLD))
		var surf: String = Surfaces.kind_at(hit) if not hit.is_empty() else ""
		_check("пуля спереди упирается в %s: поверхность %s" % [kind, surf], not hit.is_empty() and surf == "metal", str(hit.get("collider")))
		var walker := CharacterBody3D.new()
		walker.collision_layer = Hitscan.LAYER_PLAYER
		walker.collision_mask = Hitscan.LAYER_WORLD
		var cs := CollisionShape3D.new()
		var cap := CapsuleShape3D.new()
		cap.radius = 0.4
		cap.height = 1.8
		cs.shape = cap
		cs.position = Vector3(0, 0.9, 0)
		walker.add_child(cs)
		add_child(walker)
		walker.global_position = c.global_position + Vector3(0, 0.05, 2.5)
		for i in range(90):
			walker.velocity = Vector3(0, 0, -3.0)
			walker.move_and_slide()
			await get_tree().physics_frame
		var aabb: Dictionary = spec.aabb as Dictionary
		var front: float = c.global_position.z + float(aabb.center[2]) + float(aabb.size[2]) * 0.5
		_check("идущий в %s останавливается у фасада" % kind, walker.global_position.z > front, "z %.2f, фасад %.2f" % [walker.global_position.z, front])
		# обыск с 1,2 м от фасада: близость и обзор (у контейнера require_line_of_sight)
		walker.global_position = Vector3(c.global_position.x, 0.05, front + 1.2 - 0.4)
		var dist: float = c.global_position.distance_to(walker.global_position)
		_check("обыск %s: от игрока %.2f м (< %.1f), can_use" % [kind, dist, Balance.INTERACT_RADIUS], dist < Balance.INTERACT_RADIUS and c.can_use(), "")
		var eye: Vector3 = walker.global_position + Vector3(0, 1.6, 0)
		var own: CollisionObject3D = c.find_child(LootContainerVisual.BODY_NAME, true, false) as CollisionObject3D
		var q := PhysicsRayQueryParameters3D.create(eye, c.global_position + Vector3.UP * 0.08, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
		var blocked: bool = not space.intersect_ray(q).is_empty()
		q.exclude = [own.get_rid()]
		_check("обзор до %s без собственного тела свободен (с телом: %s)" % [kind, "закрыт" if blocked else "свободен"], space.intersect_ray(q).is_empty(), "")
		walker.queue_free()
	if boxes.has("weapon_locker"):
		var g: LootContainer = boxes["weapon_locker"] as LootContainer
		g.rolled = true
		await get_tree().physics_frame
		var bodies: Array[Node] = g.find_children("*", "CollisionObject3D", true, false)
		_check("раскрытый шкаф: одно тело коллизии", bodies.size() == 1, str(bodies.size()))
	# выпечка навигации (UrbanNavigation) берёт статические коллайдеры группы nav_source: тел контейнеров там нет (кэш навигации не зависит от них)
	for kind: String in ["safe", "weapon_locker", "filing", "med_cabinet"]:
		if boxes.has(kind):
			var b: Node = (boxes[kind] as LootContainer).find_child(LootContainerVisual.BODY_NAME, true, false)
			_check("тело %s не в группе nav_source (вне выпечки навигации)" % kind, b != null and not b.is_in_group("nav_source"), "")
	print("loot_collision_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
