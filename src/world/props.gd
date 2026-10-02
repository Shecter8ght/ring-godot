class_name Props
extends RefCounted
## Библиотека процедурных пропсов: коробки из примитивов, узнаваемые с высоты изометрии.
## Неподвижный проп — StaticBody3D; тележка — отдельная сцена с физикой колёс.
## Габариты в метрах: x — ширина (вдоль ряда), z — глубина, y — высота. Пивот — центр по XZ, пол по Y.
## Это запасной вариант по правилу проекта: модели из assets/ встанут на те же точки, когда появятся.

const SPECS := {
	"shelf_retail": {"w": 2.4, "d": 0.6, "h": 1.7},
	"shelf_warehouse": {"w": 2.6, "d": 0.9, "h": 2.4},
	"pallet_boxes": {"w": 1.2, "d": 1.0, "h": 1.2},
	"box_stack": {"w": 1.2, "d": 1.0, "h": 1.5},
	"cart": {"w": 0.6, "d": 0.95, "h": 1.0},
	"car": {"w": 1.85, "d": 4.4, "h": 1.5},
	"truck": {"w": 2.5, "d": 9.0, "h": 3.7},
	"barrel": {"w": 0.6, "d": 0.6, "h": 0.9},
	"desk": {"w": 1.5, "d": 0.75, "h": 0.75},
	"cabinet": {"w": 0.9, "d": 0.5, "h": 1.9},
	"bench": {"w": 1.8, "d": 0.55, "h": 0.5},
	"planter": {"w": 1.3, "d": 1.3, "h": 0.65},
	"bin": {"w": 0.6, "d": 0.6, "h": 0.85},
	"checkout": {"w": 2.4, "d": 0.9, "h": 1.0},
	"kiosk": {"w": 3.0, "d": 2.2, "h": 2.6},
}

const GOODS_COLORS := [
	Color(0.75, 0.2, 0.18), Color(0.2, 0.42, 0.75), Color(0.85, 0.72, 0.2), Color(0.25, 0.6, 0.3),
	Color(0.9, 0.9, 0.88), Color(0.55, 0.35, 0.2), Color(0.6, 0.6, 0.62), Color(0.3, 0.3, 0.35),
]
const CAR_COLORS := [
	Color(0.7, 0.7, 0.72), Color(0.15, 0.15, 0.17), Color(0.55, 0.1, 0.1), Color(0.2, 0.3, 0.5),
	Color(0.85, 0.85, 0.85), Color(0.3, 0.32, 0.3), Color(0.6, 0.45, 0.2),
]

var _rng := RandomNumberGenerator.new()


func _init(seed_value: int) -> void:
	_rng.seed = seed_value


static func size(id: String) -> Vector3:
	var s: Dictionary = SPECS.get(id, {"w": 1.0, "d": 1.0, "h": 1.0})
	return Vector3(float(s.w), float(s.h), float(s.d))


## Собирает проп; variant — подсказка (например, "wrecked" для машины).
func build(id: String, variant: String = "") -> PhysicsBody3D:
	if id == "cart":
		return (load("res://scenes/props/shopping_cart.tscn") as PackedScene).instantiate() as RigidBody3D
	var body := StaticBody3D.new()
	body.name = id
	var sz := size(id)
	match id:
		"shelf_retail":
			_shelf_retail(body, sz)
		"shelf_warehouse":
			_shelf_warehouse(body, sz)
		"pallet_boxes":
			_pallet_boxes(body, sz)
		"box_stack":
			_box_stack(body, sz)
		"car":
			_car(body, sz, variant == "wrecked")
		"truck":
			_truck(body, sz)
		"barrel":
			_cyl(body, Vector3(0, 0, 0), 0.3, 0.9, _flat(_pick([Color(0.25, 0.35, 0.55), Color(0.5, 0.25, 0.15), Color(0.35, 0.35, 0.35)]), 0.6, 0.6))
		"desk":
			_desk(body, sz)
		"cabinet":
			_box(body, Vector3(0, sz.y * 0.5, 0), sz, _flat(Color(0.55, 0.56, 0.58), 0.5, 0.5))
		"bench":
			_bench(body, sz)
		"planter":
			_planter(body, sz)
		"bin":
			_cyl(body, Vector3.ZERO, 0.3, 0.85, _flat(Color(0.12, 0.13, 0.14), 0.7, 0.3))
		"checkout":
			_checkout(body, sz)
		"kiosk":
			_kiosk(body, sz)
		_:
			_box(body, Vector3(0, sz.y * 0.5, 0), sz, _flat(Color(0.6, 0.2, 0.6), 0.9, 0.0))
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = sz
	cs.shape = shape
	cs.position = Vector3(0, sz.y * 0.5, 0)
	body.add_child(cs)
	return body


