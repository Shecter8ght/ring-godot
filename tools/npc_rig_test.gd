extends Node3D
## Мародёр v03 на скелете mixamorig_* (tools/npc_kit/game_rig.py) против Persona: те же 52 кости и rest-ориентации,
## те же клипы дают ту же позу, ступни на полу при другом росте (BodyMotion: высота таза под рост), лёжа — у земли.
## Headless — проверки; с окном (--windowed --resolution 1600x900) — снимки docs/screens/npc_rig_*.png
## (Persona слева, мародёр справа: прицел, взгляд вверх, выглядывание, перезарядка, присед с огнём, лёжа, ходьба).

const NPC := "res://assets/models/characters/npc_marauder/npc_marauder.gltf"
const PERSONA := AnimPuppet.PERSONA_MODEL
## Кости для сравнения поз: без левой руки (её ставит ИК на цевьё по длине своей руки) и без головы (взгляд
## и дыхание живости включаются у фигур с разной задержкой по дальности).
const COMPARE := ["mixamorig_Hips", "mixamorig_Spine", "mixamorig_Spine2", "mixamorig_RightArm",
	"mixamorig_RightForeArm", "mixamorig_RightUpLeg", "mixamorig_RightLeg", "mixamorig_LeftUpLeg", "mixamorig_LeftLeg"]
## Отрезки программы «shooter», где фигура стоит на ногах (ступни у пола).
const STANDING_SEGMENTS := [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

var _fails: int = 0
var _puppets: Dictionary = {}
var _cam: Camera3D


## Снаряжение на мародёре (режим «gear»): броня средняя + шлем средний + рейдовый рюкзак + подсумки;
## пояс + простой шлем + городской рюкзак + пистолетные подсумки. Проверка: всё надевается, снимки npc_gear_*.
const GEAR_SETS := {
	"shooter": {"skinned": [["armor_mid", "G_Armor_Mid"], ["helmets", "G_Helmet_Mid"], ["raid", "G_Raid_Mid"]],
		"pouches": [["mid", 1, "G_Pouch_Rifle"], ["mid", 2, "G_Pouch_Rifle"], ["mid", 3, "G_Pouch_Rifle"], ["mid", 4, "G_Pouch_Pistol"], ["mid", 5, "G_Pouch_Rifle"]]},
	"circle": {"skinned": [["belt", "G_Armor_Belt"], ["helmets", "G_Helmet_Simple"], ["daypack", "G_Daypack"]],
		"pouches": [["belt", 1, "G_Pouch_Pistol"], ["belt", 2, "G_Pouch_Rifle"]]},
}


func _ready() -> void:
	_build_world()
	await get_tree().process_frame
	if "gear" in OS.get_cmdline_user_args():
		_gear()
		return
	_check_skeleton()
	for prog: String in ["shooter", "circle"]:
		for who: String in ["persona", "npc"]:
			var p := AnimPuppet.new()
			p.program = prog
			p.model = PERSONA if who == "persona" else NPC
			p.name = "%s_%s" % [prog, who]
			var x: float = -0.9 if who == "persona" else 0.9
			p.position = Vector3(x, 0.0, 0.0 if prog == "shooter" else 4.0)
			p.rotation.y = PI
			add_child(p)
			_puppets[p.name] = p
	_cam = Camera3D.new()
	_cam.fov = 45.0
	add_child(_cam)
	_cam.current = true
	_aim_camera(Vector3(0.0, 1.0, 0.0), 5.0, 0.35, -0.12)
	await get_tree().process_frame
	await get_tree().process_frame
	var npc: AnimPuppet = _puppets["shooter_npc"]
	var k: float = npc.animator()._hips_height.scale_factor()
	var k_persona: float = (_puppets["shooter_persona"] as AnimPuppet).animator()._hips_height.scale_factor()
	_check("HipsHeight: высота таза под рост мародёра, у Persona ×1", k > 1.05 and k < 1.15 and absf(k_persona - 1.0) < 0.01, "множители %.3f / %.3f" % [k, k_persona])
	if "shots" in OS.get_cmdline_user_args():
		_shots()
	else:
		_verify()


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s%s" % ["ok" if ok else "FAIL", what, "" if detail == "" else " — " + detail])


func _skeleton_of(node: Node) -> Skeleton3D:
	var found: Array[Node] = node.find_children("*", "Skeleton3D", true, false)
	return found[0] as Skeleton3D if not found.is_empty() else null


## Скелет модели: 52 кости с именами Persona, rest-ориентации те же (клипы — повороты относительно rest).
func _check_skeleton() -> void:
	var npc: Node3D = (load(NPC) as PackedScene).instantiate() as Node3D
	var persona: Node3D = (load(PERSONA) as PackedScene).instantiate() as Node3D
	add_child(npc)
	add_child(persona)
	var sn := _skeleton_of(npc)
	var sp := _skeleton_of(persona)
	_check("мародёр: есть скелет", sn != null)
	if sn == null or sp == null:
		return
	var names: PackedStringArray = []
	for i in range(sn.get_bone_count()):
		names.append(sn.get_bone_name(i))
	var missing: PackedStringArray = []
	for i in range(sp.get_bone_count()):
		if not names.has(sp.get_bone_name(i)):
			missing.append(sp.get_bone_name(i))
	_check("52 кости, имена как у Persona", sn.get_bone_count() == 52 and missing.is_empty(), "костей %d, нет: %s" % [sn.get_bone_count(), ", ".join(missing)])
	var worst: float = 0.0
	var worst_name: String = ""
	for i in range(sp.get_bone_count()):
		var j: int = sn.find_bone(sp.get_bone_name(i))
		if j < 0:
			continue
		var a: Quaternion = sp.get_bone_global_rest(i).basis.get_rotation_quaternion()
		var b: Quaternion = sn.get_bone_global_rest(j).basis.get_rotation_quaternion()
		var d: float = rad_to_deg(a.angle_to(b))
		if d > worst:
			worst = d
			worst_name = sp.get_bone_name(i)
	_check("rest-ориентации костей как у Persona", worst < 0.5, "наибольшее расхождение %.2f° (%s)" % [worst, worst_name])
	var hips_n: float = sn.get_bone_global_rest(sn.find_bone("mixamorig_Hips")).origin.length()
	var hips_p: float = sp.get_bone_global_rest(sp.find_bone("mixamorig_Hips")).origin.length()
	_check("таз мародёра выше таза Persona (другой рост)", hips_n / hips_p > 1.02, "%.3f / %.3f" % [hips_n, hips_p])
	var meshes: int = npc.find_children("*", "MeshInstance3D", true, false).size()
	_check("сетки модели со скином", meshes >= 8, "%d MeshInstance3D" % meshes)
	npc.queue_free()
	persona.queue_free()


## Позы костей снимаются внутри сигнала modification_processed: после модификаторов скелет возвращает позы
## к исходным (результат идёт только в скин), снаружи get_bone_global_pose поправок не видит.
var _measured: Dictionary = {}


func _measure(p: AnimPuppet) -> Dictionary:
	var sk := _skeleton_of(p.get_node("Body/Persona"))
	var bones: Dictionary = {}
	for bone: String in COMPARE:
		bones[bone] = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bone))).basis.get_rotation_quaternion()
	var l: float = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("mixamorig_LeftFoot"))).origin.y
	var r: float = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("mixamorig_RightFoot"))).origin.y
	var hips: float = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("mixamorig_Hips"))).origin.y
	return {"bones": bones, "foot": minf(l, r), "hips": hips}


