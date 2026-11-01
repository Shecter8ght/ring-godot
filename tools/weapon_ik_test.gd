extends Node3D
## Реальные Persona, оружие и камеры: стена, край мебели, угол, присед/лёжа и возврат.

var _player: Player
var _camera: CameraRig
var _wall: StaticBody3D
var _table: StaticBody3D
var _side: StaticBody3D
var _ceiling: StaticBody3D
var _fails: int = 0
var _checks: int = 0
var _report: Array[Dictionary] = []
var _body_poses: Dictionary = {}
var _capture: bool = false


func _ready() -> void:
	Engine.max_fps = 90
	Profile.use_file("user://weapon_ik_test.json", true)
	RaidEvents.enabled = false
	_capture = DisplayServer.get_name() != "headless"
	DirAccess.make_dir_recursive_absolute("res://docs/screens/weapon_ik")
	FileAccess.open("res://docs/screens/weapon_ik/.gdignore", FileAccess.WRITE).close()
	_floor_and_light()
	_wall = _obstacle("Wall", Vector3(6, 3, .2), Vector3(0, 1.5, .62))
	_table = _obstacle("FurnitureEdge", Vector3(.6, 1.55, 1.0), Vector3(-.28, .775, .55))
	_side = _obstacle("SideWall", Vector3(.2, 3, 4), Vector3(-.52, 1.5, -.8))
	_ceiling = _obstacle("LowCeiling", Vector3(4, .2, 4), Vector3(0, 2.12, -.8))
	_set_obstacles(true, false, false, false)
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(_player)
	_camera = (load("res://scenes/player/camera_rig.tscn") as PackedScene).instantiate() as CameraRig
	add_child(_camera)
	_camera.set_process_unhandled_input(false)
	_camera.set_process_input(false)
	_camera._target = _player
	_player._camera_rig = _camera
	CameraRig._settings_loaded = true
	CameraRig.first_person_mode = true
	_player.global_position = Vector3(0, .02, -2)
	await _frames(40)
	_camera._look_yaw = 0.0
	_camera._look_pitch = 0.0
	_player.health.hp = 100000.0
	for id: String in ["wpn_ar_01", "wpn_ar_05", "wpn_hg_01", "wpn_hg_02", "wpn_sr_01"]:
		await _weapon(id, {})
		await _case(id + "_free", Vector3(0, .02, -2), Player.Stance.STAND, false)
		_check(id + " free pose", _player.weapon_obstruction < .001 and _camera._viewmodel.visible)
		await _case(id + "_wall", Vector3(0, .02, .05), Player.Stance.STAND, false)
		_check(id + " folds at wall", _player.weapon_obstruction > .12)
		var ammo_before: int = _player.ammo
		_player._fire(_player.spec())
		_check(id + " blocked shot does not consume ammo", _player.ammo == ammo_before)
		await _case(id + "_ads_wall", Vector3(0, .02, .05), Player.Stance.STAND, true)
		_check(id + " scope not rendered while folded", not _camera.scope_active)
		await _case(id + "_prone_wall", Vector3(0, .02, .05), Player.Stance.PRONE, true)
		await _case(id + "_prone_hip_wall", Vector3(0, .02, .05), Player.Stance.PRONE, false)
		await _case(id + "_return", Vector3(0, .02, -2), Player.Stance.STAND, true)
		_check(id + " returns to aim", _player.weapon_obstruction < .001)
	var mods: Dictionary = {}
	var entry: Dictionary = {"id":"wpn_ar_05", "mods":{}}
	var weapons: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapons.json")) as Dictionary
	for att: String in weapons.attachments:
		if String(WeaponDb.attachment(att).get("look", "")) == "suppressor" and WeaponDb.attach_block(entry, "muzzle", att) == "":
			mods["muzzle"] = {"id":att}
			break
	await _weapon("wpn_ar_05", mods)
	_check("compatible suppressor present", not mods.is_empty())
	await _case("rifle_suppressor_wall", Vector3(0, .02, .05), Player.Stance.STAND, true)
	await _case("rifle_crouch", Vector3(0, .02, .05), Player.Stance.CROUCH, false)
	await _case("rifle_prone", Vector3(0, .02, -2), Player.Stance.PRONE, true)
	await _case("rifle_prone_wall", Vector3(0, .02, .05), Player.Stance.PRONE, true)
	_set_obstacles(false, true, false, false)
	await _case("rifle_furniture", Vector3(0, .02, .05), Player.Stance.STAND, false)
	_check("furniture edge folds weapon", _player.weapon_obstruction > .12)
	_set_obstacles(true, false, true, false)
	await _case("rifle_corner", Vector3(0, .02, .05), Player.Stance.STAND, false)
	_set_obstacles(true, false, false, true)
	await _case("rifle_wall_ceiling", Vector3(0, .02, .05), Player.Stance.STAND, true)
	_set_obstacles(true, false, false, false)
	await _case("rifle_lean", Vector3(0, .02, .05), Player.Stance.STAND, true, 1.0)
	_wall.collision_layer = Hitscan.LAYER_DOOR
	await _case("rifle_door", Vector3(0, .02, .05), Player.Stance.STAND, true)
	_wall.collision_layer = Hitscan.LAYER_GLASS
	await _case("rifle_glass", Vector3(0, .02, .05), Player.Stance.STAND, true)
	_wall.collision_layer = Hitscan.LAYER_WORLD
	for id: String in ["wpn_hg_01", "wpn_hg_02"]:
		await _weapon(id, {})
		await _case(id + "_reload_ready", Vector3(0, .02, .05), Player.Stance.STAND, false)
		_player._start_reload(_player.spec())
		_check(id + " reload starts at wall", _player.reload_timer > 0.0)
		await _case(id + "_reload_magazine", Vector3(0, .02, .05), Player.Stance.STAND, false)
		await _case(id + "_reload_insert", Vector3(0, .02, .05), Player.Stance.STAND, false)
		_player.cancel_weapon_action()
	await _fallback()
	await _weapon("wpn_ar_05", mods)
	# Другой вид использует настоящий скелет целиком и ту же геометрию препятствий.
	CameraRig.first_person_mode = false
	Input.action_release("aim")
	_player.aiming = false
	_player.set_physics_process(false)
	await _case("rifle_third_wall", Vector3(0, .02, .05), Player.Stance.STAND, false)
	_check("third person folds weapon", _player.weapon_obstruction > .12)
	var animator: CharacterAnimator = _player.get_node("CharacterAnimator") as CharacterAnimator
	_check("right arm IK target reachable", animator._collision_ik.max_hand_error < .012)
	_check("weapon remains parented to right wrist", _player._weapon_model.get_parent() == animator._grip)
	Input.action_release("aim")
	var file: FileAccess = FileAccess.open("res://docs/screens/weapon_ik/results.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"checks":_checks,"failures":_fails,"cases":_report}, "\t"))
	print("WEAPON_IK_TEST checks=%d failures=%d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


## Замкнутое препятствие не оставляет ни одной позы; после освобождения сборка возвращается.
func _fallback() -> void:
	await _weapon("wpn_hg_01", {})
	_player.set_physics_process(false)
	var blocked: StaticBody3D = _obstacle("NoFreePose", Vector3(5, 5, 5), Vector3(0, 1.5, -2))
	await _frames(45)
	_check("no free pose hides weapon and hands", not _camera._viewmodel.visible and not _camera._arms.visible)
	var ammo_before: int = _player.ammo
	_player._fire(_player.spec())
	_check("no free pose blocks shot without spending ammo", _player.weapon_obstruction > .12 and _player.ammo == ammo_before)
	blocked.queue_free()
	await _frames(45)
	_check("weapon and hands recover after obstacle removed", _camera._viewmodel.visible and _camera._arms.visible)
	_check("free pose recovers aim and clearance", _player.weapon_obstruction < .001 and _camera.weapon_clearance.valid and _camera._arms.arms_clear)
	_player.set_physics_process(true)


func _weapon(id: String, mods: Dictionary) -> void:
	Input.action_release("aim")
	_player.global_position = Vector3(0, .02, -2)
	_player.stance = Player.Stance.STAND
	_player._apply_stance()
	var slot: String = String(WeaponDb.sandbox()[0])
	var weapon: Dictionary = WeaponDb.weapon(id)
	var magazine: String = WeaponDb.default_mag(id)
	var capacity: int = int(weapon.get("internal_mag", WeaponDb.magazine(magazine).get("capacity", 30)))
	var item: Dictionary = {"id":id, "n":1, "dur":100.0, "mods":mods,
		"mag":{"id":magazine,"ammo":WeaponDb.default_ammo(String(weapon.caliber)),"rounds":capacity}, "sight":"primary", "rev":1}
	_player.sandbox_weapons[slot] = item
	_player._ws.erase(slot)
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await _frames(35)
	var animator: CharacterAnimator = _player.get_node("CharacterAnimator") as CharacterAnimator
	if not animator._support.modification_processed.is_connected(_record_body):
		animator._support.modification_processed.connect(_record_body)


func _case(label: String, position: Vector3, stance: int, aimed: bool, lean: float = 0.0) -> void:
	_player.global_position = position
	_player.velocity = Vector3.ZERO
	_player.stance = stance
	_player._apply_stance()
	_camera._look_yaw = 0.0
	_camera._look_pitch = 0.0
	(_player.get_node("Body") as Node3D).rotation.y = 0.0
	if aimed: Input.action_press("aim")
	else: Input.action_release("aim")
	if lean != 0: Input.action_press("camera_right")
	await _frames(65)
	Input.action_release("camera_right")
	var rig: CameraRig = _camera
	var muzzle: Vector3 = rig.viewmodel_muzzle() if rig.ads_active else _player._muzzle_world()
	_check(label + " muzzle outside obstacles", _point_clear(muzzle))
	_check(label + " whole weapon outside obstacles", _weapon_outside(rig._viewmodel if rig.ads_active else _player._weapon_model))
	if rig.ads_active:
		_check(label + " valid visible collision pose", rig.weapon_clearance.valid and rig._viewmodel.visible)
		_check(label + " hands retain contact", rig._arms.max_grip_error < .012)
		_check(label + " bone lengths preserved", rig._arms.max_length_error < .003)
		_check(label + " sleeves outside obstacles", _arms_outside(rig._arms.skeleton))
		_check(label + " sleeves keep view clear", rig._arms.arms_clear)
	else:
		_check(label + " body weapon visible and collision pose valid", _player._weapon_model.visible and (_player.get_node("CharacterAnimator") as CharacterAnimator)._collision_ik.clearance.valid)
		_check(label + " body arms outside obstacles", _body_outside())
		var marker: Node3D = _player._weapon_model.find_child("LeftGrip", true, false) as Node3D
		var target: Vector3 = marker.global_position - marker.global_basis.orthonormalized() * (marker.get_meta("palm_offset", Vector3.ZERO) as Vector3)
		var contact_error: float = (_body_poses.Left as Array[Vector3])[2].distance_to(target)
		_check(label + " body support hand retains contact", contact_error < .012)
		print("BODY_CONTACT_ERROR ", contact_error)
	_report.append({"case":label, "weight":_player.weapon_obstruction, "up":_player.weapon_ready_up,
		"visible":rig._viewmodel.visible, "valid":rig.weapon_clearance.valid,
		"grip_error":rig._arms.max_grip_error, "length_error":rig._arms.max_length_error,
		"arms_clear":rig._arms.arms_clear, "bounds":str(rig.weapon_clearance.bounds), "muzzle":str(muzzle)})
	print("IK_CASE " + JSON.stringify(_report[-1]))
	if label in ["rifle_prone_wall", "wpn_sr_01_prone_wall", "rifle_corner", "rifle_furniture", "wpn_hg_01_reload_magazine", "wpn_hg_02_reload_magazine"]:
		_check(label + " actual skinned mesh outside obstacles and eye", _skin_outside())
	if _capture:
		var observer: Camera3D
		if not rig.ads_active:
			observer = Camera3D.new()
			add_child(observer)
			observer.global_position = _player.global_position + Vector3(3, 1.9, -3)
			observer.look_at(_player.global_position + Vector3(0, 1.1, .15))
			observer.current = true
			await _frames(2)
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/weapon_ik/" + label + ".png")
		if observer:
			observer.queue_free()
			rig._camera.current = true


## Независимая проверка рёбер и углов каждого меша, включая обвесы.
func _weapon_outside(model: Node3D) -> bool:
	for node: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		# у меша со скелетом габарит — поза покоя; руки проверяет _skin_outside по вершинам
		if not mesh.is_visible_in_tree() or mesh.mesh == null or mesh.skin != null or String(mesh.name).begins_with("Laser"): continue
		var aabb: AABB = mesh.get_aabb()
		var corners: Array[Vector3] = []
		for i: int in range(8):
			corners.append(mesh.to_global(aabb.position + aabb.size * Vector3(i & 1, (i >> 1) & 1, (i >> 2) & 1)))
			if not _point_clear(corners[-1]): return false
		for i: int in range(8):
			for axis: int in [1, 2, 4]:
				var j: int = i ^ axis
				if j <= i or corners[i].distance_squared_to(corners[j]) < .0000001: continue
				var ray: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(corners[i], corners[j], WeaponClearance.MASK, [_player.get_rid()])
				if not get_world_3d().direct_space_state.intersect_ray(ray).is_empty():
					print("WEAPON_INTERSECTION ", mesh.name)
					return false
	return true


## Проверяем вершины деформированного меша, включая ткань и пальцы.
func _skin_outside() -> bool:
	var sk: Skeleton3D = _camera._arms.skeleton
	for node: Node in _camera._arms.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = node as MeshInstance3D
		var skin: Skin = mesh.skin
		if skin == null: continue
		for surface: int in range(mesh.mesh.get_surface_count()):
			var arrays: Array = mesh.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
			var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
			var count: int = bones.size() / vertices.size()
			for v: int in range(vertices.size()):
				var posed: Vector3 = Vector3.ZERO
				for w: int in range(count):
					if weights[v * count + w] < .00001: continue
					var bind: int = bones[v * count + w]
					var index: int = sk.find_bone(skin.get_bind_name(bind)) if skin.get_bind_bone(bind) < 0 else skin.get_bind_bone(bind)
					posed += sk.get_bone_global_pose(index) * skin.get_bind_pose(bind) * vertices[v] * weights[v * count + w]
				if not _point_clear(sk.to_global(posed)):
					print("SKIN_INTERSECTION ", mesh.name, " vertex=", v, " position=", sk.to_global(posed))
					return false
				# За краем кадра рукав и пальцы могут подходить к глазу: это не засвет
				# и не отсечение видимой кисти. Проверяем глубину именно в границах кадра.
				var world_point: Vector3 = sk.to_global(posed)
				var camera_depth: float = -_camera._ads_cam.to_local(world_point).z
				if camera_depth > 0.0 and camera_depth < _camera._ads_cam.near + float(Balance.WEAPON_CLEARANCE.view_clear) \
					and get_viewport().get_visible_rect().has_point(_camera._ads_cam.unproject_position(world_point)):
					print("SKIN_IN_EYE ", mesh.name, " vertex=", v)
					return false
	return true


func _record_body() -> void:
	var animator: CharacterAnimator = _player.get_node("CharacterAnimator") as CharacterAnimator
	var skeleton: Skeleton3D = animator._support.get_skeleton()
	for side: String in ["Right", "Left"]:
		var points: Array[Vector3] = []
		for joint: String in ["Arm", "ForeArm", "Hand"]:
			points.append(skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("mixamorig_" + side + joint)).origin)
		_body_poses[side] = points


func _point_clear(position: Vector3) -> bool:
	var query: PhysicsPointQueryParameters3D = PhysicsPointQueryParameters3D.new()
	query.position = position
	query.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	return get_world_3d().direct_space_state.intersect_point(query, 1).is_empty()


func _sleeve_points_clear(a: Vector3, b: Vector3, radius: float) -> bool:
	var direction: Vector3 = (b - a).normalized()
	var across: Vector3 = direction.cross(Vector3.UP if absf(direction.y) < .95 else Vector3.RIGHT).normalized()
	var up: Vector3 = direction.cross(across).normalized()
	for step: int in range(9):
		var center: Vector3 = a.lerp(b, float(step)/8.0)
		for offset: Vector3 in [Vector3.ZERO, across*radius, -across*radius, up*radius, -up*radius]:
			if not _point_clear(center + offset): return false
	return true


func _arms_outside(skeleton: Skeleton3D) -> bool:
	for side: String in ["Right", "Left"]:
		var points: Array[Vector3] = []
		for joint: String in ["Arm", "ForeArm", "Hand"]:
			points.append(skeleton.global_transform * skeleton.get_bone_global_pose(skeleton.find_bone("mixamorig_" + side + joint)).origin)
		var radius: float = float(Balance.WEAPON_CLEARANCE.sleeve_radius) * maxf(skeleton.global_basis.x.length(), skeleton.global_basis.y.length()) * .85
		if not _sleeve_points_clear(points[0], points[1], radius) or not _sleeve_points_clear(points[1], points[2], radius): return false
	return true


func _body_outside() -> bool:
	for side: String in _body_poses:
		var points: Array[Vector3] = _body_poses[side]
		if not _sleeve_points_clear(points[0], points[1], .045) or not _sleeve_points_clear(points[1], points[2], .045): return false
	return not _body_poses.is_empty()


func _check(label: String, success: bool) -> void:
	_checks += 1
	if not success: _fails += 1
	print("[%s] %s" % ["ok" if success else "FAIL", label])


func _frames(count: int) -> void:
	for frame: int in range(count): await get_tree().process_frame


func _obstacle(label: String, size: Vector3, position: Vector3) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = label
	body.position = position
	var shape: BoxShape3D = BoxShape3D.new()
	shape.size = size
	var collision: CollisionShape3D = CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	var mesh: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = size
	mesh.mesh = box
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(.30,.36,.40) if label == "Floor" else Color(.65,.62,.54)
	material.roughness = .85
	mesh.material_override = material
	body.add_child(mesh)
	add_child(body)
	return body


func _set_obstacles(wall: bool, table: bool, side: bool, ceiling: bool) -> void:
	for config: Array in [[_wall,wall],[_table,table],[_side,side],[_ceiling,ceiling]]:
		var body: StaticBody3D = config[0] as StaticBody3D
		body.collision_layer = 1 if bool(config[1]) else 0
		body.visible = bool(config[1])


func _floor_and_light() -> void:
	_obstacle("Floor", Vector3(14,.2,14), Vector3(0,-.1,0))
	var environment: WorldEnvironment = WorldEnvironment.new()
	environment.environment = Environment.new()
	environment.environment.background_mode = Environment.BG_COLOR
	environment.environment.background_color = Color(.18,.21,.25)
	environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.environment.ambient_light_color = Color(.65,.72,.82)
	environment.environment.ambient_light_energy = .7
	add_child(environment)
	var light: DirectionalLight3D = DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45,-40,0)
	light.light_energy = 1.3
	add_child(light)
