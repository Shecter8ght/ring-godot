class_name TodLight
extends RefCounted
## Свет по времени суток по схеме Road to Vostok на всех рейдовых картах (решение владельца 2026-11-05;
## Balance.TOD_LIGHT, таблица data/lighting/time_of_day.json, стенд сравнения tools/rtv_look.tscn).
## Как у них: по их часам t (0…2400) из таблицы берутся цвет и сила солнца, цвет луны, рассеянный свет (ясно и пасмурно,
## половина — от неба), цвет неба, отражения неба, плотность и цвет объёмной дымки; тучи гасят солнце и луну до 0,5,
## туман погоды умножает дымку. Небо — tod_sky.gdshader (их схема, наши облака). Солнце и Луна у нас ходят по
## астрономии (DayCycle), поэтому их час подбирается по высоте нашего солнца (утро — на восходящей половине, вечер — на
## заходящей). Ночью светит луна напротив солнца, как у них. Свой код; их файлы игре не нужны.

const SKY_SHADER: String = "res://src/world/tod_sky.gdshader"

static var _table: Dictionary = {}
static var _cloud_blur: Dictionary = {}
static var _cloud_spread: Dictionary = {}


## Включён ли их свет (Balance.TOD_LIGHT.on и таблица на месте).
static func active() -> bool:
	return bool(Balance.TOD_LIGHT.get("on", false)) and not table().is_empty()


static func table() -> Dictionary:
	if _table.is_empty():
		var path: String = String(Balance.TOD_LIGHT.table)
		if FileAccess.file_exists(path):
			var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
			if raw is Dictionary and (raw as Dictionary).has("t"):
				_table = raw
	return _table


## Их часы с той же высотой солнца, что у нашего (elev, °): утром — на восходящей половине их суток, вечером — на
## заходящей. Выше их полудня — их полдень, ниже их полуночи — их полночь.
static func rtv_time(elev: float, morning: bool) -> float:
	var tb: Dictionary = table()
	var ts: Array = tb.t
	var es: Array = tb.sun_elev
	var half: int = ts.size() / 2
	var from: int = 0 if morning else half
	var to: int = half if morning else ts.size() - 1
	for i: int in range(from, to):
		var e0: float = float(es[i])
		var e1: float = float(es[i + 1])
		if (elev - e0) * (elev - e1) <= 0.0 and not is_equal_approx(e0, e1):
			return lerpf(float(ts[i]), float(ts[i + 1]), (elev - e0) / (e1 - e0))
	# вне их размаха: выше полудня — полдень, ниже — полночь
	return float(ts[half]) if elev > float(es[half]) else (0.0 if morning else 2400.0)


static func _row(key: String, t: float) -> Variant:
	var tb: Dictionary = table()
	var rows: Array = tb.get(key, [])
	if rows.is_empty():
		return null
	var x: float = clampf(t / float(tb.step), 0.0, float(rows.size() - 1))
	var i: int = mini(int(floor(x)), rows.size() - 2)
	var k: float = x - float(i)
	var a: Variant = rows[i]
	var b: Variant = rows[i + 1]
	if a is Array:
		return Color(lerpf(float(a[0]), float(b[0]), k), lerpf(float(a[1]), float(b[1]), k), lerpf(float(a[2]), float(b[2]), k))
	return lerpf(float(a), float(b), k)


static func color_at(key: String, t: float) -> Color:
	var v: Variant = _row(key, t)
	return v if v is Color else Color.WHITE


static func value_at(key: String, t: float) -> float:
	var v: Variant = _row(key, t)
	return float(v) if v != null else 1.0


## Погода по их таблице: тучи, ветер, туман, дождь.
static func weather(w: String) -> Dictionary:
	var all: Dictionary = Balance.TOD_LIGHT.weather
	return all.get(w, all.clear)


