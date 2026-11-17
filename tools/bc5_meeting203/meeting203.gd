extends Node3D
## Отдельная переговорная для проверки вещей, света, штатной двери и остекления.
## --check проверяет физику. --shots снимает вид на высоте глаз. Без аргументов — прогулка.

const ASSETS := "res://assets/models/props/bc5_meeting203/"
const PLAYER := preload("res://scenes/player/player.tscn")
const RIG := preload("res://scenes/player/camera_rig.tscn")
const Daylight203 := preload("res://tools/bc5_meeting203/daylight.gd")
const SunControls := preload("res://tools/bc5_meeting203/sun_controls.gd")
const QualityCapture := preload("res://tools/bc5_meeting203/quality_capture.gd")
const GLAZING := preload(ASSETS + "glazing.tres")
const GLAZING_CRACKED := preload(ASSETS + "glazing_cracked.tres")
const DISPLAY_GLASS := preload(ASSETS + "tv_glass.tres")
const CHAIR_VARIANT_B := preload(ASSETS + "chair_variant_b/material.tres")
const CABINET_OAK := preload(ASSETS + "finish/cabinet_oak.tres")
const TABLE_VARNISH := preload(ASSETS + "finish/table_varnish.png")
const DISPLAY_REFLECTION_LAYER := 1 << 11
const SKY_BLOCKER_LAYER := 1 << 13
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

@export var entry: Marker3D

var _glass: GlassPanes
var _solid: StaticBody3D
var _chairs: Array[Node3D] = []
var _player: Player
var _failures := 0
var _help: Label
var _sun_controls: SunControls

@onready var _door: Door = $OfficeDoor203
@onready var _table: Node3D = $Furniture/Table203
@onready var _daylight: Daylight203 = $Daylight


func _ready() -> void:
	RaidEvents.enabled = false
	var args := OS.get_cmdline_user_args()
	var headless := DisplayServer.get_name() == "headless"
	_build()
	if not headless and args.has("--daylight-shots"):
		await _daylight_shots()
		return
	if not headless and args.has("--shots"):
		await _shots()
		return
	Profile.use_file("user://profile_bc5_meeting203.json", true)
	_player = PLAYER.instantiate() as Player
	_player.name = "Player_1"
	add_child(_player)
	var facing := -entry.global_basis.z if entry else Vector3.BACK
	_player.global_position = entry.global_position if entry else Vector3(.02, .018, -1.0)
	_player.cursor_ground = _player.global_position + facing * 4.0
	await _ticks(14)
	if headless or args.has("--check"):
		await _check_room()
		get_tree().quit(1 if _failures > 0 else 0)
		return
	var movement_camera := RIG.instantiate() as CameraRig
	movement_camera.neutral_camera_attributes = _daylight.camera_attributes
	add_child(movement_camera)
	movement_camera.get_node("AdsCamera/ViewmodelFill").hide()
	movement_camera.set_target(_player)
	movement_camera._look_yaw = atan2(facing.x, facing.z)
	if args.has("--quality-ab") or args.has("--quality-shots") or args.has("--quality-details") or args.has("--quality-views"):
		await QualityCapture.new().run(self, movement_camera, _player, _shot_path(), args)
		return
	var ui := CanvasLayer.new()
	add_child(ui)
	_help = Label.new()
	_help.position = Vector2(24, 14)
	_help.add_theme_font_size_override("font_size", 16)
	_help.add_theme_color_override("font_shadow_color", Color.BLACK)
	_help.add_theme_constant_override("shadow_offset_x", 2)
	_help.add_theme_constant_override("shadow_offset_y", 2)
	ui.add_child(_help)
	_sun_controls = SunControls.new()
	_sun_controls.name = "SunControls"
	_sun_controls.daylight = _daylight
	_sun_controls.hide()
	ui.add_child(_sun_controls)
	_update_help()


func _unhandled_key_input(event: InputEvent) -> void:
	if _sun_controls == null or PauseMenu.shown or not event is InputEventKey or not event.pressed or event.echo:
		return
	var preset: int = event.physical_keycode - KEY_F1
	if preset >= 0 and preset < Daylight203.PRESETS.size():
		_daylight.set_preset(preset)
		_sun_controls.sync()
		_update_help(Daylight203.PRESETS[preset][3])
		get_viewport().set_input_as_handled()
		return
	var camera := get_viewport().get_camera_3d()
	if event.physical_keycode == KEY_U and not _sun_controls.is_open() and camera and _break_aimed_pane(camera):
		get_viewport().set_input_as_handled()


