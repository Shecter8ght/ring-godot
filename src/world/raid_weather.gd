class_name RaidWeather
extends Node
## Погода в рейде (RaidConditions.current.weather) и её смена по ходу рейда:
## дождь — капли, брызги и лужи шейдерами (RainFx: под крышей не капает и сухо), шум дождя (под
## крышей — глухо, по перекрытию), гром; хуже слышно (радиус шума × hear) и видно на улице;
## ясно — может начаться дождь (раскаты за минуту), туман — может рассеяться (снайперы снова
## снайперы); жара — на улице пересвечено и марево, если на тебе нет очков от солнца.
## Когда что начнётся, решает хост и рассылает всем (узел с одним именем у всех peer).
## Создаёт SectorLevel рядом с RaidAtmosphere.

signal changed

static var current: RaidWeather

var _rng := RandomNumberGenerator.new()
## Через сколько секунд рейда: гром перед дождём, дождь, туман рассеется (INF — не будет).
var _rain_at: float = INF
var _fog_lift_at: float = INF
var _t: float = 0.0
var _thundered: bool = false
var _rain: RainFx
var _rain_k: float = 0.0
var _rain_sound: AudioStreamPlayer
var _haze: ColorRect
var _haze_k: float = 0.0
var _indoor_t: float = 0.0
var _outdoor: bool = true
## Сырость земли: плёнка и лужи (0..1) — копятся в дождь, сохнут после (Balance.WET_GROUND).
var wet: float = 0.0
## Видимость ниже порога (туман) — зажигает заградительные огни днём; с гистерезисом.
var low_visibility: bool = false
var _e: Environment
var _fog_target: float = 0.0
var _fog_sky_target: float = 0.4
var _fog_ready: bool = false
## Туман погоды (на улице) и поправка на крышу над головой своего игрока (1 — улица).
var _fog_base: float = 0.0
## 0 — на улице, 1 — под крышей ТЦ; плавно (Balance.INDOOR.sec).
var _roof: float = 0.0
var puddles: float = 0.0
var _schedule_ready: bool = false
var _known: Array[int] = []


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null
	# материал асфальта общий (кэш) — следующий уровень начинается сухим
	wet = 0.0
	puddles = 0.0
	_push_wet(0.0)


func _ready() -> void:
	_rng.randomize()
	Net.scenes_changed.connect(_share_schedule)
	_apply_static()
	# рейд начался в дождь — льёт давно: мокро, лужи налиты
	if is_raining():
		wet = float(Balance.WET_GROUND.start[0])
		puddles = float(Balance.WET_GROUND.start[1])
	_push_wet(0.0)
	if not Net.is_networked() or multiplayer.is_server():
		var w := String(RaidConditions.current.weather)
		var sch: Dictionary = Balance.WEATHER_CHANGE
		var rain_at := INF
		var fog_at := INF
		if w == "clear" and _rng.randf() < float(sch.rain_chance):
			rain_at = _rng.randf_range(float(sch.rain_after[0]), float(sch.rain_after[1]))
		if w == "fog" and _rng.randf() < float(sch.fog_lift_chance):
			fog_at = _rng.randf_range(float(sch.fog_lift_after[0]), float(sch.fog_lift_after[1]))
		if Net.is_networked():
			# у клиентов узел погоды появляется вместе с уровнем — подождать
			await get_tree().create_timer(2.0).timeout
			_rpc_schedule(rain_at if rain_at != INF else -1.0, fog_at if fog_at != INF else -1.0)
			_schedule_ready = true
			_share_schedule()
		else:
			_rpc_schedule(rain_at if rain_at != INF else -1.0, fog_at if fog_at != INF else -1.0)


@rpc("authority", "call_local", "reliable")
func _rpc_schedule(rain_at: float, fog_at: float) -> void:
	_rain_at = rain_at if rain_at >= 0.0 else INF
	_fog_lift_at = fog_at if fog_at >= 0.0 else INF


