class_name HandGripInspector
extends PanelContainer
## Вторая камера смотрит на те же самые игровые руки, а не на копию позы.

signal tip_drag_started(finger: String, point: Vector2)
signal tip_dragged(point: Vector2)
signal tip_depth_changed(amount: float)
signal tip_drag_finished(cancelled: bool)

var distance: float = 0.52
var yaw: float = 1.15
var pitch: float = 0.28
var view: SubViewport
var camera: Camera3D
var surface: SubViewportContainer
var _last_mode: int = -1
var _last_side: String = ""
var dragging: bool = false
var _tip_enabled: bool = false
var _tips: Dictionary = {}
var _handles = preload("res://src/debug/hand_finger_handles.gd").new()
var _hint: Label


func _ready() -> void:
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.06, 0.075, 0.09)
	style.border_color = Color(0.6, 0.65, 0.7, 0.5)
	style.set_border_width_all(1)
	style.set_content_margin_all(8)
	add_theme_stylebox_override("panel", style)
	var body: VBoxContainer = VBoxContainer.new()
	add_child(body)
	var hint: Label = Label.new()
	_hint = hint
	hint.text = "Осмотр хвата · ЛКМ — вращать · колесо — приблизить · F8 — вид из глаз"
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.add_theme_font_size_override("font_size", 17)
	body.add_child(hint)
	surface = SubViewportContainer.new()
	surface.stretch = true
	surface.size_flags_vertical = Control.SIZE_EXPAND_FILL
	surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	surface.mouse_filter = Control.MOUSE_FILTER_STOP
	body.add_child(surface)
	view = SubViewport.new()
	view.size = Vector2i(640, 480)
	view.world_3d = get_viewport().world_3d
	view.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	view.handle_input_locally = false
	view.gui_disable_input = true
	view.msaa_3d = Viewport.MSAA_2X
	surface.add_child(view)
	camera = Camera3D.new()
	camera.cull_mask = 2
	camera.near = 0.005
	camera.far = 5.0
	camera.fov = 38.0
	camera.environment = Environment.new()
	camera.environment.background_mode = Environment.BG_COLOR
	camera.environment.background_color = Color(0.075, 0.09, 0.11)
	camera.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	camera.environment.ambient_light_color = Color(0.72, 0.8, 1.0)
	camera.environment.ambient_light_energy = 1.5
	camera.environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	camera.attributes = CameraAttributesPractical.new()
	camera.attributes.exposure_multiplier = 1.7
	view.add_child(camera)
	camera.current = true
	_handles.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_handles.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	surface.add_child(_handles)
	surface.gui_input.connect(_orbit_input)


func focus_on(point: Vector3, weapon_basis: Basis, mode: int, side: String) -> void:
	if mode != _last_mode or side != _last_side:
		_last_mode = mode
		_last_side = side
		distance = 0.95 if mode == 2 else 0.52
		yaw = 1.15 if side == "Left" else -1.15
		pitch = 0.28
	var direction: Vector3 = Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch))
	camera.look_at_from_position(point + weapon_basis * direction * distance, point, weapon_basis.y)


func _orbit_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_LEFT:
			if not button.pressed and dragging:
				finish_drag(false)
				surface.accept_event()
				return
			if button.pressed and _tip_enabled:
				var picked: String = ""
				var nearest: float = 18.0
				for digit: String in _tips:
					var distance_px: float = button.position.distance_to(_tips[digit] as Vector2)
					if distance_px < nearest:
						picked = digit
						nearest = distance_px
				if not picked.is_empty():
					dragging = true
					tip_drag_started.emit(picked, _view_point(button.position))
					surface.accept_event()
					return
	if event is InputEventMouseMotion and dragging:
		tip_dragged.emit(_view_point((event as InputEventMouseMotion).position))
		surface.accept_event()
		return
	if event is InputEventMouseMotion and (event as InputEventMouseMotion).button_mask & (MOUSE_BUTTON_MASK_LEFT | MOUSE_BUTTON_MASK_RIGHT):
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		yaw -= motion.relative.x * 0.008
		pitch = clampf(pitch + motion.relative.y * 0.008, -1.4, 1.4)
		surface.accept_event()
	elif event is InputEventMouseButton and event.is_pressed():
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if dragging and mouse.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			tip_depth_changed.emit(0.002 if mouse.button_index == MOUSE_BUTTON_WHEEL_DOWN else -0.002)
			surface.accept_event()
			return
		if mouse.button_index == MOUSE_BUTTON_WHEEL_UP:
			distance = clampf(distance * 0.9, 0.08, 2.2)
		elif mouse.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			distance = clampf(distance / 0.9, 0.08, 2.2)
		surface.accept_event()


func _view_point(point: Vector2) -> Vector2:
	return point * Vector2(view.size) / surface.size.max(Vector2.ONE)


func project_point(point: Vector3) -> Vector2:
	return camera.unproject_position(point) * surface.size / Vector2(view.size)


func show_fingers(chains: Dictionary, selected: String, enabled: bool, target: Vector3 = Vector3.INF) -> void:
	_tip_enabled = enabled
	_handles.visible = enabled
	_tips.clear()
	if not enabled:
		_hint.text = "Осмотр хвата · ЛКМ — вращать · колесо — приблизить · F8 — вид из глаз"
		if dragging:
			finish_drag(false)
		return
	for digit: String in chains:
		var points: PackedVector3Array = chains[digit] as PackedVector3Array
		if points.size() == 4 and not camera.is_position_behind(points[3]):
			_tips[digit] = project_point(points[3])
	_handles.tips = _tips.duplicate()
	_handles.selected = selected
	var line: PackedVector2Array = []
	for point: Vector3 in chains.get(selected, PackedVector3Array()):
		line.append(project_point(point))
	_handles.chain = line
	_handles.target = project_point(target) if target.is_finite() else Vector2.INF
	_handles.queue_redraw()
	_hint.text = "Кончики: ЛКМ — вести · колесо при захвате — глубина · ПКМ / пустое место — осмотр · Esc — отменить"


func finish_drag(cancelled: bool) -> void:
	if dragging:
		dragging = false
		tip_drag_finished.emit(cancelled)