func _update_help(condition: String = "Ясный день") -> void:
	_help.text = ("%s  ·  %s\n" % [_view_title(), condition]
		+ "F1–F7 — свет и погода   F8 — солнце   F — дверь   U — стекло")


func _view_title() -> String:
	return "Переговорная 203"


func _break_aimed_pane(camera: Camera3D) -> bool:
	var p := camera.global_position
	var hit := _ray(p, p - camera.global_basis.z * 13.0,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS)
	var pane := GlassPanes.pane_of(hit)
	if pane.size() != 2:
		return false
	var glazing: GlassPanes = pane[0]
	glazing.impact(int(pane[1]), 250.0, hit.position)
	return true


func _build() -> void:
	# Стекло экрана получает отдельное отражение комнаты.
	for node: MeshInstance3D in $Room203.find_children("*", "MeshInstance3D", true, false):
		var material := node.get_active_material(0) as BaseMaterial3D
		if material == DISPLAY_GLASS:
			node.layers = DISPLAY_REFLECTION_LAYER
		elif material and material.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
			node.gi_mode = GeometryInstance3D.GI_MODE_STATIC
			if FINISH_MATERIALS.has(material.resource_name):
				node.layers |= SKY_BLOCKER_LAYER
			if material.resource_name.ends_with("дуб горизонтальный") or material.resource_name.ends_with("фанера на торце"):
				node.set_surface_override_material(0, CABINET_OAK)
			elif material.resource_name.ends_with("профиль потолка"):
				var grid := _satin_finish(node, .14, .68)
				grid.metallic = .57
				grid.clearcoat_enabled = true
				grid.clearcoat = .65
				grid.clearcoat_roughness = .15
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
	var arm_finish: Material
	for chair: Node3D in $Furniture/Chairs.get_children():
		var arm := chair.find_child("ChairArms", true, false) as MeshInstance3D
		if arm:
			arm.visible = bool(chair.get_meta("has_armrests", true))
			if arm_finish == null:
				arm_finish = _satin_finish(arm, .91, .42)
			arm.set_surface_override_material(0, arm_finish)
		if chair.get_meta("alternate_upholstery", false):
			var body := chair.find_child("ChairBody", true, false) as MeshInstance3D
			body.set_surface_override_material(0, CHAIR_VARIANT_B)
		_box(chair.position + Vector3(0, .247, 0), Vector3(.51, .49, .53), null, true, "cloth")
		_chairs.append(chair)
	for node: MeshInstance3D in $Furniture.find_children("*", "MeshInstance3D", true, false):
		node.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		if not _daylight.table_lantern.is_ancestor_of(node):
			node.layers |= SKY_BLOCKER_LAYER
	for node: MeshInstance3D in _table.find_children("*", "MeshInstance3D", true, false):
		if not _daylight.table_lantern.is_ancestor_of(node):
			var varnished := _satin_finish(node, .90, .51)
			varnished.clearcoat_enabled = true
			varnished.clearcoat = .22
			varnished.clearcoat_roughness = .40
			varnished.clearcoat_texture = TABLE_VARNISH
	for node: MeshInstance3D in _door.find_children("*", "MeshInstance3D", true, false):
		node.layers |= SKY_BLOCKER_LAYER
		var material := node.get_active_material(0) as BaseMaterial3D
		if material and material.resource_name == "203 Brushed stainless":
			var steel := _satin_finish(node, .39, .50)
			steel.metallic = .79
		elif material and material.resource_name == "203 Pale office":
			_satin_finish(node, .83, .25)
	_door.set("swing_degrees", -85.0)
	_windows()


func _satin_finish(node: MeshInstance3D, roughness: float, specular: float) -> BaseMaterial3D:
	var material := node.get_active_material(0).duplicate() as BaseMaterial3D
	material.roughness = roughness
	material.metallic_specular = specular
	node.set_surface_override_material(0, material)
	return material


