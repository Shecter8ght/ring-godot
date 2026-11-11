extends Node3D
## The accepted Blender model uses a metre per unit. Blender (X, Y, Z) maps to (X, Z, −Y).

const DOOR := preload("res://scenes/props/door.tscn")
const AUTHORED_DOOR := preload("res://scenes/levels/prospekt/zerno/zerno_door.gd")
const FLOOR := preload("res://scenes/levels/prospekt/zerno/floor.gdshader")
const GLASS := preload("res://scenes/levels/prospekt/zerno/case_glass.gdshader")
const WALL := preload("res://scenes/levels/prospekt/zerno/wall_detail.gdshader")
const FASCIA := preload("res://scenes/levels/prospekt/zerno/facade_weathering.gdshader")
const MAPS := "res://assets/models/props/zerno/maps/"

# Local diffuse daylight at the openings. Final field is the occluding door, if any.
const DAYLIGHT := [
	["West windows", Vector3(-5.2, 2.38, 5.08), Vector3(-3.7, .87, -.7), 12.5, 66.0, 2.60, ""],
	["East windows", Vector3(1.60, 2.28, 5.08), Vector3(1.0, 1.0, -2.0), 12.5, 65.0, 2.25, ""],
	["Hall floor bounce", Vector3(-1.58, .54, -.58), Vector3(-1.7, 1.37, -4.37), 7.4, 67.0, .58, ""],
	["Stock doorway", Vector3(4.13, 1.97, .03), Vector3(6.34, .86, -1.68), 7.8, 65.0, 1.40, "StockDoor"],
	["Stock floor bounce", Vector3(5.46, .70, -1.30), Vector3(6.20, 1.44, -4.73), 5.2, 67.0, .62, "StockDoor"],
	["Utility sink bounce", Vector3(6.26, 1.90, -2.42), Vector3(7.34, .84, -2.31), 2.35, 56.0, .48, "StockDoor"],
	["Washroom doorway", Vector3(-5.90, 1.98, -2.76), Vector3(-6.68, 1.07, -4.58), 4.9, 61.0, 1.02, "WashroomDoor"],
	["Washroom floor bounce", Vector3(-5.68, 1.34, -3.86), Vector3(-7.44, .52, -4.57), 2.85, 65.0, .58, "WashroomDoor"],
	["Rear yard doorway", Vector3(6.0, 1.99, -14.20), Vector3(6.0, 1.23, -9.3), 9.7, 36.0, .73, "DeliveryDoor"],
]

# Broad reflected daylight for faces turned away from the openings. Each zone has its own receiver layer.
const ROOM_BOUNCE := [
	["Washroom ambient bounce", Vector3(-6.10, 1.65, -3.94), 4.25, .20, "WashroomDoor",
		["WashroomShell", "WashroomProps", "Mirror", "WashroomDoor"]],
	["Bin bounce", Vector3(-7.05, .36, -3.73), 1.15, .16, "WashroomDoor",
		["WashroomProps"]],
	["Bar ambient bounce", Vector3(2.86, 1.19, .75), 4.40, .64, "",
		["Bar", "FridgeMilk", "FridgePastry"]],
	["Utility ambient bounce", Vector3(6.04, 2.22, 2.34), 4.80, .37, "StockDoor",
		["Room", "StockWalls", "StockProps", "StockPrint", "StockDoor", "UtilityCabinetDoor", "TileSurface_3"]],
	["Passage ambient bounce", Vector3(6.0, 1.30, -10.88), 8.40, .26, "StockRearDoor",
		["Corridor", "DeliveryDoor", "Corridor roof", "Corridor end west", "Corridor end east", "Corridor exit lintel"]],
]

