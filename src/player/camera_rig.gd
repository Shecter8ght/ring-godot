class_name CameraRig
extends Node3D
## Камера от первого лица: мышь водит взглядом, ПКМ подводит оружие к глазам без изменения
## обзора мира. Колесо в ADS меняет кратность регулируемой оптики. Вид сверху, вращение и
## дистанция изометрии сохранены для инструментов съёмки и разведдрона.
## Оптика (штатная у винтовки, 4× на планке) — отдельный рендер: вторая камера с узким полем
## зрения рисует в свою текстуру, текстура ложится ровно на окуляр модели (проекция линзы на экран),
## остальной экран — обычный вид из глаз. Сетка и тень по краю — шейдером окуляра.
## Эргономика ствола (WeaponStats): «довод» в прицел и раскачка прицела.

@export var target_path: NodePath

var ads_active: bool = false
## Игра только от первого лица (решение владельца 2026-10-07): камера всегда в глазах, ПКМ — прицел.
## Вид сверху остаётся только у инструментов съёмки и будущего разведдрона (docs/design/drone.md).
static var first_person_mode: bool = true
static var _settings_loaded: bool = false
const SETTINGS_PATH := "user://settings.cfg"
## Вес тела в камере: покачивание в темп шагов, инерция, крен, приземление — отдельный слой поверх
## взгляда мышью (CameraMotion); и покачивание оружия у бедра в той же фазе.
var _motion: CameraMotion = CameraMotion.new()
## Стойка «наискосок» (Balance.WEAPON_CARRY): доля позы 0–1 (меньше нуля — ещё не задана: встаёт сразу)
## и её скорость; поза ствола по id (класс + своё из data/weapons.json).
var _carry_k: float = -1.0
var _carry_v: float = 0.0
var _carry_specs: Dictionary = {}
## Правая кисть на процедурном стволе (RightGrip): вокруг неё ствол поворачивается, руки дотягиваются ИК.
var _carry_grip: Node3D
var _distance: float = Balance.CAMERA_DISTANCE
var _target: Node3D
var _shake: float = 0.0
var _hurt: HurtFx
## толчок взгляда от попадания: (кивок, крен), рад; _punch_t — 1 → 0
var _punch: Vector2 = Vector2.ZERO
## Люфт оружия: где было направление взгляда кадр назад и на сколько оружие сейчас отстаёт (в осях камеры).
var _lag_prev: Basis = Basis.IDENTITY
var _lag_q: Quaternion = Quaternion.IDENTITY
## Люфт, применённый к модели в этом кадре (с долей «от бедра»): от него считается своя инерция метки.
var _lag_used: Quaternion = Quaternion.IDENTITY
## Дыхание в прицеле: фаза вдоха-выдоха.
var _breath_t: float = 0.0
## Отдача в руках: три пружины (x — увод вбок, y — подброс ствола, z — толчок назад) и их скорости;
## _kick_seen — толчок игрока на прошлом кадре (новый выстрел — скачок вверх).
var _hand_kick: Vector3 = Vector3.ZERO
var _hand_kick_v: Vector3 = Vector3.ZERO
var _kick_seen: float = 0.0
var _lag_ready: bool = false
var _punch_t: float = 0.0
var _hitmarker: Control
## Ранен: кровь по краям, блёклые цвета, стук сердца, звук глуше; лёжа — надпись с таймером.
var _hurt_fx: ColorRect
var _hurt_amount: float = 0.0
## Стресс на экране (плавно за Player.stress_k).
var _stress_fx: float = 0.0
var _beat_t: float = 0.0
var _down_label: Label
## ПНВ: зелёная усиленная картинка с зерном.
var _nvg_fx: ColorRect
## Новый снимок экрана сразу после ПНВ: эффекты ранения и стресса рисуются следом и тоже читают экран.
## Без него они получали кадр ДО ПНВ и закрашивали зелёную картинку — в бою фильтр «пропадал».
var _nvg_copy: BackBufferCopy
## Выносливость — тонкая полоса внизу, пока не полная.
var _stamina_bar: ProgressBar
var _hitmarker_t: float = 0.0
var _rng := RandomNumberGenerator.new()
var _mmb: bool = false
var _look_yaw: float = 0.0
var _look_pitch: float = 0.0
var _ads_cam: Camera3D
## Пространство рук и оружия перед глазами (дочернее камеры): масштаб (k, k, 1) в осях камеры даёт
## им своё поле зрения Balance.FPS_VIEWMODEL_FOV при любом поле зрения мира (см. viewmodel_scale).
## Линия на оси взгляда остаётся на оси — совмещение прицела не сбивается. Всё, что берётся у
## модели в руках в мировых координатах (дуло, луч ствола, ЛЦУ), — в этом же «видимом» пространстве:
## пуля от бедра идёт туда, куда ствол виден на экране.
var _vm_space: Node3D
var _viewmodel: Node3D
var _viewmodel_rig: WeaponRig
var _arms: FirstPersonArms
var _viewmodel_id: String = ""
## Стенд подставляет свой черновик; обычная игра читает только явно сохранённые поправки.
var weapon_pose_preview: bool = false
var weapon_pose_profiles: Dictionary = {}
var _viewmodel_cache: Dictionary = {}
var _warmed_player: int = 0
var _warmed_loadout: bool = false
## Доля визуальной позы сохраняется при отпускании ПКМ и быстром повторном нажатии.
var _aim_pose: float = 0.0
var _aim_pose_weapon: String = ""
var weapon_clearance: WeaponClearance = WeaponClearance.new()
## Приклад и затыльник модели в руках: у бедра видны, в прицеле (под щекой) — прячутся.
var _cheek_parts: Array[GeometryInstance3D] = []
## Оптика: своя камера в своей текстуре и окно на экране поверх окуляра.
var scope_active: bool = false
## Ночной режим окна голографа ЛУМАР (кнопка NV, включается в окне настройки прицела — SightMenu).
var sight_nv: bool = false
var _sight_menu: SightMenu
var _sight_menu_frame: int = -1
var _sight_parts_of: int = 0
var _sight_reticles: Array[MeshInstance3D] = []
var _sight_lenses: Array[MeshInstance3D] = []
## Плавный переход между линиями основного, углового и боковых прицелов.
var _sight_k: float = 1.0
var _sight_mode: String = ""
var _sight_pose: Vector3 = Vector3.ZERO
var _sight_from: Vector3 = Vector3.ZERO
var _sight_to: Vector3 = Vector3.ZERO
var _scope_vp: SubViewport
## Вид «как с камеры»: экспозиция глаза, объектив, зерно, размытие (CameraLook).
var _look: CameraLook
var _scope_cam: Camera3D
var _scope_view: TextureRect
# своя сетка оптики-модели (meta reticle_tex у модели в руках); пусто — общая сетка шейдера
var _scope_reticle: String = ""
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
	_vm_space = Node3D.new()
	_vm_space.name = "ViewmodelSpace"
	_ads_cam.add_child(_vm_space)
	# руки и оружие у лица — свой слабый свет, только им (слой 2), мир им не освещён: в темноте силуэт
	# ствола и перчаток читается, днём рядом с солнцем и небом его не видно (Balance.VIEWMODEL_FILL)
	var vf: Dictionary = Balance.VIEWMODEL_FILL
	var fill := DirectionalLight3D.new()
	fill.name = "ViewmodelFill"
	fill.set_meta("own", true)
	fill.light_cull_mask = 2
	fill.shadow_enabled = false
	# сила — по темноте вокруг (CameraLook); пока — дневная
	fill.light_energy = float(vf.energy) * float(vf.day_k)
	fill.light_color = vf.color
	fill.light_specular = float(vf.specular)
	fill.light_volumetric_fog_energy = 0.0
	fill.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	fill.rotation_degrees = Vector3(float(vf.pitch), float(vf.yaw), 0.0)
	_ads_cam.add_child(fill)
	_arms = (load("res://scenes/player/first_person_arms.tscn") as PackedScene).instantiate() as FirstPersonArms
	_vm_space.add_child(_arms)
	_build_hud()
	_glare = LightGlare.new()
	_glare.name = "Glare"
	add_child(_glare)
	_hurt = HurtFx.new()
	_hurt.name = "Hurt"
	add_child(_hurt)
	_build_scope()
	_look = CameraLook.new()
	_look.name = "Look"
	add_child(_look)
	_look.setup(_ads_cam, [_camera, _scope_cam])
	# в изометрии отсечения за стенами нет (см. _set_ads)
	get_viewport().use_occlusion_culling = false


