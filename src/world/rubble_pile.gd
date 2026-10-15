@tool
class_name RubblePile
extends Node3D
## Завал блокаута: россыпь обломков (плиты, балки, куски стен) в прямоугольнике size.
## Своя сцена (scenes/world/rubble_pile.tscn): двигать, крутить и менять параметры в редакторе;
## геометрия строится скриптом из параметров (и в редакторе) и в .tscn не сохраняется.
## Оси: X — ширина size.x, Z — глубина size.y. Свободный проход lane_width по оси Z через центр
## (пролом в обрушенном вестибюле); 0 — завал сплошной. Высокие обломки — у края +Z (у фасада).
## С тем же seed россыпь одинакова у всех peer. Узел — источник навмеша и prop_keepout.

@export var size: Vector2 = Vector2(12.0, 8.0):
	set(v):
		size = v
		queue_build()
@export var height: float = 3.0:
	set(v):
		height = v
		queue_build()
@export_range(1, 200) var count: int = 30:
	set(v):
		count = v
		queue_build()
## Размер одного обломка: от и до (ширина, высота, длина), м.
@export var block_min: Vector3 = Vector3(0.6, 0.3, 0.8):
	set(v):
		block_min = v
		queue_build()
@export var block_max: Vector3 = Vector3(2.4, 1.2, 3.6):
	set(v):
		block_max = v
		queue_build()
## Свободный проход по оси Z через центр, м (0 — без прохода).
@export var lane_width: float = 0.0:
	set(v):
		lane_width = v
		queue_build()
@export var seed_value: int = 1:
	set(v):
		seed_value = v
		queue_build()
## Материал блокаута (SectorMaterials): серый бетон, металл баррикады…
@export var material_id: String = "gb_structural":
	set(v):
		material_id = v
		queue_build()
@export var keepout_margin: float = 1.0

var _gen: Node3D
var _pending: bool = false


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("nav_source")
	add_to_group("prop_keepout")
	_build()


func queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


## Прямоугольник в мировых XZ, где кольцо не ставит пропсы.
func keepout_rect() -> Rect2:
	var rect := Rect2()
	var first := true
	for x in [-size.x * 0.5, size.x * 0.5]:
		for z in [-size.y * 0.5, size.y * 0.5]:
			var p := global_transform * Vector3(x, 0, z)
			if first:
				rect = Rect2(Vector2(p.x, p.z), Vector2.ZERO)
				first = false
			else:
				rect = rect.expand(Vector2(p.x, p.z))
	return rect.grow(keepout_margin)


func _build() -> void:
	_pending = false
	if _gen:
		_gen.free()
	_gen = Node3D.new()
	_gen.name = "_Generated"
	# без owner — сгенерированное не попадает в сохранённую сцену
	add_child(_gen)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var mesh := BlockoutMesh.new()
	var placed := 0
	var tries := 0
	while placed < count and tries < count * 6:
		tries += 1
		var x := rng.randf_range(-size.x * 0.5, size.x * 0.5)
		var z := rng.randf_range(-size.y * 0.5, size.y * 0.5)
		var bs := Vector3(rng.randf_range(block_min.x, block_max.x), rng.randf_range(block_min.y, block_max.y), rng.randf_range(block_min.z, block_max.z))
		var reach := maxf(bs.x, bs.z) * 0.5
		if lane_width > 0.0 and absf(x) < lane_width * 0.5 + reach * 0.7:
			continue
		# к краю +Z завал выше: там обрушилось перекрытие
		var k := clampf(0.35 + (z / size.y + 0.5) * 0.65, 0.0, 1.0)
		var y := rng.randf_range(0.0, maxf(height * k - bs.y, 0.0))
		var basis := Basis(Vector3.UP, rng.randf_range(0.0, TAU)) * Basis(Vector3.RIGHT, rng.randf_range(-0.35, 0.35)) * Basis(Vector3.FORWARD, rng.randf_range(-0.3, 0.3))
		mesh.box_rotated(material_id, Vector3(x, y + bs.y * 0.5, z), bs, basis)
		placed += 1
	mesh.emit(_gen, "Body", true, true)
