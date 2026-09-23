extends Node
## Звук: записи из assets/audio (см. tools/import_audio.py и CREDITS), случайный вариант на
## каждое проигрывание; выстрелы издалека — отдельными «дальними» записями. Для всего, у чего
## записей нет (или без assets/audio вовсе), при старте синтезируется запасной звук
## (шум + огибающие + простые фильтры) — игра обязана звучать и так. Autoload `Audio`.

const MIX_RATE := 22050

## Громкость и дальность по виду звука: дБ, единица дистанции (м, где громкость номинальная), предел слышимости.
const KINDS := {
	"shot_pistol": {"db": 2.0, "unit": 8.0, "max": 90.0},
	"shot_ai": {"db": 1.0, "unit": 8.0, "max": 90.0},
	"step": {"db": -16.0, "unit": 3.0, "max": 22.0},
	"step_ai": {"db": -14.0, "unit": 3.0, "max": 26.0},
	# шаги по поверхностям (Audio.step): occlude — за стеной глуше
	"step_stone": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true},
	"step_stone_run": {"db": -12.0, "unit": 3.0, "max": 34.0, "occlude": true},
	"step_dirt": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true},
	"step_dirt_run": {"db": -12.0, "unit": 3.0, "max": 34.0, "occlude": true},
	"step_snow": {"db": -16.0, "unit": 3.0, "max": 24.0, "occlude": true},
	"step_snow_run": {"db": -13.0, "unit": 3.0, "max": 30.0, "occlude": true},
	"step_metal": {"db": -17.0, "unit": 3.0, "max": 30.0, "occlude": true},
	"door": {"db": -6.0, "unit": 4.0, "max": 30.0},
	"hit": {"db": -4.0, "unit": 5.0, "max": 30.0},
	"reload": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"impact_hard": {"db": -6.0, "unit": 5.0, "max": 40.0},
	"impact_metal": {"db": -5.0, "unit": 6.0, "max": 45.0},
	"impact_glass": {"db": -4.0, "unit": 6.0, "max": 45.0},
	"impact_soft": {"db": -10.0, "unit": 4.0, "max": 30.0},
	"shot_rifle": {"db": 2.0, "unit": 9.0, "max": 110.0},
	"shot_shotgun": {"db": 4.0, "unit": 9.0, "max": 110.0},
	"shot_bolt": {"db": 5.0, "unit": 12.0, "max": 160.0},
	"step_run": {"db": -12.0, "unit": 3.0, "max": 28.0},
	"death": {"db": -2.0, "unit": 5.0, "max": 35.0},
	"fall": {"db": -6.0, "unit": 4.0, "max": 25.0},
	"reload_pistol": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"reload_rifle": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"reload_shotgun": {"db": -6.0, "unit": 3.0, "max": 18.0},
	"bolt": {"db": -6.0, "unit": 3.0, "max": 18.0},
	"pin": {"db": -10.0, "unit": 2.0, "max": 10.0},
	"debris": {"db": -4.0, "unit": 6.0, "max": 40.0},
	"explosion": {"db": 8.0, "unit": 14.0, "max": 220.0},
}

