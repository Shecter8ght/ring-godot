extends RefCounted
## Стенд света «Проспекта» (владелец 2026-10-26: «мне нравится освещение в EFT, но не могу объяснить чем»):
## от умолчаний Godot по одной черте освещения EFT и всё вместе. Черты — из разбора скриншотов Ground Zero
## (референсы/prospekt_ground_zero): перепад света, бирюзовый холод, дымка вдали, глубокие тени в углах, тёмные
## помещения, резкость. Снимает tools/prospekt_study.gd: PROSPEKT_LIGHT=all_variants (или имена через «,») -- shots.
## Числа подобраны замером кадров против скриншотов EFT. Владелец выбрал «всё вместе» — с 2026-10-26 это свет карты
## (tools/prospekt_light.py), и стенд снимает варианты уже поверх него; кадры от умолчаний Godot — light_stand_*.jpg.

const ORDER: Array[String] = ["default", "contrast", "teal", "haze", "ao", "gi", "sharp", "eft"]

const NAMES: Dictionary = {
	"default": "Свет карты",
	"contrast": "1 · Перепад: солнце сильнее, рассеянный слабее, небо ярче",
	"teal": "2 · Бирюзовый холод: небо и тени в холодную зелень, солнце тёплое",
	"haze": "3 · Дымка: дальнее светлеет и тонет в воздухе",
	"ao": "4 · Глубокие тени в углах и стыках",
	"gi": "5 · Тёмные помещения: рассеянный свет не проходит сквозь крыши",
	"sharp": "6 · Резкость поверх картинки",
	"eft": "Всё вместе",
}

## Из каких черт состоит вариант.
const PARTS: Dictionary = {
	"default": [],
	"contrast": ["contrast"],
	"teal": ["teal"],
	"haze": ["haze"],
	"ao": ["ao"],
	"gi": ["gi"],
	"sharp": ["sharp"],
	"eft": ["contrast", "teal", "haze", "ao", "gi", "sharp"],
}

const SHARPEN_SHADER: String = "res://src/world/screen_sharpen.gdshader"


## Сколько кадров ждать перед снимком: SDFGI набирает свет дольше.
static func settle_frames(variant: String) -> int:
	return 240 if "gi" in (PARTS.get(variant, []) as Array) else 60


## Применить вариант к копии окружения и к солнцу; резкость — слой поверх кадра (возвращается, чтобы убрать).
static func apply(variant: String, env: Environment, sun: DirectionalLight3D, host: Node) -> CanvasLayer:
	var parts: Array = PARTS.get(variant, []) as Array
	var sky: ProceduralSkyMaterial = env.sky.sky_material as ProceduralSkyMaterial if env.sky else null
	if "contrast" in parts:
		sun.light_energy = 2.0
		env.ambient_light_energy = 0.25
		env.background_energy_multiplier = 1.15
		env.tonemap_exposure = 0.8
	if "teal" in parts:
		sun.light_color = Color(1.0, 0.9, 0.76)
		if sky:
			sky.sky_top_color = Color(0.24, 0.4, 0.56)
			sky.sky_horizon_color = Color(0.6, 0.68, 0.74)
			sky.ground_horizon_color = Color(0.5, 0.56, 0.55)
			sky.ground_bottom_color = Color(0.16, 0.18, 0.16)
		env.adjustment_enabled = true
		env.adjustment_saturation = 0.9
		env.adjustment_color_correction = _teal_curve()
	if "haze" in parts:
		# по расстоянию: ближе 50 м чисто, дальше дымка набирается быстро и к 900 м — половина цвета воздуха
		env.fog_enabled = true
		env.fog_mode = Environment.FOG_MODE_DEPTH
		env.fog_depth_begin = 50.0
		env.fog_depth_end = 900.0
		env.fog_depth_curve = 0.6
		env.fog_density = 0.55
		env.fog_light_color = Color(0.7, 0.77, 0.82)
		env.fog_light_energy = 1.0
		env.fog_sun_scatter = 0.15
		env.fog_aerial_perspective = 0.5
		env.fog_sky_affect = 0.1
	if "ao" in parts:
		env.ssao_enabled = true
		env.ssao_radius = 2.5
		env.ssao_intensity = 4.0
		env.ssao_power = 2.0
		env.ssao_light_affect = 0.3
	if "gi" in parts:
		env.sdfgi_enabled = true
		env.sdfgi_use_occlusion = true
		env.sdfgi_read_sky_light = true
		env.sdfgi_cascades = 4
		env.sdfgi_min_cell_size = 0.25
		env.sdfgi_energy = 1.0
		# рассеянный от неба теперь считает SDFGI с затенением; общий — слабее, иначе он светит и под крышей
		env.ambient_light_energy = minf(env.ambient_light_energy, 0.3)
	if "sharp" in parts:
		var layer: CanvasLayer = CanvasLayer.new()
		layer.name = "LightStandSharpen"
		layer.layer = 50
		var rect: ColorRect = ColorRect.new()
		rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var mat: ShaderMaterial = ShaderMaterial.new()
		mat.shader = load(SHARPEN_SHADER) as Shader
		rect.material = mat
		layer.add_child(rect)
		host.add_child(layer)
		return layer
	return null


## Кривые по каналам (1D-таблица коррекции Godot): красный чуть ниже в середине, зелёный и синий выше —
## холодная бирюза в тенях и полутонах, света почти белые.
static func _teal_curve() -> GradientTexture1D:
	var g: Gradient = Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.25, 0.5, 0.75, 1.0])
	g.colors = PackedColorArray([Color(0.0, 0.01, 0.018), Color(0.225, 0.255, 0.265), Color(0.47, 0.505, 0.52),
		Color(0.735, 0.76, 0.77), Color(0.985, 1.0, 1.0)])
	var tex: GradientTexture1D = GradientTexture1D.new()
	tex.gradient = g
	tex.width = 256
	return tex
