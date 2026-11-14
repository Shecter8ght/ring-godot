extends Node3D
## Навесной замок (assets/models/props/padlock_01) в движке: нейтральная подложка, дневное солнце.
## Кадры: лицо с 0,4 м, тыл три четверти, с 2 м (LOD0 слева и LOD1 справа) → docs/screens/padlock_*.png.
## Узлы модели: Body, Shackle (начало — на оси ноги дужки) и их LOD1 — Body_lod1, Shackle_lod1.
## PADLOCK_MODE=albedo | flat — отладка: без освещения / без карты нормалей (кадры с приставкой режима).
## MSYS_NO_PATHCONV=1 cmd /c "tools\godot.cmd --windowed --resolution 1280x720 res://tools/padlock_shots.tscn"

const MODEL := "res://assets/models/props/padlock_01/padlock_01.gltf"

var _cam: Camera3D
var _lod0: Node3D
var _lod1: Node3D


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
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-40.0, -20.0, 0.0)
	sun.light_energy = 1.6
	sun.shadow_enabled = true
	add_child(sun)
	var floor_mi := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(20.0, 20.0)
	floor_mi.mesh = plane
	var fm := StandardMaterial3D.new()
	fm.albedo_color = Color(0.42, 0.42, 0.4)
	fm.roughness = 0.9
	floor_mi.material_override = fm
	add_child(floor_mi)
	var scene: PackedScene = load(MODEL)
	_lod0 = _make(scene, Vector3(-0.07, 0.0, 0.0), false)
	_lod1 = _make(scene, Vector3(0.07, 0.0, 0.0), true)
	# PADLOCK_MODE: albedo — без освещения (проверка карт цвета и развёртки), flat — без карты нормалей
	var mode: String = OS.get_environment("PADLOCK_MODE")
	if mode != "":
		for mi: Node in _lod0.find_children("*", "MeshInstance3D", true, false):
			var m: Material = (mi as MeshInstance3D).get_active_material(0)
			if m is StandardMaterial3D:
				var sm: StandardMaterial3D = (m as StandardMaterial3D).duplicate()
				if mode == "albedo":
					sm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
				elif mode == "flat":
					sm.normal_enabled = false
				(mi as MeshInstance3D).material_override = sm
	_cam = Camera3D.new()
	_cam.fov = 28.0
	add_child(_cam)
	_cam.make_current()
	# на подложке стоит основанием; перёд (скважина) — к +Z
	await _shot("front", _lod0.position + Vector3(0.0, 0.07, 0.4), _lod0.position + Vector3(0.0, 0.06, 0.0), true)
	await _shot("detail", _lod0.position + Vector3(0.02, 0.03, 0.16), _lod0.position + Vector3(0.02, 0.02, 0.0), true)
	# тыл три четверти: модель повёрнута спиной к камере и чуть в сторону, свет прежний
	_lod0.rotation_degrees.y = 180.0 + 35.0
	await _shot("rear", _lod0.position + Vector3(0.0, 0.09, 0.4), _lod0.position + Vector3(0.0, 0.06, 0.0), true)
	_lod0.rotation_degrees.y = 0.0
	_cam.fov = 12.0
	await _shot("far", Vector3(0.0, 0.5, 2.0), Vector3(0.0, 0.06, 0.0), false)
	_cam.fov = 28.0
	await _shot("lod1_near", _lod1.position + Vector3(0.0, 0.07, 0.4), _lod1.position + Vector3(0.0, 0.06, 0.0), false)
	get_tree().quit(0)


## Копия модели: LOD0 или LOD1 (ненужные узлы выключены).
func _make(scene: PackedScene, pos: Vector3, lod1: bool) -> Node3D:
	var n: Node3D = scene.instantiate()
	add_child(n)
	n.position = pos
	# узлы модели лежат под корнем glTF (padlock_01): LOD выбирается по имени сетки, а не по детям сцены
	for c: Node in n.find_children("*", "MeshInstance3D", true, false):
		var is_lod: bool = String(c.name).ends_with("_lod1")
		(c as Node3D).visible = is_lod == lod1
	var box := AABB()
	var first := true
	for c: Node in n.find_children("*", "MeshInstance3D", true, false):
		var mi := c as MeshInstance3D
		if not mi.is_visible_in_tree():
			continue
		var b: AABB = mi.global_transform * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	print("padlock_shots: ", "LOD1" if lod1 else "LOD0", " габарит, м: ", box.size, " низ y=", box.position.y)
	return n


func _shot(tag: String, eye: Vector3, at: Vector3, only_lod0: bool) -> void:
	_lod1.visible = not only_lod0
	_cam.position = eye
	_cam.look_at(at)
	for _i: int in range(30):
		await get_tree().process_frame
	var path: String = "res://docs/screens/padlock_%s%s.png" % [tag, ("_" + OS.get_environment("PADLOCK_MODE")) if OS.get_environment("PADLOCK_MODE") != "" else ""]
	get_viewport().get_texture().get_image().save_png(path)
	print("padlock_shots: ", path)
