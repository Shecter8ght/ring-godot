class_name SkyFlare
extends Node3D
## Осветительная ракета из сигнального пистолета: взлетает высоко, раскрывается и медленно опускается,
## заливая большой участок красным рассеянным светом; в воздухе Balance.SKY_FLARE.air_sec, потом гаснет.
## Летит по расчётной траектории (одинаково у всех peer — запуск рассылает Player), без физики:
## подъём с замедлением до вершины, дальше спуск с постоянной скоростью и лёгким сносом. Упёрлась в
## потолок — вершина там; дошла до земли — догорает лёжа.
## Свет — прожектор вниз с широким конусом и сильно размытой тенью (под крыши не светит), плюс свечение
## в тумане; звезда с двумя ореолами и искры — чтобы её было видно издалека.
## В группах "flares" (слепит вблизи, как ручная) и "sky_flares" (RaidAtmosphere: кто на улице в её
## круге — виден издалека).

var _from: Vector3
var _dir: Vector3 = Vector3.UP
var _apex: float = 0.0
var _floor_y: float = -INF
var _t: float = 0.0
var _seed: float = 0.0
var _light: SpotLight3D
var _core: MeshInstance3D
var _halo: MeshInstance3D
var _sparks: CPUParticles3D
var _core_mat: StandardMaterial3D
var _halo_mat: StandardMaterial3D


## Запуск из точки from по направлению dir (вверх, с небольшим уклоном по взгляду).
static func launch(parent: Node, from: Vector3, dir: Vector3) -> SkyFlare:
	var f := SkyFlare.new()
	f.name = "SkyFlare"
	f._from = from
	f._dir = dir.normalized() if dir.length_squared() > 0.0001 else Vector3.UP
	f._seed = fmod(absf(from.x * 12.9898 + from.z * 78.233), TAU)
	parent.add_child(f)
	return f


func _ready() -> void:
	var cfg: Dictionary = Balance.SKY_FLARE
	add_to_group("flares")
	add_to_group("sky_flares")
	global_position = _from
	# куда долетит: до вершины или до потолка над головой; где под вершиной земля
	var space: PhysicsDirectSpaceState3D = get_world_3d().direct_space_state
	var mask: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	_apex = float(cfg.rise_m)
	var up_hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(_from, _from + _dir * _apex, mask))
	if not up_hit.is_empty():
		_apex = maxf(0.3, _from.distance_to(up_hit.position) - 0.5)
	var top: Vector3 = _from + _dir * _apex
	var down_hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(top, top + Vector3.DOWN * 400.0, mask))
	_floor_y = float((down_hit.position as Vector3).y) + 0.15 if not down_hit.is_empty() else -INF
	var color: Color = cfg.color
	_light = SpotLight3D.new()
	_light.name = "Light"
	# свои настройки рассеяния — общее смягчение источников (Settings.soften) не нужно
	_light.set_meta("soft", true)
	_light.rotation.x = -PI * 0.5
	_light.light_color = color
	_light.light_energy = 0.0
	_light.spot_range = float(cfg.range)
	_light.spot_angle = float(cfg.angle)
	_light.spot_attenuation = float(cfg.attenuation)
	_light.spot_angle_attenuation = float(cfg.edge)
	_light.light_specular = 0.15
	_light.light_indirect_energy = float(cfg.indirect)
	_light.light_volumetric_fog_energy = float(cfg.fog)
	_light.shadow_enabled = true
	_light.shadow_blur = float(cfg.blur)
	_light.shadow_bias = 0.08
	_light.shadow_normal_bias = 1.5
	add_child(_light)
	# звезда и ореолы: не затеняются, смотрят в камеру
	_core_mat = _glow_material(Color(1.0, 0.82, 0.74))
	_core = _glow_quad(float(cfg.core_m), _core_mat)
	_halo_mat = _glow_material(color)
	_halo = _glow_quad(float(cfg.halo_m), _halo_mat)
	_sparks = CPUParticles3D.new()
	_sparks.name = "Sparks"
	_sparks.amount = 36
	_sparks.lifetime = 1.6
	_sparks.direction = Vector3.DOWN
	_sparks.spread = 28.0
	_sparks.gravity = Vector3(0.0, -1.6, 0.0)
	_sparks.initial_velocity_min = 0.6
	_sparks.initial_velocity_max = 2.4
	_sparks.scale_amount_min = 0.5
	_sparks.scale_amount_max = 1.0
	var spark := QuadMesh.new()
	spark.size = Vector2(0.22, 0.22)
	var spark_mat := _glow_material(Color(1.0, 0.5, 0.3))
	spark_mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	spark.material = spark_mat
	_sparks.mesh = spark
	_sparks.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_sparks)
	Audio.play("shot_pistol", _from, -2.0)
	Audio.play("flare_ignite", _from, -4.0)


