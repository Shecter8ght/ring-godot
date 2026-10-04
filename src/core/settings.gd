extends Node
## Настройки игрока: графика, мышь, громкость — user://settings.cfg (разделы graphics, mouse,
## audio; вид от первого лица и лобби пишут туда же свои разделы). Меняются в меню Esc →
## «Настройки», применяются сразу. Тесты и инструменты (res://tools/…) — всегда с умолчаниями и
## ничего не сохраняют. Autoload `Settings`.
##
## Графика: «высоко» — как задумано в сценах (SDFGI, SSIL, SSAO, объёмный туман, тени 8К, MSAA 4×);
## «средне» — без SDFGI и SSIL, тени 4К, MSAA 2×; «низко» — ещё без SSAO и тумана, тени 2К, рендер 3D в
## 77 % разрешения с FSR. TAA выключен везде: при повороте камеры он оставлял за предметами
## тающий шлейф (замер: кадр в движении против того же ракурса в покое — шлейф только от TAA). Исходные значения окружения запоминаются на нём (meta), чтобы вернуть.
## Громкость — по шинам: выстрелы, шаги, эффекты (попадания, двери, голоса), окружение.
## Экран: во весь экран (без рамки, поверх панели задач — умолчание, project.godot) или в окне;
## Alt+Enter — переключить.

signal changed

const PATH := "user://settings.cfg"
const QUALITY := ["low", "medium", "high"]
const QUALITY_NAMES := {"low": "Низко", "medium": "Средне", "high": "Высоко"}
const WINDOW_MODES := ["fullscreen", "windowed"]
const WINDOW_NAMES := {"fullscreen": "Во весь экран", "windowed": "В окне"}
## Шина → подпись в меню. Master — общая.
const BUSES := {"Master": "Общая", "Shots": "Выстрелы", "Steps": "Шаги", "World": "Эффекты", "Ambient": "Окружение"}
## Множители чувствительности мыши: от очень медленной до очень быстрой (ползунок — по экспоненте,
## точное число — в поле рядом).
const SENS_RANGE := [0.05, 10.0]
## Поле зрения от первого лица — по горизонтали, как на экране 16:9, град (раздел view).
const FOV_H_RANGE := [50.0, 120.0]
const FOV_H_DEFAULT := 90.0

var quality: String = "high"
## Во весь экран или в окне (WINDOW_MODES).
var window_mode: String = "fullscreen"
## Множитель чувствительности мыши: от первого лица (взгляд) и в изометрии (поворот камеры СКМ).
var sens_fps: float = 1.0
var sens_iso: float = 1.0
## Отдельно — пока целишься (ПКМ, оптика: поверх её поправки на кратность).
var sens_ads: float = 1.0
## Мышь вверх — взгляд вниз (как у лётчиков).
var invert_y: bool = false
## Поле зрения от первого лица по горизонтали (на 16:9), град; камере — fps_fov_v().
var fov_h: float = FOV_H_DEFAULT
## Громкость по шине, 0–1.
var volume: Dictionary = {"Master": 1.0, "Shots": 1.0, "Steps": 1.0, "World": 1.0, "Ambient": 1.0}
## Гарнитура на ушах своего игрока (data/armor.json → headsets[…].headset): поправки шин, дБ, и
## насколько дальше слышно (hear_k). Не сохраняется — это снаряжение, а не настройка.
var headset: Dictionary = {}
const HEADSET_DB := {"Shots": "shots_db", "Steps": "steps_db", "World": "world_db"}

