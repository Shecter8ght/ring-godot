extends Node3D
## Проверяет реальный луч, слои выброса по поверхностям, пол под точкой удара и маленькую верхнюю
## грань, землю района по маске (surface_map), неизвестный тип, запасные текстуры и очистку очереди.

var _fails: int = 0


## Земля района для Surfaces: отвечает по точке, как DistrictTerrain.surface_at.
class FakeTerrain:
	extends Node

	func surface_at(pos: Vector3, normal: Vector3) -> String:
		if normal.y < 0.5:
			return "gravel"
		return "mud" if pos.x > 0.0 else "grass"


func _ready() -> void:
	await get_tree().process_frame
	var body: StaticBody3D = _body(Vector3.ZERO, Vector3(4, 4, 0.2))
	# пол под стеной и маленький стол перед ней
	_body(Vector3(0, -3.0, 0), Vector3(20, 2, 20))
	var table: StaticBody3D = _body(Vector3(5, 0.0, 0), Vector3(1.0, 0.1, 1.0))
	await get_tree().physics_frame
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	for kind: String in Balance.IMPACT_SURFACES:
		var spec: Dictionary = Balance.IMPACT_SURFACES[kind]
		body.set_meta("surface", kind)
		var hit: Dictionary = Hitscan.fire(get_world_3d(), Vector3(0, 0, 2), Vector3.FORWARD, 0, 4, Hitscan.LAYER_WORLD, 0, [], rng)
		_check(hit.has("position"), "%s: луч попал" % kind)
		var burst: ImpactBurst = ImpactFx._bursts.back() as ImpactBurst
		_check(burst != null and burst.debris.emitting, "%s: куски" % kind)
		if burst == null:
			continue
		if kind == "metal":
			_check(burst.sparks.emitting and burst.flash.visible, "металл: искры и вспышка")
		if not spec.has("sparks"):
			_check(not burst.sparks.emitting, "%s: без искр" % kind)
		_check(burst.dust.emitting == spec.has("dust"), "%s: пыль по материалу" % kind)
		_check(burst.spray.emitting == spec.has("spray"), "%s: веер по материалу" % kind)
		_check(burst.bits.emitting == spec.has("bits"), "%s: мелочь по материалу" % kind)
		var aim: Vector3 = burst.aims.get("debris", Vector3.ZERO)
		_check(aim.dot(Vector3.BACK) > 0 if kind != "flesh" else aim.dot(Vector3.FORWARD) > 0, "%s: направление выброса" % kind)
		var mat: ShaderMaterial = burst.debris.process_material as ShaderMaterial
		var floor_plane: Vector4 = mat.get_shader_parameter("plane_b")
		if kind == "flesh":
			_check(floor_plane == ImpactBurst.NO_PLANE, "кровь: без отскока")
		else:
			_check(is_equal_approx(floor_plane.w, -2.0) and floor_plane.y > 0.99, "%s: пол под стеной найден" % kind)
	body.set_meta("surface", "not_a_material")
	Hitscan.fire(get_world_3d(), Vector3(0, 0, 2), Vector3.FORWARD, 0, 4, Hitscan.LAYER_WORLD, 0, [], rng)
	_check(is_instance_valid(ImpactFx._bursts.back()), "неизвестная поверхность использует бетон")
	# пол широкий — куски лежат на нём везде; стол маленький — куски падают с него на пол
	var on_floor: Array = ImpactFx._ground(self, Vector3(2.5, -2.0, 3.0), Vector3.UP, Vector3(0.3, -1, -0.3).normalized())
	_check(float(on_floor[1]) >= ImpactBurst.NO_RADIUS and is_equal_approx((on_floor[0] as Vector4).w, -2.0), "пол: опора везде")
	var on_table: Array = ImpactFx._ground(self, Vector3(5, 0.05, 0), Vector3.UP, Vector3(0.3, -1, 0).normalized())
	_check(float(on_table[1]) < 1.0 and is_equal_approx((on_table[0] as Vector4).w, -2.0), "стол: куски падают на пол")
	table.free()
	# земля района отвечает сама: грязь, газон, камень на склоне
	var ground: StaticBody3D = _body(Vector3(0, 0, 10), Vector3(4, 0.2, 4))
	var terrain: FakeTerrain = FakeTerrain.new()
	add_child(terrain)
	ground.set_meta("surface", "grass")
	ground.set_meta("surface_map", terrain)
	_check(Surfaces.kind_at({"collider": ground, "position": Vector3(1, 0, 10), "normal": Vector3.UP}) == "mud", "маска: грязь")
	_check(Surfaces.kind_at({"collider": ground, "position": Vector3(-1, 0, 10), "normal": Vector3.UP}) == "grass", "маска: газон")
	_check(Surfaces.kind_at({"collider": ground, "position": Vector3(1, 0, 10), "normal": Vector3(0, 0.3, 0.95)}) == "gravel", "маска: склон")
	GrassTrample.hit(Vector3.ZERO, 0.3)
	var saved_textures: Dictionary = ImpactFx._decal_textures
	ImpactFx._decal_textures = {}
	for kind: String in ["concrete", "wood", "metal", "grass"]:
		ImpactFx._decal(self, kind, Vector3.ZERO, Vector3.BACK)
		var decal: Decal = ImpactFx._decals.back()
		_check(decal.texture_albedo != null and decal.texture_albedo.resource_path == "" and decal.texture_normal == null, "%s: процедурный запасной вариант" % kind)
	ImpactFx._decal_textures = saved_textures
	_check(not (ImpactFx._decal_textures.get("soil", []) as Array).is_empty(), "воронки в грунте загружены")
	for normal: Vector3 in [Vector3.UP, Vector3.DOWN, Vector3.RIGHT]:
		ImpactFx._particles(self, "concrete", Vector3.ZERO, normal, -normal)
		var burst: ImpactBurst = ImpactFx._bursts.back() as ImpactBurst
		var mat: ShaderMaterial = burst.debris.process_material as ShaderMaterial
		_check((burst.aims.debris as Vector3).dot(normal) > 0 and float(mat.get_shader_parameter("gravity")) > 0.0, "выброс наружу, тяжесть вниз: %s" % normal)
	for index: int in range(Balance.IMPACT_MAX_BURSTS + 10):
		ImpactFx._particles(self, "metal", Vector3.ZERO, Vector3.BACK, Vector3.FORWARD)
	_check(ImpactFx._bursts.size() <= Balance.IMPACT_MAX_BURSTS, "лимит одновременных выбросов")
	_check(ImpactBurst._lights <= int(Balance.IMPACT_FLASH.light_max), "свет вспышек ограничен")
	var longest: float = 0.0
	for kind: String in Balance.IMPACT_SURFACES:
		for layer: String in ["debris", "bits", "spray", "dust"]:
			var spec: Dictionary = Balance.IMPACT_SURFACES[kind]
			if spec.has(layer):
				longest = maxf(longest, (spec[layer].life as Vector2).y)
	await get_tree().create_timer(longest + Balance.IMPACT_CLEANUP_MARGIN + 0.5).timeout
	var active: int = 0
	for child: Node in get_children():
		if child is ImpactBurst:
			active += 1
	_check(active == 0, "одноразовые эффекты освобождены")
	_check(ImpactBurst._lights == 0, "свет вспышек погас")
	# Старый уровень удалён, но autoload и его очередь остались. Затем очередь снова заполняется.
	var old_level: Node3D = Node3D.new()
	add_child(old_level)
	for index: int in range(Balance.IMPACT_MAX_DECALS):
		ImpactFx._place_decal(old_level, ImpactFx._tex_hole, Vector3.ZERO, Vector3.UP, 0.1, Color.WHITE)
	old_level.free()
	for index: int in range(Balance.IMPACT_MAX_DECALS + 1):
		ImpactFx._place_decal(self, ImpactFx._tex_hole, Vector3.ZERO, Vector3.UP, 0.1, Color.WHITE)
	_check(ImpactFx._decals.size() == Balance.IMPACT_MAX_DECALS, "очередь декалей после удаления уровня")
	for index: int in range(ImpactFx._decals.size()):
		_check(is_instance_valid(ImpactFx._decals[index]), "в очереди нет удалённых декалей")
	var old_stickers: Node3D = Node3D.new()
	add_child(old_stickers)
	ImpactFx._place_sticker(old_stickers, ImpactFx._tex_hole, Vector3.ZERO, Vector3.UP, 0.1, Color.WHITE)
	old_stickers.free()
	ImpactFx._place_sticker(self, ImpactFx._tex_hole, Vector3.ZERO, Vector3.UP, 0.1, Color.WHITE)
	_check(ImpactFx._stickers.size() == 1 and is_instance_valid(ImpactFx._stickers[0]), "наклейки после удаления уровня")
	print("impact_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _body(pos: Vector3, size: Vector3) -> StaticBody3D:
	var body: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = size
	collision.shape = box
	body.add_child(collision)
	body.position = pos
	add_child(body)
	return body


func _check(ok: bool, label: String) -> void:
	if not ok:
		_fails += 1
		push_error(label)
