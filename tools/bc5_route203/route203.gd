extends "res://tools/bc5_meeting203/meeting203.gd"
## Второй этаж из утверждённой сборки. Начало координат совпадает с порогом 203.

const PAINT := preload("res://assets/models/props/bc5_route203/paint.tres")
const TERRAZZO := preload("res://assets/models/props/bc5_route203/terrazzo.tres")
const PANE_SIZE := Vector2(1.766, 2.227)
const PANE_CENTERS := [
	Vector3(-24.023, 2.2615, -2.97), Vector3(-24.023, 2.2615, -1.13),
	Vector3(13.623, 2.2615, -1.13), Vector3(13.623, 2.2615, -2.97),
	Vector3(13.623, 2.2615, -5.13), Vector3(13.623, 2.2615, -6.97),
	Vector3(13.623, 2.2615, -9.13),
]
const STAIR_THRESHOLD := Vector3(5.04, 0, -6.58)
const LOWER_HINGE := Vector3(4.463, -4.20, -7.12)
const HALL_PATH := [
	Vector3(5.04, 0, -8.14), Vector3(12.48, 0, -8.14),
	Vector3(12.48, 0, -.765), Vector3(0, 0, -.765),
]
## Границы участков терраццо в XY исходника Blender, включая заход под порог 203.
const TILE_REGIONS := [
	Vector4(-17.675, 19.677, 2.445, 3.953), Vector4(-17.675, 8.10, 3.953, 5.77),
	Vector4(12.50, 19.677, 3.953, 4.30), Vector4(17.581, 19.677, 4.30, 7.28),
	Vector4(12.50, 19.677, 7.28, 9.65), Vector4(8.181, 19.677, 9.65, 11.62),
]

var _hall_glass: GlassPanes
@onready var _stair: Door = $StairDoor


func _ready() -> void:
	await super._ready()
	if DisplayServer.get_name() != "headless" and OS.get_cmdline_user_args().has("--route-shots"):
		await _route_shots()


func _view_title() -> String:
	return "БЦ «Проспект, 5» · второй этаж"


func _build_entry() -> void:
	var collider: MeshInstance3D = $Hallway/ShellCollision
	var shape := CollisionShape3D.new()
	shape.shape = collider.mesh.create_trimesh_shape()
	shape.transform = collider.transform
	shape.set_meta("surface", "concrete")
	_solid.add_child(shape)
	$Hallway.remove_child(collider)
	collider.queue_free()

	var lower_leaf: MeshInstance3D = $Hallway/LowerStairLeaf
	_build_lower_stair(lower_leaf)
	var leaf: MeshInstance3D = $Hallway/UpperStairLeaf
	leaf.reparent(_stair.get_node("Leaf"), false)
	_stair.set("swing_degrees", 97.0)
	for mesh: MeshInstance3D in $Hallway.find_children("*", "MeshInstance3D", true, false):
		if mesh.name.begins_with("Decal_"):
			mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			continue
		mesh.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		mesh.layers |= SKY_BLOCKER_LAYER
		for slot in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(slot)
			match material.resource_name:
				"BC5 Route Paint":
					mesh.set_surface_override_material(slot, PAINT)
				"BC5 Route Terrazzo":
					mesh.set_surface_override_material(slot, TERRAZZO)

	# Плита над коридором и опора лестницы замыкают этот участок корпуса.
	var concrete := _mat(Color(.37, .36, .33), .88)
	_box(Vector3(-5.20, 3.51, -2.04), Vector3(38.0, .20, 20.05), concrete, true)
	_box(Vector3(4.10, -4.305, -4.33), Vector3(4.40, .21, 5.63), concrete, true)
	for tile: Vector4 in TILE_REGIONS:
		var center := Vector3((tile.x + tile.y) * .5 - 6.20, -.056, 2.45 - (tile.z + tile.w) * .5)
		var size := Vector3(tile.y - tile.x + .008, .112, tile.w - tile.z + .008)
		_box(center, size, null, true)
	_daylight.reflections.append($HallReflection)
	_daylight.reflections.append($LiftReflection)
	_daylight.reflections.append($StairReflection)

	var panes: Array = []
	for center: Vector3 in PANE_CENTERS:
		panes.append({
			"xf": Transform3D(Basis(Vector3.UP, PI * .5), center),
			"size": PANE_SIZE, "floor_y": .008, "sill": Vector3(.002, .002, .002),
			"walk_through": false, "tempered": false,
		})
	_hall_glass = GlassPanes.new()
	_hall_glass.name = "HallWindows"
	_hall_glass.setup(panes, GLAZING, GLAZING_CRACKED)
	_hall_glass.get_node("SillMesh").hide()
	add_child(_hall_glass)


func _build_lower_stair(leaf: MeshInstance3D) -> void:
	leaf.position = LOWER_HINGE
	_box(LOWER_HINGE + Vector3(.538, 1.096, 0), Vector3(1.07, 2.171, .046), null, true, "metal")