## Отдача в прицеле: взгляд уходит вверх (pitch) и вбок (h, плюс — вправо) — навсегда, тянуть мышью.
func add_recoil(pitch: float, h: float) -> void:
	_look_pitch = clampf(_look_pitch + pitch, -Balance.ADS_PITCH_LIMIT, Balance.ADS_PITCH_LIMIT)
	_look_yaw -= h


## Толчок камеры (выстрел, попадание по тебе, взрыв); складывается и затухает сам.
## Своё попадание: виньетка по краям и резкий толчок взгляда (кивок и крен в случайную сторону),
## без направления — откуда стреляли, слышно.
func hurt(amount: float) -> void:
	var f: Dictionary = Balance.HURT_FX
	if _hurt:
		_hurt.hit(amount)
	var deg := minf(float(f.punch_deg) + amount * float(f.per_dmg_deg), float(f.punch_max_deg))
	_punch = Vector2(deg_to_rad(deg) * _rng.randf_range(0.6, 1.0), deg_to_rad(deg) * _rng.randf_range(-1.0, 1.0))
	_punch_t = 1.0


func add_shake(amount: float) -> void:
	_shake = minf(_shake + amount, 1.0)


## Крестик у курсора (в прицеле — по центру): попал; kill — крупнее и красный.
func show_hitmarker(kill: bool) -> void:
	if not Settings.hitmarker:
		return
	_hitmarker_t = Balance.HITMARKER_SEC * (1.6 if kill else 1.0)
	_hitmarker.modulate = Color(1.0, 0.25, 0.2) if kill else Color(1, 1, 1)
	_hitmarker.scale = Vector2.ONE * (1.5 if kill else 1.0)


## Настройка убирает уже показанное попадание даже при открытом меню и остановленном мире.
func clear_hitmarker() -> void:
	_hitmarker_t = 0.0
	if is_instance_valid(_hitmarker):
		_hitmarker.visible = false


## Точка, из которой «смотрит» игрок: для силы тряски от взрыва и т.п.
func focus_point() -> Vector3:
	if ads_active:
		return _ads_cam.global_position
	return _target.global_position if _target else global_position


func set_target(node: Node3D) -> void:
	_target = node


## Первый вид из глаз и обе модели оружия готовятся, пока мир ещё закрыт экраном загрузки.
func prepare_for_play() -> void:
	_process(0.0)


static func load_settings() -> void:
	if _settings_loaded:
		return
	_settings_loaded = true
	# тесты и инструменты (res://tools/…) — всегда с умолчаниями, настройки игрока их не трогают
	for a in OS.get_cmdline_args():
		if String(a).begins_with("res://tools/"):
			return
	# прежняя настройка вида (изометрия) больше не читается: вид всегда из глаз
	first_person_mode = true


## Только для инструментов съёмки и тестов: игроку вид не переключается.
static func set_first_person_mode(on: bool) -> void:
	first_person_mode = on


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
// в ПНВ картинка и так одноцветная (зелёный экран трубки): серой её не делаем — иначе «фильтр пропадает»
uniform float nvg = 0.0;
void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	float g = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(c, vec3(g), (amount * 0.75 + stress * 0.3) * (1.0 - nvg));
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
		sm.set_shader_parameter("nvg", 1.0 if pl.nvg_on else 0.0)
	_down_label.visible = down
	if down:
		var h := pl.health
		var lines := "ТЯЖЁЛОЕ РАНЕНИЕ — истекаешь кровью: %d с   ·   ранение %d из %d" % [int(ceil(h.bleed_t)), h.downs, Balance.DOWN_MAX]
		var dragger: Player = Raid.current.dragger_of(pl.peer_id) if Raid.current else null
		if dragger:
			lines += "\nТЕБЯ ТАЩАТ — стреляй из пистолета, прикрывай"
		lines += "\n%s — аптечка (подняться) / бинт   ·   %s (держать) — сдаться" % [PauseMenu.key_name("use_med"), PauseMenu.key_name("drag")]
		_down_label.text = lines


## Голограф ЛУМАР в руках: клавиша «sight_menu» открывает окно настройки (форма, цвет, толщина метки,
## ночной режим окна); каждый кадр метке и стеклу ставятся выбранные параметры. Под ПНВ на голове метка
## тускнеет, а стекло перестаёт бликовать — через окно видно; ночной режим окна (sight_nv) рисует в
## стекле усиленную зелёную картинку (lumar_glass.gdshader).
func _tick_sight(pl: Player) -> void:
	if pl == null or not pl.is_local() or _viewmodel == null or not is_instance_valid(_viewmodel):
		return
	if _sight_parts_of != _viewmodel.get_instance_id():
		_sight_parts_of = _viewmodel.get_instance_id()
		_sight_reticles.clear()
		_sight_lenses.clear()
		for mi: Node in _viewmodel.find_children("*", "MeshInstance3D", true, false):
			if mi.has_meta("lumar_reticle"):
				_sight_reticles.append(mi as MeshInstance3D)
			elif mi.has_meta("lumar_lens"):
				_sight_lenses.append(mi as MeshInstance3D)
	if Input.is_action_just_pressed("sight_menu") and not _ui_blocking() and not UiTheme.typing() \
			and (_sight_menu == null or not _sight_menu.is_open()) and Engine.get_process_frames() != _sight_menu_frame:
		if _sight_reticles.is_empty():
			if Raid.current:
				Raid.current.notify("На оружии в руках нет прицела с настройкой метки (нужен ЛУМАР H1)")
		else:
			if _sight_menu == null:
				_sight_menu = SightMenu.new()
				_sight_menu.rig = self
				add_child(_sight_menu)
			_sight_menu.open()
	if _sight_menu and _sight_menu.is_open():
		_sight_menu_frame = Engine.get_process_frames()
		# сменили ствол при открытом окне — закрыть
		if _sight_reticles.is_empty():
			_sight_menu.close_ui()
	var head_nvg: bool = pl.nvg_on
	for mesh: MeshInstance3D in _sight_reticles:
		if is_instance_valid(mesh):
			mesh.scale = Vector3.ONE
			WeaponMods.apply_reticle(mesh, float(Balance.LUMAR.nvg_energy) if head_nvg else 1.0)
	for lens: MeshInstance3D in _sight_lenses:
		var glass: ShaderMaterial = lens.material_override as ShaderMaterial if is_instance_valid(lens) else null
		if glass:
			glass.set_shader_parameter("head_nvg", 1.0 if head_nvg else 0.0)
			# с ПНВ на голове ночной режим окна не нужен: трубка усилила бы его до белого пятна
			glass.set_shader_parameter("window_nv", 1.0 if sight_nv and not head_nvg else 0.0)
			glass.set_shader_parameter("nv_gain", float(Balance.LUMAR.nv_gain))
			glass.set_shader_parameter("nv_ir_range", float(Balance.LUMAR.nv_ir_range))


## Точка коллиматора / голографа в руках: в ПНВ крупнее (в трубке тонкая точка теряется).
func _reticle_nv(on: bool) -> void:
	if _viewmodel == null:
		return
	for mi in _viewmodel.find_children("*", "MeshInstance3D", true, false):
		if mi.has_meta("lumar_reticle"):
			# метка ЛУМАРа — шейдер: в трубке не раздувается, а тускнеет (_tick_sight)
			continue
		if mi.has_meta("reticle_dot"):
			(mi as MeshInstance3D).scale = Vector3.ONE * (Balance.NVG_RETICLE_SCALE if on else 1.0)
			if mi.has_meta("condition_reticle_material"):
				var material: StandardMaterial3D = mi.get_meta("condition_reticle_material") as StandardMaterial3D
				material.emission = Color(0.88, 1.0, 0.9) if on else Color(1.0, 0.04, 0.005)


func _exit_tree() -> void:
	# ушли со сцены в ПНВ — точка прицелов снова красная (материал общий, переживает сцену)
	WeaponModels.set_night_vision(false)


