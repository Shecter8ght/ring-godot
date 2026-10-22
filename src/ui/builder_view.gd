class_name BuilderView
extends SubViewportContainer
## 3D-студия конструктора оружия: свой мир, студийный свет, модель сборки в центре. Мышь: ЛКМ —
## вращать, колесо — ближе/дальше, ПКМ (или СКМ) — сдвинуть; виды «сбоку», «сверху», «из глаза»
## плавно. Даёт проекцию точек модели на экран (точки креплений, планки) и подкраску детали-призрака.

signal clicked(at: Vector2)
signal hovered(at: Vector2)
## Щелчок без протяжки правой или средней кнопкой (протяжка ими двигает модель).
signal alt_clicked(at: Vector2, button: int)

const VIEW_SIDE := Vector2(deg_to_rad(-90.0), deg_to_rad(6.0))
const VIEW_TOP := Vector2(deg_to_rad(-90.0), deg_to_rad(80.0))
const VIEW_Q := Vector2(deg_to_rad(-135.0), deg_to_rad(22.0))

var _vp: SubViewport
var _cam: Camera3D
var _pivot: Node3D
var _model: Node3D
## Внутренний узел модели (у оружия с масштабом основы — "Scaled"): оси данных.
var _space: Node3D
var _key: String = ""
var _weapon_id: String = ""
var _center: Vector3 = Vector3.ZERO
var _radius: float = 0.5
## Камера: рысканье, тангаж, расстояние (в радиусах модели), сдвиг цели.
var _yaw: float = VIEW_Q.x
var _pitch: float = VIEW_Q.y
var _dist: float = 2.4
var _pan: Vector3 = Vector3.ZERO
var _want: Vector4 = Vector4(VIEW_Q.x, VIEW_Q.y, 2.4, 0.0)
var _eye: bool = false
var _eye_xf: Transform3D
var _drag: int = 0
var _drag_from: Vector2
var _moved: bool = false
var _ghost: Material


func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	_vp = SubViewport.new()
	_vp.own_world_3d = true
	_vp.transparent_bg = true
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
	add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.42, 0.45, 0.5)
	env.ambient_light_energy = 0.55
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 1.15
	env.ssao_enabled = true
	env.ssao_radius = 0.06
	env.ssao_intensity = 1.2
	env.glow_enabled = true
	env.glow_intensity = 0.4
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	# студия: тёплый ключевой сверху-спереди, холодный контровой сзади, мягкий заполняющий снизу
	_light(Vector3(-42, -38, 0), Color(1.0, 0.92, 0.82), 2.3, true)
	_light(Vector3(-12, 150, 0), Color(0.62, 0.76, 1.0), 1.8, false)
	_light(Vector3(35, 60, 0), Color(0.9, 0.85, 0.8), 0.35, false)
	_pivot = Node3D.new()
	_vp.add_child(_pivot)
	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.near = 0.005
	_cam.far = 20.0
	_vp.add_child(_cam)
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.albedo_color = Color(0.4, 0.95, 0.55, 0.35)
	mat.no_depth_test = false
	_ghost = mat


func _light(rot: Vector3, color: Color, energy: float, shadow: bool) -> void:
	var l := DirectionalLight3D.new()
	l.rotation_degrees = rot
	l.light_color = color
	l.light_energy = energy
	l.shadow_enabled = shadow
	l.directional_shadow_max_distance = 3.0
	_vp.add_child(l)


## Показать сборку: пересобрать модель, если изменился вид (key). keep_frame — не перекадрировать
## (смена обвеса не дёргает камеру).
func show_build(weapon_id: String, mods: Dictionary, dur: float, mag: String, key: String, engraving: Dictionary = {}) -> void:
	if key == _key and _model:
		return
	var first: bool = _model == null or _weapon_id != weapon_id
	_weapon_id = weapon_id
	_key = key
	if _model:
		_model.queue_free()
	# вблизи — подробная модель (у ВЕРАСа мировая упрощена в 7 раз и ломается на крупном плане)
	_model = WeaponModels.build(weapon_id, mods, -1, dur, mag, engraving)
	_pivot.add_child(_model)
	for l: Node in _model.find_children("*", "Light3D", true, false):
		(l as Light3D).visible = false
	for b: Node in _model.find_children("LaserBeam*", "Node3D", true, false):
		(b as Node3D).visible = false
	_space = _model.find_child("Scaled", false, false) as Node3D
	if _space == null:
		_space = _model
	if first:
		var box: AABB = _bounds()
		_center = box.get_center()
		_radius = maxf(box.size.length() * 0.5, 0.1)


func model() -> Node3D:
	return _model


## Оси данных модели (сокеты, планки) — для WeaponMods.point_frame.
func space() -> Node3D:
	return _space


func _bounds() -> AABB:
	var out := AABB()
	var first := true
	for n: Node in _model.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null or not mi.visible or bool(mi.get_meta("weapon_clearance_ignore", false)):
			continue
		var b: AABB = _relative(mi) * mi.get_aabb()
		out = b if first else out.merge(b)
		first = false
	return out


func _relative(n: Node3D) -> Transform3D:
	var xf: Transform3D = n.transform
	var p: Node = n.get_parent()
	while p != null and p != _pivot:
		if p is Node3D:
			xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf


