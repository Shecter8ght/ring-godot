class_name ItemIcons
extends RefCounted
## Иконки предметов: assets/icons/<id>.png (печёт tools/icon_bake из ItemModels). Нет файла —
## null: окна рисуют цветную плашку по категории (игра обязана работать без assets/).

const DIR := "res://assets/icons/%s.png"

static var _cache: Dictionary = {}


static func get_icon(id: String) -> Texture2D:
	if _cache.has(id):
		return _cache[id]
	var path := DIR % id
	var tex: Texture2D = load(path) if ResourceLoader.exists(path) else null
	_cache[id] = tex
	return tex


## Иконка конкретного экземпляра: снимок фактической сборки (ItemThumbs — обвес, магазин), пока его
## нет или он не нужен — обычная иконка предмета. canvas перерисуется, когда снимок будет готов.
static func entry_icon(entry: Dictionary, canvas: CanvasItem = null) -> Texture2D:
	var thumb: Texture2D = ItemThumbs.texture(entry, canvas)
	return thumb if thumb else get_icon(String(entry.get("id", "")))


## Как draw, но для записи предмета: у оружия — его сборка.
static func draw_entry(canvas: CanvasItem, entry: Dictionary, rect: Rect2, rotated: bool) -> bool:
	return _draw_tex(canvas, entry_icon(entry, canvas), rect, rotated)


## Подложка под иконку: цвет категории, разбавленный серым — воронёный металл на ней читается.
static func backdrop(cat_color: Color) -> Color:
	return cat_color.lerp(Color(0.52, 0.53, 0.55), 0.35)


## Нарисовать иконку в прямоугольник rect элемента canvas, сохранив пропорции; rotated — предмет
## лежит повёрнутым (иконка снята в неповёрнутом виде — поворачиваем на 90°).
static func draw(canvas: CanvasItem, id: String, rect: Rect2, rotated: bool) -> bool:
	return _draw_tex(canvas, get_icon(id), rect, rotated)


static func _draw_tex(canvas: CanvasItem, tex: Texture2D, rect: Rect2, rotated: bool) -> bool:
	if tex == null:
		return false
	var box := Vector2(rect.size.y, rect.size.x) if rotated else rect.size
	var ts := Vector2(tex.get_size())
	var k := minf(box.x / ts.x, box.y / ts.y)
	var sz := ts * k
	if rotated:
		canvas.draw_set_transform(rect.get_center(), PI * 0.5, Vector2.ONE)
		canvas.draw_texture_rect(tex, Rect2(-sz * 0.5, sz), false)
		canvas.draw_set_transform_matrix(Transform2D.IDENTITY)
	else:
		canvas.draw_texture_rect(tex, Rect2(rect.get_center() - sz * 0.5, sz), false)
	return true
