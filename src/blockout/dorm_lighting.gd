@tool
extends Node3D
## Собственный пробный свет общежития из dorm.json. Вокселизуется геометрия, источники динамические.
const VoxelBake = preload("res://src/blockout/dorm_voxel_bake.gd")

var plan: Dictionary = {}
var config: Dictionary = {}
var environment: Environment
var sun: DirectionalLight3D
var camera: Camera3D
var case_index: int = 0
var ssil: bool = false
var fog: bool = true
var post: bool = true
var voxels: Array[VoxelGI] = []
var layers: Array[CanvasLayer] = []
var busy: bool = false
var bake_report: Dictionary = {}
var state_label: Label
var probe_timer: float = 0.0
var cool_corridors: bool = false
var cool_toggle: CheckButton
var dust: Array[FogVolume] = []
var moon: DirectionalLight3D
var night_exterior: bool = false
var night_toggle: CheckButton
## Свет «как в Таркове» (F9; основной с 2026-10-31 — environment.tarkov, числа — tools/dorm_lighting_data.py): у них
## в помещениях художник задаёт каждой зоне нижний уровень окружения, а окна и проёмы — порталы уличного света (80.lv,
## разбор технологий EFT). Здесь то же своими средствами: в каждом помещении и вдоль коридоров — невидимая слабая
## подсветка без теней и бликов, вне VoxelGI; окна ярче, свет неба и экспозиция немного выше. Ночью подсветка тусклая
## и холодная, в окнах — слабый лунный свет (times.night).
var tarkov_cfg: Dictionary = {}
var tarkov: bool = false
var tarkov_toggle: CheckButton
var tarkov_fills: Array[OmniLight3D] = []


func _ready() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json"))
	if not parsed is Dictionary or not (parsed as Dictionary).has("environment"):
		return
	plan = parsed as Dictionary
	config = plan.environment
	environment = Environment.new()
	environment.set_meta("authored_lighting",true)
	(get_parent().get_node("WorldEnvironment") as WorldEnvironment).environment = environment
	sun = get_parent().get_node("StudySun") as DirectionalLight3D
	sun.light_bake_mode = Light3D.BAKE_DYNAMIC
	# PCSS at this low sun leaked through closed rooms onto the corridor floor.
	# Keep the same solar direction/color/energy; filtered hard shadows respect the roof.
	sun.light_angular_distance = 0.0
	sun.directional_shadow_max_distance = 90.0
	sun.shadow_bias = 0.025
	sun.shadow_normal_bias = 0.5
	moon = DirectionalLight3D.new()
	moon.name = "StudyMoon"
	moon.hide()
	add_child(moon)
	moon.sky_mode = DirectionalLight3D.SKY_MODE_LIGHT_ONLY
	moon.light_bake_mode = Light3D.BAKE_DYNAMIC
	moon.shadow_enabled = true
	moon.shadow_bias = .025
	moon.shadow_normal_bias = .5
	moon.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	moon.light_angular_distance = 0.0
	moon.light_volumetric_fog_energy = .1
	ssil = bool(config.effects.ssil)
	fog = bool(config.effects.fog)
	post = bool(config.effects.post)
	night_exterior = bool(config.night_exterior.get("default",false))
	tarkov_cfg = config.get("tarkov",{}) as Dictionary
	if bool(tarkov_cfg.get("default",false)):
		tarkov = true
		_create_tarkov_fills()
	_configure_meshes(get_parent())
	for probe: Node in get_tree().get_nodes_in_group("dorm_reflections"):
		(probe as ReflectionProbe).hide()
	for item: Dictionary in config.voxel.volumes:
		var voxel: VoxelGI = VoxelGI.new()
		voxel.name = String(item.id)
		voxel.position = _vec(item.at)
		voxel.size = _vec(item.size)
		voxel.subdiv = int(config.voxel.subdiv)
		voxel.hide()
		add_child(voxel)
		voxels.append(voxel)
	_create_dust()
	_apply()
	if not Engine.is_editor_hint():
		get_viewport().positional_shadow_atlas_size = int(config.shadow_atlas)
		# 43 influence spheres can enter the corridor frustum. The default atlas has
		# only 16 medium tiles and thrashes after view changes. 64 equal tiles retain
		# these static shadows; both GI methods use the same 4096 atlas and 512 tiles.
		var subdivisions: Dictionary = {0:0,1:1,4:2,16:3,64:4,256:5,1024:6}
		for i: int in range(4):
			get_viewport().set("positional_shadow_atlas_quad_"+str(i),subdivisions[int(config.shadow_quadrants[i])])


