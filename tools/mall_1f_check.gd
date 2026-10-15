extends Node
## Серый черновик 1-го этажа ТЦ Ø200 (scenes/levels/mall_1f.tscn, план — docs/design/mall_1f_plan.md):
## куда ИИ доходит по навмешу от главного входа — всё, кроме того, что закрыто по плану; с окном —
## снимки сверху (этаж и навмеш) и от первого лица в docs/screens/mall_1f_*.png.
##   godot --headless res://tools/mall_1f_check.tscn                      — только проверка
##   godot --windowed --resolution 1600x900 res://tools/mall_1f_check.tscn  — проверка и снимки
## MALL_ONLY=top,eye — выборочно (top — сверху, eye — от первого лица); MALL_LEVEL=res://… — другой уровень
## (проверка списков CLOSED и выходов — под ТЦ Ø200).

const LEVEL_DEFAULT := "res://scenes/levels/mall_1f.tscn"
## Куда ИИ не дойти по плану: сгоревшие, завал, «Тайга» под электророллетой, магазины, куда
## пролезают только лёжа (роллета наполовину и второй двери нет).
const CLOSED := ["coffee", "books", "telecom", "stair_n_w", "taiga", "pharmacy", "hardware"]
## Выходы на фасаде (угол плана): изнутри (радиус) наружу (106 м) — коротко, где выход открыт,
## и только в обход через другие выходы, где он заварен или завален.
const EXITS_OPEN := [[270.0, 90.0, "главный вход (пролом)"], [0.0, 92.0, "восточный вход (баррикада)"],
	[45.0, 92.0, "доки"], [180.0, 92.0, "западный пожарный"], [120.0, 92.0, "пожарный 120°"],
	[210.0, 92.0, "пожарный 210°"], [300.0, 92.0, "пожарный 300°"]]
const EXITS_SHUT := [[90.0, 80.0, "северный вход (завал)"], [60.0, 92.0, "заварен 60°"], [150.0, 92.0, "заварен 150°"],
	[240.0, 92.0, "заварен 240°"], [348.0, 92.0, "заварен 348°"]]
## Кадры от первого лица: имя, точка (угол плана, радиус), куда смотреть (угол плана, радиус).
const EYE := [
	["entrance", [270.0, 97.5], [270.0, 40.0]],
	["crossing", [272.0, 61.0], [245.0, 63.0]],
	["atrium", [262.0, 36.0], [80.0, 16.0]],
	["curtain", [138.0, 63.0], [120.0, 63.0]],
	["market", [40.0, 72.0], [20.0, 78.0]],
	["service", [226.0, 97.8], [239.0, 97.8]],
	["half_shutter", [330.0, 63.5], [330.0, 75.0]],
	["north_rubble", [90.0, 74.0], [90.0, 96.0]],
	["east_camp", [0.0, 78.0], [0.0, 104.0]],
]

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_mall_1f_check.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var level: Node3D = load(OS.get_environment("MALL_LEVEL") if OS.get_environment("MALL_LEVEL") != "" else LEVEL_DEFAULT).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0 := Time.get_ticks_msec()
	while not bool(level.get("_nav_baked")):
		if Time.get_ticks_msec() - t0 > 240000:
			print("mall_1f_check: навмеш не испёкся за 4 мин")
			get_tree().quit(1)
			return
		await get_tree().process_frame
	print("mall_1f_check: уровень и навмеш готовы за %.1f с" % ((Time.get_ticks_msec() - t0) / 1000.0))
	# испечённый меш попадает в карту навигации на её синхронизации — дождаться, пока карта ответит
	var map := level.get_world_3d().navigation_map
	var probe := level.call("spawn_pos") as Vector3
	for i in range(600):
		if NavigationServer3D.map_get_closest_point(map, probe).distance_to(probe) < 5.0:
			break
		await get_tree().physics_frame
	_check_reach(level)
	if DisplayServer.get_name() != "headless":
		var only := OS.get_environment("MALL_ONLY")
		# сначала глазами: верхняя камера после себя оставляет текущей не камеру игрока
		if only == "" or "eye" in only:
			await _eye_shots(level)
		if only == "" or "top" in only:
			await _top_shots(level)
	print("mall_1f_check: провалов %d" % _fails)
	get_tree().quit(_fails)


