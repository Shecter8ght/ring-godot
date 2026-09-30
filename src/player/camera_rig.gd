class_name CameraRig
extends Node3D
## Камера. Обычно — изометрия: следует за локальным игроком, чуть уезжает к курсору, зум
## колесом, вращение Q/E или зажатой средней кнопкой мыши. Даёт игроку точку на земле под курсором.
## ПКМ — прицел от первого лица на весь экран: своя камера в глазах игрока, мышь захвачена и
## водит взглядом, WASD — как в шутере от первого лица, в руках — модель оружия, мушка по центру.
## Оптика (штатная у винтовки, 4× на планке) — отдельный рендер: вторая камера с узким полем
## зрения рисует в свою текстуру, текстура ложится ровно на окуляр модели (проекция линзы на экран),
## остальной экран — обычный вид из глаз. Сетка и тень по краю — шейдером окуляра.
## Эргономика ствола (WeaponStats): «довод» в прицел и раскачка прицела.

@export var target_path: NodePath

var ads_active: bool = false
## Режим «от первого лица» (V или меню): камера всегда в глазах, ПКМ — прицел. Сохраняется в
## user://settings.cfg.
static var first_person_mode: bool = false
static var _settings_loaded: bool = false
const SETTINGS_PATH := "user://settings.cfg"
var _bob_t: float = 0.0
var _distance: float = Balance.CAMERA_DISTANCE
var _target: Node3D
var _shake: float = 0.0
var _hitmarker: Control
## Ранен: кровь по краям, блёклые цвета, стук сердца, звук глуше; лёжа — надпись с таймером.
var _hurt_fx: ColorRect
var _hurt_amount: float = 0.0
## Стресс на экране (плавно за Player.stress_k).
var _stress_fx: float = 0.0
var _beat_t: float = 0.0
var _down_label: Label
var _muffle: AudioEffectLowPassFilter
## ПНВ: зелёная усиленная картинка с зерном.
var _nvg_fx: ColorRect
## Выносливость — тонкая полоса внизу, пока не полная.
var _stamina_bar: ProgressBar
var _hitmarker_t: float = 0.0
var _rng := RandomNumberGenerator.new()
var _mmb: bool = false
var _look_yaw: float = 0.0
var _look_pitch: float = 0.0
var _ads_cam: Camera3D
var _viewmodel: Node3D
var _arms: FirstPersonArms
var _viewmodel_id: String = ""
## Приклад и затыльник модели в руках: у бедра видны, в прицеле (под щекой) — прячутся.
var _cheek_parts: Array[GeometryInstance3D] = []
## Оптика: своя камера в своей текстуре и окно на экране поверх окуляра.
var scope_active: bool = false
## 0 — основной прицел, 1 — угловой (плавно между ними при переключении).
var _sight_k: float = 0.0
var _scope_vp: SubViewport
var _scope_cam: Camera3D
var _scope_view: TextureRect
var _sway_t: float = 0.0
var _scope_zoom: float = 1.0
## Солнце сцены — для бликов в оптике (ищется один раз).
var _sun: DirectionalLight3D
## Солнце ближе этого угла к оси оптики — засветка и блик по краю линзы, град.
const SCOPE_SUN_NEAR_DEG := 35.0
var _weapon_label: Label
var _compass: Compass

@onready var _pivot: Node3D = $Pivot
@onready var _camera: Camera3D = $Pivot/Camera3D
var _glare: LightGlare


func _ready() -> void:
	add_to_group("camera_rig")
	rotation_degrees.y = Balance.CAMERA_YAW_DEG
	_pivot.rotation_degrees.x = -Balance.CAMERA_PITCH_DEG
	_camera.fov = Balance.CAMERA_FOV
	if target_path != NodePath():
		_target = get_node(target_path)
	# потолки и купол — только от первого лица: изометрия смотрит сверху сквозь них
	_camera.cull_mask &= ~SectorBuilder.CEILING_LAYER
	# служебная геометрия карты дождя — никому из игровых камер
	_camera.cull_mask &= ~RainOcclusion.LAYER
	_ads_cam = Camera3D.new()
	_ads_cam.name = "AdsCamera"
	_ads_cam.top_level = true
	_ads_cam.near = 0.05
	_ads_cam.far = 900.0
	_ads_cam.cull_mask &= ~RainOcclusion.LAYER
	_ads_cam.cull_mask &= ~Player.OWN_BODY_LAYER
	add_child(_ads_cam)
	_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	_ads_cam.add_child(_arms)
	_build_hud()
	_glare = LightGlare.new()
	_glare.name = "Glare"
	add_child(_glare)
	_build_scope()
	# в изометрии отсечения за стенами нет (см. _set_ads)
	get_viewport().use_occlusion_culling = false


## Отдача в прицеле: взгляд уходит вверх (pitch) и вбок (h, плюс — вправо) — навсегда, тянуть мышью.
func add_recoil(pitch: float, h: float) -> void:
	_look_pitch = clampf(_look_pitch + pitch, -Balance.ADS_PITCH_LIMIT, Balance.ADS_PITCH_LIMIT)
	_look_yaw -= h


## Толчок камеры (выстрел, попадание по тебе, взрыв); складывается и затухает сам.
func add_shake(amount: float) -> void:
	_shake = minf(_shake + amount, 1.0)


## Крестик у курсора (в прицеле — по центру): попал; kill — крупнее и красный.
func show_hitmarker(kill: bool) -> void:
	_hitmarker_t = Balance.HITMARKER_SEC * (1.6 if kill else 1.0)
	_hitmarker.modulate = Color(1.0, 0.25, 0.2) if kill else Color(1, 1, 1)
	_hitmarker.scale = Vector2.ONE * (1.5 if kill else 1.0)


## Точка, из которой «смотрит» игрок: для силы тряски от взрыва и т.п.
func focus_point() -> Vector3:
	if ads_active:
		return _ads_cam.global_position
	return _target.global_position if _target else global_position


func set_target(node: Node3D) -> void:
	_target = node


static func load_settings() -> void:
	if _settings_loaded:
		return
	_settings_loaded = true
	# тесты и инструменты (res://tools/…) — всегда с умолчаниями, настройки игрока их не трогают
	for a in OS.get_cmdline_args():
		if String(a).begins_with("res://tools/"):
			return
	var cfg := ConfigFile.new()
	if cfg.load(SETTINGS_PATH) == OK:
		first_person_mode = bool(cfg.get_value("view", "first_person", false))


static func set_first_person_mode(on: bool) -> void:
	first_person_mode = on
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS_PATH)
	cfg.set_value("view", "first_person", on)
	cfg.save(SETTINGS_PATH)


## Открыто окно (рюкзак, карта, убежище, меню) — мышь нужна курсором, взгляд стоит.
func _ui_blocking() -> bool:
	if PauseMenu.shown or (Raid.current and Raid.current.ui_open()):
		return true
	for n in get_tree().get_nodes_in_group("esc_windows"):
		if n.has_method("is_open") and bool(n.call("is_open")):
			return true
	return false