## Дистанция изометрии (зум): в тесном убежище ближе, чем в рейде.
func set_distance(d: float) -> void:
	_distance = clampf(d, Balance.CAMERA_ZOOM_MIN, Balance.CAMERA_ZOOM_MAX)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_MIDDLE:
			_mmb = mb.pressed
			# от первого лица СКМ — основной / угловой прицел (камеру она там не крутит)
			if mb.pressed and ads_active and not _ui_blocking():
				var pl := _target as Player
				if pl and pl.is_local():
					pl.toggle_sight()
		elif mb.pressed and ads_active and not _ui_blocking() \
				and mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var pl: Player = _target as Player
			var wheel := 1 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else -1
			# в прицеле — кратность оптики; без прицела — стойка оружия (вверх — от бедра, вниз — наискосок)
			if pl and (pl.adjust_scope_zoom(wheel) or pl.wheel_carry(wheel)):
				get_viewport().set_input_as_handled()
		elif mb.pressed and not ads_active:
			if mb.button_index == MOUSE_BUTTON_WHEEL_UP:
				_distance = maxf(Balance.CAMERA_ZOOM_MIN, _distance - Balance.CAMERA_ZOOM_STEP)
			elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				_distance = minf(Balance.CAMERA_ZOOM_MAX, _distance + Balance.CAMERA_ZOOM_STEP)
	elif event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		var inspecting := _target as Player
		if inspecting and inspecting.mag_inspect and inspecting.is_local() and not _ui_blocking():
			# держит магазин перед глазами: мышь поворачивает кисть с магазином, взгляд стоит
			var turn_k: float = float(Balance.AMMO_CHECK.turn_sens)
			inspecting.inspect_turn = Vector2(clampf(inspecting.inspect_turn.x + mm.relative.x * turn_k, -1.0, 1.0),
				clampf(inspecting.inspect_turn.y + mm.relative.y * turn_k, -1.0, 1.0))
		elif ads_active and not _ui_blocking():
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
	_warm_weapon_models(pl)
	# режим от первого лица (V) — и в рейде, и в убежище (в том числе сидя на диване)
	var want_ads := pl != null and pl.is_local() and pl.is_alive() and (pl.aiming or first_person_mode)
	if want_ads != ads_active:
		_set_ads(want_ads, pl)
	_shake = maxf(0.0, _shake - Balance.SHAKE_DECAY * _shake * delta - 0.01 * delta)
	var s := _shake * _shake * 4.0
	_hitmarker_t = maxf(0.0, _hitmarker_t - delta) if Settings.hitmarker else 0.0
	_hitmarker.visible = Settings.hitmarker and _hitmarker_t > 0.0
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
	_tick_sight(pl)
	if _nvg_fx:
		var on := pl != null and pl.is_local() and pl.nvg_on
		if on != _nvg_fx.visible:
			_nvg_env(on)
			WeaponModels.set_night_vision(on)
			_reticle_nv(on)
		_nvg_fx.visible = on
		_nvg_copy.visible = on
		_tick_nvg_ir(on)
	var cam := get_viewport().get_camera_3d()
	if _glare:
		_glare.tick(cam, pl if pl and pl.is_local() else null, ads_active, pl != null and pl.is_local() and pl.nvg_on, delta)
	if cam:
		_compass.set_heading(cam.global_basis)
	_compass.set_marks(_extraction_marks(pl))
	_compass.set_mates(_mate_marks(pl))


## Напарники для компаса: [курс°, расстояние м, ник]. Ушедшие и погибшие — нет.
func _mate_marks(pl: Player) -> Array:
	var out: Array = []
	if pl == null or not pl.is_local() or not Net.is_networked():
		return out
	for p in get_tree().get_nodes_in_group("players"):
		var o := p as Player
		if o == null or o == pl or not o.is_alive() or (Raid.current and Raid.current.has_left(o.peer_id)):
			continue
		var d := o.global_position - pl.global_position
		var bearing := fposmod(rad_to_deg(atan2(d.x, -d.z)), 360.0)
		out.append([bearing, Vector2(d.x, d.z).length(), String(Net.player_names.get(o.peer_id, "Напарник"))])
	return out


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

## Подготовить оба слота до первого переключения; в песочнице — автомат и пистолет.
func _warm_weapon_models(pl: Player) -> void:
	if pl == null or not pl.is_local():
		return
	if _warmed_player == pl.get_instance_id() and _warmed_loadout == pl.loadout_mode:
		return
	if pl.loadout_mode and not pl.inventory.loadout_ready:
		return
	var prepared: bool = false
	for key: Variant in pl.weapon_keys().slice(0, 2):
		var entry: Dictionary = pl.entry_of(String(key))
		if entry.is_empty():
			continue
		prepared = true
		pl.prepare_weapon_model(entry)
		_cached_viewmodel(String(entry.id), entry.get("mods", {}), WeaponCondition.percent(entry), WeaponMods.mag_state(entry), WeaponMark.marks(entry))
	if prepared:
		_warmed_player = pl.get_instance_id()
		_warmed_loadout = pl.loadout_mode


## Сборка живёт под камерой до вытеснения из ограниченного кэша; скрытые узлы не обрабатываются.
func _cached_viewmodel(id: String, mods: Dictionary, dur: float, mag: String, marks: Dictionary) -> Node3D:
	var key: String = WeaponCondition.model_key(id, mods, dur, mag) + "|" + WeaponMark.key(marks)
	var model: Node3D = _viewmodel_cache.get(key) as Node3D
	if model == null:
		if id == "grenade":
			model = GrenadeModel.create(true)
		elif (Balance.THROWN_LIGHTS as Dictionary).has(id):
			model = ThrownLight.held_model(id, false)
		elif ViewmodelClips.available(id):
			model = ViewmodelClips.create(id, mods)
			WeaponMark.attach(model, id, marks)
		else:
			model = WeaponModels.build(id, mods, 0, dur, mag, marks) if id != "" else Node3D.new()
		WeaponCondition.apply_visual(model)
		for child: Node in model.find_children("*", "GeometryInstance3D", true, false):
			var mesh: GeometryInstance3D = child as GeometryInstance3D
			mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			mesh.layers = 2
		for child: Node in model.find_children("Flashlight*", "SpotLight3D", true, false):
			child.set_meta("own", true)
			child.set_meta("vm_local", (child as Node3D).transform)
			(child as SpotLight3D).shadow_caster_mask = 0xFFFFF & ~Player.OWN_BODY_LAYER
		model.visible = false
		model.process_mode = Node.PROCESS_MODE_DISABLED
		_vm_space.add_child(model)
	_viewmodel_cache.erase(key)
	_viewmodel_cache[key] = model
	while _viewmodel_cache.size() > Balance.WEAPON_VISUAL_CACHE:
		var oldest: String = String(_viewmodel_cache.keys()[0])
		(_viewmodel_cache[oldest] as Node3D).queue_free()
		_viewmodel_cache.erase(oldest)
	return model


