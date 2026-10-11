class_name StickerArt
extends RefCounted
## Рисунки наклеек. Свой рисунок владельца — файл res://assets/stickers/<id>.png (прозрачный фон,
## квадрат; у «Счёта» — 2:1): положили файл — он и клеится, и идёт в иконку (tools/sticker_icons).
## Пока файла нет — простой знак, нарисованный кодом, чтобы механика работала.
## «Счёт» всегда дорисовывается: зарубки по числу эвакуаций со стволом (n) поверх основы.

const DIR := "res://assets/stickers/%s.png"
const SIZE := 256

static var _cache: Dictionary = {}


## Ширина к высоте.
static func aspect(id: String) -> float:
	return float((Balance.STICKERS.aspect as Dictionary).get(id, 1.0))


static func texture(id: String, n: int = 0) -> Texture2D:
	var key: String = "%s|%d" % [id, n]
	if not _cache.has(key):
		if _cache.size() > 64:
			_cache.clear()
		_cache[key] = ImageTexture.create_from_image(image(id, n))
	return _cache[key]


static func image(id: String, n: int = 0) -> Image:
	var w: int = int(round(SIZE * aspect(id)))
	var img: Image = _custom(id, w)
	var own: bool = img != null
	if img == null:
		img = Image.create(w, SIZE, false, Image.FORMAT_RGBA8)
		img.fill(Color(0, 0, 0, 0))
	match id:
		"sticker_skull":
			if not own:
				_skull(img)
		"sticker_shark":
			if not own:
				_shark(img)
		"sticker_perimeter":
			if not own:
				_perimeter(img)
		"sticker_tally":
			if not own:
				_plate(img, Color(0.93, 0.9, 0.8), Color(0.12, 0.12, 0.12))
			_tally(img, n)
		_:
			if not own:
				_plate(img, Color(0.85, 0.85, 0.82), Color(0.1, 0.1, 0.1))
	return img


## Свой рисунок владельца, приведённый к нужному размеру; нет файла — null.
static func _custom(id: String, w: int) -> Image:
	var path: String = DIR % id
	if not ResourceLoader.exists(path):
		return null
	var tex: Texture2D = load(path) as Texture2D
	if tex == null:
		return null
	var img: Image = tex.get_image()
	if img == null:
		return null
	img = img.duplicate() as Image
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGBA8)
	img.resize(w, SIZE, Image.INTERPOLATE_LANCZOS)
	return img


# ---------------------------------------------------------------- знаки кодом

static func _skull(img: Image) -> void:
	var bone := Color(0.94, 0.93, 0.88)
	var ink := Color(0.07, 0.07, 0.08)
	_disc(img, Vector2(128, 128), 124, bone)
	_disc(img, Vector2(128, 128), 114, ink)
	_disc(img, Vector2(128, 110), 62, bone)
	_rrect(img, Rect2(92, 146, 72, 52), 12, bone)
	for x: float in [104.0, 152.0]:
		_disc(img, Vector2(x, 114), 17, ink)
	_poly(img, [Vector2(128, 136), Vector2(117, 158), Vector2(139, 158)], ink)
	for x: float in [110.0, 128.0, 146.0]:
		_line(img, Vector2(x, 172), Vector2(x, 198), 4, ink)


static func _shark(img: Image) -> void:
	_rrect(img, Rect2(6, 54, 244, 148), 42, Color(0.9, 0.9, 0.86))
	_rrect(img, Rect2(14, 62, 228, 132), 36, Color(0.16, 0.23, 0.32))
	_ellipse(img, Vector2(142, 140), Vector2(92, 44), Color(0.6, 0.06, 0.05))
	var tooth := Color(0.96, 0.95, 0.9)
	for i: int in range(7):
		var x: float = 60.0 + i * 24.0
		_poly(img, [Vector2(x, 104), Vector2(x + 22, 104), Vector2(x + 11, 132)], tooth)
		_poly(img, [Vector2(x, 176), Vector2(x + 22, 176), Vector2(x + 11, 150)], tooth)
	_disc(img, Vector2(58, 88), 14, tooth)
	_disc(img, Vector2(60, 88), 6, Color(0.05, 0.05, 0.05))


