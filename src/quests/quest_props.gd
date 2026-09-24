class_name QuestProps
extends RefCounted
## Заглушки сцен квестов (data/quests → sites.props): простые меши вместо будущих моделей —
## рюкзак, кровь, гильзы, стулья, записки, ящики, ворота, раненый. Сцена рассказывает, что здесь
## было, без текста. Крупное (ящик, шкаф, стул, ворота, койка) — с коллизией: за ним прячутся.
## kind — вид, at — смещение от места (y 0 — пол), yaw — поворот, n/spread/size/to — по виду.

static var _mats: Dictionary = {}


static func build(spec: Dictionary, rng: RandomNumberGenerator) -> Node3D:
	var root := Node3D.new()
	var at: Array = spec.get("at", [0, 0, 0])
	root.position = Vector3(float(at[0]), float(at[1]), float(at[2]))
	root.rotation.y = deg_to_rad(float(spec.get("yaw", 0.0)))
	var k := float(spec.get("scale", 1.0))
	match String(spec.get("kind", "")):
		"backpack":
			_box(root, Vector3(0, 0.2, 0), Vector3(0.36, 0.42, 0.22), _m("olive", Color(0.22, 0.25, 0.16), 0.9))
			_box(root, Vector3(0, 0.33, 0.13), Vector3(0.3, 0.14, 0.06), _m("olive_d", Color(0.17, 0.19, 0.12), 0.9))
			_box(root, Vector3(0.1, 0.22, -0.13), Vector3(0.05, 0.36, 0.03), _m("strap", Color(0.1, 0.1, 0.09), 0.8))
			root.rotation.z = deg_to_rad(78.0)
			root.position.y += 0.11
		"blood":
			var sz := float(spec.get("size", 1.0))
			_decal(root, Vector3.ZERO, sz, _m("blood", Color(0.25, 0.02, 0.02, 0.85), 0.35, true))
			for i in range(3):
				_decal(root, Vector3(rng.randf_range(-0.5, 0.5), 0.0, rng.randf_range(-0.5, 0.5)) * sz, sz * rng.randf_range(0.2, 0.45), _m("blood", Color(), 0.0))
		"drops":
			var to: Array = spec.get("to", [3, 0, 3])
			var end := Vector3(float(to[0]), 0.0, float(to[2])) - root.position
			var n := int(spec.get("n", 5))
			for i in range(n):
				var t := float(i + 1) / float(n + 1)
				_decal(root, end * t + Vector3(rng.randf_range(-0.2, 0.2), 0.0, rng.randf_range(-0.2, 0.2)), rng.randf_range(0.08, 0.2), _m("blood", Color(), 0.0))
		"casings":
			_scatter(root, int(spec.get("n", 6)), float(spec.get("spread", 1.0)), rng, func(p: Node3D) -> void:
				var c := _cyl(p, Vector3.ZERO, 0.0045, 0.032, _m("brass", Color(0.78, 0.6, 0.28), 0.35, false, 0.9))
				c.rotation = Vector3(PI * 0.5, rng.randf() * TAU, 0.0)
				c.position.y = 0.005)
		"butts":
			_scatter(root, int(spec.get("n", 5)), float(spec.get("spread", 0.5)), rng, func(p: Node3D) -> void:
				var c := _cyl(p, Vector3.ZERO, 0.004, 0.022, _m("filter", Color(0.85, 0.62, 0.35), 0.8))
				c.rotation = Vector3(PI * 0.5, rng.randf() * TAU, 0.0)
				c.position.y = 0.004)
		"crate":
			_solid(root, Vector3(0, 0.3 * k, 0), Vector3(0.8, 0.6, 0.6) * k, _m("wood", Color(0.46, 0.34, 0.2), 0.85))
		"chair":
			var mm := _m("chair", Color(0.2, 0.22, 0.24), 0.6, false, 0.6)
			_solid(root, Vector3(0, 0.45, 0), Vector3(0.44, 0.05, 0.42), mm)
			_box(root, Vector3(0, 0.72, -0.2), Vector3(0.44, 0.5, 0.04), mm)
			for sx in [-0.19, 0.19]:
				for sz in [-0.18, 0.18]:
					_box(root, Vector3(sx, 0.22, sz), Vector3(0.03, 0.45, 0.03), mm)
		"note":
			_box(root, Vector3(0, 0.002, 0), Vector3(0.15, 0.003, 0.21), _m("paper", Color(0.9, 0.88, 0.8), 0.9))
		"papers":
			_scatter(root, int(spec.get("n", 5)), float(spec.get("spread", 0.5)), rng, func(p: Node3D) -> void:
				_box(p, Vector3(0, 0.002, 0), Vector3(0.21, 0.003, 0.29), _m("paper", Color(), 0.0)))
		"tarp":
			_box(root, Vector3.ZERO, Vector3(0.95, 0.03, 0.75), _m("tarp", Color(0.12, 0.2, 0.3), 0.7))
		"ammo_taped":
			for i in range(int(spec.get("n", 3))):
				var b := Node3D.new()
				b.position = Vector3(i * 0.16 - 0.16, 0.0, rng.randf_range(-0.05, 0.05))
				b.rotation.y = rng.randf_range(-0.3, 0.3)
				root.add_child(b)
				_box(b, Vector3(0, 0.035, 0), Vector3(0.12, 0.07, 0.08), _m("ammo_box", Color(0.55, 0.5, 0.36), 0.8))
				# синяя изолента крест-накрест с петлёй — как на прилавке у торговца
				var tape := _m("tape", Color(0.1, 0.25, 0.75), 0.4)
				_box(b, Vector3(0, 0.072, 0), Vector3(0.125, 0.004, 0.018), tape)
				_box(b, Vector3(0, 0.072, 0), Vector3(0.018, 0.004, 0.085), tape)
				_box(b, Vector3(0.06, 0.08, 0), Vector3(0.012, 0.02, 0.018), tape)
		"cabinet":
			_solid(root, Vector3(0, 0.95, 0), Vector3(0.9, 1.9, 0.5), _m("steel_cab", Color(0.42, 0.44, 0.45), 0.5, false, 0.6))
			_box(root, Vector3(0.52, 0.9, 0.0), Vector3(0.04, 0.9, 0.46), _m("panel", Color(0.3, 0.32, 0.33), 0.6, false, 0.5))
		"bundle":
			_box(root, Vector3(0, 0.06, 0), Vector3(0.3, 0.12, 0.22), _m("papers_b", Color(0.8, 0.76, 0.66), 0.9))
			_box(root, Vector3(0, 0.061, 0), Vector3(0.33, 0.13, 0.25), _m("film", Color(0.8, 0.85, 0.9, 0.35), 0.1, true))
		"red_gate":
			var red := _m("red_gate", Color(0.62, 0.08, 0.06), 0.55, false, 0.4)
			for sx in [-1.55, 1.55]:
				_solid(root, Vector3(sx, 1.3, 0), Vector3(3.0, 2.6, 0.08), red)
			for sx in [-3.15, 3.15]:
				_solid(root, Vector3(sx, 1.5, 0), Vector3(0.14, 3.0, 0.14), _m("post", Color(0.25, 0.25, 0.26), 0.5, false, 0.7))
		"cot":
			_solid(root, Vector3(0, 0.4, 0), Vector3(0.8, 0.06, 1.95), _m("canvas", Color(0.3, 0.34, 0.24), 0.9))
			for sx in [-0.36, 0.36]:
				for sz in [-0.9, 0.9]:
					_box(root, Vector3(sx, 0.2, sz), Vector3(0.04, 0.4, 0.04), _m("post", Color(), 0.0))
		"item":
			var model := ItemModels.build(String(spec.get("id", "bandage")))
			model.position.y = 0.03
			if bool(spec.get("lay", false)):
				model.rotation.z = PI * 0.5
			root.add_child(model)
		"npc":
			build_person(root, String(spec.get("pose", "lying")), Color(0.3, 0.3, 0.26))
	return root


