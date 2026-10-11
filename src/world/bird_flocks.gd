class_name BirdFlocks
extends Node3D
## Птицы на открытой карте (данные карты: "birds"): стаи ворон и голубей сидят во дворах, несколько
## кружат в небе. Сидящая стая взлетает с карканьем от выстрела, взрыва и от того, кто подошёл или
## пробежал рядом, — игрока, мародёра, чужого отряда. Взлёт выдаёт бой и крадущихся (как в Hunt:
## Showdown). Покружив, стая садится на другое место. Ночью птиц нет, в дождь — меньше.
##
## Сеть: места стай считаются у всех одинаково (зерно — id карты, лучи вниз по той же геометрии);
## взлёт решает хост и рассылает всем (_rpc_startle). Полёт — картинка, у каждого своя.
##
## Модель: пока силуэт из нескольких треугольников с машущими крыльями (MultiMesh, шейдер). Придёт
## модель владельца — заменить _bird_mesh. Звуки — синтез здесь же (карканье, хлопки крыльев): записи
## CC0 положить в assets/audio и перевести на Audio, когда появятся.

enum State { SIT, UP, CIRCLE, DOWN }

const SHADER := "
shader_type spatial;
render_mode cull_disabled;
void vertex() {
	float fly = INSTANCE_CUSTOM.y;
	float span = UV.x;
	float a = sin(TIME * mix(8.0, 12.0, INSTANCE_CUSTOM.z) + INSTANCE_CUSTOM.x) * 0.85 * fly;
	// крыло: у сидящей сложено вдоль тела, у летящей машет вокруг оси тела
	// тело не трогаем (span 0): складываются и машут только крылья
	float wing = step(0.05, span);
	float x = VERTEX.x;
	VERTEX.x = mix(x, mix(x * 0.2, x * cos(a), fly), wing);
	VERTEX.y += wing * mix(-span * 0.025, abs(x) * sin(a), fly);
}
void fragment() {
	ALBEDO = COLOR.rgb;
	ROUGHNESS = 0.82;
	SPECULAR = 0.2;
}
"

var definition: Dictionary = {}
## Стаи: {kind, state, perch, center, away, t, air, birds: [{off, r, w, ph, h, delay}], circling, present}.
var flocks: Array[Dictionary] = []
var _perches: Array[Vector3] = []
var _mm: MultiMesh
var _rng := RandomNumberGenerator.new()
var _scan: float = 0.0
var _presence_t: float = 0.0
var _night: bool = false
var _ready_done: bool = false
static var _sounds: Dictionary = {}


func _ready() -> void:
	name = "Birds"
	add_to_group("bird_flocks")
	# геометрия и коллизии уровня собираются не в первый кадр — места ищем чуть позже
	get_tree().create_timer(float(Balance.BIRDS.start_sec)).timeout.connect(_setup)
	if not Net.is_networked() or multiplayer.is_server():
		NoiseBus.noise.connect(_on_noise)


func _is_host() -> bool:
	return not Net.is_networked() or multiplayer.is_server()


