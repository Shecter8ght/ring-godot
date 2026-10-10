class_name ItemThumbs
extends Node
## Миниатюры конкретных экземпляров оружия: та же съёмка, что у печёных иконок (tools/icon_bake —
## ортокамера сбоку, дулом вправо, студийный свет), но с фактической сборкой — обвес, переходники
## по пазам, износ и магазин (вынут / другой). Два одинаковых автомата с разными сборками выглядят
## по-разному. Снимок — в фоне, по одному за кадр; пока его нет, окна рисуют обычную иконку и
## перерисовываются, когда он готов. Кэш — в памяти по ключу вида модели.

const PX := 96
## Снимков в памяти не больше этого (старые выбрасываются целиком — пересоберутся при показе).
const CACHE := 256

static var _self: ItemThumbs
static var _cache: Dictionary = {}

var _queue: Array[Dictionary] = []
var _queued: Dictionary = {}
## Кто ждёт снимок: ключ → [WeakRef CanvasItem].
var _waiting: Dictionary = {}
var _busy: bool = false


## Снимок экземпляра или null (нужна обычная иконка): у оружия без обвеса и со штатным магазином —
## всегда null, своя миниатюра не нужна. canvas перерисуется, когда снимок будет готов.
static func texture(entry: Dictionary, canvas: CanvasItem = null) -> Texture2D:
	var key: String = key_of(entry)
	if key == "":
		return null
	if _cache.has(key):
		return _cache[key]
	if DisplayServer.get_name() == "headless":
		return null
	var me: ItemThumbs = _instance()
	if me == null:
		return null
	me._request(key, entry, canvas)
	return null


## Ключ вида экземпляра; "" — выглядит как печёная иконка.
static func key_of(entry: Dictionary) -> String:
	var id: String = String(entry.get("id", ""))
	if not WeaponDb.is_weapon(id):
		return ""
	var mods: Dictionary = entry.get("mods", {})
	var mag: String = WeaponMods.mag_state(entry)
	if mods.is_empty() and mag == "*" and (entry.get("engraving", {}) as Dictionary).is_empty():
		return ""
	return WeaponCondition.model_key(id, mods, WeaponCondition.percent(entry), mag) + "|" + _placement(mods) + "|" + WeaponMark.key(entry.get("engraving", {}))


## Пазы, стороны и углы в ключ: сдвинул прицел — новая миниатюра.
static func _placement(mods: Dictionary) -> String:
	var parts: Array[String] = []
	for k: String in WeaponBuild.sorted_keys(mods):
		var rec: Dictionary = mods[k] if mods[k] is Dictionary else {}
		parts.append("%s@%s%s%s" % [k, str(rec.get("slot", "")), "f" if bool(rec.get("flip", false)) else "", str(rec.get("angle", ""))])
	return ",".join(parts)


static func _instance() -> ItemThumbs:
	if _self and is_instance_valid(_self):
		return _self
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null:
		return null
	_self = ItemThumbs.new()
	_self.name = "ItemThumbs"
	tree.root.add_child.call_deferred(_self)
	return _self


func _request(key: String, entry: Dictionary, canvas: CanvasItem) -> void:
	if canvas:
		var list: Array = _waiting.get(key, [])
		list.append(weakref(canvas))
		_waiting[key] = list
	if _queued.has(key):
		return
	_queued[key] = true
	_queue.append({"key": key, "entry": entry.duplicate(true)})


func _process(_delta: float) -> void:
	if _busy or _queue.is_empty() or not is_inside_tree():
		return
	_busy = true
	var job: Dictionary = _queue.pop_front()
	await _shoot(String(job.key), job.entry)
	_queued.erase(String(job.key))
	_busy = false


func _shoot(key: String, entry: Dictionary) -> void:
	var id: String = String(entry.id)
	var cells: Vector2i = ItemDb.size(id)
	var vp := SubViewport.new()
	vp.size = Vector2i(cells.x * PX, cells.y * PX)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_8X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_CLEAR_COLOR
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.75, 0.77, 0.82)
	e.ambient_light_energy = 0.9
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	e.tonemap_exposure = 1.1
	env.environment = e
	vp.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-45, -35, 0)
	light.light_energy = 2.2
	vp.add_child(light)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-20, 140, 0)
	fill.light_color = Color(0.75, 0.85, 1.0)
	fill.light_energy = 0.9
	vp.add_child(fill)
	var model: Node3D = WeaponModels.build(id, entry.get("mods", {}), 0, WeaponCondition.percent(entry), WeaponMods.mag_state(entry), entry.get("engraving", {}))
	vp.add_child(model)
	# фонарь и лазер в миниатюре не светят
	for l: Node in model.find_children("*", "Light3D", true, false):
		(l as Light3D).visible = false
	for b: Node in model.find_children("LaserBeam*", "Node3D", true, false):
		(b as Node3D).visible = false
	await get_tree().process_frame
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.01
	cam.far = 20.0
	vp.add_child(cam)
	var aabb: AABB = _aabb(model)
	var c: Vector3 = aabb.get_center()
	cam.look_at_from_position(c + Vector3(-1.0, 0.1, 0.0).normalized() * 3.0, c, Vector3.UP)
	# вписать с запасом 8 %, как у печёных иконок
	var inv: Transform3D = cam.global_transform.affine_inverse()
	var lo := Vector3(INF, INF, INF)
	var hi := -lo
	for i in range(8):
		var p: Vector3 = inv * aabb.get_endpoint(i)
		lo = lo.min(p)
		hi = hi.max(p)
	var ext: Vector3 = hi - lo
	var aspect: float = float(vp.size.x) / float(vp.size.y)
	cam.size = maxf(ext.y, ext.x / aspect) * 1.08
	var mid: Vector3 = (lo + hi) * 0.5
	cam.global_position = cam.global_transform * Vector3(mid.x, mid.y, 0.0)
	cam.current = true
	for i in range(3):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var img: Image = vp.get_texture().get_image()
	vp.queue_free()
	if img == null or img.is_empty():
		return
	if _cache.size() >= CACHE:
		_cache.clear()
	_cache[key] = ImageTexture.create_from_image(img)
	for ref: WeakRef in _waiting.get(key, []):
		var canvas: CanvasItem = ref.get_ref() as CanvasItem
		if canvas:
			canvas.queue_redraw()
	_waiting.erase(key)


## Габарит модели; магазин считается и вынутым — размер ствола в клетке не прыгает.
func _aabb(root: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for n: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if mi.mesh == null or String(mi.name).begins_with("Laser"):
			continue
		var hidden_mag: bool = not mi.visible and String(mi.get_meta("part", "")) == "mag"
		if not mi.is_visible_in_tree() and not hidden_mag:
			continue
		var box: AABB = mi.global_transform * mi.get_aabb()
		if first:
			out = box
			first = false
		else:
			out = out.merge(box)
	return out
