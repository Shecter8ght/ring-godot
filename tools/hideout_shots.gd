extends Node
## Снимки убежища на тестовом профиле: общий вид, окно тайника, торговца, выхода —
## docs/screens/hideout_*.png. godot --path . res://tools/hideout_shots.tscn

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://profile_shots.json", true)
	# немного снаряжения — чтобы окна были не пустыми
	for id in ["w_rifle", "w_pistol", "vest_light"]:
		Profile.equip_from_stash(_idx(id))
	Profile.stash_to_backpack(_idx("ammo_545"), 90)
	Profile.stash_to_backpack(_idx("bandage"), 4)
	get_tree().change_scene_to_file(Balance.HIDEOUT_SCENE)
	await _frames(240)
	_save("hideout")
	var level := get_tree().current_scene
	for kind in [HideoutStation.Kind.STASH, HideoutStation.Kind.TRADER, HideoutStation.Kind.EXIT]:
		for st in get_tree().get_nodes_in_group("interactables"):
			if st is HideoutStation and (st as HideoutStation).kind == kind:
				level.call("open_station", st)
				break
		await _frames(8)
		_save("hideout_ui_%d" % kind)
		(level.get("_ui") as HideoutUI).close_ui()
		await _frames(2)
	get_tree().quit(0)


func _idx(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