## Человек-заглушка: lying — лежит на спине, sitting — сидит, привалившись; carried — через плечо.
static func build_person(root: Node3D, pose: String, coat: Color) -> void:
	var body := _m("coat_%s" % coat.to_html(), coat, 0.85)
	var skin := _m("skin", Color(0.72, 0.56, 0.46), 0.7)
	var legs := _m("jeans", Color(0.16, 0.18, 0.24), 0.9)
	var bandage := _m("bandage_red", Color(0.8, 0.62, 0.6), 0.9)
	match pose:
		"sitting":
			_box(root, Vector3(0, 0.45, -0.1), Vector3(0.42, 0.62, 0.26), body).rotation.x = deg_to_rad(-12.0)
			_box(root, Vector3(0, 0.88, -0.2), Vector3(0.2, 0.22, 0.22), skin)
			_box(root, Vector3(0, 0.12, 0.35), Vector3(0.36, 0.2, 0.7), legs)
			_box(root, Vector3(0.12, 0.42, 0.04), Vector3(0.22, 0.16, 0.05), bandage)
		"carried":
			_box(root, Vector3(0, 0, 0), Vector3(0.6, 0.26, 0.4), body)
			_box(root, Vector3(0.45, -0.05, 0), Vector3(0.22, 0.2, 0.2), skin)
			_box(root, Vector3(-0.55, -0.02, 0), Vector3(0.6, 0.2, 0.3), legs)
		_:
			_box(root, Vector3(0, 0.14, -0.1), Vector3(0.44, 0.24, 0.62), body)
			_box(root, Vector3(0, 0.14, -0.55), Vector3(0.2, 0.2, 0.22), skin)
			_box(root, Vector3(0, 0.1, 0.55), Vector3(0.36, 0.18, 0.8), legs)
			_box(root, Vector3(0.1, 0.27, -0.05), Vector3(0.24, 0.02, 0.2), bandage)


