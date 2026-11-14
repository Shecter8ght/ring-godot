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
var _vm: ViewmodelClips


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
	await _clip_shots()
	# прежние процедурные руки на риге модели (запасной вид, если файла клипов нет) — только по only=rig
	var config: Dictionary = WeaponDb.weapon(WEAPON_ID).get("rig", {}) as Dictionary
	var phases: Dictionary = config.get("reload", {}) as Dictionary
	var mag_out: float = lerpf(float(phases.get("mag_out", 0.22)), float(phases.get("mag_hidden", 0.34)), 0.65)
	var mag_in: float = float(phases.get("mag_in", 0.65))
	var charge: float = lerpf(float(phases.get("charge", 0.82)), float(phases.get("charge_end", 0.94)), 0.5)
	await _fp("rig_fp_hip", false)
	await _fp("rig_ads", true)
	await _fp("rig_reload_partial_mag_out", false, "reload", mag_out)
	await _fp("rig_reload_partial_mag_in", false, "reload", mag_in)
	# обойма из окна рюкзака: «вынуть» (середина и конец — рука уходит без магазина) и «вставить»
	await _fp("rig_hand_mag_out", false, "reload:out", 0.55)
	await _fp("rig_hand_mag_out_end", false, "reload:out", 0.9)
	await _fp("rig_hand_mag_in", false, "reload:in", 0.35)
	await _fp("rig_empty_locked", false, "", 0.0, true)
	await _fp("rig_reload_empty_charge", false, "reload", charge, true)
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


## Клипы рук владельца (ViewmodelClips, tools/asten919/clips/export_viewmodel.py) — как в игре: сцена в осях камеры,
## у бедра поза из Blender, в прицеле линия прицеливания на оси взгляда. Кадры фаз — метки клипов из отчёта вывода.
func _clip_shots() -> void:
	var report: Dictionary = {}
	var text: String = FileAccess.get_file_as_string("res://assets/models/weapons/asten919/asten919_viewmodel.json")
	if text != "":
		report = JSON.parse_string(text) as Dictionary
	var clips: Dictionary = report.get("clips", {}) as Dictionary
	if not ViewmodelClips.available(WEAPON_ID) or clips.is_empty():
		_failures += 1
		push_error("glock_shots: нет клипов рук АСТЕН-919 (export_viewmodel.py) или их отчёта")
		return
	_weapon.visible = false
	_arms.visible = false
	_vm = ViewmodelClips.create(WEAPON_ID, {})
	# клипы, у которых в игре пока нет случая, — на просмотр отдельными ролями этого экземпляра
	_vm.config = _vm.config.duplicate(true)
	for spare: String in ["reload_full_rack", "slide_rack", "finger_to_trigger"]:
		(_vm.config.clips as Dictionary)[spare] = spare
	_vm_space.add_child(_vm)
	var at := func(clip: String, mark: String, shift: float = 0.0) -> float:
		var c: Dictionary = clips.get(clip, {}) as Dictionary
		var m: Dictionary = c.get("marks", {}) as Dictionary
		return clampf((float(m.get(mark, 0)) + shift) / maxf(float(c.get("frames", 1)), 1.0), 0.0, 1.0)
	var mid := func(clip: String, a: String, b: String) -> float:
		return lerpf(at.call(clip, a), at.call(clip, b), 0.5)
	await _clip("clip_hip", "idle", 0.0)
	await _clip("clip_ads", "idle", 0.0, true)
	await _clip("clip_reload_tactical_catch", "reload", at.call("reload_tactical", "catch"))
	await _clip("clip_reload_tactical_out", "reload", at.call("reload_tactical", "mag_out"))
	await _clip("clip_reload_tactical_new", "reload", mid.call("reload_tactical", "mag_new", "insert"))
	await _clip("clip_reload_tactical_insert", "reload", at.call("reload_tactical", "insert"))
	await _clip("clip_reload_tactical_seat", "reload", at.call("reload_tactical", "seat"))
	await _clip("clip_reload_full_start", "reload_empty", at.call("reload_full", "catch"))
	await _clip("clip_reload_full_insert", "reload_empty", at.call("reload_full", "insert"))
	await _clip("clip_reload_full_release", "reload_empty", at.call("reload_full", "slide_release"))
	await _clip("clip_reload_fast_flick", "reload_fast", at.call("reload_fast", "flick"))
	await _clip("clip_reload_fast_insert", "reload_fast", at.call("reload_fast", "insert"))
	await _clip("clip_reload_fast_full_release", "reload_fast_empty", at.call("reload_fast_full", "slide_release"))
	await _clip("clip_check_hold", "check", mid.call("mag_check", "hold_start", "hold_end"))
	await _clip("clip_inspect_left", "inspect", mid.call("inspect", "left_side_start", "left_side_end"))
	await _clip("clip_inspect_right", "inspect", mid.call("inspect", "right_side_start", "right_side_end"))
	await _clip("clip_jam_pull", "clear", at.call("jam_clear", "pull"))
	await _clip("clip_fire_press", "shot", at.call("fire", "press"))
	await _clip("clip_fire_slide", "shot", at.call("fire", "slide_back"))
	await _clip("clip_empty_locked", "idle", 0.0, false, "held")
	await _clip("clip_jammed", "idle", 0.0, false, "jam")
	await _clip("clip_spare_full_rack_pull", "reload_full_rack", at.call("reload_full_rack", "rack_pull"))
	await _clip("clip_spare_slide_rack", "slide_rack", at.call("slide_rack", "pull"))
	await _clip("clip_spare_finger_trigger", "finger_to_trigger", 1.0)
	await _hand_mag_clips()
	await _locked_reload_clips()
	await _slide_closeup()
	_vm.queue_free()
	_vm = null
	if _wanted("clip_suppressor"):
		var sup: ViewmodelClips = ViewmodelClips.create(WEAPON_ID, {"muzzle": {"id": "muzzle_supp_9_01"}})
		_vm_space.add_child(sup)
		_vm = sup
		await _clip("clip_suppressor", "idle", 0.0)
		await _clip("clip_suppressor_ads", "idle", 0.0, true)
		sup.queue_free()
		_vm = null
	_weapon.visible = true
	_arms.visible = true


