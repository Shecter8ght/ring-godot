class_name GlassCracks
extends RefCounted
## Трещины одной панели стекла (GlassPanes) — рисуются на её текстуре при каждом попадании:
## сквозная дырка, белая крошка вокруг, лучи от точки удара (сколько, под какими углами, какой
## длины, с изломами и ветками — своё у каждого попадания), дуги между соседними лучами. Луч
## останавливается, дойдя до трещины от прежнего попадания. Пока ослабленная панель держится,
## концы лучей понемногу ползут дальше (creep). Каналы текстуры: R — трещины, G — матовая крошка,
## B — дырка насквозь. Случайность — от номера панели и попадания: у всех peer узор один.
## Углы лучей и радиусы дуг запоминаются (hits) — по ним GlassShatter режет панель на куски.

var image: Image
var texture: ImageTexture
## Размер панели, м, и пикселей на метр.
var size_m: Vector2
var ppm: float
## Попадания: {"at": Vector2 (м от центра панели, Y вверх), "angles": PackedFloat32Array (углы лучей
## в тех же осях), "arcs": PackedFloat32Array (радиусы дуг, м)}.
var hits: Array[Dictionary] = []

var _w: int
var _h: int
var _data: PackedByteArray
## Снимок трещин до текущего попадания — лучи останавливаются только о чужие трещины.
var _before: PackedByteArray
## Концы лучей, которые ещё могут ползти: {"pos": Vector2 (px), "ang": float (px, Y вниз)}.
var _tips: Array[Dictionary] = []
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()


func _init(pane_size: Vector2) -> void:
	var cfg: Dictionary = Balance.GLASS
	size_m = pane_size
	ppm = minf(float(cfg.crack_ppm), float(cfg.crack_px_max) / maxf(pane_size.x, pane_size.y))
	_w = maxi(8, int(ceil(pane_size.x * ppm)))
	_h = maxi(8, int(ceil(pane_size.y * ppm)))
	_data = PackedByteArray()
	_data.resize(_w * _h * 4)
	_data.fill(0)
	image = Image.create_from_data(_w, _h, false, Image.FORMAT_RGBA8, _data)
	image.generate_mipmaps()
	texture = ImageTexture.create_from_image(image)


## Попадание в точку uv (0..1 по панели, Y вверх): запомнить лучи и дуги, нарисовать — если draw
## (панель, которая рассыпается в этом же кадре, не рисует). damage_k 0..1 — сила удара, weak —
## панель уже ослаблена (лучи длиннее, часть — до рамы); rays — false у закалённого (только дырка и
## крошка, остальное — сетка кубиков в шейдере).
func add_hit(uv: Vector2, seed_value: int, damage_k: float, weak: bool, draw: bool, rays: bool = true) -> void:
	var cfg: Dictionary = Balance.GLASS
	_rng.seed = seed_value
	var center: Vector2 = Vector2(uv.x * _w, (1.0 - uv.y) * _h)
	var rays_range: Vector2i = cfg.rays
	var count: int = clampi(int(round(lerpf(float(rays_range.x), float(rays_range.y), clampf(damage_k, 0.0, 1.0) * 0.7 + _rng.randf() * 0.3))), rays_range.x, rays_range.y)
	# неравные промежутки между лучами — не звезда
	var weights: Array[float] = []
	var total: float = 0.0
	for i: int in range(count):
		var w: float = _rng.randf_range(0.35, 1.65)
		weights.append(w)
		total += w
	var angles: PackedFloat32Array = PackedFloat32Array()
	var a: float = _rng.randf() * TAU
	for i: int in range(count):
		angles.append(a)
		a += weights[i] / total * TAU
	var len_range: Vector2 = cfg.ray_len_m
	var base_len: float = lerpf(len_range.x, len_range.y, clampf(damage_k, 0.0, 1.0)) * ppm
	var lengths: PackedFloat32Array = PackedFloat32Array()
	for i: int in range(count):
		var k: float = _rng.randf_range(0.35, 1.0)
		if weak and _rng.randf() < 0.35:
			k *= 3.0
		lengths.append(base_len * k)
	var arcs: PackedFloat32Array = PackedFloat32Array()
	var arcs_range: Vector2i = cfg.arcs
	for i: int in range(_rng.randi_range(arcs_range.x, arcs_range.y)):
		arcs.append(base_len * _rng.randf_range(0.18, 0.62) / ppm)
	arcs.sort()
	var local_angles: PackedFloat32Array = PackedFloat32Array()
	for angle: float in angles:
		local_angles.append(-angle)
	hits.append({"at": Vector2((uv.x - 0.5) * size_m.x, (uv.y - 0.5) * size_m.y), "angles": local_angles, "arcs": arcs})
	if not draw:
		return
	_before = _data.duplicate()
	var frost_range: Vector2 = cfg.frost_m
	var frost_px: float = _rng.randf_range(frost_range.x, frost_range.y) * ppm
	_frost(center, frost_px)
	if not rays:
		count = 0
		arcs = PackedFloat32Array()
	for i: int in range(count):
		var end: Dictionary = _grow(center, angles[i], lengths[i], 1.3, 0, frost_px * 0.6)
		if not end.is_empty():
			_tips.append(end)
	for radius_m: float in arcs:
		_arc_ring(center, angles, lengths, radius_m * ppm)
	var hole_range: Vector2 = cfg.hole_m
	_hole(center, _rng.randf_range(hole_range.x, hole_range.y) * ppm)
	_upload()


