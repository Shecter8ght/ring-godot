class_name AtmosphereSky
extends RefCounted
## Расчётное небо — режим «расчёт» смены суток (DayCycle, Settings.sky_mode): материал
## atmosphere_sky.gdshader с таблицами рассеяния из data/sky_atmosphere.json (tools/gen_sky_atmosphere.py)
## и подгонка по высоте солнца и погоде из того же файла — яркость атмосферы, низ, оттенок отражений
## (Balance.SKY_CALC). Облака — объёмный слой в том же шейдере: шумы генерирует движок (FastNoiseLite,
## файлов нет), покрытие и высота — от погоды, ветер — от игровых часов (у всех игроков облака одни).
## Солнце за облаком тускнеет (sun_through) — по тем же шумам, что рисует шейдер. Нет таблиц — режима
## нет, небо из панорам.

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
	return m


## Солнце (направление на него, высота, °) и погода: дымка, облака, яркость и оттенок по подгонке.
static func update(m: ShaderMaterial, to_sun: Vector3, elev: float, weather: String) -> void:
	var d := _load()
	if d.is_empty() or m == null:
		return
	var sc: Dictionary = Balance.SKY_CALC
	var ws: Dictionary = (sc.weather as Dictionary).get(weather, sc.weather.clear)
	var cal: Dictionary = d.calib
	var rows: Dictionary = (cal.weather as Dictionary).get(weather, cal.weather.clear)
	var elevs: Array = cal.elev
	var x := clampf(elev - float(elevs[0]), 0.0, float(elevs.size() - 1))
	var i := mini(int(floor(x)), elevs.size() - 2)
	var f := x - float(i)
	# усиление в сумерках меняется на порядки — между строками по логарифму
	var gain := exp(lerpf(log(float(rows.gain[i])), log(float(rows.gain[i + 1])), f))
	var amb := _v3(rows.amb[i]).lerp(_v3(rows.amb[i + 1]), f)
	var amb_eff := Vector3.ONE.lerp(amb, float(sc.amb_match))
	# низ в таблице — до поправки оттенка (в карте отражений он умножится на неё)
	var ground := _v3(rows.ground[i]).lerp(_v3(rows.ground[i + 1]), f) * amb / amb_eff
	var oc := _v3(rows.oc[i]).lerp(_v3(rows.oc[i + 1]), f)
	var clouds := float(ws.get("cover", 0.0)) > 0.0
	m.set_shader_parameter("sun_dir", to_sun)
	m.set_shader_parameter("gain", gain)
	m.set_shader_parameter("mie_k", float(ws.mie))
	# пасмурность из подгонки рисуют облака; ровная пелена — только если облаков нет
	m.set_shader_parameter("veil", 0.0 if clouds else float(ws.overcast))
	m.set_shader_parameter("overcast", 0.0 if clouds else float(ws.overcast))
	m.set_shader_parameter("oc_zenith", oc)
	m.set_shader_parameter("amb_tint", amb_eff)
	m.set_shader_parameter("view_k", view_k(rows, cal, elev))
	m.set_shader_parameter("ground_col", ground)
	m.set_shader_parameter("clouds_on", clouds)
	# солнце за облаком гаснет только там, где свет погоды его ещё не приглушил под пасмурность
	m.set_meta("cloud_shadow", clouds and float(ws.overcast) <= 0.0)
	if clouds:
		m.set_shader_parameter("cloud_coverage", float(ws.cover))
		m.set_shader_parameter("cloud_base", float(ws.base))
		m.set_shader_parameter("cloud_top", float(ws.top))
		m.set_shader_parameter("amb_bottom", float(ws.amb_bottom))
		# свет неба на облака — средняя яркость неба, какой её даёт подгонка (до поправки оттенка):
		# под сплошными тучами земля освещена, как раньше под пасмурной панорамой
		m.set_shader_parameter("cloud_amb", oc * (7.0 / 9.0) / amb)


## Ветер: облака плывут по игровым часам hour — у всех игроков одинаково (часы ведёт хост).
static func clouds_tick(m: ShaderMaterial, hour: float) -> void:
	if m == null:
		return
	var cl: Dictionary = Balance.SKY_CALC.clouds
	var to := deg_to_rad(float(cl.wind_from) + 180.0)
	var km := float(cl.wind_ms) * hour * float(Balance.DAY_CYCLE.hour_sec) / 1000.0
	# карта на север — −Z, восток — +X; шум сдвигается против движения облаков
	m.set_shader_parameter("cloud_offset", -Vector2(sin(to), -cos(to)) * fposmod(km, float(cl.cover_tile) * 8.0))


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
