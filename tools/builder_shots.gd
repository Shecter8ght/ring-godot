extends Control
## Конструктор оружия (WeaponBuilder) на деле: ВЕРАС с LPVO, в тайнике кронштейн 45°, коллиматор,
## рукоятка; шаги — общий вид, точка выбрана, призрак кронштейна по пазам (можно / занято), прицел
## на кронштейне, вид из глаза, торговец, применено. Снимки docs/screens/builder_*.png.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/builder_shots.tscn

var _b: WeaponBuilder


func _shot(name: String) -> void:
	for i in range(6):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/builder_%s.png" % name)
	print("SHOT ", name)


func _ready() -> void:
	Profile.use_file("user://builder_shots.json", true)
	Profile.money = 60000
	Profile.modules["workbench"] = 2
	Profile.stash.clear()
	for e: Dictionary in [{"id": "mount_offset45_01", "n": 1, "dur": 92.0}, {"id": "optic_rmr_01", "n": 1, "dur": 80.0},
			{"id": "grip_vertical_01", "n": 1, "dur": 100.0}, {"id": "muzzle_supp_545_01", "n": 1, "dur": 70.0}, {"id": "mag_545_60", "n": 1, "rounds": 60, "ammo": "ammo_545_std"}]:
		ItemDb.add_to(Profile.stash, e, Profile.stash_grid())
	Profile.equipment["primary"] = {"id": "wpn_ar_01", "n": 1, "dur": 94.0, "sight": "primary",
		"mods": {"optic_primary": {"id": "optic_lpvo_01", "dur": 96.0, "slot": 1}, "side_right": {"id": "tac_flashlight_01", "dur": 100.0}},
		"mag": {"id": "mag_545_30", "ammo": "ammo_545_std", "rounds": 30}}
	_b = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await get_tree().create_timer(1.2).timeout
	print("SIZES root ", size, " builder ", _b.size, " vp ", get_viewport_rect().size, " view ", _b._view.size)
	await _shot("1_overview")
	_b._select("optic_primary", true)
	await _shot("2_point")
	var bracket: Dictionary = {}
	for p: Dictionary in _b._pool():
		if String(p.id) == "mount_offset45_01":
			bracket = p
	_b._choose(bracket)
	_b._place.slot = 6
	_b._update_place()
	await _shot("3_place_ok")
	_b._place.slot = 2
	_b._update_place()
	await _shot("4_place_bad")
	_b._place.slot = 7
	_b._update_place()
	_b._confirm_place()
	_b._select("optic_primary#2/rail")
	for p2: Dictionary in _b._pool():
		if String(p2.id) == "optic_rmr_01":
			_b._choose(p2)
			break
	await _shot("5_bracket_optic")
	_b._set_view("eye")
	await get_tree().create_timer(0.8).timeout
	await _shot("6_eye")
	_b._set_view("q")
	_b._pick_source("shop")
	_b._pick_tab("fore")
	await _shot("7_shop")
	_b._pick_source("mine")
	_b._pick_tab("all")
	_b._apply()
	var mods: Dictionary = Profile.equipment.primary.mods
	print("APPLIED ", mods.has("optic_primary#2/rail"), " stash ", Profile.stash.size())
	await _shot("8_applied")
	_b._close()
	get_tree().quit()