func _setup() -> void:
	if not is_inside_tree():
		return
	var cfg: Dictionary = Balance.BIRDS
	_rng.seed = hash(String(definition.get("id", "map"))) + 7
	var rects: Array = []
	for d: Variant in definition.get("districts", []):
		if d is Dictionary and (d as Dictionary).get("rect") is Array:
			rects.append((d as Dictionary).rect)
	if rects.is_empty():
		var b: Array = definition.get("bounds", [-100.0, -100.0, 100.0, 100.0])
		rects.append(b)
	# места: в каждом районе по нескольку точек под открытым небом
	var space := get_world_3d().direct_space_state
	for rect: Array in rects:
		for i: int in range(int(cfg.perches_per_district)):
			var p := Vector3(_rng.randf_range(float(rect[0]), float(rect[2])), 0.0, _rng.randf_range(float(rect[1]), float(rect[3])))
			var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 120.0, p + Vector3.DOWN * 40.0, Hitscan.LAYER_WORLD)
			var hit: Dictionary = space.intersect_ray(q)
			if not hit.is_empty() and (hit.normal as Vector3).y > 0.7:
				_perches.append(hit.position as Vector3)
	if _perches.is_empty():
		return
	var conf: Dictionary = definition.get("birds", {}) if definition.get("birds") is Dictionary else {}
	var sitting: int = mini(int(conf.get("sitting", cfg.sitting)), _perches.size())
	var circling: int = int(conf.get("circling", cfg.circling))
	var order: Array = range(_perches.size())
	# перемешать тем же зерном — у всех игроков одинаково
	for i: int in range(order.size() - 1, 0, -1):
		var j: int = _rng.randi_range(0, i)
		var tmp: int = order[i]
		order[i] = order[j]
		order[j] = tmp
	var total: int = 0
	for i: int in range(sitting + circling):
		var air: bool = i >= sitting
		var kind: String = "crow" if air or _rng.randf() < float(cfg.crow_share) else "pigeon"
		var perch: Vector3 = _perches[order[i % order.size()]]
		var flock: Dictionary = {"kind": kind, "state": State.CIRCLE if air else State.SIT, "perch": perch, "center": perch,
			"away": Vector3.ZERO, "t": _rng.randf() * 60.0, "air": INF if air else 0.0, "circling": air, "present": true, "birds": [],
			"caw": _rng.randf_range(4.0, 14.0), "fly": _rng.randf() * 60.0}
		for b: int in range(_rng.randi_range(int(cfg.flock[0]), int(cfg.flock[1]))):
			var ang: float = _rng.randf() * TAU
			flock.birds.append({"off": Vector3(cos(ang), 0.0, sin(ang)) * _rng.randf_range(0.3, float(cfg.sit_spread_m)), "yaw": _rng.randf() * TAU,
				"r": _rng.randf_range(float(cfg.circle_r[0]), float(cfg.circle_r[1])) * (1.6 if air else 1.0),
				"h": _rng.randf_range(float(cfg.circle_h[0]), float(cfg.circle_h[1])) * (1.7 if air else 1.0),
				"ph": _rng.randf() * TAU, "delay": _rng.randf() * float(cfg.takeoff_spread_sec), "dir": 1.0 if _rng.randf() < 0.5 else -1.0})
		total += flock.birds.size()
		flocks.append(flock)
	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.use_custom_data = true
	_mm.mesh = _bird_mesh()
	_mm.instance_count = total
	var inst := MultiMeshInstance3D.new()
	inst.name = "Flock"
	inst.multimesh = _mm
	inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# стаи разбросаны по всей карте: общий габарит, иначе меш отсекался бы по началу координат
	inst.custom_aabb = AABB(Vector3(-2000, -200, -2000), Vector3(4000, 800, 4000))
	add_child(inst)
	_ready_done = true
	_refresh_presence()
	_draw(0.0)


func _process(delta: float) -> void:
	if not _ready_done:
		return
	_presence_t -= delta
	if _presence_t <= 0.0:
		_presence_t = 4.0
		_refresh_presence()
	for flock: Dictionary in flocks:
		_tick(flock, delta)
	_draw(delta)
	if _is_host():
		_scan -= delta
		if _scan <= 0.0:
			_scan = float(Balance.BIRDS.scan_sec)
			_scan_walkers()


## Ночью птиц нет; в дождь остаётся только часть стай.
func _refresh_presence() -> void:
	var time_key: String = String(RaidConditions.current.get("time", "day"))
	var dc: DayCycle = get_parent().get_node_or_null("DayCycle") as DayCycle
	_night = (dc.hour < 4.5 or dc.hour > 21.5) if dc else time_key == "night"
	var k: float = float(Balance.BIRDS.rain_k) if String(RaidConditions.current.get("weather", "")) == "rain" else 1.0
	var keep: int = int(ceil(flocks.size() * k))
	for i: int in range(flocks.size()):
		flocks[i].present = not _night and i < keep


# ---------------------------------------------------------------- полёт