func _clip(stage: String, role: String, fraction: float, ads: bool = false, state: String = "") -> void:
	if not _wanted(stage) or _vm == null:
		return
	_ground.position.y = -1.5
	_camera.transform = Transform3D.IDENTITY
	_camera.near = 0.05
	_camera.fov = Settings.fps_fov_v()
	var vk: float = CameraRig.viewmodel_scale(_camera.fov)
	_vm_space.transform = Transform3D(Basis.from_scale(Vector3(vk, vk, 1.0)), Vector3.ZERO)
	_vm.preview_reload(role, fraction, "*")
	if state == "held":
		_vm._pose_overrides(0, 0.0, false, true)
	elif state == "jam":
		_vm._pose_overrides(8, 0.0, true, false)
		if _vm._jam_case:
			_vm._jam_case.visible = true
	_vm.transform = _vm.ads_transform() if ads else _vm.hip_transform()
	await _settle()
	await _capture(stage, {"view": "first_person_clips", "role": role, "clip": _vm._clip_name(role), "fraction": fraction, "ads": ads, "state": state})


## «Вынуть / вставить обойму» из окна рюкзака у пистолета с патронником: игрок шлёт действия mag_out / mag_in (как
## риг модели), клипы рук ведёт ViewmodelClips.update по настоящему Player (без уровня и физики).
func _hand_mag_clips() -> void:
	if not (_wanted("clip_hand_mag_out") or _wanted("clip_hand_mag_out_end") or _wanted("clip_hand_mag_in")):
		return
	var pl: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(pl)
	pl.set_physics_process(false)
	pl.set_process(false)
	pl.visible = false
	pl.combat_enabled = false
	pl.weapon_id = WEAPON_ID
	pl.weapon_mag = "*"
	pl.ammo = 18
	_vm.equip()
	var step := func(seconds: float) -> void:
		var t: float = 0.0
		while t < seconds:
			_vm.update(pl, 1.0 / 60.0)
			t += 1.0 / 60.0
	_vm.weapon_action("mag_out", false, 1.0)
	step.call(0.55)
	await _clip_live("clip_hand_mag_out")
	step.call(0.4)
	await _clip_live("clip_hand_mag_out_end")
	step.call(0.4)
	pl.weapon_mag = ""
	pl.ammo = 1
	step.call(0.8)
	_vm.weapon_action("mag_in", false, 1.2)
	step.call(0.45)
	await _clip_live("clip_hand_mag_in")
	pl.queue_free()
	await _frames(2)


