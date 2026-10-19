class_name AtmosphereSky
extends RefCounted
## Расчётное небо — режим «расчёт» смены суток (DayCycle, Settings.sky_mode): материал
## atmosphere_sky.gdshader с таблицами рассеяния из data/sky_atmosphere.json (tools/gen_sky_atmosphere.py)
## и подгонка по высоте солнца и погоде из того же файла — яркость атмосферы, низ, оттенок отражений
## (Balance.SKY_CALC). Облака — объёмный слой в том же шейдере: шумы генерирует движок (FastNoiseLite,
## файлов нет), покрытие и высота — от погоды, ветер — от игровых часов (у всех игроков облака одни).
## Солнце за облаком тускнеет (sun_through) — по тем же шумам, что рисует шейдер. Непогода: тучи
## неровной толщины с рваным низом, низкие клочья своим ветром, полосы дождя вдали, молния в тучах
## (lightning). Смена погоды — небо перетекает за SKY_CALC.change_sec, перед дождём тучи собираются заранее
## (RaidWeather.rain_build). Нет таблиц — режима нет, небо из панорам.

const DATA := "res://data/sky_atmosphere.json"
const SHADER := "res://src/world/atmosphere_sky.gdshader"

static var _data: Dictionary = {}
static var _t_lut: ImageTexture
static var _ms_lut: ImageTexture
## Шумы облаков: карта покрытия (2D), форма клубов и детали (3D); их картинки — для света сквозь облака.
static var _cover: NoiseTexture2D
static var _shape: NoiseTexture3D
static var _detail: NoiseTexture3D
static var _cover_img: Image
static var _shape_imgs: Array[Image] = []
static var _detail_imgs: Array[Image] = []
## Смена погоды: параметры неба в миг смены (с них перетекаем), к какой погоде, доля пути; последние
## выставленные — снимок для следующей смены.
static var _from: Dictionary = {}
static var _to_weather: String = ""
static var _blend_t: float = 1.0
static var _last: Dictionary = {}
## Молния: секунд от начала вспышки (< 0 — нет), где она в тучах (как q шейдера), есть ли у неё видимый
## канал до земли; _flash_clear — погасить на небе прерванную вспышку (новый рейд).
static var _flash_t: float = -1.0
static var _flash_q: Vector3 = Vector3.ZERO
static var _bolt_on: bool = false
static var _flash_clear: bool = false


static func available() -> bool:
	return not _load().is_empty()


## Новый материал неба; null — нет таблиц.
static func material() -> ShaderMaterial:
	var d := _load()
	if d.is_empty():
		return null
	var m := ShaderMaterial.new()
	m.shader = load(SHADER)
	# погоду небо учитывает само (RaidWeather._set_overcast его не трогает)
	m.set_meta("hdri", true)
	m.set_shader_parameter("t_lut", _t_lut)
	m.set_shader_parameter("ms_lut", _ms_lut)
	var a: Dictionary = d.atmosphere
	m.set_shader_parameter("r_ground", float(a.rg))
	m.set_shader_parameter("r_top", float(a.rt))
	for k: String in ["ray_h", "mie_s", "mie_e", "mie_h", "mie_g", "oz_c", "oz_w", "view_h"]:
		m.set_shader_parameter(k, float(a[k]))
	m.set_shader_parameter("ray_s", _v3(a.ray_s))
	m.set_shader_parameter("oz_a", _v3(a.oz_a))
	var sc: Dictionary = Balance.SKY_CALC
	m.set_shader_parameter("sun_size", float(sc.sun_size))
	m.set_shader_parameter("sun_clamp", float(sc.sun_clamp))
	m.set_shader_parameter("ground_blend", float(sc.ground_blend))
	var cl: Dictionary = sc.clouds
	_make_noise()
	m.set_shader_parameter("cloud_cover", _cover)
	m.set_shader_parameter("cloud_shape", _shape)
	m.set_shader_parameter("cloud_detail", _detail)
	m.set_shader_parameter("cloud_sigma", float(cl.sigma))
	m.set_shader_parameter("cover_tile", float(cl.cover_tile))
	m.set_shader_parameter("shape_tile", float(cl.shape_tile))
	m.set_shader_parameter("detail_tile", float(cl.detail_tile))
	m.set_shader_parameter("detail_k", float(cl.detail_k))
	m.set_shader_parameter("cloud_sun", float(cl.sun))
	m.set_shader_parameter("cloud_far", float(cl.far))
	m.set_shader_parameter("cloud_haze", float(cl.haze))
	m.set_shader_parameter("cloud_steps", int(cl.steps))
	var su: Dictionary = sc.scud
	m.set_shader_parameter("scud_base", float(su.base))
	m.set_shader_parameter("scud_top", float(su.top))
	m.set_shader_parameter("scud_steps", int(su.steps))
	var fl: Dictionary = sc.flash
	m.set_shader_parameter("flash_core", float(fl.core))
	m.set_shader_parameter("flash_radius", float(fl.radius_km))
	m.set_shader_parameter("flash_amb", float(fl.amb))
	var fc: Color = fl.color
	m.set_shader_parameter("flash_color", Vector3(fc.r, fc.g, fc.b))
	var bo: Dictionary = fl.bolt
	m.set_shader_parameter("bolt_core", float(bo.core))
	m.set_shader_parameter("bolt_halo", float(bo.halo))
	return m


