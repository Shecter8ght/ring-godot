extends Node
## Перепечь навигацию карты «Проспект» (scenes/levels/prospekt.tscn) после правки блокаута — без запуска рейда:
##   tools/godot.cmd --headless res://tools/bake_prospekt_nav.tscn
## Кэш — data/navigation/prospekt (тайлы и manifest.json с хэшами источников, UrbanNavigation.SOURCES).


func _ready() -> void:
	await get_tree().process_frame
	var level: Node3D = (load("res://scenes/levels/prospekt.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var navigation := UrbanNavigation.new()
	navigation.definition = SectorBuilder.load_def("res://data/sectors/prospekt.json")
	navigation.save_cache = true
	navigation.ready_for_agents.connect(func() -> void:
		print("prospekt: кэш навигации сохранён")
		get_tree().quit())
	level.get_node("Navigation").add_child(navigation)