func _set_ads(on: bool, pl: Player) -> void:
	ads_active = on
	if not on:
		_aim_pose = 0.0
		_aim_pose_weapon = ""
	if not on and _look:
		_look.aim_k = 0.0
	if pl:
		pl.ads = on
		pl.set_first_person(on)
	_motion.reset()
	# стойка оружия встаёт сразу в выбранную (без «падения» ствола при входе в вид из глаз)
	_carry_k = -1.0
	if pl:
		pl.weapon_lowered = 0.0
	if on:
		# взгляд — туда, куда уже смотрит корпус; по вертикали — горизонт
		_look_yaw = pl.body_yaw()
		_look_pitch = 0.0
		_ads_cam.fov = Settings.fps_fov_v()
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
	var wid: String = pl.held_model_id()
	var spec: Dictionary = pl.spec() if pl.weapon_id != "" and not pl.grenade_equipped else {}
	# с завалом в оптику не смотрят: вид и чувствительность — как с открытым прицелом
	var scoped := bool(spec.get("scoped", false)) and not pl.aim_cant
	# ПКМ подводит оружие к глазам; поле зрения мира остаётся выбранным в настройках.
	if _aim_pose_weapon != wid:
		_aim_pose_weapon = wid
		_aim_pose = 0.0
	var pose_time: float = float(spec.get("aim_time", Balance.AIM_TIME_FAST)) if pl.aiming else Balance.ADS_LOWER_TIME
	_aim_pose = move_toward(_aim_pose, 1.0 if pl.aiming and wid != "" else 0.0, delta / pose_time)
	var aim_t: float = _aim_pose
	_look.aim_k = aim_t
	_look.iron = not scoped
	_ads_cam.fov = Settings.fps_fov_v()
	# руки и оружие — со своим полем зрения, сколько бы ни было у мира
	var vk := viewmodel_scale(_ads_cam.fov)
	_vm_space.transform = Transform3D(Basis.from_scale(Vector3(vk, vk, 1.0)), Vector3.ZERO)
	# раскачка — по эргономике и стойке; на сошках (сидя/лёжа) почти нет
	_sway_t += delta
	var amp := float(spec.get("sway", 0.0)) * float(Balance.SWAY_STANCE.get(pl.stance_key(), 1.0)) * lerpf(0.4, 1.0, aim_t)
	amp *= lerpf(1.0, Balance.ADS_SWAY_SCALE, aim_t)
	# стресс — руки ходят сильнее
	amp *= 1.0 + float(Balance.STRESS.sway_k) * pl.stress_k()
	if pl.stance != Player.Stance.STAND:
		amp *= float(spec.get("braced_spread", 1.0))
	if pl.is_downed():
		amp *= Balance.DOWN_SWAY
	var sway := Vector2(sin(_sway_t * 1.13) * 0.7 + sin(_sway_t * 2.71 + 1.3) * 0.3, sin(_sway_t * 0.87 + 0.5) * 0.6 + sin(_sway_t * 2.05) * 0.4) * amp
	# дыхание: в прицеле линия медленно ходит вверх-вниз с дрейфом вбок; устал, стресс — сильнее,
	# сидя и лёжа — слабее, задержал дыхание — почти стоит (Player.breath_k)
	var br: Dictionary = Balance.BREATH
	_breath_t += delta * TAU / float(br.period)
	if pl.aiming and wid != "":
		var breath_amp: float = deg_to_rad(float(br.deg)) * pl.breath_k() * float(Balance.SWAY_STANCE.get(pl.stance_key(), 1.0)) * aim_t
		sway += Vector2(sin(_breath_t * 0.5 + 0.7) * float(br.side), sin(_breath_t)) * breath_amp
	# вес тела: шаги, инерция, крен — своим слоем, поверх взгляда мышью; ни мышь, ни отдачу не трогает
	_motion.update(pl, delta, aim_t, _look_yaw)
	# отдача подкидывает взгляд, дальше игрок сам возвращает прицел
	var pitch := _look_pitch + pl.recoil() + sway.y + _motion.pitch
	var yaw := _look_yaw + sway.x - pl.recoil_h() + _motion.yaw
	# наклон — крен камеры (глаз уже сдвинут в eye_position)
	var roll := -pl.lean * deg_to_rad(Balance.LEAN_ROLL_DEG) + _motion.roll
	# попадание: взгляд дёрнулся и вернулся
	if _punch_t > 0.0:
		_punch_t = maxf(0.0, _punch_t - delta / float(Balance.HURT_FX.punch_sec))
		var pk := _punch_t * _punch_t
		pitch += _punch.x * pk
		roll += _punch.y * pk
	# глаз — плавно между тиками физики (Player.view_eye) и со сдвигом от шагов и инерции
	_ads_cam.global_transform = Transform3D(Basis.from_euler(Vector3(pitch, yaw + PI, roll)), pl.view_eye())
	_ads_cam.global_position += _ads_cam.global_basis * (_motion.offset + Vector3(_rng.randf_range(-s, s), _rng.randf_range(-s, s), 0.0) * 0.15)
	# пули летят туда, куда смотрит прицел, — с раскачкой и покачиванием шага
	pl.look_yaw = yaw
	# пули летят туда, куда сейчас смотрит ствол: с отдачей и раскачкой
	pl.look_pitch = pitch
	# модель в руках с обвесами: линия прицеливания на оси взгляда, рукоять — на ads_z перед глазом
	var vm_key := WeaponCondition.model_key(wid, pl.weapon_mods, pl.weapon_condition, pl.weapon_mag) + "|" + WeaponMark.key(pl.weapon_engraving)
	if _viewmodel_id != vm_key:
		if _viewmodel:
			_viewmodel.visible = false
			_viewmodel.process_mode = Node.PROCESS_MODE_DISABLED
		_viewmodel = _cached_viewmodel(wid, pl.weapon_mods, pl.weapon_condition, pl.weapon_mag, pl.weapon_engraving)
		_viewmodel.process_mode = Node.PROCESS_MODE_INHERIT
		if _viewmodel is ViewmodelClips:
			(_viewmodel as ViewmodelClips).equip()
		_cheek_parts.clear()
		for mi in _viewmodel.find_children("*", "GeometryInstance3D", true, false):
			if (mi as GeometryInstance3D).has_meta("hide_ads"):
				_cheek_parts.append(mi as GeometryInstance3D)
		if pl.grenade_equipped:
			_arms.unbind_weapon()
		elif not _viewmodel is ViewmodelClips:
			_arms.bind_weapon(_viewmodel)
		weapon_clearance.bind(_viewmodel)
		_carry_grip = null if _viewmodel is ViewmodelClips else _viewmodel.find_child("RightGrip", true, false) as Node3D
		_viewmodel_rig = WeaponRig.find_on(_viewmodel)
		if _viewmodel_rig:
			_viewmodel_rig.set_ammo_state(pl.ammo)
		_viewmodel_id = vm_key
		_sight_mode = ""
		_reticle_nv(pl.nvg_on)
	_viewmodel.visible = true
	if pl.grenade_equipped:
		pl.weapon_lowered = 0.0
		_process_grenade_viewmodel(pl, delta)
		_set_scope(false)
		return
	WeaponMods.update_condition(_viewmodel, pl.weapon_mods)
	for n in _viewmodel.find_children("LaserBeam*", "Node3D", true, false):
		(n as Node3D).visible = Player.tac_on(pl.weapon_mods, n, "laser")
	for n in _viewmodel.find_children("Flashlight*", "SpotLight3D", true, false):
		(n as SpotLight3D).visible = Player.tac_on(pl.weapon_mods, n, "light")
	var az: float = _viewmodel.get_meta("ads_z", 0.25)
	var line: Vector3 = _aim_line(_viewmodel, "cant" if pl.aim_cant else String(spec.get("sight", "primary")), delta)
	var sx: float = line.x
	var sh: float = line.y
	var sroll: float = line.z
	# Подъём по эргономике и опускание идут от текущей доли позы, без сброса на отпускании ПКМ.
	var k := smoothstep(0.0, 1.0, aim_t)
	# приклад у бедра виден; вскинул к щеке — он под щекой и заслонял бы низ прицельной линии
	for gi in _cheek_parts:
		gi.visible = k < 0.6
	var cant := Basis(Vector3(0, 0, 1), -sroll)
	var ads_pos := -(Basis(Vector3.UP, PI) * cant * Vector3(sx, sh, 0.0)) + Vector3(0.0, 0.0, -az)
	var hip_pos := Balance.FPS_HIP_POSE
	if pl.stance == Player.Stance.PRONE: hip_pos.y += float(Balance.WEAPON_CLEARANCE.prone_hip_lift)
	# На ходу у бедра оружие покачивается в темп шагов (та же фаза, что у камеры, руки чуть позже
	# головы); размах следует реальной скорости — при разгоне и остановке не включается рывком.
	var bob := _motion.weapon_bob * (1.0 - k)
	# камера смотрит по −Z, у модели дуло по +Z — разворот на π; отдача — подброс и откат назад
	# толчок в плечо: модель откатывается назад, дуло подскакивает, чуть заваливается; пружиной обратно
	# в прицеле дуло подскакивает меньше, а оружие сильнее уходит назад, в плечо и камеру
	# отдача в руках — пружинами: толчок назад, подброс, увод вбок, возврат с небольшим перелётом;
	# от бедра оружие гуляет сильнее (взгляд при этом почти стоит — Player._apply_recoil)
	_tick_hand_kick(pl, delta)
	var hip_gain: float = lerpf(float(Balance.HAND_RECOIL.hip_k), 1.0, k)
	var flip := _hand_kick.y * hip_gain * lerpf(1.0, Balance.ADS_RECOIL_FLIP_SCALE, k)
	var kick_back := _hand_kick.z * hip_gain * lerpf(1.0, Balance.ADS_RECOIL_BACK_SCALE, k)
	var kick_side := deg_to_rad(float(Balance.HAND_RECOIL.side_deg)) * _hand_kick.x * hip_gain
	var vm_basis := Basis(Vector3.UP, PI + deg_to_rad(4.0) * (1.0 - k) + kick_side).rotated(Vector3.RIGHT, flip * 0.05).rotated(Vector3.FORWARD, pl.recoil_h() * 1.5 + deg_to_rad(-3.0) * (1.0 - k)) * Basis(Vector3(0, 0, 1), -sroll * k)
	var action_offset: Vector3 = pl._weapon_rig.view_offset() * (1.0 - k) if is_instance_valid(pl._weapon_rig) else Vector3.ZERO
	if is_instance_valid(pl._weapon_rig):
		vm_basis *= Basis.from_euler(pl._weapon_rig.view_rotation_degrees() * (PI / 180.0) * (1.0 - k))
	_viewmodel.transform = Transform3D(vm_basis, hip_pos.lerp(ads_pos, k) + action_offset + bob + Vector3(0.0, flip * 0.004, kick_back * 0.028))
	var clips: ViewmodelClips = _viewmodel as ViewmodelClips
	if clips:
		# сцена уже в осях камеры: у бедра — поза из Blender, в прицеле — линия прицеливания на оси взгляда;
		# поверх — раскачка при ходьбе, подброс и откат при выстреле
		clips.update(pl, delta)
	# Импортированная поза может иметь свои оси: поворачиваем её линию, сохраняя готовые клипы.
	if _viewmodel.has_method("ads_transform") and _viewmodel.has_method("hip_transform"):
		var primary_ads: Transform3D = _viewmodel.call("ads_transform")
		var hip: Transform3D = _viewmodel.call("hip_transform")
		var selected_ads: Transform3D = cant_ads(primary_ads, float(_viewmodel.get_meta("sight_h", 0.08)), line)
		var vt: Transform3D = hip.interpolate_with(selected_ads, k)
		vt.basis = Basis(Vector3.UP, kick_side) * Basis(Vector3.RIGHT, flip * 0.05) * Basis(Vector3.FORWARD, pl.recoil_h() * 1.5) * vt.basis
		vt.origin += bob + Vector3(0.0, flip * 0.004, kick_back * 0.028)
		_viewmodel.transform = vt
	_carry_pose(pl, delta)
	var pose_profiles: Dictionary = weapon_pose_profiles if weapon_pose_preview else WeaponPoseProfiles.active()
	_viewmodel.transform = WeaponPoseProfiles.apply(_viewmodel.transform, pose_profiles, wid, k, maxf(_carry_k, 0.0))
	var before_lag: Transform3D = _viewmodel.transform
	_viewmodel.transform = _weapon_lag(delta, k) * _viewmodel.transform
	_float_reticle(before_lag)
	if _viewmodel_rig:
		if is_instance_valid(pl._weapon_rig):
			_viewmodel_rig.synchronize_from(pl._weapon_rig)
		elif not _viewmodel_rig.is_busy():
			_viewmodel_rig.set_ammo_state(pl.ammo)
	weapon_clearance.refresh_action(_viewmodel, _viewmodel_rig)
	if wid != "":
		# Лёжа отводим ствол вбок: вертикальная поза упирала приклад в пол.
		weapon_clearance.sideways = pl.stance == Player.Stance.PRONE
		var requested: Transform3D = _vm_space.global_transform * _viewmodel.transform
		var corrected: Transform3D = weapon_clearance.solve(get_world_3d(), requested, _ads_cam.global_transform, [pl.get_rid()], delta, 0.0, weapon_clearance.sideways)
		_viewmodel.transform = _vm_space.global_transform.affine_inverse() * corrected
		_viewmodel.visible = weapon_clearance.valid
		pl.weapon_obstruction = weapon_clearance.weight if weapon_clearance.valid else 1.0
		pl.weapon_ready_up = weapon_clearance.ready_up
	else:
		pl.weapon_obstruction = 0.0
	if clips:
		# свои руки уже в сцене клипов — процедурные руки Persona не нужны
		_arms.visible = false
	else:
		if _viewmodel_rig:
			_arms.set_hand_target("Left", _viewmodel_rig.get_hand_target(), _viewmodel_rig.get_hand_weight())
		else:
			_arms.set_hand_target("Left", null, 0.0)
		_arms.collision_exclude = [pl.get_rid()]
		_arms.update_pose()
		if not _arms.arms_clear:
			_viewmodel.visible = false
			pl.weapon_obstruction = 1.0
		_arms.visible = _arms.visible and _viewmodel.visible
	_straighten_lights()
	_set_scope(scoped and _viewmodel.has_meta("ocular") and pl.aiming and aim_t > 0.85 and absf(sroll) < 0.05 and pl.weapon_obstruction <= float(Balance.WEAPON_CLEARANCE.fire_threshold))
	if scope_active:
		# подсветка центра сетки (у оптики с подсветкой) — той же клавишей, что фонарь (T)
		_update_scope(float(spec.get("zoom", 4.0)), pl.light_on and _viewmodel.has_meta("reticle_illum"))


