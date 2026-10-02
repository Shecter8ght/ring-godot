class_name GlassPanes
extends Node3D
## Витринные стёкла сектора — каждая панель отдельно: пуля пробивает стекло (и летит дальше),
## панель трескается (трещины растут от попаданий), треснувшая сильно — через пару секунд
## осыпается сама, крупная дробь и граната выбивают сразу. На месте выбитой — проём: коллизия
## стекла и нижней рамы (подоконника) выключается, для ИИ появляется связка навигации через проём.
## Все панели — один MultiMesh (трещины в шейдере по данным экземпляра) и одно тело на слое
## Hitscan.LAYER_GLASS (форма на панель): ИИ сквозь стекло видит, пули его не останавливают,
## ходить сквозь целое нельзя. Решает хост (урон копится у него), состояние рассылается всем.
## Строит SectorBuilder (setup до входа в дерево); панели «выбитые с начала» — без стекла.

## Прочность, когда осыпается сама, урон пули по стеклу — Balance.GLASS.
const HP := 100.0
const CRACK_ATLAS_PATH := "res://assets/textures/impacts/glass_cracks.png"

## Панели: {xf: Transform3D (центр, X — вдоль, Z — нормаль), size: Vector2 (ширина, высота),
## floor_y, sill: Vector3 (размер подоконника, центр — под панелью), hp, broken}.
var panes: Array = []
var _glass_mm: MultiMesh
var _body: StaticBody3D
var _sill_body: StaticBody3D
## Формы по панелям (у выбитых с начала — null: формы нет вовсе).
var _shapes: Array = []
var _sill_shapes: Array = []
var _collapse: Dictionary = {}
var _rng := RandomNumberGenerator.new()

const GLASS_SHADER := """
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, specular_schlick_ggx;
uniform sampler2D crack_atlas : source_color, filter_linear_mipmap_anisotropic, repeat_disable;
uniform bool has_crack_atlas = false;
varying vec2 lp;
varying vec4 cd;
varying vec2 hitp;
float hash1(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
vec2 hash2(vec2 p) { return fract(sin(vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)))) * 43758.5453); }
void vertex() {
	cd = INSTANCE_CUSTOM;
	// точка первого попадания (0..1 по панели) — из цвета экземпляра
	hitp = COLOR.rg;
	// локальная точка на панели в метрах (меш — единичный куб, размер — в данных экземпляра)
	lp = VERTEX.xy * cd.ba;
}
// «паутина»: радиальные лучи от точки удара + кольца, узор Вороного поверх — осколки
float cracks(vec2 p, vec2 c, float amount, float seed) {
	vec2 d = p - c;
	float r = length(d);
	float a = atan(d.y, d.x);
	float n = 11.0 + floor(seed * 6.0);
	float sector = a / 6.2831853 * n;
	float fs = fract(sector + hash1(vec2(floor(sector), seed)) * 0.3);
	// расстояние до ближайшего луча, м
	float dl = min(fs, 1.0 - fs) * 6.2831853 * r / n;
	float rays = 1.0 - smoothstep(0.002, 0.008, dl);
	float fr = fract(r * 5.0 + seed);
	float rings = 1.0 - smoothstep(0.002, 0.007, min(fr, 1.0 - fr) / 5.0);
	vec2 g = p * 7.0;
	vec2 i = floor(g);
	float md = 8.0;
	float md2 = 8.0;
	for (int y = -1; y <= 1; y++) {
		for (int x = -1; x <= 1; x++) {
			vec2 o = vec2(float(x), float(y));
			vec2 q = o + hash2(i + o + seed * 13.0) - fract(g);
			float dd = dot(q, q);
			if (dd < md) { md2 = md; md = dd; } else if (dd < md2) { md2 = dd; }
		}
	}
	float vor = 1.0 - smoothstep(0.0, 0.06, sqrt(md2) - sqrt(md));
	float reach = amount * 1.6;
	float inner = 1.0 - smoothstep(reach * 0.35, reach * 0.55, r);
	float outer = 1.0 - smoothstep(reach * 0.8, reach, r);
	return clamp(max(rays * outer, max(rings * inner * 0.8, vor * inner * step(0.35, amount))), 0.0, 1.0);
}
// CC0-атлас даёт естественную форму трещин; размер повреждения растёт вместе с накопленным уроном.
float atlas_cracks(vec2 p, vec2 c, float amount, float seed) {
	float diameter = mix(0.34, 1.05, clamp(amount, 0.0, 1.0));
	vec2 uv = (p - c) / diameter + vec2(0.5);
	if (uv.x <= 0.0 || uv.y <= 0.0 || uv.x >= 1.0 || uv.y >= 1.0) { return 0.0; }
	float cell = floor(seed * 15.999);
	vec2 tile = vec2(mod(cell, 4.0), floor(cell / 4.0));
	float mask = texture(crack_atlas, (tile + uv) / 4.0).a;
	return mask * smoothstep(0.06, 0.28, amount);
}
void fragment() {
	float amount = cd.r;
	float seed = cd.g;
	vec2 c = (hitp - 0.5) * cd.ba;
	float generated = amount > 0.001 ? cracks(lp, c, amount, seed) : 0.0;
	float sampled = has_crack_atlas && amount > 0.001 ? atlas_cracks(lp, c, amount, seed) : 0.0;
	float k = max(generated * (has_crack_atlas ? 0.22 : 1.0), sampled);
	ALBEDO = mix(vec3(0.62, 0.72, 0.78), vec3(0.9, 0.93, 0.95), k);
	ROUGHNESS = mix(0.08, 0.55, k);
	METALLIC = 0.1;
	SPECULAR = 0.8;
	// треснувшее стекло мутнеет
	ALPHA = mix(0.22, 0.85, k) + amount * 0.08;
}
"""


