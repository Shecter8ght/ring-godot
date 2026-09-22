extends Node
## Эффекты попаданий: частицы по виду поверхности, декали (отверстия, трещины, кровь),
## вспышка искр, звук удара. Autoload `ImpactFx`. Текстуры декалей и частиц рисуются кодом.

## Сколько декалей держим в мире — старые убираются.
const MAX_DECALS := 320

## Частицы по виду поверхности: цвета, число, скорость, гравитация, размер, время жизни, свечение.
const FX := {
	"concrete": {"colors": [Color(0.72, 0.7, 0.66), Color(0.55, 0.53, 0.5)], "count": 18, "speed": [2.0, 5.0], "gravity": -9.0, "size": 0.077, "life": 0.55, "dust": true},
	"tile": {"colors": [Color(0.8, 0.78, 0.74), Color(0.6, 0.6, 0.58)], "count": 14, "speed": [2.5, 6.0], "gravity": -9.0, "size": 0.066, "life": 0.5, "dust": true},
	"asphalt": {"colors": [Color(0.3, 0.29, 0.28), Color(0.45, 0.43, 0.4)], "count": 16, "speed": [2.0, 5.0], "gravity": -9.0, "size": 0.066, "life": 0.5, "dust": true},
	"metal": {"colors": [Color(1.0, 0.85, 0.45), Color(1.0, 0.6, 0.2)], "count": 22, "speed": [5.0, 12.0], "gravity": -12.0, "size": 0.040, "life": 0.35, "spark": true},
	"glass": {"colors": [Color(0.8, 0.9, 0.95), Color(0.6, 0.75, 0.85)], "count": 26, "speed": [2.0, 6.0], "gravity": -9.0, "size": 0.066, "life": 0.7, "spark": true},
	"wood": {"colors": [Color(0.55, 0.4, 0.22), Color(0.4, 0.28, 0.14)], "count": 16, "speed": [2.0, 6.0], "gravity": -9.0, "size": 0.088, "life": 0.6},
	"cardboard": {"colors": [Color(0.62, 0.5, 0.32), Color(0.5, 0.4, 0.26)], "count": 14, "speed": [1.5, 4.0], "gravity": -4.0, "size": 0.110, "life": 0.8},
	"fabric": {"colors": [Color(0.25, 0.22, 0.35), Color(0.4, 0.15, 0.2)], "count": 10, "speed": [1.0, 3.0], "gravity": -2.0, "size": 0.088, "life": 0.9},
	"plastic": {"colors": [Color(0.15, 0.15, 0.16), Color(0.3, 0.3, 0.3)], "count": 12, "speed": [2.0, 5.0], "gravity": -8.0, "size": 0.066, "life": 0.5},
	"flesh": {"colors": [Color(0.45, 0.03, 0.03), Color(0.3, 0.02, 0.02)], "count": 24, "speed": [2.0, 6.0], "gravity": -9.0, "size": 0.077, "life": 0.6},
}

## Звук удара по виду поверхности.
const SOUND := {
	"concrete": "impact_hard", "tile": "impact_hard", "asphalt": "impact_hard", "metal": "impact_metal",
	"glass": "impact_glass", "wood": "impact_soft", "cardboard": "impact_soft", "fabric": "impact_soft",
	"plastic": "impact_soft", "flesh": "hit",
}

var _rng := RandomNumberGenerator.new()
var _decals: Array[Decal] = []
var _stickers: Array[MeshInstance3D] = []
var _tex_hole: Texture2D
var _tex_crack: Texture2D
var _tex_splat: Texture2D
var _tex_dust: Texture2D
var _process_mats: Dictionary = {}
var _chip_mesh: BoxMesh
var _spark_mesh: BoxMesh
var _dust_mesh: QuadMesh


func _ready() -> void:
	_rng.randomize()
	_tex_hole = _make_hole_texture(64)
	_tex_crack = _make_crack_texture(96)
	_tex_splat = _make_splat_texture(128)
	_tex_dust = _make_soft_texture(48)
	_chip_mesh = BoxMesh.new()
	_chip_mesh.size = Vector3(1, 1, 1)
	_spark_mesh = BoxMesh.new()
	_spark_mesh.size = Vector3(0.6, 0.6, 3.0)
	_dust_mesh = QuadMesh.new()
	_dust_mesh.size = Vector2(1, 1)


