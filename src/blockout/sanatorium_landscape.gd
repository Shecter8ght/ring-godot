@tool
extends Node3D
## «Санаторий»: постройки, участки, деревья — сохранённые узлы сцены, их правят руками в редакторе (решение владельца
## 2026-11-08, docs/design/editable_levels.md). Постройки — сцены scenes/levels/sanatorium/buildings, куски участка —
## …/site, беседки, машины, валуны, стройплощадки и деревья — прямо в сцене уровня; материалы — …/materials.
## В редакторе узлы видны сами. В игре этот узел склеивает коробки, марши, цилиндры и покрытия в один меш на материал
## с простыми коллизиями (BlockoutMerge — так было и у генератора), деревья собирает в россыпи (полные модели вблизи,
## карточки дальше), а проверкам отдаёт план: места и виды — из data/blockouts/sanatorium.json, помещения и обходы —
## из узлов BlockoutChecks внутри построек (по тому месту, где постройка стоит сейчас).

const META_PATH: String = "res://data/blockouts/sanatorium.json"
## Лес за забором (без коллизии) — данными, как раньше; деревья участка — узлы TreeSpot.
const VEG_PATH: String = "res://data/blockouts/sanatorium_vegetation.json"
const MATERIALS_DIR: String = "res://scenes/levels/sanatorium/materials"
## Снимок сцены в прежнем формате плана — для питоновских инструментов (замер обзора tools/sanatorium_ld_plan.py).
const SNAPSHOT_PATH: String = "res://data/blockouts/sanatorium_snapshot.json"
const SNAPSHOT_VEG_PATH: String = "res://data/blockouts/sanatorium_snapshot_vegetation.json"
## Цвета материалов блокаута: серые по назначению, чтобы читались постройки, настилы и покрытия
## (по ним переносчик tools/sanatorium_to_scenes.gd записал материалы папки; править — сами .tres).
const COLORS: Dictionary = {
	"facade": Color("b9b6ad"), "partition": Color("d3d0c6"), "struct": Color("9d9a92"), "glass": Color(0.62, 0.74, 0.8, 0.32),
	"slab": Color("8f8d87"), "floor": Color("a7a39a"), "roof": Color("4f5154"), "plinth": Color("85827a"),
	"stair": Color("a19c90"), "stone": Color("b0a993"), "rock": Color("6e6b65"), "planter": Color("6f7d5a"), "rail": Color("4a4c4f"),
	"parapet": Color("a59f8c"), "wood": Color("7a5e43"), "wood_dark": Color("5b4a3c"), "white": Color("e2dfd6"),
	"deck": Color("8d7356"), "logs": Color("6e5a42"), "trail": Color("7b6a4f"), "trail_strip": Color("7b6a4f"),
	"asphalt": Color("4c4f52"), "paving": Color("a39d8e"), "stripe": Color("d8d6cc"), "kiosk": Color("c3b89a"),
	"tile": Color("8fb1b8"), "metal": Color("5d6366"), "fence": Color("5e6560"), "fence_green": Color("4f7354"),
	"court": Color("6f7f74"), "brick": Color("8c5a48"), "eurocube": Color("d6d6d0"), "boat": Color("d8dad6"),
	"car_a": Color("5f6670"), "car_b": Color("7d3e36"), "car_c": Color("2f3d4c"), "car_d": Color("a7a8a2"),
	"barrier_red": Color("b8362c"), "play": Color("d6c9a7"), "play_red": Color("bf5a3c"), "rope": Color("7a6a4e"),
	"rubber_red": Color("8e4a40"), "rubber_green": Color("5c7a52"), "rubber_blue": Color("4e6787"), "rubber_dark": Color("2f3133"),
	"umbrella": Color("d08a4e"), "umbrella_pink": Color("d6768f"), "dam": Color("9c9a94"), "dam_dark": Color("6d6c68"),
}
## Покрытия, по которым ходят (владелец 2026-11-08: «сначала то, по чему будем ходить»), — покрытия «Проспекта»,
## выбранные владельцем на стенде tools/paving_probe (StreetPaving): дорога А — чёткий асфальт с трещинами, тротуар А —
## серый кирпичик ложком; корт и детская площадка — их же. Грунтовые тропы — материалом земли (тот же грунт тропы,
## что в масках рельефа: лента и земля под ней — одно). Без текстур — серые цвета блокаута. В редакторе эти покрытия
## серые (материалы папки), в игре — эти.
const PAVING: Dictionary = {"asphalt": "road_a", "paving": "walk_a", "court": "court", "rubber_red": "rubber"}
const GROUND_KEYS: Array[String] = ["trail", "trail_strip"]
## Асфальт и мощение — по рельефу, тень от них не нужна.
const NO_SHADOW: Array[String] = ["asphalt", "paving", "stripe", "trail_strip", "court", "rubber_red", "rubber_green", "rubber_blue"]
## Сырость покрытий — от погоды рейда, раз в столько секунд (как у «Проспекта»).
const WEATHER_SYNC_SEC: float = 0.25
## Лес за забором: порода → модель зоны 1 (россыпь без стволов).
const BG_SPECIES: Dictionary = {"spruce_a": "spruce_forest_a", "spruce_b": "spruce_forest_b", "pine": "pine_forest"}

