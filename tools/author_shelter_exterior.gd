extends Node
## Офлайн-авторинг двора котельной (убежище снаружи): перевод GLB из tools/build_shelter_exterior.py в
## законченные сцены, земля с вырезами под здание, растительность, забор, ворота, дверь выхода, зона
## сбора — и запись сцены levels/shelter/Shelter_Exterior.tscn. Дальше сцену правят руками в редакторе;
## повторный запуск инструмента перезапишет её (правки руками — после него).
## tools/godot.cmd --headless res://tools/author_shelter_exterior.tscn

const BASE: String = "res://levels/shelter/"
const OUT: String = "res://levels/shelter/exterior/"
const MODELS: String = "res://assets/shelter/models/"
const VEG: String = "res://assets/zone01/models/"
const VEG_DATA: String = "res://data/shelter_vegetation.json"
const IDS: Array[String] = ["Wall_EntrySouth", "BlastDoorFrame", "BlastDoorLeaf", "ExitCorridor", "ShellUpper", "FencePanel", "YardGate"]
## Земля: границы сетки (x0, z0, x1, z1) и шаг, м.
const AREA := Rect2(-120.0, -110.0, 300.0, 240.0)
const STEP: float = 3.0
## Вырезы под здание и лестничный спуск (x0, z0, x1, z1).
const HOLES: Array = [[-18.2, -11.2, 18.2, 7.2], [-4.2, 7.2, 4.2, 12.2], [18.2, -11.2, 62.6, 7.2], [-1.8, 12.2, 1.8, 21.2]]
## Двор: забор (x запад, x восток, z юг), ворота по центру.
const YARD_W: float = -22.0
const YARD_E: float = 30.0
const YARD_S: float = 50.0

var _author: Node
var _root: Node3D
var _kit: Dictionary = {}
var _layout: Dictionary = {}
var _ground_y: float = 1.2
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	await get_tree().process_frame
	_rng.seed = 505
	_ground_y = float(Balance.SHELTER_YARD.ground)
	_layout = JSON.parse_string(FileAccess.get_file_as_string(MODELS + "exterior_layout.json")) as Dictionary
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	_convert()
	_root = Node3D.new()
	_root.name = "Shelter_Exterior"
	add_child(_root)
	_ground()
	_building()
	_door()
	_yard()
	_yard_lamps()
	_vegetation()
	_start_zone()
	var packed := PackedScene.new()
	assert(packed.pack(_root) == OK)
	assert(ShelterSave.save(packed, BASE + "Shelter_Exterior.tscn") == OK)
	print("SHELTER_EXTERIOR_AUTHORED nodes=", _root.find_children("*", "", true, false).size())
	get_tree().quit()


func _own(parent: Node, child: Node) -> Node:
	parent.add_child(child)
	child.owner = _root
	return child


func _group(label: String) -> Node3D:
	var n := Node3D.new()
	n.name = label
	return _own(_root, n) as Node3D


# ---------------------------------------------------------------- сборки из Blender

## GLB → меши и сцены тем же способом, что и остальное убежище (author_shelter_scene._convert_asset);
## материалы берутся готовые из levels/shelter/materials — их этот инструмент не перезаписывает.
func _convert() -> void:
	_author = (load("res://tools/author_shelter_scene.gd") as GDScript).new()
	var mats: Dictionary = {}
	for file: String in DirAccess.get_files_at(BASE + "materials"):
		if file.ends_with(".tres"):
			mats[file.get_basename()] = load(BASE + "materials/" + file)
	# уличный бетон (забор, подпорные стенки, парапеты): те же фототекстуры, но без шейдера старения
	# помещений — тот темнит стену по высоте от пола котельной, и забор выходил чёрным
	var outdoor: Dictionary = mats.duplicate()
	for label: String in ["RawConcrete", "DampConcrete"]:
		outdoor[label] = _outdoor_material(label)
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(MODELS + "manifest.json")) as Dictionary
	for id: String in IDS:
		_author.set("_materials", outdoor if id in ["FencePanel", "YardGate", "ShellUpper"] else mats)
		_author.call("_convert_asset", id, manifest[id])
		var path: String = BASE + ("architecture/" if id.begins_with("Wall_") else "props/") + id + ".tscn"
		_kit[id] = load(path)
	_author.free()