## Готовый Weather получает расписание после загрузки, а не по фиксированной задержке.
func _share_schedule() -> void:
	if not Net.is_host() or not _schedule_ready:
		return
	var here: Array[int] = []
	for peer: int in multiplayer.get_peers():
		if Net.visible_in(peer, "raid"):
			here.append(peer)
			if not peer in _known:
				_receive_schedule.rpc_id(peer, maxf(0.0, _rain_at - _t) if _rain_at != INF else -1.0,
					maxf(0.0, _fog_lift_at - _t) if _fog_lift_at != INF else -1.0,
					String(RaidConditions.current.weather))
	_known = here


@rpc("authority", "call_remote", "reliable")
func _receive_schedule(rain_left: float, fog_left: float, weather: String) -> void:
	_rpc_schedule(_t + rain_left if rain_left >= 0.0 else -1.0, _t + fog_left if fog_left >= 0.0 else -1.0)
	RaidConditions.current["weather"] = weather
	_apply_static()


func is_raining() -> bool:
	return String(RaidConditions.current.weather) == "rain"


## Всё, что зависит от погоды на старте (и после смены).
func _apply_static() -> void:
	var w := String(RaidConditions.current.weather)
	_fog_target = 0.03 if w == "fog" else (0.006 if w == "rain" else 0.0)
	_fog_sky_target = 0.9 if w == "fog" else 0.4
	# ночью небо не серит (RaidAtmosphere: звёзды на чёрном)
	if String(RaidConditions.current.time) == "night":
		_fog_sky_target = minf(_fog_sky_target, float(Balance.NIGHT_ENV.fog_sky))
	var e := _env()
	if e:
		e.fog_light_color = Color(0.62, 0.64, 0.66) if String(RaidConditions.current.time) != "night" else Color(0.05, 0.06, 0.08)
		# в начале рейда — сразу как есть; дальше туман сгущается и рассеивается плавно (_tick_fog)
		if not _fog_ready:
			_fog_ready = true
			_fog_base = _fog_target
			e.fog_density = _fog_base
			e.fog_sky_affect = _fog_sky_target
			e.fog_enabled = _fog_target > 0.0
	_update_visibility()
	_set_overcast(w == "rain")
	_set_rain(w == "rain")
	changed.emit()


func _env() -> Environment:
	if _e == null:
		var we := get_parent().find_child("WorldEnvironment", false, false) as WorldEnvironment
		if we:
			_e = we.environment
	return _e


## Туман меняется за Balance.OUTDOOR_LIGHTS.fog_change_sec, а не скачком («рассеялся» — постепенно).
func _tick_fog(delta: float) -> void:
	var e := _env()
	if e == null or not _fog_ready:
		return
	var sec := float(Balance.OUTDOOR_LIGHTS.fog_change_sec)
	_fog_base = move_toward(_fog_base, _fog_target, 0.03 * delta / sec)
	# под крышей ТЦ туман реже (у каждого peer — по своему игроку, это только картинка)
	var ind: Dictionary = Balance.INDOOR
	_roof = move_toward(_roof, 0.0 if _outdoor else 1.0, delta / float(ind.sec))
	e.fog_density = _fog_base * lerpf(1.0, float(ind.fog_k), _roof)
	e.fog_sky_affect = move_toward(e.fog_sky_affect, _fog_sky_target, 0.5 * delta / sec)
	e.fog_enabled = e.fog_density > 0.00001
	_update_visibility()


## Видимость на улице, м (Кошмидер: контраст падает до 2 % на расстоянии 3.912 / плотность).
## Считается по туману погоды — не по тому, что видит игрок под крышей.
func visibility_m() -> float:
	var e := _env()
	if e == null:
		return INF
	var d := (_fog_base if _fog_ready else 0.0) + (e.volumetric_fog_density if e.volumetric_fog_enabled else 0.0)
	return 3.912 / d if d > 0.00001 else INF


## Низкая видимость — с гистерезисом: зажглось ниже fog_on_m, гаснет только выше fog_off_m.
func _update_visibility() -> void:
	var v := visibility_m()
	if low_visibility and v > float(Balance.OUTDOOR_LIGHTS.fog_off_m):
		low_visibility = false
	elif not low_visibility and v < float(Balance.OUTDOOR_LIGHTS.fog_on_m):
		low_visibility = true


## Общая система наружного света (одна на все светильники). Темно — не день.
static func is_dark() -> bool:
	return String(RaidConditions.current.get("time", "day")) != "day"