## Подписи: на какой дальности ещё видны (м) — для переносчика и новых подписей.
const LABEL_RANGE: Dictionary = {"room": 22.0, "unit": 70.0, "object": 90.0, "building": 650.0, "far": 6000.0}
const LABEL_PIXEL: Dictionary = {"room": 0.006, "unit": 0.012, "object": 0.01, "building": 0.03, "far": 0.4}
const LABEL_BEGIN: Dictionary = {"room": 1.2, "unit": 6.0, "object": 3.0, "building": 45.0, "far": 400.0}

@export var build_trees: bool = true

var plan: Dictionary = {}
## Склейка как план генератора (коробки, марши, цилиндры, треугольники, деревья — в мире), см. write_snapshot.
var snapshot: Dictionary = {}
var generated: Node3D
var built_ms: int = 0
var _paving_weather_t: float = 0.0


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	rebuild()


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	_paving_weather_t += delta
	if _paving_weather_t >= WEATHER_SYNC_SEC:
		StreetPaving.sync_weather(_paving_weather_t)
		_paving_weather_t = 0.0


func load_plan() -> void:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(META_PATH))
	if not parsed is Dictionary:
		push_error("Не прочитан план «Санатория»: " + META_PATH)
		return
	plan = parsed as Dictionary


func rebuild() -> void:
	var started: int = Time.get_ticks_msec()
	load_plan()
	if plan.is_empty():
		return
	if is_instance_valid(generated):
		generated.free()
	generated = Node3D.new()
	generated.name = "_Generated"
	add_child(generated)
	var merge: BlockoutMerge = BlockoutMerge.new(generated, _palette(), MATERIALS_DIR)
	merge.record = true
	merge.collect(self)
	merge.finish()
	for child: Node in generated.get_children():
		if child is MeshInstance3D and String(child.name).trim_prefix("Mesh_") in NO_SHADOW:
			(child as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var rooms: Array = []
	var routes: Array = []
	for c: Node in merge.checks:
		rooms.append_array((c as BlockoutChecks).world_rooms())
		routes.append_array((c as BlockoutChecks).world_routes())
	plan.rooms = rooms
	plan.routes = routes
	plan.water = _water_bodies(merge.water)
	snapshot = merge.snapshot
	snapshot.buildings = plan.get("buildings", [])
	var trees: int = 0
	if build_trees:
		trees = _trees(merge.trees)
	for t: Node in merge.trees:
		t.free()
	merge.free_sources()
	var counts: Dictionary = merge.counts
	plan.stats = {"boxes": int(counts.boxes), "stairs": int(counts.stairs), "cyls": int(counts.cyls), "csg": int(counts.csg),
		"tris": int(counts.tris), "rooms": rooms.size(), "routes": routes.size(), "trees": trees}
	built_ms = Time.get_ticks_msec() - started


## Палитра: ключ → материал в игре (материал папки; покрытия улиц и тропы — свои).
func _palette() -> Dictionary:
	var result: Dictionary = {}
	var ground: Material = _ground_material()
	for key: Variant in plan.get("mats", COLORS.keys()):
		var k: String = String(key)
		if PAVING.has(k) and StreetPaving.has_maps(String(StreetPaving.SURFACES[PAVING[k]].set)):
			result[k] = StreetPaving.material(String(PAVING[k]), false)
			continue
		if ground != null and k in GROUND_KEYS:
			result[k] = ground
			continue
		var path: String = "%s/%s.tres" % [MATERIALS_DIR, k]
		if ResourceLoader.exists(path):
			result[k] = load(path)
		else:
			var m: StandardMaterial3D = StandardMaterial3D.new()
			m.albedo_color = COLORS.get(k, Color("a0a093"))
			m.roughness = 0.9
			result[k] = m
	return result


## Материал земли соседнего узла Terrain (SanatoriumGround): строится раньше ландшафта (порядок узлов сцены).
func _ground_material() -> Material:
	var terrain: Node = get_parent().get_node_or_null("Terrain") if get_parent() else null
	if terrain == null:
		return null
	var m: Variant = terrain.get("_material")
	return m as Material if m is Material else null


## Вода для проверок и ботов (контур и уровень — в мире, по нынешнему положению узла воды).
func _water_bodies(nodes: Array[Node]) -> Array:
	var out: Array = []
	for n: Node in nodes:
		var mi: MeshInstance3D = n as MeshInstance3D
		var body: Dictionary = (mi.get_meta("water_body") as Dictionary).duplicate(true)
		var xf: Transform3D = mi.global_transform
		var level: float = float(body.level)
		body.level = (xf * Vector3(0.0, level, 0.0)).y
		if body.has("poly"):
			var poly: Array = []
			for q: Array in body.poly:
				var w: Vector3 = xf * Vector3(float(q[0]), level, float(q[1]))
				poly.append([w.x, w.z])
			body.poly = poly
		if body.has("circle"):
			var c: Array = body.circle
			var w2: Vector3 = xf * Vector3(float(c[0]), level, float(c[1]))
			body.circle = [w2.x, w2.z, float(c[2]) * BlockoutMerge.split(xf.basis)[1].x]
		out.append(body)
	return out


## Деревья: участок — из узлов TreeSpot (порода, место, поворот, масштаб), лес за забором — данными. Россыпи
## DistrictScatter: полные модели вблизи, карточки дальше; у деревьев участка — коллизия ствола. Возвращает число деревьев.
func _trees(spots: Array[Node]) -> int:
	var root: Node3D = Node3D.new()
	root.name = "Forest"
	generated.add_child(root)
	var by: Dictionary = {}
	for n: Node in spots:
		var spot: TreeSpot = n as TreeSpot
		if not by.has(spot.species):
			by[spot.species] = []
		(by[spot.species] as Array).append(spot.scatter_point())
	var total: int = spots.size()
	snapshot.trees = by.duplicate(true)
	for key: String in by:
		var spec: Array = TreeSpot.SPECIES[key]
		root.add_child(_scatter(key, String(spec[0]), String(spec[1]), float(spec[2]), by[key]))
	if FileAccess.file_exists(VEG_PATH):
		var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(VEG_PATH)) as Dictionary
		for key: String in data:
			var list: Array = data[key]
			if list.is_empty() or not key.ends_with("_bg"):
				continue
			var bg: String = "res://assets/zone01/models/%s" % String(BG_SPECIES[key.trim_suffix("_bg")])
			var s: DistrictScatter = _scatter(key, bg + ".glb", bg + "_far.glb", 0.0, [])
			s.data_path = VEG_PATH
			s.key = key
			root.add_child(s)
			total += list.size()
			(snapshot.trees as Dictionary)[key] = list
	return total


## Записать снимок (data/blockouts/sanatorium_snapshot*.json): объёмы — как в прежнем плане, деревья — как в прежнем
## файле деревьев. Пишет tools/sanatorium_study.tscn -- snapshot.
func write_snapshot() -> void:
	var geo: Dictionary = snapshot.duplicate()
	var trees: Variant = geo.get("trees", {})
	geo.erase("trees")
	for pair: Array in [[SNAPSHOT_PATH, geo], [SNAPSHOT_VEG_PATH, trees]]:
		var f: FileAccess = FileAccess.open(String(pair[0]), FileAccess.WRITE)
		f.store_string(JSON.stringify(pair[1], "", false))
		f.close()


func _scatter(key: String, model: String, far_model: String, trunk: float, points: Array) -> DistrictScatter:
	var scatter: DistrictScatter = DistrictScatter.new()
	scatter.name = key
	scatter.points_override = points
	scatter.model = model
	scatter.far_model = far_model
	scatter.near_distance = 220.0
	scatter.view_distance = 2400.0
	scatter.cell = 64.0
	scatter.far_cell = 256.0
	scatter.trunk_radius = trunk
	return scatter
