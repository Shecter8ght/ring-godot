extends Node3D
## Детерминированные кадры настоящего Glock 17 Gen5, рук Persona и модели третьего лица.
## Запуск с окном: tools/godot.cmd --windowed --resolution 1280x720 res://tools/glock_shots.tscn
## Выбор кадров: после -- передать only=fp_hip,ads или группу only=model / only=hands / only=third.
## Снимки не имитируют интерфейс игры; позы оружия и ладоней берутся из игровых API и данных.

const WEAPON_ID: String = "wpn_hg_02"
const OUTPUT_DIR: String = "res://docs/screens"

var _camera: Camera3D
var _weapon: Node3D
var _rig: WeaponRig
var _arms: FirstPersonArms
## Как ViewmodelSpace у CameraRig: оружие и руки — со своим полем зрения (масштаб k, k, 1 у камеры).
var _vm_space: Node3D
var _player: Player
var _ground: MeshInstance3D
var _captures: Array[Dictionary] = []
var _only: PackedStringArray = []
var _failures: int = 0


func _ready() -> void:
	Engine.max_fps = 60
	if "compile" in OS.get_cmdline_user_args():
		print("glock_shots: компиляция с автозагрузками завершена")
		await _cleanup()
		get_tree().quit(0)
		return
	if DisplayServer.get_name() == "headless":
		push_error("glock_shots: снимки требуют запуска с окном и настоящим GPU, без --headless")
		get_tree().quit(1)
		return
	# Проект масштабирует внутренний viewport до 1920×1080; для стенда фиксируем и PNG.
	get_window().content_scale_size = Vector2i(1280, 720)
	get_window().size = Vector2i(1280, 720)
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("only="):
			_only = argument.trim_prefix("only=").split(",", false)
	_build_stage()
	_vm_space = Node3D.new()
	_vm_space.name = "ViewmodelSpace"
	add_child(_vm_space)
	_weapon = WeaponModels.build(WEAPON_ID)
	_vm_space.add_child(_weapon)
	_rig = WeaponRig.find_on(_weapon)
	if _rig == null or not bool(_weapon.get_meta("asset_loaded", false)) or not _rig.has_parts():
		push_error("glock_shots: нужен импортированный Glock со всеми деталями; запасная модель не является свидетельством проверки ассета")
		get_tree().quit(1)
		return
	_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	_vm_space.add_child(_arms)
	_arms.bind_weapon(_weapon)
	_rig.attach_arms(_arms)
	await _frames(8)
	if _arms.skeleton == null:
		push_error("glock_shots: нет импортированных рук Persona")
		get_tree().quit(1)
		return
	var config: Dictionary = WeaponDb.weapon(WEAPON_ID).get("rig", {}) as Dictionary
	var phases: Dictionary = config.get("reload", {}) as Dictionary
	var mag_out: float = lerpf(float(phases.get("mag_out", 0.22)), float(phases.get("mag_hidden", 0.34)), 0.65)
	var mag_in: float = float(phases.get("mag_in", 0.65))
	var charge: float = lerpf(float(phases.get("charge", 0.82)), float(phases.get("charge_end", 0.94)), 0.5)
	await _fp("fp_hip", false)
	await _fp("ads", true)
	await _fp("reload_partial_mag_out", false, "reload", mag_out)
	await _fp("reload_partial_mag_in", false, "reload", mag_in)
	await _fp("empty_locked", false, "", 0.0, true)
	await _fp("reload_empty_charge", false, "reload", charge, true)
	await _model("model_side", Vector3(-0.45, 0.035, 0.0))
	await _model("model_front", Vector3(0.065, 0.035, 0.44))
	await _model("model_back", Vector3(-0.035, 0.035, -0.40))
	await _model("model_bottom_open", Vector3(-0.07, -0.38, -0.12), true)
	await _hand("hand_right", "Right")
	await _hand("hand_left", "Left")
	if _wanted("third_person") or _wanted("third_person_detail") or _wanted("isometric"):
		await _third()
	var manifest: FileAccess = FileAccess.open(OUTPUT_DIR + "/glock_shots_manifest.json", FileAccess.WRITE)
	if manifest:
		manifest.store_string(JSON.stringify({"weapon": WEAPON_ID, "renderer": RenderingServer.get_current_rendering_method(), "captures": _captures, "failures": _failures}, "\t"))
	else:
		_failures += 1
		push_error("glock_shots: не удалось записать манифест")
	print("glock_shots: кадров %d, ошибок %d" % [_captures.size(), _failures])
	await _cleanup()
	get_tree().quit(1 if _failures > 0 else 0)


## Освобождение стенда завершает и последний dummy-audio playback в режиме compile.
func _cleanup() -> void:
	for sound: Node in Audio.get_children():
		if sound is AudioStreamPlayer:
			(sound as AudioStreamPlayer).stop()
			(sound as AudioStreamPlayer).stream = null
		elif sound is AudioStreamPlayer3D:
			(sound as AudioStreamPlayer3D).stop()
			(sound as AudioStreamPlayer3D).stream = null
	for child: Node in get_children():
		child.queue_free()
	await _frames(3)
	await get_tree().create_timer(0.12).timeout


