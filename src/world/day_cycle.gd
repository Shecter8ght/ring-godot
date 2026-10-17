class_name DayCycle
extends Node
## Смена суток в рейде: часы идут (Balance.DAY_CYCLE.hour_sec — секунд на игровой час), солнце и
## Луна ходят по небу как в жизни (широта, день года — Balance.DAY_CYCLE; север карты — −Z, восток —
## +X). По высоте солнца плавно смешиваются «день / закат / ночь»: сила и цвет света, рассеянный
## свет, выдержка, туман, свечение, небо (day_cycle_sky — панорамы дня и заката под погоду, или
## расчётное AtmosphereSky — Settings.sky_mode; ночью — звёзды и Луна). Фаза (RaidConditions.current.time)
## меняется сама — по ней фонари, зрение ИИ.
## Начало — час старта выбранного времени (Balance.RAID_TIME.start_hour). Время ведёт хост и
## раз в sync_sec рассылает. Создаёт RaidAtmosphere.

static var current: DayCycle

## Сейчас, часы (0..24, местное солнечное время).
var hour: float = 12.0
## Высота солнца, градусы (для отладки и тестов).
var sun_elev: float = 0.0
## Плавная дальность зрения ИИ на улице, м (вместо ступени по фазе).
var view: float = 100.0

var _atm: RaidAtmosphere
var _sky: ShaderMaterial
## Небо расчётное (AtmosphereSky), а не из панорам.
var _calc: bool = false
var _profiles: Dictionary = {}
var _conf: Dictionary = {}
var _phase: String = ""
var _sync_t: float = 0.0
var _sky_t: float = 0.0
var _light_t: float = 0.0


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null


## Начать с часа старта для выбранного времени суток (RaidConditions.current.time).
func start(atm: RaidAtmosphere, time_key: String) -> void:
	_atm = atm
	hour = float((Balance.RAID_TIME.get(time_key, Balance.RAID_TIME.day) as Dictionary).get("start_hour", 12.0))
	# точное время из настроек — у того, кто ведёт время (одиночная игра, хост)
	if Settings.raid_hour >= 0.0 and (not Net.is_networked() or multiplayer.is_server()):
		hour = Settings.raid_hour
	rebuild()


## Перевести часы (настройки, хост): свет и небо — сразу, гостям — сразу же.
func set_hour(h: float) -> void:
	if Net.is_networked() and not multiplayer.is_server():
		return
	hour = fposmod(h, 24.0)
	_tick(0.0, true)
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_hour", [hour], false)


## Погода или карта сменились: собрать заново профили времени суток и небо.
func rebuild() -> void:
	_profiles.clear()
	for k in ["day", "dusk", "night"]:
		_profiles[k] = _profile(k)
	_build_sky()
	_phase = ""
	_tick(0.0, true)


func _process(delta: float) -> void:
	hour = fposmod(hour + delta / float(Balance.DAY_CYCLE.hour_sec), 24.0)
	_tick(delta, false)
	# облака плывут каждый кадр (карта отражений неба обновляется сама — Sky в реальном времени)
	if _calc and _sky:
		AtmosphereSky.clouds_tick(_sky, hour)
	if Net.is_networked() and multiplayer.is_server():
		_sync_t -= delta
		if _sync_t <= 0.0:
			_sync_t = float(Balance.DAY_CYCLE.sync_sec)
			Net.broadcast_scene(self, &"_rpc_hour", [hour], false)


## Часы для HUD: «18:46».
func clock_text() -> String:
	var total := int(floor(hour * 60.0)) % (24 * 60)
	return "%02d:%02d" % [total / 60, total % 60]


@rpc("authority", "call_remote", "unreliable")
func _rpc_hour(h: float) -> void:
	# большой скачок (хост перевёл часы) — свет и небо сразу
	var jump := absf(h - hour) > 0.1
	hour = h
	if jump:
		_tick(0.0, true)


# ---------------------------------------------------------------- астрономия

## Направление на светило (мир) по высоте и азимуту, градусы (азимут от севера к востоку).
static func dir_from(elev: float, az: float) -> Vector3:
	var e := deg_to_rad(elev)
	var a := deg_to_rad(az)
	# север — −Z, восток — +X
	return Vector3(sin(a) * cos(e), sin(e), -cos(a) * cos(e)).normalized()


## Высота и азимут светила со склонением decl, градусы, при часовом угле ha, градусы.
static func alt_az(decl: float, ha: float) -> Vector2:
	var lat := deg_to_rad(float(Balance.DAY_CYCLE.latitude))
	var d := deg_to_rad(decl)
	var h := deg_to_rad(ha)
	var sin_alt := sin(lat) * sin(d) + cos(lat) * cos(d) * cos(h)
	var alt := asin(clampf(sin_alt, -1.0, 1.0))
	var az := atan2(-sin(h) * cos(d), cos(lat) * sin(d) - sin(lat) * cos(d) * cos(h))
	return Vector2(rad_to_deg(alt), fposmod(rad_to_deg(az), 360.0))