## ПНВ — как в Tarkov / Arma / Ground Branch: не «кислотный» зелёный, а бледный фосфор;
## автоматическая регулировка яркости трубки (ABC: светлая сцена — усиление меньше, в темноте —
## больше), яркое мягко уходит в ореол, а не выжигает кадр; чёрное — не ноль (свечение экрана);
## трубка чуть мягкая, зерно тонкое и сильнее в темноте, круглая виньетка с мягким краем.
const NVG_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform vec3 phosphor = vec3(0.56, 0.96, 0.66);
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float lum(vec3 c) { return dot(c, vec3(0.3, 0.59, 0.11)); }
void fragment() {
	vec2 px = SCREEN_PIXEL_SIZE;
	// мягкость трубки: крест из 5 выборок
	float l = lum(texture(screen_tex, SCREEN_UV).rgb) * 0.4;
	l += lum(texture(screen_tex, SCREEN_UV + vec2(px.x, 0.0) * 1.5).rgb) * 0.15;
	l += lum(texture(screen_tex, SCREEN_UV - vec2(px.x, 0.0) * 1.5).rgb) * 0.15;
	l += lum(texture(screen_tex, SCREEN_UV + vec2(0.0, px.y) * 1.5).rgb) * 0.15;
	l += lum(texture(screen_tex, SCREEN_UV - vec2(0.0, px.y) * 1.5).rgb) * 0.15;
	// ABC: средняя яркость кадра (верхний мип) задаёт усиление
	float avg = lum(textureLod(screen_tex, vec2(0.5), 9.0).rgb);
	float gain = clamp(0.3 / (avg + 0.004), 2.0, 30.0);
	float v = 1.0 - exp(-l * gain);
	// ореол вокруг ярких источников (фонарь, ракета, окно) — из размытого мипа
	float glow = lum(textureLod(screen_tex, SCREEN_UV, 4.0).rgb) * gain;
	v += max(glow - 0.9, 0.0) * 0.25;
	// потолок яркости — экран трубки не бьёт в глаза; пол — фосфор светится и в «чёрном»
	v = 0.035 + 0.8 * (1.0 - exp(-v * 1.6));
	// точечные яркие источники (точка коллиматора, ЛЦУ, лампочка) — выше потолка, почти белые:
	// иначе сжатие ровняло их с фоном и точка прицела «становилась цветом стекла»
	float hot = smoothstep(0.8, 0.97, lum(texture(screen_tex, SCREEN_UV).rgb));
	v += hot * 0.45;
	float n = hash(floor(SCREEN_UV / px / 1.5) + fract(TIME * 13.0) * 97.0) - 0.5;
	v += n * mix(0.07, 0.025, v);
	vec2 d = SCREEN_UV - 0.5;
	d.x *= px.y / px.x;
	float vig = smoothstep(0.68, 0.40, length(d));
	COLOR = vec4(mix(phosphor * clamp(v, 0.0, 1.0), vec3(0.9, 1.0, 0.92), hot * 0.6) * vig, 1.0);
}
"""

const HURT_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float amount = 0.0;
uniform float pulse = 0.0;
// стресс: сужается поле зрения (тёмные края в такт сердцу), краски тускнеют — без крови
uniform float stress = 0.0;
void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	float g = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(c, vec3(g), amount * 0.75 + stress * 0.3);
	vec2 d = SCREEN_UV - 0.5;
	d.x *= SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
	float r = length(d);
	c *= 1.0 - smoothstep(0.34 - pulse * 0.03, 0.85, r) * stress * 0.75;
	float v = smoothstep(0.22 - pulse * 0.06, 0.72, r) * amount;
	c = mix(c, vec3(0.32, 0.0, 0.0), clamp(v * 1.4, 0.0, 0.88));
	c *= 1.0 - amount * (0.22 + pulse * 0.1);
	COLOR = vec4(c, 1.0);
}
"""


## ИК-подсветка ПНВ: слабый широкий луч по взгляду — в полной темноте (ночь, свет отключён)
## трубке нечего усиливать. Только у себя (узел камеры), с тенью — сквозь стены не светит.
var _nvg_ir: SpotLight3D


func _tick_nvg_ir(on: bool) -> void:
	if on and _nvg_ir == null:
		_nvg_ir = SpotLight3D.new()
		_nvg_ir.name = "NvgIr"
		_nvg_ir.top_level = true
		_nvg_ir.light_color = Color(0.9, 0.95, 1.0)
		_nvg_ir.light_energy = 0.9
		_nvg_ir.spot_range = 32.0
		_nvg_ir.spot_angle = 48.0
		_nvg_ir.spot_attenuation = 0.6
		_nvg_ir.shadow_enabled = true
		_nvg_ir.shadow_caster_mask = 0xFFFFF & ~Player.OWN_BODY_LAYER
		_nvg_ir.light_specular = 0.1
		_nvg_ir.light_volumetric_fog_energy = 0.0
		_nvg_ir.set_meta("crisp", true)
		add_child(_nvg_ir)
	if _nvg_ir:
		_nvg_ir.visible = on
		var cam := get_viewport().get_camera_3d()
		if on and cam:
			_nvg_ir.global_transform = cam.global_transform


## ПНВ усиливает свет, которого глазом не видно: у себя — ярче окружение и выдержка.
func _nvg_env(on: bool) -> void:
	var we := get_tree().current_scene.find_child("WorldEnvironment", false, false) as WorldEnvironment if get_tree().current_scene else null
	if we == null or we.environment == null:
		return
	var e := we.environment
	if on:
		e.set_meta("nvg_prev", [e.ambient_light_energy, e.tonemap_exposure])
		# усиление мягкое: остальное делает трубка (ABC в шейдере), иначе яркое выжигается
		e.ambient_light_energy = maxf(e.ambient_light_energy, 0.5) * 3.0
		e.tonemap_exposure *= 1.5
	elif e.has_meta("nvg_prev"):
		var prev: Array = e.get_meta("nvg_prev")
		e.ambient_light_energy = float(prev[0])
		e.tonemap_exposure = float(prev[1])
		e.remove_meta("nvg_prev")


