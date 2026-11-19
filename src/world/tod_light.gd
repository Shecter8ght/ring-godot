class_name TodLight
extends RefCounted
## Свет по времени суток по схеме Road to Vostok на всех рейдовых картах (решение владельца 2026-11-05;
## Balance.TOD_LIGHT, таблица data/lighting/time_of_day.json, стенд сравнения tools/rtv_look.tscn).
## Как у них: по их часам t (0…2400) из таблицы берутся цвет и сила солнца, цвет луны, рассеянный свет (ясно и пасмурно),
## цвет неба, отражения неба, плотность и цвет объёмной дымки. Небо — tod_sky.gdshader (их цвета по часам, наши облака).
## Солнце и Луна у нас ходят по астрономии (DayCycle), поэтому их час подбирается по высоте нашего солнца (утро — на
## восходящей половине, вечер — на заходящей). Ночью светит луна напротив солнца, как у них.
## Погода — наша (решение владельца 2026-11-19, Balance.TOD_LIGHT.weather): под тучами прямого света и теней почти нет,
## свет идёт от неба; дождь темнее и с завесой; туман — плотная дымка с бледным солнцем; в ясную — мягкая полутень
## и воздушная дымка вдаль цвета неба у горизонта (дальние дома уходят в небо, а не стоят «макетом»). Погода меняется
## плавно (weather_sec). Свой код; их файлы игре не нужны.

const SKY_SHADER: String = "res://src/world/tod_sky.gdshader"
const LAB_DOMAIN: String = "atmosphere_tod"

static var _table: Dictionary = {}
static var _cloud_blur: Dictionary = {}
static var _cloud_spread: Dictionary = {}


## Включён ли их свет: Balance.TOD_LIGHT.on, выбор игрока (Settings.sky_mode = "tod" — читы «Свет и небо»,
## стенд света) и таблица на месте.
static func active() -> bool:
	return bool(Balance.TOD_LIGHT.get("on", false)) and Settings.sky_mode == "tod" and not table().is_empty()


## Ползунок стенда «Свет и атмосфера» при их свете (LAB_RULES.atmosphere_tod; без стенда — исходное число).
static func lab(key: String) -> float:
	return Balance.lab_number(LAB_DOMAIN, key)


static func lab_color(key: String) -> Color:
	return LabTuning.value(LAB_DOMAIN, key) as Color


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


## Числа погоды из таблицы (Balance.TOD_LIGHT.weather).
static func weather(w: String) -> Dictionary:
	var all: Dictionary = Balance.TOD_LIGHT.weather
	return all.get(w, all.clear)


## Погода сейчас: числа таблицы, плавно идущие к погоде рейда за weather_sec (дождь начинается не скачком).
static var _wx: Dictionary = {}
static var _wx_from: Dictionary = {}
static var _wx_key: String = ""
static var _wx_ms: int = 0
## Жара без очков (RaidWeather): пересвет и блёклость 0…1 — цветокоррекцию окружения ведёт TodLight.
static var heat_k: float = 0.0


## Новая погода — сразу, без перехода (начало рейда, смена из настроек).
static func snap_weather() -> void:
	_wx_key = ""
	_wx.clear()


static func weather_now() -> Dictionary:
	var key: String = String(RaidConditions.current.weather)
	var target: Dictionary = weather(key)
	var now: int = Time.get_ticks_msec()
	if _wx.is_empty() or _wx_key == "":
		_wx = target.duplicate(true)
		_wx_from = _wx.duplicate(true)
		_wx_key = key
		_wx_ms = now
		return _wx
	if key != _wx_key:
		_wx_from = _wx.duplicate(true)
		_wx_key = key
		_wx_ms = now
	var k: float = smoothstep(0.0, 1.0, float(now - _wx_ms) / 1000.0 / maxf(float(Balance.TOD_LIGHT.weather_sec), 0.01))
	for name: String in target:
		var to: Variant = target[name]
		var from: Variant = _wx_from.get(name, to)
		if to is Array:
			var mixed: Array = []
			for i: int in range((to as Array).size()):
				mixed.append(lerpf(float((from as Array)[i]), float((to as Array)[i]), k))
			_wx[name] = mixed
		else:
			_wx[name] = lerpf(float(from), float(to), k)
	return _wx


## Доля ночи по их часам: 1 — луна, 0 — солнце (на их восходе и закате — плавно).
static func night_k(t: float) -> float:
	var tb: Dictionary = Balance.TOD_LIGHT
	var up: float = smoothstep(float(tb.day_from) - 50.0, float(tb.day_from) + 75.0, t)
	var down: float = 1.0 - smoothstep(float(tb.day_to) - 75.0, float(tb.day_to) + 50.0, t)
	return 1.0 - up * down


