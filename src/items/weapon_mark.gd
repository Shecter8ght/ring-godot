class_name WeaponMark
extends Node3D
## Постоянная метка экземпляра и лазерная гравировка на самой поверхности оружия.

var weapon_id: String = ""
var inscription: Dictionary = {}
## Наклейка вместо гравировки: {id, site, scale, n} (Stickers); preview — образец в окне верстака.
var sticker: Dictionary = {}
static var _textures: Dictionary = {}
static var _surfaces: Dictionary = {}


static func new_id() -> String:
	return Crypto.new().generate_random_bytes(16).hex_encode()


static func identify(entry: Dictionary) -> void:
	if WeaponDb.is_weapon(String(entry.get("id", ""))) and String(entry.get("uid", "")) == "":
		entry["uid"] = new_id()


## Размеры надписи на выбор: множитель к обычной ширине и подпись в окне станка.
const SCALES := [[0.7, "Мелко"], [1.0, "Обычно"], [1.5, "Крупно"], [2.1, "Очень крупно"]]


static func key(mark: Dictionary) -> String:
	if mark.is_empty():
		return ""
	var out: String = "%s|%s|%s|%s|%.2f" % [String(mark.get("text", "")), String(mark.get("date", "")), String(mark.get("serial", "")), String(mark.get("site", "right_1")), float(mark.get("scale", 1.0))]
	for st: Variant in mark.get("stickers", []):
		out += "|%s:%s:%.2f:%d" % [String(st.get("id", "")), String(st.get("site", "")), float(st.get("scale", 1.0)), int(st.get("n", 0))]
	return out


## Всё, что нанесено на ствол, одним словарём для моделей и сети: гравировка и "stickers" — наклейки.
static func marks(entry: Dictionary) -> Dictionary:
	var out: Dictionary = (entry.get("engraving", {}) as Dictionary).duplicate(true)
	var list: Array = Stickers.of(entry)
	if not list.is_empty():
		out["stickers"] = list.duplicate(true)
	return out


## Позиции привязаны к коробке, рукоятке или затвору, вне магазинов и сменных обвесов.
static func positions(id: String) -> Array[Dictionary]:
	var weapon: Dictionary = WeaponDb.weapon(id)
	var pistol: bool = String(weapon.get("slot", "")) in ["sidearm", "launcher"]
	var base: Array = weapon.get("engraving_anchor", [0.42, 0.18] if pistol else [0.78, 0.23])
	var anchors: Array = weapon.get("engraving_positions", [[0.62, 0.20], [0.44, 0.16], [0.26, 0.12]] if pistol else
		[[base[0], base[1]], [base[0], float(base[1]) + 0.15], [base[0], float(base[1]) + 0.30], [float(base[0]) + 0.06, float(base[1]) - 0.07], [float(base[0]) + 0.06, float(base[1]) + 0.07]])
	if pistol:
		anchors = [anchors[0], anchors[2], weapon.get("engraving_slide_anchor", [0.50, 0.62])]
	var names: Array = ["рукоятка сверху", "рукоятка снизу", "затвор"] if pistol else ["коробка сзади", "коробка посередине", "коробка спереди", "коробка выше сзади", "коробка выше спереди"]
	var out: Array[Dictionary] = []
	for side: int in [-1, 1]:
		for index: int in range(anchors.size()):
			var anchor: Array = anchors[index] if anchors[index] is Array else (anchors[index] as Dictionary).get("right" if side < 0 else "left", [0.50, 0.62])
			out.append({"id": ("right_" if side < 0 else "left_") + str(index + 1), "name": ("Справа · " if side < 0 else "Слева · ") + names[index], "side": side, "anchor": anchor, "part": ("slide" if index == 2 else "grip") if pistol else "receiver"})
	return out


static func position_spec(id: String, site: String) -> Dictionary:
	for row: Dictionary in positions(id):
		if String(row.id) == site:
			return row
	return {}


