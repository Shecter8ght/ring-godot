class_name ItemThumbs
extends Node
## Миниатюры конкретных экземпляров оружия: та же съёмка, что у печёных иконок (tools/icon_bake —
## ортокамера сбоку, дулом вправо, студия ItemStudio), но с фактической сборкой — обвес, переходники
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


## Крупный снимок предмета для карточки витрины (торговец) кадром frame (точки, пропорции картинки карточки):
## печёная иконка (96 на клетку, по клеткам предмета) в большой карточке расплывается и мелка. Оружие — его
## сборка (и без обвеса), остальное — модель предмета (ItemModels, как у печёных иконок); наклейки — null: их
## иконки нарисованы, а не сняты с модели; пустой снимок (модели нет) — тоже null, рисуется иконка.
static func card_texture(entry: Dictionary, frame: Vector2i, canvas: CanvasItem = null, urgent: bool = false) -> Texture2D:
	var id: String = String(entry.get("id", ""))
	if id == "" or id.begins_with("sticker_"):
		return null
	var key: String = "card%dx%d|item|%s" % [frame.x, frame.y, id]
	if WeaponDb.is_weapon(id):
		var mods: Dictionary = entry.get("mods", {})
		key = "card%dx%d|%s|%s|%s" % [frame.x, frame.y, WeaponCondition.model_key(id, mods, WeaponCondition.percent(entry),
			WeaponMods.mag_state(entry)), _placement(mods), WeaponMark.key(WeaponMark.marks(entry))]
	if _cache.has(key):
		return _cache[key]
	if DisplayServer.get_name() == "headless":
		return null
	var me: ItemThumbs = _instance()
	if me == null:
		return null
	me._request(key, entry, canvas, frame, urgent)
	return null


## Ключ вида экземпляра; "" — выглядит как печёная иконка.
static func key_of(entry: Dictionary) -> String:
	var id: String = String(entry.get("id", ""))
	if not WeaponDb.is_weapon(id):
		return ""
	var mods: Dictionary = entry.get("mods", {})
	var mag: String = WeaponMods.mag_state(entry)
	if mods.is_empty() and mag == "*" and WeaponMark.marks(entry).is_empty():
		return ""
	return WeaponCondition.model_key(id, mods, WeaponCondition.percent(entry), mag) + "|" + _placement(mods) + "|" + WeaponMark.key(WeaponMark.marks(entry))


## Пазы, стороны и углы в ключ: сдвинул прицел — новая миниатюра.
static func _placement(mods: Dictionary) -> String:
	var parts: Array[String] = []
	for k: String in WeaponBuild.sorted_keys(mods):
		var rec: Dictionary = mods[k] if mods[k] is Dictionary else {}
		parts.append("%s@%s%s%s" % [k, str(rec.get("slot", "")), "f" if bool(rec.get("flip", false)) else "", str(rec.get("angle", ""))])
		if rec.has("remote"):
			parts.append("remote=" + str(rec.remote))
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


## urgent — вперёд очереди (большой снимок витрины не ждёт мелкие в списке).
func _request(key: String, entry: Dictionary, canvas: CanvasItem, frame: Vector2i = Vector2i.ZERO, urgent: bool = false) -> void:
	if canvas:
		var list: Array = _waiting.get(key, [])
		list.append(weakref(canvas))
		_waiting[key] = list
	if _queued.has(key):
		return
	_queued[key] = true
	var job := {"key": key, "entry": entry.duplicate(true), "frame": frame}
	if urgent:
		_queue.push_front(job)
	else:
		_queue.append(job)


func _process(_delta: float) -> void:
	if _busy or _queue.is_empty() or not is_inside_tree():
		return
	_busy = true
	var job: Dictionary = _queue.pop_front()
	await _shoot(String(job.key), job.entry, job.get("frame", Vector2i.ZERO) as Vector2i)
	_queued.erase(String(job.key))
	_busy = false


## frame — свой кадр (карточка витрины); нулевой — по клеткам предмета, как у печёной иконки.
func _shoot(key: String, entry: Dictionary, frame: Vector2i = Vector2i.ZERO) -> void:
	var id: String = String(entry.id)
	var cells: Vector2i = ItemDb.size(id)
	var vp := SubViewport.new()
	# подробные предметы (Balance.ICON_DETAIL): миниатюра в клетках — во столько раз подробнее, и любой их снимок
	# делается с запасом и показывается пересчитанным под размер на экране (ItemIcons.sized)
	var detail: int = int(Balance.ICON_DETAIL.get(id, 1))
	var card: bool = frame.x > 0 and frame.y > 0
	var master: Vector2i = frame if card else Vector2i(cells.x * PX, cells.y * PX) * detail
	vp.size = master * (Balance.ICON_DETAIL_SUPERSAMPLE if detail > 1 else 1)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_8X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	ItemStudio.setup(vp)
	var weapon: bool = WeaponDb.is_weapon(id)
	var model: Node3D = WeaponModels.build(id, entry.get("mods", {}), 0, WeaponCondition.percent(entry), WeaponMods.mag_state(entry), WeaponMark.marks(entry)) 		if weapon else ItemModels.build(id)
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
	# как у печёных иконок: оружие и обвес — сбоку, дулом вправо, остальное — на три четверти сверху
	var dir: Vector3 = ItemStudio.view_dir(id, weapon or String(ItemDb.item(id).get("cat", "")) == "mod")
	cam.look_at_from_position(c + dir * 3.0, c, Vector3.UP)
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
	if detail > 1:
		# подробный предмет — точно по вершинам, как у его печёного значка
		ItemStudio.fit_exact(cam, model, aspect, Balance.ICON_DETAIL_MARGIN)
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
	# пустой кадр (у предмета нет модели) — не снимок: окно нарисует печёную иконку
	var shot: ImageTexture = null
	if img.get_used_rect().has_area():
		if detail > 1 and not card:
			# миниатюра в клетках: запас съёмки сразу сводится к размеру мастера (карточка витрины хранится крупной)
			img.convert(Image.FORMAT_RGBA8)
			img.fix_alpha_edges()
			img.resize(master.x, master.y, Image.INTERPOLATE_LANCZOS)
		shot = ImageTexture.create_from_image(img)
		if detail > 1:
			shot.set_meta(ItemIcons.META_DETAIL, true)
	_cache[key] = shot
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
