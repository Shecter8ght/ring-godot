class_name ItemIcons
extends RefCounted
## Иконки предметов: assets/icons/<id>.png (печёт tools/icon_bake из ItemModels). Нет файла —
## null: окна рисуют цветную плашку по категории (игра обязана работать без assets/).
## Подробные значки (Balance.ICON_DETAIL) — крупный снимок-«мастер» с меткой META_DETAIL: при показе он
## пересчитывается точно под размер на экране (sized) и ложится в целые точки — без ряби и «мыла» от сжатия на лету.

const DIR := "res://assets/icons/%s.png"
## Метка текстуры-мастера: показывать пересчитанной под размер.
const META_DETAIL := &"icon_detail"
## Мастеров в памяти не больше этого: при переполнении выбрасываются записи исчезнувших снимков.
const SIZED_MASTERS := 64

static var _cache: Dictionary = {}
## Пересчитанные значки: номер объекта мастера → {"ref": WeakRef, "img": Image, "by": {Vector2i: ImageTexture}}.
static var _sized: Dictionary = {}


static func get_icon(id: String) -> Texture2D:
	if _cache.has(id):
		return _cache[id]
	var path := DIR % id
	var tex: Texture2D = load(path) if ResourceLoader.exists(path) else null
	if tex and Balance.ICON_DETAIL.has(id):
		tex.set_meta(META_DETAIL, true)
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
## лежит повёрнутым (иконка снята в неповёрнутом виде — поворачиваем на 90°); max_k — во сколько раз
## иконку можно растянуть (большие карточки: печёная иконка сильнее расплывается).
static func draw(canvas: CanvasItem, id: String, rect: Rect2, rotated: bool, max_k: float = INF) -> bool:
	return draw_tex(canvas, get_icon(id), rect, rotated, max_k)


static func _draw_tex(canvas: CanvasItem, tex: Texture2D, rect: Rect2, rotated: bool) -> bool:
	return draw_tex(canvas, tex, rect, rotated)


static func draw_tex(canvas: CanvasItem, tex: Texture2D, rect: Rect2, rotated: bool, max_k: float = INF) -> bool:
	if tex == null:
		return false
	var box := Vector2(rect.size.y, rect.size.x) if rotated else rect.size
	var ts := Vector2(tex.get_size())
	var k := minf(minf(box.x / ts.x, box.y / ts.y), max_k)
	var sz := ts * k
	var center := rect.get_center()
	if tex.has_meta(META_DETAIL):
		# мастер подробного значка: пересчитать под точки экрана и положить в целые точки
		var scale: Vector2 = screen_scale(canvas)
		var px := Vector2i((sz * scale).round())
		var fit: Texture2D = sized(tex, px)
		if fit != tex:
			tex = fit
			sz = Vector2(px) / scale
			var on_screen := Vector2(sz.y, sz.x) if rotated else sz
			center = ((center - on_screen * 0.5) * scale).round() / scale + on_screen * 0.5
	if rotated:
		canvas.draw_set_transform(center, PI * 0.5, Vector2.ONE)
		canvas.draw_texture_rect(tex, Rect2(-sz * 0.5, sz), false)
		canvas.draw_set_transform_matrix(Transform2D.IDENTITY)
	else:
		canvas.draw_texture_rect(tex, Rect2(center - sz * 0.5, sz), false)
	return true


## Сколько точек экрана в единице координат элемента (растяжение окна и масштаб самого элемента).
static func screen_scale(canvas: CanvasItem) -> Vector2:
	if canvas == null or not canvas.is_inside_tree():
		return Vector2.ONE
	var scale: Vector2 = (canvas.get_viewport().get_stretch_transform() * canvas.get_global_transform_with_canvas()).get_scale()
	return scale if scale.x > 0.0 and scale.y > 0.0 else Vector2.ONE


## Значок-мастер, пересчитанный под размер px (точки экрана) фильтром Ланцоша; пересчёт — один раз на размер.
## Мастер не крупнее px, без метки или без картинки (запуск без окна) — возвращается сам.
static func sized(tex: Texture2D, px: Vector2i) -> Texture2D:
	if tex == null or not tex.has_meta(META_DETAIL) or px.x < 1 or px.y < 1 or px.x >= tex.get_width():
		return tex
	var key: int = tex.get_instance_id()
	var rec: Dictionary = _sized.get(key, {})
	if rec.is_empty() or (rec.ref as WeakRef).get_ref() != tex:
		var img: Image = tex.get_image()
		if img == null or img.is_empty():
			return tex
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_RGBA8)
		# цвет края — и в прозрачные точки: иначе уменьшение тянет в контур чёрное
		img.fix_alpha_edges()
		if _sized.size() >= SIZED_MASTERS:
			for old: int in _sized.keys():
				if ((_sized[old] as Dictionary).ref as WeakRef).get_ref() == null:
					_sized.erase(old)
		rec = {"ref": weakref(tex), "img": img, "by": {}}
		_sized[key] = rec
	var by: Dictionary = rec.by
	if not by.has(px):
		var out: Image = (rec.img as Image).duplicate() as Image
		out.resize(px.x, px.y, Image.INTERPOLATE_LANCZOS)
		by[px] = ImageTexture.create_from_image(out)
	return by[px]