## Стойка «наискосок» (Balance.WEAPON_CARRY): ствол вниз-влево вокруг правой кисти. Бегом — всегда, на ходу
## и стоя — если выбрана колесом (Player.carry_low); в прицеле, лёжа, раненым и пока заняты руки
## (перезарядка, проверка, задержка) — оружие на изготовку. Доля — пружиной, без рывка; сколько опущено —
## в Player.weapon_lowered (стрелять можно, только когда поднято).
func _carry_pose(pl: Player, delta: float) -> void:
	var cfg: Dictionary = Balance.WEAPON_CARRY
	var clips := _viewmodel as ViewmodelClips
	var pose: Dictionary = _carry_spec(pl.weapon_id, clips != null)
	var busy: bool = pl.reload_timer > 0.0 or pl.mag_inspect or (clips != null and clips.is_busy()) \
		or (_viewmodel_rig != null and _viewmodel_rig.is_busy())
	var sprinting: bool = pl.sprint_held() and pl.stance == Player.Stance.STAND \
		and Vector2(pl.velocity.x, pl.velocity.z).length() > Balance.PLAYER_WALK_SPEED + 0.3
	var want: bool = not pose.is_empty() and not pl.aiming and not busy and not pl.is_downed() \
		and pl.stance != Player.Stance.PRONE and (pl.carry_low or sprinting)
	var target: float = 1.0 if want else 0.0
	if _carry_k < 0.0:
		_carry_k = target
		_carry_v = 0.0
	# критически затухающая пружина: трогается плавно и встаёт без перелёта
	var w: float = 4.75 / maxf(float(cfg.lower_sec) if target > _carry_k else float(cfg.raise_sec), 0.01)
	var steps: int = clampi(ceili(delta / 0.004), 1, 12)
	var h: float = delta / float(steps)
	for i in steps:
		_carry_v += (-w * w * (_carry_k - target) - 2.0 * w * _carry_v) * h
		_carry_k += _carry_v * h
	_carry_k = clampf(_carry_k, 0.0, 1.0)
	pl.weapon_lowered = _carry_k
	if _carry_k < 0.0005 or pose.is_empty():
		return
	# поворот в осях камеры: дуло влево, вниз, завал. Процедурный ствол — вокруг точки на pivot_back позади
	# правой кисти (руки дотягиваются ИК); у вьюмодели с клипами руки — одно целое с оружием, её
	# поворачиваем вокруг своей точки (clips_pivot) и мягче — настоящую позу даст хват из Blender
	var full := Basis(Vector3.UP, deg_to_rad(float(pose.yaw_deg))) * Basis(Vector3.RIGHT, -deg_to_rad(float(pose.pitch_deg))) \
		* Basis(Vector3.BACK, deg_to_rad(float(pose.roll_deg)))
	var turn := Basis(Quaternion.IDENTITY.slerp(full.get_rotation_quaternion(), _carry_k))
	var pivot: Vector3 = pose.get("clips_pivot", Vector3.ZERO) as Vector3
	if is_instance_valid(_carry_grip):
		# от кисти назад по оружию (к затыльнику у плеча): приклад остаётся у плеча, а не задирается к лицу
		var along: Vector3 = _viewmodel.global_basis.z.normalized()
		pivot = _vm_space.to_local(_carry_grip.global_position - along * float(pose.get("pivot_back", 0.0)))
	var shift: Vector3 = pose.shift as Vector3
	_viewmodel.transform = Transform3D(turn, pivot + shift * _carry_k - turn * pivot) * _viewmodel.transform


