extends Node3D
## Магазины ВЕРАС-54 в движке (tools/veras54_mags): магазин на 45 и барабан на 60 — игровая модель и мировая.
## Проверяет узлы (корпус, подаватель / ключ, патроны Round_NN), габарит, треугольники, карты материала, маски износа и
## жировой плёнки, шейдер износа (WeaponCondition) при прочности 100 и 25 %.
## tools/godot.cmd --headless res://tools/veras54_mags_check.tscn — только проверка (код выхода 1 — есть ошибки);
## с окном (--windowed --resolution 1600x900) — ещё снимки docs/screens/veras54_mags_*.png.

const DIR := "res://assets/models/weapons/veras54_mags/"
## габарит high-poly в осях игры (X — ширина, Y — высота, Z — к дулу), мм; игровая сетка отходит не больше чем на 1 мм
const MAGS := {
	"veras54_mag45": {"rounds": 45, "size_mm": Vector3(34.0, 260.74, 155.18), "moving": "MagazineFollower", "tag": "veras54_Mag45_100"},
	"veras54_drum60": {"rounds": 8, "size_mm": Vector3(114.0, 182.67, 103.96), "moving": "DrumKey", "tag": "veras54_Drum60_100"},
}
const SIZE_TOL_MM := 1.5

var _errors: Array[String] = []
var _cam: Camera3D


func _ready() -> void:
	var shots: bool = DisplayServer.get_name() != "headless"
	if shots:
		_stage()
	var x: float = 0.0
	for name: String in MAGS:
		var spec: Dictionary = MAGS[name]
		var model: Node3D = _check(name, spec, false)
		var world: Node3D = _check(name + "_world", spec, true)
		if model == null:
			continue
		if world:
			world.queue_free()
		if shots:
			model.position = Vector3(x, 0.0, 0.0)
			x += 0.5
			await _shots(name, model)
		model.queue_free()
	for e: String in _errors:
		print("veras54_mags_check: ОШИБКА ", e)
	print("veras54_mags_check: ", "PASS" if _errors.is_empty() else "FAIL (%d)" % _errors.size())
	get_tree().quit(0 if _errors.is_empty() else 1)


func _fail(msg: String) -> void:
	_errors.append(msg)


func _check(name: String, spec: Dictionary, world: bool) -> Node3D:
	var path: String = DIR + name + ".gltf"
	var scene: PackedScene = load(path) as PackedScene
	if scene == null:
		_fail("%s: не загрузилась" % path)
		return null
	var root: Node3D = scene.instantiate() as Node3D
	add_child(root)
	var body: MeshInstance3D = root.find_child("Magazine", true, false) as MeshInstance3D
	if body == null:
		_fail("%s: нет узла Magazine" % name)
		return root
	if root.find_child(String(spec["moving"]), true, false) == null:
		_fail("%s: нет узла %s" % [name, spec["moving"]])
	var rounds: int = 0
	var tris: int = 0
	var box: AABB = AABB()
	var first: bool = true
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		if String(mi.name).begins_with("Round_"):
			rounds += 1
		for s: int in range(mi.mesh.get_surface_count()):
			var arr: Array = mi.mesh.surface_get_arrays(s)
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX] as PackedInt32Array
			tris += (idx.size() if idx.size() > 0 else (arr[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()) / 3
		var b: AABB = mi.global_transform * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	var want_rounds: int = 2 if world else int(spec["rounds"])
	if rounds != want_rounds:
		_fail("%s: патронов %d, нужно %d" % [name, rounds, want_rounds])
	for i: int in range(1, want_rounds + 1):
		if root.find_child("Round_%02d" % i, true, false) == null:
			_fail("%s: нет Round_%02d" % [name, i])
	var size_mm: Vector3 = box.size * 1000.0
	if not world:
		var want: Vector3 = spec["size_mm"]
		for a: int in range(3):
			if absf(size_mm[a] - want[a]) > SIZE_TOL_MM:
				_fail("%s: габарит %s мм, у high-poly %s" % [name, size_mm, want])
				break
	var mat: StandardMaterial3D = body.mesh.surface_get_material(0) as StandardMaterial3D
	var tag: String = String(spec["tag"])
	if mat == null or mat.albedo_texture == null or not mat.albedo_texture.resource_path.ends_with(tag + "_albedo.png"):
		_fail("%s: нет карты цвета %s_albedo.png" % [name, tag])
	elif not (mat.normal_enabled and mat.normal_texture and mat.roughness_texture and mat.metallic_texture and mat.ao_enabled):
		_fail("%s: в материале не все карты (нормали, ORM)" % name)
	elif not (mat.emission_enabled and mat.emission_texture):
		_fail("%s: нет свечения цифр" % name)
	for m: String in ["_wear.png", "_coat.png"]:
		if not ResourceLoader.exists(DIR + tag + m):
			_fail("%s: нет %s%s" % [name, tag, m])
	WeaponCondition.apply_visual(root, {"id": "", "dur": 100.0})
	if not root.get_meta("wear_shader", false):
		_fail("%s: шейдер износа не встал" % name)
	print("veras54_mags_check: %s — треугольников %d, патронов %d, габарит %.1f × %.1f × %.1f мм" % [
		name, tris, rounds, size_mm.x, size_mm.y, size_mm.z])
	return root


func _stage() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.25, 0.27, 0.3)
	sky_mat.sky_horizon_color = Color(0.4, 0.4, 0.42)
	sky_mat.ground_bottom_color = Color(0.05, 0.05, 0.05)
	sky_mat.ground_horizon_color = Color(0.3, 0.3, 0.3)
	sky.sky_material = sky_mat
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.03, 0.03, 0.03)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.sky = sky
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-40.0, 35.0, 0.0)
	key.light_energy = 2.2
	key.shadow_enabled = true
	add_child(key)
	var fill := OmniLight3D.new()
	fill.position = Vector3(-0.6, 0.4, 0.8)
	fill.omni_range = 4.0
	fill.light_energy = 0.8
	add_child(fill)
	_cam = Camera3D.new()
	_cam.fov = 40.0
	_cam.near = 0.01
	add_child(_cam)
	_cam.make_current()


func _shots(name: String, model: Node3D) -> void:
	var box: AABB = AABB()
	var first: bool = true
	for raw: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		var b: AABB = mi.global_transform * mi.get_aabb()
		box = b if first else box.merge(b)
		first = false
	var c: Vector3 = box.get_center()
	var r: float = box.size.length()
	for dur: float in [100.0, 25.0]:
		WeaponCondition.update_wear(model, dur)
		# 3/4 справа спереди (правая сторона стрелка — −X), сзади слева
		for view: Array in [["r34", Vector3(-0.8, 0.35, 0.6)], ["l34", Vector3(0.8, 0.3, -0.5)]]:
			_cam.position = c + (view[1] as Vector3).normalized() * r * 1.5
			_cam.look_at(c)
			for _i: int in range(20):
				await get_tree().process_frame
			var path: String = "res://docs/screens/veras54_mags_%s_%s_%d.png" % [name.trim_prefix("veras54_"), view[0], int(dur)]
			get_viewport().get_texture().get_image().save_png(path)
			print("veras54_mags_check: ", path)
