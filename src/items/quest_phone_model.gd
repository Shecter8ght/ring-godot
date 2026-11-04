class_name QuestPhoneModel
extends Node3D
## Accepted graphite finish, baked from factory_v01. Screen remains a separate surface.

const MODEL := "res://assets/items/models/quest_phone/quest_phone.glb"
const MAPS := "res://assets/items/models/quest_phone/quest_phone_%s.png"
const TRIANGLE_LIMIT := 5000
const BODY_SIZE := Vector3(0.0776, 0.163, 0.00825)

var screen: MeshInstance3D


func _ready() -> void:
	prepare()


func prepare() -> void:
	var body := StandardMaterial3D.new()
	body.resource_name = "QuestPhone · baked graphite"
	body.albedo_texture = load(MAPS % "albedo") as Texture2D
	body.roughness = 1.0
	body.metallic = 1.0
	body.roughness_texture = load(MAPS % "orm") as Texture2D
	body.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	body.metallic_texture = body.roughness_texture
	body.metallic_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_BLUE
	body.ao_enabled = true
	body.ao_texture = body.roughness_texture
	body.ao_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	body.normal_enabled = true
	body.normal_texture = load(MAPS % "normal") as Texture2D
	body.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	var off := StandardMaterial3D.new()
	off.resource_name = "QuestPhone · display off"
	off.albedo_color = Color(0.09, 0.092, 0.096)
	off.roughness = 0.055
	for raw: Node in find_children("*", "MeshInstance3D", true, false):
		var mesh := raw as MeshInstance3D
		if mesh.name == "DisplaySurface":
			screen = mesh
			mesh.material_override = off
		elif mesh.name in ["CameraGlass", "CameraOptics"]:
			var glass := ShaderMaterial.new()
			glass.shader = preload("res://src/items/quest_phone_glass.gdshader")
			glass.set_shader_parameter("optical_coating", mesh.name == "CameraOptics")
			mesh.material_override = glass
		else:
			mesh.material_override = body


func show_screen(texture: Texture2D) -> void:
	if screen == null:
		prepare()
	if screen == null:
		return
	var material := StandardMaterial3D.new()
	material.resource_name = "QuestPhone · live display"
	material.albedo_texture = texture
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
	screen.material_override = material
