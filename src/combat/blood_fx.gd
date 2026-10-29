class_name BloodFx
extends Node
## Кровь — косметика, без урона и шума для ИИ (узел ImpactFx). Каждый peer считает сам по тем
## попаданиям, что ему пришли (ImpactFx._rpc_hit_fx), и по синхронизированному состоянию раненых —
## по сети отдельно ничего не идёт; раскладка капель у разных игроков своя.
## Попадание в тело (wound): капли вылетают по ходу пули (выходное), немного — назад, тяжёлые — почти
## вниз; летят с тяжестью и сопротивлением воздуха (свои лучи по физике), где ударились — след
## (Decal): отвесно — круглый с венчиком, вскользь — вытянутый с хвостом по ходу полёта. Крупная
## капля на стене пускает подтёк — струйки стекают вниз (коробка с шейдером blood_decal, форма —
## assets/textures/blood/drips.png). Рана ещё пару секунд капает — и с бегущего тоже.
## Раненый и убитый лежат в луже: она растекается неровным краем, на уклоне — языком вниз
## (pools.png — заранее посчитанное растекание по шероховатой поверхности). Утащили раненого — за ним
## мазок, на новом месте — новая лужа; подняли — лужа перестаёт расти. Всё сохнет: темнеет и матовеет.
## Ограничения — Balance.BLOOD; всё живёт в сцене уровня и уходит вместе с ней.

const DECAL_SHADER := preload("res://src/combat/blood_decal.gdshader")
const MAPS_DIR := "res://assets/textures/blood"
## клетки атласов карт: лужи 4×2 (верхний ряд — ровно, нижний — уклон), подтёки 4×1
const POOL_COLS := 4
const DRIP_COLS := 4
## где в клетке источник (доля по v): у лужи на уклоне и у подтёка — сверху
const POOL_SLOPE_SOURCE_V := 0.24
const DRIP_SOURCE_V := 0.086

static var current: BloodFx

var _rng := RandomNumberGenerator.new()
## часы крови (с): по ним растут лужи и сохнут следы; идут с игровым временем
var _clock: float = 0.0
## Для проверок: во сколько раз быстрее идут часы крови (физика и игра — как обычно).
var time_k: float = 1.0
var _drop_pos := PackedVector3Array()
var _drop_vel := PackedVector3Array()
var _drop_size := PackedFloat32Array()
var _drop_age := PackedFloat32Array()
var _drop_mmi: MultiMeshInstance3D
var _drop_mat: StandardMaterial3D
var _drop_mesh: SphereMesh
## следы капель: [Decal, когда, высох ли]
var _splats: Array = []
## лужи и подтёки — коробки с шейдером
var _boxes: Array[MeshInstance3D] = []
var _box_mesh: BoxMesh
var _pool_mat: ShaderMaterial
var _drip_mat: ShaderMaterial
var _spatter: Array[Texture2D] = []
var _spatter_n: Array[Texture2D] = []
var _orm: Texture2D
var _fallback_splat: Texture2D
## раненые и убитые: узел → {since, pool, center, last, still}
var _bodies: Dictionary = {}
## рана ещё капает: {node, off, until, next}
var _bleeders: Array = []
var _scan_t: float = 0.0
var _dry_t: float = 0.0


func _ready() -> void:
	current = self
	_rng.randomize()
	_box_mesh = BoxMesh.new()
	_box_mesh.size = Vector3.ONE
	_drop_mesh = SphereMesh.new()
	_drop_mesh.radius = 0.5
	_drop_mesh.height = 1.0
	_drop_mesh.radial_segments = 8
	_drop_mesh.rings = 4
	_drop_mat = StandardMaterial3D.new()
	_drop_mat.albedo_color = Color(0.2, 0.008, 0.006)
	_drop_mat.roughness = 0.12
	_drop_mat.metallic_specular = 0.7
	_drop_mesh.material = _drop_mat
	var noise := NoiseTexture2D.new()
	noise.seamless = true
	noise.width = 128
	noise.height = 128
	noise.noise = FastNoiseLite.new()
	_pool_mat = _make_box_mat("pools.png", noise)
	_drip_mat = _make_box_mat("drips.png", noise)
	for i in range(8):
		var p := "%s/spatter_%d.png" % [MAPS_DIR, i]
		var pn := "%s/spatter_%d_n.png" % [MAPS_DIR, i]
		if ResourceLoader.exists(p):
			_spatter.append(load(p) as Texture2D)
			_spatter_n.append(load(pn) as Texture2D if ResourceLoader.exists(pn) else null)
	if ResourceLoader.exists(MAPS_DIR + "/spatter_orm.png"):
		_orm = load(MAPS_DIR + "/spatter_orm.png") as Texture2D


