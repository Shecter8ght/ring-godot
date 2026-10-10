extends Node
## ПНВ в бою: зелёная картинка не пропадает, когда поверх включаются эффекты стресса и ранения
## (оба читают экран; раньше второй брал кадр до ПНВ и закрашивал зелёный).
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/nvg_stress_test.tscn → docs/screens/nvg_stress_*.png

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	Profile.use_file("user://profile_nvg_stress.json", true)
	Profile.ensure()
	await get_tree().process_frame
	RaidConditions.from_host = {"time": "night", "weather": "clear", "power": "on"}
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	var me: Player = Raid.current.local_player()
	me.health.hp = 1e9
	me.health.max_hp = 1e9
	me.inventory.equipment = {"eyes": ItemDb.make("nvg", 1)}
	CameraRig.first_person_mode = true
	await _frames(20)
	me.nvg_on = true
	await _frames(40)
	_check("ПНВ: картинка зелёная", _green(), "")
	await _save("nvg_stress_0_calm")
	# стресс: тёмные края и тусклые краски поверх ПНВ
	for i in range(40):
		me.stress = 95.0
		await get_tree().process_frame
	_check("ПНВ + стресс: картинка осталась зелёной", _green(), "")
	await _save("nvg_stress_1_stress")
	# попадание: красная виньетка по краям, середина — всё та же зелёная
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	rig._hurt_amount = 0.4
	for i in range(6):
		me.stress = 95.0
		rig._hurt_amount = 0.4
		await get_tree().process_frame
	_check("ПНВ + ранение: середина кадра зелёная", _green(), "")
	await _save("nvg_stress_2_hurt")
	me.nvg_on = false
	me.stress = 0.0
	await _frames(60)
	_check("выключил ПНВ — зелёного нет", not _green(), "")
	print("nvg_stress_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails else 0)


## Середина кадра заметно зеленее, чем красная и синяя.
func _green() -> bool:
	var img: Image = get_viewport().get_texture().get_image()
	var w: int = img.get_width()
	var h: int = img.get_height()
	var sum := Vector3.ZERO
	for y in range(h / 2 - 60, h / 2 + 60, 6):
		for x in range(w / 2 - 160, w / 2 + 160, 6):
			var c: Color = img.get_pixel(x, y)
			sum += Vector3(c.r, c.g, c.b)
	return sum.y > sum.x * 1.35 and sum.y > sum.z * 1.35


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(name: String) -> void:
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/" + name + ".png"))


func _check(label: String, ok: bool, detail: String) -> void:
	if not ok:
		_fails += 1
	print("%s %s %s" % ["[ok]  " if ok else "[FAIL]", label, detail])