## Поза «наискосок» ствола: по классу (rifle / pistol), у вьюмодели с клипами — поверх своя мягкая
## (clips), и своя у ствола из data/weapons.json ("carry": {…} поверх всего, "carry": false — без позы).
## Пусто — без позы.
func _carry_spec(wid: String, clips: bool) -> Dictionary:
	if wid == "":
		return {}
	var key := carry_key(wid, clips)
	if _carry_specs.has(key):
		return _carry_specs[key]
	var w: Dictionary = WeaponDb.weapon(wid)
	var own: Variant = w.get("carry", {})
	var pose: Dictionary = {}
	if not (own is bool and not bool(own)):
		var cfg: Dictionary = Balance.WEAPON_CARRY
		pose = (cfg.pistol if String(w.get("class", "")) == "PISTOL" else cfg.rifle).duplicate()
		if clips:
			pose.merge(cfg.clips as Dictionary, true)
		if own is Dictionary:
			pose.merge(own as Dictionary, true)
			for k: String in ["shift", "clips_pivot"]:
				if pose.get(k) is Array:
					var a: Array = pose[k]
					pose[k] = Vector3(float(a[0]), float(a[1]), float(a[2]))
	_carry_specs[key] = pose
	return pose


## Ключ позы ствола в кэше (вьюмодель с клипами — своя поза).
static func carry_key(wid: String, clips: bool) -> String:
	return wid + ("|clips" if clips else "")


## Гранату держит отдельный FPS_ArmsRig ВЕРАС-54; поза левой синхронна движению чеки.
func _process_grenade_viewmodel(pl: Player, delta: float) -> void:
	var cfg: Dictionary = Balance.GRENADE_HAND
	var position: Vector3 = cfg.pose
	position += (cfg.pose_charge as Vector3) * pl.grenade_charge
	if pl.grenade_underhand and pl.grenade_pin > 0.0:
		position += cfg.pose_under as Vector3
	var basis: Basis = Basis(Vector3.UP, PI)
	_viewmodel.transform = Transform3D(basis, position)
	_viewmodel.transform = _weapon_lag(delta, 0.0) * _viewmodel.transform
	if _viewmodel is GrenadeModel:
		(_viewmodel as GrenadeModel).prepare(pl.grenade_pin)
	ThrownLight.prepare_held(_viewmodel, pl.grenade_pin)
	_viewmodel.visible = pl.grenade_in_hand
	_arms.visible = false
	pl.weapon_obstruction = 0.0


## Линия выбранного прицела в осях оружия: x, высота, крен. Между любыми двумя — один переход.
func _aim_line(model: Node3D, sight: String, delta: float) -> Vector3:
	var primary: Vector3 = Vector3(0.0, float(model.get_meta("sight_h", 0.08)), 0.0)
	var data: Dictionary = (model.get_meta("sights", {}) as Dictionary).get(sight, {})
	var target: Vector3 = Vector3(float(data.get("x", primary.x)), float(data.get("h", primary.y)), float(data.get("roll", 0.0)))
	if sight == "cant":
		# с завалом: взгляд проходит правее и выше прицельной линии, оружие — затвором к глазам
		var c: Dictionary = Balance.AIM_CANT
		target = Vector3(-float(c.right), primary.y + float(c.up), deg_to_rad(float(c.roll_deg)))
	if _sight_mode == "":
		_sight_pose = primary
		_sight_from = primary
		_sight_to = primary
		_sight_k = 1.0
		_sight_mode = "primary"
	if sight != _sight_mode or not target.is_equal_approx(_sight_to):
		_sight_mode = sight
		_sight_from = _sight_pose
		_sight_to = target
		_sight_k = 0.0
	_sight_k = move_toward(_sight_k, 1.0, delta / Balance.SIGHT_SWITCH_SEC)
	_sight_pose = _sight_from.lerp(_sight_to, smoothstep(0.0, 1.0, _sight_k))
	return _sight_pose


## Люфт оружия: взгляд повернулся (мышь, отдача) — оружие на миг остаётся, где было, и догоняет
## пружиной. Поворот — вокруг глаза, поэтому прицельная линия уходит с оси взгляда: метка коллиматора
## смещается в окне, показываются стенки, мушка расходится с целиком. Только вид: пули летят по взгляду.
## aim_k — доля прицеливания (у бедра люфт слабее, Balance.AIM_LAG.hip_k).
func _weapon_lag(delta: float, aim_k: float) -> Transform3D:
	var cfg: Dictionary = Balance.AIM_LAG
	var now: Basis = _ads_cam.global_basis.orthonormalized()
	if _lag_ready:
		# прошлое направление взгляда в осях нынешней камеры — туда оружие «хочет» остаться
		var back := Quaternion((now.inverse() * _lag_prev).orthonormalized())
		_lag_q = (Quaternion.IDENTITY.slerp(back, float(cfg.share)) * _lag_q).normalized()
	_lag_prev = now
	_lag_ready = true
	_lag_q = _lag_q.slerp(Quaternion.IDENTITY, 1.0 - exp(-float(cfg.follow) * delta))
	var limit: float = deg_to_rad(float(cfg.max_deg))
	if _lag_q.get_angle() > limit:
		_lag_q = Quaternion(_lag_q.get_axis().normalized(), limit)
	_lag_used = Quaternion.IDENTITY.slerp(_lag_q, lerpf(float(cfg.hip_k), 1.0, aim_k))
	return Transform3D(Basis(_lag_used), Vector3.ZERO)


## Своя инерция метки коллиматора: корпус прицела отстал от взгляда на весь люфт, а светящаяся метка —
## только на долю Balance.AIM_LAG.dot_k. Метка плавает в окне и остаётся почти на цели (пули летят по
## взгляду). before — поза модели до люфта (в осях ViewmodelSpace). Метки — сетки с meta "reticle_dot"
## (WeaponMods.fit); место покоя запоминается в meta "dot_rest".
func _float_reticle(before: Transform3D) -> void:
	var keep: float = 1.0 - float(Balance.AIM_LAG.dot_k)
	var moving: bool = _lag_used.get_angle() > 0.00002
	var partial: Transform3D = Transform3D(Basis(Quaternion.IDENTITY.slerp(_lag_used, float(Balance.AIM_LAG.dot_k))), Vector3.ZERO) * before
	var model_inv: Transform3D = _viewmodel.global_transform.affine_inverse()
	for node: Node in _viewmodel.find_children("*", "MeshInstance3D", true, false):
		if not node.has_meta("reticle_dot"):
			continue
		var dot: MeshInstance3D = node as MeshInstance3D
		if not dot.has_meta("dot_rest"):
			dot.set_meta("dot_rest", dot.position)
		var rest: Vector3 = dot.get_meta("dot_rest")
		var parent: Node3D = dot.get_parent() as Node3D
		if not moving or keep <= 0.0 or parent == null:
			dot.position = rest
			continue
		# место метки в осях модели → куда она встала бы при полном люфте и при своём (меньшем)
		var in_model: Transform3D = model_inv * parent.global_transform
		var at: Vector3 = in_model * rest
		var shift: Vector3 = _viewmodel.transform.affine_inverse() * (partial * at) - at
		dot.position = rest + in_model.basis.inverse() * shift


## Отдача в руках: новый выстрел (скачок Player.kick_vis) толкает три пружины — назад в плечо, вверх
## (подброс ствола) и вбок; каждая возвращается с небольшим перелётом (Balance.HAND_RECOIL).
func _tick_hand_kick(pl: Player, delta: float) -> void:
	var cfg: Dictionary = Balance.HAND_RECOIL
	var impulse: float = pl.kick_vis - _kick_seen
	_kick_seen = pl.kick_vis
	var axes: Array = [cfg.side, cfg.rise, cfg.back]
	if impulse > 0.05:
		# скорость такая, чтобы пик пружины был около величины толчка
		var side_sign: float = signf(pl.recoil_h()) if absf(pl.recoil_h()) > 0.0005 else (1.0 if _rng.randf() < 0.5 else -1.0)
		var push := Vector3(side_sign * _rng.randf_range(0.4, 1.0), 1.0, 1.0) * impulse
		for i in range(3):
			_hand_kick_v[i] += push[i] * sqrt(float(axes[i][0])) * 2.0
	# шаг пружин мелкими долями: при просадке кадров не разлетаются
	var steps: int = clampi(int(ceil(delta / 0.004)), 1, 12)
	var h: float = delta / float(steps)
	for s in range(steps):
		for i in range(3):
			var stiff: float = float(axes[i][0])
			var damp: float = 2.0 * float(axes[i][1]) * sqrt(stiff)
			_hand_kick_v[i] += (-stiff * _hand_kick[i] - damp * _hand_kick_v[i]) * h
			_hand_kick[i] += _hand_kick_v[i] * h
	# границы шире на прибавку отдачи: очередь из крупного калибра не должна в них упираться
	var room: float = maxf(float(Balance.RECOIL_GAIN.hip), float(Balance.RECOIL_GAIN.ads))
	_hand_kick = _hand_kick.clamp(Vector3(-2.5, -1.0, -1.0) * room, Vector3(2.5, 3.0, 3.0) * room)