## Ослабленная панель потрескивает: несколько концов лучей ползут дальше. true — что-то выросло.
func creep(seed_value: int) -> bool:
	if _tips.is_empty():
		return false
	var cfg: Dictionary = Balance.GLASS
	_rng.seed = seed_value
	_before = _data.duplicate()
	var grown: bool = false
	var creep_px: Vector2 = cfg.creep_px
	for n: int in range(_rng.randi_range(1, 3)):
		var index: int = _rng.randi_range(0, _tips.size() - 1)
		var tip: Dictionary = _tips[index]
		var end: Dictionary = _grow(tip.pos, tip.ang, _rng.randf_range(creep_px.x, creep_px.y), 1.1, 1, 0.0)
		if end.is_empty():
			_tips.remove_at(index)
		else:
			_tips[index] = end
		grown = true
		if _tips.is_empty():
			break
	if grown:
		_upload()
	return grown


## Луч из точки: блуждает, ломается, ветвится; стоп — у края панели или у чужой трещины.
## Возвращает конец для дальнейшего роста или {} (упёрся).
func _grow(from: Vector2, angle: float, length: float, width: float, depth: int, free_px: float) -> Dictionary:
	var pos: Vector2 = from
	var ang: float = angle
	var travelled: float = 0.0
	var kink: float = _rng.randf_range(10.0, 40.0)
	var step: float = 2.0
	while travelled < length:
		ang += _rng.randf_range(-0.06, 0.06)
		kink -= step
		if kink <= 0.0:
			ang += _rng.randf_range(-0.38, 0.38)
			kink = _rng.randf_range(12.0, 45.0)
		var next: Vector2 = pos + Vector2(cos(ang), sin(ang)) * step
		if next.x < 0.0 or next.y < 0.0 or next.x >= float(_w) or next.y >= float(_h):
			return {}
		var fade: float = travelled / maxf(length, 1.0)
		_line(pos, next, maxf(0.7, width * (1.0 - 0.45 * fade)), 1.0 - 0.35 * fade)
		if travelled > free_px and _was_cracked(next):
			return {}
		if depth < 2 and _rng.randf() < 0.012 * step:
			var side: float = 1.0 if _rng.randf() < 0.5 else -1.0
			_grow(next, ang + side * _rng.randf_range(0.3, 0.75), (length - travelled) * _rng.randf_range(0.25, 0.6), width * 0.7, depth + 1, 0.0)
		pos = next
		travelled += step
	return {"pos": pos, "ang": ang}


