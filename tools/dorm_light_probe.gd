extends SceneTree
## Reproducible one-variable lighting experiments, separate from the owner's comparison shots.
const Metrics = preload("res://tools/dorm_light_metrics.gd")
var world: Node3D
var camera: Camera3D
var lighting: Node3D
var plan: Dictionary
var output: String
var results: Array[Dictionary] = []

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	Engine.max_fps = 0
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	output = OS.get_environment("DORM_DIAG_OUTPUT")
	if output.is_empty():output = ProjectSettings.globalize_path("res://_asset_src/dorm_light_r6/diagnostics")
	DirAccess.make_dir_recursive_absolute(output)
	if OS.get_environment("DORM_MATERIAL_AUDIT")=="1":
		await _material_audit()
		quit();return
	plan = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json")) as Dictionary
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(),true)
	RenderingServer.frame_pre_draw.connect(_begin)
	var input: String = OS.get_environment("DORM_DIAG_CONFIG")
	if input.is_empty():input = "res://_asset_src/dorm_light_r6/probe_cases.json"
	var trials: Array = JSON.parse_string(FileAccess.get_file_as_string(input)) as Array
	for trial: Dictionary in trials:
		world = (load("res://scenes/levels/dorm_study.tscn") as PackedScene).instantiate() as Node3D
		root.add_child(world)
		for node: Node in get_nodes_in_group("dorm_study_labels"):(node as Node3D).hide()
		camera = Camera3D.new();world.add_child(camera);camera.current = true;camera.far = 250.0
		lighting = world.get_node("Lighting")
		lighting.call("attach_camera",camera)
		lighting.set_process(bool(trial.get("controller_process",false)))
		var config: Dictionary = lighting.get("config")
		var index: int = 0
		for i: int in range(config.cases.size()):
			if String(config.cases[i].id)==String(trial.get("case","evening_A")):index = i
		await lighting.call("set_case",index)
		if bool(trial.get("prewalk",false)):
			for previous: Dictionary in plan.shots:
				camera.global_position = _vec(previous.foot)+Vector3.UP*float(previous.eye_height);camera.look_at(_vec(previous.look),Vector3.UP)
				lighting.call("update_active_probes");await _frames(90)
			lighting.call("set_cool_corridors",true);await _frames(120)
			lighting.call("set_cool_corridors",false);await _frames(120)
			lighting.call("set_effect",true,"ssil");await _frames(120)
			lighting.call("set_effect",false,"ssil");await _frames(120)
		# VoxelGIData is cached across scene instances: each trial starts from authored values.
		for voxel: VoxelGI in lighting.get("voxels"):
			if voxel.data!=null:
				voxel.data.energy = float(config.voxel.energy)
				voxel.data.interior = bool(config.voxel.get("interior",false))
		var metrics: RefCounted = Metrics.new(world,camera)
		for view: Dictionary in plan.shots:
			if String(view.id) not in trial.get("views",["01_corridor"]):continue
			camera.global_position = _vec(view.foot)+Vector3.UP*float(view.eye_height)
			camera.look_at(_vec(view.look),Vector3.UP)
			var viewport: Vector2 = root.get_visible_rect().size
			camera.fov = rad_to_deg(2.0*atan(tan(deg_to_rad(80.0)/2.0)/(viewport.x/viewport.y)))
			lighting.call("update_active_probes")
			_apply(trial.get("override",{}))
			await _frames(int(trial.get("warm_frames",300)))
			var sample: Dictionary = await metrics.call("sample",float(trial.get("seconds",1.0)))
			sample.merge(metrics.call("visibility"),true)
			sample["trial"] = trial.id;sample["view"] = view.id
			sample["override"] = trial.get("override",{})
			sample["voxel_light_candidates"] = _voxel_light_candidates()
			sample["voxel_data"] = []
			for voxel: VoxelGI in lighting.get("voxels"):
				if voxel.data!=null:(sample.voxel_data as Array).append({"id":voxel.name,"position":str(voxel.global_position),"size":str(voxel.size),"bounds":str(voxel.data.get_bounds()),"energy":voxel.data.energy,"interior":voxel.data.interior,"bias":voxel.data.bias,"normal_bias":voxel.data.normal_bias})
			await RenderingServer.frame_post_draw
			var image: Image = root.get_texture().get_image()
			var file: String = String(trial.id)+"__"+String(view.id)+".png"
			image.save_png(output.path_join(file));sample["file"] = file
			results.append(sample)
			_save()
			print("DORM_DIAG ",trial.id," ",view.id," draws median=",sample.draw_calls_median," max=",sample.draw_calls_max," GPU=",sample.gpu_frame_ms)
		world.queue_free();await _frames(8)
	_save();quit()