# ---------------------------------------------------------------- пропы

func _shelf_retail(body: StaticBody3D, sz: Vector3) -> void:
	var steel := _flat(Color(0.82, 0.82, 0.8), 0.5, 0.4)
	_box(body, Vector3(0, 0.08, 0), Vector3(sz.x, 0.16, sz.z), _flat(Color(0.2, 0.2, 0.22), 0.7, 0.2))
	_box(body, Vector3(0, sz.y * 0.5, 0), Vector3(sz.x, sz.y, 0.06), steel)
	for side in [-1.0, 1.0]:
		for level in [0.42, 0.85, 1.28]:
			_box(body, Vector3(0, level, side * sz.z * 0.25), Vector3(sz.x, 0.03, sz.z * 0.48), steel)
			# товар: коробки с прорехами
			var x := -sz.x * 0.5 + 0.1
			while x < sz.x * 0.5 - 0.15:
				var w := _rng.randf_range(0.18, 0.45)
				if x + w > sz.x * 0.5 - 0.05:
					break
				if _rng.randf() < 0.65:
					var h := _rng.randf_range(0.15, 0.36)
					_box(body, Vector3(x + w * 0.5, level + 0.015 + h * 0.5, side * sz.z * 0.27), Vector3(w, h, sz.z * 0.4), _flat(_pick(GOODS_COLORS), 0.8, 0.0))
				x += w + 0.04


func _shelf_warehouse(body: StaticBody3D, sz: Vector3) -> void:
	var orange := _flat(Color(0.85, 0.42, 0.1), 0.55, 0.5)
	var beam := _flat(Color(0.25, 0.25, 0.27), 0.5, 0.6)
	for x in [-sz.x * 0.5 + 0.05, sz.x * 0.5 - 0.05]:
		for z in [-sz.z * 0.5 + 0.05, sz.z * 0.5 - 0.05]:
			_box(body, Vector3(x, sz.y * 0.5, z), Vector3(0.08, sz.y, 0.08), orange)
	for level in [0.15, 1.15, 2.05]:
		_box(body, Vector3(0, level, 0), Vector3(sz.x, 0.08, sz.z), beam)
		if _rng.randf() < 0.7:
			var bw := _rng.randf_range(0.6, 1.1)
			var bh := _rng.randf_range(0.4, 0.8)
			_box(body, Vector3(_rng.randf_range(-0.6, 0.6), level + 0.04 + bh * 0.5, 0), Vector3(bw, bh, sz.z * 0.85), _flat(_cardboard(), 0.9, 0.0))


func _pallet_boxes(body: StaticBody3D, sz: Vector3) -> void:
	_box(body, Vector3(0, 0.075, 0), Vector3(sz.x, 0.15, sz.z), _flat(Color(0.55, 0.42, 0.25), 0.9, 0.0))
	var y := 0.15
	var layers := _rng.randi_range(1, 3)
	for i in range(layers):
		var h := _rng.randf_range(0.3, 0.45)
		var shrink := 1.0 - i * 0.08
		_box(body, Vector3(0, y + h * 0.5, 0), Vector3(sz.x * shrink * 0.95, h, sz.z * shrink * 0.95), _flat(_cardboard(), 0.9, 0.0))
		y += h