func _build_stage() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))
	var world: WorldEnvironment = WorldEnvironment.new()
	var environment: Environment = Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.12, 0.15, 0.19)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.78, 0.85, 1.0)
	environment.ambient_light_energy = 0.55
	environment.tonemap_mode = Environment.TONE_MAPPER_ACES
	environment.ssao_enabled = true
	environment.ssao_radius = 0.035
	environment.glow_enabled = true
	world.environment = environment
	add_child(world)
	var key: DirectionalLight3D = DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-32, 42, 0)
	key.light_energy = 2.2
	key.light_color = Color(1.0, 0.92, 0.82)
	key.shadow_enabled = true
	add_child(key)
	var fill: DirectionalLight3D = DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-22, -115, 0)
	fill.light_energy = 1.2
	fill.light_color = Color(0.68, 0.80, 1.0)
	add_child(fill)
	var mesh: PlaneMesh = PlaneMesh.new()
	mesh.size = Vector2(40.0, 40.0)
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(0.20, 0.23, 0.26)
	material.roughness = 0.88
	_ground = MeshInstance3D.new()
	_ground.mesh = mesh
	_ground.material_override = material
	_ground.position.y = -1.5
	add_child(_ground)
	_camera = Camera3D.new()
	_camera.near = 0.005
	_camera.far = 100.0
	_camera.fov = Settings.fps_fov_v()
	add_child(_camera)
	_camera.current = true


## Те же позиции камеры и модели, что у CameraRig, без покачивания и отдачи.
func _fp(stage: String, ads: bool, action_name: String = "", progress: float = 0.0, empty: bool = false, suppressed: bool = false) -> void:
	if not _wanted(stage):
		return
	_reset()
	_rig.set_ammo_state(0 if empty else 5)
	_rig.set_suppressed(suppressed)
	if action_name != "":
		_rig.pose_action(action_name, progress, empty)
	_weapon.rotation.y = PI
	_weapon.position = Balance.FPS_HIP_POSE + _rig.view_offset()
	_weapon.basis *= Basis.from_euler(_rig.view_rotation_degrees() * (PI / 180.0))
	_camera.transform = Transform3D.IDENTITY
	_camera.near = 0.05
	_camera.fov = Settings.fps_fov_v()
	if ads:
		var height: float = float(_weapon.get_meta("sight_h", 0.0))
		var distance: float = float(_weapon.get_meta("ads_z", 0.36))
		_weapon.position = Vector3(0.0, -height, -distance)
	# камера в начале координат без поворота — оси камеры совпадают с осями сцены
	var vk: float = CameraRig.viewmodel_scale(_camera.fov)
	_vm_space.transform = Transform3D(Basis.from_scale(Vector3(vk, vk, 1.0)), Vector3.ZERO)
	_arms.set_hand_target("Left", _rig.get_hand_target(), _rig.get_hand_weight())
	_arms.update_pose()
	await _settle()
	await _capture(stage, {"view": "first_person", "action": action_name, "progress": progress, "empty": empty, "suppressed": suppressed, "ads": ads, "asset_lod": 0, "grip_error_m": _arms.max_grip_error, "arm_length_error_m": _arms.max_length_error})


func _model(stage: String, offset: Vector3, slide_open: bool = false) -> void:
	if not _wanted(stage):
		return
	_reset()
	_weapon.transform = Transform3D.IDENTITY
	_arms.visible = false
	_rig.set_ammo_state(0 if slide_open else 9)
	_camera.near = 0.005
	_camera.fov = 30.0
	var center: Vector3 = _bounds(_weapon).get_center()
	_camera.position = center + offset
	_camera.look_at(center)
	await _settle()
	await _capture(stage, {"view": "asset_diagnostic", "slide_open": slide_open, "asset_lod": 0})


func _hand(stage: String, side: String) -> void:
	if not _wanted(stage):
		return
	_reset()
	_weapon.rotation.y = PI
	_weapon.position = Balance.FPS_HIP_POSE
	_arms.update_pose()
	var marker: Node3D = _weapon.find_child(side + "Grip", true, false) as Node3D
	if marker == null:
		_failures += 1
		push_error("glock_shots: нет метки " + side + "Grip")
		return
	_camera.near = 0.005
	_camera.fov = 34.0
	_camera.position = marker.global_position + Vector3(0.22 if side == "Right" else -0.22, 0.035, 0.12)
	_camera.look_at(marker.global_position)
	await _settle()
	await _capture(stage, {"view": "hand_diagnostic", "side": side, "asset_lod": 0, "grip_error_m": _arms.max_grip_error, "arm_length_error_m": _arms.max_length_error})


