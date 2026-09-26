extends Node
## Загружает все скрипты src/ и tools/ — печатает, какие не компилируются.
## godot --headless res://tools/compile_check.tscn

func _ready() -> void:
	var bad := 0
	for dir in ["res://src", "res://tools"]:
		bad += _walk(dir)
	print("compile_check: не собралось %d" % bad)
	get_tree().quit(bad)


func _walk(path: String) -> int:
	var bad := 0
	var d := DirAccess.open(path)
	if d == null:
		return 0
	for f in d.get_files():
		if f.ends_with(".gd") and f != "compile_check.gd":
			var s := load(path + "/" + f) as GDScript
			if s == null or not s.can_instantiate():
				print("  НЕ СОБРАЛСЯ: ", path + "/" + f)
				bad += 1
	for sub in d.get_directories():
		# скрипты импорта (EditorScenePostImport) есть только в редакторе
		if path + "/" + sub == "res://tools/editor":
			continue
		bad += _walk(path + "/" + sub)
	return bad
