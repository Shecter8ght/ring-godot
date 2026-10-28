extends RefCounted
## Same fourteen cameras, reproducible GI/color/effect pairs and warmed GPU measurements.
const Metrics = preload("res://tools/dorm_light_metrics.gd")
var host: Node3D
var light: Node3D
var meter: RefCounted
var manifest: Array[Dictionary] = []
var performance: Array[Dictionary] = []
var failed: int = 0
var view_filter: PackedStringArray
var seconds: float = 2.0
var bench_only: bool = false

func run(owner: Node3D) -> void:
	host = owner;light = host.get("lighting") as Node3D
	bench_only = OS.get_environment("DORM_BENCH_ONLY")=="1"
	if DisplayServer.get_name()=="headless":
		push_error("dorm: свет и GPU измеряются оконным запуском");host.get_tree().quit(1);return
	(host.get("walker") as Node).set_physics_process(false)
	(host.get("hud") as CanvasLayer).hide()
	for label: Node in host.get_tree().get_nodes_in_group("dorm_study_labels"):(label as Node3D).hide()
	RenderingServer.viewport_set_measure_render_time(host.get_viewport().get_viewport_rid(),true)
	RenderingServer.frame_pre_draw.connect(_gpu_begin)
	Engine.max_fps = 0
	meter = Metrics.new(host,host.get("camera") as Camera3D)
	if not OS.get_environment("DORM_BENCH_SECONDS").is_empty():seconds = float(OS.get_environment("DORM_BENCH_SECONDS"))
	var plan: Dictionary = host.get("plan") as Dictionary
	var cases: Array = plan.environment.cases
	var case_filter: PackedStringArray = OS.get_environment("DORM_CASES").split(",",false)
	view_filter = OS.get_environment("DORM_VIEWS").split(",",false)
	for i: int in range(cases.size()):
		var choice: Dictionary = cases[i]
		if not case_filter.is_empty() and String(choice.id) not in case_filter:continue
		print("dorm: LIGHT CASE ",choice.id)
		await light.call("set_case",i)
		light.call("set_cool_corridors",false)
		for leaf: Node in host.get_tree().get_nodes_in_group("dorm_study_doors"):leaf.call("reset_pose")
		for angle: float in [80.0,95.0]:
			host.call("_set_fov",angle)
			for view: Dictionary in plan.shots:
				if not _wanted(view):continue
				if angle==95.0 and String(view.id) not in ["01_corridor","02_room","05_stairs_bottom"]:continue
				_place(view)
				# Settle GI, fog history, one-shot cubemaps and cached local shadows
				# before the image and the timing series.
				await _frames(360 if angle==80 else 120)
				var tag: String = String(choice.id)+("_fov95" if angle==95 else "")
				await _capture(tag,view,angle)
				if angle==80 and String(view.id) in ["01_corridor","02_room","04_wash","05_stairs_bottom","08_street","09_lounge"]:
					await _measure(tag,view)
		if OS.get_environment("DORM_NO_EXTRAS")=="1":continue
		if String(choice.id) in ["evening_A","evening_B","night_A","night_B"]:
			await _colors(String(choice.id),plan.shots)
		if String(choice.id) in ["evening_A","evening_B"]:
			await _effects(String(choice.id),plan.shots)
		if String(choice.id)=="evening_B" and _wanted(plan.shots[0]):
			var saved: Array[VoxelGIData] = []
			for voxel: VoxelGI in light.get("voxels"):
				saved.append(voxel.data);voxel.data = null
			host.call("_set_fov",80.0);_place(plan.shots[0]);await _frames(360)
			await _capture("evening_B_unbaked",plan.shots[0],80)
			await _measure("evening_B_unbaked",plan.shots[0])
			var n: int = 0
			for voxel: VoxelGI in light.get("voxels"):
				voxel.data = saved[n];n += 1
	var output: String = String(host.get("output_dir"))
	if not bench_only:await _save(output.path_join("light_views.json"),manifest)
	await _save(output.path_join("light_performance.json"),{"revision":6,"samples":performance,"engine":Engine.get_version_info().string,
		"gpu":RenderingServer.get_video_adapter_name(),"cpu":OS.get_processor_name(),"viewport":str(host.get_viewport().get_visible_rect().size),
		"vsync":DisplayServer.window_get_vsync_mode(),"lighting_settings":plan.environment,"draw_method":"Series after 360 warm-up frames; mean, median, p95 and range, not one last frame",
		"shadow_count_method":"Frustum upper bound plus occlusion-tested emitter origins and sampled visible receiving surfaces; see each sample.visibility_method",
		"gpu_method":"RenderingDevice frame_pre_draw to viewport end, ns / 1e6; viewport-only time retained", "bake":light.get("bake_report")})
	print("dorm: light shots ",manifest.size()," failed ",failed)
	host.get_tree().quit(failed)

