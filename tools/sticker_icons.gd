extends Node
## Иконки наклеек из их рисунков (StickerArt: свой файл assets/stickers/<id>.png или знак кодом) →
## assets/icons/<id>.png; затем tools/godot.cmd --headless --import.
## tools/godot.cmd --headless res://tools/sticker_icons.tscn

const PX := 96


func _ready() -> void:
	for id: String in Balance.STICKERS.ids:
		var art: Image = StickerArt.image(id, 13 if id == String(Balance.STICKERS.tally) else 0)
		var k: float = minf(float(PX - 8) / float(art.get_width()), float(PX - 8) / float(art.get_height()))
		art.resize(int(art.get_width() * k), int(art.get_height() * k), Image.INTERPOLATE_LANCZOS)
		var icon: Image = Image.create(PX, PX, false, Image.FORMAT_RGBA8)
		icon.fill(Color(0, 0, 0, 0))
		icon.blit_rect(art, Rect2i(Vector2i.ZERO, art.get_size()), Vector2i((PX - art.get_width()) / 2, (PX - art.get_height()) / 2))
		icon.save_png(ProjectSettings.globalize_path("res://assets/icons/%s.png" % id))
		print("sticker_icons: ", id)
	get_tree().quit(0)
