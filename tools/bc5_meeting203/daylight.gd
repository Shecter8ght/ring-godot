extends Node3D
## Стенд использует астрономию и небо рейда. Свет проходит через настоящие проёмы.

const PRESETS := [
	["01_morning", 9.0, "clear", "Ясное утро"],
	["02_noon", 12.0, "clear", "Ясный полдень"],
	["03_overcast", 12.0, "overcast", "Пасмурный полдень"],
	["04_sunset", 18.65, "clear", "Закат"],
	["05_fog", 12.0, "fog", "Сильный туман"],
	["06_rain", 12.0, "rain", "Дождь под облаками"],
	["07_night", 1.5, "clear", "Безлунная ночь"],
]
const APERTURE_CENTERS := [-3.28, .58, 3.72]
const LANTERN_LAYER := 1 << 12
const LANTERN_ENERGY := .72
const LANTERN_EMISSION := 2.1
const REFLECTION_INTERVAL := 4.0
const SUN_REFLECTION_DELAY := .25

@export var table_lantern: Node3D

var hour := 15.55
var weather := "clear"
var running := true
var _rain: RainFx
var _sky: ShaderMaterial
var _sky_time := 0.0
var _reflection_time := 0.0
var _moonlit := true
var _manual_sun := false
var _manual_angles := Vector2.ZERO
var sky_apertures: Array[AreaLight3D] = []
var _lantern_level := -1.0
var _lantern_diffuser: BaseMaterial3D

@onready var sun: DirectionalLight3D = $Sun
@onready var sky_aperture: AreaLight3D = $SkyAperture
@onready var environment: Environment = $WorldEnvironment.environment
@onready var camera_attributes: CameraAttributesPractical = $WorldEnvironment.camera_attributes
@onready var reflections: Array[ReflectionProbe] = [$RoomReflections, $DisplayReflection]
@onready var lantern_light: OmniLight3D = table_lantern.get_node("Light")


func _ready() -> void:
	_prepare_lantern()
	# Каждый участок неба освещает через свою часть окна. Одна карта теней
	# в центре большого витража преувеличивает тень ближайшего импоста.
	sky_apertures.append(sky_aperture)
	for i in range(1, APERTURE_CENTERS.size()):
		var section := sky_aperture.duplicate() as AreaLight3D
		section.name = "SkyAperture%d" % (i + 1)
		add_child(section)
		sky_apertures.append(section)
	for i in APERTURE_CENTERS.size():
		sky_apertures[i].position.x = APERTURE_CENTERS[i]
	_sky = TodLight.sky_material()
	environment.sky.sky_material = _sky
	# Свет неба рассчитывается по отдельной карте отражений. Диск солнца освещает только через Sun.
	_sky.set_shader_parameter("sun_reflection", 1.0)
	_sky.set_shader_parameter("moon_reflection", 1.0)
	_apply_light(true)


func _prepare_lantern() -> void:
	var model := table_lantern.get_node("Model")
	var meshes := model.find_children("*", "MeshInstance3D", true, false)
	if model is MeshInstance3D:
		meshes.append(model)
	for mesh: MeshInstance3D in meshes:
		mesh.layers = LANTERN_LAYER
		# Источник внутри рассеивателя. Корпус не должен перегораживать весь свет.
		mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for surface in mesh.mesh.get_surface_count():
			var material := mesh.get_active_material(surface) as BaseMaterial3D
			if material and material.resource_name.ends_with("_свет"):
				_lantern_diffuser = material.duplicate() as BaseMaterial3D
				_lantern_diffuser.emission = lantern_light.light_color
				mesh.set_surface_override_material(surface, _lantern_diffuser)


func _set_lantern(level: float) -> void:
	if is_equal_approx(level, _lantern_level):
		return
	_lantern_level = level
	lantern_light.light_energy = LANTERN_ENERGY * level
	lantern_light.visible = level > .001
	if _lantern_diffuser:
		_lantern_diffuser.emission_enabled = lantern_light.visible
		_lantern_diffuser.emission_energy_multiplier = LANTERN_EMISSION * level


func lantern_is_lit() -> bool:
	return (lantern_light.visible and lantern_light.light_energy > .001
		and _lantern_diffuser != null and _lantern_diffuser.emission_enabled)