## Заградительные огни: в темноте и при низкой видимости.
static func beacons_wanted() -> bool:
	if is_dark():
		return true
	if current:
		return current.low_visibility
	return String(RaidConditions.current.get("weather", "clear")) == "fog"


## Уличные фонари: только в темноте (фотореле), туман их не зажигает.
static func street_lights_wanted() -> bool:
	return is_dark()


## Насколько мокро (0..1): мокрые кровля, фасад и асфальт отражают фонари сильнее.
static func wetness() -> float:
	return current.wet if current else 0.0


var _overcast: Array = []


## Дождь — пасмурно: солнце и небо тусклее (вернуть, если дождь кончится / уровень ушёл).
func _set_overcast(on: bool) -> void:
	var sun := get_parent().get_node_or_null("Sun") as DirectionalLight3D
	var we := get_parent().find_child("WorldEnvironment", false, false) as WorldEnvironment
	# ночное небо: облака закрывают звёзды и Луну
	if we and we.environment and we.environment.sky and we.environment.sky.sky_material is ShaderMaterial:
		(we.environment.sky.sky_material as ShaderMaterial).set_shader_parameter("overcast", 1.0 if on else 0.0)
	if on and _overcast.is_empty() and sun and we and we.environment:
		var e := we.environment
		_overcast = [sun.light_energy, e.background_energy_multiplier, e.ambient_light_energy]
		sun.light_energy *= 0.3
		e.background_energy_multiplier *= 0.45
		e.ambient_light_energy *= 0.85
	elif not on and not _overcast.is_empty() and sun and we and we.environment:
		sun.light_energy = float(_overcast[0])
		we.environment.background_energy_multiplier = float(_overcast[1])
		we.environment.ambient_light_energy = float(_overcast[2])
		_overcast.clear()


# ---------------------------------------------------------------- ход рейда

func _process(delta: float) -> void:
	_t += delta
	if not _thundered and _t >= _rain_at - float(Balance.WEATHER_CHANGE.thunder_lead):
		_thundered = true
		_thunder()
		if Raid.current:
			Raid.current.notify("Гром — будет дождь")
	if _t >= _rain_at:
		_rain_at = INF
		RaidConditions.current["weather"] = "rain"
		_apply_static()
		if Raid.current:
			Raid.current.notify("Пошёл дождь: слышно хуже, на улице видно хуже")
	if _t >= _fog_lift_at:
		_fog_lift_at = INF
		RaidConditions.current["weather"] = "clear"
		_apply_static()
		if Raid.current:
			Raid.current.notify("Туман рассеялся")
	if is_raining() and _rng.randf() < delta / 40.0:
		_thunder()
	_tick_wet(delta)
	_tick_fog(delta)
	_tick_local(delta)


## Сырость: в дождь плёнка набегает быстро, лужи — медленно; без дождя плёнка сохнет первой,
## лужи стоят дольше. У всех peer одинаково (от того же дождя), по сети не шлётся.
func _tick_wet(delta: float) -> void:
	var g: Dictionary = Balance.WET_GROUND
	if _rain_k > 0.01:
		wet = minf(1.0, wet + delta * _rain_k / float(g.film_up_sec))
		puddles = minf(float(g.puddle_max), puddles + delta * _rain_k / float(g.puddle_up_sec))
	else:
		wet = maxf(0.0, wet - delta / float(g.film_dry_sec))
		puddles = maxf(0.0, puddles - delta / float(g.puddle_dry_sec))
	_push_wet(_rain_k)


func _push_wet(rain: float) -> void:
	var m := SectorMaterials.get_material("asphalt_02") as ShaderMaterial
	if m == null:
		return
	m.set_shader_parameter("wetness", wet)
	m.set_shader_parameter("puddles", puddles)
	m.set_shader_parameter("rain", rain)


