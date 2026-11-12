extends Control
## Подробные значки (Balance.ICON_DETAIL — пистолет АСТЕН-919 и его обойма) в настоящих виджетах игры при 1920 × 1080:
## сетка рюкзака / тайника (GridView: предмет лежит, повёрнут, со сборкой — снимок ItemThumbs), слот снаряжения
## (SlotView), карточки витрины торговца (ItemCard.IconBox со студийным фоном, кадры списка, карточки и витрины),
## строка конструктора. Рядом для сравнения — обычные значки (ПМ и его обойма).
## tools/godot.cmd --windowed --resolution 1920x1080 res://tools/icon_detail_shots.tscn
## → docs/screens/icon_detail.png и icon_detail_zoom.png (сетка и слот, увеличено втрое без сглаживания);
## печатает размеры пересчитанных значков: ICON_DETAIL <где> <точек на экране>.

const OUT := "res://docs/screens/icon_detail%s.png"
const GUN := "wpn_hg_02"
const MAG := "mag_919_17"


func _gun(mods: Dictionary = {}, mag: Dictionary = {"id": MAG, "ammo": "ammo_919_std", "rounds": 17}) -> Dictionary:
	return {"id": GUN, "n": 1, "dur": 100.0, "mods": mods, "mag": mag}


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.09, 0.085, 0.08)
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(bg)
	# рюкзак / тайник
	var grid := GridView.new(Vector2i(10, 5))
	grid.position = Vector2(40, 40)
	add_child(grid)
	var supp: Dictionary = _gun({"muzzle": {"id": "muzzle_supp_9_01"}})
	var items: Array = [
		_gun().merged({"x": 0, "y": 0}),
		supp.merged({"x": 2, "y": 0}),
		_gun({}, {"id": "", "ammo": "", "rounds": 0}).merged({"x": 4, "y": 0}),
		_gun().merged({"x": 6, "y": 0, "r": true}),
		{"id": MAG, "n": 1, "x": 0, "y": 1, "ammo": "ammo_919_std", "rounds": 17},
		{"id": MAG, "n": 1, "x": 1, "y": 1, "ammo": "ammo_919_std", "rounds": 0},
		{"id": MAG, "n": 1, "x": 2, "y": 1},
		{"id": "wpn_hg_01", "n": 1, "dur": 100.0, "x": 0, "y": 3},
		{"id": "mag_918_8", "n": 1, "x": 2, "y": 3},
	]
	grid.set_items(items)
	# слот снаряжения
	var slot := SlotView.new("sidearm")
	slot.position = Vector2(560, 40)
	slot.size = slot.custom_minimum_size
	add_child(slot)
	slot.set_entry(_gun())
	# карточки торговца и строка конструктора
	var cards: Array[ItemCard.IconBox] = []
	var at := Vector2(40, 300)
	for spec: Array in [[GUN, Vector2i(320, 145), Vector2(132, 60)], [MAG, Vector2i(320, 145), Vector2(132, 60)],
			[GUN, Vector2i(480, 200), Vector2(240, 100)], [MAG, Vector2i(480, 200), Vector2(240, 100)],
			[GUN, Vector2i(640, 268), Vector2(640, 268)], [MAG, Vector2i(640, 268), Vector2(640, 268)]]:
		var box := ItemCard.IconBox.new()
		box.id = String(spec[0])
		box.entry = _gun() if box.id == GUN else {"id": MAG, "n": 1}
		box.studio = true
		box.frame = spec[1] as Vector2i
		box.position = at
		box.size = spec[2] as Vector2
		add_child(box)
		cards.append(box)
		at.x += box.size.x + 16.0
		if at.x > 1200.0:
			at = Vector2(40, at.y + box.size.y + 16.0)
	for id: String in [GUN, MAG]:
		var small := ItemCard.IconBox.new()
		small.id = id
		small.position = Vector2(820 + (0 if id == GUN else 70), 40)
		small.size = Vector2(52, 36)
		add_child(small)
	# ждём снимки сборок и карточек
	for t: int in range(600):
		var ready: bool = ItemThumbs.texture(supp, grid) != null
		for box: ItemCard.IconBox in cards:
			ready = ready and ItemThumbs.card_texture(box.entry, box.frame, box) != null
		if ready:
			break
		await get_tree().process_frame
	for i: int in range(4):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	_report("значок пистолета", ItemIcons.get_icon(GUN), Vector2(2, 1) * GridView.CELL - Vector2(6, 6))
	_report("значок обоймы", ItemIcons.get_icon(MAG), Vector2(1, 1) * GridView.CELL - Vector2(6, 6))
	_report("сборка с глушителем", ItemThumbs.texture(supp), Vector2(2, 1) * GridView.CELL - Vector2(6, 6))
	var shot: Image = get_viewport().get_texture().get_image()
	shot.save_png(ProjectSettings.globalize_path(OUT % ""))
	var zoom: Image = shot.get_region(Rect2i(30, 30, 880, 250))
	zoom.resize(zoom.get_width() * 3, zoom.get_height() * 3, Image.INTERPOLATE_NEAREST)
	zoom.save_png(ProjectSettings.globalize_path(OUT % "_zoom"))
	print("icon_detail_shots: снимки → docs/screens/icon_detail*.png")
	get_tree().quit(0)


## Мастер и его размер после пересчёта под прямоугольник box (точки экрана).
func _report(what: String, tex: Texture2D, box: Vector2) -> void:
	if tex == null:
		print("ICON_DETAIL %s: нет" % what)
		return
	var ts := Vector2(tex.get_size())
	var px := Vector2i((ts * minf(box.x / ts.x, box.y / ts.y) * ItemIcons.screen_scale(self)).round())
	var fit: Texture2D = ItemIcons.sized(tex, px)
	print("ICON_DETAIL %s: мастер %s, подробный %s, на экране %s" % [what, str(tex.get_size()), str(tex.has_meta(ItemIcons.META_DETAIL)), str(fit.get_size())])