func _outdoor_material(label: String) -> StandardMaterial3D:
	var tex: String = "res://assets/shelter/textures/"
	var m := StandardMaterial3D.new()
	m.resource_name = label + "Outdoor"
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	m.albedo_texture = load(tex + label + "_base.jpg")
	# фототекстуры убежища тёмные и бурые (под лампы помещений): на улице осветляем и уводим в серый
	m.albedo_color = Color(1.75, 1.82, 1.92) if label == "RawConcrete" else Color(1.55, 1.62, 1.7)
	if ResourceLoader.exists(tex + label + "_normal.jpg"):
		m.normal_enabled = true
		m.normal_texture = load(tex + label + "_normal.jpg")
		m.normal_scale = 0.5
	if ResourceLoader.exists(tex + label + "_orm.jpg"):
		var orm: Texture2D = load(tex + label + "_orm.jpg")
		m.roughness_texture = orm
		m.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
		m.ao_enabled = true
		m.ao_texture = orm
	m.metallic_specular = 0.3
	var path: String = BASE + "materials/" + label + "Outdoor.tres"
	assert(ShelterSave.save(m, path) == OK)
	return load(path) as StandardMaterial3D


func _put(id: String, label: String, parent: Node, at: Vector3, yaw: float = 0.0) -> Node3D:
	var n: Node3D = (_kit[id] as PackedScene).instantiate() as Node3D
	n.name = label
	n.position = at
	n.rotation_degrees.y = yaw
	_own(parent, n)
	return n


# ---------------------------------------------------------------- земля

func _in_hole(x: float, z: float) -> bool:
	for h: Array in HOLES:
		if x > float(h[0]) and x < float(h[2]) and z > float(h[1]) and z < float(h[3]):
			return true
	return false


## Расстояние до ближайшего выреза (0 — внутри).
func _hole_dist(x: float, z: float) -> float:
	var best: float = INF
	for h: Array in HOLES:
		var c := Vector2((float(h[0]) + float(h[2])) * 0.5, (float(h[1]) + float(h[3])) * 0.5)
		var half := Vector2((float(h[2]) - float(h[0])) * 0.5, (float(h[3]) - float(h[1])) * 0.5)
		best = minf(best, Vector2(maxf(absf(x - c.x) - half.x, 0.0), maxf(absf(z - c.y) - half.y, 0.0)).length())
	return best


func _lines(from: float, to: float, extra: Array) -> Array[float]:
	var out: Array[float] = []
	var v: float = from
	while v <= to + 0.001:
		out.append(v)
		v += STEP
	for e: float in extra:
		out.append(e)
	out.sort()
	var clean: Array[float] = []
	for value: float in out:
		if clean.is_empty() or value - clean[clean.size() - 1] > 0.05:
			clean.append(value)
	return clean


