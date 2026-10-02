@tool
extends Node3D
## Процедурная проволочная корзина и поворотные колёса: три вызова отрисовки на тележку.
## Геометрия остаётся дочерней телу; внешние модели и текстуры для неё не нужны.

const WHEEL_RADIUS: float = 0.065
const WHEEL_POINTS: Array[Vector3] = [
	Vector3(-0.245, WHEEL_RADIUS, -0.375), Vector3(0.245, WHEEL_RADIUS, -0.375),
	Vector3(-0.245, WHEEL_RADIUS, 0.375), Vector3(0.245, WHEEL_RADIUS, 0.375),
]

var _wheels: MultiMesh
var _steer: Array[float] = [0.0, 0.0, 0.0, 0.0]
var _spin: Array[float] = [0.0, 0.0, 0.0, 0.0]


func _ready() -> void:
	var bars: Array[Transform3D] = []
	for y: float in [0.40, 0.51, 0.62, 0.73, 0.845]:
		_bar(bars, Vector3(-0.30, y, -0.4275), Vector3(0.30, y, -0.4275))
		_bar(bars, Vector3(-0.30, y, 0.4275), Vector3(0.30, y, 0.4275))
		_bar(bars, Vector3(-0.30, y, -0.4275), Vector3(-0.30, y, 0.4275))
		_bar(bars, Vector3(0.30, y, -0.4275), Vector3(0.30, y, 0.4275))
	for i: int in range(9):
		var z: float = lerpf(-0.4275, 0.4275, float(i) / 8.0)
		for x: float in [-0.30, 0.30]:
			_bar(bars, Vector3(x, 0.40, z), Vector3(x, 0.845, z))
		_bar(bars, Vector3(-0.30, 0.40, z), Vector3(0.30, 0.40, z))
	for i: int in range(7):
		var x: float = lerpf(-0.30, 0.30, float(i) / 6.0)
		for z: float in [-0.4275, 0.4275]:
			_bar(bars, Vector3(x, 0.40, z), Vector3(x, 0.845, z))
	for x: float in [-0.245, 0.245]:
		_bar(bars, Vector3(x, 0.18, -0.40), Vector3(x, 0.18, 0.40), 0.025)
		_bar(bars, Vector3(x, 0.18, -0.375), Vector3(x, 0.96, -0.4275), 0.025)
		_bar(bars, Vector3(x, 0.18, 0.375), Vector3(x, 0.40, 0.35), 0.025)
		for z: float in [-0.375, 0.375]:
			_bar(bars, Vector3(x, 0.065, z), Vector3(x, 0.18, z), 0.025)
	for z: float in [-0.40, 0.0, 0.40]:
		_bar(bars, Vector3(-0.245, 0.18, z), Vector3(0.245, 0.18, z), 0.025)
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3.ONE
	var steel: StandardMaterial3D = StandardMaterial3D.new()
	steel.albedo_color = Color(0.65, 0.67, 0.69)
	steel.metallic = 0.85
	steel.roughness = 0.32
	_fill($Wire as MultiMeshInstance3D, box, steel, bars)
	var tyre: CylinderMesh = CylinderMesh.new()
	tyre.top_radius = WHEEL_RADIUS
	tyre.bottom_radius = WHEEL_RADIUS
	tyre.height = 0.035
	tyre.radial_segments = 12
	tyre.rings = 1
	var rubber: StandardMaterial3D = StandardMaterial3D.new()
	rubber.albedo_color = Color(0.06, 0.065, 0.07)
	rubber.roughness = 0.9
	var wheel_transforms: Array[Transform3D] = []
	for point: Vector3 in WHEEL_POINTS:
		wheel_transforms.append(Transform3D(Basis(Vector3.FORWARD, PI * 0.5), point))
	_wheels = _fill($Wheels as MultiMeshInstance3D, tyre, rubber, wheel_transforms)


func _physics_process(delta: float) -> void:
	if Engine.is_editor_hint() or _wheels == null:
		return
	var cart: ShoppingCart = get_parent() as ShoppingCart
	var local_velocity: Vector3 = cart.global_basis.inverse() * cart.net_velocity
	for i: int in range(WHEEL_POINTS.size()):
		var velocity: Vector3 = local_velocity + (cart.global_basis.inverse() * cart.angular_velocity).cross(WHEEL_POINTS[i])
		velocity.y = 0.0
		if velocity.length_squared() > 0.001:
			_steer[i] = lerp_angle(_steer[i], atan2(velocity.x, velocity.z), 1.0 - exp(-float(Balance.CART.caster_response) * delta))
			_spin[i] += velocity.length() * delta / WHEEL_RADIUS
		var basis: Basis = Basis(Vector3.UP, _steer[i]) * Basis(Vector3.RIGHT, _spin[i]) * Basis(Vector3.FORWARD, PI * 0.5)
		_wheels.set_instance_transform(i, Transform3D(basis, WHEEL_POINTS[i]))


func _bar(out: Array[Transform3D], from: Vector3, to: Vector3, width: float = 0.008) -> void:
	var direction: Vector3 = to - from
	var basis: Basis = Basis(Quaternion(Vector3.UP, direction.normalized()))
	out.append(Transform3D(basis.scaled_local(Vector3(width, direction.length(), width)), (from + to) * 0.5))


func _fill(node: MultiMeshInstance3D, mesh: Mesh, material: Material, transforms: Array[Transform3D]) -> MultiMesh:
	var mm: MultiMesh = MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = transforms.size()
	for i: int in range(transforms.size()):
		mm.set_instance_transform(i, transforms[i])
	node.multimesh = mm
	node.material_override = material
	return mm
