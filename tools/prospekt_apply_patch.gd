extends Node
## Применяет патч этапа к блокауту «Проспекта» (docs/tasks/prospekt_north_vershina_build.md): убирает и добавляет узлы
## в scenes/levels/prospekt_study.tscn по data/blockouts/prospekt_patch_<этап>.json (его собирает tools/prospekt_patch.py).
##   tools/godot.cmd --headless res://tools/prospekt_apply_patch.tscn -- 1_street
## Куски улиц — PlanPiece в Landscape/Улицы/<папка>, вещи — PropSpot в Filler/Наполнение/<папка> (как у разовых
## переносов prospekt_streets_to_nodes / prospekt_items_to_nodes); у каждого добавленного узла meta patch_stage = имя
## этапа. Повторный запуск того же этапа сначала убирает узлы с этой меткой — дубликатов нет; убранное «remove»
## обратно не возвращается (копия сцены перед первым применением — на совести запускающего).
## Формат патча — в шапке tools/prospekt_patch.py.

const SCENE: String = "res://scenes/levels/prospekt_study.tscn"
const PATCH_DIR: String = "res://data/blockouts/"
const META: String = "patch_stage"
const PLAN_LISTS: Array = ["surfaces", "ground_holes", "walk_holes", "slabs", "walls", "boxes", "columns", "stairs",
	"ramps", "beams", "lamps", "signs"]
const LIST_FOLDERS: Dictionary = {
	"surfaces": "Покрытия", "ground_holes": "Вырезы в земле", "walk_holes": "Вырезы тротуаров", "slabs": "Плиты",
	"walls": "Стены", "boxes": "Коробки", "columns": "Колонны", "stairs": "Лестницы", "ramps": "Пандусы",
	"beams": "Балки и трубы", "lamps": "Фонари (свет)", "signs": "Надписи"}
const MATS: Dictionary = {
	"wall": "Простые", "concrete": "Бетон", "steel": "Сталь", "mud": "Грунт", "tunnel_tile": "Кафель перехода",
	"fountain_tile": "Плитка фонтана", "ground": "Земля", "dark": "Тёмное", "hazard_yellow": "Жёлтая разметка",
	"accent": "Цветное", "walk": "Тротуар", "grass": "Газоны", "road": "Асфальт", "rust": "Ржавое", "wood": "Дерево",
	"paint_blue": "Синяя краска", "pipe_red": "Красные трубы", "graffiti": "Граффити", "rock": "Камень", "slab": "Плиты",
	"tray": "Лотки", "marker": "Метки", "exit_sign": "Указатели", "paint_white": "Белая краска", "water": "Вода",
	"black": "Чёрное", "stripe": "Светлое"}
const SURFACE_MATS: Dictionary = {"road": "Асфальт", "grass": "Газон", "walk": "Тротуар", "parking": "Парковка",
	"court": "Площадка", "mud": "Грунт", "slab": "Плиты", "fountain_floor": "Дно фонтана"}
const SLAB_MATS: Dictionary = {"tunnel_floor": "Пол перехода", "tunnel_ceiling": "Потолок перехода", "slab": "Перекрытие",
	"walk": "Пол", "pit_floor": "Пол паркинга", "concrete": "Перекрытие бетон", "mud": "Грунт", "steel": "Мост"}
