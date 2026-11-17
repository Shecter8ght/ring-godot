extends "res://tools/bc5_route203/route203.gd"
## Стыкует лобби из общей Blender-сборки с готовой лестницей и вторым этажом.

const POLISHED := preload("res://tools/bc5_lobby203/polished_stone.gdshader")
const PLASTER_COLOR := preload("res://assets/textures/painted_plaster_wall/albedo.jpg")
const TERRAZZO_COLOR := preload("res://assets/models/props/bc5_route203/terrazzo_albedo.jpg")
const FINISH_VARIATION := preload("res://assets/models/props/bc5_route203/terrazzo_roughness.jpg")
const GROUND := -4.20
const STREET_EDGE := 7.731
const PUBLIC_PATH := [
	Vector3(11.40, GROUND, 6.03), Vector3(12.08, GROUND, 4.23),
	Vector3(12.38, GROUND, 1.64), Vector3(12.41, GROUND, -3.30),
	Vector3(12.41, GROUND, -5.97), Vector3(6.81, GROUND, -6.33),
	Vector3(6.78, GROUND, -8.11), Vector3(5.02, GROUND, -8.38),
]
const FLIGHTS := [
	Vector3(5.12, GROUND, -6.35), Vector3(5.12, -2.10, -2.29),
	Vector3(3.03, -2.10, -2.29), Vector3(3.03, 0.0, -6.32),
]

var _facade_glass: GlassPanes
var _leaf_glass: Array[GlassPanes] = []
@onready var _ground_stair: Door = $GroundStairDoor
@onready var _street_doors: Array[Door] = [$EntryLeft, $EntryRight]


func _ready() -> void:
	await super._ready()
	if DisplayServer.get_name() != "headless" and OS.get_cmdline_user_args().has("--lobby-shots"):
		await _lobby_shots()


func _view_title() -> String:
	return "БЦ «Проспект, 5» · вход и переговорная 203"


func _street_start_z() -> float:
	return STREET_EDGE


func _build_lower_stair(leaf: MeshInstance3D) -> void:
	leaf.reparent(_ground_stair.get_node("Leaf"), false)
	_ground_stair.set("swing_degrees", 83.0)


func _build_entry() -> void:
	super._build_entry()
	var collision: MeshInstance3D = $Lobby/LobbyCollision
	var shape := CollisionShape3D.new()
	shape.shape = collision.mesh.create_trimesh_shape()
	shape.transform = collision.transform
	shape.set_meta("surface", "concrete")
	_solid.add_child(shape)
	$Lobby.remove_child(collision)
	collision.queue_free()

	var floor_finish := _polished(TERRAZZO_COLOR, Color(.51, .49, .455), 1.0)
	var edge_finish := _polished(TERRAZZO_COLOR, Color(.39, .38, .35), 1.0)
	var stone_finish := _polished(PLASTER_COLOR, Color(.716, .690, .638), 0.0)
	var lift_finish: StandardMaterial3D
	for mesh: MeshInstance3D in $Lobby.find_children("*", "MeshInstance3D", true, false):
		if mesh.name.begins_with("Wear_"):
			mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			continue
		if not mesh.name.begins_with("Entry"):
			mesh.gi_mode = GeometryInstance3D.GI_MODE_STATIC
			mesh.layers |= SKY_BLOCKER_LAYER
		for slot: int in mesh.mesh.get_surface_count():
			var material: Material = mesh.get_active_material(slot)
			match material.resource_name:
				"BC5 Lobby Terrazzo":
					mesh.set_surface_override_material(slot, floor_finish)
				"BC5 Lobby Terrazzo Edge":
					mesh.set_surface_override_material(slot, edge_finish)
				"BC5 Lobby Stone":
					mesh.set_surface_override_material(slot, stone_finish)
				"Painted concrete", "Warm plaster · PBR":
					mesh.set_surface_override_material(slot, PAINT)
				"Лобби · сатинированные створки":
					if lift_finish == null:
						lift_finish = (material as StandardMaterial3D).duplicate() as StandardMaterial3D
						lift_finish.metallic = .56
						lift_finish.roughness = .32
						lift_finish.anisotropy_enabled = true
						lift_finish.anisotropy = .36
					mesh.set_surface_override_material(slot, lift_finish)

	_build_public_collision()
	_daylight.reflections.append($VestibuleReflection)
	_daylight.reflections.append($PassageReflection)
	_daylight.reflections.append($GroundLiftsReflection)
	$StairReflection.set_meta("sky_bounce_scale", 1.42)
	_facade_glass = _glazing(self, "LobbyWindows", [
		_pane(Vector3(9.725, -2.34, 7.757), Vector2(1.202, 3.132), GROUND + .01),
		_pane(Vector3(11.4, -1.18, 7.757), Vector2(1.864, .824), GROUND + .01),
		_pane(Vector3(12.975, -2.34, 7.757), Vector2(1.002, 3.132), GROUND + .01),
	])
	_install_entry_leaf($EntryLeft, $Lobby/EntryLeft, -82.0)
	_install_entry_leaf($EntryRight, $Lobby/EntryRight, 82.0)
	_daylight.set_conditions(_daylight.hour, _daylight.weather)