func _make_box_mat(file: String, noise: Texture2D) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = DECAL_SHADER
	var path := MAPS_DIR + "/" + file
	var has := ResourceLoader.exists(path)
	m.set_shader_parameter("has_maps", has)
	if has:
		m.set_shader_parameter("maps", load(path) as Texture2D)
	m.set_shader_parameter("fallback_noise", noise)
	return m


## Без своих ассетов — запасной след (ImpactFx рисует его кодом).
## Материалы крови (капли, лужи, подтёки) — для разогрева шейдеров под экраном загрузки.
func warm_materials() -> Array[Material]:
	return [_drop_mat, _pool_mat, _drip_mat]


func set_fallback_splat(tex: Texture2D) -> void:
	_fallback_splat = tex


func clock() -> float:
	return _clock


# ---------------------------------------------------------------- попадание

## Попадание в тело: pos — куда, dir — ход пули, body — в кого (может быть null — по сети).
func wound(parent: Node, pos: Vector3, dir: Vector3, body: Object) -> void:
	var cfg: Dictionary = Balance.BLOOD
	var d := dir.normalized() if dir.length() > 0.001 else Vector3.FORWARD
	var n: int = _rng.randi_range((cfg.drops as Vector2i).x, (cfg.drops as Vector2i).y)
	for i in range(n):
		var exit := _rng.randf() < float(cfg.exit_share)
		var axis := d if exit else -d
		var spread := float(cfg.exit_spread) if exit else float(cfg.back_spread)
		var sp: Vector2 = cfg.exit_speed if exit else cfg.back_speed
		var v := _cone(axis, spread) * _rng.randf_range(sp.x, sp.y)
		var sz: Vector2 = cfg.drop_size
		var size := lerpf(sz.x, sz.y, pow(_rng.randf(), 1.8)) * (1.0 if exit else 0.6)
		_spawn_drop(parent, pos + axis * 0.04, v, size)
	# тяжёлые: вываливаются из раны почти вниз, чуть вперёд
	var g: Vector2i = cfg.gush
	for i in range(_rng.randi_range(g.x, g.y)):
		var gs: Vector2 = cfg.gush_speed
		var v := (_cone(d, 50.0) * 0.6 + Vector3.DOWN * 0.4).normalized() * _rng.randf_range(gs.x, gs.y)
		var gz: Vector2 = cfg.gush_size
		_spawn_drop(parent, pos, v, _rng.randf_range(gz.x, gz.y))
	# рана капает, пока тело движется — дорожка капель
	if body is Node3D and (body as Node3D).is_inside_tree() and _bleeders.size() < int(cfg.max_bleeders):
		var b := body as Node3D
		var bs: Vector2 = cfg.bleed_sec
		_bleeders.append({"node": weakref(b), "off": b.to_local(pos), "until": _clock + _rng.randf_range(bs.x, bs.y), "next": _clock + 0.2})


## Случайное направление в конусе полуугла deg вокруг axis.
func _cone(axis: Vector3, deg: float) -> Vector3:
	var a := axis.normalized()
	var side := a.cross(Vector3.UP)
	if side.length() < 0.01:
		side = a.cross(Vector3.RIGHT)
	side = side.normalized()
	var tilt := deg_to_rad(deg) * sqrt(_rng.randf())
	return a.rotated(side, tilt).rotated(a, _rng.randf() * TAU).normalized()


func _spawn_drop(parent: Node, pos: Vector3, vel: Vector3, size: float) -> void:
	if _drop_pos.size() >= int(Balance.BLOOD.max_drops):
		return
	_ensure_drop_mmi(parent)
	_drop_pos.append(pos)
	_drop_vel.append(vel)
	_drop_size.append(size)
	_drop_age.append(0.0)


func _ensure_drop_mmi(parent: Node) -> void:
	if is_instance_valid(_drop_mmi) and _drop_mmi.is_inside_tree():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = _drop_mesh
	mm.instance_count = int(Balance.BLOOD.max_drops)
	mm.visible_instance_count = 0
	_drop_mmi = MultiMeshInstance3D.new()
	_drop_mmi.name = "BloodDrops"
	_drop_mmi.multimesh = mm
	_drop_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_drop_mmi.extra_cull_margin = 16384.0
	parent.add_child(_drop_mmi)


