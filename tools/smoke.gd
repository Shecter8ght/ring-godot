extends Node
## Дымовой прогон: грузит сцену, ждёт N кадров, сохраняет скриншот, выходит.
## Запускается как обычная сцена (чтобы работали autoload): godot --path . res://tools/smoke.tscn -- <сцена> [кадров] [overview|at=a,r]

const OUT_DIR := "res://docs/screens"


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var scene_path := args[0] if args.size() > 0 else String(ProjectSettings.get_setting("application/run/main_scene"))
	var frames := int(args[1]) if args.size() > 1 else 90
	var packed: PackedScene = load(scene_path)
	if packed == null:
		push_error("smoke: сцена не загрузилась: " + scene_path)
		get_tree().quit(2)
		return
	var inst := packed.instantiate()
	await get_tree().process_frame
	get_tree().root.add_child(inst)
	get_tree().current_scene = inst
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	var suffix := ""
	if args.size() > 2 and args[2].begins_with("overview"):
		# Обзорная камера: вид сверху на весь сектор, чтобы проверять планировку.
		# overview:x:z:высота — куда смотреть (по умолчанию — старый сектор f1_market); «=» и «,» режет cmd.
		suffix = "_overview"
		var ov := [70.0, 0.0, 190.0]
		if args[2].begins_with("overview:"):
			var p := args[2].trim_prefix("overview:").split(":")
			ov = [float(p[0]), float(p[1]), float(p[2])]
			suffix = "_overview_%d_%d" % [int(ov[0]), int(ov[1])]
		await get_tree().process_frame
		var cam := Camera3D.new()
		cam.fov = 45.0
		cam.far = 1000.0
		get_tree().root.add_child(cam)
		var center := Vector3(float(ov[0]), 0, float(ov[1]))
		cam.position = center + Vector3(-float(ov[2]) * 0.2, float(ov[2]), 0)
		cam.look_at(center, Vector3(1, 0, 0))
		cam.current = true
	elif args.size() > 2 and (args[2].begins_with("at=") or args[2].begins_with("at:")):
		# Поставить игрока в полярную точку сектора: at:угол:радиус[:высота[:курс камеры]] —
		# снимок «глазами» камеры игрока (через cmd — только двоеточия).
		var parts := args[2].substr(3).replace(",", ":").split(":")
		suffix = "_at_%s_%s" % [parts[0], parts[1]]
		await get_tree().process_frame
		var player := get_tree().get_first_node_in_group("players") as Node3D
		if player:
			var y := float(parts[2]) if parts.size() > 2 else 0.0
			player.global_position = SectorBuilder.polar(float(parts[0]), float(parts[1])) + Vector3(0, y + 0.05, 0)
		if parts.size() > 3:
			var rig := get_tree().get_first_node_in_group("camera_rig") as Node3D
			if rig:
				rig.rotation.y = -deg_to_rad(float(parts[3]))
	_run(scene_path, frames, suffix)


func _run(scene_path: String, frames: int, suffix: String) -> void:
	for i in range(frames):
		await get_tree().process_frame
	var img := get_viewport().get_texture().get_image()
	var file_name := scene_path.get_file().get_basename() + suffix + ".png"
	var out := ProjectSettings.globalize_path(OUT_DIR + "/" + file_name)
	var err := img.save_png(out)
	print("smoke: %s -> %s (%s)" % [scene_path, out, error_string(err)])
	get_tree().quit(0 if err == OK else 1)
