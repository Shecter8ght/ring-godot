class_name CameraRig
extends Node3D
## Камера. Обычно — изометрия: следует за локальным игроком, чуть уезжает к курсору, зум
## колесом, вращение Q/E или зажатой средней кнопкой мыши. Даёт игроку точку на земле под курсором.
## ПКМ — прицел от первого лица на весь экран: своя камера в глазах игрока, мышь захвачена и
## водит взглядом, WASD — как в шутере от первого лица, в руках — модель оружия, мушка по центру.
## У болтовки вместо модели — оптика: узкое поле зрения и прицельная сетка. HUD остаётся.

@export var target_path: NodePath

var ads_active: bool = false
var _distance: float = Balance.CAMERA_DISTANCE
var _target: Node3D
var _shake: float = 0.0
var _hitmarker: Control
var _hitmarker_t: float = 0.0
var _rng := RandomNumberGenerator.new()
var _mmb: bool = false
var _look_yaw: float = 0.0
var _look_pitch: float = 0.0
var _ads_cam: Camera3D
var _viewmodel: Node3D
var _viewmodel_id: String = ""
var _dot: Control
var _scope: Control
var _weapon_label: Label

@onready var _pivot: Node3D = $Pivot
@onready var _camera: Camera3D = $Pivot/Camera3D


func _ready() -> void:
	add_to_group("camera_rig")
	rotation_degrees.y = Balance.CAMERA_YAW_DEG
	_pivot.rotation_degrees.x = -Balance.CAMERA_PITCH_DEG
	_camera.fov = Balance.CAMERA_FOV
	if target_path != NodePath():
		_target = get_node(target_path)
	_ads_cam = Camera3D.new()
	_ads_cam.name = "AdsCamera"
	_ads_cam.top_level = true
	_ads_cam.near = 0.05
	_ads_cam.far = 400.0
	add_child(_ads_cam)
	_build_hud()


## Толчок камеры (выстрел, попадание по тебе, взрыв); складывается и затухает сам.
func add_shake(amount: float) -> void:
	_shake = minf(_shake + amount, 1.0)


## Крестик у курсора (в прицеле — по центру): попал; kill — крупнее и красный.
func show_hitmarker(kill: bool) -> void:
	_hitmarker_t = Balance.HITMARKER_SEC * (1.6 if kill else 1.0)
	_hitmarker.modulate = Color(1.0, 0.25, 0.2) if kill else Color(1, 1, 1)
	_hitmarker.scale = Vector2.ONE * (1.5 if kill else 1.0)


## Точка, из которой «смотрит» игрок: для силы тряски от взрыва и т.п.
func focus_point() -> Vector3:
	if ads_active:
		return _ads_cam.global_position
	return _target.global_position if _target else global_position


func set_target(node: Node3D) -> void:
	_target = node


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_MIDDLE:
			_mmb = mb.pressed
		elif mb.pressed and not ads_active:
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_distance = maxf(Balance.CAMERA_ZOOM_MIN, _distance - Balance.CAMERA_ZOOM_STEP)
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_distance = minf(Balance.CAMERA_ZOOM_MAX, _distance + Balance.CAMERA_ZOOM_STEP)
	elif event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		if ads_active:
			# вправо — поворот вправо; у оптики чувствительность меньше пропорционально полю зрения
			var sens := Balance.ADS_SENS * (_ads_cam.fov / 62.0)
			_look_yaw -= mm.relative.x * sens
			_look_pitch = clampf(_look_pitch - mm.relative.y * sens, -Balance.ADS_PITCH_LIMIT, Balance.ADS_PITCH_LIMIT)
		elif _mmb:
			rotation.y -= mm.relative.x * Balance.CAMERA_MMB_SENS


func _process(delta: float) -> void:
	if _target == null:
		_target = get_tree().get_first_node_in_group("players") as Node3D
		if _target == null:
			return
	var pl := _target as Player
	var want_ads := pl != null and pl.is_local() and pl.is_alive() and pl.aiming
	if want_ads != ads_active:
		_set_ads(want_ads, pl)
	_shake = maxf(0.0, _shake - Balance.SHAKE_DECAY * _shake * delta - 0.01 * delta)
	var s := _shake * _shake * 4.0
	_hitmarker_t -= delta
	_hitmarker.visible = _hitmarker_t > 0.0
	if ads_active:
		_process_ads(pl, delta, s)
		if _hitmarker.visible:
			_hitmarker.position = get_viewport().get_visible_rect().size * 0.5
	else:
		_process_iso(delta, s)
		if _hitmarker.visible:
			_hitmarker.position = get_viewport().get_mouse_position()
	_update_hud(pl)


