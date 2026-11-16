class_name GlassPanes
extends Node3D
## Витринные стёкла сектора — каждая панель отдельно: пуля пробивает стекло (и летит дальше),
## у каждого попадания свои трещины (GlassCracks: дырка, крошка, лучи с изломами и ветками, дуги;
## лучи упираются в прежние трещины). Ослабленная панель потрескивает — трещины ползут, — и через
## пару секунд рассыпается на куски по узору трещин (GlassShatter): куски падают по ходу пуль,
## часть остаётся «зубьями» в раме. Закалённое стекло (двери) от первой пули покрывается сеткой
## мелких кубиков и осыпается ими волной от точки удара. Крупная дробь и граната выбивают сразу.
## На месте выбитой — проём: коллизия стекла и нижней рамы (подоконника) выключается, для ИИ
## появляется связка навигации через проём. Целые панели — один MultiMesh; повреждённая получает
## свой меш с текстурой трещин. Одно тело на слое Hitscan.LAYER_GLASS (форма на панель): ИИ сквозь
## стекло видит, пули его не останавливают, ходить сквозь целое нельзя. Решает хост (урон копится
## у него), состояние и точки попаданий рассылаются всем — трещины и куски у всех одинаковые.
## Строит SectorBuilder (setup до входа в дерево); панели «выбитые с начала» — без стекла.

## Прочность, когда осыпается сама, урон пули по стеклу, трещины, куски — Balance.GLASS.
const HP := 100.0
const DAMAGED_SHADER: Shader = preload("res://src/world/glass_damaged.gdshader")
const PARTICLES_SHADER: Shader = preload("res://src/combat/impact_particles.gdshader")
const STEP_LAYER: Script = preload("res://src/audio/step_layer_patch.gd")

## Панели: {xf: Transform3D (центр, X — вдоль, Z — нормаль), size: Vector2 (ширина, высота),
## floor_y, sill: Vector3 (размер подоконника, центр — под панелью), hp, broken, tempered,
## hits — сколько попаданий, side — куда полетят куски (+1 — по нормали).
## walk_through: false у окон без пешеходного маршрута с обеих сторон}.
var panes: Array = []
var _glass_mm: MultiMesh
var _body: StaticBody3D
var _sill_body: StaticBody3D
## Формы по панелям (у выбитых с начала — null: формы нет вовсе).
var _shapes: Array = []
var _sill_shapes: Array = []
var _collapse: Dictionary = {}
var _rng := RandomNumberGenerator.new()
## Повреждённые панели: номер → {"mesh": MeshInstance3D, "material": ShaderMaterial, "cracks": GlassCracks,
## "pending": попадания, ещё не нарисованные, "creep": до следующего потрескивания, с}.
var _damaged: Dictionary = {}
var _flush_queued: bool = false
var _damage_finish: ShaderMaterial

static var _cube_material: StandardMaterial3D

const GLASS_SHADER := """
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, specular_schlick_ggx;
void fragment() {
	ALBEDO = vec3(0.62, 0.72, 0.78);
	ROUGHNESS = 0.08;
	METALLIC = 0.1;
	SPECULAR = 0.8;
	ALPHA = 0.22;
}
"""