func set_preset(index: int) -> void:
	var choice: Array = PRESETS[index]
	set_conditions(choice[1], choice[2], choice[0] != "07_night")


func set_conditions(at_hour: float, condition: String, moonlit := true) -> void:
	hour = fposmod(at_hour, 24.0)
	weather = condition
	_moonlit = moonlit
	reset_sun_angles()
	if DisplayServer.get_name() != "headless":
		if weather == "rain" and _rain == null:
			_rain = RainFx.new()
			add_child(_rain)
		if _rain:
			_rain.set_amount(1.0 if weather == "rain" else 0.0)


## x — высота над горизонтом, y — азимут по часовой стрелке от севера, в градусах.
func sun_angles() -> Vector2:
	return _manual_angles if _manual_sun else DayCycle.sun_at(hour)


func set_sun_angles(angles: Vector2) -> void:
	_manual_sun = true
	_manual_angles = Vector2(clampf(angles.x, -90.0, 90.0), clampf(angles.y, 0.0, 360.0))
	_apply_light(true)
	# Обновляем отражения, когда пользователь перестаёт двигать ползунок.
	_reflection_time = REFLECTION_INTERVAL - SUN_REFLECTION_DELAY


func reset_sun_angles() -> void:
	_manual_sun = false
	_apply_light(true)
	_refresh_reflections()


func _process(delta: float) -> void:
	if running:
		hour = fposmod(hour + delta / float(Balance.DAY_CYCLE.hour_sec), 24.0)
		_sky_time += delta
		_apply_light(_sky_time >= .75)
	if running or _manual_sun:
		_reflection_time += delta
		if _reflection_time >= REFLECTION_INTERVAL:
			_refresh_reflections()
	if _rain and weather == "rain":
		var camera := get_viewport().get_camera_3d()
		_rain.track(camera, camera, true, .80, false)


func _apply_light(update_sky: bool) -> void:
	var solar := sun_angles()
	_set_lantern(float(DayCycle.weights(solar.x).night))
	var lunar := DayCycle.moon_at(hour)
	var solar_dir := DayCycle.dir_from(solar.x, solar.y)
	var lunar_dir := DayCycle.dir_from(lunar.x, lunar.y)
	var t := TodLight.time_for(hour, solar)
	var cloud := float(TodLight.weather(weather).overcast)
	var twilight := smoothstep(-8.0, 2.0, solar.x)
	var day_energy := TodLight.value_at("sunEnergy", t) * smoothstep(-.4, 4.0, solar.x)
	var moon_energy := .017 * smoothstep(1.0, 12.0, lunar.x) * (1.0 - twilight) if _moonlit else 0.0
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
	var window_color := Color(.86, .89, .96).lerp(sky_color, .47).lerp(Color(.87, .90, .93), cloud * .58)
	var window_energy := lerpf(.0021, lerpf(.48, .40, cloud), twilight) * (1.0 - .44 * fog_k)
	for aperture in sky_apertures:
		aperture.light_color = window_color
		aperture.light_energy = window_energy
		aperture.visible = window_energy > .001
	var bounce_color := window_color.lerp(Color(.95, .91, .85), .40)
	var bounce_energy := lerpf(.0005, .20, twilight) * (1.0 - .49 * fog_k)
	for probe in reflections:
		if probe.ambient_mode == ReflectionProbe.AMBIENT_COLOR:
			probe.ambient_color = bounce_color
			probe.ambient_color_energy = bounce_energy * float(probe.get_meta("sky_bounce_scale", 1.0))
	environment.ambient_light_energy = lerpf(.21, .49, twilight) * (1.0 - .39 * fog_k)
	_sky.set_shader_parameter("sky_color", sky_color * sky_gain)
	_sky.set_shader_parameter("horizon_color", sky_color * .8 * sky_gain)
	_sky.set_shader_parameter("ground_color", sky_color * .45 * sky_gain)
	_sky.set_shader_parameter("reflection", lerpf(.45, 1.0, twilight) * (1.0 - .38 * fog_k))
	_sky.set_shader_parameter("sun_dir", solar_dir)
	_sky.set_shader_parameter("moon_dir", lunar_dir)
	_sky.set_shader_parameter("sun_color", TodLight.color_at("sunColor", t))
	_sky.set_shader_parameter("moon_color", Color(.53, .60, .73) * (1.0 - twilight) if _moonlit else Color.BLACK)
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