func _ground() -> void:
	var xs: Array[float] = _lines(AREA.position.x, AREA.end.x, [-18.2, 18.2, -4.2, 4.2, 62.6, -1.8, 1.8])
	var zs: Array[float] = _lines(AREA.position.y, AREA.end.y, [-11.2, 7.2, 12.2, 21.2])
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i: int in range(xs.size() - 1):
		for j: int in range(zs.size() - 1):
			var x0: float = xs[i]
			var x1: float = xs[i + 1]
			var z0: float = zs[j]
			var z1: float = zs[j + 1]
			if _in_hole((x0 + x1) * 0.5, (z0 + z1) * 0.5):
				continue
			var a := Vector3(x0, ShelterGround.height(x0, z0), z0)
			var b := Vector3(x1, ShelterGround.height(x1, z0), z0)
			var c := Vector3(x1, ShelterGround.height(x1, z1), z1)
			var d := Vector3(x0, ShelterGround.height(x0, z1), z1)
			for p: Vector3 in [a, b, c, a, c, d]:
				st.set_uv(Vector2(p.x, p.z))
				st.add_vertex(p)
	st.index()
	st.generate_normals()
	var mesh: ArrayMesh = st.commit()
	mesh.surface_set_material(0, _ground_material())
	assert(ShelterSave.save(mesh, OUT + "ground.res") == OK)
	var ground := ShelterGround.new()
	ground.name = "Ground"
	_own(_root, ground)
	var mi := MeshInstance3D.new()
	mi.name = "Mesh"
	mi.mesh = load(OUT + "ground.res")
	mi.gi_mode = GeometryInstance3D.GI_MODE_STATIC
	_own(ground, mi)
	var body := StaticBody3D.new()
	body.name = "Collision"
	body.collision_layer = 1
	body.collision_mask = 0
	body.set_meta("surface", "grass")
	_own(ground, body)
	var shape := CollisionShape3D.new()
	shape.name = "Shape"
	shape.shape = (mi.mesh as ArrayMesh).create_trimesh_shape()
	_own(body, shape)


## Материал земли — шейдер рельефа района ТЦ с теми же фототекстурами и своей маской: щебень дорожки и
## отмостки, грязь у ворот, опавшая листва под лесом.
func _ground_material() -> ShaderMaterial:
	var terrain: Dictionary = (SectorBuilder.load_def("res://data/sectors/zone01_mall.json").get("terrain", {}) as Dictionary)
	var m := ShaderMaterial.new()
	m.shader = load("res://src/world/district_terrain.gdshader")
	for key: String in ["albedo_array", "normal_array", "arm_array", "noise"]:
		var path: String = String((terrain.get("textures", {}) as Dictionary).get(key, ""))
		assert(ResourceLoader.exists(path), "нет текстуры рельефа: " + path)
		m.set_shader_parameter(key, load(path))
	m.set_shader_parameter("layer_tile", PackedFloat32Array(terrain.get("layer_tiles", [3.0, 3.0, 2.5, 3.0, 4.0, 2.0])))
	var w: int = int(AREA.size.x)
	var h: int = int(AREA.size.y)
	var splat := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var noise := FastNoiseLite.new()
	noise.seed = 77
	noise.frequency = 0.06
	for pz: int in range(h):
		for px: int in range(w):
			var x: float = AREA.position.x + px + 0.5
			var z: float = AREA.position.y + pz + 0.5
			var n: float = noise.get_noise_2d(x, z)
			var gravel: float = 0.0
			# дорожка от лестницы к воротам и дальше — лесная дорога
			if z > 20.6:
				gravel = 1.0 - smoothstep(1.3, 2.1 + n * 0.5, absf(x + sin(z * 0.07) * (0.0 if z < YARD_S else 2.5)))
			# отмостка вдоль стен
			var hd: float = _hole_dist(x, z)
			if hd > 0.0:
				gravel = maxf(gravel, 0.85 * (1.0 - smoothstep(0.7, 1.4, hd)))
			var in_yard: bool = x > YARD_W and x < YARD_E and z > 3.0 and z < YARD_S
			var mud: float = 0.0
			if z > 20.6 and absf(x) < 5.0:
				mud = clampf((n - 0.15) * 2.2, 0.0, 0.7) * (1.0 - gravel)
			if absf(z - YARD_S) < 4.0 and absf(x) < 4.5:
				mud = maxf(mud, 0.55 * (1.0 - gravel))
			var litter: float = 0.0
			if not in_yard and hd > 5.0:
				litter = clampf(0.12 + noise.get_noise_2d(x * 0.5 + 300.0, z * 0.5) * 0.75, 0.0, 0.6) * smoothstep(5.0, 14.0, hd)
			splat.set_pixel(px, pz, Color(mud, 0.0, gravel, litter))
	m.set_shader_parameter("splat", ImageTexture.create_from_image(splat))
	m.set_shader_parameter("splat_origin", AREA.position)
	m.set_shader_parameter("splat_size", AREA.size)
	assert(ShelterSave.save(m, OUT + "ground_material.tres") == OK)
	# трава: всюду, кроме щебня, грязи и самого здания; под лесом — реже (R — трава, G — сорняки)
	var grass := Image.create(w, h, false, Image.FORMAT_RGB8)
	for pz: int in range(h):
		for px: int in range(w):
			var x: float = AREA.position.x + px + 0.5
			var z: float = AREA.position.y + pz + 0.5
			var s: Color = splat.get_pixel(px, pz)
			var k: float = 0.0 if _in_hole(x, z) else clampf(1.0 - s.b * 1.6 - s.r * 1.2, 0.0, 1.0) * lerpf(1.0, 0.45, s.a)
			grass.set_pixel(px, pz, Color(k, k * clampf(0.3 + noise.get_noise_2d(x * 2.0, z * 2.0 + 90.0), 0.0, 1.0), 0.0))
	grass.save_png(ProjectSettings.globalize_path(OUT + "grass_density.png"))
	return load(OUT + "ground_material.tres") as ShaderMaterial