func _colors(tag: String, views: Array) -> void:
	light.call("set_cool_corridors",true)
	for view: Dictionary in views:
		if not _wanted(view) or String(view.id) not in ["01_corridor","05_stairs_bottom","06_stairs_top","10_turn"]:continue
		host.call("_set_fov",80.0);_place(view);await _frames(360)
		await _capture(tag+"_cool",view,80)
		await _measure(tag+"_cool",view)
	light.call("set_cool_corridors",false)

func _effects(tag: String, views: Array) -> void:
	for view: Dictionary in views:
		if not _wanted(view) or String(view.id) not in ["01_corridor","02_room"]:continue
		host.call("_set_fov",80.0);_place(view)
		await _frames(360)
		await _capture(tag+"_effects_control",view,80)
		for effect: String in ["ssil","fog","post"]:
			# Control: SSIL off, dust and grading on.
			light.call("set_effect",effect=="ssil",effect)
			await _frames(360)
			var suffix: String = "ssil_on" if effect=="ssil" else effect+"_off"
			await _capture(tag+"_"+suffix,view,80)
			await _measure(tag+"_"+suffix,view)
			if effect=="ssil":
				var environment: Environment = light.get("environment")
				environment.ssil_intensity = 4.0
				await _frames(120)
				await _capture(tag+"_ssil_strong",view,80)
				await _measure(tag+"_ssil_strong",view)
			light.call("set_effect",effect!="ssil",effect)
		await _frames(360)
		await _capture(tag+"_effects_repeat",view,80)

func _wanted(view: Dictionary) -> bool:return view_filter.is_empty() or String(view.id) in view_filter

func _place(view: Dictionary) -> void:
	var camera: Camera3D = host.get("camera") as Camera3D
	camera.global_position = _vec(view.foot)+Vector3.UP*float(view.eye_height)
	camera.look_at(_vec(view.look),Vector3.UP)
	light.call("update_active_probes")

func _frames(count: int) -> void:
	for i: int in range(count):await host.get_tree().process_frame

func _capture(tag: String, view: Dictionary, angle: float) -> void:
	if bench_only:return
	await RenderingServer.frame_post_draw
	var filename: String = "light_%s_%s.png" % [tag,String(view.id)]
	var error: Error = host.get_viewport().get_texture().get_image().save_png(String(host.get("output_dir")).path_join(filename))
	failed += 1 if error!=OK else 0
	var actual_voxels: Array[Dictionary] = []
	for voxel: VoxelGI in light.get("voxels"):
		if voxel.data!=null:actual_voxels.append({"id":String(voxel.name),"visible":voxel.visible,"energy":voxel.data.energy,"interior":voxel.data.interior})
	var sun: DirectionalLight3D = light.get("sun")
	manifest.append({"file":filename,"id":view.id,"case":tag,"foot":view.foot,"look":view.look,"eye_height":view.eye_height,
		"fov_h":angle,"fov_v":(host.get("camera") as Camera3D).fov,"ssil":light.get("ssil"),"fog":light.get("fog"),
		"post":light.get("post"),"cool_corridors":light.get("cool_corridors"),"tonemap":"Filmic","revision":6,
		"sdfgi_actual":(light.get("environment") as Environment).sdfgi_enabled,"quality_setting":Settings.quality,"voxel_actual":actual_voxels,
		"shadow_atlas":4096,"shadow_tiles_per_quadrant":[16,16,16,16],
		"sun":{"energy":sun.light_energy,"color":str(sun.light_color),"rotation":str(sun.rotation_degrees),"pcss_angle":sun.light_angular_distance}})
	print("dorm: light shot ",filename," error ",error)

func _measure(tag: String, view: Dictionary) -> void:
	var sample: Dictionary = await meter.call("sample",seconds)
	sample.merge(meter.call("visibility"),true)
	sample["case"] = tag;sample["view"] = view.id
	performance.append(sample)
	print("dorm: PERF ",tag," ",view.id," FPS=",sample.fps," GPU=",sample.gpu_frame_ms," draws=",sample.draw_calls_median)

static func _vec(at: Array) -> Vector3:return Vector3(float(at[0]),float(at[1]),float(at[2]))

func _save(path: String, data: Variant) -> void:
	# Write a complete new file first; preserve it if a desktop reader briefly locks
	# the existing JSON on Windows. Failed metadata is a failed capture, not success.
	var absolute: String = ProjectSettings.globalize_path(path)
	var temporary: String = absolute+".r6.tmp"
	var file: FileAccess = FileAccess.open(temporary,FileAccess.WRITE)
	if file==null:
		failed += 1;push_error("dorm: cannot save "+temporary+" "+error_string(FileAccess.get_open_error()));return
	file.store_string(JSON.stringify(data,"\t"));file.close()
	for attempt: int in range(10):
		if DirAccess.rename_absolute(temporary,absolute)==OK:return
		await host.get_tree().create_timer(.1).timeout
	failed += 1;push_error("dorm: output locked; complete metadata retained at "+temporary)

func _gpu_begin() -> void:
	RenderingServer.call_on_render_thread(func() -> void: RenderingServer.get_rendering_device().capture_timestamp("dorm_frame_start"))
