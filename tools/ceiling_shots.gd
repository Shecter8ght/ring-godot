extends Node
## Потолки и купол: от первого лица вверх (галерея, атриум) и та же точка в изометрии.
## godot --path . res://tools/ceiling_shots.tscn → docs/screens/ceil_*.png

func _ready() -> void:
	await get_tree().process_frame
	var inst: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	while inst.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in inst.get_node("Marauders").get_children():
		m.queue_free()
	var me := get_tree().get_first_node_in_group("players") as Player
	me.health.hp = 1e9
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	for spot in [["gallery", SectorBuilder.polar(-100.0, 35.0), -60.0], ["atrium", SectorBuilder.polar(-90.0, 12.0), -90.0], ["shop", SectorBuilder.polar(-104.0, 94.0), 30.0]]:
		me.global_position = (spot[1] as Vector3) + Vector3(0, 0.1, 0)
		CameraRig.first_person_mode = false
		await _frames(40)
		_save("ceil_%s_iso" % spot[0])
		CameraRig.first_person_mode = true
		await _frames(10)
		rig._look_pitch = 0.75
		rig._look_yaw = deg_to_rad(float(spot[2]))
		await _frames(40)
		_save("ceil_%s_fps" % spot[0])
	CameraRig.first_person_mode = false
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("ceiling_shots: ", n)