## Собрать панели (SectorBuilder, до входа в дерево).
func setup(specs: Array) -> void:
	name = "GlassPanes"
	add_to_group("glass_panes")
	panes = specs
	_rng.seed = 7331
	var sh := Shader.new()
	sh.code = GLASS_SHADER
	var gm := ShaderMaterial.new()
	gm.shader = sh
	if ResourceLoader.exists(CRACK_ATLAS_PATH):
		gm.set_shader_parameter("crack_atlas", load(CRACK_ATLAS_PATH) as Texture2D)
		gm.set_shader_parameter("has_crack_atlas", true)
	_glass_mm = MultiMesh.new()
	_glass_mm.transform_format = MultiMesh.TRANSFORM_3D
	_glass_mm.use_custom_data = true
	_glass_mm.use_colors = true
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
		_glass_mm.set_instance_transform(i, Transform3D(xf.basis.scaled_local(Vector3(sz.x, sz.y, 0.02)), xf.origin) if not bool(p.broken) else Transform3D(Basis.from_scale(Vector3.ZERO), xf.origin))
		_glass_mm.set_instance_custom_data(i, Color(0.0, _rng.randf(), sz.x, sz.y))
		_glass_mm.set_instance_color(i, Color(0.5 + _rng.randf_range(-0.2, 0.2), 0.5 + _rng.randf_range(-0.2, 0.2), 0.0))
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
	gi.material_override = gm
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


## Пуля попала в панель (у любого peer) в точку at: урон копит хост; трещины — от первого попадания.
func bullet(idx: int, damage: float, at: Vector3 = Vector3.INF) -> void:
	var dmg := damage * float(Balance.GLASS.bullet_k)
	var uv := Vector2(-1, -1)
	if at != Vector3.INF and float(panes[idx].hp) >= HP:
		var l: Vector3 = (panes[idx].xf as Transform3D).affine_inverse() * at
		var sz: Vector2 = panes[idx].size
		uv = Vector2(clampf(l.x / sz.x + 0.5, 0.05, 0.95), clampf(l.y / sz.y + 0.5, 0.05, 0.95))
	if Net.is_networked() and not multiplayer.is_server():
		_rpc_hit.rpc_id(1, idx, dmg, uv)
	else:
		_apply(idx, dmg, uv)


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
	_apply(idx, HP * energy_j / float(Balance.CART.glass_break_j), uv)


## Взрыв рядом (у хоста): чем ближе, тем сильнее; в радиусе удара — выбивает.
func blast(pos: Vector3, radius: float) -> void:
	for i in range(panes.size()):
		var p: Dictionary = panes[i]
		if bool(p.broken):
			continue
		var d := ((p.xf as Transform3D).origin).distance_to(pos)
		if d < radius:
			_apply(i, HP * 2.5 * (1.0 - d / radius) + 20.0)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_hit(idx: int, dmg: float, uv: Vector2) -> void:
	if multiplayer.is_server():
		_apply(idx, dmg, uv)


