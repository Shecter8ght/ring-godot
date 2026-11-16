extends Node3D
## Отдельная переговорная для проверки вещей, света, штатной двери и остекления.
## --check проверяет физику. --shots снимает вид на высоте глаз. Без аргументов — прогулка.

const ASSETS := "res://assets/models/props/bc5_meeting203/"
const PLAYER := preload("res://scenes/player/player.tscn")
const RIG := preload("res://scenes/player/camera_rig.tscn")
const GLAZING := preload(ASSETS + "glazing.tres")
const GLAZING_CRACKED := preload(ASSETS + "glazing_cracked.tres")
const DISPLAY_GLASS := preload(ASSETS + "tv_glass.tres")
const DISPLAY_REFLECTION_LAYER := 1 << 11
const FINISH_MATERIALS := ["BC5_203_Walls", "BC5_203_Carpet", "BC5_203_Ceiling"]
const BIRCH := "res://assets/models/plants/birch_b_lod0.glb"
const BIRCH_MATERIALS := "res://assets/models/plants/materials"
const X_MIN := -4.968
const X_MAX := 4.618
const EDGE_A := -4.89
const EDGE_B := 4.54
const GLASS_Z := 7.773
const GLASS_LOW := 1.149
const GLASS_HIGH := 3.373
const INITIAL_OPEN_PANE := 4
const PANE_COUNT := 6

var _glass: GlassPanes
var _solid: StaticBody3D
var _chairs: Array[Node3D] = []
var _player: Player
var _failures := 0

@onready var _door: Door = $OfficeDoor203
@onready var _table: Node3D = $Furniture/Table203


func _ready() -> void:
	RaidEvents.enabled = false
	var args := OS.get_cmdline_user_args()
	var headless := DisplayServer.get_name() == "headless"
	_build()
	if not headless and args.has("--shots"):
		await _shots()
		return
	Profile.use_file("user://profile_bc5_meeting203.json", true)
	_player = PLAYER.instantiate() as Player
	_player.name = "Player_1"
	add_child(_player)
	_player.global_position = Vector3(.02, .018, -1.0)
	_player.cursor_ground = Vector3(.02, 0, 3.0)
	await _ticks(14)
	if headless or args.has("--check"):
		await _check_room()
		get_tree().quit(1 if _failures > 0 else 0)
		return
	var movement_camera := RIG.instantiate() as CameraRig
	add_child(movement_camera)
	movement_camera.set_target(_player)
	movement_camera._look_yaw = 0.0
	var ui := CanvasLayer.new()
	add_child(ui)
	var help := Label.new()
	help.position = Vector2(24, 20)
	help.text = "Переговорная 203   ·   WASD — ходьба   ·   F — дверь   ·   U — разбить стекло под прицелом"
	help.add_theme_font_size_override("font_size", 18)
	help.add_theme_color_override("font_shadow_color", Color.BLACK)
	help.add_theme_constant_override("shadow_offset_x", 2)
	help.add_theme_constant_override("shadow_offset_y", 2)
	ui.add_child(help)


func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo or event.physical_keycode != KEY_U:
		return
	var camera := get_viewport().get_camera_3d()
	if camera and _break_aimed_pane(camera):
		get_viewport().set_input_as_handled()


func _break_aimed_pane(camera: Camera3D) -> bool:
	var p := camera.global_position
	var hit := _ray(p, p - camera.global_basis.z * 13.0,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS)
	var pane := GlassPanes.pane_of(hit)
	if pane.size() != 2 or pane[0] != _glass:
		return false
	_glass.impact(int(pane[1]), 250.0, hit.position)
	return true


