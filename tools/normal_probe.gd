extends Node3D
## Стенд нормалей в Godot: те же low и high, что запёк `tools/asset_kit/normal_probe.py`, одним светом.
## Варианты: тангенты из файла Blender (со сжатием вершин и без), тангенты, посчитанные Godot при загрузке, и карта
## нормалей в разных форматах сжатия (как без флага карты нормалей — S3TC, с флагом — RGTC, «высокое качество» — BPTC).
## Снимки godot_<вариант>_<деталь>.png кладутся в ту же папку; разбор — tools/asset_kit/normal_probe_report.py.
##
## NORMAL_PROBE_DIR=<папка> tools/godot.cmd --windowed --resolution 512x512 res://tools/normal_probe.tscn

const SHOT: int = 512
const PARTS: Array[String] = ["box_smooth", "box_hard", "oct", "cyl", "blob"]
const FLAG_GENERATE_TANGENTS: int = 8
const FLAG_NO_COMPRESSION: int = 64
const ALBEDO_LINEAR: float = 0.21
const ROUGHNESS: float = 0.45
## Тот же материал, но вторая касательная (бинормаль) считается в каждом пикселе из интерполированных нормали
## и касательной, как в запекании Blender (MikkTSpace «per pixel»); у Godot она считается в вершинах.
const PER_PIXEL_SHADER: String = """
shader_type spatial;
uniform vec3 albedo : source_color;
uniform float roughness_value;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap_anisotropic;
void fragment() {
	ALBEDO = albedo;
	ROUGHNESS = roughness_value;
	METALLIC = 0.0;
	float s = dot(cross(NORMAL, TANGENT), BINORMAL) < 0.0 ? -1.0 : 1.0;
	BINORMAL = s * cross(NORMAL, TANGENT);
	NORMAL_MAP = texture(normal_tex, UV).rgb;
}
"""

var _dir: String = ""
var _camera: Camera3D = null


func _ready() -> void:
	_dir = OS.get_environment("NORMAL_PROBE_DIR")
	if _dir.is_empty() or not DirAccess.dir_exists_absolute(_dir):
		push_error("NORMAL_PROBE: нет папки NORMAL_PROBE_DIR")
		get_tree().quit(1)
		return
	get_window().size = Vector2i(SHOT, SHOT)
	get_viewport().transparent_bg = true
	_setup_world()
	await _run()
	get_tree().quit()


func _setup_world() -> void:
	var env: Environment = Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0, 0, 0, 0)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.05, 0.05, 0.05)
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we: WorldEnvironment = WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun: DirectionalLight3D = DirectionalLight3D.new()
	sun.light_energy = 1.5
	sun.shadow_enabled = false
	add_child(sun)
	# направление света — как у солнца в снимках Blender (оси Blender → Godot: x, z, −y)
	sun.look_at_from_position(Vector3(0.6, 0.7, 0.4), Vector3.ZERO)
	_camera = Camera3D.new()
	_camera.fov = 30.0
	add_child(_camera)
	_camera.current = true


func _load(file: String, flags: int) -> Node3D:
	var doc: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	var err: Error = doc.append_from_file(_dir.path_join(file), state, flags)
	if err != OK:
		push_error("NORMAL_PROBE: не открыть %s (%d)" % [file, err])
		return null
	var root: Node3D = doc.generate_scene(state) as Node3D
	add_child(root)
	root.visible = false
	return root


func _normal_texture(part: String, mode: String) -> Texture2D:
	var img: Image = Image.load_from_file(_dir.path_join(part + "_normal.png"))
	img.generate_mipmaps()
	match mode:
		"s3tc":
			img.compress(Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_GENERIC)
		"rgtc":
			img.compress(Image.COMPRESS_S3TC, Image.COMPRESS_SOURCE_NORMAL)
		"bptc":
			img.compress(Image.COMPRESS_BPTC, Image.COMPRESS_SOURCE_GENERIC)
	return ImageTexture.create_from_image(img)