## Точка входа: результат intersect_ray и направление пули.
func spawn_hit(hit: Dictionary, dir: Vector3) -> void:
	if hit.is_empty() or not hit.has("position"):
		return
	var kind := Surfaces.kind_at(hit)
	var pos: Vector3 = hit.position
	var n: Vector3 = hit.get("normal", -dir)
	if n.length_squared() < 0.01:
		n = -dir
	var parent := get_tree().current_scene
	if parent == null:
		return
	if kind == "flesh":
		_blood(parent, pos, dir, hit.collider)
	else:
		_particles(parent, kind, pos, n, dir)
		_decal(parent, kind, pos, n)
		if bool(FX[kind].get("spark", false)):
			_flash(parent, pos + n * 0.1, Color(1.0, 0.8, 0.5) if kind == "metal" else Color(0.8, 0.9, 1.0))
	Audio.play(String(SOUND.get(kind, "impact_hard")), pos)


# ---------------------------------------------------------------- частицы

func _particles(parent: Node, kind: String, pos: Vector3, n: Vector3, dir: Vector3) -> void:
	var spec: Dictionary = FX[kind]
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 1.0
	p.amount = int(spec.count)
	p.lifetime = float(spec.life)
	p.process_material = _process_for(kind, n, dir)
	p.draw_pass_1 = _spark_mesh if bool(spec.get("spark", false)) else _chip_mesh
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.roughness = 0.8
	if bool(spec.get("spark", false)):
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.emission_enabled = true
		mat.emission = (spec.colors[0] as Color)
		mat.emission_energy_multiplier = 3.0
	p.material_override = mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(p)
	p.global_position = pos + n * 0.03
	p.emitting = true
	get_tree().create_timer(float(spec.life) + 0.3).timeout.connect(p.queue_free)
	if bool(spec.get("dust", false)):
		_dust(parent, pos, n, spec.colors[0])


## Облачко пыли: несколько мягких квадов-билбордов, растут и тают.
func _dust(parent: Node, pos: Vector3, n: Vector3, color: Color) -> void:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 1.0
	p.amount = 8
	p.lifetime = 1.1
	var pm := ParticleProcessMaterial.new()
	pm.direction = n
	pm.spread = 45.0
	pm.initial_velocity_min = 0.6
	pm.initial_velocity_max = 1.6
	pm.gravity = Vector3(0, 0.3, 0)
	pm.damping_min = 2.0
	pm.damping_max = 3.0
	pm.scale_min = 0.6
	pm.scale_max = 1.1
	var scale_curve := CurveTexture.new()
	var c := Curve.new()
	c.add_point(Vector2(0, 0.4))
	c.add_point(Vector2(1, 1.0))
	scale_curve.curve = c
	pm.scale_curve = scale_curve
	var grad := Gradient.new()
	grad.set_color(0, Color(color, 0.55))
	grad.set_color(1, Color(color, 0.0))
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	p.draw_pass_1 = _dust_mesh
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = _tex_dust
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	p.material_override = mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(p)
	p.global_position = pos + n * 0.05
	p.emitting = true
	get_tree().create_timer(1.3).timeout.connect(p.queue_free)


func _process_for(kind: String, n: Vector3, dir: Vector3) -> ParticleProcessMaterial:
	var spec: Dictionary = FX[kind]
	var pm := ParticleProcessMaterial.new()
	# осколки летят от поверхности, чуть в сторону рикошета
	pm.direction = (n * 1.0 + dir.bounce(n) * 0.5).normalized()
	pm.spread = 55.0
	pm.initial_velocity_min = float(spec.speed[0])
	pm.initial_velocity_max = float(spec.speed[1])
	pm.gravity = Vector3(0, float(spec.gravity), 0)
	pm.scale_min = float(spec.size) * 0.6
	pm.scale_max = float(spec.size) * 1.4
	pm.angular_velocity_min = -360.0
	pm.angular_velocity_max = 360.0
	pm.damping_min = 0.5
	pm.damping_max = 1.5
	var grad := Gradient.new()
	grad.set_color(0, spec.colors[0])
	grad.set_color(1, spec.colors[1])
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_initial_ramp = gt
	return pm