func _build() -> void:
	# Стекло экрана получает отдельное отражение комнаты.
	for node: MeshInstance3D in $Room203.find_children("*", "MeshInstance3D", true, false):
		if node.get_active_material(0) == DISPLAY_GLASS:
			node.layers = DISPLAY_REFLECTION_LAYER
			break
	_solid = StaticBody3D.new()
	_solid.name = "SlabWallsFurniture"
	_solid.collision_layer = Hitscan.LAYER_WORLD
	_solid.collision_mask = 0
	add_child(_solid)
	_shell()
	_street()
	_box(Vector3(0, .739, 0) + _table.position, Vector3(3.50, .049, 1.26), null, true)
	for x in [-1.16, 1.16]:
		_box(Vector3(x, .347, 0) + _table.position, Vector3(.125, .686, .68), null, true)
	for chair: Node3D in $Furniture/Chairs.get_children():
		var arm := chair.find_child("ChairArms", true, false) as Node3D
		if arm:
			arm.visible = bool(chair.get_meta("has_armrests", true))
		_box(chair.position + Vector3(0, .247, 0), Vector3(.51, .49, .53), null, true, "cloth")
		_chairs.append(chair)
	_door.set("swing_degrees", -85.0)
	_windows()


func _mat(rgb: Color, rough: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = rgb
	material.roughness = rough
	return material


func _box(at: Vector3, size: Vector3, material: Material = null, solid := false, surface := "concrete") -> void:
	if material:
		var mesh := BoxMesh.new()
		mesh.size = size
		var visual := MeshInstance3D.new()
		visual.mesh = mesh
		visual.material_override = material
		visual.position = at
		add_child(visual)
	if solid:
		var shape := BoxShape3D.new()
		shape.size = size
		var collision := CollisionShape3D.new()
		collision.shape = shape
		collision.position = at
		collision.set_meta("surface", surface)
		_solid.add_child(collision)


func _shell() -> void:
	var graphite := _mat(Color(.175, .182, .175), .53)
	var corridor := _mat(Color(.48, .49, .45), .73)
	var corridor_floor := _mat(Color(.375, .382, .358), .15)
	var thin_slab := _mat(Color(.28, .282, .265), .9)
	_box(Vector3(-.175, -.13, 3.775), Vector3(9.80, .26, 7.82), null, true, "cloth")
	_box(Vector3(-.175, 3.262, 3.77), Vector3(9.92, .29, 7.98), thin_slab, true)
	_box(Vector3(X_MIN-.081, 1.67, 3.8), Vector3(.16, 3.36, 7.85), null, true)
	_box(Vector3(X_MAX+.08, 1.67, 3.8), Vector3(.16, 3.36, 7.85), null, true)
	_box(Vector3((X_MIN-.6)*.5, 1.67, 0), Vector3(-.6-X_MIN, 3.36, .16), null, true)
	_box(Vector3((X_MAX+.6)*.5, 1.67, 0), Vector3(X_MAX-.6, 3.36, .16), null, true)
	_box(Vector3(0, 2.765, 0), Vector3(1.20, 1.09, .16), null, true)
	for x in [-.57, .57]:
		_box(Vector3(x, 1.11, 0), Vector3(.06, 2.22, .19), graphite, true, "metal")
	_box(Vector3(0, 2.193, 0), Vector3(1.08, .055, .21), graphite, true, "metal")
	_box(Vector3(0, .006, 0), Vector3(1.08, .012, .17), graphite, false)
	_box(Vector3(.01, -.105, -1.62), Vector3(8.9, .21, 3.25), corridor_floor, true)
	_box(Vector3(.01, 1.599, -3.22), Vector3(9.08, 3.2, .17), corridor, true)
	for x in [-4.43, 4.46]:
		_box(Vector3(x, 1.599, -1.66), Vector3(.16, 3.2, 3.2), corridor, true)
	_box(Vector3(.015, 3.09, -1.61), Vector3(9.12, .15, 3.36), thin_slab, true)
	_box(Vector3(-2.67, 1.65, -.116), Vector3(4.13, 3.30, .11), corridor)
	_box(Vector3(2.54, 1.65, -.116), Vector3(3.98, 3.30, .11), corridor)
	_box(Vector3(0, 2.725, -.118), Vector3(1.2, 1.005, .11), corridor)
	var sign := Label3D.new()
	sign.text = "203   ПЕРЕГОВОРНАЯ"
	sign.font_size = 40
	sign.pixel_size = .00140
	sign.position = Vector3(.994, 1.68, -.180)
	sign.rotation.y = PI
	sign.modulate = Color(.78,.81,.74)
	sign.outline_size = 3
	add_child(sign)


func _windows() -> void:
	var frame := _mat(Color(.154, .16, .156), .37)
	frame.metallic = .31
	var count := PANE_COUNT
	var step := (EDGE_B - EDGE_A) / count
	var center := (X_MIN + X_MAX) * .5
	_box(Vector3(center, .543, 7.795), Vector3(X_MAX-X_MIN, 1.083, .32), null, true)
	_box(Vector3(center, 1.12, GLASS_Z), Vector3(X_MAX-X_MIN, .066, .115), frame, true, "metal")
	_box(Vector3(center, 3.402, GLASS_Z), Vector3(X_MAX-X_MIN, .066, .115), frame, true, "metal")
	for index in range(count + 1):
		var x := EDGE_A + step * index
		_box(Vector3(x, 2.263, GLASS_Z), Vector3(.074, 2.24, .114), frame, true, "metal")
	# Откосы закрывают зазор между рамой и плоскостями боковых стен.
	for bounds: Vector2 in [Vector2(X_MIN, EDGE_A - .023), Vector2(EDGE_B + .023, X_MAX)]:
		_box(Vector3((bounds.x + bounds.y) * .5, 2.261, 7.701),
			Vector3(bounds.y - bounds.x, 2.289, .247), frame, true, "metal")
	var list: Array = []
	for index in range(count):
		var x := EDGE_A + step * (index + .5)
		# Отключаем связку через фасад второго этажа. Подоконник и стойки имеют собственные коллизии.
		list.append({"xf": Transform3D(Basis.IDENTITY, Vector3(x, (GLASS_HIGH+GLASS_LOW)*.5, GLASS_Z)),
			"size": Vector2(step-.074, GLASS_HIGH-GLASS_LOW), "floor_y": .008, "sill": Vector3(.002,.002,.002),
			"broken":index==INITIAL_OPEN_PANE, "tempered":false, "walk_through":false})
	_glass = GlassPanes.new()
	_glass.setup(list, GLAZING, GLAZING_CRACKED)
	_glass.name = "OfficeWindows203"
	_glass.get_node("SillMesh").hide()
	add_child(_glass)


func _street() -> void:
	var pavement := _mat(Color(.33,.34,.331), .84)
	var siding := _mat(Color(.58,.592,.571), .74)
	var bands := _mat(Color(.49,.50,.48), .77)
	var window := _mat(Color(.145,.181,.209), .31)
	_box(Vector3(0,-4.28,26),Vector3(92,.18,49),pavement, true, "concrete")
	for offset in [-21.0, 2.5, 24.7]:
		_box(Vector3(offset,4.64,33),Vector3(20.6,17.7,6),siding)
		for row in range(5):
			var y := -2.48 + row * 3.04
			_box(Vector3(offset,y-.56,29.979),Vector3(20.6,.28,.19),bands)
			for i in range(9):
				var wx: float = float(offset) - 8.7 + i * 2.14
				_box(Vector3(wx,y+.29,29.90),Vector3(1.48,1.52,.17),window)
	var tree := MeshInstance3D.new()
	tree.name = "BirchAcrossTheWindow"
	tree.mesh = TreeSpot._mesh(BIRCH, BIRCH_MATERIALS)
	tree.position = Vector3(2.4,-4.20,16.72)
	tree.scale = Vector3.ONE * 0.95
	add_child(tree)


func _ray(a: Vector3, b: Vector3, mask: int) -> Dictionary:
	var query := PhysicsRayQueryParameters3D.create(a,b,mask)
	return get_world_3d().direct_space_state.intersect_ray(query)


func _hits_leaf() -> bool:
	return _ray(Vector3(.06,1.2,-.41),Vector3(.06,1.2,.42),Hitscan.LAYER_DOOR).get("collider") == _door.get_node("Leaf")


func _pane_hit(i: int) -> bool:
	var p: Dictionary = _glass.panes[i]
	var center: Vector3 = p.xf.origin
	var hit := _ray(center+Vector3(0,0,-.24),center+Vector3(0,0,.20),Hitscan.LAYER_GLASS)
	var panel := GlassPanes.pane_of(hit)
	return panel.size()==2 and panel[0]==_glass and int(panel[1])==i


func _check(label: String, ok: bool) -> void:
	print(("OK " if ok else "FAIL ") + label)
	if not ok:
		_failures += 1


func _ticks(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _interact() -> void:
	await get_tree().process_frame
	Input.action_press("interact")
	await get_tree().process_frame
	Input.action_release("interact")
	await _ticks(48)


func _textured(root: Node) -> bool:
	var meshes := root.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty():
		return false
	for node in meshes:
		var m: Material = (node as MeshInstance3D).get_active_material(0)
		if not m is BaseMaterial3D:
			return false
		var material := m as BaseMaterial3D
		if not (material.albedo_texture and material.normal_enabled and material.normal_texture
			and material.roughness_texture and material.metallic_texture):
			return false
	return true


func _native_room_finish() -> bool:
	var found: Dictionary = {}
	for node: MeshInstance3D in $Room203.find_children("*", "MeshInstance3D", true, false):
		var material := node.get_active_material(0) as StandardMaterial3D
		if material == null or not FINISH_MATERIALS.has(material.resource_name):
			continue
		if material.resource_name == "BC5_203_Walls" and material.cull_mode != BaseMaterial3D.CULL_DISABLED:
			return false
		if material.resource_name == "BC5_203_Ceiling" and not (material.heightmap_enabled
			and material.heightmap_deep_parallax and material.heightmap_texture):
			return false
		found[material.resource_name] = (material.albedo_texture != null and material.normal_enabled
			and material.normal_texture != null and material.roughness_texture != null
			and material.ao_enabled and material.ao_texture != null
			and material.roughness_texture_channel == BaseMaterial3D.TEXTURE_CHANNEL_GREEN)
	return found.size() == FINISH_MATERIALS.size() and not found.values().has(false)


func _glossy_display() -> bool:
	for node: MeshInstance3D in $Room203.find_children("*", "MeshInstance3D", true, false):
		if node.get_active_material(0) == DISPLAY_GLASS:
			return (node.layers == $Daylight/DisplayReflection.reflection_mask
				and DISPLAY_GLASS.roughness < .15 and DISPLAY_GLASS.clearcoat_enabled
				and not DISPLAY_GLASS.emission_enabled)
	return false


func _check_room() -> void:
	_check("Стол и кресла загружены с PBR-картами Painter",_textured(_table) and _textured(_chairs[0]))
	_check("Восемь кресел в исходных позициях",_chairs.size()==8)
	_check("Отделка v02, затенение примыканий и рельеф плит подключены", _native_room_finish())
	_check("Телевизор отражает свет через отдельный глянцевый материал", _glossy_display())
	_check("Игрок появился перед дверью на полу",_player.is_on_floor() and _player.position.z < -.65)
	_check("Закрытая дверь держит коллизию",_hits_leaf())
	await _interact()
	_check("F открывает штатную дверь",_door.is_open and not _hits_leaf())
	_check("Створка повернулась внутрь",absf((_door.get_node("Leaf") as Node3D).rotation_degrees.y+85.0)<1.0)
	if _door.is_open:
		for i in range(22):
			var contact := _player.move_and_collide(Vector3(0,0,.075))
			if contact != null:
				print("Контакт у порога ",contact.get_collider(), " ",contact.get_normal(),
					" в ",contact.get_position())
				break
			await _ticks(1)
	_check("Игрок физически прошёл в помещение",_player.position.z>.54)
	await _interact()
	_check("F закрывает ту же створку",not _door.is_open and _hits_leaf())
	_check("По одному коллайдеру у каждой целой секции",_pane_hit(0) and _pane_hit(1) and _pane_hit(2) and _pane_hit(3) and _pane_hit(5))
	_check("Стартовый выбитый пролёт свободен",bool(_glass.panes[INITIAL_OPEN_PANE].broken) and not _pane_hit(INITIAL_OPEN_PANE))
	var target: Dictionary = _glass.panes[2]
	var intact := _glass.get_node("GlassMesh") as MultiMeshInstance3D
	_check("Целый витраж использует свой материал", intact.material_override == GLAZING)
	_glass.impact(2, 4.0, target.xf.origin)
	await _ticks(4)
	var damaged := _glass.get_node_or_null("Pane_2") as MeshInstance3D
	var optics := damaged.material_override as ShaderMaterial if damaged else null
	_check("Трещина сохраняет оптику секции и коллизию", optics != null and _pane_hit(2)
		and optics.shader == GLAZING_CRACKED.shader
		and is_equal_approx(float(optics.get_shader_parameter("glass_fresnel")),
			float(GLAZING.get_shader_parameter("glass_fresnel"))))
	var probe := Camera3D.new()
	probe.position = Vector3(-1.9, 1.66, 6.55)
	add_child(probe)
	probe.look_at(target.xf.origin, Vector3.UP)
	_check("Луч проверки попал в нужную панель", _break_aimed_pane(probe))
	probe.queue_free()
	await _ticks(16)
	_check("Целевая панель осыпалась и сняла коллизию",bool(target.broken) and not _pane_hit(2))
	_check("Соседние панели остались целыми",_pane_hit(1) and _pane_hit(3))
	_check("Осколки созданы штатным GlassShatter",_glass.get_node_or_null("Shards_2") is GlassShatter)
	_check("Оконная стойка сохранила коллизию",not _ray(Vector3(EDGE_A,2,7.55),Vector3(EDGE_A,2,8.0),Hitscan.LAYER_WORLD).is_empty())
	_check("Связь навигации через окно отсутствует",_glass.get_node_or_null("Gap_2")==null)
	print("BC5_MEETING203: %d failures" % _failures)


func _shots() -> void:
	var path := OS.get_environment("BC5_MEETING_SHOTS")
	if path.is_empty():
		path = "user://bc5_meeting203"
	DirAccess.make_dir_recursive_absolute(path)
	var window := get_window()
	window.content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	window.size = Vector2i(1680, 1040)
	var snapshot := Camera3D.new()
	snapshot.near = .032
	add_child(snapshot)
	snapshot.current = true
	var requested := OS.get_environment("BC5_MEETING_ONLY").split(",", false)
	for view: Array in [
		["meeting203", Vector3(-2.91,1.65,1.62), Vector3(.87,1.28,5.36), 52.69273],
		["table203_detail", Vector3(-1.79,.99,3.11), Vector3(-.23,.789,4.56), 36.79],
		["glass203_detail", Vector3(-1.27, 1.72, 6.29), Vector3(2.1, 2.0, 7.77), 48.0],
		["ceiling203_detail", Vector3(-2.91, 1.65, 1.62), Vector3(.73, 3.1, 5.65), 40.0],
		["glass203_cracked", Vector3(-.78, 1.72, 5.93), Vector3(.61, 2.27, 7.77), 43.0],
		["chair203_leather", Vector3(-1.75, 1.25, 3.95), Vector3(-.97, .67, 3.56), 46.0],
		["seat203_leather", Vector3(-1.79, 1.52, 6.15), Vector3(-.96, .57, 5.45), 44.0],
		["tv203_gloss", Vector3(3.41, 1.58, 2.54), Vector3(4.5, 1.52, 4.4), 37.0],
		["door203",Vector3(.13,1.65,-1.88),Vector3(.26,1.36,2.15),63.0],
	]:
		if not requested.is_empty() and not requested.has(view[0]):
			continue
		if view[0] == "glass203_cracked":
			var panel: Dictionary = _glass.panes[3]
			_glass.impact(3, 4.0, panel.xf.origin)
		if view[0] == "door203":
			_door.toggle(Vector3(0,0,-1))
			await _ticks(55)
		snapshot.position = view[1]
		snapshot.look_at(view[2],Vector3.UP)
		snapshot.fov = view[3]
		for frame in range(40):
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var f := path.path_join(view[0]+".png")
		var err := get_viewport().get_texture().get_image().save_png(f)
		_check("Сохранён вид "+f,err==OK)
	get_tree().quit(1 if _failures else 0)