## Для своего игрока: шум дождя (на улице / под крышей), жара без очков, капли за камерой.
func _tick_local(delta: float) -> void:
	var me: Player = Raid.current.local_player() if Raid.current else null
	if me == null:
		return
	_indoor_t -= delta
	if _indoor_t <= 0.0 and RaidAtmosphere.current:
		_indoor_t = 0.5
		_outdoor = not RaidAtmosphere.current.is_indoor(me.global_position)
	if _rain_sound:
		var want := -8.0 if _outdoor else -17.0
		_rain_sound.volume_db = move_toward(_rain_sound.volume_db, want, delta * 12.0)
	if _rain:
		# начинается и кончается плавно
		_rain_k = move_toward(_rain_k, 1.0 if is_raining() else 0.0, delta / 12.0)
		_rain.set_amount(_rain_k)
		var rig := get_tree().get_first_node_in_group("camera_rig")
		var fp := rig != null and bool(rig.get("ads_active"))
		var bright := {"day": 1.0, "dusk": 0.55, "night": 0.22}.get(String(RaidConditions.current.time), 1.0) as float
		_rain.track(me, get_viewport().get_camera_3d(), fp, bright)
	# жара: на улице без очков — пересвет и марево
	var hot := String(RaidConditions.current.weather) == "heat" and _outdoor and not bool(ItemDb.equip(me.eyes_item()).get("uv", false))
	_haze_k = move_toward(_haze_k, 1.0 if hot else 0.0, delta * 0.8)
	_apply_heat(_haze_k)


# ---------------------------------------------------------------- дождь

func _set_rain(on: bool) -> void:
	if on and _rain == null:
		_rain = RainFx.new()
		_rain.name = "Rain"
		get_parent().add_child(_rain)
		_rain_sound = AudioStreamPlayer.new()
		_rain_sound.stream = Audio.rain_loop()
		_rain_sound.bus = &"Ambient"
		_rain_sound.volume_db = -30.0
		_rain_sound.autoplay = true
		add_child(_rain_sound)
	elif not on and _rain:
		_rain.queue_free()
		_rain = null
		_rain_k = 0.0
		if _rain_sound:
			_rain_sound.queue_free()
			_rain_sound = null


func _thunder() -> void:
	var me: Player = Raid.current.local_player() if Raid.current else null
	Audio.play("thunder", (me.global_position if me else Vector3.ZERO) + Vector3(_rng.randf_range(-80, 80), 60, _rng.randf_range(-80, 80)))
	# ночью — вспышка молнии
	if String(RaidConditions.current.time) == "night":
		var sun := get_parent().get_node_or_null("Sun") as DirectionalLight3D
		if sun:
			var e := sun.light_energy
			sun.light_energy = 3.0
			get_tree().create_timer(0.09).timeout.connect(func() -> void:
				if is_instance_valid(sun):
					sun.light_energy = e)


# ---------------------------------------------------------------- жара

func _apply_heat(k: float) -> void:
	var we := get_parent().find_child("WorldEnvironment", false, false) as WorldEnvironment
	if we and we.environment:
		var e := we.environment
		e.adjustment_enabled = k > 0.001
		e.adjustment_brightness = 1.0 + 0.4 * k
		e.adjustment_contrast = 1.0 - 0.12 * k
		e.adjustment_saturation = 1.0 - 0.2 * k
	if k > 0.001 and _haze == null:
		var layer := CanvasLayer.new()
		layer.layer = 9
		add_child(layer)
		_haze = ColorRect.new()
		_haze.set_anchors_preset(Control.PRESET_FULL_RECT)
		_haze.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var sh := Shader.new()
		sh.code = HAZE_SHADER
		var sm := ShaderMaterial.new()
		sm.shader = sh
		_haze.material = sm
		layer.add_child(_haze)
	if _haze:
		_haze.visible = k > 0.001
		(_haze.material as ShaderMaterial).set_shader_parameter("amount", k)


const HAZE_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float amount = 0.0;
void fragment() {
	// марево: дрожит нижняя половина кадра (над раскалённым асфальтом), лёгкий пересвет краёв
	float w = sin(SCREEN_UV.y * 90.0 + TIME * 5.0) * sin(SCREEN_UV.x * 40.0 + TIME * 3.0);
	vec2 uv = SCREEN_UV + vec2(w * 0.0016, w * 0.0010) * amount * smoothstep(0.35, 1.0, SCREEN_UV.y);
	vec3 c = texture(screen_tex, uv).rgb;
	c += vec3(0.08, 0.06, 0.02) * amount;
	COLOR = vec4(c, 1.0);
}
"""
