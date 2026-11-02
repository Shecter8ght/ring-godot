extends RefCounted
## Модули Blender этапа 2 в стенде общежития (tools/dorm_modules/godot_export.py → assets/models/dorm): коробки дверей
## комнат (проём 1,17 × 2,415 в стене 0,38), полотна этих дверей (узел двери на петле — dorm_study_door.gd), окна
## 2,096 × 1,65 и батареи под ними. Черновые бруски тех же мест не строятся (dorm_geometry.gd спрашивает skip),
## коллизии стекла, подоконника и батареи остаются. Проём 1,17 × 2,415 — чистый (по четверти коробки); добор коробки
## стоит за ним, в черновом проёме 1,244 × 2,452, — стены у таких дверей подрезаются до него (trim), коллизия прежняя.
## Лестница: марши 12 и 10 ступеней шириной 1,5 — модули M09 / M10 с ограждением M12 (сбоку к просвету), на каждой
## площадке, где марш переходит в следующий, — поворот поручня M13 через просвет 0,30; площадки — бетоном (палитра
## stair_landing). Черновые ступени и перила не рисуются, их коллизия (наклонная плоскость марша, перила) — прежняя.
## Без файлов модулей стенд прежний.
## Оси модулей (Blender): X вдоль стены, +Y — коридор у двери / комната у окна / подъём марша; в Godot +Y Blender → −Z.

const DIR: String = "res://assets/models/dorm"
const PARTS: Array[String] = ["door_frame", "door_leaf", "window", "radiator"]
const STAIR_PARTS: Array[String] = ["stair_flight_12", "stair_flight_10", "stair_rail_12", "stair_rail_10",
	"stair_turn_12_12", "stair_turn_10_10", "stair_turn_12_10"]
## Марши-модули: число ступеней → суффикс файлов; ширина марша и полупросвет между осями маршей.
const FLIGHTS: Dictionary = {12: "12", 10: "10"}
const FLIGHT_WIDTH: float = 1.5
const FLIGHT_AXIS_TO_GAP: float = 0.9
## Слоты Blender, которые берут материал палитры стенда (побелка v03 по миру, мозаика); без карт v03 — черновые.
const PALETTE_SLOTS: Dictionary = {"Побелка_потолок": ["ceiling"], "Ступени_мозаика": ["stair_tread", "slab"]}
const FACADE_HALF: float = 0.32
const SILL_ABOVE_FLOOR: float = 0.85
## Модуль окна — на 3 мм выше: верх его подоконника совпадал с верхом кладки под окном и мерцал.
const SILL_LIFT: float = 0.003
## Черновой проём коробки M01 (снят с модели: наружная грань добора 0,622 от оси, верх 2,452 от пола).
const DOOR_ROUGH_HALF: float = 0.622
const DOOR_ROUGH_TOP: float = 2.452

static var _meshes: Dictionary = {}
static var _materials: Dictionary = {}

var plan: Dictionary
var section_id: String
var palette: Dictionary
var doors: Dictionary = {}          # uid → запись плана
var windows: Dictionary = {}        # «window_014» → запись плана
var radiator_windows: Dictionary = {}
var flights: Array[Dictionary] = []
var _door_re: RegEx = RegEx.create_from_string("^(door_\\d+)_(lining|casing|casing_top)$")
var _window_re: RegEx = RegEx.create_from_string("^(window_\\d+)_(sill|radiator|radiator_link)$")


static func available() -> bool:
	return _parts_exist(PARTS)


static func _stairs_available() -> bool:
	return _parts_exist(STAIR_PARTS)


static func _parts_exist(parts: Array[String]) -> bool:
	for part: String in parts:
		if not ResourceLoader.exists("%s/%s.glb" % [DIR, part]):
			return false
	return true


## true — марш ставится модулем: черновые ступени не рисуются (коллизию строит стенд).
func flight(item: Dictionary) -> bool:
	return _stairs_available() and FLIGHTS.has(int(item.count)) and _near(item.width, FLIGHT_WIDTH)


## true — перила лестницы, у которой марши — модули: вид даёт ограждение M12, коллизия остаётся.
func rail_beam(item: Dictionary) -> bool:
	return not flights.is_empty() and String(item.get("mat", "")) == "rail"


func _init(value: Dictionary, section: String, materials: Dictionary) -> void:
	plan = value
	section_id = section
	palette = materials
	var data: Dictionary = (plan.get("sections", {}) as Dictionary).get(section_id, {})
	if _stairs_available():
		for item: Dictionary in data.get("stairs", []):
			if flight(item):
				flights.append(item)
	for item: Dictionary in plan.doors:
		if String(item.section) == section_id and _near(item.width, 1.17) and _near(item.height, 2.415) and _near(item.thickness, 0.38):
			doors[String(item.uid)] = item
	for i: int in range(plan.windows.size()):
		var w: Dictionary = plan.windows[i]
		if String(w.section) == section_id and _near(w.width, 2.096):
			windows["window_%03d" % i] = w


