@tool
extends Node3D
## Объёмы серого блокаута «Санатория» из плана data/blockouts/sanatorium.json (генератор — tools/build_sanatorium.py):
## коробки (стены по классу, плиты, площадки каскада, ряды амфитеатра, машины), марши (ступени видом и наклон
## для шага), наклонные ленты троп и служебной дороги, цилиндры (колонны, фонтаны, маяк), треугольники (асфальт и
## мощение по рельефу, мол, плотина вдали), вода (озеро, бассейны, фонтаны), подписи помещений и мест, выходы и
## заходы, невидимые стенки по границе карты и у воды, ели и сосны (модели зоны 1). Рельеф — соседние узлы
## Terrain и FarTerrain (HeliTerrain). Материалы — серые, по назначению; стекло полупрозрачное.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const WATER_SHADER: Shader = preload("res://src/world/district_water.gdshader")
const NOISE: String = "res://assets/terrain/zone01_noise.png"
const PLAN_PATH: String = "res://data/blockouts/sanatorium.json"
const VEG_PATH: String = "res://data/blockouts/sanatorium_vegetation.json"
## Порода → модель зоны 1 (и её «_far») и радиус ствола для коллизии; только ели и сосны (решение владельца 22).
const SPECIES: Dictionary = {
	"spruce_a": ["spruce_forest_a", 0.3], "spruce_b": ["spruce_forest_b", 0.3], "spruce_young": ["spruce_young_a", 0.2],
	"pine": ["pine_forest", 0.3], "pine_slim": ["pine_slim_a", 0.25],
}
## Цвета материалов блокаута: серые по назначению, чтобы читались постройки, настилы и покрытия.
const COLORS: Dictionary = {
	"facade": Color("b9b6ad"), "partition": Color("d3d0c6"), "struct": Color("9d9a92"), "glass": Color(0.62, 0.74, 0.8, 0.32),
	"slab": Color("8f8d87"), "floor": Color("a7a39a"), "roof": Color("4f5154"), "plinth": Color("85827a"),
	"stair": Color("a19c90"), "stone": Color("b0a993"), "rock": Color("6e6b65"), "planter": Color("6f7d5a"), "rail": Color("4a4c4f"),
	"parapet": Color("a59f8c"), "wood": Color("7a5e43"), "wood_dark": Color("5b4a3c"), "white": Color("e2dfd6"),
	"deck": Color("8d7356"), "logs": Color("6e5a42"), "trail": Color("7b6a4f"), "trail_strip": Color("7b6a4f"),
	"asphalt": Color("4c4f52"), "paving": Color("a39d8e"), "stripe": Color("d8d6cc"), "kiosk": Color("c3b89a"),
	"tile": Color("8fb1b8"), "metal": Color("5d6366"), "fence": Color("5e6560"), "fence_green": Color("4f7354"),
	"court": Color("6f7f74"), "brick": Color("8c5a48"), "eurocube": Color("d6d6d0"), "boat": Color("d8dad6"),
	"car_a": Color("5f6670"), "car_b": Color("7d3e36"), "car_c": Color("2f3d4c"), "car_d": Color("a7a8a2"),
	"barrier_red": Color("b8362c"), "play": Color("d6c9a7"), "play_red": Color("bf5a3c"), "rope": Color("7a6a4e"),
	"rubber_red": Color("8e4a40"), "rubber_green": Color("5c7a52"), "rubber_blue": Color("4e6787"), "rubber_dark": Color("2f3133"),
	"umbrella": Color("d08a4e"), "umbrella_pink": Color("d6768f"), "dam": Color("9c9a94"), "dam_dark": Color("6d6c68"),
}
## Подписи: на какой дальности ещё видны (м).
const LABEL_RANGE: Dictionary = {"room": 22.0, "unit": 70.0, "object": 90.0, "building": 650.0, "far": 6000.0}
const LABEL_PIXEL: Dictionary = {"room": 0.006, "unit": 0.012, "object": 0.01, "building": 0.03, "far": 0.4}
const LABEL_BEGIN: Dictionary = {"room": 1.2, "unit": 6.0, "object": 3.0, "building": 45.0, "far": 400.0}

@export var build_trees: bool = true

var plan: Dictionary = {}
var generated: Node3D
var built_ms: int = 0


func _ready() -> void:
	rebuild()