static func _perimeter(img: Image) -> void:
	var gold := Color(0.86, 0.7, 0.22)
	var shield: Array = [Vector2(128, 12), Vector2(234, 48), Vector2(234, 142), Vector2(128, 244), Vector2(22, 142), Vector2(22, 48)]
	_poly(img, shield, gold)
	var inner: Array = []
	for p: Vector2 in shield:
		inner.append(Vector2(128, 124) + (p - Vector2(128, 124)) * 0.9)
	_poly(img, inner, Color(0.09, 0.15, 0.12))
	_disc(img, Vector2(128, 108), 58, gold)
	_disc(img, Vector2(128, 108), 46, Color(0.09, 0.15, 0.12))
	var white := Color(0.92, 0.92, 0.88)
	_line(img, Vector2(110, 132), Vector2(110, 88), 9, white)
	_line(img, Vector2(110, 88), Vector2(146, 88), 9, white)
	_line(img, Vector2(146, 88), Vector2(146, 132), 9, white)
	_line(img, Vector2(90, 196), Vector2(128, 174), 10, gold)
	_line(img, Vector2(128, 174), Vector2(166, 196), 10, gold)


## Подложка: скруглённая плашка с каймой.
static func _plate(img: Image, fill: Color, edge: Color) -> void:
	var w: float = float(img.get_width())
	var h: float = float(img.get_height())
	_rrect(img, Rect2(4, 28, w - 8, h - 56), 26, edge)
	_rrect(img, Rect2(12, 36, w - 24, h - 72), 20, fill)


## Зарубки пятёрками: четыре палочки и перечёркивающая; n — сколько эвакуаций.
static func _tally(img: Image, n: int) -> void:
	var ink := Color(0.1, 0.1, 0.11)
	var groups: int = int(Balance.STICKERS.tally_max) / 5
	var step: float = (float(img.get_width()) - 56.0) / float(maxi(groups, 1))
	for i: int in range(mini(n, int(Balance.STICKERS.tally_max))):
		var g: int = i / 5
		var k: int = i % 5
		var x0: float = 36.0 + g * step
		if k < 4:
			var x: float = x0 + k * step * 0.19
			_line(img, Vector2(x + 3, 70), Vector2(x - 3, 186), 7, ink)
		else:
			_line(img, Vector2(x0 - 10, 176), Vector2(x0 + step * 0.66, 82), 7, ink)


# ---------------------------------------------------------------- примитивы растра

static func _fill(img: Image, box: Rect2, inside: Callable, col: Color) -> void:
	var x0: int = clampi(int(floor(box.position.x)), 0, img.get_width() - 1)
	var x1: int = clampi(int(ceil(box.end.x)), 0, img.get_width() - 1)
	var y0: int = clampi(int(floor(box.position.y)), 0, img.get_height() - 1)
	var y1: int = clampi(int(ceil(box.end.y)), 0, img.get_height() - 1)
	for y: int in range(y0, y1 + 1):
		for x: int in range(x0, x1 + 1):
			if bool(inside.call(Vector2(x + 0.5, y + 0.5))):
				img.set_pixel(x, y, col)


static func _disc(img: Image, c: Vector2, r: float, col: Color) -> void:
	_fill(img, Rect2(c - Vector2(r, r), Vector2(r, r) * 2.0), func(p: Vector2) -> bool: return p.distance_to(c) <= r, col)


static func _ellipse(img: Image, c: Vector2, r: Vector2, col: Color) -> void:
	_fill(img, Rect2(c - r, r * 2.0), func(p: Vector2) -> bool: return ((p - c) / r).length() <= 1.0, col)


static func _rrect(img: Image, rect: Rect2, radius: float, col: Color) -> void:
	var core: Rect2 = rect.grow(-radius)
	_fill(img, rect, func(p: Vector2) -> bool:
		var q: Vector2 = Vector2(clampf(p.x, core.position.x, core.end.x), clampf(p.y, core.position.y, core.end.y))
		return p.distance_to(q) <= radius, col)


static func _line(img: Image, a: Vector2, b: Vector2, width: float, col: Color) -> void:
	var box: Rect2 = Rect2(a, Vector2.ZERO).expand(b).grow(width)
	_fill(img, box, func(p: Vector2) -> bool:
		return p.distance_to(Geometry2D.get_closest_point_to_segment(p, a, b)) <= width * 0.5, col)


static func _poly(img: Image, points: Array, col: Color) -> void:
	var packed: PackedVector2Array = PackedVector2Array(points)
	var box: Rect2 = Rect2(packed[0], Vector2.ZERO)
	for p: Vector2 in packed:
		box = box.expand(p)
	_fill(img, box, func(p: Vector2) -> bool: return Geometry2D.is_point_in_polygon(p, packed), col)
