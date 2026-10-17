extends Node
## Эффекты попаданий: выброс слоями по виду поверхности (ImpactBurst), декали (отверстия, трещины,
## воронки в грунте, кровь), звук удара; по траве пятно вокруг ложится (GrassTrample). Autoload
## `ImpactFx`. Декали — CC0 и свои из assets/textures/impacts (tools/import_impact_decals.py,
## tools/gen_impact_soil.py); если ассетов нет, остаётся процедурный запасной вариант.

## Сколько декалей держим в мире — старые убираются.
const MAX_DECALS: int = Balance.IMPACT_MAX_DECALS
const BURST_SCENE: PackedScene = preload("res://scenes/combat/impact_burst.tscn")
const DECAL_DIR := "res://assets/textures/impacts"
const DECAL_COUNTS := {"concrete": 1, "metal": 8, "wood": 8, "soil": 4}

## Звук удара по виду поверхности.
const SOUND := {
	"concrete": "impact_hard", "tile": "impact_ceramic", "asphalt": "impact_dirt", "metal": "impact_metal",
	"glass": "impact_glass", "wood": "impact_soft", "cardboard": "impact_soft", "fabric": "impact_soft",
	"plastic": "impact_soft", "flesh": "hit", "snow": "impact_dirt",
	"grass": "impact_dirt", "dirt": "impact_dirt", "mud": "impact_dirt", "gravel": "impact_dirt",
}

var _rng := RandomNumberGenerator.new()
var _decals: Array[Decal] = []
var _stickers: Array[MeshInstance3D] = []
var _tex_hole: Texture2D
var _tex_crack: Texture2D
var _tex_splat: Texture2D
var _tex_dust: Texture2D
var _decal_textures: Dictionary = {}
var _decal_normals: Dictionary = {}
var _bursts: Array[Node3D] = []
var _chip_mesh: BoxMesh
var _dust_mesh: QuadMesh
var _blood_fx: BloodFx


func _ready() -> void:
	_rng.randomize()
	_tex_hole = _make_hole_texture(64)
	_tex_crack = _make_crack_texture(96)
	_tex_splat = _make_splat_texture(128)
	_tex_dust = _make_soft_texture(48)
	_load_decal_textures()
	ImpactBurst.prepare()
	_chip_mesh = BoxMesh.new()
	_chip_mesh.size = Vector3(1, 1, 1)
	_dust_mesh = QuadMesh.new()
	_dust_mesh.size = Vector2(1, 1)
	# капли, следы, подтёки, лужи — отдельный узел (src/combat/blood_fx.gd)
	_blood_fx = BloodFx.new()
	_blood_fx.name = "Blood"
	add_child(_blood_fx)
	_blood_fx.set_fallback_splat(_tex_splat)


## Внешние ассеты необязательны: без них игра продолжает использовать процедурные следы.
func _load_decal_textures() -> void:
	for kind: String in DECAL_COUNTS:
		var albedo: Array[Texture2D] = []
		var normals: Array[Texture2D] = []
		for index: int in range(int(DECAL_COUNTS[kind])):
			var path := "%s/%s_%d.png" % [DECAL_DIR, kind, index]
			var normal_path := "%s/%s_%d_normal.png" % [DECAL_DIR, kind, index]
			if not ResourceLoader.exists(path):
				continue
			var texture := load(path) as Texture2D
			var normal := load(normal_path) as Texture2D if ResourceLoader.exists(normal_path) else null
			albedo.append(texture)
			normals.append(normal)
		_decal_textures[kind] = albedo
		_decal_normals[kind] = normals


## Точка входа: результат intersect_ray и направление пули.
func spawn_hit(hit: Dictionary, dir: Vector3) -> void:
	if hit.is_empty() or not hit.has("position"):
		return
	var kind: String = Surfaces.kind_at(hit)
	if not Balance.IMPACT_SURFACES.has(kind):
		kind = "concrete"
	var pos: Vector3 = hit.position
	var n: Vector3 = hit.get("normal", -dir)
	if n.length_squared() < 0.01:
		n = -dir
	n = n.normalized()
	if n.is_zero_approx():
		n = Vector3.UP
	var parent := get_tree().current_scene
	if parent == null:
		return
	_show_hit(parent, kind, pos, n, dir, hit.get("collider"))
	# По сети передаём только косметическое событие, без коллайдеров и повторного урона.
	if Net.is_networked():
		var scene_key: String = Net.scene_of(parent)
		if scene_key != "":
			for peer: int in multiplayer.get_peers():
				if Net.visible_in(peer, scene_key):
					_rpc_hit_fx.rpc_id(peer, scene_key, kind, pos, n, dir)


