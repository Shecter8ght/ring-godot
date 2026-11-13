@tool
class_name LootContainerVisual
extends Node3D
## Контейнер-модель с закрытым и открытым видом: общий слой для мебели общежития (DormLootBox) и для рейдовых
## контейнеров по виду (LootContainer.kind, каталог data/loot_containers.json). Закрытая модель и, если у открытого
## своя (ящики, коробка), — открытая, скрытая до обыска. Обыск (сигнал LootContainer.opened) — open(): закрытая
## прячется, открытая показывается, крышка и створка (index movers с углом open) доводятся от закрытого положения
## до открытого. Открытую модель можно делать лениво — при первом open() (в рейде их сотни, раскрывается малая часть).

const OPEN_SEC: float = 0.6
const CATALOG_PATH: String = "res://data/loot_containers.json"
## Суффикс узлов упрощённой сетки (LOD1) у моделей с расстоянием смены «lod» в каталоге.
const LOD_SUFFIX: String = "_lod1"

static var _catalog: Dictionary = {}
static var _indexes: Dictionary = {}
static var _mats: Dictionary = {}

var closed: Node3D
## Своя модель открытого; null — открывается та же (лежащий чемодан: створка из позы «закрыто»).
var opened_model: Node3D
## Подвижное открытого: [{node, axis, rest (базис узла в открытом), from (угол закрытого, градусы)}]; у выдвижного (slide) — ещё
## rest_pos (положение в открытом), from — смещение закрытого вдоль axis, м.
var movers: Array[Dictionary] = []
var is_open: bool = false
## Лениво: возвращает узел открытой модели (добавляется потомком при первом open()); info и pose — как у setup().
var _open_factory: Callable = Callable()
var _open_info: Dictionary = {}


## Открытое прячется, подвижное — в закрытое положение (у той же модели оно уже стоит позой из расстановки).
func setup(closed_node: Node3D, open_node: Node3D, info: Dictionary, pose: Dictionary) -> void:
	closed = closed_node
	_prepare_open(open_node, info, pose)


## То же, но открытая модель строится только при первом open().
func setup_lazy(closed_node: Node3D, open_factory: Callable, info: Dictionary) -> void:
	closed = closed_node
	_open_factory = open_factory
	_open_info = info


func _prepare_open(open_node: Node3D, info: Dictionary, pose: Dictionary) -> void:
	opened_model = open_node
	var target: Node3D = open_node if open_node != null else closed
	for mover: Dictionary in info.get("movers", []):
		if not mover.has("open"):
			continue
		var part: Node3D = target.find_child(String(mover.node), true, false) as Node3D
		if part == null:
			continue
		var axis: Vector3 = Vector3(float(mover.axis[0]), float(mover.axis[1]), float(mover.axis[2])).normalized()
		var from: float = float(pose.get(String(mover.node), -float(mover.open)))
		var rest: Basis = part.basis
		if String(mover.get("kind", "hinge")) == "slide":
			# выдвижное (ящик картотеки, лоток кассы): open — ход, м, вдоль axis; закрытое положение = открытое − axis · ход
			var rest_pos: Vector3 = part.position
			if open_node == null:
				rest_pos = part.position - axis * from
			else:
				part.position = rest_pos + axis * from
			movers.append({"node": part, "axis": axis, "rest": rest, "from": from, "slide": true, "rest_pos": rest_pos})
			continue
		if open_node == null:
			# поза «закрыто» уже применена расстановкой: открытый базис — обратно на её угол
			rest = Basis(axis, deg_to_rad(-from)) * part.basis
		else:
			part.basis = Basis(axis, deg_to_rad(from)) * rest
		movers.append({"node": part, "axis": axis, "rest": rest, "from": from})
	if open_node != null:
		open_node.visible = false


## instant — без качания крышки (контейнер уже обыскан к моменту появления: поздний вход, переимпорт сцены).
func open(instant: bool = false) -> void:
	if is_open:
		return
	is_open = true
	if opened_model == null and _open_factory.is_valid():
		var node: Node3D = _open_factory.call() as Node3D
		if node != null:
			add_child(node)
			_prepare_open(node, _open_info, {})
	if opened_model != null:
		closed.visible = false
		opened_model.visible = true
	if movers.is_empty():
		return
	if instant:
		_swing(1.0)
		return
	var tween: Tween = create_tween()
	tween.tween_method(_swing, 0.0, 1.0, OPEN_SEC).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


func _swing(t: float) -> void:
	for m: Dictionary in movers:
		var part: Node3D = m.node as Node3D
		if m.has("slide"):
			part.position = (m.rest_pos as Vector3) + (m.axis as Vector3) * float(m.from) * (1.0 - t)
			continue
		part.basis = Basis(m.axis as Vector3, deg_to_rad(float(m.from) * (1.0 - t))) * (m.rest as Basis)


# --- каталог моделей контейнеров рейда (data/loot_containers.json) ---------------------------------------------------

static func catalog() -> Dictionary:
	if _catalog.is_empty():
		_catalog = _read(CATALOG_PATH)
	return _catalog


static func _read(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}


## Модель по умолчанию вида ("" — нет: вид показывается боксом).
static func kind_model(kind: String) -> String:
	return String(((catalog().get("kinds", {}) as Dictionary).get(kind, {}) as Dictionary).get("model", ""))