func _process_iso(delta: float, s: float) -> void:
	# Вращение камеры вокруг игрока: Q/E, плавно, пока зажато (средняя кнопка — в _unhandled_input).
	var turn := Input.get_axis("camera_left", "camera_right")
	if turn != 0.0:
		rotation.y -= deg_to_rad(Balance.CAMERA_TURN_DEG_PER_SEC) * turn * delta
	_camera.position.z = lerpf(_camera.position.z, _distance, minf(1.0, 6.0 * delta))
	# Тряска — смещение камеры в её плоскости; квадрат силы, чтобы мелкие толчки были мягкими.
	_camera.position.x = _rng.randf_range(-s, s)
	_camera.position.y = _rng.randf_range(-s, s)
	SectorMaterials.set_cutaway_distance(_camera.position.z * Balance.CAMERA_CUTAWAY_NEAR, _camera.position.z * Balance.CAMERA_CUTAWAY_FAR)
	var cursor := cursor_on_ground()
	var lead := (cursor - _target.global_position) * Balance.CAMERA_CURSOR_LEAD
	lead.y = 0.0
	lead = lead.limit_length(Balance.CAMERA_CURSOR_LEAD_MAX)
	var want := _target.global_position + lead
	global_position = global_position.lerp(want, minf(1.0, Balance.CAMERA_FOLLOW_SMOOTH * delta))
	if _target is Player:
		var pl := _target as Player
		pl.cursor_ground = cursor
		pl.cursor_body = _body_under_cursor()


# ---------------------------------------------------------------- прицел от первого лица

func _set_ads(on: bool, pl: Player) -> void:
	ads_active = on
	if pl:
		pl.ads = on
		pl.set_first_person(on)
	if on:
		# взгляд — туда, куда уже смотрит корпус; по вертикали — горизонт
		_look_yaw = pl.body_yaw()
		_look_pitch = 0.0
		_ads_cam.fov = float(Balance.ADS_FOV.get(pl.weapon_id, 60.0)) + 8.0
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		_ads_cam.current = true
		# без выреза стен: из глаз игрока стены вокруг должны быть целыми
		SectorMaterials.set_cutaway_distance(0.0, 0.001)
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		_camera.current = true
		if _viewmodel:
			_viewmodel.visible = false
		# курсор — туда, куда смотрели: выход из прицела не сбивает направление
		if pl:
			var ahead := pl.global_position + Vector3(sin(_look_yaw), 0.0, cos(_look_yaw)) * 6.0
			Input.warp_mouse(_camera.unproject_position(ahead))
	_scope.visible = false
	_dot.visible = on


func _process_ads(pl: Player, delta: float, s: float) -> void:
	var wid := pl.weapon_id
	var scoped := wid == "bolt"
	var fov: float = Balance.ADS_FOV.get(wid, 60.0)
	_ads_cam.fov = lerpf(_ads_cam.fov, fov, minf(1.0, 14.0 * delta))
	# отдача подкидывает взгляд, дальше игрок сам возвращает прицел
	var pitch := _look_pitch + pl.recoil() * 0.6
	_ads_cam.global_transform = Transform3D(Basis.from_euler(Vector3(pitch, _look_yaw + PI, 0.0)), pl.eye_position())
	_ads_cam.global_position += _ads_cam.global_basis * Vector3(_rng.randf_range(-s, s), _rng.randf_range(-s, s), 0.0) * 0.15
	pl.look_yaw = _look_yaw
	pl.look_pitch = _look_pitch
	# модель в руках: линия прицеливания на оси взгляда, рукоять — на ads_z перед глазом
	if _viewmodel_id != wid:
		if _viewmodel:
			_viewmodel.queue_free()
		_viewmodel = WeaponModels.build(wid)
		for mi in _viewmodel.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if mi.has_meta("hide_ads"):
				mi.visible = false
		_ads_cam.add_child(_viewmodel)
		_viewmodel_id = wid
	_viewmodel.visible = not scoped
	var sh: float = _viewmodel.get_meta("sight_h", 0.08)
	var az: float = _viewmodel.get_meta("ads_z", 0.25)
	# камера смотрит по −Z, у модели дуло по +Z — разворот на π; отдача — подброс и откат назад
	_viewmodel.transform = Transform3D(Basis(Vector3.UP, PI).rotated(Vector3.RIGHT, pl.recoil() * 0.35),
		Vector3(0.0, -sh, -az + pl.recoil() * 0.12))
	_scope.visible = scoped
	_dot.visible = not scoped


## Дуло модели в руках (в прицеле) — отсюда трассер и вспышка.
func viewmodel_muzzle() -> Vector3:
	if _viewmodel and _viewmodel.visible:
		return _viewmodel.to_global(_viewmodel.get_meta("muzzle", Vector3.ZERO))
	return _ads_cam.global_position - _ads_cam.global_basis.z * 0.6 - _ads_cam.global_basis.y * 0.06


