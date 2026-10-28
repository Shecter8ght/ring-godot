@tool
extends Node3D
## Серый объём общежития из данных. Каждый этаж и лестница — отдельный узел сцены.
## Предпросмотр не сохраняет созданные меши в tscn; этап 2 заменит их модулями Blender.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const StudyDoor = preload("res://src/blockout/dorm_study_door.gd")

@export var section_id: String = "Site"
@export_file("*.json") var plan_path: String = "res://data/blockouts/dorm.json"
@export_tool_button("Пересобрать из JSON") var rebuild_action: Callable = rebuild


func _ready() -> void:
	rebuild()


func rebuild() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()
	if not FileAccess.file_exists(plan_path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
	if not parsed is Dictionary:
		push_error("dorm: не прочитан " + plan_path)
		return
	var plan: Dictionary = parsed as Dictionary
	var section: Dictionary = (plan.get("sections", {}) as Dictionary).get(section_id, {})
	if section.is_empty():
		return
	var palette: Dictionary = _palette(plan)
	_build_geometry(self,section,palette)
	for group_name: String in section.get("groups",{}):
		var group: Node3D = Node3D.new()
		group.name = group_name
		group.add_to_group("dorm_detail_"+group_name)
		add_child(group)
		_build_geometry(group,section.groups[group_name],palette)
	for item: Dictionary in section.get("lights", []):
		var lamp: Light3D = SpotLight3D.new() if String(item.get("type","omni"))=="spot" else OmniLight3D.new()
		lamp.name = String(item.get("id","StudyFill"))
		lamp.position = _vec(item.at)
		lamp.light_color = Color(String(item.get("color","eef5ff")))
		lamp.light_energy = float(item.energy)
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		lamp.shadow_enabled = bool(item.get("shadow",true))
		lamp.visible = bool(item.get("on",true))
		lamp.shadow_bias = 0.025
		lamp.set_meta("light_group",String(item.get("group","legacy")))
		lamp.add_to_group("dorm_lamps")
		if bool(item.get("sky_fill",false)):
			lamp.add_to_group("dorm_window_sky")
			lamp.shadow_blur = 2.0
		if lamp is SpotLight3D:
			var spot: SpotLight3D = lamp as SpotLight3D
			spot.rotation_degrees.x = -90.0
			if item.has("rotation"):
				spot.rotation_degrees = _vec(item.rotation)
			spot.spot_range = float(item.range)
			spot.spot_angle = float(item.get("angle",68.0))
			spot.spot_attenuation = float(item.get("attenuation",1.7))
		else:
			var omni: OmniLight3D = lamp as OmniLight3D
			omni.omni_range = float(item.range)
			omni.omni_shadow_mode = OmniLight3D.SHADOW_DUAL_PARABOLOID
		add_child(lamp)
	for item: Dictionary in section.get("probes", []):
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.name = String(item.get("id","BathroomReflection"))
		probe.position = _vec(item.at)
		probe.size = _vec(item.size)+Vector3(0.1,0.1,0.1)
		probe.blend_distance = float(item.get("blend",0.05))
		probe.interior = true
		probe.box_projection = true
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.max_distance = float(item.get("max_distance",12.0))
		probe.intensity = float(item.get("intensity",1.0))
		probe.enable_shadows = bool(item.get("shadows",true))
		probe.ambient_mode = ReflectionProbe.AMBIENT_DISABLED
		probe.add_to_group("dorm_reflections")
		add_child(probe)


func _build_geometry(target: Node3D, data: Dictionary, palette: Dictionary) -> void:
	var builder: RefCounted = Geometry.new(target,palette)
	for item: Dictionary in data.get("boxes",[]):
		if String(item.mat)=="mirror":
			# Отдельная поверхность получает пробу своей комнаты, а не всего этажа.
			var surface: MeshInstance3D = MeshInstance3D.new()
			surface.name = "StudyMirror"
			var shape: BoxMesh = BoxMesh.new()
			shape.size = _vec(item.size)
			surface.mesh = shape
			surface.material_override = palette["mirror"] as Material
			surface.position = _vec(item.at)
			target.add_child(surface)
		else:
			builder.call("box",_vec(item.at),_vec(item.size),String(item.mat),bool(item.solid),deg_to_rad(float(item.yaw)))
	for item: Dictionary in data.get("beams",[]):
		var start: Vector3 = _vec(item.start)
		var end: Vector3 = _vec(item.end)
		if absf(start.x-end.x)<0.001 and absf(start.z-end.z)<0.001:
			builder.call("box",(start+end)*0.5,Vector3(float(item.width),absf(end.y-start.y),float(item.depth)),String(item.mat),bool(item.solid))
		else:
			builder.call("beam",start,end,float(item.width),float(item.depth),String(item.mat),bool(item.solid))
	for item: Dictionary in data.get("stairs",[]):
		builder.call("stairs",_vec(item.start),_vec(item.end),float(item.width),int(item.count),String(item.mat))
	builder.call("finish")
	for item: Dictionary in data.get("labels",[]):
		var plaque: Label3D = Label3D.new()
		plaque.name = "RoomNumber" if bool(item.get("permanent",false)) else "StudyLabel"
		plaque.text = String(item.text)
		plaque.position = _vec(item.at)
		plaque.rotation_degrees.y = float(item.yaw)
		plaque.font_size = 36
		plaque.pixel_size = 0.005
		plaque.modulate = Color("24282b")
		plaque.outline_size = 2
		plaque.outline_modulate = Color("c9cdd0")
		plaque.no_depth_test = false
		plaque.add_to_group("dorm_door_numbers" if bool(item.get("permanent",false)) else "dorm_study_labels")
		target.add_child(plaque)
	for item: Dictionary in data.get("doors",[]):
		var leaf: Node3D = StudyDoor.new() as Node3D
		leaf.name = String(item.id)
		leaf.set("data",item)
		leaf.set("materials",palette)
		target.add_child(leaf)


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]), float(values[1]), float(values[2]))


