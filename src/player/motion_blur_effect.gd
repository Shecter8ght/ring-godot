@tool
class_name MotionBlurEffect
extends CompositorEffect
## Размытие в движении на камере игрока (Compositor камеры, CameraLook): после прозрачного, до
## тонмаппинга, по векторам движения кадра. Поворот головы смазывает мир, оружие в руках (оно
## движется вместе с камерой) остаётся чётким. strength = 0 — шаг пропускается целиком.

const CONTEXT := &"ring_motion_blur"
const TEMP := &"color_copy"

## Доля кадра «выдержки» (0 — выключено), предел длины мазка в долях экрана, число выборок.
var strength: float = 0.0
var max_len: float = 0.03
var samples: int = 12

var _rd: RenderingDevice
var _copy_shader: RID
var _copy_pipeline: RID
var _blur_shader: RID
var _blur_pipeline: RID
var _sampler: RID
var _frame: int = 0


func _init() -> void:
	effect_callback_type = EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
	needs_motion_vectors = true
	access_resolved_color = true
	RenderingServer.call_on_render_thread(_init_compute)


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and _rd:
		# пайплайны освобождаются вместе с шейдерами
		for rid: RID in [_copy_shader, _blur_shader, _sampler]:
			if rid.is_valid():
				_rd.free_rid(rid)


func _init_compute() -> void:
	_rd = RenderingServer.get_rendering_device()
	if not _rd:
		return
	_copy_shader = _rd.shader_create_from_spirv((load("res://src/player/motion_blur_copy.glsl") as RDShaderFile).get_spirv())
	_copy_pipeline = _rd.compute_pipeline_create(_copy_shader)
	_blur_shader = _rd.shader_create_from_spirv((load("res://src/player/motion_blur.glsl") as RDShaderFile).get_spirv())
	_blur_pipeline = _rd.compute_pipeline_create(_blur_shader)
	var ss: RDSamplerState = RDSamplerState.new()
	ss.min_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	ss.mag_filter = RenderingDevice.SAMPLER_FILTER_LINEAR
	ss.repeat_u = RenderingDevice.SAMPLER_REPEAT_MODE_CLAMP_TO_EDGE
	ss.repeat_v = RenderingDevice.SAMPLER_REPEAT_MODE_CLAMP_TO_EDGE
	_sampler = _rd.sampler_create(ss)


func _render_callback(callback_type: int, render_data: RenderData) -> void:
	if callback_type != EFFECT_CALLBACK_TYPE_POST_TRANSPARENT or strength <= 0.0:
		return
	if not _rd or not _blur_pipeline.is_valid():
		return
	var buffers: RenderSceneBuffersRD = render_data.get_render_scene_buffers() as RenderSceneBuffersRD
	if not buffers:
		return
	var size: Vector2i = buffers.get_internal_size()
	if size.x == 0 or size.y == 0:
		return
	if not buffers.has_texture(CONTEXT, TEMP):
		buffers.create_texture(CONTEXT, TEMP, RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT,
			RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT | RenderingDevice.TEXTURE_USAGE_STORAGE_BIT,
			RenderingDevice.TEXTURE_SAMPLES_1, size, 1, 1, true, false)
	_frame = (_frame + 1) % 4096
	var groups: Vector3i = Vector3i(ceili(size.x / 8.0), ceili(size.y / 8.0), 1)
	var copy_push: PackedByteArray = PackedFloat32Array([size.x, size.y, 0.0, 0.0]).to_byte_array()
	var blur_push: PackedByteArray = PackedFloat32Array([size.x, size.y, strength, max_len, float(_frame), float(samples), 0.0, 0.0]).to_byte_array()
	for view: int in range(buffers.get_view_count()):
		var color: RID = buffers.get_color_layer(view)
		var velocity: RID = buffers.get_velocity_layer(view)
		var temp: RID = buffers.get_texture_slice(CONTEXT, TEMP, view, 0, 1, 1)
		if not color.is_valid() or not velocity.is_valid():
			continue
		var copy_set: RID = UniformSetCacheRD.get_cache(_copy_shader, 0, [_image(0, color), _image(1, temp)])
		var blur_set: RID = UniformSetCacheRD.get_cache(_blur_shader, 0, [_sampled(0, temp), _sampled(1, velocity), _image(2, color)])
		var list: int = _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(list, _copy_pipeline)
		_rd.compute_list_bind_uniform_set(list, copy_set, 0)
		_rd.compute_list_set_push_constant(list, copy_push, copy_push.size())
		_rd.compute_list_dispatch(list, groups.x, groups.y, groups.z)
		_rd.compute_list_add_barrier(list)
		_rd.compute_list_bind_compute_pipeline(list, _blur_pipeline)
		_rd.compute_list_bind_uniform_set(list, blur_set, 0)
		_rd.compute_list_set_push_constant(list, blur_push, blur_push.size())
		_rd.compute_list_dispatch(list, groups.x, groups.y, groups.z)
		_rd.compute_list_end()


func _image(binding: int, tex: RID) -> RDUniform:
	var u: RDUniform = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	u.binding = binding
	u.add_id(tex)
	return u


func _sampled(binding: int, tex: RID) -> RDUniform:
	var u: RDUniform = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_SAMPLER_WITH_TEXTURE
	u.binding = binding
	u.add_id(_sampler)
	u.add_id(tex)
	return u