## Склонение солнца в день года.
static func sun_decl() -> float:
	var n := float(Balance.DAY_CYCLE.day_of_year)
	return 23.44 * sin(deg_to_rad(360.0 / 365.0 * (284.0 + n)))


## Солнце: (высота, азимут) в час h.
static func sun_at(h: float) -> Vector2:
	return alt_az(sun_decl(), (h - 12.0) * 15.0)


## Луна: близко к полнолунию — напротив солнца с отставанием на moon_lag часов, склонение —
## противоположное солнцу (как у полной Луны).
static func moon_at(h: float) -> Vector2:
	return alt_az(-sun_decl() * 0.9, (h - 12.0 + 12.0 - float(Balance.DAY_CYCLE.moon_lag)) * 15.0)


# ---------------------------------------------------------------- профили времени суток

## Всё, что RaidAtmosphere ставит для времени k (и нынешней погоды), — в одном словаре.
func _profile(k: String) -> Dictionary:
	var c := RaidConditions.current
	var t: Dictionary = Balance.RAID_TIME[k]
	var lc: Dictionary = {}
	var path: Variant = _atm.get_parent().get("sector_path") if _atm else null
	if path != null and String(path) != "":
		lc = SectorBuilder.load_def(String(path)).get("light", {})
	var ak: float = float(lc.get("ambient_k_%s_%s" % [k, c.weather], lc.get("ambient_k_" + k, lc.get("ambient_k", 1.0))))
	var p := {
		"sun_energy": float(t.sun_energy) * float(lc.get("sun_k", 1.0)),
		"sun_color": t.sun_color,
		"ambient": 0.8 * float(t.ambient) * ak,
		"exposure": float(t.get("exposure", 1.0)),
		"view": float(t.view),
		"vol": float((Balance.VOLUMETRIC_TIME.get(k, {}) as Dictionary).get("density", 1.0)),
		"vol_sun": float((Balance.VOLUMETRIC_TIME.get(k, {}) as Dictionary).get("sun", 1.4)),
		"fog_color": Color(0.62, 0.64, 0.66) if k != "night" else Color(0.05, 0.06, 0.08),
	}
	# погода: пелена под панораму, сила солнца за ней
	var conf := hdri_conf(k)
	var w: Dictionary = Balance.HDRI_WEATHER.get(String(c.weather), Balance.HDRI_WEATHER["clear"])
	var veil: float = float(conf.get("veil", 1.0))
	p["sun_energy"] = float(p.sun_energy) * float(conf.get("sun_k", 1.0)) * lerpf(1.0, float(w.sun_k), veil)
	p["hdri_exposure"] = float(conf.get("exposure", 1.0)) * lerpf(1.0, float(w.exposure), veil)
	p["overcast"] = float(w.overcast) * veil
	p["haze"] = float(conf.get("haze", 0.0))
	p["horizon_cut"] = float(conf.get("horizon_cut", 0.0))
	if k == "night":
		p["sun_energy"] = float(t.sun_energy) * (0.0 if String(c.weather) == "rain" else 1.0)
	return p


## Панорама для времени k под нынешнюю погоду (данные карты "sky_hdri"), с положением её солнца.
func hdri_conf(k: String) -> Dictionary:
	var path: Variant = _atm.get_parent().get("sector_path") if _atm else null
	if path == null or String(path) == "":
		return {}
	var all: Dictionary = SectorBuilder.load_def(String(path)).get("sky_hdri", {})
	var conf: Dictionary = (all.get(k + "_" + String(RaidConditions.current.weather), all.get(k, {})) as Dictionary).duplicate()
	if conf.is_empty() or not ResourceLoader.exists(String(conf.get("a", ""))):
		return {}
	if not conf.has("sun_u") and FileAccess.file_exists(RaidAtmosphere.SKY_INFO):
		var info: Variant = JSON.parse_string(FileAccess.get_file_as_string(RaidAtmosphere.SKY_INFO))
		if info is Dictionary:
			var si: Dictionary = (info as Dictionary).get(String(conf.a).get_file().get_basename(), {})
			if si.has("sun_u"):
				conf["sun_u"] = si.sun_u
	return conf


# ---------------------------------------------------------------- небо

