extends Node
## Разовый перенос наполнения «Проспекта» в узлы PropSpot (решение владельца 2026-11-08 — карты правятся руками,
## docs/level_editing.md): каждая машина, киоск, забор, бумажка, модель города — свой узел под Filler/Наполнение,
## по папкам. Узел стоит так, как вещь ставит россыпь; его запись — прежняя (машине «вперемешку» модель закреплена
## по прежнему месту, чтобы при сдвиге она не сменилась). План: filler.items очищается, filler.from_nodes = true
## (это допишет tools/prospekt_items_json.py — формат плана как у генератора).
##   tools/godot.cmd --headless res://tools/prospekt_items_to_nodes.tscn
## Повторно не запускать: второй раз вещей в плане уже нет.

const SCENE: String = "res://scenes/levels/prospekt_study.tscn"
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
	"car": "Машина", "car_open": "Машина открытая", "car_wreck": "Машина разбитая", "suv_open": "Внедорожник открытый",
	"truck": "Грузовик", "van": "Фургон", "bus_city": "Автобус", "district_fence": "Забор", "rail_fence": "Ограждение",
	"fence": "Забор", "bar_fence": "Решётка", "chainlink": "Сетка", "po2": "Плита ПО-2", "paper": "Бумага",
	"paper_ball": "Комок бумаги", "glass_shards": "Осколки", "bags": "Мешки", "can": "Банка", "bottle": "Бутылка",
	"trash_pile": "Куча мусора", "kiosk": "Киоск", "bench": "Скамейка", "stall": "Прилавок", "tree_birch": "Берёза",
	"tree_round": "Дерево", "bush_big": "Куст", "pole_conc": "Столб", "pole_trolley": "Столб контактной сети",
	"garage": "Гараж", "container20": "Контейнер 20", "container40": "Контейнер 40", "track_3m": "Рельсы 3 м",
	"ac_unit": "Кондиционер", "pallets": "Поддоны", "barrel": "Бочка", "cone": "Конус", "ornate_lamp": "Фонарь",
	"lamp": "Фонарь", "bus_stop": "Остановка", "cafe_table": "Столик", "sandbags": "Мешки с песком",
}


func _ready() -> void:
	var root: Node3D = (load(SCENE) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN) as Node3D
	var landscape: Node = root.get_node("Landscape")
	landscape.call("load_plan")
	var plan: Dictionary = landscape.get("plan")
	var filler_data: Dictionary = plan.filler
	var filler: Node = root.get_node("Filler")
	filler.set("landscape", landscape)
	filler.call("_load_models", filler_data)
	var index: Dictionary = filler.get("_model_index")
	var kit_models: Dictionary = filler_data.get("kit_models", {})
	var top: Node3D = Node3D.new()
	top.name = "Наполнение"
	filler.add_child(top, true)
	top.owner = root
	var folders: Dictionary = {}
	var counts: Dictionary = {}
	var pinned: int = 0
	var order: int = 0
	for raw: Array in filler_data.items:
		var item: Array = raw.duplicate()
		order += 1
		var kit: String = String(item[0])
		var m: Array = filler.call("item_model", kit, float(item[1]), float(item[2]))
		# машина, дерево, контейнер «вперемешку»: модель — по месту; закрепить прежнюю девятым полем, чтобы при сдвиге
		# узла она не сменилась
		var base_model: String = String((kit_models[kit] as Dictionary).model) if kit_models.has(kit) else kit.substr(2)
		if String(m[0]) != "" and String(m[0]) != base_model:
			while item.size() < 8:
				item.append([1.0, 0.0, -1, 0.0][item.size() - 4] if item.size() >= 4 else 0.0)
			item.append(String(m[0]))
			pinned += 1
		var folder_name: String = "Модели города" if String(m[0]) != "" else _folder_of(kit)
		var title: String = String((index.get(String(m[0]), {}) as Dictionary).get("name", m[0])) if String(m[0]) != "" \
			else String(TITLES.get(kit, kit))
		if not folders.has(folder_name):
			var f: Node3D = Node3D.new()
			f.name = folder_name.validate_node_name()
			top.add_child(f, true)
			f.owner = root
			folders[folder_name] = f
		counts[title] = int(counts.get(title, 0)) + 1
		var spot: PropSpot = PropSpot.new()
		spot.name = ("%s %04d" % [title.left(48), int(counts[title])]).validate_node_name()
		spot.item = item
		spot.order = order
		var xf: Transform3D = filler.call("item_transform", item)
		spot.transform = xf
		spot.base = xf
		(folders[folder_name] as Node3D).add_child(spot)
		spot.owner = root
	var packed: PackedScene = PackedScene.new()
	packed.pack(root)
	ResourceSaver.save(packed, SCENE)
	print("prospekt_items_to_nodes: вещей %d, папок %d, моделей вперемешку закреплено %d" % [filler_data.items.size(),
		folders.size(), pinned])
	root.free()
	get_tree().quit(0)


func _folder_of(kit: String) -> String:
	for f: String in FOLDERS:
		if kit in (FOLDERS[f] as Array):
			return f
	return "Прочее"