## Папки вещей — как у prospekt_items_to_nodes.gd.
const FOLDERS: Dictionary = {
	"Машины и техника": ["car", "car_open", "car_wreck", "suv_open", "truck", "truck_cab", "van", "taxi", "police_car",
		"ambulance", "armored_truck", "avtozak", "btr", "bus_city", "bus_over", "bus_wreck", "paz", "paz_police", "minibus",
		"dump_truck", "excavator", "fire_truck", "flatbed", "inkassator", "mixer", "roller", "tractor", "trailer", "loco_tem",
		"wagon_box", "wagon_pass", "cart", "cart_row"],
	"Заборы и ограждения": ["district_fence", "rail_fence", "fence", "bar_fence", "chainlink", "hazard_fence", "ped_fence",
		"crowd_barrier", "jersey", "jersey_rw", "water_barrier", "water_barrier_w", "deposit_wall", "po2", "po2_breach",
		"po2_fallen", "bollard", "barrier_arm", "sandbags", "sandbag_post", "half_sphere", "cone", "tape", "speed_bump", "mesh_sign"],
	"Мусор": ["paper", "paper_ball", "glass_shards", "bags", "can", "bottle", "trash_pile", "dust", "puddle", "tires", "boxes",
		"pallets", "suitcase", "water_bottles", "body_mar", "body_sheet", "shell", "shell_open", "rebar", "pipes", "reel",
		"slab", "log_pile", "pile_dirt", "pile_sand"],
	"Киоски, лавки, площадки": ["kiosk", "food_kiosk", "stall", "booth", "cabin", "outhouse", "bus_stop", "cafe_table", "bench",
		"ad_column", "billboard", "billboard_fallen", "stage", "monument", "flowerbed", "planter", "hedge", "sandbox", "seesaw",
		"slide", "swing", "climber", "hoop"],
	"Деревья, кусты, камни": ["tree_birch", "tree_poplar", "tree_round", "bush_big", "rock_a", "rock_b", "rock_c"],
	"Столбы и фонари": ["pole_conc", "pole_trolley", "lamp", "lamp_park", "ornate_lamp", "mast", "floodlight", "flagpole", "signal_arm"],
	"Гаражи, контейнеры, будки": ["garage", "garage_open", "container20", "container20_open", "container40", "container40_open",
		"ktp", "ktp_open", "watchtower", "army_tent", "tent", "rack_high", "vault_door", "fire_hose", "barrel"],
	"Рельсы": ["track_3m"],
	"Кондиционеры": ["ac_unit"],
}
const TITLES: Dictionary = {
	"car": "Машина", "truck": "Грузовик", "van": "Фургон", "bus_city": "Автобус", "kiosk": "Киоск", "bench": "Скамейка",
	"tree_birch": "Берёза", "ktp": "Трансформаторная", "bus_stop": "Остановка", "ad_column": "Афишная тумба",
	"half_sphere": "Полусфера", "bollard": "Столбик", "signal_arm": "Сигнал"}

var _root: Node3D
var _counts: Dictionary = {}
var _stage: String = ""
var _filler: Node
var _item_index: Dictionary = {}
var _item_order: int = 1000000
var _piece_order: int = 1000000
var _stats: Dictionary = {"убрано прежних узлов этапа": 0, "убрано вещей": 0, "убрано кусков": 0, "убрано узлов": 0,
	"добавлено кусков": 0, "добавлено вещей": 0, "добавлено зданий": 0}


func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.is_empty():
		push_error("prospekt_apply_patch: укажите этап (-- 1_street)")
		get_tree().quit(2)
		return
	_stage = String(args[0])
	var path: String = PATCH_DIR + "prospekt_patch_%s.json" % _stage
	var patch: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not (patch is Dictionary):
		push_error("prospekt_apply_patch: не читается %s" % path)
		get_tree().quit(2)
		return
	_root = (load(SCENE) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN) as Node3D
	var landscape: Node = _root.get_node("Landscape")
	landscape.call("load_plan")
	_filler = _root.get_node("Filler")
	_filler.set("landscape", landscape)
	var plan: Dictionary = landscape.get("plan")
	_filler.call("_load_models", plan.filler)
	_item_index = _filler.get("_model_index")

	# 1. узлы прежнего запуска этого этапа
	for n: Node in _all_nodes(_root):
		if n.has_meta(META) and String(n.get_meta(META)) == _stage:
			_drop(n)
			_stats["убрано прежних узлов этапа"] += 1
	# 2. убрать по патчу
	var remove: Dictionary = patch.get("remove", {})
	for rule: Dictionary in remove.get("items", []):
		_remove_items(rule)
	for rule: Dictionary in remove.get("pieces", []):
		_remove_pieces(rule)
	for node_name: String in remove.get("nodes", []):
		var found: Node = _root.find_child(node_name, true, false)
		if found != null:
			_drop(found)
			_stats["убрано узлов"] += 1
		else:
			push_warning("prospekt_apply_patch: узла «%s» нет" % node_name)
	# 3. добавить
	var add: Dictionary = patch.get("add", {})
	for list_name: String in PLAN_LISTS:
		for e: Variant in add.get(list_name, []):
			_add_piece(list_name, e)
	for raw: Array in add.get("items", []):
		_add_item(raw)
	for b: Dictionary in add.get("buildings", []):
		_add_building(b)
	for l: Dictionary in add.get("ladders", []):
		_add_ladder(l)

	var packed: PackedScene = PackedScene.new()
	var err: int = packed.pack(_root)
	if err == OK:
		err = ResourceSaver.save(packed, SCENE)
	print("prospekt_apply_patch[%s]: %s; сохранение: %s" % [_stage, _stats, "ok" if err == OK else str(err)])
	_root.free()
	get_tree().quit(0 if err == OK else 1)


