class_name CameraLook
extends Node
## Вид «как с камеры» поверх кадра (Balance.LOOK): глаз привыкает к свету (автоэкспозиция вокруг экспозиции
## сцены: в темноте — светлее, до adapt_up; ночь остаётся ночью ночным зрением — в тёмном цвет уходит,
## картинка холодеет; тени не проваливаются в чёрное), объектив (лёгкая бочка, цветная кайма к
## краям, виньетка), зерно, резкость и грейд; в прицеле бочка и кайма уходят, оружие у лица чуть
## размыто; «зайчики» объектива от ярких источников (LensFlare); размытие в движении (MotionBlurEffect). Настройки: Settings.lens_fx, Settings.motion_blur.
## Слой объектива — под всем интерфейсом (layer -1): надписи и окна не искажаются.

const LENS_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float distortion = 0.0;
uniform float aberration = 0.0;
uniform float vignette = 0.0;
uniform float grain = 0.0;
uniform float sharpen = 0.0;
uniform float saturation = 1.0;
uniform float contrast = 1.0;
uniform float black_keep = 0.12;
uniform vec3 shadow_tint = vec3(1.0);
uniform vec3 high_tint = vec3(1.0);
uniform float scotopic = 0.0;
uniform float scotopic_l = 0.2;
uniform vec3 scotopic_tint = vec3(1.0);
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void fragment() {
	vec2 px = SCREEN_PIXEL_SIZE;
	// бочка: края кадра чуть сжаты к центру, углы остаются углами
	vec2 c0 = SCREEN_UV - 0.5;
	vec2 uv = 0.5 + c0 * (1.0 + distortion * dot(c0, c0)) / (1.0 + distortion * 0.5);
	vec2 dir = uv - 0.5;
	vec3 c = vec3(texture(screen_tex, uv + dir * aberration).r, texture(screen_tex, uv).g,
		texture(screen_tex, uv - dir * aberration).b);
	vec3 blur = texture(screen_tex, uv + vec2(px.x, 0.0)).rgb + texture(screen_tex, uv - vec2(px.x, 0.0)).rgb
		+ texture(screen_tex, uv + vec2(0.0, px.y)).rgb + texture(screen_tex, uv - vec2(0.0, px.y)).rgb;
	c = max(c + (c - blur * 0.25) * sharpen, vec3(0.0));
	float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c = mix(vec3(l), c, saturation);
	// контраст вокруг середины, но тени не уходят в ноль: прежде всё темнее ~7/255 становилось чёрным
	c = mix(c, (c - 0.5) * contrast + 0.5, smoothstep(0.0, black_keep, l));
	c *= mix(shadow_tint, high_tint, smoothstep(0.05, 0.7, l));
	// ночное зрение: в темноте цвет уходит, картинка холодеет — ночь видна ночью и при поднятой экспозиции
	c = mix(c, vec3(dot(c, vec3(0.2126, 0.7152, 0.0722))) * scotopic_tint, scotopic * (1.0 - smoothstep(0.0, scotopic_l, l)));
	vec2 d = SCREEN_UV - 0.5;
	d.x *= px.y / px.x;
	c *= mix(1.0, smoothstep(0.95, 0.25, length(d)), vignette);
	float n = hash(floor(SCREEN_UV / px) + fract(TIME * 7.0) * 113.0) - 0.5;
	c += n * grain * (1.0 - clamp(l, 0.0, 1.0) * 0.7);
	COLOR = vec4(max(c, vec3(0.0)), 1.0);
}
"""

var _cams: Array[Camera3D] = []
var _attr: CameraAttributesPractical
var _layer: CanvasLayer
var _lens: ColorRect
var _blur: MotionBlurEffect
var _flare: LensFlare
var _compositor: Compositor
## 0 — у бедра, 1 — в прицеле (CameraRig задаёт каждый кадр); iron — открытый прицел (мушка).
var aim_k: float = 0.0
var iron: bool = false
var _prev_xf: Transform3D
var _has_prev: bool = false
## В рейде глаз привыкает к темноте шире и есть ночное зрение; в убежище — свет, как его настроил владелец.
var _raid: bool = false
## Внутри здания глаз привыкает сильнее (adapt_up_indoor): тёмная квартира на порядок темнее ночного двора.
var _indoor: bool = false
## Темнота вокруг (0..1): ночь или помещение без света — плавно; ночное зрение — только тогда (днём тёмные
## места не обесцвечиваются: листва и стволы в дождь серели).
var _dark_k: float = 0.0
var _dark_target: float = 0.0
var _ctx_t: float = 0.0
## Свой свет рук и оружия (CameraRig, ViewmodelFill): в темноте сильнее, внутри здания — слабее во
## столько, во сколько глаз там привыкает сильнее (иначе ствол «светится» в тёмной квартире).
var _fill: DirectionalLight3D
## Своё привыкание глаза у карты рейда — данные сектора "look" (ключи — как в Balance.LOOK: exposure_scale_raid,
## adapt_up, adapt_up_indoor); у какого уровня (id) прочитано. Нет ключа — общее из Balance.LOOK.
var _map_look: Dictionary = {}
var _map_look_level: int = 0


## Основная камера — главная: по ней размытие в движении; остальные (оптика) получают ту же экспозицию.
func setup(main: Camera3D, others: Array[Camera3D] = []) -> void:
	_cams = [main]
	_cams.append_array(others)
	_attr = CameraAttributesPractical.new()
	_attr.dof_blur_far_enabled = false
	_blur = MotionBlurEffect.new()
	_compositor = Compositor.new()
	_compositor.compositor_effects = [_blur]
	main.compositor = _compositor
	_layer = CanvasLayer.new()
	_layer.name = "LensLayer"
	_layer.layer = -1
	add_child(_layer)
	_lens = ColorRect.new()
	_lens.name = "Lens"
	_lens.set_anchors_preset(Control.PRESET_FULL_RECT)
	_lens.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh: Shader = Shader.new()
	sh.code = LENS_SHADER
	var mat: ShaderMaterial = ShaderMaterial.new()
	mat.shader = sh
	_lens.material = mat
	_layer.add_child(_lens)
	_flare = LensFlare.new()
	_flare.name = "Flare"
	_layer.add_child(_flare)
	Settings.changed.connect(apply_settings)
	apply_settings()


func apply_settings() -> void:
	var on: bool = Settings.lens_fx
	var L: Dictionary = Balance.LOOK
	_lens.visible = on
	_flare.visible = on
	_flare.reference = float(L.flare_ref)
	_attr.auto_exposure_enabled = on
	if on:
		_attr.auto_exposure_speed = float(L.adapt_speed)
		_apply_exposure()
	for cam: Camera3D in _cams:
		cam.attributes = _attr
	var mat: ShaderMaterial = _lens.material as ShaderMaterial
	for k: String in ["vignette", "grain", "sharpen", "saturation", "contrast", "black_keep", "scotopic_l"]:
		mat.set_shader_parameter(k, float(L[k]))
	mat.set_shader_parameter("scotopic", float(L.scotopic) * _dark_k if _raid else 0.0)
	mat.set_shader_parameter("shadow_tint", L.shadow_tint)
	mat.set_shader_parameter("high_tint", L.high_tint)
	mat.set_shader_parameter("scotopic_tint", L.scotopic_tint)
	_blur.max_len = float(L.blur_max)
	_blur.near_k = _cams[0].near / float(L.blur_keep_m)
	_blur.samples = int(L.blur_samples)
	_has_prev = false


## Привыкание глаза: поправка экспозиции = scale / средняя яркость кадра, яркость зажата так, что поправка
## в [down, up]. Убежище — как настроено; в рейде своя цель (светлее) и свой предел на улице и в здании.
func _apply_exposure() -> void:
	var L: Dictionary = Balance.LOOK
	_refresh_map_look()
	var scale: float = _look("exposure_scale_raid") if _raid else float(L.exposure_scale)
	var up: float = float(L.adapt_up_shelter)
	if _raid:
		up = _look("adapt_up_indoor") if _indoor else _look("adapt_up")
	_attr.auto_exposure_scale = scale
	_attr.auto_exposure_min_sensitivity = _iso(scale / up)
	_attr.auto_exposure_max_sensitivity = _iso(scale / float(L.adapt_down))
	_update_fill()


func _update_fill() -> void:
	if _fill == null and not _cams.is_empty() and is_instance_valid(_cams[0]):
		_fill = _cams[0].get_node_or_null("ViewmodelFill") as DirectionalLight3D
	if _fill == null:
		return
	var vf: Dictionary = Balance.VIEWMODEL_FILL
	var L: Dictionary = Balance.LOOK
	var k: float = lerpf(float(vf.day_k), 1.0, _dark_k)
	if _raid and Settings.lens_fx:
		k *= _look("adapt_up") / (_look("adapt_up_indoor") if _indoor else _look("adapt_up"))
	_fill.light_energy = float(vf.energy) * k


func _look(key: String) -> float:
	return float(_map_look.get(key, Balance.LOOK[key]))


## Данные "look" карты рейда — раз на уровень (уровень меняется — читаются заново).
func _refresh_map_look() -> void:
	var level: Node = RaidAtmosphere.current.get_parent() if _raid and RaidAtmosphere.current else null
	var level_id: int = level.get_instance_id() if level else 0
	if level_id == _map_look_level:
		return
	_map_look_level = level_id
	_map_look = {}
	var path: Variant = level.get("sector_path") if level else null
	if path != null and String(path) != "":
		_map_look = SectorBuilder.load_def(String(path)).get("look", {}) as Dictionary


## Светимость (как её меряет движок) → «чувствительность ISO» CameraAttributesPractical (12.5 ед. = ISO 100).
static func _iso(luminance: float) -> float:
	return luminance * 100.0 / 0.125


func _process(delta: float) -> void:
	if _cams.is_empty() or not is_instance_valid(_cams[0]):
		return
	if (Raid.current != null) != _raid:
		_raid = Raid.current != null
		apply_settings()
	var L: Dictionary = Balance.LOOK
	if _raid and Settings.lens_fx:
		_ctx_t -= delta
		if _ctx_t <= 0.0 and RaidAtmosphere.current:
			_ctx_t = float(L.context_sec)
			# уровень рейда появился позже Raid.current — его привыкание глаза ещё не прочитано
			if RaidAtmosphere.current.get_parent().get_instance_id() != _map_look_level:
				_apply_exposure()
			var feet: Vector3 = _cams[0].global_position + Vector3.DOWN * 1.6
			var indoor: bool = RaidAtmosphere.current.is_indoor(feet)
			if indoor != _indoor:
				_indoor = indoor
				_apply_exposure()
			var night: bool = String(RaidConditions.current.get("time", "day")) == "night"
			_dark_target = 1.0 if RaidAtmosphere.current.is_dark(feet) or (indoor and night) else 0.0
		if not is_equal_approx(_dark_k, _dark_target):
			_dark_k = move_toward(_dark_k, _dark_target, delta / float(L.scotopic_sec))
			(_lens.material as ShaderMaterial).set_shader_parameter("scotopic", float(L.scotopic) * _dark_k)
			_update_fill()
	var free_k: float = 1.0 - clampf(aim_k, 0.0, 1.0)
	if _lens.visible:
		var mat: ShaderMaterial = _lens.material as ShaderMaterial
		mat.set_shader_parameter("distortion", float(L.distortion) * free_k)
		mat.set_shader_parameter("aberration", float(L.aberration) * free_k)
	# у лица в прицеле — ствольная коробка, приклад, задний целик: глаз смотрит вдаль, они мягкие
	var dof: float = float(L.dof_amount) * aim_k * (float(L.dof_iron_k) if iron else 1.0)
	_attr.dof_blur_near_enabled = Settings.lens_fx and dof > 0.002
	_attr.dof_blur_near_distance = float(L.dof_near_m)
	_attr.dof_blur_near_transition = float(L.dof_transition_m)
	_attr.dof_blur_amount = dof
	# размытие в движении; скачок камеры (возрождение, смена вида) кадр не смазывает
	var cam: Camera3D = _cams[0]
	var xf: Transform3D = cam.global_transform
	var cut: bool = not _has_prev or not cam.current
	if _has_prev:
		cut = cut or xf.origin.distance_to(_prev_xf.origin) > float(L.blur_cut_m)
		cut = cut or rad_to_deg(_prev_xf.basis.z.angle_to(xf.basis.z)) > float(L.blur_cut_deg)
	_prev_xf = xf
	_has_prev = true
	_blur.strength = 0.0 if cut or not Settings.motion_blur else float(L.blur_shutter)
