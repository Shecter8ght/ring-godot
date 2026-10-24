class_name NpcOutfit
extends Node
## Внешность бота из его снаряжения (схема docs/design/npc_gear_by_type.md, правило «что видно — то и есть»):
## броня, шлем (забрало — у штурмовика «Периметра»), рюкзак в посадке по броне, подсумки по запасным
## магазинам в местах брони. Модели — из данных (armor.npc, helmet.npc, items.npc) через NpcGear на скелет
## тела. Набор описывает хост строкой (describe → Marauder.outfit, синхронизируется), все peer одевают
## одинаково. LOD по дальности: сетки *_LOD1 / *_LOD2 тела и вещей переключаются visibility_range
## (Balance.CHARACTER_LOD.mesh_m); у модели без LOD дальность не трогается.

var _worn: Array[Node] = []
var _spec: String = ""


func _ready() -> void:
	# модель тела — LOD по дальности сразу; снаряжение — когда хост опишет набор
	var sk := _skeleton()
	if sk:
		lod_ranges(sk)
	if _spec != "":
		apply(_spec)


## Описание набора по снаряжению бота: броня, шлем, рюкзак, забрало, подсумки по запасным магазинам
## (пистолетные — пистолетные, крупные от 50 патронов — большой на два места, остальные — автоматные).
static func describe(equipment: Dictionary, spare: Array, visor: bool) -> String:
	var d: Dictionary = {}
	for slot: String in ["armor", "helmet", "backpack"]:
		if equipment.has(slot):
			d[slot] = String((equipment[slot] as Dictionary).get("id", ""))
	if visor and d.has("helmet"):
		d["visor"] = true
	var places: int = int(WeaponDb.vest(String(d.get("armor", ""))).get("places", 0))
	if places > 0:
		var pistol: bool = String(WeaponDb.weapon(String((equipment.get("primary", {}) as Dictionary).get("id", ""))).get("class", "")) == "PISTOL"
		var pouches: Array = []
		var n: int = 1
		for it: Variant in spare:
			if n > places:
				break
			var e := it as Dictionary
			var mag: Dictionary = (WeaponDb.items().get(String(e.get("id", "")), {}) as Dictionary).get("mag", {})
			if mag.is_empty():
				continue                                    # патроны россыпью — не магазин
			var cap: int = int(mag.get("capacity", 30))
			var item: String = "pouch_pistol" if pistol else ("pouch_big" if cap >= 50 else "pouch_rifle")
			var cost: int = 2 if item == "pouch_big" else 1
			if n + cost - 1 > places:
				continue
			pouches.append([n, item])
			n += cost
		if not pouches.is_empty():
			d["pouches"] = pouches
	return JSON.stringify(d)


## Надеть по описанию (пустая строка — снять всё).
func apply(spec: String) -> void:
	_spec = spec
	if not is_inside_tree():
		return
	_clear()
	var sk := _skeleton()
	if sk == null:
		return
	var parsed: Variant = JSON.parse_string(spec) if spec != "" else null
	if not parsed is Dictionary:
		return
	var d := parsed as Dictionary
	var fit: String = ""
	var tier: String = ""
	var armor := String(d.get("armor", ""))
	if armor != "":
		var npc: Dictionary = WeaponDb.vest(armor).get("npc", {})
		if not npc.is_empty():
			_wear(sk, String(npc.item), String(npc.mesh))
			fit = String(npc.get("fit", ""))
			tier = "belt" if fit == "" else fit.to_lower()
	var helmet := String(d.get("helmet", ""))
	if helmet != "":
		var npc: Dictionary = WeaponDb.helmet(helmet).get("npc", {})
		if not npc.is_empty():
			_wear(sk, String(npc.item), String(npc.mesh))
			if bool(d.get("visor", false)) and npc.has("visor_mesh"):
				_wear(sk, String(npc.item), String(npc.visor_mesh))
	var pack := String(d.get("backpack", ""))
	if pack != "":
		var npc: Dictionary = ItemDb.item(pack).get("npc", {})
		if not npc.is_empty():
			_wear(sk, String(npc.item), String(npc.mesh) + ("_" + fit if fit != "" else ""))
	if tier != "":
		for p: Variant in d.get("pouches", []):
			var rec: Array = p
			var mesh := String((ItemDb.item(String(rec[1])).get("pouch", {}) as Dictionary).get("npc_mesh", ""))
			if mesh == "":
				continue
			var holder := NpcGear.place(sk, tier, int(rec[0]))
			if holder:
				_worn.append(holder.get_parent())
				NpcGear.attach_pouch(holder, mesh)
	lod_ranges(sk)


## Что надето сейчас (имена сеток и узлов мест) — для проверок.
func worn_names() -> PackedStringArray:
	var out: PackedStringArray = []
	for n: Node in _worn:
		if is_instance_valid(n):
			out.append(n.name)
	return out


func _wear(sk: Skeleton3D, item: String, mesh: String) -> void:
	for suffix: String in ["", "_LOD1", "_LOD2"]:
		if NpcGear.has_mesh(item, mesh + suffix):
			var mi := NpcGear.attach_skinned(sk, item, mesh + suffix)
			if mi:
				_worn.append(mi)


func _clear() -> void:
	for n: Node in _worn:
		if is_instance_valid(n):
			n.get_parent().remove_child(n)
			n.queue_free()
	_worn.clear()


func _skeleton() -> Skeleton3D:
	var model: Node = get_parent().get_node_or_null("Body/Persona")
	if model == null:
		return null
	var found: Array[Node] = model.find_children("*", "Skeleton3D", true, false)
	return found[0] as Skeleton3D if not found.is_empty() else null


## Дальности LOD по именам: G_X — до mesh_m[0], G_X_LOD1 — до mesh_m[1], G_X_LOD2 — дальше; с запасом на
## возврат, без плавного перехода. Сетка без собственных LOD (Persona) не трогается.
static func lod_ranges(root: Node) -> void:
	var lod: Dictionary = Balance.CHARACTER_LOD
	var m: Array = lod.mesh_m
	var margin: float = float(lod.mesh_margin_m)
	var names: Dictionary = {}
	var meshes: Array[Node] = root.find_children("*", "MeshInstance3D", true, false)
	for n: Node in meshes:
		names[n.name] = true
	for n: Node in meshes:
		var mi := n as MeshInstance3D
		var level: int = 2 if mi.name.ends_with("_LOD2") else (1 if mi.name.ends_with("_LOD1") else 0)
		if level == 0 and not names.has(mi.name + "_LOD1"):
			continue
		mi.visibility_range_begin = [0.0, float(m[0]), float(m[1])][level]
		mi.visibility_range_end = [float(m[0]), float(m[1]), 0.0][level]
		mi.visibility_range_begin_margin = margin if level > 0 else 0.0
		mi.visibility_range_end_margin = margin if level < 2 else 0.0
		mi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