## Чит «бессмертие» (меню Esc → Настройки, консоль: god) — раздел cheats; в коопе решает хост.
var god: bool = false
## Админский ассортимент Михалыча: показывает все стволы и не проверяет доверие для оружия.
var all_weapons: bool = false
## Свои клавиши поверх project.godot: действие → {"t": "k", "c": физ. код} или {"t": "m", "b": кнопка
## мыши}. Раздел keys; меняются в меню Esc → «Управление».
var keys: Dictionary = {}

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
		apply_window()
	_apply_audio()
	get_tree().node_added.connect(_on_node_added)
	apply_graphics.call_deferred()


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(PATH) != OK:
		return
	var q := String(cfg.get_value("graphics", "quality", quality))
	quality = q if q in QUALITY else "high"
	var wm := String(cfg.get_value("graphics", "window", window_mode))
	window_mode = wm if wm in WINDOW_MODES else "fullscreen"
	sens_fps = clampf(float(cfg.get_value("mouse", "fps", sens_fps)), SENS_RANGE[0], SENS_RANGE[1])
	sens_iso = clampf(float(cfg.get_value("mouse", "iso", sens_iso)), SENS_RANGE[0], SENS_RANGE[1])
	sens_ads = clampf(float(cfg.get_value("mouse", "ads", sens_ads)), SENS_RANGE[0], SENS_RANGE[1])
	invert_y = bool(cfg.get_value("mouse", "invert_y", invert_y))
	fov_h = clampf(float(cfg.get_value("view", "fov_h", fov_h)), FOV_H_RANGE[0], FOV_H_RANGE[1])
	for b in BUSES:
		volume[b] = clampf(float(cfg.get_value("audio", String(b), 1.0)), 0.0, 1.0)
	god = bool(cfg.get_value("cheats", "god", false))
	all_weapons = bool(cfg.get_value("cheats", "all_weapons", false))
	if cfg.has_section("keys"):
		for a in cfg.get_section_keys("keys"):
			var d: Variant = cfg.get_value("keys", a)
			if d is Dictionary and InputMap.has_action(a) and _event_from(d as Dictionary) != null:
				keys[a] = d
	_apply_keys()


func save() -> void:
	if _tool_run:
		return
	var cfg := ConfigFile.new()
	cfg.load(PATH)
	cfg.set_value("graphics", "quality", quality)
	cfg.set_value("graphics", "window", window_mode)
	cfg.set_value("mouse", "fps", sens_fps)
	cfg.set_value("mouse", "iso", sens_iso)
	cfg.set_value("mouse", "ads", sens_ads)
	cfg.set_value("mouse", "invert_y", invert_y)
	cfg.set_value("view", "fov_h", fov_h)
	for b in BUSES:
		cfg.set_value("audio", String(b), float(volume[b]))
	cfg.set_value("cheats", "god", god)
	cfg.set_value("cheats", "all_weapons", all_weapons)
	if cfg.has_section("keys"):
		cfg.erase_section("keys")
	for a in keys:
		cfg.set_value("keys", String(a), keys[a])
	cfg.save(PATH)


func set_quality(q: String) -> void:
	if not q in QUALITY:
		return
	quality = q
	apply_graphics()
	save()
	changed.emit()


func set_window_mode(m: String) -> void:
	if not m in WINDOW_MODES:
		return
	window_mode = m
	apply_window()
	save()
	changed.emit()


## Во весь экран — окно без рамки на весь монитор, поверх панели задач; в окне — 80 % экрана
## по центру.
func apply_window() -> void:
	if DisplayServer.get_name() == "headless":
		return
	if window_mode == "windowed":
		if DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_WINDOWED:
			return
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		var scr := DisplayServer.screen_get_usable_rect()
		var sz := Vector2i(Vector2(scr.size) * 0.8)
		DisplayServer.window_set_size(sz)
		DisplayServer.window_set_position(scr.position + (scr.size - sz) / 2)
	elif DisplayServer.window_get_mode() != DisplayServer.WINDOW_MODE_FULLSCREEN:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)


## Alt+Enter — во весь экран / в окне.
func _input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k and k.pressed and not k.echo and k.alt_pressed and (k.keycode == KEY_ENTER or k.keycode == KEY_KP_ENTER):
		set_window_mode("windowed" if window_mode == "fullscreen" else "fullscreen")
		get_viewport().set_input_as_handled()


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