static func _scatter(root: Node3D, n: int, spread: float, rng: RandomNumberGenerator, make: Callable) -> void:
	for i in range(n):
		var p := Node3D.new()
		var a := rng.randf() * TAU
		p.position = Vector3(cos(a), 0.0, sin(a)) * rng.randf() * spread
		p.rotation.y = rng.randf() * TAU
		root.add_child(p)
		make.call(p)


static func _box(parent: Node3D, at: Vector3, size: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var b := BoxMesh.new()
	b.size = size
	mi.mesh = b
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


static func _cyl(parent: Node3D, at: Vector3, r: float, h: float, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = r
	c.bottom_radius = r
	c.height = h
	c.radial_segments = 8
	mi.mesh = c
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


## Пятно на полу: плоский круг чуть над полом (без теней).
static func _decal(parent: Node3D, at: Vector3, size: float, mat: Material) -> void:
	var mi := MeshInstance3D.new()
	var c := CylinderMesh.new()
	c.top_radius = size * 0.5
	c.bottom_radius = size * 0.5
	c.height = 0.004
	c.radial_segments = 12
	mi.mesh = c
	mi.position = at + Vector3.UP * 0.006
	mi.scale = Vector3(1.0, 1.0, randf_range(0.55, 1.0))
	mi.rotation.y = randf() * TAU
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)


## Меш с коллизией (укрытие, препятствие) — слой мира: пули и зрение через него не проходят.
static func _solid(parent: Node3D, at: Vector3, size: Vector3, mat: Material) -> void:
	_box(parent, at, size, mat)
	var body := StaticBody3D.new()
	body.collision_layer = Hitscan.LAYER_WORLD
	body.collision_mask = 0
	body.position = at
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	body.add_child(cs)
	parent.add_child(body)


## Материал по ключу (кэш); цвет задаётся при первом обращении.
static func _m(key: String, color: Color, rough: float, transparent: bool = false, metal: float = 0.0) -> StandardMaterial3D:
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	if transparent or color.a < 1.0:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mats[key] = m
	return m