## Собрать панели до входа в дерево. У материала повреждения те же параметры трещин, что у DAMAGED_SHADER.
func setup(specs: Array, finish: ShaderMaterial = null, damage_finish: ShaderMaterial = null) -> void:
	name = "GlassPanes"
	add_to_group("glass_panes")
	panes = specs
	_rng.seed = 7331
	_damage_finish = damage_finish
	if finish == null:
		var sh := Shader.new()
		sh.code = GLASS_SHADER
		finish = ShaderMaterial.new()
		finish.shader = sh
	_glass_mm = MultiMesh.new()
	_glass_mm.transform_format = MultiMesh.TRANSFORM_3D
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	_glass_mm.mesh = box
	_glass_mm.instance_count = panes.size()
	var sill_mm := MultiMesh.new()
	sill_mm.transform_format = MultiMesh.TRANSFORM_3D
	sill_mm.mesh = box
	sill_mm.instance_count = panes.size()
	_body = StaticBody3D.new()
	_body.name = "Glass"
	_body.collision_layer = Hitscan.LAYER_GLASS
	_body.collision_mask = 0
	add_child(_body)
	_sill_body = StaticBody3D.new()
	_sill_body.name = "Sills"
	_sill_body.collision_layer = Hitscan.LAYER_WORLD
	_sill_body.collision_mask = 0
	add_child(_sill_body)
	for i in range(panes.size()):
		var p: Dictionary = panes[i]
		var xf: Transform3D = p.xf
		var sz: Vector2 = p.size
		p["hp"] = 0.0 if bool(p.get("broken", false)) else HP
		p["broken"] = bool(p.get("broken", false))
		# закалённое или обычное — по порядку сборки (у всех peer одинаково) или из данных
		var tempered_roll: bool = _rng.randf() < float(Balance.GLASS.tempered_share)
		p["tempered"] = bool(p.get("tempered", tempered_roll))
		p["hits"] = 0
		p["side"] = 1.0
		_glass_mm.set_instance_transform(i, Transform3D(xf.basis.scaled_local(Vector3(sz.x, sz.y, 0.02)), xf.origin) if not bool(p.broken) else Transform3D(Basis.from_scale(Vector3.ZERO), xf.origin))
		var sill: Vector3 = p.sill
		var sill_xf := Transform3D(xf.basis, Vector3(xf.origin.x, float(p.floor_y) + sill.y * 0.5, xf.origin.z))
		sill_mm.set_instance_transform(i, Transform3D(sill_xf.basis.scaled_local(sill), sill_xf.origin))
		if bool(p.broken):
			# выбита с начала — формы нет вовсе (навмеш печётся через проём)
			_shapes.append(null)
			_sill_shapes.append(null)
			continue
		var cs := CollisionShape3D.new()
		var bs := BoxShape3D.new()
		bs.size = Vector3(sz.x, sz.y, 0.03)
		cs.shape = bs
		cs.transform = xf
		cs.set_meta("surface", "glass")
		cs.set_meta("pane", i)
		_body.add_child(cs)
		_shapes.append(cs)
		var ss := CollisionShape3D.new()
		var sb := BoxShape3D.new()
		sb.size = sill
		ss.shape = sb
		ss.transform = sill_xf
		ss.set_meta("surface", "metal")
		ss.set_meta("sill_pane", i)
		_sill_body.add_child(ss)
		_sill_shapes.append(ss)
	var gi := MultiMeshInstance3D.new()
	gi.name = "GlassMesh"
	gi.multimesh = _glass_mm
	gi.material_override = finish
	gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(gi)
	var si := MultiMeshInstance3D.new()
	si.name = "SillMesh"
	si.multimesh = sill_mm
	si.material_override = SectorMaterials.get_material("steel_dark")
	add_child(si)


## Кто попал лучом в стекло: [GlassPanes, номер панели] или [].
static func pane_of(hit: Dictionary) -> Array:
	var body := hit.get("collider") as CollisionObject3D
	if body == null or not (body.get_parent() is GlassPanes) or not hit.has("shape"):
		return []
	var owner_node := body.shape_owner_get_owner(body.shape_find_owner(int(hit.shape)))
	if owner_node == null or not owner_node.has_meta("pane"):
		return []
	return [body.get_parent(), int(owner_node.get_meta("pane"))]


## Пуля попала в панель (у любого peer) в точку at, летела по dir: урон копит хост; трещины —
## от каждого попадания, куски потом полетят по ходу пули.
func bullet(idx: int, damage: float, at: Vector3 = Vector3.INF, dir: Vector3 = Vector3.ZERO) -> void:
	var dmg := damage * float(Balance.GLASS.bullet_k)
	var uv := Vector2(-1, -1)
	var xf: Transform3D = panes[idx].xf
	if at != Vector3.INF:
		var l: Vector3 = xf.affine_inverse() * at
		var sz: Vector2 = panes[idx].size
		uv = Vector2(clampf(l.x / sz.x + 0.5, 0.03, 0.97), clampf(l.y / sz.y + 0.5, 0.03, 0.97))
	var side: float = signf(dir.dot(xf.basis.z)) if not dir.is_zero_approx() else 0.0
	if Net.is_networked() and not multiplayer.is_server():
		_rpc_hit.rpc_id(1, idx, dmg, uv, side)
	else:
		_apply(idx, dmg, uv, side)


