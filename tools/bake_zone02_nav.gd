extends Node
## Перепечь навигацию после ручного изменения городской планировки, без запуска рейда.


func _ready() -> void:
	await get_tree().process_frame
	var level: Node3D = (load("res://scenes/levels/zone02_urban_belt.tscn") as PackedScene).instantiate() as Node3D
	level.set_script(null)
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var navigation := UrbanNavigation.new()
	navigation.definition = SectorBuilder.load_def("res://data/sectors/zone02_urban_belt.json")
	navigation.save_cache = true
	navigation.ready_for_agents.connect(func() -> void:
		print("zone02: кэш навигации сохранён")
		get_tree().quit())
	level.get_node("Navigation").add_child(navigation)