func _flash(parent: Node, pos: Vector3, color: Color) -> void:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = 3.0
	l.omni_range = 2.5
	parent.add_child(l)
	l.global_position = pos
	get_tree().create_timer(0.05).timeout.connect(l.queue_free)


# ---------------------------------------------------------------- взрыв

## Взрыв гранаты: вспышка света, огненный шар, клубы дыма, разлёт крошки, подпалина на полу.
func explosion(pos: Vector3) -> void:
	var parent := get_tree().current_scene
	if parent == null:
		return
	var light := OmniLight3D.new()
	light.light_color = Color(1.0, 0.72, 0.4)
	light.light_energy = 18.0
	light.omni_range = 14.0
	light.shadow_enabled = true
	parent.add_child(light)
	light.global_position = pos + Vector3.UP * 0.6
	var tw := light.create_tween()
	tw.tween_property(light, "light_energy", 0.0, 0.4).set_ease(Tween.EASE_OUT)
	tw.tween_callback(light.queue_free)
	# огненный шар: яркие мягкие пятна, быстро раздуваются и темнеют
	_puffs(parent, pos, 26, 0.55, Vector2(2.5, 7.0), Vector2(0.9, 1.6), 3.2, 2.0,
		[Color(1.0, 0.95, 0.75, 1.0), Color(1.0, 0.55, 0.15, 0.9), Color(0.25, 0.15, 0.1, 0.0)], true)
	# дым: медленно поднимается и расползается
	_puffs(parent, pos + Vector3.UP * 0.3, 20, 2.8, Vector2(0.6, 2.2), Vector2(1.4, 2.4), 4.5, -0.6,
		[Color(0.35, 0.33, 0.3, 0.0), Color(0.3, 0.29, 0.27, 0.55), Color(0.4, 0.39, 0.37, 0.0)], false)
	# крошка и осколки во все стороны
	var chips := GPUParticles3D.new()
	chips.one_shot = true
	chips.explosiveness = 1.0
	chips.amount = 40
	chips.lifetime = 1.1
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 80.0
	pm.initial_velocity_min = 5.0
	pm.initial_velocity_max = 14.0
	pm.gravity = Vector3(0, -9.8, 0)
	pm.scale_min = 0.03
	pm.scale_max = 0.08
	pm.angular_velocity_min = -540.0
	pm.angular_velocity_max = 540.0
	pm.color = Color(0.3, 0.28, 0.25)
	chips.process_material = pm
	chips.draw_pass_1 = _chip_mesh
	var cm := StandardMaterial3D.new()
	cm.vertex_color_use_as_albedo = true
	chips.material_override = cm
	parent.add_child(chips)
	chips.global_position = pos
	chips.emitting = true
	get_tree().create_timer(1.6).timeout.connect(chips.queue_free)
	# подпалина
	var world: World3D = (parent as Node3D).get_world_3d()
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.5, pos + Vector3.DOWN * 2.0, Hitscan.LAYER_WORLD)
	var floor_hit: Dictionary = world.direct_space_state.intersect_ray(q)
	if not floor_hit.is_empty():
		_place_decal(parent, _tex_splat, floor_hit.position, floor_hit.normal, _rng.randf_range(2.8, 3.6), Color(0.04, 0.035, 0.03, 0.85))


## Облако мягких билбордов: огонь (светится, не отбрасывает тень) или дым.
func _puffs(parent: Node, pos: Vector3, amount: int, life: float, speed: Vector2, scale: Vector2, grow: float, lift: float, colors: Array, glow: bool) -> void:
	var p := GPUParticles3D.new()
	p.one_shot = true
	p.explosiveness = 0.9
	p.amount = amount
	p.lifetime = life
	var pm := ParticleProcessMaterial.new()
	pm.direction = Vector3.UP
	pm.spread = 180.0
	pm.initial_velocity_min = speed.x
	pm.initial_velocity_max = speed.y
	pm.gravity = Vector3(0, lift, 0)
	pm.damping_min = 3.0
	pm.damping_max = 5.0
	pm.scale_min = scale.x
	pm.scale_max = scale.y
	var sc := Curve.new()
	sc.add_point(Vector2(0, 0.4))
	sc.add_point(Vector2(1, grow / 2.0))
	var sct := CurveTexture.new()
	sct.curve = sc
	pm.scale_curve = sct
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.35, 1.0])
	grad.colors = PackedColorArray(colors)
	var gt := GradientTexture1D.new()
	gt.gradient = grad
	pm.color_ramp = gt
	p.process_material = pm
	p.draw_pass_1 = _dust_mesh
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	mat.albedo_texture = _tex_dust
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	if glow:
		mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	p.material_override = mat
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(p)
	p.global_position = pos
	p.emitting = true
	get_tree().create_timer(life + 0.5).timeout.connect(p.queue_free)