## Ранения на экране: лёжа — сильно (кровь, серость, пульс, стук сердца, глухой звук, таймер);
## мало здоровья — слегка.
func _update_hurt(pl: Player, delta: float) -> void:
	if pl == null or not pl.is_local():
		return
	var down := pl.is_downed()
	var want := 0.0
	if down:
		want = 1.0
	elif pl.is_alive():
		var frac := pl.health.hp / maxf(pl.health.max_hp, 1.0)
		want = clampf((0.35 - frac) / 0.35, 0.0, 1.0) * 0.45
	_hurt_amount = move_toward(_hurt_amount, want, delta * 1.5)
	# стресс: тёмные края и тусклые краски, сердце колотится (от heart_from)
	var sk := pl.stress_k() if not down else 0.0
	_stress_fx = move_toward(_stress_fx, sk, delta * 0.8)
	_hurt_fx.visible = _hurt_amount > 0.01 or _stress_fx > 0.01
	var loud := not down and pl.stress >= float(Balance.STRESS.heart_from)
	var bpm := 64.0 if down else lerpf(90.0, 140.0, sk)
	_beat_t += delta * bpm / 60.0
	if _beat_t >= 1.0:
		_beat_t -= 1.0
		if down:
			Audio.play("heartbeat", pl.global_position + Vector3.UP)
		elif loud:
			Audio.play("heartbeat", pl.global_position + Vector3.UP, -10.0 + 6.0 * sk)
	var pulse := pow(absf(sin(_beat_t * PI)), 8.0)
	if _hurt_fx.visible:
		var sm := _hurt_fx.material as ShaderMaterial
		sm.set_shader_parameter("amount", _hurt_amount)
		sm.set_shader_parameter("pulse", pulse)
		sm.set_shader_parameter("stress", _stress_fx)
	_set_muffle(down)
	_down_label.visible = down
	if down:
		var h := pl.health
		var lines := "ТЯЖЁЛОЕ РАНЕНИЕ — истекаешь кровью: %d с   ·   ранение %d из %d" % [int(ceil(h.bleed_t)), h.downs, Balance.DOWN_MAX]
		var dragger: Player = Raid.current.dragger_of(pl.peer_id) if Raid.current else null
		if dragger:
			lines += "\nТЕБЯ ТАЩАТ — стреляй из пистолета, прикрывай"
		lines += "\n%s — аптечка (подняться) / бинт   ·   %s (держать) — сдаться" % [PauseMenu.key_name("use_med"), PauseMenu.key_name("drag")]
		_down_label.text = lines


## Лёжа раненым звук глуше (на общей шине — срез верхов).
func _set_muffle(on: bool) -> void:
	if on == (_muffle != null):
		return
	if on:
		_muffle = AudioEffectLowPassFilter.new()
		_muffle.cutoff_hz = 900.0
		AudioServer.add_bus_effect(0, _muffle)
	else:
		for i in range(AudioServer.get_bus_effect_count(0)):
			if AudioServer.get_bus_effect(0, i) == _muffle:
				AudioServer.remove_bus_effect(0, i)
				break
		_muffle = null


## Точка коллиматора / голографа в руках: в ПНВ крупнее (в трубке тонкая точка теряется).
func _reticle_nv(on: bool) -> void:
	if _viewmodel == null:
		return
	for mi in _viewmodel.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("reticle_dot"):
			(mi as MeshInstance3D).scale = Vector3.ONE * (Balance.NVG_RETICLE_SCALE if on else 1.0)


func _exit_tree() -> void:
	_set_muffle(false)
	# ушли со сцены в ПНВ — точка прицелов снова красная (материал общий, переживает сцену)
	WeaponModels.set_night_vision(false)


## Дистанция изометрии (зум): в тесном убежище ближе, чем в рейде.
func set_distance(d: float) -> void:
	_distance = clampf(d, Balance.CAMERA_ZOOM_MIN, Balance.CAMERA_ZOOM_MAX)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("view_toggle") and not event.is_echo():
		set_first_person_mode(not first_person_mode)
		get_viewport().set_input_as_handled()
		return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_MIDDLE:
			_mmb = mb.pressed
			# от первого лица СКМ — основной / угловой прицел (камеру она там не крутит)
			if mb.pressed and ads_active and not _ui_blocking():
				var pl := _target as Player
				if pl and pl.is_local():
					pl.toggle_sight()
		elif mb.pressed and not ads_active:
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_distance = maxf(Balance.CAMERA_ZOOM_MIN, _distance - Balance.CAMERA_ZOOM_STEP)
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_distance = minf(Balance.CAMERA_ZOOM_MAX, _distance + Balance.CAMERA_ZOOM_STEP)
	elif event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		if ads_active and not _ui_blocking():
			# вправо — поворот вправо; у оптики чувствительность меньше пропорционально полю зрения
			var sens := ads_sens()
			var dy := -mm.relative.y if Settings.invert_y else mm.relative.y
			_look_yaw -= mm.relative.x * sens
			_look_pitch = clampf(_look_pitch - dy * sens, -Balance.ADS_PITCH_LIMIT, Balance.ADS_PITCH_LIMIT)
		elif _mmb:
			rotation.y -= mm.relative.x * Balance.CAMERA_MMB_SENS * Settings.sens_iso


func _process(delta: float) -> void:
	# цель ушла со сцены (смена уровня, хост вышел) — искать новую
	if _target != null and (not is_instance_valid(_target) or not _target.is_inside_tree()):
		_target = null
	if _target == null:
		_target = get_tree().get_first_node_in_group("players") as Node3D
		if _target == null:
			return
	var pl := _target as Player
	load_settings()
	# режим от первого лица (V) — и в рейде, и в убежище (в том числе сидя на диване)
	var want_ads := pl != null and pl.is_local() and pl.is_alive() and (pl.aiming or first_person_mode)
	if want_ads != ads_active:
		_set_ads(want_ads, pl)
	_shake = maxf(0.0, _shake - Balance.SHAKE_DECAY * _shake * delta - 0.01 * delta)
	var s := _shake * _shake * 4.0
	_hitmarker_t -= delta
	_hitmarker.visible = _hitmarker_t > 0.0
	if ads_active:
		_process_ads(pl, delta, s)
		# окно открыто — курсор свободен; закрыли — снова взгляд мышью
		var want_mouse := Input.MOUSE_MODE_VISIBLE if _ui_blocking() else Input.MOUSE_MODE_CAPTURED
		if Input.mouse_mode != want_mouse and not PauseMenu.shown:
			Input.mouse_mode = want_mouse
		if _hitmarker.visible:
			_hitmarker.position = get_viewport().get_visible_rect().size * 0.5
	else:
		_process_iso(delta, s)
		if _hitmarker.visible:
			_hitmarker.position = get_viewport().get_mouse_position()
	_update_hud(pl)
	_update_hurt(pl, delta)
	if _stamina_bar and pl and pl.is_local():
		_stamina_bar.visible = pl.stamina < Balance.STAMINA_MAX - 0.5 and pl.combat_enabled
		_stamina_bar.value = pl.stamina
	if _nvg_fx:
		var on := pl != null and pl.is_local() and pl.nvg_on
		if on != _nvg_fx.visible:
			_nvg_env(on)
			WeaponModels.set_night_vision(on)
			_reticle_nv(on)
		_nvg_fx.visible = on
		_tick_nvg_ir(on)
	var cam := get_viewport().get_camera_3d()
	if _glare:
		_glare.tick(cam, pl if pl and pl.is_local() else null, ads_active, pl != null and pl.is_local() and pl.nvg_on, delta)
	if cam:
		_compass.set_heading(cam.global_basis)
	_compass.set_marks(_extraction_marks(pl))


## Точки эвакуации для компаса: [курс°, расстояние м, заперта ли для меня]. Заперта — нет питания
## (рубильник) или у меня нет нужного ключа.
func _extraction_marks(pl: Player) -> Array:
	var out: Array = []
	if pl == null or Raid.current == null or not pl.combat_enabled:
		return out
	for x in get_tree().get_nodes_in_group("extractions"):
		var ep := x as ExtractionPoint
		if ep == null:
			continue
		var d := ep.global_position - pl.global_position
		var bearing := fposmod(rad_to_deg(atan2(d.x, -d.z)), 360.0)
		var locked := (ep.required_switch != "" and not bool(Raid.current.switches.get(ep.required_switch, false))) 			or (ep.required_key != "" and not pl.inventory.has(ep.required_key))
		out.append([bearing, Vector2(d.x, d.z).length(), locked])
	return out


