class_name WeaponPreview
extends SubViewportContainer
## Витрина ствола в окне: свой маленький мир (SubViewport), студийный свет, модель с обвесами
## медленно вращается. show_weapon — пересобрать, если сменилось оружие или обвесы.

var _vp: SubViewport
var _pivot: Node3D
var _model: Node3D
var _cam: Camera3D
var _key: String = ""


func _ready() -> void:
	stretch = true
	custom_minimum_size = Vector2(640, 300)
	_vp = SubViewport.new()
	_vp.own_world_3d = true
	_vp.transparent_bg = true
	_vp.msaa_3d = Viewport.MSAA_4X
	add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.45, 0.47, 0.52)
	env.ambient_light_energy = 0.6
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.1
	env.glow_enabled = true
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	# ключевой тёплый сверху-спереди, холодный контровой сзади, мягкий заполняющий снизу
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.9, 0.78)
	key.light_energy = 2.2
	key.rotation_degrees = Vector3(-38, -35, 0)
	_vp.add_child(key)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(0.6, 0.75, 1.0)
	rim.light_energy = 1.6
	rim.rotation_degrees = Vector3(-15, 150, 0)
	_vp.add_child(rim)
	var fill := OmniLight3D.new()
	fill.light_color = Color(1.0, 0.85, 0.7)
	fill.light_energy = 0.8
	fill.omni_range = 3.0
	fill.position = Vector3(0.4, -0.4, 0.6)
	_vp.add_child(fill)
	_pivot = Node3D.new()
	_vp.add_child(_pivot)
	_cam = Camera3D.new()
	_cam.fov = 28.0
	_cam.near = 0.01
	_vp.add_child(_cam)


func show_weapon(weapon_id: String, mods: Dictionary) -> void:
	var key := weapon_id + str(mods)
	if key == _key:
		return
	_key = key
	if _model:
		_model.queue_free()
		_model = null
	if weapon_id == "":
		return
	_model = WeaponModels.build(weapon_id, mods)
	_pivot.add_child(_model)
	# центр модели — в центр вращения; камера — по размеру
	var box := AABB()
	var first := true
	for mi in _model.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if not m.visible or m.name == "LaserBeam":
			continue
		var b := _relative(m) * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	_model.position = -box.get_center()
	var size := maxf(box.size.z, box.size.y * 2.0)
	_cam.position = Vector3(size * 1.02, size * 0.26, 0.0)
	_cam.look_at(Vector3.ZERO, Vector3.UP)


func _relative(n: Node3D) -> Transform3D:
	var xf := n.transform
	var p := n.get_parent()
	while p != null and p != _model:
		if p is Node3D:
			xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf


func _process(delta: float) -> void:
	if _pivot:
		_pivot.rotate_y(delta * 0.35)
