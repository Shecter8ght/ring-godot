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
	if args.size() > 2 and args[2] == "overview":
		# Обзорная камера: вид сверху на весь сектор, чтобы проверять планировку.
		suffix = "_overview"
		await get_tree().process_frame
		var cam := Camera3D.new()
		cam.fov = 45.0
		cam.far = 1000.0
		get_tree().root.add_child(cam)
		var center := Vector3(70, 0, 0)
		cam.position = center + Vector3(-40, 190, 0)
		cam.look_at(center, Vector3(1, 0, 0))
		cam.current = true
	elif args.size() > 2 and args[2].begins_with("at="):
		# Поставить игрока в полярную точку сектора: at=угол,радиус — снимок «глазами» камеры игрока.
		var parts := args[2].trim_prefix("at=").split(",")
		suffix = "_at_%s_%s" % [parts[0], parts[1]]
		await get_tree().process_frame
		var player := get_tree().get_first_node_in_group("players") as Node3D
		if player:
			player.global_position = SectorBuilder.polar(float(parts[0]), float(parts[1])) + Vector3(0, 0.05, 0)
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
