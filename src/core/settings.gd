extends Node
## Настройки игрока: графика, мышь, громкость — user://settings.cfg (разделы graphics, mouse,
## audio; вид от первого лица и лобби пишут туда же свои разделы). Меняются в меню Esc →
## «Настройки», применяются сразу. Тесты и инструменты (res://tools/…) — всегда с умолчаниями и
## ничего не сохраняют. Autoload `Settings`.
##
## Графика: «высоко» — как задумано в сценах (SDFGI, SSIL, SSAO, объёмный туман, тени 8К, TAA);
## «средне» — без SDFGI и SSIL, тени 4К; «низко» — ещё без SSAO и тумана, тени 2К, рендер 3D в
## 77 % разрешения с FSR. Исходные значения окружения запоминаются на нём (meta), чтобы вернуть.
## Громкость — по шинам: выстрелы, шаги, эффекты (попадания, двери, голоса), окружение.

signal changed

const PATH := "user://settings.cfg"
const QUALITY := ["low", "medium", "high"]
const QUALITY_NAMES := {"low": "Низко", "medium": "Средне", "high": "Высоко"}
## Шина → подпись в меню. Master — общая.
const BUSES := {"Master": "Общая", "Shots": "Выстрелы", "Steps": "Шаги", "World": "Эффекты", "Ambient": "Окружение"}
## Множители чувствительности мыши: от очень медленной до очень быстрой (ползунок — по экспоненте,
## точное число — в поле рядом).
const SENS_RANGE := [0.05, 10.0]

var quality: String = "high"
## Множитель чувствительности мыши: от первого лица (взгляд) и в изометрии (поворот камеры СКМ).
var sens_fps: float = 1.0
var sens_iso: float = 1.0
## Отдельно — пока целишься (ПКМ, оптика: поверх её поправки на кратность).
var sens_ads: float = 1.0
## Мышь вверх — взгляд вниз (как у лётчиков).
var invert_y: bool = false
## Громкость по шине, 0–1.
var volume: Dictionary = {"Master": 1.0, "Shots": 1.0, "Steps": 1.0, "World": 1.0, "Ambient": 1.0}
## Гарнитура на ушах своего игрока (data/armor.json → headsets[…].headset): поправки шин, дБ, и
## насколько дальше слышно (hear_k). Не сохраняется — это снаряжение, а не настройка.
var headset: Dictionary = {}
const HEADSET_DB := {"Shots": "shots_db", "Steps": "steps_db", "World": "world_db"}

## Чит «бессмертие» (меню Esc → Настройки, консоль: god) — раздел cheats; в коопе решает хост.
var god: bool = false

var _tool_run: bool = false
var _defaults: Dictionary = {}


func _ready() -> void:
	for a in OS.get_cmdline_args():
		if String(a).begins_with("res://tools/"):
			_tool_run = true
	_make_buses()
	var vp := get_viewport()
	_defaults = {"taa": vp.use_taa, "msaa": vp.msaa_3d, "ssaa": vp.screen_space_aa,
		"scale_mode": vp.scaling_3d_mode, "scale": vp.scaling_3d_scale,
		"dir_shadow": int(ProjectSettings.get_setting("rendering/lights_and_shadows/directional_shadow/size", 4096)),
		"pos_shadow": vp.positional_shadow_atlas_size}
	if not _tool_run:
		_load()
	_apply_audio()
	get_tree().node_added.connect(_on_node_added)
	apply_graphics.call_deferred()


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	var q := String(cfg.get_value("graphics", "quality", quality))
	quality = q if q in QUALITY else "high"
	sens_fps = clampf(float(cfg.get_value("mouse", "fps", sens_fps)), SENS_RANGE[0], SENS_RANGE[1])
	sens_iso = clampf(float(cfg.get_value("mouse", "iso", sens_iso)), SENS_RANGE[0], SENS_RANGE[1])
	sens_ads = clampf(float(cfg.get_value("mouse", "ads", sens_ads)), SENS_RANGE[0], SENS_RANGE[1])
	invert_y = bool(cfg.get_value("mouse", "invert_y", invert_y))
	for b in BUSES:
		volume[b] = clampf(float(cfg.get_value("audio", String(b), 1.0)), 0.0, 1.0)
	god = bool(cfg.get_value("cheats", "god", false))