static func clean_text(value: String) -> String:
	var out: String = ""
	for character: String in value.strip_edges():
		var code: int = character.unicode_at(0)
		if code >= 32 and code != 127 and not (code >= 0x200b and code <= 0x200f) and not (code >= 0x202a and code <= 0x202e):
			out += character
	return out.strip_edges()


static func make(entry: Dictionary, text: String, site: String = "right_1") -> Dictionary:
	identify(entry)
	var now: Dictionary = Time.get_datetime_dict_from_system()
	return {"text": clean_text(text), "date": "%02d.%02d.%04d" % [int(now.day), int(now.month), int(now.year)],
		"serial": String(entry.uid).substr(0, 10).to_upper(), "site": site}


static func attach(root: Node3D, id: String, mark: Dictionary) -> void:
	if mark.is_empty():
		return
	var index: int = 0
	for st: Variant in mark.get("stickers", []):
		if not st is Dictionary:
			continue
		var paper: WeaponMark = WeaponMark.new()
		paper.name = "Sticker%d" % index
		index += 1
		paper.weapon_id = id
		paper.sticker = (st as Dictionary).duplicate(true)
		paper.inscription = {"site": String(st.get("site", "right_1")), "scale": float(st.get("scale", 1.0))}
		paper.set_meta("weapon_clearance_ignore", true)
		root.add_child(paper)
	if String(mark.get("text", "")) == "":
		return
	var node: WeaponMark = WeaponMark.new()
	node.name = "Engraving"
	node.weapon_id = id
	node.inscription = mark.duplicate(true)
	node.set_meta("weapon_clearance_ignore", true)
	root.add_child(node)


func _ready() -> void:
	if DisplayServer.get_name() == "headless":
		return
	_build.call_deferred()


func _build() -> void:
	var root: Node3D = get_parent() as Node3D
	var pistol: bool = String(WeaponDb.weapon(weapon_id).get("slot", "")) in ["sidearm", "launcher"]
	var target: String = String(_position().get("part", "receiver"))
	var best: MeshInstance3D = null
	var score: float = -INF
	for child: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh: MeshInstance3D = child as MeshInstance3D
		var name_lower: String = String(mesh.name).to_lower()
		if mesh.mesh == null or not mesh.is_visible_in_tree() or name_lower.contains("arms") or name_lower.contains("hand"):
			continue
		if mesh.has_meta("weapon_clearance_ignore") or _attachment(mesh, root):
			continue
		if pistol and ((_under(mesh, "slide", root) and target != "slide") or (target == "slide" and not _under(mesh, "slide", root))):
			continue
		var box: AABB = mesh.get_aabb()
		var area: float = box.size.y * box.size.z
		if name_lower.contains("magazine") or name_lower.contains("stock") or name_lower.contains("round") or name_lower.contains("marking"):
			area *= 0.01
		if name_lower.contains("receiver") or name_lower.contains("frame") or name_lower.contains("body"):
			area *= 8.0
		if mesh.has_meta("engraving_positions"):
			area += 2000.0
		if pistol and target == "grip" and (_under(mesh, "frame", root) or _under(mesh, "grip", root)):
			area += 1000.0
		if area > score:
			score = area
			best = mesh
	if best == null:
		return
	var paper: bool = not sticker.is_empty()
	var maps: Dictionary = _sticker_maps() if paper else await _maps()
	if not is_inside_tree() or not is_instance_valid(best) or maps.is_empty():
		return
	var bounds: AABB = best.get_aabb()
	# размер по выбору игрока (scale): крупная надпись может занять почти всю длину детали
	var scale_k: float = clampf(float(inscription.get("scale", 1.0)), 0.5, 2.5)
	var width: float = minf(float(WeaponDb.weapon(weapon_id).get("engraving_width", Balance.ENGRAVING.pistol_width if pistol else Balance.ENGRAVING.width)) * scale_k,
		bounds.size.z * (0.62 if scale_k <= 1.0 else 0.92))
	var height: float = minf(width / 4.0, bounds.size.y * (0.65 if scale_k <= 1.0 else 0.9))
	if paper:
		# наклейка: свой размер и свои пропорции, не шире детали
		var ratio: float = StickerArt.aspect(String(sticker.get("id", "")))
		height = minf(float(Balance.STICKERS.pistol_size_m if pistol else Balance.STICKERS.size_m) * scale_k, bounds.size.y * 0.92)
		height = minf(height, bounds.size.z * 0.9 / ratio)
		width = height * ratio
	if width < 0.012 or height < 0.004:
		return
	# Свой слой получателя исключает ладонь и соседние детали из проекции.
	best.layers |= 1 << 18
	var decal: Decal = Decal.new()
	# наклеек на детали несколько — у каждой своё имя (образец в окне верстака ищут по «StickerPreview»)
	decal.name = ("StickerPreview" if bool(sticker.get("preview", false)) else "StickerMark_" + String(name)) if paper else "LaserMark"
	decal.cull_mask = 1 << 18
	# Объём только проецирует на существующую поверхность; рукоятка округлая, ей нужен запас.
	decal.size = Vector3(width, 0.028 if pistol else 0.008, height)
	decal.upper_fade = 0.0
	decal.lower_fade = 0.0
	decal.normal_fade = 0.0
	decal.distance_fade_enabled = true
	decal.distance_fade_begin = float(Balance.ENGRAVING.fade_begin)
	decal.distance_fade_length = float(Balance.ENGRAVING.fade_length)
	decal.texture_albedo = maps.albedo
	decal.texture_normal = maps.get("normal")
	decal.texture_orm = maps.orm
	decal.modulate = Color(1, 1, 1) if paper else Color(0.8, 0.8, 0.8)
	var side: int = int(_position().side)
	decal.basis = Basis(Vector3(0, 0, -side), Vector3(side, 0, 0), Vector3(0, -1, 0))
	decal.position = _surface(best, bounds)
	decal.set_meta("weapon_clearance_ignore", true)
	best.add_child(decal)