## Новый рейд (или время суток сменили руками): небо сразу как погода, без перетекания.
static func reset_blend() -> void:
	_from = {}
	_to_weather = ""
	_blend_t = 1.0
	_last = {}
	_flash_t = -1.0
	_bolt_on = false
	_flash_clear = true


## Солнце (направление на него, высота, °) и погода: дымка, облака, яркость и оттенок по подгонке.
## Погода сменилась — параметры перетекают за change_sec (delta — с прошлого вызова; 0 — без хода);
## перед дождём тучи собираются заранее (RaidWeather.rain_build).
static func update(m: ShaderMaterial, to_sun: Vector3, elev: float, weather: String, delta: float = 0.0) -> void:
	var d := _load()
	if d.is_empty() or m == null:
		return
	var sc: Dictionary = Balance.SKY_CALC
	var target := _params(weather, elev)
	var pre: float = RaidWeather.current.rain_build() if RaidWeather.current and weather != "rain" else 0.0
	if pre > 0.0:
		target = _mix(target, _params("rain", elev), pre)
	if weather != _to_weather:
		# с того, что было на небе в миг смены (в начале рейда — сразу)
		_from = _last.duplicate() if not _last.is_empty() and _to_weather != "" else {}
		_to_weather = weather
		_blend_t = 0.0 if not _from.is_empty() else 1.0
	_blend_t = minf(1.0, _blend_t + delta / maxf(float(sc.change_sec), 0.01))
	var p := target if _from.is_empty() or _blend_t >= 1.0 else _mix(_from, target, smoothstep(0.0, 1.0, _blend_t))
	_last = p
	var amb: Vector3 = p.amb
	var amb_eff := Vector3.ONE.lerp(amb, float(sc.amb_match))
	var clouds := float(p.cover) > 0.0
	m.set_shader_parameter("sun_dir", to_sun)
	m.set_shader_parameter("gain", exp(float(p.log_gain)))
	m.set_shader_parameter("mie_k", float(p.mie))
	# пасмурность из подгонки рисуют облака; ровная пелена — только если облаков нет
	m.set_shader_parameter("veil", 0.0 if clouds else float(p.overcast))
	m.set_shader_parameter("overcast", 0.0 if clouds else float(p.overcast))
	m.set_shader_parameter("oc_zenith", p.oc)
	m.set_shader_parameter("amb_tint", amb_eff)
	m.set_shader_parameter("view_k", float(p.view_k))
	# низ в таблице — до поправки оттенка (в карте отражений он умножится на неё)
	m.set_shader_parameter("ground_col", (p.ground as Vector3) * amb / amb_eff)
	m.set_shader_parameter("clouds_on", clouds)
	# солнце за облаком гаснет только там, где свет погоды его ещё не приглушил под пасмурность
	m.set_meta("cloud_shadow", clouds and float(p.overcast) <= 0.01)
	if clouds:
		# шагов по толщине слоя: в толстых тучах дождя иначе на днище ступеньки (в плотном марш кончается рано)
		var cl: Dictionary = sc.clouds
		m.set_shader_parameter("cloud_steps", clampi(int(ceil((float(p.top) - float(p.base)) / float(cl.step_km))),
			int(cl.steps), int(cl.steps_max)))
		for k: String in ["cover", "base", "top", "amb_bottom", "deck_var", "base_rag", "scud", "shafts"]:
			m.set_shader_parameter({"cover": "cloud_coverage", "base": "cloud_base", "top": "cloud_top",
				"scud": "scud_coverage"}.get(k, k), float(p[k]))
		# свет неба на облака — средняя яркость неба, какой её даёт подгонка (до поправки оттенка):
		# под сплошными тучами земля освещена, как раньше под пасмурной панорамой
		m.set_shader_parameter("cloud_amb", (p.oc as Vector3) * (7.0 / 9.0) / amb)