func _apply(overrides: Dictionary) -> void:
	if overrides.has("atlas_quadrants"):
		for i: int in range(4):root.set("positional_shadow_atlas_quad_"+str(i),int(overrides.atlas_quadrants[i]))
	if overrides.has("post"):lighting.call("set_effect",bool(overrides.post),"post")
	var env: Environment = lighting.get("environment")
	if overrides.has("fog"):env.volumetric_fog_enabled = bool(overrides.fog)
	if overrides.has("fog_density"):env.volumetric_fog_density = float(overrides.fog_density)
	if overrides.has("sun_fog_energy"):(lighting.get("sun") as DirectionalLight3D).light_volumetric_fog_energy = float(overrides.sun_fog_energy)
	if overrides.has("local_dust"):
		var volume: FogVolume = FogVolume.new();volume.position = Vector3(3.8,5.92,0);volume.size = Vector3(7.4,2.9,3.25)
		var material: FogMaterial = FogMaterial.new();material.density = float(overrides.local_dust);material.edge_fade = .1;material.albedo = Color("e6e3db")
		volume.material = material;world.add_child(volume)
	if overrides.has("ssr"):env.ssr_enabled = bool(overrides.ssr)
	if overrides.has("ambient"):env.ambient_light_energy = float(overrides.ambient)
	if overrides.has("ssil"):env.ssil_enabled = bool(overrides.ssil)
	if overrides.has("ssil_intensity"):env.ssil_intensity = float(overrides.ssil_intensity)
	if overrides.has("sdfgi_bias"):env.sdfgi_normal_bias = float(overrides.sdfgi_bias)
	if overrides.has("sdfgi"):env.sdfgi_enabled = bool(overrides.sdfgi)
	for voxel: VoxelGI in lighting.get("voxels"):
		if overrides.has("voxel"):voxel.visible = bool(overrides.voxel) and voxel.data!=null
		if overrides.has("only_voxel_ids"):voxel.visible = String(voxel.name) in overrides.only_voxel_ids
		if voxel.data!=null:
			if overrides.has("interior"):voxel.data.interior = bool(overrides.interior)
			if overrides.has("voxel_energy"):voxel.data.energy = float(overrides.voxel_energy)
			if overrides.has("voxel_normal_bias"):voxel.data.normal_bias = float(overrides.voxel_normal_bias)
			if overrides.has("voxel_bias"):voxel.data.bias = float(overrides.voxel_bias)
	if overrides.has("sun_energy"):(lighting.get("sun") as DirectionalLight3D).light_energy = float(overrides.sun_energy)
	if overrides.has("sun_angular_distance"):(lighting.get("sun") as DirectionalLight3D).light_angular_distance = float(overrides.sun_angular_distance)
	if overrides.get("helpers_direct_only",false):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			var lamp: Light3D = node as Light3D
			if lamp.is_in_group("dorm_window_sky") or not lamp.shadow_enabled:lamp.light_bake_mode = Light3D.BAKE_DISABLED
	if overrides.get("windows",true)==false:
		for node: Node in get_nodes_in_group("dorm_window_sky"):(node as Light3D).hide()
	if overrides.get("probes",true)==false:
		for node: Node in get_nodes_in_group("dorm_reflections"):(node as ReflectionProbe).hide()
	if overrides.get("lamps",true)==false:
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if not node.is_in_group("dorm_window_sky"):(node as Light3D).hide()
	if overrides.has("stair_energy"):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if String(node.get_meta("light_group",""))=="stairs":(node as Light3D).light_energy = float(overrides.stair_energy)
	if overrides.has("stair_shadows"):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if String(node.get_meta("light_group",""))=="stairs":(node as Light3D).shadow_enabled = bool(overrides.stair_shadows)
	if overrides.has("window_shadows"):
		for node: Node in get_nodes_in_group("dorm_window_sky"):(node as Light3D).shadow_enabled = bool(overrides.window_shadows)
	if overrides.has("window_normal_bias"):
		for node: Node in get_nodes_in_group("dorm_window_sky"):(node as Light3D).shadow_normal_bias = float(overrides.window_normal_bias)
	if overrides.has("window_bias"):
		for node: Node in get_nodes_in_group("dorm_window_sky"):(node as Light3D).shadow_bias = float(overrides.window_bias)
	if overrides.has("window_shadow_blur"):
		for node: Node in get_nodes_in_group("dorm_window_sky"):(node as Light3D).shadow_blur = float(overrides.window_shadow_blur)
	if overrides.has("stair_at"):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if String(node.get_meta("light_group",""))=="stairs" and node.position.y<4.0:node.position = _vec(overrides.stair_at)
	if overrides.has("watch_at"):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if String(node.get_meta("light_group",""))=="watch":node.position = _vec(overrides.watch_at)
	if overrides.has("watch_energy"):
		for node: Node in get_nodes_in_group("dorm_lamps"):
			if String(node.get_meta("light_group",""))=="watch":(node as Light3D).light_energy = float(overrides.watch_energy)
	if overrides.get("glass_shaded",false):_shade_glass(world)