## Окружение под их свет: тональная кривая AgX как у них, объёмная дымка их параметров, без глубинного тумана;
## SSAO, SDFGI и отражения в лужах (SSR) — по качеству графики, как раньше. Тень солнца — их даль.
static func prepare(we: WorldEnvironment, sun: DirectionalLight3D) -> void:
	var tb: Dictionary = table()
	if we and we.environment:
		var e: Environment = we.environment
		var env: Dictionary = tb.get("environment", {})
		e.set_meta("tod", true)
		e.tonemap_mode = Environment.TONE_MAPPER_AGX
		e.tonemap_agx_white = float(env.get("tonemap_agx_white", 2.0))
		e.tonemap_agx_contrast = float(env.get("tonemap_agx_contrast", 1.5))
		e.tonemap_exposure = float(env.get("tonemap_exposure", 1.0))
		e.adjustment_enabled = false
		e.fog_enabled = false
		e.volumetric_fog_emission_energy = float(env.get("volumetric_fog_emission_energy", 0.2))
		e.volumetric_fog_gi_inject = float(env.get("volumetric_fog_gi_inject", 1.0))
		e.volumetric_fog_anisotropy = float(env.get("volumetric_fog_anisotropy", 0.9))
		e.volumetric_fog_length = float(env.get("volumetric_fog_length", 400.0))
		e.volumetric_fog_detail_spread = float(env.get("volumetric_fog_detail_spread", 2.0))
		e.volumetric_fog_ambient_inject = float(env.get("volumetric_fog_ambient_inject", 0.0))
		e.volumetric_fog_sky_affect = float(env.get("volumetric_fog_sky_affect", 0.0))
		e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
		e.background_mode = Environment.BG_SKY
		e.background_energy_multiplier = 1.0
		if not e.has_meta("tod_glow"):
			e.set_meta("tod_glow", e.glow_enabled)
		# объёмная дымка — их; затенение в углах (SSAO) и отражённый свет (SDFGI) остаются нашими по качеству
		# графики: у них помещения и подлесок затемнены прямо в моделях (вершинное затенение), у нас — этим
		var orig: Dictionary = (e.get_meta("orig", {}) as Dictionary).duplicate()
		if not orig.is_empty():
			orig["fog"] = true
			e.set_meta("orig", orig)
		e.volumetric_fog_enabled = true
		Settings._apply_env(we)
	if sun:
		sun.light_angular_distance = 0.0
		sun.shadow_blur = 1.0
		sun.directional_shadow_blend_splits = true
		sun.shadow_enabled = true
		var o: Dictionary = sun.get_meta("orig_sun_shadow", {}) as Dictionary
		sun.set_meta("orig_sun_shadow", {"max_m": float(Balance.TOD_LIGHT.shadow_max_m),
			"mode": int(o.get("mode", DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS))})
		Settings._apply_sun_quality(sun)


