class_name AtmosphereSky
extends RefCounted
## Расчётное небо — режим «расчёт» смены суток (DayCycle, Settings.sky_mode): материал
## atmosphere_sky.gdshader с таблицами рассеяния из data/sky_atmosphere.json (tools/gen_sky_atmosphere.py)
## и подгонка по высоте солнца и погоде из того же файла — яркость атмосферы, пелена туч, низ, оттенок
## отражений (Balance.SKY_CALC). Нет файла — режима нет, небо из панорам.

const DATA := "res://data/sky_atmosphere.json"
const SHADER := "res://src/world/atmosphere_sky.gdshader"

static var _data: Dictionary = {}
static var _t_lut: ImageTexture
static var _ms_lut: ImageTexture


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
	return m


## Солнце (направление на него, высота, °) и погода: дымка, тучи, яркость и оттенок по подгонке.
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
	m.set_shader_parameter("sun_dir", to_sun)
	m.set_shader_parameter("gain", gain)
	m.set_shader_parameter("mie_k", float(ws.mie))
	m.set_shader_parameter("overcast", float(ws.overcast))
	m.set_shader_parameter("oc_zenith", _v3(rows.oc[i]).lerp(_v3(rows.oc[i + 1]), f))
	m.set_shader_parameter("amb_tint", amb_eff)
	m.set_shader_parameter("view_k", view_k(rows, cal, elev))
	m.set_shader_parameter("ground_col", ground)


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
