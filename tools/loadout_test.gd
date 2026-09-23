extends Node
## Сквозной прогон «убежище → рейд → эвакуация → убежище» на тестовом профиле (настоящий не
## трогаем): надеть снаряжение, собрать рюкзак, купить/продать; в рейде — оружие из слотов,
## магазины из рюкзака, перезарядка тратит патроны, броня снимает урон; эвакуация возвращает всё
## в профиль; Enter — назад в убежище.
## godot --path . res://tools/loadout_test.tscn

const TEST_PROFILE := "user://profile_test.json"

var _fails: int = 0


func _ready() -> void:
	await get_tree().process_frame
	# смена сцены не должна удалить сам тест: отвязываем его от «текущей сцены»
	get_tree().current_scene = null
	Profile.use_file(TEST_PROFILE, true)

	# --- убежище: всё локально, в профиле
	_check("новый профиль: деньги и стартовый набор", Profile.money == Balance.START_MONEY and _idx("w_rifle") >= 0, "%d ₽, %d записей" % [Profile.money, Profile.stash.size()])
	for id in ["w_rifle", "w_pistol", "vest_light", "helmet"]:
		Profile.equip_from_stash(_idx(id))
	_check("надето снаряжение", Profile.equipment.size() == 4, str(Profile.equipment.keys()))
	for id in ["ammo_545", "ammo_9x19", "bandage", "grenade"]:
		# все стопки предмета (патроны лежат в тайнике несколькими стопками)
		while _idx(id) >= 0 and Profile.stash_to_backpack(_idx(id), int(Profile.stash[_idx(id)].n)):
			pass
	_check("рюкзак собран — сетка без наложений", _ids(Profile.backpack) == 4 and ItemDb.grid_ok(Profile.backpack, Balance.BACKPACK_GRID), "%d ячеек, записей %d" % [Profile.backpack_cells(), Profile.backpack.size()])
	var m0 := Profile.money
	Profile.buy("ammo_12", 20)
	_check("покупка у торговца", Profile.money < m0 and _idx("ammo_12") >= 0, "%d ₽" % Profile.money)
	var m1 := Profile.money
	Profile.sell(_idx("painkillers"), 2)
	_check("продажа торговцу", Profile.money > m1 and _idx("painkillers") < 0, "%d ₽" % Profile.money)
	# верстак: обвесы на автомат (обвесы у Михалыча дорогие)
	_check("обвесы дороже обычной наценки", Profile.buy_price("mod_grip") > int(ItemDb.value("mod_grip") * Balance.TRADER_BUY_MULT),
		"рукоятка %d ₽" % Profile.buy_price("mod_grip"))
	Profile.money += 150000
	for id in ["mod_mag_ext", "mod_supp_545", "mod_grip"]:
		Profile.buy(id, 1)
		Profile.install_mod("primary", _idx(id))
	var wm := Profile.weapon_mods("primary")
	_check("верстак: обвесы на автомате", wm.size() == 3 and _idx("mod_grip") < 0, str(wm))
	var st := WeaponStats.compute("rifle", wm)
	var st0 := WeaponStats.compute("rifle", {})
	_check("характеристики: магазин 45, тише, меньше отдача, эргономика", int(st.mag) == 45 and float(st.noise_m) < float(st0.noise_m) and float(st.kick) < float(st0.kick) and bool(st.suppressed),
		"маг %d, шум %.0f→%.0f, отдача %.3f→%.3f, эрго %.0f→%.0f" % [int(st.mag), float(st0.noise_m), float(st.noise_m), float(st0.kick), float(st.kick), float(st0.ergo), float(st.ergo)])
	Profile.install_mod("primary", _idx("w_pistol")) # не обвес — не ставится
	_check("чужое на верстак не ставится", Profile.weapon_mods("primary").size() == 3, "")
	# модули убежища: верстак 1 не ставит прицелы; генератор + верстак 2 — ставит
	Profile.money += 200000
	Profile.buy("mod_rmr", 1)
	_check("верстак 1: коллиматор нельзя", Profile.mod_block("mod_rmr") != "", Profile.mod_block("mod_rmr"))
	_check("генератор без деталей не строится", Upgrades.block("generator") != "", Upgrades.block("generator"))
	for pair in [["battery", 2], ["wires", 5], ["toolset", 1], ["cigarettes", 5], ["lighter", 2]]:
		ItemDb.add_to(Profile.stash, ItemDb.make(String(pair[0]), int(pair[1])), Profile.stash_grid())
	Profile.trust = 3
	var built := Upgrades.build("generator") and Upgrades.build("workbench") and Upgrades.build("pocket")
	_check("модули построены: генератор, верстак 2, карман 2×2 — детали ушли", built and Upgrades.level("workbench") == 2 and Profile.pocket_grid() == Vector2i(2, 2)
		and Profile.stash_count("battery") == 0 and Profile.mod_block("mod_rmr") == "", str(Profile.modules))
	Profile.trust = 0
	# в карман — бинт: он поедет в рейд и вернётся
	Profile.buy("bandage", 1)
	Profile.transfer("stash", _idx("bandage"), "pocket", 0, 0, false)
	# обвес из рюкзака: коллиматор на пистолет, потом снять (ляжет в тайник)
	Profile.stash_to_backpack(_idx("mod_rmr"), 1)
	var bi := -1
	for i in range(Profile.backpack.size()):
		if String(Profile.backpack[i].id) == "mod_rmr":
			bi = i
	Profile.install_mod("secondary", bi, true)
	_check("верстак: обвес из рюкзака", String(Profile.weapon_mods("secondary").get("optic", "")) == "mod_rmr" and _ids(Profile.backpack) == 4, str(Profile.weapon_mods("secondary")))
	Profile.remove_mod("secondary", "optic")
	# задания: без рации — одно; убил троих — сдал за деньги и доверие
	_check("задание взято, второе — нет (слот один без рации)", Missions.take("m_kills3") and not Missions.take("m_dock"), str(Profile.missions_active))
	for i in range(3):
		Missions.on_kill()
	var mm := Profile.money
	var tr := Profile.trust
	_check("задание выполнено и сдано: деньги и доверие", Missions.turn_in("m_kills3") and Profile.money > mm and Profile.trust > tr and "m_kills3" in Profile.missions_done,
		"%d ₽, доверие %d" % [Profile.money - mm, Profile.trust - tr])
	Profile.trust = 0
	# этажи: первый открыт и выбран, второй закрыт до доверия
	_check("этажи: 1F открыт и выбран, 2F закрыт по доверию", Floors.is_open("f1") and Profile.floor == "f1" and not Floors.is_open("f2") and Floors.unlock_block("f2").begins_with("доверие")
		and Floors.start_block("f1") == "", Floors.unlock_block("f2"))

	# --- соло-рейд со снаряжением (на выбранный этаж — как кнопка в убежище)
	Profile.pending_raid = true
	get_tree().change_scene_to_file(Floors.scene(Profile.floor))
	for i in range(40):
		await get_tree().physics_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	pl.health.hp = 100.0
	await _wait(0.5)
	_check("в рейде — снаряжение, профиль пуст (на кону)", pl.loadout_mode and pl.inventory.loadout_ready and Profile.equipment.is_empty(), str(pl.inventory.equipment.keys()))
	_check("в руках автомат с обвесами, магазин на 45 заряжен", pl.weapon_id == "rifle" and pl.ammo == 45 and pl.weapon_mods.size() == 3, "%s %d %s" % [pl.weapon_id, pl.ammo, pl.weapon_mods])
	_check("патроны в рюкзаке ушли в магазин", pl.inventory.count("ammo_545") == 75, "%d" % pl.inventory.count("ammo_545"))
	pl.ammo = 5
	Input.action_press("reload")
	await _frames(2)
	Input.action_release("reload")
	await _wait(float(Balance.WEAPONS.rifle.reload) + 0.3)
	_check("перезарядка из рюкзака", pl.ammo == 45 and pl.inventory.count("ammo_545") == 35, "магазин %d, в рюкзаке %d" % [pl.ammo, pl.inventory.count("ammo_545")])
	# обвес прямо в рейде: фонарь из рюкзака — на автомат, потом снять обратно
	pl.inventory.add("mod_flashlight", 1)
	var fi := -1
	for i in range(pl.inventory.items.size()):
		if String(pl.inventory.items[i].id) == "mod_flashlight":
			fi = i
	Raid.current.request_install_mod("primary", "backpack", fi)
	await _frames(3)
	_check("в рейде: фонарь поставлен на автомат, модель в руках с ним", String(pl.inventory.equipment.primary.mods.get("tac", "")) == "mod_flashlight" and pl.weapon_mods.has("tac") and not pl.inventory.has("mod_flashlight"),
		str(pl.weapon_mods))
	Raid.current.request_remove_mod("primary", "tac")
	await _frames(3)
	_check("в рейде: фонарь снят в рюкзак", not pl.inventory.equipment.primary.mods.has("tac") and pl.inventory.has("mod_flashlight"), str(pl.inventory.equipment.primary.mods))
	pl.inventory.remove("mod_flashlight", 1)
	var dur0 := float(pl.inventory.equipment.armor.dur)
	pl.health.take_damage(40.0, pl.global_position + Vector3(0, 1, 5))
	_check("броня снимает урон и изнашивается", pl.health.hp > 60.0 and float(pl.inventory.equipment.armor.dur) < dur0, "hp %d, броня %.0f" % [int(pl.health.hp), float(pl.inventory.equipment.armor.dur)])
	Input.action_press("weapon_1")
	await _frames(3)
	Input.action_release("weapon_1")
	await _frames(2)
	_check("1 — пистолет", pl.weapon_id == "pistol" and pl.ammo == 12, "%s %d" % [pl.weapon_id, pl.ammo])
	# эвакуация через остановку
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	pl.health.hp = 1e9
	var bus := get_tree().current_scene.get_node("Extractions/Bus") as ExtractionPoint
	pl.global_position = bus.global_position + Vector3(0, 0.1, 0)
	await _wait(bus.channel_s + 1.0)
	_check("эвакуирован", Raid.current.is_extracted(1), "")
	await _frames(3)
	var back_ammo := 0
	for e in Profile.backpack:
		if String(e.id) == "ammo_545":
			back_ammo += int(e.n)
	_check("профиль: снаряжение вернулось", Profile.equipment.has("primary") and Profile.equipment.has("armor"), str(Profile.equipment.keys()))
	_check("профиль: патроны из магазина вернулись в рюкзак", back_ammo == 35 + 45, "5.45: %d" % back_ammo)
	_check("профиль: обвесы остались на автомате", Profile.weapon_mods("primary").size() == 3, str(Profile.weapon_mods("primary")))
	_check("карман: вернулся после рейда", Profile.pocket.size() == 1 and String(Profile.pocket[0].id) == "bandage", str(Profile.pocket))
	_check("эвакуация добавила доверия Михалыча", Profile.extractions == 1 and Profile.trust >= Balance.TRUST_PER_EXTRACTION, "доверие %d, выходов %d" % [Profile.trust, Profile.extractions])
	# доверие набрано — маршрут на 2F открывается за деньги, но этаж ещё не собран
	Profile.trust = 3
	Profile.money += 50000
	var m2 := Profile.money
	_check("маршрут на 2F открыт за доверие и деньги", Floors.unlock("f2") and Floors.is_open("f2") and Profile.money == m2 - int(Floors.find("f2").price),
		"%d ₽" % Profile.money)
	_check("2F: выход закрыт — этаж не собран", Floors.start_block("f2") == "этаж ещё не собран", Floors.start_block("f2"))
	# Enter — в убежище
	Input.action_press("ui_accept")
	await _frames(2)
	Input.action_release("ui_accept")
	for i in range(30):
		await get_tree().process_frame
	_check("Enter — назад в убежище", get_tree().current_scene and get_tree().current_scene.scene_file_path == Balance.HIDEOUT_SCENE and not Profile.pending_raid, str(get_tree().current_scene.scene_file_path if get_tree().current_scene else ""))
	# выручка Михалыча: ни ствола, ни денег — бесплатный набор; со стволом — не положено
	_check("со стволом выручки нет", not Profile.needs_rescue(), "")
	Profile.equipment = {}
	Profile.backpack = []
	Profile.pocket = []
	Profile.stash = Profile.stash.filter(func(e: Dictionary) -> bool: return String(ItemDb.equip(String(e.id)).get("weapon", "")) == "")
	Profile.money = 1000
	_check("без ствола и денег — выручка", Profile.needs_rescue() and Profile.take_rescue() and _idx("w_pistol") >= 0 and not Profile.needs_rescue(),
		"пистолет в тайнике: %s" % (_idx("w_pistol") >= 0))
	print("loadout_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Сколько разных предметов в списке (стопки одного — одна позиция).
func _ids(list: Array) -> int:
	var seen := {}
	for e in list:
		seen[String(e.id)] = true
	return seen.size()


func _idx(id: String) -> int:
	for i in range(Profile.stash.size()):
		if String(Profile.stash[i].id) == id:
			return i
	return -1


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])