## Всё, что небо берёт от погоды на высоте солнца elev: подгонка (усиление — логарифмом, оттенок, низ,
## пасмурность) и облака из Balance.SKY_CALC.weather.
static func _params(weather: String, elev: float) -> Dictionary:
	var sc: Dictionary = Balance.SKY_CALC
	var ws: Dictionary = (sc.weather as Dictionary).get(weather, sc.weather.clear)
	var cal: Dictionary = _load().calib
	var rows: Dictionary = (cal.weather as Dictionary).get(weather, cal.weather.clear)
	var elevs: Array = cal.elev
	var x := clampf(elev - float(elevs[0]), 0.0, float(elevs.size() - 1))
	var i := mini(int(floor(x)), elevs.size() - 2)
	var f := x - float(i)
	var p := {
		# усиление в сумерках меняется на порядки — между строками по логарифму
		"log_gain": lerpf(log(float(rows.gain[i])), log(float(rows.gain[i + 1])), f),
		"amb": _v3(rows.amb[i]).lerp(_v3(rows.amb[i + 1]), f),
		"ground": _v3(rows.ground[i]).lerp(_v3(rows.ground[i + 1]), f),
		"oc": _v3(rows.oc[i]).lerp(_v3(rows.oc[i + 1]), f),
		"view_k": view_k(rows, cal, elev),
		"overcast": float(ws.overcast),
	}
	for k: String in ["mie", "cover", "base", "top", "amb_bottom", "deck_var", "base_rag", "scud", "shafts"]:
		p[k] = float(ws.get(k, 0.0))
	return p


static func _mix(a: Dictionary, b: Dictionary, t: float) -> Dictionary:
	var out := {}
	for k: String in b:
		var va: Variant = a.get(k, b[k])
		out[k] = (va as Vector3).lerp(b[k] as Vector3, t) if va is Vector3 else lerpf(float(va), float(b[k]), t)
	return out


## Каждый кадр: ветер — облака и клочья плывут по игровым часам hour (у всех игроков одинаково, часы
## ведёт хост), клочья быстрее и под углом; молния — пульсы вспышки.
static func clouds_tick(m: ShaderMaterial, hour: float, delta: float = 0.0) -> void:
	if m == null:
		return
	var sc: Dictionary = Balance.SKY_CALC
	var cl: Dictionary = sc.clouds
	var km := float(cl.wind_ms) * hour * float(Balance.DAY_CYCLE.hour_sec) / 1000.0
	# шум сдвигается против движения облаков
	m.set_shader_parameter("cloud_offset", -_dir_to(float(cl.wind_from) + 180.0) * fposmod(km, float(cl.cover_tile) * 8.0))
	var su: Dictionary = sc.scud
	m.set_shader_parameter("scud_offset", -_dir_to(float(cl.wind_from) + 180.0 + float(su.turn))
		* fposmod(km * float(su.wind_k), float(cl.cover_tile) * 8.0))
	if _flash_clear:
		_flash_clear = false
		for k: String in ["flash", "bolt", "bolt_branch"]:
			m.set_shader_parameter(k, 0.0)
	if _flash_t >= 0.0:
		_flash_t += delta
		var fl: Dictionary = sc.flash
		var bo: Dictionary = fl.bolt
		var v := 0.0
		var vb := 0.0
		for pulse: Array in fl.pulses:
			var dt := _flash_t - float(pulse[0])
			if dt >= 0.0:
				v += float(pulse[1]) * exp(-dt / float(fl.fade_sec))
				# канал светится дольше вспышки в туче: ток после удара
				vb += float(pulse[1]) * exp(-dt / float(bo.fade_sec))
		m.set_shader_parameter("flash", v)
		m.set_shader_parameter("flash_q", _flash_q)
		# ветви канала — только в первом ударе (ступенчатый лидер), следующие идут по главному каналу
		var first: Array = fl.pulses[0]
		m.set_shader_parameter("bolt", vb if _bolt_on else 0.0)
		m.set_shader_parameter("bolt_branch", float(first[1]) * exp(-_flash_t / float(bo.fade_sec)) if _bolt_on else 0.0)
		if maxf(v, vb) < 0.002 and _flash_t > 0.5:
			_flash_t = -1.0
			_flash_clear = true