## Записанные звуки: вид -> ["группа/префикс", ...] в assets/audio. Префикс ловит только
## файлы «префикс + номер»: "guns/pistol_" не цепляет "pistol_far_01".
const SAMPLES := {
	"shot_pistol": ["guns/pistol_"], "shot_ai": ["guns/pistol_"], "shot_rifle": ["guns/carbine_"],
	"shot_shotgun": ["guns/shotgun_"], "shot_bolt": ["guns/marksman_"],
	"step": ["steps/stone_"], "step_run": ["steps/stone_run_"], "step_ai": ["steps/stone_"],
	"step_stone": ["steps/stone_"], "step_stone_run": ["steps/stone_run_"],
	"step_dirt": ["steps/dirt_"], "step_dirt_run": ["steps/dirt_run_"],
	"step_snow": ["steps/snow_"], "step_snow_run": ["steps/snow_run_"], "step_metal": ["steps/metal_"],
	"door": ["world/door_"], "hit": ["body/hit_"], "fall": ["body/fall_"],
	"death": ["voice/rattle_groan_", "voice/rattle_gurgle_"],
	"reload": ["guns/reload_pistol_"], "reload_pistol": ["guns/reload_pistol_"],
	"reload_rifle": ["guns/reload_rifle_"], "reload_shotgun": ["guns/reload_shotgun_"], "bolt": ["guns/reload_shotgun_"],
	"impact_hard": ["hits/concrete_", "hits/hard_"], "impact_metal": ["hits/metal_"],
	"impact_glass": ["hits/glass_"], "impact_soft": ["hits/wood_"], "debris": ["world/debris_"],
}
## Выстрел дальше FAR_M от слушателя звучит «дальней» записью: хлопок с эхом, без щелчка.
const FAR := {
	"shot_pistol": "guns/pistol_far_", "shot_ai": "guns/pistol_far_", "shot_rifle": "guns/carbine_far_",
	"shot_shotgun": "guns/shotgun_far_", "shot_bolt": "guns/marksman_far_",
}
const FAR_M := 30.0
## Поверхность под ногами (Surfaces) → набор записей шагов. Металл — камень + звонкий слой
## step_metal (запись steps/metal_*, если есть, иначе синтез).
const STEP_SET := {
	"tile": "stone", "concrete": "stone", "plastic": "stone", "wood": "stone", "glass": "stone",
	"metal": "stone", "asphalt": "dirt", "cardboard": "dirt", "fabric": "dirt", "snow": "snow",
}

## Сыгран шаг: вид звука и поверхность (для тестов и отладки).
signal stepped(kind: String, surface: String, pos: Vector3)

var _samples: Dictionary = {}
var _far: Dictionary = {}

var _streams: Dictionary = {}
var _rng := RandomNumberGenerator.new()
## Последний сыгранный вариант по виду — подряд один и тот же не звучит.
var _last_pick: Dictionary = {}
var _ambient: AudioStreamPlayer


func _ready() -> void:
	_rng.randomize()
	_streams["shot_pistol"] = _make(_gunshot(0.32, 1.0))
	_streams["shot_ai"] = _make(_gunshot(0.36, 0.85))
	_streams["step"] = _make(_footstep())
	_streams["step_ai"] = _make(_footstep())
	_streams["door"] = _make(_door())
	_streams["hit"] = _make(_hit())
	_streams["reload"] = _make(_reload())
	_streams["impact_hard"] = _make(_impact_hard())
	_streams["impact_metal"] = _make(_impact_metal())
	_streams["impact_glass"] = _make(_impact_glass())
	_streams["impact_soft"] = _make(_impact_soft())
	_streams["shot_rifle"] = _make(_gunshot(0.28, 1.25))
	_streams["shot_shotgun"] = _make(_gunshot(0.55, 0.7))
	_streams["shot_bolt"] = _make(_gunshot(0.65, 1.35))
	_streams["step_run"] = _streams["step"]
	for k in ["step_stone", "step_stone_run", "step_dirt", "step_dirt_run", "step_snow", "step_snow_run"]:
		_streams[k] = _streams["step"]
	_streams["step_metal"] = _make(_step_metal())
	_streams["death"] = _streams["hit"]
	_streams["fall"] = _streams["hit"]
	for k in ["reload_pistol", "reload_rifle", "reload_shotgun", "bolt", "pin"]:
		_streams[k] = _streams["reload"]
	_streams["debris"] = _streams["impact_hard"]
	_streams["explosion"] = _make(_explosion())
	_load_samples()
	_ambient = AudioStreamPlayer.new()
	var amb_path := "res://assets/audio/ambient/building_wind_drips.ogg"
	if ResourceLoader.exists(amb_path):
		var ogg: AudioStreamOggVorbis = load(amb_path)
		ogg.loop = true
		_ambient.stream = ogg
		_ambient.volume_db = -16.0
	else:
		var amb := _make(_ambient_loop(6.0))
		amb.loop_mode = AudioStreamWAV.LOOP_FORWARD
		amb.loop_end = amb.data.size() / 2
		_ambient.stream = amb
		_ambient.volume_db = -22.0
	_ambient.autoplay = true
	add_child(_ambient)