## Дуги между соседними лучами на радиусе r (px): не везде, с неровным радиусом.
func _arc_ring(center: Vector2, angles: PackedFloat32Array, lengths: PackedFloat32Array, r: float) -> void:
	var count: int = angles.size()
	for i: int in range(count):
		var j: int = (i + 1) % count
		if lengths[i] < r or lengths[j] < r or _rng.randf() > 0.62:
			continue
		var a0: float = angles[i]
		var a1: float = angles[j]
		if a1 < a0:
			a1 += TAU
		var radius: float = r * _rng.randf_range(0.88, 1.12)
		var steps: int = maxi(2, int((a1 - a0) * radius / 3.0))
		var prev: Vector2 = center + Vector2(cos(a0), sin(a0)) * radius
		for s: int in range(1, steps + 1):
			var t: float = float(s) / float(steps)
			# дуга не идеальна: радиус гуляет, к середине — чуть провисает
			var rr: float = radius * (1.0 + 0.06 * sin(t * PI) * (1.0 if i % 2 == 0 else -1.0)) + _rng.randf_range(-0.8, 0.8)
			var a: float = lerpf(a0, a1, t)
			var point: Vector2 = center + Vector2(cos(a), sin(a)) * rr
			_line(prev, point, 0.9, 0.75)
			prev = point


## Белая крошка вокруг дырки (G) и мелкие трещинки в ней (R).
func _frost(center: Vector2, radius: float) -> void:
	var r: int = int(ceil(radius * 1.3))
	for y: int in range(maxi(0, int(center.y) - r), mini(_h, int(center.y) + r + 1)):
		for x: int in range(maxi(0, int(center.x) - r), mini(_w, int(center.x) + r + 1)):
			var d: float = Vector2(float(x) + 0.5, float(y) + 0.5).distance_to(center) / radius
			d += (_hash(x, y) - 0.5) * 0.35
			var v: float = 1.0 - smoothstep(0.55, 1.0, d)
			if v > 0.0:
				_put(x, y, 1, v)
	for i: int in range(_rng.randi_range(14, 26)):
		var a: float = _rng.randf() * TAU
		var from: Vector2 = center + Vector2(cos(a), sin(a)) * radius * _rng.randf_range(0.0, 0.4)
		var to: Vector2 = center + Vector2(cos(a), sin(a)) * radius * _rng.randf_range(0.8, 1.9)
		_line(from, to, 0.8, 0.8)


func _hole(center: Vector2, radius: float) -> void:
	var r: int = int(ceil(radius + 1.5))
	for y: int in range(maxi(0, int(center.y) - r), mini(_h, int(center.y) + r + 1)):
		for x: int in range(maxi(0, int(center.x) - r), mini(_w, int(center.x) + r + 1)):
			var d: float = Vector2(float(x) + 0.5, float(y) + 0.5).distance_to(center) + (_hash(x + 17, y) - 0.5) * 1.2
			var v: float = clampf(radius + 0.5 - d, 0.0, 1.0)
			if v > 0.0:
				_put(x, y, 2, v)


func _line(a: Vector2, b: Vector2, width: float, value: float) -> void:
	var steps: int = maxi(1, int(ceil(a.distance_to(b))))
	var r: float = width * 0.5 + 0.5
	for s: int in range(steps + 1):
		var p: Vector2 = a.lerp(b, float(s) / float(steps))
		for y: int in range(maxi(0, floori(p.y - r)), mini(_h, ceili(p.y + r))):
			for x: int in range(maxi(0, floori(p.x - r)), mini(_w, ceili(p.x + r))):
				var k: float = clampf(r - Vector2(float(x) + 0.5, float(y) + 0.5).distance_to(p), 0.0, 1.0)
				if k > 0.0:
					_put(x, y, 0, value * k)


func _put(x: int, y: int, channel: int, value: float) -> void:
	var index: int = (y * _w + x) * 4 + channel
	var v: int = int(clampf(value, 0.0, 1.0) * 255.0)
	if v > _data[index]:
		_data[index] = v


func _was_cracked(p: Vector2) -> bool:
	var index: int = (int(p.y) * _w + int(p.x)) * 4
	return _before[index] > 110


func _hash(x: int, y: int) -> float:
	var n: int = (x * 73856093) ^ (y * 19349663)
	n = (n ^ (n >> 13)) * 1274126177
	return float(n & 0xFFFF) / 65535.0


func _upload() -> void:
	image.set_data(_w, _h, false, Image.FORMAT_RGBA8, _data)
	image.generate_mipmaps()
	texture.update(image)