# ---------------------------------------------------------------- здание снаружи и выход

func _building() -> void:
	var g := _group("Building")
	_put("ShellUpper", "ShellUpper", g, Vector3.ZERO)
	_put("ExitCorridor", "ExitCorridor", g, Vector3.ZERO)
	# свет в коридоре: два плафона под перекрытием, тёплые, с тенью
	var cor: Dictionary = _layout.corridor
	for i: int in range(2):
		var lamp := OmniLight3D.new()
		lamp.name = "CorridorLamp_%d" % i
		lamp.position = Vector3(0.0, float(cor.h) - 0.35, float(cor.z0) + 1.4 + i * 3.2)
		lamp.light_color = Color(1.0, 0.86, 0.66)
		lamp.light_energy = 0.9
		lamp.omni_range = 6.5
		lamp.omni_attenuation = 1.2
		lamp.shadow_enabled = true
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		_own(g, lamp)


## Фонари двора: над порталом лестницы, у стены тамбура и на столбах ворот. Группа
## «shelter_yard_lamps» — ShelterWeather гасит их днём.
func _yard_lamps() -> void:
	var g := _group("YardLamps")
	var cor: Dictionary = _layout.corridor
	for spot: Array in [["Portal", Vector3(0.0, float(cor.h) + 0.55, float(cor.z1) + 0.5), 1.4, 11.0],
			["EntryWall", Vector3(-3.4, 3.0, 12.6), 1.1, 10.0], ["GateWest", Vector3(-2.5, _ground_y + 2.5, YARD_S - 0.4), 1.3, 12.0],
			["GateEast", Vector3(2.5, _ground_y + 2.5, YARD_S - 0.4), 1.3, 12.0], ["YardEast", Vector3(YARD_E - 0.6, _ground_y + 2.6, 26.0), 1.0, 12.0]]:
		var lamp := OmniLight3D.new()
		lamp.name = String(spot[0])
		lamp.position = spot[1]
		lamp.light_color = Color(1.0, 0.82, 0.58)
		lamp.light_energy = float(spot[2])
		lamp.omni_range = float(spot[3])
		lamp.omni_attenuation = 1.1
		lamp.shadow_enabled = true
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		lamp.add_to_group("shelter_yard_lamps", true)
		_own(g, lamp)


func _door() -> void:
	var door := ShelterExitDoor.new()
	door.name = "ExitDoor"
	door.position = Vector3(0.0, 0.0, float(_layout.door_z))
	_own(_root, door)
	var frame: Node3D = _put("BlastDoorFrame", "Frame", door, Vector3.ZERO)
	frame.add_to_group("shelter_navigation_geometry", true)
	_put("BlastDoorLeaf", "Leaf", door, Vector3(float(_layout.door_hinge_x), 0.0, 0.0))
	door.leaf = NodePath("Leaf")


# ---------------------------------------------------------------- двор: забор, ворота, границы

