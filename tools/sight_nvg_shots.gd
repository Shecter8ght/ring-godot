extends Node
## Прицелы и ЛЦУ ночью: коллиматор в прицеле без ПНВ и в ПНВ (точка — яркая, не цвета стекла),
## ЛЦУ — точка на стене видна и без ПНВ, луч — только в ПНВ; от первого лица и в изометрии.
## godot --path . res://tools/sight_nvg_shots.tscn → docs/screens/sight_nvg_*.png

const MODS := {"optic_primary": "optic_rd_01", "side_right": "tac_laser_01"}

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	# SHOTS_LOW=1 — качество «низко» (программный рендер без видеокарты иначе не дождаться)
	if OS.get_environment("SHOTS_LOW") == "1":
		Settings.set_quality("low")
	Profile.use_file("user://profile_sight_nvg.json", true)
	Profile.ensure()
	await get_tree().process_frame
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "off"}
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for mm in _level.get_node("Marauders").get_children():
		mm.queue_free()
	var me := Raid.current.local_player()
	me.health.hp = 1e9
	me.inventory.equipment = {"eyes": ItemDb.make("nvg", 1)}
	await _frames(5)
	# первый ствол набора «песочницы» (раньше здесь был зашит пресет, которого в наборе уже нет)
	var key: String = String(me.weapon_keys()[0])
	me.set_sandbox_mods(key, MODS)
	me._switch(key, false)
	await _frames(5)
	me._toggle_tac("laser")
	var at := SectorBuilder.polar(-104.0, 72.0)
	var look := SectorBuilder.polar(-97.0, 67.0) + Vector3(0, 1.2, 0)
	# от первого лица, в прицел
	me.global_position = at + Vector3(0, 0.1, 0)
	CameraRig.first_person_mode = true
	Input.action_press("aim")
	await _frames(12)
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var d := look - me.eye_position()
	rig._look_yaw = atan2(d.x, d.z)
	rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
	await _frames(60)
	var laser := _laser(rig)
	_check("ЛЦУ включён — точка на стене", laser != null and laser.get_node("Dot").visible, "")
	_check("без ПНВ луча не видно", laser != null and not laser.get_node("Beam").visible, "")
	_save("sight_nvg_ads")
	me.nvg_on = true
	await _frames(40)
	_check("в ПНВ луч виден", laser != null and laser.get_node("Beam").visible, "")
	_check("в ПНВ точка прицела — почти белая", WeaponModels._mat("reticle").albedo_color.g > 0.8, str(WeaponModels._mat("reticle").albedo_color))
	_save("sight_nvg_ads_nvg")
	me.nvg_on = false
	Input.action_release("aim")
	CameraRig.first_person_mode = false
	# изометрия: ствол на ту же точку
	me.cursor_ground = look
	me.get_node("Body").rotation.y = atan2(d.x, d.z)
	await _frames(60)
	_save("sight_nvg_iso")
	me.nvg_on = true
	await _frames(40)
	_save("sight_nvg_iso_nvg")
	me.nvg_on = false
	await _frames(5)
	_check("выключил ПНВ — точка прицела снова красная", WeaponModels._mat("reticle").albedo_color.g < 0.3, str(WeaponModels._mat("reticle").albedo_color))
	print("sight_nvg_shots: провалено %d" % _fails)
	get_tree().quit(_fails)


## Лазер модели в руках (от первого лица) или на теле — тот, что сейчас виден.
func _laser(rig: CameraRig) -> LaserSight:
	for n in get_tree().root.find_children("LaserBeam*", "Node3D", true, false):
		if n is LaserSight and (n as LaserSight).is_visible_in_tree():
			return n as LaserSight
	return null


func _save(n: String) -> void:
	if DisplayServer.get_name() == "headless":
		return
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
