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


## Подложка под иконку: цвет категории, разбавленный серым — воронёный металл на ней читается.
static func backdrop(cat_color: Color) -> Color:
	return cat_color.lerp(Color(0.52, 0.53, 0.55), 0.35)


## Нарисовать иконку в прямоугольник rect элемента canvas, сохранив пропорции; rotated — предмет
## лежит повёрнутым (иконка снята в неповёрнутом виде — поворачиваем на 90°).
static func draw(canvas: CanvasItem, id: String, rect: Rect2, rotated: bool) -> bool:
	var tex := get_icon(id)
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