func _fence_line(parent: Node, from: Vector2, to: Vector2) -> void:
	var pw: float = float(_layout.fence.panel_w)
	var length: float = from.distance_to(to)
	var n: int = maxi(1, int(round(length / pw)))
	var dir: Vector2 = (to - from) / float(n)
	var yaw: float = rad_to_deg(atan2(-(to - from).y, (to - from).x))
	for i: int in range(n):
		var p: Vector2 = from + dir * (float(i) + 0.5)
		_put("FencePanel", "Panel_%02d" % parent.get_child_count(), parent, Vector3(p.x, ShelterGround.height(p.x, p.y) - 0.06, p.y), yaw)


func _wall(parent: Node, label: String, center: Vector3, size: Vector3) -> void:
	var cs := CollisionShape3D.new()
	cs.name = label
	var box := BoxShape3D.new()
	box.size = size
	cs.shape = box
	cs.position = center
	_own(parent, cs)


func _yard() -> void:
	var fence := _group("Fence")
	var gate_half: float = float(_layout.gate.w) * 0.5 + 0.2
	_fence_line(fence, Vector2(-18.2, 3.0), Vector2(YARD_W, 3.0))
	_fence_line(fence, Vector2(YARD_W, 3.0), Vector2(YARD_W, YARD_S))
	_fence_line(fence, Vector2(YARD_W, YARD_S), Vector2(-gate_half, YARD_S))
	_fence_line(fence, Vector2(gate_half, YARD_S), Vector2(YARD_E, YARD_S))
	_fence_line(fence, Vector2(YARD_E, YARD_S), Vector2(YARD_E, 7.4))
	_put("YardGate", "Gate", _root, Vector3(0.0, _ground_y - 0.02, YARD_S))
	# невидимые границы: за ворота — на несколько шагов, через забор и по кровле пристройки — нельзя
	var bounds := StaticBody3D.new()
	bounds.name = "Bounds"
	bounds.collision_layer = 1
	bounds.collision_mask = 0
	_own(_root, bounds)
	var y: float = _ground_y + 3.0
	_wall(bounds, "West", Vector3(YARD_W - 0.4, y, 26.5), Vector3(0.6, 8.0, 48.0))
	_wall(bounds, "WestReturn", Vector3(-20.1, y, 2.6), Vector3(4.4, 8.0, 0.6))
	_wall(bounds, "East", Vector3(YARD_E + 0.4, y, 28.5), Vector3(0.6, 8.0, 44.0))
	_wall(bounds, "SouthWest", Vector3((YARD_W - gate_half) * 0.5, y, YARD_S + 0.4), Vector3(absf(YARD_W + gate_half), 8.0, 0.6))
	_wall(bounds, "SouthEast", Vector3((YARD_E + gate_half) * 0.5, y, YARD_S + 0.4), Vector3(YARD_E - gate_half, 8.0, 0.6))
	_wall(bounds, "GateEnd", Vector3(0.0, y, YARD_S + 6.0), Vector3(gate_half * 2.0 + 4.0, 8.0, 0.6))
	for sx: float in [-1.0, 1.0]:
		_wall(bounds, "GateSide%d" % int(sx), Vector3(sx * (gate_half + 1.8), y, YARD_S + 3.0), Vector3(0.6, 8.0, 6.0))
	# на кровлю не залезть: над пристройкой коридора и над тамбуром встать негде (только снаружи здания —
	# внутри под перекрытиями зала и галереи есть антресоль, её задевать нельзя)
	_wall(bounds, "RoofEntry", Vector3(0.0, 6.2, 10.0), Vector3(9.0, 5.0, 5.0))
	_wall(bounds, "RoofCorridor", Vector3(0.0, 5.6, 15.3), Vector3(4.0, 5.0, 6.4))


# ---------------------------------------------------------------- растительность

func _clear(x: float, z: float, margin: float) -> bool:
	# здание с запасом, двор, дорога за воротами
	if _hole_dist(x, z) < margin:
		return false
	if x > YARD_W - 1.5 and x < YARD_E + 1.5 and z > 1.5 and z < YARD_S + 1.5:
		return false
	if z >= YARD_S and absf(x + sin(z * 0.07) * 2.5) < 4.5:
		return false
	return true


