class_name ThrownLight
extends RigidBody3D
## Брошенный свет: осветительная ракета (flare — ярко, красным, минуту; кто смотрит в неё рядом
## — слепнет, освещённое место видно издалека, в том числе тебя) и химсвет (chem — тускло,
## зелёным, долго, тихо: метка). Летит и катится физикой, как граната; свет — у каждого peer
## (бросок рассылает Player). Параметры — Balance.THROWN_LIGHTS.

var kind: String = "flare"
var _t: float = 0.0
## Касался земли / сколько катится / сколько уже медленный — чтобы замереть.
var _landed: bool = false
var _roll_t: float = 0.0
var _slow_t: float = 0.0
var _light: OmniLight3D
var _base_energy: float = 1.0


static func throw(parent: Node, k: String, from: Vector3, velocity: Vector3) -> ThrownLight:
	var spec: Dictionary = Balance.THROWN_LIGHTS[k]
	var g := ThrownLight.new()
	g.name = "Light_" + k
	g.kind = k
	g.mass = 0.3
	g.collision_layer = Hitscan.LAYER_DEBRIS
	g.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_DEBRIS | Hitscan.LAYER_GLASS
	g.continuous_cd = true
	var pm := PhysicsMaterial.new()
	pm.bounce = 0.25
	pm.friction = 0.9
	g.physics_material_override = pm
	g.linear_damp = 0.2
	g.angular_damp = 2.0
	var cs := CollisionShape3D.new()
	var sh := CapsuleShape3D.new()
	sh.radius = 0.02
	sh.height = 0.16
	cs.shape = sh
	cs.rotation.z = PI * 0.5
	g.add_child(cs)
	var body := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.018
	cm.bottom_radius = 0.018
	cm.height = 0.16
	body.mesh = cm
	body.rotation.z = PI * 0.5
	var mat := StandardMaterial3D.new()
	mat.albedo_color = spec.color
	mat.emission_enabled = true
	mat.emission = spec.color
	mat.emission_energy_multiplier = 6.0
	body.material_override = mat
	g.add_child(body)
	g._light = OmniLight3D.new()
	g._light.light_color = spec.color
	g._light.light_energy = float(spec.energy)
	g._light.omni_range = float(spec.range)
	g._light.shadow_enabled = bool(spec.get("shadow", false))
	# мягкий рассеянный: больше отражённого света (заливает помещение), размытая тень
	g._light.light_indirect_energy = float(spec.get("indirect", 1.0))
	g._light.shadow_blur = float(spec.get("blur", 1.0))
	# свет не крутится вместе с палочкой — висит над ней (иначе катится — и свет скачет)
	g._light.top_level = true
	g._base_energy = float(spec.energy)
	g.add_child(g._light)
	g.add_to_group("thrown_lights")
	if k == "flare":
		g.add_to_group("flares")
	parent.add_child(g)
	# смягчение света (Settings.soften) при входе в дерево пересчитало яркость — от неё и мерцать
	g._base_energy = g._light.light_energy
	g.global_position = from
	g.linear_velocity = velocity
	g.angular_velocity = Vector3(randf_range(-6, 6), randf_range(-3, 3), randf_range(-6, 6))
	g._t = float(spec.sec)
	g.contact_monitor = true
	g.max_contacts_reported = 2
	g._light.global_position = from + Vector3.UP * 0.15
	Audio.play("pin", from, -6.0)
	return g


func radius() -> float:
	return float(Balance.THROWN_LIGHTS[kind].range)


func _physics_process(delta: float) -> void:
	_light.global_position = global_position + Vector3.UP * 0.15
	if freeze:
		return
	# на земле — гасит качение и замирает (Balance.THROWN_SETTLE)
	var st: Dictionary = Balance.THROWN_SETTLE
	if not _landed and get_contact_count() > 0:
		_landed = true
		angular_damp = float(st.roll_damp)
		linear_damp = 3.0
	if not _landed:
		return
	_roll_t += delta
	_slow_t = _slow_t + delta if linear_velocity.length() < float(st.settle_speed) else 0.0
	if _slow_t >= float(st.settle_sec) or _roll_t >= float(st.max_roll_sec):
		linear_velocity = Vector3.ZERO
		angular_velocity = Vector3.ZERO
		freeze_mode = RigidBody3D.FREEZE_MODE_STATIC
		freeze = true


func _process(delta: float) -> void:
	_t -= delta
	if _t <= 0.0:
		queue_free()
		return
	# ракета горит неровно и к концу тускнеет
	var k := clampf(_t / 8.0, 0.0, 1.0)
	if kind == "flare":
		_light.light_energy = _base_energy * k * randf_range(0.8, 1.15)
	else:
		_light.light_energy = _base_energy * k
