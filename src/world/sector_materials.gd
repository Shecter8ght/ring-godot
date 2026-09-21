class_name SectorMaterials
extends RefCounted
## Материалы сектора по id: готовый PBR из assets/materials/<id>.tres, а если ассетов нет —
## плоский цвет из таблицы. Игра обязана собираться без assets/.

const FALLBACK := {
	"large_floor_tiles_02": Color(0.58, 0.57, 0.54),
	"worn_tile_floor": Color(0.62, 0.6, 0.55),
	"concrete_floor_worn_001": Color(0.45, 0.45, 0.44),
	"asphalt_02": Color(0.22, 0.22, 0.23),
	"painted_plaster_wall": Color(0.72, 0.7, 0.64),
	"concrete_wall_006": Color(0.5, 0.5, 0.48),
	"concrete_panels": Color(0.55, 0.54, 0.52),
	"concrete_block_wall_02": Color(0.5, 0.48, 0.45),
	"painted_metal_shutter": Color(0.35, 0.37, 0.4),
	"corrugated_iron_02": Color(0.45, 0.45, 0.47),
	"metal_plate": Color(0.4, 0.4, 0.42),
}

static var _cache: Dictionary = {}


static func get_material(id: String) -> Material:
	if _cache.has(id):
		return _cache[id]
	var path := "res://assets/materials/%s.tres" % id
	var mat: Material
	if ResourceLoader.exists(path):
		mat = load(path)
	else:
		var flat := StandardMaterial3D.new()
		flat.albedo_color = FALLBACK.get(id, Color(0.6, 0.2, 0.6))
		flat.roughness = 0.9
		mat = flat
	_cache[id] = mat
	return mat