## Молния у игрока в pos (м, мир), в случайной стороне. Обычно — вспышка в толще туч на dist_km; с долей
## bolt.chance — с видимым каналом до земли (ближе, bolt.dist_km), вспышка тогда у его верха, над низом туч.
## with_bolt: 1 — канал всегда, 0 — никогда (снимки, проверки), −1 — по случаю. Возвращает {"dir" —
## направление на молнию (мир), "bolt" — есть ли канал}; тучи нет — {}.
static func lightning(m: ShaderMaterial, pos: Vector3, with_bolt: int = -1) -> Dictionary:
	if m == null or m.get_shader_parameter("clouds_on") != true:
		return {}
	var fl: Dictionary = Balance.SKY_CALC.flash
	var bo: Dictionary = fl.bolt
	_bolt_on = randf() < float(bo.chance) if with_bolt < 0 else with_bolt > 0
	var dk: Array = bo.dist_km if _bolt_on else fl.dist_km
	var dist := randf_range(float(dk[0]), float(dk[1]))
	var off: Vector2 = m.get_shader_parameter("cloud_offset")
	var dir := _dir_to(randf() * 360.0)
	var base: float = m.get_shader_parameter("cloud_base")
	var top: float = m.get_shader_parameter("cloud_top")
	var qx := pos.x / 1000.0 + off.x + dir.x * dist
	var qz := pos.z / 1000.0 + off.y + dir.y * dist
	_flash_q = Vector3(qx, lerpf(base, top, 0.35), qz)
	_flash_t = 0.0
	var look := Vector3(dir.x, 0.0, dir.y)
	m.set_shader_parameter("bolt_n", 0)
	if _bolt_on:
		# низ туч над каналом — с рваным низом, как его рисует шейдер
		var low := base + _rag(m, qx, qz)
		_flash_q.y = low + float(bo.flash_above_km)
		look = _make_bolt(m, dir, dist, low)
	return {"dir": look, "bolt": _bolt_on}


