extends Node3D
## Люминесцентный светильник, который ещё тускло горит в брошенном общежитии (владелец 2026-11-01: «кое-где лампы
## тускло горят», мигающих — 1–2 на этаж): свет и свечение трубок вместе — тусклый ровный фон с дрожью, сбоями
## пачкой (старый стартер щёлкает), изредка гаснет на секунду-две и разгорается миганием. Ставит dorm_electrics.gd
## под светильник с трубками; материалы трубок — свои копии со свечением.

const COLOR: Color = Color(0.86, 0.95, 0.88)     # ЛБ-40 «белый» на износе — холодный, чуть в зелень
const ENERGY: float = 0.5
const RANGE: float = 6.5
const GLOW: float = 0.75                         # свечение трубки при полном накале

var seed_value: int = 1
## Сколько трубок горит (у «одной и обломка» свет вдвое тусклее).
var tubes: int = 2
var tube_materials: Array[StandardMaterial3D] = []

var _light: OmniLight3D
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _t: float = 0.0
var _next: float = 0.0
## Сбой пачкой: сколько щелчков осталось и сколько длится текущий; погас надолго — сколько ещё темно.
var _blinks: int = 0
var _blink_left: float = 0.0
var _blink_on: bool = true
var _dark_left: float = 0.0


func _ready() -> void:
	_rng.seed = seed_value
	_light = OmniLight3D.new()
	_light.name = "Свет"
	_light.position = Vector3(0.0, -0.2, 0.0)
	_light.light_color = COLOR
	_light.omni_range = RANGE
	_light.omni_attenuation = 1.4
	_light.shadow_enabled = true
	_light.shadow_bias = 0.04
	_light.omni_shadow_mode = OmniLight3D.SHADOW_CUBE
	_light.distance_fade_enabled = true
	_light.distance_fade_begin = 22.0
	_light.distance_fade_length = 6.0
	_light.light_bake_mode = Light3D.BAKE_DYNAMIC
	_light.add_to_group("dorm_flicker")
	add_child(_light)
	_next = _rng.randf_range(1.0, 6.0)
	_apply(1.0)


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_t += delta
	var level: float = 1.0
	if _dark_left > 0.0:
		_dark_left -= delta
		level = 0.0
		if _dark_left <= 0.0:
			_blinks = _rng.randi_range(4, 9)     # разгорается миганием
			_blink_left = 0.0
	elif _blinks > 0:
		_blink_left -= delta
		if _blink_left <= 0.0:
			_blink_on = not _blink_on
			_blink_left = _rng.randf_range(0.03, 0.14) if _blink_on else _rng.randf_range(0.02, 0.09)
			if _blink_on:
				_blinks -= 1
		level = 1.0 if _blink_on else 0.04
	else:
		_next -= delta
		if _next <= 0.0:
			if _rng.randf() < 0.18:
				_dark_left = _rng.randf_range(0.5, 2.4)
			else:
				_blinks = _rng.randi_range(2, 6)
				_blink_on = true
			_next = _rng.randf_range(2.5, 11.0)
		# тусклый накал дрожит: износ трубки и сети
		level = 0.86 + 0.08 * sin(_t * 9.7 + float(seed_value % 97)) * sin(_t * 2.3) + 0.04 * _rng.randf_range(-1.0, 1.0)
	_apply(level)


func _apply(level: float) -> void:
	var k: float = level * (1.0 if tubes >= 2 else 0.55)
	_light.light_energy = ENERGY * k
	_light.visible = k > 0.01
	for mat: StandardMaterial3D in tube_materials:
		mat.emission_energy_multiplier = GLOW * level
