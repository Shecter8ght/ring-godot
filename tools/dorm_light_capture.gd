extends RefCounted
## Фиксированные камеры, варианты света и замеры того же кадра без V-Sync.

var host: Node3D
var light: Node3D
var manifest: Array[Dictionary] = []
var performance: Array[Dictionary] = []
var failed: int = 0


func run(owner: Node3D) -> void:
	host = owner
	light = host.get("lighting") as Node3D
	if DisplayServer.get_name()=="headless":
		push_error("dorm: свет и GPU измеряются оконным запуском")
		host.get_tree().quit(1)
		return
	(host.get("walker") as Node).set_physics_process(false)
	(host.get("hud") as CanvasLayer).hide()
	for label: Node in host.get_tree().get_nodes_in_group("dorm_study_labels"):
		(label as Node3D).hide()
	RenderingServer.viewport_set_measure_render_time(host.get_viewport().get_viewport_rid(),true)
	RenderingServer.frame_pre_draw.connect(_gpu_begin)
	Engine.max_fps = 0
	var plan: Dictionary = host.get("plan") as Dictionary
	var cases: Array = plan.environment.cases
	var case_filter: PackedStringArray = OS.get_environment("DORM_CASES").split(",",false)
	var view_filter: PackedStringArray = OS.get_environment("DORM_VIEWS").split(",",false)
	for i: int in range(cases.size()):
		var choice: Dictionary = cases[i]
		if not case_filter.is_empty() and String(choice.id) not in case_filter:
			continue
		print("dorm: LIGHT CASE ",choice.id)
		await light.call("set_case",i)
		for leaf: Node in host.get_tree().get_nodes_in_group("dorm_study_doors"):
			leaf.call("reset_pose")
		for angle: float in [80.0,95.0]:
			host.call("_set_fov",angle)
			for view: Dictionary in plan.shots:
				if not view_filter.is_empty() and String(view.id) not in view_filter:
					continue
				if angle==95.0 and String(view.id) not in ["01_corridor","02_room","05_stairs_bottom"]:
					continue
				_place(view)
				await _frames(150 if angle==80 else 75)
				var tag: String = String(choice.id)+("_fov95" if angle==95 else "")
				await _capture(tag,view,angle)
				if angle==80 and String(view.id) in ["01_corridor","09_lounge"]:
					var sample: Dictionary = await _measure()
					sample["case"] = choice.id
					sample["view"] = view.id
					performance.append(sample)
					print("dorm: PERF ",JSON.stringify(sample))
		if i==0 and OS.get_environment("DORM_NO_EXTRAS")!="1":
			for view: Dictionary in plan.shots:
				if String(view.id) not in ["01_corridor","02_room"]:
					continue
				_place(view)
				host.call("_set_fov",80.0)
				for effect: String in ["ssil","fog","post"]:
					light.call("set_effect",effect=="ssil",effect)
					await _frames(120)
					await _capture("evening_A_"+("ssil_on" if effect=="ssil" else effect+"_off"),view,80)
					light.call("set_effect",effect!="ssil",effect)
		if i==1:
			# Настоящее отсутствие VoxelGIData: прямой свет остаётся, отскоков VoxelGI нет.
			var saved: Array[VoxelGIData] = []
			for voxel: VoxelGI in light.get("voxels"):
				saved.append(voxel.data)
				voxel.data = null
			var view: Dictionary = plan.shots[0]
			_place(view)
			host.call("_set_fov",80.0)
			await _frames(150)
			await _capture("evening_B_unbaked",view,80)
			var n: int = 0
			for voxel: VoxelGI in light.get("voxels"):
				voxel.data = saved[n]
				n += 1
	var output: String = String(host.get("output_dir"))
	_save(output.path_join("light_views.json"),manifest)
	_save(output.path_join("light_performance.json"),{"samples":performance,"engine":Engine.get_version_info().string,
		"gpu":RenderingServer.get_video_adapter_name(),"cpu":OS.get_processor_name(),"viewport":str(host.get_viewport().get_visible_rect().size),
		"vsync":DisplayServer.window_get_vsync_mode(),"shadow_count_method":"Light influence sphere vs camera frustum; conservative upper bound, no occlusion",
		"gpu_method":"RenderingDevice timestamps from frame_pre_draw to viewport end, nanoseconds / 1e6; viewport-only time also retained", "bake":light.get("bake_report")})
	print("dorm: light shots ",manifest.size()," failed ",failed)
	host.get_tree().quit(failed)


func _place(view: Dictionary) -> void:
	var camera: Camera3D = host.get("camera") as Camera3D
	camera.global_position = _vec(view.foot)+Vector3.UP*float(view.eye_height)
	camera.look_at(_vec(view.look),Vector3.UP)
	light.call("update_active_probes")


func _frames(count: int) -> void:
	for i: int in range(count):
		await host.get_tree().process_frame