func _all_nodes(n: Node) -> Array[Node]:
	var out: Array[Node] = []
	for c: Node in n.get_children():
		out.append(c)
		out.append_array(_all_nodes(c))
	return out


func _drop(n: Node) -> void:
	n.get_parent().remove_child(n)
	n.free()


func _remove_items(rule: Dictionary) -> void:
	var kits: Array = rule.get("kits", [])
	var r: Array = rule.rect
	for n: Node in _filler.find_children("*", "PropSpot", true, false):
		var item: Array = (n as PropSpot).item
		if item.size() < 3 or not (String(item[0]) in kits):
			continue
		var x: float = float(item[1])
		var z: float = float(item[2])
		if x >= float(r[0]) and z >= float(r[1]) and x <= float(r[2]) and z <= float(r[3]):
			_drop(n)
			_stats["убрано вещей"] += 1


func _remove_pieces(rule: Dictionary) -> void:
	var list_name: String = String(rule.get("list", ""))
	var r: Array = rule.rect
	for n: Node in _root.find_children("*", "PlanPiece", true, false):
		var piece: PlanPiece = n as PlanPiece
		if piece.list != list_name:
			continue
		var d: Dictionary = piece.data
		if rule.has("mat") and String(d.get("mat", "")) != String(rule.mat):
			continue
		if rule.has("id") and String(d.get("id", "")) != String(rule.id):
			continue
		if rule.has("inside") or rule.has("ymin") or rule.has("keep"):
			if not _extended_match(d, rule):
				continue
			_drop(piece)
			_stats["убрано кусков"] += 1
			continue
		var c: Vector3 = _world_origin(piece)
		if c.x >= float(r[0]) and c.z >= float(r[1]) and c.x <= float(r[2]) and c.z <= float(r[3]):
			_drop(piece)
			_stats["убрано кусков"] += 1


## Расширенный отбор кусков (этап 5): "inside" [x0, z0, x1, z1] — габарит куска целиком внутри; "ymin"/"ymax" — высоты
## куска (стена: y0…y1, коробка: низ…верх) внутри диапазона; "keep" — список [x0, z0, x1, z1, y0, y1], которые оставить.
## Габарит — из данных куска (стена: rect; коробка: at ± size / 2; плита: rect); допуск 3 см.
func _extended_match(d: Dictionary, rule: Dictionary) -> bool:
	var box: Array = []
	var lo: float = 0.0
	var hi: float = 0.0
	if d.has("rect"):
		box = (d.rect as Array).duplicate()
		lo = float(d.get("y0", d.get("y_top", 0.0)))
		hi = float(d.get("y1", d.get("y_top", 0.0)))
	elif d.has("at") and d.has("size"):
		var a: Array = d.at
		var s: Array = d.size
		box = [float(a[0]) - float(s[0]) * 0.5, float(a[2]) - float(s[2]) * 0.5, float(a[0]) + float(s[0]) * 0.5, float(a[2]) + float(s[2]) * 0.5]
		lo = float(a[1]) - float(s[1]) * 0.5
		hi = float(a[1]) + float(s[1]) * 0.5
	else:
		return false
	var tol: float = 0.03
	if rule.has("inside"):
		var ins: Array = rule.inside
		if float(box[0]) < float(ins[0]) - tol or float(box[1]) < float(ins[1]) - tol or float(box[2]) > float(ins[2]) + tol or float(box[3]) > float(ins[3]) + tol:
			return false
	if rule.has("ymin") and lo < float(rule.ymin) - tol:
		return false
	if rule.has("ymax") and hi > float(rule.ymax) + tol:
		return false
	for k: Array in rule.get("keep", []):
		if absf(float(box[0]) - float(k[0])) < tol and absf(float(box[1]) - float(k[1])) < tol and absf(float(box[2]) - float(k[2])) < tol \
				and absf(float(box[3]) - float(k[3])) < tol and (k.size() < 6 or (absf(lo - float(k[4])) < tol and absf(hi - float(k[5])) < tol)):
			return false
	return true


