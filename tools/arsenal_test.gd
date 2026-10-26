extends Node
## Арсенал по тест-кейсам ТЗ (docs/design/weapons.md, CASE 1–20) на тестовом профиле: прицелы
## (основной + угловой, переключение, от первого лица и в изометрии), фонарь и ЛЦУ по разным
## точкам, новый обвес из данных, пробитие плит патронами, плиты спереди / сзади, ИИ тратит
## патроны и роняет остаток, снять прицел с трупа, снять плиту, эвакуация и перезагрузка профиля
## сохраняют всё (обвес, состояние фонаря / ЛЦУ, выбранный прицел, трофеи).
## godot --path . res://tools/arsenal_test.tscn

const TEST_PROFILE := "user://profile_arsenal_test.json"

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file(TEST_PROFILE, true)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	_data_cases(rng)
	# снаряжение: AK-12 (LPVO + угловой коллиматор + ЛЦУ справа) + фонарь слева,
	# плитоносец с плитами спереди и сзади
	var w := WeaponDb.make_weapon("AR_06_MARKSMAN", rng, [100, 100])
	w = Gear.fit(w, ItemDb.make("tac_flashlight_01", 1), "side_left")[0]
	Profile.equipment = {"primary": w, "armor": WeaponDb.make_vest("armor_top", {"front": "plate_ceramic", "back": "plate_steel"}),
		"helmet": ItemDb.make("helmet_mid", 1), "ears": ItemDb.make("headset_active", 1),
		"backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	Profile.backpack = []
	ItemDb.add_to(Profile.backpack, ItemDb.make("ammo_545_std", 60), Balance.BACKPACK_GRID)
	Profile.save()

	# --- рейд
	Profile.pending_raid = true
	get_tree().change_scene_to_file(Floors.scene(Profile.floor))
	for i in range(40):
		await get_tree().physics_frame
	for m in get_tree().get_nodes_in_group("marauders"):
		(m as Node).queue_free()
	var pl := Raid.current.local_player()
	pl.health.hp = 1e9
	pl.health.head_protected = func() -> bool: return true
	pl.global_position = SectorBuilder.polar(-100.0, 72.0) + Vector3(0, 0.1, 0)
	await _frames(5)
	# клавиша ствола, который уже в руках, убирает его — нажимаем, только если в руках не он
	if pl.weapon_slot != "primary" or pl.weapon_id == "":
		await _tap("weapon_1")
	_check("в руках AK-12 из снаряжения", pl.weapon_id == "wpn_ar_01" and pl.weapon_slot == "primary", pl.weapon_id)

	# CASE 4: фонарь слева и ЛЦУ справа — оба на модели одновременно
	var lights := pl.find_children("Flashlight_side_left", "SpotLight3D", true, false)
	var beams := pl.find_children("LaserBeam_side_right", "Node3D", true, false)
	_check("CASE 4: фонарь (слева) и ЛЦУ (справа) стоят одновременно", not lights.is_empty() and not beams.is_empty(), "фонарей %d, лучей %d" % [lights.size(), beams.size()])
	# CASE 5: только фонарь
	await _tac("light")
	_check("CASE 5: включён только фонарь", _on(pl, "side_left", "light") and not _on(pl, "side_right", "laser") and pl.light_on and not pl.laser_on, str(pl.weapon_mods))
	# CASE 6: только ЛЦУ
	await _tac("light")
	await _tac("laser")
	_check("CASE 6: включён только ЛЦУ", not _on(pl, "side_left", "light") and _on(pl, "side_right", "laser") and not pl.light_on and pl.laser_on, str(pl.weapon_mods))
	# CASE 7: оба
	await _tac("light")
	_check("CASE 7: включены оба", _on(pl, "side_left", "light") and _on(pl, "side_right", "laser") and pl.light_on and pl.laser_on, "")
	var lit := 0
	# от первого лица фонарь светит с модели в руках у камеры, на теле — у напарников
	for n in get_tree().root.find_children("Flashlight_side_left", "SpotLight3D", true, false):
		lit += 1 if (n as SpotLight3D).visible else 0
	_check("…фонарь на модели светит", lit > 0, "")

	# CASE 2: от первого лица — основной (LPVO, в оптику) и угловой (ствол заваливается на 45°)
	CameraRig.first_person_mode = true
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	Input.action_press("aim")
	await _wait(1.2)
	var roll_p := _vm_roll(rig)
	var scope_p := rig.scope_active
	var pos_p := rig._viewmodel.position if rig._viewmodel else Vector3.ZERO
	pl._toggle_sight()
	await _wait(1.2)
	var roll_o := _vm_roll(rig)
	var pos_o := rig._viewmodel.position if rig._viewmodel else Vector3.ZERO
	_check("CASE 2: от первого лица — основной: оптика, ствол ровно; угловой: без оптики, крен 45°, другая линия",
		scope_p and absf(roll_p) < 4.0 and not rig.scope_active and absf(roll_o - 45.0) < 5.0 and pos_p.distance_to(pos_o) > 0.01,
		"крен %.1f° → %.1f°, оптика %s → %s, сдвиг линии %.3f м" % [roll_p, roll_o, scope_p, rig.scope_active, pos_p.distance_to(pos_o)])
	Input.action_release("aim")
	CameraRig.first_person_mode = false
	await _frames(10)
	# CASE 3: в изометрии — выбранный прицел меняет наведение (приближение, разброс от бедра)
	var e := pl.weapon_entry()
	var so := WeaponStats.compute(e)
	var ep := e.duplicate(true)
	ep["sight"] = "primary"
	var sp := WeaponStats.compute(ep)
	_check("CASE 3: изометрия — основной (LPVO): дальше обзор; угловой: без приближения, от бедра точнее",
		String(so.sight) == _angled(e) and String(sp.sight) == "primary" and float(sp.iso_zoom) > float(so.iso_zoom) and bool(sp.scoped) and not bool(so.scoped)
		and float(Balance.ISO_AIM.offset_hip) < float(Balance.ISO_AIM.scope_hip),
		"приближение %.2f / %.2f" % [float(sp.iso_zoom), float(so.iso_zoom)])

	# CASE 8: снял фонарь — ЛЦУ работает
	Raid.current.request_strip("equip:primary", -1, "mod:side_left")
	await _frames(6)
	_check("CASE 8: фонарь снят в рюкзак — ЛЦУ светит", not pl.weapon_mods.has("side_left") and _on(pl, "side_right", "laser") and pl.laser_on
		and pl.inventory.has("tac_flashlight_01"), str(pl.weapon_mods.keys()))
	# CASE 11: снял LPVO в рейде — угловой остался и им можно целиться
	Raid.current.request_strip("equip:primary", -1, "mod:optic_primary")
	await _frames(6)
	var e11 := pl.weapon_entry()
	_check("CASE 11: LPVO снят — угловой коллиматор на кронштейне на месте и выбран", pl.inventory.has("optic_lpvo_01") and _angled(e11) != ""
		and String(WeaponStats.compute(e11).sight) == _angled(e11), str(WeaponStats.sights_of(e11)))
	# CASE 19: снять заднюю плиту со своего плитоносца
	Raid.current.request_strip("equip:armor", -1, "plate:back")
	await _frames(4)
	_check("CASE 19: задняя плита снята в рюкзак", not (pl.inventory.equipment.armor.plates as Dictionary).has("back") and pl.inventory.has("plate_steel"),
		str((pl.inventory.equipment.armor.plates as Dictionary).keys()))

	# консоль разработчика — команды буквально как в ТЗ
	var codes := {"VERAS54": "wpn_ar_01", "AK12": "wpn_ar_01", "545_AP": "ammo_545_ap", "LPVO_01": "optic_lpvo_01", "OFFSET_RED_DOT_01": "optic_zorin_k1",
		"FLASHLIGHT_01": "tac_flashlight_01", "LASER_01": "tac_laser_01", "AR_06_PATROL": "preset:AR_06_PATROL"}
	var bad := []
	for c in codes:
		if ArsenalDev.resolve(String(c)) != String(codes[c]):
			bad.append("%s→%s" % [c, ArsenalDev.resolve(String(c))])
	var ap0 := pl.inventory.count("ammo_545_ap")
	ArsenalDev.run(get_tree(), "give ammo 545_AP 120".split(" "))
	ArsenalDev.run(get_tree(), "set weapon durability 25".split(" "))
	ArsenalDev.run(get_tree(), "damage plate front 5".split(" "))
	await _frames(4)
	_check("консоль: коды ТЗ, give ammo, set weapon durability, damage plate", bad.is_empty() and pl.inventory.count("ammo_545_ap") == ap0 + 120
		and is_equal_approx(float(pl.inventory.equipment.primary.dur), 25.0) and float(pl.inventory.equipment.armor.plates.front.dur) < float(ItemDb.max_dur("plate_ceramic")),
		str(bad))
	# выданное консолью — прочь из рюкзака (иначе трофеям с трупа не хватит места)
	pl.inventory.remove("ammo_545_ap", pl.inventory.count("ammo_545_ap"))

	# CASE 17: ИИ тратит патроны; после смерти — остаток в магазине, запасные целы
	var m := (preload("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "ArsenalNpc"
	m.archetype = "pmc"
	m.loadout_id = "perimeter_marksman"
	m.patrol_point_provider = func() -> Vector3: return m.global_position
	get_tree().current_scene.get_node("Marauders").add_child(m)
	m.global_position = SectorBuilder.polar(-104.0, 72.0) + Vector3(0, 0.1, 0)
	await _frames(3)
	m.process_mode = Node.PROCESS_MODE_DISABLED
	var m0 := m._mag
	var pid := String(m.equipment.primary.id)
	var shots := 0
	m.last_known = m.global_position + Vector3(sin(m._facing), 0.0, cos(m._facing)) * 12.0
	for i in range(40):
		if shots >= 7:
			break
		m._shot_t = 0.0
		var before := m._mag
		m._try_fire()
		shots += before - m._mag
	var left := m._mag
	var spare_n := m.spare.size()
	_check("CASE 17: ИИ тратит настоящие патроны", shots == 7 and left == m0 - 7 and int((m.equipment.primary.mag as Dictionary).rounds) == left,
		"выстрелов %d, в магазине %d → %d" % [shots, m0, left])
	m.process_mode = Node.PROCESS_MODE_INHERIT
	# насмерть (шлем может удержать пулю — тогда лёг бы раненым)
	(m.get_node("Health") as Health).take_damage(9999.0, pl.global_position, "blast_close")
	await _frames(6)
	var crate: LootContainer = null
	for cn in get_tree().get_nodes_in_group("loot_containers"):
		var cc := cn as LootContainer
		if cc.display_name == "Ящик мародёра" and (crate == null or cc.global_position.distance_to(m.global_position) < crate.global_position.distance_to(m.global_position)):
			crate = cc
	var wi := -1
	var mags := 0
	if crate:
		for i in range(crate.items.size()):
			if String(crate.items[i].id) == pid:
				wi = i
			elif (crate.items[i] as Dictionary).has("rounds"):
				mags += 1
	# (магазины могут быть и сверх запасных — из таблицы лута «Периметра»)
	_check("CASE 17: в ящике — оружие с остатком в магазине и запасные магазины", wi >= 0 and int(crate.items[wi].mag.rounds) == left and mags >= spare_n,
		"остаток %d, запасных %d из %d" % [int(crate.items[wi].mag.rounds) if wi >= 0 else -1, mags, spare_n])
	# CASE 18: снять прицел с трупа
	if crate:
		pl.global_position = crate.global_position + Vector3(0.8, 0.1, 0)
		await _frames(4)
		var opt := WeaponDb.mod_id(crate.items[wi].mods.optic_primary) if wi >= 0 else ""
		var had := _count_in(crate.items, opt) + _count_in(pl.inventory.buffer, opt)
		Raid.current.request_strip("loot", wi, "mod:optic_primary", crate)
		await _frames(4)
		# снятое с вещи в ящике — в свободные клетки того же ящика, нет места — в буфер окна; не в рюкзак
		_check("CASE 18: прицел снят с оружия в ящике — в ящике или буфере", opt != "" and _count_in(crate.items, opt) + _count_in(pl.inventory.buffer, opt) == had + 1 and not (crate.items[wi].mods as Dictionary).has("optic_primary"),
			opt)
		# CASE 20 (часть 1): трофей — оружие целиком, как есть
		var trophy: Dictionary = (crate.items[wi] as Dictionary).duplicate(true)
		Raid.current.request_take_idx(crate, wi)
		await _frames(4)
		_check("трофей в рюкзаке — то самое оружие (обвес, магазин, износ)", _find(pl.inventory.items, trophy) >= 0, str(trophy.get("mods", {}).keys()))
		set_meta("trophy", trophy)

	# вернуть LPVO и фонарь на свои точки, выбрать угловой, включить фонарь и ЛЦУ
	Raid.current.request_fit("equip:primary", -1, _bi(pl, "optic_lpvo_01"), "optic_primary")
	await _frames(4)
	Raid.current.request_fit("equip:primary", -1, _bi(pl, "tac_flashlight_01"), "side_left")
	await _frames(6)
	if String(WeaponStats.compute(pl.weapon_entry()).sight) != _angled(pl.weapon_entry()):
		pl._toggle_sight()
	if not _on(pl, "side_left", "light"):
		await _tac("light")
	await _wait(1.0)
	var mods_before := {}
	for k in pl.weapon_mods:
		mods_before[k] = WeaponDb.mod_id(pl.weapon_mods[k])
	# эвакуация
	pl.global_position = SectorBuilder.polar(-100.0, 72.0) + Vector3(0, 0.1, 0)
	await _frames(3)
	var bus := get_tree().current_scene.get_node("Extractions/Bus") as ExtractionPoint
	pl.global_position = bus.global_position + Vector3(0, 0.1, 0)
	await _wait(bus.channel_s + 1.0)
	_check("эвакуирован", Raid.current.is_extracted(1), "")
	await _frames(3)
	# CASE 9: после эвакуации — основной, угловой, фонарь, ЛЦУ и их состояние
	var pw: Dictionary = Profile.equipment.get("primary", {})
	_check("CASE 9: после эвакуации обвес и состояния на месте", _mods_ok(pw, mods_before) and String(pw.get("sight", "")) == _angled(pw)
		and bool((pw.mods.side_left as Dictionary).get("light", false)) and bool((pw.mods.side_right as Dictionary).get("laser", false)),
		"%s, прицел %s" % [str(pw.get("mods", {})), String(pw.get("sight", ""))])
	# CASE 20: трофей в профиле — как был
	_check("CASE 20: трофей после эвакуации — в том же состоянии", has_meta("trophy") and _find(Profile.backpack, get_meta("trophy")) >= 0, "")
	# CASE 10: перезагрузка сохранения — выбранный прицел и обвес целы
	Profile.use_file(TEST_PROFILE, false)
	var rw: Dictionary = Profile.equipment.get("primary", {})
	_check("CASE 10: после перезагрузки профиля прицел «угловой», обвес и фонарь / ЛЦУ целы", String(WeaponStats.compute(rw).sight) == _angled(rw) and _mods_ok(rw, mods_before)
		and bool((rw.mods.side_left as Dictionary).get("light", false)) and bool((rw.mods.side_right as Dictionary).get("laser", false)), String(rw.get("sight", "")))
	print("arsenal_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Кейсы без сцены: только коллиматор, новый обвес из данных, пробитие, плиты спереди / сзади.
func _data_cases(rng: RandomNumberGenerator) -> void:
	var missing_flavor: Array[String] = []
	var catalog_count := 0
	for section in ["weapons", "ammo", "magazines", "attachments"]:
		for raw_id in WeaponDb.ids(section):
			var id := String(raw_id)
			catalog_count += 1
			if String(ItemDb.item(id).get("flavor", "")).strip_edges() == "":
				missing_flavor.append(id)
	_check("каталог: у всех 144 элементов есть отдельная игровая фраза", catalog_count == 144 and missing_flavor.is_empty(),
		"элементов %d, без фразы: %s" % [catalog_count, ", ".join(missing_flavor)])
	var vss_item: Dictionary = ItemDb.item("wpn_sp_02")
	var vss_spec: Dictionary = WeaponDb.weapon("wpn_sp_02")
	var vss_integral: Dictionary = vss_spec.get("integral", {})
	_check("ВСС: отдельный редкий ствол, встроенный глушитель, родные магазины 10 / 20 и иконка",
		String(vss_item.get("name", "")) == "VSS Vintorez" and int(vss_item.get("tier", 0)) == 4
		and bool(vss_integral.get("suppressed", false))
		and String(vss_spec.get("default_mag", "")) == "mag_939_10"
		and WeaponDb.mag_fits("wpn_sp_02", "mag_939_10") and WeaponDb.mag_fits("wpn_sp_02", "mag_939_20")
		and ResourceLoader.exists("res://assets/icons/wpn_sp_02.png"), str(vss_item))
	var weapon_info := ItemInfo.describe("wpn_sp_02")
	var ammo_info := ItemInfo.describe("ammo_545_std")
	var mag_info := ItemInfo.describe("mag_545_60")
	var mod_info := ItemInfo.describe("optic_4x_01")
	_check("карточки: характеристики и фраза видны у оружия, патрона, магазина и обвеса",
		"Технические характеристики" in weapon_info and "Надёжность" in weapon_info and "В деле:" in weapon_info
		and "Скорость" in ammo_info and "В деле:" in ammo_info
		and "Влияние:" in mag_info and "В деле:" in mag_info
		and "Эффекты:" in mod_info and "В деле:" in mod_info, "")
	# CASE 1: только коллиматор — один прицел, без оптики, в прицеле точнее, чем без него
	var rd := WeaponDb.make_weapon("AR_03_RD", rng, [100, 100])
	var st := WeaponStats.compute(rd)
	var bare := rd.duplicate(true)
	bare["mods"] = {}
	var st0 := WeaponStats.compute(bare)
	var model := WeaponModels.build(String(rd.id), rd.mods)
	_check("CASE 1: только коллиматор — один основной прицел, в прицеле точнее", WeaponStats.sights_of(rd) == ["primary"] and String(st.sight) == "primary" and not bool(st.scoped)
		and float(st.ads_spread) < float(st0.ads_spread) and model.has_meta("sight_h") and not model.has_meta("sight_offset"),
		"разброс в прицеле %.2f → %.2f" % [float(st0.ads_spread), float(st.ads_spread)])
	model.free()
	# CASE 12: новый прицел и новый ствол — только данными (интерфейс RAIL_TOP), без кода
	var att := {"name": "Коллиматор тестовый", "cat": "mod", "size": [1, 1], "value": 1000, "stack": 1, "weight": 0.2, "tier": 1, "rarity": "common", "tags": [],
		"attach": {"type": "OPTIC_RED_DOT", "fits": ["RAIL_TOP"], "look": "red_dot", "fx": {"ads_spread": 0.5, "ergo": -1}, "role": "PRIMARY", "zoom": 0.0, "aim_k": 1.1}}
	var gun: Dictionary = (WeaponDb._w.weapons.wpn_ar_04 as Dictionary).duplicate(true)
	gun["name"] = "Автомат тестовый"
	gun["code"] = "AR_99"
	WeaponDb._w.attachments["optic_test_99"] = att
	WeaponDb._w.weapons["wpn_test_99"] = gun
	WeaponDb._items["optic_test_99"] = att
	WeaponDb._items["wpn_test_99"] = gun
	var ne := {"id": "wpn_test_99", "n": 1, "dur": 100.0, "mods": {}, "mag": WeaponDb.make_mag("mag_545_30", "ammo_545_std", 30)}
	var r := Gear.fit(ne, {"id": "optic_test_99", "n": 1}, "")
	_check("CASE 12: новый прицел встал на новый ствол по интерфейсу (данные, без кода)", String(r[2]) == "" and WeaponDb.mod_id((r[0].mods as Dictionary).get("optic_primary", "")) == "optic_test_99"
		and float(WeaponStats.compute(r[0]).ads_spread) < float(WeaponStats.compute(ne).ads_spread), String(r[2]))
	WeaponDb._w.attachments.erase("optic_test_99")
	WeaponDb._w.weapons.erase("wpn_test_99")
	WeaponDb._items.erase("optic_test_99")
	WeaponDb._items.erase("wpn_test_99")
	# CASE 13/14: пистолетный FMJ против тяжёлой плиты — почти никак; автоматный бронебойный — пробивает
	var pd := WeaponDb.plate("plate_military")
	var fmj := WeaponDb.ammo("ammo_919_fmj")
	var ap := WeaponDb.ammo("ammo_545_ap")
	var dm_fmj := _mean_through("plate_military", fmj, rng)
	var dm_ap := _mean_through("plate_military", ap, rng)
	_check("CASE 13: 9×19 FMJ против тяжёлой плиты — не пробивает", Armor.pen_chance(float(fmj.pen), int(pd["class"])) < 0.05 and dm_fmj < float(fmj.damage) * 0.5,
		"шанс %.2f, в среднем прошло %.1f из %d" % [Armor.pen_chance(float(fmj.pen), int(pd["class"])), dm_fmj, int(fmj.damage)])
	_check("CASE 14: 5.45 бронебойный — намного эффективнее против плиты", Armor.pen_chance(float(ap.pen), int(pd["class"])) > Armor.pen_chance(float(fmj.pen), int(pd["class"])) + 0.3
		and dm_ap > dm_fmj * 2.0, "шанс %.2f, в среднем прошло %.1f из %d" % [Armor.pen_chance(float(ap.pen), int(pd["class"])), dm_ap, int(ap.damage)])
	# CASE 15/16: попадания спереди бьют переднюю плиту, сзади — заднюю (плита закрывает не всю
	# грудь — серия из 10)
	var eq := {"armor": WeaponDb.make_vest("armor_top", {"front": "plate_ceramic", "back": "plate_ceramic"})}
	var at := Vector3(0, 1.3, 0)
	var fwd := Vector3(0, 0, 1)
	var f0 := float(eq.armor.plates.front.dur)
	var b0 := float(eq.armor.plates.back.dur)
	for i in range(10):
		eq = Armor.hit(eq, 40.0, "thorax", at + fwd * 10.0, at, fwd, {"pen": 5.0, "armor_dmg": 3.0}, rng).equipment
	var p1: Dictionary = eq.armor.plates
	var f1 := float(p1.front.dur)
	_check("CASE 15: спереди — урон передней плите, задняя цела", f1 < f0 and is_equal_approx(float(p1.back.dur), b0),
		"перед %.0f→%.0f, зад %.0f" % [f0, f1, float(p1.back.dur)])
	for i in range(10):
		eq = Armor.hit(eq, 40.0, "thorax", at - fwd * 10.0, at, fwd, {"pen": 5.0, "armor_dmg": 3.0}, rng).equipment
	var p2: Dictionary = eq.armor.plates
	_check("CASE 16: сзади — урон задней плите, передняя без изменений", float(p2.back.dur) < b0 and is_equal_approx(float(p2.front.dur), f1),
		"зад %.0f→%.0f, перед %.0f" % [b0, float(p2.back.dur), float(p2.front.dur)])


## Средний урон, прошедший через плиту plate_id спереди, пулей патрона a (200 выстрелов по новой плите).
func _mean_through(plate_id: String, a: Dictionary, rng: RandomNumberGenerator) -> float:
	var sum := 0.0
	for i in range(200):
		var eq := {"armor": WeaponDb.make_vest("armor_top", {"front": plate_id})}
		var h := Armor.hit(eq, float(a.damage), "thorax", Vector3(0, 1.3, 10), Vector3(0, 1.3, 0), Vector3(0, 0, 1), {"pen": float(a.pen), "armor_dmg": float(a.armor_dmg)}, rng)
		sum += float(h.damage)
	return sum / 200.0


func _on(pl: Player, mount: String, kind: String) -> bool:
	return Player.tac_on(pl.weapon_mods, _meta_node(mount), kind)


func _meta_node(mount: String) -> Node:
	var n := Node.new()
	n.set_meta("mount", mount)
	n.queue_free()
	return n


## Крен модели в руках вокруг оси взгляда, градусы (угловой прицел — 45).
func _vm_roll(rig: CameraRig) -> float:
	if rig._viewmodel == null:
		return 999.0
	var up := rig._viewmodel.transform.basis.y
	return rad_to_deg(atan2(-up.x, up.y))


## Угловой прицел сборки (на кронштейне с креном), "" — нет. Старой точки «угловой» больше нет.
func _angled(e: Dictionary) -> String:
	var model_key: String = WeaponBuild.model_of(String(e.get("id", "")))
	for k: Variant in WeaponStats.sights_of(e):
		if WeaponBuild.depth(String(k)) > 0 and not is_zero_approx(WeaponBuild.point_roll(model_key, e.get("mods", {}), String(k))):
			return String(k)
	return ""


func _mods_ok(e: Dictionary, want: Dictionary) -> bool:
	var mods: Dictionary = e.get("mods", {})
	if mods.size() != want.size():
		return false
	for k in want:
		if WeaponDb.mod_id(mods.get(k, "")) != String(want[k]):
			return false
	return true


## Индекс записи, совпадающей с trophy по сути (id, обвес, магазин, износ).
func _find(list: Array, trophy: Dictionary) -> int:
	for i in range(list.size()):
		var e: Dictionary = list[i]
		if String(e.id) != String(trophy.id) or not is_equal_approx(float(e.get("dur", 0)), float(trophy.get("dur", 0))):
			continue
		var a := {}
		for k in e.get("mods", {}):
			a[k] = WeaponDb.mod_id(e.mods[k])
		var b := {}
		for k in trophy.get("mods", {}):
			b[k] = WeaponDb.mod_id(trophy.mods[k])
		if a == b and int(e.mag.rounds) == int(trophy.mag.rounds) and String(e.mag.get("ammo", "")) == String(trophy.mag.get("ammo", "")):
			return i
	return -1


func _bi(pl: Player, id: String) -> int:
	for i in range(pl.inventory.items.size()):
		if String(pl.inventory.items[i].id) == id:
			return i
	return -1


func _tac(kind: String) -> void:
	await _tap("flashlight" if kind == "light" else "laser")
	await _frames(6)


func _tap(action: String) -> void:
	Input.action_press(action)
	await _frames(2)
	Input.action_release(action)
	await _frames(3)


func _wait(sec: float) -> void:
	await get_tree().create_timer(sec).timeout


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _count_in(list: Array, id: String) -> int:
	var n := 0
	for e in list:
		if String((e as Dictionary).get("id", "")) == id:
			n += int((e as Dictionary).get("count", 1))
	return n