@rpc("any_peer", "call_remote", "unreliable")
func _rpc_hit_fx(scene_key: String, kind: String, pos: Vector3, n: Vector3, dir: Vector3) -> void:
	var parent: Node = get_tree().current_scene
	var sender: int = multiplayer.get_remote_sender_id()
	if parent == null or not Net.visible_in(sender, scene_key) or Net.scene_of(parent) != scene_key:
		return
	if not Balance.IMPACT_SURFACES.has(kind) or not pos.is_finite() or not n.is_finite() or not dir.is_finite():
		return
	if n.is_zero_approx() or dir.is_zero_approx():
		return
	_show_hit(parent, kind, pos, n.normalized(), dir.normalized(), null)


func _show_hit(parent: Node, kind: String, pos: Vector3, n: Vector3, dir: Vector3, body: Object) -> void:
	if kind == "flesh":
		_blood(parent, pos, dir, body)
	else:
		_particles(parent, kind, pos, n, dir)
		# на витрине след рисуют трещины самой панели (GlassPanes), а выбитая — без висящих в воздухе дыр
		if kind != "glass":
			_decal(parent, kind, pos, n)
		var spec: Dictionary = Balance.IMPACT_SURFACES[kind]
		if spec.has("trample"):
			GrassTrample.hit(pos, float(spec.trample))

	Audio.play(String(SOUND.get(kind, "impact_hard")), pos)


# ---------------------------------------------------------------- частицы

## Только выброс частиц, без следа и звука (кусок стекла разбился о пол и т. п.). У каждого peer свой.
func debris_at(kind: String, pos: Vector3, n: Vector3, dir: Vector3) -> void:
	var parent: Node = get_tree().current_scene
	if parent == null or not Balance.IMPACT_SURFACES.has(kind):
		return
	_particles(parent, kind, pos, n.normalized(), dir.normalized())


func _particles(parent: Node, kind: String, pos: Vector3, n: Vector3, dir: Vector3) -> void:
	var camera: Camera3D = get_viewport().get_camera_3d()
	if camera != null and camera.global_position.distance_to(pos) > Balance.IMPACT_MAX_DISTANCE:
		return
	# Освободившиеся эффекты не удерживаем между рейдами; очередь ограничена при дроби/автомате.
	for index: int in range(_bursts.size() - 1, -1, -1):
		if not is_instance_valid(_bursts[index]):
			_bursts.remove_at(index)
	while _bursts.size() >= Balance.IMPACT_MAX_BURSTS:
		var oldest: Node3D = _bursts.pop_front()
		if is_instance_valid(oldest):
			oldest.free()
	var far: bool = camera != null and camera.global_position.distance_to(pos) > Balance.IMPACT_LOD_M
	var floor_plane: Vector4 = ImpactBurst.NO_PLANE
	var radius: float = ImpactBurst.NO_RADIUS
	if kind != "flesh":
		var ground: Array = _ground(parent, pos, n, dir)
		floor_plane = ground[0]
		radius = ground[1]
	var burst: ImpactBurst = BURST_SCENE.instantiate() as ImpactBurst
	parent.add_child(burst)
	burst.global_position = pos + n * Balance.IMPACT_OFFSET
	burst.setup(kind, n, dir.normalized(), _rng.randi(), floor_plane, radius, far)
	_bursts.append(burst)