# Pivot name, clear leaf width and height, collision depth, closed yaw, swing into the room.
const LEAVES := [
	["StreetDoor", 1.053, 2.182, 0.10, 0.0, 90.0],
	["StockDoor", 1.052, 2.132, 0.05, 90.0, -90.0],
	["WashroomDoor", 0.970, 2.121, 0.047, 0.0, 94.0],
	["StockRearDoor", 1.069, 2.195, 0.067, 0.0, 93.0],
	["DeliveryDoor", 1.070, 2.221, 0.046, 0.0, 94.0],
]
# The original right pane next to the entrance was already knocked out in Blender.
const PANES := [
	Vector4(-7.624, -6.3376, 0.286, 3.364),
	Vector4(-6.2636, -4.9772, 0.286, 3.364),
	Vector4(-4.9032, -3.6168, 0.286, 3.364),
	Vector4(-3.5428, -2.2564, 0.286, 3.364),
	Vector4(-2.1824, -0.8960, 0.286, 3.364),
	Vector4(0.8960, 2.2480, 0.286, 3.364),
	Vector4(2.3220, 3.6740, 0.286, 3.364),
	Vector4(-0.524, 0.524, 2.326, 3.364),
]
const BLOCKS := [
	["Slab", Vector3(-8,-5.50,-.18), Vector3(8,5.50,0)],
	["Left shell", Vector3(-8,-5.50,0), Vector3(-7.76,5.50,4)],
	["Right shell", Vector3(7.77,-5.50,0), Vector3(8,5.50,4)],
	["Back west", Vector3(-7.77,5.27,0), Vector3(5.46,5.50,4)],
	["Back east", Vector3(6.54,5.27,0), Vector3(7.77,5.50,4)],
	["Rear lintel", Vector3(5.46,5.27,2.205), Vector3(6.54,5.50,4)],
	["Stock front wall", Vector3(3.92,-5.37,0), Vector3(4.08,-.55,3.66)],
	["Stock back wall", Vector3(3.92,.55,0), Vector3(4.08,5.37,3.66)],
	["Stock lintel", Vector3(3.92,-.55,2.145), Vector3(4.08,.55,3.66)],
	["WC side", Vector3(-4.68,2.64,0), Vector3(-4.52,5.38,3.72)],
	["WC west", Vector3(-7.77,2.56,0), Vector3(-6.39,2.72,3.72)],
	["WC east", Vector3(-5.41,2.56,0), Vector3(-4.60,2.72,3.72)],
	["WC lintel", Vector3(-6.39,2.56,2.125), Vector3(-5.41,2.72,3.72)],
	["Washstand", Vector3(-7.61,4.48,.39), Vector3(-6.46,5.24,.99)],
	["Washroom toilet", Vector3(-5.94,4.64,.18), Vector3(-5.53,5.25,.49)],
	["Left sill", Vector3(-7.77,-5.50,0), Vector3(-.60,-5.25,.25)],
	["Right sill", Vector3(.60,-5.50,0), Vector3(3.92,-5.25,.25)],
	["Street lintel", Vector3(-7.77,-5.49,3.44), Vector3(4, -5.20,4)],
	["Stock façade", Vector3(4.0,-5.50,0), Vector3(7.77,-5.15,3.44)],
	["Counter", Vector3(1.005,-4.485,0), Vector3(1.885,-1.165,1.053)],
	["Display case", Vector3(1.08,-2.33,1.052), Vector3(1.79,-1.32,1.605)],
	["Backbar", Vector3(3.168,-4.531,0), Vector3(3.890,-1.02,.96)],
	["Rack west", Vector3(4.18,3.12,0), Vector3(4.70,4.66,2.07)],
	["Rack east", Vector3(7.20,3.66,0), Vector3(7.73,5.22,2.07)],
	["Rack front", Vector3(4.36,-5.16,0), Vector3(5.88,-4.60,2.07)],
	["Sink unit", Vector3(6.89,1.08,0), Vector3(7.74,3.28,.95)],
	["Fridge", Vector3(6.66,-3.75,0), Vector3(7.65,-2.91,1.91)],
	["Corridor floor", Vector3(4.73,5.49,-.14), Vector3(7.27,14.56,0)],
	["Corridor west", Vector3(4.72,5.49,0), Vector3(4.88,14.39,3.98)],
	["Corridor east", Vector3(7.12,5.49,0), Vector3(7.28,14.39,3.98)],
	["Corridor end west", Vector3(4.72,14.25,0), Vector3(5.46,14.49,3.98)],
	["Corridor end east", Vector3(6.54,14.25,0), Vector3(7.28,14.49,3.98)],
	["Corridor exit lintel", Vector3(5.46,14.25,2.225), Vector3(6.54,14.49,3.98)],
	["Cafe roof", Vector3(-8,-5.5,3.82), Vector3(8,5.5,4.06)],
	["Corridor roof", Vector3(4.72,5.47,3.86), Vector3(7.28,14.49,4.06)],
]

