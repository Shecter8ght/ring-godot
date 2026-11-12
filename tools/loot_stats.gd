extends Node
## Замер лута по настоящему ItemDb.roll (docs/design/loot_matrix_v2.md §5.1): по каждой таблице — среднее, медиана, p90
## стоимости и доля пустых бросков; по «Проспекту» — ожидаемая стоимость всех мест Loot_N (схроны × STASH_SHARE),
## распределение по категориям и ожидаемое число за рейд ключевых вещей.
##   LOOT_STATS_N=3000 LOOT_STATS_OUT=<файл.json> tools/godot.cmd --headless res://tools/loot_stats.tscn
## Места карты читаются из текста сцены (узлы Loot_N) — рейд не запускается, выходит быстро.

const LEVEL := "res://scenes/levels/prospekt.tscn"
## Схроны: в рейде открыто 4 из 12 (Raid.roll_stashes, середина вилки 3–5).
const STASH_SHARE := 4.0 / 12.0
const KEY_IDS: Array[String] = ["toolset", "bandage", "medkit", "painkillers", "grenade", "cash", "documents", "battery",
	"wires", "phone", "cigarettes", "lighter", "laptop", "server_drive", "diamond_ring", "laser_head", "engraver_frame",
	"engraver_controller", "printer_body", "printer_head", "printer_board", "sticker_film", "ink_set", "stencil_kit",
	"spray_paint", "mag_loader", "pouch_pistol", "pouch_rifle", "nvg"]


func _ready() -> void:
	var n: int = int(OS.get_environment("LOOT_STATS_N")) if OS.get_environment("LOOT_STATS_N") != "" else 3000
	var out_path: String = OS.get_environment("LOOT_STATS_OUT")
	var tables: Array = _table_ids()
	var per_table: Dictionary = {}
	print("таблица | среднее | медиана | p90 | пустых %")
	for t: String in tables:
		var st: Dictionary = _measure(t, n)
		per_table[t] = st
		print("%s | %d | %d | %d | %.1f" % [t, int(st.mean), int(st.median), int(st.p90), float(st.empty) * 100.0])
	var places: Array = _places()
	var total: float = 0.0
	var cats: Dictionary = {}
	var keys: Dictionary = {}
	var by_table: Dictionary = {}
	for p: Dictionary in places:
		var t: String = String(p.table)
		if not per_table.has(t):
			per_table[t] = _measure(t, n)
		var st: Dictionary = per_table[t]
		var w: float = STASH_SHARE if bool(p.stash) else 1.0
		by_table[t] = float(by_table.get(t, 0.0)) + w
		total += float(st.mean) * w
		for c: String in st.cats:
			cats[c] = float(cats.get(c, 0.0)) + float(st.cats[c]) * w
		for k: String in st.keys:
			keys[k] = float(keys.get(k, 0.0)) + float(st.keys[k]) * w
	print("")
	print("мест Loot_N: %d, ожидаемая стоимость карты: %d" % [places.size(), int(total)])
	var cat_names: Array = cats.keys()
	cat_names.sort_custom(func(a: String, b: String) -> bool: return float(cats[a]) > float(cats[b]))
	for c: String in cat_names:
		print("  категория %s: %d (%.1f %%)" % [c, int(cats[c]), float(cats[c]) / total * 100.0])
	var key_names: Array = keys.keys()
	key_names.sort()
	for k: String in key_names:
		print("  за рейд %s: %.2f" % [k, float(keys[k])])
	var tables_used: Array = by_table.keys()
	tables_used.sort()
	print("  мест по таблицам: " + ", ".join(tables_used.map(func(t: String) -> String: return "%s %s" % [t, snappedf(float(by_table[t]), 0.01)])))
	if out_path != "":
		var f := FileAccess.open(out_path, FileAccess.WRITE)
		var slim: Dictionary = {}
		for t: String in per_table:
			var st: Dictionary = per_table[t]
			slim[t] = {"mean": st.mean, "median": st.median, "p90": st.p90, "empty": st.empty}
		f.store_string(JSON.stringify({"n": n, "tables": slim, "map": {"places": places.size(), "total": total, "cats": cats,
			"keys": keys, "by_table": by_table}}, "\t"))
		f.close()
	get_tree().quit(0)


## Все таблицы: data/loot.json и гражданские Balance.CIVILIAN_LOOT.
func _table_ids() -> Array:
	var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/loot.json")) as Dictionary
	var ids: Array = (d.tables as Dictionary).keys()
	for t: String in Balance.CIVILIAN_LOOT:
		if not ids.has(t):
			ids.append(t)
	ids.sort()
	return ids


func _measure(table: String, n: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = 424242
	var vals: Array[float] = []
	var empty: int = 0
	var cats: Dictionary = {}
	var keys: Dictionary = {}
	for i: int in range(n):
		var list: Array = ItemDb.roll(table, rng)
		if list.is_empty():
			empty += 1
		var v: float = 0.0
		for e: Dictionary in list:
			var ev: float = float(ItemDb.entry_value(e))
			v += ev
			var id: String = String(e.id)
			var cat: String = String(ItemDb.item(id).get("cat", "misc"))
			cats[cat] = float(cats.get(cat, 0.0)) + ev / float(n)
			var cnt: float = float(e.get("n", 1))
			if id in KEY_IDS:
				keys[id] = float(keys.get(id, 0.0)) + cnt / float(n)
			if cat == "ammo":
				keys["ammo_pcs"] = float(keys.get("ammo_pcs", 0.0)) + cnt / float(n)
			elif cat == "key":
				keys["keys"] = float(keys.get("keys", 0.0)) + cnt / float(n)
		vals.append(v)
	vals.sort()
	var sum: float = 0.0
	for v: float in vals:
		sum += v
	return {"mean": sum / float(n), "median": vals[n / 2], "p90": vals[int(float(n) * 0.9)], "empty": float(empty) / float(n),
		"cats": cats, "keys": keys}


## Места лута из текста сцены: [{name, table, stash}].
func _places() -> Array:
	var text: String = FileAccess.get_file_as_string(LEVEL)
	var out: Array = []
	# LOOT_STATS_MAP — файл «узел → таблица» (data/blockouts/prospekt_loot_kinds.json): расчёт до внесения в сцену
	var over: Dictionary = {}
	if OS.get_environment("LOOT_STATS_MAP") != "":
		over = JSON.parse_string(FileAccess.get_file_as_string(OS.get_environment("LOOT_STATS_MAP"))) as Dictionary
	var re := RegEx.new()
	re.compile("\\[node name=\"(Loot_\\d+)\" parent=\"Gameplay/Loot\" instance=ExtResource\\(\"\\d+\"\\)\\]\\n((?:(?!\\[node).*\\n?)*)")
	for m: RegExMatch in re.search_all(text):
		var body: String = m.get_string(2)
		var tm := RegEx.create_from_string("table = \"(\\w+)\"").search(body)
		var table: String = tm.get_string(1) if tm != null else "storage"
		if over.has(m.get_string(1)):
			table = String((over[m.get_string(1)] as Dictionary).table)
		out.append({"name": m.get_string(1), "table": table, "stash": body.contains("stash = true")})
	return out