func _process_iso(delta: float, s: float) -> void:
	# Вращение камеры вокруг игрока: Q/E, плавно, пока зажато (средняя кнопка — в _unhandled_input).
	var turn := Input.get_axis("camera_left", "camera_right")
	if turn != 0.0:
		rotation.y -= deg_to_rad(Balance.CAMERA_TURN_DEG_PER_SEC) * turn * delta
	_camera.position.z = lerpf(_camera.position.z, _distance, minf(1.0, 6.0 * delta))
	# Тряска — смещение камеры в её плоскости; квадрат силы, чтобы мелкие толчки были мягкими.
	_camera.position.x = _rng.randf_range(-s, s)
	_camera.position.y = _rng.randf_range(-s, s)
	SectorMaterials.set_cutaway_distance(_camera.position.z * Balance.CAMERA_CUTAWAY_NEAR, _camera.position.z * Balance.CAMERA_CUTAWAY_FAR)
	var cursor := cursor_on_ground()
	var lead := (cursor - _target.global_position) * Balance.CAMERA_CURSOR_LEAD
	lead.y = 0.0
	lead = lead.limit_length(Balance.CAMERA_CURSOR_LEAD_MAX)
	var want := _target.global_position + lead
	global_position = global_position.lerp(want, minf(1.0, Balance.CAMERA_FOLLOW_SMOOTH * delta))
	if _target is Player:
		var pl := _target as Player
		pl.cursor_ground = cursor
		pl.cursor_body = _body_under_cursor()


# ---------------------------------------------------------------- прицел от первого лица

func _set_ads(on: bool, pl: Player) -> void:
	ads_active = on
	if pl:
		pl.ads = on
		pl.set_first_person(on)
	if on:
		# взгляд — туда, куда уже смотрит корпус; по вертикали — горизонт
		_look_yaw = pl.body_yaw()
		_look_pitch = 0.0
		_ads_cam.fov = _ads_fov(pl) + 8.0
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		_ads_cam.current = true
		# без выреза стен: из глаз игрока стены вокруг должны быть целыми
		SectorMaterials.set_cutaway_distance(0.0, 0.001)
	else:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		_camera.current = true
		if _viewmodel:
			_viewmodel.visible = false
		_arms.visible = false
		# курсор — туда, куда смотрели: выход из прицела не сбивает направление
		if pl:
			var ahead := pl.global_position + Vector3(sin(_look_yaw), 0.0, cos(_look_yaw)) * 6.0
			Input.warp_mouse(_camera.unproject_position(ahead))
	# отсечение за стенами — только из глаз: в изометрии стены у камеры растворены, и окклюдер
	# спрятал бы то, что за невидимой стеной (в том числе игрока)
	get_viewport().use_occlusion_culling = on
	if not on:
		_set_scope(false)