## Удар твёрдым предметом: энергия по нормали, а не скорость скольжения вдоль витрины.
func impact(idx: int, energy_j: float, at: Vector3) -> void:
	if Net.is_networked() and not multiplayer.is_server():
		return
	if idx < 0 or idx >= panes.size() or energy_j < float(Balance.CART.glass_min_j):
		return
	var p: Dictionary = panes[idx]
	if bool(p.broken):
		return
	var local: Vector3 = (p.xf as Transform3D).affine_inverse() * at
	var sz: Vector2 = p.size
	var uv: Vector2 = Vector2(clampf(local.x / sz.x + 0.5, 0.05, 0.95), clampf(local.y / sz.y + 0.5, 0.05, 0.95))
	_apply(idx, HP * energy_j / float(Balance.CART.glass_break_j), uv, -signf(local.z))


## Взрыв рядом (у хоста): чем ближе, тем сильнее; в радиусе удара — выбивает.
func blast(pos: Vector3, radius: float) -> void:
	for i in range(panes.size()):
		var p: Dictionary = panes[i]
		if bool(p.broken):
			continue
		var xf: Transform3D = p.xf
		var d := xf.origin.distance_to(pos)
		if d < radius:
			_apply(i, HP * 2.5 * (1.0 - d / radius) + 20.0, Vector2(-1, -1), signf((xf.origin - pos).dot(xf.basis.z)))


@rpc("any_peer", "call_remote", "reliable")
func _rpc_hit(idx: int, dmg: float, uv: Vector2, side: float = 0.0) -> void:
	if multiplayer.is_server():
		_apply(idx, dmg, uv, side)


func _apply(idx: int, dmg: float, uv: Vector2 = Vector2(-1, -1), side: float = 0.0) -> void:
	if idx < 0 or idx >= panes.size():
		return
	var p: Dictionary = panes[idx]
	if bool(p.broken):
		return
	var hp := maxf(0.0, float(p.hp) - dmg)
	var g: Dictionary = Balance.GLASS
	if hp > 0.0 and not _collapse.has(idx):
		if bool(p.tempered):
			# закалённое держит недолго: сетка кубиков — и осыпалось
			_collapse[idx] = _rng.randf_range(float(g.tempered_sec[0]), float(g.tempered_sec[1]))
		elif hp < HP * float(g.collapse_below):
			_collapse[idx] = _rng.randf_range(float(g.collapse_sec[0]), float(g.collapse_sec[1]))
	_send(idx, hp, uv, side)


func _send(idx: int, hp: float, uv: Vector2 = Vector2(-1, -1), side: float = 0.0) -> void:
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_state", [idx, hp, uv, side])
	else:
		_rpc_state(idx, hp, uv, side)


func _process(delta: float) -> void:
	_tick_creep(delta)
	if _collapse.is_empty() or (Net.is_networked() and not multiplayer.is_server()):
		return
	for idx in _collapse.keys():
		_collapse[idx] = float(_collapse[idx]) - delta
		if float(_collapse[idx]) <= 0.0:
			_collapse.erase(idx)
			if not bool(panes[idx].broken):
				_send(idx, 0.0)


## Ослабленная обычная панель потрескивает: трещины ползут к раме (у каждого peer своё — это вид).
func _tick_creep(delta: float) -> void:
	var g: Dictionary = Balance.GLASS
	for idx: int in _damaged:
		var p: Dictionary = panes[idx]
		if bool(p.broken) or bool(p.tempered) or float(p.hp) >= HP * float(g.collapse_below):
			continue
		var state: Dictionary = _damaged[idx]
		state.creep = float(state.creep) - delta
		if float(state.creep) > 0.0:
			continue
		var interval: Vector2 = g.creep_sec
		state.creep = _rng.randf_range(interval.x, interval.y)
		if (state.cracks as GlassCracks).creep(_rng.randi()) and _rng.randf() < 0.45:
			Audio.play("glass_crack", Vector3((p.xf as Transform3D).origin), -9.0)