## true — брусок заменён модулем; коллизию, где она нужна, оставляет builder.collision_box.
func skip(item: Dictionary, builder: RefCounted) -> bool:
	var id: String = String(item.get("id", ""))
	var m: RegExMatch = _door_re.search(id)
	if m != null:
		return doors.has(m.get_string(1))
	m = _window_re.search(id)
	if m != null and windows.has(m.get_string(1)):
		if m.get_string(2) != "sill":
			radiator_windows[m.get_string(1)] = true
		builder.call("collision_box", _vec(item.at), _vec(item.size))
		return true
	if id in ["window_frame", "window_glass", "window_rail"]:
		var at: Vector3 = _vec(item.at)
		for w: Dictionary in windows.values():
			if _in_window(at, w):
				if id == "window_glass":
					builder.call("collision_box", at, _vec(item.size))
				return true
	return false


## Брусок стены у двери-модуля — кусками под черновой проём коробки (откосы отходят на 37 мм, низ перемычки
## поднимается до верха коробки); срезанное остаётся коллизией. Остальные бруски — [item] как есть.
## Площадки лестницы с маршами-модулями — бетоном (палитра stair_landing), коробка та же; пол клетки 1-го этажа
## (stair_ground, та же коробка, что и площадка) — тоже, иначе две совпавшие поверхности мерцают.
func trim(item: Dictionary, builder: RefCounted) -> Array[Dictionary]:
	var result: Array[Dictionary] = [item]
	var id: String = String(item.get("id", ""))
	if id.begins_with("stair_") and (id.ends_with("_landing") or id == "stair_ground") and _stairs_available() and palette.has("stair_landing"):
		var landing: Dictionary = item.duplicate()
		landing.mat = "stair_landing"
		return [landing]
	if String(item.get("mat", "")) != "wall" or absf(float(item.get("yaw", 0.0))) > 0.001:
		return result
	var pieces: Array[AABB] = [AABB(_vec(item.at) - _vec(item.size) * 0.5, _vec(item.size))]
	var changed: bool = false
	for d: Dictionary in doors.values():
		var next: Array[AABB] = []
		for box: AABB in pieces:
			var cut: Array[AABB] = _cut(box, d, builder)
			changed = changed or cut.size() != 1 or not cut[0].is_equal_approx(box)
			next.append_array(cut)
		pieces = next
	if not changed:
		return result
	result.clear()
	for box: AABB in pieces:
		var piece: Dictionary = item.duplicate()
		var center: Vector3 = box.get_center()
		piece.at = [center.x, center.y, center.z]
		piece.size = [box.size.x, box.size.y, box.size.z]
		result.append(piece)
	return result


func _cut(box: AABB, d: Dictionary, builder: RefCounted) -> Array[AABB]:
	var c: Vector3 = _vec(d.at)
	var a: int = 0 if String(d.axis) == "z" else 2  # вдоль стены
	var b: int = 2 - a
	var lo: Vector3 = box.position
	var hi: Vector3 = box.end
	if lo[b] > c[b] - 0.15 or hi[b] < c[b] + 0.15:
		return [box]
	var left: float = c[a] - float(d.width) * 0.5
	var right: float = c[a] + float(d.width) * 0.5
	var clear_top: float = c.y + float(d.height)
	var rough_top: float = c.y + DOOR_ROUGH_TOP
	if absf(lo[a] - left) < 0.003 and absf(hi[a] - right) < 0.003 and absf(lo.y - clear_top) < 0.003:
		var slice_hi: Vector3 = hi
		slice_hi.y = rough_top
		builder.call("collision_box", (lo + slice_hi) * 0.5, slice_hi - lo)
		lo.y = rough_top
		return [AABB(lo, hi - lo)]
	var side: int = -1 if absf(hi[a] - left) < 0.003 else (1 if absf(lo[a] - right) < 0.003 else 0)
	if side == 0 or lo.y >= rough_top - 0.003 or hi.y <= c.y + 0.003:
		return [box]
	var out: Array[AABB] = []
	if hi.y > rough_top + 0.003:
		var upper: Vector3 = lo
		upper.y = rough_top
		out.append(AABB(upper, hi - upper))
	var low_hi: Vector3 = hi
	low_hi.y = minf(hi.y, rough_top)
	var low_lo: Vector3 = lo
	var slice_lo: Vector3 = lo
	var slice_hi2: Vector3 = low_hi
	if side < 0:
		low_hi[a] = c[a] - DOOR_ROUGH_HALF
		slice_lo[a] = low_hi[a]
	else:
		low_lo[a] = c[a] + DOOR_ROUGH_HALF
		slice_hi2[a] = low_lo[a]
	builder.call("collision_box", (slice_lo + slice_hi2) * 0.5, slice_hi2 - slice_lo)
	out.append(AABB(low_lo, low_hi - low_lo))
	return out