var leaves: Dictionary = {}
var _solids: StaticBody3D
var _daylight: Array[Array] = []


func _ready() -> void:
	_solids = StaticBody3D.new()
	_solids.name = "ArchitectureCollision"
	_solids.collision_layer = Hitscan.LAYER_WORLD
	_solids.collision_mask = 0
	add_child(_solids)
	for spec: Array in BLOCKS:
		_box(spec[0], spec[1], spec[2])
		if spec[0] in ["Corridor end west", "Corridor end east", "Corridor exit lintel", "Cafe roof", "Corridor roof"]:
			var midpoint: Vector3 = (spec[1] + spec[2]) * .5
			var extent: Vector3 = spec[2] - spec[1]
			_solid_visual(spec[0], Vector3(midpoint.x, midpoint.z, -midpoint.y), Vector3(extent.x, extent.z, extent.y))
	for x: float in [-6.3006, -4.9402, -3.5798, -2.2194, -.75, .75, 2.285]:
		_box("Mullion", Vector3(x-.033,-5.36,.245), Vector3(x+.033,-5.27,3.444))
	var furniture: Array = JSON.parse_string(FileAccess.get_file_as_string(MAPS + "collision_props.json"))
	for spec: Array in furniture:
		if spec[0] in ["Hanging basin body", "Ceramic toilet base"]:
			continue
		var a: Array = spec[1]
		var b: Array = spec[2]
		_box(spec[0], Vector3(a[0], a[1], a[2]), Vector3(b[0], b[1], b[2]))
	_materials()
	for spec: Array in LEAVES:
		_door(spec)
	_reflection("Washroom reflections", Vector3(-6.25, 1.47, -3.99), Vector3(3.07, 2.83, 2.55))
	_reflection("Storefront reflections", Vector3(-1.15, 1.7, 2.17), Vector3(11.55, 3.4, 6.1))
	_setup_daylight()


func install_glass(level: Node3D, at: Transform3D) -> GlassPanes:
	# GlassPanes uses world transforms for ray hits, shards and navigation links.
	var specs: Array = []
	for i in range(PANES.size()):
		var limits: Vector4 = PANES[i]
		var centre := Vector3((limits.x + limits.y) * .5, (limits.z + limits.w) * .5, 5.315)
		specs.append({"xf": at * Transform3D(Basis.IDENTITY, centre),
			"size": Vector2(limits.y - limits.x, limits.w - limits.z), "floor_y": at.origin.y,
			"sill": Vector3(.02, .01, .02), "broken": i == 5, "tempered": false})
	var glass := GlassPanes.new()
	glass.setup(specs)
	glass.name = "ZernoGlazing"
	glass.get_node("SillMesh").hide()
	var window := StandardMaterial3D.new()
	window.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	window.cull_mode = BaseMaterial3D.CULL_DISABLED
	window.albedo_color = Color(.49, .56, .54, .085)
	window.roughness = .24
	window.metallic_specular = .17
	(glass.get_node("GlassMesh") as MultiMeshInstance3D).material_override = window
	level.add_child(glass)
	return glass