## Состояние панели у всех: прочность, точка попадания (трещины), куда полетят куски; 0 — осыпалась.
@rpc("authority", "call_local", "reliable")
func _rpc_state(idx: int, hp: float, uv: Vector2 = Vector2(-1, -1), side: float = 0.0) -> void:
	var p: Dictionary = panes[idx]
	if bool(p.broken):
		return
	var was: float = float(p.hp)
	p["hp"] = hp
	if side != 0.0:
		p["side"] = side
	if uv.x >= 0.0:
		var state: Dictionary = _ensure_damaged(idx)
		p["hits"] = int(p.hits) + 1
		var damage_k: float = clampf((was - hp) / HP * 1.5, 0.2, 1.0)
		var weak: bool = hp < HP * float(Balance.GLASS.collapse_below)
		(state.pending as Array).append({"uv": uv, "seed": idx * 7919 + int(p.hits) * 104729 + 13, "k": damage_k, "weak": weak})
		if bool(p.tempered):
			var material: ShaderMaterial = state.material
			if float(material.get_shader_parameter("crazed")) < 0.5:
				material.set_shader_parameter("hit_uv", Vector2(uv.x, 1.0 - uv.y))
			material.set_shader_parameter("crazed", 1.0)
		Audio.play("glass_crack", Vector3(p.xf.origin))
		if not _flush_queued:
			_flush_queued = true
			_flush.call_deferred()
	if hp <= 0.0:
		_shatter(idx)


## Трещины рисуются в конце кадра, все попадания разом (дробь — восемь дробин в один кадр).
func _flush() -> void:
	_flush_queued = false
	for idx: int in _damaged:
		_draw_pending(idx, not bool(panes[idx].broken))


func _draw_pending(idx: int, draw: bool) -> void:
	var state: Dictionary = _damaged[idx]
	var cracks: GlassCracks = state.cracks
	var rays: bool = not bool(panes[idx].tempered)
	for hit: Dictionary in state.pending:
		cracks.add_hit(hit.uv, int(hit.seed), float(hit.k), bool(hit.weak), draw, rays)
	(state.pending as Array).clear()


## Свой меш повреждённой панели (целая — в общем MultiMesh) с текстурой трещин.
func _ensure_damaged(idx: int) -> Dictionary:
	if _damaged.has(idx):
		return _damaged[idx]
	var p: Dictionary = panes[idx]
	var xf: Transform3D = p.xf
	var sz: Vector2 = p.size
	var cracks: GlassCracks = GlassCracks.new(sz)
	var material: ShaderMaterial = _damage_finish.duplicate() as ShaderMaterial if _damage_finish else ShaderMaterial.new()
	if material.shader == null:
		material.shader = DAMAGED_SHADER
	material.set_shader_parameter("crack_tex", cracks.texture)
	material.set_shader_parameter("texel", Vector2(1.0 / float(cracks.texture.get_width()), 1.0 / float(cracks.texture.get_height())))
	material.set_shader_parameter("pane_size", sz)
	material.set_shader_parameter("hit_uv", Vector2(0.5, 0.5))
	material.set_shader_parameter("crazed", 0.0)
	var quad: QuadMesh = QuadMesh.new()
	quad.size = sz
	var mesh: MeshInstance3D = MeshInstance3D.new()
	mesh.name = "Pane_%d" % idx
	mesh.mesh = quad
	mesh.material_override = material
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mesh)
	mesh.transform = xf
	_glass_mm.set_instance_transform(idx, Transform3D(Basis.from_scale(Vector3.ZERO), xf.origin))
	var state: Dictionary = {"mesh": mesh, "material": material, "cracks": cracks, "pending": [], "creep": 0.3}
	_damaged[idx] = state
	return state


func _shatter(idx: int) -> void:
	var p: Dictionary = panes[idx]
	p["broken"] = true
	var xf: Transform3D = p.xf
	var state: Dictionary = _ensure_damaged(idx)
	# попадания этого же кадра — только в узор кусков, рисовать уже нечего
	_draw_pending(idx, false)
	_shapes[idx].set_deferred("disabled", true)
	_sill_shapes[idx].set_deferred("disabled", true)
	if bool(p.tempered):
		_crumble(idx, state)
	else:
		_break_apart(idx, state)
	Audio.play("glass_break", xf.origin)
	Audio.play("glass_shards", xf.origin, -5.0)
	NoiseBus.emit(xf.origin, float(Balance.GLASS.noise_m), "glass")
	if not bool(p.get("walk_through", true)):
		return
	# проём — ИИ проходит: связка навигации с одной стороны на другую
	var link := NavigationLink3D.new()
	link.name = "Gap_%d" % idx
	link.bidirectional = true
	var fl := Vector3(xf.origin.x, float(p.floor_y), xf.origin.z)
	var nrm := xf.basis.z.normalized()
	add_child(link)
	link.global_position = fl
	link.start_position = nrm * 0.9
	link.end_position = -nrm * 0.9