# ---------------------------------------------------------------- кровь

func _blood(parent: Node, pos: Vector3, dir: Vector3, body: Object) -> void:
	# брызги — по ходу пули (выходное) и чуть назад
	_particles(parent, "flesh", pos, dir, dir)
	if body is Marauder:
		(body as Marauder).hit_flash()
	# пятно на полу под точкой попадания
	var world: World3D = (get_tree().current_scene as Node3D).get_world_3d()
	var down := PhysicsRayQueryParameters3D.create(pos, pos + Vector3.DOWN * 3.0, Hitscan.LAYER_WORLD)
	var floor_hit: Dictionary = world.direct_space_state.intersect_ray(down)
	if not floor_hit.is_empty():
		_place_decal(parent, _tex_splat, floor_hit.position, floor_hit.normal, _rng.randf_range(0.7, 1.2), Color(0.35, 0.02, 0.02, 0.9))
	# пятно на стене позади — по направлению пули
	var behind := PhysicsRayQueryParameters3D.create(pos, pos + dir * 3.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	var wall_hit: Dictionary = world.direct_space_state.intersect_ray(behind)
	if not wall_hit.is_empty():
		_place_decal(parent, _tex_splat, wall_hit.position, wall_hit.normal, _rng.randf_range(0.45, 0.7), Color(0.4, 0.03, 0.03, 0.85))


# ---------------------------------------------------------------- декали

func _decal(parent: Node, kind: String, pos: Vector3, n: Vector3) -> void:
	match kind:
		"glass":
			# Декали не ложатся на прозрачное — трещина на стекле как наклейка-квад.
			_place_sticker(parent, _tex_crack, pos, n, _rng.randf_range(0.55, 0.75), Color(0.92, 0.96, 1.0, 0.85))
		"fabric", "cardboard":
			_place_decal(parent, _tex_hole, pos, n, _rng.randf_range(0.12, 0.16), Color(0.1, 0.08, 0.06, 0.9))
		"metal":
			_place_decal(parent, _tex_hole, pos, n, _rng.randf_range(0.14, 0.18), Color(0.15, 0.13, 0.1, 0.95))
		_:
			_place_decal(parent, _tex_hole, pos, n, _rng.randf_range(0.2, 0.28), Color(0.2, 0.18, 0.16, 0.95))


## Декаль проецируется вдоль своей -Y: ставим Y по нормали, случайный поворот вокруг неё.
func _place_decal(parent: Node, tex: Texture2D, pos: Vector3, n: Vector3, size: float, tint: Color) -> void:
	var d := Decal.new()
	d.texture_albedo = tex
	d.modulate = tint
	d.albedo_mix = 1.0
	d.size = Vector3(size, 0.35, size)
	d.cull_mask = 1
	d.normal_fade = 0.3
	var up := n.normalized()
	var x := up.cross(Vector3.FORWARD if absf(up.dot(Vector3.FORWARD)) < 0.9 else Vector3.RIGHT).normalized()
	var z := x.cross(up).normalized()
	var basis := Basis(x, up, z).rotated(up, _rng.randf_range(0.0, TAU))
	parent.add_child(d)
	d.global_transform = Transform3D(basis, pos + up * 0.01)
	_decals.append(d)
	while _decals.size() > MAX_DECALS:
		var old: Decal = _decals.pop_front()
		if is_instance_valid(old):
			old.queue_free()


## Наклейка на прозрачной поверхности: квад с текстурой чуть перед точкой попадания, с обеих сторон.
func _place_sticker(parent: Node, tex: Texture2D, pos: Vector3, n: Vector3, size: float, tint: Color) -> void:
	var mi := MeshInstance3D.new()
	var quad := QuadMesh.new()
	quad.size = Vector2(size, size)
	mi.mesh = quad
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_texture = tex
	m.albedo_color = tint
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mi.material_override = m
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(mi)
	# квад смотрит по +Z: разворачиваем Z по нормали, случайный поворот вокруг неё
	var up := n.normalized()
	mi.global_transform = Transform3D(Basis.looking_at(-up, Vector3.UP if absf(up.dot(Vector3.UP)) < 0.9 else Vector3.RIGHT).rotated(up, _rng.randf_range(0.0, TAU)), pos + up * 0.015)
	_stickers.append(mi)
	while _stickers.size() > MAX_DECALS / 4:
		var old: MeshInstance3D = _stickers.pop_front()
		if is_instance_valid(old):
			old.queue_free()


# ---------------------------------------------------------------- текстуры

func _make_hole_texture(size: int) -> Texture2D:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var c := size * 0.5
	for y in range(size):
		for x in range(size):
			var r := Vector2(x - c, y - c).length() / c
			var edge := r + _rng.randf_range(-0.08, 0.08)
			var a := clampf(1.0 - smoothstep(0.35, 0.95, edge), 0.0, 1.0)
			var core := 1.0 - smoothstep(0.0, 0.45, r)
			var v := lerpf(0.35, 0.02, core)
			img.set_pixel(x, y, Color(v, v, v, a))
	return ImageTexture.create_from_image(img)


func _make_crack_texture(size: int) -> Texture2D:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 1, 1, 0))
	var c := Vector2(size * 0.5, size * 0.5)
	# лучи от центра с изломами
	for k in range(9):
		var ang := k * TAU / 9.0 + _rng.randf_range(-0.2, 0.2)
		var p := c
		var len := _rng.randf_range(size * 0.28, size * 0.5)
		var steps := 24
		for i in range(steps):
			var q := p + Vector2(cos(ang), sin(ang)) * (len / steps)
			ang += _rng.randf_range(-0.25, 0.25)
			_line(img, p, q, Color(1, 1, 1, 0.9 - float(i) / steps * 0.6))
			p = q
	# центр — паутина
	for y in range(size):
		for x in range(size):
			var r := (Vector2(x, y) - c).length() / (size * 0.5)
			if r < 0.12:
				var px := img.get_pixel(x, y)
				img.set_pixel(x, y, Color(1, 1, 1, maxf(px.a, 1.0 - r / 0.12)))
	return ImageTexture.create_from_image(img)