## Звук в точке мира. Игрок слушает из своей позиции (AudioListener3D на игроке).
## pitch 0 — случайный тон ±8 %.
func play(kind: String, pos: Vector3, extra_db: float = 0.0, pitch: float = 0.0) -> void:
	var stream: AudioStream = _pick(kind, pos)
	if stream == null:
		return
	var spec: Dictionary = KINDS.get(kind, {"db": 0.0, "unit": 5.0, "max": 40.0})
	var listener := _listener_pos()
	var ears := _has_ears()
	if ears and listener.distance_to(pos) > float(spec["max"]):
		return
	var p := AudioStreamPlayer3D.new()
	p.stream = stream
	p.volume_db = float(spec.db) + extra_db
	p.unit_size = float(spec.unit)
	p.max_distance = float(spec["max"])
	p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	p.pitch_scale = pitch if pitch > 0.0 else _rng.randf_range(0.92, 1.08)
	if ears and bool(spec.get("occlude", false)) and _occluded(listener, pos):
		# за стеной: тише и без верхов
		p.volume_db -= Balance.AUDIO_OCCLUDED_DB
		p.attenuation_filter_cutoff_hz = Balance.AUDIO_OCCLUDED_CUTOFF
	p.finished.connect(p.queue_free)
	get_tree().current_scene.add_child(p)
	p.global_position = pos
	p.play()


## Шаг в точке pos: поверхность под ногами, бег/шаг, мародёр (ботинки ниже и громче), левая/правая.
func step(pos: Vector3, run: bool, ai: bool, extra_db: float, left: bool) -> void:
	# дальше, чем слышно бег, — не считаем (24 мародёра шагают всё время)
	if _has_ears() and _listener_pos().distance_to(pos) > float(KINDS.step_stone_run["max"]):
		return
	var surf := _surface_under(pos)
	var sset := String(STEP_SET.get(surf, "stone"))
	var pitch := (0.97 if left else 1.02) * (0.93 if ai else 1.0) * _rng.randf_range(0.97, 1.03)
	var db := extra_db + (1.5 if ai else 0.0)
	var kind := "step_%s%s" % [sset, "_run" if run else ""]
	play(kind, pos, db, pitch)
	stepped.emit(kind, surf, pos)
	if surf == "metal":
		play("step_metal", pos, db + (2.0 if run else 0.0), pitch)


## Из чего пол под точкой (Surfaces), "concrete" — если не понять.
func _surface_under(pos: Vector3) -> String:
	var world := get_viewport().find_world_3d() if get_viewport() else null
	if world == null:
		return "concrete"
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.4, pos + Vector3.DOWN * 0.6, Hitscan.LAYER_WORLD)
	var hit := world.direct_space_state.intersect_ray(q)
	# бесконечная «земля» (WorldBoundary) лежит над полами двора — смотрим, что под ней
	if not hit.is_empty() and _is_boundary(hit):
		q.exclude = [(hit.collider as CollisionObject3D).get_rid()]
		hit = world.direct_space_state.intersect_ray(q)
	return Surfaces.kind_at(hit) if not hit.is_empty() else "concrete"


func _is_boundary(hit: Dictionary) -> bool:
	var co := hit.get("collider") as CollisionObject3D
	if co == null:
		return false
	var sn := co.shape_owner_get_owner(co.shape_find_owner(int(hit.get("shape", 0)))) as CollisionShape3D
	return sn != null and sn.shape is WorldBoundaryShape3D


## Есть кто слушает (камера или AudioListener3D) — иначе расстояние до «ушей» не знаем.
func _has_ears() -> bool:
	var vp := get_viewport()
	return vp != null and (vp.get_audio_listener_3d() != null or vp.get_camera_3d() != null)