func _tick(flock: Dictionary, delta: float) -> void:
	if not bool(flock.present):
		return
	var cfg: Dictionary = Balance.BIRDS
	flock.t = float(flock.t) + delta
	# время полёта не сбрасывается между фазами — птица не прыгает по кругу при смене фазы
	flock.fly = float(flock.fly) + delta
	match int(flock.state):
		State.UP:
			# уходят от того, кто спугнул, и набирают высоту
			flock.center = (flock.center as Vector3) + (flock.away as Vector3) * float(cfg.speed) * 0.5 * delta
			if float(flock.t) >= float(cfg.climb_sec) + float(cfg.takeoff_spread_sec):
				flock.state = State.CIRCLE
				flock.t = 0.0
		State.CIRCLE:
			if bool(flock.circling):
				# кружащие медленно сносятся по карте
				flock.center = (flock.center as Vector3) + Vector3(sin(float(flock.t) * 0.013), 0.0, cos(float(flock.t) * 0.011)) * 0.6 * delta
				flock.caw = float(flock.caw) - delta
				if float(flock.caw) <= 0.0:
					flock.caw = _rng.randf_range(float(cfg.idle_caw_sec[0]), float(cfg.idle_caw_sec[1]))
					if String(flock.kind) == "crow":
						_sound("caw", (flock.center as Vector3) + Vector3.UP * 40.0, -6.0)
			elif float(flock.t) >= float(flock.air):
				# садятся на другое место, подальше от того, что спугнуло
				flock.state = State.DOWN
				flock.t = 0.0
				flock.perch = _free_perch(flock.center as Vector3)
		State.DOWN:
			flock.center = (flock.center as Vector3).lerp(flock.perch as Vector3, clampf(delta * 0.5, 0.0, 1.0))
			if float(flock.t) >= float(cfg.land_sec):
				flock.state = State.SIT
				flock.center = flock.perch
				flock.t = 0.0


func _free_perch(from: Vector3) -> Vector3:
	var best: Vector3 = from
	var best_d: float = -1.0
	for i: int in range(6):
		var p: Vector3 = _perches[_rng.randi_range(0, _perches.size() - 1)]
		var d: float = p.distance_to(from)
		if d > 20.0 and d < 160.0 and (best_d < 0.0 or d < best_d):
			best = p
			best_d = d
	return best if best_d > 0.0 else _perches[_rng.randi_range(0, _perches.size() - 1)]


## Где птица b стаи сейчас и насколько она «летит» (0 — сидит, 1 — в воздухе).
func _bird_at(flock: Dictionary, b: Dictionary) -> Array:
	var cfg: Dictionary = Balance.BIRDS
	var ground: Vector3 = (flock.perch as Vector3) + (b.off as Vector3)
	var st: int = int(flock.state)
	if st == State.SIT:
		# сидит: голова приподнята
		return [ground, Basis(Vector3.UP, float(b.yaw)) * Basis(Vector3.RIGHT, 0.4), 0.0]
	var t: float = float(flock.t)
	var k: float = 1.0
	if st == State.UP:
		k = smoothstep(0.0, 1.0, clampf((t - float(b.delay)) / float(cfg.climb_sec), 0.0, 1.0))
	elif st == State.DOWN:
		k = 1.0 - smoothstep(0.0, 1.0, clampf(t / float(cfg.land_sec), 0.0, 1.0))
	if k <= 0.0:
		return [ground, Basis(Vector3.UP, float(b.yaw)) * Basis(Vector3.RIGHT, 0.4), 0.0]
	var speed: float = float(cfg.speed) * (0.8 if String(flock.kind) == "crow" else 1.15)
	var ang: float = float(b.ph) + float(b.dir) * float(flock.fly) * speed / float(b.r)
	var air: Vector3 = (flock.center as Vector3) + Vector3(cos(ang), 0.0, sin(ang)) * float(b.r) * k + Vector3.UP * float(b.h) * k
	if st == State.DOWN:
		air = ground.lerp((flock.center as Vector3) + Vector3(cos(ang), 0.0, sin(ang)) * float(b.r) + Vector3.UP * float(b.h), k)
	elif st == State.UP:
		air = ground.lerp(air, k)
	var fwd: Vector3 = Vector3(-sin(ang), 0.0, cos(ang)) * float(b.dir)
	if st == State.UP:
		fwd = (fwd + Vector3.UP * 0.6 * (1.0 - k)).normalized()
	var basis := Basis.looking_at(fwd, Vector3.UP)
	# крен в вираже
	basis = basis * Basis(Vector3.FORWARD, -0.45 * float(b.dir) * k)
	return [air, basis, clampf(k * 3.0, 0.0, 1.0)]


