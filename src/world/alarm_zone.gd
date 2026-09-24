class_name AlarmZone
extends Node3D
## Магазин на сигнализации: датчик мигает красным (видно, что охраняется); кто-то из игроков
## зашёл в радиус — воет сирена ALARM_SEC секунд и каждые несколько секунд «шумит» на всю округу
## (мародёры идут смотреть). Лут в таком магазине богаче. Срабатывает один раз. Ставит
## RaidEvents (или руками в сцене — radius в инспекторе). Проверку «зашёл» ведёт хост.

@export var radius: float = 6.0

var triggered: bool = false
var _led: MeshInstance3D
var _led_light: OmniLight3D
var _blink: float = 0.0
var _siren: AudioStreamPlayer3D
var _left: float = 0.0
var _noise_t: float = 0.0


func _ready() -> void:
	add_to_group("alarm_zones")
	var post := MeshInstance3D.new()
	var pm := BoxMesh.new()
	pm.size = Vector3(0.12, 0.18, 0.08)
	post.mesh = pm
	post.position = Vector3(0, 2.6, 0)
	var dark := StandardMaterial3D.new()
	dark.albedo_color = Color(0.9, 0.9, 0.88)
	post.material_override = dark
	add_child(post)
	_led = MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.025
	sm.height = 0.05
	_led.mesh = sm
	_led.position = Vector3(0, 2.6, 0.05)
	var lm := StandardMaterial3D.new()
	lm.albedo_color = Color(1, 0.1, 0.05)
	lm.emission_enabled = true
	lm.emission = Color(1, 0.1, 0.05)
	lm.emission_energy_multiplier = 4.0
	_led.material_override = lm
	add_child(_led)
	_led_light = OmniLight3D.new()
	_led_light.light_color = Color(1, 0.1, 0.05)
	_led_light.light_energy = 0.3
	_led_light.omni_range = 1.5
	_led_light.position = _led.position
	add_child(_led_light)


## Лут внутри богаче (LootContainer спрашивает при броске).
static func boosts(p: Vector3, tree: SceneTree) -> bool:
	for z in tree.get_nodes_in_group("alarm_zones"):
		var a := z as AlarmZone
		if a and a.global_position.distance_to(p) <= a.radius:
			return true
	return false


func _process(delta: float) -> void:
	_blink += delta
	var fast := _left > 0.0
	var on := fmod(_blink, 0.25 if fast else 1.2) < (0.12 if fast else 0.08)
	_led.visible = on
	_led_light.visible = on
	if _left > 0.0:
		_left -= delta
		if _left <= 0.0 and _siren:
			_siren.stop()
		if Net.is_networked() and not multiplayer.is_server():
			return
		_noise_t -= delta
		if _noise_t <= 0.0:
			_noise_t = 5.0
			NoiseBus.emit(global_position, float(Balance.RAID_EVENTS.alarm_noise_m), "alarm")
		return
	if triggered or (Net.is_networked() and not multiplayer.is_server()):
		return
	for n in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl and pl.is_alive() and pl.global_position.distance_to(global_position) <= radius:
			if Net.is_networked():
				_rpc_trigger.rpc()
			else:
				_rpc_trigger()
			return


@rpc("authority", "call_local", "reliable")
func _rpc_trigger() -> void:
	if triggered:
		return
	triggered = true
	_left = float(Balance.RAID_EVENTS.alarm_sec)
	_siren = AudioStreamPlayer3D.new()
	_siren.stream = Audio.siren_loop()
	_siren.unit_size = 25.0
	_siren.max_distance = 160.0
	_siren.volume_db = 2.0
	_siren.bus = &"World"
	_siren.position = Vector3(0, 2.6, 0)
	add_child(_siren)
	_siren.play()
	if Raid.current:
		Raid.current.notify("Сработала сигнализация!")
