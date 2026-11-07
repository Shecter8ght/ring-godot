class_name ThermalView
extends RefCounted
## Тепловой канал прицела ПН-36Т «ПОЛЫНЬ» (обвес optic_polyn_01 на «Осоке»; задание владельца 2026-11-06: «в прицеле
## тепловая картинка: вертолёт белый на сером»). Камера окуляра (CameraRig, отдельный рендер) в тепловом канале снимает
## мир со своим окружением (environment): холодное небо, ровный рассеянный свет вместо неба, без отражений, дымка по
## расстоянию, линейный тон и «автоусиление» — мир серый и не доходит до белого; тёплое — поверх (material_overlay
## THERMAL_SHADER): белым, и его видит только камера с битом THERMAL_BIT в маске (CAMERA_VISIBLE_LAYERS), остальные
## камеры этот проход отбрасывают. Тёплое: вертолёт-цель (корпус светлый, у сопел двигателей — белое пятно), люди
## (мародёры, другие игроки), горящие осветительные ракеты и ракеты в полёте (их сопло — шариком-«пятном»).
## Числа — Balance.THERMAL_SIGHT.

## Бит маски камеры теплового канала: выше 20 слоёв отрисовки — ни один объект на нём не стоит, отсечение не меняется.
const THERMAL_BIT: int = 1 << 24

const THERMAL_SHADER := """
shader_type spatial;
render_mode unshaded, depth_draw_never, cull_back, shadows_disabled;
// бит маски камеры теплового канала (ThermalView.THERMAL_BIT); у прочих камер проход отброшен
const uint THERMAL_BIT = 16777216u;
// «температура» поверхности 0…1 и горячее пятно: xyz — точка в мире, w — радиус спада, м (0 — без пятна)
instance uniform float heat_base = 0.75;
instance uniform vec4 hot = vec4(0.0);
// во сколько раз тёплое ярче: с поправкой на «автоусиление» камеры (ThermalView.update)
uniform float gain = 1.0;
varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	if ((CAMERA_VISIBLE_LAYERS & THERMAL_BIT) == 0u) {
		discard;
	}
	float h = heat_base;
	if (hot.w > 0.0) {
		h = max(h, exp(-distance(wpos, hot.xyz) / hot.w));
	}
	// под косым углом излучает слабее: края силуэта чуть темнее середины
	h *= mix(0.78, 1.0, clamp(dot(NORMAL, VIEW), 0.0, 1.0));
	ALBEDO = vec3(h * gain);
}
"""

static var _material: ShaderMaterial
static var _sphere: SphereMesh

var _env: Environment
var _attr: CameraAttributesPractical
## Наложенные проходы: [MeshInstance3D, прежний material_overlay]; «пятна» — [Node3D цели, MeshInstance3D, радиус].
var _applied: Array = []
var _spots: Array = []
var _heli: Array = []
var _scan_t: float = 0.0
var active: bool = false


static func material() -> ShaderMaterial:
	if _material == null:
		var sh := Shader.new()
		sh.code = THERMAL_SHADER
		_material = ShaderMaterial.new()
		_material.shader = sh
	return _material


## Тепловой канал на камере cam (каждый кадр, пока он включён): окружение, «автоусиление», тёплые цели.
func update(cam: Camera3D, base_mask: int, delta: float, own: Node) -> void:
	var cfg: Dictionary = Balance.THERMAL_SIGHT
	if _env == null:
		_build_env()
	active = true
	cam.environment = _env
	cam.attributes = _attr
	cam.cull_mask = base_mask | THERMAL_BIT
	# «автоусиление»: самая светлая поверхность мира — world_max при любом солнце (днём, в сумерках, ночью)
	var sun: float = sun_energy(cam)
	var amb: float = float(cfg.ambient) + sun * float(cfg.sun_ambient)
	var exposure: float = float(cfg.world_max) / (0.85 * (amb + sun))
	_env.ambient_light_energy = amb
	_env.tonemap_exposure = exposure
	# цвет фона движок берёт как sRGB (множитель — до перевода в линейный): небо — sky на экране после усиления
	var bg: float = pow(float(cfg.sky) / exposure, 1.0 / 2.2)
	_env.background_color = Color(bg, bg, bg)
	material().set_shader_parameter("gain", float(cfg.gain) / exposure)
	_scan_t -= delta
	if _scan_t <= 0.0:
		_scan_t = float(cfg.rescan_sec)
		_scan(cam.get_tree(), own)
	_tick_spots()


## Выключить тепловой канал: камере — прежнее окружение и маска, целям — прежние проходы.
func off(cam: Camera3D, base_mask: int) -> void:
	if cam:
		cam.environment = null
		cam.attributes = null
		cam.cull_mask = base_mask
	if not active:
		return
	active = false
	for item: Array in _applied:
		if not is_instance_valid(item[0]):
			continue
		var mi: MeshInstance3D = item[0] as MeshInstance3D
		if mi.material_overlay == material():
			mi.material_overlay = item[1] as Material
	_applied.clear()
	for spot: Array in _spots:
		if is_instance_valid(spot[1]):
			(spot[1] as Node).queue_free()
	_spots.clear()
	_heli.clear()


func _build_env() -> void:
	var cfg: Dictionary = Balance.THERMAL_SIGHT
	_env = Environment.new()
	_env.background_mode = Environment.BG_COLOR
	_env.background_color = Color.WHITE
	_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	_env.ambient_light_color = Color.WHITE
	# отражения неба у металла и стекла в тепловом канале — холодные: без отражений
	_env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
	_env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	_env.fog_enabled = true
	var hz: float = float(cfg.haze_color)
	_env.fog_light_color = Color(hz, hz, hz)
	_env.fog_density = float(cfg.haze)
	_env.fog_sky_affect = 0.0
	_attr = CameraAttributesPractical.new()
	_attr.auto_exposure_enabled = false
	_attr.exposure_multiplier = 1.0


