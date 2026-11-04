extends Node3D
## Dedicated phone entry using the same hand controls and profile storage as the weapon lab.
var panel: HandGripPanel
var inspector: HandGripInspector
var draft: Dictionary = {}
var player: Player
var rig: CameraRig
var status: Label
var _editing_ready: bool = false

func _ready() -> void:
	draft = HandGripProfiles.snapshot()
	var env := WorldEnvironment.new(); env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.1, 0.13, 0.18)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.8
	add_child(env)
	var sun := DirectionalLight3D.new(); sun.rotation_degrees = Vector3(-45, -35, 0); add_child(sun)
	rig = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig; add_child(rig)
	player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(player); player.set_physics_process(false); player.health.invulnerable = true
	player.inventory.items = [ItemDb.make(PhoneGear.ID, 1)]
	rig.set_target(player); rig.first_person_mode = true
	for i: int in 20: await get_tree().process_frame
	Phone.set_active(true)
	if not Phone.active:
		push_error("Phone grip lab could not equip its preview")
		return
	Phone.preview = true
	add_to_group("esc_windows")
	var canvas := CanvasLayer.new(); canvas.layer = 30; add_child(canvas)
	var root := Control.new(); root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE; canvas.add_child(root)
	var scroll := ScrollContainer.new(); scroll.position = Vector2(12, 12)
	scroll.set_anchors_preset(Control.PRESET_LEFT_WIDE); scroll.offset_right = 480; scroll.offset_bottom = -12
	root.add_child(scroll)
	var column := VBoxContainer.new(); column.custom_minimum_size.x = 450; scroll.add_child(column)
	status = Label.new(); status.text = "Телефон · правый хват · @phone"; column.add_child(status)
	var save := Button.new(); save.text = "Сохранить хват · Ctrl+S"; save.pressed.connect(_save); column.add_child(save)
	var reset := Button.new(); reset.text = "Сбросить поправки телефона"; column.add_child(reset)
	reset.pressed.connect(func() -> void:
		HandGripProfiles.put(draft, "@phone", "Right", {}); panel.show_values(HandGripProfiles.values(draft, "@phone", "Right")))
	panel = HandGripPanel.new(); column.add_child(panel)
	panel.sides.select(1); panel.sides.set_item_disabled(0, true)
	panel.use_in_game.set_pressed_no_signal(HandGripProfiles.enabled())
	panel.show_values(HandGripProfiles.values(draft, "@phone", "Right"))
	panel.context.text = "Отдельный профиль @phone · остальные хваты не меняются"
	panel.values_changed.connect(func(value: Dictionary) -> void:
		HandGripProfiles.put(draft, "@phone", "Right", value); status.text = "Есть несохранённые изменения · Ctrl+S")
	panel.reset_requested.connect(func() -> void:
		HandGripProfiles.put(draft, "@phone", "Right", {}); panel.show_values(HandGripProfiles.values(draft, "@phone", "Right")))
	# Sliders and each joint are available; this stand does not expose weapon-specific transfer/IK actions.
	panel.copy_grip.disabled = true; panel.paste_grip.disabled = true
	panel.drag_tips.disabled = true; panel.undo_finger.disabled = true
	panel.views.select(1)
	inspector = HandGripInspector.new()
	inspector.set_anchors_preset(Control.PRESET_FULL_RECT)
	inspector.offset_left = 500; inspector.offset_top = 12; inspector.offset_right = -12; inspector.offset_bottom = -12
	root.add_child(inspector)
	process_priority = 110
	_editing_ready = true
	if "check" in OS.get_cmdline_user_args():
		await get_tree().process_frame
		print("PHONE GRIP LAB READY ", Phone.arms.skeleton != null)
		Phone.close(); Phone.preview = false
		get_tree().quit(0)

func is_open() -> bool:
	return _editing_ready

func _process(_delta: float) -> void:
	if not _editing_ready or not Phone.active: return
	Phone._hint.visible = false
	Phone.arms.grip_preview = true; Phone.arms.grip_profiles = draft
	inspector.visible = panel.views.selected != 0
	if inspector.visible:
		var sk := Phone.arms.skeleton
		var bone := sk.find_bone("mixamorig_RightHandMiddle1")
		inspector.focus_on(sk.to_global(sk.get_bone_global_pose(bone).origin), Phone.model.global_basis, panel.views.selected, "Right")
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _save() -> void:
	# Save only this key; HandGripProfiles merges all other profiles from disk and backs them up.
	var only := {"@phone": draft.get("@phone", {}).duplicate(true)}
	var result := HandGripProfiles.save_profiles(only, panel.use_in_game.button_pressed)
	status.text = "Сохранено: @phone · остальные хваты сохранены" if result == OK else "Ошибка сохранения: " + str(result)

func _input(event: InputEvent) -> void:
	if _editing_ready and event is InputEventKey and event.pressed and event.ctrl_pressed and event.physical_keycode == KEY_S:
		_save(); get_viewport().set_input_as_handled()

func _exit_tree() -> void:
	Phone.close(); Phone.preview = false