static func _palette(plan: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	var colors: Dictionary = {"wall": "a9adb0", "floor": "777d83", "slab": "8c9195", "frame": "626970",
		"rail": "444a50", "sealed": "555b60", "ground": "656b66", "paving": "85898b", "tree": "646b67", "glass": "88969e",
		"mattress": "a39d89", "wood": "766449", "ceramic": "d5d9ce", "basin": "8d9996", "mirror": "f0f0ed",
		"ceiling":"777d83", "skirting":"4d554d", "reveal":"dfe1d9", "radiator":"c0c6bc",
		"door_green":"596350", "door_wood":"75634f", "panel":"656a65", "fire_cabinet":"824b43"}
	for key: String in colors:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = Color(String(colors[key]))
		material.roughness = 0.95
		if key == "glass":
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			material.albedo_color.a = 0.07
			material.cull_mode = BaseMaterial3D.CULL_DISABLED
			material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		if key == "mirror":
			material.metallic = 1.0
			material.roughness = 0.025
		result[key] = material
	var levels: Array = plan.scale.floor_y
	var heights: Array = plan.scale.ceiling_clear
	for key: String in ["wall", "tile", "tile_floor"]:
		var finish: ShaderMaterial = ShaderMaterial.new()
		finish.shader = preload("res://src/blockout/dorm_finish.gdshader")
		finish.set_shader_parameter("finish_mode", 0 if key=="wall" else 1)
		finish.set_shader_parameter("floors", Vector4(float(levels[0]),float(levels[1]),float(levels[2]),float(levels[3])))
		finish.set_shader_parameter("fifth_floor", float(levels[4]))
		finish.set_shader_parameter("heights", Vector4(float(heights[0]),float(heights[1]),float(heights[2]),float(heights[3])))
		finish.set_shader_parameter("green", Color(String(plan.finish.green)))
		finish.set_shader_parameter("white", Color(String(plan.finish.white)))
		var main_rect: Array = plan.main_rect
		var annex_rect: Array = plan.annex_rect
		finish.set_shader_parameter("main_bounds",Vector4(float(main_rect[0]),float(main_rect[1]),float(main_rect[2]),float(main_rect[3])))
		finish.set_shader_parameter("annex_bounds",Vector4(float(annex_rect[0]),float(annex_rect[1]),float(annex_rect[2]),float(annex_rect[3])))
		if key=="tile_floor":
			finish.set_shader_parameter("tile_color",Color("939d94"))
		result[key] = finish
	return result
