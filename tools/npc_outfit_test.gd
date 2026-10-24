extends Node3D
## Внешность ботов по снаряжению (NpcOutfit, схема docs/design/npc_gear_by_type.md): мародёр на новом теле,
## броня, шлем, рюкзак в посадке по броне, забрало у штурмовика «Периметра», подсумки по магазинам, LOD по
## дальности, единый стиль чужого отряда. Без окна — проверки; с окном (--windowed --resolution 1600x900)
## — снимки docs/screens/npc_outfit_*.png: ряд типов спереди и сзади.

## [подпись, тип, выкладка]
const LINEUP := [
	["жилец", "resident", "civilian"],
	["оборванец", "scout", "scav_poor"],
	["мародёр", "gunner", "scav_standard"],
	["бывалый", "heavy", "scav_veteran"],
	["стрелок", "sniper", "scav_sniper"],
	["главарь", "gunner", "scav_leader"],
	["«Периметр» стрелок", "pmc", "perimeter_rifleman"],
	["«Периметр» штурмовик", "pmc", "perimeter_breacher"],
]

var _fails: int = 0
var _bots: Array[Marauder] = []


func _ready() -> void:
	_world()
	await get_tree().process_frame
	var i: int = 0
	for row: Array in LINEUP:
		var m := load("res://scenes/ai/marauder.tscn").instantiate() as Marauder
		m.name = "Bot_%d" % i
		m.archetype = String(row[1])
		m.loadout_id = String(row[2])
		m.position = Vector3((float(i) - 3.5) * 1.3, 0.0, 0.0)
		add_child(m)
		m.process_mode = Node.PROCESS_MODE_DISABLED
		_bots.append(m)
		i += 1
	await get_tree().process_frame
	await get_tree().process_frame
	for k in range(_bots.size()):
		_check_bot(_bots[k], String(LINEUP[k][0]))
	_check_rival_style()
	if "shots" in OS.get_cmdline_user_args():
		await _shots()
	print("npc_outfit_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s%s" % ["ok" if ok else "FAIL", what, "" if detail == "" else " — " + detail])


func _skeleton(m: Marauder) -> Skeleton3D:
	var found: Array[Node] = m.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)
	return found[0] as Skeleton3D if not found.is_empty() else null


func _check_bot(m: Marauder, label: String) -> void:
	var sk := _skeleton(m)
	_check("%s: новое тело (52 кости, HipsHeight)" % label, sk != null and sk.get_bone_count() == 52 and sk.get_node_or_null("HipsHeight") != null)
	if sk == null:
		return
	var parsed: Variant = JSON.parse_string(m.outfit) if m.outfit != "" else null
	_check("%s: внешность описана" % label, parsed is Dictionary, m.outfit)
	if not parsed is Dictionary:
		return
	var d := parsed as Dictionary
	var names: Dictionary = {}
	for n: Node in sk.get_children():
		names[n.name] = n
	for slot: String in ["armor", "helmet", "backpack"]:
		var eq_id := String((m.equipment.get(slot, {}) as Dictionary).get("id", ""))
		_check("%s: %s в описании как в снаряжении (%s)" % [label, slot, eq_id if eq_id != "" else "нет"], String(d.get(slot, "")) == eq_id)
	var fit: String = ""
	if d.has("armor"):
		var npc: Dictionary = WeaponDb.vest(String(d.armor)).get("npc", {})
		fit = String(npc.get("fit", ""))
		_check("%s: броня %s надета (%s + LOD1, LOD2)" % [label, String(d.armor), String(npc.mesh)],
			names.has(String(npc.mesh)) and names.has(String(npc.mesh) + "_LOD1") and names.has(String(npc.mesh) + "_LOD2"))
		var mi := names.get(String(npc.mesh)) as MeshInstance3D
		_check("%s: броня со скином на скелете тела" % label, mi != null and mi.skin != null and mi.get_node(mi.skeleton) == sk)
	if d.has("helmet"):
		var npc: Dictionary = WeaponDb.helmet(String(d.helmet)).get("npc", {})
		_check("%s: шлем %s надет" % [label, String(d.helmet)], names.has(String(npc.mesh)))
		var visor: bool = names.has(String(npc.get("visor_mesh", "—")))
		_check("%s: забрало %s" % [label, "есть" if bool(d.get("visor", false)) else "нет"], visor == bool(d.get("visor", false)))
	if d.has("backpack"):
		var npc: Dictionary = ItemDb.item(String(d.backpack)).get("npc", {})
		var mesh := String(npc.mesh) + ("_" + fit if fit != "" else "")
		_check("%s: рюкзак %s в посадке «%s» (%s)" % [label, String(d.backpack), fit if fit != "" else "без брони", mesh], names.has(mesh))
	var pouches: Array = d.get("pouches", [])
	var places: int = int(WeaponDb.vest(String(d.get("armor", ""))).get("places", 0))
	var holders: int = 0
	for n: Node in sk.get_children():
		if n.name.begins_with("Place_"):
			holders += 1
	_check("%s: подсумков %d (мест %d, магазинов %d)" % [label, pouches.size(), places, m.spare.size()], holders == pouches.size() and pouches.size() <= places)
	# LOD по дальности: тело и вещи
	var lod: Array = Balance.CHARACTER_LOD.mesh_m
	var j := names.get("G_Jacket") as MeshInstance3D
	var j1 := names.get("G_Jacket_LOD1") as MeshInstance3D
	_check("%s: LOD тела по дальности (%d / %d м)" % [label, int(lod[0]), int(lod[1])], j != null and j1 != null and is_equal_approx(j.visibility_range_end, float(lod[0])) and is_equal_approx(j1.visibility_range_begin, float(lod[0])) and is_equal_approx(j1.visibility_range_end, float(lod[1])))
	if d.has("armor"):
		var npc: Dictionary = WeaponDb.vest(String(d.armor)).get("npc", {})
		var a2 := names.get(String(npc.mesh) + "_LOD2") as MeshInstance3D
		_check("%s: LOD брони по дальности" % label, a2 != null and is_equal_approx(a2.visibility_range_begin, float(lod[1])) and a2.visibility_range_end == 0.0)


