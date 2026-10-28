@tool
extends Node3D
## Серый объём общежития из данных. Каждый этаж и лестница — отдельный узел сцены.
## Предпросмотр не сохраняет созданные меши в tscn; этап 2 заменит их модулями Blender.

const Geometry = preload("res://src/blockout/study_geometry.gd")

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
	var builder: RefCounted = Geometry.new(self, _palette())
	for item: Dictionary in section.get("boxes", []):
		builder.call("box", _vec(item.at), _vec(item.size), String(item.mat), bool(item.solid), deg_to_rad(float(item.yaw)))
	for item: Dictionary in section.get("beams", []):
		var start: Vector3 = _vec(item.start)
		var end: Vector3 = _vec(item.end)
		if absf(start.x-end.x)<0.001 and absf(start.z-end.z)<0.001:
			# Вертикальной стойке не нужен поворот looking_at вдоль собственного up.
			builder.call("box", (start+end)*0.5, Vector3(float(item.width),absf(end.y-start.y),float(item.depth)), String(item.mat), bool(item.solid))
		else:
			builder.call("beam", start, end, float(item.width), float(item.depth), String(item.mat), bool(item.solid))
	for item: Dictionary in section.get("stairs", []):
		builder.call("stairs", _vec(item.start), _vec(item.end), float(item.width), int(item.count), String(item.mat))
	builder.call("finish")
	for item: Dictionary in section.get("labels", []):
		var plaque: Label3D = Label3D.new()
		plaque.name = "StudyLabel"
		plaque.text = String(item.text)
		plaque.position = _vec(item.at)
		plaque.rotation_degrees.y = float(item.yaw)
		plaque.font_size = 36
		plaque.pixel_size = 0.005
		plaque.modulate = Color("24282b")
		plaque.outline_size = 2
		plaque.outline_modulate = Color("c9cdd0")
		plaque.no_depth_test = false
		plaque.add_to_group("dorm_study_labels")
		add_child(plaque)
	for item: Dictionary in section.get("lights", []):
		var lamp: OmniLight3D = OmniLight3D.new()
		lamp.name = "StudyFill"
		lamp.position = _vec(item.at)
		lamp.light_color = Color(0.94, 0.96, 1.0)
		lamp.light_energy = float(item.energy)
		lamp.omni_range = float(item.range)
		lamp.shadow_enabled = true
		lamp.omni_shadow_mode = OmniLight3D.SHADOW_DUAL_PARABOLOID
		add_child(lamp)


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]), float(values[1]), float(values[2]))


static func _palette() -> Dictionary:
	var result: Dictionary = {}
	var colors: Dictionary = {"wall": "a9adb0", "floor": "777d83", "slab": "8c9195", "frame": "626970",
		"rail": "444a50", "sealed": "555b60", "ground": "656b66", "paving": "85898b", "tree": "646b67", "glass": "88969e"}
	for key: String in colors:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = Color(String(colors[key]))
		material.roughness = 0.95
		if key == "glass":
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			material.albedo_color.a = 0.07
			material.cull_mode = BaseMaterial3D.CULL_DISABLED
			material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		result[key] = material
	return result
