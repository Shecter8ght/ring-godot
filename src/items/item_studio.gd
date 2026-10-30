class_name ItemStudio
extends RefCounted
## Студия для снимков предметов (печёные иконки tools/icon_bake и снимки ItemThumbs): прозрачный фон, но металлу
## есть что отражать — студийное «небо» светлым сверху и тёмным снизу (как софтбокс над столом), рисующий свет
## спереди сверху, контровой сзади отделяет силуэт, слабый заполняющий. Без неба воронёный металл и чёрный полимер
## отражали пустоту и выходили плоскими и тусклыми (владелец 2026-10-30: «ВЕРАС и винторез очень блеклые»).


## Свет и окружение студии — в вьюпорт снимка (прозрачный фон, свой мир).
static func setup(vp: SubViewport) -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_CLEAR_COLOR
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.92, 0.93, 0.95)
	sky_mat.sky_horizon_color = Color(0.62, 0.64, 0.67)
	sky_mat.sky_curve = 0.12
	sky_mat.ground_horizon_color = Color(0.3, 0.31, 0.33)
	sky_mat.ground_bottom_color = Color(0.06, 0.06, 0.07)
	sky_mat.ground_curve = 0.06
	sky_mat.sun_angle_max = 0.0
	sky_mat.energy_multiplier = 1.6
	var sky := Sky.new()
	sky.sky_material = sky_mat
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.ambient_light_energy = 0.7
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 1.15
	env.environment = e
	vp.add_child(env)
	# рисующий: спереди сверху слева, тёплый белый
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-42, -32, 0)
	key.light_color = Color(1.0, 0.97, 0.92)
	key.light_energy = 3.0
	vp.add_child(key)
	# контровой: сзади сверху — светлая кромка по верху силуэта
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-50, 120, 0)
	rim.light_color = Color(0.85, 0.9, 1.0)
	rim.light_energy = 2.6
	vp.add_child(rim)
	# заполняющий: снизу спереди справа, слабый — тени не проваливаются в чёрное
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(12, 40, 0)
	fill.light_energy = 0.35
	vp.add_child(fill)