func _door(spec: Array) -> void:
	var model := find_child(spec[0] + "Pivot", true, false) as Node3D
	if model == null:
		push_error("Zerno missing pivot " + spec[0])
		return
	var d := DOOR.instantiate() as Door
	d.set_script(AUTHORED_DOOR)
	d.name = spec[0]
	d.width = spec[1]
	d.height = spec[2]
	d.thickness = spec[3]
	d.position = model.position
	d.rotation.y = deg_to_rad(spec[4])
	d.set("swing_degrees", spec[5])
	var leaf := d.get_node("Leaf") as Node3D
	var compensate := Transform3D(Basis(Vector3.UP, -d.rotation.y), Vector3.ZERO)
	for part: Node3D in model.get_children():
		var offset := part.transform
		model.remove_child(part)
		leaf.add_child(part)
		part.transform = compensate * offset
	model.get_parent().add_child(d)
	model.queue_free()
	leaves[spec[0]] = d


func _box(label: String, a: Vector3, b: Vector3) -> void:
	var col := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(b.x-a.x, b.z-a.z, b.y-a.y)
	col.name = label
	var p := (a+b)*.5
	col.position = Vector3(p.x, p.z, -p.y)
	col.shape = shape
	_solids.add_child(col)


func _solid_visual(label: String, at: Vector3, size: Vector3) -> void:
	var obj := MeshInstance3D.new()
	obj.name = label
	var slab := BoxMesh.new()
	slab.size = size
	obj.mesh = slab
	obj.position = at
	obj.material_override = SectorMaterials.get_material("concrete_wall_006")
	add_child(obj)


func _setup_daylight() -> void:
	for spec: Array in DAYLIGHT:
		var fill := SpotLight3D.new()
		fill.name = spec[0]
		fill.position = spec[1]
		fill.spot_range = spec[3]
		fill.spot_angle = spec[4]
		fill.spot_attenuation = 1.1
		fill.light_specular = .05
		fill.shadow_enabled = not String(spec[0]).ends_with("bounce")
		fill.shadow_blur = 2.5
		_add_daylight(fill, spec[5], spec[6])
		fill.look_at(to_global(spec[2]))
	var meshes := find_children("*", "MeshInstance3D", true, false)
	for i in range(ROOM_BOUNCE.size()):
		var spec: Array = ROOM_BOUNCE[i]
		var mask := 1 << (8 + i)
		for mesh: MeshInstance3D in meshes:
			if mesh.name in spec[5]:
				mesh.layers |= mask
		var fill := OmniLight3D.new()
		fill.name = spec[0]
		fill.position = spec[1]
		fill.omni_range = spec[2]
		fill.omni_attenuation = .65
		fill.light_specular = .18
		fill.light_cull_mask = mask
		_add_daylight(fill, spec[3], spec[4])
	var clock := Timer.new()
	clock.wait_time = .16
	add_child(clock)
	clock.timeout.connect(_update_daylight)
	clock.start()
	_update_daylight()


func _add_daylight(fill: Light3D, strength: float, door_name: String) -> void:
	fill.light_bake_mode = Light3D.BAKE_DISABLED
	# Scattered light has no visible emitter for the camera's optics effects.
	fill.set_meta("own", true)
	add_child(fill)
	var door: Door = leaves.get(door_name)
	var leaf := door.get_node("Leaf") as Node3D if door else null
	_daylight.append([fill, strength, leaf])


func _update_daylight() -> void:
	var time: String = RaidConditions.current.get("time", "dusk")
	var elevation := 30.0 if time == "day" else 5.0 if time == "dusk" else -10.0
	if is_instance_valid(DayCycle.current):
		elevation = DayCycle.sun_at(DayCycle.current.hour).x
	var weather: String = RaidConditions.current.get("weather", "clear")
	var amount: float = smoothstep(-4.0, 22.0, elevation) * {"overcast": .74, "rain": .60, "fog": .66}.get(weather, 1.0)
	var tint := Color(1.0, .84, .69).lerp(Color(.87, .94, 1.0), smoothstep(1.0, 30.0, elevation))
	for spec: Array in _daylight:
		var fill: Light3D = spec[0]
		var leaf: Node3D = spec[2]
		var through := absf(sin(leaf.rotation.y)) if leaf else 1.0
		fill.light_energy = spec[1] * amount * through
		fill.light_color = tint
		fill.visible = fill.light_energy > .015