func _polished(scan: Texture2D, tint: Color, floor_weight: float) -> ShaderMaterial:
	var material := ShaderMaterial.new()
	material.shader = POLISHED
	material.set_shader_parameter("scan_color", scan)
	material.set_shader_parameter("finish_variation", FINISH_VARIATION)
	material.set_shader_parameter("tint", tint)
	material.set_shader_parameter("is_floor", floor_weight)
	return material


func _build_public_collision() -> void:
	# Тонкие облицовочные плиты лежат на четырёх цельных участках пола.
	var slab := _mat(Color(.31, .30, .28), .88)
	for rect: Vector4 in [
		Vector4(8.89, 13.508, -1.47, 7.731),
		Vector4(11.385, 13.508, -4.83, -1.47),
		Vector4(6.31, 13.508, -7.215, -4.827),
		Vector4(1.08, 13.508, -9.169, -7.21),
		Vector4(2.00, 6.31, -7.215, -6.97),
	]:
		var center := Vector3((rect.x + rect.y) * .5, GROUND - .082, (rect.z + rect.w) * .5)
		var footprint := Vector3(rect.y - rect.x, 0, rect.w - rect.z)
		_box(center, footprint + Vector3.UP * .175, null, true, "tile")
		if rect.x > 6.0 or rect.z < -8.0:
			center.y = -.124
			_box(center, footprint + Vector3.UP * .20, slab, true)
	_box(Vector3(10.127, GROUND - .082, -1.645), Vector3(2.49, .175, .36), null, true, "tile")
	_box(Vector3(1.042, -2.45, -8.2), Vector3(.083, 3.50, 1.95), slab, true)
	_box(Vector3(6.242, -2.45, -5.99), Vector3(.085, 3.50, 2.53), slab, true)
	_box(Vector3(10.128, -3.65, 2.125), Vector3(1.70, 1.10, 1.072), null, true, "wood")
	_box(Vector3(13.175, -3.94, .634), Vector3(.51, .52, 1.664), null, true, "cloth")
	_box(Vector3(13.175, -3.495, .634), Vector3(.148, .405, 1.664), null, true, "cloth")
	_box(Vector3(13.173, -3.94, 3.615), Vector3(.375, .52, .375), null, true, "stone")
	for x: float in [7.78, 10.20]:
		_box(Vector3(x, -3.068, -4.746), Vector3(1.228, 2.22, .042), null, true, "metal")
	# Низ витрины соседнего закрытого модуля закрывает границу стенда.
	_box(Vector3(5.30, -2.35, 7.80), Vector3(6.50, 3.70, .07), _mat(Color(.13, .15, .145), .36), true)


func _pane(center: Vector3, size: Vector2, floor_y: float, tempered := false) -> Dictionary:
	return {"xf": Transform3D(Basis.IDENTITY, center), "size": size, "floor_y": floor_y,
		"sill": Vector3(.002, .002, .002), "walk_through": false, "tempered": tempered}