func _configure_meshes(root: Node) -> void:
	for child: Node in root.get_children():
		if child is GeometryInstance3D:
			var mesh: GeometryInstance3D = child as GeometryInstance3D
			var ancestor: Node = child.get_parent()
			var door: bool = false
			while ancestor != null and ancestor != get_parent():
				door = door or ancestor.is_in_group("dorm_study_doors")
				ancestor = ancestor.get_parent()
			# Двери не входят в неподвижную сетку GI; прямые тени остаются подвижными.
			mesh.gi_mode = GeometryInstance3D.GI_MODE_DISABLED if door else GeometryInstance3D.GI_MODE_STATIC
			if child is Label3D or String(child.name).begins_with("Mesh_glass") or child.is_in_group("dorm_mirrors"):
				mesh.gi_mode = GeometryInstance3D.GI_MODE_DISABLED
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_configure_meshes(child)


func attach_camera(value: Camera3D) -> void:
	camera = value
	update_active_probes()
	var attributes: CameraAttributesPractical = CameraAttributesPractical.new()
	attributes.auto_exposure_enabled = false
	camera.attributes = attributes
	for shader_path: String in ["res://src/blockout/dorm_post.gdshader","res://src/world/screen_sharpen.gdshader"]:
		var layer: CanvasLayer = CanvasLayer.new()
		layer.name = "DormPost" if layers.is_empty() else "DormSharpen"
		layer.layer = -3+layers.size()
		var copy: BackBufferCopy = BackBufferCopy.new()
		copy.copy_mode = BackBufferCopy.COPY_MODE_VIEWPORT
		layer.add_child(copy)
		var rect: ColorRect = ColorRect.new()
		rect.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var material: ShaderMaterial = ShaderMaterial.new()
		material.shader = load(shader_path) as Shader
		if layers.is_empty():
			material.set_shader_parameter("grain",float(config.effects.grain))
			material.set_shader_parameter("vignette",float(config.effects.vignette))
		else:
			material.set_shader_parameter("amount",float(config.effects.sharpen))
		rect.material = material
		layer.add_child(rect)
		add_child(layer)
		layers.append(layer)
	_apply()


func _process(delta: float) -> void:
	if not is_instance_valid(camera):
		return
	probe_timer += delta
	if probe_timer>0.25:
		probe_timer = 0.0
		update_active_probes()


func update_active_probes() -> void:
	if not is_instance_valid(camera):
		return
	var windows_enabled: bool = bool(config.cases[case_index].get("windows",true))
	var window_energy: float = _window_energy()
	for node: Node in get_tree().get_nodes_in_group("dorm_window_sky"):
		var window: Light3D = node as Light3D
		window.visible = windows_enabled and window_energy>0 and absf(window.global_position.y-camera.global_position.y)<2.2
	var nearby: Array[ReflectionProbe] = []
	for node: Node in get_tree().get_nodes_in_group("dorm_reflections"):
		var probe: ReflectionProbe = node as ReflectionProbe
		var offset: Vector3 = probe.global_position-camera.global_position
		if absf(offset.y)<2.2 and Vector2(offset.x,offset.z).length()<25.0:
			nearby.append(probe)
		else:
			_set_probe_active(probe,false)
	nearby.sort_custom(func(a: ReflectionProbe,b: ReflectionProbe) -> bool: return a.global_position.distance_squared_to(camera.global_position)<b.global_position.distance_squared_to(camera.global_position))
	for i: int in range(nearby.size()):
		_set_probe_active(nearby[i],i<int(config.active_reflection_limit))