## Готовая поза основного прицела → поза дополнительного, независимо от осей исходной сцены.
## Высота и боковой сдвиг компенсируются до крена: окно остаётся на оси взгляда.
static func cant_ads(primary: Transform3D, primary_h: float, line: Vector3) -> Transform3D:
	var turn: Basis = Basis(Vector3.BACK, line.z)
	var offset: Vector3 = Basis(Vector3.UP, PI) * Vector3(line.x, line.y - primary_h, 0.0)
	return Transform3D(turn * primary.basis, turn * (primary.origin - offset))


## Доля перезарядки, где у клипа рук старый магазин скрылся и сменился новым (−1 — клипов нет).
func reload_swap_fraction(empty: bool) -> float:
	if _viewmodel is ViewmodelClips:
		return (_viewmodel as ViewmodelClips).swap_fraction("reload_empty" if empty else "reload")
	return -1.0


## Действия деталей одинаковы у модели перед глазами и у модели в руке персонажа.
func weapon_action(action: String, flag: bool = false, duration: float = 0.0, rounds: int = -1) -> void:
	if _viewmodel is ViewmodelClips:
		(_viewmodel as ViewmodelClips).weapon_action(action, flag, duration, rounds)
	if not is_instance_valid(_viewmodel_rig):
		return
	match action:
		"shot":
			_viewmodel_rig.play_shot(rounds)
		"reload":
			_viewmodel_rig.play_reload(flag, duration)
		"finish_reload":
			_viewmodel_rig.finish_reload(rounds)
		"suppressor":
			_viewmodel_rig.play_suppressor(flag, duration)
		"suppressed":
			_viewmodel_rig.set_suppressed(flag)
		"cancel":
			_viewmodel_rig.cancel_action()
			_arms.set_hand_target("Left", null, 0.0)


## Фонарь на модели в руках: под масштабом ViewmodelSpace его базис скошен (свет и тень от
## скошенного прожектора считаются неверно) — ставим ровный базис в той же точке, луч — туда, куда
## на экране смотрит фонарь (как ствол и ЛЦУ). Исходное положение у модели — meta "vm_local".
func _straighten_lights() -> void:
	for n in _viewmodel.find_children("Flashlight*", "SpotLight3D", true, false):
		var l := n as SpotLight3D
		if not l.visible or not l.has_meta("vm_local"):
			continue
		var g: Transform3D = (l.get_parent() as Node3D).global_transform * (l.get_meta("vm_local") as Transform3D)
		l.global_transform = Transform3D(Basis.looking_at(-g.basis.z, g.basis.y), g.origin)


## Масштаб ViewmodelSpace по X и Y (в осях камеры) при поле зрения камеры cam_v: модель
## рисуется так, будто у камеры Balance.FPS_VIEWMODEL_FOV.
static func viewmodel_scale(cam_v: float) -> float:
	return tan(deg_to_rad(cam_v) * 0.5) / tan(deg_to_rad(Balance.FPS_VIEWMODEL_FOV) * 0.5)


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
	_scope_cam.keep_aspect = Camera3D.KEEP_HEIGHT
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


## Чувствительность мыши от первого лица: в оптике делится на текущую кратность; пока
## целишься (ПКМ) — свой множитель из настроек.
func ads_sens() -> float:
	var pl := _target as Player
	var aim_k := Settings.sens_ads if pl != null and pl.aiming else 1.0
	# Градусов на отсчёт мыши столько же при любом поле зрения из настроек.
	var s: float = Balance.ADS_SENS * Settings.sens_fps * aim_k * (Balance.FPS_FOV / 62.0)
	return s / maxf(1.0, _scope_zoom) if scope_active else s


## Поле зрения камеры оптики (для проверок).
func scope_fov() -> float:
	return rad_to_deg(2.0 * atan(_scope_cam.size / (2.0 * _scope_cam.near)))


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
	var scope_mat := _scope_view.material as ShaderMaterial
	scope_mat.set_shader_parameter("illum", 1.0 if illum else 0.0)
	# сетка оптики-модели (attach.model.reticle): R — нити, G — что светится с подсветкой; нет — общая
	var reticle_path: String = String(_vm_frame().get_meta("reticle_tex", ""))
	if reticle_path != _scope_reticle:
		_scope_reticle = reticle_path
		var reticle: Texture2D = load(reticle_path) as Texture2D if reticle_path != "" and ResourceLoader.exists(reticle_path) else null
		scope_mat.set_shader_parameter("reticle_tex", reticle)
		scope_mat.set_shader_parameter("reticle_custom", 1.0 if reticle else 0.0)
	# люфт оружия → глаз сошёл с оси прицела: сдвиг картинки, тень с края, искажение
	var lag_cfg: Dictionary = Balance.AIM_LAG
	var lag_euler: Vector3 = Basis(_lag_q).get_euler()
	var lag_k: float = 1.0 / deg_to_rad(float(lag_cfg.max_deg))
	scope_mat.set_shader_parameter("lag", Vector2(clampf(-lag_euler.y * lag_k, -1.0, 1.0), clampf(lag_euler.x * lag_k, -1.0, 1.0)))
	scope_mat.set_shader_parameter("lag_shift", float(lag_cfg.scope_shift))
	scope_mat.set_shader_parameter("lag_shadow", float(lag_cfg.scope_shadow))
	scope_mat.set_shader_parameter("lag_warp", float(lag_cfg.scope_warp))
	var ocular: Vector3 = _vm_frame().to_global(_vm_frame().get_meta("ocular"))
	# окуляр рисуется в ViewmodelSpace — на экране он больше (меньше) в масштаб пространства
	var r := float(_vm_frame().get_meta("ocular_r")) * _vm_space.scale.x
	_scope_cam.global_transform = _ads_cam.global_transform
	var dist := maxf(0.02, _ads_cam.global_position.distance_to(ocular))
	# угол окуляра в основном виде и во сколько раз его «растянуть»
	var half_main := atan(r / dist)
	var main_px_per_rad := get_viewport().get_visible_rect().size.y * 0.5 / tan(deg_to_rad(_ads_cam.fov) * 0.5)
	# Размер ближней плоскости задаёт перспективу без ограничения FOV в 1°: даже дальняя
	# оптика и большая кратность дают нужный масштаб внутри линзы.
	var scope_size: float = 2.0 * _scope_cam.near * tan(half_main) / maxf(1.0, zoom)
	_scope_cam.set_frustum(scope_size, Vector2.ZERO, _scope_cam.near, _scope_cam.far)
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
				# свой свет рук и оружия (ViewmodelFill) — не солнце
				if (l as DirectionalLight3D).visible and not l.has_meta("own"):
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
// своя сетка прицела (ПСО, 4×32): квадрат текстуры — окно окуляра, R — нити, G — светится с подсветкой
uniform sampler2D reticle_tex : filter_linear_mipmap, repeat_disable;
uniform float reticle_custom = 0.0;
// люфт: глаз ушёл с оси прицела (−1…1 по осям окна): картинка сдвигается, с края наползает тень,
// искажение растёт («жидкое стекло»)
uniform vec2 lag = vec2(0.0);
uniform float lag_shift = 0.07;
uniform float lag_shadow = 0.42;
uniform float lag_warp = 0.3;