## Яркость неба: погода, ночью — светлее (силуэты читаются на фоне неба), под ночными тучами — ещё светлее.
static func sky_gain(wx: Dictionary, night: float) -> float:
	var tb: Dictionary = Balance.TOD_LIGHT
	var night_gain: float = float(tb.night_sky) * lerpf(1.0, float(tb.night_overcast_sky), float(wx.overcast))
	return float(wx.sky) * lerpf(1.0, night_gain, night) * lab("sky")


## Средняя яркость облачного слоя (доля от цвета неба): ясные облака → тучи.
static func clouds_mean(wx: Dictionary) -> float:
	return lerpf(float(Balance.TOD_LIGHT.clear_mean), float(Balance.TOD_LIGHT.overcast_mean), float(wx.overcast)) * lab("clouds_bright")


## Во сколько раз небо у горизонта ярче среднего: ясное — светлее, пасмурное — темнее зенита.
static func horizon_k(wx: Dictionary) -> float:
	return lerpf(float(Balance.TOD_LIGHT.sky_look.horizon), float(Balance.TOD_LIGHT.sky_look.overcast_horizon), float(wx.overcast))


## Цвет неба у горизонта — он же цвет воздушной дымки вдаль: дальние дома растворяются ровно в небо.
## Считается в линейном свете (как в шейдере неба), наружу — sRGB: свойства движка и шейдера сами переводят обратно.
static func haze_color(t: float, wx: Dictionary, night: float) -> Color:
	var c: Color = color_at("skyColor", t).srgb_to_linear() * (clouds_mean(wx) * horizon_k(wx) * sky_gain(wx, night) * float(Balance.TOD_LIGHT.haze_k))
	return Color(c.r, c.g, c.b).linear_to_srgb()


## Низкое солнце (рассвет, закат): прямой свет слабее, свет неба относительно сильнее — тени не проваливаются.
## 0 — солнце высоко, 1 — у горизонта.
static func low_sun(elev: float) -> float:
	var ls: Dictionary = Balance.TOD_LIGHT.low_sun
	return 1.0 - smoothstep(float(ls.from), float(ls.to), elev)