func save() -> void:
	if _tool_run:
		return
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	cfg.set_value("graphics", "quality", quality)
	cfg.set_value("mouse", "fps", sens_fps)
	cfg.set_value("mouse", "iso", sens_iso)
	cfg.set_value("mouse", "ads", sens_ads)
	cfg.set_value("mouse", "invert_y", invert_y)
	for b in BUSES:
		cfg.set_value("audio", String(b), float(volume[b]))
	cfg.set_value("cheats", "god", god)
	cfg.save(PATH)


func set_quality(q: String) -> void:
	if not q in QUALITY:
		return
	quality = q
	apply_graphics()
	save()
	changed.emit()


func set_sens(fps: float, iso: float) -> void:
	sens_fps = clampf(fps, SENS_RANGE[0], SENS_RANGE[1])
	sens_iso = clampf(iso, SENS_RANGE[0], SENS_RANGE[1])
	save()
	changed.emit()


func set_sens_ads(v: float) -> void:
	sens_ads = clampf(v, SENS_RANGE[0], SENS_RANGE[1])
	save()
	changed.emit()


func set_invert_y(on: bool) -> void:
	invert_y = on
	save()
	changed.emit()


## Бессмертие вкл/выкл: сохраняется и сразу действует на своего игрока (и в следующих рейдах).
func set_god(on: bool) -> void:
	god = on
	save()
	for n in get_tree().get_nodes_in_group("all_players"):
		var pl := n as Player
		if pl and pl.is_local():
			pl.set_god(on)
	changed.emit()


func set_volume(bus: String, v: float) -> void:
	if not volume.has(bus):
		return
	volume[bus] = clampf(v, 0.0, 1.0)
	_apply_audio()
	save()
	changed.emit()


# ---------------------------------------------------------------- звук

## Шины звука (все — в Master): создаются при старте, если их нет в раскладке проекта.
func _make_buses() -> void:
	for b in BUSES:
		if AudioServer.get_bus_index(String(b)) >= 0:
			continue
		AudioServer.add_bus()
		var i := AudioServer.bus_count - 1
		AudioServer.set_bus_name(i, String(b))
		AudioServer.set_bus_send(i, "Master")


func _apply_audio() -> void:
	for b in BUSES:
		var i := AudioServer.get_bus_index(String(b))
		if i < 0:
			continue
		var v := float(volume[b])
		AudioServer.set_bus_mute(i, v <= 0.001)
		AudioServer.set_bus_volume_db(i, linear_to_db(maxf(v, 0.001)) + float(headset.get(String(HEADSET_DB.get(b, "")), 0.0)))


## Надел / снял гарнитуру: выстрелы глушатся, шаги и мелочь — громче (активная).
func set_headset(h: Dictionary) -> void:
	if h == headset:
		return
	headset = h
	_apply_audio()


## Шина для вида звука (Audio.play).
static func bus_for(kind: String) -> StringName:
	if kind.begins_with("shot_") or kind == "explosion":
		return &"Shots"
	if kind.begins_with("step"):
		return &"Steps"
	return &"World"


# ---------------------------------------------------------------- графика

func _on_node_added(n: Node) -> void:
	if n is WorldEnvironment:
		_apply_env.call_deferred(n as WorldEnvironment)
	elif n is OmniLight3D or n is SpotLight3D:
		soften(n as Light3D)


## Мягкий свет от любого источника: спад по расстоянию плавнее (яркость пересчитана так, чтобы
## на обычном расстоянии свет был тот же, а горячее пятно под лампой — мягче), край конуса
## размыт, блик мягче, больше отражённого (SDFGI), край тени чуть размыт. Сквозь стены не
## светит: свечение в воздухе (объёмный туман) — только у источников с тенью (у бестеневого оно
## шло бы сквозь стену), смещения тени малые (иначе свет подтекает по стыку стены с полом и
## под тонкие перемычки), без PCSS (он тоже подтекает у стыков). Один раз на источник; свет,
## которому нужна чёткость, — meta "crisp".
static func soften(l: Light3D) -> void:
	if l.has_meta("crisp") or l.has_meta("soft"):
		return
	l.set_meta("soft", true)
	l.light_specular = minf(l.light_specular, 0.45)
	l.light_indirect_energy = maxf(l.light_indirect_energy, 1.3)
	if l.shadow_enabled:
		l.light_volumetric_fog_energy = maxf(l.light_volumetric_fog_energy, 1.4)
		l.shadow_blur = maxf(l.shadow_blur, 1.2)
		l.shadow_bias = minf(l.shadow_bias, 0.04)
		l.shadow_normal_bias = minf(l.shadow_normal_bias, 0.5)
	else:
		l.light_volumetric_fog_energy = minf(l.light_volumetric_fog_energy, 0.35)
	var range_m := 0.0
	var decay := 1.0
	if l is OmniLight3D:
		range_m = (l as OmniLight3D).omni_range
		decay = (l as OmniLight3D).omni_attenuation
	elif l is SpotLight3D:
		range_m = (l as SpotLight3D).spot_range
		decay = (l as SpotLight3D).spot_attenuation
		(l as SpotLight3D).spot_angle_attenuation = minf((l as SpotLight3D).spot_angle_attenuation, 0.8)
	var soft := minf(decay, SOFT_DECAY)
	if soft < decay:
		# на «рабочем» расстоянии яркость как была
		var ref := clampf(range_m * 0.35, 1.0, 6.0)
		l.light_energy *= pow(ref, soft - decay)
		if l is OmniLight3D:
			(l as OmniLight3D).omni_attenuation = soft
		else:
			(l as SpotLight3D).spot_attenuation = soft


