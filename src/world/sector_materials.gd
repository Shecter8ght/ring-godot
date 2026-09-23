@tool
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

## Блокаут: серые стены без текстур, классы по конструкции (см. docs/building_standards.md).
## Тон различает класс: противопожарные — с красноватым оттенком, перегородки — светлее.
const GREYBOX := {
	"gb_facade": Color(0.56, 0.57, 0.58),
	"gb_fire": Color(0.6, 0.5, 0.48),
	"gb_structural": Color(0.62, 0.62, 0.6),
	"gb_partition": Color(0.78, 0.77, 0.73),
	"gb_fence": Color(0.5, 0.51, 0.49),
	"gb_slab": Color(0.52, 0.52, 0.51),
}
## Сетка блокаута: тонкая линия каждый метр, жирная — каждые 4 м (размер плитки текстуры).
const GRID_TILE_M := 4.0

## Процедурные материалы без текстур: стекло витрин, тёмная сталь рам, панель вывески.
const SPECIAL := ["glass", "steel_dark", "sign_panel"]

static var _cache: Dictionary = {}
static var _grid_tex: Texture2D


## Серая сетка 1 м / 4 м — по ней видно масштаб без текстур.
static func _grid() -> Texture2D:
	if _grid_tex:
		return _grid_tex
	var n := 512
	var img := Image.create(n, n, true, Image.FORMAT_RGB8)
	img.fill(Color(1, 1, 1))
	var cell := n / 4
	for i in range(n):
		for k in range(4):
			var major := k == 0
			var w := 3 if major else 1
			var c := Color(0.62, 0.62, 0.62) if major else Color(0.84, 0.84, 0.84)
			for t in range(w):
				var x := (k * cell + t) % n
				img.set_pixel(x, i, c)
				img.set_pixel(i, x, c)
	img.generate_mipmaps()
	_grid_tex = ImageTexture.create_from_image(img)
	return _grid_tex


static func _greybox(id: String) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = GREYBOX[id]
	m.albedo_texture = _grid()
	m.uv1_triplanar = true
	m.uv1_world_triplanar = true
	m.uv1_scale = Vector3.ONE / GRID_TILE_M
	m.roughness = 0.92
	return m


static func _special(id: String) -> Material:
	var m := StandardMaterial3D.new()
	match id:
		"glass":
			m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			m.albedo_color = Color(0.62, 0.72, 0.78, 0.22)
			m.roughness = 0.08
			m.metallic = 0.1
			m.metallic_specular = 0.8
			m.cull_mode = BaseMaterial3D.CULL_DISABLED
		"steel_dark":
			m.albedo_color = Color(0.12, 0.12, 0.13)
			m.roughness = 0.45
			m.metallic = 0.85
		"sign_panel":
			m.albedo_color = Color(0.06, 0.06, 0.07)
			m.roughness = 0.6
			m.emission_enabled = true
			m.emission = Color(0.9, 0.75, 0.5)
			m.emission_energy_multiplier = 0.08
	return m


## Материалы стен с вырезом у камеры — их дистанции фейда обновляет камера каждый кадр.
static var _cutaway: Array[BaseMaterial3D] = []


## cutaway — вариант материала, который растворяется (дизеринг) вблизи камеры: для стен, не для полов.
## Ткань баннеров: матовая, чуть просвечивает на солнце.
static func _banner(i: int) -> Material:
	var colors := [Color(0.12, 0.14, 0.36), Color(0.3, 0.12, 0.36), Color(0.45, 0.1, 0.1), Color(0.1, 0.25, 0.3)]
	var m := StandardMaterial3D.new()
	m.albedo_color = colors[i % colors.size()]
	m.roughness = 0.95
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	return m


static func get_material(id: String, cutaway: bool = false) -> Material:
	var key := id + ("#cut" if cutaway else "")
	if _cache.has(key):
		return _cache[key]
	var path := "res://assets/materials/%s.tres" % id
	var mat: Material
	if id in SPECIAL:
		mat = _special(id)
	elif GREYBOX.has(id):
		mat = _greybox(id)
	elif id.begins_with("banner_"):
		mat = _banner(int(id.trim_prefix("banner_")))
	elif ResourceLoader.exists(path):
		mat = load(path)
		if cutaway:
			mat = mat.duplicate()
	else:
		var flat := StandardMaterial3D.new()
		flat.albedo_color = FALLBACK.get(id, Color(0.6, 0.2, 0.6))
		flat.roughness = 0.9
		mat = flat
	if cutaway and mat is BaseMaterial3D:
		var bm := mat as BaseMaterial3D
		bm.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
		_cutaway.append(bm)
	_cache[key] = mat
	return mat


## Плоский цвет для процедурных пропсов — с вырезом у камеры, кэш по параметрам.
static func flat(color: Color, rough: float, metal: float) -> Material:
	var key := "flat:%s:%.2f:%.2f" % [color.to_html(false), rough, metal]
	if _cache.has(key):
		return _cache[key]
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	m.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
	_cutaway.append(m)
	_cache[key] = m
	return m


## Материал склеенных пропсов (PropBatcher): цвет — из вершин, общие только шероховатость
## и металл. Тоже с вырезом у камеры.
static func flat_vc(rough: float, metal: float) -> Material:
	var key := "flatvc:%.2f:%.2f" % [rough, metal]
	if _cache.has(key):
		return _cache[key]
	var m := StandardMaterial3D.new()
	m.vertex_color_use_as_albedo = true
	# цвета вершин взяты из albedo_color исходных материалов — они в sRGB
	m.vertex_color_is_srgb = true
	m.roughness = rough
	m.metallic = metal
	m.distance_fade_mode = BaseMaterial3D.DISTANCE_FADE_PIXEL_DITHER
	_cutaway.append(m)
	_cache[key] = m
	return m


## Камера зовёт каждый кадр: всё ближе near к камере — невидимо, дальше far — целиком.
static func set_cutaway_distance(near: float, far: float) -> void:
	for m in _cutaway:
		m.distance_fade_min_distance = near
		m.distance_fade_max_distance = far