## Описание модели из каталога: open, variants, aabb, open_aabb ({} — модели нет).
static func model_spec(model: String) -> Dictionary:
	return (catalog().get("models", {}) as Dictionary).get(model, {})


## Модель контейнера вида kind (model_id — своя вместо модели вида): закрытый узел, открытый — лениво. variant_seed
## выбирает вариант отделки (устойчиво по имени узла). null — модели нет или файла нет: остаётся прежний вид.
static func create(kind: String, model_id: String, variant_seed: int) -> LootContainerVisual:
	var model: String = model_id if model_id != "" else kind_model(kind)
	if model == "":
		return null
	var spec: Dictionary = model_spec(model)
	if spec.is_empty():
		return null
	# модель может быть из другого источника (свои контейнеры: assets/models/loot_containers): dir / index — в её записи
	var dir: String = String(spec.get("dir", catalog().get("dir", "")))
	var index_path: String = String(spec.get("index", catalog().get("index", "")))
	var lod_dist: float = float(spec.get("lod", 0.0))
	var path: String = "%s/%s.gltf" % [dir, model]
	if not ResourceLoader.exists(path):
		return null
	var variants: Array = spec.get("variants", [""]) as Array
	var variant: String = String(variants[variant_seed % maxi(1, variants.size())]) if not variants.is_empty() else ""
	var far: float = float(catalog().get("far", 45.0))
	var closed_node: Node3D = _instance(dir, model, variant, far, index_path, lod_dist)
	if closed_node == null:
		return null
	closed_node.name = "Закрыт"
	var vis: LootContainerVisual = LootContainerVisual.new()
	vis.name = "Модель"
	vis.add_child(closed_node)
	var open_id: String = String(spec.get("open", ""))
	if open_id == "":
		vis.setup(closed_node, null, {}, {})
	else:
		var info: Dictionary = (_index_at(index_path).get(open_id, {}) as Dictionary)
		vis.setup_lazy(closed_node, func() -> Node3D:
			var n: Node3D = _instance(dir, open_id, variant, far, index_path, lod_dist)
			if n != null:
				n.name = "Открыт"
			return n, info)
	return vis


## Индекс моделей источника (furniture.json общежития или loot_containers_models.json): движки, габариты, подвижное.
static func _index_at(path: String) -> Dictionary:
	if not _indexes.has(path):
		_indexes[path] = _read(path)
	return _indexes[path] as Dictionary


## lod_dist > 0 — у модели есть узлы «*_lod1» (≈ ¼ треугольников): основные сетки рисуются до lod_dist, упрощённые — от него до far.
static func _instance(dir: String, model: String, variant: String, far: float, index_path: String, lod_dist: float = 0.0) -> Node3D:
	var path: String = "%s/%s.gltf" % [dir, model]
	if not ResourceLoader.exists(path):
		return null
	var node: Node3D = (load(path) as PackedScene).instantiate() as Node3D
	var info: Dictionary = _index_at(index_path).get(model, {}) as Dictionary
	for found: Node in node.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = found as MeshInstance3D
		# дальше far модель не рисуется: сотни контейнеров карты не дают тысяч сеток в кадре
		mesh_node.visibility_range_end = far
		mesh_node.visibility_range_end_margin = 2.0
		mesh_node.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		if lod_dist > 0.0:
			if String(mesh_node.name).ends_with(LOD_SUFFIX):
				mesh_node.visibility_range_begin = lod_dist
				mesh_node.visibility_range_begin_margin = 1.0
			else:
				mesh_node.visibility_range_end = lod_dist
				mesh_node.visibility_range_end_margin = 1.0
		if variant == "" or mesh_node.mesh == null:
			continue
		for s: int in range(mesh_node.mesh.get_surface_count()):
			var source: StandardMaterial3D = mesh_node.mesh.surface_get_material(s) as StandardMaterial3D
			if source == null:
				continue
			var mat: StandardMaterial3D = _variant_material(source, model, variant, info, dir)
			if mat != source:
				mesh_node.set_surface_override_material(s, mat)
	return node


## Вариант отделки: карты textures/<набор>__<код>_* вместо карт материала набора (как у мебели общежития).
static func _variant_material(source: StandardMaterial3D, model: String, variant: String, info: Dictionary, dir: String) -> StandardMaterial3D:
	var name_id: String = source.resource_name
	var key: String = "%s|%s|%s" % [model, variant, name_id]
	if _mats.has(key):
		return _mats[key] as StandardMaterial3D
	var mat: StandardMaterial3D = source
	if name_id == String(info.get("material", model)):
		mat = source.duplicate() as StandardMaterial3D
		var base: String = "%s/textures/%s__%s_" % [dir, name_id, variant]
		if ResourceLoader.exists(base + "baseColor.webp"):
			mat.albedo_texture = load(base + "baseColor.webp") as Texture2D
			var orm_path: String = base + "occlusionRoughnessMetallic.webp"
			if ResourceLoader.exists(orm_path):
				var orm: Texture2D = load(orm_path) as Texture2D
				mat.roughness_texture = orm
				mat.metallic_texture = orm
				if mat.ao_enabled:
					mat.ao_texture = orm
			if ResourceLoader.exists(base + "normal.webp"):
				mat.normal_texture = load(base + "normal.webp") as Texture2D
	_mats[key] = mat
	return mat