## Полотно двери из модуля — узлу двери на петле (dorm_study_door.gd); null — прежнее черновое.
func leaf_mesh(door: Dictionary) -> Mesh:
	return mesh("door_leaf") if doors.has(String(door.get("door_uid", ""))) else null


func place(target: Node3D) -> void:
	var root: Node3D = Node3D.new()
	root.name = "Modules"
	target.add_child(root)
	for uid: String in doors:
		var d: Dictionary = doors[uid]
		var inward: float = float(d.get("inward", 1))
		var corridor: Vector3 = Vector3(0, 0, -inward) if String(d.axis) == "z" else Vector3(-inward, 0, 0)
		_instance(root, "door_frame", uid, _vec(d.at), corridor)
	for wid: String in windows:
		var w: Dictionary = windows[wid]
		var at: Vector3 = _vec(w.at)
		var floor_at: Vector3 = Vector3(at.x, at.y - SILL_ABOVE_FLOOR + SILL_LIFT, at.z)
		var room: Vector3 = _room_dir(w)
		_instance(root, "window", wid, floor_at, room)
		if radiator_windows.has(wid):
			_instance(root, "radiator", wid + "_radiator", floor_at + room * FACADE_HALF, room)
	for i: int in range(flights.size()):
		var f: Dictionary = flights[i]
		var start: Vector3 = _vec(f.start)
		var end: Vector3 = _vec(f.end)
		var up: Vector3 = Vector3(end.x - start.x, 0, end.z - start.z).normalized()
		var n: String = String(FLIGHTS[int(f.count)])
		_instance(root, "stair_flight_" + n, "%02d" % i, start, up)
		_instance(root, "stair_rail_" + n, "%02d" % i, start, up)
		# Поворот поручня — где с площадки этого марша следующий уходит вверх по ту сторону просвета (ограждение M12 —
		# на +X марша, к просвету).
		var gap_side: Vector3 = Basis(Vector3.UP, atan2(-up.x, -up.z)) * Vector3.RIGHT
		for g: Dictionary in flights:
			var offset: Vector3 = _vec(g.start) - end
			if absf(offset.y) < 0.02 and absf(offset.dot(up)) < 0.05 and absf(offset.dot(gap_side) - FLIGHT_AXIS_TO_GAP * 2.0) < 0.05:
				var turn: String = "stair_turn_%s_%s" % [n, String(FLIGHTS[int(g.count)])]
				_instance(root, turn, "%02d" % i, end + gap_side * FLIGHT_AXIS_TO_GAP, up)


func _instance(root: Node3D, part: String, id: String, at: Vector3, side: Vector3) -> void:
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = "%s_%s" % [part, id]
	node.mesh = mesh(part)
	# +Y модуля (в Godot −Z) — в сторону side
	node.transform = Transform3D(Basis(Vector3.UP, atan2(-side.x, -side.z)), at)
	# Модули — не в запекании VoxelGI (их краску CPU не считает), свет и тени — обычные.
	node.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
	apply_materials(node, palette)
	root.add_child(node)


func _room_dir(w: Dictionary) -> Vector3:
	var at: Vector3 = _vec(w.at)
	var rect: Array = plan.annex_rect if _inside(at, plan.annex_rect, 1.0) else plan.main_rect
	var center: Vector2 = Vector2((float(rect[0]) + float(rect[2])) * 0.5, (float(rect[1]) + float(rect[3])) * 0.5)
	if String(w.axis) == "z":
		return Vector3(0, 0, 1.0 if at.z < center.y else -1.0)
	return Vector3(1.0 if at.x < center.x else -1.0, 0, 0)


func _in_window(at: Vector3, w: Dictionary) -> bool:
	var c: Vector3 = _vec(w.at)
	var along: float = absf(at.x - c.x) if String(w.axis) == "z" else absf(at.z - c.z)
	var across: float = absf(at.z - c.z) if String(w.axis) == "z" else absf(at.x - c.x)
	return along <= float(w.width) * 0.5 + 0.1 and across <= 0.35 and at.y >= c.y - 0.1 and at.y <= c.y + float(w.height) + 0.1