func _draw(_delta: float) -> void:
	if _mm == null:
		return
	var i: int = 0
	for flock: Dictionary in flocks:
		var crow: bool = String(flock.kind) == "crow"
		var size: float = 1.0 if crow else 0.66
		var tint := Color(0.035, 0.035, 0.045) if crow else Color(0.36, 0.38, 0.42)
		for b: Dictionary in flock.birds:
			if not bool(flock.present):
				_mm.set_instance_transform(i, Transform3D(Basis().scaled(Vector3.ZERO), Vector3(0, -500, 0)))
			else:
				var at: Array = _bird_at(flock, b)
				_mm.set_instance_transform(i, Transform3D((at[1] as Basis).scaled(Vector3.ONE * size), (at[0] as Vector3) + Vector3.UP * 0.11 * size))
				_mm.set_instance_color(i, tint)
				_mm.set_instance_custom_data(i, Color(float(b.ph), float(at[2]), 0.0 if crow else 1.0, 0.0))
			i += 1


# ---------------------------------------------------------------- кто спугнул

func _on_noise(pos: Vector3, radius_m: float, kind: String) -> void:
	if not _ready_done:
		return
	var cfg: Dictionary = Balance.BIRDS
	var reach: float = minf(radius_m, float(cfg.step_m)) if kind == "step" else minf(radius_m * float(cfg.noise_k), float(cfg.noise_cap_m))
	for i: int in range(flocks.size()):
		var flock: Dictionary = flocks[i]
		if int(flock.state) == State.SIT and bool(flock.present) and (flock.perch as Vector3).distance_to(pos) <= reach:
			_startle(i, pos)


## Кто-то подошёл вплотную или пробежал рядом: игроки, мародёры, чужие отряды (их шаги в шину шума
## не идут — смотрим сами).
func _scan_walkers() -> void:
	var cfg: Dictionary = Balance.BIRDS
	var walkers: Array = get_tree().get_nodes_in_group("all_players") + get_tree().get_nodes_in_group("marauders")
	for i: int in range(flocks.size()):
		var flock: Dictionary = flocks[i]
		if int(flock.state) != State.SIT or not bool(flock.present):
			continue
		for n: Node in walkers:
			var body := n as CharacterBody3D
			if body == null or not body.is_inside_tree():
				continue
			var d: float = body.global_position.distance_to(flock.perch as Vector3)
			var moving: bool = Vector2(body.velocity.x, body.velocity.z).length() > float(cfg.walk_speed)
			if d <= float(cfg.touch_m) or (moving and d <= float(cfg.near_m)):
				_startle(i, body.global_position)
				break


func _startle(index: int, from: Vector3) -> void:
	if not _is_host():
		return
	Net.broadcast_scene(self, &"_rpc_startle", [index, from, _rng.randf_range(float(Balance.BIRDS.air_sec[0]), float(Balance.BIRDS.air_sec[1]))])
	# взлёт слышат и мародёры — если это включено в балансе
	if float(Balance.BIRDS.ai_noise_m) > 0.0:
		NoiseBus.emit(flocks[index].perch as Vector3, float(Balance.BIRDS.ai_noise_m), "birds")


@rpc("authority", "call_remote", "reliable")
func _rpc_startle(index: int, from: Vector3, air_sec: float) -> void:
	if index < 0 or index >= flocks.size():
		return
	var flock: Dictionary = flocks[index]
	if int(flock.state) != State.SIT:
		return
	var away: Vector3 = (flock.perch as Vector3) - from
	away.y = 0.0
	flock.away = away.normalized() if away.length() > 0.5 else Vector3(1, 0, 0)
	flock.center = flock.perch
	flock.state = State.UP
	flock.t = 0.0
	flock.air = air_sec
	if not bool(flock.present) or DisplayServer.get_name() == "headless":
		return
	var at: Vector3 = (flock.perch as Vector3) + Vector3.UP * 2.0
	_sound("flap", at, 0.0)
	if String(flock.kind) == "crow":
		for k: int in range(_rng.randi_range(3, 5)):
			get_tree().create_timer(0.15 + k * _rng.randf_range(0.28, 0.5)).timeout.connect(func() -> void: _sound("caw", at + Vector3.UP * 6.0, 0.0))


## Сколько стай сейчас в воздухе после испуга (итог, тесты).
func startled() -> int:
	var n: int = 0
	for flock: Dictionary in flocks:
		if not bool(flock.circling) and int(flock.state) != State.SIT:
			n += 1
	return n


# ---------------------------------------------------------------- вид и звук

