class_name ShelterWeather
extends Node
## Погода за окнами убежища — та, что ждёт в следующем рейде (Profile.next_conditions, выбирается у
## лестницы): сменили условия — через секунду другой свет. Ясно и жара — солнце в окна котельного
## зала: пятна на полу с тенью переплёта и лучи в пыльном воздухе; дождь и туман — серо, холодный
## ровный свет стекла, в дождь — шум по крыше; ночь — тёмные окна, в ясно — слабая луна.
## Рассеянный свет помещений запечён заранее на каждый вид и питание генератора
## (levels/shelter/lightmap/Shelter_<вид>[_off].lmbake, tools/bake_shelter_light.cmd) и подменяется;
## прямое солнце и тени — живые. Значения — Balance.SHELTER_WEATHER. Узел «Weather» в корне сцены.

const GLASS := "res://levels/shelter/materials/WiredGlass.tres"
const VARIANT_PATH := "res://levels/shelter/lightmap/Shelter_%s.lmbake"

var _key: String = ""
var _poll: float = 0.0
var _rain: AudioStreamPlayer
var _baked: Dictionary = {}
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


## Применить погоду и питание; force — даже если не менялись (рубильник генератора).
func refresh(force: bool = false) -> void:
	var c: Dictionary = RaidConditions.next_shared()
	var power: bool = _power_on()
	var key: String = "%s|%s|%s" % [c.time, c.weather, power]
	if key == _key and not force:
		return
	_key = key
	var level: Node = get_parent()
	apply_state(level, c, power)
	_set_lightmap(level, lightmap_variant(c, power))
	_rain_sound(String(c.weather) == "rain")


## Вид за окном: «<время>_sun» — ясно или жара, «<время>_grey» — дождь или туман.
static func look_key(c: Dictionary) -> String:
	return String(c.time) + ("_sun" if String(c.weather) in ["clear", "heat"] else "_grey")


## Вариант запечённого света: вид и питание генератора.
static func lightmap_variant(c: Dictionary, power: bool) -> String:
	return look_key(c) + ("" if power else "_off")


## Все варианты для запекания: [вид, условия, питание].
static func bake_variants() -> Array:
	var out: Array = []
	for time: String in ["day", "dusk", "night"]:
		for weather: String in ["clear", "rain"]:
			for power: bool in [true, false]:
				var c: Dictionary = {"time": time, "weather": weather, "power": "on"}
				out.append([lightmap_variant(c, power), c, power])
	return out


## Солнце, стекло окон, дневной свет зала, пыль в воздухе; при запекании (bake) ещё и лампы по
## питанию. Общая для игры и для запекания вариантов — свет в карте совпадает с живым.
static func apply_state(level: Node, c: Dictionary, power: bool, bake: bool = false) -> void:
	var w: Dictionary = Balance.SHELTER_WEATHER
	var look_name: String = look_key(c)
	var look: Dictionary = w.looks[look_name]
	var time: String = String(c.time)
	var t: Dictionary = Balance.RAID_TIME[time]
	var sun: DirectionalLight3D = level.get_node_or_null("Lights/Sun") as DirectionalLight3D
	if sun:
		sun.visible = look_name.ends_with("_sun")
		var e: float = deg_to_rad(float(t.sun_elev))
		var a: float = deg_to_rad(float(w.sun_azimuth[time]))
		var dir: Vector3 = Vector3(-sin(a) * cos(e), -sin(e), -cos(a) * cos(e))
		sun.global_basis = Basis.looking_at(dir, Vector3.UP)
		sun.light_energy = float(t.sun_energy) * float(w.sun_k)
		sun.light_color = t.sun_color
		sun.light_volumetric_fog_energy = float(w.sun_fog)
	var glass: StandardMaterial3D = load(GLASS) as StandardMaterial3D
	glass.emission = look.glass_color
	glass.emission_energy_multiplier = float(look.glass)
	var lights: Node = level.get_node_or_null("Lights")
	if lights:
		for n: Node in lights.get_children():
			var l: Light3D = n as Light3D
			if not l:
				continue
			if not l.has_meta("authored_energy"):
				l.set_meta("authored_energy", l.light_energy)
			if String(l.name).begins_with("HallDaylight"):
				l.light_energy = float(l.get_meta("authored_energy")) * float(look.daylight)
			elif bake and not ShelterPower.daylight(l):
				# лампы — по питанию; в игре их гасит и зажигает ShelterPower
				l.light_energy = float(l.get_meta("authored_energy")) if power or String(l.name).begins_with("Emergency") else 0.0
	var we: WorldEnvironment = level.get_node_or_null("WorldEnvironment") as WorldEnvironment
	if we and we.environment:
		var env: Environment = we.environment
		if not env.has_meta("authored_fog"):
			env.set_meta("authored_fog", env.volumetric_fog_density)
		var k: float = float(look.fog) * (float(w.fog_weather_k) if String(c.weather) == "fog" else 1.0)
		env.volumetric_fog_density = float(env.get_meta("authored_fog")) * k


func _set_lightmap(level: Node, variant: String) -> void:
	var lm: LightmapGI = level.get_node_or_null("LightmapGI") as LightmapGI
	if not lm:
		return
	var path: String = VARIANT_PATH % variant
	if not _baked.has(path):
		_baked[path] = load(path) if ResourceLoader.exists(path) else null
	if _baked[path]:
		lm.light_data = _baked[path]


func _power_on() -> bool:
	return _power.enabled if is_instance_valid(_power) else true


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
