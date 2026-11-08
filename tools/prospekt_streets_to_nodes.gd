extends Node
## Разовый перенос улиц «Проспекта» в узлы PlanPiece (решение владельца 2026-11-08 — карты правятся руками,
## docs/level_editing.md): покрытия, вырезы в земле, плиты, стены, коробки (бордюры, разметка, газоны, ограждения…),
## колонны паркинга, лестницы, пандусы, балки и трубы, фонари-свет, надписи — каждый свой узел под Landscape/Улицы,
## по папкам. Места лута остаются данными: настоящие ящики — узлы рейдовой сцены prospekt.tscn (Gameplay).
## План: эти списки очищаются, plan.lists_from_nodes — их имена (допишет tools/prospekt_streets_json.py).
##   tools/godot.cmd --headless res://tools/prospekt_streets_to_nodes.tscn
## Повторно не запускать: второй раз списков в плане уже нет.

const SCENE: String = "res://scenes/levels/prospekt_study.tscn"
## Список плана → папка.
const LISTS: Array = [
	["surfaces", "Покрытия"], ["ground_holes", "Вырезы в земле"], ["walk_holes", "Вырезы тротуаров"], ["slabs", "Плиты"],
	["walls", "Стены"], ["boxes", "Коробки"], ["columns", "Колонны"], ["stairs", "Лестницы"], ["ramps", "Пандусы"],
	["beams", "Балки и трубы"], ["lamps", "Фонари (свет)"], ["signs", "Надписи"]]
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

var _root: Node3D
var _counts: Dictionary = {}


func _ready() -> void:
	_root = (load(SCENE) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN) as Node3D
	var landscape: Node3D = _root.get_node("Landscape") as Node3D
	landscape.call("load_plan")
	var plan: Dictionary = landscape.get("plan")
	var top: Node3D = _folder(landscape, "Улицы")
	var total: int = 0
	for pair: Array in LISTS:
		var list_name: String = pair[0]
		var entries: Array = plan.get(list_name, [])
		var folder: Node3D = _folder(top, String(pair[1]))
		for i: int in range(entries.size()):
			var e: Variant = entries[i]
			var piece: PlanPiece = PlanPiece.new()
			piece.list = list_name
			piece.data = {"a": e} if e is Array else (e as Dictionary)
			piece.order = i
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
			_add(parent, piece, title)
			total += 1
	var packed: PackedScene = PackedScene.new()
	packed.pack(_root)
	ResourceSaver.save(packed, SCENE)
	print("prospekt_streets_to_nodes: кусков улиц %d" % total)
	_root.free()
	get_tree().quit(0)


## Основа с осью Z вдоль направления (лестница, балка): X — поперёк, Y — вверх (у отвесной — X по миру).
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


## Папка коробки: бордюры и разметка (светлые полосы — как их меняет сборка улиц), газоны, остальное — по материалу.
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


func _add(parent: Node3D, piece: PlanPiece, title: String) -> void:
	var key: String = "%d|%s" % [parent.get_instance_id(), title]
	_counts[key] = int(_counts.get(key, 0)) + 1
	piece.name = ("%s %04d" % [title, int(_counts[key])]).validate_node_name()
	parent.add_child(piece)
	piece.owner = _root
