extends Control
## Миниатюры экземпляров (ItemThumbs) в настоящей сетке рюкзака: два ВЕРАСа с разными сборками,
## вынутый магазин, магазин на 60, пустой штатный (виден — патронов нет, а магазин есть).
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/thumb_shots.tscn → docs/screens/thumb_*.png

func _veras(mods: Dictionary, mag: Dictionary) -> Dictionary:
	return {"id": "wpn_ar_01", "n": 1, "dur": 100.0, "mods": mods, "mag": mag, "sight": "primary"}


func _ready() -> void:
	var full: Dictionary = {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}
	var entries: Array = [
		_veras({"optic_primary": {"id": "optic_lpvo_01", "slot": 1}, "optic_primary#2": {"id": "mount_offset45_01", "slot": 7},
			"optic_primary#2/rail": {"id": "optic_holo_01"}, "underbarrel": {"id": "grip_vertical_01", "slot": 3}, "muzzle": {"id": "muzzle_supp_545_01"}}, full),
		_veras({"optic_primary": {"id": "optic_rd_01", "slot": 3}, "side_right": {"id": "tac_flashlight_01"}}, {"id": "", "ammo": "", "rounds": 0}),
		_veras({"optic_primary": {"id": "mount_riser_01", "slot": 2}, "optic_primary/rail": {"id": "optic_4x_01"}}, {"id": "mag_545_60", "ammo": "ammo_545_std", "rounds": 60}),
		_veras({}, {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 0}),
	]
	var bg := ColorRect.new()
	bg.color = Color(0.09, 0.085, 0.08)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var grid := GridView.new(Vector2i(8, 4))
	grid.position = Vector2(40, 40)
	add_child(grid)
	var list: Array = []
	for i in range(entries.size()):
		var e: Dictionary = entries[i]
		e["x"] = (i % 2) * 4
		e["y"] = (i / 2) * 2
		list.append(e)
	grid.set_items(list)
	# снимки: ждём, пока все четыре готовы
	for t in range(240):
		var ready := 0
		for e: Dictionary in entries:
			ready += 1 if ItemThumbs.texture(e, grid) != null else 0
		if ready == entries.size():
			break
		await get_tree().process_frame
	for i in range(entries.size()):
		var tex: Texture2D = ItemThumbs.texture(entries[i])
		print("THUMB %d %s" % [i, "есть" if tex else "нет"])
		if tex:
			tex.get_image().save_png("res://docs/screens/thumb_%d.png" % i)
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/thumb_grid.png")
	get_tree().quit()
