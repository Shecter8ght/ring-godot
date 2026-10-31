extends Node3D
## Оставленный кем-то свет в заброшенном общежитии (электричества нет): фонарь на полу с садящимися батарейками,
## налобник, химсвет-метка, кемпинговый фонарь, окопные свечи в банках, дорожная мигалка. Предметы — игровые модели
## с картами (tools/dorm_modules/game_props.py → assets/models/dorm/props/found_*.gltf), без них — формы Blender без
## текстур (build_found_lights.py → assets/models/dorm/found_*.glb; точки света — found_lights.json, общие для обоих),
## без тех — простые формы кодом. Свет и его поведение — здесь же. Расстановка — data/blockouts/dorm_found_lights.json.

## Вид: цвет, яркость, дальность, угол луча (0 — во все стороны), тень.
const KINDS: Dictionary = {
	"flashlight": {"color": Color(1.0, 0.9, 0.74), "energy": 2.2, "range": 9.0, "angle": 24.0, "shadow": true},
	"headlamp": {"color": Color(0.92, 0.95, 1.0), "energy": 1.4, "range": 5.5, "angle": 34.0, "shadow": true},
	"chem_green": {"color": Color(0.35, 1.0, 0.45), "energy": 0.45, "range": 3.2, "angle": 0.0, "shadow": true},
	"chem_yellow": {"color": Color(1.0, 0.86, 0.25), "energy": 0.4, "range": 3.0, "angle": 0.0, "shadow": true},
	"chem_orange": {"color": Color(1.0, 0.48, 0.12), "energy": 0.4, "range": 3.0, "angle": 0.0, "shadow": true},
	"lantern": {"color": Color(1.0, 0.84, 0.64), "energy": 1.0, "range": 5.5, "angle": 0.0, "shadow": true},
	"candles": {"color": Color(1.0, 0.58, 0.26), "energy": 0.85, "range": 4.5, "angle": 0.0, "shadow": true},
	"beacon": {"color": Color(1.0, 0.1, 0.04), "energy": 1.4, "range": 3.0, "angle": 0.0, "shadow": false},
}

## Модель предмета на вид и отбрасывает ли он тень (у фонаря-лампы, мигалки и химсвета свет внутри корпуса).
const MODELS: Dictionary = {"flashlight": "found_flashlight", "headlamp": "found_headlamp", "chem_green": "found_chemlight",
	"chem_yellow": "found_chemlight", "chem_orange": "found_chemlight", "lantern": "found_lantern", "candles": "found_candles",
	"beacon": "found_beacon"}
const PROP_SHADOW: Array[String] = ["flashlight", "headlamp"]
const MODEL_DIR: String = "res://assets/models/dorm"
## Игровые модели: материал «<модель>» — карты, «<модель>_стекло» — прозрачное, «<модель>_свет» — светится цветом света.
const GAME_DIR: String = "res://assets/models/dorm/props"
## Слоты материалов Blender: цвет (линейный, как в .blend), шероховатость, металл; светящиеся — цветом света.
const SLOTS: Dictionary = {
	"Фонарь_корпус": [Color(0.05, 0.05, 0.055), 0.4, 0.6], "Фонарь_резина": [Color(0.02, 0.02, 0.02), 0.85, 0.0],
	"Фонарь_отражатель": [Color(0.85, 0.85, 0.85), 0.08, 1.0], "Налобник_корпус": [Color(0.03, 0.03, 0.03), 0.55, 0.0],
	"Налобник_ремень": [Color(0.05, 0.08, 0.12), 0.9, 0.0], "Налобник_пряжка": [Color(0.04, 0.04, 0.04), 0.5, 0.0],
	"Химсвет_колпачок": [Color(0.03, 0.03, 0.03), 0.5, 0.0], "Лампа_корпус": [Color(0.08, 0.12, 0.08), 0.6, 0.0],
	"Лампа_ручка": [Color(0.6, 0.6, 0.6), 0.35, 1.0], "Лампа_резина": [Color(0.02, 0.02, 0.02), 0.85, 0.0],
	"Банка_жесть": [Color(0.62, 0.6, 0.56), 0.35, 1.0], "Свеча_воск": [Color(0.85, 0.8, 0.66), 0.6, 0.0],
	"Картон": [Color(0.36, 0.26, 0.16), 0.9, 0.0], "Фитиль": [Color(0.02, 0.02, 0.02), 0.9, 0.0],
	"Мигалка_корпус": [Color(0.85, 0.55, 0.05), 0.55, 0.0], "Мигалка_оправа": [Color(0.03, 0.03, 0.03), 0.6, 0.0],
}
const GLOWING: Array[String] = ["Фонарь_светодиод", "Химсвет_трубка", "Лампа_рассеиватель", "Пламя", "Мигалка_линза"]

