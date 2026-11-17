extends Node3D
## Стенд использует астрономию и небо рейда. Свет проходит через настоящие проёмы.

const PRESETS := [
	["01_morning", 9.0, "clear", "Ясное утро"],
	["02_noon", 12.0, "clear", "Ясный полдень"],
	["03_overcast", 12.0, "overcast", "Пасмурный полдень"],
	["04_sunset", 18.65, "clear", "Закат"],
	["05_fog", 12.0, "fog", "Сильный туман"],
	["06_rain", 12.0, "rain", "Дождь под облаками"],
	["07_night", 1.5, "clear", "Ночь"],
]

var hour := 15.55
var weather := "clear"
var running := true
var _rain: RainFx
var _sky: ShaderMaterial
var _sky_time := 0.0
var _reflection_time := 0.0

@onready var sun: DirectionalLight3D = $Sun
@onready var sky_aperture: AreaLight3D = $SkyAperture
@onready var environment: Environment = $WorldEnvironment.environment
@onready var camera_attributes: CameraAttributesPractical = $WorldEnvironment.camera_attributes
@onready var reflections: Array[ReflectionProbe] = [$RoomReflections, $DisplayReflection]


func _ready() -> void:
	_sky = TodLight.sky_material()
	environment.sky.sky_material = _sky
	# Свет неба рассчитывается по отдельной карте отражений. Диск солнца освещает только через Sun.
	_sky.set_shader_parameter("sun_reflection", 1.0)
	_sky.set_shader_parameter("moon_reflection", 1.0)
	_apply_light(true)


func set_conditions(at_hour: float, condition: String) -> void:
	hour = fposmod(at_hour, 24.0)
	weather = condition
	_sky_time = 0.0
	_apply_light(true)
	_refresh_reflections()
	if DisplayServer.get_name() != "headless":
		if weather == "rain" and _rain == null:
			_rain = RainFx.new()
			add_child(_rain)
		if _rain:
			_rain.set_amount(1.0 if weather == "rain" else 0.0)


func _process(delta: float) -> void:
	if running:
		hour = fposmod(hour + delta / float(Balance.DAY_CYCLE.hour_sec), 24.0)
		_sky_time += delta
		_apply_light(_sky_time >= .75)
		_reflection_time += delta
		if _reflection_time >= 4.0:
			_refresh_reflections()
	if _rain and weather == "rain":
		var camera := get_viewport().get_camera_3d()
		_rain.track(camera, camera, true, .80, false)


func _apply_light(update_sky: bool) -> void:
	var solar := DayCycle.sun_at(hour)
	var lunar := DayCycle.moon_at(hour)
	var solar_dir := DayCycle.dir_from(solar.x, solar.y)
	var lunar_dir := DayCycle.dir_from(lunar.x, lunar.y)
	var t := TodLight.time_for(hour, solar)
	var cloud := float(TodLight.weather(weather).overcast)
	var twilight := smoothstep(-8.0, 2.0, solar.x)
	var day_energy := TodLight.value_at("sunEnergy", t) * smoothstep(-.4, 4.0, solar.x)
	var moon_energy := .017 * smoothstep(1.0, 12.0, lunar.x) * (1.0 - twilight)
	var to := solar_dir if day_energy >= moon_energy else lunar_dir
	sun.global_basis = Basis.looking_at(-to, Vector3.UP if absf(to.y) < .99 else Vector3.FORWARD)
	sun.light_energy = (day_energy + moon_energy) * (1.0 - cloud)
	sun.light_color = TodLight.color_at("sunColor", t) if day_energy >= moon_energy else Color(.71, .80, 1)
	sun.light_angular_distance = .42 if solar.x > 14.0 else 0.0
	sun.visible = sun.light_energy > .0001
	if not update_sky:
		return
	_sky_time = 0.0
	var sky_color := TodLight.color_at("skyColor", t)
	var sky_gain := lerpf(.33, 1.0, twilight)
	var fog_k := {"clear": .0, "overcast": .0, "fog": .92, "rain": .40}.get(weather, .0) as float
	# Рассеянная часть того же неба. Источник снаружи витража, рамы и перекрытия отсекают его свет.
	sky_aperture.light_color = Color(.78, .86, 1).lerp(sky_color, .66).lerp(Color(.87, .9, .93), cloud * .58)
	sky_aperture.light_energy = lerpf(.0038, lerpf(.61, .53, cloud), twilight) * (1.0 - .44 * fog_k)
	sky_aperture.visible = sky_aperture.light_energy > .001
	environment.ambient_light_energy = lerpf(.21, .49, twilight) * (1.0 - .39 * fog_k)
	_sky.set_shader_parameter("sky_color", sky_color * sky_gain)
	_sky.set_shader_parameter("horizon_color", sky_color * .8 * sky_gain)
	_sky.set_shader_parameter("ground_color", sky_color * .45 * sky_gain)
	_sky.set_shader_parameter("reflection", lerpf(.45, 1.0, twilight) * (1.0 - .38 * fog_k))
	_sky.set_shader_parameter("sun_dir", solar_dir)
	_sky.set_shader_parameter("moon_dir", lunar_dir)
	_sky.set_shader_parameter("sun_color", TodLight.color_at("sunColor", t))
	_sky.set_shader_parameter("moon_color", Color(.53, .60, .73) * (1.0 - twilight))
	_sky.set_shader_parameter("overcast", cloud)
	_sky.set_shader_parameter("clouds_shift", fposmod(hour * float(Balance.TOD_LIGHT.clouds_drift), 1.0))
	environment.fog_enabled = fog_k > .001
	environment.fog_density = fog_k
	environment.fog_light_color = sky_color.lerp(Color(.52, .56, .59), .68) * sky_gain
	environment.fog_depth_end = 34.0 if weather == "fog" else 64.0


func _refresh_reflections() -> void:
	_reflection_time = 0.0
	# UPDATE_ONCE обновляется после изменения положения. Смещаем зонд на долю миллиметра.
	for probe in reflections:
		probe.position.y += .0001 if not probe.has_meta("refresh_offset") else -.0001
		if probe.has_meta("refresh_offset"):
			probe.remove_meta("refresh_offset")
		else:
			probe.set_meta("refresh_offset", true)