## Между ушами и источником — стена или дверь.
func _occluded(listener: Vector3, pos: Vector3) -> bool:
	var world := get_viewport().find_world_3d() if get_viewport() else null
	if world == null or listener.distance_to(pos) < 1.5:
		return false
	var q := PhysicsRayQueryParameters3D.create(listener, pos + Vector3.UP * 0.4, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	return not world.direct_space_state.intersect_ray(q).is_empty()


## Запись (или дальняя запись), иначе синтетика.
func _pick(kind: String, pos: Vector3) -> AudioStream:
	if _far.has(kind):
		var listener := _listener_pos()
		if listener.distance_to(pos) > FAR_M:
			var far: Array = _far[kind]
			return far[_rng.randi_range(0, far.size() - 1)]
	if _samples.has(kind):
		var arr: Array = _samples[kind]
		var i := _rng.randi_range(0, arr.size() - 1)
		if arr.size() > 1 and i == int(_last_pick.get(kind, -1)):
			i = (i + 1 + _rng.randi_range(0, arr.size() - 2)) % arr.size()
		_last_pick[kind] = i
		return arr[i]
	return _streams.get(kind)


func _listener_pos() -> Vector3:
	var vp := get_viewport()
	var l := vp.get_audio_listener_3d() if vp else null
	if l:
		return l.global_position
	var cam := vp.get_camera_3d() if vp else null
	return cam.global_position if cam else Vector3.ZERO


func _load_samples() -> void:
	for kind in SAMPLES:
		var arr := _load_prefixes(SAMPLES[kind])
		if not arr.is_empty():
			_samples[kind] = arr
	for kind in FAR:
		var arr := _load_prefixes([FAR[kind]])
		if not arr.is_empty():
			_far[kind] = arr


func _load_prefixes(prefixes: Array) -> Array:
	var out: Array = []
	for pr in prefixes:
		var parts := String(pr).split("/")
		var dir := "res://assets/audio/%s/" % parts[0]
		if not DirAccess.dir_exists_absolute(dir):
			continue
		for f in ResourceLoader.list_directory(dir):
			var stem := String(f).get_basename()
			if not stem.begins_with(parts[1]):
				continue
			if not stem.trim_prefix(parts[1]).is_valid_int():
				continue
			var st: AudioStream = load(dir + f)
			if st:
				out.append(st)
	return out


# ---------------------------------------------------------------- синтез

func _make(samples: PackedFloat32Array) -> AudioStreamWAV:
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = MIX_RATE
	wav.stereo = false
	var bytes := PackedByteArray()
	bytes.resize(samples.size() * 2)
	for i in range(samples.size()):
		var v := int(clampf(samples[i], -1.0, 1.0) * 32767.0)
		bytes.encode_s16(i * 2, v)
	wav.data = bytes
	return wav


func _noise() -> float:
	return _rng.randf_range(-1.0, 1.0)


## Выстрел: щелчок белого шума с быстрым спадом + низкий удар + хвост.
func _gunshot(dur: float, brightness: float) -> PackedFloat32Array:
	var n := int(dur * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		var crack := _noise() * exp(-t * 60.0)
		lp += (_noise() - lp) * (0.25 * brightness)
		var body := lp * exp(-t * 14.0) * 1.6
		var thump := sin(TAU * 70.0 * t) * exp(-t * 18.0) * 0.9
		out[i] = tanh((crack * 1.2 + body + thump) * 1.4)
	return out


## Шаг: короткий глухой шорох.
func _footstep() -> PackedFloat32Array:
	var n := int(0.11 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		lp += (_noise() - lp) * 0.18
		var env := minf(1.0, t * 400.0) * exp(-t * 45.0)
		out[i] = lp * env * 1.8
	return out


## Звонкий слой шага по металлу (решётка, лист, эскалатор): пара негармоничных обертонов + щелчок.
func _step_metal() -> PackedFloat32Array:
	var n := int(0.22 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	for i in range(n):
		var t := float(i) / MIX_RATE
		var ring := sin(TAU * 690.0 * t) * 0.5 + sin(TAU * 1130.0 * t) * 0.35 + sin(TAU * 1870.0 * t) * 0.2
		var click := _noise() * exp(-t * 180.0)
		out[i] = (ring * exp(-t * 26.0) * 0.55 + click * 0.5) * minf(1.0, t * 900.0)
	return out


## Дверь: скрип — свип синуса с дрожанием + шорох.
func _door() -> PackedFloat32Array:
	var n := int(0.55 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var phase := 0.0
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		var f := 210.0 - 90.0 * t + sin(t * 40.0) * 12.0
		phase += TAU * f / MIX_RATE
		lp += (_noise() - lp) * 0.1
		var env := sin(PI * t / 0.55)
		out[i] = (sin(phase) * 0.35 + sin(phase * 2.01) * 0.12 + lp * 0.5) * env
	return out


## Попадание: глухой удар.
func _hit() -> PackedFloat32Array:
	var n := int(0.18 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		lp += (_noise() - lp) * 0.08
		out[i] = (lp * 2.0 + sin(TAU * 55.0 * t) * 0.6) * exp(-t * 28.0)
	return out


## Перезарядка: два металлических щелчка.
func _reload() -> PackedFloat32Array:
	var n := int(0.45 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	for i in range(n):
		var t := float(i) / MIX_RATE
		var v := 0.0
		for click: float in [0.0, 0.27]:
			var dt: float = t - click
			if dt >= 0.0:
				v += _noise() * exp(-dt * 220.0) * 0.8 + sin(TAU * 1800.0 * dt) * exp(-dt * 90.0) * 0.3
		out[i] = v
	return out


## Удар по бетону/плитке: сухой щелчок с крошкой.
func _impact_hard() -> PackedFloat32Array:
	var n := int(0.14 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var prev := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		var w := _noise()
		var hp := w - prev * 0.6
		prev = w
		out[i] = hp * exp(-t * 55.0) * 1.3 + _noise() * exp(-t * 25.0) * 0.25
	return out


## Удар по металлу: звон.
func _impact_metal() -> PackedFloat32Array:
	var n := int(0.32 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var f := _rng.randf_range(1900.0, 2600.0)
	for i in range(n):
		var t := float(i) / MIX_RATE
		out[i] = _noise() * exp(-t * 90.0) * 0.9 + (sin(TAU * f * t) * 0.5 + sin(TAU * f * 1.51 * t) * 0.25) * exp(-t * 14.0)
	return out


## Удар по стеклу: звон осколков.
func _impact_glass() -> PackedFloat32Array:
	var n := int(0.5 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var tones: Array[float] = []
	for k in range(5):
		tones.append(_rng.randf_range(2800.0, 6500.0))
	for i in range(n):
		var t := float(i) / MIX_RATE
		var v := _noise() * exp(-t * 70.0) * 0.8
		for k in range(tones.size()):
			var on := 0.03 * k
			if t > on:
				v += sin(TAU * tones[k] * (t - on)) * exp(-(t - on) * 12.0) * 0.18
		out[i] = v
	return out


## Удар по дереву/картону: глухой тук.
func _impact_soft() -> PackedFloat32Array:
	var n := int(0.12 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		lp += (_noise() - lp) * 0.12
		out[i] = lp * exp(-t * 40.0) * 2.2 + sin(TAU * 140.0 * t) * exp(-t * 35.0) * 0.4
	return out


## Взрыв: удар низкой частоты, рваный шум, долгий гул-хвост.
func _explosion() -> PackedFloat32Array:
	var n := int(1.8 * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var lp := 0.0
	var lp2 := 0.0
	for i in range(n):
		var t := float(i) / MIX_RATE
		lp += (_noise() - lp) * 0.06
		lp2 += (lp - lp2) * 0.08
		var boom := sin(TAU * (48.0 - 20.0 * t) * t) * exp(-t * 4.0) * 1.2
		var crack := _noise() * exp(-t * 35.0)
		out[i] = tanh((boom + lp2 * 6.0 * exp(-t * 1.8) + crack) * 1.3)
	return out


## Фон: коричневый шум (ветер в пустом здании), зациклен.
func _ambient_loop(dur: float) -> PackedFloat32Array:
	var n := int(dur * MIX_RATE)
	var out := PackedFloat32Array()
	out.resize(n)
	var brown := 0.0
	var lp := 0.0
	for i in range(n):
		brown = clampf(brown + _noise() * 0.02, -1.0, 1.0) * 0.998
		lp += (brown - lp) * 0.05
		var t := float(i) / MIX_RATE
		var swell := 0.7 + 0.3 * sin(TAU * t / dur)
		out[i] = lp * swell * 2.5
	# сшивка петли: плавно к началу
	var fade := int(0.05 * MIX_RATE)
	for i in range(fade):
		var k := float(i) / fade
		out[n - fade + i] = out[n - fade + i] * (1.0 - k) + out[i] * k
	return out