void fragment() {
	vec2 c = UV - 0.5;
	float r = length(c) * 2.0;
	// Искажение линзы сохраняет масштаб в центре: кратность задаёт камера оптики.
	float off_axis = length(lag);
	float bar = barrel + lag_warp * off_axis;
	vec2 w = c * (1.0 + bar * r * r) / (1.0 + bar * r * r * r * r);
	// поле «плывёт» в сторону люфта, сильнее к краю
	w += lag * lag_shift * (0.35 + r * r);
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
	float glow = step(r, 0.32);
	float reticle = clamp(thin + post, 0.0, 1.0);
	float dot_c = step(length(c), line_w * 2.2);
	if (reticle_custom > 0.5) {
		vec4 rt = texture(reticle_tex, UV);
		reticle = rt.r;
		glow = rt.g;
		dot_c = 0.0;
	}
	vec3 ink = mix(vec3(0.01), illum_color * 2.2, illum * glow);
	col = mix(col, ink, reticle);
	col = mix(col, illum_color * 2.6, illum * dot_c);
	col += illum_color * illum * 0.35 * exp(-length(c) * 60.0);
	col *= smoothstep(1.0, 0.72, r);
	// тень окуляра: тёмный серп с той стороны, куда ушёл глаз
	float shade_r = length(c + lag * lag_shadow) * 2.0;
	col *= mix(1.0, smoothstep(1.0, 0.62, shade_r), clamp(off_axis * 1.6, 0.0, 1.0));
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
	var f := _vm_frame()
	return [f.to_global(f.get_meta("muzzle", Vector3.ZERO)), f.global_basis.z.normalized()]


## Узел, в осях которого заданы метки ствола (дуло, окуляр; дуло по +Z): у вьюмодели с клипами — рама
## обвесов (WeaponFrame у кости оружия), у остальных — сама модель.
func _vm_frame() -> Node3D:
	var clips := _viewmodel as ViewmodelClips
	return clips.frame if clips and is_instance_valid(clips.frame) else _viewmodel


func viewmodel_muzzle() -> Vector3:
	if _viewmodel and _viewmodel.visible:
		var f := _vm_frame()
		return f.to_global(f.get_meta("muzzle", Vector3.ZERO))
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
	_nvg_copy = BackBufferCopy.new()
	_nvg_copy.copy_mode = BackBufferCopy.COPY_MODE_VIEWPORT
	_nvg_copy.visible = false
	layer.add_child(_nvg_copy)
	layer.move_child(_nvg_copy, 1)
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
	# во всю ширину экрана: длинная строка (запасные магазины, прицел, СВЕТ, ЛЦУ) обрезалась слева
	_weapon_label.anchor_left = 0.0
	_weapon_label.anchor_right = 1.0
	_weapon_label.anchor_top = 1.0
	_weapon_label.anchor_bottom = 1.0
	_weapon_label.offset_left = 28.0
	_weapon_label.offset_right = -28.0
	# длинная строка растёт влево — не за край экрана
	_weapon_label.grow_horizontal = Control.GROW_DIRECTION_BEGIN
	_weapon_label.clip_text = false
	_weapon_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
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
	## Напарники: [курс°, расстояние, ник].
	var mates: Array = []
	var _mates_sig: String = ""


	func set_mates(m: Array) -> void:
		var sig := ""
		for k in m:
			sig += "%d,%d,%s;" % [int(k[0]), int(float(k[1])), k[2]]
		if sig != _mates_sig:
			_mates_sig = sig
			mates = m
			queue_redraw()


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
		# напарники: синий ромб, над ним ник и расстояние; за краем шкалы — прижат к краю
		for m in mates:
			var off := wrapf(float(m[0]) - heading, -180.0, 180.0)
			var edge := absf(off) > span
			var mx := cx + clampf(off, -span, span) * ppd
			var blue := Color(0.45, 0.72, 1.0, 0.95)
			draw_colored_polygon(PackedVector2Array([Vector2(mx, base_y - 7), Vector2(mx + 6, base_y), Vector2(mx, base_y + 7), Vector2(mx - 6, base_y)]), blue)
			var ms := String(m[2]) if edge else "%s %d м" % [String(m[2]), int(round(float(m[1])))]
			var mw := font.get_string_size(ms, HORIZONTAL_ALIGNMENT_LEFT, -1, 11).x
			var lx := clampf(mx - mw * 0.5, 0.0, w - mw)
			draw_string_outline(font, Vector2(lx, base_y + 40), ms, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, 3, Color(0, 0, 0, 0.6))
			draw_string(font, Vector2(lx, base_y + 40), ms, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, blue)
		# метка центра и курс в градусах
		draw_colored_polygon(PackedVector2Array([Vector2(cx - 5, 0), Vector2(cx + 5, 0), Vector2(cx, 7)]), Color(1, 0.85, 0.5, 0.95))
		var hs := "%03d" % (int(round(heading)) % 360)
		var hw := font.get_string_size(hs, HORIZONTAL_ALIGNMENT_LEFT, -1, 12).x
		draw_string(font, Vector2(cx - hw * 0.5, base_y + 44), hs, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1, 0.85, 0.5, 0.8))


func _update_hud(pl: Player) -> void:
	if pl == null or not pl.is_local() or not pl.combat_enabled:
		_weapon_label.text = ""
		return
	if pl.grenade_equipped:
		var left: String = "без счёта" if not pl.loadout_mode and pl.throwable_id != "grenade" else "× %d" % pl.throwable_count()
		_weapon_label.text = "%s %s   ·   ЛКМ — верхом   ПКМ — снизу   ·   держать — сильнее" % [pl.throwable_name(), left]
		return
	if pl.weapon_id == "":
		var put_away: String = "без оружия"
		if pl.holstered and pl.weapon_slot != "":
			# убрано повторным нажатием клавиши ствола — подсказать, как достать
			var away: String = String(pl.entry_of(pl.weapon_slot).get("id", ""))
			var slot_n: int = pl.weapon_keys().find(pl.weapon_slot) + 1
			put_away = "%s убрано%s" % [ItemDb.item_name(away) if away != "" else "оружие",
				" (%s — достать)" % PauseMenu.key_name("weapon_%d" % slot_n) if slot_n > 0 and InputMap.has_action("weapon_%d" % slot_n) else ""]
		_weapon_label.text = "%s      гранаты × %d" % [put_away, pl.grenade_count()]
		return
	var spec := pl.spec()
	if spec.is_empty():
		_weapon_label.text = ""
		return
	# сколько в магазине — не видно: держать R — проверить (итог — несколько секунд)
	var t := "%s   маг. %d %s" % [String(spec.name), int(spec.mag), String(ItemDb.item(String(spec.ammo)).get("short", ""))]
	if pl.mag_out():
		t = "%s   без магазина (%s — вставить)" % [String(spec.name), PauseMenu.key_name("reload")]
	# режим огня — у ствола с переводчиком (X — следующий)
	if WeaponDb.fire_modes(pl.weapon_id).size() > 1:
		t += "   [%s]" % String((Balance.FIRE_MODES.labels as Dictionary).get(pl.fire_mode(), ""))
	if pl.ammo_check_t > 0.0:
		t += "   [%s]" % pl.ammo_check_text
	if pl.loadout_mode:
		t += "   · запасных маг. %d, россыпью %d" % [pl.spare_mags(), pl.loose_rounds()]
	if pl.aiming and pl.zero_clicks() != Vector2i.ZERO:
		t += "   [поправка: %s]" % Gear.zero_text(pl.zero_clicks())
	if pl.breath_held:
		t += "   [дыхание задержано]"
	elif pl.breath_gasping():
		t += "   [одышка]"
	if pl.aim_cant:
		t += "   [с завалом]"
	elif (spec.sights as Array).size() > 1:
		t += "   [%s]" % WeaponStats.sight_name(String(spec.sight), pl.weapon_entry()).to_lower()
	if pl.aiming and not pl.aim_cant and bool(spec.scoped):
		t += "   [%.0f×%s]" % [float(spec.zoom), " · колесо" if float(spec.zoom_max) > float(spec.zoom_min) else ""]
	if pl.light_on:
		t += "   СВЕТ"
	if pl.laser_on:
		t += "   ЛЦУ"
	if pl.is_jammed():
		t += "   ЗАДЕРЖКА (%s)" % PauseMenu.key_name("reload")
	if pl.reload_timer > 0.0:
		var action: String = "снаряжение магазина патронами…" if pl._reload_kind == "topup" else "перезарядка…"
		t = "%s   %s" % [String(spec.name), action]
	elif not pl._pm_action.is_empty() and String(pl._pm_action.kind) == "suppressor":
		t = "%s   %s глушителя…" % [String(spec.name), "установка" if bool(pl._pm_action.install) else "снятие"]
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