static func mesh(part: String) -> Mesh:
	if not _meshes.has(part):
		var scene: PackedScene = load("%s/%s.glb" % [DIR, part]) as PackedScene
		var node: Node = scene.instantiate()
		var found: Mesh = null
		for child: Node in node.find_children("*", "MeshInstance3D", true, false):
			found = (child as MeshInstance3D).mesh
			break
		node.free()
		_meshes[part] = found
	return _meshes[part] as Mesh


## Материалы по именам слотов Blender (glTF их сохраняет); побелка и бетон ступеней — из палитры стенда.
static func apply_materials(node: MeshInstance3D, materials: Dictionary = {}) -> void:
	for s: int in range(node.mesh.get_surface_count()):
		var source: Material = node.mesh.surface_get_material(s)
		var name: String = source.resource_name if source != null else ""
		var material: Material = _material(name)
		for key: String in PALETTE_SLOTS.get(name, []):
			if materials.has(key):
				material = materials[key] as Material
				break
		if material != null:
			node.set_surface_override_material(s, material)


static func _material(name: String) -> Material:
	if _materials.has(name):
		return _materials[name] as Material
	var result: Material = null
	match name:
		"Коробка_наличник_краска": result = _paint(0, "8a7b66", 0.45, 1.0, 0.0)
		"Дверь_краска": result = _paint(0, "6b4c34", 0.42, 1.0, 0.0)
		"Окно_краска_белая": result = _paint(0, "e2e0d6", 0.4, 1.0, 0.0)
		"Батарея_краска": result = _paint(1, "d8d4c4", 0.42, 3.0, 1.0)
		"Ограждение_краска": result = _paint(1, "2c3230", 0.45, 2.0, 0.6)
		"Поручень_дерево": result = _paint(2, "3a2416", 0.32, 1.0, 0.0)
		"Алюминий": result = _metal("b9bbbd", 0.38)
		"Сталь_тёмная": result = _metal("3a3b3c", 0.48)
		"Отлив_оцинковка": result = _metal("8f9497", 0.5)
		"Стекло":
			var glass: StandardMaterial3D = StandardMaterial3D.new()
			glass.albedo_color = Color(0.85, 0.88, 0.88, 0.1)
			glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			glass.roughness = 0.04
			glass.cull_mode = BaseMaterial3D.CULL_DISABLED
			result = glass
	_materials[name] = result
	return result


static func _paint(mode: int, hexcolor: String, rough: float, scale: float, rust: float) -> ShaderMaterial:
	var m: ShaderMaterial = ShaderMaterial.new()
	m.shader = load("res://src/blockout/dorm_v3/dorm_module_paint.gdshader") as Shader
	m.set_shader_parameter("mode", mode)
	m.set_shader_parameter("paint", Color(hexcolor))
	m.set_shader_parameter("rough_base", rough)
	m.set_shader_parameter("uv_scale", scale)
	m.set_shader_parameter("rust", rust)
	var tex: Dictionary = {"wood_albedo": "res://assets/textures/dorm_v3/painted_wood_albedo.webp",
		"wood_rough": "res://assets/textures/dorm_v3/painted_wood_rough.png",
		"wood_normal": "res://assets/textures/dorm_v3/painted_wood_normal.png",
		"wood_ao": "res://assets/textures/dorm_v3/painted_wood_ao.png",
		"metal_albedo": "res://assets/textures/green_metal_rust/albedo.jpg",
		"metal_arm": "res://assets/textures/green_metal_rust/arm.jpg",
		"metal_normal": "res://assets/textures/green_metal_rust/normal.jpg",
		"sapele_albedo": "res://assets/textures/sapele_veneer/albedo.jpg",
		"sapele_normal": "res://assets/textures/sapele_veneer/normal.jpg",
		"wear_noise": "res://assets/textures/dorm_v3/dorm_wear_noise.png"}
	for key: String in tex:
		if ResourceLoader.exists(String(tex[key])):
			m.set_shader_parameter(key, load(String(tex[key])))
	return m


static func _metal(hexcolor: String, rough: float) -> StandardMaterial3D:
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = Color(hexcolor)
	m.metallic = 1.0
	m.roughness = rough
	return m


static func _near(value: Variant, target: float) -> bool:
	return absf(float(value) - target) < 0.011


static func _inside(at: Vector3, rect: Array, pad: float) -> bool:
	return at.x >= float(rect[0]) - pad and at.z >= float(rect[1]) - pad and at.x <= float(rect[2]) + pad and at.z <= float(rect[3]) + pad


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]), float(values[1]), float(values[2]))
