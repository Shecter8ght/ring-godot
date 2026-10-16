extends Node3D
## F6 из самой карты тоже запускает прогулку. При вложении в стенд второй игрок не нужен.

func _enter_tree() -> void:
	if get_parent() == get_tree().root:
		Profile.use_file("user://profile_urban_belt_study_test.json",true)

func _ready() -> void:
	if get_parent() != get_tree().root:
		return
	# Используем уже собранную сцену, не загружаем её повторно через стенд.
	var session_script: GDScript = load("res://tools/urban_belt_study.gd") as GDScript
	var session: Node3D = session_script.new() as Node3D
	session.name = "WalkSession"
	session.set("world",self)
	add_child(session)
