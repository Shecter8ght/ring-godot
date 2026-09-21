extends SceneTree
## Дымовой прогон: грузит сцену, ждёт N кадров, сохраняет скриншот, выходит.
## godot --path . --script res://tools/smoke.gd -- res://scenes/levels/test_range.tscn [frames]

const OUT_DIR := "res://docs/screens"


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var scene_path := args[0] if args.size() > 0 else String(ProjectSettings.get_setting("application/run/main_scene"))
	var frames := int(args[1]) if args.size() > 1 else 90
	var packed: PackedScene = load(scene_path)
	if packed == null:
		push_error("smoke: сцена не загрузилась: " + scene_path)
		quit(2)
		return
	var inst := packed.instantiate()
	root.add_child(inst)
	current_scene = inst
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT_DIR))
	_run(scene_path, frames)


func _run(scene_path: String, frames: int) -> void:
	for i in range(frames):
		await process_frame
	var img := root.get_viewport().get_texture().get_image()
	var file_name := scene_path.get_file().get_basename() + ".png"
	var out := ProjectSettings.globalize_path(OUT_DIR + "/" + file_name)
	var err := img.save_png(out)
	print("smoke: %s -> %s (%s)" % [scene_path, out, error_string(err)])
	quit(0 if err == OK else 1)