func _material(normal: Texture2D) -> StandardMaterial3D:
	var m: StandardMaterial3D = StandardMaterial3D.new()
	var a: float = Color(ALBEDO_LINEAR, ALBEDO_LINEAR, ALBEDO_LINEAR).linear_to_srgb().r
	m.albedo_color = Color(a, a, a)
	m.roughness = ROUGHNESS
	m.metallic = 0.0
	if normal != null:
		m.normal_enabled = true
		m.normal_texture = normal
	return m


func _per_pixel_material(normal: Texture2D) -> ShaderMaterial:
	var sh: Shader = Shader.new()
	sh.code = PER_PIXEL_SHADER
	var m: ShaderMaterial = ShaderMaterial.new()
	m.shader = sh
	var a: float = Color(ALBEDO_LINEAR, ALBEDO_LINEAR, ALBEDO_LINEAR).linear_to_srgb().r
	m.set_shader_parameter("albedo", Color(a, a, a))
	m.set_shader_parameter("roughness_value", ROUGHNESS)
	if normal != null:
		m.set_shader_parameter("normal_tex", normal)
	return m


func _frame(mi: MeshInstance3D) -> void:
	var box: AABB = mi.global_transform * mi.get_aabb()
	var rad: float = maxf(box.size.x, maxf(box.size.y, box.size.z)) * 0.6
	var d: Vector3 = Vector3(1.0, 0.9, 1.3).normalized()
	var c: Vector3 = box.get_center()
	_camera.look_at_from_position(c + d * (rad / tan(deg_to_rad(15.0)) * 1.15), c)


func _describe(mi: MeshInstance3D) -> String:
	var fmt: int = mi.mesh.surface_get_format(0)
	var tangent: bool = (fmt & Mesh.ARRAY_FORMAT_TANGENT) != 0
	var compressed: bool = (fmt & Mesh.ARRAY_FLAG_COMPRESS_ATTRIBUTES) != 0
	return "тангенты=%s сжатие=%s" % [tangent, compressed]


func _shot(name: String) -> void:
	for i: int in 4:
		await RenderingServer.frame_post_draw
	var img: Image = get_viewport().get_texture().get_image()
	img.save_png(_dir.path_join("godot_%s.png" % name))


func _run() -> void:
	var high: Node3D = _load("high.glb", 0)
	# вариант → [файл, флаги загрузки, формат карты нормалей]
	var variants: Dictionary = {
		"tan": ["low_tan.glb", 0, "raw"],
		"tan_nocomp": ["low_tan.glb", FLAG_NO_COMPRESSION, "raw"],
		"gen": ["low_notan.glb", FLAG_GENERATE_TANGENTS, "raw"],
		"tan_s3tc": ["low_tan.glb", 0, "s3tc"],
		"tan_rgtc": ["low_tan.glb", 0, "rgtc"],
		"tan_bptc": ["low_tan.glb", 0, "bptc"],
		"tan_pp": ["low_tan.glb", 0, "per_pixel"],
	}
	var roots: Dictionary = {}
	for key: String in variants:
		roots[key] = _load(variants[key][0], variants[key][1])
	for part: String in PARTS:
		var hm: MeshInstance3D = high.find_child(part + "_high", true, false) as MeshInstance3D
		hm.material_override = _material(null)
		high.visible = true
		for child: Node in high.get_children():
			(child as Node3D).visible = child == hm
		_frame(hm)
		await _shot("high_" + part)
		hm.material_override = _per_pixel_material(null)
		await _shot("highpp_" + part)
		high.visible = false
		for key: String in variants:
			var root: Node3D = roots[key]
			var lm: MeshInstance3D = root.find_child(part, true, false) as MeshInstance3D
			var mode: String = variants[key][2]
			if mode == "per_pixel":
				lm.material_override = _per_pixel_material(_normal_texture(part, "raw"))
			else:
				lm.material_override = _material(_normal_texture(part, mode))
			root.visible = true
			for child: Node in root.get_children():
				(child as Node3D).visible = child == lm
			print("NORMAL_PROBE ", key, " ", part, " ", _describe(lm))
			await _shot(key + "_" + part)
			root.visible = false
	print("NORMAL_PROBE готово ", _dir)