func _box_stack(body: StaticBody3D, sz: Vector3) -> void:
	var y := 0.0
	for i in range(_rng.randi_range(2, 4)):
		var w := _rng.randf_range(0.5, sz.x)
		var d := _rng.randf_range(0.5, sz.z)
		var h := _rng.randf_range(0.3, 0.5)
		_box(body, Vector3(_rng.randf_range(-0.15, 0.15), y + h * 0.5, _rng.randf_range(-0.15, 0.15)), Vector3(w, h, d), _flat(_cardboard(), 0.9, 0.0))
		y += h


func _car(body: StaticBody3D, sz: Vector3, wrecked: bool) -> void:
	var paint := _flat(_pick(CAR_COLORS) * (0.5 if wrecked else 1.0), 0.75 if wrecked else 0.35, 0.0 if wrecked else 0.4)
	var glass := _flat(Color(0.15, 0.2, 0.25), 0.2, 0.3)
	_box(body, Vector3(0, 0.62, 0), Vector3(sz.x, 0.55, sz.z), paint)
	_box(body, Vector3(0, 1.15, -0.2), Vector3(sz.x * 0.88, 0.55, sz.z * 0.48), glass)
	_box(body, Vector3(0, 1.32, -0.2), Vector3(sz.x * 0.86, 0.22, sz.z * 0.44), paint)
	var tire := _flat(Color(0.08, 0.08, 0.08), 0.9, 0.0)
	for x in [-sz.x * 0.5 + 0.12, sz.x * 0.5 - 0.12]:
		for z in [-sz.z * 0.32, sz.z * 0.32]:
			var wheel := _cyl(body, Vector3(x, 0.0, z), 0.34, 0.24, tire)
			wheel.rotation.z = PI * 0.5
			wheel.position.y = 0.34


func _truck(body: StaticBody3D, sz: Vector3) -> void:
	var cab := _flat(_pick([Color(0.8, 0.8, 0.82), Color(0.2, 0.35, 0.6), Color(0.6, 0.15, 0.12)]), 0.4, 0.3)
	_box(body, Vector3(0, 1.6, sz.z * 0.5 - 1.1), Vector3(sz.x * 0.94, 2.4, 2.2), cab)
	_box(body, Vector3(0, 1.9, sz.z * 0.5 - 1.5), Vector3(sz.x * 0.9, 0.9, 1.0), _flat(Color(0.12, 0.15, 0.18), 0.2, 0.3))
	var box := SectorMaterials.get_material("corrugated_iron_02", true)
	_box(body, Vector3(0, 0.6 + 1.55, -1.1), Vector3(sz.x, 3.1, sz.z - 2.3), box)
	_box(body, Vector3(0, 0.55, 0), Vector3(sz.x * 0.8, 0.3, sz.z * 0.9), _flat(Color(0.15, 0.15, 0.16), 0.8, 0.3))
	var tire := _flat(Color(0.08, 0.08, 0.08), 0.9, 0.0)
	for x in [-sz.x * 0.5 + 0.18, sz.x * 0.5 - 0.18]:
		for z in [sz.z * 0.5 - 1.3, -sz.z * 0.5 + 1.4, -sz.z * 0.5 + 2.6]:
			var wheel := _cyl(body, Vector3(x, 0.0, z), 0.5, 0.35, tire)
			wheel.rotation.z = PI * 0.5
			wheel.position.y = 0.5


func _desk(body: StaticBody3D, sz: Vector3) -> void:
	_box(body, Vector3(0, sz.y - 0.02, 0), Vector3(sz.x, 0.04, sz.z), _flat(Color(0.5, 0.4, 0.28), 0.7, 0.0))
	for x in [-sz.x * 0.5 + 0.05, sz.x * 0.5 - 0.05]:
		_box(body, Vector3(x, sz.y * 0.5, 0), Vector3(0.06, sz.y, sz.z * 0.9), _flat(Color(0.3, 0.3, 0.32), 0.6, 0.3))
	if _rng.randf() < 0.7:
		_box(body, Vector3(_rng.randf_range(-0.3, 0.3), sz.y + 0.2, -0.1), Vector3(0.45, 0.32, 0.05), _flat(Color(0.1, 0.1, 0.11), 0.4, 0.2))