## От главного входа по навмешу — в каждое помещение; закрытые по плану недостижимы.
func _check_reach(level: Node3D) -> void:
	var map := level.get_world_3d().navigation_map
	var rooms: Array = level.get("_rooms")
	var spawn := level.call("spawn_pos") as Vector3
	var from := NavigationServer3D.map_get_closest_point(map, spawn)
	var region := level.get_node_or_null("NavRegion") as NavigationRegion3D
	var polys := region.navigation_mesh.get_polygon_count() if region and region.navigation_mesh else 0
	print("  навмеш: многоугольников %d, вход %s → на навмеше %s" % [polys, spawn, from])
	_check("навмеш испечён", polys > 100, str(polys))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var reached := 0
	var lost: Array[String] = []
	var leaked: Array[String] = []
	for room: Dictionary in rooms:
		if bool(room.get("outdoor", false)):
			continue
		var id := String(room.id)
		# несколько точек: одна может попасть на стеллаж (там навмеша нет)
		var ok := false
		var why := "нет места"
		for attempt in range(6):
			var p := SectorBuilder.random_point(room, rooms, rng, 0.9)
			if p == Vector3.INF:
				continue
			var q := NavigationServer3D.map_get_closest_point(map, p)
			if Vector2(q.x - p.x, q.z - p.z).length() >= 1.2:
				why = "нет навмеша"
				continue
			var path := NavigationServer3D.map_get_path(map, from, q, true)
			if path.size() > 0 and path[path.size() - 1].distance_to(q) < 0.8:
				ok = true
				break
			why = "нет пути"
		if ok:
			reached += 1
			if id in CLOSED:
				leaked.append(id)
		elif not id in CLOSED:
			lost.append("%s (%s)" % [id, why])
	_check("от главного входа дойти во все открытые помещения (%d)" % reached, lost.is_empty(), ", ".join(lost))
	_check("закрытые по плану недоступны ИИ", leaked.is_empty(), ", ".join(leaked))
	for e: Array in EXITS_OPEN:
		var d := _walk(map, float(e[0]), float(e[1]), 108.0)
		_check("выход открыт: %s (%.0f м)" % [e[2], d], d < 25.0)
	for e: Array in EXITS_SHUT:
		var d := _walk(map, float(e[0]), float(e[1]), 108.0)
		_check("выхода нет: %s (в обход %.0f м)" % [e[2], d], d > 35.0)


## Длина пути по навмешу от точки внутри (угол плана, радиус) до точки снаружи на том же луче.
func _walk(map: RID, p_deg: float, r_in: float, r_out: float) -> float:
	var a := NavigationServer3D.map_get_closest_point(map, SectorBuilder.polar(-p_deg, r_in))
	var b := NavigationServer3D.map_get_closest_point(map, SectorBuilder.polar(-p_deg, r_out))
	var path := NavigationServer3D.map_get_path(map, a, b, true)
	if path.size() < 2 or path[path.size() - 1].distance_to(b) > 1.0:
		return INF
	var len := 0.0
	for i in range(path.size() - 1):
		len += path[i].distance_to(path[i + 1])
	return len


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("  %s %s%s" % ["ok  " if ok else "FAIL", what, ("  — " + detail) if detail != "" else ""])


func _clear_ai() -> void:
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	var root := get_tree().current_scene.get_node_or_null("Marauders")
	if root:
		for m in root.get_children():
			m.queue_free()


