extends Node3D
## Радиатор с патрубками (предмет car_radiator) в движке: модель предмета (ItemModels — как в точках заказа и на
## полу) стоит и лежит, как уроненная (LooseLoot.lay_item), на бетонном полу под солнцем. Снимки от первого лица
## вблизи, на рабочем расстоянии и издали (переходы LOD) → docs/screens/car_radiator_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/car_radiator_shots.tscn

const ID := "car_radiator"
const EYE := 1.6

var _cam: Camera3D


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.32, 0.45, 0.66)
	sky_mat.sky_horizon_color = Color(0.68, 0.72, 0.78)
	sky_mat.ground_horizon_color = Color(0.5, 0.5, 0.5)
	sky.sky_material = sky_mat
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	e.ssao_enabled = true
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-48.0, -35.0, 0.0)
	sun.light_energy = 1.6
	sun.shadow_enabled = true
	add_child(sun)
	var floor_mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(40.0, 40.0)
	floor_mi.mesh = plane
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.42, 0.42, 0.4)
	fm.roughness = 0.9
	floor_mi.material_override = fm
	add_child(floor_mi)
	# стоит, как в точке заказа (QuestSite: низ модели на полу), и лежит, как уронили
	var standing := Node3D.new()
	add_child(standing)
	var model: Node3D = ItemModels.build(ID)
	standing.add_child(model)
	model.position.y = -ItemModels.bounds(model).position.y
	var laid := Node3D.new()
	laid.position = Vector3(1.4, 0.0, 0.6)
	add_child(laid)
	LooseLoot.lay_item(laid, ID, deg_to_rad(25.0))
	_cam = Camera3D.new()
	_cam.fov = 75.0
	add_child(_cam)
	_cam.make_current()
	var box: AABB = ItemModels.bounds(model)
	print("car_radiator_shots: габарит модели, м: ", box.size)
	# крупно, на вытянутую руку (координаты — после центровки модели ItemModels: перёд — +Z, патрубки — −Z)
	await _shot("near", Vector3(0.15, 0.45, 0.45), Vector3(0.1, 0.22, 0.1))
	await _shot("tag", Vector3(0.56, 0.12, -0.27), Vector3(0.438, 0.1, 0.004))
	await _shot("hose_end", Vector3(0.09, 0.24, -0.22), Vector3(0.35, 0.21, -0.083))
	await _shot("neck", Vector3(0.62, 0.32, -0.2), Vector3(0.43, 0.2, 0.0))
	await _shot("work", Vector3(-0.6, EYE, 1.8), Vector3(0.3, 0.2, 0.2))
	await _shot("back", Vector3(0.9, EYE - 0.3, -1.4), Vector3(0.0, 0.2, 0.0))
	await _shot("laid", Vector3(1.0, EYE, 2.1), Vector3(1.4, 0.05, 0.6))
	await _shot("far", Vector3(-2.0, EYE, 12.0), Vector3(0.5, 0.2, 0.3))
	get_tree().quit(0)


func _shot(tag: String, eye: Vector3, at: Vector3) -> void:
	_cam.position = eye
	_cam.look_at(at)
	for _i: int in range(30):
		await get_tree().process_frame
	var path: String = "res://docs/screens/car_radiator_%s.png" % tag
	get_viewport().get_texture().get_image().save_png(path)
	print("car_radiator_shots: ", path)