## Чужой отряд: броня, шлем и рюкзак как у ведущего.
func _check_rival_style() -> void:
	var sq := Squad.new()
	var members: Array[Marauder] = []
	for k in range(3):
		var m := load("res://scenes/ai/marauder.tscn").instantiate() as Marauder
		m.name = "Rival_%d" % k
		m.archetype = "rival" if k < 2 else "rival_scout"
		m.position = Vector3(float(k) * 1.3 - 1.3, 0.0, -3.0)
		add_child(m)
		m.process_mode = Node.PROCESS_MODE_DISABLED
		sq.add(m)
		members.append(m)
	var same := true
	var detail: PackedStringArray = []
	for m in members:
		var d: Variant = JSON.parse_string(m.outfit)
		var row: String = "%s/%s/%s" % [String((d as Dictionary).get("armor", "-")), String((d as Dictionary).get("helmet", "-")), String((d as Dictionary).get("backpack", "-"))]
		detail.append(row)
	for slot: String in ["armor", "helmet", "backpack"]:
		var lead := String((members[0].equipment.get(slot, {}) as Dictionary).get("id", ""))
		var second := String((members[1].equipment.get(slot, {}) as Dictionary).get("id", ""))
		if lead != second:
			same = false
	_check("чужой отряд: двое из трёх (одна выкладка) одеты как ведущий", same, ", ".join(detail))
	for m in members:
		_bots.append(m)


func _shots() -> void:
	var cam := Camera3D.new()
	cam.fov = 40.0
	add_child(cam)
	cam.current = true
	# боты стоят лицом к +Z: камера с +Z видит их спереди
	var views: Array = [["front", Vector3(0.0, 1.3, 9.5), Vector3(0.0, 1.0, 0.0)], ["back", Vector3(0.0, 1.3, -9.5), Vector3(0.0, 1.0, 0.0)],
		["close_front", Vector3(2.0, 1.3, 4.0), Vector3(2.0, 1.1, 0.0)], ["close_back", Vector3(-1.2, 1.3, -4.0), Vector3(-1.2, 1.1, 0.0)],
		["rivals", Vector3(0.0, 1.3, 5.0), Vector3(0.0, 1.0, -3.0)]]
	for v: Array in views:
		cam.global_position = v[1]
		cam.look_at(v[2], Vector3.UP)
		for i in range(4):
			await get_tree().process_frame
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/npc_outfit_%s.png" % String(v[0])))
		print("SHOT ", v[0])


func _world() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50.0, 35.0, 0.0)
	sun.shadow_enabled = true
	add_child(sun)
	var floor := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(40.0, 40.0)
	floor.mesh = plane
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.5, 0.5, 0.5)
	floor.material_override = mat
	add_child(floor)
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(40.0, 0.2, 40.0)
	shape.shape = box
	shape.position.y = -0.1
	body.add_child(shape)
	add_child(body)