static var _meta: Dictionary = {}
static var _meshes: Dictionary = {}

var kind: String = "chem_green"
## Сколько осталось в батарейках / насколько тускло (0…1) — у фонарей и налобника.
var charge: float = 0.6
var seed_value: int = 1

var _light: Light3D
var _glow: Array[StandardMaterial3D] = []
var _base: float = 1.0
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _t: float = 0.0
## Фонарь: когда следующий сбой, сколько он ещё длится, погас ли совсем.
var _next_fault: float = 0.0
var _fault_left: float = 0.0
var _off: bool = false
var _flame_home: Vector3 = Vector3.ZERO


func _ready() -> void:
	_rng.seed = seed_value
	var spec: Dictionary = KINDS[kind]
	var point: Variant = _build_model(String(MODELS.get(kind, "")))
	if point == null:
		_build_prop()
	if float(spec.angle) > 0.0:
		var spot: SpotLight3D = SpotLight3D.new()
		spot.spot_range = float(spec.range)
		spot.spot_angle = float(spec.angle)
		spot.spot_angle_attenuation = 1.6
		spot.spot_attenuation = 1.4
		_light = spot
	else:
		var omni: OmniLight3D = OmniLight3D.new()
		omni.omni_range = float(spec.range)
		omni.omni_attenuation = 1.6
		omni.omni_shadow_mode = OmniLight3D.SHADOW_DUAL_PARABOLOID
		_light = omni
	_light.name = "Light"
	_light.light_color = spec.color
	_light.light_energy = float(spec.energy)
	_light.shadow_enabled = bool(spec.shadow)
	_light.light_bake_mode = Light3D.BAKE_DYNAMIC if bool(spec.shadow) else Light3D.BAKE_DISABLED
	# свет — у светящейся части: у фонаря из стекла вперёд по −Z, у остальных — над предметом
	_light.position = Vector3(0, 0, -0.09) if float(spec.angle) > 0.0 else Vector3(0, 0.12 if kind == "lantern" else 0.06, 0)
	if point is Vector3:
		_light.position = point
	add_child(_light)
	# Settings.soften пересчитывает яркость при входе в дерево — мерцать от уже смягчённой
	_light.shadow_bias = 0.03
	_light.shadow_blur = 1.5
	_base = _light.light_energy
	_flame_home = _light.position
	_next_fault = _rng.randf_range(2.0, 8.0)
	add_to_group("dorm_found_lights")


func _process(delta: float) -> void:
	_t += delta
	var k: float = 1.0
	match kind:
		"flashlight", "headlamp":
			k = _dying(delta)
		"lantern":
			# светодиоды на подсевших батарейках: ровно, изредка проседает на пару секунд
			_next_fault -= delta
			if _next_fault <= 0.0:
				_fault_left = _rng.randf_range(0.8, 2.2)
				_next_fault = _rng.randf_range(18.0, 40.0)
			if _fault_left > 0.0:
				_fault_left -= delta
				k = 0.35 + 0.1 * sin(_t * 9.0)
			else:
				k = 0.92 + 0.04 * sin(_t * 0.7 + float(seed_value))
		"candles":
			# пламя: быстрая дрожь и медленное колыхание, свет чуть гуляет — тени живые
			k = 0.82 + 0.12 * sin(_t * 7.3 + float(seed_value)) * sin(_t * 3.1) + 0.08 * _rng.randf_range(-1.0, 1.0)
			_light.position = _flame_home + Vector3(sin(_t * 5.1), 0.0, cos(_t * 4.3)) * 0.006
		"beacon":
			# двойная вспышка раз в 1,6 с
			var phase: float = fmod(_t + float(seed_value) * 0.37, 1.6)
			k = 1.0 if phase < 0.07 or (phase > 0.18 and phase < 0.25) else 0.0
		_:
			k = 1.0
	_light.light_energy = _base * k
	for m: StandardMaterial3D in _glow:
		m.emission_energy_multiplier = 2.5 * k