func _capture(tag: String, view: Dictionary, angle: float) -> void:
	await RenderingServer.frame_post_draw
	var filename: String = "light_%s_%s.png" % [tag,String(view.id)]
	var error: Error = host.get_viewport().get_texture().get_image().save_png(String(host.get("output_dir")).path_join(filename))
	failed += 1 if error!=OK else 0
	manifest.append({"file":filename,"id":view.id,"case":tag,"foot":view.foot,"look":view.look,"eye_height":view.eye_height,
		"fov_h":angle,"fov_v":(host.get("camera") as Camera3D).fov,"ssil":light.get("ssil"),"fog":light.get("fog"),
		"post":light.get("post"),"tonemap":"Filmic" if bool(light.get("post")) else "Linear", "revision":5,
		"sdfgi_actual":(light.get("environment") as Environment).sdfgi_enabled,"quality_setting":Settings.quality})
	print("dorm: light shot ",filename," error ",error)


func _measure() -> Dictionary:
	var viewport: RID = host.get_viewport().get_viewport_rid()
	var gpu: Array[float] = []
	var cpu: float = 0
	var setup_cpu: float = 0
	var full_gpu: Array[float] = []
	var timestamp_names: Array[String] = []
	var device: RenderingDevice = RenderingServer.get_rendering_device()
	var start: int = Time.get_ticks_usec()
	var seconds: float = 2.0 if OS.get_environment("DORM_BENCH_SECONDS").is_empty() else float(OS.get_environment("DORM_BENCH_SECONDS"))
	while gpu.size()<120 or Time.get_ticks_usec()-start<int(seconds*1000000):
		await host.get_tree().process_frame
		gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(viewport))
		cpu += RenderingServer.viewport_get_measured_render_time_cpu(viewport)
		setup_cpu += RenderingServer.get_frame_setup_time_cpu()
		var stamps: int = device.get_captured_timestamps_count()
		if stamps>1:
			var first: int = -1
			var last: int = -1
			for n: int in range(stamps):
				var marker: String = device.get_captured_timestamp_name(n)
				if marker=="dorm_frame_start":
					first = n
				elif marker.begins_with("vp_end_"):
					last = n
			if first>=0 and last>first:
				full_gpu.append((device.get_captured_timestamp_gpu_time(last)-device.get_captured_timestamp_gpu_time(first))/1000000.0)
			if timestamp_names.is_empty():
				for n: int in range(stamps):
					timestamp_names.append(device.get_captured_timestamp_name(n))
	var elapsed: float = (Time.get_ticks_usec()-start)/1000000.0
	var mean_gpu: float = 0
	for value: float in gpu:
		mean_gpu += value
	mean_gpu /= gpu.size()
	gpu.sort()
	var mean_full: float = 0
	for value: float in full_gpu:
		mean_full += value
	if not full_gpu.is_empty():
		mean_full /= full_gpu.size()
	full_gpu.sort()
	var shadows: Dictionary = _shadow_count()
	return {"fps":gpu.size()/elapsed,"gpu_viewport_ms":mean_gpu,"gpu_viewport_p95_ms":gpu[int(gpu.size()*.95)],"cpu_render_ms":cpu/gpu.size(),
		"cpu_setup_ms":setup_cpu/gpu.size(),"gpu_frame_ms":mean_full,"gpu_timestamp_names":timestamp_names,
		"gpu_frame_p95_ms":full_gpu[int(full_gpu.size()*.95)] if not full_gpu.is_empty() else 0.0,
		"frames":gpu.size(),"seconds":elapsed,"shadow_lamps_frustum":shadows.lamps,"shadow_windows_frustum":shadows.windows,
		"shadow_sources_frustum":int(shadows.lamps)+int(shadows.windows),
		"shadow_atlas":host.get_viewport().positional_shadow_atlas_size,"draw_calls":RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)}


func _shadow_count() -> Dictionary:
	var camera: Camera3D = host.get("camera") as Camera3D
	var planes: Array[Plane] = camera.get_frustum()
	var inside: Vector3 = camera.global_position-camera.global_basis.z*5
	var count: int = 0
	var windows: int = 0
	for node: Node in host.get_tree().get_nodes_in_group("dorm_lamps"):
		var lamp: Light3D = node as Light3D
		if not lamp.is_visible_in_tree() or not lamp.shadow_enabled:
			continue
		var radius: float = (lamp as OmniLight3D).omni_range if lamp is OmniLight3D else (lamp as SpotLight3D).spot_range
		var visible: bool = true
		for plane: Plane in planes:
			var distance: float = plane.distance_to(lamp.global_position)
			if distance*signf(plane.distance_to(inside)) < -radius:
				visible = false
				break
		if visible:
			if node.is_in_group("dorm_window_sky"):
				windows += 1
			else:
				count += 1
	return {"lamps":count,"windows":windows}


static func _vec(at: Array) -> Vector3:
	return Vector3(float(at[0]),float(at[1]),float(at[2]))


static func _save(path: String, data: Variant) -> void:
	var file: FileAccess = FileAccess.open(path,FileAccess.WRITE)
	file.store_string(JSON.stringify(data,"\t"))
	file.close()


func _gpu_begin() -> void:
	RenderingServer.call_on_render_thread(func() -> void: RenderingServer.get_rendering_device().capture_timestamp("dorm_frame_start"))