## Атлас отражений держит 64 зонда, и скрытый зонд (hide) своё место не отдаёт: за прогулку по этажам и лестнице
## показанных из 90 зондов стенда набиралось больше 64 — «Reflection probe atlas index invalid» и падение Godot.
## У неактивного зонда на сервере отрисовки снимается основа: место в атласе и очередь съёмки освобождаются (снятие со
## сцены оставляло его в очереди — «scenario is null»); вернувшийся снимает комнату заново.
func _set_probe_active(probe: ReflectionProbe, active: bool) -> void:
	probe.visible = active
	if bool(probe.get_meta("dorm_probe_attached",true))==active:
		return
	RenderingServer.instance_set_base(probe.get_instance(),probe.get_base() if active else RID())
	probe.set_meta("dorm_probe_attached",active)


func create_controls(parent: Control) -> void:
	var panel: ColorRect = ColorRect.new()
	panel.color = Color(0.03,0.04,0.05,0.86)
	panel.position = Vector2(18,146)
	panel.size = Vector2(1420,154)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(panel)
	for i: int in range(config.cases.size()):
		var button: Button = Button.new()
		button.text = String(config.cases[i].label)
		button.position = Vector2(30+(i%3)*380,153+(i/3)*38)
		button.size = Vector2(366,32)
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(set_case.bind(i))
		parent.add_child(button)
	for i: int in range(3):
		var toggle: CheckButton = CheckButton.new()
		toggle.text = ["SSIL","Пыль в лучах","Обработка кадра"][i]
		toggle.position = Vector2(30+i*230,234)
		toggle.focus_mode = Control.FOCUS_NONE
		toggle.button_pressed = [ssil,fog,post][i]
		toggle.toggled.connect(set_effect.bind(["ssil","fog","post"][i]))
		parent.add_child(toggle)
	cool_toggle = CheckButton.new()
	cool_toggle.text = "F5 · Холодные коридоры · 4400 K"
	cool_toggle.position = Vector2(730,234)
	cool_toggle.focus_mode = Control.FOCUS_NONE
	cool_toggle.toggled.connect(set_cool_corridors)
	parent.add_child(cool_toggle)
	state_label = Label.new()
	state_label.position = Vector2(30,275)
	state_label.add_theme_font_size_override("font_size",15)
	parent.add_child(state_label)
	night_toggle = CheckButton.new()
	night_toggle.text = "F8 · Ночная улица · луна"
	night_toggle.position = Vector2(730,270)
	night_toggle.focus_mode = Control.FOCUS_NONE
	night_toggle.button_pressed = night_exterior
	night_toggle.toggled.connect(set_night_exterior)
	parent.add_child(night_toggle)
	tarkov_toggle = CheckButton.new()
	tarkov_toggle.text = "F9 · Как в Таркове (зоны окружения)"
	# правее подписи «холодных коридоров»: на 960 текст двух переключателей наезжал друг на друга
	tarkov_toggle.position = Vector2(1070,234)
	tarkov_toggle.focus_mode = Control.FOCUS_NONE
	tarkov_toggle.button_pressed = tarkov
	tarkov_toggle.toggled.connect(set_tarkov)
	parent.add_child(tarkov_toggle)
	_update_label()


func set_effect(enabled: bool, effect: String) -> void:
	match effect:
		"ssil": ssil = enabled
		"fog": fog = enabled
		"post": post = enabled
	_apply()

func set_cool_corridors(enabled: bool) -> void:
	if cool_corridors==enabled:return
	cool_corridors = enabled
	if is_instance_valid(cool_toggle):cool_toggle.set_pressed_no_signal(enabled)
	_apply_lamp_colors()
	await refresh_reflections()
	_update_label()

func set_night_exterior(enabled: bool) -> void:
	if night_exterior==enabled:return
	night_exterior = enabled
	if is_instance_valid(night_toggle):night_toggle.set_pressed_no_signal(enabled)
	_apply()
	await refresh_reflections()

func set_tarkov(enabled: bool) -> void:
	if tarkov==enabled or tarkov_cfg.is_empty():return
	tarkov = enabled
	if is_instance_valid(tarkov_toggle):tarkov_toggle.set_pressed_no_signal(enabled)
	if tarkov and tarkov_fills.is_empty():
		_create_tarkov_fills()
	_apply()
	await refresh_reflections()


