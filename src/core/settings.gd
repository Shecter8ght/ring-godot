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
const SENS_RANGE := [0.3, 3.0]

var quality: String = "high"
## Множитель чувствительности мыши: от первого лица (взгляд) и в изометрии (поворот камеры СКМ).
var sens_fps: float = 1.0
var sens_iso: float = 1.0
## Громкость по шине, 0–1.
var volume: Dictionary = {"Master": 1.0, "Shots": 1.0, "Steps": 1.0, "World": 1.0, "Ambient": 1.0}

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
	for b in BUSES:
		volume[b] = clampf(float(cfg.get_value("audio", String(b), 1.0)), 0.0, 1.0)


func save() -> void:
	if _tool_run:
		return
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	cfg.set_value("graphics", "quality", quality)
	cfg.set_value("mouse", "fps", sens_fps)
	cfg.set_value("mouse", "iso", sens_iso)
	for b in BUSES:
		cfg.set_value("audio", String(b), float(volume[b]))
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
		AudioServer.set_bus_volume_db(i, linear_to_db(maxf(v, 0.001)))


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
	e.ssr_enabled = bool(o.ssr) and hi
	e.ssao_enabled = bool(o.ssao) and (hi or mid)
	e.volumetric_fog_enabled = bool(o.fog) and (hi or mid)
