class_name NpcGear
## Снаряжение на скелете NPC (mixamorig_*, tools/npc_kit/game_rig.py). Вещи лежат в
## assets/models/characters/npc_gear/<вещь>/<вещь>.gltf со своей копией того же скелета: сетка со скином
## переносится под Skeleton3D персонажа (кости те же — по именам и по порядку), её собственный скелет
## выбрасывается. Подсумки — без скелета: BoneAttachment3D в месте брони (places.json: кость, положение и
## поворот в пространстве скелета; у места +X — поперёк, −Z — наружу от брони, +Y — вверх).
## Сцена каждой вещи раскрывается один раз (library): два десятка ботов не грузят glTF заново.

const GEAR_DIR := "res://assets/models/characters/npc_gear/"
const PLACES := GEAR_DIR + "places.json"

static var _places: Dictionary = {}
## Вещь → {имя сетки: {mesh, skin, materials}}.
static var _lib: Dictionary = {}


## Разобранный glTF вещи: сетки, скины и материалы по именам узлов.
static func library(item: String) -> Dictionary:
	if _lib.has(item):
		return _lib[item]
	var out: Dictionary = {}
	var scene := load(GEAR_DIR + item + "/" + item + ".gltf") as PackedScene
	if scene == null:
		push_error("NpcGear: нет вещи %s" % item)
		_lib[item] = out
		return out
	var root: Node = scene.instantiate()
	for n: Node in root.find_children("*", "MeshInstance3D", true, false):
		var m := n as MeshInstance3D
		var mats: Array = []
		for i in range(m.get_surface_override_material_count()):
			mats.append(m.get_surface_override_material(i))
		out[m.name] = {"mesh": m.mesh, "skin": m.skin, "materials": mats}
	root.free()
	_lib[item] = out
	return out


static func has_mesh(item: String, mesh_name: String) -> bool:
	return library(item).has(mesh_name)


## Сетка вещи со скином — под скелет персонажа. mesh_name — имя узла в glTF (G_Helmet_Mid, G_Raid_Poor…).
static func attach_skinned(sk: Skeleton3D, item: String, mesh_name: String) -> MeshInstance3D:
	var rec: Dictionary = library(item).get(mesh_name, {})
	if rec.is_empty():
		push_error("NpcGear: в %s нет сетки %s" % [item, mesh_name])
		return null
	var mi := _instance(rec, mesh_name)
	mi.skin = rec.skin
	sk.add_child(mi)
	mi.skeleton = NodePath("..")
	return mi


## Место подсумка на броне: узел на кости, в rest-позе стоит в точке места. tier — poor / mid / top / belt.
static func place(sk: Skeleton3D, tier: String, n: int) -> Node3D:
	var rec: Dictionary = _place_record(tier, n)
	if rec.is_empty():
		push_error("NpcGear: нет места %s/%d" % [tier, n])
		return null
	var bone: int = sk.find_bone(String(rec.bone))
	if bone < 0:
		push_error("NpcGear: нет кости %s" % String(rec.bone))
		return null
	var att := BoneAttachment3D.new()
	att.name = "Place_%s_%d" % [tier, n]
	att.bone_name = String(rec.bone)
	sk.add_child(att)
	var p: Array = rec.pos
	var q: Array = rec.quat
	var world := Transform3D(Basis(Quaternion(float(q[0]), float(q[1]), float(q[2]), float(q[3]))), Vector3(float(p[0]), float(p[1]), float(p[2])))
	var holder := Node3D.new()
	holder.name = "Holder"
	att.add_child(holder)
	holder.transform = sk.get_bone_global_rest(bone).affine_inverse() * world
	holder.set_meta("mirror", bool(rec.mirror))
	return holder


## Подсумок в месте: сетка подсумка (с ключами формы) спиной к броне. В исходнике подсумки разложены рядом
## (сдвиг по X), дно на нулевой высоте, наружу — −Z после экспорта: по X — в середину места, дно — в точку
## места, задняя стенка (max Z) — к броне.
static func attach_pouch(holder: Node3D, mesh_name: String, shift_x: float = 0.0) -> MeshInstance3D:
	var rec: Dictionary = library("pouches").get(mesh_name, {})
	if rec.is_empty():
		push_error("NpcGear: нет подсумка %s" % mesh_name)
		return null
	var mi := _instance(rec, mesh_name)
	holder.add_child(mi)
	var aabb: AABB = (rec.mesh as Mesh).get_aabb()
	mi.position = Vector3(shift_x - aabb.get_center().x, 0.0, -aabb.end.z)
	return mi


## Шаг между соседними местами брони tier у места n (по данным places.json; у одиночного места — 0).
static func place_pitch(tier: String, n: int) -> float:
	var a := _place_record(tier, n)
	if a.is_empty():
		return 0.0
	for m: int in [n + 1, n - 1]:
		var b := _place_record(tier, m)
		if not b.is_empty() and String(b.get("kind", "")) == String(a.get("kind", "")):
			var pa: Array = a.pos
			var pb: Array = b.pos
			return Vector3(float(pa[0]), float(pa[1]), float(pa[2])).distance_to(Vector3(float(pb[0]), float(pb[1]), float(pb[2])))
	return 0.0


static func _instance(rec: Dictionary, mesh_name: String) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.name = mesh_name
	mi.mesh = rec.mesh
	var mats: Array = rec.materials
	for i in range(mats.size()):
		mi.set_surface_override_material(i, mats[i])
	return mi


static func _place_record(tier: String, n: int) -> Dictionary:
	if _places.is_empty():
		if not FileAccess.file_exists(PLACES):
			return {}
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PLACES))
		if parsed is Dictionary:
			_places = parsed
	var t: Dictionary = _places.get(tier, {})
	for rec: Dictionary in t.get("places", []):
		if int(rec.n) == n:
			return rec
	return {}


## Сколько мест у брони по places.json (0 — нет мест).
static func places_count(tier: String) -> int:
	_place_record(tier, 1)
	return ((_places.get(tier, {}) as Dictionary).get("places", []) as Array).size()