## Поправки «как в Таркове» для времени суток текущего случая (подсветка, её цвет, лунный свет в окнах).
func _tarkov_time() -> Dictionary:
	return (tarkov_cfg.get("times",{}) as Dictionary).get(String(config.cases[case_index].time),{}) as Dictionary


## Сила оконного света: ночью у времени суток её нет, «как в Таркове» в окнах остаётся слабый лунный свет.
func _window_energy() -> float:
	var energy: float = float(config.times[String(config.cases[case_index].time)].window_energy)
	if not tarkov:
		return energy
	return maxf(energy*float(tarkov_cfg.window),float(_tarkov_time().get("window",0.0)))


## Подсветка-«зона окружения»: по одной в каждом помещении плана и цепочкой вдоль коридоров каждого этажа.
## Без теней (светит ровно, как окружение), без бликов (не выдаёт себя на глянце), не входит в VoxelGI (не
## отражается от стен второй раз и не меняет запечённое).
func _create_tarkov_fills() -> void:
	var floors: Dictionary = {}
	for space: Dictionary in plan.spaces:
		var rect: Array = space.rect
		var size: Vector2 = Vector2(float(rect[2])-float(rect[0]),float(rect[3])-float(rect[1]))
		var kind: String = String(space.kind)
		var wet: bool = kind in ["toilets","showers","wash","laundry"]
		var energy: float = float(tarkov_cfg.wet) if wet else float(tarkov_cfg.room)
		_tarkov_fill(Vector3((float(rect[0])+float(rect[2]))*.5,float(space.y)+float(tarkov_cfg.height),(float(rect[1])+float(rect[3]))*.5),
			size.length()*float(tarkov_cfg.range_scale)+0.8,energy,Color(String(tarkov_cfg.room_color)))
		floors[int(space.floor)] = float(space.y)
	# коридоры: основной — посередине основного корпуса вдоль X, пристройка — вдоль Z
	var main: Array = plan.main_rect
	var annex: Array = plan.annex_rect
	for y: float in floors.values():
		var x: float = float(main[0])+1.5
		while x<float(main[2])-1.0:
			_tarkov_fill(Vector3(x,y+float(tarkov_cfg.height),0.0),4.2,float(tarkov_cfg.corridor),Color(String(tarkov_cfg.corridor_color)))
			x += float(tarkov_cfg.corridor_step)
		var z: float = float(annex[1])+1.5
		while z<float(annex[3])-0.5:
			_tarkov_fill(Vector3((float(annex[0])+float(annex[2]))*.5,y+float(tarkov_cfg.height),z),4.2,float(tarkov_cfg.corridor),
				Color(String(tarkov_cfg.corridor_color)))
			z += float(tarkov_cfg.corridor_step)


func _tarkov_fill(at: Vector3, light_range: float, energy: float, color: Color) -> void:
	var fill: OmniLight3D = OmniLight3D.new()
	fill.name = "TarkovFill%d" % tarkov_fills.size()
	fill.position = at
	fill.omni_range = light_range
	fill.omni_attenuation = float(tarkov_cfg.attenuation)
	fill.light_energy = energy
	fill.light_color = color
	fill.set_meta("base_energy",energy)
	fill.set_meta("base_color",color)
	fill.light_specular = 0.0
	fill.shadow_enabled = false
	fill.light_bake_mode = Light3D.BAKE_DISABLED
	fill.light_volumetric_fog_energy = 0.0
	fill.add_to_group("dorm_tarkov_fill")
	add_child(fill)
	tarkov_fills.append(fill)


func _apply_lamp_colors() -> void:
	for node: Node in get_tree().get_nodes_in_group("dorm_lamps"):
		var lamp: Light3D = node as Light3D
		if not lamp.has_meta("warm_color"):lamp.set_meta("warm_color",lamp.light_color)
		var group: String = String(lamp.get_meta("light_group",""))
		var cool: bool = cool_corridors and group in ["main_corridor","annex_corridor","stairs","services"]
		lamp.light_color = Color(String(config.cool_corridors.color)) if cool else lamp.get_meta("warm_color") as Color
		if tarkov and group=="window_sky" and _tarkov_time().has("window_color"):
			lamp.light_color = Color(String(_tarkov_time().window_color))
		lamp.set_meta("selected_kelvin",int(config.cool_corridors.kelvin) if cool else (4500 if group in ["wet_rooms","window_sky"] else 2850))


