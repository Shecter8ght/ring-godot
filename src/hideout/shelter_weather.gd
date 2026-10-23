class_name ShelterWeather
extends Node
## Погода и время за окнами убежища — те, что ждут в следующем рейде (Profile.next_conditions, выбираются
## у стола планирования): сменили условия — через секунду другой свет.
##
## Котельная стоит на открытой местности, окна настоящие (решение владельца 2026-10-11): свет — обычный
## уличный, как на картах рейда. Небо — те же панорамы (Balance.SHELTER_SKY), ночью — звёзды и Луна;
## солнце — живой направленный свет с тенями (в окна — пятна на полу с тенью переплёта и лучи в пыльном
## воздухе); рассеянный свет в помещениях даёт SDFGI — от неба через окна и от ламп. Запечённого света нет.
## Значения — Balance.SHELTER_WEATHER. Узел «Weather» в корне сцены.

var _key: String = ""
var _poll: float = 0.0
var _rain: AudioStreamPlayer
var _power: ShelterPower


func _ready() -> void:
	set_process(false)
	_start.call_deferred()


## Уровень убежища встаёт в группу в своём _ready — после детей, поэтому проверка на кадр позже.
func _start() -> void:
	# только в живом убежище: в инструментах сборки сцена сохраняется как задумана
	if not is_inside_tree() or get_tree().get_first_node_in_group("hideout_level") == null:
		set_process(false)
		return
	for n: Node in get_parent().find_children("*", "", true, false):
		if n is ShelterPower:
			_power = n as ShelterPower
			break
	set_process(true)
	refresh(true)


func _process(delta: float) -> void:
	_poll -= delta
	if _poll <= 0.0:
		_poll = float(Balance.SHELTER_WEATHER.poll_sec)
		refresh()


## Применить погоду; force — даже если не менялась.
func refresh(force: bool = false) -> void:
	var c: Dictionary = RaidConditions.next_shared()
	var key: String = "%s|%s" % [c.time, c.weather]
	if key == _key and not force:
		return
	_key = key
	apply_state(get_parent(), c)
	_rain_sound(String(c.weather) == "rain")


## Вид за окном: «<время>_sun» — ясно или жара, «<время>_grey» — дождь, туман или пасмурно.
static func look_key(c: Dictionary) -> String:
	return String(c.time) + ("_sun" if String(c.weather) in ["clear", "heat"] else "_grey")