func _hook(p: AnimPuppet) -> void:
	var hh: HipsHeight = p.animator()._hips_height
	hh.modification_processed.connect(func() -> void: _measured[p.name] = _measure(p))


func _verify() -> void:
	var per: AnimPuppet = _puppets["shooter_persona"]
	var npc: AnimPuppet = _puppets["shooter_npc"]
	for n: String in _puppets:
		_hook(_puppets[n])
	var pose_worst: float = 0.0
	var pose_bone: String = ""
	var foot_diff_max: float = 0.0
	var foot_low_npc: float = 10.0
	var foot_low_per: float = 10.0
	var walk_foot_npc: float = 10.0
	var walk_foot_per: float = 10.0
	var prone_hips: float = 10.0
	var samples: int = 0
	while per.clock < 25.0:
		await get_tree().physics_frame
		if per.clock < 0.5 or _measured.size() < 4:
			continue
		samples += 1
		var mp: Dictionary = _measured["shooter_persona"]
		var mn: Dictionary = _measured["shooter_npc"]
		if samples == 120:
			print("  таз в мире, м: мародёр %.3f, Persona %.3f; нижняя лодыжка %.3f / %.3f" % [mn.hips, mp.hips, mn.foot, mp.foot])
		for bone: String in COMPARE:
			var d: float = rad_to_deg((mp.bones[bone] as Quaternion).angle_to(mn.bones[bone] as Quaternion))
			if d > pose_worst:
				pose_worst = d
				pose_bone = bone
		if npc._segment in STANDING_SEGMENTS:
			foot_diff_max = maxf(foot_diff_max, absf(float(mn.foot) - float(mp.foot)))
			foot_low_npc = minf(foot_low_npc, float(mn.foot))
			foot_low_per = minf(foot_low_per, float(mp.foot))
		if npc._segment == 12:
			prone_hips = minf(prone_hips, float(mn.hips))
		walk_foot_npc = minf(walk_foot_npc, float((_measured["circle_npc"] as Dictionary).foot))
		walk_foot_per = minf(walk_foot_per, float((_measured["circle_persona"] as Dictionary).foot))
	_check("те же клипы — та же поза у мародёра и Persona (корпус, правая рука, ноги)", pose_worst < 8.0, "наибольшее расхождение %.1f° (%s), замеров %d" % [pose_worst, pose_bone, samples])
	# лодыжка мародёра выше, чем у Persona, на толщину подошвы берца (~5 см): не ниже её и не выше 10 см
	_check("стоя и в приседе: ступни мародёра не в полу и не висят", foot_low_npc > foot_low_per - 0.01 and foot_low_npc < foot_low_per + 0.10, "ниже всего лодыжка: мародёр %.3f, Persona %.3f (разница до %.3f)" % [foot_low_npc, foot_low_per, foot_diff_max])
	_check("на ходу и бегом по кругу: ступни не в полу и не висят", walk_foot_npc > walk_foot_per - 0.01 and walk_foot_npc < walk_foot_per + 0.10, "нижняя лодыжка: мародёр %.3f, Persona %.3f" % [walk_foot_npc, walk_foot_per])
	_check("лёжа — таз у земли", prone_hips < 0.45, "таз %.2f м" % prone_hips)
	print("npc_rig_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _shots() -> void:
	var out := "res://docs/screens/"
	var views: Array = [
		# [имя, время программы, с (по возрастанию), фигуры (0 — оба стрелка, 1 — идущие, 2 — только мародёр), расстояние, курс, наклон, высота цели]
		["aim", 1.0, 0, 4.6, 0.35, -0.1, 1.0],
		["close_front", 1.2, 2, 2.4, 0.15, -0.05, 1.05],
		["close_back", 1.4, 2, 2.4, 2.9, -0.05, 1.05],
		["knees", 1.6, 2, 1.6, 0.3, 0.0, 0.55],
		["pitch_up", 3.6, 0, 4.6, 0.35, -0.1, 1.0],
		["lean", 10.6, 0, 4.6, 0.35, -0.1, 1.0],
		["reload", 13.6, 0, 4.6, 0.6, -0.1, 1.0],
		["walk", 15.0, 1, 5.5, 0.5, -0.2, 1.0],
		["crouch_fire", 21.3, 0, 4.4, 0.5, -0.15, 0.8],
		["prone", 23.8, 0, 6.0, 1.3, -0.55, 0.2],
	]
	var clock: AnimPuppet = _puppets["shooter_persona"]
	for v: Array in views:
		while clock.clock < float(v[1]):
			await get_tree().process_frame
		var row: int = int(v[2])
		var mid: Vector3 = Vector3(0.0, float(v[6]), 0.0)
		if row == 1:
			mid = ((_puppets["circle_persona"] as AnimPuppet).global_position + (_puppets["circle_npc"] as AnimPuppet).global_position) * 0.5 + Vector3(0.0, 1.0, 0.0)
		elif row == 2:
			mid = (_puppets["shooter_npc"] as AnimPuppet).global_position + Vector3(0.0, float(v[6]), 0.0)
		_aim_camera(mid, float(v[3]), float(v[4]), float(v[5]))
		for n: String in _puppets:
			(_puppets[n] as AnimPuppet).animator()._lod_t = 0.0
		for i in range(3):
			await get_tree().process_frame
		var img: Image = get_viewport().get_texture().get_image()
		img.save_png(ProjectSettings.globalize_path(out + "npc_rig_%s.png" % String(v[0])))
		print("SHOT ", v[0])
	get_tree().quit(0)


func _gear() -> void:
	for prog: String in ["shooter", "circle"]:
		var p := AnimPuppet.new()
		p.program = prog
		p.model = NPC
		p.name = "gear_" + prog
		p.position = Vector3(-0.9 if prog == "shooter" else 0.9, 0.0, 0.0)
		p.rotation.y = PI
		add_child(p)
		_puppets[p.name] = p
	_cam = Camera3D.new()
	_cam.fov = 45.0
	add_child(_cam)
	_cam.current = true
	_aim_camera(Vector3(0.0, 1.0, 0.0), 4.6, 0.35, -0.1)
	await get_tree().process_frame
	await get_tree().process_frame
	for prog: String in GEAR_SETS:
		var p: AnimPuppet = _puppets["gear_" + prog]
		var sk := _skeleton_of(p.get_node("Body/Persona"))
		var set: Dictionary = GEAR_SETS[prog]
		for pair: Array in set.skinned:
			var mi := NpcGear.attach_skinned(sk, String(pair[0]), String(pair[1]))
			_check("%s: надета %s" % [prog, pair[1]], mi != null and mi.skin != null and mi.mesh != null, "" if mi else "нет сетки")
		for rec: Array in set.pouches:
			var holder := NpcGear.place(sk, String(rec[0]), int(rec[1]))
			var mi: MeshInstance3D = NpcGear.attach_pouch(holder, String(rec[2])) if holder else null
			_check("%s: подсумок %s в месте %s/%d" % [prog, rec[2], rec[0], rec[1]], mi != null)
			if mi:
				await get_tree().process_frame
				var spine: Vector3 = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("mixamorig_Spine"))).origin
				var hips: Vector3 = (sk.global_transform * sk.get_bone_global_pose(sk.find_bone("mixamorig_Hips"))).origin
				var c: Vector3 = mi.global_transform * mi.mesh.get_aabb().get_center()
				print("    место %s/%d: узел %s, подсумок (центр) %s; таз %s, позвонок %s; вперёд модели %s" % [rec[0], rec[1], holder.global_position, c, hips, spine, p.get_node("Body").global_basis.z])
	await get_tree().process_frame
	if "shots" in OS.get_cmdline_user_args():
		var views: Array = [
			# [имя, время, цель (shooter / circle / mid), расстояние, курс, наклон, высота]
			["pouches", 0.25, "shooter", 1.5, 0.0, -0.05, 1.15],
			["belt_pouches", 0.4, "circle", 1.6, 0.6, -0.1, 0.95],
			["front", 1.0, "mid", 4.6, 0.3, -0.08, 1.0],
			["back", 1.3, "mid", 4.6, 2.9, -0.08, 1.0],
			["side", 1.6, "mid", 4.6, 1.45, -0.08, 1.0],
			["close_chest", 1.9, "shooter", 2.0, 0.25, -0.05, 1.2],
			["close_head", 2.2, "shooter", 1.4, 0.5, 0.1, 1.55],
			["close_pack", 2.5, "shooter", 2.2, 2.8, -0.05, 1.15],
			["belt_close", 2.8, "circle", 2.0, 0.2, -0.1, 1.0],
			["lean", 10.6, "shooter", 3.2, 0.35, -0.1, 1.0],
			["reload", 13.6, "shooter", 3.2, 0.6, -0.1, 1.0],
			["walk", 15.0, "circle", 4.0, 0.5, -0.2, 1.0],
			["crouch_fire", 21.3, "shooter", 3.2, 0.5, -0.15, 0.8],
			["prone", 23.8, "shooter", 5.0, 1.3, -0.55, 0.2],
		]
		var clock: AnimPuppet = _puppets["gear_shooter"]
		for v: Array in views:
			while clock.clock < float(v[1]):
				await get_tree().process_frame
			var who: String = String(v[2])
			var mid: Vector3 = Vector3(0.0, float(v[6]), 0.0)
			if who != "mid":
				mid = (_puppets["gear_" + who] as AnimPuppet).global_position + Vector3(0.0, float(v[6]), 0.0)
			_aim_camera(mid, float(v[3]), float(v[4]), float(v[5]))
			for n: String in _puppets:
				(_puppets[n] as AnimPuppet).animator()._lod_t = 0.0
			for i in range(3):
				await get_tree().process_frame
			get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/npc_gear_%s.png" % String(v[0])))
			print("SHOT ", v[0])
	else:
		# прогон без окна: три секунды анимации с надетым — без ошибок
		while (_puppets["gear_shooter"] as AnimPuppet).clock < 3.0:
			await get_tree().process_frame
	print("npc_rig_test gear: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _aim_camera(target: Vector3, dist: float, yaw: float, pitch: float) -> void:
	var off := Vector3(sin(yaw) * cos(pitch), sin(pitch), cos(yaw) * cos(pitch)) * dist
	_cam.global_position = target - off
	_cam.look_at(target, Vector3.UP)


func _build_world() -> void:
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