func _mat(rgb: Color, rough: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = rgb
	material.roughness = rough
	return material


func _box(at: Vector3, size: Vector3, material: Material = null, solid := false,
		surface := "concrete", blocks_sky := true) -> void:
	if material:
		var mesh := BoxMesh.new()
		mesh.size = size
		var visual := MeshInstance3D.new()
		visual.mesh = mesh
		visual.material_override = material
		visual.position = at
		visual.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		if blocks_sky:
			visual.layers |= SKY_BLOCKER_LAYER
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
	var thin_slab := _mat(Color(.28, .282, .265), .9)
	var wall_core := _mat(Color(.36, .35, .32), .92)
	_box(Vector3(-.175, -.13, 3.775), Vector3(9.80, .26, 7.82), null, true, "cloth")
	_box(Vector3(-.175, 3.262, 3.77), Vector3(9.92, .29, 7.98), thin_slab, true)
	_box(Vector3(X_MIN-.081, 1.67, 3.8), Vector3(.16, 3.36, 7.85), null, true)
	_box(Vector3(X_MAX+.08, 1.67, 3.8), Vector3(.16, 3.36, 7.85), null, true)
	# Толщина за чистовыми плоскостями закрывает торцы плит от косого солнца.
	_box(Vector3(-.175, -.155, 3.81), Vector3(10.10, .30, 8.05), wall_core)
	for x in [X_MIN - .164, X_MAX + .164]:
		_box(Vector3(x, 1.62, 3.8), Vector3(.32, 3.49, 8.0), wall_core)
	_box(Vector3((X_MIN-.6)*.5, 1.67, 0), Vector3(-.6-X_MIN, 3.36, .16), null, true)
	_box(Vector3((X_MAX+.6)*.5, 1.67, 0), Vector3(X_MAX-.6, 3.36, .16), null, true)
	_box(Vector3(0, 2.765, 0), Vector3(1.20, 1.09, .16), null, true)
	for x in [-.57, .57]:
		_box(Vector3(x, 1.11, 0), Vector3(.06, 2.22, .19), graphite, true, "metal")
	_box(Vector3(0, 2.193, 0), Vector3(1.08, .055, .21), graphite, true, "metal")
	_box(Vector3(0, .006, 0), Vector3(1.08, .012, .17), graphite, false)
	_build_entry()


func _build_entry() -> void:
	var corridor := _mat(Color(.48, .49, .45), .73)
	var corridor_floor := _mat(Color(.375, .382, .358), .15)
	var thin_slab := _mat(Color(.28, .282, .265), .9)
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
	var spandrel := _mat(Color(.30, .29, .26), .88)
	_box(Vector3(center, .529, 7.863), Vector3(X_MAX-X_MIN+.18, 1.15, .39), spandrel)
	_box(Vector3(center, 3.268, 7.82), Vector3(X_MAX-X_MIN+.18, .48, .44), spandrel)
	_box(Vector3(center, 1.12, GLASS_Z), Vector3(X_MAX-X_MIN, .066, .115), frame, true, "metal", false)
	_box(Vector3(center, 3.402, GLASS_Z), Vector3(X_MAX-X_MIN, .066, .115), frame, true, "metal", false)
	for index in range(count + 1):
		var x := EDGE_A + step * index
		_box(Vector3(x, 2.263, GLASS_Z), Vector3(.074, 2.24, .114), frame, true, "metal", false)
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
	var street_start := _street_start_z()
	_box(Vector3(0, -4.28, (street_start + 50.5) * .5),
		Vector3(92, .18, 50.5 - street_start), pavement, true, "concrete")
	var tree := MeshInstance3D.new()
	tree.name = "BirchAcrossTheWindow"
	tree.mesh = TreeSpot._mesh(BIRCH, BIRCH_MATERIALS)
	tree.position = Vector3(2.4,-4.20,16.72)
	tree.scale = Vector3.ONE * 0.95
	tree.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	add_child(tree)


func _street_start_z() -> float:
	return 1.5


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
		if not (material.albedo_texture and material.normal_enabled and material.normal_texture):
			return false
		if material is ORMMaterial3D:
			if not (material as ORMMaterial3D).orm_texture:
				return false
		elif not (material.roughness_texture and material.metallic_texture):
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
	_daylight.running = false
	_daylight.set_conditions(9.0, "clear")
	var morning := _daylight.sun.global_basis.z
	_check("Утром фонарь на столе выключен", not _daylight.lantern_light.visible)
	_daylight.set_conditions(12.0, "clear")
	_check("Солнце меняет высоту и направление", morning.angle_to(_daylight.sun.global_basis.z) > .30
		and _daylight.sun.visible and _daylight.sun.shadow_enabled)
	var toward_sun := _daylight.sun.global_basis.z * 5.0
	var through_pane := Vector3(.34, .23, 6.16)
	var toward_frame := Vector3((EDGE_A + EDGE_B) * .5, .23, 6.16)
	_check("Прямой свет проходит через проём и перекрывается стойкой",
		_ray(through_pane, through_pane + toward_sun, Hitscan.LAYER_WORLD).is_empty()
		and not _ray(toward_frame, toward_frame + toward_sun, Hitscan.LAYER_WORLD).is_empty())
	_daylight.set_sun_angles(Vector2(24, 160))
	var raised := DayCycle.dir_from(38, 160)
	_daylight.set_sun_angles(Vector2(38, 160))
	_check("Ручная высота меняет направление солнечного света", _daylight.sun.global_basis.z.is_equal_approx(raised))
	var rotated := DayCycle.dir_from(38, 215)
	_daylight.set_sun_angles(Vector2(38, 215))
	var sky_material := _daylight.environment.sky.sky_material as ShaderMaterial
	var sky_direction: Vector3 = sky_material.get_shader_parameter("sun_dir")
	_check("По ручному азимуту поворачиваются и свет, и солнце на небе",
		_daylight.sun.global_basis.z.is_equal_approx(rotated) and sky_direction.is_equal_approx(rotated))
	_daylight.reset_sun_angles()
	_check("Сброс возвращает положение солнца по часам",
		_daylight.sun.global_basis.z.is_equal_approx(toward_sun.normalized()) and _daylight.weather == "clear")
	_daylight.set_conditions(12.0, "overcast")
	_daylight.set_sun_angles(Vector2(36, 190))
	_check("Под сплошными облаками прямое солнце гаснет", not _daylight.sun.visible)
	var overcast_light := _daylight.sky_aperture.light_energy
	_daylight.set_conditions(12.0, "fog")
	_check("Густой туман гасит свет из окна", _daylight.environment.fog_enabled
		and _daylight.sky_aperture.light_energy < overcast_light and not _daylight.sun.visible)
	_daylight.set_preset(Daylight203.PRESETS.size() - 1)
	_check("В безлунную ночь солнце и луна выключены", not _daylight.sun.visible
		and _daylight.reflections[0].ambient_color_energy < .001)
	_check("Ночью фонарь даёт свет и светится рассеиватель", _daylight.lantern_is_lit()
		and _daylight.lantern_light.shadow_enabled and _daylight.table_lantern.get_parent() == _table)
	_daylight.set_sun_angles(Vector2(35, 180))
	_check("При ручном восходе фонарь гаснет", _daylight.sun.visible and not _daylight.lantern_light.visible)
	_check("Рассеянный свет идёт через витраж снаружи", _daylight.sky_apertures.size() == 3
		and _daylight.sky_apertures.all(func(aperture: AreaLight3D) -> bool:
			return (aperture.position.z > GLASS_Z and aperture.shadow_enabled
				and is_zero_approx(aperture.light_size))))
	_daylight.set_conditions(15.55, "clear")
	_check("При возвращении дня фонарь гаснет", not _daylight.lantern_light.visible and not _daylight.lantern_is_lit())
	_check("Стол и кресла загружены с PBR-картами Painter",_textured(_table) and _textured(_chairs[0]))
	_check("Восемь кресел в исходных позициях",_chairs.size()==8)
	var alt := _chairs[2].find_child("ChairBody", true, false) as MeshInstance3D
	var primary := _chairs[0].find_child("ChairBody", true, false) as MeshInstance3D
	_check("В креслах два разных атласа обивки", _textured(_chairs[2])
		and alt.get_active_material(0) == CHAIR_VARIANT_B
		and CHAIR_VARIANT_B.normal_texture != (primary.get_active_material(0) as BaseMaterial3D).normal_texture)
	_check("Карты отделки, затенение примыканий и рельеф плит подключены", _native_room_finish())
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
			float(GLAZING.get_shader_parameter("glass_fresnel")))
		and is_equal_approx(float(optics.get_shader_parameter("transmission_warp")),
			float(GLAZING.get_shader_parameter("transmission_warp")))
		and optics.get_shader_parameter("transmission_dust_mask") == GLAZING.get_shader_parameter("transmission_dust_mask"))
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
	_daylight.running = false
	var path := _shot_path()
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
		for frame in range(105):
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		var f := path.path_join(view[0]+".png")
		var err := get_viewport().get_texture().get_image().save_png(f)
		_check("Сохранён вид "+f,err==OK)
	get_tree().quit(1 if _failures else 0)