# ---------------------------------------------------------------- полёт капель

func _physics_process(delta: float) -> void:
	_tick_bleeders()
	if _drop_pos.is_empty():
		if is_instance_valid(_drop_mmi):
			_drop_mmi.multimesh.visible_instance_count = 0
		return
	if not is_instance_valid(_drop_mmi) or not _drop_mmi.is_inside_tree():
		_clear_drops()
		return
	var cfg: Dictionary = Balance.BLOOD
	var space := _drop_mmi.get_world_3d().direct_space_state
	var g := Vector3.DOWN * float(cfg.gravity)
	var drag := float(cfg.drag)
	var life := float(cfg.drop_life)
	var i := 0
	while i < _drop_pos.size():
		var p := _drop_pos[i]
		var v := _drop_vel[i] + g * delta
		v *= maxf(0.0, 1.0 - drag * delta)
		var q := p + v * delta
		var ray := PhysicsRayQueryParameters3D.create(p, q, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
		var hit := space.intersect_ray(ray)
		_drop_age[i] += delta
		if not hit.is_empty():
			_land(hit, v, _drop_size[i])
			_remove_drop(i)
			continue
		if _drop_age[i] > life:
			_remove_drop(i)
			continue
		_drop_pos[i] = q
		_drop_vel[i] = v
		i += 1
	_draw_drops()


func _remove_drop(i: int) -> void:
	var last := _drop_pos.size() - 1
	_drop_pos[i] = _drop_pos[last]
	_drop_vel[i] = _drop_vel[last]
	_drop_size[i] = _drop_size[last]
	_drop_age[i] = _drop_age[last]
	_drop_pos.resize(last)
	_drop_vel.resize(last)
	_drop_size.resize(last)
	_drop_age.resize(last)


func _clear_drops() -> void:
	_drop_pos.clear()
	_drop_vel.clear()
	_drop_size.clear()
	_drop_age.clear()


## Капли в полёте — вытянуты по скорости (глаз видит смазанную каплю, а не шарик).
func _draw_drops() -> void:
	var mm := _drop_mmi.multimesh
	var k := float(Balance.BLOOD.drop_visual_k)
	var stretch := float(Balance.BLOOD.stretch_k)
	for i in range(_drop_pos.size()):
		var v := _drop_vel[i]
		var y := v.normalized() if v.length() > 0.01 else Vector3.DOWN
		var x := y.cross(Vector3.UP if absf(y.y) < 0.95 else Vector3.RIGHT).normalized()
		var z := x.cross(y)
		var s := _drop_size[i] * 2.0 * k
		mm.set_instance_transform(i, Transform3D(Basis(x * s, y * s * (1.0 + v.length() * stretch), z * s), _drop_pos[i]))
	mm.visible_instance_count = _drop_pos.size()


## Капля ударилась: след по углу удара; крупная на стене — подтёк.
func _land(hit: Dictionary, vel: Vector3, size: float) -> void:
	var cfg: Dictionary = Balance.BLOOD
	if size < float(cfg.splat_min_drop):
		return
	if Surfaces.kind_at(hit) == "glass":
		return
	var parent := _drop_mmi.get_parent()
	var n: Vector3 = (hit.normal as Vector3).normalized()
	var p: Vector3 = hit.position
	var speed := vel.length()
	var along := vel - n * vel.dot(n)
	var sin_a := absf(vel.dot(n)) / maxf(speed, 0.001)
	var elong := clampf(1.0 / maxf(sin_a, 0.28), 1.0, float(cfg.max_elong))
	var oblique := elong > 1.45 and along.length() > 0.05
	var base := clampf(size * float(cfg.splat_k) * (1.0 + speed * 0.1), float(cfg.splat_size.x), float(cfg.splat_size.y))
	var tangent := along.normalized() if along.length() > 0.001 else _any_tangent(n)
	var variant := -1
	if not _spatter.is_empty():
		var half := _spatter.size() / 2
		variant = (half + _rng.randi() % half) if oblique else _rng.randi() % maxi(half, 1)
	_splat(parent, p, n, tangent, Vector2(base * (elong if oblique else 1.0), base), variant)
	# крупная капля на отвесной стене стекает
	if absf(n.y) < 0.5 and size >= float(cfg.drip_min_drop) and _rng.randf() < float(cfg.drip_chance):
		drip(parent, p, n, size)


func _any_tangent(n: Vector3) -> Vector3:
	var t := n.cross(Vector3.UP if absf(n.y) < 0.9 else Vector3.RIGHT).normalized()
	return t.rotated(n, _rng.randf() * TAU)


## След капли — Decal: X — по ходу полёта (хвост вытянутого следа), Y — нормаль.
func _splat(parent: Node, p: Vector3, n: Vector3, tangent: Vector3, size: Vector2, variant: int) -> void:
	var cfg: Dictionary = Balance.BLOOD
	_prune_splats()
	var d := Decal.new()
	if variant >= 0:
		d.texture_albedo = _spatter[variant]
		if _spatter_n[variant] != null:
			d.texture_normal = _spatter_n[variant]
		if _orm:
			d.texture_orm = _orm
	elif _fallback_splat:
		d.texture_albedo = _fallback_splat
	else:
		d.free()
		return
	d.modulate = cfg.wet
	d.albedo_mix = 1.0
	d.normal_fade = 0.5
	d.cull_mask = 1
	d.size = Vector3(size.x, clampf(size.y * 0.35, 0.05, float(cfg.splat_depth)), size.y)
	d.distance_fade_enabled = true
	d.distance_fade_begin = float(cfg.draw_m) - 15.0
	d.distance_fade_length = 15.0
	var x := (tangent - n * tangent.dot(n)).normalized()
	var z := x.cross(n).normalized()
	if variant >= 0 and variant < _spatter.size() / 2:
		x = x.rotated(n, _rng.randf() * TAU)
		z = x.cross(n).normalized()
	parent.add_child(d)
	d.global_transform = Transform3D(Basis(x, n, z), p + n * 0.01)
	_splats.append([d, _clock, false])


func _prune_splats() -> void:
	while _splats.size() >= int(Balance.BLOOD.max_splats):
		var old: Array = _splats.pop_front()
		if is_instance_valid(old[0]):
			(old[0] as Node).queue_free()
	if _splats.size() > 0 and not is_instance_valid(_splats[0][0]):
		_splats = _splats.filter(func(e: Array) -> bool: return is_instance_valid(e[0]))


# ---------------------------------------------------------------- подтёки и лужи

## Подтёк на стене: пятно в точке p, струйки — вниз по стене.
func drip(parent: Node, p: Vector3, n: Vector3, size: float) -> void:
	var cfg: Dictionary = Balance.BLOOD
	var down := Vector3.DOWN - n * Vector3.DOWN.dot(n)
	if down.length() < 0.2:
		return
	down = down.normalized()
	var wr: Vector2 = cfg.drip_width
	var w := clampf(lerpf(wr.x, wr.y, inverse_lerp(float(cfg.drip_min_drop), float((cfg.gush_size as Vector2).y), size)), wr.x, wr.y)
	var length := w * 2.0
	var gr: Vector2 = cfg.drip_grow_sec
	var box := _box(parent, _drip_mat, p, n, down, Vector3(w, float(cfg.drip_depth), length), length * (0.5 - DRIP_SOURCE_V))
	box.set_instance_shader_parameter("cell_rect", Vector4(float(_rng.randi() % DRIP_COLS) / DRIP_COLS, 0.0, 1.0 / DRIP_COLS, 1.0))
	box.set_instance_shader_parameter("timing", Vector4(_clock, _rng.randf_range(gr.x, gr.y), 1e9, 1.0))
	box.set_instance_shader_parameter("look", Vector4(_rng.randf(), float(cfg.dry_sec), 0.0, 0.0))


## Лужа в точке p на поверхности с нормалью n: size — сторона, м, grow — за сколько растечётся.
## На уклоне течёт вниз (своя карта). Возвращает коробку — ей потом ставят stop (остановить рост).
func pool(parent: Node, p: Vector3, n: Vector3, size: float, grow: float) -> MeshInstance3D:
	var cfg: Dictionary = Balance.BLOOD
	var down := Vector3.DOWN - n * Vector3.DOWN.dot(n)
	var sloped := n.y < float(cfg.slope_cos) and down.length() > 0.05
	var flow := down.normalized() if sloped else _any_tangent(n)
	var shift := size * (0.5 - POOL_SLOPE_SOURCE_V) if sloped else 0.0
	var box := _box(parent, _pool_mat, p, n, flow, Vector3(size, float(cfg.pool_depth), size), shift)
	var row := 1 if sloped else 0
	box.set_instance_shader_parameter("cell_rect", Vector4(float(_rng.randi() % POOL_COLS) / POOL_COLS, float(row) * 0.5, 1.0 / POOL_COLS, 0.5))
	box.set_instance_shader_parameter("timing", Vector4(_clock, grow, 1e9, 1.0))
	box.set_instance_shader_parameter("look", Vector4(_rng.randf(), float(cfg.dry_sec), 0.0, 0.0))
	return box


## Остановить рост лужи (подняли раненого, утащили).
func stop(box: Variant) -> void:
	if box == null or not is_instance_valid(box):
		return
	var mi := box as MeshInstance3D
	var t: Vector4 = mi.get_instance_shader_parameter("timing")
	mi.set_instance_shader_parameter("timing", Vector4(t.x, t.y, minf(t.z, _clock), t.w))


## Коробка-проекция: Y — по нормали n, Z — по flow; центр сдвинут по flow на shift (источник у края).
func _box(parent: Node, mat: ShaderMaterial, p: Vector3, n: Vector3, flow: Vector3, size: Vector3, shift: float) -> MeshInstance3D:
	# сперва выкинуть удалённые вместе с родителем (filter отдаёт нетипизированный Array — только через assign),
	# потом старейшие сверх предела
	_boxes.assign(_boxes.filter(func(b: Variant) -> bool: return is_instance_valid(b)))
	while _boxes.size() >= int(Balance.BLOOD.max_boxes):
		_boxes.pop_front().queue_free()
	var y := n.normalized()
	var z := (flow - y * flow.dot(y)).normalized()
	var x := y.cross(z).normalized()
	var mi := MeshInstance3D.new()
	mi.name = "Blood"
	mi.mesh = _box_mesh
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	mi.visibility_range_end = float(Balance.BLOOD.draw_m)
	parent.add_child(mi)
	mi.global_transform = Transform3D(Basis(x * size.x, y * size.y, z * size.z), p + z * shift)
	_boxes.append(mi)
	return mi


# ---------------------------------------------------------------- раненые и убитые

func _process(delta: float) -> void:
	_clock += delta * time_k
	RenderingServer.global_shader_parameter_set("fx_time", _clock)
	_scan_t -= delta
	if _scan_t <= 0.0:
		_scan_t = float(Balance.BLOOD.scan_sec)
		_scan_bodies()
	_dry_t -= delta
	if _dry_t <= 0.0:
		_dry_t = 1.5
		_dry_splats()


## Лежащие (раненые и убитые) — в луже; утащили — мазок и новая лужа; подняли — лужа не растёт.
func _scan_bodies() -> void:
	var cfg: Dictionary = Balance.BLOOD
	var seen: Dictionary = {}
	for group: String in ["marauders", "all_players"]:
		for node in get_tree().get_nodes_in_group(group):
			var body := node as Node3D
			if body == null or not body.is_inside_tree():
				continue
			var h := body.get_node_or_null("Health") as Health
			if h == null:
				continue
			var lying := h.downed or not h.alive
			if not lying:
				if _bodies.has(body):
					stop(_bodies[body].pool)
					_bodies.erase(body)
				continue
			seen[body] = true
			var st: Dictionary = _bodies.get(body, {})
			if st.is_empty():
				st = {"since": _clock, "pool": null, "center": Vector3.INF, "last": Vector3.INF, "dead": not h.alive, "dragged": false}
				_bodies[body] = st
			st.dead = not h.alive
			var settle := float(cfg.settle_dead) if st.dead else float(cfg.settle_down)
			if _clock - float(st.since) < settle:
				continue
			var c := _body_center(body)
			var last: Vector3 = st.last
			st.last = c
			var moving := last != Vector3.INF and last.distance_to(c) > 0.08
			var pool_box: MeshInstance3D = st.pool as MeshInstance3D if st.pool != null and is_instance_valid(st.pool) else null
			if pool_box and (st.center as Vector3).distance_to(c) > float(cfg.drag_m):
				# тащат: лужа остаётся, за телом — мазок
				stop(pool_box)
				st.pool = null
				st.dragged = true
				pool_box = null
			if moving:
				# раненого тащат с лужи — мазок; оседает при падении или убитый ещё катится — ждём
				if bool(st.dragged) and not st.dead:
					_smear(body.get_tree().current_scene, last, c)
				continue
			if pool_box == null:
				var g := _ground(body, c)
				if g.is_empty():
					continue
				var sr: Vector2 = cfg.pool_dead if st.dead else cfg.pool_down
				var tr: Vector2 = cfg.pool_dead_sec if st.dead else cfg.pool_down_sec
				st.pool = pool(get_tree().current_scene, g.position, g.normal, _rng.randf_range(sr.x, sr.y), _rng.randf_range(tr.x, tr.y))
				st.center = c
	# узел ушёл (уровень сменился, тело убрали) — забыть; ключ уже может быть освобождён
	for body in _bodies.keys():
		if not is_instance_valid(body):
			_bodies.erase(body)


## Середина корпуса лежащего: кость модели, иначе — ближайший регдолл, иначе — сам узел.
func _body_center(body: Node3D) -> Vector3:
	var anim := body.get_node_or_null("CharacterAnimator") as CharacterAnimator
	if anim and anim.has_model():
		var b := anim.bone_node(String(Balance.BLOOD.body_bone))
		if b:
			return b.global_position
	var best: Vector3 = body.global_position + Vector3.UP * 0.3
	var best_d := 3.0
	for r in get_tree().get_nodes_in_group("ragdolls"):
		for part in (r as Node).get_children():
			if part is Node3D:
				var d := (part as Node3D).global_position.distance_to(body.global_position)
				if d < best_d:
					best_d = d
					best = (part as Node3D).global_position
				break
	return best


func _ground(body: Node3D, c: Vector3) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(c + Vector3.UP * 0.6, c + Vector3.DOWN * 2.5, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	return body.get_world_3d().direct_space_state.intersect_ray(q)


## Мазок за телом, которое тащат: вытянутые следы вдоль пути.
func _smear(parent: Node, a: Vector3, b: Vector3) -> void:
	var cfg: Dictionary = Balance.BLOOD
	var step := float(cfg.smear_step)
	var dist := a.distance_to(b)
	var dir := (b - a).normalized()
	var s := 0.0
	while s < dist:
		var at := a + dir * s
		var q := PhysicsRayQueryParameters3D.create(at + Vector3.UP * 0.6, at + Vector3.DOWN * 2.5, Hitscan.LAYER_WORLD)
		var hit := (parent as Node3D).get_world_3d().direct_space_state.intersect_ray(q) if parent is Node3D else {}
		if not hit.is_empty():
			var half := _spatter.size() / 2
			var variant := (half + _rng.randi() % half) if half > 0 else -1
			var w := _rng.randf_range(0.3, 0.45)
			_splat(parent, hit.position, hit.normal, -dir, Vector2(w * 2.2, w), variant)
		s += step


func _tick_bleeders() -> void:
	if _bleeders.is_empty():
		return
	var cfg: Dictionary = Balance.BLOOD
	var keep: Array = []
	for b: Dictionary in _bleeders:
		var node := (b.node as WeakRef).get_ref() as Node3D
		if node == null or not node.is_inside_tree() or _clock > float(b.until):
			continue
		keep.append(b)
		if _clock >= float(b.next):
			var de: Vector2 = cfg.drip_every
			b.next = _clock + _rng.randf_range(de.x, de.y)
			var ds: Vector2 = cfg.drop_size
			_spawn_drop(node.get_tree().current_scene, node.to_global(b.off), Vector3(_rng.randf_range(-0.2, 0.2), -0.3, _rng.randf_range(-0.2, 0.2)), _rng.randf_range(ds.y * 0.6, ds.y))
	_bleeders = keep


## Следы капель сохнут: темнеют и буреют (у Decal шейдера нет — цветом).
func _dry_splats() -> void:
	var cfg: Dictionary = Balance.BLOOD
	var wet: Color = cfg.wet
	var dried: Color = cfg.dried
	var sec := float(cfg.dry_sec)
	for e: Array in _splats:
		if bool(e[2]) or not is_instance_valid(e[0]):
			continue
		var k := clampf((_clock - float(e[1])) / sec, 0.0, 1.0)
		(e[0] as Decal).modulate = wet.lerp(dried, smoothstep(0.0, 1.0, k))
		if k >= 1.0:
			e[2] = true


## Для проверок.
func stats() -> Dictionary:
	return {"drops": _drop_pos.size(), "splats": _splats.size(), "boxes": _boxes.size(), "bodies": _bodies.size(), "bleeders": _bleeders.size(), "maps": _spatter.size()}