## Положение узла в мире, пока сцена не в дереве (global_transform тут не работает): цепочка transform до корня.
func _world_origin(n: Node3D) -> Vector3:
	var xf: Transform3D = n.transform
	var p: Node = n.get_parent()
	while p != null and p != _root.get_parent():
		if p is Node3D:
			xf = (p as Node3D).transform * xf
		p = p.get_parent()
	return xf.origin


func _add_item(raw: Array) -> void:
	var item: Array = raw.duplicate()
	var kit: String = String(item[0])
	var m: Array = _filler.call("item_model", kit, float(item[1]), float(item[2]), String(item[8]) if item.size() > 8 else "")
	var folder_name: String = "Модели города" if String(m[0]) != "" else _folder_of(kit)
	var title: String = String((_item_index.get(String(m[0]), {}) as Dictionary).get("name", m[0])) if String(m[0]) != "" \
		else String(TITLES.get(kit, kit))
	var top: Node3D = _folder(_folder(_root.get_node("Filler") as Node3D, "Наполнение"), folder_name)
	var spot: PropSpot = PropSpot.new()
	_counts["i|" + title] = int(_counts.get("i|" + title, 0)) + 1
	spot.name = ("%s этап %s %d" % [title.left(40), _stage, int(_counts["i|" + title])]).validate_node_name()
	spot.item = item
	spot.order = _item_order
	_item_order += 1
	var xf: Transform3D = _filler.call("item_transform", item)
	spot.transform = xf
	spot.base = xf
	spot.set_meta(META, _stage)
	top.add_child(spot, true)
	spot.owner = _root
	_stats["добавлено вещей"] += 1


## Здание-объём (study_building.gd) в области сцены: {id, parent, at: [x, z], footprint: [w, d], floors, story_height, label, kind}.
## Как у соседних узлов-объёмов: группа mall_study_snap, meta height_m / enterable / loot_count. Прежний узел с тем же именем
## (от прошлого запуска этого этапа) уже убран по метке этапа.
func _add_building(b: Dictionary) -> void:
	var parent: Node = _root.get_node_or_null(NodePath(String(b.get("parent", "East"))))
	if parent == null:
		push_warning("prospekt_apply_patch: нет области «%s» для здания %s" % [b.get("parent"), b.get("id")])
		return
	var node: Node3D = Node3D.new()
	node.name = String(b.id)
	# "script": "flats" — секция flat_section.gd (башня, стилобат): open_floors / balconies / glass_bands — из "extra"
	var flats: bool = String(b.get("script", "build")) == "flats"
	node.set_script(load("res://src/blockout/flat_section.gd" if flats else "res://src/blockout/study_building.gd"))
	var fp: Array = b.footprint
	if flats:
		var extra: Dictionary = b.get("extra", {})
		node.set("open_floors", int(extra.get("open_floors", 0)))
		node.set("balconies", bool(extra.get("balconies", false)))
		node.set("glass_bands", bool(extra.get("glass_bands", false)))
	else:
		node.set("kind", String(b.get("kind", "mass")))
		if b.has("jib"):
			node.set("jib", bool(b.jib))
		if b.has("interior"):
			node.set("interior", String(b.interior))
			node.set("loot_theme", String(b.get("loot_theme", "")))
			node.set("loot_density", float(b.get("loot_density", 0.0)))
	node.set("footprint", Vector2(float(fp[0]), float(fp[1])))
	node.set("floors", int(b.get("floors", 1)))
	node.set("story_height", float(b.get("story_height", 3.0)))
	node.set("label", String(b.get("label", "")))
	var at: Array = b.at
	var lift: float = float(b.get("lift", 0.0))
	node.transform = Transform3D(Basis.IDENTITY, Vector3(float(at[0]), lift, float(at[1])))
	node.add_to_group("mall_study_snap", true)
	node.set_meta("height_m", int(b.get("floors", 1)) * float(b.get("story_height", 3.0)))
	node.set_meta("lift", lift)
	node.set_meta("enterable", String(b.get("interior", "")) != "")
	node.set_meta("loot_count", 0)
	node.set_meta(META, _stage)
	parent.add_child(node, true)
	node.owner = _root
	_stats["добавлено зданий"] += 1