## Куда лягут куски: [плоскость пола под точкой удара, радиус поверхности удара]. Попали в верхнюю
## грань — есть ли опора в стороне, куда полетят куски: нет на высоте удара — грань маленькая (стол,
## капот), куски с неё падают на пол под ней.
func _ground(parent: Node, pos: Vector3, n: Vector3, dir: Vector3) -> Array:
	var cfg: Dictionary = Balance.IMPACT_FLOOR
	var world: World3D = (parent as Node3D).get_world_3d() if parent is Node3D else get_viewport().find_world_3d()
	if world == null:
		return [ImpactBurst.NO_PLANE, ImpactBurst.NO_RADIUS]
	var space: PhysicsDirectSpaceState3D = world.direct_space_state
	if n.y > 0.7:
		var side: Vector3 = Vector3(dir.x, 0.0, dir.z)
		side = side.normalized() if side.length_squared() > 0.0001 else Vector3.RIGHT
		var probe: Vector3 = pos + side * float(cfg.probe_m)
		var down: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(
			probe + Vector3.UP * float(cfg.lift_m), probe + Vector3.DOWN * float(cfg.down_m), Hitscan.LAYER_WORLD))
		if down.is_empty():
			return [ImpactBurst.NO_PLANE, float(cfg.small_radius_m)]
		var broad: bool = absf((down.position as Vector3).y - pos.y) <= float(cfg.edge_m)
		return [_plane(down), ImpactBurst.NO_RADIUS if broad else float(cfg.small_radius_m)]
	var start: Vector3 = pos + n * 0.05
	var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(
		start, start + Vector3.DOWN * float(cfg.down_m), Hitscan.LAYER_WORLD))
	return [ImpactBurst.NO_PLANE if hit.is_empty() else _plane(hit), ImpactBurst.NO_RADIUS]


static func _plane(hit: Dictionary) -> Vector4:
	var normal: Vector3 = (hit.normal as Vector3).normalized()
	return Vector4(normal.x, normal.y, normal.z, normal.dot(hit.position as Vector3))


# ---------------------------------------------------------------- взрыв

## Взрыв гранаты: вспышка света, огненный шар, клубы дыма, разлёт крошки, подпалина на полу.
func explosion(pos: Vector3) -> void:
	var parent := get_tree().current_scene
	if parent == null:
		return
	# трава вокруг ложится от взрыва
	GrassTrample.blast(pos, float(Balance.GRENADE.radius))
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
	# морось и брызги у раны — частицами; попали в себя (рана у самой камеры) — без облака в глаза
	var camera: Camera3D = get_viewport().get_camera_3d()
	if camera == null or camera.global_position.distance_to(pos) > float(Balance.BLOOD.mist_skip_m):
		_particles(parent, "flesh", pos, dir, dir)
	if body is Marauder:
		(body as Marauder).hit_flash()
	# капли летят и ложатся следами, на стене — подтёки (BloodFx)
	_blood_fx.wound(parent, pos, dir, body)


# ---------------------------------------------------------------- декали

func _decal(parent: Node, kind: String, pos: Vector3, n: Vector3) -> void:
	if kind in ["snow", "glass"]:
		return
	var spec: Dictionary = Balance.IMPACT_DECALS.get(kind, Balance.IMPACT_DECALS.concrete)
	var asset_kind: String = String(spec.asset)
	var size_range: Vector2 = spec.size
	var tint: Color = spec.tint
	var textures: Array = _decal_textures.get(asset_kind, [])
	var normals: Array = _decal_normals.get(asset_kind, [])
	if not textures.is_empty():
		var index: int = _rng.randi_range(0, textures.size() - 1)
		var normal_texture: Texture2D = normals[index] as Texture2D if index < normals.size() else null
		_place_decal(parent, textures[index] as Texture2D, pos, n, _rng.randf_range(size_range.x, size_range.y), tint, normal_texture)
	else:
		_place_decal(parent, _tex_hole, pos, n, _rng.randf_range(size_range.x, size_range.y), tint)


## Декаль проецируется вдоль своей -Y: ставим Y по нормали, случайный поворот вокруг неё.
func _place_decal(parent: Node, tex: Texture2D, pos: Vector3, n: Vector3, size: float, tint: Color, normal_tex: Texture2D = null) -> void:
	# Autoload переживает уровень, а его декали — нет. Проверяем ссылку ДО типизированного присваивания.
	for index: int in range(_decals.size() - 1, -1, -1):
		if not is_instance_valid(_decals[index]):
			_decals.remove_at(index)
	var d := Decal.new()
	d.texture_albedo = tex
	if normal_tex != null:
		d.texture_normal = normal_tex
	d.modulate = tint
	d.albedo_mix = 1.0
	d.size = Vector3(size, maxf(0.12, size * 0.6), size)
	d.cull_mask = 1
	d.normal_fade = 0.45
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
	for index: int in range(_stickers.size() - 1, -1, -1):
		if not is_instance_valid(_stickers[index]):
			_stickers.remove_at(index)
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