## Видимая сила солнца (или луны) сцены: энергия × яркость цвета; своего света рук нет.
func sun_energy(cam: Camera3D) -> float:
	var best: float = 0.0
	var scene: Node = cam.get_tree().current_scene
	if scene == null:
		return 0.0
	for raw: Node in scene.find_children("*", "DirectionalLight3D", true, false):
		var l: DirectionalLight3D = raw as DirectionalLight3D
		if not l.visible or l.has_meta("own"):
			continue
		var c: Color = l.light_color
		best = maxf(best, l.light_energy * (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b))
	return best


func _scan(tree: SceneTree, own: Node) -> void:
	var cfg: Dictionary = Balance.THERMAL_SIGHT
	for k in range(_applied.size() - 1, -1, -1):
		if not is_instance_valid((_applied[k] as Array)[0]):
			_applied.remove_at(k)
	for raw: Node in tree.get_nodes_in_group("heat_targets"):
		if raw is HeliTarget:
			var heli: HeliTarget = raw as HeliTarget
			var hc: Dictionary = cfg.heli
			if _heli.find(heli) < 0:
				_heli.append(heli)
			_overlay_tree(heli, float(hc.base))
		elif raw is Node3D:
			_spot(raw as Node3D, float(cfg.flare), float(cfg.flare_r))
	for raw2: Node in tree.get_nodes_in_group("missiles"):
		_spot(raw2 as Node3D, float(cfg.missile), float(cfg.missile_r))
	for group: String in ["marauders", "all_players"]:
		for raw3: Node in tree.get_nodes_in_group(group):
			if raw3 == own or not raw3 is Node3D:
				continue
			_overlay_tree(raw3 as Node3D, float(cfg.person))


## Тёплый проход на все сетки узла (кроме прозрачных: диск винта, свечение огня, частицы).
func _overlay_tree(root: Node3D, heat: float) -> void:
	for raw: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = raw as MeshInstance3D
		if mi.material_overlay == material() or not _opaque(mi):
			continue
		_applied.append([mi, mi.material_overlay])
		mi.material_overlay = material()
		mi.set_instance_shader_parameter("heat_base", heat)
		mi.set_instance_shader_parameter("hot", Vector4.ZERO)


func _opaque(mi: MeshInstance3D) -> bool:
	if mi.mesh == null or mi.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
		return false
	var m: Material = mi.material_override if mi.material_override else (mi.get_active_material(0) if mi.mesh.get_surface_count() > 0 else null)
	if m is BaseMaterial3D:
		var bm: BaseMaterial3D = m as BaseMaterial3D
		return bm.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED and bm.blend_mode == BaseMaterial3D.BLEND_MODE_MIX
	return true


## Горячее «пятно» шариком у тепловой точки цели (ракета, осветительная ракета): видно только тепловой камере.
func _spot(target: Node3D, heat: float, radius: float) -> void:
	for spot: Array in _spots:
		if is_instance_valid(spot[0]) and spot[0] == target:
			return
	if _sphere == null:
		_sphere = SphereMesh.new()
		_sphere.radius = 1.0
		_sphere.height = 2.0
		_sphere.radial_segments = 16
		_sphere.rings = 8
	var mi := MeshInstance3D.new()
	mi.name = "ThermalSpot"
	mi.mesh = _sphere
	mi.material_override = material()
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.scale = Vector3.ONE * radius
	mi.top_level = true
	target.add_child(mi)
	mi.set_instance_shader_parameter("heat_base", heat)
	mi.set_instance_shader_parameter("hot", Vector4.ZERO)
	_spots.append([target, mi, radius])


## Каждый кадр: «пятна» — к тепловой точке цели, у вертолёта — горячее место у сопел (горит — шире и жарче).
func _tick_spots() -> void:
	var cfg: Dictionary = Balance.THERMAL_SIGHT
	for i in range(_spots.size() - 1, -1, -1):
		var spot: Array = _spots[i]
		if not is_instance_valid(spot[0]) or not is_instance_valid(spot[1]):
			if is_instance_valid(spot[1]):
				(spot[1] as Node).queue_free()
			_spots.remove_at(i)
			continue
		var target: Node3D = spot[0] as Node3D
		var mi: MeshInstance3D = spot[1] as MeshInstance3D
		var alive: bool = not target.has_method("heat_alive") or bool(target.call("heat_alive"))
		mi.visible = alive or target is OsokaMissile
		mi.global_position = target.call("heat_point") if target.has_method("heat_point") else target.global_position
	var hc: Dictionary = cfg.heli
	for j in range(_heli.size() - 1, -1, -1):
		if not is_instance_valid(_heli[j]):
			_heli.remove_at(j)
			continue
		var heli: HeliTarget = _heli[j] as HeliTarget
		var burning: bool = not heli.heat_alive()
		var p: Vector3 = heli.heat_point()
		var hot := Vector4(p.x, p.y, p.z, float(hc.hot_r) * (float(hc.fire_k) if burning else 1.0))
		for raw: Node in heli.find_children("*", "MeshInstance3D", true, false):
			var mi2: MeshInstance3D = raw as MeshInstance3D
			if mi2.material_overlay == material():
				mi2.set_instance_shader_parameter("hot", hot)