## Канал молнии за dist км в сторону dir: от низа туч low (км над глазом; верх уходит в тучу на into_cloud_km
## и гаснет к низу туч за fade_km) до земли с наклоном до lean его высоты. Главный канал — ломаная середин
## (_bolt_path), из верхней половины — ветви, к концам тоньше и тусклее. Шейдеру — в картинной плоскости
## (проекция из глаза: отрезки остаются прямыми). Возвращает направление на середину канала (мир).
static func _make_bolt(m: ShaderMaterial, dir: Vector2, dist: float, low: float) -> Vector3:
	var bo: Dictionary = Balance.SKY_CALC.flash.bolt
	var top := low + float(bo.into_cloud_km)
	var fade := float(bo.fade_km)
	var main := _bolt_path(Vector2(0.0, top), Vector2(randf_range(-1.0, 1.0) * float(bo.lean) * top, 0.0),
		int(bo.depth), float(bo.rough))
	# x — вбок, км; y — высота над глазом; z — сила (к концу ветви — 0); w — 1 у ветвей
	var paths: Array[Array] = [[main, 1.0, 0.0]]
	# шейдеру — не больше 64 отрезков
	var room := floori(float(64 - (main.size() - 1)) / float(1 << maxi(int(bo.depth) - 2, 0)))
	for i in range(mini(randi_range(int(bo.branches[0]), int(bo.branches[1])), room)):
		var at: Vector2 = main[randi_range(floori(main.size() * 0.125), floori(main.size() * 0.5))]
		var ang := deg_to_rad(randf_range(20.0, 60.0)) * (1.0 if randf() < 0.5 else -1.0)
		var end := at + Vector2(sin(ang), -cos(ang)) * randf_range(0.25, 0.5) * top
		paths.append([_bolt_path(at, end, int(bo.depth) - 2, float(bo.rough)), float(bo.branch_k), 1.0])
	var fwd := Vector3(dir.x, 0.0, dir.y)
	var side := Vector3(-dir.y, 0.0, dir.x)
	var c := (fwd * dist + Vector3.UP * top * 0.5).normalized()
	var r := c.cross(Vector3.UP).normalized()
	var u := r.cross(c)
	var segs := PackedVector4Array()
	var ks := PackedVector4Array()
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for path: Array in paths:
		var pts: PackedVector2Array = path[0]
		var k0: float = path[1]
		var branch: float = path[2]
		var uv := PackedVector2Array()
		var kk := PackedFloat32Array()
		for i in range(pts.size()):
			var w := fwd * dist + side * pts[i].x + Vector3.UP * pts[i].y
			uv.append(Vector2(w.dot(r), w.dot(u)) / w.dot(c))
			# в туче канала не видно; ветвь к концу гаснет
			var tip := 1.0 - float(i) / float(pts.size() - 1) if branch > 0.0 else 1.0
			kk.append(k0 * tip * (1.0 - smoothstep(low - fade, low, pts[i].y)))
			lo = lo.min(uv[i])
			hi = hi.max(uv[i])
		for i in range(pts.size() - 1):
			segs.append(Vector4(uv[i].x, uv[i].y, uv[i + 1].x, uv[i + 1].y))
			ks.append(Vector4(kk[i], kk[i + 1], 1.0 if branch == 0.0 else float(bo.branch_width), branch))
	var w_half := float(bo.width_m) * 0.5 / 1000.0 / dist
	var glow := float(bo.glow_m) / 1000.0 / dist
	var pad := glow * 7.0 + 0.003
	var n := segs.size()
	segs.resize(64)
	ks.resize(64)
	m.set_shader_parameter("bolt_c", c)
	m.set_shader_parameter("bolt_r", r)
	m.set_shader_parameter("bolt_u", u)
	m.set_shader_parameter("bolt_seg", segs)
	m.set_shader_parameter("bolt_k", ks)
	m.set_shader_parameter("bolt_n", n)
	m.set_shader_parameter("bolt_box", Vector4(lo.x - pad, lo.y - pad, hi.x + pad, hi.y + pad))
	m.set_shader_parameter("bolt_w", w_half)
	m.set_shader_parameter("bolt_glow", glow)
	m.set_shader_parameter("bolt_dist", dist)
	return c


## Ломаная от a до b: depth раз каждый отрезок делится пополам, середина сдвигается поперёк на долю ~rough
## его длины — изломы на всех масштабах, как у канала молнии.
static func _bolt_path(a: Vector2, b: Vector2, depth: int, rough: float) -> PackedVector2Array:
	var pts := PackedVector2Array([a, b])
	for level in range(depth):
		var out := PackedVector2Array()
		for i in range(pts.size() - 1):
			var p := pts[i]
			var q := pts[i + 1]
			out.append(p)
			out.append((p + q) * 0.5 + (q - p).orthogonal().normalized() * clampf(randfn(0.0, rough), -2.0 * rough, 2.0 * rough) * p.distance_to(q))
		out.append(pts[pts.size() - 1])
		pts = out
	return pts


## Насколько низ туч в точке карты (qx, qz, км) ниже или выше ровного (рваный низ шейдера), км.
static func _rag(m: ShaderMaterial, qx: float, qz: float) -> float:
	if not _noise_ready():
		return 0.0
	var tile := float(Balance.SKY_CALC.clouds.detail_tile) * 2.5
	return (_sample3(_detail_imgs, Vector3(qx, 0.0, qz) / tile) - 0.5) * float(m.get_shader_parameter("base_rag"))


## Направление по карте на азимут az, ° (от севера к востоку): север — −Z, восток — +X.
static func _dir_to(az: float) -> Vector2:
	var a := deg_to_rad(az)
	return Vector2(sin(a), -cos(a))


