class_name DozorAsset
extends RefCounted
## Approved working100 art only. Inventory, prices, controls and hand poses are separate.

const DIRECTORY: String = "res://assets/models/attachments/dozor/"
const TRIANGLE_LIMIT: int = 5000
static var _materials: Dictionary = {}


static func flashlight(variant: String = "f1", mounted: bool = false) -> Node3D:
	assert(variant in ["f1", "f1m", "f1s"])
	var scene: PackedScene = load(DIRECTORY + "dozor_" + variant + ".gltf") as PackedScene
	var model: Node3D = scene.instantiate() as Node3D
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = raw as MeshInstance3D
		if String(mesh.name).begins_with("Lens"):
			mesh.material_override = _glass()
		else:
			mesh.material_override = _opaque(variant, "f1")
		if String(mesh.name).begins_with("Clip"):
			mesh.visible = not mounted
	return model


static func mount() -> Node3D:
	var scene: PackedScene = load(DIRECTORY + "dozor_p.gltf") as PackedScene
	var model: Node3D = scene.instantiate() as Node3D
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		(raw as MeshInstance3D).material_override = _opaque("p", "p")
	return model


static func _opaque(variant: String, atlas: String) -> StandardMaterial3D:
	if _materials.has(variant):
		return _materials[variant] as StandardMaterial3D
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	mat.albedo_texture = load(DIRECTORY + "dozor_" + variant + "_base_color.png") as Texture2D
	var orm: Texture2D = load(DIRECTORY + "dozor_" + atlas + "_orm.png") as Texture2D
	# The accepted Painter/Blender preview uses color, roughness, metal and normal;
	# its exported AO channel is not connected. Match it, and use scene SSAO.
	mat.ao_enabled = false
	mat.ao_texture = orm
	mat.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	mat.roughness_texture = orm
	mat.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	mat.metallic = 1.0
	mat.metallic_texture = orm
	mat.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
	mat.normal_enabled = true
	mat.normal_texture = load(DIRECTORY + "dozor_" + atlas + "_normal.png") as Texture2D
	_materials[variant] = mat
	return mat


static func _glass() -> ShaderMaterial:
	if not _materials.has("glass"):
		var mat: ShaderMaterial = ShaderMaterial.new()
		mat.shader = load("res://src/combat/dozor_glass.gdshader") as Shader
		_materials["glass"] = mat
	return _materials["glass"] as ShaderMaterial


static func collision(is_mount: bool = false) -> Shape3D:
	if is_mount:
		var box: BoxShape3D = BoxShape3D.new()
		box.size = Vector3(0.045, 0.045, 0.035)
		return box
	var shape: ConvexPolygonShape3D = ConvexPolygonShape3D.new()
	var points: PackedVector3Array = PackedVector3Array()
	for profile: Vector2 in [Vector2(0.0805, 0.017), Vector2(0.044, 0.014), Vector2(-0.0385, 0.0127), Vector2(-0.0625, 0.0135)]:
		for i: int in range(16):
			var angle: float = TAU * i / 16.0
			points.append(Vector3(cos(angle) * profile.y, sin(angle) * profile.y, profile.x))
	for x: float in [-0.0021, 0.0021]:
		for z: float in [-0.037, 0.030]:
			points.append(Vector3(x, 0.0175, z))
	shape.points = points
	return shape


static func collision_node(is_mount: bool = false) -> CollisionShape3D:
	var node: CollisionShape3D = CollisionShape3D.new()
	node.shape = collision(is_mount)
	if is_mount:
		node.position.y = 0.018
	return node
