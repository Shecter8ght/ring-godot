extends Node
## Свет по помещениям и через стены: ночью со светом — служебные и торговые помещения от
## первого лица; аварийный — панели горят только у горящих огней; без света — ракета и химсвет
## за перегородкой (не должны светить сквозь стену, в т.ч. в изометрии); засвет от фонаря
## мародёра; ПНВ. godot --path . res://tools/light_tour.tscn → docs/screens/tour_*.png

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	Profile.use_file("user://profile_light_tour.json", true)
	Profile.ensure()
	await get_tree().process_frame
	var only := OS.get_environment("TOUR_ONLY")
	if only == "glare":
		await _load({"time": "night", "weather": "clear", "power": "off"})
		await _glare_part()
		print("light_tour: провалено %d" % _fails)
		get_tree().quit(_fails)
		return
	# ночь, свет есть: помещения
	await _load({"time": "night", "weather": "clear", "power": "on"})
	for r in [["electrical", -23.5, 115.0], ["svc_1", -60.0, 123.0], ["loading_bay", -30.0, 117.0], ["cold", -38.0, 115.0], ["hyper", -45.0, 94.0], ["retail", -104.0, 94.0]]:
		await _fps("tour_room_%s" % r[0], SectorBuilder.polar(float(r[1]), float(r[2])), SectorBuilder.polar(float(r[1]) + 3.0, float(r[2]) + 2.0))
	# аварийный: панель горит только над горящим огнём
	await _load({"time": "night", "weather": "clear", "power": "emergency"})
	var bad := _panels_mismatch()
	_check("аварийный свет: панели как их огни", bad == 0, "не совпало %d" % bad)
	await _fps("tour_emergency", SectorBuilder.polar(-70.0, 94.0), SectorBuilder.polar(-90.0, 94.0))
	# без света: ракета и химсвет за перегородкой прохода и универмага
	await _load({"time": "night", "weather": "clear", "power": "off"})
	var me := Raid.current.local_player()
	for k in ["flare", "chemlight"]:
		var lamp := ThrownLight.throw(_level, k, SectorBuilder.polar(-25.6, 96.0) + Vector3(0, 0.3, 0), Vector3.ZERO)
		await _frames(30)
		await _fps("tour_leak_%s" % k, SectorBuilder.polar(-30.0, 96.0), SectorBuilder.polar(-27.5, 96.0))
		me.global_position = SectorBuilder.polar(-30.0, 96.0) + Vector3(0, 0.1, 0)
		CameraRig.first_person_mode = false
		await _frames(60)
		_save("tour_leak_%s_iso" % k)
		lamp.queue_free()
	await _glare_part()
	print("light_tour: провалено %d" % _fails)
	get_tree().quit(_fails)


func _glare_part() -> void:
	var me := Raid.current.local_player()
	# засвет: мародёр с фонарём светит в лицо, потом в ПНВ
	var m := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "Torchbearer"
	_level.get_node("Marauders").add_child(m)
	# оба на торговой улице — между ними ничего
	var at := SectorBuilder.polar(-104.0, 72.0)
	var mp := SectorBuilder.polar(-98.0, 72.0)
	m.global_position = mp + Vector3(0, 0.1, 0)
	await _frames(5)
	m.process_mode = Node.PROCESS_MODE_DISABLED
	m._body.rotation.y = atan2(at.x - mp.x, at.z - mp.z)
	m._torch.visible = true
	await _fps("tour_glare", at, mp + Vector3(0, 1.4, 0))
	var veil := (get_tree().get_first_node_in_group("camera_rig") as CameraRig)._glare._veil.color.a
	_check("фонарь в лицо — засвет", veil > 0.05, "вуаль %.2f" % veil)
	me.inventory.equipment = {"eyes": ItemDb.make("nvg", 1)}
	me.nvg_on = true
	await _frames(40)
	_save("tour_glare_nvg")
	m._torch.visible = false
	# фонарь на оружии от первого лица — туда же, куда ствол (смотрим вверх)
	me.nvg_on = false
	me.loadout_mode = false
	me.set_sandbox_mods(me.weapon_slot if me.weapon_slot != "" else "AR_03_BASE", {"side_right": "mount_dozor_p", "side_right/light": "tac_flashlight_01"})
	me.light_on = true
	await _fps("tour_flashlight_up", SectorBuilder.polar(-100.0, 72.0), SectorBuilder.polar(-96.0, 72.0) + Vector3(0, 5.0, 0))
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var cam := get_viewport().get_camera_3d()
	var beam: SpotLight3D = null
	for l in rig.find_children("Flashlight", "SpotLight3D", true, false):
		if (l as SpotLight3D).is_visible_in_tree():
			beam = l
	var body_lit := false
	for l in me.find_children("Flashlight", "SpotLight3D", true, false):
		body_lit = body_lit or (l as SpotLight3D).is_visible_in_tree()
	var along := (-beam.global_basis.z).dot(-cam.global_basis.z) if beam else 0.0
	_check("фонарь на оружии: светит от модели в руках, вслед за взглядом вверх", beam != null and not body_lit and along > 0.95, "совпадение %.2f, на теле горит %s" % [along, body_lit])
	me.light_on = false
	me.nvg_on = true
	await _fps("tour_nvg_dark", SectorBuilder.polar(-100.0, 94.0), SectorBuilder.polar(-80.0, 94.0))
	me.nvg_on = false
	CameraRig.first_person_mode = false


func _panels_mismatch() -> int:
	var panels := get_tree().get_first_node_in_group("mall_lamps") as MultiMeshInstance3D
	var bad := 0
	for n in get_tree().get_nodes_in_group("mall_lights"):
		var l := n as Light3D
		if not l.has_meta("lamp"):
			continue
		var c := panels.multimesh.get_instance_color(int(l.get_meta("lamp")))
		if l.visible != (c.r + c.g + c.b > 0.01):
			bad += 1
	return bad


func _load(c: Dictionary) -> void:
	if _level:
		_level.queue_free()
		await get_tree().process_frame
	RaidConditions.from_host = c
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for mm in _level.get_node("Marauders").get_children():
		mm.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	me.health.head_protected = func() -> bool: return true
	await _frames(5)


## От первого лица из точки at, взгляд на look.
func _fps(n: String, at: Vector3, look: Vector3) -> void:
	var me := Raid.current.local_player()
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	me.global_position = at + Vector3(0, 0.1, 0)
	CameraRig.first_person_mode = true
	await _frames(12)
	var eye := me.eye_position()
	var d := look - eye
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length()) if absf(d.y) > 0.5 else -0.05
	await _frames(50)
	_save(n)


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
