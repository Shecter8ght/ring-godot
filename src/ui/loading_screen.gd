extends CanvasLayer
## Общий экран перехода живёт вне уровня: старую сцену можно удалить, а новую — готовить по этапам.

signal stage_changed(text: String, percent: float)

var active: bool = false
var progress: float = 0.0
var stage_text: String = ""
var _began_ms: int = 0
var _mouse_before: Input.MouseMode = Input.MOUSE_MODE_VISIBLE
var _scene_modes: Dictionary = {}

@onready var _title: Label = $Root/Center/Content/Title
@onready var _status: Label = $Root/Center/Content/StatusRow/Status
@onready var _percent: Label = $Root/Center/Content/StatusRow/Percent
@onready var _bar: ProgressBar = $Root/Center/Content/Progress
@onready var _elapsed: Label = $Root/Center/Content/Elapsed
@onready var _back: Button = $Root/Center/Content/Back


func _ready() -> void:
	add_to_group("esc_windows")
	_back.pressed.connect(dismiss)
	hide()


func is_open() -> bool:
	return visible


func begin(title: String) -> void:
	if visible:
		dismiss()
	_mouse_before = Input.mouse_mode
	active = true
	progress = 0.0
	_began_ms = Time.get_ticks_msec()
	_title.text = title
	_elapsed.text = "Прошло 00:00"
	_back.hide()
	show()
	hold_scene(get_tree().current_scene)
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	report("Подготовка", 0.0)


## Мир и его ввод стоят во время загрузки; автозагрузки и ENet продолжают работать.
func hold_scene(scene: Node) -> void:
	if not active or not is_instance_valid(scene) or _scene_modes.has(scene):
		return
	_scene_modes[scene] = scene.process_mode
	scene.process_mode = Node.PROCESS_MODE_DISABLED


func report(text: String, percent: float) -> void:
	if not active:
		return
	stage_text = text
	progress = maxf(progress, clampf(percent, 0.0, 100.0))
	_bar.value = progress
	_percent.text = "%d %%" % int(progress)
	_status.text = stage_text
	stage_changed.emit(stage_text, progress)


## Отрисовать подпись ДО тяжёлой работы, включая создание сцены и моделей оружия.
func stage(text: String, percent: float) -> void:
	if not active:
		return
	report(text, percent)
	await get_tree().process_frame
	if DisplayServer.get_name() == "headless":
		await get_tree().process_frame
	else:
		await RenderingServer.frame_post_draw


func finish() -> void:
	dismiss()
	var rig: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if rig != null and rig.ads_active else Input.MOUSE_MODE_VISIBLE


func fail(text: String) -> void:
	active = false
	_title.text = "Загрузка не завершена"
	_status.text = text
	_elapsed.text = "Попробуйте ещё раз."
	_back.show()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func dismiss() -> void:
	active = false
	hide()
	for scene: Variant in _scene_modes:
		if is_instance_valid(scene):
			(scene as Node).process_mode = int(_scene_modes[scene]) as Node.ProcessMode
	_scene_modes.clear()
	Input.mouse_mode = _mouse_before


func _process(_delta: float) -> void:
	if not active:
		return
	var ms: int = Time.get_ticks_msec() - _began_ms
	_status.text = stage_text + ".".repeat((ms / 450) % 4)
	var seconds: int = ms / 1000
	_elapsed.text = "Прошло %02d:%02d" % [seconds / 60, seconds % 60]


func _input(event: InputEvent) -> void:
	if not visible:
		return
	if active:
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("pause"):
		dismiss()
		get_viewport().set_input_as_handled()
