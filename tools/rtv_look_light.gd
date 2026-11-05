extends Node
## Свет Road to Vostok для стенда tools/rtv_look.tscn. Подключает файлы игры (RTV.pck из её папки в Steam — только
## на время запуска, в проект ничего не копируется, AGENTS.md п. 6), заводит их общие параметры шейдеров
## (shader_globals из их project.binary) и ведёт их мир Resources/World.tscn: солнце и луну на «планете», небо
## Sky.gdshader, окружение Environment/Main.tres, дождь частицами. Время суток и погода — как в их World.gd
## (TOD(), Weather()): те же градиенты, кривые и формулы, повторены своим кодом; их скрипты не запускаются —
## у всех узлов из их сцен скрипт снимается (strip). Разбор — docs/research/road_to_vostok.md.

const PCK_DEFAULT: String = "E:/SteamLibrary/steamapps/common/Road to Vostok/RTV.pck"
const WORLD_SCENE: String = "res://Resources/World.tscn"
## Общие параметры их шейдеров и значения по умолчанию (их project.godot, [shader_globals]).
const GLOBALS_FLOAT: Dictionary = {"Wind": 0.2, "Snow": 0.0, "Rain": 0.0, "Indoor": 0.0, "Viewmodel": 50.0}
const GLOBALS_BOOL: Dictionary = {"Winter": false, "Occlusion": true, "Compatibility": false}
const GLOBALS_TEX: Dictionary = {
	"Noise": "res://Terrains/Textures/TX_Mask_Noise.png",
	"Specular": "res://Modular/Textures/TX_Specular.png",
	"Overlay": "res://Terrains/Textures/TX_Mask_Overlay.png",
	"SnowNormal": "res://Terrains/Textures/TX_Snow_NR.png",
	"Ripples": "res://Modular/Textures/TX_Ripples.png",
}
## Погода их World.gd (Neutral, Overcast, Rain, Fog): к чему идут тучи, ветер, туман и дождь. Ветер без
## ветреной погоды у них не ниже 0,2, туман — множитель кривой fogDensity (1 обычно, 4 в туман).
const WEATHER: Dictionary = {
	"clear": {"overcast": 0.0, "wind": 0.2, "fog": 1.0, "rain": 0.0},
	"heat": {"overcast": 0.0, "wind": 0.2, "fog": 1.0, "rain": 0.0},
	"overcast": {"overcast": 1.0, "wind": 1.0, "fog": 1.0, "rain": 0.0},
	"rain": {"overcast": 1.0, "wind": 0.2, "fog": 1.0, "rain": 1.0},
	"fog": {"overcast": 1.0, "wind": 1.0, "fog": 4.0, "rain": 0.0},
}
## Слой «деталей без тени»: их солнце его в тень не кладёт (World.gd, _ready).
const NO_SHADOW_LAYER: int = 1 << 2

var mounted: bool = false
var error: String = ""
## Их окружение (копия Main.tres) и экспозиция их камеры (Core.tscn: CameraAttributesPractical, без автоподстройки).
var environment: Environment
var attributes: CameraAttributesPractical
## Время по-их (0…2400) и погода стенда (ключ RaidConditions).
var time: float = 1200.0
var weather: String = "clear"
var active: bool = false

var _world: Node3D
var _planet: Node3D
var _sun: DirectionalLight3D
var _moon: DirectionalLight3D
var _vfx: Node3D
var _rain_fx: GPUParticles3D
var _sky: ShaderMaterial
## Градиенты и кривые времени суток из их World.tscn (имя свойства → ресурс).
var _g: Dictionary = {}
var _v: Dictionary = (WEATHER.clear as Dictionary).duplicate()


static func pck_path() -> String:
	var env: String = OS.get_environment("RTV_PCK")
	return env if env != "" else PCK_DEFAULT