## Небо их схемы с нашими облаками (панорамы sky.json), звёздами и Луной ночного неба.
static func sky_material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load(SKY_SHADER) as Shader
	var sky: Dictionary = table().get("sky", {})
	for pair: Array in [["sun_size", "sunSize"], ["sun_blur", "sunBlur"], ["sun_glow_size", "sunGlowSize"],
			["sun_glow_intensity", "sunGlowIntensity"], ["sun_reflection", "sunReflection"], ["moon_size", "moonSize"],
			["moon_glow_size", "moonGlowSize"], ["moon_glow_intensity", "moonGlowIntensity"],
			["moon_reflection", "moonReflection"], ["stars_reflection", "starsReflection"], ["horizon_blur", "horizonBlur"]]:
		if sky.has(pair[1]):
			m.set_shader_parameter(String(pair[0]), float(sky[pair[1]]))
	for pair2: Array in [["sun_color", "sunColor"], ["moon_color", "moonColor"]]:
		var c: Array = sky.get(pair2[1], [])
		if c.size() == 3:
			m.set_shader_parameter(String(pair2[0]), Color(float(c[0]), float(c[1]), float(c[2])))
	var conf: Dictionary = RaidLighting.sky_conf()
	var clear_path: String = String((conf.get(String(Balance.TOD_LIGHT.clouds_clear), {}) as Dictionary).get("a", ""))
	var over_path: String = String((conf.get(String(Balance.TOD_LIGHT.clouds_overcast), {}) as Dictionary).get("a", ""))
	if ResourceLoader.exists(clear_path) and ResourceLoader.exists(over_path):
		m.set_shader_parameter("clouds_clear", load(clear_path))
		m.set_shader_parameter("clouds_overcast", load(over_path))
		m.set_shader_parameter("clear_blur", _blur(clear_path))
		m.set_shader_parameter("overcast_blur", _blur(over_path))
		m.set_shader_parameter("clear_mean", float(Balance.TOD_LIGHT.clear_mean))
		m.set_shader_parameter("overcast_mean", float(Balance.TOD_LIGHT.overcast_mean))
		m.set_shader_parameter("clear_contrast", _contrast(clear_path, float(Balance.TOD_LIGHT.clear_spread), float(Balance.TOD_LIGHT.clear_mean)))
		m.set_shader_parameter("overcast_contrast", _contrast(over_path, float(Balance.TOD_LIGHT.overcast_spread), float(Balance.TOD_LIGHT.overcast_mean)))
		m.set_shader_parameter("has_clouds", true)
	var night: ShaderMaterial = RaidAtmosphere.night_sky_material()
	for key: String in ["stars_tex", "has_stars_tex", "stars_energy", "stars_floor", "stars_max", "moon_tex", "has_moon_tex"]:
		var v: Variant = night.get_shader_parameter(key)
		if v != null:
			m.set_shader_parameter(key, v)
	return m


## Размытая копия панорамы (64 × 32): по ней облака выравниваются по направлениям (один раз на файл).
## Заодно — контраст: разброс выровненной яркости (5–95 %) против разброса их картинки облаков (spread).
static func _blur(path: String) -> Texture2D:
	if _cloud_blur.has(path):
		return _cloud_blur[path] as Texture2D
	var out: Texture2D = null
	var tex: Texture2D = load(path) as Texture2D
	var img: Image = tex.get_image() if tex else null
	if img:
		if img.is_compressed():
			img.decompress()
		img.convert(Image.FORMAT_RGBF)
		img.resize(128, 64, Image.INTERPOLATE_BILINEAR)
		var blur: Image = img.duplicate() as Image
		blur.resize(16, 8, Image.INTERPOLATE_BILINEAR)
		blur.resize(128, 64, Image.INTERPOLATE_CUBIC)
		var rel: PackedFloat32Array = PackedFloat32Array()
		for y: int in range(4, 30):
			for x: int in range(128):
				rel.append(img.get_pixel(x, y).get_luminance() / maxf(blur.get_pixel(x, y).get_luminance(), 0.0001))
		rel.sort()
		var spread: float = rel[rel.size() * 95 / 100] - rel[rel.size() * 5 / 100]
		_cloud_spread[path] = spread
		blur.resize(64, 32, Image.INTERPOLATE_BILINEAR)
		out = ImageTexture.create_from_image(blur)
	_cloud_blur[path] = out
	return out


## Контраст облаков панорамы: их разброс / наш (выровненный, в долях средней).
static func _contrast(path: String, their_spread: float, mean: float) -> float:
	_blur(path)
	var ours: float = float(_cloud_spread.get(path, 0.0)) * mean
	return clampf(their_spread / ours, 1.0, 4.0) if ours > 0.0001 else 1.0


## Их часы для нашего часа и высоты солнца sa.x (утро — до полудня по солнцу).
static func time_for(hour: float, sa: Vector2) -> float:
	return rtv_time(sa.x, fposmod(hour, 24.0) < 12.0)