## Силуэт птицы: тело, хвост, два крыла (UV.x — доля размаха: по ней шейдер машет и складывает).
func _bird_mesh() -> Mesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var tri := func(a: Vector3, b: Vector3, c: Vector3, ua: float, ub: float, uc: float) -> void:
		var n: Vector3 = (b - a).cross(c - a).normalized()
		for pair: Array in [[a, ua], [b, ub], [c, uc]]:
			st.set_normal(n)
			st.set_uv(Vector2(float(pair[1]), 0.0))
			st.add_vertex(pair[0])
	# тело — вытянутый ромб, клюв вперёд (−Z)
	var nose := Vector3(0, 0.0, -0.24)
	var tail := Vector3(0, 0.0, 0.2)
	var ring: Array = [Vector3(0, 0.06, -0.02), Vector3(0.055, 0, 0), Vector3(0, -0.055, 0), Vector3(-0.055, 0, 0)]
	for i: int in range(4):
		tri.call(nose, ring[(i + 1) % 4], ring[i], 0.0, 0.0, 0.0)
		tri.call(tail, ring[i], ring[(i + 1) % 4], 0.0, 0.0, 0.0)
	# хвост веером
	tri.call(Vector3(0, 0.01, 0.16), Vector3(0.075, 0.0, 0.36), Vector3(-0.075, 0.0, 0.36), 0.0, 0.0, 0.0)
	# крылья
	for sx: float in [-1.0, 1.0]:
		var r0 := Vector3(sx * 0.045, 0.02, -0.1)
		var r1 := Vector3(sx * 0.045, 0.02, 0.09)
		var m0 := Vector3(sx * 0.28, 0.02, -0.07)
		var m1 := Vector3(sx * 0.3, 0.02, 0.13)
		var tip := Vector3(sx * 0.5, 0.02, 0.05)
		tri.call(r0, m0, r1, 0.09, 0.56, 0.09)
		tri.call(r1, m0, m1, 0.09, 0.56, 0.6)
		tri.call(m0, tip, m1, 0.56, 1.0, 0.6)
	var mesh: ArrayMesh = st.commit()
	var mat := ShaderMaterial.new()
	var shader := Shader.new()
	shader.code = SHADER
	mat.shader = shader
	mesh.surface_set_material(0, mat)
	return mesh


func _sound(kind: String, at: Vector3, db: float) -> void:
	if DisplayServer.get_name() == "headless":
		return
	if not _sounds.has(kind):
		_sounds[kind] = _synth(kind)
	var p := AudioStreamPlayer3D.new()
	p.stream = _sounds[kind]
	p.bus = &"World"
	p.volume_db = float(Balance.BIRDS.sound_db) + db
	p.unit_size = float(Balance.BIRDS.sound_unit)
	p.max_distance = float(Balance.BIRDS.sound_max_m)
	p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	p.pitch_scale = _rng.randf_range(0.86, 1.12)
	add_child(p)
	p.global_position = at
	p.finished.connect(p.queue_free)
	p.play()


## Карканье (хриплый падающий тон) и хлопки крыльев стаи — простым синтезом.
static func _synth(kind: String) -> AudioStreamWAV:
	var rate: int = 22050
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(kind)
	var n: int = int(rate * (0.3 if kind == "caw" else 1.5))
	var data := PackedByteArray()
	data.resize(n * 2)
	var phase: float = 0.0
	var low: float = 0.0
	for i: int in range(n):
		var t: float = float(i) / float(rate)
		var v: float = 0.0
		if kind == "caw":
			var f: float = lerpf(640.0, 470.0, t / 0.3)
			phase += f / float(rate)
			var saw: float = fposmod(phase, 1.0) * 2.0 - 1.0
			var rough: float = 0.55 + 0.45 * sin(TAU * 74.0 * t)
			var env: float = clampf(t / 0.02, 0.0, 1.0) * clampf((0.3 - t) / 0.1, 0.0, 1.0)
			v = (saw * rough + sin(TAU * f * 2.5 * t) * 0.3 + rng.randf_range(-1.0, 1.0) * 0.3) * env * 0.5
		else:
			# хлопки: частые короткие шумовые удары, затихают
			var beat: float = fposmod(t * 11.0 + sin(t * 3.0) * 0.4, 1.0)
			var hit: float = exp(-beat * 9.0)
			low = lerpf(low, rng.randf_range(-1.0, 1.0), 0.35)
			v = low * hit * clampf((1.5 - t) / 1.2, 0.0, 1.0) * 0.6
		data.encode_s16(i * 2, int(clampf(v, -1.0, 1.0) * 32000.0))
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = rate
	wav.data = data
	return wav