## Фонарь с садящимися батарейками: тускло и чуть «дышит», временами дребезжит контакт, изредка гаснет.
func _dying(delta: float) -> float:
	var level: float = charge * (0.85 + 0.15 * sin(_t * 0.35 + float(seed_value)))
	_next_fault -= delta
	if _next_fault <= 0.0 and _fault_left <= 0.0:
		_off = _rng.randf() < 0.3
		_fault_left = _rng.randf_range(0.3, 1.4) if _off else _rng.randf_range(0.15, 0.8)
		_next_fault = _rng.randf_range(4.0, 12.0)
	if _fault_left > 0.0:
		_fault_left -= delta
		if _off:
			return 0.0
		return level * (0.15 if _rng.randf() < 0.5 else 1.0)
	return level


## Модель Blender предмета; вернёт точку света из found_lights.json или null, если файлов нет.
func _build_model(model: String) -> Variant:
	if _meta.is_empty() and FileAccess.file_exists(MODEL_DIR + "/found_lights.json"):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(MODEL_DIR + "/found_lights.json"))
		if parsed is Dictionary:
			_meta = parsed as Dictionary
	var path: String = "%s/%s.gltf" % [GAME_DIR, model]
	var game: bool = ResourceLoader.exists(path)
	if not game:
		path = "%s/%s.glb" % [MODEL_DIR, model]
	if model == "" or not _meta.has(model) or not ResourceLoader.exists(path):
		return null
	if not _meshes.has(model):
		var scene: Node = (load(path) as PackedScene).instantiate()
		for child: Node in scene.find_children("*", "MeshInstance3D", true, false):
			_meshes[model] = (child as MeshInstance3D).mesh
			break
		scene.free()
	var mesh: Mesh = _meshes.get(model) as Mesh
	if mesh == null:
		return null
	var node: MeshInstance3D = MeshInstance3D.new()
	node.name = "Prop"
	node.mesh = mesh
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if kind in PROP_SHADOW else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var color: Color = (KINDS[kind] as Dictionary).color
	for s: int in range(mesh.get_surface_count()):
		var source: Material = mesh.surface_get_material(s)
		var slot: String = source.resource_name if source != null else ""
		var material: StandardMaterial3D
		if game:
			material = _game_material(source, slot, color)
		elif slot in GLOWING:
			material = _emit(color)
		elif slot.ends_with("_стекло"):
			material = _mat(Color(0.9, 0.95, 1.0, 0.12), 0.02, 0.0)
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		else:
			var spec: Array = SLOTS.get(slot, [Color(0.3, 0.3, 0.3), 0.7, 0.0])
			material = _mat((spec[0] as Color).linear_to_srgb(), float(spec[1]), float(spec[2]))
		node.set_surface_override_material(s, material)
	add_child(node)
	var at: Array = (_meta[model] as Dictionary).light
	return Vector3(float(at[0]), float(at[1]), float(at[2]))


## Материал игровой модели: карты как есть; стекло — прозрачное с картами; светящееся — цветом света (у трубки
## химсвета, рассеивателя лампы и линзы мигалки поверх их карт), яркость идёт за светом.
func _game_material(source: Material, slot: String, color: Color) -> StandardMaterial3D:
	var base: StandardMaterial3D = source as StandardMaterial3D
	if base == null:
		return _mat(Color(0.3, 0.3, 0.3), 0.7, 0.0)
	if slot.ends_with("_стекло"):
		var glass: StandardMaterial3D = base.duplicate() as StandardMaterial3D
		glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		glass.albedo_color.a = 0.25
		glass.metallic = 0.0
		return glass
	if slot.ends_with("_свет"):
		if base.albedo_texture == null:
			return _emit(color)
		var lit: StandardMaterial3D = base.duplicate() as StandardMaterial3D
		lit.emission_enabled = true
		lit.emission = color
		lit.emission_energy_multiplier = 2.5
		_glow.append(lit)
		return lit
	return base


