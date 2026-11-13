@tool
class_name MallGenerator
extends Interactable
## Дизель-генератор ТЦ — стоит на уровне всегда (узел в сцене, двигать руками; на 1F — мастерская,
## scenes/world/f1_mall_power.tscn). Работает — гудит, лампа на щитке зелёная. Встал (событие
## рейда «авария генератора» или условия «света нет» / «аварийный») — дымит, лампа мигает красным,
## гула нет; F — чинить (Balance.RAID_EVENTS.repair_sec на месте, громко лязгает — мародёры
## слышат). Починил — генератор снова даёт ток: весь свет, если главный рубильник поднят.
## Состояние — RaidEvents.generator_down (решает хост, знают все). Чинит хост.

@export var display_name: String = "Генератор ТЦ":
	set(v):
		display_name = v
		_rebuild()
## Где он — для сообщения «генератор встал, чинить — …».
@export var where: String = "в мастерской"

var _smoke: GPUParticles3D
var _hum: AudioStreamPlayer3D
var _lamp: MeshInstance3D
var _lamp_mat: StandardMaterial3D
var _repair_t: float = -1.0
var _repairer: int = 0
var _clank_t: float = 0.0
var _blink_t: float = 0.0


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	add_to_group("mall_generator")
	add_to_group("power_points")
	# корпус — препятствие для навмеша (мародёры обходят), пропсы кольца под него не ставятся
	add_to_group("nav_source")
	add_to_group("prop_keepout")
	var cfg: Dictionary = Balance.MALL_GENERATOR
	_smoke = RaidEvents._smoke(Color(0.2, 0.2, 0.22, 0.6))
	_smoke.position = Vector3(0.9, 2.4, 0.2)
	_smoke.emitting = false
	add_child(_smoke)
	_hum = AudioStreamPlayer3D.new()
	_hum.stream = Audio.hum_loop()
	_hum.volume_db = float(cfg.hum_db)
	_hum.unit_size = float(cfg.hum_unit_m)
	_hum.max_distance = float(cfg.hum_max_m)
	_hum.bus = &"World"
	_hum.position = Vector3(0, 1.0, 0)
	add_child(_hum)


## Прямоугольник XZ мира, где SectorBuilder не ставит пропсы (с проходом вокруг).
func keepout_rect() -> Rect2:
	var r := Rect2()
	var first := true
	for x in [-1.4, 1.4]:
		for z in [-0.65, 0.65]:
			var p := global_transform * Vector3(x, 0.0, z)
			if first:
				r = Rect2(Vector2(p.x, p.z), Vector2.ZERO)
				first = false
			else:
				r = r.expand(Vector2(p.x, p.z))
	return r.grow(float(Balance.MALL_GENERATOR.keepout_m))


func is_down() -> bool:
	return RaidEvents.current != null and RaidEvents.current.generator_down


func can_use() -> bool:
	return is_down() and _repair_t < 0.0


func prompt() -> String:
	return "%s: чинить (%.0f с, громко)" % [display_name, float(Balance.RAID_EVENTS.repair_sec)]


func _use(peer_id: int) -> void:
	_repair_t = 0.0
	_repairer = peer_id


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_show_state(delta)
	# ремонт считает хост
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
		_clank_t = float(Balance.MALL_GENERATOR.clank_sec)
		NoiseBus.emit(global_position, float(Balance.MALL_GENERATOR.clank_noise_m), "repair")
		if Net.is_networked():
			Net.broadcast_scene(self, &"_rpc_clank", [])
		else:
			_rpc_clank()
	if _repair_t >= float(Balance.RAID_EVENTS.repair_sec):
		_repair_t = -1.0
		if RaidEvents.current:
			RaidEvents.current.generator_fixed()


## Лязг ремонта слышат все, не только хост (чинить может и клиент).
@rpc("authority", "call_local", "unreliable")
func _rpc_clank() -> void:
	Audio.play("repair", global_position + Vector3.UP, 2.0)


## Дым, гул и лампа — по RaidEvents.generator_down у каждого peer.
func _show_state(delta: float) -> void:
	var down := is_down()
	_smoke.emitting = down
	if down == _hum.playing:
		if down:
			_hum.stop()
		else:
			Audio.play_world_loop(_hum)
	if _lamp_mat == null:
		return
	_blink_t += delta
	var on := not down or fmod(_blink_t * float(Balance.MALL_GENERATOR.blink_hz), 1.0) < 0.5
	var col := Color(0.3, 1.0, 0.4) if not down else Color(1.0, 0.15, 0.1)
	_lamp_mat.albedo_color = col if on else col * 0.15
	_lamp_mat.emission = col
	_lamp_mat.emission_energy_multiplier = 3.0 if on else 0.0


## Блокаут: рама, бак, кожух, радиатор с торца, щиток с лампой (лицом к -Z узла), выхлопная труба.
## Длинная ось — X узла. Коллизия — коробкой по габариту.
func _build_visual(parent: Node3D) -> void:
	var steel := Color(0.16, 0.17, 0.18)
	var paint := Color(0.33, 0.4, 0.27)
	_box(parent, Vector3(0, 0.075, 0), Vector3(2.8, 0.15, 1.3), steel)
	_box(parent, Vector3(0, 0.32, 0), Vector3(2.6, 0.34, 1.1), Color(0.22, 0.23, 0.22))
	_box(parent, Vector3(0, 1.12, 0), Vector3(2.6, 1.26, 1.1), paint)
	# радиатор: решётка на торце +X
	_box(parent, Vector3(1.31, 1.1, 0), Vector3(0.03, 0.95, 0.9), Color(0.1, 0.1, 0.1))
	for i in range(6):
		_box(parent, Vector3(1.33, 0.72 + 0.15 * i, 0), Vector3(0.02, 0.03, 0.88), Color(0.28, 0.29, 0.3))
	# жалюзи на длинной стороне
	for i in range(5):
		_box(parent, Vector3(0.1 + 0.22 * i, 1.35, -0.56), Vector3(0.12, 0.5, 0.02), Color(0.2, 0.24, 0.18))
	# щиток управления: коробка, табличка, лампа состояния
	_box(parent, Vector3(-0.85, 1.3, -0.58), Vector3(0.55, 0.5, 0.07), Color(0.25, 0.27, 0.26))
	_box(parent, Vector3(-0.85, 1.48, -0.62), Vector3(0.4, 0.08, 0.01), Color(0.9, 0.85, 0.2))
	_lamp = _box(parent, Vector3(-0.72, 1.24, -0.63), Vector3(0.09, 0.09, 0.03), Color(0.3, 1.0, 0.4), 3.0)
	_lamp_mat = _lamp.material_override as StandardMaterial3D
	_box(parent, Vector3(-0.98, 1.24, -0.63), Vector3(0.1, 0.1, 0.03), Color(0.7, 0.1, 0.08))
	# выхлоп: труба вверх над кожухом и колпак
	_box(parent, Vector3(0.9, 2.0, 0.2), Vector3(0.14, 0.6, 0.14), steel)
	_box(parent, Vector3(0.9, 2.33, 0.2), Vector3(0.22, 0.05, 0.22), steel)
	_label(parent, display_name, 2.7, Color(1.0, 0.85, 0.6), true)
	var body := StaticBody3D.new()
	body.collision_layer = Hitscan.LAYER_WORLD
	body.collision_mask = 0
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(2.8, 1.75, 1.3)
	cs.shape = shape
	cs.position = Vector3(0, 0.875, 0)
	body.add_child(cs)
	parent.add_child(body)