## Подключить файлы игры и завести их общие параметры. Нет файла или не читается — false и error.
func mount() -> bool:
	var path: String = pck_path()
	if not FileAccess.file_exists(path):
		error = "нет файла игры: " + path
		return false
	# replace_files = false: свои файлы проекта их файлами не подменяются
	if not ProjectSettings.load_resource_pack(path, false):
		error = "не удалось подключить " + path
		return false
	for key: String in GLOBALS_FLOAT:
		_add_global(key, RenderingServer.GLOBAL_VAR_TYPE_FLOAT, float(GLOBALS_FLOAT[key]))
	for key: String in GLOBALS_BOOL:
		_add_global(key, RenderingServer.GLOBAL_VAR_TYPE_BOOL, bool(GLOBALS_BOOL[key]))
	_add_global("Player", RenderingServer.GLOBAL_VAR_TYPE_VEC3, Vector3.ZERO)
	for key: String in GLOBALS_TEX:
		var tex: Texture2D = load(String(GLOBALS_TEX[key])) as Texture2D if ResourceLoader.exists(String(GLOBALS_TEX[key])) else null
		_add_global(key, RenderingServer.GLOBAL_VAR_TYPE_SAMPLER2D, tex)
	mounted = true
	return true


func _add_global(key: String, type: RenderingServer.GlobalShaderParameterType, value: Variant) -> void:
	if RenderingServer.global_shader_parameter_get_list().has(StringName(key)):
		RenderingServer.global_shader_parameter_set(key, value)
	else:
		RenderingServer.global_shader_parameter_add(key, type, value)


## Их мир: планета с солнцем и луной, дождь у камеры, небо и окружение. Звуки мира и их WorldEnvironment не нужны
## (окружение ставит стенд в свой узел, когда включён их свет).
func build(parent: Node3D) -> bool:
	if not mounted or not ResourceLoader.exists(WORLD_SCENE):
		error = "нет " + WORLD_SCENE
		return false
	var ps: PackedScene = load(WORLD_SCENE) as PackedScene
	var state: SceneState = ps.get_state()
	for j: int in range(state.get_node_property_count(0)):
		var value: Variant = state.get_node_property_value(0, j)
		if value is GradientTexture1D or value is CurveTexture or value is ShaderMaterial:
			_g[String(state.get_node_property_name(0, j))] = value
	_sky = _g.get("skyMaterial") as ShaderMaterial
	_world = ps.instantiate() as Node3D
	strip(_world)
	var we: WorldEnvironment = _world.get_node_or_null("Environment") as WorldEnvironment
	if we:
		environment = we.environment.duplicate(true) as Environment
		_world.remove_child(we)
		we.free()
	var audio: Node = _world.get_node_or_null("Audio")
	if audio:
		_world.remove_child(audio)
		audio.free()
	_world.name = "RtvWorld"
	parent.add_child(_world)
	_planet = _world.get_node("Planet") as Node3D
	_sun = _world.get_node("Planet/Sun/Light") as DirectionalLight3D
	_moon = _world.get_node("Planet/Moon/Light") as DirectionalLight3D
	_vfx = _world.get_node_or_null("VFX") as Node3D
	_rain_fx = _world.get_node_or_null("VFX/Rain") as GPUParticles3D
	for l: DirectionalLight3D in [_sun, _moon]:
		l.shadow_caster_mask &= ~NO_SHADOW_LAYER
	# их камера: экспозиция как есть (чувствительность 100, множитель 1), без автоподстройки и размытия
	attributes = CameraAttributesPractical.new()
	attributes.auto_exposure_enabled = false
	if environment == null or _sky == null or _g.size() < 10:
		error = "в их мире нет окружения, неба или градиентов"
		return false
	set_active(false)
	return true


## Снять скрипты у всего дерева их сцены (их код у нас не запускается) и положить их тела на слой мира.
static func strip(n: Node) -> void:
	if n.get_script() != null:
		n.set_script(null)
	if n is CollisionObject3D:
		(n as CollisionObject3D).collision_layer = 1
		(n as CollisionObject3D).collision_mask = 0
	for c: Node in n.get_children():
		strip(c)


## Их солнце, луна и дождь видны только при их свете.
func set_active(on: bool) -> void:
	active = on
	if _world:
		_world.visible = on
		_apply_weather()


## Время (0…2400 по-их) и погода — сразу, без их 20-секундного перетекания (стенд сравнивает состояния).
func apply(t: float, w: String) -> void:
	time = t
	weather = w
	_v = (WEATHER.get(w, WEATHER.clear) as Dictionary).duplicate()
	if _world == null:
		return
	_tod()
	_apply_weather()