## Обычное стекло: куски по узору трещин (GlassShatter) вместо панели.
func _break_apart(idx: int, state: Dictionary) -> void:
	var p: Dictionary = panes[idx]
	var xf: Transform3D = p.xf
	var shatter: GlassShatter = GlassShatter.new()
	shatter.name = "Shards_%d" % idx
	add_child(shatter)
	shatter.transform = xf
	var cracks: GlassCracks = state.cracks
	var floor_local: float = float(p.floor_y) - xf.origin.y
	shatter.build(p.size, cracks.hits, float(p.side), floor_local, idx * 92821 + int(p.hits) * 31, (state.material as ShaderMaterial).duplicate() as ShaderMaterial)
	(state.mesh as MeshInstance3D).queue_free()
	get_tree().create_timer(1.0).timeout.connect(_pile.bind(xf, p.size, float(p.floor_y), false))


## Закалённое: сетка кубиков исчезает волной от точки удара, кубики сыплются той же волной.
func _crumble(idx: int, state: Dictionary) -> void:
	var g: Dictionary = Balance.GLASS
	var p: Dictionary = panes[idx]
	var xf: Transform3D = p.xf
	var sz: Vector2 = p.size
	var material: ShaderMaterial = state.material
	var hit_uv: Vector2 = material.get_shader_parameter("hit_uv")
	material.set_shader_parameter("crazed", 1.0)
	var hit_local: Vector2 = Vector2((hit_uv.x - 0.5) * sz.x, (0.5 - hit_uv.y) * sz.y)
	var reach: float = 0.0
	for corner: Vector2 in [Vector2(-0.5, -0.5), Vector2(0.5, -0.5), Vector2(0.5, 0.5), Vector2(-0.5, 0.5)]:
		reach = maxf(reach, (corner * sz).distance_to(hit_local))
	var wave: float = float(g.tempered_wave_mps)
	var tween: Tween = (state.mesh as MeshInstance3D).create_tween()
	tween.tween_method(func(r: float) -> void: material.set_shader_parameter("dissolve_r", r), 0.001, reach + 0.1, (reach + 0.1) / wave)
	tween.tween_callback((state.mesh as MeshInstance3D).queue_free)
	var cubes: GPUParticles3D = GPUParticles3D.new()
	cubes.name = "Cubes_%d" % idx
	var count: int = clampi(int(sz.x * sz.y * float(g.cubes_per_m2)), 60, int(g.cubes_max))
	var life: Vector2 = Vector2(0.9, 1.7)
	var process: ShaderMaterial = ShaderMaterial.new()
	process.shader = PARTICLES_SHADER
	process.set_shader_parameter("direction", (xf.basis.z * float(p.side) + Vector3.DOWN * 0.6).normalized())
	process.set_shader_parameter("spread", 70.0)
	process.set_shader_parameter("speed", Vector2(0.2, 1.4))
	process.set_shader_parameter("life", life)
	process.set_shader_parameter("size", Vector2(0.01, 0.022))
	process.set_shader_parameter("gravity", Balance.IMPACT_GRAVITY)
	process.set_shader_parameter("drag", 0.3)
	process.set_shader_parameter("spin", 9.0)
	process.set_shader_parameter("bounce", 0.3)
	process.set_shader_parameter("friction", 0.5)
	process.set_shader_parameter("jitter", 0.0)
	process.set_shader_parameter("emit_box", Vector3(sz.x * 0.5, sz.y * 0.5, 0.004))
	process.set_shader_parameter("release_from", xf * Vector3(hit_local.x, hit_local.y, 0.0))
	process.set_shader_parameter("release_speed", wave)
	process.set_shader_parameter("plane_b", Vector4(0.0, 1.0, 0.0, float(p.floor_y)))
	process.set_shader_parameter("color_ramp", ImpactBurst._ramp("debris"))
	process.set_shader_parameter("tint", Color(0.82, 0.9, 0.93))
	process.set_shader_parameter("tint_alt", Color(0.95, 0.98, 1.0))
	process.set_shader_parameter("alt_share", 0.4)
	cubes.process_material = process
	cubes.amount = count
	cubes.lifetime = life.y + (reach + 0.1) / wave + 0.1
	cubes.one_shot = true
	cubes.explosiveness = 1.0
	cubes.local_coords = false
	cubes.fixed_fps = 0
	cubes.visibility_aabb = AABB(Vector3(-sz.x - 2.0, float(p.floor_y) - xf.origin.y - 1.0, -3.0), Vector3(sz.x * 2.0 + 4.0, sz.y + 4.0, 6.0))
	cubes.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	cubes.draw_pass_1 = ImpactBurst._mesh("pebble")
	cubes.material_override = _cubes_material()
	add_child(cubes)
	cubes.transform = xf
	cubes.emitting = true
	get_tree().create_timer(cubes.lifetime + 0.5).timeout.connect(cubes.queue_free)
	get_tree().create_timer(life.x + reach / wave).timeout.connect(_pile.bind(xf, sz, float(p.floor_y), true))


