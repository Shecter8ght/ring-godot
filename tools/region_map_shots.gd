extends Control
## Схема района (RegionMapView) отдельно от убежища, в размере окна «План рейда»: выбран каждый открытый маршрут по
## очереди, под курсором — участок; снимки docs/screens/region_map_<id>.png. Для подгонки раскладки
## data/region_map.json без загрузки убежища.
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/region_map_shots.tscn

## Место карты в окне 1920 × 1080 (под вкладками «район / план локации»).
const STAGE := Vector2(975, 490)


func _ready() -> void:
	Profile.use_file("user://profile_region_shots.json", true)
	var bg := ColorRect.new()
	bg.color = LightUi.BG
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	var view := RegionMapView.new()
	view.position = Vector2(20, 20)
	view.size = STAGE
	add_child(view)
	for id: String in RegionMapView.data().get("places", {}):
		view.selected = id
		await _frames(6)
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image().get_region(Rect2i(Vector2i(view.position), Vector2i(STAGE)))
		img.save_png(ProjectSettings.globalize_path("res://docs/screens/region_map_%s.png" % id))
		print("region_map_shots: ", id)
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