# ---------------------------------------------------------------- HUD камеры

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	# оптика: чёрная виньетка с прозрачным кругом и тонкой сеткой; поля по бокам — чёрные
	_scope = Control.new()
	_scope.set_anchors_preset(Control.PRESET_FULL_RECT)
	_scope.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scope.visible = false
	layer.add_child(_scope)
	var bg := ColorRect.new()
	bg.color = Color.BLACK
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scope.add_child(bg)
	var lens := TextureRect.new()
	lens.texture = _make_scope_texture(1024)
	lens.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	lens.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	lens.set_anchors_preset(Control.PRESET_FULL_RECT)
	lens.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scope.add_child(lens)
	# круг прозрачен только внутри линзы — фон вокруг закрываем маской по кругу
	bg.material = _scope_mask_material()
	# точка по центру в прицеле
	_dot = Control.new()
	_dot.set_anchors_preset(Control.PRESET_CENTER)
	_dot.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dot.visible = false
	var d := ColorRect.new()
	d.color = Color(1, 1, 1, 0.8)
	d.size = Vector2(3, 3)
	d.position = Vector2(-1.5, -1.5)
	d.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_dot.add_child(d)
	layer.add_child(_dot)
	_hitmarker = Control.new()
	_hitmarker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hitmarker.visible = false
	layer.add_child(_hitmarker)
	for ang in [45.0, 135.0, 225.0, 315.0]:
		var r := ColorRect.new()
		r.color = Color(1, 1, 1)
		r.size = Vector2(10, 2)
		r.position = Vector2(6, -1)
		r.pivot_offset = Vector2(-6, 1)
		r.rotation_degrees = ang
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_hitmarker.add_child(r)
	# оружие, патроны, гранаты — внизу справа
	_weapon_label = Label.new()
	_weapon_label.anchor_left = 1.0
	_weapon_label.anchor_right = 1.0
	_weapon_label.anchor_top = 1.0
	_weapon_label.anchor_bottom = 1.0
	_weapon_label.offset_left = -620.0
	_weapon_label.offset_right = -28.0
	_weapon_label.offset_top = -64.0
	_weapon_label.offset_bottom = -24.0
	_weapon_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_weapon_label.add_theme_font_size_override("font_size", 22)
	_weapon_label.add_theme_color_override("font_color", Color(0.92, 0.88, 0.78))
	_weapon_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	_weapon_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_weapon_label)


func _update_hud(pl: Player) -> void:
	if pl == null or not pl.is_local():
		_weapon_label.text = ""
		return
	var spec: Dictionary = Balance.WEAPONS[pl.weapon_id]
	var t := "%s   %d / %d" % [String(spec.name), pl.ammo, int(spec.mag)]
	if pl.reload_timer > 0.0:
		t = "%s   перезарядка…" % String(spec.name)
	_weapon_label.text = t + "      гранаты × %d" % pl.grenades


## Чёрный фон оптики с «дыркой» по кругу высоты экрана: шейдер режет круг по центру.
func _scope_mask_material() -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = """
shader_type canvas_item;
void fragment() {
	vec2 px = FRAGCOORD.xy - (1.0 / SCREEN_PIXEL_SIZE) * 0.5;
	float r = length(px) / ((1.0 / SCREEN_PIXEL_SIZE).y * 0.47);
	COLOR = vec4(0.0, 0.0, 0.0, smoothstep(0.96, 1.0, r));
}
"""
	var m := ShaderMaterial.new()
	m.shader = sh
	return m


## Прицельная сетка оптики: тонкие нити, к краям утолщаются; мягкая тень по краю линзы.
func _make_scope_texture(size: int) -> Texture2D:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var c := size * 0.5
	var rad := size * 0.5
	for y in range(size):
		for x in range(size):
			var dx := x - c
			var dy := y - c
			var r := sqrt(dx * dx + dy * dy)
			var a := clampf((r - rad * 0.8) / (rad * 0.2), 0.0, 1.0) * 0.55
			var col := Color(0, 0, 0, a)
			var ax := absf(dx)
			var ay := absf(dy)
			var thick := 0.8 if r < rad * 0.5 else 3.5
			if r < rad and ((ay <= thick and ax > 5.0) or (ax <= thick and ay > 5.0)):
				col = Color(0, 0, 0, 0.92)
			img.set_pixel(x, y, col)
	return ImageTexture.create_from_image(img)


# ---------------------------------------------------------------- лучи из курсора

## Тело под курсором (мародёр/мишень): луч из камеры сквозь курсор. Пусто — если под курсором пол/стена.
func _body_under_cursor() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * 200.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DOOR)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty() or not ((hit.collider as Node).is_in_group("marauders") or (hit.collider as Node).is_in_group("shootable")):
		return Vector3.ZERO
	return hit.position


## Пересечение луча из курсора с плоскостью пола игрока (y = высота цели).
func cursor_on_ground() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var plane := Plane(Vector3.UP, _target.global_position.y)
	var hit: Variant = plane.intersects_ray(from, dir)
	if hit == null:
		return _target.global_position
	return hit