## Их TOD() и Weather() на наш час: солнце или луна, рассеянный свет, дымка. sa — (высота, азимут) солнца
## (DayCycle.sun_at), night_w — доля ночи (свечение фонарей и ракет — наше, как раньше).
static func apply(hour: float, sa: Vector2, sun: DirectionalLight3D, e: Environment, night_w: float) -> void:
	var tb: Dictionary = Balance.TOD_LIGHT
	var t: float = time_for(hour, sa)
	var wv: Dictionary = weather(String(RaidConditions.current.weather))
	var overcast: float = float(wv.overcast)
	var fog: float = float(wv.fog)
	var day: bool = t > float(tb.day_from) and t < float(tb.day_to)
	var to_sun: Vector3 = DayCycle.dir_from(sa.x, sa.y)
	var to_moon: Vector3 = -to_sun
	if sun:
		var to: Vector3 = to_sun if day else to_moon
		sun.global_basis = Basis.looking_at(-to, Vector3.UP if absf(to.y) < 0.99 else Vector3.FORWARD)
		if day:
			sun.light_energy = remap(overcast, 0.0, 1.0, value_at("sunEnergy", t), float(tb.overcast_energy))
			sun.light_color = color_at("sunColor", t)
		else:
			sun.light_energy = remap(overcast, 0.0, 1.0, float(tb.moon_energy), float(tb.overcast_energy))
			sun.light_color = color_at("moonColor", t)
		sun.visible = sun.light_energy > 0.001
		sun.shadow_enabled = true
		sun.light_volumetric_fog_energy = 1.0
	if e:
		var sky_color: Color = color_at("skyColor", t)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		e.ambient_light_color = color_at("ambientColor", t).lerp(color_at("overcastColor", t), overcast)
		e.ambient_light_sky_contribution = float((table().get("environment", {}) as Dictionary).get("ambient_light_sky_contribution", 0.5))
		e.ambient_light_energy = 1.0
		e.background_energy_multiplier = 1.0
		e.tonemap_exposure = 1.0
		e.volumetric_fog_density = value_at("fogDensity", t) * fog / float(tb.fog_div)
		e.volumetric_fog_emission = sky_color
		e.volumetric_fog_albedo = color_at("sunScatter", t)
		# свечение — только ночью, вокруг фонарей и ракет (наше: у них свечения нет совсем)
		e.glow_hdr_threshold = float(Balance.NIGHT_ENV.glow_threshold)
		e.glow_intensity = float(Balance.NIGHT_ENV.glow_intensity) * night_w
		e.glow_bloom = 0.0
		e.glow_enabled = bool(e.get_meta("tod_glow", true)) and e.glow_intensity > 0.001
	Balance.lab_atmosphere(sun, e)


## Их небо на наш час: цвет неба, горизонта и земли, тучи, отражения, солнце и луна (луна — напротив солнца).
## Раз в DAY_CYCLE.sky_sec: каждая смена пересчитывает карту отражений.
static func apply_sky(sky: ShaderMaterial, hour: float, sa: Vector2) -> void:
	if sky == null:
		return
	var t: float = time_for(hour, sa)
	var sky_color: Color = color_at("skyColor", t)
	var to_sun: Vector3 = DayCycle.dir_from(sa.x, sa.y)
	sky.set_shader_parameter("overcast", float(weather(String(RaidConditions.current.weather)).overcast))
	sky.set_shader_parameter("sky_color", sky_color)
	sky.set_shader_parameter("horizon_color", sky_color * 0.8)
	sky.set_shader_parameter("ground_color", sky_color * 0.5)
	sky.set_shader_parameter("reflection", value_at("skyReflection", t))
	sky.set_shader_parameter("sun_dir", to_sun)
	sky.set_shader_parameter("moon_dir", -to_sun)
	sky.set_shader_parameter("clouds_shift", fposmod(hour * float(Balance.TOD_LIGHT.clouds_drift), 1.0))
