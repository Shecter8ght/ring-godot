class_name Grenade
extends RigidBody3D
## Брошенная граната: летит и катится физикой, через запал взрывается. Урон — всем Health в
## радиусе, до кого есть прямая линия (за стеной не достанет), с падением к краю; толчок —
## регдоллам и мишеням; шум — для AI; вспышка, огненный шар, дым, подпалина, звук, тряска.
## Урон проходит через Health.apply_or_request_damage — в сети его считает хост.

var _fuse: float = 0.0
var _thrower: RID
var _bounced: float = 0.0
## Считать ли урон этой гранатой (граната мародёра у клиентов — только картинка и звук).
var _damage: bool = true
## Кто бросил: -1 — игрок этого peer (убийство — ему), 0 — ИИ (никому).
var _attacker: int = -1
## Огонёк: светодиод, ореол вокруг (виден из изометрии) и красный свет — мигают всё чаще к взрыву.
var _led: Node3D
var _led_light: OmniLight3D
var _blink: float = 0.0


static func throw(parent: Node, from: Vector3, velocity: Vector3, thrower: RID, deal_damage: bool = true, attacker: int = -1) -> Grenade:
	var g := Grenade.new()
	g.name = "Grenade"
	g._thrower = thrower
	g._damage = deal_damage
	g._attacker = attacker
	g.mass = 0.6
	g.collision_layer = Hitscan.LAYER_DEBRIS
	g.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_DEBRIS | Hitscan.LAYER_GLASS
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
	g._build_led()
	g.body_entered.connect(g._on_bounce)
	Audio.play("pin", from)
	return g


func _on_bounce(_b: Node) -> void:
	# стук о пол — не чаще раза в 0.15 с и только если летела заметно быстро
	if _bounced <= 0.0 and linear_velocity.length() > 1.5:
		Audio.play("impact_metal", global_position, -10.0)
		_bounced = 0.15


## Светодиод на запале: красная точка, ореол-билборд и свет (Balance.GRENADE_LED).
func _build_led() -> void:
	var cfg: Dictionary = Balance.GRENADE_LED
	_led = Node3D.new()
	_led.name = "Led"
	# не крутится с гранатой: огонёк сверху, ореол смотрит в камеру
	_led.top_level = true
	add_child(_led)
	var dot := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.015
	sm.height = 0.03
	dot.mesh = sm
	var dm := StandardMaterial3D.new()
	dm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dm.albedo_color = Color(1.0, 0.15, 0.1)
	dot.material_override = dm
	dot.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_led.add_child(dot)
	var halo := MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2.ONE * float(cfg.halo_m)
	halo.mesh = qm
	var hm := StandardMaterial3D.new()
	hm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	hm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	hm.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	hm.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	hm.albedo_color = Color(1.0, 0.2, 0.12, 0.9)
	var grad := Gradient.new()
	grad.set_color(0, Color(1, 1, 1, 1))
	grad.set_color(1, Color(1, 1, 1, 0))
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	hm.albedo_texture = tex
	halo.material_override = hm
	halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_led.add_child(halo)
	_led_light = OmniLight3D.new()
	_led_light.light_color = Color(1.0, 0.15, 0.08)
	_led_light.light_energy = float(cfg.light_energy)
	_led_light.omni_range = float(cfg.light_range)
	_led_light.shadow_enabled = false
	_led.add_child(_led_light)


func _process(delta: float) -> void:
	if _led == null:
		return
	var cfg: Dictionary = Balance.GRENADE_LED
	_led.global_position = global_position + Vector3.UP * 0.07
	# период мигания — от медленного к частому по мере запала
	var left := clampf(_fuse / float(Balance.GRENADE.fuse), 0.0, 1.0)
	var period := lerpf(float(cfg.fast), float(cfg.slow), left)
	_blink += delta / period
	_led.visible = fmod(_blink, 1.0) < 0.5


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
			if h and _damage:
				# подорвался на ней — насмерть; дальше — ранит (осколки, броня помогает)
				var feet := pos.distance_to(body.global_position + Vector3.UP * 0.5)
				h.apply_or_request_damage(dmg, pos, "blast_close" if feet < Balance.GRENADE_LETHAL_M else "blast", _attacker)
	for rd in get_tree().get_nodes_in_group("ragdolls"):
		var r := rd as Ragdoll
		var c := r.chest()
		if c and c.global_position.distance_to(pos) < radius:
			var k := 1.0 - c.global_position.distance_to(pos) / radius
			r.push(((c.global_position - pos).normalized() + Vector3.UP * 0.6) * float(spec.push) * k, c.global_position)
	# стёкла рядом вылетают (решает хост — у него урон)
	if _damage:
		for gp in get_tree().get_nodes_in_group("glass_panes"):
			(gp as GlassPanes).blast(pos, radius * 1.3)
	NoiseBus.emit(pos, float(spec.noise_m), "shot")
	ImpactFx.explosion(pos)
	Audio.play("explosion", pos)
	Audio.play("debris", pos, -4.0)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig:
		var cam_d := pos.distance_to(rig.focus_point())
		rig.add_shake(clampf(1.0 - cam_d / float(spec.shake_radius), 0.0, 1.0) * 0.9)
	queue_free()
