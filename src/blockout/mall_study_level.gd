extends Node3D
## F6 прямо из scenes/levels/mall_study.tscn запускает прогулку (tools/mall_study.gd) на уже собранной
## сцене. Основной профиль не трогается — свой тестовый.

func _enter_tree() -> void:
	if get_parent() == get_tree().root:
		Profile.use_file("user://profile_mall_study_test.json", true)


func _ready() -> void:
	if get_parent() != get_tree().root:
		return
	var session_script: GDScript = load("res://tools/mall_study.gd") as GDScript
	var session: Node3D = session_script.new() as Node3D
	session.name = "WalkSession"
	session.set("world", self)
	add_child(session)