## Сверху, ортогонально, север вверху: этаж без потолков; второй снимок — с навмешем поверх.
func _top_shots(level: Node3D) -> void:
	_clear_ai()
	# без интерфейса: компас, оружие и подписи закрывают план
	var hidden: Array[CanvasLayer] = []
	for n: Node in get_tree().root.find_children("*", "CanvasLayer", true, false):
		var cl := n as CanvasLayer
		if cl.visible:
			cl.visible = false
			hidden.append(cl)
	var ceilings := level.get_node_or_null("Ceilings") as Node3D
	if ceilings:
		ceilings.visible = false
	var sun := level.get_node_or_null("Sun") as DirectionalLight3D
	var sun_xf := sun.global_transform if sun else Transform3D()
	if sun:
		sun.shadow_enabled = false
		sun.global_transform = Transform3D(Basis.looking_at(Vector3(0.15, -1.0, 0.1)), Vector3(0, 50, 0))
	# как чертёж: стены тёмные (сверху их торцы того же серого, что пол), пропсы видны издалека
	var dark := StandardMaterial3D.new()
	dark.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dark.albedo_color = Color(0.16, 0.15, 0.14)
	var restore: Array = []
	for n: Node in level.find_children("*", "GeometryInstance3D", true, false):
		var gi := n as GeometryInstance3D
		var is_wall := gi.get_parent() != null and String(gi.get_parent().name) == "Walls" and not String(gi.name).ends_with("_shadow")
		if is_wall or gi.visibility_range_end > 0.0:
			restore.append([gi, gi.material_override, gi.visibility_range_end])
			gi.visibility_range_end = 0.0
			if is_wall and String(gi.name) != "glass":
				gi.material_override = dark
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = 212.0
	cam.near = 1.0
	cam.far = 400.0
	cam.cull_mask = 0xFFFFF & ~SectorBuilder.CEILING_LAYER & ~RainOcclusion.LAYER
	level.add_child(cam)
	cam.global_transform = Transform3D(Basis.looking_at(Vector3.DOWN, Vector3.FORWARD), Vector3(0, 120, 0))
	cam.current = true
	await _frames(30)
	_save("mall_1f_top")
	# половины крупнее: на всём круге перегородки тоньше пикселя
	cam.size = 110.0
	for half: Array in [["n", -50.0], ["s", 50.0]]:
		cam.global_position = Vector3(0, 120, float(half[1]))
		await _frames(15)
		_save("mall_1f_top_" + String(half[0]))
	cam.size = 212.0
	cam.global_position = Vector3(0, 120, 0)
	var overlay := _nav_overlay(level)
	await _frames(10)
	_save("mall_1f_nav")
	overlay.queue_free()
	cam.queue_free()
	for r: Array in restore:
		var gi := r[0] as GeometryInstance3D
		gi.material_override = r[1]
		gi.visibility_range_end = float(r[2])
	if ceilings:
		ceilings.visible = true
	for cl in hidden:
		cl.visible = true
	if sun:
		sun.shadow_enabled = true
		sun.global_transform = sun_xf
	await _frames(5)


## Навмеш полупрозрачной заливкой чуть над полом — видно, где ИИ ходит и где нет.
func _nav_overlay(level: Node3D) -> MeshInstance3D:
	var region := level.get_node("NavRegion") as NavigationRegion3D
	var nm := region.navigation_mesh
	var verts := nm.get_vertices()
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in range(nm.get_polygon_count()):
		var poly := nm.get_polygon(i)
		for k in range(1, poly.size() - 1):
			for idx in [poly[0], poly[k], poly[k + 1]]:
				im.surface_add_vertex(verts[idx] + Vector3.UP * 0.3)
	im.surface_end()
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_color = Color(0.0, 0.75, 0.2, 0.6)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	var mi := MeshInstance3D.new()
	mi.mesh = im
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	level.add_child(mi)
	return mi


## От первого лица: игрок в точке, взгляд — на цель (угол камеры: направление (sin, cos) по X, Z).
func _eye_shots(level: Node3D) -> void:
	var me := get_tree().get_first_node_in_group("players") as Player
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	if me == null or rig == null:
		_check("игрок и камера для снимков", false)
		return
	me.health.hp = 1e9
	CameraRig.first_person_mode = true
	for spot: Array in EYE:
		_clear_ai()
		var at: Array = spot[1]
		var to: Array = spot[2]
		var p := SectorBuilder.polar(-float(at[0]), float(at[1]))
		var q := SectorBuilder.polar(-float(to[0]), float(to[1]))
		me.global_position = p + Vector3.UP * 0.1
		me.velocity = Vector3.ZERO
		var d := q - p
		# взгляд держится каждый кадр, мышь не захватывается: настоящая мышь иначе крутит камеру
		for i in range(45):
			rig.set("_look_yaw", atan2(d.x, d.z))
			rig.set("_look_pitch", 0.0)
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			await get_tree().process_frame
		_save("mall_1f_" + String(spot[0]))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	var path := ProjectSettings.globalize_path("res://docs/screens/%s.png" % n)
	get_viewport().get_texture().get_image().save_png(path)
	print("mall_1f_check: снимок ", n)
