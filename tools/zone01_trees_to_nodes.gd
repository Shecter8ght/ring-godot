extends Node
## Разовый перенос деревьев «Пригорода» в узлы TreeSpot (решение владельца 2026-11-08 — карты правятся руками,
## docs/level_editing.md): каждое дерево — свой узел, его двигают, поворачивают, копируют, прячут глазком.
##   tools/godot.cmd --headless res://tools/zone01_trees_to_nodes.tscn
## Мир зоны (zone01_world.tscn, точки — data/zone01_vegetation.json, мировые) и двор хрущёвок (zone01_yard05.tscn,
## data/zone01_yard_scatter.json, точки в координатах двора): у россыпей деревьев — from_nodes, их точки в JSON
## очищаются (кусты, папоротник, пни, коряги, камни остаются данными). Земле мира — группа "blockout_terrain"
## (кисть земли и деревья, встающие на землю). Повторный запуск не нужен: второй раз деревьев в JSON уже нет.

const TITLES: Dictionary = {
	"tree_poplar_0": "Тополь 1", "tree_poplar_1": "Тополь 2", "tree_poplar_2": "Тополь 3",
	"tree_maple_0": "Клён 1", "tree_maple_1": "Клён 2", "tree_maple_2": "Клён 3",
	"spruce_forest_a": "Ель лесная 1", "spruce_forest_b": "Ель лесная 2", "spruce_open": "Ель на просторе",
	"spruce_young_a": "Ель молодая 1", "spruce_young_b": "Ель молодая 2",
	"birch_a": "Берёза 1", "birch_b": "Берёза 2", "birch_c": "Берёза 3", "birch_bare": "Берёза голая", "birch_young": "Берёза молодая",
	"pine_young": "Сосна молодая", "pine_slim_a": "Сосна стройная 1", "pine_slim_b": "Сосна стройная 2",
	"pine_forest": "Сосна лесная", "pine_thick": "Сосна толстая", "pine_old": "Сосна старая", "pine_twin": "Сосна двойная",
	"pine_yard": "Сосна во дворе",
}
const JOBS: Array = [
	["res://scenes/levels/zone01/zone01_world.tscn", "res://data/zone01_vegetation.json", true],
	["res://scenes/levels/zone01/zone01_yard05.tscn", "res://data/zone01_yard_scatter.json", false],
]


func _ready() -> void:
	var total: int = 0
	for job: Array in JOBS:
		total += _convert(String(job[0]), String(job[1]), bool(job[2]))
	print("zone01_trees_to_nodes: деревьев в узлы %d" % total)
	get_tree().quit(0)


func _convert(scene_path: String, data_path: String, world: bool) -> int:
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(data_path)) as Dictionary
	var root: Node3D = (load(scene_path) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN) as Node3D
	if world:
		root.get_node("Terrain").add_to_group("blockout_terrain", true)
	var veg: Node3D = root.get_node("Vegetation") as Node3D
	var folder: Node3D = Node3D.new()
	folder.name = "Деревья"
	veg.add_child(folder, true)
	folder.owner = root
	var count: int = 0
	for child: Node in veg.get_children():
		if not child is DistrictScatter:
			continue
		var scatter: DistrictScatter = child as DistrictScatter
		if not TITLES.has(scatter.key) or scatter.data_path != data_path:
			continue
		var points: Array = data.get(scatter.key, [])
		scatter.from_nodes = true
		if points.is_empty():
			continue
		var sub: Node3D = Node3D.new()
		sub.name = String(TITLES[scatter.key])
		folder.add_child(sub, true)
		sub.owner = root
		var i: int = 0
		for p: Array in points:
			i += 1
			var t: TreeSpot = TreeSpot.new()
			t.name = "%s %04d" % [String(TITLES[scatter.key]), i]
			t.species = scatter.key
			t.position = Vector3(float(p[0]), float(p[1]), float(p[2]))
			t.rotation.y = deg_to_rad(float(p[3]))
			t.scale = Vector3.ONE * float(p[4])
			sub.add_child(t)
			t.owner = root
			count += 1
		data[scatter.key] = []
	var packed: PackedScene = PackedScene.new()
	packed.pack(root)
	ResourceSaver.save(packed, scene_path)
	root.free()
	var f: FileAccess = FileAccess.open(data_path, FileAccess.WRITE)
	f.store_string(JSON.stringify(data, "", false) + "\n")
	f.close()
	print("  %s: деревьев %d" % [scene_path, count])
	return count