func _shade_glass(node: Node) -> void:
	if node is MeshInstance3D and String(node.name).begins_with("Mesh_glass"):
		var mesh: MeshInstance3D = node as MeshInstance3D
		for s: int in range(mesh.mesh.get_surface_count()):
			var material: StandardMaterial3D = mesh.get_active_material(s).duplicate() as StandardMaterial3D
			material.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
			mesh.set_surface_override_material(s,material)
	for child: Node in node.get_children():_shade_glass(child)

func _save() -> void:
	var file: FileAccess = FileAccess.open(output.path_join("results.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"engine":Engine.get_version_info().string,"gpu":RenderingServer.get_video_adapter_name(),"samples":results},"\t"))
	file.close()

func _frames(count: int) -> void:
	for i: int in range(count):await process_frame

func _begin() -> void:
	RenderingServer.call_on_render_thread(func() -> void: RenderingServer.get_rendering_device().capture_timestamp("dorm_probe_start"))

static func _vec(at: Array) -> Vector3:return Vector3(float(at[0]),float(at[1]),float(at[2]))

func _material_audit() -> void:
	var holder: Node3D = Node3D.new();root.add_child(holder)
	var box: MeshInstance3D = MeshInstance3D.new()
	box.mesh = BoxMesh.new();box.gi_mode = GeometryInstance3D.GI_MODE_STATIC;holder.add_child(box)
	var voxel: VoxelGI = VoxelGI.new();voxel.size = Vector3(3,3,3);voxel.subdiv = VoxelGI.SUBDIV_64;holder.add_child(voxel)
	var signatures: Dictionary = {}
	for kind: String in ["shader_green","shader_white","standard_green"]:
		if kind.begins_with("shader"):
			var shader: Shader = Shader.new()
			shader.code = "shader_type spatial; void fragment(){ ALBEDO=vec3(%s); }" % ("0.1,0.2,0.05" if kind=="shader_green" else "1.0")
			var material: ShaderMaterial = ShaderMaterial.new();material.shader = shader;box.material_override = material
		else:
			var material: StandardMaterial3D = StandardMaterial3D.new();material.albedo_color = Color("59654c");box.material_override = material
		await process_frame
		voxel.bake(holder)
		var hash: HashingContext = HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(voxel.data.get_data_cells())
		signatures[kind] = {"sha256":hash.finish().hex_encode(),"bytes":voxel.data.get_data_cells().size()}
	var report: Dictionary = {"engine":Engine.get_version_info().string,"signatures":signatures,
		"shader_colors_identical_in_bake":signatures.shader_green.sha256==signatures.shader_white.sha256,
		"standard_differs":signatures.standard_green.sha256!=signatures.shader_green.sha256}
	var file: FileAccess = FileAccess.open(output.path_join("material_audit.json"),FileAccess.WRITE);file.store_string(JSON.stringify(report,"\t"));file.close()
	print("DORM_MATERIAL_AUDIT ",JSON.stringify(report))
	holder.queue_free();await process_frame

func _voxel_light_candidates() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for voxel: VoxelGI in lighting.get("voxels"):
		if not voxel.visible:continue
		var bounds: AABB = voxel.global_transform*voxel.get_aabb()
		var names: Array[String] = []
		for node: Node in get_nodes_in_group("dorm_lamps"):
			var lamp: Light3D = node as Light3D
			if lamp.is_visible_in_tree() and lamp.light_bake_mode!=Light3D.BAKE_DISABLED and bounds.intersects(lamp.global_transform*lamp.get_aabb()):names.append(String(lamp.name))
		result.append({"id":String(voxel.name),"local_aabb_candidates":names.size(),"sun_appended_after_locals":(lighting.get("sun") as DirectionalLight3D).visible,
			"limit":32,"locals":names})
	return result
