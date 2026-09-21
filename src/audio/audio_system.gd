extends Node
## Звук без внешних файлов: все сэмплы синтезируются при старте (шум + огибающие + простые фильтры)
## в AudioStreamWAV. Это запасной вариант по правилу проекта; записанные звуки из assets/audio
## подменят синтетику по тем же именам, когда появятся. Autoload `Audio`.

const MIX_RATE := 22050

## Громкость и дальность по виду звука: дБ, единица дистанции (м, где громкость номинальная), предел слышимости.
const KINDS := {
	"shot_pistol": {"db": 2.0, "unit": 8.0, "max": 90.0},
	"shot_ai": {"db": 1.0, "unit": 8.0, "max": 90.0},
	"step": {"db": -16.0, "unit": 3.0, "max": 22.0},
	"step_ai": {"db": -14.0, "unit": 3.0, "max": 26.0},
	"door": {"db": -6.0, "unit": 4.0, "max": 30.0},
	"hit": {"db": -4.0, "unit": 5.0, "max": 30.0},
	"reload": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"impact_hard": {"db": -6.0, "unit": 5.0, "max": 40.0},
	"impact_metal": {"db": -5.0, "unit": 6.0, "max": 45.0},
	"impact_glass": {"db": -4.0, "unit": 6.0, "max": 45.0},
	"impact_soft": {"db": -10.0, "unit": 4.0, "max": 30.0},
}

var _streams: Dictionary = {}
var _rng := RandomNumberGenerator.new()
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
	var amb := _make(_ambient_loop(6.0))
	amb.loop_mode = AudioStreamWAV.LOOP_FORWARD
	amb.loop_end = amb.data.size() / 2
	_ambient = AudioStreamPlayer.new()
	_ambient.stream = amb
	_ambient.volume_db = -22.0
	_ambient.autoplay = true
	add_child(_ambient)


## Звук в точке мира. Игрок слушает из своей позиции (AudioListener3D на игроке).
func play(kind: String, pos: Vector3, extra_db: float = 0.0) -> void:
	var stream: AudioStreamWAV = _streams.get(kind)
	if stream == null:
		return
	var spec: Dictionary = KINDS.get(kind, {"db": 0.0, "unit": 5.0, "max": 40.0})
	var p := AudioStreamPlayer3D.new()
	p.stream = stream
	p.volume_db = float(spec.db) + extra_db
	p.unit_size = float(spec.unit)
	p.max_distance = float(spec["max"])
	p.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	p.pitch_scale = _rng.randf_range(0.92, 1.08)
	p.finished.connect(p.queue_free)
	get_tree().current_scene.add_child(p)
	p.global_position = pos
	p.play()


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