## Полный Player с Persona, настоящим сокетом кости и веткой LOD1.
## Уровень не нужен: отключённая физика удерживает позу над отдельным тестовым полом.
func _third() -> void:
	_reset()
	_weapon.visible = false
	_arms.visible = false
	_ground.position.y = 0.0
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(_player)
	_player.set_physics_process(false)
	_player.set_process(false)
	_player.weapon_id = WEAPON_ID
	_player.weapon_rounds = 9
	_player.ammo = 9
	_player.aiming = true
	_player.combat_enabled = false
	_player._update_hand()
	var animator: CharacterAnimator = _player.get_node("CharacterAnimator") as CharacterAnimator
	animator.set_process(false)
	if not animator.has_model():
		_failures += 1
		push_error("glock_shots: аниматор Persona не готов")
		return
	animator.hold_pose("pistol_idle", 0.35)
	# Модификатор SupportHandIK обновляет реальную вторую кисть после клипа.
	if animator._support:
		animator._support.influence = 1.0
	await _settle()
	var third_rig: WeaponRig = WeaponRig.find_on(_player._weapon_model)
	if third_rig == null or int(_player._weapon_model.get_meta("asset_lod", -1)) != 1:
		_failures += 1
		push_error("glock_shots: у Player не загрузился Glock LOD1")
		return
	if _wanted("third_person"):
		_camera.near = 0.02
		_camera.fov = 38.0
		_camera.position = Vector3(-1.8, 1.35, 2.7)
		_camera.look_at(Vector3(0.0, 1.0, 0.1))
		await _settle()
		await _capture("third_person", {"view": "third_person", "character": "Player/Persona", "asset_lod": 1})
	if _wanted("third_person_detail"):
		var gun_at: Vector3 = _player._weapon_model.global_position
		_camera.near = 0.01
		_camera.fov = 34.0
		_camera.position = gun_at + Vector3(-0.70, 0.15, 0.85)
		_camera.look_at(gun_at)
		await _settle()
		await _capture("third_person_detail", {"view": "third_person_grip_diagnostic", "character": "Player/Persona", "asset_lod": 1})
	if _wanted("isometric"):
		# Стандартные углы изометрии игры; приближение помогает оценить компактный пистолет.
		var basis: Basis = Basis(Vector3.UP, deg_to_rad(Balance.CAMERA_YAW_DEG)) * Basis(Vector3.RIGHT, deg_to_rad(-Balance.CAMERA_PITCH_DEG))
		_camera.transform = Transform3D(basis, Vector3(0.0, 0.7, 0.0) + basis * Vector3(0.0, 0.0, Balance.CAMERA_ZOOM_MIN))
		_camera.near = 0.05
		_camera.fov = Balance.CAMERA_FOV
		await _settle()
		await _capture("isometric", {"view": "isometric", "character": "Player/Persona", "asset_lod": 1, "distance_m": Balance.CAMERA_ZOOM_MIN})
	_player.queue_free()
	await _frames(2)


func _reset() -> void:
	_vm_space.transform = Transform3D.IDENTITY
	_weapon.visible = true
	_weapon.transform = Transform3D.IDENTITY
	_rig.cancel_action()
	_rig.set_ammo_state(9)
	_rig.set_suppressed(false)
	_arms.set_hand_target("Left", null, 0.0)
	_ground.position.y = -1.5
	_camera.projection = Camera3D.PROJECTION_PERSPECTIVE


func _wanted(stage: String) -> bool:
	if _only.is_empty():
		return true
	if stage in _only:
		return true
	if "model" in _only and stage.begins_with("model_"):
		return true
	if "hands" in _only and stage.begins_with("hand_"):
		return true
	if "third" in _only and stage in ["third_person", "third_person_detail", "isometric"]:
		return true
	return false


func _bounds(root: Node3D) -> AABB:
	var bounds: AABB = AABB()
	var started: bool = false
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var instance: MeshInstance3D = node as MeshInstance3D
		if instance.mesh == null or not instance.is_visible_in_tree():
			continue
		var at: AABB = instance.global_transform * instance.get_aabb()
		bounds = bounds.merge(at) if started else at
		started = true
	return bounds


func _frames(count: int) -> void:
	for index: int in range(count):
		await get_tree().process_frame


func _settle() -> void:
	await _frames(8)
	await RenderingServer.frame_post_draw


func _capture(stage: String, details: Dictionary) -> void:
	# frame_post_draw нужен для настоящего GPU-кадра, headless dummy не даёт доказательства.
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	var path: String = OUTPUT_DIR + "/glock_" + stage + ".png"
	var error: Error = image.save_png(ProjectSettings.globalize_path(path))
	if error != OK:
		_failures += 1
		push_error("glock_shots: ошибка сохранения %s: %s" % [path, error_string(error)])
		return
	details["file"] = path
	details["camera_position"] = [_camera.position.x, _camera.position.y, _camera.position.z]
	details["camera_fov"] = _camera.fov
	details["resolution"] = [image.get_width(), image.get_height()]
	_captures.append(details)
	print("glock_shots: ", path)
