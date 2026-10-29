extends Node
## Снаряжение и убранное оружие на теле (владелец 2026-10-29: «надо, чтобы было видно»). Рейд «Проспекта»:
## игрок на теле мародёра одет по своему снаряжению (броня с подсумками, шлем, рюкзак), убранные стволы — за
## спиной (два — накрест, позади рюкзака), пистолет — в кобуре на правом бедре, ракетница — на левом; в руках —
## не висит; убрал — повесил; от первого лица своё — только тенью; убит — оружия на теле нет. Мародёр: сменил
## ствол — второй на теле, гостю виден ствол в руках (active_slot). С окном (--windowed --resolution 1600x900)
## — снимки docs/screens/slung_*.png.
## tools/godot.cmd --headless res://tools/slung_test.tscn

var _fails: int = 0
var _me: Player
var _cam: Camera3D


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node3D = load("res://scenes/levels/prospekt.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() < 2 or Raid.current == null or Raid.current.local_player() == null:
		await get_tree().process_frame
	for i in range(20):
		await get_tree().process_frame
	var bots: Array = level.get_node("Marauders").get_children()
	for m: Marauder in bots:
		m.process_mode = Node.PROCESS_MODE_DISABLED
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	await _player_checks()
	await _marauder_checks(bots)
	if DisplayServer.get_name() != "headless":
		await _shots(bots)
	print("slung_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _player_checks() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var eq: Dictionary = {
		"primary": WeaponDb.make_weapon("AR_01_PSO", rng),
		"secondary": WeaponDb.make_weapon("SG_02_TAC", rng),
		"sidearm": WeaponDb.make_weapon("HG_03_TAC", rng),
		"launcher": WeaponDb.bare_weapon("signal_launcher", rng),
		"armor": WeaponDb.make_vest("armor_mid", {"front": "", "back": ""}, 1.0),
		"helmet": ItemDb.make("helmet_mid", 1),
		"backpack": ItemDb.make("bp_raid", 1),
	}
	_me.inventory.equipment = eq
	_me.weapon_id = String((eq.primary as Dictionary).id)
	await _settle()
	var outfit := _me.get_node("NpcOutfit") as NpcOutfit
	var worn: PackedStringArray = outfit.worn_names()
	_check("игрок одет по снаряжению: броня, шлем, рюкзак (%s)" % ", ".join(worn),
		"G_Armor_Mid" in worn and "G_Helmet_Mid" in worn and _has_prefix(worn, "G_Raid"))
	var slung := _me.get_node("SlungWeapons") as SlungWeapons
	_check("в руках основной — на теле второй длинный, пистолет и ракетница", _names(slung) == ["Slung_back_0", "Slung_thigh_l", "Slung_thigh_r"], str(_names(slung)))
	# убрал оружие — основной тоже за спиной
	_me._holster()
	await _settle()
	_check("убрал — оба длинных за спиной накрест", _names(slung) == ["Slung_back_0", "Slung_back_1", "Slung_thigh_l", "Slung_thigh_r"], str(_names(slung)))
	var sk := _skel(_me)
	# кости — узлами на скелете: они идут за позой после всех модификаторов (рост таза), как и само оружие
	var anim := _me.get_node("CharacterAnimator") as CharacterAnimator
	var spine: Vector3 = anim.bone_node("mixamorig_Spine2").global_position
	var hips: Vector3 = anim.bone_node("mixamorig_Hips").global_position
	var fwd: Vector3 = (_me.get_node("Body") as Node3D).global_basis.z
	var pack_back := _farthest_back(sk, anim, fwd, spine)
	for a: Node in slung.anchors():
		var c := _centre(a as Node3D)
		var rel := c - spine
		if String(a.name).begins_with("Slung_back"):
			# центр ствола — у задней стенки рюкзака (внахлёст на толщину ткани), не висит в воздухе позади
			_check("%s: на рюкзаке (%.2f м за позвонком, рюкзак до %.2f), на уровне спины" % [a.name, -rel.dot(fwd), pack_back],
				-rel.dot(fwd) > pack_back - 0.09 and -rel.dot(fwd) < pack_back + 0.12 and absf(rel.y) < 0.35)
		else:
			var right: Vector3 = fwd.cross(Vector3.UP).normalized()
			var side := (c - hips).dot(right)
			var want_right := String(a.name).ends_with("_r")
			var below := hips.y - c.y
			_check("%s: на %s бедре (вбок %.2f м, ниже таза %.2f м)" % [a.name, "правом" if want_right else "левом", side, below],
				(side > 0.12 and side < 0.32 if want_right else side < -0.12 and side > -0.32) and below > 0.15 and below < 0.45)
	# от первого лица своё убранное — только тенью
	_me.set_first_person(true)
	var shadows_only := true
	for a: Node in slung.anchors():
		for mi: Node in a.find_children("*", "MeshInstance3D", true, false):
			if (mi as MeshInstance3D).cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
				shadows_only = false
	_check("от первого лица своё оружие на теле не видно (только тень)", shadows_only)
	_me.set_first_person(false)
	# пистолет в руках — в кобуре пусто
	_me.weapon_id = String((eq.sidearm as Dictionary).id)
	await _settle()
	_check("в руках пистолет — правое бедро пусто, оба длинных за спиной", _names(slung) == ["Slung_back_0", "Slung_back_1", "Slung_thigh_l"], str(_names(slung)))
	_me.weapon_id = String((eq.primary as Dictionary).id)
	await _settle()


func _marauder_checks(bots: Array) -> void:
	var m: Marauder = null
	for b: Marauder in bots:
		if b.equipment.has("primary") and b.equipment.has("secondary"):
			m = b
			break
	if m == null:
		m = bots[0]
		var rng := RandomNumberGenerator.new()
		m.equipment["secondary"] = WeaponDb.make_weapon("HG_03_TAC", rng)
		m._use("primary")
	var slung := m.get_node("SlungWeapons") as SlungWeapons
	_check("мародёр: основной в руках — запасной на теле (%s)" % str(_names(slung)), _names(slung).size() == 1)
	m._use("secondary")
	await get_tree().process_frame
	_check("мародёр: перешёл на запасной — основной на теле, ствол в руках виден гостю (active_slot)",
		_names(slung).size() == 1 and m.active_slot == "secondary", "%s, %s" % [_names(slung), m.active_slot])
	m._use("primary")
	await get_tree().process_frame
	m.process_mode = Node.PROCESS_MODE_INHERIT
	m._last_hit_from = m.global_position + Vector3(6.0, 1.5, 0.0)
	for t in range(40):
		if m.state == Marauder.State.DEAD:
			break
		m._health.take_damage(45.0, m._last_hit_from, "thorax")
		for i in range(4):
			await get_tree().physics_frame
	_check("мародёр убит — оружия на теле нет", m.state == Marauder.State.DEAD and _names(slung).is_empty(), str(_names(slung)))


func _shots(bots: Array) -> void:
	var out := ProjectSettings.globalize_path("res://docs/screens/")
	# своя камера на уровне (как prospekt_raid_shots), интерфейс скрыт; игрок — на открытой площади «Вершины»
	var level := get_tree().current_scene as Node3D
	for layer: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		(layer as CanvasLayer).visible = false
	var space := level.get_world_3d().direct_space_state
	var hit := space.intersect_ray(PhysicsRayQueryParameters3D.create(Vector3(50.0, 30.0, -12.0), Vector3(50.0, -10.0, -12.0), 1))
	if not hit.is_empty():
		_me.global_position = hit.position as Vector3
		_me.velocity = Vector3.ZERO
	_cam = Camera3D.new()
	var player_cam: Camera3D = get_viewport().get_camera_3d()
	if player_cam:
		_cam.cull_mask = player_cam.cull_mask
	_cam.fov = 40.0
	_cam.far = 2000.0
	level.add_child(_cam)
	_cam.make_current()
	_me._holster()
	_me.set_first_person(false)
	await _settle()
	var body := _me.get_node("Body") as Node3D
	var at: Vector3 = _me.global_position
	var fwd: Vector3 = body.global_basis.z
	var right: Vector3 = fwd.cross(Vector3.UP).normalized()
	var views: Array = [
		["slung_player_back", -fwd * 2.6 + right * 0.6, 1.25],
		["slung_player_side", right * 2.4 - fwd * 0.4, 1.1],
		["slung_player_front", fwd * 2.6 + right * 0.5, 1.2],
		["slung_holster_close", -right * 1.1 - fwd * 0.2, 0.85],
	]
	for v: Array in views:
		_cam.global_position = at + (v[1] as Vector3) + Vector3.UP * float(v[2])
		_cam.look_at(at + Vector3.UP * float(v[2]), Vector3.UP)
		for i in range(12):
			await get_tree().process_frame
		_me.weapon_id = ""
		_me.set_first_person(false)
		_cam.make_current()
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(out + String(v[0]) + ".png")
		print("SHOT ", v[0])
	# мародёр с пистолетом в руках — автомат за спиной: рядом с игроком на площади, сзади
	var mb_bot: Marauder = null
	for b: Marauder in bots:
		if b.state != Marauder.State.DEAD and b.equipment.has("primary") and b.equipment.has("secondary"):
			mb_bot = b
			break
	if mb_bot:
		mb_bot.global_position = at + right * 2.2
		(mb_bot.get_node("Body") as Node3D).global_rotation.y = body.global_rotation.y
		mb_bot._use("secondary")
		await _settle()
		_cam.global_position = mb_bot.global_position - fwd * 2.4 - right * 0.5 + Vector3.UP * 1.3
		_cam.look_at(mb_bot.global_position + Vector3.UP * 1.2, Vector3.UP)
		_cam.make_current()
		for i in range(12):
			await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(out + "slung_marauder.png")
		print("SHOT slung_marauder")


## Сверка вида у игрока — раз в Balance.SLUNG.every; с запасом.
func _settle() -> void:
	await get_tree().create_timer(float(Balance.SLUNG.every) * 2.0 + 0.1).timeout
	for i in range(3):
		await get_tree().process_frame


func _names(slung: SlungWeapons) -> Array:
	var out: Array = []
	for a: Node in slung.anchors():
		out.append(String(a.name))
	out.sort()
	return out


func _has_prefix(names: PackedStringArray, prefix: String) -> bool:
	for n: String in names:
		if n.begins_with(prefix):
			return true
	return false


## Центр видимой геометрии узла в мире.
func _centre(n: Node3D) -> Vector3:
	var box := AABB()
	var first := true
	for mi: Node in n.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.mesh == null or m.name == "Holster":
			continue
		var b: AABB = m.global_transform * m.get_aabb()
		box = b if first else box.merge(b)
		first = false
	return box.get_center()


## Насколько далеко назад от позвонка заходит рюкзак: углы его сетки в позе покоя переносятся вместе с позвонком
## Spine2 в нынешнюю позу (рюкзак на нём и висит).
func _farthest_back(sk: Skeleton3D, anim: CharacterAnimator, fwd: Vector3, spine: Vector3) -> float:
	var bone := sk.find_bone("mixamorig_Spine2")
	var follow: Transform3D = anim.bone_node("mixamorig_Spine2").global_transform * (sk.global_transform * sk.get_bone_global_rest(bone)).affine_inverse()
	var far := 0.0
	for c: Node in sk.get_children():
		var mi := c as MeshInstance3D
		if mi == null or not String(mi.name).begins_with("G_Raid") or "_LOD" in String(mi.name):
			continue
		var b: AABB = mi.get_aabb()
		for i in range(8):
			var pt: Vector3 = follow * (sk.global_transform * b.get_endpoint(i))
			far = maxf(far, -(pt - spine).dot(fwd))
	return far


func _skel(n: Node) -> Skeleton3D:
	return n.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("slung_test: %s · %s%s" % ["PASS" if ok else "FAIL", label, (" — " + detail) if detail != "" and not ok else ""])