func set_case(index: int) -> void:
	if busy:
		return
	busy = true
	if String(config.cases[index].gi)=="B" and not await ensure_baked():
		busy = false
		return
	busy = true
	environment.sdfgi_enabled = false
	await get_tree().process_frame
	case_index = index
	_apply()
	await refresh_reflections()
	busy = false
	_update_label()


func _apply() -> void:
	if config.is_empty():
		return
	var choice: Dictionary = config.cases[case_index]
	var time: Dictionary = config.times[String(choice.time)]
	var sky_material: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
	sky_material.sky_top_color = Color(String(time.sky_top))
	sky_material.sky_horizon_color = Color(String(time.sky_horizon))
	sky_material.ground_bottom_color = Color("141a20") if String(choice.time)!="night" else Color.BLACK
	sky_material.ground_horizon_color = Color(String(time.sky_horizon))*0.45
	sky_material.sun_angle_max = 12.0
	var sky: Sky = Sky.new()
	sky.sky_material = sky_material
	environment.background_mode = Environment.BG_SKY
	environment.sky = sky
	environment.background_energy_multiplier = float(time.background_energy)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	environment.ambient_light_color = Color("718aa2")
	environment.ambient_light_energy = float(time.ambient)*(float(tarkov_cfg.ambient) if tarkov else 1.0)
	environment.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	# The grading switch must not also change camera exposure or the highlight curve.
	environment.tonemap_mode = int(config.effects.tonemap_mode)
	environment.tonemap_exposure = float(time.exposure)*(float(tarkov_cfg.exposure) if tarkov else 1.0)
	environment.ssao_enabled = true
	environment.ssao_radius = float(config.effects.ssao_radius)
	environment.ssao_intensity = float(config.effects.ssao_intensity)
	environment.ssil_enabled = ssil
	environment.ssil_radius = float(config.effects.ssil_radius)
	environment.ssil_intensity = float(config.effects.ssil_intensity)
	environment.ssr_enabled = true
	environment.ssr_max_steps = 96
	environment.sdfgi_enabled = String(choice.gi)=="A"
	environment.sdfgi_use_occlusion = true
	environment.sdfgi_read_sky_light = String(choice.time)!="night"
	environment.sdfgi_min_cell_size = float(config.sdfgi.min_cell_size)
	environment.sdfgi_cascades = int(config.sdfgi.cascades)
	environment.sdfgi_energy = float(config.sdfgi.energy)
	environment.sdfgi_bounce_feedback = float(config.sdfgi.bounce_feedback)
	environment.sdfgi_normal_bias = float(config.sdfgi.normal_bias)
	environment.sdfgi_probe_bias = float(config.sdfgi.probe_bias)
	environment.volumetric_fog_enabled = fog
	environment.volumetric_fog_density = float(config.effects.fog_density)
	environment.volumetric_fog_length = float(config.effects.fog_length)
	environment.volumetric_fog_albedo = Color("a4adb5")
	environment.volumetric_fog_ambient_inject = 0.0
	environment.volumetric_fog_sky_affect = 0.0
	environment.volumetric_fog_anisotropy = float(config.effects.get("fog_anisotropy",.15))
	for volume: FogVolume in dust:volume.visible = fog
	environment.glow_enabled = post
	environment.glow_intensity = .12
	environment.glow_hdr_threshold = 2.0
	environment.adjustment_enabled = post
	environment.adjustment_saturation = float(config.effects.saturation)
	var gradient: Gradient = Gradient.new()
	gradient.offsets = PackedFloat32Array([0,.25,.5,.75,1])
	var colors: PackedColorArray = PackedColorArray()
	for rgb: Array in config.effects.lut:
		colors.append(Color(float(rgb[0]),float(rgb[1]),float(rgb[2])))
	gradient.colors = colors
	var table: GradientTexture1D = GradientTexture1D.new()
	table.gradient = gradient
	table.width = 256
	environment.adjustment_color_correction = table
	sun.rotation_degrees = _vec(time.sun_rotation)
	sun.light_energy = float(time.sun_energy)
	sun.visible = float(time.sun_energy)>0
	sun.light_color = Color(String(time.sun_color))
	sun.shadow_enabled = true
	sun.light_bake_mode = Light3D.BAKE_DYNAMIC
	sun.light_volumetric_fog_energy = float(config.effects.get("sun_fog_energy",1.0))
	sun.directional_shadow_max_distance = float(config.sun_shadows.distance)
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS if int(config.sun_shadows.cascades)==2 else DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	moon.light_energy = float(config.night_exterior.energy)
	moon.light_color = Color(String(config.night_exterior.color))
	moon.rotation_degrees = _vec(config.night_exterior.rotation)
	moon.directional_shadow_max_distance = float(config.night_exterior.shadow_distance)
	moon.visible = night_exterior and String(choice.time)=="night"
	for node: Node in get_tree().get_nodes_in_group("dorm_lamps"):
		var local: Light3D = node as Light3D
		# Direct sky stand-ins must not double-inject sky into GI. Unshadowed fills
		# must not bounce through walls. Same rule in A/B, and <32 lights per VoxelGI
		# leaves room for the sun (Godot appends directionals after local lights).
		local.light_bake_mode = Light3D.BAKE_DYNAMIC if local.shadow_enabled and not node.is_in_group("dorm_window_sky") else Light3D.BAKE_DISABLED
		if node.is_in_group("dorm_window_sky"):
			(node as Light3D).light_energy = _window_energy()
			(node as Light3D).visible = _window_energy()>0
		(node as Light3D).light_volumetric_fog_energy = 0.0 if node.is_in_group("dorm_window_sky") else .25
	_apply_lamp_colors()
	var tarkov_time: Dictionary = _tarkov_time()
	for fill: OmniLight3D in tarkov_fills:
		fill.visible = tarkov
		fill.light_energy = float(fill.get_meta("base_energy"))*float(tarkov_time.get("fill",1.0))
		fill.light_color = Color(String(tarkov_time.color)) if tarkov_time.has("color") else fill.get_meta("base_color") as Color
	for voxel: VoxelGI in voxels:
		_apply_voxel_data(voxel)
		voxel.visible = String(choice.gi)=="B" and voxel.data!=null
	for layer: CanvasLayer in layers:
		layer.visible = post
	update_active_probes()
	_update_label()