func _walk_segment(point: Vector3) -> bool:
	var start := _player.global_position
	var direction := point - start
	direction.y = 0.0
	var subdivisions := maxi(1, ceili(direction.length() / .20))
	for i in range(1, subdivisions + 1):
		var sample := start + direction * (float(i) / subdivisions)
		if _ray(sample + Vector3.UP * .28, sample - Vector3.UP * .11, Hitscan.LAYER_WORLD).is_empty():
			print("Разрыв пола у ", sample)
			return false
	var contact := _player.move_and_collide(direction)
	if contact:
		print("Капсула задела ", contact.get_collider(), " у ", contact.get_position())
	return contact == null and _player.global_position.distance_to(start + direction) < .04


func _check_room() -> void:
	_daylight.running = false
	_daylight.set_preset(1)
	_check("Игрок на полу верхней площадки", _player.is_on_floor()
		and _player.position.distance_to($LandingSpawn.position) < .10)
	_check("Подход с площадки к лестничной двери",
		_walk_segment(Vector3(3.07, 0, -6.58)) and _walk_segment(STAIR_THRESHOLD))
	_check("Лестничная дверь закрыта при входе", not _stair.is_open)
	await _ticks(3)
	await _interact()
	_check("F открывает лестничную дверь", _stair.is_open)
	var walkable := true
	for point: Vector3 in HALL_PATH:
		walkable = _walk_segment(point) and walkable
	_check("Капсула прошла через лифтовой холл к 203", walkable)
	await _ticks(3)
	await _interact()
	_check("F открывает 203 из общего коридора", _door.is_open)
	_player.ads = true
	_player.look_yaw = 0.0
	Input.action_press("move_forward")
	await _ticks(78)
	Input.action_release("move_forward")
	await _ticks(4)
	_check("Игрок прошёл через порог 203 штатным движением", _player.position.z > 1.15 and _player.is_on_floor())
	if _player.position.z <= 1.15:
		print("Конец прохода через порог: ", _player.position)

	var all_panes := true
	for i in PANE_CENTERS.size():
		all_panes = _hall_pane_at(i) and all_panes
	_check("Все доступные секции коридора имеют отдельные коллизии", all_panes)
	var section: Vector3 = PANE_CENTERS[4]
	var aim := Camera3D.new()
	add_child(aim)
	aim.position = section - Vector3.RIGHT
	aim.look_at(section)
	_check("U выбирает стекло нового коридора", _break_aimed_pane(aim))
	aim.queue_free()
	await _ticks(16)
	_check("Выбранная секция осыпается", not _hall_pane_at(4) and bool(_hall_glass.panes[4].broken))
	_check("Соседние секции остаются целыми", _hall_pane_at(3) and _hall_pane_at(5))
	_check("Окно второго этажа без навигационной связи", _hall_glass.get_node_or_null("Gap_4") == null)
	var daylight_level: float = $HallReflection.ambient_color_energy
	_daylight.set_preset(4)
	_check("Туман ослабляет отражённый свет холла", $HallReflection.ambient_color_energy < daylight_level)
	_daylight.set_preset(6)
	_check("Безлунной ночью лестница и коридор темнеют", $StairReflection.ambient_color_energy < .001
		and $HallReflection.ambient_color_energy < .001 and _daylight.lantern_is_lit())
	print("BC5_ROUTE203: %d failures" % _failures)


func _hall_pane_at(index: int) -> bool:
	var p: Vector3 = PANE_CENTERS[index]
	var hit := _ray(p - Vector3.RIGHT * .25, p + Vector3.RIGHT * .25, Hitscan.LAYER_GLASS)
	var section := GlassPanes.pane_of(hit)
	return section.size() == 2 and section[0] == _hall_glass and int(section[1]) == index


func _route_shots() -> void:
	await get_tree().process_frame
	_daylight.running = false
	_daylight.set_preset(1)
	_daylight.camera_attributes.auto_exposure_enabled = false
	_daylight.camera_attributes.exposure_multiplier = .60
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	get_window().size = Vector2i(1920, 1080)
	var previous := get_viewport().get_camera_3d()
	$CameraRig.set_process(false)
	var camera := Camera3D.new()
	camera.attributes = _daylight.camera_attributes
	camera.near = .032
	camera.fov = 60.0
	camera.cull_mask = previous.cull_mask & ~2
	add_child(camera)
	camera.make_current()
	_player.hide()
	_stair.toggle(entry.position)
	_door.toggle(Vector3(0, 0, -1))
	var path := _shot_path()
	for view: Array in [
		["01_landing", Vector3(3.07, 1.61, -5.72), Vector3(4.66, 1.48, -7.27)],
		["02_lifts", Vector3(12.00, 1.61, -7.55), Vector3(8.39, 1.44, -4.86)],
		["03_corridor", Vector3(1.21, 1.61, -1.90), Vector3(-9.20, 1.61, -2.10)],
		["04_door203", Vector3(1.73, 1.61, -2.39), Vector3(.05, 1.43, .74)],
	]:
		camera.position = view[1]
		camera.look_at(view[2])
		await get_tree().create_timer(1.1).timeout
		await RenderingServer.frame_post_draw
		var filename := path.path_join(view[0] + ".png")
		var result := get_viewport().get_texture().get_image().save_png(filename)
		_check("Кадр %s" % filename, result == OK)
	get_tree().quit(1 if _failures else 0)