## Вертикальная лестница (scenes/world/ladder.tscn) в области South: {name, at: [x, y, z], yaw, height}. Низ — на полу,
## лезут со стороны +Z лицом к −Z; yaw поворачивает вокруг Y. Узел — экземпляр сцены (внутренности в .tscn не пишутся).
func _add_ladder(l: Dictionary) -> void:
	var parent: Node3D = _folder(_root.get_node("South") as Node3D, "Лестницы-скобы")
	var node: Node3D = (load("res://scenes/world/ladder.tscn") as PackedScene).instantiate() as Node3D
	node.name = String(l.name)
	node.set("height", float(l.height))
	var at: Array = l.at
	node.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(float(l.get("yaw", 0.0)))), Vector3(float(at[0]), float(at[1]), float(at[2])))
	node.set_meta(META, _stage)
	parent.add_child(node, true)
	node.owner = _root
	_stats["добавлено лестниц"] = int(_stats.get("добавлено лестниц", 0)) + 1


func _folder_of(kit: String) -> String:
	for f: String in FOLDERS:
		if kit in (FOLDERS[f] as Array):
			return f
	return "Прочее"


func _add_piece(list_name: String, e: Variant) -> void:
	var landscape: Node3D = _root.get_node("Landscape") as Node3D
	var folder: Node3D = _folder(_folder(landscape, "Улицы"), String(LIST_FOLDERS[list_name]))
	var piece: PlanPiece = PlanPiece.new()
	piece.list = list_name
	piece.data = {"a": e} if e is Array else (e as Dictionary)
	piece.order = _piece_order
	_piece_order += 1
	var parent: Node3D = folder
	var title: String = ""
	var xf: Transform3D = Transform3D.IDENTITY
	match list_name:
		"surfaces", "slabs", "ground_holes", "walk_holes", "columns":
			var d: Dictionary = e if e is Dictionary else {"rect": e}
			var r: Array = d.rect
			var size := Vector3(absf(float(r[2]) - float(r[0])), 0.0, absf(float(r[3]) - float(r[1])))
			var y: float = 0.0
			if list_name == "surfaces":
				size.y = float(d.get("t", 0.08))
				y = float(d.get("y", 0.0)) + size.y * 0.5
				title = "%s %s" % [String(SURFACE_MATS.get(String(d.mat), d.mat)), String(d.id)]
			elif list_name == "slabs":
				size.y = float(d.t)
				y = float(d.y_top) - size.y * 0.5
				title = "%s %s" % [String(SLAB_MATS.get(String(d.mat), d.mat)), String(d.id)]
			elif list_name == "columns":
				size += Vector3(float(d.size), float(d.y1) - float(d.y0), float(d.size))
				y = (float(d.y0) + float(d.y1)) * 0.5
				title = "Ряд колонн"
			else:
				size.y = 0.12
				title = "Вырез"
			xf.origin = Vector3((float(r[0]) + float(r[2])) * 0.5, y, (float(r[1]) + float(r[3])) * 0.5)
			piece.pick_size = size
		"walls":
			var w: Dictionary = e
			var r2: Array = w.rect
			xf.origin = Vector3((float(r2[0]) + float(r2[2])) * 0.5, (float(w.y0) + float(w.y1)) * 0.5, (float(r2[1]) + float(r2[3])) * 0.5)
			piece.pick_size = Vector3(absf(float(r2[2]) - float(r2[0])), float(w.y1) - float(w.y0), absf(float(r2[3]) - float(r2[1])))
			parent = _folder(folder, String(MATS.get(String(w.get("mat", "wall")), w.get("mat", "wall"))))
			title = "Стена"
		"boxes":
			var bx: Dictionary = e
			var at: Array = bx.at
			var sz: Array = bx.size
			xf = Transform3D(Basis(Vector3.UP, deg_to_rad(float(bx.get("yaw", 0.0)))), Vector3(float(at[0]), float(at[1]), float(at[2])))
			piece.pick_size = Vector3(float(sz[0]), float(sz[1]), float(sz[2]))
			var kind: String = _box_kind(bx)
			parent = _folder(folder, kind)
			title = kind.trim_suffix("ы").trim_suffix("и") if kind in ["Бордюры", "Газоны"] else ("Полоса" if kind == "Разметка" else "Коробка")
		"stairs":
			var st: Dictionary = e
			var a := Vector3(float((st.from as Array)[0]), float((st.from as Array)[1]), float((st.from as Array)[2]))
			var b := Vector3(float((st.to as Array)[0]), float((st.to as Array)[1]), float((st.to as Array)[2]))
			xf = Transform3D(_along(Vector3(b.x - a.x, 0.0, b.z - a.z)), (a + b) * 0.5)
			piece.pick_size = Vector3(float(st.width), absf(b.y - a.y) + 0.2, Vector2(b.x - a.x, b.z - a.z).length())
			title = "Лестница"
		"ramps":
			var rp: Dictionary = e
			xf.origin = Vector3((float(rp.x0) + float(rp.x1)) * 0.5, (float(rp.y0) + float(rp.y1)) * 0.5, (float(rp.z0) + float(rp.z1)) * 0.5)
			piece.pick_size = Vector3(absf(float(rp.x1) - float(rp.x0)), absf(float(rp.y1) - float(rp.y0)) + 0.3, absf(float(rp.z1) - float(rp.z0)))
			piece.pick_center = Vector3(0.0, -0.15, 0.0)
			title = "Пандус"
		"beams":
			var bm: Array = e
			var p: Vector3 = Vector3(float((bm[0] as Array)[0]), float((bm[0] as Array)[1]), float((bm[0] as Array)[2]))
			var q: Vector3 = Vector3(float((bm[1] as Array)[0]), float((bm[1] as Array)[1]), float((bm[1] as Array)[2]))
			xf = Transform3D(_along(q - p), (p + q) * 0.5)
			var thick: float = maxf(float(bm[2]), float(bm[3]))
			piece.pick_size = Vector3(thick, thick, p.distance_to(q))
			parent = _folder(folder, String(MATS.get(String(bm[4]), bm[4])))
			title = "Балка"
		"lamps":
			var l: Array = e
			xf.origin = Vector3(float(l[0]), float(l[1]), float(l[2]))
			piece.pick_size = Vector3(0.4, 0.4, 0.4)
			title = "Фонарь"
		"signs":
			var s: Dictionary = e
			var at2: Array = s.at
			xf.origin = Vector3(float(at2[0]), float(at2[1]), float(at2[2]))
			var k: float = float(s.get("size", 56)) / 56.0
			piece.pick_size = Vector3(1.2, 1.2, 1.2) * k
			title = "Надпись «%s»" % String(s.text).left(32)
	piece.transform = xf
	piece.base = xf
	piece.set_meta(META, _stage)
	# пометки куска (закрытая дверь «под ключ»): запись плана может нести "meta": {имя: значение}
	if e is Dictionary and (e as Dictionary).has("meta"):
		for mk: String in ((e as Dictionary).meta as Dictionary):
			piece.set_meta(mk, ((e as Dictionary).meta as Dictionary)[mk])
	var key: String = "%d|%s" % [parent.get_instance_id(), title]
	_counts[key] = int(_counts.get(key, 0)) + 1
	piece.name = ("%s этап %s %d" % [title, _stage, int(_counts[key])]).validate_node_name()
	parent.add_child(piece, true)
	piece.owner = _root
	_stats["добавлено кусков"] += 1