## Высота их солнца над горизонтом (°) в момент t — чтобы подобрать их время под высоту нашего солнца.
func sun_elevation_at(t: float) -> float:
	if _planet == null:
		return 0.0
	var keep: Vector3 = _planet.rotation_degrees
	_planet.rotation_degrees = Vector3(t / 2400.0 * 360.0, 75.0, -45.0)
	var toward: Vector3 = _sun.global_transform.basis.z
	_planet.rotation_degrees = keep
	return rad_to_deg(asin(clampf(toward.y, -1.0, 1.0)))


## Их TOD(): планета, какое светило светит, небо, туман, сила и цвет света, рассеянный свет.
func _tod() -> void:
	environment.sky.sky_material = _sky
	var hm: float = remap(time, 0.0, 2400.0, 0.0, 1.0)
	_planet.rotation_degrees = Vector3(hm * 360.0, 75.0, -45.0)
	var day: bool = time > 600.0 and time < 1800.0
	_sun.light_cull_mask = 1048575 if day else 0
	_sun.shadow_enabled = day
	_moon.light_cull_mask = 0 if day else 1048575
	_moon.shadow_enabled = not day
	var sky_color: Color = _grad("skyColor", hm)
	var overcast: float = float(_v.overcast)
	var fog: float = float(_v.fog)
	_sky.set_shader_parameter("overcast", overcast)
	_sky.set_shader_parameter("skyColor", sky_color)
	_sky.set_shader_parameter("horizonColor", sky_color * 0.8)
	_sky.set_shader_parameter("groundColor", sky_color * 0.5)
	_sky.set_shader_parameter("reflection", _curve("skyReflection", hm))
	environment.volumetric_fog_density = _curve("fogDensity", hm) * fog / 100.0
	environment.volumetric_fog_emission = sky_color
	environment.volumetric_fog_albedo = _grad("sunScatter", hm)
	environment.fog_light_color = sky_color
	environment.fog_light_energy = 1.5
	environment.fog_sky_affect = 0.0
	environment.fog_density = _curve("fogDensity", hm) * fog / 2000.0
	environment.fog_height_density = 0.0
	_sun.light_energy = remap(overcast, 0.0, 1.0, _curve("sunEnergy", hm), 0.5)
	_moon.light_energy = remap(overcast, 0.0, 1.0, 2.0, 0.5)
	_sun.light_color = _grad("sunColor", hm)
	_moon.light_color = _grad("moonColor", hm)
	environment.ambient_light_color = _grad("ambientColor", hm).lerp(_grad("overcastColor", hm), overcast)
	environment.ambient_light_sky_contribution = 0.5


## Их Weather(): ветер и дождь в общие параметры (качаются деревья и трава, мокнут поверхности, круги на воде),
## дождь частицами у камеры. Снега и грома в стенде нет.
func _apply_weather() -> void:
	if not mounted:
		return
	var rain: float = float(_v.rain) if active else 0.0
	RenderingServer.global_shader_parameter_set("Snow", 0.0)
	RenderingServer.global_shader_parameter_set("Wind", float(_v.wind))
	RenderingServer.global_shader_parameter_set("Rain", float(_v.rain))
	if _rain_fx == null:
		return
	var pass_mesh: PrimitiveMesh = _rain_fx.draw_pass_1 as PrimitiveMesh
	if pass_mesh and pass_mesh.material is BaseMaterial3D:
		var mat: BaseMaterial3D = pass_mesh.material as BaseMaterial3D
		mat.albedo_color.a = rain
	_rain_fx.speed_scale = 1.0 + float(_v.wind) / 2.0
	var raining: bool = rain > 0.1
	_rain_fx.visible = raining
	_rain_fx.amount_ratio = 1.0 if raining else 0.0
	_rain_fx.emitting = raining


## Дождь у камеры (их Follow.gd) и где игрок (их трава и кусты мнутся по Player).
func follow(cam: Camera3D, player_pos: Vector3) -> void:
	if not mounted:
		return
	RenderingServer.global_shader_parameter_set("Player", player_pos)
	if _vfx and cam:
		_vfx.global_position = cam.global_position


func _grad(key: String, x: float) -> Color:
	var g: GradientTexture1D = _g.get(key) as GradientTexture1D
	return g.gradient.sample(x) if g and g.gradient else Color.WHITE


func _curve(key: String, x: float) -> float:
	var c: CurveTexture = _g.get(key) as CurveTexture
	return c.curve.sample(x) if c and c.curve else 1.0