func _update_label() -> void:
	if is_instance_valid(state_label):
		state_label.text = "Обновляется освещение…" if busy else "%s%s · %s · атлас %d" % [String(config.cases[case_index].label),
			" · как в Таркове" if tarkov else "","Filmic" if post else "без обработки",int(config.shadow_atlas)]


func refresh_reflections() -> void:
	if DisplayServer.get_name()=="headless":
		return
	for probe: Node in get_tree().get_nodes_in_group("dorm_reflections"):
		# Смена времени должна обновить и комнаты, в которые камера зайдёт позже.
		var shift: float = -.0001 if bool(probe.get_meta("refresh_shift",false)) else .0001
		(probe as ReflectionProbe).position.x += shift
		probe.set_meta("refresh_shift",shift>0)
		(probe as ReflectionProbe).update_mode = ReflectionProbe.UPDATE_ONCE
	# No 12-frame UPDATE_ALWAYS burst (six scene renders per probe per frame).
	# Hidden rooms are invalidated too and recapture once when they become visible.
	await get_tree().process_frame


func ensure_baked(force: bool = false) -> bool:
	if DisplayServer.get_name()=="headless":
		push_error("dorm: VoxelGI запекается оконным запуском -- bake")
		return false
	var manifest_path: String = "res://data/blockouts/dorm_voxel/bake.json"
	if not force and FileAccess.file_exists(manifest_path):
		var cached: Variant = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		if cached is Dictionary and String((cached as Dictionary).get("bake_sha256",""))==_bake_signature():
			var valid: bool = true
			for i: int in range(voxels.size()):
				var path: String = String(config.voxel.volumes[i].cache)
				if not FileAccess.file_exists(path):
					valid = false
					break
				voxels[i].data = load(path) as VoxelGIData
				_apply_voxel_data(voxels[i])
				valid = valid and voxels[i].data!=null
			if valid:
				bake_report = cached as Dictionary
				return true
	busy = true
	_update_label()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://data/blockouts/dorm_voxel"))
	bake_report = {"geometry_sha256":config.geometry_sha256,"bake_sha256":_bake_signature(),"diffuse_proxy":VoxelBake.VERSION,
		"engine":Engine.get_version_info().string,"floors":[],"total_sec":0.0,"lighting":"BAKE_DYNAMIC; no LightmapGI"}
	for i: int in range(voxels.size()):
		var voxel: VoxelGI = voxels[i]
		voxel.show()
		await get_tree().process_frame
		var started: int = Time.get_ticks_msec()
		print("dorm: VoxelGI bake start ",voxel.name)
		var proxy: RefCounted = VoxelBake.new(plan)
		if bool(config.voxel.get("diffuse_proxy",true)):proxy.call("begin",get_parent())
		voxel.bake(get_parent())
		proxy.call("restore")
		var seconds: float = (Time.get_ticks_msec()-started)/1000.0
		if voxel.data==null:
			push_error("dorm: VoxelGI bake не создал данные")
			busy = false
			return false
		_apply_voxel_data(voxel)
		var path: String = String(config.voxel.volumes[i].cache)
		var error: Error = ResourceSaver.save(voxel.data,path,ResourceSaver.FLAG_COMPRESS)
		if error!=OK:
			push_error("dorm: не сохранён "+path)
			busy = false
			return false
		var file: FileAccess = FileAccess.open(path,FileAccess.READ)
		(bake_report.floors as Array).append({"id":voxel.name,"seconds":seconds,"bytes":file.get_length(),"path":path,"size":str(voxel.size),"subdiv":voxel.subdiv,"octree_size":str(voxel.data.get_octree_size()),"data_bytes":voxel.data.get_data_cells().size()})
		file.close()
		bake_report.total_sec = float(bake_report.total_sec)+seconds
		print("dorm: VoxelGI bake done ",voxel.name," ",seconds," sec")
		voxel.hide()
	var manifest: FileAccess
	for attempt: int in range(3):
		manifest = FileAccess.open(manifest_path,FileAccess.WRITE)
		if manifest!=null:break
		await get_tree().create_timer(.1).timeout
	if manifest==null:
		push_error("dorm: не сохранён манифест "+manifest_path+"; "+error_string(FileAccess.get_open_error()))
		busy = false
		return false
	manifest.store_string(JSON.stringify(bake_report,"\t"))
	manifest.close()
	busy = false
	_update_label()
	return true