func _apply(idx: int, dmg: float, uv: Vector2 = Vector2(-1, -1)) -> void:
	if idx < 0 or idx >= panes.size():
		return
	var p: Dictionary = panes[idx]
	if bool(p.broken):
		return
	var hp := maxf(0.0, float(p.hp) - dmg)
	var g: Dictionary = Balance.GLASS
	if hp > 0.0 and hp < HP * float(g.collapse_below) and not _collapse.has(idx):
		_collapse[idx] = _rng.randf_range(float(g.collapse_sec[0]), float(g.collapse_sec[1]))
	_send(idx, hp, uv)


func _send(idx: int, hp: float, uv: Vector2 = Vector2(-1, -1)) -> void:
	if Net.is_networked():
		_rpc_state.rpc(idx, hp, uv)
	else:
		_rpc_state(idx, hp, uv)


func _process(delta: float) -> void:
	if _collapse.is_empty() or (Net.is_networked() and not multiplayer.is_server()):
		return
	for idx in _collapse.keys():
		_collapse[idx] = float(_collapse[idx]) - delta
		if float(_collapse[idx]) <= 0.0:
			_collapse.erase(idx)
			if not bool(panes[idx].broken):
				_send(idx, 0.0)


## Состояние панели у всех: трещины по прочности; 0 — осыпалась.
@rpc("authority", "call_local", "reliable")
func _rpc_state(idx: int, hp: float, uv: Vector2 = Vector2(-1, -1)) -> void:
	var p: Dictionary = panes[idx]
	if bool(p.broken):
		return
	p["hp"] = hp
	if uv.x >= 0.0:
		_glass_mm.set_instance_color(idx, Color(uv.x, uv.y, 0.0))
		Audio.play("glass_crack", Vector3(p.xf.origin))
	var c := _glass_mm.get_instance_custom_data(idx)
	c.r = clampf(1.0 - hp / HP, 0.0, 1.0) * 0.85 + (0.15 if hp < HP else 0.0)
	_glass_mm.set_instance_custom_data(idx, c)
	if hp <= 0.0:
		_shatter(idx)


func _shatter(idx: int) -> void:
	var p: Dictionary = panes[idx]
	p["broken"] = true
	var xf: Transform3D = p.xf
	_glass_mm.set_instance_transform(idx, Transform3D(Basis.from_scale(Vector3.ZERO), xf.origin))
	_shapes[idx].set_deferred("disabled", true)
	_sill_shapes[idx].set_deferred("disabled", true)
	_shards(xf, p.size)
	_pile(xf, p.size, float(p.floor_y))
	Audio.play("glass_break", xf.origin)
	Audio.play("glass_shards", xf.origin, -5.0)
	NoiseBus.emit(xf.origin, float(Balance.GLASS.noise_m), "glass")
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


## Осколки: сыплются вниз и в стороны, остаются лежать.
func _shards(xf: Transform3D, size: Vector2) -> void:
	var parts := CPUParticles3D.new()
	parts.one_shot = true
	parts.explosiveness = 0.85
	parts.amount = 70
	parts.lifetime = 1.6
	parts.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	parts.emission_box_extents = Vector3(size.x * 0.5, size.y * 0.5, 0.02)
	parts.direction = Vector3(0, -0.3, 1)
	parts.spread = 80.0
	parts.initial_velocity_min = 0.5
	parts.initial_velocity_max = 2.5
	parts.gravity = Vector3(0, -9.8, 0)
	parts.angular_velocity_min = -400.0
	parts.angular_velocity_max = 400.0
	parts.scale_amount_min = 0.012
	parts.scale_amount_max = 0.05
	parts.mesh = _shard_mesh()
	add_child(parts)
	parts.global_transform = xf
	parts.emitting = true
	get_tree().create_timer(3.0).timeout.connect(parts.queue_free)


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


## Россыпь осколков на полу у проёма — лежит до конца рейда (один MultiMesh на проём).
func _pile(xf: Transform3D, size: Vector2, floor_y: float) -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = _shard_mesh()
	mm.instance_count = 36
	var along := xf.basis.x.normalized()
	var nrm := xf.basis.z.normalized()
	for i in range(mm.instance_count):
		var p := xf.origin + along * _rng.randf_range(-size.x * 0.55, size.x * 0.55) + nrm * _rng.randf_range(-1.3, 1.3) * pow(_rng.randf(), 1.5)
		p.y = floor_y + 0.004
		var b := Basis(Vector3.UP, _rng.randf() * TAU) * Basis(Vector3.RIGHT, -PI * 0.5)
		mm.set_instance_transform(i, Transform3D(b.scaled(Vector3.ONE * _rng.randf_range(0.015, 0.06)), p))
	var mi := MultiMeshInstance3D.new()
	mi.multimesh = mm
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)
