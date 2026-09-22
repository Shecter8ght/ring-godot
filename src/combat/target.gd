class_name Target
extends StaticBody3D
## Мишень-«поппер»: стальной силуэт на петле у основания. Попадание откидывает его назад,
## пружина возвращает; в голову — заваливается и встаёт через паузу. Над точкой попадания
## всплывает урон. Для тренировки стрельбы: не стреляет, не ходит, не умирает.

signal hit(damage: float, head: bool)

@export var head_height: float = 1.55

var _swing: float = 0.0
var _swing_vel: float = 0.0
var _down_timer: float = 0.0
var _plate: Node3D
var _mat: StandardMaterial3D
var _flash: float = 0.0


func _ready() -> void:
	add_to_group("shootable")
	collision_layer = Hitscan.LAYER_MARAUDER
	collision_mask = 0
	_mat = StandardMaterial3D.new()
	_mat.albedo_color = Color(0.72, 0.7, 0.66)
	_mat.metallic = 0.6
	_mat.roughness = 0.45
	_mat.emission_enabled = true
	_mat.emission = Color(1.0, 0.55, 0.2)
	_mat.emission_energy_multiplier = 0.0
	var post_mat := StandardMaterial3D.new()
	post_mat.albedo_color = Color(0.18, 0.18, 0.19)
	post_mat.metallic = 0.7
	post_mat.roughness = 0.5
	_part(self, Vector3(0, 0.03, 0), Vector3(0.9, 0.06, 0.5), post_mat)
	# Плита качается на петле у основания — всё тело силуэта внутри _plate.
	_plate = Node3D.new()
	_plate.position = Vector3(0, 0.1, 0)
	add_child(_plate)
	_part(_plate, Vector3(0, 0.35, 0), Vector3(0.12, 0.5, 0.04), post_mat)
	_part(_plate, Vector3(0, 1.0, 0), Vector3(0.5, 0.8, 0.03), _mat)
	_part(_plate, Vector3(0, 1.45, 0), Vector3(0.3, 0.12, 0.03), _mat)
	var head := MeshInstance3D.new()
	var sph := CylinderMesh.new()
	sph.top_radius = 0.13
	sph.bottom_radius = 0.13
	sph.height = 0.03
	head.mesh = sph
	head.rotation.x = PI * 0.5
	head.position = Vector3(0, head_height - 0.1, 0)
	head.material_override = _mat
	_plate.add_child(head)
	# Коллайдер — по силуэту, неподвижный: попадания считаются по стоячей мишени.
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(0.5, 1.6, 0.2)
	cs.shape = box
	cs.position = Vector3(0, 0.95, 0)
	add_child(cs)


func _part(parent: Node3D, at: Vector3, size: Vector3, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)


## Зовёт Hitscan: точка попадания, направление пули, урон.
func on_hit(point: Vector3, dir: Vector3, damage: float) -> void:
	var head := point.y - global_position.y >= head_height - 0.25
	var dmg := damage * (Balance.TARGET_HEAD_MULT if head else 1.0)
	# Толчок — в сторону полёта пули относительно лица мишени (+Z узла).
	var side := signf(-dir.dot(global_basis.z)) if absf(dir.dot(global_basis.z)) > 0.05 else 1.0
	if head:
		_down_timer = Balance.TARGET_DOWN_SEC
		_swing_vel += side * -Balance.TARGET_KNOCK * 3.0
	else:
		_swing_vel += side * -Balance.TARGET_KNOCK
	_flash = 1.0
	_spawn_number(point, dmg, head)
	hit.emit(dmg, head)


func _physics_process(delta: float) -> void:
	var rest := 0.0
	if _down_timer > 0.0:
		_down_timer -= delta
		rest = -deg_to_rad(80.0) * signf(_swing if _swing != 0.0 else -1.0)
	# Пружина с затуханием к положению покоя.
	var acc := (rest - _swing) * Balance.TARGET_SPRING - _swing_vel * Balance.TARGET_DAMP
	_swing_vel += acc * delta
	_swing = clampf(_swing + _swing_vel * delta, -deg_to_rad(85.0), deg_to_rad(85.0))
	_plate.rotation.x = _swing
	_flash = maxf(0.0, _flash - delta * 6.0)
	_mat.emission_energy_multiplier = _flash * 2.5


## Всплывающая цифра урона: жёлтая по телу, красная и крупнее — в голову.
func _spawn_number(at: Vector3, dmg: float, head: bool) -> void:
	var l := Label3D.new()
	l.text = ("%d!" if head else "%d") % int(round(dmg))
	l.font_size = 72 if head else 52
	l.pixel_size = 0.01
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	l.shaded = false
	l.outline_size = 12
	l.modulate = Color(1.0, 0.25, 0.2) if head else Color(1.0, 0.9, 0.4)
	get_tree().current_scene.add_child(l)
	l.global_position = at + Vector3(randf_range(-0.15, 0.15), 0.2, 0)
	var tw := l.create_tween().set_parallel(true)
	tw.tween_property(l, "global_position:y", l.global_position.y + 1.0, 0.7).set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	tw.tween_property(l, "modulate:a", 0.0, 0.7).set_delay(0.25)
	tw.chain().tween_callback(l.queue_free)