func _glazing(parent: Node3D, label: String, panes: Array) -> GlassPanes:
	var glazing := GlassPanes.new()
	glazing.setup(panes, GLAZING, GLAZING_CRACKED)
	glazing.name = label
	glazing.get_node("SillMesh").hide()
	parent.add_child(glazing)
	return glazing


func _install_entry_leaf(door: Door, visual: MeshInstance3D, swing: float) -> void:
	var leaf: StaticBody3D = door.get_node("Leaf")
	visual.reparent(leaf, false)
	door.set("swing_degrees", swing)
	var old_shape: CollisionShape3D = leaf.get_node("Shape")
	old_shape.disabled = true
	# После осыпания проём занят только подвижной обвязкой створки.
	for rail: Array in [
		[Vector3(.4635, .0465, -.007), Vector3(.927, .069, .110)],
		[Vector3(.4635, 2.4465, -.007), Vector3(.927, .069, .110)],
		[Vector3(.0345, 1.2465, -.007), Vector3(.069, 2.331, .110)],
		[Vector3(.8925, 1.2465, -.007), Vector3(.069, 2.331, .110)],
	]:
		var frame_shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = rail[1]
		frame_shape.shape = box
		frame_shape.position = rail[0]
		frame_shape.set_meta("surface", "metal")
		leaf.add_child(frame_shape)
	_leaf_glass.append(_glazing(leaf, "DoorGlass", [
		_pane(Vector3(.4635, 1.2465, .001), Vector2(.793, 2.335), .01, true),
	]))


func _walk_to(point: Vector3) -> bool:
	_player.ads = true
	Input.action_press("move_forward")
	var reached := false
	var frames := ceili(_player.position.distance_to(point) * 52.0) + 75
	for frame: int in range(frames):
		var direction := point - _player.position
		if Vector2(direction.x, direction.z).length() < .065:
			reached = true
			break
		_player.look_yaw = atan2(direction.x, direction.z)
		await get_tree().physics_frame
	Input.action_release("move_forward")
	await _ticks(6)
	if not reached or absf(_player.position.y - point.y) > .09 or not _player.is_on_floor():
		print("Остановка у ", _player.position, ", ожидалось ", point)
		return false
	return true


func _hits_glass(glazing: GlassPanes, index: int) -> bool:
	var xf := glazing.pane_world_transform(index)
	var panel := GlassPanes.pane_of(_ray(xf.origin - xf.basis.z * .25,
		xf.origin + xf.basis.z * .25, Hitscan.LAYER_GLASS))
	return panel.size() == 2 and panel[0] == glazing and int(panel[1]) == index


func _check_room() -> void:
	_daylight.running = false
	_daylight.set_preset(1)
	_check("Игрок появляется на тротуаре", _player.is_on_floor() and _player.position.z > STREET_EDGE)
	_check("Подход к уличной двери шагом", await _walk_to(Vector3(11.4, GROUND, 8.58)))
	_check("Две уличные створки закрыты, обе со стеклом",
		not _street_doors[0].is_open and not _street_doors[1].is_open
		and _hits_glass(_leaf_glass[0], 0) and _hits_glass(_leaf_glass[1], 0))
	await _interact()
	_check("F открывает обе входные створки", _street_doors[0].is_open and _street_doors[1].is_open)
	_check("Коллизия каждого стекла повернулась со створкой", _hits_glass(_leaf_glass[0], 0)
		and _hits_glass(_leaf_glass[1], 0) and _leaf_glass[0].pane_world_transform(0).origin.z > 8.10)
	await _check_moving_glass()
	var public_ok := true
	for point: Vector3 in PUBLIC_PATH:
		if not await _walk_to(point):
			public_ok = false
			break
	_check("Проход от входа мимо стойки и лифтов к лестнице", public_ok)
	if not public_ok:
		return
	await _interact()
	_check("F открывает нижнюю дверь лестницы", _ground_stair.is_open)
	var flights_ok := true
	for point: Vector3 in FLIGHTS:
		if not await _walk_to(point):
			flights_ok = false
			break
	_check("Оба марша и поворот пройдены обычным движением", flights_ok)
	var day_bounce: float = $GroundLiftsReflection.ambient_color_energy
	var entry_bounce: float = $VestibuleReflection.ambient_color_energy
	_daylight.set_preset(4)
	_check("Рассеянный свет лобби следует погоде", $GroundLiftsReflection.ambient_color_energy < day_bounce)
	_daylight.set_preset(6)
	_check("Безлунной ночью лобби темнеет, работает фонарь 203",
		$VestibuleReflection.ambient_color_energy < entry_bounce * .01 and _daylight.lantern_is_lit())
	if flights_ok:
		await super._check_room()
	print("BC5_LOBBY203: %d failures" % _failures)