## Пистолет на задержке (пусто), полная перезарядка: в начале клипа затвор остаётся сзади (без хода вперёд-назад на
## вливании клипа), после кадра рычага — впереди. Клипы ведёт ViewmodelClips.update по настоящему Player.
func _locked_reload_clips() -> void:
	if not (_wanted("clip_locked_reload_start") or _wanted("clip_locked_reload_released")):
		return
	var pl: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(pl)
	pl.set_physics_process(false)
	pl.set_process(false)
	pl.visible = false
	pl.combat_enabled = false
	pl.weapon_id = WEAPON_ID
	pl.weapon_mag = "*"
	pl.ammo = 0
	_vm.equip()
	var step := func(seconds: float) -> void:
		var t: float = 0.0
		while t < seconds:
			_vm.update(pl, 1.0 / 60.0)
			t += 1.0 / 60.0
	step.call(0.2)
	_vm.weapon_action("reload", true, 2.81)
	step.call(0.08)
	await _clip_live("clip_locked_reload_start")
	step.call(2.81 * 0.8)
	await _clip_live("clip_locked_reload_released")
	pl.queue_free()
	await _frames(2)


## Затвор крупно (касательные карты нормалей, гладкость граней) — та же сцена клипов, узкое поле зрения.
func _slide_closeup() -> void:
	if not _wanted("clip_slide_closeup"):
		return
	_vm.preview_reload("idle", 0.0, "*")
	_vm_space.transform = Transform3D.IDENTITY
	_vm.transform = _vm.hip_transform()
	await _frames(2)
	var slide: Node3D = _vm.find_child("Part_Slide", true, false) as Node3D
	if slide == null:
		_failures += 1
		push_error("glock_shots: нет Part_Slide")
		return
	var arms: Array[Node] = _vm.find_children("FPS_Arms*", "MeshInstance3D", true, false)
	for m: Node in arms:
		(m as MeshInstance3D).visible = false
	# в осях рамы (у рукояти: +X влево, +Y вверх, +Z к дулу): середина затвора и точка сверху-слева-сзади
	var fr: Transform3D = _vm.frame.global_transform
	var center: Vector3 = fr * Vector3(0.0, 0.065, 0.05)
	_camera.near = 0.005
	_camera.fov = 24.0
	_camera.position = fr * Vector3(0.16, 0.16, -0.14)
	_camera.look_at(center, fr.basis.y)
	await _settle()
	await _capture("clip_slide_closeup", {"view": "first_person_clips_detail"})
	for m: Node in arms:
		(m as MeshInstance3D).visible = true


func _clip_live(stage: String) -> void:
	if not _wanted(stage):
		return
	_camera.transform = Transform3D.IDENTITY
	_camera.fov = Settings.fps_fov_v()
	var vk: float = CameraRig.viewmodel_scale(_camera.fov)
	_vm_space.transform = Transform3D(Basis.from_scale(Vector3(vk, vk, 1.0)), Vector3.ZERO)
	_vm.transform = _vm.hip_transform()
	await _settle()
	await _capture(stage, {"view": "first_person_clips", "clip": _vm._clip, "position": _vm._anim.current_animation_position})


## Те же позиции камеры и модели, что у CameraRig, без покачивания и отдачи.
func _fp(stage: String, ads: bool, action_name: String = "", progress: float = 0.0, empty: bool = false, suppressed: bool = false) -> void:
	if not _wanted(stage):
		return
	_reset()
	_rig.set_ammo_state(0 if empty else 5)
	_rig.set_suppressed(suppressed)
	if action_name != "":
		var action_parts: PackedStringArray = action_name.split(":")
		_rig.pose_action(action_parts[0], progress, empty, action_parts[1] if action_parts.size() > 1 else "")
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
	if stage in _only:
		return true
	if stage.begins_with("rig_"):
		return "rig" in _only
	if _only.is_empty():
		return true
	if "clips" in _only and stage.begins_with("clip_"):
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