func load_plan() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PLAN_PATH))
	if not parsed is Dictionary:
		push_error("Не прочитан план «Санатория»: " + PLAN_PATH)
		return
	plan = parsed as Dictionary


func rebuild() -> void:
	var started: int = Time.get_ticks_msec()
	load_plan()
	if plan.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Generated"
	add_child(generated)
	var palette: Dictionary = _palette()
	var g: RefCounted = Geometry.new(generated, palette)
	var mats: Array = plan.mats
	for b: Array in plan.boxes:
		g.call("box", Vector3(float(b[0]), float(b[1]), float(b[2])), Vector3(float(b[3]), float(b[4]), float(b[5])),
			String(mats[int(b[7])]), int(b[8]) == 1, deg_to_rad(float(b[6])))
	for s: Array in plan.stairs:
		_stair(g, s, mats)
	for b: Array in plan.beams:
		g.call("beam", Vector3(float(b[0]), float(b[1]), float(b[2])), Vector3(float(b[3]), float(b[4]), float(b[5])),
			float(b[6]), float(b[7]), String(mats[int(b[8])]), int(b[9]) == 1)
	for c: Array in plan.cyls:
		_cyl(g, c, mats)
	_tris(g)
	g.call("finish")
	for child: Node in generated.get_children():
		if child is MeshInstance3D:
			var key: String = String(child.name).trim_prefix("Mesh_")
			# асфальт и мощение — по рельефу, тень от них не нужна; стекло тень почти не даёт
			if key in ["asphalt", "paving", "stripe", "trail_strip", "court", "rubber_red", "rubber_green", "rubber_blue"]:
				(child as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_water()
	_labels()
	_markers()
	_barriers()
	if build_trees and not Engine.is_editor_hint():
		_trees()
	built_ms = Time.get_ticks_msec() - started


func _palette() -> Dictionary:
	var result: Dictionary = {}
	for key: Variant in plan.mats:
		var m: StandardMaterial3D = StandardMaterial3D.new()
		var c: Color = COLORS.get(String(key), Color("a0a093"))
		m.albedo_color = c
		m.roughness = 0.9
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		if String(key) == "glass":
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.roughness = 0.08
			m.metallic_specular = 0.8
		elif String(key) in ["metal", "rail", "car_a", "car_b", "car_c", "car_d", "boat"]:
			m.roughness = 0.5
			m.metallic = 0.3
		elif String(key) == "tile":
			m.roughness = 0.35
		result[String(key)] = m
	return result


## Марш: ступени видом (сплошные до fill — с коллизией, у винтовой лестницы — тонкие), шаг — по наклонной.
func _stair(g: RefCounted, s: Array, mats: Array) -> void:
	var bottom: Vector3 = Vector3(float(s[0]), float(s[1]), float(s[2]))
	var top: Vector3 = Vector3(float(s[3]), float(s[4]), float(s[5]))
	var width: float = float(s[6])
	var count: int = int(s[7])
	var key: String = String(mats[int(s[9])])
	if s[8] == null:
		g.call("stairs", bottom, top, width, count, key, true)
		return
	var fill: float = float(s[8])
	var delta: Vector3 = top - bottom
	var flat: Vector3 = Vector3(delta.x, 0.0, delta.z)
	var direction: Vector3 = flat.normalized()
	var yaw: float = -atan2(direction.x, -direction.z)
	for i: int in range(count):
		var k: float = (float(i) + 0.5) / float(count)
		var tread: float = bottom.y + delta.y * float(i + 1) / float(count)
		var at: Vector3 = bottom + flat * k
		var h: float = maxf(tread - fill, 0.05)
		at.y = tread - h * 0.5
		g.call("box", at, Vector3(width, h, flat.length() / float(count) + 0.01), key, true, yaw)
	g.call("stairs", bottom, top, width, count, key, false)


func _cyl(g: RefCounted, c: Array, mats: Array) -> void:
	var base: Vector3 = Vector3(float(c[0]), float(c[1]), float(c[2]))
	var r: float = float(c[3])
	var h: float = float(c[4])
	var key: String = String(mats[int(c[5])])
	var sides: int = int(c[7])
	for i: int in range(sides):
		var a0: float = TAU * float(i) / float(sides)
		var a1: float = TAU * float(i + 1) / float(sides)
		var p0: Vector3 = base + Vector3(cos(a0) * r, 0.0, sin(a0) * r)
		var p1: Vector3 = base + Vector3(cos(a1) * r, 0.0, sin(a1) * r)
		var up: Vector3 = Vector3.UP * h
		g.call("quad", p0, p1, p1 + up, p0 + up, key)
		g.call("tri", base + up, p0 + up, p1 + up, key)
		g.call("tri", base, p1, p0, key)
	if int(c[6]) == 1:
		var shape: CylinderShape3D = CylinderShape3D.new()
		shape.radius = r
		shape.height = h
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		cs.position = base + Vector3.UP * h * 0.5
		(g.get("body") as StaticBody3D).add_child(cs)


## Треугольники: ключ «материал|твёрдо». Покрытия по рельефу — нормалью вверх; твёрдые — ещё и коллизия.
func _tris(g: RefCounted) -> void:
	var tris: Dictionary = plan.tris
	for key: String in tris:
		var parts: PackedStringArray = key.split("|")
		var m: String = parts[0]
		var solid: bool = parts.size() > 1 and parts[1] == "1"
		var flat: Array = tris[key]
		var faces: PackedVector3Array = PackedVector3Array()
		var i: int = 0
		while i + 8 < flat.size():
			var a: Vector3 = Vector3(float(flat[i]), float(flat[i + 1]), float(flat[i + 2]))
			var b: Vector3 = Vector3(float(flat[i + 3]), float(flat[i + 4]), float(flat[i + 5]))
			var c: Vector3 = Vector3(float(flat[i + 6]), float(flat[i + 7]), float(flat[i + 8]))
			if (c - a).cross(b - a).y < 0.0:
				var t: Vector3 = b
				b = c
				c = t
			g.call("tri", a, b, c, m)
			if solid:
				faces.append_array([a, b, c])
			i += 9
		if solid and not faces.is_empty():
			var shape: ConcavePolygonShape3D = ConcavePolygonShape3D.new()
			shape.backface_collision = true
			shape.set_faces(faces)
			var cs: CollisionShape3D = CollisionShape3D.new()
			cs.shape = shape
			(g.get("body") as StaticBody3D).add_child(cs)


func _water() -> void:
	var root: Node3D = Node3D.new()
	root.name = "Water"
	generated.add_child(root)
	var lake: ShaderMaterial = ShaderMaterial.new()
	lake.shader = WATER_SHADER
	if ResourceLoader.exists(NOISE):
		lake.set_shader_parameter("noise_tex", load(NOISE))
	# нижнее озеро под плотиной: глубокая холодная вода
	lake.set_shader_parameter("deep_color", Color(0.05, 0.09, 0.1))
	lake.set_shader_parameter("murk_color", Color(0.12, 0.18, 0.17))
	lake.set_shader_parameter("depth_max", 3.0)
	var pool: StandardMaterial3D = StandardMaterial3D.new()
	pool.albedo_color = Color(0.32, 0.62, 0.7, 0.72)
	pool.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	pool.roughness = 0.06
	pool.cull_mode = BaseMaterial3D.CULL_DISABLED
	for body: Dictionary in plan.water:
		var level: float = float(body.level)
		var outline: PackedVector2Array = PackedVector2Array()
		if body.has("circle"):
			var c: Array = body.circle
			for k: int in range(28):
				var a: float = TAU * float(k) / 28.0
				outline.append(Vector2(float(c[0]) + cos(a) * float(c[2]), float(c[1]) + sin(a) * float(c[2])))
		else:
			for q: Array in body.poly:
				outline.append(Vector2(float(q[0]), float(q[1])))
		var tris: PackedInt32Array = Geometry2D.triangulate_polygon(outline)
		if tris.is_empty():
			push_warning("Санаторий: вода «%s» не разбита на треугольники" % String(body.name))
			continue
		var verts: PackedVector3Array = PackedVector3Array()
		var normals: PackedVector3Array = PackedVector3Array()
		for idx: int in tris:
			verts.append(Vector3(outline[idx].x, level, outline[idx].y))
			normals.append(Vector3.UP)
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = verts
		arrays[Mesh.ARRAY_NORMAL] = normals
		var mesh: ArrayMesh = ArrayMesh.new()
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
		mesh.surface_set_material(0, lake if String(body.name) == "Lake" else pool)
		var mi: MeshInstance3D = MeshInstance3D.new()
		mi.name = String(body.name)
		mi.mesh = mesh
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(mi)


func _labels() -> void:
	var root: Node3D = Node3D.new()
	root.name = "Labels"
	generated.add_child(root)
	for l: Array in plan.labels:
		var kind: String = String(l[5])
		var label: Label3D = Label3D.new()
		label.text = String(l[3])
		label.position = Vector3(float(l[0]), float(l[1]), float(l[2]))
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.pixel_size = float(LABEL_PIXEL.get(kind, 0.01)) * maxf(float(l[4]), 0.3)
		label.font_size = 48
		label.outline_size = 10
		label.modulate = Color(0.97, 0.96, 0.9) if kind != "room" else Color(0.92, 0.95, 1.0)
		label.visibility_range_end = float(LABEL_RANGE.get(kind, 60.0))
		label.visibility_range_end_margin = 4.0
		# крупные подписи построек и плотины вблизи не нужны — закрыли бы полэкрана
		label.visibility_range_begin = float(LABEL_BEGIN.get(kind, 0.0))
		label.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(label)


func _markers() -> void:
	var root: Node3D = Node3D.new()
	root.name = "Markers"
	generated.add_child(root)
	for m: Array in plan.markers:
		var exit: bool = String(m[0]) == "exit"
		var at: Vector3 = Vector3(float(m[1]), float(m[2]), float(m[3]))
		var pole: MeshInstance3D = MeshInstance3D.new()
		var cyl: CylinderMesh = CylinderMesh.new()
		cyl.top_radius = 0.18
		cyl.bottom_radius = 0.18
		cyl.height = 5.0
		pole.mesh = cyl
		var mat: StandardMaterial3D = StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(0.2, 0.85, 0.35) if exit else Color(0.3, 0.55, 1.0)
		pole.material_override = mat
		pole.position = at + Vector3.UP * 2.5
		pole.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		root.add_child(pole)
		var label: Label3D = Label3D.new()
		label.text = String(m[4])
		label.position = at + Vector3.UP * 5.6
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.font_size = 48
		label.outline_size = 10
		label.pixel_size = 0.012
		label.modulate = mat.albedo_color.lightened(0.3)
		label.visibility_range_end = 260.0
		root.add_child(label)


## Невидимые стенки: граница участка (берег — парапетом набережной, овраг, мыс, забор), края мола и пирсов.
func _barriers() -> void:
	var body: StaticBody3D = StaticBody3D.new()
	body.name = "Barriers"
	body.collision_layer = 1
	body.collision_mask = 0
	generated.add_child(body)
	for b: Array in plan.barriers:
		var a: Vector2 = Vector2(float(b[0]), float(b[1]))
		var c: Vector2 = Vector2(float(b[2]), float(b[3]))
		var length: float = a.distance_to(c)
		if length < 0.01:
			continue
		var bottom: float = float(b[4])
		var top: float = float(b[5])
		var shape: BoxShape3D = BoxShape3D.new()
		shape.size = Vector3(0.5, top - bottom, length + 0.5)
		var cs: CollisionShape3D = CollisionShape3D.new()
		cs.shape = shape
		var mid: Vector2 = (a + c) * 0.5
		cs.position = Vector3(mid.x, (bottom + top) * 0.5, mid.y)
		cs.rotation.y = atan2(c.x - a.x, c.y - a.y)
		body.add_child(cs)


## Ели и сосны — россыпи DistrictScatter (полные модели вблизи, карточки дальше); фон за забором — без стволов.
func _trees() -> void:
	if not FileAccess.file_exists(VEG_PATH):
		return
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(VEG_PATH)) as Dictionary
	var root: Node3D = Node3D.new()
	root.name = "Forest"
	generated.add_child(root)
	for key: String in data:
		if (data[key] as Array).is_empty():
			continue
		var background: bool = key.ends_with("_bg")
		var spec: Array = SPECIES[key.trim_suffix("_bg")]
		var scatter: DistrictScatter = DistrictScatter.new()
		scatter.name = key
		scatter.data_path = VEG_PATH
		scatter.key = key
		scatter.model = "res://assets/zone01/models/%s.glb" % String(spec[0])
		scatter.far_model = "res://assets/zone01/models/%s_far.glb" % String(spec[0])
		scatter.near_distance = 220.0
		scatter.view_distance = 2400.0
		scatter.cell = 64.0
		scatter.far_cell = 256.0
		scatter.trunk_radius = 0.0 if background else float(spec[1])
		root.add_child(scatter)