func _make_splat_texture(size: int) -> Texture2D:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 1, 1, 0))
	var c := Vector2(size * 0.5, size * 0.5)
	# основное пятно + капли вокруг
	var blobs: Array[Vector3] = [Vector3(c.x, c.y, size * 0.28)]
	for i in range(14):
		var ang := _rng.randf_range(0.0, TAU)
		var dist := _rng.randf_range(size * 0.15, size * 0.45)
		blobs.append(Vector3(c.x + cos(ang) * dist, c.y + sin(ang) * dist, _rng.randf_range(size * 0.03, size * 0.1)))
	for y in range(size):
		for x in range(size):
			var a := 0.0
			for b in blobs:
				var r := Vector2(x - b.x, y - b.y).length() / b.z
				a = maxf(a, 1.0 - smoothstep(0.7, 1.0, r + _rng.randf_range(-0.05, 0.05)))
			img.set_pixel(x, y, Color(1, 1, 1, a))
	return ImageTexture.create_from_image(img)


func _make_soft_texture(size: int) -> Texture2D:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var c := size * 0.5
	for y in range(size):
		for x in range(size):
			var r := Vector2(x - c, y - c).length() / c
			img.set_pixel(x, y, Color(1, 1, 1, clampf(1.0 - smoothstep(0.2, 1.0, r), 0.0, 1.0)))
	return ImageTexture.create_from_image(img)


func _line(img: Image, a: Vector2, b: Vector2, col: Color) -> void:
	var steps := int(maxf(1.0, a.distance_to(b)))
	for i in range(steps + 1):
		var p := a.lerp(b, float(i) / steps)
		var x := int(p.x)
		var y := int(p.y)
		if x >= 0 and y >= 0 and x < img.get_width() and y < img.get_height():
			img.set_pixel(x, y, col)