## Радиус освещённого круга на земле, м (кто в нём на улице — виден издалека).
func radius() -> float:
	return float(Balance.SKY_FLARE.lit_radius)


## Сколько ещё гореть, с.
func time_left() -> float:
	return maxf(0.0, float(Balance.SKY_FLARE.air_sec) - _t)


func _process(delta: float) -> void:
	var cfg: Dictionary = Balance.SKY_FLARE
	_t += delta
	var air: float = float(cfg.air_sec)
	if _t >= air:
		queue_free()
		return
	global_position = position_at(_t)
	# разгорается на подъёме, горит неровно, к концу гаснет
	var burn: float = smoothstep(0.0, float(cfg.rise_sec) * 0.6, _t) * clampf((air - _t) / float(cfg.fade_sec), 0.0, 1.0)
	var flicker: float = 1.0 + 0.07 * sin(_t * 23.0 + _seed) + 0.05 * sin(_t * 41.0 + _seed * 2.0)
	_light.light_energy = float(cfg.energy) * burn * flicker
	_core_mat.albedo_color.a = burn
	_halo_mat.albedo_color.a = 0.55 * burn * flicker
	_sparks.emitting = burn > 0.2


## Где ракета через t секунд после выстрела.
func position_at(t: float) -> Vector3:
	var cfg: Dictionary = Balance.SKY_FLARE
	var rise: float = float(cfg.rise_sec)
	var top: Vector3 = _from + _dir * _apex
	if t <= rise:
		var k: float = 1.0 - t / rise
		return _from + _dir * _apex * (1.0 - k * k)
	var fall: float = t - rise
	# снос на спуске: плавное покачивание под парашютом
	var sway: Vector3 = Vector3(sin(fall * 0.55 + _seed), 0.0, cos(fall * 0.4 + _seed * 1.7)) * float(cfg.sway_m) * minf(1.0, fall / 3.0)
	var p: Vector3 = top + Vector3.DOWN * float(cfg.fall_speed) * fall + sway
	p.y = maxf(p.y, _floor_y)
	return p


func _glow_material(color: Color) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	m.albedo_color = color
	m.albedo_texture = _glow_texture()
	m.disable_fog = true
	return m


func _glow_quad(size_m: float, mat: StandardMaterial3D) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var q := QuadMesh.new()
	q.size = Vector2(size_m, size_m)
	mi.mesh = q
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.extra_cull_margin = size_m
	add_child(mi)
	return mi


static var _glow_tex: GradientTexture2D


## Мягкое круглое пятно: яркая середина, прозрачный край.
static func _glow_texture() -> GradientTexture2D:
	if _glow_tex == null:
		var g := Gradient.new()
		g.offsets = PackedFloat32Array([0.0, 0.18, 0.5, 1.0])
		g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0.12), Color(1, 1, 1, 0)])
		_glow_tex = GradientTexture2D.new()
		_glow_tex.gradient = g
		_glow_tex.fill = GradientTexture2D.FILL_RADIAL
		_glow_tex.fill_from = Vector2(0.5, 0.5)
		_glow_tex.fill_to = Vector2(1.0, 0.5)
		_glow_tex.width = 128
		_glow_tex.height = 128
	return _glow_tex