## Сколько света светила с направления to (солнце или Луна) проходит сквозь облака к точке pos (м, мир):
## 1 — ясно. Тот же слой и шумы, что рисует шейдер (без мелких деталей — свет меняется плавно); не ниже
## sun_floor — облако светится и само. В туман и дождь — всегда 1: их профиль света солнце уже приглушил.
static func sun_through(m: ShaderMaterial, pos: Vector3, to: Vector3) -> float:
	# до первого update параметров ещё нет (null)
	if m == null or not bool(m.get_meta("cloud_shadow", false)) or to.y <= 0.01 or not _noise_ready():
		return 1.0
	var cl: Dictionary = Balance.SKY_CALC.clouds
	var base: float = m.get_shader_parameter("cloud_base")
	var top: float = m.get_shader_parameter("cloud_top")
	var cover: float = m.get_shader_parameter("cloud_coverage")
	var off: Vector2 = m.get_shader_parameter("cloud_offset")
	var t0 := base / to.y
	var t1 := minf(top / to.y, float(cl.far))
	if t0 >= t1:
		return 1.0
	var n := 8
	var dt := (t1 - t0) / float(n)
	var tau := 0.0
	for k in range(n):
		var t := t0 + dt * (float(k) + 0.5)
		var q := Vector3(pos.x / 1000.0 + off.x + to.x * t, to.y * t, pos.z / 1000.0 + off.y + to.z * t)
		tau += _density(q, base, top, cover) * dt
	return maxf(exp(-tau * float(cl.sigma) * float(cl.sun_tau)), float(cl.sun_floor))


## Плотность как в шейдере (cloud_density без деталей), по картинкам тех же шумов.
static func _density(q: Vector3, base: float, top: float, cover: float) -> float:
	var hf := (q.y - base) / (top - base)
	if hf <= 0.0 or hf >= 1.0:
		return 0.0
	var cl: Dictionary = Balance.SKY_CALC.clouds
	var t := 1.0 - cover
	var wc := smoothstep(t - 0.08, t + 0.18, _sample2(_cover_img, Vector2(q.x, q.z) / float(cl.cover_tile)))
	if wc <= 0.0:
		return 0.0
	var top_f := lerpf(0.45, 1.0, wc)
	var prof := smoothstep(0.0, 0.12, hf) * (1.0 - smoothstep(top_f - 0.35, top_f, hf))
	var k := wc * prof
	var sh := lerpf(_sample3(_shape_imgs, q / float(cl.shape_tile)), _sample3(_detail_imgs, q / (float(cl.shape_tile) * 0.5)), 0.35)
	return clampf((sh - (1.0 - k)) / maxf(k, 0.05), 0.0, 1.0)


## Шумы облаков — один раз на запуск: движок считает их сам (в своём потоке), файлов нет.
static func _make_noise() -> void:
	if _cover != null:
		return
	var cn := FastNoiseLite.new()
	cn.noise_type = FastNoiseLite.TYPE_PERLIN
	cn.seed = 1741
	cn.frequency = 1.0 / 64.0
	cn.fractal_type = FastNoiseLite.FRACTAL_FBM
	cn.fractal_octaves = 5
	_cover = NoiseTexture2D.new()
	_cover.width = 256
	_cover.height = 256
	_cover.seamless = true
	_cover.noise = cn
	var sn := FastNoiseLite.new()
	sn.noise_type = FastNoiseLite.TYPE_PERLIN
	sn.seed = 911
	sn.frequency = 1.0 / 16.0
	sn.fractal_type = FastNoiseLite.FRACTAL_FBM
	sn.fractal_octaves = 4
	_shape = NoiseTexture3D.new()
	_shape.width = 64
	_shape.height = 64
	_shape.depth = 64
	_shape.seamless = true
	_shape.noise = sn
	# детали — ячейки (Ворли): светлые в середине клубка, края выедаются
	var dn := FastNoiseLite.new()
	dn.noise_type = FastNoiseLite.TYPE_CELLULAR
	dn.seed = 377
	dn.frequency = 1.0 / 8.0
	dn.cellular_return_type = FastNoiseLite.RETURN_DISTANCE
	dn.fractal_type = FastNoiseLite.FRACTAL_FBM
	dn.fractal_octaves = 3
	_detail = NoiseTexture3D.new()
	_detail.width = 32
	_detail.height = 32
	_detail.depth = 32
	_detail.seamless = true
	_detail.invert = true
	_detail.noise = dn