## Проекция ложится на металл, а не на край общего AABB (рукоять часто шире коробки).
func _surface(mesh: MeshInstance3D, bounds: AABB) -> Vector3:
	var location: Dictionary = _position().duplicate(true)
	# Запасные основы имеют свою геометрию: координаты подробного ассета им не подходят.
	var anchors: Array = mesh.get_meta("engraving_positions", [])
	if not anchors.is_empty():
		location.anchor = anchors[int(String(location.id).get_slice("_", 1)) - 1]
	var side: int = int(location.side)
	var signature: String = weapon_id + "|" + String(location.id) + "|" + String(mesh.name) + "|" + str(bounds)
	if _surfaces.has(signature):
		return _surfaces[signature]
	var point: Vector3 = bounds.get_center()
	var anchor: Array = location.anchor
	point.y = bounds.position.y + bounds.size.y * float(anchor[0])
	point.z = bounds.position.z + bounds.size.z * float(anchor[1])
	var faces: PackedVector3Array = mesh.mesh.get_faces()
	var from: Vector3 = Vector3(bounds.position.x - 0.1, point.y, point.z)
	var to: Vector3 = Vector3(bounds.end.x + 0.1, point.y, point.z)
	var nearest: float = INF if side < 0 else -INF
	for index: int in range(0, faces.size(), 3):
		var hit: Variant = Geometry3D.segment_intersects_triangle(from, to, faces[index], faces[index + 1], faces[index + 2])
		if hit is Vector3:
			nearest = minf(nearest, (hit as Vector3).x) if side < 0 else maxf(nearest, (hit as Vector3).x)
	point.x = (nearest if is_finite(nearest) else (bounds.position.x if side < 0 else bounds.end.x)) + side * 0.0004
	_surfaces[signature] = point
	return point


func _position() -> Dictionary:
	var site: Dictionary = position_spec(weapon_id, String(inscription.get("site", "right_1")))
	return positions(weapon_id)[0] if site.is_empty() else site


func _under(mesh: Node, label: String, root: Node) -> bool:
	var node: Node = mesh
	while node != null and node != root:
		var node_name: String = String(node.name).to_lower()
		if node_name.contains(label) and not (label == "slide" and node_name.contains("stop")):
			return true
		node = node.get_parent()
	return false