func _apply_voxel_data(voxel: VoxelGI) -> void:
	if voxel.data==null:return
	voxel.data.energy = float(config.voxel.energy)
	voxel.data.bias = float(config.voxel.bias)
	voxel.data.normal_bias = float(config.voxel.normal_bias)
	voxel.data.interior = bool(config.voxel.get("interior",false))

func _bake_signature() -> String:
	return JSON.stringify({"geometry":config.geometry_sha256,"volumes":config.voxel.volumes,"subdiv":config.voxel.subdiv,
		"gi_batches":"floor_and_exterior_packets_exclude_all_mirrors_2",
		"diffuse_proxy":VoxelBake.VERSION if bool(config.voxel.get("diffuse_proxy",true)) else "none","finish":plan.finish,
		"finish_shader":FileAccess.get_sha256("res://src/blockout/dorm_finish.gdshader")}).sha256_text()

func _create_dust() -> void:
	for item: Dictionary in config.effects.get("dust_volumes",[]):
		var volume: FogVolume = FogVolume.new()
		volume.name = String(item.id)
		volume.position = _vec(item.at);volume.size = _vec(item.size)
		var material: FogMaterial = FogMaterial.new()
		material.density = float(item.get("density",config.effects.get("dust_density",.025)))
		material.albedo = Color("e6e3db");material.edge_fade = .2
		volume.material = material
		add_child(volume);dust.append(volume)


static func _vec(at: Array) -> Vector3:
	return Vector3(float(at[0]),float(at[1]),float(at[2]))
