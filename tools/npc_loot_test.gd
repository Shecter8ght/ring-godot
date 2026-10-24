extends Node
## Лут с тела по видимому (схема npc_gear_by_type.md, правило «что видно — то и есть»): у мародёра на теле
## броня с подсумками и магазинами, шлем, рюкзак; убит — ящик с тем же; забрали броню из ящика — на теле
## её (и подсумков) нет; забрали всё — тело голое. Магазины бота — в подсумках на броне в ящике.

var _fails: int = 0
var _level: Node


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	_level = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(_level)
	get_tree().current_scene = _level
	while _level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for i in range(20):
		await get_tree().process_frame
	var bots: Array = _level.get_node("Marauders").get_children()
	for m in bots:
		(m as Marauder).process_mode = Node.PROCESS_MODE_DISABLED
	# бот, у которого есть броня с подсумками и шлем, — его и обыщем
	var target: Marauder = null
	for m: Marauder in bots:
		if m.equipment.has("armor") and not (m.equipment.armor.get("pouches", []) as Array).is_empty() and m.equipment.has("helmet"):
			target = m
			break
	if target == null:
		for m: Marauder in bots:
			if m.equipment.has("armor") and not (m.equipment.armor.get("pouches", []) as Array).is_empty():
				target = m
				break
	_check("есть бот с бронёй и подсумками", target != null, "ботов %d" % bots.size())
	if target == null:
		_finish()
		return
	target.process_mode = Node.PROCESS_MODE_INHERIT
	var worn0: PackedStringArray = (target.get_node("NpcOutfit") as NpcOutfit).worn_names()
	var pouches0: int = ItemDb.pouch_list(target.equipment.armor).size()
	var mags0: int = 0
	for it: Dictionary in target.spare:
		if it.has("rounds"):
			mags0 += 1
	_check("на теле броня, подсумки (%d) и шлем" % pouches0, worn0.size() >= 2 and pouches0 > 0, ", ".join(worn0))
	# убить
	target._last_hit_from = target.global_position + Vector3(2.0, 1.0, 0.0)
	target._health.take_damage(10000.0, target.global_position + Vector3(2.0, 1.5, 0.0), "head")
	for i in range(30):
		await get_tree().process_frame
	# тяжёлое ранение вместо смерти — добить
	for k in range(5):
		if target.state != Marauder.State.DOWNED:
			break
		target._health.take_damage(10000.0, target.global_position + Vector3(2.0, 1.5, 0.0), "head")
		for i in range(30):
			await get_tree().process_frame
	_check("убит, ящик с тела есть", target.state == Marauder.State.DEAD and is_instance_valid(target._crate), str(target.state))
	if not is_instance_valid(target._crate):
		_finish()
		return
	var crate: LootContainer = target._crate
	var armor_in_crate: Dictionary = {}
	for e: Dictionary in crate.items:
		if not WeaponDb.vest(String(e.get("id", ""))).is_empty():
			armor_in_crate = e
	var in_pouches: int = (armor_in_crate.get("mags", []) as Array).size()
	_check("в ящике броня с подсумками и магазинами в них (%d из %d)" % [in_pouches, mags0], not armor_in_crate.is_empty() and ItemDb.pouch_list(armor_in_crate).size() == pouches0 and in_pouches == mini(mags0, pouches0),
		"подсумков %d, магазинов в них %d" % [ItemDb.pouch_list(armor_in_crate).size(), in_pouches])
	await get_tree().create_timer(0.8).timeout
	var worn_dead: PackedStringArray = (target.get_node("NpcOutfit") as NpcOutfit).worn_names()
	_check("мёртвый — одет как при жизни", worn_dead.size() == worn0.size(), "%d / %d" % [worn_dead.size(), worn0.size()])
	# забрали броню из ящика
	var rest: Array = []
	for e: Dictionary in crate.items:
		if WeaponDb.vest(String(e.get("id", ""))).is_empty():
			rest.append(e)
	crate.items = rest
	await get_tree().create_timer(0.8).timeout
	var worn_after: PackedStringArray = (target.get_node("NpcOutfit") as NpcOutfit).worn_names()
	var armor_left := false
	var pouch_left := false
	for n: String in worn_after:
		if n.begins_with("G_Armor"):
			armor_left = true
		if n.begins_with("Place_"):
			pouch_left = true
	_check("броню забрали — на теле нет ни брони, ни подсумков; шлем остался", not armor_left and not pouch_left and worn_after.size() < worn_dead.size(), ", ".join(worn_after))
	# забрали всё: ящик исчез
	crate.queue_free()
	await get_tree().create_timer(0.8).timeout
	_check("ящик унесли — тело голое", (target.get_node("NpcOutfit") as NpcOutfit).worn_names().is_empty(), ", ".join((target.get_node("NpcOutfit") as NpcOutfit).worn_names()))
	_finish()


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s%s" % ["ok" if ok else "FAIL", what, "" if detail == "" else " — " + detail])


func _finish() -> void:
	print("npc_loot_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)
