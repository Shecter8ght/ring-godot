class_name Grenade
extends RigidBody3D
## Брошенная граната: летит и катится физикой, через запал взрывается. Урон — всем Health в
## радиусе, до кого есть прямая линия (за стеной не достанет), с падением к краю; толчок —
## регдоллам и мишеням; шум — для AI; вспышка, огненный шар, дым, подпалина, звук, тряска.
## Урон проходит через Health.apply_or_request_damage — в сети его считает хост.

var _fuse: float = 0.0
var _thrower: RID
var _bounced: float = 0.0


static func throw(parent: Node, from: Vector3, velocity: Vector3, thrower: RID) -> Grenade:
	var g := Grenade.new()
	g.name = "Grenade"
	g._thrower = thrower
	g.mass = 0.6
	g.collision_layer = Hitscan.LAYER_DEBRIS
	g.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_DEBRIS
	g.continuous_cd = true
	var pm := PhysicsMaterial.new()
	pm.bounce = 0.35
	pm.friction = 0.8
	g.physics_material_override = pm
	g.linear_damp = 0.15
	g.angular_damp = 1.2
	var cs := CollisionShape3D.new()
	var sh := SphereShape3D.new()
	sh.radius = 0.036
	cs.shape = sh
	g.add_child(cs)
	g.add_child(WeaponModels.build("grenade"))
	g.contact_monitor = true
	g.max_contacts_reported = 2
	parent.add_child(g)
	g.global_position = from
	g.linear_velocity = velocity
	g.angular_velocity = Vector3(randf_range(-8, 8), randf_range(-4, 4), randf_range(-8, 8))
	g._fuse = float(Balance.GRENADE.fuse)
	g.body_entered.connect(g._on_bounce)
	Audio.play("pin", from)
	return g


func _on_bounce(_b: Node) -> void:
	# стук о пол — не чаще раза в 0.15 с и только если летела заметно быстро
	if _bounced <= 0.0 and linear_velocity.length() > 1.5:
		Audio.play("impact_metal", global_position, -10.0)
		_bounced = 0.15


func _physics_process(delta: float) -> void:
	_bounced -= delta
	_fuse -= delta
	if _fuse <= 0.0:
		_explode()


func _explode() -> void:
	var pos := global_position + Vector3.UP * 0.15
	var spec: Dictionary = Balance.GRENADE
	var radius := float(spec.radius)
	var space := get_world_3d().direct_space_state
	for group in ["players", "marauders", "shootable"]:
		for n in get_tree().get_nodes_in_group(group):
			var body := n as Node3D
			if body == null:
				continue
			var point := body.global_position + Vector3.UP * 1.0
			var d := pos.distance_to(point)
			if d > radius:
				continue
			# прямая видимость: стена или ящик между гранатой и целью — укрытие
			var q := PhysicsRayQueryParameters3D.create(pos, point, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
			if not space.intersect_ray(q).is_empty():
				continue
			var dmg := float(spec.damage) * pow(1.0 - d / radius, 1.3)
			if body is Target:
				(body as Target).on_hit(point, (point - pos).normalized(), dmg)
			var h := body.get_node_or_null("Health") as Health
			if h:
				# подорвался на ней — насмерть; дальше — ранит (осколки, броня помогает)
				var feet := pos.distance_to(body.global_position + Vector3.UP * 0.5)
				h.apply_or_request_damage(dmg, pos, "blast_close" if feet < Balance.GRENADE_LETHAL_M else "blast")
	for rd in get_tree().get_nodes_in_group("ragdolls"):
		var r := rd as Ragdoll
		var c := r.chest()
		if c and c.global_position.distance_to(pos) < radius:
			var k := 1.0 - c.global_position.distance_to(pos) / radius
			r.push(((c.global_position - pos).normalized() + Vector3.UP * 0.6) * float(spec.push) * k, c.global_position)
	NoiseBus.emit(pos, float(spec.noise_m), "shot")
	ImpactFx.explosion(pos)
	Audio.play("explosion", pos)
	Audio.play("debris", pos, -4.0)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig:
		var cam_d := pos.distance_to(rig.focus_point())
		rig.add_shake(clampf(1.0 - cam_d / float(spec.shake_radius), 0.0, 1.0) * 0.9)
	queue_free()
