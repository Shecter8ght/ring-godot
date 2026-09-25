extends Node
## Снимки: окно описания предмета (патроны, оружие, плитоносец) и прицел гранаты (G зажата).
## docs/screens/info_*.png, nade_aim.png. godot --path . res://tools/info_shots.tscn

func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var layer := CanvasLayer.new()
	layer.layer = 40
	get_tree().root.add_child(layer)
	var bg := ColorRect.new()
	bg.color = Color(0.1, 0.1, 0.1)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	layer.add_child(bg)
	for id in ["ammo_545_ap", "wpn_ar_01" if ItemDb.exists("wpn_ar_01") else String(WeaponDb.ids("weapons")[8]), "carrier_tactical", "mag_545_30", "optic_offset_rd_01", "bandage"]:
		var w := ItemInfo.open(layer, {"id": id, "n": 1})
		for i in range(4):
			await get_tree().process_frame
		_save("info_" + id)
		print("%s: %s" % [id, ItemInfo.describe(id).replace("\n", " | ").substr(0, 400)])
		w.queue_free()
		await get_tree().process_frame
	layer.queue_free()
	var inst: Node = load(Balance.RAID_SCENE).instantiate()
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	for i in range(40):
		await get_tree().physics_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	pl.health.hp = 1e9
	# наверх, на улицу, и граната к точке в 12 м
	pl.global_position = pl.global_position + Vector3(0, 3.7, 0) + pl.global_basis.z * 0.0
	var ent := get_tree().get_first_node_in_group("ground_holes") as Node3D
	pl.global_position = ent.global_transform * Vector3(0, 0.1, -3.0)
	for i in range(30):
		await get_tree().physics_frame
	# держим G, курсор — на точку в 12 м дальше от лестницы
	var target := ent.global_transform * Vector3(0, 0, -15.0)
	Input.action_press("grenade")
	for i in range(20):
		var cam := get_viewport().get_camera_3d()
		Input.warp_mouse(cam.unproject_position(target))
		await get_tree().physics_frame
	_save("nade_aim")
	Input.action_release("grenade")
	get_tree().quit()


func _save(n: String) -> void:
	if DisplayServer.get_name() != "headless":
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