## Небо: из панорам (как сейчас) или расчётное (Settings.sky_mode = "calc", AtmosphereSky) — ночь у
## обоих одна. Свет на земле (профили выше) от режима не зависит.
func _build_sky() -> void:
	_sky = null
	_calc = false
	var day := hdri_conf("day")
	var dusk := hdri_conf("dusk")
	_conf = {"day": day, "dusk": dusk}
	if day.is_empty() or dusk.is_empty():
		return
	var m: ShaderMaterial = AtmosphereSky.material() if Settings.sky_mode == "calc" else null
	_calc = m != null
	if m == null:
		m = ShaderMaterial.new()
		m.shader = load("res://src/world/day_cycle_sky.gdshader")
		# погода (RaidWeather._set_overcast) небо из панорам не трогает
		m.set_meta("hdri", true)
		m.set_shader_parameter("sky_a", load(String(day.a)))
		m.set_shader_parameter("sky_b", load(String(dusk.a)))
		m.set_shader_parameter("has_b", true)
		m.set_shader_parameter("clamp_max", float(day.get("clamp_max", 40.0)))
		var w: Dictionary = Balance.HDRI_WEATHER.get(String(RaidConditions.current.weather), Balance.HDRI_WEATHER["clear"])
		m.set_shader_parameter("tint", w.tint)
	var night := RaidAtmosphere.night_sky_material()
	for pn in ["stars_tex", "has_stars_tex", "stars_energy", "stars_floor", "moon_tex", "has_moon_tex", "moon_size",
			"moon_energy", "halo_strength", "halo_size"]:
		var v: Variant = night.get_shader_parameter(pn)
		if v != null:
			m.set_shader_parameter(pn, v)
	var sky := Sky.new()
	sky.sky_material = m
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	if _calc:
		# облака движутся — отражения и рассеянный свет от неба пересчитываются каждый кадр
		sky.process_mode = Sky.PROCESS_MODE_REALTIME
		AtmosphereSky.clouds_tick(m, hour)
	_sky = m
	var e := _env()
	if e:
		e.sky = sky
		e.background_mode = Environment.BG_SKY
		e.background_energy_multiplier = 1.0
		e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY


func _env() -> Environment:
	if _atm == null:
		return null
	var we := _atm.get_parent().find_child("WorldEnvironment", false, false) as WorldEnvironment
	return we.environment if we else null


# ---------------------------------------------------------------- каждый кадр

## Доли «день / закат / ночь» по высоте солнца.
static func weights(elev: float) -> Dictionary:
	var dc: Dictionary = Balance.DAY_CYCLE
	var day := smoothstep(float(dc.dusk_to), float(dc.day_from), elev)
	var night := 1.0 - smoothstep(float(dc.night_to), float(dc.dusk_from), elev)
	var dusk := maxf(0.0, 1.0 - day - night)
	return {"day": day, "dusk": dusk, "night": night}


func _mixf(w: Dictionary, key: String) -> float:
	var v := 0.0
	for k in w:
		v += float(w[k]) * float((_profiles[k] as Dictionary)[key])
	return v


func _mixc(w: Dictionary, key: String) -> Color:
	var v := Color(0, 0, 0, 0)
	for k in w:
		v += ((_profiles[k] as Dictionary)[key] as Color) * float(w[k])
	return v


func _tick(delta: float, force: bool) -> void:
	if _atm == null or _profiles.is_empty():
		return
	var sa := sun_at(hour)
	var ma := moon_at(hour)
	sun_elev = sa.x
	var w := weights(sa.x)
	view = _mixf(w, "view")
	# фаза для игры (фонари, зрение, фонари ИИ): преобладающая доля
	var ph := "day"
	for k in ["dusk", "night"]:
		if float(w[k]) > float(w[ph]):
			ph = k
	if ph != _phase:
		var first := _phase == ""
		_phase = ph
		if String(RaidConditions.current.time) != ph:
			RaidConditions.current["time"] = ph
			if not first and RaidWeather.current:
				RaidWeather.current.changed.emit()
	_light_t -= delta
	if force or _light_t <= 0.0:
		_light_t = float(Balance.DAY_CYCLE.light_sec)
		_apply_light(w, sa, ma)
	_sky_t -= delta
	if _sky and (force or _sky_t <= 0.0):
		_sky_t = float(Balance.DAY_CYCLE.sky_sec)
		_apply_sky(w, sa, ma)


