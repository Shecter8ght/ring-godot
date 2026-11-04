extends Node
## Local personal device. Quest reports still go through Quests' authoritative field-link API.
const SCENE := preload("res://scenes/items/quest_phone.tscn")
const CAMERA_SIZE := Vector2i(720, 960)
const MAX_PHOTOS := 24
var active: bool = false
var pointer: bool = false
var actor: Player
var model: QuestPhoneModel
var holder: Node3D
var arms: FirstPersonArms
var screen_viewport: SubViewport
var finder: SubViewport
var lens: Camera3D
var screen_ui: PhoneScreen
var _camera: Camera3D
var _site: WeakRef
var _tick: float = 0.0
var _capture_busy: bool = false
var _photos: Array = []
var _profile: String = ""
var _hint: Label
var _shutter_t: float = 0.0
var _release_guard: bool = false
var _grip_data: Dictionary = {}
var thumb_error: float = 0.0
var preview: bool = false


func _ready() -> void:
	process_priority = 100
	add_to_group("quest_phone")
	add_to_group("esc_windows")
	Quests.changed.connect(_unlock)
	_unlock()
	var canvas := CanvasLayer.new(); canvas.layer = 16; add_child(canvas)
	_hint = Label.new(); _hint.position = Vector2(30, 100); _hint.visible = false
	_hint.add_theme_font_size_override("font_size", 20)
	canvas.add_child(_hint)


func _unlock() -> void:
	if Quests.state("car_recovery") in ["ACTIVE", "COMPLETED"]:
		Profile.ensure()
		Profile.flags[PhoneGear.FLAG] = true
		PhoneGear.ensure_profile()
		Profile.save()


func is_open() -> bool:
	return active and pointer


func close() -> void:
	set_active(false)


func blocks_combat(player: Player) -> bool:
	if actor != player: return false
	if active: return true
	if _release_guard:
		if not Input.is_action_pressed("fire") and not Input.is_action_pressed("aim"): _release_guard = false
		return true
	return false


func _process(delta: float) -> void:
	if not active:
		return
	if not is_instance_valid(actor) or not actor.is_alive() or actor.is_downed() or actor.on_ladder \
			or PauseMenu.shown or (Raid.current and Raid.current.ui_open()):
		set_active(false)
		return
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if rig == null or not is_instance_valid(_camera) or not _camera.current:
		set_active(false)
		return
	# CameraRig has already updated its normal viewmodel this frame.
	if is_instance_valid(rig._viewmodel): rig._viewmodel.visible = false
	if is_instance_valid(rig._arms): rig._arms.visible = false
	if is_instance_valid(rig._weapon_label): rig._weapon_label.visible = false
	if is_instance_valid(actor._weapon_model): actor._weapon_model.visible = false
	actor.aiming = false
	var reading := pointer or Input.is_action_pressed("aim")
	var target := Vector3(0.015, -0.01, -0.24) if reading else Vector3(0.10, -0.065, -0.36)
	holder.position = holder.position.lerp(target, 1.0 - exp(-delta * 14))
	# The second camera is at the actual rear lens; it shares the world's 3D state.
	var marker := model.find_child("CameraLensMarker", true, false) as Node3D
	lens.global_transform = Transform3D(model.global_basis.orthonormalized(), marker.global_position)
	_tick += delta
	if screen_ui.app == "Камера" and _tick >= 1.0 / 30.0:
		_tick = 0.0
		finder.render_target_update_mode = SubViewport.UPDATE_ONCE
	_shutter_t = maxf(0, _shutter_t - delta)
	var shutter_button := model.find_child("ButtonShutter", true, false) as Node3D
	if shutter_button:
		var rest: Vector3 = shutter_button.get_meta("phone_rest", shutter_button.position)
		shutter_button.set_meta("phone_rest", rest)
		shutter_button.position = rest + Vector3(-0.00016 if _shutter_t > 0 else 0, 0, 0)
	if arms:
		arms.global_transform = _camera.global_transform
		var editing := arms.grip_preview
		var original := arms.grip_profiles
		var profiles := original if editing else HandGripProfiles.active()
		var value := HandGripProfiles.values(profiles, "@phone", "Right")
		var wrists: Dictionary = {}
		HandGripProfiles.put(wrists, "@phone", "Right", {"position": value.position, "rotation": value.rotation})
		arms.grip_preview = true; arms.grip_profiles = wrists
		arms.update_pose()
		arms.grip_preview = editing; arms.grip_profiles = original
		for finger: String in _grip_data.get("back_contacts", {}):
			PhoneHandGrip.solve_finger(arms, finger, model.to_global(WeaponGrips.vector(_grip_data.back_contacts[finger])))
		var contact := WeaponGrips.vector(_grip_data.get("thumb_button", [0.043, -0.039, 0.001]))
		contact.x -= 0.00016 if _shutter_t > 0 else 0.0
		thumb_error = PhoneHandGrip.solve_thumb(arms, model.to_global(contact))
		arms._hand_pose.apply_fingers("Right", value, 1.0)