## Основа с осью Z вдоль направления (лестница, балка): X — поперёк, Y — вверх.
static func _along(dir: Vector3) -> Basis:
	if dir.length() < 0.001:
		return Basis.IDENTITY
	var z: Vector3 = dir.normalized()
	var x: Vector3 = Vector3.UP.cross(z)
	if x.length() < 0.01:
		x = Vector3.RIGHT
	x = x.normalized()
	var y: Vector3 = z.cross(x).normalized()
	return Basis(x, y, z)


## Папка коробки: бордюры и разметка (как их различает prospekt_streets_to_nodes), остальное — по материалу.
static func _box_kind(bx: Dictionary) -> String:
	var sz: Array = bx.size
	var mat: String = String(bx.get("mat", "wall"))
	var narrow: float = minf(float(sz[0]), float(sz[2]))
	if mat == "stripe" and bool(bx.get("solid", true)) and float(sz[1]) > 0.12 and float(sz[1]) < 0.18 and narrow > 0.15 and narrow < 0.25:
		return "Бордюры"
	if mat == "stripe" and float(sz[1]) <= 0.03:
		return "Разметка"
	return String(MATS.get(mat, mat))


func _folder(parent: Node3D, title: String) -> Node3D:
	var existing: Node = parent.get_node_or_null(NodePath(title.validate_node_name()))
	if existing:
		return existing as Node3D
	var f: Node3D = Node3D.new()
	f.name = title.validate_node_name()
	parent.add_child(f, true)
	f.owner = _root
	return f
