extends SceneTree
## Числа света Road to Vostok по времени суток → data/lighting/time_of_day.json (перенос их света на все карты RING,
## решение владельца 2026-11-05). Берутся только числа: градиенты и кривые их мира Resources/World.tscn (цвет неба,
## солнца, луны, рассеянного света, рассеяния в дымке; сила солнца, отражения неба, плотность дымки), высота их солнца
## по часам (их «планета»: поворот (t/2400·360°, 75°, −45°)), настройки неба и окружения. Картинок и кода не берём.
##   godot --headless --path tools/research/rtv --script res://light_tables.gd   (RTV_PCK — путь к игре,
##   RTV_LIGHT_OUT — куда писать JSON, RTV_PREVIEW — папка вне проекта для просмотра их облаков, по желанию)

const STEP: float = 25.0
const GRADIENTS: Array[String] = ["skyColor", "sunColor", "sunScatter", "ambientColor", "overcastColor", "moonColor"]
const CURVES: Array[String] = ["sunEnergy", "skyReflection", "fogDensity"]
const SKY_PARAMS: Array[String] = ["sunColor", "moonColor", "horizonBlur", "sunSize", "sunBlur", "sunGlowSize", "sunGlowIntensity", "sunReflection",
	"moonSize", "moonGlowSize", "moonGlowIntensity", "moonReflection", "starsReflection"]
const ENV_KEYS: Array[String] = ["tonemap_mode", "tonemap_exposure", "tonemap_agx_white", "tonemap_agx_contrast",
	"ambient_light_energy", "ambient_light_sky_contribution", "volumetric_fog_emission_energy", "volumetric_fog_gi_inject",
	"volumetric_fog_anisotropy", "volumetric_fog_length", "volumetric_fog_detail_spread", "volumetric_fog_ambient_inject",
	"volumetric_fog_sky_affect", "glow_enabled", "adjustment_contrast", "adjustment_saturation"]


func _init() -> void:
	ProjectSettings.load_resource_pack(OS.get_environment("RTV_PCK"), false)
	for n: String in ["Rain", "Snow", "Wind", "Indoor", "Viewmodel"]:
		RenderingServer.global_shader_parameter_add(n, RenderingServer.GLOBAL_VAR_TYPE_FLOAT, 0.0)
	for n: String in ["Winter", "Occlusion", "Compatibility"]:
		RenderingServer.global_shader_parameter_add(n, RenderingServer.GLOBAL_VAR_TYPE_BOOL, false)
	RenderingServer.global_shader_parameter_add("Player", RenderingServer.GLOBAL_VAR_TYPE_VEC3, Vector3.ZERO)
	for n: String in ["Noise", "Specular", "Overlay", "SnowNormal", "Ripples"]:
		RenderingServer.global_shader_parameter_add(n, RenderingServer.GLOBAL_VAR_TYPE_SAMPLER2D, null)
	var state: SceneState = (load("res://Resources/World.tscn") as PackedScene).get_state()
	var props: Dictionary = {}
	for j: int in range(state.get_node_property_count(0)):
		props[String(state.get_node_property_name(0, j))] = state.get_node_property_value(0, j)
	var out: Dictionary = {
		"_comment": "Свет по времени суток по схеме Road to Vostok (решение владельца 2026-11-05: их свет на все рейдовые карты). "
			+ "Числа сняты из их Resources/World.tscn и Environment/Main.tres скриптом tools/research/rtv/light_tables.gd; "
			+ "t — их часы 0…2400 (линейно, 2400 = сутки), sun_elev — высота их солнца, °. Ведёт TodLight (src/world/tod_light.gd).",
		"step": STEP,
	}
	var t_list: Array = []
	var elev: Array = []
	var t: float = 0.0
	while t <= 2400.0 + 0.01:
		t_list.append(t)
		var b := Basis.from_euler(Vector3(deg_to_rad(t / 2400.0 * 360.0), deg_to_rad(75.0), deg_to_rad(-45.0)))
		elev.append(snappedf(rad_to_deg(asin(clampf((b * Vector3(0.0, -1.0, 0.0)).y, -1.0, 1.0))), 0.01))
		t += STEP
	out["t"] = t_list
	out["sun_elev"] = elev
	for key: String in GRADIENTS:
		var g: GradientTexture1D = props.get(key) as GradientTexture1D
		var rows: Array = []
		for tt: float in t_list:
			var c: Color = g.gradient.sample(tt / 2400.0)
			rows.append([snappedf(c.r, 0.0001), snappedf(c.g, 0.0001), snappedf(c.b, 0.0001)])
		out[key] = rows
	for key: String in CURVES:
		var cv: CurveTexture = props.get(key) as CurveTexture
		var vals: Array = []
		for tt: float in t_list:
			vals.append(snappedf(cv.curve.sample(tt / 2400.0), 0.0001))
		out[key] = vals
	var sky: ShaderMaterial = props.get("skyMaterial") as ShaderMaterial
	var sky_out: Dictionary = {}
	for key: String in SKY_PARAMS:
		var v: Variant = sky.get_shader_parameter(key)
		if v is Color or v is Vector3:
			var c3: Color = v if v is Color else Color((v as Vector3).x, (v as Vector3).y, (v as Vector3).z)
			v = [snappedf(c3.r, 0.0001), snappedf(c3.g, 0.0001), snappedf(c3.b, 0.0001)]
		sky_out[key] = v
	var preview: String = OS.get_environment("RTV_PREVIEW")
	for key: String in ["neutralTexture", "overcastTexture"]:
		var tex: Texture2D = sky.get_shader_parameter(key) as Texture2D
		if tex == null:
			continue
		var img: Image = tex.get_image()
		if img.is_compressed():
			img.decompress()
		var small: Image = img.duplicate() as Image
		small.resize(64, 32, Image.INTERPOLATE_BILINEAR)
		var acc := Color(0, 0, 0, 0)
		var lo: float = 1.0
		var hi: float = 0.0
		for y: int in range(8, 16):
			for x: int in range(64):
				var c2: Color = small.get_pixel(x, y)
				acc += c2
				lo = minf(lo, c2.get_luminance())
				hi = maxf(hi, c2.get_luminance())
		acc /= 64.0 * 8.0
		sky_out[key + "_upper_mean"] = [snappedf(acc.r, 0.001), snappedf(acc.g, 0.001), snappedf(acc.b, 0.001)]
		sky_out[key + "_upper_range"] = [snappedf(lo, 0.001), snappedf(hi, 0.001)]
		if preview != "":
			var p: Image = img.duplicate() as Image
			p.resize(1024, 512, Image.INTERPOLATE_BILINEAR)
			p.save_png(preview.path_join(key + ".png"))
	out["sky"] = sky_out
	var env: Environment = load("res://Environment/Main.tres") as Environment
	var env_out: Dictionary = {}
	for key: String in ENV_KEYS:
		env_out[key] = env.get(key)
	out["environment"] = env_out
	var path: String = OS.get_environment("RTV_LIGHT_OUT")
	var f := FileAccess.open(path, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, " ", false) + "\n")
	f.close()
	print("light_tables: ", path, " — ", t_list.size(), " строк")
	quit(0)