func set_fov_h(v: float) -> void:
	fov_h = clampf(v, FOV_H_RANGE[0], FOV_H_RANGE[1])
	save()
	changed.emit()


## Вертикальное поле зрения камеры (Camera3D держит высоту, keep_aspect = KEEP_HEIGHT) для
## горизонтального h на экране с соотношением сторон aspect, град.
static func fov_v_from_h(h_deg: float, aspect: float = 16.0 / 9.0) -> float:
	return rad_to_deg(2.0 * atan(tan(deg_to_rad(h_deg) * 0.5) / aspect))


## Поле зрения от первого лица без прицела — вертикальное, для Camera3D.fov.
func fps_fov_v() -> float:
	return fov_v_from_h(fov_h)


# ---------------------------------------------------------------- клавиши

## Назначить действию клавишу / кнопку мыши (одна на действие, как в project.godot).
func set_key(action: String, ev: InputEvent) -> void:
	var d := _event_to(ev)
	if d.is_empty() or not InputMap.has_action(action):
		return
	keys[action] = d
	_apply_keys()
	save()
	changed.emit()


## Все клавиши — как в проекте.
func reset_keys() -> void:
	keys.clear()
	InputMap.load_from_project_settings()
	save()
	changed.emit()


## Какие ещё действия висят на том же, что у action (пусто — ни одно).
func key_conflicts(action: String) -> Array[String]:
	var out: Array[String] = []
	var mine := _event_to(_first_event(action))
	if mine.is_empty():
		return out
	for a in InputMap.get_actions():
		var s := String(a)
		if s == action or s.begins_with("ui_"):
			continue
		if _event_to(_first_event(s)) == mine:
			out.append(s)
	return out


func _apply_keys() -> void:
	for a in keys:
		var ev := _event_from(keys[a] as Dictionary)
		if ev and InputMap.has_action(a):
			InputMap.action_erase_events(a)
			InputMap.action_add_event(a, ev)


func _first_event(action: String) -> InputEvent:
	if not InputMap.has_action(action):
		return null
	var evs := InputMap.action_get_events(action)
	return evs[0] if not evs.is_empty() else null


static func _event_to(ev: InputEvent) -> Dictionary:
	if ev is InputEventKey:
		var k := ev as InputEventKey
		return {"t": "k", "c": int(k.physical_keycode if k.physical_keycode != 0 else k.keycode)}
	if ev is InputEventMouseButton:
		return {"t": "m", "b": int((ev as InputEventMouseButton).button_index)}
	return {}


static func _event_from(d: Dictionary) -> InputEvent:
	match String(d.get("t", "")):
		"k":
			var k := InputEventKey.new()
			k.physical_keycode = int(d.get("c", 0)) as Key
			return k
		"m":
			var m := InputEventMouseButton.new()
			m.button_index = int(d.get("b", 0)) as MouseButton
			return m
	return null


## Бессмертие вкл/выкл: сохраняется и сразу действует на своего игрока (и в следующих рейдах).
func set_god(on: bool) -> void:
	god = on
	save()
	for n in get_tree().get_nodes_in_group("all_players"):
		var pl := n as Player
		if pl and pl.is_local():
			pl.set_god(on)
	changed.emit()


## Полный оружейный ассортимент у Михалыча; деньги и место в инвентаре по-прежнему нужны.
func set_all_weapons(on: bool) -> void:
	all_weapons = on
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
	elif n is DirectionalLight3D:
		# солнце без PCSS (угловой размер): при низком солнце (закат, 12°) мягкая тень в каскадах
		# не находит перекрытие над головой — прямое солнце ложилось на пол коридоров ТЦ под
		# потолком ярким пятном (проба: пол 0.49 → 0.13 без PCSS); мягкость края — shadow_blur
		(n as DirectionalLight3D).light_angular_distance = 0.0


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
			vp.msaa_3d = Viewport.MSAA_2X
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
