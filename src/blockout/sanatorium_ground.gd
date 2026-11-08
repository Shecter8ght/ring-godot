@tool
extends "res://src/blockout/heli_terrain.gd"
## Земля «Санатория» (tools/build_sanatorium.py пишет данные, tools/build_sanatorium_ground.py — массивы слоёв):
## рельеф, ступени детализации и коллизия — как у стенда «Плотины» (heli_terrain.gd), поверхность — восемь грунтов
## 4K шейдера sanatorium_ground (газон, вытоптанный газон, хвоя, мох, тропа, гранит, щебень, песок) по двум маскам.

const GROUND_SHADER: Shader = preload("res://src/world/sanatorium_ground.gdshader")
## вид шагов и попаданий по грунтам масок: вытоптанный газон, хвоя, мох, тропа, гранит, щебень, песок
const KINDS: Array[String] = ["grass", "dirt", "grass", "dirt", "gravel", "gravel", "sand"]

var _splat2: Image
var _mask2_file: String = ""
var _mask2_texture: ImageTexture


func _surface_shader() -> Shader:
	return GROUND_SHADER


func _extra_textures(material: ShaderMaterial, terrain: Dictionary) -> void:
	var file: String = String(terrain.get("splat2_file", ""))
	_mask2_file = file
	_mask2_texture = null
	_splat2 = null
	if file != "":
		var image: Image = Image.load_from_file(ProjectSettings.globalize_path(file))
		if image:
			_splat2 = image
			material.set_shader_parameter("splat2", ImageTexture.create_from_image(image))
	var gain: Array = terrain.get("layer_gain", [])
	if gain.size() == 8:
		material.set_shader_parameter("layer_gain", PackedFloat32Array(gain))


## Кисть земли: газон — основа, дальше семь грунтов двух масок (у второй маски канал A — сырость у воды, не кисть).
func brush_grounds() -> PackedStringArray:
	return PackedStringArray(["Газон", "Вытоптанный газон", "Хвоя", "Мох", "Тропа, грунтовка", "Гранит", "Щебень", "Песок"])


func brush_masks() -> Array[Image]:
	var out: Array[Image] = []
	if _splat != null:
		out.append(_splat)
	if _splat2 != null:
		out.append(_splat2)
	return out


func brush_mask_channels() -> PackedInt32Array:
	return PackedInt32Array([4, 3])


func brush_mask_paths() -> PackedStringArray:
	return PackedStringArray([_mask_file, _mask2_file])


func brush_push_masks() -> void:
	super.brush_push_masks()
	if _splat2 == null or _material == null:
		return
	if _mask2_texture == null:
		_mask2_texture = ImageTexture.create_from_image(_splat2)
		_material.set_shader_parameter("splat2", _mask2_texture)
	else:
		_mask2_texture.update(_splat2)


## Из чего земля в точке (шаги, попадания): преобладающий грунт двух масок; крутой склон — щебень и камень.
func surface_at(pos: Vector3, normal: Vector3) -> String:
	var cfg: Dictionary = Balance.TERRAIN_SURFACE
	if normal.y < float(cfg.rock_slope):
		return "gravel"
	if _splat == null or _cols < 2 or _rows < 2:
		return "grass"
	var span: Vector2 = Vector2(float(_cols - 1), float(_rows - 1)) * _step
	var uv: Vector2 = (Vector2(pos.x, pos.z) - _origin) / span
	var a: Color = _pixel(_splat, uv)
	var b: Color = _pixel(_splat2, uv) if _splat2 != null else Color(0, 0, 0, 0)
	var values: Array[float] = [a.r, a.g, a.b, a.a, b.r, b.g, b.b]
	var best: float = float(cfg.mask_min)
	var kind: String = "grass"
	for i: int in range(values.size()):
		if values[i] > best:
			best = values[i]
			kind = KINDS[i]
	return kind


func _pixel(image: Image, uv: Vector2) -> Color:
	var px: int = clampi(int(uv.x * image.get_width()), 0, image.get_width() - 1)
	var py: int = clampi(int(uv.y * image.get_height()), 0, image.get_height() - 1)
	return image.get_pixel(px, py)