## Солнце (или Луна), небо, рассеянный свет, пыль в воздухе — по условиям c {time, weather}.
static func apply_state(level: Node, c: Dictionary) -> void:
	var w: Dictionary = Balance.SHELTER_WEATHER
	var time: String = String(c.time)
	var weather: String = String(c.weather)
	var night: bool = time == "night"
	var t: Dictionary = Balance.RAID_TIME[time]
	var sun: DirectionalLight3D = level.get_node_or_null("Lights/Sun") as DirectionalLight3D
	var night_sky: ShaderMaterial = RaidAtmosphere.night_sky_material() if night else null
	if sun:
		var e: float = deg_to_rad(float(t.sun_elev))
		var a: float = deg_to_rad(float(w.sun_azimuth[time]))
		if night_sky:
			# ночью свет — Луна: там, где она нарисована на небе
			e = deg_to_rad(float(night_sky.get_shader_parameter("moon_elevation")))
			sun.global_rotation = Vector3(-e, deg_to_rad(float(night_sky.get_shader_parameter("moon_azimuth"))), 0.0)
		else:
			var dir: Vector3 = Vector3(-sin(a) * cos(e), -sin(e), -cos(a) * cos(e))
			sun.global_basis = Basis.looking_at(dir, Vector3.UP)
		sun.light_energy = float(t.sun_energy) * float(w.sun_k)
		sun.light_color = t.sun_color
		sun.light_volumetric_fog_energy = float(w.sun_fog)
		sun.shadow_enabled = true
		sun.visible = true
		sun.light_angular_distance = 0.5
		if RaidConditions.clouded(weather):
			# сплошные тучи (дождь, пасмурно): солнца нет, но небо светит сверху ровным холодным светом — тот же источник
			# становится «светом облаков»: почти из зенита, слабый, с размытой тенью. Без него двор в
			# дождь был чёрным: рассеянный свет неба через SDFGI слишком слаб
			var oc: Dictionary = w.overcast
			var ce: float = deg_to_rad(float(oc.elev))
			sun.global_basis = Basis.looking_at(Vector3(-sin(a) * cos(ce), -sin(ce), -cos(a) * cos(ce)), Vector3.UP)
			sun.light_color = oc.color
			sun.light_angular_distance = float(oc.soft_deg)
			sun.light_volumetric_fog_energy = 0.0
	# стекло окон прозрачное и само не светится; ложный «дневной свет зала» больше не нужен
	var lights: Node = level.get_node_or_null("Lights")
	if lights:
		for n: Node in lights.get_children():
			if n is Light3D and String(n.name).begins_with("HallDaylight"):
				(n as Light3D).visible = false
	# фонари двора (группа «shelter_yard_lamps») — в сумерки, ночью и в непогоду
	var lamps_on: bool = time != "day" or weather in ["rain", "fog", "overcast"]
	for lamp: Node in level.get_tree().get_nodes_in_group("shelter_yard_lamps") if level.is_inside_tree() else []:
		if lamp is Light3D:
			(lamp as Light3D).visible = lamps_on
	var we: WorldEnvironment = level.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if we == null or we.environment == null:
		return
	var env: Environment = we.environment
	if not env.has_meta("authored_fog"):
		env.set_meta("authored_fog", env.volumetric_fog_density)
	env.background_mode = Environment.BG_SKY
	env.background_energy_multiplier = 1.0
	env.sdfgi_enabled = true
	# небо светит в окна: SDFGI учитывает его и сам затеняет стенами
	env.sdfgi_read_sky_light = true
	env.tonemap_exposure = float(w.exposure.get(time, 1.0))
	env.sdfgi_energy = float(w.gi.get(look_key(c), 1.0))
	if night_sky:
		var n_cfg: Dictionary = Balance.NIGHT_ENV
		night_sky.set_shader_parameter("overcast", 1.0 if RaidConditions.clouded(weather) else 0.0)
		var sky := Sky.new()
		sky.sky_material = night_sky
		sky.radiance_size = Sky.RADIANCE_SIZE_256
		env.sky = sky
		env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		env.ambient_light_color = n_cfg.ambient_color
		env.ambient_light_energy = float(w.ambient.night)
	else:
		var all: Dictionary = Balance.SHELTER_SKY
		var conf: Dictionary = (all.get(time + "_" + weather, all.get(time, {})) as Dictionary).duplicate()
		var sky: Sky = RaidAtmosphere.hdri_sky(conf, weather, sun)
		if sky:
			env.sky = sky
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.ambient_light_energy = float(w.ambient.get(look_key(c), 1.0))
	if sun and RaidConditions.clouded(weather):
		# сила «света облаков» — после неба: панорама под дождь и пасмурно обнуляет солнце (sun_k 0)
		var oc2: Dictionary = w.overcast
		sun.light_energy = float(Balance.RAID_TIME.day.sun_energy) * float(oc2.energy_k) * float(oc2.time_k.get(time, 1.0))
	var fog_k: float = float(w.fog.get(look_key(c), 1.0)) * (float(w.fog_weather_k) if weather == "fog" else 1.0)
	env.volumetric_fog_density = float(env.get_meta("authored_fog")) * fog_k
	if not env.has_meta("lab_authored_fog_color"):
		env.set_meta("lab_authored_fog_color", env.fog_light_color)
	env.fog_light_color = env.get_meta("lab_authored_fog_color") as Color
	Balance.lab_atmosphere(sun, env)


func _rain_sound(on: bool) -> void:
	if on and _rain == null:
		_rain = AudioStreamPlayer.new()
		_rain.stream = Audio.rain_loop()
		_rain.bus = &"Ambient"
		_rain.volume_db = float(Balance.SHELTER_WEATHER.rain_db)
		add_child(_rain)
	if _rain:
		if on and not _rain.playing:
			_rain.play()
		elif not on:
			_rain.stop()