func _process_ads(pl: Player, delta: float, s: float) -> void:
	var wid := pl.weapon_id
	var spec := pl.spec() if wid != "" else {}
	var scoped := bool(spec.get("scoped", false))
	# без ПКМ (режим от первого лица) — широкий вид, оружие у бедра
	var aim_t := pl.aim_progress()
	var fov_to := _ads_fov(pl) if pl.aiming else Balance.FPS_FOV
	_ads_cam.fov = lerpf(_ads_cam.fov, fov_to, minf(1.0, 12.0 * delta))
	# раскачка — по эргономике и стойке; на сошках (сидя/лёжа) почти нет
	_sway_t += delta
	var amp := float(spec.get("sway", 0.0)) * float(Balance.SWAY_STANCE.get(pl.stance_key(), 1.0)) * lerpf(0.4, 1.0, aim_t)
	if pl.aiming:
		amp *= Balance.ADS_SWAY_SCALE
	# стресс — руки ходят сильнее
	amp *= 1.0 + float(Balance.STRESS.sway_k) * pl.stress_k()
	if pl.stance != Player.Stance.STAND:
		amp *= float(spec.get("braced_spread", 1.0))
	if pl.is_downed():
		amp *= Balance.DOWN_SWAY
	var sway := Vector2(sin(_sway_t * 1.13) * 0.7 + sin(_sway_t * 2.71 + 1.3) * 0.3, sin(_sway_t * 0.87 + 0.5) * 0.6 + sin(_sway_t * 2.05) * 0.4) * amp
	# отдача подкидывает взгляд, дальше игрок сам возвращает прицел
	var pitch := _look_pitch + pl.recoil() + sway.y
	var yaw := _look_yaw + sway.x - pl.recoil_h()
	# наклон — крен камеры (глаз уже сдвинут в eye_position)
	var roll := -pl.lean * deg_to_rad(Balance.LEAN_ROLL_DEG)
	_ads_cam.global_transform = Transform3D(Basis.from_euler(Vector3(pitch, yaw + PI, roll)), pl.eye_position())
	_ads_cam.global_position += _ads_cam.global_basis * Vector3(_rng.randf_range(-s, s), _rng.randf_range(-s, s), 0.0) * 0.15
	# пули летят туда, куда смотрит прицел, — с раскачкой
	pl.look_yaw = yaw
	# пули летят туда, куда сейчас смотрит ствол: с отдачей и раскачкой
	pl.look_pitch = pitch
	# модель в руках с обвесами: линия прицеливания на оси взгляда, рукоять — на ads_z перед глазом
	var vm_key := wid + str(pl.weapon_mods)
	if _viewmodel_id != vm_key:
		if _viewmodel:
			_viewmodel.queue_free()
		_viewmodel = WeaponModels.build(wid, pl.weapon_mods) if wid != "" else Node3D.new()
		for mi in _viewmodel.find_children("*", "GeometryInstance3D", true, false):
			var gi := mi as GeometryInstance3D
			gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			# слой 2 — только для глаз: камера оптики его не видит (иначе рисовала бы свой прицел)
			gi.layers = 2
		_cheek_parts.clear()
		for mi in _viewmodel.find_children("*", "GeometryInstance3D", true, false):
			if (mi as GeometryInstance3D).has_meta("hide_ads"):
				_cheek_parts.append(mi as GeometryInstance3D)
		# фонарь у себя светит от модели в руках: луч идёт за стволом (у модели на теле он погашен)
		for n in _viewmodel.find_children("Flashlight*", "SpotLight3D", true, false):
			n.set_meta("own", true)
			(n as SpotLight3D).shadow_caster_mask = 0xFFFFF & ~Player.OWN_BODY_LAYER
		_ads_cam.add_child(_viewmodel)
		_arms.bind_weapon(_viewmodel)
		_viewmodel_id = vm_key
		_reticle_nv(pl.nvg_on)
	_viewmodel.visible = true
	for n in _viewmodel.find_children("LaserBeam*", "Node3D", true, false):
		(n as Node3D).visible = Player.tac_on(pl.weapon_mods, n, "laser")
	for n in _viewmodel.find_children("Flashlight*", "SpotLight3D", true, false):
		(n as SpotLight3D).visible = Player.tac_on(pl.weapon_mods, n, "light")
	var sh: float = _viewmodel.get_meta("sight_h", 0.08)
	var az: float = _viewmodel.get_meta("ads_z", 0.25)
	# выбранный прицел: угловой — ствол заваливается по крену кронштейна, его линия — на оси взгляда
	# переход между прицелами — прямо, не опуская оружия: линия и крен плавно к выбранному
	var want_off := 1.0 if String(spec.get("sight", "primary")) == "offset" and _viewmodel.has_meta("sight_offset") else 0.0
	_sight_k = move_toward(_sight_k, want_off, delta / Balance.SIGHT_SWITCH_SEC)
	var sx := 0.0
	var sroll := 0.0
	if _viewmodel.has_meta("sight_offset") and _sight_k > 0.0:
		var so: Dictionary = _viewmodel.get_meta("sight_offset")
		var e := smoothstep(0.0, 1.0, _sight_k)
		sx = float(so.x) * e
		sh = lerpf(sh, float(so.h), e)
		sroll = float(so.roll) * e
	# у бедра (без ПКМ) → в прицел: «довод» по эргономике (aim_progress), плавно
	var k := smoothstep(0.0, 1.0, aim_t)
	# приклад у бедра виден; вскинул к щеке — он под щекой и заслонял бы низ прицельной линии
	for gi in _cheek_parts:
		gi.visible = k < 0.6
	var cant := Basis(Vector3(0, 0, 1), -sroll)
	var ads_pos := -(Basis(Vector3.UP, PI) * cant * Vector3(sx, sh, 0.0)) + Vector3(0.0, 0.0, -az)
	var hip_pos := Balance.FPS_HIP_POSE
	# На ходу у бедра оружие покачивается. Частота и амплитуда следуют реальной скорости,
	# поэтому при разгоне и инерционной остановке движение модели не включается рывком.
	var planar_speed := Vector2(pl.velocity.x, pl.velocity.z).length()
	var walk_k := clampf(planar_speed / Balance.PLAYER_WALK_SPEED, 0.0, 1.0)
	var sprint_k := clampf((planar_speed - Balance.PLAYER_WALK_SPEED) \
		/ (Balance.PLAYER_SPRINT_SPEED - Balance.PLAYER_WALK_SPEED), 0.0, 1.0)
	var bob_rate := lerpf(float(Balance.WEAPON_BOB.idle_rate), float(Balance.WEAPON_BOB.walk_rate), walk_k)
	bob_rate = lerpf(bob_rate, float(Balance.WEAPON_BOB.sprint_rate), sprint_k)
	_bob_t += delta * bob_rate
	var vertical_bob := lerpf(float(Balance.WEAPON_BOB.idle_vertical),
		float(Balance.WEAPON_BOB.walk_vertical), walk_k)
	var bob := Vector3(sin(_bob_t * 0.5) * float(Balance.WEAPON_BOB.horizontal),
		absf(sin(_bob_t)) * vertical_bob, 0.0) * (1.0 - k)
	# камера смотрит по −Z, у модели дуло по +Z — разворот на π; отдача — подброс и откат назад
	# толчок в плечо: модель откатывается назад, дуло подскакивает, чуть заваливается; пружиной обратно
	# в прицеле дуло подскакивает меньше, а оружие сильнее уходит назад, в плечо и камеру
	var kv := pl.kick_vis
	var flip := kv * lerpf(1.0, Balance.ADS_RECOIL_FLIP_SCALE, k)
	var kick_back := kv * lerpf(1.0, Balance.ADS_RECOIL_BACK_SCALE, k)
	var vm_basis := Basis(Vector3.UP, PI + deg_to_rad(4.0) * (1.0 - k)).rotated(Vector3.RIGHT, flip * 0.05).rotated(Vector3.FORWARD, pl.recoil_h() * 1.5 + deg_to_rad(-3.0) * (1.0 - k)) * Basis(Vector3(0, 0, 1), -sroll * k)
	_viewmodel.transform = Transform3D(vm_basis, hip_pos.lerp(ads_pos, k) + bob + Vector3(0.0, flip * 0.004, kick_back * 0.028))
	_arms.update_pose()
	_set_scope(scoped and _viewmodel.has_meta("ocular") and pl.aiming and aim_t > 0.85 and _sight_k < 0.05)
	if scope_active:
		# подсветка центра сетки (у оптики с подсветкой) — той же клавишей, что фонарь (T)
		_update_scope(float(spec.get("zoom", 4.0)), pl.light_on and _viewmodel.has_meta("reticle_illum"))


## Поле зрения глаз в прицеле: с оптикой — обычное (увеличение — в окуляре), иначе — по стволу.
func _ads_fov(pl: Player) -> float:
	if pl.weapon_id == "":
		return 60.0
	var spec := pl.spec()
	# в убежище оружие в руках — для вида, характеристик нет
	return Balance.SCOPE_MAIN_FOV if bool(spec.get("scoped", false)) else float(spec.get("ads_fov", 60.0))


# ---------------------------------------------------------------- оптика отдельным рендером

func _build_scope() -> void:
	_scope_vp = SubViewport.new()
	_scope_vp.name = "ScopeView"
	_scope_vp.size = Vector2i(Balance.SCOPE_RT_SIZE, Balance.SCOPE_RT_SIZE)
	_scope_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
	_scope_vp.msaa_3d = Viewport.MSAA_2X
	_scope_vp.use_occlusion_culling = true
	add_child(_scope_vp)
	_scope_cam = Camera3D.new()
	_scope_cam.name = "ScopeCamera"
	_scope_cam.near = 0.1
	_scope_cam.far = 900.0
	# без слоя 2: модель в руках (и сам прицел) в окуляр не попадает
	_scope_cam.cull_mask = 0xFFFFF & ~2 & ~RainOcclusion.LAYER
	_scope_cam.current = true
	_scope_vp.add_child(_scope_cam)
	var layer := CanvasLayer.new()
	layer.layer = 9
	add_child(layer)
	_scope_view = TextureRect.new()
	_scope_view.texture = _scope_vp.get_texture()
	_scope_view.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_scope_view.stretch_mode = TextureRect.STRETCH_SCALE
	_scope_view.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scope_view.visible = false
	_scope_view.material = _ocular_material()
	layer.add_child(_scope_view)


## Чувствительность мыши от первого лица: по полю зрения, в оптике — ещё и на кратность; пока
## целишься (ПКМ) — свой множитель из настроек.
func ads_sens() -> float:
	var pl := _target as Player
	var aim_k := Settings.sens_ads if pl != null and pl.aiming else 1.0
	var s := Balance.ADS_SENS * Settings.sens_fps * aim_k * (_ads_cam.fov / 62.0)
	return s / maxf(1.0, _scope_zoom) if scope_active else s