func _apply_light(w: Dictionary, sa: Vector2, ma: Vector2) -> void:
	var sun := _atm.get_parent().get_node_or_null("Sun") as DirectionalLight3D
	var e := _env()
	var dc: Dictionary = Balance.DAY_CYCLE
	if sun:
		# днём — солнце (гаснет у горизонта), ночью — Луна (пока над горизонтом)
		var lit := smoothstep(float(dc.sun_off), float(dc.sun_on), sa.x)
		var to: Vector3
		var energy: float
		var col: Color
		if lit > 0.0005:
			to = dir_from(sa.x, sa.y)
			var dd := float(w.day) + float(w.dusk)
			var wd := {"day": float(w.day) / maxf(dd, 0.001), "dusk": float(w.dusk) / maxf(dd, 0.001)}
			energy = _mixf(wd, "sun_energy") * lit
			col = _mixc(wd, "sun_color")
		else:
			to = dir_from(maxf(ma.x, 2.0), ma.y)
			energy = float((_profiles.night as Dictionary).sun_energy) * float(w.night) * smoothstep(0.0, 8.0, ma.x)
			col = (_profiles.night as Dictionary).sun_color
		# светило за облаком — свет тускнеет (расчётное небо: те же шумы, что рисуют облака)
		if _calc and _sky:
			var cam := get_viewport().get_camera_3d()
			energy *= AtmosphereSky.sun_through(_sky, cam.global_position if cam else Vector3.ZERO, to)
		# свет идёт от светила: −Z узла смотрит от него
		sun.global_basis = Basis.looking_at(-to, Vector3.UP if absf(to.y) < 0.99 else Vector3.FORWARD)
		sun.light_energy = energy
		sun.light_color = col
		sun.visible = String(RaidConditions.current.weather) != "rain" and energy > 0.001
		sun.light_volumetric_fog_energy = lerpf(_mixf(w, "vol_sun"), float(Balance.NIGHT_ENV.moon_fog), float(w.night))
	if e:
		e.ambient_light_energy = _mixf(w, "ambient")
		# ночью рассеянный — ровным тёмно-холодным цветом (небо почти чёрное)
		e.ambient_light_sky_contribution = 1.0 - float(w.night)
		e.ambient_light_color = Balance.NIGHT_ENV.ambient_color
		e.tonemap_exposure = _mixf(w, "exposure")
		e.fog_light_color = _mixc(w, "fog_color")
		if e.has_meta("vol_base") and e.volumetric_fog_enabled:
			e.volumetric_fog_density = float(e.get_meta("vol_base")) * _mixf(w, "vol") * lerpf(1.0, float(Balance.NIGHT_ENV.fog_k), float(w.night))
		var day_env: Dictionary = e.get_meta("day", {})
		if not day_env.is_empty():
			# свечение днём — Balance.DAY_GLOW (нет), к ночи — как ночью (фонари, ракеты)
			e.glow_hdr_threshold = lerpf(float(day_env.glow_threshold), float(Balance.NIGHT_ENV.glow_threshold), float(w.night))
			e.glow_intensity = lerpf(float(Balance.DAY_GLOW.intensity), float(Balance.NIGHT_ENV.glow_intensity), float(w.night))
			e.glow_bloom = lerpf(float(Balance.DAY_GLOW.bloom), float(Balance.NIGHT_ENV.glow_bloom), float(w.night))
			e.glow_enabled = bool(day_env.get("glow", true)) and e.glow_intensity > 0.001


func _apply_sky(w: Dictionary, sa: Vector2, ma: Vector2) -> void:
	var to_sun := dir_from(sa.x, sa.y)
	_sky.set_shader_parameter("night_k", float(w.night))
	_sky.set_shader_parameter("stars_rotation", hour * 15.0)
	_sky.set_shader_parameter("moon_dir", dir_from(ma.x, ma.y))
	if _calc:
		AtmosphereSky.update(_sky, to_sun, sa.x, String(RaidConditions.current.weather))
		return
	var sun_yaw := rad_to_deg(atan2(to_sun.x, -to_sun.z))
	for pair in [["day", "rotation_a"], ["dusk", "rotation_b"]]:
		var conf: Dictionary = _conf[pair[0]]
		var rot := float(conf.get("rotation", 0.0))
		if conf.has("sun_u"):
			rot = (float(conf.sun_u) - 0.5) * 360.0 - sun_yaw
		_sky.set_shader_parameter(pair[1], rot)
	var dd := float(w.day) + float(w.dusk)
	_sky.set_shader_parameter("mix_b", float(w.dusk) / maxf(dd, 0.001))
	var wd := {"day": float(w.day) / maxf(dd, 0.001), "dusk": float(w.dusk) / maxf(dd, 0.001)}
	# солнце ушло за горизонт — небо не дневное: панорама тускнеет (сумерки), потом гаснет
	var dc0: Dictionary = Balance.DAY_CYCLE
	var dim := lerpf(float(dc0.twilight_dim), 1.0, smoothstep(float(dc0.twilight_end), float(dc0.sun_on), sa.x))
	_sky.set_shader_parameter("exposure", _mixf(wd, "hdri_exposure") * dim)
	_sky.set_shader_parameter("overcast", _mixf(w, "overcast"))
	_sky.set_shader_parameter("haze", _mixf(wd, "haze"))
	_sky.set_shader_parameter("horizon_cut", _mixf(wd, "horizon_cut"))
	# панорамы гаснут вместе с солнцем, ночь проступает
	var dc: Dictionary = Balance.DAY_CYCLE
	_sky.set_shader_parameter("hdri_k", smoothstep(float(dc.sky_off), float(dc.sky_on), sa.x))
