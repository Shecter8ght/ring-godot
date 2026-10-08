class_name RainLens
extends CanvasLayer
## Капли дождя на «объективе» — симуляция, а не рисунок. Каждая капля живёт сама:
## удар — клякса из нескольких брызг, за доли секунды стягивается в каплю; крупная капля
## срывается и стекает вниз рывками и с вилянием, оставляя мокрую дорожку и бисеринки; без дождя
## всё сохнет. Капли рисуются куполами в карту высот (SubViewport, сложение — соседние сливаются,
## как жидкость); экранный шейдер по ней преломляет кадр: «жидкое стекло» — перевёрнутая картинка
## внутри, тёмный ободок, цветная кайма по краю, блик. Копятся только под открытым небом при
## взгляде вверх от 45° (RainFx.track → update).

const MAX_DROPS := 90
## Высота карты относительно экрана (половина — достаточно, преломление размывает).
const MAP_SCALE := 0.5
const DOME_PX := 64

const SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D height_tex : filter_linear, repeat_disable;
uniform vec2 texel = vec2(0.002, 0.0035);
uniform float strength = 1.0;
void fragment() {
	vec2 uv = SCREEN_UV;
	float h = texture(height_tex, uv).r;
	if (h < 0.02) {
		COLOR = textureLod(screen_tex, uv, 0.0);
	} else {
		float hx = texture(height_tex, uv + vec2(texel.x, 0.0)).r - texture(height_tex, uv - vec2(texel.x, 0.0)).r;
		float hy = texture(height_tex, uv + vec2(0.0, texel.y)).r - texture(height_tex, uv - vec2(0.0, texel.y)).r;
		vec3 n = normalize(vec3(-hx * 2.6, -hy * 2.6, 1.0));
		// край капли — порог по высоте: слившиеся капли дают общий контур
		float cover = smoothstep(0.1, 0.16, h);
		// выпуклая линза: внутри — картинка с противоположной стороны (перевёрнута), цвета расходятся у края
		vec2 o = n.xy * 0.22 * strength;
		vec3 c;
		c.r = textureLod(screen_tex, uv - o * 1.04, 0.5).r;
		c.g = textureLod(screen_tex, uv - o, 0.5).g;
		c.b = textureLod(screen_tex, uv - o * 0.96, 0.5).b;
		// тонкая тёмная кромка там, где поверхность круче всего (у самого края)
		float rim = smoothstep(0.1, 0.13, h) * (1.0 - smoothstep(0.13, 0.22, h));
		c *= 1.0 - rim * 0.45;
		// мелкий блик сверху и слабый отсвет снизу (свет проходит каплю насквозь)
		float spec = pow(max(dot(n, normalize(vec3(-0.3, -0.6, 0.74))), 0.0), 160.0);
		float glow = pow(max(dot(n, normalize(vec3(0.2, 0.7, 0.68))), 0.0), 24.0);
		c += spec * 0.7 + glow * 0.08;
		float a = cover;
		COLOR = vec4(mix(textureLod(screen_tex, uv, 0.0).rgb, c, a), 1.0);
	}
}
"""


class Drop:
	var pos: Vector2          # доли экрана (x по ширине, y по высоте)
	var r: float              # радиус, доля высоты экрана
	var age: float = 0.0
	var sliding: bool = false
	var vy: float = 0.0
	var pause: float = 0.0
	var wob: float = 0.0
	var trail_t: float = 0.0
	var splat: Array = []     # [смещение, радиус] брызг удара
	var lobes: Array = []     # [смещение (доля r), масштаб] — неровный контур
	var lobe_sprites: Array[Sprite2D] = []
	var splat_sprites: Array[Sprite2D] = []
	var residue: bool = false # след/бисеринка: не течёт, быстро сохнет
	var sprite: Sprite2D


var _vp: SubViewport
var _root: Node2D
var _rect: ColorRect
var _mat: ShaderMaterial
var _dome: ImageTexture
var _drops: Array[Drop] = []
var _rng := RandomNumberGenerator.new()
var _spawn_acc: float = 0.0


func _ready() -> void:
	layer = 1
	_rng.randomize()
	_vp = SubViewport.new()
	_vp.transparent_bg = true
	_vp.use_hdr_2d = true
	_vp.disable_3d = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)
	_root = Node2D.new()
	_vp.add_child(_root)
	_dome = _make_dome()
	_rect = ColorRect.new()
	_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_mat = ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = SHADER
	_mat.shader = sh
	_mat.set_shader_parameter("height_tex", _vp.get_texture())
	_rect.material = _mat
	add_child(_rect)
	visible = false


## Купол высоты: профиль капли (плоское дно, крутой край у стекла — как у настоящей).
func _make_dome() -> ImageTexture:
	var img := Image.create(DOME_PX, DOME_PX, false, Image.FORMAT_RGBAF)
	var c := (DOME_PX - 1) * 0.5
	for y in range(DOME_PX):
		for x in range(DOME_PX):
			var d := Vector2(x - c, y - c).length() / c
			var h := 0.0 if d >= 1.0 else pow(1.0 - d * d, 0.6)
			img.set_pixel(x, y, Color(h, 0, 0, 1))
	return ImageTexture.create_from_image(img)


## Каждый кадр от RainFx: сила дождя, куда смотрим (y вектора взгляда), под открытым ли небом.
func step(dt: float, rain_k: float, look_up: float, outdoor: bool) -> void:
	var vs := get_viewport().get_visible_rect().size
	var size := Vector2i(maxi(64, int(vs.x * MAP_SCALE)), maxi(64, int(vs.y * MAP_SCALE)))
	if _vp.size != size:
		_vp.size = size
		_mat.set_shader_parameter("texel", Vector2(2.0 / size.x, 2.0 / size.y))
	var collect: bool = outdoor and rain_k > 0.2 and look_up >= 0.707
	if collect:
		var k: float = rain_k * (0.35 + 0.65 * clampf((look_up - 0.707) / 0.29, 0.0, 1.0))
		_spawn_acc += dt * 9.0 * k
		while _spawn_acc >= 1.0 and _drops.size() < MAX_DROPS:
			_spawn_acc -= 1.0
			_spawn(Vector2(_rng.randf(), _rng.randf() * 0.95), _rng.randf_range(0.006, 0.02) if _rng.randf() < 0.8 else _rng.randf_range(0.02, 0.034), false)
	else:
		_spawn_acc = 0.0
	# взгляд вниз — капли текут вниз (гравитация вдоль экрана), вверх — почти стоят
	var grav: float = clampf(1.0 - maxf(look_up, 0.0) * 0.6, 0.35, 1.0)
	var aspect: float = vs.x / maxf(vs.y, 1.0)
	for d in _drops.duplicate():
		_tick(d, dt, collect, grav)
	for d in _drops.duplicate():
		if d.r < 0.0025 or d.pos.y - d.r > 1.05:
			_remove(d)
	for d in _drops:
		_draw(d, size, aspect)
	visible = not _drops.is_empty()
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if visible else SubViewport.UPDATE_DISABLED


func _spawn(p: Vector2, r: float, residue: bool) -> Drop:
	var d := Drop.new()
	d.pos = p
	d.r = r
	d.residue = residue
	d.wob = _rng.randf() * TAU
	if not residue:
		# клякса удара: брызги вокруг, стягиваются за ~0.25 с
		for i in range(_rng.randi_range(3, 7)):
			var a := _rng.randf() * TAU
			d.splat.append([Vector2(cos(a), sin(a)) * r * _rng.randf_range(1.2, 2.6), r * _rng.randf_range(0.25, 0.55)])
	d.sprite = Sprite2D.new()
	d.sprite.texture = _dome
	var cm := CanvasItemMaterial.new()
	cm.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	d.sprite.material = cm
	_root.add_child(d.sprite)
	if not residue:
		for i in range(_rng.randi_range(1, 3)):
			var a := _rng.randf() * TAU
			d.lobes.append([Vector2(cos(a), sin(a) * 0.8) * _rng.randf_range(0.25, 0.5), _rng.randf_range(0.5, 0.8)])
	for l in d.lobes:
		var lp := Sprite2D.new()
		lp.texture = _dome
		lp.material = cm
		d.sprite.add_child(lp)
		d.lobe_sprites.append(lp)
	for s in d.splat:
		var sp := Sprite2D.new()
		sp.texture = _dome
		sp.material = cm
		d.sprite.add_child(sp)
		d.splat_sprites.append(sp)
	_drops.append(d)
	return d


func _tick(d: Drop, dt: float, collect: bool, grav: float) -> void:
	d.age += dt
	# сохнет: следы быстро, капли медленно; под дождём капли почти не сохнут
	var dry: float = (0.012 if d.residue else (0.0006 if collect else 0.004)) * dt
	d.r -= dry
	if d.residue:
		return
	# крупная капля срывается и течёт рывками
	if not d.sliding and d.r > 0.019 and d.age > 0.4 and _rng.randf() < dt * 0.8:
		d.sliding = true
	if d.sliding:
		if d.pause > 0.0:
			d.pause -= dt
			d.vy = 0.0
		else:
			d.vy = minf(d.vy + 0.9 * grav * dt, 0.35 * grav)
			if _rng.randf() < dt * 1.2:
				d.pause = _rng.randf_range(0.1, 0.6)
		d.pos.y += d.vy * dt
		d.pos.x += sin(d.age * 3.0 + d.wob) * 0.012 * dt * (1.0 if d.vy > 0.0 else 0.0)
		# дорожка: мокрый след и бисеринки, капля теряет воду
		d.trail_t -= d.vy * dt
		if d.trail_t <= 0.0 and d.vy > 0.0:
			d.trail_t = d.r * 0.9
			var bead: float = d.r * _rng.randf_range(0.18, 0.35)
			_spawn(d.pos + Vector2(_rng.randf_range(-0.2, 0.2) * d.r, -d.r * 0.9), bead, true)
			d.r -= bead * 0.12
			if d.r < 0.015:
				d.sliding = false
	# слияние: догнала другую — забирает её воду
	for o in _drops:
		if o == d or o.residue:
			continue
		if d.pos.distance_to(o.pos) < (d.r + o.r) * 0.75 and d.r >= o.r:
			d.r = sqrt(d.r * d.r + o.r * o.r)
			o.r = 0.0


func _draw(d: Drop, size: Vector2i, aspect: float) -> void:
	var px_r: float = d.r * size.y
	var stretch: float = 1.0 + minf(d.vy * 3.0, 0.7)
	d.sprite.position = Vector2(d.pos.x * size.x, d.pos.y * size.y)
	d.sprite.scale = Vector2(2.0 * px_r / DOME_PX / stretch * 1.0, 2.0 * px_r / DOME_PX * stretch)
	# высота купола: следы ниже (тонкая плёнка), капли выше
	var hgt: float = 0.2 if d.residue else clampf(0.45 + d.r * 12.0, 0.45, 0.85)
	d.sprite.modulate = Color(hgt, 0, 0, 1)
	# дольки: у стекающей капли тянутся вверх — хвост; у стоящей — неровный край
	for j in range(d.lobes.size()):
		var lp := d.lobe_sprites[j]
		var off: Vector2 = d.lobes[j][0]
		if d.vy > 0.0:
			off = Vector2(off.x * 0.3, -absf(off.y) - 0.6 * (j + 1))
		lp.position = off * DOME_PX * 0.5
		lp.scale = Vector2.ONE * float(d.lobes[j][1]) * (0.75 if d.vy > 0.0 else 1.0)
		lp.modulate = Color(0.75, 0, 0, 1)
	var t: float = clampf(d.age / 0.25, 0.0, 1.0)
	for i in range(d.splat_sprites.size()):
		var sp := d.splat_sprites[i]
		if t >= 1.0:
			sp.visible = false
			continue
		var s: Array = d.splat[i]
		# брызги стягиваются к центру и вливаются в каплю
		var off2: Vector2 = (s[0] as Vector2) * (1.0 - t * t)
		sp.position = Vector2(off2.x * size.y, off2.y * size.y) / d.sprite.scale
		sp.scale = Vector2.ONE * float(s[1]) / maxf(d.r, 0.0001) * (1.0 - t * 0.5)
		sp.modulate = Color(0.8, 0, 0, 1)
	if t >= 1.0 and not d.splat_sprites.is_empty():
		for sp in d.splat_sprites:
			sp.queue_free()
		d.splat_sprites.clear()
		d.splat.clear()


func _remove(d: Drop) -> void:
	_drops.erase(d)
	if is_instance_valid(d.sprite):
		d.sprite.queue_free()


func clear() -> void:
	for d in _drops.duplicate():
		_remove(d)