## Материалы повреждённого стекла (трещины, куски, кубики, мелочь на полу) — для разогрева шейдеров.
static func warm_materials() -> Array[Material]:
	var damaged: ShaderMaterial = ShaderMaterial.new()
	damaged.shader = DAMAGED_SHADER
	return [damaged, _cubes_material(), _shard_mesh().surface_get_material(0)]


static func _cubes_material() -> StandardMaterial3D:
	if _cube_material == null:
		_cube_material = StandardMaterial3D.new()
		_cube_material.vertex_color_use_as_albedo = true
		_cube_material.roughness = 0.2
		_cube_material.metallic_specular = 0.9
		# кубик закалённого стекла светится по краям — блёстка, а не тёмная крошка
		_cube_material.rim_enabled = true
		_cube_material.rim = 0.8
		_cube_material.rim_tint = 0.2
	return _cube_material


static var _shard: ArrayMesh


## Осколок — неровный треугольник (1 м по большей стороне, масштабируется).
static func _shard_mesh() -> ArrayMesh:
	if _shard:
		return _shard
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_normal(Vector3.BACK)
	for v in [Vector3(-0.5, -0.4, 0), Vector3(0.5, -0.2, 0), Vector3(0.05, 0.6, 0)]:
		st.add_vertex(v)
	var m := StandardMaterial3D.new()
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(0.8, 0.88, 0.92, 0.6)
	m.roughness = 0.08
	m.metallic = 0.3
	m.metallic_specular = 0.9
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	st.set_material(m)
	_shard = st.commit()
	return _shard


## Мелочь на полу у проёма — лежит до конца рейда (один MultiMesh на проём): у обычного стекла —
## мелкие осколки между кусками, у закалённого — горка кубиков.
func _pile(xf: Transform3D, size: Vector2, floor_y: float, cubes: bool) -> void:
	if not is_inside_tree():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = ImpactBurst._mesh("pebble") if cubes else _shard_mesh()
	mm.instance_count = 220 if cubes else 24
	var along := xf.basis.x.normalized()
	var nrm := xf.basis.z.normalized()
	for i in range(mm.instance_count):
		var p := xf.origin + along * _rng.randf_range(-size.x * 0.55, size.x * 0.55) + nrm * _rng.randf_range(-Balance.STEP_GLASS_SPREAD, Balance.STEP_GLASS_SPREAD) * pow(_rng.randf(), 1.8)
		p.y = floor_y + 0.004
		var b := Basis(Vector3.UP, _rng.randf() * TAU) * (Basis.IDENTITY if cubes else Basis(Vector3.RIGHT, -PI * 0.5))
		var scale: float = _rng.randf_range(0.008, 0.018) if cubes else _rng.randf_range(0.012, 0.04)
		mm.set_instance_transform(i, Transform3D(b.scaled(Vector3.ONE * scale), p))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if cubes:
		mi.material_override = _cubes_material()
	add_child(mi)
	# Область живёт вместе с видимой россыпью и появляется у каждого участника рейда.
	var patch: Node3D = STEP_LAYER.new()
	patch.name = "GlassFootsteps"
	patch.set("size", Vector2(size.x * 1.1, Balance.STEP_GLASS_SPREAD * 2.0))
	patch.transform = Transform3D(Basis(along, Vector3.UP, nrm), Vector3(xf.origin.x, floor_y, xf.origin.z))
	mi.add_child(patch)