## Расстояние до ровной площадки двора и здания (0 — на ней).
func _site_dist(x: float, z: float) -> float:
	var c: Vector2 = ShelterGround.FLAT.get_center()
	var half: Vector2 = ShelterGround.FLAT.size * 0.5
	return Vector2(maxf(absf(x - c.x) - half.x, 0.0), maxf(absf(z - c.y) - half.y, 0.0)).length()


func _point(x: float, z: float, scale_from: float, scale_to: float) -> Array:
	return [snappedf(x, 0.01), snappedf(ShelterGround.height(x, z) - 0.06, 0.001), snappedf(z, 0.01), snappedf(_rng.randf() * 360.0, 0.1), snappedf(_rng.randf_range(scale_from, scale_to), 0.001)]


func _vegetation() -> void:
	var data: Dictionary = {}
	var trees: Array = [["spruce_forest_a", 0.22], ["spruce_forest_b", 0.2], ["birch_a", 0.14], ["birch_b", 0.1], ["birch_c", 0.08],
		["pine_forest", 0.12], ["spruce_young_a", 0.07], ["spruce_young_b", 0.07]]
	for row: Array in trees:
		data[String(row[0])] = []
	var noise := FastNoiseLite.new()
	noise.seed = 31
	noise.frequency = 0.02
	var tries: int = 0
	var placed: Array[Vector2] = []
	while placed.size() < 420 and tries < 40000:
		tries += 1
		var x: float = _rng.randf_range(AREA.position.x + 4.0, AREA.end.x - 4.0)
		var z: float = _rng.randf_range(AREA.position.y + 4.0, AREA.end.y - 4.0)
		if not _clear(x, z, 7.0) or _site_dist(x, z) > 85.0:
			continue
		var near: bool = false
		for p: Vector2 in placed:
			if absf(p.x - x) < 3.2 and absf(p.y - z) < 3.2:
				near = true
				break
		if near:
			continue
		# породы пятнами: шум сдвигает выбор — ельник, березняк, сосны
		var pick: float = fposmod(_rng.randf() * 0.55 + (noise.get_noise_2d(x, z) * 0.5 + 0.5) * 0.45, 1.0)
		var key: String = String(trees[trees.size() - 1][0])
		for row: Array in trees:
			pick -= float(row[1])
			if pick <= 0.0:
				key = String(row[0])
				break
		placed.append(Vector2(x, z))
		(data[key] as Array).append(_point(x, z, 0.85, 1.2))
	# во дворе — несколько берёз у забора
	for spot: Vector2 in [Vector2(-16.0, 30.0), Vector2(-12.0, 44.0), Vector2(18.0, 40.0), Vector2(24.0, 22.0), Vector2(11.0, 28.0)]:
		(data["birch_b" if int(spot.x) % 2 == 0 else "birch_a"] as Array).append(_point(spot.x, spot.y, 0.85, 1.05))
	# подлесок: кусты и поросль — в лесу и вдоль забора; папоротник, валежник, пни, камни — только в лесу
	var under: Array = [["ug_bush_a", 90, 3.0], ["ug_bush_b", 90, 3.0], ["ug_bush_c", 80, 3.0], ["ug_bush_d", 80, 3.0],
		["ug_sapling_a", 70, 3.0], ["ug_sapling_b", 70, 3.0], ["ug_sapling_c", 60, 3.0],
		["forest_fern", 260, 6.0], ["forest_dry_branches", 70, 6.0], ["forest_stump_01", 16, 8.0], ["forest_stump_02", 14, 8.0],
		["forest_rocks_01", 12, 8.0], ["forest_rocks_02", 12, 8.0], ["forest_dead_trunk", 10, 9.0]]
	for row: Array in under:
		var list: Array = []
		var guard: int = 0
		while list.size() < int(row[1]) and guard < 6000:
			guard += 1
			var x: float = _rng.randf_range(AREA.position.x + 4.0, AREA.end.x - 4.0)
			var z: float = _rng.randf_range(AREA.position.y + 4.0, AREA.end.y - 4.0)
			if _clear(x, z, float(row[2])) and _site_dist(x, z) < 60.0:
				list.append(_point(x, z, 0.8, 1.25) if not String(row[0]).begins_with("ug_sapling") else _point(x, z, 1.3, 2.3))
		data[String(row[0])] = list
	# кусты во дворе вдоль забора
	for i: int in range(26):
		var along: float = _rng.randf()
		var side: int = i % 3
		var p: Vector2 = Vector2(YARD_W + 1.4, lerpf(6.0, YARD_S - 2.0, along)) if side == 0 else (Vector2(YARD_E - 1.4, lerpf(10.0, YARD_S - 2.0, along)) if side == 1 else Vector2(lerpf(YARD_W + 2.0, YARD_E - 2.0, along), YARD_S - 1.4))
		if absf(p.x) < 4.0 and p.y > YARD_S - 4.0:
			continue
		(data[["ug_bush_a", "ug_bush_b", "ug_bush_c", "ug_bush_d"][i % 4]] as Array).append(_point(p.x, p.y, 0.8, 1.2))
	var f := FileAccess.open(VEG_DATA, FileAccess.WRITE)
	f.store_string(JSON.stringify(data))
	f.close()
	var veg := _group("Vegetation")
	for key: String in data:
		var sc := DistrictScatter.new()
		sc.name = key.to_pascal_case()
		sc.data_path = VEG_DATA
		sc.key = key
		sc.model = VEG + key + ".glb"
		assert(ResourceLoader.exists(sc.model), "нет модели: " + sc.model)
		if key.begins_with("ug_"):
			sc.view_distance = 90.0
			sc.cell = 24.0
			sc.foliage = true
			sc.foliage_tint = Color(0.82, 0.8, 0.62) if key.begins_with("ug_bush") else Color(0.78, 0.82, 0.72)
		elif key.begins_with("forest_"):
			sc.view_distance = 60.0
			sc.cell = 24.0
			sc.shadows = false
			if key.begins_with("forest_stump"):
				sc.trunk_radius = 0.3
				sc.trunk_height = 0.6
			elif key.begins_with("forest_rocks"):
				sc.trunk_radius = 0.5
				sc.trunk_height = 0.8
		else:
			# подробная модель — только рядом; дальше — силуэт (иначе лес за окнами съедал половину кадров)
			sc.view_distance = 420.0
			sc.cell = 20.0
			sc.near_distance = 42.0
			if ResourceLoader.exists(VEG + key + "_far.glb"):
				sc.far_model = VEG + key + "_far.glb"
			sc.trunk_radius = 0.08 if key.begins_with("spruce_young") else (0.21 if key.begins_with("birch") else 0.3)
		_own(veg, sc)
	# трава — покровом вокруг камеры, как в районе ТЦ
	var grass := DistrictGrass.new()
	grass.name = "Grass"
	grass.density_map = OUT + "grass_density.png"
	grass.origin = AREA.position
	grass.per_m2 = 9.0
	grass.radius = 26.0
	grass.models = PackedStringArray([VEG + "ug_grass_tall_a.glb", VEG + "ug_grass_tall_b.glb", VEG + "ug_grass_tall_a.glb", VEG + "ug_grass_small.glb", VEG + "ug_grass_mid_b.glb", VEG + "ug_grass2_c.glb"])
	grass.weed_models = PackedStringArray([VEG + "ug_weed_a.glb", VEG + "ug_weed_b.glb", VEG + "ug_dandelion_c.glb", VEG + "ug_dandelion_e.glb"])
	_own(veg, grass)


func _start_zone() -> void:
	var zone := RaidStartZone.new()
	zone.name = "StartZone"
	zone.radius = float(Balance.SHELTER_YARD.start_radius)
	zone.position = Vector3(0.0, _ground_y, YARD_S - 4.5)
	_own(_root, zone)
