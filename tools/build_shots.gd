extends Node3D
## Снимки сборок деревом (WeaponBuild): ВЕРАС с кронштейнами, проставкой и устройствами по пазам.
## tools/godot.cmd --windowed --resolution 1280x720 res://tools/build_shots.tscn → docs/screens/build_*.png

const BUILDS := {
	"offset_right": {"optic_primary": {"id": "optic_lpvo_01", "slot": 1}, "optic_primary#2": {"id": "mount_offset45_01", "slot": 7},
		"optic_primary#2/rail": {"id": "optic_holo_01"}, "underbarrel": {"id": "grip_vertical_01", "slot": 3}},
	"offset_left": {"optic_primary": {"id": "optic_lpvo_01", "slot": 1}, "optic_primary#2": {"id": "mount_offset45_01", "slot": 7, "flip": true},
		"optic_primary#2/rail": {"id": "optic_holo_01"}, "side_right": {"id": "tac_flashlight_01"}},
	"riser": {"optic_primary": {"id": "mount_riser_01", "slot": 2}, "optic_primary/rail": {"id": "optic_4x_01"},
		"top_front": {"id": "optic_holo_01", "slot": 0}, "underbarrel": {"id": "grip_offset_01", "slot": 0}},
	"adjustable": {"optic_primary": {"id": "optic_rd_01", "slot": 2}, "optic_primary#2": {"id": "mount_adjustable_01", "slot": 7, "angle": 30.0},
		"optic_primary#2/rail": {"id": "optic_holo_01"}, "underbarrel": {"id": "grip_vertical_01", "slot": 0}, "underbarrel#2": {"id": "tac_combo_01", "slot": 4}},
}

var _cam: Camera3D


func _ready() -> void:
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.16, 0.17, 0.19)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.5, 0.52, 0.56)
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-40, -30, 0)
	key.light_energy = 2.2
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-15, 150, 0)
	rim.light_energy = 1.2
	add_child(rim)
	_cam = Camera3D.new()
	_cam.fov = 30.0
	_cam.near = 0.01
	add_child(_cam)
	_cam.current = true
	for name: String in BUILDS:
		var entry: Dictionary = {"id": "wpn_ar_01", "mods": BUILDS[name]}
		for k: Variant in entry.mods:
			var why: String = WeaponBuild.block(entry, String(k), String(entry.mods[k].id))
			if why != "":
				print("BUILD %s %s: %s" % [name, k, why])
		var model: Node3D = WeaponModels.build("wpn_ar_01", BUILDS[name], 0, 100.0)
		add_child(model)
		for view: Array in [["side", Vector3(-0.95, 0.12, 0.22), Vector3(0, 0.08, 0.22)], ["rear", Vector3(-0.32, 0.32, -0.42), Vector3(0, 0.1, 0.18)]]:
			_cam.position = view[1]
			_cam.look_at(view[2])
			await _frames(4)
			await RenderingServer.frame_post_draw
			get_viewport().get_texture().get_image().save_png("res://docs/screens/build_%s_%s.png" % [name, view[0]])
		model.queue_free()
		await _frames(2)
	get_tree().quit()


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