func _shot_path() -> String:
	var path := OS.get_environment("BC5_MEETING_SHOTS")
	if path.is_empty():
		path = "user://bc5_meeting203"
	DirAccess.make_dir_recursive_absolute(path)
	return path


func _daylight_shots() -> void:
	_daylight.running = false
	var path := _shot_path()
	get_window().content_scale_mode = Window.CONTENT_SCALE_MODE_DISABLED
	get_window().size = Vector2i(1680, 1040)
	var camera := Camera3D.new()
	camera.near = .04
	camera.fov = 52.69273
	camera.cull_mask &= ~RainOcclusion.LAYER
	camera.position = Vector3(-2.91, 1.65, 1.62)
	add_child(camera)
	camera.look_at(Vector3(.87, 1.28, 5.36))
	camera.make_current()
	var viewport_rid := get_viewport().get_viewport_rid()
	RenderingServer.viewport_set_measure_render_time(viewport_rid, true)
	var requested := OS.get_environment("BC5_MEETING_ONLY").split(",", false)
	var report := []
	for i in Daylight203.PRESETS.size():
		var preset: Array = Daylight203.PRESETS[i]
		if not requested.is_empty() and not requested.has(preset[0]):
			continue
		_daylight.set_preset(i)
		await get_tree().create_timer(1.85).timeout
		var elapsed := PackedFloat32Array()
		var gpu := PackedFloat32Array()
		for frame in range(45):
			var begin := Time.get_ticks_usec()
			await RenderingServer.frame_post_draw
			elapsed.append((Time.get_ticks_usec() - begin) / 1000.0)
			gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport_rid))
		elapsed.sort()
		gpu.sort()
		var shot := path.path_join("%s.png" % preset[0])
		_check("Сохранён вид " + shot, get_viewport().get_texture().get_image().save_png(shot) == OK)
		var from_sun := _daylight.sun.global_basis.z
		report.append({"id": preset[0], "hour": preset[1], "weather": preset[2],
			"sun_energy": _daylight.sun.light_energy, "light_direction": [from_sun.x, from_sun.y, from_sun.z],
			"median_frame_ms": snappedf(elapsed[22], .01), "p95_frame_ms": snappedf(elapsed[42], .01),
			"median_gpu_ms": snappedf(gpu[22], .01), "p95_gpu_ms": snappedf(gpu[42], .01)})
	if requested.is_empty() or requested.has("exposure"):
		await _exposure_shots(camera, path)
	var file := FileAccess.open(path.path_join("daylight.json"), FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(report, "  "))
	get_tree().quit(1 if _failures > 0 else 0)


func _exposure_shots(camera: Camera3D, path: String) -> void:
	_daylight.set_conditions(12.0, "clear")
	var frame := camera.transform
	camera.position = Vector3(-.22, 1.64, -1.17)
	camera.look_at(Vector3(.6, 1.42, -3.0))
	await get_tree().create_timer(2.5).timeout
	camera.transform = frame
	await RenderingServer.frame_post_draw
	var first := get_viewport().get_texture().get_image()
	await get_tree().create_timer(2.5).timeout
	await RenderingServer.frame_post_draw
	var settled := get_viewport().get_texture().get_image()
	_check("Снимок при переводе взгляда к витражу",
		first.save_png(path.path_join("08_exposure_turn.png")) == OK)
	_check("Снимок после адаптации экспозиции",
		settled.save_png(path.path_join("09_exposure_settled.png")) == OK)
