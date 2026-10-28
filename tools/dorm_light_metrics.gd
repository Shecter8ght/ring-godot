extends RefCounted
## Benchmarks in a warmed static view; visibility is checked against actual physics walls/doors.
var host: Node3D
var camera: Camera3D

func _init(owner: Node3D, value: Camera3D) -> void:
	host = owner
	camera = value

func sample(seconds: float = 2.0) -> Dictionary:
	var viewport: RID = host.get_viewport().get_viewport_rid()
	var device: RenderingDevice = RenderingServer.get_rendering_device()
	var gpu: Array[float] = []
	var full: Array[float] = []
	var draws: Array[float] = []
	var visible_draws: Array[float] = []
	var shadow_draws: Array[float] = []
	var canvas_draws: Array[float] = []
	var cpu: float = 0.0
	var start: int = Time.get_ticks_usec()
	while gpu.size()<120 or Time.get_ticks_usec()-start<int(seconds*1000000.0):
		await host.get_tree().process_frame
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport))
		draws.append(float(RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)))
		visible_draws.append(float(host.get_viewport().get_render_info(Viewport.RENDER_INFO_TYPE_VISIBLE,Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)))
		shadow_draws.append(float(host.get_viewport().get_render_info(Viewport.RENDER_INFO_TYPE_SHADOW,Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)))
		canvas_draws.append(float(host.get_viewport().get_render_info(Viewport.RENDER_INFO_TYPE_CANVAS,Viewport.RENDER_INFO_DRAW_CALLS_IN_FRAME)))
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(viewport)
		var first: int = -1
		var last: int = -1
		for i: int in range(device.get_captured_timestamps_count()):
			var name: String = device.get_captured_timestamp_name(i)
			if name in ["dorm_frame_start","dorm_probe_start"]:first = i
			elif name.begins_with("vp_end_"):last = i
		if first>=0 and last>first:
			full.append((device.get_captured_timestamp_gpu_time(last)-device.get_captured_timestamp_gpu_time(first))/1000000.0)
	var elapsed: float = (Time.get_ticks_usec()-start)/1000000.0
	return {"fps":gpu.size()/elapsed,"frames":gpu.size(),"seconds":elapsed,"gpu_viewport_ms":_mean(gpu),
		"gpu_viewport_p95_ms":_percentile(gpu,.95),"gpu_frame_ms":_mean(full),"gpu_frame_p95_ms":_percentile(full,.95),
		"cpu_render_ms":cpu/gpu.size(),"draw_calls":draws[-1],"draw_calls_mean":_mean(draws),
		"draw_calls_median":_percentile(draws,.5),"draw_calls_p95":_percentile(draws,.95),
		"draw_calls_min":draws.min(),"draw_calls_max":draws.max(),"shadow_atlas":host.get_viewport().positional_shadow_atlas_size,
		"draw_visible_median":_percentile(visible_draws,.5),"draw_shadow_median":_percentile(shadow_draws,.5),
		"draw_shadow_min":shadow_draws.min(),"draw_shadow_max":shadow_draws.max(),"draw_canvas_median":_percentile(canvas_draws,.5),
		"atlas_quadrants":[host.get_viewport().positional_shadow_atlas_quad_0,host.get_viewport().positional_shadow_atlas_quad_1,
			host.get_viewport().positional_shadow_atlas_quad_2,host.get_viewport().positional_shadow_atlas_quad_3]}

