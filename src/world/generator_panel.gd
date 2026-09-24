class_name GeneratorPanel
extends Interactable
## Генератор встал (событие рейда): дым и гул; F — чинить (REPAIR_SEC на месте, громко лязгает —
## мародёры слышат). Починил — свет в ТЦ вернулся у всех. Ставит RaidEvents. Чинит хост.

var _smoke: GPUParticles3D
var _hum: AudioStreamPlayer3D
var _repair_t: float = -1.0
var _repairer: int = 0
var _clank_t: float = 0.0


func _ready() -> void:
	super._ready()
	_smoke = RaidEvents._smoke(Color(0.25, 0.25, 0.27, 0.55))
	add_child(_smoke)
	_smoke.position = Vector3(0, 2.0, 0)
	_hum = AudioStreamPlayer3D.new()
	_hum.stream = Audio.hum_loop()
	_hum.unit_size = 6.0
	_hum.max_distance = 45.0
	_hum.bus = &"World"
	add_child(_hum)
	_hum.play()


func _build_visual(parent: Node3D) -> void:
	var box := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1.6, 1.4, 1.0)
	box.mesh = bm
	box.position = Vector3(0, 0.7, 0)
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.3, 0.38, 0.28)
	m.metallic = 0.4
	m.roughness = 0.6
	box.material_override = m
	parent.add_child(box)


func can_use() -> bool:
	return _repair_t < 0.0


func prompt() -> String:
	return "чинить генератор (%.0f с, громко)" % Balance.RAID_EVENTS.repair_sec


func _use(peer_id: int) -> void:
	_repair_t = 0.0
	_repairer = peer_id


func _process(delta: float) -> void:
	if _repair_t < 0.0 or (Net.is_networked() and not multiplayer.is_server()):
		return
	var pl := Raid.current.player_of(_repairer) if Raid.current else null
	# отошёл — сначала
	if pl == null or pl.global_position.distance_to(global_position) > Balance.INTERACT_RADIUS + 1.5:
		_repair_t = -1.0
		return
	_repair_t += delta
	_clank_t -= delta
	if _clank_t <= 0.0:
		_clank_t = 1.2
		Audio.play("impact_metal", global_position, 2.0)
		NoiseBus.emit(global_position, 45.0, "repair")
	if _repair_t >= float(Balance.RAID_EVENTS.repair_sec):
		_repair_t = -1.0
		if RaidEvents.current:
			RaidEvents.current.generator_fixed()