## Предмет простыми формами (без моделей); светящиеся части — свои материалы, их яркость идёт за светом.
func _build_prop() -> void:
	var spec: Dictionary = KINDS[kind]
	var c: Color = spec.color
	match kind:
		"flashlight":
			_cyl(Vector3(0, 0.02, 0.02), 0.017, 0.15, _mat(Color(0.12, 0.12, 0.13), 0.45, 0.8), true)
			_cyl(Vector3(0, 0.02, -0.07), 0.024, 0.04, _mat(Color(0.14, 0.14, 0.15), 0.4, 0.8), true)
			_cyl(Vector3(0, 0.02, -0.091), 0.02, 0.003, _emit(c), true)
		"headlamp":
			_box(Vector3(0, 0, 0), Vector3(0.06, 0.035, 0.03), _mat(Color(0.1, 0.1, 0.1), 0.6, 0.0))
			_cyl(Vector3(0, 0, -0.016), 0.012, 0.004, _emit(c), true)
			_box(Vector3(0, 0, 0.03), Vector3(0.05, 0.012, 0.03), _mat(Color(0.15, 0.17, 0.2), 0.9, 0.0))
		"chem_green", "chem_yellow", "chem_orange":
			var stick: MeshInstance3D = _cyl(Vector3(0, 0.009, 0), 0.008, 0.15, _emit(c), false)
			stick.rotation.z = PI * 0.5
			var cap: MeshInstance3D = _cyl(Vector3(0.08, 0.009, 0), 0.009, 0.015, _mat(Color(0.18, 0.18, 0.18), 0.6, 0.0), false)
			cap.rotation.z = PI * 0.5
		"lantern":
			_cyl(Vector3(0, 0.02, 0), 0.05, 0.04, _mat(Color(0.2, 0.32, 0.22), 0.6, 0.0), false)
			_cyl(Vector3(0, 0.09, 0), 0.042, 0.1, _emit(c), false)
			_cyl(Vector3(0, 0.155, 0), 0.05, 0.03, _mat(Color(0.2, 0.32, 0.22), 0.6, 0.0), false)
		"candles":
			for i: int in range(3):
				var at: Vector3 = Vector3((float(i) - 1.0) * 0.11, 0, (0.03 if i == 1 else -0.02))
				_cyl(at + Vector3(0, 0.04, 0), 0.037, 0.08, _mat(Color(0.55, 0.53, 0.5), 0.35, 0.9), false)
				_cyl(at + Vector3(0, 0.06, 0), 0.03, 0.05, _mat(Color(0.86, 0.82, 0.7), 0.7, 0.0), false)
				var flame: MeshInstance3D = MeshInstance3D.new()
				var sphere: SphereMesh = SphereMesh.new()
				sphere.radius = 0.006
				sphere.height = 0.022
				flame.mesh = sphere
				flame.position = at + Vector3(0, 0.097, 0)
				flame.material_override = _emit(c)
				flame.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
				add_child(flame)
		"beacon":
			_box(Vector3(0, 0.02, 0), Vector3(0.12, 0.04, 0.09), _mat(Color(0.75, 0.6, 0.08), 0.6, 0.0))
			var dome: MeshInstance3D = MeshInstance3D.new()
			var half: SphereMesh = SphereMesh.new()
			half.radius = 0.04
			half.height = 0.04
			half.is_hemisphere = true
			dome.mesh = half
			dome.position = Vector3(0, 0.04, 0)
			dome.material_override = _emit(c)
			dome.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(dome)


func _cyl(at: Vector3, radius: float, length: float, material: Material, along_z: bool) -> MeshInstance3D:
	var node: MeshInstance3D = MeshInstance3D.new()
	var mesh: CylinderMesh = CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = length
	mesh.radial_segments = 16
	node.mesh = mesh
	node.position = at
	if along_z:
		node.rotation.x = PI * 0.5
	node.material_override = material
	if material in _glow:
		node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node)
	return node


func _box(at: Vector3, size: Vector3, material: Material) -> MeshInstance3D:
	var node: MeshInstance3D = MeshInstance3D.new()
	var mesh: BoxMesh = BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.position = at
	node.material_override = material
	add_child(node)
	return node


func _mat(color: Color, rough: float, metal: float) -> StandardMaterial3D:
	var m: StandardMaterial3D = StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	return m


func _emit(color: Color) -> StandardMaterial3D:
	var m: StandardMaterial3D = _mat(color, 0.3, 0.0)
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 2.5
	_glow.append(m)
	return m