## Поле зрения камеры оптики (для проверок).
func scope_fov() -> float:
	return _scope_cam.fov


func _set_scope(on: bool) -> void:
	if on == scope_active:
		return
	scope_active = on
	_scope_view.visible = on
	_scope_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS if on else SubViewport.UPDATE_DISABLED


## Камера оптики — там же, где глаз, по той же оси; её поле зрения — чтобы в окуляре было
## увеличение zoom относительно основного вида. Окно — ровно на проекции окуляра.
func _update_scope(zoom: float, illum: bool = false) -> void:
	_scope_zoom = zoom
	(_scope_view.material as ShaderMaterial).set_shader_parameter("illum", 1.0 if illum else 0.0)
	var ocular: Vector3 = _viewmodel.to_global(_viewmodel.get_meta("ocular"))
	var r := float(_viewmodel.get_meta("ocular_r"))
	_scope_cam.global_transform = _ads_cam.global_transform
	var dist := maxf(0.02, _ads_cam.global_position.distance_to(ocular))
	# угол окуляра в основном виде и во сколько раз его «растянуть»
	var half_main := atan(r / dist)
	var main_px_per_rad := get_viewport().get_visible_rect().size.y * 0.5 / tan(deg_to_rad(_ads_cam.fov) * 0.5)
	var half_scope := atan(tan(half_main) / maxf(1.0, zoom))
	_scope_cam.fov = rad_to_deg(half_scope * 2.0)
	var c := _ads_cam.unproject_position(ocular)
	var rad_px := tan(half_main) * main_px_per_rad
	_scope_view.position = c - Vector2(rad_px, rad_px)
	_scope_view.size = Vector2(rad_px, rad_px) * 2.0
	_update_scope_sun()


## Солнце для бликов в оптике: где оно в окуляре и насколько близко к оси. Закрыто стеной или
## крышей (луч к солнцу во что-то упёрся) — бликов нет.
func _update_scope_sun() -> void:
	var mat := _scope_view.material as ShaderMaterial
	var sun := _sun_dir()
	var near := 0.0
	var inside := 0.0
	var suv := Vector2(-9, -9)
	var b := _scope_cam.global_basis
	if sun != Vector3.ZERO:
		near = smoothstep(cos(deg_to_rad(SCOPE_SUN_NEAR_DEG)), cos(deg_to_rad(2.0)), (-b.z).dot(sun))
		if near > 0.0 and _sun_blocked(sun):
			near = 0.0
		var far := _scope_cam.global_position + sun * 1000.0
		if near > 0.0 and not _scope_cam.is_position_behind(far):
			suv = _scope_cam.unproject_position(far) / Vector2(_scope_vp.size)
			inside = near * (1.0 - smoothstep(0.5, 0.62, (suv - Vector2(0.5, 0.5)).length()))
	var sd := Vector2(sun.dot(b.x), -sun.dot(b.y))
	mat.set_shader_parameter("sun_uv", suv)
	mat.set_shader_parameter("sun_in", inside)
	mat.set_shader_parameter("sun_near", near)
	mat.set_shader_parameter("sun_dir", sd.normalized() if sd.length() > 1e-4 else Vector2(0, -1))


## Направление на солнце (мировое): DirectionalLight3D сцены светит по своей -Z. Нет — ноль.
func _sun_dir() -> Vector3:
	if _sun == null or not is_instance_valid(_sun):
		_sun = null
		var scene := get_tree().current_scene
		if scene:
			for l in scene.find_children("*", "DirectionalLight3D", true, false):
				if (l as DirectionalLight3D).visible:
					_sun = l
					break
	if _sun == null:
		return Vector3.ZERO
	return _sun.global_basis.z.normalized()


func _sun_blocked(sun: Vector3) -> bool:
	var from := _scope_cam.global_position
	var q := PhysicsRayQueryParameters3D.create(from, from + sun * 400.0, Hitscan.LAYER_WORLD)
	return not get_world_3d().direct_space_state.intersect_ray(q).is_empty()


## Шейдер окуляра: круг, тонкие нити с толстыми «пеньками» к краю, тень по краю (выход зрачка).
## Оптика как у настоящей: хроматическая аберрация растёт к краю (красный наружу, синий внутрь,
## цветная кайма у края поля), солнце в поле — ореол, лучи и цепочка «призраков» по линии через
## центр; солнце рядом с осью — засветка (контраст падает) и блик-полумесяц по краю линзы с его
## стороны. Параметры солнца ставит _update_scope каждый кадр.
func _ocular_material() -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = """
shader_type canvas_item;
uniform float line_w = 0.0018;
uniform float ca = 0.035;
uniform float barrel = 0.22;
uniform float edge_blur = 0.006;
uniform vec2 sun_uv = vec2(-9.0);
uniform float sun_in = 0.0;
uniform float sun_near = 0.0;
uniform vec2 sun_dir = vec2(0.0, -1.0);
// подсветка центра сетки: 0 — выкл, 1 — горит красным
uniform float illum = 0.0;
uniform vec3 illum_color = vec3(1.0, 0.12, 0.06);

void fragment() {
	vec2 c = UV - 0.5;
	float r = length(c) * 2.0;
	// бочка: к краю картинка сжимается (прямые выгибаются наружу), центр чуть увеличен
	vec2 w = c * (1.0 + barrel * r * r) / (1.0 + barrel);
	vec2 uv = 0.5 + w;
	// аберрация: смещение каналов растёт квадратом радиуса (красный наружу, синий внутрь)
	vec2 off = w * ca * r * r;
	vec3 col = vec3(texture(TEXTURE, uv + off).r, texture(TEXTURE, uv).g, texture(TEXTURE, uv - off).b);
	// к краю — мягче (кривизна поля): четыре отсчёта вокруг, вес растёт к краю
	float soft = smoothstep(0.45, 0.95, r);
	vec3 blur = vec3(0.0);
	for (int k = 0; k < 4; k++) {
		float a = float(k) * 1.5708 + 0.785;
		vec2 o = vec2(cos(a), sin(a)) * edge_blur * soft;
		blur += vec3(texture(TEXTURE, uv + off + o).r, texture(TEXTURE, uv + o).g, texture(TEXTURE, uv - off + o).b);
	}
	col = mix(col, blur * 0.25, soft * 0.8);
	// кайма у края поля: холодная изнутри, тёплая снаружи
	float rim = smoothstep(0.8, 0.97, r);
	col += rim * vec3(0.12, -0.02, -0.08) + smoothstep(0.88, 0.97, r) * vec3(-0.06, 0.02, 0.14);
	// солнце в поле зрения: ядро, ореол, лучи-крест
	vec2 s = sun_uv - 0.5;
	vec2 q = c - s;
	float d = length(q);
	float core = exp(-d * 70.0) * 1.4 + exp(-d * 18.0) * 0.35;
	float rays = (exp(-abs(q.y) * 300.0) * exp(-abs(q.x) * 5.0) + exp(-abs(q.x) * 300.0) * exp(-abs(q.y) * 5.0)) * 0.45;
	vec3 flare = vec3(1.0, 0.9, 0.72) * (core + rays) * sun_in;
	// «призраки» — отражения между линзами: по линии солнце — центр, за центром, в разных оттенках
	for (int i = 0; i < 5; i++) {
		float f = -0.35 - float(i) * 0.38;
		float gr = 0.025 + 0.018 * float(i % 3);
		float g = smoothstep(gr, gr * 0.55, length(c - s * f));
		vec3 tint = i % 2 == 0 ? vec3(0.35, 0.6, 1.0) : vec3(0.7, 1.0, 0.45);
		flare += tint * g * 0.3 * sun_in;
	}
	// засветка и блик по краю линзы со стороны солнца (солнце рядом, даже вне поля)
	float side = max(dot(normalize(c + vec2(1e-5)), sun_dir), 0.0);
	float crescent = smoothstep(0.62, 0.9, r) * smoothstep(1.0, 0.9, r) * pow(side, 3.0);
	flare += vec3(1.0, 0.86, 0.62) * crescent * sun_near * 0.9;
	col = mix(col, vec3(0.85, 0.8, 0.72), sun_near * 0.12);
	col += flare;
	// сетка поверх света (нити в светлом поле тёмные)
	float ax = abs(c.x);
	float ay = abs(c.y);
	float thin = step(ax, line_w) + step(ay, line_w);
	float post = step(ax, line_w * 4.0) * step(0.2, ay) + step(ay, line_w * 4.0) * step(0.2, ax);
	// центр перекрестия (нити ближе 0.16 от центра и точка) с подсветкой светится, дальше — чёрные
	float centre = step(r, 0.32);
	float reticle = clamp(thin + post, 0.0, 1.0);
	vec3 ink = mix(vec3(0.01), illum_color * 2.2, illum * centre);
	col = mix(col, ink, reticle);
	float dot_c = step(length(c), line_w * 2.2);
	col = mix(col, illum_color * 2.6, illum * dot_c);
	col += illum_color * illum * 0.35 * exp(-length(c) * 60.0);
	col *= smoothstep(1.0, 0.72, r);
	COLOR = vec4(col, 1.0 - smoothstep(0.97, 1.0, r));
}
"""
	var m := ShaderMaterial.new()
	m.shader = sh
	return m


