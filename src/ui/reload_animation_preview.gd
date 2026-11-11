extends SubViewportContainer
## Игровые руки и оружие в отдельном мире, без экземпляра Player и таймеров рейда.

var _world: SubViewport
var _camera: Camera3D
var _model: Node3D
var _arms: FirstPersonArms
var _rig: WeaponRig
var _weapon: String = ""


func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_world = SubViewport.new()
	_world.own_world_3d = true
	_world.gui_disable_input = true
	_world.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	add_child(_world)
	_camera = Camera3D.new()
	_camera.fov = Settings.fps_fov_v()
	_camera.near = 0.05
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.085, 0.11, 0.14)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.78, 0.85, 0.97)
	environment.ambient_light_energy = 0.8
	_camera.environment = environment
	_world.add_child(_camera)
	_camera.make_current()
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-35, 30, 0)
	key.light_energy = 1.8
	_world.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(15, -55, 0)
	fill.light_energy = 0.85
	_world.add_child(fill)
	_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	_camera.add_child(_arms)


func select_weapon(id: String) -> void:
	if id == _weapon:
		return
	_weapon = id
	_arms.unbind_weapon()
	if is_instance_valid(_model):
		_model.hide()
		_model.queue_free()
	_model = ViewmodelClips.create(id, {}) if ViewmodelClips.available(id) else WeaponModels.build(id, {}, 0, 100.0, "*", {})
	_camera.add_child(_model)
	_rig = WeaponRig.find_on(_model)
	if _rig:
		_arms.bind_weapon(_model)


func seek_reload(role: String, fraction: float) -> void:
	if _model is ViewmodelClips:
		var clips: ViewmodelClips = _model
		clips.preview_reload(role, fraction, "*")
		_model.transform = WeaponPoseProfiles.apply(clips.hip_transform(), WeaponPoseProfiles.active(), _weapon, 0.0, 0.0)
	elif _rig:
		var empty: bool = role.ends_with("empty")
		_rig.set_ammo_state(0 if empty else 2)
		_rig.pose_action("reload", fraction, empty)
		var orientation := Basis(Vector3.UP, PI + deg_to_rad(4.0)).rotated(Vector3.FORWARD, deg_to_rad(-3.0))
		orientation *= Basis.from_euler(_rig.view_rotation_degrees() * (PI / 180.0))
		var pose := Transform3D(orientation, Balance.FPS_HIP_POSE + _rig.view_offset())
		_model.transform = WeaponPoseProfiles.apply(pose, WeaponPoseProfiles.active(), _weapon, 0.0, 0.0)
		_arms.set_hand_target("Left", _rig.get_hand_target(), _rig.get_hand_weight())
		_arms.update_pose()


func frame_count(role: String, duration: float) -> int:
	if _model is ViewmodelClips:
		return maxi(1, (_model as ViewmodelClips).reload_frame_count(role))
	return maxi(1, roundi(duration * float(Engine.physics_ticks_per_second)))


func set_wide(enabled: bool) -> void:
	_camera.fov = maxf(68.0, Settings.fps_fov_v()) if enabled else Settings.fps_fov_v()