func visibility() -> Dictionary:
	var space: PhysicsDirectSpaceState3D = host.get_world_3d().direct_space_state
	var planes: Array[Plane] = camera.get_frustum()
	var inside: Vector3 = camera.global_position-camera.global_basis.z*5.0
	var receivers: Array[Dictionary] = []
	var size: Vector2 = host.get_viewport().get_visible_rect().size
	for y: int in range(27):
		for x: int in range(48):
			var pixel: Vector2 = Vector2((x+.5)*size.x/48.0,(y+.5)*size.y/27.0)
			var direction: Vector3 = camera.project_ray_normal(pixel)
			var hit: Dictionary = _optical_hit(space,camera.global_position,camera.global_position+direction*90.0)
			if not hit.is_empty():receivers.append({"at":hit.position,"normal":hit.normal})
	var rows: Array[Dictionary] = []
	var frustum_lamps: int = 0
	var frustum_windows: int = 0
	var visible_lamps: int = 0
	var visible_windows: int = 0
	var receiver_lamps: int = 0
	var receiver_windows: int = 0
	var sun_receivers: int = 0
	var sun_count: int = 0
	for node: Node in host.find_children("*","DirectionalLight3D",true,false):
		var sun: DirectionalLight3D = node as DirectionalLight3D
		if not sun.is_visible_in_tree() or not sun.shadow_enabled or sun.light_energy<=0:continue
		sun_count += 1
		var direction: Vector3 = sun.global_basis.z.normalized()
		for receiver: Dictionary in receivers:
			var normal: Vector3 = receiver.normal
			if normal.dot(direction)<=.02:continue
			var start: Vector3 = (receiver.at as Vector3)+normal*.015
			if _optical_hit(space,start,start+direction*150.0).is_empty():sun_receivers += 1
	for node: Node in host.get_tree().get_nodes_in_group("dorm_lamps"):
		var lamp: Light3D = node as Light3D
		if not lamp.is_visible_in_tree() or not lamp.shadow_enabled or lamp.light_energy<=0:continue
		var radius: float = lamp.omni_range if lamp is OmniLight3D else (lamp as SpotLight3D).spot_range
		var intersects: bool = true
		for plane: Plane in planes:
			if plane.distance_to(lamp.global_position)*signf(plane.distance_to(inside)) < -radius:
				intersects = false
				break
		if not intersects:continue
		var window: bool = lamp.is_in_group("dorm_window_sky")
		if window:frustum_windows += 1
		else:frustum_lamps += 1
		var origin_visible: bool = false
		if camera.is_position_in_frustum(lamp.global_position):
			origin_visible = _optical_hit(space,camera.global_position,lamp.global_position).is_empty()
		if origin_visible:
			if window:visible_windows += 1
			else:visible_lamps += 1
		var lit_samples: int = 0
		for receiver: Dictionary in receivers:
			var point: Vector3 = receiver.at
			var delta: Vector3 = lamp.global_position-point
			var distance: float = delta.length()
			if distance<.02 or distance>=radius or (receiver.normal as Vector3).dot(delta/distance)<=.02:continue
			if lamp is SpotLight3D and (-lamp.global_basis.z).dot(-delta/distance)<cos(deg_to_rad((lamp as SpotLight3D).spot_angle)):continue
			var from: Vector3 = point+(receiver.normal as Vector3)*.015
			if _optical_hit(space,from,lamp.global_position).is_empty():lit_samples += 1
		if lit_samples>0:
			if window:receiver_windows += 1
			else:receiver_lamps += 1
		rows.append({"id":String(lamp.name),"window":window,"origin_visible":origin_visible,"lit_screen_samples":lit_samples})
	return {"shadow_lamps_frustum":frustum_lamps,"shadow_windows_frustum":frustum_windows,
		"shadow_sources_frustum":frustum_lamps+frustum_windows,"shadow_lamps_origin_visible":visible_lamps,
		"shadow_windows_origin_visible":visible_windows,"shadow_sources_origin_visible":visible_lamps+visible_windows,
		"shadow_lamps_visible_receivers":receiver_lamps,"shadow_windows_visible_receivers":receiver_windows,
		"shadow_sources_visible_receivers":receiver_lamps+receiver_windows,"visibility_grid":[48,27],"visibility_details":rows,
		"directional_shadow_sources":sun_count,"sun_visible_receiver_samples":sun_receivers,"voxel_light_candidates":voxel_light_candidates(),
		"visibility_method":"Origin: inside frustum plus unobstructed camera ray. Receivers: 48x27 screen-surface rays, normal/range/spot cone and source-to-surface visibility. Opaque level collision layer 1; transparent window collisions are skipped. Receiver count is sampled, not the engine shadow-pass count."}

static func _optical_hit(space: PhysicsDirectSpaceState3D, from: Vector3, to: Vector3) -> Dictionary:
	var start: Vector3 = from
	var direction: Vector3 = (to-from).normalized()
	for step: int in range(16):
		var hit: Dictionary = space.intersect_ray(PhysicsRayQueryParameters3D.create(start,to,1))
		if hit.is_empty():return {}
		var body: CollisionObject3D = hit.collider as CollisionObject3D
		var owner_id: int = body.shape_find_owner(int(hit.shape))
		var shape_owner: Object = body.shape_owner_get_owner(owner_id)
		if not shape_owner.has_meta("dorm_light_transparent"):return hit
		start = (hit.position as Vector3)+direction*.01
	return {"occluded":true}

func voxel_light_candidates() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for node: Node in host.find_children("*","VoxelGI",true,false):
		var voxel: VoxelGI = node as VoxelGI
		if not voxel.is_visible_in_tree():continue
		var bounds: AABB = voxel.global_transform*voxel.get_aabb()
		var count: int = 0
		for value: Node in host.get_tree().get_nodes_in_group("dorm_lamps"):
			var lamp: Light3D = value as Light3D
			if lamp.is_visible_in_tree() and lamp.light_bake_mode!=Light3D.BAKE_DISABLED and bounds.intersects(lamp.global_transform*lamp.get_aabb()):count += 1
		result.append({"id":String(voxel.name),"local_aabb_candidates":count,"voxel_limit_including_sun":32})
	return result

static func _mean(values: Array[float]) -> float:
	var sum: float = 0.0
	for value: float in values:sum += value
	return sum/maxi(values.size(),1)

static func _percentile(values: Array[float], fraction: float) -> float:
	if values.is_empty():return 0.0
	var sorted: Array[float] = values.duplicate()
	sorted.sort()
	return sorted[mini(sorted.size()-1,int(sorted.size()*fraction))]
