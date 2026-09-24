class_name RainOcclusion
extends Node3D
## Карта «что над головой» для дождя: ортокамера смотрит сверху вниз на квадрат SIZE×SIZE м
## вокруг игрока и пишет в текстуру высоту самой верхней поверхности (крыша, перекрытие, купол,
## земля). Шейдеры дождя сравнивают с ней высоту капли, брызги и луж: ниже — под крышей, сухо.
## Карта перерисовывается один раз, когда игрок ушёл от центра дальше MOVE_M (геометрия
## статична). Работает с любой картой: смотрит на то, что нарисовано, а не на данные сектора.
## Прозрачное (стекло купола) глубину не пишет, а потолок смотрит вниз (сверху — изнанка,
## отсекается): для мешей в группе "rain_block" — непрозрачный двусторонний двойник на слое
## LAYER. Слой LAYER основные камеры не видят (CameraRig).

## Слой служебной геометрии карты (невидим основным камерам).
const LAYER := 1 << 18
const SIZE := 96.0
const RES := 512
## Высота камеры над центром и глубина диапазона высот (кодируем 0..1 в канал R, fp16).
const LIFT := 70.0
const RANGE := 128.0
const MOVE_M := 10.0
const SNAP_M := 4.0

var center := Vector3(INF, 0.0, INF)
var _vp: SubViewport
var _cam: Camera3D
var _mats: Array[ShaderMaterial] = []
var _twins: Array[Node] = []

const DEPTH_SHADER := """
shader_type spatial;
render_mode unshaded, fog_disabled, depth_test_disabled, depth_draw_never, cull_disabled, shadows_disabled, ambient_light_disabled;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest;
uniform float cam_y;
uniform float range_m;
void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}
void fragment() {
	float d = texture(depth_tex, SCREEN_UV).r;
	vec4 v = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, d, 1.0);
	v.xyz /= v.w;
	// камера смотрит вниз: вид −Z = мир −Y; ничего не попало (d = 0, дальняя плоскость) — самый низ
	float h01 = d <= 0.0 ? 0.0 : clamp((cam_y + v.z - (cam_y - range_m)) / range_m, 0.0, 1.0);
	ALBEDO = vec3(h01, 0.0, 0.0);
	ALPHA = 1.0;
}
"""


func _ready() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(RES, RES)
	_vp.use_hdr_2d = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	_vp.positional_shadow_atlas_size = 0
	_vp.msaa_3d = Viewport.MSAA_DISABLED
	_vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_DISABLED
	_vp.use_taa = false
	_vp.audio_listener_enable_3d = false
	add_child(_vp)
	_cam = Camera3D.new()
	_cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	_cam.size = SIZE
	_cam.near = 0.5
	_cam.far = RANGE + 8.0
	_cam.cull_mask = 0xFFFFF
	_cam.rotation_degrees.x = -90.0
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	env.tonemap_exposure = 1.0
	_cam.environment = env
	_vp.add_child(_cam)
	var quad := MeshInstance3D.new()
	var qm := QuadMesh.new()
	qm.size = Vector2(2, 2)
	quad.mesh = qm
	quad.extra_cull_margin = 16384.0
	quad.layers = LAYER
	quad.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	quad.position = Vector3(0, 0, -1.0)
	var sh := Shader.new()
	sh.code = DEPTH_SHADER
	var sm := ShaderMaterial.new()
	sm.shader = sh
	sm.render_priority = 127
	sm.set_shader_parameter("range_m", RANGE)
	quad.material_override = sm
	_cam.add_child(quad)
	_make_twins()


func _exit_tree() -> void:
	for t in _twins:
		if is_instance_valid(t):
			t.queue_free()
	_twins.clear()


## Стекло и прочее прозрачное, что держит дождь: непрозрачный двойник на служебном слое.
func _make_twins() -> void:
	var opaque := StandardMaterial3D.new()
	opaque.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	opaque.cull_mode = BaseMaterial3D.CULL_DISABLED
	for n in get_tree().get_nodes_in_group("rain_block"):
		var mi := n as MeshInstance3D
		if mi == null or mi.mesh == null:
			continue
		var t := MeshInstance3D.new()
		t.name = mi.name + "_RainTwin"
		t.mesh = mi.mesh
		t.material_override = opaque
		t.layers = LAYER
		t.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.add_child(t)
		_twins.append(t)


func texture() -> Texture2D:
	return _vp.get_texture()


## Шейдер, которому нужна карта (uniform occ_tex, occ_center, occ_size, occ_base, occ_range).
func bind(m: ShaderMaterial) -> void:
	_mats.append(m)
	m.set_shader_parameter("occ_tex", _vp.get_texture())
	_push(m)


func _push(m: ShaderMaterial) -> void:
	m.set_shader_parameter("occ_center", Vector2(center.x, center.z))
	m.set_shader_parameter("occ_size", SIZE)
	m.set_shader_parameter("occ_base", center.y + LIFT - RANGE)
	m.set_shader_parameter("occ_range", RANGE)


## Центр карты — у фокуса (игрок / камера); ушёл далеко — перерисовать.
func follow(focus: Vector3) -> void:
	if center.x != INF and Vector2(focus.x - center.x, focus.z - center.z).length() < MOVE_M and absf(focus.y - center.y) < 6.0:
		return
	center = Vector3(snappedf(focus.x, SNAP_M), snappedf(focus.y, SNAP_M), snappedf(focus.z, SNAP_M))
	_cam.global_position = center + Vector3.UP * LIFT
	(( _cam.get_child(0) as MeshInstance3D).material_override as ShaderMaterial).set_shader_parameter("cam_y", center.y + LIFT)
	_vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	for m in _mats:
		_push(m)


## Высота верхней поверхности по карте (для тестов: читает картинку с GPU — медленно).
func height_at(img: Image, x: float, z: float) -> float:
	var u := (x - center.x) / SIZE + 0.5
	var v := (z - center.z) / SIZE + 0.5
	if u < 0.0 or u >= 1.0 or v < 0.0 or v >= 1.0:
		return -INF
	var c := img.get_pixel(int(u * img.get_width()), int(v * img.get_height()))
	return center.y + LIFT - RANGE + c.r * RANGE
