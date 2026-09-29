extends Node3D
## Визуальная проверка попаданий по всем видам поверхности крупным планом.
## tools/godot.cmd res://tools/impact_gallery.tscn → docs/screens/impact_gallery_*.png

const SURFACES: Array[String] = [
	"concrete", "tile", "asphalt",
	"metal", "wood", "cardboard",
	"plastic", "fabric", "glass",
]
const COLORS := {
	"concrete": Color(0.52, 0.5, 0.46),
	"tile": Color(0.8, 0.79, 0.75),
	"asphalt": Color(0.18, 0.18, 0.17),
	"metal": Color(0.32, 0.36, 0.39),
	"wood": Color(0.42, 0.24, 0.11),
	"cardboard": Color(0.5, 0.36, 0.2),
	"plastic": Color(0.2, 0.25, 0.31),
	"fabric": Color(0.2, 0.16, 0.25),
}


func _ready() -> void:
	_world()
	var bodies: Array[StaticBody3D] = []
	for index: int in range(SURFACES.size() - 1):
		bodies.append(_panel(SURFACES[index], _cell_position(index)))
	var glass := GlassPanes.new()
	var glass_pos := _cell_position(SURFACES.size() - 1)
	glass.setup([{
		"xf": Transform3D(Basis.IDENTITY, glass_pos),
		"size": Vector2(1.55, 1.55),
		"floor_y": glass_pos.y - 0.9,
		"sill": Vector3(1.65, 0.12, 0.18),
		"broken": false,
	}])
	add_child(glass)
	_label("glass", glass_pos)

	await get_tree().physics_frame
	for index: int in range(bodies.size()):
		var center := _cell_position(index) + Vector3(0, 0, 0.07)
		for offset: Vector2 in [Vector2(-0.34, 0.18), Vector2(0.05, -0.2), Vector2(0.34, 0.22)]:
			ImpactFx.spawn_hit({
				"position": center + Vector3(offset.x, offset.y, 0),
				"normal": Vector3.BACK,
				"collider": bodies[index],
			}, Vector3.FORWARD)
	glass.bullet(0, 18.0, glass_pos + Vector3(0.08, -0.04, 0.07))
	ImpactFx.spawn_hit({
		"position": glass_pos + Vector3(0.08, -0.04, 0.07),
		"normal": Vector3.BACK,
		"collider": glass.get_node("Glass"),
		"shape": 0,
	}, Vector3.FORWARD)

	await get_tree().create_timer(0.16).timeout
	_save("impact_gallery_particles.png")
	await get_tree().create_timer(1.2).timeout
	_save("impact_gallery_decals.png")
	var textured := 0
	var normal_mapped := 0
	for child: Node in get_children():
		if child is Decal:
			textured += int((child as Decal).texture_albedo != null)
			normal_mapped += int((child as Decal).texture_normal != null)
	print("impact_gallery: декалей %d, с albedo %d, с normal %d" % [_count_decals(), textured, normal_mapped])
	var camera: Camera3D = $Camera
	for index: int in [0, 3, 4]:
		var point: Vector3 = _cell_position(index) + Vector3(0, 0, 0.065)
		camera.look_at_from_position(point + Vector3(0.45, 0.2, 2.0), point, Vector3.UP)
		await get_tree().create_timer(0.25).timeout
		ImpactFx.spawn_hit({"position": point, "normal": Vector3.BACK, "collider": bodies[index]}, Vector3.FORWARD)
		await get_tree().create_timer(0.065).timeout
		_save("impact_%s_close.png" % SURFACES[index])
		if index == 0:
			await get_tree().create_timer(0.2).timeout
			_save("impact_concrete_dust.png")
		await get_tree().create_timer(1.0).timeout
	get_tree().quit(0)


func _world() -> void:
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.055, 0.06, 0.07)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.42, 0.48, 0.58)
	environment.ambient_light_energy = 0.65
	environment.tonemap_mode = Environment.TONE_MAPPER_AGX
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)
	var light := DirectionalLight3D.new()
	light.light_color = Color(1.0, 0.82, 0.65)
	light.light_energy = 1.6
	light.rotation_degrees = Vector3(-32, -28, 0)
	light.shadow_enabled = true
	add_child(light)
	var camera := Camera3D.new()
	camera.name = "Camera"
	camera.position = Vector3(0, 2.65, 10.5)
	camera.fov = 46.0
	add_child(camera)
	camera.look_at_from_position(camera.position, Vector3(0, 2.65, 0), Vector3.UP)


func _cell_position(index: int) -> Vector3:
	var column := index % 3
	var row := index / 3
	return Vector3((column - 1) * 2.05, 4.72 - row * 2.05, 0)


func _panel(kind: String, pos: Vector3) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = kind.capitalize()
	body.set_meta("surface", kind)
	body.position = pos
	var shape := BoxShape3D.new()
	shape.size = Vector3(1.55, 1.55, 0.12)
	var collision := CollisionShape3D.new()
	collision.shape = shape
	body.add_child(collision)
	var box := BoxMesh.new()
	box.size = shape.size
	var mesh := MeshInstance3D.new()
	mesh.mesh = box
	var material := StandardMaterial3D.new()
	material.albedo_color = COLORS[kind]
	material.roughness = 0.72 if kind != "metal" else 0.34
	material.metallic = 0.0 if kind != "metal" else 0.65
	mesh.material_override = material
	body.add_child(mesh)
	add_child(body)
	_label(kind, pos)
	return body


func _label(text: String, pos: Vector3) -> void:
	var label := Label3D.new()
	label.text = text.to_upper()
	label.font_size = 34
	label.outline_size = 8
	label.position = pos + Vector3(0, 0.98, 0.12)
	add_child(label)


func _save(file_name: String) -> void:
	var path := ProjectSettings.globalize_path("res://docs/screens/%s" % file_name)
	get_viewport().get_texture().get_image().save_png(path)


func _count_decals() -> int:
	var count := 0
	for child: Node in get_children():
		if child is Decal:
			count += 1
	return count