## Окружение под их свет: тональная кривая AgX как у них, объёмная дымка их параметров, без глубинного тумана;
## SSAO, SDFGI и отражения в лужах (SSR) — по качеству графики, как раньше. Тень солнца — их даль.
static func prepare(we: WorldEnvironment, sun: DirectionalLight3D) -> void:
	var tb: Dictionary = table()
	if we and we.environment:
		var e: Environment = we.environment
		var env: Dictionary = tb.get("environment", {})
		e.set_meta("tod", true)
		e.tonemap_mode = Environment.TONE_MAPPER_AGX
		e.tonemap_agx_white = lab("tone_white")
		e.tonemap_agx_contrast = lab("tone_contrast")
		e.tonemap_exposure = float(env.get("tonemap_exposure", 1.0))
		# цветокоррекция — только насыщенность по погоде; таблица цвета прежнего света не нужна
		e.adjustment_enabled = false
		e.adjustment_color_correction = null
		e.adjustment_brightness = 1.0
		e.adjustment_contrast = 1.0
		# дымка вдаль (по расстоянию) — наша, числа ставит apply по погоде
		e.fog_enabled = true
		e.fog_mode = Environment.FOG_MODE_DEPTH
		e.fog_depth_curve = 1.0
		e.fog_aerial_perspective = 0.0
		e.fog_height_density = 0.0
		e.fog_light_energy = 1.0
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
		sun.shadow_blur = 1.0
		sun.directional_shadow_blend_splits = true
		sun.shadow_enabled = true
		var o: Dictionary = sun.get_meta("orig_sun_shadow", {}) as Dictionary
		# тень как в сцене — на случай возврата к прежнему свету (RaidAtmosphere.relight)
		if not sun.has_meta("pre_tod_shadow") and not o.is_empty():
			sun.set_meta("pre_tod_shadow", o)
		sun.set_meta("orig_sun_shadow", {"max_m": lab("shadow_m"),
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
		# своя поправка контраста панорамы; ползунки стенда множат её в apply_sky
		m.set_meta("clear_contrast", _contrast(clear_path, float(Balance.TOD_LIGHT.clear_spread), float(Balance.TOD_LIGHT.clear_mean)))
		m.set_meta("overcast_contrast", _contrast(over_path, float(Balance.TOD_LIGHT.overcast_spread), float(Balance.TOD_LIGHT.overcast_mean)))
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


## Свет на наш час и погоду: солнце или луна, рассеянный свет, дымка вблизи и вдаль, тон. sa — (высота, азимут)
## солнца (DayCycle.sun_at), night_w — доля ночи (свечение фонарей и ракет — наше, как раньше).
static func apply(hour: float, sa: Vector2, sun: DirectionalLight3D, e: Environment, night_w: float) -> void:
	var tb: Dictionary = Balance.TOD_LIGHT
	var t: float = time_for(hour, sa)
	var wx: Dictionary = weather_now()
	var overcast: float = float(wx.overcast)
	var day: bool = t > float(tb.day_from) and t < float(tb.day_to)
	var night: float = night_k(t)
	var to_sun: Vector3 = DayCycle.dir_from(sa.x, sa.y)
	var to_moon: Vector3 = -to_sun
	if sun:
		var to: Vector3 = to_sun if day else to_moon
		sun.global_basis = Basis.looking_at(-to, Vector3.UP if absf(to.y) < 0.99 else Vector3.FORWARD)
		if day:
			sun.light_energy = value_at("sunEnergy", t) * float(wx.sun) * lerpf(1.0, float(tb.low_sun.sun), low_sun(sa.x)) * lab("sun")
			sun.light_color = color_at("sunColor", t) * lab_color("sun_tint")
		else:
			sun.light_energy = float(tb.moon_energy) * float(wx.moon) * lab("moon")
			sun.light_color = color_at("moonColor", t) * lab_color("sun_tint")
		sun.visible = sun.light_energy > 0.001
		sun.shadow_enabled = true
		sun.light_volumetric_fog_energy = 1.0
		# полутень: у предмета тень резкая, дальше размывается; под тучами светило «размазано» — тень мягкая.
		# Низкое светило: мягкая тень движка пропускает крыши в каскадах — там обычная фильтрация с размытием
		var soft: float = float(wx.soft) * lab("shadow_soft")
		var high: bool = absf(to.y) > float(tb.soft_min_sin)
		sun.light_angular_distance = soft if high else 0.0
		sun.shadow_blur = 1.0 if high else clampf(1.0 + soft * 0.5, 1.0, 3.0)
	if e:
		var sky_color: Color = color_at("skyColor", t)
		var haze: Array = wx.haze
		var fogginess: float = clampf((float(wx.fog) - 1.0) / 4.0, 0.0, 1.0)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		e.ambient_light_color = color_at("ambientColor", t).lerp(color_at("overcastColor", t), overcast)
		e.ambient_light_sky_contribution = lab("sky_part")
		e.ambient_light_energy = lab("ambient") * float(wx.ambient) * lerpf(1.0, float(tb.night_ambient), night) \
			* lerpf(1.0, float(tb.low_sun.ambient), low_sun(sa.x) * (1.0 - night))
		e.background_energy_multiplier = 1.0
		# жара без очков (RaidWeather): пересвет, мягче контраст, блёкло
		e.tonemap_exposure = float(wx.exposure) * (1.0 + 0.4 * heat_k)
		e.tonemap_agx_white = lab("tone_white")
		e.tonemap_agx_contrast = lab("tone_contrast") * (1.0 - 0.12 * heat_k)
		e.adjustment_saturation = lab("saturation") * float(wx.sat) * lerpf(1.0, float(tb.night_sat), night) * (1.0 - 0.2 * heat_k)
		e.adjustment_enabled = not is_equal_approx(e.adjustment_saturation, 1.0)
		# дымка вблизи (объёмная: лучи, свет фонарей): в тумане и дожде рассеивает свет солнца и неба
		# дымка вдаль: цвет неба у горизонта, у солнца светится; объёмная светится тем же цветом — дальнее уходит в небо
		var hc: Color = haze_color(t, wx, night) * lab_color("fog_tint")
		e.volumetric_fog_density = value_at("fogDensity", t) * float(wx.fog) / float(tb.fog_div) * lab("fog")
		e.volumetric_fog_emission = Color(hc.r, hc.g, hc.b)
		e.volumetric_fog_emission_energy = lab("fog_glow") * float(tb.fog_glow_k)
		e.volumetric_fog_anisotropy = lab("fog_forward")
		e.volumetric_fog_albedo = color_at("sunScatter", t).lerp(Color(0.62, 0.64, 0.66), fogginess)
		e.fog_enabled = true
		e.fog_mode = Environment.FOG_MODE_DEPTH
		e.fog_depth_begin = float(haze[0])
		e.fog_depth_end = float(haze[1])
		e.fog_depth_curve = 1.0
		e.fog_density = clampf(float(haze[2]) * lab("haze"), 0.0, 1.0)
		e.fog_light_color = Color(hc.r, hc.g, hc.b)
		e.fog_light_energy = 1.0
		e.fog_sun_scatter = float(tb.haze_sun_scatter) * float(wx.sun) * (1.0 - night)
		e.fog_sky_affect = float(wx.sky_fog)
		# свечение — только ночью, вокруг фонарей и ракет (наше: у них свечения нет совсем)
		e.glow_hdr_threshold = float(Balance.NIGHT_ENV.glow_threshold)
		e.glow_intensity = float(Balance.NIGHT_ENV.glow_intensity) * night_w
		e.glow_bloom = 0.0
		e.glow_enabled = bool(e.get_meta("tod_glow", true)) and e.glow_intensity > 0.001


## Небо на наш час и погоду: цвет неба по часам, градиент к зениту и горизонту, тучи и пелена, дымка у горизонта,
## земля под горизонтом, солнце и луна (луна — напротив солнца).
## Раз в DAY_CYCLE.sky_sec: каждая смена пересчитывает карту отражений.
static func apply_sky(sky: ShaderMaterial, hour: float, sa: Vector2) -> void:
	if sky == null:
		return
	var tb: Dictionary = Balance.TOD_LIGHT
	var look: Dictionary = tb.sky_look
	var t: float = time_for(hour, sa)
	var wx: Dictionary = weather_now()
	var night: float = night_k(t)
	var day: bool = t > float(tb.day_from) and t < float(tb.day_to)
	var gain: float = sky_gain(wx, night)
	var sky_color: Color = color_at("skyColor", t)
	var to_sun: Vector3 = DayCycle.dir_from(sa.x, sa.y)
	var hc: Color = haze_color(t, wx, night)
	# земля под горизонтом: отражает свет неба и светила (albedo) — свет снизу в рассеянном свете
	var direct: float = (value_at("sunEnergy", t) * float(wx.sun) if day else float(tb.moon_energy) * float(wx.moon)) * absf(to_sun.y)
	var direct_color: Color = (color_at("sunColor", t) if day else color_at("moonColor", t)).srgb_to_linear()
	var ground: Color = ((sky_color.srgb_to_linear() * (clouds_mean(wx) * gain) + direct_color * direct) * float(tb.ground_albedo)).linear_to_srgb()
	sky.set_shader_parameter("overcast", float(wx.overcast))
	sky.set_shader_parameter("veil", float(wx.veil))
	sky.set_shader_parameter("sky_color", Color(sky_color.r, sky_color.g, sky_color.b))
	sky.set_shader_parameter("sky_gain", gain)
	sky.set_shader_parameter("ground_color", Color(ground.r, ground.g, ground.b))
	sky.set_shader_parameter("haze_color", hc)
	sky.set_shader_parameter("haze_amount", clampf(0.55 + 0.45 * float((wx.haze as Array)[2]), 0.0, 1.0))
	sky.set_shader_parameter("horizon_pow", float(look.horizon_pow))
	sky.set_shader_parameter("zenith", float(look.zenith))
	sky.set_shader_parameter("zenith_tint", look.zenith_tint)
	sky.set_shader_parameter("horizon_k", float(look.horizon))
	sky.set_shader_parameter("overcast_zenith", float(look.overcast_zenith))
	sky.set_shader_parameter("overcast_horizon", float(look.overcast_horizon))
	sky.set_shader_parameter("sun_side", float(look.sun_side))
	sky.set_shader_parameter("sun_through", clampf(float(wx.sun), 0.0, 1.0))
	# ночью небо на экране светлее (night_sky), а свет от него на землю — прежний
	sky.set_shader_parameter("reflection", value_at("skyReflection", t) / lerpf(1.0, float(tb.night_sky), night) * lab("reflection"))
	sky.set_shader_parameter("clear_mean", float(tb.clear_mean) * lab("clouds_bright"))
	sky.set_shader_parameter("overcast_mean", float(tb.overcast_mean) * lab("clouds_bright"))
	sky.set_shader_parameter("clear_contrast", float(sky.get_meta("clear_contrast", 1.0)) * lab("clouds_contrast"))
	sky.set_shader_parameter("overcast_contrast", float(sky.get_meta("overcast_contrast", 1.0)) * lab("clouds_contrast"))
	sky.set_shader_parameter("sun_dir", to_sun)
	sky.set_shader_parameter("moon_dir", -to_sun)
	sky.set_shader_parameter("clouds_shift", fposmod(hour * float(tb.clouds_drift), 1.0))