## Дуло модели в руках (в прицеле) — отсюда появляется вспышка.
## Луч ствола модели в руках: [дуло, направление] (дуло у модели по +Z); нет модели — [].
func barrel_ray() -> Array:
	if _viewmodel == null or not _viewmodel.visible or not ads_active:
		return []
	return [_viewmodel.to_global(_viewmodel.get_meta("muzzle", Vector3.ZERO)), _viewmodel.global_basis.z.normalized()]


func viewmodel_muzzle() -> Vector3:
	if _viewmodel and _viewmodel.visible:
		return _viewmodel.to_global(_viewmodel.get_meta("muzzle", Vector3.ZERO))
	return _ads_cam.global_position - _ads_cam.global_basis.z * 0.6 - _ads_cam.global_basis.y * 0.06


# ---------------------------------------------------------------- HUD камеры

func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	# ранен — поверх мира, под остальным HUD
	_hurt_fx = ColorRect.new()
	_hurt_fx.set_anchors_preset(Control.PRESET_FULL_RECT)
	_hurt_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = HURT_SHADER
	var sm := ShaderMaterial.new()
	sm.shader = sh
	_hurt_fx.material = sm
	_hurt_fx.visible = false
	layer.add_child(_hurt_fx)
	_nvg_fx = ColorRect.new()
	_nvg_fx.set_anchors_preset(Control.PRESET_FULL_RECT)
	_nvg_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var nsh := Shader.new()
	nsh.code = NVG_SHADER
	var nm := ShaderMaterial.new()
	nm.shader = nsh
	_nvg_fx.material = nm
	_nvg_fx.visible = false
	layer.add_child(_nvg_fx)
	layer.move_child(_nvg_fx, 0)
	_stamina_bar = ProgressBar.new()
	_stamina_bar.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	_stamina_bar.offset_left = -120
	_stamina_bar.offset_right = 120
	_stamina_bar.offset_top = -34
	_stamina_bar.offset_bottom = -28
	_stamina_bar.max_value = Balance.STAMINA_MAX
	_stamina_bar.show_percentage = false
	var sfill := StyleBoxFlat.new()
	sfill.bg_color = Color(0.85, 0.82, 0.55, 0.85)
	var sbg := StyleBoxFlat.new()
	sbg.bg_color = Color(0, 0, 0, 0.45)
	_stamina_bar.add_theme_stylebox_override("fill", sfill)
	_stamina_bar.add_theme_stylebox_override("background", sbg)
	_stamina_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_stamina_bar.visible = false
	layer.add_child(_stamina_bar)
	_down_label = Label.new()
	_down_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_down_label.position = Vector2(-460, 96)
	_down_label.size = Vector2(920, 80)
	_down_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_down_label.add_theme_font_size_override("font_size", 20)
	_down_label.add_theme_color_override("font_color", Color(1.0, 0.72, 0.66))
	_down_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	_down_label.add_theme_constant_override("outline_size", 6)
	_down_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_down_label.visible = false
	layer.add_child(_down_label)
	# прицельной метки на экране нет ни в прицеле, ни от бедра: целятся по мушке, метке
	# коллиматора или сетке оптики, от бедра — по стволу
	_hitmarker = Control.new()
	_hitmarker.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_hitmarker.visible = false
	layer.add_child(_hitmarker)
	for ang in [45.0, 135.0, 225.0, 315.0]:
		var r := ColorRect.new()
		r.color = Color(1, 1, 1)
		r.size = Vector2(10, 2)
		r.position = Vector2(6, -1)
		r.pivot_offset = Vector2(-6, 1)
		r.rotation_degrees = ang
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		_hitmarker.add_child(r)
	# оружие, патроны, гранаты — внизу справа
	_weapon_label = Label.new()
	_weapon_label.anchor_left = 1.0
	_weapon_label.anchor_right = 1.0
	_weapon_label.anchor_top = 1.0
	_weapon_label.anchor_bottom = 1.0
	_weapon_label.offset_left = -900.0
	_weapon_label.offset_right = -28.0
	# длинная строка растёт влево — не за край экрана
	_weapon_label.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_weapon_label.clip_text = true
	_weapon_label.offset_top = -64.0
	_weapon_label.offset_bottom = -24.0
	_weapon_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_weapon_label.add_theme_font_size_override("font_size", 22)
	_weapon_label.add_theme_color_override("font_color", Color(0.92, 0.88, 0.78))
	_weapon_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	_weapon_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(_weapon_label)
	# компас — вверху по центру, и в изометрии, и в прицеле
	_compass = Compass.new()
	_compass.anchor_left = 0.5
	_compass.anchor_right = 0.5
	_compass.offset_left = -Balance.COMPASS_WIDTH * 0.5
	_compass.offset_right = Balance.COMPASS_WIDTH * 0.5
	_compass.offset_top = 10.0
	_compass.offset_bottom = 58.0
	_compass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(_compass)


