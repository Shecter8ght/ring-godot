extends Node
## Перепечь навигацию карты ТЦ (scenes/levels/mall_map.tscn) после правки территории — без запуска рейда:
##   tools/godot.cmd --headless res://tools/bake_mall_nav.tscn
## Кэш — data/navigation/mall_map (тайлы и manifest.json с хэшами источников, UrbanNavigation.SOURCES).


func _ready() -> void:
	await get_tree().process_frame
	var level: Node3D = (load("res://scenes/levels/mall_map.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var navigation := UrbanNavigation.new()
	navigation.definition = SectorBuilder.load_def("res://data/sectors/mall_map.json")
	navigation.save_cache = true
	navigation.ready_for_agents.connect(func() -> void:
		print("mall_map: кэш навигации сохранён")
		get_tree().quit())
	level.get_node("Navigation").add_child(navigation)
