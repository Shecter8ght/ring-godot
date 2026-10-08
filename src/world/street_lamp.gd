@tool
class_name StreetLamp
extends Node3D
## Уличный фонарь: столб (высота height), консоль в сторону -Z узла, светильник светит вниз.
## Горит в сумерки и ночью, если подстанция даёт ток (Raid.switches[switch_id], по умолчанию —
## да; рубильник на подстанции гасит все фонари с этим switch_id). Свет — Balance.STREET_LAMP;
## вдали гаснет, тень — только вблизи. Геометрия строится скриптом (и в редакторе), в .tscn не
## сохраняется: в сцене — только положение и параметры.

@export var height: float = 10.0:
	set(v):
		height = maxf(3.0, v)
		_rebuild()
## Длина консоли, м (светильник выносится над проезжей частью).
@export var arm: float = 1.6:
	set(v):
		arm = maxf(0.0, v)
		_rebuild()
@export var switch_id: String = "street_lights"

var _light: SpotLight3D
var _lens: StandardMaterial3D
var _gen: Node3D
var _t: float = 0.0
## Плавный уровень 0..1 и решение (общая система RaidWeather + ток подстанции), проверяется дважды в секунду.
var _k: float = 0.0
var _want: bool = false


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("nav_source")
		# при появлении — сразу как есть, дальше включается и гаснет плавно
		_want = is_lit()
		_k = 1.0 if _want else 0.0
	_rebuild()


func _rebuild() -> void:
	if not is_inside_tree():
		return
	if _gen:
		_gen.queue_free()
	_gen = Node3D.new()
	_gen.name = "Gen"
	add_child(_gen)
	var metal := StandardMaterial3D.new()
	metal.albedo_color = Color(0.32, 0.33, 0.34)
	metal.metallic = 0.6
	metal.roughness = 0.5
	# столб сужается к верху, у земли — бетонный стакан
	var pole := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.07
	cm.bottom_radius = 0.13
	cm.height = height
	pole.mesh = cm
	pole.position.y = height * 0.5
	pole.material_override = metal
	_gen.add_child(pole)
	var base := MeshInstance3D.new()
	var bm := CylinderMesh.new()
	bm.top_radius = 0.22
	bm.bottom_radius = 0.26
	bm.height = 0.5
	base.mesh = bm
	base.position.y = 0.25
	var conc := StandardMaterial3D.new()
	conc.albedo_color = Color(0.5, 0.5, 0.48)
	conc.roughness = 0.9
	base.material_override = conc
	_gen.add_child(base)
	# консоль и светильник
	var arm_m := MeshInstance3D.new()
	var am := BoxMesh.new()
	am.size = Vector3(0.08, 0.08, arm + 0.1)
	arm_m.mesh = am
	arm_m.position = Vector3(0, height - 0.1, -arm * 0.5)
	arm_m.material_override = metal
	_gen.add_child(arm_m)
	var head := MeshInstance3D.new()
	var hm := BoxMesh.new()
	hm.size = Vector3(0.36, 0.12, 0.7)
	head.mesh = hm
	head.position = Vector3(0, height - 0.12, -arm - 0.2)
	head.material_override = metal
	_gen.add_child(head)
	var lens := MeshInstance3D.new()
	var lm := BoxMesh.new()
	lm.size = Vector3(0.3, 0.02, 0.6)
	lens.mesh = lm
	lens.position = Vector3(0, height - 0.19, -arm - 0.2)
	_lens = StandardMaterial3D.new()
	_lens.albedo_color = Color(0.9, 0.9, 0.85)
	_lens.emission_enabled = true
	_lens.emission = Color(1.0, 0.86, 0.66)
	_lens.emission_energy_multiplier = 0.0
	lens.material_override = _lens
	_gen.add_child(lens)
	# коллизия столба — в него упираются и пули, и люди
	var body := StaticBody3D.new()
	body.collision_layer = Hitscan.LAYER_WORLD
	var cs := CollisionShape3D.new()
	var sh := CylinderShape3D.new()
	sh.radius = 0.16
	sh.height = height
	cs.shape = sh
	cs.position.y = height * 0.5
	body.add_child(cs)
	_gen.add_child(body)
	var ls: Dictionary = Balance.STREET_LAMP
	_light = SpotLight3D.new()
	_light.name = "Light"
	_light.position = Vector3(0, height - 0.22, -arm - 0.2)
	_light.rotation.x = -PI * 0.5
	_light.light_color = ls.color
	_light.light_energy = float(ls.energy)
	_light.spot_range = float(ls.range)
	_light.spot_angle = float(ls.angle)
	_light.spot_angle_attenuation = float(ls.get("edge", 0.6))
	_light.spot_attenuation = float(ls.get("falloff", 1.0))
	_light.light_indirect_energy = float(ls.indirect)
	_light.light_volumetric_fog_energy = float(ls.fog)
	_light.shadow_enabled = true
	_light.distance_fade_enabled = true
	_light.distance_fade_begin = float(ls.fade_begin)
	_light.distance_fade_length = 25.0
	_light.distance_fade_shadow = float(ls.shadow_m)
	_light.visible = Engine.is_editor_hint()
	_gen.add_child(_light)
	if Engine.is_editor_hint():
		_lens.emission_energy_multiplier = float(ls.lens)
	else:
		_apply_k()


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_t -= delta
	if _t <= 0.0:
		_t = 0.5
		_want = is_lit()
		if _light and _k > 0.0:
			_light.light_specular = lerpf(0.5, 1.0, RaidWeather.wetness())
	var goal := 1.0 if _want else 0.0
	if _k != goal:
		_k = move_toward(_k, goal, delta / float(Balance.OUTDOOR_LIGHTS.fade_sec))
		_apply_k()


## Горит: темно (общая система наружного света) и подстанция даёт ток.
func is_lit() -> bool:
	var powered := Raid.current == null or bool(Raid.current.switches.get(switch_id, true))
	return RaidWeather.street_lights_wanted() and powered


func _apply_k() -> void:
	if _light == null:
		return
	_light.visible = _k > 0.001
	_light.light_energy = float(Balance.STREET_LAMP.energy) * _k
	_lens.emission_energy_multiplier = float(Balance.STREET_LAMP.lens) * _k
