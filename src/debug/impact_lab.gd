class_name ImpactLab
extends DevelopmentLab
## Все попадания проходят через игровой ImpactFx. Стекло — настоящий GlassPanes с трещинами.

const SURFACES: Array[String] = ["concrete", "metal", "wood", "glass", "tile", "asphalt", "cardboard", "fabric", "plastic", "grass", "dirt", "mud", "gravel", "snow"]
const NAMES: Array[String] = ["Бетон", "Металл", "Дерево", "Стекло", "Плитка", "Асфальт", "Картон", "Ткань", "Пластик", "Трава", "Земля", "Грязь", "Гравий", "Снег"]

var surface_index: int = 0
var sample: StaticBody3D
var glass: GlassPanes
var _label: Label3D
var _target: Vector3 = Vector3(0, 1.6, 2.85)
var _repeat: bool = false
var _repeat_time: float = 0.0
var _shots: int = 0
var _distance: float = 7.0
var _angle: float = 0.0
var _surface_choice: OptionButton
var _last_hit: String = "Нажми «Тестовое попадание» или F6 и стреляй сам."


func _ready() -> void:
	super._ready()
	_surface_choice = panel.option("Материал (каждый сохраняется отдельно)", NAMES, select_surface)
	panel.action("Тестовое попадание", hit)
	panel.toggle("Повторять попадание каждые 1,2 с", false, func(enabled: bool) -> void: _repeat = enabled)
	panel.action("Очистить следы / восстановить стекло", clear_effects)
	panel.number("Расстояние осмотра · м", _distance, 2.0, 18.0, 0.5, func(value: float) -> void:
		_distance = value
		_focus())
	panel.number("Угол осмотра / тестового выстрела · °", 0.0, -65.0, 65.0, 1.0, func(value: float) -> void:
		_angle = value
		_focus())
	weapon_selector()
	select_surface(0)


func select_surface(index: int) -> void:
	surface_index = index
	if is_instance_valid(_surface_choice):
		_surface_choice.select(index)
	set_domain("impact:" + SURFACES[index])
	clear_effects()
	var active: Dictionary = Balance.IMPACT_SURFACES[SURFACES[index]]
	panel.status.text = "Материал: %s. Доступные слои: %s." % [NAMES[index], ", ".join(active.keys())]
	for key: String in panel.fields:
		var layer: String = key.get_slice("_", 0)
		if layer in ["debris", "bits", "spray", "dust", "sparks"] and not active.has(layer):
			(panel.fields[key] as SpinBox).editable = false
			((panel.fields[key] as SpinBox).get_meta("slider") as HSlider).editable = false
			(panel.fields[key] as SpinBox).tooltip_text = "У этой поверхности такого слоя нет."


func clear_effects() -> void:
	for node: Node in get_tree().get_nodes_in_group("impact_effects"):
		if is_ancestor_of(node):
			node.queue_free()
	if is_instance_valid(sample):
		sample.queue_free()
	if is_instance_valid(glass):
		glass.queue_free()
	if is_instance_valid(_label):
		_label.queue_free()
	var kind: String = SURFACES[surface_index]
	var colors: Array[Color] = [Color(0.55,0.53,0.48), Color(0.3,0.35,0.4), Color(0.45,0.27,0.12), Color(0.6,0.8,0.85)]
	sample = box($Samples, "SurfaceSample", Vector3(0, 1.6, 3), Vector3(6, 3.2, 0.25), colors[mini(surface_index, 3)], kind)
	_target = Vector3(0, 1.6, 2.85)
	if kind in ["grass", "dirt", "mud", "gravel", "snow", "asphalt"]:
		sample.position = Vector3(0, 0.13, 3)
		sample.rotation.x = PI * 0.5
		_target = Vector3(0, 0.27, 3)
	if kind == "glass":
		sample.visible = false
		sample.collision_layer = 0
		glass = GlassPanes.new()
		glass.setup([{"xf": Transform3D(Basis.IDENTITY, Vector3(0, 1.6, 3)), "size": Vector2(5.5, 3), "floor_y": 0.0,
			"sill": Vector3(5.5, 0.1, 0.2), "tempered": false}])
		$Samples.add_child(glass)
		glass.get_node("Glass").set_meta("surface", "glass")
	_label = text_3d($Samples, NAMES[surface_index].to_upper(), Vector3(0, 3.7, 3))
	_focus()


func _focus() -> void:
	var angle: float = deg_to_rad(_angle)
	player.position = Vector3(-sin(angle) * _distance, 0.03, 3.0 - cos(angle) * _distance)
	player.velocity = Vector3.ZERO
	player._eye_tick_ready = false
	var direction: Vector3 = _target - player.eye_position()
	rig._look_yaw = atan2(direction.x, direction.z)
	rig._look_pitch = atan2(direction.y, Vector2(direction.x, direction.z).length())


func hit() -> void:
	var origin: Vector3 = rig._ads_cam.global_position
	var direction: Vector3 = (_target - origin).normalized()
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, origin + direction * 100.0,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_GLASS, [player.get_rid()])
	var result: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	if result.is_empty():
		_last_hit = "Луч не встретил образец. Восстанови образец кнопкой очистки."
		return
	var kind: String = Surfaces.kind_at(result)
	if kind == "glass" and is_instance_valid(glass):
		glass.bullet(int(result.get("shape", 0)), 18.0, result.position, direction)
	ImpactFx.spawn_hit(result, direction)
	_shots += 1
	_last_hit = "Попадание №%d · поверхность: %s" % [_shots, kind]


func _lab_tick(delta: float) -> void:
	if _repeat:
		_repeat_time -= delta
		if _repeat_time <= 0.0:
			_repeat_time = 1.2
			hit()
	var effects: int = 0
	for node: Node in get_tree().get_nodes_in_group("impact_effects"):
		if is_ancestor_of(node):
			effects += 1
	telemetry.text = "ПОПАДАНИЯ И ЭФФЕКТЫ\n%s\nЖивых эффектов / следов: %d\n%s\nИзменения видны со следующего попадания.\nСтекло: настоящие трещины; очистка возвращает целую панель." % [
		_last_hit, effects, "СРАВНЕНИЕ: исходные параметры" if panel.compare.button_pressed else "Материал: " + NAMES[surface_index]]