func _input(event: InputEvent) -> void:
	if preview: return
	if UiTheme.typing(): return
	if event.is_action_pressed("phone"):
		set_active(not active)
		get_viewport().set_input_as_handled()
		return
	if not active: return
	if event.is_action_pressed("pause"):
		if pointer: pointer = false
		else: set_active(false)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("inventory"):
		set_active(false)
	elif event.is_action_pressed("phone_screen"):
		pointer = not pointer
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if pointer else Input.MOUSE_MODE_CAPTURED
		_hint.text = hint_text()
		get_viewport().set_input_as_handled()
	elif pointer and (event is InputEventMouseButton or event is InputEventMouseMotion):
		_forward_pointer(event)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("fire"):
		capture()
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton:
		if event.pressed and event.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			_set_zoom(2.0 if event.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0)
		get_viewport().set_input_as_handled()


func set_active(on: bool) -> void:
	if on == active: return
	if on:
		var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
		var player := rig._target as Player if rig else null
		if player == null or not player.is_local() or not player.is_alive() or player.is_downed() \
				or player.ui_blocked() or player.on_ladder or not rig.ads_active:
			return
		if not player.inventory.has(PhoneGear.ID):
			Quests.notice.emit("Личный телефон выдаётся при принятии заказа Ильи в убежище.")
			return
		if player.reload_timer > 0 or not player._pm_action.is_empty() or player.grenade_equipped:
			return
		actor = player
		_camera = rig._ads_cam
		actor.cancel_weapon_action()
		if actor.handheld_flashlight: actor.handheld_flashlight.stow()
		_build()
		active = true
		actor.phone_equipped = true
		pointer = false
		_hint.visible = true
		_hint.text = hint_text()
	else:
		active = false; pointer = false; _site = null
		if is_instance_valid(actor): actor.phone_equipped = false
		_release_guard = true
		_hint.visible = false
		if is_instance_valid(actor) and is_instance_valid(actor._weapon_model): actor._weapon_model.visible = true
		var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
		if rig and is_instance_valid(rig._weapon_label): rig._weapon_label.visible = true
		for node: Node in [holder, screen_viewport, finder]:
			if is_instance_valid(node): node.queue_free()
		holder = null; screen_viewport = null; finder = null; arms = null; model = null
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED


