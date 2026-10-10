extends Node
## Снимки станка и надписей на реальных моделях; отдельный тестовый профиль.
var fails: int = 0

func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://engraving_shots.json", true)
	Profile.modules["generator"] = 1
	Profile.flags["engraver_installed"] = true
	Profile.stash = []
	for id: String in ["wpn_ar_01", "wpn_hg_01", "wpn_hg_02", "wpn_hg_03", "wpn_ar_03", "wpn_sg_01", "wpn_sr_01"]:
		if not WeaponDb.weapon(id).is_empty():
			ItemDb.add_to(Profile.stash, ItemDb.make(id, 1), Profile.stash_grid())
	ItemDb.add_to(Profile.stash, ItemDb.make("laser_head", 1), Profile.stash_grid())
	Profile.save()
	var hideout: Node = load("res://scenes/levels/hideout.tscn").instantiate()
	get_tree().root.add_child(hideout)
	get_tree().current_scene = hideout
	for frame: int in range(20):
		await get_tree().process_frame
	var camera: Camera3D = Camera3D.new()
	hideout.add_child(camera)
	camera.global_position = Vector3(14.5, 1.65, -1.8)
	camera.look_at(Vector3(15.8, 1.25, -4.25))
	camera.current = true
	await _shot("engraver_workshop")
	var ui: HideoutUI = hideout._ui
	ui.open(HideoutStation.Kind.ENGRAVER)
	for frame: int in range(8):
		await get_tree().process_frame
	var panel: EngraverPanel = ui.find_child("*", true, false) as EngraverPanel
	for node: Node in ui.find_children("*", "EngraverPanel", true, false):
		panel = node as EngraverPanel
	if panel == null:
		for child: Node in ui._cols.get_children():
			if child is EngraverPanel:
				panel = child
	for idx: int in range(panel._weapons.size()):
		panel._weapon.select(idx)
		panel._invalidate()
		panel._text.text = "Михалыч"
		panel._make_preview()
		for frame: int in range(24):
			await get_tree().process_frame
		await _shot("engraving_" + String(panel._weapons[idx].entry.id))
		var stamps: Array[Node] = panel._view.model().find_children("LaserMark", "Decal", true, false)
		if not stamps.is_empty():
			panel._view.focus_mark()
			for frame: int in range(30):
				await get_tree().process_frame
			await _shot("engraving_close_" + String(panel._weapons[idx].entry.id))
		# Обе стороны и каждое место: снимок самого 3D-предпросмотра, без остального окна.
		# Максимальная длина выявляет перекрытия, которые короткое имя не показывает.
		panel._text.text = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧ"
		for site_index: int in range(panel._positions.size()):
			panel._site.select(site_index)
			panel._invalidate()
			panel._make_preview()
			for frame: int in range(18):
				await get_tree().process_frame
			panel._view.focus_mark()
			for frame: int in range(24):
				await get_tree().process_frame
			await RenderingServer.frame_post_draw
			var marks: Array[Node] = panel._view.model().find_children("LaserMark", "Decal", true, false)
			if marks.is_empty():
				push_error("Нет гравировки: %s / %s" % [String(panel._weapons[idx].entry.id), String(panel._positions[site_index].id)])
				fails += 1
			elif String(panel._positions[site_index].part) == "slide":
				var rig: WeaponRig = WeaponRig.find_on(panel._view.model())
				if rig != null and not rig.part("Slide").is_ancestor_of(marks[0]):
					push_error("Гравировка должна следовать затвору")
					fails += 1
			panel._view._vp.get_texture().get_image().save_png("res://docs/screens/engraving_slot_%s_%s.png" % [String(panel._weapons[idx].entry.id), String(panel._positions[site_index].id)])
	print("engraving_shots: failures=%d" % fails)
	get_tree().quit(1 if fails else 0)


func _shot(name: String) -> void:
	for frame: int in range(8):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/%s.png" % name)
	print("SHOT ", name)