## Полоса компаса: риски каждые 5°, крупнее каждые 15°, стороны света буквами, курс под центром.
## Север — -Z мира (как на плане: docs/plans), восток — +X.
class Compass extends Control:
	const LETTERS := {0: "С", 45: "СВ", 90: "В", 135: "ЮВ", 180: "Ю", 225: "ЮЗ", 270: "З", 315: "СЗ"}
	var heading: float = 0.0
	## Точки эвакуации: [курс°, расстояние, заперта].
	var marks: Array = []
	var _marks_sig: String = ""


	func set_marks(m: Array) -> void:
		var sig := ""
		for k in m:
			sig += "%d,%d,%s;" % [int(k[0]), int(float(k[1]) / 5.0), k[2]]
		if sig != _marks_sig:
			_marks_sig = sig
			marks = m
			queue_redraw()

	## Курс по направлению взгляда камеры (горизонтальная проекция -Z базиса).
	func set_heading(b: Basis) -> void:
		var f := -b.z
		f.y = 0.0
		if f.length() < 0.001:
			f = b.y
			f.y = 0.0
		var h := fposmod(rad_to_deg(atan2(f.x, -f.z)), 360.0)
		if absf(h - heading) > 0.05:
			heading = h
			queue_redraw()

	func _draw() -> void:
		var w := size.x
		var cx := w * 0.5
		var span := Balance.COMPASS_SPAN_DEG
		var ppd := w * 0.5 / span
		var font := ThemeDB.fallback_font
		var base_y := 16.0
		draw_line(Vector2(0, base_y), Vector2(w, base_y), Color(1, 1, 1, 0.18), 1.0)
		var start := int(floor((heading - span) / 5.0)) * 5
		for deg in range(start, int(heading + span) + 5, 5):
			var off := float(deg) - heading
			if absf(off) > span:
				continue
			var x := cx + off * ppd
			var fade := 1.0 - pow(absf(off) / span, 2.0)
			var d := posmod(deg, 360)
			var col := Color(0.92, 0.9, 0.84, 0.85 * fade)
			if LETTERS.has(d):
				var txt: String = LETTERS[d]
				var fs := 18 if d % 90 == 0 else 14
				var tw := font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
				draw_line(Vector2(x, base_y - 6), Vector2(x, base_y + 6), col, 2.0)
				draw_string_outline(font, Vector2(x - tw * 0.5, base_y + 26), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 4, Color(0, 0, 0, 0.6 * fade))
				draw_string(font, Vector2(x - tw * 0.5, base_y + 26), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
			elif d % 15 == 0:
				draw_line(Vector2(x, base_y - 5), Vector2(x, base_y + 5), col, 1.5)
			else:
				draw_line(Vector2(x, base_y - 2), Vector2(x, base_y + 3), Color(col, col.a * 0.6), 1.0)
		# точки эвакуации: зелёный треугольник (запертая — серый контур) и расстояние; за краем
		# шкалы — прижата к краю
		for m in marks:
			var off := wrapf(float(m[0]) - heading, -180.0, 180.0)
			var edge := absf(off) > span
			var mx := cx + clampf(off, -span, span) * ppd
			var locked := bool(m[2])
			var green := Color(0.35, 0.95, 0.5, 0.95)
			var grey := Color(0.75, 0.75, 0.72, 0.8)
			var tri := PackedVector2Array([Vector2(mx, base_y - 9), Vector2(mx + 7, base_y + 4), Vector2(mx - 7, base_y + 4)])
			if edge:
				var sgn := signf(off)
				tri = PackedVector2Array([Vector2(mx + sgn * 8, base_y), Vector2(mx - sgn * 2, base_y - 7), Vector2(mx - sgn * 2, base_y + 7)])
			if locked:
				var closed := tri.duplicate()
				closed.append(tri[0])
				draw_polyline(closed, grey, 1.6)
			else:
				draw_colored_polygon(tri, green)
			if not edge:
				var ds := "%d м" % int(round(float(m[1])))
				var dw := font.get_string_size(ds, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
				draw_string_outline(font, Vector2(mx - dw * 0.5, base_y - 12), ds, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, 3, Color(0, 0, 0, 0.6))
				draw_string(font, Vector2(mx - dw * 0.5, base_y - 12), ds, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, grey if locked else green)
		# метка центра и курс в градусах
		draw_colored_polygon(PackedVector2Array([Vector2(cx - 5, 0), Vector2(cx + 5, 0), Vector2(cx, 7)]), Color(1, 0.85, 0.5, 0.95))
		var hs := "%03d" % (int(round(heading)) % 360)
		var hw := font.get_string_size(hs, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
		draw_string(font, Vector2(cx - hw * 0.5, base_y + 44), hs, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 0.85, 0.5, 0.8))


func _update_hud(pl: Player) -> void:
	if pl == null or not pl.is_local() or not pl.combat_enabled:
		_weapon_label.text = ""
		return
	if pl.weapon_id == "":
		_weapon_label.text = "без оружия      гранаты × %d" % pl.grenade_count()
		return
	var spec := pl.spec()
	if spec.is_empty():
		_weapon_label.text = ""
		return
	# сколько в магазине — не видно: держать R — проверить (итог — несколько секунд)
	var t := "%s   маг. %d %s" % [String(spec.name), int(spec.mag), String(ItemDb.item(String(spec.ammo)).get("short", ""))]
	if pl.ammo_check_t > 0.0:
		t += "   [%s]" % pl.ammo_check_text
	if pl.loadout_mode:
		t += "   · запасных маг. %d, россыпью %d" % [pl.spare_mags(), pl.loose_rounds()]
	if (spec.sights as Array).size() > 1:
		t += "   [%s]" % ("угловой" if String(spec.sight) == "offset" else "основной")
	if pl.light_on:
		t += "   СВЕТ"
	if pl.laser_on:
		t += "   ЛЦУ"
	if pl.is_jammed():
		t += "   ЗАДЕРЖКА (%s)" % PauseMenu.key_name("reload")
	if pl.reload_timer > 0.0:
		t = "%s   перезарядка…" % String(spec.name)
	_weapon_label.text = t + "      гранаты × %d" % pl.grenade_count()


# ---------------------------------------------------------------- лучи из курсора

## Тело под курсором (мародёр/мишень): луч из камеры сквозь курсор. Пусто — если под курсором пол/стена.
func _body_under_cursor() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * 200.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DOOR)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty() or not ((hit.collider as Node).is_in_group("marauders") or (hit.collider as Node).is_in_group("shootable")):
		return Vector3.ZERO
	return hit.position


## Пересечение луча из курсора с плоскостью пола игрока (y = высота цели).
func cursor_on_ground() -> Vector3:
	var vp := get_viewport()
	if vp == null or _target == null:
		return Vector3.ZERO
	var mouse := vp.get_mouse_position()
	var from := _camera.project_ray_origin(mouse)
	var dir := _camera.project_ray_normal(mouse)
	var plane := Plane(Vector3.UP, _target.global_position.y)
	var hit: Variant = plane.intersects_ray(from, dir)
	if hit == null:
		return _target.global_position
	return hit
