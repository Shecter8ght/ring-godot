extends Node
## Настоящие сцены рейда и сохранения: потеря, пять входов, защищённый карман, вынос.
var fails: int = 0
var uid: String = ""
var gun: Dictionary = {}


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://engraving_raid_test.json", true)
	RaidEvents.enabled = false
	gun = ItemDb.make("wpn_ar_03", 1)
	gun["engraving"] = WeaponMark.make(gun, "Вернусь")
	gun["mods"] = {"optic_primary": {"id": "optic_rd_01", "dur": 63.0}}
	gun["dur"] = 61.0
	gun.mag.rounds = 7
	uid = String(gun.uid)
	Profile.equipment = {"primary": gun.duplicate(true), "backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = [ItemDb.make("bandage", 1)]
	var player: Player = await enter_raid()
	var carried: Dictionary = player.equipment_state().primary.duplicate(true)
	Raid.current.mark_dead(1)
	check("реальная потеря записана с окном пять рейдов", Profile.weapon_world.lost.has(uid) and int(Profile.weapon_world.lost[uid].remaining) == 5)
	check("сборка, износ, патроны и метка не изменились", without_grid(Profile.weapon_world.lost[uid].weapon) == without_grid(carried))
	await leave_raid()
	for number: int in range(1, 6):
		Profile._loaded = false
		Profile.ensure()
		Profile.equipment = {"secondary": ItemDb.make("wpn_hg_01", 1)}
		Profile.backpack = []
		player = await enter_raid()
		var end: int = Time.get_ticks_msec() + 30000
		while not Raid.current.recovery._attempted.has(Profile.profile_id) and Time.get_ticks_msec() < end:
			await get_tree().create_timer(.1).timeout
		check("в рейде %d выполнена одна попытка" % number, Raid.current.recovery._attempted.has(Profile.profile_id))
		var lost: Dictionary = Raid.current.recovery.journal.lost.get(uid, {})
		check("окно уменьшилось ровно на один: %d" % number, int(lost.get("remaining", 0)) == 5 - number)
		for enemy: Node in get_tree().get_nodes_in_group("marauders"):
			if String((enemy as Marauder).recovered_weapon.get("uid", "")) == uid:
				check("найденный враг получил исходную сборку", without_grid((enemy as Marauder).recovered_weapon) == without_grid(carried))
		Raid.current.recovery.finish()
		await leave_raid()
	check("после пятого рейда запись исчезла с диска", Profile.weapon_world.lost.is_empty() and Profile.weapon_world.pending.is_empty())
	# Случайные совместимые рамы: сдаётся одна, второй экземпляр остаётся обычной добычей.
	Profile.quests = {}
	Profile.flags = {}
	Quests.start("own_mark")
	Quests.finish_talk("own_mark", "trader", "intro")
	Profile.equipment = {"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	var cargo_frame: Dictionary = ItemDb.make("engraver_frame", 1)
	cargo_frame["fir"] = true
	Profile.backpack = [cargo_frame.duplicate(true), cargo_frame.duplicate(true)]
	player = await enter_raid()
	var cargo_exit: ExtractionPoint = ExtractionPoint.new()
	cargo_exit.display_name = "Вынос деталей"
	get_tree().current_scene.add_child(cargo_exit)
	Raid.current._extract(player, cargo_exit)
	for tick: int in range(12):
		await get_tree().process_frame
	check("случайная рама закрывает этап при выносе", String(Quests.objective("own_mark").get("id", "")) == "frame_report")
	check("передан только один узел, лишний остался", Profile.backpack.size() == 1 and String(Profile.backpack[0].id) == "engraver_frame")
	await leave_raid()
	# Перекладывание в карман до гибели спасает уже наблюдавшийся ствол.
	Profile.equipment = {"secondary": ItemDb.make("wpn_hg_01", 1)}
	Profile.backpack = []
	Profile.equipment.secondary["engraving"] = WeaponMark.make(Profile.equipment.secondary, "Карман")
	player = await enter_raid()
	var protected: Dictionary = player.inventory.equipment.secondary.duplicate(true)
	player.inventory.equipment = {}
	player.inventory.pocket = [protected]
	Raid.current.mark_dead(1)
	check("защищённый карман не создаёт потерю", not Profile.weapon_world.lost.has(String(protected.uid)))
	await leave_raid()
	# Реальная эвакуация закрывает запись и возвращает ту же вещь в профиль.
	Profile.equipment = {"primary": gun.duplicate(true)}
	Profile.backpack = []
	player = await enter_raid()
	var ext: ExtractionPoint = ExtractionPoint.new()
	ext.display_name = "Тестовый выход"
	get_tree().current_scene.add_child(ext)
	Raid.current._extract(player, ext)
	for frame: int in range(12):
		await get_tree().process_frame
	check("эвакуация сохраняет UUID и гравировку", Profile.equipment.has("primary") and String(Profile.equipment.primary.uid) == uid and Profile.equipment.primary.engraving == gun.engraving)
	check("вынесенное оружие больше не появляется у NPC", not Profile.weapon_world.pending.has(uid) and not Profile.weapon_world.lost.has(uid))
	await leave_raid()
	print("engraving_raid_test: failures=", fails)
	get_tree().quit(1 if fails else 0)


func enter_raid() -> Player:
	Profile.pending_raid = true
	Profile.save()
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	get_tree().change_scene_to_file("res://scenes/levels/mall_map.tscn")
	for frame: int in range(20):
		await get_tree().process_frame
	var player: Player = Raid.current.local_player()
	player.health.hp = 1e9
	# Прогон проверяет предметы, бой здесь не нужен.
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		enemy.set_physics_process(false)
	return player


func leave_raid() -> void:
	var scene: Node = get_tree().current_scene
	get_tree().current_scene = null
	scene.queue_free()
	for frame: int in range(5):
		await get_tree().process_frame


func without_grid(entry: Dictionary) -> Dictionary:
	var copy: Dictionary = entry.duplicate(true)
	for key: String in ["x", "y", "r", "rev", "_equip_generation"]:
		copy.erase(key)
	copy["_condition_shots"] = int(copy.get("_condition_shots", 0))
	for mod: Dictionary in (copy.get("mods", {}) as Dictionary).values():
		mod["light"] = bool(mod.get("light", false))
		mod["laser"] = bool(mod.get("laser", false))
	return copy


func check(label: String, result: bool) -> void:
	print("%s: %s" % ["PASS" if result else "FAIL", label])
	if not result:
		fails += 1