func _attachment(mesh: Node, root: Node) -> bool:
	var parent: Node = mesh
	while parent != root and parent != null:
		if parent is Skeleton3D and (parent as Skeleton3D).find_bone("hand.L") >= 0:
			# В сцене рук само оружие тоже находится на скелете; отсекаются только меши рук.
			if String(mesh.name).to_lower().contains("arm"):
				return true
		if parent.has_meta("mod_id") or parent.has_meta("weapon_clearance_ignore"):
			return true
		parent = parent.get_parent()
	return false


## Наклейка: готовый рисунок (StickerArt), гладкая плёнка без рельефа.
func _sticker_maps() -> Dictionary:
	var signature: String = "sticker|%s|%d" % [String(sticker.get("id", "")), int(sticker.get("n", 0))]
	if _textures.has(signature):
		return _textures[signature]
	var orm: Image = Image.create(1, 1, false, Image.FORMAT_RGB8)
	orm.fill(Color(1.0, 0.42, 0.0))
	var maps: Dictionary = {"albedo": StickerArt.texture(String(sticker.get("id", "")), int(sticker.get("n", 0))), "orm": ImageTexture.create_from_image(orm)}
	if _textures.size() >= int(Balance.ENGRAVING.cache):
		_textures.clear()
	_textures[signature] = maps
	return maps


func _maps() -> Dictionary:
	# Место меняет модель, но не изображение букв: все позиции используют один набор карт.
	var signature: String = "%s|%s|%s" % [String(inscription.text), String(inscription.date), String(inscription.serial)]
	if _textures.has(signature):
		return _textures[signature]
	var viewport: SubViewport = SubViewport.new()
	viewport.size = Vector2i(1024, 256)
	viewport.transparent_bg = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(viewport)
	var text: Label = Label.new()
	text.position = Vector2(12, 8)
	text.size = Vector2(1000, 145)
	text.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	text.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	text.add_theme_font_size_override("font_size", 64)
	text.text = String(inscription.text)
	while ThemeDB.fallback_font.get_string_size(text.text, HORIZONTAL_ALIGNMENT_LEFT, -1, text.get_theme_font_size("font_size")).x > 990:
		text.add_theme_font_size_override("font_size", text.get_theme_font_size("font_size") - 1)
	viewport.add_child(text)
	var detail: Label = Label.new()
	detail.position = Vector2(12, 158)
	detail.size = Vector2(1000, 80)
	detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	detail.add_theme_font_size_override("font_size", 40)
	detail.text = "%s  № %s" % [String(inscription.date), String(inscription.serial)]
	viewport.add_child(detail)
	for frame: int in range(3):
		if not is_inside_tree():
			return {}
		await get_tree().process_frame
	if not is_inside_tree():
		return {}
	await RenderingServer.frame_post_draw
	if not is_inside_tree():
		return {}
	var picture: Image = viewport.get_texture().get_image()
	viewport.queue_free()
	var normal: Image = Image.create(1024, 256, false, Image.FORMAT_RGBA8)
	for y: int in range(256):
		for x: int in range(1024):
			var dx: float = picture.get_pixel(maxi(x - 1, 0), y).a - picture.get_pixel(mini(x + 1, 1023), y).a
			var dy: float = picture.get_pixel(x, maxi(y - 1, 0)).a - picture.get_pixel(x, mini(y + 1, 255)).a
			normal.set_pixel(x, y, Color(0.5 + dx * 0.12, 0.5 + dy * 0.12, 1.0, picture.get_pixel(x, y).a))
	var orm: Image = Image.create(1, 1, false, Image.FORMAT_RGB8)
	orm.fill(Color(1.0, 0.62, 0.7))
	var maps: Dictionary = {"albedo": ImageTexture.create_from_image(picture), "normal": ImageTexture.create_from_image(normal), "orm": ImageTexture.create_from_image(orm)}
	if _textures.size() >= int(Balance.ENGRAVING.cache):
		_textures.clear()
	_textures[signature] = maps
	return maps