## Картинки шумов для расчёта на процессоре — когда движок их досчитал.
static func _noise_ready() -> bool:
	if _cover == null:
		return false
	if _cover_img == null:
		var img: Image = _cover.get_image()
		if img == null or img.is_empty():
			return false
		_cover_img = img
	if _shape_imgs.is_empty():
		var layers: Array[Image] = _shape.get_data()
		if layers.size() != _shape.depth:
			return false
		_shape_imgs = layers
	if _detail_imgs.is_empty():
		var dl: Array[Image] = _detail.get_data()
		if dl.size() != _detail.depth:
			return false
		_detail_imgs = dl
	return true


## Как текстура с повтором и линейной выборкой: uv — доли плитки.
static func _sample2(img: Image, uv: Vector2) -> float:
	var w := img.get_width()
	var h := img.get_height()
	var fx := fposmod(uv.x, 1.0) * float(w) - 0.5
	var fy := fposmod(uv.y, 1.0) * float(h) - 0.5
	var x0 := int(floor(fx))
	var y0 := int(floor(fy))
	var ax := fx - float(x0)
	var ay := fy - float(y0)
	var a := lerpf(img.get_pixel(posmod(x0, w), posmod(y0, h)).r, img.get_pixel(posmod(x0 + 1, w), posmod(y0, h)).r, ax)
	var b := lerpf(img.get_pixel(posmod(x0, w), posmod(y0 + 1, h)).r, img.get_pixel(posmod(x0 + 1, w), posmod(y0 + 1, h)).r, ax)
	return lerpf(a, b, ay)


static func _sample3(layers: Array[Image], uvw: Vector3) -> float:
	var dd := layers.size()
	var fz := fposmod(uvw.z, 1.0) * float(dd) - 0.5
	var z0 := int(floor(fz))
	var uv := Vector2(uvw.x, uvw.y)
	return lerpf(_sample2(layers[posmod(z0, dd)], uv), _sample2(layers[posmod(z0 + 1, dd)], uv), fz - float(z0))


## Видимое небо темнее карты отражений во столько раз: та подогнана к облачным панорамам, у которых на
## закате освещённость как днём, — чистое небо при той же яркости белёсое. Усиление относительно
## view_ref (° высоты солнца) смягчается в степени view_dim, не ниже view_min. Солнце за горизонтом —
## как на горизонте: сумерки ярче не подгонкой, а привыканием глаза (twilight_adapt), их не гасим.
static func view_k(rows: Dictionary, cal: Dictionary, elev: float) -> float:
	elev = maxf(elev, 0.0)
	var sc: Dictionary = Balance.SKY_CALC
	var elevs: Array = cal.elev
	var g_ref: float = float(rows.gain[clampi(int(sc.view_ref) - int(elevs[0]), 0, elevs.size() - 1)])
	var x := clampf(elev - float(elevs[0]), 0.0, float(elevs.size() - 1))
	var i := mini(int(floor(x)), elevs.size() - 2)
	var g := exp(lerpf(log(float(rows.gain[i])), log(float(rows.gain[i + 1])), x - float(i)))
	return clampf(pow(g_ref / g, float(sc.view_dim)), float(sc.view_min), 1.0)


static func _load() -> Dictionary:
	if not _data.is_empty() or not FileAccess.file_exists(DATA):
		return _data
	var v: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA))
	if not v is Dictionary:
		return _data
	var d: Dictionary = v
	_t_lut = _lut(d.get("transmittance", {}))
	_ms_lut = _lut(d.get("multiscatter", {}))
	if _t_lut == null or _ms_lut == null or not d.has("calib") or not d.has("atmosphere"):
		return _data
	_data = d
	return _data


## Таблица из записи {w, h, rgbah — base64 полуплавающих RGBA}.
static func _lut(t: Dictionary) -> ImageTexture:
	if t.is_empty():
		return null
	var raw := Marshalls.base64_to_raw(String(t.get("rgbah", "")))
	var w := int(t.get("w", 0))
	var h := int(t.get("h", 0))
	if w <= 0 or h <= 0 or raw.size() != w * h * 8:
		return null
	return ImageTexture.create_from_image(Image.create_from_data(w, h, false, Image.FORMAT_RGBAH, raw))


static func _v3(a: Variant) -> Vector3:
	var arr: Array = a
	return Vector3(float(arr[0]), float(arr[1]), float(arr[2]))