## Точка в осях данных модели → экран (координаты этого контрола); behind — за камерой.
func project(p: Vector3) -> Vector2:
	if _space == null or not _space.is_inside_tree():
		return size * 0.5
	var world: Vector3 = _space.global_transform * p
	var k: Vector2 = size / Vector2(_vp.size) if _vp.size.x > 0 else Vector2.ONE
	return _cam.unproject_position(world) * k


func behind(p: Vector3) -> bool:
	if _space == null or not _space.is_inside_tree():
		return false
	return _cam.is_position_behind(_space.global_transform * p)


## Подкрасить узел детали как призрак (ok — зелёный, иначе красный); null — убрать подкраску.
func tint(node: Node3D, ok: bool) -> void:
	if node == null:
		return
	var m := (_ghost as StandardMaterial3D).duplicate() as StandardMaterial3D
	m.albedo_color = Color(0.35, 0.95, 0.5, 0.42) if ok else Color(1.0, 0.32, 0.28, 0.5)
	for n: Node in node.find_children("*", "MeshInstance3D", true, false):
		(n as MeshInstance3D).material_overlay = m


func set_view(view: String, eye: Transform3D = Transform3D.IDENTITY) -> void:
	_eye = view == "eye"
	match view:
		"mark":
			_want = Vector4(PI, deg_to_rad(4.0), 4.5, 0.0)
		"mark_left":
			_want = Vector4(0.0, deg_to_rad(4.0), 4.5, 0.0)
		"side":
			_want = Vector4(VIEW_SIDE.x, VIEW_SIDE.y, 2.2, 0.0)
		"top":
			_want = Vector4(VIEW_TOP.x, VIEW_TOP.y, 2.2, 0.0)
		"eye":
			_eye_xf = eye
		_:
			_want = Vector4(VIEW_Q.x, VIEW_Q.y, 2.4, 0.0)
	if not _eye:
		_pan = Vector3.ZERO


## Приблизить к точке модели (оси данных; двойной клик по детали).
func focus(p: Vector3) -> void:
	_eye = false
	if _space and _space.is_inside_tree():
		_pan = _space.global_transform * p - _center
	_want.z = 1.1


func focus_mark(decal_name: String = "LaserMark") -> void:
	if _model == null:
		return
	var marks: Array[Node] = _model.find_children(decal_name, "Decal", true, false)
	if marks.is_empty():
		return
	var left: bool = (marks[0] as Node3D).basis.y.x > 0
	set_view("mark_left" if left else "mark")
	_pan = (marks[0] as Node3D).global_position - _center
	var pistol: bool = String(WeaponDb.weapon(_weapon_id).get("slot", "")) in ["sidearm", "launcher"]
	_want.z = (0.22 if pistol else 0.35) / _radius


func _process(delta: float) -> void:
	if _cam == null:
		return
	var k: float = 1.0 - exp(-delta * 9.0)
	if _drag == 0:
		_yaw = lerp_angle(_yaw, _want.x, k)
		_pitch = lerpf(_pitch, _want.y, k)
	_dist = lerpf(_dist, _want.z, k)
	# центр и сдвиг — в осях мира студии (модель стоит в начале без поворота)
	var world_target: Vector3 = _center + _pan
	var base: Transform3D = _space.global_transform if _space and _space.is_inside_tree() else Transform3D.IDENTITY
	if _eye:
		var want := Transform3D(base.basis.orthonormalized() * _eye_xf.basis, base * _eye_xf.origin)
		_cam.global_transform = _cam.global_transform.interpolate_with(want, k)
		_cam.fov = lerpf(_cam.fov, 42.0, k)
		return
	_cam.fov = lerpf(_cam.fov, 30.0, k)
	var dir := Vector3(cos(_pitch) * cos(_yaw), sin(_pitch), cos(_pitch) * sin(_yaw))
	_cam.global_position = world_target + dir * _radius * _dist
	_cam.look_at(world_target, Vector3.UP)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN] and mb.pressed and not mb.ctrl_pressed:
			if not get_meta("wheel_taken", false):
				_want.z = clampf(_want.z * (0.88 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else 1.14), 0.6, 5.0)
				accept_event()
			return
		if mb.pressed and mb.button_index in [MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE]:
			_drag = mb.button_index
			_drag_from = mb.position
			_moved = false
			if mb.double_click and mb.button_index == MOUSE_BUTTON_LEFT:
				_moved = true
		elif not mb.pressed and mb.button_index == _drag:
			if not _moved and _drag == MOUSE_BUTTON_LEFT:
				clicked.emit(mb.position)
			elif not _moved:
				alt_clicked.emit(mb.position, _drag)
			_drag = 0
			_want.x = _yaw
			_want.y = _pitch
	elif event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		hovered.emit(mm.position)
		if _drag == 0:
			return
		if mm.position.distance_to(_drag_from) > 4.0:
			_moved = true
		if not _moved:
			return
		_eye = false
		if _drag == MOUSE_BUTTON_LEFT:
			_yaw += mm.relative.x * 0.008
			_pitch = clampf(_pitch + mm.relative.y * 0.006, deg_to_rad(-80.0), deg_to_rad(85.0))
			_want.x = _yaw
			_want.y = _pitch
		else:
			var right: Vector3 = _cam.global_basis.x
			var up: Vector3 = _cam.global_basis.y
			_pan += (-right * mm.relative.x + up * mm.relative.y) * _radius * _dist * 0.0016