func _build() -> void:
	finder = SubViewport.new(); finder.name = "PhoneViewfinder"
	finder.size = CAMERA_SIZE; finder.world_3d = _camera.get_world_3d()
	finder.render_target_update_mode = SubViewport.UPDATE_ONCE
	finder.msaa_3d = Viewport.MSAA_2X
	add_child(finder)
	lens = Camera3D.new(); lens.name = "RearPhoneCamera"; lens.fov = 60; lens.near = 0.035
	lens.cull_mask = _camera.cull_mask & ~2 & ~Player.OWN_BODY_LAYER & ~RainOcclusion.LAYER
	finder.add_child(lens); lens.make_current()
	if _camera.attributes: lens.attributes = _camera.attributes.duplicate()
	screen_viewport = SubViewport.new(); screen_viewport.name = "PhoneInterface"
	screen_viewport.size = PhoneScreen.RESOLUTION
	screen_viewport.disable_3d = true
	screen_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(screen_viewport)
	_load_photos()
	screen_ui = PhoneScreen.new(); screen_ui.viewfinder = finder.get_texture(); screen_ui.photos = _photos
	screen_ui.shutter.connect(capture); screen_ui.zoom_changed.connect(_set_zoom)
	screen_viewport.add_child(screen_ui)
	holder = Node3D.new(); holder.name = "PhoneInRightHand"; _camera.add_child(holder)
	holder.position = Vector3(0.11, -0.27, -0.36)
	model = SCENE.instantiate() as QuestPhoneModel; holder.add_child(model)
	model.show_screen(screen_viewport.get_texture())
	for raw: Node in model.find_children("*", "GeometryInstance3D", true, false):
		(raw as GeometryInstance3D).layers = 2
		(raw as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_build_grip()

func hint_text() -> String:
	return "%s — убрать телефон · %s — снимок · %s — ближе · %s — экран" % [PauseMenu.key_name("phone"), PauseMenu.key_name("fire"), PauseMenu.key_name("aim"), PauseMenu.key_name("phone_screen")]


func _build_grip() -> void:
	# An editable contact setup on the existing arms. Left hand is parked below the frame.
	_grip_data = JSON.parse_string(FileAccess.get_file_as_string("res://data/phone_grip.json")) as Dictionary
	var right := Node3D.new(); right.name = "RightGrip"; right.position = WeaponGrips.vector(_grip_data.right.position)
	right.rotation_degrees = WeaponGrips.vector(_grip_data.right.rotation_degrees)
	right.set_meta("curl", _grip_data.right.curl); right.set_meta("thumb_directions", [])
	right.set_meta("palm_offset", Vector3(0, 0.085, 0.01))
	model.add_child(right)
	var left := Node3D.new(); left.name = "LeftGrip"; left.position = WeaponGrips.vector(_grip_data.left_rest)
	left.set_meta("curl", [10.0, 10.0, 10.0]); left.set_meta("thumb_directions", [])
	left.set_meta("palm_offset", Vector3(0, 0.085, -0.01))
	model.add_child(left)
	model.set_meta("hand_grip_keys", {"Right": "@phone", "Left": "@phone"})
	arms = FirstPersonArms.new(); arms.name = "PhoneArms"; _camera.add_child(arms)
	arms.bind_weapon(model)
	# Own the arms through the holder so closing/reopening cannot leave orphan sleeves.
	arms.reparent(holder, true)


func _set_zoom(value: float) -> void:
	if not is_instance_valid(lens): return
	lens.fov = rad_to_deg(2.0 * atan(tan(deg_to_rad(60.0) / 2.0) / value))
	screen_ui.zoom = value
	if screen_ui.app == "Камера": screen_ui.refresh()


func frame_site(site: QuestSite) -> void:
	set_active(true)
	if active:
		_site = weakref(site)
		screen_ui.select("Камера")
		screen_ui.toast(String(site.spec.get("prompt", "Сделайте снимок")))


func capture() -> void:
	if not active or _capture_busy or screen_ui.app != "Камера": return
	_capture_busy = true
	var capture_view := finder
	finder.render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	if not active or not is_instance_valid(finder) or finder != capture_view: _capture_busy = false; return
	var image := finder.get_texture().get_image()
	var site := _site.get_ref() as QuestSite if _site else null
	var stamp := Time.get_datetime_string_from_system().replace("T", " ")
	var filename := "%d_%d.png" % [Time.get_unix_time_from_system(), Time.get_ticks_usec()]
	var path := _photo_dir() + "/" + filename
	if image.save_png(path) == OK:
		if is_instance_valid(site) and site.active and actor.global_position.distance_to(site.global_position) <= 5.0:
			site._done()
			_site = null
		_photos.push_front({"texture": ImageTexture.create_from_image(image), "file": filename, "time": stamp})
		while _photos.size() > MAX_PHOTOS:
			var old: Dictionary = _photos.pop_back()
			DirAccess.remove_absolute(_photo_dir() + "/" + String(old.file))
		_save_photo_index()
		screen_ui.photos = _photos
		_shutter_t = 0.13
		screen_ui.refresh(); screen_ui.toast("Снимок сохранён")
	else:
		screen_ui.toast("Не удалось сохранить снимок")
	_capture_busy = false


func _photo_dir() -> String:
	var id := Profile.profile_id if Profile.profile_id != "" else "local"
	return "user://phone/" + id.validate_filename()


func _load_photos() -> void:
	var directory := _photo_dir()
	if directory == _profile: return
	_profile = directory; _photos = []
	DirAccess.make_dir_recursive_absolute(directory)
	var index: Variant = JSON.parse_string(FileAccess.get_file_as_string(directory + "/index.json")) if FileAccess.file_exists(directory + "/index.json") else []
	if not index is Array: return
	for entry: Variant in index.slice(0, MAX_PHOTOS):
		if not entry is Dictionary: continue
		var filename := String(entry.get("file", ""))
		if filename != filename.get_file() or not filename.ends_with(".png"): continue
		var image := Image.load_from_file(directory + "/" + filename)
		if image and not image.is_empty():
			_photos.append({"texture": ImageTexture.create_from_image(image), "file": filename, "time": String(entry.get("time", ""))})


func _save_photo_index() -> void:
	var list: Array = []
	for photo: Dictionary in _photos: list.append({"file": photo.file, "time": photo.time})
	var file := FileAccess.open(_photo_dir() + "/index.json", FileAccess.WRITE)
	if file: file.store_string(JSON.stringify(list))


func _forward_pointer(event: InputEvent) -> void:
	var screen := model.screen
	if screen == null: return
	var inverse := screen.global_transform.affine_inverse()
	var origin := inverse * _camera.project_ray_origin(event.position)
	var direction := inverse.basis * _camera.project_ray_normal(event.position)
	var box := screen.get_aabb()
	if absf(direction.z) < 0.00001: return
	var t := (box.position.z - origin.z) / direction.z
	if t <= 0: return
	var point := origin + direction * t
	var uv := Vector2((point.x - box.position.x) / box.size.x, (box.end.y - point.y) / box.size.y)
	if not Rect2(Vector2.ZERO, Vector2.ONE).has_point(uv): return
	var forwarded := event.duplicate() as InputEvent
	forwarded.position = uv * Vector2(PhoneScreen.RESOLUTION)
	forwarded.global_position = forwarded.position
	screen_viewport.push_input(forwarded, true)
