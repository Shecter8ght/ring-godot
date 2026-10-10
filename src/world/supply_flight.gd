extends Node3D
## Только изображение общего сигнала: время/место и груз считает Raid у хоста.
var _aircraft: Node3D
var _flare: GPUParticles3D
var _engine: AudioStreamPlayer3D
var _sound_started: bool = false


func _ready() -> void:
	if Raid.current != null and float(Raid.current.supply_state.get("elapsed", 0.0)) < 1.0:
		Audio.play("shot_pistol", Raid.current.supply_state.origin)
	# Без внешних ассетов сама доставка продолжает работать.
	var path: String = "res://assets/items/models/valuable/supply_aircraft.glb"
	_aircraft = (load(path) as PackedScene).instantiate() as Node3D if ResourceLoader.exists(path) else Node3D.new()
	add_child(_aircraft)
	_aircraft.visible = false
	_flare = GPUParticles3D.new()
	_flare.amount = 48
	_flare.lifetime = 1.2
	_flare.visibility_aabb = AABB(Vector3(-4, -70, -4), Vector3(8, 140, 8))
	var process: ParticleProcessMaterial = ParticleProcessMaterial.new()
	process.direction = Vector3.DOWN
	process.spread = 12.0
	process.initial_velocity_min = 1.0
	process.initial_velocity_max = 3.0
	process.gravity = Vector3(0, -2, 0)
	process.scale_min = 0.12
	process.scale_max = 0.3
	process.color = Color(1.0, 0.2, 0.05, 0.8)
	_flare.process_material = process
	var mesh: QuadMesh = QuadMesh.new()
	mesh.size = Vector2(0.4, 0.4)
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mesh.material = mat
	_flare.draw_pass_1 = mesh
	add_child(_flare)


func _process(_delta: float) -> void:
	if Raid.current == null or Raid.current.supply_state.is_empty():
		return
	var state: Dictionary = Raid.current.supply_state
	var spec: Dictionary = Balance.SUPPLY_SIGNAL
	var t: float = float(state.elapsed)
	_flare.global_position = state.origin + Vector3.UP * float(spec.flare_height) * clampf(t / float(spec.flare_sec), 0.0, 1.0)
	_flare.emitting = t < float(spec.flare_sec)
	var flight_t: float = t - (float(spec.delay) - float(spec.flight) * 0.5)
	_aircraft.visible = flight_t >= 0.0 and flight_t <= float(spec.flight)
	_aircraft.global_position = state.pos + Vector3((flight_t - float(spec.flight) * 0.5) * float(spec.speed), float(spec.altitude), 0)
	_aircraft.rotation.y = PI * 0.5
	if _aircraft.visible and not _sound_started:
		_sound_started = true
		_engine = Audio.start_loop("supply_plane", _aircraft)
	if not _aircraft.visible and _engine != null:
		_engine.queue_free()
		_engine = null
