class_name NpcGear
## Снаряжение на скелете NPC (mixamorig_*, tools/npc_kit/game_rig.py). Вещи лежат в
## assets/models/characters/npc_gear/<вещь>/<вещь>.gltf со своей копией того же скелета: сетка со скином
## переносится под Skeleton3D персонажа (кости те же — по именам и по порядку), её собственный скелет
## выбрасывается. Подсумки — без скелета: BoneAttachment3D в месте брони (places.json: кость, положение и
## поворот в пространстве скелета; у места +X — поперёк, −Z — наружу от брони, +Y — вверх).

const GEAR_DIR := "res://assets/models/characters/npc_gear/"
const PLACES := GEAR_DIR + "places.json"

static var _places: Dictionary = {}


## Сетка вещи со скином — под скелет персонажа. mesh_name — имя узла в glTF (G_Helmet_Mid, G_Raid_Poor…).
static func attach_skinned(sk: Skeleton3D, item: String, mesh_name: String) -> MeshInstance3D:
	var scene := load(GEAR_DIR + item + "/" + item + ".gltf") as PackedScene
	if scene == null:
		push_error("NpcGear: нет вещи %s" % item)
		return null
	var root: Node = scene.instantiate()
	var src := root.find_child(mesh_name, true, false) as MeshInstance3D
	if src == null:
		push_error("NpcGear: в %s нет сетки %s" % [item, mesh_name])
		root.free()
		return null
	var mi := MeshInstance3D.new()
	mi.name = mesh_name
	mi.mesh = src.mesh
	mi.skin = src.skin
	for i in range(src.get_surface_override_material_count()):
		mi.set_surface_override_material(i, src.get_surface_override_material(i))
	sk.add_child(mi)
	mi.skeleton = NodePath("..")
	root.free()
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
static func attach_pouch(holder: Node3D, mesh_name: String) -> MeshInstance3D:
	var scene := load(GEAR_DIR + "pouches/pouches.gltf") as PackedScene
	if scene == null:
		push_error("NpcGear: нет подсумков")
		return null
	var root: Node = scene.instantiate()
	var src := root.find_child(mesh_name, true, false) as MeshInstance3D
	if src == null:
		push_error("NpcGear: нет подсумка %s" % mesh_name)
		root.free()
		return null
	var mi := MeshInstance3D.new()
	mi.name = mesh_name
	mi.mesh = src.mesh
	for i in range(src.get_surface_override_material_count()):
		mi.set_surface_override_material(i, src.get_surface_override_material(i))
	holder.add_child(mi)
	var aabb: AABB = src.mesh.get_aabb()
	mi.position = Vector3(-aabb.get_center().x, 0.0, -aabb.end.z)
	root.free()
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
