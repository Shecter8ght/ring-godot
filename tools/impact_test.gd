extends Node3D
## Проверяет реальный луч, профили поверхностей, неизвестный тип, запасные текстуры и очистку очереди.

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	var body: StaticBody3D = StaticBody3D.new()
	var collision: CollisionShape3D = CollisionShape3D.new()
	var box: BoxShape3D = BoxShape3D.new()
	box.size = Vector3(4, 4, 0.2)
	collision.shape = box
	body.add_child(collision)
	add_child(body)
	await get_tree().physics_frame
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	for kind: String in Balance.IMPACT_SURFACES:
		body.set_meta("surface", kind)
		var hit: Dictionary = Hitscan.fire(get_world_3d(), Vector3(0, 0, 2), Vector3.FORWARD, 0, 4, Hitscan.LAYER_WORLD, 0, [], rng)
		_check(hit.has("position"), "%s: луч попал" % kind)
		var burst: ImpactBurst = ImpactFx._bursts.back() as ImpactBurst
		_check(burst != null and burst.debris.emitting, "%s: частицы" % kind)
		_check(burst.sparks.emitting == (kind == "metal"), "%s: искры только металлу" % kind)
		_check(burst.dust.emitting == (int(Balance.IMPACT_SURFACES[kind].dust) > 0), "%s: пыль по материалу" % kind)
		_check(burst.debris.direction.dot(Vector3.BACK) > 0 if kind != "flesh" else burst.debris.direction.dot(Vector3.FORWARD) > 0, "%s: направление выброса" % kind)
	body.set_meta("surface", "not_a_material")
	Hitscan.fire(get_world_3d(), Vector3(0, 0, 2), Vector3.FORWARD, 0, 4, Hitscan.LAYER_WORLD, 0, [], rng)
	_check(is_instance_valid(ImpactFx._bursts.back()), "неизвестная поверхность использует бетон")
	var saved_textures: Dictionary = ImpactFx._decal_textures
	ImpactFx._decal_textures = {}
	for kind: String in ["concrete", "wood", "metal"]:
		ImpactFx._decal(self, kind, Vector3.ZERO, Vector3.BACK)
		var decal: Decal = ImpactFx._decals.back()
		_check(decal.texture_albedo != null and decal.texture_albedo.resource_path == "" and decal.texture_normal == null, "%s: процедурный запасной вариант" % kind)
	ImpactFx._decal_textures = saved_textures
	for normal: Vector3 in [Vector3.UP, Vector3.DOWN, Vector3.RIGHT]:
		ImpactFx._particles(self, "concrete", Vector3.ZERO, normal, -normal)
		var burst: ImpactBurst = ImpactFx._bursts.back() as ImpactBurst
		_check(burst.debris.direction.dot(normal) > 0 and burst.debris.gravity.y < 0, "выброс наружу, гравитация вниз: %s" % normal)
	for index: int in range(Balance.IMPACT_MAX_BURSTS + 10):
		ImpactFx._particles(self, "metal", Vector3.ZERO, Vector3.BACK, Vector3.FORWARD)
	_check(ImpactFx._bursts.size() <= Balance.IMPACT_MAX_BURSTS, "лимит одновременных выбросов")
	await get_tree().create_timer(1.5).timeout
	var active: int = 0
	for child: Node in get_children():
		if child is ImpactBurst:
			active += 1
	_check(active == 0, "одноразовые эффекты освобождены")
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


func _check(ok: bool, label: String) -> void:
	if not ok:
		_fails += 1
		push_error(label)