func _check_moving_glass() -> void:
	var glass := _leaf_glass[0]
	var impact := glass.pane_world_transform(0)
	var camera := Camera3D.new()
	add_child(camera)
	camera.position = impact.origin + impact.basis.z * .35
	camera.look_at(impact.origin)
	_check("U выбирает стекло открытой створки", _break_aimed_pane(camera))
	camera.queue_free()
	await _ticks(12)
	_check("Осыпавшееся стекло освобождает проём, второе цело",
		bool(glass.panes[0].broken) and not _hits_glass(glass, 0) and _hits_glass(_leaf_glass[1], 0))
	await _interact()
	var shards := glass.get_node_or_null("Cubes_0") as Node3D
	_check("Осколки остаются на месте после закрытия створки", shards != null
		and shards.global_position.distance_to(impact.origin) < .03 and not _street_doors[0].is_open)
	await _interact()
	_check("Три неподвижные секции фасада имеют отдельные коллизии",
		_hits_glass(_facade_glass, 0) and _hits_glass(_facade_glass, 1) and _hits_glass(_facade_glass, 2))
	_facade_glass.impact(2, 250.0, _facade_glass.pane_world_transform(2).origin)
	await _ticks(12)
	_check("Неподвижная секция осыпалась отдельно от соседних стёкол", bool(_facade_glass.panes[2].broken)
		and not _hits_glass(_facade_glass, 2) and _hits_glass(_facade_glass, 0) and _hits_glass(_facade_glass, 1))


func _lobby_shots() -> void:
	_daylight.running = false
	_daylight.set_preset(1)
	_daylight.camera_attributes.auto_exposure_enabled = false
	_daylight.camera_attributes.exposure_multiplier = .60
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	get_window().size = Vector2i(1600, 900)
	var previous := get_viewport().get_camera_3d()
	$CameraRig.set_process(false)
	var camera := Camera3D.new()
	camera.attributes = _daylight.camera_attributes
	camera.near = .032
	camera.fov = 55.0
	camera.cull_mask = previous.cull_mask & ~2
	add_child(camera)
	camera.make_current()
	_player.hide()
	_help.hide()
	for door: Door in _street_doors:
		door.toggle(entry.position)
	_ground_stair.toggle(Vector3(5.02, GROUND, -7.79))
	_stair.toggle($LandingSpawn.position)
	var path := _shot_path()
	for view: Array in [
		["01_street", Vector3(12.44, -2.55, 12.24), Vector3(11.35, -2.03, 7.94)],
		["02_reception", Vector3(12.08, -2.54, 6.59), Vector3(11.42, -2.79, .86)],
		["03_lifts", Vector3(12.54, -2.56, -8.35), Vector3(8.97, -2.79, -4.95)],
		["04_stair", Vector3(5.34, -2.56, -8.69), Vector3(4.94, -2.74, -6.39)],
		["05_polish", Vector3(12.12, -2.76, 1.15), Vector3(11.18, -3.61, 7.28)],
	]:
		camera.position = view[1]
		camera.look_at(view[2])
		await get_tree().create_timer(1.15).timeout
		await RenderingServer.frame_post_draw
		var result := get_viewport().get_texture().get_image().save_png(path.path_join(view[0] + ".png"))
		_check("Кадр %s" % view[0], result == OK)
	get_tree().quit(1 if _failures else 0)