func _bench(body: StaticBody3D, sz: Vector3) -> void:
	var wood := _flat(Color(0.42, 0.3, 0.18), 0.8, 0.0)
	for i in range(4):
		_box(body, Vector3(0, 0.45, -sz.z * 0.5 + 0.08 + i * 0.13), Vector3(sz.x, 0.04, 0.1), wood)
	for x in [-sz.x * 0.5 + 0.15, sz.x * 0.5 - 0.15]:
		_box(body, Vector3(x, 0.22, 0), Vector3(0.06, 0.44, sz.z * 0.8), _flat(Color(0.2, 0.2, 0.2), 0.6, 0.5))


func _planter(body: StaticBody3D, sz: Vector3) -> void:
	_box(body, Vector3(0, 0.3, 0), Vector3(sz.x, 0.6, sz.z), SectorMaterials.get_material("concrete_wall_006", true))
	_box(body, Vector3(0, 0.58, 0), Vector3(sz.x * 0.85, 0.06, sz.z * 0.85), _flat(Color(0.2, 0.15, 0.1), 0.95, 0.0))
	# сухой куст: несколько тёмных сфер
	for i in range(_rng.randi_range(2, 4)):
		var mi := MeshInstance3D.new()
		var sph := SphereMesh.new()
		var r := _rng.randf_range(0.3, 0.55)
		sph.radius = r
		sph.height = r * 2.0
		mi.mesh = sph
		mi.position = Vector3(_rng.randf_range(-0.3, 0.3), 0.6 + r * 0.8, _rng.randf_range(-0.3, 0.3))
		mi.material_override = _flat(Color(0.28, 0.3, 0.16), 0.95, 0.0)
		body.add_child(mi)


func _checkout(body: StaticBody3D, sz: Vector3) -> void:
	_box(body, Vector3(0, 0.45, 0), Vector3(sz.x, 0.9, sz.z), _flat(Color(0.75, 0.74, 0.7), 0.6, 0.1))
	_box(body, Vector3(-0.3, 0.92, 0), Vector3(sz.x * 0.6, 0.04, sz.z * 0.7), _flat(Color(0.1, 0.1, 0.1), 0.5, 0.1))
	_box(body, Vector3(sz.x * 0.35, 1.05, 0.1), Vector3(0.35, 0.3, 0.3), _flat(Color(0.2, 0.2, 0.22), 0.5, 0.2))


func _kiosk(body: StaticBody3D, sz: Vector3) -> void:
	_box(body, Vector3(0, 0.55, 0), Vector3(sz.x, 1.1, sz.z), _flat(Color(0.35, 0.3, 0.28), 0.7, 0.1))
	for x in [-sz.x * 0.5 + 0.08, sz.x * 0.5 - 0.08]:
		for z in [-sz.z * 0.5 + 0.08, sz.z * 0.5 - 0.08]:
			_box(body, Vector3(x, sz.y * 0.5, z), Vector3(0.1, sz.y, 0.1), _flat(Color(0.2, 0.2, 0.2), 0.5, 0.5))
	_box(body, Vector3(0, sz.y - 0.15, 0), Vector3(sz.x + 0.3, 0.3, sz.z + 0.3), _flat(Color(0.5, 0.12, 0.1), 0.7, 0.0))


# ---------------------------------------------------------------- примитивы

func _box(parent: Node3D, at: Vector3, sz: Vector3, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = sz
	mi.mesh = mesh
	mi.position = at
	mi.material_override = mat
	parent.add_child(mi)
	return mi


func _cyl(parent: Node3D, at: Vector3, r: float, h: float, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = r
	mesh.bottom_radius = r
	mesh.height = h
	mesh.radial_segments = 14
	mi.mesh = mesh
	mi.position = at + Vector3(0, h * 0.5, 0)
	mi.material_override = mat
	parent.add_child(mi)
	return mi


func _flat(color: Color, rough: float, metal: float) -> Material:
	return SectorMaterials.flat(color, rough, metal)


func _pick(arr: Array) -> Color:
	return arr[_rng.randi_range(0, arr.size() - 1)]


func _cardboard() -> Color:
	var v := _rng.randf_range(0.45, 0.62)
	return Color(v, v * 0.78, v * 0.52)