func _reflection(label: String, at: Vector3, size: Vector3) -> void:
	var probe := ReflectionProbe.new()
	probe.name = label
	probe.position = at
	probe.size = size
	probe.box_projection = true
	probe.ambient_mode = ReflectionProbe.AMBIENT_DISABLED
	probe.enable_shadows = true
	probe.intensity = .68
	add_child(probe)


func _materials() -> void:
	var paint := ShaderMaterial.new()
	paint.shader = FASCIA
	var fascia: String = "res://assets/models/props/zerno/facade_sign_facade_sign_"
	paint.set_shader_parameter("paint_color", load(fascia + "color.png"))
	paint.set_shader_parameter("paint_normal", load(fascia + "normal.png"))
	paint.set_shader_parameter("paint_orm", load(fascia + "orm.png"))
	for m: MeshInstance3D in $FacadeSign.find_children("*", "MeshInstance3D", true, false):
		m.material_override = paint
	var floor := ShaderMaterial.new()
	floor.shader = FLOOR
	for k: String in ["ceramic_color", "ceramic_normal", "ceramic_rough", "local_mask", "stock_mask"]:
		var file: String = {"ceramic_color": "ceramic_color.jpg", "ceramic_normal": "ceramic_normal.png",
			"ceramic_rough": "ceramic_rough.jpg", "local_mask": "ceramic_local.png", "stock_mask": "stock_floor.png"}[k]
		floor.set_shader_parameter(k, load(MAPS + file))
	var stock := floor.duplicate() as ShaderMaterial
	stock.set_shader_parameter("stockroom", true)
	var edge := StandardMaterial3D.new()
	edge.albedo_color = Color(.145,.123,.100)
	edge.roughness = .94
	for child: Node in $CeramicFloor.find_children("*", "MeshInstance3D", true, false):
		var m := child as MeshInstance3D
		m.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		for s in range(m.mesh.get_surface_count()):
			var source: Material = m.mesh.surface_get_material(s)
			if source and "Ceramic photo" in source.resource_name:
				m.set_surface_override_material(s, stock if m.name == "TileSurface_3" else floor)
			elif source and "Ceramic edge" in source.resource_name:
				m.set_surface_override_material(s, edge)
	var cracked := ShaderMaterial.new()
	cracked.shader = GLASS
	cracked.set_shader_parameter("case_map", load(MAPS + "case_cracks.png"))
	var clear := StandardMaterial3D.new()
	clear.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	clear.cull_mode = BaseMaterial3D.CULL_DISABLED
	clear.roughness = .16
	clear.albedo_color = Color(.64,.66,.63,.17)
	for child: Node in $Model.find_children("*", "MeshInstance3D", true, false):
		var m := child as MeshInstance3D
		if m.name in ["Room", "WallEast", "WallWest", "WallRear", "Ceiling", "StockWalls", "WashroomShell", "Corridor"]:
			m.gi_mode = GeometryInstance3D.GI_MODE_STATIC
		if m.name == "WindowGlass":
			m.hide()
		elif m.name == "CaseGlass":
			m.material_override = cracked
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		elif "Glass" in m.name or m.name == "Fragments":
			m.material_override = clear
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		else:
			for s in range(m.mesh.get_surface_count()):
				var source := m.mesh.surface_get_material(s) as StandardMaterial3D
				if source == null:
					continue
				source.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
				if m.name in ["WallEast", "WallWest", "WallRear"]:
					var plaster := ShaderMaterial.new()
					plaster.shader = WALL
					plaster.set_shader_parameter("wall_color", source.albedo_texture)
					plaster.set_shader_parameter("wall_normal", source.normal_texture)
					plaster.set_shader_parameter("wall_orm", source.roughness_texture)
					plaster.set_shader_parameter("plaster_normal", load(MAPS + "painted_plaster_wall_nor_gl_4k.jpg"))
					plaster.set_shader_parameter("rear_wall", m.name == "WallRear")
					m.set_surface_override_material(s, plaster)