const SOFT_DECAY := 0.8


func apply_graphics() -> void:
	var vp := get_viewport()
	match quality:
		"low":
			vp.use_taa = false
			vp.msaa_3d = Viewport.MSAA_DISABLED
			vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR
			vp.scaling_3d_scale = 0.77
			RenderingServer.directional_shadow_atlas_set_size(2048, true)
			vp.positional_shadow_atlas_size = 1024
		"medium":
			vp.use_taa = bool(_defaults.taa)
			vp.msaa_3d = Viewport.MSAA_DISABLED
			vp.screen_space_aa = _defaults.ssaa
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
			vp.scaling_3d_scale = 1.0
			RenderingServer.directional_shadow_atlas_set_size(4096, true)
			vp.positional_shadow_atlas_size = 2048
		_:
			vp.use_taa = bool(_defaults.taa)
			vp.msaa_3d = _defaults.msaa
			vp.screen_space_aa = _defaults.ssaa
			vp.scaling_3d_mode = _defaults.scale_mode
			vp.scaling_3d_scale = float(_defaults.scale)
			RenderingServer.directional_shadow_atlas_set_size(int(_defaults.dir_shadow), true)
			vp.positional_shadow_atlas_size = int(_defaults.pos_shadow)
	for we in get_tree().root.find_children("*", "WorldEnvironment", true, false):
		_apply_env(we as WorldEnvironment)


## Окружение сцены по качеству; исходное (как в сцене) — в meta, «высоко» возвращает его.
func _apply_env(we: WorldEnvironment) -> void:
	if not is_instance_valid(we) or we.environment == null:
		return
	var e := we.environment
	if not e.has_meta("orig"):
		e.set_meta("orig", {"sdfgi": e.sdfgi_enabled, "ssil": e.ssil_enabled, "ssao": e.ssao_enabled,
			"fog": e.volumetric_fog_enabled, "ssr": e.ssr_enabled})
	var o: Dictionary = e.get_meta("orig")
	var hi := quality == "high"
	var mid := quality == "medium"
	e.sdfgi_enabled = bool(o.sdfgi) and hi
	e.ssil_enabled = bool(o.ssil) and hi
	# отражения в экранном пространстве — мокрый асфальт и лужи (средне и высоко)
	e.ssr_enabled = hi or mid
	if e.ssr_enabled:
		# длинный луч и слабое затухание — отражение в луже во всю высоту здания (подобрано ssr_probe)
		e.ssr_max_steps = 256 if hi else 128
		e.ssr_fade_in = 0.15
		e.ssr_fade_out = 0.3
		e.ssr_depth_tolerance = 0.5
	e.ssao_enabled = bool(o.ssao) and (hi or mid)
	e.volumetric_fog_enabled = bool(o.fog) and (hi or mid)
	# свечение вокруг ярких мест — широкое и мягкое (дальние уровни), свет «обволакивает»
	# свет заливает помещение: отражённый (SDFGI) — с повторными отскоками
	if hi and e.sdfgi_enabled:
		e.sdfgi_bounce_feedback = maxf(e.sdfgi_bounce_feedback, 0.8)
	if e.glow_enabled and not e.has_meta("soft_glow"):
		e.set_meta("soft_glow", true)
		# дальние уровни слабые: широкий ореол переползал через края стен у ярких мест
		for lv in [[3, 1.0], [4, 0.75], [5, 0.55], [6, 0.18]]:
			e.set_glow_level(int(lv[0]) - 1, maxf(e.get_glow_level(int(lv[0]) - 1), float(lv[1])))
